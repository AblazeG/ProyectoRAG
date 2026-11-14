# Informe de auditoría MeshAudit — Fox.glb

- **Perfil:** Juego móvil
- **Semáforo:** amarillo
- **Ruta:** rapida · **Modelo:** gemma4:e2b · **Caché:** ninguna
- **Dimensión máxima:** 154.719864 m · **Caras:** 576 · **Triángulos:** 576

Juego móvil: 1 hallazgo (1 menor); 2 informativos. V1 no se pueden medir en GLB: audita el archivo en OBJ

## Hallazgos

### h1 · V7 · Dimensión máxima fuera del rango esperado (menor)

- Medido: `154.72 m` · Límite: `0.01–100 m`

La dimensión máxima fuera del rango esperado se relaciona con la implementación de la textura para normales y la normalización de vectores, y la aplicación de transformaciones de escala y traslación en la escena.

**Pasos de corrección:**
1. La implementación de la textura para normales puede contener un valor de escala escalar que escala linealmente los componentes X e Y del vector normal.
2. [gltf_spec:3-9-materials#12]
3. Los vectores normales DEBEN normalizarse antes de ser utilizados en ecuaciones de iluminación. Cuando se usa escalado, la normalización ocurre después del escalado.
4. [gltf_spec:3-9-materials#10]
5. En el orden T * R * S, primero se aplica la escala a los vértices, luego la rotación y luego la traslación.
6. [gltf_spec:3-5-scenes#5]
7. Las transformaciones no invertibles (ej. escalar un eje a cero) podrían provocar artefactos de iluminación y/o visibilidad.
8. [gltf_spec:3-5-scenes#5]
9. Cuando la escala es cero en los tres ejes (por transformación de nodo o por escala animada), las implementaciones son libres para eliminar el renderizado de la malla del nodo y todas las mallas de sus hijos. Esto proporciona un mecanismo para animar la visibilidad. Las mallas esqueladas no deben usar esta optimización a menos que todos los articulaciones de la piel se escalen a cero simultáneamente.
10. [gltf_spec:3-5-scenes#5]
11. El nivel de detalle (LOD) puede configurarse mediante un enfoque manual en el nodo 3D usando rangos de visibilidad (HLOD). Los decals y luces también pueden beneficiarse del nivel de detalle usando sus propiedades de Desvanecimiento de Distancia.
12. [godot_docs_rendimiento:nivel-de-detalle-lod#2]

> **Fuente:** gltf_spec — 3.9. Materials (`gltf_spec:3-9-materials#12`, puntaje 0.5892)
>
> is usually implemented as sampledValue * 2.0 - 1.0 .
> 
> This mapping is usually implemented as sampledValue * 2.0 - 1.0 .
> 
> The texture binding for normal textures MAY additionally contain a scalar scale value that linearly scales X and Y components of the normal vector.
> 
> Normal vectors MUST be normalized before being used in lighting equations. When scaling is used, vector normalization happens after scaling.

### h2 · V1 · Caras con más de cuatro lados (n-gons): no medible en GLB; audita el archivo en OBJ para medirlo. (informativo)

- Medido: `no medible` · Límite: `0 %`

### h3 · V10 · Vértices duplicados (informativo)

- Medido: `1294 vértices` · Límite: `0`

---
_Informe generado por un modelo; puede contener errores._

Traza: `323aa85f46d24ad68e53418e53dac714`