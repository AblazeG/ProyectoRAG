---
doc_id: guia_tiempo_real
titulo: Guía de recursos para tiempo real (texto sintético de prueba)
licencia: CC0-1.0
perfiles: [juego_movil, web_ar]
fuente: Texto redactado para las pruebas de MeshAudit.
---
# Guía de recursos para tiempo real

## Presupuesto de polígonos

Cada plataforma tiene un presupuesto de polígonos por objeto. En juegos móviles un personaje principal debe mantenerse por debajo de 20000 triángulos para conservar la tasa de cuadros. En experiencias web y de realidad aumentada un modelo de producto no debería superar 100000 triángulos.

Para reducir el número de triángulos usa el modificador Decimate en modo Collapse y ajusta la proporción hasta llegar al presupuesto. Conserva la silueta y transfiere el detalle fino a un mapa de normales horneado desde la versión de alta resolución.

También puedes generar niveles de detalle: versiones con menos triángulos que el motor muestra cuando el objeto está lejos de la cámara. Revisa el conteo final en las estadísticas de la escena.

El presupuesto incluye todos los triángulos que el motor dibuja, por lo que un quad cuenta como dos triángulos y un n-gon como varios. Mide el presupuesto después de triangular. Reparte los triángulos según la importancia visual: la silueta y las zonas cercanas a la cámara merecen más detalle que las caras ocultas o pequeñas, que se pueden simplificar sin pérdida visible.

## Tamaño de archivo para web

Los modelos para web se descargan antes de mostrarse, por lo que el tamaño del archivo afecta el tiempo de carga. Un modelo para web o realidad aumentada no debería superar 10 MB.

Para reducir el tamaño comprime la geometría con Draco o meshopt al exportar a glTF, reduce la resolución de las texturas y elimina atributos que no se usan, como colores de vértice innecesarios.

Prefiere el formato binario GLB, que empaqueta geometría y texturas en un solo archivo. Mide el resultado y repite la compresión si el archivo sigue siendo grande.

Las texturas suelen ocupar la mayor parte del archivo. Usa formatos comprimidos como KTX2 con Basis Universal o reduce la resolución a la mínima que se vea bien en pantalla. Elimina las animaciones, los materiales y las mallas que no se usan antes de exportar. Un archivo más pequeño también reduce el consumo de memoria en teléfonos y la espera del usuario.
