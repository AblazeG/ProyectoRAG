# Desviaciones respecto al informe técnico

Cada entrada indica qué dice el informe (o la especificación del encargo), qué se implementó y por qué.

## D0. El informe no estaba en el repositorio

- **Informe:** `Informe_tecnico_MeshAudit.pdf` debía estar en `docs/` o en la raíz.
- **Implementado:** el repositorio estaba vacío al empezar. Se usó como fuente de verdad la especificación detallada del encargo (capas, módulos, umbrales, tablas, guardrails, cachés, rutas, API y fases). Lo que el informe define y la especificación no repite se reconstruyó y se marca abajo: redacción y numeración de los 8 ADR (D15), contenido de las tablas 16–23 (D16), Código 6 completo (D11) y fuentes del corpus (D17).
- **Pendiente:** copiar el PDF a `docs/` y contrastar esta lista.

## D1. Embeddings falsos con componente común (anisotropía)

- **Informe:** dobles deterministas, por ejemplo un hash de n-gramas normalizado.
- **Implementado:** `EmbeddingsFalsos` usa hash con signo de raíces de palabras y 4-gramas de caracteres, más un componente común de peso 0.5 (coseno resultante = (0.25 + cos) / 1.25).
- **Por qué:** sin ese componente, los puntajes del hash quedaban muy por debajo de los umbrales del informe (0.30, 0.55 y 0.92), que están pensados para modelos reales y no isótropos. Con el doble falso, la recuperación es pobre (acierto@5 ≈ 0.03–0.07 con el criterio de suficiencia) y E4 depende mucho de la frase: algunos textos fuera de dominio quedan cerca de 0.30. Esas cifras no son las del sistema real; las del informe deben medirse en el Mac con `nomic-embed-text`.

## D2. Unidad de los archivos para V7

- **Informe:** dimensión máxima de la caja envolvente en la unidad del perfil.
- **Implementado:** GLB se interpreta en metros (lo fija la especificación glTF) y se convierte a la unidad del perfil. OBJ, STL y PLY no declaran unidad y se interpretan directamente en la unidad del perfil (m o mm).

## D3. V10 sin falsos positivos por costuras; STL no medible

- **Informe:** vértices a menos de 1e-6 en la malla sin procesar.
- **Implementado:** al leer un OBJ con UV, trimesh separa vértices en las costuras. Dos vértices en la misma posición con UV (o normal) distintas son una costura legítima, así que la clave de duplicado incluye UV y normales cuando existen. En STL cada faceta guarda sus propios vértices por definición, por lo que V10 se marca «no medible».

## D4. «No medible» como hallazgo informativo

- **Implementado:** cuando V1/V2 (o V10 en STL) no se pueden medir, se añade un hallazgo informativo `tipo: "no_medible"` y el resumen recomienda auditar en OBJ. No cuenta para el semáforo ni para el enrutador.

## D5. Archivos añadidos a la estructura del Anexo A

- `servicio/datos/memoria.py`: segundo adaptador vectorial (en memoria), pedido en la especificación.
- `servicio/datos/mallas.py` incluye `AlmacenMallasTemporal` (guardar y borrar en `data/mallas/`).
- `servicio/datos/falsos.py` incluye `ChatConFalla`, activado con `MESHAUDIT_FALLA=alias:tipo[:n]` para la tabla de fallas con Ollama real.
- `evaluacion/`: `comun.py`, `juez.py`, `sinteticas.py` (mallas M1–M5 sin Blender para el modo falso) y `plantillas.py` (genera los `casos_*.json`).
- `tests/corpus/`: corpus sintético de prueba (CC0, redactado para este proyecto).

## D6. El prompt del clasificador E2 vive en C3

- **Informe:** prompts versionados en `contexto/prompts.py`.
- **Implementado:** el prompt few-shot del clasificador de inyección está en `guardrails/entrada.py`, porque C3 solo puede depender de C6 y C7, no de C5. El prompt v1 del sistema, la reformulación y la pregunta siguen en `prompts.py`.

## D7. Firma de `recuperar_con_agente`

- **Informe (Código 4):** `recuperar_con_agente(consulta, perfil, presupuesto, traza)`.
- **Implementado:** misma firma posicional, más dependencias por palabra clave (`recuperador`, `gateway`), porque no hay estado global. `Agente` envuelve la función con las dependencias ya inyectadas.

## D8. Recuperación insuficiente

- Si tras las reformulaciones no hay al menos 2 fragmentos sobre 0.55, se responde «Sin norma aplicable en el corpus», aunque exista un único fragmento bueno. Es la lectura estricta del criterio de suficiencia.
- Los hallazgos sin fragmentos no se envían al modelo: la plantilla escribe directamente «Sin norma aplicable en el corpus». Así se ahorran llamadas; la regla 3 del prompt se mantiene para el caso en que el modelo lo decida.

## D9. Clasificador de E2 sin respaldo

- El clasificador usa el alias `rapido` sin pasar al respaldo (`completo`): si `rapido` no responde, E2 se queda con los patrones y la traza registra `E2_sin_clasificador`. Así el clasificador no bloquea el servicio ni dispara el modelo grande.

## D10. Rechazos de la API frente a rechazos de C3

- La API valida perfil, extensión y tamaño antes de llamar a C2. Esas respuestas (413/415/422) llevan solo `detalle`. Todos los rechazos de C3 y los errores de C2 (incluido el 503) pasan por S4 y llevan `aviso`.

## D11. Contrato de respuesta y preguntas

- `POST /auditorias` devuelve los campos del Código 6 y además `archivo`, `perfil`, `perfil_nombre`, `uso_respaldo`, `versiones` y, por hallazgo, `descripcion` y `norma_esperada`. `fuente` incluye también `id`, `doc_id` y `pagina`.
- `cache` toma los valores `ninguna`, `exacta`, `hallazgos` (aciertos de la caché de hallazgos) o `semantica` (solo preguntas).
- `uso_respaldo` del informe es verdadero si hubo respaldo en cualquier llamada de la auditoría, incluidas las reformulaciones del agente.
- En las preguntas, el propio informe se entrega como un fragmento citable `informe:<auditoria_id>#1`, para que el modelo pueda usar sus mediciones sin violar S3.

## D12. Retroalimentación por `traza_id`

- `POST /retroalimentacion` recibe `traza_id`, `util`, `comentario` y `hallazgo_id`. Responde 404 si la traza no corresponde a un informe o si el hallazgo no pertenece a él.

## D13. E5: licencia y cuarentena

- La licencia sale del formulario, del front matter o del texto, y debe estar en `guardrails.licencias_permitidas`. Si falta o no está permitida: 422. Un documento con instrucciones inyectadas se registra en estado `cuarentena` (no se indexa) y la API responde 422.

## D14. Orden de las fases

- `servicio/ingestar.py` (fase 4) y el núcleo de `composicion.py` (fase 9) se escribieron en las fases 9 y 8: el punto de entrada necesita la raíz de composición, y las pruebas de C2 usan la misma composición que la API.

## D15. ADR reconstruidos

- Los 8 ADR de `docs/adr/` se redactaron a partir de las decisiones de la especificación. Hay que contrastar títulos y numeración con el informe.

## D16. Tablas 16–23

- Sin el PDF, el contenido de cada tabla se infirió: 16 producto, 17 recuperación, 18 guardrails, 19 caché, 20 enrutador, 21 agente, 22 fallas y 23 latencias. `run_eval.py` corre la API en proceso (TestClient, mismo código que uvicorn) o contra `--url`. La tabla 22 necesita el modo en proceso, porque inyecta fallas en el adaptador.

## D17. Corpus

- `perfiles.yaml` apunta a cuatro documentos: `blender_manual`, `gltf_spec`, `guia_tiempo_real` y `guia_impresion3d`. En `tests/corpus/` hay versiones sintéticas (CC0) con esas secciones. Las fuentes reales y sus licencias se listan en `corpus/README.md`; hay que verificarlas antes de usarlas.

## D18. Mutaciones M4 y M5

- M4 crea la arista no manifold con una aleta triangular, que además abre la malla (V5 en impresión 3D).
- M5 crea caras degeneradas colapsando un vértice sobre la arista opuesta, lo que mantiene la malla cerrada.

## D19. Trazas sin pasar por C7

- T1 es una capa abierta y escribe `data/trazas.jsonl` directamente con la biblioteca estándar. El criterio solo restringe `httpx`, `chromadb`, `sqlite3` y la lectura de mallas y documentos.

## D20. Entorno

- En la nube se probó con Python 3.13; el CI (GitHub Actions) usa Python 3.11, la versión del Mac. El código evita sintaxis posterior a 3.11.
- `<model-viewer>` 4.1.0 se obtuvo con npm y está en `web/vendor/` (Apache-2.0).
