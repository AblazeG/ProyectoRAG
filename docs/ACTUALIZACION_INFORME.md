# MeshAudit · Datos reales para actualizar el informe técnico

**Para:** quien edite `Informe_tecnico_MeshAudit`.
**Fecha de la corrida:** 13 de noviembre de 2026.
**Sustituye:** las cifras provisionales de `docs/ENTREGA_PARA_EL_INFORME.md`, sección 5. Las secciones 3 y 4 de ese documento siguen vigentes, con los cambios del punto 2.4 de este.

Las tablas de este documento salen de los CSV de `evaluacion/resultados/`. La versión que genera el script está en `evaluacion/resultados/INSUMOS_INFORME.md`, y las filas en LaTeX, en `tablas_informe.tex`.

---

## 0. Qué hacer, en orden

1. **Quitar la nota provisional.** Quita «Datos provisionales» de los pies de tabla y el párrafo provisional de la sección 9.2. Usa en su lugar el párrafo del punto 1.2.
2. **Copiar las tablas.** Sustituye las cifras de las tablas 2, 5, 8, 9 y 16–23 por las de la sección 3.
3. **Aplicar las correcciones de texto.** Son las de `ENTREGA_PARA_EL_INFORME.md`, sección 3, más las tres nuevas del punto 2.4 de este documento.
4. **Escribir la conclusión 6.4.1 y el análisis de errores 9.3.** Parte de los textos de la sección 4 y ajústalos con tu criterio.
5. **Decidir el estado de cada ADR.** La sección 5 trae una recomendación; la decisión es tuya.
6. **Completar los datos manuales.** Están en la sección 6; ningún script puede llenarlos.

---

## 1. Condiciones de la corrida

### 1.1 Entorno

| Elemento | Valor |
|---|---|
| Equipo | Mac con Apple M4 Max, 128 GB de memoria unificada |
| Ollama | 0.40.16 (`OLLAMA_NO_CLOUD=1`) |
| Modelos | gemma4:e2b (rápida), gpt-oss:20b (completa), qwen3:8b (candidato), mistral-small3.2:24b (juez); bge-m3, embeddinggemma y nomic-embed-text (embeddings) |
| Python / trimesh | 3.11.15 / 5.2.0 |
| Blender (mutaciones) | 5.2.2 LTS, modo `-b` |
| Corpus | 13 documentos HTML reales: 8 páginas del manual de Blender 5.3, 4 de la documentación de Godot 4.x y la especificación glTF 2.0. En total, 852 fragmentos. |
| Mallas base | 5 modelos CC0 de Kenney (desk, loaf, tower-square-top, plantSmall3 y cardboardBoxClosed), con una mutación M1–M5 cada uno, hecha en Blender |
| Juez | mistral-small3.2:24b, con `--juez` |
| Pruebas automatizadas | 258 de 258 pasan |

### 1.2 Párrafo para el inicio de la sección 9.2

Reemplaza el párrafo provisional por este:

> Los resultados se obtuvieron en el equipo local (Apple M4 Max, 128 GB) con los modelos servidos por Ollama, el corpus normativo real (13 documentos HTML del manual de Blender, la documentación de Godot y la especificación glTF 2.0; 852 fragmentos) y cinco mallas CC0 mutadas con Blender según la tabla 3. La calidad de las explicaciones la calificó un juez LLM (mistral-small3.2:24b). Los dos documentos propios del autor, la guía de entrega y la rúbrica de animación, todavía no forman parte del corpus. Por eso 12 de las 30 consultas con respuesta del conjunto de recuperación no tienen documento que recuperar, y eso baja las métricas de fundamentación (sección 9.3).

En el Resumen, quita «(resultados provisionales; ver sección 9.2)».

---

## 2. Cambios al producto durante las pruebas locales

El informe debe describir el producto tal como quedó. Todos los cambios están en el repositorio y anotados en `docs/PRUEBAS_LOCALES.md`, en el «Registro de incidencias».

### 2.1 Cambios que afectan al texto del informe

| Cambio | Dónde | Qué cambiar en el informe |
|---|---|---|
| **E4**: el umbral de fuera de dominio pasa de **0.30 a 0.40** | `config/servicio.yaml` | Sección 2 de ENTREGA («Parámetros»), tabla 13 (E4) y ADR-05. Calibración: las preguntas fuera de dominio llegan como mucho a 0.35 de similitud y las normales empiezan en 0.48. Con 0.30, dos de las tres preguntas fuera de dominio pasaban. |
| **E2**: el clasificador few-shot recibe el texto **ya enmascarado por E3** y tiene un ejemplo negativo con datos de contacto | `servicio/guardrails/entrada.py` | Tabla 13 (E2) y figura del flujo de guardrails si muestra el orden. Los patrones de E2 siguen revisando el texto original. Motivo: gemma4:e2b tomaba «escríbeme a correo@…» o una CURP por inyección. Además, así los datos personales no llegan al modelo. |
| Los embeddings falsos de las pruebas conservan E4 = 0.30 (`umbral_fuera_dominio_falso`) | `servicio/composicion.py` | Ninguno. Si el informe menciona el modo sin Ollama, añade que los umbrales se calibran por modelo de embeddings, como ya dice el ADR-02. |

### 2.2 Cambios en la ingesta y en la evaluación (no cambian el diseño)

- **Ingesta de HTML.** Se descartan las anclas «¶» de Sphinx (`headerlink`) y el aviso de versión inestable de Godot (`latest-notice`). Puedes añadir a la sección 7 (ingesta) que también se quita el ruido de navegación y los avisos de versión.
- **Punteros `norma` de `config/perfiles.yaml`.** Apuntan a los `doc_id` y secciones del corpus real; por ejemplo, `blender_manual_seleccion / Non Manifold` y `gltf_spec / 3.4. Coordinate System and Units`. Si la tabla 11 cita secciones, usa estos nombres.
- **`evaluacion/mutar_blender.py`.** Tenía dos errores que solo aparecen en Blender 5.x en modo `-b`. Ambos se debían a que la malla evaluada no se actualizaba: M1 no veía la escala nueva y M2 exportaba las UV que había borrado. Además, ahora cada base recibe solo su mutación (base1→M1…base5→M5), como en la tabla 15.

### 2.3 Cambios que no se hicieron (decisiones del autor)

- **E1 con un `.obj` ilegible responde 415, no 422.** El código lo hace a propósito: 415 significa «no es una malla válida en el formato indicado» y 422 queda para mallas que se leen pero tienen contenido inválido. La corrección 3.4 de ENTREGA («Bloquear (HTTP 413, 415 o 422)») ya cubre los dos casos. Decide si `PRUEBAS_LOCALES.md` debe esperar 415.
- **El umbral de recuperación (0.55) y el de la caché semántica (0.92) no cambian.** La justificación está en la sección 4.

### 2.4 Correcciones nuevas al texto (además de las de ENTREGA, sección 3)

1. **Tabla 13, E4:** «similitud top-1 con el corpus y con el informe < 0.40 (calibrado con bge-m3)».
2. **Tabla 13, E2:** «Patrones sobre el texto original y clasificador few-shot (modelo rápido) sobre el texto ya enmascarado por E3».
3. **Tabla 2 y sección 2.3:** el corpus real tiene 13 documentos y 852 fragmentos; la licencia de glTF es la *Khronos Specification License* (punto 3.1).

---

## 3. Tablas con datos reales

### 3.1 Tabla 2 · Composición del corpus

| Fuente | Formato | Licencia | Docs. | Págs.* | Fragm. |
|---|---|---|---|---|---|
| Blender Manual (5.3) | HTML | CC-BY-SA-4.0 | 8 | 49 | 256 |
| Documentación de Godot Engine (4.x) | HTML | CC-BY-3.0 | 4 | 12 | 59 |
| Especificación glTF 2.0 | HTML | Khronos Specification License | 1 | 101 | 537 |
| Guía de entrega (autor) | — | propio | 0 | 0 | 0 |
| Rúbrica de animación (autor) | — | propio | 0 | 0 | 0 |
| **Total** | | | **13** | **162** | **852** |

\* Páginas equivalentes de 3 000 caracteres (los documentos son HTML). Anótalo en el pie de la tabla.

- Con 162 páginas se cumple el mínimo sugerido de 50 páginas; con 13 documentos no se llega al de 20.
- **Sección 2.3:** «Tras la ingesta, el corpus produce **852** fragmentos indexados en ChromaDB (800 caracteres, solape 120).»
- **Licencia de glTF:** el archivo ingerido es el HTML del registro de Khronos, que está bajo la *Khronos Specification License*. Permite usar y reproducir el texto sin modificarlo y sin costo, y no concede patentes ni marcas. Confírmala en el registro antes de entregar.

### 3.2 Tabla 5 · Estado de las metas

| Atributo | Meta | Medido | Estado |
|---|---|---|---|
| Exactitud | recall y precisión ≥ 0.95 | 1.00 / 0.98 | Cumple |
| Fundamentación | acierto@5 ≥ 0.85; fidelidad ≥ 4; S2 ≤ 5 % | 0.26; 2.87; 1.1 % | **No cumple** (S2 sí) |
| Seguridad | ≥ 90 % bien manejadas; ≤ 10 % falsos positivos | 92.3 %; 0.0 % | Cumple |
| Latencia | p95 ≤ 15 s rápida, ≤ 45 s completa; caché exacta ≤ 300 ms | 2.33 s; 15.67 s; 18.9 ms | Cumple |
| Privacidad | 0 datos personales | 0 en los 5 almacenes | Cumple |
| Disponibilidad | 0 errores 500; termina con el respaldo | 0 errores 500; 5 de 5 | Cumple |
| Modificabilidad | cambiar la base vectorial toca un adaptador | prueba de arquitectura y adaptador en memoria | Cumple (pytest) |
| Recursos | memoria pico ≤ 40 GB | 20.8 GB con los dos modelos del servicio cargados; 27.8 GB de pico observado con `ollama ps` | Cumple |
| Reproducibilidad | un tercero lo levanta en ≤ 30 min | **DATO MANUAL** | Sin dato |

### 3.3 Tabla 8 · Modelos de lenguaje (20 informes por modelo; juez mistral-small3.2:24b)

| Modelo | Cuantización | Contexto | Calidad | Español | Lat. p50 / p95 (s) | tok/s | Memoria (GB) |
|---|---|---|---|---|---|---|---|
| gemma4:e2b | NVFP4 | 131 072 | 2.85 | 4.80 | 2.41 / 5.22 | 201 | 8.0 |
| qwen3:8b | Q4_K_M | 40 960 | 3.48 | 5.00 | 16.97 / 24.48 | 71.8 | 5.8 |
| gpt-oss:20b | MXFP4 | 131 072 | 4.14 | 5.00 | 14.32 / 23.22 | 91.1 | 12.9 |

- **Calidad** es la media de fidelidad y relevancia. Las fidelidades son 2.63, 3.02 y 3.58, y las relevancias, 3.07, 3.93 y 4.69.
- **Carga en frío** (va en el texto): gemma4:e2b 3.9 s, qwen3:8b 3.7 s y gpt-oss:20b 7.8 s.
- **Repetición:** la tabla se corrió dos veces, la segunda con las mallas M2 corregidas. Las cifras de arriba son de la segunda corrida. En la primera, las calidades fueron 2.50, 3.41 y 4.19 y el orden fue el mismo.
- **Parámetros:** la columna de parámetros, si la tabla la tiene, es 5.2B, 8.2B y 20.9B (gpt-oss activa unos 3.6B).

### 3.4 Tabla 9 · Embeddings (30 consultas con sección relevante; acierto y MRR sin umbral)

| Modelo | Acierto@1 | Acierto@5 | MRR | Indexado (s) | Rechazos con 0.55 (de 10) |
|---|---|---|---|---|---|
| bge-m3 | 0.10 | 0.23 | 0.14 | 19.1 | 7 |
| embeddinggemma | 0.13 | 0.17 | 0.15 | 14.5 | 8 |
| nomic-embed-text | 0.03 | 0.10 | 0.06 | 11.0 | 0 |

**Pie de la tabla:** «Acierto y MRR se calculan sobre el orden, sin umbral. 12 de las 30 consultas apuntan a los documentos propios del autor, que no están en el corpus, así que el máximo alcanzable es 0.60.»

### 3.5 Tabla 16 · Calidad del producto (20 casos)

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Recall de hallazgos | 1.00 | — |
| Precisión de hallazgos | 0.98 | — |
| Acierto@5 de la sección esperada | 0.26 | – |
| Fidelidad al contexto (0–5) | 2.87 | 2.17 |
| Relevancia de la corrección (0–5) | 3.74 | 4.33 |
| Citas inventadas detectadas por S2 (% de las citas) | 1.1 % | – |
| Cifras sin respaldo eliminadas por S3 | 0 | 0 |
| Diferencia media juez–autor (15 casos) | **DATO MANUAL** | – |
| Acuerdo juez–autor, diferencia ≤ 1 punto (%) | **DATO MANUAL** | – |
| Hallazgos servidos desde la caché de hallazgos | 10 | – |

- La precisión no es 1.00 por un solo «falso»: V10 en P07 (base2_M2, impresión 3D). Al borrar las UV, los vértices de costura quedan en la misma posición y con la misma normal, así que son duplicados reales. La línea base, tomada de la malla con UV, no lo prevé. Es un efecto de la mutación, no un error del analizador (sección 4.6).
- «Sin RAG» tiene mejor relevancia (4.33 frente a 3.74) y peor fidelidad (2.17 frente a 2.87). Interpretación en la sección 4.4.

### 3.6 Tabla 17 · Tamaño de fragmento (mismo presupuesto de unos 4 000 caracteres; umbral 0.55)

| Fragmento | k | Fragm. | Acierto@k | MRR |
|---|---|---|---|---|
| 500 car., solape 75 | 8 | 1 351 | 0.13 | 0.12 |
| 800 car., solape 120 | 5 | 852 | 0.13 | 0.11 |
| 1000 car., solape 150 | 4 | 682 | 0.13 | 0.11 |

### 3.7 Tabla 18 · Barrido de k y umbral (800/120)

| Umbral | @3 | @5 | @8 | Rechazos (de 10) |
|---|---|---|---|---|
| 0.40 | 0.13 | 0.20 | 0.20 | 1 |
| 0.50 | 0.10 | 0.17 | 0.17 | 4 |
| 0.55 | 0.10 | 0.13 | 0.13 | 7 |
| 0.60 | 0.10 | 0.10 | 0.10 | 9 |
| 0.70 | 0.03 | 0.03 | 0.03 | 10 |

### 3.8 Tabla 19 · Guardrails de entrada (E4 = 0.40)

| Entrada | Casos | Correctos | Falsos pos. |
|---|---|---|---|
| Inyección (E2) | 4 | 4 | – |
| Fuera de dominio (E4) | 3 | 3 | – |
| Datos personales (E3) | 3 | 2 | – |
| Documentos (E5) | 3 | 3 | – |
| Normales | 10 | – | 0 |
| **Total** | 23 | **92.3 %** | **0.0 %** |

- **Caso fallido:** G10, una nota con CURP. El clasificador E2 la tomó por inyección y respondió 422, aunque la CURP ya llegó enmascarada. En la corrida anterior al cambio del punto 2.1 fallaban G08 (correo) y G10, con un total de 84.6 %.

### 3.9 Tabla 20 · Ciclo de agente

| Métrica | Valor |
|---|---|
| Superan el umbral tras reformular | 9 de 27 |
| Reformulaciones promedio | 2.37 |
| Terminan en «sin norma» | 24 |
| Latencia adicional media (s) | 0.22 |

- **Superan el umbral pero citan otra sección:** A01, A02, A06, R02, R04, R10, R12, R18 y R20.

### 3.10 Tabla 21 · Enrutador (40 casos, ruta esperada etiquetada por calidad con el juez)

| Ruta esperada | Casos | Adec. | Lat. p50 / p95 (s) |
|---|---|---|---|
| Sin modelo | 3 | 3 | 0.02 / 0.02 |
| Rápida | 0 | 0 | — |
| Completa | 31 | 13 | 2.27 / 15.60 |
| Sin etiqueta (excluidos) | 6 | – | — |
| A la completa sin necesidad | | 0 | |

- **Cómo se etiqueta:** un caso espera la ruta rápida solo si el juez califica las explicaciones de gemma4:e2b con un mínimo de fidelidad y relevancia ≥ 4. Ningún caso llegó a 4, así que 18 casos que el enrutador mandó a la ruta rápida cuentan como inadecuados.
- **Resultado:** 16 de 34 casos etiquetados (47 %) fueron a una ruta adecuada.
- **Casos sin etiqueta:** son 6. No tienen ningún hallazgo con norma que calificar.

### 3.11 Tabla 22 · Caché semántica y exacta

| Umbral | Recall | Precisión | Falsos pos. | Ahorro (ms) |
|---|---|---|---|---|
| 0.85 | 1.00 | 0.83 | 2 | 716 |
| 0.90 | 0.90 | 1.00 | 0 | 692 |
| **0.92** | 0.80 | 1.00 | 0 | 718 |
| 0.95 | 0.60 | 1.00 | 0 | 594 |
| Exacta (20 repetidas) | 0.95 | 1.00 | 0 | 2 530 |

- **Caché exacta:** el p95 de una auditoría servida por ella es de 18.9 ms (meta ≤ 300 ms).
- **Variación entre corridas:** el recall cambia de una corrida a otra porque solo se guardan las respuestas que pasan S1–S3. Con 0.92 fue 0.9 en la primera corrida y 0.8 en la segunda; la precisión fue 1.00 en las dos.
- **La miss de la exacta:** las 20 repeticiones exactas dan 0.95 por la misma causa. Una respuesta corregida por S2 no se guarda.

### 3.12 Tabla 23 · Latencia por capa (ms; caché desactivada)

| Etapa | Mediana | p95 | Máxima |
|---|---|---|---|
| Guardrails de entrada | 0.2 | 16.5 | 21.6 |
| Caché (consultas) | 0.0 | 0.1 | 0.1 |
| Análisis de malla | 5.6 | 977.9 | 1 229.4 |
| Recuperación (incluye agente) | 332.4 | 759.7 | 821.3 |
| Gateway, ruta rápida | 1 462.2 | 2 284.1 | 3 151.3 |
| Gateway, ruta completa | 5 638.8 | 13 056.8 | 13 521.8 |
| Guardrails de salida | 3.5 | 7.6 | 8.4 |
| Total por auditoría | 3 020.8 | 13 274.4 | 14 191.3 |

- **Análisis de malla:** el p95 de casi 1 s corresponde a base4_M4, de más de 100 000 triángulos.
- **Guardrails de entrada:** el p95 de 16 ms incluye el clasificador E2 cuando la caché tiene la respuesta del modelo.

### 3.13 Sección 9.2 · Fallas, privacidad y retroalimentación

- **Fallas inyectadas:** F1–F5 son *timeout*, etiqueta inexistente (404 de Ollama) y conexión rechazada, en los dos alias. Hubo **0 errores 500** y **5 de 5** auditorías terminaron con el modelo de respaldo.
- **Privacidad:** hubo **0** datos personales en trazas, caché exacta, caché semántica, retroalimentación e informes.
- **Retroalimentación:** el CSV tiene 2 calificaciones, pero **son de prueba**: las hizo la fase 4 para probar el endpoint. No las presentes como de usuarios. Texto sugerido: «Durante la evaluación no hubo usuarios reales; el endpoint de retroalimentación se probó con dos calificaciones de prueba y el comentario con correo y teléfono quedó enmascarado.» Las calificaciones reales salen de la prueba con personas (fase 9).

---

## 4. Textos de interpretación (para 6.4.1, 9.3 y 9.4)

### 4.1 Sección 6.4.1 · Conclusión de la selección

> La ruta rápida usa **gemma4:e2b** (calidad 2.85, p95 5.2 s) y la completa **gpt-oss:20b** (calidad 4.14, p95 23.2 s); cada uno es el respaldo del otro. qwen3:8b mejora la calidad de la ruta rápida (3.48), pero su p95 de 24.5 s supera la meta de 15 s, así que no la reemplaza; en la completa queda por debajo de gpt-oss:20b en calidad y no lo supera en latencia. Juntos, los dos modelos del servicio ocupan 20.8 GB (pico observado: 27.8 GB), dentro del tope de 40 GB. Para los embeddings se mantiene **bge-m3**: tiene el mejor acierto@5 (0.23 frente a 0.17 de embeddinggemma y 0.10 de nomic-embed-text). embeddinggemma lo iguala en MRR (0.15 frente a 0.14), pero no en acierto@5, que es la condición del ADR-02 para preferirlo. nomic-embed-text, centrado en inglés, no rechaza ninguna consulta sin respaldo con el umbral 0.55.

**Cuidado.** La calidad de gemma4:e2b (2.85) es baja. El enrutador manda a la ruta rápida los casos con pocos hallazgos menores, y en esos casos el juez nunca le dio a gemma4:e2b un 4 o más (tabla 21). La conclusión sigue en pie porque las mediciones no dependen del modelo (ADR-08), pero el informe debe reconocerlo (punto 4.4).

### 4.2 Umbrales (fase 7)

- **Recuperación: se mantiene 0.55.** En la tabla 18, aciertos@5 + rechazos correctos suman 9 con 0.50, 11 con 0.55 y 12 con 0.60: la diferencia entre 0.55 y 0.60 es de un solo caso. Además, con el corpus incompleto la calibración no es fiable. Recalibrar cuando entren la guía y la rúbrica.
- **Caché semántica: se mantiene 0.92.** 0.90 y 0.92 tienen precisión 1.00. El distractor más cercano («¿Qué es TEXCOORD_1 en glTF?») llega a 0.893, así que 0.92 deja margen. Con 0.85 se sirven dos distractores.
- **E4: pasa a 0.40** (punto 2.1).

### 4.3 Sección 9.3 · Análisis de errores

- **Analizador.** Recall 1.00. El único «falso positivo» es V10 en P07: al quitar las UV en M2, los vértices de costura quedan duplicados de verdad, y la línea base, medida antes de la mutación, no lo prevé (punto 4.6). Las mutaciones de Blender reproducen los defectos de la tabla 3 en todos los formatos tras corregir `mutar_blender.py`.
- **Recuperación (causa principal de «sin norma»).**
  - En los 20 casos, 24 hallazgos terminaron «sin norma aplicable», y el acierto@5 de la sección esperada fue 0.26.
  - Hay tres causas:
    1. **Faltan documentos.** 12 de las 30 consultas (y las verificaciones V1, V2, V11 y las de impresión) apuntan a `guia_entrega` y `rubrica_animacion`, que no se han ingerido.
    2. **Consultas coloquiales.** Frases como «se ve negra en el juego» o «se ve gigante en el visor» no se parecen al texto técnico del manual. Fallan aun después de reformular: 9 de 27 consultas pobres superan el umbral, y de esas, 9 citan una sección distinta de la esperada.
    3. **Títulos de sección genéricos.** El manual de Blender tiene muchas subsecciones llamadas «Opciones». Esos fragmentos pierden el contexto del operador al que pertenecen («Desplegar», «Fusionar»), aparecen arriba en el orden y no coinciden con la sección esperada.
  - Las consultas técnicas directas sí aciertan, por ejemplo «¿Cómo selecciono la geometría non-manifold?» o «¿Cómo recalculo las normales?».
- **Fidelidad.** La fidelidad media con RAG es 2.87. Baja sobre todo cuando el fragmento recuperado es de una sección cercana pero no la esperada, y el juez penaliza que la explicación diga más que el fragmento. S2 detectó un 1.1 % de citas inventadas; S3 no eliminó ninguna cifra, porque las mediciones las inserta la plantilla.
- **Guardrails.** Solo falló G10: el clasificador E2 (gemma4:e2b) tomó por inyección una nota con CURP ya enmascarada. No hubo falsos positivos en las 10 entradas normales.
- **Enrutador.** Ningún caso de la ruta rápida alcanzó 4 con gemma4:e2b. Con un etiquetado por calidad tan exigente, la tabla 21 muestra que la ruta rápida ahorra latencia a costa de calidad, no que el enrutador se equivoque de regla: los casos se enviaron según su regla de gravedades (ADR-04), y 0 fueron a la completa sin necesidad.
- **Caché semántica.** Con 0.92 no se sirvió ningún distractor. Con 0.85 se sirvieron «¿Qué es TEXCOORD_1 en glTF?» (0.893) y «¿Cuántos triángulos puede tener un escenario de juego móvil?» (0.890).
- **Latencia.** Todo queda dentro de la meta. En la primera corrida hubo un caso de la ruta rápida de 52 s: gemma4:e2b agotó el tiempo y respondió gpt-oss:20b como respaldo. En la corrida final, el máximo por auditoría fue de 14.2 s.

### 4.4 Interpretación de «con RAG» frente a «sin RAG»

> Con RAG, la fidelidad sube de 2.17 a 2.87, porque la explicación se apoya en un fragmento citado. La relevancia baja de 4.33 a 3.74. Sin contexto, el modelo da consejos genéricos que el juez considera útiles; con un fragmento poco pertinente, la explicación se ciñe a ese fragmento y pierde utilidad. La mejora de la fundamentación depende, entonces, de la calidad de la recuperación, que es el punto débil de esta versión (acierto@5 de 0.26).

### 4.5 Sección 9.4 · Mejoras que surgen del análisis

1. **Ingerir la guía de entrega y la rúbrica de animación.** Cubren 12 de las 30 consultas y varias verificaciones; después hay que actualizar sus punteros en `perfiles.yaml` y recalibrar el umbral de recuperación.
2. **Heredar el título del padre en subsecciones genéricas** al fragmentar. Por ejemplo, «Desplegar › Opciones» en lugar de «Opciones». Así esos fragmentos no compiten con la sección correcta.
3. **Búsqueda híbrida (BM25 + embeddings)** para los términos exactos de las normas, como «TEXCOORD_0», «Merge by Distance» o «non-manifold».
4. **Prompt de reformulación del agente** con un vocabulario de traducción de síntomas a términos técnicos, por ejemplo «se ve negra» → «normales invertidas» y «gigante» → «unidades/escala».
5. **Ruta rápida.** Probar gemma4:e4b o qwen3:8b sin razonamiento para subir la calidad sin pasar de 15 s, o bajar el umbral de gravedad del enrutador.
6. **Clasificador E2.** Añadir más ejemplos negativos con identificadores enmascarados, o usar el modelo completo solo cuando los patrones no deciden.
7. **Base de la mutación M2.** Calcular la línea base de V10 después de quitar las UV, o quitar las UV sin dejar vértices de costura duplicados.

### 4.6 Nota para la revisión manual de la línea base

- **V8 en base1, base2 y base3.** Son triángulos de relleno con vértices colineales (área 0) que ya vienen en los OBJ de Kenney: desk tiene 5, loaf 4 y tower-square-top 4. Es un defecto real de origen; Blender no lo ve porque mide en float32.
- **V4 y V5 en base1.** Aparecen solo al fusionar vértices coincidentes; sin fusionar, Blender ve la malla cerrada. **Confírmalo tú.**
- **V10 en P07.** Ver el punto 4.3 («Analizador»).

---

## 5. Estado recomendado de los ADR (la decisión es tuya)

| ADR | Evidencia | Recomendación |
|---|---|---|
| ADR-01 · Modelos de lenguaje | Tabla 8: gpt-oss:20b tiene la mejor calidad (4.14) dentro de 45 s; gemma4:e2b es el único que cumple 15 s en la rápida | **Aceptada**, con la nota de que la calidad de la ruta rápida es baja (2.85) |
| ADR-02 · Embeddings | Tabla 9: bge-m3 tiene el mejor acierto@5 | **Aceptada**, con la salvedad de que todas las cifras de recuperación son bajas por el corpus incompleto |
| ADR-03 · Caché semántica | Tabla 22: con 0.92, precisión 1.00 en dos corridas | **Aceptada** (umbral 0.92) |
| ADR-04 · Enrutador | Tabla 21: 0 casos a la completa sin necesidad; con etiquetado por calidad, 47 % adecuado | **Propuesta**: la regla funciona, pero la calidad de la ruta rápida no basta. Revisar tras la mejora 5 |
| ADR-05 · Guardrails | Tabla 19: 92.3 % y 0 % de falsos positivos, con E4 = 0.40 y E2 sobre el texto enmascarado | **Aceptada**, con la calibración anotada en el ADR |
| ADR-06 · Fragmentación | Tablas 17 y 18: los tres tamaños empatan (0.13); 0.55 está a un caso del mejor equilibrio | **Propuesta**: no hay evidencia suficiente para preferir 800/120 con el corpus incompleto |
| ADR-07 · Agente | Tabla 20: 9 de 27 consultas superan el umbral, con 0.22 s adicionales | **Propuesta**: el costo es bajo, pero la mejora es modesta y las citas no siempre son de la sección esperada |
| ADR-08 · El modelo no mide | Tabla 16: S3 eliminó 0 cifras y el recall es 1.00 | **Aceptada** |

El ADR-05 ya tiene anotada la calibración del 13 de noviembre. Los demás ADR todavía dicen «[Pendiente: …]» en su línea de evidencia; usa las cifras de la sección 3.

---

## 6. Datos manuales (ningún script puede llenarlos)

| Dónde | Qué falta | Cómo |
|---|---|---|
| Portada | Nombre del docente | — |
| Tabla 16 y 9.1, juez–autor | Calificar 15 explicaciones | Abre `evaluacion/resultados/muestra_revision_manual.csv` y llena `nota_autor_fidelidad` y `nota_autor_relevancia` (0–5). **Las columnas `fidelidad` y `relevancia` traen la nota del juez: tápalas antes de calificar.** Luego corre `python evaluacion/run_eval.py --proveedor ollama --tablas 16 --juez --salida evaluacion/resultados/` y `python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/` |
| 9.2, valor | Prueba del revisor independiente: 5 mallas, tiempo manual frente a MeshAudit y hallazgos | Plantilla en `INSUMOS_INFORME.md`, sección 9.2 |
| Tabla 5, reproducibilidad | Un compañero instala el sistema siguiendo solo el README (≤ 30 min) | Cronometra sin contar las descargas |
| 9.2 / 4.5, sin red | Demostración con Wi‑Fi apagado: una auditoría y una pregunta | — |
| Prueba de disponibilidad | Cierra Ollama a mano con el servicio levantado y audita una malla con hallazgos: debe responder 503, no 500 | No se pudo hacer en esta sesión: la app de Ollama canceló el cierre |
| Línea base | Revisión manual de cada `baseN_base.obj` en los 4 perfiles | Ver el punto 4.6 |
| Corpus | Agregar `guia_entrega` y `rubrica_animacion` y repetir las fases 6–8 | Mejora 1 |
| 10.3 | Ajustar la declaración de uso de IA | Texto en ENTREGA, sección 4. Añade que las pruebas locales, la calibración y las correcciones de este documento también las hizo Claude Code en el Mac del autor, bajo su supervisión |

### Versiones para las referencias

- **Manual de Blender:** 5.3 (`corpus/fuentes.yaml`).
- **Documentación de Godot:** 4.x, traducción al español.
- **glTF:** 2.0.
- **trimesh:** 5.2.0.
- **Blender** (mutaciones): 5.2.2 LTS.
- **Ollama:** 0.40.16.

---

## 7. Archivos de esta corrida

| Archivo | Contenido |
|---|---|
| `evaluacion/resultados/tabla08_llm.csv` … `tabla23_latencias.csv` | Una tabla del informe por archivo (más `_casos.csv` con el detalle por caso) |
| `evaluacion/resultados/fallas.csv`, `privacidad.csv`, `retroalimentacion.csv` | Sección 9.2 |
| `evaluacion/resultados/muestra_revision_manual.csv` | 15 casos para validar al juez (pendiente) |
| `evaluacion/resultados/INSUMOS_INFORME.md`, `tablas_informe.tex` | Generados por `insumos_informe.py` |
| `evaluacion/resultados/ultima_corrida.json` | Parámetros de la corrida |
| `docs/PRUEBAS_LOCALES.md` | Lista de pruebas con su estado y el registro de incidencias |
