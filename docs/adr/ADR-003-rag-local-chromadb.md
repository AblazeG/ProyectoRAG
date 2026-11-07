# ADR-003. RAG local con ChromaDB y manifiesto del índice

- **Estado:** Propuesta
- **Contexto:** Cada hallazgo debe citar la norma técnica que lo respalda, sin enviar datos fuera del equipo.
- **Decisión:** Ingesta de PDF (pypdf), HTML (BeautifulSoup, sin menús, cabeceras ni pies) y Markdown; fragmentos de 800 caracteres con solape de 120, cortando por sección y luego por párrafo; metadatos `doc_id`, título, sección, página, formato, licencia y perfiles. ChromaDB persistente con espacio coseno. Un manifiesto guarda el modelo de embeddings y la `version_corpus`, que sube con cada ingesta o eliminación; si el modelo cambia hay que reindexar. `recuperar(consulta, k=5, perfil)` con umbral 0.55 y filtro por perfil, devolviendo el top-1 para la traza. Prefijos `search_document:`/`search_query:` con nomic-embed-text.
- **Consecuencias:** Se añade `datos/memoria.py` como segundo adaptador vectorial para demostrar la modificabilidad.
