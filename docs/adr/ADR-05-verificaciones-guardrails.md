# ADR-05 · Verificaciones de los guardrails

- **Estado:** Propuesta.
- **Contexto:** Las notas y las preguntas son texto libre que puede traer inyección de instrucciones o datos personales, y el modelo puede inventar citas o cifras (seguridad, privacidad y exactitud).
- **Decisión:** Cinco verificaciones de entrada, una de ellas para documentos ingeridos, y cuatro de salida con política explícita (tabla 13); la inyección se detecta con patrones más un clasificador few-shot con el modelo rápido.
- **Alternativas:** Solo un prompt defensivo: no basta frente a ataques evidentes. Un modelo dedicado de moderación: más memoria y latencia para un dominio acotado. Solo expresiones regulares: pocas detecciones con paráfrasis.
- **Evidencia:** Tabla 19 — `evaluacion/resultados/tabla19_guardrails.csv`. [Pendiente: manejo correcto y falsos positivos sobre 13 entradas problemáticas y 10 normales].
- **Consecuencias:** Se acepta un pequeño costo de latencia por el clasificador. Puede haber falsos positivos en notas legítimas que mencionen «instrucciones»; se revisan en las trazas.
- **En el código:** `servicio/guardrails/entrada.py` (E1–E5), `servicio/guardrails/salida.py` (`verificar_generacion → Veredicto`, S4), `servicio/guardrails/patrones.py`.
