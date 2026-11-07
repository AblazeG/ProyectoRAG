"""Utilidades compartidas por las pruebas."""
from pathlib import Path

from servicio.contexto.recuperador import Indice, Recuperador
from servicio.datos.documentos import LectorDocumentos
from servicio.datos.falsos import EmbeddingsFalsos
from servicio.datos.memoria import AlmacenMemoria
from servicio.datos.sqlite import (BaseSQLite, RepositorioDocumentosSQLite,
                                   RepositorioManifiestoSQLite)
from servicio.dominio import ArchivoSubido

RAIZ = Path(__file__).resolve().parents[1]
CORPUS = RAIZ / "tests" / "corpus"


def indice_de_prueba(almacen=None, embeddings=None, base=None):
    base = base or BaseSQLite(":memory:")
    embeddings = embeddings or EmbeddingsFalsos()
    almacen = almacen if almacen is not None else AlmacenMemoria()
    indice = Indice(embeddings, almacen, RepositorioManifiestoSQLite(base),
                    RepositorioDocumentosSQLite(base), LectorDocumentos())
    return indice, Recuperador(embeddings, almacen)


def cargar_corpus(indice):
    for ruta in sorted(CORPUS.glob("*.md")):
        archivo = ArchivoSubido(ruta.name, ruta.read_bytes())
        _, fragmentos, registro = indice.extraer_y_fragmentar(archivo, "CC0-1.0")
        indice.indexar(fragmentos, registro)


def contenedor_de_prueba(tmp_path, vectorial="memoria", chats=None, cache_activa=True,
                         con_corpus=True):
    """Contenedor completo con el proveedor falso, en un directorio temporal."""
    from servicio.composicion import construir
    c = construir(proveedor="falso", dir_datos=tmp_path / "data", vectorial=vectorial,
                  chats=chats, cache_activa=cache_activa, dormir=lambda s: None)
    if con_corpus:
        for ruta in sorted(CORPUS.glob("*.md")):
            c.ingesta.ingerir(ArchivoSubido(ruta.name, ruta.read_bytes()))
    return c
