# U12-T03 — Escenarios RT-2, RT-3 y RT-5 con `rt2-setup`, y la medición `SIM-NORMAL` de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que implementa:** ninguna propia. La trazabilidad del plan (§3) nombra el Paso 8 en US-111 (RT-3), US-303 (RT-2 y `RT2-LATENCY`) y US-603 (RT-5), y el Paso 10 en US-101 (`SIM-NORMAL`). Aquí se escriben los oráculos de esas evidencias. Las ejecuta el operador en kind (Paso 18, U12-T05).
**Depende de:**
- **U12-T02 fusionada en `main`** (PR #___, commit de fusión `_______`: **por completar al fusionar**). Lo que esta tarea da por sentado, leído en la rama `tarea/U12-T02` (`15e6f2f`, ronda 1 cerrada, sin fusionar: **vuelve a leer `aidlc-docs/construction/system-verification/code/clients.md` al empezar**, porque la revisión puede cambiar firmas):
  - `clock.Clock` con `now()` (UTC con zona), `monotonic()` y `sleep(segundos)`; `tests/doubles/fake_clock.py`.
  - `clients/oidc.py`: `OidcClient.login(user)`, `.step_up(user)` y `.service_session(client_id, scopes)`. La aserción de servicio lleva `aud` = el emisor público del entorno (`identity-edge/docs/emisor-de-tokens.md`, resultado R2). La espera de la ventana TOTP entre dos logins del mismo usuario ya está dentro.
  - `clients/bff.py`, `BffClient`: `me`, `list_cases(state, page, page_size)`, `get_case`, `record_explanation_view`, `record_decision` y `resolve_frozen(model_version_id, FrozenResolutionIn, section)`, que llama a `guard.check_reactivation` y exige una sesión de step-up. **No tiene las rutas de modelos**: las agrega esta tarea.
  - `clients/_api.py`: `ApiError(status, code, reason, retry_after)` (no expone `invalid_params`) y `RunTag(scenario, prefix)`.
  - `clients/registry.py`, `RegistryClient`: `metrics(case_id, entry_type, recorded_from, recorded_to, seq_after, limit)` devuelve `MetricsProjection`; `freezes(recorded_from, recorded_to, …)` devuelve `FreezeProjection | FrozenResolutionProjection`. **Una respuesta 2xx que no valida es `ApiError(…, "invalid_response")`**, no un dato.
  - `clients/prom.py`, `PromClient`: `query(expr, at)` y `query_range(expr, start, end, step)`; devuelven `QueryResult(query, start, end, step, result_type, result)`. Un `status: error` es `ObsError`.
  - `clients/k8s_read.py`, `K8sRead`: `get(resource, namespace, selector, output)`, `logs(pod, namespace, tail, since)`, `auth_can_i` y `port_forward`. Un fallo es `K8sError`. `logs` no recibe contenedor.
  - `simulator.py`: `Simulator.select(scenario, volume, seed)` devuelve las posiciones y las celdas cortas **sin enviar**; `Simulator.run(scenario, volume, seed, rate, section)` devuelve `SimulationResult(report: RunReport, sent_positions)`. `RunReport` trae `sent`, `accepted`, `rejected_by_code`, `case_ids` y `short_cells` (`sampler.CellReport`: `attribute`, `group`, `band`, `available`, `taken`).
  - `guard.py`: `SECTIONS` incluye `rt5`, `rt3`, `rt2-setup` y `rt2`; en staging solo `prepare`, `decisions`, `u11` y `report`; `REACTIVATION_SECTION = "rt2"`. `evidence.prepare` ya atiende F-07, F-08 y F-09 de `revisiones/U12-T01/ronda-2.md`, y `guard.check_known`, F-04.
  - `.importlinter` con 6 contratos (`subprocess` solo en `clients.k8s_read`, `playwright` solo en `clients.oidc`, `pyarrow` solo en `simulator`); `Makefile` con `check: lint types imports test`; `make -C system-verification check` ≈ 10 a 11 min con carga 2 a 3 (`bitacoras/U12-T02.md`).
  - Dobles: `tests/doubles/real_bff.py` (el BFF real en proceso con los dobles de U10), `real_case.py`, `contract_world.py`, `registry_read_double.py`, `obs_double.py`, `kubectl_double.py`, `u5_delivery.py` y `external_paths.py`.
- **U12-T01** (ya en `main`): `report.Evidence` (`result` solo admite `pasa` o `falla`; `report.py`, línea 63), `report.ELEMENT_IDS` (`RT-2`, `RT-3`, `RT-5`, `SIM-NORMAL` y `RT2-LATENCY`, líneas 27 a 39), `rt2_latency.measure(run, recommendation_recorded_at, freeze_recorded_at)` con `RUNS = (1, 2, 3, 4, 5)` y `LIMIT` de 1 800 s, `sampler.stratified` y `sampler.cell_report`, y `tests/unit/test_kubectl_verbs.py`.
- **Lo que los oráculos leen de las demás unidades.** Comprobado sobre `origin/main` `4e33d39`. Está en «Lo que cada oráculo lee de verdad», con ruta y línea.
- **No depende de U01-T09** (métricas del proxy de Linkerd, en preparación). El oráculo de `rt5` se escribe y se prueba igual con o sin ella; lo que cambia es el resultado en kind.

Es código, dobles y pruebas sin clúster (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6). Usa Docker local para Testcontainers.
**Rama:** `tarea/U12-T03`, desde `origin/main` **después** de fusionar U12-T02.

Bloque D del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, Pasos 8 y 10), según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fila U12: «A+B (1–4) · C (5–6) · D (8, 10) · E+F (12, 13, 15, 17) · G+H (18–19)») y §8 (U12: 5 tareas, sin cambio). Es la tercera de cinco. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 7 RT-1 y RT-4 | **D** | No entra | Enmienda §3 U12, fila «7: D, D»; §1.5, fila U12 |
| 8 RT-2, RT-3 y RT-5 | **E\*** | Entran RT-3, RT-5, `rt2-setup` y RT-2 con **1** versión del proxy. Se difiere correr las otras 4 | Enmienda §3 U12, fila «8: E\*, E\*, RT-2 (1 versión), RT-3 y RT-5»; §1.2: «DD-1 = 1 versión»; alcance §3 U12, fila 8: «RT-2 con el número de versiones de DD-1»; alcance §5, DD-1: «**1 en la demo**; U5 genera las 5 igual, y el cierre completo corre las 5» |
| 8b `resilience` · 9 X01–X10 · 11 Carga | **D** | No entran | Enmienda §3 U12, fila «8b · 9 · 11: D, D»; alcance §3 U12: 9 por T5 y 11 por T3 |
| 10 `SIM-NORMAL`, `LOGS-NO-PII` y `CASE-SIZE` | **E\*F** | Entra `SIM-NORMAL`. Se difieren `LOGS-NO-PII` y `CASE-SIZE` | Enmienda §3 U12, fila «10: E\*, E\*F, Entra `SIM-NORMAL`, que verifica el flujo base de D4. Se difieren `LOGS-NO-PII` (ninguna demo; P-18) y `CASE-SIZE`»; §6, P-18: «Por la regla del usuario, diferir» |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09. No hay PBT nuevas en estos pasos; PBT-U12-01, 02 y 04 siguen verdes.

**Decisiones del usuario que rigen** (`DECISIONES-LOOP.md` §10, 2026-11-13):
- **Celdas de RT-2.** `rt2` se niega **solo si queda corta una celda alcanzable** (una con 30 o más filas disponibles en `test`). Las inalcanzables se informan en la evidencia y no bloquean. Con los datos reales de U5 son 4 de 65 (`CANDIDATAS.md`, línea 333; remedido al redactar, ver CA-9).
- **D2 usa 1 versión del proxy** (DD-1).
- **Emisor.** Keycloak publica solo el emisor público; las aserciones de servicio llevan `aud` = emisor.
- **Sin clúster** en esta tarea: dobles validados o servicios reales en proceso.

**Lección que esta tarea aplica** (enmienda §8; U12-T02): un oráculo que espera un campo, un estado o una serie que el servicio no produce solo se descubre en kind, y U12 es la última unidad. Por eso cada oráculo nombra aquí la ruta, el campo y el valor reales, y cada doble se valida contra `contracts/openapi/` o se sustituye por la app real en proceso.

Lo que U12 hace en las demos (enmienda §1) y lo que esta tarea aporta:
- **D1, journey 7.3 (§1.1):** la sección `rt3`. RT3-a, c y d → 422 de U4; RT3-b; y la evidencia de la demo: con F22 apagado, cero `recommendation` y casos `en_sincronizacion` con causa `timeout` o `explainer_unavailable`.
- **D2, journey 7.4 (§1.2):** las secciones `rt2-setup` y `rt2`: lote `stratified`, `freeze` con su paquete completo, casos nuevos `modelo_congelado`, reactivación con step-up, que no se recongele, `rt2_latency` ≤ 1 800 s y el cierre.
- **D3, RT-5 (§1.3):** la sección `rt5`: el Job `rt5-demo-<runId>`, su log, `CoreWriteAttempt` y los dos contadores.
- **D4, dashboard (§1.4):** `SIM-NORMAL` sobre los 2 000 casos `normal` de `decisions`.

---

## Alcance

**Dentro:** los Pasos 8 y 10 del plan. Texto del plan, sin recortes salvo lo que el recorte difiere, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque D — Escenarios y mediciones

- [ ] **Paso 8 — RT-2, RT-3 y RT-5** (E\*; RT-2 con 1 versión)
  - RT-3 (cuarta revisión de coherencia entre unidades, 2026-10-31): `RT3-a`, `c` y `d`: 422 de U4 al registrar, sin cambio en `serving-config`; `a` y `d`, desplegados por PR sin registrar, no listos con `ModelPackageIntegrityFailed` (quinta revisión de coherencia entre unidades, 2026-10-31). `RT3-b`: `validacion_fallida`; si pasa la validación, se aprueba y se promueve como en RT-2, y da `FailClosed` con `explainer_error` o `feature_dictionary_incomplete`. PR solo de kind que deshabilita F22: `FailClosed` con `timeout` o `explainer_unavailable`, que es la evidencia de `journey-7-3` (quinta revisión de coherencia entre unidades, 2026-10-31). Cero `recommendation` de la versión alterada, y con F22 deshabilitado, de ninguna versión (proyección `metrics`); casos `en_sincronizacion`, o `no_disponible` tras ≈ 15,5 min. `version_mismatch` en runtime lo cubren las pruebas de integración de U7.
  - RT-2 (cuarta revisión de coherencia entre unidades, 2026-10-31): por cada una de las ~~5~~ versiones del proxy, ya aprobadas en `rt2-setup`: PR de promoción y sync; `mark_active` del operador con `promotion-tool` (F08), y la herramienta espera a verla `activo` en `list_models`; PR post-activación de la anterior; lote `stratified` (la sección se niega si una celda no alcanza 30), entrada `freeze`, casos nuevos `modelo_congelado`, reactivación por `cumplimiento-1` con MFA por el BFF, comprobación de que no se recongela y `rt2_latency`. En la primera, además, sigue congelada tras 3 corridas más de bias antes de reactivar. Al final, rollback al modelo de referencia (quinta revisión de coherencia entre unidades, 2026-10-31). **(Se difiere correr 4 de las 5 versiones: enmienda §3 U12, fila «8»: «RT-2 (1 versión), RT-3 y RT-5»; §1.2: «DD-1 = 1 versión»; alcance §5, DD-1: «**1 en la demo**; U5 genera las 5 igual, y el cierre completo corre las 5». La demo corre 1, que es «la primera»: ver «Qué cambia» y «Fuera».)**
  - **`rt2-setup`** (quinta revisión de coherencia entre unidades, 2026-10-31): `ingeniero-1` registra las ~~5~~ versiones y lanza su validación por el BFF, tras el PR de sus `InferenceService` de staging; `cro-1` las aprueba, distinto de `registered_by`. Termina cuando las ~~5~~ están `aprobado`; si una queda en `validacion_fallida`, la sección se niega a seguir. **(Con DD-1 son las versiones que recibe; la demo pasa 1. Misma cita que arriba.)**
  - **Paquete completo** (revisión del plan de tareas de U12, 2026-10-10; BR-U12-04 y Paso 16 de U9): el oráculo lee la entrada `freeze` por la proyección `monitoring_freezes` (`verification-reader`) y exige un `context_package` válido según `FreezeContext` de U0 §9.4 (`before`, `after`, `last_7_days`, `trigger_attribute`, `implicated`, `affected_volume`, `threshold_pp`, `n_min`), y además `data_sources` presente, que puede ir vacía, e `initial_disparity` no vacía (los agrega governance, BR-U9-16; cuarta revisión de coherencia entre unidades, 2026-10-31). Un paquete al que le falta cualquiera → `falla`.
  - RT-5: lee el Job de U8 (`rt5-demo-<runId>`, solo kind, que solo cuenta con el `runId` del manifiesto y un `completionTime` posterior a `started_at`, la misma regla de frescura que X04 y X06; pendientes posteriores al cierre, 2026-10-10): su log con el 403 del proxy (`l5d-proxy-error`), `CoreWriteAttempt` en Prometheus y `vectra_core_write_attempts_total` en 0. Las otras dos identidades las cubre X01; sin `auth can-i` de otras identidades, que exigiría impersonación (pendientes consolidados, 2026-10-10).
  - **Consulta anclada al Job** (pendientes consolidados, segunda tanda, 2026-10-10): la sección `rt5` puede correr horas después del Job, y `CoreWriteAttempt` mira una ventana de 5 min. Por eso el oráculo no consulta «ahora»: toma `t0 = status.startTime` y `t1 = status.completionTime` del Job `rt5-demo-<runId>` y consulta con **`/api/v1/query_range`** (`start`, `end` y `step = 15s`), con expresiones instantáneas válidas; el máximo y la presencia los calcula el oráculo en Python sobre los puntos devueltos, sin rangos `[t0, …]` dentro de PromQL (pendientes abiertos, 2026-10-10):
    - `ALERTS{alertname="CoreWriteAttempt", alertstate="firing"}` en [t0, t1 + 15 min]: al menos un punto;
    - `sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})` en [t0, t1 + 15 min]: la serie tiene puntos y su máximo es ≥ 1. No se usa `increase()`, porque la serie **nace en 1** con la primera denegación (INF-U8-03) y `increase()` daría 0 (pendientes consolidados, tercera tanda, 2026-10-10);
    - `sum(vectra_core_write_attempts_total)` en [`started_at`, ahora]: el máximo de los puntos es 0 (o la serie existe y nunca supera 0);
    - **retención**: `prometheus_tsdb_lowest_timestamp_seconds` (instantánea) ≤ t0; si no, el resultado es `no ejecutado`, nunca `pasa`. Las consultas se guardan en la evidencia (NFR-U12-50).
  - Diseño: BR-U12-04, 07; NFR-U12-11.
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py` (una sola `recommendation` en RT-3 → `falla`; `RT3-a` aceptado por U4 → `falla`; sin `FailClosed` de `timeout` o `explainer_unavailable` con F22 deshabilitado → `falla`; una versión reactivada que se recongela el mismo día → `falla`; dos corridas con el mismo `model_version_id` → `falla` (cuarta revisión de coherencia entre unidades, 2026-10-31); una corrida de RT-2 de 31 min → `falla` con la medición registrada; un `freeze` sin el campo `data_sources` o con `initial_disparity` vacía, o con un `FreezeContext` incompleto → `falla`; RT-5 con un 403 sin `l5d-proxy-error` (de la aplicación) → `falla`; RT-5 evaluado 6 h después del Job con un doble de Prometheus que tiene la alerta solo en [t0, t1 + 5 min] → `pasa`, y con la alerta fuera de esa ventana → `falla`; retención que no cubre t0 → `no ejecutado` (pendientes consolidados, segunda tanda, 2026-10-10); la serie de denegaciones **nace en 1** dentro de la ventana y no vuelve a crecer → `pasa`; la serie ausente en la ventana → `falla` (pendientes consolidados, tercera tanda, 2026-10-10); contador del mock > 0 → `falla`; sin `CoreWriteAttempt` → `falla` (pendientes consolidados, 2026-10-10); revisión del plan de tareas de U12, 2026-10-10).
    Además, contra un **Prometheus real** (pendientes abiertos, 2026-10-10): `uv run pytest system-verification/tests/integration/test_rt5_promql.py` levanta Prometheus por digest con Testcontainers sobre un bloque TSDB creado con `promtool tsdb create-blocks-from openmetrics` a partir de fixtures (la serie de denegaciones que nace en 1 y no crece; la alerta solo en [t0, t1 + 5 min]; el contador del mock en 0 y en 1; la evaluación 6 h después). Comprueba que cada expresión del oráculo es aceptada por la API (sin `bad_data`) y que el resultado es `pasa`, `falla` o `no ejecutado` como en los casos con doble. Corre en CI (Paso 16) sin clúster.

- [ ] **Paso 10 — `SIM-NORMAL`~~, `LOGS-NO-PII` y `CASE-SIZE`~~** (E\*F)
  - `SIM-NORMAL`: `accepted = sent`, un caso por solicitud y cada uno en `listo` o en un fail-closed documentado.
  - ~~`LOGS-NO-PII`: consulta de Loki sobre el periodo por los `SYN-…` y los nombres de U5 enviados → 0 resultados.~~ **(Diferido por la demo: enmienda §3 U12, fila «10»: «Entra `SIM-NORMAL`, que verifica el flujo base de D4. Se difieren `LOGS-NO-PII` (ninguna demo; P-18) y `CASE-SIZE`»; ver «Fuera».)**
  - ~~`CASE-SIZE`: crecimiento de `case-db` y del registro por caso con los primeros 1 000 casos (series de Prometheus de U1 y U8).~~ **(Diferido por la demo: enmienda §3 U12, fila «10»: «Entra `SIM-NORMAL`, que verifica el flujo base de D4. Se difieren `LOGS-NO-PII` (ninguna demo; P-18) y `CASE-SIZE`»; ver «Fuera».)**
  - Diseño: BR-U12-06, ~~12~~; domain-entities §4.1. **(BR-U12-12 es `LOGS-NO-PII`: diferida.)**
  - **Aceptación**: `uv run pytest system-verification/tests/unit/test_oracles_measurements.py` (~~un `SYN-` encontrado → `falla`;~~ `accepted < sent` → `falla`). **(El caso del `SYN-` es de `LOGS-NO-PII`: diferido, misma cita.)**

**Qué cambia frente al texto del Paso 8 por DD-1** (1 versión, no 5):
- `rt2-setup` registra, valida y aprueba **las versiones que recibe** (una lista de 1 a 5). La demo le pasa 1. Termina cuando todas están `aprobado`.
- `rt2` corre **una corrida por versión recibida**. La demo corre 1: es «la primera», así que **sí** espera las 3 corridas más de bias antes de reactivar.
- «Dos corridas con el mismo `model_version_id` → `falla`» se conserva: la lista se valida antes de enviar nada, y la prueba usa 2 corridas.
- `RT2-LATENCY` informa el máximo de las corridas hechas y cuántas fueron. Con 1, la evidencia dice «1 medición (DD-1)». No se exige que sean 5 (P-12).
- Lo que se difiere es **ejecutar** las otras 4 versiones. El código no se recorta: el cierre completo corre las 5 sin tocarlo.

### Estructura de destino (§1 del plan): lo que esta tarea crea o llena

```text
vectra-risk/system-verification/
|-- .importlinter  Makefile                         # se modifican (un contrato nuevo; nada mas en el Makefile salvo lo que CA-17 pida)
|-- src/vectra_verification/
|   |-- clients/bff.py  clients/_api.py  clients/registry.py   # se amplian: rutas de modelos del BFF; `invalid_params` en `ApiError`; lectura cruda del `freeze` si hace falta
|   |-- scenarios/
|   |   |-- outcome.py                             # nuevo, no esta en §1 (P-4): resultado de tres valores y «que falto»
|   |   |-- waits.py                               # nuevo, no esta en §1 (P-4): esperas con el reloj inyectado
|   |   |-- rt5.py  rt3.py  rt2.py                 # Paso 8 (`rt2-setup` vive en `rt2.py`: P-4)
|   |   `-- sim_normal.py                          # Paso 10; no esta en §1 (P-4)
`-- tests/
    |-- unit/         test_oracles_rt2_rt3_rt5.py  test_oracles_measurements.py  test_rt2_cells.py
    |                 test_scenario_outcome.py  test_scenario_waits.py  test_rt5_job_script.py
    |-- integration/  test_rt5_promql.py  test_scenarios_contract.py  test_rt3_real_chain.py  test_rt2_cells_real_u5.py
    |-- doubles/      prometheus_tc.py  (y lo que amplies de los dobles de U12-T02)
    `-- fixtures/     (lo que haga falta; ningun secreto real)

vectra-risk/aidlc-docs/construction/system-verification/code/scenarios.md   # nuevo
```

Los nombres `test_oracles_rt2_rt3_rt5.py`, `test_rt5_promql.py` y `test_oracles_measurements.py` son los de la aceptación del plan: son fijos. Los demás son una propuesta: puedes fundir o partir archivos y lo anotas en la bitácora. Los criterios filtran con `-k`: los nombres de las pruebas llevan `rt5`, `rt3`, `rt2_setup`, `rt2` o `sim_normal`.

**No** se crean: `scenarios/rt1.py`, `rt4.py`, `x_network.py`, `x_behavior.py`, `logs_pii.py` ni `case_size.py` (diferidos); `manifest.py` y `cli.py` siguen vacíos (Paso 13); `load/` sigue vacío; no hay `Dockerfile`, `README.md`, `demos/`, `chart/` ni `migrations/`.

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas. Pasos 8 y 10 en `[x]` con `(U12-T03)`; Pasos 7, 8b, 9 y 11 siguen en `[ ]` y ganan su nota (CA-21).
2. `aidlc-docs/construction/system-verification/code/scenarios.md`: nuevo. Si cambias una firma de U12-T02, también `code/clients.md`.
3. `aidlc-docs/construction/system-verification/nfr-requirements/nfr-requirements.md`: **solo** la fila NFR-U12-11 (la precisión de las celdas alcanzables).
4. `aidlc-docs/construction/system-verification/functional-design/business-rules.md`: **solo** la fila «RT-2» de BR-U12-06 (la misma precisión).
5. `CANDIDATAS.md`: las candidatas nuevas de «Notas» y el cierre de las que se atienden.
6. `bitacoras/U12-T03.md`: nuevo.
7. `uv.lock` y `pyproject.toml` raíz: **no deberían cambiar** (no hay dependencias nuevas: `testcontainers`, `httpx` y los paquetes de las demás unidades ya están). Solo si hace falta un `[[tool.mypy.overrides]]`; anótalo.

**Por qué esta tarea sí toca dos documentos de diseño.** `DECISIONES-LOOP.md` §10 dice «NFR-U12-11 y BR-U12-06 se precisan en U12-T03», y hay precedente (BR-U5-14, enmendada en U05-T05). Es una frase fechada en cada uno, con la cita de la decisión. No se toca `audit.md` ni ningún otro documento de diseño: lo demás que el diseño diga mal va a `CANDIDATAS.md`.

`governance/`, `case-management/`, `decision-registry/`, `bias-monitoring/`, `console/`, `model-serving/`, `reference-model/`, `identity-edge/`, `contracts/`, `platform/` y `vectra-risk-gitops/` **se leen, no se editan**. Las pruebas pueden importar sus apps y sus dobles; el código de `src/` no.

### Lo que cada oráculo lee de verdad

Comprobado al redactar sobre `origin/main` `4e33d39`. Verifícalo en tu rama antes de escribir el oráculo y anota en la bitácora «igual» o lo que cambió.

**RT-5 / D3**

| Qué | Dónde está | Valor real |
|---|---|---|
| El Job | `case-management/chart/templates/rt5-demo-job.yaml`, líneas 11 y 18 | `rt5-demo-<runId>` en `vectra-app`; solo se rinde con `probes.enabled` **y** `probes.runId` (`^[0-9]{8}-[0-9]{4}$`, línea 9) |
| Dónde se enciende | `vectra-risk-gitops/values/kind/case-management.yaml`, líneas 5 y 6 | `probes.enabled: true`; `probes.runId` lo agrega `prepare` (U12-T04) |
| Cuándo sale con 0 | misma plantilla, línea 60 | `sys.exit(0 if code == 403 else 1)`: sale con 0 ante **cualquier** 403, también uno de la aplicación |
| La línea del log | misma plantilla, línea 59 | `rt5-demo: POST <url> -> <código> l5d-proxy-error: <valor>`. Si la cabecera no viene, imprime `l5d-proxy-error: None` |
| Reintentos y plazo | misma plantilla, líneas 26 y 27; `case-management/chart/values.yaml`, línea 123 | `backoffLimit: 0`; `activeDeadlineSeconds: 300`; sin `ttlSecondsAfterFinished` |
| Etiquetas del pod | misma plantilla, línea 31 | `app.kubernetes.io/name: case-service`. **No** selecciones por esa etiqueta: toma el pod con `job-name=rt5-demo-<runId>` |
| La alerta | `case-management/chart/templates/prometheusrule.yaml`, líneas 22 a 28 | `CoreWriteAttempt`, sin `for:`, `severity: SEV2`. Expresión: `increase(vectra_core_write_attempts_total[5m]) > 0 or sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"}) - (sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"} offset 5m) or vector(0)) > 0` |
| El nombre de la ruta | `platform/network/flows.yaml`, línea 66 | `core-mock-catch-all` |
| El contador del mock | `case-management/core_banking_mock/src/core_banking_mock/metrics.py`, línea 9 | `vectra_core_write_attempts_total`, sin etiquetas, nace en 0 |
| La serie de Linkerd | **hoy no existe en Prometheus** | Nadie raspa el proxy (F-02 de `revisiones/U08-T05/ronda-1.md`). Lo corrige U01-T09 (`tareas/U01-T09-metricas-del-proxy-de-linkerd.md`), sin probar en clúster |
| Permisos de lectura | `platform/rbac/verification-operator/k16.yaml`, líneas 28 a 70 | En `vectra-app`: `jobs` y `pods` con `get`, `list` y `watch`; `pods/log` con `get` |
| Retención en kind | `platform/observability/values/kube-prometheus-stack-kind.yaml`, línea 5 | `retention: 3d` |

**RT-3 / D1**

| Qué | Dónde está | Valor real |
|---|---|---|
| Registro por el BFF | `contracts/openapi/role-endpoint-matrix.md`, línea 39 | `POST /api/console/models`: solo `ingeniero_riesgo`, con MFA. Cuerpo `ModelRegistration` (`vectra_contracts/models/governance.py`, líneas 96 a 105) |
| Rechazo de U4 | `governance/src/vectra_governance/api.py`, líneas 125 a 130; `registration.py`, línea 56 | 422, `code = validation_error`, `invalid_params = [{name: "package", reason_code: <motivo>}]`. El BFF reenvía `invalid_params` (`console/bff/src/console_bff/errors.py`, líneas 68 a 87) |
| Motivo de cada paquete | `governance/tests/property/test_registration.py`, líneas 224 a 226 | RT3-a: `model_version_id_mismatch_inside:explainer.json`; RT3-c: `model_version_id_mismatch_inside:feature_dictionary.json`; RT3-d: `model_version_id_mismatch:explainer.json` |
| RT3-b lo acepta U4 | `reference-model/src/vectra_reference/adversarial.py`, líneas 371 y 372 | `REJECTED_BY_U4 = ("RT3-a", "RT3-c", "RT3-d")`; `ACCEPTED_BY_U4 = ("RT3-b",)` |
| De dónde salen los 4 paquetes | `reference-model/src/vectra_reference/release.py`, líneas 312 a 317; `adversarial.py`, línea 393 | Son copias del paquete **base**: llevan **el mismo `model_version_id` que el modelo de referencia** |
| Registrar dos veces una versión | `governance/tests/integration/test_api_models.py`, líneas 92 a 95 | 409 |
| `serving-config` | `role-endpoint-matrix.md`, línea 78 | `GET /v1/serving-config` pide el scope `governance:read-serving`. `verification-reader` no lo tiene y el BFF no tiene esa ruta: **U12 no puede leerlo** (P-3) |
| Estados del modelo | `governance/src/vectra_governance/model_fsm.py`, líneas 154 a 172 | `registrado` → `en_validacion` → `lista_para_aprobacion` o `validacion_fallida` → `aprobado` → `activo`. Solo `sync_check` bloquea la validación (`evidence.py`, líneas 1159 a 1166) |
| `ModelPackageIntegrityFailed` | `model-serving/common/src/vectra_serving_common/package_loader.py`, líneas 22 y 56 a 59; `metrics.py`, líneas 21 a 26 | Es una excepción, un evento de log (`ModelPackageIntegrityFailed component=… reason=…`) y el contador `vectra_serving_package_integrity_failed_total{component}`. **No hay alerta** (plan de U6, Paso 9, diferido), el chart de U6 no trae monitor y K16 no da `pods/log` fuera de `vectra-app` |
| Dónde se despliega un paquete sin registrar | `model-serving/docs/values.md`, líneas 31 y 47 a 53 | Perfil `staging` → namespace `vectra-staging`, solo predictor. K16 **no tiene** `Role` en `vectra-staging` |
| Estado del caso por el BFF | `vectra_contracts/models/api.py`, líneas 103 a 113; `case-management/src/vectra_case/views.py`, líneas 29 y 100 | `CaseDetail.state`, `attempts` y `last_cause`. `last_cause` solo va en `en_sincronizacion` y `no_disponible` |
| Causas | `vectra_contracts/catalog.py`, líneas 75 a 87 y 124 a 127 | `FailClosedCause`: `timeout`, `explainer_unavailable`, `explainer_error`, `feature_dictionary_incomplete`, `model_frozen`, …; `LocalCause`: `serving_config_unavailable`, `scoring_unreachable`, `scoring_rejected` |
| Estados del caso | `vectra_contracts/catalog.py`, líneas 201 a 208 | `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado`, `decidido`, `vencido` |
| Backoff | `case-management/src/vectra_case/backoff.py`; `config.py`, líneas 35 a 38 | 30 s, 1, 2, 4 y 8 min con ±20 %; 6 intentos. `no_disponible` tras ≈ 12,4 a 19,3 min |
| `fail_closed` en el outbox | `case-management/src/vectra_case/evaluation.py`, líneas 258 a 295 | Se escribe **solo al escalar** a `no_disponible`, una por ciclo |
| Proyección `metrics` | `decision-registry/src/vectra_registry/projections.py`, líneas 69 a 81; `vectra_contracts/models/registry.py`, línea 374 | Solo `recommendation`, `human_decision` y `explanation_view`. **`fail_closed` no está**: `verification-reader` no puede leerla |
| Gauge y alerta | `case-management/src/vectra_case/metrics.py`, líneas 54 a 56; `db_gauges.py` (cada 30 s); `platform/observability/rules/platform-rules.yaml`, líneas 143 a 150 | `vectra_cases_failclosed_persistent`; `FailClosedPersistente`: `max(vectra_cases_failclosed_persistent) > 0`, `for: 1m`, `SEV2` |
| F22 y `env_disabled` | `platform/network/flows.yaml`, líneas 5, 6 y 172; `platform/network/generate.py`, línea 391 | `env_disabled: { kind: [], staging: [], prod: [] }`. El PR de la demo pone `kind: [F22]` (enmienda §6, P-19), **no** `enabled: false` |

**RT-2 / D2**

| Qué | Dónde está | Valor real |
|---|---|---|
| Rutas de modelos del BFF | `role-endpoint-matrix.md`, líneas 38 a 44; `contracts/openapi/console-bff.yaml`, líneas 4000 a 4214 | `GET /api/console/models` y `/{id}`: `ingeniero_riesgo`, `cro` y `cumplimiento`. `POST /api/console/models` (200) y `POST …/validations` (200): `ingeniero_riesgo` con MFA. `POST …/approval` (204, cuerpo `ModelApprovalIn`): `cro` con MFA. `POST …/frozen-resolution` (204, cuerpo `FrozenResolutionIn`): `cumplimiento` con MFA |
| MFA reciente | `vectra_contracts/routes/__init__.py`, línea 21 | `MFA_MAX_AGE = 900` s |
| Aprobador distinto | `vectra_contracts/models/governance.py`, líneas 122 y 123; `model_fsm.py`, línea 186 | `ModelVersion.registered_by` y `approved_by`. Si coinciden, U4 responde 409 |
| Informe de validación | `vectra_contracts/models/governance.py`, líneas 139 a 150 | `ModelVersionDetail.validation_report`: `auc_meets_target`, `initial_disparity` y `sync_check`. La variante proxy tiene AUC 0,825 < 0,85 y **aun así pasa**: solo bloquea `sync_check` |
| Validar sin política activa | `CANDIDATAS.md`, línea 349 | 409 `conflict_state` |
| Cuerpo del registro | `governance/docs/kind/registro-cuerpo.sh`, líneas 3 y 16 a 25 | URIs `s3://model-store/<model_version_id>/<archivo>`; `artifact_format: xgboost_json`; SHA-256 del manifiesto del paquete |
| Promoción | `governance/promotion_tool/vectra_promotion/commands.py`, líneas 11 a 36 | `list_promotable`, `create_promotion_pr`, `post_activation_pr`, `rollback_pr` y `mark_active`. **Los ejecuta el operador**, nunca U12 |
| Cron de U9 | `bias-monitoring/chart/values-monitoring-policy.yaml`, líneas 4 a 8; `chart/values.yaml`, líneas 56 a 64 | `schedule: "2,17,32,47 * * * *"` (cada 15 min), `threshold_pp: 5`, `n_min: 30`, `stale_after: 1h`; `successfulJobsHistoryLimit: 3` |
| Métricas de la corrida de U9 | `bias-monitoring/src/vectra_bias/publish.py`, líneas 130 a 137 | `vectra_bias_last_run_timestamp` (segundos del fin de la corrida), `vectra_bias_last_run_ok` y `vectra_bias_last_run_failure{reason}`, por el Pushgateway |
| La entrada `freeze` | `vectra_contracts/models/registry.py`, líneas 397 a 405 | `FreezeProjection`: `seq`, `freeze_id`, `model_version_id`, `frozen_at`, `recorded_at` y `context_package` |
| El paquete | `vectra_contracts/models/monitoring.py`, líneas 189 a 226 | `FreezeContextPackage` = `FreezeContext` (`model_version_id`, `computed_at`, `threshold_pp`, `n_min`, `window_days`, `schedule`, `stale_after_s`, `library_version`, `window_start`, `before`, `after`, `last_7_days`, `trigger_attribute`, `implicated`, `affected_volume`, `truncated`) + `data_sources: list` + `initial_disparity: InitialDisparity`. «`initial_disparity` no vacía» = `initial_disparity.attributes` con al menos un elemento |
| Quién lee `monitoring_freezes` | `decision-registry/src/vectra_registry/projections.py`, líneas 49 a 54 y 77 a 80 | El scope `registry:read:monitoring`. Devuelve entradas `freeze` y `frozen_resolution` (`seq`, `model_version_id`, `action`, `recorded_at`) |
| Reactivar | `model_fsm.py`, líneas 165 a 168 | `congelado` + `reactivar` → `activo`; `investigar` → sigue `congelado` |
| Barrido de U8 | `case-management/src/vectra_case/sweeps.py`, líneas 1 a 50; `config.py`, línea 75 | Cada 300 s: con la versión `activo`, los `modelo_congelado` pasan a `en_evaluacion` |
| Vuelta al modelo de referencia | `model_fsm.py`, líneas 163 y 164 | `inactivo` + `mark_active` → `activo`; la que estaba activa pasa a `inactivo` |

**`SIM-NORMAL` / D4**

| Qué | Dónde está | Valor real |
|---|---|---|
| La corrida | `simulator.RunReport` (U12-T02) | `sent`, `accepted`, `rejected_by_code`, `case_ids` |
| El estado de cada caso | `GET /api/console/cases/{id}` con `analista-1` (`role-endpoint-matrix.md`, líneas 18 y 20) | `CaseDetail.state` y `last_cause` |
| Definición | `aidlc-docs/construction/system-verification/functional-design/domain-entities.md` §4.1 | «`accepted = sent`, un caso por solicitud aceptada y cada caso llega a `listo` o a un estado de fail-closed documentado» |

### Precisiones

**Generales**

- **Resultado de tres valores** (`scenarios/outcome.py`; BR-U12-11; NFR-U12-42). Todo oráculo devuelve uno de `pasa`, `falla` o `no ejecutado` (las constantes de `report`), con:
  - `expected` y `obtained` en texto: son iguales si y solo si el resultado es `pasa`;
  - **qué faltó**: una lista de códigos estables, no vacía en `falla` y en `no ejecutado`, vacía en `pasa`. Cada forma incorrecta tiene **su** código, y el código nombra el campo, el estado, la serie o el paso que faltó. Un `falla` genérico («oráculo no cumplido») es un hallazgo;
  - los sub-resultados (por paquete de RT-3, por fase de RT-2), cada uno con su resultado y su código;
  - las consultas a Prometheus usadas, con su texto y su ventana (`QueryResult` de U12-T02; NFR-U12-50);
  - las lecturas (estados, conteos, mediciones). **Sin datos del solicitante:** solo `case_id` y conteos.
- **`no ejecutado` no es una `Evidence`.** `report.Evidence.result` solo admite `pasa` o `falla`. La conversión a `Evidence` devuelve **nada** cuando el resultado es `no ejecutado`: así el informe lo marca `no ejecutado` por falta de evidencia (BR-U12-11). El motivo se conserva en el resultado, para que U12-T04 lo escriba junto al manifiesto.
- **`falla` frente a `no ejecutado`.** `falla`: el sistema respondió y no cumplió. `no ejecutado`: faltó un prerrequisito y el oráculo no pudo juzgar (el Job no existe o es de otro `runId`, la retención no cubre t0, el operador no hizo su paso, K16 no deja leer, Prometheus o el registro no responden). Un prerrequisito ausente **nunca** da `pasa` ni `falla`.
- **Oráculo puro, lecturas aparte.** Cada escenario separa la función que **lee** (clientes de U12-T02) de la que **juzga** (pura: recibe lecturas y devuelve el resultado). `test_oracles_*.py` prueba la que juzga con respuestas de ejemplo; las de integración prueban la que lee.
- **Esperas con el reloj inyectado** (`scenarios/waits.py`). Una sola función de sondeo: condición, intervalo y plazo, con `Clock.sleep`. Ningún módulo de `scenarios/` llama a `time.sleep`, `time.time` ni `datetime.now`. Las esperas largas (15 min de la ventana de RT-5, 12 a 19 min de `no_disponible`, 1 800 s de RT-2, 45 min de bias, 300 s del barrido) se prueban con el reloj falso: **cero `sleep` reales**. La única espera real permitida es la de arranque del contenedor de Prometheus (CA-7).
- **Pasos del operador.** U12 no promueve, no sincroniza y no abre PR. Donde el flujo necesita al operador (PR de F22, PR de promoción, `mark_active`, rollback), la sección **espera** la condición observable con el reloj inyectado. Si vence el plazo, el resultado es `no ejecutado` con el código del paso pendiente, y la sección se puede retomar (P-8).
- **Barreras de U12-T01 que siguen en pie:**
  - `test_kubectl_verbs.py` recorre el código nuevo. Los escenarios solo usan `K8sRead.get` y `K8sRead.logs`. **Nada de `argocd`, `helm`, `gh` ni `git`**, tampoco dentro de un texto: los mensajes al operador describen el paso («sincroniza la Application `case-management`») sin escribir la orden. El detector de U12-T01 lee las cadenas.
  - `guard.check_section` al entrar a cada sección, antes de la primera solicitud. La reactivación sale solo de `rt2`: `rt3` y `rt2-setup` no pueden llamar a `resolve_frozen`.
  - Todo lo que un escenario devuelve pasa por `evidence.prepare` sin fallar (CA-13). Ningún token, contraseña, TOTP ni cabecera `Authorization` en un resultado ni en un mensaje de error.
- **import-linter.** Un contrato nuevo: `vectra_verification.scenarios` no importa `httpx`, `requests`, `socket`, `subprocess`, `playwright` ni `pyarrow` (con `allow_indirect_imports`). Toda la E/S pasa por `clients/` y `simulator`.
- **`clients/bff.py` gana las rutas de modelos:** `list_models`, `get_model` (devuelve `ModelVersionDetail`), `register_model(ModelRegistration)`, `start_validation(id)` y `approve_model(id, ModelApprovalIn)`. Con los tipos de `vectra_contracts`; una respuesta 2xx que no valida es un error. Las tres de escritura exigen una sesión de step-up, como `resolve_frozen`. La prueba de U12-T02 que recorre todos los métodos públicos (cabecera y prefijo) debe cubrirlas. `ApiError` gana `invalid_params`.
- **MFA de 900 s.** Antes de cada escritura con MFA (`register_model`, `start_validation`, `approve_model`, `resolve_frozen`), si el `auth_time` de la sesión tiene más de ≈ 800 s, la sección hace un step-up nuevo. Un 401 o 403 por MFA vencido no se reintenta a ciegas: un step-up y **una** repetición.
- **`scenarios.md`.** Firmas de cada sección; por oráculo, la tabla «ruta, campo, valor» de arriba tal como quedó; los códigos de «qué faltó»; la decisión de cada P-n; la tabla BR-U12-04, 06, 07 y 10 → prueba; la precisión de NFR-U12-11; y lo que T04 y T05 pueden llamar.

**Paso 8 — RT-5** (BR-U12-04; INF-U12-02; NFR-U12-50)

- **Entradas:** el `runId` y el `started_at` de la verificación llegan por parámetro (`manifest.py` es de U12-T04).
- **Lectura del Job:** `K8sRead.get("job/rt5-demo-<runId>", "vectra-app")`. De su JSON: `status.startTime` (t0), `status.completionTime` (t1), `status.succeeded`, `status.failed` y `status.conditions`.
- **Frescura** (la regla de X04 y X06): el nombre debe ser exactamente `rt5-demo-<runId>` y `completionTime` posterior a `started_at`. Si no → `no ejecutado`. El Job no existe → `no ejecutado` (falta el PR del parche de `probes.runId`).
- **Un Job fallido no tiene `completionTime`.** Kubernetes solo lo pone al completar. Con `status.failed ≥ 1` o la condición `Failed`, el resultado es `falla` con la línea del log (el código no fue 403, o no hubo respuesta). No es `no ejecutado`. Un Job todavía activo: espera hasta `activeDeadlineSeconds` (300 s) más un margen; si no termina → `no ejecutado`.
- **Log:** el pod se toma con `get("pods", "vectra-app", selector="job-name=rt5-demo-<runId>")` y se lee con `K8sRead.logs`. El oráculo **analiza** la línea `rt5-demo: POST … -> <código> l5d-proxy-error: <valor>`:
  - código 403 y valor presente, no vacío y distinto de `None` → cumple;
  - código 403 con `l5d-proxy-error: None` → `falla` (el 403 es de la aplicación: Linkerd dejó pasar la llamada);
  - buscar el texto `l5d-proxy-error` no sirve: la línea lo trae siempre.
- **Prometheus, anclado al Job**, con `PromClient.query_range` y `step = 15 s`. Las tres expresiones y la de retención son **las del plan, literales**. El máximo y la presencia se calculan en Python.
  - Si la ventana tiene más de 11 000 puntos (a 15 s, más de 45,8 h), Prometheus rechaza la consulta: parte la ventana y une los puntos. CA-7 lo comprueba contra el Prometheus real.
  - La sección puede correr justo después del Job: sondea cada 15 s (reloj inyectado) hasta que haya un punto de la alerta y la serie de denegaciones tenga máximo ≥ 1, o hasta `t1 + 15 min`. Juzga una sola vez, al salir del sondeo.
- **Qué serie falta, dicho con claridad** (F-02 de `revisiones/U08-T05/ronda-1.md`). Si la serie de denegaciones no tiene puntos en la ventana, el resultado es `falla` (así lo manda el plan) y el código **nombra la serie completa**, con sus etiquetas. Además, el oráculo hace una consulta instantánea de `count(inbound_http_authz_deny_total)`:
  - sin ninguna serie de esa familia → el mensaje añade que Prometheus no raspa el proxy de Linkerd de `vectra-mock` (U01-T09);
  - hay series, pero ninguna con esas dos etiquetas → el mensaje lista las etiquetas `namespace` y `route_name` que sí existen.
  Si falta la alerta **y** falta la serie, el mensaje dice las dos cosas y cuál es la causa probable. Lo mismo para `vectra_core_write_attempts_total`: una serie ausente es `falla` con su nombre, no un `pasa` por «máximo 0 de nada».
- **Retención:** `prometheus_tsdb_lowest_timestamp_seconds` > t0 → `no ejecutado`, nunca `pasa`. En kind la retención es de 3 días.

**Paso 8 — RT-3** (BR-U12-04, 10)

- **Sub-resultados**, cada uno con su resultado y su código: `RT3-a`, `RT3-c`, `RT3-d` (registro), `RT3-a-desplegado`, `RT3-d-desplegado`, `RT3-b` y `F22`. Cómo se combinan en el resultado de `RT-3`: P-2.
- **RT3-a, c y d.** `ingeniero-1` con step-up → `register_model`. Cumple solo un 422 con `code = validation_error` e `invalid_params` con `name = "package"`. El `reason_code` se guarda en la lectura; si viene y no es el de la tabla, `falla`. Un 200 («aceptado por U4») → `falla`. Cualquier otro estado → `falla` con el estado y el código.
- **«Sin cambio en `serving-config`»** (P-3): antes y después de los tres registros, `list_models` (todas las páginas). Cumple si el conjunto de `model_version_id` es el mismo, cada uno con el mismo `state`, y la versión `activo` es la misma. Una versión nueva o un cambio de estado → `falla`.
- **URIs del cuerpo.** Los cuatro paquetes RT-3 llevan el `model_version_id` del modelo de referencia, así que **no** pueden usar la convención `s3://model-store/<model_version_id>/`: el prefijo de cada paquete en el model-store llega por parámetro. Los SHA-256 salen del `manifest.json` del paquete local (`reference-model/.out/adversarial/rt3/<caso>/`), como en `registro-cuerpo.sh`.
- **RT3-a y d desplegados sin registrar.** `K8sRead.get("inferenceservice/<nombre>", "vectra-staging")`. Cumple si la condición `Ready` no es `True` y sigue sin serlo tras un plazo. Si `kubectl` responde `Forbidden` (K16 no llega a `vectra-staging`) → `no ejecutado` con ese código. La causa `ModelPackageIntegrityFailed` hoy no se puede leer; el sub-resultado lo dice (`causa_no_leida`). Ver P-2 y «Contradicciones» 4.
- **RT3-b.** `register_model`:
  - 409 → `no ejecutado` (`rt3b_version_ya_registrada`): el paquete comparte `model_version_id` con el modelo de referencia. Ver P-2 y «Contradicciones» 3;
  - 200 → `start_validation` y espera: `validacion_fallida` → cumple. Si llega a `lista_para_aprobacion`: `cro-1` aprueba, la sección espera al operador (`activo`), envía los casos de sonda y cumple si quedan en fail-closed con `last_cause` `explainer_error` o `feature_dictionary_incomplete` y sin ninguna `recommendation` de esa versión; después espera el rollback.
- **F22 apagado** (la evidencia de `journey-7-3`). El operador ya sincronizó el PR de `env_disabled.kind: [F22]`; la sección no puede comprobarlo antes (K16 no lee `NetworkPolicy`): lo dicen los casos.
  1. Envía los casos de sonda (`normal`, 5 por omisión: P-11) con `Simulator.run(…, section="rt3")`.
  2. Espera a que cada caso tenga `attempts ≥ 1` o esté en un estado final.
  3. Lee cada caso por el BFF con `analista-1` (`get_case`). Cumple si **todos** están en `en_sincronizacion` o `no_disponible` y **al menos uno** tiene `last_cause` `timeout` o `explainer_unavailable`. Un caso en `listo` → `falla`. Ninguno con esas dos causas → `falla` con las causas vistas.
  4. Lee el registro: `RegistryClient.metrics(entry_type="recommendation", recorded_from=<inicio de la sonda>, recorded_to=<fin>)`. Cumple si no hay **ninguna**, de ninguna versión. Una sola → `falla`, con su `case_id` y su `model_version_id`.
  5. Opción `wait_for_escalation`: espera hasta ≈ 20 min (reloj inyectado) a que los casos pasen a `no_disponible`, y lee `max(vectra_cases_failclosed_persistent)` y `ALERTS{alertname="FailClosedPersistente", alertstate="firing"}`. Son **lecturas informativas** para `journey-7-3` (U12-T04): no cambian el resultado de RT-3, porque el Paso 8 no las pide.
- **Cierre** (BR-U12-10): tras la reversión del PR de F22, un caso de sonda nuevo llega a `listo`. Va en un campo propio del resultado (P-9).
- La causa `fail_closed` **no** se lee del registro: `metrics` no trae esa entrada. Se lee de `CaseDetail.last_cause` (P-3).

**Paso 8 — `rt2-setup`** (BR-U12-07)

- **Entradas:** la lista de versiones del proxy (carpetas `reference-model/.out/proxy/run-N`, de 1 a 5; la demo pasa 1). Dos con el mismo `model_version_id` → error **antes** de enviar nada.
- **Por versión:** `ingeniero-1` con step-up → `register_model` (cuerpo con la convención de `registro-cuerpo.sh`) → `start_validation` → espera a que salga de `en_validacion`. Después `cro-1` con step-up → `approve_model` con `decision = "aprobado"`.
- **Termina** cuando todas están `aprobado`. Una en `validacion_fallida` → la sección **se niega a seguir**: no aprueba ninguna más y lo dice.
- **Aprobador distinto:** al final, `get_model`: `approved_by` distinto de `registered_by`. Si U4 responde 409 a la aprobación, es un `falla` con su `reason`.
- **Retoma:** una versión ya `registrado`, `en_validacion`, `lista_para_aprobacion` o `aprobado` no se vuelve a registrar: la sección sigue desde su estado. Un 409 al registrar una versión que ya existe en un estado de ese camino no es un fallo.
- **Prerrequisitos que dan `no ejecutado`:** validar sin política activa (409 `conflict_state`); el `InferenceService` de staging sin desplegar (la validación vence): el mensaje nombra el PR que falta.
- **Aviso temprano:** lee `validation_report.initial_disparity.attributes`. Si viene vacía, lo deja en el resultado (`initial_disparity_vacia`): el oráculo del paquete de RT-2 fallaría una hora después. No cambia el resultado de `rt2-setup`.

**Paso 8 — RT-2** (BR-U12-04, 06, 07, 10; NFR-U12-11)

Por cada versión recibida, en este orden. Cada fase es un sub-resultado.

1. **Regla de las celdas** (decisión del usuario, 2026-11-13). **Antes** de enviar nada: `Simulator.select("stratified", 1 500, semilla)`. De cada celda corta (`taken < 30`):
   - `available ≥ 30` → es **alcanzable y quedó corta**: `rt2` **se niega** (error con las celdas, 0 solicitudes);
   - `available < 30` → es **inalcanzable**: no bloquea. Va al resultado con `attribute`, `group`, `band`, `available` y `taken`.

   Casos: una alcanzable corta → se niega; solo inalcanzables cortas → corre e informa; ninguna corta → corre. La regla es una función pura sobre la tabla de celdas, separada del muestreo: `sampler.stratified` nunca deja corta una celda alcanzable, así que la regla es una defensa y se prueba con una tabla de celdas de doble (CA-8) y con los datos reales de U5 (CA-9).
   El volumen es un piso (`CANDIDATAS.md`, línea 643): el resultado registra el pedido y el enviado. No hay tope.
2. **Promoción.** Espera al operador: `get_model(proxy).state == "activo"`. Después comprueba que la de referencia quedó `inactivo`.
3. **Lote.** `Simulator.run("stratified", 1 500, semilla, section="rt2")`, a 10/s por omisión.
4. **`freeze`.** Sondea `RegistryClient.freezes(recorded_from=<inicio del lote>)` hasta ver un `FreezeProjection` con el `model_version_id` del proxy. Sigue esperando **más allá** de 1 800 s (tope: 2 700 s) para registrar la medición real de una corrida lenta. Sin `freeze` al tope → `falla`, y el mensaje añade la última corrida de bias si Prometheus la tiene (`vectra_bias_last_run_ok` y `vectra_bias_last_run_failure`).
5. **Paquete completo.** El oráculo exige un `FreezeContextPackage` válido, `data_sources` presente (puede ir vacía) e `initial_disparity.attributes` no vacía. `RegistryClient` rechaza con `invalid_response` un paquete que no valida: el oráculo debe convertir eso en `falla` **y decir qué campo falta** (lee la respuesta cruda o valida él mismo con el tipo de U0; amplía `RegistryClient` con una lectura sin validar si hace falta). No puede quedar en un error sin nombre ni en `no ejecutado`.
6. **Versión `congelado`:** `get_model(proxy).state == "congelado"`.
7. **Casos nuevos.** Envía los casos de sonda (`normal`, 5 por omisión) y cumple si todos quedan en `modelo_congelado` (por el BFF). Uno en `listo` → `falla`.
8. **Sigue congelada tras 3 corridas más de bias** (solo en la primera versión). Cuenta 3 corridas completas posteriores al `recorded_at` del `freeze` (P-5). Después: sigue `congelado` y no hay ninguna `frozen_resolution`. Con el cron cada 15 min son ≈ 45 min.
9. **Reactivación.** `cumplimiento-1` con step-up → `resolve_frozen(proxy, action="reactivar", justification=<texto de prueba>, section="rt2")`. Cumple con 204, `get_model(proxy).state == "activo"` y una entrada `frozen_resolution` con `action = "reactivar"` en `monitoring_freezes`.
10. **No se recongela.** Tras al menos 1 corrida completa de bias posterior a la reactivación: ningún `freeze` nuevo de esa versión y sigue `activo`. Un `freeze` nuevo el mismo día → `falla`.
11. **Barrido de U8.** Los casos de sonda de la fase 7 salen de `modelo_congelado` en 300 s más un margen.
12. **Latencia.** `RegistryClient.metrics(entry_type="recommendation", recorded_from=<inicio del lote>)`, filtradas por los `case_ids` del `RunReport`. Todas deben llevar el `model_version_id` del proxy: si el lote lo puntuó otra versión → `falla`. `rt2_latency.measure(run, …)` da la medición. `RT2-LATENCY` es un resultado aparte: `pasa` si el máximo de las corridas hechas es ≤ 1 800 s; si no, `falla` **con la medición registrada**. Sin ninguna `recommendation` del lote → `falla`.
13. **Cierre** (BR-U12-07, 10). Al terminar la última versión: espera al operador (`rollback_pr` y `mark_active`) y comprueba que la de referencia está `activo` y la del proxy `inactivo`. Va en un campo propio (P-9).

- **Precisión de NFR-U12-11 y BR-U12-06** (cambios permitidos 3 y 4). Texto que se añade, sin borrar el original:
  - NFR-U12-11: «*(Precisada en U12-T03, 2026-11-13; decisión del usuario, `DECISIONES-LOOP.md` §10.)* «Alguna celda» es una celda **alcanzable**: una con 30 o más filas disponibles en `test`. Las inalcanzables no hacen que `rt2` se niegue: se informan en la evidencia, con sus filas disponibles y tomadas.»
  - BR-U12-06, fila RT-2: tras «≥ 30 por celda de U9», «(por celda **alcanzable**; precisada en U12-T03, 2026-11-13, `DECISIONES-LOOP.md` §10)».
  - La misma frase va en el docstring de la regla y en `scenarios.md`.

**Paso 10 — `SIM-NORMAL`** (BR-U12-02, 06; domain-entities §4.1)

- **Entradas:** el `RunReport` de la corrida `normal` (los 2 000 de `decisions`) y una sesión de `analista-1`.
- **Oráculo:**
  - `accepted = sent`; `accepted < sent` → `falla` con los conteos de `rejected_by_code`;
  - un caso por solicitud: `len(case_ids) == accepted` y sin repetidos;
  - cada caso (`get_case`, espaciado por debajo de 20/s por usuario): `listo`; o `decidido` (el conductor ya lo decidió: pasó por `listo`, P-7); o un fail-closed documentado: `en_sincronizacion` o `no_disponible` con `last_cause` del catálogo (`FailClosedCause` o `LocalCause`), o `modelo_congelado`;
  - `en_evaluacion` → espera (reloj inyectado) hasta un plazo; si sigue → `falla` con cuántos. `vencido`, o un `last_cause` fuera del catálogo → `falla`.
- El resultado trae el conteo por estado y por causa. Ningún dato del solicitante.
- **No** usa `created_from` ni `created_to` por el BFF: el filtro de fecha de la bandeja da 422 contra el BFF real (`DECISIONES-LOOP.md` §10, U10-T04).

**Plan.** Marca `[x]` los Pasos 8 y 10 con `(U12-T03)`. En el 8, la nota «RT-2 con 1 versión (DD-1)»; en el 10, «`LOGS-NO-PII` y `CASE-SIZE` diferidos por la demo». Los Pasos 7, 8b, 9 y 11 siguen en `[ ]` con la nota «(diferido por la demo: enmienda §3 U12)» antes del título, como hace el plan de U6 con su Paso 9.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Ejecutar las otras 4 versiones del proxy** en `rt2-setup` y `rt2`. Enmienda §3 U12, fila «8»: «RT-2 (1 versión), RT-3 y RT-5»; §1.2: «DD-1 = 1 versión»; alcance §5, DD-1: «**1 en la demo**». El código admite de 1 a 5.
- **`LOGS-NO-PII` y `CASE-SIZE`.** Enmienda §3 U12, fila «10»: «Se difieren `LOGS-NO-PII` (ninguna demo; P-18) y `CASE-SIZE`». No se escriben `scenarios/logs_pii.py` ni `case_size.py`, ni la prueba «un `SYN-` encontrado → `falla`».
- **Pasos 7, 8b, 9 y 11:** RT-1, RT-4, `resilience`, X01–X10 y la carga. Enmienda §3 U12, filas «7» y «8b · 9 · 11»; §1.5, fila U12.
- **Bloques E a H** (Pasos 12 a 19): guiones y `verify/*.sh`, los PR preparados de `demos/prs/`, `cli`, `manifest`, la imagen, el README y la verificación en kind. Aquí las secciones son **funciones** que U12-T04 llamará; no hay CLI.
- **Escribir evidencias en disco.** Es del Paso 13.
- **Promover, sincronizar, abrir PR o llamar a `promotion-tool`.** Lo hace el operador. U12 espera y lee.
- **Editar otras unidades.** Si algo de U1, U3, U4, U5, U6, U8, U9 o U10 no encaja, es candidata. En particular: no se toca K16, no se agrega un scope a `verification-reader`, no se cambia `rt3_package` y no se agrega un monitor.
- **Cualquier llamada a un clúster.** Nada de `kubectl` real ni solicitudes a `vectra.localtest.me`. El kind de la máquina puede estar arriba: no se usa.
- **`mutmut`** (diferido en U12-T01) y **el workflow de CI** (Paso 16, D). `test_rt5_promql.py` corre en `make check`, no en un workflow.
- **`make -C reference-model release`** completo. La prueba con datos reales usa solo el generador (CA-9).

---

## Candidatas (`CANDIDATAS.md`)

**Se atienden aquí:**

| Dónde | Candidata | Qué se hace |
|---|---|---|
| Líneas 333 y 637 | 4 de las 65 celdas de U9 no llegan a 30; «la decisión de qué hace `rt2` es P-8» | La regla de las celdas alcanzables (CA-8, CA-9) y la precisión de NFR-U12-11 y BR-U12-06 (CA-20). Se marcan resueltas |
| Línea 643 | `sampler.stratified`: el volumen es un piso; «U12-T03 debe decidir si `rt2` valida el tamaño devuelto» | `rt2` registra el pedido y el enviado; no pone tope |
| Línea 622 | Nadie raspa el proxy de Linkerd (F-02 de U08-T05) | El oráculo de `rt5` nombra la serie que falta y distingue «nadie raspa el proxy» (CA-5). El arreglo es de U01-T09 |
| Línea 349 | Validar sin política activa da 409 | `rt2-setup` lo convierte en `no ejecutado` con su motivo (CA-10) |
| Línea 252 | La variante proxy tiene AUC 0,825 < 0,85 | `rt2-setup` no exige `auc_meets_target`: solo `sync_check` bloquea. Lo registra en el resultado |
| Línea 641 | Con las secciones diferidas, varias historias saldrán `no ejecutado` | `scenarios.md` lista qué evidencias produce esta tarea y cuáles no |

**Para una tarea posterior de U12** (no las atiendas):

- Línea 640: K16 y el camino a la bóveda de kind. Antes del Paso 18.
- Líneas 615 y 684: `probes.enabled` y los digests de ejemplo. `prepare` y el Paso 18 (U12-T04 y T05).
- Línea 649 (F-06): el detector de verbos rechaza formas legítimas en guiones. Paso 12 (U12-T04).
- Líneas 598 y 619: orden de arranque de U11 y memoria de U8 con 2 000 decisiones. Paso 18.
- Línea 207: marcadores de `LOGS-NO-PII`. Diferido.
- Línea 686: la `aud` de la aserción en `vectra_common.service_token`. No es de U12 (U12 firma la suya con `aud` = emisor), pero sin ese arreglo ningún servicio obtiene token en kind y D1 a D4 no arrancan. Paso 18.
- Las dos del realm de kind que dejó U12-T02 (alias `loa-mfa` y `VERIFY_PROFILE`): si se confirman, el login de `rt2-setup` y `rt2` falla en kind. `DECISIONES-LOOP.md` §10.

---

## Contradicciones entre plan, recorte, diseño y código

Vistas al redactar. Las que romperían una demo, primero. Deja en `CANDIDATAS.md` las que no estén ya.

1. **D3: la serie `inbound_http_authz_deny_total` hoy no existe en Prometheus.** Nadie raspa el proxy de Linkerd, la red no abre el 4191 y no hay `Server` para él. Sin la serie, `CoreWriteAttempt` no dispara y RT-5 sale `falla`. Lo corrige U01-T09, que tampoco se prueba en clúster: las etiquetas reales (`namespace`, `route_name`) se confirman en el Paso 18. Aquí: el oráculo dice qué serie falta (CA-5).
2. **D1: U12 no puede leer la entrada `fail_closed`.** El plan pide «`FailClosed` con `timeout` o `explainer_unavailable`» y la enmienda §1.1 dice que el reconciliador la registra en U3. Pero la proyección `metrics` no trae `fail_closed`, `verification-reader` no tiene otra, y U8 solo la escribe al escalar a `no_disponible` (12 a 19 min después). La causa se lee de `CaseDetail.last_cause` por el BFF (P-3).
3. **D1: RT3-b comparte `model_version_id` con el modelo de referencia.** `write_adversarial` construye los 4 paquetes desde `package/`. En kind el modelo de referencia ya está registrado y activo: registrar RT3-b da **409**, no 200. «`RT3-b`: `validacion_fallida`» no se puede alcanzar con la entrega de U5 tal como sale. RT3-a, c y d no tienen el problema: la validación (422) va antes que el alta (P-2).
4. **D1: «a y d, desplegados por PR sin registrar, no listos con `ModelPackageIntegrityFailed`» no se puede leer con K16.** Por el mismo `model_version_id`, solo caben en `vectra-staging` (en `vectra-serving` chocarían con el `InferenceService` activo: `values.md`, línea 51), y K16 no tiene `Role` allí. Además no existe la alerta (U6 Paso 9, diferido; enmienda §6, P-3: «La de U6 solo si el guion la enseña»), el chart de U6 no trae monitor y K16 no da `pods/log` fuera de `vectra-app` (P-2).
5. **D1: «sin cambio en `serving-config`» no lo puede leer U12.** La ruta pide `governance:read-serving` y el BFF no la expone. Se sustituye por la lista de modelos (P-3).
6. **D2: NFR-U12-11 y BR-U12-06 frente a los datos reales.** 4 de 65 celdas son inalcanzables: al pie de la letra, `rt2` no correría nunca. Resuelta por el usuario (2026-11-13).
7. **D3: el Job sale con 0 ante cualquier 403** y su log siempre contiene el texto `l5d-proxy-error`. El comentario de la plantilla (línea 5) dice «Termina con 0 SOLO si el codigo es 403»: no mira la cabecera. Un Job «Complete» no prueba nada por sí solo: el oráculo analiza el valor (CA-4).
8. **D3: un Job fallido no tiene `completionTime`.** El plan toma `t1 = status.completionTime` sin decir qué pasa si falta. Aquí: `falla` con la línea del log.
9. **D2: «3 corridas más de bias» son ≈ 45 min** con el cron real (`2,17,32,47`). Con la espera del `freeze` (hasta 30 min), el lote y los pasos del operador, D2 con 1 versión dura más de 75 min. NFR-U12-31 habla de «~30 min» por corrida. El guion de `journey-7-4` (U12-T04) debe contarlo.
10. **D2: U3 puede responder 504 al cron de U9 con la máquina cargada** (U03-T07 aparcada, `DECISIONES-LOOP.md` §9). Sin corrida de bias no hay `freeze` y RT-2 sale `falla`. El mensaje añade el estado de la última corrida de bias.
11. **D2: `rt2_latency.RUNS` es 1..5 y `RT2-LATENCY` dice «las 5 corridas»** (domain-entities §4.1), pero DD-1 corre 1. Resuelta con P-12.
12. **D1: tiempos de `no_disponible`.** El plan y BR-U12-04 dicen «≈ 15,5 min»; la enmienda, «≈ 12,4–19,3 min». Las dos salen de `backoff.py` (nominal y con ±20 %). Quien espere a `no_disponible` espera al menos 19,3 min más un margen.
13. **`Evidence.result` no admite `no ejecutado`**, y el plan pide ese resultado en RT-5. No se contradicen: `no ejecutado` es la ausencia de evidencia (BR-U12-11).
14. **BR-U12-04 dice que el PR de F22 pone `enabled: false`;** la enmienda §6, P-19, manda `env_disabled.kind`. Rige la enmienda. Aquí solo afecta a los textos al operador.
15. **MFA de 900 s.** Las cuatro escrituras de RT-2 y RT-3 piden MFA reciente, y las esperas son de 30 a 45 min. Ni el plan ni el diseño dicen cuándo repetir el step-up. Aquí: antes de cada escritura.
16. **Dónde están los paquetes RT-3 en el model-store.** `reference-model/docs/release.md` describe cómo subir el base y las 5 corridas proxy, no `adversarial/rt3/*`; `model-serving/tests/fixtures/` usa `s3://model-store/adversarial/rt3-a/`. Aquí llega por parámetro; U12-T04 lo fija en el guion.
17. **Límite de 11 000 puntos de `query_range`.** La ventana [`started_at`, ahora] a 15 s lo supera a las 45,8 h. El plan no lo prevé.
18. **§1 del plan no tiene módulo para `SIM-NORMAL`, `rt2-setup`, el resultado ni las esperas.** Resuelta con P-4.
19. **El plan pide Prometheus «por digest con Testcontainers»** y la imagen no está en el Docker local. Resuelta con P-1.

---

## Preguntas abiertas

**P-1 y P-2 necesitan la decisión del usuario antes de despachar.** Las demás no: si nadie responde, rige la recomendación y el codificador la anota en `scenarios.md`.

- **P-1 — Prometheus real para `test_rt5_promql.py` (necesita al usuario).** El plan lo exige y la imagen no está en el Docker local (`docker images` al redactar: ninguna de Prometheus).
  - (a) **Recomendada.** Autorizar la descarga de la imagen de Prometheus **con el digest de la plataforma** (`platform/observability/values/kube-prometheus-stack.yaml`, línea 20: `sha256:451a845b…`; el registro y el repositorio son los del chart `kube-prometheus-stack`), leído en la prueba. ≈ 0,1 GB (estimación). `promtool` se usa **desde esa misma imagen**: no hace falta en el host.
  - (b) Sin imagen: el binario `prometheus` del mismo tarball que `platform/install-tools.sh` ya baja y verifica (`platform/tools.env`, línea 4: `v3.15.1`), como proceso local en un puerto libre. No cumple «Testcontainers por digest» y puede no ser la versión de kind.
  - (c) Sin autorización y sin (b), la aceptación del plan no se puede cumplir y hay que decidir qué la reemplaza.
- **P-2 — Qué sub-resultados deciden RT-3 en la demo (necesita al usuario).** Por «Contradicciones» 3 y 4, hoy dos sub-resultados no pueden pasar en kind: `RT3-b` (409) y `RT3-a/d-desplegado` (K16).
  - (a) **Recomendada.** RT-3 `pasa` si pasan RT3-a, c y d (422 y sin cambios en los modelos) y `F22`. `RT3-b` y los dos «desplegados» se calculan siempre y salen en la evidencia con su estado: un `no ejecutado` suyo **no** baja RT-3; un `falla` suyo **sí**. Es la evidencia que la enmienda llama «la evidencia de la demo» (§1.1).
  - (b) Estricta: los siete son obligatorios. RT-3 y US-111 salen `no ejecutado` en la demo hasta que cambien U5 y U1.
  - (c) Arreglar los prerrequisitos y exigirlo todo: el operador genera RT3-b desde un paquete **no registrado** (por ejemplo `proxy/run-5`, que DD-1 deja libre) con la función pública `vectra_reference.adversarial.rt3_package`, y U1 amplía K16 con `inferenceservices` y `pods/log` en `vectra-staging`. No cambia U5. Son dos candidatas (guion de U12-T04 y una tarea corta de U1).
  - El código es el mismo en los tres casos: solo cambia una constante que dice qué sub-resultados son obligatorios. Con (a) hoy, (c) se puede adoptar después sin reescribir oráculos.
- **P-3 — Dónde lee el oráculo lo que el plan nombra y U12 no alcanza.**
  - (a) **Recomendada.** «Sin cambio en `serving-config`» → la lista de modelos por el BFF, antes y después. La causa del fail-closed → `CaseDetail.last_cause` por el BFF. `scenarios.md` dice que son sustitutos y por qué.
  - (b) Pedir a U2 un scope más para `verification-reader` y a U3 que `metrics` traiga `fail_closed`. Cambia tres unidades.
- **P-4 — Módulos que §1 del plan no tiene.**
  - (a) **Recomendada.** `scenarios/outcome.py`, `scenarios/waits.py` y `scenarios/sim_normal.py`, nuevos; `rt2-setup` dentro de `scenarios/rt2.py`.
  - (b) `SIM-NORMAL` dentro de `simulator.py` y el resultado dentro de `report.py`. No cambia §1, pero `report` es puro y no puede importar `scenarios`, y mezcla el envío con su oráculo.
- **P-5 — Cómo se cuentan las corridas de bias** («3 corridas más» y «no se recongela»).
  - (a) **Recomendada.** Por Prometheus: valores distintos y crecientes de `max(vectra_bias_last_run_timestamp)` posteriores al instante de referencia, con `vectra_bias_last_run_ok == 1` en ese punto. Una corrida fallida no cuenta. Las consultas van a la evidencia.
  - (b) Por tiempo: esperar 3 intervalos del cron. No prueba que las corridas ocurrieron.
  - (c) Por `kubectl get jobs`: el historial es de 3 Jobs exitosos; justo y frágil.
- **P-6 — Dobles frente a servicios reales.**
  - (a) **Recomendada.** RT-3, registro: el BFF real en proceso encadenado a la app real de governance (`governance/tests/integration/api_support.py`, `ApiWorld`, sobre PostgreSQL de Testcontainers) y los paquetes de `rt3_package` sobre un paquete real chico (`run_release` con 6 000 filas, como `governance/tests/integration/conftest.py`). Casos y estados: el BFF real con los dobles de U10 (`real_bff.py`). Registro: el doble de U12-T02, validado contra `contracts/openapi/decision-registry-service.yaml`. Prometheus: el doble se valida corriendo **los mismos casos** contra el Prometheus real (CA-7). `kubectl`: el doble de U12-T02, con el JSON de un Job con la forma de `batch/v1`.
  - (b) Si la cadena con governance no sale en 1 h: el doble de governance de U10, configurado con el `Problem` que produce la función real `vectra_governance.registration.validate_registration` sobre los bytes de `rt3_package`. Anótalo.
  - (c) Solo dobles escritos a mano. Es lo que la lección prohíbe.
- **P-7 — `SIM-NORMAL` y los casos ya decididos.** El conductor decide los casos justo después del simulador.
  - (a) **Recomendada.** `decidido` cuenta como «llegó a `listo`». `en_evaluacion` espera hasta un plazo y después es `falla`.
  - (b) Solo `listo`. Entonces `SIM-NORMAL` tendría que correr entre el simulador y el conductor, y `decisions` es una sola sección.
- **P-8 — Qué pasa cuando el operador no ha hecho su paso.**
  - (a) **Recomendada.** La sección sondea con el reloj inyectado hasta un plazo por parámetro (3 600 s por omisión). Al vencer: `no ejecutado`, con el código del paso pendiente, y se puede retomar desde esa fase.
  - (b) Bloquear sin plazo. Una sección colgada no deja evidencia.
- **P-9 — El cierre de RT-2 y de RT-3 en el resultado** (BR-U12-10).
  - (a) **Recomendada.** Un campo `cierre` aparte, con su estado. No cambia el resultado del RT, pero la sección no se da por terminada sin él.
  - (b) El cierre es parte del oráculo: sin rollback, RT-2 es `falla`. Mezcla lo que el sistema hizo con lo que el operador no ha hecho.
- **P-10 — La prueba de las celdas con los datos reales de U5.**
  - (a) **Recomendada.** Dentro de `make check`: genera `test` con el generador real y la configuración completa (120 000 filas, 18 000 en `test`). Medido al redactar: 12 s de generación y 17 s en total, con carga 5.
  - (b) Si en tu máquina pasa de 2 min: fuera de `make check`, con un objetivo propio del `Makefile`, y lo anotas.
- **P-11 — Cuántos casos de sonda** (F22 apagado; «casos nuevos» de RT-2). El plan no lo dice.
  - (a) **Recomendada.** 5 casos `normal`, por parámetro.
  - (b) 1. Un solo caso puede caer en fail-closed por otra causa y dar un falso `pasa`.
- **P-12 — `RT2-LATENCY` con 1 medición.**
  - (a) **Recomendada.** `pasa` si el máximo de las corridas **hechas** es ≤ 1 800 s; la evidencia dice cuántas fueron y cita DD-1.
  - (b) Exigir 5: `RT2-LATENCY` y US-303 saldrían `no ejecutado` en la demo.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, Bloque D, y los Pasos 12, 13 y 18, que usan lo de esta tarea)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1 entero, §2, §3 U12, §5.1, §5.3, §6, §8) y `demo-kind-alcance.md` (§3 U12, §5, §6)
- `DECISIONES-LOOP.md` (§6, §9 y §10)
- `aidlc-docs/construction/system-verification/functional-design/business-rules.md` (BR-U12-04, 06, 07, 10, 11), `business-logic-model.md` (§2 y §3) y `domain-entities.md` (§2 a §4)
- `aidlc-docs/construction/system-verification/nfr-requirements/nfr-requirements.md` (NFR-U12-03, 05, 11, 42, 43, 50) e `infrastructure-design/infrastructure-design.md` (INF-U12-02 y 03)
- `aidlc-docs/construction/system-verification/code/clients.md` y `logic.md`; `tareas/U12-T02-clientes-simulador-y-conductor.md`; `bitacoras/U12-T02.md`
- `revisiones/U12-T01/ronda-1.md` y `ronda-2.md`: el tipo de defecto que el revisor busca en U12 (barreras que se burlan, generadores débiles, falsos positivos)
- `revisiones/U08-T05/ronda-1.md` (F-02) y `tareas/U01-T09-metricas-del-proxy-de-linkerd.md`
- Los archivos de «Lo que cada oráculo lee de verdad»
- `CANDIDATAS.md`: las líneas citadas en «Candidatas»

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Los comandos del plan abrevian rutas; aquí van completas. Ningún criterio admite pruebas omitidas ni `xfail`: sin Docker, la prueba **falla**.

En los criterios de oráculos, «correcta → `pasa`» e «incorrecta → `falla`» significan: una prueba por cada forma, con su nombre, y la incorrecta comprueba **el código de «qué faltó»**, no solo el resultado (NFR-U12-42).

- [ ] **CA-1** — Estructura, dependencias y contratos de imports (Paso 8; NFR-U12-01).
  ```bash
  uv sync --frozen && uv run lint-imports --config system-verification/.importlinter && cd system-verification && for p in src/vectra_verification/scenarios/outcome.py src/vectra_verification/scenarios/rt5.py src/vectra_verification/scenarios/rt3.py src/vectra_verification/scenarios/rt2.py src/vectra_verification/scenarios/sim_normal.py tests/unit/test_oracles_rt2_rt3_rt5.py tests/unit/test_oracles_measurements.py tests/integration/test_rt5_promql.py; do test -s "$p" || echo "FALTA $p"; done; for p in rt1 rt4 x_network x_behavior logs_pii case_size; do test ! -e "src/vectra_verification/scenarios/$p.py" || echo "SOBRA $p"; done; test ! -e Dockerfile && test ! -e chart && test ! -e demos/prs && ! find tests -name __init__.py | grep -q . && echo OK
  ```
  Esperado: `Contracts: 7 kept, 0 broken.` (los 6 de U12-T02 y el nuevo); ninguna línea `FALTA` ni `SOBRA`; `OK`. **Rojo primero:** un `import httpx` en `scenarios/rt5.py` y un `import subprocess` en `scenarios/rt2.py` rompen cada uno su contrato; regístralo.

- [ ] **CA-2** — Las barreras de U12-T01 cubren el código nuevo (NFR-U12-03, 43; BR-U12-10).
  ```bash
  uv run pytest system-verification/tests/unit/test_kubectl_verbs.py system-verification/tests/unit/test_guard.py -v && uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py -v -k guard && ! grep -rnE "argocd|helm (install|upgrade|template)|gh pr|git (push|commit)|time\.sleep|datetime\.now|time\.time" system-verification/src/vectra_verification/scenarios; echo "limpio=$?"; git diff origin/main...HEAD --stat -- system-verification/tests/unit/test_kubectl_verbs.py system-verification/tests/fixtures/kubectl
  ```
  Esperado: código 0 y `limpio=0`. El detector de verbos **no cambia** (el `--stat` no lo lista, o solo muestra casos agregados) y `scenarios/` está entre los archivos que recorre. Además pasan, en la segunda orden (`-k guard`):
  - `rt5`, `rt3`, `rt2-setup` y `rt2` en staging → `GuardError` y **0** solicitudes (HTTP y `kubectl`);
  - `resolve_frozen` llamado desde `rt3` o desde `rt2-setup` → `GuardError` y 0 solicitudes;
  - host o `issuer` de producción → 0 solicitudes.

  **Rojo primero:** un mensaje al operador con la orden literal de sincronizar de `argocd` hace fallar `test_real_files_have_no_findings`; regístralo y quítalo.

- [ ] **CA-3** — El resultado de tres valores y «qué faltó» (BR-U12-11; NFR-U12-42).
  ```bash
  uv run pytest system-verification/tests/unit/test_scenario_outcome.py -v
  ```
  Esperado: pasan:
  - `pasa` con «qué faltó» no vacío, y `falla` o `no ejecutado` con «qué faltó» vacío → no se pueden construir;
  - `expected == obtained` si y solo si `pasa`;
  - la conversión a `report.Evidence`: `pasa` y `falla` dan una `Evidence` válida con el `id` correcto (`RT-2`, `RT2-LATENCY`, `RT-3`, `RT-5`, `SIM-NORMAL`); `no ejecutado` **no da ninguna**;
  - con esa salida, `report.build` marca el elemento `no ejecutado` cuando no hay evidencia, y `falla` cuando la hay con `expected ≠ obtained`;
  - la combinación de sub-resultados: un `falla` obligatorio → `falla`; ningún `falla` y un obligatorio `no ejecutado` → `no ejecutado`; un opcional `no ejecutado` no baja el resultado; un opcional `falla` sí (P-2).

  **Rojo primero:** convertir `no ejecutado` en una `Evidence` con `result = "pasa"` hace fallar el tercer caso; regístralo.

- [ ] **CA-4** — Oráculo de RT-5 con dobles (Paso 8, «Aceptación»; BR-U12-04; INF-U12-02).
  ```bash
  uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py -v -k rt5
  ```
  Esperado: pasan, cada uno con su nombre:
  - Job completo, log con 403 y `l5d-proxy-error` con valor, alerta en la ventana, serie de denegaciones con máximo ≥ 1 y contador del mock en 0 → `pasa`;
  - **RT-5 con un 403 sin `l5d-proxy-error` (de la aplicación) → `falla`**: la línea real `… -> 403 l5d-proxy-error: None`;
  - log con otro código (200, 500) o sin la línea → `falla`;
  - **RT-5 evaluado 6 h después del Job con un doble de Prometheus que tiene la alerta solo en [t0, t1 + 5 min] → `pasa`, y con la alerta fuera de esa ventana → `falla`**;
  - **retención que no cubre t0 → `no ejecutado`**;
  - **la serie de denegaciones nace en 1 dentro de la ventana y no vuelve a crecer → `pasa`; la serie ausente en la ventana → `falla`**;
  - **contador del mock > 0 → `falla`; sin `CoreWriteAttempt` → `falla`**;
  - la serie del contador del mock ausente → `falla` con su nombre;
  - Job de otro `runId`, o con `completionTime` anterior o igual a `started_at`, o inexistente → `no ejecutado`, cada uno con su código;
  - Job fallido (sin `completionTime`, `status.failed = 1`) → `falla` con la línea del log; Job que no termina en el plazo → `no ejecutado`;
  - Prometheus o `kubectl` no responden → `no ejecutado`;
  - las consultas son **las del plan, literales**, con `start`, `end` y `step = 15 s`; ninguna usa `increase(` ni un rango dentro de PromQL; todas quedan en el resultado con su texto y su ventana;
  - una ventana de más de 11 000 puntos se parte y los puntos se unen.

  **Rojo primero** (regístralos): (1) decidir «403 del proxy» buscando el texto `l5d-proxy-error` en el log → el caso de la aplicación debe matarlo; (2) consultar «ahora» en vez de [t0, t1 + 15 min] → el caso de las 6 h debe matarlo; (3) usar `increase()` sobre la serie de denegaciones → el caso «nace en 1» debe matarlo.

- [ ] **CA-5** — RT-5 dice qué serie falta (F-02 de `revisiones/U08-T05/ronda-1.md`; NFR-U12-42).
  ```bash
  uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py -v -k "rt5 and missing"
  ```
  Esperado: pasan, comprobando el texto de «qué faltó»:
  - Prometheus sin ninguna serie `inbound_http_authz_deny_total` → `falla`; el mensaje contiene la serie con sus dos etiquetas (`namespace="vectra-mock"` y `route_name="core-mock-catch-all"`) y dice que nadie raspa el proxy de Linkerd de `vectra-mock`;
  - hay series de esa familia con otras etiquetas → `falla`; el mensaje lista las etiquetas que sí existen;
  - falta la serie y falta la alerta → un solo resultado con los dos códigos, la serie primero;
  - está la serie y falta solo la alerta → el código de la alerta, sin culpar al raspado.

  **Rojo primero:** devolver el mismo código para los cuatro casos hace fallar tres; regístralo.

- [ ] **CA-6** — El analizador del log está atado al Job real de U8 (lección de la enmienda §8).
  ```bash
  uv run pytest system-verification/tests/unit/test_rt5_job_script.py -v
  ```
  Esperado: pasan. La prueba **lee** `case-management/chart/templates/rt5-demo-job.yaml`, extrae el guion de Python de `args` y lo ejecuta contra un servidor HTTP de la biblioteca estándar en `127.0.0.1` y puerto libre, con `CASE_CORE_URL` y `RT5_CREDIT_ID` de prueba. La salida real del guion se pasa al analizador:
  - el servidor responde 403 con `l5d-proxy-error` → el guion sale con 0 y el analizador ve «403 del proxy»;
  - 403 sin la cabecera → el guion **sale con 0** y el analizador ve «403 de la aplicación»;
  - 200 → el guion sale con 1 y el analizador ve el código;
  - sin servidor → el guion sale con 2 y el analizador ve «sin respuesta».

  Si U8 cambia el formato de la línea, esta prueba falla. **Rojo primero:** cambia en una copia de la plantilla `"->"` por `"=>"`; el analizador debe fallar. Regístralo.

- [ ] **CA-7** — Las consultas de RT-5 contra un Prometheus real (Paso 8, «Además, contra un **Prometheus real**»; P-1).
  ```bash
  uptime; time uv run pytest system-verification/tests/integration/test_rt5_promql.py -v; uptime
  ```
  Esperado: pasan, con Prometheus por digest en Testcontainers sobre un bloque TSDB creado con `promtool tsdb create-blocks-from openmetrics` a partir de fixtures **generados en la prueba, con tiempos relativos a «ahora»**:
  - la serie de denegaciones que nace en 1 y no crece → `pasa`;
  - la alerta solo en [t0, t1 + 5 min], evaluada 6 h después → `pasa`; fuera de la ventana → `falla`;
  - el contador del mock en 0 → `pasa`; en 1 → `falla`;
  - t0 anterior al primer dato → `no ejecutado`;
  - cada expresión del oráculo la acepta la API (ningún `bad_data`), incluida la de retención;
  - una ventana de más de 11 000 puntos, sin partir, da el error real de Prometheus, y partida, no;
  - **los mismos casos**, con el doble de Prometheus de CA-4, dan el mismo resultado: la prueba corre los dos y los compara.

  Tiempo esperado: menos de 3 min (estimación: arranque del contenedor y un raspado propio). Anota el real. **Rojo primero:** una expresión con un rango `[t0, …]` dentro de PromQL da `bad_data` contra el Prometheus real; regístralo.

- [ ] **CA-8** — La regla de las celdas alcanzables (NFR-U12-11 precisada; BR-U12-06; decisión del usuario).
  ```bash
  uv run pytest system-verification/tests/unit/test_rt2_cells.py -v
  ```
  Esperado: pasan, con una tabla de celdas de doble (`sampler.CellReport`) y con poblaciones de fixture:
  - una celda con `available = 40` y `taken = 12` (alcanzable y corta) → `rt2` **se niega**: el error nombra la celda y el simulador envió **0** solicitudes;
  - solo celdas cortas con `available < 30` (por ejemplo 12, 21, 4 y 10 disponibles) → `rt2` **corre**, y el resultado las trae con `attribute`, `group`, `band`, `available` y `taken`;
  - ninguna corta → corre y la lista de inalcanzables va vacía;
  - una alcanzable corta **y** varias inalcanzables → se niega (gana la alcanzable) y el error lista solo las alcanzables;
  - frontera: `available = 30` y `taken = 29` → se niega; `available = 29` y `taken = 29` → corre e informa; `available = 30` y `taken = 30` → corre;
  - una población de fixture con una celda de 5 filas: `sampler.stratified` real + la regla → corre e informa esa celda (es la prueba de NFR-U12-11, con su precisión);
  - el volumen pedido y el enviado quedan en el resultado.

  **Rojo primero:** la regla del NFR original (negarse si **cualquier** celda queda corta) hace fallar el segundo caso; la regla contraria (no negarse nunca) hace fallar el primero. Regístralos.

- [ ] **CA-9** — La regla, atada a los datos reales de U5 (P-10).
  ```bash
  uptime; time uv run pytest system-verification/tests/integration/test_rt2_cells_real_u5.py -v; uptime
  ```
  Esperado: pasan. La prueba genera la partición `test` con el **generador real y la configuración completa** de U5 (`vectra_reference.generate.generate` con `load_config()`, sin `with_overrides`; solo datos, sin entrenar), en una carpeta temporal dentro del worktree, y la lee con `simulator.read_delivery` y una fecha de evaluación **fija**:
  - `test` tiene 18 000 filas y 65 celdas;
  - las celdas con menos de 30 filas disponibles son exactamente 4: (`estrato`, `6`, `lt_20`), (`rango_edad`, `56-65`, `lt_20`), (`rango_edad`, `66+`, `20_30`) y (`rango_edad`, `66+`, `gt_30`);
  - con `Simulator.select("stratified", 1500, semilla)`, la regla **corre** e informa esas 4; las otras 61 tienen `taken ≥ 30`;
  - con 3 semillas distintas, lo mismo.

  Medido al redactar: 12 s de generación, 17 s en total, 4 de 65 (con fecha 2026-11-13: 12, 25, 4 y 10 filas). **El conteo de `56-65/lt_20` depende de la fecha de evaluación** (la candidata de la línea 333 dice 21): fija la fecha y no escribas los conteos a mano; compara el **conjunto** de celdas. Si con tu fecha el conjunto cambia, anótalo y avisa: es un dato para el usuario.

- [ ] **CA-10** — `rt2-setup` (Paso 8, «`rt2-setup`»; BR-U12-07).
  ```bash
  uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py -v -k rt2_setup
  ```
  Esperado: pasan, con el BFF real en proceso (P-6):
  - 1 versión: `ingeniero-1` registra y lanza la validación, `cro-1` aprueba → termina con la versión `aprobado`; cada escritura salió con un token de step-up y con el `sub` correcto;
  - 3 versiones → las 3 `aprobado` (el código admite de 1 a 5);
  - una queda en `validacion_fallida` → la sección **se niega a seguir**: 0 aprobaciones posteriores;
  - dos versiones con el mismo `model_version_id` en la entrada → error y **0** solicitudes;
  - `approved_by` igual a `registered_by` (el doble responde 409 a la aprobación) → `falla`;
  - el cuerpo del registro valida como `ModelRegistration` y sus URIs y SHA-256 son los de `governance/docs/kind/registro-cuerpo.sh` para el mismo paquete (la prueba ejecuta el guion y compara);
  - retoma: una versión ya `lista_para_aprobacion` no se vuelve a registrar ni a validar;
  - validar sin política activa (409 `conflict_state`) → `no ejecutado` con su motivo; validación que no termina en el plazo (reloj falso) → `no ejecutado`;
  - `auth_time` de hace 801 s antes de aprobar → un step-up nuevo; la segunda escritura de `ingeniero-1` dentro de los 800 s → ninguno;
  - `initial_disparity.attributes` vacía en el informe → el aviso queda en el resultado.

  **Rojo primero:** aprobar con la sesión de `ingeniero-1` hace fallar el primer caso (403 del BFF real); regístralo.

- [ ] **CA-11** — Oráculo de RT-2 (Paso 8, «Aceptación» y «Paquete completo»; BR-U12-04, 07).
  ```bash
  uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py -v -k "rt2 and not rt2_setup"
  ```
  Esperado: pasan, cada uno con su nombre:
  - corrida completa correcta (lote, `freeze` a los 1 500 s, paquete completo, `congelado`, casos nuevos `modelo_congelado`, 3 corridas de bias, reactivación, sin recongelar, barrido, cierre) → RT-2 `pasa` y `RT2-LATENCY` `pasa` con `latency_seconds = 1500`;
  - **una versión reactivada que se recongela el mismo día → `falla`**;
  - **dos corridas con el mismo `model_version_id` → `falla`**, antes de enviar nada;
  - **una corrida de RT-2 de 31 min → `falla` con la medición registrada**: `RT2-LATENCY` `falla` y `latency_seconds = 1860` en el resultado; a 1 800 s exactos → `pasa`;
  - **un `freeze` sin el campo `data_sources`, o con `initial_disparity` vacía, o con un `FreezeContext` incompleto → `falla`**: tres pruebas, más una por cada campo de la lista del plan (`before`, `after`, `last_7_days`, `trigger_attribute`, `implicated`, `affected_volume`, `threshold_pp`, `n_min`) quitado del paquete. El código nombra **el campo que falta**; `data_sources: []` → `pasa`;
  - sin `freeze` al tope → `falla`, y el mensaje trae el estado de la última corrida de bias;
  - un `freeze` de **otra** versión no cuenta; uno anterior al inicio del lote, tampoco;
  - la versión no pasa a `congelado` → `falla`; un caso nuevo en `listo` → `falla`;
  - una `frozen_resolution` antes de las 3 corridas, o la versión deja de estar `congelado` → `falla`; solo 2 corridas completas en el plazo → `no ejecutado`; una corrida con `vectra_bias_last_run_ok = 0` no cuenta;
  - la reactivación responde 403 → `falla` con el `code`; sale con un token **sin** step-up → error antes de enviar;
  - los casos no salen de `modelo_congelado` tras el barrido → `falla`;
  - una `recommendation` del lote con el `model_version_id` de la versión de referencia → `falla` (faltó `mark_active`);
  - el operador no activa la versión en el plazo → `no ejecutado` con la fase pendiente; el rollback pendiente → el campo de cierre lo dice;
  - con 1 versión, la evidencia de `RT2-LATENCY` dice «1 medición» y cita DD-1.

  **Rojo primero** (regístralos): (1) medir desde el **mayor** `recorded_at` del lote deja pasar la corrida de 31 min; (2) aceptar cualquier `freeze` posterior, sin mirar la versión; (3) dejar que `invalid_response` de `RegistryClient` suba como excepción: las pruebas del paquete deben fallar por falta de código.

- [ ] **CA-12** — Oráculo de RT-3 (Paso 8, «Aceptación»; BR-U12-04).
  ```bash
  uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py -v -k rt3
  ```
  Esperado: pasan, cada uno con su nombre:
  - RT3-a, c y d con 422 `validation_error`, la lista de modelos igual antes y después, y F22 con casos `en_sincronizacion`, `last_cause = timeout` y cero `recommendation` → RT-3 `pasa` (con P-2 (a));
  - **`RT3-a` aceptado por U4 → `falla`** (200); lo mismo para c y d;
  - 422 con otro `code`, o 409, o 403 → `falla` con el estado y el código; un `reason_code` distinto del de la tabla → `falla`;
  - una versión nueva en la lista de modelos tras los registros, o la `activo` cambia → `falla`;
  - **una sola `recommendation` en RT-3 → `falla`**, con su `case_id` y su `model_version_id`;
  - **sin `FailClosed` de `timeout` o `explainer_unavailable` con F22 deshabilitado → `falla`**: todos los casos con `last_cause = explainer_error`; y otro con todos en `listo`;
  - casos en `no_disponible` con `last_cause = explainer_unavailable` → cumple; un caso en `en_evaluacion` sin intentos tras el plazo → `falla`;
  - RT3-b: `validacion_fallida` → cumple; promovida, con `last_cause` `explainer_error` o `feature_dictionary_incomplete` y cero `recommendation` de esa versión → cumple; con una `recommendation` suya → `falla`; **409 al registrar → `no ejecutado`** con su código;
  - RT3-a o d desplegado: `Ready = False` sostenido → cumple (con `causa_no_leida`); `Ready = True` → `falla`; `Forbidden` de `kubectl` → `no ejecutado`;
  - `wait_for_escalation`: con el reloj falso espera más de 1 160 s (19,3 min) sin `sleep` real, y las lecturas del gauge y de `FailClosedPersistente` quedan en el resultado sin cambiarlo;
  - el registro o el BFF no responden → `no ejecutado`.

  **Rojo primero** (regístralos): (1) contar solo las `recommendation` de los casos de sonda deja pasar una de otra versión en la ventana; (2) aceptar cualquier 4xx como rechazo deja pasar el 409.

- [ ] **CA-13** — El filtro de evidencias sobre todo lo que los escenarios devuelven (NFR-U12-05, 50).
  ```bash
  uv run pytest system-verification/tests/unit/test_evidence_filter.py && uv run pytest system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py system-verification/tests/unit/test_oracles_measurements.py -v -k "evidence or leak"
  ```
  Esperado: código 0; el filtro de U12-T01 y U12-T02 sigue verde, y pasan:
  - el resultado de cada escenario (RT-5, RT-3, `rt2-setup`, RT-2, `RT2-LATENCY` y `SIM-NORMAL`), serializado, pasa `evidence.prepare` con los secretos de `Credentials.secret_values()` **sin cambios**;
  - los mensajes de todos los errores de `scenarios/` en una corrida con fallos (401, 403, 409, 422, 500, tiempo agotado) no contienen un token, una contraseña ni un TOTP;
  - un resultado al que la prueba le inyecta un JWT → `evidence.prepare` falla: el filtro sí lo ve;
  - el log del Job y el JSON de `kubectl` pasan el filtro (el token de desarrollo `root` de kind no los bloquea: F-09);
  - ningún resultado contiene un campo de `ApplicationIn`.

- [ ] **CA-14** — `SIM-NORMAL` (Paso 10, «Aceptación»; BR-U12-02, 06).
  ```bash
  uv run pytest system-verification/tests/unit/test_oracles_measurements.py -v
  ```
  Esperado: pasan, cada uno con su nombre:
  - `accepted = sent = 20`, 20 `case_id` distintos, todos `listo` → `pasa`;
  - **`accepted < sent` → `falla`**, con `rejected_by_code` en el mensaje;
  - `case_ids` con un repetido, o con menos elementos que `accepted` → `falla`;
  - un caso `decidido` → `pasa` (P-7); uno en `en_sincronizacion` con `last_cause = timeout` → `pasa`; uno `modelo_congelado` → `pasa`; uno `no_disponible` con `last_cause = scoring_unreachable` → `pasa`;
  - un caso `vencido` → `falla`; uno con `last_cause` fuera del catálogo → `falla`; uno en `en_evaluacion` tras el plazo (reloj falso) → `falla` con el conteo;
  - un `case_id` que el BFF no conoce (404) → `falla`;
  - el BFF no responde → `no ejecutado`;
  - el resultado trae el conteo por estado y por causa, y ningún dato del solicitante;
  - con 2 000 casos y el reloj falso, el ritmo por usuario no pasa de 20/s y la prueba termina en segundos reales.

  No hay pruebas de `LOGS-NO-PII` ni de `CASE-SIZE`. **Rojo primero:** comparar `accepted <= sent` en vez de `==` deja pasar el segundo caso; regístralo.

- [ ] **CA-15** — Los dobles se parecen al contrato (lección de la enmienda §8; P-6).
  ```bash
  uv run pytest system-verification/tests/integration/test_scenarios_contract.py -v
  ```
  Esperado: pasan:
  - cada ruta y método que los escenarios llaman del BFF existe en `contracts/openapi/console-bff.yaml` con ese rol y ese MFA en `role-endpoint-matrix.md` (la prueba lee los dos archivos);
  - cada respuesta **correcta** de los dobles (BFF, registro) valida contra el esquema de su ruta en `contracts/openapi/`; cada error es un `Problem` válido;
  - cada respuesta **incorrecta** que usan los oráculos difiere de la correcta **solo** en lo que su nombre dice (un campo quitado, un estado cambiado): la prueba lo comprueba con un diff de claves;
  - los parámetros de consulta al registro existen en `GET /v1/entries` de `decision-registry-service.yaml`, y `entry_type` y `projection` son valores que `decision-registry/src/vectra_registry/projections.py` (`FIELDS`) admite para ese scope;
  - los estados de caso y las causas que los oráculos nombran son miembros de `CaseState`, `FailClosedCause` o `LocalCause`; los estados de modelo, de `ModelState`;
  - el JSON del Job del doble de `kubectl` tiene los campos de `batch/v1` que el oráculo lee (`status.startTime`, `completionTime`, `succeeded`, `failed`, `conditions`);
  - los nombres de las series y de las alertas que los oráculos consultan aparecen, tal cual, en su fuente: `case-management/chart/templates/prometheusrule.yaml`, `case-management/core_banking_mock/src/core_banking_mock/metrics.py`, `case-management/src/vectra_case/metrics.py`, `platform/observability/rules/platform-rules.yaml`, `platform/network/flows.yaml` y `bias-monitoring/src/vectra_bias/publish.py` (la prueba los busca en esos archivos).

  **Rojo primero:** pedir `entry_type=fail_closed` con la proyección `metrics` hace fallar el cuarto caso; un estado `sincronizando` hace fallar el quinto. Regístralos.

- [ ] **CA-16** — RT-3 contra governance real (P-6 (a)).
  ```bash
  uptime; time uv run pytest system-verification/tests/integration/test_rt3_real_chain.py -v; uptime
  ```
  Esperado: pasan, con el BFF real en proceso encadenado a la app real de governance sobre PostgreSQL de Testcontainers, y los paquetes de `vectra_reference.adversarial.rt3_package` sobre un paquete real chico:
  - RT3-a, c y d por `BffClient.register_model` → 422 `validation_error`, con `invalid_params` y los `reason_code` de la tabla; la lista de modelos no cambia; el oráculo da `pasa` en los tres;
  - RT3-b con el modelo base **sin registrar** → 200 y `registrado`;
  - RT3-b con el modelo base **ya registrado** → 409, y el oráculo da `no ejecutado` (`rt3b_version_ya_registrada`). Es «Contradicciones» 3, reproducida;
  - `rt2-setup` con un paquete válido: `ingeniero-1` registra, `cro-1` aprueba y `approved_by ≠ registered_by` en la respuesta real; aprobar con el mismo `sub` que registró → 409 real y `falla`.

  Tiempo esperado: menos de 3 min (estimación). Si la cadena no sale en 1 h, aplica P-6 (b) y anótalo. **Rojo primero:** mandar el cuerpo con las URIs de la convención `<model_version_id>/` para RT3-a (en vez del prefijo por parámetro) hace que governance lea el paquete base: el 422 llega con `manifest_sha256_mismatch` (`registration.py`, línea 115), no con el motivo de la tabla, y el oráculo debe dar `falla`. Regístralo.

- [ ] **CA-17** — Las esperas largas usan el reloj inyectado (NFR-U12-42; «Restricciones del entorno»).
  ```bash
  uptime; time uv run pytest system-verification/tests/unit -q -p no:cacheprovider; uptime
  ```
  Esperado: código 0. `test_scenario_waits.py` comprueba el sondeo: condición cierta al primer intento → 0 esperas; cierta al intento n → (n − 1) intervalos en el reloj falso; plazo vencido → el resultado de «vencido» y nunca más del plazo. Las pruebas de `tests/unit` de **esta tarea** suman menos de 60 s reales aunque simulen más de 2 h de reloj (15 min de RT-5, 20 min de D1, 45 min de bias, 30 min de `freeze`): anota la duración (`--durations=10`).

- [ ] **CA-18** — Cobertura al umbral del plan (Pasos 4 y 16; NFR-U12-40).
  ```bash
  uv run pytest system-verification/tests --cov=vectra_verification --cov-branch --cov-fail-under=85 && uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100
  ```
  Esperado: los dos en 0. Además, `scenarios/` por sí solo no baja de 90 % de ramas (míralo en `term-missing` y anótalo). Sin `# pragma: no cover` nuevos. Si `make check` ya corre las dos medidas, vale su salida.

- [ ] **CA-19** — Trazabilidad (`DECISIONES-LOOP.md` §6, regla «sin fallos nuevos», con su enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado:
  - el primero puede salir con código 1, y entonces cada línea es de este conjunto: INF-U12-04, INF-U12-05 y NFR-U12-31 (Pasos 11, 13 y 18);
  - **ninguna** línea nombra NFR-U12-42 (hoy sin trazar; lo cubre esta tarea), NFR-U12-11, NFR-U12-50 ni INF-U12-02, ni ninguno de los que U12-T01 y U12-T02 dejaron trazados;
  - el segundo da, para las demás unidades, el mismo conjunto de fallos que en la base de la rama.

  Las BR-U12-04, 06, 07 y 10 se trazan a mano: tabla en `scenarios.md` y citas en las pruebas.

- [ ] **CA-20** — La precisión de NFR-U12-11 y BR-U12-06, en el diseño y en el código.
  ```bash
  grep -n "alcanzable" aidlc-docs/construction/system-verification/nfr-requirements/nfr-requirements.md aidlc-docs/construction/system-verification/functional-design/business-rules.md aidlc-docs/construction/system-verification/code/scenarios.md system-verification/src/vectra_verification/scenarios/rt2.py && git diff origin/main...HEAD --stat -- aidlc-docs/construction/system-verification/nfr-requirements aidlc-docs/construction/system-verification/functional-design aidlc-docs/construction/system-verification/infrastructure-design
  ```
  Esperado: los cuatro archivos tienen la precisión, con la fecha y la cita de `DECISIONES-LOOP.md` §10. El `--stat` lista solo `nfr-requirements.md` y `business-rules.md`, con 1 línea cambiada cada uno (la fila de NFR-U12-11 y la fila RT-2 de BR-U12-06). El texto original no se borra.

- [ ] **CA-21** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso (8|10) " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; grep -nE "^- \[ \] .*\*\*Paso (7|8b|9|11) " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: los Pasos 8 y 10 en `[x] (U12-T03)`, el 8 con «RT-2 con 1 versión (DD-1)» y el 10 con «`LOGS-NO-PII` y `CASE-SIZE` diferidos por la demo»; los Pasos 7, 8b, 9 y 11 en `[ ]`, cada uno con su nota de diferido. El diff muestra solo esas seis casillas. La sección de reglas de admisión sigue en el plan (`platform/tests/test_unit_plans.py`).

- [ ] **CA-22** — `check` de la unidad (RL-4).
  ```bash
  uptime; time make -C system-verification check; uptime
  ```
  Esperado: código 0, con lint, mypy estricto, import-linter y **todas** las pruebas (`unit`, `property` e `integration`, con el perfil `ci` y la semilla impresa) y las dos coberturas. Tiempo esperado: **menos de 15 min** con la máquina cargada. Referencia medida: ≈ 10 a 11 min en U12-T02 con carga 2 a 3; lo demás es una estimación (Prometheus, la cadena con governance y los datos reales de U5). Anota el tiempo que imprime pytest y los dos `uptime`. Si pasa de 20 min, revisa antes de seguir.

- [ ] **CA-23** — Sin contenedores huérfanos (`CANDIDATAS.md`, línea 532).
  ```bash
  docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -iE "prometheus|keycloak|config-cli|postgres" ; echo "restantes=$?"
  ```
  Esperado: después de CA-22, `restantes=1` (ninguno), o solo contenedores que ya estaban antes de empezar: lista los de antes en la bitácora. Los nodos de kind y `kind-registry` no se tocan.

- [ ] **CA-24** — Lock y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/|pyproject\.toml$|uv\.lock$|CANDIDATAS\.md$|bitacoras/U12-T03\.md$|aidlc-docs/construction/system-verification/code/|aidlc-docs/construction/system-verification/nfr-requirements/nfr-requirements\.md$|aidlc-docs/construction/system-verification/functional-design/business-rules\.md$|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$)"; echo "fuera=$?"; git diff origin/main...HEAD --stat -- vectra-risk/uv.lock vectra-risk/pyproject.toml
  ```
  Esperado: `uv lock --check` en 0, `fuera=1`, y el último `--stat` vacío (ni `uv.lock` ni el `pyproject.toml` raíz cambian). Si cambian, la bitácora dice por qué.

- [ ] **CA-25** — Enlaces.
  ```bash
  uv run python platform/tests/test_links.py
  ```
  Esperado: `N archivos Markdown sin enlaces rotos`, código 0.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_scenario_outcome.py` (CA-3) y `test_scenario_waits.py` (CA-17).
- `tests/unit/test_oracles_rt2_rt3_rt5.py`: CA-2 (`-k guard`), CA-4 y CA-5 (`-k rt5`), CA-10 (`-k rt2_setup`), CA-11 (`-k rt2`), CA-12 (`-k rt3`) y CA-13.
- `tests/unit/test_rt5_job_script.py` (CA-6) y `tests/integration/test_rt5_promql.py` (CA-7), con `tests/doubles/prometheus_tc.py`.
- `tests/unit/test_rt2_cells.py` (CA-8) y `tests/integration/test_rt2_cells_real_u5.py` (CA-9).
- `tests/unit/test_oracles_measurements.py` (CA-14).
- `tests/integration/test_scenarios_contract.py` (CA-15) y `test_rt3_real_chain.py` (CA-16).
- La prueba de U12-T02 que recorre los métodos públicos de `BffClient` se amplía a las rutas de modelos.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U12-T03.md`, como mínimo los de CA-1 a CA-8, CA-10 a CA-12 y CA-14 a CA-16. El par falla-pasa es la prueba. Las mutaciones nombradas en cada criterio son un mínimo: el revisor traerá otras.
- **Lo que el revisor de U12 suele encontrar** (`revisiones/U12-T01/`): una barrera que mira solo la primera forma de un caso; una prueba que pasa con el oráculo vacío; un filtro que marca como secreto algo legítimo. Para cada oráculo, pregúntate qué respuesta **casi** correcta lo engañaría, y pruébala.
- **Orden de las pruebas con Docker:** Prometheus, PostgreSQL y Keycloak (de U12-T02) no se levantan a la vez si la memoria disponible es menor de 2 GiB: fixtures en serie.

---

## Restricciones del entorno

- **No copies el repositorio a `/tmp`.** Es un tmpfs con cuota. Los temporales van dentro del worktree, en una carpeta sin versionar (por ejemplo, `platform/.tools/tmp/u12t03/`): `TMPDIR`, los bloques TSDB de la prueba, los datos generados de U5 y los logs. Docker monta desde el worktree, no desde `/tmp`.
- **Máquina compartida y cargada.** Al redactar: `load average: 5.14, 2.84, 2.55` y ≈ 5 GiB de memoria disponible de 14. Anota `uptime` junto a cada medida de tiempo. **Las pruebas de tiempo usan el reloj inyectado, nunca `sleep` real.** Una prueba que falla por tiempo con carga alta se repite en frío antes de darla por rota, y se anotan las dos corridas. No corras `make -C platform check` ni las suites de otras unidades (`make -C governance check`, `make -C case-management check`): de ellas solo se importan apps y dobles.
- **Docker es compartido** con kind (`vectra-control-plane`, `vectra-worker`, `vectra-worker2`, `kind-registry` en `127.0.0.1:5001`) y con otros codificadores. Nombres y puertos de Testcontainers **al azar**. Límite de memoria en Prometheus (≈ 512 MiB). **Borra tus contenedores al terminar**, también tras una corrida interrumpida (CA-23). Nada de `docker system prune`.
- **Puertos ocupados.** 443 es del kind. 8080 y 8081 son fijos en las suites de otras unidades. No uses ninguno, ni 8443, 8200 ni 9090. Pide puertos libres al sistema (puerto 0).
- **Sin clúster.** El kind puede estar corriendo y hay un kubeconfig que funciona: **no lo uses**. Ninguna prueba ejecuta el `kubectl` real ni llama a `vectra.localtest.me`.
- **Imágenes.** Bajar Prometheus necesita red y la decisión de P-1. Siempre por digest. Las de Keycloak, keycloak-config-cli y PostgreSQL ya las usa U12-T02.
- **El bloque TSDB.** La imagen de Prometheus corre sin privilegios (usuario `nobody`): la carpeta montada debe poder leerla y escribirla ese usuario. Los datos de más de 15 días se borran con la retención por omisión: los fixtures llevan tiempos relativos a «ahora». La serie `prometheus_tsdb_lowest_timestamp_seconds` solo existe si Prometheus se raspa a sí mismo: déjalo en su configuración.
- **Navegadores.** `make check` corre también el login de U12-T02: reusa los de `~/.cache/ms-playwright`. No los borres ni los reinstales; nada de `sudo` ni `--with-deps`.
- **No toques el árbol principal ni otros worktrees.** Escribe solo en el tuyo. No uses `git stash` sin etiqueta (`git stash push -m "U12-T03 …"`).
- **Otros codificadores en paralelo.** U01-T09 toca `platform/`; esta tarea no. Si otra tarea toca `uv.lock`, el orquestador fusiona `origin/main`.

---

## Notas

- **Orden sugerido:** (1) leer `clients.md` y verificar la tabla «Lo que cada oráculo lee de verdad»; (2) prueba de concepto de P-1: Prometheus arriba con un bloque de `promtool` y una `query_range`, antes de escribir nada más; (3) `outcome` y `waits` con CA-3 y CA-17; (4) RT-5 con CA-4 a CA-7; (5) la regla de las celdas con CA-8 y CA-9, y la precisión del diseño; (6) las rutas de modelos del BFF, `rt2-setup` y RT-2; (7) RT-3 y la cadena con governance; (8) `SIM-NORMAL`; (9) contrato de los dobles, cobertura, `scenarios.md`, plan y bitácora. Lo que más riesgo tiene va primero.
- Archivos que se **modifican en su sitio**: `system-verification/.importlinter`, `clients/bff.py`, `clients/_api.py`, `clients/registry.py` (si hace falta), `scenarios/__init__.py`, las pruebas y los dobles de U12-T02 que amplíes, el plan (seis casillas), las dos filas del diseño y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- **`Makefile`.** `check` sigue siendo `lint types imports test`. No se agregan `links` ni `traceability`: son de U12-T04.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`: `test_traceability.py` los salta.
- **Enlaces:** `test_links.py` lee como enlace cualquier corchete cerrado seguido de un paréntesis fuera de un bloque de código sin sangría. Cuidado con los patrones de `grep` en `scenarios.md` y en la bitácora.
- **Candidatas nuevas** que esta tarea deja en `CANDIDATAS.md`, si no están ya: «Contradicciones» 2, 3, 4, 5, 7, 9, 16 y 17; la ampliación de K16 a `vectra-staging` (U1); generar RT3-b desde un paquete no registrado (guion de U12-T04); y lo que encuentres al verificar la tabla.
- **Bitácora** `bitacoras/U12-T03.md`: la salida real de cada comando, pegada, con rutas absolutas a los logs largos. Incluye la tabla de verificación de «Lo que cada oráculo lee de verdad» («igual» o corregida), los pares falla-pasa, la decisión tomada en P-1 a P-12, el digest de la imagen de Prometheus, el tiempo de cada `make check` con sus `uptime`, la lista de contenedores antes y después, y la tabla de celdas reales de CA-9. **Ningún secreto.**
- PBT-U12-01..04 nunca se recortan. Esta tarea no agrega ninguna.
- U12 no tiene datos propios ni recursos en el clúster: no hay migraciones, chart ni nada que limpiar en kind.

### Lo que T04 y T05 necesitan de esta tarea

- **U12-T04 (E+F, Pasos 12, 13, 15 y 17):**
  - una función por sección (`rt5`, `rt3`, `rt2-setup`, `rt2`) y la de `SIM-NORMAL`, con sus parámetros (`runId`, `started_at`, versiones del proxy, prefijos del model-store, semillas, plazos) y su resultado. La CLI solo las ordena;
  - la conversión a `report.Evidence` y el motivo de cada `no ejecutado`, para el manifiesto;
  - las fases de `rt2` y de `rt3` como puntos de retoma, y los textos al operador (sin órdenes prohibidas);
  - las consultas guardadas de cada oráculo (NFR-U12-50);
  - para `demos/prs/` y los guiones: F22 con `env_disabled.kind` (P-19); RT3-a y d como `InferenceService` de perfil `staging`; el prefijo de los paquetes RT-3 en el model-store; RT3-b según P-2; el `InferenceService` de staging del proxy antes de `rt2-setup`; y los tiempos reales de D1 (≥ 19,3 min si se enseña `FailClosedPersistente`) y de D2 (> 75 min con 1 versión);
  - para `verify/journey-7-3.sh`: las lecturas informativas del gauge y de `FailClosedPersistente`;
  - para el informe y el README: `RT2-LATENCY` con 1 medición, las celdas inalcanzables, y las historias que salen `no ejecutado` por lo diferido;
  - para `SIM-NORMAL`: llamarla al final de `decisions`, con el `RunReport` de la corrida.
- **U12-T05 (G+H, Pasos 18 y 19):** `make -C system-verification check` con estas pruebas; y lo que solo se ve en kind:
  - que la serie `inbound_http_authz_deny_total` exista tras U01-T09, con las etiquetas `namespace` y `route_name` que el oráculo pide;
  - el valor real de `l5d-proxy-error` y que el log del pod del Job se lea sin nombrar el contenedor;
  - que `CoreWriteAttempt` llegue a `firing` con el intervalo de raspado y de evaluación reales;
  - que la sección `rt5` corra dentro de los 3 días de retención de kind;
  - qué `last_cause` da de verdad F22 apagado (`timeout` o `explainer_unavailable`, según el breaker de U7);
  - las métricas de bias por el Pushgateway (P-5) y que U3 no responda 504 al cron (U03-T07);
  - K16 en `vectra-staging` (P-2), el login real de `ingeniero-1`, `cro-1` y `cumplimiento-1` (defectos del realm) y la `aud` de los tokens de servicio;
  - los paquetes RT-3 y proxy subidos al model-store, la política activa antes de `rt2-setup`, y el modelo de referencia `activo` al terminar RT-2 y RT-3.
