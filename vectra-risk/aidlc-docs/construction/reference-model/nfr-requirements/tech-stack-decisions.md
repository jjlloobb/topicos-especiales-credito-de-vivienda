# Decisiones de stack — U5 `reference-model`

Decisiones del plan (`reference-model-nfr-requirements-plan.md`, Q1–Q4 = A). Versiones
pinneadas en `uv.lock`.

---

| Área | Decisión | Dónde corre | Origen |
|---|---|---|---|
| Lenguaje | Python 3.12, miembro del workspace `uv` | CI | U0 |
| Datos | numpy, pandas, pyarrow (Parquet) | CI | Q4 |
| Modelo | xgboost (`nthread` fijo, `hist`, semilla), exportado a JSON | CI | Q2, Q4 |
| Validación del explicador | shap (`TreeExplainer`, modo `tree_path_dependent`), solo para comparar con `pred_contribs` de XGBoost | CI | Q4 |
| Envolvente (ajuste) | scikit-learn `MinCovDet` | CI | Q4 |
| Envolvente (`confidence`) | numpy y biblioteca estándar; librería compartida con U6 | CI y predictor de U6 (runtime) | Q4, BR-U5-12 |
| Disparidad | Librería de U9 (doble mientras no exista) | CI | FD |
| PBT | Hypothesis, pytest | CI | U0 |
| Publicación | `oras` (OCI), Cosign *keyless*, Syft (SBOM), attestation de procedencia | CI | Q1 |
| Ejecución | GitHub Actions, runner estándar (4 vCPU, 16 GiB) | CI | Q3 |

## Descartado

| Opción | Motivo |
|---|---|
| CI que sube al model-store | Pondría credenciales del clúster en el CI (Q1=B; NFR-U1-40) |
| Solo datos reproducibles | El `model_version_id` cambiaría entre ejecuciones del mismo commit (Q2=B) |
| TreeSHAP y MCD propios | Más código propio en piezas numéricas delicadas (Q4=B) |
