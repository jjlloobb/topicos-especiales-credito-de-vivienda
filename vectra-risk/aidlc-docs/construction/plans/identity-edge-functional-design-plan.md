# Plan de Functional Design — U2 `identity-edge`

**Alcance de la unidad** (`unit-of-work.md` §1):
- **realm de Keycloak como código**: roles, MFA obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`, protección contra fuerza bruta, clientes (SPA, Grafana e identidades de servicio con los scopes de U0) y consola de administración no expuesta;
- **Envoy Gateway**: rutas F01–F08, validación de JWT, rate limiting, límite de payload, access log y cabeceras de seguridad de la SPA.

**Historias (dueña):** US-601 (autenticación con roles y MFA), US-611 (endurecimiento del
gateway y de la SPA). Contribuye a US-602 (el gateway es la primera capa de autorización).

**Ya decidido** (no se pregunta):
- roles `analista`, `ingeniero_riesgo`, `cro`, `cumplimiento`, y MFA obligatorio para los tres últimos (personas, requirements);
- SPA con Authorization Code + PKCE (`components.md`);
- catálogo de scopes de servicio en U0 (domain-entities §7.2), incluidos `core:read-credit` y `core:write-credit` (este último sin titular);
- validación de JWT en los servicios (BR-U0-70..73) y en el gateway (F03);
- consola de administración no expuesta (X10); el gateway es la única entrada (X09);
- Keycloak 2 réplicas en `vectra-identity` con `keycloak-db` (U1); federación con el LDAP del banco (F73) solo en producción real.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Separación de funciones entre roles (Business Rules)
El CRO aprueba modelos y políticas; cumplimiento reactiva modelos congelados y aprueba
fuentes; el ingeniero registra y valida. Si una persona tiene dos roles, puede aprobar lo
que ella misma propuso.

A) **Un solo rol de negocio por usuario.** El realm lo hace cumplir: una prueba sobre el realm exportado y una regla en la federación con LDAP que rechaza usuarios con dos roles de negocio. Las combinaciones `ingeniero_riesgo`+`cro`, `cro`+`cumplimiento` e `ingeniero_riesgo`+`cumplimiento` quedan prohibidas. Además, governance verifica que quien aprueba no es quien propuso (eso lo diseña U4) (recomendado)

B) Varios roles por usuario; solo governance verifica que aprobador ≠ proponente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Método de MFA (Business Rules, US-601)

A) **TOTP** (aplicación autenticadora) obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`, configurado como *required action* en el primer login. **WebAuthn** opcional como segundo método. Para `analista`, MFA disponible y no obligatorio (recomendado: funciona sin hardware y el banco puede endurecerlo después)

B) WebAuthn (llave de seguridad o passkey) obligatorio para los aprobadores

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Re-autenticación para acciones de aprobación (Business Rules)
Todas las acciones con «MFA = sí» de la tabla del BFF son firmas que quedan a nombre del
usuario en el registro.

A) **Step-up con antigüedad máxima**:
   - las acciones con MFA exigen `acr = mfa` **y** `auth_time` de **≤ 15 min**;
   - si la autenticación es más antigua, el BFF responde `mfa_required` y la SPA pide re-autenticar con `prompt=login` y `max_age=0`;
   - se registran el `acr` y el `auth_time` de la firma en el registro.

   (Recomendado: una sesión abierta en un puesto desatendido no basta para firmar)

B) Basta con que la sesión se haya iniciado con MFA, sin límite de antigüedad

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Protección contra fuerza bruta (Business Rules, US-601 «N intentos»)

A) Keycloak *brute force detection*:
   - **5 fallos** → bloqueo temporal de 1 min, duplicado en cada nueva serie, hasta un máximo de 15 min;
   - **20 fallos en 12 h** → bloqueo permanente hasta que lo levante un administrador.

   Cada bloqueo emite un evento que alimenta `AuthDeniedBurst` (SEV2). El rate limit del gateway sobre `/auth/**` (Q8) es la primera barrera (recomendado)

B) 10 fallos → bloqueo temporal de 30 min, sin bloqueo permanente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Vida de tokens y sesiones (Business Logic / Security)

A) **Access token de 5 min**, refresh token con **rotación** (un solo uso). Sesión SSO con inactividad máxima de **30 min** y duración máxima de **10 h** (una jornada). La SPA guarda los tokens **solo en memoria** (nunca en `localStorage` ni `sessionStorage`). Tokens de identidades de servicio de 5 min, sin refresh: se piden de nuevo con client credentials (recomendado)

B) Access token de 30 min y sesión de 8 h sin rotación de refresh

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Autenticación de las identidades de servicio (Security)

A) **`private_key_jwt`**: cada servicio firma su aserción con una llave privada que entrega ESO desde la bóveda; Keycloak solo conoce la llave pública. No hay secretos compartidos que puedan filtrarse desde Keycloak (recomendado)

B) `client_secret` gestionado por ESO

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Audiencia del token de usuario que el BFF propaga (Domain Model / Integration)
El BFF propaga el token del usuario y el servicio de destino vuelve a validar rol y objeto.
BR-U0-70 exige `aud` del servicio.

A) **Token de usuario con varias audiencias**: `console-bff` más los servicios a los que el BFF llama en nombre del usuario (`case-service`, `governance-service`, `decision-registry-service`, `bias-monitoring-service`, `explainability-service`). Cada servicio acepta el token si su nombre está **en** `aud` (semántica estándar de RFC 7519). Se precisa BR-U0-70 de «igual» a «contiene». Los servicios internos no son alcanzables desde fuera del gateway (X09 y NetworkPolicy) (recomendado: simple y conforme al estándar)

B) **Token exchange** (RFC 8693): el BFF cambia el token del usuario por uno con la audiencia exacta del destino en cada llamada

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Límites del gateway (Business Rules, US-611)

A) Rate limiting y límites de tamaño:

   | Ruta | Límite de tasa | Tamaño máximo |
   |---|---|---|
   | `/api/console/**` | 20 req/s por usuario (`sub`), ráfaga de 40 | 64 KiB |
   | `/api/intake/**` | 10 req/s por cliente `channel`, ráfaga de 20 | **32 KiB** (BR-U0-21) |
   | `/api/promotion/**` | 1 req/s por usuario | 16 KiB |
   | `/auth/**` (login y token) | 10 req/min por IP | Por defecto de Keycloak |

   Además, un límite global de 200 req/s. Las respuestas 429 y 413 usan `Problem` (U0) (recomendado: holgado para el volumen de diseño de U1 y estricto con el login)

B) Un solo límite global de 100 req/s, sin límites por usuario

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Cabeceras de seguridad y dashboards embebidos (Business Rules, US-611, F06)
F06 embebe dashboards de Grafana en la SPA, y eso choca con `X-Frame-Options: DENY`.

A) **Cabeceras por ruta**:
   - SPA y API: `X-Frame-Options: DENY` y CSP `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'`.
   - Solo `/grafana/**`: `frame-ancestors 'self'` y `X-Frame-Options: SAMEORIGIN`, porque se sirve en el mismo origen.
   - En todas las rutas: HSTS de 1 año con `includeSubDomains`, `nosniff` y `Referrer-Policy: no-referrer`.

   (Recomendado: conserva el embebido de F06 sin relajar la SPA)

B) Sin embebido: Grafana se abre en otra pestaña y `DENY` aplica en todas las rutas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Realm como código y consola de administración (Business Logic / Security)

A) **`keycloak-config-cli`** como Job de Argo CD (hook de sync): aplica `realm.yaml` desde Git solo cuando un humano sincroniza (AUTONOMIA-01).
   - La consola de administración vive en un hostname interno separado (`hostname-admin`) que el gateway **no** enruta, y solo se alcanza con `kubectl port-forward` con aprobación.
   - Los cambios al realm hechos a mano se detectan con una comparación periódica (realm exportado contra Git) que alerta si hay deriva.

   (Recomendado)

B) Terraform con el proveedor de Keycloak

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Usuarios en kind, staging y producción (Domain Model)

A) **kind y staging**: usuarios sintéticos por rol en el `realm.yaml` del entorno (al menos 2 por rol, para probar que aprobador ≠ proponente), con credenciales desde ESO. **Producción**: federación con el LDAP del banco (F73), con roles asignados por **grupo** de LDAP y una tabla de mapeo grupo → rol versionada en el realm. No hay usuarios locales en producción salvo una cuenta de emergencia (*break-glass*) con MFA, cuyo uso genera una alerta SEV1 (recomendado)

B) Usuarios locales de Keycloak en todos los entornos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12 — Eventos de Keycloak (Business Rules, SECURITY-14)

A) **Eventos de login y de administración** habilitados, emitidos como JSON a stdout (los recoge Alloy hacia Loki, 90 días).
   - Campos: `userId` (UUID), tipo de evento, `clientId`, código de error, IP y `realmId`.
   - **Sin** username ni email: el `userId` es el mismo `sub` que usa `principal_subject` (U0), así que se pueden correlacionar.
   - Los eventos `LOGIN_ERROR` y los bloqueos alimentan `AuthDeniedBurst`.

   (Recomendado)

B) Eventos con username y email para facilitar la investigación

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto de la unidad (unit-of-work, story map, flujos F01–F08 y F50, X09–X10, catálogo de scopes de U0, tabla de roles del BFF)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/identity-edge/functional-design/domain-entities.md` (roles, clientes, scopes, audiencias, claims, rutas)
- [x] 4. Generar `construction/identity-edge/functional-design/business-rules.md` (SoD, MFA y step-up, fuerza bruta, sesiones, límites, cabeceras, realm como código)
- [x] 5. Generar `construction/identity-edge/functional-design/business-logic-model.md` (flujos de login, step-up, client credentials, enrutamiento y validación en el gateway; propiedades PBT)
- [x] 6. Verificar el cumplimiento de las extensiones
