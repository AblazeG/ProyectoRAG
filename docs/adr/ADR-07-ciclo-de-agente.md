# ADR-07 · Diseño del ciclo de agente

- **Estado:** Propuesta.
- **Contexto:** Las preguntas de seguimiento usan términos coloquiales que no coinciden con los del corpus, y algunas consultas canónicas de hallazgos no recuperan bien entre español e inglés; una recuperación pobre termina en «sin norma aplicable» (fundamentación).
- **Decisión:** Si el mejor fragmento queda bajo 0.55 o hay menos de dos sobre el umbral, el modelo rápido reformula la consulta; máximo tres reformulaciones por consulta y seis por informe (código 4).
- **Alternativas:** Sin agente: más hallazgos sin norma. Un agente libre con herramientas: menos predecible y difícil de evaluar. Búsqueda híbrida con BM25: se deja como trabajo futuro.
- **Evidencia:** Tabla 20 — `evaluacion/resultados/tabla20_agente.csv`. [Pendiente: porcentaje de consultas que mejoran tras reformular y reformulaciones promedio].
- **Consecuencias:** La latencia extra está acotada a tres llamadas cortas al modelo rápido por consulta y seis por informe. La condición de salida evita ciclos infinitos.
- **En el código:** `servicio/orquestacion/agente.py` (`CicloAgente.recuperar_con_agente`, `es_suficiente`, `Presupuesto`), `servicio/contexto/prompts.py` (`prompt_reformular`).
