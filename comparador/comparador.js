// Muestra los precios comparados:
//  - data/precios.json: comparación diaria (GitHub Actions, scraper/comparar.py)
//  - Firestore "precios": comparaciones hechas al momento desde esta página (servidor en Render)
import { auth, db, onAuthStateChanged, collection, getDocs } from "../js/services/firebase.js";
import { API_URL } from "./config.js";
const $ = id => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const cop = n => n == null ? "—" : "$ " + Math.round(n).toLocaleString("es-CO");
const VER = { mismo: "Mismo producto", posible: "Posible", alternativa: "Alternativa", distinto: "Distinto" };

let datos = { productos: [] }, diarios = [], alMomento = [], usuario = null;

function foto(src, cls = "cfoto"){
  if (!src) return el("div", cls, "📦");
  const i = el("img", cls); i.src = src; i.alt = ""; i.loading = "lazy";
  i.onerror = () => i.replaceWith(el("div", cls, "📦"));
  return i;
}

function specsChips(s, conflictos = []){
  const box = el("div", "specs");
  const add = (txt, clave) => box.append(el("span", "spec" + (conflictos.includes(clave) ? " conf" : ""), txt));
  if (s.chips) add("Chip " + s.chips.join(" / "), "chips");
  if (s.corriente_a) add(s.corriente_a + " A", "corriente_a");
  if (s.vin) add("Entrada " + s.vin[0] + "–" + s.vin[1] + " V", "vin");
  if (s.vout) add("Salida " + s.vout[0] + "–" + s.vout[1] + " V", "vout");
  if (s.potencia_w) add(s.potencia_w + " W", "potencia_w");
  if (s.frecuencia_khz) add(s.frecuencia_khz + " kHz", "frecuencia_khz");
  if (s.eficiencia_pct) add(s.eficiencia_pct + " % efic.", "eficiencia_pct");
  if (s.dimensiones_mm) add(s.dimensiones_mm.join("×") + " mm", "dimensiones_mm");
  return box;
}

function precio(p){
  const box = el("div", "cprecio", cop(p.precio_con_iva));
  const nota = p.iva_incluido === false ? cop(p.precio) + " + IVA" : p.iva_incluido === true ? "IVA incluido" : "IVA sin confirmar";
  box.append(el("small", null, nota));
  return box;
}

function barra(nombre, v){
  const f = document.createDocumentFragment();
  const b = el("div", "barra"), i = el("i"); i.style.width = (v ?? 0) + "%"; b.append(i);
  f.append(el("span", null, nombre), b, el("span", null, v == null ? "sin dato" : Math.round(v) + ""));
  return f;
}

function candidato(c){
  const fila = el("div", "cand");
  fila.append(foto(c.imagen));
  const info = el("div");
  const h = el("h3"); const a = el("a", null, c.nombre); a.href = c.url; a.target = "_blank"; a.rel = "noopener";
  h.append(el("span", "veredicto " + c.veredicto, VER[c.veredicto]), a);
  info.append(h, el("div", "csub", (c.sku ? "Ref. " + c.sku : "")));
  const conf = c.motivos.filter(m => /distint/.test(m)).map(m => /chip/.test(m) ? "chips" : /corriente/.test(m) ? "corriente_a" : "");
  info.append(specsChips(c.specs || {}, conf));
  if (c.motivos.length) info.append(el("div", "motivos", c.motivos.join(" · ")));
  const p = el("div", "puntajes");
  p.append(barra("Características", c.puntajes.specs), barra("Descripción", c.puntajes.descripcion), barra("Foto", c.puntajes.foto), barra("Total", c.puntajes.total));
  info.append(p);
  const der = precio(c);
  if (c.diferencia_pct != null) {
    const d = c.diferencia_pct;
    der.append(el("div", "dif " + (d > 0 ? "mas" : d < 0 ? "menos" : ""), d === 0 ? "Mismo precio" : (d > 0 ? "+" : "") + d + " % vs Suconel"));
  }
  fila.append(info, der);
  return fila;
}

function render(){
  const lista = $("lista"); lista.textContent = "";
  const q = $("buscar").value.trim().toLowerCase(), verDist = $("verDistintos").checked;
  const prods = datos.productos.filter(p => {
    if (!q) return true;
    const r = p.referencia, hay = [r.nombre, r.sku, ...(r.specs.chips || [])].join(" ").toLowerCase();
    return hay.includes(q) || p.competidores.some(c => c.candidatos.some(x => (x.nombre + " " + x.sku).toLowerCase().includes(q)));
  });
  if (!prods.length) {
    lista.append(el("div", "rempty", q ? "Ese producto todavía no está en el comparador. Pega su URL de Suconel arriba y toca «Comparar»." : "Todavía no hay productos comparados."));
    return;
  }
  prods.forEach(p => {
    const r = p.referencia, card = el("section", "cprod");
    const ref = el("div", "cref"), info = el("div"), h = el("h2"), a = el("a", null, r.nombre);
    a.href = r.url; a.target = "_blank"; a.rel = "noopener"; h.append(a);
    const sub = el("div", "csub", "Suconel · Ref. " + r.sku);
    if (p.generado) sub.append(el("span", "corigen", "Comparado " + fecha(p.generado) + (p.pedido_por ? " por @" + p.pedido_por : "")));
    info.append(h, sub, specsChips(r.specs || {}));
    ref.append(foto(r.imagen), info, precio(r));
    card.append(ref);
    p.competidores.forEach(c => {
      const t = el("div", "ctienda", c.tienda);
      if (c.estado !== "ok") t.append(el("span", "cestado " + c.estado, c.estado === "bloqueado" ? "La tienda bloqueó la consulta" : "Error al consultar"));
      if (c.via === "firecrawl") t.append(el("span", "cestado via", "Leído con Firecrawl"));
      if (c.datos_de) t.append(el("span", "cestado viejo", "Mostrando datos del " + new Date(c.datos_de).toLocaleDateString("es-CO")));
      card.append(t);
      const cands = c.candidatos.filter(x => verDist || x.veredicto !== "distinto");
      if (!cands.length) card.append(el("div", "vacio", c.candidatos.length ? "Solo hay productos descartados (activa «Mostrar descartados»)." : "No se encontraron productos."));
      cands.forEach(x => card.append(candidato(x)));
    });
    lista.append(card);
  });
}

const fecha = iso => new Date(iso).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

// Une la comparación diaria con las hechas al momento (gana la más reciente de cada producto).
function unir(){
  const porId = new Map();
  [...diarios, ...alMomento].forEach(p => {
    const prev = porId.get(p.id);
    if (!prev || (p.generado || "") >= (prev.generado || "")) porId.set(p.id, p);
  });
  const lista = [...porId.values()].sort((a, b) => (b.generado || "").localeCompare(a.generado || ""));
  datos = { ...datos, productos: lista };
  render();
}

async function cargarDiario(){
  try {
    const r = await fetch("data/precios.json", { cache: "no-store" });
    const d = await r.json();
    diarios = d.productos.map(p => ({ ...p, generado: p.generado || d.generado }));
    $("generado").textContent = "Comparación diaria: " + fecha(d.generado);
    $("nota").textContent = d.nota || "";
  } catch (e) { diarios = []; }
  unir();
}

async function cargarFirestore(){
  if (!usuario) { alMomento = []; unir(); return; }
  try {
    const snap = await getDocs(collection(db, "precios"));
    alMomento = snap.docs.map(d => d.data());
  } catch (e) { alMomento = []; }   // usuario no aprobado o reglas sin publicar
  unir();
}

function msg(t, cls){ const m = $("msgComparar"); m.textContent = t || ""; m.className = "cmsg" + (cls ? " " + cls : ""); }

async function compararAhora(ev){
  ev.preventDefault();
  if (!usuario) return msg("Inicia sesión en Evaluaciones (con una cuenta aprobada) para comparar productos.", "err");
  const url = $("urlComparar").value.trim();
  const btn = $("btnComparar"); btn.disabled = true;
  msg("Comparando… puede tardar hasta 1 minuto (más si el servidor estaba dormido).");
  const t0 = Date.now(), reloj = setInterval(() => msg("Comparando… " + Math.round((Date.now() - t0) / 1000) + " s"), 1000);
  try {
    const token = await usuario.getIdToken();
    const r = await fetch(API_URL + "/comparar", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: JSON.stringify({ url }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.detail || "Error " + r.status);
    alMomento = [d, ...alMomento.filter(p => p.id !== d.id)];
    $("buscar").value = ""; unir();
    msg("✓ Listo: " + d.referencia.nombre, "ok");
    $("urlComparar").value = "";
  } catch (e) {
    msg(e.message === "Failed to fetch" ? "No se pudo conectar con el servidor del comparador. Intenta de nuevo en un minuto." : e.message, "err");
  } finally { clearInterval(reloj); btn.disabled = false; }
}

$("buscar").addEventListener("input", render);
$("verDistintos").addEventListener("change", render);
$("formComparar").addEventListener("submit", compararAhora);
onAuthStateChanged(auth, u => { usuario = u; cargarFirestore(); });
cargarDiario();
