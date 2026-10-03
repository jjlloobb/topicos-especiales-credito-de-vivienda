# Modelo de lógica — U2 `identity-edge`

U2 casi no tiene código propio: su lógica es **configuración** (realm y rutas) más unos
pocos validadores que corren en CI. La lógica de autorización en los servicios es de U0.

## 1. Módulos lógicos

| Módulo | Forma | Responsabilidad | Reglas |
|---|---|---|---|
| `realm` | `realm.{env}.yaml` + `keycloak-config-cli` | Roles, clientes, scopes, audiencias, MFA, sesiones, fuerza bruta, eventos, LDAP | BR-U2-01, 03, 05, 06, 09, 12, 15, 16 |
| `realm-lint` | Script de CI | Validar el `realm.yaml`: SoD, clientes sin comodines, scopes del catálogo de U0, nadie con `core:write-credit`, sin secretos compartidos en clientes de servicio | BR-U2-01, 09; AUTONOMIA-03 |
| `realm-drift` | CronJob | Exportar el realm y compararlo con Git | BR-U2-12 |
| `gateway-routes` | Manifiestos de Envoy Gateway (`HTTPRoute`, `SecurityPolicy`, `BackendTrafficPolicy`, `ClientTrafficPolicy`) generados desde una tabla de rutas | Rutas cerradas, JWT, límites, cabeceras, errores | BR-U2-08, 10, 11, 13, 14 |
| `route-gen` | Script de CI | Generar los manifiestos del gateway desde `routes.yaml` (domain-entities §4) y probarlos | BR-U2-10 |
| `stepup` | En la SPA (U10) y en `authz` de U0 | Re-autenticar ante `mfa_required` | BR-U2-04, BR-U0-72 |

## 2. Flujos

### 2.1 Login de un aprobador

```text
navegador -> gateway /auth/... -> Keycloak (Authorization Code + PKCE, S256)
  usuario + contraseña (o LDAP en prod)
  ¿rol aprobador y sin TOTP configurado? -> required action: configurar TOTP (BR-U2-03)
  TOTP -> acr = mfa, auth_time = ahora
  ¿5 fallos? -> bloqueo temporal (BR-U2-05) + evento
-> código -> SPA canjea por tokens (en memoria, BR-U2-07)
```

### 2.2 Firma con step-up

```text
SPA -> POST /api/console/models/{id}/approval
  gateway: JWT válido (BR-U2-11) -> BFF
  BFF/servicio (U0): rol cro ✓; acr = mfa ✓; now - auth_time <= 900 s ?
     no -> 403 mfa_required
           SPA: authorize?prompt=login&max_age=0&acr_values=mfa -> TOTP -> token nuevo
           SPA reintenta la acción
     sí -> acción; la entrada del registro guarda actor.acr y actor.auth_time
```

### 2.3 Identidad de servicio

```text
servicio -> Keycloak /token (client_credentials, private_key_jwt, scope=<scopes>, audience=<destino>)
         <- access token (300 s, aud = destino, scope ⊆ los permitidos al cliente)
servicio -> destino (token en Authorization) -> destino valida (BR-U0-70..71)
```

### 2.4 Request en el gateway

```text
request
  -> ClientTrafficPolicy: TLS, límite de tamaño por ruta (413)
  -> HTTPRoute: ¿ruta en la tabla? no -> 404 genérico (BR-U2-10)
  -> SecurityPolicy: JWT (firma, exp, iss, azp, claims) -> 401/403 (BR-U2-11)
  -> BackendTrafficPolicy: rate limit por sub / cliente / IP -> 429 + Retry-After (BR-U2-08)
  -> cabeceras de respuesta por perfil (BR-U2-13); se ocultan server y x-envoy-* (BR-U2-14)
  -> access log (sin cuerpo ni query string; route_template, status, duración, correlation_id)
```

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U2-01 | `realm-lint` | Para todo conjunto de roles generado, el validador acepta ⇔ contiene como máximo un rol de negocio | Oráculo | Subconjuntos de los 4 roles de negocio más roles técnicos |
| PBT-U2-02 | `realm-lint` / mapeo LDAP | Para toda asignación de grupos LDAP, el usuario obtiene un rol ⇔ pertenece exactamente a un grupo mapeado; con dos o más, no obtiene ninguno | Oráculo | Conjuntos de grupos mapeados y no mapeados |
| PBT-U2-03 | `realm-lint` | Para todo cliente del realm generado: ningún scope fuera del catálogo de U0 pasa, y `core:write-credit` no pasa nunca | Invariante | Clientes con scopes arbitrarios del catálogo y fuera de él |
| PBT-U2-04 | `route-gen` | Para todo path generado, el gateway lo enruta ⇔ coincide con una entrada de `routes.yaml`; todo path bajo `/auth/admin` o del realm `master` da 404 | Invariante | Paths aleatorios, prefijos de las rutas válidas, codificaciones (`%2F`, `..`, mayúsculas) |
| PBT-U2-05 | `route-gen` | Para toda ruta generada, el perfil de cabeceras aplicado es el de su fila, y solo `/grafana/**` permite `frame-ancestors 'self'` | Invariante | Rutas de la tabla y paths dentro de cada una |
| PBT-U2-06 | `route-gen` | `generate(routes.yaml)` es determinista: dos ejecuciones producen manifiestos idénticos | Idempotencia | Tablas de rutas con orden de entradas permutado |
| PBT-U2-07 | `stepup` (U0 `authz`) | Para todo `acr` y `auth_time` generados: la acción con MFA se permite ⇔ `acr = mfa` ∧ `now − auth_time ≤ 900` | Oráculo | `acr` ∈ {`pwd`, `mfa`, ausente, otro}; `auth_time` alrededor del borde (899, 900, 901 s) y en el futuro |

**PBT-06 (stateful):** se aplica al bloqueo por fuerza bruta solo como prueba de modelo de
la **configuración**: un modelo de estados (contador de fallos, bloqueos y duraciones) se
compara con el comportamiento de un Keycloak de prueba en kind, con secuencias generadas
de éxitos y fallos. Corre en el entorno con aprobación del operador (U1, Paso 19), no en
CI. Se marca PBT-U2-08.

**Pruebas de ejemplo obligatorias (PBT-10):**
- un aprobador sin TOTP no obtiene token (US-601);
- 5 fallos → bloqueo, y el evento llega con `userId` y sin `username`;
- `curl -I` a la SPA: CSP sin `unsafe-inline`, HSTS, `nosniff`, `DENY` y `Referrer-Policy` (US-611);
- más de 20 req/s de un mismo usuario → 429 con `Retry-After` (US-611);
- `/auth/admin` → 404 (X10);
- un token de `scoring-service` presentado a `case-service` → 401 (audiencia);
- el refresh token reusado → sesión revocada.

## 4. Cumplimiento de extensiones (Functional Design U2)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-04 | Cumple | BR-U2-13 |
| SECURITY-08 | Cumple | BR-U2-11 (primera capa); U0 revalida |
| SECURITY-09 | Cumple | BR-U2-10, 12, 14 (consola admin no expuesta, errores genéricos, sin cabeceras de versión) |
| SECURITY-11 | Cumple | BR-U2-08 (rate limiting), autenticación aislada en Keycloak y el gateway |
| SECURITY-12 | Cumple | BR-U2-03, 05, 06, 09 |
| SECURITY-14 | Cumple | BR-U2-16, 17 |
| AUTONOMIA-01 | Cumple | BR-U2-12 (realm solo por sync manual) |
| AUTONOMIA-03 | Cumple | Ningún cliente con `core:write-credit` (PBT-U2-03) |
| AUTONOMIA-05 | Cumple | Eventos y access log sin PII de solicitantes ni identificadores directos de empleados |
| PBT-01 | Cumple | §3 |
| PBT-06 | Cumple | PBT-U2-08 (modelo de la configuración de fuerza bruta) |
