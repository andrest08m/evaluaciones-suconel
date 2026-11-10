// Vista de evaluación: preguntas, pistas, resultado y guardado del puntaje.
import { DATA } from "../data/preguntas.js";
import { META } from "../data/evaluaciones.js";
import { L, PTS, PTS_HINT } from "../config/constants.js";
import { db, doc, collection, writeBatch } from "../services/firebase.js";
import { $ } from "../utils/dom.js";
import { state, show, approved } from "../state.js";
import { renderHome } from "./home.js";

let cur = null, Q = [], i = 0, ans = [], hint = [], shown = [], t0 = 0, saved = false, saveState = "";
export function startQuiz(k){
  cur = META.find(m => m.k === k); Q = DATA[k].Q;
  i = 0; ans = Array(Q.length).fill(null); hint = Array(Q.length).fill(false); shown = Array(Q.length).fill(false);
  t0 = Date.now(); saved = false; saveState = "";
  $("qtitle").textContent = "Evaluación · " + cur.t; $("tot").textContent = Q.length;
  show("quiz"); render();
}
function qPts(k){ return ans[k] === Q[k].c ? (hint[k] ? PTS_HINT : PTS) : 0; }
function points(){ let s = 0; for (let k = 0; k < Q.length; k++) s += qPts(k); return s; }
function render(){
  $("qfoot").style.display = "";
  if (i >= Q.length) return renderEnd();
  const q = Q[i], a = ans[i], done = a !== null || shown[i];
  $("pos").textContent = i + 1; $("pts").textContent = points();
  $("prog").style.width = (i / Q.length * 100) + "%";
  let h = `<div class="qnum">Pregunta ${i + 1}</div><div class="prompt">${q.p}</div><div class="opts">`;
  q.o.forEach((t, k) => {
    let cls = "";
    if (done) { if (k === q.c) cls = "ok"; else if (k === a) cls = "bad"; else cls = "dim"; }
    h += `<button class="opt ${cls}" data-k="${k}" ${done ? "disabled" : ""}><span class="k">${L[k]}</span><span>${t}</span></button>`;
  });
  h += `</div><div class="panel hint ${hint[i] && !done ? "show" : ""}">💡 ${q.h} <i>(un acierto con pista vale ${PTS_HINT} puntos)</i></div>`;
  if (done) {
    const v = a === null ? `<span class="verdict">Respuesta: ${L[q.c]}. +0</span>`
      : (a === q.c ? `<span class="verdict ok">¡Correcto! +${hint[i] ? PTS_HINT + " (con pista)" : PTS}</span>` : `<span class="verdict bad">Incorrecto. Era la ${L[q.c]}.</span>`);
    h += `<div class="panel exp show">${v}${q.e}</div>`;
  }
  $("qmain").innerHTML = h;
  document.querySelectorAll("#qmain .opt").forEach(b => b.onclick = () => choose(+b.dataset.k));
  $("prev").disabled = i === 0;
  $("hintBtn").disabled = done || hint[i]; $("revealBtn").disabled = done;
  $("next").textContent = i === Q.length - 1 ? "Ver resultado →" : "Siguiente →";
}
function renderEnd(){
  const max = Q.length * PTS, s = points(), pct = Math.round(s / max * 100);
  const hits = ans.filter((a, k) => a === Q[k].c).length, nh = hint.filter(Boolean).length, nr = shown.filter(Boolean).length;
  $("prog").style.width = "100%"; $("pts").textContent = s; $("pos").textContent = Q.length;
  const msg = pct >= 90 ? DATA[cur.k].end : pct >= 70 ? "Bien. Repasa los temas en rojo." : pct >= 50 ? "Aceptable. Hay temas por reforzar." : "Toca repasar los fundamentos.";
  const chips = Q.map((q, k) => { const a = ans[k]; const c = a === null ? "na" : a === q.c ? (hint[k] ? "half" : "ok") : "bad"; return `<button class="chip ${c}" data-k="${k}">${k + 1}</button>`; }).join("");
  $("qmain").innerHTML = `<div class="end"><div class="msg">Resultado</div>
    <div class="big">${s}<small> / ${max} pts</small></div>
    <div class="msg">${pct}% · ${msg}</div>
    <div class="stats">${hits} aciertos de ${Q.length} · ${nh} pistas · ${nr} reveladas</div>
    <div class="save" id="saveMsg"></div>
    <div class="review">${chips}</div><div class="keys">Toca un número para revisar esa pregunta</div>
    <div class="endbtns"><button class="btn" id="endHome">← Evaluaciones</button><button class="btn primary" id="restart">↺ Intentar de nuevo</button></div></div>`;
  document.querySelectorAll("#qmain .chip").forEach(b => b.onclick = () => { i = +b.dataset.k; render(); });
  $("restart").onclick = () => startQuiz(cur.k);
  $("endHome").onclick = goHome;
  $("qfoot").style.display = "none";
  if (!saved) { saved = true; saveResult({ k: cur.k, s, max, hits, h: nh, r: nr, ms: Date.now() - t0, at: new Date().toISOString() }); }
  renderSave();
}
export function choose(k){ if (i >= Q.length || ans[i] !== null || shown[i]) return; ans[i] = k; render(); }
export function next(){ if (i < Q.length) { i++; render(); } }
export function prev(){ if (i > 0) { i--; render(); } }
export function goHome(){ show("home"); renderHome(); }

function renderSave(){
  const m = $("saveMsg"); if (!m) return;
  const map = {
    saving: ["wait", "Guardando tu puntaje…"],
    ok: ["ok", "✓ Puntaje guardado"],
    guest: ["warn", state.acct ? "Tu cuenta aún no está aprobada: este puntaje no se guarda" : "Modo práctica: inicia sesión para guardar tu puntaje"],
    error: ["warn", "No se pudo guardar el puntaje. Revisa tu conexión."],
    denied: ["warn", "No se guardó: Firebase rechazó la escritura. Avísale al administrador."],
  };
  const v = map[saveState]; if (!v) { m.style.display = "none"; return; }
  m.style.display = ""; m.className = "save " + v[0]; m.textContent = v[1];
}
async function saveResult(r){
  if (!approved() || !state.fbUser) { saveState = "guest"; return; }
  saveState = "saving"; renderSave();
  const sum = JSON.parse(JSON.stringify(state.mine || {}));
  sum.quizzes = sum.quizzes || {};
  const q = sum.quizzes[r.k] || { attempts: 0, best: 0 };
  q.attempts = (q.attempts || 0) + 1;
  if (q.attempts === 1 || r.s > (q.best || 0)) { q.best = r.s; q.bestAt = r.at; }
  q.last = r.s; q.lastAt = r.at; q.max = r.max;
  sum.quizzes[r.k] = q; sum.updatedAt = r.at; sum.username = state.acct.username; sum.name = state.acct.name;
  const batch = writeBatch(db);
  batch.set(doc(db, "scores", state.fbUser.uid), sum);
  batch.set(doc(collection(db, "scores", state.fbUser.uid, "attempts")), { quiz: r.k, score: r.s, max: r.max, hits: r.hits, hints: r.h, revealed: r.r, ms: r.ms, at: r.at });
  try { await batch.commit(); saveState = "ok"; state.mine = sum; }
  catch (e) { saveState = (e && String(e.code).includes("permission")) ? "denied" : "error"; }
  renderSave();
}

// Atajos de teclado dentro de la evaluación (1-4 / A-D, flechas, P, R).
export function handleQuizKey(k, e){
  if (["1","2","3","4"].includes(k)) choose(+k - 1);
  else if (["a","b","c","d"].includes(k)) choose(L.indexOf(k.toUpperCase()));
  else if (k === "arrowright" || k === "enter" || k === " ") { e.preventDefault(); next(); }
  else if (k === "arrowleft") prev();
  else if (k === "p") $("hintBtn").click();
  else if (k === "r" && i < Q.length) { shown[i] = true; render(); }
}

export function initQuiz(){
  $("next").onclick = next; $("prev").onclick = prev;
  $("hintBtn").onclick = () => { if (i < Q.length && ans[i] === null && !shown[i]) { hint[i] = true; render(); } };
  $("revealBtn").onclick = () => { if (i < Q.length) { shown[i] = true; render(); } };
  $("toHome").onclick = goHome;
}
