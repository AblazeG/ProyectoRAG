# ADR-004. Modelos locales con Ollama, enrutador por alias y gateway con respaldo

- **Estado:** Propuesta
- **Contexto:** El servicio corre en un Mac M4 Max (128 GB) sin nube (`OLLAMA_NO_CLOUD=1`). Modelos grandes dan mejor calidad pero tardan más.
- **Decisión:** El enrutador devuelve alias, nunca nombres: sin modelo (sin G ni M), `rapido` → gemma4:e2b (1–3 menores; preguntas) y `completo` → gpt-oss:20b (≥ 4 G/M o algún grave). El gateway aplica 45 s / 90 s, hasta 2 reintentos (1 y 2 s) solo ante conexión o 5xx; timeout y 404 van directo al respaldo (el otro alias); si este falla, `ModeloNoDisponible` → 503. Opciones fijas: `temperature` 0.1, `seed` 42, `num_ctx` 8192, `format` = esquema Pydantic, `think` falso en gemma4/qwen3 y bajo en gpt-oss, `keep_alive` 30m. Una llamada por lote de hasta 4 hallazgos. Los embeddings no pasan por el gateway.
- **Consecuencias:** Con `MESHAUDIT_PROVEEDOR=falso` los dobles deterministas sustituyen a Ollama en pruebas y en la nube.
