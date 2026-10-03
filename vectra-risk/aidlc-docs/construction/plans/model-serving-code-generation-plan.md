# Plan de tareas (Code Generation Part 1) — U6 `model-serving`

**Este plan es la única fuente de verdad para generar el código de U6.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U6. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U6 `model-serving`: sirve predictor y explicador de cada versión en un `InferenceService` propio (azul/verde) |
| Contribuye a | US-111 (sincronía por plataforma), US-204 (plantilla atómica), US-609 (escalado de KServe) |
| Ubicación | `vectra-risk/model-serving/` (imágenes, plantilla, políticas) y Applications en `vectra-risk-gitops` |
| Datos propios | Ninguno (descarga el paquete de U5 desde el model-store) |
| Depende de | U0 (puerto 8081, métricas), U1 (KServe, Kyverno, `flows.yaml`, supply chain), U4 (`serving-config.inference_service`, `promotion-tool`), U5 (paquete y `envelope.confidence`) |
| Lo consumen | scoring y explainability (U7), `model-validation-job` (U4), U12 (carga y RT-3) |
| Etapa omitida | Functional Design (sin lógica de negocio) |

**Diseño de entrada:**
- NFR Requirements: `construction/model-serving/nfr-requirements/` (NFR-U6-01..41).
- NFR Design: `construction/model-serving/nfr-design/` (P-U6-01..06).
- Infrastructure Design: `construction/model-serving/infrastructure-design/` (INF-U6-01, 02).

**AUTONOMIA-01:** las verificaciones estáticas y las pruebas de las imágenes corren en CI;
las que necesitan el clúster las ejecuta **un operador en kind** después de un PR aprobado
(Paso 11), con la evidencia adjunta al PR.

### Estructura de destino

```text
vectra-risk/model-serving/
|-- Makefile  pyproject.toml
|-- predictor/   src/  Dockerfile        # vector + XGBoost + confidence, :predict
|-- explainer/   src/  Dockerfile        # pred_contribs, :explain
|-- common/      package_loader.py  concurrency.py  metrics.py
|-- chart/       templates/inferenceservice.yaml  values-{prod,inactive,staging}.yaml
|-- policies/    conftest/  kyverno/
|-- observability/  runbooks/
`-- tests/       unit/ property/ integration/ fixtures/
```

---

## 2. Pasos

### Bloque A — Estructura

- [ ] **Paso 1 — Esqueleto de `model-serving/`**
  - Directorios de §1; `pyproject.toml` (miembro del workspace) con `xgboost`, `numpy` y la librería `envelope` de U5; **sin** `shap`.
  - Contrato de import-linter: ninguna imagen importa `shap` ni `sklearn`.
  - Diseño: NFR-U6-01.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config model-serving/.importlinter && make -C model-serving check` sobre el esqueleto.

### Bloque B — Imágenes de serving

- [ ] **Paso 2 — Cargador del paquete y límite de concurrencia (comunes)**
  - `package_loader`: lee `manifest.json`, verifica el SHA-256 de cada archivo usado y que el `model_version_id` coincida con la anotación; si falla, no marca listo y emite `ModelPackageIntegrityFailed`.
  - `concurrency`: semáforo por pod; por encima del límite responde 503 inmediato y cuenta `vectra_serving_rejected_total{component}`.
  - Diseño: NFR-U6-03, 40; P-U6-03, 05. Historia: US-111.
  - **Aceptación**: `uv run pytest model-serving/tests/unit/test_package_loader.py test_concurrency.py`, con los artefactos RT-3 de U5 como fixtures: (d) → no listo; un byte alterado → no listo; la solicitud N+1 con N en curso → 503 sin espera.

- [ ] **Paso 3 — Predictor**
  - `:predict` (protocolo v1 de KServe): arma el vector con `feature_spec.json`, predice con XGBoost y calcula `confidence` con `envelope.confidence` de U5.
  - Responde `{score, confidence, model_version_id}`; límite de 16 concurrentes; métricas en 8081.
  - Diseño: NFR-U6-04, 05, 10; P-U6-01, 05. Historias: US-111, US-106.
  - **Aceptación**:
    - `uv run pytest model-serving/tests/integration/test_predictor.py` (contrato de la respuesta; `model_version_id` del manifiesto);
    - PBT-U5-04 (paridad de `confidence`) ejecutada contra el predictor;
    - `uv run pytest model-serving/tests/bench -m benchmark` (p95 ≤ 30 ms por solicitud sin red).

- [ ] **Paso 4 — Explicador**
  - `:explain`: contribuciones con `pred_contribs=True` y `base_value` (término de sesgo), en el orden del `feature_spec`, con el `model_version_id` del manifiesto; límite de 8 concurrentes.
  - Diseño: NFR-U6-01, 04, 10; P-U6-05. Historia: US-111.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests/property/test_explainer.py`. Propiedad: para todo `FeatureVector` válido generado, la suma de las contribuciones + `base_value` reproduce el margen del predictor (tolerancia 1e-6), y la respuesta lleva el mismo `model_version_id` que `:predict`.

- [ ] **Paso 5 — Dockerfiles y cadena de suministro**
  - Imágenes del predictor y del explicador sobre una base Python oficial pinneada por digest, `runAsNonRoot`, `readOnlyRootFilesystem`; construidas, escaneadas, con SBOM y firmadas por `supply-chain.yml` de U1.
  - Diseño: NFR-U6-30, 32.
  - **Aceptación**: `hadolint model-serving/*/Dockerfile`; prueba sobre el SBOM: `shap` y `scikit-learn` ausentes; `kyverno test model-serving/policies/kyverno/` (una imagen sin firma → rechazada).

### Bloque C — Plantilla y políticas

- [ ] **Paso 6 — Plantilla del `InferenceService`**
  - `isvc-<8 hex>`: predictor y explicador con el mismo `storageUri` y la misma anotación, y etiquetas `vectra.io/component`.
  - Values `prod` (HPA por CPU al 60 %, predictor 2–4, explicador 2–6, spread, PDB, `vectra-high`), `inactive` (1 réplica fija, `vectra-normal`) y `staging` (1 réplica, recursos reducidos, `vectra-low`).
  - Probes de INF-U6-01; `emptyDir` de 1 GiB.
  - Diseño: NFR-U6-02, 11, 20; P-U6-02, 04; INF-U6-01, 02. Historias: US-204, US-609.
  - **Aceptación**: `helm template` con cada values + `kubeconform` con el CRD de `InferenceService` + `conftest test model-serving/policies/conftest/`:
    - mismo `storageUri` y anotación en los dos componentes;
    - nombre derivado del `model_version_id`;
    - prod sin rutas `adversarial/`;
    - el activo con mínimo 2 réplicas.

- [ ] **Paso 7 — Integración con `promotion-tool`**
  - Esquema de values que consume `promotion-tool` (U4, Paso 12) para los cuatro PR: promoción, post-activación, rollback y retiro.
  - Diseño: INF-U6-02; P-U6-02. Historia: US-204.
  - **Aceptación**: `uv run pytest model-serving/tests/unit/test_promotion_renders.py`. Para cada uno de los cuatro tipos de PR, el render con `promotion-tool` produce el cambio esperado y nunca deja el activo con menos de 2 réplicas.

- [ ] **Paso 8 — Flujos por etiqueta**
  - Actualizar en `platform/network/flows.yaml` de U1 los destinos de F19, F22, F30 y F46 por etiqueta (`vectra.io/component=predictor|explainer`); X08 sin cambios.
  - Diseño: NFR-U6-21, 31.
  - **Aceptación**: `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests` (los selectores por etiqueta están presentes y X08 sigue bloqueado).

### Bloque D — Operación

- [ ] **Paso 9 — Alertas y runbooks**
  - `PrometheusRule` con las alertas de P-U6-06 (`InferenceServiceNotReady` con severidad según sea el activo) y sus runbooks; `ServiceMonitor` en 8081.
  - Diseño: P-U6-06; NFR-U6-03.
  - **Aceptación**: `promtool test rules model-serving/observability/rules/tests/*.yaml`; `uv run python platform/tests/test_runbooks.py --root model-serving`.

- [ ] **Paso 10 — Applications, cobertura y trazabilidad**
  - Application en la wave 6 (InferenceServices) por entorno.
  - Cobertura de ramas ≥ 90 % y 100 % en `package_loader`; resumen en `aidlc-docs/construction/model-serving/code/README.md`.
  - Diseño: P-U1-12.
  - **Aceptación**: `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `uv run pytest model-serving/tests --cov --cov-branch --cov-fail-under=90`; `uv run python platform/tests/test_traceability.py --unit model-serving --all`.

### Bloque E — Verificación en kind (con aprobación humana)

- [ ] **Paso 11 — Puerta de aprobación y escenarios en kind**
  - **Requisito previo**: un PR con los Pasos 1–10 aprobado por un humano, sobre U1–U4 instalados en kind y un paquete de U5 registrado.
  - El operador ejecuta, con evidencia:
    1. promoción de M1 a M2 con tráfico continuo (los cuatro PR) → 0 respuestas `version_mismatch`;
    2. rollback a M1 → el activo nunca baja de 2 réplicas;
    3. artefactos RT-3 en staging → los componentes no quedan listos;
    4. saturación → 503 inmediatos y `ServingSaturation`;
    5. drenado de una zona → el activo sigue sirviendo;
    6. prueba de carga a 20 solicitudes/s (cuando exista U12) → sin superar los máximos y con p95 dentro del objetivo.
  - Diseño: NFR-U6-10, 12, 22, 41; P-U6-02..05; INF-U6-02. Historias: US-111, US-204, US-609.
  - **Aceptación**: un archivo de evidencia por escenario adjunto al PR, con comando, salida y resultado esperado contra el obtenido.

### Bloque F — Cierre

- [ ] **Paso 12 — Repositorio, migraciones y frontend: N/A**
  - U6 no tiene base de datos, migraciones ni interfaz.
  - **Aceptación**: `test ! -d model-serving/migrations && test ! -d model-serving/frontend`.

- [ ] **Paso 13 — Cierre de la unidad**
  - **Aceptación**: `make -C model-serving check`, que corre en orden las verificaciones estáticas y las pruebas de los Pasos 1–10 y termina en 0. Las de kind (Paso 11) se revisan como evidencia en el PR.

---

## 3. Trazabilidad

Verificada con un script contra las líneas «Diseño» e «Historia(s)» de cada paso antes de presentarla.

| Historia | Pasos |
|---|---|
| US-106 (contribución por `confidence`) | 3 |
| US-111 | 2, 3, 4, 11 |
| US-204 | 6, 7, 11 |
| US-609 | 6, 11 |

| Diseño | Pasos |
|---|---|
| NFR-U6-01..41 | 1, 2, 3, 4, 5, 6, 8, 9, 11 |
| P-U6-01..06 | 2, 3, 4, 6, 7, 9, 11 |
| INF-U6-01, 02 | 6, 7, 11 |

## 4. Cumplimiento de extensiones (plan de tareas U6)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Todo cambio de versión o de réplicas por PR + sync manual (Pasos 6, 7); escenarios en kind por el operador (Paso 11) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-05 | Cumple | Sin egress; solo F46 de lectura (Paso 8) |
| AUTONOMIA-06 | Cumple | Integridad al cargar (Paso 2), azul/verde sin versiones mezcladas (Pasos 6, 11) |
| SECURITY-07 / 09 / 10 / 11 / 13 / 14 / 15 | Cumple | Pasos 2, 5, 6, 8, 9, 11 |
| RESILIENCY-06 / 08 / 09 / 10 | Cumple | Pasos 2, 6, 11 |
| PBT-01..10 | Cumple | Paso 4 (propiedad de la suma), Paso 3 (paridad PBT-U5-04), pruebas de ejemplo en los Pasos 2, 3 y 7 |
