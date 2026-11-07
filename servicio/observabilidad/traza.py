"""Trazas (T1). Cada operación abre una traza, mide etapas y al cerrar escribe
una línea JSON en ``data/trazas.jsonl``. Nunca se guarda el contenido de la
malla, solo su hash."""
from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


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
            "hallazgos": {},
            "iteraciones_agente": 0,
            "guardrails": [],
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
        """Mide el tiempo de la etapa incluso si lanza una excepción."""
        inicio = time.perf_counter()
        try:
            yield self
        finally:
            ms = (time.perf_counter() - inicio) * 1000
            tiempos = self.datos["tiempos_ms"]
            tiempos[nombre] = round(tiempos.get(nombre, 0.0) + ms, 3)

    def anotar(self, **campos) -> None:
        if "archivo" in campos or "contenido" in campos:
            raise ValueError("Las trazas solo guardan el hash de la malla")
        self.datos.update(campos)

    def registrar_guardrail(self, guardrail: str) -> None:
        self.datos["guardrails"].append(guardrail)

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

    def cerrar(self, estado: str = "ok") -> dict:
        if self._cerrada:
            return self.datos
        self._cerrada = True
        self.datos["estado"] = estado if self.datos["estado"] == "abierta" else self.datos["estado"]
        self.datos["tiempo_total_ms"] = round((time.perf_counter() - self._inicio) * 1000, 3)
        if self.registro is not None:
            self.registro.escribir(self.datos)
        return self.datos
