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

from servicio.dominio import (
    SIN_NORMA,
    SIN_NORMA_VERIFICADA,
    RespuestaExplicaciones,
    RespuestaPreguntaModelo,
    Veredicto,
)
from servicio.guardrails import patrones

# Código 8 del informe y tabla 13 (S4).
AVISOS = {
    ("informe", True): "Informe generado por un modelo; puede contener errores.",
    ("informe", False): "Informe automático; puede contener errores.",
    ("respuesta", True): "Respuesta generada por un modelo; puede contener errores.",
    ("respuesta", False): "Respuesta automática; puede contener errores.",
}
AVISO_MODELO = AVISOS[("informe", True)]
AVISO_SIN_MODELO = AVISOS[("informe", False)]
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

    # -- S1 + S2 + S3 --------------------------------------------------------
    def verificar_generacion(self, texto: str, modelo: type[BaseModel],
                             permitidos: dict[str, set[str]] | set[str],
                             textos: dict[str, str]) -> Veredicto:
        """Verifica una salida del modelo: formato (S1), citas (S2) y cifras (S3).

        ``permitidos``: ids de fragmento entregados (por hallazgo en las
        explicaciones). ``textos``: texto de cada fragmento, para S3. La
        instancia del veredicto ya trae las citas inventadas quitadas.
        """
        instancia = self.validar_formato(texto, modelo)
        if instancia is None:
            return Veredicto(False, motivo="formato", activaciones=["S1"])
        if isinstance(instancia, RespuestaExplicaciones):
            elementos = [(e.id, e.explicacion, e.correccion, e.citas) for e in instancia.hallazgos]
        elif isinstance(instancia, RespuestaPreguntaModelo):
            elementos = [("respuesta", instancia.respuesta, [], instancia.citas)]
        else:
            return Veredicto(True, instancia=instancia)
        items, activaciones = {}, []
        for clave, principal, pasos, citas in elementos:
            if es_sin_norma(principal):
                items[clave] = {"texto": SIN_NORMA, "correccion": [], "citas": [],
                                "removidas": [], "malas": [], "sin_norma": True}
                continue
            validos = permitidos.get(clave, set()) if isinstance(permitidos, dict) else permitidos
            exp = self.verificar_citas(principal, citas, validos)
            corr = [self.verificar_citas(p, citas, validos) for p in pasos]
            usadas = list(dict.fromkeys(exp.citas + [c for p in corr for c in p.citas]))
            removidas = exp.removidas + [c for p in corr for c in p.removidas]
            malas = self.verificar_cifras(" ".join([exp.texto] + [p.texto for p in corr]),
                                          [textos[c] for c in usadas if c in textos])
            items[clave] = {"texto": exp.texto, "correccion": [p.texto for p in corr if p.texto],
                            "citas": usadas, "removidas": removidas, "malas": malas,
                            "sin_norma": False}
            if removidas and "S2" not in activaciones:
                activaciones.append("S2")
            if malas and "S3" not in activaciones:
                activaciones.append("S3")
        con_cifras = any(i["malas"] for i in items.values())
        return Veredicto(not con_cifras, motivo="cifras" if con_cifras else None,
                         activaciones=activaciones, instancia=instancia, detalles=items)

    def eliminar_cifras(self, veredicto: Veredicto) -> Veredicto:
        """S3 tras el reintento: elimina las frases con cifras sin respaldo."""
        for item in veredicto.detalles.values():
            if item["malas"]:
                item["eliminadas"] = list(item["malas"])
                item["texto"] = self.eliminar_frases(item["texto"], item["malas"])
                item["correccion"] = [x for x in (self.eliminar_frases(c, item["malas"])
                                                  for c in item["correccion"]) if x]
                item["malas"] = []
        veredicto.aprobado = False   # corregida: no se guarda en caché
        return veredicto

    # -- S4 --------------------------------------------------------------------
    @classmethod
    def aplicar_aviso(cls, respuesta: dict, con_modelo: bool, tipo: str = "informe") -> dict:
        """S4: vuelve a enmascarar y añade el aviso («generado por un modelo» o,
        sin modelo, «automático»). Se aplica a toda respuesta, también de caché."""
        salida = cls._reenmascarar(copy.deepcopy(respuesta))
        salida["aviso"] = AVISOS[(tipo, bool(con_modelo))]
        guardrails = salida.get("guardrails")
        if not isinstance(guardrails, dict):
            guardrails = {"entrada": "aprobada", "salida": "aprobada",
                          "activaciones": list(guardrails or [])}
        guardrails = {**guardrails, "activaciones": list(guardrails.get("activaciones", []))}
        if "S4" not in guardrails["activaciones"]:
            guardrails["activaciones"].append("S4")
        salida["guardrails"] = guardrails
        return salida


def es_sin_norma(texto: str) -> bool:
    return texto.strip().rstrip(".") == SIN_NORMA


__all__ = ["GuardrailsSalida", "AVISO_MODELO", "AVISO_SIN_MODELO", "MENSAJE_SEGURO_FORMATO",
           "SIN_NORMA_VERIFICADA", "es_sin_norma"]
