# ADR-006. Caché exacta y semántica en SQLite

- **Estado:** Propuesta
- **Contexto:** Auditar la misma malla o repetir preguntas no debería costar otra llamada al modelo.
- **Decisión:** Exacta de informes (SHA-256 del archivo, perfil, hash de notas enmascaradas y versiones de perfiles, analizador, corpus, prompt y modelos), exacta de hallazgos (verificación, perfil, gravedad, versiones de corpus y prompt, modelo de la ruta; sin mediciones) y exacta de preguntas; semántica solo para preguntas del mismo archivo y perfil con coseno ≥ 0.92 y misma `version_corpus`. Expiración 7 días / 24 horas; `purgar(version)` tras cada cambio del corpus. Solo se guardan respuestas que pasaron S1–S3 y que no son rechazos.
- **Consecuencias:** Los informes viven en su propia tabla: purgar la caché no rompe `GET /auditorias/{id}`.
