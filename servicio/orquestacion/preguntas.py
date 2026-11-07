"""Orquestador de preguntas de seguimiento (C2).

E2/E3 → E4 → caché exacta → caché semántica → agente de recuperación →
gateway (ruta rápida) → S1–S3 → S4.
"""
from __future__ import annotations

import time

from servicio.cache.exacta import CacheExacta
from servicio.cache.semantica import CacheSemantica
from servicio.contexto import prompts
from servicio.contexto.herramientas import Analizador
from servicio.contexto.recuperador import Indice
from servicio.dominio import (
    SIN_NORMA,
    SIN_NORMA_VERIFICADA,
    ErrorDominio,
    Fragmento,
    NoEncontrado,
    Recuperado,
    RepositorioInformes,
    RespuestaPreguntaModelo,
)
from servicio.guardrails.entrada import MENSAJE_FUERA_DOMINIO, GuardrailsEntrada
from servicio.guardrails.salida import MENSAJE_SEGURO_FORMATO, GuardrailsSalida, es_sin_norma
from servicio.modelos.enrutador import Enrutador
from servicio.modelos.gateway import Gateway
from servicio.observabilidad.traza import RegistroTrazas, Traza
from servicio.orquestacion.agente import Agente, Presupuesto
from servicio.orquestacion.auditor import CORRECCION_S3, fuente_de, llamar_con_s1, versiones_actuales


def texto_del_informe(informe: dict) -> str:
    """Resumen del informe en texto (para E4 y como fragmento citable)."""
    partes = [informe.get("resumen", "")]
    for h in informe.get("hallazgos", []):
        partes.append(f"{h['verificacion']} {h['descripcion']} ({h['gravedad']}): "
                      f"medido {h['medido']}, límite {h['limite']}.")
        if h.get("explicacion"):
            partes.append(h["explicacion"])
    return "\n".join(partes)


class ServicioPreguntas:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 cache: CacheExacta, cache_semantica: CacheSemantica, analizador: Analizador,
                 enrutador: Enrutador, gateway: Gateway, agente: Agente, indice: Indice,
                 informes: RepositorioInformes, trazas: RegistroTrazas, embeddings_nombre: str,
                 num_ctx: int = prompts.NUM_CTX, max_reformulaciones: int = 6):
        self.entrada = entrada
        self.salida = salida
        self.cache = cache
        self.cache_semantica = cache_semantica
        self.analizador = analizador
        self.enrutador = enrutador
        self.gateway = gateway
        self.agente = agente
        self.indice = indice
        self.informes = informes
        self.trazas = trazas
        self.embeddings_nombre = embeddings_nombre
        self.num_ctx = num_ctx
        self.max_reformulaciones = max_reformulaciones

    def _responder(self, respuesta: dict, con_modelo: bool) -> dict:
        return self.salida.aplicar_aviso(respuesta, con_modelo=con_modelo)

    def preguntar(self, auditoria_id: str, pregunta: str) -> dict:
        informe = self.informes.obtener(auditoria_id)
        if informe is None:
            raise NoEncontrado("Auditoría no encontrada.")
        perfil = informe["perfil"]
        traza = Traza("pregunta", perfil, self.trazas, prompts.VERSION_PROMPT,
                      self.indice.version_corpus)
        traza.anotar(auditoria_id=auditoria_id, archivo_sha=informe.get("_archivo_sha"))
        inicio = time.perf_counter()
        try:
            return self._preguntar(traza, informe, pregunta, inicio)
        except ErrorDominio as error:
            guardrail = getattr(error, "guardrail", None)
            if guardrail:
                traza.registrar_guardrail(guardrail)
            traza.anotar(estado="rechazo" if guardrail else "error", error=type(error).__name__)
            error.cuerpo = self._responder(
                {"detalle": error.mensaje, "traza_id": traza.traza_id,
                 "guardrails": list(traza.datos["guardrails"])}, con_modelo=False)
            raise
        finally:
            traza.cerrar()

    def _base(self, informe: dict, traza: Traza, inicio: float, **campos) -> dict:
        base = {"auditoria_id": informe["auditoria_id"], "respuesta": "", "fuentes": [],
                "cache": "ninguna", "modelo": None, "ruta": None, "uso_respaldo": False,
                "guardrails": list(dict.fromkeys(traza.datos["guardrails"])),
                "iteraciones_agente": traza.datos["iteraciones_agente"],
                "traza_id": traza.traza_id}
        base.update(campos)
        base["tiempo_ms"] = round((time.perf_counter() - inicio) * 1000, 2)
        return base

    def _preguntar(self, traza: Traza, informe: dict, pregunta: str, inicio: float) -> dict:
        perfil = informe["perfil"]
        archivo_sha = informe.get("_archivo_sha") or ""
        with traza.etapa("C3.entrada"):
            verificada = self.entrada.verificar_texto(pregunta, "pregunta")
            for g in verificada.activaciones:
                traza.registrar_guardrail(g)
            texto = verificada.texto
            texto_informe = texto_del_informe(informe)
            dominio = self.entrada.verificar_dominio(texto, texto_informe, perfil)
        traza.anotar(similitud_corpus=dominio.similitud_corpus,
                     similitud_informe=dominio.similitud_informe)
        if not dominio.en_dominio:  # E4: mensaje seguro, sin modelo
            traza.registrar_guardrail("E4")
            traza.anotar(ruta="sin_modelo")
            return self._responder(self._base(informe, traza, inicio, respuesta=MENSAJE_FUERA_DOMINIO,
                                              ruta="sin_modelo", modelo="plantilla"),
                                   con_modelo=False)

        versiones = versiones_actuales(self.analizador, self.indice, self.gateway,
                                       self.embeddings_nombre)
        with traza.etapa("C4.cache"):
            clave = self.cache.clave_pregunta(archivo_sha, perfil, texto, versiones)
            exacta = self.cache.obtener_pregunta(clave)
            semantica = None if exacta else self.cache_semantica.buscar(
                texto, archivo_sha, perfil, versiones["corpus"])
        if exacta or semantica:
            tipo = "exacta" if exacta else "semantica"
            guardado = dict(exacta or semantica[0])
            traza.anotar(cache=tipo, ruta=guardado.get("ruta"), modelo=guardado.get("modelo"))
            if semantica:
                traza.anotar(similitud_cache=round(semantica[1], 4))
            respuesta = self._base(informe, traza, inicio, **{
                k: v for k, v in guardado.items()
                if k in ("respuesta", "fuentes", "modelo", "ruta")})
            respuesta["cache"] = tipo
            return self._responder(respuesta, con_modelo=True)

        # Recuperación con agente (uso principal: preguntas coloquiales)
        self.indice.verificar_compatibilidad()
        with traza.etapa("C5.recuperacion"):
            agente = self.agente.recuperar_con_agente(texto, perfil,
                                                      Presupuesto(self.max_reformulaciones),
                                                      traza, etiqueta="pregunta")
        del_informe = Recuperado(Fragmento(
            id=f"informe:{informe['auditoria_id']}#1", doc_id="informe", texto=texto_informe,
            titulo="Informe de auditoría", seccion="Hallazgos y mediciones", pagina=None,
            formato="informe", licencia="-", perfiles=[perfil]), dominio.similitud_informe)
        fragmentos = agente.fragmentos + [del_informe]

        decision = self.enrutador.ruta_pregunta()
        traza.anotar(ruta=decision.ruta)
        with traza.etapa("C6.modelo"):
            mensajes, entregados = prompts.construir_pregunta(texto, texto_informe, fragmentos,
                                                              self.num_ctx)
            instancia, resultado = llamar_con_s1(self.gateway, self.salida, decision.alias,
                                                 mensajes, RespuestaPreguntaModelo,
                                                 decision.ruta, traza)
            validada = instancia is not None
            if instancia is None:
                respuesta_texto, citas = MENSAJE_SEGURO_FORMATO, []
            else:
                respuesta_texto, citas, malas, s2 = self._procesar(instancia, fragmentos, entregados)
                if malas:
                    traza.registrar_guardrail("S3")
                    reintento = mensajes + [
                        {"role": "assistant", "content": resultado.generacion.texto},
                        {"role": "user", "content": CORRECCION_S3}]
                    nueva, resultado = llamar_con_s1(self.gateway, self.salida, decision.alias,
                                                     reintento, RespuestaPreguntaModelo,
                                                     decision.ruta, traza)
                    if nueva is not None:
                        respuesta_texto, citas, malas, s2 = self._procesar(nueva, fragmentos,
                                                                           entregados)
                    if malas:
                        respuesta_texto = self.salida.eliminar_frases(respuesta_texto, malas)
                        validada = False
                if s2:
                    traza.registrar_guardrail("S2")
                    validada = False
                if not citas and not es_sin_norma(respuesta_texto):
                    respuesta_texto = f"{respuesta_texto or SIN_NORMA} ({SIN_NORMA_VERIFICADA})"
                    validada = False
        por_id = {r.fragmento.id: r for r in fragmentos}
        fuentes = [fuente_de(por_id[c]) for c in citas if c in por_id]
        respuesta = self._base(informe, traza, inicio, respuesta=respuesta_texto, fuentes=fuentes,
                               modelo=resultado.modelo, ruta=decision.ruta,
                               uso_respaldo=resultado.uso_respaldo)
        respuesta = self._responder(respuesta, con_modelo=True)
        guardable = {k: respuesta[k] for k in ("respuesta", "fuentes", "modelo", "ruta")}
        with traza.etapa("C4.cache"):
            self.cache.guardar_pregunta(clave, guardable, versiones["corpus"], validada)
            self.cache_semantica.guardar(texto, archivo_sha, perfil, guardable,
                                         versiones["corpus"], validada)
        return respuesta

    def _procesar(self, instancia: RespuestaPreguntaModelo, fragmentos: list[Recuperado],
                  entregados: set[str]):
        if es_sin_norma(instancia.respuesta):
            return SIN_NORMA, [], [], False
        citas = self.salida.verificar_citas(instancia.respuesta, instancia.citas, entregados)
        textos = [r.fragmento.texto for r in fragmentos if r.fragmento.id in citas.citas]
        malas = self.salida.verificar_cifras(citas.texto, textos)
        return citas.texto, citas.citas, malas, bool(citas.removidas)
