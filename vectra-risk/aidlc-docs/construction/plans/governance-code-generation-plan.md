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
| Historias (participa) | US-306 (dueña U9): ciclo de la fuente, versión candidata y modo `source_comparison` (quinta revisión del FD de U9, 2026-10-10) |
| Ubicación | `vectra-risk/governance/` (servicio, `promotion-tool`, `model-validation-job`) y entradas en `vectra-risk-gitops/components.yaml`, dentro del monorepo (revisión de consistencia entre unidades, 2026-11-01) |
| Datos propios | `governance-db` (esquema, triggers, grants) y el bucket `vectra-model-archive` |
| Depende de | U0 (tipos y `create_app`), U1 (plataforma, K01, model-store), U2 (roles, MFA, step-up, cliente `promotion-tool`), U3 (append con idempotencia), U9 (librería de disparidad y `compare_source`; se usa un doble hasta que exista), U5/U6 (modelo de referencia y KServe de staging para la validación real) |
| Lo consumen | scoring y `case-worker` (`serving-config`), explainability (diccionario), case-service y `case-worker` (`feature_spec`), U6 (`inference_service`, `promotion-tool`), BFF (consola), bias (`freeze`), U12 (verificación) |

**Diseño de entrada:**
- Functional Design: `construction/governance/functional-design/` (BR-U4-01..19, PBT-U4-01..07).
- NFR Requirements: `construction/governance/nfr-requirements/` (NFR-U4-01..41).
- NFR Design: `construction/governance/nfr-design/` (P-U4-01..08).
- Infrastructure Design: `construction/governance/infrastructure-design/` (INF-U4-01..05; INF-U4-05 agregada por el FD de U9).

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
|-- migrations/                  # Alembic: tablas, índice parcial, triggers, grants, NOTIFY
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

- [x] **Paso 1 — Esqueleto de `governance/`** (U04-T01)
  - Directorios de §1; `pyproject.toml` (miembro del workspace) con extras separados: el servicio **sin** librerías de inferencia y `validation_job` con ONNX Runtime, `xgboost` y `lightgbm`.
  - `validation_job` depende además de `vectra_disparity` (librería de U9, ruta del workspace; doble mientras no exista) para la disparidad inicial y el modo `source_comparison` (tercera revisión del FD de U9, 2026-10-10).
  - Contrato de import-linter: `model_fsm`, `policy`, `serving_config` y `registration` sin E/S; ningún módulo del servicio importa librerías de inferencia.
  - Diseño: NFR-U4-24.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config governance/.importlinter && make -C governance check` sobre el esqueleto.

### Bloque B — Datos

- [x] **Paso 2 — Migraciones de `governance-db`** (U04-T01)
  - Tablas de domain-entities §1–§5 (incluidos `archived_uri` y `archived_at`); índice único parcial «una sola versión `activo` o `congelado`»; una sola política `activa`; tabla única `transitions` para modelo, política y fuente, con `entity_type` y `entity_id`, e índice único parcial `(entity_type, entity_id, transition_number) WHERE status <> 'abandonada'` (precisado el 2026-10-06, revisión del FD de U8); columnas `unit_id`, `kind` (`cambio_estado` \| `compensacion`) y estado `descartada` (precisado el 2026-10-06, revisión del FD de U8).
  - Triggers `guard_unfreeze` y `guard_freeze` (P-U4-06).
  - `validation_runs.mode` (`validacion` por omisión en las filas existentes), `source_id`, `baseline_version_id`; `model_versions.source_candidate_for`; `data_sources.pre_post_report` (segunda revisión del FD de U9, 2026-10-08).
  - `NOTIFY serving_config` al confirmar.
  - Grants de `gov_app`, `gov_migrator` y `gov_archiver` (permiso por columna); los roles los crea U1 (cuarta revisión de coherencia entre unidades, 2026-10-31); sin `DELETE` en tablas de historia.
  - Diseño: BR-U4-02, 03; NFR-U4-30; P-U4-01, 06; INF-U4-03. Historia: US-305.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_migrations.py` (Testcontainers):
    - una transición `descartada` con `n = 5` → otra inserción con `n = 5` en la misma entidad viola el índice (el `n` sigue reservado); una `abandonada` con `n = 5` → se puede insertar otra con `n = 5` (precisado el 2026-10-06, revisión del FD de U8);
    - un `UPDATE` directo `congelado → activo` → excepción; con la variable fijada pero sin transición de cumplimiento → excepción; con la variable apuntando a una `frozen_resolution` confirmada de **otra** versión, o a una fila de `transitions` de política o de fuente → excepción (precisado el 2026-10-06, revisión del FD de U8);
    - dos versiones `activo` → violación del índice;
    - la migración de `validation_runs` deja `mode = validacion` en las filas existentes; `mode = source_comparison` sin `source_id` → violación del `CHECK` (segunda revisión del FD de U9, 2026-10-08);
    - `gov_archiver` no puede cambiar `state`;
    - ningún rol tiene `DELETE` sobre `model_versions`, `policies`, `data_sources` ni `transitions`;
    - una transición de política y una de fuente con el mismo `entity_id` textual y el mismo `n` → llaves distintas; dos pendientes de la misma política con el mismo `n` → violación del índice.

### Bloque C — Lógica pura

- [x] **Paso 3 — `model_fsm`** (U04-T02)
  - Función pura con la tabla de BR-U4-01; errores `Forbidden`/`ConflictState`.
  - Propiedad PBT-U4-02 (oráculo sobre el producto completo de estados × acciones × actores).
  - Diseño: BR-U4-01, 02, 04, 10. Historias: US-203, US-305.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_model_fsm.py`.

- [x] **Paso 4 — `policy`** (U04-T02)
  - Validación de la lista normativa (BR-U0-33); `normative_at(policy, fecha)` con fechas en **`America/Bogota`**; cuatro ojos; activación (la anterior pasa a `historica`).
  - Propiedades PBT-U4-03 (incluidos los bordes de la medianoche de Bogotá) y PBT-U4-04.
  - Diseño: BR-U4-10, 11; P-U4-05. Historias: US-205, US-206.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_policy.py`, y la prueba con reloj simulado: el cambio de vigencia ocurre a las 00:00 de Bogotá y no a las 19:00 de Bogotá.

- [x] **Paso 5 — `serving_config`** (U04-T02)
  - Composición de domain-entities §5 (incluido `inference_service`) y `etag` (JCS de todos los campos; sin `bias_monitoring_age_s`, precisado el 2026-10-08 por U9 FD); prueba de ejemplo: cambiar solo `inference_service` cambia el `etag`.
  - Propiedad PBT-U4-05.
  - Diseño: BR-U4-11, 14; P-U4-07.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_serving_config.py`.

- [x] **Paso 6 — `registration`** (U04-T02)
  - Formato permitido, rechazo de `pickle`/`joblib` por extensión y bytes mágicos, SHA-256 sobre los bytes de cada archivo del `manifest.json` (U5) y mismo `model_version_id` en todos; nunca deserializa.
  - Propiedad PBT-U4-06.
  - Diseño: BR-U4-06. Historia: US-201.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_registration.py`, más una prueba que hace fallar a cualquier deserializador si se lo invoca (*monkeypatch* de `pickle.loads`, `joblib.load` y `onnx.load`).

- [x] **Paso 7 — Resumen de la lógica pura** (U04-T02)
  - `aidlc-docs/construction/governance/code/business-logic-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit governance --section logic` (BR-U4-01, 02, 04, 06, 10, 11 y 14 aparecen en las pruebas).

### Bloque D — Servicio

- [x] **Paso 8 — Evidencia en dos fases, reconciliador y barridos** (U04-T03, acotado a la demo)
  - Transición `pendiente_registro` → append con `idempotency_key = UUIDv5(entity_type:entity_id, n)` → `confirmada` + efecto (BR-U4-17); excepción de `freeze` (BR-U4-15); conflicto tras un abandono → reenviar la abandonada y confirmarla (precisado el 2026-10-06).
  - Tarea de fondo con `SKIP LOCKED`, que toma solo la menor `n` pendiente de cada entidad: reintentos, `abandonada` a las 24 h (salvo `freeze` y compensaciones), `FreezeEventPending`, compensaciones `transicion_descartada` sin abandono con `CompensationEventPending`, y barrido de validaciones vencidas (P-U4-02; precisado el 2026-10-06, revisión del FD de U8).
  - Propiedades stateful **PBT-U4-01** (máquina completa con actores y MFA, contra el servicio y Testcontainers) y **PBT-U4-07** (registro con fallos al azar).
  - Diseño: BR-U4-05, 15, 17; NFR-U4-40; P-U4-02.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_stateful_*.py governance/tests/integration/test_evidence.py`, con 2 réplicas y un doble del registro que falla al azar: ninguna transición distinta de `freeze` cambia el estado sin ack; ningún evento se duplica; abandono + transición nueva con la abandonada ya escrita → un solo evento y el estado de la abandonada; `frozen_resolution` con el `freeze` pendiente → 409 `transition_pending`; `freeze` con un `mark_active` pendiente → la versión queda `congelado`, el par queda `descartada` sin aplicar aunque luego llegue el ack, la versión destino no pasa a `activo` y la cadena tiene `freeze` y después los `transicion_descartada` (precisado el 2026-10-06, revisión del FD de U8). Una compensación pendiente más de 24 h no pasa a `abandonada`, sigue bloqueando la `frozen_resolution` (409 `transition_pending`) y dispara `CompensationEventPending`; `promtool test rules` de esa alerta. Barrido por modo (tercera revisión del FD de U9, 2026-10-10): un `ValidationRun` `validacion` vencido → la versión a `validacion_fallida`; uno `source_comparison` vencido → solo el run a `timeout`, la fuente sigue `en_evaluacion` y ninguna versión cambia.

- [x] **Paso 9 — `serving-config` en memoria, convergencia y pools** (U04-T03)
  - Copia en memoria; `LISTEN serving_config` + sondeo del `etag` cada 1 s; temporizador de medianoche de Bogotá; readiness solo con la copia cargada.
  - Edad de la copia (NFR-U4-04; revisión de coherencia entre unidades, 2026-10-10): gauge `vectra_serving_config_age_seconds` (segundos desde la última confirmación contra la base); a los 30 s sin confirmar, `GET /v1/serving-config` responde 503.
  - `If-None-Match`/304.
  - Pools `tx` 2, `read` 1, `background` 1 y `listen` 1.
  - Diseño: NFR-U4-04, 05, 06, 10; P-U4-01, 04, 05.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_convergence.py test_pools.py` (Testcontainers con 2 réplicas):
    - `freeze` en A → B sirve el `etag` nuevo en ≤ 1 s, también con la conexión `LISTEN` de B cortada;
    - con la base pausada, `serving-config` sigue respondiendo la última copia durante 29 s y responde 503 a los 30 s; el gauge de edad crece y vuelve a 0 al reanudar la base (revisión de coherencia entre unidades, 2026-10-10);
    - `pg_stat_activity` cuenta 5 conexiones por réplica.

- [x] **Paso 10 — Endpoints** (U04-T04, acotado a la demo; arranque completado en U04-T08)
  - Nota (U04-T08): arranque completado en U04-T08. `vectra_governance.service` (`config_from_env`, `build_app`, `main`) arma `ApiDeps` desde las variables del chart, con el cliente S3 de F47 (`s3_store.py`, SigV4 contra MinIO) y `Background` en el ciclo de vida; `test_container_start.py` arranca la imagen de verdad.
  - Modelos: registrar, lanzar validación (Job en `vectra-staging` por K01, con TTL, `activeDeadlineSeconds` y `backoffLimit: 0`), recibir el informe (F32), aprobar o rechazar, `mark_active`, retirar.
  - Registro: los paquetes RT-3 (a), (c) y (d) de U5 → 422 sin crear la versión; (b) → aceptado (BR-U4-06; doble de los paquetes hasta que exista U5; quinta revisión de coherencia entre unidades, 2026-10-31).
  - `freeze` (solo `governance:freeze`).
  - `GET /v1/models/{id}/feature-dictionary` (solo `governance:read-dictionary`; BR-U4-18, agregado por U7 FD Q4).
  - `GET /v1/models/{id}/feature-spec` (solo `governance:read-feature-spec`; BR-U4-19, agregado por U8 FD Q1). Prueba: otra identidad → 403; el contenido es byte a byte el `feature_spec.json` verificado.
  - `frozen-resolution`: solo `cumplimiento` + MFA + step-up; fija `SET LOCAL vectra.frozen_resolution`.
  - Políticas (cuatro ojos; `POST /v1/policies/{id}/approval` recibe `PolicyDecisionIn`; revisión de consistencia entre unidades, 2026-11-01); fuentes (BR-U4-13, precisado el 2026-10-08 por U9 FD): versión candidata con `source_candidate_for`, Job en modo `source_comparison` (con la versión activa también desplegada en KServe de staging, X08), `PUT /v1/validation-runs/{run_id}/source-counts` (F32), `compare_source` por **F25** con tablas de conteo (doble de U9 hasta que exista) y `data_sources.pre_post_report`; un `timeout` en ese modo no cambia ninguna versión (revisión del FD de U9, 2026-10-08); `freeze` agrega `data_sources` e `initial_disparity` al `FreezeContext` antes de escribir el evento (BR-U4-15).
  - Todas las rutas como `RouteContract` en el registro de contratos de U0.
  - Diseño: BR-U4-01..05, 07, 08, 10..13, 15, 16, 18, 19; NFR-U4-11, 25; P-U4-03, 06. Historias: US-201, US-202, US-203, US-205, US-206, US-208, US-305.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_api_*.py` con las pruebas de ejemplo de business-logic-model §3:
    - `cro` aprueba → 200; `ingeniero_riesgo` → 403;
    - un CRO, un job o un webhook intentan reactivar → denegado;
    - el mismo CRO propone y aprueba → 409;
    - una vigencia normativa vencida da `normative_current` nulo;
    - una candidata con `source_candidate_for` y la fuente `en_evaluacion` se registra; aprobarla o activarla → 409; una versión común que declara esa fuente → 422;
    - el evento `freeze` lleva el `FreezeContext` de bias más `data_sources` e `initial_disparity`;
    - `freeze` con un token del cliente `bias-monitoring-service` → 403; con `bias-monitoring-job` → 204 (el contrato no tiene cuerpo de respuesta; revisión del FD de U9, 2026-10-08);
    - `start_source_comparison` (`ingeniero_riesgo` con MFA): sin versión `activo` → 409 `no_active_version`; con la servible `congelado` → 409 `active_version_frozen`; sin los `InferenceService` de staging → 409; otro rol → 403 (segunda revisión del FD de U9, 2026-10-08);
    - `PUT /v1/validation-runs/{run_id}/source-counts`: con `governance:validation-report` sobre un run `source_comparison` `lanzado` → 204 y `PrePostReport` guardado; en un run `validacion` o repetido → 409; sin el scope → 403 (segunda revisión del FD de U9, 2026-10-08);
    - evento `freeze` mayor de 60 KiB → `initial_disparity` con sus agregadas; mayor de 64 KiB → `data_sources` con ids; el doble del registro nunca recibe más de 64 KiB (segunda revisión del FD de U9, 2026-10-08);
    - aprobar o activar una candidata con su fuente `en_evaluacion` → 409 (segunda revisión del FD de U9, 2026-10-08);
    - `GET /v1/models?state=activo,congelado` (la versión servible que usa el BFF para `get_disparity`): con `cro` o `cumplimiento` → 200 con una sola versión; tras un congelamiento, la `congelado`; con `analista` → 403 (sexta revisión del FD de U9, 2026-10-10);
    - el `data_source_event` de `aprobada` y de `rechazada` lleva el `pre_post_report` con ≤ 48 KiB; un informe más grande llega con `truncated = true` (tercera revisión del FD de U9, 2026-10-10);
    - `source_comparison` vencido (reloj simulado) → `ValidationRun` `timeout`, sin `validacion_fallida` (tercera revisión del FD de U9, 2026-10-10).
    
    Además, `make -C contracts openapi && git diff --exit-code contracts/openapi/`.

- [x] **Paso 11 — Resumen del servicio** (U04-T04)
  - `aidlc-docs/construction/governance/code/api-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit governance --section api` (BR-U4-03, 05, 07, 08, 12, 13 y 15..17 aparecen en las pruebas).

### Bloque E — Herramientas y Jobs

- [x] **Paso 12 — `promotion-tool`** (U04-T05b, acotado a la demo)
  - `list_promotable`, `create_promotion_pr` (un solo commit que **agrega** el `InferenceService` `isvc-<8 hex>` de la versión, con predictor y explicador del mismo `model_version_id`, más la evidencia `helm template` y `kubectl diff` contra kind), `post_activation_pr` (baja la versión anterior a 1 réplica por componente), `rollback_pr` (restaura los mínimos de producción de la versión `inactivo` antes de su `mark_active`), `retire_inference_service` (PR que retira el de una versión `inactivo` > 7 días) y `mark_active` (que también fija `inference_service` en `serving-config`).
  - Login PKCE con loopback (token solo en memoria), `gh` con la sesión del ingeniero y commit firmado. Nunca sincroniza ni aplica.
  - Diseño: BR-U4-08, 09; NFR-U4-20, 21. Historias: US-204, US-208.
  - **Aceptación**: `uv run pytest governance/tests/unit/test_promotion_tool.py`:
    - con un repositorio git de fixture, el PR generado tiene un solo commit firmado y los dos manifiestos con el mismo `model_version_id`;
    - ningún archivo de configuración guarda tokens;
    - `! grep -rE "argocd app sync|kubectl apply|helm (install|upgrade)" governance/promotion_tool/`.

- [x] **Paso 13 — `model-validation-job`** (U04-T05, acotado a la demo)
  - En `vectra-staging` (quinta revisión de coherencia entre unidades, 2026-10-31): `ServiceAccount` `model-validation-job` y `ExternalSecret` con la llave `private_key_jwt` de su cliente de Keycloak (F32, F50). La credencial de solo lectura de `validation-datasets` (F31) es `minio-validation`, usuario `validation-readonly`, que U1 ya entrega en `vectra-staging` (revisión de consistencia entre unidades, 2026-11-01). El Job las monta y sigue sin token de Kubernetes. Recursos de INF-U4-01.
  - AUC-ROC (con `auc_target` y `auc_meets_target`), disparidad inicial con la librería de U9 (`counts_from_records` + `disparity_by_band`; doble mientras no exista), prueba de sincronía predictor ↔ explicador, informe con el `disclaimer` y envío por F32.
  - Modo `source_comparison` (BR-U4-13): puntúa el dataset con la versión activa y con la candidata y envía por F32 **solo** tablas de conteo por atributo, nunca filas (precisado el 2026-10-08 por U9 FD).
  - Imagen con las librerías de inferencia, `runAsNonRoot`, `readOnlyRootFilesystem`, sin token de Kubernetes.
  - La plantilla del Job que governance crea en `vectra-staging` (K01) lleva **explícita** la anotación del sidecar nativo de Linkerd (`config.alpha.linkerd.io/proxy-enable-native-sidecar: "true"`), como todo Job de un namespace mallado (U1 P-U1-05). Así el Job termina cuando termina su contenedor, aunque la mutación de Kyverno no se aplicara (revisión del Infrastructure Design de U10, 2026-10-10). Aceptación adicional: prueba sobre la plantilla generada (la anotación está) y, en kind, un Job de validación termina `Complete` con el proxy detenido.
  - Diseño: BR-U4-07; NFR-U4-12, 23; P-U4-03; U1 P-U1-05. Historia: US-202.
  - **Aceptación**: `uv run pytest governance/tests/unit/test_validation_job.py`:
    - con un modelo ONNX de fixture y un explicador que no produce vectores → `sync_check.passed = false`;
    - las plantillas del informe pasan `contracts/tools/forbidden_phrases.py` con la lista única de U0 (FR-BIA-08, BR-U0-94; precisado el 2026-10-10 por U10 FD, Q8);
    - modo `source_comparison`: la salida solo tiene tablas de conteo (ninguna clave por registro) y la suma de cada tabla es el tamaño del dataset.

- [ ] **Paso 14 — Scripts de CI** (diferido por la demo (T4))
  - `no-unfreeze-paths`: falla si hay escrituras `congelado → activo` fuera del handler de cumplimiento.
  - `promotion-pr-check`, workflow de `.github/workflows/` en la raíz del monorepo, para los PR que tocan `vectra-risk/vectra-risk-gitops/`: un commit, mismo `model_version_id` y evidencia adjunta. Un check obligatorio no puede usar `on.paths`, porque GitHub lo deja pendiente en los PR que no tocan la ruta: el filtro va dentro del job (revisión de consistencia entre unidades, 2026-11-01).
  - `branch-protection-check`: verifica con `gh api` la protección de `main` del único repositorio, el monorepo (`vectra-risk-gitops/` vive dentro, con el prefijo `vectra-risk/`), incluida la aprobación obligatoria de los *code owners* (`require_code_owner_reviews`), que sostiene la revisión de cumplimiento de `values-monitoring-policy.yaml` de U9 y `contracts/forbidden-phrases.yaml` de U0. `CODEOWNERS` es un solo archivo, `.github/CODEOWNERS`, con una regla por ruta (revisión del FD de U10, 2026-10-10, A5; revisión de consistencia entre unidades, 2026-11-01).
  - `sbom-check`: la imagen del servicio no contiene ONNX Runtime, `xgboost` ni `lightgbm`.
  - Diseño: BR-U4-03, 09; NFR-U4-21, 22, 24. Historias: US-204, US-305.
  - **Aceptación**: `uv run pytest governance/tests/unit/test_ci_scripts.py` (cada script falla con un fixture que lo viola y pasa con uno correcto).

- [ ] **Paso 15 — `model-archive`** (diferido por la demo (T5))
  - CronJob diario: lee del model-store (F101), sube a `vectra-model-archive` (F100) con object lock `COMPLIANCE`, cifrado del lado del servidor y TLS, descarga y verifica el SHA-256, y solo entonces registra `archived_uri` (F102, `gov_archiver`).
  - Diseño: NFR-U4-31; INF-U4-02, 03.
  - **Aceptación**: `uv run pytest governance/tests/integration/test_model_archive.py`, con Testcontainers (PostgreSQL y MinIO con object lock):
    - una versión activada queda archivada y con `archived_uri`;
    - un SHA-256 distinto → no registra y emite la métrica de fallo;
    - borrar el objeto archivado → rechazado por el lock.

### Bloque F — Despliegue y operación

- [x] **Paso 16 — Chart, flujos y RBAC** (U04-T06, acotado a la demo)
  - Deployment: HPA de 2 a 6, spread, PDB, `vectra-high`, recursos de INF-U4-01, `tzdata`.
  - CronJob `model-archive` (sidecar nativo de Linkerd, `Forbid`); Job de migración como hook, con la `ServiceAccount` `migration-governance`, la etiqueta `vectra.io/workload: migration-governance` (F44) y `pg-role-gov-migrator`. El servicio y `model-archive` montan `pg-role-gov-app` y `pg-role-gov-archiver`, y para leer el model-store `minio-governance` (`governance-readonly`, F47) y `minio-model-archive` (`model-archive-writer`, F101), todos de U1; la credencial del S3 del banco de F100 sigue en este chart. En kind, el destino es MinIO por F118, con `minio-model-archive` (revisión de consistencia entre unidades, 2026-11-01).
  - RBAC K01; values del bucket por entorno en `vectra-risk-gitops/values/<env>/governance.yaml` (revisión de consistencia entre unidades, 2026-11-01).
  - Runbook de kind: carga `reference-policy.json` de U5 como política por la API normal, con `ingeniero-1` proponiendo y `cro-1` aprobando, y sin un atajo en el servicio (seguimiento de la cuarta revisión de coherencia, 2026-10-31).
  - La plantilla de values de staging con el predictor de la versión activa la entrega U6, que se construye después; aquí se prueba con un doble y, cuando exista U6, con su chart (INF-U4-05; seguimiento de la cuarta revisión de coherencia, 2026-10-31).
  - Verificar F100, F101 y F102 en `platform/network/flows.yaml` de U1: ya están (revisión de consistencia entre unidades, 2026-11-01).
  - Sin `AuthorizationPolicy` ni `HTTPRoute` en el chart: U1 las genera desde `http_routes.governance-service` de `flows.yaml`, una por identidad, con la ruta de captura `governance-catch-all`. Aquí se verifica la ruta `freeze`, solo para la identidad `bias-monitoring-job` (revisión de consistencia entre unidades, 2026-11-01); prueba de conectividad: `bias-monitoring-service` → `freeze` → denegado (precisado el 2026-10-10 por U9 Infrastructure Design Q4).
  - Diseño: NFR-U4-03, 25; INF-U4-01..05.
  - **Aceptación**: `helm template` + `conftest test governance/chart/`; `conftest test` sobre los values de staging (el `InferenceService` de la versión activa es solo predictor, 1 réplica, `vectra-low`; tercera revisión del FD de U9, 2026-10-10); `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests` (F100–F102 presentes).

- [x] **Paso 17 — Alertas, runbooks y documentación** (U04-T06, acotado a la demo)
  - `PrometheusRule` con las alertas de P-U4-08 (incluidas `ServingConfigStale` (revisión de coherencia entre unidades, 2026-10-10), `ServingConfigConvergenceSlow`, `ModelArchivePending` y `CompensationEventPending`, esta última precisado el 2026-10-06, revisión del FD de U8) y sus runbooks, cada una con `runbook_url`.
  - `docs/slo.md` (governance dentro del SLO, NFR-U4-01).
  - Diseño: NFR-U4-01, 07; P-U4-08; BR-U4-08, 11, 16.
  - **Aceptación**: `promtool test rules governance/observability/rules/tests/*.yaml`; `uv run python platform/tests/test_runbooks.py --root governance`; `test -s governance/docs/slo.md`.

- [x] **Paso 18 — Application de GitOps** (U04-T06)
  - Entrada `governance` en `vectra-risk-gitops/components.yaml` con `wave: 5` (migración como hook, servicio y CronJob); `generate.py` escribe las Applications y los values por entorno van en `vectra-risk-gitops/values/<env>/governance.yaml` (revisión de consistencia entre unidades, 2026-11-01).
  - Diseño: P-U1-12.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`, `uv run python platform/tests/test_waves.py` y `kyverno test` de `disallow-argocd-auto-sync` (revisión de consistencia entre unidades, 2026-11-01).

### Bloque G — Calidad

- [x] **Paso 19 — Cobertura, mutación, trazabilidad y especificación de carga** (U04-T06, acotado a la demo)
  - Cobertura de ramas ≥ 95 % y **100 %** en `model_fsm`, `policy` y `evidence`; `mutmut` en `model_fsm`; trazabilidad de cada BR-U4 a una prueba.
  - Script k6: `serving-config` con 12 clientes cada 5 s (6 de scoring y 6 de `case-worker`), una lectura de `feature_spec` por cliente de U8 al cambiar de versión y transiciones con firma (precisado el 2026-10-06 por U8 NFR Requirements, NFR-U8-15).
  - Diseño: NFR-U4-10, 11, 41.
  - **Aceptación**: `uv run pytest governance/tests --cov --cov-branch --cov-fail-under=95`, el umbral por módulo, `uv run mutmut run` sin sobrevivientes fuera de la allowlist, `uv run python platform/tests/test_traceability.py --unit governance --all` y `k6 inspect governance/tests/load/governance.js` (umbrales p95 de 20 ms y 500 ms).

### Bloque H — Verificación en kind (con aprobación humana)

- [ ] **Paso 20 — Puerta de aprobación, instalación y escenarios en kind** (U04-T07, acotado a la demo: **guía lista, pendiente del operador**; `governance/docs/paso-20-kind.md`, scripts en `governance/docs/kind/` y plantillas en `evidence/kind/`; pasa a `[x]` cuando el operador adjunte la evidencia. Entran el arranque P-7 y los escenarios 2, 3, 4 y 7 —el 7 solo hasta `serving-config`, pendiente de U7 Paso 18—; se difieren el 1, 5, 6, 8 y 9)
  - **Requisito previo**: un PR con los Pasos 1–19 aprobado por un humano, sobre U1–U3 instalados en kind.
  - El operador sincroniza la wave 5 y ejecuta, con evidencia:
    1. la prueba de carga k6;
    2. la validación con el modelo de referencia (cuando existan U5 y U6) → informe en ≤ 30 min;
    3. la promoción de punta a punta: aprobación → `promotion-tool` (PR de un commit) → revisión y merge → sync manual → `mark_active`;
    4. el rollback a la versión `inactivo` (US-208);
    5. `governance-db` pausada → la readiness sigue en 200, `serving-config` responde y las escrituras dan 503 (seguimiento de la quinta revisión de coherencia, 2026-10-31);
    6. registro caído → transiciones pendientes sin efecto y `freeze` aplicado igual;
    7. la propagación del congelamiento en ≤ 6 s (completa cuando existan U7 y U9);
    8. la protección de rama verificada con `branch-protection-check`;
    9. **US-306** (cuando existan U5 y U9): fuente propuesta, candidata con `source_candidate_for`, predictor de la versión activa en staging (INF-U4-05), Job en modo `source_comparison` dentro de **60 min** (NFR-U4-12), `PrePostReport` guardado, aprobación de cumplimiento y evento en el registro (tercera revisión del FD de U9, 2026-10-10).
  - Historias: US-201, US-202, US-204, US-206, US-208, US-306.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con comando, salida y resultado esperado contra el obtenido. Los que dependen de U5, U6, U7 y U9 se marcan como pendientes hasta que esas unidades existan.

### Bloque I — Cierre

- [x] **Paso 21 — Frontend: N/A** (U04-T07: `test ! -d governance/frontend`)
  - Las pantallas de governance son de U10 (SPA) vía el BFF.
  - **Aceptación**: `test ! -d governance/frontend`.

- [x] **Paso 22 — Cierre de la unidad** (U04-T07, acotado a la demo: `evidence/cierre-demo.md`)
  - **Aceptación**: `make -C governance check`, que corre en orden las verificaciones estáticas y de integración (Testcontainers) de los Pasos 2–19 y termina en 0. Las de kind (Paso 20) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

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
| US-306 (participa) | 2, 10, 13, 16, 20 |

| Diseño | Pasos |
|---|---|
| BR-U4-01..19 | 2, 3, 4, 5, 6, 8, 10, 12, 13, 14, 17 |
| NFR-U4-01..41 | 1, 2, 8, 9, 10, 12, 13, 14, 15, 16, 17, 19 |
| P-U4-01..08 | 2, 4, 5, 8, 9, 10, 13, 17 |
| INF-U4-01..05 | 2, 15, 16, 20 |

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

## Reglas de admisión que este plan debe cumplir (revisión de consistencia entre unidades, 2026-11-01)

Cada chart de esta unidad pasa `make -C platform check-chart CHART=<ruta>` en el PR, con los mismos values que usa Argo CD en cada entorno:

- Imágenes por digest, de un registro que admita `restrict-registries`; las de terceros se espejan.
- `runAsNonRoot`, `readOnlyRootFilesystem` (con `emptyDir` para lo que escriba en disco), sin `privileged` ni `hostPath`, con recursos y `priorityClassName`.
- `vectra.io/criticality` en cada `Deployment` y `StatefulSet` que el chart declare.
- En `vectra-app`, `vectra-edge`, `vectra-identity`, `vectra-serving` y `vectra-mock`: 2 réplicas o más, `topologySpreadConstraints` por zona, PDB por `app.kubernetes.io/name`, y HPA o `vectra.io/hpa-exempt`.

Detalle en `aidlc-docs/construction/shared-infrastructure.md` §2.
