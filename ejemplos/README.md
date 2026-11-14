# Mallas de ejemplo para demostrar MeshAudit

Modelos públicos descargados el 14 de noviembre de 2026 para la demostración. Ninguno está comprimido
con Draco ni meshopt, así que trimesh los lee bien (ver la incidencia de Draco en
`docs/PRUEBAS_LOCALES.md`).

## Cómo abrir MeshAudit

- **Doble clic en `MeshAudit.command`** (en la raíz del repositorio). Abre Terminal, arranca Ollama, la
  API y la web, y abre `http://localhost:5173`. Al pulsar Enter o cerrar la ventana se detiene.
- **O `app_mac/MeshAudit.app`.** Se queda en el Dock; al salir de la app se detiene. Se regenera con
  `zsh app_mac/crear_app.sh`.

La primera vez, macOS puede pedir permiso para abrir un archivo descargado o un script: clic derecho >
Abrir.

## Qué auditar y qué esperar

Resultados obtenidos con bge-m3, gemma4:e2b y gpt-oss:20b (informes en `informes/`, en JSON y Markdown).

| Archivo | Perfil | Semáforo | Ruta | Hallazgos | Qué demuestra |
|---|---|---|---|---|---|
| `BoxTextured.glb` | Web/AR | verde | sin modelo | — | Malla sana: informe instantáneo sin usar modelo |
| `Avocado.glb` | Web/AR | verde | sin modelo | — | Malla sana con texturas (8 MB, bajo el límite de 10 MB) |
| `spot_impresion.stl` | Impresión 3D | verde | sin modelo | V10 (I) | STL en mm dentro de 1–300 mm; un informativo no cambia el semáforo |
| `spot.obj` | Juego móvil | verde | sin modelo | — | OBJ con UV y bajo el presupuesto de triángulos |
| `DamagedHelmet.glb` | Web/AR | amarillo | rápida | V4 (M), V10 (I) | Hallazgo menor explicado por el modelo rápido |
| `Fox.glb` | Juego móvil | amarillo | rápida | V7 (M), V1 (I), V10 (I) | Escala implausible: 154.7 «m» porque está modelado en centímetros |
| `stanford-bunny.obj` | Juego móvil | rojo | completa | V3 (G), V6 (G) | 69 451 triángulos (límite 20 000) y sin UV |
| `suzanne.obj` | Animación | rojo | completa | V6 (G), V4 (M) | Sin UV y una arista no manifold |
| `teapot.obj` | Animación | rojo | completa | V6 (G), V2 (M), V10 (I) | 100 % triángulos en una malla de deformación |

Ideas para la demostración:

1. Audita `BoxTextured.glb` (verde, sin modelo) y luego `stanford-bunny.obj` en Juego móvil (rojo, ruta
   completa con citas).
2. Repite la misma auditoría: la segunda vez la sirve la caché exacta en milisegundos.
3. En el informe del conejo, pregunta «¿Cómo le pongo UV?» para mostrar las preguntas de seguimiento.
4. Audita `Fox.glb` en Juego móvil y luego en Animación para ver cómo cambian las reglas por perfil.
5. Visualiza cualquier `.glb` en el visor 3D de la web.

Con la caché vacía, la primera auditoría por la ruta completa tarda de 5 a 15 s; las de la ruta rápida,
unos 2 a 5 s.

## Origen y licencias

| Archivo | Fuente | Autor y licencia |
|---|---|---|
| `Avocado.glb` | [KhronosGroup/glTF-Sample-Assets](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Avocado) | Microsoft, CC0 1.0 |
| `BoxTextured.glb` | [KhronosGroup/glTF-Sample-Assets](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/BoxTextured) | Cesium, CC BY 4.0 (logotipo de Cesium como marca) |
| `DamagedHelmet.glb` | [KhronosGroup/glTF-Sample-Assets](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/DamagedHelmet) | theblueturtle_, CC BY-NC 4.0 (solo uso no comercial); conversión de ctxwing, CC BY 4.0 |
| `Fox.glb` | [KhronosGroup/glTF-Sample-Assets](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Fox) | PixelMannen (modelo), tomkranis (rig y animación, CC BY 4.0), @AsoboStudio y @scurest (conversión, CC BY 4.0) |
| `spot.obj` | [alecjacobson/common-3d-test-models](https://github.com/alecjacobson/common-3d-test-models) | Keenan Crane, dominio público (CC0) |
| `spot_impresion.stl` | Derivado de `spot.obj` (escala ×50 a milímetros, con trimesh) | Igual que `spot.obj` |
| `stanford-bunny.obj` | [alecjacobson/common-3d-test-models](https://github.com/alecjacobson/common-3d-test-models) | Stanford Computer Graphics Laboratory; uso de investigación con crédito (Turk y Levoy, 1994) |
| `suzanne.obj` | [alecjacobson/common-3d-test-models](https://github.com/alecjacobson/common-3d-test-models) | Blender Foundation (primitiva de Blender) |
| `teapot.obj` | [alecjacobson/common-3d-test-models](https://github.com/alecjacobson/common-3d-test-models) | Martin Newell (tetera de Utah), uso libre |

Si citas estos modelos en el informe, da el crédito de la tabla. `DamagedHelmet.glb` es solo para uso no
comercial; para un uso académico basta con atribuirlo.
