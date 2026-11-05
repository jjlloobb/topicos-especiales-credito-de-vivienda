# U02-T12 — Flujos y RBAC del borde

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-611 (exceso de solicitudes → 429), por la red que lo hace posible. Ninguna historia nueva.
**Depende de:** U02-T11 (`envoy-ratelimit`, chart de Valkey), en `main` (PR 65)

Paso 10 del plan de U2. El 2026-11-05 el orquestador comparó `platform/network/flows.yaml` y `generate.py` con el diseño enmendado por R1–R8 de U02-T11. El usuario decidió T1–T4:
- T1: autorizar a `envoy-ratelimit` sin malla;
- T2: el flujo de Valkey a Sentinel;
- T3: el scrape;
- T4: las sondas.

Están en INF-U2-04 («Flujos y sondas»), en component-dependency (F60, F61, F91 y F92) y en la nota del Paso 10 del plan.

> **Enmienda del 2026-11-05 (orquestador, decisión T5 del usuario tras la detención de la ronda 1):** T4 quedó confirmado contra Linkerd, pero `REDISCLI_AUTH` no basta para las sondas. Las sondas usan las credenciales de INF-U2-04 «Credenciales de las sondas»:
> - **Valkey:** usuario `exporter`, con `VALKEY_PROBE_PASSWORD` desde la clave `exporter-password` de `valkey-acl`;
> - **Sentinel:** usuario `ratelimit`, con el `REDISCLI_AUTH` que ya está en el pod.
>
> Las dos comparan la salida con `PONG`. Donde la tarea dice «autenticadas con `REDISCLI_AUTH`», rige T5. CA-3 exige además:
> - que el oráculo lea del diseño el comando, el usuario y la clave del Secret;
> - que conftest rechace una sonda sin `--user` o con la contraseña en la línea de comandos.

## Alcance

**Dentro:** todo el Paso 10 del plan. Texto del plan, sin recortes:

- [ ] **Paso 10 — Flujos y RBAC**
  - **Nota del 2026-11-04 (decisión Z1 del usuario en U02-T10):** la identidad `api-gateway` de `flows.yaml` pasa a seleccionar el data plane por `gateway.envoyproxy.io/owning-gateway-name: api-gateway` (INF-U2-02).
  - Verificar en `platform/network/flows.yaml` de U1, donde ya están: F05, F43, F50, F73 (solo prod), F90–F95, F112, F117 y el scrape de Keycloak (9000). El de `vectra-edge` es F60, solo al 8081: Envoy, rate limit y el exportador de Valkey se publican en ese puerto o se agrega su puerto por PR (revisión de consistencia entre unidades, 2026-11-01). Agregar el RBAC K14. `realm-drift` no tiene binding: usa F94, no la API de Kubernetes (cuarta revisión de coherencia entre unidades, 2026-10-31).
  - **Nota del 2026-11-05 (decisiones T1–T4 del usuario al preparar U02-T12; INF-U2-04 «Flujos y sondas», component-dependency F60, F61, F91 y F92):** el servicio de rate limit es `envoy-ratelimit` en `envoy-gateway-system` (F90 al 8081), fuera de la malla y autorizado por `NetworkAuthentication` (T1); F92 suma Valkey → Sentinel 26379 (T2); F60 suma los 19001 de Envoy y `envoy-ratelimit` y el 9121 del exportador (T3); las sondas de Valkey y Sentinel pasan a `exec` (T4, toca el chart del Paso 9). K14 ya está en `flows.yaml` desde U02-T10 (X2): se verifica, no se agrega.
  - Diseño: INF-U2-02..04; P-U1-01.
  - **Aceptación**: `uv run python platform/network/generate.py --check` y `uv run pytest platform/network/tests` (los IDs F90–F95 y K14 de `component-dependency.md` están en `flows.yaml`).

Precisiones del diseño que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Identidad `api-gateway`** (Z1, INF-U2-02): en `workloads`, `api-gateway` selecciona por `labels: { gateway.envoyproxy.io/owning-gateway-name: api-gateway }`, con `sa: api-gateway`. La etiqueta sale del modelo de `identity-edge/tests/unit/test_data_plane_policies.py` y de `generated/<env>/envoyproxies.yaml`, no de un literal propio.
- **Identidad del rate limit** (R1 de U02-T11, T1):
  - el workload `rate-limit` pasa a `envoy-gateway-system`, con `sa: envoy-ratelimit` y las tres etiquetas de `rateLimitLabels()` de v1.9.3;
  - el nombre de la clave del workload no cambia, porque `platform/tests/test_waves.py` (`FIXED_WAVES`) lo usa y eso es del Paso 12;
  - compruébalo contra `internal/infrastructure/kubernetes/ratelimit/resource.go` y `resource_provider.go` de v1.9.3.
- **F90** (R1): `api-gateway` → `rate-limit` en el **8081**. Reemplaza al 8083.
- **F91** (R1, T1):
  - `rate-limit` → `valkey` y `sentinel` en el 6379 y el 26379, con `unmeshed_source: true`;
  - `generate.py` genera la `NetworkAuthentication` por `pod_cidr` y su `AuthorizationPolicy` para cualquier puerto de un flujo `unmeshed_source`, no solo para el 5432. Si el puerto es opaco, el `Server` se declara `opaque`, como el 5432;
  - F80 no debe cambiar su salida, salvo lo que sea idéntico.
- **F61** (R8 de U02-T11, T1): `rate-limit` → `otel-collector` en el 4317, como origen sin malla, con la misma autorización de T1.
- **F92** (T2):
  - además de `valkey` → `valkey` en el 6379, una segunda línea con el mismo id: `valkey` → `sentinel` en el 26379;
  - F93 queda igual.
- **F60** (T3): tres líneas nuevas desde `prometheus`:
  - `api-gateway` en el 19001;
  - `rate-limit` en el 19001;
  - `valkey` en el 9121.

  El 19001 del data plane se comprueba en `internal/xds/bootstrap/` de v1.9.3 (puerto de estadísticas de Envoy); si no es el 19001, detente y repórtalo.
- **Sondas** (T4):
  - primero confirma, contra el código del proxy de Linkerd de la versión pinneada (`linkerd-control-plane` 2026.10.2 en `vectra-risk-gitops/components.yaml`), que una sonda `tcpSocket` contra un puerto de la malla la acepta el proxy aunque la aplicación no escuche. Regístralo en la bitácora con la ruta y la línea;
  - si se confirma, las sondas `readinessProbe` y `livenessProbe` de Valkey y Sentinel pasan a `exec` con `valkey-cli` y `PING`, contra el 6379 y el 26379 de `localhost`, autenticadas con `REDISCLI_AUTH`, que ya está en el pod. Vuelve a renderizar `identity-edge/charts/valkey/rendered/<env>/`, y el oráculo de `test_valkey_chart.py` lee las sondas del diseño;
  - si no se confirma, detente y repórtalo sin cambiar las sondas.
- **K14** (X2 de U02-T10): ya está en `k_egress`. Verifica que los namespaces y el RBAC coinciden con component-dependency K14 y con `identity-edge/docs/adr-envoy-gateway.md` §5. Si falta algo, detente y repórtalo.
- **Verificaciones del plan:** F05, F43, F50, F73 (solo prod), F93–F95, F112, F117 y el scrape de Keycloak (9000) se comprueban en `flows.yaml` contra component-dependency. Lo que no coincida se reporta, no se arregla en silencio.
- **Los selectores seleccionan de verdad** (lección de F-12 de U02-T10 y de F-01 de U02-T11). Una prueba nueva, `platform/network/tests/test_edge_selectors.py`, comprueba que el `podSelector` y el `namespaceSelector` de cada NetworkPolicy y `Server` generados para `api-gateway`, `rate-limit`, `valkey` y `sentinel` seleccionan los pods reales:
  - el data plane del modelo de `test_data_plane_policies.py`;
  - el Deployment de `envoy-ratelimit` del modelo de `test_ratelimit_deployment.py`;
  - los StatefulSet de `identity-edge/charts/valkey/rendered/<env>/`.

  Debe fallar si la etiqueta de un workload de `flows.yaml` no está en el pod.

**Fuera:**
- Alertas y runbooks: Paso 11.
- `vectra-risk-gitops/components.yaml`, `FIXED_WAVES` de `test_waves.py` y la candidata del añadido a `services()` de `test_integration.py`: Paso 12.
- Los `ServiceMonitor` y `PodMonitor` de los puertos nuevos: no los nombra el Paso 10. Si hacen falta para el scrape, van a `CANDIDATAS.md`.
- Pedir el rango de pods del banco: `pod_cidr` de staging y prod sigue en `0.0.0.0/32`.
- Cualquier cosa contra un clúster o contra Docker. La conectividad en vivo es del Paso 16.
- En `platform/` solo se tocan:
  - `network/flows.yaml`, `network/generate.py`, `network/generated/` y `network/tests/`;
  - las pruebas de U1 que fijan la identidad o los puertos del borde, como `platform/tests/test_unit_plans.py::test_u2_plan_sets_the_identity_flows_expects` y `test_integration.py`, si el cambio las rompe.
- En `identity-edge/` solo se tocan el chart de Valkey (sondas, por T4), su render y sus pruebas.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Pasos 9 y 10)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md`:
  - INF-U2-02: Z1;
  - INF-U2-03;
  - INF-U2-04: «Flujos (para el Paso 10)» y «Flujos y sondas».
- `aidlc-docs/inception/application-design/component-dependency.md` (§0, §2.8: F60, F61, F90–F95; §3: K14)
- `aidlc-docs/construction/platform-foundation/nfr-design/` (P-U1-01 y P-U1-02, el generador de flujos)
- `platform/network/flows.yaml`, `platform/network/generate.py`, `platform/network/forbidden.yaml`, `platform/network/tests/test_flows.py`
- `platform/tests/test_unit_plans.py`, `platform/tests/test_integration.py`
- `identity-edge/charts/valkey/`, `identity-edge/tests/unit/test_valkey_chart.py`, `identity-edge/tests/strategies/valkey_design.py`
- `identity-edge/tests/unit/test_data_plane_policies.py` y `test_ratelimit_deployment.py` (modelos de los pods de v1.9.3)
- `identity-edge/docs/adr-envoy-gateway.md` (§5, K14)
- `revisiones/U01-T03/` (lección de flujos: los criterios incluyen `test_integration.py`)

## Criterios de aceptación

- [ ] **CA-1** — Es la aceptación del Paso 10: lo generado está al día y las pruebas de flujos pasan.
  ```bash
  uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q
  ```
  Esperado: pasa. `test_flows.py` comprueba que los ids F90–F95 y K14 de `component-dependency.md` están en `flows.yaml`. Además, pruebas nuevas comprueban sobre lo generado en los tres entornos:
  - **F90** abre el 8081 hacia `envoy-gateway-system`, y no el 8083;
  - **F91 y F61** de `rate-limit`: una `NetworkAuthentication` con el `pod_cidr` del entorno, su `AuthorizationPolicy` sobre el `Server` del puerto y la NetworkPolicy que limita el origen a los pods de `envoy-ratelimit`;
  - **F92** con sus dos líneas;
  - **F60** con los tres puertos nuevos.

  Cada una falla con el cambio contrario aplicado en una copia de `flows.yaml`. F80 genera lo mismo que en `main`.
- [ ] **CA-2** — Los selectores seleccionan los pods reales.
  ```bash
  uv run pytest platform/network/tests/test_edge_selectors.py -q
  ```
  Esperado: pasa en los tres entornos. Falla si, en una copia, la etiqueta de `api-gateway`, `rate-limit`, `valkey` o `sentinel` de `flows.yaml` deja de coincidir con su pod, o si el namespace de `rate-limit` vuelve a `vectra-edge`.
- [ ] **CA-3** — Sondas de Valkey y Sentinel (T4).
  ```bash
  make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && uv run pytest identity-edge/tests/unit/test_valkey_chart.py -q
  ```
  Esperado: pasa. Las sondas son `exec` con `valkey-cli` contra el puerto de cada contenedor, y el oráculo las lee del diseño. Hay una regla de conftest que rechaza una sonda `tcpSocket` en Valkey o Sentinel, con su caso que falla. La bitácora cita la línea del proxy de Linkerd que justifica T4.
- [ ] **CA-4** — U1 sigue cumpliendo, incluida la integración (lección de U01-T03).
  ```bash
  uv run pytest platform/tests/test_integration.py -q && make -C platform check-local
  ```
  Esperado: pasa y termina en 0.
- [ ] **CA-5** — U2 sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: todo pasa y termina en 0, sin pruebas omitidas. Corre CA-4 y CA-5 en serie, no en paralelo.

## Plan de pruebas

**Rojo primero:** escribe las pruebas nuevas de CA-1, `test_edge_selectors.py`, los casos de sondas de `test_valkey_chart.py` y la regla de conftest con su caso que falla. Registra en la bitácora que fallan antes de cambiar `flows.yaml`, `generate.py` y el chart.

## Notas

- Implementa lo que define el diseño enmendado. Detente y repórtalo, sin sustituirlo por otro mecanismo, si pasa algo de esto:
  - falta un dato;
  - una verificación del plan no coincide;
  - v1.9.3 o Linkerd no se comportan como asume T1, T3 o T4.
- Los campos y puertos se comprueban contra el código de los tags, no de memoria:
  - `gh api repos/envoyproxy/gateway/contents/<ruta>?ref=v1.9.3 -H "Accept: application/vnd.github.raw"`;
  - `gh api repos/linkerd/linkerd2-proxy/...` y `repos/linkerd/linkerd2/...`, en el tag que corresponde a la versión 2026.10.2.
- Las clases de valores se definen por listas exactas. No uses expresiones regulares sobre el texto de los manifiestos.
- Ninguna prueba de pytest fija con un literal propio un valor que el diseño fija (puertos, etiquetas, sondas): lo lee del diseño o del modelo. Los literales de las políticas de Rego se aceptan, porque son la política misma (arbitraje de la ronda 2 de U02-T11).
- Lo generado (`platform/network/generated/`, `identity-edge/charts/valkey/rendered/`) es salida versionada.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker**: el proyecto los deniega por configuración. El destino es un pull request, y lo fusiona una persona.
- Comandos desde `vectra-risk/`. La red solo se usa para `install-tools.sh`, `charts.sh` y `gh api` de lectura.
- CA-5 necesita el chart `keycloakx` en `platform/.charts/` (candidata abierta). Si falta, cópialo del worktree de `main` sin versionarlo y anótalo en la bitácora.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
