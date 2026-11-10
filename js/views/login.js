// Vista de ingreso y registro, y ciclo de sesión de Firebase Auth.
import { auth, db, signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut, onAuthStateChanged, doc, getDoc, setDoc, writeBatch } from "../services/firebase.js";
import { $ } from "../utils/dom.js";
import { toEmail, normUser, validUser, nowIso } from "../utils/format.js";
import { authMsg } from "../utils/errors.js";
import { state, show, approved } from "../state.js";
import { renderHome } from "./home.js";

let lmode = "in";       // in | up | admin
export function setMode(m){
  lmode = m;
  $("tabIn").classList.toggle("on", m === "in"); $("tabUp").classList.toggle("on", m !== "in");
  $("fName").style.display = m === "in" ? "none" : "";
  $("fPass2").style.display = m === "in" ? "none" : "";
  $("lpass").autocomplete = m === "in" ? "current-password" : "new-password";
  $("ltitle").textContent = m === "admin" ? "Registro de administrador" : m === "up" ? "Crear cuenta" : "Evaluaciones";
  $("lbtn").textContent = m === "in" ? "Entrar →" : m === "admin" ? "Crear administrador →" : "Registrarme →";
  $("lhelp").textContent = m === "in" ? "¿No tienes cuenta? Toca «Registrarme»." :
    m === "admin" ? "Esta cuenta será la administradora: aprueba asesores, crea usuarios y ve todos los resultados." :
    "Tu cuenta quedará pendiente hasta que el administrador la apruebe.";
  lmsg("");
}
function lmsg(t, ok){ $("lerr").textContent = t || ""; $("lerr").className = "lerr" + (ok ? " ok" : ""); }
export async function checkAdminExists(){
  try { const s = await getDoc(doc(db, "config", "admin")); state.adminExists = s.exists(); } catch (e) { state.adminExists = true; }
  const b = $("lbanner");
  if (!state.adminExists) { b.style.display = ""; b.textContent = "Aún no hay administrador. La primera cuenta que se registre aquí será la administradora."; if (lmode !== "in") setMode("admin"); else $("tabUp").textContent = "Registrar administrador"; }
  else { b.style.display = "none"; $("tabUp").textContent = "Registrarme"; }
}
let busy = false;
async function submitLogin(){
  if (busy) return;
  const u = normUser($("luser").value), p = $("lpass").value;
  if (!u || !p) return lmsg("Escribe tu usuario y tu contraseña.");
  if (!validUser(u)) return lmsg(lmode === "in" ? "Usuario o contraseña incorrectos." : "Usuario no válido: letras, números, punto, guion o guion bajo (3 a 30).");
  busy = true; $("lbtn").disabled = true; lmsg(lmode === "in" ? "Verificando…" : "Creando cuenta…", true);
  try {
    if (lmode === "in") { await signInWithEmailAndPassword(auth, toEmail(u), p); return; }
    const name = $("lname").value.trim();
    if (!name) return lmsg("Escribe tu nombre completo.");
    if (p.length < 6) return lmsg("La contraseña debe tener al menos 6 caracteres.");
    if (p !== $("lpass2").value) return lmsg("Las contraseñas no coinciden.");
    state.pendingProfile = { username: u, name, wantAdmin: lmode === "admin" };
    await createUserWithEmailAndPassword(auth, toEmail(u), p);   // onAuthStateChanged crea el perfil
  } catch (e) { state.pendingProfile = null; lmsg(authMsg(e)); }
  finally { busy = false; $("lbtn").disabled = false; }
}
async function createProfile(user, prof){
  const base = { username: prof.username, name: prof.name, createdAt: nowIso() };
  if (prof.wantAdmin) {
    const batch = writeBatch(db);
    batch.set(doc(db, "config", "admin"), { uid: user.uid, createdAt: base.createdAt });
    batch.set(doc(db, "users", user.uid), { ...base, role: "admin", estado: "aprobado" });
    await batch.commit();
    state.adminExists = true;
    return { ...base, role: "admin", estado: "aprobado" };
  }
  const data = { ...base, role: "asesor", estado: "pendiente" };
  await setDoc(doc(db, "users", user.uid), data);
  return data;
}
async function loadAccount(user){
  let snap = await getDoc(doc(db, "users", user.uid));
  let data = snap.exists() ? snap.data() : null;
  if (!data) {
    let prof = state.pendingProfile;
    if (!prof) {   // la cuenta existe en Auth pero sin perfil (p. ej. falló la creación): si aún no hay admin, queda como admin
      const u = (user.email || "").split("@")[0];
      let noAdmin = false;
      try { noAdmin = !(await getDoc(doc(db, "config", "admin"))).exists(); } catch (e) { throw e; }
      prof = { username: u, name: u, wantAdmin: noAdmin };
    }
    data = await createProfile(user, prof);
    state.pendingProfile = null;
  }
  state.acct = { uid: user.uid, username: data.username, name: data.name, role: data.role, estado: data.estado };
  state.mine = {};
  if (approved()) { try { const s = await getDoc(doc(db, "scores", user.uid)); state.mine = s.exists() ? s.data() : {}; } catch (e) {} }
}
function routeAfterLogin(){
  $("lpass").value = ""; $("lpass2").value = ""; lmsg("");
  if (approved()) { state.practice = false; show("home"); renderHome(); return; }
  $("ptitle").textContent = state.acct.estado === "rechazado" ? "Cuenta no aprobada" : "Cuenta pendiente";
  $("ptext").textContent = state.acct.estado === "rechazado"
    ? "El administrador no aprobó esta cuenta. Si crees que es un error, habla con tu líder de formación."
    : "Hola " + (state.acct.name || state.acct.username) + ". Tu cuenta @" + state.acct.username + " está pendiente de aprobación. Cuando el administrador la apruebe, tus puntajes se guardarán.";
  $("precheck").style.display = state.acct.estado === "rechazado" ? "none" : "";
  show("pending");
}
onAuthStateChanged(auth, async user => {
  state.fbUser = user;
  if (!user) { state.acct = null; state.mine = {}; if (state.view !== "login" && !state.practice) show("login"); return; }
  try { await loadAccount(user); routeAfterLogin(); }
  catch (e) { state.acct = null; show("login"); lmsg(authMsg(e)); }
});
async function doLogout(){ state.practice = false; state.acct = null; state.mine = {}; try { await signOut(auth); } catch (e) {} show("login"); setMode("in"); checkAdminExists(); setTimeout(() => $("luser").focus(), 50); }

export function initLogin(){
  $("tabIn").onclick = () => setMode("in");
  $("tabUp").onclick = () => setMode(state.adminExists ? "up" : "admin");
  $("lbtn").onclick = submitLogin;
  ["luser", "lpass", "lpass2", "lname"].forEach(id => $(id).addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); submitLogin(); } }));
  $("practice").onclick = () => { state.practice = true; show("home"); renderHome(); };
  $("ppractice").onclick = () => { state.practice = true; show("home"); renderHome(); };
  $("plogout").onclick = doLogout;
  $("precheck").onclick = async () => { if (!state.fbUser) return; try { await loadAccount(state.fbUser); routeAfterLogin(); } catch (e) {} };
  $("logout").onclick = () => { if (state.acct) doLogout(); else { state.practice = false; show("login"); setMode("in"); } };
}
