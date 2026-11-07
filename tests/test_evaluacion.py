"""La evaluación y los experimentos deben correr en modo falso."""
import csv
import json

from evaluacion import run_eval
from evaluacion.comun import DIR_EVAL
from experimentos import experimento_cache, experimento_embeddings


def test_plantillas_de_casos():
    tamanos = {"casos_producto.json": 20, "casos_recuperacion.json": 40,
               "casos_guardrails.json": 23, "casos_fallas.json": 5}
    for nombre, n in tamanos.items():
        assert len(json.loads((DIR_EVAL / nombre).read_text())) == n
    rec = json.loads((DIR_EVAL / "casos_recuperacion.json").read_text())
    assert sum(c["relevante"] for c in rec) == 30
    cache = json.loads((DIR_EVAL / "casos_cache.json").read_text())
    assert all(len(v) == 10 for v in cache.values())


def test_run_eval_modo_falso(tmp_path):
    assert run_eval.main(["--proveedor", "falso", "--tablas", "17,18,21,22",
                          "--salida", str(tmp_path)]) == 0
    guardrails = list(csv.DictReader(open(tmp_path / "tabla18_guardrails.csv")))
    assert len(guardrails) == 23 and all(f["correcto"] == "True" for f in guardrails)
    fallas = list(csv.DictReader(open(tmp_path / "tabla22_fallas.csv")))
    assert all(f["correcto"] == "True" for f in fallas)
    assert (tmp_path / "tabla17_recuperacion.csv").exists()


def test_experimentos_modo_falso():
    assert experimento_cache.main(["--proveedor", "falso"]) == 0
    assert experimento_embeddings.main(["--proveedor", "falso", "--candidatos", "nomic-embed-text"]) == 0
