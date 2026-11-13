---
doc_id: rubrica_animacion
titulo: Rúbrica de modelado para animación 3D
licencia: propio
perfiles: [animacion, juego_movil]
---
# Rúbrica de modelado para animación 3D

Esta rúbrica se usa para evaluar los modelos que se entregan en el curso de animación 3D. Cada criterio indica qué se espera, por qué importa para la animación y cómo se califica.

## Topología para deformación

Un modelo que se va a deformar con un esqueleto (personajes, criaturas, ropa) debe estar hecho de cuadriláteros con bucles de aristas que sigan la forma de las articulaciones y los músculos. Los cuadriláteros se subdividen de forma predecible y se doblan sin pellizcarse; por eso los bucles deben rodear codos, rodillas, hombros, boca y ojos.

Los n-gons, caras de más de cuatro lados, no se aceptan en una malla de deformación: al subdividir o al triangular el motor los divide de forma impredecible y producen pellizcos y sombras raras al doblar la articulación. Los triángulos se toleran en zonas planas que no se deforman, pero no deben pasar del 10 % de las caras; si un personaje se pellizca en el codo al doblarlo, casi siempre hay triángulos o n-gons en la articulación.

Para revisarlo en Blender, usa Select > Select All by Trait > Faces by Sides (número de vértices mayor que 4 para los n-gons, igual a 3 para los triángulos). Los n-gons se reparan cortando con la herramienta Knife o con Connect Vertex Path hasta dejar cuadriláteros; los triángulos se convierten con Face > Tris to Quads o rehaciendo el flujo de aristas.

Calificación: 0 n-gons y como máximo 10 % de triángulos, fuera de las articulaciones, obtiene la nota completa; n-gons en cualquier zona de deformación es motivo de corrección obligatoria.

## Bucles de aristas en articulaciones

Cada articulación necesita al menos tres bucles de aristas para doblarse con suavidad: uno en el centro del pliegue y uno a cada lado. Con menos bucles el volumen colapsa al doblar; con bucles mal orientados la deformación se tuerce.

Para revisarlo, selecciona los bucles con Alt+clic y comprueba que rodeen la articulación de forma perpendicular al eje del hueso. Prueba la deformación con un esqueleto sencillo antes de entregar.

## Escala, orientación y origen

El modelo debe entregarse en metros, a escala real (un personaje humano mide entre 1.6 y 1.9 m), con la escala aplicada (Object > Apply > All Transforms), mirando hacia el eje −Y de Blender y con el origen a la altura de los pies. Una escala sin aplicar o un origen mal colocado rompen el esqueleto y la exportación a los motores.

## Mapa UV y nombres

El modelo debe tener un mapa UV completo, sin islas superpuestas salvo en partes simétricas intencionales, con las costuras en zonas poco visibles y una densidad de texeles uniforme. El objeto, la malla y los materiales deben tener nombres descriptivos en lugar de «Cube.001» o «Material.002».
