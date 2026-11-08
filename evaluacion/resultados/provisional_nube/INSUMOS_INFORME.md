# Insumos para completar el informe técnico

Generado con `evaluacion/insumos_informe.py` desde `evaluacion/resultados/provisional_nube`. Corrida: proveedor `falso`, juez no, 5 corridas por caso.

> **PROVISIONAL.** Esta corrida usó el proveedor falso (modelos y embeddings simulados, mallas sintéticas, corpus de prueba). Sirve para ver la forma del texto y las tablas; las cifras de modelos, recuperación, caché semántica, agente y enrutador **no** deben ir al informe. Vuelve a generar este archivo tras la corrida con Ollama.

## Estado de las metas (tabla 5)

| Atributo | Meta | Medido | Estado |
|---|---|---|---|
| Exactitud | recall y precisión ≥ 0.95 | 1.00 / 1.00 | Cumple |
| Fundamentación | acierto@5 ≥ 0.85; fidelidad ≥ 4; S2 ≤ 5 % | 0.52; —; 0.0 % | Sin dato |
| Seguridad | ≥ 90 % bien manejadas; ≤ 10 % falsos positivos | 100 %; 0.0 % | Cumple (indicativo) |
| Latencia | p95 ≤ 15 s rápida, ≤ 45 s completa; caché exacta ≤ 300 ms | 1.94 s; 2.52 s; 23.8 ms | Cumple (indicativo) |
| Privacidad | 0 datos personales | 0 | Cumple |
| Disponibilidad | 0 errores 500; termina con el respaldo | 0 errores 500; 5 de 5 | Cumple |
| Modificabilidad | cambiar la base vectorial toca un adaptador | prueba de arquitectura y adaptador en memoria | Cumple (pytest) |
| Recursos | memoria pico ≤ 40 GB | — | Sin dato |
| Reproducibilidad | un tercero lo levanta en ≤ 30 min | **DATO MANUAL** | Sin dato |

## Pendientes del informe, en orden

### Portada · Docente
**DATO MANUAL**: nombre del docente.

### Resumen · resultados principales

En los 20 casos, el analizador obtuvo un recall de 1.00 y una precisión de 1.00 en los hallazgos. La sección de norma esperada apareció entre los cinco primeros fragmentos en el 52 % de los hallazgos, y la fidelidad media al contexto fue de — sobre 5. La latencia p95 por auditoría fue de 1.94 s en la ruta rápida y 2.52 s en la completa. Los guardrails manejaron bien el 100 % de las entradas problemáticas, con 0 % de falsos positivos.

### 2.3 · Número de fragmentos

Tras la ingesta, el corpus produce **31** fragmentos indexados en ChromaDB (800 caracteres, solape 120).

### Tabla 2 · Composición del corpus

| Fuente | Formato | Licencia | Docs. | Págs. | Fragm. |
|---|---|---|---|---|---|
| Blender Manual | Markdown | CC-BY-SA-4.0 | 1 | 2 | 10 |
| Documentación de Godot Engine | Markdown | CC-BY-3.0 | 1 | 1 | 2 |
| Especificación glTF 2.0 | Markdown | CC-BY-4.0 | 1 | 1 | 4 |
| Guía de entrega (autor) | Markdown | propio | 1 | 2 | 12 |
| Rúbrica de animación (autor) | Markdown | propio | 1 | 1 | 3 |
| **Total** (mínimo sugerido: 20 documentos o 50 páginas) |  |  | 5 | 7 | 31 |

Las páginas de PDF son reales; las de HTML y Markdown son equivalentes de 3000 caracteres (anótalo en el pie de la tabla). La columna de fragmentos es opcional.

**Licencia de glTF 2.0** (el «[Pendiente: verificar]»): el HTML del registro de Khronos está bajo la *Khronos Specification License* (uso y reproducción sin modificar, sin costo; no concede patentes ni marcas); las fuentes AsciiDoc del repositorio de Khronos, bajo CC BY 4.0. Pon la que corresponda al archivo que ingeriste y confírmala en el registro.

### Tabla 8 · Modelos de lenguaje

| Modelo | Cuantización | Contexto | Calidad | Español | Lat. p50 / p95 (s) | tok/s | Memoria (GB) |
|---|---|---|---|---|---|---|---|
| gemma4:e2b | **DATO MANUAL** | **DATO MANUAL** | — | — | 0.02 / 2.24 | — | — |
| qwen3:8b | **DATO MANUAL** | **DATO MANUAL** | — | — | 0.02 / 1.90 | — | — |
| gpt-oss:20b | **DATO MANUAL** | **DATO MANUAL** | — | — | 0.02 / 2.04 | — | — |

La cuantización y el contexto salen de `ollama show` (los «?» de la columna de características). La carga en frío va aparte, en el texto: gemma4:e2b — s, qwen3:8b — s, gpt-oss:20b — s.

### Tabla 9 · Embeddings

| Modelo | Acierto@1 | Acierto@5 | MRR | Indexado (s) | Rechazos (umbral 0.55) |
|---|---|---|---|---|---|
| bge-m3 | 0.63 | 0.93 | 0.77 | 0.1 | 10 de 10 |
| embeddinggemma | 0.63 | 0.93 | 0.77 | 0.0 | 10 de 10 |
| nomic-embed-text | 0.63 | 0.93 | 0.77 | 0.0 | 10 de 10 |

Acierto y MRR se midieron sin umbral (solo el orden); la columna de rechazos es opcional en el informe y puede ir en el texto.

### 6.4.1 · Conclusión de la selección
La tabla 8 no tiene calidad (la corrida fue sin `--juez`), así que la elección de modelos de lenguaje no puede justificarse todavía; se mantiene la propuesta del ADR-01. Para los embeddings se adopta **embeddinggemma** (acierto@5 0.93, MRR 0.77); embeddinggemma iguala a bge-m3 y es más ligero, que es la condición del ADR-02 para preferirlo.

### Sección 8 · Evidencia de cada ADR

- **ADR-01 (tabla 8):** gemma4:e2b: calidad —, p95 2.24 s; qwen3:8b: calidad —, p95 1.90 s; gpt-oss:20b: calidad —, p95 2.04 s.
- **ADR-02 (tabla 9):** bge-m3: acierto@5 0.93, MRR 0.77; embeddinggemma: acierto@5 0.93, MRR 0.77; nomic-embed-text: acierto@5 0.93, MRR 0.77.
- **ADR-03 (tabla 22):** 0.85: recall 0.50, precisión 0.71; 0.9: recall 0.30, precisión 0.75; 0.92: recall 0.20, precisión 0.67; 0.95: recall 0.20, precisión 0.67.
- **ADR-04 (tabla 21):** 40 de 40 casos (100 %) a una ruta adecuada; 0 enviados a la completa sin necesidad; p95 rápida 1.94 s y completa 2.52 s.
- **ADR-05 (tabla 19):** 100 % de las 13 entradas problemáticas bien manejadas y 0 % de falsos positivos en las 10 normales.
- **ADR-06 (tablas 17 y 18):** 500 car., solape 75, k=8: acierto@k 0.07; 800 car., solape 120, k=5: acierto@k 0.07; 1000 car., solape 150, k=4: acierto@k 0.00. Con 800/120 y umbral 0.55: @3 0.07; @5 0.07; @8 0.07, 10 de 10 rechazos.
- **ADR-07 (tabla 20):** 1 de 38 consultas pobres superan el umbral tras reformular, con 2.95 reformulaciones de media.
- **ADR-08 (tabla 16):** recall 1.00 y precisión 1.00; S3 eliminó 0 frases con cifras sin respaldo.

Cuando una evidencia confirme su decisión, cambia el «Estado» del ADR de «Propuesta» a «Aceptada».

### Tabla 16 · Calidad del producto

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Recall de hallazgos | 1.0 | — |
| Precisión de hallazgos | 1.0 | — |
| Acierto@5 de la sección esperada | 0.517 | – |
| Fidelidad al contexto (0–5) | — | — |
| Relevancia de la corrección (0–5) | — | — |
| Citas inventadas detectadas por S2 (% de las citas) | 0.0 | – |
| Cifras sin respaldo eliminadas por S3 | 0 | — |
| Diferencia media juez–autor (15 casos) | — | – |
| Acuerdo juez–autor, diferencia ≤ 1 punto (%) | — | – |
| Hallazgos servidos desde la caché de hallazgos | 0 | – |

El informe tiene una sola fila juez–autor: pon la diferencia media en «Con RAG» y el % de acuerdo en el texto de la sección 9.1, o añade la fila.

### Tabla 17 · Tamaño de fragmento

| Fragmento | k | Fragm. | Acierto@k | MRR |
|---|---|---|---|---|
| 500 car., solape 75 | 8 | 46 | 0.07 | 0.07 |
| 800 car., solape 120 | 5 | 31 | 0.07 | 0.07 |
| 1000 car., solape 150 | 4 | 21 | 0.00 | 0.00 |

### Tabla 18 · Barrido de k y umbral

| Umbral | @3 | @5 | @8 | Rechazos (de 10) |
|---|---|---|---|---|
| 0.4 | 0.37 | 0.37 | 0.37 | 10 |
| 0.5 | 0.13 | 0.13 | 0.13 | 10 |
| 0.55 | 0.07 | 0.07 | 0.07 | 10 |
| 0.6 | 0.03 | 0.03 | 0.03 | 10 |
| 0.7 | 0.00 | 0.00 | 0.00 | 10 |

### Tabla 19 · Guardrails de entrada

| Entrada | Casos | Correctos | Falsos pos. |
|---|---|---|---|
| Inyección (E2) | 4 | 4 | – |
| Fuera de dominio (E4) | 3 | 3 | – |
| Datos personales (E3) | 3 | 3 | – |
| Documentos (E5) | 3 | 3 | – |
| Normales | 10 | – | 0 |
| Total | 23 | 100.0 % | 0.0 % |

### Tabla 20 · Ciclo de agente

| Métrica | Valor |
|---|---|
| Superan el umbral tras reformular | 1 de 38 |
| Reformulaciones promedio | 2.95 |
| Terminan en «sin norma» | 37 |
| Latencia adicional media (s) | 0.0 |

### Tabla 21 · Enrutador

| Ruta esperada | Casos | Adec. | Lat. p50 / p95 (s) |
|---|---|---|---|
| Sin modelo | 17 | 17 | 0.01 / 0.43 |
| Rápida | 12 | 12 | 0.03 / 1.94 |
| Completa | 11 | 11 | 0.03 / 2.52 |
| A la completa sin necesidad |  | 0 |  |

### Tabla 22 · Caché

| Umbral | Recall | Precisión | Falsos pos. | Ahorro (ms) |
|---|---|---|---|---|
| 0.85 | 0.50 | 0.71 | 2 | 9.3 |
| 0.9 | 0.30 | 0.75 | 1 | 9.1 |
| 0.92 | 0.20 | 0.67 | 1 | 8.6 |
| 0.95 | 0.20 | 0.67 | 1 | 8.7 |
| Exacta (20 repetidas) | 1.00 | 1.00 | 0 | 221.9 |

p95 de una auditoría servida por la caché exacta: 23.8 ms (meta ≤ 300 ms).

### Tabla 23 · Latencia por capa (ms)

| Etapa | Mediana | p95 | Máxima |
|---|---|---|---|
| Guardrails de entrada | 0.3 | 14.7 | 17.3 |
| Caché (consultas) | 0.0 | 0.1 | 0.1 |
| Análisis de malla | 5.3 | 2106.8 | 2215.8 |
| Recuperación (incluye agente) | 10.2 | 21.9 | 24.4 |
| Gateway, ruta rápida | 0.2 | 0.2 | 0.2 |
| Gateway, ruta completa | 0.1 | 0.2 | 0.3 |
| Guardrails de salida | 0.3 | 1.1 | 1.7 |
| Total por auditoría | 20.3 | 2155.0 | 2260.7 |

### 9.2 · Valor medido con el revisor independiente

**DATO MANUAL**: completa la tabla con la prueba de las cinco mallas y pega el párrafo.

| Malla | Tiempo manual (min) | Tiempo MeshAudit (s) | Hallazgos del revisor | Encontrados por MeshAudit |
|---|---|---|---|---|
| malla 1 |  |  |  |  |
| malla 2 |  |  |  |  |
| malla 3 |  |  |  |  |
| malla 4 |  |  |  |  |
| malla 5 |  |  |  |  |

Texto: «El revisor tardó en promedio X min por malla; MeshAudit, Y s. De los N hallazgos del revisor, la herramienta encontró M (P %); los restantes eran aspectos que las reglas no miden, como …».

### 9.2 · Fallas y retroalimentación

En las fallas inyectadas se registraron **0** errores 500 y **5** de 5 auditorías terminaron con el respaldo. Durante las pruebas se registraron **0** calificaciones de retroalimentación, con una tasa de utilidad de **—**.

No hay calificaciones: usa la aplicación web en las pruebas o pasa `--datos` con tu `data/`.

### 9.3 · Análisis de errores
- **Analizador.** Sin hallazgos no detectados ni falsos en los 20 casos.
- **Sin norma.** 22 hallazgos terminaron «sin norma aplicable»; la causa más probable es la recuperación (acierto@5 de la sección esperada = 0.52). Citas eliminadas por S2: 0.0 % de las citas generadas.
- **Caché semántica.** Aciertos equivocados (distractores servidos): umbral 0.85: «¿Qué es TEXCOORD_1 en glTF?» (1.000), «¿Cuántos triángulos puede tener un escenario de juego móvil?» (0.865); umbral 0.9: «¿Qué es TEXCOORD_1 en glTF?» (1.000); umbral 0.92: «¿Qué es TEXCOORD_1 en glTF?» (1.000); umbral 0.95: «¿Qué es TEXCOORD_1 en glTF?» (1.000).
- **Guardrails.** Ninguna entrada problemática mal manejada ni falsos positivos.
- **Enrutador.** Sin juez, la ruta esperada salió de la misma regla: la tabla 21 es circular.
- **Agente.** De 38 consultas con recuperación pobre, 1 superan el umbral tras reformular.
- **Latencia.** Casos en el p95 o por encima: P13 (2.2 s).

### 9.4 · Mejoras que surgen del análisis
- El acierto@5 (0.52) queda bajo la meta de 0.85: ajustar los títulos de sección de `perfiles.yaml` a los del corpus real y probar la búsqueda híbrida con BM25.
- Añadir al prompt de reformulación los términos que el agente no logró traducir.
- Con 0.92 la caché semántica sirvió distractores: subir el umbral o exigir la misma verificación.

### Referencias · versiones

- Blender Manual (versión **DATO MANUAL**): la del manual que descargaste; puedes declararla como `version:` en `corpus/fuentes.yaml` y este script la toma.
- trimesh (versión 5.2.0): la instalada al generar este archivo; en el Mac, la de `pip show trimesh`.

### 10.3 · Declaración de uso de asistentes de IA
Ver el texto propuesto en `docs/REVISION_INFORME.md`, sección 3: hay que decirlo con exactitud, porque el código no es solo un esqueleto.
