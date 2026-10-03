# Requisitos no funcionales — U5 `reference-model`

Decisiones del plan (`reference-model-nfr-requirements-plan.md`, Q1–Q4 = A). U5 corre solo
en CI y no tiene runtime; NFR Design e Infrastructure Design están en SKIP, así que las
decisiones de ejecución se fijan aquí.

Los IDs `NFR-U5-xx` se referencian en el plan de tareas.

---

## 1. Ejecución y entrega (Q1)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U5-01 | La entrega completa (BR-U5 §2) corre en un workflow de GitHub Actions **sin credenciales del clúster** (NFR-U1-40) | `grep -L "KUBECONFIG\|MINIO\|S3_" .github/workflows/reference-model.yml` devuelve el archivo (ningún secreto de clúster ni de almacenamiento) |
| NFR-U5-02 | El resultado se publica como una **release firmada**: artefacto OCI con `oras`, firma Cosign *keyless*, SBOM (Syft) y una attestation de procedencia con el commit, `generator_version` y la semilla | El workflow ejecuta `cosign verify` y `cosign verify-attestation` sobre lo que acaba de publicar |
| NFR-U5-03 | El ingeniero de riesgo descarga la release, verifica la firma y los SHA-256 del manifiesto, y la sube al model-store con **sus propias** credenciales; después la registra en U4. El procedimiento está en `reference-model/docs/release.md` con los comandos exactos | `test -s reference-model/docs/release.md`; el procedimiento incluye `cosign verify` y la verificación de cada SHA-256 |

## 2. Reproducibilidad (Q2; BR-U5-02)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U5-10 | XGBoost con `nthread` fijo, `tree_method = "hist"`, `seed` fija y versiones pinneadas en `uv.lock`: el mismo commit y la misma semilla dan el mismo `predictor.json`, el mismo manifiesto y el mismo `model_version_id` | El workflow ejecuta la entrega **dos veces** en paralelo y compara el SHA-256 de `manifest.json`; si difieren, falla |
| NFR-U5-11 | Ningún archivo de la entrega incluye marcas de tiempo, rutas locales ni nombres de máquina | Prueba que busca esos patrones en los JSON y en los metadatos de Parquet |

## 3. Tiempo y recursos (Q3)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U5-20 | Entrega completa en **≤ 30 min** en un runner estándar de GitHub (4 vCPU, 16 GiB); timeout del job de 60 min | Duración registrada por el workflow; un paso falla si supera 30 min |

## 4. Librerías y calidad (Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U5-30 | `shap` se usa **solo** para validar el explicador en CI: los valores que da XGBoost con `pred_contribs=True` (lo que calcula el explicador en runtime, U6) coinciden con los de `shap.TreeExplainer(feature_perturbation="tree_path_dependent")` con tolerancia de 1e-6 en 1 000 filas de `test`, y la suma de cada vector más `base_value` reproduce el margen del modelo (precisado por U6 NFR Q1) | Prueba de la entrega |
| NFR-U5-31 | `scikit-learn` se usa **solo** para `MinCovDet` al calcular la envolvente; el resultado se guarda en JSON | Contrato de import-linter: solo `envelope.fit` importa `sklearn` |
| NFR-U5-32 | La función compartida `envelope.confidence` (la que usa el predictor de U6 en runtime) depende **solo** de numpy y de la biblioteca estándar: ni `sklearn`, ni `shap`, ni `xgboost` | Contrato de import-linter sobre el módulo `envelope.confidence`; prueba que la importa en un entorno con solo numpy |
| NFR-U5-33 | PBT-U5-01..07 con Hypothesis, perfil `ci` (500 ejemplos, semilla impresa); cobertura de ramas ≥ 90 % y **100 %** en `envelope.confidence` | `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests` + `--cov --cov-branch` |
| NFR-U5-34 | Ningún dato real: los identificadores tienen el prefijo `SYN-` y los nombres salen del catálogo ficticio | Prueba que recorre todos los Parquet y falla con cualquier identificador sin `SYN-` o un nombre fuera del catálogo |

## 5. Cumplimiento de extensiones (NFR Requirements U5)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | NFR-U5-01, 03 (el CI no toca el clúster; una persona sube los artefactos) |
| AUTONOMIA-02 | Cumple | Cada requisito tiene su verificación |
| AUTONOMIA-05 | Cumple | NFR-U5-34 (ningún dato real); U5 no tiene runtime ni egress |
| SECURITY-10 | Cumple | NFR-U5-02 (SBOM), NFR-U5-10 (versiones pinneadas) |
| SECURITY-13 | Cumple | NFR-U5-02, 03 (release firmada con procedencia y verificación antes de subir) |
| PBT-07 / 08 / 09 | Cumple | NFR-U5-33 |
| RESILIENCY-* | N/A | Herramienta offline, sin runtime |
