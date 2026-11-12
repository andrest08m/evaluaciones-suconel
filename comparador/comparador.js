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
  if (p.precio == null) {
    const box = el("div", "cprecio sinprecio", "Sin precio");
    box.append(el("small", null, p.tienda === "Suconel" ? "Se cotiza por WhatsApp" : "No publicado"));
    return box;
  }
  const box = el("div", "cprecio", cop(p.precio_con_iva));
  const nota = p.iva_incluido === false ? cop(p.precio) + " + IVA" : p.iva_incluido === true ? "IVA incluido" : "IVA sin confirmar";
  box.append(el("small", null, nota));
  return box;
}

function difTexto(d){
  if (d == null) return null;
  return el("div", "dif " + (d > 0 ? "mas" : d < 0 ? "menos" : ""),
    d === 0 ? "Mismo precio" : d > 0 ? "Suconel " + d + " % más barato" : "Suconel " + Math.abs(d) + " % más caro");
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
  const der = precio(c), dif = difTexto(c.diferencia_pct);
  if (dif) der.append(dif);
  fila.append(info, der);
  return fila;
}

// Mejor candidato de una tienda: el primero que no sea «distinto» (ya vienen ordenados).
const mejorDe = c => c.candidatos.find(x => x.veredicto !== "distinto");
const TOL = 2;   // ±2 % se considera «igual»

function productosVisibles(){
  const q = $("buscar").value.trim().toLowerCase();
  return datos.productos.filter(p => {
    if (!q) return true;
    const r = p.referencia, hay = [r.nombre, r.sku, ...((r.specs || {}).chips || [])].join(" ").toLowerCase();
    return hay.includes(q) || p.competidores.some(c => c.candidatos.some(x => (x.nombre + " " + x.sku).toLowerCase().includes(q)));
  });
}

// Resumen por tienda a partir de los productos visibles. diferencia_pct > 0: Suconel más barato.
function resumen(prods){
  const por = new Map();
  prods.forEach(p => p.competidores.forEach(c => {
    const r = por.get(c.tienda) || { tienda: c.tienda, comparados: 0, coinciden: 0, difs: [], barato: 0 };
    por.set(c.tienda, r);
    r.comparados++;
    const m = mejorDe(c);
    if (!m || m.veredicto === "alternativa") return;
    r.coinciden++;
    if (m.diferencia_pct == null) return;
    r.difs.push(m.diferencia_pct);
    if (m.diferencia_pct > TOL) r.barato++;
  }));
  return [...por.values()];
}

function pintarResumen(prods){
  const box = $("resumen"); box.textContent = "";
  resumen(prods).forEach(r => {
    const card = el("div", "cres"), prom = r.difs.length ? r.difs.reduce((a, b) => a + b, 0) / r.difs.length : null;
    card.append(el("h3", null, r.tienda));
    const n = (txt, num, resto) => { const d = el("div"); d.append(el("b", null, num), " " + resto); return d; };
    card.append(n(0, r.comparados, r.comparados === 1 ? "producto comparado" : "productos comparados"),
                n(0, r.coinciden, "con coincidencia (mismo/posible)"));
    const dif = el("div", "cdif" + (prom == null ? "" : prom > 0 ? " mas" : prom < 0 ? " menos" : ""),
      prom == null ? "Diferencia promedio: —" : "Diferencia promedio: " + (prom > 0 ? "+" : "") + (Math.round(prom * 10) / 10).toLocaleString("es-CO") + " %");
    dif.title = "Positivo: Suconel más barato. Negativo: Suconel más caro.";
    card.append(dif, el("div", null, "Suconel más barato en " + r.barato + " de " + r.difs.length));
    box.append(card);
  });
  $("btnCsv").disabled = !prods.some(p => p.competidores.some(mejorDe));
}

const COLS_CSV = ["fecha", "id", "categoria", "sku_suconel", "nombre_suconel", "precio_suconel_con_iva", "tienda", "veredicto",
  "sku_competidor", "nombre_competidor", "precio_competidor", "precio_competidor_con_iva", "iva_incluido", "diferencia_pct", "puntaje_total", "url_competidor"];

function filasCsv(prods){
  const filas = [];
  prods.forEach(p => p.competidores.forEach(c => {
    const m = mejorDe(c); if (!m) return;
    const r = p.referencia;
    filas.push([(p.generado || "").slice(0, 10), p.id, p.categoria || "", r.sku, r.nombre, r.precio_con_iva, c.tienda, m.veredicto,
      m.sku, m.nombre, m.precio, m.precio_con_iva, m.iva_incluido, m.diferencia_pct, m.puntajes && m.puntajes.total, m.url]);
  }));
  return filas;
}

const celdaCsv = v => {
  const t = v == null ? "" : String(v);
  return /[;"\n\r]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
};

function descargarCsv(){
  const filas = filasCsv(productosVisibles());
  if (!filas.length) return;
  const txt = "\ufeff" + [COLS_CSV, ...filas].map(f => f.map(celdaCsv).join(";")).join("\r\n") + "\r\n";
  const url = URL.createObjectURL(new Blob([txt], { type: "text/csv;charset=utf-8" }));
  const a = el("a"); a.href = url; a.download = "comparador-suconel-" + new Date().toISOString().slice(0, 10) + ".csv";
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function render(){
  const lista = $("lista"); lista.textContent = "";
  const q = $("buscar").value.trim(), verDist = $("verDistintos").checked;
  const prods = productosVisibles();
  pintarResumen(prods);
  if (!prods.length) {
    lista.append(el("div", "rempty", q ? "Ese producto todavía no está en el comparador. Pega su URL de Suconel arriba y toca «Comparar»." : "Todavía no hay productos comparados."));
    return;
  }
  prods.forEach(p => {
    const r = p.referencia, card = el("section", "cprod");
    const ref = el("div", "cref"), info = el("div"), h = el("h2"), a = el("a", null, r.nombre);
    a.href = r.url; a.target = "_blank"; a.rel = "noopener"; h.append(a);
    const sub = el("div", "csub", "Suconel · Ref. " + (r.sku || "—"));
    if (p.generado) sub.append(el("span", "corigen", "Comparado " + fecha(p.generado) + (p.pedido_por ? " por @" + p.pedido_por : "")));
    info.append(h, sub, specsChips(r.specs || {}));
    const der = precio(r);
    const upd = el("button", "mini actualizar", "🔄 Actualizar"); upd.title = "Volver a comparar este producto ahora";
    upd.onclick = () => compararUrl(r.url, upd);
    der.append(upd);
    ref.append(foto(r.imagen), info, der);
    card.append(ref);

    p.competidores.forEach(c => {
      const t = el("div", "ctienda", c.tienda);
      if (c.estado !== "ok") {
        const txt = { bloqueado: "La tienda bloqueó la consulta", limite: "Se alcanzó el límite diario de Firecrawl — intenta mañana", error: "Error al consultar" }[c.estado] || "Error al consultar";
        const e = el("span", "cestado " + (c.estado === "limite" ? "viejo" : c.estado), txt);
        if (c.error) e.title = c.error;
        t.append(e);
      }
      if (c.via === "firecrawl") t.append(el("span", "cestado via", "Leído con Firecrawl"));
      if (c.datos_de) t.append(el("span", "cestado viejo", "Datos del " + new Date(c.datos_de).toLocaleDateString("es-CO")));
      card.append(t);

      // Solo la mejor coincidencia a la vista; el resto, en "Ver detalles".
      const visibles = c.candidatos.filter(x => verDist || x.veredicto !== "distinto");
      if (!visibles.length) {
        card.append(el("div", "vacio", c.candidatos.length ? "No se encontró un producto equivalente (hay " + c.candidatos.length + " descartados)." : "No se encontraron productos."));
        return;
      }
      card.append(candidato(visibles[0]));
      const resto = visibles.slice(1);
      if (resto.length) {
        const det = el("details", "cmas");
        det.append(el("summary", null, "Ver " + resto.length + (resto.length === 1 ? " resultado más" : " resultados más")));
        resto.forEach(x => det.append(candidato(x)));
        card.append(det);
      }
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
    $("generado").textContent = diarios.length ? "Comparación diaria: " + fecha(d.generado) : "";
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

async function compararUrl(url, btn){
  if (!usuario) return msg("Inicia sesión en Evaluaciones (con una cuenta aprobada) para comparar productos.", "err");
  const textoBtn = btn.textContent; btn.disabled = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
  msg("Comparando… puede tardar 1 a 3 minutos (más si el servidor estaba dormido).");
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
    return true;
  } catch (e) {
    msg(e.message === "Failed to fetch" ? "No se pudo conectar con el servidor del comparador. Intenta de nuevo en un minuto." : e.message, "err");
    return false;
  } finally { clearInterval(reloj); btn.disabled = false; btn.textContent = textoBtn; }
}

async function compararAhora(ev){
  ev.preventDefault();
  if (await compararUrl($("urlComparar").value.trim(), $("btnComparar"))) $("urlComparar").value = "";
}

$("buscar").addEventListener("input", render);
$("btnCsv").addEventListener("click", descargarCsv);
$("verDistintos").addEventListener("change", render);
$("formComparar").addEventListener("submit", compararAhora);
onAuthStateChanged(auth, u => { usuario = u; cargarFirestore(); });
cargarDiario();
