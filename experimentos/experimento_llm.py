"""Experimento de modelos de lenguaje (ADR-01): tabla 8 del informe.

Candidatos: gemma4:e2b, qwen3:8b y gpt-oss:20b, con temperature 0.1, num_ctx 8192
y seed 42 (think desactivado en gemma4 y qwen3, bajo en gpt-oss). Cada candidato
explica los hallazgos de los 20 casos de producto (ambos alias apuntan a él).

Columnas: calidad (0–5, media de fidelidad y relevancia del juez
mistral-small3.2:24b), español (0–5), latencia p50/p95 por auditoría (s),
tok/s en caliente (eval_count / eval_duration × 10⁹), memoria (GB, ``ollama ps``)
y carga en frío (s), medida una sola vez y aparte. Entre candidatos cada modelo
se libera de la memoria. Además escribe ``muestra_revision_manual.csv`` con cinco
casos al azar por modelo para validar al juez a mano (15 casos).

    python -m experimentos.experimento_llm --proveedor ollama --juez --salida evaluacion/resultados/
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion.comun import (OLLAMA, Sesion, argumentos_comunes, cargar, chat_para,  # noqa: E402
                              corpus_por_defecto, escribir_csv, estadisticos, mallas)
from evaluacion.juez import crear_juez  # noqa: E402

CANDIDATOS = ["gemma4:e2b", "qwen3:8b", "gpt-oss:20b"]


def _ollama(metodo: str, ruta: str, **kw):
    import httpx
    try:
        return httpx.request(metodo, f"{OLLAMA}{ruta}", timeout=600, trust_env=False, **kw).json()
    except Exception:  # noqa: BLE001
        return None


def liberar(modelo: str) -> None:
    _ollama("POST", "/api/generate", json={"model": modelo, "keep_alive": 0})


def memoria_gb(modelo: str) -> float | None:
    estado = _ollama("GET", "/api/ps") or {}
    for m in estado.get("models", []):
        if m.get("name", "").startswith(modelo):
            return round(m.get("size", 0) / 1e9, 2)
    return None


def carga_en_frio(modelo: str) -> float | None:
    inicio = time.perf_counter()
    r = _ollama("POST", "/api/generate", json={"model": modelo, "prompt": "ok", "stream": False,
                                               "options": {"num_ctx": 8192}})
    return round(time.perf_counter() - inicio, 2) if r else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos_comunes(p)
    p.add_argument("--candidatos", default=",".join(CANDIDATOS))
    p.add_argument("--mallas", type=Path, default=None)
    p.add_argument("--mallas-sinteticas", action="store_true",
                   help="genera mallas sintéticas si faltan (sin Blender)")
    p.add_argument("--juez", action="store_true")
    p.add_argument("--corridas", type=int, default=1)
    args = p.parse_args(argv)
    corpus = corpus_por_defecto(args)
    dir_mallas = mallas(args.mallas, args.proveedor, args.mallas_sinteticas)
    juez = crear_juez(args.juez, "mistral-small3.2:24b", OLLAMA)
    casos = cargar("casos_producto.json")
    filas, muestra = [], []
    rng = random.Random(42)
    for modelo in args.candidatos.split(","):
        frio = None
        if args.proveedor == "ollama":
            for otro in CANDIDATOS:
                liberar(otro)
            frio = carga_en_frio(modelo)
        chat = chat_para(modelo, args.proveedor)
        sesion = Sesion(proveedor=args.proveedor, cache=False, corpus=corpus,
                        chats={"rapido": chat, "completo": chat})
        tiempos, tok_s, notas, explicaciones = [], [], [], []
        for _ in range(args.corridas):
            for caso in casos:
                inf = sesion.auditar(dir_mallas / caso["malla"], caso["perfil"]).json()
                if inf.get("ruta") in (None, "sin_modelo"):
                    continue
                tiempos.append(inf["tiempo_ms"] / 1000)
                traza = sesion.trazas().get(inf["traza_id"], {})
                tok_s += [l["tokens_por_s"] for l in traza.get("llamadas", []) if l.get("tokens_por_s")]
                for h in inf["hallazgos"]:
                    if h["gravedad"] == "informativo" or not h.get("fuente"):
                        continue
                    texto = h["explicacion"] + "\n" + "\n".join(h["correccion"])
                    nota = juez.calificar(f"Explicar el hallazgo {h['verificacion']}: {h['descripcion']}",
                                          texto, [h["fuente"]["fragmento"]])
                    explicaciones.append({"modelo": modelo, "caso": caso["id"], "hallazgo": h["id"],
                                          "explicacion": texto, "fragmento": h["fuente"]["fragmento"],
                                          **(nota or {})})
                    if nota:
                        notas.append(nota)
        muestra += rng.sample(explicaciones, min(5, len(explicaciones)))
        lat = estadisticos(tiempos)
        filas.append({
            "modelo": modelo, "informes": len(tiempos),
            "calidad": round(statistics.mean((n["fidelidad"] + n["relevancia"]) / 2 for n in notas), 2) if notas else None,
            "fidelidad": round(statistics.mean(n["fidelidad"] for n in notas), 2) if notas else None,
            "relevancia": round(statistics.mean(n["relevancia"] for n in notas), 2) if notas else None,
            "espanol": round(statistics.mean(n.get("espanol", 0) for n in notas), 2) if notas else None,
            "latencia_p50_s": lat["mediana"], "latencia_p95_s": lat["p95"],
            "tok_s": round(statistics.mean(tok_s), 1) if tok_s else None,
            "memoria_gb": memoria_gb(modelo) if args.proveedor == "ollama" else None,
            "carga_en_frio_s": frio})
        print(filas[-1])
    print(escribir_csv(args.salida / "tabla08_llm.csv", filas))
    print(escribir_csv(args.salida / "muestra_revision_manual.csv",
                       [{**m, "nota_autor_fidelidad": "", "nota_autor_relevancia": ""} for m in muestra]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
