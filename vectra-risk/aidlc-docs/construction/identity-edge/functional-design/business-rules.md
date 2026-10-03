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
`auth_time` de ≤ 900 s (BR-U0-72). La SPA, al recibir `mfa_required`, inicia un nuevo
Authorization Code con `prompt=login`, `max_age=0` y `acr_values=mfa`, y reintenta la acción.
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
valida firma (JWKS), `exp`, `iss`, el `azp` esperado y los claims de la tabla de rutas.
Un fallo responde 401 o 403 con `Problem`. El servicio de destino **vuelve** a validar
todo (BR-U0-70..72): el gateway es la primera capa, no la única.

**BR-U2-13 — Cabeceras por perfil.** Cada ruta aplica su perfil (domain-entities §4.1).
Ninguna respuesta de la SPA ni de la API permite ser embebida (`frame-ancestors 'none'`).
Solo `/grafana/**` permite el mismo origen.

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
mapeado puede autenticarse, pero no tiene rol: el BFF le responde 403 en todo.

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
