# Servicios de `scoring-explainability` (U07-T03, Pasos 8 a 13 del plan)

Resumen de los dos servicios, sus clientes, sus pruebas y su cobertura. Se cierra con lo diferido y con lo que la tarea dejó abierto. Diseño: BR-U7-01 a 03, 08 a 16; P-U7-01 a 05, 07, 08; NFR-U7-02, 03, 04, 10 a 13, 21, 30, 31, 40, 42, 43; INF-U7-01, 03, 04.

## Módulos

| Módulo | Qué hace | Diseño · historias |
|---|---|---|
| `explainability/src/explainability/dictionary_cache.py` | `DictionaryCache`: diccionario por `model_version_id`, sin vencimiento, LRU de 4 versiones; `preload()` de la versión activa al arrancar (en segundo plano, sin bloquear). Cliente propio de governance (F103, pool 5). | P-U7-05; NFR-U7-21 · US-104 |
| `explainability/src/explainability/explain.py` | `Explainer.explain`: corte en `min(deadline − 50 ms, llegada + 700 ms)`; diccionario y `:explain` en un `asyncio.TaskGroup` (el otro se cancela si uno falla); después versión (409), cobertura (422), narrativa y factualidad (422). Una conexión rechazada o descartada hacia `:explain` da 503 o 504, nunca 500. Métrica `vectra_explanations_total{result}`. | BR-U7-08 a 11; P-U7-01, 04 · US-104, 105, 111 |
| `explainability/src/explainability/summaries.py` | `RegistryExplanations` (cliente F23, pool 5) y `ApplicantSummaries`: lee la entrada por `seq` en la proyección `explanation`, comprueba que es del `case_id` (si no, 409 sin datos parciales), llama a `applicant.generate` y emite `applicant_summary.generated` solo con `case_id`. No guarda el resumen. | BR-U7-13, 14; P-U7-03 · US-110 |
| `explainability/src/explainability/app.py` | `create_app` de U0 con las dos rutas (`/v1/explanations` F20, `/v1/applicant-summaries` F12); URLs por entorno; precarga en el `lifespan`; cierra los clientes al salir. | INF-U7-01, 04; NFR-U7-21 |
| `scoring/src/scoring/serving_config_client.py` | Caché de ≤ 5 s revalidada con `If-None-Match`; con la entrada vencida y governance sin responder devuelve `None` (`no_disponible`): nunca usa una entrada vencida. Una sola revalidación a la vez. | BR-U7-01; P-U7-05 |
| `scoring/src/scoring/clients.py` | `PredictClient` (`:predict`, pool 20), `ExplainabilityClient` (F20, pool 20), `RegistryClient` (F21, pool 10) sobre `deps.call`; traducen los errores de domain-entities §5; `PolicySource` (ver «Abierto»). | P-U7-04; NFR-U7-11, 43 |
| `scoring/src/scoring/orchestrator.py` | La secuencia de BR-U0-08 con `check_preconditions` y `build_outcome`, todas las ramas; presupuesto de 700 ms previo al registro; append con 2 intentos y la misma llave (UUID v4 por solicitud); `fail_closed` best effort de 250 ms con otra llave y solo `cause`. | BR-U7-01 a 03, 12, 15, 16; P-U7-01 a 03 · US-103, 109, 111, 113 |
| `scoring/src/scoring/app.py` | `create_app` de U0 con `/v1/recommendations` (F15); URLs por entorno; cierra los clientes al salir; `run` sirve 8080 y 8081 con `ops_server`. | INF-U7-01, 03, 04 |
| `*/metrics.py` | Las métricas de P-U7-08 con etiquetas solo de la allowlist de P-U7-07 (`outcome`, `cause`, `reason`, `dependency`, `result`, `attempt`, `stage`). | P-U7-07, 08 |

## URL del explicador y de `:predict`

KServe se llama por el `Service` del `InferenceService` que dice `serving-config` (`isvc-<8 hex>`). El host sale de una plantilla de URL por configuración con el marcador `{inference_service}` (`EXPLAINABILITY_EXPLAINER_URL_TEMPLATE`, `SCORING_PREDICTOR_URL_TEMPLATE`); la ruta es `/v1/models/<isvc>:explain` y `:predict`, protocolo v1. Las pruebas usan `http://{inference_service}-explainer.vectra-serving` y `-predictor`, que es la convención de KServe (`<isvc>-predictor` en el namespace `vectra-serving`, como dicen los runbooks de `model-serving/docs`). Ni `model-serving/docs/values.md` ni el chart de U6 fijan el host del `Service` del explicador: queda para la verificación de U12 (candidata).

## Pruebas

| Archivo | Cubre |
|---|---|
| `tests/integration/test_explanations.py` | CA-1: paralelismo (~400 ms), cabecera pasada/lejana/mal formada, RT-3, diccionario incompleto o de otra versión, generador alterado, LRU, R-3, precarga. |
| `tests/integration/test_applicant_summaries.py` | CA-2: 409 sin explicación, abuso con una entrada de otro caso (también con un registro defectuoso), log solo con `case_id`, resumen no guardado, registro caído. |
| `tests/integration/test_clients.py` | CA-3: un cliente y un breaker por dependencia, caché y `If-None-Match`, congelamiento, `serving_config_unavailable`, breaker de explainability y del registro, bulkhead con sockets reales. |
| `tests/integration/test_orchestrator.py` y `tests/property/test_orchestrator.py` | CA-4: ejemplos del Paso 11, PBT-U7-07 (con un oráculo de BR-U0-02 escrito aparte), P-U7-01 y PBT-U7-08 (20 pares RT-1 de U5 y texto generado, con la cadena real de explainability). |
| `tests/integration/test_app.py`, `test_shutdown.py` | CA-5: arranque con governance caído, scopes, roles del resumen, allowlist de etiquetas, SIGTERM con el registro lento en un proceso real. |
| `tests/integration/test_edges.py` | Bordes con efecto: respuestas ilegibles, traducción de errores, ciclo de vida, `main`. |
| `tests/doubles/` | Dobles de U3, U4 y U6 y de explainability, que siguen los contratos de `vectra_contracts`. `AsgiTransport` aplica el timeout de la solicitud; el límite de conexiones solo se ejerce con `servers.py` (sockets reales). |

La semilla de Hypothesis se imprime en el encabezado de pytest (`tests/conftest.py`); `--hypothesis-seed=N` repite la corrida.

## Cobertura (NFR-U7-40)

`make -C scoring-explainability coverage` corre toda la suite con `--cov=scoring --cov=explainability --cov-branch` y exige ≥ 95 % en cada servicio, 100 % en `policy`, `narrative`, `factuality` y 100 % en `orchestrator`. Cifras de la última corrida en `bitacoras/U07-T03.md`.

## Decisiones y desviaciones que conviene conocer

- **`dictionary` de `check_preconditions`.** scoring no lee el diccionario (F103 es de explainability), pero `check_preconditions` exige uno: sin él, toda `Explanation` da `feature_dictionary_incomplete`, y `factuality_failed` (causa 9) es inalcanzable porque la causa 8 trata un `dictionary` ausente como «falta». El `orchestrator` declara la cobertura que explainability ya verificó (`attested_dictionary`): factor por factor para una `Explanation`, y uno vacío de la versión de la predicción para `factuality_failed`. Candidata sobre U0.
- **Fallo de `:predict` y la causa.** P-U7-04 y P-U7-09 dicen que un `:predict` que falla da `timeout`; la tabla de BR-U0-02 lo da como `serving_config_unavailable` (falta la predicción, causa 2) y es lo que `check_preconditions` produce. Se sigue la tabla de U0.
- **Versión de la predicción distinta de la de `serving-config`.** `check_preconditions` no la compara. El `orchestrator` no pide explicación y cierra con `version_mismatch` (SECURITY-13: nunca una recomendación de una versión distinta de la registrada).
- **Registro que «responde a los 3 s».** Cada intento espera 2,5 s (P-U3-02), así que un registro que responde a los 3 s agota el primer intento. La prueba de apagado usa un primer intento lento y un reintento que recupera el ack original con la misma llave: lo que debe sobrevivir al SIGTERM.
- **`fail_closed` con `local_cause`.** El doble del registro rechaza con 422 un payload con `cause` y `local_cause` (BR-U0-38 no valida) y con 403 uno con `local_cause` solo, como el registro real (candidata de U03-T03).
- **Respuesta de `/v1/recommendations`.** Se serializa el `Recommendation` o el `FailClosed` ya construido; `RecommendResult(...)` volvería a validar y lanzaría `ContractViolation`, porque `Recommendation` solo se construye con las fábricas de U0.
- **uvicorn y el estado de salida.** Tras un SIGTERM el proceso termina con `-SIGTERM` (uvicorn vuelve a emitir la señal capturada); no es una caída.

## Diferido

- `mutmut` sobre `policy` y `factuality` (NFR-U7-41): T3 (enmienda §2.3).
- Carga (T3), Dockerfiles, chart, Application y trazabilidad: U07-T04.
- Escenarios en kind, incluido D1 (F22 apagado): consolidados en U12, Paso 18.

## Abierto

- **Fuente de la política activa.** `PolicyEvaluationInput` pide `cutoff`, `low_confidence_threshold` y `channel_rules`. `ServingConfig` (U0 §9.3) no los trae y ninguna ruta del contrato los sirve a un cliente de servicio (`GET /v1/policies` pide roles de usuario). scoring los lee de una `PolicySource` inyectada (las pruebas usan una fija) y `scoring.app.main` **no arranca** hasta que el diseño defina de dónde salen (ampliar `ServingConfig` o una ruta con scope `governance:read-serving`). Sin esa decisión, el chart de U07-T04 no puede desplegar scoring.
