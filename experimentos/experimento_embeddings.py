"""Experimento de embeddings: bge-m3, embeddinggemma y nomic-embed-text.

Indexa el corpus con cada modelo (en memoria) y mide acierto@5, MRR y rechazo
correcto con casos_recuperacion.json, más el tiempo de indexado y de consulta.

    python -m experimentos.experimento_embeddings --proveedor ollama --corpus corpus/
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from evaluacion.comun import (CORPUS_PRUEBA, RAIZ, cargar, embeddings_para, escribir_csv,
                              evaluar_recuperacion, indice_en_memoria)

CANDIDATOS = ["bge-m3", "embeddinggemma", "nomic-embed-text"]
SALIDA = RAIZ / "experimentos" / "resultados"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proveedor", default="falso", choices=["falso", "ollama"])
    p.add_argument("--corpus", type=Path, default=None)
    p.add_argument("--candidatos", default=",".join(CANDIDATOS))
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--umbral", type=float, default=0.55)
    args = p.parse_args(argv)
    casos = cargar("casos_recuperacion.json")
    filas = []
    for modelo in args.candidatos.split(","):
        emb = embeddings_para(modelo, args.proveedor)
        inicio = time.perf_counter()
        indice, recuperador = indice_en_memoria(emb, args.corpus or CORPUS_PRUEBA)
        indexado = (time.perf_counter() - inicio) * 1000
        inicio = time.perf_counter()
        metricas = evaluar_recuperacion(recuperador, casos, args.k, args.umbral)
        consulta = (time.perf_counter() - inicio) * 1000 / len(casos)
        filas.append({"modelo": modelo, "fragmentos": indice.almacen.contar(), "k": args.k,
                      "umbral": args.umbral, **metricas, "indexado_ms": round(indexado, 1),
                      "consulta_ms": round(consulta, 2)})
        print(filas[-1])
    print(escribir_csv(SALIDA / "experimento_embeddings.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
