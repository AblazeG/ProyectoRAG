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
    (re.compile(r"CC[\s-]?BY[\s-]?SA[\s-]?4\.0|Attribution-ShareAlike 4\.0|licenses/by-sa/4\.0", re.I), "CC-BY-SA-4.0"),
    (re.compile(r"CC[\s-]?BY[\s-]?4\.0|Creative Commons Attribution 4\.0|licenses/by/4\.0", re.I), "CC-BY-4.0"),
    (re.compile(r"CC[\s-]?BY[\s-]?3\.0|Creative Commons Attribution 3\.0|licenses/by/3\.0", re.I), "CC-BY-3.0"),
    (re.compile(r"\bCC0\b|CC0[\s-]1\.0|Public Domain Dedication", re.I), "CC0-1.0"),
    (re.compile(r"Apache License,? Version 2\.0|Apache-2\.0", re.I), "Apache-2.0"),
    (re.compile(r"\bMIT License\b", re.I), "MIT"),
]

# «1 Título», «2.3 Título»: 1–2 dígitos por nivel y sin punto final (no «2024 Universidad…»
# ni «20000 Triángulos como máximo.»).
ENCABEZADO_NUMERADO = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+([A-ZÁÉÍÓÚÑ][^\n]{2,80}[^.:;,\n])$")
SELECTORES_RUIDO = ("nav", "header", "footer", "aside", "script", "style", "noscript",
                    "form", "button", "svg", "iframe")
# Clases o ids de ruido, comparados como tokens completos: «wy-nav-content» (contenido
# de Sphinx/Godot) o «toc2» en el <body> de Asciidoctor (glTF) no son ruido.
CLASES_RUIDO = re.compile(
    r"^(?:nav|navbar|navigation|menu|menubar|sidebar|side-bar|sidenav|sphinxsidebar|wy-nav-side|"
    r"footer|site-footer|header|site-header|page-header|breadcrumbs?|toc|cookies?|cookie-banner|"
    r"related|skip-link)$", re.I)
CONTENEDORES = ("html", "body", "main", "article")


def detectar_licencia(texto: str) -> str | None:
    for patron, licencia in PATRONES_LICENCIA:
        if patron.search(texto):
            return licencia
    return None


def decodificar(contenido: bytes) -> str:
    """UTF-8 (con o sin BOM); si no lo es, Windows-1252 (textos latinos antiguos)."""
    try:
        return contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenido.decode("cp1252", "replace")


def _front_matter(texto: str) -> tuple[dict, str]:
    """Front matter YAML entre «---». Si el YAML es inválido (p. ej. «titulo: A: B» sin
    comillas) se lee como líneas «clave: valor». Sin «---» de cierre: error 422."""
    if not texto.startswith("---"):
        return {}, texto
    partes = texto[3:].split("\n---", 1)
    if len(partes) != 2:
        raise EntradaInvalida("El front matter del Markdown no tiene «---» de cierre.")
    bloque, cuerpo = partes
    try:
        meta = yaml.safe_load(bloque) or {}
    except yaml.YAMLError:
        meta = {}
        for linea in bloque.splitlines():
            if ":" in linea and not linea.startswith((" ", "-")):
                clave, valor = linea.split(":", 1)
                valor = valor.strip()
                if valor.startswith("[") and valor.endswith("]"):
                    valor = [v.strip(" '\"") for v in valor[1:-1].split(",") if v.strip()]
                meta[clave.strip()] = valor
    if not isinstance(meta, dict):
        meta = {}
    return meta, cuerpo.lstrip("-").lstrip("\n")


# Texto que el navegador no muestra: no se indexa (podría esconder instrucciones).
OCULTO = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)", re.I)


def _limpiar(texto: str) -> str:
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def _licencia_html(contenido: bytes) -> str | None:
    sopa = BeautifulSoup(contenido, "html.parser")
    for etiqueta in sopa.find_all("meta"):
        if (etiqueta.get("name") or "").lower() in ("license", "licencia", "dcterms.license"):
            return detectar_licencia(etiqueta.get("content") or "") or (etiqueta.get("content") or None)
    for enlace in sopa.find_all("a", rel=True) + sopa.find_all("link", rel=True):
        if "license" in [r.lower() for r in enlace.get("rel", [])]:
            return detectar_licencia((enlace.get("href") or "") + " " + enlace.get_text(" "))
    pie = sopa.find("footer") or sopa.find(attrs={"role": "contentinfo"})
    return detectar_licencia(pie.get_text(" ")) if pie else None


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
            # En Markdown la licencia se declara en el front matter (no en el cuerpo).
            meta, _ = _front_matter(decodificar(archivo.contenido))
            licencia = meta.get("licencia") or meta.get("license")
        elif formato == "html" and firma_ok:
            # En HTML: <meta name="license">, <link rel="license"> o el aviso del pie de página.
            licencia = _licencia_html(archivo.contenido[:400_000])
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
        paginas = [(pagina.extract_text() or "").splitlines() for pagina in lector.pages]
        # Encabezados y pies de página: líneas que se repiten en la mayoría de las páginas.
        frecuencia: dict[str, int] = {}
        for lineas in paginas:
            for linea in {x.strip() for x in lineas if x.strip()}:
                frecuencia[linea] = frecuencia.get(linea, 0) + 1
        repetidas = ({x for x, n in frecuencia.items() if n >= max(3, len(paginas) // 2)}
                     if len(paginas) >= 3 else set())
        for numero, lineas in enumerate(paginas, start=1):
            for linea in lineas:
                limpia = linea.strip()
                if limpia in repetidas:
                    continue
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
        for elemento in sopa.find_all(True):   # texto oculto: no se extrae ni se indexa
            if elemento.decomposed or elemento.attrs is None:
                continue
            if (elemento.has_attr("hidden") or elemento.get("aria-hidden") == "true"
                    or OCULTO.search(elemento.get("style") or "")):
                elemento.decompose()
        for elemento in sopa.find_all(attrs={"role": re.compile("navigation|banner|contentinfo")}):
            elemento.decompose()
        raiz = (sopa.find("main") or sopa.find(attrs={"role": "main"}) or sopa.find("article")
                or sopa.body or sopa)
        protegidos = {id(raiz)} | {id(p) for p in raiz.parents}
        for elemento in sopa.find_all(True):
            if (elemento.attrs is None or elemento.name in CONTENEDORES
                    or id(elemento) in protegidos or elemento.decomposed):
                continue
            tokens = list(elemento.get("class", []) or []) + [elemento.get("id") or ""]
            if any(CLASES_RUIDO.match(t) for t in tokens if t):
                elemento.decompose()
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
        texto = decodificar(archivo.contenido)
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


def listar_corpus(directorio: Path | str) -> list[tuple[ArchivoSubido, dict]]:
    """Documentos de un directorio del corpus con sus metadatos.

    ``fuentes.yaml`` (opcional) asigna a cada archivo ``doc_id``, ``titulo``,
    ``licencia`` y ``perfiles``; el front matter del Markdown también sirve.
    """
    directorio = Path(directorio)
    fuentes_yaml = directorio / "fuentes.yaml"
    fuentes = {}
    if fuentes_yaml.exists():
        fuentes = (yaml.safe_load(fuentes_yaml.read_text(encoding="utf-8")) or {}).get("documentos") or {}
    salida = []
    for ruta in sorted(directorio.rglob("*")):
        if ruta.is_file() and ruta.suffix.lower() in FORMATOS:
            meta = fuentes.get(ruta.name) or fuentes.get(str(ruta.relative_to(directorio))) or {}
            salida.append((ArchivoSubido(ruta.name, ruta.read_bytes()), dict(meta)))
    return salida
