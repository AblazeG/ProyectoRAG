"""Experimento de fragmentación: 500/k=8, 800/k=5 y 1000/k=4 (solape 120), más un
barrido de k ∈ {3, 5, 8} y umbral 0.40–0.70 con la configuración de 800.

    python -m experimentos.experimento_fragmentos --proveedor ollama --modelo nomic-embed-text --corpus corpus/
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from evaluacion.comun import (CORPUS_PRUEBA, RAIZ, cargar, embeddings_para, escribir_csv,
                              evaluar_recuperacion, indice_en_memoria)

CONFIGURACIONES = [(500, 8), (800, 5), (1000, 4)]
SALIDA = RAIZ / "experimentos" / "resultados"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proveedor", default="falso", choices=["falso", "ollama"])
    p.add_argument("--modelo", default="nomic-embed-text")
    p.add_argument("--corpus", type=Path, default=None)
    p.add_argument("--solape", type=int, default=120)
    args = p.parse_args(argv)
    corpus = args.corpus or CORPUS_PRUEBA
    casos = cargar("casos_recuperacion.json")
    emb = embeddings_para(args.modelo, args.proveedor)
    filas = []
    recuperador_800 = None
    for tam, k in CONFIGURACIONES:
        indice, recuperador = indice_en_memoria(emb, corpus, tam, args.solape)
        if tam == 800:
            recuperador_800 = recuperador
        filas.append({"experimento": "configuracion", "tam": tam, "solape": args.solape, "k": k,
                      "umbral": 0.55, "fragmentos": indice.almacen.contar(),
                      **evaluar_recuperacion(recuperador, casos, k, 0.55)})
    for k in (3, 5, 8):
        for umbral in np.round(np.arange(0.40, 0.701, 0.05), 2):
            filas.append({"experimento": "barrido", "tam": 800, "solape": args.solape, "k": k,
                          "umbral": float(umbral),
                          **evaluar_recuperacion(recuperador_800, casos, k, float(umbral))})
    for f in filas[:3]:
        print(f)
    print(escribir_csv(SALIDA / "experimento_fragmentos.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
