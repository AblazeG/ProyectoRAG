"""Repositorios SQLite (C7): caché, informes, documentos, manifiesto y
retroalimentación. Los informes viven en su propia tabla, fuera de la caché,
para que purgar o expirar la caché nunca rompa ``GET /auditorias/{id}``."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from servicio.dominio import ErrorDatos

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cache (
    espacio TEXT NOT NULL, clave TEXT NOT NULL, valor TEXT NOT NULL,
    version_corpus INTEGER NOT NULL, creado REAL NOT NULL, expira REAL NOT NULL,
    PRIMARY KEY (espacio, clave));
CREATE TABLE IF NOT EXISTS cache_semantica (
    id INTEGER PRIMARY KEY AUTOINCREMENT, grupo TEXT NOT NULL, vector TEXT NOT NULL,
    valor TEXT NOT NULL, version_corpus INTEGER NOT NULL,
    creado REAL NOT NULL, expira REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_sem_grupo ON cache_semantica(grupo);
CREATE TABLE IF NOT EXISTS informes (
    auditoria_id TEXT PRIMARY KEY, traza_id TEXT, archivo_sha TEXT, perfil TEXT,
    creado REAL NOT NULL, informe TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_inf_traza ON informes(traza_id);
CREATE TABLE IF NOT EXISTS documentos (
    doc_id TEXT PRIMARY KEY, datos TEXT NOT NULL, creado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS manifiesto (
    id INTEGER PRIMARY KEY CHECK (id = 1), datos TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retroalimentacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT, traza_id TEXT NOT NULL,
    hallazgo_id TEXT, util INTEGER NOT NULL, comentario TEXT, creado REAL NOT NULL);
"""


class BaseSQLite:
    """Conexión compartida y protegida por candado (FastAPI usa hilos)."""

    nombre = "sqlite"

    def __init__(self, ruta: Path | str):
        self.ruta = str(ruta)
        if self.ruta != ":memory:":
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._con = sqlite3.connect(self.ruta, check_same_thread=False)
            self._con.row_factory = sqlite3.Row
            if self.ruta != ":memory:":
                self._con.execute("PRAGMA journal_mode=WAL")
            self._con.executescript(ESQUEMA)
            self._con.commit()
        except sqlite3.Error as exc:
            raise ErrorDatos(f"No se pudo abrir SQLite: {exc}") from exc
        self._candado = threading.RLock()

    def ejecutar(self, sql: str, parametros: tuple = ()) -> sqlite3.Cursor:
        with self._candado:
            try:
                cursor = self._con.execute(sql, parametros)
                self._con.commit()
                return cursor
            except sqlite3.Error as exc:
                raise ErrorDatos(f"Error de SQLite: {exc}") from exc

    def consultar(self, sql: str, parametros: tuple = ()) -> list[sqlite3.Row]:
        with self._candado:
            try:
                return self._con.execute(sql, parametros).fetchall()
            except sqlite3.Error as exc:
                raise ErrorDatos(f"Error de SQLite: {exc}") from exc

    def comprobar(self) -> dict:
        try:
            self.consultar("SELECT 1")
            return {"ok": True, "ruta": self.ruta}
        except ErrorDatos as exc:
            return {"ok": False, "detalle": exc.mensaje}


class AlmacenCacheSQLite:
    """Puerto ``AlmacenClaveValor`` para C4."""

    def __init__(self, base: BaseSQLite):
        self.base = base

    def obtener(self, espacio: str, clave: str, ahora: float) -> dict | None:
        filas = self.base.consultar(
            "SELECT valor FROM cache WHERE espacio=? AND clave=? AND expira>?",
            (espacio, clave, ahora))
        return json.loads(filas[0]["valor"]) if filas else None

    def guardar(self, espacio: str, clave: str, valor: dict, version_corpus: int,
                expira: float, ahora: float) -> None:
        self.base.ejecutar(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?,?)",
            (espacio, clave, json.dumps(valor, ensure_ascii=False),
             version_corpus, ahora, expira))

    def guardar_semantica(self, grupo: str, vector: list[float], valor: dict,
                          version_corpus: int, expira: float, ahora: float) -> None:
        self.base.ejecutar(
            "INSERT INTO cache_semantica (grupo, vector, valor, version_corpus, creado,"
            " expira) VALUES (?,?,?,?,?,?)",
            (grupo, json.dumps(vector), json.dumps(valor, ensure_ascii=False),
             version_corpus, ahora, expira))

    def listar_semantica(self, grupo: str, ahora: float) -> list[dict]:
        filas = self.base.consultar(
            "SELECT vector, valor, version_corpus FROM cache_semantica"
            " WHERE grupo=? AND expira>?", (grupo, ahora))
        return [{"vector": json.loads(f["vector"]), "valor": json.loads(f["valor"]),
                 "version_corpus": f["version_corpus"]} for f in filas]

    def purgar(self, version_corpus: int) -> int:
        a = self.base.ejecutar("DELETE FROM cache WHERE version_corpus<?",
                               (version_corpus,)).rowcount
        b = self.base.ejecutar("DELETE FROM cache_semantica WHERE version_corpus<?",
                               (version_corpus,)).rowcount
        return a + b

    def eliminar_expirados(self, ahora: float) -> int:
        a = self.base.ejecutar("DELETE FROM cache WHERE expira<=?", (ahora,)).rowcount
        b = self.base.ejecutar("DELETE FROM cache_semantica WHERE expira<=?",
                               (ahora,)).rowcount
        return a + b

    def contar(self) -> dict:
        exacta = self.base.consultar("SELECT espacio, COUNT(*) n FROM cache GROUP BY espacio")
        sem = self.base.consultar("SELECT COUNT(*) n FROM cache_semantica")
        return {**{f["espacio"]: f["n"] for f in exacta}, "semantica": sem[0]["n"]}


class RepositorioInformesSQLite:
    def __init__(self, base: BaseSQLite):
        self.base = base

    def guardar(self, informe: dict, archivo_sha: str) -> None:
        self.base.ejecutar(
            "INSERT OR REPLACE INTO informes VALUES (?,?,?,?,?,?)",
            (informe["auditoria_id"], informe.get("traza_id"), archivo_sha,
             informe.get("perfil"), time.time(),
             json.dumps(informe, ensure_ascii=False)))

    def obtener(self, auditoria_id: str) -> dict | None:
        filas = self.base.consultar(
            "SELECT informe, archivo_sha FROM informes WHERE auditoria_id=?",
            (auditoria_id,))
        if not filas:
            return None
        informe = json.loads(filas[0]["informe"])
        informe["_archivo_sha"] = filas[0]["archivo_sha"]
        return informe

    def obtener_por_traza(self, traza_id: str) -> dict | None:
        filas = self.base.consultar(
            "SELECT auditoria_id FROM informes WHERE traza_id=?", (traza_id,))
        return self.obtener(filas[0]["auditoria_id"]) if filas else None


class RepositorioDocumentosSQLite:
    def __init__(self, base: BaseSQLite):
        self.base = base

    def guardar(self, documento: dict) -> None:
        self.base.ejecutar(
            "INSERT OR REPLACE INTO documentos VALUES (?,?,?)",
            (documento["doc_id"], json.dumps(documento, ensure_ascii=False), time.time()))

    def obtener(self, doc_id: str) -> dict | None:
        filas = self.base.consultar("SELECT datos FROM documentos WHERE doc_id=?", (doc_id,))
        return json.loads(filas[0]["datos"]) if filas else None

    def listar(self) -> list[dict]:
        filas = self.base.consultar("SELECT datos FROM documentos ORDER BY creado")
        return [json.loads(f["datos"]) for f in filas]

    def eliminar(self, doc_id: str) -> bool:
        return self.base.ejecutar("DELETE FROM documentos WHERE doc_id=?",
                                  (doc_id,)).rowcount > 0


class RepositorioManifiestoSQLite:
    def __init__(self, base: BaseSQLite):
        self.base = base

    def leer(self) -> dict:
        filas = self.base.consultar("SELECT datos FROM manifiesto WHERE id=1")
        return json.loads(filas[0]["datos"]) if filas else {}

    def guardar(self, manifiesto: dict) -> None:
        self.base.ejecutar("INSERT OR REPLACE INTO manifiesto VALUES (1, ?)",
                           (json.dumps(manifiesto, ensure_ascii=False),))


class RepositorioRetroalimentacionSQLite:
    def __init__(self, base: BaseSQLite):
        self.base = base

    def guardar(self, registro: dict) -> None:
        self.base.ejecutar(
            "INSERT INTO retroalimentacion (traza_id, hallazgo_id, util, comentario,"
            " creado) VALUES (?,?,?,?,?)",
            (registro["traza_id"], registro.get("hallazgo_id"), int(registro["util"]),
             registro.get("comentario"), time.time()))

    def resumen(self) -> dict:
        fila = self.base.consultar(
            "SELECT COUNT(*) total, COALESCE(SUM(util),0) utiles FROM retroalimentacion")[0]
        total, utiles = fila["total"], fila["utiles"]
        return {"total": total, "utiles": utiles, "no_utiles": total - utiles,
                "tasa_utilidad": (utiles / total) if total else None}
