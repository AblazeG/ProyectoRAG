"""Segundo adaptador vectorial, en memoria (C7).

Existe para la meta de modificabilidad: sustituir ChromaDB por este adaptador
solo toca ``datos/`` y ``composicion.py``. Usa numpy y similitud coseno exacta.
"""
from __future__ import annotations

import threading

import numpy as np

from servicio.dominio import ErrorDatos, Fragmento, Recuperado


class AlmacenMemoria:
    """Puerto ``AlmacenVectorial`` no persistente."""

    nombre = "memoria"

    def __init__(self):
        self._fragmentos: dict[str, Fragmento] = {}
        self._vectores: dict[str, np.ndarray] = {}
        self._candado = threading.Lock()

    def agregar(self, fragmentos: list[Fragmento], vectores: list[list[float]]) -> None:
        with self._candado:
            for f, v in zip(fragmentos, vectores):
                arr = np.asarray(v, dtype=float)
                norma = np.linalg.norm(arr)
                self._fragmentos[f.id] = f
                self._vectores[f.id] = arr / norma if norma else arr

    @staticmethod
    def _cumple(f: Fragmento, filtro: dict | None) -> bool:
        for clave, valor in (filtro or {}).items():
            if clave == "perfil":
                if valor not in f.perfiles:
                    return False
            elif getattr(f, clave, None) != valor:
                return False
        return True

    def buscar(self, vector: list[float], k: int,
               filtro: dict | None = None) -> list[Recuperado]:
        consulta = np.asarray(vector, dtype=float)
        norma = np.linalg.norm(consulta)
        if norma:
            consulta = consulta / norma
        with self._candado:
            candidatos = [(id_, f) for id_, f in self._fragmentos.items()
                          if self._cumple(f, filtro)]
            try:
                puntajes = [(float(self._vectores[id_] @ consulta), f) for id_, f in candidatos]
            except ValueError as exc:   # dimensión distinta: otro modelo de embeddings
                raise ErrorDatos("El vector de consulta no tiene la dimensión del índice.") from exc
        puntajes.sort(key=lambda par: (-par[0], par[1].id))
        return [Recuperado(f, p) for p, f in puntajes[:k]]

    def eliminar_documento(self, doc_id: str) -> int:
        with self._candado:
            ids = [i for i, f in self._fragmentos.items() if f.doc_id == doc_id]
            for i in ids:
                del self._fragmentos[i]
                del self._vectores[i]
        return len(ids)

    def contar(self) -> int:
        return len(self._fragmentos)

    def vaciar(self) -> None:
        with self._candado:
            self._fragmentos.clear()
            self._vectores.clear()

    def comprobar(self) -> dict:
        return {"ok": True, "fragmentos": self.contar(), "tipo": "memoria"}
