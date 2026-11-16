# U10-T06 — La SPA no depende del documento de descubrimiento OIDC

**Unidad:** U10 — `console` (SPA)
**Historias que implementa:** ninguna nueva; cierra un defecto medido al desplegar U2 en `kind-vectra` el 2026-11-15.
**Depende de:** ninguna

---

## Alcance

**Dentro:**

> En kind, `GET /auth/realms/vectra/.well-known/openid-configuration` responde **500**: Keycloak 26.8.1 falla al listar los niveles de autenticación porque el flujo de login del realm tiene varias condiciones de nivel 2, una por rol (`Duplicate key 2`; lo reprodujo U02-T24 con el Keycloak real de las pruebas). Arreglarlo en el realm obliga a cambiar la regla del MFA por rol. **Decisión del usuario (2026-11-15): no tocar el realm ahora; la SPA deja de depender del descubrimiento.** El resto del realm responde: `…/protocol/openid-connect/certs` 200 y `…/protocol/openid-connect/auth` pinta la página de login.
>
> La SPA crea su `UserManager` de `oidc-client-ts` 3.5.0 con `authority` (`console/spa/src/auth/manager.ts`, `src/wiring.ts`, que además usa `OidcClient` para el step-up), así que la librería pide el documento de descubrimiento antes de redirigir: el login por el navegador no arranca.
>
> 1. La SPA configura **explícitamente** los metadatos del emisor (el ajuste `metadata` de `oidc-client-ts`: `issuer`, `authorization_endpoint`, `token_endpoint`, `end_session_endpoint` y los que la librería necesite de verdad para lo que la SPA usa: login por redirección con PKCE, recarga con `prompt=none`, step-up y logout), derivados del emisor que ya trae `config.json` (`oidc.authority`), en **todos** los sitios donde se construye un cliente OIDC (`UserManager` y `OidcClient`). Con eso la librería no pide el documento.
> 2. Comprueba cómo valida la SPA el `id_token` y si la librería necesita `jwks_uri` o `userinfo_endpoint` para lo que la SPA hace; no añadas endpoints que no se usen ni desactives ninguna validación que hoy esté activa. Si para no depender del descubrimiento hubiera que desactivar una validación de seguridad, **PARA y pregunta**.
> 3. Las rutas de los endpoints salen de un solo sitio y son las de Keycloak para un realm (`/protocol/openid-connect/auth`, `/token`, `/logout`, `/certs`); una prueba las ata a lo que el gateway publica (`identity-edge/gateway/routes.yaml`, rutas de `/auth`).
> 4. Pruebas (vitest y, si existen para el login, las e2e de la SPA con sus dobles): el login completo, la recarga, el step-up y el logout funcionan **con el documento de descubrimiento respondiendo 500** (el doble del emisor debe poder fallar ese documento), y ninguna petición sale a `.well-known/openid-configuration`.
> 5. Mira si el chart de la SPA (`console/chart/spa`, ConfigMap de `config.json`) o la CSP necesitan algún cambio para esto; el BFF no cambia.

**Fuera:**

- El realm de Keycloak y cualquier cosa de `identity-edge/` (el 500 del descubrimiento queda como defecto conocido de U2, en `CANDIDATAS.md`).
- El BFF, salvo que una prueba compartida lo exija.
- El mecanismo del login decidido el 2026-11-12 (redirección; tokens en memoria; estado transitorio en `sessionStorage`; recarga con `prompt=none`; sin `signinPopup` ni `signinSilent`): no cambia.
- Construir o publicar la imagen y los digests: lo hace el orquestador después.

---

## Archivos de contexto

- `console/spa/src/auth/` (`manager.ts` y lo que haya de step-up y logout), `console/spa/src/wiring.ts`, `console/spa/src/config*` (forma de `config.json`), `console/spa/package.json`
- `console/spa/tests/` o donde vivan las pruebas de la SPA (vitest y e2e), y sus dobles del emisor
- `console/chart/spa/` (`values.yaml`, `templates/configmap.yaml`), `console/Makefile`, `console/README.md`
- `identity-edge/gateway/routes.yaml` (solo lectura)
- `revisiones/U10-T03/arbitraje-ronda-1.md` y `DECISIONES-LOOP.md` §9 (mecanismo del login)
- `bitacoras/U02-T24.md` en la rama `origin/tarea/U02-T24` (la causa del 500 y quién usa el descubrimiento)

---

## Criterios de aceptación

- [ ] **CA-1** — Con el descubrimiento respondiendo 500, el login por redirección, la recarga con `prompt=none`, el step-up y el logout funcionan, y la SPA no pide `.well-known/openid-configuration`.
  ```bash
  cd vectra-risk && make -C console test-spa
  ```
  Esperado: pasa, con pruebas nuevas; contra `main`, las nuevas fallan (rojo registrado). Ajusta el objetivo al nombre real del `Makefile` (vitest de la SPA) y dilo.

- [ ] **CA-2** — Los endpoints salen de un solo sitio y coinciden con las rutas que publica el gateway.
  ```bash
  cd vectra-risk && make -C console test-spa
  ```
  Esperado: una prueba falla si se cambia una ruta de endpoint sin cambiar la otra parte. (Mismo objetivo; di qué prueba es.)

- [ ] **CA-3** — Ninguna validación del `id_token` ni del `state`/`nonce`/PKCE que hoy esté activa queda desactivada.
  ```bash
  cd vectra-risk && git diff origin/main -- console/spa/src | grep -n -i -E 'validate|skip|loadUserInfo|filterProtocolClaims|disable' || echo "sin cambios en validaciones"
  ```
  Esperado: nada que desactive una validación; la bitácora explica cada línea que salga.

- [ ] **CA-4** — Todo `console` en verde, y la imagen de la SPA construye.
  ```bash
  cd vectra-risk && make -C console check && make -C console image-spa
  ```
  Esperado: rc 0 en los dos. (`check` puede levantar contenedores y navegadores: una sola vez, al final. `image-spa` necesita `platform/.tools/bin/hadolint`.) La prueba `console/bff/tests/unit/test_chart.py::test_flows_f10…` ya falla en `main` desde U01-T09 y no es de esta tarea: si es lo único que falla, dilo y corre aparte lo que no llegó a correr.

---

## Plan de pruebas

Las de CA-1 y CA-2. **Rojo primero**; orden y salida en la bitácora.

---

## Notas

- **Nada contra el clúster `kind-vectra`**, ni contra `vectra.localtest.me` ni la IP de su balanceador.
- No descargues imágenes de contenedor nuevas. Las dependencias de npm ya fijadas en `package-lock.json` se instalan con `npm ci`.
- `platform/.tools`: enlázalo a `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk/platform/.tools`; `platform/.charts`, cópialo del worktree `u01-t13`. No van en el commit.
- La máquina tiene poca memoria y un clúster de kind completo corriendo: suites pesadas una sola vez.
- En cada criterio, comprueba que el comando ejecuta de verdad tus pruebas nuevas.
- El scratchpad está en un disco en RAM y es compartido: prefijo `u10t06-`.
- `CANDIDATAS.md`: solo añadir al final (añade el 500 del descubrimiento del realm como defecto conocido de U2, con la causa medida por U02-T24). Pocos commits grandes. No hagas push, no fusiones, no muevas el estado de la tarea.
