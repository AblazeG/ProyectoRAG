# Informe de auditoría MeshAudit — teapot.obj

- **Perfil:** Animación
- **Semáforo:** rojo
- **Ruta:** completa · **Modelo:** gpt-oss:20b · **Caché:** exacta
- **Dimensión máxima:** 6.434 m · **Caras:** 6320 · **Triángulos:** 6320

Animación: 2 hallazgos (1 grave, 1 menor); 1 informativo

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

### h2 · V2 · Proporción de triángulos en una malla de deformación (menor)

- Medido: `100 %` · Límite: `≤ 10 %`

La especificación glTF 2.0 define que cada canal de animación debe usar un sampler que especifica los datos de fotogramas clave y el método de interpolación. Los ejemplos muestran que los samplers pueden apuntar a distintas propiedades (rotación, escala, traducción, pesos de morfología) y que cada sampler puede tener su propio conjunto de entradas y salidas. Para una malla de deformación, la proporción de triángulos que se deforman depende de los pesos de los targets de morfología, los cuales se animan a través de los samplers. Si los pesos no se actualizan correctamente, la deformación será incorrecta o inexistente. Por lo tanto, es crítico que los canales de animación incluyan samplers que interpolen los pesos de los targets de morfología de manera adecuada, tal como se muestra en los ejemplos de la sección 3.11 de la especificación glTF 2.0.

**Pasos de corrección:**
1. Verificar que cada canal de animación que afecta a una malla de deformación incluya un sampler con la propiedad "path": "weights" (cita: [gltf_spec:3-11-animations#9]).
2. Asegurarse de que el sampler asociado a los pesos utilice la interpolación LINEAR o la que sea apropiada para la aplicación (cita: [gltf_spec:3-11-animations#7]).
3. Confirmar que el sampler tenga entradas y salidas válidas y que el número de valores de salida coincida con el número de targets de morfología de la malla (cita: [gltf_spec:3-11-animations#14]).
4. Revisar que los samplers dentro de la misma animación puedan tener diferentes entradas, permitiendo que los pesos se actualicen en momentos distintos a los de otras propiedades (cita: [gltf_spec:3-11-animations#14]).
5. Validar que la malla de deformación tenga la proporción correcta de triángulos deformados según los pesos animados, utilizando herramientas de inspección de glTF que muestren la distribución de pesos (cita: [gltf_spec:3-11-animations#6]).

> **Fuente:** gltf_spec — 3.11. Animations (`gltf_spec:3-11-animations#9`, puntaje 0.618)
>
> " } } ], " samplers " : [ { " input " : 0 , " interpolation " : " LINEAR " , " output " : 1 } ] }, { " name " :
> 
> " Animate a node rotation channel and the weights of a Morph Target it instantiates " , " channels " : [ { " sampler " : 0 , " target " : { " node " : 1 , " path " : " rotation " } }, { " sampler " : 1 , " target " : { " node " : 1 , " path " : " weights " } } ], " samplers " : [ { " input " : 4 , " interpolation " : " LINEAR " , " output " : 5 }, { " input " : 4 , " interpolation " : " LINEAR " , " output " : 6 } ] } ] }

### h3 · V10 · Vértices duplicados (informativo)

- Medido: `403 vértices` · Límite: `0`

---
_Informe generado por un modelo; puede contener errores._

Traza: `88d4cb907a744e6687974f32dea32943`