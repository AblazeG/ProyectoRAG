"""Orquestador de auditorías (C2). Actúa como mediador: invoca en orden solo
los servicios que necesita el flujo y nunca toca C7 directamente.

Flujo (sección 5 del informe):
 1. la API valida esquema, extensión y tamaño;   2. C2 crea la traza;
 3. C3 aplica E1 al archivo y E2/E3 a las notas;
 4. caché exacta de informes (si acierta: S4 y paso 10);
 5. C5 ``analizar_malla``;                        6. el enrutador elige ruta;
 7. por hallazgo G/M: caché de hallazgos y, si falla, recuperación con agente;
 8. el gateway explica los hallazgos sin acierto en lotes de hasta 4;
 9. S1–S3 y luego S4 (sin modelo: solo S4);
10. plantilla, caché, métricas y respuesta.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

from pydantic import BaseModel

from servicio.cache.exacta import CacheExacta, sha256
from servicio.contexto import prompts
from servicio.contexto.herramientas import Analizador, ResultadoAnalisis
from servicio.contexto.recuperador import Indice
from servicio.dominio import (
    SIN_NORMA,
    SIN_NORMA_VERIFICADA,
    AlmacenArchivosTemporales,
    ArchivoSubido,
    ErrorDominio,
    Hallazgo,
    Recuperado,
    RepositorioInformes,
    RespuestaExplicaciones,
)
from servicio.guardrails.entrada import GuardrailsEntrada
from servicio.guardrails.salida import MENSAJE_SEGURO_FORMATO, GuardrailsSalida, es_sin_norma
from servicio.modelos.enrutador import SIN_MODELO, DecisionRuta, Enrutador
from servicio.modelos.gateway import Gateway, ResultadoGateway
from servicio.observabilidad.traza import RegistroTrazas, Traza
from servicio.orquestacion.agente import Agente, Presupuesto

CORRECCION_S1 = ("La respuesta anterior no cumplía el esquema JSON pedido. Responde de nuevo "
                 "solo con el JSON válido.")
CORRECCION_S3 = ("La respuesta anterior contenía cifras que no aparecen en los fragmentos "
                 "citados. Reescríbela sin mediciones de la malla y usando solo cifras de los "
                 "fragmentos.")


# ---------------------------------------------------------------------------
# Utilidades compartidas con el orquestador de preguntas
# ---------------------------------------------------------------------------

def versiones_actuales(analizador: Analizador, indice: Indice, gateway: Gateway,
                       embeddings_nombre: str) -> dict:
    return {"perfiles": analizador.catalogo.version, "analizador": analizador.version,
            "corpus": indice.version_corpus, "prompt": prompts.VERSION_PROMPT,
            "modelos": {"rapido": gateway.nombre_modelo("rapido"),
                        "completo": gateway.nombre_modelo("completo"),
                        "embeddings": embeddings_nombre}}


def llamar_con_s1(gateway: Gateway, salida: GuardrailsSalida, alias: str,
                  mensajes: list[dict], modelo: type[BaseModel], ruta: str,
                  traza: Traza) -> tuple[BaseModel | None, ResultadoGateway]:
    """Llama al gateway y valida S1; reintenta una vez si el JSON no es válido."""
    resultado = gateway.generar(alias, mensajes, modelo.model_json_schema(), ruta=ruta, traza=traza)
    instancia = salida.validar_formato(resultado.generacion.texto, modelo)
    if instancia is None:
        traza.registrar_guardrail("S1")
        reintento = mensajes + [{"role": "assistant", "content": resultado.generacion.texto},
                                {"role": "user", "content": CORRECCION_S1}]
        resultado = gateway.generar(alias, reintento, modelo.model_json_schema(),
                                    ruta=ruta, traza=traza)
        instancia = salida.validar_formato(resultado.generacion.texto, modelo)
    return instancia, resultado


def fuente_de(recuperado: Recuperado | None) -> dict | None:
    if recuperado is None:
        return None
    f = recuperado.fragmento
    return {"id": f.id, "documento": f.titulo, "doc_id": f.doc_id, "seccion": f.seccion,
            "pagina": f.pagina, "puntaje": round(recuperado.puntaje, 4), "fragmento": f.texto}


@dataclass
class _Explicada:
    explicacion: str
    correccion: list[str]
    citas: list[str]
    malas: list[str] = field(default_factory=list)
    s2: bool = False


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------

class Auditor:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 cache: CacheExacta, analizador: Analizador, enrutador: Enrutador,
                 gateway: Gateway, agente: Agente, indice: Indice,
                 temporales: AlmacenArchivosTemporales, informes: RepositorioInformes,
                 trazas: RegistroTrazas, embeddings_nombre: str,
                 lote: int = prompts.LOTE_HALLAZGOS, num_ctx: int = prompts.NUM_CTX,
                 max_reformulaciones_informe: int = 6):
        self.entrada = entrada
        self.salida = salida
        self.cache = cache
        self.analizador = analizador
        self.enrutador = enrutador
        self.gateway = gateway
        self.agente = agente
        self.indice = indice
        self.temporales = temporales
        self.informes = informes
        self.trazas = trazas
        self.embeddings_nombre = embeddings_nombre
        self.lote = lote
        self.num_ctx = num_ctx
        self.max_reformulaciones_informe = max_reformulaciones_informe

    def versiones(self) -> dict:
        return versiones_actuales(self.analizador, self.indice, self.gateway,
                                  self.embeddings_nombre)

    # -- punto de entrada ---------------------------------------------------
    def auditar(self, archivo: ArchivoSubido, perfil: str, notas: str = "") -> dict:
        traza = Traza("auditoria", perfil, self.trazas, prompts.VERSION_PROMPT,
                      self.indice.version_corpus)
        inicio = time.perf_counter()
        ruta_archivo = None
        try:
            self.analizador.catalogo.obtener(perfil)
            with traza.etapa("C7.archivo_temporal"):
                ruta_archivo = self.temporales.guardar(archivo.contenido, archivo.extension)
            return self._auditar(traza, archivo, ruta_archivo, perfil, notas, inicio)
        except ErrorDominio as error:
            guardrail = getattr(error, "guardrail", None)
            if guardrail:
                traza.registrar_guardrail(guardrail)
            traza.anotar(estado="rechazo" if guardrail else "error",
                         error=type(error).__name__)
            error.cuerpo = self._responder(
                {"detalle": error.mensaje, "traza_id": traza.traza_id,
                 "guardrails": list(traza.datos["guardrails"])}, con_modelo=False)
            raise
        finally:
            if ruta_archivo is not None:
                self.temporales.borrar(ruta_archivo)  # la malla no se conserva
            traza.cerrar()

    def _responder(self, respuesta: dict, con_modelo: bool) -> dict:
        """Único punto de salida: todo camino de respuesta pasa por S4."""
        return self.salida.aplicar_aviso(respuesta, con_modelo=con_modelo)

    def _auditar(self, traza: Traza, archivo: ArchivoSubido, ruta_archivo, perfil: str,
                 notas: str, inicio: float) -> dict:
        # 3. Guardrails de entrada
        with traza.etapa("C3.entrada"):
            malla = self.entrada.verificar_archivo(archivo, ruta_archivo)
            notas_ok = self.entrada.verificar_texto(notas, "notas")
            for g in notas_ok.activaciones:
                traza.registrar_guardrail(g)
        archivo_sha = sha256(archivo.contenido)
        versiones = self.versiones()
        traza.anotar(archivo_sha=archivo_sha, version_corpus=versiones["corpus"])

        # 4. Caché exacta de informes
        with traza.etapa("C4.cache"):
            clave = self.cache.clave_informe(archivo_sha, perfil, notas_ok.texto, versiones)
            guardado = self.cache.obtener_informe(clave)
        if guardado is not None:
            informe = dict(guardado)
            informe.update(auditoria_id=uuid.uuid4().hex, traza_id=traza.traza_id,
                           cache="exacta", iteraciones_agente=0,
                           tiempo_ms=round((time.perf_counter() - inicio) * 1000, 2),
                           guardrails=list(traza.datos["guardrails"]))
            traza.anotar(cache="exacta", ruta=informe.get("ruta"), modelo=informe.get("modelo"),
                         hallazgos=self._conteo(informe["hallazgos"]))
            with traza.etapa("C3.salida"):
                respuesta = self._responder(informe, con_modelo=informe.get("ruta") != SIN_MODELO)
            with traza.etapa("C7.persistencia"):
                self.informes.guardar(respuesta, archivo_sha)
            return respuesta

        # 5. Análisis determinista
        with traza.etapa("C5.analisis"):
            resultado = self.analizador.analizar(ruta_archivo, perfil, malla)
        # 6. Enrutador
        decision = self.enrutador.ruta_auditoria(resultado.hallazgos)
        traza.anotar(ruta=decision.ruta, hallazgos=self._conteo(
            [{"gravedad": h.gravedad} for h in resultado.hallazgos]))

        # 7–9. Explicaciones (solo si la ruta usa modelo)
        validado = True
        cache_hallazgos = 0
        if decision.alias is not None:
            validado, cache_hallazgos = self._explicar(traza, resultado, decision, perfil,
                                                       notas_ok.texto, versiones)
        if cache_hallazgos:
            traza.anotar(cache="hallazgos")

        # 10. Plantilla, S4, caché y persistencia
        with traza.etapa("C2.ensamblado"):
            informe = self._ensamblar(resultado, perfil, decision, traza, archivo, versiones,
                                      inicio, cache_hallazgos)
        with traza.etapa("C3.salida"):
            respuesta = self._responder(informe, con_modelo=decision.ruta != SIN_MODELO)
        with traza.etapa("C4.cache"):
            para_cache = {k: v for k, v in respuesta.items()
                          if k not in ("auditoria_id", "traza_id", "tiempo_ms")}
            self.cache.guardar_informe(clave, para_cache, versiones["corpus"], validada=validado)
        with traza.etapa("C7.persistencia"):
            self.informes.guardar(respuesta, archivo_sha)
        return respuesta

    # -- pasos 7 a 9 ----------------------------------------------------------
    def _explicar(self, traza: Traza, resultado: ResultadoAnalisis, decision: DecisionRuta,
                  perfil: str, notas: str, versiones: dict) -> tuple[bool, int]:
        self.indice.verificar_compatibilidad()
        explicables = [h for h in resultado.hallazgos if h.explicable]
        modelo_ruta = self.gateway.nombre_modelo(decision.alias)
        claves = {}
        pendientes: list[Hallazgo] = []
        aciertos = 0
        with traza.etapa("C4.cache_hallazgos"):
            for h in explicables:
                claves[h.id] = self.cache.clave_hallazgo(
                    h.verificacion, perfil, h.gravedad, versiones["corpus"],
                    versiones["prompt"], modelo_ruta)
                guardado = self.cache.obtener_hallazgo(claves[h.id])
                if guardado is not None:
                    h.explicacion = guardado["explicacion"]
                    h.correccion = list(guardado.get("correccion") or [])
                    h.fuente = guardado.get("fuente")
                    aciertos += 1
                else:
                    pendientes.append(h)

        presupuesto = Presupuesto(self.max_reformulaciones_informe)
        fragmentos: dict[str, list[Recuperado]] = {}
        with traza.etapa("C5.recuperacion"):
            for h in pendientes:
                r = self.agente.recuperar_con_agente(h.consulta, perfil, presupuesto, traza,
                                                     etiqueta=h.id)
                fragmentos[h.id] = r.fragmentos
        con_norma = [h for h in pendientes if fragmentos[h.id]]
        for h in pendientes:
            if not fragmentos[h.id]:
                h.explicacion, h.correccion, h.fuente = SIN_NORMA, [], None

        validados: dict[str, bool] = {h.id: True for h in pendientes if not fragmentos[h.id]}
        with traza.etapa("C6.modelo"):
            for lote in prompts.lotes(con_norma, self.lote):
                validados.update(self._explicar_lote(traza, lote, fragmentos, decision,
                                                     perfil, notas))
        for h in pendientes:
            if validados.get(h.id) and fragmentos[h.id]:
                self.cache.guardar_hallazgo(claves[h.id], h.__dict__, versiones["corpus"],
                                            validada=True)
        return all(validados.values()), aciertos

    def _procesar(self, instancia: RespuestaExplicaciones, lote: list[Hallazgo],
                  fragmentos: dict[str, list[Recuperado]],
                  entregados: set[str]) -> dict[str, _Explicada]:
        """S2 (citas) y detección de S3 (cifras) para cada hallazgo del lote."""
        por_id = {e.id: e for e in instancia.hallazgos}
        procesadas = {}
        for h in lote:
            e = por_id.get(h.id)
            if e is None:
                continue
            permitidos = {r.fragmento.id for r in fragmentos[h.id]} & entregados
            if es_sin_norma(e.explicacion):
                procesadas[h.id] = _Explicada(SIN_NORMA, [], [])
                continue
            exp = self.salida.verificar_citas(e.explicacion, e.citas, permitidos)
            pasos = [self.salida.verificar_citas(p, e.citas, permitidos) for p in e.correccion]
            citas = list(dict.fromkeys(exp.citas + [c for p in pasos for c in p.citas]))
            s2 = bool(exp.removidas or any(p.removidas for p in pasos))
            textos = [r.fragmento.texto for r in fragmentos[h.id] if r.fragmento.id in citas]
            malas = self.salida.verificar_cifras(" ".join([exp.texto] + [p.texto for p in pasos]),
                                                 textos)
            procesadas[h.id] = _Explicada(exp.texto, [p.texto for p in pasos if p.texto],
                                          citas, malas, s2)
        return procesadas

    def _explicar_lote(self, traza: Traza, lote: list[Hallazgo],
                       fragmentos: dict[str, list[Recuperado]], decision: DecisionRuta,
                       perfil: str, notas: str) -> dict[str, bool]:
        nombre_perfil = self.analizador.catalogo.obtener(perfil).nombre
        mensajes, entregados = prompts.construir_explicacion(lote, fragmentos, nombre_perfil,
                                                             notas, self.num_ctx)
        instancia, resultado = llamar_con_s1(self.gateway, self.salida, decision.alias, mensajes,
                                             RespuestaExplicaciones, decision.ruta, traza)
        traza.datos["modelo_explicacion"] = resultado.modelo
        traza.datos["respaldo_explicacion"] = (traza.datos.get("respaldo_explicacion", False)
                                               or resultado.uso_respaldo)
        if instancia is None:  # S1 falló dos veces: mensaje seguro
            for h in lote:
                h.explicacion, h.correccion, h.fuente = MENSAJE_SEGURO_FORMATO, [], None
            return {h.id: False for h in lote}
        procesadas = self._procesar(instancia, lote, fragmentos, entregados)
        if any(p.malas for p in procesadas.values()):  # S3: reintentar una vez
            traza.registrar_guardrail("S3")
            reintento = mensajes + [{"role": "assistant", "content": resultado.generacion.texto},
                                    {"role": "user", "content": CORRECCION_S3}]
            nueva, _ = llamar_con_s1(self.gateway, self.salida, decision.alias, reintento,
                                     RespuestaExplicaciones, decision.ruta, traza)
            if nueva is not None:
                procesadas = self._procesar(nueva, lote, fragmentos, entregados)
        validos = {}
        indice_fragmentos = {r.fragmento.id: r for h in lote for r in fragmentos[h.id]}
        for h in lote:
            p = procesadas.get(h.id)
            if p is None:
                h.explicacion, h.correccion, h.fuente = MENSAJE_SEGURO_FORMATO, [], None
                validos[h.id] = False
                continue
            valido = True
            if p.malas:  # tras el reintento: eliminar las frases sin respaldo
                p.explicacion = self.salida.eliminar_frases(p.explicacion, p.malas)
                p.correccion = [x for x in (self.salida.eliminar_frases(c, p.malas)
                                            for c in p.correccion) if x]
                valido = False
            if p.s2:
                traza.registrar_guardrail("S2")
            if p.explicacion == SIN_NORMA:
                h.explicacion, h.correccion, h.fuente = SIN_NORMA, [], None
            elif not p.citas:
                h.explicacion = f"{p.explicacion or SIN_NORMA} ({SIN_NORMA_VERIFICADA})"
                h.correccion, h.fuente = p.correccion, None
                valido = False
            else:
                h.explicacion, h.correccion = p.explicacion, p.correccion
                h.fuente = fuente_de(indice_fragmentos.get(p.citas[0]))
            validos[h.id] = valido and not p.s2
        return validos

    # -- paso 10 --------------------------------------------------------------
    @staticmethod
    def _conteo(hallazgos: list[dict]) -> dict:
        cuenta = {"grave": 0, "menor": 0, "informativo": 0}
        for h in hallazgos:
            cuenta[h["gravedad"]] = cuenta.get(h["gravedad"], 0) + 1
        return cuenta

    def _ensamblar(self, resultado: ResultadoAnalisis, perfil: str, decision: DecisionRuta,
                   traza: Traza, archivo: ArchivoSubido, versiones: dict, inicio: float,
                   cache_hallazgos: int) -> dict:
        """Plantilla: las mediciones las pone siempre la plantilla, nunca el modelo."""
        datos_perfil = self.analizador.catalogo.obtener(perfil)
        hallazgos = []
        for h in resultado.hallazgos:
            informativo = not h.explicable
            hallazgos.append({
                "id": h.id, "verificacion": h.verificacion, "tipo": h.tipo,
                "gravedad": h.gravedad, "descripcion": h.descripcion,
                "medido": h.medido, "limite": h.limite,
                "explicacion": None if informativo else h.explicacion,
                "correccion": [] if informativo else list(h.correccion),
                "fuente": None if informativo else h.fuente,
                "norma_esperada": h.norma,
            })
        cuenta = resultado.contar()
        resumen = (f"{datos_perfil.nombre}: {cuenta['grave']} graves, {cuenta['menor']} menores "
                   f"y {cuenta['informativo']} informativos. Semáforo {resultado.semaforo}.")
        if resultado.no_medibles:
            resumen += (f" {', '.join(resultado.no_medibles)} no se pueden medir en "
                        f"{resultado.metricas['formato'].upper()}: audita el archivo en OBJ.")
        modelo = None
        if decision.ruta != SIN_MODELO:  # el modelo que explicó, no el que reformuló
            modelo = (traza.datos.get("modelo_explicacion")
                      or self.gateway.nombre_modelo(decision.alias))
            traza.anotar(modelo=modelo)
        return {
            "auditoria_id": uuid.uuid4().hex,
            "archivo": archivo.nombre,
            "perfil": perfil,
            "perfil_nombre": datos_perfil.nombre,
            "resumen": resumen,
            "semaforo": resultado.semaforo,
            "metricas_malla": resultado.metricas,
            "hallazgos": hallazgos,
            "modelo": modelo or "plantilla",
            "ruta": decision.ruta,
            "uso_respaldo": bool(traza.datos.get("uso_respaldo")),
            "cache": "hallazgos" if cache_hallazgos else "ninguna",
            "guardrails": list(dict.fromkeys(traza.datos["guardrails"])),
            "iteraciones_agente": traza.datos["iteraciones_agente"],
            "tiempo_ms": round((time.perf_counter() - inicio) * 1000, 2),
            "traza_id": traza.traza_id,
            "versiones": versiones,
        }


def informe_a_markdown(informe: dict) -> str:
    """Exportación del informe a Markdown (``GET /auditorias/{id}/markdown``)."""
    m = informe["metricas_malla"]
    lineas = [f"# Informe de auditoría MeshAudit — {informe.get('archivo', '')}", "",
              f"- **Perfil:** {informe.get('perfil_nombre', informe['perfil'])}",
              f"- **Semáforo:** {informe['semaforo']}",
              f"- **Ruta:** {informe['ruta']} · **Modelo:** {informe['modelo']} · "
              f"**Caché:** {informe['cache']}",
              f"- **Dimensión máxima:** {m.get('dimension_max')} {m.get('unidad')} · "
              f"**Triángulos:** {m.get('triangulos')}",
              "", informe["resumen"], "", "## Hallazgos", ""]
    if not informe["hallazgos"]:
        lineas.append("Sin hallazgos.")
    for h in informe["hallazgos"]:
        lineas += [f"### {h['verificacion']} · {h['descripcion']} ({h['gravedad']})", "",
                   f"- Medido: `{h['medido']}` · Límite: `{h['limite']}`"]
        if h.get("explicacion"):
            lineas += ["", h["explicacion"]]
        if h.get("correccion"):
            lineas += ["", "**Pasos de corrección:**"]
            lineas += [f"{i}. {paso}" for i, paso in enumerate(h["correccion"], start=1)]
        if h.get("fuente"):
            f = h["fuente"]
            lineas += ["", f"> **Fuente:** {f['documento']} — {f['seccion']} "
                           f"(`{f['id']}`, puntaje {f['puntaje']})", ">",
                       "> " + f["fragmento"].replace("\n", "\n> ")]
        lineas.append("")
    lineas += ["---", f"_{informe.get('aviso', '')}_", "",
               f"Traza: `{informe['traza_id']}`"]
    return "\n".join(lineas)


Versionador = Callable[[], dict]
