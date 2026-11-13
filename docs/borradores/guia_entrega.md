---
doc_id: guia_entrega
titulo: Guía de entrega de modelos 3D
licencia: propio
perfiles: [juego_movil, impresion_3d, web_ar]
---
# Guía de entrega de modelos 3D

Esta guía reúne los requisitos que debe cumplir un modelo 3D antes de entregarse para impresión 3D, para un juego móvil o para un visor web o de realidad aumentada. Cada sección explica el requisito, por qué importa y cómo comprobarlo y corregirlo en Blender.

## Mallas cerradas

Una malla para impresión 3D debe ser cerrada (en inglés, *watertight*): su superficie tiene que encerrar un volumen sin huecos, de modo que cada arista quede compartida por exactamente dos caras. El laminador calcula qué está dentro y qué está fuera de la pieza para generar las paredes y el relleno; si la superficie tiene agujeros, no puede saberlo y produce capas incompletas, paredes abiertas o mensajes de error como «la pieza tiene agujeros».

Para comprobarlo en Blender, entra en modo edición y usa Select > Select All by Trait > Non Manifold: los bordes abiertos quedan resaltados. El complemento 3D Print Toolbox también los cuenta en su revisión. Para cerrar un hueco, selecciona el borde y usa Fill (F) o Grid Fill; después vuelve a ejecutar la comprobación hasta que no quede ningún borde abierto.

## Geometría no manifold

La geometría no manifold no puede existir en un objeto sólido: aristas compartidas por más de dos caras, caras internas, vértices o aristas sueltos y piezas que se tocan solo en un vértice o una arista. En impresión 3D provoca que el laminador interprete mal el volumen y aparecen huecos o paredes raras en la vista previa de capas.

Se detecta igual que los bordes abiertos, con Select Non Manifold o con la revisión del 3D Print Toolbox. Las caras internas se borran con Delete Faces; las aletas pegadas a una arista se eliminan borrando las caras sobrantes; las piezas que solo se tocan en un punto se separan o se unen con un puente de caras. Al terminar, la malla no debe tener ninguna arista no manifold.

## Escala y volumen de impresión

Los archivos STL y OBJ no guardan unidades: el laminador interpreta cada unidad como un milímetro. Un modelo hecho en metros en Blender (por ejemplo, una figura de 0.05 de alto) sale diminuto, de 0.05 mm, y uno de 50 metros no cabe en la cama de impresión.

Antes de exportar, comprueba que la dimensión mayor de la pieza esté entre 1 mm y 300 mm, que es el rango útil de las impresoras de escritorio del taller. En Blender, ajusta Scene Properties > Units con Unit Scale 0.001 y Length en milímetros para modelar directamente en milímetros, o escala la pieza y aplica la escala con Object > Apply > Scale antes de exportar. Revisa el tamaño final en el laminador.

## Caras degeneradas

Una cara degenerada tiene área nula o casi nula: sus vértices son colineales o coinciden. No aportan forma, tienen normales indefinidas y los laminadores las reportan como errores o las omiten, lo que puede dejar huecos en la superficie impresa.

Se encuentran con la revisión Degenerate del 3D Print Toolbox, que marca las caras con área por debajo de un umbral. Se eliminan con Mesh > Clean Up > Degenerate Dissolve. Después de disolverlas comprueba que no se hayan abierto huecos y vuelve a revisar la malla con Select Non Manifold.

## Normales invertidas

Las normales indican hacia dónde mira cada cara. En una pieza para imprimir todas deben apuntar hacia fuera del volumen. Si algunas apuntan hacia dentro, el laminador puede tomar esa zona como exterior: deja partes sin relleno, invierte paredes o genera superficies sueltas.

En Blender, activa Viewport Overlays > Face Orientation: las caras que miran hacia fuera se ven azules y las invertidas, rojas. Para corregirlas, selecciona toda la malla en modo edición y usa Mesh > Normals > Recalculate Outside (Shift+N). En mallas abiertas el recálculo puede fallar: cierra primero la malla.

## Tamaño de archivo para web

Un modelo para un visor web o de realidad aumentada se descarga cada vez que alguien abre la página. Un archivo grande tarda en cargar, sobre todo en redes móviles, y puede hacer que el visor falle en teléfonos con poca memoria. El archivo GLB final no debe pasar de 10 MB.

Lo que más pesa suelen ser las texturas incrustadas. Para reducir el tamaño: baja la resolución de las texturas (por ejemplo, de 4096 a 2048 o 1024 píxeles), usa JPEG o WebP para las texturas de color y reduce el número de polígonos con el modificador Decimate si el detalle no se aprecia en pantalla. La compresión de geometría con Draco o meshopt se aplica solo a la versión que se publica: el archivo que se entrega para revisión debe ir sin comprimir, porque las herramientas de revisión no siempre pueden leer la geometría comprimida.

## Presupuesto de triángulos para juego móvil

En un juego móvil, cada triángulo cuesta tiempo de GPU en cada cuadro. Un modelo principal, como un personaje o un objeto con el que el jugador interactúa, no debe pasar de 20 000 triángulos; para un visor web el límite práctico es de 100 000. Los objetos secundarios deben quedarse muy por debajo.

Para cumplirlo, consulta la cuenta de triángulos en Viewport Overlays > Statistics, reduce detalle con el modificador Decimate o retopología, y traslada el detalle fino a un mapa de normales horneado. Para objetos que se ven a distintas distancias, prepara niveles de detalle (LOD) para que el motor muestre versiones más ligeras cuando el objeto está lejos.
