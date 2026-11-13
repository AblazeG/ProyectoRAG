# ADR-05 · Verificaciones de los guardrails

- **Estado:** Propuesta.
- **Contexto:** Las notas y las preguntas son texto libre que puede traer inyección de instrucciones o datos personales, y el modelo puede inventar citas o cifras (seguridad, privacidad y exactitud).
- **Decisión:** Cinco verificaciones de entrada, una de ellas para documentos ingeridos, y cuatro de salida con política explícita (tabla 13); la inyección se detecta con patrones más un clasificador few-shot con el modelo rápido.
- **Alternativas:** Solo un prompt defensivo: no basta frente a ataques evidentes. Un modelo dedicado de moderación: más memoria y latencia para un dominio acotado. Solo expresiones regulares: pocas detecciones con paráfrasis.
- **Evidencia:** Tabla 19 — `evaluacion/resultados/tabla19_guardrails.csv`. [Pendiente: manejo correcto y falsos positivos sobre 13 entradas problemáticas y 10 normales].
- **Calibración (2026-11-13, corrida local con bge-m3):**
  - **E4:** `umbral_fuera_dominio` pasa de 0.30 a **0.40**. Con 0.30, dos de las tres preguntas fuera de dominio pasaban. La similitud más alta de esas preguntas (con el corpus o con el informe) es 0.35, y la más baja de las preguntas normales es 0.48. Los embeddings falsos de las pruebas conservan 0.30 (`umbral_fuera_dominio_falso`).
  - **E2:** el clasificador recibe el texto ya enmascarado por E3. Además tiene un ejemplo negativo con datos de contacto, porque gemma4:e2b tomaba «escríbeme a …» y una CURP por inyección: 2 falsos positivos de 3 casos de E3. Los patrones siguen revisando el texto original.
- **Consecuencias:** Se acepta un pequeño costo de latencia por el clasificador. Puede haber falsos positivos en notas legítimas que mencionen «instrucciones»; se revisan en las trazas.
- **En el código:** `servicio/guardrails/entrada.py` (E1–E5), `servicio/guardrails/salida.py` (`verificar_generacion → Veredicto`, S4), `servicio/guardrails/patrones.py`.
