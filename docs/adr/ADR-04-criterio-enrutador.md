# ADR-04 · Criterio del enrutador

- **Estado:** Propuesta.
- **Contexto:** Enviar todo al modelo grande es lento; enviarlo todo al pequeño baja la calidad (latencia frente a exactitud).
- **Decisión:** Enrutar por la salida del analizador determinista: sin hallazgos graves ni menores, sin modelo; hasta tres hallazgos menores y ningún grave, ruta rápida; en otro caso, ruta completa (tabla 10).
- **Alternativas:** Clasificador de intención con un modelo: agrega latencia y su propio error. Enrutar por longitud del texto: no aplica, porque la entrada principal es una malla. Ruta única: pierde el ahorro.
- **Evidencia:** Tabla 21 — `evaluacion/resultados/tabla21_enrutador.csv` (40 casos etiquetados por calidad medida con `--juez`). [Pendiente: porcentaje de casos enviados a una ruta adecuada según la calidad medida, casos enviados a la completa sin necesidad y latencia de cada ruta].
- **Consecuencias:** El criterio es transparente y se prueba con casos etiquetados. No captura casos con pocos hallazgos pero difíciles de explicar.
- **En el código:** `servicio/modelos/enrutador.py` (`Enrutador.clasificar → Ruta`; devuelve un alias, nunca un nombre de modelo).
