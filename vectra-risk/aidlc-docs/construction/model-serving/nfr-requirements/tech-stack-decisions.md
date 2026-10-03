# Decisiones de stack — U6 `model-serving`

Decisiones del plan (`model-serving-nfr-requirements-plan.md`, Q1–Q5 = A).

---

| Área | Decisión | Origen |
|---|---|---|
| Plataforma | KServe en modo RawDeployment (controlador de U1) | INCEPTION, U1 |
| Predictor | Imagen propia de Vectra (Python 3.12, librería de XGBoost): en un solo proceso arma el vector con `feature_spec.json`, predice y calcula `confidence` con `envelope.confidence` de U5 (numpy). Sin transformer separado ni servidor de XGBoost de KServe (precisado por U6 NFR Design Q1) | U5, Q5, NFR Design Q1 |
| Explicador | Imagen propia de Vectra: XGBoost con `pred_contribs=True` (TreeSHAP nativo); sin `shap` | Q1 |
| Integridad | Verificación del manifiesto (SHA-256 y `model_version_id`) al arrancar cada componente | Q2 |
| Imágenes | Construidas en CI, Trivy, Syft y Cosign (`supply-chain.yml` de U1) | Q5 |
| Pruebas | pytest y Hypothesis; paridad de `confidence` con U5 | U0, U5 |

## Descartado

| Opción | Motivo |
|---|---|
| `shap` en modo `interventional` en runtime | Agrega `shap` a la imagen y depende de la muestra de fondo (Q1=B) |
| Confiar solo en la verificación de U4 | Sin defensa si el model-store se altera después de registrar (Q2=B) |
| Una réplica sin escalado | No cumple RESILIENCY-08/09 ni US-609 (Q3=B) |
| Staging igual a producción | Costo sin beneficio para la validación (Q4=B) |
| Excepción de Kyverno para imágenes oficiales | Rompe la regla única de verificación de firmas (Q5=B) |
