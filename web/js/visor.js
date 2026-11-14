// Vista 3D de la malla abierta (solo en el navegador: el archivo no sale del equipo para esto).
// Usa three.js local (web/vendor/three), así que funciona sin red.
// Las ayudas visuales (caras traseras, bordes abiertos, aristas no manifold) son una vista
// aproximada para ubicar los problemas; las cifras oficiales son las del analizador del servicio.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { PLYLoader } from "three/addons/loaders/PLYLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { mergeVertices } from "three/addons/utils/BufferGeometryUtils.js";

const lienzo = document.getElementById("lienzo");
const gizmo = document.getElementById("gizmo");
const ctxGizmo = gizmo.getContext("2d");
const leyenda = document.getElementById("leyenda");

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(0x000000, 0);
lienzo.prepend(renderer.domElement);

const escena = new THREE.Scene();
const camara = new THREE.PerspectiveCamera(35, 1, 0.01, 1000);
camara.position.set(6, 4.5, 7.5);
escena.add(camara);
const controles = new OrbitControls(camara, renderer.domElement);
controles.enableDamping = true;
controles.dampingFactor = 0.18;
controles.screenSpacePanning = true;

// Iluminación por defecto: hemisférica más una luz que sigue a la cámara.
escena.add(new THREE.HemisphereLight(0xffffff, 0x3a3f45, 1.15));
const luz = new THREE.DirectionalLight(0xffffff, 1.9);
luz.position.set(0.6, 0.9, 1);
camara.add(luz);

const MAT_SOMBREADO = new THREE.MeshStandardMaterial({
  color: 0xa3a3a3, roughness: 0.8, metalness: 0, side: THREE.FrontSide,
  polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
const MAT_TRASERA = new THREE.MeshBasicMaterial({ color: 0xd04a46, side: THREE.BackSide });
const MAT_TRASERA_NEUTRA = new THREE.MeshStandardMaterial({ color: 0x6d6d6d, roughness: 0.9, side: THREE.BackSide });
const MAT_ALAMBRE = new THREE.LineBasicMaterial({ color: 0x0e1f3d, transparent: true, opacity: 0.75 });
const MAT_ALAMBRE_SOLO = new THREE.LineBasicMaterial({ color: 0x0d2147 });
const MAT_ABIERTO = new THREE.LineBasicMaterial({ color: 0xff9a1f, depthTest: false });
const MAT_NO_MANIFOLD = new THREE.LineBasicMaterial({ color: 0xff3df0, depthTest: false });

const estado = { modo: "sombreado", alambreEncima: false, traseras: false, bordes: false, rejilla: true };
let raiz = null;               // grupo con la malla cargada
let mallas = [];               // { malla, original, alambre, trasera, bordes }
let rejilla = null;
let estadisticas = null;
let tieneMateriales = false;

function crearRejilla(tam) {
  if (rejilla) { escena.remove(rejilla); rejilla.geometry.dispose(); rejilla.material.dispose(); }
  rejilla = new THREE.GridHelper(tam, 20, 0x101214, 0x353b42);
  rejilla.material.transparent = true;
  rejilla.material.opacity = 0.85;
  rejilla.visible = estado.rejilla;
  rejilla.renderOrder = -1;
  escena.add(rejilla);
}
crearRejilla(10);

// ── Carga ────────────────────────────────────────────────────────────────
async function cargar(archivo) {
  const ext = archivo.name.split(".").pop().toLowerCase();
  const url = URL.createObjectURL(archivo);
  let objeto;
  try {
    if (ext === "glb" || ext === "gltf") {
      objeto = (await new GLTFLoader().loadAsync(url)).scene;
    } else if (ext === "obj") {
      objeto = await new OBJLoader().loadAsync(url);
    } else if (ext === "stl" || ext === "ply") {
      const geo = await (ext === "stl" ? new STLLoader() : new PLYLoader()).loadAsync(url);
      objeto = new THREE.Mesh(geo);
    } else {
      throw new Error(`Formato .${ext} no soportado por la vista 3D.`);
    }
  } finally {
    URL.revokeObjectURL(url);
  }
  montar(objeto, ext);
  return estadisticas;
}

function liberar() {
  if (!raiz) return;
  escena.remove(raiz);
  raiz.traverse(o => {
    if (o.geometry) o.geometry.dispose();
  });
  raiz = null;
  mallas = [];
}

function montar(objeto, ext) {
  liberar();
  raiz = new THREE.Group();
  raiz.add(objeto);
  escena.add(raiz);
  raiz.updateMatrixWorld(true);
  tieneMateriales = ext === "glb" || ext === "gltf";

  let vertices = 0, triangulos = 0, abiertas = 0, noManifold = 0, mallasCount = 0;
  // Primero se reúnen las mallas: las capas de ayuda que se añaden después también son mallas.
  const encontradas = [];
  objeto.traverse(o => {
    if (o.isMesh && o.geometry && o.geometry.getAttribute("position")) encontradas.push(o);
  });
  encontradas.forEach(o => {
    mallasCount++;
    const geo = o.geometry;
    if (!geo.getAttribute("normal")) geo.computeVertexNormals();
    triangulos += geo.index ? geo.index.count / 3 : geo.getAttribute("position").count / 3;

    const caja = new THREE.Box3().setFromBufferAttribute(geo.getAttribute("position"));
    const tolerancia = Math.max(caja.getSize(new THREE.Vector3()).length() * 1e-6, 1e-9);
    const topo = topologia(geo, tolerancia);
    vertices += topo.vertices;
    abiertas += topo.abiertas.length / 6;
    noManifold += topo.noManifold.length / 6;

    const alambre = new THREE.LineSegments(new THREE.WireframeGeometry(geo), MAT_ALAMBRE);
    const trasera = new THREE.Mesh(geo, MAT_TRASERA_NEUTRA);
    const bordes = new THREE.Group();
    if (topo.abiertas.length) bordes.add(lineas(topo.abiertas, MAT_ABIERTO));
    if (topo.noManifold.length) bordes.add(lineas(topo.noManifold, MAT_NO_MANIFOLD));
    bordes.renderOrder = 10;
    o.add(alambre, trasera, bordes);
    mallas.push({ malla: o, original: o.material, alambre, trasera, bordes });
  });

  estadisticas = { mallas: mallasCount, vertices, triangulos: Math.round(triangulos),
                   abiertas, noManifold, ...medidas() };
  aplicar();
  encuadrar();
  lienzo.dispatchEvent(new CustomEvent("visor:cargado", { detail: estadisticas }));
}

function lineas(posiciones, material) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(posiciones, 3));
  const l = new THREE.LineSegments(geo, material);
  l.renderOrder = 10;
  return l;
}

// Une vértices por posición y cuenta cuántas caras usa cada arista:
// 1 = borde abierto, más de 2 = arista no manifold.
function topologia(geo, tolerancia) {
  const soloPosicion = new THREE.BufferGeometry();
  soloPosicion.setAttribute("position", geo.getAttribute("position"));
  if (geo.index) soloPosicion.setIndex(geo.index);
  const unida = mergeVertices(soloPosicion, tolerancia);
  const indice = unida.index.array;
  const pos = unida.getAttribute("position");
  const n = pos.count;
  const usos = new Map();
  const sumar = (a, b) => {
    if (a === b) return;
    const k = a < b ? a * n + b : b * n + a;
    usos.set(k, (usos.get(k) || 0) + 1);
  };
  for (let i = 0; i + 2 < indice.length; i += 3) {
    sumar(indice[i], indice[i + 1]);
    sumar(indice[i + 1], indice[i + 2]);
    sumar(indice[i + 2], indice[i]);
  }
  const abiertas = [], noManifold = [];
  for (const [k, c] of usos) {
    if (c === 2) continue;
    const a = Math.floor(k / n), b = k % n;
    (c === 1 ? abiertas : noManifold).push(
      pos.getX(a), pos.getY(a), pos.getZ(a), pos.getX(b), pos.getY(b), pos.getZ(b));
  }
  const vertices = n;
  unida.dispose();
  return { vertices, abiertas, noManifold };
}

function medidas() {
  const caja = new THREE.Box3().setFromObject(raiz);
  const t = caja.getSize(new THREE.Vector3());
  return { dimensiones: [t.x, t.y, t.z], caja };
}

// ── Modos de visualización ───────────────────────────────────────────────
function aplicar() {
  for (const m of mallas) {
    const soloAlambre = estado.modo === "alambre";
    m.malla.material = estado.modo === "texturas" && tieneMateriales ? m.original : MAT_SOMBREADO;
    m.malla.material.visible = !soloAlambre;
    if (m.original && m.original !== MAT_SOMBREADO) {
      // El material original puede ser de doble cara; las traseras se dibujan aparte.
      const originales = Array.isArray(m.original) ? m.original : [m.original];
      originales.forEach(mat => { mat.visible = !soloAlambre; });
    }
    m.alambre.visible = soloAlambre || estado.alambreEncima;
    m.alambre.material = soloAlambre ? MAT_ALAMBRE_SOLO : MAT_ALAMBRE;
    m.trasera.visible = !soloAlambre;
    m.trasera.material = estado.traseras ? MAT_TRASERA : MAT_TRASERA_NEUTRA;
    m.bordes.visible = estado.bordes;
  }
  if (rejilla) rejilla.visible = estado.rejilla;
  pintarLeyenda();
  document.dispatchEvent(new CustomEvent("visor:estado", { detail: { ...estado } }));
}

function pintarLeyenda() {
  const items = [];
  if (estado.traseras) items.push(`<span><i style="background:#d04a46"></i>caras traseras</span>`);
  if (estado.bordes && estadisticas) {
    items.push(`<span><i style="background:#ff9a1f"></i>bordes abiertos (${estadisticas.abiertas})</span>`);
    items.push(`<span><i style="background:#ff3df0"></i>no manifold (${estadisticas.noManifold})</span>`);
  }
  leyenda.innerHTML = items.join("") + (items.length ? "<br>vista aproximada; las cifras del informe son las del analizador" : "");
  leyenda.classList.toggle("oculto", !items.length);
}

function modo(nuevo) {
  estado.modo = nuevo;
  aplicar();
}

function alternar(clave, valor) {
  estado[clave] = valor === undefined ? !estado[clave] : !!valor;
  aplicar();
}

function encuadrar() {
  if (!raiz) return;
  const caja = new THREE.Box3().setFromObject(raiz);
  if (caja.isEmpty()) return;
  const centro = caja.getCenter(new THREE.Vector3());
  const radio = Math.max(caja.getSize(new THREE.Vector3()).length() / 2, 1e-6);
  const distancia = radio / Math.sin(THREE.MathUtils.degToRad(camara.fov / 2)) * 1.15;
  const direccion = camara.position.clone().sub(controles.target).normalize();
  if (!isFinite(direccion.x) || direccion.lengthSq() === 0) direccion.set(0.6, 0.45, 0.75).normalize();
  controles.target.copy(centro);
  camara.position.copy(centro).addScaledVector(direccion, distancia);
  camara.near = distancia / 500;
  camara.far = distancia * 200;
  camara.updateProjectionMatrix();
  controles.update();
  // Rejilla en el suelo del modelo, con un tamaño redondo a su escala.
  const mayor = Math.max(...caja.getSize(new THREE.Vector3()).toArray());
  const tam = Math.pow(10, Math.ceil(Math.log10(mayor * 2)));
  crearRejilla(tam);
  rejilla.position.set(0, caja.min.y, 0);
}

// ── Bucle de dibujo, tamaño y eje de orientación ─────────────────────────
function ajustarTamano() {
  const { clientWidth: w, clientHeight: h } = lienzo;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camara.aspect = w / h;
  camara.updateProjectionMatrix();
}
new ResizeObserver(ajustarTamano).observe(lienzo);
ajustarTamano();

const EJES = [
  { v: new THREE.Vector3(1, 0, 0), color: "#e2504c", etiqueta: "X" },
  { v: new THREE.Vector3(0, 1, 0), color: "#7fcf3e", etiqueta: "Y" },
  { v: new THREE.Vector3(0, 0, 1), color: "#4c8be2", etiqueta: "Z" },
];
function dibujarGizmo() {
  const s = gizmo.width, c = s / 2, r = s * 0.32;
  ctxGizmo.clearRect(0, 0, s, s);
  const inversa = camara.quaternion.clone().invert();
  const proyectados = EJES.map(e => ({ ...e, p: e.v.clone().applyQuaternion(inversa) }))
    .sort((a, b) => a.p.z - b.p.z);
  ctxGizmo.lineWidth = 4;
  ctxGizmo.font = `bold ${Math.round(s * 0.15)}px -apple-system, Segoe UI, sans-serif`;
  ctxGizmo.textAlign = "center";
  ctxGizmo.textBaseline = "middle";
  for (const e of proyectados) {
    const x = c + e.p.x * r, y = c - e.p.y * r;
    ctxGizmo.strokeStyle = e.color;
    ctxGizmo.beginPath(); ctxGizmo.moveTo(c, c); ctxGizmo.lineTo(x, y); ctxGizmo.stroke();
    ctxGizmo.fillStyle = e.color;
    ctxGizmo.fillText(e.etiqueta, c + e.p.x * r * 1.32, c - e.p.y * r * 1.32);
  }
}

renderer.setAnimationLoop(() => {
  controles.update();
  renderer.render(escena, camara);
  dibujarGizmo();
});

// ── Atajos de teclado (fuera de campos de texto) ─────────────────────────
document.addEventListener("keydown", (e) => {
  const t = e.target;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (t.closest && t.closest("input, textarea, select, [contenteditable]")) return;
  const tecla = e.key.toLowerCase();
  const acciones = {
    f: encuadrar, 4: () => modo("alambre"), 5: () => modo("sombreado"), 6: () => modo("texturas"),
    w: () => alternar("alambreEncima"), b: () => alternar("traseras"), e: () => alternar("bordes"),
    g: () => alternar("rejilla"),
  };
  if (acciones[tecla]) { acciones[tecla](); e.preventDefault(); }
});

window.Visor = { cargar, modo, alternar, encuadrar, estado,
                 get estadisticas() { return estadisticas; } };
document.dispatchEvent(new CustomEvent("visor:listo"));
