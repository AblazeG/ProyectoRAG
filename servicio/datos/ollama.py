"""Adaptadores de Ollama (C7): chat, embeddings y sonda de salud.

Solo este módulo conoce la API HTTP de Ollama. Los errores de red se traducen
a errores del dominio para que C6 decida si reintenta o usa el respaldo.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from servicio.dominio import (
    ErrorConexion,
    ErrorRespuestaModelo,
    ErrorServidorModelo,
    ErrorTiempoLimite,
    Generacion,
    ModeloInexistente,
)

URL_POR_DEFECTO = "http://127.0.0.1:11434"
OPCIONES_POR_DEFECTO = {"temperature": 0.1, "seed": 42, "num_ctx": 8192}


def _nivel_razonamiento(modelo: str) -> bool | str | None:
    """«think»: desactivado en gemma4 y qwen3, nivel bajo en gpt-oss."""
    nombre = modelo.lower()
    if nombre.startswith(("gemma4", "qwen3")):
        return False
    if nombre.startswith("gpt-oss"):
        return "low"
    return None


def _traducir_error(exc: Exception, modelo: str) -> Exception:
    if isinstance(exc, httpx.TimeoutException):
        return ErrorTiempoLimite(f"Tiempo límite agotado con {modelo}")
    if isinstance(exc, httpx.HTTPStatusError):
        codigo = exc.response.status_code
        if codigo == 404:
            return ModeloInexistente(f"El modelo {modelo} no existe en Ollama")
        if codigo >= 500:
            return ErrorServidorModelo(f"Ollama respondió {codigo}")
        return ErrorRespuestaModelo(f"Ollama respondió {codigo}")
    if isinstance(exc, (httpx.TransportError, OSError)):
        return ErrorConexion(f"No se pudo conectar con Ollama: {type(exc).__name__}")
    return ErrorRespuestaModelo(f"Respuesta inválida de Ollama: {type(exc).__name__}")


class ChatOllama:
    """Puerto ``ModeloChat`` sobre ``POST /api/chat``."""

    def __init__(self, nombre: str, url: str = URL_POR_DEFECTO,
                 opciones: dict | None = None, keep_alive: str = "30m",
                 cliente: httpx.Client | None = None):
        self.nombre = nombre
        self.url = url.rstrip("/")
        self.opciones = {**OPCIONES_POR_DEFECTO, **(opciones or {})}
        self.keep_alive = keep_alive
        self._cliente = cliente or httpx.Client()

    def cuerpo(self, mensajes: list[dict], esquema: dict | None) -> dict:
        cuerpo: dict[str, Any] = {
            "model": self.nombre,
            "messages": mensajes,
            "stream": False,
            "options": dict(self.opciones),
            "keep_alive": self.keep_alive,
        }
        if esquema is not None:
            cuerpo["format"] = esquema
        think = _nivel_razonamiento(self.nombre)
        if think is not None:
            cuerpo["think"] = think
        return cuerpo

    def generar(self, mensajes: list[dict], esquema: dict | None,
                tiempo_limite_s: float) -> Generacion:
        inicio = time.perf_counter()
        try:
            respuesta = self._cliente.post(
                f"{self.url}/api/chat", json=self.cuerpo(mensajes, esquema),
                timeout=httpx.Timeout(tiempo_limite_s, connect=5.0))
            respuesta.raise_for_status()
            datos = respuesta.json()
            texto = datos["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - se traduce al dominio
            raise _traducir_error(exc, self.nombre) from exc
        duracion = datos.get("total_duration")
        eval_ns = datos.get("eval_duration")
        tokens_salida = int(datos.get("eval_count") or 0)
        return Generacion(
            texto=texto,
            modelo=datos.get("model", self.nombre),
            tokens_entrada=int(datos.get("prompt_eval_count") or 0),
            tokens_salida=tokens_salida,
            duracion_ms=(duracion / 1e6) if duracion else
            (time.perf_counter() - inicio) * 1000,
            tokens_por_s=(tokens_salida / eval_ns * 1e9) if eval_ns else None,
        )


class EmbeddingsOllama:
    """Puerto ``ModeloEmbeddings`` sobre ``POST /api/embed``.

    Con nomic-embed-text se anteponen los prefijos de tarea
    ``search_document:`` y ``search_query:``.
    """

    PREFIJOS_NOMIC = {"documento": "search_document: ", "consulta": "search_query: "}

    def __init__(self, nombre: str, url: str = URL_POR_DEFECTO,
                 tiempo_limite_s: float = 30.0, keep_alive: str = "30m",
                 cliente: httpx.Client | None = None, lote: int = 32):
        self.nombre = nombre
        self.url = url.rstrip("/")
        self.tiempo_limite_s = tiempo_limite_s
        self.keep_alive = keep_alive
        self.lote = lote
        self._cliente = cliente or httpx.Client()

    def _prefijar(self, textos: list[str], tipo: str) -> list[str]:
        if tipo not in ("documento", "consulta"):
            raise ValueError("tipo debe ser 'documento' o 'consulta'")
        if self.nombre.startswith("nomic-embed-text"):
            prefijo = self.PREFIJOS_NOMIC[tipo]
            return [prefijo + t for t in textos]
        return list(textos)

    def vectorizar(self, textos: list[str], tipo: str) -> list[list[float]]:
        entradas = self._prefijar(textos, tipo)
        vectores: list[list[float]] = []
        for i in range(0, len(entradas), self.lote):
            try:
                respuesta = self._cliente.post(
                    f"{self.url}/api/embed",
                    json={"model": self.nombre, "input": entradas[i:i + self.lote],
                          "keep_alive": self.keep_alive},
                    timeout=httpx.Timeout(self.tiempo_limite_s, connect=5.0))
                respuesta.raise_for_status()
                vectores.extend(respuesta.json()["embeddings"])
            except Exception as exc:  # noqa: BLE001
                raise _traducir_error(exc, self.nombre) from exc
        return vectores


class SondaOllama:
    """Sonda de salud: Ollama responde y tiene los modelos configurados."""

    nombre = "ollama"

    def __init__(self, url: str, modelos: list[str],
                 cliente: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.modelos = modelos
        self._cliente = cliente or httpx.Client()

    def comprobar(self) -> dict:
        try:
            respuesta = self._cliente.get(f"{self.url}/api/tags", timeout=3.0)
            respuesta.raise_for_status()
            instalados = {m["name"] for m in respuesta.json().get("models", [])}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "detalle": f"Ollama no responde ({type(exc).__name__})",
                    "modelos": {m: False for m in self.modelos}}

        def presente(modelo: str) -> bool:
            return modelo in instalados or f"{modelo}:latest" in instalados

        estado = {m: presente(m) for m in self.modelos}
        return {"ok": all(estado.values()), "modelos": estado}
