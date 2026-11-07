"""Experimento de embeddings (ADR-02): tabla 9 del informe.

bge-m3, embeddinggemma y nomic-embed-text sobre las 30 consultas con sección
relevante: acierto@1, acierto@5, MRR y tiempo de indexado (s).

    python -m experimentos.experimento_embeddings --proveedor ollama --salida evaluacion/resultados/
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion.comun import (argumentos_comunes, cargar, corpus_por_defecto, embeddings_para,  # noqa: E402
                              escribir_csv, evaluar_recuperacion, indice_en_memoria)

CANDIDATOS = ["bge-m3", "embeddinggemma", "nomic-embed-text"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos_comunes(p)
    p.add_argument("--candidatos", default=",".join(CANDIDATOS))
    p.add_argument("--umbral", type=float, default=0.55)
    args = p.parse_args(argv)
    corpus = corpus_por_defecto(args)
    casos = cargar("casos_recuperacion.json")
    relevantes = [c for c in casos if c["relevante"]]
    filas = []
    for modelo in args.candidatos.split(","):
        emb = embeddings_para(modelo, args.proveedor)
        inicio = time.perf_counter()
        indice, recuperador = indice_en_memoria(emb, corpus)
        indexado_s = time.perf_counter() - inicio
        m1 = evaluar_recuperacion(recuperador, relevantes, 1, args.umbral)
        m5 = evaluar_recuperacion(recuperador, casos, 5, args.umbral)
        filas.append({"modelo": modelo, "fragmentos": indice.almacen.contar(),
                      "acierto_1": m1["acierto_k"], "acierto_5": m5["acierto_k"], "mrr": m5["mrr"],
                      "rechazos_de_10": m5["rechazos_correctos"], "indexado_s": round(indexado_s, 2)})
        print(filas[-1])
    print(escribir_csv(args.salida / "tabla09_embeddings.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
