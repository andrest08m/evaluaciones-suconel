// Inicializa Firebase y reexporta las funciones del SDK que usa la app.
// Para actualizar el SDK basta con cambiar la versión (11.10.0) en este archivo.
import { initializeApp } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js";
import { firebaseConfig } from "../config/firebase-config.js";

export { signInWithEmailAndPassword, createUserWithEmailAndPassword, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js";
export { doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs, query, orderBy, limit, writeBatch } from "https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js";

const fbApp = initializeApp(firebaseConfig);
export const auth = getAuth(fbApp);
export const db = getFirestore(fbApp);

let secAuth = null;   // segunda instancia para que el admin cree usuarios sin cerrar su sesión
export function secondaryAuth(){ if (!secAuth) secAuth = getAuth(initializeApp(firebaseConfig, "crear-usuarios")); return secAuth; }
