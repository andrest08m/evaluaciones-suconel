// Utilidades de usuarios, fechas y porcentajes.
import { EMAIL_DOMAIN } from "../config/firebase-config.js";

export const toEmail = u => u + "@" + EMAIL_DOMAIN;
export function normUser(u){ return (u || "").trim().toLowerCase(); }
export function validUser(u){ return /^[a-z0-9._-]{3,30}$/.test(u); }
export const nowIso = () => new Date().toISOString();
export function pctClass(p){ return p >= 80 ? "c-hi" : p >= 60 ? "c-mid" : "c-lo"; }
export function fmtDate(iso){ return iso ? new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—"; }
