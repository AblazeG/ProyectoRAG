---
doc_id: gltf_spec
titulo: Notas sobre glTF 2.0 (texto sintético de prueba)
licencia: CC0-1.0
perfiles: [animacion, juego_movil, web_ar]
fuente: Texto redactado para las pruebas de MeshAudit; resume ideas de la especificación glTF 2.0 sin copiarla.
---
# Notas sobre glTF 2.0

## Unidades y escala

En glTF la unidad de longitud es el metro. Un objeto modelado en centímetros o milímetros y exportado sin convertir aparece cien o mil veces más grande en el visor. Por eso la escala del modelo debe aplicarse antes de exportar.

En Blender selecciona el objeto y usa Object > Apply > Scale para que la escala quede en uno. Revisa las dimensiones en el panel de propiedades: un mueble debe medir alrededor de un metro y un personaje entre uno y dos metros.

Las escenas de realidad aumentada colocan el modelo en el mundo real, así que una escala equivocada hace que el objeto se vea gigante o diminuto. Comprueba la escala en el visor antes de publicar.

Configura la escena con el sistema métrico y la escala de unidades en uno antes de modelar. Si el modelo ya existe en otra escala, ajústalo con la herramienta de escala y aplica la transformación. Los exportadores de glTF convierten la orientación de los ejes, pero no corrigen una escala equivocada, por lo que la comprobación de dimensiones debe hacerse antes de exportar el modelo.

## Coordenadas de textura

Los atributos TEXCOORD_0 y TEXCOORD_1 guardan las coordenadas de textura de cada vértice. Los materiales con imagen base, mapa de normales u oclusión necesitan estas coordenadas para muestrear la textura.

Un modelo sin coordenadas de textura solo puede mostrar colores planos. Los visores web y los motores de juego esperan que cada vértice tenga sus coordenadas, por lo que el modelo debe desenvolverse antes de exportarse.

Al exportar desde Blender activa la opción de incluir UV y revisa que el mapa activo sea el correcto. Si el objeto tiene varios mapas, el primero se exporta como TEXCOORD_0.

Las coordenadas de textura deben estar dentro del espacio de la imagen para evitar repeticiones inesperadas cuando el muestreador no usa el modo de repetición. Un mapa de normales también necesita tangentes, que el exportador calcula a partir de las coordenadas de textura. Si faltan las coordenadas, el material se muestra con un solo color y los mapas de normales no tienen efecto en el visor.
