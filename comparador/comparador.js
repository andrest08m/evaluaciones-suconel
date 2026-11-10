// Muestra data/precios.json (lo genera scraper/comparar.py).
const $ = id => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const cop = n => n == null ? "—" : "$ " + Math.round(n).toLocaleString("es-CO");
const VER = { mismo: "Mismo producto", posible: "Posible", alternativa: "Alternativa", distinto: "Distinto" };

let datos = null;

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
  if (!prods.length) { lista.append(el("div", "rempty", "No hay productos que coincidan.")); return; }
  prods.forEach(p => {
    const r = p.referencia, card = el("section", "cprod");
    const ref = el("div", "cref"), info = el("div"), h = el("h2"), a = el("a", null, r.nombre);
    a.href = r.url; a.target = "_blank"; a.rel = "noopener"; h.append(a);
    info.append(h, el("div", "csub", "Suconel · Ref. " + r.sku), specsChips(r.specs || {}));
    ref.append(foto(r.imagen), info, precio(r));
    card.append(ref);
    p.competidores.forEach(c => {
      const t = el("div", "ctienda", c.tienda);
      if (c.estado !== "ok") t.append(el("span", "cestado " + c.estado, c.estado === "bloqueado" ? "La tienda bloqueó la consulta" : "Error al consultar"));
      if (c.datos_de) t.append(el("span", "cestado viejo", "Mostrando datos del " + new Date(c.datos_de).toLocaleDateString("es-CO")));
      card.append(t);
      const cands = c.candidatos.filter(x => verDist || x.veredicto !== "distinto");
      if (!cands.length) card.append(el("div", "vacio", c.candidatos.length ? "Solo hay productos descartados (activa «Mostrar descartados»)." : "No se encontraron productos."));
      cands.forEach(x => card.append(candidato(x)));
    });
    lista.append(card);
  });
}

async function cargar(){
  try {
    const r = await fetch("data/precios.json", { cache: "no-store" });
    datos = await r.json();
    $("generado").textContent = "Actualizado: " + new Date(datos.generado).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    $("nota").textContent = datos.nota || "";
    render();
  } catch (e) {
    $("lista").textContent = ""; $("lista").append(el("div", "rempty", "No se pudieron cargar los precios."));
  }
}
$("buscar").addEventListener("input", render);
$("verDistintos").addEventListener("change", render);
cargar();
