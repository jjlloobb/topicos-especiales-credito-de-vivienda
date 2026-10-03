# Plan de NFR Requirements — U6 `model-serving`

**Alcance de la unidad** (`unit-of-work.md` §1): servir el predictor y el explicador **en la
misma revisión**:
- chart y plantilla del `InferenceService` (RawDeployment, predictor + explicador, `storageUri`, anotación de `model_version_id`) para prod (`vectra-serving`) y staging (`vectra-staging`);
- escalado de KServe con mínimo y máximo, y probes;
- NetworkPolicies de destino F19, F22 y F30;
- la plantilla que usa `promotion-tool`.

Functional Design = SKIP.

**Contribuye a:** US-111 (sincronía por plataforma), US-204 (plantilla atómica), US-609
(escalado de KServe).

**Ya decidido** (no se pregunta):
- el paquete de U5: XGBoost JSON, `explainer.json`, `background.csv`, `domain_envelope.json`, `feature_spec.json` y `manifest.json` con SHA-256 (BR-U5-09); sin `pickle`;
- `confidence` con la envolvente de U5, calculada en el transformer con la librería compartida (solo numpy; BR-U5-12, NFR-U5-32);
- controlador de KServe y namespaces (U1); NetworkPolicies desde `flows.yaml` (P-U1-01); Kyverno con verificación de firma (NFR-U1-25); fail-closed en scoring ante cualquier desincronía (BR-U0-02).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Cómo calcula los valores SHAP el explicador en runtime (Tech Stack / Correctness)
**Inconsistencia que encontré.** U5 definió `explainer.json` en modo `interventional`, con una
muestra de fondo, y validó esos valores contra `shap.TreeExplainer` solo en CI
(NFR-U5-30). Pero en runtime **alguien tiene que calcular** los SHAP de cada solicitud, y
U5 no definió con qué.

A) **TreeSHAP nativo de XGBoost** (`predict(pred_contribs=True)`, modo *tree path dependent*, exacto). El explicador no necesita `shap` ni la muestra de fondo en runtime.
   - Se precisa U5: `explainer.json` declara el modo `tree_path_dependent`, y la validación de CI compara contra `shap.TreeExplainer(feature_perturbation="tree_path_dependent")` con tolerancia de 1e-6.
   - `background.csv` se mantiene solo como referencia para el diccionario y las pruebas.

   (Recomendado: una sola librería en runtime, valores exactos y deterministas, sin dependencia de la muestra de fondo)

B) **`shap.TreeExplainer` en modo `interventional`** en la imagen del explicador, con la muestra de fondo (agrega `shap` y sus dependencias a la imagen de runtime)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Integridad y versión al cargar (Security / Correctness, US-111, RT-3)

A) **Verificación al arrancar**: el transformer, el predictor y el explicador leen `manifest.json`, verifican el SHA-256 de **cada** archivo que van a usar y que todos lleven el mismo `model_version_id` que la anotación del `InferenceService`. Si algo no coincide, el contenedor **no** pasa a listo y emite `ModelPackageIntegrityFailed`. Toda respuesta (`:predict` y `:explain`) incluye el `model_version_id` leído del manifiesto, para que scoring y explainability puedan comparar (BR-U0-02) (recomendado: defensa adicional a la verificación de U4 al registrar)

B) Confiar en la verificación de U4 al registrar y no repetirla al cargar

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Rendimiento y escalado en producción (Performance / Scalability, US-609)
Pico de diseño: 10 solicitudes/s (U1), es decir, 10 `:predict` y 10 `:explain` por segundo.

A)
   - `:predict` (transformer + predictor): **p95 ≤ 30 ms**.
   - `:explain`: **p95 ≤ 150 ms**.
   - Predictor y transformer: mín. 2, máx. 4 réplicas. Explicador: mín. 2, máx. 6. Spread por zona y PDB.
   - Se valida con la prueba de carga de U12 a 20 solicitudes/s (2× el pico) sin superar los máximos.

   (Recomendado)

B) Una réplica de cada componente, sin escalado

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Staging (Availability / Isolation, X08)

A) En `vectra-staging`: 1 réplica de cada componente, sin HPA y con recursos reducidos; aislado de `vectra-serving` en ambas direcciones (X08). Solo lo llama `model-validation-job` (F30). Se usa también para ensayar los artefactos RT-3 sin tocar producción (recomendado)

B) Staging con la misma configuración que producción

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Imágenes de KServe y verificación de firma (Security, SECURITY-10/13)
Kyverno exige imágenes firmadas con la identidad de Vectra (NFR-U1-25), y las imágenes
oficiales de KServe no están firmadas con esa identidad.

A) **Imágenes propias construidas en CI** a partir de las bases oficiales pinneadas por digest (servidor de XGBoost de KServe, más el transformer y el explicador de Vectra), escaneadas con Trivy, con SBOM y firmadas con Cosign. Así Kyverno verifica todas las imágenes con la misma política, sin excepciones (recomendado)

B) Una excepción en Kyverno para las imágenes oficiales de KServe, pinneadas por digest

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el alcance de U6, las historias a las que contribuye y las decisiones de U1, U4 y U5
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/model-serving/nfr-requirements/nfr-requirements.md`
- [x] 4. Generar `construction/model-serving/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Si la Q1 cambia U5, actualizar su Functional Design y su NFR Requirements y registrarlo
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
