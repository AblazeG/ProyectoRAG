# Informe de auditoría MeshAudit — stanford-bunny.obj

- **Perfil:** Juego móvil
- **Semáforo:** rojo
- **Ruta:** completa · **Modelo:** gpt-oss:20b · **Caché:** exacta
- **Dimensión máxima:** 0.155699 m · **Caras:** 69451 · **Triángulos:** 69451

Juego móvil: 2 hallazgos (2 graves)

## Hallazgos

### h1 · V3 · Presupuesto de triángulos (grave)

- Medido: `69451 triángulos` · Límite: `≤ 20000 triángulos`

Sin norma aplicable en el corpus

### h2 · V6 · La malla no tiene coordenadas UV por vértice (grave)

- Medido: `sin UV` · Límite: `UV por vértice`

En un juego móvil, la ausencia de coordenadas UV por vértice impide que las texturas se asignen correctamente a las caras de la malla, lo que puede provocar que las imágenes no se muestren o se distorsionen durante la renderización en tiempo real. Según el manual de Blender, cada cara debe tener coordenadas UV que definan cómo se mapeará una imagen a la cara, y estas coordenadas son esenciales para el procesamiento final y la visualización en la Vista 3D [blender_manual_uv_intro:acerca-de-las-uv#2][blender_manual_uv_intro:acerca-de-las-uv#4]. Además, la exportación a glTF 2.0 requiere que las coordenadas UV estén presentes para que los nodos de textura de imagen funcionen correctamente, ya que el nodo Mapa UV y el nodo Mapeo dependen de ellas para aplicar transformaciones y exportar la textura [blender_manual_gltf:materiales-exportados#42].

**Pasos de corrección:**
1. Asegurarse de que la malla tenga un material con un nodo de textura de imagen seleccionado en el Shader Editor, lo que permite que el sistema genere automáticamente coordenadas UV para cada cara [blender_manual_uv:opciones-6#7][blender_manual_uv:opciones-8#3].
2. Utilizar la herramienta de desempaquetado UV (UV Unwrap) en Blender para crear coordenadas UV por vértice, garantizando que cada cara tenga las cuatro coordenadas UV necesarias para mapear la textura correctamente [blender_manual_uv_intro:acerca-de-las-uv#2].
3. Verificar que las coordenadas UV generadas no excedan los límites de la textura (out-of-bounds) y, si es necesario, aplicar la opción de mover UVs fuera de rango al borde más cercano para evitar artefactos visuales [blender_manual_uv:opciones-6#7][blender_manual_uv:opciones-8#3].
4. Revisar la configuración de exportación glTF para asegurarse de que la extensión KHR_texture_transform esté habilitada y que los valores de escala, posición y rotación se apliquen correctamente a las coordenadas UV exportadas [blender_manual_gltf:materiales-exportados#42].

> **Fuente:** blender_manual_uv_intro — Acerca de las UV (`blender_manual_uv_intro:acerca-de-las-uv#2`, puntaje 0.6384)
>
> de la malla 3D. Es posible pensar en un mapa UV como si se proyectara la superficie del modelo 3D sobre una imagen 2D.
> 
> Cada cara de una malla podrá tener varias texturas UV. Cada textura UV podrá tener asignada una imagen individual. Cuando se despliegue una cara para usar una textura UV en el Editor de UV, a cada cara de la malla se le asignarán automáticamente cuatro coordenadas UV: estas coordenadas definirán la forma en que se asignará una imagen o textura de cualquier tipo a la cara. Para distinguir estas coordenadas de las coordenadas XYZ del entorno 3D, se utilizarán ejes con nombres U y V , para determinar las coordenadas de cada punto. De ahí el nombre de despliegue UV .

---
_Informe generado por un modelo; puede contener errores._

Traza: `dd5edd38bae446f995fb275c44ae13e4`