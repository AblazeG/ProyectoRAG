# MeshAudit

**Auditor técnico de modelos 3D con normas citadas, ejecutado de forma local.**

MeshAudit recibe un archivo de malla (`.obj`, `.glb`, `.stl`, `.ply`) y un perfil de destino
(Animación, Juego móvil, Impresión 3D o Web/AR) y entrega un informe de auditoría con:
- un semáforo;
- los hallazgos con su gravedad, el valor medido frente al límite;
- la norma técnica que los respalda (recuperada con RAG);
- los pasos de corrección en Blender.

La decisión central es separar *medir* de *interpretar*:
- un analizador determinista calcula todas las métricas;
- los modelos de lenguaje nunca generan mediciones, solo explican cada hallazgo con fragmentos citados del corpus.

Proyecto integrador de *Tópicos selectos de arquitectura de software* (Unidad II), Maestría en
Ciencias e Innovación Tecnológica, UPChiapas. Diseño completo en
[`docs/Informe_tecnico_MeshAudit.pdf`](docs/Informe_tecnico_MeshAudit.pdf); ADR en [`docs/adr/`](docs/adr/);
diferencias con el informe en [`docs/DESVIACIONES.md`](docs/DESVIACIONES.md).

## Arquitectura (sección 4 del informe)

```
Aplicación web (HTML + JS) ──HTTP──▶ C1 API (FastAPI)
                                       │
                                       ▼
                                C2 Orquestación y agente (mediador)
              ┌──────────────┬─────────┴──────┬───────────────┐
              ▼              ▼                ▼               ▼
        C3 Guardrails    C4 Caché       C5 Contexto      C6 Modelos        T1 Observabilidad (abierta)
        E1–E5, S1–S4     exacta y       analizar_malla,  enrutador,        T2 Retroalimentación (abierta)
        (usa C6 en E2)   semántica      RAG, prompts     gateway, respaldo
              └──────────────┴─────────┬──────┴───────────────┘
                                       ▼
                    C7 Acceso a datos: Ollama · ChromaDB · SQLite · archivos
```

- `servicio/dominio.py`: entidades y puertos (`typing.Protocol`).
- `servicio/composicion.py`: raíz de composición, el único lugar que conoce las implementaciones.
- `tests/test_arquitectura.py`: falla si una capa importa algo que no tiene permitido (Código 2).

## Estructura del repositorio (Código 6)

```
meshaudit/
  web/                  # Presentación: HTML + JS, consume solo la API
  servicio/
    dominio.py          # Entidades y puertos (Protocol)
    api/                # C1  Interfaz del servicio
    orquestacion/       # C2  Flujo de auditoría, ingesta, preguntas y ciclo de agente
    guardrails/         # C3  Verificaciones de entrada y salida
    cache/              # C4  Caché exacta y semántica
    contexto/           # C5  analizar_malla, perfiles, RAG y prompts
    modelos/            # C6  Enrutador y gateway
    datos/              # C7  Adaptadores: Ollama, Chroma, SQLite, trimesh, documentos
    observabilidad/     # T1  Trazas, bitácoras y métricas
    retroalimentacion/  # T2  Opinión del usuario ligada a la traza
    composicion.py      # Raíz de composición
    ingestar.py         # Ingesta inicial del corpus desde una carpeta
  config/perfiles.yaml  # Límites por perfil de destino (y config/servicio.yaml)
  corpus/               # Documentos normativos con su licencia
  data/                 # Generado: chroma/, meshaudit.sqlite, trazas.jsonl, mallas/
  experimentos/         # experimento_llm.py, _embeddings.py, _fragmentos.py, _cache.py
  evaluacion/           # Conjuntos de prueba, run_eval.py y resultados CSV
  tests/                # Pruebas por capa y test_arquitectura.py
  docs/                 # Informe, especificación, diagramas y ADR
```

## Instalación y ejecución (Código 7)

Requisitos: macOS con Apple Silicon, Python 3.11, Ollama 0.40 o posterior y unos 45 GB libres en
disco (unos 30 GB sin el juez). Equipo de referencia: M4 Max, 128 GB. Todo escucha solo en `127.0.0.1`.

```bash
# 1. Modelos locales (sin nube)
launchctl setenv OLLAMA_NO_CLOUD 1      # luego reiniciar la app de Ollama
ollama pull gemma4:e2b                  # ruta rápida (ADR-01)
ollama pull qwen3:8b                    # candidato del experimento
ollama pull gpt-oss:20b                 # ruta completa (ADR-01)
ollama pull bge-m3                      # embeddings del servicio (ADR-02)
ollama pull embeddinggemma              # candidato del experimento
ollama pull nomic-embed-text            # candidato del experimento
ollama pull mistral-small3.2:24b        # solo para la evaluación (juez)

# 2. Entorno de Python
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -c restricciones.txt   # versiones con las que pasó la suite

# 3. Ingesta del corpus (ver corpus/README.md)
python -m servicio.ingestar corpus/

# 4. Servicio y aplicación web (dos terminales)
uvicorn servicio.composicion:app --host 127.0.0.1 --port 8000
python -m http.server 5173 --bind 127.0.0.1 -d web
# Web: http://localhost:5173   API: http://localhost:8000/docs

# 5. Pruebas
MESHAUDIT_PROVEEDOR=falso pytest -q

# 6. Experimentos de selección (tablas 8, 9, 17/18 y 22). experimento_llm va antes de
#    run_eval: escribe muestra_revision_manual.csv, que se califica a mano para la
#    validación del juez (fila juez–autor de la tabla 16).
python -m experimentos.experimento_llm --juez --salida evaluacion/resultados/
for e in embeddings fragmentos cache; do
  python -m experimentos.experimento_$e --salida evaluacion/resultados/
done

# 7. Evaluación (tablas 16–23, fallas, privacidad y retroalimentación)
python evaluacion/run_eval.py --juez --salida evaluacion/resultados/
```

La web solo habla con la API (nunca con Ollama ni ChromaDB). Si la API está en otra dirección:
`http://localhost:5173/?api=http://127.0.0.1:8001`.

### App para Mac

`app_mac/MeshAudit.app` arranca Ollama, la API y la web con un doble clic, abre el navegador
en `http://localhost:5173` y, al salir de la app, detiene la API y la web (Ollama se queda abierto).
Usa el `.venv` del repositorio, así que la app debe quedarse dentro de `app_mac/`.

```bash
zsh app_mac/crear_app.sh            # genera (o regenera) MeshAudit.app
zsh app_mac/meshaudit.sh estado     # iniciar | detener | estado, también desde la terminal
```

Registros: `~/Library/Logs/MeshAudit/api.log` y `web.log`.

### Sin Ollama (proveedor falso)

Para pruebas y demostraciones sin modelos, con dobles deterministas (`ChatFalso`, `EmbeddingsFalsos`):

```bash
export MESHAUDIT_PROVEEDOR=falso
python -m servicio.ingestar tests/corpus/       # corpus sintético de prueba
uvicorn servicio.composicion:app --host 127.0.0.1 --port 8000
```

## Configuración

- `config/servicio.yaml`: modelos por alias, `num_ctx` 8192, `keep_alive` 30m, k = 5, umbral 0.55, lotes de hasta 4, tiempos límite 45/90 s, reintentos 1 y 2 s, caché (7 días / 24 h, 0.92), guardrails y licencias.
- `config/perfiles.yaml`: verificaciones V1–V11 por perfil (tabla 11), con unidad y puntero `norma`.

| Variable | Uso |
|---|---|
| `MESHAUDIT_PROVEEDOR=ollama\|falso` | proveedor de modelos |
| `MESHAUDIT_VECTORIAL=chroma\|memoria` | almacén vectorial (segundo adaptador: modificabilidad) |
| `MESHAUDIT_DATOS=ruta` | directorio de datos (por defecto `data/`) |
| `MESHAUDIT_CACHE=0` | desactiva la caché (latencias de la tabla 23) |
| `MESHAUDIT_MODELO_RAPIDO`, `_COMPLETO`, `_EMBEDDINGS` | cambian el modelo de un alias |
| `MESHAUDIT_FALLA=alias:tipo[:n]` | inyecta fallas en el adaptador (evaluación de disponibilidad) |
| `MESHAUDIT_OLLAMA_URL` | por defecto `http://127.0.0.1:11434` |

## API (Anexo B)

| Método y ruta | Propósito | Códigos |
|---|---|---|
| `GET /health` | Estado de Ollama, ChromaDB, SQLite y modelos | 200, 503 |
| `POST /documentos` | Sube una norma (E5, fragmenta, indexa, versión++) → `documento_id`, fragmentos | 201, 413, 415, 422, 503 |
| `GET /documentos` | Documentos con identificador, nombre, formato, fecha y fragmentos | 200 |
| `DELETE /documentos/{id}` | Elimina el documento y sus fragmentos; sube la versión del corpus | 200, 404 |
| `POST /auditorias` | Función principal (multipart: `archivo`, `perfil`, `notas`) | 200, 413, 415, 422, 503 |
| `GET /auditorias/{id}` | Informe generado | 200, 404 |
| `GET /auditorias/{id}/markdown` | Exporta el informe a Markdown | 200, 404 |
| `POST /auditorias/{id}/preguntas` | Pregunta de seguimiento con fuentes | 200, 404, 422, 503 |
| `POST /retroalimentacion` | Útil o no útil y comentario, ligados a la traza y opcionalmente a un hallazgo | 201, 404, 422 |
| `GET /metricas` | Latencias por capa, caché, guardrails, uso por modelo y retroalimentación | 200 |
| `GET /configuracion` | Modelos activos, k, umbrales, tiempos límite y expiraciones | 200 |
| `GET /perfiles` | Perfiles de destino y sus límites | 200 |

```bash
curl -F archivo=@tests/mallas/prisma_ngon.obj -F perfil=animacion http://127.0.0.1:8000/auditorias
```

La respuesta sigue el Código 8: `auditoria_id`, `resumen`, `semaforo`, `metricas_malla`,
`hallazgos[]` (`id`, `verificacion`, `tipo`, `gravedad`, `medido`, `limite`, `explicacion`,
`correccion[]`, `fuente{documento, seccion, puntaje, fragmento}`), `modelo`, `ruta`, `cache`,
`guardrails{entrada, salida}`, `iteraciones_agente`, `tiempo_ms`, `traza_id` y `aviso`.

## Evaluación (sección 9)

```bash
# Mutaciones M1–M5 (tabla 3) de las cinco mallas base CC0 de evaluacion/mallas_base/
blender -b -P evaluacion/mutar_blender.py -- evaluacion/mallas_base evaluacion/mallas_generadas
# Conjuntos de prueba (tabla 15) con la línea base de tus mallas; revísala a mano
python -m evaluacion.plantillas --bases silla,personaje,engrane,escaneo,lampara
# Tabla 8 y muestra para validar al juez (califica a mano las columnas nota_autor_*)
python -m experimentos.experimento_llm --juez --salida evaluacion/resultados/
# Tablas 16–23, fallas, privacidad y retroalimentación
python evaluacion/run_eval.py --juez --salida evaluacion/resultados/
# Texto y tablas para cada «[Pendiente]» del informe (docs/REVISION_INFORME.md)
python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/
```

Con Ollama, `run_eval.py` se detiene si faltan las mallas de Blender que piden los casos;
`--mallas-sinteticas` las sustituye por las de `evaluacion/sinteticas.py` (requiere Pillow),
pero esas cifras no son las del informe. Sin Ollama, `python evaluacion/run_eval.py
--proveedor falso` usa siempre las mallas sintéticas y el corpus de prueba. Cada sesión de la
evaluación tiene su propia base SQLite y sus trazas (solo comparte el índice de Chroma) y sus
directorios temporales se borran al terminar. `docs/DESVIACIONES.md` (sección C) indica qué
archivo llena cada «[Pendiente]» del informe.

## Pruebas

```bash
MESHAUDIT_PROVEEDOR=falso pytest -q
```

Incluyen pruebas por capa, la prueba de arquitectura, la prueba de C2 que recorre todos los caminos
de respuesta y falla si alguno omite S4, y pruebas de extremo a extremo con `TestClient` (una auditoría
por perfil). GitHub Actions las ejecuta con Python 3.11 en cada push.
