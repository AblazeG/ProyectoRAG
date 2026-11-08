# MeshAudit · Material para terminar el informe técnico

**Para:** el chat o la persona que va a editar `Informe_tecnico_MeshAudit` (35 páginas, entrega del 7 de noviembre de 2026).
**De:** la sesión que implementó y revisó el repositorio `AblazeG/ProyectoRAG`, rama `claude/eager-ritchie-mcs5zh` (commit `0c8fa84`).
**Fecha:** 8 de noviembre de 2026.

> ## ⚠️ Los datos de este documento son PROVISIONALES
> Todas las cifras se obtuvieron en un contenedor Linux en la nube, **sin el Mac del autor**:
> sin Ollama, sin GPU, sin Blender y sin el juez LLM. Los modelos de lenguaje y los embeddings
> fueron **dobles de prueba** (`ChatFalso` y `EmbeddingsFalsos`, un hash de n‑gramas), las mallas
> fueron las **sintéticas** de `evaluacion/sinteticas.py` (no las mutaciones de Blender) y el corpus
> fue el de `tests/corpus/` (5 textos sintéticos, no las normas reales).
>
> El informe se entrega así de momento. Cada tabla o párrafo con estas cifras debe llevar la nota de
> la sección 1.2, y las cifras se reemplazan cuando se corra la evaluación en el Mac (sección 6).

## 0. Qué hay que hacer, en orden

1. Aplicar las **correcciones de texto** de la sección 3: son pasajes que ya no describen al producto.
2. Sustituir la **declaración de uso de IA** (sección 10.3) por la de la sección 4, ajustada por el autor.
3. Llenar cada **«[Pendiente]»** y cada tabla con «?» con el contenido de la sección 5, en el orden del informe, poniendo la nota de datos provisionales donde indica la sección 1.2.
4. Dejar marcados los **datos manuales** de la sección 6 que el autor todavía no tiene.
5. **No** cambiar el estado de los ADR de «Propuesta» a «Aceptada»: la evidencia es provisional.

## 1. Cómo tratar las cifras

### 1.1 Qué cifras valen ya y cuáles no

| Valen ya (lógica determinista, no cambian con Ollama) | Solo indicativas (dependen de los dobles) | No medidas |
|---|---|---|
| Recall y precisión del analizador (tabla 16, sobre mallas sintéticas) | Acierto@k y MRR (tablas 9, 16, 17 y 18) | Fidelidad y relevancia (sin juez) |
| Guardrails E1, E3, E5 y patrones de E2 (tabla 19) | E4 y el clasificador de E2 (tabla 19) | Calidad, español, tok/s, memoria y carga en frío (tabla 8) |
| Caché exacta (fila «Exacta» de la tabla 22) | Caché semántica por umbral (tabla 22) | Acuerdo juez–autor |
| Fallas inyectadas y respaldo (0 errores 500, 5 de 5) | Agente (tabla 20) | Prueba con el revisor independiente |
| Privacidad (0 datos personales) | Enrutador (tabla 21: sin juez es circular) | Prueba de instalación con un compañero |
| Latencia de las capas sin modelo (tabla 23: guardrails, caché, análisis de malla) | Latencias de gateway y totales por ruta (el doble responde en < 1 ms) | Número real de fragmentos y composición del corpus real (tabla 2) |
| 258 pruebas automatizadas, 94 % de cobertura | | |

### 1.2 Nota para poner en el informe

Pie de cada tabla con cifras provisionales (8, 9, 16–23 y 2):

> *Datos provisionales: corrida en la nube con modelos y embeddings simulados, mallas sintéticas y
> corpus de prueba; se reemplazan con la corrida en el equipo local (sección 9).*

Párrafo sugerido al inicio de la sección 9.2:

> Los resultados de esta versión del informe son provisionales. Se obtuvieron ejecutando toda la
> evaluación de forma automática con dobles de prueba en lugar de los modelos de Ollama, con mallas
> sintéticas equivalentes a las mutaciones de la tabla 3 y con un corpus de prueba de cinco textos.
> Las métricas deterministas (analizador, guardrails basados en patrones, caché exacta, respaldo del
> gateway y privacidad) ya son representativas; las que dependen de los modelos o los embeddings
> (calidad de las explicaciones, recuperación, caché semántica, agente, enrutador y latencia de los
> modelos) se miden en el Mac con Apple M4 Max y sustituirán a estas.

Y en el Resumen, después de las cifras: «(resultados provisionales; ver sección 9.2)».

## 2. Lo que se comprobó y coincide con el informe

Se revisó cada cifra y cada nombre que el informe da como parte del diseño:

- **Arquitectura (sección 4):** capas C1–C7, T1 y T2, `PERMITIDOS` del código 2, puertos del código 1, raíz de composición y segundo adaptador vectorial en memoria. La prueba de arquitectura lo verifica por importaciones y en ejecución.
- **Flujos (sección 5, figuras 6–10):** orden de la auditoría (análisis antes del enrutador; caché de hallazgos después), ingesta con E5 antes y después de extraer, pregunta servida por la caché semántica, rechazo por inyección y ciclo de agente.
- **Parámetros:** `num_ctx` 8192, `keep_alive` 30m, tiempos límite de 45 y 90 s, 2 reintentos con esperas de 1 y 2 s, k = 5, umbral 0.55, fragmentos de 800 con solape 120, lotes de hasta 4 hallazgos, 3 reformulaciones por consulta y 6 por informe, E4 0.30, caché semántica 0.92, expiraciones de 7 días y 24 horas, 50 MB por malla, 2 000 000 de caras.
- **Tablas 10, 11, 13 y 14:** rutas del enrutador, límites y gravedades de V1–V11 por perfil (`config/perfiles.yaml`), verificaciones E1–E5 y S1–S4, y claves de la caché.
- **Conjuntos de prueba (tabla 15):** 20 casos de producto; 40 consultas de recuperación (30 relevantes y 10 sin respaldo); 23 de guardrails (4 de inyección, 3 fuera de dominio, 3 con datos personales, 3 documentos y 10 normales, 3 de ellas sobre el propio informe); 8 preguntas coloquiales del agente; 40 casos del enrutador; 5 fallas.
- **Código 4 (agente), código 5 (traza) y código 8 (respuesta de `POST /auditorias`):** mismos campos y nombres.

## 3. Correcciones al texto del informe

Cada punto da la ubicación, lo que dice, lo que hace el producto y el texto propuesto.

propuesto. Si prefieres cambiar el producto en lugar del texto, dímelo y lo ajusto.

### 3.1 Quién prioriza los hallazgos (tabla 1 y ADR-08)
- **Dice:** «Un modelo de lenguaje prioriza, explica y redacta la corrección» (tabla 1) y «el modelo solo explica y prioriza» (ADR-08).
- **Producto:** el orden lo fija el analizador (graves, menores, informativos y, dentro de cada gravedad, por número de verificación). El modelo no lo cambia.
- **Propuesta (tabla 1):** «Un modelo de lenguaje explica cada hallazgo y redacta la corrección citando la fuente; el orden por gravedad lo fija el analizador.»
- **Propuesta (ADR-08):** «…el modelo solo explica y redacta, el orden de los hallazgos sale de su gravedad y las mediciones las inserta una plantilla.»

### 3.2 Escenas con varias mallas (tabla 4, RF9, y sección 10.1, «Formatos»)
- **Dice:** RF9 «Aceptar archivos FBX y escenas con varias mallas y rig: No tendrá»; «No se aceptan FBX ni escenas con varias mallas, esqueletos o animación».
- **Producto:** un GLB con varios nodos se acepta: C7 combina las mallas aplicando la transformación de cada nodo (y corrige el orden de las caras si es un espejo). Rechazarlos dejaría fuera casi todos los GLB exportados desde Blender.
- **Propuesta (RF9):** «Aceptar FBX y escenas con rig o animación.» (No tendrá.)
- **Propuesta (10.1):** «No se aceptan FBX, esqueletos ni animación. Un GLB con varias mallas se audita como un solo objeto, con las transformaciones de sus nodos aplicadas.»

### 3.3 Persistencia de las mallas (sección 10.1, «Privacidad»)
- **Dice:** «las mallas subidas se borran tras la auditoría salvo que el usuario pida conservarlas».
- **Producto:** se borran siempre; la API del anexo B no tiene una opción para conservarlas.
- **Propuesta:** «las mallas subidas se borran al terminar cada auditoría, y las trazas no guardan el contenido del archivo, solo su hash.»

### 3.4 Tabla 13 (verificaciones)
- **E1, política:** dice «Bloquear (HTTP 413 o 415)». El producto también responde **422** cuando el archivo no se puede leer o su contenido es inválido: más de 2 millones de caras (ya lo dice la sección 7.1.1), índices de cara fuera de rango o coordenadas NaN/infinitas.
  - **Propuesta:** «Bloquear (HTTP 413, 415 o 422).»
- **E3, detección:** dice «correo, teléfono, CURP y matrícula». El producto también reconoce RFC y números de tarjeta (con verificación de Luhn). Los teléfonos de 10 dígitos seguidos se enmascaran salvo que vayan seguidos de una unidad («1234567890 mm»).
  - **Propuesta:** «Expresiones regulares para correo, teléfono, CURP, RFC, matrícula y tarjeta; una cifra seguida de una unidad no se toma por teléfono.»
- **E5, detección:** añadir «tamaño ≤ 20 MB» y «el HTML oculto (`hidden`, `display:none`) se descarta antes de buscar patrones».
- **S3, detección:** el producto solo evalúa cifras seguidas de una unidad o de un sustantivo de conteo; versiones («glTF 2.0»), años y números de sección no cuentan.
  - **Propuesta:** añadir «…; tampoco cuentan versiones, años ni números de sección».

### 3.5 Tabla 11 (V9 y V10)
- **V9:** el producto exige volumen con signo positivo **en cada componente cerrado**, no solo en el total, para que un cuerpo pequeño invertido no quede compensado por otro grande.
  - **Propuesta:** «`is_winding_consistent` y volumen con signo > 0 en cada componente cerrado».
- **V10:** el producto cuenta vértices a distancia < 10⁻⁶ que además tienen las mismas UV y normales. Así una arista dura (`f v//vn`) o una costura de UV no cuenta como duplicado.
  - **Propuesta:** «Vértices a distancia < 10⁻⁶ con las mismas UV y normales, sobre la malla sin procesar».

### 3.6 Tabla 24 (anexo B)
- **`POST /documentos`:**
  - Añadir los códigos **409**, para un `doc_id` que ya pertenece a otro archivo, y **403**.
  - Añadir el campo de formulario `reemplazar=true`, que permite reemplazarlo a propósito.
  - Subir el mismo archivo otra vez no sube la versión del corpus.
- **`DELETE /documentos/{id}`, `POST /auditorias`, `POST /auditorias/{id}/preguntas` y `POST /retroalimentacion`:** añadir **403**. Toda petición que modifica datos con una cabecera `Origin` que no sea la de la aplicación web se rechaza. Esto impide que otra página abierta en el navegador suba o borre documentos en `127.0.0.1:8000`.
- **Sección 10.1, «Seguridad y despliegue»:** añadir al final «Las peticiones que modifican datos desde un origen distinto del de la aplicación web se rechazan (HTTP 403).»

### 3.7 Figura 4 y código 6 (módulos que no aparecen)
- **Añadir a la figura 4:**
  - `cache/informes.py` (`ArchivoInformes`, el repositorio de informes que usa C2 a través de C4);
  - `orquestacion/estado.py` (`ServicioEstado`: salud, configuración y perfiles).
- **Añadir al código 6:**
  - `config/servicio.yaml` (modelos, umbrales y tiempos límite);
  - `servicio/datos/memoria.py` (segundo adaptador vectorial) y `servicio/datos/falsos.py` (dobles de prueba);
  - `restricciones.txt` (versiones probadas);
  - `evaluacion/{comun,juez,sinteticas,plantillas,mutar_blender,insumos_informe}.py`.
- **Código 1:** el puerto `LectorMalla` tiene además `probar(ruta)`, una lectura ligera que usa E1. Como el código 1 es un «extracto», basta con dejarlo así o añadir la línea.

### 3.8 Código 7 (README)
Cambios para que coincida con el README del repositorio:
- `pip install -r requirements.txt -c restricciones.txt`. numpy 2.5 exige Python 3.12, y el archivo fija la 2.4 para 3.11.
- Un paso para las mallas de evaluación: `blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas` (requiere Blender 4.2 o posterior).
- Los experimentos van **antes** que `run_eval.py`, y la evaluación se corre con `--juez`. `experimento_llm` escribe la muestra de 15 casos que el autor califica a mano para validar al juez.

### 3.9 Método de evaluación (sección 9.1 y tablas 9 y 16)
- **Juez–autor:** se reportan la diferencia media y el % de casos con diferencia ≤ 1 punto. La tabla 16 tiene una sola fila; añade «Acuerdo juez–autor (≤ 1 punto)» o pon el porcentaje en el texto.
- **«Sin RAG»:** a la salida sin contexto se le aplican los mismos S1–S3. La columna «Sin RAG» de «Cifras eliminadas por S3» sí tiene valor.
  - **Propuesta:** añadir al final de 9.1 «…pero sin fragmentos de contexto; a su salida se le aplican los mismos S1 a S3».
- **Tabla 9:** acierto y MRR se miden sin umbral, porque cada modelo tiene su propia escala de similitud.
  - **Propuesta (pie de la tabla 9):** «Acierto y MRR se calculan sobre el orden, sin umbral; el umbral 0.55 está calibrado para bge-m3.»

### 3.10 Tabla 2 (licencia de glTF)
El «[Pendiente: verificar]» depende del archivo que ingieras:
- El HTML y el PDF del registro de Khronos están bajo la **Khronos Specification License**. Permite usar y reproducir la especificación sin modificarla y sin costo, y no concede patentes ni marcas.
- Las fuentes AsciiDoc del repositorio de Khronos en GitHub están bajo **CC BY 4.0**.

El servicio ya acepta `Khronos-Specification` como licencia; antes, E5 habría puesto en cuarentena el HTML oficial. Confirma el texto vigente en el registro antes de entregar.

Fuentes consultadas:
- [Prólogo de la especificación glTF 2.0 en el registro de Khronos](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- [Archivo de licencia de una copia del repositorio](https://github.com/javagl/glTF/blob/main/LICENSE.adoc)
- [Archivo COPYING de otra copia](https://github.com/facebook/glTF/blob/main/COPYING.adoc)

Las dos últimas son copias del repositorio oficial; contrasta con el `COPYING.adoc` de KhronosGroup/glTF.

## 4. Declaración de uso de asistentes de IA (sección 10.3)

El borrador del informe dice que Claude se usó para «generar el esqueleto del código a partir del
proyecto de ejemplo del curso». No es exacto: el código del repositorio lo escribió casi completo
Claude Code, el agente de programación de Anthropic. Eso incluye el servicio, la aplicación web, las
pruebas, la evaluación, los experimentos, los conjuntos de casos (`evaluacion/casos_*.json`), el
corpus de prueba sintético (`tests/corpus/`), los ADR, `DESVIACIONES.md` y el README. Lo escribió a
partir de la especificación del proyecto y de este informe, en sesiones en la nube, sin acceso a
Ollama, a Blender ni al Mac.

El borrador también dice que «la construcción del corpus y de los casos de prueba» es del autor. Si
usas los casos tal como están, hay que decirlo. Texto propuesto, para que lo ajustes a lo que tú
hiciste:

> Conforme a los lineamientos del proyecto, se declara el uso de asistentes de IA. Se usó Claude
> (Anthropic) para estructurar el informe, redactar borradores de secciones y dibujar los diagramas
> en TikZ. La implementación del repositorio (servicio, aplicación web, pruebas, scripts de
> evaluación y de experimentos, conjuntos de casos y documentación) la escribió Claude Code, el
> agente de programación de Anthropic, a partir de la especificación del proyecto y de este informe;
> el autor revisó el código, corrigió [qué] y ejecutó las pruebas. La idea, el dominio, las decisiones
> de arquitectura, la selección y depuración del corpus normativo, la revisión de los casos de prueba
> y de la línea base de las mallas, la ejecución de los experimentos en el equipo local y la revisión
> final son del autor, quien verificó el contenido y responde por él.

Quita o cambia lo que no corresponda; en especial, «revisó el código», «corrigió [qué]» y «revisión
de los casos de prueba» solo deben quedar si de verdad los hiciste.

## 5. Contenido para cada «[Pendiente]» y tabla — DATOS PROVISIONALES

Generado por `evaluacion/insumos_informe.py` desde `evaluacion/resultados/provisional_nube/`. Donde dice «—» no hay dato; «DATO MANUAL», ver sección 6.

### 5.1 Estado de las metas (tabla 5)

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

### 5.2 Pendientes en el orden del informe

#### Portada · Docente
**DATO MANUAL**: nombre del docente.

#### Resumen · resultados principales
> Añade al final «(resultados provisionales; ver sección 9.2)». La fidelidad no se midió: quita esa frase o pon «pendiente».


En los 20 casos, el analizador obtuvo un recall de 1.00 y una precisión de 1.00 en los hallazgos. La sección de norma esperada apareció entre los cinco primeros fragmentos en el 52 % de los hallazgos, y la fidelidad media al contexto fue de — sobre 5. La latencia p95 por auditoría fue de 1.94 s en la ruta rápida y 2.52 s en la completa. Los guardrails manejaron bien el 100 % de las entradas problemáticas, con 0 % de falsos positivos.

#### 2.3 · Número de fragmentos

Tras la ingesta, el corpus produce **31** fragmentos indexados en ChromaDB (800 caracteres, solape 120).

#### Tabla 2 · Composición del corpus

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

#### Tabla 8 · Modelos de lenguaje

| Modelo | Cuantización | Contexto | Calidad | Español | Lat. p50 / p95 (s) | tok/s | Memoria (GB) |
|---|---|---|---|---|---|---|---|
| gemma4:e2b | **DATO MANUAL** | **DATO MANUAL** | — | — | 0.02 / 2.24 | — | — |
| qwen3:8b | **DATO MANUAL** | **DATO MANUAL** | — | — | 0.02 / 1.90 | — | — |
| gpt-oss:20b | **DATO MANUAL** | **DATO MANUAL** | — | — | 0.02 / 2.04 | — | — |

La cuantización y el contexto salen de `ollama show` (los «?» de la columna de características). La carga en frío va aparte, en el texto: gemma4:e2b — s, qwen3:8b — s, gpt-oss:20b — s.

#### Tabla 9 · Embeddings

| Modelo | Acierto@1 | Acierto@5 | MRR | Indexado (s) | Rechazos (umbral 0.55) |
|---|---|---|---|---|---|
| bge-m3 | 0.63 | 0.93 | 0.77 | 0.1 | 10 de 10 |
| embeddinggemma | 0.63 | 0.93 | 0.77 | 0.0 | 10 de 10 |
| nomic-embed-text | 0.63 | 0.93 | 0.77 | 0.0 | 10 de 10 |

Acierto y MRR se midieron sin umbral (solo el orden); la columna de rechazos es opcional en el informe y puede ir en el texto.

#### 6.4.1 · Conclusión de la selección
> **Ojo:** con los embeddings simulados los tres modelos empatan, y por la regla del ADR-02 el script elige embeddinggemma. **No** pongas esa conclusión en el informe. Mientras tanto usa: «La selección se confirma con la corrida en el equipo local; se mantiene la propuesta de ADR-01 (gemma4:e2b en la ruta rápida y gpt-oss:20b en la completa) y de ADR-02 (bge-m3).»

La tabla 8 no tiene calidad (la corrida fue sin `--juez`), así que la elección de modelos de lenguaje no puede justificarse todavía; se mantiene la propuesta del ADR-01. Para los embeddings se adopta **embeddinggemma** (acierto@5 0.93, MRR 0.77); embeddinggemma iguala a bge-m3 y es más ligero, que es la condición del ADR-02 para preferirlo.

#### Sección 8 · Evidencia de cada ADR

- **ADR-01 (tabla 8):** gemma4:e2b: calidad —, p95 2.24 s; qwen3:8b: calidad —, p95 1.90 s; gpt-oss:20b: calidad —, p95 2.04 s.
- **ADR-02 (tabla 9):** bge-m3: acierto@5 0.93, MRR 0.77; embeddinggemma: acierto@5 0.93, MRR 0.77; nomic-embed-text: acierto@5 0.93, MRR 0.77.
- **ADR-03 (tabla 22):** 0.85: recall 0.50, precisión 0.71; 0.9: recall 0.30, precisión 0.75; 0.92: recall 0.20, precisión 0.67; 0.95: recall 0.20, precisión 0.67.
- **ADR-04 (tabla 21):** 40 de 40 casos (100 %) a una ruta adecuada; 0 enviados a la completa sin necesidad; p95 rápida 1.94 s y completa 2.52 s.
- **ADR-05 (tabla 19):** 100 % de las 13 entradas problemáticas bien manejadas y 0 % de falsos positivos en las 10 normales.
- **ADR-06 (tablas 17 y 18):** 500 car., solape 75, k=8: acierto@k 0.07; 800 car., solape 120, k=5: acierto@k 0.07; 1000 car., solape 150, k=4: acierto@k 0.00. Con 800/120 y umbral 0.55: @3 0.07; @5 0.07; @8 0.07, 10 de 10 rechazos.
- **ADR-07 (tabla 20):** 1 de 38 consultas pobres superan el umbral tras reformular, con 2.95 reformulaciones de media.
- **ADR-08 (tabla 16):** recall 1.00 y precisión 1.00; S3 eliminó 0 frases con cifras sin respaldo.

Mientras los datos sean provisionales, los ADR se quedan en «Propuesta»; puede añadirse «(evidencia provisional)» a cada línea.

#### Tabla 16 · Calidad del producto

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

#### Tabla 17 · Tamaño de fragmento

| Fragmento | k | Fragm. | Acierto@k | MRR |
|---|---|---|---|---|
| 500 car., solape 75 | 8 | 46 | 0.07 | 0.07 |
| 800 car., solape 120 | 5 | 31 | 0.07 | 0.07 |
| 1000 car., solape 150 | 4 | 21 | 0.00 | 0.00 |

#### Tabla 18 · Barrido de k y umbral

| Umbral | @3 | @5 | @8 | Rechazos (de 10) |
|---|---|---|---|---|
| 0.4 | 0.37 | 0.37 | 0.37 | 10 |
| 0.5 | 0.13 | 0.13 | 0.13 | 10 |
| 0.55 | 0.07 | 0.07 | 0.07 | 10 |
| 0.6 | 0.03 | 0.03 | 0.03 | 10 |
| 0.7 | 0.00 | 0.00 | 0.00 | 10 |

#### Tabla 19 · Guardrails de entrada

| Entrada | Casos | Correctos | Falsos pos. |
|---|---|---|---|
| Inyección (E2) | 4 | 4 | – |
| Fuera de dominio (E4) | 3 | 3 | – |
| Datos personales (E3) | 3 | 3 | – |
| Documentos (E5) | 3 | 3 | – |
| Normales | 10 | – | 0 |
| Total | 23 | 100.0 % | 0.0 % |

#### Tabla 20 · Ciclo de agente

| Métrica | Valor |
|---|---|
| Superan el umbral tras reformular | 1 de 38 |
| Reformulaciones promedio | 2.95 |
| Terminan en «sin norma» | 37 |
| Latencia adicional media (s) | 0.0 |

#### Tabla 21 · Enrutador

| Ruta esperada | Casos | Adec. | Lat. p50 / p95 (s) |
|---|---|---|---|
| Sin modelo | 17 | 17 | 0.01 / 0.43 |
| Rápida | 12 | 12 | 0.03 / 1.94 |
| Completa | 11 | 11 | 0.03 / 2.52 |
| A la completa sin necesidad |  | 0 |  |

#### Tabla 22 · Caché

| Umbral | Recall | Precisión | Falsos pos. | Ahorro (ms) |
|---|---|---|---|---|
| 0.85 | 0.50 | 0.71 | 2 | 9.3 |
| 0.9 | 0.30 | 0.75 | 1 | 9.1 |
| 0.92 | 0.20 | 0.67 | 1 | 8.6 |
| 0.95 | 0.20 | 0.67 | 1 | 8.7 |
| Exacta (20 repetidas) | 1.00 | 1.00 | 0 | 221.9 |

p95 de una auditoría servida por la caché exacta: 23.8 ms (meta ≤ 300 ms).

#### Tabla 23 · Latencia por capa (ms)

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

#### 9.2 · Valor medido con el revisor independiente

**DATO MANUAL**: completa la tabla con la prueba de las cinco mallas y pega el párrafo.

| Malla | Tiempo manual (min) | Tiempo MeshAudit (s) | Hallazgos del revisor | Encontrados por MeshAudit |
|---|---|---|---|---|
| malla 1 |  |  |  |  |
| malla 2 |  |  |  |  |
| malla 3 |  |  |  |  |
| malla 4 |  |  |  |  |
| malla 5 |  |  |  |  |

Texto: «El revisor tardó en promedio X min por malla; MeshAudit, Y s. De los N hallazgos del revisor, la herramienta encontró M (P %); los restantes eran aspectos que las reglas no miden, como …».

#### 9.2 · Fallas y retroalimentación

En las fallas inyectadas se registraron **0** errores 500 y **5** de 5 auditorías terminaron con el respaldo. Durante las pruebas se registraron **0** calificaciones de retroalimentación, con una tasa de utilidad de **—**.

No hay calificaciones: usa la aplicación web en las pruebas o pasa `--datos` con tu `data/`.

#### 9.3 · Análisis de errores
- **Analizador.** Sin hallazgos no detectados ni falsos en los 20 casos.
- **Sin norma.** 22 hallazgos terminaron «sin norma aplicable»; la causa más probable es la recuperación (acierto@5 de la sección esperada = 0.52). Citas eliminadas por S2: 0.0 % de las citas generadas.
- **Caché semántica.** Aciertos equivocados (distractores servidos): umbral 0.85: «¿Qué es TEXCOORD_1 en glTF?» (1.000), «¿Cuántos triángulos puede tener un escenario de juego móvil?» (0.865); umbral 0.9: «¿Qué es TEXCOORD_1 en glTF?» (1.000); umbral 0.92: «¿Qué es TEXCOORD_1 en glTF?» (1.000); umbral 0.95: «¿Qué es TEXCOORD_1 en glTF?» (1.000).
- **Guardrails.** Ninguna entrada problemática mal manejada ni falsos positivos.
- **Enrutador.** Sin juez, la ruta esperada salió de la misma regla: la tabla 21 es circular.
- **Agente.** De 38 consultas con recuperación pobre, 1 superan el umbral tras reformular.
- **Latencia.** Casos en el p95 o por encima: P13 (2.2 s).

#### 9.4 · Mejoras que surgen del análisis
- El acierto@5 (0.52) queda bajo la meta de 0.85: ajustar los títulos de sección de `perfiles.yaml` a los del corpus real y probar la búsqueda híbrida con BM25.
- Añadir al prompt de reformulación los términos que el agente no logró traducir.
- Con 0.92 la caché semántica sirvió distractores: subir el umbral o exigir la misma verificación.

#### Referencias · versiones

- Blender Manual (versión **DATO MANUAL**): la del manual que descargaste; puedes declararla como `version:` en `corpus/fuentes.yaml` y este script la toma.
- trimesh (versión 5.2.0): la instalada al generar este archivo; en el Mac, la de `pip show trimesh`.

#### 10.3 · Declaración de uso de asistentes de IA
Ver la sección 4 de este documento: hay que decirlo con exactitud, porque el código no es solo un esqueleto.

## 6. Datos manuales (no los puede llenar ningún script)

| Dónde | Qué hace falta | Mientras tanto |
|---|---|---|
| Portada | Nombre del docente | Dejar «[Pendiente: nombre del docente]» |
| 9.2, valor | Prueba del revisor independiente: 5 mallas, tiempo manual frente a MeshAudit y hallazgos encontrados | Dejar el «[Pendiente]» o decir «se realizará con la corrida final» |
| Tabla 5, reproducibilidad | Prueba de instalación con un compañero (≤ 30 min) | «Pendiente» |
| Tabla 16, juez–autor | Calificar a mano `muestra_revision_manual.csv` (columnas `nota_autor_*`) tras `experimento_llm --juez` | «–» |
| Tabla 8 | Cuantización y contexto (`ollama show`), calidad, tok/s, memoria y carga en frío | «?» o «–» con la nota provisional |
| Tabla 2 | Documentos, páginas y licencia de glTF del corpus real | Las cifras de la sección 5 son del corpus de prueba |
| Referencias | Versión del manual de Blender descargado | «[Pendiente: x.y]» |
| Referencias | Versión de trimesh: **5.2.0** (la probada; en el Mac, `pip show trimesh`) | Usar 5.2.0 |
| Sección 8 | Estado de los ADR | Mantener «Propuesta» |
| 10.3 | Ajustar la declaración de la sección 4 a lo que el autor hizo | — |

### Para la versión final (en el Mac)

```bash
pip install -r requirements.txt -c restricciones.txt
# corpus real en corpus/ y cinco mallas base CC0 en evaluacion/mallas_base/
python -m servicio.ingestar corpus/
blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas
python -m evaluacion.plantillas --bases silla,personaje,engrane,escaneo,lampara   # revisar a mano
python -m experimentos.experimento_llm --juez --salida evaluacion/resultados/
for e in embeddings fragmentos cache; do python -m experimentos.experimento_$e --salida evaluacion/resultados/; done
python evaluacion/run_eval.py --juez --salida evaluacion/resultados/
python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/
```

El último comando regenera la sección 5 de este documento con las cifras reales
(`evaluacion/resultados/INSUMOS_INFORME.md` y `tablas_informe.tex` con las filas en LaTeX).
