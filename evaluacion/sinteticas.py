"""Mallas de evaluación sin Blender (modo falso), con la misma estructura que
la sección 2.4 y la tabla 3 del informe: cinco mallas base y una variante por
base, nombradas como las produce ``mutar_blender.py`` (``<base>_<variante>``).

| Base  | Imita                                  | Variante | Mutaciones (tabla 3)                          |
|-------|----------------------------------------|----------|-----------------------------------------------|
| base1 | modelo propio de quads, 20 unidades    | M1       | n-gons y escala ×1000 (base > 0.3 unidades)   |
| base2 | pieza pequeña de 0.5 unidades          | M2       | abrir la malla y quitar las UV                |
| base3 | modelo de Kenney (triangulado)         | M3       | invertir normales de una región y duplicar vértices |
| base4 | escaneo denso (43 200 triángulos)      | M4       | subdividir > 100 000 triángulos y arista no manifold; GLB con texturas > 10 MB |
| base5 | modelo propio de quads                 | M5       | triangular una zona amplia y crear caras degeneradas |

En el Mac se usan las mallas reales de ``mallas_base/`` y el script de Blender.
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np

DESTINO = Path(__file__).resolve().parent / "mallas_generadas"
BASES = ["base1", "base2", "base3", "base4", "base5"]
VARIANTE_DE_BASE = {"base1": "M1", "base2": "M2", "base3": "M3", "base4": "M4", "base5": "M5"}


def cubo_rejilla(n: int, lado: float = 20.0):
    """Cubo de quads n×n por cara, con vértices compartidos (normales hacia fuera)."""
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
                    if (signo == 1.0) == (eje == 1):
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


def triangular(caras):
    return [[c[0], c[i], c[i + 1]] for c in caras for i in range(1, len(c) - 1)]


def _ngons(caras, cuantos: int):
    """Une pares de quads vecinos en hexágonos encadenando su contorno."""
    resto = list(caras)
    nuevos = []
    for _ in range(cuantos):
        a = resto.pop(0)
        k = next((i for i, b in enumerate(resto) if len(set(a) & set(b)) == 2), None)
        if k is None:
            nuevos.append(a)
            continue
        b = resto.pop(k)
        aristas = [(c[i], c[(i + 1) % 4]) for c in (a, b) for i in range(4)]
        contorno = {u: w for u, w in aristas if (w, u) not in aristas}
        inicio = next(iter(contorno))
        hexagono = [inicio]
        while contorno[hexagono[-1]] != inicio:
            hexagono.append(contorno[hexagono[-1]])
        nuevos.append(hexagono)
    return nuevos + resto


def _glb_con_textura(obj: Path, destino: Path, lado_px: int = 2048) -> Path:
    """GLB con una textura de ruido incrustada (incompresible) para superar 10 MB (V11)."""
    import trimesh
    from PIL import Image

    malla = trimesh.load(obj, process=False, force="mesh")
    rng = np.random.default_rng(42)
    imagen = Image.fromarray(rng.integers(0, 255, (lado_px, lado_px, 3), dtype=np.uint8))
    uv = malla.visual.uv if getattr(malla.visual, "uv", None) is not None else np.zeros((len(malla.vertices), 2))
    material = trimesh.visual.material.PBRMaterial(baseColorTexture=imagen)
    malla.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    destino.write_bytes(malla.export(file_type="glb"))
    return destino


def generar(destino: Path = DESTINO, con_glb_texturas: bool = True) -> dict[str, Path]:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    rutas: dict[str, Path] = {}

    # Líneas base
    v1, f1 = cubo_rejilla(6, 20.0)
    v2, f2 = cubo_rejilla(4, 0.5)
    v3, f3 = cubo_rejilla(6, 2.0)
    f3 = triangular(f3)                               # como un modelo de Kenney
    v4, f4 = cubo_rejilla(60, 1.5)                    # 43 200 triángulos: un «escaneo»
    v5, f5 = cubo_rejilla(8, 1.0)
    for nombre, (v, f) in {"base1": (v1, f1), "base2": (v2, f2), "base3": (v3, f3),
                           "base4": (v4, f4), "base5": (v5, f5)}.items():
        rutas[f"{nombre}_base"] = escribir(destino / f"{nombre}_base.obj", v, f)

    # M1 sobre base1: n-gons y escala ×1000
    rutas["base1_M1"] = escribir(destino / "base1_M1.obj", [[c * 1000 for c in p] for p in v1],
                                 _ngons(f1, 4))
    # M2 sobre base2: abrir la malla y quitar las UV
    rutas["base2_M2"] = escribir(destino / "base2_M2.obj", v2, f2[2:], uv=False)
    # M3 sobre base3: invertir las normales de una región y duplicar vértices
    region = [c[::-1] for c in f3[:12]] + f3[12:]
    inicio = len(v3) + 1
    v3m = v3 + [list(v3[i - 1]) for i in region[-1]]
    region[-1] = list(range(inicio, inicio + 3))
    rutas["base3_M3"] = escribir(destino / "base3_M3.obj", v3m, region)
    # M4 sobre base4: subdividir hasta superar 100 000 triángulos y crear una arista no manifold
    v4m, f4m = cubo_rejilla(130, 1.5)
    a, b = f4m[0][0], f4m[0][1]
    v4m = v4m + [[-0.5, -0.5, -0.5]]
    rutas["base4_M4"] = escribir(destino / "base4_M4.obj", v4m, f4m + [[a, b, len(v4m)]])
    # M5 sobre base5: triangular una cara entera del cubo y colapsar vértices (área cero)
    zona = 8 * 8
    tri = triangular(f5[:zona])
    v5m = [list(p) for p in v5]
    for k in (10, 30, 50):
        a, b, c = tri[k]
        v5m[c - 1] = [(v5m[a - 1][i] + v5m[b - 1][i]) / 2 for i in range(3)]
    rutas["base5_M5"] = escribir(destino / "base5_M5.obj", v5m, tri + f5[zona:])

    # Exportaciones extra cuando el defecto sobrevive (GLB, STL y PLY)
    try:
        import trimesh
        for nombre in ("base2_M2", "base3_M3", "base5_M5"):
            m = trimesh.load(rutas[nombre], process=False, force="mesh")
            for ext in ("glb", "stl", "ply"):
                m.export(destino / f"{nombre}.{ext}")
        if con_glb_texturas:
            rutas["base4_M4_texturas"] = _glb_con_textura(rutas["base4_M4"],
                                                          destino / "base4_M4_texturas.glb")
    except Exception as exc:  # noqa: BLE001
        print(f"aviso: exportaciones extra omitidas ({exc})")
    return rutas


if __name__ == "__main__":
    for k, r in generar().items():
        print(k, r, f"{r.stat().st_size / 1e6:.1f} MB")
