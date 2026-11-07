// Página principal: subir malla, ver el informe, retroalimentación, preguntas y exportación.
let informeActual = null;

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

function mostrarError(mensaje) {
  const nodo = $("#error");
  nodo.textContent = mensaje;
  nodo.classList.toggle("oculto", !mensaje);
}

// RF8: visor solo para GLB, cargando el archivo local del usuario.
$("#archivo").addEventListener("change", (evento) => {
  const archivo = evento.target.files[0];
  const visor = $("#visor");
  if (archivo && archivo.name.toLowerCase().endsWith(".glb")) {
    $("#modelo").src = URL.createObjectURL(archivo);
    visor.classList.remove("oculto");
  } else {
    visor.classList.add("oculto");
  }
});

$("#formulario").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mostrarError("");
  const boton = $("#enviar");
  boton.disabled = true;
  $("#estado").textContent = "Auditando…";
  try {
    informeActual = await API.auditar(new FormData(evento.target));
    pintarInforme(informeActual);
    $("#respuestas").innerHTML = "";
    $("#estado").textContent = `Listo en ${Math.round(informeActual.tiempo_ms)} ms.`;
  } catch (e) {
    mostrarError(e.message + (e.cuerpo && e.cuerpo.aviso ? ` — ${e.cuerpo.aviso}` : ""));
    $("#estado").textContent = "";
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

function pintarInforme(inf) {
  // Reinicia la valoración del informe anterior (la caja global no se vuelve a dibujar).
  document.querySelectorAll("#informe > .retro").forEach(caja => {
    caja.querySelectorAll("button").forEach(b => b.disabled = false);
    caja.querySelector("input").value = "";
    caja.querySelector(".meta").textContent = "";
  });
  $("#informe").classList.remove("oculto");
  $("#preguntas").classList.remove("oculto");
  const s = $("#semaforo");
  s.className = `semaforo ${inf.semaforo}`;
  s.textContent = inf.semaforo;
  $("#resumen").textContent = inf.resumen;
  $("#detalles").textContent = `Ruta ${inf.ruta} · modelo ${inf.modelo} · caché ${inf.cache}` +
    ` · guardrails ${textoGuardrails(inf.guardrails)} · iteraciones del agente ${inf.iteraciones_agente}` +
    ` · traza ${inf.traza_id}`;
  const m = inf.metricas_malla;
  $("#metricas").innerHTML = Object.entries(ETIQUETAS).filter(([k]) => k in m && m[k] !== null)
    .map(([k, etiqueta]) => {
      let v = m[k];
      if (k === "dimension_max") v = `${formatoMedido(v)} ${m.unidad}`;
      else if (Array.isArray(v)) v = v.map(formatoMedido).join(" × ") + ` ${m.unidad}`;
      else v = formatoMedido(v);
      return `<tr><th>${esc(etiqueta)}</th><td>${esc(v)}</td></tr>`;
    }).join("");
  $("#hallazgos").innerHTML = inf.hallazgos.length ? inf.hallazgos.map(pintarHallazgo).join("")
    : "<p>Sin hallazgos: la malla cumple el perfil.</p>";
  $("#aviso").textContent = inf.aviso;
}

function pintarHallazgo(h) {
  const pasos = (h.correccion || []).map(p => `<li>${esc(p)}</li>`).join("");
  const fuente = h.fuente ? `<details><summary>Fuente: ${esc(h.fuente.titulo || h.fuente.documento)} — ${esc(h.fuente.seccion)}
      (puntaje ${Number(h.fuente.puntaje).toFixed(2)})</summary>
      <blockquote>${esc(h.fuente.fragmento)}</blockquote><p class="meta">${esc(h.fuente.documento)} · ${esc(h.fuente.id || "")}</p></details>` : "";
  const retro = h.gravedad === "informativo" ? "" : `<div class="retro" data-hallazgo="${esc(h.id)}">
      <input type="text" maxlength="2000" placeholder="Comentario sobre este hallazgo (opcional)">
      <button class="secundario" data-util="true">👍</button>
      <button class="secundario" data-util="false">👎</button><span class="meta"></span></div>`;
  return `<article class="hallazgo ${esc(h.gravedad)}">
    <h3>${esc(h.id)} · ${esc(h.verificacion)} · ${esc(h.descripcion || h.tipo)} <span class="chip ${esc(h.gravedad)}">${esc(h.gravedad)}</span></h3>
    <p class="medido">Medido: <strong>${esc(formatoMedido(h.medido))}</strong> · Límite: ${esc(h.limite)}</p>
    ${h.explicacion ? `<p>${esc(h.explicacion)}</p>` : ""}
    ${pasos ? `<strong>Pasos de corrección</strong><ol>${pasos}</ol>` : ""}
    ${fuente}${retro}</article>`;
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
  } catch (e) {
    mostrarError(e.message);
  }
});

$("#form-pregunta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (!informeActual) return;
  const campo = $("#pregunta");
  const pregunta = campo.value.trim();
  if (!pregunta) return;
  const nodo = document.createElement("div");
  nodo.className = "respuesta";
  nodo.innerHTML = `<p><strong>${esc(pregunta)}</strong></p><p class="meta">Pensando…</p>`;
  $("#respuestas").prepend(nodo);
  campo.value = "";
  try {
    const r = await API.preguntar(informeActual.auditoria_id, pregunta);
    const fuentes = r.fuentes.map(f => `<details><summary>${esc(f.titulo || f.documento)} — ${esc(f.seccion)}
      (${Number(f.puntaje).toFixed(2)})</summary><blockquote>${esc(f.fragmento)}</blockquote></details>`).join("");
    nodo.innerHTML = `<p><strong>${esc(pregunta)}</strong></p><p>${esc(r.respuesta)}</p>${fuentes}
      <p class="meta">Caché ${esc(r.cache)} · ruta ${esc(r.ruta)} · modelo ${esc(r.modelo)} ·
      guardrails ${esc(textoGuardrails(r.guardrails))}</p><p class="aviso">${esc(r.aviso)}</p>`;
  } catch (e) {
    nodo.innerHTML = `<p><strong>${esc(pregunta)}</strong></p><p class="error">${esc(e.message)}</p>`;
  }
});

cargarPerfiles();
