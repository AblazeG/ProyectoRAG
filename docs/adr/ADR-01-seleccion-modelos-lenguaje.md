# ADR-01 · Selección de modelos de lenguaje

- **Estado:** Propuesta.
- **Contexto:** El informe debe ser fiel y útil (exactitud), pero la auditoría no debe tardar más de 15 s en casos simples (latencia). Con 128 GB la memoria no limita la elección, pero se fija un tope de 40 GB para los modelos del servicio (tabla 5); el límite real es el tiempo.
- **Decisión:** Usar dos modelos: gemma4:e2b para la ruta rápida y gpt-oss:20b para la completa, cada uno respaldo del otro.
- **Alternativas:** Un solo modelo grande: descartado por latencia en casos simples. Un solo modelo pequeño: descartado por calidad en casos con varios hallazgos. qwen3:8b: queda como alternativa si supera a gemma4:e2b en la tabla 8. Modelos densos de 27B o más, como gemma4:31b: descartados por latencia. Los de mezcla de expertos se juzgan por sus parámetros activos: gpt-oss:20b activa unos 3.6B, y gemma4:26b, con unos 3.8B activos, queda como alternativa para la ruta completa. Modelos en la nube: descartados porque violan la restricción de ejecución local (sección 3).
- **Evidencia:** Tabla 8 — `evaluacion/resultados/tabla08_llm.csv` (`python -m experimentos.experimento_llm --juez`). [Pendiente: calidad y latencia p95 de cada modelo].
- **Consecuencias:** Se reduce la latencia en la mayoría de los casos. Se sacrifica memoria (dos modelos cargados) y se acepta una pequeña diferencia de estilo entre rutas.
- **En el código:** `config/servicio.yaml` (`modelos.rapido`, `modelos.completo`), `servicio/modelos/gateway.py` (respaldo), `servicio/datos/ollama.py` (`think`).
