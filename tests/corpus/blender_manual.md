---
doc_id: blender_manual
titulo: Blender Manual: limpieza de mallas, normales y UV (texto sintético de prueba)
licencia: CC-BY-SA-4.0
perfiles: [animacion, juego_movil, impresion_3d, web_ar]
fuente: Texto redactado para las pruebas de MeshAudit; sustituye al Blender Manual (HTML, CC BY-SA 4.0), que no se puede descargar en la nube.
formato_real: html
---
# Blender Manual: limpieza de mallas

## Limpieza de geometría no manifold

Una arista no manifold es una arista compartida por más de dos caras, o una arista suelta sin caras. Este tipo de geometría no puede existir en un objeto sólido real y causa errores en modificadores, en el cálculo de normales y en los programas de exportación.

Para encontrarla entra en modo edición, deselecciona todo y usa Select > Select All by Trait > Non Manifold. Blender resalta las aristas problemáticas. Las aletas de caras pegadas a una arista existente se eliminan borrando las caras sobrantes. Las caras internas se borran con Delete Faces.

Cuando dos piezas comparten una arista, sepáralas con Edge Split o únelas con un puente de caras para que cada arista quede compartida por exactamente dos caras. Después vuelve a ejecutar Select Non Manifold para confirmar que no queda ninguna arista resaltada.

Las aristas no manifold también aparecen al extruir sin mover la selección, porque la extrusión crea caras duplicadas encima de las originales. Para limpiar ese caso usa Merge by Distance y después borra las caras internas. Los modificadores Solidify y Boolean producen resultados incorrectos cuando la malla de entrada contiene geometría no manifold, así que limpia antes de aplicarlos.

## Desenvolvimiento UV

Las coordenadas UV asignan a cada vértice una posición en la imagen de textura. Sin UV no se pueden aplicar texturas, hornear mapas de normales ni pintar la superficie. Todo modelo destinado a materiales con imagen debe tener un mapa UV completo.

Para crear el mapa marca costuras con Mark Seam en las aristas donde la superficie se puede abrir, como en un patrón de costura. Después usa UV > Unwrap. Revisa el resultado en el editor UV con una textura de cuadrícula para detectar estiramientos.

Para objetos sencillos puedes usar Smart UV Project, que corta la malla por ángulo de forma automática. Ajusta el margen entre islas para evitar que los colores se mezclen al generar mipmaps.

Coloca las costuras en lugares poco visibles, como la parte inferior de un objeto o la cara interior de un brazo. Mantén una densidad de texeles similar en todas las islas para que la textura tenga la misma resolución en toda la superficie. Si la malla se exporta a un motor de juego, comprueba que el mapa UV se conserve al triangular y que ninguna isla quede fuera del espacio de cero a uno.

## Disolver geometría degenerada

Una cara degenerada tiene área nula o casi nula: sus vértices son colineales o coinciden. Estas caras no aportan forma, producen normales indefinidas y provocan fallos en el horneado y en los motores de juego.

Para eliminarlas selecciona toda la malla y usa Mesh > Clean Up > Degenerate Dissolve. La herramienta colapsa las aristas y caras cuyo tamaño es menor que la distancia de fusión indicada.

Después de disolver revisa que no se hayan creado agujeros. Si aparecen, rellénalos con Fill o con Grid Fill y vuelve a comprobar la malla con Select Non Manifold.

Las caras degeneradas suelen aparecer después de fusionar vértices, de aplicar booleanas o de importar modelos desde otros programas. También pueden ser triángulos muy delgados en los que dos vértices casi coinciden. Revisa la malla con la superposición de estadísticas y con el complemento 3D Print Toolbox, que las marca de forma explícita, antes de hornear texturas o exportar el modelo.

## Orientación de normales

Cada cara tiene una normal que indica cuál es su lado exterior. Si una parte de la malla tiene las normales invertidas, la iluminación se ve oscura o la cara desaparece cuando el motor descarta las caras traseras.

Activa la superposición Face Orientation: el exterior se muestra en azul y el interior en rojo. Para corregir la orientación selecciona toda la malla y usa Mesh > Normals > Recalculate Outside. Blender orienta todas las caras de forma consistente hacia fuera.

Si solo una región está invertida, selecciónala y usa Flip. En mallas abiertas el cálculo automático puede fallar, así que revisa visualmente cada zona.

Las normales invertidas suelen aparecer al reflejar un objeto con escala negativa o al unir piezas modeladas por separado. Aplica la escala antes de recalcular las normales para que el resultado sea correcto. En los motores de juego que descartan las caras traseras, una normal invertida hace que la cara desaparezca, así que revisa el modelo en el visor del motor después de exportar.

## Fusionar vértices por distancia

Los vértices duplicados ocupan la misma posición pero no están unidos. Separan la superficie en piezas, generan costuras de sombreado y aumentan el tamaño del archivo.

Para unirlos selecciona toda la malla y usa Mesh > Clean Up > Merge by Distance. Ajusta la distancia de fusión para que una los vértices coincidentes sin colapsar detalles pequeños.

Después de fusionar comprueba que la malla siga cerrada y que las costuras de UV se hayan conservado, porque la fusión puede unir vértices que debían permanecer separados en el mapa de textura.

Los vértices duplicados aparecen al importar modelos desde formatos que guardan cada cara por separado, al unir piezas o al usar el modificador Mirror sin la opción de recorte. La fusión por distancia también reduce el número de vértices y el tamaño del archivo. Si la malla debe tener bordes duros, usa Mark Sharp o el modificador Edge Split en lugar de mantener vértices sin unir.
