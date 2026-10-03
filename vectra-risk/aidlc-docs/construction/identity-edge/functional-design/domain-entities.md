# Entidades de dominio — U2 `identity-edge`

Decisiones del plan (`identity-edge-functional-design-plan.md`, Q1–Q12 = A). Los tipos
compartidos (`Principal`, scopes, `Problem`) son de U0 y no se redefinen aquí.

---

## 1. Realm `vectra`

### 1.1 Roles de negocio (realm roles)

| Rol | MFA | Persona | Notas |
|---|---|---|---|
| `analista` | Disponible, no obligatorio | P1 | — |
| `ingeniero_riesgo` | **Obligatorio** (TOTP) | P2 | — |
| `cro` | **Obligatorio** (TOTP) | P3 | — |
| `cumplimiento` | **Obligatorio** (TOTP) | P4 | — |

**Un solo rol de negocio por usuario** (Q1, BR-U2-01). Roles técnicos fuera de este
conjunto: `realm-admin` (solo la cuenta *break-glass* y el `keycloak-config-cli`).

### 1.2 Niveles de autenticación (ACR)

| `acr` | Significado | Cómo se obtiene |
|---|---|---|
| `pwd` | Solo contraseña (o LDAP) | Login sin segundo factor (`analista` sin MFA) |
| `mfa` | Contraseña + TOTP o WebAuthn | Login con segundo factor; obligatorio para los tres roles aprobadores |

Mapeo de LoA de Keycloak: `pwd` = 1, `mfa` = 2. El token incluye `acr`, `amr` y `auth_time`.

### 1.3 Claims del token de usuario

| Claim | Contenido |
|---|---|
| `sub` | UUID del usuario (el mismo `userId` de los eventos y el `principal_subject` de U0) |
| `roles` | Arreglo plano con el rol de negocio (mapper desde `realm_access.roles`) |
| `aud` | `console-bff`, `case-service`, `governance-service`, `decision-registry-service`, `bias-monitoring-service`, `explainability-service` (Q7) |
| `acr`, `amr`, `auth_time` | Nivel y momento de la autenticación (Q3) |
| `azp` | `vectra-console` (o `promotion-tool`) |

**Sin** `preferred_username`, `email` ni `name` en el access token. El ID token, que solo
consume la SPA, lleva `name` para mostrarlo en pantalla.

## 2. Clientes

### 2.1 Clientes de usuario

| Client ID | Tipo | Flujo | Audiencias / scopes | Notas |
|---|---|---|---|---|
| `vectra-console` | Público | Authorization Code + **PKCE (S256)** | Mapper de audiencias de §1.3 | Redirect URIs exactas (sin comodines); `post_logout_redirect_uris` exactas; orígenes web = el host del gateway |
| `promotion-tool` | Público | Authorization Code + PKCE con *loopback redirect* (`http://127.0.0.1:{puerto}`) | `aud = governance-service`; scope opcional `governance:promotion`, asignable solo al rol `ingeniero_riesgo` | Exige `acr = mfa` (F08) |
| `grafana` | Confidencial (`private_key_jwt`) | Authorization Code | Mapper `roles` → rol de Grafana (`cro`, `cumplimiento` → Viewer de los dashboards de negocio; `ingeniero_riesgo` → Viewer de operación) | F06 |

### 2.2 Identidades de servicio (client credentials, `private_key_jwt`)

Los scopes salen del catálogo de U0 (domain-entities §7.2). Cada cliente solo puede pedir
sus scopes (*optional client scopes* restringidos) y la audiencia correspondiente.

| Client ID | Scopes | Audiencia del token |
|---|---|---|
| `case-service` | `case:recommend`, `registry:append:case`, `core:read-credit` | `scoring-service`, `decision-registry-service`, `core-banking-mock` |
| `scoring-service` | `scoring:explain`, `governance:read-serving`, `registry:append:scoring` | `explainability-service`, `governance-service`, `decision-registry-service` |
| `explainability-service` | `registry:read:explanation` | `decision-registry-service` |
| `governance-service` | `bias:compare`, `registry:append:governance` | `bias-monitoring-service`, `decision-registry-service` |
| `bias-monitoring-service` | `governance:freeze`, `registry:read:monitoring` | `governance-service`, `decision-registry-service` |
| `model-validation-job` | `governance:validation-report` | `governance-service` |
| `product-metrics` | `registry:read:metrics` | `decision-registry-service` |
| `channel` | `intake:submit` | `case-service` |

- **Ningún cliente tiene `core:write-credit`** (AUTONOMIA-03). Una prueba sobre el realm lo verifica.
- Los clientes de servicio no tienen roles de usuario ni `acr = mfa`, así que nunca pasan un endpoint con MFA.
- Las llaves públicas de cada cliente se registran en el realm; las privadas las entrega ESO (U1) desde la bóveda.

## 3. Usuarios por entorno (Q11)

| Entorno | Fuente | Contenido |
|---|---|---|
| kind / staging | `realm.{env}.yaml` | ≥ 2 usuarios sintéticos por rol (para probar aprobador ≠ proponente); credenciales desde ESO |
| prod | Federación LDAP (F73) | Rol por **grupo** de LDAP según la tabla `group-role-map` versionada en el realm; sin usuarios locales salvo `break-glass` |

`break-glass`: un usuario local con `realm-admin` y MFA, credencial en sobre sellado del
banco; su login genera una alerta SEV1 (BR-U2-12).

## 4. Rutas del gateway (Envoy Gateway)

| Ruta | Flujo | Destino | Autenticación en el gateway | Límite de tasa | Tamaño máx. | Cabeceras |
|---|---|---|---|---|---|---|
| `/` y estáticos | F02 | console-spa | Pública | Global | — | Perfil `spa` |
| `/api/console/**` | F03 | console-bff | JWT válido de `vectra-console`, cualquier rol de negocio | 20 req/s por `sub`, ráfaga 40 | 64 KiB | Perfil `api` |
| `/api/intake/**` (solo `POST /v1/intake/applications`) | F04, F07 | case-service | JWT de `channel` con `intake:submit` | 10 req/s por cliente, ráfaga 20 | 32 KiB | Perfil `api` |
| `/api/promotion/**` (solo `GET /v1/models?state=aprobado` y `POST /v1/models/{id}/activation`) | F08 | governance-service | JWT de `promotion-tool`, rol `ingeniero_riesgo`, `governance:promotion`, `acr = mfa` | 1 req/s por `sub` | 16 KiB | Perfil `api` |
| `/auth/realms/vectra/**` (solo endpoints públicos: autorización, token, JWKS, logout, cuenta) | F05 | Keycloak | Pública | 10 req/min por IP en login y token | Por defecto | Perfil `auth` |
| `/grafana/**` | F06 | Grafana | Grafana hace su propio OIDC | Global | 64 KiB | Perfil `grafana` |
| `/federate` | F09 | Prometheus | Basic auth del usuario de solo lectura del banco | 1 req/s | — | Perfil `api` |

- F09 está **deshabilitada por defecto** (`enabled: false` en los values).
- Cualquier otra ruta, incluida `/auth/admin/**`, devuelve **404** (X10).
- Límite global: 200 req/s.

### 4.1 Perfiles de cabeceras (Q9)

| Perfil | Cabeceras |
|---|---|
| `spa` y `api` | `X-Frame-Options: DENY`; CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'` |
| `grafana` | `X-Frame-Options: SAMEORIGIN`; `Content-Security-Policy: frame-ancestors 'self'` |
| `auth` | Las de Keycloak, más `frame-ancestors 'self'` (el chequeo silencioso de sesión usa un iframe del mismo origen) |
| Todos | `Strict-Transport-Security: max-age=31536000; includeSubDomains`; `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer` |

## 5. Eventos de Keycloak (Q12)

`KeycloakEvent` (JSON a stdout): `time`, `type`, `realmId`, `clientId`, `userId`, `ipAddress`,
`error?`, `details` filtrados (sin `username` ni `email`). Eventos de administración:
`operationType`, `resourceType`, `resourcePath`, `authDetails.userId`.

## 6. Parámetros versionados

| Parámetro | Valor | Regla |
|---|---|---|
| `mfa_max_age` | 900 s | BR-U2-04 / BR-U0-72 |
| Access token | 300 s | BR-U2-06 |
| SSO idle / max | 1 800 s / 36 000 s | BR-U2-06 |
| Fuerza bruta | 5 fallos → 60 s ×2 hasta 900 s; 20 en 12 h → permanente | BR-U2-05 |
