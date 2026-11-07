# U02-T17 — Endurecimiento de las alertas de U2

**Unidad:** U2 `identity-edge`
**Historias que implementa:** US-601 y US-611, en su parte de operación (alertas). Ninguna historia nueva.
**Depende de:** U02-T13 (PR 71) en `main`, en 0e3a1f3.

Sigue al Paso 11 del plan, que cerró U02-T13. El usuario pidió revisar el PR 71 ya en verde. La revisión de código encontró que la tabla de P-U2-09, aplicada al pie de la letra, deja alertas que callan:

- `LdapUnavailable` y `RoleConflict` no ven el primer evento de un contador que nace con él, y `LdapUnavailable` no dispara con un fallo corto;
- `RateLimitBackendDown` calla si desaparecen las series de kube-state-metrics del Deployment o del StatefulSet;
- `RealmDriftStale` y `SigningKeyAgeStale` callan si el Pushgateway pierde el grupo o el CronJob nunca empujó;
- `GatewayHighLatency` mezcla todos los listeners y clusters de Envoy.

El usuario decidió B12–B15 el 2026-11-06. Están en P-U2-09 («Endurecimiento de las alertas»), en la tabla enmendada y en la nota del Paso 11 del plan.

## Alcance

**Dentro:**

> Las reglas de `identity-edge/observability/rules/` cumplen la tabla de P-U2-09 enmendada por B12–B14, con sus casos de promtool, sus pruebas y sus runbooks; B15 queda escrito en el runbook `break-glass-login`.

Precisiones del diseño que la tarea aplica. La fuente de cada una va entre paréntesis.

- **B12**: `LdapUnavailable` y `RoleConflict` llevan, además del `increase`, la rama de serie nueva (`X > 0 unless X offset 5m`), con `for` 0m.
  - Casos de promtool: dispara con la primera muestra de una serie nueva, dispara con un fallo corto (un solo incremento), y no dispara con el contador quieto.
- **B13**: `RateLimitBackendDown` lleva `or absent(...)` de la serie de kube-state-metrics del Deployment `envoy-ratelimit` y de la del StatefulSet de Valkey; `RealmDriftStale` y `SigningKeyAgeStale` llevan `or absent(push_time_seconds{job="..."})` de su grupo.
  - Casos de promtool: dispara con cada serie ausente, y no dispara con las series presentes y sanas.
  - `absent()` devuelve una serie sin las etiquetas del selector que no son de igualdad. Comprueba en promtool qué etiquetas trae la alerta y que el runbook dice qué mirar en ese caso.
  - Los runbooks `rate-limit-backend-down`, `realm-drift` y `signing-key-rotation` dicen qué significa la alerta por ausencia, y que en kind las dos `*Stale` disparan si los CronJobs no corren.
- **B14**: `GatewayHighLatency` filtra el p95 de downstream al listener HTTP del `api-gateway` y el de upstream a los clusters de sus rutas, sin el cluster del rate limit ni los listeners de estadísticas (19001) y de readiness.
  - Comprueba en el código de Envoy Gateway **v1.9.3** (y del Envoy que trae) qué etiqueta lleva el prefijo del HTTP connection manager y el nombre del cluster en Prometheus, y qué valores toman para el `api-gateway` de `identity-edge/gateway/` y para el cluster del rate limit. Regístralo en la bitácora con ruta y línea.
  - Si los nombres no se pueden fijar desde el código pinneado, **detente y repórtalo**. No adivines etiquetas.
  - Casos de promtool: con series del listener de estadísticas o del cluster del rate limit que moverían el p95, la alerta no cambia.
- **B15**: el runbook `break-glass-login` deja claro que el reinicio normal del pod es un límite aceptado (B15) junto a los de B11. No cambia la regla.
- **Pruebas** de `identity-edge/tests/unit/test_alert_rules.py`: los `for`, las ventanas y las familias siguen saliendo de la tabla del diseño, sin literales. Agrega lo necesario para que la tabla enmendada se compruebe:
  - la rama de serie nueva de B12 en las dos alertas;
  - el `absent()` de B13 en las tres;
  - el filtro de B14.

  Cada una falla en una copia mutada que quite esa parte.
- **CR**: `identity-edge-rules.prometheusrule.yaml` lleva los mismos `groups` (la prueba que ya existe).

**Fuera:**

- `BreakGlassLogin`: su expresión no cambia (B15). El ruler de Loki sigue en `CANDIDATAS.md`.
- `KeycloakDown`, `AuthDeniedBurst`, `RealmDrift`, `SigningKeyAgeHigh` y `KeycloakMetricsDown`.
- Los monitores, `flows.yaml`, la imagen y los values de Keycloak.
- Los otros hallazgos menores de la revisión del PR 71: la regla de grabación para el selector de break-glass, `test_keycloak_image.py` y el helper repetido de `keycloak_deploy_checks.py`. Están en `CANDIDATAS.md`.
- `platform/observability/` de U1 y las Applications de GitOps (Paso 12).
- Cualquier cosa contra un clúster o contra Docker.

## Archivos de contexto

- `aidlc-docs/construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-09: la tabla enmendada, B11 y «Endurecimiento de las alertas», B12–B15)
- `aidlc-docs/construction/plans/identity-edge-code-generation-plan.md` (Paso 11 y su nota del 2026-11-06)
- `identity-edge/observability/rules/` (los dos archivos y `tests/`)
- `identity-edge/runbooks/` (`ldap-unavailable`, `role-conflict`, `rate-limit-backend-down`, `realm-drift`, `signing-key-rotation`, `gateway-high-latency`, `break-glass-login`)
- `identity-edge/tests/unit/test_alert_rules.py`
- `identity-edge/gateway/` (el `api-gateway` y sus rutas) y `identity-edge/ratelimit/` (el cluster del rate limit)
- `tareas/U02-T13-alertas-y-runbooks.md` y `bitacoras/U02-T13.md` (cómo se escribieron las reglas y la rama de serie nueva de B11)
- `platform/tests/test_runbooks.py` y `platform/runbooks/_template.md`
- `CANDIDATAS.md`

## Criterios de aceptación

Corre los comandos desde `vectra-risk/`.

- [ ] **CA-1** — Las reglas son válidas y cada alerta tocada dispara y no dispara según B12–B14.
  ```bash
  platform/.tools/bin/promtool check rules identity-edge/observability/rules/identity-edge-rules.yaml && platform/.tools/bin/promtool test rules identity-edge/observability/rules/tests/*.yaml
  ```
  Esperado: pasa. Cada alerta tocada tiene sus casos:
  - `LdapUnavailable` y `RoleConflict`: la primera muestra de una serie nueva, un incremento único y el contador quieto;
  - `RateLimitBackendDown`, `RealmDriftStale` y `SigningKeyAgeStale`: cada serie ausente y las series sanas;
  - `GatewayHighLatency`: el filtro, con series ajenas que no la mueven.

  Los casos que ya había de las alertas no tocadas siguen igual.
- [ ] **CA-2** — Los runbooks siguen en regla.
  ```bash
  uv run python platform/tests/test_runbooks.py --root identity-edge && uv run python platform/tests/test_runbooks.py --root identity-edge --operational
  ```
  Esperado: los dos terminan en 0.
- [ ] **CA-3** — Las reglas corresponden a la tabla enmendada.
  ```bash
  uv run pytest identity-edge/tests/unit/test_alert_rules.py -q
  ```
  Esperado: pasa. Con la tabla enmendada y las reglas de 0e3a1f3, la bitácora muestra el rojo (`RoleConflict: for 5m y el diseno dice 0m`, entre otros). Cada parte nueva (B12, B13 y B14) falla en una copia mutada que la quite.
- [ ] **CA-4** — U2 sigue cumpliendo.
  ```bash
  uv sync --frozen && make -C identity-edge check
  ```
  Esperado: termina en 0, sin fallos ni omitidas. En un worktree nuevo, antes instala herramientas y charts (`bash platform/install-tools.sh` y `bash platform/charts.sh`, y el chart keycloakx de `CANDIDATAS.md`).
- [ ] **CA-5** — U1 sigue cumpliendo. Va en serie, después de CA-4.
  ```bash
  make -C platform check-local
  ```
  Esperado: termina en 0.

## Plan de pruebas

**Rojo primero:** antes de cambiar las reglas, escribe los casos nuevos de promtool y las comprobaciones nuevas de `test_alert_rules.py`. Registra en la bitácora que fallan contra las reglas de 0e3a1f3.

## Notas

- Implementa lo que define el diseño enmendado. Si una expresión no se puede escribir como la fija la tabla, o una etiqueta de B14 no existe en v1.9.3, **detente y repórtalo**.
- Comprueba los nombres contra el código de los tags, no de memoria, con `gh api repos/<org>/<repo>/contents/<ruta>?ref=<tag> -H "Accept: application/vnd.github.raw"`.
- Ninguna prueba de pytest fija con un literal propio un valor que el diseño fija (umbrales, `for`, ventanas, severidades): lo lee del diseño.
- Directorio temporal propio: un subdirectorio `U02-T17-<papel>-r<n>/` de tu scratchpad.
- Trabaja solo en tu worktree. **Nada contra un clúster ni contra Docker.** El destino es un pull request, y lo fusiona una persona.
- Si ves otro defecto, va a la bitácora como candidata; no lo arregles en el diff.

## Enmienda del 2026-11-07, después de la revisión de código del PR 74 (decisiones B16 y B17 del usuario)

Los hallazgos están en `revisiones/U02-T17/revision-codigo-pr74.md` (C-01 a C-03 y C-05) y el arbitraje en `revisiones/U02-T17/arbitraje-ronda-2.md`. Las decisiones están en P-U2-09, en «Endurecimiento de las alertas» y en la tabla.

- **B16**: `LdapUnavailable` y `RoleConflict` llevan la guarda de B11 tal como la fija el diseño.
  - Casos de promtool que pasan después de la enmienda:
    - un contador que vale más de 0, con un hueco de scrape de 6 min y sin incremento, **no** dispara;
    - un incremento durante el hueco **sí** dispara;
    - los casos de B12 (primera muestra, fallo corto, contador quieto) siguen como están.
  - La bitácora registra el rojo del primer caso contra `842d3f1`.
- **B17**: las ramas por ausencia de `RateLimitBackendDown`, `RealmDriftStale` y `SigningKeyAgeStale` usan `absent_over_time(...[10m])` y se condicionan a `up` de su exportador.
  - Casos de promtool que pasan después de la enmienda:
    - un solo scrape fallido del Pushgateway **no** dispara las `*Stale`;
    - con el exportador arriba, el grupo ausente durante 10 min **sí** las dispara;
    - con kube-state-metrics caído, `RateLimitBackendDown` **no** dispara.
  - Si ninguna alerta del proyecto informa la caída de kube-state-metrics, **detente y repórtalo**.
  - La bitácora registra contra `842d3f1` el rojo del primer caso y el del tercero.
- Las pruebas de `test_alert_rules.py` comprueban la guarda de B16 y la ventana y la condición de B17. Cada comprobación falla en una copia mutada que quite esa parte. F-02 de la ronda 1 (subcadenas en lugar del operador) entra aquí, porque toca justamente estas comprobaciones.
- Los runbooks `ldap-unavailable`, `role-conflict`, `rate-limit-backend-down`, `realm-drift` y `signing-key-rotation` describen las guardas y sus límites.
- **Fuera**: C-04 (un solo StatefulSet de Valkey) y C-06 a C-09 siguen en `CANDIDATAS.md`.
- Se corren otra vez CA-1 a CA-5, con CA-5 en serie después de CA-4.
