# Plan de tareas (Code Generation Part 1) — U2 `identity-edge`

**Este plan es la única fuente de verdad para generar el código de U2.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`, 2026-11-02):**
> la restricción se levantó para U2. Code Generation Part 2 se ejecuta por tareas del loop
> (`tareas/U02-*`); cada casilla se marca cuando su PR se fusiona.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U2 `identity-edge`: identidad (Keycloak) y borde (Envoy Gateway) |
| Historias (dueña) | US-601 (autenticación con roles y MFA), US-611 (endurecimiento del gateway y de la SPA) |
| Contribuye a | US-602 (primera capa de autorización en el gateway) |
| Ubicación | `vectra-risk/identity-edge/` (monorepo) y entradas en `vectra-risk-gitops/components.yaml`, dentro del monorepo (revisión de consistencia entre unidades, 2026-11-01) |
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
|-- jobs/                          # realm-drift, signing-key-age
|-- observability/                 # PrometheusRule, ServiceMonitor, tests de reglas
|-- runbooks/
|-- tools/                         # realm_lint.py, route_gen.py, realm_diff.py
`-- tests/                         # unit/, property/, e2e/ (Playwright), load/ (k6)
```

---

## 2. Pasos

### Bloque A — Estructura

- [x] **Paso 1 — Esqueleto de `identity-edge/`** (U02-T01 y U02-T02)
  - Directorios de §1; `pyproject.toml` como miembro del workspace `uv` de U0; `Makefile` con el objetivo `check`; perfiles de Hypothesis importados de `contracts/tests/conftest.py`.
  - **Aceptación**: `uv sync --frozen && make -C identity-edge check` termina en 0 sobre el esqueleto.

### Bloque B — Keycloak

- [x] **Paso 2 — Realm como código** (U02-T04; `group-role-map.yaml` y las sesiones persistentes quedan fuera por las decisiones D1 y D6)
  - `realm.{env}.yaml`:
    - los 4 roles de negocio y el mapeo de ACR (`pwd` = 1, `mfa` = 2);
    - el flujo de login con OTP **condicional por rol** (obligatorio para `ingeniero_riesgo`, `cro` y `cumplimiento`) y TOTP como *required action*;
    - WebAuthn opcional;
    - fuerza bruta (BR-U2-05), vidas de tokens y sesiones con rotación de refresh (BR-U2-06) y política de contraseñas (NFR-U2-24); las sesiones persistentes son opción del servidor y pasan a los Pasos 4 y 5 (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04);
    - eventos de login y de administración sin username ni email (BR-U2-16).
  - Clientes de domain-entities §2:
    - `vectra-console` y `promotion-tool` (PKCE S256, redirect URIs exactas; `vectra-console` con la de login y `/stepup-callback`, U10 BR-U10-06, revisión del FD de U10, 2026-10-10);
    - rol técnico `operacion` y el mapper de Grafana a roles y equipos (`cro`, `cumplimiento`, `operacion`; domain-entities §1.1 y §2.1); `realm-lint` rechaza `operacion` junto a un rol de negocio; usuarios `operacion-1` y `operacion-2` en kind y staging (segunda revisión del Infrastructure Design de U10, 2026-10-10);
    - `grafana` y los 10 de servicio con `private_key_jwt` (incluidos `case-worker`, agregado el 2026-10-08 por U8 INF-U8-01, y `bias-monitoring-job`, revisión del FD de U9, 2026-10-08); solo `bias-monitoring-job` tiene `governance:freeze`;
    - usuarios sintéticos de domain-entities §3 (`analista-1` y `-2`, `ingeniero-1` y `-2`, `cro-1` y `-2`, `cumplimiento-1` y `-2`), un rol cada uno, con contraseña y TOTP desde ESO, en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si `realm.prod.yaml` tiene algún usuario local distinto de `break-glass`, con un caso de prueba que agrega `cro-1` al realm de producción (revisión del Infrastructure Design de U10, 2026-10-10);
    - `verification-reader` (`private_key_jwt`) con **solo** `registry:read:metrics` y `registry:read:monitoring`, únicamente en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si aparece en `realm.prod.yaml` o con otro scope (Infrastructure Design de U12, 2026-10-10);
    - `product-metrics` (`private_key_jwt`) con **solo** `registry:read:metrics`; `realm-lint` falla si tiene otro scope (NFR-U11-20; NFR Requirements de U11, 2026-10-10);
    - `channel-simulator` (`private_key_jwt`, `intake:submit`, audiencia `case-service`) solo en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si aparece en `realm.prod.yaml` (precisado el 2026-10-06, revisión del FD de U8);
    - `case-service` con `core:read-credit` y la audiencia `core-banking-mock` solo en `realm.kind.yaml` y `realm.staging.yaml`; `realm-lint` falla si aparecen en `realm.prod.yaml`, y una prueba sobre el realm de producción comprueba que `case-service` no obtiene un token con ese scope ni con esa audiencia (precisado el 2026-10-08 por U8 INF-U8-02, core deshabilitado en producción);
    - clientes de administración de INF-U2-05a: `keycloak-config-cli` (cuenta de servicio con `realm-admin`) y `keycloak-reader` (cuenta de servicio con solo `view-realm`), ambos con `private_key_jwt` (enmienda del 2026-11-02, decisión del usuario tras la ronda 3 de U02-T03); `keycloak-reader` pasa a `view-realm`, `view-clients` y `view-users` en el Paso 6 (enmienda del 2026-11-03, decisión R1 del usuario al preparar U02-T08, INF-U2-05a);
    - mapper de audiencias y mapper `roles`;
    - access token sin `preferred_username`, `email` ni `name`.
  - kind y staging: ≥ 2 usuarios sintéticos por rol. prod: federación LDAPS `READ_ONLY` (INF-U2-07) y el usuario `break-glass`. `group-role-map.yaml` y los mappers de grupo LDAP a rol pasan a una tarea propia, que se despacha cuando el banco dé los nombres de los grupos; hasta entonces, en prod los usuarios LDAP no reciben rol (enmienda del 2026-11-02, decisión del usuario tras la ronda 1 de U02-T04).
  - Diseño: BR-U2-01, 03..07, 09, 12, 15, 16; NFR-U2-24; INF-U2-07. Historia: US-601.
  - **Aceptación**: `uv run python identity-edge/tools/realm_lint.py identity-edge/keycloak/realm/realm.*.yaml` termina en 0 (Paso 3).

- [x] **Paso 3 — `realm-lint` y sus pruebas** (U02-T03)
  - El validador verifica:
    - separación de funciones (BR-U2-01) y mapeo de grupos LDAP (BR-U2-15);
    - scopes solo del catálogo de U0 y **ningún cliente con `core:write-credit`**;
    - `governance:freeze` **solo** en `bias-monitoring-job` (revisión del FD de U9, 2026-10-08);
    - en `realm.prod.yaml`: ni `channel-simulator`, ni `case-service` con `core:read-credit` o la audiencia `core-banking-mock` (U8 INF-U8-02; precisado el 2026-10-08);
    - clientes de servicio sin `client_secret` y sin redirect URIs con comodines;
    - claims prohibidos en el access token;
    - parámetros de §6 de domain-entities y política de contraseñas;
    - (pendientes posteriores al cierre, 2026-10-10) `verification-reader` y los usuarios sintéticos solo en kind y staging; `product-metrics` y `verification-reader` con exactamente sus scopes; el rol técnico `operacion` con MFA obligatorio y nunca junto a un rol de negocio.
  - **Casos nombrados nuevos** de `tests/unit/test_realm_lint.py` (pendientes posteriores al cierre, 2026-10-10):
    - `verification-reader` en `realm.prod.yaml` → error; con un scope distinto de `registry:read:metrics` y `registry:read:monitoring` (por ejemplo `registry:append:case`) → error; en `realm.kind.yaml` con sus dos scopes → válido;
    - `product-metrics` con un scope además de `registry:read:metrics` → error; con solo ese scope → válido;
    - un usuario con `operacion` sin la acción requerida de TOTP (MFA no obligatorio) → error; `operacion` junto a `cro` → error; `operacion-1` con TOTP obligatorio → válido.
  - Propiedades PBT-U2-01, 02 y 03, con generadores en `tests/strategies/`.
  - Diseño: BR-U2-01, 09, 15; NFR-U2-40; AUTONOMIA-03. Historia: US-601 (su verificación pide la prueba del realm exportado: MFA por rol y fuerza bruta).
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_realm_*.py identity-edge/tests/unit/test_realm_lint.py`, con casos nombrados: un usuario con dos roles → error; un cliente con `core:write-credit` → error; un cliente distinto de `bias-monitoring-job` con `governance:freeze` → error; `case-service` con `core:read-credit` en `realm.prod.yaml` → error; el mismo cliente en `realm.staging.yaml` → aceptado.

- [x] **Paso 4 — Tema `vectra` e imagen de Keycloak** (U02-T06)
  - Tema hijo de `keycloak.v2` con `messages_es.properties`, logo y colores; sin JavaScript propio ni recursos de otro origen.
  - `Dockerfile`: imagen oficial 26.x pinneada por digest + tema + `kc.sh build` (`db=postgres`, `health-enabled`, `metrics-enabled`, `cache=ispn`).
  - Diseño: BR-U2-13 (CSP estricta en `/auth/**`, posible porque el tema no tiene JavaScript propio); P-U2-08; INF-U2-08; NFR-U2-25.
  - **Aceptación**: `hadolint identity-edge/keycloak/Dockerfile`; `uv run pytest identity-edge/tests/unit/test_theme.py` (ningún archivo del tema referencia `http(s)://` externos ni `<script>` propio; todas las claves de `messages_es` existen). La construcción, el escaneo y la firma los hace `supply-chain.yml` de U1.

- [x] **Paso 5 — Despliegue de Keycloak y `keycloak-config-cli`** (U02-T07; el Job de `keycloak-config-cli` queda en su tarea propia, ver la enmienda)
  - Values de `keycloakx`:
    - 2 réplicas con HPA de 2 a 4, spread por zona y PDB;
    - `cache-stack` con `jdbc-ping`;
    - `hostname` y `hostname-admin`, `proxy-headers=xforwarded`;
    - puerto de gestión 9000;
    - recursos de INF-U2-06 y prioridad `vectra-high`;
    - Secrets por `ExternalSecret`, incluida la credencial de administración de INF-U2-05a (seguimiento de la quinta revisión de coherencia, 2026-10-31); la contraseña de la base `keycloak` es `pg-role-keycloak`, que U1 entrega en `vectra-identity` (revisión de consistencia entre unidades, 2026-11-01);
    - `Certificate` `keycloak-tls` para 8443 y `BackendTLSPolicy` de F05 con el certificado de la CA (INF-U2-05b; quinta revisión de coherencia entre unidades, 2026-10-31).
  - `keycloak-config-cli` como Job hook del sync.
  - **Enmienda del 2026-11-03 (decisión Q1 del usuario al preparar U02-T07):** el Job de `keycloak-config-cli` y el criterio «hook de sync presente» salen de este paso a una tarea propia, bloqueada hasta que exista un release de `keycloak-config-cli` con aserciones de cliente y el firmante esté diseñado (INF-U2-05a). El hook será `PostSync`. El resto del paso no cambia.
  - Diseño: NFR-U2-01, 02, 23, 26; P-U2-04; INF-U2-01, 05, 06. Historia: US-601.
  - **Aceptación**: `helm template` + `conftest test identity-edge/keycloak/` (réplicas, HPA, spread, PDB, `start --optimized`, `hostname-admin` interno, sin Secret plano, hook de sync presente, `keycloak-tls` y `BackendTLSPolicy` presentes).

- [x] **Paso 6 — `realm-drift` y `signing-key-age`** (U02-T08)
  - CronJob diario que exporta el realm, lo normaliza (sin secretos, IDs internos ni timestamps) y lo compara con Git; empuja `vectra_realm_drift` al Pushgateway (F112, `PUT /metrics/job/realm-drift`; revisión de consistencia entre unidades, 2026-11-01), de donde sale `RealmDrift` (cuarta revisión de coherencia entre unidades, 2026-10-31).
  - CronJob horario `signing-key-age`: lee por F94 la llave de firma activa y empuja su antigüedad al Pushgateway (F112, `PUT /metrics/job/signing-key-age`; revisión de consistencia entre unidades, 2026-11-01) para `SigningKeyAgeHigh`. Sin Deployment ni scrape (seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - **Enmienda del 2026-11-03 (decisiones R1–R4 del usuario al preparar U02-T08):** `keycloak-reader` necesita además `view-clients` y `view-users` para leer clientes, client scopes y usuarios, así que el paso amplía sus roles en los tres realms y la regla de `realm-lint` (INF-U2-05a). La comparación es una proyección sobre Git, la métrica de `signing-key-age` es `vectra_signing_key_created_timestamp_seconds`, y la imagen `identity-jobs` y el ConfigMap del realm están en INF-U2-09.
  - Diseño: BR-U2-12; P-U2-05; INF-U2-05a, 06, 09.
  - **Aceptación**: `uv run pytest identity-edge/tests/unit/test_realm_diff.py` y una propiedad: `normalize(normalize(x)) == normalize(x)`, y dos exportaciones que solo difieren en secretos o timestamps no generan diferencias.

### Bloque C — Gateway

- [x] **Paso 7 — `routes.yaml` y `route-gen`** (U02-T09)
  - `routes.yaml` con F01–F09 (F09 con `enabled: false`) según domain-entities §4.
  - `route-gen` genera:
    - **HTTPRoute** cerradas, con 404 genérico para el resto (incluido `/auth/admin/**` y el realm `master`);
    - **SecurityPolicy**: JWT con JWKS por la URL interna, refresco cada 5 min, claims requeridos por ruta y copia de `sub`/`azp` a cabeceras internas;
    - **BackendTrafficPolicy**: descriptores de rate limit, timeouts, reintentos solo idempotentes y outlier detection, que en `/api/console/**` cuenta solo errores de conexión (seguimiento de la cuarta revisión de coherencia, 2026-10-31);
    - **ClientTrafficPolicy**: tamaño máximo por ruta y confianza en `X-Forwarded-For` de 1 salto o PROXY protocol;
    - perfiles de cabeceras, con `Cross-Origin-Opener-Policy: same-origin` en todos (revisión del Infrastructure Design de U10, 2026-10-10);
    - afinidad por cookie `vectra-spa-route` en la ruta `/` (BackendTrafficPolicy con `consistentHash` de tipo `Cookie`; revisión del Infrastructure Design de U10, 2026-10-10);
    - respuestas de error `Problem`;
    - eliminación de `server`, `x-envoy-*` y de las cabeceras internas entrantes y salientes.
  - Propiedades PBT-U2-04, 05 y 06.
  - **Enmienda del 2026-11-03 (decisiones V1–V10 del usuario al preparar U02-T09):** `/` es un prefijo hacia la SPA, y `/api/` y `/auth/` son prefijos cerrados con 404 `Problem` para el resto (V10, BR-U2-10). Los límites de `channel` y `channel-simulator` quedan en 10/s y 30/s, sin ráfaga (V2). El tamaño máximo por ruta va en la `BackendTrafficPolicy` (`requestBuffer`), porque la `ClientTrafficPolicy` no aplica a una ruta (V4, INF-U2-10). La lista de endpoints de `/auth/**` y sus dos contadores (V1), los límites sin ráfaga (V2), la reescritura de `/api/intake` y `/api/promotion` (V3), la cookie de sesión (V6) y la credencial de F09 (V7) están en domain-entities §4. `Retry-After` está en BR-U2-08 (V5). El `Gateway` `api-gateway`, los destinos, los `ReferenceGrant` y `kubeconform` están en INF-U2-10 (V8, V9).
  - Diseño: BR-U2-08, 10, 11, 13, 14; P-U2-02, 03, 06, 07; NFR-U2-20, 23, 40, 41; INF-U2-01, 10. Historias: US-611, US-602.
  - **Aceptación**:
    - `uv run python identity-edge/tools/route_gen.py --check` (los manifiestos versionados coinciden con los generados);
    - `kubeconform` con los CRDs de Gateway API y Envoy Gateway;
    - `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_routes_*.py`;
    - `conftest`: ningún reintento en `POST`/`PUT`/`PATCH`; toda ruta autenticada tiene SecurityPolicy;
    - `/api/intake/**`: el JWT de `channel-simulator` pasa en kind y staging y se rechaza (403) con los values de producción; descriptores separados por `azp` (10/20 para `channel`, 30/60 para `channel-simulator`), y el de `channel-simulator` no existe en producción (precisado el 2026-10-06, revisión del FD de U8).

- [x] **Paso 8 — Envoy Gateway, `Gateway` y verificación de la versión pinneada** (U02-T10)
  - Values del controlador (`envoy-gateway-system`, 2 réplicas; `deploy.type: GatewayNamespace` ya está en `platform/operators/envoy-gateway.yaml`); `EnvoyProxy` con la identidad que usa `flows.yaml` (`provider.kubernetes.envoyServiceAccount.name: api-gateway`, `envoyDeployment.pod.labels: {app.kubernetes.io/name: api-gateway}`, `envoyDeployment.container.image` espejada en un registro permitido, `envoyDeployment.replicas ≥ 2`, `envoyPDB`, `securityContext` y `priorityClassName` para Kyverno; campos comprobados en el CRD de v1.9.3, no en un clúster (revisión de consistencia entre unidades, 2026-11-01)); (data plane en `vectra-edge`, HPA de 2 a 6, spread, PDB, Service `LoadBalancer` con `externalTrafficPolicy: Local` o PROXY protocol); `GatewayClass`, `Gateway` (HTTPS 443) y `Certificate` con el `ClusterIssuer` de cada entorno; binding K14.
  - **Verificación de la versión pinneada.** Se registra en `identity-edge/docs/adr-envoy-gateway.md` y en `audit.md`:
    1. si se puede desplegar el data plane en el namespace del `Gateway` (INF-U2-02); si no, el data plane va en `envoy-gateway-system` y se ajustan `flows.yaml` y las NetworkPolicies;
    2. cuál de las tres alternativas de P-U2-01 se usa para el modo de fallo por ruta.
  - **Enmienda del 2026-11-04 (decisiones W1–W7 del usuario al preparar U02-T10):**
    - el servicio de rate limit es el `envoy-ratelimit` de Envoy Gateway; los values del controlador no llevan `rateLimit`, que se diseña con el Paso 9 (W1, INF-U2-03);
    - Service con `externalTrafficPolicy: Local`, y la `ClientTrafficPolicy` de `route-gen` deja de confiar en `X-Forwarded-For` (W2, NFR-U2-23);
    - modo de fallo por la alternativa 2 de P-U2-01, con `auth-rate-limits` y una `EnvoyPatchPolicy` (W3);
    - imagen de Envoy espejada con el digest real (W4);
    - HPA con objetivo del 70 % y `minAvailable: 1` (W5);
    - access log de P-U2-07 y tracing al 100 % en el `EnvoyProxy` (W6);
    - `egctl` v1.9.3 con su sha256 en las herramientas de U1 (W7);
    - el pod no lleva `pod.labels: {app.kubernetes.io/name: api-gateway}`: rompería el selector del Deployment en v1.9.3; la identidad se selecciona por `gateway.envoyproxy.io/owning-gateway-name` (decisión Z1 del usuario en la ronda 2 de U02-T10, INF-U2-02).

    Todo está en INF-U2-02, 03 y 10, P-U2-01 y NFR-U2-23.
  - Diseño: NFR-U2-03, 04, 21, 22, 23; P-U2-01, 07; INF-U2-01, 02, 03, 10. Historia: US-611 (el gateway sirve las cabeceras y los errores genéricos).
  - **Aceptación**:
    - `egctl x translate --from gateway-api --to xds -f identity-edge/gateway/generated/` (traducción offline, sin clúster) y una prueba que inspecciona el xDS: el filtro de rate limit de la ruta `/auth/**` tiene `failure_mode_deny: true` y el de las demás no;
    - `test -s identity-edge/docs/adr-envoy-gateway.md`.

- [x] **Paso 9 — Servicio de rate limit y Valkey** (U02-T11)
  - `envoyproxy/ratelimit` (HPA de 2 a 4, quinta revisión de coherencia entre unidades, 2026-10-31; gRPC en 8083, métricas en 8081) con la configuración de descriptores generada por `route-gen`.
  - Chart propio de Valkey 8: 2 nodos en zonas distintas, primaria preferida en la zona A, 3 Sentinel, sin persistencia, PDB, exportador como sidecar, ACL `ratelimit`, de replicación y de Sentinel desde ESO (seguimiento de la quinta revisión de coherencia, 2026-10-31), usuario `default` deshabilitado, `maxmemory 128mb`, `volatile-ttl`, prioridad `vectra-high`.
  - **Nota del 2026-11-04 (decisión W1 del usuario al preparar U02-T10):** el servicio de rate limit es el `envoy-ratelimit` que despliega Envoy Gateway, no un `envoyproxy/ratelimit` propio en el 8083 con configuración de `route-gen` (INF-U2-03). Este paso se rediseña al prepararlo.
  - **Rediseño del 2026-11-04 (decisiones R1–R4 del usuario al preparar U02-T11; INF-U2-03, INF-U2-04, NFR-U2-27, component-dependency §0 y §2.8):**
    - `envoy-ratelimit` de Envoy Gateway v1.9.3, en `envoy-gateway-system`, configurado en `platform/operators/envoy-gateway.yaml` (`rateLimit`, `rateLimitDeployment`, `rateLimitHpa` de 2 a 4 al 70 %, `rateLimitPDB` `minAvailable: 1`). Los puertos los fija v1.9.3: gRPC 8081, health 8080 y métricas 19001;
    - conexión por Sentinel con `REDIS_TYPE=SENTINEL`, y `REDIS_AUTH` y `REDIS_SENTINEL_AUTH` desde un `ExternalSecret` en `envoy-gateway-system`; K11 se amplía a ese namespace (R1);
    - el endurecimiento de `rateLimitDeployment` lo exige conftest sobre el render, porque Kyverno no alcanza `envoy-gateway-system`. Imagen `ratelimit:5ae0682e` espejada con digest (R2);
    - chart `identity-edge/charts/valkey`: `valkey-a` y `valkey-b` por zona con `replica-priority`, `sentinel-a` (1) y `sentinel-b` (2) (R3);
    - ACL armadas por la plantilla de ESO, con el usuario `exporter` y la ACL propia de Sentinel (R4);
    - Valkey 8.1.11-alpine y redis_exporter v1.95.0-alpine con digest (R2).
  - Diseño: NFR-U2-20, 27, 30; P-U2-04, 06; INF-U2-03, 04. Historia: US-611 (exceso de solicitudes → 429).
  - **Aceptación** (enmendada el 2026-11-04 con R1–R4; la original pedía los puertos 8083/8081 y descriptores generados por `route-gen`):
    - `helm template` de `identity-edge/charts/valkey` y del chart `gateway-helm` v1.9.3 con los values, más `conftest test` con las políticas de `identity-edge/ratelimit/policy/` e `identity-edge/charts/valkey/policy/`: puertos 8081, 8080 y 19001 de `envoy-ratelimit`, Sentinel por env, sin RDB ni AOF, ACL presente, `default` deshabilitado y reparto por zona;
    - `uv run pytest identity-edge/tests/unit/test_ratelimit_config.py`: los descriptores del IR de `egctl x translate --to ir` coinciden con `routes.yaml`.

### Bloque D — Plataforma: red, observabilidad y GitOps

- [x] **Paso 10 — Flujos y RBAC** (U02-T12)
  - **Nota del 2026-11-04 (decisión Z1 del usuario en U02-T10):** la identidad `api-gateway` de `flows.yaml` pasa a seleccionar el data plane por `gateway.envoyproxy.io/owning-gateway-name: api-gateway` (INF-U2-02).
  - Verificar en `platform/network/flows.yaml` de U1, donde ya están: F05, F43, F50, F73 (solo prod), F90–F95, F112, F117 y el scrape de Keycloak (9000). El de `vectra-edge` es F60, solo al 8081: Envoy, rate limit y el exportador de Valkey se publican en ese puerto o se agrega su puerto por PR (revisión de consistencia entre unidades, 2026-11-01). Agregar el RBAC K14. `realm-drift` no tiene binding: usa F94, no la API de Kubernetes (cuarta revisión de coherencia entre unidades, 2026-10-31).
  - **Nota del 2026-11-05 (decisiones T1–T4 del usuario al preparar U02-T12; INF-U2-04 «Flujos y sondas», component-dependency F60, F61, F91 y F92):** el servicio de rate limit es `envoy-ratelimit` en `envoy-gateway-system` (F90 al 8081), fuera de la malla y autorizado por `NetworkAuthentication` (T1); F92 suma Valkey → Sentinel 26379 (T2); F60 suma los 19001 de Envoy y `envoy-ratelimit` y el 9121 del exportador (T3); las sondas de Valkey y Sentinel pasan a `exec` (T4, toca el chart del Paso 9). K14 ya está en `flows.yaml` desde U02-T10 (X2): se verifica, no se agrega.
  - Diseño: INF-U2-02..04; P-U1-01.
  - **Aceptación**: `uv run python platform/network/generate.py --check` y `uv run pytest platform/network/tests` (los IDs F90–F95 y K14 de `component-dependency.md` están en `flows.yaml`).

- [x] **Paso 11 — Alertas y runbooks** (U02-T13)
  - `PrometheusRule` con las alertas de P-U2-09, incluida `LdapUnavailable`. Runbooks: `keycloak-down`, `rate-limit-backend-down`, `auth-denied-burst`, `break-glass-login`, `realm-drift`, `role-conflict`, `signing-key-rotation`, `gateway-high-latency`, `ldap-unavailable`.
  - **Nota del 2026-11-05 (decisiones B1–B9 del usuario al preparar U02-T13; P-U2-09 «Fuentes, umbrales y despliegue»):**
    - expresiones, umbrales y `for` de las 9 alertas, más `RealmDriftStale` y `SigningKeyAgeStale` (B3, B8);
    - métricas de eventos de usuario en la imagen de Keycloak (B1);
    - `RoleConflict` y `LdapUnavailable` sobre métricas de contrato (B2);
    - los `ServiceMonitor`/`PodMonitor` de U2 en `observability/` (B5);
    - el CR en `vectra-observability` con el patrón de U1 (B6);
    - el runbook operativo de la vuelta de Valkey a la zona A (B7).
  - Diseño: P-U2-09; BR-U2-17; P-U2-05; NFR-U2-05 (`KeycloakDown`).
  - **Aceptación**: `promtool test rules identity-edge/observability/rules/tests/*.yaml` y `uv run python platform/tests/test_runbooks.py --root identity-edge` (`severity` válida y `runbook_url` existente).

- [ ] **Paso 12 — Applications de GitOps**
  - Entradas en `vectra-risk-gitops/components.yaml` con sus waves: Valkey (2), Keycloak + `keycloak-config-cli` y gateway + rate limit (3); los CRDs de Gateway API y el controlador (0) ya están en la entrada `envoy-gateway` de U1. `generate.py` escribe las Applications. Values por entorno en `vectra-risk-gitops/values/<env>/<componente>.yaml`: hostnames (INF-U2-01), issuer y LDAP (prod) (revisión de consistencia entre unidades, 2026-11-01).
  - **Nota del 2026-11-05 (decisión B6 del usuario al preparar U02-T13):** el paso también suma las entradas `identity-rules` e `identity-monitors` en wave 4, con las reglas y los monitores que deja el Paso 11 en `identity-edge/observability/`.
  - **Nota del 2026-11-07 (decisiones M1–M3 del usuario al preparar U02-T18):**
    - **M1**: cada Application de U2 apunta al directorio que ya renderiza y verifica `make -C identity-edge check` (`charts/valkey/rendered/{env}`, `keycloak/rendered/{env}`, `gateway/generated/{env}`, `jobs/rendered/{env}`), como la Application `network` de U1. No se crea `vectra-risk-gitops/values/<env>/` para U2: los hostnames (INF-U2-01), el issuer y el LDAP (prod) siguen en los values de `identity-edge/`, que se renderizan.
    - **M2**: `keycloak-config-cli` queda fuera de este paso. Su Job está bloqueado (INF-U2-05a); su hook `PostSync` entra en la Application `keycloak` con su tarea propia.
    - **M3**: los CronJobs `realm-drift` y `signing-key-age` y su ConfigMap van en una Application `identity-jobs` en wave 4, después del Pushgateway.
  - Diseño: P-U1-12; INF-U2-01.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`, `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync` sobre las Applications nuevas (revisión de consistencia entre unidades, 2026-11-01).

### Bloque E — Pruebas de extremo a extremo y de carga (definición)

- [x] **Paso 13 — Especificación de las pruebas de extremo a extremo** (U02-T14)
  - Playwright + `httpx` + `pyotp` + `axe-core`:
    - aprobador sin TOTP → no obtiene token;
    - step-up sin SPA: flujo OIDC con `acr_values=mfa` y TOTP hasta el token con `acr = mfa`; el diálogo en la consola se prueba en U10, que se construye después (seguimiento de la quinta revisión de coherencia, 2026-10-31). Comportamiento que U10 debe cubrir, step-up en ventana emergente (revisión del Infrastructure Design de U10, 2026-10-10): firma con `auth_time` > 900 s → `mfa_required` → diálogo → clic → ventana con `acr_values=mfa` → TOTP → `/stepup-callback` envía `code` y `state` por `postMessage` → la ventana principal reintenta con el mismo cuerpo → éxito, sin recarga; un `postMessage` de otro origen → ignorado; la ventana conserva `window.opener` con `Cross-Origin-Opener-Policy: same-origin`;
    - 5 fallos → bloqueo, con el evento con `userId` y sin `username`;
    - refresh reusado → sesión revocada;
    - cabeceras (CSP, HSTS, `nosniff`, `DENY`, `Referrer-Policy`); la CSP de `spa` y `api` incluye `require-trusted-types-for 'script'` y `trusted-types 'none'` (NFR Requirements de U10, 2026-10-10, Q7);
    - 429 con `Retry-After`; cuerpo mayor que el límite → 413 `payload_too_large` (seguimiento de la quinta revisión de coherencia, 2026-10-31); `/auth/admin` → 404;
    - token de otro servicio → 401;
    - `X-Forwarded-For` falso no cambia la IP registrada;
    - cabecera interna `x-vectra-sub` inyectada → sin efecto;
    - backend de eco: `Idempotency-Key` (en `/api/intake/**` y `/api/console/**`) y `X-Test-Scenario` (en `/api/intake/**`) llegan intactas, y ninguna `x-vectra-*` entrante llega (P-U2-06; precisado el 2026-10-06, revisión del FD de U8);
    - accesibilidad del login.
  - PBT-U2-08: modelo de estados de la fuerza bruta contra el Keycloak de kind.
  - **Nota del 2026-11-05 (decisiones H1–H9 del usuario al preparar U02-T14):**
    - **H1**: backend de eco solo para kind, en `tests/e2e/echo/`. Lleva los nombres, la SA y las etiquetas reales de `console-spa`, `console-bff`, `case-service` y `governance-service`, y se valida en estático. Lo aplica el operador en el Paso 16.
    - **H2**: «token de otro servicio» espera **403** en el gateway, que autoriza por `azp` y scope sin `audiences`. El 401 por audiencia es de U8.
    - **H3**: `make check` no ejecuta las e2e (`--ignore`). `collect-e2e` sí entra en `check`, y el target `e2e` es para el Paso 16.
    - **H4**: dependencias `playwright`, `pytest-playwright`, `pyotp` y `axe-playwright-python`, con `httpx` explícito y `uv lock` con red.
    - **H5**: el aprobador sin TOTP lo crea y lo borra una fixture por la Admin API.
    - **H6**: el evento del bloqueo y la IP registrada se observan en Loki (LogQL); la IP, también por el contador de `/auth`.
    - **H7**: los casos de PBT-10 sobre `governance:freeze` y `core:read-credit` quedan fuera y pasan a `CANDIDATAS.md`.
    - **H8**: PBT-U2-08 usa el perfil de Hypothesis `kind-e2e`, con un usuario efímero por ejemplo.
    - **H9**: el tipo de evento del bloqueo se fija contra el código de Keycloak 26.8.1.
  - Diseño: PBT-10; NFR-U2-42; BR-U2-03..08, 10, 13, 16; P-U2-06, 08. Historias: US-601, US-611.
  - **Aceptación** (estática): `uv run ruff check identity-edge/tests/e2e` y `uv run pytest identity-edge/tests/e2e --collect-only` lista todos los casos nombrados. La ejecución es del Paso 16.

- [ ] **Paso 14 — Especificación de la prueba de carga**
  - Script k6: 200 usuarios concurrentes con login y token, 10 identidades de servicio renovando cada 5 min (incluidas `case-worker` y `bias-monitoring-job`), ráfagas contra la consola; umbrales de NFR-U2-10..12 como `thresholds`.
  - **Nota del 2026-11-05 (decisiones J1–J7 del usuario al preparar U02-T15):**
    - **J1**: 200 usuarios `load-001..200` solo en kind, con un rol al que BR-U2-03 no exige MFA. Los crea un script de este paso por la Admin API; lo ejecuta el operador en el Paso 16 y no va al realm versionado.
    - **J2**: k6 como binario pinneado con SHA-256 en `platform/install-tools.sh` y `tools.env`. Es una excepción explícita a la decisión de U12 de usar contenedor, porque `check` corre sin Docker.
    - **J3**: NFR-U2-11 y 12 como en su enmienda de NFR Requirements.
    - **J4**: las ráfagas contra la consola van al eco del Paso 13 y esperan 429 con `Retry-After: 1` por encima de 20/s por usuario.
    - **J5**: los logins se escalonan por debajo de 10/s, por el límite de 600/min por IP de `/auth/**`, y un 429 cuenta como fallo.
    - **J6**: las llaves privadas de los clientes se leen de `K6_CLIENT_KEYS_DIR`, que el operador llena desde Vault.
    - **J7**: perfil de 2 min de subida y 15 min sostenidos, con `http_req_failed` < 1 %.
    - Las 10 identidades de servicio son los 14 clientes con service account de `realm.kind.yaml`, menos `keycloak-config-cli`, `keycloak-reader`, `verification-reader` y `channel-simulator`.
    - Depende del Paso 13, por el eco.
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
| INF-U2-10 | 7 |

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

## Reglas de admisión que este plan debe cumplir (revisión de consistencia entre unidades, 2026-11-01)

Cada chart de esta unidad pasa `make -C platform check-chart CHART=<ruta>` en el PR, con los mismos values que usa Argo CD en cada entorno:

- Imágenes por digest, de un registro que admita `restrict-registries`; las de terceros se espejan.
- `runAsNonRoot`, `readOnlyRootFilesystem` (con `emptyDir` para lo que escriba en disco), sin `privileged` ni `hostPath`, con recursos y `priorityClassName`.
- `vectra.io/criticality` en cada `Deployment` y `StatefulSet` que el chart declare.
- En `vectra-app`, `vectra-edge`, `vectra-identity`, `vectra-serving` y `vectra-mock`: 2 réplicas o más, `topologySpreadConstraints` por zona, PDB por `app.kubernetes.io/name`, y HPA o `vectra.io/hpa-exempt`.

Detalle en `aidlc-docs/construction/shared-infrastructure.md` §2.
