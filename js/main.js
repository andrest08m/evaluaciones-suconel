// Punto de entrada de la aplicación.
import { $ } from "./utils/dom.js";
import { state } from "./state.js";
import { initLogin, setMode, checkAdminExists } from "./views/login.js";
import { renderHome } from "./views/home.js";
import { initQuiz } from "./views/quiz.js";
import { initAdmin } from "./views/admin.js";
import { initKeyboard } from "./keyboard.js";

initLogin();
initQuiz();
initAdmin();
initKeyboard();

setMode("in"); renderHome(); checkAdminExists();
setTimeout(() => { if (state.view === "login") $("luser").focus(); }, 50);
