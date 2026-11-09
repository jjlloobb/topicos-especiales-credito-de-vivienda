# Resumen del servicio — U4 `governance`

Bloque D del plan (Pasos 10 y 11; tarea U04-T04). El servicio es la app de `create_app` de U0 (`vectra_common`) con las 21 rutas del
`RouteContract` de `governance-service` (`vectra_contracts.routes`, ya versionadas en `contracts/openapi/governance-service.yaml`).
La autenticación, los scopes y roles, el MFA y su `auth_time` (el step-up de 15 min), el límite de cuerpo y los `Problem` los pone la
fábrica; el servicio solo aporta los handlers (`api.py`). Cada handler llama a las operaciones de `evidence.py` (U04-T03) y no
repite su lógica. La capa de servicio es síncrona: cada handler corre en el hilo del *threadpool*. Entran las cinco rutas de
US-306 (Q-6, opción (a)) y `retirement` (P-8); siguen diferidos el modo `source_comparison` del `model-validation-job` (Paso 13) y
la rama `source_comparison` del barrido.

## Qué reglas cubre cada módulo

| Reglas | Archivo | Pruebas |
|---|---|---|
| P-U0-12 (las 21 rutas como `RouteContract`; ni falta ni sobra un handler; 403 por scope y por rol) | `src/vectra_governance/api.py` (`build_handlers`, `create_governance_app`) | `tests/integration/test_api_app.py` |
| BR-U4-03 (`cumplimiento` + MFA + step-up; ningún CRO, job ni webhook reactiva; `SET LOCAL vectra.frozen_resolution` al confirmar) | `api.py` (`frozen_resolution`), `evidence.py` (`_apply`, op `resolution`) | `tests/integration/test_api_models.py` (`test_us_305_*`, `test_br_u4_03_*`) |
| BR-U4-04, 16 (bias solo congela, solo el `bias-monitoring-job`; sin congelamiento manual) | `api.py` (`freeze`, `actor_of`) y el scope `governance:freeze` del contrato | `tests/integration/test_api_freeze.py` (`test_br_u4_04_*`) |
| BR-U4-05 (el Job en `vectra-staging` con TTL, `activeDeadlineSeconds` y `backoffLimit: 0`; `mode` es parámetro y `source_comparison` solo sale de `comparisons`) | `src/vectra_governance/k8s_jobs.py` (`job_manifest`, `KubernetesJobs`), `api.py` (`start_validation`, `start_source_comparison`) | `test_api_models.py` (`test_br_u4_05_*`), `test_api_data_sources.py`, `tests/unit/test_api_clients.py` |
| BR-U4-06 (registrar sin deserializar: los bytes del model-store y los paquetes RT-3 de U5; 422 sin crear la versión) | `api.py` (`register_model`, `read_package`), `registration.py` | `test_api_models.py` (`test_br_u4_06_*`, `test_us_201_*`) |
| BR-U4-07 (solo la sincronía bloquea; el informe F32 y el detalle con `validation_report`) | `api.py` (`receive_report`, `get_model`) | `test_api_models.py` (`test_us_202_*`) |
| BR-U4-08 (`mark_active` en una unidad; `serving-config` recalculado; la evidencia del PR viaja en el evento) | `api.py` (`activate`), `evidence.py` (`mark_active`) | `test_api_models.py` (`test_us_208_*`) |
| BR-U4-10 (cuatro ojos del modelo, la política y la fuente → 409) | `api.py`, `evidence.py` (`decide_source`), `policy.py` | `test_api_policies.py` (`test_br_u4_10_*`), `test_api_models.py`, `test_api_data_sources.py` |
| BR-U4-11, 12 (activación y vigencia, `normative_current` nulo; ningún servicio escribe política) | `api.py` (`propose_policy`, `decide_policy`, `list_policies`) | `test_api_policies.py` |
| BR-U4-12 (los servicios no escriben política) | el rol `cro` de `POST /v1/policies` en el contrato | `test_api_policies.py` (`test_us_205_*`) |
| BR-U4-13 (ciclo de la fuente: alta, candidata, `start_source_comparison` con sus 409, F32 `source-counts`, F25 `compare_source`, decisión con `pre_post_report`) | `api.py`, `evidence.py` (`propose_source`, `decide_source`, `comparison_models`, `open_comparison`, `save_source_counts`, `fit_report`), `clients.py` (`HttpSourceComparer`) | `test_api_data_sources.py` |
| BR-U4-15 (`freeze` agrega `data_sources` e `initial_disparity`; 60 y 64 KiB) | `evidence.py` (`_freeze_package`, `fit_freeze_package`, `wire_size`) | `test_api_freeze.py` (`test_br_u4_15_*`) |
| BR-U4-16 (monitoreo detenido: el modelo sigue sirviendo; bias no tiene otra ruta) | `api.py` (`freeze`) | `test_api_freeze.py` (`test_br_u4_04_bias_can_call_nothing_but_freeze`) |
| BR-U4-17 (sin evidencia, sin efecto: el 503 deja la transición pendiente) | `evidence.py` (U04-T03); la API traduce `RegistryUnavailable` a 503 | `test_api_freeze.py` (`test_freeze_applies_even_when_the_registry_is_down_*`), `test_api_models.py` |
| BR-U4-18, 19 (`feature-dictionary` y `feature-spec`, solo su identidad; el `feature_spec` byte a byte) | `api.py` (`get_dictionary`, `get_feature_spec`) | `test_api_models.py` (`test_br_u4_18_*`, `test_br_u4_19_*`) |
| BR-U4-14 (`serving-config` con `If-None-Match` → 304; 503 sin copia) | `api.py` (`serving_config`) sobre `convergence.py` | `test_api_models.py` (`test_serving_config_*`) |
| NFR-U4-11, 25; P-U4-03, 06 (timeouts de 5 s del cliente de Kubernetes; los chequeos de rol, MFA y step-up antes de la barrera del trigger) | `k8s_jobs.py`, `api.py` | `tests/unit/test_api_clients.py`, `test_api_models.py` |

## Rutas

| Ruta | Quién (contrato de U0) | Qué hace | Estado |
|---|---|---|---|
| `POST /v1/models` | `ingeniero_riesgo` + MFA | Lee del model-store (F47) los bytes del manifiesto y de cada archivo, `validate_registration` (422 sin fila), fuentes declaradas (422 salvo la candidata de una fuente `en_evaluacion`), `register` con evidencia | 200 `ModelVersion` |
| `POST /v1/models/{id}/validations` | `ingeniero_riesgo` + MFA | `start_validation` (o `retry_validation` desde `validacion_fallida`) y después el Job de K01. Si Kubernetes falla: corrida `fallido`, `validacion_fallida` y 503 | 200 `ValidationRun` |
| `PUT /v1/models/{id}/validation-report` | `governance:validation-report` | F32: la corrida `validacion` `lanzado` más reciente; `sync_check.passed` decide | 204 |
| `POST /v1/models/{id}/approval` | `cro` + MFA | `aprobado` o `rechazado` (con justificación); cuatro ojos, fuente de la candidata | 204 |
| `POST /v1/models/{id}/activation` | `ingeniero_riesgo` + MFA + `governance:promotion` | `mark_active` (la unidad `activo`/`inactivo`) | 204 |
| `POST /v1/models/{id}/retirement` | `cro` + MFA | `retire` (`inactivo`, `rechazado` o `validacion_fallida` → `retirado`) | 200 `ModelVersion` |
| `POST /v1/models/{id}/freeze` | `governance:freeze` (solo `bias-monitoring-job`) | `freeze` con `data_sources` e `initial_disparity` y la reducción por tamaño; el evento puede quedar pendiente | 204 |
| `POST /v1/models/{id}/frozen-resolution` | `cumplimiento` + MFA ≤ 15 min | `reactivar`, `descartar` o `investigar` con justificación | 204 |
| `GET /v1/models`, `GET /v1/models/{id}` | `ingeniero_riesgo`, `cro`, `cumplimiento` | `Page[ModelVersion]` (`?state=a,b`) y detalle con `validation_report` | 200 |
| `GET /v1/models/{id}/feature-dictionary`, `…/feature-spec` | `governance:read-dictionary`, `governance:read-feature-spec` | El JSON canónico guardado de la versión | 200 |
| `GET /v1/serving-config` | `governance:read-serving` | Desde la copia en memoria; `ETag` y 304 con `If-None-Match` | 200 / 304 |
| `GET /v1/policies`, `POST /v1/policies`, `POST /v1/policies/{id}/approval` | `analista`/`cumplimiento`/`cro`; `cro` + MFA | Lista; propuesta; aprobación (activa y deja la anterior `historica`) o rechazo con justificación | 200 / 200 / 204 |
| `GET /v1/data-sources`, `POST /v1/data-sources` | `ingeniero_riesgo`/`cro`/`cumplimiento`; `ingeniero_riesgo` + MFA | Lista; alta (queda `en_evaluacion`) | 200 |
| `POST /v1/data-sources/{id}/comparisons` | `ingeniero_riesgo` + MFA | Las condiciones de BR-U4-13 (409: `no_active_version`, `active_version_frozen`, sin `InferenceService` de staging, otra comparación `lanzado`) y el Job en modo `source_comparison` | 200 `ValidationRun` |
| `PUT /v1/validation-runs/{run_id}/source-counts` | `governance:validation-report` | F32 + F25: solo una corrida `source_comparison` `lanzado`, una vez; guarda las tablas de conteo y el `PrePostReport` de la fuente | 204 |
| `POST /v1/data-sources/{id}/decision` | `cumplimiento` + MFA | `aprobada`/`rechazada` solo con `pre_post_report`; distinto de quien propuso; el evento lleva el informe (≤ 48 KiB) | 204 |

`/readyz` y `/healthz` van en el puerto 8081 (`app.state.ops_app`); `/readyz` es 200 con la copia de `serving-config` cargada.

## Errores

`model_fsm.Forbidden` → 403; `model_fsm.ConflictState` → 409 con el `reason` del catálogo `ProblemReason` de U0 cuando el motivo es
uno de ellos (`transition_pending`, `no_active_version`, `active_version_frozen`; el resto de los motivos internos no sale);
`EntityNotFound` → 404; `RegistrationRejected` → 422 `validation_error` (con el motivo estable en `invalid_params`);
`RegistryUnavailable`, `PoolTimeout`, `ServingConfigUnavailable` y los fallos de Kubernetes o de bias → 503. No faltó ningún `reason`
en U0.

## Decisiones de U04-T04 (el diseño no las fija)

| Decisión | Razón |
|---|---|
| Los estados HTTP son los del contrato de U0 (`POST /v1/models` 200; `approval`, `activation`, `freeze`, `frozen-resolution`, `decision`, `source-counts` 204) | El plan y la tarea hablan de «200» y «201» en algunos casos; U0 no se toca, y su OpenAPI no declara 201 |
| `KubernetesJobs` usa `httpx` contra la API REST (5 s), no el cliente oficial de Kubernetes | No sumar un paquete al `uv.lock` por tres llamadas; el doble de las pruebas es un `MockTransport` que guarda el manifiesto |
| El Job se crea **después** de confirmar la transición; si Kubernetes falla, la corrida queda `fallido` y la versión `validacion_fallida` | Un Job sin corrida registrada no podría devolver su informe; `start_validation` ganó el parámetro `run_id` |
| `start_source_comparison` no escribe evidencia: solo inserta la `ValidationRun` `source_comparison` bajo el `GLOBAL_LOCK` y crea el Job | BR-U4-13: la comparación no cambia el estado de ninguna versión |
| Una fuente propuesta es una sola transición `-` → `en_evaluacion` con el evento `evaluacion_iniciada` | BR-U4-13 («al proponer pasa a `en_evaluacion`») y BR-U4-17 (un evento por transición) |
| `isvc-` + los 8 hex finales del `model_version_id` | `mv-<fecha>-<8 hex>` (`vectra_reference.package`) |
| `feature-spec` se sirve en el JSON canónico de U5 (`sort_keys`, indent 2, salto final) | La columna es `jsonb` y no conserva bytes; para un paquete de U5 el resultado es idéntico al `feature_spec.json` |
| El tamaño del evento se mide sobre el cuerpo completo de `POST /v1/entries` con `json.dumps` por defecto (cota por arriba de `httpx`); el `PrePostReport` de la decisión igual | Que el registro nunca reciba más de 64 KiB y que el informe del evento nunca pase de 48 KiB, sin depender del serializador |
