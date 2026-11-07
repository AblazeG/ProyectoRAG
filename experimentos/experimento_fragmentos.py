"""Experimento de fragmentación (ADR-06): tablas 17 y 18 del informe.

- Tabla 17: tamaño de fragmento con el mismo presupuesto de ~4 000 caracteres
  (500 car./solape 75/k=8, 800/120/k=5 y 1000/150/k=4; solape del 15 %).
- Tabla 18: barrido de k ∈ {3, 5, 8} y umbral ∈ {0.40, 0.50, 0.55, 0.60, 0.70}
  con 800/120; un acierto exige la sección relevante entre los k primeros y sobre
  el umbral; rechazos correctos de las 10 consultas sin respaldo.

    python -m experimentos.experimento_fragmentos --proveedor ollama --salida evaluacion/resultados/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion.comun import (argumentos_comunes, cargar, corpus_por_defecto, embeddings_para,  # noqa: E402
                              escribir_csv, evaluar_recuperacion, indice_en_memoria)

CONFIGURACIONES = [(500, 75, 8), (800, 120, 5), (1000, 150, 4)]
KS = (3, 5, 8)
UMBRALES = (0.40, 0.50, 0.55, 0.60, 0.70)


def tabla17(embeddings, corpus: Path, casos: list[dict]) -> list[dict]:
    filas = []
    for tam, solape, k in CONFIGURACIONES:
        indice, recuperador = indice_en_memoria(embeddings, corpus, tam, solape)
        m = evaluar_recuperacion(recuperador, casos, k, 0.55)
        filas.append({"fragmento": f"{tam} car., solape {solape}", "k": k,
                      "fragmentos": indice.almacen.contar(), "acierto_k": m["acierto_k"],
                      "mrr": m["mrr"], "acierto_1": m["acierto_1"]})
    return filas


def tabla18(embeddings, corpus: Path, casos: list[dict]) -> list[dict]:
    _, recuperador = indice_en_memoria(embeddings, corpus, 800, 120)
    filas = []
    for umbral in UMBRALES:
        fila = {"umbral": umbral}
        for k in KS:
            m = evaluar_recuperacion(recuperador, casos, k, umbral)
            fila[f"acierto_{k}"] = m["acierto_k"]
        fila["rechazos_de_10"] = m["rechazos_correctos"]
        filas.append(fila)
    return filas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos_comunes(p)
    p.add_argument("--modelo", default="bge-m3", help="modelo de embeddings (ADR-02)")
    args = p.parse_args(argv)
    corpus = corpus_por_defecto(args)
    casos = cargar("casos_recuperacion.json")
    emb = embeddings_para(args.modelo, args.proveedor)
    print(escribir_csv(args.salida / "tabla17_fragmentos.csv", tabla17(emb, corpus, casos)))
    print(escribir_csv(args.salida / "tabla18_barrido.csv", tabla18(emb, corpus, casos)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
