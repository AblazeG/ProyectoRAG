# ADR-001. Arquitectura en capas con orquestación mediadora

- **Estado:** Propuesta
- **Contexto:** MeshAudit combina un analizador determinista, recuperación (RAG), modelos de lenguaje locales, guardrails y caché. El profesor exige que el código coincida con los diagramas y que cada capa sea visible.
- **Decisión:** Siete capas (C1 API, C2 Orquestación, C3 Guardrails, C4 Caché, C5 Contexto, C6 Modelos, C7 Datos) y dos capas abiertas (T1 Observabilidad, T2 Retroalimentación). C2 actúa como **mediador**: invoca en orden solo los servicios del flujo y nunca importa C7. C3–C6 forman el nivel de servicios; solo C7 toca recursos. Los puertos viven en `servicio/dominio.py` (`typing.Protocol`) y `servicio/composicion.py` es el único lugar que conoce implementaciones. No se usan LangChain ni LlamaIndex.
- **Consecuencias:** `tests/test_arquitectura.py` analiza las importaciones con `ast` y falla ante dependencias no permitidas, ante `httpx`, `chromadb` o `sqlite3` fuera de C7, y ante `trimesh` fuera de `datos/mallas.py` y `contexto/herramientas.py`. Cambiar ChromaDB por el adaptador en memoria toca solo `datos/` y `composicion.py`.
