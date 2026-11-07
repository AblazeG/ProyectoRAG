# ADR-03 · Alcance y umbral de la caché semántica

- **Estado:** Propuesta; el umbral se calibra con la tabla 22.
- **Contexto:** Las preguntas de seguimiento sobre un mismo informe se repiten con otras palabras, y responderlas otra vez es costoso, pero un acierto puede servir la respuesta a una pregunta distinta (exactitud frente a latencia). Los hallazgos no necesitan similitud, porque su consulta se deriva de campos fijos.
- **Decisión:** Caché semántica solo para preguntas, limitada al mismo archivo y perfil, con umbral de coseno 0.92, expiración de 24 horas e invalidación por versión del corpus. Los hallazgos usan caché exacta.
- **Alternativas:** 0.85: más aciertos y más respuestas equivocadas. 0.95: casi equivale a la caché exacta. Caché semántica también para hallazgos: no añade aciertos y puede mezclar perfiles o verificaciones. Sin caché semántica: más simple, pero repite llamadas.
- **Evidencia:** Tabla 22 — `evaluacion/resultados/tabla22_cache.csv` (`python -m experimentos.experimento_cache`). [Pendiente: recall y precisión con 0.85, 0.90, 0.92 y 0.95 frente a 10 paráfrasis y 10 distractores].
- **Consecuencias:** Un acierto equivocado entrega la respuesta, con sus citas, a otra pregunta sobre el mismo informe; por eso en la calibración pesa más la precisión que el recall. Las mediciones no se ven afectadas, porque las inserta la plantilla.
- **En el código:** `servicio/cache/semantica.py` (`CacheSemantica.buscar_similar`), `config/servicio.yaml` (`cache.umbral_semantico`, `cache.expiracion_semantica_h`).
