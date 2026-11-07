"""Experimento de embeddings (ADR-02): tabla 9 del informe.

bge-m3, embeddinggemma y nomic-embed-text sobre las 30 consultas con sección
relevante: acierto@1, acierto@5 y MRR (orden, sin umbral), tiempo de indexado (s) y,
aparte, los rechazos correctos de las 10 consultas sin respaldo con el umbral 0.55.

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
        # Orden puro (umbral 0): los modelos tienen escalas de similitud distintas y un
        # umbral fijo calibrado para bge-m3 penalizaría a los otros dos. Los rechazos de
        # las 10 consultas sin respaldo se informan aparte, con el umbral del servicio.
        orden = evaluar_recuperacion(recuperador, relevantes, 5, 0.0)
        rechazo = evaluar_recuperacion(recuperador, casos, 5, args.umbral)
        filas.append({"modelo": modelo, "fragmentos": indice.almacen.contar(),
                      "acierto_1": orden["acierto_1"], "acierto_5": orden["acierto_k"],
                      "mrr": orden["mrr"], "acierto_5_con_umbral": rechazo["acierto_k"],
                      "rechazos_correctos": rechazo["rechazos_correctos"],
                      "rechazos_de": rechazo["rechazos_de"], "indexado_s": round(indexado_s, 2)})
        print(filas[-1])
    print(escribir_csv(args.salida / "tabla09_embeddings.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
