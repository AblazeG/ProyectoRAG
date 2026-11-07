---
doc_id: rubrica_animacion
titulo: Rúbrica de modelado para un curso de animación 3D (texto sintético de prueba)
licencia: propio
perfiles: [animacion, juego_movil]
fuente: Texto redactado para las pruebas de MeshAudit; en el corpus real es un PDF propio del autor.
formato_real: pdf
---
# Rúbrica de modelado para animación 3D

## Topología para deformación

Una malla que se va a deformar con un esqueleto debe construirse con quads, es decir, caras de cuatro lados. Los quads forman bucles de aristas continuos que siguen la musculatura y permiten que la superficie se doble sin pellizcos. Los n-gons, caras con más de cuatro lados, rompen esos bucles: al deformarse producen sombreado irregular y la subdivisión genera artefactos alrededor de ellos.

Para eliminar n-gons, selecciona las caras con Select All by Trait > Faces by Sides con la opción mayor que cuatro. Después divide cada n-gon con la herramienta Knife o con Connect Vertex Path para convertirlo en quads. Revisa que los nuevos bucles sigan el flujo de la forma.

Los triángulos son aceptables en zonas planas que no se deforman, pero en articulaciones como codos, rodillas y la cara producen pliegues duros. Una malla de deformación debe mantener los triángulos en una proporción baja. Para convertir triángulos en quads usa Face > Tris to Quads y luego corrige a mano los que queden en zonas de deformación.

En personajes conviene colocar al menos tres bucles de aristas alrededor de cada articulación para que el pliegue sea suave. Evita los polos con cinco o más aristas en las zonas que se doblan y desplázalos a regiones rígidas. Antes de crear el rig, prueba la deformación con un esqueleto sencillo y revisa los pliegues desde varios ángulos.
