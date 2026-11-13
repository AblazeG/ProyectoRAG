# Insumos para completar el informe técnico

Generado con `evaluacion/insumos_informe.py` desde `evaluacion/resultados`. Corrida: proveedor `ollama`, juez sí, 5 corridas por caso.

## Estado de las metas (tabla 5)

| Atributo | Meta | Medido | Estado |
|---|---|---|---|
| Exactitud | recall y precisión ≥ 0.95 | 1.00 / 0.98 | Cumple |
| Fundamentación | acierto@5 ≥ 0.85; fidelidad ≥ 4; S2 ≤ 5 % | 0.26; 2.87; 1.1 % | No cumple |
| Seguridad | ≥ 90 % bien manejadas; ≤ 10 % falsos positivos | 92.3 %; 0.0 % | Cumple |
| Latencia | p95 ≤ 15 s rápida, ≤ 45 s completa; caché exacta ≤ 300 ms | 2.33 s; 15.67 s; 18.9 ms | Cumple |
| Privacidad | 0 datos personales | 0 | Cumple |
| Disponibilidad | 0 errores 500; termina con el respaldo | 0 errores 500; 5 de 5 | Cumple |
| Modificabilidad | cambiar la base vectorial toca un adaptador | prueba de arquitectura y adaptador en memoria | Cumple (pytest) |
| Recursos | memoria pico ≤ 40 GB | 20.8 GB | Cumple |
| Reproducibilidad | un tercero lo levanta en ≤ 30 min | **DATO MANUAL** | Sin dato |

## Pendientes del informe, en orden

### Portada · Docente
**DATO MANUAL**: nombre del docente.

### Resumen · resultados principales

En los 20 casos, el analizador obtuvo un recall de 1.00 y una precisión de 0.98 en los hallazgos. La sección de norma esperada apareció entre los cinco primeros fragmentos en el 26 % de los hallazgos, y la fidelidad media al contexto fue de 2.87 sobre 5. La latencia p95 por auditoría fue de 2.33 s en la ruta rápida y 15.67 s en la completa. Los guardrails manejaron bien el 92 % de las entradas problemáticas, con 0 % de falsos positivos.

### 2.3 · Número de fragmentos

Tras la ingesta, el corpus produce **852** fragmentos indexados en ChromaDB (800 caracteres, solape 120).

### Tabla 2 · Composición del corpus

| Fuente | Formato | Licencia | Docs. | Págs. | Fragm. |
|---|---|---|---|---|---|
| Blender Manual | HTML | CC-BY-SA-4.0 | 8 | 49 | 256 |
| Documentación de Godot Engine | HTML | CC-BY-3.0 | 4 | 12 | 59 |
| Especificación glTF 2.0 | HTML | Khronos-Specification | 1 | 101 | 537 |
| Guía de entrega (autor) | — | — | 0 | 0 | 0 |
| Rúbrica de animación (autor) | — | — | 0 | 0 | 0 |
| **Total** (mínimo sugerido: 20 documentos o 50 páginas) |  |  | 13 | 162 | 852 |

Las páginas de PDF son reales; las de HTML y Markdown son equivalentes de 3000 caracteres (anótalo en el pie de la tabla). La columna de fragmentos es opcional.

**Licencia de glTF 2.0** (el «[Pendiente: verificar]»): el HTML del registro de Khronos está bajo la *Khronos Specification License* (uso y reproducción sin modificar, sin costo; no concede patentes ni marcas); las fuentes AsciiDoc del repositorio de Khronos, bajo CC BY 4.0. Pon la que corresponda al archivo que ingeriste y confírmala en el registro.

### Tabla 8 · Modelos de lenguaje

| Modelo | Cuantización | Contexto | Calidad | Español | Lat. p50 / p95 (s) | tok/s | Memoria (GB) |
|---|---|---|---|---|---|---|---|
| gemma4:e2b | nvfp4 | 131072 | 2.85 | 4.80 | 2.41 / 5.22 | 201 | 8.0 |
| qwen3:8b | Q4_K_M | 40960 | 3.48 | 5.00 | 16.97 / 24.48 | 71.8 | 5.8 |
| gpt-oss:20b | MXFP4 | 131072 | 4.14 | 5.00 | 14.32 / 23.22 | 91.1 | 12.9 |

La cuantización y el contexto salen de `ollama show` (los «?» de la columna de características). La carga en frío va aparte, en el texto: gemma4:e2b 3.9 s, qwen3:8b 3.7 s, gpt-oss:20b 7.8 s.

### Tabla 9 · Embeddings

| Modelo | Acierto@1 | Acierto@5 | MRR | Indexado (s) | Rechazos (umbral 0.55) |
|---|---|---|---|---|---|
| bge-m3 | 0.10 | 0.23 | 0.14 | 19.1 | 7 de 10 |
| embeddinggemma | 0.13 | 0.17 | 0.15 | 14.5 | 8 de 10 |
| nomic-embed-text | 0.03 | 0.10 | 0.06 | 11.0 | 0 de 10 |

Acierto y MRR se midieron sin umbral (solo el orden); la columna de rechazos es opcional en el informe y puede ir en el texto.

### 6.4.1 · Conclusión de la selección
La ruta rápida usa **gemma4:e2b** (calidad 2.85, p95 5.22 s) y la completa **gpt-oss:20b** (calidad 4.14, p95 23.22 s); cada uno es el respaldo del otro. Se sacrifican 1.29 puntos de calidad en los casos simples a cambio de 18 s menos de p95; el compromiso es adecuado porque esos casos tienen hasta tres hallazgos menores y una explicación corta, y las cifras del informe no dependen del modelo (ADR-08). Juntos ocupan 20.8 GB (meta ≤ 40 GB). Para los embeddings se adopta **bge-m3** (acierto@5 0.23, MRR 0.14); nomic-embed-text, centrado en inglés, queda en 0.10 con consultas en español.

### Sección 8 · Evidencia de cada ADR

- **ADR-01 (tabla 8):** gemma4:e2b: calidad 2.85, p95 5.22 s; qwen3:8b: calidad 3.48, p95 24.48 s; gpt-oss:20b: calidad 4.14, p95 23.22 s.
- **ADR-02 (tabla 9):** bge-m3: acierto@5 0.23, MRR 0.14; embeddinggemma: acierto@5 0.17, MRR 0.15; nomic-embed-text: acierto@5 0.10, MRR 0.06.
- **ADR-03 (tabla 22):** 0.85: recall 1.00, precisión 0.83; 0.9: recall 0.90, precisión 1.00; 0.92: recall 0.80, precisión 1.00; 0.95: recall 0.60, precisión 1.00.
- **ADR-04 (tabla 21):** 16 de 34 casos (47 %) a una ruta adecuada; 0 enviados a la completa sin necesidad; p95 rápida 2.33 s y completa 15.67 s.
- **ADR-05 (tabla 19):** 92 % de las 13 entradas problemáticas bien manejadas y 0 % de falsos positivos en las 10 normales.
- **ADR-06 (tablas 17 y 18):** 500 car., solape 75, k=8: acierto@k 0.13; 800 car., solape 120, k=5: acierto@k 0.13; 1000 car., solape 150, k=4: acierto@k 0.13. Con 800/120 y umbral 0.55: @3 0.10; @5 0.13; @8 0.13, 7 de 10 rechazos.
- **ADR-07 (tabla 20):** 9 de 27 consultas pobres superan el umbral tras reformular, con 2.37 reformulaciones de media.
- **ADR-08 (tabla 16):** recall 1.00 y precisión 0.98; S3 eliminó 0 frases con cifras sin respaldo.

Cuando una evidencia confirme su decisión, cambia el «Estado» del ADR de «Propuesta» a «Aceptada».

### Tabla 16 · Calidad del producto

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Recall de hallazgos | 1.0 | — |
| Precisión de hallazgos | 0.982 | — |
| Acierto@5 de la sección esperada | 0.255 | – |
| Fidelidad al contexto (0–5) | 2.87 | 2.17 |
| Relevancia de la corrección (0–5) | 3.74 | 4.33 |
| Citas inventadas detectadas por S2 (% de las citas) | 1.1 | – |
| Cifras sin respaldo eliminadas por S3 | 0 | — |
| Diferencia media juez–autor (15 casos) | — | – |
| Acuerdo juez–autor, diferencia ≤ 1 punto (%) | — | – |
| Hallazgos servidos desde la caché de hallazgos | 10 | – |

El informe tiene una sola fila juez–autor: pon la diferencia media en «Con RAG» y el % de acuerdo en el texto de la sección 9.1, o añade la fila.

### Tabla 17 · Tamaño de fragmento

| Fragmento | k | Fragm. | Acierto@k | MRR |
|---|---|---|---|---|
| 500 car., solape 75 | 8 | 1351 | 0.13 | 0.12 |
| 800 car., solape 120 | 5 | 852 | 0.13 | 0.11 |
| 1000 car., solape 150 | 4 | 682 | 0.13 | 0.11 |

### Tabla 18 · Barrido de k y umbral

| Umbral | @3 | @5 | @8 | Rechazos (de 10) |
|---|---|---|---|---|
| 0.4 | 0.13 | 0.20 | 0.20 | 1 |
| 0.5 | 0.10 | 0.17 | 0.17 | 4 |
| 0.55 | 0.10 | 0.13 | 0.13 | 7 |
| 0.6 | 0.10 | 0.10 | 0.10 | 9 |
| 0.7 | 0.03 | 0.03 | 0.03 | 10 |

### Tabla 19 · Guardrails de entrada

| Entrada | Casos | Correctos | Falsos pos. |
|---|---|---|---|
| Inyección (E2) | 4 | 4 | – |
| Fuera de dominio (E4) | 3 | 3 | – |
| Datos personales (E3) | 3 | 2 | – |
| Documentos (E5) | 3 | 3 | – |
| Normales | 10 | – | 0 |
| Total | 23 | 92.3 % | 0.0 % |

### Tabla 20 · Ciclo de agente

| Métrica | Valor |
|---|---|
| Superan el umbral tras reformular | 9 de 27 |
| Reformulaciones promedio | 2.37 |
| Terminan en «sin norma» | 24 |
| Latencia adicional media (s) | 0.22 |

### Tabla 21 · Enrutador

| Ruta esperada | Casos | Adec. | Lat. p50 / p95 (s) |
|---|---|---|---|
| Sin modelo | 3 | 3 | 0.02 / 0.02 |
| Rápida | 0 | 0 |  |
| Completa | 31 | 13 | 2.27 / 15.60 |
| Sin etiqueta (excluidos) | 6 | – |  |
| A la completa sin necesidad |  | 0 |  |

### Tabla 22 · Caché

| Umbral | Recall | Precisión | Falsos pos. | Ahorro (ms) |
|---|---|---|---|---|
| 0.85 | 1.00 | 0.83 | 2 | 716.3 |
| 0.9 | 0.90 | 1.00 | 0 | 692.1 |
| 0.92 | 0.80 | 1.00 | 0 | 718.4 |
| 0.95 | 0.60 | 1.00 | 0 | 593.6 |
| Exacta (20 repetidas) | 0.95 | 1.00 | 0 | 2530 |

p95 de una auditoría servida por la caché exacta: 18.9 ms (meta ≤ 300 ms).

### Tabla 23 · Latencia por capa (ms)

| Etapa | Mediana | p95 | Máxima |
|---|---|---|---|
| Guardrails de entrada | 0.2 | 16.5 | 21.6 |
| Caché (consultas) | 0.0 | 0.1 | 0.1 |
| Análisis de malla | 5.6 | 977.9 | 1229.4 |
| Recuperación (incluye agente) | 332.4 | 759.7 | 821.3 |
| Gateway, ruta rápida | 1462.2 | 2284.1 | 3151.3 |
| Gateway, ruta completa | 5638.8 | 13056.8 | 13521.8 |
| Guardrails de salida | 3.5 | 7.6 | 8.4 |
| Total por auditoría | 3020.8 | 13274.4 | 14191.3 |

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

En las fallas inyectadas se registraron **0** errores 500 y **5** de 5 auditorías terminaron con el respaldo. Durante las pruebas se registraron **2** calificaciones de retroalimentación, con una tasa de utilidad de **50 %**.

### 9.3 · Análisis de errores
- **Analizador.** Falsos: V10 en P07. 
- **Sin norma.** 24 hallazgos terminaron «sin norma aplicable»; la causa más probable es la recuperación (acierto@5 de la sección esperada = 0.26). Citas eliminadas por S2: 1.1 % de las citas generadas.
- **Caché semántica.** Aciertos equivocados (distractores servidos): umbral 0.85: «¿Qué es TEXCOORD_1 en glTF?» (0.893), «¿Cuántos triángulos puede tener un escenario de juego móvil?» (0.890).
- **Guardrails.** Mal manejados: G10 (datos_personales, código 422). 
- **Enrutador.** Ruta equivocada en E02 (esperada completa, tomó rapida), E09 (esperada completa, tomó rapida), E10 (esperada completa, tomó rapida), E12 (esperada completa, tomó rapida), E13 (esperada completa, tomó rapida), E16 (esperada completa, tomó rapida), E17 (esperada completa, tomó rapida), E18 (esperada completa, tomó rapida), E20 (esperada completa, tomó rapida), E21 (esperada completa, tomó rapida), E22 (esperada completa, tomó rapida), E24 (esperada completa, tomó rapida), E25 (esperada completa, tomó rapida), E29 (esperada completa, tomó rapida), E33 (esperada completa, tomó rapida), E37 (esperada completa, tomó rapida), E38 (esperada completa, tomó rapida), E40 (esperada completa, tomó rapida).
- **Enrutador.** 6 casos quedaron sin etiqueta (nada que calificar).
- **Agente.** De 27 consultas con recuperación pobre, 9 superan el umbral tras reformular. Superan el umbral pero citan otra sección: A01, A02, A06, R02, R04, R10, R12, R18, R20.
- **Latencia.** Casos en el p95 o por encima: P04 (13.5 s).
- **Retroalimentación.** Calificados como no útiles: h1 (no me sirvió).

### 9.4 · Mejoras que surgen del análisis
- El acierto@5 (0.26) queda bajo la meta de 0.85: ajustar los títulos de sección de `perfiles.yaml` a los del corpus real y probar la búsqueda híbrida con BM25.
- Añadir al prompt de reformulación los términos que el agente no logró traducir.

### Referencias · versiones

- Blender Manual (versión Blender 5.3 Manual): la del manual que descargaste; puedes declararla como `version:` en `corpus/fuentes.yaml` y este script la toma.
- trimesh (versión 5.2.0): la instalada al generar este archivo; en el Mac, la de `pip show trimesh`.

### 10.3 · Declaración de uso de asistentes de IA
Ver el texto propuesto en `docs/REVISION_INFORME.md`, sección 3: hay que decirlo con exactitud, porque el código no es solo un esqueleto.
