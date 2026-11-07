"""Orquestador de auditorías (C2). Actúa como mediador: invoca en orden solo
los servicios que necesita el flujo y nunca toca C7 directamente.

Flujo (sección 5 y figura 7 del informe):
 1. la API valida esquema, extensión y tamaño;   2. C2 crea la traza;
 3. C3 verifica el archivo (E1) y las notas (E2, E3);
 4. caché exacta de informes (si acierta: S4 y paso 10);
 5. C5 ``analizar_malla``;                        6. C6 ``clasificar`` (ruta);
 7. por hallazgo G/M: caché de hallazgos; si falla, C5 recupera normas y el
    ciclo de agente reformula si la recuperación es pobre;
 8. el gateway explica los hallazgos sin acierto, en lotes de hasta 4;
 9. C3 verifica la salida (S1–S3) y aplica S4 (sin modelo: solo S4);
10. plantilla, caché, métricas (T1) y respuesta.
"""
from __future__ import annotations

import time
import uuid

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
    Generacion,
    Hallazgo,
    Recuperado,
    RepositorioInformes,
    RespuestaExplicaciones,
    Veredicto,
)
from servicio.guardrails.entrada import GuardrailsEntrada
from servicio.guardrails.salida import MENSAJE_SEGURO_FORMATO, GuardrailsSalida
from servicio.modelos.enrutador import SIN_MODELO, Enrutador, Ruta
from servicio.modelos.gateway import Gateway
from servicio.observabilidad.traza import RegistroTrazas, Traza
from servicio.orquestacion.agente import CicloAgente, Presupuesto

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


def generar_verificado(gateway: Gateway, salida: GuardrailsSalida, traza: Traza, ruta: Ruta,
                       mensajes: list[dict], modelo: type[BaseModel],
                       permitidos: dict[str, set[str]] | set[str],
                       textos: dict[str, str]) -> tuple[Veredicto, Generacion]:
    """Pasos 8 y 9: el gateway genera y C3 verifica la salida (S1–S3).

    S1 y S3 reintentan una vez; después, S1 deja que C2 escriba un mensaje
    seguro y S3 elimina las frases con cifras sin respaldo.
    """
    esquema = modelo.model_json_schema()

    def llamar(mensajes_):
        with traza.etapa("gateway"):
            generacion = gateway.generar(ruta.alias, mensajes_, esquema, ruta=ruta.ruta, traza=traza)
        with traza.etapa("guardrails_salida"):
            return salida.verificar_generacion(generacion.texto, modelo, permitidos, textos), generacion

    veredicto, generacion = llamar(mensajes)
    if veredicto.motivo == "formato":                                   # S1: reintentar una vez
        traza.registrar_guardrail("S1")
        veredicto, generacion = llamar(mensajes + [
            {"role": "assistant", "content": generacion.texto},
            {"role": "user", "content": CORRECCION_S1}])
        if veredicto.motivo == "formato":
            return veredicto, generacion
    if veredicto.motivo == "cifras":                                    # S3: reintentar una vez
        traza.registrar_guardrail("S3")
        nuevo, generacion = llamar(mensajes + [
            {"role": "assistant", "content": generacion.texto},
            {"role": "user", "content": CORRECCION_S3}])
        if nuevo.motivo != "formato":
            veredicto = nuevo
        if veredicto.motivo == "cifras":
            with traza.etapa("guardrails_salida"):
                veredicto = salida.eliminar_cifras(veredicto)
    for activacion in veredicto.activaciones:
        traza.registrar_guardrail(activacion)
    for item in veredicto.detalles.values():   # contadores para la tabla 16
        traza.sumar("citas_generadas", len(item["citas"]) + len(item["removidas"]))
        traza.sumar("citas_removidas_s2", len(item["removidas"]))
        traza.sumar("frases_eliminadas_s3", len(item.get("eliminadas", [])))
    return veredicto, generacion


def fuente_de(recuperado: Recuperado | None) -> dict | None:
    """Fuente citada: documento (doc_id), sección, puntaje y fragmento (Código 8)."""
    if recuperado is None:
        return None
    f = recuperado.fragmento
    return {"documento": f.doc_id, "seccion": f.seccion, "puntaje": round(recuperado.puntaje, 4),
            "fragmento": f.texto, "id": f.id, "titulo": f.titulo, "pagina": f.pagina}


def cuerpo_de_error(salida: GuardrailsSalida, traza: Traza, error: ErrorDominio,
                    tipo: str) -> dict:
    """Todo rechazo o error responde con mensaje seguro, traza_id y S4."""
    guardrail = getattr(error, "guardrail", None)
    if guardrail:
        traza.rechazar(guardrail, type(error).__name__)
    traza.anotar(estado="rechazo" if guardrail else "error", error=type(error).__name__)
    return salida.aplicar_aviso({"detalle": error.mensaje, "traza_id": traza.traza_id,
                                 "guardrails": traza.guardrails}, con_modelo=False, tipo=tipo)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

class OrquestadorAuditoria:
    def __init__(self, *, entrada: GuardrailsEntrada, salida: GuardrailsSalida,
                 cache: CacheExacta, analizador: Analizador, enrutador: Enrutador,
                 gateway: Gateway, agente: CicloAgente, indice: Indice,
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

    def _responder(self, respuesta: dict, con_modelo: bool) -> dict:
        """Único punto de salida: todo camino de respuesta pasa por S4."""
        return self.salida.aplicar_aviso(respuesta, con_modelo=con_modelo, tipo="informe")

    # -- auditar(malla, perfil, notas) → Informe ---------------------------
    def auditar(self, malla: ArchivoSubido, perfil: str, notas: str = "") -> dict:
        traza = Traza("auditoria", perfil, self.trazas, prompts.VERSION_PROMPT,   # paso 2
                      self.indice.version_corpus)
        inicio = time.perf_counter()
        ruta_archivo = None
        try:
            self.analizador.catalogo.obtener(perfil)
            with traza.etapa("archivo_temporal"):
                ruta_archivo = self.temporales.guardar(malla.contenido, malla.extension)
            return self._auditar(traza, malla, ruta_archivo, perfil, notas, inicio)
        except ErrorDominio as error:
            error.cuerpo = cuerpo_de_error(self.salida, traza, error, "informe")
            raise
        finally:
            if ruta_archivo is not None:
                self.temporales.borrar(ruta_archivo)   # la malla no se conserva
            traza.cerrar()

    def _auditar(self, traza: Traza, malla: ArchivoSubido, ruta_archivo, perfil: str,
                 notas: str, inicio: float) -> dict:
        # 3. Guardrails de entrada: E1 al archivo, E2 y E3 a las notas
        with traza.etapa("guardrails_entrada"):
            self.entrada.verificar_archivo(malla, ruta_archivo)
            notas_ok = self.entrada.verificar_texto(notas, "notas")
        for g in notas_ok.activaciones:
            traza.registrar_guardrail(g)
        archivo_sha = sha256(malla.contenido)
        versiones = self.versiones()
        traza.anotar(archivo_sha=archivo_sha, version_corpus=versiones["corpus"])

        # 4. Caché exacta de informes
        with traza.etapa("cache"):
            clave = self.cache.clave_informe(archivo_sha, perfil, notas_ok.texto, versiones)
            guardado = self.cache.obtener_informe(clave)
        if guardado is not None:
            return self._desde_cache(traza, guardado, archivo_sha, inicio)

        # 5. Análisis determinista
        with traza.etapa("contexto_malla"):
            resultado = self.analizador.analizar_malla(ruta_archivo, perfil)
        # 6. Enrutador
        with traza.etapa("enrutador"):
            ruta = self.enrutador.clasificar(resultado.hallazgos)
        traza.anotar(ruta=ruta.ruta, hallazgos=ruta.graves + ruta.menores)

        # 7–9. Explicaciones (solo si la ruta usa modelo)
        validado, aciertos = True, 0
        if ruta.alias is not None:
            validado, aciertos = self._explicar(traza, resultado, ruta, perfil, notas_ok.texto,
                                                versiones)
        if aciertos:
            traza.anotar(cache="hallazgos")

        # 10. Plantilla, S4, caché, persistencia
        with traza.etapa("ensamblado"):
            informe = self._ensamblar(resultado, perfil, ruta, traza, malla, versiones, inicio,
                                      aciertos)
        with traza.etapa("guardrails_salida"):
            respuesta = self._responder(informe, con_modelo=ruta.ruta != SIN_MODELO)
        with traza.etapa("cache"):
            para_cache = {k: v for k, v in respuesta.items()
                          if k not in ("auditoria_id", "traza_id", "tiempo_ms")}
            self.cache.guardar_informe(clave, para_cache, versiones["corpus"], validada=validado)
        with traza.etapa("persistencia"):
            self.informes.guardar(respuesta, archivo_sha)
        return respuesta

    def _desde_cache(self, traza: Traza, guardado: dict, archivo_sha: str, inicio: float) -> dict:
        informe = dict(guardado)
        informe.update(auditoria_id=uuid.uuid4().hex, traza_id=traza.traza_id, cache="exacta",
                       iteraciones_agente=0, guardrails=traza.guardrails,
                       tiempo_ms=round((time.perf_counter() - inicio) * 1000, 2))
        traza.anotar(cache="exacta", ruta=informe.get("ruta"), modelo=informe.get("modelo"),
                     hallazgos=sum(h["gravedad"] != "informativo" for h in informe["hallazgos"]))
        with traza.etapa("guardrails_salida"):
            respuesta = self._responder(informe, con_modelo=informe.get("ruta") != SIN_MODELO)
        with traza.etapa("persistencia"):
            self.informes.guardar(respuesta, archivo_sha)
        return respuesta

    # -- pasos 7 a 9 ----------------------------------------------------------
    def _explicar(self, traza: Traza, resultado: ResultadoAnalisis, ruta: Ruta, perfil: str,
                  notas: str, versiones: dict) -> tuple[bool, int]:
        self.indice.verificar_compatibilidad()
        explicables = [h for h in resultado.hallazgos if h.explicable]
        modelo_ruta = self.gateway.nombre_modelo(ruta.alias)
        claves, pendientes, aciertos = {}, [], 0
        with traza.etapa("cache"):                                  # 7. caché de hallazgos
            for h in explicables:
                claves[h.id] = self.cache.clave_hallazgo(
                    h.verificacion, perfil, h.gravedad, versiones["corpus"],
                    versiones["prompt"], modelo_ruta)
                guardado = self.cache.obtener_hallazgo(claves[h.id])
                if guardado is None:
                    pendientes.append(h)
                    continue
                h.explicacion = guardado["explicacion"]
                h.correccion = list(guardado.get("correccion") or [])
                h.fuente = guardado.get("fuente")
                aciertos += 1
        traza.sumar("hallazgos_cache", aciertos)

        presupuesto = Presupuesto(self.max_reformulaciones_informe)
        fragmentos: dict[str, list[Recuperado]] = {}
        with traza.etapa("contexto_rag"):                           # 7. recuperar normas
            for h in pendientes:
                fragmentos[h.id], _ = self.agente.recuperar_con_agente(
                    h.consulta, perfil, presupuesto, traza)
        validos: dict[str, bool] = {}
        for h in pendientes:
            if not fragmentos[h.id]:
                h.explicacion, h.correccion, h.fuente = SIN_NORMA, [], None
                validos[h.id] = True
        con_norma = [h for h in pendientes if fragmentos[h.id]]
        nombre_perfil = self.analizador.catalogo.obtener(perfil).nombre
        tamano = prompts.tamano_lote(self.agente.k, self.indice.tam, self.num_ctx,
                                     maximo=self.lote)
        for lote in prompts.lotes(con_norma, tamano):                # 8 y 9: una llamada por lote
            validos.update(self._explicar_lote(traza, lote, fragmentos, ruta, nombre_perfil, notas))
        for h in con_norma:
            if validos.get(h.id):
                self.cache.guardar_hallazgo(claves[h.id], h.__dict__, versiones["corpus"],
                                            validada=True)
        return all(validos.values()), aciertos

    def _explicar_lote(self, traza: Traza, lote: list[Hallazgo],
                       fragmentos: dict[str, list[Recuperado]], ruta: Ruta,
                       nombre_perfil: str, notas: str) -> dict[str, bool]:
        mensajes, entregados = prompts.armar_prompt(lote, fragmentos, nombre_perfil, notas,
                                                    self.num_ctx)
        permitidos = {h.id: {r.fragmento.id for r in fragmentos[h.id]} & entregados for h in lote}
        por_id = {r.fragmento.id: r for h in lote for r in fragmentos[h.id]}
        textos = {i: r.fragmento.texto for i, r in por_id.items()}
        veredicto, generacion = generar_verificado(self.gateway, self.salida, traza, ruta, mensajes,
                                                   RespuestaExplicaciones, permitidos, textos)
        traza.datos["modelo_explicacion"] = generacion.modelo
        validos = {}
        for h in lote:
            item = veredicto.detalles.get(h.id) if veredicto.motivo != "formato" else None
            if item is None:                                         # S1 falló dos veces
                h.explicacion, h.correccion, h.fuente = MENSAJE_SEGURO_FORMATO, [], None
                validos[h.id] = False
            elif item["sin_norma"]:
                h.explicacion, h.correccion, h.fuente = SIN_NORMA, [], None
                validos[h.id] = True
            elif not item["citas"]:                                  # S2 quitó todas las citas
                h.explicacion = f"{item['texto'] or SIN_NORMA} ({SIN_NORMA_VERIFICADA})"
                h.correccion, h.fuente = item["correccion"], None
                validos[h.id] = False
            else:
                h.explicacion, h.correccion = item["texto"], item["correccion"]
                h.fuente = fuente_de(por_id.get(item["citas"][0]))
                validos[h.id] = veredicto.aprobado and not item["removidas"]
        return validos

    # -- paso 10: plantilla ---------------------------------------------------
    @staticmethod
    def _resumen(nombre_perfil: str, resultado: ResultadoAnalisis) -> str:
        """«Animación: 2 hallazgos (1 grave, 1 menor)» (Código 8)."""
        c = resultado.contar()
        total = c["grave"] + c["menor"]
        if total == 0:
            texto = f"{nombre_perfil}: sin hallazgos graves ni menores"
        else:
            partes = []
            if c["grave"]:
                partes.append(f"{c['grave']} {'grave' if c['grave'] == 1 else 'graves'}")
            if c["menor"]:
                partes.append(f"{c['menor']} {'menor' if c['menor'] == 1 else 'menores'}")
            texto = (f"{nombre_perfil}: {total} {'hallazgo' if total == 1 else 'hallazgos'} "
                     f"({', '.join(partes)})")
        if c["informativo"]:
            texto += f"; {c['informativo']} informativo{'s' if c['informativo'] != 1 else ''}"
        if resultado.no_medibles:
            texto += (f". {', '.join(resultado.no_medibles)} no se pueden medir en "
                      f"{resultado.metricas['formato'].upper()}: audita el archivo en OBJ")
        return texto

    def _ensamblar(self, resultado: ResultadoAnalisis, perfil: str, ruta: Ruta, traza: Traza,
                   malla: ArchivoSubido, versiones: dict, inicio: float, aciertos: int) -> dict:
        """Las mediciones las pone siempre la plantilla, nunca el modelo."""
        datos_perfil = self.analizador.catalogo.obtener(perfil)
        hallazgos = []
        for h in resultado.hallazgos:
            informativo = not h.explicable                 # se listan sin explicación ni cita
            hallazgos.append({
                "id": h.id, "verificacion": h.verificacion, "tipo": h.tipo,
                "gravedad": h.gravedad, "medido": h.medido, "limite": h.limite,
                "explicacion": None if informativo else h.explicacion,
                "correccion": [] if informativo else list(h.correccion),
                "fuente": None if informativo else h.fuente,
                "descripcion": h.descripcion, "valor": h.valor, "norma_esperada": h.norma,
            })
        modelo = "plantilla"
        if ruta.ruta != SIN_MODELO:   # el modelo que explicó, no el que reformuló
            modelo = traza.datos.get("modelo_explicacion") or self.gateway.nombre_modelo(ruta.alias)
        traza.anotar(modelo=modelo)
        return {
            "auditoria_id": uuid.uuid4().hex,
            "resumen": self._resumen(datos_perfil.nombre, resultado),
            "semaforo": resultado.semaforo,
            "metricas_malla": resultado.metricas,
            "hallazgos": hallazgos,
            "modelo": modelo,
            "ruta": ruta.ruta,
            "cache": "hallazgos" if aciertos else "ninguna",
            "guardrails": traza.guardrails,
            "iteraciones_agente": traza.datos["iteraciones_agente"],
            "tiempo_ms": round((time.perf_counter() - inicio) * 1000, 2),
            "traza_id": traza.traza_id,
            "uso_respaldo": bool(traza.datos.get("uso_respaldo")),
            "archivo": malla.nombre,
            "perfil": perfil,
            "perfil_nombre": datos_perfil.nombre,
            "versiones": versiones,
        }


def informe_a_markdown(informe: dict) -> str:
    """Exportación del informe a Markdown (``GET /auditorias/{id}/markdown``, RF7)."""
    m = informe["metricas_malla"]
    lineas = [f"# Informe de auditoría MeshAudit — {informe.get('archivo', '')}", "",
              f"- **Perfil:** {informe.get('perfil_nombre', informe.get('perfil'))}",
              f"- **Semáforo:** {informe['semaforo']}",
              f"- **Ruta:** {informe['ruta']} · **Modelo:** {informe['modelo']} · "
              f"**Caché:** {informe['cache']}",
              f"- **Dimensión máxima:** {m.get('dimension_max')} {m.get('unidad')} · "
              f"**Caras:** {m.get('caras')} · **Triángulos:** {m.get('triangulos')}",
              "", informe["resumen"], "", "## Hallazgos", ""]
    if not informe["hallazgos"]:
        lineas.append("Sin hallazgos.")
    for h in informe["hallazgos"]:
        lineas += [f"### {h['id']} · {h['verificacion']} · {h.get('descripcion', h['tipo'])} "
                   f"({h['gravedad']})", "",
                   f"- Medido: `{h['medido']}` · Límite: `{h['limite']}`"]
        if h.get("explicacion"):
            lineas += ["", h["explicacion"]]
        if h.get("correccion"):
            lineas += ["", "**Pasos de corrección:**"]
            lineas += [f"{i}. {paso}" for i, paso in enumerate(h["correccion"], start=1)]
        if h.get("fuente"):
            f = h["fuente"]
            lineas += ["", f"> **Fuente:** {f['documento']} — {f['seccion']} "
                           f"(`{f.get('id', '')}`, puntaje {f['puntaje']})", ">",
                       "> " + f["fragmento"].replace("\n", "\n> ")]
        lineas.append("")
    lineas += ["---", f"_{informe.get('aviso', '')}_", "", f"Traza: `{informe['traza_id']}`"]
    return "\n".join(lineas)
