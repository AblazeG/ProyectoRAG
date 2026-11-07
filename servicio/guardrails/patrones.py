"""Patrones de los guardrails (C3): inyección ES/EN, datos personales y cifras.

Los mensajes de rechazo nunca revelan cuál de estos patrones se detectó.
"""
from __future__ import annotations

import re
import unicodedata

_I = re.IGNORECASE
_ANCHO_CERO = re.compile("[\u00ad\u200b-\u200f\u2060-\u2064\ufeff]")


def normalizar_texto(texto: str) -> str:
    """NFKC, sin caracteres de ancho cero y con espacios simples (evita evasiones triviales)."""
    texto = _ANCHO_CERO.sub("", unicodedata.normalize("NFKC", texto or ""))
    return re.sub(r"\s+", " ", texto)


# -- E2: inyección de instrucciones (español e inglés) ----------------------
# Cada patrón exige un objeto de instrucción («instrucciones», «prompt del sistema»,
# «a partir de ahora» + orden…), para no bloquear notas técnicas como «ignora las
# caras ocultas», «act as a mold», «sin restricciones de presupuesto» o «las UV dan…».
_ORDEN = (r"(?:responde\w*|contesta\w*|aprueba\w*|acepta\w*|di|dime|escribe\w*|eres|act[uú]a\w*|"
          r"revela\w*|mu[eé]stra\w*|imprime\w*|ignora\w*|olvida\w*|haz|marca\w*|answer|respond|"
          r"approve|say|write|reveal|print|act|ignore|forget|you)")
_INSTRUCCIONES_ES = (r"(?:instrucciones|indicaciones|[oó]rdenes|directrices|"
                     r"reglas\s+(?:anteriores|previas|del\s+sistema|de\s+seguridad)|"
                     r"(?:tus|sus)\s+reglas(?!\s+de\b))")
INYECCION = [re.compile(p, _I) for p in (
    # ignorar u olvidar instrucciones (ES)
    rf"\b(?:ignor\w*|omit\w*|descart\w*|haz(?:\s+caso)?\s+omiso\s+(?:de|a)|olv[ií]d\w*(?:\s+de)?)\s+"
    rf"(?:todas?\s+|todo\s+)?(?:las\s+|los\s+|tus\s+|sus\s+|mis\s+)?{_INSTRUCCIONES_ES}",
    rf"\b(?:ignor\w*|olv[ií]d\w*|haz\s+caso\s+omiso\s+de)\s+(?:todo\s+)?lo\s+(?:anterior|que\s+te\s+dijeron)"
    rf"\b.{{0,25}}\b{_ORDEN}\b",
    # ignorar u olvidar instrucciones (EN)
    r"\b(?:ignore|disregard|forget|override|skip)\s+(?:all\s+|any\s+|the\s+|your\s+|my\s+|of\s+)*"
    r"(?:previous|prior|above|earlier|preceding|system|initial|original|existing)?\s*"
    r"(?:instructions|directions|directives|prompts?|guidelines|rules(?!\s+of\b))",
    r"\bforget\s+(?:everything|all)\s+(?:above|before|you\s+(?:were|have\s+been)\s+told)",
    # revelar el prompt o las instrucciones
    r"\b(?:revela\w*|mu[eé]stra\w*|imprim\w*|repit\w*|dime|ens[eé][ñn]a\w*|escrib\w*)\s+"
    r"(?:tu|tus)\s+(?:prompt|instrucciones|reglas|indicaciones)",
    r"\b(?:revela\w*|mu[eé]stra\w*|imprim\w*|repit\w*|dime)\s+(?:el|las|los)\s+(?:prompt|mensaje|"
    r"instrucciones)\s+(?:del\s+sistema|de\s+sistema|ocult\w+|inicial\w*|secret\w+|intern\w+)",
    r"\b(?:reveal|show|print|repeat|leak|tell|output|display)\s+(?:me\s+)?"
    r"(?:your\s+(?:system\s+|initial\s+|hidden\s+|original\s+)?|the\s+(?:system|hidden|initial|original)\s+)"
    r"(?:prompt|instructions)",
    r"\bsystem\s+prompt\b|\bprompt\s+(?:del|de)\s+sistema\b",
    # cambio de rol
    r"\b(?:act[uú]a\w*|comp[oó]rtate|finge|simula)\s+(?:como|ser|que\s+eres)\s+(?:si\s+fueras\s+)?"
    r"(?:un|una|el|la)?\s*(?:asistente|ia|modelo|chatbot|bot|sistema|administrador|admin|hacker|"
    r"pirata|desarrollador|otro|otra|dan)\b",
    r"\b(?:act|behave)\s+as\s+(?:an?\s+|the\s+|if\s+you\s+were\s+)?(?:\w+\s+)?"
    r"(?:assistant|ai|model|chatbot|bot|system|admin(?:istrator)?|hacker|dan)\b",
    r"\b(?:act|behave)\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered|jailbroken|uncensored)\b",
    r"\byou\s+are\s+now\b|\bahora\s+eres\b",
    rf"\b(?:a\s+partir\s+de\s+ahora|de\s+ahora\s+en\s+adelante|from\s+now\s+on)\b.{{0,40}}\b{_ORDEN}\b",
    # modos y filtros
    r"\b(?:modo|mode)\s+(?:desarrollador|developer|dan|jailbreak|sin\s+restricciones|unrestricted)\b"
    r"|\bjailbreak\w*|(?-i:\bDAN\b)",
    r"\b(?:sin|without)\s+(?:restricciones|filtros|censura|restrictions|filters|censorship)\b"
    r"(?!\s+(?:de|on|for|en|para)\b)",
    r"\b(?:desactiva\w*|quita\w*|elimina\w*)\s+(?:los\s+|tus\s+|las\s+)?"
    r"(?:filtros|guardrails|restricciones|reglas\s+de\s+seguridad)",
    r"\b(?:disable|bypass|override|turn\s+off)\s+(?:the\s+|your\s+|all\s+)?"
    r"(?:filters|guardrails|safety|restrictions)",
    r"<\s*/?\s*(?:system|sistema|assistant|asistente)\s*>|\[/?INST\]|###\s*(?:system|instruction)",
    r"\bnuevas\s+instrucciones\s*:|\bnew\s+instructions\s*:",
)]


def detectar_inyeccion(texto: str) -> bool:
    limpio = normalizar_texto(texto)
    return any(p.search(limpio) for p in INYECCION)


# -- E3: datos personales ---------------------------------------------------
ESTADOS_CURP = ("AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|"
                "SL|SR|TC|TS|TL|VZ|YN|ZS|NE")
# Un número seguido de una unidad es una medición, no un teléfono.
_UNIDAD_SIGUE = (r"(?!\s*(?:mm|cm|km|m\b|metros|caras|tri|v[eé]rtices|vertices|aristas|pol[ií]gonos|"
                 r"quads|bytes|kb|mb|gb|px|p[ií]xeles|%|unidades|fps))")
_EXTENSIONES = ("png|jpe?g|gif|webp|bmp|tga|tiff?|exr|hdr|glb|gltf|obj|fbx|stl|ply|blend|usdz?|"
                "html?|md|pdf|txt|json|zip|bin|ktx2")
DATOS_PERSONALES = [
    ("[CORREO]", re.compile(
        rf"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?!(?:{_EXTENSIONES})\b)[A-Za-z]{{2,}}\b")),
    ("[CURP]", re.compile(
        r"\b[A-Z][AEIOUX][A-Z]{2}\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[HM]"
        rf"(?:{ESTADOS_CURP})[B-DF-HJ-NP-TV-Z]{{3}}[A-Z\d]\d\b", _I)),
    ("[MATRICULA]", re.compile(r"\bmatr[ií]cula\s*(?:n[uú]m(?:ero)?\.?|no\.?)?\s*[:#]?\s*[A-Z0-9-]{5,12}\b", _I)),
    ("[MATRICULA]", re.compile(r"\b[Aa]0\d{7}\b")),
    # Teléfono con prefijo explícito («tel», «cel», «WhatsApp»…), aunque no lleve separadores.
    ("[TELEFONO]", re.compile(
        r"(?i:\b(?:tel(?:[eé]fono)?|cel(?:ular)?|m[oó]vil|whats(?:app)?|phone|mobile)\.?\s*[:#]?\s*)"
        r"\+?\d[\d\s().-]{7,16}\d")),
    # Teléfono con separadores entre grupos (55 1234 5678, +52 (55) 1234-5678).
    ("[TELEFONO]", re.compile(
        r"(?<![\w.\-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,3}\)\s?|\d{2,3}[\s.-])\d{3,4}[\s.-]\d{4}"
        rf"(?![\w.\-]){_UNIDAD_SIGUE}")),
]


def enmascarar(texto: str) -> tuple[str, int]:
    """Sustituye datos personales por etiquetas. Devuelve (texto, n)."""
    total = 0
    for etiqueta, patron in DATOS_PERSONALES:
        texto, n = patron.subn(etiqueta, texto)
        total += n
    return texto, total


# -- S2: citas -------------------------------------------------------------
ID_FRAGMENTO = r"[A-Za-z0-9_.\-]+:[^\s\[\](),;]+#\d+"
CITA = re.compile(rf"\[\s*({ID_FRAGMENTO})\s*\]")
# Grupo de citas entre corchetes o paréntesis, con una o varias separadas por coma o punto y coma.
GRUPO_CITAS = re.compile(rf"[\[(]\s*({ID_FRAGMENTO}(?:\s*[,;]\s*{ID_FRAGMENTO})*)\s*[\])]")
ID_SUELTO = re.compile(rf"(?<![\w\[(:])({ID_FRAGMENTO})")

# -- S3: cifras ------------------------------------------------------------
# Tabla 13: «conteos, porcentajes y valores con unidad». Un número sin unidad ni
# sustantivo de conteo (versiones, años, secciones, «Blender 4.2») no se evalúa.
UNIDADES = (r"%|por\s*ciento|percent|mm|cm|km|m|metros?|mil[ií]metros?|cent[ií]metros?|in|pulgadas?|"
            r"MB|KB|GB|kB|bytes?|px|p[ií]xeles|°|grados|degrees|segundos?|s|ms|fps|Hz|"
            r"caras?|faces?|tri[aá]ngulos?|triangles?|tris|v[eé]rtices|vertex|vertices|aristas?|edges?|"
            r"pol[ií]gonos?|polygons?|quads?|n-?gons?|lados|sides|unidades|units|veces|times")
CIFRA = re.compile(
    rf"(?<![\w.,#/:])([-−]?(?:\d{{1,3}}(?:[  ]\d{{3}})+|\d+(?:[.,]\d+)?))\s?(?:{UNIDADES})(?![\w])"
    rf"|(?<![\w])[x×]\s?(\d+(?:[.,]\d+)?)(?![\w.,])", _I)
NUMERACION_INICIAL = re.compile(r"^\s*(?:paso\s+)?\d+\s*[.):-]\s+", _I)
PASO = re.compile(r"\b(?:paso|step|punto|fase)\s+\d+\b", _I)
ORDINAL = re.compile(r"\b\d+(?:\.º|\.ª|\.er|º|ª|er|ero|era|ro|ra|do|da|to|ta|vo|va|st|nd|rd|th)\b", _I)
NUMERO = re.compile(r"[-−]?(?:\d{1,3}(?:[  ]\d{3})+|\d+(?:[.,]\d+)?)")


def valor_numerico(texto: str) -> float | None:
    limpio = re.sub(r"[  ]", "", texto).replace(",", ".").replace("−", "-")
    try:
        return float(limpio)
    except ValueError:
        return None


def cifras(texto: str) -> list[tuple[str, float]]:
    """Cifras con unidad o sustantivo de conteo que S3 debe encontrar en los fragmentos."""
    sin_citas = GRUPO_CITAS.sub(" ", texto)
    sin_numeracion = NUMERACION_INICIAL.sub(" ", sin_citas)
    sin_pasos = ORDINAL.sub(" ", PASO.sub(" ", sin_numeracion))
    encontradas = []
    for coincidencia in CIFRA.finditer(sin_pasos):
        valor = valor_numerico(coincidencia.group(1) or coincidencia.group(2))
        if valor is not None:
            encontradas.append((coincidencia.group(0).strip(), valor))
    return encontradas


def valores_en(texto: str) -> set[float]:
    """Todos los valores numéricos de un fragmento (respaldo para S3)."""
    return {v for v in (valor_numerico(n) for n in NUMERO.findall(texto)) if v is not None}


# -- División en oraciones ---------------------------------------------------
_ABREVIATURA_FINAL = re.compile(
    r"(?:\b(?:sec|secc|p|pp|p[aá]g|fig|figs|ej|aprox|vs|n[uú]m|cap|art|ed|vol|etc|ver|cf|e\.g|i\.e)"
    r"|(?<![\w.])[A-Za-z])\.$", _I)


def oraciones(texto: str) -> list[str]:
    """Divide en oraciones sin separar la numeración de pasos («1. Haz…») ni las
    abreviaturas («sec. 4», «p. 12», «fig. 3», «Ej. 3»)."""
    piezas = [o for o in re.split(r"(?<=[.!?])\s+", texto.strip()) if o]
    unidas: list[str] = []
    for pieza in piezas:
        if unidas and (re.fullmatch(r"(?:paso\s+)?\d+[.)]", unidas[-1], re.IGNORECASE)
                       or _ABREVIATURA_FINAL.search(unidas[-1])):
            unidas[-1] = f"{unidas[-1]} {pieza}"
        else:
            unidas.append(pieza)
    return unidas
