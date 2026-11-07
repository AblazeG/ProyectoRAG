"""Enrutador (C6): elige la ruta y devuelve un alias, nunca el nombre de un modelo.

| Ruta       | Condición                                 | Alias      |
|------------|-------------------------------------------|------------|
| sin_modelo | sin hallazgos G ni M                      | (plantilla)|
| rapida     | 1 a 3 menores y ningún grave; preguntas   | rapido     |
| completa   | 4 o más G/M, o al menos un grave          | completo   |
| respaldo   | timeout o fallo tras reintentos           | el otro    |
"""
from __future__ import annotations

from dataclasses import dataclass

from servicio.dominio import Hallazgo

SIN_MODELO, RAPIDA, COMPLETA = "sin_modelo", "rapida", "completa"
ALIAS = {RAPIDA: "rapido", COMPLETA: "completo"}
RESPALDO = {"rapido": "completo", "completo": "rapido"}


@dataclass(frozen=True)
class Ruta:
    ruta: str
    alias: str | None
    graves: int = 0
    menores: int = 0


class Enrutador:
    def clasificar(self, hallazgos: list[Hallazgo] | None = None,
                   tipo: str = "auditoria") -> Ruta:
        """Tabla 10: decide por la salida del analizador determinista (ADR-04).

        Las preguntas de seguimiento siempre van a la ruta rápida.
        """
        if tipo == "pregunta":
            return Ruta(RAPIDA, ALIAS[RAPIDA])
        hallazgos = hallazgos or []
        graves = sum(h.gravedad == "grave" for h in hallazgos)
        menores = sum(h.gravedad == "menor" for h in hallazgos)  # los informativos no cuentan
        if graves + menores == 0:
            return Ruta(SIN_MODELO, None, graves, menores)
        if graves >= 1 or graves + menores >= 4:
            return Ruta(COMPLETA, ALIAS[COMPLETA], graves, menores)
        return Ruta(RAPIDA, ALIAS[RAPIDA], graves, menores)

    @staticmethod
    def alias_respaldo(alias: str) -> str:
        return RESPALDO[alias]
