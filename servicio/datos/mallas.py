"""Lectura de mallas (C7). Es el único lugar que abre archivos de malla.

- ``LectorTrimesh`` carga con ``trimesh.load(..., process=False, force="mesh")``
  y entrega arreglos crudos en ``MallaCruda``.
- ``leer_lados_obj`` es el lector propio de líneas ``f`` del OBJ: cuenta los
  lados de cada cara antes de que trimesh triangule (V1 y V2).
- ``AlmacenMallasTemporal`` guarda las mallas subidas en ``data/mallas/`` y
  las borra al terminar la auditoría.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import trimesh

from servicio.dominio import EntradaInvalida, MallaCruda


def leer_lados_obj(ruta: Path) -> list[int]:
    """Número de vértices de cada línea ``f`` del OBJ (sin triangular)."""
    lados: list[int] = []
    with open(ruta, "r", encoding="utf-8", errors="replace") as archivo:
        continuacion = ""
        for linea in archivo:
            linea = continuacion + linea.strip()
            continuacion = ""
            if linea.endswith("\\"):  # continuación de línea del formato OBJ
                continuacion = linea[:-1] + " "
                continue
            if linea.startswith("f ") or linea.startswith("f\t"):
                indices = linea.split()[1:]
                if indices:
                    lados.append(len(indices))
    return lados


class LectorTrimesh:
    """Puerto ``LectorMalla``."""

    def leer(self, ruta: Path) -> MallaCruda:
        ruta = Path(ruta)
        formato = ruta.suffix.lower().lstrip(".")
        try:
            malla = trimesh.load(str(ruta), process=False, force="mesh")
        except Exception as exc:  # noqa: BLE001
            raise EntradaInvalida("No se pudo leer la malla.") from exc
        if not isinstance(malla, trimesh.Trimesh) or len(malla.faces) == 0:
            raise EntradaInvalida("El archivo no contiene una malla con caras.")

        uv = None
        visual = getattr(malla, "visual", None)
        if visual is not None and getattr(visual, "kind", None) == "texture":
            uv_crudo = getattr(visual, "uv", None)
            if uv_crudo is not None and len(uv_crudo) == len(malla.vertices):
                uv = np.asarray(uv_crudo, dtype=float)

        normales = None
        cache = getattr(malla, "_cache", None)
        guardadas = cache.cache.get("vertex_normals") if cache is not None else None
        if guardadas is not None and len(guardadas) == len(malla.vertices):
            normales = np.asarray(guardadas, dtype=float)

        return MallaCruda(
            vertices=np.asarray(malla.vertices, dtype=float),
            caras=np.asarray(malla.faces, dtype=np.int64),
            uv=uv,
            normales=normales,
            lados_por_cara=leer_lados_obj(ruta) if formato == "obj" else None,
            formato=formato,
            tamano_bytes=ruta.stat().st_size,
        )


class AlmacenMallasTemporal:
    """Puerto ``AlmacenArchivosTemporales`` sobre ``data/mallas/``."""

    def __init__(self, directorio: Path | str):
        self.directorio = Path(directorio)
        self.directorio.mkdir(parents=True, exist_ok=True)

    def guardar(self, contenido: bytes, extension: str) -> Path:
        ruta = self.directorio / f"{uuid.uuid4().hex}{extension.lower()}"
        ruta.write_bytes(contenido)
        return ruta

    def borrar(self, ruta: Path) -> None:
        Path(ruta).unlink(missing_ok=True)
