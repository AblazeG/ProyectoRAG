"""Prueba de arquitectura: analiza las importaciones con ``ast`` y falla ante
cualquier dependencia entre capas que el informe no permita."""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "servicio"

PERMITIDOS = {
    "api":          {"orquestacion"},
    "orquestacion": {"guardrails", "cache", "contexto", "modelos"},
    "guardrails":   {"modelos", "datos"},  # clasificador few-shot y embeddings
    "cache":        {"datos"},
    "contexto":     {"datos"},
    "modelos":      {"datos"},
    "datos":        set(),
}
TRANSVERSALES = {"dominio", "observabilidad", "retroalimentacion"}
# Raíces de composición: son los únicos módulos que conocen implementaciones.
RAICES_COMPOSICION = {"composicion", "ingestar"}

BIBLIOTECAS_DE_RECURSOS = {"httpx", "chromadb", "sqlite3"}


def _modulos():
    for ruta in sorted(RAIZ.rglob("*.py")):
        relativa = ruta.relative_to(RAIZ)
        capa = relativa.parts[0].removesuffix(".py")
        yield ruta, capa


def _importaciones(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres = []
    paquete = ".".join(("servicio",) + ruta.relative_to(RAIZ).parent.parts)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.extend(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:  # import relativo -> absoluto
                base = paquete.split(".")
                base = base[: len(base) - (nodo.level - 1)]
                modulo = ".".join(base + ([nodo.module] if nodo.module else []))
                if not nodo.module:
                    nombres.extend(f"{modulo}.{a.name}" for a in nodo.names)
                    continue
                nombres.append(modulo)
            else:
                nombres.append(nodo.module or "")
    return nombres


def _capa_destino(nombre: str) -> str | None:
    partes = nombre.split(".")
    if partes[0] != "servicio" or len(partes) < 2:
        return None
    return partes[1]


def test_dependencias_entre_capas():
    violaciones = []
    for ruta, capa in _modulos():
        if capa in RAICES_COMPOSICION or capa == "__init__":
            continue
        for nombre in _importaciones(ruta):
            destino = _capa_destino(nombre)
            if destino is None or destino == capa or destino in TRANSVERSALES:
                continue
            if capa in TRANSVERSALES:
                violaciones.append(f"{ruta.name}: transversal {capa} -> {destino}")
                continue
            if destino in RAICES_COMPOSICION:
                violaciones.append(f"{ruta}: {capa} importa la raíz de composición")
                continue
            if destino not in PERMITIDOS.get(capa, set()):
                violaciones.append(f"{ruta.relative_to(RAIZ)}: {capa} -> {destino}")
    assert not violaciones, "Dependencias no permitidas:\n" + "\n".join(violaciones)


def test_orquestacion_nunca_importa_datos():
    for ruta, capa in _modulos():
        if capa == "orquestacion":
            assert all(_capa_destino(n) != "datos" for n in _importaciones(ruta)), ruta


def test_solo_datos_toca_recursos():
    violaciones = []
    for ruta, capa in _modulos():
        if capa == "datos":
            continue
        for nombre in _importaciones(ruta):
            if nombre.split(".")[0] in BIBLIOTECAS_DE_RECURSOS:
                violaciones.append(f"{ruta.relative_to(RAIZ)} importa {nombre}")
    assert not violaciones, "\n".join(violaciones)


def test_trimesh_solo_en_lector_y_herramientas():
    permitidos = {RAIZ / "datos" / "mallas.py", RAIZ / "contexto" / "herramientas.py"}
    for ruta, _ in _modulos():
        if any(n.split(".")[0] == "trimesh" for n in _importaciones(ruta)):
            assert ruta in permitidos, f"{ruta} importa trimesh"


def test_sin_frameworks_que_oculten_capas():
    prohibidos = {"langchain", "llama_index", "llamaindex", "haystack"}
    for ruta, _ in _modulos():
        for nombre in _importaciones(ruta):
            assert nombre.split(".")[0] not in prohibidos, ruta


def test_fuera_de_datos_nadie_abre_mallas_ni_documentos():
    """Heurística: fuera de C7 no se llama a trimesh.load, pypdf ni BeautifulSoup."""
    prohibidos = ("trimesh.load", "PdfReader", "BeautifulSoup(")
    for ruta, capa in _modulos():
        if capa == "datos":
            continue
        texto = ruta.read_text(encoding="utf-8")
        for patron in prohibidos:
            assert patron not in texto, f"{ruta} usa {patron}"
