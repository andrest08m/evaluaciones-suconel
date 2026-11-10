# Evaluaciones Suconel

Evaluaciones de selección múltiple para la formación de asesores de Suconel: 12 evaluaciones de 15 preguntas cada una, pensadas para proyectar en pantalla grande.

Sitio: https://andrest08m.github.io/evaluaciones-suconel/

## Cómo funciona

- **Login** con usuario y contraseña (Firebase Authentication). Internamente el usuario se guarda como `usuario@evaluaciones-suconel.app`; no se usa ningún correo real.
- **Registro de asesores**: cada asesor se registra desde la pantalla de ingreso y queda *pendiente* hasta que un administrador lo apruebe.
- **Registro del administrador**: la primera cuenta que se registre como administrador queda como administradora (solo se puede una vez). Después, los administradores pueden aprobar, rechazar, crear usuarios y nombrar otros administradores.
- **Puntajes** (Firestore): `scores/{uid}` guarda el mejor puntaje por evaluación y `scores/{uid}/attempts` el historial de cada intento.
- **Modo práctica**: cualquiera puede practicar sin iniciar sesión; no se guarda nada.

Puntaje: 10 puntos por acierto, 5 si se usó la pista (máximo 150 por evaluación).

## Configuración de Firebase

1. Authentication → Sign-in method → **Email/Password** activado.
2. Authentication → Settings → Authorized domains → `andrest08m.github.io`.
3. Firestore Database creada.
4. Firestore → Reglas → pegar el contenido de [`firebase/firestore.rules`](firebase/firestore.rules) → Publicar
   (o con la CLI: `firebase deploy --only firestore:rules`, que usa `firebase.json`).

Las credenciales web del proyecto están en [`js/config/firebase-config.js`](js/config/firebase-config.js).

## Teclado

1-9 abre una evaluación · 1-4 o A-D responde · P pista · R revelar · ← → navegar · F pantalla completa.

## Estructura

Sitio estático sin paso de compilación: HTML, CSS y módulos ES nativos (Firebase se carga desde el CDN oficial).

```
index.html                  Marcado de las vistas (login, inicio, evaluación, administración)
css/styles.css              Estilos
js/
  main.js                   Punto de entrada: inicializa las vistas
  state.js                  Estado compartido y cambio de vista
  keyboard.js               Pantalla completa y atajos de teclado
  config/
    firebase-config.js      Credenciales web de Firebase y dominio interno de usuarios
    constants.js            Letras de opciones y puntaje por pregunta
  data/
    evaluaciones.js         Catálogo de las 12 evaluaciones (título, ícono, colores)
    preguntas.js            Banco de preguntas
  services/firebase.js      Inicialización de Firebase y funciones del SDK
  utils/                    Utilidades (DOM, formato, mensajes de error)
  views/                    login, home, quiz, admin
firebase/firestore.rules    Reglas de seguridad de Firestore
firebase.json               Configuración de la CLI de Firebase
```

Para probarlo en local hay que servirlo por HTTP (los módulos ES no cargan desde `file://`), por ejemplo `python3 -m http.server`.
