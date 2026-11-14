# Resumen del código: U12 `system-verification`, Pasos 8 y 10 (U12-T03)

Código en `vectra-risk/system-verification/src/vectra_verification/scenarios/`: `outcome`, `waits`, `common`, `rt5`, `rt3`, `rt2` (con `rt2-setup`) y `sim_normal`. Los clientes ganan las rutas de modelos del BFF (`list_models`, `get_model`,
`register_model`, `start_validation`, `approve_model`; las tres de escritura exigen step-up), `ApiError.invalid_params` y `RegistryClient.freezes_raw`. Un contrato nuevo de import-linter: `scenarios` no importa `httpx`, `requests`,
`socket`, `subprocess`, `playwright` ni `pyarrow` (7 contratos). Diferido por la demo (enmienda §3 U12): ejecutar las otras 4 versiones del proxy, `LOGS-NO-PII` y `CASE-SIZE`; no hay `rt1.py`, `rt4.py`, `x_*.py`, `logs_pii.py` ni `case_size.py`.

## Firmas

```python
# scenarios.outcome: el resultado de tres valores
Outcome(id, result, expected, obtained, missing=(), subresults=(), queries=(), readings={})   # result: pasa | falla | no ejecutado
SubOutcome(name, result, missing=(), detail="", mandatory=True, readings={})
combine(subresults) -> (result, missing);  from_subresults(id, expected, subresults, readings=, queries=) -> Outcome
to_evidence(outcome, command=, output=, commit=, images=, executed_at=, operator=) -> Evidence | None   # no ejecutado: None
to_text(outcome) -> str                                                                                  # JSON; pasa por evidence.prepare sin cambios

# scenarios.waits
poll(clock, condition, interval=, timeout=) -> Waited(met, value, elapsed, attempts)      # reloj inyectado: ni un sleep real; un plazo que la coma flotante deja `1e-12` corto termina (`EPSILON`)

# scenarios.common
Sessions(environment, oidc, clock, tag, transport=, verify=).reader(user) / .writer(user) / .write(user, call)   # step-up renovado si auth_time > 800 s
registration_body(package_dir, prefix=None) -> ModelRegistration;  package_version(dir);  list_all_models(bff);  snapshot(models);  ScenarioError(code)

# scenarios.rt5
run(k8s, prom, clock, run_id, started_at, environment=, after_job=15 min) -> Outcome        # read(...) -> Readings;  judge(run_id, started_at, readings) -> Outcome  (pura)
# scenarios.rt3
rt3(Rt3Deps(environment, clock, sessions, simulator, registry, k8s, prom), Rt3Params(packages, seed, deployed, probes=5, wait_for_escalation, ...)) -> Outcome
rt3_closing(deps, params, timeout=) -> SubOutcome                                            # el cierre de D1 (P-9 (a)), tras revertir el PR de F22
# scenarios.rt2
rt2_setup(environment, sessions, clock, versions, validation_timeout=) -> Outcome            # de 1 a 5 ProxyVersion(run, model_version_id, package_dir, prefix)
run_rt2(Rt2Deps(environment, clock, sessions, simulator, registry, prom, reactivator), Rt2Params(reference_version_id, versions, seed, ...), state=None) -> Rt2Result(rt2, latency, closing, state, pending, unreachable_cells)
check_cells(short) / classify_cells(short);  judge_package(freeze);  count_bias_runs(ts, ok, after);  latency_outcome(measurements);  verify_reactivation(run, version, vs)
Reactivator.reactivate(model_version_id) -> SubOutcome | None;  ToolReactivation(sessions)
# scenarios.sim_normal
sim_normal(environment, bff, clock, report, timeout=) -> Outcome;  judge(sent, accepted, rejected_by_code, case_ids, reads) -> Outcome (pura)
```

Cada escenario separa lo que **lee** (clientes de U12-T02) de lo que **juzga** (funciones puras que reciben lecturas). `guard.check_section` se llama al entrar, antes de la primera solicitud; `resolve_frozen` solo sale de `rt2`.

## Lo que cada oráculo lee de verdad (verificado en esta rama, sobre `origin/main` cc1fdd6: igual a la tarea)

| Oráculo | Ruta | Campo | Valor |
|---|---|---|---|
| RT-5, el Job | `case-management/chart/templates/rt5-demo-job.yaml` (líneas 18, 26 y 27, 59 y 60) | nombre, `backoffLimit`, `activeDeadlineSeconds`, línea del log, salida | `rt5-demo-<runId>` en `vectra-app`; `backoffLimit: 0`; 300 s; `rt5-demo: POST <url> -> <código> l5d-proxy-error: <valor>`; `sys.exit(0 if code == 403 else 1)` |
| RT-5, Prometheus | `case-management/chart/templates/prometheusrule.yaml`; `platform/network/flows.yaml`; `core_banking_mock/metrics.py` | alerta, ruta, contador | `CoreWriteAttempt`; `core-mock-catch-all`; `vectra_core_write_attempts_total` |
| RT-5, retención | `platform/observability/values/kube-prometheus-stack-kind.yaml` | `retention` | `3d` |
| RT-3, registro | `contracts/openapi/role-endpoint-matrix.md`; `governance/src/vectra_governance/api.py` | ruta, rol, MFA; rechazo | `POST /api/console/models`, `ingeniero_riesgo`, MFA; 422 `validation_error` con `invalid_params = [{name: package, reason_code}]` |
| RT-3, motivos | `reference-model/src/vectra_reference/adversarial.py` | `REJECTED_BY_U4`, `ACCEPTED_BY_U4` | `RT3-a`, `RT3-c`, `RT3-d` y `RT3-b`; motivos de `rt3.EXPECTED_REASON` (confirmados contra governance real) |
| RT-3, estado | `contracts/.../models/api.py` | `CaseDetail.state`, `attempts`, `last_cause` | `last_cause` solo en `en_sincronizacion` y `no_disponible` |
| RT-3, F22 | `platform/network/flows.yaml` | `env_disabled` | `kind: [F22]` (P-19), no `enabled: false` |
| RT-2 | `contracts/.../routes/__init__.py`; `bias-monitoring/chart/values-monitoring-policy.yaml`; `bias-monitoring/src/vectra_bias/publish.py` | `MFA_MAX_AGE`; cron; series | 900 s; `2,17,32,47 * * * *`; `vectra_bias_last_run_timestamp`, `_ok` y `_failure{reason}` |
| RT-2, registro | `contracts/.../models/registry.py`; `decision-registry/src/vectra_registry/projections.py` | `FreezeProjection`, `FIELDS` | `metrics` solo trae `recommendation`, `human_decision` y `explanation_view`; `monitoring_freezes`: `freeze` y `frozen_resolution` |
| K16 | `platform/rbac/verification-operator/k16.yaml` | `Role` | `vectra-app`: `jobs`, `pods`, `pods/log`; sin `Role` en `vectra-staging` |

Todo esto lo ata `tests/integration/test_scenarios_contract.py` a su fuente y valida las respuestas de los dobles contra `contracts/openapi/`.

## Códigos de «qué faltó» (estables; cada forma incorrecta tiene el suyo)

- **RT-5:** `rt5_job_inexistente`, `rt5_job_otro_runid`, `rt5_job_anterior_al_inicio`, `rt5_job_no_termina`, `rt5_job_fallido`, `rt5_k8s_forbidden`, `rt5_k8s_no_responde`, `rt5_log_no_leido`, `rt5_pod_inexistente`, `rt5_prometheus_no_responde`,
  `rt5_retencion_no_cubre_t0`, `rt5_retencion_sin_dato`, `rt5_403_de_la_aplicacion`, `rt5_log_codigo_distinto_de_403`, `rt5_log_sin_linea`, `rt5_log_sin_respuesta`, `rt5_serie_denegaciones_ausente`, `rt5_serie_denegaciones_menor_que_1`,
  `rt5_alerta_core_write_attempt_ausente`, `rt5_serie_contador_del_mock_ausente`, `rt5_contador_del_mock_mayor_que_0`. Si falta la serie de denegaciones el mensaje la nombra completa y distingue «nadie raspa el proxy de Linkerd de `vectra-mock`» (U01-T09) de «hay series con otras etiquetas».
- **RT-3:** `rt3_<caso>_aceptado_por_u4`, `rt3_<caso>_estado_<estado>_<code>`, `rt3_<caso>_sin_invalid_params_package`, `rt3_<caso>_reason_code_distinto`, `rt3_lista_de_modelos_cambio`, `rt3_f22_caso_en_listo`, `rt3_f22_caso_sin_intentos`, `rt3_f22_estado_inesperado`,
  `rt3_f22_sin_causa_timeout_o_explainer_unavailable`, `rt3_recommendation_con_f22_apagado`, `rt3_f22_sonda_rechazada`, `rt3_RT3-a-desplegado_listo`, `rt3_k8s_forbidden`, `rt3_inferenceservice_inexistente`, `rt3b_version_ya_registrada`,
  `rt3b_validacion_no_termina`, `rt3b_promocion_pendiente`, `rt3b_recommendation_de_la_version_alterada`, `rt3b_sin_fail_closed_esperado`, `rt3_cierre_f22_sigue_apagado`, `rt3_dependencia_no_responde`.
- **`rt2-setup`:** `rt2_setup_registro_http_*`, `rt2_setup_sin_politica_activa`, `rt2_setup_validacion_no_termina`, `rt2_setup_validacion_fallida`, `rt2_setup_aprobacion_http_<estado>_<code>`, `rt2_setup_aprobador_igual_al_registrante`, `rt2_setup_no_quedo_aprobado`; antes de enviar nada: `rt2_version_repetida`, `rt2_versiones_fuera_de_rango`.
- **RT-2:** `rt2_celda_alcanzable_corta` (error, 0 solicitudes), `rt2_operador_promocion_pendiente`, `rt2_referencia_no_inactiva`, `rt2_lote_sin_solicitudes_aceptadas`, `rt2_freeze_ausente`, `rt2_paquete_<campo>_ausente`, `rt2_paquete_initial_disparity_vacia`, `rt2_paquete_invalido:<campo>:<tipo>`,
  `rt2_version_no_congelada`, `rt2_caso_nuevo_en_listo`, `rt2_resolucion_antes_de_las_corridas`, `rt2_version_dejo_de_estar_congelada`, `rt2_corridas_de_bias_pendientes`, `rt2_reactivacion_http_<estado>_<code>`, `rt2_version_no_quedo_activa`,
  `rt2_sin_frozen_resolution_reactivar`, `rt2_recongelada`, `rt2_corrida_de_bias_pendiente`, `rt2_barrido_no_libero_casos`, `rt2_lote_puntuado_por_otra_version`, `rt2_sin_recommendation_del_lote`, `rt2_latencia_mayor_que_1800s`, `rt2_cierre_rollback_pendiente`,
  `rt2_prometheus_requerido`, `rt2_prometheus_no_responde`, `rt2_dependencia_no_responde`.
- **`SIM-NORMAL`:** `sim_normal_aceptadas_menor_que_enviadas`, `sim_normal_case_id_repetido`, `sim_normal_casos_distintos_de_aceptadas`, `sim_normal_caso_desconocido`, `sim_normal_estado_vencido`, `sim_normal_causa_fuera_del_catalogo`,
  `sim_normal_fail_closed_sin_causa`, `sim_normal_casos_en_evaluacion_tras_el_plazo`, `sim_normal_bff_no_responde`.

## Decisiones de las preguntas abiertas

Del usuario (2026-11-13): P-1 (a) autorizada, con el digest de la plataforma; P-2 (a); celdas alcanzables. Las demás: nadie respondió y rige la recomendación de la tarea.

| Pregunta | Decisión | Dónde |
|---|---|---|
| P-1 Prometheus real | (a) `quay.io/prometheus/prometheus` por el digest de `kube-prometheus-stack.yaml` (v3.15.1, 266 MB); `promtool` de la misma imagen; bloque TSDB desde OpenMetrics; Prometheus se raspa a sí mismo | `tests/doubles/prometheus_tc.py`, `test_rt5_promql.py` |
| P-2 RT-3 en la demo | (a) obligatorios: RT3-a, c, d, «sin cambio» y F22 (`rt3.MANDATORY`); RT3-b y los dos «desplegado» se calculan y salen en la evidencia; un `no ejecutado` suyo no baja RT-3, un `falla` sí. Pasar a (b) o (c) es cambiar esa constante | `rt3.py`, `outcome.combine` |
| P-3 sustitutos | (a) «sin cambio en `serving-config`» = lista de modelos del BFF antes y después; causa del fail-closed = `CaseDetail.last_cause`. Son sustitutos: U12 no alcanza `serving-config` ni la entrada `fail_closed` | `rt3.py` |
| P-4 módulos | (a) `outcome`, `waits`, `sim_normal` y `common` (este último, nuevo: sesiones, cuerpo del registro) | `scenarios/` |
| P-5 corridas de bias | (a) por Prometheus: valores distintos de `max(vectra_bias_last_run_timestamp)` posteriores al instante, con `min(vectra_bias_last_run_ok) == 1`; una corrida fallida no cuenta; las consultas van a la evidencia | `rt2.count_bias_runs` |
| P-6 dobles o reales | (a) el BFF real en proceso con los dobles de U10, y para el registro de RT-3 la app real de governance sobre PostgreSQL de Testcontainers (`test_rt3_real_chain.py`); el registro (U3) es un doble validado contra su OpenAPI | `tests/doubles/rt2_world.py`, `real_chain.py` |
| P-7 casos decididos | (a) `decidido` cuenta como llegado a `listo` | `sim_normal.OK_STATES` |
| P-8 operador | (a) sondeo con el reloj inyectado hasta un plazo (3 600 s); al vencer `no ejecutado` con el código de la fase pendiente; `run_rt2` devuelve el `Rt2State` para retomar | `rt2.py` |
| P-9 cierre | (a) campo propio (`Rt2Result.closing`, `rt3_closing`); no cambia el resultado | `rt2.py`, `rt3.py` |
| P-10 datos reales de U5 | (a) dentro de `make check` (≈ 35 s con carga alta) | `test_rt2_cells_real_u5.py` |
| P-11 casos de sonda | (a) 5 `normal`, por parámetro | `Rt2Params.probes`, `Rt3Params.probes` |
| P-12 `RT2-LATENCY` | (a) `pasa` si el máximo de las corridas hechas es ≤ 1 800 s; con 1 dice «1 medición» y cita DD-1 | `rt2.latency_outcome` |

## Regla de las celdas (NFR-U12-11 y BR-U12-06, precisadas en U12-T03, 2026-11-13; decisión del usuario, `DECISIONES-LOOP.md` §10)

«Alguna celda» es una celda **alcanzable**: una con 30 o más filas disponibles en `test`. `rt2` se niega solo si queda corta una celda alcanzable (error con las celdas, 0 solicitudes); las inalcanzables no hacen que se niegue: se informan en la
evidencia con `attribute`, `group`, `band`, `available` y `taken`. Con los datos reales de U5 y la fecha 2026-11-13 son 4 de 65 (`estrato/6/lt_20` 12, `rango_edad/56-65/lt_20` 25, `66+/20_30` 4, `66+/gt_30` 10); el conteo de `56-65/lt_20` depende de la
fecha de evaluación (la candidata decía 21). El volumen es un piso: el resultado registra el pedido y el enviado, sin tope.

## BR → prueba

| Regla | Prueba |
|---|---|
| BR-U12-04 (oráculos de RT-2, RT-3 y RT-5) | `tests/unit/test_oracles_rt2_rt3_rt5.py` (`-k rt5`, `-k rt3`, `-k rt2`); `test_rt5_job_script.py`; `tests/integration/test_rt5_promql.py`, `test_rt3_real_chain.py` |
| BR-U12-06 (volúmenes y celdas de RT-2; `SIM-NORMAL` sobre los 2 000) | `test_rt2_cells.py`; `test_rt2_cells_real_u5.py`; `test_oracles_measurements.py` |
| BR-U12-07 (`rt2-setup`, latencia) | `test_oracles_rt2_rt3_rt5.py` (`-k rt2_setup`, `-k "rt2 and not rt2_setup"`); `test_rt3_real_chain.py` |
| BR-U12-10 (barreras de entorno, cierre) | `test_oracles_rt2_rt3_rt5.py` (`-k guard`); `test_kubectl_verbs.py`; los campos de cierre de `rt2` y `rt3` |
| BR-U12-11 (resultado de tres valores) | `test_scenario_outcome.py` |

## Qué evidencias produce esta tarea y cuáles no (con las secciones diferidas)

Produce: `RT-2`, `RT2-LATENCY`, `RT-3`, `RT-5` y `SIM-NORMAL`. No hay evidencia de `rt2-setup` (no es un elemento del informe). Siguen en `no ejecutado` por lo diferido: `RT-1`, `RT-4`, `X01` a `X10`, `LOGS-NO-PII`, `CASE-SIZE`, `LOAD`, `RESILIENCE` y las historias
que dependen de ellos. `RT-3` tiene sub-resultados opcionales (`RT3-b` y los dos «desplegado») que, si salen `no ejecutado`, no bajan el resultado (P-2 (a)); el informe los muestra. `RT-5` no tiene sub-resultados.

## Lo que U12-T04 y U12-T05 pueden llamar

- **U12-T04:** una función por sección (`rt5.run`, `rt3.rt3`, `rt2.rt2_setup`, `rt2.run_rt2`, `sim_normal.sim_normal`) con sus parámetros (`runId`, `started_at`, versiones del proxy y sus prefijos, paquetes RT-3, semillas, plazos); `outcome.to_evidence` y el motivo de cada
  `no ejecutado` (`Outcome.missing`); las fases de `rt2` y los sub-resultados de `rt3` como puntos de retoma (`Rt2State`, `Rt2Result.pending`); las consultas guardadas (`Outcome.queries`). La reactivación es un paso separable: el modo de la herramienta es
  `ToolReactivation`; para esperar al presentador, un `Reactivator` que no haga nada y la verificación posterior de `verify_reactivation` (la misma). Los textos al operador describen el paso sin la orden. Para `SIM-NORMAL`: llamarla al final de `decisions`.
- **U12-T05 (Paso 18):** la serie `inbound_http_authz_deny_total` con `namespace` y `route_name` tras U01-T09; el valor real de `l5d-proxy-error`; `CoreWriteAttempt` en `firing` con los intervalos reales; que `rt5` corra dentro de los 3 días de retención; qué `last_cause` da F22 apagado;
  las métricas de bias por el Pushgateway; K16 en `vectra-staging`; el login real de `ingeniero-1`, `cro-1` y `cumplimiento-1`; la audiencia que acepta governance de un token reenviado por el BFF; los paquetes RT-3 y proxy en el model-store.

## Enmienda de la ronda 2 (arbitraje de U12-T03, 2026-11-13; rige sobre la tarea)

- **Espera de F22.** El oráculo no deja de esperar por `attempts ≥ 1`: U8 escribe `attempts` al tomar el trabajo (`case-management/src/vectra_case/job_queue.py`) y el caso sigue en `en_evaluacion` mientras la llamada a scoring está en vuelo (hasta `SCORING_TIMEOUT`). `Rt3Run.cases` espera a que **cada caso de la sonda salga de `en_evaluacion`**; al vencer el plazo, un caso que sigue en `en_evaluacion` da `rt3_f22_caso_sin_intentos` (sin intentos) o `rt3_f22_caso_sin_estado_final` (con ellos). `_rt3b` usa el mismo `cases`.
- **«3 corridas más de bias» (corregida en la ronda 3, F-11).** U9 publica `vectra_bias_last_run_timestamp` como un **entero truncado al segundo** (`bias-monitoring/src/vectra_bias/publish.py`: `int(report.finished_at.timestamp())`), y escribe el `freeze` **dentro** de la corrida, antes de fijar el fin (`run.py`). El `recorded_at` del `freeze` lleva microsegundos y cae casi siempre en el mismo segundo que `finished_at`: la marca de la corrida que congeló **no es posterior** al `recorded_at` (suele quedar por debajo; solo la supera si el fin cruza al segundo siguiente). La referencia es **la primera marca mayor o igual que `floor(recorded_at)`** (el `recorded_at` truncado al segundo) y se cuentan las corridas correctas (`vectra_bias_last_run_ok == 1`) **estrictamente posteriores** a ella (`rt2.count_bias_runs`); la que congeló más 2 no basta y más 3 da `pasa`. Lo mismo en `no_recongela`, con el `recorded_at` de la reactivación (misma función, misma referencia truncada): una corrida en vuelo durante la reactivación no cuenta.
- **Otros cambios de la ronda.** `rt5.ranged` no pide nunca `start > end` en la costura (F-03). Sin `freeze` al tope de 2 700 s (la fase `freeze` quedó en `rt2_freeze_ausente`), `RT2-LATENCY` es `falla` con `rt2_latencia_sin_freeze` (F-04); un 4xx en esa fase no produce ese código ni su texto (F-12, ronda 3). `K8sError` y `OidcError` dentro de `rt2`, `rt3`, `rt5` y `sim_normal` dan `no ejecutado` con `<sección>_port_forward_caido`, `<sección>_kubectl_no_responde` o `<sección>_sesion_oidc_no_disponible`, conservando los sub-resultados y el punto de retoma (`Rt2Result.pending`; en `rt3`, `readings["interrumpida_tras"]` y el sub-resultado `infraestructura`) (F-05).
