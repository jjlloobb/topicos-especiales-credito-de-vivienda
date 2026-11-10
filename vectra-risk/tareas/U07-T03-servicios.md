# U07-T03 — Servicios de `scoring-explainability`: explicaciones, resumen al solicitante, clientes, `orchestrator` y endpoints

**Unidad:** U7 `scoring-explainability`
**Historias que implementa:** US-103, US-104, US-105, US-109, US-110, US-111 y US-113.
**Depende de:**
- U07-T02 (lógica pura: `policy`, `narrative`, `factuality` y `applicant`);
- en `main`, como contratos de los dobles: U0 (`create_app`, `REGISTRY`, `deps`, `deadline`, `service_token`, `ops_server`, `check_preconditions`, `build_outcome`), U3 (append con idempotencia y proyección `explanation` por `seq`), U4 (`serving-config`, `feature-dictionary`), U5 (pares RT-1, casos RT-4 y paquetes RT-3) y U6 (forma HTTP de `:predict` y `:explain`).

**Se despacha** cuando U07-T02 esté fusionado en `main`.
**Rama:** `tarea/U07-T03`, desde `origin/main`.

Bloques C y D del plan de U7 (`aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`), tarea «C+D (8, 10–13)» de `demo-recorte-funcional.md` §8, ampliada con el Paso 9 por P-1. Quedan 6 pasos, el máximo de RL-1. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 8 `POST /v1/explanations` | **E** | Completo. Mapear la conexión descartada (F22 apagado, D1) a 504/503 y nunca a 500; ya cabe en la aceptación (riesgo R-3) | Enmienda §3 U7 |
| 9 `POST /v1/applicant-summaries` | **E** | Completo: cliente F23, regla 409 y log `applicant_summary.generated`, con su aceptación | Decisión del usuario, 2026-11-10; enmienda §6 P-1 |
| 10 Clientes y caché de `serving-config` | **E** | Completo | Enmienda §3 U7; §5.1 |
| 11 `orchestrator` | **E** | Completo: **todas las ramas**, con PBT-U7-07 y 08 y la propiedad de P-U7-01 | Enmienda §3 U7; §5.1 |
| 12 Endpoints, arranque y apagado | **E** | Completo, con las tres rutas: `/v1/recommendations`, `/v1/explanations` y `/v1/applicant-summaries` | Decisión del usuario, 2026-11-10; enmienda §6 P-1 |
| 13 Resumen de los servicios | **E** | Completo | Enmienda §3 U7 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

**P-1:** decisión del usuario del 2026-11-10: opción (a) para U7, implementar `/v1/applicant-summaries`, como Q-6 en U4 (enmienda §6 P-1). `create_app` exige un handler por cada ruta de `REGISTRY`, así que los Pasos 9 y 12 entran completos.

---

## Alcance

**Dentro:** los Pasos 8 a 13 del plan, con su texto y su aceptación, sin recortes. Léelos allí. Precisiones:

### Paso 8 — `POST /v1/explanations` (E)

- `dictionary_cache`: LRU de 4 versiones, sin expiración; precarga de la versión activa al arrancar, si governance responde (NFR-U7-21; P-U7-05).
- `explain`:
  - lee `x-vectra-deadline` con `vectra_common.deadline`;
  - corta en `min(deadline − 50 ms, llegada + 700 ms)`; ausente o mal formada → solo el tope de 700 ms; en el pasado → 504 inmediato (P-U7-01);
  - diccionario (F103) y `:explain` (F22, al `inference_service` de `ExplainRequest`) **en paralelo** con `asyncio.TaskGroup`, cancelando el otro si uno falla;
  - después, verificación de versión (BR-U7-08), cobertura del diccionario (BR-U7-09), narrativa y factualidad (BR-U7-10, 11);
  - errores tipificados de `domain-entities.md` §5, con `Problem` y `reason` de `ProblemReason`: 409 `version_mismatch`, 422 `feature_dictionary_incomplete` o `factuality_failed`, 504 `timeout`, 503 `unavailable`, 500 `error`;
  - **una conexión rechazada o descartada hacia `:explain` (F22 apagado en D1) → 503 o 504, nunca 500** (riesgo R-3 de la enmienda);
  - un cliente por dependencia (P-U7-04): `:explain` 20 y diccionario 5.
- **Forma de `:explain`** (U6, protocolo v1 de KServe; candidata de U06-T01 en `CANDIDATAS.md`): cuerpo `{"instances": [FeatureVector]}` con 1 instancia; respuesta `{"explanations": [{contributions: [{feature_id, contribution}], base_value, model_version_id}]}`. El doble de KServe sigue esa forma; `model-serving/explainer/src/vectra_explainer/app.py` es la referencia.
- **URL del explicador.** El host se arma con el `inference_service` y una plantilla de URL que llega por configuración (INF-U7-04: el chart solo inyecta URLs). El plan no fija el host del `Service` de KServe; si `model-serving/docs/values.md` y el chart de U6 no lo dejan claro, regístralo en la bitácora y en `CANDIDATAS.md` para la verificación de U12.
- Métrica `vectra_explanations_total{result}` (P-U7-08).
- Diseño: BR-U7-08, 09, 10, 11; P-U7-01, 04, 05; NFR-U7-02, 10, 21. Historias: US-104, US-105, US-111.

### Paso 9 — `POST /v1/applicant-summaries` (E)

- Recibe `ApplicantSummaryRequest` (`case_id`, `recommendation_entry_id`) de U0.
- Lee la entrada por `seq` en la proyección `explanation` del registro (F23; `ExplanationProjection` dentro de `Page[EntryProjection]`, `GET /v1/entries` con `EntryFilter`) y comprueba que pertenece al `case_id`. Si no existe, no tiene explicación o es de otro caso → 409 `conflict_state`, sin datos parciales (BR-U7-13; P-U7-03).
- Cliente F23 propio, con pool 5 y su circuit breaker; registro caído → 503 hacia el BFF (P-U7-04).
- Llama a `applicant.generate` (U07-T02) y emite el log `applicant_summary.generated` (`LogEvent.APPLICANT_SUMMARY_GENERATED`) **solo** con `case_id`. El resumen no se guarda (BR-U7-14).
- Roles del BFF verificados por la ruta de `REGISTRY` (`analista` y `cro`, F12). La regla de objeto «decisión final `desfavorable`» es del BFF (U10), no de U7 (BR-U7-13).
- Sin `x-vectra-deadline`: la llamada F12 no la envía (P-U7-01).
- Diseño: BR-U7-13, 14; P-U7-03; NFR-U7-03. Historia: US-110.

### Paso 10 — Clientes y caché de `serving-config` (E)

- Un `DependencyClient` de `vectra_common.deps` por dependencia, con `deps.call`: `:predict` 20, explainability 20, registro 10, `serving-config` 5. Cada uno con su circuit breaker y su causa (P-U7-04).
- NFR-U7-11 como `BreakerConfig(open_for=10, window_size=20, failure_ratio=0.5, window_seconds=30)`. Token de servicio con `service_token.provider_from_env(audience, scopes)`, pasado como `token_source`; ante un 401, `deps.call` reintenta una vez (U0).
- `serving_config_client`: caché ≤ 5 s con `If-None-Match`; revalidación fallida con la entrada vencida → `no_disponible`, nunca una entrada vencida; llama al `inference_service` indicado.
- **Forma de `:predict`** (U6): `{"instances": [FeatureVector]}` → `{"predictions": [{score, confidence, model_version_id}]}`.
- Diseño: BR-U7-01; P-U7-04, 05; NFR-U7-11, 43.

### Paso 11 — `orchestrator` (E)

- Secuencia de BR-U0-08 y BR-U7-01 con `check_preconditions` y `build_outcome` de U0, **todas las ramas** (enmienda §5.1: `model_frozen`, `timeout`, `explainer_unavailable` y `version_mismatch` sostienen D1 y D2):
  - presupuesto previo al registro de 700 ms, con `deadline=` en cada llamada y `x-vectra-deadline` hacia explainability;
  - `serving_state = congelado` → `model_frozen` aunque la versión pedida difiera; `activo` con versión distinta → `version_mismatch` sin llamar a KServe ni al explicador;
  - append de la `recommendation` con `idempotency_key` = UUID v4 generado al recibir cada `POST /v1/recommendations`, **nunca** derivado de `case_id` ni de `attempt`, reutilizado solo por el reintento de ese append: 2 intentos, solo ante 503, timeout o error de conexión, sin reintento con el circuito abierto (BR-U7-15; P-U7-02);
  - el payload de la `recommendation` copia de la `ScoringRequest` `received_at`, `policy_inputs.channel` (como `channel`), `attempt` y `first_evaluation`, sin recalcularlos;
  - un 409 de idempotencia → `registry_unavailable` + log `LogEvent.REGISTRY_IDEMPOTENCY_CONFLICT`;
  - `fail_closed` best effort de 250 ms, con **otro** UUID v4 de la misma solicitud y solo `cause`: nunca `local_cause` ni `escalated_at` (BR-U7-16, BR-U0-38). El registro real rechaza ese payload con 422, no con el 403 que dice BR-U7-16 (candidata de U03-T03 en `CANDIDATAS.md`); el doble del registro hace lo mismo que U3.
- Métricas: `vectra_scoring_failclosed_total{cause}` (BR-U7-03, la que lee `PromotionMismatchPersistent` de U4), `vectra_recommendations_total{outcome}`, `vectra_registry_append_attempts_total`, `vectra_registry_append_abandoned_total` y `vectra_deadline_exhausted_total`.
- **PBT-U7-08** usa los pares RT-1 de U5 (`vectra_reference.adversarial.rt1_cases`) convertidos a `FeatureVector` con `vectra_contracts.labels.derive` y el `feature_spec` del paquete de U5, sin copias. El caso RT-3 de versión distinta usa los paquetes de `rt3_cases` o un doble que devuelve otra versión.
- Diseño: BR-U7-01, 02, 03, 12, 15, 16; P-U7-01, 02, 03; NFR-U7-04, 12, 13. Historias: US-103, US-109, US-111, US-113.

### Paso 12 — Endpoints, arranque y apagado (E)

- `create_app` de U0 en los dos servicios, con los handlers de `REGISTRY`: `POST /v1/recommendations` (F15) y `POST /v1/explanations` (F20). `POST /v1/applicant-summaries` (F12). Scopes y audiencias de U2.
- Readiness y liveness solo del proceso (8081).
- Arranque con `vectra_common.ops_server.run_service(app)`, que ya fija la espera de ≤ 10 s en el apagado (`GRACEFUL_SHUTDOWN`).
- Diseño: BR-U7-13; INF-U7-01, 03; NFR-U7-21, 30, 31; P-U7-07. Historias: US-103, US-110.

### Paso 13 — Resumen de los servicios (E)

- Cobertura de ramas ≥ 95 % en los dos servicios y **100 %** en `orchestrator` (NFR-U7-40).
- Resumen en `aidlc-docs/construction/scoring-explainability/code/services.md`, con lo diferido (`mutmut`, T3).
- Diseño: NFR-U7-40, 42.

### Plan

Marca `[x]` los Pasos 8 a 13 con `(U07-T03)`.

**Fuera** (rechazar aunque se vea roto o tentador):

- El Paso 6 (`applicant`): es de U07-T02.
- Cambios en U0.
- Chart, Dockerfiles, Application, k6 y trazabilidad (U07-T04).
- `mutmut` (T3).
- Cualquier orden contra el clúster (AUTONOMIA-01).
- Cambios en U3, U4, U5 o U6. Si un contrato de ellos no basta para escribir el doble (por ejemplo, el host del explicador o un campo de `serving-config`), **detente y repórtalo**.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`: §1, Pasos 8 a 13, §3 y §4.
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1.0, §1.1, §1.2 (cadenas de D1 y D2), §2, §3 U7, §5.1, §5.2 y §6 (P-1, decidida el 2026-11-10: opción (a); P-2).
- `aidlc-docs/construction/plans/governance-bloque-d-precisiones.md` §5 (P-1 para U4, Q-6, con la misma opción).
- `aidlc-docs/construction/scoring-explainability/`: `functional-design/` (BR-U7-01 a 16; `domain-entities.md` §4, §5 y §6; PBT-U7-07, 08), `nfr-requirements/` (NFR-U7-02, 03, 04, 10 a 13, 21, 30, 31, 40, 42, 43), `nfr-design/` (P-U7-01 a 05, 07, 08; `logical-components.md`) e `infrastructure-design/` (INF-U7-01, 03, 04).
- `contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py` (`_scoring`, `_explainability`, `REGISTRY`), `catalog.py` (`ProblemCode`, `ProblemReason`, `LogEvent`), `models/api.py` (`ScoringRequest`, `ExplainRequest`, `ApplicantSummaryRequest`, `ApplicantSummary`), `models/registry.py` (`EntryFilter`, `ExplanationProjection`), `outcome/__init__.py` (`check_preconditions`, `build_outcome`) y `labels.py` (`derive`).
- `contracts/python/vectra_common/src/vectra_common/`: `app_factory.py`, `deps.py`, `deadline.py`, `service_token.py` y `ops_server.py`.
- `model-serving/predictor/src/vectra_predictor/app.py`, `model-serving/explainer/src/vectra_explainer/app.py` y `model-serving/docs/values.md` (forma v1 y nombre `isvc-<8 hex>`).
- `governance/src/vectra_governance/api.py` (`serving-config` con `etag`, `feature-dictionary`) y `decision-registry/src/vectra_registry/` (`append.py`: idempotencia, 409 y 422; `projections.py` y `queries.py`: proyección `explanation` por `seq`).
- `reference-model/src/vectra_reference/adversarial.py` (`rt1_cases`, `rt3_cases`, `rt4_cases`) y `model-serving/tests/conftest.py`.
- `CANDIDATAS.md`: la forma de `:predict` y `:explain` (U06-T01) y `fail_closed` con `local_cause` → 422 (U03-T03).

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster. Todos los dobles HTTP viven en `scoring-explainability/tests/doubles/` y siguen los contratos de `vectra_contracts`.

- [ ] **CA-1** — Paso 8: aceptación del plan.
  ```bash
  uv run pytest scoring-explainability/tests/integration/test_explanations.py -v
  ```
  Esperado: código 0. Con dobles de KServe y de governance, pasan como mínimo:
  - caché fría con diccionario y `:explain` a 400 ms cada uno → ~400 ms, no ~800 ms;
  - cabecera en el pasado → 504 inmediato;
  - cabecera a 1 h en el futuro o mal formada → corte a los 700 ms;
  - explicador de otra versión (RT-3) → 409 `version_mismatch`;
  - diccionario incompleto → 422 `feature_dictionary_incomplete`;
  - generador alterado en la prueba → 422 `factuality_failed`;
  - 5 versiones → se descarta la menos usada;
  - conexión rechazada hacia `:explain` → 503 o 504, nunca 500 (R-3).

- [ ] **CA-2** — Paso 9: aceptación del plan.
  ```bash
  uv run pytest scoring-explainability/tests/integration/test_applicant_summaries.py -v
  ```
  Esperado: código 0. Con un doble del registro que sigue la proyección `explanation` de U3, pasan como mínimo:
  - caso sin explicación → 409;
  - caso de abuso: `recommendation_entry_id` de otro caso → 409, sin datos parciales;
  - el log `applicant_summary.generated` lleva `case_id` y no contiene texto del resumen;
  - un resumen válido trae como máximo 3 factores `applicant_safe` y la leyenda.

- [ ] **CA-3** — Paso 10: aceptación del plan.
  ```bash
  uv run pytest scoring-explainability/tests/integration/test_clients.py -v
  ```
  Esperado: código 0. Pasan:
  - KServe colgado agota sus 20 conexiones y una explicación en paralelo responde en su tiempo normal;
  - tras congelar en el doble de governance → `FailClosed(model_frozen)` en ≤ 6 s;
  - caché vencida + governance caído → `serving_config_unavailable`;
  - con explainability caído, tras 20 llamadas → `FailClosed` en < 50 ms.

- [ ] **CA-4** — Paso 11: aceptación del plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_orchestrator.py scoring-explainability/tests/integration/test_orchestrator.py -v
  ```
  Esperado: código 0, con la semilla impresa. Pasan PBT-U7-07, PBT-U7-08, la propiedad de P-U7-01 (sin invocar el registro para una `recommendation`, responde antes de 1 s) y **todos** los ejemplos del Paso 11 del plan, sin excepción: versiones M y P (US-103); RT-3 → `version_mismatch` y la métrica sube (US-111); versión pedida distinta → `version_mismatch` sin llamadas; congelado y versión distinta → `model_frozen` sin llamadas; dos solicitudes con el mismo `attempt` → llaves distintas; `fail_closed` con `cause` y sin `local_cause` ni `escalated_at`; `received_at`, `channel`, `attempt` y `first_evaluation` copiados (también con `first_evaluation = false` y `attempt = 2`) y ausentes en `fail_closed`; registro sin réplica → `registry_unavailable` (US-113); registro que falla una vez → dos llamadas con la misma llave y una entrada; registro que confirma a los 2,6 s → `FailClosed`, la entrada existe y `abandoned` = 1; un 4xx → un solo intento.

- [ ] **CA-5** — Paso 12: aceptación del plan.
  ```bash
  uv run pytest scoring-explainability/tests/integration/test_app.py scoring-explainability/tests/integration/test_shutdown.py -v
  ```
  Esperado: código 0. Pasan:
  - con governance caído, explainability queda listo y la primera explicación pide el diccionario;
  - `SIGTERM` a los 0,5 s de una solicitud cuyo registro responde a los 3 s → `Recommendation` con `registry_entry_id`;
  - las etiquetas de las métricas están dentro de la allowlist de P-U7-07 (`outcome`, `cause`, `reason`, `dependency`, `result`, `attempt`, `stage`);
  - una ruta sin scope → 403;
  - `create_app` de los dos servicios arranca con los handlers de las tres rutas de `REGISTRY`;
  - `/v1/applicant-summaries` con un rol distinto de `analista` o `cro` → 403.

- [ ] **CA-6** — Paso 13: cobertura.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests --cov=scoring --cov=explainability --cov-branch --cov-fail-under=95 \
    && uv run coverage report --include="*/scoring/orchestrator.py" --fail-under=100
  test -s aidlc-docs/construction/scoring-explainability/code/services.md
  ```
  Esperado: código 0. El `--cov` sin argumento del plan mide el `source` de la raíz (U0), por eso el comando nombra los paquetes. Los dos comandos quedan en el `check` de `scoring-explainability/Makefile`.

- [ ] **CA-7** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C scoring-explainability check && make -C platform check
  ```
  Esperado: código 0 en los dos.

- [ ] **CA-8** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso (8|9|1[0-3]) "
  ```
  Esperado: Pasos 8 a 13 en `[x] (U07-T03)`. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U07-T03.md`:
- diccionario y `:explain` en serie → la prueba de ~400 ms falla;
- explainability que acepta una cabecera a 1 h → la prueba del corte a 700 ms falla;
- conexión rechazada mapeada a 500 → la prueba de R-3 falla;
- `idempotency_key` derivada de `case_id` y `attempt` → el ejemplo de las llaves distintas falla;
- reintento del append ante un 4xx → «un solo intento» falla;
- `local_cause` en la entrada `fail_closed` → su ejemplo falla;
- `version_mismatch` evaluado antes que `congelado` → PBT-U7-07 falla;
- una `Recommendation` sin `registry_entry_id` cuando el registro tarda → PBT-U7-07 falla;
- `free_text` en el vector → PBT-U7-08 falla;
- un pool compartido entre `:predict` y explainability → la prueba del bulkhead falla;
- el resumen sin comprobar que la entrada es del `case_id` → el caso de abuso falla;
- el texto del resumen en el log `applicant_summary.generated` → su prueba falla;
- `case_id` como etiqueta de una métrica → la prueba de la allowlist falla;
- una rama de `orchestrator.py` sin prueba → el umbral del 100 % falla.

---

## Notas

- **Detención con reporte:** si U0, U3, U4 o U6 no exponen algo que esta tarea necesita (un campo de `serving-config`, el `etag`, el host del explicador o la forma de un error), detente y repórtalo. No inventes campos en los dobles.
- Archivos que se modifican en su sitio: `scoring-explainability/` (módulos de los dos servicios, `tests/`, `Makefile`), el plan y `CANDIDATAS.md`. Archivo nuevo: `aidlc-docs/construction/scoring-explainability/code/services.md`.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- **Bitácora:** `bitacoras/U07-T03.md`, con la cobertura de partida y la final, la semilla de cada PBT, la plantilla de URL del explicador y los pares falla-pasa.
