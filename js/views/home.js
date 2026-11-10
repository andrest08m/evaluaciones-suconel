// Vista de inicio: tarjetas de evaluaciones y mejores puntajes.
import { META } from "../data/evaluaciones.js";
import { $, el } from "../utils/dom.js";
import { pctClass } from "../utils/format.js";
import { state, approved, isAdmin } from "../state.js";
import { startQuiz } from "./quiz.js";

export function renderHome(){
  const g = $("grid"); g.textContent = "";
  META.forEach((m, n) => {
    const b = el("button", "card"); b.style.setProperty("--c", m.c); b.style.setProperty("--cbg", m.b);
    b.onclick = () => startQuiz(m.k);
    const top = el("div", "ctop");
    top.append(el("span", "ico", m.i), el("h2", null, m.t)); if (n < 9) top.append(el("span", "key", String(n + 1)));
    if (m.n) b.append(el("span", "new", "NUEVA"));
    const foot = el("div", "cfoot");
    const r = approved() && state.mine.quizzes && state.mine.quizzes[m.k];
    if (r) {
      const max = r.max || 150, p = Math.round(r.best / max * 100);
      const best = el("span", "best");
      best.append("Tu mejor: ", el("span", "pill " + pctClass(p), r.best + "/" + max));
      best.append(" · " + r.attempts + (r.attempts === 1 ? " intento" : " intentos"));
      foot.append(best, el("span", "go", "Repetir →"));
    } else foot.append(el("span", null, "15 preguntas"), el("span", "go", "Comenzar →"));
    b.append(top, el("p", null, m.d), foot);
    g.append(b);
  });
  const w = $("who"), nt = $("notice");
  w.textContent = ""; nt.classList.remove("show"); document.body.classList.remove("guest");
  if (approved()) { w.className = "who"; w.append(el("span", null, "👤 " + (state.acct.name || state.acct.username))); }
  else {
    w.className = "who off"; w.textContent = "Modo práctica";
    nt.textContent = state.acct ? "Tu cuenta aún no está aprobada: puedes practicar, pero los puntajes no se guardan." : "Estás en modo práctica: tus puntajes no se guardan. Toca «Iniciar sesión» para entrar con tu usuario.";
    nt.classList.add("show"); document.body.classList.add("guest");
  }
  $("admBtn").style.display = isAdmin() ? "" : "none";
  $("logout").textContent = state.acct ? "🔒 Salir" : "🔑 Iniciar sesión";
}
