// Estado global compartido entre las vistas.
export const state = {
  fbUser: null,          // usuario de Firebase Auth
  acct: null,            // {uid, username, name, role, estado}
  practice: false,       // modo práctica (sin guardar)
  mine: {},              // resumen de puntajes del usuario
  adminExists: true,     // ya existe el primer administrador
  view: "login",         // vista visible
  pendingProfile: null,  // perfil a crear tras registrarse
};

export function show(v){ state.view = v; document.querySelectorAll(".view").forEach(s => s.classList.toggle("on", s.id === v)); window.scrollTo(0, 0); }
export const approved = () => state.acct && state.acct.estado === "aprobado";
export const isAdmin = () => approved() && state.acct.role === "admin";
