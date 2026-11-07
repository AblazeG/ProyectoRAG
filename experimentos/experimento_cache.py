"""Experimento del umbral de la caché semántica (ADR-03): tabla 22 del informe.

Para cada umbral (0.85, 0.90, 0.92 y 0.95) se hacen las 10 preguntas originales
sobre el mismo informe y luego sus 10 paráfrasis y 10 distractores. Recall:
paráfrasis servidas desde la caché; precisión: aciertos que no son distractores;
ahorro: latencia media de un fallo menos la de un acierto. La fila «Exacta»
repite 10 auditorías y 10 preguntas (20 repetidas).

    python -m experimentos.experimento_cache --proveedor ollama --salida evaluacion/resultados/
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion.comun import (Sesion, argumentos_comunes, cargar, corpus_por_defecto,  # noqa: E402
                              escribir_csv, mallas)

UMBRALES = (0.85, 0.90, 0.92, 0.95)


def _media(valores):
    return statistics.mean(valores) if valores else None


def tabla22(proveedor: str, corpus: Path, dir_mallas: Path, umbrales=UMBRALES) -> list[dict]:
    casos = cargar("casos_cache.json")
    producto = {c["id"]: c for c in cargar("casos_producto.json")}
    referencia = producto[casos["informe_preguntas"]]
    filas = []
    for umbral in umbrales:
        sesion = Sesion(proveedor=proveedor, cache=True, corpus=corpus)
        sesion.contenedor.extras["cache_semantica"].umbral = umbral
        auditoria = sesion.auditar(dir_mallas / referencia["malla"], referencia["perfil"]).json()
        fallos_ms = [sesion.preguntar(auditoria["auditoria_id"], c["original"]).json()["tiempo_ms"]
                     for c in casos["parafrasis"]]
        par = [sesion.preguntar(auditoria["auditoria_id"], c["pregunta"]).json() for c in casos["parafrasis"]]
        dis = [sesion.preguntar(auditoria["auditoria_id"], c["pregunta"]).json() for c in casos["distractores"]]
        vp = sum(r["cache"] == "semantica" for r in par)
        fp = sum(r["cache"] == "semantica" for r in dis)
        aciertos_ms = [r["tiempo_ms"] for r in par + dis if r["cache"] == "semantica"]
        filas.append({"umbral": umbral, "recall": round(vp / len(par), 3),
                      "precision": round(vp / (vp + fp), 3) if vp + fp else None,
                      "falsos_positivos": fp,
                      "ahorro_ms": round(_media(fallos_ms) - _media(aciertos_ms), 1) if aciertos_ms else None})
    # Exacta: 10 auditorías repetidas sin notas + 10 preguntas repetidas
    sesion = Sesion(proveedor=proveedor, cache=True, corpus=corpus)
    primeras, segundas = [], []
    for c in casos["auditorias_repetidas"]:
        p = producto[c["caso_producto"]]
        primeras.append(sesion.auditar(dir_mallas / p["malla"], p["perfil"]).json())
        segundas.append(sesion.auditar(dir_mallas / p["malla"], p["perfil"]).json())
    auditoria = segundas[0]["auditoria_id"]
    for c in casos["preguntas_repetidas"]:
        primeras.append(sesion.preguntar(auditoria, c["pregunta"]).json())
        segundas.append(sesion.preguntar(auditoria, c["pregunta"]).json())
    aciertos = [s for s in segundas if s["cache"] == "exacta"]
    filas.append({"umbral": "Exacta (20 repetidas)", "recall": round(len(aciertos) / len(segundas), 3),
                  "precision": 1.0, "falsos_positivos": 0,
                  "ahorro_ms": round(_media([p["tiempo_ms"] for p in primeras])
                                     - _media([s["tiempo_ms"] for s in aciertos]), 1) if aciertos else None,
                  "acierto_exacto_p95_ms": round(sorted(s["tiempo_ms"] for s in aciertos)[
                      int(0.95 * (len(aciertos) - 1))], 1) if aciertos else None})
    return filas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    argumentos_comunes(p)
    p.add_argument("--mallas", type=Path, default=None)
    args = p.parse_args(argv)
    filas = tabla22(args.proveedor, corpus_por_defecto(args), mallas(args.mallas, args.proveedor))
    for f in filas:
        print(f)
    print(escribir_csv(args.salida / "tabla22_cache.csv", filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
