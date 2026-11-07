"""Ciclo de agente (C2): recuperación con reformulación acotada.

Uso principal: preguntas de seguimiento coloquiales. También se aplica a la
consulta canónica de un hallazgo que no recupera bien.

- Suficiente si top-1 ≥ 0.55 y hay al menos 2 fragmentos sobre el umbral.
- Si no, el alias ``rapido`` reformula con sinónimos técnicos ES/EN.
- Tope: 3 reformulaciones por consulta y 6 por informe (``presupuesto.consumir()``).
- Al agotarse: «sin norma aplicable» (lista vacía).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from servicio.contexto import prompts
from servicio.contexto.recuperador import Recuperador, ResultadoRecuperacion
from servicio.dominio import ErrorModelo, Recuperado, Reformulacion
from servicio.modelos.gateway import Gateway

MAX_REFORMULACIONES = 3
UMBRAL = 0.55
MAX_POR_INFORME = 6
MIN_FRAGMENTOS = 2


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


@dataclass
class ResultadoAgente:
    fragmentos: list[Recuperado]          # vacío = sin norma aplicable
    iteraciones: int
    consultas: list[str] = field(default_factory=list)
    top1: float = 0.0
    suficiente: bool = False


def suficiente(resultado: ResultadoRecuperacion, umbral: float = UMBRAL) -> bool:
    sobre_umbral = [r for r in resultado.candidatos if r.puntaje >= umbral]
    return resultado.top1 >= umbral and len(sobre_umbral) >= MIN_FRAGMENTOS


def recuperar_con_agente(consulta, perfil, presupuesto, traza, *,
                         recuperador: Recuperador, gateway: Gateway | None,
                         etiqueta: str | None = None,
                         max_reformulaciones: int = MAX_REFORMULACIONES) -> ResultadoAgente:
    """Código 4 del informe. ``recuperador`` y ``gateway`` se inyectan."""
    mejor = recuperador.recuperar(consulta, perfil=perfil)
    consultas = [consulta]
    actual = consulta
    iteraciones = 0
    while (not suficiente(mejor) and iteraciones < max_reformulaciones
           and gateway is not None and presupuesto.consumir()):
        iteraciones += 1
        try:
            resultado = gateway.generar("rapido", prompts.construir_reformulacion(actual, iteraciones),
                                        prompts.ESQUEMA_REFORMULACION, ruta="agente", traza=traza)
            actual = Reformulacion.model_validate_json(resultado.generacion.texto).consulta
        except (ErrorModelo, ValueError):
            break  # sin reformulación posible: se conserva lo mejor que hubo
        consultas.append(actual)
        nuevo = recuperador.recuperar(actual, perfil=perfil)
        if nuevo.top1 > mejor.top1 or suficiente(nuevo):
            mejor = nuevo
    es_suficiente = suficiente(mejor)
    if traza is not None:
        traza.sumar_iteraciones(iteraciones)
        traza.registrar_recuperacion(etiqueta or consulta[:60], mejor.top1, len(mejor.fragmentos))
    return ResultadoAgente(fragmentos=mejor.fragmentos if es_suficiente else [],
                           iteraciones=iteraciones, consultas=consultas, top1=mejor.top1,
                           suficiente=es_suficiente)


class Agente:
    """Envoltura con las dependencias ya inyectadas."""

    def __init__(self, recuperador: Recuperador, gateway: Gateway | None,
                 max_reformulaciones: int = MAX_REFORMULACIONES):
        self.recuperador = recuperador
        self.gateway = gateway
        self.max_reformulaciones = max_reformulaciones

    def recuperar_con_agente(self, consulta, perfil, presupuesto, traza,
                             etiqueta: str | None = None) -> ResultadoAgente:
        return recuperar_con_agente(consulta, perfil, presupuesto, traza,
                                    recuperador=self.recuperador, gateway=self.gateway,
                                    etiqueta=etiqueta,
                                    max_reformulaciones=self.max_reformulaciones)
