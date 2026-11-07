"""Experimento de modelos de chat: gemma4:e2b, qwen3:8b y gpt-oss:20b.

Cada candidato explica los hallazgos de los casos de producto (ambos alias
apuntan al candidato). Se mide latencia, validez del JSON (S1), citas
inventadas (S2), cifras sin respaldo (S3), «sin norma» y, con --juez, la
calidad con mistral-small3.2:24b.

    python -m experimentos.experimento_llm --proveedor ollama --corpus corpus/ --juez
    python -m experimentos.experimento_llm --proveedor falso
"""
from __future__ import annotations

import argparse
from pathlib import Path

from evaluacion.comun import (CORPUS_PRUEBA, RAIZ, Sesion, cargar, chat_para, escribir_csv,
                              estadisticos, mallas)
from evaluacion.juez import crear_juez

CANDIDATOS = ["gemma4:e2b", "qwen3:8b", "gpt-oss:20b"]
SALIDA = RAIZ / "experimentos" / "resultados"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proveedor", default="falso", choices=["falso", "ollama"])
    p.add_argument("--corpus", type=Path, default=None)
    p.add_argument("--candidatos", default=",".join(CANDIDATOS))
    p.add_argument("--juez", action="store_true")
    p.add_argument("--corridas", type=int, default=1)
    args = p.parse_args(argv)
    corpus = args.corpus or CORPUS_PRUEBA
    dir_mallas = mallas(None, "falso")
    juez = crear_juez(args.juez, "mistral-small3.2:24b", "http://127.0.0.1:11434")
    casos = [c for c in cargar("casos_producto.json") if c["mutacion"] != "base"]
    filas = []
    for modelo in args.candidatos.split(","):
        chat = chat_para(modelo, args.proveedor)
        sesion = Sesion(proveedor=args.proveedor, cache=False, corpus=corpus,
                        chats={"rapido": chat, "completo": chat})
        tiempos, s1, s2, s3, sin_norma, explicados, notas = [], 0, 0, 0, 0, 0, []
        for _ in range(args.corridas):
            for caso in casos:
                inf = sesion.auditar(dir_mallas / caso["malla"], caso["perfil"]).json()
                if inf.get("ruta") in (None, "sin_modelo"):
                    continue
                tiempos.append(inf["tiempo_ms"])
                g = inf["guardrails"]
                s1, s2, s3 = s1 + ("S1" in g), s2 + ("S2" in g), s3 + ("S3" in g)
                for h in inf["hallazgos"]:
                    if h["gravedad"] == "informativo":
                        continue
                    explicados += 1
                    sin_norma += h["explicacion"] == "Sin norma aplicable en el corpus"
                    if h.get("fuente"):
                        nota = juez.calificar(h["descripcion"], h["explicacion"] + "\n" + "\n".join(h["correccion"]),
                                              [h["fuente"]["fragmento"]])
                        if nota:
                            notas.append(nota)
        n = len(tiempos) or 1
        filas.append({"modelo": modelo, "informes": len(tiempos), **{f"latencia_{k}": v for k, v in estadisticos(tiempos).items()},
                      "tasa_s1": round(s1 / n, 3), "tasa_s2": round(s2 / n, 3), "tasa_s3": round(s3 / n, 3),
                      "hallazgos": explicados, "sin_norma": sin_norma,
                      "fidelidad": round(sum(x["fidelidad"] for x in notas) / len(notas), 2) if notas else None,
                      "relevancia": round(sum(x["relevancia"] for x in notas) / len(notas), 2) if notas else None})
        print(filas[-1])
    print(escribir_csv(SALIDA / "experimento_llm.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
