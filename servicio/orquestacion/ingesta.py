"""Orquestador de ingesta de normas (C2), figura 6 del informe.

``ingerir(doc)``: E5(archivo) → C5 extrae y fragmenta → E5(texto) →
C5 indexa (embeddings, alta, versión++ en el manifiesto) → C4 purga la
versión anterior → ``DocIndexado``.
"""
from __future__ import annotations

from servicio.cache.exacta import CacheExacta
from servicio.contexto.recuperador import Indice
from servicio.dominio import (ArchivoSubido, DocIndexado, EntradaInvalida, ErrorDominio,
                              RechazoSolicitud)
from servicio.guardrails.entrada import MENSAJE_CUARENTENA, GuardrailsEntrada
from servicio.guardrails.salida import GuardrailsSalida
from servicio.observabilidad.traza import RegistroTrazas, Traza
from servicio.orquestacion.auditor import cuerpo_de_error


class ServicioIngesta:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 indice: Indice, cache: CacheExacta, trazas: RegistroTrazas):
        self.entrada = entrada
        self.salida = salida
        self.indice = indice
        self.cache = cache
        self.trazas = trazas

    def ingerir(self, doc: ArchivoSubido, licencia: str | None = None,
                doc_id: str | None = None, perfiles: list[str] | None = None,
                titulo: str | None = None) -> DocIndexado:
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
            with traza.etapa("contexto_indexado"):                    # embeddings + versión++
                indexado = self.indice.indexar(fragmentos, registro)
            with traza.etapa("cache"):                                # purgar versión anterior
                indexado.entradas_purgadas = self.cache.purgar(indexado.version_corpus)
            traza.anotar(version_corpus=indexado.version_corpus, doc_id=indexado.documento_id)
            return indexado
        except ErrorDominio as error:
            error.cuerpo = cuerpo_de_error(self.salida, traza, error, "respuesta")
            raise
        finally:
            traza.cerrar()

    def eliminar(self, doc_id: str) -> dict:
        """Elimina el documento y sus fragmentos, sube la versión y purga la caché."""
        traza = Traza("eliminacion", None, self.trazas)
        try:
            resultado = self.indice.eliminar(doc_id)
            resultado["entradas_purgadas"] = self.cache.purgar(resultado["version_corpus"])
            traza.anotar(version_corpus=resultado["version_corpus"], doc_id=doc_id)
            return resultado
        except ErrorDominio as error:
            error.cuerpo = cuerpo_de_error(self.salida, traza, error, "respuesta")
            raise
        finally:
            traza.cerrar()

    def listar(self) -> list[dict]:
        return self.indice.listar()

    def manifiesto(self) -> dict:
        return {**self.indice.manifiesto(), "fragmentos": self.indice.almacen.contar()}
