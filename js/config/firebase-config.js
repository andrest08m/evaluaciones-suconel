// Configuración del proyecto de Firebase (es pública por diseño: la seguridad la dan las reglas de Firestore).
export const firebaseConfig = {
  apiKey: "AIzaSyDbEYF3lXPEauVkt7w7hCbicELbpCWjuzI",
  authDomain: "evaluaciones-suconel.firebaseapp.com",
  projectId: "evaluaciones-suconel",
  storageBucket: "evaluaciones-suconel.firebasestorage.app",
  messagingSenderId: "675911522350",
  appId: "1:675911522350:web:188b4ff49502efa747a7bf",
};

// El usuario se guarda como usuario@dominio (correo interno, no se usa).
// Debe coincidir con emailMatches() en firebase/firestore.rules.
export const EMAIL_DOMAIN = "evaluaciones-suconel.app";

