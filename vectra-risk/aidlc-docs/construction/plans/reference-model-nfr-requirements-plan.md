# Plan de NFR Requirements — U5 `reference-model`

**Alcance:** requisitos no funcionales y stack de la herramienta offline de U5 (generador,
entrenamiento, empaquetado y conjunto adversarial). No tiene runtime ni despliegue, así que
NFR Design e Infrastructure Design quedan en SKIP; sus decisiones de ejecución se fijan aquí.

**Ya decidido** (no se pregunta):
- el Functional Design (BR-U5-01..18), con XGBoost JSON, explicador TreeSHAP en JSON y la envolvente compartida con U6;
- Python 3.12 + workspace `uv`; Hypothesis para PBT (U0);
- CI sin credenciales del clúster (NFR-U1-40); cadena de suministro con Trivy, Syft y Cosign (U1).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Dónde se ejecuta y cómo llegan los artefactos al model-store (Security, AUTONOMIA-01)
El CI no tiene credenciales del clúster (NFR-U1-40), y el model-store vive dentro del clúster.

A) **CI construye y publica; una persona sube**:
   - un workflow de GitHub Actions ejecuta la entrega completa (BR-U5 §2) y publica el resultado como una **release firmada**: un artefacto OCI con `oras`, firma Cosign *keyless*, SBOM y una attestation de procedencia con el commit y la semilla;
   - el ingeniero de riesgo descarga la release, **verifica la firma y los SHA-256 del manifiesto**, y la sube al model-store con sus propias credenciales;
   - después la registra en U4 (US-201).

   (Recomendado: es lo que haría un banco real con su pipeline externo)

B) El CI sube directamente al model-store (requiere credenciales del clúster en el CI)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Reproducibilidad del modelo (Maintainability, BR-U5-02)
BR-U5-02 garantiza que los **datos** son idénticos byte a byte. XGBoost puede producir
árboles distintos entre ejecuciones si usa varios hilos.

A) **Reproducibilidad completa**: XGBoost con `nthread` fijo, `tree_method = "hist"`, `seed` fija y versiones pinneadas, así que el mismo commit y la misma semilla dan el mismo `predictor.json` y el mismo `model_version_id`. CI ejecuta la entrega **dos veces** y compara el SHA-256 del manifiesto; si difieren, falla (recomendado)

B) Solo los datos son reproducibles; el modelo puede variar levemente entre ejecuciones

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Tiempo y recursos de la entrega (Performance)

A) La entrega completa (120 000 filas, entrenamiento, envolvente, variante proxy y conjunto adversarial) termina en **≤ 30 min** en un runner estándar de GitHub (4 vCPU, 16 GiB), con un timeout de job de 60 min. La doble ejecución de la Q2 corre en paralelo (recomendado)

B) Sin límite de tiempo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Librerías (Tech Stack)

A)
   - **numpy** y **pandas** con **pyarrow** (Parquet);
   - **xgboost** para entrenar y exportar a JSON;
   - **shap** solo para **validar** el explicador en la entrega: comparar los valores de TreeSHAP calculados con el `explainer.json` contra los de `shap.TreeExplainer`, con tolerancia de 1e-6;
   - **scikit-learn** solo para `MinCovDet` (covarianza robusta) al calcular la envolvente;
   - la librería de disparidad de U9 (doble mientras no exista);
   - **Hypothesis** y **pytest**.

   Ninguna de estas librerías llega a la imagen de producción: U5 corre solo en CI (recomendado)

B) Implementar TreeSHAP y la covarianza robusta a mano, sin `shap` ni `scikit-learn`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U5 y las restricciones heredadas
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/reference-model/nfr-requirements/nfr-requirements.md`
- [x] 4. Generar `construction/reference-model/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
