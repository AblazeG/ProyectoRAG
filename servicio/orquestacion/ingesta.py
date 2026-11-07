"""Orquestador de ingesta de normas (C2), figura 6 del informe.

``ingerir(doc)``: E5(archivo) → C5 extrae y fragmenta → E5(texto) →
C5 indexa (embeddings, alta, versión++ en el manifiesto) → C4 purga la
versión anterior → ``DocIndexado``.
"""
from __future__ import annotations

from servicio.cache.exacta import CacheExacta
from servicio.cache.semantica import CacheSemantica
from servicio.contexto.recuperador import Indice
from servicio.dominio import (ArchivoSubido, Conflicto, DocIndexado, EntradaInvalida,
                              ErrorDominio, ErrorInterno, RechazoSolicitud)
from servicio.guardrails.entrada import MENSAJE_CUARENTENA, GuardrailsEntrada
from servicio.guardrails.salida import GuardrailsSalida
from servicio.observabilidad.traza import RegistroTrazas, Traza
from servicio.orquestacion.auditor import cuerpo_de_error


def _doc_indexado(registro: dict) -> DocIndexado:
    return DocIndexado(documento_id=registro["doc_id"], nombre=registro.get("nombre", ""),
                       formato=registro.get("formato", ""), licencia=registro.get("licencia", ""),
                       perfiles=registro.get("perfiles", []), fragmentos=registro.get("fragmentos", 0),
                       version_corpus=registro.get("version_corpus", 0), fecha=registro.get("fecha", 0.0),
                       titulo=registro.get("titulo", ""))


class ServicioIngesta:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 indice: Indice, cache: CacheExacta, trazas: RegistroTrazas,
                 cache_semantica: CacheSemantica | None = None):
        self.entrada = entrada
        self.salida = salida
        self.indice = indice
        self.cache = cache
        self.cache_semantica = cache_semantica
        self.trazas = trazas

    def ingerir(self, doc: ArchivoSubido, licencia: str | None = None,
                doc_id: str | None = None, perfiles: list[str] | None = None,
                titulo: str | None = None, reemplazar: bool = False) -> DocIndexado:
        traza = Traza("ingesta", None, self.trazas, version_corpus=self.indice.version_corpus)
        try:
            with traza.etapa("guardrails_entrada"):                   # E5 (archivo)
                aprobado = self.entrada.verificar_documento(doc, licencia=licencia)
            with traza.etapa("contexto_extraccion"):                  # extraer y fragmentar
                documento, fragmentos, registro = self.indice.extraer_y_fragmentar(
                    doc, aprobado.detalles["licencia"], doc_id, perfiles, titulo)
            if not fragmentos:   # p. ej. un HTML sin contenido extraíble
                raise EntradaInvalida("El documento no tiene texto extraíble para indexar.")
            with traza.etapa("guardrails_entrada"):                   # E5 (texto)
                contenido = self.entrada.verificar_documento(texto=documento.texto)
            if not contenido.aprobado:
                self.indice.registrar_cuarentena(doc, "contenido con instrucciones")
                raise RechazoSolicitud(422, MENSAJE_CUARENTENA, "E5")
            existente = self.indice.obtener(registro["doc_id"])
            if existente and existente.get("estado") == "indexado":
                if existente.get("sha256") == registro["sha256"]:
                    # Mismo contenido: no se reindexa ni se invalida la caché.
                    traza.anotar(doc_id=registro["doc_id"], sin_cambios=True)
                    return _doc_indexado(existente)
                if existente.get("nombre") != registro["nombre"] and not reemplazar:
                    raise Conflicto(f"Ya existe el documento «{registro['doc_id']}» con otro "
                                    "archivo; envía reemplazar=true para sustituirlo.")
            with traza.etapa("contexto_indexado"):                    # embeddings + versión++
                indexado = self.indice.indexar(fragmentos, registro)
            with traza.etapa("cache"):                                # purgar versión anterior
                indexado.entradas_purgadas = self._purgar(indexado.version_corpus)
            traza.anotar(version_corpus=indexado.version_corpus, doc_id=indexado.documento_id)
            return indexado
        except ErrorDominio as error:
            error.cuerpo = cuerpo_de_error(self.salida, traza, error, "respuesta")
            raise
        except Exception as exc:  # noqa: BLE001
            error = ErrorInterno()
            traza.anotar(detalle_error=f"{type(exc).__name__}: {exc}"[:300])
            error.cuerpo = cuerpo_de_error(self.salida, traza, error, "respuesta")
            raise error from exc
        finally:
            traza.cerrar()

    def eliminar(self, doc_id: str) -> dict:
        """Elimina el documento y sus fragmentos, sube la versión y purga la caché."""
        traza = Traza("eliminacion", None, self.trazas)
        try:
            resultado = self.indice.eliminar(doc_id)
            resultado["entradas_purgadas"] = self._purgar(resultado["version_corpus"])
            traza.anotar(version_corpus=resultado["version_corpus"], doc_id=doc_id)
            return resultado
        except ErrorDominio as error:
            error.cuerpo = cuerpo_de_error(self.salida, traza, error, "respuesta")
            raise
        finally:
            traza.cerrar()

    def _purgar(self, version: int) -> int:
        """Purga la caché exacta y la semántica de las versiones anteriores del corpus."""
        purgadas = self.cache.purgar(version)
        if self.cache_semantica is not None:
            purgadas += self.cache_semantica.purgar(version)
        return purgadas

    def reindexar(self) -> int:
        """Vacía el índice (cambio de modelo de embeddings, ADR-02) y purga la caché.
        Después hay que volver a ``ingerir`` el corpus."""
        version = self.indice.vaciar()
        self._purgar(version)
        return version

    def listar(self) -> list[dict]:
        """Documentos con identificador (``documento_id``), nombre, formato, fecha y fragmentos."""
        return [{"documento_id": d.get("doc_id"), **d} for d in self.indice.listar()]

    def manifiesto(self) -> dict:
        return {**self.indice.manifiesto(), "fragmentos": self.indice.almacen.contar()}
