"""Orquestador de ingesta de normas (C2).

E5(archivo) → extraer → E5(texto) → fragmentar e indexar (version_corpus++) →
purgar la caché de versiones anteriores.
"""
from __future__ import annotations

from servicio.cache.exacta import CacheExacta
from servicio.contexto.recuperador import Indice
from servicio.dominio import ArchivoSubido, ErrorDominio, RechazoSolicitud
from servicio.guardrails.entrada import MENSAJE_CUARENTENA, GuardrailsEntrada
from servicio.guardrails.salida import GuardrailsSalida
from servicio.observabilidad.traza import RegistroTrazas, Traza


class ServicioIngesta:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 indice: Indice, cache: CacheExacta, trazas: RegistroTrazas):
        self.entrada = entrada
        self.salida = salida
        self.indice = indice
        self.cache = cache
        self.trazas = trazas

    def _envolver(self, traza: Traza, error: ErrorDominio) -> None:
        guardrail = getattr(error, "guardrail", None)
        if guardrail:
            traza.registrar_guardrail(guardrail)
        traza.anotar(estado="rechazo" if guardrail else "error", error=type(error).__name__)
        error.cuerpo = self.salida.aplicar_aviso(
            {"detalle": error.mensaje, "traza_id": traza.traza_id,
             "guardrails": list(traza.datos["guardrails"])}, con_modelo=False)

    def ingestar(self, archivo: ArchivoSubido, licencia: str | None = None,
                 doc_id: str | None = None, perfiles: list[str] | None = None,
                 titulo: str | None = None) -> dict:
        traza = Traza("ingesta", None, self.trazas, version_corpus=self.indice.version_corpus)
        try:
            with traza.etapa("C3.entrada"):
                revision = self.entrada.verificar_documento(archivo, licencia=licencia)
            with traza.etapa("C5.extraccion"):
                documento = self.indice.extraer(archivo)
            with traza.etapa("C3.entrada"):
                contenido = self.entrada.verificar_documento(texto=documento.texto)
            if contenido["cuarentena"]:
                self.indice.registrar_cuarentena(archivo, contenido["motivo"])
                raise RechazoSolicitud(422, MENSAJE_CUARENTENA, "E5")
            with traza.etapa("C5.indexado"):
                registro = self.indice.indexar(documento, archivo, revision["licencia"],
                                               doc_id=doc_id, perfiles=perfiles, titulo=titulo)
            with traza.etapa("C4.purga"):
                registro["entradas_purgadas"] = self.cache.purgar(registro["version_corpus"])
            traza.anotar(version_corpus=registro["version_corpus"], doc_id=registro["doc_id"])
            return registro
        except ErrorDominio as error:
            self._envolver(traza, error)
            raise
        finally:
            traza.cerrar()

    def eliminar(self, doc_id: str) -> dict:
        traza = Traza("eliminacion", None, self.trazas)
        try:
            resultado = self.indice.eliminar(doc_id)
            resultado["entradas_purgadas"] = self.cache.purgar(resultado["version_corpus"])
            traza.anotar(version_corpus=resultado["version_corpus"], doc_id=doc_id)
            return resultado
        except ErrorDominio as error:
            self._envolver(traza, error)
            raise
        finally:
            traza.cerrar()

    def listar(self) -> list[dict]:
        return self.indice.listar()

    def manifiesto(self) -> dict:
        return {**self.indice.manifiesto(), "fragmentos": self.indice.almacen.contar()}
