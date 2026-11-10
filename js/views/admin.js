// Panel de administración: resultados, historial y gestión de usuarios.
import { META } from "../data/evaluaciones.js";
import { db, secondaryAuth, createUserWithEmailAndPassword, signOut, doc, setDoc, updateDoc, collection, getDocs, query, orderBy, limit } from "../services/firebase.js";
import { $, el } from "../utils/dom.js";
import { toEmail, normUser, validUser, nowIso, pctClass, fmtDate } from "../utils/format.js";
import { authMsg } from "../utils/errors.js";
import { state, show } from "../state.js";
import { goHome } from "./quiz.js";

let users = null, scores = null;
async function loadAdmin(){
  $("rstatus").textContent = "Cargando…";
  try {
    const [us, ss] = await Promise.all([getDocs(collection(db, "users")), getDocs(collection(db, "scores"))]);
    users = us.docs.map(d => ({ id: d.id, ...d.data() }));
    scores = ss.docs.map(d => ({ id: d.id, ...d.data() }));
    $("rstatus").textContent = "Actualizado " + new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
  } catch (e) { $("rstatus").textContent = authMsg(e); users = users || []; scores = scores || []; }
  renderRank(); renderUsers();
}
function openAdmin(){ show("admin"); tab("res"); $("hist").textContent = ""; loadAdmin(); }
function tab(which){
  $("tabRes").classList.toggle("on", which === "res"); $("tabUsers").classList.toggle("on", which === "users");
  $("paneRes").style.display = which === "res" ? "" : "none"; $("paneUsers").style.display = which === "users" ? "" : "none";
}
function renderRank(){
  const box = $("rtable"); if (!scores) return;
  const names = Object.fromEntries((users || []).map(u => [u.id, u]));
  if (!scores.length) { box.textContent = ""; box.append(el("div", "rempty", "Todavía nadie ha presentado evaluaciones.")); return; }
  const rows = scores.map(d => {
    const qz = d.quizzes || {}; let sum = 0, n = 0, att = 0, last = "";
    const cells = META.map(m => { const r = qz[m.k]; if (!r) return null; const p = Math.round(r.best / (r.max || 150) * 100); sum += p; n++; att += r.attempts || 0; if ((r.lastAt || "") > last) last = r.lastAt; return { p, r }; });
    const u = names[d.id] || {};
    return { id: d.id, name: u.name || d.name || "—", username: u.username || d.username || "", cells, avg: n ? Math.round(sum / n) : -1, n, att, last };
  }).sort((a, b) => b.avg - a.avg);
  const t = el("table"), th = el("tr");
  th.append(el("th", "l", "Asesor"), el("th", null, "Promedio"));
  META.forEach((m, n) => { const c = el("th", null, String(n + 1)); c.title = m.t; th.append(c); });
  th.append(el("th", null, "Presentadas"), el("th", null, "Intentos"), el("th", null, "Última vez"));
  const thead = el("thead"); thead.append(th); t.append(thead);
  const tb = el("tbody");
  rows.forEach(r => {
    const tr = el("tr", "click"); tr.title = "Ver historial";
    const who = el("td", "l"); who.append(el("span", null, r.name), el("span", "rnote", " @" + r.username)); tr.append(who);
    const avg = el("td"); avg.append(r.avg >= 0 ? el("span", "cell " + pctClass(r.avg), r.avg + "%") : el("span", "na", "—")); tr.append(avg);
    r.cells.forEach((c, n) => {
      const td = el("td");
      if (c) { const s = el("span", "cell " + pctClass(c.p), c.p + "%"); s.title = META[n].t + ": " + c.r.best + "/" + (c.r.max || 150) + " pts · " + c.r.attempts + " intento(s)"; td.append(s); }
      else td.append(el("span", "na", "—"));
      tr.append(td);
    });
    tr.append(el("td", null, r.n + "/" + META.length), el("td", null, String(r.att)), el("td", null, fmtDate(r.last)));
    tr.onclick = () => showHistory(r);
    tb.append(tr);
  });
  t.append(tb);
  const legend = el("div", "rnote"); legend.style.padding = ".7em 1em";
  legend.textContent = "Columnas: " + META.map((m, n) => (n + 1) + " " + m.t).join(" · ");
  box.textContent = ""; box.append(t, legend);
}
async function showHistory(r){
  const box = $("hist"); box.textContent = ""; box.append(el("h3", null, "Historial de " + r.name + " (@" + r.username + ")"), el("div", "rnote", "Cargando…"));
  try {
    const snap = await getDocs(query(collection(db, "scores", r.id, "attempts"), orderBy("at", "desc"), limit(100)));
    const t = el("table"), th = el("tr");
    ["Fecha", "Evaluación", "Puntaje", "%", "Aciertos", "Pistas", "Reveladas", "Duración"].forEach((h, k) => th.append(el("th", k < 2 ? "l" : null, h)));
    const thead = el("thead"); thead.append(th); t.append(thead);
    const tb = el("tbody");
    snap.docs.forEach(d => {
      const a = d.data(), m = META.find(x => x.k === a.quiz), p = Math.round(a.score / (a.max || 150) * 100);
      const tr = el("tr");
      tr.append(el("td", "l", fmtDate(a.at)), el("td", "l", m ? m.t : a.quiz));
      tr.append(el("td", null, a.score + "/" + (a.max || 150)));
      const pc = el("td"); pc.append(el("span", "cell " + pctClass(p), p + "%")); tr.append(pc);
      tr.append(el("td", null, String(a.hits)), el("td", null, String(a.hints)), el("td", null, String(a.revealed)),
        el("td", null, a.ms ? Math.round(a.ms / 60000) + " min" : "—"));
      tb.append(tr);
    });
    t.append(tb);
    const wrap = el("div", "tablewrap"); wrap.append(snap.empty ? el("div", "rempty", "Sin intentos registrados.") : t);
    box.textContent = ""; box.append(el("h3", null, "Historial de " + r.name + " (@" + r.username + ") · " + snap.size + " intento(s)"), wrap);
    box.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) { box.lastChild.textContent = authMsg(e); }
}
function renderUsers(){
  const box = $("utable"); if (!users) return;
  const pend = users.filter(u => u.estado === "pendiente").length;
  $("pendCount").textContent = pend ? "(" + pend + ")" : "";
  if (!users.length) { box.textContent = ""; box.append(el("div", "rempty", "No hay usuarios.")); return; }
  const order = { pendiente: 0, aprobado: 1, rechazado: 2 };
  const t = el("table"), th = el("tr");
  ["Nombre", "Usuario", "Estado", "Rol", "Registro", ""].forEach((h, k) => th.append(el("th", k < 2 ? "l" : null, h)));
  const thead = el("thead"); thead.append(th); t.append(thead);
  const tb = el("tbody");
  users.slice().sort((a, b) => (order[a.estado] - order[b.estado]) || (a.name || "").localeCompare(b.name || "")).forEach(u => {
    const tr = el("tr"), me = state.fbUser && u.id === state.fbUser.uid;
    tr.append(el("td", "l", u.name || "—"), el("td", "l", "@" + (u.username || "")));
    const es = el("td"); es.append(el("span", "estado " + u.estado, u.estado === "aprobado" ? "Aprobado" : u.estado === "rechazado" ? "Rechazado" : "Pendiente")); tr.append(es);
    const rl = el("td"); rl.append(el("span", "role " + (u.role === "admin" ? "admin" : ""), u.role === "admin" ? "Administrador" : "Asesor")); tr.append(rl);
    tr.append(el("td", null, fmtDate(u.createdAt)));
    const act = el("td"), bx = el("div", "rowbtns");
    if (me) bx.append(el("span", "rnote", "(tú)"));
    else {
      const btn = (txt, cls, fn) => { const b = el("button", "mini " + (cls || ""), txt); b.onclick = async () => { b.disabled = true; try { await fn(); await loadAdmin(); } catch (e) { b.textContent = "Error"; $("rstatus").textContent = authMsg(e); } }; bx.append(b); };
      if (u.estado !== "aprobado") btn("✓ Aprobar", "", () => updateDoc(doc(db, "users", u.id), { estado: "aprobado" }));
      if (u.estado === "pendiente") btn("Rechazar", "danger", () => updateDoc(doc(db, "users", u.id), { estado: "rechazado" }));
      if (u.estado === "aprobado") {
        btn(u.role === "admin" ? "Quitar admin" : "Hacer admin", "", () => updateDoc(doc(db, "users", u.id), { role: u.role === "admin" ? "asesor" : "admin" }));
        btn("Suspender", "danger", () => updateDoc(doc(db, "users", u.id), { estado: "rechazado" }));
      }
    }
    act.append(bx); tr.append(act); tb.append(tr);
  });
  t.append(tb); box.textContent = ""; box.append(t);
}
async function createUser(){
  const name = $("nName").value.trim(), u = normUser($("nUser").value), p = $("nPass").value, role = $("nRole").value;
  const msg = (t, ok) => { $("nMsg").textContent = t; $("nMsg").className = "lerr" + (ok ? " ok" : ""); };
  if (!name) return msg("Escribe el nombre.");
  if (!validUser(u)) return msg("Usuario no válido: letras, números, punto, guion o guion bajo (3 a 30).");
  if (p.length < 6) return msg("La contraseña debe tener al menos 6 caracteres.");
  $("nSave").disabled = true; msg("Creando…", true);
  try {
    const sa = secondaryAuth();
    const cred = await createUserWithEmailAndPassword(sa, toEmail(u), p);
    await setDoc(doc(db, "users", cred.user.uid), { username: u, name, role, estado: "aprobado", createdAt: nowIso(), createdBy: state.acct.username });
    try { await signOut(sa); } catch (e) {}
    msg("✓ Usuario creado: @" + u + ". Compártele su usuario y contraseña.", true);
    $("nName").value = ""; $("nUser").value = ""; $("nPass").value = ""; $("nRole").value = "asesor";
    loadAdmin();
  } catch (e) { msg(authMsg(e)); }
  finally { $("nSave").disabled = false; }
}

export function initAdmin(){
  $("tabRes").onclick = () => tab("res"); $("tabUsers").onclick = () => tab("users");
  $("admBtn").onclick = openAdmin; $("admHome").onclick = goHome; $("admRefresh").onclick = loadAdmin;
  $("nSave").onclick = createUser;
  ["nName", "nUser", "nPass"].forEach(id => $(id).addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); createUser(); } }));
}
