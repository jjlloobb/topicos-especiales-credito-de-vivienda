# Reglas de negocio — U2 `identity-edge`

Los IDs `BR-U2-xx` se referencian en los planes de tareas. Las reglas de validación de
token y de autorización por endpoint son de U0 (BR-U0-70..73); aquí se fija lo que el
realm y el gateway aportan.

---

## 1. Roles y separación de funciones (Q1)

**BR-U2-01 — Un rol de negocio por usuario.** El conjunto de roles de negocio de un
usuario tiene como máximo un elemento de {`analista`, `ingeniero_riesgo`, `cro`,
`cumplimiento`}. Un usuario con dos roles de negocio es inválido:
- en el realm como código, la validación del `realm.yaml` falla en CI;
- en la federación LDAP, un usuario que pertenece a dos grupos mapeados **no recibe ningún rol** y se emite el evento `ROLE_CONFLICT` (alerta SEV2). Así, un error de LDAP nunca da acceso de más.

**BR-U2-02 — Aprobador ≠ proponente.** U2 garantiza la identidad (`sub`) en el token.
Que quien aprueba no sea quien propuso lo verifica governance (U4) comparando `sub`.

## 2. MFA y step-up (Q2, Q3; US-601)

**BR-U2-03 — MFA obligatorio por rol.** Los usuarios con `ingeniero_riesgo`, `cro` o
`cumplimiento` tienen TOTP como *required action*: no obtienen ningún token hasta
configurarlo (escenario «aprobador sin MFA» de US-601). WebAuthn es opcional como segundo
método. Para estos roles, el flujo de login exige el segundo factor siempre, así que su
token tiene `acr = mfa`.

**BR-U2-04 — Step-up para firmar.** Un endpoint con `mfa_required` exige `acr = mfa` **y**
`auth_time` de ≤ 900 s (BR-U0-72). El step-up es el de U10 BR-U10-06 (revisión del Infrastructure Design de U10, 2026-10-10): un
Authorization Code con PKCE, `prompt=login`, `max_age=0` y `acr_values=mfa`, en una **ventana
emergente** abierta por un clic del usuario, con `redirect_uri = /stepup-callback`; esa página
devuelve `code` y `state` a la ventana principal por `postMessage` al mismo origen. La ventana
principal canjea el código y reintenta la acción una vez, sin recargar.
La entrada del registro guarda el `acr` y el `auth_time` de la firma.

## 3. Fuerza bruta (Q4; US-601)

**BR-U2-05 — Bloqueo.** Detección de fuerza bruta de Keycloak:
- 5 fallos consecutivos → bloqueo temporal de 60 s, que se duplica en cada nueva serie hasta un máximo de 900 s;
- 20 fallos en 12 h → bloqueo permanente, que solo levanta un administrador.

Cada bloqueo emite un evento que alimenta la alerta `AuthDeniedBurst` (SEV2). El rate
limit de `/auth/**` (BR-U2-08) actúa antes.

## 4. Tokens y sesiones (Q5, Q6)

**BR-U2-06 — Vidas.**
- Access token: 300 s.
- Refresh token con **rotación**: cada uso emite uno nuevo e invalida el anterior; reusar uno invalidado revoca la sesión.
- Sesión SSO: 1 800 s de inactividad y 36 000 s como máximo.
- Tokens de servicio: 300 s, sin refresh.

**BR-U2-07 — Almacenamiento en la SPA.** Los tokens viven solo en memoria del navegador.
Prohibido `localStorage`, `sessionStorage` y cookies legibles por JavaScript. Al recargar
la página, la SPA recupera la sesión con un Authorization Code silencioso.

**BR-U2-09 — Autenticación de clientes de servicio.** `private_key_jwt` con RS256 o ES256.
Las aserciones duran ≤ 60 s y llevan un `jti` único. Keycloak no guarda secretos
compartidos de ningún cliente de servicio.

## 5. Gateway (Q8, Q9; US-611)

**BR-U2-08 — Límites.** Los de la tabla de rutas (domain-entities §4). Al superar un
límite de tasa, el gateway responde **429** con `Problem` (`code = rate_limited`) y
`Retry-After`. Al superar el tamaño, responde **413** (`payload_too_large`). Los dos sin
eco del contenido.

**BR-U2-10 — Rutas cerradas.** El gateway solo enruta las rutas de domain-entities §4.
Cualquier otra ruta devuelve 404 genérico, incluida `/auth/admin/**` (X10). En `/auth/**`
solo se enrutan los endpoints públicos del realm `vectra`; el realm `master` no se expone.

**BR-U2-11 — Validación de JWT en el gateway.** Para las rutas autenticadas, el gateway
valida firma (JWKS), `exp`, `iss`, el `azp` esperado y los claims de la tabla de rutas. El `azp` esperado puede ser un conjunto por ruta y por entorno: en `/api/intake/**`, `channel` y, fuera de producción, `channel-simulator` (precisado el 2026-10-06, revisión del FD de U8).
Un fallo responde 401 o 403 con `Problem`. El servicio de destino **vuelve** a validar
todo (BR-U0-70..72): el gateway es la primera capa, no la única.

**BR-U2-13 — Cabeceras por perfil.** Cada ruta aplica su perfil (domain-entities §4.1).
Ninguna respuesta de la SPA ni de la API permite ser embebida (`frame-ancestors 'none'`).
Solo dos perfiles admiten el mismo origen: `grafana` (el iframe del dashboard, U10 BR-U10-16) y
`auth` (el iframe de la comprobación silenciosa de sesión de Keycloak) (revisión del Infrastructure Design de U10, 2026-10-10; antes decía que solo
`/grafana/**`). Todos los perfiles envían `Cross-Origin-Opener-Policy: same-origin`, que conserva
`window.opener` entre páginas del mismo origen, como necesita el step-up (revisión del Infrastructure Design de U10, 2026-10-10). Los perfiles `spa` y `api` exigen Trusted Types con `trusted-types 'none'` (NFR Requirements de U10, 2026-10-10, Q7).

**BR-U2-14 — Errores del gateway.** Las respuestas de error que genera el propio gateway
(401, 403, 404, 413, 429, 503) son `Problem` genéricos con `correlation_id` y sin detalles
de enrutamiento ni de versión del proxy. Se ocultan las cabeceras `server` y `x-envoy-*`.

## 6. Realm como código y administración (Q10, Q11)

**BR-U2-12 — Cambios al realm.**
- Toda configuración del realm sale de `realm.{env}.yaml` en Git y la aplica `keycloak-config-cli` como hook de un sync manual (AUTONOMIA-01).
- La consola de administración solo es accesible por `hostname-admin` interno, sin ruta en el gateway, vía `kubectl port-forward` con aprobación.
- Un CronJob diario exporta el realm y lo compara con Git (sin secretos); cualquier diferencia emite `RealmDrift` (SEV2).
- El login de `break-glass` emite `BreakGlassLogin` (SEV1).

**BR-U2-15 — Mapeo LDAP.** En producción, el rol sale de la tabla `group-role-map`.
Cambiar esa tabla es un cambio de realm (PR + sync manual). Un usuario LDAP sin grupo
mapeado puede autenticarse, pero no tiene rol: el **gateway** le responde 403 en
`/api/console/**`, que exige un rol de negocio (domain-entities §4), y el BFF también lo
rechazaría (defensa en profundidad; revisión del Infrastructure Design de U10, 2026-10-10).

## 7. Eventos (Q12)

**BR-U2-16 — Eventos sin identificadores personales directos.** Los eventos de login y de
administración se emiten con `userId` (UUID) y nunca con `username` ni `email`. La
correlación con los logs de los servicios se hace por `userId` = `sub` =
`principal_subject`. Retención: la de Loki (90 días, U1).

**BR-U2-17 — Alertas de identidad.**

| Alerta | Origen | Severidad |
|---|---|---|
| `AuthDeniedBurst` | `LOGIN_ERROR` y bloqueos por encima del umbral; 401/403 de U0 | SEV2 |
| `BreakGlassLogin` | Login del usuario `break-glass` | SEV1 |
| `RealmDrift` | Diferencia entre el realm exportado y Git | SEV2 |
| `RoleConflict` | Usuario LDAP en dos grupos mapeados | SEV2 |

## 8. Cambios a contratos de otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 BR-U0-70 | `aud` **contiene** el servicio (antes «igual») | Q7: token de usuario con varias audiencias |
| U0 BR-U0-72, `Principal`, `RegistryEntryIn.actor`, `RouteContract` | Step-up con `acr = mfa` y `auth_time ≤ mfa_max_age`; `acr`/`auth_time` en el actor del registro; `mfa_max_age` en `RouteContract` | Q3 |
| U0 plan de tareas, Paso 11 | Pruebas de los bordes de 900 s y de la audiencia múltiple | Q3, Q7 |
| U2 (esta unidad), por U8 INF-U8-01 y 02 | Cliente nuevo `case-worker` (`case:recommend`, `governance:read-serving`, `governance:read-feature-spec`); `case-service` sin esos scopes y, en el realm de producción, sin `core:read-credit` ni la audiencia `core-banking-mock` (domain-entities §2.2) | U8 Infrastructure Design, 2026-10-08 |
| U2 (esta unidad), por el FD de U9 | Cliente nuevo `bias-monitoring-job` (`governance:freeze`, `registry:read:monitoring`); `bias-monitoring-service` solo con `registry:read:monitoring`; `realm-lint` y PBT-U2-03: `governance:freeze` solo en `bias-monitoring-job` (domain-entities §2.2) | FD de U9, 2026-10-08; tercera revisión del FD de U9, 2026-10-10 |
| U2 (esta unidad), revisión del Infrastructure Design de U10, 2026-10-10 | BR-U2-04 y business-logic-model §2.2 con el step-up en ventana emergente; BR-U2-13 y PBT-U2-05 con `auth` además de `grafana`; COOP `same-origin` en todos los perfiles; rutas `/callback` y `/stepup-callback` de la SPA; afinidad por cookie en `/`; usuarios de prueba con nombres en domain-entities §3; BR-U2-15 con el 403 en el gateway; límite de `/auth/**` por IP adecuado a un NAT | Revisión del Infrastructure Design de U10 |
| U2 (esta unidad), por el Infrastructure Design de U10 | ~~Usuarios de prueba por rol con TOTP solo en `realm.kind.yaml`; `realm-lint` los rechaza en staging y producción~~ **Superada** por la fila de la revisión del Infrastructure Design de U10: dos usuarios nombrados por rol en kind **y** staging (domain-entities §3); `realm-lint` rechaza usuarios locales en producción salvo `break-glass` | Infrastructure Design de U10, 2026-10-10, Q6 |
| U2 (esta unidad), segunda revisión del Infrastructure Design de U10, 2026-10-10 | Rol técnico `operacion` (Grafana: operación y silencios por F109); equipos de Grafana `cumplimiento` y `cro` para la carpeta `Vectra / Sesgo` de U9; frase sobrante de BR-U2-13 quitada | Segunda revisión del Infrastructure Design de U10 |
| U2 (esta unidad), por el NFR Requirements de U10 | CSP de los perfiles `spa` y `api` con `require-trusted-types-for 'script'; trusted-types 'none'` (BR-U2-13, domain-entities §4.1) | NFR Requirements de U10, 2026-10-10, Q7 |
| U2 (esta unidad), por el FD de U10 | `vectra-console` registra además el redirect URI exacto `/stepup-callback` (step-up en ventana emergente, BR-U10-06) | Revisión del FD de U10, 2026-10-10, A1 |
