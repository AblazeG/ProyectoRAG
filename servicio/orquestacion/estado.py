"""Estado del servicio (C2): salud, configuración activa y perfiles.

La API (C1) solo conoce a la orquestación (figura 3); este servicio le da
``GET /health``, ``GET /configuracion`` y ``GET /perfiles`` sin que C1 llegue a
C5, C6 ni C7. Las sondas, el catálogo y la configuración los inyecta la
raíz de composición.
"""
from __future__ import annotations

from typing import Callable


class ServicioEstado:
    def __init__(self, sondas: list, perfiles: Callable[[], dict],
                 configuracion: Callable[[], dict], proveedor: str):
        self.sondas = sondas
        self._perfiles = perfiles
        self._configuracion = configuracion
        self.proveedor = proveedor

    def salud(self) -> tuple[bool, dict]:
        """Estado de Ollama, ChromaDB, SQLite y modelos."""
        componentes = {}
        for sonda in self.sondas:
            try:
                componentes[sonda.nombre] = sonda.comprobar()
            except Exception as exc:  # noqa: BLE001 - una sonda rota es un componente caído
                componentes[sonda.nombre] = {"ok": False, "detalle": type(exc).__name__}
        ok = all(c.get("ok") for c in componentes.values())
        return ok, {"estado": "ok" if ok else "degradado", "proveedor": self.proveedor,
                    "componentes": componentes}

    def configuracion(self) -> dict:
        return self._configuracion()

    def perfiles(self) -> dict:
        return self._perfiles()
