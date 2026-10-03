# Requisitos no funcionales — U6 `model-serving`

Decisiones del plan (`model-serving-nfr-requirements-plan.md`, Q1–Q5 = A). Las verificaciones
«en kind» las ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las demás corren
en CI.

Los IDs `NFR-U6-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Corrección y sincronía (Q1, Q2; US-111, RT-3)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U6-01 | El explicador calcula los SHAP con **TreeSHAP nativo de XGBoost** (`pred_contribs=True`, modo `tree_path_dependent`), exacto y determinista. La imagen del explicador **no** incluye `shap`. `base_value` es el término de sesgo que devuelve XGBoost | Prueba: para 1 000 filas de `test`, la suma de las contribuciones + `base_value` reproduce el margen del predictor (tolerancia 1e-6); `pip list` de la imagen sin `shap` (SBOM) |
| NFR-U6-02 | Predictor y explicador del mismo `InferenceService` usan el **mismo** `storageUri` y la **misma** anotación `vectra.io/model-version-id`; cada versión tiene su propio `InferenceService` (`isvc-<8 hex>`, azul/verde, P-U6-02) | Política de `conftest`/Kyverno sobre la plantilla: los dos componentes con el mismo `storageUri` y anotación, y el nombre derivado del `model_version_id` |
| NFR-U6-03 | **Verificación al arrancar**: cada componente lee `manifest.json`, verifica el SHA-256 de cada archivo que usa y que todos lleven el mismo `model_version_id` que la anotación. Si algo no coincide, el contenedor no pasa a listo y emite `ModelPackageIntegrityFailed` (SEV2) | Prueba con los artefactos RT-3 de U5: (d) → el componente no queda listo; un archivo alterado → no queda listo |
| NFR-U6-04 | Toda respuesta de `:predict` y `:explain` incluye el `model_version_id` leído del manifiesto, para que scoring y explainability comparen (BR-U0-02) | Prueba de contrato de las dos respuestas |
| NFR-U6-05 | El predictor arma el vector en el orden de `feature_spec.json` y calcula `confidence` con `envelope.confidence` de U5 (solo numpy), en el mismo proceso que la predicción (P-U6-01) | PBT-U5-04 (paridad U5–U6) ejecutada también contra la imagen del predictor |

## 2. Rendimiento y escalado (Q3; US-609)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U6-10 | `:predict` (armado del vector + predicción + `confidence`, un solo componente): p95 ≤ 30 ms. `:explain`: p95 ≤ 150 ms | Prueba de carga de U12 en kind (operador) |
| NFR-U6-11 | Producción: predictor con 2 a 4 réplicas; explicador con 2 a 6; spread por zona y PDB | `helm template` + `conftest` |
| NFR-U6-12 | A 20 solicitudes/s (2× el pico) los componentes escalan sin superar sus máximos y sin errores | Prueba de carga de U12 + `kubectl get hpa` durante la prueba (US-609) |

## 3. Staging (Q4; X08)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U6-20 | `vectra-staging`: 1 réplica de cada componente, sin HPA, recursos reducidos | `helm template` del entorno staging + `conftest` |
| NFR-U6-21 | Aislamiento en ambas direcciones con `vectra-serving` (X08); solo `model-validation-job` llama al KServe de staging (F30) | Suite de conectividad de U1 (casos X08) |
| NFR-U6-22 | Los artefactos RT-3 se ensayan solo en staging o en kind, nunca en producción | `conftest`: los values de producción no referencian rutas `adversarial/` |

## 4. Seguridad (Q5)

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U6-30 | Imágenes propias construidas en CI sobre bases oficiales pinneadas por digest (predictor y explicador de Vectra, sobre una base Python oficial), escaneadas con Trivy, con SBOM y firmadas con Cosign; Kyverno sin excepciones | Q5, SECURITY-10, 13 | `supply-chain.yml` de U1; `kyverno test` con una imagen oficial sin firmar → rechazada |
| NFR-U6-31 | El storage initializer lee el model-store con una credencial de solo lectura (F46); los pods de serving no tienen egress | SECURITY-06, 07, AUTONOMIA-05 | `flows.yaml`; prueba de egress en kind |
| NFR-U6-32 | Pods con `runAsNonRoot`, `readOnlyRootFilesystem` y `automountServiceAccountToken: false` | SECURITY-09 | Políticas de Kyverno de U1 |

## 5. Disponibilidad

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U6-40 | Readiness = paquete cargado y verificado (NFR-U6-03); sin dependencias externas en la readiness (P-U1-04) | Prueba de readiness |
| NFR-U6-41 | Si el KServe de producción no responde, scoring y explainability fallan cerrado (`timeout`, `explainer_unavailable`; BR-U0-02); U6 no tiene modo degradado | Escenario de U12 |

## 6. Cumplimiento de extensiones (NFR Requirements U6)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-05 | Cumple | NFR-U6-31 (sin egress) |
| AUTONOMIA-06 | Cumple | NFR-U6-02..04 (misma revisión, verificación al cargar, `model_version_id` en cada respuesta) |
| AUTONOMIA-02 | Cumple | Cada requisito tiene su verificación |
| SECURITY-06 / 07 | Cumple | NFR-U6-21, 31 |
| SECURITY-09 | Cumple | NFR-U6-32 |
| SECURITY-10 / 13 | Cumple | NFR-U6-03 (integridad al cargar), NFR-U6-30 (imágenes firmadas) |
| SECURITY-11 | Cumple | NFR-U6-03: la verificación al arrancar se prueba con los casos de abuso RT-3 que construye U5 (paquete desincronizado o alterado → el componente no queda listo). Es además defensa en profundidad: repite al cargar la verificación que U4 hace al registrar. NFR-U6-22 restringe esos casos a staging y kind |
| SECURITY-14 | Cumple | NFR-U6-03 (`ModelPackageIntegrityFailed`) |
| SECURITY-15 | Cumple | NFR-U6-41 (sin modo degradado; fail-closed en los llamadores) |
| RESILIENCY-06 | Cumple | NFR-U6-40 |
| RESILIENCY-08 / 09 | Cumple | NFR-U6-11, 12 |
| PBT-09 | Cumple | Hypothesis (paridad de `confidence`, NFR-U6-05) |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

Precisado el 2026-10-03 por U6 NFR Design (Q1, Q2): un solo componente predictor (sin
transformer ni servidor de XGBoost de KServe) y un `InferenceService` por versión.


| Artefacto | Cambio |
|---|---|
| U5 FD domain-entities §3 | `explainer.json` en modo `tree_path_dependent`; `background.csv` solo como referencia |
| U5 NFR-U5-30 y tech-stack | La validación compara `pred_contribs` de XGBoost con `shap.TreeExplainer` en modo `tree_path_dependent`, y verifica la suma con el margen |
| U5 plan de tareas, Paso 5 | La misma validación |
