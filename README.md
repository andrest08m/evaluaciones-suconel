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
4. Firestore → Reglas → pegar el contenido de [`firestore.rules`](firestore.rules) → Publicar.

## Teclado

1-9 abre una evaluación · 1-4 o A-D responde · P pista · R revelar · ← → navegar · F pantalla completa.

Todo el sitio es un único `index.html` sin paso de compilación (Firebase se carga desde el CDN oficial).
