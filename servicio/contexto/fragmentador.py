"""Fragmentación del corpus (C5): 800 caracteres con solape de 120, cortando
primero por sección y luego por párrafo."""
from __future__ import annotations

import re
import unicodedata

from servicio.dominio import DocumentoExtraido, Fragmento

TAM_FRAGMENTO = 800
SOLAPE = 120


def slug(texto: str, maximo: int | None = 60) -> str:
    """Identificador legible. Las secciones se truncan a 60 caracteres (su unicidad
    la garantiza ``fragmentar``); los ``doc_id`` no se truncan (``maximo=None``) para
    que dos documentos con nombres largos parecidos no se reemplacen entre sí."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return (texto[:maximo] if maximo else texto) or "seccion"


def _piezas(parrafo: str, tam: int) -> list[str]:
    """Divide un párrafo largo por oraciones y, si hace falta, por palabras."""
    if len(parrafo) <= tam:
        return [parrafo]
    piezas, actual = [], ""
    for oracion in re.split(r"(?<=[.!?;:])\s+", parrafo):
        while len(oracion) > tam:  # oración más larga que el fragmento
            corte = oracion.rfind(" ", 0, tam)
            corte = corte if corte > 0 else tam
            if actual:
                piezas.append(actual)
                actual = ""
            piezas.append(oracion[:corte].strip())
            oracion = oracion[corte:].strip()
        if actual and len(actual) + 1 + len(oracion) > tam:
            piezas.append(actual)
            actual = oracion
        else:
            actual = f"{actual} {oracion}".strip()
    if actual:
        piezas.append(actual)
    return piezas


def _cola(texto: str, solape: int) -> str:
    """Últimos ``solape`` caracteres, empezando en un límite de palabra."""
    if len(texto) <= solape:
        return texto
    cola = texto[-solape:]
    espacio = cola.find(" ")
    return cola[espacio + 1:] if 0 <= espacio < len(cola) - 1 else cola


def fragmentar_texto(texto: str, tam: int = TAM_FRAGMENTO, solape: int = SOLAPE) -> list[str]:
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    # Una pieza más la cola de solape y el separador «\n\n» nunca superan ``tam``.
    piezas = [x for p in parrafos for x in _piezas(" ".join(p.split()), tam - solape - 2)]
    fragmentos: list[str] = []
    actual = ""
    for pieza in piezas:
        if not actual:
            actual = pieza
        elif len(actual) + 2 + len(pieza) <= tam:
            actual = f"{actual}\n\n{pieza}"
        else:
            fragmentos.append(actual)
            actual = f"{_cola(actual, solape)}\n\n{pieza}"
    if actual:
        fragmentos.append(actual)
    return fragmentos


def fragmentar(documento: DocumentoExtraido, doc_id: str, licencia: str,
               perfiles: list[str], tam: int = TAM_FRAGMENTO,
               solape: int = SOLAPE) -> list[Fragmento]:
    """Fragmentos con id ``doc_id:seccion#n`` y sus metadatos."""
    fragmentos: list[Fragmento] = []
    usados: set[str] = set()
    for seccion in documento.secciones:
        base = slug(seccion.titulo)
        nombre, sufijo = base, 2
        while nombre in usados:  # dos secciones con el mismo título
            nombre, sufijo = f"{base}-{sufijo}", sufijo + 1
        usados.add(nombre)
        for n, texto in enumerate(fragmentar_texto(seccion.texto, tam, solape), start=1):
            fragmentos.append(Fragmento(
                id=f"{doc_id}:{nombre}#{n}", doc_id=doc_id, texto=texto,
                titulo=documento.titulo, seccion=seccion.titulo, pagina=seccion.pagina,
                formato=documento.formato, licencia=licencia, perfiles=list(perfiles)))
    return fragmentos


def texto_para_embedding(fragmento: Fragmento) -> str:
    """Se antepone la sección para que el vector capture el tema del fragmento."""
    return f"{fragmento.seccion}. {fragmento.texto}"
