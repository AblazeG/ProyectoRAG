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


class Sesion:
    """Cliente HTTP de la API: externo (``--url``) o en proceso (TestClient)."""

    def __init__(self, url: str | None = None, proveedor: str = "falso", cache: bool = True,
                 corpus: Path | None = None, falla: str | None = None, dir_datos: Path | None = None,
                 trazas: Path | None = None, vectorial: str = "memoria", chats: dict | None = None):
        self.contenedor = None
        if url:
            import httpx
            self.http = httpx.Client(base_url=url.rstrip("/"), timeout=600)
            self.ruta_trazas = trazas
            return
        from fastapi.testclient import TestClient
        from servicio.composicion import construir, crear_aplicacion
        self.dir_datos = Path(dir_datos or tempfile.mkdtemp(prefix="meshaudit_eval_"))
        with entorno(MESHAUDIT_FALLA=falla):
            self.contenedor = construir(proveedor=proveedor, dir_datos=self.dir_datos,
                                        cache_activa=cache, vectorial=vectorial, chats=chats,
                                        dormir=(lambda s: None) if proveedor == "falso" else None)
        self.http = TestClient(crear_aplicacion(self.contenedor))
        self.ruta_trazas = self.dir_datos / "trazas.jsonl"
        if corpus:
            self.ingestar(corpus)

    def ingestar(self, directorio: Path):
        from servicio.datos.documentos import listar_corpus
        for archivo, meta in listar_corpus(directorio):
            datos = {k: (",".join(v) if isinstance(v, list) else v) for k, v in meta.items()
                     if k in ("licencia", "doc_id", "perfiles", "titulo")}
            self.http.post("/documentos", files={"archivo": (archivo.nombre, archivo.contenido)},
                           data=datos)

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


class DirMallas:
    """Resuelve ``M1.obj`` tanto en mallas sintéticas (``M1.obj``) como en las de
    Blender (``<malla>_M1.obj``; con ``prefijo`` se elige la malla base)."""

    def __init__(self, ruta: Path, prefijo: str | None = None):
        self.ruta = Path(ruta)
        self.prefijo = prefijo

    def __truediv__(self, nombre: str) -> Path:
        directa = self.ruta / (f"{self.prefijo}_{nombre}" if self.prefijo else nombre)
        if directa.exists():
            return directa
        candidatas = sorted(self.ruta.glob(f"*_{nombre}"))
        if not candidatas:
            raise FileNotFoundError(f"No encuentro {nombre} en {self.ruta}")
        return candidatas[0]

    def __str__(self) -> str:
        return str(self.ruta)


def mallas(directorio: Path | None, proveedor: str, prefijo: str | None = None) -> DirMallas:
    """Directorio con base y M1–M5; en modo falso se generan si faltan."""
    directorio = Path(directorio or MALLAS_GENERADAS)
    hay = (directorio / "base.obj").exists() or any(directorio.glob("*_base.obj"))
    if not hay:
        if proveedor != "falso" and directorio != MALLAS_GENERADAS:
            raise SystemExit(f"Faltan mallas en {directorio}: ejecuta mutar_blender.py primero.")
        from evaluacion.sinteticas import generar
        generar(directorio)
    return DirMallas(directorio, prefijo)


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
        documento = indice.extraer(archivo)
        indice.indexar(documento, archivo, meta.get("licencia") or "CC0-1.0", meta.get("doc_id"),
                       meta.get("perfiles"), meta.get("titulo"))
    return indice, Recuperador(embeddings, almacen)


def evaluar_recuperacion(recuperador, casos: list[dict], k: int, umbral: float) -> dict:
    """Acierto@k, MRR y rechazo correcto sobre casos_recuperacion.json."""
    aciertos, reciprocos, rechazos, n_rel, n_neg = 0, 0.0, 0, 0, 0
    for caso in casos:
        r = recuperador.recuperar(caso["consulta"], k=k, umbral=umbral)
        if caso["relevante"]:
            n_rel += 1
            rango = next((i + 1 for i, x in enumerate(r.fragmentos)
                          if x.fragmento.doc_id == caso["documento"]
                          and x.fragmento.seccion == caso["seccion"]), None)
            aciertos += rango is not None
            reciprocos += 1 / rango if rango else 0
        else:
            n_neg += 1
            rechazos += not r.fragmentos
    return {"acierto_k": round(aciertos / n_rel, 3) if n_rel else None,
            "mrr": round(reciprocos / n_rel, 3) if n_rel else None,
            "rechazo_correcto": round(rechazos / n_neg, 3) if n_neg else None}
