# ADR-007. Ciclo de agente acotado para la recuperación

- **Estado:** Propuesta
- **Contexto:** Las preguntas coloquiales («mi personaje se pellizca en el codo») recuperan mal con una sola consulta.
- **Decisión:** `recuperar_con_agente(consulta, perfil, presupuesto, traza)`: suficiente si top-1 ≥ 0.55 y al menos 2 fragmentos sobre el umbral; si no, `rapido` reformula con sinónimos ES/EN. Tope de 3 reformulaciones por consulta y 6 por informe; al agotarse, «Sin norma aplicable en el corpus».
- **Consecuencias:** El costo está acotado y queda registrado en la traza (`iteraciones_agente`).
