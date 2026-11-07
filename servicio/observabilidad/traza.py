"""Trazas (T1). Cada operación abre una traza, mide etapas y al cerrar escribe
una línea JSON en ``data/trazas.jsonl``. Nunca se guarda el contenido de la
malla, solo su hash."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


# Etapa de la traza (Código 5) -> capa del servicio.
CAPA_DE_ETAPA = {
    "guardrails_entrada": "C3", "guardrails_salida": "C3", "cache": "C4",
    "contexto_malla": "C5", "contexto_rag": "C5", "contexto_extraccion": "C5",
    "contexto_indexado": "C5", "enrutador": "C6", "gateway": "C6",
    "ensamblado": "C2", "persistencia": "C4", "archivo_temporal": "C5",
}


class RegistroTrazas:
    """Sumidero JSONL (capa abierta: lo usan C2, C6 y la API para /metricas)."""

    def __init__(self, ruta: Path | str | None):
        self.ruta = Path(ruta) if ruta else None
        self._candado = threading.Lock()
        self._memoria: list[dict] = []
        if self.ruta:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)

    def escribir(self, registro: dict) -> None:
        linea = json.dumps(registro, ensure_ascii=False, default=str)
        with self._candado:
            if self.ruta:
                with open(self.ruta, "a", encoding="utf-8") as archivo:
                    archivo.write(linea + "\n")
            else:
                self._memoria.append(json.loads(linea))

    def leer(self, limite: int | None = None) -> list[dict]:
        with self._candado:
            if not self.ruta:
                registros = list(self._memoria)
            elif not self.ruta.exists():
                registros = []
            else:
                registros = []
                with open(self.ruta, encoding="utf-8") as archivo:
                    for linea in archivo:
                        try:
                            registros.append(json.loads(linea))
                        except json.JSONDecodeError:
                            continue
        return registros[-limite:] if limite else registros

    def buscar(self, traza_id: str) -> dict | None:
        for registro in reversed(self.leer()):
            if registro.get("traza_id") == traza_id:
                return registro
        return None


class Traza:
    """Traza de una consulta (Código 5). Las etapas usan los nombres del informe:
    ``guardrails_entrada``, ``cache``, ``contexto_malla``, ``enrutador``,
    ``contexto_rag``, ``gateway`` y ``guardrails_salida`` (más ``persistencia``)."""

    def __init__(self, tipo: str, perfil: str | None = None,
                 registro: RegistroTrazas | None = None, version_prompt: str | None = None,
                 version_corpus: int | None = None):
        self.registro = registro
        self._inicio = time.perf_counter()
        self._cerrada = False
        self.datos: dict = {
            "traza_id": uuid.uuid4().hex,
            "tipo": tipo,
            "perfil": perfil,
            "inicio": time.time(),
            "tiempos_ms": {},
            "cache": "ninguna",
            "ruta": None,
            "modelo": None,
            "uso_respaldo": False,
            "hallazgos": 0,
            "iteraciones_agente": 0,
            "guardrails": {"entrada": "aprobada", "salida": "aprobada", "activaciones": []},
            "llamadas": [],
            "recuperaciones": [],
            "version_prompt": version_prompt,
            "version_corpus": version_corpus,
            "estado": "abierta",
        }

    @property
    def traza_id(self) -> str:
        return self.datos["traza_id"]

    @contextmanager
    def etapa(self, nombre: str):
        """Mide el tiempo de la etapa incluso si lanza una excepción y deja una bitácora
        estructurada por capa (logger ``meshaudit.<capa>``, una línea JSON por etapa)."""
        inicio = time.perf_counter()
        error = None
        try:
            yield self
        except BaseException as exc:
            error = type(exc).__name__
            raise
        finally:
            ms = (time.perf_counter() - inicio) * 1000
            tiempos = self.datos["tiempos_ms"]
            tiempos[nombre] = round(tiempos.get(nombre, 0.0) + ms, 3)
            capa = CAPA_DE_ETAPA.get(nombre, "C2")
            logging.getLogger(f"meshaudit.{capa}").info(json.dumps(
                {"traza_id": self.traza_id, "tipo": self.datos["tipo"], "capa": capa,
                 "etapa": nombre, "ms": round(ms, 3), "error": error}, ensure_ascii=False))

    def anotar(self, **campos) -> None:
        if "archivo" in campos or "contenido" in campos:
            raise ValueError("Las trazas solo guardan el hash de la malla")
        self.datos.update(campos)

    def registrar_guardrail(self, guardrail: str) -> None:
        """Anota una activación (E1–E5, S1–S4) y actualiza el estado de entrada/salida."""
        g = self.datos["guardrails"]
        if guardrail not in g["activaciones"]:
            g["activaciones"].append(guardrail)
        if guardrail.startswith("S") and guardrail != "S4":
            g["salida"] = "corregida"
        if guardrail == "E3" and g["entrada"] == "aprobada":
            g["entrada"] = "enmascarada"

    def rechazar(self, guardrail: str, motivo: str) -> None:
        self.registrar_guardrail(guardrail)
        self.datos["guardrails"]["entrada"] = "rechazada"
        self.datos["guardrails"]["motivo"] = motivo

    @property
    def guardrails(self) -> dict:
        g = self.datos["guardrails"]
        return {**g, "activaciones": list(g["activaciones"])}

    def registrar_llamada(self, llamada: dict) -> None:
        self.datos["llamadas"].append(llamada)
        if llamada.get("ok"):
            self.datos["modelo"] = llamada.get("modelo")
            if llamada.get("uso_respaldo"):
                self.datos["uso_respaldo"] = True

    def registrar_recuperacion(self, consulta_id: str, top1: float, n: int) -> None:
        self.datos["recuperaciones"].append({"consulta": consulta_id, "top1": round(top1, 4),
                                             "fragmentos": n})

    def sumar_iteraciones(self, n: int) -> None:
        self.datos["iteraciones_agente"] += n

    def sumar(self, campo: str, n: int = 1) -> None:
        """Contadores para la evaluación (citas generadas, quitadas por S2, …)."""
        self.datos[campo] = self.datos.get(campo, 0) + n

    def cerrar(self, estado: str = "ok") -> dict:
        if self._cerrada:
            return self.datos
        self._cerrada = True
        self.datos["estado"] = estado if self.datos["estado"] == "abierta" else self.datos["estado"]
        self.datos["tiempo_total_ms"] = round((time.perf_counter() - self._inicio) * 1000, 3)
        if self.registro is not None:
            self.registro.escribir(self.datos)
        return self.datos
