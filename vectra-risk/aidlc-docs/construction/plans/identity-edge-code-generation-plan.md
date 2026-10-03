# Plan de tareas (Code Generation Part 1) — U2 `identity-edge`

**Este plan es la única fuente de verdad para generar el código de U2.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U2. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U2 `identity-edge`: identidad (Keycloak) y borde (Envoy Gateway) |
| Historias (dueña) | US-601 (autenticación con roles y MFA), US-611 (endurecimiento del gateway y de la SPA) |
| Contribuye a | US-602 (primera capa de autorización en el gateway) |
| Ubicación | `vectra-risk/identity-edge/` (monorepo) y Applications en `vectra-risk-gitops` |
| Datos propios | El realm, en `keycloak-db` (cluster de U1). Keycloak migra su propio esquema al arrancar una versión nueva; una actualización de versión entra por PR + sync manual |
| Depende de | U0 (catálogo de scopes, `Problem`, BR-U0-70..72), U1 (plataforma completa: `flows.yaml`, Kyverno, ESO, cert-manager, observabilidad, waves) |
| Lo consumen | Todas las unidades: rutas, clientes de Keycloak, JWKS y step-up (`shared-infrastructure.md` §4) |

**Diseño de entrada:**
- Functional Design: `construction/identity-edge/functional-design/` (BR-U2-01..17, PBT-U2-01..08).
- NFR Requirements: `construction/identity-edge/nfr-requirements/` (NFR-U2-01..42).
- NFR Design: `construction/identity-edge/nfr-design/` (P-U2-01..09).
- Infrastructure Design: `construction/identity-edge/infrastructure-design/` (INF-U2-01..08).

**AUTONOMIA-01:** igual que en U1. Las verificaciones **estáticas** corren en CI; las que
necesitan un clúster las ejecuta **un operador en kind** después de un PR aprobado (Paso 16),
y la evidencia se adjunta al PR.

### Estructura de destino

```text
vectra-risk/identity-edge/
|-- Makefile                       # check (verificaciones estáticas)
|-- pyproject.toml                 # miembro del workspace uv (U0)
|-- keycloak/
|   |-- Dockerfile                 # oficial pinneada + tema + kc.sh build
|   |-- themes/vectra/             # tema hijo de keycloak.v2, messages_es.properties
|   |-- realm/                     # realm.{kind,staging,prod}.yaml, group-role-map.yaml
|   `-- values/                    # keycloakx + keycloak-config-cli
|-- gateway/
|   |-- routes.yaml                # F01–F09 con límites, perfiles y timeouts
|   |-- generated/                 # HTTPRoute, SecurityPolicy, BackendTrafficPolicy, ClientTrafficPolicy
|   `-- values/                    # Envoy Gateway, EnvoyProxy, Gateway, certificado
|-- ratelimit/                     # values del servicio y configuración generada
|-- charts/valkey/                 # chart propio mínimo (Valkey + Sentinel)
|-- jobs/                          # realm-drift, exportador de antigüedad de llaves
|-- observability/                 # PrometheusRule, ServiceMonitor, tests de reglas
|-- runbooks/
|-- tools/                         # realm_lint.py, route_gen.py, realm_diff.py
`-- tests/                         # unit/, property/, e2e/ (Playwright), load/ (k6)
```

---

## 2. Pasos

### Bloque A — Estructura

- [ ] **Paso 1 — Esqueleto de `identity-edge/`**
  - Directorios de §1; `pyproject.toml` como miembro del workspace `uv` de U0; `Makefile` con el objetivo `check`; perfiles de Hypothesis importados de `contracts/tests/conftest.py`.
  - **Aceptación**: `uv sync --frozen && make -C identity-edge check` termina en 0 sobre el esqueleto.

### Bloque B — Keycloak

- [ ] **Paso 2 — Realm como código**
  - `realm.{env}.yaml`:
    - los 4 roles de negocio y el mapeo de ACR (`pwd` = 1, `mfa` = 2);
    - el flujo de login con OTP **condicional por rol** (obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`) y TOTP como *required action*;
    - WebAuthn opcional;
    - fuerza bruta (BR-U2-05), vidas de tokens y sesiones con rotación de refresh (BR-U2-06), sesiones persistentes y política de contraseñas (NFR-U2-24);
    - eventos de login y de administración sin username ni email (BR-U2-16).
  - Clientes de domain-entities §2:
    - `vectra-console` y `promotion-tool` (PKCE S256, redirect URIs exactas);
    - `grafana` y los 8 de servicio con `private_key_jwt`;
    - mapper de audiencias y mapper `roles`;
    - access token sin `preferred_username`, `email` ni `name`.
  - kind y staging: ≥ 2 usuarios sintéticos por rol. prod: federación LDAPS `READ_ONLY` con `group-role-map.yaml` (INF-U2-07) y el usuario `break-glass`.
  - Diseño: BR-U2-01, 03..07, 09, 12, 15, 16; NFR-U2-24; INF-U2-07. Historia: US-601.
  - **Aceptación**: `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` termina en 0 (Paso 3).

- [ ] **Paso 3 — `realm-lint` y sus pruebas**
  - El validador verifica:
    - separación de funciones (BR-U2-01) y mapeo de grupos LDAP (BR-U2-15);
    - scopes solo del catálogo de U0 y **ningún cliente con `core:write-credit`**;
    - clientes de servicio sin `client_secret` y sin redirect URIs con comodines;
    - claims prohibidos en el access token;
    - parámetros de §6 de domain-entities y política de contraseñas.
  - Propiedades PBT-U2-01, 02 y 03, con generadores en `tests/strategies/`.
  - Diseño: BR-U2-01, 09, 15; NFR-U2-40; AUTONOMIA-03. Historia: US-601 (su verificación pide la prueba del realm exportado: MFA por rol y fuerza bruta).
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py`, con casos nombrados: un usuario con dos roles → error; un cliente con `core:write-credit` → error.

- [ ] **Paso 4 — Tema `vectra` e imagen de Keycloak**
  - Tema hijo de `keycloak.v2` con `messages_es.properties`, logo y colores; sin JavaScript propio ni recursos de otro origen.
  - `Dockerfile`: imagen oficial 26.x pinneada por digest + tema + `kc.sh build` (`db=postgres`, `health-enabled`, `metrics-enabled`, `cache=ispn`).
  - Diseño: BR-U2-13 (CSP estricta en `/auth/**`, posible porque el tema no tiene JavaScript propio); P-U2-08; INF-U2-08; NFR-U2-25.
  - **Aceptación**: `hadolint identity-edge/keycloak/Dockerfile`; `uv run pytest identity-edge/tests/unit/test_theme.py` (ningún archivo del tema referencia `http(s)://` externos ni `<script>` propio; todas las claves de `messages_es` existen). La construcción, el escaneo y la firma los hace `supply-chain.yml` de U1.

- [ ] **Paso 5 — Despliegue de Keycloak y `keycloak-config-cli`**
  - Values de `keycloakx`:
    - 2 réplicas con HPA de 2 a 4, spread por zona y PDB;
    - `cache-stack` con `jdbc-ping`;
    - `hostname` y `hostname-admin`, `proxy-headers=xforwarded`;
    - puerto de gestión 9000;
    - recursos de INF-U2-06 y prioridad `vectra-high`;
    - Secrets por `ExternalSecret`.
  - `keycloak-config-cli` como Job hook del sync.
  - Diseño: NFR-U2-01, 02, 23, 26; P-U2-04; INF-U2-01, 05, 06. Historia: US-601.
  - **Aceptación**: `helm template` + `conftest test identity-edge/keycloak/` (réplicas, HPA, spread, PDB, `start --optimized`, `hostname-admin` interno, sin Secret plano, hook de sync presente).

- [ ] **Paso 6 — `realm-drift` y exportador de antigüedad de llaves**
  - CronJob diario que exporta el realm, lo normaliza (sin secretos, IDs internos ni timestamps) y lo compara con Git; emite `RealmDrift`.
  - Exportador que publica la antigüedad de la llave de firma activa (`SigningKeyAgeHigh`).
  - Diseño: BR-U2-12; P-U2-05.
  - **Aceptación**: `uv run pytest identity-edge/tests/unit/test_realm_diff.py` y una propiedad: `normalize(normalize(x)) == normalize(x)`, y dos exportaciones que solo difieren en secretos o timestamps no generan diferencias.

### Bloque C — Gateway

- [ ] **Paso 7 — `routes.yaml` y `route-gen`**
  - `routes.yaml` con F01–F09 (F09 con `enabled: false`) según domain-entities §4.
  - `route-gen` genera:
    - **HTTPRoute** cerradas, con 404 genérico para el resto (incluido `/auth/admin/**` y el realm `master`);
    - **SecurityPolicy**: JWT con JWKS por la URL interna, refresco cada 5 min, claims requeridos por ruta y copia de `sub`/`azp` a cabeceras internas;
    - **BackendTrafficPolicy**: descriptores de rate limit, timeouts, reintentos solo idempotentes y outlier detection;
    - **ClientTrafficPolicy**: tamaño máximo por ruta y confianza en `X-Forwarded-For` de 1 salto o PROXY protocol;
    - perfiles de cabeceras;
    - respuestas de error `Problem`;
    - eliminación de `server`, `x-envoy-*` y de las cabeceras internas entrantes y salientes.
  - Propiedades PBT-U2-04, 05 y 06.
  - Diseño: BR-U2-08, 10, 11, 13, 14; P-U2-02, 03, 06, 07; NFR-U2-20, 23, 40, 41. Historias: US-611, US-602.
  - **Aceptación**:
    - `uv run python identity-edge/tools/route_gen.py --check` (los manifiestos versionados coinciden con los generados);
    - `kubeconform` con los CRDs de Gateway API y Envoy Gateway;
    - `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_routes_*.py`;
    - `conftest`: ningún reintento en `POST`/`PUT`/`PATCH`; toda ruta autenticada tiene SecurityPolicy.

- [ ] **Paso 8 — Envoy Gateway, `Gateway` y verificación de la versión pinneada**
  - Values del controlador (`envoy-gateway-system`, 2 réplicas); `EnvoyProxy` (data plane en `vectra-edge`, HPA de 2 a 6, spread, PDB, Service `LoadBalancer` con `externalTrafficPolicy: Local` o PROXY protocol); `GatewayClass`, `Gateway` (HTTPS 443) y `Certificate` con el `ClusterIssuer` de cada entorno; binding K14.
  - **Verificación de la versión pinneada.** Se registra en `identity-edge/docs/adr-envoy-gateway.md` y en `audit.md`:
    1. si se puede desplegar el data plane en el namespace del `Gateway` (INF-U2-02); si no, el data plane va en `envoy-gateway-system` y se ajustan `flows.yaml` y las NetworkPolicies;
    2. cuál de las tres alternativas de P-U2-01 se usa para el modo de fallo por ruta.
  - Diseño: NFR-U2-03, 04, 21, 22, 23; P-U2-01; INF-U2-01, 02. Historia: US-611 (el gateway sirve las cabeceras y los errores genéricos).
  - **Aceptación**:
    - `egctl x translate --from gateway-api --to xds -f identity-edge/gateway/generated/` (traducción offline, sin clúster) y una prueba que inspecciona el xDS: el filtro de rate limit de la ruta `/auth/**` tiene `failure_mode_deny: true` y el de las demás no;
    - `test -s identity-edge/docs/adr-envoy-gateway.md`.

- [ ] **Paso 9 — Servicio de rate limit y Valkey**
  - `envoyproxy/ratelimit` (2 réplicas, gRPC en 8083, métricas en 8081) con la configuración de descriptores generada por `route-gen`.
  - Chart propio de Valkey 8: 2 nodos en zonas distintas, 3 Sentinel, sin persistencia, ACL `ratelimit` desde ESO, usuario `default` deshabilitado, `maxmemory 128mb`, `volatile-ttl`, prioridad `vectra-high`.
  - Diseño: NFR-U2-20, 27, 30; P-U2-04, 06; INF-U2-03, 04. Historia: US-611 (exceso de solicitudes → 429).
  - **Aceptación**: `helm template` + `conftest test identity-edge/ratelimit/ identity-edge/charts/valkey/` (puertos 8083/8081, sin RDB/AOF, ACL presente, `default` deshabilitado, spread por zona); `uv run pytest identity-edge/tests/unit/test_ratelimit_config.py` (los descriptores coinciden con `routes.yaml`).

### Bloque D — Plataforma: red, observabilidad y GitOps

- [ ] **Paso 10 — Flujos y RBAC**
  - Agregar a `platform/network/flows.yaml` de U1: F05, F43, F50, F73 (solo prod), F90–F95 y el scrape de Keycloak (9000), Envoy, rate limit y el exportador de Valkey. Agregar el RBAC K14 y el de `realm-drift`.
  - Diseño: INF-U2-02..04; P-U1-01.
  - **Aceptación**: `uv run python platform/network/generate.py --check` y `uv run pytest platform/network/tests` (los IDs F90–F95 y K14 de `component-dependency.md` están en `flows.yaml`).

- [ ] **Paso 11 — Alertas y runbooks**
  - `PrometheusRule` con las alertas de P-U2-09, incluida `LdapUnavailable`. Runbooks: `keycloak-down`, `rate-limit-backend-down`, `auth-denied-burst`, `break-glass-login`, `realm-drift`, `role-conflict`, `signing-key-rotation`, `gateway-high-latency`, `ldap-unavailable`.
  - Diseño: P-U2-09; BR-U2-17; P-U2-05; NFR-U2-05 (`KeycloakDown`).
  - **Aceptación**: `promtool test rules identity-edge/observability/rules/tests/*.yaml` y `uv run python platform/tests/test_runbooks.py --root identity-edge` (`severity` válida y `runbook_url` existente).

- [ ] **Paso 12 — Applications de GitOps**
  - Applications con sus waves: CRDs de Gateway API y controlador (0), Valkey (2), Keycloak + `keycloak-config-cli` y gateway + rate limit (3). Values por entorno: hostnames (INF-U2-01), issuer y LDAP (prod).
  - Diseño: P-U1-12; INF-U2-01.
  - **Aceptación**: `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync` sobre las Applications nuevas.

### Bloque E — Pruebas de extremo a extremo y de carga (definición)

- [ ] **Paso 13 — Especificación de las pruebas de extremo a extremo**
  - Playwright + `httpx` + `pyotp` + `axe-core`:
    - aprobador sin TOTP → no obtiene token;
    - step-up: firma con `auth_time` > 900 s → `mfa_required` → re-autenticación → éxito;
    - 5 fallos → bloqueo, con el evento con `userId` y sin `username`;
    - refresh reusado → sesión revocada;
    - cabeceras (CSP, HSTS, `nosniff`, `DENY`, `Referrer-Policy`);
    - 429 con `Retry-After`; `/auth/admin` → 404;
    - token de otro servicio → 401;
    - `X-Forwarded-For` falso no cambia la IP registrada;
    - cabecera interna `x-vectra-sub` inyectada → sin efecto;
    - accesibilidad del login.
  - PBT-U2-08: modelo de estados de la fuerza bruta contra el Keycloak de kind.
  - Diseño: PBT-10; NFR-U2-42; BR-U2-03..08, 10, 13, 16; P-U2-06, 08. Historias: US-601, US-611.
  - **Aceptación** (estática): `uv run ruff check identity-edge/tests/e2e` y `uv run pytest identity-edge/tests/e2e --collect-only` lista todos los casos nombrados. La ejecución es del Paso 16.

- [ ] **Paso 14 — Especificación de la prueba de carga**
  - Script k6: 200 usuarios concurrentes con login y token, 8 identidades de servicio renovando cada 5 min, ráfagas contra la consola; umbrales de NFR-U2-10..12 como `thresholds`.
  - Diseño: NFR-U2-10..12.
  - **Aceptación** (estática): `k6 inspect identity-edge/tests/load/identity.js` muestra los umbrales p95 de login (500 ms), token (200 ms) y JWKS (50 ms). La ejecución es del Paso 16.

- [ ] **Paso 15 — Resumen del código de U2**
  - `aidlc-docs/construction/identity-edge/code/README.md`: componente → archivos → verificación → BR/NFR/P/INF.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit identity-edge` (cada BR-U2, NFR-U2, P-U2 e INF-U2 aparece en algún archivo de `identity-edge/`).

### Bloque F — Verificación en kind (con aprobación humana)

- [ ] **Paso 16 — Puerta de aprobación, instalación y pruebas en kind**
  - **Requisito previo**: un PR con los Pasos 1–15 aprobado por un humano, sobre la plataforma de U1 ya instalada en kind (U1, Paso 19).
  - El operador sincroniza manualmente las waves de U2 y ejecuta, con evidencia:
    1. la suite de Playwright y PBT-U2-08 (Paso 13);
    2. la prueba de carga k6 (Paso 14);
    3. `testssl.sh` contra el gateway (NFR-U2-22);
    4. Valkey escalado a 0 → consola 200 y token 503 (P-U2-01);
    5. borrado del pod de Keycloak con sesión activa → el refresh sigue (NFR-U2-02);
    6. controlador de Envoy Gateway escalado a 0 → las rutas siguen (NFR-U2-04);
    7. rotación de la llave de firma con solapamiento (P-U2-05);
    8. un `POST` a un backend que devuelve 503 → exactamente 1 llamada (P-U2-02).
  - Diseño: NFR-U2-02, 04, 10..12, 21, 22, 30; P-U2-01, 02, 05; PBT-U2-08. Historias: US-601, US-611.
  - **Aceptación**: un archivo de evidencia por prueba adjunto al PR, con comando, salida y resultado esperado contra el obtenido.

### Bloque G — Cierre

- [ ] **Paso 17 — Repositorio, migraciones y frontend: N/A**
  - U2 no tiene capa de repositorio propia; el esquema de `keycloak-db` lo gestiona Keycloak. El tema de login (Paso 4) es la única interfaz de usuario de U2; la SPA es de U10.
  - **Aceptación**: `test ! -d identity-edge/migrations`.

- [ ] **Paso 18 — Cierre de la unidad**
  - Verificación final de cumplimiento.
  - **Aceptación**: `make -C identity-edge check`, que corre en orden todas las verificaciones **estáticas** de los Pasos 2–15 y termina en 0. Las de kind (Paso 16) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

| Historia | Pasos |
|---|---|
| US-601 | 2, 3, 5, 13, 16 |
| US-611 | 7, 8, 9, 13, 16 |
| US-602 (contribución) | 7 |

| Diseño | Pasos |
|---|---|
| BR-U2-01, 03..17 | 2, 3, 6, 7, 11, 13 (BR-U2-02, aprobador ≠ proponente, lo implementa U4) |
| NFR-U2-01..05 (disponibilidad) | 5, 8, 11, 16 |
| NFR-U2-10..12 (rendimiento) | 14, 16 |
| NFR-U2-20..27 (seguridad) | 2, 4, 5, 7, 8, 9, 16 |
| NFR-U2-30 (escalabilidad) | 9, 16 |
| NFR-U2-40..42 (pruebas) | 3, 7, 13 |
| P-U2-01..09 | 4, 5, 6, 7, 8, 9, 11, 13, 16 |
| INF-U2-01..08 | 2, 4, 5, 8, 9, 10, 12 |

| Propiedad | Paso |
|---|---|
| PBT-U2-01..03 | 3 |
| PBT-U2-04..06 | 7 |
| PBT-U2-07 | En U0 (PBT-U0-09 con los bordes de 900 s, plan de U0 Paso 12) |
| PBT-U2-08 | 13 (definición), 16 (ejecución) |

## 4. Cumplimiento de extensiones (plan de tareas U2)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Realm y gateway solo por PR + sync manual; pruebas con clúster ejecutadas por el operador tras aprobación (Paso 16) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-03 | Cumple | `realm-lint` rechaza `core:write-credit` (Paso 3) |
| AUTONOMIA-05 | Cumple | Access log y eventos sin datos de solicitantes (Pasos 2, 7); único egress F73 |
| SECURITY-01/02/04/07/08/09/11/12/13/14/15 | Cumple | Pasos 2–11 y 16 |
| RESILIENCY-05..10, 14, 15 | Cumple | Pasos 5, 8, 9, 11, 16 |
| PBT-01..10 | Cumple | Pasos 3, 7, 13 (PBT-U2-07 en U0) |
