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
    """Vértices a menos de ``distancia`` de otro en la malla sin procesar.

    Se cuantiza la posición (rejilla de lado ``distancia``). Si hay UV o
    normales, se incluyen en la clave: dos vértices en la misma posición con
    UV distintas son una costura legítima, no un duplicado.
    """
    if len(malla.vertices) == 0:
        return 0
    claves = [np.round(malla.vertices / distancia).astype(np.int64)]
    if malla.uv is not None:
        claves.append(np.round(malla.uv / 1e-6).astype(np.int64))
    if malla.normales is not None:
        claves.append(np.round(malla.normales / 1e-4).astype(np.int64))
    unicos = np.unique(np.hstack(claves), axis=0)
    return int(len(malla.vertices) - len(unicos))


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
        "caras_originales": len(malla.lados_por_cara) if malla.lados_por_cara is not None else None,
        "dimensiones": [round(float(x), 6) for x in extension],
        "dimension_max": round(float(extension.max()), 6),
        "unidad": perfil.unidad,
        "aristas_no_manifold": aristas_no_manifold(fusionada),
        "cerrada": cerrada,
        "tiene_uv": malla.uv is not None,
        "caras_degeneradas": int(np.count_nonzero(cruda.area_faces < area_min)),
        "normales_consistentes": consistente,
        "volumen_con_signo": None if volumen is None else round(volumen, 9),
        "normales_ok": consistente and (volumen is None or volumen > 0),
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

def _evaluar(verificacion: str, p: dict, m: dict, unidad: str):
    """Devuelve (falla, medido, limite_texto); falla=None si no es medible."""
    if verificacion == "V1":
        medido = m["pct_ngons"]
        limite = f"≤ {p.get('max_pct', 0)} %"
        return (None if medido == NO_MEDIBLE else medido > p.get("max_pct", 0)), medido, limite
    if verificacion == "V2":
        medido = m["pct_triangulos"]
        limite = f"≤ {p.get('max_pct', 10)} %"
        return (None if medido == NO_MEDIBLE else medido > p.get("max_pct", 10)), medido, limite
    if verificacion == "V3":
        return m["triangulos"] > p["max"], m["triangulos"], f"≤ {p['max']} triángulos"
    if verificacion == "V4":
        return m["aristas_no_manifold"] > p.get("max", 0), m["aristas_no_manifold"], f"{p.get('max', 0)}"
    if verificacion == "V5":
        return not m["cerrada"], m["cerrada"], "cerrada (watertight)"
    if verificacion == "V6":
        return not m["tiene_uv"], m["tiene_uv"], "UV presentes"
    if verificacion == "V7":
        d = m["dimension_max"]
        return (not p["min"] <= d <= p["max"]), d, f"{p['min']}–{p['max']} {unidad}"
    if verificacion == "V8":
        return m["caras_degeneradas"] > p.get("max", 0), m["caras_degeneradas"], f"{p.get('max', 0)}"
    if verificacion == "V9":
        return not m["normales_ok"], m["normales_ok"], "normales consistentes y hacia fuera"
    if verificacion == "V10":
        medido = m["vertices_duplicados"]
        return (None if medido == NO_MEDIBLE else medido > p.get("max", 0)), medido, f"{p.get('max', 0)}"
    if verificacion == "V11":
        mb = round(p["max_bytes"] / (1024 * 1024), 2)
        return m["tamano_bytes"] > p["max_bytes"], m["tamano_bytes"], f"≤ {mb:g} MB"
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
        falla, medido, limite = _evaluar(verificacion, regla.parametros, metricas, perfil.unidad)
        if falla is None:
            no_medibles.append(verificacion)
            hallazgos.append(Hallazgo(
                id=f"h-{verificacion}", verificacion=verificacion, tipo="no_medible",
                gravedad="informativo", medido=NO_MEDIBLE, limite=limite,
                descripcion=f"{descripcion}: no medible en {malla.formato.upper()}; "
                            "audita el archivo en OBJ para medirlo.",
                consulta=consulta, norma=regla.norma))
        elif falla:
            hallazgos.append(Hallazgo(
                id=f"h-{verificacion}", verificacion=verificacion, tipo=tipo,
                gravedad=regla.gravedad, medido=medido, limite=limite,
                descripcion=descripcion, consulta=consulta, norma=regla.norma))
    reales = [h for h in hallazgos if h.tipo != "no_medible"]
    return ResultadoAnalisis(metricas=metricas, hallazgos=hallazgos,
                             semaforo=calcular_semaforo(reales), no_medibles=no_medibles)


class Analizador:
    """Herramienta ``analizar_malla`` lista para C2: lee con el puerto de C7 y mide."""

    version = VERSION_ANALIZADOR

    def __init__(self, lector: LectorMalla, catalogo: CatalogoPerfiles,
                 max_caras: int = MAX_CARAS):
        self.lector = lector
        self.catalogo = catalogo
        self.max_caras = max_caras

    def leer(self, ruta: Path) -> MallaCruda:
        return self.lector.leer(ruta)

    def analizar(self, ruta: Path | None, clave_perfil: str,
                 malla: MallaCruda | None = None) -> ResultadoAnalisis:
        perfil = self.catalogo.obtener(clave_perfil)
        if malla is None:
            malla = self.lector.leer(ruta)
        return analizar_malla(malla, perfil, self.max_caras)
