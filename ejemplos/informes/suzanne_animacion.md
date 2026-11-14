# Informe de auditoría MeshAudit — suzanne.obj

- **Perfil:** Animación
- **Semáforo:** rojo
- **Ruta:** completa · **Modelo:** gpt-oss:20b · **Caché:** exacta
- **Dimensión máxima:** 2.734375 m · **Caras:** 500 · **Triángulos:** 968

Animación: 2 hallazgos (1 grave, 1 menor)

## Hallazgos

### h1 · V6 · La malla no tiene coordenadas UV por vértice (grave)

- Medido: `sin UV` · Límite: `UV por vértice`

Las coordenadas UV son esenciales para mapear texturas a la superficie 3D. Sin ellas, la malla no puede recibir texturas ni ser exportada correctamente a formatos como glTF, donde el nodo Mapa UV y el nodo Mapeo dependen de UVs para aplicar transformaciones (posición, rotación, escala). Además, el Editor de UV requiere que cada cara tenga UVs para asignar imágenes, lo que impide la edición y visualización en tiempo real.

**Pasos de corrección:**
1. Seleccionar la malla en modo Edición y activar la vista de UV (UV Editor).
2. Usar la opción *Unwrap* (desenvolver) para generar coordenadas UV automáticas para todas las caras.
3. Verificar que cada cara tenga un nodo Image Texture en el Shader Editor y que esté seleccionado.
4. Exportar la malla a glTF asegurándose de que el nodo Mapeo esté configurado con la extensión KHR_texture_transform si se requieren transformaciones.

> **Fuente:** blender_manual_uv_intro — Acerca de las UV (`blender_manual_uv_intro:acerca-de-las-uv#2`, puntaje 0.6384)
>
> de la malla 3D. Es posible pensar en un mapa UV como si se proyectara la superficie del modelo 3D sobre una imagen 2D.
> 
> Cada cara de una malla podrá tener varias texturas UV. Cada textura UV podrá tener asignada una imagen individual. Cuando se despliegue una cara para usar una textura UV en el Editor de UV, a cada cara de la malla se le asignarán automáticamente cuatro coordenadas UV: estas coordenadas definirán la forma en que se asignará una imagen o textura de cualquier tipo a la cara. Para distinguir estas coordenadas de las coordenadas XYZ del entorno 3D, se utilizarán ejes con nombres U y V , para determinar las coordenadas de cada punto. De ahí el nombre de despliegue UV .

### h2 · V4 · Aristas no manifold (compartidas por más de dos caras) (menor)

- Medido: `1 arista` · Límite: `0`

Las aristas no manifold (compartidas por más de dos caras) generan geometría no válida que puede causar problemas en la simulación física, la exportación a otros formatos y la visualización en tiempo real. Blender permite seleccionar y limpiar este tipo de geometría para asegurar que la malla sea manifold y esté lista para animación.

**Pasos de corrección:**
1. Entrar en modo Edición y usar *Select > Select All by Trait > Non Manifold* para identificar las aristas problemáticas.
2. Aplicar *Mesh > Clean > Split Non Planar Faces* para dividir caras que estén dobladas más allá del ángulo permitido, lo que puede resolver aristas compartidas por más de dos caras.
3. Revisar y eliminar vértices aislados o aristas que pertenezcan a más de dos caras usando las opciones de selección de rasgos.
4. Repetir la selección y limpieza hasta que no queden aristas no manifold.

> **Fuente:** blender_manual_limpieza — Limpiar (`blender_manual_limpieza:limpiar#1`, puntaje 0.5849)
>
> These operators can automatically clean up certain types of messy geometry.

---
_Informe generado por un modelo; puede contener errores._

Traza: `c61a56b82ef645409061561566e6ca8f`