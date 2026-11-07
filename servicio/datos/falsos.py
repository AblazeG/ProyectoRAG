"""Dobles deterministas de los modelos (C7), para pruebas y para la nube.

- ``EmbeddingsFalsos``: hash de n-gramas normalizado (palabras con raíz
  truncada + 4-gramas de caracteres) con signo, proyectado a ``dimension``
  componentes y normalizado L2. Mismo texto, mismo vector; textos parecidos,
  vectores cercanos. Sirve para probar recuperación y caché semántica.
- ``ChatFalso``: devuelve JSON válido contra el esquema pedido y cita los ids
  de fragmento que recibió en el prompt. Puede inyectar fallas.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter

from servicio.dominio import (
    ErrorConexion,
    ErrorServidorModelo,
    ErrorTiempoLimite,
    Generacion,
    ModeloInexistente,
)

PALABRAS_VACIAS = set("""
a al algo ante antes como con contra cual cuando de del desde donde durante e el
ella ellas ellos en entre era es esa ese eso esta este esto estos estas fue ha
hay la las le les lo los mas me mi muy no nos o para pero por que se sea ser si
sin sobre son su sus tambien te tiene tu un una uno unos unas y ya cada debe
deben puede pueden hacer usa usar the of and or to in on for is are be by with
as an at it this that from can should must not if your you how what why which
como cómo qué cuál por qué mi mis
""".split())

SINONIMOS = {  # une términos ES/EN para que la recuperación falsa sea razonable
    "ngon": "ngon", "ngons": "ngon", "n-gon": "ngon", "n-gons": "ngon",
    "poligonos": "ngon", "poligono": "ngon",
    "manifold": "manifold", "variedad": "manifold",
    "normals": "normal", "normales": "normal", "normal": "normal",
    "vertices": "vertice", "vertex": "vertice", "vertice": "vertice",
    "duplicados": "duplic", "duplicate": "duplic", "duplicates": "duplic",
    "triangulos": "triang", "triangles": "triang", "triangulo": "triang",
    "triangulares": "triang", "triangular": "triang",
    "uvs": "uv", "uv": "uv", "texturas": "textur", "texture": "textur",
    "escala": "escal", "scale": "escal", "unidades": "unidad", "units": "unidad",
    "degeneradas": "degener", "degenerate": "degener", "degenerada": "degener",
    "cerrada": "cerrad", "watertight": "cerrad", "hermetica": "cerrad",
    "presupuesto": "presup", "budget": "presup",
}

PALABRAS_INYECCION = ("ignora", "ignore", "olvida", "forget", "system prompt",
                      "instrucciones anteriores", "previous instructions",
                      "jailbreak", "actua como", "act as", "revela", "reveal")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\s-]", " ", texto)


def _raiz(palabra: str) -> str:
    return SINONIMOS.get(palabra, palabra[:6])


def _indice(caracteristica: str, dimension: int) -> tuple[int, float]:
    digest = hashlib.md5(caracteristica.encode("utf-8")).digest()
    indice = int.from_bytes(digest[:4], "little") % dimension
    signo = 1.0 if digest[4] & 1 else -1.0
    return indice, signo


class EmbeddingsFalsos:
    """Puerto ``ModeloEmbeddings`` determinista."""

    def __init__(self, dimension: int = 512, nombre: str = "falso-ngramas-v1"):
        self.dimension = dimension
        self.nombre = nombre

    def _vector(self, texto: str) -> list[float]:
        palabras = [p for p in normalizar(texto).split()
                    if p not in PALABRAS_VACIAS and len(p) > 1]
        raices = Counter(_raiz(p) for p in palabras)
        vector = [0.0] * self.dimension
        for raiz, frecuencia in raices.items():
            peso = 1.0 + math.log(frecuencia)
            i, s = _indice("w:" + raiz, self.dimension)
            vector[i] += s * peso
            marcada = f"#{raiz}#"
            for j in range(max(1, len(marcada) - 3)):
                i, s = _indice("c:" + marcada[j:j + 4], self.dimension)
                vector[i] += s * peso * 0.25
        norma = math.sqrt(sum(v * v for v in vector))
        if norma == 0:
            vector[0] = 1.0
            return vector
        return [v / norma for v in vector]

    def vectorizar(self, textos: list[str], tipo: str) -> list[list[float]]:
        if tipo not in ("documento", "consulta"):
            raise ValueError("tipo debe ser 'documento' o 'consulta'")
        return [self._vector(t) for t in textos]


# ---------------------------------------------------------------------------
# Chat falso
# ---------------------------------------------------------------------------

RE_FRAGMENTO = re.compile(r'<fragmento id="([^"]+)"[^>]*>(.*?)</fragmento>', re.S)
RE_HALLAZGO = re.compile(r'<hallazgo id="([^"]+)" fragmentos="([^"]*)"[^>]*>', re.S)
RE_TEXTO = re.compile(r"<texto>(.*?)</texto>", re.S)
RE_CONSULTA = re.compile(r"<consulta>(.*?)</consulta>", re.S)

SINONIMOS_REFORMULACION = {
    "ngon": "n-gons polígonos de más de cuatro lados quads topología",
    "manifold": "non-manifold aristas compartidas geometría no manifold limpieza",
    "normal": "normales orientación recalcular normals flip",
    "uv": "coordenadas de textura UV unwrap desenvolvimiento",
    "escal": "escala unidades metros milímetros apply scale",
    "degener": "caras degeneradas área cero dissolve degenerate",
    "duplic": "vértices duplicados merge by distance fusionar",
    "triang": "triángulos presupuesto de polígonos triangle count",
    "cerrad": "malla cerrada watertight agujeros hermética",
}


def _oraciones(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?])\s+", " ".join(texto.split()))
    return [p.strip() for p in partes if len(p.strip()) > 10]


class ChatFalso:
    """Puerto ``ModeloChat`` determinista con inyección de fallas.

    ``falla``: None | "timeout" | "conexion" | "5xx" | "404" | "json_invalido"
    | "cita_falsa" | "cifra_falsa". ``fallas`` limita cuántas llamadas fallan
    (None = todas); después responde bien.
    """

    def __init__(self, nombre: str = "falso", falla: str | None = None,
                 fallas: int | None = None, demora_s: float = 0.0):
        self.nombre = nombre
        self.falla = falla
        self.fallas = fallas
        self.demora_s = demora_s
        self.llamadas: list[dict] = []

    def _debe_fallar(self) -> bool:
        if self.falla is None:
            return False
        if self.fallas is None:
            return True
        if self.fallas > 0:
            self.fallas -= 1
            return True
        return False

    def generar(self, mensajes: list[dict], esquema: dict | None,
                tiempo_limite_s: float) -> Generacion:
        self.llamadas.append({"mensajes": mensajes, "esquema": esquema,
                              "tiempo_limite_s": tiempo_limite_s})
        if self.demora_s:
            time.sleep(self.demora_s)
        falla = self.falla if self._debe_fallar() else None
        if falla == "timeout":
            raise ErrorTiempoLimite(f"timeout simulado en {self.nombre}")
        if falla == "conexion":
            raise ErrorConexion(f"conexión simulada caída en {self.nombre}")
        if falla == "5xx":
            raise ErrorServidorModelo("500 simulado")
        if falla == "404":
            raise ModeloInexistente(f"{self.nombre} no existe (simulado)")
        prompt = "\n".join(m.get("content", "") for m in mensajes if m.get("role") == "user")
        if falla == "json_invalido":
            texto = "esto no es JSON {"
        else:
            datos = self._responder(prompt, esquema or {})
            if falla == "cita_falsa":
                datos = self._contaminar(datos, cita=True)
            if falla == "cifra_falsa":
                datos = self._contaminar(datos, cita=False)
            texto = json.dumps(datos, ensure_ascii=False)
        return Generacion(texto=texto, modelo=self.nombre,
                          tokens_entrada=len(" ".join(m.get("content", "")
                                                      for m in mensajes).split()),
                          tokens_salida=len(texto.split()), duracion_ms=1.0)

    # -- respuestas por esquema -------------------------------------------
    def _responder(self, prompt: str, esquema: dict) -> dict:
        titulo = esquema.get("title", "")
        fragmentos = dict(RE_FRAGMENTO.findall(prompt))
        if titulo == "RespuestaExplicaciones":
            return {"hallazgos": [self._explicar(h, ids, fragmentos)
                                  for h, ids in RE_HALLAZGO.findall(prompt)]}
        if titulo == "RespuestaPreguntaModelo":
            if not fragmentos:
                return {"respuesta": "Sin norma aplicable en el corpus", "citas": []}
            id_, texto = next(iter(fragmentos.items()))
            oraciones = _oraciones(texto) or [texto.strip()]
            return {"respuesta": " ".join(f"{o} [{id_}]" for o in oraciones[:2]),
                    "citas": [id_]}
        if titulo == "ClasificacionInyeccion":
            texto = normalizar(" ".join(RE_TEXTO.findall(prompt)[-1:]) or prompt)
            return {"inyeccion": any(normalizar(p) in texto for p in PALABRAS_INYECCION)}
        if titulo == "Reformulacion":
            consulta = (RE_CONSULTA.findall(prompt) or [prompt])[-1].strip()
            raices = {_raiz(p) for p in normalizar(consulta).split()}
            extra = [v for k, v in SINONIMOS_REFORMULACION.items() if k in raices]
            return {"consulta": " ".join([consulta] + extra) if extra
                    else consulta + " norma técnica de modelado 3D"}
        return _instancia(esquema)

    @staticmethod
    def _explicar(hallazgo_id: str, ids: str, fragmentos: dict[str, str]) -> dict:
        citables = [i for i in ids.split(",") if i in fragmentos]
        if not citables:
            return {"id": hallazgo_id, "explicacion": "Sin norma aplicable en el corpus",
                    "correccion": [], "citas": []}
        principal = citables[0]
        oraciones = _oraciones(fragmentos[principal]) or [fragmentos[principal].strip()]
        explicacion = f"{oraciones[0]} [{principal}]"
        pasos = [f"{o} [{principal}]" for o in oraciones[1:3]] or [explicacion]
        return {"id": hallazgo_id, "explicacion": explicacion, "correccion": pasos,
                "citas": [principal]}

    @staticmethod
    def _contaminar(datos: dict, cita: bool) -> dict:
        extra = " [documento_inventado:seccion#99]" if cita else " La malla tiene 123457 caras."
        if "hallazgos" in datos:
            for h in datos["hallazgos"]:
                h["explicacion"] += extra
                if cita:
                    h["citas"].append("documento_inventado:seccion#99")
        elif "respuesta" in datos:
            datos["respuesta"] += extra
            if cita:
                datos["citas"].append("documento_inventado:seccion#99")
        return datos


def _instancia(esquema: dict) -> dict:
    """Instancia mínima válida para un esquema JSON desconocido."""
    valores = {"string": "", "integer": 0, "number": 0.0, "boolean": False,
               "array": [], "object": {}}
    return {k: valores.get(v.get("type"), None)
            for k, v in esquema.get("properties", {}).items()}


class SondaFalsa:
    def __init__(self, nombre: str, ok: bool = True):
        self.nombre = nombre
        self.ok = ok

    def comprobar(self) -> dict:
        return {"ok": self.ok, "proveedor": "falso"}
