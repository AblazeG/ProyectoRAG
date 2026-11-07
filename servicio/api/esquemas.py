"""Esquemas Pydantic v2 de la API (C1). Contrato de ``POST /auditorias``
según el Código 8 del informe."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Semaforo = Literal["verde", "amarillo", "rojo"]


class Abierto(BaseModel):
    model_config = ConfigDict(extra="allow")


class Fuente(Abierto):
    documento: str            # doc_id, p. ej. "blender_manual"
    seccion: str
    puntaje: float
    fragmento: str
    id: str | None = None


class Guardrails(Abierto):
    entrada: str              # "aprobada" | "enmascarada" | "rechazada"
    salida: str               # "aprobada" | "corregida"
    activaciones: list[str] = Field(default_factory=list)


class HallazgoSalida(Abierto):
    id: str
    verificacion: str
    tipo: str
    gravedad: Literal["grave", "menor", "informativo"]
    medido: str               # p. ej. "12.4 %"
    limite: str               # p. ej. "0 %"
    explicacion: str | None = None
    correccion: list[str] = Field(default_factory=list)
    fuente: Fuente | None = None


class MetricasMalla(Abierto):
    dimension_max: float
    unidad: Literal["m", "mm"]


class RespuestaAuditoria(Abierto):
    auditoria_id: str
    resumen: str
    semaforo: Semaforo
    metricas_malla: MetricasMalla
    hallazgos: list[HallazgoSalida]
    modelo: str
    ruta: Literal["sin_modelo", "rapida", "completa"]
    cache: str
    guardrails: Guardrails
    iteraciones_agente: int
    tiempo_ms: float
    traza_id: str
    aviso: str


class EntradaPregunta(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    pregunta: str = Field(min_length=1, max_length=1000)


class FuentePregunta(Abierto):
    id: str
    documento: str
    seccion: str
    puntaje: float
    fragmento: str


class RespuestaPregunta(Abierto):
    auditoria_id: str
    respuesta: str
    fuentes: list[FuentePregunta]
    cache: str
    modelo: str | None
    ruta: str | None
    guardrails: Guardrails
    iteraciones_agente: int
    traza_id: str
    aviso: str


class EntradaRetroalimentacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    traza_id: str = Field(min_length=1, max_length=64)
    util: bool
    comentario: str | None = Field(default=None, max_length=2000)
    hallazgo_id: str | None = Field(default=None, max_length=32)


class RespuestaRetroalimentacion(Abierto):
    traza_id: str
    util: bool
    hallazgo_id: str | None = None
    comentario: str | None = None


class RespuestaDocumento(Abierto):
    documento_id: str
    nombre: str
    formato: str
    fragmentos: int
    version_corpus: int
    fecha: float


class Error(Abierto):
    detalle: str
