"""Cachés exactas (C4) sobre SQLite: informes, hallazgos y preguntas.

Las claves se calculan sobre texto ya enmascarado e incluyen todas las
versiones que cambian el resultado. Solo se guardan respuestas que pasaron
S1–S3 y que no son rechazos (``validada=True``). Caducan a los 7 días.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from typing import Callable

from servicio.dominio import AlmacenClaveValor

HORAS = 3600.0


def sha256(datos: bytes | str) -> str:
    if isinstance(datos, str):
        datos = datos.encode("utf-8")
    return hashlib.sha256(datos).hexdigest()


def normalizar_pregunta(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto).lower().strip()
    texto = re.sub(r"[¿?¡!.,;:]+", " ", texto)
    return " ".join(texto.split())


def _clave(*partes) -> str:
    return sha256(json.dumps(partes, sort_keys=True, ensure_ascii=False))


class CacheExacta:
    ESPACIOS = ("informe", "hallazgo", "pregunta")

    def __init__(self, almacen: AlmacenClaveValor, expiracion_h: float = 168,
                 activa: bool = True, reloj: Callable[[], float] = time.time):
        self.almacen = almacen
        self.expiracion_s = expiracion_h * HORAS
        self.activa = activa
        self.reloj = reloj

    # -- claves ------------------------------------------------------------
    @staticmethod
    def clave_informe(archivo_sha: str, perfil: str, notas_enmascaradas: str,
                      versiones: dict) -> str:
        """SHA-256 del archivo + perfil + hash de notas + versiones de perfiles,
        analizador, corpus, prompt y modelos."""
        return _clave("informe", archivo_sha, perfil, sha256(notas_enmascaradas or ""),
                      versiones["perfiles"], versiones["analizador"], versiones["corpus"],
                      versiones["prompt"], versiones["modelos"])

    @staticmethod
    def clave_hallazgo(verificacion: str, perfil: str, gravedad: str, version_corpus: int,
                       version_prompt: str, modelo: str) -> str:
        return _clave("hallazgo", verificacion, perfil, gravedad, version_corpus,
                      version_prompt, modelo)

    @staticmethod
    def clave_pregunta(archivo_sha: str, perfil: str, pregunta_enmascarada: str,
                       versiones: dict) -> str:
        return _clave("pregunta", archivo_sha, perfil, normalizar_pregunta(pregunta_enmascarada),
                      versiones["corpus"], versiones["prompt"], versiones["modelos"])

    # -- operaciones -------------------------------------------------------
    def obtener(self, espacio: str, clave: str) -> dict | None:
        if not self.activa:
            return None
        return self.almacen.obtener(espacio, clave, self.reloj())

    def guardar(self, espacio: str, clave: str, valor: dict, version_corpus: int,
                validada: bool) -> bool:
        if not (self.activa and validada):
            return False
        ahora = self.reloj()
        self.almacen.guardar(espacio, clave, valor, version_corpus,
                             ahora + self.expiracion_s, ahora)
        return True

    def obtener_informe(self, clave: str) -> dict | None:
        return self.obtener("informe", clave)

    def guardar_informe(self, clave: str, informe: dict, version_corpus: int,
                        validada: bool) -> bool:
        return self.guardar("informe", clave, informe, version_corpus, validada)

    def obtener_hallazgo(self, clave: str) -> dict | None:
        return self.obtener("hallazgo", clave)

    def guardar_hallazgo(self, clave: str, explicacion: dict, version_corpus: int,
                         validada: bool) -> bool:
        """Guarda la explicación sin mediciones (explicación, pasos y fuente)."""
        sin_mediciones = {k: explicacion.get(k) for k in ("explicacion", "correccion", "fuente")}
        return self.guardar("hallazgo", clave, sin_mediciones, version_corpus, validada)

    def obtener_pregunta(self, clave: str) -> dict | None:
        return self.obtener("pregunta", clave)

    def guardar_pregunta(self, clave: str, respuesta: dict, version_corpus: int,
                         validada: bool) -> bool:
        return self.guardar("pregunta", clave, respuesta, version_corpus, validada)

    def purgar(self, version_corpus: int) -> int:
        """Borra lo guardado con versiones anteriores del corpus."""
        return self.almacen.purgar(version_corpus)

    def eliminar_expirados(self) -> int:
        return self.almacen.eliminar_expirados(self.reloj())
