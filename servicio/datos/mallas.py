"""Lectura de mallas (C7). Es el único lugar que abre archivos de malla.

- ``LectorTrimesh`` carga con ``trimesh.load(..., process=False)`` (sin
  ``force="mesh"``, que pierde las normales declaradas) y entrega arreglos crudos
  en ``MallaCruda``; las escenas se combinan con la transformación de cada nodo.
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

from servicio.dominio import EntradaInvalida, MallaCruda, MallaDemasiadoCompleja


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
            linea = linea.split("#", 1)[0]  # comentario al final de la línea
            if linea.startswith("f ") or linea.startswith("f\t"):
                indices = linea.split()[1:]
                if len(indices) >= 3:      # trimesh descarta las «caras» de 1 o 2 índices
                    lados.append(len(indices))
    return lados


def probar_obj(ruta: Path, muestra: int = 1 << 20) -> bool:
    """Lectura de prueba de un OBJ: en el primer MB hay vértices y caras válidas."""
    with open(ruta, "rb") as archivo:
        cabeza = archivo.read(muestra)
        cortada = len(cabeza) == muestra and archivo.read(1) != b""
    if b"\x00" in cabeza:
        return False
    if cortada and b"\n" in cabeza:   # la última línea puede estar incompleta
        cabeza = cabeza[:cabeza.rfind(b"\n")]
    vertices = caras = 0
    for linea in cabeza.splitlines():
        partes = linea.split()
        if not partes:
            continue
        if partes[0] == b"v" and len(partes) >= 4:
            try:
                [float(x) for x in partes[1:4]]
            except ValueError:
                return False
            vertices += 1
        elif partes[0] == b"f" and len(partes) >= 4:
            caras += 1
    return vertices >= 3 and (caras >= 1 or cortada)


def probar_stl(ruta: Path) -> bool:
    """Lectura de prueba de un STL: binario con tamaño 84 + 50·n, o ASCII con «solid … facet»."""
    tamano = Path(ruta).stat().st_size
    with open(ruta, "rb") as archivo:
        cabeza = archivo.read(1 << 16)
    texto = cabeza.removeprefix(b"\xef\xbb\xbf").lstrip().lower()
    if texto.startswith(b"solid") and (b"facet" in texto or b"endsolid" in texto
                                       or len(cabeza) == 1 << 16):
        return True
    if tamano < 84:
        return False
    n = int.from_bytes(cabeza[80:84], "little")
    return n > 0 and tamano == 84 + 50 * n


class LectorTrimesh:
    """Puerto ``LectorMalla``. Rechaza mallas de más de 2 000 000 de caras (HTTP 422)."""

    def __init__(self, max_caras: int = 2_000_000):
        self.max_caras = max_caras

    def probar(self, ruta: Path) -> bool:
        """Lectura de prueba de E1 para formatos sin firma fiable (OBJ y STL).

        Es ligera a propósito: la carga completa ocurre en ``analizar_malla``
        solo si la caché exacta falla (meta de latencia de la tabla 5)."""
        ruta = Path(ruta)
        formato = ruta.suffix.lower()
        try:
            if formato == ".obj":
                return probar_obj(ruta)
            if formato == ".stl":
                return probar_stl(ruta)
        except OSError:
            return False
        return True

    def leer(self, ruta: Path) -> MallaCruda:
        """Carga sin procesar. No usa ``force="mesh"`` porque esa conversión pierde
        las normales declaradas en el archivo y V10 confundiría las aristas duras
        con vértices duplicados; las escenas se combinan aplicando su transformación."""
        ruta = Path(ruta)
        formato = ruta.suffix.lower().lstrip(".")
        try:
            cargado = trimesh.load(str(ruta), process=False)
            partes = _partes(cargado)
        except EntradaInvalida:
            raise
        except Exception as exc:  # noqa: BLE001
            raise EntradaInvalida("No se pudo leer la malla.") from exc
        partes = [p for p in partes if len(p[0].faces)]
        if not partes:
            raise EntradaInvalida("El archivo no contiene una malla con caras.")
        if sum(len(m.faces) for m, _ in partes) > self.max_caras:
            raise MallaDemasiadoCompleja()

        vertices, caras, uvs, normales, desplazamiento = [], [], [], [], 0
        for malla, transformacion in partes:
            v = np.asarray(malla.vertices, dtype=float)
            if transformacion is not None:
                v = trimesh.transformations.transform_points(v, transformacion)
            vertices.append(v)
            caras.append(np.asarray(malla.faces, dtype=np.int64) + desplazamiento)
            desplazamiento += len(v)
            uvs.append(_uv(malla))
            n = _normales(malla)
            if n is not None and transformacion is not None:
                n = n @ np.asarray(transformacion)[:3, :3].T
                n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            normales.append(n)

        return MallaCruda(
            vertices=np.vstack(vertices),
            caras=np.vstack(caras),
            uv=None if any(u is None for u in uvs) else np.vstack(uvs),
            normales=None if any(n is None for n in normales) else np.vstack(normales),
            lados_por_cara=leer_lados_obj(ruta) if formato == "obj" else None,
            formato=formato,
            tamano_bytes=ruta.stat().st_size,
        )


def _partes(cargado) -> list[tuple]:
    """(malla, transformación) de cada geometría; una escena aporta sus nodos."""
    if isinstance(cargado, trimesh.Trimesh):
        return [(cargado, None)]
    if isinstance(cargado, trimesh.Scene):
        partes = []
        for nodo in cargado.graph.nodes_geometry:
            transformacion, nombre = cargado.graph[nodo]
            geometria = cargado.geometry.get(nombre)
            if isinstance(geometria, trimesh.Trimesh):
                partes.append((geometria, transformacion))
        return partes
    raise EntradaInvalida("El archivo no contiene una malla con caras.")


def _uv(malla) -> np.ndarray | None:
    visual = getattr(malla, "visual", None)
    if visual is not None and getattr(visual, "kind", None) == "texture":
        uv = getattr(visual, "uv", None)
        if uv is not None and len(uv) == len(malla.vertices):
            return np.asarray(uv, dtype=float)
    return None


def _normales(malla) -> np.ndarray | None:
    """Normales por vértice solo si el archivo las declara (están en la caché de trimesh)."""
    cache = getattr(malla, "_cache", None)
    guardadas = cache.cache.get("vertex_normals") if cache is not None else None
    if guardadas is not None and len(guardadas) == len(malla.vertices):
        return np.asarray(guardadas, dtype=float).copy()
    return None


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
