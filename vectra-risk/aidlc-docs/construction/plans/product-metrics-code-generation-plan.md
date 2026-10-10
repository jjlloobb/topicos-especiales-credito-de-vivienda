# Plan de tareas (Code Generation Part 1) — U11 `product-metrics`

**Este plan es la única fuente de verdad para generar el código de U11.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U11. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U11 `product-metrics`: proceso `asyncio` sin API de negocio que lee la proyección `metrics` del registro, calcula las métricas de producto en memoria y las publica en `/metrics`; reglas de Prometheus y dashboards como código |
| Historias (dueña) | US-503 (North Star), US-504 (métrica de ruido con alerta), US-505 (métricas operativas y de producto) |
| Ubicación | `vectra-risk/product-metrics/` y Applications en `vectra-risk-gitops` |
| Datos propios | Ninguno: estado en memoria, reconstruido con la pasada completa al arrancar |
| Depende de | U0 (`vectra_common.ops_server` con predicado de readiness, `process.init`, `deps.call`, `FailClosedCause.category`, tipos de la proyección), U1 (malla, cuotas, `flows.yaml`, Job `grafana-folder-permissions`, carpeta de operación, exención de HPA), U2 (cliente `product-metrics` con un solo scope, equipos de Grafana), U3 (proyección `metrics` con la recomendación resuelta, `first_evaluation` y paginación por `seq`), U7 (`vectra_recommendations_total`, `vectra_scoring_failclosed_total`, y la copia de `received_at`, `channel`, `attempt` y `first_evaluation` al payload), U8 (`received_at` y `first_evaluation` en la `ScoringRequest`) |
| Lo consumen | CRO, cumplimiento e ingeniería de riesgo en Grafana; U12 (demostración del dashboard) |

**Diseño de entrada:**
- Functional Design: `construction/product-metrics/functional-design/` (BR-U11-01..14, PBT-U11-01..07).
- NFR Requirements: `construction/product-metrics/nfr-requirements/` (NFR-U11-01..42).
- NFR Design: `construction/product-metrics/nfr-design/` (P-U11-01..06, E1–E8).
- Infrastructure Design: `construction/product-metrics/infrastructure-design/` (INF-U11-01..06).

**AUTONOMIA-01:** las verificaciones estáticas, las propiedades, la prueba de volumen a 10
veces con el doble de U3 y las pruebas de integración corren en CI. Las que necesitan el
clúster las ejecuta **un operador en kind** después de un PR aprobado (Paso 16).

**Dobles hasta que existan las unidades reales:** en CI, un doble de U3 implementa la
proyección `metrics` (filtros, paginación por `seq`, recomendación resuelta) y un emisor de
token de prueba sustituye a Keycloak. Las pruebas de kind usan las unidades reales.

### Estructura de destino

```text
vectra-risk/product-metrics/
|-- Makefile  pyproject.toml  .importlinter
|-- src/vectra_product/
|   |-- config.py  params.py              # constantes del ciclo y parámetros de cumplimiento
|   |-- model.py                          # tipos con __slots__ y códigos enteros
|   |-- compute.py  noise.py              # puros
|   |-- state.py  reader.py  scheduler.py  collector.py  main.py
|-- tools/gen_rules.py
|-- chart/   templates/  values-{prod,staging,kind}.yaml  values-product-metrics-policy.yaml
|-- policies/conftest/
|-- observability/  rules/  rules/tests/  runbooks/  dashboards/{product.json, operation.json}
`-- tests/  unit/ property/ integration/ doubles/ volume/
```

---

## 2. Pasos

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `product-metrics/`**
  - Directorios de §1; `pyproject.toml` como miembro del workspace de `uv` (depende de `vectra_contracts` y `vectra_common`).
  - import-linter: `compute`, `noise` y `model` sin E/S; ningún módulo importa `httpx` fuera de `vectra_common.deps`; ningún módulo importa FastAPI.
  - Diseño: NFR-U11-21; tech-stack.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config product-metrics/.importlinter && make -C product-metrics check` sobre el esqueleto.

- [ ] **Paso 2 — Constantes y parámetros**
  - `config.py`: ciclo de 5 min, 02:30 UTC + desfase de 0 a 10 min, plazo de 75 min, reintentos de la completa (15 min, 6 veces), timeout de 5 s, página de 1 000, parámetros del breaker de `deps.call` en modo `consecutive_failures` de U0 (`consecutive_failures=3`, `open_for=60s`, `close_after=1`; pendientes consolidados, 2026-10-10), ventanas de 35 días y 6 meses.
  - `params.py`: lee el `ConfigMap` de `values-product-metrics-policy.yaml` (F, S, N y targets) y falla al arrancar con un valor fuera de rango.
  - Diseño: BR-U11-09, 11; NFR-U11-04, 09; P-U11-01, 02.
  - **Aceptación**: `uv run pytest product-metrics/tests/unit/test_config.py test_params.py` (valores de la tabla; rangos dentro y fuera; ninguna constante desde variables de entorno).

### Bloque B — Lógica pura y estado

- [ ] **Paso 3 — `model`, `compute` y `noise`**
  - `model`: decisión con `__slots__`, códigos enteros del catálogo de U0 y cadenas internadas (P-U11-04).
  - `compute(entries, params, now) -> BusinessMetrics`: atribución por la recomendación resuelta, North Star con desglose, sostenida, tasa de consulta, tiempo de originación con `first_evaluation`, no atribuibles, exclusiones (catálogo, `actor_role ≠ analista`, `decided_at > recorded_at + 5 min`) y `degraded`; periodos `day`, `30d`, `month_to_date` y los 6 `month`; conteos con todos los cortes y razones solo totales o por un corte.
  - `noise.days_below_floor`.
  - Diseño: BR-U11-01..10; domain-entities §3. Historias: US-503, US-504, US-505.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/property/test_compute.py tests/property/test_noise.py tests/unit/test_compute_examples.py`: PBT-U11-01, 03, 04, 06 y 07; las pruebas de ejemplo de business-logic-model §3 que no dependen de E/S.

- [ ] **Paso 4 — `state` y `reader`**
  - `reader`: `GET /v1/entries?projection=metrics&entry_type=human_decision&…&seq_after=…&limit=1000` con `deps.call` y su breaker en modo `consecutive_failures` (U0 NFR-U0-23 (i); no hay breaker propio en U11; pendientes consolidados, 2026-10-10); una página a la vez bajo un `asyncio.Lock` único; nunca avanza `last_seq` más allá de la última página confirmada.
  - `state`: pasada completa en una sola lectura desde el día 1 del sexto mes cerrado − 1 día, plegando cada página en los contadores por mes y guardando solo las decisiones de 35 días; estado nuevo construido aparte y reemplazo atómico; después, lectura incremental desde el `last_seq` de la pasada.
  - Diseño: BR-U11-11; P-U11-01, 02, 04; NFR-U11-01, 02, 09..12.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/property/test_state_machine.py tests/integration/test_reader.py` (doble de U3):
    - PBT-U11-02 (stateful, con pasadas intercaladas y fallos a mitad);
    - el doble cuenta las conexiones simultáneas y falla si ve 2;
    - una página fallida no avanza `last_seq`; 3 fallos seguidos → breaker abierto; 1 éxito en semiabierto → cerrado;
    - una entrada de 40 días va a su contador de mes y no al estado de 35 días.

- [ ] **Paso 5 — Resumen de la lógica**
  - Cobertura de ramas **100 %** en `compute` y `noise`; `mutmut` en `compute` y `noise`.
  - Resumen en `aidlc-docs/construction/product-metrics/code/logic.md`.
  - Diseño: NFR-U11-30, 31.
  - **Aceptación**: `uv run pytest product-metrics/tests/unit product-metrics/tests/property --cov=vectra_product.compute --cov=vectra_product.noise --cov-branch --cov-fail-under=100`; `uv run mutmut run --paths-to-mutate product-metrics/src/vectra_product/compute.py,product-metrics/src/vectra_product/noise.py`.

### Bloque C — Proceso y publicación

- [ ] **Paso 6 — `scheduler`, `collector` y `main`**
  - `scheduler`: pasada completa al arrancar y diaria; ciclo incremental cada 5 min, omitido (y contado) si el candado está tomado; plazo y reintentos de la pasada.
  - `collector`: `Collector` de `prometheus-client` sobre la instantánea inmutable; sin instantánea, sin series de producto; series de operación siempre.
  - `main`: `vectra_common.process.init(kind="service")`, `ops_server` con el **predicado de readiness** (instantánea o breaker abierto o semiabierto), apagado con `SIGTERM` (no toma ciclos nuevos, termina la página en curso).
  - Allowlist de series y etiquetas de domain-entities §5 (producto y operación).
  - Diseño: P-U11-02, 03; INF-U11-01; NFR-U11-07, 08, 40.
  - **Aceptación**: `uv run pytest product-metrics/tests/integration/test_process.py tests/integration/test_collector.py`:
    - arranque con U3 caído → series de operación sí (sin `vectra_product_last_full_recompute_timestamp` hasta la primera pasada completa exitosa; pendientes consolidados, 2026-10-10), de producto no, `/readyz` 503 hasta que el breaker abre y 200 después; al cerrarse el breaker sin instantánea → 503;
    - primera pasada que vence su plazo de 75 min con U3 lento pero sin 3 fallos seguidos (reloj simulado) → `/readyz` 503 (revisión del plan de tareas de U11, 2026-10-10);
    - `SIGTERM` durante una pasada: no toma ciclos nuevos, termina la página en curso en ≤ 10 s, descarta la pasada a medias (el estado vigente queda intacto) y sale con código 0 (revisión del plan de tareas de U11, 2026-10-10);
    - desfase de la pasada diaria: con relojes simulados y semillas fijas, el desfase uniforme cae en [0, 600] s en 10 000 sorteos, el inicio entre las 02:30 y las 02:40 UTC, dos semillas fijas distintas dan desfases distintos y la misma semilla repite la secuencia; sin umbrales estadísticos (NFR-U11-04; revisión del plan de tareas de U11, 2026-10-10; prueba determinista, pendientes posteriores al cierre, 2026-10-10);
    - etiqueta `month`: las series con `period="month"` (North Star, desglose, sostenida y sus razones) la llevan con `AAAA-MM`; ninguna otra `period` la lleva; las de consulta de explicación no la tienen (pendientes posteriores al cierre, 2026-10-10);
    - reintentos de la pasada completa: con U3 fallando y reloj simulado, 6 reintentos cada 15 min y después ninguno hasta la del día siguiente, con el estado incremental intacto (NFR-U11-09; revisión del plan de tareas de U11, 2026-10-10);
    - un scrape durante el reemplazo → solo valores de un ciclo;
    - un ciclo durante la pasada → omitido y contado;
    - `/metrics` sin ninguna serie ni etiqueta fuera de la allowlist (PBT-U11-05);
    - PBT-U0-07 en modo strict sobre los logs.

- [ ] **Paso 7 — Pruebas de ejemplo del proceso y prueba de volumen**
  - Las pruebas de ejemplo de business-logic-model §3 que dependen de E/S (reinicio a mitad, registro caído 31 min, decisión sobre una recomendación de hace 60 días).
  - **Prueba de volumen** (INF-U11-06): el doble de U3 sirve 10 veces el volumen de NFR-U3-30 durante 7 meses, con la latencia de página del p95 de U3; se miden la duración de la pasada, el pico de memoria (`tracemalloc` y RSS) y la ausencia de lecturas simultáneas.
  - Diseño: NFR-U11-02, 03, 12, 13; P-U11-04.
  - **Aceptación**: `uv run pytest product-metrics/tests/integration/test_examples.py`; `uv run pytest product-metrics/tests/volume -m volume` (pasada ≤ 60 min; pico ≤ 70 % de 512 MiB; si se supera, se ajusta INF-U11-01 y el aporte a la cuota antes de seguir).

- [ ] **Paso 8 — Resumen del proceso**
  - Cobertura ≥ 90 % en el resto; resumen en `aidlc-docs/construction/product-metrics/code/process.md`.
  - **Aceptación**: `uv run pytest product-metrics/tests --cov=vectra_product --cov-branch --cov-fail-under=90`.

### Bloque D — Repositorio y frontend

- [ ] **Paso 9 — Repositorio, migraciones y frontend: N/A**
  - U11 no tiene base de datos ni interfaz propia; los dashboards son código de Grafana (Paso 13).
  - **Aceptación**: `test ! -d product-metrics/migrations && test ! -d product-metrics/frontend`.

### Bloque E — Despliegue y operación

- [ ] **Paso 10 — Imagen**
  - Python oficial por digest, `runAsNonRoot`, `readOnlyRootFilesystem`; construida, escaneada, con SBOM y firmada por `supply-chain.yml` de U1.
  - **Aceptación**: `hadolint product-metrics/Dockerfile`; el SBOM no contiene FastAPI.

- [ ] **Paso 11 — Chart, cuotas y flujos**
  - `Deployment` de 2 réplicas fijas con `vectra.io/hpa-exempt` y su justificación, `RollingUpdate` con `maxSurge: 1` y `maxUnavailable: 0`, `progressDeadlineSeconds: 4800`, PDB, spread por zona, `vectra-normal`, `terminationGracePeriodSeconds: 10`.
  - Sondas del `Deployment` (revisión del plan de tareas de U11, 2026-10-10): `livenessProbe` HTTP sobre `/healthz` y `readinessProbe` HTTP sobre `/readyz`, las dos en 8081; sin `startupProbe` larga (INF-U11-01).
  - `Service` solo con 8081 y `publishNotReadyAddresses: true`; `ServiceMonitor`.
  - Linkerd `Server` en 8081 y `AuthorizationPolicy` que admite solo la identidad de Prometheus (F60); las sondas del kubelet pasan por la autorización automática de sondas de Linkerd (INF-U11-04; revisión del plan de tareas de U11, 2026-10-10).
  - `ServiceAccount` con `automountServiceAccountToken: false`; `ExternalSecret` de la llave del cliente.
  - `ConfigMap` de `values-product-metrics-policy.yaml` sin `subPath` y con `checksum/config`; `CODEOWNERS` de producto y riesgo en el monorepo y en GitOps.
  - Aporte a la cuota de `vectra-app` (NFR-U11-14) en `platform/policies/quotas/` de U1.
  - Flujos F28, F50 y F60 en `platform/network/flows.yaml`, con los casos bloqueados de INF-U11-04.
  - Diseño: INF-U11-01..04; NFR-U11-05, 14, 20, 21.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test product-metrics/policies/conftest/` (réplicas, exención, estrategia, plazos, `livenessProbe` en `/healthz` y `readinessProbe` en `/readyz` en 8081 presentes, `publishNotReadyAddresses`, sin token montado, sin `subPath`, `checksum/config`, `Server` y `AuthorizationPolicy` de Linkerd en 8081 solo para Prometheus, rangos de los parámetros dentro y fuera; revisión del plan de tareas de U11, 2026-10-10); `kyverno test` de U1 (`require-hpa-bounds`); `conftest test platform/policies/quotas/`; `uv run python platform/network/generate.py --check`; `CODEOWNERS` con la línea del archivo.

- [ ] **Paso 12 — Reglas generadas y alertas**
  - `tools/gen_rules.py` genera, desde `vectra_contracts.catalog.FailClosedCause`, la regla `vectra:product_desync_failclosed:rate1h`, y desde la allowlist, las recording rules `:dedup`.
  - `PrometheusRule` del chart con `vectra:product_complete_response_ratio:1h` y `:1d`, las `:dedup` y las alertas de P-U11-06 (`RuidoExplicacion` con S del archivo; `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing`, cada una en dos reglas: edad con `for: 0` y ausencia con `up … unless on (pod)` y `for` de 30 min y 26 h, las dos sin disparar durante la pasada; pendientes posteriores al cierre, 2026-10-10). `GrafanaFolderPermissionsDrift` no va aquí: es de U1.
  - Diseño: BR-U11-06, 14; P-U11-05, 06; NFR-U11-06, 08, 32.
  - **Aceptación**: `uv run python product-metrics/tools/gen_rules.py --check`; `promtool test rules product-metrics/observability/rules/tests/*.yaml`:
    - cada alerta a los dos lados del umbral;
    - una réplica sin la serie y la otra con ella (las dos con `up = 1`) → `ProductMetricsStale` solo para la primera;
    - la pasada en curso → no dispara ninguna rama;
    - la rama de edad dispara al superar el umbral sin esperar un `for`; la de ausencia, solo tras su `for`;
    - la `PrometheusRule` de U11 tiene exactamente cuatro `alertname`;
    - réplica recién arrancada con U3 caído (`up = 1`, sin `vectra_product_last_full_recompute_timestamp`) → `ProductMetricsFullRecomputeMissing` no dispara al arrancar ni a las 25 h, y dispara por la rama de ausencia a las 26 h; con la serie en 0 dispararía de inmediato, por eso el `Collector` no la emite (pendientes consolidados, 2026-10-10);
    - dos réplicas idénticas → una sola `RuidoExplicacion`;
    - `vectra:product_complete_response_ratio:1h` con 98 y 2 → 0,98.

- [ ] **Paso 13 — Dashboards y runbooks**
  - `product.json` (carpeta `Vectra / Producto`): North Star con desglose, tasa de consulta con el piso y los días bajo el piso, sostenida con la nota de aproximación, originación con el target, respuesta completa y fail-closed, no atribuibles, excluidas y degradado; solo series `:dedup`; targets como líneas.
  - `operation.json` (carpeta de operación de U1): ciclo, entradas leídas, pasada, ciclos omitidos, breaker.
  - Runbooks `product-noise`, `product-metrics-degraded`, `product-metrics-stale`, `product-metrics-full-recompute-missing` y `product-metrics-parameter-change`.
  - Diseño: BR-U11-12, 13; INF-U11-05; NFR-U11-33, 41.
  - **Aceptación**: `uv run pytest product-metrics/tests/unit/test_dashboards.py` (ninguna referencia a series `vectra_product_*` crudas salvo en las dos alertas por réplica; ninguna razón calculada como promedio de razones; la nota de aproximación y «sin target acordado» presentes); `uv run python contracts/tools/forbidden_phrases.py product-metrics/observability/dashboards/*.json`; `uv run python platform/tests/test_runbooks.py --root product-metrics`.

- [ ] **Paso 14 — Workflow de CI**
  - `.github/workflows/product-metrics.yml` en cada PR que toca `product-metrics/` o `contracts/` (por el catálogo de causas): `uv sync --frozen`, ruff, mypy, import-linter, pruebas con perfil `ci` y semilla impresa, cobertura, `gen_rules.py --check`, `promtool`, `helm template`, `conftest`, pruebas de dashboards; la prueba de volumen en el workflow nocturno, con `mutmut` y el perfil `nightly`.
  - **AUTONOMIA-01**: ningún paso `kubectl`, `helm install`/`upgrade` ni `terraform apply`.
  - **Aceptación**: `actionlint .github/workflows/product-metrics.yml`; `! grep -E "kubectl|helm (install|upgrade)|terraform apply" .github/workflows/product-metrics.yml`; una prueba sobre el YAML: el disparador incluye `contracts/**`.

- [ ] **Paso 15 — Application y trazabilidad**
  - Application en la wave 5 por entorno, sin auto-sync.
  - Trazabilidad de cada BR-U11 a una prueba.
  - **Aceptación**: `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `uv run python platform/tests/test_traceability.py --unit product-metrics --all`.

### Bloque F — Verificación en kind (con aprobación humana)

- [ ] **Paso 16 — Puerta de aprobación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–15 aprobado por un humano, con U1–U3, U7 y U8 instalados en kind y los datos de demostración de U12: 2 000 casos `normal` decididos (U12 BR-U12-06 y plan, Paso 6; pendientes consolidados, tercera tanda, 2026-10-10).
  - El operador ejecuta, con evidencia:
    1. la suite de conectividad de U1 con los casos de INF-U11-04, incluido `/readyz` del kubelet;
    2. E1–E8 de P-U11 §3 con las unidades reales;
    3. un rollout con U3 sano: en ningún momento faltan las series `:dedup` de producto; un rollout con U3 caído: termina sin esperar;
    4. los permisos de las carpetas con los usuarios de U2 (`ingeniero-1`, `operacion-1`, `analista-1`, `cro-1`, `cumplimiento-1`);
    5. el día siguiente a las 2 000 decisiones del conductor de U12 (U12 BR-U12-06): North Star, sostenida, tasa de consulta y `ProductMetricsStale` con datos reales. `RuidoExplicacion` necesita S días seguidos bajo el piso, que kind no puede simular (`decided_at` lo pone case-service), así que se verifica con `promtool` y con la prueba con reloj simulado de los Pasos 3 y 12, no aquí (FD de U12, 2026-10-10).
  - Diseño: P-U11-02, 06; INF-U11-01, 04..06; BR-U11-13. Historias: US-503, US-504, US-505.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con el comando, la salida y el resultado esperado frente al obtenido.

### Bloque G — Documentación y cierre

- [ ] **Paso 17 — Documentación**
  - `product-metrics/README.md`: qué mide cada métrica y qué no (la nota de aproximación de la sostenida), parámetros y targets **[INTERNO]**, ciclo de lectura, deduplicación, readiness y runbooks.
  - **Aceptación**: `test -s product-metrics/README.md`; `platform/tests/test_links.py`.

- [ ] **Paso 18 — Cierre de la unidad**
  - **Aceptación**: `make -C product-metrics check`, que corre en orden las verificaciones estáticas, las propiedades, las pruebas de integración y de reglas de los Pasos 1–15 y termina en 0. La prueba de volumen corre en el workflow nocturno; las de kind (Paso 16) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

| Historia | Pasos |
|---|---|
| US-503 (North Star) | 3, 6, 13, 16 |
| US-504 (ruido y alerta) | 3, 12, 13, 16 |
| US-505 (métricas operativas y de producto) | 3, 7, 12, 13, 16 |

| Diseño | Pasos |
|---|---|
| BR-U11-01..10 | 3 |
| BR-U11-11 | 2, 4, 6 |
| BR-U11-12, 13 | 13, 16 |
| BR-U11-14 | 12 |
| NFR-U11-01..42 | 2, 4–8, 10–16 |
| P-U11-01..06 | 2, 4, 6, 7, 12, 13, 16 |
| INF-U11-01..06 | 7, 11, 13, 16 |

| Propiedad | Pasos |
|---|---|
| PBT-U11-01, 03, 04, 06, 07 | 3 |
| PBT-U11-02 | 4 |
| PBT-U11-05 | 6 |

## 4. Cumplimiento de extensiones (plan de tareas U11)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Ningún paso aplica ni sincroniza; el rollout espera solo por readiness; los escenarios con clúster los ejecuta el operador (Paso 16) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-03 / 05 | Cumple | Casos bloqueados y sin egress (Pasos 11, 16) |
| SECURITY-03 / 06 / 08 / 11 / 12 | Cumple | Pasos 6, 11, 13, 16 |
| RESILIENCY-01 / 05 / 07 / 08 / 09 / 10 / 14 / 15 | Cumple | Pasos 4, 6, 7, 11–13, 16 |
| PBT-01..10 | Cumple | PBT-U11-01..07 (Pasos 3, 4, 6), perfiles `ci` y `nightly` (Paso 14) y pruebas de ejemplo (Pasos 3, 7) |
