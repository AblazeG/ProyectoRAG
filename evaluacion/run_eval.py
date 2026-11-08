"""Evaluación de MeshAudit (sección 9 del informe).

Llama a la API como cualquier cliente (TestClient en proceso, que ejecuta el mismo
código que uvicorn, o un servicio externo con ``--url``), lee las trazas y guarda
los resultados en CSV, uno por tabla del informe:

    tabla16_producto.csv (+ tabla16_casos.csv)   calidad del producto, con y sin RAG
    tabla17_fragmentos.csv, tabla18_barrido.csv   recuperación (experimento_fragmentos)
    tabla19_guardrails.csv (+ _casos)            guardrails de entrada
    tabla20_agente.csv (+ _casos)                ciclo de agente
    tabla21_enrutador.csv (+ _casos)             enrutador sobre 40 casos
    tabla22_cache.csv                            caché semántica y exacta (experimento_cache)
    tabla23_latencias.csv                        latencia por capa, caché desactivada
    fallas.csv, privacidad.csv, retroalimentacion.csv, juez_autor.csv

Uso (Anexo A):
    python evaluacion/run_eval.py --salida evaluacion/resultados/                     # con Ollama
    python evaluacion/run_eval.py --proveedor falso --salida /tmp/res                  # sin Ollama
    python evaluacion/run_eval.py --url http://127.0.0.1:8000 --trazas data/trazas.jsonl --tablas 16,19
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion.comun import (OLLAMA, RAIZ, RESULTADOS, SESIONES, Sesion, cargar,  # noqa: E402
                              corpus_por_defecto, embeddings_para, escribir_csv, estadisticos,
                              mallas)
from evaluacion.juez import crear_juez  # noqa: E402

SIN_NORMA = "Sin norma aplicable en el corpus"
SISTEMA_SIN_RAG = (  # comparación «sin RAG»: mismo modelo y hallazgos, sin fragmentos
    "Eres un supervisor técnico de modelos 3D. Explicas hallazgos de una auditoría. "
    "No escribas mediciones de la malla. Responde en español y en el esquema JSON indicado.")


def _pct(a, b):
    return round(100 * a / b, 1) if b else None


def _normas(respuesta: dict) -> list[dict]:
    return [f for f in respuesta.get("fuentes", []) if not str(f.get("id", "")).startswith("informe:")]


def _referencia(sesion: Sesion, dir_mallas: Path, perfil: str) -> str:
    """Informe sobre el que se hacen las preguntas de un perfil (primer caso del perfil)."""
    caso = next(c for c in cargar("casos_producto.json") if c["perfil"] == perfil)
    return sesion.auditar(dir_mallas / caso["malla"], perfil).json()["auditoria_id"]


# -- Tabla 16: calidad del producto ------------------------------------------------
def _sin_rag(sesion: Sesion, informe: dict, hallazgo: dict, juez):
    """Misma explicación sin fragmentos de contexto, calificada por el juez."""
    from servicio.dominio import RespuestaExplicaciones
    c = sesion.contenedor
    alias = "completo" if informe["ruta"] == "completa" else "rapido"
    mensajes = [{"role": "system", "content": SISTEMA_SIN_RAG},
                {"role": "user", "content": f'<hallazgos><hallazgo id="{hallazgo["id"]}" fragmentos="">'
                                            f'{hallazgo["descripcion"]}</hallazgo></hallazgos>\n'
                                            "Explica el hallazgo y da los pasos de corrección."}]
    try:
        g = c.gateway.generar(alias, mensajes, RespuestaExplicaciones.model_json_schema())
    except Exception:  # noqa: BLE001
        return None
    # Mismos guardrails de salida que la ruta con RAG (S1–S3): sin fragmentos entregados,
    # S2 quita toda cita y S3 elimina las cifras sin respaldo. Así la comparación mide
    # el aporte del contexto y no la ausencia de guardrails.
    veredicto = c.auditor.salida.verificar_generacion(g.texto, RespuestaExplicaciones,
                                              {hallazgo["id"]: set()}, {})
    if veredicto.motivo == "formato":
        return None
    if veredicto.motivo == "cifras":
        veredicto = c.auditor.salida.eliminar_cifras(veredicto)
    item = veredicto.detalles.get(hallazgo["id"])
    if not item or item["sin_norma"] or not item["texto"]:
        return None
    return juez.calificar(f"Explicar el hallazgo {hallazgo['verificacion']}: {hallazgo['descripcion']}",
                          item["texto"] + "\n" + "\n".join(item["correccion"]),
                          [hallazgo["fuente"]["fragmento"]] if hallazgo.get("fuente") else [])


def tabla16(sesion: Sesion, dir_mallas: Path, juez, salida: Path = RESULTADOS
            ) -> tuple[list[dict], list[dict]]:
    casos_det, vp_t, det_t, esp_t = [], 0, 0, 0
    aciertos5, total5, con, sin = 0, 0, [], []
    citas_gen, citas_s2, frases_s3, desde_cache = 0, 0, 0, 0
    recuperador = sesion.contenedor.extras.get("recuperador") if sesion.contenedor else None
    for caso in cargar("casos_producto.json"):
        r = sesion.auditar(dir_mallas / caso["malla"], caso["perfil"])
        if r.status_code != 200:
            casos_det.append({"caso": caso["id"], "codigo": r.status_code})
            continue
        inf = r.json()
        traza = sesion.trazas().get(inf["traza_id"], {})
        citas_gen += traza.get("citas_generadas", 0)
        citas_s2 += traza.get("citas_removidas_s2", 0)
        frases_s3 += traza.get("frases_eliminadas_s3", 0)
        desde_cache += traza.get("hallazgos_cache", 0)
        obtenidas = {h["verificacion"]: h["gravedad"] for h in inf["hallazgos"] if h["gravedad"] != "informativo"}
        esperadas = caso["verificaciones_esperadas"]
        vp = sum(1 for v, g in esperadas.items() if obtenidas.get(v) == g)
        vp_t, det_t, esp_t = vp_t + vp, det_t + len(obtenidas), esp_t + len(esperadas)
        for v, norma in caso["fuentes_esperadas"].items():
            h = next((x for x in inf["hallazgos"] if x["verificacion"] == v), None)
            if h is None:
                continue
            total5 += 1
            if recuperador is not None:   # acierto@5 de la sección esperada (C5 directo)
                from servicio.contexto.herramientas import VERIFICACIONES
                rec = recuperador.recuperar(VERIFICACIONES[v][2], k=5, perfil=caso["perfil"])
                aciertos5 += any(x.fragmento.doc_id == norma["documento"] and x.fragmento.seccion == norma["seccion"]
                                 for x in rec.fragmentos)
            elif h.get("fuente"):
                aciertos5 += (h["fuente"]["documento"] == norma["documento"]
                              and h["fuente"]["seccion"] == norma["seccion"])
            if h.get("explicacion") and h["explicacion"] != SIN_NORMA and h.get("fuente"):
                nota = juez.calificar(f"Explicar el hallazgo {v}: {h['descripcion']}",
                                      h["explicacion"] + "\n" + "\n".join(h["correccion"]),
                                      [h["fuente"]["fragmento"]])
                if nota:
                    con.append(nota)
                if nota and sesion.contenedor is not None:
                    nota_sin = _sin_rag(sesion, inf, h, juez)
                    if nota_sin:
                        sin.append(nota_sin)
        casos_det.append({
            "caso": caso["id"], "perfil": caso["perfil"], "base": caso["base"], "variante": caso["variante"],
            "semaforo_esperado": caso["semaforo_esperado"], "semaforo": inf["semaforo"],
            "esperadas": len(esperadas), "detectadas": len(obtenidas), "verdaderos_positivos": vp,
            "no_detectadas": sorted(set(esperadas) - set(obtenidas)),
            "falsos": sorted(set(obtenidas) - set(esperadas)),
            "sin_norma": sum(h.get("explicacion") == SIN_NORMA for h in inf["hallazgos"]),
            "ruta": inf["ruta"], "modelo": inf["modelo"], "cache": inf["cache"],
            "tiempo_ms": inf["tiempo_ms"], "traza_id": inf["traza_id"]})

    def media(notas, campo):
        return round(statistics.mean(n[campo] for n in notas), 2) if notas else None
    juez_autor = _juez_autor(salida)
    resumen = [
        {"metrica": "Recall de hallazgos", "con_rag": round(vp_t / esp_t, 3) if esp_t else None, "sin_rag": ""},
        {"metrica": "Precisión de hallazgos", "con_rag": round(vp_t / det_t, 3) if det_t else None, "sin_rag": ""},
        {"metrica": "Acierto@5 de la sección esperada", "con_rag": round(aciertos5 / total5, 3) if total5 else None, "sin_rag": "–"},
        {"metrica": "Fidelidad al contexto (0–5)", "con_rag": media(con, "fidelidad"), "sin_rag": media(sin, "fidelidad")},
        {"metrica": "Relevancia de la corrección (0–5)", "con_rag": media(con, "relevancia"), "sin_rag": media(sin, "relevancia")},
        {"metrica": "Citas inventadas detectadas por S2 (% de las citas)", "con_rag": _pct(citas_s2, citas_gen), "sin_rag": "–"},
        {"metrica": "Cifras sin respaldo eliminadas por S3", "con_rag": frases_s3, "sin_rag": ""},
        {"metrica": "Diferencia media juez–autor (15 casos)", "con_rag": juez_autor.get("diferencia_media"),
         "sin_rag": "–"},
        {"metrica": "Acuerdo juez–autor, diferencia ≤ 1 punto (%)",
         "con_rag": juez_autor.get("acuerdo_1_punto_pct"), "sin_rag": "–"},
        {"metrica": "Hallazgos servidos desde la caché de hallazgos", "con_rag": desde_cache, "sin_rag": "–"},
    ]
    return resumen, casos_det


def _juez_autor(salida: Path = RESULTADOS) -> dict:
    """Validación del juez: diferencia media y % de casos con diferencia ≤ 1 (15 casos).

    Lee ``muestra_revision_manual.csv`` (de experimento_llm) en el directorio de salida."""
    ruta = Path(salida) / "muestra_revision_manual.csv"
    if not ruta.exists():
        return {}
    diferencias = []
    for fila in csv.DictReader(open(ruta, encoding="utf-8")):
        for campo in ("fidelidad", "relevancia"):
            autor = fila.get(f"nota_autor_{campo}")
            if autor and fila.get(campo):
                diferencias.append(abs(float(autor) - float(fila[campo])))
    if not diferencias:
        return {}
    return {"diferencia_media": round(statistics.mean(diferencias), 2),
            "acuerdo_1_punto_pct": _pct(sum(d <= 1 for d in diferencias), len(diferencias))}


# -- Tabla 19: guardrails --------------------------------------------------------

def tabla19(sesion: Sesion, dir_mallas: Path) -> tuple[list[dict], list[dict]]:
    referencia = _referencia(sesion, dir_mallas, "animacion")
    malla_normal = dir_mallas / next(c for c in cargar("casos_producto.json")
                                     if c["perfil"] == "animacion")["malla"]
    detalle = []
    for caso in cargar("casos_guardrails.json"):
        e, esperado = caso["entrada"], caso["esperado"]
        if caso["tipo"] == "notas":
            r = sesion.auditar(malla_normal, "animacion", e["notas"])
        elif caso["tipo"] == "documento":
            r = sesion.http.post("/documentos", files={"archivo": (e["archivo"], e["contenido"].encode())})
        else:
            r = sesion.preguntar(referencia, e["pregunta"])
        cuerpo = r.json() if "json" in r.headers.get("content-type", "") else {}
        g = cuerpo.get("guardrails") or {}
        activaciones = g.get("activaciones", []) if isinstance(g, dict) else g
        correcto = r.status_code == esperado["codigo"]
        if "guardrail" in esperado:
            # Debe actuar el guardrail esperado, no basta cualquier 422 (p. ej. un E1).
            correcto = correcto and esperado["guardrail"] in activaciones
        if "no_contiene" in esperado:
            correcto = correcto and esperado["no_contiene"] not in r.text
        falso_positivo = esperado.get("sin_rechazo") and (r.status_code != 200 or "E4" in activaciones)
        detalle.append({"caso": caso["id"], "categoria": caso["categoria"], "tipo": caso["tipo"],
                        "codigo_esperado": esperado["codigo"], "codigo": r.status_code,
                        "activaciones": activaciones, "aviso": bool(cuerpo.get("aviso")),
                        "correcto": bool(correcto) if not esperado.get("sin_rechazo") else None,
                        "falso_positivo": bool(falso_positivo) if esperado.get("sin_rechazo") else None})
    nombres = {"inyeccion": "Inyección (E2)", "fuera_de_dominio": "Fuera de dominio (E4)",
               "datos_personales": "Datos personales (E3)", "documento": "Documentos (E5)",
               "normal": "Normales"}
    resumen, correctos_t, problematicas, fp_t, normales = [], 0, 0, 0, 0
    for categoria, nombre in nombres.items():
        filas = [d for d in detalle if d["categoria"] == categoria]
        if categoria == "normal":
            fp = sum(bool(d["falso_positivo"]) for d in filas)
            fp_t, normales = fp_t + fp, normales + len(filas)
            resumen.append({"entrada": nombre, "casos": len(filas), "correctos": "–", "falsos_positivos": fp})
        else:
            ok = sum(bool(d["correcto"]) for d in filas)
            correctos_t, problematicas = correctos_t + ok, problematicas + len(filas)
            resumen.append({"entrada": nombre, "casos": len(filas), "correctos": ok, "falsos_positivos": "–"})
    resumen.append({"entrada": "Total", "casos": len(detalle),
                    "correctos": f"{_pct(correctos_t, problematicas)} %",
                    "falsos_positivos": f"{_pct(fp_t, normales)} %"})
    return resumen, detalle


# -- Tabla 20: ciclo de agente -------------------------------------------------------
def tabla20(sesion: Sesion, dir_mallas: Path) -> tuple[list[dict], list[dict]]:
    casos = [dict(c) for c in cargar("casos_agente.json")]
    recuperador = sesion.contenedor.extras.get("recuperador") if sesion.contenedor else None
    if recuperador is not None:   # + consultas del conjunto de recuperación que no superan el umbral
        from servicio.orquestacion.agente import es_suficiente
        for c in cargar("casos_recuperacion.json"):
            if c["relevante"] and not es_suficiente(recuperador.recuperar(c["consulta"], k=5, perfil=c["perfil"])):
                casos.append({"id": c["id"], "consulta": c["consulta"], "documento": c["documento"],
                              "seccion": c["seccion"], "perfil": c["perfil"]})
    umbral = (sesion.contenedor.config.get("rag", {}).get("umbral", 0.55)
              if sesion.contenedor else 0.55)

    def suficiente(r: dict) -> bool:   # misma condición que es_suficiente (top-1 y ≥ 2 fragmentos)
        from servicio.orquestacion.agente import MIN_SOBRE_UMBRAL
        return r.get("top1", 0) >= umbral and r.get("fragmentos", 0) >= MIN_SOBRE_UMBRAL

    referencias, detalle = {}, []
    for c in casos:
        if c["perfil"] not in referencias:
            referencias[c["perfil"]] = _referencia(sesion, dir_mallas, c["perfil"])
        r = sesion.preguntar(referencias[c["perfil"]], c["consulta"]).json()
        traza = sesion.trazas().get(r.get("traza_id"), {})
        rec = traza.get("recuperaciones") or [{}]
        inicial_ok = suficiente(rec[0])
        final_ok = suficiente(rec[-1])     # la última recuperación del ciclo (Código 4)
        normas = _normas(r)
        agente_ms = sum(l["duracion_ms"] for l in traza.get("llamadas", []) if l.get("ruta") == "agente")
        detalle.append({"caso": c["id"], "inicial_suficiente": inicial_ok,
                        "top1_inicial": rec[0].get("top1"), "top1_final": rec[-1].get("top1"),
                        "reformulaciones": r.get("iteraciones_agente", 0),
                        "supera_tras_reformular": (not inicial_ok) and final_ok and len(rec) > 1,
                        "sin_norma": not normas,
                        "fuente_correcta": any(f.get("documento") == c["documento"] and f.get("seccion") == c["seccion"]
                                               for f in normas),
                        "latencia_adicional_s": round(agente_ms / 1000, 3)})
    pobres = [d for d in detalle if not d["inicial_suficiente"]]
    resumen = [
        {"metrica": "Superan el umbral tras reformular",
         "valor": f"{sum(d['supera_tras_reformular'] for d in pobres)} de {len(pobres)}"},
        {"metrica": "Reformulaciones promedio",
         "valor": round(statistics.mean(d["reformulaciones"] for d in pobres), 2) if pobres else None},
        {"metrica": "Terminan en «sin norma»", "valor": sum(d["sin_norma"] for d in pobres)},
        {"metrica": "Latencia adicional media (s)",
         "valor": round(statistics.mean(d["latencia_adicional_s"] for d in pobres), 3) if pobres else None},
    ]
    return resumen, detalle


# -- Tabla 21: enrutador ------------------------------------------------------------
def tabla21(sesion: Sesion, dir_mallas: Path, juez, args) -> tuple[list[dict], list[dict]]:
    solo_rapido = None
    if args.juez and sesion.contenedor is not None:   # etiqueta por calidad: ¿basta gemma4:e2b?
        solo_rapido = Sesion(proveedor=args.proveedor, cache=False, corpus=args.corpus)
        chats = solo_rapido.contenedor.extras["chats"]
        chats["completo"] = chats["rapido"]
    detalle = []
    for c in cargar("casos_enrutador.json"):
        inicio = time.perf_counter()
        inf = sesion.auditar(dir_mallas / c["malla"], c["perfil"]).json()
        latencia = time.perf_counter() - inicio
        esperada, nota = c.get("ruta_esperada_calidad"), None
        if esperada is None and c["ruta_esperada_regla"] == "sin_modelo":
            esperada = "sin_modelo"
        if esperada is None and solo_rapido is not None:
            r = solo_rapido.auditar(dir_mallas / c["malla"], c["perfil"]).json()
            # Solo se califican explicaciones generadas con norma: «sin norma» y los
            # hallazgos sin fuente no dicen nada de la calidad de gemma4:e2b.
            notas = [juez.calificar(h["descripcion"], h["explicacion"],
                                    [h["fuente"]["fragmento"]])
                     for h in r.get("hallazgos", []) if h["gravedad"] != "informativo"
                     and h.get("fuente") and h.get("explicacion") and h["explicacion"] != SIN_NORMA]
            notas = [min(n["fidelidad"], n["relevancia"]) for n in notas if n]
            if notas:
                nota = round(statistics.mean(notas), 2)
                esperada = "rapida" if nota >= 4 else "completa"
            else:
                esperada = "sin_etiqueta"   # con juez pero nada que calificar: no se inventa
        esperada = esperada or c["ruta_esperada_regla"]   # sin juez: se usa la regla (ver DESVIACIONES)
        detalle.append({"caso": c["id"], "origen": c["origen"], "perfil": c["perfil"],
                        "ruta_esperada": esperada, "nota_gemma": nota,
                        "etiquetada_por": ("calidad" if nota is not None or esperada == "sin_modelo"
                                           else "ninguna" if esperada == "sin_etiqueta" else "regla"),
                        "ruta": inf["ruta"], "adecuada": inf["ruta"] == esperada,
                        "completa_sin_necesidad": inf["ruta"] == "completa" and esperada != "completa",
                        "latencia_s": round(latencia, 3)})
    resumen = []
    for ruta, nombre in (("sin_modelo", "Sin modelo"), ("rapida", "Rápida"), ("completa", "Completa")):
        filas = [d for d in detalle if d["ruta_esperada"] == ruta]
        lat = estadisticos([d["latencia_s"] for d in filas])
        resumen.append({"ruta_esperada": nombre, "casos": len(filas),
                        "adecuados": sum(d["adecuada"] for d in filas),
                        "latencia_p50_s": lat["mediana"], "latencia_p95_s": lat["p95"]})
    sin_etiqueta = [d for d in detalle if d["ruta_esperada"] == "sin_etiqueta"]
    if sin_etiqueta:
        resumen.append({"ruta_esperada": "Sin etiqueta (excluidos)", "casos": len(sin_etiqueta),
                        "adecuados": "–"})
    resumen.append({"ruta_esperada": "A la completa sin necesidad", "casos": "",
                    "adecuados": sum(d["completa_sin_necesidad"] for d in detalle
                                     if d["ruta_esperada"] != "sin_etiqueta")})
    return resumen, detalle


# -- Tabla 23: latencia por capa ---------------------------------------------------
ETAPAS_23 = [("guardrails_entrada", "Guardrails de entrada"), ("cache", "Caché (consultas)"),
             ("contexto_malla", "Análisis de malla"), ("contexto_rag", "Recuperación (incluye agente)"),
             ("gateway:rapida", "Gateway, ruta rápida"), ("gateway:completa", "Gateway, ruta completa"),
             ("guardrails_salida", "Guardrails de salida")]


def tabla23(sesion: Sesion, dir_mallas: Path, corridas: int) -> list[dict]:
    valores: dict[str, list[float]] = {k: [] for k, _ in ETAPAS_23}
    totales = []
    for caso in cargar("casos_producto.json"):
        for _ in range(corridas):
            r = sesion.auditar(dir_mallas / caso["malla"], caso["perfil"]).json()
            t = sesion.trazas().get(r.get("traza_id"), {})
            for etapa, ms in (t.get("tiempos_ms") or {}).items():
                clave = f"gateway:{t.get('ruta')}" if etapa == "gateway" else etapa
                if clave in valores:
                    valores[clave].append(ms)
            totales.append(t.get("tiempo_total_ms") or r.get("tiempo_ms"))
    filas = [{"etapa": nombre, **estadisticos(valores[clave])} for clave, nombre in ETAPAS_23]
    filas.append({"etapa": "Total por auditoría", **estadisticos(totales)})
    return filas


# -- Disponibilidad: fallas inyectadas -----------------------------------------------
def fallas(args, dir_mallas: Path) -> list[dict]:
    producto = {c["id"]: c for c in cargar("casos_producto.json")}
    filas = []
    for c in cargar("casos_fallas.json"):
        alias, tipo = c["falla"]["alias"], c["falla"]["tipo"]
        variables, falla = {}, None
        if tipo == "etiqueta_inexistente":
            if args.proveedor == "ollama":   # alias configurado hacia una etiqueta inexistente → 404
                variables[f"MESHAUDIT_MODELO_{alias.upper()}"] = "meshaudit-etiqueta-inexistente:0"
            else:
                falla = f"{alias}:404"
        else:                                # doble del adaptador que agota el tiempo o pierde la conexión
            falla = f"{alias}:{tipo}"
        sesion = Sesion(proveedor=args.proveedor, cache=False, corpus=args.corpus, falla=falla,
                        variables=variables)
        p = producto[c["caso_producto"]]
        r = sesion.auditar(dir_mallas / p["malla"], p["perfil"])
        cuerpo = r.json()
        traza = sesion.trazas().get(cuerpo.get("traza_id"), {})
        filas.append({"caso": c["id"], "alias": alias, "falla": tipo, "codigo": r.status_code,
                      "error_500": r.status_code >= 500 and r.status_code != 503,
                      "terminada_con_respaldo": r.status_code == 200 and bool(cuerpo.get("uso_respaldo")),
                      "llamadas_fallidas": sum(not x["ok"] for x in traza.get("llamadas", [])),
                      "ruta": cuerpo.get("ruta"), "modelo": cuerpo.get("modelo")})
    filas.append({"caso": "RESUMEN", "error_500": sum(f["error_500"] for f in filas),
                  "terminada_con_respaldo": f"{sum(f['terminada_con_respaldo'] for f in filas)} de {len(filas)}"})
    return filas


# -- Privacidad: 0 datos personales en trazas, caché y retroalimentación --------------
def privacidad(sesiones: list[Sesion]) -> list[dict]:
    """Se mide al final de la corrida sobre los almacenes de todas las sesiones."""
    from servicio.guardrails.patrones import DATOS_PERSONALES
    literales = ["ana.perez@uni.mx", "55 1234 5678", "GOPA850101HDFRRN09"]
    textos: dict[str, str] = {}

    def sumar(nombre: str, texto: str) -> None:
        textos[nombre] = textos.get(nombre, "") + "\n" + texto

    for sesion in sesiones:
        if sesion.ruta_trazas and Path(sesion.ruta_trazas).exists():
            sumar("trazas.jsonl", Path(sesion.ruta_trazas).read_text(encoding="utf-8"))
        base = getattr(sesion, "ruta_sqlite", None)
        if base and Path(base).exists():
            con = sqlite3.connect(base)
            for tabla, columnas in (("cache", "clave, valor"), ("cache_semantica", "valor"),
                                    ("retroalimentacion", "comentario"), ("informes", "informe")):
                filas = con.execute(f"SELECT {columnas} FROM {tabla}").fetchall()
                sumar(tabla, "\n".join(" ".join(str(x) for x in f) for f in filas))
            con.close()
    resultado = []
    for almacen, texto in textos.items():
        n = sum(texto.count(l) for l in literales)
        n += sum(len(p.findall(texto)) for etiqueta, p in DATOS_PERSONALES if etiqueta == "[CORREO]")
        resultado.append({"almacen": almacen, "datos_personales": n})
    return resultado


def retroalimentacion(datos: Path) -> list[dict]:
    """Calificaciones registradas durante las pruebas; las «no útil» se revisan una a una."""
    base = datos / "meshaudit.sqlite"
    if not base.exists():
        return []
    con = sqlite3.connect(base)
    filas = con.execute("SELECT traza_id, hallazgo_id, util, comentario, creado FROM retroalimentacion").fetchall()
    con.close()
    return [{"traza_id": t, "hallazgo_id": h, "util": bool(u), "comentario": c, "creado": f}
            for t, h, u, c, f in filas]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="servicio ya levantado (si no, la API corre en proceso)")
    p.add_argument("--trazas", type=Path, help="data/trazas.jsonl del servicio externo")
    p.add_argument("--proveedor", default="ollama", choices=["falso", "ollama"])
    p.add_argument("--corpus", type=Path, default=None)
    p.add_argument("--mallas", type=Path, default=None, help="directorio con <base>_base.obj y <base>_M1.obj…")
    p.add_argument("--mallas-sinteticas", action="store_true",
                   help="genera mallas sintéticas si faltan (sin Blender; no son las del informe)")
    p.add_argument("--juez", action="store_true", help="usa mistral-small3.2:24b como juez")
    p.add_argument("--corridas", type=int, default=5)
    p.add_argument("--datos", type=Path, default=RAIZ / "data", help="data/ con la retroalimentación real")
    p.add_argument("--salida", type=Path, default=RESULTADOS)
    p.add_argument("--tablas", default="16,17,18,19,20,21,22,23,fallas,privacidad,retro")
    args = p.parse_args(argv)
    args.corpus = corpus_por_defecto(args)
    tablas = set(args.tablas.split(","))
    dir_mallas = mallas(args.mallas, args.proveedor, args.mallas_sinteticas)
    juez = crear_juez(args.juez, "mistral-small3.2:24b", OLLAMA)

    def sesion(cache: bool) -> Sesion:
        if args.url:
            return Sesion(url=args.url, trazas=args.trazas)
        s = Sesion(proveedor=args.proveedor, cache=cache, corpus=args.corpus)
        s.contenedor.extras["recuperador"] = s.contenedor.auditor.agente.recuperador
        return s

    con_cache, sin_cache = sesion(cache=True), sesion(cache=False)
    salida = args.salida

    def guardar(nombre, filas):
        print(f"{nombre}: {escribir_csv(salida / nombre, filas)}")

    if "16" in tablas:
        con_cache.vaciar_cache()
        resumen, detalle = tabla16(con_cache, dir_mallas, juez, salida)
        guardar("tabla16_producto.csv", resumen)
        guardar("tabla16_casos.csv", detalle)
    if tablas & {"17", "18"} and not args.url:
        from experimentos.experimento_fragmentos import tabla17 as t17, tabla18 as t18
        emb = embeddings_para(con_cache.contenedor.config["modelos"]["embeddings"], args.proveedor)
        casos = cargar("casos_recuperacion.json")
        if "17" in tablas:
            guardar("tabla17_fragmentos.csv", t17(emb, args.corpus, casos))
        if "18" in tablas:
            guardar("tabla18_barrido.csv", t18(emb, args.corpus, casos))
    if "19" in tablas:
        resumen, detalle = tabla19(con_cache, dir_mallas)
        guardar("tabla19_guardrails.csv", resumen)
        guardar("tabla19_casos.csv", detalle)
    if "20" in tablas:
        resumen, detalle = tabla20(sin_cache, dir_mallas)
        guardar("tabla20_agente.csv", resumen)
        guardar("tabla20_casos.csv", detalle)
    if "21" in tablas:
        resumen, detalle = tabla21(sin_cache, dir_mallas, juez, args)
        guardar("tabla21_enrutador.csv", resumen)
        guardar("tabla21_casos.csv", detalle)
    if "22" in tablas and not args.url:
        from experimentos.experimento_cache import tabla22
        detalle22: list[dict] = []
        guardar("tabla22_cache.csv", tabla22(args.proveedor, args.corpus, dir_mallas, detalle=detalle22))
        guardar("tabla22_casos.csv", detalle22)
    if "23" in tablas:
        guardar("tabla23_latencias.csv", tabla23(sin_cache, dir_mallas, args.corridas))
    if "fallas" in tablas and not args.url:
        guardar("fallas.csv", fallas(args, dir_mallas))
    if "retro" in tablas:
        guardar("retroalimentacion.csv", retroalimentacion(args.datos))
    if "privacidad" in tablas:   # al final: revisa lo que dejaron todas las tablas
        guardar("privacidad.csv", privacidad([con_cache] if args.url else list(SESIONES)))
    juez_autor = _juez_autor(salida)
    if juez_autor:
        guardar("juez_autor.csv", [juez_autor])
    (salida / "ultima_corrida.json").write_text(json.dumps(
        {"proveedor": args.proveedor, "juez": bool(args.juez), "corridas": args.corridas,
         "corpus": str(args.corpus), "mallas": str(dir_mallas)}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
