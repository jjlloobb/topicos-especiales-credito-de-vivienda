VEREDICTO: VERDE

# Ronda 1 — U10-T06

Revisada la punta 99b6ae2 de `tarea/U10-T06` contra `origin/main`. Todos los criterios pasan con ejecuciones del revisor. Ningún ROJO ni NARANJA. El único fallo de `check` es `test_flows_f10…`, que viene de U01-T09. El PR #186 se fusionó en `main` (c2f5a36) mientras se revisaba.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | Login, recarga con `prompt=none`, step-up y logout con el descubrimiento en 500, sin pedir `.well-known` | `make -C console check`, una vez (`test-spa` y `e2e-spa` dentro); `npx vitest run tests/unit/auth --reporter=verbose` en una copia | **pasa**. vitest: 35 archivos y 388 pruebas. Playwright: 64 en chromium y firefox, ninguna omitida, con el emisor respondiendo 500 al descubrimiento. `stats.discovery == 0` en los dos navegadores |
| 2 | Las rutas salen de un solo sitio y coinciden con el gateway | mutaciones M3, M4, M5 y M7 | **pasa** (`issuer-metadata.test.ts`) |
| 3 | Ninguna validación desactivada | el `git diff … \| grep` del criterio | **pasa**: una sola línea, un comentario; `loadUserInfo` ya estaba en `false` en `main` |
| 4 | Todo `console` en verde y la imagen de la SPA construye | `make -C console check` (rc 2) y, aparte, `policy-chart-u1`, `quota-flows`, `gitops`, `links` y `traceability` | **pasa, con la excepción conocida**. Lint, pytest del BFF (541 y 341), vitest (388) y Playwright (64); las tres imágenes construyen. Único fallo: `test_chart.py::test_flows_f10_to_f14…` (`KeyError: 'port'`), ajeno al diff |

## Seguridad: qué valida `oidc-client-ts` 3.5.0 (leído en `node_modules/oidc-client-ts/dist/esm/oidc-client-ts.js`)
- **Lo que valida, con y sin descubrimiento:** `_processSigninState` (l.1405-1435): el `state` coincide con el guardado, `settings.authority === state.authority`, `client_id`, y exige `code` cuando hay `code_verifier`. PKCE S256 (l.1575-1576) y `_processCode` (l.1451-1467). `_validateIdTokenAttributes` (l.1469-1499): decodifica sin verificar firma, exige `sub`, `nonce` igual al guardado y, en el refresco, `sub`, `auth_time` y `azp` iguales.
- **Lo que no se validaba ni con descubrimiento:** `getIssuer()` (l.883) y `getSigningKeys()` (l.920) están definidos pero nada los llama. La librería tampoco lee el parámetro `iss` de la respuesta de autorización (RFC 9207). Con descubrimiento tampoco se verificaban la firma, `iss`, `aud` ni el `iss` de RFC 9207: **la afirmación del codificador es correcta**.
- `getMetadata` (l.867-882) devuelve `settings.metadata` si existe y no hace ningún `fetch`. La SPA solo necesita `getAuthorizationEndpoint`, `getTokenEndpoint` y `getEndSessionEndpoint`. `getUserInfoEndpoint`, `getCheckSessionIframe` y `getRevocationEndpoint` no se usan con la configuración de la SPA.
- La comprobación de `acr` del step-up (`src/stepup/oidc.ts:37`) no cambia.

## Mutaciones (en una copia)
Quitar `metadata` de `manager.ts`: 4 fallan. De `wiring.ts`: 1 falla. `endSession` → `logoutX`: 3 fallan. El `Exact …/logout` de `routes.yaml` → `logoutX`: 1 falla. `token` → `tokenX`: 3 fallan. Quitar `end_session_endpoint`: 2 fallan. El límite `auth-token` del gateway → `tokenX`: 1 falla.

Los tres constructores de cliente OIDC (`createUserManager`, `new OidcClient` en `wiring.ts:60` y el de la PoC) reciben `metadata`. El doble del emisor tiene `discovery_status=200` por omisión; el BFF de producto no consulta el descubrimiento.

## Solo leído
- El gateway publica `…/openid-connect/{auth,token,logout}` como `Exact` en la ruta `auth` (`routes.yaml:200,201,203`), con los límites `auth-login` y `auth-token`.
- La CSP solo permite `connect-src 'self'` y el emisor está en el mismo host: sin cambio. El diff no toca `identity-edge/`, `console/bff/src`, `console/chart` ni `platform`. El mecanismo del login se mantiene.

## Hallazgos
### F-01 · AMARILLO · `console/spa/tests/unit/auth/issuer-metadata.test.ts:14` · El prefijo del realm está repetido en la prueba, en vez de salir de `issuerPath` del chart
### F-02 · AMARILLO · `console/spa/tests/e2e/` · El contador de descubrimiento solo se comprueba en `auth.spec.ts` (el step-up está cubierto de todos modos: con el doble en 500 fallaría)

## Tareas candidatas
- `console/bff/tests/unit/test_chart.py::test_flows_f10_to_f14…` sigue rompiendo `check` y `quota-flows` desde U01-T09.
- El descubrimiento con 500 del realm (U2) sigue roto para cualquier otro cliente.

```
VEREDICTO: VERDE
AMARILLO|console/spa/tests/unit/auth/issuer-metadata.test.ts:14|el prefijo del realm está repetido en la prueba
AMARILLO|console/spa/tests/e2e/|el contador de descubrimiento solo se comprueba en auth.spec.ts
INFORME: revisiones/U10-T06/ronda-1.md
```
