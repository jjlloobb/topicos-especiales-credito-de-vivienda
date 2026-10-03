# Plan de tareas (Code Generation Part 1) — U5 `reference-model`

**Este plan es la única fuente de verdad para generar el código de U5.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U5. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U5 `reference-model`: herramienta offline, fuera de la frontera del producto, que hace de «banco que entrega su modelo» |
| Contribuye a | US-106 (RT-4), US-109 (RT-1), US-111 (RT-3), US-201 (artefacto), US-202 (dataset de validación), US-303 (modelo proxy, RT-2) |
| Ubicación | `vectra-risk/reference-model/` y el workflow `.github/workflows/reference-model.yml` |
| Datos propios | Datasets sintéticos y paquetes de modelo versionados (publicados como releases OCI firmadas) |
| Depende de | U0 (`ApplicationIn`, `derive` con `feature_spec`, `FeatureDictionary`, JCS), U1 (workflows reutilizables de CI), U9 (librería de disparidad; doble mientras no exista) |
| Lo consumen | U4 (registro y validación), U6 (predictor con `envelope.confidence`; serving), U12 (casos adversariales) |
| Etapas omitidas | NFR Design e Infrastructure Design (sin runtime ni despliegue) |

**Diseño de entrada:**
- Functional Design: `construction/reference-model/functional-design/` (BR-U5-01..18, PBT-U5-01..07).
- NFR Requirements: `construction/reference-model/nfr-requirements/` (NFR-U5-01..34).

**AUTONOMIA-01:** U5 corre solo en CI y nunca toca el clúster. La subida al model-store la
hace una persona con sus propias credenciales (NFR-U5-03).

### Estructura de destino

```text
vectra-risk/reference-model/
|-- Makefile  pyproject.toml
|-- config/generator.yaml         # versión, semilla, marginales, correlaciones, etiqueta, proxy
|-- config/catalog/               # nombres ficticios; tablas de zona y de canal (variante proxy)
|-- src/vectra_reference/
|   |-- generate.py  train.py  package.py  proxy.py  adversarial.py  release.py
|   `-- envelope/  fit.py  confidence.py      # confidence: solo numpy (compartido con U6)
|-- docs/release.md
`-- tests/  unit/ property/ examples/
```

---

## 2. Pasos

### Bloque A — Estructura

- [ ] **Paso 1 — Esqueleto y contratos de dependencias**
  - Directorios de §1; `pyproject.toml` (miembro del workspace) con numpy, pandas, pyarrow, xgboost, shap y scikit-learn; `Makefile` con `release` y `check`.
  - Contrato de import-linter: solo `envelope/fit.py` importa `sklearn`; solo la validación del explicador importa `shap`; `envelope/confidence.py` importa solo numpy y la biblioteca estándar.
  - Diseño: NFR-U5-31, 32.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config reference-model/.importlinter && make -C reference-model check` sobre el esqueleto.

### Bloque B — Datos

- [ ] **Paso 2 — Configuración y generador**
  - `generator.yaml` (marginales, correlaciones, tope VIS **[VERIFICAR]**, coeficientes de la etiqueta con ~4 % **[VERIFICAR]**) y catálogo de nombres ficticios.
  - `generate.py`: filas `ApplicationIn` válidas con identificadores `SYN-`, etiqueta por la función de riesgo latente, partición 70/15/15 estratificada y Parquet sin marcas de tiempo.
  - Propiedades PBT-U5-01 (determinismo) y PBT-U5-02 (validez).
  - Diseño: BR-U5-01..05; NFR-U5-11, 34. Historia: US-202.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_generate.py`, y una prueba que genera dos veces con la semilla de referencia y compara los SHA-256 de los Parquet; `uv run pytest reference-model/tests/unit/test_no_real_data.py`.

### Bloque C — Modelo y confianza

- [ ] **Paso 3 — Entrenamiento**
  - XGBoost con `nthread` fijo, `hist` y semilla; solo las features de domain-entities §3.1; AUC de validación ≥ 0,85 **[INTERNO]** o la entrega falla.
  - Diseño: BR-U5-07, 08; NFR-U5-10.
  - **Aceptación**: `uv run pytest reference-model/tests/examples/test_train.py` (AUC ≥ 0,85 con la semilla de referencia; una feature excluida en el `feature_spec` → error).

- [ ] **Paso 4 — Envolvente de dominio y `confidence`**
  - `envelope/fit.py`: p1–p99, categorías vistas, `MinCovDet` y la distribución de distancias.
  - `envelope/confidence.py`: la fórmula de BR-U5-12, cuantizada a `Decimal4`, solo con numpy.
  - Calibración: los casos RT-4 bajo el umbral y ≥ 95 % de `test` sobre él.
  - Propiedades PBT-U5-03 y PBT-U5-04.
  - Diseño: BR-U5-11..13; NFR-U5-32, 33. Historia: US-106.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_envelope.py`, cobertura del 100 % en `envelope/confidence.py`, y una prueba que importa `confidence` en un entorno con solo numpy.

- [ ] **Paso 5 — Empaquetado**
  - `predictor.json`, `explainer.json` (TreeSHAP) y `background.csv` (200 filas, sin identificadores).
  - `domain_envelope.json`, `feature_dictionary.json` (en español, con `applicant_safe`) y `feature_spec.json`.
  - `manifest.json` con los SHA-256 y el `model_version_id`.
  - Validación del explicador: `pred_contribs` de XGBoost contra `shap.TreeExplainer(feature_perturbation="tree_path_dependent")` (tolerancia 1e-6, 1 000 filas) y suma de contribuciones + `base_value` = margen del modelo (precisado por U6 NFR Q1).
  - Propiedades PBT-U5-05 y PBT-U5-06.
  - Diseño: BR-U5-09, 10; NFR-U5-30. Historia: US-201.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_package.py reference-model/tests/unit/test_explainer_parity.py`, y el validador de manifiesto de U4 (`vectra_governance.registration`) acepta el paquete; si U4 todavía no existe, se usa la misma lógica copiada en una prueba.

### Bloque D — Variante proxy y conjunto adversarial

- [ ] **Paso 6 — Variante proxy (RT-2)**
  - `zona_vivienda` (≥ 5 municipios por zona) y `canal_originacion_detalle` como búsquedas en el `feature_spec`; etiqueta con dependencia parcial; disparidad agregada ≥ 10 pp con la librería de U9 (doble mientras no exista); `purpose = rt2-demo`.
  - Diseño: BR-U5-06, 14, 15. Historia: US-303.
  - **Aceptación**: `uv run pytest reference-model/tests/examples/test_proxy.py` (disparidad del modelo base < 5 pp y de la variante ≥ 10 pp; ninguna zona con menos de 5 municipios; `municipality_code` no aparece en el `FeatureVector` producido por `derive`).

- [ ] **Paso 7 — Conjunto adversarial**
  - 20 pares RT-1, 18 casos RT-4 y los paquetes RT-3 (a)–(d), con `adversarial/manifest.json` y el resultado esperado de cada caso.
  - Propiedad PBT-U5-07.
  - Diseño: BR-U5-16..18. Historias: US-106, US-109, US-111.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_adversarial.py`; `uv run pytest reference-model/tests/examples/test_adversarial_manifest.py` (42 casos, cada uno con su `expected`; `RT3-d` rechazado por el validador de manifiesto).

### Bloque E — Entrega en CI

- [ ] **Paso 8 — Workflow de entrega y release firmada**
  - `.github/workflows/reference-model.yml`, que usa los workflows reutilizables de U1:
    - dos ejecuciones en paralelo de `make release`, con comparación del SHA-256 del manifiesto;
    - un paso que falla si la entrega supera 30 min (timeout del job de 60 min);
    - publicación OCI con `oras`, firma Cosign *keyless*, SBOM con Syft y attestation de procedencia (commit, `generator_version`, semilla);
    - `cosign verify` y `cosign verify-attestation` sobre lo publicado.
  - Sin secretos del clúster ni del almacenamiento.
  - Diseño: NFR-U5-01, 02, 10, 20.
  - **Aceptación**: `actionlint .github/workflows/reference-model.yml`; `grep -L "KUBECONFIG\|MINIO\|S3_" .github/workflows/reference-model.yml` devuelve el archivo; `! grep -E "kubectl|helm (install|upgrade)" .github/workflows/reference-model.yml`.

- [ ] **Paso 9 — Procedimiento de entrega al model-store**
  - `docs/release.md`: descargar la release, `cosign verify`, verificar cada SHA-256 del manifiesto, subir al model-store con las credenciales del ingeniero (bucket `model-store` y dataset de validación en `validation-datasets`) y registrar en U4 (US-201).
  - Diseño: NFR-U5-03. Historias: US-201, US-202.
  - **Aceptación**: `uv run python platform/tests/test_runbooks.py --operational --root reference-model/docs` (el documento sigue la plantilla y cada paso nombra un comando).

### Bloque F — Calidad y cierre

- [ ] **Paso 10 — Cobertura, trazabilidad y resumen**
  - Cobertura de ramas ≥ 90 % y 100 % en `envelope/confidence.py`; trazabilidad de cada BR-U5 a una prueba; `aidlc-docs/construction/reference-model/code/README.md`.
  - Diseño: NFR-U5-33.
  - **Aceptación**: `uv run pytest reference-model/tests --cov --cov-branch --cov-fail-under=90` y `uv run python platform/tests/test_traceability.py --unit reference-model --all`.

- [ ] **Paso 11 — Despliegue, repositorio, API y frontend: N/A**
  - U5 no tiene runtime, base de datos, API ni interfaz. Sus artefactos entran por U4 y los sirve U6.
  - **Aceptación**: `test ! -d reference-model/chart && test ! -d reference-model/migrations`.

- [ ] **Paso 12 — Cierre de la unidad**
  - **Aceptación**: `make -C reference-model check`, que corre en orden las verificaciones de los Pasos 1–10 y termina en 0.

---

## 3. Trazabilidad

Verificada con un script contra las líneas «Diseño» e «Historia(s)» de cada paso antes de presentarla.

| Historia | Pasos |
|---|---|
| US-106 | 4, 7 |
| US-109 | 7 |
| US-111 | 7 |
| US-201 | 5, 9 |
| US-202 | 2, 9 |
| US-303 | 6 |

| Diseño | Pasos |
|---|---|
| BR-U5-01..05 | 2 |
| BR-U5-07, 08 | 3 |
| BR-U5-09, 10 | 5 |
| BR-U5-11..13 | 4 |
| BR-U5-06, 14, 15 | 6 |
| BR-U5-16..18 | 7 |
| NFR-U5-01..34 | 1, 2, 3, 4, 5, 8, 9, 10 |

| Propiedad | Paso |
|---|---|
| PBT-U5-01, 02 | 2 |
| PBT-U5-03, 04 | 4 |
| PBT-U5-05, 06 | 5 |
| PBT-U5-07 | 7 |

## 4. Cumplimiento de extensiones (plan de tareas U5)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | El CI no toca el clúster (Paso 8); la subida la hace una persona (Paso 9) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación |
| AUTONOMIA-05 | Cumple | Ningún dato real (Paso 2) |
| AUTONOMIA-06 | Cumple | Artefactos RT-3 para probar el fail-closed (Paso 7) |
| SECURITY-05 / 10 / 11 / 13 | Cumple | Pasos 2, 5, 7, 8 |
| PBT-01..10 | Cumple | Pasos 2, 4, 5, 7, 10 |
| RESILIENCY-* | N/A | Sin runtime |
