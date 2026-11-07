"""Métricas (T1 + T2) calculadas a partir de las trazas para ``GET /metricas``."""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from servicio.observabilidad.traza import CAPA_DE_ETAPA


def _resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "media": None, "p50": None, "p95": None}
    arr = np.asarray(valores, dtype=float)
    return {"n": int(arr.size), "media": round(float(arr.mean()), 3),
            "p50": round(float(np.percentile(arr, 50)), 3),
            "p95": round(float(np.percentile(arr, 95)), 3)}


def capa_de(etapa: str) -> str:
    return CAPA_DE_ETAPA.get(etapa, etapa.split(".")[0])


def calcular_metricas(trazas: list[dict], retroalimentacion: dict | None = None) -> dict:
    por_etapa: dict[str, list[float]] = defaultdict(list)
    por_capa: dict[str, list[float]] = defaultdict(list)
    gateway_por_ruta: dict[str, list[float]] = defaultdict(list)
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
        capas_traza: dict[str, float] = defaultdict(float)
        for etapa, ms in (t.get("tiempos_ms") or {}).items():
            por_etapa[etapa].append(ms)
            capas_traza[capa_de(etapa)] += ms
            if etapa == "gateway" and t.get("ruta"):
                gateway_por_ruta[t["ruta"]].append(ms)
        # Las llamadas al modelo del agente (dentro de contexto_rag) y del clasificador de E2
        # (dentro de guardrails_entrada) son tiempo de C6, no de C5 ni de C3.
        for llamada in t.get("llamadas") or []:
            origen = {"agente": "C5", "clasificador": "C3"}.get(llamada.get("ruta"))
            if origen and capas_traza.get(origen):
                ms = min(llamada.get("duracion_ms", 0.0), capas_traza[origen])
                capas_traza[origen] -= ms
                capas_traza["C6"] += ms
        for capa, ms in capas_traza.items():   # una muestra por traza y capa
            por_capa[capa].append(round(ms, 3))
        if t.get("tiempo_total_ms") is not None:
            totales[t.get("tipo")].append(t["tiempo_total_ms"])
        if t.get("tipo") in ("auditoria", "pregunta"):
            cache[t.get("cache") or "ninguna"] += 1
            if t.get("ruta"):
                rutas[t["ruta"]] += 1
            iteraciones.append(t.get("iteraciones_agente", 0))
            if t.get("uso_respaldo"):
                respaldo += 1
        g = t.get("guardrails") or {}
        for activacion in (g.get("activaciones", []) if isinstance(g, dict) else g):
            guardrails[activacion] += 1
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
            "gateway_por_ruta": {r: _resumen(v) for r, v in gateway_por_ruta.items()},
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


class Metricas:
    """``GET /metricas``: lee las trazas (T1) y la retroalimentación (T2)."""

    def __init__(self, registro, retroalimentacion=None):
        self.registro = registro
        self.retroalimentacion = retroalimentacion

    def resumen(self) -> dict:
        retro = self.retroalimentacion.resumen() if self.retroalimentacion else {}
        return calcular_metricas(self.registro.leer(), retro)
