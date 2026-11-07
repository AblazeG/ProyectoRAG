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
class DecisionRuta:
    ruta: str
    alias: str | None
    graves: int = 0
    menores: int = 0


class Enrutador:
    def ruta_auditoria(self, hallazgos: list[Hallazgo]) -> DecisionRuta:
        graves = sum(h.gravedad == "grave" for h in hallazgos)
        menores = sum(h.gravedad == "menor" for h in hallazgos)  # los informativos no cuentan
        if graves + menores == 0:
            return DecisionRuta(SIN_MODELO, None, graves, menores)
        if graves >= 1 or graves + menores >= 4:
            return DecisionRuta(COMPLETA, ALIAS[COMPLETA], graves, menores)
        return DecisionRuta(RAPIDA, ALIAS[RAPIDA], graves, menores)

    def ruta_pregunta(self) -> DecisionRuta:
        return DecisionRuta(RAPIDA, ALIAS[RAPIDA])

    @staticmethod
    def alias_respaldo(alias: str) -> str:
        return RESPALDO[alias]
