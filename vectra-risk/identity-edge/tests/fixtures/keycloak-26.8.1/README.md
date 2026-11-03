# Referencia de Keycloak 26.8.1 para el tema `vectra`

Archivos copiados sin cambios del repositorio `keycloak/keycloak`, tag `26.8.1`, rutas `themes/src/main/resources/theme/{base,keycloak.v2}/login/`. Descargados el 2026-11-02 (U02-T06, decisión P4 del usuario). `SHA256SUMS` fija su contenido; se verifica con `sha256sum -c SHA256SUMS` desde este directorio.

- `base/messages_en.properties` y `keycloak.v2/messages_en.properties`: claves de mensajes que existen en Keycloak.
- `keycloak.v2/templates/*.ftl`: plantillas de login, TOTP (`login-otp`, `login-config-totp`) y cambio de contraseña, con las comunes que incluyen.

Al subir la versión de Keycloak (INF-U2-08) se reemplaza este directorio por el de la versión nueva.
