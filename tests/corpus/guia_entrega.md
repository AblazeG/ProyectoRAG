---
doc_id: guia_entrega
titulo: Guía de entrega de modelos 3D con los límites de cada perfil (texto sintético de prueba)
licencia: propio
perfiles: [animacion, juego_movil, impresion_3d, web_ar]
fuente: Texto redactado para las pruebas de MeshAudit; en el corpus real es un Markdown propio del autor.
---
# Guía de entrega de modelos 3D

## Mallas cerradas

Un modelo para impresión debe ser una malla cerrada, también llamada hermética o watertight: no puede tener agujeros ni bordes abiertos. El programa laminador necesita distinguir el interior del exterior para generar las capas.

Para encontrar agujeros selecciona los bordes abiertos con Select Non Manifold y ciérralos con Fill o Grid Fill. El complemento 3D Print Toolbox incluye la comprobación Solid, que indica si la malla está cerrada.

Antes de exportar vuelve a ejecutar la comprobación. Una malla abierta puede imprimirse con capas incompletas o hacer que el laminador falle.

Los agujeros pequeños son difíciles de ver a simple vista, por eso conviene confiar en la comprobación automática. Las mallas formadas por varias piezas deben cerrarse por separado o unirse con una operación booleana. Una pieza abierta impide calcular el volumen, de modo que el laminador no puede estimar el material ni el tiempo de impresión del modelo.

## Geometría no manifold

La geometría no manifold, como aristas compartidas por más de dos caras o caras internas, impide calcular un volumen sólido. El laminador puede interpretar mal las paredes y producir piezas con huecos.

Usa la comprobación de geometría no manifold del 3D Print Toolbox para localizar las aristas problemáticas. Elimina las caras internas, separa las piezas que solo se tocan por una arista y une las que deban formar un solo sólido con una operación booleana.

Repite la comprobación hasta que el informe no muestre aristas no manifold. Solo entonces exporta el modelo en STL o 3MF.

Las piezas que se tocan solo en un vértice o en una arista también son no manifold y deben separarse o unirse con material suficiente. Las paredes con grosor cero se imprimen mal aunque la malla esté cerrada, así que dales un grosor mínimo con el modificador Solidify. Después de cada corrección vuelve a exportar y abre el archivo en el laminador para confirmar que la vista previa de capas es correcta.

## Escala y volumen de impresión

Los archivos STL no guardan unidades; los laminadores suelen interpretarlos en milímetros. Un modelo exportado en metros aparece mil veces más pequeño. El objeto debe caber en el volumen de impresión, que en impresoras de escritorio suele ser de 300 mm por lado o menos.

Configura la escena en milímetros en las propiedades de unidades y aplica la escala del objeto antes de exportar. Revisa las dimensiones finales con el 3D Print Toolbox.

Si la pieza es más grande que el volumen disponible, divídela en partes con uniones y pégalas después de imprimir.

Comprueba también el grosor mínimo de pared que admite la boquilla: con una boquilla estándar de 0.4 mm las paredes más delgadas que ese valor no se imprimen. Al cambiar la escala del modelo cambian también los grosores, así que repite la comprobación de grosor después de escalar. Algunos laminadores permiten elegir la unidad al importar; selecciona milímetros si el modelo se exportó en esa unidad.

## Caras degeneradas

Las caras degeneradas tienen área cero y no definen ninguna superficie. Generan errores en el cálculo de las capas y pueden aparecer como huecos o paredes delgadas.

La comprobación Degenerate del 3D Print Toolbox las encuentra. Elimínalas con Mesh > Clean Up > Degenerate Dissolve y revisa que no queden agujeros.

Después de limpiar vuelve a comprobar que la malla esté cerrada, porque eliminar caras puede abrir bordes.

Las caras degeneradas aparecen con frecuencia después de convertir modelos desde formatos CAD o tras simplificar la malla con Decimate. Si el modelo se va a reparar de forma automática, revisa el resultado, porque la reparación puede rellenar agujeros con caras degeneradas. Un modelo limpio de caras degeneradas produce capas continuas y evita mensajes de error durante el laminado.

## Normales invertidas

En impresión 3D las normales deben apuntar hacia fuera del sólido. Si están invertidas, el laminador puede considerar el modelo como un hueco y no generar relleno.

Activa Face Orientation para ver las caras invertidas en rojo. Selecciona toda la malla y usa Recalculate Outside para orientar todas las normales de forma consistente.

Comprueba que el volumen calculado sea positivo; un volumen negativo indica que todas las normales apuntan hacia dentro.

Las normales invertidas aparecen con frecuencia en modelos reflejados con escala negativa, en piezas unidas desde varios archivos y en mallas reparadas de forma automática. El laminador muestra las zonas afectadas con un color distinto en la vista previa. Corrige la orientación antes de exportar a STL, porque el formato guarda la normal de cada faceta y algunos programas la usan para decidir qué es interior.

## Tamaño de archivo para web

Los modelos para web se descargan antes de mostrarse, por lo que el tamaño del archivo afecta el tiempo de carga. Un modelo para web o realidad aumentada no debería superar 10 MB.

Para reducir el tamaño comprime la geometría con Draco o meshopt al exportar a glTF, reduce la resolución de las texturas y elimina atributos que no se usan, como colores de vértice innecesarios.

Prefiere el formato binario GLB, que empaqueta geometría y texturas en un solo archivo. Mide el resultado y repite la compresión si el archivo sigue siendo grande.

Las texturas suelen ocupar la mayor parte del archivo. Usa formatos comprimidos como KTX2 con Basis Universal o reduce la resolución a la mínima que se vea bien en pantalla. Elimina las animaciones, los materiales y las mallas que no se usan antes de exportar. Un archivo más pequeño también reduce el consumo de memoria en teléfonos y la espera del usuario.
