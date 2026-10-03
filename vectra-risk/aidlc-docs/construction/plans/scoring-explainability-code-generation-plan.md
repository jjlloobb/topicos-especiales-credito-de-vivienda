# Plan de tareas (Code Generation Part 1) — U7 `scoring-explainability`

**Este plan es la única fuente de verdad para generar el código de U7.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U7. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U7 `scoring-explainability`: `scoring-service` (orquesta la recomendación) y `explainability-service` (explicación, narrativa, factualidad y resumen al solicitante) |
| Historias (dueña) | US-103, US-104, US-105, US-106, US-109, US-110, US-111, US-113, US-207 |
| Ubicación | `vectra-risk/scoring-explainability/` (dos servicios) y Applications en `vectra-risk-gitops` |
| Datos propios | Ninguno: servicios sin estado, cachés en memoria |
| Depende de | U0 (tipos, `check_preconditions`/`build_outcome`, `create_app`, `deps` con deadline y circuit breaker, `vectra_common.deadline`), U1 (plataforma, cuotas, `flows.yaml`, supply chain), U2 (clientes `scoring-service` y `explainability-service`), U3 (append con idempotencia, proyección `explanation` por `seq`), U4 (`serving-config`, diccionario F103), U5 (conjuntos RT-1/RT-3/RT-4 como fixtures), U6 (`:predict`, `:explain`) |
| Lo consumen | case-service (U8, F15), console-bff (U10, F12), U12 (carga y RT) |

**Diseño de entrada:**
- Functional Design: `construction/scoring-explainability/functional-design/` (BR-U7-01..16, PBT-U7-01..08).
- NFR Requirements: `construction/scoring-explainability/nfr-requirements/` (NFR-U7-01..43).
- NFR Design: `construction/scoring-explainability/nfr-design/` (P-U7-01..09).
- Infrastructure Design: `construction/scoring-explainability/infrastructure-design/` (INF-U7-01..05).

**AUTONOMIA-01:** las verificaciones estáticas, las propiedades y las pruebas de integración
con dobles corren en CI. Las que necesitan el clúster las ejecuta **un operador en kind**
después de un PR aprobado (Paso 18), con la evidencia adjunta al PR.

**Dobles hasta que existan las unidades reales:** U3, U4 y U6 ya tienen plan, así que en CI
se usan dobles HTTP que siguen sus contratos (`vectra_contracts`). Las pruebas de kind usan
las unidades reales.

### Estructura de destino

```text
vectra-risk/scoring-explainability/
|-- Makefile  pyproject.toml  .importlinter
|-- scoring/          src/scoring/  {config, orchestrator, policy, serving_config_client, clients, metrics, app}.py
|-- explainability/   src/explainability/  {config, explain, dictionary_cache, narrative, factuality, applicant, metrics, app}.py
|                     templates/  template_v1.txt  applicant_v1.txt
|-- chart/            templates/  values-{prod,staging,kind}.yaml
|-- policies/         conftest/
|-- observability/    rules/  rules/tests/  runbooks/
`-- tests/            unit/ property/ integration/ doubles/ fixtures/ load/
```

---

## 2. Pasos

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `scoring-explainability/`**
  - Directorios de §1; `pyproject.toml` (dos miembros del workspace) que dependen de `vectra_contracts` y `vectra_common`.
  - Contratos de import-linter:
    - `factuality` no importa `narrative` (BR-U7-11);
    - ningún módulo importa `httpx` fuera de `vectra_common.deps` (P-U0-07);
    - ninguno importa librerías de circuit breaking (NFR-U7-43) ni clientes de LLM (NFR-U7-32);
    - ningún módulo contiene la URL ni un cliente del core bancario (BR-U7-02).
  - Diseño: BR-U7-02, 11; NFR-U7-30, 32, 43; P-U7-07.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config scoring-explainability/.importlinter && make -C scoring-explainability check` sobre el esqueleto; `uv run pytest scoring-explainability/tests/unit/test_no_core_client.py`.

- [ ] **Paso 2 — Presupuestos como constantes**
  - `scoring/config.py` y `explainability/config.py`:
    - presupuesto previo al registro (700 ms);
    - timeouts por llamada de NFR-U7-10;
    - append: 2 intentos de 2,5 s, con jitter de 0 a 100 ms;
    - `fail_closed`: 250 ms;
    - tope propio de explainability: 700 ms, más 50 ms de margen;
    - tamaños de pool de P-U7-04;
    - umbrales del circuit breaker (≥ 50 % en 20 llamadas dentro de 30 s; semiabierto a los 10 s);
    - caché de `serving-config` ≤ 5 s y LRU del diccionario de 4 versiones.
  - Diseño: INF-U7-04; P-U7-01, 02, 04, 05; NFR-U7-10, 11.
  - **Aceptación**: `uv run pytest scoring-explainability/tests/unit/test_config.py`:
    - `700 + 250 + 50 ≤ 1000 ms`;
    - `20 s > 0,7 + 2 × 2,5 + 0,1 s`;
    - ningún presupuesto se lee de variables de entorno.

### Bloque B — Lógica pura

- [ ] **Paso 3 — `policy`**
  - `evaluate(PolicyEvaluationInput) -> PolicyResult`:
    - las cinco reglas, evaluadas todas y con sus motivos acumulados en el orden de la tabla;
    - `cutoff_efectivo` por canal;
    - el resultado más conservador gana;
    - `normative` nulo → `revision_requerida`, sin fail-closed.
  - Diseño: BR-U7-04, 05, 06, 07; NFR-U7-41. Historias: US-103, US-106, US-207.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_policy.py tests/unit/test_policy_examples.py`:
    - PBT-U7-01 y PBT-U7-02;
    - ejemplo de US-207: tasa sobre usura y normativa no vigente → `revision_requerida` con los dos motivos;
    - un caso RT-4 de U5 → `baja_confianza`.

- [ ] **Paso 4 — `narrative`**
  - `TemplateNarrativeGenerator` (`template:v1`) detrás de la interfaz `NarrativeGenerator`, con una sola implementación registrada:
    - top 5 por |SHAP|, sin ceros y con desempate por `feature_id`;
    - intensidad `fuerte`, `moderada` o `leve`;
    - encabezado y leyenda post-hoc;
    - sin números.
  - Diseño: BR-U7-10; NFR-U7-32. Historia: US-104.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_narrative.py tests/unit/test_narrative_examples.py`:
    - PBT-U7-03;
    - narrativa de un caso fijo idéntica al texto esperado;
    - una sola implementación de `NarrativeGenerator`.

- [ ] **Paso 5 — `factuality`**
  - `FactualityValidator` independiente del generador:
    - parte la narrativa;
    - reconoce `label_es` y la dirección contra el diccionario;
    - reimplementa por separado la selección y el desempate.
  - Diseño: BR-U7-11; NFR-U7-41. Historia: US-105.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_factuality.py`:
    - PBT-U7-04 (round-trip);
    - PBT-U7-05 (mutaciones);
    - una narrativa con un factor invertido → `False`.

- [ ] **Paso 6 — `applicant`**
  - Hasta 3 factores `applicant_safe` con SHAP > 0, plantilla `applicant:v1` y leyenda.
  - Ningún campo prohibido ni número. No se guarda.
  - Diseño: BR-U7-14. Historia: US-110.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_applicant.py`: PBT-U7-06, más el ejemplo de un rechazo sin campos prohibidos.

- [ ] **Paso 7 — Resumen de la lógica pura**
  - Cobertura de ramas **100 %** en `policy`, `narrative` y `factuality`.
  - `mutmut` en `policy` y `factuality`, con 0 sobrevivientes sin justificar.
  - Resumen en `aidlc-docs/construction/scoring-explainability/code/logic.md`.
  - Diseño: NFR-U7-40, 41, 42.
  - **Aceptación**: `uv run pytest scoring-explainability/tests/unit scoring-explainability/tests/property --cov=policy --cov=narrative --cov=factuality --cov-branch --cov-fail-under=100` y `uv run mutmut run --paths-to-mutate scoring-explainability/scoring/src/scoring/policy.py,scoring-explainability/explainability/src/explainability/factuality.py` sin sobrevivientes fuera de la allowlist.

### Bloque C — `explainability-service`

- [ ] **Paso 8 — `POST /v1/explanations`**
  - `dictionary_cache`:
    - LRU de 4 versiones, sin expiración;
    - precarga de la versión activa al arrancar, si governance responde.
  - `explain`:
    - lee `x-vectra-deadline` con `vectra_common.deadline`;
    - corte en `min(deadline − 50 ms, llegada + 700 ms)`;
    - diccionario (F103) y `:explain` (F22) en paralelo con `asyncio.TaskGroup`, cancelando el otro si uno falla;
    - verificación de versión, cobertura del diccionario, narrativa y factualidad;
    - errores tipificados: 409 `version_mismatch`, 422 `feature_dictionary_incomplete`/`factuality_failed`, 504 `timeout`, 503 `unavailable`, 500 `error`;
    - un cliente por dependencia (P-U7-04).
  - Diseño: BR-U7-08, 09, 10, 11; P-U7-01, 04, 05; NFR-U7-02, 10, 21. Historias: US-104, US-105, US-111.
  - **Aceptación**: `uv run pytest scoring-explainability/tests/integration/test_explanations.py`, con dobles de KServe y de governance:
    - caché fría con diccionario y `:explain` a 400 ms cada uno → ~400 ms;
    - cabecera en el pasado → 504 inmediato;
    - cabecera a 1 h en el futuro o mal formada → corte a los 700 ms;
    - explicador de otra versión (RT-3) → 409;
    - diccionario incompleto → 422;
    - generador alterado en la prueba → 422 `factuality_failed`;
    - 5 versiones → se descarta la menos usada.

- [ ] **Paso 9 — `POST /v1/applicant-summaries`**
  - Recibe `ApplicantSummaryRequest` (`case_id`, `recommendation_entry_id`).
  - Lee la entrada por `seq` en la proyección `explanation` (F23) y comprueba que pertenece al `case_id`. Si no existe o es de otro caso → 409, sin datos parciales.
  - Llama a `applicant.generate` y emite el log `applicant_summary.generated` (solo con `case_id`).
  - Roles del BFF verificados por scope (F12).
  - Diseño: BR-U7-13, 14; P-U7-03; NFR-U7-03. Historia: US-110.
  - **Aceptación**: `uv run pytest scoring-explainability/tests/integration/test_applicant_summaries.py`, con un doble del registro:
    - caso sin explicación → 409;
    - caso de abuso: `recommendation_entry_id` de otro caso → 409;
    - el log no contiene texto del resumen.

### Bloque D — `scoring-service`

- [ ] **Paso 10 — Clientes y caché de `serving-config`**
  - Un `httpx.AsyncClient` por dependencia con `deps.call` (P-U7-04): `:predict` 20, explainability 20, registro 10, `serving-config` 5. Cada uno con su circuit breaker y la causa que le corresponde.
  - `serving_config_client`:
    - caché ≤ 5 s con `If-None-Match`;
    - revalidación fallida con la entrada vencida → `no_disponible`;
    - llama al `inference_service` indicado.
  - Diseño: BR-U7-01; P-U7-04, 05; NFR-U7-11, 43.
  - **Aceptación**: `uv run pytest scoring-explainability/tests/integration/test_clients.py`:
    - KServe colgado agota sus 20 conexiones y una explicación en paralelo responde en su tiempo normal;
    - tras congelar en el doble de governance → `FailClosed(model_frozen)` en ≤ 6 s;
    - caché vencida + governance caído → `serving_config_unavailable`;
    - con explainability caído, tras 20 llamadas → `FailClosed` en < 50 ms.

- [ ] **Paso 11 — `orchestrator`**
  - Secuencia de BR-U0-08 con `check_preconditions` y `build_outcome` de U0:
    - presupuesto previo al registro de 700 ms, con `deadline=` en cada llamada y `x-vectra-deadline` hacia explainability;
    - append de la `recommendation` con `idempotency_key` fija por intento: 2 intentos, solo ante 503, timeout o error de conexión, sin reintento con el circuito abierto;
    - un 409 de idempotencia → `registry_unavailable` + `registry.idempotency_conflict`;
    - `fail_closed` best effort de 250 ms.
  - Métricas:
    - `vectra_scoring_failclosed_total{cause}`;
    - `vectra_recommendations_total{outcome}`;
    - `vectra_registry_append_attempts_total` y `vectra_registry_append_abandoned_total`;
    - `vectra_deadline_exhausted_total`.
  - Diseño: BR-U7-01, 02, 03, 12, 15, 16; P-U7-01, 02, 03; NFR-U7-04, 12, 13. Historias: US-103, US-109, US-111, US-113.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_orchestrator.py tests/integration/test_orchestrator.py`:
    - PBT-U7-07 (toda combinación de fallos → 200 `RecommendResult`, y nunca una `Recommendation` sin `registry_entry_id` ni con versiones distintas);
    - PBT-U7-08 (pares RT-1 de U5 → salidas idénticas);
    - propiedad de P-U7-01: sin invocar el registro para una `recommendation`, responde antes de 1 s;
    - ejemplos:
      - respuesta con `model_version_id = M` y `policy_version_id = P` (US-103);
      - versión distinta (RT-3) → `FailClosed(version_mismatch)` y la métrica sube (US-111);
      - `ScoringRequest.model_version_id` distinto del de `serving-config` → `FailClosed(version_mismatch)` sin llamar a KServe ni al explicador (agregado por U8 FD Q1);
      - registro sin réplica → `FailClosed(registry_unavailable)` sin recomendación entregada (US-113);
      - registro que falla una vez → dos llamadas con la misma llave y una entrada;
      - registro que confirma a los 2,6 s en los dos intentos → `FailClosed`, la entrada existe y `abandoned` = 1;
      - un 4xx → un solo intento.

- [ ] **Paso 12 — Endpoints, arranque y apagado de los dos servicios**
  - `create_app` de U0 con `POST /v1/recommendations` (F15) y `POST /v1/explanations` / `POST /v1/applicant-summaries` (F20, F12). Scopes y audiencias de U2.
  - Readiness y liveness solo del proceso (8081).
  - uvicorn con `timeout_graceful_shutdown = 10`.
  - Diseño: BR-U7-13; INF-U7-01, 03; NFR-U7-21, 30, 31; P-U7-07. Historias: US-103, US-110.
  - **Aceptación**: `uv run pytest scoring-explainability/tests/integration/test_app.py test_shutdown.py`:
    - con governance caído, explainability queda listo y la primera explicación pide el diccionario;
    - `SIGTERM` a los 0,5 s de una solicitud cuyo registro responde a los 3 s → `Recommendation` con `registry_entry_id`;
    - las etiquetas de las métricas están dentro de la allowlist de P-U7-07;
    - una ruta sin scope → 403.

- [ ] **Paso 13 — Resumen de los servicios**
  - Cobertura de ramas ≥ 95 % en los dos servicios y **100 %** en `orchestrator`.
  - Resumen en `aidlc-docs/construction/scoring-explainability/code/services.md`.
  - Diseño: NFR-U7-40, 42.
  - **Aceptación**: `uv run pytest scoring-explainability/tests --cov --cov-branch --cov-fail-under=95` y el umbral por módulo (`orchestrator` = 100 %).

### Bloque E — Despliegue y operación

- [ ] **Paso 14 — Dockerfiles y cadena de suministro**
  - Una imagen por servicio sobre una base Python oficial pinneada por digest, `runAsNonRoot` y `readOnlyRootFilesystem`. Las plantillas van dentro de la imagen de explainability.
  - Construidas, escaneadas, con SBOM y firmadas por `supply-chain.yml` de U1.
  - Diseño: NFR-U7-32; P-U7-07.
  - **Aceptación**: `hadolint scoring-explainability/*/Dockerfile`; prueba sobre el SBOM: ningún cliente de LLM y ninguna librería de circuit breaking.

- [ ] **Paso 15 — Chart, cuota y flujos**
  - Por servicio: `Deployment`, `Service`, `HorizontalPodAutoscaler`, `PodDisruptionBudget`, `ServiceAccount`, `ExternalSecret`, `ServiceMonitor`.
    - El `ExternalSecret` trae la llave `private_key_jwt` desde la bóveda.
    - Recursos y probes de INF-U7-01; spread por zona; `vectra-high`; sidecar nativo de Linkerd.
    - `preStop.sleep` de 5 s y `terminationGracePeriodSeconds: 20`.
    - Sin variables con los nombres de los presupuestos.
  - Aporte de U7 a la cuota de `vectra-app` en `platform/policies/quotas/` de U1 (INF-U7-02).
  - Comprobar que F12, F15, F18–F23 y F103 están en `platform/network/flows.yaml`, sin flujos nuevos.
  - Diseño: INF-U7-01, 02, 03, 04, 05; P-U7-06; NFR-U7-20, 30.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test scoring-explainability/policies/conftest/`, que verifica HPA 2–6, PDB, spread, `priorityClassName`, `preStop.sleep`, el período de gracia y la ausencia de variables de presupuesto. Además, `conftest test platform/policies/quotas/` (cuota ≥ suma de aportes) y `uv run python platform/network/generate.py --check`.

- [ ] **Paso 16 — Alertas y runbooks**
  - `PrometheusRule` con las alertas de P-U7-08: `CircuitOpen`, `RegistryAppendSlow`, `RegistryAppendAbandoned`, `RegistryIdempotencyConflict`, `FactualityFailed`, `ExplainerVersionMismatch` y `RecommendationLatencyHigh`.
  - Cada una con su runbook.
  - `PromotionMismatchPersistent` es de U4: aquí solo se prueba que `vectra_scoring_failclosed_total{cause="version_mismatch"}` existe con ese nombre.
  - Diseño: P-U7-08; BR-U7-03; NFR-U7-31.
  - **Aceptación**: `promtool test rules scoring-explainability/observability/rules/tests/*.yaml`; `uv run python platform/tests/test_runbooks.py --root scoring-explainability`; prueba que compara el nombre de la métrica con la expresión de la regla de U4.

- [ ] **Paso 17 — Applications, especificación de carga y trazabilidad**
  - Application en la wave 5, por entorno y sin auto-sync.
  - Script k6 para U12: 10 solicitudes/s de diseño y 20/s de prueba, con umbrales p95 de 400 ms, 250 ms y 500 ms y p99 de 1 s.
  - Trazabilidad de cada BR-U7 a una prueba.
  - Diseño: P-U1-12; NFR-U7-01, 02, 03.
  - **Aceptación**: `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `k6 inspect scoring-explainability/tests/load/recommendations.js`; `uv run python platform/tests/test_traceability.py --unit scoring-explainability --all`.

### Bloque F — Verificación en kind (con aprobación humana)

- [ ] **Paso 18 — Puerta de aprobación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–17 aprobado por un humano, con U1–U6 instalados en kind y un modelo activo.
  - El operador ejecuta, con evidencia, los escenarios de P-U7-09 y además:
    1. explainability escalado a 0 → `FailClosed(explainer_unavailable)`; el circuito se abre y salta `CircuitOpen`;
    2. KServe saturado → `FailClosed(timeout)`;
    3. governance caído con la caché vencida → `serving_config_unavailable`;
    4. standby del registro pausado → `FailClosed(registry_unavailable)` en ≤ 6,1 s y `RegistryAppendAbandoned`;
    5. promoción azul/verde con tráfico → 0 `version_mismatch`;
    6. `kubectl rollout restart` de scoring durante la carga → `vectra_registry_append_abandoned_total` = 0;
    7. congelamiento → `FailClosed(model_frozen)` en ≤ 6 s;
    8. suite de conectividad de U1: los flujos permitidos responden y las salidas a X01 y X02 se bloquean;
    9. cuando exista U12, prueba de carga a 10 y 20 solicitudes/s con reinicio de réplicas → objetivos de NFR-U7-01..03.
  - Diseño: P-U7-01, 02, 03, 05, 06, 09; INF-U7-03, 05; NFR-U7-01, 02, 03, 11, 22. Historias: US-111, US-113.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con el comando, la salida y el resultado esperado frente al obtenido.

### Bloque G — Cierre

- [ ] **Paso 19 — Repositorio, migraciones y frontend: N/A**
  - U7 no tiene base de datos, migraciones ni interfaz; la consola es de U10.
  - **Aceptación**: `test ! -d scoring-explainability/migrations && test ! -d scoring-explainability/frontend`.

- [ ] **Paso 20 — Cierre de la unidad**
  - **Aceptación**: `make -C scoring-explainability check`, que corre en orden las verificaciones estáticas, las propiedades y las pruebas de integración de los Pasos 1–17 y termina en 0. Las de kind (Paso 18) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

Verificada con un script contra las líneas «Diseño» e «Historia(s)» de cada paso antes de presentarla.

| Historia | Pasos |
|---|---|
| US-103 | 3, 11, 12 |
| US-104 | 4, 8 |
| US-105 | 5, 8 |
| US-106 | 3 |
| US-109 | 11 |
| US-110 | 6, 9, 12 |
| US-111 | 8, 11, 18 |
| US-113 | 11, 18 |
| US-207 | 3 |

| Diseño | Pasos |
|---|---|
| BR-U7-01..16 | 1, 3, 4, 5, 6, 8, 9, 10, 11, 12, 16 |
| NFR-U7-01..43 | 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18 |
| P-U7-01..09 | 1, 2, 8, 9, 10, 11, 12, 14, 15, 16, 18 |
| INF-U7-01..05 | 2, 12, 15, 18 |

| Propiedad | Paso |
|---|---|
| PBT-U7-01, 02 | 3 |
| PBT-U7-03 | 4 |
| PBT-U7-04, 05 | 5 |
| PBT-U7-06 | 6 |
| PBT-U7-07, 08 y la propiedad de P-U7-01 | 11 |

## 4. Cumplimiento de extensiones (plan de tareas U7)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Ningún paso aplica ni sincroniza; los escenarios con clúster los ejecuta el operador (Paso 18) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-03 | Cumple | Sin cliente ni URL del core (Paso 1); bloqueo de X01 (Paso 18) |
| AUTONOMIA-04 | Cumple | Congelamiento visible en ≤ 6 s, nunca con una `serving-config` vencida (Pasos 10, 18) |
| AUTONOMIA-05 | Cumple | Sin egress ni datos del solicitante en la telemetría (Pasos 12, 15, 18) |
| AUTONOMIA-06 | Cumple | PBT-U7-07, append con reintento acotado y apagado sin abandono (Pasos 11, 12, 18) |
| SECURITY-03 / 07 / 08 / 11 / 13 / 14 / 15 | Cumple | Pasos 8, 9, 11, 12, 14, 15, 16 (SECURITY-11: casos de abuso RT-1, RT-3, resumen de un caso ajeno y cabecera manipulada en los Pasos 8, 9 y 11) |
| RESILIENCY-01 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 14 / 15 | Cumple | Pasos 10, 11, 12, 15, 16, 18 |
| PBT-01..10 | Cumple | Pasos 3–6 y 11 (PBT-U7-01..08), Paso 7 (perfil `ci`) y pruebas de ejemplo en los Pasos 3, 4, 6, 9 y 11 |
