// Pantalla completa y atajos de teclado globales.
import { META } from "./data/evaluaciones.js";
import { state } from "./state.js";
import { startQuiz, handleQuizKey } from "./views/quiz.js";

function toggleFS(){
  try {
    if (!document.fullscreenElement) { const p = document.documentElement.requestFullscreen(); if (p && p.catch) p.catch(() => {}); }
    else { const p = document.exitFullscreen(); if (p && p.catch) p.catch(() => {}); }
  } catch (e) {}
}

export function initKeyboard(){
  document.querySelectorAll(".fsbtn").forEach(b => b.onclick = toggleFS);
  document.addEventListener("keydown", e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    const k = e.key.toLowerCase();
    if (k === "f") { toggleFS(); return; }
    if (state.view === "home") { const n = parseInt(k, 10); if (n >= 1 && n <= META.length) startQuiz(META[n - 1].k); return; }
    if (state.view !== "quiz") return;
    handleQuizKey(k, e);
  });
}
