---
doc_id: godot_docs
titulo: Godot Engine — importación de escenas 3D, LOD y rendimiento (texto sintético de prueba)
licencia: CC-BY-3.0
perfiles: [juego_movil, web_ar]
fuente: Texto redactado para las pruebas de MeshAudit; sustituye a la documentación de Godot (HTML, CC BY 3.0).
formato_real: html
---
# Godot Engine: rendimiento 3D

## Presupuesto de polígonos

Cada plataforma tiene un presupuesto de polígonos por objeto. En juegos móviles un personaje principal debe mantenerse por debajo de 20000 triángulos para conservar la tasa de cuadros. En experiencias web y de realidad aumentada un modelo de producto no debería superar 100000 triángulos.

Para reducir el número de triángulos usa el modificador Decimate en modo Collapse y ajusta la proporción hasta llegar al presupuesto. Conserva la silueta y transfiere el detalle fino a un mapa de normales horneado desde la versión de alta resolución.

También puedes generar niveles de detalle: versiones con menos triángulos que el motor muestra cuando el objeto está lejos de la cámara. Revisa el conteo final en las estadísticas de la escena.

El presupuesto incluye todos los triángulos que el motor dibuja, por lo que un quad cuenta como dos triángulos y un n-gon como varios. Mide el presupuesto después de triangular. Reparte los triángulos según la importancia visual: la silueta y las zonas cercanas a la cámara merecen más detalle que las caras ocultas o pequeñas, que se pueden simplificar sin pérdida visible.
