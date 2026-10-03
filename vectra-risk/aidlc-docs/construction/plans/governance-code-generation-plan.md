# Plan de tareas (Code Generation Part 1) — U4 `governance`

**Este plan es la única fuente de verdad para generar el código de U4.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U4. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U4 `governance`: modelos, políticas, fuentes de datos y `serving-config` |
| Historias (dueña) | US-201, US-202, US-203, US-204, US-205, US-206, US-208, US-305 |
| Ubicación | `vectra-risk/governance/` (servicio, `promotion-tool`, `model-validation-job`) y Applications en `vectra-risk-gitops` |
| Datos propios | `governance-db` (esquema, triggers, roles) y el bucket `vectra-model-archive` |
| Depende de | U0 (tipos y `create_app`), U1 (plataforma, K01, model-store), U2 (roles, MFA, step-up, cliente `promotion-tool`), U3 (append con idempotencia), U9 (librería de disparidad y `compare_source`; se usa un doble hasta que exista), U5/U6 (modelo de referencia y KServe de staging para la validación real) |
| Lo consumen | scoring (`serving-config`), BFF (consola), bias (`freeze`), U12 (verificación) |

**Diseño de entrada:**
- Functional Design: `construction/governance/functional-design/` (BR-U4-01..17, PBT-U4-01..07).
- NFR Requirements: `construction/governance/nfr-requirements/` (NFR-U4-01..41).
- NFR Design: `construction/governance/nfr-design/` (P-U4-01..08).
- Infrastructure Design: `construction/governance/infrastructure-design/` (INF-U4-01..04).

**AUTONOMIA-01:** las verificaciones estáticas y las de integración con Testcontainers
corren en CI; las que necesitan el clúster las ejecuta **un operador en kind** después de
un PR aprobado (Paso 20), con la evidencia adjunta al PR.

### Estructura de destino

```text
vectra-risk/governance/
|-- Makefile  pyproject.toml
|-- src/vectra_governance/
|   |-- model_fsm.py  policy.py  serving_config.py  registration.py   # puros
|   |-- evidence.py  background.py  convergence.py  pools.py  api.py  k8s_jobs.py
|-- migrations/                  # Alembic: tablas, índice parcial, triggers, roles, NOTIFY
|-- promotion_tool/              # CLI: PKCE loopback, gh, gitsign
|-- validation_job/              # AUC, disparidad, sincronía, informe
|-- archive_job/                 # model-archive
|-- ci/                          # no-unfreeze-paths, promotion-pr-check, branch-protection, sbom-check
|-- chart/  observability/  runbooks/  docs/
`-- tests/  unit/ property/ integration/ examples/ load/
```

---

## 2. Pasos

### Bloque A — Estructura

- [ ] **Paso 1 — Esqueleto de `governance/`**
  - Directorios de §1; `pyproject.toml` (miembro del workspace) con extras separados: el servicio **sin** librerías de inferencia y `validation_job` con ONNX Runtime, `xgboost` y `lightgbm`.
  - Contrato de import-linter: `model_fsm`, `policy`, `serving_config` y `registration` sin E/S; ningún módulo del servicio importa librerías de inferencia.
  - Diseño: NFR-U4-24.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config governance/.importlinter && make -C governance check` sobre el esqueleto.

### Bloque B — Datos

- [ ] **Paso 2 — Migraciones de `governance-db`**
  - Tablas de domain-entities §1–§5 (incluidos `archived_uri` y `archived_at`); índice único parcial «una sola versión `activo` o `congelado`»; una sola política `activa`.
  - Triggers `guard_unfreeze` y `guard_freeze` (P-U4-06).
  - `NOTIFY serving_config` al confirmar.
  - Roles `gov_app`, `gov_migrator` y `gov_archiver` (permiso por columna); sin `DELETE` en tablas de historia.
  - Diseño: BR-U4-02, 03; NFR-U4-30; P-U4-01, 06; INF-U4-03. Historia: US-305.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_migrations.py` (Testcontainers):
    - un `UPDATE` directo `congelado → activo` → excepción; con la variable fijada pero sin transición de cumplimiento → excepción;
    - dos versiones `activo` → violación del índice;
    - `gov_archiver` no puede cambiar `state`;
    - ningún rol tiene `DELETE` sobre `model_versions`, `policies` ni `model_transitions`.

### Bloque C — Lógica pura

- [ ] **Paso 3 — `model_fsm`**
  - Función pura con la tabla de BR-U4-01; errores `Forbidden`/`ConflictState`.
  - Propiedad PBT-U4-02 (oráculo sobre el producto completo de estados × acciones × actores).
  - Diseño: BR-U4-01, 02, 04, 10. Historias: US-203, US-305.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_model_fsm.py`.

- [ ] **Paso 4 — `policy`**
  - Validación de la lista normativa (BR-U0-33); `normative_at(policy, fecha)` con fechas en **`America/Bogota`**; cuatro ojos; activación (la anterior pasa a `historica`).
  - Propiedades PBT-U4-03 (incluidos los bordes de la medianoche de Bogotá) y PBT-U4-04.
  - Diseño: BR-U4-10, 11; P-U4-05. Historias: US-205, US-206.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_policy.py`, y la prueba con reloj simulado: el cambio de vigencia ocurre a las 00:00 de Bogotá y no a las 19:00 de Bogotá.

- [ ] **Paso 5 — `serving_config`**
  - Composición de domain-entities §5 (incluido `inference_service`) y `etag` (JCS sin `bias_monitoring_age_s`); prueba de ejemplo: cambiar solo `inference_service` cambia el `etag`.
  - Propiedad PBT-U4-05.
  - Diseño: BR-U4-11, 14; P-U4-07.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_serving_config.py`.

- [ ] **Paso 6 — `registration`**
  - Formato permitido, rechazo de `pickle`/`joblib` por extensión y bytes mágicos, SHA-256 sobre los bytes de cada archivo del `manifest.json` (U5) y mismo `model_version_id` en todos; nunca deserializa.
  - Propiedad PBT-U4-06.
  - Diseño: BR-U4-06. Historia: US-201.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_registration.py`, más una prueba que hace fallar a cualquier deserializador si se lo invoca (*monkeypatch* de `pickle.loads`, `joblib.load` y `onnx.load`).

- [ ] **Paso 7 — Resumen de la lógica pura**
  - `aidlc-docs/construction/governance/code/business-logic-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit governance --section logic` (BR-U4-01, 02, 04, 06, 10, 11 y 14 aparecen en las pruebas).

### Bloque D — Servicio

- [ ] **Paso 8 — Evidencia en dos fases, reconciliador y barridos**
  - Transición `pendiente_registro` → append con `idempotency_key = transition_id` → `confirmada` + efecto (BR-U4-17); excepción de `freeze` (BR-U4-15).
  - Tarea de fondo con `SKIP LOCKED`: reintentos, `abandonada` a las 24 h, `FreezeEventPending` y barrido de validaciones vencidas (P-U4-02).
  - Propiedades stateful **PBT-U4-01** (máquina completa con actores y MFA, contra el servicio y Testcontainers) y **PBT-U4-07** (registro con fallos al azar).
  - Diseño: BR-U4-05, 15, 17; NFR-U4-40; P-U4-02.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_stateful_*.py governance/tests/integration/test_evidence.py`, con 2 réplicas y un doble del registro que falla al azar: ninguna transición distinta de `freeze` cambia el estado sin ack; ningún evento se duplica.

- [ ] **Paso 9 — `serving-config` en memoria, convergencia y pools**
  - Copia en memoria; `LISTEN serving_config` + sondeo del `etag` cada 1 s; temporizador de medianoche de Bogotá; readiness solo con la copia cargada.
  - `If-None-Match`/304.
  - Pools `tx` 2, `read` 1, `background` 1 y `listen` 1.
  - Diseño: NFR-U4-04, 05, 06, 10; P-U4-01, 04, 05.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_convergence.py test_pools.py` (Testcontainers con 2 réplicas):
    - `freeze` en A → B sirve el `etag` nuevo en ≤ 1 s, también con la conexión `LISTEN` de B cortada;
    - con la base pausada, `serving-config` sigue respondiendo;
    - `pg_stat_activity` cuenta 5 conexiones por réplica.

- [ ] **Paso 10 — Endpoints**
  - Modelos: registrar, lanzar validación (Job en `vectra-staging` por K01, con TTL, `activeDeadlineSeconds` y `backoffLimit: 0`), recibir el informe (F32), aprobar o rechazar, `mark_active`, retirar.
  - `freeze` (solo `governance:freeze`).
  - `GET /v1/models/{id}/feature-dictionary` (solo `governance:read-dictionary`; BR-U4-18, agregado por U7 FD Q4).
  - `GET /v1/models/{id}/feature-spec` (solo `governance:read-feature-spec`; BR-U4-19, agregado por U8 FD Q1). Prueba: otra identidad → 403; el contenido es byte a byte el `feature_spec.json` verificado.
  - `frozen-resolution`: solo `cumplimiento` + MFA + step-up; fija `SET LOCAL vectra.frozen_resolution`.
  - Políticas (cuatro ojos); fuentes (con `compare_source` F27; doble de U9 hasta que exista).
  - Todas las rutas como `RouteContract` en el registro de contratos de U0.
  - Diseño: BR-U4-01..05, 07, 08, 10..13, 16, 18, 19; NFR-U4-11, 25; P-U4-03, 06. Historias: US-201, US-202, US-203, US-205, US-206, US-208, US-305.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_api_*.py` con las pruebas de ejemplo de business-logic-model §3:
    - `cro` aprueba → 200; `ingeniero_riesgo` → 403;
    - un CRO, un job o un webhook intentan reactivar → denegado;
    - el mismo CRO propone y aprueba → 409;
    - una vigencia normativa vencida da `normative_current` nulo.
    
    Además, `make -C contracts openapi && git diff --exit-code contracts/openapi/`.

- [ ] **Paso 11 — Resumen del servicio**
  - `aidlc-docs/construction/governance/code/api-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit governance --section api` (BR-U4-03, 05, 07, 08, 12, 13 y 15..17 aparecen en las pruebas).

### Bloque E — Herramientas y Jobs

- [ ] **Paso 12 — `promotion-tool`**
  - `list_promotable`, `create_promotion_pr` (un solo commit que **agrega** el `InferenceService` `isvc-<8 hex>` de la versión, con predictor y explicador del mismo `model_version_id`, más la evidencia `helm template` y `kubectl diff` contra kind), `post_activation_pr` (baja la versión anterior a 1 réplica por componente), `rollback_pr` (restaura los mínimos de producción de la versión `inactivo` antes de su `mark_active`), `retire_inference_service` (PR que retira el de una versión `inactivo` > 7 días) y `mark_active` (que también fija `inference_service` en `serving-config`).
  - Login PKCE con loopback (token solo en memoria), `gh` con la sesión del ingeniero y commit firmado. Nunca sincroniza ni aplica.
  - Diseño: BR-U4-08, 09; NFR-U4-20, 21. Historias: US-204, US-208.
  - **Aceptación**: `uv run pytest governance/tests/unit/test_promotion_tool.py`:
    - con un repositorio git de fixture, el PR generado tiene un solo commit firmado y los dos manifiestos con el mismo `model_version_id`;
    - ningún archivo de configuración guarda tokens;
    - `! grep -rE "argocd app sync|kubectl apply|helm (install|upgrade)" governance/promotion_tool/`.

- [ ] **Paso 13 — `model-validation-job`**
  - AUC-ROC (con `auc_target` y `auc_meets_target`), disparidad inicial con la librería de U9 (doble mientras no exista), prueba de sincronía predictor ↔ explicador, informe con el `disclaimer` y envío por F32.
  - Imagen con las librerías de inferencia, `runAsNonRoot`, `readOnlyRootFilesystem`, sin token de Kubernetes.
  - Diseño: BR-U4-07; NFR-U4-12, 23; P-U4-03. Historia: US-202.
  - **Aceptación**: `uv run pytest governance/tests/unit/test_validation_job.py`:
    - con un modelo ONNX de fixture y un explicador que no produce vectores → `sync_check.passed = false`;
    - las plantillas del informe no contienen «sin sesgo», «libre de discriminación» ni equivalentes (FR-BIA-08).

- [ ] **Paso 14 — Scripts de CI**
  - `no-unfreeze-paths`: falla si hay escrituras `congelado → activo` fuera del handler de cumplimiento.
  - `promotion-pr-check` en el repositorio GitOps: un commit, mismo `model_version_id` y evidencia adjunta.
  - `branch-protection-check`: verifica la protección de `main` en `vectra-risk-gitops` con `gh api`.
  - `sbom-check`: la imagen del servicio no contiene ONNX Runtime, `xgboost` ni `lightgbm`.
  - Diseño: BR-U4-03, 09; NFR-U4-21, 22, 24. Historias: US-204, US-305.
  - **Aceptación**: `uv run pytest governance/tests/unit/test_ci_scripts.py` (cada script falla con un fixture que lo viola y pasa con uno correcto).

- [ ] **Paso 15 — `model-archive`**
  - CronJob diario: lee del model-store (F101), sube a `vectra-model-archive` (F100) con object lock `COMPLIANCE`, cifrado del lado del servidor y TLS, descarga y verifica el SHA-256, y solo entonces registra `archived_uri` (F102, `gov_archiver`).
  - Diseño: NFR-U4-31; INF-U4-02, 03.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_model_archive.py`, con Testcontainers (PostgreSQL y MinIO con object lock):
    - una versión activada queda archivada y con `archived_uri`;
    - un SHA-256 distinto → no registra y emite la métrica de fallo;
    - borrar el objeto archivado → rechazado por el lock.

### Bloque F — Despliegue y operación

- [ ] **Paso 16 — Chart, flujos y RBAC**
  - Deployment: HPA de 2 a 6, spread, PDB, `vectra-high`, recursos de INF-U4-01, `tzdata`.
  - CronJob `model-archive` (sidecar nativo de Linkerd, `Forbid`); Job de migración como hook.
  - RBAC K01; values del bucket por entorno.
  - Agregar F100, F101 y F102 a `platform/network/flows.yaml` de U1.
  - Diseño: NFR-U4-03, 25; INF-U4-01..04.
  - **Aceptación**: `helm template` + `conftest test governance/chart/`; `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests` (F100–F102 presentes).

- [ ] **Paso 17 — Alertas, runbooks y documentación**
  - `PrometheusRule` con las alertas de P-U4-08 (incluidas `ServingConfigConvergenceSlow` y `ModelArchivePending`) y sus runbooks.
  - `docs/slo.md` (governance dentro del SLO, NFR-U4-01).
  - Diseño: NFR-U4-01, 07; P-U4-08; BR-U4-08, 11, 16.
  - **Aceptación**: `promtool test rules governance/observability/rules/tests/*.yaml`; `uv run python platform/tests/test_runbooks.py --root governance`; `test -s governance/docs/slo.md`.

- [ ] **Paso 18 — Application de GitOps**
  - Application en la wave 5 (migración como hook, servicio y CronJob).
  - Diseño: P-U1-12.
  - **Aceptación**: `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync`.

### Bloque G — Calidad

- [ ] **Paso 19 — Cobertura, mutación, trazabilidad y especificación de carga**
  - Cobertura de ramas ≥ 95 % y **100 %** en `model_fsm`, `policy` y `evidence`; `mutmut` en `model_fsm`; trazabilidad de cada BR-U4 a una prueba.
  - Script k6: `serving-config` con 6 clientes cada 5 s y transiciones con firma.
  - Diseño: NFR-U4-10, 11, 41.
  - **Aceptación**: `uv run pytest governance/tests --cov --cov-branch --cov-fail-under=95`, el umbral por módulo, `uv run mutmut run` sin sobrevivientes fuera de la allowlist, `uv run python platform/tests/test_traceability.py --unit governance --all` y `k6 inspect governance/tests/load/governance.js` (umbrales p95 de 20 ms y 500 ms).

### Bloque H — Verificación en kind (con aprobación humana)

- [ ] **Paso 20 — Puerta de aprobación, instalación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–19 aprobado por un humano, sobre U1–U3 instalados en kind.
  - El operador sincroniza la wave 5 y ejecuta, con evidencia:
    1. la prueba de carga k6;
    2. la validación con el modelo de referencia (cuando existan U5 y U6) → informe en ≤ 30 min;
    3. la promoción de punta a punta: aprobación → `promotion-tool` (PR de un commit) → revisión y merge → sync manual → `mark_active`;
    4. el rollback a la versión `inactivo` (US-208);
    5. `governance-db` pausada → `serving-config` sigue respondiendo;
    6. registro caído → transiciones pendientes sin efecto y `freeze` aplicado igual;
    7. la propagación del congelamiento en ≤ 6 s (completa cuando existan U7 y U9);
    8. la protección de rama verificada con `branch-protection-check`.
  - Historias: US-201, US-202, US-204, US-206, US-208.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con comando, salida y resultado esperado contra el obtenido. Los que dependen de U5, U6, U7 y U9 se marcan como pendientes hasta que esas unidades existan.

### Bloque I — Cierre

- [ ] **Paso 21 — Frontend: N/A**
  - Las pantallas de governance son de U10 (SPA) vía el BFF.
  - **Aceptación**: `test ! -d governance/frontend`.

- [ ] **Paso 22 — Cierre de la unidad**
  - **Aceptación**: `make -C governance check`, que corre en orden las verificaciones estáticas y de integración (Testcontainers) de los Pasos 2–19 y termina en 0. Las de kind (Paso 20) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

Verificada con un script contra las líneas «Diseño» e «Historia(s)» de cada paso antes de presentarla.

| Historia | Pasos |
|---|---|
| US-201 | 6, 10, 20 |
| US-202 | 10, 13, 20 |
| US-203 | 3, 10 |
| US-204 | 12, 14, 20 |
| US-205 | 4, 10 |
| US-206 | 4, 10, 20 |
| US-208 | 10, 12, 20 |
| US-305 | 2, 3, 10, 14 |

| Diseño | Pasos |
|---|---|
| BR-U4-01..19 | 2, 3, 4, 5, 6, 8, 10, 12, 13, 14, 17 |
| NFR-U4-01..41 | 1, 2, 8, 9, 10, 12, 13, 14, 15, 16, 17, 19 |
| P-U4-01..08 | 2, 4, 5, 8, 9, 10, 13, 17 |
| INF-U4-01..04 | 2, 15, 16 |

| Propiedad | Paso |
|---|---|
| PBT-U4-01, 07 (stateful) | 8 |
| PBT-U4-02 | 3 |
| PBT-U4-03, 04 | 4 |
| PBT-U4-05 | 5 |
| PBT-U4-06 | 6 |

## 4. Cumplimiento de extensiones (plan de tareas U4)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | `promotion-tool` nunca aplica ni sincroniza (Paso 12); escenarios con clúster por el operador (Paso 20) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-04 | Cumple | Triggers (Paso 2), `model_fsm` (Paso 3), endpoint (Paso 10) y script de CI (Paso 14) |
| AUTONOMIA-05 | Cumple | La API sin egress; F100 sin datos de solicitantes (Pasos 15, 16) |
| AUTONOMIA-06 | Cumple | Promoción incompleta → `version_mismatch` (Paso 20). `normative_current` nulo ya no es fail-closed (U7 FD Q1): lo prueba U7 |
| SECURITY-01/05/06/07/08/11/12/13/14/15 | Cumple | Pasos 2, 6, 10, 12..17 |
| RESILIENCY-05..12, 14, 15 | Cumple | Pasos 8, 9, 15, 16, 17, 20 |
| PBT-01..10 | Cumple | Pasos 3..6, 8 (dos stateful), 19 |
