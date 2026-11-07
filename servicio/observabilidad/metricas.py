"""Métricas (T1 + T2) calculadas a partir de las trazas para ``GET /metricas``."""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np


def _resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "media": None, "p50": None, "p95": None}
    arr = np.asarray(valores, dtype=float)
    return {"n": int(arr.size), "media": round(float(arr.mean()), 3),
            "p50": round(float(np.percentile(arr, 50)), 3),
            "p95": round(float(np.percentile(arr, 95)), 3)}


def calcular_metricas(trazas: list[dict], retroalimentacion: dict | None = None) -> dict:
    por_etapa: dict[str, list[float]] = defaultdict(list)
    por_capa: dict[str, list[float]] = defaultdict(list)
    totales: dict[str, list[float]] = defaultdict(list)
    cache = Counter()
    guardrails = Counter()
    rutas = Counter()
    modelos = Counter()
    tipos = Counter()
    respaldo = 0
    llamadas_ok = 0
    iteraciones = []
    for t in trazas:
        tipos[t.get("tipo")] += 1
        for etapa, ms in (t.get("tiempos_ms") or {}).items():
            por_etapa[etapa].append(ms)
            por_capa[etapa.split(".")[0]].append(ms)
        if t.get("tiempo_total_ms") is not None:
            totales[t.get("tipo")].append(t["tiempo_total_ms"])
        if t.get("tipo") in ("auditoria", "pregunta"):
            cache[t.get("cache") or "ninguna"] += 1
            if t.get("ruta"):
                rutas[t["ruta"]] += 1
            iteraciones.append(t.get("iteraciones_agente", 0))
            if t.get("uso_respaldo"):
                respaldo += 1
        for g in t.get("guardrails") or []:
            guardrails[g] += 1
        for llamada in t.get("llamadas") or []:
            if llamada.get("ok"):
                llamadas_ok += 1
                modelos[llamada.get("modelo")] += 1
    consultas = sum(cache.values())
    return {
        "trazas": dict(tipos),
        "latencia_ms": {
            "por_capa": {c: _resumen(v) for c, v in sorted(por_capa.items())},
            "por_etapa": {e: _resumen(v) for e, v in sorted(por_etapa.items())},
            "total": {t: _resumen(v) for t, v in totales.items()},
        },
        "cache": {
            "exacta": cache.get("exacta", 0),
            "semantica": cache.get("semantica", 0),
            "hallazgos": cache.get("hallazgos", 0),
            "fallos": cache.get("ninguna", 0),
            "tasa_acierto": round((cache.get("exacta", 0) + cache.get("semantica", 0))
                                  / consultas, 4) if consultas else None,
        },
        "guardrails": dict(guardrails),
        "rutas": dict(rutas),
        "modelos": dict(modelos),
        "respaldo": {"usos": respaldo, "llamadas_ok": llamadas_ok,
                     "tasa": round(respaldo / consultas, 4) if consultas else None},
        "agente": {"iteraciones_totales": int(sum(iteraciones)),
                   "media": round(float(np.mean(iteraciones)), 3) if iteraciones else None,
                   "maximo": int(max(iteraciones)) if iteraciones else 0},
        "retroalimentacion": retroalimentacion or {},
    }
