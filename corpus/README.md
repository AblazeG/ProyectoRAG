# Corpus normativo (tabla 2 del informe)

La carpeta queda vacía en el repositorio: descarga los documentos en tu equipo y ejecuta

```bash
python -m servicio.ingestar corpus/
```

Cada documento pasa por E5 (formato PDF/HTML/Markdown, tamaño ≤ 20 MB, licencia permitida y
patrones de inyección en el texto extraído). Ningún documento debe contener datos personales.

| `doc_id` | Fuente | Formato | Licencia |
|---|---|---|---|
| `blender_manual` | Blender Manual: modelado de mallas, limpieza, 3D-Print Toolbox, mapeo UV, normales y exportador glTF 2.0 (docs.blender.org/manual) | HTML | CC BY-SA 4.0 |
| `godot_docs` | Documentación de Godot Engine: importación de escenas 3D, mallas, LOD y rendimiento 3D (docs.godotengine.org) | HTML | CC BY 3.0 |
| `gltf_spec` | Especificación glTF 2.0 (registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) | HTML | **Pendiente: verificar** |
| `guia_entrega` | Guía de entrega de modelos 3D con los límites de cada perfil (documento del autor) | Markdown | Propio |
| `rubrica_animacion` | Rúbrica de modelado para un curso de animación 3D (documento del autor) | PDF | Propio |

Mínimo sugerido: 20 documentos o 50 páginas. Si una fuente se divide en varios archivos HTML, dale
a cada uno su propio `doc_id` (por ejemplo `blender_manual_cleanup`) y actualiza los punteros
`norma` de `config/perfiles.yaml`.

## Metadatos: `corpus/fuentes.yaml`

Los PDF y HTML no llevan front matter; declara sus metadatos así:

```yaml
documentos:
  blender_mesh_cleanup.html:
    doc_id: blender_manual
    titulo: Blender Manual — Mesh Clean Up
    licencia: CC-BY-SA-4.0
    perfiles: [animacion, juego_movil, impresion_3d, web_ar]
  godot_3d_performance.html:
    doc_id: godot_docs
    titulo: Godot Engine — Optimizing 3D performance
    licencia: CC-BY-3.0
    perfiles: [juego_movil, web_ar]
  rubrica_animacion.pdf:
    doc_id: rubrica_animacion
    titulo: Rúbrica de modelado para animación 3D
    licencia: propio
    perfiles: [animacion, juego_movil]
```

En Markdown, los mismos campos pueden ir en el front matter (ver `tests/corpus/*.md`).
Licencias aceptadas por defecto (`config/servicio.yaml`): CC-BY-4.0, CC-BY-SA-4.0, CC-BY-3.0,
CC0-1.0, propio, MIT, Apache-2.0 y dominio-publico.

## Punteros `norma` de `config/perfiles.yaml`

Cada regla apunta al documento y la sección que la justifican; ese puntero es la fuente esperada de
la evaluación. Los títulos actuales coinciden con el corpus de prueba en español; **ajústalos a los
títulos reales** después de ingerir (consúltalos en `GET /documentos` o en las fuentes que cita un informe).

## Corpus de prueba

`tests/corpus/` contiene cinco textos **sintéticos**, redactados para las pruebas (no son las fuentes
oficiales), con los mismos `doc_id`. Sirven para las pruebas y para una demostración sin internet:

```bash
MESHAUDIT_PROVEEDOR=falso python -m servicio.ingestar tests/corpus/
```

## Cambiar el modelo de embeddings

El manifiesto del índice guarda el modelo (bge-m3, ADR-02). Si lo cambias, reindexa y recalibra los
umbrales:

```bash
python -m servicio.ingestar corpus/ --reindexar
```
