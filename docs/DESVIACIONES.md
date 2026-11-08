# Desviaciones respecto al informe técnico

Fuente de verdad: `docs/Informe_tecnico_MeshAudit.pdf` (junto con `docs/Especificacion_proyecto_integrador.pdf`
y `docs/Rubrica_proyecto_integrador.pdf`). Cada entrada dice qué dice el informe, qué se implementó y por qué.
Lo que no aparece aquí se implementó tal como lo describe el informe.

## A. Diferencias entre el encargo inicial y el informe

| Tema | Encargo inicial | Informe (se siguió) |
|---|---|---|
| Modelo de embeddings | nomic-embed-text con prefijos | **bge-m3** (ADR-02, figura 5). Los prefijos `search_document:`/`search_query:` se conservan en `EmbeddingsOllama` y solo se aplican a nomic-embed-text, que sigue en el experimento de la tabla 9. |
| Nombres de C2 | `ingestar` | `ingerir(doc) → DocIndexado`; clases `OrquestadorAuditoria` y `CicloAgente` (tabla 6, figura 4). |
| Corpus | sin fuentes definidas | Las cinco fuentes de la tabla 2: Blender Manual, documentación de Godot, especificación glTF 2.0, guía de entrega propia y rúbrica propia. |
| Conjuntos de prueba | E1 dentro de los 23 casos de guardrails; fallas con 503 | Composición de la tabla 15: 4 inyección, 3 fuera de dominio, 3 datos personales, 3 documentos y 10 normales. Las 5 fallas deben terminar con el respaldo. E1 queda cubierto por las pruebas unitarias (`tests/test_guardrails.py`, `tests/test_api.py`). |
| Numeración de tablas | 16–23 con otro orden | 16 producto, 17 fragmentos, 18 barrido, 19 guardrails, 20 agente, 21 enrutador, 22 caché, 23 latencias; 8 y 9 salen de los experimentos. |

## B. Desviaciones de implementación

### B1. Puertos del dominio con métodos adicionales (Código 1)
- **Informe:** `ModeloEmbeddings.vectorizar`, `AlmacenVectorial.agregar/buscar/eliminar_documento` y `LectorMalla.leer`.
- **Implementado:** además, `ModeloEmbeddings.nombre` (el manifiesto guarda el modelo con que se indexó), `AlmacenVectorial.contar` (manifiesto y `/health`) y `LectorMalla.probar` (lectura de prueba de E1, ver B2).

### B2. Lectura de prueba ligera en E1
- **Informe:** «OBJ y STL, que no tienen firma fiable, se validan con una lectura de prueba» (tabla 13), y la caché exacta se consulta después de E1 (sección 5).
- **Implementado:** `LectorTrimesh.probar` revisa la estructura (OBJ: líneas `v` y `f` válidas en el primer MB; STL: tamaño binario 84 + 50·n o ASCII con `solid … facet`) sin cargar la malla. La carga completa ocurre en `analizar_malla`, solo cuando la caché falla.
- **Por qué:** con una carga completa en E1, un acierto de caché sobre la malla de M4 (10 MB) tardaba ~630 ms (p95). La meta de la tabla 5 es ≤ 300 ms; con la lectura ligera queda en ~25 ms.
- **Consecuencia:** un archivo que pasa la lectura de prueba pero falla en la carga completa responde 422 (malla inválida) y no 415.

### B3. Ciclo de agente (Código 4)
- **Implementado:** misma lógica, condición de salida y topes (3 por consulta, 6 por informe), como método de `CicloAgente`, que recibe `recuperador` y `gateway` por inyección. Devuelve `(fragmentos, intento)`, con lista vacía para «sin norma aplicable». Si el modelo rápido no responde, el ciclo termina sin reformular en vez de propagar el error. Además de `traza.anotar(reformulacion, intento)`, suma `iteraciones_agente`.

### B4. Traza (Código 5)
- **Implementado:** las claves de `tiempos_ms` del Código 5 (`guardrails_entrada`, `cache`, `contexto_malla`, `enrutador`, `contexto_rag`, `gateway`, `guardrails_salida`), más `archivo_temporal`, `ensamblado` y `persistencia`.
- `guardrails` es `{"entrada", "salida"}` como en el Código 5, más la lista `activaciones` (E1–E5, S1–S4), que alimenta las métricas por guardrail.
- `hallazgos` cuenta los graves y menores.
- Contadores añadidos para la tabla 16: `citas_generadas`, `citas_removidas_s2`, `frases_eliminadas_s3` y `hallazgos_cache`.

### B5. Respuesta de `POST /auditorias` (Código 8)
- Se respetan los campos y su forma: ids `h1…`, `medido` y `limite` como texto con unidad, `fuente.documento` = doc_id, `guardrails` con `entrada`/`salida`, aviso «Informe generado por un modelo; puede contener errores.» y resumen «Animación: 2 hallazgos (1 grave, 1 menor)».
- **Campos añadidos:**
  - En el informe: `uso_respaldo`, `archivo`, `perfil`, `perfil_nombre`, `versiones` y `guardrails.activaciones`.
  - En cada hallazgo: `descripcion`, `valor` (número sin formato) y `norma_esperada`.
  - En la fuente: `titulo`, `id` y `pagina`.
- `cache` puede valer `ninguna`, `exacta`, `hallazgos` (si algún hallazgo vino de la caché de hallazgos) o `semantica` (solo en preguntas).
- El resumen añade los informativos y las verificaciones no medibles.
- En la ruta sin modelo, el aviso dice «Informe automático; puede contener errores.». En las preguntas y los rechazos se usa «Respuesta generada por un modelo…» o «Respuesta automática…».

### B5b. `modelo` y `uso_respaldo` según lo que realmente pasó
- `modelo` es el modelo que explicó algún hallazgo en esta ejecución (no el que reformuló ni el clasificador de E2). Si todo vino de la caché de hallazgos, es el modelo de la ruta. Si ningún modelo intervino (por ejemplo, todos los hallazgos quedaron «sin norma»), es `plantilla` y el aviso es el de informe automático, aunque la ruta sea rápida o completa.
- `uso_respaldo` solo cuenta el respaldo en las llamadas de explicación. Un acierto de caché siempre responde `uso_respaldo: false`.
- Lo que explicó el modelo de respaldo, y los «sin norma» producidos porque el agente no pudo reformular por falta de modelo, no se guardan en caché.

### B6. Rechazos de C1 sin aviso
- **Informe (3.3):** «toda respuesta incluye el aviso».
- **Implementado:** todo lo que pasa por C2 lleva el aviso de S4, incluidos rechazos, 503, errores imprevistos (500 con `traza_id`) y respuestas de caché. Las validaciones de esquema, extensión, perfil y tamaño que hace C1 antes de crear la traza (paso 1) responden solo con `detalle`, porque C1 no puede depender de C3 y en ese punto no se ha generado contenido. Los 422 de esquema de FastAPI también usan `detalle`.

### B7. Analizador (sección 7.1.1)
- **V7:** los GLB están en metros por especificación y se convierten a la unidad del perfil. OBJ, STL y PLY se interpretan en la unidad del perfil, como dice la sección 10.1.
- **V10:** dos vértices en la misma posición pero con UV o normales distintas son una costura legítima, no un duplicado. En STL, V10 es «no medible», porque cada faceta guarda sus propios vértices.
- **No medibles:** V1 y V2 fuera de OBJ, y V10 en STL, aparecen como hallazgos informativos `tipo: "no_medible"`. El resumen recomienda auditar en OBJ.
- El orden de los hallazgos es graves, menores e informativos, y dentro de cada gravedad, por número de verificación.

### B7b. Lectura de mallas, V9 y V10
- `LectorTrimesh` carga sin `force="mesh"`: esa conversión pierde las normales declaradas y V10 confundía las aristas duras (`f v//vn`) con vértices duplicados. Las escenas (GLB con varias mallas) se combinan aplicando la transformación de cada nodo.
- **V9:** el volumen con signo se exige positivo en cada componente cerrado, no solo en el total. Así un cuerpo pequeño invertido no queda compensado por otro grande.
- **V10:** usa la distancia euclídea real (< 1e-6) con los mismos UV y normales, sin errores en los bordes de la rejilla.

### B7c. Interpretación de S3 y E3
- **S3** (tabla 13: «conteos, porcentajes y valores con unidad») solo evalúa cifras seguidas de una unidad o de un sustantivo de conteo (mm, %, caras, triángulos, MB…). Versiones («glTF 2.0», «Blender 4.2»), años, secciones y razones no cuentan, y cada campo (explicación y cada paso) se evalúa por separado.
- **E3:** un teléfono se enmascara si lleva separadores entre grupos, una palabra clave («tel», «cel», «WhatsApp») o si son 10 dígitos seguidos (con o sin +52). No se enmascara cuando a los dígitos les sigue una unidad o un sustantivo de conteo («1234567890 mm», «… caras»). Las tarjetas solo se enmascaran si pasan la verificación de Luhn; el RFC, la CURP con espacios y los correos con «(at)» también se reconocen.
- **E2/E5:** «el modelo debe…» no se trata como instrucción al asistente: en este dominio «el modelo» es el modelo 3D («el modelo debe desenvolverse antes de exportarse»). Sí cuentan «el asistente», «la IA» y «el modelo de lenguaje».
- **E5:** el HTML oculto (`hidden`, `aria-hidden`, `display:none`) se descarta antes de extraer el texto, para que no se cuele una inyección invisible.
- **E2:** los patrones exigen un objeto de instrucción («instrucciones anteriores», «tu prompt», «a partir de ahora» + orden). Así no bloquean notas técnicas como «ignora las caras ocultas» o «act as a mold».

### B7d. Escenas con varias mallas (RF9)
- RF9 («escenas con varias mallas y rig») es «No tendrá». Aun así, un GLB con varios nodos no se rechaza: C7 combina las mallas aplicando la transformación de cada nodo (y voltea el orden de las caras si la transformación es un espejo) y el informe audita el conjunto. Rechazarlo dejaría fuera los GLB exportados desde Blender, que casi siempre traen al menos un nodo. Los rigs y el FBX siguen fuera.

### B7e. Quién prioriza los hallazgos
- El informe dice que «el modelo solo explica y prioriza». Aquí el orden de los hallazgos lo fija C2 de forma determinista (graves, menores, informativos y, dentro de cada gravedad, por número de verificación), y el modelo solo explica y redacta la corrección. Así el orden no varía entre corridas ni entre modelos.

### B8. Hallazgos sin fragmentos
- Un hallazgo para el que el agente no encuentra norma no se envía al modelo: la plantilla escribe «Sin norma aplicable en el corpus». La regla 3 del prompt se mantiene para el caso en que el modelo lo decida.

### B9. Preguntas de seguimiento
- El propio informe se entrega al modelo como un fragmento citable `informe:<id>#1` (semáforo, hallazgos, mediciones y límites). Así puede responder preguntas sobre el informe sin que S3 elimine las cifras.

### B10. Clasificador de E2
- El prompt few-shot del clasificador vive en `guardrails/entrada.py`, porque C3 solo depende de C6 y C7 (figura 3), no de C5.
- Usa el alias `rapido` sin respaldo: si no responde, E2 se queda con los patrones y la traza registra `E2_sin_clasificador`.

### B10b. API: códigos y protecciones que no están en el anexo B
- **409 Conflicto** en `POST /documentos` cuando el `doc_id` ya pertenece a otro archivo. Para reemplazarlo a propósito se envía `reemplazar=true` (campo de formulario añadido). Subir otra vez el mismo archivo (mismo SHA-256) no es un conflicto: devuelve el documento ya indexado sin subir `version_corpus`.
- **403** a `POST`, `PUT`, `PATCH` y `DELETE` con una cabecera `Origin` que no esté en `cors_origenes`. CORS solo impide leer la respuesta, no que el navegador envíe el formulario; sin esta regla, una página cualquiera abierta en el Mac podría subir o borrar documentos en `127.0.0.1:8000`. Los clientes sin navegador (curl, `run_eval.py`) no envían `Origin` y no se ven afectados.
- Los nombres de archivo se reducen a su nombre base (`../../x.md` → `x.md`), y un nombre sin caracteres ASCII recibe un `doc_id` estable `doc_<sha1>`.
- `/health` no expone rutas del servidor.
- **Retroalimentación:** se guarda un voto por traza y hallazgo; el último reemplaza al anterior, para que la tasa de utilidad no se infle con clics repetidos.

### B11. Persistencia de las mallas (sección 10.1)
- **Informe:** «las mallas subidas se borran tras la auditoría salvo que el usuario pida conservarlas».
- **Implementado:** siempre se borran. No hay opción para conservarlas (no figura en la API del anexo B).

### B12. Corpus y licencias
- `licencias_permitidas` incluye `CC-BY-3.0` (Godot) y `propio` (guía y rúbrica del autor). Para la especificación glTF (tabla 2, «Pendiente: verificar») se añadió `Khronos-Specification`: el HTML del registro de Khronos está bajo la Khronos Specification License, y sus fuentes AsciiDoc, bajo CC BY 4.0 (ver `corpus/README.md`).
- `tests/corpus/` contiene textos **sintéticos**, redactados para las pruebas, con los `doc_id` y la licencia de las fuentes reales; la rúbrica real es PDF y aquí es Markdown.
- Los títulos de sección de `config/perfiles.yaml` coinciden con esos textos en español. Tras ingerir el corpus real (en inglés) hay que ajustarlos a las secciones reales (por ejemplo, «Mesh cleanup», como en el Código 8).

### B13. Evaluación
- `run_eval.py` ejecuta la API en proceso (TestClient, el mismo código que uvicorn) o contra `--url`.
- Las tablas 17 y 18 miden C5 directamente, porque la API no expone la recuperación. La tabla 22 y la de fallas necesitan el modo en proceso: ajustan el umbral o inyectan fallas en el adaptador.
- **Fallas:** el «doble del adaptador» es `ChatConFalla` (`MESHAUDIT_FALLA=alias:tipo`). El «alias hacia una etiqueta inexistente» se configura con `MESHAUDIT_MODELO_RAPIDO|COMPLETO` (404 real de Ollama).
- **Enrutador (tabla 21):** sin `--juez`, la ruta esperada cae en la regla del enrutador y la tabla se vuelve circular. Hay que correrla con `--juez`. Con juez solo se califican explicaciones generadas con norma (no «sin norma» ni hallazgos sin fuente); un caso sin nada que calificar queda «sin etiqueta» y se excluye, en lugar de recibir una etiqueta inventada.
- **«Sin RAG» (tabla 16):** se usa un prompt de sistema sin las reglas de contexto y citas, con el mismo modelo y los mismos hallazgos. A su salida se le aplican los mismos S1–S3 que a la ruta con RAG, para que la diferencia mida el aporte del contexto y no la falta de guardrails.
- **Juez–autor:** `experimento_llm.py` escribe `muestra_revision_manual.csv` (5 casos por modelo), así que debe correr **antes** que `run_eval.py`. Al llenar las columnas del autor, `run_eval.py` calcula la diferencia media y, en una fila aparte, el % de casos con diferencia ≤ 1.
- **Agente (tabla 20):** «supera el umbral» se decide con la última recuperación de la traza y la misma condición que `es_suficiente` (top-1 ≥ umbral configurado y ≥ 2 fragmentos), no con que la respuesta traiga alguna fuente.
- **Guardrails (tabla 19):** un caso problemático solo es correcto si se activó el guardrail esperado; un 422 por otra causa (por ejemplo E1) no cuenta.
- **Embeddings (tabla 9):** acierto@1, acierto@5 y MRR se miden sin umbral (solo el orden), porque cada modelo tiene su propia escala de similitud y el 0.55 está calibrado para bge-m3. Los rechazos correctos y el acierto@5 con el umbral del servicio se informan en columnas aparte.
- **Recuperación (tablas 9, 17 y 18):** la búsqueda se filtra por el perfil de cada caso, como en el servicio.
- **Caché (tabla 22):** la precisión de la fila «Exacta» se mide comparando cada acierto con la respuesta original (no se supone 1.0), y el p95 se calcula solo sobre las auditorías servidas por la caché, con `np.percentile`.
- **Aislamiento:** cada sesión de la evaluación tiene su propia base SQLite y sus trazas; solo comparten el índice (Chroma y el registro de documentos) para no recalcular los embeddings. La privacidad se mide al final, sobre los almacenes de todas las sesiones. Los directorios temporales se borran al salir.

### B14. Mallas de evaluación
- `evaluacion/mutar_blender.py` implementa M1–M5 con bpy, pero **no se ejecutó aquí**: no hay Blender en la nube. Tras cada mutación comprueba que el defecto existe y se detiene si no. M3 se exporta sin normales (con normales suavizadas los vértices separados parecen costuras y no duplicados). M5 colapsa vértices sobre aristas paralelas a un eje, para que el área sea exactamente cero en float32 (el umbral de V8 es 1e-10).
- Con Ollama, `run_eval.py` y los experimentos se detienen si faltan las mallas que piden los casos; `--mallas-sinteticas` las sustituye por las sintéticas, pero esas cifras no son las del informe.
- En modo falso, `evaluacion/sinteticas.py` genera cinco bases y sus variantes con numpy. Imitan la sección 2.4: una pieza pequeña, un modelo triangulado tipo Kenney que falla V2 y un «escaneo» que supera V3. Reproducen exactamente la tabla 3.
- `plantillas.py --bases …` recalcula la línea base con tus mallas reales, pero **hay que revisarla a mano**, como pide el informe.

### B15. Dobles de prueba
- `EmbeddingsFalsos` (hash de n-gramas) añade un componente común para que sus cosenos caigan en la escala de los umbrales del informe (0.30, 0.55 y 0.92).
- Las métricas de recuperación en modo falso son bajas (acierto@5 ≈ 0.07) y no representan al sistema. Las cifras del informe deben medirse con bge-m3 en el Mac.

### B16. Archivos añadidos a la estructura del Anexo A (Código 6)
- `config/servicio.yaml` (modelos, umbrales, tiempos límite).
- `servicio/datos/memoria.py` (segundo adaptador vectorial, meta de modificabilidad de la tabla 5).
- `servicio/datos/falsos.py` (dobles y `ChatConFalla`).
- `evaluacion/{comun,juez,sinteticas,plantillas}.py`.
- `tests/corpus/` y `tests/mallas/`.

### B17. Entorno
- En la nube se probó con Python 3.13 y también con 3.11.18 en un entorno limpio, como el Mac. `restricciones.txt` fija las versiones de ese entorno (`pip install -r requirements.txt -c restricciones.txt`). numpy 2.5 exige Python ≥ 3.12, así que en 3.11 se instala la 2.4.
- El README añade a los comandos del Código 7 el archivo de restricciones y ordena los experimentos antes de `run_eval.py`.
- `docs/` contiene los PDF del encargo, la rúbrica y el informe, pero no las fuentes editables de los diagramas (figuras 1–7). El código sigue los diagramas del PDF.
- Pillow está en `requirements.txt`: lo usa `evaluacion/sinteticas.py` para la textura del GLB de V11.
- `<model-viewer>` 4.1.0 está en `web/vendor/` (Apache-2.0).

## C. Pendientes del informe y dónde se obtienen

| Pendiente en el informe | Se obtiene con | Archivo |
|---|---|---|
| Resumen: recall, precisión, acierto@5, fidelidad, latencia p95, guardrails | `python evaluacion/run_eval.py --juez` | tablas 16, 19, 23 |
| Tabla 2: documentos, páginas y licencia de glTF | `python -m servicio.ingestar corpus/` y `GET /documentos` | — |
| Sección 2.3: número de fragmentos | manifiesto (`GET /documentos`) | — |
| Tabla 8 y ADR-01 | `python -m experimentos.experimento_llm --juez` | `tabla08_llm.csv` |
| Tabla 9 y ADR-02 | `python -m experimentos.experimento_embeddings` | `tabla09_embeddings.csv` |
| 6.4.1 Conclusión de la selección | tablas 8 y 9 | — |
| Tabla 16 y ADR-08 | `run_eval.py --juez` (+ notas del autor en `muestra_revision_manual.csv`) | `tabla16_producto.csv` |
| Tablas 17, 18 y ADR-06 | `python -m experimentos.experimento_fragmentos` | `tabla17_fragmentos.csv`, `tabla18_barrido.csv` |
| Tabla 19 y ADR-05 | `run_eval.py` | `tabla19_guardrails.csv` |
| Tabla 20 y ADR-07 | `run_eval.py` | `tabla20_agente.csv` |
| Tabla 21 y ADR-04 | `run_eval.py --juez` | `tabla21_enrutador.csv` |
| Tabla 22 y ADR-03 | `python -m experimentos.experimento_cache` | `tabla22_cache.csv` |
| Tabla 23 | `run_eval.py` (5 corridas, caché desactivada) | `tabla23_latencias.csv` |
| 9.2: errores 500 y auditorías con respaldo | `run_eval.py` | `fallas.csv` |
| 9.2: calificaciones y tasa de utilidad | uso real de la web + `run_eval.py --datos data/` | `retroalimentacion.csv`, `GET /metricas` |
| Tabla 5: privacidad (0 datos personales) | `run_eval.py` | `privacidad.csv` |
| Medición del valor con el revisor independiente | cronometraje manual | — |
| Referencias: versión de Blender Manual y de trimesh | `pip show trimesh` (5.2 en la nube) | — |
| 10.3 Declaración de uso de asistentes de IA | Claude Code construyó el código a partir del informe; ver el historial de commits | — |
