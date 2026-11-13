"""Mutaciones M1–M5 de las mallas base con Blender (bpy), tabla 3 del informe.

Uso (Blender 4.2 o posterior):
    blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas [--todas]

Para cada ``<nombre>.obj`` de ``mallas_base/`` (cinco mallas CC0 de Kenney,
Poly Haven o propias; sección 2.4) escribe ``<nombre>_base.obj`` y la variante que
le toca en orden alfabético (la primera base, M1; la segunda, M2…), que es la
misma asignación de ``plantillas.py``. Con ``--todas`` aplica M1–M5 a cada base
(cada base debe admitir entonces todas las mutaciones). Cuando el defecto
sobrevive al formato, exporta también GLB, STL y PLY. Después, ``evaluacion/plantillas.py
--bases b1,…,b5`` asigna a cada variante su base (M1 necesita una base cuya
dimensión máxima supere 0.3 unidades) y calcula la línea base:

- M1: n-gons (se disuelven aristas entre quads vecinos) y escala ×1000.
- M2: abrir la malla (se borran caras) y quitar las UV.
- M3: invertir las normales de una región y duplicar vértices (split).
- M4: subdividir hasta superar 100 000 triángulos y crear una arista no
  manifold (aleta); exportación extra en GLB con texturas.
- M5: triangular una zona y crear caras degeneradas (vértice colapsado sobre una
  arista paralela a un eje, para que el área sea exactamente cero).

Tras cada mutación se comprueba que el defecto existe; si no, el script se detiene.

Sin argumentos usa ``evaluacion/mallas_base`` y ``evaluacion/mallas_generadas``.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import bmesh  # type: ignore  # disponible dentro de Blender
import bpy  # type: ignore

SEMILLA = 42
DIR = Path(__file__).resolve().parent
# Formatos donde cada defecto sobrevive (los n-gons solo existen en OBJ).
FORMATOS = {"base": ("obj",), "M1": ("obj",), "M2": ("obj", "glb", "stl", "ply"),
            "M3": ("obj", "glb", "ply"), "M4": ("obj", "glb", "stl", "ply"),
            "M5": ("obj", "glb", "stl", "ply")}


def argumentos() -> tuple[Path, Path]:
    extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    extra = [a for a in extra if a != "--todas"]
    entrada = Path(extra[0]) if extra else DIR / "mallas_base"
    salida = Path(extra[1]) if len(extra) > 1 else DIR / "mallas_generadas"
    salida.mkdir(parents=True, exist_ok=True)
    return entrada, salida


def escena_vacia() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def importar(ruta: Path):
    bpy.ops.wm.obj_import(filepath=str(ruta))
    objetos = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objetos:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objetos[0]
    if len(objetos) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


def exportar(obj, ruta_sin_ext: Path, formatos: tuple[str, ...], normales: bool = True) -> None:
    """``normales=False`` en M3: con normales suavizadas, los vértices separados por
    «split» llevan normales distintas y C5 los trata como costuras de normales (no
    como duplicados), así que el defecto no se vería."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for formato in formatos:
        ruta = str(ruta_sin_ext.with_suffix(f".{formato}"))
        if formato == "obj":
            bpy.ops.wm.obj_export(filepath=ruta, export_selected_objects=True, export_uv=True,
                                  export_normals=normales, export_triangulated_mesh=False,
                                  export_materials=False, apply_modifiers=True)
        elif formato == "glb":
            bpy.ops.export_scene.gltf(filepath=ruta, export_format="GLB", use_selection=True,
                                      export_normals=normales)
        elif formato == "stl":
            bpy.ops.wm.stl_export(filepath=ruta, export_selected_objects=True)
        elif formato == "ply":
            bpy.ops.wm.ply_export(filepath=ruta, export_selected_objects=True, export_uv=True,
                                  export_normals=normales)


def con_bmesh(obj, funcion) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    funcion(bm)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    bpy.context.view_layer.update()  # sin esto, obj.dimensions conserva la caja anterior (modo -b)


def triangulos(bm) -> int:
    return sum(len(f.verts) - 2 for f in bm.faces)


# -- Mutaciones -----------------------------------------------------------------
def m1(obj, rng) -> None:
    def mutar(bm):
        candidatas = [e for e in bm.edges if len(e.link_faces) == 2
                      and all(len(f.verts) == 4 for f in e.link_faces)]
        rng.shuffle(candidatas)
        usadas, aristas = set(), []
        for e in candidatas:
            caras = {f.index for f in e.link_faces}
            if caras & usadas:
                continue
            usadas |= caras
            aristas.append(e)
            if len(aristas) >= max(3, len(bm.faces) // 40):
                break
        bmesh.ops.dissolve_edges(bm, edges=aristas, use_verts=False)  # dos quads -> hexágono
        for v in bm.verts:
            v.co *= 1000.0
    con_bmesh(obj, mutar)


def m2(obj, rng) -> None:
    def mutar(bm):
        caras = list(bm.faces)
        rng.shuffle(caras)
        bmesh.ops.delete(bm, geom=caras[:max(1, len(caras) // 50)], context="FACES_ONLY")
    con_bmesh(obj, mutar)
    while obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers[0])


def _region(bm, rng, proporcion=0.1):
    semilla = rng.choice(list(bm.faces))
    region, frontera = {semilla}, [semilla]
    objetivo = max(4, int(len(bm.faces) * proporcion))
    while frontera and len(region) < objetivo:
        cara = frontera.pop(0)
        for e in cara.edges:
            for vecina in e.link_faces:
                if vecina not in region:
                    region.add(vecina)
                    frontera.append(vecina)
    return list(region)


def m3(obj, rng) -> None:
    def mutar(bm):
        region = _region(bm, rng)
        bmesh.ops.reverse_faces(bm, faces=region)
        otra = _region(bm, rng, 0.03)
        bmesh.ops.split(bm, geom=otra, use_only_faces=False)  # vértices duplicados
    con_bmesh(obj, mutar)


def m4(obj, rng) -> None:
    def mutar(bm):
        while triangulos(bm) <= 100_000:
            bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=1, use_grid_fill=True)
        bm.edges.ensure_lookup_table()
        bm.normal_update()   # tras subdividir, las normales de cara no están recalculadas
        arista = rng.choice([e for e in bm.edges if len(e.link_faces) == 2])
        a, b = arista.verts
        normal = arista.link_faces[0].normal
        punta = bm.verts.new((a.co + b.co) / 2 + normal * (a.co - b.co).length)
        bm.faces.new((a, b, punta))  # tercera cara en la arista: no manifold
    con_bmesh(obj, mutar)


def textura_de_prueba(obj, lado_px: int = 2048) -> None:
    """Material con una textura de ruido (incompresible) para que el GLB con
    texturas incrustadas supere los 10 MB de V11 en Web/AR (tabla 3)."""
    import numpy as np  # Blender incluye numpy
    imagen = bpy.data.images.new("meshaudit_textura", lado_px, lado_px, alpha=False)
    ruido = np.random.default_rng(SEMILLA).random((lado_px * lado_px, 4), dtype=np.float32)
    ruido[:, 3] = 1.0
    imagen.pixels.foreach_set(ruido.ravel())
    imagen.file_format = "PNG"
    imagen.pack()
    material = bpy.data.materials.new("meshaudit_material")
    material.use_nodes = True
    nodos = material.node_tree.nodes
    nodo_imagen = nodos.new("ShaderNodeTexImage")
    nodo_imagen.image = imagen
    principal = nodos.get("Principled BSDF")
    material.node_tree.links.new(nodo_imagen.outputs["Color"], principal.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(material)


def _arista_alineada(a, b) -> bool:
    """Arista paralela a un eje: dos coordenadas idénticas en float32."""
    return sum(a.co[i] == b.co[i] for i in range(3)) >= 2


def m5(obj, rng) -> None:
    """El punto medio de una arista cualquiera no es exactamente colineal en float32 y
    el área queda en ~1e-8, por encima del umbral absoluto de V8 (1e-10). Se colapsa
    sobre aristas paralelas a un eje, donde el punto medio sí es colineal (área 0
    exacta) sin crear vértices coincidentes, que contarían como duplicados."""
    def mutar(bm):
        region = _region(bm, rng, 0.08)
        resultado = bmesh.ops.triangulate(bm, faces=region)
        nuevas = list(resultado["faces"])
        rng.shuffle(nuevas)
        usados = set()
        colapsadas = 0
        for cara in nuevas:
            vs = list(cara.verts)
            giros = [(vs[i], vs[(i + 1) % 3], vs[(i + 2) % 3]) for i in range(3)]
            elegido = next((g for g in giros if _arista_alineada(g[0], g[1])), None)
            if elegido is None or set(vs) & usados:
                continue
            a, b, c = elegido
            c.co = (a.co + b.co) / 2  # colineal con a y b: área cero
            usados |= set(vs)
            colapsadas += 1
            if colapsadas >= 3:
                break
    con_bmesh(obj, mutar)


# -- Comprobaciones: cada variante debe tener su defecto antes de exportarse -----------
def _area(cara) -> float:
    a, b, c = (cara.verts[i].co for i in range(3))
    return (b - a).cross(c - a).length / 2


def comprobar(nombre: str, obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    try:
        dimension = max(obj.dimensions)
        if nombre == "M1":
            ok = any(len(f.verts) > 4 for f in bm.faces) and dimension > 300
        elif nombre == "M2":
            ok = any(e.is_boundary for e in bm.edges) and not obj.data.uv_layers
        elif nombre == "M3":
            posiciones = {tuple(round(x, 6) for x in v.co) for v in bm.verts}
            ok = len(posiciones) < len(bm.verts)          # hay vértices duplicados
        elif nombre == "M4":
            ok = (triangulos(bm) > 100_000
                  and any(len(e.link_faces) > 2 for e in bm.edges))
        elif nombre == "M5":
            ok = any(len(f.verts) == 3 and _area(f) < 1e-10 for f in bm.faces)
        else:
            ok = True
    finally:
        bm.free()
    if not ok:
        raise SystemExit(f"{obj.name}: la mutación {nombre} no produjo el defecto esperado "
                         "(revisa la malla base; tabla 3).")


MUTACIONES = {"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5}


def main() -> None:
    entrada, salida = argumentos()
    bases = sorted(entrada.glob("*.obj"))
    if not bases:
        raise SystemExit(f"No hay mallas .obj en {entrada}")
    todas = "--todas" in sys.argv
    if not todas and len(bases) != len(MUTACIONES):
        raise SystemExit(f"Se esperaban {len(MUTACIONES)} mallas base (una por variante) y hay "
                         f"{len(bases)}; usa --todas para aplicar M1–M5 a cada una.")
    for indice, ruta in enumerate(bases):
        escena_vacia()
        exportar(importar(ruta), salida / f"{ruta.stem}_base", FORMATOS["base"])
        asignadas = MUTACIONES if todas else dict([list(MUTACIONES.items())[indice]])
        for nombre, mutacion in asignadas.items():
            escena_vacia()
            obj = importar(ruta)
            mutacion(obj, random.Random(f"{SEMILLA}-{ruta.stem}-{nombre}"))
            comprobar(nombre, obj)
            exportar(obj, salida / f"{ruta.stem}_{nombre}", FORMATOS[nombre],
                     normales=nombre != "M3")
            if nombre == "M4":
                textura_de_prueba(obj)
                exportar(obj, salida / f"{ruta.stem}_M4_texturas", ("glb",))
            print(f"✔ {ruta.stem} {nombre}")


if __name__ == "__main__":
    main()
