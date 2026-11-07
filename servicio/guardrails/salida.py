"""Guardrails de salida (C3): S1 formato, S2 citas, S3 cifras y S4 aviso.

S1 y S3 indican a C2 que reintente una vez; después, S1 deja un mensaje
seguro y S3 elimina la frase. S4 se aplica siempre, también con caché.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from servicio.dominio import SIN_NORMA, SIN_NORMA_VERIFICADA
from servicio.guardrails import patrones

AVISO_MODELO = ("Texto generado por un modelo de lenguaje a partir de mediciones deterministas "
                "y de las normas del corpus; puede contener errores. Verifica las correcciones "
                "antes de aplicarlas.")
AVISO_SIN_MODELO = ("Informe automático generado por plantilla, sin modelo de lenguaje; puede "
                    "contener errores. Verifica los resultados antes de usarlos.")
MENSAJE_SEGURO_FORMATO = ("No fue posible generar una explicación verificable. Consulta la "
                          "fuente indicada y las mediciones del informe.")

# Claves que no se re-enmascaran en S4 (identificadores y hashes técnicos).
CLAVES_TECNICAS = {"auditoria_id", "traza_id", "id", "verificacion", "hallazgo_id",
                   "archivo_sha", "documento_id", "doc_id"}


@dataclass
class ResultadoCitas:
    texto: str
    citas: list[str]
    removidas: list[str] = field(default_factory=list)

    @property
    def sin_norma_verificada(self) -> bool:
        return not self.citas


class GuardrailsSalida:
    # -- S1 ----------------------------------------------------------------
    @staticmethod
    def validar_formato(texto: str, modelo: type[BaseModel]) -> BaseModel | None:
        """JSON válido contra el esquema Pydantic; None si no lo es."""
        try:
            return modelo.model_validate_json(texto)
        except (ValidationError, ValueError):
            return None

    # -- S2 ----------------------------------------------------------------
    @staticmethod
    def verificar_citas(texto: str, citas: list[str], entregados: set[str]) -> ResultadoCitas:
        """Quita las citas a ids que no se entregaron en el contexto."""
        removidas = []

        def reemplazo(m: re.Match) -> str:
            if m.group(1) in entregados:
                return m.group(0)
            removidas.append(m.group(1))
            return ""

        limpio = re.sub(r"\s{2,}", " ", patrones.CITA.sub(reemplazo, texto)).strip()
        limpio = re.sub(r"\s+([.,;:])", r"\1", limpio)
        en_texto = [m.group(1) for m in patrones.CITA.finditer(limpio)]
        validas = list(dict.fromkeys([c for c in citas if c in entregados] + en_texto))
        removidas += [c for c in citas if c not in entregados and c not in removidas]
        return ResultadoCitas(limpio, validas, removidas)

    # -- S3 ----------------------------------------------------------------
    @staticmethod
    def valores_respaldados(textos: list[str]) -> set[float]:
        valores = set()
        for texto in textos:
            for crudo in re.findall(r"\d{1,3}(?:[  ]\d{3})+|\d+(?:[.,]\d+)?", texto):
                valor = patrones.valor_numerico(crudo)
                if valor is not None:
                    valores.add(valor)
        return valores

    @classmethod
    def verificar_cifras(cls, texto: str, textos_citados: list[str]) -> list[str]:
        """Oraciones con cifras que no aparecen en los fragmentos citados."""
        respaldo = cls.valores_respaldados(textos_citados)
        return [o for o in patrones.oraciones(texto)
                if any(valor not in respaldo for _, valor in patrones.cifras(o))]

    @staticmethod
    def eliminar_frases(texto: str, frases: list[str]) -> str:
        restantes = [o for o in patrones.oraciones(texto) if o not in frases]
        return " ".join(restantes).strip()

    # -- S4 ----------------------------------------------------------------
    @staticmethod
    def _reenmascarar(valor: Any, clave: str | None = None) -> Any:
        if isinstance(valor, str):
            return valor if clave in CLAVES_TECNICAS else patrones.enmascarar(valor)[0]
        if isinstance(valor, list):
            return [GuardrailsSalida._reenmascarar(v, clave) for v in valor]
        if isinstance(valor, dict):
            return {k: GuardrailsSalida._reenmascarar(v, k) for k, v in valor.items()}
        return valor

    @classmethod
    def aplicar_aviso(cls, respuesta: dict, con_modelo: bool) -> dict:
        """S4: vuelve a enmascarar y añade el aviso que corresponde a la ruta."""
        salida = cls._reenmascarar(copy.deepcopy(respuesta))
        salida["aviso"] = AVISO_MODELO if con_modelo else AVISO_SIN_MODELO
        activados = list(salida.get("guardrails") or [])
        if "S4" not in activados:
            activados.append("S4")
        salida["guardrails"] = activados
        return salida


def es_sin_norma(texto: str) -> bool:
    return texto.strip().rstrip(".") == SIN_NORMA


__all__ = ["GuardrailsSalida", "AVISO_MODELO", "AVISO_SIN_MODELO", "MENSAJE_SEGURO_FORMATO",
           "SIN_NORMA_VERIFICADA", "es_sin_norma"]
