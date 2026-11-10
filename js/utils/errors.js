// Traduce los errores de Firebase a mensajes para el usuario.
export function authMsg(e){
  const c = (e && e.code) || "";
  if (c.includes("invalid-credential") || c.includes("wrong-password") || c.includes("user-not-found") || c.includes("invalid-email")) return "Usuario o contraseña incorrectos.";
  if (c.includes("email-already-in-use")) return "Ese usuario ya existe. Elige otro.";
  if (c.includes("weak-password")) return "La contraseña debe tener al menos 6 caracteres.";
  if (c.includes("too-many-requests")) return "Demasiados intentos. Espera unos minutos.";
  if (c.includes("network-request-failed")) return "Sin conexión. Revisa tu internet.";
  if (c.includes("unauthorized-domain")) return "Este dominio no está autorizado en Firebase (Authentication → Settings → Authorized domains).";
  if (c.includes("operation-not-allowed")) return "El login con correo y contraseña no está activado en Firebase.";
  if (c.includes("unavailable") || c.includes("failed-precondition") || c.includes("not-found")) return "No hay conexión con la base de datos. En Firebase revisa que Firestore Database esté creada (base «(default)») y que las reglas estén publicadas.";
  if (c.includes("configuration-not-found")) return "Firebase Authentication no está activado: en la consola entra a Authentication → Get started y activa Email/Password.";
  if (c.includes("permission-denied")) return "Firebase rechazó la operación (revisa las reglas de Firestore).";
  return "Ocurrió un error (" + (c || "desconocido") + "). Inténtalo de nuevo.";
}
