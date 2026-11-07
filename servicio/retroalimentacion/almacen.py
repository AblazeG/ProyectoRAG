"""Retroalimentación (T2): útil / no útil y comentario, por informe u hallazgo.

El comentario pasa por E3 (se enmascaran datos personales) antes de guardarse.
La composición inyecta el enmascarador de C3 y la búsqueda de informes, así
esta capa abierta no depende de ninguna otra.
"""
from __future__ import annotations

from typing import Callable

from servicio.dominio import NoEncontrado, RepositorioRetroalimentacion


class AlmacenRetroalimentacion:
    def __init__(self, repositorio: RepositorioRetroalimentacion,
                 enmascarar: Callable[[str], tuple[str, int]],
                 buscar_informe: Callable[[str], dict | None]):
        self.repositorio = repositorio
        self.enmascarar = enmascarar
        self.buscar_informe = buscar_informe

    def guardar(self, traza_id: str, util: bool, comentario: str | None = None,
                hallazgo_id: str | None = None) -> dict:
        informe = self.buscar_informe(traza_id)
        if informe is None:
            raise NoEncontrado("No existe un informe con esa traza.")
        if hallazgo_id and hallazgo_id not in {h["id"] for h in informe.get("hallazgos", [])}:
            raise NoEncontrado("El hallazgo no pertenece a ese informe.")
        enmascarado, n = self.enmascarar(comentario or "")
        registro = {"traza_id": traza_id, "auditoria_id": informe.get("auditoria_id"),
                    "hallazgo_id": hallazgo_id, "util": bool(util),
                    "comentario": enmascarado or None, "datos_personales_enmascarados": n}
        self.repositorio.guardar(registro)
        return registro

    def resumen(self) -> dict:
        return self.repositorio.resumen()
