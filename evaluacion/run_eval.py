"""Evaluación de MeshAudit: llama a la API como cualquier cliente, lee las
trazas y escribe un CSV por cada tabla de resultados del informe (16 a 23).

En el Mac (Ollama real, servicio y API en proceso, mismo código que uvicorn):
    python -m evaluacion.run_eval --proveedor ollama --corpus corpus/ --juez
Contra un servicio ya levantado (sin la tabla de fallas, que reinicia el adaptador):
    python -m evaluacion.run_eval --url http://127.0.0.1:8000 --trazas data/trazas.jsonl
En la nube (modo falso, mallas sintéticas y corpus de prueba):
    python -m evaluacion.run_eval --proveedor falso
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from evaluacion.comun import (CORPUS_PRUEBA, RESULTADOS, Sesion, cargar, escribir_csv,
                              estadisticos, mallas)
from evaluacion.juez import crear_juez

SIN_NORMA = "Sin norma aplicable en el corpus"
PERFIL_DE_DOC = {"guia_impresion3d": "impresion_3d", "guia_tiempo_real": "juego_movil",
                 "gltf_spec": "web_ar"}


def _normas(respuesta: dict) -> list[dict]:
    return [f for f in respuesta.get("fuentes", []) if not f.get("id", "").startswith("informe:")]


# -- Tabla 16: producto ----------------------------------------------------------
def tabla16(sesion: Sesion, dir_mallas, juez) -> list[dict]:
    filas = []
    for caso in cargar("casos_producto.json"):
        r = sesion.auditar(dir_mallas / caso["malla"], caso["perfil"])
        if r.status_code != 200:
            filas.append({"caso": caso["id"], "codigo": r.status_code})
            continue
        inf = r.json()
        obtenidas = {h["verificacion"]: h["gravedad"] for h in inf["hallazgos"] if h["tipo"] != "no_medible"}
        esperadas = caso["verificaciones_esperadas"]
        vp = sum(1 for v, g in esperadas.items() if obtenidas.get(v) == g)
        fuentes_ok, fuentes_total, puntajes = 0, 0, []
        for v, norma in caso["fuentes_esperadas"].items():
            h = next((x for x in inf["hallazgos"] if x["verificacion"] == v), None)
            fuentes_total += 1
            if h and h.get("fuente") and h["fuente"].get("doc_id") == norma["documento"] \
                    and h["fuente"].get("seccion") == norma["seccion"]:
                fuentes_ok += 1
            if h and h.get("explicacion") and h["explicacion"] != SIN_NORMA:
                nota = juez.calificar(f"Explicar el hallazgo {v}: {h['descripcion']}",
                                      h["explicacion"] + "\n" + "\n".join(h["correccion"]),
                                      [h["fuente"]["fragmento"]] if h.get("fuente") else [])
                if nota:
                    puntajes.append(nota)
        filas.append({
            "caso": caso["id"], "perfil": caso["perfil"], "mutacion": caso["mutacion"],
            "semaforo_esperado": caso["semaforo_esperado"], "semaforo": inf["semaforo"],
            "semaforo_ok": inf["semaforo"] == caso["semaforo_esperado"],
            "esperadas": len(esperadas), "detectadas": len(obtenidas), "verdaderos_positivos": vp,
            "precision": round(vp / len(obtenidas), 3) if obtenidas else (1.0 if not esperadas else 0.0),
            "exhaustividad": round(vp / len(esperadas), 3) if esperadas else 1.0,
            "fuente_correcta": f"{fuentes_ok}/{fuentes_total}",
            "sin_norma": sum(1 for h in inf["hallazgos"] if h.get("explicacion") == SIN_NORMA),
            "fidelidad": round(sum(p["fidelidad"] for p in puntajes) / len(puntajes), 2) if puntajes else None,
            "relevancia": round(sum(p["relevancia"] for p in puntajes) / len(puntajes), 2) if puntajes else None,
            "ruta": inf["ruta"], "modelo": inf["modelo"], "tiempo_ms": inf["tiempo_ms"],
            "traza_id": inf["traza_id"]})
    return filas


# -- Tabla 17: recuperación -------------------------------------------------------
def tabla17(sesion: Sesion, dir_mallas) -> list[dict]:
    referencias = {}
    for perfil in ("animacion", "juego_movil", "impresion_3d", "web_ar"):
        referencias[perfil] = sesion.auditar(dir_mallas / "M1.obj", perfil).json()["auditoria_id"]
    trazas_previas = set(sesion.trazas())
    filas = []
    for caso in cargar("casos_recuperacion.json"):
        perfil = PERFIL_DE_DOC.get(caso.get("documento"), "animacion")
        r = sesion.preguntar(referencias[perfil], caso["consulta"])
        cuerpo = r.json()
        normas = _normas(cuerpo) if r.status_code == 200 else []
        rango = next((i + 1 for i, f in enumerate(normas)
                      if f.get("doc_id") == caso.get("documento") and f.get("seccion") == caso.get("seccion")), None)
        traza = sesion.trazas().get(cuerpo.get("traza_id"), {})
        top1 = (traza.get("recuperaciones") or [{}])[-1].get("top1")
        fila = {"caso": caso["id"], "relevante": caso["relevante"], "codigo": r.status_code,
                "top1": top1, "fuentes": len(normas), "iteraciones_agente": cuerpo.get("iteraciones_agente"),
                "guardrails": cuerpo.get("guardrails")}
        if caso["relevante"]:
            fila.update({"acierto_k": rango is not None, "rango": rango,
                         "reciproco": round(1 / rango, 3) if rango else 0.0})
        else:
            fila.update({"rechazo_correcto": not normas})
        filas.append(fila)
    relevantes = [f for f in filas if f["relevante"]]
    negativos = [f for f in filas if not f["relevante"]]
    filas.append({"caso": "RESUMEN", "relevante": None,
                  "acierto_k": round(sum(f["acierto_k"] for f in relevantes) / len(relevantes), 3),
                  "reciproco": round(sum(f["reciproco"] for f in relevantes) / len(relevantes), 3),
                  "rechazo_correcto": round(sum(f["rechazo_correcto"] for f in negativos) / len(negativos), 3)})
    del trazas_previas
    return filas


# -- Tabla 18: guardrails ---------------------------------------------------------
def tabla18(sesion: Sesion, dir_mallas) -> list[dict]:
    referencia = sesion.auditar(dir_mallas / "M1.obj", "animacion").json()["auditoria_id"]
    filas = []
    for caso in cargar("casos_guardrails.json"):
        e, esperado = caso["entrada"], caso["esperado"]
        if caso["tipo"] == "auditoria" and "archivo" in e:
            contenido = b"v 0 0 0\n" * (e["bytes"] // 8 + 1) if "bytes" in e else e["contenido"].encode()
            r = sesion.http.post("/auditorias", files={"archivo": (e["archivo"], contenido)},
                                 data={"perfil": "animacion"})
        elif caso["tipo"] == "auditoria":
            r = sesion.auditar(dir_mallas / e["malla"], "animacion", e["notas"])
        elif caso["tipo"] == "pregunta":
            r = sesion.preguntar(referencia, e["pregunta"])
        else:
            r = sesion.http.post("/documentos", files={"archivo": (e["archivo"], e["contenido"].encode())})
        cuerpo = r.json() if "json" in r.headers.get("content-type", "") else {}
        activados = cuerpo.get("guardrails", [])
        correcto = r.status_code == esperado["codigo"]
        if "guardrail" in esperado:
            correcto = correcto and esperado["guardrail"] in activados
        if "no_contiene" in esperado:
            correcto = correcto and esperado["no_contiene"] not in r.text
        if esperado.get("sin_rechazo"):
            correcto = correcto and "E2" not in activados and "E4" not in activados
        filas.append({"caso": caso["id"], "guardrail": caso["guardrail"], "tipo": caso["tipo"],
                      "codigo_esperado": esperado["codigo"], "codigo": r.status_code,
                      "activados": activados, "aviso": bool(cuerpo.get("aviso")), "correcto": correcto})
    return filas


# -- Tabla 19: caché --------------------------------------------------------------
def tabla19(sesion: Sesion, dir_mallas) -> list[dict]:
    producto = {c["id"]: c for c in cargar("casos_producto.json")}
    casos = cargar("casos_cache.json")
    filas = []
    for c in casos["auditorias_repetidas"]:
        p = producto[c["caso_producto"]]
        primera = sesion.auditar(dir_mallas / p["malla"], p["perfil"]).json()
        segunda = sesion.auditar(dir_mallas / p["malla"], p["perfil"]).json()
        filas.append({"grupo": "auditoria_repetida", "caso": c["id"], "acierto": segunda["cache"] == "exacta",
                      "cache": segunda["cache"], "ms_fallo": primera["tiempo_ms"], "ms_acierto": segunda["tiempo_ms"]})
    referencia = sesion.auditar(dir_mallas / "M1.obj", "animacion").json()["auditoria_id"]
    for c in casos["preguntas_repetidas"]:
        primera = sesion.preguntar(referencia, c["pregunta"]).json()
        segunda = sesion.preguntar(referencia, c["pregunta"]).json()
        filas.append({"grupo": "pregunta_repetida", "caso": c["id"], "acierto": segunda["cache"] == "exacta",
                      "cache": segunda["cache"], "ms_fallo": primera["tiempo_ms"], "ms_acierto": segunda["tiempo_ms"]})
    for grupo in ("parafrasis", "distractores"):
        for c in casos[grupo]:
            r = sesion.preguntar(referencia, c["pregunta"]).json()
            acierto = r["cache"] == "semantica"
            filas.append({"grupo": grupo, "caso": c["id"], "acierto": acierto, "cache": r["cache"],
                          "falso_positivo": acierto if grupo == "distractores" else None,
                          "ms_acierto": r["tiempo_ms"]})
    for grupo in ("auditoria_repetida", "pregunta_repetida", "parafrasis", "distractores"):
        del_grupo = [f for f in filas if f["grupo"] == grupo and f["caso"] != "RESUMEN"]
        filas.append({"grupo": grupo, "caso": "RESUMEN",
                      "acierto": round(sum(f["acierto"] for f in del_grupo) / len(del_grupo), 3)})
    return filas


# -- Tabla 20: enrutador ------------------------------------------------------------
def tabla20(sesion: Sesion, dir_mallas, juez, args) -> list[dict]:
    producto = {c["id"]: c for c in cargar("casos_producto.json")}
    solo_rapido = None
    if args.juez and not args.url:  # etiqueta por calidad: ¿basta gemma4:e2b?
        solo_rapido = Sesion(proveedor=args.proveedor, cache=False, corpus=args.corpus)
        chats = solo_rapido.contenedor.extras["chats"]
        chats["completo"] = chats["rapido"]
    filas = []
    for c in cargar("casos_enrutador.json"):
        p = producto[c["caso_producto"]]
        inf = sesion.auditar(dir_mallas / p["malla"], p["perfil"]).json()
        etiqueta = c.get("ruta_esperada_calidad")
        nota_rapido = None
        if solo_rapido is not None and inf["ruta"] != "sin_modelo":
            r = solo_rapido.auditar(dir_mallas / p["malla"], p["perfil"]).json()
            notas = [juez.calificar(h["descripcion"], h["explicacion"] or "",
                                    [h["fuente"]["fragmento"]] if h.get("fuente") else [])
                     for h in r["hallazgos"] if h["gravedad"] != "informativo"]
            notas = [min(n["fidelidad"], n["relevancia"]) for n in notas if n]
            if notas:
                nota_rapido = round(sum(notas) / len(notas), 2)
                etiqueta = "rapida" if nota_rapido >= 4 else "completa"
        filas.append({"caso": c["id"], "caso_producto": p["id"], "perfil": p["perfil"],
                      "ruta_esperada_regla": c["ruta_esperada_regla"], "ruta_esperada_calidad": etiqueta,
                      "nota_rapido": nota_rapido, "ruta": inf["ruta"], "modelo": inf["modelo"],
                      "acierto_regla": inf["ruta"] == c["ruta_esperada_regla"],
                      "acierto_calidad": (inf["ruta"] == etiqueta) if etiqueta else None,
                      "tiempo_ms": inf["tiempo_ms"]})
    return filas


# -- Tabla 21: agente ------------------------------------------------------------------
def tabla21(sesion: Sesion, dir_mallas) -> list[dict]:
    referencias = {}
    filas = []
    for c in cargar("casos_agente.json"):
        perfil = PERFIL_DE_DOC.get(c["documento"], "animacion")
        if perfil not in referencias:
            referencias[perfil] = sesion.auditar(dir_mallas / "M1.obj", perfil).json()["auditoria_id"]
        r = sesion.preguntar(referencias[perfil], c["consulta"]).json()
        normas = _normas(r)
        traza = sesion.trazas().get(r.get("traza_id"), {})
        filas.append({"caso": c["id"], "iteraciones": r.get("iteraciones_agente"),
                      "top1": (traza.get("recuperaciones") or [{}])[-1].get("top1"),
                      "fuente_correcta": any(f.get("doc_id") == c["documento"] and f.get("seccion") == c["seccion"]
                                             for f in normas),
                      "sin_norma": not normas, "guardrails": r.get("guardrails"),
                      "tiempo_ms": r.get("tiempo_ms")})
    return filas


# -- Tabla 22: fallas ---------------------------------------------------------------------
def tabla22(args, dir_mallas) -> list[dict]:
    filas = []
    for c in cargar("casos_fallas.json"):
        sesion = Sesion(proveedor=args.proveedor, cache=False, corpus=args.corpus, falla=c["falla"])
        r = sesion.auditar(dir_mallas / c["malla"], c["perfil"])
        cuerpo = r.json()
        traza = sesion.trazas().get(cuerpo.get("traza_id"), {})
        llamadas = traza.get("llamadas", [])
        filas.append({"caso": c["id"], "falla": c["falla"], "codigo_esperado": c["esperado"]["codigo"],
                      "codigo": r.status_code, "uso_respaldo": cuerpo.get("uso_respaldo"),
                      "llamadas_fallidas": sum(not x["ok"] for x in llamadas),
                      "aviso": bool(cuerpo.get("aviso")),
                      "correcto": r.status_code == c["esperado"]["codigo"] and (
                          "uso_respaldo" not in c["esperado"]
                          or cuerpo.get("uso_respaldo") == c["esperado"]["uso_respaldo"])})
    return filas


# -- Tabla 23: latencias ----------------------------------------------------------------------
def tabla23(sesion: Sesion, dir_mallas, corridas: int) -> list[dict]:
    filas = []
    for caso in cargar("casos_producto.json"):
        totales, por_capa = [], {}
        for _ in range(corridas):
            inicio = time.perf_counter()
            r = sesion.auditar(dir_mallas / caso["malla"], caso["perfil"])
            totales.append((time.perf_counter() - inicio) * 1000)
            traza = sesion.trazas().get(r.json().get("traza_id"), {})
            for etapa, ms in (traza.get("tiempos_ms") or {}).items():
                por_capa.setdefault(etapa.split(".")[0], []).append(ms)
        fila = {"caso": caso["id"], "perfil": caso["perfil"], "mutacion": caso["mutacion"],
                "corridas": corridas, **{f"total_{k}": v for k, v in estadisticos(totales).items()}}
        for capa, valores in sorted(por_capa.items()):
            fila[f"{capa}_mediana"] = estadisticos(valores)["mediana"]
        filas.append(fila)
    return filas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="servicio ya levantado (si no, la API corre en proceso)")
    p.add_argument("--trazas", type=Path, help="data/trazas.jsonl del servicio externo")
    p.add_argument("--proveedor", default="falso", choices=["falso", "ollama"])
    p.add_argument("--corpus", type=Path, default=None, help="corpus a ingerir (en proceso)")
    p.add_argument("--mallas", type=Path, default=None, help="directorio con base y M1–M5")
    p.add_argument("--prefijo", default=None, help="malla base de Blender (<prefijo>_M1.obj)")
    p.add_argument("--juez", action="store_true", help="usa mistral-small3.2:24b como juez")
    p.add_argument("--modelo-juez", default="mistral-small3.2:24b")
    p.add_argument("--ollama", default="http://127.0.0.1:11434")
    p.add_argument("--corridas", type=int, default=5)
    p.add_argument("--salida", type=Path, default=RESULTADOS)
    p.add_argument("--tablas", default="16,17,18,19,20,21,22,23")
    args = p.parse_args(argv)
    if args.corpus is None and args.proveedor == "falso" and not args.url:
        args.corpus = CORPUS_PRUEBA
    tablas = {int(x) for x in args.tablas.split(",")}
    dir_mallas = mallas(args.mallas, args.proveedor, args.prefijo)
    juez = crear_juez(args.juez, args.modelo_juez, args.ollama)

    def sesion(cache: bool) -> Sesion:
        if args.url:
            return Sesion(url=args.url, trazas=args.trazas)
        return Sesion(proveedor=args.proveedor, cache=cache, corpus=args.corpus)

    sin_cache = sesion(cache=False)
    pasos = {
        16: ("tabla16_producto.csv", lambda: tabla16(sin_cache, dir_mallas, juez)),
        17: ("tabla17_recuperacion.csv", lambda: tabla17(sin_cache, dir_mallas)),
        18: ("tabla18_guardrails.csv", lambda: tabla18(sin_cache, dir_mallas)),
        19: ("tabla19_cache.csv", lambda: tabla19(sesion(cache=True), dir_mallas)),
        20: ("tabla20_enrutador.csv", lambda: tabla20(sin_cache, dir_mallas, juez, args)),
        21: ("tabla21_agente.csv", lambda: tabla21(sin_cache, dir_mallas)),
        22: ("tabla22_fallas.csv", lambda: tabla22(args, dir_mallas) if not args.url else
             [{"nota": "La tabla de fallas inyecta errores en el adaptador: córrela sin --url."}]),
        23: ("tabla23_latencias.csv", lambda: tabla23(sin_cache, dir_mallas, args.corridas)),
    }
    for numero in sorted(tablas):
        nombre, funcion = pasos[numero]
        inicio = time.perf_counter()
        ruta = escribir_csv(args.salida / nombre, funcion())
        print(f"Tabla {numero}: {ruta} ({time.perf_counter() - inicio:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
