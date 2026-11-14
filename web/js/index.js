// Página principal: abrir la malla, verla en 3D, auditarla, navegar el informe
// (Outliner → Atributos), retroalimentación, preguntas de seguimiento y exportación.
let informeActual = null;
let hallazgoSeleccionado = null;
let archivoActual = null;

// guardrails: {"entrada": "aprobada", "salida": "aprobada", "activaciones": [...]} (Código 8)
function textoGuardrails(g) {
  if (!g) return "";
  if (Array.isArray(g)) return g.join(", ");
  return `entrada ${g.entrada}, salida ${g.salida}` +
    (g.activaciones && g.activaciones.length ? ` (${g.activaciones.join(", ")})` : "");
}

async function cargarPerfiles() {
  const selector = $("#perfil");
  try {
    const datos = await API.perfiles();
    selector.innerHTML = Object.entries(datos.perfiles).map(([clave, p]) =>
      `<option value="${esc(clave)}">${esc(p.nombre)} (${esc(p.unidad)})</option>`).join("");
  } catch (e) {
    selector.innerHTML = ["animacion", "juego_movil", "impresion_3d", "web_ar"]
      .map(c => `<option value="${c}">${c}</option>`).join("");
  }
}

// Línea de ayuda: estado a la izquierda y errores en rojo.
function mostrarError(mensaje) {
  const nodo = $("#error");
  nodo.textContent = mensaje;
  nodo.title = mensaje;
  nodo.classList.toggle("oculto", !mensaje);
  if (mensaje) $("#estado").textContent = "";
}
function mostrarEstado(texto) { $("#estado").textContent = texto; }

// ── Iconos del Outliner ──────────────────────────────────────────────────
const ICONOS = {
  malla: `<svg class="ico" viewBox="0 0 16 16"><path d="M8 1.5 14 5v6l-6 3.5L2 11V5z" fill="none" stroke="currentColor"/><path d="M2 5l6 3.5L14 5M8 8.5v6" fill="none" stroke="currentColor"/></svg>`,
  carpeta: `<svg class="ico" viewBox="0 0 16 16"><path d="M1.5 4h5l1.5 1.5h6.5v8h-13z" fill="none" stroke="currentColor"/></svg>`,
  perfil: `<svg class="ico" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor"/><circle cx="8" cy="8" r="2" fill="currentColor"/></svg>`,
};

// ── Abrir una malla (botón o arrastrar a la vista) ───────────────────────
async function abrirArchivo(archivo) {
  if (!archivo) return;
  archivoActual = archivo;
  const nombre = $("#nombre-archivo");
  nombre.textContent = archivo.name;
  nombre.title = `${archivo.name} · ${(archivo.size / 1048576).toFixed(2)} MB`;
  nombre.classList.add("cargado");
  limpiarInforme();
  mostrarError("");
  $("#vacio").classList.add("oculto");
  pintarHud();
  if (!window.Visor) { mostrarEstado("La vista 3D todavía se está cargando…"); return; }
  mostrarEstado(`Cargando ${archivo.name} en la vista…`);
  try {
    await window.Visor.cargar(archivo);
    mostrarEstado(`${archivo.name} abierta. Elige el perfil y pulsa Auditar.`);
  } catch (e) {
    mostrarEstado("");
    mostrarError(`No se pudo mostrar en la vista 3D: ${e.message}. Aun así puedes auditarla.`);
  }
  pintarArbol();
}

$("#archivo").addEventListener("change", (evento) => abrirArchivo(evento.target.files[0]));

const lienzo = $("#lienzo");
["dragenter", "dragover"].forEach(tipo => lienzo.addEventListener(tipo, (e) => {
  e.preventDefault();
  lienzo.classList.add("arrastrando");
}));
["dragleave", "drop"].forEach(tipo => lienzo.addEventListener(tipo, (e) => {
  e.preventDefault();
  lienzo.classList.remove("arrastrando");
}));
lienzo.addEventListener("drop", (e) => {
  const archivo = e.dataTransfer.files[0];
  if (!archivo) return;
  if (!/\.(obj|glb|stl|ply)$/i.test(archivo.name)) {
    mostrarError("Formato no admitido: usa .obj, .glb, .stl o .ply.");
    return;
  }
  const transferencia = new DataTransfer();
  transferencia.items.add(archivo);
  $("#archivo").files = transferencia.files;
  abrirArchivo(archivo);
});

// ── Auditar ──────────────────────────────────────────────────────────────
$("#formulario").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mostrarError("");
  if (!$("#archivo").files.length) {
    mostrarError("Abre una malla primero (botón «Abrir malla» o arrástrala a la vista).");
    return;
  }
  const boton = $("#enviar");
  boton.disabled = true;
  mostrarEstado("Auditando… (la ruta completa puede tardar unos segundos)");
  try {
    informeActual = await API.auditar(new FormData(evento.target));
    pintarInforme(informeActual);
    $("#respuestas").innerHTML = "";
    $("#preguntas").classList.remove("abierta");
    mostrarEstado(`Auditoría lista en ${Math.round(informeActual.tiempo_ms)} ms · ruta ${informeActual.ruta}` +
      ` · modelo ${informeActual.modelo} · caché ${informeActual.cache}.`);
  } catch (e) {
    mostrarError(e.message + (e.cuerpo && e.cuerpo.aviso ? ` — ${e.cuerpo.aviso}` : ""));
  } finally {
    boton.disabled = false;
  }
});

const ETIQUETAS = {
  formato: "Formato", tamano_bytes: "Tamaño (bytes)", vertices: "Vértices", triangulos: "Triángulos",
  caras: "Caras", dimension_max: "Dimensión máxima", dimensiones: "Dimensiones",
  pct_ngons: "% n-gons", pct_triangulos: "% triángulos", aristas_no_manifold: "Aristas no manifold",
  cerrada: "Cerrada", uv: "UV", caras_degeneradas: "Caras degeneradas",
  normales_consistentes: "Normales consistentes", volumen_con_signo: "Volumen con signo",
  vertices_duplicados: "Vértices duplicados",
};

// Métrica que corresponde a cada verificación, para resaltar el canal con problema.
const METRICA_DE = { V1: "pct_ngons", V2: "pct_triangulos", V3: "triangulos", V4: "aristas_no_manifold",
  V5: "cerrada", V6: "uv", V7: "dimension_max", V8: "caras_degeneradas", V9: "normales_consistentes",
  V10: "vertices_duplicados", V11: "tamano_bytes" };

// Ayuda visual de la vista que conviene activar al seleccionar cada hallazgo.
const AYUDA_VISUAL = { V3: ["alambreEncima"], V1: ["alambreEncima"], V2: ["alambreEncima"],
  V4: ["bordes"], V5: ["bordes"], V9: ["traseras"] };

function limpiarInforme() {
  informeActual = null;
  hallazgoSeleccionado = null;
  $("#semaforo").textContent = "";
  $("#semaforo").className = "semaforo";
  $("#metricas").innerHTML = "";
  $("#sin-metricas").classList.remove("oculto");
  $("#hallazgos").innerHTML = `<p class="vacio-panel">Selecciona un hallazgo en el Outliner.</p>`;
  $("#informe-datos").classList.add("oculto");
  $("#sin-informe").classList.remove("oculto");
  $("#exportar").disabled = true;
  $("#pregunta").disabled = true;
  $("#preguntar").disabled = true;
  $("#pregunta").placeholder = "Audita una malla para preguntar sobre su informe…";
  pintarArbol();
}

function pintarInforme(inf) {
  // Reinicia la valoración del informe anterior (la caja global no se vuelve a dibujar).
  document.querySelectorAll("#informe .retro").forEach(caja => {
    caja.querySelectorAll("button").forEach(b => b.disabled = false);
    caja.querySelector("input").value = "";
    caja.querySelector(".meta").textContent = "";
  });
  const s = $("#semaforo");
  s.className = `semaforo ${inf.semaforo}`;
  s.textContent = inf.semaforo;
  $("#sin-informe").classList.add("oculto");
  $("#informe-datos").classList.remove("oculto");
  $("#resumen").textContent = inf.resumen;
  $("#detalles").textContent = `Ruta ${inf.ruta} · modelo ${inf.modelo} · caché ${inf.cache}` +
    ` · guardrails ${textoGuardrails(inf.guardrails)} · iteraciones del agente ${inf.iteraciones_agente}` +
    ` · traza ${inf.traza_id}`;
  $("#aviso").textContent = inf.aviso;

  const m = inf.metricas_malla;
  const conProblema = new Set(inf.hallazgos.filter(h => h.gravedad !== "informativo")
    .map(h => METRICA_DE[h.verificacion]));
  $("#metricas").innerHTML = Object.entries(ETIQUETAS).filter(([k]) => k in m && m[k] !== null)
    .map(([k, etiqueta]) => {
      let v = m[k];
      if (k === "dimension_max") v = `${formatoMedido(v)} ${m.unidad}`;
      else if (Array.isArray(v)) v = v.map(formatoMedido).join(" × ") + ` ${m.unidad}`;
      else v = formatoMedido(v);
      return `<tr class="${conProblema.has(k) ? "alerta" : ""}"><th>${esc(etiqueta)}</th>` +
             `<td><span title="${esc(v)}">${esc(v)}</span></td></tr>`;
    }).join("");
  $("#sin-metricas").classList.add("oculto");

  $("#exportar").disabled = false;
  $("#pregunta").disabled = false;
  $("#preguntar").disabled = false;
  $("#pregunta").placeholder = "Ej.: ¿Cómo encuentro las aristas no manifold en Blender?";

  const primero = inf.hallazgos.find(h => h.gravedad !== "informativo") || inf.hallazgos[0];
  pintarArbol();
  if (primero) seleccionarHallazgo(primero.id);
  else {
    $("#hallazgos").innerHTML = `<p class="vacio-panel">Sin hallazgos: la malla cumple el perfil.</p>`;
    cambiarPestana("informe");
  }
  pintarHud();
}

// ── Outliner ─────────────────────────────────────────────────────────────
function pintarArbol() {
  const arbol = $("#arbol");
  if (!archivoActual && !informeActual) {
    arbol.innerHTML = `<li class="vacio-arbol">Sin escena. Abre una malla.</li>`;
    return;
  }
  const nombre = informeActual ? informeActual.archivo : archivoActual.name;
  const nodoMalla = `<li><div class="nodo clic ${hallazgoSeleccionado ? "" : "sel"}" data-nodo="malla">
      ${ICONOS.malla}<span class="etq">${esc(nombre)}</span>
      ${informeActual ? `<span class="punto ${esc(informeActual.semaforo)}" title="Semáforo ${esc(informeActual.semaforo)}"></span>` : ""}
    </div>`;
  if (!informeActual) {
    arbol.innerHTML = nodoMalla + `<ul><li><div class="nodo"><span class="etq meta">Sin auditar</span></div></li></ul></li>`;
    return;
  }
  const graves = informeActual.hallazgos.filter(h => h.gravedad !== "informativo");
  const informativos = informeActual.hallazgos.filter(h => h.gravedad === "informativo");
  const item = h => `<li><div class="nodo clic ${h.id === hallazgoSeleccionado ? "sel" : ""}" data-hallazgo="${esc(h.id)}"
      title="${esc(h.descripcion || h.tipo)} · medido ${esc(formatoMedido(h.medido))}, límite ${esc(h.limite)}">
      <span class="punto ${esc(h.gravedad)}"></span><span class="etq">${esc(h.verificacion)} · ${esc(h.descripcion || h.tipo)}</span>
    </div></li>`;
  const grupo = (titulo, lista) => lista.length ? `<li><div class="nodo">${ICONOS.carpeta}
      <span class="etq">${titulo}</span><span class="cuenta">${lista.length}</span></div>
      <ul>${lista.map(item).join("")}</ul></li>` : "";
  arbol.innerHTML = nodoMalla + `<ul>
      <li><div class="nodo">${ICONOS.perfil}<span class="etq">Perfil: ${esc(informeActual.perfil_nombre || informeActual.perfil)}</span></div></li>
      ${grupo("Hallazgos", graves)}
      ${grupo("Informativos", informativos)}
      ${informeActual.hallazgos.length ? "" : `<li><div class="nodo"><span class="punto verde"></span><span class="etq">Sin hallazgos</span></div></li>`}
    </ul></li>`;
}

$("#arbol").addEventListener("click", (e) => {
  const nodo = e.target.closest(".nodo.clic");
  if (!nodo) return;
  if (nodo.dataset.hallazgo) seleccionarHallazgo(nodo.dataset.hallazgo);
  else if (nodo.dataset.nodo === "malla") {
    hallazgoSeleccionado = null;
    pintarArbol();
    cambiarPestana(informeActual ? "informe" : "canales");
  }
});

function seleccionarHallazgo(id) {
  const h = informeActual && informeActual.hallazgos.find(x => x.id === id);
  if (!h) return;
  hallazgoSeleccionado = id;
  pintarArbol();
  $("#hallazgos").innerHTML = pintarHallazgo(h);
  cambiarPestana("atributos");
  // Activa la ayuda visual que muestra este problema en la vista 3D.
  if (window.Visor) (AYUDA_VISUAL[h.verificacion] || []).forEach(clave => window.Visor.alternar(clave, true));
}

// ── Pestañas del panel derecho ───────────────────────────────────────────
function cambiarPestana(nombre) {
  document.querySelectorAll(".pestanas button").forEach(b =>
    b.classList.toggle("activo", b.dataset.pestana === nombre));
  document.querySelectorAll("[data-panel]").forEach(p =>
    p.classList.toggle("oculto", p.dataset.panel !== nombre));
}
document.querySelector(".pestanas").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-pestana]");
  if (b) cambiarPestana(b.dataset.pestana);
});

// ── HUD de la vista: conteo del archivo abierto y medidas del analizador ─
function pintarHud() {
  const hud = $("#hud");
  const est = window.Visor && window.Visor.estadisticas;
  if (!archivoActual) { hud.innerHTML = ""; return; }
  const fila = (k, v, clase = "") => `<span class="k">${k}</span><span class="v ${clase}">${esc(v)}</span>`;
  let html = `<span class="titulo">${esc(archivoActual.name)}</span>`;
  if (est) {
    html += fila("Vértices", formatoMedido(est.vertices)) + fila("Triángulos", formatoMedido(est.triangulos)) +
            fila("Mallas", est.mallas) +
            fila("Bordes abiertos", formatoMedido(est.abiertas), est.abiertas ? "alerta" : "") +
            fila("No manifold", formatoMedido(est.noManifold), est.noManifold ? "alerta" : "");
  }
  if (informeActual) {
    const m = informeActual.metricas_malla;
    html += fila("Dimensión máx.", `${formatoMedido(m.dimension_max)} ${m.unidad}`);
  }
  hud.innerHTML = html;
}
document.getElementById("lienzo").addEventListener("visor:cargado", pintarHud);

// ── Botones de la vista, sincronizados con el estado del visor ──────────
document.querySelector(".barra-vista").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b || !window.Visor) return;
  if (b.dataset.modo) window.Visor.modo(b.dataset.modo);
  else if (b.dataset.alternar) window.Visor.alternar(b.dataset.alternar);
  else if (b.id === "encuadrar") window.Visor.encuadrar();
});
document.addEventListener("visor:estado", (e) => {
  const est = e.detail;
  document.querySelectorAll(".barra-vista [data-modo]").forEach(b =>
    b.classList.toggle("activo", b.dataset.modo === est.modo));
  document.querySelectorAll(".barra-vista [data-alternar]").forEach(b =>
    b.classList.toggle("activo", !!est[b.dataset.alternar]));
});

// Citas: el texto trae ids de fragmento («[doc:seccion#3]») que S2 ya validó; aquí solo se
// muestran como «[1]», en el orden en que aparecen, con la lista de referencias al final.
const ID_FRAGMENTO = String.raw`[A-Za-z0-9_.\-]+:[^\s\[\](),;]+#\d+`;
const GRUPO_CITAS = new RegExp(String.raw`[\[(]\s*(${ID_FRAGMENTO}(?:\s*[,;]\s*${ID_FRAGMENTO})*)\s*[\])]`, "g");
const ID_SUELTO = new RegExp(String.raw`(?<![\w\[(:])(${ID_FRAGMENTO})`, "g");
const NUMEROS_JUNTOS = /\[(\d+(?:, \d+)*)\]\s*,?\s*\[(\d+(?:, \d+)*)\]/;

function etiquetaReferencia(r) {
  let titulo = r.titulo || r.documento, seccion = r.seccion;
  if (!titulo || !seccion) {
    const [doc, resto = ""] = r.id.split(/:(.*)/s);
    const s = resto.split("#")[0].replace(/-/g, " ");
    titulo = titulo || doc;
    seccion = seccion || (s.charAt(0).toUpperCase() + s.slice(1));
  }
  return `${titulo} › ${seccion}`;
}

// Los fragmentos de una misma sección comparten número; cada referencia lleva sus «ids».
function numerarCitas(textos, referencias) {
  const datos = Object.fromEntries((referencias || []).map(r => [r.id, r]));
  const orden = [], porSeccion = {};
  const numero = id => {
    const seccion = id.split("#")[0];               // «doc:seccion», común a sus fragmentos
    if (!(seccion in porSeccion)) { orden.push({ id, ids: [] }); porSeccion[seccion] = orden.length; }
    const n = porSeccion[seccion], ref = orden[n - 1];
    if (datos[id] && !ref.seccion) Object.assign(ref, datos[id], { id: ref.id, ids: ref.ids });
    if (!ref.ids.includes(id)) ref.ids.push(id);
    return n;
  };
  const salida = textos.map(t => {
    let x = (t || "").replace(GRUPO_CITAS, (_, ids) =>
      "[" + [...new Set(ids.match(new RegExp(ID_FRAGMENTO, "g")).map(numero))].join(", ") + "]");
    x = x.replace(ID_SUELTO, (_, id) => `[${numero(id)}]`);
    while (NUMEROS_JUNTOS.test(x)) x = x.replace(NUMEROS_JUNTOS, (_, a, b) =>
      "[" + [...new Set([...a.split(", "), ...b.split(", ")])].join(", ") + "]");
    return x;
  });
  return { textos: salida, refs: orden };
}

// Markdown en línea que escriben los modelos: `código`, **negrita** y *cursiva* (sobre texto ya escapado).
function formatoEnLinea(html) {
  return html
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^\w*])\*([^*\n]+)\*(?![\w*])/g, "$1<em>$2</em>");
}

// Escapa el texto y marca «[1, 2]» con la etiqueta de cada referencia como ayuda emergente.
function htmlConCitas(texto, refs) {
  return formatoEnLinea(esc(texto)).replace(/\[(\d+(?:, \d+)*)\]/g, (todo, nums) => {
    const titulos = nums.split(", ").map(n => refs[n - 1]).filter(Boolean)
      .map(r => etiquetaReferencia(r)).join("\n");
    return titulos ? `<span class="cita" title="${esc(titulos)}">${todo}</span>` : todo;
  });
}

function listaReferencias(refs) {
  if (!refs.length) return "";
  return `<p class="titulo-refs">Referencias</p><ul class="referencias">${refs.map((r, i) =>
    `<li><span class="cita">[${i + 1}]</span> ${esc(etiquetaReferencia(r))}</li>`).join("")}</ul>`;
}


// Editor de atributos del hallazgo seleccionado.
function pintarHallazgo(h) {
  const { textos, refs } = numerarCitas([h.explicacion || "", ...(h.correccion || [])], h.referencias);
  const explicacion = textos[0];
  const pasos = textos.slice(1).map(p => `<li>${htmlConCitas(p, refs)}</li>`).join("");
  const fuente = h.fuente ? `<details class="fuente"><summary>Fragmento: ${esc(h.fuente.titulo || h.fuente.documento)} › ${esc(h.fuente.seccion)}
      (puntaje ${Number(h.fuente.puntaje).toFixed(2)})</summary>
      <blockquote>${esc(h.fuente.fragmento)}</blockquote><p class="meta">${esc(h.fuente.documento)} · ${esc(h.fuente.id || "")}</p></details>` : "";
  const retro = h.gravedad === "informativo" ? "" : `<div class="retro" data-hallazgo="${esc(h.id)}">
      <input type="text" maxlength="2000" placeholder="Comentario sobre este hallazgo (opcional)">
      <button type="button" data-util="true" title="Útil">👍</button>
      <button type="button" data-util="false" title="No útil">👎</button><span class="meta"></span></div>`;
  const informativo = h.gravedad === "informativo"
    ? `<p class="meta">Hallazgo informativo: se lista sin explicación ni cita y no cambia el semáforo.</p>` : "";
  return `<article class="hallazgo ${esc(h.gravedad)}">
    <div class="cabecera-h">
      <h3>${esc(h.verificacion)} · ${esc(h.descripcion || h.tipo)}</h3>
      <div class="medido">
        <span class="k">Gravedad</span><span><span class="chip ${esc(h.gravedad)}">${esc(h.gravedad)}</span></span>
        <span class="k">Medido</span><span>${esc(formatoMedido(h.medido))}</span>
        <span class="k">Límite</span><span>${esc(h.limite)}</span>
        <span class="k">Id</span><span>${esc(h.id)}</span>
      </div>
    </div>
    <div class="cuerpo-h">
      ${informativo}
      ${explicacion ? `<div class="etiqueta-campo">Explicación</div><p>${htmlConCitas(explicacion, refs)}</p>` : ""}
      ${pasos ? `<div class="etiqueta-campo">Pasos de corrección</div><ol>${pasos}</ol>` : ""}
      ${listaReferencias(refs)}${fuente}${retro}
    </div></article>`;
}

// Retroalimentación por informe o por hallazgo (delegación de eventos).
document.addEventListener("click", async (evento) => {
  const boton = evento.target.closest(".retro button");
  if (!boton || !informeActual) return;
  const caja = boton.closest(".retro");
  const estado = caja.querySelector(".meta");
  const datos = {traza_id: informeActual.traza_id, util: boton.dataset.util === "true",
                 comentario: caja.querySelector("input").value || null,
                 hallazgo_id: caja.dataset.hallazgo || null};
  try {
    await API.retroalimentar(datos);
    estado.textContent = "¡Gracias!";
    caja.querySelectorAll("button").forEach(b => b.disabled = true);
  } catch (e) {
    estado.textContent = e.message;
  }
});

$("#exportar").addEventListener("click", async () => {
  if (!informeActual) return;
  try {
    const texto = await API.markdown(informeActual.auditoria_id);
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([texto], {type: "text/markdown"}));
    enlace.download = `auditoria-${informeActual.auditoria_id}.md`;
    enlace.click();
    mostrarEstado(`Informe exportado: ${enlace.download}`);
  } catch (e) {
    mostrarError(e.message);
  }
});

// ── Línea de comandos: preguntas de seguimiento ──────────────────────────
$("#alternar-historial").addEventListener("click", () => $("#preguntas").classList.toggle("abierta"));

$("#form-pregunta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!informeActual) return;
  const campo = $("#pregunta");
  const pregunta = campo.value.trim();
  if (!pregunta) return;
  $("#preguntas").classList.add("abierta");
  const nodo = document.createElement("div");
  nodo.className = "respuesta";
  nodo.innerHTML = `<p class="pregunta">${esc(pregunta)}</p><p class="meta">Pensando…</p>`;
  $("#respuestas").prepend(nodo);
  campo.value = "";
  try {
    const r = await API.preguntar(informeActual.auditoria_id, pregunta);
    const { textos: [respuesta], refs } = numerarCitas([r.respuesta], r.fuentes);
    const citadas = new Set(refs.flatMap(f => f.ids));
    const sinCitar = r.fuentes.filter(f => !citadas.has(f.id));
    const fuentes = [...refs, ...sinCitar].map((f, i) => `<details><summary>${i < refs.length ? `[${i + 1}] ` : ""}${esc(etiquetaReferencia(f))}
      ${f.puntaje != null ? `(${Number(f.puntaje).toFixed(2)})` : ""}</summary>${f.fragmento ? `<blockquote>${esc(f.fragmento)}</blockquote>` : ""}</details>`).join("");
    nodo.innerHTML = `<p class="pregunta">${esc(pregunta)}</p><p>${htmlConCitas(respuesta, refs)}</p>${fuentes}
      <p class="meta">Caché ${esc(r.cache)} · ruta ${esc(r.ruta)} · modelo ${esc(r.modelo)} ·
      guardrails ${esc(textoGuardrails(r.guardrails))}</p><p class="aviso">${esc(r.aviso)}</p>`;
  } catch (e) {
    nodo.innerHTML = `<p class="pregunta">${esc(pregunta)}</p><p class="error">${esc(e.message)}</p>`;
  }
});

cargarPerfiles();
pintarArbol();
