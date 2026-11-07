"""Patrones de los guardrails (C3): inyección ES/EN, datos personales y cifras.

Los mensajes de rechazo nunca revelan cuál de estos patrones se detectó.
"""
from __future__ import annotations

import re

# -- E2: inyección de instrucciones (español e inglés) ----------------------
_I = re.IGNORECASE
INYECCION = [re.compile(p, _I) for p in (
    r"\bignora(r|d)?\s+(todas?\s+)?(las\s+|tus\s+|los\s+)?(instrucciones|reglas|indicaciones|[oó]rdenes)",
    r"\bignore\s+(all\s+|any\s+)?(the\s+|your\s+)?(previous|prior|above|earlier|preceding)?\s*(instructions|rules|prompts?)",
    r"\bolvida(r)?\s+(todo|todas?|tus|las)\s*(lo anterior|instrucciones|reglas)?",
    r"\bforget\s+(everything|all|your|the)\b.{0,30}\b(instructions|rules|above|said)",
    r"\b(revela|muestra|imprime|repite|dime)\s+(el|tu|tus|las)\s+(prompt|mensaje|instrucciones)\s*(del|de)?\s*(sistema|ocultas|iniciales)?",
    r"\b(reveal|show|print|repeat|leak)\s+(me\s+)?(the|your)\s+(system\s+)?(prompt|instructions)",
    r"\bsystem\s+prompt\b|\bprompt\s+del\s+sistema\b",
    r"\b(act[uú]a|comp[oó]rtate)\s+como\b|\bact\s+as\s+(an?|the)\b|\byou\s+are\s+now\b|\bahora\s+eres\b",
    r"\b(modo|mode)\s+(desarrollador|developer|dios|god|dan)\b|\bjailbreak\b|\bDAN\b",
    r"\bsin\s+(restricciones|filtros|l[ií]mites)\b|\bno\s+(restrictions|filters|limits)\b",
    r"\bdesactiva(r)?\s+(los\s+|tus\s+)?(filtros|guardrails|reglas|restricciones)",
    r"\b(disable|bypass|override)\s+(the\s+|your\s+|all\s+)?(filters|guardrails|rules|safety)",
    r"<\s*/?\s*(system|sistema|assistant|asistente)\s*>|\[/?INST\]|###\s*(system|instruction)",
    r"\bnuevas\s+instrucciones\s*:|\bnew\s+instructions\s*:",
)]


def detectar_inyeccion(texto: str) -> bool:
    return any(p.search(texto) for p in INYECCION)


# -- E3: datos personales ---------------------------------------------------
ESTADOS_CURP = ("AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|"
                "SL|SR|TC|TS|TL|VZ|YN|ZS|NE")
DATOS_PERSONALES = [
    ("[CORREO]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[CURP]", re.compile(
        r"\b[A-Z][AEIOUX][A-Z]{2}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[HM]"
        rf"(?:{ESTADOS_CURP})[B-DF-HJ-NP-TV-Z]{{3}}[A-Z\d]\d\b", _I)),
    ("[MATRICULA]", re.compile(r"\bmatr[ií]cula\s*(?:n[uú]m(?:ero)?\.?|no\.?)?\s*[:#]?\s*[A-Z0-9-]{5,12}\b", _I)),
    ("[MATRICULA]", re.compile(r"\b[Aa]0\d{7}\b")),
    ("[TELEFONO]", re.compile(
        r"(?<![\w.])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,3}\)|\d{2,3})[\s.-]?\d{3,4}[\s.-]?\d{4}(?![\w.])")),
]


def enmascarar(texto: str) -> tuple[str, int]:
    """Sustituye datos personales por etiquetas. Devuelve (texto, n)."""
    total = 0
    for etiqueta, patron in DATOS_PERSONALES:
        texto, n = patron.subn(etiqueta, texto)
        total += n
    return texto, total


# -- S2 / S3: citas y cifras ------------------------------------------------
CITA = re.compile(r"\[([A-Za-z0-9_\-]+:[^\[\]\s]+#\d+)\]")

UNIDADES = (r"%|mm|cm|km|m|MB|KB|GB|kB|px|°|grados|caras|triángulos|triangulos|"
            r"vértices|vertices|aristas|metros|milímetros|milimetros|segundos|s|ms")
CIFRA = re.compile(
    rf"(?<![\w.,#/])(\d{{1,3}}(?:[  ]\d{{3}})+|\d+(?:[.,]\d+)?)(?:\s?(?:{UNIDADES}))?(?![\w])")
NUMERACION_INICIAL = re.compile(r"^\s*(?:paso\s+)?\d+\s*[.):-]\s+", _I)
PASO = re.compile(r"\b(?:paso|step|punto|fase)\s+\d+\b", _I)
ORDINAL = re.compile(r"\b\d+\s?(?:\.º|º|ª|°(?=\s+(?:paso|lugar))|er|ero|ro|do|to|vo|no|st|nd|rd|th)\b", _I)


def valor_numerico(texto: str) -> float | None:
    limpio = re.sub(r"[  ]", "", texto).replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def cifras(texto: str) -> list[tuple[str, float]]:
    """Cifras relevantes (conteos, porcentajes y valores con unidad)."""
    sin_citas = CITA.sub(" ", texto)
    sin_numeracion = NUMERACION_INICIAL.sub(" ", sin_citas)
    sin_pasos = ORDINAL.sub(" ", PASO.sub(" ", sin_numeracion))
    encontradas = []
    for coincidencia in CIFRA.finditer(sin_pasos):
        valor = valor_numerico(coincidencia.group(1))
        if valor is not None:
            encontradas.append((coincidencia.group(0).strip(), valor))
    return encontradas


def oraciones(texto: str) -> list[str]:
    """Divide en oraciones sin separar la numeración de pasos («1. Haz…»)."""
    piezas = [o for o in re.split(r"(?<=[.!?])\s+", texto.strip()) if o]
    unidas: list[str] = []
    for pieza in piezas:
        if unidas and re.fullmatch(r"(?:paso\s+)?\d+[.)]", unidas[-1], re.IGNORECASE):
            unidas[-1] = f"{unidas[-1]} {pieza}"
        else:
            unidas.append(pieza)
    return unidas
