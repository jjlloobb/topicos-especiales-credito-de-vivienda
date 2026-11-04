# U02-T10 — Envoy Gateway, `Gateway` y verificación de la versión pinneada

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-611
**Depende de:** U02-T09 (`routes.yaml`, `route-gen` y `generated/<env>/`), en `main`

Paso 8 del plan de U2. Al preparar la tarea (2026-11-04), el orquestador comprobó el diseño contra el código de Envoy Gateway v1.9.3, la versión pinneada en `vectra-risk-gitops/components.yaml`. El usuario decidió W1–W7:
- W1: servicio de rate limit;
- W2: IP real;
- W3: modo de fallo;
- W4: imagen de Envoy;
- W5: HPA y PDB;
- W6: telemetría;
- W7: `egctl`.

Las decisiones están en INF-U2-02, INF-U2-03, INF-U2-10, P-U2-01 y NFR-U2-23.

## Alcance

**Dentro:** todo el Paso 8 del plan. Texto del plan, sin recortes:

- [ ] **Paso 8 — Envoy Gateway, `Gateway` y verificación de la versión pinneada**
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
    - `egctl` v1.9.3 con su sha256 en las herramientas de U1 (W7).

    Todo está en INF-U2-02, 03 y 10, P-U2-01 y NFR-U2-23.
  - Diseño: NFR-U2-03, 04, 21, 22, 23; P-U2-01, 07; INF-U2-01, 02, 03, 10. Historia: US-611 (el gateway sirve las cabeceras y los errores genéricos).
  - **Aceptación**:
    - `egctl x translate --from gateway-api --to xds -f identity-edge/gateway/generated/` (traducción offline, sin clúster) y una prueba que inspecciona el xDS: el filtro de rate limit de la ruta `/auth/**` tiene `failure_mode_deny: true` y el de las demás no;
    - `test -s identity-edge/docs/adr-envoy-gateway.md`.

Precisiones del diseño enmendado que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Ubicación:**
  - Los values del controlador están en `platform/operators/envoy-gateway.yaml`, el archivo que ya usa `components.yaml`.
  - `GatewayClass`, `Gateway`, `Certificate`, `EnvoyProxy`, `auth-rate-limits` y la `EnvoyPatchPolicy` los genera `route-gen` en `identity-edge/gateway/generated/<env>/`, desde `routes.yaml` y `identity-edge/gateway/values/<env>.yaml`.
  - El ADR va en `identity-edge/docs/adr-envoy-gateway.md`.
- **Controlador** (INF-U2-02, INF-U2-06; P-U2-01):
  - `deployment.replicas: 2`, con la elección de líder del chart;
  - prioridad `vectra-high` (logical-components §1);
  - recursos de INF-U2-06: requests 100m / 128 MiB, limits 500m / 256 MiB;
  - `config.envoyGateway.extensionApis.enableEnvoyPatchPolicy: true` (W3);
  - sin `rateLimit` (W1).

  Comprueba los nombres de las claves en `charts/gateway-helm/values.tmpl.yaml` de v1.9.3.
- **Binding K14** (component-dependency §3): renderiza el RBAC del chart `gateway-helm` v1.9.3 y compáralo con K14, que permite leer los recursos de Gateway API y de Envoy Gateway y gestionar Deployments, Services y ConfigMaps del data plane. Lista en el ADR lo que el chart concede de más. Si concede de más, detente y repórtalo; no lo recortes por tu cuenta.
- **`GatewayClass` y `Gateway`** (V9, INF-U2-01, INF-U2-02):
  - `GatewayClass` con `parametersRef` al `EnvoyProxy`;
  - `Gateway` `api-gateway` en `vectra-edge`, con un solo listener `https` (443, protocolo HTTPS, `hostname` del entorno) y `tls.certificateRefs` al Secret del `Certificate`.
- **`Certificate`** (INF-U2-01, NFR-U2-22):
  - en `vectra-edge`, con `dnsNames` el hostname público del entorno;
  - `ClusterIssuer` `vectra-internal-ca` en kind y `banco-ca` en staging y prod, el ejemplo de INF-U2-01 hasta la integración; staging y prod nunca usan el de kind.
- **`EnvoyProxy`** (Paso 8; W2, W4, W5, W6; INF-U2-06):
  - `envoyServiceAccount.name: api-gateway`;
  - en el pod, la etiqueta `app.kubernetes.io/name: api-gateway` y `vectra.io/criticality: high`, como Keycloak;
  - imagen `kind-registry:5000/vectra/envoy` en kind y `registro.banco.internal/vectra/envoy` en staging y prod, con `@sha256:9d84a586119a27b50437dbb01eccd4722832741539b1ed53c8e9d6da6067a6e0` en los values de cada entorno; sin digest, el generador falla;
  - réplicas ≥ 2, `envoyHpa` de 2 a 6 con objetivo de CPU del 70 % y `envoyPDB` con `minAvailable: 1`;
  - `topologySpreadConstraints` por `topology.kubernetes.io/zone`;
  - recursos 250m / 256 MiB y 1 CPU / 512 MiB;
  - `priorityClassName: vectra-high`;
  - `securityContext` que cumpla las políticas estáticas de U1 (`STATIC_POLICIES` del `Makefile` de `identity-edge`): no root, sin privilegios, raíz de solo lectura y `seccompProfile: RuntimeDefault`. El sidecar `shutdown-manager` de v1.9.3 también tiene que cumplirlas.
  - Service `LoadBalancer` con `externalTrafficPolicy: Local` y la etiqueta `app.kubernetes.io/name: api-gateway` (`restrict-loadbalancer` de U1).
  - Access log JSON a stdout con exactamente los campos de P-U2-07: `timestamp`, `route_name`, `method`, `status`, `duration_ms`, `upstream_cluster`, `correlation_id` (`%TRACE_ID%`), `client_ip` y `response_flags`. Ni query string, ni cuerpo, ni `Authorization`, ni cookies, ni cabeceras `x-vectra-*`. Para `route_name` y `method`, usa operadores que no lleven la query.
  - Tracing OpenTelemetry hacia `otel-collector.vectra-observability.svc:4317`, con muestreo del 100 %.
- **IP real** (W2, NFR-U2-23): la `ClientTrafficPolicy` de `route-gen` deja de confiar en `X-Forwarded-For`. Se quita `clientIPDetection.xForwardedFor.numTrustedHops: 1`, o se deja en 0 si v1.9.3 lo exige, y `trusted_hops` de `routes.yaml` cambia a 0. Envoy toma la dirección remota, que con `externalTrafficPolicy: Local` es la del cliente.
- **Modo de fallo** (W3, P-U2-01):
  - Los dos contadores por IP de `/auth/**` salen de `edge-rate-limits` a una `BackendTrafficPolicy` del `Gateway`, `auth-rate-limits`, con reglas `shared` y `mergeType: StrategicMerge`.
  - El límite global de 200/s sigue en `edge-rate-limits`.
  - Una `EnvoyPatchPolicy` (`type: JSONPatch`, con `targetRef` al `Gateway`) fija en el filtro `envoy.filters.http.ratelimit/<dominio de auth-rate-limits>` del listener `https` `failure_mode_deny: true` y `status_on_error: {code: 503}`.
  - Las rutas de `/auth/**` agregan un `responseOverride` de 503 con `Problem` `dependency_unavailable`.
  - Comprueba en `internal/xds/translator/ratelimit.go` y `jsonpatch.go` de v1.9.3 el nombre exacto del filtro y del listener.
- **Verificación offline** (aceptación del plan):
  - `make -C identity-edge xds-gateway` corre `egctl x translate --from gateway-api --to xds` sobre `generated/<env>/` en los tres entornos;
  - `identity-edge/tests/unit/test_gateway_xds.py` lee esa salida y comprueba que el filtro del dominio de `auth-rate-limits` tiene `failure_mode_deny: true` y `status_on_error` 503, y que ningún otro filtro de rate limit tiene `failure_mode_deny`;
  - la misma prueba comprueba en el xDS:
    - el access log;
    - el tracing;
    - que no hay `xff_num_trusted_hops` mayor que 0;
    - que todas las políticas generadas se aceptan: ningún estado `Accepted: False` ni error en la salida de `--to gateway-api`.
- **ADR** (`identity-edge/docs/adr-envoy-gateway.md`), con la cita del código de v1.9.3 de cada punto:
  1. el data plane en `vectra-edge` con `deploy.type: GatewayNamespace`;
  2. la alternativa 2 de P-U2-01 y por qué no la 1 ni la 3;
  3. el servicio de rate limit del controlador (W1);
  4. la IP real (W2);
  5. el binding K14.

  La entrada de `audit.md` la escribe el orquestador.
- **Herramientas** (W7): `EGCTL_VERSION=v1.9.3` y `EGCTL_SHA256=82b6164a6cd966fcb6e244a5931c6c3e46193816714a0b69043db1606098150f` en `platform/tools.env`. `install-tools.sh` descarga `egctl_v1.9.3_linux_amd64.tar.gz`, comprueba el sha256 y lo instala en `platform/.tools/bin/egctl`. `check-tools` exige el binario.

**Fuera:**
- La conexión del servicio de rate limit a Valkey, su HPA, sus recursos y los flujos F90–F93: Paso 9 (W1).
- Valkey: Paso 9.
- Flujos, NetworkPolicies y RBAC de `flows.yaml`: Paso 10. Si el punto 1 del ADR obligara a mover el data plane, detente y repórtalo antes de tocar `flows.yaml`.
- Entradas de `vectra-risk-gitops/components.yaml` para lo generado: Paso de integración.
- Cualquier cosa contra un clúster o contra Docker.
- En `platform/` solo se tocan `operators/envoy-gateway.yaml`, `tools.env`, `install-tools.sh` y `check-tools`.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 7, 8 y 9)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01, 02, 03, 06 y 10)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-01, P-U2-07)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-03, 04, 21, 22, 23)
- `aidlc-docs/construction/identity-edge/nfr-design/logical-components.md` (§1)
- `aidlc-docs/inception/application-design/component-dependency.md` (§3, K14)
- `aidlc-docs/construction/contracts/nfr-design/nfr-design-patterns.md` (P-U0-11)
- `identity-edge/gateway/routes.yaml`, `identity-edge/tools/route_gen.py`, `identity-edge/gateway/policy/`, `identity-edge/tests/strategies/gateway_*.py` (Paso 7)
- `platform/operators/envoy-gateway.yaml`, `platform/tools.env`, `platform/install-tools.sh`, `platform/policies/kyverno/`

## Criterios de aceptación

- [ ] **CA-1** — Aceptación del Paso 8.
  ```bash
  make -C identity-edge xds-gateway && uv run pytest identity-edge/tests/unit/test_gateway_xds.py -q && test -s identity-edge/docs/adr-envoy-gateway.md
  ```
  Esperado: pasa en los tres entornos. Además, un `generated/` en el que el contador de `/auth/**` volviera a `edge-rate-limits`, o sin la `EnvoyPatchPolicy`, hace fallar la prueba.
- [ ] **CA-2** — Lo generado del Paso 8 sigue el diseño. Lo comprueban `test_route_gen.py` y conftest (`identity-edge/gateway/policy/`):
  - el conjunto exacto de documentos de cada entorno, cada uno comparado completo con el oráculo, que lee del diseño todo valor que el diseño fija (lección de U02-T09). Esto incluye el digest de W4, los valores de W5, los campos de P-U2-07, el destino del tracing, el issuer de cada entorno, los recursos de INF-U2-06 y el filtro de W3;
  - `kubeconform -strict` de CA-2 de U02-T09 pasa con los documentos nuevos;
  - sin digest, el generador falla;
  - la prueba de que un cambio en el diseño que no llega al oráculo hace fallar alguna prueba se amplía a los valores nuevos.

  Cada regla de conftest tiene un caso que falla.
  ```bash
  uv run python identity-edge/tools/route_gen.py --check && make -C identity-edge kubeconform-gateway policy-gateway && uv run pytest identity-edge/tests/unit/test_route_gen.py -q
  ```
  Esperado: pasa.
- [ ] **CA-3** — Values del controlador.
  ```bash
  make -C identity-edge render-envoy-gateway && uv run pytest identity-edge/tests/unit/test_envoy_gateway_values.py -q
  ```
  Esperado: pasa. `render-envoy-gateway` corre `helm template` del chart `gateway-helm` v1.9.3 de `platform/.charts/` con `platform/operators/envoy-gateway.yaml`. La prueba comprueba sobre el render:
  - 2 réplicas;
  - prioridad;
  - recursos;
  - `GatewayNamespace`;
  - `enableEnvoyPatchPolicy`;
  - sin `rateLimit`.

  También compara el RBAC con K14, y lo que sobra queda listado en el ADR.
- [ ] **CA-4** — El data plane cumple las políticas de U1. `EnvoyProxy` no genera un Deployment en el render, así que una regla de conftest exige en el `EnvoyProxy` cada campo que piden las `STATIC_POLICIES` de U1 que alcanzan a `vectra-edge`: registro permitido con digest, no root, sin privilegios, raíz de solo lectura, recursos, prioridad, etiqueta de criticidad y la etiqueta de `restrict-loadbalancer` en el Service. Cada campo tiene un caso que falla.
  ```bash
  make -C identity-edge policy-gateway
  ```
  Esperado: pasa. Si una política de U1 exige algo que el diseño de U2 no fija, detente y repórtalo.
- [ ] **CA-5** — La herramienta.
  ```bash
  platform/install-tools.sh && make -C platform check-tools && platform/.tools/bin/egctl version --remote=false
  ```
  Esperado: termina en 0, con el sha256 comprobado; con un sha256 alterado, `install-tools.sh` falla.
- [ ] **CA-6** — Lo anterior sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check && make -C platform check-local
  ```
  Esperado: todo pasa y termina en 0. `check` incluye `xds-gateway` y `render-envoy-gateway`. Corre CA-5 y CA-6 en serie, no en paralelo.

## Plan de pruebas

**Rojo primero:** escribe `test_gateway_xds.py`, `test_envoy_gateway_values.py` y los casos nuevos de `test_route_gen.py`, y registra en la bitácora que fallan antes de cambiar `routes.yaml`, `route_gen.py`, los values y las políticas.

## Notas

- Implementa lo que define el diseño enmendado. Si falta un dato, o si un campo de la API de Envoy Gateway v1.9.3 no permite expresar una precisión, detente y repórtalo; no lo sustituyas por otro mecanismo.
- Los campos se comprueban contra el código del tag v1.9.3 y los esquemas del chart, no de memoria: `gh api repos/envoyproxy/gateway/contents/<ruta>?ref=v1.9.3 -H "Accept: application/vnd.github.raw"`.
- Las clases de valores se definen por listas exactas. No uses expresiones regulares sobre el texto de los manifiestos.
- `identity-edge/gateway/generated/` es salida generada y versionada.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker**: el proyecto los deniega por configuración. El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. La red solo se usa para `install-tools.sh`, `charts.sh` y `gh api` de lectura.
- CA-6 necesita el chart `keycloakx` en `platform/.charts/` (candidata abierta). Si falta, cópialo del worktree de `main` sin versionarlo, y anótalo en la bitácora.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
