"""C5: analizador determinista. Cada verificación tiene un caso que pasa y otro que falla."""
from pathlib import Path

import numpy as np
import pytest
import trimesh

from servicio.contexto.herramientas import Analizador, analizar_malla, calcular_semaforo
from servicio.contexto.perfiles import cargar_perfiles
from servicio.datos.mallas import LectorTrimesh
from servicio.dominio import MallaCruda, MallaDemasiadoCompleja
from tests.mallas.generar import esfera, generar

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = cargar_perfiles(RAIZ / "config" / "perfiles.yaml")
MALLAS = generar()
LECTOR = LectorTrimesh()


def analizar(nombre, perfil):
    return analizar_malla(LECTOR.leer(MALLAS[nombre]), CATALOGO.obtener(perfil))


def ids(resultado):
    return {h.verificacion: h.gravedad for h in resultado.hallazgos}


def test_perfiles_cargan_cuatro_claves_y_unidades():
    assert set(CATALOGO.perfiles) == {"animacion", "juego_movil", "impresion_3d", "web_ar"}
    assert CATALOGO.obtener("impresion_3d").unidad == "mm"
    assert all(CATALOGO.obtener(p).unidad == "m" for p in ("animacion", "juego_movil", "web_ar"))
    for perfil in CATALOGO.perfiles.values():
        for regla in perfil.reglas.values():
            assert regla.norma and regla.norma["documento"] and regla.norma["seccion"]


def test_cubo_limpio_es_verde_en_animacion():
    r = analizar("cubo", "animacion")
    assert r.hallazgos == [] and r.semaforo == "verde"
    assert r.metricas["dimension_max"] == 1.0 and r.metricas["unidad"] == "m"
    assert r.metricas["pct_ngons"] == 0 and r.metricas["cerrada"]


def test_v1_ngons():
    assert "V1" not in ids(analizar("cubo", "animacion"))
    r = analizar("prisma_ngon", "animacion")
    assert ids(r)["V1"] == "grave" and r.semaforo == "rojo"
    assert r.metricas["pct_ngons"] == pytest.approx(100 * 2 / 7, abs=1e-3)
    # En juego móvil es informativo y no cuenta para el semáforo.
    m = analizar("prisma_ngon", "juego_movil")
    assert ids(m)["V1"] == "informativo" and m.semaforo == "verde"


def test_v2_triangulos_en_deformacion():
    assert "V2" not in ids(analizar("cubo", "animacion"))
    r = analizar("cubo_triangulado", "animacion")
    assert ids(r)["V2"] == "menor" and r.semaforo == "amarillo"


def test_v1_v2_no_medibles_fuera_de_obj(tmp_path):
    m = trimesh.load(MALLAS["cubo"], process=False, force="mesh")
    for ext in ("glb", "stl", "ply"):
        ruta = tmp_path / f"cubo.{ext}"
        m.export(ruta)
        malla = LECTOR.leer(ruta)
        assert malla.lados_por_cara is None
        r = analizar_malla(malla, CATALOGO.obtener("animacion"))
        assert r.metricas["pct_ngons"] == "no medible"
        assert {"V1", "V2"} <= set(r.no_medibles)
        assert all(h.gravedad == "informativo" for h in r.hallazgos if h.tipo == "no_medible")


def _malla(vertices, caras, **extra):
    datos = dict(vertices=np.asarray(vertices, float), caras=np.asarray(caras),
                 uv=np.zeros((len(vertices), 2)), normales=None, lados_por_cara=None,
                 formato="ply", tamano_bytes=1000)
    datos.update(extra)
    return MallaCruda(**datos)


def test_v3_presupuesto():
    v, f = esfera(4)  # 5 120 triángulos
    assert "V3" not in ids(analizar_malla(_malla(v, f), CATALOGO.obtener("juego_movil")))
    v, f = esfera(6)  # 81 920 triángulos
    assert ids(analizar_malla(_malla(v, f), CATALOGO.obtener("juego_movil")))["V3"] == "grave"
    assert "V3" not in ids(analizar_malla(_malla(v, f), CATALOGO.obtener("web_ar")))
    v, f = esfera(7)  # 327 680 triángulos
    assert ids(analizar_malla(_malla(v, f), CATALOGO.obtener("web_ar")))["V3"] == "menor"


def test_v4_no_manifold():
    assert "V4" not in ids(analizar("cubo", "impresion_3d"))
    r = analizar("cubo_aleta", "impresion_3d")
    assert r.metricas["aristas_no_manifold"] == 1 and ids(r)["V4"] == "grave"
    assert ids(analizar("cubo_aleta", "web_ar"))["V4"] == "menor"


def test_v5_malla_cerrada():
    assert "V5" not in ids(analizar("cubo_20mm", "impresion_3d"))
    r = analizar("cubo_abierto", "impresion_3d")
    assert ids(r)["V5"] == "grave" and not r.metricas["cerrada"]
    assert "V5" not in ids(analizar("cubo_abierto", "animacion"))


def test_v6_uv():
    assert "V6" not in ids(analizar("cubo", "web_ar"))
    assert ids(analizar("cubo_sin_uv", "web_ar"))["V6"] == "grave"


def test_v7_escala_en_unidad_del_perfil():
    assert "V7" not in ids(analizar("cubo", "animacion"))
    assert ids(analizar("cubo_x1000", "animacion"))["V7"] == "menor"
    assert ids(analizar("cubo_x1000", "web_ar"))["V7"] == "grave"
    assert "V7" not in ids(analizar("cubo_20mm", "impresion_3d"))
    assert ids(analizar("cubo_x1000", "impresion_3d"))["V7"] == "menor"  # 1000 mm > 300 mm
    # GLB está en metros: un cubo de 0.02 m son 20 mm.
    malla = _malla(np.array(trimesh.creation.box().vertices) * 0.02,
                   trimesh.creation.box().faces, formato="glb")
    r = analizar_malla(malla, CATALOGO.obtener("impresion_3d"))
    assert r.metricas["dimension_max"] == pytest.approx(20.0) and "V7" not in ids(r)


def test_v8_caras_degeneradas():
    assert "V8" not in ids(analizar("cubo", "impresion_3d"))
    r = analizar("cubo_degenerado", "impresion_3d")
    assert r.metricas["caras_degeneradas"] == 1 and ids(r)["V8"] == "grave"
    assert ids(analizar("cubo_degenerado", "animacion"))["V8"] == "menor"


def test_v9_normales():
    assert "V9" not in ids(analizar("cubo_20mm", "impresion_3d"))
    r = analizar("cubo_cara_invertida", "animacion")
    assert not r.metricas["normales_consistentes"] and ids(r)["V9"] == "menor"
    r = analizar("cubo_invertido", "impresion_3d")
    assert r.metricas["normales_consistentes"] and r.metricas["volumen_con_signo"] < 0
    assert ids(r)["V9"] == "grave"


def test_v10_vertices_duplicados_en_malla_sin_procesar():
    r = analizar("cubo", "impresion_3d")
    assert r.metricas["vertices_duplicados"] == 0
    r = analizar("cubo_duplicados", "impresion_3d")
    assert r.metricas["vertices_duplicados"] == 4 and ids(r)["V10"] == "menor"
    assert r.metricas["cerrada"]  # V4, V5 y V9 se calculan sobre la copia fusionada
    assert ids(analizar("cubo_duplicados", "animacion"))["V10"] == "informativo"


def test_v10_costuras_uv_no_son_duplicados(tmp_path):
    obj = tmp_path / "costura.obj"
    texto = MALLAS["cubo"].read_text().splitlines()
    vt = ["vt 0 0", "vt 1 0", "vt 1 1", "vt 0 1"]
    caras = [l for l in texto if l.startswith("f ")]
    nuevas = ["f " + " ".join(f"{t.split('/')[0]}/{k + 1}" for k, t in enumerate(c.split()[1:]))
              for c in caras]
    obj.write_text("\n".join([l for l in texto if l.startswith("v ")] + vt + nuevas))
    malla = LECTOR.leer(obj)
    assert len(malla.vertices) > 8  # trimesh separa vértices en las costuras
    assert analizar_malla(malla, CATALOGO.obtener("impresion_3d")).metricas["vertices_duplicados"] == 0


def test_v11_tamano_archivo():
    v, f = esfera(1)
    assert "V11" not in ids(analizar_malla(_malla(v, f), CATALOGO.obtener("web_ar")))
    grande = _malla(v, f, tamano_bytes=11 * 1024 * 1024)
    assert ids(analizar_malla(grande, CATALOGO.obtener("web_ar")))["V11"] == "menor"


def test_limite_de_caras():
    v, f = esfera(1)
    with pytest.raises(MallaDemasiadoCompleja):
        analizar_malla(_malla(v, f), CATALOGO.obtener("web_ar"), max_caras=10)


def test_semaforo_ignora_informativos():
    from servicio.dominio import Hallazgo
    info = Hallazgo("h-V10", "V10", "vertices_duplicados", "informativo", 4, "0", "", "")
    menor = Hallazgo("h-V4", "V4", "aristas_no_manifold", "menor", 1, "0", "", "")
    grave = Hallazgo("h-V6", "V6", "sin_uv", "grave", False, "", "", "")
    assert calcular_semaforo([info]) == "verde"
    assert calcular_semaforo([info, menor]) == "amarillo"
    assert calcular_semaforo([menor, grave]) == "rojo"


def test_analizador_con_lector():
    analizador = Analizador(LECTOR, CATALOGO)
    r = analizador.analizar(MALLAS["prisma_ngon"], "animacion")
    assert r.semaforo == "rojo" and r.hallazgos[0].consulta
