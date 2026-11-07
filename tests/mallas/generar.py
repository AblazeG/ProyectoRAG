"""Mallas sintéticas de prueba, escritas a mano en OBJ para tener quads y
n-gons (trimesh triangula al leer). Uso: ``python -m tests.mallas.generar``."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

DIRECTORIO = Path(__file__).resolve().parent

CUBO_V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
          (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
CUBO_F = [[1, 4, 3, 2], [5, 6, 7, 8], [1, 2, 6, 5],
          [2, 3, 7, 6], [3, 4, 8, 7], [4, 1, 5, 8]]  # quads, normales hacia fuera


def escribir_obj(ruta: Path, vertices, caras, uv: bool = True) -> Path:
    lineas = ["# malla sintética de MeshAudit"]
    lineas += [f"v {x:.9g} {y:.9g} {z:.9g}" for x, y, z in vertices]
    if uv:
        lineas += [f"vt {(i % 4) / 3:.6f} {(i // 4) / 3:.6f}" for i in range(len(vertices))]
        lineas += ["f " + " ".join(f"{i}/{i}" for i in cara) for cara in caras]
    else:
        lineas += ["f " + " ".join(str(i) for i in cara) for cara in caras]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def cubo(escala: float = 1.0):
    return [tuple(c * escala for c in v) for v in CUBO_V], [list(f) for f in CUBO_F]


def triangular(caras):
    return [[c[0], c[i], c[i + 1]] for c in caras for i in range(1, len(c) - 1)]


def prisma_pentagonal():
    vertices = []
    for z in (0, 1):
        for k in range(5):
            a = 2 * math.pi * k / 5
            vertices.append((0.5 * math.cos(a), 0.5 * math.sin(a), z))
    inferior = [5, 4, 3, 2, 1]
    superior = [6, 7, 8, 9, 10]
    lados = [[k + 1, (k + 1) % 5 + 1, (k + 1) % 5 + 6, k + 6] for k in range(5)]
    return vertices, [inferior, superior] + lados


def generar(directorio: Path = DIRECTORIO) -> dict[str, Path]:
    d = Path(directorio)
    d.mkdir(parents=True, exist_ok=True)
    rutas = {}
    v, f = cubo()
    rutas["cubo"] = escribir_obj(d / "cubo.obj", v, f)
    rutas["cubo_sin_uv"] = escribir_obj(d / "cubo_sin_uv.obj", v, f, uv=False)
    rutas["cubo_triangulado"] = escribir_obj(d / "cubo_triangulado.obj", v, triangular(f))
    rutas["cubo_abierto"] = escribir_obj(d / "cubo_abierto.obj", v, f[:1] + f[2:])
    rutas["cubo_aleta"] = escribir_obj(  # arista 1-2 compartida por 3 caras
        d / "cubo_aleta.obj", v + [(0.5, -0.5, -0.5)], f + [[1, 2, 9]])
    rutas["cubo_degenerado"] = escribir_obj(  # triángulo aislado de área cero
        d / "cubo_degenerado.obj", v + [(2, 0, 0), (3, 0, 0), (4, 0, 0)], f + [[9, 10, 11]])
    rutas["cubo_cara_invertida"] = escribir_obj(
        d / "cubo_cara_invertida.obj", v, [f[0], f[1][::-1]] + f[2:])
    rutas["cubo_invertido"] = escribir_obj(
        d / "cubo_invertido.obj", v, [c[::-1] for c in f])
    duplicados = v + [v[4], v[5], v[6], v[7]]
    f_dup = [f[0], [9, 10, 11, 12]] + f[2:]
    rutas["cubo_duplicados"] = escribir_obj(d / "cubo_duplicados.obj", duplicados, f_dup, uv=False)
    v1000, _ = cubo(1000.0)
    rutas["cubo_x1000"] = escribir_obj(d / "cubo_x1000.obj", v1000, f)
    v20, _ = cubo(20.0)
    rutas["cubo_20mm"] = escribir_obj(d / "cubo_20mm.obj", v20, f)
    vp, fp = prisma_pentagonal()
    rutas["prisma_ngon"] = escribir_obj(d / "prisma_ngon.obj", vp, fp)
    return rutas


def esfera(subdivisiones: int):
    """Arreglos (vértices, caras) de una icoesfera, para presupuestos (V3)."""
    import trimesh
    m = trimesh.creation.icosphere(subdivisions=subdivisiones)
    return np.asarray(m.vertices), np.asarray(m.faces)


if __name__ == "__main__":
    for nombre, ruta in generar().items():
        print(nombre, ruta)
