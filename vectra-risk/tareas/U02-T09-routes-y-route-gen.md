# U02-T09 — `routes.yaml` y `route-gen`

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-611, US-602 (contribución)
**Depende de:** U02-T07 (Service `keycloak` y `BackendTLSPolicy` de F05), en `main`

Paso 7 del plan de U2. Al preparar la tarea (2026-11-03), el orquestador comprobó el diseño contra el código de Envoy Gateway v1.9.3, la versión pinneada en `vectra-risk-gitops/components.yaml`. El usuario decidió V1–V10:
- V1: endpoints de `/auth/**` y sus dos contadores;
- V2: límites sin ráfaga;
- V3: reescritura de prefijos;
- V4: tamaño por ruta en la `BackendTrafficPolicy`;
- V5: `Retry-After`;
- V6: TTL de la cookie;
- V7: credencial de F09;
- V8: `kubeconform` y CRDs;
- V9: nombre del `Gateway`;
- V10: SPA por prefijo y prefijos cerrados.

Las decisiones están en domain-entities §4, BR-U2-08, BR-U2-10 e INF-U2-10.

## Alcance

**Dentro:** todo el Paso 7 del plan. Texto del plan, sin recortes:

- [ ] **Paso 7 — `routes.yaml` y `route-gen`**
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

Precisiones del diseño enmendado que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Ubicación** (estructura de destino del plan):
  - `identity-edge/gateway/routes.yaml` es la única fuente. Los datos que cambian por entorno (hostname, `azp` de `channel-simulator`, F09) van en `identity-edge/gateway/values/<env>.yaml`.
  - El generador es `identity-edge/tools/route_gen.py` y la salida versionada va en `identity-edge/gateway/generated/<env>/`, como `keycloak/rendered/<env>/`.
  - Sin `--check`, el generador escribe. Con `--check`, compara sin escribir y termina distinto de 0 si algo difiere.
- **Hostnames** (INF-U2-01): `vectra.localtest.me` (kind), `vectra.staging.banco.internal` (staging) y `vectra.banco.internal` (prod).
- **`Gateway` y namespaces** (V9, INF-U2-10):
  - `parentRefs` a `api-gateway` en `vectra-edge`, con `sectionName: https`. Las HTTPRoute y las políticas van en `vectra-edge`.
  - Hay un `ReferenceGrant` en `vectra-app`, `vectra-identity` y `vectra-observability`. Cada uno admite solo HTTPRoute de `vectra-edge` y solo hacia los Services de ese namespace que se usan, por nombre.
  - El `Gateway`, el `GatewayClass`, el `EnvoyProxy` y el certificado no son de esta tarea (Paso 8).
- **Destinos** (INF-U2-10):
  - `/`: `console-spa:8080` (`vectra-edge`);
  - `/api/console/**`: `console-bff:8080`;
  - `/api/intake/**`: `case-service:8080`;
  - `/api/promotion/**`: `governance-service:8080`;
  - `/auth/**`: `keycloak:8443` (`vectra-identity`, con la `BackendTLSPolicy` de U02-T07);
  - `/grafana/**`: `kube-prometheus-stack-grafana:80`;
  - `/federate`: `kube-prometheus-stack-prometheus:9090` (los dos en `vectra-observability`).

  `vectra-app` es el namespace de `console-bff`, `case-service` y `governance-service`.
- **Rutas** (domain-entities §4, V1, V3 y V10; BR-U2-10):
  - `/` por prefijo va a la SPA, y lo que no es `/api/`, `/auth/`, `/grafana/` ni `/federate` llega a nginx.
  - `/api/` y `/auth/` son prefijos cerrados. Solo pasan sus entradas, y todo lo demás bajo ellos da 404 `Problem` por `HTTPRouteFilter` `directResponse`. Eso incluye `/auth/admin/**`, `/auth/realms/master/**` y los demás caminos de Keycloak fuera de la lista de V1.
  - `/federate` da 404 mientras F09 está deshabilitada.
  - `/auth/**` enruta exactamente la lista de domain-entities §4 (V1):
    - exactos: `.well-known/openid-configuration`, `protocol/openid-connect/{auth,token,certs,logout}`, `protocol/openid-connect/login-status-iframe.html` y `.../login-status-iframe.html/init`;
    - por prefijo: `protocol/openid-connect/3p-cookies/`, `login-actions/` y `account/`, todos bajo `/auth/realms/vectra/`;
    - y `/auth/resources/` por prefijo.
  - `/api/intake/**`: solo `POST /api/intake/v1/intake/applications`, reescrito a `/v1/intake/applications` (V3).
  - `/api/promotion/**`: solo `GET /api/promotion/v1/models` con `state=aprobado`, reescrito a `/v1/models`, y `POST /api/promotion/v1/models/{id}/activation`, reescrito a `/v1/models/{id}/activation`. El `{id}` es un segmento sin `/`.
  - `/api/console/**`, `/grafana/**`, `/auth/**` y `/federate` no se reescriben.
- **Caminos** (V10): `ClientTrafficPolicy` con `path.escapedSlashesAction: UnescapeAndRedirect` y `disableMergeSlashes: false`, fijados de forma explícita.
- **JWT** (BR-U2-11, P-U2-03, INF-U2-10, domain-entities §4):
  - un proveedor por entorno con `issuer` `https://<hostname>/auth/realms/vectra`;
  - `remoteJWKS` en `https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/protocol/openid-connect/certs`, con `backendRefs` a `keycloak:8443` y `cacheDuration: 300s`;
  - `claimToHeaders`: `sub` a `x-vectra-sub` y `azp` a `x-vectra-azp`.
  - Autorización por ruta, con `defaultAction: Deny` (403):
    - `/api/console/**`: `azp` = `vectra-console` y `roles` con al menos uno de `analista`, `ingeniero_riesgo`, `cro`, `cumplimiento`;
    - `/api/intake/**`: scope `intake:submit` y `azp` ∈ {`channel`} en prod, y {`channel`, `channel-simulator`} en kind y staging;
    - `/api/promotion/**`: `azp` = `promotion-tool`, `roles` con `ingeniero_riesgo`, scope `governance:promotion` y `acr` = `mfa`.
  - `/`, `/auth/**` y `/grafana/**` no llevan JWT.
  - `/federate` (solo si F09 está habilitada) lleva basic auth con el Secret `federate-basic-auth` (V7).
- **Rate limit** (domain-entities §4, V1, V2; P-U2-06): global, en la `BackendTrafficPolicy` de cada ruta.
  - Consola: 20/s por `x-vectra-sub`.
  - Intake: 10/s para `x-vectra-azp` = `channel` y 30/s para `channel-simulator`, en reglas separadas. La de `channel-simulator` no existe en prod.
  - Promoción: 1/s por `x-vectra-sub`.
  - `/auth/**`: 600/min por IP de origen en el contador de login (`protocol/openid-connect/auth` y `login-actions/**`) y otro de 600/min en el de token (`protocol/openid-connect/token`).
  - `/federate`: 1/s.
  - Límite global de 200/s compartido por todas las rutas, en un solo contador (`shared: true`).
  - Sin ráfagas (V2).
- **Timeouts y reintentos** (P-U2-02):
  - consola: 15 s; solo `GET`/`HEAD`, 1 reintento ante `connect-failure`, presupuesto del 20 % y sin reintento ante 503;
  - intake: 5 s y ningún reintento;
  - promoción: 10 s; solo el `GET` se reintenta, el `POST` nunca;
  - `/auth/**`: 10 s, solo `GET`/`HEAD`;
  - `/grafana/**`: 30 s, solo `GET`/`HEAD`.

  Las reglas de una ruta se separan por método para que el reintento aplique solo a las idempotentes. `POST`, `PUT` y `PATCH` nunca tienen reintento.
- **Outlier detection** (P-U2-02):
  - 5 errores 5xx consecutivos, expulsión de 30 s y como máximo el 50 % de los pods;
  - en `/api/console/**`, `splitExternalLocalOriginErrors: true` y `consecutiveLocalOriginFailures: 5`, sin expulsar por 5xx.
- **Tamaño** (V4): `requestBuffer.limit` en la `BackendTrafficPolicy` de cada ruta con tamaño en la tabla:
  - 64 KiB en consola, 32 KiB en intake, 16 KiB en promoción y 64 KiB en Grafana;
  - las filas sin tamaño («—» o «Por defecto») no llevan límite.
- **Cliente** (NFR-U2-23, P-U2-06, BR-U2-14): `ClientTrafficPolicy` sobre el `Gateway`.
  - `clientIPDetection.xForwardedFor.numTrustedHops: 1`.
  - `headers.earlyRequestHeaders.removeOnMatch` con el prefijo `x-vectra-`, que corre antes del filtro JWT.
  - `headers.lateResponseHeaders`: quita `server` y, por prefijo, `x-envoy-` y `x-vectra-`.
  - Envoy Gateway v1.9.3 fija `server_header_transformation: PASS_THROUGH` (no agrega el suyo) y `suppress_envoy_headers` salvo con `enableEnvoyHeaders`, que no se activa.
  - La regla de PROXY protocol queda para el Paso 8, que fija el Service.
- **Cabeceras internas hacia el backend** (P-U2-06): cada regla autenticada quita `x-vectra-sub` y `x-vectra-azp` con `RequestHeaderModifier`. Ese filtro corre en el router, después del rate limit.
  - `Idempotency-Key` y `X-Test-Scenario` no se tocan en ninguna regla.
- **Perfiles de cabeceras** (domain-entities §4.1, BR-U2-13): `ResponseHeaderModifier` por regla.
  - `spa` y `api`: `set` de `X-Frame-Options: DENY` y la CSP exacta de §4.1.
  - `grafana`: `set` de `X-Frame-Options: SAMEORIGIN` y `Content-Security-Policy: frame-ancestors 'self'`.
  - `auth`: se conservan las de Keycloak y se agrega (`add`) `Content-Security-Policy: frame-ancestors 'self'`.
  - Todos: `set` de HSTS, `nosniff`, `Referrer-Policy: no-referrer` y `Cross-Origin-Opener-Policy: same-origin`, con los valores exactos de §4.1.
- **Errores `Problem`** (BR-U2-08, BR-U2-14; V5):
  - Cuerpo con la forma de U0: `vectra_common.errors.to_problem` y `problem_body`, `type` `urn:vectra:problem:<code>`, el título de U0 y `content-type: application/problem+json`.
  - Códigos: 401 `unauthenticated`, 403 `forbidden`, 404 `not_found`, 413 `payload_too_large`, 429 `rate_limited` y 503 `dependency_unavailable`.
  - Se generan con `responseOverride` y `directResponse`.
  - `correlation_id` es el trace-id de `traceparent` (P-U2-07), escrito con el operador de formato de Envoy `%TRACE_ID%`. Comprueba en el código de Envoy Gateway v1.9.3 y en la versión de Envoy que trae que el cuerpo admite ese operador. Si no lo admite, detente y repórtalo.
  - El 429 lleva `Retry-After: 1` en los límites por segundo y `60` en los de `/auth/**` (V5).
  - Sin eco del contenido ni detalles de enrutamiento.
- **Afinidad** (V6): en `/`, `loadBalancer.type: ConsistentHash` con `consistentHash.type: Cookie`, nombre `vectra-spa-route`, `ttl: 0s` y atributos `Secure`, `HttpOnly`, `SameSite=Strict` y `Path=/`. Comprueba en el CRD de v1.9.3 cómo se expresan; si alguno no se puede expresar, detente y repórtalo.
- **F09** (V7): con `enabled: false` en los tres entornos, `generated/` no tiene nada de F09. Con `true`, se generan la ruta, su SecurityPolicy con `basicAuth.users` al Secret `federate-basic-auth` y un `ExternalSecret` (`ClusterSecretStore` `vectra-store`, clave `identity/federate`, propiedad `.htpasswd`). Una prueba genera con `true` sobre una copia de los values.
- **Nombres:** cada regla lleva un nombre estable (`name` de la regla), que el access log de P-U2-07 usa como `route_name`.
- **Herramientas** (V8, INF-U2-10):
  - `kubeconform` v0.8.0 en `platform/tools.env` y en `platform/install-tools.sh`, con el checksum del archivo `CHECKSUMS` del release, como hadolint;
  - `platform/Makefile check-tools` exige el binario;
  - `platform/charts.sh` también descarga los charts OCI de `components.yaml` (`helm pull oci://<repo>/<chart>`), entre ellos `gateway-helm` v1.9.3;
  - `identity-edge/tools/crd_schemas.py` convierte los CRDs de ese chart (subchart `crds`: Envoy Gateway y Gateway API v1.6.1) a esquemas JSON en `identity-edge/.tools/schemas/`, que no se versiona.

**Fuera:**
- `GatewayClass`, `Gateway`, `EnvoyProxy` (incluido el formato del access log de P-U2-07), el certificado, PROXY protocol del Service y el modo de fallo del rate limit (P-U2-01): Paso 8.
- El servicio de rate limit y Valkey: Paso 9.
- Flujos y RBAC (`flows.yaml`): Paso 10.
- Entradas de `vectra-risk-gitops/components.yaml`: Paso de integración del plan.
- Cualquier cosa contra un clúster.
- Cambios en `contracts/`, en el realm y en los charts de Keycloak y de los jobs.
- En `platform/` solo se cambia lo de las herramientas: `tools.env`, `install-tools.sh`, `charts.sh`, `check-tools` y `.gitignore` si hace falta.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 7 y estructura de destino)
- `aidlc-docs/construction/identity-edge/functional-design/domain-entities.md` (§4 y §4.1, con la enmienda V1–V7)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-08, 10, 11, 13, 14)
- `aidlc-docs/construction/identity-edge/functional-design/business-logic-model.md` (§2.4 y PBT-U2-04..06)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-02, 03, 06, 07)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-20, 23, 40, 41)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, 02, 10)
- `contracts/python/vectra_common/src/vectra_common/errors.py` y `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` (`Problem`)
- `platform/network/flows.yaml` (F01–F09, identidades)
- `identity-edge/keycloak/rendered/` (la `BackendTLSPolicy` de F05) e `identity-edge/Makefile` (modelo de los objetivos)
- `platform/tools.env`, `platform/install-tools.sh`, `platform/charts.sh`

## Criterios de aceptación

- [ ] **CA-1** — Generación determinista (PBT-U2-06) y versionada.
  ```bash
  uv run python identity-edge/tools/route_gen.py --check && HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests/property/test_routes_*.py -q
  ```
  Esperado: pasa. Las propiedades corren con el perfil `ci` y comprueban:
  - PBT-U2-06: dos ejecuciones, con las entradas de `routes.yaml` permutadas, dan manifiestos idénticos byte a byte;
  - PBT-U2-04: con paths aleatorios, prefijos de las rutas válidas y codificaciones (`%2F`, `%5C`, `..`, `//`, mayúsculas), un path se enruta a un backend si y solo si coincide con una entrada de `routes.yaml`. Todo path bajo `/auth/admin`, bajo `/auth/realms/master` o fuera de la lista de V1 bajo `/auth/` o `/api/` da 404. El modelo de coincidencia lee los manifiestos generados, no `routes.yaml`.
  - PBT-U2-05: el perfil aplicado a cada ruta es el de su fila; solo `/grafana/**` y `/auth/**` admiten `frame-ancestors 'self'`; toda ruta lleva `Cross-Origin-Opener-Policy: same-origin`.

  `--check` termina distinto de 0 sobre un `generated/` alterado.
- [ ] **CA-2** — Validación de esquema.
  ```bash
  make -C identity-edge schemas-gateway kubeconform-gateway
  ```
  Esperado: `kubeconform -strict` con los esquemas de `gateway-helm` v1.9.3 valida todos los documentos de `generated/<env>/` en los tres entornos, con 0 inválidos y 0 sin esquema (sin `-ignore-missing-schemas`). Un documento con un campo desconocido falla.
- [ ] **CA-3** — Políticas sobre lo generado, con `conftest` en `identity-edge/gateway/policy/` y objetivos `policy-gateway` en el `Makefile`:
  - ningún reintento en `POST`, `PUT` ni `PATCH`;
  - toda regla autenticada tiene SecurityPolicy con JWT y autorización `Deny` por defecto;
  - `/api/console/**` no expulsa por 5xx;
  - toda ruta tiene el perfil de su fila;
  - el conjunto exacto de documentos de cada entorno, cada uno comparado completo con los valores del diseño (lección de U02-T07): los valores que fija el diseño se leen del diseño, y los que solo fija el generador se comparan con `generated/`.

  Cada regla tiene un caso que falla sobre un documento alterado.
  ```bash
  make -C identity-edge policy-gateway && uv run pytest identity-edge/tests/unit/test_route_gen.py -q
  ```
  Esperado: pasa.
- [ ] **CA-4** — Intake por entorno (`test_route_gen.py`):
  - en kind y staging, la autorización admite `azp` `channel` y `channel-simulator`; en prod solo `channel`, así que el JWT de `channel-simulator` da 403;
  - las reglas de rate limit son 10/s para `channel` y 30/s para `channel-simulator`, separadas, y en prod la de `channel-simulator` no existe;
  - `POST /api/intake/v1/intake/applications` se reescribe a `/v1/intake/applications`, y `GET` en el mismo camino o cualquier otro camino bajo `/api/intake/` da 404.
  ```bash
  uv run pytest identity-edge/tests/unit/test_route_gen.py -q -k intake
  ```
  Esperado: pasa.
- [ ] **CA-5** — Reglas de las precisiones, cada una con un caso que pasa y uno que falla en `test_route_gen.py`:
  - la lista exacta de `/auth/**` de V1 y sus dos contadores de 600/min con `Retry-After: 60`;
  - la promoción solo con `GET` y `state=aprobado`, o con el `POST` de activación, reescrita;
  - las cabeceras internas se quitan al entrar (prefijo) y hacia el backend, e `Idempotency-Key` y `X-Test-Scenario` no aparecen en ningún filtro;
  - `server`, `x-envoy-` y `x-vectra-` se quitan de la respuesta;
  - el cuerpo de cada `Problem` valida con el modelo `Problem` de U0 si se sustituye `%TRACE_ID%`;
  - la cookie `vectra-spa-route` con TTL 0;
  - los `ReferenceGrant` admiten exactamente los Services usados;
  - F09 deshabilitada no genera nada, y habilitada genera la ruta, la basic auth y el `ExternalSecret`.
  ```bash
  uv run pytest identity-edge/tests/unit/test_route_gen.py -q
  ```
  Esperado: pasa.
- [ ] **CA-6** — Las herramientas de U1.
  ```bash
  platform/install-tools.sh && platform/charts.sh && make -C platform check-tools
  ```
  Esperado: termina en 0, `platform/.tools/bin/kubeconform` existe con el checksum comprobado y `platform/.charts/envoy-gateway/gateway-helm/` existe.
- [ ] **CA-7** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check && make -C platform check-local
  ```
  Esperado: todo pasa y termina en 0. `check` incluye `route_gen.py --check`, `kubeconform-gateway` y `policy-gateway`.

## Plan de pruebas

**Rojo primero:** escribe `test_route_gen.py` y `test_routes_*.py`, y registra en la bitácora que fallan antes de escribir `routes.yaml`, `route_gen.py` y las políticas.

## Notas

- Implementa lo que define el diseño enmendado. Si falta un dato, o si un campo de la API de Envoy Gateway v1.9.3 no permite expresar una precisión, detente y repórtalo; no lo sustituyas por otro mecanismo.
- Los campos de los CRDs se comprueban contra `api/v1alpha1/` del tag v1.9.3 y los esquemas del chart, no de memoria.
- Las listas de rutas, perfiles y claims se definen por listas exactas en el código o en `routes.yaml`. No uses expresiones regulares sobre el texto de los manifiestos.
- `identity-edge/gateway/generated/` es salida generada. Versiónala como `identity-edge/keycloak/rendered/`.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker**: el proyecto los deniega por configuración. El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. La red solo se usa para `install-tools.sh` y `charts.sh`.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
