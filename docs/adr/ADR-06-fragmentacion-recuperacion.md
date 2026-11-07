# ADR-06 · Fragmentación del corpus y parámetros de recuperación

- **Estado:** Propuesta.
- **Contexto:** Fragmentos grandes mezclan temas y diluyen el vector; fragmentos pequeños pierden contexto (fundamentación).
- **Decisión:** 800 caracteres con 120 de solape, cortando primero por sección y después por párrafo; recuperación con k = 5 y umbral 0.55 como valores iniciales.
- **Alternativas:** 500 y 1000 caracteres con el mismo solape relativo; corte fijo sin respetar secciones; un fragmento por página; k de 3 u 8; umbrales de 0.40 a 0.70.
- **Evidencia:** Tablas 17 y 18 — `evaluacion/resultados/tabla17_fragmentos.csv` y `tabla18_barrido.csv` (`python -m experimentos.experimento_fragmentos`). [Pendiente: acierto@k de cada tamaño con el mismo presupuesto de caracteres, y aciertos y rechazos correctos para cada k y umbral].
- **Consecuencias:** Con k = 5, cada hallazgo ocupa unos 1 400 tokens entre fragmentos y salida, así que caben lotes de hasta cuatro hallazgos en 8 192 tokens. Los umbrales dependen del modelo de embeddings y se recalibran si cambia.
- **En el código:** `servicio/contexto/fragmentador.py`, `servicio/contexto/recuperador.py` (`recuperar(consulta, k, perfil)`), `servicio/contexto/prompts.py` (`tamano_lote`), `config/servicio.yaml` (`rag`).
