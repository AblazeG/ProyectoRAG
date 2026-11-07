# ADR-02 · Selección del modelo de embeddings

- **Estado:** Propuesta.
- **Contexto:** Las consultas se formulan en español y la mayor parte del corpus está en inglés. Sin un fragmento pertinente no hay hallazgo fundamentado (fundamentación).
- **Decisión:** Usar bge-m3 para indexar y consultar.
- **Alternativas:** nomic-embed-text: más ligero, pero entrenado sobre todo en inglés. embeddinggemma: multilingüe y ligero, con contexto de 2048 tokens; es la alternativa si su acierto@5 iguala al de bge-m3.
- **Evidencia:** Tabla 9 — `evaluacion/resultados/tabla09_embeddings.csv` (`python -m experimentos.experimento_embeddings`). [Pendiente: acierto@5 y MRR de los tres modelos].
- **Consecuencias:** Vectores de 1024 dimensiones: índice más grande y búsqueda algo más lenta. Cambiar de modelo obliga a reindexar todo el corpus; el manifiesto del índice guarda el modelo usado para impedir mezclas, y los umbrales de recuperación, de E4 y de la caché se recalibran.
- **En el código:** `config/servicio.yaml` (`modelos.embeddings: bge-m3`), `servicio/contexto/recuperador.py` (`Indice.verificar_compatibilidad`), `python -m servicio.ingestar corpus/ --reindexar`.
