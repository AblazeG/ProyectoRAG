"""Gateway de modelos (C6): tiempo límite por ruta, reintentos y respaldo.

- 45 s en la ruta rápida y 90 s en la completa.
- Hasta 2 reintentos con espera de 1 y 2 s, solo ante error de conexión o 5xx.
- Ni un timeout ni un 404 (modelo inexistente) se reintentan: van al respaldo.
- Si el respaldo también falla: ``ModeloNoDisponible`` (la API responde 503).
Los embeddings no pasan por aquí: C3, C4 y C5 usan el puerto directamente.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from servicio.dominio import (
    ErrorConexion,
    ErrorModelo,
    ErrorRespuestaModelo,
    ErrorServidorModelo,
    Generacion,
    ModeloChat,
    ModeloNoDisponible,
)
from servicio.modelos.enrutador import RESPALDO

REINTENTABLES = (ErrorConexion, ErrorServidorModelo)


@dataclass
class RegistroLlamada:
    alias: str
    modelo: str
    ruta: str | None
    tokens_entrada: int
    tokens_salida: int
    duracion_ms: float
    uso_respaldo: bool
    ok: bool
    error: str | None = None
    tokens_por_s: float | None = None


class Gateway:
    def __init__(self, modelos: dict[str, ModeloChat], tiempos_limite_s: dict[str, float],
                 reintentos: int = 2, esperas_s: list[float] | None = None,
                 dormir: Callable[[float], None] = time.sleep):
        self.modelos = modelos
        self.tiempos_limite_s = tiempos_limite_s
        self.reintentos = reintentos
        self.esperas_s = esperas_s or [1.0, 2.0]
        self.dormir = dormir
        self.registro: list[RegistroLlamada] = []

    def nombre_modelo(self, alias: str) -> str:
        return self.modelos[alias].nombre

    def _con_reintentos(self, alias: str, mensajes: list[dict], esquema: dict | None,
                        ruta: str | None, respaldo: bool, traza, contador: list[int]) -> Generacion:
        """Llama al modelo del alias. Reintenta hasta 2 veces (esperas de 1 y 2 s) solo
        ante error de conexión o 5xx; timeout, 404 u otro error van directo al respaldo.
        Cada intento queda registrado (sin contar las esperas) y suma en ``contador``."""
        modelo = self.modelos[alias]
        intento = 0
        while True:
            intento += 1
            contador[0] += 1
            inicio = time.perf_counter()
            try:
                generacion = modelo.generar(mensajes, esquema, self.tiempos_limite_s[alias])
            except REINTENTABLES as exc:
                self._registrar(alias, ruta, None, inicio, respaldo, traza, type(exc).__name__)
                if intento > self.reintentos:
                    raise
                self.dormir(self.esperas_s[min(intento - 1, len(self.esperas_s) - 1)])
                continue
            except ErrorModelo as exc:
                self._registrar(alias, ruta, None, inicio, respaldo, traza, type(exc).__name__)
                raise
            except Exception as exc:  # noqa: BLE001 - un adaptador defectuoso no tumba el flujo
                self._registrar(alias, ruta, None, inicio, respaldo, traza, type(exc).__name__)
                raise ErrorRespuestaModelo(f"Error inesperado del adaptador: {type(exc).__name__}") from exc
            self._registrar(alias, ruta, generacion, inicio, respaldo, traza)
            return generacion

    def generar(self, alias: str, mensajes: list[dict], esquema: dict | None = None,
                ruta: str | None = None, traza=None,
                permitir_respaldo: bool = True) -> Generacion:
        """Interfaz única hacia los modelos: ``generar(alias, mensajes, esquema)``.

        La ``Generacion`` devuelta indica el alias que respondió, si se usó el
        respaldo y cuántas llamadas hubo en total (``intentos``).
        """
        candidatos = [alias] + ([RESPALDO[alias]] if permitir_respaldo else [])
        contador = [0]
        for posicion, actual in enumerate(candidatos):
            try:
                generacion = self._con_reintentos(actual, mensajes, esquema, ruta, posicion > 0,
                                                  traza, contador)
            except ErrorModelo:
                continue
            generacion.alias = actual
            generacion.uso_respaldo = posicion > 0
            generacion.intentos = contador[0]
            return generacion
        raise ModeloNoDisponible("Ni la ruta principal ni el respaldo respondieron.")

    def _registrar(self, alias, ruta, generacion, inicio, respaldo, traza, error=None):
        registro = RegistroLlamada(
            alias=alias, modelo=self.modelos[alias].nombre, ruta=ruta,
            tokens_entrada=generacion.tokens_entrada if generacion else 0,
            tokens_salida=generacion.tokens_salida if generacion else 0,
            duracion_ms=round((time.perf_counter() - inicio) * 1000, 2),
            uso_respaldo=respaldo, ok=generacion is not None, error=error,
            tokens_por_s=generacion.tokens_por_s if generacion else None)
        self.registro.append(registro)
        if len(self.registro) > 1000:
            del self.registro[:500]
        if traza is not None:
            traza.registrar_llamada(registro.__dict__)
