"""Índice y recuperación del corpus normativo (C5).

- ``Indice`` mantiene el manifiesto (modelo de embeddings y ``version_corpus``),
  indexa y elimina documentos. Si el modelo de embeddings cambia, impide
  mezclar vectores: hay que reindexar.
- ``Recuperador.recuperar(consulta, k=5, perfil)`` aplica el umbral 0.55 y el
  filtro por perfil, y devuelve también el puntaje top-1 para la traza.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from servicio.contexto.fragmentador import SOLAPE, TAM_FRAGMENTO, fragmentar, slug, texto_para_embedding
from servicio.dominio import (
    PERFILES,
    AlmacenVectorial,
    ArchivoSubido,
    DocIndexado,
    DocumentoExtraido,
    Fragmento,
    IndiceIncompatible,
    LectorDocumento,
    ModeloEmbeddings,
    NoEncontrado,
    Recuperado,
    RepositorioDocumentos,
    RepositorioManifiesto,
)

K = 5
UMBRAL = 0.55


@dataclass
class ResultadoRecuperacion:
    consulta: str
    fragmentos: list[Recuperado]          # sobre el umbral
    top1: float                           # aunque quede bajo el umbral
    candidatos: list[Recuperado] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [r.fragmento.id for r in self.fragmentos]


class Recuperador:
    def __init__(self, embeddings: ModeloEmbeddings, almacen: AlmacenVectorial,
                 k: int = K, umbral: float = UMBRAL):
        self.embeddings = embeddings
        self.almacen = almacen
        self.k = k
        self.umbral = umbral

    def vectorizar_consulta(self, consulta: str) -> list[float]:
        return self.embeddings.vectorizar([consulta], "consulta")[0]

    def recuperar(self, consulta: str, k: int | None = None, perfil: str | None = None,
                  umbral: float | None = None) -> ResultadoRecuperacion:
        k = k or self.k
        umbral = self.umbral if umbral is None else umbral
        vector = self.vectorizar_consulta(consulta)
        candidatos = self.almacen.buscar(vector, k, {"perfil": perfil} if perfil else None)
        top1 = candidatos[0].puntaje if candidatos else 0.0
        return ResultadoRecuperacion(
            consulta=consulta, fragmentos=[c for c in candidatos if c.puntaje >= umbral],
            top1=top1, candidatos=candidatos)

    def similitud_corpus(self, texto: str, perfil: str | None = None) -> float:
        """Similitud top-1 con el corpus (la usa E4)."""
        return self.recuperar(texto, k=1, perfil=perfil, umbral=0.0).top1


class Indice:
    def __init__(self, embeddings: ModeloEmbeddings, almacen: AlmacenVectorial,
                 manifiesto: RepositorioManifiesto, documentos: RepositorioDocumentos,
                 lector: LectorDocumento, tam: int = TAM_FRAGMENTO, solape: int = SOLAPE):
        self.embeddings = embeddings
        self.almacen = almacen
        self.repo_manifiesto = manifiesto
        self.repo_documentos = documentos
        self.lector = lector
        self.tam = tam
        self.solape = solape

    # -- manifiesto --------------------------------------------------------
    def manifiesto(self) -> dict:
        datos = self.repo_manifiesto.leer()
        return {"modelo_embeddings": datos.get("modelo_embeddings"),
                "version_corpus": int(datos.get("version_corpus", 0)),
                "actualizado": datos.get("actualizado")}

    @property
    def version_corpus(self) -> int:
        return self.manifiesto()["version_corpus"]

    def verificar_compatibilidad(self) -> None:
        modelo = self.manifiesto()["modelo_embeddings"]
        if modelo and modelo != self.embeddings.nombre and self.almacen.contar() > 0:
            raise IndiceIncompatible(
                f"El índice usa {modelo} y el servicio está configurado con "
                f"{self.embeddings.nombre}; ejecuta «python -m servicio.ingestar corpus/ --reindexar».")

    def _subir_version(self) -> int:
        actual = self.manifiesto()
        nuevo = {"modelo_embeddings": self.embeddings.nombre,
                 "version_corpus": actual["version_corpus"] + 1,
                 "actualizado": time.time()}
        self.repo_manifiesto.guardar(nuevo)
        return nuevo["version_corpus"]

    # -- documentos (figura 6) ------------------------------------------------
    def inspeccionar(self, archivo: ArchivoSubido) -> dict:
        return self.lector.inspeccionar(archivo)

    def extraer_y_fragmentar(self, archivo: ArchivoSubido, licencia: str,
                             doc_id: str | None = None, perfiles: list[str] | str | None = None,
                             titulo: str | None = None
                             ) -> tuple[DocumentoExtraido, list[Fragmento], dict]:
        """Lee PDF/HTML/MD con C7 y corta en fragmentos de 800 caracteres (solape 120)."""
        documento = self.lector.extraer(archivo)
        meta = documento.metadatos or {}
        doc_id = slug(doc_id or meta.get("doc_id") or archivo.nombre.rsplit(".", 1)[0]).replace("-", "_")
        perfiles = perfiles or meta.get("perfiles") or list(PERFILES)
        if isinstance(perfiles, str):
            perfiles = [p.strip() for p in perfiles.split(",") if p.strip()]
        perfiles = [p for p in perfiles if p in PERFILES] or list(PERFILES)
        if titulo:
            documento.titulo = titulo
        fragmentos = fragmentar(documento, doc_id, licencia, perfiles, self.tam, self.solape)
        registro = {"doc_id": doc_id, "nombre": archivo.nombre, "titulo": documento.titulo,
                    "formato": documento.formato, "licencia": licencia, "perfiles": perfiles,
                    "secciones": len(documento.secciones), "fuente": meta.get("fuente")}
        return documento, fragmentos, registro

    def indexar(self, fragmentos: list[Fragmento], registro: dict) -> DocIndexado:
        """Embeddings de los fragmentos, alta en el almacén y versión++ en el manifiesto."""
        self.verificar_compatibilidad()
        doc_id = registro["doc_id"]
        if self.repo_documentos.obtener(doc_id):
            self.almacen.eliminar_documento(doc_id)  # reemplazo del mismo documento
        if fragmentos:
            vectores = self.embeddings.vectorizar(
                [texto_para_embedding(f) for f in fragmentos], "documento")
            self.almacen.agregar(fragmentos, vectores)
        version = self._subir_version()
        fecha = time.time()
        self.repo_documentos.guardar({**registro, "fragmentos": len(fragmentos),
                                      "version_corpus": version, "fecha": fecha,
                                      "estado": "indexado"})
        return DocIndexado(documento_id=doc_id, nombre=registro["nombre"],
                           formato=registro["formato"], licencia=registro["licencia"],
                           perfiles=registro["perfiles"], fragmentos=len(fragmentos),
                           version_corpus=version, fecha=fecha, titulo=registro["titulo"])

    def registrar_cuarentena(self, archivo: ArchivoSubido, motivo: str) -> dict:
        registro = {"doc_id": "cuarentena_" + slug(archivo.nombre).replace("-", "_"),
                    "titulo": archivo.nombre, "nombre": archivo.nombre,
                    "formato": archivo.extension.lstrip("."), "fecha": time.time(),
                    "estado": "cuarentena", "motivo": motivo, "fragmentos": 0}
        self.repo_documentos.guardar(registro)
        return registro

    def eliminar(self, doc_id: str) -> dict:
        if not self.repo_documentos.obtener(doc_id):
            raise NoEncontrado("Documento no encontrado.")
        n = self.almacen.eliminar_documento(doc_id)
        self.repo_documentos.eliminar(doc_id)
        return {"doc_id": doc_id, "fragmentos_eliminados": n,
                "version_corpus": self._subir_version()}

    def listar(self) -> list[dict]:
        return self.repo_documentos.listar()

    def vaciar(self) -> int:
        """Borra el índice completo (reindexación tras cambiar de modelo)."""
        for doc in self.repo_documentos.listar():
            self.almacen.eliminar_documento(doc["doc_id"])
            self.repo_documentos.eliminar(doc["doc_id"])
        if hasattr(self.almacen, "vaciar"):
            self.almacen.vaciar()
        return self._subir_version()
