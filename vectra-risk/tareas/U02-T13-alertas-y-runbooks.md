# U02-T13 — Alertas, monitores y runbooks de U2

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 y US-611, en su parte de operación (alertas y runbooks). Ninguna historia nueva.
**Depende de:** U02-T12 (PR 67) en `main`. Los monitores necesitan los puertos de F60 (19001 y 9121) que abre ese PR. **No se despacha hasta que el PR 67 esté fusionado.**

Paso 11 del plan de U2. El 2026-11-05 el orquestador comparó P-U2-09 con lo que el código emite hoy y encontró cinco problemas:

- 4 de las 9 alertas no tenían ninguna métrica que las alimentara;
- solo 2 tenían umbral;
- ninguna tenía `for`;
- ningún paso creaba los `ServiceMonitor`;
- el runbook de la vuelta de Valkey a la zona A, que U02-T11 mandó a este paso, no estaba en el plan.

El usuario decidió B1–B9. Están en P-U2-09 («Fuentes, umbrales y despliegue») y en la nota del Paso 11 del plan.

> **Enmienda del 2026-11-05 (orquestador, decisión B10 del usuario tras la parada de la ronda 1; `bitacoras/U02-T13.md`).** En 26.8.1, `keycloak_user_events_total` no lleva ninguna etiqueta de usuario, así que la parada de B1 era correcta. Rige B10 (P-U2-09):
> - `BreakGlassLogin` es `keycloak_user_events_total{event="login", client_id="security-admin-console"}`, con `increase` mayor que 0, en cualquier realm, SEV1 y `for` 0m;
> - la imagen activa `--event-metrics-user-enabled=true` y `--event-metrics-user-tags=realm,clientId` en el `kc.sh build`, junto con `--metrics-enabled=true`;
> - antes de escribir la regla, comprueba en el código de 26.8.1 cómo se escriben los valores de `event` y `client_id` en la métrica (minúsculas, nombre de la etiqueta) y cítalo en la bitácora;
> - `test_keycloak_image.py` comprueba las dos opciones, y falla si falta `clientId` en los tags;
> - los casos de promtool incluyen uno que no dispara: un `client_login` de `keycloak-config-cli`, y un `login` en `vectra-console`.
>
> Donde la tarea dice «Si `break-glass` no se puede distinguir... detente», ya no aplica.

> **Arbitraje del 2026-11-05 tras la ronda 1 (orquestador; hallazgo 1 de tu bitácora).** Tienes razón: `event-metrics-user-tags` es de ejecución en 26.8.1, y la enmienda B10 lo ponía en el build por error del orquestador. Sin ese tag, `BreakGlassLogin` nunca dispara, y eso rompe el propio criterio de la tarea. **Entra en el alcance** (P-U2-09, corrección de B10):
> - en `identity-edge/keycloak/values/common.yaml`, `extraEnv` agrega `KC_EVENT_METRICS_USER_TAGS` con el valor `realm,clientId`;
> - se regenera `identity-edge/keycloak/rendered/<env>/` y pasan `check-keycloak-rendered`, `policy-keycloak` y `policy-keycloak-u1`;
> - la opción de tags sale del `kc.sh build` del Dockerfile, que queda solo con `--event-metrics-user-enabled=true`;
> - una prueba, nueva o en `test_keycloak_deploy.py`, comprueba que el contenedor de Keycloak de los tres renders lleva esa variable con `clientId`. Lee el valor del diseño, y falla si en una copia se quita la variable o el `clientId`;
> - `test_keycloak_image.py` deja de exigir los tags en el build, y falla si vuelven a aparecer ahí;
> - retira de `CANDIDATAS.md` la entrada del hallazgo 1.
>
> El orquestador da por buenos los hallazgos 2 y 3: `error=""` con la rama de primera muestra, y el runbook de failback que borra `valkey-b-0`. Quedan en el diseño. El 4 (`redis_up == 0` con una réplica) se queda en `CANDIDATAS.md`.

## Alcance

**Dentro:** todo el Paso 11 del plan. Texto del plan, sin recortes:

- [ ] **Paso 11 — Alertas y runbooks**
  - `PrometheusRule` con las alertas de P-U2-09, incluida `LdapUnavailable`. Runbooks: `keycloak-down`, `rate-limit-backend-down`, `auth-denied-burst`, `break-glass-login`, `realm-drift`, `role-conflict`, `signing-key-rotation`, `gateway-high-latency`, `ldap-unavailable`.
  - Nota del 2026-11-05 (B1–B9; P-U2-09 «Fuentes, umbrales y despliegue»).
  - Diseño: P-U2-09; BR-U2-17; P-U2-05; NFR-U2-05 (`KeycloakDown`).
  - **Aceptación**: `promtool test rules identity-edge/observability/rules/tests/*.yaml` y `uv run python platform/tests/test_runbooks.py --root identity-edge` (`severity` válida y `runbook_url` existente).

Precisiones del diseño que la tarea aplica. La fuente de cada una va entre paréntesis.

- **Reglas** (B3, B6, B8). Hay dos archivos, como en U1:
  - `identity-edge/observability/rules/identity-edge-rules.yaml`, solo con `groups:`. Es lo que leen promtool y las pruebas;
  - `identity-edge/observability/rules/identity-edge-rules.prometheusrule.yaml`, el CR con `namespace: vectra-observability` y los mismos `groups`.

  Son las 11 alertas de la tabla de P-U2-09 enmendada, con su severidad, su expresión y su `for`. Cada una lleva `runbook_url`, una ruta relativa a `vectra-risk/`, como en U1.
- **Fuentes de Keycloak** (B1). La imagen de `identity-edge/keycloak/Dockerfile` activa las métricas de eventos de usuario, para que exista `keycloak_user_events_total`.
  - Comprueba en el código o la documentación de Keycloak **26.8.1** el nombre de la opción (`user-event-metrics`, `--event-metrics-user-enabled` o lo que corresponda), si es de build o de arranque, las etiquetas de la métrica y cómo se distingue el login de `break-glass` (busca el usuario en los realms y en BR-U2). Regístralo en la bitácora con la ruta y la línea.
  - Si `break-glass` no se puede distinguir con las etiquetas de la métrica, **detente y repórtalo**. No lo sustituyas por otra señal.
  - Actualiza `test_keycloak_image.py` con la opción nueva.
- **Métricas de contrato** (B2). `RoleConflict` usa `vectra_role_conflict_total` y `LdapUnavailable` usa `vectra_ldap_connection_failures_total`. Nada las emite todavía: se prueban con series sintéticas, y cada fuente queda como una entrada en `CANDIDATAS.md`, enlazada con las que ya hay sobre `ROLE_CONFLICT`.
- **RateLimitBackendDown** (B4): kube-state-metrics, con las réplicas disponibles de `envoy-ratelimit` en `envoy-gateway-system` y del StatefulSet de Valkey, o `redis_up == 0`.
- **Monitores** (B5). En `identity-edge/observability/monitors/` van los `ServiceMonitor` o `PodMonitor` de:
  - Keycloak: HTTPS al 9000, con la CA interna (ver la candidata del 9000 en `CANDIDATAS.md`);
  - el data plane de Envoy: 19001;
  - `envoy-ratelimit`: 19001;
  - el exportador de Valkey: 9121.

  Los selectores salen de los pods reales, con los mismos modelos que `platform/network/tests/test_edge_selectors.py`. Los recoge el Prometheus de U1: mira `ruleSelectorNilUsesHelmValues` y el selector de monitores en `platform/observability/values/kube-prometheus-stack.yaml`.
- **Fuentes de cada familia** (B5, lección de `platform/tests/test_alert_sources.py`). Cada familia de métricas que usan las reglas tiene:
  - quien la emite: un monitor de esta tarea, kube-state-metrics, el Pushgateway o una métrica de contrato de B2;
  - si va por monitor, un puerto abierto en F60 de `platform/network/flows.yaml`.
- **Runbooks** (B7). En `identity-edge/runbooks/` van los 9 runbooks del plan, más `valkey-zone-failback.md`, el operativo de INF-U2-04 sin alerta. Cada uno tiene las secciones de `platform/runbooks/_template.md`, y cada paso de «Verificación» nombra un comando (`--operational`).
- **Makefile**. Targets `rules` (`promtool check rules` y `promtool test rules`) y `runbooks` (`test_runbooks.py --root identity-edge` y `--operational`), los dos agregados a `check`.

**Fuera:**
- Las entradas de `vectra-risk-gitops/components.yaml` para reglas y monitores: son del Paso 12 (B6).
- El mecanismo que emite `ROLE_CONFLICT` o los fallos de LDAP, el ruler de Loki y el blackbox exporter: van a `CANDIDATAS.md`.
- Cambiar `platform/observability/` de U1. Las reglas y los monitores de U2 viven en `identity-edge/`. Si una prueba de U1 necesita leerlos, se detiene y se reporta.
- Cualquier cosa contra un clúster o contra Docker, incluido construir la imagen de Keycloak.
- `flows.yaml`: F60 ya trae los puertos, desde U02-T12. Si falta uno, detente y repórtalo.

## Archivos de contexto

- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 11 y árbol de §1)
- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-05; P-U2-09 y su enmienda B1–B9)
- `aidlc-docs/construction/identity-edge/functional-design/business-rules.md` (BR-U2-17, `ROLE_CONFLICT`, `BreakGlassLogin`)
- `aidlc-docs/construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-05)
- `aidlc-docs/construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-04: vuelta a la zona A; INF-U2-07: LDAP; INF-U2-09)
- `platform/observability/rules/` (los dos archivos y `tests/`), `platform/observability/monitors/monitors.yaml`, `platform/observability/values/kube-prometheus-stack.yaml`
- `platform/runbooks/_template.md` y `platform/runbooks/pushgateway-down.md` (ejemplo)
- `platform/tests/test_runbooks.py`, `platform/tests/test_alert_sources.py`, `platform/tests/test_ci.py` (prueba de igualdad de `groups`)
- `identity-edge/keycloak/Dockerfile`, `identity-edge/tests/unit/test_keycloak_image.py`
- `identity-edge/jobs/realm_drift.py`, `identity-edge/jobs/signing_key_age.py`, `identity-edge/jobs/chart/values.yaml` (horarios)
- `contracts/python/vectra_common/src/vectra_common/metrics.py` (`vectra_authz_denied_total`)
- `platform/network/flows.yaml` (F60) y `platform/network/tests/test_edge_selectors.py` (modelos de los pods)
- `CANDIDATAS.md`

## Criterios de aceptación

Corre los comandos desde `vectra-risk/`.

- [ ] **CA-1** — Es la aceptación del Paso 11: las reglas son válidas y cada alerta dispara y no dispara.
  ```bash
  platform/.tools/bin/promtool check rules identity-edge/observability/rules/identity-edge-rules.yaml && platform/.tools/bin/promtool test rules identity-edge/observability/rules/tests/*.yaml
  ```
  Esperado: pasa. Las 11 alertas tienen al menos un caso que dispara, con sus etiquetas y su `severity`, y uno que no dispara: por debajo del umbral, o antes de cumplir el `for`.
- [ ] **CA-2** — Es la aceptación del Paso 11: los runbooks.
  ```bash
  uv run python platform/tests/test_runbooks.py --root identity-edge && uv run python platform/tests/test_runbooks.py --root identity-edge --operational
  ```
  Esperado: los dos terminan en 0. El primero informa las 11 alertas con su runbook en regla.
- [ ] **CA-3** — Las reglas corresponden al diseño y cada métrica tiene fuente.
  ```bash
  uv run pytest identity-edge/tests/unit/test_alert_rules.py -q
  ```
  Esperado: pasa. Comprueba lo siguiente:
  - los nombres, severidades, umbrales y `for` salen de la tabla de P-U2-09 enmendada, leída del diseño y no de literales;
  - el conjunto de runbooks es la lista del plan más `valkey-zone-failback`;
  - el CR tiene los mismos `groups` que el archivo de reglas y está en `vectra-observability`;
  - cada familia de métricas tiene su fuente y, si va por monitor, su puerto en F60;
  - los selectores de los monitores seleccionan los pods reales.

  Cada comprobación falla en una copia mutada. Por ejemplo: un umbral cambiado, un runbook borrado, un monitor con otra etiqueta, una familia sin fuente.
- [ ] **CA-4** — La imagen de Keycloak activa las métricas de eventos de usuario (B1).
  ```bash
  uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q
  ```
  Esperado: pasa, con un caso que falla si se quita la opción. La bitácora cita dónde fija Keycloak 26.8.1 la opción y las etiquetas.
- [ ] **CA-5** — U2 sigue cumpliendo, y `check` incluye `rules` y `runbooks`.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: todo pasa y termina en 0, sin pruebas omitidas.
- [ ] **CA-6** — U1 sigue cumpliendo.
  ```bash
  make -C platform check-local
  ```
  Esperado: termina en 0. Corre CA-5 y CA-6 en serie.

## Plan de pruebas

**Rojo primero:** antes de escribir reglas, monitores y runbooks, escribe:
- `test_alert_rules.py`;
- `identity-edge/observability/rules/tests/identity-edge-rules-test.yaml`;
- el caso nuevo de `test_keycloak_image.py`.

Registra en la bitácora que fallan. `test_runbooks.py --root identity-edge` ya termina en 1 con «sin alertas que revisar».

## Notas

- Implementa lo que define el diseño enmendado. Detente y repórtalo, sin sustituirlo por otro mecanismo, si pasa algo de esto:
  - falta un dato;
  - una métrica de la tabla no existe con ese nombre en la versión pinneada (Envoy de Envoy Gateway v1.9.3, `envoy-ratelimit`, `redis_exporter`, Keycloak 26.8.1);
  - una expresión no se puede escribir como la fija la tabla.
- Comprueba los nombres de métricas contra el código de los tags, no de memoria, con `gh api repos/<org>/<repo>/contents/<ruta>?ref=<tag> -H "Accept: application/vnd.github.raw"`.
- Ninguna prueba de pytest fija con un literal propio un valor que el diseño fija (umbrales, `for`, severidades, puertos): lo lee del diseño o del modelo.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- La red solo se usa para `install-tools.sh`, `charts.sh` y `gh api` de lectura.
- Si ves otro defecto, va a `CANDIDATAS.md`, no al diff.
