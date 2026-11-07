"""Lectura de documentos normativos (C7): PDF (pypdf), HTML (BeautifulSoup) y
Markdown. Es el único lugar que abre documentos del corpus."""
from __future__ import annotations

import io
import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from pypdf import PdfReader

from servicio.dominio import (
    ArchivoSubido,
    DocumentoExtraido,
    EntradaInvalida,
    SeccionDocumento,
)

FORMATOS = {".pdf": "pdf", ".html": "html", ".htm": "html", ".md": "markdown",
            ".markdown": "markdown"}

PATRONES_LICENCIA = [
    (re.compile(r"CC[\s-]?BY[\s-]?SA[\s-]?4\.0|Attribution-ShareAlike 4\.0", re.I), "CC-BY-SA-4.0"),
    (re.compile(r"CC[\s-]?BY[\s-]?4\.0|Creative Commons Attribution 4\.0", re.I), "CC-BY-4.0"),
    (re.compile(r"\bCC0\b|CC0[\s-]1\.0|Public Domain Dedication", re.I), "CC0-1.0"),
    (re.compile(r"Apache License,? Version 2\.0|Apache-2\.0", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT License\b", re.I), "MIT"),
]

ENCABEZADO_NUMERADO = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+([A-ZÁÉÍÓÚÑ][^\n]{2,80})$")
SELECTORES_RUIDO = ("nav", "header", "footer", "aside", "script", "style", "noscript",
                    "form", "button", "svg", "iframe")
CLASES_RUIDO = re.compile(r"menu|nav|sidebar|footer|header|breadcrumb|toc|cookie", re.I)


def detectar_licencia(texto: str) -> str | None:
    for patron, licencia in PATRONES_LICENCIA:
        if patron.search(texto):
            return licencia
    return None


def _front_matter(texto: str) -> tuple[dict, str]:
    if texto.startswith("---"):
        partes = texto.split("\n---", 1)
        if len(partes) == 2:
            try:
                meta = yaml.safe_load(partes[0][3:]) or {}
                if isinstance(meta, dict):
                    return meta, partes[1].lstrip("-\n")
            except yaml.YAMLError:
                pass
    return {}, texto


def _limpiar(texto: str) -> str:
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


class LectorDocumentos:
    """Puerto ``LectorDocumento``."""

    def inspeccionar(self, archivo: ArchivoSubido) -> dict:
        """Datos que E5 revisa antes de extraer: formato, firma, tamaño y licencia."""
        formato = FORMATOS.get(archivo.extension)
        cabeza = archivo.contenido[:2048]
        if formato == "pdf":
            firma_ok = cabeza.startswith(b"%PDF")
        elif formato == "html":
            firma_ok = b"<html" in cabeza.lower() or b"<!doctype" in cabeza.lower()
        elif formato == "markdown":
            firma_ok = b"\x00" not in cabeza
        else:
            firma_ok = False
        licencia = None
        if formato == "markdown" and firma_ok:
            meta, _ = _front_matter(archivo.contenido.decode("utf-8", "replace"))
            licencia = meta.get("licencia") or meta.get("license")
        if licencia is None and firma_ok and formato in ("markdown", "html"):
            licencia = detectar_licencia(archivo.contenido[:200_000].decode("utf-8", "replace"))
        return {"formato": formato, "firma_ok": firma_ok, "tamano": archivo.tamano,
                "licencia_detectada": licencia}

    def extraer(self, archivo: ArchivoSubido) -> DocumentoExtraido:
        formato = FORMATOS.get(archivo.extension)
        try:
            if formato == "pdf":
                return self._pdf(archivo)
            if formato == "html":
                return self._html(archivo)
            if formato == "markdown":
                return self._markdown(archivo)
        except EntradaInvalida:
            raise
        except Exception as exc:  # noqa: BLE001
            raise EntradaInvalida("No se pudo extraer el texto del documento.") from exc
        raise EntradaInvalida("Formato de documento no soportado.")

    # -- PDF ---------------------------------------------------------------
    def _pdf(self, archivo: ArchivoSubido) -> DocumentoExtraido:
        lector = PdfReader(io.BytesIO(archivo.contenido))
        titulo = (lector.metadata.title if lector.metadata and lector.metadata.title
                  else Path(archivo.nombre).stem)
        secciones: list[SeccionDocumento] = []
        actual = SeccionDocumento(titulo="Introducción", texto="", pagina=1)
        for numero, pagina in enumerate(lector.pages, start=1):
            for linea in (pagina.extract_text() or "").splitlines():
                limpia = linea.strip()
                coincidencia = ENCABEZADO_NUMERADO.match(limpia)
                if coincidencia:
                    if actual.texto.strip():
                        secciones.append(actual)
                    actual = SeccionDocumento(titulo=coincidencia.group(2).strip(),
                                              texto="", pagina=numero)
                else:
                    # Un salto doble separa párrafos cuando la línea queda vacía.
                    actual.texto += (limpia + "\n") if limpia else "\n\n"
        if actual.texto.strip():
            secciones.append(actual)
        secciones = [SeccionDocumento(s.titulo, _limpiar(s.texto), s.pagina) for s in secciones]
        return DocumentoExtraido(titulo=str(titulo), formato="pdf", secciones=secciones)

    # -- HTML --------------------------------------------------------------
    def _html(self, archivo: ArchivoSubido) -> DocumentoExtraido:
        sopa = BeautifulSoup(archivo.contenido, "html.parser")
        titulo = sopa.title.get_text(strip=True) if sopa.title else Path(archivo.nombre).stem
        for etiqueta in sopa(list(SELECTORES_RUIDO)):
            etiqueta.decompose()
        for elemento in sopa.find_all(attrs={"role": re.compile("navigation|banner|contentinfo")}):
            elemento.decompose()
        for elemento in sopa.find_all(True):
            if elemento.attrs is None:
                continue
            clases = " ".join(elemento.get("class", []) or []) + " " + (elemento.get("id") or "")
            if clases.strip() and CLASES_RUIDO.search(clases):
                elemento.decompose()
        raiz = sopa.find("main") or sopa.find("article") or sopa.body or sopa
        secciones: list[SeccionDocumento] = []
        actual = SeccionDocumento(titulo=titulo, texto="")
        for elemento in raiz.find_all(["h1", "h2", "h3", "p", "li", "pre", "td", "dd"]):
            texto = elemento.get_text(" ", strip=True)
            if not texto:
                continue
            if elemento.name in ("h1", "h2", "h3"):
                if actual.texto.strip():
                    secciones.append(actual)
                actual = SeccionDocumento(titulo=texto, texto="")
            else:
                actual.texto += texto + "\n\n"
        if actual.texto.strip():
            secciones.append(actual)
        secciones = [SeccionDocumento(s.titulo, _limpiar(s.texto)) for s in secciones]
        return DocumentoExtraido(titulo=titulo, formato="html", secciones=secciones)

    # -- Markdown ----------------------------------------------------------
    def _markdown(self, archivo: ArchivoSubido) -> DocumentoExtraido:
        texto = archivo.contenido.decode("utf-8", "replace")
        meta, cuerpo = _front_matter(texto)
        titulo = str(meta.get("titulo") or meta.get("title") or Path(archivo.nombre).stem)
        secciones: list[SeccionDocumento] = []
        actual = SeccionDocumento(titulo=titulo, texto="")
        en_codigo = False
        for linea in cuerpo.splitlines():
            if linea.strip().startswith("```"):
                en_codigo = not en_codigo
            encabezado = None if en_codigo else re.match(r"^(#{1,3})\s+(.+?)\s*#*$", linea)
            if encabezado:
                if len(encabezado.group(1)) == 1 and not secciones and not actual.texto.strip():
                    titulo = meta.get("titulo") or encabezado.group(2)
                    actual = SeccionDocumento(titulo=str(titulo), texto="")
                    continue
                if actual.texto.strip():
                    secciones.append(actual)
                actual = SeccionDocumento(titulo=encabezado.group(2).strip(), texto="")
            else:
                actual.texto += linea + "\n"
        if actual.texto.strip():
            secciones.append(actual)
        secciones = [SeccionDocumento(s.titulo, _limpiar(s.texto)) for s in secciones]
        return DocumentoExtraido(titulo=str(titulo), formato="markdown", secciones=secciones,
                                 metadatos=meta)
