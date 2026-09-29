# Assets de marca

Sustituye estos ficheros por los del destino (mantén los nombres):

- `logo.png` — logotipo (cabecera / login).
- `login-background.jpg` — fondo de la pantalla de acceso.
- `favicon.ico` — icono de pestaña del navegador.

Los incluidos son *placeholders* (1×1 px). En `docker-compose` esta carpeta se
monta en el frontal (`/usr/share/nginx/html/assets/branding`), así que basta con
reemplazar los ficheros y recargar — **no hay que reconstruir la imagen**.

Textos, colores y nombre del destino se editan en `branding.json`.
