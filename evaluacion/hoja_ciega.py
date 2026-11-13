"""Validación del juez a ciegas (fila juez–autor de la tabla 16).

1. Crear la hoja: una página HTML con las 15 explicaciones de
   ``muestra_revision_manual.csv`` en orden aleatorio, **sin** el modelo ni las notas
   del juez, para calificarlas de 0 a 5:

       python -m evaluacion.hoja_ciega crear

2. Abrir ``evaluacion/resultados/hoja_ciega.html`` en el navegador, calificar y
   pulsar «Descargar notas» (``notas_autor.csv``).

3. Juntar las notas con la muestra (llena ``nota_autor_fidelidad`` y
   ``nota_autor_relevancia``) y recalcular las tablas:

       python -m evaluacion.hoja_ciega juntar ~/Downloads/notas_autor.csv
       python evaluacion/run_eval.py --proveedor ollama --tablas 16 --juez --salida evaluacion/resultados/
       python -m evaluacion.insumos_informe --resultados evaluacion/resultados/ --corpus corpus/
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import random
from pathlib import Path

from evaluacion.comun import RESULTADOS

MUESTRA = RESULTADOS / "muestra_revision_manual.csv"
HOJA = RESULTADOS / "hoja_ciega.html"
CAMPOS_AUTOR = ("nota_autor_fidelidad", "nota_autor_relevancia")

PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Validación del juez</title>
<style>
:root{--fondo:#f6f7f9;--carta:#fff;--texto:#1d2330;--suave:#5b6474;--borde:#d9dde4;--acento:#1f4fbf}
@media (prefers-color-scheme:dark){:root{--fondo:#14171c;--carta:#1d2128;--texto:#e6e9ef;--suave:#9aa3b2;--borde:#333a45;--acento:#7fa5ff}}
body{margin:0;background:var(--fondo);color:var(--texto);font:15px/1.5 -apple-system,system-ui,sans-serif}
main{max-width:900px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:22px;margin:0 0 4px}.nota{color:var(--suave);margin:0 0 20px}
article{background:var(--carta);border:1px solid var(--borde);border-radius:10px;padding:16px;margin:0 0 16px}
h2{font-size:15px;margin:0 0 8px}.etq{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--suave);margin:12px 0 4px}
.fragmento{white-space:pre-wrap;font-size:13px;color:var(--suave);max-height:220px;overflow:auto;border-left:3px solid var(--borde);padding-left:10px}
.explicacion{white-space:pre-wrap}
fieldset{border:0;padding:0;margin:10px 0 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
legend{font-weight:600;margin-right:8px;float:left}
label{border:1px solid var(--borde);border-radius:6px;padding:4px 10px;cursor:pointer}
input[type=radio]{margin-right:4px}
footer{position:fixed;bottom:0;left:0;right:0;background:var(--carta);border-top:1px solid var(--borde);padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:center}
button{background:var(--acento);color:#fff;border:0;border-radius:8px;padding:8px 16px;font-size:15px;cursor:pointer}
</style></head><body><main>
<h1>Validación del juez: 15 explicaciones</h1>
<p class="nota"><strong>Fidelidad</strong>: ¿la explicación se apoya solo en el fragmento, sin inventar? <strong>Relevancia</strong>: ¿la corrección propuesta sirve para el hallazgo? 0 = nada, 5 = totalmente. El orden es aleatorio y no se muestra qué modelo la escribió.</p>
__CASOS__
</main>
<footer><span id="avance"></span><button id="descargar">Descargar notas</button></footer>
<script>
const ids = __IDS__;
const clave = "hoja_ciega_notas";
function leer(){ try { return JSON.parse(localStorage.getItem(clave) || "{}"); } catch(e){ return {}; } }
function guardar(n){ try { localStorage.setItem(clave, JSON.stringify(n)); } catch(e){} }
const notas = leer();
for (const [nombre, valor] of Object.entries(notas)) {
  const r = document.querySelector(`input[name="${nombre}"][value="${valor}"]`); if (r) r.checked = true;
}
function avance(){
  const hechas = ids.filter(i => notas[i+"|fidelidad"] !== undefined && notas[i+"|relevancia"] !== undefined).length;
  document.getElementById("avance").textContent = `${hechas} de ${ids.length} calificadas`;
}
document.addEventListener("change", e => { if (e.target.type === "radio") { notas[e.target.name] = e.target.value; guardar(notas); avance(); }});
document.getElementById("descargar").onclick = () => {
  const filas = [["id","nota_autor_fidelidad","nota_autor_relevancia"]];
  for (const i of ids) filas.push([i, notas[i+"|fidelidad"] ?? "", notas[i+"|relevancia"] ?? ""]);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([filas.map(f => f.join(",")).join("\\n")], {type:"text/csv"}));
  a.download = "notas_autor.csv"; a.click();
};
avance();
</script></body></html>
"""


def _id(fila: dict) -> str:
    return f"{fila['modelo']}|{fila['caso']}|{fila['hallazgo']}"


def crear(semilla: int = 7) -> Path:
    filas = list(csv.DictReader(open(MUESTRA, encoding="utf-8")))
    random.Random(semilla).shuffle(filas)
    # Identificador opaco por caso: el modelo no se ve en la página.
    mapa = {f"c{n:02d}": _id(f) for n, f in enumerate(filas, 1)}
    (RESULTADOS / "hoja_ciega_claves.json").write_text(json.dumps(mapa, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
    bloques = []
    for (opaco, _), f in zip(mapa.items(), filas):
        escalas = "".join(
            f'<fieldset><legend>{campo.capitalize()}</legend>' + "".join(
                f'<label><input type="radio" name="{opaco}|{campo}" value="{v}">{v}</label>' for v in range(6))
            + "</fieldset>" for campo in ("fidelidad", "relevancia"))
        bloques.append(
            f'<article><h2>Caso {opaco[1:]}</h2>'
            f'<div class="etq">Fragmento recuperado (contexto)</div><div class="fragmento">{html.escape(f["fragmento"])}</div>'
            f'<div class="etq">Explicación generada</div><div class="explicacion">{html.escape(f["explicacion"])}</div>'
            f'{escalas}</article>')
    HOJA.write_text(PLANTILLA.replace("__CASOS__", "\n".join(bloques))
                    .replace("__IDS__", json.dumps(list(mapa))), encoding="utf-8")
    return HOJA


def juntar(notas: Path) -> int:
    mapa = json.loads((RESULTADOS / "hoja_ciega_claves.json").read_text(encoding="utf-8"))
    autor = {mapa[f["id"]]: f for f in csv.DictReader(open(notas, encoding="utf-8")) if f["id"] in mapa}
    filas = list(csv.DictReader(open(MUESTRA, encoding="utf-8")))
    llenas = 0
    for f in filas:
        a = autor.get(_id(f))
        if a and a["nota_autor_fidelidad"] != "" and a["nota_autor_relevancia"] != "":
            for campo in CAMPOS_AUTOR:
                f[campo] = a[campo]
            llenas += 1
    with open(MUESTRA, "w", encoding="utf-8", newline="") as salida:
        w = csv.DictWriter(salida, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    return llenas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="accion", required=True)
    sub.add_parser("crear")
    j = sub.add_parser("juntar")
    j.add_argument("notas", type=Path)
    args = p.parse_args(argv)
    if args.accion == "crear":
        print(crear())
    else:
        print(f"{juntar(args.notas)} de 15 casos con nota del autor en {MUESTRA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
