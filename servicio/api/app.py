"""API HTTP (C1): FastAPI + Pydantic v2. Sin lógica de IA: valida la entrada,
llama al orquestador que corresponde y traduce errores del dominio a HTTP."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from servicio.api.esquemas import (
    EntradaPregunta,
    EntradaRetroalimentacion,
    RespuestaAuditoria,
    RespuestaDocumento,
    RespuestaPregunta,
    RespuestaRetroalimentacion,
)
from servicio.dominio import (
    FORMATOS_MALLA,
    PERFILES,
    ArchivoDemasiadoGrande,
    ArchivoSubido,
    EntradaInvalida,
    ErrorDominio,
    FormatoNoSoportado,
    NoEncontrado,
)
from servicio.orquestacion.auditor import informe_a_markdown

MB = 1024 * 1024
CORS_POR_DEFECTO = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _leer(archivo: UploadFile, limite: int) -> bytes:
    """Lee hasta ``limite`` bytes; si hay más, 413 sin cargar el resto."""
    contenido = archivo.file.read(limite + 1)
    if len(contenido) > limite:
        raise ArchivoDemasiadoGrande()
    return contenido


def _publico(informe: dict) -> dict:
    return {k: v for k, v in informe.items() if not k.startswith("_")}


def crear_app(servicios: Any) -> FastAPI:
    """``servicios`` es el contenedor que arma ``composicion.py``."""
    config = servicios.config
    limite_malla = int(config["guardrails"]["tam_max_malla_mb"] * MB)
    limite_documento = int(config["guardrails"]["tam_max_documento_mb"] * MB)

    app = FastAPI(title="MeshAudit", version="1.0.0",
                  description="Auditoría de mallas 3D con normas recuperadas por RAG.")
    app.add_middleware(CORSMiddleware,
                       allow_origins=config.get("servidor", {}).get("cors_origenes", CORS_POR_DEFECTO),
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])
    app.state.servicios = servicios

    @app.exception_handler(ErrorDominio)
    def _error_dominio(_: Request, error: ErrorDominio):
        cuerpo = getattr(error, "cuerpo", None) or {"detalle": error.mensaje}
        return JSONResponse(status_code=error.codigo_http, content=cuerpo)

    # -- salud y configuración ---------------------------------------------
    @app.get("/health")
    def salud():
        componentes = {}
        for sonda in servicios.sondas:
            try:
                componentes[sonda.nombre] = sonda.comprobar()
            except Exception as exc:  # noqa: BLE001
                componentes[sonda.nombre] = {"ok": False, "detalle": type(exc).__name__}
        ok = all(c.get("ok") for c in componentes.values())
        cuerpo = {"estado": "ok" if ok else "degradado", "proveedor": config["proveedor"],
                  "componentes": componentes}
        return JSONResponse(status_code=200 if ok else 503, content=cuerpo)

    @app.get("/configuracion")
    def configuracion():
        return servicios.configuracion_publica()

    @app.get("/perfiles")
    def perfiles():
        return servicios.catalogo.como_dict()

    @app.get("/metricas")
    def metricas():
        return servicios.metricas.resumen()

    # -- documentos ----------------------------------------------------------
    @app.post("/documentos", status_code=201, response_model=RespuestaDocumento)
    def subir_documento(archivo: UploadFile = File(...), licencia: str | None = Form(None),
                        doc_id: str | None = Form(None), perfiles: str | None = Form(None),
                        titulo: str | None = Form(None)):
        contenido = _leer(archivo, limite_documento)
        lista = [p.strip() for p in perfiles.split(",") if p.strip()] if perfiles else None
        indexado = servicios.ingesta.ingerir(ArchivoSubido(archivo.filename or "documento", contenido),
                                             licencia=licencia or None, doc_id=doc_id or None,
                                             perfiles=lista, titulo=titulo or None)
        return asdict(indexado)

    @app.get("/documentos")
    def listar_documentos():
        return {"documentos": servicios.ingesta.listar(),
                "manifiesto": servicios.ingesta.manifiesto()}

    @app.delete("/documentos/{doc_id}")
    def borrar_documento(doc_id: str):
        return servicios.ingesta.eliminar(doc_id)

    # -- auditorías ----------------------------------------------------------
    @app.post("/auditorias", response_model=RespuestaAuditoria)
    def auditar(archivo: UploadFile = File(...), perfil: str = Form(...),
                notas: str = Form("", max_length=4000)):
        """Función principal: devuelve el informe con fuentes, modelo, ruta, caché,
        guardrails, iteraciones del agente, tiempo y ``traza_id``."""
        nombre = archivo.filename or "malla"
        if perfil not in PERFILES:
            raise EntradaInvalida(f"Perfil desconocido. Usa uno de: {', '.join(PERFILES)}.")
        if not nombre.lower().endswith(FORMATOS_MALLA):
            raise FormatoNoSoportado("El formato del archivo no es compatible. "
                                     "Usa .obj, .glb, .stl o .ply.")
        contenido = _leer(archivo, limite_malla)
        return servicios.auditor.auditar(ArchivoSubido(nombre, contenido), perfil, notas)

    def _informe(auditoria_id: str) -> dict:
        informe = servicios.auditor.informes.obtener(auditoria_id)
        if informe is None:
            raise NoEncontrado("Auditoría no encontrada.")
        return informe

    @app.get("/auditorias/{auditoria_id}", response_model=RespuestaAuditoria)
    def obtener_auditoria(auditoria_id: str):
        return _publico(_informe(auditoria_id))

    @app.get("/auditorias/{auditoria_id}/markdown", response_class=PlainTextResponse)
    def exportar_markdown(auditoria_id: str):
        return PlainTextResponse(informe_a_markdown(_informe(auditoria_id)),
                                 media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition":
                                          f'attachment; filename="auditoria-{auditoria_id}.md"'})

    @app.post("/auditorias/{auditoria_id}/preguntas", response_model=RespuestaPregunta)
    def preguntar(auditoria_id: str, entrada: EntradaPregunta):
        return servicios.preguntas.preguntar(auditoria_id, entrada.pregunta)

    # -- retroalimentación ---------------------------------------------------
    @app.post("/retroalimentacion", status_code=201, response_model=RespuestaRetroalimentacion)
    def retroalimentar(entrada: EntradaRetroalimentacion):
        return servicios.retroalimentacion.guardar(entrada.traza_id, entrada.util,
                                                   entrada.comentario, entrada.hallazgo_id)

    return app
