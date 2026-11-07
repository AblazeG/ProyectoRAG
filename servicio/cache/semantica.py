"""Caché semántica (C4), solo para preguntas de seguimiento.

Compara el embedding de la pregunta (enmascarada) solo con preguntas del mismo
archivo y perfil; acierta con coseno ≥ 0.92 y misma ``version_corpus``.
Caduca a las 24 horas.
"""
from __future__ import annotations

import time
from typing import Callable

import numpy as np

from servicio.dominio import AlmacenClaveValor, ModeloEmbeddings

HORAS = 3600.0


class CacheSemantica:
    def __init__(self, almacen: AlmacenClaveValor, embeddings: ModeloEmbeddings,
                 umbral: float = 0.92, expiracion_h: float = 24, activa: bool = True,
                 reloj: Callable[[], float] = time.time):
        self.almacen = almacen
        self.embeddings = embeddings
        self.umbral = umbral
        self.expiracion_s = expiracion_h * HORAS
        self.activa = activa
        self.reloj = reloj

    def grupo(self, archivo_sha: str, perfil: str, version: str = "") -> str:
        """Mismo archivo y perfil, y además mismo modelo de embeddings y misma versión
        de prompt, modelos, perfiles y analizador (``version``): un cambio de modelo
        nunca sirve respuestas ni compara vectores del anterior."""
        return f"{archivo_sha}|{perfil}|{self.embeddings.nombre}|{version}"

    def _vector(self, pregunta: str) -> np.ndarray:
        v = np.asarray(self.embeddings.vectorizar([pregunta], "consulta")[0], dtype=float)
        n = np.linalg.norm(v)
        return v / n if n else v

    def buscar_similar(self, pregunta: str, archivo_sha: str, perfil: str,
                       version_corpus: int, version: str = "") -> tuple[dict, float] | None:
        if not self.activa:
            return None
        entradas = [e for e in self.almacen.listar_semantica(self.grupo(archivo_sha, perfil, version),
                                                             self.reloj())
                    if e["version_corpus"] == version_corpus]
        if not entradas:
            return None
        consulta = self._vector(pregunta)
        mejor, similitud = None, -1.0
        for entrada in entradas:
            v = np.asarray(entrada["vector"], dtype=float)
            if v.shape != consulta.shape:      # vector de otro modelo: no comparable
                continue
            s = float(consulta @ (v / (np.linalg.norm(v) or 1.0)))
            if s > similitud:
                mejor, similitud = entrada["valor"], s
        return (mejor, similitud) if similitud >= self.umbral else None

    def guardar(self, pregunta: str, archivo_sha: str, perfil: str, valor: dict,
                version_corpus: int, validada: bool, version: str = "") -> bool:
        if not (self.activa and validada):
            return False
        ahora = self.reloj()
        self.almacen.guardar_semantica(self.grupo(archivo_sha, perfil, version),
                                       self._vector(pregunta).tolist(), valor, version_corpus,
                                       ahora + self.expiracion_s, ahora)
        return True

    def purgar(self, version_corpus: int) -> int:
        return self.almacen.purgar(version_corpus)
