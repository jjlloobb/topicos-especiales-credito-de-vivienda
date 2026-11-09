# Código de U6 `model-serving`: resumen

Alcance acotado a la demo (`demo-recorte-funcional.md` §3 U6). Plan: `aidlc-docs/construction/plans/model-serving-code-generation-plan.md`.

## Qué hay y dónde

| Pieza | Dónde | Tarea | Pasos |
|---|---|---|---|
| Cargador y verificación del paquete (`package_loader`), límite de concurrencia, métricas | `model-serving/common/src/vectra_serving_common/` | U06-T01 | 1, 2 |
| Predictor (`:predict`) y explicador (`:explain`) | `model-serving/predictor/src/vectra_predictor/`, `model-serving/explainer/src/vectra_explainer/` | U06-T01 | 3, 4 |
| Imágenes (Dockerfile por digest, `runAsNonRoot`, `readOnlyRootFilesystem`) | `model-serving/predictor/Dockerfile`, `model-serving/explainer/Dockerfile` | U06-T01 | 5 |
| Chart: `InferenceService` por versión (perfiles `prod`, `inactive`, `staging`), PDB y `ServiceAccount` `kserve-model` con `minio-kserve` | `model-serving/chart/` | U06-T02 | 6, 7 |
| Esquema de values que consume `promotion-tool` | `model-serving/chart/values.schema.json`, `model-serving/docs/values.md` | U06-T02 | 7 |
| Políticas `conftest` de la plantilla (una mutación por regla en `test_chart.py`) | `model-serving/policies/conftest/` | U06-T02 | 6 |
| Prueba de los cuatro PR y de los flujos F19, F22, F30 y F46 | `model-serving/tests/unit/test_promotion_renders.py`, `model-serving/tests/unit/test_flows_labels.py` | U06-T02 | 7, 8 |
| CRD de `InferenceService` de KServe v0.21.0 (fixture de `kubeconform`) | `model-serving/tests/fixtures/crds/` | U06-T02 | 6 |
| Application `model-serving` (wave 6, sin sync automático) y values por entorno (`inferenceServices: []`) | `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/values/<env>/model-serving.yaml` | U06-T02 | 10 |

## Comandos

- `make -C model-serving check`: lint, pruebas con cobertura (≥ 90 % de ramas y 100 % en `package_loader`), `policy-chart`, `policy-chart-u1` y trazabilidad.
- `make -C model-serving policy-chart`: `helm template` de cada perfil + `kubeconform -strict` + `conftest`.
- `make -C model-serving policy-chart-u1`: lo que Argo CD renderiza por entorno, más cada perfil encima, contra `require-hpa-bounds` y el rego de `platform/policies/rego`.

## Diferido por la demo

Ver `aidlc-docs/construction/model-serving/evidence/cierre-demo.md`. Fuera de U06-T02: Paso 9 (alertas, runbooks, `ServiceMonitor`; T2), benchmark (T3), firma y SBOM (T1) y los Pasos 11 a 13 (kind y cierre; U06-T03).

## Decisiones de la plantilla que el operador verifica en el Paso 11

- El `storageUri` viaja como `STORAGE_URI` del contenedor y como anotación `internal.serving.kserve.io/storage-initializer-sourceuri` del componente; el volumen `kserve-provision-location` (`emptyDir` de 1 GiB) lo declara el chart. Hay que confirmar en kind que el storage initializer se inyecta en el predictor y en el explicador.
- La credencial de F46 es el Secret `minio-kserve` de U1, referenciado en `secrets` de la `ServiceAccount` `kserve-model`. Sus claves son `accessKey` y `secretKey`, no las `AWS_*` que KServe espera por defecto: hay que confirmar en kind cómo las lee el storage initializer (`CANDIDATAS.md`).
- `vectra.io/serving-state: inactivo` y `vectra.io/hpa-exempt` se declaran en el `InferenceService` y en los pods de cada componente; hay que confirmar que KServe los propaga al `Deployment` que evalúa Kyverno (Paso 19 de U1, INF-U6-02).
