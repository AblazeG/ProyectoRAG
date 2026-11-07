"""Utilidades de evaluación y experimentos: clientes de la API, trazas, CSV y estadísticos."""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DIR_EVAL = RAIZ / "evaluacion"
RESULTADOS = DIR_EVAL / "resultados"
MALLAS_GENERADAS = DIR_EVAL / "mallas_generadas"
CORPUS_PRUEBA = RAIZ / "tests" / "corpus"
OLLAMA = "http://127.0.0.1:11434"


def argumentos_comunes(parser) -> None:
    parser.add_argument("--proveedor", default=os.environ.get("MESHAUDIT_PROVEEDOR", "ollama"),
                        choices=["falso", "ollama"])
    parser.add_argument("--corpus", type=Path, default=None,
                        help="corpus a ingerir (por defecto: corpus/ con Ollama, tests/corpus/ en falso)")
    parser.add_argument("--salida", type=Path, default=RESULTADOS)


def corpus_por_defecto(args) -> Path:
    if args.corpus:
        return args.corpus
    return CORPUS_PRUEBA if args.proveedor == "falso" else RAIZ / "corpus"


def cargar(nombre: str):
    return json.loads((DIR_EVAL / nombre).read_text(encoding="utf-8"))


def escribir_csv(ruta: Path, filas: list[dict]) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    campos: list[str] = []
    for fila in filas:
        for k in fila:
            if k not in campos:
                campos.append(k)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos or ["sin_datos"])
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                               for k, v in fila.items()})
    return ruta


def estadisticos(valores: list[float]) -> dict:
    if not valores:
        return {"mediana": None, "p95": None, "maximo": None}
    a = np.asarray(valores, float)
    return {"mediana": round(float(np.median(a)), 2), "p95": round(float(np.percentile(a, 95)), 2),
            "maximo": round(float(a.max()), 2)}


@contextmanager
def entorno(**variables):
    anterior = {k: os.environ.get(k) for k in variables}
    os.environ.update({k: str(v) for k, v in variables.items() if v is not None})
    try:
        yield
    finally:
        for k, v in anterior.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


_INDICES: dict[tuple, Path] = {}


class Sesion:
    """Cliente HTTP de la API: externo (``--url``) o en proceso (TestClient)."""

    def __init__(self, url: str | None = None, proveedor: str = "falso", cache: bool = True,
                 corpus: Path | None = None, falla: str | None = None, dir_datos: Path | None = None,
                 trazas: Path | None = None, vectorial: str = "memoria", chats: dict | None = None,
                 variables: dict | None = None):
        self.contenedor = None
        if url:
            import httpx
            self.http = httpx.Client(base_url=url.rstrip("/"), timeout=600)
            self.ruta_trazas = trazas
            return
        from fastapi.testclient import TestClient
        from servicio.composicion import construir, crear_aplicacion
        # Las sesiones con el mismo corpus comparten el índice (Chroma persistente) para
        # no volver a generar los embeddings de todo el corpus en cada sesión.
        clave = None
        if corpus and dir_datos is None:
            clave = (proveedor, str(Path(corpus).resolve()),
                     (variables or {}).get("MESHAUDIT_MODELO_EMBEDDINGS",
                                           os.environ.get("MESHAUDIT_MODELO_EMBEDDINGS", "")))
            vectorial = "chroma"
        reutiliza = clave in _INDICES
        self.dir_datos = Path(dir_datos or _INDICES.get(clave)
                              or tempfile.mkdtemp(prefix="meshaudit_eval_"))
        with entorno(MESHAUDIT_FALLA=falla, **(variables or {})):
            self.contenedor = construir(proveedor=proveedor, dir_datos=self.dir_datos,
                                        cache_activa=cache, vectorial=vectorial, chats=chats,
                                        dormir=(lambda s: None) if proveedor == "falso" else None)
        self.http = TestClient(crear_aplicacion(self.contenedor))
        self.ruta_trazas = self.dir_datos / "trazas.jsonl"
        if corpus and not reutiliza:
            self.ingestar(corpus)
            if clave:
                _INDICES[clave] = self.dir_datos

    def ingestar(self, directorio: Path):
        from servicio.datos.documentos import listar_corpus
        documentos = listar_corpus(directorio)
        if not documentos:
            print(f"aviso: no hay documentos en {directorio}", file=sys.stderr)
        for archivo, meta in documentos:
            datos = {k: (",".join(v) if isinstance(v, list) else v) for k, v in meta.items()
                     if k in ("licencia", "doc_id", "perfiles", "titulo")}
            r = self.http.post("/documentos", files={"archivo": (archivo.nombre, archivo.contenido)},
                               data=datos)
            if r.status_code != 201:
                print(f"aviso: {archivo.nombre} no se ingirió ({r.status_code}): "
                      f"{r.json().get('detalle', r.text)}", file=sys.stderr)

    def vaciar_cache(self) -> None:
        """Borra la caché exacta y semántica (las sesiones comparten la base de datos)."""
        if self.contenedor is not None:
            self.contenedor.cache.purgar(10 ** 9)

    def auditar(self, ruta: Path, perfil: str, notas: str = ""):
        return self.http.post("/auditorias", files={"archivo": (ruta.name, ruta.read_bytes())},
                              data={"perfil": perfil, "notas": notas})

    def preguntar(self, auditoria_id: str, pregunta: str):
        return self.http.post(f"/auditorias/{auditoria_id}/preguntas", json={"pregunta": pregunta})

    def trazas(self) -> dict[str, dict]:
        if not self.ruta_trazas or not Path(self.ruta_trazas).exists():
            return {}
        salida = {}
        for linea in Path(self.ruta_trazas).read_text(encoding="utf-8").splitlines():
            try:
                t = json.loads(linea)
                salida[t["traza_id"]] = t
            except (json.JSONDecodeError, KeyError):
                continue
        return salida


def mallas(directorio: Path | None, proveedor: str) -> Path:
    """Directorio con ``<base>_base.obj`` y ``<base>_M1.obj``…; en modo falso se
    generan las mallas sintéticas si faltan."""
    directorio = Path(directorio or MALLAS_GENERADAS)
    if not any(directorio.glob("*_base.obj")):
        if proveedor != "falso" and directorio != MALLAS_GENERADAS:
            raise SystemExit(f"Faltan mallas en {directorio}: ejecuta mutar_blender.py primero.")
        from evaluacion.sinteticas import generar
        generar(directorio)
    return directorio


def embeddings_para(modelo: str, proveedor: str, url: str = "http://127.0.0.1:11434"):
    if proveedor == "falso":
        from servicio.datos.falsos import EmbeddingsFalsos
        return EmbeddingsFalsos(nombre=f"falso-{modelo}")
    from servicio.datos.ollama import EmbeddingsOllama
    return EmbeddingsOllama(modelo, url, tiempo_limite_s=120)


def chat_para(modelo: str, proveedor: str, url: str = "http://127.0.0.1:11434"):
    if proveedor == "falso":
        from servicio.datos.falsos import ChatFalso
        return ChatFalso(f"falso-{modelo}")
    from servicio.datos.ollama import ChatOllama
    return ChatOllama(modelo, url)


def indice_en_memoria(embeddings, corpus: Path, tam: int = 800, solape: int = 120):
    """Índice y recuperador en memoria (experimentos: sin tocar data/)."""
    from servicio.contexto.recuperador import Indice, Recuperador
    from servicio.datos.documentos import LectorDocumentos, listar_corpus
    from servicio.datos.memoria import AlmacenMemoria
    from servicio.datos.sqlite import BaseSQLite, RepositorioDocumentosSQLite, RepositorioManifiestoSQLite
    base = BaseSQLite(":memory:")
    almacen = AlmacenMemoria()
    indice = Indice(embeddings, almacen, RepositorioManifiestoSQLite(base),
                    RepositorioDocumentosSQLite(base), LectorDocumentos(), tam, solape)
    for archivo, meta in listar_corpus(corpus):
        _, fragmentos, registro = indice.extraer_y_fragmentar(
            archivo, meta.get("licencia") or "CC0-1.0", meta.get("doc_id"),
            meta.get("perfiles"), meta.get("titulo"))
        indice.indexar(fragmentos, registro)
    return indice, Recuperador(embeddings, almacen)


def evaluar_recuperacion(recuperador, casos: list[dict], k: int, umbral: float) -> dict:
    """Acierto@1, acierto@k, MRR y rechazos correctos sobre casos_recuperacion.json.

    La relevancia se define por documento y sección, no por id de fragmento,
    para comparar tamaños de fragmento (sección 9.1). Un acierto exige la
    sección entre los k primeros y sobre el umbral.
    """
    aciertos1, aciertos, reciprocos, rechazos, n_rel, n_neg = 0, 0, 0.0, 0, 0, 0
    for caso in casos:
        r = recuperador.recuperar(caso["consulta"], k=k, umbral=umbral)
        if caso["relevante"]:
            n_rel += 1
            rango = next((i + 1 for i, x in enumerate(r.fragmentos)
                          if x.fragmento.doc_id == caso["documento"]
                          and x.fragmento.seccion == caso["seccion"]), None)
            aciertos1 += rango == 1
            aciertos += rango is not None
            reciprocos += 1 / rango if rango else 0
        else:
            n_neg += 1
            rechazos += not r.fragmentos
    return {"acierto_1": round(aciertos1 / n_rel, 3) if n_rel else None,
            "acierto_k": round(aciertos / n_rel, 3) if n_rel else None,
            "mrr": round(reciprocos / n_rel, 3) if n_rel else None,
            "rechazos_correctos": rechazos, "rechazos_de": n_neg}
