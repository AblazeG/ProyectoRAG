"""Ciclo de agente (C2): recuperación con reformulación acotada (Código 4, ADR-07).

Uso principal: preguntas de seguimiento coloquiales. También se aplica a la
consulta canónica de un hallazgo que no recupera bien entre español e inglés.

- Suficiente si top-1 ≥ 0.55 y hay al menos 2 fragmentos sobre el umbral.
- Si no, el alias ``rapido`` reformula la consulta con sinónimos técnicos ES/EN.
- Tope: 3 reformulaciones por consulta y 6 por informe (``presupuesto.consumir()``).
- Al agotarse, la consulta se declara «sin norma aplicable» (lista vacía).
"""
from __future__ import annotations

from servicio.contexto.prompts import prompt_reformular
from servicio.contexto.recuperador import Recuperador, ResultadoRecuperacion
from servicio.dominio import ErrorModelo, Recuperado
from servicio.modelos.gateway import Gateway

MAX_REFORMULACIONES = 3        # por consulta; el presupuesto admite 6 por informe
UMBRAL = 0.55
MAX_POR_INFORME = 6
MIN_SOBRE_UMBRAL = 2


class Presupuesto:
    """Reformulaciones disponibles para todo un informe (o una pregunta)."""

    def __init__(self, maximo: int = MAX_POR_INFORME):
        self.maximo = maximo
        self.usadas = 0

    @property
    def restante(self) -> int:
        return self.maximo - self.usadas

    def consumir(self) -> bool:
        if self.usadas >= self.maximo:
            return False
        self.usadas += 1
        return True


def es_suficiente(recuperados: ResultadoRecuperacion, umbral: float = UMBRAL) -> bool:
    """top-1 ≥ umbral y al menos dos fragmentos sobre el umbral."""
    sobre_umbral = [r for r in recuperados.candidatos if r.puntaje >= umbral]
    return recuperados.top1 >= umbral and len(sobre_umbral) >= MIN_SOBRE_UMBRAL


class CicloAgente:
    def __init__(self, recuperador: Recuperador, gateway: Gateway | None, k: int = 5,
                 max_reformulaciones: int = MAX_REFORMULACIONES, umbral: float = UMBRAL):
        self.recuperador = recuperador
        self.gateway = gateway
        self.k = k
        self.max_reformulaciones = max_reformulaciones
        self.umbral = umbral

    def recuperar_con_agente(self, consulta, perfil, presupuesto, traza
                             ) -> tuple[list[Recuperado], int]:
        """Código 4 del informe. Devuelve (fragmentos, reformulaciones usadas);
        una lista vacía significa «sin norma aplicable»."""
        recuperador, gateway = self.recuperador, self.gateway
        intento = 0
        for intento in range(self.max_reformulaciones + 1):
            recuperados = recuperador.recuperar(consulta, k=self.k, perfil=perfil)
            if traza is not None:
                traza.registrar_recuperacion(consulta[:80], recuperados.top1,
                                             len(recuperados.fragmentos))
            if es_suficiente(recuperados, self.umbral):
                return recuperados.fragmentos, intento          # condición de salida
            if (intento == self.max_reformulaciones or gateway is None
                    or not presupuesto.consumir()):
                break                                           # tope por consulta o por informe
            try:
                consulta = gateway.generar("rapido", prompt_reformular(consulta),
                                           ruta="agente", traza=traza).texto.strip()
            except ErrorModelo:
                break
            if not consulta:
                break
            if traza is not None:
                traza.anotar(reformulacion=consulta, intento=intento + 1)
                traza.sumar_iteraciones(1)
        return [], intento                                      # se informa «sin norma aplicable»
