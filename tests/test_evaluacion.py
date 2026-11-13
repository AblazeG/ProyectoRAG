"""La evaluación (sección 9) y los experimentos deben correr en modo falso."""
import csv
import json

from evaluacion import run_eval
from evaluacion.comun import DIR_EVAL
from experimentos import experimento_embeddings, experimento_fragmentos


def test_conjuntos_de_la_tabla_15():
    cargar = lambda n: json.loads((DIR_EVAL / n).read_text())  # noqa: E731
    producto = cargar("casos_producto.json")
    assert len(producto) == 20                                      # 5 variantes × 4 perfiles
    assert {c["variante"] for c in producto} == {"M1", "M2", "M3", "M4", "M5"}
    web_m4 = next(c for c in producto if c["variante"] == "M4" and c["perfil"] == "web_ar")
    assert web_m4["malla"].endswith("_texturas.glb") and "V11" in web_m4["verificaciones_esperadas"]
    rec = cargar("casos_recuperacion.json")
    assert len(rec) == 40 and sum(c["relevante"] for c in rec) == 30
    guardrails = cargar("casos_guardrails.json")
    cuenta = {k: sum(c["categoria"] == k for c in guardrails)
              for k in ("inyeccion", "fuera_de_dominio", "datos_personales", "documento", "normal")}
    assert cuenta == {"inyeccion": 4, "fuera_de_dominio": 3, "datos_personales": 3,
                      "documento": 3, "normal": 10}
    assert sum(c["tipo"] == "pregunta_informe" for c in guardrails) == 3
    cache = cargar("casos_cache.json")
    assert all(len(cache[k]) == 10 for k in ("auditorias_repetidas", "preguntas_repetidas",
                                              "parafrasis", "distractores"))
    assert len(cargar("casos_enrutador.json")) == 40
    assert len(cargar("casos_agente.json")) == 8
    assert len(cargar("casos_fallas.json")) == 5


def test_run_eval_modo_falso(tmp_path):
    # Mallas sintéticas propias en un directorio temporal: la prueba no debe depender de las
    # mallas de Blender que haya en evaluacion/mallas_generadas ni escribir ahí.
    assert run_eval.main(["--proveedor", "falso", "--tablas", "19,fallas,privacidad",
                          "--mallas", str(tmp_path / "mallas"), "--salida", str(tmp_path)]) == 0
    resumen = list(csv.DictReader(open(tmp_path / "tabla19_guardrails.csv")))
    assert resumen[-1]["correctos"] == "100.0 %" and resumen[-1]["falsos_positivos"] == "0.0 %"
    fallas = list(csv.DictReader(open(tmp_path / "fallas.csv")))
    assert fallas[-1]["error_500"] == "0" and fallas[-1]["terminada_con_respaldo"] == "5 de 5"
    assert all(f["datos_personales"] == "0" for f in csv.DictReader(open(tmp_path / "privacidad.csv")))


def test_experimentos_modo_falso(tmp_path):
    assert experimento_embeddings.main(["--proveedor", "falso", "--candidatos", "bge-m3",
                                        "--salida", str(tmp_path)]) == 0
    assert experimento_fragmentos.main(["--proveedor", "falso", "--salida", str(tmp_path)]) == 0
    assert len(list(csv.DictReader(open(tmp_path / "tabla17_fragmentos.csv")))) == 3
    assert len(list(csv.DictReader(open(tmp_path / "tabla18_barrido.csv")))) == 5
    assert (tmp_path / "tabla09_embeddings.csv").exists()


def test_insumos_del_informe_llenan_las_tablas(tmp_path):
    """El generador de insumos lee los CSV de una corrida y no deja «?» en las tablas."""
    from evaluacion import insumos_informe
    from tests.utiles import CORPUS
    resultados = DIR_EVAL / "resultados" / "provisional_nube"
    assert insumos_informe.main(["--resultados", str(resultados), "--corpus", str(CORPUS),
                                 "--salida", str(tmp_path)]) == 0
    md = (tmp_path / "INSUMOS_INFORME.md").read_text(encoding="utf-8")
    assert "PROVISIONAL" in md and "**31** fragmentos" in md
    for seccion in ("Tabla 2", "Tabla 8", "Tabla 9", "6.4.1", "Tabla 16", "Tabla 19", "Tabla 23", "9.3"):
        assert seccion in md
    assert "| ? " not in md
    assert "\\\\" in (tmp_path / "tablas_informe.tex").read_text(encoding="utf-8")
