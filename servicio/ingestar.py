"""Ingesta del corpus desde la línea de comandos (raíz de composición).

    python -m servicio.ingestar corpus/              # ingesta incremental
    python -m servicio.ingestar corpus/ --reindexar  # tras cambiar el modelo de embeddings

Cada documento pasa por E5 (formato, tamaño, licencia y, tras extraer, inyección)
igual que en ``POST /documentos``.
"""
from __future__ import annotations

import argparse
import sys

from servicio.composicion import construir
from servicio.datos.documentos import listar_corpus
from servicio.dominio import ErrorDominio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingesta del corpus normativo de MeshAudit")
    parser.add_argument("directorio", help="carpeta con PDF, HTML o Markdown (y fuentes.yaml)")
    parser.add_argument("--reindexar", action="store_true",
                        help="borra el índice y lo reconstruye con el modelo de embeddings actual")
    parser.add_argument("--licencia", default=None,
                        help="licencia por defecto si el documento no la declara")
    args = parser.parse_args(argv)

    contenedor = construir()
    if args.reindexar:   # se hace a través de C2, como cualquier cliente
        version = contenedor.ingesta.reindexar()
        print(f"Índice vaciado (version_corpus={version}).")
    documentos = listar_corpus(args.directorio)
    if not documentos:
        print(f"No hay documentos en {args.directorio}.")
        return 1
    errores = 0
    for archivo, meta in documentos:
        try:
            indexado = contenedor.ingesta.ingerir(
                archivo, licencia=meta.get("licencia") or args.licencia,
                doc_id=meta.get("doc_id"), perfiles=meta.get("perfiles"),
                titulo=meta.get("titulo"))
            print(f"✔ {archivo.nombre}: {indexado.documento_id} · {indexado.fragmentos} fragmentos "
                  f"· version_corpus={indexado.version_corpus}")
        except ErrorDominio as error:
            errores += 1
            print(f"✘ {archivo.nombre}: {error.mensaje}", file=sys.stderr)
    print(f"Manifiesto: {contenedor.ingesta.manifiesto()}")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
