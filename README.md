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

## Comparador de precios

Botón **💲 Comparador de precios** al lado del nombre en la pantalla de inicio (`comparador/`).

Compara cada producto de Suconel con otras tiendas (por ahora **Didácticas Electrónicas**) y clasifica cada resultado como *mismo producto*, *posible*, *alternativa* o *distinto* según:

- **Características** (50 %): chip, corriente, rangos de entrada/salida, frecuencia, potencia y tamaño. Un chip o una corriente distinta marca el resultado como *alternativa* aunque el nombre se parezca.
- **Descripción** (30 %): similitud de nombre y descripción (rapidfuzz).
- **Foto** (20 %): hash perceptual de la imagen del producto (ImageHash).

```
comparador/
  index.html, comparador.css, comparador.js   Página que muestra los resultados
  productos.json                              Productos a comparar (URL de Suconel + tiendas)
  data/precios.json                           Resultados (lo genera el script)
  config.js                                   URL del servidor en Render
  servidor/app.py                             Servidor (FastAPI) para comparar al momento
  scraper/
    comparar.py                               Script principal
    coincidencia.py                           Extracción de características y puntajes
    tiendas/                                  Un conector por tienda (suconel, didacticas)
    tests/                                    Pruebas con páginas de ejemplo
```

- **Agregar un producto:** añadir una entrada en `comparador/productos.json` con la URL de Suconel. Opcionalmente, URLs fijas del competidor y términos de búsqueda.
- **Actualización:** el workflow `.github/workflows/comparador-precios.yml` corre todos los días (y a mano desde *Actions → Comparador de precios → Run workflow*) y guarda `precios.json`.
- **En local:** `pip install -r comparador/scraper/requirements.txt` y `python comparador/scraper/comparar.py`.
- **Comparar al momento:** en la página del comparador, un usuario aprobado pega la URL de un producto de Suconel y toca «Comparar». La página llama al servidor en **Render** (`comparador/servidor/`), que compara el producto y guarda el resultado en Firestore (`precios/{id}`).
- El script respeta `robots.txt` y espera 2 s entre peticiones. Si una tienda responde 403/429 y existe `FIRECRAWL_API_KEY` (en Render y, opcional, como *secret* de GitHub), esa tienda se lee a través de [Firecrawl](https://firecrawl.dev) con un máximo diario de páginas (`FIRECRAWL_MAX_DIA`). Sin clave, o si Firecrawl también falla, se muestran los últimos datos buenos marcados con su fecha.

### Servidor en Render (plan gratuito)

1. En [render.com](https://render.com) → **New → Blueprint** → elegir este repositorio. Render lee `render.yaml` y crea el servicio `comparador-suconel`.
2. Cuando pida `FIREBASE_SERVICE_ACCOUNT`, pegar el contenido del JSON de Firebase → Configuración del proyecto → Cuentas de servicio → *Generar nueva clave privada*. Es secreto: no se sube al repositorio.
3. Si la URL que asigna Render no es `https://comparador-suconel.onrender.com`, cambiarla en `comparador/config.js`.
4. Publicar de nuevo las reglas de `firebase/firestore.rules` (se agregó la colección `precios`).
5. Opcional: en GitHub → Settings → Secrets and variables → Actions → **Variables**, crear `RENDER_URL` con la URL del servicio. El workflow `despertar-render.yml` lo mantiene despierto en horario laboral.

Pruebas del servidor: `pip install -r comparador/servidor/requirements.txt pytest` y `python -m pytest comparador/servidor`.
