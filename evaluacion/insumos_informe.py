"""Insumos para completar el informe técnico a partir de los resultados medidos.

Lee los CSV que escriben ``run_eval.py`` y los experimentos, y el corpus, y genera:

- ``INSUMOS_INFORME.md``: un apartado por cada «[Pendiente]» del informe, con el texto
  propuesto, y todas las tablas con «?» ya llenas (tablas 2, 8, 9 y 16–23), más el
  estado de cada meta de la tabla 5.
- ``tablas_informe.tex``: las filas de esas tablas en LaTeX (``a & b \\\\``), para pegarlas
  dentro de los ``tabular`` del informe.

Lo que no sale de un CSV (nombre del docente, prueba con el revisor independiente,
versión del manual de Blender) queda marcado «DATO MANUAL». Si la corrida fue con el
proveedor falso, todo el documento se marca como PROVISIONAL.

    python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion.comun import RAIZ, RESULTADOS  # noqa: E402

MANUAL = "**DATO MANUAL**"
FALTA = "—"

# Metas de la tabla 5 del informe
META_RECALL = META_PRECISION = 0.95
META_ACIERTO5 = 0.85
META_FIDELIDAD = 4.0
META_S2_PCT = 5.0
META_SEGURIDAD_PCT, META_FP_PCT = 90.0, 10.0
META_RAPIDA_S, META_COMPLETA_S, META_EXACTA_MS = 15.0, 45.0, 300.0
META_MEMORIA_GB = 40.0

# Fuentes de la tabla 2, por prefijo del doc_id
FUENTES = [("blender", "Blender Manual"), ("godot", "Documentación de Godot Engine"),
           ("gltf", "Especificación glTF 2.0"), ("guia", "Guía de entrega (autor)"),
           ("rubrica", "Rúbrica de animación (autor)")]
CARACTERES_POR_PAGINA = 3000   # para expresar HTML y Markdown en «páginas equivalentes»


# -- lectura -------------------------------------------------------------------------
def leer(directorio: Path, nombre: str) -> list[dict]:
    ruta = directorio / nombre
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def num(valor) -> float | None:
    if valor in (None, "", "–", "-", "None"):
        return None
    try:
        return float(str(valor).replace("%", "").strip())
    except ValueError:
        return None


def lista(valor) -> list:
    try:
        return json.loads(valor) if valor else []
    except (TypeError, json.JSONDecodeError):
        return []


def fmt(valor, decimales: int = 2, sufijo: str = "") -> str:
    v = num(valor) if not isinstance(valor, (int, float)) else valor
    if v is None:
        return FALTA
    if float(v).is_integer() and decimales <= 2 and abs(v) >= 10:
        return f"{int(v)}{sufijo}"
    return f"{v:.{decimales}f}{sufijo}"


def por_metrica(filas: list[dict], clave: str = "metrica") -> dict[str, dict]:
    return {f[clave]: f for f in filas}


def p95(valores: list[float]) -> float | None:
    return float(np.percentile(valores, 95)) if valores else None


def version_de(paquete: str) -> str:
    try:
        return version(paquete)
    except PackageNotFoundError:
        return MANUAL


# -- corpus (tabla 2 y número de fragmentos) -----------------------------------------
def resumen_corpus(directorio: Path) -> dict:
    """Fragmenta el corpus con los parámetros del servicio (sin embeddings) y cuenta
    documentos, páginas y fragmentos por fuente."""
    from servicio.composicion import cargar_config
    from servicio.contexto.recuperador import Indice
    from servicio.datos.documentos import LectorDocumentos, listar_corpus
    from servicio.datos.sqlite import BaseSQLite, RepositorioDocumentosSQLite, RepositorioManifiestoSQLite

    rag = cargar_config()["rag"]
    base = BaseSQLite(":memory:")
    indice = Indice(None, None, RepositorioManifiestoSQLite(base), RepositorioDocumentosSQLite(base),
                    LectorDocumentos(), rag["tam_fragmento"], rag["solape"])
    fuentes: dict[str, dict] = {}
    total_fragmentos, errores = 0, []
    for archivo, meta in listar_corpus(directorio):
        try:
            documento, fragmentos, registro = indice.extraer_y_fragmentar(
                archivo, meta.get("licencia") or "propio", meta.get("doc_id"),
                meta.get("perfiles"), meta.get("titulo"))
        except Exception as exc:  # noqa: BLE001  (se informa, no detiene el resumen)
            errores.append(f"{archivo.nombre}: {exc}")
            continue
        doc_id = registro["doc_id"]
        clave = next((p for p, _ in FUENTES if doc_id.startswith(p)), "otros")
        f = fuentes.setdefault(clave, {"docs": 0, "paginas_pdf": 0, "caracteres": 0, "fragmentos": 0,
                                       "formatos": set(), "licencias": set(), "versiones": set()})
        f["docs"] += 1
        f["fragmentos"] += len(fragmentos)
        f["formatos"].add({"md": "Markdown", "markdown": "Markdown", "html": "HTML", "htm": "HTML",
                           "pdf": "PDF"}.get(documento.formato.lower(), documento.formato))
        f["licencias"].add(meta.get("licencia") or (documento.metadatos or {}).get("licencia") or "?")
        if meta.get("version"):
            f["versiones"].add(str(meta["version"]))
        paginas = {s.pagina for s in documento.secciones if getattr(s, "pagina", None)}
        if documento.formato == "pdf" and paginas:
            f["paginas_pdf"] += len(paginas)
        else:   # páginas equivalentes, al menos una por documento
            f["caracteres"] += len(documento.texto)
            f["paginas_equivalentes"] = f.get("paginas_equivalentes", 0) + max(
                1, math.ceil(len(documento.texto) / CARACTERES_POR_PAGINA))
        total_fragmentos += len(fragmentos)
    for f in fuentes.values():
        f["paginas"] = f["paginas_pdf"] + f.get("paginas_equivalentes", 0)
    return {"fuentes": fuentes, "fragmentos": total_fragmentos, "errores": errores,
            "tam": rag["tam_fragmento"], "solape": rag["solape"]}


# -- métricas derivadas --------------------------------------------------------------
class Resultados:
    def __init__(self, d: Path):
        self.d = d
        self.corrida = json.loads((d / "ultima_corrida.json").read_text()) if (d / "ultima_corrida.json").exists() else {}
        self.t08 = leer(d, "tabla08_llm.csv")
        self.t09 = leer(d, "tabla09_embeddings.csv")
        self.t16 = por_metrica(leer(d, "tabla16_producto.csv"))
        self.t16c = leer(d, "tabla16_casos.csv")
        self.t17 = leer(d, "tabla17_fragmentos.csv")
        self.t18 = leer(d, "tabla18_barrido.csv")
        self.t19 = por_metrica(leer(d, "tabla19_guardrails.csv"), "entrada")
        self.t19c = leer(d, "tabla19_casos.csv")
        self.t20 = por_metrica(leer(d, "tabla20_agente.csv"))
        self.t20c = leer(d, "tabla20_casos.csv")
        self.t21 = leer(d, "tabla21_enrutador.csv")
        self.t21c = leer(d, "tabla21_casos.csv")
        self.t22 = leer(d, "tabla22_cache.csv")
        self.t22c = leer(d, "tabla22_casos.csv")
        self.t23 = por_metrica(leer(d, "tabla23_latencias.csv"), "etapa")
        self.fallas = [f for f in leer(d, "fallas.csv") if f.get("caso") != "RESUMEN"]
        self.privacidad = leer(d, "privacidad.csv")
        self.retro = leer(d, "retroalimentacion.csv")
        self.juez_autor = (leer(d, "juez_autor.csv") or [{}])[0]

    @property
    def provisional(self) -> bool:
        return self.corrida.get("proveedor", "falso") != "ollama"

    def m16(self, metrica: str, columna: str = "con_rag") -> float | None:
        return num(self.t16.get(metrica, {}).get(columna))

    def latencias_por_ruta(self) -> dict[str, dict]:
        """Latencia total por auditoría según la ruta que tomó (tabla 21, caché desactivada)."""
        salida = {}
        for ruta in ("sin_modelo", "rapida", "completa"):
            v = [num(c["latencia_s"]) for c in self.t21c if c.get("ruta") == ruta and num(c.get("latencia_s")) is not None]
            salida[ruta] = {"n": len(v), "p50": statistics.median(v) if v else None, "p95": p95(v)}
        return salida

    def seguridad(self) -> tuple[float | None, float | None]:
        total = self.t19.get("Total", {})
        return num(total.get("correctos")), num(total.get("falsos_positivos"))

    def fallas_resumen(self) -> tuple[int, int, int]:
        e500 = sum(f.get("error_500") == "True" for f in self.fallas)
        respaldo = sum(f.get("terminada_con_respaldo") == "True" for f in self.fallas)
        return e500, respaldo, len(self.fallas)

    def privacidad_total(self) -> int | None:
        v = [num(p["datos_personales"]) for p in self.privacidad]
        return int(sum(x for x in v if x is not None)) if v else None

    def exacta(self) -> dict:
        fila = next((f for f in self.t22 if str(f.get("umbral", "")).startswith("Exacta")), {})
        return {"recall": num(fila.get("recall")), "precision": num(fila.get("precision")),
                "p95_ms": num(fila.get("auditoria_exacta_p95_ms"))}

    def acierto5(self) -> float | None:
        return self.m16("Acierto@5 de la sección esperada")

    def fidelidad(self) -> float | None:
        return self.m16("Fidelidad al contexto (0–5)")

    def retro_resumen(self) -> tuple[int, float | None]:
        utiles = [r.get("util") == "True" for r in self.retro]
        return len(utiles), (100 * sum(utiles) / len(utiles) if utiles else None)


# -- textos --------------------------------------------------------------------------
def estado(cumple: bool | None) -> str:
    return {True: "Cumple", False: "No cumple", None: "Sin dato"}[cumple]


def comparar(valor, meta, mayor_es_mejor=True) -> bool | None:
    if valor is None:
        return None
    return valor >= meta if mayor_es_mejor else valor <= meta


def tabla_md(encabezado: list[str], filas: list[list]) -> str:
    lineas = ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    lineas += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(lineas)


def tabla_tex(nombre: str, filas: list[list]) -> str:
    def esc(c):
        return (str(c).replace("\\", "\\textbackslash{}").replace("%", "\\%").replace("&", "\\&")
                .replace("_", "\\_").replace("#", "\\#").replace("—", "--").replace("≤", "$\\le$"))
    cuerpo = "\n".join(" & ".join(esc(c) for c in f) + r" \\" for f in filas)
    return f"% {nombre}\n{cuerpo}\n"


def conclusion_seleccion(r: Resultados) -> str:
    """Texto de la sección 6.4.1 según las reglas de ADR-01, ADR-02 y ADR-04."""
    modelos = {f["modelo"]: f for f in r.t08}
    calidad = {m: num(f.get("calidad")) for m, f in modelos.items()}
    lat95 = {m: num(f.get("latencia_p95_s")) for m, f in modelos.items()}
    partes = []
    if not modelos:
        return "Falta `tabla08_llm.csv`: corre `experimento_llm --juez`."
    if all(v is None for v in calidad.values()):
        partes.append("La tabla 8 no tiene calidad (la corrida fue sin `--juez`), así que la elección de "
                      "modelos de lenguaje no puede justificarse todavía; se mantiene la propuesta del ADR-01.")
        rapido, completo = "gemma4:e2b", "gpt-oss:20b"
    else:
        rapido = "gemma4:e2b"
        q, g = calidad.get("qwen3:8b"), calidad.get("gemma4:e2b")
        if q is not None and g is not None and q > g and (lat95.get("qwen3:8b") or 1e9) <= META_RAPIDA_S:
            rapido = "qwen3:8b"
        aptos = [m for m in modelos if calidad[m] is not None and (lat95[m] or 1e9) <= META_COMPLETA_S and m != rapido]
        completo = max(aptos, key=lambda m: calidad[m]) if aptos else "gpt-oss:20b"
        partes.append(
            f"La ruta rápida usa **{rapido}** (calidad {fmt(calidad.get(rapido))}, p95 {fmt(lat95.get(rapido))} s) "
            f"y la completa **{completo}** (calidad {fmt(calidad.get(completo))}, p95 {fmt(lat95.get(completo))} s); "
            "cada uno es el respaldo del otro.")
        if calidad.get(rapido) is not None and calidad.get(completo) is not None:
            dif = calidad[completo] - calidad[rapido]
            partes.append(
                f"Se sacrifican {fmt(dif)} puntos de calidad en los casos simples a cambio de "
                f"{fmt((lat95.get(completo) or 0) - (lat95.get(rapido) or 0))} s menos de p95; el compromiso es "
                "adecuado porque esos casos tienen hasta tres hallazgos menores y una explicación corta, y las "
                "cifras del informe no dependen del modelo (ADR-08).")
        memoria = [num(modelos[m].get("memoria_gb")) for m in {rapido, completo}]
        if all(v is not None for v in memoria):
            partes.append(f"Juntos ocupan {fmt(sum(memoria), 1)} GB (meta ≤ {META_MEMORIA_GB:g} GB).")
    emb = {f["modelo"]: f for f in r.t09}
    if emb:
        a5 = {m: num(f.get("acierto_5")) for m, f in emb.items()}
        elegido = "bge-m3"
        if (a5.get("embeddinggemma") is not None and a5.get("bge-m3") is not None
                and a5["embeddinggemma"] >= a5["bge-m3"]):
            elegido = "embeddinggemma"   # ADR-02: alternativa si iguala el acierto@5
        partes.append(
            f"Para los embeddings se adopta **{elegido}** (acierto@5 {fmt(a5.get(elegido))}, "
            f"MRR {fmt(num(emb[elegido].get('mrr')))}); "
            + ("embeddinggemma iguala a bge-m3 y es más ligero, que es la condición del ADR-02 para preferirlo."
               if elegido == "embeddinggemma" else
               "nomic-embed-text, centrado en inglés, queda "
               f"en {fmt(a5.get('nomic-embed-text'))} con consultas en español."))
    return " ".join(partes)


def analisis_errores(r: Resultados) -> list[str]:
    puntos = []
    # Analizador
    no_det, falsos = {}, {}
    for c in r.t16c:
        for v in lista(c.get("no_detectadas")):
            no_det.setdefault(v, []).append(c["caso"])
        for v in lista(c.get("falsos")):
            falsos.setdefault(v, []).append(c["caso"])
    semaforos = [c for c in r.t16c if c.get("semaforo") and c["semaforo"] != c.get("semaforo_esperado")]
    if no_det or falsos or semaforos:
        texto = "**Analizador.** "
        if no_det:
            texto += "No detectados: " + "; ".join(f"{v} en {', '.join(cs)}" for v, cs in sorted(no_det.items())) + ". "
        if falsos:
            texto += "Falsos: " + "; ".join(f"{v} en {', '.join(cs)}" for v, cs in sorted(falsos.items())) + ". "
        if semaforos:
            texto += f"Semáforo distinto del esperado en {', '.join(c['caso'] for c in semaforos)}."
        puntos.append(texto)
    else:
        puntos.append(f"**Analizador.** Sin hallazgos no detectados ni falsos en los {len(r.t16c)} casos.")
    # Sin norma
    sin_norma = sum(int(num(c.get("sin_norma")) or 0) for c in r.t16c)
    s2 = r.m16("Citas inventadas detectadas por S2 (% de las citas)")
    a5 = r.acierto5()
    if sin_norma:
        causa = ("la recuperación (acierto@5 de la sección esperada = " + fmt(a5) + ")") if a5 is not None and a5 < META_ACIERTO5 \
            else "el modelo, porque la recuperación sí encuentra la sección esperada"
        puntos.append(f"**Sin norma.** {sin_norma} hallazgos terminaron «sin norma aplicable»; la causa más "
                      f"probable es {causa}. Citas eliminadas por S2: {fmt(s2, 1, ' %')} de las citas generadas.")
    # Caché semántica
    fp = [c for c in r.t22c if c.get("tipo") == "distractor" and c.get("cache") == "semantica"]
    if fp:
        por_umbral = {}
        for c in fp:
            por_umbral.setdefault(c["umbral"], []).append(c)
        texto = "**Caché semántica.** Aciertos equivocados (distractores servidos): " + "; ".join(
            f"umbral {u}: " + ", ".join(f"«{c['pregunta'][:60]}» ({fmt(num(c.get('similitud')), 3)})" for c in cs)
            for u, cs in sorted(por_umbral.items())) + "."
        puntos.append(texto)
    # Guardrails
    fallidos = [c for c in r.t19c if c.get("correcto") == "False"]
    fps = [c for c in r.t19c if c.get("falso_positivo") == "True"]
    if fallidos or fps:
        texto = "**Guardrails.** "
        if fallidos:
            texto += "Mal manejados: " + ", ".join(f"{c['caso']} ({c['categoria']}, código {c['codigo']})" for c in fallidos) + ". "
        if fps:
            texto += "Falsos positivos: " + ", ".join(f"{c['caso']} (activó {', '.join(lista(c.get('activaciones'))) or c['codigo']})" for c in fps) + "."
        puntos.append(texto)
    else:
        puntos.append("**Guardrails.** Ninguna entrada problemática mal manejada ni falsos positivos.")
    # Enrutador
    mal = [c for c in r.t21c if c.get("adecuada") == "False" and c.get("ruta_esperada") != "sin_etiqueta"]
    if mal:
        puntos.append("**Enrutador.** Ruta equivocada en " + ", ".join(
            f"{c['caso']} (esperada {c['ruta_esperada']}, tomó {c['ruta']})" for c in mal) + ".")
    sin_etiqueta = [c for c in r.t21c if c.get("ruta_esperada") == "sin_etiqueta"]
    if sin_etiqueta:
        puntos.append(f"**Enrutador.** {len(sin_etiqueta)} casos quedaron sin etiqueta (nada que calificar).")
    if r.t21c and all(c.get("etiquetada_por") == "regla" or c.get("ruta_esperada") == "sin_modelo" for c in r.t21c):
        puntos.append("**Enrutador.** Sin juez, la ruta esperada salió de la misma regla: la tabla 21 es circular.")
    # Agente
    pobres = [c for c in r.t20c if c.get("inicial_suficiente") == "False"]
    if pobres:
        mejoran = sum(c.get("supera_tras_reformular") == "True" for c in pobres)
        incorrecta = [c["caso"] for c in pobres if c.get("supera_tras_reformular") == "True" and c.get("fuente_correcta") == "False"]
        texto = f"**Agente.** De {len(pobres)} consultas con recuperación pobre, {mejoran} superan el umbral tras reformular."
        if incorrecta:
            texto += f" Superan el umbral pero citan otra sección: {', '.join(incorrecta)}."
        puntos.append(texto)
    # Latencias atípicas
    tiempos = [(num(c.get("tiempo_ms")), c["caso"]) for c in r.t16c if num(c.get("tiempo_ms")) is not None]
    if len(tiempos) >= 5:
        corte = p95([t for t, _ in tiempos])
        atipicos = [f"{caso} ({t / 1000:.1f} s)" for t, caso in tiempos if t >= corte]
        puntos.append("**Latencia.** Casos en el p95 o por encima: " + ", ".join(atipicos) + ".")
    # Retroalimentación
    no_utiles = [x for x in r.retro if x.get("util") == "False"]
    if no_utiles:
        puntos.append("**Retroalimentación.** Calificados como no útiles: " + "; ".join(
            f"{x.get('hallazgo_id') or 'informe'} ({(x.get('comentario') or 'sin comentario')[:80]})" for x in no_utiles) + ".")
    return puntos


def mejoras(r: Resultados) -> list[str]:
    salida = []
    a5 = r.acierto5()
    if a5 is not None and a5 < META_ACIERTO5:
        salida.append(f"El acierto@5 ({fmt(a5)}) queda bajo la meta de {META_ACIERTO5}: ajustar los títulos de "
                      "sección de `perfiles.yaml` a los del corpus real y probar la búsqueda híbrida con BM25.")
    _, fp = r.seguridad()
    if fp is not None and fp > 0:
        salida.append("Revisar los patrones o el umbral de E4 que causaron falsos positivos (tabla 19).")
    pobres = num(r.t20.get("Terminan en «sin norma»", {}).get("valor"))
    if pobres:
        salida.append("Añadir al prompt de reformulación los términos que el agente no logró traducir.")
    if any(c.get("tipo") == "distractor" and c.get("cache") == "semantica" and str(c.get("umbral")) == "0.92"
           for c in r.t22c):
        salida.append("Con 0.92 la caché semántica sirvió distractores: subir el umbral o exigir la misma verificación.")
    lat = r.latencias_por_ruta()
    if lat["rapida"]["p95"] and lat["rapida"]["p95"] > META_RAPIDA_S:
        salida.append("La ruta rápida supera los 15 s de p95: reducir el lote o la salida por hallazgo.")
    return salida or ["Sin mejoras adicionales derivadas de los errores de esta corrida."]


# -- documento -----------------------------------------------------------------------
def generar(r: Resultados, corpus: dict) -> tuple[str, str]:
    md, tex = [], []
    prov = r.provisional
    md.append("# Insumos para completar el informe técnico\n")
    md.append(f"Generado con `evaluacion/insumos_informe.py` desde `{r.d}`. Corrida: proveedor "
              f"`{r.corrida.get('proveedor', '?')}`, juez {'sí' if r.corrida.get('juez') else 'no'}, "
              f"{r.corrida.get('corridas', '?')} corridas por caso.\n")
    if prov:
        md.append("> **PROVISIONAL.** Esta corrida usó el proveedor falso (modelos y embeddings simulados, mallas "
                  "sintéticas, corpus de prueba). Sirve para ver la forma del texto y las tablas; las cifras de "
                  "modelos, recuperación, caché semántica, agente y enrutador **no** deben ir al informe. "
                  "Vuelve a generar este archivo tras la corrida con Ollama.\n")

    # Estado de las metas (tabla 5)
    lat = r.latencias_por_ruta()
    seg, fp = r.seguridad()
    e500, respaldo, nf = r.fallas_resumen()
    priv = r.privacidad_total()
    exacta = r.exacta()
    memoria = [num(f.get("memoria_gb")) for f in r.t08 if f["modelo"] in ("gemma4:e2b", "gpt-oss:20b")]
    memoria_total = sum(memoria) if memoria and all(v is not None for v in memoria) else None
    recall, precision = r.m16("Recall de hallazgos"), r.m16("Precisión de hallazgos")
    s2 = r.m16("Citas inventadas detectadas por S2 (% de las citas)")
    metas = [
        ["Exactitud", "recall y precisión ≥ 0.95", f"{fmt(recall)} / {fmt(precision)}",
         estado(None if recall is None else recall >= META_RECALL and (precision or 0) >= META_PRECISION)],
        ["Fundamentación", "acierto@5 ≥ 0.85; fidelidad ≥ 4; S2 ≤ 5 %",
         f"{fmt(r.acierto5())}; {fmt(r.fidelidad())}; {fmt(s2, 1, ' %')}",
         estado(None if r.acierto5() is None or r.fidelidad() is None else
                r.acierto5() >= META_ACIERTO5 and r.fidelidad() >= META_FIDELIDAD and (s2 or 0) <= META_S2_PCT)],
        ["Seguridad", "≥ 90 % bien manejadas; ≤ 10 % falsos positivos", f"{fmt(seg, 1, ' %')}; {fmt(fp, 1, ' %')}",
         estado(None if seg is None else seg >= META_SEGURIDAD_PCT and (fp or 0) <= META_FP_PCT)],
        ["Latencia", "p95 ≤ 15 s rápida, ≤ 45 s completa; caché exacta ≤ 300 ms",
         f"{fmt(lat['rapida']['p95'])} s; {fmt(lat['completa']['p95'])} s; {fmt(exacta['p95_ms'], 1)} ms",
         estado(None if lat["rapida"]["p95"] is None or exacta["p95_ms"] is None else
                lat["rapida"]["p95"] <= META_RAPIDA_S and (lat["completa"]["p95"] or 0) <= META_COMPLETA_S
                and exacta["p95_ms"] <= META_EXACTA_MS)],
        ["Privacidad", "0 datos personales", fmt(priv, 0), estado(None if priv is None else priv == 0)],
        ["Disponibilidad", "0 errores 500; termina con el respaldo", f"{e500} errores 500; {respaldo} de {nf}",
         estado(None if not nf else e500 == 0 and respaldo == nf)],
        ["Modificabilidad", "cambiar la base vectorial toca un adaptador",
         "prueba de arquitectura y adaptador en memoria", "Cumple (pytest)"],
        ["Recursos", "memoria pico ≤ 40 GB", fmt(memoria_total, 1, " GB"),
         estado(comparar(memoria_total, META_MEMORIA_GB, mayor_es_mejor=False))],
        ["Reproducibilidad", "un tercero lo levanta en ≤ 30 min", MANUAL, "Sin dato"],
    ]
    if prov:   # estas metas dependen de los modelos o los embeddings reales
        for fila in metas:
            if fila[0] in ("Fundamentación", "Seguridad", "Latencia", "Recursos") and fila[3] != "Sin dato":
                fila[3] += " (indicativo)"
    md.append("## Estado de las metas (tabla 5)\n")
    md.append(tabla_md(["Atributo", "Meta", "Medido", "Estado"], metas) + "\n")

    # Pendientes en orden del informe
    md.append("## Pendientes del informe, en orden\n")
    md.append(f"### Portada · Docente\n{MANUAL}: nombre del docente.\n")

    md.append("### Resumen · resultados principales\n")
    md.append(
        f"En los 20 casos, el analizador obtuvo un recall de {fmt(recall)} y una precisión de {fmt(precision)} en los "
        f"hallazgos. La sección de norma esperada apareció entre los cinco primeros fragmentos en el "
        f"{fmt((r.acierto5() or 0) * 100 if r.acierto5() is not None else None, 0, ' %')} de los hallazgos, y la "
        f"fidelidad media al contexto fue de {fmt(r.fidelidad())} sobre 5. La latencia p95 por auditoría fue de "
        f"{fmt(lat['rapida']['p95'])} s en la ruta rápida y {fmt(lat['completa']['p95'])} s en la completa. Los "
        f"guardrails manejaron bien el {fmt(seg, 0, ' %')} de las entradas problemáticas, con "
        f"{fmt(fp, 0, ' %')} de falsos positivos.\n")

    md.append("### 2.3 · Número de fragmentos\n")
    md.append(f"Tras la ingesta, el corpus produce **{corpus['fragmentos']}** fragmentos indexados en ChromaDB "
              f"({corpus['tam']} caracteres, solape {corpus['solape']}).\n")
    if corpus["errores"]:
        md.append("Documentos que no se pudieron leer: " + "; ".join(corpus["errores"]) + "\n")

    md.append("### Tabla 2 · Composición del corpus\n")
    filas2 = []
    total_docs = total_pags = 0
    for clave, nombre in FUENTES + [("otros", "Otros")]:
        f = corpus["fuentes"].get(clave)
        if not f:
            if clave != "otros":
                filas2.append([nombre, FALTA, FALTA, 0, 0, 0])
            continue
        total_docs += f["docs"]
        total_pags += f["paginas"]
        filas2.append([nombre, "/".join(sorted(f["formatos"])), ", ".join(sorted(f["licencias"])),
                       f["docs"], f["paginas"], f["fragmentos"]])
    filas2.append(["**Total** (mínimo sugerido: 20 documentos o 50 páginas)", "", "", total_docs, total_pags,
                   corpus["fragmentos"]])
    md.append(tabla_md(["Fuente", "Formato", "Licencia", "Docs.", "Págs.", "Fragm."], filas2) + "\n")
    md.append(f"Las páginas de PDF son reales; las de HTML y Markdown son equivalentes de {CARACTERES_POR_PAGINA} "
              "caracteres (anótalo en el pie de la tabla). La columna de fragmentos es opcional.\n")
    md.append("**Licencia de glTF 2.0** (el «[Pendiente: verificar]»): el HTML del registro de Khronos está bajo la "
              "*Khronos Specification License* (uso y reproducción sin modificar, sin costo; no concede patentes ni "
              "marcas); las fuentes AsciiDoc del repositorio de Khronos, bajo CC BY 4.0. Pon la que corresponda al "
              "archivo que ingeriste y confírmala en el registro.\n")
    tex.append(tabla_tex("Tabla 2: Fuente & Formato & Licencia & Docs. & Págs.", [x[:5] for x in filas2]))

    # Tabla 8
    md.append("### Tabla 8 · Modelos de lenguaje\n")
    filas8 = []
    for f in r.t08:
        filas8.append([f["modelo"], f.get("cuantizacion") or MANUAL, f.get("contexto") or MANUAL,
                       fmt(f.get("calidad")), fmt(f.get("espanol")),
                       f"{fmt(f.get('latencia_p50_s'))} / {fmt(f.get('latencia_p95_s'))}",
                       fmt(f.get("tok_s"), 1), fmt(f.get("memoria_gb"), 1)])
    md.append(tabla_md(["Modelo", "Cuantización", "Contexto", "Calidad", "Español", "Lat. p50 / p95 (s)",
                        "tok/s", "Memoria (GB)"], filas8) + "\n")
    md.append("La cuantización y el contexto salen de `ollama show` (los «?» de la columna de características). "
              "La carga en frío va aparte, en el texto: " + ", ".join(
                  f"{f['modelo']} {fmt(f.get('carga_en_frio_s'), 1)} s" for f in r.t08) + ".\n")
    tex.append(tabla_tex("Tabla 8 (columnas medidas): Calidad & Español & p50 / p95 & tok/s & Memoria",
                         [[x[0], x[3], x[4], x[5], x[6], x[7]] for x in filas8]))

    # Tabla 9
    md.append("### Tabla 9 · Embeddings\n")
    filas9 = [[f["modelo"], fmt(f.get("acierto_1")), fmt(f.get("acierto_5")), fmt(f.get("mrr")),
               fmt(f.get("indexado_s"), 1), f"{f.get('rechazos_correctos', FALTA)} de {f.get('rechazos_de', 10)}"]
              for f in r.t09]
    md.append(tabla_md(["Modelo", "Acierto@1", "Acierto@5", "MRR", "Indexado (s)", "Rechazos (umbral 0.55)"],
                       filas9) + "\n")
    md.append("Acierto y MRR se midieron sin umbral (solo el orden); la columna de rechazos es opcional en el "
              "informe y puede ir en el texto.\n")
    tex.append(tabla_tex("Tabla 9: Acierto@1 & Acierto@5 & MRR & Indexado (s)", [x[:5] for x in filas9]))

    md.append("### 6.4.1 · Conclusión de la selección\n" + conclusion_seleccion(r) + "\n")

    # Evidencias de los ADR
    md.append("### Sección 8 · Evidencia de cada ADR\n")
    m8 = {f["modelo"]: f for f in r.t08}
    ev = {
        "ADR-01 (tabla 8)": "; ".join(f"{m}: calidad {fmt(f.get('calidad'))}, p95 {fmt(f.get('latencia_p95_s'))} s"
                                      for m, f in m8.items()) or FALTA,
        "ADR-02 (tabla 9)": "; ".join(f"{f['modelo']}: acierto@5 {fmt(f.get('acierto_5'))}, MRR {fmt(f.get('mrr'))}"
                                      for f in r.t09) or FALTA,
        "ADR-03 (tabla 22)": "; ".join(
            f"{f['umbral']}: recall {fmt(f.get('recall'))}, precisión {fmt(f.get('precision'))}"
            for f in r.t22 if not str(f.get("umbral", "")).startswith("Exacta")) or FALTA,
        "ADR-04 (tabla 21)": (lambda adec, total: (
            f"{adec} de {total} casos ({fmt(100 * adec / total if total else None, 0, ' %')}) a una ruta adecuada; "
            f"{next((f['adecuados'] for f in r.t21 if f['ruta_esperada'].startswith('A la completa')), FALTA)} "
            f"enviados a la completa sin necesidad; p95 rápida {fmt(lat['rapida']['p95'])} s y completa "
            f"{fmt(lat['completa']['p95'])} s"))(
            sum(int(num(f.get("adecuados")) or 0) for f in r.t21 if f["ruta_esperada"] in ("Sin modelo", "Rápida", "Completa")),
            sum(int(num(f.get("casos")) or 0) for f in r.t21 if f["ruta_esperada"] in ("Sin modelo", "Rápida", "Completa"))),
        "ADR-05 (tabla 19)": f"{fmt(seg, 0, ' %')} de las 13 entradas problemáticas bien manejadas y "
                             f"{fmt(fp, 0, ' %')} de falsos positivos en las 10 normales",
        "ADR-06 (tablas 17 y 18)": "; ".join(f"{f['fragmento']}, k={f['k']}: acierto@k {fmt(f.get('acierto_k'))}"
                                             for f in r.t17) + ". Con 800/120 y umbral 0.55: " + (
            "; ".join(f"@{k} {fmt(next((x.get(f'acierto_{k}') for x in r.t18 if num(x['umbral']) == 0.55), None))}"
                      for k in (3, 5, 8))
            + f", {next((x.get('rechazos_de_10') for x in r.t18 if num(x['umbral']) == 0.55), FALTA)} de 10 rechazos"),
        "ADR-07 (tabla 20)": f"{r.t20.get('Superan el umbral tras reformular', {}).get('valor', FALTA)} consultas pobres "
                             f"superan el umbral tras reformular, con "
                             f"{r.t20.get('Reformulaciones promedio', {}).get('valor', FALTA)} reformulaciones de media",
        "ADR-08 (tabla 16)": f"recall {fmt(recall)} y precisión {fmt(precision)}; S3 eliminó "
                             f"{fmt(r.m16('Cifras sin respaldo eliminadas por S3'), 0)} frases con cifras sin respaldo",
    }
    md.append("\n".join(f"- **{k}:** {v}." for k, v in ev.items()) + "\n")
    md.append("Cuando una evidencia confirme su decisión, cambia el «Estado» del ADR de «Propuesta» a «Aceptada».\n")

    # Tablas 16-23
    md.append("### Tabla 16 · Calidad del producto\n")
    orden16 = ["Recall de hallazgos", "Precisión de hallazgos", "Acierto@5 de la sección esperada",
               "Fidelidad al contexto (0–5)", "Relevancia de la corrección (0–5)",
               "Citas inventadas detectadas por S2 (% de las citas)", "Cifras sin respaldo eliminadas por S3",
               "Diferencia media juez–autor (15 casos)", "Acuerdo juez–autor, diferencia ≤ 1 punto (%)",
               "Hallazgos servidos desde la caché de hallazgos"]
    filas16 = [[m, self_or(r.t16.get(m, {}).get("con_rag")), self_or(r.t16.get(m, {}).get("sin_rag"))] for m in orden16]
    md.append(tabla_md(["Métrica", "Con RAG", "Sin RAG"], filas16) + "\n")
    md.append("El informe tiene una sola fila juez–autor: pon la diferencia media en «Con RAG» y el % de acuerdo "
              "en el texto de la sección 9.1, o añade la fila.\n")
    tex.append(tabla_tex("Tabla 16: Con RAG & Sin RAG", [[x[1], x[2]] for x in filas16]))

    md.append("### Tabla 17 · Tamaño de fragmento\n")
    filas17 = [[f["fragmento"], f["k"], f.get("fragmentos"), fmt(f.get("acierto_k")), fmt(f.get("mrr"))] for f in r.t17]
    md.append(tabla_md(["Fragmento", "k", "Fragm.", "Acierto@k", "MRR"], filas17) + "\n")
    tex.append(tabla_tex("Tabla 17", filas17))

    md.append("### Tabla 18 · Barrido de k y umbral\n")
    filas18 = [[f["umbral"], fmt(f.get("acierto_3")), fmt(f.get("acierto_5")), fmt(f.get("acierto_8")),
                f.get("rechazos_de_10")] for f in r.t18]
    md.append(tabla_md(["Umbral", "@3", "@5", "@8", "Rechazos (de 10)"], filas18) + "\n")
    tex.append(tabla_tex("Tabla 18", filas18))

    md.append("### Tabla 19 · Guardrails de entrada\n")
    filas19 = [[k, f.get("casos"), f.get("correctos"), f.get("falsos_positivos")] for k, f in r.t19.items()]
    md.append(tabla_md(["Entrada", "Casos", "Correctos", "Falsos pos."], filas19) + "\n")
    tex.append(tabla_tex("Tabla 19", filas19))

    md.append("### Tabla 20 · Ciclo de agente\n")
    filas20 = [[k, f.get("valor")] for k, f in r.t20.items()]
    md.append(tabla_md(["Métrica", "Valor"], filas20) + "\n")
    tex.append(tabla_tex("Tabla 20", filas20))

    md.append("### Tabla 21 · Enrutador\n")
    filas21 = [[f["ruta_esperada"], f.get("casos"), f.get("adecuados"),
                f"{fmt(f.get('latencia_p50_s'))} / {fmt(f.get('latencia_p95_s'))}"
                if f.get("latencia_p50_s") else ""] for f in r.t21]
    md.append(tabla_md(["Ruta esperada", "Casos", "Adec.", "Lat. p50 / p95 (s)"], filas21) + "\n")
    tex.append(tabla_tex("Tabla 21", filas21))

    md.append("### Tabla 22 · Caché\n")
    filas22 = [[f["umbral"], fmt(f.get("recall")), fmt(f.get("precision")), f.get("falsos_positivos"),
                fmt(f.get("ahorro_ms"), 1)] for f in r.t22]
    md.append(tabla_md(["Umbral", "Recall", "Precisión", "Falsos pos.", "Ahorro (ms)"], filas22) + "\n")
    md.append(f"p95 de una auditoría servida por la caché exacta: {fmt(exacta['p95_ms'], 1)} ms (meta ≤ 300 ms).\n")
    tex.append(tabla_tex("Tabla 22", filas22))

    md.append("### Tabla 23 · Latencia por capa (ms)\n")
    filas23 = [[k, fmt(f.get("mediana"), 1), fmt(f.get("p95"), 1), fmt(f.get("maximo"), 1)] for k, f in r.t23.items()]
    md.append(tabla_md(["Etapa", "Mediana", "p95", "Máxima"], filas23) + "\n")
    tex.append(tabla_tex("Tabla 23", filas23))

    # 9.2 textos
    md.append("### 9.2 · Valor medido con el revisor independiente\n")
    md.append(f"{MANUAL}: completa la tabla con la prueba de las cinco mallas y pega el párrafo.\n\n"
              + tabla_md(["Malla", "Tiempo manual (min)", "Tiempo MeshAudit (s)", "Hallazgos del revisor",
                          "Encontrados por MeshAudit"], [[f"malla {i}", "", "", "", ""] for i in range(1, 6)])
              + "\n\nTexto: «El revisor tardó en promedio X min por malla; MeshAudit, Y s. De los N hallazgos del "
                "revisor, la herramienta encontró M (P %); los restantes eran aspectos que las reglas no miden, "
                "como …».\n")
    total_retro, tasa = r.retro_resumen()
    md.append("### 9.2 · Fallas y retroalimentación\n")
    md.append(f"En las fallas inyectadas se registraron **{e500}** errores 500 y **{respaldo}** de {nf} auditorías "
              f"terminaron con el respaldo. Durante las pruebas se registraron **{total_retro}** calificaciones de "
              f"retroalimentación, con una tasa de utilidad de **{fmt(tasa, 0, ' %')}**.\n")
    if total_retro == 0:
        md.append("No hay calificaciones: usa la aplicación web en las pruebas o pasa `--datos` con tu `data/`.\n")

    md.append("### 9.3 · Análisis de errores\n" + "\n".join(f"- {p}" for p in analisis_errores(r)) + "\n")
    md.append("### 9.4 · Mejoras que surgen del análisis\n" + "\n".join(f"- {m}" for m in mejoras(r)) + "\n")

    md.append("### Referencias · versiones\n")
    blender = ", ".join(sorted(corpus["fuentes"].get("blender", {}).get("versiones", set()))) or MANUAL
    md.append(f"- Blender Manual (versión {blender}): la del manual que descargaste; puedes declararla como "
              "`version:` en `corpus/fuentes.yaml` y este script la toma.\n"
              f"- trimesh (versión {version_de('trimesh')}): la instalada al generar este archivo; en el Mac, la de "
              "`pip show trimesh`.\n")
    md.append("### 10.3 · Declaración de uso de asistentes de IA\nVer el texto propuesto en "
              "`docs/REVISION_INFORME.md`, sección 3: hay que decirlo con exactitud, porque el código no es solo un "
              "esqueleto.\n")
    return "\n".join(md), "\n".join(tex)


def self_or(valor):
    return valor if valor not in (None, "") else FALTA


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--resultados", type=Path, default=RESULTADOS)
    p.add_argument("--corpus", type=Path, default=RAIZ / "corpus")
    p.add_argument("--salida", type=Path, default=None, help="directorio de salida (por defecto, --resultados)")
    args = p.parse_args(argv)
    salida = args.salida or args.resultados
    salida.mkdir(parents=True, exist_ok=True)
    r = Resultados(args.resultados)
    md, tex = generar(r, resumen_corpus(args.corpus))
    (salida / "INSUMOS_INFORME.md").write_text(md, encoding="utf-8")
    (salida / "tablas_informe.tex").write_text(tex, encoding="utf-8")
    print(salida / "INSUMOS_INFORME.md")
    print(salida / "tablas_informe.tex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
