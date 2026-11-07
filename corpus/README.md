# Corpus normativo

Esta carpeta está vacía en el repositorio: los documentos se descargan en tu equipo
(la sesión en la nube no tiene acceso a internet) y se ingieren con

```bash
python -m servicio.ingestar corpus/
```

Cada documento pasa por E5: formato (PDF, HTML o Markdown), tamaño (≤ 20 MB),
licencia permitida e inyección tras extraer el texto.

## Qué poner

Las reglas de `config/perfiles.yaml` apuntan (campo `norma`) a cuatro `doc_id`.
Para que la evaluación encuentre la fuente esperada, usa esos identificadores y
títulos de sección parecidos, o ajusta los punteros de `perfiles.yaml`.

| `doc_id` | Fuente propuesta | Licencia (verifícala antes de usarla) | Secciones que cubre |
|---|---|---|---|
| `blender_manual` | Blender Manual: Modeling › Meshes (Clean Up, Normals, Select All by Trait, UV Unwrap, Merge by Distance), docs.blender.org | CC BY-SA 4.0 | Topología para deformación, Limpieza de geometría no manifold, Desenvolvimiento UV, Disolver geometría degenerada, Orientación de normales, Fusionar vértices por distancia |
| `gltf_spec` | Especificación glTF 2.0 de Khronos (unidades, TEXCOORD_n), registry.khronos.org | Revisa la licencia de la especificación (Khronos publica partes bajo CC BY 4.0) | Unidades y escala, Coordenadas de textura |
| `guia_tiempo_real` | Khronos 3D Commerce «Real-time Asset Creation Guidelines» | CC BY 4.0 (verificar) | Presupuesto de polígonos, Tamaño de archivo para web |
| `guia_impresion3d` | Blender Manual: complemento 3D Print Toolbox, o una guía abierta de preparación para impresión 3D (por ejemplo, Wikibooks) | CC BY-SA 4.0 (verificar) | Mallas cerradas, Geometría no manifold, Escala y volumen de impresión, Caras degeneradas, Normales invertidas |

Licencias aceptadas por defecto (`config/servicio.yaml` → `guardrails.licencias_permitidas`):
CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0, MIT, Apache-2.0 y dominio-publico.

## Metadatos: `fuentes.yaml`

Los PDF y HTML no llevan front matter. Declara sus metadatos en `corpus/fuentes.yaml`:

```yaml
documentos:
  blender_mesh_cleanup.html:
    doc_id: blender_manual
    titulo: Blender Manual — Mesh Clean Up
    licencia: CC-BY-SA-4.0
    perfiles: [animacion, juego_movil, impresion_3d, web_ar]
  gltf-2.0.pdf:
    doc_id: gltf_spec
    titulo: glTF 2.0 Specification
    licencia: CC-BY-4.0
    perfiles: [animacion, juego_movil, web_ar]
```

En Markdown, los mismos campos pueden ir en el front matter (ver `tests/corpus/*.md`).
Si varios archivos comparten un `doc_id`, cada ingesta reemplaza la anterior: dales
identificadores distintos (`blender_manual_cleanup`, `blender_manual_normals`, …) y
actualiza los punteros de `perfiles.yaml`.

## Corpus de prueba

`tests/corpus/` contiene cuatro documentos **sintéticos** (CC0, redactados para las
pruebas; no son las fuentes oficiales) con los mismos `doc_id` y secciones. Sirven para
las pruebas y para una demostración sin internet:

```bash
python -m servicio.ingestar tests/corpus/
```

## Cambiar el modelo de embeddings

El manifiesto del índice guarda el modelo con que se vectorizó. Si cambias
`modelos.embeddings`, reindexa:

```bash
python -m servicio.ingestar corpus/ --reindexar
```
