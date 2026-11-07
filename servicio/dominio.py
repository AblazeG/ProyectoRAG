"""Dominio de MeshAudit: entidades, errores y puertos.

Este módulo es transversal: todas las capas pueden importarlo y él no importa
ninguna capa. Los puertos se expresan con ``typing.Protocol`` para que las
implementaciones concretas (C7) se conecten solo en ``composicion.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constantes del dominio
# ---------------------------------------------------------------------------

PERFILES = ("animacion", "juego_movil", "impresion_3d", "web_ar")
FORMATOS_MALLA = (".obj", ".glb", ".stl", ".ply")
FORMATOS_DOCUMENTO = (".pdf", ".html", ".htm", ".md", ".markdown")

Gravedad = Literal["grave", "menor", "informativo"]
GRAVEDADES = {"G": "grave", "M": "menor", "I": "informativo"}

SIN_NORMA = "Sin norma aplicable en el corpus"
SIN_NORMA_VERIFICADA = "sin norma verificada"


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------

@dataclass
class MallaCruda:
    """Arreglos leídos del archivo por C7, sin ningún procesamiento."""

    vertices: np.ndarray                 # (n, 3) float
    caras: np.ndarray                    # (m, 3) int, ya trianguladas
    uv: np.ndarray | None                # (n, 2) o None
    normales: np.ndarray | None          # (n, 3) o None si el archivo no las trae
    lados_por_cara: list[int] | None     # solo OBJ (lector propio de líneas «f»)
    formato: str                         # "obj" | "glb" | "stl" | "ply"
    tamano_bytes: int


@dataclass
class Hallazgo:
    """Resultado de una verificación que no se cumple (C5 lo produce)."""

    id: str                      # "h1", "h2", … en el orden del informe
    verificacion: str            # "V4"
    tipo: str                    # "aristas_no_manifold"
    gravedad: str                # "grave" | "menor" | "informativo"
    medido: str                  # texto con unidad, p. ej. "12.4 %" (Código 8)
    limite: str                  # p. ej. "0 %"
    descripcion: str
    consulta: str                # consulta canónica para el RAG
    norma: dict | None = None    # {"documento", "seccion"} esperado (perfiles.yaml)
    explicacion: str | None = None
    correccion: list[str] = field(default_factory=list)
    fuente: dict | None = None
    valor: Any = None            # valor numérico o lógico sin formato

    @property
    def explicable(self) -> bool:
        return self.gravedad in ("grave", "menor")


@dataclass
class Fragmento:
    id: str                 # p. ej. "blender_manual:mesh-cleanup#3"
    doc_id: str
    texto: str
    titulo: str
    seccion: str
    pagina: int | None
    formato: str
    licencia: str
    perfiles: list[str] = field(default_factory=list)


@dataclass
class Recuperado:
    fragmento: Fragmento
    puntaje: float          # similitud coseno (1 - distancia)


@dataclass
class Generacion:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_salida: int = 0
    duracion_ms: float = 0.0
    tokens_por_s: float | None = None    # eval_count / eval_duration × 10⁹
    alias: str | None = None             # lo completa el gateway
    uso_respaldo: bool = False
    intentos: int = 1


@dataclass
class DocIndexado:
    """Resultado de ``ingerir(doc)`` (C2)."""

    documento_id: str
    nombre: str
    formato: str
    licencia: str
    perfiles: list[str]
    fragmentos: int
    version_corpus: int
    fecha: float
    titulo: str = ""
    entradas_purgadas: int = 0


@dataclass
class Veredicto:
    """Respuesta de los guardrails (C3)."""

    aprobado: bool
    motivo: str | None = None
    texto: str | None = None                  # texto ya enmascarado o corregido
    activaciones: list[str] = field(default_factory=list)
    instancia: Any = None                     # salida validada (S1)
    detalles: dict = field(default_factory=dict)


@dataclass
class SeccionDocumento:
    titulo: str
    texto: str
    pagina: int | None = None


@dataclass
class DocumentoExtraido:
    titulo: str
    formato: str
    secciones: list[SeccionDocumento]
    metadatos: dict = field(default_factory=dict)   # front matter, si existe

    @property
    def texto(self) -> str:
        return "\n\n".join(f"{s.titulo}\n{s.texto}" for s in self.secciones)


@dataclass
class ArchivoSubido:
    """Archivo recibido por la API (malla o documento), aún sin validar."""

    nombre: str
    contenido: bytes

    @property
    def extension(self) -> str:
        return Path(self.nombre).suffix.lower()

    @property
    def tamano(self) -> int:
        return len(self.contenido)


# ---------------------------------------------------------------------------
# Esquemas de salida de los modelos (contratos JSON pedidos con «format»)
# ---------------------------------------------------------------------------

class ExplicacionHallazgo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="id del hallazgo que se explica")
    explicacion: str
    correccion: list[str] = Field(default_factory=list)
    citas: list[str] = Field(default_factory=list,
                             description="ids de fragmento citados")


class RespuestaExplicaciones(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hallazgos: list[ExplicacionHallazgo]


class RespuestaPreguntaModelo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    respuesta: str
    citas: list[str] = Field(default_factory=list)


class ClasificacionInyeccion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inyeccion: bool


class Reformulacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consulta: str


# ---------------------------------------------------------------------------
# Errores del dominio (la API los traduce a códigos HTTP)
# ---------------------------------------------------------------------------

class ErrorDominio(Exception):
    codigo_http = 500
    mensaje_seguro = "Ocurrió un error interno."

    def __init__(self, mensaje: str | None = None):
        super().__init__(mensaje or self.mensaje_seguro)
        self.mensaje = mensaje or self.mensaje_seguro


class NoEncontrado(ErrorDominio):
    codigo_http = 404
    mensaje_seguro = "Recurso no encontrado."


class ArchivoDemasiadoGrande(ErrorDominio):
    codigo_http = 413
    mensaje_seguro = "El archivo supera el tamaño máximo permitido."


class FormatoNoSoportado(ErrorDominio):
    codigo_http = 415
    mensaje_seguro = "El formato del archivo no es compatible."


class EntradaInvalida(ErrorDominio):
    codigo_http = 422
    mensaje_seguro = "La solicitud no se puede procesar."


class MallaDemasiadoCompleja(EntradaInvalida):
    mensaje_seguro = "La malla supera el máximo de 2 000 000 de caras."


class RechazoSolicitud(ErrorDominio):
    """Rechazo de un guardrail. ``cuerpo`` ya pasó por S4."""

    def __init__(self, codigo_http: int, mensaje: str, guardrail: str,
                 cuerpo: dict | None = None):
        super().__init__(mensaje)
        self.codigo_http = codigo_http
        self.guardrail = guardrail
        self.cuerpo = cuerpo or {"detalle": mensaje}


class IndiceIncompatible(ErrorDominio):
    codigo_http = 503
    mensaje_seguro = ("El índice se construyó con otro modelo de embeddings; "
                      "hay que reindexar el corpus.")


# Errores de modelos (C7 los produce, C6 decide qué hacer con ellos)
class ErrorModelo(ErrorDominio):
    codigo_http = 503
    mensaje_seguro = "El modelo de lenguaje no está disponible."


class ErrorConexion(ErrorModelo):
    """No se pudo conectar con el proveedor (se reintenta)."""


class ErrorServidorModelo(ErrorModelo):
    """El proveedor respondió 5xx (se reintenta)."""


class ErrorTiempoLimite(ErrorModelo):
    """Se agotó el tiempo límite (no se reintenta: va al respaldo)."""


class ModeloInexistente(ErrorModelo):
    """El proveedor respondió 404: el modelo no existe (no se reintenta)."""


class ErrorRespuestaModelo(ErrorModelo):
    """Otro error 4xx o respuesta ilegible del proveedor."""


class ModeloNoDisponible(ErrorModelo):
    """Fallaron la ruta principal y el respaldo: la API responde 503."""


class ErrorDatos(ErrorDominio):
    codigo_http = 503
    mensaje_seguro = "Un recurso de datos no está disponible."


# ---------------------------------------------------------------------------
# Puertos
# ---------------------------------------------------------------------------

@runtime_checkable
class ModeloChat(Protocol):
    nombre: str

    def generar(self, mensajes: list[dict], esquema: dict | None,
                tiempo_limite_s: float) -> Generacion: ...


@runtime_checkable
class ModeloEmbeddings(Protocol):
    nombre: str

    def vectorizar(self, textos: list[str], tipo: str) -> list[list[float]]: ...
    # tipo: "documento" | "consulta"


@runtime_checkable
class AlmacenVectorial(Protocol):
    def agregar(self, fragmentos: list[Fragmento],
                vectores: list[list[float]]) -> None: ...

    def buscar(self, vector: list[float], k: int,
               filtro: dict | None = None) -> list[Recuperado]: ...

    def eliminar_documento(self, doc_id: str) -> int: ...

    def contar(self) -> int: ...


@runtime_checkable
class LectorMalla(Protocol):
    def leer(self, ruta: Path) -> MallaCruda: ...   # vértices, caras, UV, normales

    def probar(self, ruta: Path) -> bool: ...       # lectura de prueba de E1 (OBJ y STL)


class LectorDocumento(Protocol):
    def inspeccionar(self, archivo: ArchivoSubido) -> dict: ...

    def extraer(self, archivo: ArchivoSubido) -> DocumentoExtraido: ...


class AlmacenArchivosTemporales(Protocol):
    """Guarda las mallas subidas en data/mallas/ y las borra al terminar."""

    def guardar(self, contenido: bytes, extension: str) -> Path: ...

    def borrar(self, ruta: Path) -> None: ...


class AlmacenClaveValor(Protocol):
    """Persistencia de la caché (exacta y semántica)."""

    def obtener(self, espacio: str, clave: str, ahora: float) -> dict | None: ...

    def guardar(self, espacio: str, clave: str, valor: dict,
                version_corpus: int, expira: float, ahora: float) -> None: ...

    def guardar_semantica(self, grupo: str, vector: list[float], valor: dict,
                          version_corpus: int, expira: float,
                          ahora: float) -> None: ...

    def listar_semantica(self, grupo: str, ahora: float) -> list[dict]: ...

    def purgar(self, version_corpus: int) -> int: ...

    def eliminar_expirados(self, ahora: float) -> int: ...


class RepositorioInformes(Protocol):
    def guardar(self, informe: dict, archivo_sha: str) -> None: ...

    def obtener(self, auditoria_id: str) -> dict | None: ...

    def obtener_por_traza(self, traza_id: str) -> dict | None: ...


class RepositorioDocumentos(Protocol):
    def guardar(self, documento: dict) -> None: ...

    def obtener(self, doc_id: str) -> dict | None: ...

    def listar(self) -> list[dict]: ...

    def eliminar(self, doc_id: str) -> bool: ...


class RepositorioManifiesto(Protocol):
    def leer(self) -> dict: ...

    def guardar(self, manifiesto: dict) -> None: ...


class RepositorioRetroalimentacion(Protocol):
    def guardar(self, registro: dict) -> None: ...

    def resumen(self) -> dict: ...


class Sonda(Protocol):
    """Comprobación de salud de un recurso para GET /health."""

    nombre: str

    def comprobar(self) -> dict[str, Any]: ...
