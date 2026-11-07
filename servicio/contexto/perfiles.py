"""Perfiles de destino y sus reglas (C5), leídos de ``config/perfiles.yaml``."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from servicio.dominio import GRAVEDADES, PERFILES, EntradaInvalida

VERIFICACIONES_VALIDAS = {f"V{i}" for i in range(1, 12)}
UNIDADES = {"m": 1.0, "mm": 1000.0}  # factor desde metros


@dataclass
class Regla:
    verificacion: str
    gravedad: str                 # "grave" | "menor" | "informativo"
    parametros: dict
    norma: dict | None = None     # {"documento": ..., "seccion": ...}


@dataclass
class Perfil:
    clave: str
    nombre: str
    unidad: str
    reglas: dict[str, Regla] = field(default_factory=dict)


@dataclass
class CatalogoPerfiles:
    version: str
    perfiles: dict[str, Perfil]

    def obtener(self, clave: str) -> Perfil:
        if clave not in self.perfiles:
            raise EntradaInvalida(f"Perfil desconocido. Usa uno de: {', '.join(self.perfiles)}")
        return self.perfiles[clave]

    def como_dict(self) -> dict:
        return {
            "version": self.version,
            "perfiles": {
                c: {"nombre": p.nombre, "unidad": p.unidad,
                    "reglas": {v: {"gravedad": r.gravedad, **r.parametros, "norma": r.norma}
                               for v, r in p.reglas.items()}}
                for c, p in self.perfiles.items()},
        }


def cargar_perfiles(ruta: Path | str) -> CatalogoPerfiles:
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    perfiles: dict[str, Perfil] = {}
    for clave, crudo in datos["perfiles"].items():
        if clave not in PERFILES:
            raise ValueError(f"Perfil no previsto en el dominio: {clave}")
        if crudo["unidad"] not in UNIDADES:
            raise ValueError(f"Unidad no soportada: {crudo['unidad']}")
        reglas = {}
        for verificacion, regla in (crudo.get("reglas") or {}).items():
            if verificacion not in VERIFICACIONES_VALIDAS:
                raise ValueError(f"Verificación desconocida: {verificacion}")
            regla = dict(regla)
            gravedad = GRAVEDADES[regla.pop("gravedad")]
            norma = regla.pop("norma", None)
            reglas[verificacion] = Regla(verificacion, gravedad, regla, norma)
        perfiles[clave] = Perfil(clave, crudo["nombre"], crudo["unidad"], reglas)
    return CatalogoPerfiles(version=str(datos["version"]), perfiles=perfiles)
