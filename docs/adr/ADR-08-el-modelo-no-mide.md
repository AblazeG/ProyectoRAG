# ADR-08 · El modelo de lenguaje no mide la geometría

- **Estado:** Propuesta.
- **Contexto:** Un modelo de lenguaje que lee una malla o un render puede inventar conteos y dimensiones con total seguridad; una cifra falsa en un informe técnico destruye su valor (exactitud).
- **Decisión:** Todas las métricas las calcula un analizador determinista con trimesh, un lector propio de OBJ y reglas en `perfiles.yaml`; el modelo solo explica y prioriza, y las mediciones las inserta una plantilla.
- **Alternativas:** Pasar el OBJ como texto al modelo: excede el contexto y produce errores de conteo. Usar un modelo de visión sobre renders: impreciso para topología. Calcular con el modelo usando herramientas: más llamadas y más puntos de falla.
- **Evidencia:** Tabla 16 — `evaluacion/resultados/tabla16_producto.csv`. [Pendiente: recall y precisión de los hallazgos y activaciones de la verificación S3].
- **Consecuencias:** Exactitud y facilidad de prueba. A cambio, cada regla nueva exige código, y el producto no evalúa aspectos que no se pueden medir con reglas, como el flujo de aristas o la calidad estética.
- **En el código:** `servicio/contexto/herramientas.py` (`analizar_malla`), `servicio/datos/mallas.py` (`LectorTrimesh`, `leer_lados_obj`), `config/perfiles.yaml`, S3 en `servicio/guardrails/salida.py`.
