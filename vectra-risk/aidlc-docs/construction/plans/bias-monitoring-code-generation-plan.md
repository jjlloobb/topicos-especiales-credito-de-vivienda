# Plan de tareas (Code Generation Part 1) — U9 `bias-monitoring`

**Este plan es la única fuente de verdad para generar el código de U9.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U9. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U9 `bias-monitoring`: CronJob de cálculo (único que congela), servicio HTTP `bias-monitoring-service` y librería `vectra_disparity` |
| Historias (dueña) | US-301, US-302, US-303, US-304, US-306, US-307, US-308 |
| Ubicación | `vectra-risk/bias-monitoring/` (una imagen con dos puntos de entrada; la librería como paquete propio del workspace) y Applications en `vectra-risk-gitops` |
| Datos propios | Ninguno: lee conteos agregados del registro (F26) y publica métricas (F106) |
| Depende de | U0 (tipos de §9.4, `create_app`, `deps.call` con `breaker="disabled"` para batch, catálogo de eventos §8.1, `RouteContract`), U1 (Pushgateway, cuotas, `flows.yaml`, `require-hpa-bounds` con exención, sidecar nativo), U2 (clientes `bias-monitoring-job` y `bias-monitoring-service`), U3 (`POST /v1/monitoring/daily:query`, `GET /v1/monitoring/freezes`, agregador), U4 (`freeze` con su `AuthorizationPolicy`, `compare_source` por F25, `list_models` para el BFF) |
| Lo consumen | console-bff (U10, F14), governance (U4, F25; y la librería en el `model-validation-job`), U5 (la librería), U12 (demostración RT-2) |

**Diseño de entrada:**
- Functional Design: `construction/bias-monitoring/functional-design/` (BR-U9-01..22, PBT-U9-01..08).
- NFR Requirements: `construction/bias-monitoring/nfr-requirements/` (NFR-U9-01..54).
- NFR Design: `construction/bias-monitoring/nfr-design/` (P-U9-01..07).
- Infrastructure Design: `construction/bias-monitoring/infrastructure-design/` (INF-U9-01..05).

**AUTONOMIA-01:** las verificaciones estáticas, las propiedades y las pruebas de integración
con dobles corren en CI. Las que necesitan el clúster las ejecuta **un operador en kind**
después de un PR aprobado (Paso 16), con la evidencia adjunta al PR.

**Dobles hasta que existan las unidades reales:** U3 y U4 ya tienen plan, así que en CI se
usan dobles HTTP que siguen sus contratos (`vectra_contracts`): un registro que responde
`monitoring_daily:query` y `monitoring/freezes`, y un governance con `freeze` y
`list_models`. Las pruebas de kind usan las unidades reales.

### Estructura de destino

```text
vectra-risk/bias-monitoring/
|-- Makefile  pyproject.toml  .importlinter
|-- disparity/        src/vectra_disparity/ {counts, stats, disparity}.py   # librería pura (U4, U5)
|-- src/vectra_bias/
|   |-- config.py
|   |-- freeze_rule.py  context.py  window.py                              # puros
|   |-- registry_client.py  freeze_client.py  publish.py  run.py          # CronJob
|   `-- dashboard.py  freezes.py  compare.py  cache.py  app.py            # servicio
|-- chart/            templates/  values-{prod,staging,kind}.yaml  values-monitoring-policy.yaml
|-- policies/         conftest/
|-- observability/    rules/  rules/tests/  runbooks/  dashboards/bias.json
`-- tests/            unit/ property/ integration/ doubles/ simulation/ load/
```

---

## 2. Pasos

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `bias-monitoring/`**
  - Directorios de §1; `pyproject.toml` con dos miembros del workspace: `vectra_disparity` (sin dependencias de runtime fuera de la biblioteca estándar) y `vectra_bias` (depende de `vectra_contracts`, `vectra_common` y `vectra_disparity`).
  - Dependencias de desarrollo directas: Fairlearn, pandas y numpy, solo para pruebas y la simulación; scipy y scikit-learn llegan como transitivas de Fairlearn. Herramientas de prueba: pytest, pytest-cov (coverage.py), Hypothesis y mutmut (revisión del FD de U10, 2026-10-10, B9).
  - Contratos de import-linter:
    - `vectra_disparity` no importa nada fuera de la biblioteca estándar;
    - `freeze_rule`, `context` y `window` no hacen E/S;
    - `app` y sus módulos no importan `freeze_client` (el servicio no congela);
    - ningún módulo importa `httpx` fuera de `vectra_common.deps`.
  - Diseño: P-U9-04, 05; NFR-U9-30.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config bias-monitoring/.importlinter && make -C bias-monitoring check` sobre el esqueleto; prueba de que el árbol de dependencias de runtime de `vectra_disparity` está vacío.

- [ ] **Paso 2 — Constantes y parámetros**
  - `vectra_bias/config.py`, con las constantes del código:
    - timeouts y reintentos de P-U9-02;
    - caché de 64 entradas y 15 min (P-U9-03);
    - razón de inválidas del 1 % y atraso máximo del agregador de 30 min.
  - Los cinco parámetros de cumplimiento vienen de `values-monitoring-policy.yaml` (INF-U9-03), nunca de constantes (revisión del plan de tareas de U9, 2026-10-10):
    - la app lee umbral, `n_min` y ventana para calcular, y los cinco para informarlos en el paquete y el dashboard (BR-U9-13), desde un `ConfigMap` que el chart genera de ese archivo;
    - el **horario** solo lo usa el chart, en el `schedule` del CronJob, y **W** solo lo usa la `PrometheusRule`.
  - Diseño: INF-U9-03; P-U9-02, 03; NFR-U9-03.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/unit/test_config.py`:
    - el peor caso de una corrida (3 versiones que fallan, 2 solicitudes de rangos, lectura de grupos, 3 `PUT`/`DELETE` de grupos `freeze-<v>` y 16 `DELETE` de versiones que ya no se evalúan; ≈ 186 s, P-U9-02) < `activeDeadlineSeconds` (600 s) (revisión del FD de U10, 2026-10-10, A6);
    - ninguna constante se lee de variables de entorno;
    - un archivo de parámetros con valores fuera de rango → error al arrancar.

### Bloque B — Librería `vectra_disparity`

- [ ] **Paso 3 — `stats`**
  - Funciones puras:
    - intervalo de Wilson;
    - diferencia de Newcombe (método 10);
    - combinación de varianzas `Σ w_b² v_b`.

    Todo con `math`; la salida en `Decimal4`.
  - Diseño: BR-U9-03, 04.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/unit/test_stats.py`, con valores de referencia publicados de Newcombe (1998) para varios pares de proporciones, con tolerancia de 1e−4.

- [ ] **Paso 4 — `counts` y `disparity`**
  - `counts`:
    - `counts_from_records(records) -> dict[atributo, CountTable]`;
    - `CountTable` a partir de los `MonitoringMarginalCount` de un rango.
  - `disparity_by_band(counts, attribute, n_min) -> AttributeResult`:
    - celdas, con la supresión de celdas chicas siempre aplicada (P-U9-04);
    - diferencias por banda, sin `no_informado`;
    - par extremo e intervalo de Newcombe;
    - agregada ponderada con los pesos de BR-U9-04 y su intervalo;
    - diferencia sin bandas con `population_difference_partial`.
  - Agregada del modelo y atributo disparador (BR-U9-05).
  - Diseño: BR-U9-01..07; P-U9-04; NFR-U9-31. Historia: US-301.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_disparity.py tests/property/test_counts.py tests/unit/test_disparity_examples.py`:
    - PBT-U9-01 (oráculo de Fairlearn), PBT-U9-02, PBT-U9-03 y PBT-U9-06;
    - muestra insuficiente: una banda de `region = insular` con 12 casos → «muestra insuficiente» y fuera de la agregada (US-301);
    - un grupo con una celda insuficiente → su tasa sin bandas no aparece y `population_difference_partial = true`;
    - los conteos de la variante proxy de U5 → agregada ≥ 10 pp; los del modelo base → < 5 pp.

- [ ] **Paso 5 — Resumen de la librería y simulación estadística**
  - Cobertura de ramas **100 %** en `stats` y `disparity`; `mutmut` en `stats` y `disparity`, con 0 sobrevivientes sin justificar.
  - Simulación (`tests/simulation/`):
    - cobertura del intervalo de Newcombe con un par fijo (≥ 93 % de 10 000 repeticiones);
    - tasa de congelamientos falsos con disparidad real 0, con 30, 100, 500 y 2 000 casos por celda (≤ 5 % con ≥ 500 casos por celda; el resultado se documenta).
  - Versión SemVer de la librería (NFR-U9-54).
  - Resumen en `aidlc-docs/construction/bias-monitoring/code/library.md`.
  - Diseño: NFR-U9-50, 51, 53, 54.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py --cov=vectra_disparity --cov-branch --cov-fail-under=100` (las pruebas de la librería viven en `bias-monitoring/tests`; revisión del plan de tareas de U9, 2026-10-10); `uv run mutmut run --paths-to-mutate bias-monitoring/disparity/src/vectra_disparity/stats.py,bias-monitoring/disparity/src/vectra_disparity/disparity.py`; `uv run pytest bias-monitoring/tests/simulation -m simulation` (en el workflow nocturno y en los PR que cambien `stats` o `freeze_rule`, Paso 15).

### Bloque C — Lógica del CronJob

- [ ] **Paso 6 — `window`, `freeze_rule` y `context`**
  - `window`: inicio de la ventana de cada versión, el más tardío entre el primer día con datos y el día siguiente (UTC) al `recorded_at` de su última reactivación; rangos de 30 días UTC (BR-U9-08).
  - `freeze_rule`: `decide(result, threshold) -> FreezeDecision` (BR-U9-11); la población `humana` nunca produce `freeze`.
  - `context`: `build_context_package` con antes, después y últimos 7 días, sin tasas de celdas insuficientes, ≤ 48 KiB con recorte ordenado y `truncated` (BR-U9-15).
  - Diseño: BR-U9-08, 11, 14, 15. Historias: US-303, US-304.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_freeze_rule.py tests/property/test_context.py tests/unit/test_window.py`:
    - PBT-U9-04 y PBT-U9-08;
    - reactivación con `recorded_at` a las 23:50 UTC del día D → la ventana empieza el día D + 1;
    - paquete con los catálogos completos → ≤ 48 KiB o `truncated = true` con las agregadas intactas;
    - con 40 casos por celda y 6 pp → sin `freeze`; con 2 000 casos y 6 pp → `freeze`.

- [ ] **Paso 7 — `registry_client`, `freeze_client` y `publish`**
  - `registry_client`:
    - `GET /v1/monitoring/freezes`;
    - `POST /v1/monitoring/daily:query` en solicitudes de ≤ 12 rangos, con `unattributable_range` solo en la primera;
    - en el CronJob, `deps.call` con `breaker="disabled"` y `process_kind="batch"`; en el servicio, con breaker (P-U9-02).
  - `freeze_client`: solo `POST /v1/models/{id}/freeze`, con 3 reintentos (1, 2 y 4 s) y timeout de 3 s.
  - `publish`:
    - grupos `run` y `success` del Pushgateway, con `PUT`;
    - grupo `freeze-<model_version_id>`, que se crea al fallar el `freeze` y se borra con un `freeze` exitoso o 409, o en una corrida **completa** en la que la versión ya no cumple la regla o ya no se evalúa (BR-U9-20; revisión del plan de tareas de U9, 2026-10-10); los grupos de versiones que ya no se evalúan se encuentran con `GET /api/v1/metrics` del Pushgateway y se borran hasta 16 por corrida (revisión del FD de U10, 2026-10-10, A6);
    - sin tasas de celdas insuficientes.
  - Diseño: BR-U9-07, 12, 20; P-U9-01, 02, 05; NFR-U9-03, 22.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/integration/test_clients.py tests/integration/test_publish.py` (dobles de U3, U4 y del Pushgateway):
    - cada llamada corta en su timeout;
    - 4 versiones → dos solicitudes de rangos (12 + 4) y `unattributable_invalid` tomado una sola vez;
    - `freeze` con 503 persistente → 4 intentos;
    - el grupo `freeze-<v>` persiste tras una corrida que falla antes del cálculo; se borra con un `freeze` exitoso, con un 409, y en una corrida completa en la que `v` ya no cumple la regla o ya no se evalúa;
    - una corrida fallida no borra `last_success`;
    - una versión que deja de evaluarse desaparece del grupo `run`;
    - 20 grupos `freeze-<v>` de versiones que ya no se evalúan → la corrida borra 16 y la siguiente, los 4 restantes; cada operación corta a los 5 s.

- [ ] **Paso 8 — `run`: la corrida completa**
  - Orden de P-U9-01:
    1. token;
    2. lectura (atraso del agregador e inválidas);
    3. cálculo de todas las versiones evaluadas;
    4. `freeze` en todas las que cumplan la regla, aunque falle una;
    5. publicación.
  - Razón de inválidas de la corrida (BR-U9-09) y motivos de falla `lectura`, `libreria`, `invalidas`, `agregador_atrasado`, `token` y `freeze`.
  - Decisiones humanas y tasa de apartamiento (BR-U9-14).
  - Diseño: BR-U9-08..14, 20; P-U9-01, 07; NFR-U9-01, 20, 21. Historias: US-302, US-303, US-308.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_run_machine.py tests/integration/test_run.py`:
    - PBT-U9-05 (stateful, con reactivaciones, Keycloak sin token y dos versiones con un `freeze` que falla solo en una), incluido el invariante del ciclo de vida de los grupos `freeze-<v>` contra un doble del Pushgateway que registra `PUT` y `DELETE` (revisión del Infrastructure Design de U10, 2026-10-10);
    - RT-2: conteos de la variante proxy → `freeze` con el atributo disparador; modelo base → sin `freeze` (US-303);
    - humana alta y modelo bajo → `rule_met{population="humana"}` = 1 y ninguna llamada a `freeze` (US-302);
    - tras el `freeze`, una medición de 1 pp → ninguna llamada (US-303);
    - inválidas al 0,5 % → corrida completa; al 1,5 % → fallida; decisión no atribuible → cuenta una vez en los dos lados;
    - agregador atrasado 45 min → fallida;
    - E1, E3, E4, E5 y E7 de P-U9-07 con dobles;
    - una corrida con 3 versiones y celdas densas dura < 2 min y mide su pico de memoria (NFR-U9-01, 04).

### Bloque D — Servicio HTTP

- [ ] **Paso 9 — `dashboard`, `freezes`, `compare` y la app**
  - `create_app` de U0 con:
    - `GET /v1/disparity` y `GET /v1/freezes` (`cumplimiento` y `cro`);
    - `GET /v1/freezes/{id}` (solo `cumplimiento`);
    - `POST /v1/source-comparisons` (scope `bias:compare`).
  - `dashboard`:
    - versión servible enviada por el BFF o, si no llega, la más reciente con datos;
    - caché LRU de 64 entradas y 15 min con *single-flight*;
    - `disclaimer` en toda respuesta;
    - log `disparity.viewed`.
  - `freezes`: `FreezeSummary` con `resolution?`; log `freeze_context.viewed`; 404 si no existe.
  - `compare`: valida las tablas (422) y devuelve `PrePostReport` ≤ 48 KiB con `truncated`.
  - Readiness y liveness solo del proceso; `preStop` de 5 s y uvicorn con `timeout_graceful_shutdown = 10`.
  - Diseño: BR-U9-17, 18, 19; P-U9-03, 05; NFR-U9-02, 12, 32, 33. Historias: US-304, US-306, US-307.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_compare.py tests/integration/test_app.py tests/integration/test_cache.py`:
    - PBT-U9-07;
    - toda respuesta lleva `disclaimer` y ningún texto pasa `contracts/tools/forbidden_phrases.py` con la lista única de U0 (BR-U0-94; US-307; revisión del FD de U10, 2026-10-10, B6);
    - con un `ConfigMap` de parámetros de prueba (umbral 7 pp, `n_min` 40, ventana 20 días, otro horario, W 2 h), `GET /v1/disparity` y el paquete de `GET /v1/freezes/{id}` informan esos cinco valores, no los de producción (BR-U9-13; revisión del FD de U10, 2026-10-10, A7);
    - al arrancar `uvicorn vectra_bias.app:app`, `vectra_bias.freeze_client` no está en `sys.modules`: la imagen es una sola (P-U9-05), así que se comprueba en el proceso además de import-linter (A7);
    - registro caído al arrancar → los pods quedan `Ready` y la consulta da 503 (NFR-U9-12; A7);
    - `GET /metrics` en 8081 expone las series HTTP y de la caché esperadas, sin etiquetas fuera de la allowlist (NFR-U9-41; A7);
    - una consulta servida desde la caché también emite `disparity.viewed` con el `principal_subject` del que consulta (NFR-U9-32; A7);
    - 10 consultas concurrentes con la misma llave → una sola lectura del registro; un error no queda en la caché;
    - paquete válido contra el esquema de U0 (US-304);
    - `compare_source` con un grupo fuera del catálogo → 422 (US-306);
    - un rol no permitido → 403 con `authz.denied`;
    - PBT-U0-07 en modo strict sobre los dos eventos de log;
    - registro caído → 503 sin datos parciales y circuito abierto tras 20 llamadas.

- [ ] **Paso 10 — Resumen del CronJob y del servicio**
  - Cobertura de ramas **100 %** en `freeze_rule`, `context` y `window`, y ≥ 95 % en el resto; `mutmut` en `freeze_rule`; PBT-U9-01..08 con el perfil `ci`.
  - Resumen en `aidlc-docs/construction/bias-monitoring/code/services.md`.
  - Diseño: NFR-U9-50, 51, 52.
  - Herramienta de cobertura: pytest-cov (coverage.py) con `--cov-branch`; el umbral por módulo lo comprueba `coverage report --include` para cada módulo al 100 % (revisión del FD de U10, 2026-10-10, B9).
  - **Aceptación**: `uv run pytest bias-monitoring/tests --cov=vectra_bias --cov-branch --cov-fail-under=95` y `uv run coverage report --include='*/freeze_rule.py,*/context.py,*/window.py' --fail-under=100`; `uv run mutmut run --paths-to-mutate bias-monitoring/src/vectra_bias/freeze_rule.py`.

### Bloque E — Despliegue y operación

- [ ] **Paso 11 — Dockerfile y cadena de suministro**
  - Una imagen con los dos puntos de entrada (`python -m vectra_bias.run` y `uvicorn vectra_bias.app:app`); base Python oficial pinneada por digest, `runAsNonRoot` y `readOnlyRootFilesystem`; sin numpy, scipy, pandas ni Fairlearn en la imagen.
  - Construida, escaneada, con SBOM y firmada por `supply-chain.yml` de U1.
  - Diseño: P-U9-05; NFR-U9-54.
  - **Aceptación**: `hadolint bias-monitoring/Dockerfile`; prueba sobre el SBOM: ni las tres dependencias de desarrollo directas (Fairlearn, pandas, numpy) ni sus transitivas scipy y scikit-learn en la imagen (revisión del FD de U10, 2026-10-10, B9).

- [ ] **Paso 12 — Chart, parámetros, cuota y flujos**
  - **Servicio**:
    - `Deployment` de 2 réplicas fijas con `vectra.io/hpa-exempt`, `Service`, `PodDisruptionBudget`, spread por zona y `vectra-normal`;
    - `ServiceAccount` `bias-monitoring-service`, su `ExternalSecret` y `ServiceMonitor`.
  - **CronJob**:
    - `schedule` tomado de `values-monitoring-policy.yaml` (hoy `"2,17,32,47 * * * *"`, en UTC; nunca escrito en la plantilla; revisión del plan de tareas de U9, 2026-10-10), `Forbid`, `startingDeadlineSeconds: 300`, `backoffLimit: 0`, `activeDeadlineSeconds: 600`, `vectra-high`;
    - anotación explícita del sidecar nativo;
    - `ServiceAccount` `bias-monitoring-job` y su `ExternalSecret`.
  - **`values-monitoring-policy.yaml`**:
    - línea de `CODEOWNERS` para el equipo de cumplimiento en el **monorepo** (`bias-monitoring/chart/values-monitoring-policy.yaml`) y en el repositorio GitOps (revisión del FD de U10, 2026-10-10, A5);
    - regla de `conftest` con los rangos de INF-U9-03: horario con intervalo de 5, 10 o 15 min y desfase de 1 a 4 min, W ≥ 4 × el intervalo y `activeDeadlineSeconds` ≤ el intervalo en segundos (A6).
  - **Job `x04-probe-<runId>`** (U12 INF-U12-02; Infrastructure Design de U12, 2026-10-10): solo con los values de kind y `probes.runId`; identidad `bias-monitoring-job`; llama a `POST /v1/models/{id}/approval` de governance y termina con éxito solo con el 403 de Linkerd; `backoffLimit: 0`, sidecar nativo, **sin** `ttlSecondsAfterFinished` (se poda al cambiar `probes.runId`, con un sync con prune); sus pods llevan la etiqueta `vectra.io/workload: bias-monitoring-job` y la `ServiceAccount` `bias-monitoring-job`, para que la `NetworkPolicy` de F27 los deje pasar y el rechazo sea el 403 de Linkerd. `conftest`: no aparece con los values de staging ni de producción; los pods del CronJob y de `x04-probe` llevan la etiqueta (revisión del Infrastructure Design de U12, 2026-10-10).
  - Aporte de U9 a la cuota de `vectra-app` en `platform/policies/quotas/` de U1 (INF-U9-01).
  - **Flujos** en `platform/network/flows.yaml`: F14, F25, F26, F27 (solo desde los pods del CronJob), F50, F60 y F106. La `AuthorizationPolicy` de `freeze` en governance la entrega U4 (Paso 16 de su plan).
  - Diseño: INF-U9-01..04; NFR-U9-10, 11, 13, 30, 34; BR-U9-13.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test bias-monitoring/policies/conftest/` (réplicas, exención, PDB, spread, PriorityClass, horario, plazos, `backoffLimit`, anotación del sidecar, rangos de los parámetros dentro y fuera); `kyverno test` de U1 con la exención; `conftest test platform/policies/quotas/`; `uv run python platform/network/generate.py --check`; `CODEOWNERS` del monorepo contiene la línea del archivo; fixtures de `conftest` con intervalos de 6 y 12 min → fallan, y con 5 min y `activeDeadlineSeconds: 600` → falla.

- [ ] **Paso 13 — Alertas, runbooks y dashboard**
  - `PrometheusRule` como plantilla del chart con las alertas de P-U9-06; los umbrales de `MonitoreoSesgoDetenido` salen de `stale_after` (W y 2W).
  - Runbooks de las cuatro alertas. El de `BiasInvalidEntries` explica cómo silenciar una entrada conocida hasta que salga de la ventana; el de `BiasFreezeFailed` explica cuándo se cierra solo el grupo por versión (BR-U9-20); el de `MonitoreoSesgoDetenido` dice que durante una reconstrucción del agregador de U3 (runbook `monitoring-rebuild`) la alerta es **esperada** y viene silenciada por ese runbook con vencimiento (revisión del plan de tareas de U9, 2026-10-10).
  - Dashboard `observability/dashboards/bias.json` con la leyenda fija «mide y alerta, no certifica» (INF-U9-05).
  - Diseño: BR-U9-21, 22; P-U9-06; INF-U9-05; NFR-U9-40, 41. Historias: US-307, US-308.
  - **Aceptación**:
    - `helm template` con `stale_after` = 1 h y = 2 h, y con horarios de 15 y 5 min (el `for` de `DisparidadDecisionHumana` = 30 y 10 min; revisión del Infrastructure Design de U10, 2026-10-10), + `promtool test rules` generado para cada valor (los dos lados de W y 2W, la serie ausente, una sola corrida de `DisparidadDecisionHumana` sin disparar, `BiasFreezeFailed` que sigue tras una corrida fallida y se apaga con un `freeze` exitoso);
    - `uv run python platform/tests/test_runbooks.py --root bias-monitoring`;
    - prueba sobre `bias.json`: leyenda presente, sin frases prohibidas (`contracts/tools/forbidden_phrases.py`, BR-U0-94; precisado el 2026-10-10 por U10 FD, Q8) y sin consultas que muestren tasas de celdas insuficientes.

- [ ] **Paso 14 — Applications, especificación de carga y trazabilidad**
  - Application en la wave 5 (servicio y CronJob) por entorno y sin auto-sync.
  - Script k6: 10 usuarios de consola con los umbrales de NFR-U9-02.
  - Trazabilidad de cada BR-U9 a una prueba.
  - Diseño: P-U1-12; NFR-U9-02.
  - **Aceptación**: `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `k6 inspect bias-monitoring/tests/load/dashboard.js`; `uv run python platform/tests/test_traceability.py --unit bias-monitoring --all`.

- [ ] **Paso 15 — Workflow de CI de U9** (revisión del plan de tareas de U9, 2026-10-10)
  - `.github/workflows/bias-monitoring.yml`, en cada PR que toca `bias-monitoring/`:
    - `uv sync --frozen`, ruff, mypy e import-linter;
    - pruebas con el perfil `ci` y la semilla impresa, guardando `.hypothesis/` como artefacto;
    - cobertura con los umbrales por módulo;
    - `helm template`, `conftest`, `promtool` y `kyverno test` de los Pasos 12 y 13;
    - `forbidden_phrases.py` sobre los textos de la API y `bias.json`.
  - **Regla de rutas**: si el PR toca `disparity/src/vectra_disparity/stats.py`, `disparity.py` o `src/vectra_bias/freeze_rule.py`, corre además `mutmut` y la simulación estadística (`-m simulation`).
  - **Workflow nocturno** (`schedule`): simulación y `mutmut` completos sobre `main`; si falla, abre un issue.
  - Reutiliza los workflows de U1 (`tests.yml`, `supply-chain.yml`, `policies.yml`).
  - Diseño: NFR-U9-50, 51, 52, 53.
  - **AUTONOMIA-01**: el workflow no tiene pasos `kubectl`, `helm install`/`upgrade` ni `terraform apply`; `forbidden-steps.yml` de U1 lo cubre.
  - **Aceptación**: `actionlint .github/workflows/bias-monitoring.yml`; `! grep -E "kubectl|helm (install|upgrade)|terraform apply" .github/workflows/bias-monitoring.yml` (revisión del FD de U10, 2026-10-10, B9); una prueba sobre el YAML: la regla de rutas lista los tres archivos y el disparador `schedule` existe.

### Bloque F — Verificación en kind (con aprobación humana)

- [ ] **Paso 16 — Puerta de aprobación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–15 aprobado por un humano, con U1–U4 instalados en kind y un modelo activo.
  - El operador ejecuta, con evidencia:
    1. suite de conectividad de U1: servicio → `freeze` → denegado por Linkerd; CronJob → `freeze` → permitido; servicio → Pushgateway → denegado;
    2. E1–E7 de P-U9-07 con las unidades reales. E2 se prueba suspendiendo el agregador de U3; E6, con la demostración RT-2 cuando exista U12;
    3. RT-2 (cuando existan U5, U6, U7 y U12): latencia de detección p95 ≤ 30 min y paquete completo en el evento `freeze`, con las `data_sources` y la `initial_disparity` que agrega governance (NFR-U9-01; BR-U9-16);
    4. prueba de carga del dashboard con 10 usuarios (NFR-U9-02);
    5. una corrida mide su duración y su pico de memoria con el volumen de la demostración (NFR-U9-04).
  - Diseño: BR-U9-16; P-U9-01, 06, 07; INF-U9-02, 04; NFR-U9-01, 02, 04, 20. Historias: US-303, US-308.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con el comando, la salida y el resultado esperado frente al obtenido.

### Bloque G — Cierre

- [ ] **Paso 17 — Repositorio, migraciones y frontend: N/A**
  - U9 no tiene base de datos, migraciones ni interfaz; la consola y el embebido del dashboard son de U10.
  - **Aceptación**: `test ! -d bias-monitoring/migrations && test ! -d bias-monitoring/frontend`.

- [ ] **Paso 18 — Cierre de la unidad**
  - **Aceptación**: `make -C bias-monitoring check`, que corre en orden las verificaciones estáticas, las propiedades, la simulación (con la marca `simulation`, opcional en el PR salvo que cambien `stats` o `freeze_rule`) y las pruebas de integración de los Pasos 1–15 y termina en 0. Las de kind (Paso 16) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

| Historia | Pasos |
|---|---|
| US-301 | 4 |
| US-302 | 8 |
| US-303 | 6, 8, 16 |
| US-304 | 6, 9 |
| US-306 | 9 |
| US-307 | 9, 13 |
| US-308 | 8, 13, 16 |

| Diseño | Pasos |
|---|---|
| BR-U9-01..22 | 3, 4, 6, 7, 8, 9, 12, 13, 16 |
| NFR-U9-01..54 | 1, 2, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 |
| P-U9-01..07 | 1, 2, 4, 7, 8, 9, 11, 13, 16 |
| INF-U9-01..05 | 2, 12, 13, 16 |

| Propiedad | Pasos |
|---|---|
| PBT-U9-01 | 4, 10 |
| PBT-U9-02 | 4 |
| PBT-U9-03 | 4 |
| PBT-U9-04 | 6 |
| PBT-U9-05 | 8 |
| PBT-U9-06 | 4 |
| PBT-U9-07 | 9 |
| PBT-U9-08 | 6 |

## 4. Cumplimiento de extensiones (plan de tareas U9)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Ningún paso aplica ni sincroniza; los escenarios con clúster los ejecuta el operador (Paso 16) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-04 | Cumple | Solo el CronJob congela, con tres barreras (Pasos 1, 7, 12, 16); nunca reactiva (Paso 8) |
| AUTONOMIA-05 | Cumple | Supresión de celdas chicas en la librería (Paso 4); sin egress (Paso 12) |
| SECURITY-03 / 06 / 08 / 11 / 12 / 14 / 15 | Cumple | Pasos 4, 7, 8, 9, 12, 13 (SECURITY-11: tablas manipuladas en `compare_source`, servicio que intenta `freeze`, parámetros fuera de rango) |
| RESILIENCY-01 / 04 / 05 / 07 / 08 / 09 / 10 / 14 / 15 | Cumple | Pasos 7, 8, 9, 12, 13, 15, 16 |
| PBT-01..10 | Cumple | Pasos 4, 6, 8 y 9 (PBT-U9-01..08), Paso 10 (perfil `ci`) y pruebas de ejemplo en los Pasos 4, 6, 7, 8 y 9 |
