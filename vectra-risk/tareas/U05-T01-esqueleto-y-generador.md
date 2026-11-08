# U05-T01 — Esqueleto y generador de `reference-model`

**Unidad:** U5 `reference-model`
**Historias que implementa:** US-202 (dataset de validación), en su parte de generación.
**Depende de:** U0 y U1 en `main`. U5 no depende de U2 ni de U3 (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6).

Bloques A y B del plan de U5 (Pasos 1 y 2). Los dos entran **completos** en el alcance de la demo (E). Rige el ritmo RL-1 a RL-5: una tarea por bloque, máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 1 y 2 del plan. Texto del plan, sin recortes:

- [ ] **Paso 1 — Esqueleto y contratos de dependencias**
  - Directorios de §1; `pyproject.toml` (miembro del workspace) con numpy, pandas, pyarrow, xgboost, shap y scikit-learn; `Makefile` con `release` y `check`.
  - Contrato de import-linter: solo `envelope/fit.py` importa `sklearn`; solo la validación del explicador importa `shap`; `envelope/confidence.py` importa solo numpy y la biblioteca estándar.
  - Diseño: NFR-U5-31, 32.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config reference-model/.importlinter && make -C reference-model check` sobre el esqueleto.

- [ ] **Paso 2 — Configuración y generador**
  - `generator.yaml` (marginales, correlaciones, tope VIS **[VERIFICAR]**, coeficientes de la etiqueta con ~4 % **[VERIFICAR]**) y catálogo de nombres ficticios.
  - `generate.py`: filas `ApplicationIn` válidas con identificadores `SYN-`, etiqueta por la función de riesgo latente, partición 70/15/15 estratificada y Parquet sin marcas de tiempo.
  - Propiedades PBT-U5-01 (determinismo) y PBT-U5-02 (validez).
  - Diseño: BR-U5-01..05; NFR-U5-11, 34. Historia: US-202.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_generate.py`, y una prueba que genera dos veces con la semilla de referencia y compara los SHA-256 de los Parquet; `uv run pytest reference-model/tests/unit/test_no_real_data.py`.

Precisiones:
- **`[VERIFICAR]`.** El tope VIS (`vis_cap_cop`) y la tasa objetivo de la etiqueta (~4 %) son parámetros de `generator.yaml`. El comentario conserva la marca `[VERIFICAR]` y la referencia al diseño (`functional-design/domain-entities.md`), igual que el diseño. No busques el valor «vigente» en internet ni inventes uno con aire de oficial: usa el que fije el diseño o, si no fija ninguno, un valor plausible marcado como sintético en el comentario.
- **`Makefile`.** `check` corre lint, import-linter y las pruebas. `release` existe y, en esta tarea, solo genera los datos (`generate.py`). El empaquetado llega en el Paso 5.
- **`ApplicationIn`.** Viene de U0 (`contracts/python/vectra_contracts`). Las filas generadas se validan con ese modelo, no con una copia.
- **Workspace.** Agrega `reference-model` a `[tool.uv.workspace].members` del `pyproject.toml` raíz y regenera `uv.lock`. Si al abrir el PR ya se fusionó otra tarea que tocó el workspace (U03-T01), el orquestador rebasa y vuelve a correr `uv lock`.
- **Plan.** Marca `[x]` los Pasos 1 y 2, con `(U05-T01)`.

**Fuera:**
- Entrenamiento, envolvente, `confidence`, empaquetado, variante proxy y conjunto adversarial (Pasos 3 a 7).
- El workflow de CI y la release firmada (Paso 8, diferido por la demo, T1 y T4).
- Datos reales de cualquier tipo.

## Archivos de contexto

- `aidlc-docs/construction/plans/reference-model-code-generation-plan.md` (§1 y Pasos 1–2)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (U5 y §6)
- `aidlc-docs/construction/reference-model/functional-design/` (BR-U5-01..05, PBT-U5-01 y 02, `domain-entities.md`)
- `aidlc-docs/construction/reference-model/nfr-requirements/` (NFR-U5-11, 31, 32, 34)
- `contracts/python/vectra_contracts` (`ApplicationIn`, perfiles de Hypothesis)
- `identity-edge/pyproject.toml` y `identity-edge/Makefile` como ejemplo de miembro del workspace

## Criterios de aceptación

- [ ] **CA-1** — Esqueleto, dependencias y contratos de imports.
  ```bash
  uv sync --frozen && uv run lint-imports --config reference-model/.importlinter
  ```
  Esperado: código 0, con los tres contratos `KEPT`. **Rojo primero:** un `import sklearn` en `confidence.py` hace fallar el contrato.

- [ ] **CA-2** — Propiedades del generador.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_generate.py -v
  ```
  Esperado: PBT-U5-01 y PBT-U5-02 pasan.

- [ ] **CA-3** — Determinismo byte a byte con la semilla de referencia.
  ```bash
  uv run pytest reference-model/tests -k "sha256 or determinis" -v
  ```
  Esperado: dos generaciones con la semilla de referencia dan los mismos SHA-256 de los tres Parquet (70/15/15). La prueba lee los archivos escritos de vuelta del disco.

- [ ] **CA-4** — Sin datos reales.
  ```bash
  uv run pytest reference-model/tests/unit/test_no_real_data.py -v
  ```
  Esperado: pasa. Identificadores con prefijo `SYN-` y nombres solo del catálogo ficticio.

- [ ] **CA-5** — `check` de la unidad y de U1.
  ```bash
  make -C reference-model check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

- `tests/property/test_generate.py`: PBT-U5-01 y PBT-U5-02.
- Prueba de SHA-256 con dos generaciones.
- `tests/unit/test_no_real_data.py`.
- Rojo primero de CA-1 y de PBT-U5-01 (por ejemplo, una marca de tiempo en el Parquet rompe el determinismo). Regístralo en `bitacoras/U05-T01.md`.

## Notas

- Archivos que se modifican en su sitio: `pyproject.toml` raíz, `uv.lock`, el plan de U5.
- Las dependencias pesadas (xgboost, shap) entran ya en el Paso 1, aunque su uso llegue después: así lo pide el plan.
