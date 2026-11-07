"""Mutaciones M1–M5 de las mallas base con Blender (bpy).

Uso (Blender 4.2 o posterior):
    blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas

Para cada ``<nombre>.obj`` de ``mallas_base/`` escribe ``<nombre>_base.obj`` y
``<nombre>_M1.obj`` … ``<nombre>_M5.obj``; cuando el defecto sobrevive al
formato, exporta también GLB, STL y PLY:

- M1: n-gons (se disuelven aristas entre quads vecinos) y escala ×1000.
- M2: abrir la malla (se borran caras) y quitar las UV.
- M3: invertir las normales de una región y duplicar vértices (split).
- M4: subdividir hasta superar 100 000 triángulos y crear una arista no
  manifold (aleta); exportación extra en GLB con texturas.
- M5: triangular una zona y crear caras degeneradas (vértice colapsado).

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


def exportar(obj, ruta_sin_ext: Path, formatos: tuple[str, ...]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for formato in formatos:
        ruta = str(ruta_sin_ext.with_suffix(f".{formato}"))
        if formato == "obj":
            bpy.ops.wm.obj_export(filepath=ruta, export_selected_objects=True, export_uv=True,
                                  export_normals=True, export_triangulated_mesh=False,
                                  export_materials=False, apply_modifiers=True)
        elif formato == "glb":
            bpy.ops.export_scene.gltf(filepath=ruta, export_format="GLB", use_selection=True)
        elif formato == "stl":
            bpy.ops.wm.stl_export(filepath=ruta, export_selected_objects=True)
        elif formato == "ply":
            bpy.ops.wm.ply_export(filepath=ruta, export_selected_objects=True, export_uv=True)


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
        arista = rng.choice([e for e in bm.edges if len(e.link_faces) == 2])
        a, b = arista.verts
        normal = arista.link_faces[0].normal
        punta = bm.verts.new((a.co + b.co) / 2 + normal * (a.co - b.co).length)
        bm.faces.new((a, b, punta))  # tercera cara en la arista: no manifold
    con_bmesh(obj, mutar)


def textura_de_prueba(obj) -> None:
    """Material con una imagen empaquetada para la exportación GLB con texturas."""
    imagen = bpy.data.images.new("meshaudit_textura", 1024, 1024)
    imagen.generated_type = "UV_GRID"
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


def m5(obj, rng) -> None:
    def mutar(bm):
        region = _region(bm, rng, 0.08)
        resultado = bmesh.ops.triangulate(bm, faces=region)
        nuevas = resultado["faces"]
        usados = set()
        colapsadas = 0
        for cara in nuevas:
            a, b, c = cara.verts
            if {a, b, c} & usados:
                continue
            c.co = (a.co + b.co) / 2  # el triángulo queda con área cero
            usados |= {a, b, c}
            colapsadas += 1
            if colapsadas >= 3:
                break
    con_bmesh(obj, mutar)


MUTACIONES = {"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5}


def main() -> None:
    entrada, salida = argumentos()
    bases = sorted(entrada.glob("*.obj"))
    if not bases:
        raise SystemExit(f"No hay mallas .obj en {entrada}")
    for ruta in bases:
        escena_vacia()
        exportar(importar(ruta), salida / f"{ruta.stem}_base", FORMATOS["base"])
        for nombre, mutacion in MUTACIONES.items():
            escena_vacia()
            obj = importar(ruta)
            mutacion(obj, random.Random(f"{SEMILLA}-{ruta.stem}-{nombre}"))
            exportar(obj, salida / f"{ruta.stem}_{nombre}", FORMATOS[nombre])
            if nombre == "M4":
                textura_de_prueba(obj)
                exportar(obj, salida / f"{ruta.stem}_M4_texturas", ("glb",))
            print(f"✔ {ruta.stem} {nombre}")


if __name__ == "__main__":
    main()
