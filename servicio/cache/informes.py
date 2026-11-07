"""Archivo de informes (C4), fuera de la caché.

Los informes generados se guardan en su propio repositorio: purgar o expirar la
caché nunca rompe ``GET /auditorias/{id}``, la exportación a Markdown ni las
preguntas de seguimiento (sección 7.3). En la figura 7, «guardar informe y
hallazgos» va a la línea de vida de C4; C2 no toca el repositorio de C7.
"""
from __future__ import annotations

from servicio.dominio import RepositorioInformes


class ArchivoInformes:
    def __init__(self, repositorio: RepositorioInformes):
        self.repositorio = repositorio

    def guardar(self, informe: dict, archivo_sha: str) -> None:
        self.repositorio.guardar(informe, archivo_sha)

    def obtener(self, auditoria_id: str) -> dict | None:
        return self.repositorio.obtener(auditoria_id)

    def obtener_por_traza(self, traza_id: str) -> dict | None:
        return self.repositorio.obtener_por_traza(traza_id)
