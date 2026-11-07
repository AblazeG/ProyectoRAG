# MeshAudit

Servicio local que recibe una malla 3D (OBJ, GLB, STL o PLY) y un perfil de destino
(Animación, Juego móvil, Impresión 3D o Web/AR) y entrega un informe de auditoría:
hallazgos medidos, la norma técnica que los respalda (recuperada con RAG) y los pasos
de corrección. **Los modelos de lenguaje nunca miden la geometría:** un analizador
determinista mide y el modelo solo explica, citando fragmentos del corpus.

Proyecto integrador de la maestría (Tópicos selectos de arquitectura de software).
El diseño está en `docs/` (informe, ADR y [desviaciones](docs/DESVIACIONES.md)).

## Arquitectura

```
web/ (HTML + JS)  ──HTTP──▶  C1 api  ──▶  C2 orquestacion (mediador)
                                             │
                     ┌───────────────┬───────┴──────┬──────────────┐
                     ▼               ▼              ▼              ▼
               C3 guardrails     C4 cache     C5 contexto     C6 modelos
                     └───────────────┴──────┬───────┴──────────────┘
                                            ▼
                     C7 datos: Ollama · ChromaDB · SQLite · mallas · documentos
   T1 observabilidad y T2 retroalimentacion: capas abiertas
```

- `servicio/dominio.py`: entidades y puertos (`typing.Protocol`).
- `servicio/composicion.py`: raíz de composición; único lugar que conoce implementaciones.
- `tests/test_arquitectura.py`: falla ante cualquier importación entre capas no permitida.

## Requisitos (Mac de producción)

- macOS en Apple Silicon (probado para M4 Max, 128 GB), Python 3.11.
- Ollama 0.40 o posterior, sin nube: `OLLAMA_NO_CLOUD=1`.
- Opcional: Blender 4.2 o posterior para las mutaciones de la evaluación.

Todo escucha solo en `127.0.0.1`.

## Puesta en marcha (Anexo A)

```bash
# 1. Ollama local y modelos
export OLLAMA_NO_CLOUD=1
ollama serve &                                # o la app de Ollama con esa variable
ollama pull gemma4:e2b                        # alias «rapido»
ollama pull gpt-oss:20b                       # alias «completo»
ollama pull nomic-embed-text                  # embeddings
ollama pull mistral-small3.2:24b              # juez de la evaluación
ollama pull qwen3:8b                          # experimentos (opcional)
ollama pull bge-m3 && ollama pull embeddinggemma

# 2. Entorno de Python
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Corpus (ver corpus/README.md); para una demostración rápida: tests/corpus/
python -m servicio.ingestar corpus/

# 4. Servicio en 127.0.0.1:8000
uvicorn servicio.composicion:app --host 127.0.0.1 --port 8000

# 5. Aplicación web en 127.0.0.1:5173 (otra terminal)
python -m http.server 5173 --bind 127.0.0.1 -d web
# abre http://127.0.0.1:5173
```

La web solo habla con la API (nunca con Ollama ni ChromaDB). Si la API está en otra
dirección, abre `http://127.0.0.1:5173/?api=http://127.0.0.1:8001`.

### Sin Ollama (proveedor falso)

```bash
MESHAUDIT_PROVEEDOR=falso python -m servicio.ingestar tests/corpus/
MESHAUDIT_PROVEEDOR=falso uvicorn servicio.composicion:app --host 127.0.0.1 --port 8000
```

`ChatFalso` devuelve JSON válido que cita los fragmentos recibidos y `EmbeddingsFalsos`
es un hash determinista de n-gramas. Todo el sistema funciona de punta a punta.

## Configuración

- `config/servicio.yaml`: modelos, umbrales, tiempos límite, reintentos, caché y rutas de datos.
- `config/perfiles.yaml`: límites V1–V11 por perfil, unidad y la norma que justifica cada regla.

Variables de entorno:

| Variable | Valores | Uso |
|---|---|---|
| `MESHAUDIT_PROVEEDOR` | `ollama` · `falso` | proveedor de modelos |
| `MESHAUDIT_VECTORIAL` | `chroma` · `memoria` | almacén vectorial |
| `MESHAUDIT_DATOS` | ruta | directorio de `data/` |
| `MESHAUDIT_CACHE` | `0` · `1` | desactiva la caché (latencias de la evaluación) |
| `MESHAUDIT_OLLAMA_URL` | URL | por defecto `http://127.0.0.1:11434` |
| `MESHAUDIT_FALLA` | `alias:tipo[:n]` | inyecta fallas en el adaptador (`rapido:timeout`, `*:timeout`) |

## API (Anexo B)

| Método y ruta | Propósito |
|---|---|
| `GET /health` | Estado de Ollama, ChromaDB, SQLite y modelos (200 / 503) |
| `POST /documentos` | Sube una norma (E5, fragmenta, indexa, versión++) |
| `GET /documentos` | Lista de documentos y manifiesto |
| `DELETE /documentos/{id}` | Borra el documento y sus fragmentos, versión++ |
| `POST /auditorias` | Multipart: `archivo`, `perfil`, `notas` |
| `GET /auditorias/{id}` | Informe generado |
| `GET /auditorias/{id}/markdown` | Exportar a Markdown |
| `POST /auditorias/{id}/preguntas` | `{"pregunta": "..."}` con fuentes |
| `POST /retroalimentacion` | `{"traza_id", "util", "comentario", "hallazgo_id"}` |
| `GET /metricas` | Métricas de T1 y T2 |
| `GET /configuracion` | Modelos activos, k, umbrales, tiempos límite y expiraciones |
| `GET /perfiles` | Perfiles y límites |

Documentación interactiva: `http://127.0.0.1:8000/docs`.

```bash
curl -F archivo=@tests/mallas/cubo_aleta.obj -F perfil=impresion_3d \
     http://127.0.0.1:8000/auditorias
```

## Pruebas

```bash
MESHAUDIT_PROVEEDOR=falso pytest -q
```

Incluye pruebas por capa, la prueba de arquitectura, la que recorre todos los caminos de
respuesta verificando S4, y pruebas de extremo a extremo con `TestClient` (una auditoría
por perfil). GitHub Actions las corre en cada push con Python 3.11.

## Evaluación

```bash
# Mutaciones M1–M5 de tus mallas base (evaluacion/mallas_base/*.obj)
blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas

# Tablas 16–23 con Ollama real (la API corre en proceso: mismo código que uvicorn)
python -m evaluacion.run_eval --proveedor ollama --corpus corpus/ \
       --mallas evaluacion/mallas_generadas --prefijo <nombre_malla_base> --juez

# Contra un servicio ya levantado (sin la tabla 22 de fallas)
python -m evaluacion.run_eval --url http://127.0.0.1:8000 --trazas data/trazas.jsonl \
       --mallas evaluacion/mallas_generadas --tablas 16,17,18,19,20,21

# En la nube o sin Ollama: mallas sintéticas y corpus de prueba
python -m evaluacion.run_eval --proveedor falso
```

Los CSV quedan en `evaluacion/resultados/` (`tabla16_producto.csv` … `tabla23_latencias.csv`).
Las latencias usan la caché desactivada y cinco corridas por caso (mediana, p95 y máximo).
Para la tabla 23 contra un servicio externo, levántalo con `MESHAUDIT_CACHE=0`.
Las plantillas de casos (`evaluacion/casos_*.json`) se regeneran con
`python -m evaluacion.plantillas`; revísalas con tus mallas reales.

## Experimentos

```bash
python -m experimentos.experimento_llm --proveedor ollama --corpus corpus/ --juez   # gemma4:e2b, qwen3:8b, gpt-oss:20b
python -m experimentos.experimento_embeddings --proveedor ollama --corpus corpus/   # bge-m3, embeddinggemma, nomic-embed-text
python -m experimentos.experimento_fragmentos --proveedor ollama --corpus corpus/   # 500/k8, 800/k5, 1000/k4 y barrido k × umbral
python -m experimentos.experimento_cache --proveedor ollama                         # umbral semántico 0.85–0.95
```

Resultados en `experimentos/resultados/`. Con `--proveedor falso` corren sin Ollama.

## Estructura

```
web/                  Presentación (index, documentos, métricas; vendor/model-viewer)
servicio/
  dominio.py          Entidades y puertos
  api/                C1  app.py, esquemas.py
  orquestacion/       C2  auditor.py, agente.py, ingesta.py, preguntas.py
  guardrails/         C3  entrada.py, salida.py, patrones.py
  cache/              C4  exacta.py, semantica.py
  contexto/           C5  herramientas.py, perfiles.py, fragmentador.py, recuperador.py, prompts.py
  modelos/            C6  enrutador.py, gateway.py
  datos/              C7  ollama.py, chroma.py, memoria.py, sqlite.py, mallas.py, documentos.py, falsos.py
  observabilidad/     T1  traza.py, metricas.py
  retroalimentacion/  T2  almacen.py
  composicion.py      Raíz de composición
  ingestar.py         python -m servicio.ingestar corpus/
config/               perfiles.yaml, servicio.yaml
corpus/               Documentos normativos (ver corpus/README.md)
data/                 Generado: chroma/, meshaudit.sqlite, trazas.jsonl, mallas/
experimentos/         experimento_{llm,embeddings,fragmentos,cache}.py
evaluacion/           casos_*.json, run_eval.py, mutar_blender.py, resultados/
tests/                Pruebas por capa, mallas sintéticas, corpus de prueba
docs/                 Informe, ADR y DESVIACIONES.md
```
