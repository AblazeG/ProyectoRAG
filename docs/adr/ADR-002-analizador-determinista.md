# ADR-002. El modelo nunca mide: analizador determinista

- **Estado:** Propuesta
- **Contexto:** Los LLM alucinan cifras. Un informe técnico con mediciones inventadas es peor que no tener informe.
- **Decisión:** `contexto/herramientas.py::analizar_malla` calcula V1–V11 con numpy y trimesh sobre los arreglos de `MallaCruda` que entrega C7 (`trimesh.load(..., process=False, force="mesh")`). V4, V5 y V9 usan una copia con `merge_vertices(merge_tex=True, merge_norm=True)`; V10 usa la malla sin procesar; V1 y V2 usan un lector propio de líneas `f` del OBJ y son «no medible» en GLB, STL y PLY. Más de 2 000 000 de caras → 422. Las mediciones las inserta la plantilla; el prompt prohíbe escribirlas y S3 elimina cifras sin respaldo.
- **Consecuencias:** El semáforo es reproducible (rojo con algún grave, amarillo con solo menores, verde sin G ni M) y la ruta «sin modelo» no necesita LLM.
