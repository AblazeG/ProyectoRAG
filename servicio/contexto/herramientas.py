"""Analizador determinista de mallas (C5).

El modelo de lenguaje nunca mide la geometría: estas funciones calculan las
métricas V1–V11 sobre los arreglos de ``MallaCruda`` y producen hallazgos con
la gravedad del perfil. trimesh se usa solo como biblioteca de cálculo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh

from servicio.dominio import (
    Hallazgo,
    LectorMalla,
    MallaCruda,
    MallaDemasiadoCompleja,
)
from servicio.contexto.perfiles import UNIDADES, CatalogoPerfiles, Perfil

VERSION_ANALIZADOR = "1.0.0"
MAX_CARAS = 2_000_000
NO_MEDIBLE = "no medible"

# Descripción, tipo y consulta canónica de cada verificación (para el RAG).
VERIFICACIONES = {
    "V1": ("ngons", "Caras con más de cuatro lados (n-gons)",
           "n-gons caras con más de cuatro lados topología de quads para deformación"),
    "V2": ("triangulos_en_deformacion", "Proporción de triángulos en una malla de deformación",
           "triángulos en malla de deformación topología de quads animación"),
    "V3": ("presupuesto_triangulos", "Presupuesto de triángulos",
           "presupuesto de polígonos número de triángulos para tiempo real"),
    "V4": ("aristas_no_manifold", "Aristas no manifold (compartidas por más de dos caras)",
           "aristas no manifold compartidas por más de dos caras limpieza de geometría"),
    "V5": ("malla_abierta", "La malla no es cerrada (watertight)",
           "malla cerrada watertight agujeros para impresión 3D"),
    "V6": ("sin_uv", "La malla no tiene coordenadas UV por vértice",
           "coordenadas de textura UV desenvolvimiento"),
    "V7": ("escala", "Dimensión máxima fuera del rango esperado",
           "escala y unidades del modelo dimensiones aplicar escala"),
    "V8": ("caras_degeneradas", "Caras degeneradas (área casi nula)",
           "caras degeneradas con área cero disolver geometría degenerada"),
    "V9": ("normales", "Normales inconsistentes o invertidas",
           "orientación de normales invertidas recalcular normales"),
    "V10": ("vertices_duplicados", "Vértices duplicados",
            "vértices duplicados fusionar por distancia merge by distance"),
    "V11": ("tamano_archivo", "Tamaño de archivo excesivo",
            "tamaño de archivo para web compresión de modelos"),
}


@dataclass
class ResultadoAnalisis:
    metricas: dict
    hallazgos: list[Hallazgo]
    semaforo: str
    no_medibles: list[str] = field(default_factory=list)

    def contar(self) -> dict:
        cuenta = {"grave": 0, "menor": 0, "informativo": 0}
        for h in self.hallazgos:
            cuenta[h.gravedad] += 1
        return cuenta


def calcular_semaforo(hallazgos: list[Hallazgo]) -> str:
    """Rojo con al menos un grave; amarillo con solo menores; verde sin G ni M."""
    gravedades = {h.gravedad for h in hallazgos}
    if "grave" in gravedades:
        return "rojo"
    if "menor" in gravedades:
        return "amarillo"
    return "verde"


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def aristas_no_manifold(malla: trimesh.Trimesh) -> int:
    """Aristas compartidas por más de dos caras."""
    if len(malla.faces) == 0:
        return 0
    _, conteos = np.unique(malla.edges_sorted, axis=0, return_counts=True)
    return int(np.count_nonzero(conteos > 2))


def vertices_duplicados(malla: MallaCruda, distancia: float) -> int:
    """Vértices a menos de ``distancia`` (euclídea) de otro vértice anterior en la
    malla sin procesar, con los mismos atributos.

    Dos vértices en la misma posición con UV o normales distintas son una costura o
    una arista dura legítimas, no un duplicado. Para encontrar los pares sin un
    árbol KD se usan 8 rejillas de lado 2·d desplazadas d en cada eje: cualquier par
    a menos de d comparte celda en al menos una, y después se comprueba la
    distancia real (así no hay errores en los bordes de las celdas).
    """
    v = np.asarray(malla.vertices, dtype=float)
    if len(v) < 2:
        return 0
    lado = 2.0 * distancia
    duplicado = np.zeros(len(v), dtype=bool)
    for desplazamiento in np.array(np.meshgrid([0, 1], [0, 1], [0, 1])).T.reshape(-1, 3):
        celdas = np.floor((v + desplazamiento * distancia) / lado).astype(np.int64)
        _, inverso, cuenta = np.unique(celdas, axis=0, return_inverse=True, return_counts=True)
        inverso = inverso.reshape(-1)
        candidatos = np.flatnonzero(cuenta[inverso] > 1)
        if len(candidatos) == 0:
            continue
        orden = candidatos[np.argsort(inverso[candidatos], kind="stable")]
        grupos = np.split(orden, np.flatnonzero(np.diff(inverso[orden])) + 1)
        for grupo in grupos:
            for a, i in enumerate(grupo[:-1]):
                otros = grupo[a + 1:]
                cerca = np.linalg.norm(v[otros] - v[i], axis=1) < distancia
                if malla.uv is not None:
                    cerca &= np.all(np.abs(malla.uv[otros] - malla.uv[i]) < 1e-6, axis=1)
                if malla.normales is not None:
                    cerca &= np.all(np.abs(malla.normales[otros] - malla.normales[i]) < 1e-4, axis=1)
                duplicado[otros[cerca]] = True
    return int(np.count_nonzero(duplicado))


def componentes(caras: np.ndarray, n_vertices: int) -> np.ndarray:
    """Etiqueta de componente conexo de cada vértice (union-find vectorizado)."""
    padre = np.arange(n_vertices)
    aristas = np.vstack([caras[:, [0, 1]], caras[:, [1, 2]]])
    while True:
        pu, pv = padre[aristas[:, 0]], padre[aristas[:, 1]]
        distintos = pu != pv
        if not distintos.any():
            return padre
        np.minimum.at(padre, np.maximum(pu, pv)[distintos], np.minimum(pu, pv)[distintos])
        while True:  # compresión de caminos
            siguiente = padre[padre]
            if np.array_equal(siguiente, padre):
                break
            padre = siguiente


def normales_hacia_fuera(malla: trimesh.Trimesh) -> bool:
    """Cada componente cerrado debe tener volumen con signo > 0 (V9 por componente:
    un cuerpo pequeño invertido no se compensa con otro grande bien orientado)."""
    caras = np.asarray(malla.faces)
    if len(caras) == 0:
        return True
    etiqueta_vertice = componentes(caras, len(malla.vertices))
    etiqueta_cara = etiqueta_vertice[caras[:, 0]]
    v = np.asarray(malla.vertices)
    triple = np.einsum("ij,ij->i", v[caras[:, 0]], np.cross(v[caras[:, 1]], v[caras[:, 2]])) / 6.0
    volumen = np.zeros(len(v))
    np.add.at(volumen, etiqueta_cara, triple)
    aristas = np.sort(np.vstack([caras[:, [0, 1]], caras[:, [1, 2]], caras[:, [2, 0]]]), axis=1)
    _, inverso, cuenta = np.unique(aristas, axis=0, return_inverse=True, return_counts=True)
    abierta = np.zeros(len(v), dtype=bool)
    np.logical_or.at(abierta, np.tile(etiqueta_cara, 3), cuenta[inverso.reshape(-1)] != 2)
    cerrados = np.unique(etiqueta_cara)
    cerrados = cerrados[~abierta[cerrados]]
    return bool(np.all(volumen[cerrados] > 0))


def factor_unidad(malla: MallaCruda, perfil: Perfil) -> float:
    """GLB está en metros por especificación; OBJ, STL y PLY no declaran
    unidad y se interpretan en la unidad del perfil."""
    if malla.formato == "glb":
        return UNIDADES[perfil.unidad]
    return 1.0


def medir(malla: MallaCruda, perfil: Perfil) -> dict:
    reglas = perfil.reglas
    cruda = trimesh.Trimesh(vertices=malla.vertices, faces=malla.caras, process=False)
    fusionada = cruda.copy()
    fusionada.merge_vertices(merge_tex=True, merge_norm=True)

    area_min = reglas["V8"].parametros.get("area_min", 1e-10) if "V8" in reglas else 1e-10
    distancia = reglas["V10"].parametros.get("distancia", 1e-6) if "V10" in reglas else 1e-6

    cerrada = bool(fusionada.is_watertight)
    consistente = bool(fusionada.is_winding_consistent)
    volumen = float(fusionada.volume) if cerrada else None
    extension = (malla.vertices.max(axis=0) - malla.vertices.min(axis=0)) * factor_unidad(malla, perfil)

    metricas = {
        "formato": malla.formato,
        "tamano_bytes": int(malla.tamano_bytes),
        "vertices": int(len(malla.vertices)),
        "triangulos": int(len(malla.caras)),
        "caras": len(malla.lados_por_cara) if malla.lados_por_cara else int(len(malla.caras)),
        "dimensiones": [round(float(x), 6) for x in extension],
        "dimension_max": round(float(extension.max()), 6),
        "unidad": perfil.unidad,
        "aristas_no_manifold": aristas_no_manifold(fusionada),
        "cerrada": cerrada,
        "uv": malla.uv is not None,
        "caras_degeneradas": int(np.count_nonzero(cruda.area_faces < area_min)),
        "normales_consistentes": consistente,
        "volumen_con_signo": None if volumen is None else round(volumen, 9),
        "normales_ok": consistente and normales_hacia_fuera(fusionada),
    }
    if malla.lados_por_cara:
        lados = np.asarray(malla.lados_por_cara)
        metricas["pct_ngons"] = round(100.0 * np.count_nonzero(lados > 4) / len(lados), 4)
        metricas["pct_triangulos"] = round(100.0 * np.count_nonzero(lados == 3) / len(lados), 4)
    else:
        metricas["pct_ngons"] = NO_MEDIBLE
        metricas["pct_triangulos"] = NO_MEDIBLE
    # En STL cada faceta guarda sus propios vértices por definición del formato.
    metricas["vertices_duplicados"] = (NO_MEDIBLE if malla.formato == "stl"
                                       else vertices_duplicados(malla, distancia))
    return metricas


# ---------------------------------------------------------------------------
# Reglas -> hallazgos
# ---------------------------------------------------------------------------

def _n(valor: float) -> str:
    return f"{round(float(valor), 4):g}"


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _cota(maximo, unidad: str = "") -> str:
    texto = _n(maximo) if maximo == 0 else f"≤ {_n(maximo)}"
    return f"{texto} {unidad}".strip()


def _evaluar(verificacion: str, p: dict, m: dict, unidad: str):
    """Devuelve (falla, valor, medido, limite); falla=None si no es medible.

    ``medido`` y ``limite`` son texto con unidad, como en el Código 8 del informe.
    """
    if verificacion in ("V1", "V2"):
        clave = "pct_ngons" if verificacion == "V1" else "pct_triangulos"
        maximo = p.get("max_pct", 0 if verificacion == "V1" else 10)
        valor = m[clave]
        if valor == NO_MEDIBLE:
            return None, None, NO_MEDIBLE, _cota(maximo, "%")
        return valor > maximo, valor, f"{round(valor, 1):g} %", _cota(maximo, "%")
    if verificacion == "V3":
        n = m["triangulos"]
        return n > p["max"], n, _plural(n, "triángulo", "triángulos"), _cota(p["max"], "triángulos")
    if verificacion == "V4":
        n = m["aristas_no_manifold"]
        return n > p.get("max", 0), n, _plural(n, "arista", "aristas"), _cota(p.get("max", 0))
    if verificacion == "V5":
        return (not m["cerrada"], m["cerrada"], "cerrada" if m["cerrada"] else "abierta",
                "cerrada (watertight)")
    if verificacion == "V6":
        return not m["uv"], m["uv"], "con UV" if m["uv"] else "sin UV", "UV por vértice"
    if verificacion == "V7":
        d = m["dimension_max"]
        return (not p["min"] <= d <= p["max"]), d, f"{_n(d)} {unidad}", \
            f"{_n(p['min'])}–{_n(p['max'])} {unidad}"
    if verificacion == "V8":
        n = m["caras_degeneradas"]
        return n > p.get("max", 0), n, _plural(n, "cara", "caras"), _cota(p.get("max", 0))
    if verificacion == "V9":
        if m["normales_ok"]:
            medido = "consistentes"
        elif not m["normales_consistentes"]:
            medido = "inconsistentes"
        else:
            medido = "invertidas (volumen negativo)"
        return not m["normales_ok"], m["normales_ok"], medido, "consistentes y hacia fuera"
    if verificacion == "V10":
        n = m["vertices_duplicados"]
        if n == NO_MEDIBLE:
            return None, None, NO_MEDIBLE, _cota(p.get("max", 0))
        return n > p.get("max", 0), n, _plural(n, "vértice", "vértices"), _cota(p.get("max", 0))
    if verificacion == "V11":
        mb = m["tamano_bytes"] / (1024 * 1024)
        return (m["tamano_bytes"] > p["max_bytes"], m["tamano_bytes"], f"{mb:.2f} MB",
                _cota(p["max_bytes"] / (1024 * 1024), "MB"))
    raise ValueError(verificacion)


def analizar_malla(malla: MallaCruda, perfil: Perfil,
                   max_caras: int = MAX_CARAS) -> ResultadoAnalisis:
    """Métricas y hallazgos de una malla para un perfil."""
    if len(malla.caras) > max_caras or (malla.lados_por_cara and len(malla.lados_por_cara) > max_caras):
        raise MallaDemasiadoCompleja()
    metricas = medir(malla, perfil)
    hallazgos: list[Hallazgo] = []
    no_medibles: list[str] = []
    for verificacion in sorted(perfil.reglas, key=lambda v: int(v[1:])):
        regla = perfil.reglas[verificacion]
        tipo, descripcion, consulta = VERIFICACIONES[verificacion]
        falla, valor, medido, limite = _evaluar(verificacion, regla.parametros, metricas,
                                                perfil.unidad)
        if falla is None:
            no_medibles.append(verificacion)
            hallazgos.append(Hallazgo(
                id="", verificacion=verificacion, tipo="no_medible",
                gravedad="informativo", medido=NO_MEDIBLE, limite=limite,
                descripcion=f"{descripcion}: no medible en {malla.formato.upper()}; "
                            "audita el archivo en OBJ para medirlo.",
                consulta=consulta, norma=regla.norma))
        elif falla:
            hallazgos.append(Hallazgo(
                id="", verificacion=verificacion, tipo=tipo,
                gravedad=regla.gravedad, medido=medido, limite=limite,
                descripcion=descripcion, consulta=consulta, norma=regla.norma, valor=valor))
    orden = {"grave": 0, "menor": 1, "informativo": 2}
    hallazgos.sort(key=lambda h: (orden[h.gravedad], int(h.verificacion[1:])))
    for numero, h in enumerate(hallazgos, start=1):  # "h1", "h2", … (Código 8)
        h.id = f"h{numero}"
    reales = [h for h in hallazgos if h.tipo != "no_medible"]
    return ResultadoAnalisis(metricas=metricas, hallazgos=hallazgos,
                             semaforo=calcular_semaforo(reales), no_medibles=no_medibles)


class Analizador:
    """Herramienta ``analizar_malla`` de C5: lee con el puerto de C7 (``LectorTrimesh``)
    y devuelve (métricas, hallazgos)."""

    version = VERSION_ANALIZADOR

    def __init__(self, lector: LectorMalla, catalogo: CatalogoPerfiles,
                 max_caras: int = MAX_CARAS):
        self.lector = lector
        self.catalogo = catalogo
        self.max_caras = max_caras

    def leer(self, ruta: Path) -> MallaCruda:
        return self.lector.leer(ruta)

    def analizar_malla(self, ruta: Path | None, clave_perfil: str,
                       malla: MallaCruda | None = None) -> ResultadoAnalisis:
        perfil = self.catalogo.obtener(clave_perfil)
        if malla is None:
            malla = self.lector.leer(ruta)
        return analizar_malla(malla, perfil, self.max_caras)
