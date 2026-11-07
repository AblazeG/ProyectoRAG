"""Mallas de evaluación sin Blender (modo falso): línea base y mutaciones M1–M5.

En el Mac se usan las mallas reales de ``mallas_base/`` mutadas con
``mutar_blender.py``; aquí se generan equivalentes con numpy para que
``run_eval.py`` y los experimentos corran en la nube.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

DESTINO = Path(__file__).resolve().parent / "mallas_generadas"


def cubo_rejilla(n: int, lado: float = 20.0):
    """Cubo de quads n×n por cara, con vértices compartidos y UV por vértice."""
    indice: dict[tuple, int] = {}
    vertices: list[tuple] = []

    def v(p):
        clave = tuple(np.round(p, 9))
        if clave not in indice:
            indice[clave] = len(vertices)
            vertices.append(clave)
        return indice[clave] + 1

    caras = []
    t = np.linspace(0, 1, n + 1)
    for eje in range(3):
        for signo in (0.0, 1.0):
            u_eje, w_eje = [e for e in range(3) if e != eje]
            for i in range(n):
                for j in range(n):
                    esquinas = []
                    for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                        p = np.zeros(3)
                        p[eje], p[u_eje], p[w_eje] = signo, t[a], t[b]
                        esquinas.append(v(p * lado))
                    if (signo == 1.0) == (eje == 1):  # orientación hacia fuera
                        esquinas.reverse()
                    caras.append(esquinas)
    return [list(x) for x in vertices], caras


def escribir(ruta: Path, vertices, caras, uv=True):
    arr = np.asarray(vertices, float)
    mn, mx = arr.min(0), arr.max(0)
    span = np.where(mx - mn == 0, 1, mx - mn)
    lineas = [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in arr]
    if uv:
        uvs = (arr - mn) / span
        lineas += [f"vt {a:.6f} {b:.6f}" for a, b in uvs[:, :2] * 0.5 + uvs[:, 1:] * 0.5]
        lineas += ["f " + " ".join(f"{i}/{i}" for i in c) for c in caras]
    else:
        lineas += ["f " + " ".join(str(i) for i in c) for c in caras]
    ruta.write_text("\n".join(lineas) + "\n")
    return ruta


def _ngon(caras):
    """Une dos quads vecinos en un hexágono (n-gon) encadenando su contorno."""
    a = caras[0]
    for k, b in enumerate(caras[1:], start=1):
        if len(set(a) & set(b)) == 2:
            break
    else:
        return caras
    aristas = [(c[i], c[(i + 1) % 4]) for c in (a, b) for i in range(4)]
    contorno = {u: v for u, v in aristas if (v, u) not in aristas}
    inicio = next(iter(contorno))
    hexagono = [inicio]
    while contorno[hexagono[-1]] != inicio:
        hexagono.append(contorno[hexagono[-1]])
    resto = [c for i, c in enumerate(caras) if i not in (0, k)]
    return [hexagono] + resto


def generar(destino: Path = DESTINO, n: int = 6) -> dict[str, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    v, f = cubo_rejilla(n)
    rutas = {"base": escribir(destino / "base.obj", v, f)}
    # M1: n-gons y escala ×1000
    rutas["M1"] = escribir(destino / "M1.obj", [[c * 1000 for c in p] for p in v], _ngon(f))
    # M2: abrir la malla y quitar UV
    rutas["M2"] = escribir(destino / "M2.obj", v, f[1:], uv=False)
    # M3: invertir las normales de una región y duplicar vértices
    region = [c[::-1] for c in f[:n]] + f[n:]
    dup_inicio = len(v) + 1
    v3 = v + [list(v[i - 1]) for i in region[-1]]
    region[-1] = list(range(dup_inicio, dup_inicio + 4))
    rutas["M3"] = escribir(destino / "M3.obj", v3, region)
    # M4: subdividir hasta superar 100 000 triángulos y crear una arista no manifold
    v4, f4 = cubo_rejilla(130)
    a, b = f4[0][0], f4[0][1]
    v4 = v4 + [[-5.0, -5.0, -5.0]]
    rutas["M4"] = escribir(destino / "M4.obj", v4, f4 + [[a, b, len(v4)]])
    # M5: triangular una zona y crear caras degeneradas
    tri = [[c[0], c[1], c[2]] for c in f[:n * 2]] + [[c[0], c[2], c[3]] for c in f[:n * 2]]
    v5 = [list(p) for p in v]
    a, b, c = tri[n + 1]  # colapsar un vértice sobre la arista opuesta: área cero, malla cerrada
    v5[c - 1] = [(v5[a - 1][i] + v5[b - 1][i]) / 2 for i in range(3)]
    rutas["M5"] = escribir(destino / "M5.obj", v5, tri + f[n * 2:])
    try:  # exportaciones extra (GLB, STL, PLY) cuando el defecto sobrevive
        import trimesh
        for nombre in ("M3", "M4", "M5"):
            m = trimesh.load(rutas[nombre], process=False, force="mesh")
            for ext in ("glb", "stl", "ply"):
                m.export(destino / f"{nombre}.{ext}")
    except Exception:  # noqa: BLE001
        pass
    return rutas


if __name__ == "__main__":
    for k, r in generar().items():
        print(k, r)
