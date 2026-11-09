# U04-T04 — Endpoints y resumen del servicio de `governance`

**Unidad:** U4 `governance`
**Historias que implementa:** US-201, US-202, US-203, US-205, US-206, US-208 y US-305, en su parte HTTP. US-306 solo en sus rutas (Q-6).
**Depende de:** U04-T03 (PR #95). Usa las operaciones de `evidence.py`, `background.py` y `convergence.py`.
**Rama:** `tarea/U04-T04`, creada desde `tarea/U04-T03` (`453719f`), porque el PR #95 todavía no está fusionado. Si se fusiona durante la tarea, integra `origin/main`.
**Precisiones:** `aidlc-docs/construction/plans/governance-bloque-d-precisiones.md`, aprobada el 2026-11-09. Q-5 dice que esta tarea son los Pasos 10 y 11. Q-6 resuelve P-1 para US-306 con la opción **(a)**: implementar las rutas.

Segunda mitad del Bloque D del plan de U4. Alcance de la enmienda (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §3, U4), con Q-6:
- **Paso 10 E\*F:**
  - Entran los modelos (registrar, validar, informe, aprobar, `activation`, lista y detalle), `freeze`, `frozen-resolution`, `feature-dictionary`, `feature-spec`, `serving-config`, las 3 rutas de políticas y `retirement` (P-8).
  - Por Q-6 entran también **las rutas de US-306**: `GET`/`POST /v1/data-sources`, `…/comparisons`, `…/decision` y `PUT /v1/validation-runs/{run_id}/source-counts`.
  - Siguen diferidos el modo `source_comparison` del `model-validation-job` (Paso 13), la rama `source_comparison` del barrido y el invariante de `source_candidate_for` en PBT-U4-01 (P-5).
- **Paso 11 E.**

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige la regla «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).

## Alcance

**Dentro:** los Pasos 10 y 11 del plan (`aidlc-docs/construction/plans/governance-code-generation-plan.md`, Bloque D), con su texto y su aceptación, salvo lo que se difiere y se nombra abajo. Léelos allí. Precisiones:

- **Las 21 rutas de `governance-service`** del registro de U0 (`vectra_contracts.routes.REGISTRY["governance-service"]`) tienen handler, y `create_app` arranca con todas. Cada handler llama a las operaciones de U04-T03, no repite su lógica. Los scopes de cada ruta salen del `RouteContract`. Los roles, del FD (BR-U4-01, 02, 10, 13, 18 y 19) y de `contracts/openapi/role-endpoint-matrix.md`.
- **Errores.** Los `Forbidden` y `ConflictState` de `model_fsm`/`policy` y el `transition_pending` de U04-T03 se traducen a `vectra_common.errors` y al catálogo `ProblemReason` de U0. Si falta un `reason` en U0, **detente y repórtalo**: no cambies U0.
- **Autenticación y step-up.** Usa lo que ofrece `vectra_common` (mira cómo lo hace `decision-registry/src/vectra_registry/service.py`). `frozen-resolution` exige `cumplimiento`, MFA y step-up, y fija `SET LOCAL vectra.frozen_resolution` (BR-U4-03). Los tokens de prueba se firman con una llave de prueba, como en U3.
- **Registro (BR-U4-06).** Las pruebas usan los **paquetes reales de U5** (`reference-model/`, incluidos los RT-3): (a), (c) y (d) → 422 sin crear la versión; (b) → aceptado. Ya no hace falta el doble de paquetes.
- **`freeze` (BR-U4-15).** Agrega `data_sources` e `initial_disparity` al `FreezeContext` antes de escribir el evento, con la reducción por tamaño: más de 60 KiB → `initial_disparity` solo con sus agregadas; más de 64 KiB → `data_sources` solo con ids; el registro nunca recibe más de 64 KiB. Con un token de `bias-monitoring-service` → 403; con `bias-monitoring-job` → 204.
- **Lanzador de Jobs (K01).** `POST /v1/models/{id}/validations` crea el Job en `vectra-staging` con TTL, `activeDeadlineSeconds` y `backoffLimit: 0`, por el cliente de Kubernetes de `k8s_jobs.py`. `mode` es un parámetro, y `source_comparison` solo se lanza desde `…/comparisons`. Las pruebas usan un doble de la API de Kubernetes que registra el manifiesto, y lo leen de vuelta. No hace falta un clúster.
- **F25 (`compare_source`)** hacia U9 `POST /v1/source-comparisons`: cliente real con `httpx` y timeouts, más un doble en las pruebas. U9 no existe todavía en main.
- **Líneas de aceptación del Paso 10 que entran:** todas, salvo la última, «`source_comparison` vencido (reloj simulado) → `ValidationRun` `timeout`», que es la rama diferida del barrido. Las de US-306 entran por Q-6 (`start_source_comparison` con sus 409/403, `source-counts`, candidata con `source_candidate_for`, `pre_post_report` ≤ 48 KiB con `truncated`).
- **Contrato.** `make -C contracts openapi && git diff --exit-code contracts/openapi/` no debe mostrar cambios: esta tarea no toca U0.
- **Paso 11.** `aidlc-docs/construction/governance/code/api-summary.md`.
- **Plan.** Marca `[x]` los Pasos 10 y 11 con `(U04-T04, acotado a la demo)` en el 10 y `(U04-T04)` en el 11.

**Fuera:**

- `promotion-tool` (Paso 12) y `model-validation-job` (Paso 13), incluido su modo `source_comparison`.
- La rama `source_comparison` del barrido y su línea de aceptación. El invariante de `source_candidate_for` en PBT-U4-01 (P-5).
- Chart, RBAC, alertas, runbooks y `slo.md` (Pasos 16 y 17).
- Cambios a U0, U1, U3, U5 o U9. Si algo falta allí, detente y repórtalo.
- Las candidatas de U04-T03 en `CANDIDATAS.md` (promtool en el CI, literales de `evidence.py`, `ruff format`).

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md` (§1 y Pasos 10–11)
- `aidlc-docs/construction/plans/governance-bloque-d-precisiones.md` (Q-5 y Q-6)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U4 y §6: P-1, P-5, P-8, P-9)
- `aidlc-docs/construction/governance/functional-design/` (business-rules.md BR-U4-01..08, 10..13, 15..19; business-logic-model.md §3; domain-entities.md)
- `aidlc-docs/construction/governance/nfr-requirements/nfr-requirements.md` (NFR-U4-11 y 25) y `nfr-design/nfr-design-patterns.md` (P-U4-03 y 06)
- `contracts/openapi/role-endpoint-matrix.md`, `contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`, `catalog.py` y `models/`
- `contracts/python/vectra_common/src/vectra_common/` (`app_factory.py`, `errors.py`, autenticación)
- `governance/src/vectra_governance/` (U04-T02 y U04-T03) y `governance/tests/` (dobles del registro y Testcontainers)
- `decision-registry/src/vectra_registry/service.py` y `decision-registry/tests/service_harness.py` (ejemplo de servicio con `create_app` y tokens de prueba)
- `reference-model/` (paquetes de U5, incluidos los RT-3)
- `bitacoras/U04-T03.md` (decisiones de la capa de servicio síncrona)

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1** — `create_app` arranca con las 21 rutas.
  ```bash
  uv run pytest governance/tests/integration/test_api_app.py -v
  ```
  Esperado: pasa una prueba que construye la app de governance con `create_app` y compara sus rutas con `REGISTRY["governance-service"]`, sin que falte ni sobre ninguna. Otra prueba confirma que cada ruta con scopes en su `RouteContract` responde 403 a un token sin ese scope.

- [ ] **CA-2** — Aceptación del Paso 10 (salvo la línea diferida).
  ```bash
  uv run pytest governance/tests/integration/test_api_*.py -v
  ```
  Esperado: pasan todas, con un caso por cada viñeta de la aceptación del Paso 10 excepto «`source_comparison` vencido». La lectura de vuelta es con SQL sobre `model_versions`, `transitions`, `policies` y `data_sources`, y sobre la cadena del doble del registro; no basta el código HTTP. Además:
  - registro con los paquetes reales de U5: RT-3 (a), (c) y (d) → 422 y ninguna fila nueva; (b) → 201;
  - `feature-spec`: otra identidad → 403, y el cuerpo es byte a byte el `feature_spec.json` verificado;
  - `serving-config` con `If-None-Match` vigente → 304;
  - el manifiesto del Job de validación, leído del doble de Kubernetes, está en `vectra-staging` con TTL, `activeDeadlineSeconds` y `backoffLimit: 0`.

- [ ] **CA-3** — El contrato no cambia.
  ```bash
  make -C contracts openapi && git diff --exit-code contracts/openapi/
  ```
  Esperado: código 0, sin diff.

- [ ] **CA-4** — Paso 11: resumen y trazabilidad de la API.
  ```bash
  test -s aidlc-docs/construction/governance/code/api-summary.md && uv run python platform/tests/test_traceability.py --unit governance --section api
  ```
  Esperado: código 0. BR-U4-03, 05, 07, 08, 12, 13 y 15..17 aparecen en las pruebas.

- [ ] **CA-5** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C governance check
  make -C platform check
  ```
  Esperado: código 0 en los dos. Si `make -C platform check` falla en `check-tools` porque `platform/.tools` no existe en el worktree, regístralo y corre `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib`. Si `governance check` omite `promtool`, corre aparte `promtool test rules governance/observability/tests/*.yaml` con el `promtool` del checkout principal, después de comparar su versión con `tools.env`.

## Plan de pruebas

- `governance/tests/integration/test_api_app.py`: las rutas de `create_app` frente al registro de U0, y los 403 por scope.
- `governance/tests/integration/test_api_models.py`, `test_api_policies.py`, `test_api_freeze.py` y `test_api_data_sources.py` (o el reparto que prefieras, siempre con el prefijo `test_api_`): las viñetas del Paso 10.
- **Rojo primero**, registrado en `bitacoras/U04-T04.md`:
  - la prueba de rutas falla con `api.py` vacío;
  - con el chequeo de cuatro ojos quitado del handler, «el mismo CRO propone y aprueba → 409» falla;
  - sin la reducción por tamaño, el doble del registro recibe más de 64 KiB.

## Notas

- Archivos que se modifican en su sitio:
  - `governance/src/vectra_governance/{api,k8s_jobs,evidence}.py`, y los demás módulos solo para exponer lo que los handlers necesiten;
  - el plan (casillas).

  Nada de duplicados con sufijo.
- La capa de servicio es síncrona (decisión de U04-T03): los handlers pueden ser `def` y correr en un hilo.
- Docker está disponible para Testcontainers.
