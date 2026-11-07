"""Raíz de composición: el único lugar que conoce las implementaciones.

Lee ``config/servicio.yaml`` y ``config/perfiles.yaml``, elige el proveedor
(``MESHAUDIT_PROVEEDOR=ollama|falso``) y el almacén vectorial
(``MESHAUDIT_VECTORIAL=chroma|memoria``), y conecta C7 con las capas
superiores a través de los puertos del dominio.

Uso:  MESHAUDIT_PROVEEDOR=falso uvicorn servicio.composicion:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from servicio.cache.exacta import CacheExacta
from servicio.cache.semantica import CacheSemantica
from servicio.contexto.herramientas import Analizador
from servicio.contexto.perfiles import CatalogoPerfiles, cargar_perfiles
from servicio.contexto.prompts import tamano_lote
from servicio.contexto.recuperador import Indice, Recuperador
from servicio.datos.documentos import LectorDocumentos
from servicio.datos.falsos import ChatFalso, EmbeddingsFalsos, SondaFalsa
from servicio.datos.mallas import AlmacenMallasTemporal, LectorTrimesh
from servicio.datos.memoria import AlmacenMemoria
from servicio.datos.sqlite import (
    AlmacenCacheSQLite,
    BaseSQLite,
    RepositorioDocumentosSQLite,
    RepositorioInformesSQLite,
    RepositorioManifiestoSQLite,
    RepositorioRetroalimentacionSQLite,
)
from servicio.dominio import ModeloChat
from servicio.guardrails.entrada import GuardrailsEntrada
from servicio.guardrails.salida import GuardrailsSalida
from servicio.modelos.enrutador import Enrutador
from servicio.modelos.gateway import Gateway
from servicio.observabilidad.metricas import Metricas
from servicio.observabilidad.traza import RegistroTrazas
from servicio.orquestacion.agente import CicloAgente
from servicio.orquestacion.auditor import OrquestadorAuditoria
from servicio.orquestacion.ingesta import ServicioIngesta
from servicio.orquestacion.preguntas import ServicioPreguntas
from servicio.retroalimentacion.almacen import AlmacenRetroalimentacion

RAIZ = Path(__file__).resolve().parents[1]
CONFIG_SERVICIO = RAIZ / "config" / "servicio.yaml"
CONFIG_PERFILES = RAIZ / "config" / "perfiles.yaml"


def cargar_config(ruta: Path | str | None = None) -> dict:
    config = yaml.safe_load(Path(ruta or CONFIG_SERVICIO).read_text(encoding="utf-8"))
    entorno = os.environ
    if entorno.get("MESHAUDIT_PROVEEDOR"):
        config["proveedor"] = entorno["MESHAUDIT_PROVEEDOR"]
    if entorno.get("MESHAUDIT_VECTORIAL"):
        config["vectorial"] = entorno["MESHAUDIT_VECTORIAL"]
    if entorno.get("MESHAUDIT_DATOS"):
        config["datos"]["directorio"] = entorno["MESHAUDIT_DATOS"]
    if entorno.get("MESHAUDIT_CACHE") is not None and entorno.get("MESHAUDIT_CACHE") != "":
        config["cache"]["activa"] = entorno["MESHAUDIT_CACHE"].lower() not in ("0", "false", "no")
    for alias in ("rapido", "completo", "embeddings"):  # p. ej. un alias hacia una etiqueta inexistente
        if entorno.get(f"MESHAUDIT_MODELO_{alias.upper()}"):
            config["modelos"][alias] = entorno[f"MESHAUDIT_MODELO_{alias.upper()}"]
    if entorno.get("MESHAUDIT_OLLAMA_URL"):
        config["ollama"]["url"] = entorno["MESHAUDIT_OLLAMA_URL"]
    if config["proveedor"] not in ("ollama", "falso"):
        raise ValueError("MESHAUDIT_PROVEEDOR debe ser 'ollama' o 'falso'")
    return config


@dataclass
class Contenedor:
    config: dict
    catalogo: CatalogoPerfiles
    auditor: OrquestadorAuditoria
    preguntas: ServicioPreguntas
    ingesta: ServicioIngesta
    retroalimentacion: AlmacenRetroalimentacion
    trazas: RegistroTrazas
    metricas: Metricas | None = None
    sondas: list = field(default_factory=list)
    indice: Indice | None = None
    gateway: Gateway | None = None
    cache: CacheExacta | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def configuracion_publica(self) -> dict:
        c = self.config
        return {
            "proveedor": c["proveedor"],
            "vectorial": c["vectorial"],
            "modelos": {"rapido": self.gateway.nombre_modelo("rapido"),
                        "completo": self.gateway.nombre_modelo("completo"),
                        "embeddings": self.extras["embeddings"].nombre,
                        "juez": c["modelos"].get("juez")},
            "rag": {**c["rag"], "lote_efectivo": tamano_lote(
                c["rag"]["k"], c["rag"]["tam_fragmento"], c["rag"]["num_ctx"],
                c["rag"]["reserva_prompt_tokens"], c["rag"]["lote_hallazgos"],
                **_parametros_lote(c["rag"]))},
            "agente": c["agente"],
            "umbrales": {"recuperacion": c["rag"]["umbral"],
                         "fuera_de_dominio": c["guardrails"]["umbral_fuera_dominio"],
                         "cache_semantica": c["cache"]["umbral_semantico"]},
            "tiempos_limite_s": c["tiempos_limite_s"],
            "reintentos": c["reintentos"],
            "cache": {"activa": c["cache"]["activa"],
                      "expiracion_exacta_h": c["cache"]["expiracion_exacta_h"],
                      "expiracion_semantica_h": c["cache"]["expiracion_semantica_h"]},
            "guardrails": {k: v for k, v in c["guardrails"].items()},
            "ollama": {"opciones": c["ollama"]["opciones"], "keep_alive": c["ollama"]["keep_alive"]},
            "versiones": self.auditor.versiones(),
        }


def _parametros_lote(rag: dict) -> dict:
    return {"tokens_salida": rag.get("tokens_salida_por_hallazgo", 250),
            "caracteres_por_token": rag.get("caracteres_por_token", 3.5)}


def _modelos(config: dict, proveedor: str):
    nombres = config["modelos"]
    if proveedor == "falso":
        chats: dict[str, ModeloChat] = {"rapido": ChatFalso(f"falso-{nombres['rapido']}"),
                                        "completo": ChatFalso(f"falso-{nombres['completo']}")}
        return chats, EmbeddingsFalsos(), [SondaFalsa("modelos")]
    from servicio.datos.ollama import ChatOllama, EmbeddingsOllama, SondaOllama

    o = config["ollama"]
    chats = {alias: ChatOllama(nombres[alias], o["url"], o["opciones"], o["keep_alive"])
             for alias in ("rapido", "completo")}
    embeddings = EmbeddingsOllama(nombres["embeddings"], o["url"],
                                  config["tiempos_limite_s"]["embeddings"], o["keep_alive"])
    sonda = SondaOllama(o["url"], [nombres["rapido"], nombres["completo"], nombres["embeddings"]])
    return chats, embeddings, [sonda]


def construir(config: dict | None = None, *, proveedor: str | None = None,
              dir_datos: Path | str | None = None, vectorial: str | None = None,
              chats: dict[str, ModeloChat] | None = None, cache_activa: bool | None = None,
              dormir=None) -> Contenedor:
    config = copy.deepcopy(config or cargar_config())
    if proveedor:
        config["proveedor"] = proveedor
    if vectorial:
        config["vectorial"] = vectorial
    if dir_datos:
        config["datos"]["directorio"] = str(dir_datos)
    if cache_activa is not None:
        config["cache"]["activa"] = cache_activa
    datos = config["datos"]
    directorio = Path(datos["directorio"])
    if not directorio.is_absolute():
        directorio = RAIZ / directorio
    directorio.mkdir(parents=True, exist_ok=True)

    # C7: recursos
    base = BaseSQLite(directorio / datos["sqlite"])
    almacen = (AlmacenMemoria() if config["vectorial"] == "memoria"
               else _chroma(directorio / datos["chroma"]))
    temporales = AlmacenMallasTemporal(directorio / datos["mallas"])
    trazas = RegistroTrazas(directorio / datos["trazas"])
    modelos_chat, embeddings, sondas_modelos = _modelos(config, config["proveedor"])
    if chats:
        modelos_chat.update(chats)
    falla = os.environ.get("MESHAUDIT_FALLA")  # evaluación de fallas: alias:tipo[:n]
    if falla:
        from servicio.datos.falsos import ChatConFalla
        alias, tipo, *n = falla.split(":")
        for nombre in (("rapido", "completo") if alias == "*" else (alias,)):
            modelos_chat[nombre] = ChatConFalla(modelos_chat[nombre], tipo, int(n[0]) if n else None)
    informes = RepositorioInformesSQLite(base)
    catalogo = cargar_perfiles(CONFIG_PERFILES)

    # C6
    gateway_kwargs = {"dormir": dormir} if dormir else {}
    gateway = Gateway(modelos_chat, config["tiempos_limite_s"], config["reintentos"]["maximo"],
                      config["reintentos"]["esperas_s"], **gateway_kwargs)
    enrutador = Enrutador()
    # C5
    rag = config["rag"]
    indice = Indice(embeddings, almacen, RepositorioManifiestoSQLite(base),
                    RepositorioDocumentosSQLite(base), LectorDocumentos(),
                    rag["tam_fragmento"], rag["solape"])
    recuperador = Recuperador(embeddings, almacen, rag["k"], rag["umbral"])
    g = config["guardrails"]
    analizador = Analizador(LectorTrimesh(g["max_caras"]), catalogo, g["max_caras"])
    # C4
    c = config["cache"]
    almacen_cache = AlmacenCacheSQLite(base)
    cache = CacheExacta(almacen_cache, c["expiracion_exacta_h"], c["activa"])
    cache_semantica = CacheSemantica(almacen_cache, embeddings, c["umbral_semantico"],
                                     c["expiracion_semantica_h"], c["activa"])
    # C3
    entrada = GuardrailsEntrada(LectorTrimesh(g["max_caras"]), LectorDocumentos(), embeddings, almacen,
                                gateway, g["tam_max_malla_mb"], g["tam_max_documento_mb"],
                                g["umbral_fuera_dominio"], g["licencias_permitidas"])
    salida = GuardrailsSalida()
    # C2
    agente = CicloAgente(recuperador, gateway, rag["k"], config["agente"]["max_reformulaciones"],
                         rag["umbral"])
    comunes = dict(entrada=entrada, salida=salida, cache=cache, analizador=analizador,
                   enrutador=enrutador, gateway=gateway, agente=agente, indice=indice,
                   informes=informes, trazas=trazas, embeddings_nombre=embeddings.nombre,
                   num_ctx=rag["num_ctx"])
    auditor = OrquestadorAuditoria(temporales=temporales, lote=rag["lote_hallazgos"],
                                   max_reformulaciones_informe=config["agente"]["max_por_informe"],
                                   reserva_tokens=rag["reserva_prompt_tokens"],
                                   parametros_lote=_parametros_lote(rag), **comunes)
    preguntas = ServicioPreguntas(cache_semantica=cache_semantica,
                                  max_reformulaciones=config["agente"]["max_por_informe"],
                                  **comunes)
    ingesta = ServicioIngesta(entrada=entrada, salida=salida, indice=indice, cache=cache,
                              trazas=trazas)
    # T2
    retro = AlmacenRetroalimentacion(RepositorioRetroalimentacionSQLite(base),
                                     entrada.enmascarar, informes.obtener_por_traza)
    sondas = [*sondas_modelos, _Sonda("chromadb" if config["vectorial"] == "chroma"
                                      else "vectorial", almacen),
              _Sonda("sqlite", base)]
    return Contenedor(config=config, catalogo=catalogo, auditor=auditor, preguntas=preguntas,
                      ingesta=ingesta, retroalimentacion=retro, trazas=trazas,
                      metricas=Metricas(trazas, retro), sondas=sondas,
                      indice=indice, gateway=gateway, cache=cache,
                      extras={"embeddings": embeddings, "almacen": almacen, "base": base,
                              "chats": modelos_chat, "cache_semantica": cache_semantica})


def _chroma(ruta: Path):
    from servicio.datos.chroma import AlmacenChroma
    return AlmacenChroma(ruta)


class _Sonda:
    def __init__(self, nombre: str, recurso):
        self.nombre = nombre
        self.recurso = recurso

    def comprobar(self) -> dict:
        return self.recurso.comprobar()


# ---------------------------------------------------------------------------
# Aplicación ASGI
# ---------------------------------------------------------------------------

def crear_aplicacion(contenedor: Contenedor | None = None):
    from servicio.api.app import crear_app
    return crear_app(contenedor or construir())


_app = None


def __getattr__(nombre: str):
    """``servicio.composicion:app`` se construye al pedirla (uvicorn), no al importar."""
    global _app
    if nombre == "app":
        if _app is None:
            _app = crear_aplicacion()
        return _app
    raise AttributeError(nombre)
