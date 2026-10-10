# Plan de tareas (Code Generation Part 1) — U12 `system-verification`

**Este plan es la única fuente de verdad para generar el código de U12.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U12. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U12 `system-verification`: herramientas de verificación que corren **fuera** del clúster (simulador, conductor de decisiones, escenarios RT y X, carga, demos e informe) |
| Historias (dueña) | US-609 |
| Verifica de extremo a extremo | US-101, 106, 109, 111, 303, 305, 603, 604 (mapa de domain-entities §4.2) y las demos de US-304, 503, 504 y 505 |
| Ubicación | `vectra-risk/system-verification/`; no hay Applications ni recursos en el clúster |
| Datos propios | Ninguno en el clúster; evidencias en el monorepo por PR |
| Depende de | U0 (`vectra_contracts`), U1 (suite de conectividad, binding K16, F07 desde fuera, F111), U2 (`channel-simulator`, `verification-reader`, usuarios sintéticos `analista-1`, `analista-2`, `ingeniero-1`, `cro-1`, `cumplimiento-1`), U3 (`x06-probe`, proyecciones `metrics` y `monitoring_freezes`; la `monitoring` está retirada, revisión de coherencia entre unidades, 2026-10-10), U4 (reactivación por el BFF en RT-2), U6 (digests de los `InferenceService`), U5 (partición `test` y manifiesto adversarial), U7, U8 (Job de RT-5, BFF de casos, scripts k6), U9 (`x04-probe`), U10 (BFF y perfil de carga), U11 (métricas y dashboard) |

**Diseño de entrada:**
- Functional Design: `construction/system-verification/functional-design/` (BR-U12-01..13, PBT-U12-01..04, mapa historia → evidencias).
- NFR Requirements: `construction/system-verification/nfr-requirements/` (NFR-U12-01..50).
- NFR Design: SKIP.
- Infrastructure Design: `construction/system-verification/infrastructure-design/` (INF-U12-01..05).

**AUTONOMIA-01:** U12 no aplica nada al clúster. Las pruebas de sus componentes corren en CI con
dobles. La verificación real la ejecuta **un operador en kind** después de un PR aprobado
(Paso 18), y los cambios que necesita (Jobs de prueba, artefacto alterado, modelo proxy) entran
por PRs preparados y syncs manuales.

### Estructura de destino

```text
vectra-risk/system-verification/
|-- Makefile  pyproject.toml  .importlinter  Dockerfile
|-- src/vectra_verification/
|   |-- guard.py  credentials.py  evidence.py  manifest.py     # barrera, credenciales en memoria, filtro
|   |-- sampler.py  report.py  story_map.py  rt2_latency.py    # puros
|   |-- clients/   gateway.py  bff.py  registry.py  prom.py  loki.py  k8s_read.py
|   |-- simulator.py  driver.py
|   |-- scenarios/  rt1.py rt2.py rt3.py rt4.py rt5.py x_network.py x_behavior.py logs_pii.py case_size.py
|   |-- load/       capacity.py  run.py
|   `-- cli.py                                                   # secciones
|-- report/story-map.yaml
|-- demos/   journey-7-3.md  journey-7-4.md  rt-5.md  dashboard.md  verify/*.sh
|-- evidence/                                                    # una carpeta por verificación (PR)
`-- tests/   unit/ property/ integration/ doubles/ fixtures/
```

---

## 2. Pasos

### Bloque A — Estructura y barreras

- [ ] **Paso 1 — Esqueleto y prueba de comandos de `kubectl`**
  - Directorios de §1; `pyproject.toml` como miembro del workspace (depende de `vectra_contracts`; **no** de `vectra_common`).
  - import-linter: `sampler`, `report`, `story_map` y `rt2_latency` sin E/S.
  - Prueba estática: el código y los guiones solo invocan `kubectl` con `get`, `auth can-i`, `logs` y `port-forward`; cualquier `exec`, `apply`, `create`, `delete`, `patch`, `scale`, `edit` o `rollout` (y `argocd app sync`) → falla.
  - Diseño: NFR-U12-01, 43; INF-U12-02.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config system-verification/.importlinter`; `uv run pytest system-verification/tests/unit/test_kubectl_verbs.py` (un fixture con `kubectl apply` → falla).

- [ ] **Paso 2 — Barrera de entorno, credenciales y filtro de evidencias**
  - `guard`: lista de `issuer` y hosts de kind y staging; secciones permitidas por entorno (staging: `decisions` ≤ 100, lectura de `u11`, `report`); `decisions` no empieza después de las 23:00 UTC.
  - `credentials`: lee del Vault de kind (o la bóveda de staging) con la sesión del operador, en las rutas que usa ESO, la llave de `channel-simulator` y de `verification-reader` y las contraseñas y semillas TOTP de los usuarios sintéticos; solo en memoria; TOTP con `pyotp`.
  - `evidence`: filtro que quita `Authorization`, tokens, cookies y semillas; falla si una salida contiene un JWT o una semilla.
  - Diseño: NFR-U12-03, 04, 05, 32; INF-U12-01.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_guard.py test_credentials.py test_evidence_filter.py`: `issuer` o host de producción simulados → error y cero solicitudes; `rt2` en staging → se niega; `decisions` a las 22:30 UTC con reloj simulado → se niega; ningún archivo escrito con credenciales; evidencia con un JWT → la generación falla.

### Bloque B — Lógica pura

- [ ] **Paso 3 — `sampler`, `rt2_latency`, `story_map` y `report`**
  - `sampler`: muestra `normal` y `stratified` (≥ 30 por celda en `region` × `estrato`), determinista con semilla; informa las celdas que no alcanzan.
  - `rt2_latency`: inicio = menor `recorded_at` de las `recommendation` del lote; fin = `recorded_at` del `freeze`; `passed` ≤ 1 800 s.
  - `story_map`: carga `report/story-map.yaml` y falla ante una historia sin fila o una evidencia desconocida.
  - `report`: `VerificationReport` desde las evidencias y el manifiesto (sin evidencia o con hash distinto → `no ejecutado`; `expected ≠ obtained` → `falla`; historias según el mapa); encabezado con el límite del manifiesto (NFR-U12-21).
  - Diseño: BR-U12-01, 06, 07, 11, 13; domain-entities §3, §4; NFR-U12-11, 20, 21.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_sampler.py tests/property/test_report.py tests/property/test_rt2_latency.py tests/unit/test_story_map.py`: PBT-U12-01, 02 y 04; las pruebas de ejemplo de business-logic-model §3 del informe y de la latencia.

- [ ] **Paso 4 — Resumen de la lógica pura**
  - Cobertura de ramas **100 %** en `report` y `sampler`; `mutmut` en `report`.
  - Cobertura de ramas **≥ 85 %** en el resto del paquete (NFR-U12-40): se comprueba en el Paso 16, cuando existen los clientes y los escenarios (pendientes posteriores al cierre, 2026-10-10).
  - Resumen en `aidlc-docs/construction/system-verification/code/logic.md`.
  - **Aceptación**: `uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100`; `uv run mutmut run --paths-to-mutate system-verification/src/vectra_verification/report.py`.

### Bloque C — Clientes, simulador y conductor

- [ ] **Paso 5 — Clientes de lectura y del gateway**
  - `gateway` y `bff`: `httpx` con la cabecera de escenario de U8 y un `traceparent` con el prefijo de la corrida.
  - **Login y step-up sin navegador visible** (revisión del plan de tareas de U12, 2026-10-10): el BFF no hace el flujo OIDC, lo hace el cliente público `vectra-console` (U2), y Keycloak solo ofrece Authorization Code + PKCE (sin *password grant*). La herramienta actúa como ese cliente:
    1. genera `state`, `nonce` y `code_verifier`;
    2. abre la URL de autorización (`prompt=login`, `max_age=0`, `acr_values=mfa` para el step-up) en **Chromium sin interfaz con Playwright**, que llena el formulario de Keycloak con la contraseña y el código TOTP calculado con `pyotp`;
    3. intercepta la navegación al `redirect_uri` registrado (`/callback` o `/stepup-callback`) **antes** de cargar la SPA, y toma de la URL `code` y `state`;
    4. valida que `state` coincida, canjea `code` con el `code_verifier` en el endpoint de token y valida el `nonce` y `acr = mfa` del ID token.

    Los tokens solo quedan en memoria; el contexto de Playwright se descarta tras cada login.
  - **Reuso de TOTP** (pendientes posteriores al cierre, 2026-10-10): Keycloak rechaza un código TOTP ya usado en la misma ventana de 30 s. La herramienta guarda en memoria, por usuario, la ventana del último código usado, y antes de un nuevo login o step-up del mismo usuario (por ejemplo, dos reactivaciones seguidas de `cumplimiento-1` en RT-2) espera a la ventana siguiente. El mismo mecanismo sirve para el login normal de los analistas y para el step-up de `cumplimiento-1` en la reactivación de RT-2.
  - **Aceptación del login**: `uv run pytest system-verification/tests/integration/test_oidc_headless.py` contra un Keycloak de Testcontainers con el realm de kind: login de `analista-1` → token con su rol; step-up de `cumplimiento-1` → `acr = mfa` y `auth_time` reciente; un `state` alterado → error sin canje; ningún token ni contraseña en disco.
  - `registry`: por `kubectl port-forward` a **un pod de** `decision-registry-service` (`pod/<nombre>`, elegido con `kubectl get pods -l …`; nunca `svc/…`, INF-U12-03; pendientes consolidados, segunda tanda, 2026-10-10), con el token de `verification-reader` (`registry:read:metrics` y `registry:read:monitoring`).
  - `prom` y `loki`: por `port-forward`, sus APIs de lectura.
  - `k8s_read`: envoltorio de `kubectl get`, `logs`, `auth can-i` y `port-forward` (lo único que el Paso 1 admite).
  - Diseño: INF-U12-03; NFR-U12-50.
  - **Aceptación**: `uv run pytest system-verification/tests/integration/test_clients.py` con dobles (cada solicitud lleva la cabecera y el prefijo; el cliente del registro manda el token de `verification-reader`; un `port-forward` caído → error claro, sin reintento silencioso).

- [ ] **Paso 6 — Simulador y conductor de decisiones**
  - `simulator`: escenarios `normal`, `stratified`, `rt1`, `rt4` desde U5 (partición `test` y manifiesto adversarial), con `generator_version` y `seed` registrados; una `Idempotency-Key` por solicitud; ritmo ≤ 30/s; `RunReport` sin datos del solicitante.
  - `driver`: `analista-1` y `analista-2` por el BFF; `DecisionMix` con semilla; 409 y 422 contados, sin reintentar con otro contenido.
  - **Volumen de demostración** (BR-U12-06; pendientes consolidados, segunda tanda, 2026-10-10): la sección `decisions` envía **2 000** casos `normal` y el conductor los decide, con el modelo de referencia activo y antes de RT-2. Son los datos de la prueba en kind de U11 (INF-U11-06), del dashboard de producto, de la disparidad humana de U9 y, los primeros 1 000, de `CASE-SIZE`. El manifiesto registra el número enviado y el decidido.
  - Diseño: BR-U12-01..03; NFR-U12-10.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest system-verification/tests/property/test_driver_mix.py tests/integration/test_simulator.py tests/integration/test_driver.py` (dobles del gateway y del BFF): PBT-U12-03; el simulador nunca supera 30/s; claves distintas; el `RunReport` sin identificadores; el conductor ante un 409 `decision_already_recorded` sigue con el caso siguiente.

### Bloque D — Escenarios y mediciones

- [ ] **Paso 7 — RT-1 y RT-4**
  - RT-1: por cada par de U5, por el BFF con `analista-1`: `free_text` del detalle igual byte a byte; recomendación y narrativa iguales a las del par; sin llamadas distintas de scoring y explainability.
  - RT-4: los 18 casos; `confidence` bajo el umbral, `revision_requerida` y `baja_confianza`.
  - Diseño: BR-U12-04; INF-U12-03.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_rt1_rt4.py`: los oráculos contra respuestas correctas → `pasa` e incorrectas (narrativa distinta, `free_text` alterado, confianza alta) → `falla` (NFR-U12-42).

- [ ] **Paso 8 — RT-2, RT-3 y RT-5**
  - RT-3: tras cada sync del paquete alterado, solo `FailClosed(version_mismatch)`; cero `recommendation` en la ventana (proyección `metrics`); casos `en_sincronizacion`.
  - RT-2: tras el sync del modelo proxy, lote `stratified` (la sección se niega si una celda no alcanza 30); espera la entrada `freeze`; los casos nuevos `modelo_congelado`; sigue congelada tras 3 corridas más; reactivación por `cumplimiento-1` con MFA por el BFF; 5 corridas con `rt2_latency`.
  - **Paquete completo** (revisión del plan de tareas de U12, 2026-10-10; BR-U12-04 y Paso 16 de U9): el oráculo lee la entrada `freeze` por la proyección `monitoring_freezes` (`verification-reader`) y exige un `context_package` válido según `FreezeContext` de U0 §9.4 (`before`, `after`, `last_7_days`, `trigger_attribute`, `implicated`, `affected_volume`, `threshold_pp`, `n_min`), y además `data_sources` e `initial_disparity` presentes y no vacíos (los agrega governance, BR-U9-16). Un paquete al que le falta cualquiera → `falla`.
  - RT-5: lee el Job de U8 (`rt5-demo-<runId>`, solo kind, que solo cuenta con el `runId` del manifiesto y un `completionTime` posterior a `started_at`, la misma regla de frescura que X04 y X06; pendientes posteriores al cierre, 2026-10-10): su log con el 403 del proxy (`l5d-proxy-error`), `CoreWriteAttempt` en Prometheus y `vectra_core_write_attempts_total` en 0. Las otras dos identidades las cubre X01; sin `auth can-i` de otras identidades, que exigiría impersonación (pendientes consolidados, 2026-10-10).
  - **Consulta anclada al Job** (pendientes consolidados, segunda tanda, 2026-10-10): la sección `rt5` puede correr horas después del Job, y `CoreWriteAttempt` mira una ventana de 5 min. Por eso el oráculo no consulta «ahora»: toma `t0 = status.startTime` y `t1 = status.completionTime` del Job `rt5-demo-<runId>` y consulta con **`/api/v1/query_range`** (`start`, `end` y `step = 15s`), con expresiones instantáneas válidas; el máximo y la presencia los calcula el oráculo en Python sobre los puntos devueltos, sin rangos `[t0, …]` dentro de PromQL (pendientes abiertos, 2026-10-10):
    - `ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}` en [t0, t1 + 15 min]: al menos un punto;
    - `sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})` en [t0, t1 + 15 min]: la serie tiene puntos y su máximo es ≥ 1. No se usa `increase()`, porque la serie **nace en 1** con la primera denegación (INF-U8-03) y `increase()` daría 0 (pendientes consolidados, tercera tanda, 2026-10-10);
    - `sum(vectra_core_write_attempts_total)` en [`started_at`, ahora]: el máximo de los puntos es 0 (o la serie existe y nunca supera 0);
    - **retención**: `prometheus_tsdb_lowest_timestamp_seconds` (instantánea) ≤ t0; si no, el resultado es `no ejecutado`, nunca `pasa`. Las consultas se guardan en la evidencia (NFR-U12-50).
  - Diseño: BR-U12-04, 07; NFR-U12-11.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py` (una sola `recommendation` en RT-3 → `falla`; una corrida de RT-2 de 31 min → `falla` con la medición registrada; un `freeze` sin `data_sources` o sin `initial_disparity`, o con un `FreezeContext` incompleto → `falla`; RT-5 con un 403 sin `l5d-proxy-error` (de la aplicación) → `falla`; RT-5 evaluado 6 h después del Job con un doble de Prometheus que tiene la alerta solo en [t0, t1 + 5 min] → `pasa`, y con la alerta fuera de esa ventana → `falla`; retención que no cubre t0 → `no ejecutado` (pendientes consolidados, segunda tanda, 2026-10-10); la serie de denegaciones **nace en 1** dentro de la ventana y no vuelve a crecer → `pasa`; la serie ausente en la ventana → `falla` (pendientes consolidados, tercera tanda, 2026-10-10); contador del mock > 0 → `falla`; sin `CoreWriteAttempt` → `falla` (pendientes consolidados, 2026-10-10); revisión del plan de tareas de U12, 2026-10-10).
    Además, contra un **Prometheus real** (pendientes abiertos, 2026-10-10): `uv run pytest system-verification/tests/integration/test_rt5_promql.py` levanta Prometheus por digest con Testcontainers sobre un bloque TSDB creado con `promtool tsdb create-blocks-from openmetrics` a partir de fixtures (la serie de denegaciones que nace en 1 y no crece; la alerta solo en [t0, t1 + 5 min]; el contador del mock en 0 y en 1; la evaluación 6 h después). Comprueba que cada expresión del oráculo es aceptada por la API (sin `bad_data`) y que el resultado es `pasa`, `falla` o `no ejecutado` como en los casos con doble. Corre en CI (Paso 16) sin clúster.

- [ ] **Paso 9 — X01–X10**
  - Red: toma la salida de la suite de conectividad de U1 (X01, X02, X05, X07, X08, X09) como evidencia.
  - Comportamiento: X03 (`ingeniero-1` y `cro-1` intentan `resolve_frozen` → 403); X04 y X06 desde los Jobs `x04-probe` y `x06-probe`, que solo cuentan con el `runId` del manifiesto y un `completionTime` posterior al `started_at` que fijó la sección `prepare` (Paso 13), **antes** del PR de los Jobs (revisión del plan de tareas de U12, 2026-10-10); X10 (`/auth/admin` → 404).
  - Diseño: BR-U12-05; INF-U12-02.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_x.py` (un Job de otro `runId` o con `completionTime` anterior → `no ejecutado`; un 200 en X03 → `falla`; un 200 en X10 → `falla`).

- [ ] **Paso 10 — `SIM-NORMAL`, `LOGS-NO-PII` y `CASE-SIZE`**
  - `SIM-NORMAL`: `accepted = sent`, un caso por solicitud y cada uno en `listo` o en un fail-closed documentado.
  - `LOGS-NO-PII`: consulta de Loki sobre el periodo por los `SYN-…` y los nombres de U5 enviados → 0 resultados.
  - `CASE-SIZE`: crecimiento de `case-db` y del registro por caso con los primeros 1 000 casos (series de Prometheus de U1 y U8).
  - Diseño: BR-U12-06, 12; domain-entities §4.1.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_measurements.py` (un `SYN-` encontrado → `falla`; `accepted < sent` → `falla`).

- [ ] **Paso 11 — Carga (US-609)**
  - `capacity`: asignable de los 4 workers frente a la suma de máximos de los HPA (`vectra-app`, `vectra-edge`, `vectra-serving`) y de KServe, y CPU y memoria libres del host; si no alcanza, `scale = 0,5` y se registra.
  - `run`: línea base a 5/s; después 20/s + 200 usuarios durante 30 min con los scripts k6 de U7, U8 y U10 en su propio contenedor `grafana/k6` de 2 CPU y 2 GiB, siempre aparte y **lanzado por el operador** (pendientes consolidados, 2026-10-10). Intercambio con la sección `load` (pendientes consolidados, segunda tanda, 2026-10-10):
    - `load` no lanza contenedores: imprime el comando exacto de `docker run` (digest de `grafana/k6`, límites, red de kind, variables de entorno con la URL y el token de carga, montaje del directorio de evidencias de la verificación) y espera;
    - k6 escribe su resumen con `--summary-export` en `evidence/<fecha>-<commit>/load/k6-summary-<runId>.json` del directorio montado;
    - el operador confirma el fin y `load` lee ese resumen, comprueba que el nombre lleva el `runId` del manifiesto y que el archivo es posterior a la impresión del comando, y aplica el oráculo; prueba en `test_load_oracle.py`: resumen ausente o anterior al comando → `no ejecutado`; sin el archivo, o con uno viejo, US-609 sale `no ejecutado`; HPA muestreados cada 30 s (lectura); p95 contra NFR-U7-01..03, NFR-U8-01 y NFR-U10-01; tasa de fail-closed frente a la línea base.
  - Diseño: BR-U12-08; INF-U12-05.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_capacity.py test_load_oracle.py` (capacidad insuficiente → `scale = 0,5` y la nota en la evidencia; una réplica sobre el máximo → `falla`; fail-closed sobre la línea base → `falla`); `k6 inspect` de cada script dentro del contenedor `grafana/k6` por digest (también en CI, Paso 16; pendientes consolidados, 2026-10-10).

### Bloque E — Demos, informe y CLI

- [ ] **Paso 12 — Demos**
  - Guiones `journey-7-3.md`, `journey-7-4.md`, `rt-5.md` y `dashboard.md` con los pasos del presentador, las lecturas y las llamadas a la API, y un `verify/<demo>.sh` por demo que comprueba cada paso.
  - Los cambios al clúster (artefacto alterado, modelo proxy, Jobs de prueba) son PRs preparados en `demos/prs/`, que el operador sincroniza antes.
  - Diseño: BR-U12-09.
  - **Aceptación**: la prueba del Paso 1 sobre `demos/`; `shellcheck system-verification/demos/verify/*.sh`.

- [ ] **Paso 13 — CLI por secciones, manifiesto y `CODEOWNERS`**
  - `cli`: secciones `prepare`, `network`, `decisions`, `rt1`, `rt4`, `rt5`, `rt3`, `rt2`, `load`, `pii`, `u11`, `report`, en el orden de business-logic-model §2.1, con retoma desde una sección y evidencia al terminar cada una.
  - **`prepare`** (revisión del plan de tareas de U12, 2026-10-10): primera sección, **antes** del PR de los Jobs de prueba. Genera el `runId` de la verificación, escribe el manifiesto inicial con ese `runId` y `started_at = ahora`, y produce el parche de values de kind (`probes.runId`, y el de U8 para RT-5) que el operador usa en el PR. Así los Jobs de prueba terminan **después** de `started_at`, y el oráculo de X04 y X06 (Paso 9) puede aceptarlos. Sin `prepare`, las demás secciones se niegan a correr.
  - `manifest`: `manifest.json` con SHA-256 por archivo, `started_at`, semillas, `generator_version`, digests (leídos del clúster), tamaño de `test` y las **solicitudes repetidas** entre escenarios (misma fila de U5 enviada en dos escenarios, NFR-U12-11); tope de 50 MB.
  - **`runId`** (pendientes posteriores al cierre, 2026-10-10): un solo `runId` por verificación, generado por `prepare` con el formato `AAAAMMDD-HHMM` a partir de `started_at` en UTC, truncado al minuto (el que exige `rebuild-runid-check` de U3; pendientes consolidados, 2026-10-10); es el `probes.runId` de los tres Jobs (`x04-probe-<runId>` de U9, `x06-probe-<runId>` de U3 y `rt5-demo-<runId>` de U8). El manifiesto guarda ese `runId` y los nombres esperados de los tres Jobs; el oráculo de cada uno compara contra ellos.
  - `prepare` **se niega** si ya existe un `manifest.json` en el directorio de la verificación: así una retoma nunca reinicia `started_at` a mitad de camino. Para empezar otra verificación se usa un directorio nuevo.
  - **Tiempo medido** (NFR-U12-31): cada sección registra en el manifiesto su inicio y su fin, y el informe muestra la duración por sección y la total, con las esperas de los PRs del operador aparte.
  - **Consultas guardadas** (NFR-U12-50): cada consulta a Prometheus y a Loki que usa un oráculo se guarda en la evidencia con su texto, su ventana de tiempo y el `correlation_id` o prefijo de la corrida.
  - `CODEOWNERS` del monorepo: `system-verification/evidence/` para los equipos `calidad` y `cumplimiento` (crearlos si no existen).
  - Diseño: NFR-U12-10, 20, 30; INF-U12-04.
  - **Aceptación**: `uv run pytest system-verification/tests/integration/test_cli.py` (interrumpir en `rt3` y retomar → no se repiten las anteriores; manifiesto con todos los campos; > 50 MB → resumen y hash; `network` sin `prepare` → se niega; `prepare` con un manifiesto existente → se niega y `started_at` no cambia; dos escenarios con la misma fila de U5 → el manifiesto la lista; el informe muestra la duración por sección; cada evidencia con oráculo de Prometheus o Loki incluye su consulta; `prepare` → manifiesto con `runId` y `started_at` y el parche de values con ese `runId` en los tres archivos de values; `started_at = 2026-10-12T14:07:31Z` → `runId = 20261012-1407` (pendientes consolidados, 2026-10-10); revisión del plan de tareas de U12, 2026-10-10); un PR de fixture que toca solo `system-verification/evidence/` pide la aprobación de *code owners* (prueba de `branch-protection-check` de U4).

### Bloque F — Imagen, CI y documentación

- [ ] **Paso 14 — Repositorio, migraciones, frontend y despliegue en el clúster: N/A**
  - U12 no tiene base de datos, interfaz ni recursos de Kubernetes.
  - **Aceptación**: `test ! -d system-verification/chart && test ! -d system-verification/migrations`; la imagen no contiene manifiestos de Kubernetes.

- [ ] **Paso 15 — Imagen**
  - Python oficial por digest, sin privilegios; incluye `kubectl`, Playwright y su Chromium por versión fijada (el Chromium sin interfaz del login del Paso 5). **k6 no va en esta imagen** (pendientes posteriores al cierre, 2026-10-10): corre en su propio contenedor (`grafana/k6` por digest), con límites de 2 CPU y 2 GiB, que **el operador** lanza en la red de kind con el comando que imprime la sección `load` (Paso 11, INF-U12-05; pendientes consolidados, segunda tanda, 2026-10-10);
  - **sandbox de Chromium** (pendientes posteriores al cierre, 2026-10-10): el contenedor corre como usuario no root con el perfil `seccomp` que publica Playwright para Chromium (`chrome.json`) y espacios de nombres de usuario sin privilegios; **nunca** con `--no-sandbox`. Si el host no los permite, la sección que necesita login termina con un error claro;
  - la imagen se construye, se escanea, lleva SBOM y se firma con `supply-chain.yml` de U1 (frase separada, pendientes consolidados, 2026-10-10).
  - Diseño: INF-U12-01.
  - **Aceptación**: `hadolint system-verification/Dockerfile`; el SBOM lista `kubectl`, Playwright y Chromium con su versión y **no** `k6`; prueba de humo: Chromium arranca con el sandbox activo bajo el perfil `seccomp` (`chrome://sandbox` sin errores).

- [ ] **Paso 16 — Workflow de CI**
  - `.github/workflows/system-verification.yml`, en cada PR que toca `system-verification/`: `uv sync --frozen`, ruff, mypy, import-linter, pruebas con perfil `ci` y semilla impresa, cobertura (100 % en `report` y `sampler`; ≥ 85 % en el resto, NFR-U12-40), prueba de verbos de `kubectl`, `shellcheck`, `k6 inspect` de los scripts en el contenedor `grafana/k6` por digest (pendientes consolidados, 2026-10-10); `test_rt5_promql.py` con el contenedor de Prometheus (pendientes abiertos, 2026-10-10); perfil `nightly` y `mutmut` en el nocturno.
  - **AUTONOMIA-01**: ningún paso ejecuta la verificación contra un clúster.
  - **Aceptación**: `uv run pytest system-verification/tests --cov=vectra_verification --cov-branch --cov-fail-under=85` (pendientes consolidados, 2026-10-10); `actionlint .github/workflows/system-verification.yml`; `! grep -E "kubectl|helm (install|upgrade)|terraform apply|argocd" .github/workflows/system-verification.yml`.

- [ ] **Paso 17 — Documentación y trazabilidad**
  - `system-verification/README.md`: cómo ejecutar cada sección, requisitos (K16, PRs preparados, `runId` de los Jobs en formato `AAAAMMDD-HHMM` y el sync manual de las **tres Applications** `bias-monitoring`, `decision-registry-rebuild` y `case-management`; pendientes consolidados, 2026-10-10), presupuesto de tiempo (con las esperas de PRs aparte), cómo leer el informe y su límite.
  - El README dice también cómo llegan al contenedor el kubeconfig, el certificado raíz y la sesión de Vault **sin escribirse en disco** (montajes de solo lectura del kubeconfig y del certificado; token de Vault como variable de entorno; sistema de archivos de solo lectura salvo el directorio de evidencias y un `tmpfs`; deployment-architecture §2b), y cómo lanzar el contenedor de k6 con sus límites (pendientes posteriores al cierre, 2026-10-10).
  - Trazabilidad de cada BR-U12 a una prueba.
  - **Aceptación**: `test -s system-verification/README.md`; `uv run python platform/tests/test_traceability.py --unit system-verification --all`.

### Bloque G — Verificación en kind (con aprobación humana)

- [ ] **Paso 18 — Primera verificación completa en kind**
  - **Requisito previo**: un PR con los Pasos 1–17 aprobado por un humano, con U1–U11 instalados en kind, el modelo de referencia activo y el binding K16 presente.
  - **Orden** (revisión del plan de tareas de U12, 2026-10-10):
    1. el operador ejecuta `prepare`, que fija el `runId` y el `started_at`;
    2. abre el PR de los Jobs de prueba con el parche que produjo `prepare` (values de kind de `bias-monitoring`, `decision-registry-rebuild` y `case-management`) y sincroniza las **tres Applications** con prune (pendientes consolidados, 2026-10-10);
    3. ejecuta las demás secciones en orden, empezando por `network`, que lee los Jobs ya terminados (con `completionTime` posterior a `started_at`).
  - El operador ejecuta todas las secciones en orden, con los PRs preparados de RT-3 y RT-2 y sus reversiones, y el día siguiente la sección `u11`; genera el informe y abre el PR de verificación.
  - Diseño: BR-U12-04..13; NFR-U12-30, 31; INF-U12-01..05. Historias: US-609 y las de domain-entities §4.2.
  - **Aceptación**: el PR de verificación con `evidence/<fecha>-<commit>/`, `manifest.json` y `verification-report.md`, revisado por `calidad` y `cumplimiento`; el informe lista cada RT, X, demo e historia con su resultado y no marca `pasa` sin evidencia.

### Bloque H — Cierre

- [ ] **Paso 19 — Cierre de la unidad**
  - **Aceptación**: `make -C system-verification check`, que corre en orden las verificaciones estáticas, las propiedades y las pruebas con dobles de los Pasos 1–17 y termina en 0. La verificación en kind (Paso 18) se revisa como el PR de verificación.

---

## 3. Trazabilidad

| Historia o elemento | Pasos |
|---|---|
| US-609 (dueña) | 11, 18 |
| US-101 (`SIM-NORMAL`) | 6, 10, 18 |
| US-106 (RT-4), US-109 (RT-1) | 7, 18 |
| US-111 (RT-3, `journey-7-3`), US-303 (RT-2, `RT2-LATENCY`, `journey-7-4`), US-305 (`journey-7-4`, X03) | 8, 9, 12, 18 |
| US-603 (RT-5, X01, `rt-5`), US-604 (X02, `LOGS-NO-PII`) | 8, 9, 10, 12, 18 |
| Demos US-304, 503, 504, 505 | 12, 18 |

| Diseño | Pasos |
|---|---|
| BR-U12-01..03 | 6 |
| BR-U12-04, 05, 07 | 7, 8, 9 |
| BR-U12-06, 12 | 10 |
| BR-U12-08 | 11 |
| BR-U12-09 | 12 |
| BR-U12-10 | 2 |
| BR-U12-11, 13 | 3, 13 |
| BR-U12-04 (paquete completo de RT-2) | 8 |
| NFR-U12-01..50 | 1–3, 5, 6, 8, 11, 13, 15, 16 |
| INF-U12-01..05 | 2, 5, 9, 11, 13, 15 |

| Propiedad | Pasos |
|---|---|
| PBT-U12-01, 02, 04 | 3 |
| PBT-U12-03 | 6 |

## 4. Cumplimiento de extensiones (plan de tareas U12)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Sin recursos de U12 en el clúster; `kubectl` sin escritura (Paso 1); la verificación la ejecuta el operador (Paso 18) |
| AUTONOMIA-02 | Cumple | Oráculos probados contra respuestas incorrectas (Pasos 7–11); informe que no marca `pasa` sin evidencia (Paso 3) |
| AUTONOMIA-03 | Cumple | RT-5, X01, X04, X06 (Pasos 8, 9) |
| SECURITY-03 / 11 / 12 | Cumple | Pasos 2, 6, 10 |
| RESILIENCY-09 | Cumple | Paso 11 |
| PBT-01..10 | Cumple | PBT-U12-01..04 (Pasos 3, 6), perfiles `ci` y `nightly` (Paso 16) y pruebas de ejemplo (Pasos 3, 6–11) |
