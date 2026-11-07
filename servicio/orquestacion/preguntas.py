"""Orquestador de preguntas de seguimiento (C2), función secundaria (RF6).

Figura 8: ``verificar_texto`` (E2–E4) → caché exacta → ``buscar_similar``
(caché semántica) → S4. Si no hay acierto (figura 10): ciclo de agente →
gateway (ruta rápida) → S1–S3 → S4 → caché.
"""
from __future__ import annotations

import json
import time

from servicio.cache.exacta import CacheExacta
from servicio.cache.semantica import CacheSemantica
from servicio.contexto import prompts
from servicio.contexto.herramientas import Analizador
from servicio.contexto.recuperador import Indice
from servicio.dominio import (
    SIN_NORMA,
    SIN_NORMA_VERIFICADA,
    EntradaInvalida,
    ErrorDominio,
    ErrorInterno,
    Fragmento,
    NoEncontrado,
    Recuperado,
    RepositorioInformes,
    RespuestaPreguntaModelo,
)
from servicio.guardrails.entrada import MENSAJE_FUERA_DOMINIO, GuardrailsEntrada
from servicio.guardrails.salida import MENSAJE_SEGURO_FORMATO, GuardrailsSalida
from servicio.modelos.enrutador import Enrutador
from servicio.modelos.gateway import Gateway
from servicio.observabilidad.traza import RegistroTrazas, Traza
from servicio.orquestacion.agente import CicloAgente, Presupuesto
from servicio.orquestacion.auditor import (cuerpo_de_error, fuente_de, generar_verificado,
                                           versiones_actuales)


def _version_semantica(versiones: dict) -> str:
    """Todo lo que cambia una respuesta salvo el corpus (que va aparte para la purga)."""
    return json.dumps({k: v for k, v in versiones.items() if k != "corpus"}, sort_keys=True)


def texto_del_informe(informe: dict) -> str:
    """Resumen del informe en texto (para E4 y como fragmento citable)."""
    partes = [f"Informe de auditoría. Semáforo {informe.get('semaforo', '')}. "
              f"{informe.get('resumen', '')}."]
    for h in informe.get("hallazgos", []):
        partes.append(f"Hallazgo {h['id']} ({h['verificacion']}, {h['gravedad']}): "
                      f"{h.get('descripcion', h['tipo'])}; medido {h['medido']}, límite {h['limite']}.")
        if h.get("explicacion"):
            partes.append(h["explicacion"])
    return "\n".join(partes)


class ServicioPreguntas:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 cache: CacheExacta, cache_semantica: CacheSemantica, analizador: Analizador,
                 enrutador: Enrutador, gateway: Gateway, agente: CicloAgente, indice: Indice,
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
        return self.salida.aplicar_aviso(respuesta, con_modelo=con_modelo, tipo="respuesta")

    # -- preguntar(id, texto) → Respuesta ----------------------------------
    def preguntar(self, id: str, texto: str) -> dict:  # noqa: A002 - nombre de la tabla 6
        informe = self.informes.obtener(id)
        if informe is None:
            raise NoEncontrado("Auditoría no encontrada.")
        traza = Traza("pregunta", informe["perfil"], self.trazas, prompts.VERSION_PROMPT,
                      self.indice.version_corpus)
        traza.anotar(auditoria_id=id, archivo_sha=informe.get("_archivo_sha"))
        inicio = time.perf_counter()
        try:
            if not (texto or "").strip():
                raise EntradaInvalida("La pregunta está vacía.")
            return self._preguntar(traza, informe, texto, inicio)
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

    def _base(self, informe: dict, traza: Traza, inicio: float, **campos) -> dict:
        base = {"auditoria_id": informe["auditoria_id"], "respuesta": "", "fuentes": [],
                "cache": "ninguna", "modelo": None, "ruta": None, "uso_respaldo": False,
                "guardrails": traza.guardrails,
                "iteraciones_agente": traza.datos["iteraciones_agente"],
                "traza_id": traza.traza_id}
        base.update(campos)
        base["tiempo_ms"] = round((time.perf_counter() - inicio) * 1000, 2)
        return base

    def _preguntar(self, traza: Traza, informe: dict, pregunta: str, inicio: float) -> dict:
        perfil = informe["perfil"]
        archivo_sha = informe.get("_archivo_sha") or ""
        texto_informe = texto_del_informe(informe)
        with traza.etapa("guardrails_entrada"):                   # E2, E3 y E4
            veredicto = self.entrada.verificar_texto(pregunta, "pregunta", texto_informe, perfil)
        for g in veredicto.activaciones:
            traza.registrar_guardrail(g)
        traza.anotar(**veredicto.detalles)
        if veredicto.motivo == "fuera_de_dominio":                # mensaje seguro, sin modelo
            traza.anotar(ruta="sin_modelo")
            return self._responder(self._base(informe, traza, inicio,
                                              respuesta=MENSAJE_FUERA_DOMINIO,
                                              ruta="sin_modelo", modelo="plantilla"),
                                   con_modelo=False)
        texto = veredicto.texto

        versiones = versiones_actuales(self.analizador, self.indice, self.gateway,
                                       self.embeddings_nombre)
        with traza.etapa("cache"):
            clave = self.cache.clave_pregunta(archivo_sha, perfil, texto, versiones)
            exacta = self.cache.obtener_pregunta(clave)
            semantica = None if exacta else self.cache_semantica.buscar_similar(
                texto, archivo_sha, perfil, versiones["corpus"], _version_semantica(versiones))
        if exacta or semantica:
            tipo = "exacta" if exacta else "semantica"
            guardado = dict(exacta or semantica[0])
            traza.anotar(cache=tipo, ruta=guardado.get("ruta"), modelo=guardado.get("modelo"))
            if semantica:
                traza.anotar(similitud_cache=round(semantica[1], 4))
            # La cita del informe apunta a la auditoría actual, no a la que llenó la caché.
            propio = f"informe:{informe['auditoria_id']}#1"
            for fuente in guardado.get("fuentes", []):
                if str(fuente.get("id", "")).startswith("informe:"):
                    guardado["respuesta"] = guardado["respuesta"].replace(fuente["id"], propio)
                    fuente["id"] = propio
            respuesta = self._base(informe, traza, inicio, **{
                k: v for k, v in guardado.items() if k in ("respuesta", "fuentes", "modelo", "ruta")})
            respuesta["cache"] = tipo
            with traza.etapa("guardrails_salida"):
                return self._responder(respuesta, con_modelo=True)

        # Ciclo de agente (uso principal: preguntas coloquiales)
        self.indice.verificar_compatibilidad()
        with traza.etapa("contexto_rag"):
            normas, _ = self.agente.recuperar_con_agente(
                texto, perfil, Presupuesto(self.max_reformulaciones), traza)
        del_informe = Recuperado(Fragmento(
            id=f"informe:{informe['auditoria_id']}#1", doc_id="informe", texto=texto_informe,
            titulo="Informe de auditoría", seccion="Hallazgos y mediciones", pagina=None,
            formato="informe", licencia="-", perfiles=[perfil]),
            veredicto.detalles.get("similitud_informe", 0.0))
        fragmentos = normas + [del_informe]

        with traza.etapa("enrutador"):
            ruta = self.enrutador.clasificar(tipo="pregunta")
        traza.anotar(ruta=ruta.ruta)
        mensajes, entregados = prompts.construir_pregunta(texto, texto_informe, fragmentos,
                                                          self.num_ctx)
        por_id = {r.fragmento.id: r for r in fragmentos}
        resultado, generacion = generar_verificado(
            self.gateway, self.salida, traza, ruta, mensajes, RespuestaPreguntaModelo,
            entregados, {i: r.fragmento.texto for i, r in por_id.items()})
        item = resultado.detalles.get("respuesta") if resultado.motivo != "formato" else None
        if item is None:
            respuesta_texto, citas, validada = MENSAJE_SEGURO_FORMATO, [], False
        elif item["sin_norma"]:
            respuesta_texto, citas, validada = SIN_NORMA, [], True
        elif not item["citas"]:
            respuesta_texto, citas, validada = (f"{item['texto'] or SIN_NORMA} "
                                                f"({SIN_NORMA_VERIFICADA})"), [], False
        else:
            respuesta_texto, citas = item["texto"], item["citas"]
            validada = resultado.aprobado and not item["removidas"]
        traza.anotar(modelo=generacion.modelo)
        respuesta = self._base(informe, traza, inicio, respuesta=respuesta_texto,
                               fuentes=[fuente_de(por_id[c]) for c in citas if c in por_id],
                               modelo=generacion.modelo, ruta=ruta.ruta,
                               uso_respaldo=generacion.uso_respaldo)
        with traza.etapa("guardrails_salida"):
            respuesta = self._responder(respuesta, con_modelo=True)
        guardable = {k: respuesta[k] for k in ("respuesta", "fuentes", "modelo", "ruta")}
        with traza.etapa("cache"):  # solo lo que pasó S1–S3; nunca rechazos
            self.cache.guardar_pregunta(clave, guardable, versiones["corpus"], validada)
            self.cache_semantica.guardar(texto, archivo_sha, perfil, guardable,
                                         versiones["corpus"], validada,
                                         _version_semantica(versiones))
        return respuesta
