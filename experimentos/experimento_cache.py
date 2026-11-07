"""Experimento del umbral de la caché semántica: 0.85, 0.90, 0.92 y 0.95.

Con los pares de casos_cache.json: las paráfrasis deberían acertar y los
distractores (misma forma, otra pregunta) no. Reporta exhaustividad de
aciertos, tasa de falsos positivos y precisión.

    python -m experimentos.experimento_cache --proveedor ollama --modelo nomic-embed-text
"""
from __future__ import annotations

import argparse

import numpy as np

from evaluacion.comun import RAIZ, cargar, embeddings_para, escribir_csv

UMBRALES = [0.85, 0.90, 0.92, 0.95]
SALIDA = RAIZ / "experimentos" / "resultados"


def coseno(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proveedor", default="falso", choices=["falso", "ollama"])
    p.add_argument("--modelo", default="nomic-embed-text")
    args = p.parse_args(argv)
    casos = cargar("casos_cache.json")
    emb = embeddings_para(args.modelo, args.proveedor)

    def similitudes(grupo):
        originales = emb.vectorizar([c["original"] for c in casos[grupo]], "consulta")
        variantes = emb.vectorizar([c["pregunta"] for c in casos[grupo]], "consulta")
        return [coseno(a, b) for a, b in zip(originales, variantes)]

    parafrasis, distractores = similitudes("parafrasis"), similitudes("distractores")
    filas = [{"tipo": "similitud", "grupo": g, "caso": c["id"], "coseno": round(s, 4)}
             for g, sims in (("parafrasis", parafrasis), ("distractores", distractores))
             for c, s in zip(casos[g], sims)]
    for umbral in UMBRALES:
        vp = sum(s >= umbral for s in parafrasis)
        fp = sum(s >= umbral for s in distractores)
        filas.append({"tipo": "umbral", "umbral": umbral,
                      "exhaustividad": round(vp / len(parafrasis), 3),
                      "falsos_positivos": round(fp / len(distractores), 3),
                      "precision": round(vp / (vp + fp), 3) if vp + fp else None})
        print(filas[-1])
    print(escribir_csv(SALIDA / "experimento_cache.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
