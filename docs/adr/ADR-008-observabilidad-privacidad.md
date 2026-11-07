# ADR-008. Observabilidad local y privacidad

- **Estado:** Propuesta
- **Contexto:** Para evaluar el sistema (tablas 16–23) se necesitan tiempos por capa, rutas, cachés y guardrails, sin exponer datos del usuario.
- **Decisión:** Cada operación abre una traza (`traza.etapa(nombre)` mide incluso con excepciones) y al cerrar escribe una línea en `data/trazas.jsonl` con `traza_id`, tipo, perfil, `tiempos_ms`, caché, ruta, modelo, respaldo, hallazgos, iteraciones, guardrails y versiones. Nunca se guarda la malla, solo su hash. `GET /metricas` agrega latencias (media, p50, p95), aciertos de caché, guardrails, rutas, modelos, respaldo, agente y utilidad (T2). Todo escucha en `127.0.0.1`, CORS solo para el puerto 5173, las mallas subidas se borran al terminar y los comentarios pasan por E3.
- **Consecuencias:** La evaluación lee las mismas trazas que el panel de métricas.
