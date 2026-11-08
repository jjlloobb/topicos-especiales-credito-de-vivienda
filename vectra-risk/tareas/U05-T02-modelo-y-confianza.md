# U05-T02 — Modelo, envolvente, `confidence` y empaquetado de `reference-model`

**Unidad:** U5 `reference-model`
**Historias que implementa:** US-106 (RT-4) y US-201 (artefacto), en su parte de modelo y paquete.
**Depende de:** U05-T01 (PR 81). **Si el PR 81 todavía no está fusionado, la rama parte de `origin/tarea/U05-T01`**, y el orquestador la rebasa sobre `main` cuando se fusione.

Bloque C del plan de U5 (Pasos 3 a 5), que entra **completo** en la demo (E). Rige el ritmo RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: una tarea por bloque, máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 3 a 5 del plan (`aidlc-docs/construction/plans/reference-model-code-generation-plan.md`, Bloque C), con su texto, su diseño y su aceptación **sin recortes**:

- **Paso 3 — Entrenamiento**: XGBoost con `nthread` fijo, `hist` y semilla; solo las features de domain-entities §3.1; AUC de validación ≥ 0,85 **[INTERNO]** o la entrega falla. Diseño: BR-U5-07, 08; NFR-U5-10. Aceptación: `uv run pytest reference-model/tests/examples/test_train.py` (AUC ≥ 0,85 con la semilla de referencia; una feature excluida en el `feature_spec` → error).
- **Paso 4 — Envolvente de dominio y `confidence`**:
  - `envelope/fit.py`: p1–p99, categorías vistas, `MinCovDet` y la distribución de distancias.
  - `envelope/confidence.py`: la fórmula de BR-U5-12, cuantizada a `Decimal4`, solo con numpy.
  - Calibración: los casos RT-4 por debajo del umbral de `reference_policy` y al menos el 95 % de `test` por encima. El resultado se publica como `reference-policy.json`, válido según `PolicyDraft` de U0.
  - Propiedades PBT-U5-03 y PBT-U5-04.

  Diseño: BR-U5-11..13; NFR-U5-32, 33.

  Aceptación:
  - `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_envelope.py`;
  - cobertura del 100 % en `envelope/confidence.py`;
  - una prueba que importa `confidence` en un entorno con solo numpy.
- **Paso 5 — Empaquetado**:
  - `predictor.json`, `explainer.json` (TreeSHAP) y `background.csv` (200 filas, sin identificadores);
  - `domain_envelope.json`, `feature_dictionary.json` (en español, con `applicant_safe`) y `feature_spec.json`;
  - `manifest.json`, con los SHA-256 y el `model_version_id`;
  - validación del explicador: `pred_contribs` de XGBoost contra `shap.TreeExplainer(feature_perturbation="tree_path_dependent")` con tolerancia 1e-6 sobre 1 000 filas, y la suma de contribuciones + `base_value` igual al margen del modelo;
  - propiedades PBT-U5-05 y PBT-U5-06.

  Diseño: BR-U5-09, 10; NFR-U5-30.

  Aceptación:
  - `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_package.py reference-model/tests/unit/test_explainer_parity.py`;
  - el validador de manifiesto de U4 acepta el paquete. **U4 todavía no existe**: según el plan, se usa la misma lógica, copiada en una prueba desde el diseño de U4 (`aidlc-docs/construction/governance/`, validación de registro). Cita en la prueba el BR o la sección de donde sale cada regla.

Precisiones:
- **Casos RT-4 para la calibración.** El plan los genera en el Paso 7 (Bloque D), pero la calibración del Paso 4 los necesita. Implementa en `adversarial.py` solo la generación de los 18 casos RT-4 (BR-U5-16..18). Los pares RT-1 y los paquetes RT-3 quedan para el Bloque D. Regístralo en la bitácora.
- **`[INTERNO]` y `[VERIFICAR]`**: el umbral de AUC (0,85) se usa tal como está en el plan.
- **Determinismo (NFR-U5-10):** dos entrenamientos con la misma semilla dan el mismo `predictor.json` (SHA-256). Esto es parte de la aceptación del Paso 3.
- **`Makefile release`** ahora genera, entrena y empaqueta.
- **Plan:** marca `[x]` los Pasos 3 a 5, con `(U05-T02)`.

**Fuera:**
- La variante proxy (Paso 6).
- Los pares RT-1 y los paquetes RT-3 del Paso 7.
- El workflow de CI y la release firmada (Paso 8, diferido por la demo).
- El procedimiento de entrega (Paso 9).

## Archivos de contexto

- `aidlc-docs/construction/plans/reference-model-code-generation-plan.md` (Bloques C y D)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6)
- `aidlc-docs/construction/reference-model/functional-design/` (BR-U5-07..13 y 16..18; PBT-U5-03..06; domain-entities §3.1)
- `aidlc-docs/construction/reference-model/nfr-requirements/` (NFR-U5-10, 30, 32, 33)
- `aidlc-docs/construction/governance/functional-design/` (validación del manifiesto en el registro de modelos de U4)
- `contracts/python/vectra_contracts` (`PolicyDraft`, `FeatureDictionary`, `derive` con `feature_spec`, `Decimal4`)
- `reference-model/` (lo que dejó U05-T01) y `revisiones/U05-T01/`

## Criterios de aceptación

- [ ] **CA-1** — Entrenamiento, AUC y determinismo.
  ```bash
  uv run pytest reference-model/tests/examples/test_train.py -v
  ```
  Esperado:
  - AUC de validación ≥ 0,85 con la semilla de referencia;
  - con una feature excluida en el `feature_spec`, el entrenamiento da error;
  - dos entrenamientos con la misma semilla dan el mismo SHA-256 de `predictor.json`.

- [ ] **CA-2** — Envolvente y `confidence`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_envelope.py -v --cov=vectra_reference.envelope.confidence --cov-fail-under=100
  ```
  Esperado:
  - PBT-U5-03 y 04 pasan, con cobertura del 100 %;
  - los 18 casos RT-4 quedan por debajo del umbral;
  - al menos el 95 % de `test` queda por encima;
  - `reference-policy.json` es válido según `PolicyDraft`.

- [ ] **CA-3** — `confidence` solo con numpy.
  ```bash
  uv run pytest reference-model/tests -k "numpy_only" -v
  ```
  Esperado: una prueba importa `confidence` en un entorno aislado (subproceso con un `sys.path` limitado, o un venv con solo numpy) y pasa.

- [ ] **CA-4** — Paquete y paridad del explicador.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_package.py reference-model/tests/unit/test_explainer_parity.py -v
  ```
  Esperado:
  - PBT-U5-05 y 06 pasan;
  - paridad TreeSHAP ≤ 1e-6 en 1 000 filas;
  - la suma de contribuciones + `base_value` es igual al margen;
  - el validador copiado de U4 acepta el paquete y rechaza uno con un SHA-256 alterado.

- [ ] **CA-5** — `check` de la unidad y de U1.
  ```bash
  make -C reference-model check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

Rojo primero de cada criterio con una mutación. Por ejemplo:
- `nthread` sin fijar o sin semilla rompe el determinismo;
- `confidence` sin cuantizar;
- un SHA-256 alterado en el manifiesto;
- `feature_perturbation="interventional"` rompe la paridad.

Registra todo en `bitacoras/U05-T02.md`.

## Notas

- Archivos que se modifican en su sitio: `reference-model/src/vectra_reference/{train,package,adversarial}.py`, `envelope/{fit,confidence}.py`, `Makefile`, `config/generator.yaml` si hacen falta parámetros, y el plan de U5.
- Los artefactos generados (paquete y Parquet) **no** se versionan: van a un directorio de salida ignorado por git.
