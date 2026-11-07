// Cliente mínimo de la API de MeshAudit. La web solo habla con la API:
// nunca llama a Ollama ni a ChromaDB.
const API = (() => {
  const parametros = new URLSearchParams(location.search);
  const base = (parametros.get("api") || localStorage.getItem("meshaudit_api") ||
                "http://127.0.0.1:8000").replace(/\/$/, "");
  if (parametros.get("api")) localStorage.setItem("meshaudit_api", base);

  async function pedir(ruta, opciones = {}) {
    let respuesta;
    try {
      respuesta = await fetch(base + ruta, opciones);
    } catch (e) {
      throw new Error(`No se pudo contactar la API en ${base}. ¿Está corriendo el servicio?`);
    }
    const tipo = respuesta.headers.get("content-type") || "";
    const cuerpo = tipo.includes("application/json") ? await respuesta.json() : await respuesta.text();
    if (!respuesta.ok) {
      const detalle = typeof cuerpo === "object"
        ? (Array.isArray(cuerpo.detail) ? cuerpo.detail.map(d => d.msg).join("; ") : (cuerpo.detalle || cuerpo.detail))
        : cuerpo;
      const error = new Error(`${respuesta.status}: ${detalle || "error"}`);
      error.cuerpo = cuerpo;
      error.estado = respuesta.status;
      throw error;
    }
    return cuerpo;
  }
  const json = (ruta, datos) => pedir(ruta, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(datos)});
  return {
    base,
    salud: () => pedir("/health").catch(e => ({estado: "caido", detalle: e.message, ...(e.cuerpo || {})})),
    perfiles: () => pedir("/perfiles"),
    configuracion: () => pedir("/configuracion"),
    metricas: () => pedir("/metricas"),
    auditar: (formulario) => pedir("/auditorias", {method: "POST", body: formulario}),
    auditoria: (id) => pedir(`/auditorias/${encodeURIComponent(id)}`),
    markdown: (id) => pedir(`/auditorias/${encodeURIComponent(id)}/markdown`),
    preguntar: (id, pregunta) => json(`/auditorias/${encodeURIComponent(id)}/preguntas`, {pregunta}),
    retroalimentar: (datos) => json("/retroalimentacion", datos),
    documentos: () => pedir("/documentos"),
    subirDocumento: (formulario) => pedir("/documentos", {method: "POST", body: formulario}),
    borrarDocumento: (id) => pedir(`/documentos/${encodeURIComponent(id)}`, {method: "DELETE"}),
  };
})();

// Utilidades de presentación compartidas.
function esc(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, c => (
    {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}
function $(selector, raiz = document) { return raiz.querySelector(selector); }
function formatoMedido(v) {
  if (typeof v === "boolean") return v ? "sí" : "no";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("es-MX") : v.toLocaleString("es-MX", {maximumFractionDigits: 4});
  return v;
}
async function pintarSalud() {
  const nodo = $("#salud");
  if (!nodo) return;
  const s = await API.salud();
  const ok = s.estado === "ok";
  nodo.textContent = `${ok ? "●" : "○"} API ${s.estado}${s.proveedor ? " · proveedor " + s.proveedor : ""}`;
  nodo.style.color = ok ? "var(--verde)" : "var(--rojo)";
  nodo.title = JSON.stringify(s.componentes || s.detalle || {}, null, 1);
}
document.addEventListener("DOMContentLoaded", pintarSalud);
