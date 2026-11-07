# ADR-005. Guardrails de entrada y salida

- **Estado:** Propuesta
- **Contexto:** El servicio recibe archivos, notas, preguntas y documentos no confiables, y genera texto con un LLM.
- **Decisión:** Entrada: E1 archivo (extensión, ≤ 50 MB, firma `glTF`/`ply`, lectura de prueba de OBJ y STL), E2 inyección (patrones ES/EN + clasificador few-shot con `rapido`), E3 datos personales (correo, teléfono, CURP, matrícula: enmascarar y continuar), E4 fuera de dominio (< 0.30 con el corpus y con el informe), E5 documento (antes y después de extraer; cuarentena). Salida: S1 formato (reintento y mensaje seguro), S2 citas (quitar las que no se entregaron), S3 cifras (reintento y eliminar frase), S4 aviso y re-enmascarado **siempre**, también con caché y en rechazos. Los mensajes de rechazo no revelan el patrón.
- **Consecuencias:** Hay una prueba que recorre todos los caminos de respuesta y falla si alguno omite S4.
