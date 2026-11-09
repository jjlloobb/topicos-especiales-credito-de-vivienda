# U09-T01 — Esqueleto, configuración y librería `vectra_disparity` de `bias-monitoring`

**Unidad:** U9 `bias-monitoring`
**Historias que implementa:** US-301 (disparidad por grupo, banda y atributo, con muestra insuficiente), en su parte de cálculo (Paso 4). Los Pasos 1, 2, 3 y 5 no tienen historia propia en la trazabilidad del plan (§3).
**Depende de:** U0 y U1 en `main`. No depende de U3 ni de U4: es código estático, lógica pura y pruebas sin clúster (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6).
**Rama:** `tarea/U09-T01`, que parte de `origin/main`.

Bloques A y B del plan de U9 (Pasos 1 a 5), juntos en una tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fusión «A+B», enmienda P-2). La tarea **se adelanta** y corre en paralelo con U4, porque la verificación en kind de U4 (escenario 2, `model-validation-job` del Paso 13 de U4, y `rt2-setup`) necesita la librería fusionada en `main` (enmienda §4 y §5.3; RL-5). Los Pasos 1 a 4 entran **completos** (E). El Paso 5 entra como **E\*F**: sin `mutmut` (enmienda §3, U9, fila «5 · 10 Resúmenes»; §2 regla 3); la simulación estadística se queda (P-14). Rige el ritmo RL-1 a RL-5: una tarea por bloque fusionado, máximo 2 rondas, y solo un ROJO bloquea.

---

## Alcance

**Dentro:** los Pasos 1 a 5 del plan. Texto del plan, sin recortes salvo el `mutmut` del Paso 5, que se marca abajo y va en «Fuera»:

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `bias-monitoring/`**
  - Directorios de §1; `pyproject.toml` con dos miembros del workspace: `vectra_disparity` (sin dependencias de runtime fuera de la biblioteca estándar) y `vectra_bias` (depende de `vectra_contracts`, `vectra_common` y `vectra_disparity`).
  - Dependencias de desarrollo directas: Fairlearn, pandas y numpy, solo para pruebas y la simulación; scipy y scikit-learn llegan como transitivas de Fairlearn. Herramientas de prueba: pytest, pytest-cov (coverage.py), Hypothesis y mutmut (revisión del FD de U10, 2026-10-10, B9).
  - Contratos de import-linter:
    - `vectra_disparity` no importa nada fuera de la biblioteca estándar;
    - `freeze_rule`, `context` y `window` no hacen E/S;
    - `app` y sus módulos no importan `freeze_client` (el servicio no congela);
    - ningún módulo importa `httpx` fuera de `vectra_common.deps`.
  - Diseño: P-U9-04, 05; NFR-U9-30.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config bias-monitoring/.importlinter && make -C bias-monitoring check` sobre el esqueleto; prueba de que el árbol de dependencias de runtime de `vectra_disparity` está vacío.

- [ ] **Paso 2 — Constantes y parámetros**
  - `vectra_bias/config.py`, con las constantes del código:
    - timeouts y reintentos de P-U9-02;
    - caché de 64 entradas y 15 min (P-U9-03);
    - razón de inválidas del 1 % y atraso máximo del agregador de 30 min.
  - Los cinco parámetros de cumplimiento vienen de `values-monitoring-policy.yaml` (INF-U9-03), nunca de constantes (revisión del plan de tareas de U9, 2026-10-10):
    - la app lee umbral, `n_min` y ventana para calcular, y los cinco para informarlos en el paquete y el dashboard (BR-U9-13), desde un `ConfigMap` que el chart genera de ese archivo;
    - el **horario** solo lo usa el chart, en el `schedule` del CronJob, y **W** solo lo usa la `PrometheusRule`.
  - Diseño: INF-U9-03; P-U9-02, 03; NFR-U9-03.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/unit/test_config.py`:
    - el peor caso de una corrida (3 versiones que fallan, 2 solicitudes de rangos, lectura de grupos, 3 `PUT`/`DELETE` de grupos `freeze-<v>` y 16 `DELETE` de versiones que ya no se evalúan; ≈ 186 s, P-U9-02) < `activeDeadlineSeconds` (600 s) (revisión del FD de U10, 2026-10-10, A6);
    - ninguna constante se lee de variables de entorno;
    - un archivo de parámetros con valores fuera de rango → error al arrancar.

### Bloque B — Librería `vectra_disparity`

- [ ] **Paso 3 — `stats`**
  - Funciones puras:
    - intervalo de Wilson;
    - diferencia de Newcombe (método 10);
    - combinación de varianzas `Σ w_b² v_b`.

    Todo con `math`; la salida en `Decimal4`.
  - Diseño: BR-U9-03, 04.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/unit/test_stats.py`, con valores de referencia publicados de Newcombe (1998) para varios pares de proporciones, con tolerancia de 1e−4.

- [ ] **Paso 4 — `counts` y `disparity`**
  - `counts`:
    - `counts_from_records(records) -> dict[atributo, CountTable]`;
    - `CountTable` a partir de los `MonitoringMarginalCount` de un rango.
  - `disparity_by_band(counts, attribute, n_min) -> AttributeResult`:
    - celdas, con la supresión de celdas chicas siempre aplicada (P-U9-04);
    - diferencias por banda, sin `no_informado`;
    - par extremo e intervalo de Newcombe;
    - agregada ponderada con los pesos de BR-U9-04 y su intervalo;
    - diferencia sin bandas con `population_difference_partial`.
  - Agregada del modelo y atributo disparador (BR-U9-05).
  - Diseño: BR-U9-01..07; P-U9-04; NFR-U9-31. Historia: US-301.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_disparity.py tests/property/test_counts.py tests/unit/test_disparity_examples.py`:
    - PBT-U9-01 (oráculo de Fairlearn), PBT-U9-02, PBT-U9-03 y PBT-U9-06;
    - muestra insuficiente: una banda de `region = insular` con 12 casos → «muestra insuficiente» y fuera de la agregada (US-301);
    - un grupo con una celda insuficiente → su tasa sin bandas no aparece y `population_difference_partial = true`;
    - los conteos de la variante proxy de U5 → agregada ≥ 10 pp; los del modelo base → < 5 pp.

- [ ] **Paso 5 — Resumen de la librería y simulación estadística** (E\*F)
  - Cobertura de ramas **100 %** en `stats` y `disparity`; ~~`mutmut` en `stats` y `disparity`, con 0 sobrevivientes sin justificar~~ **(diferido por la demo, T3; ver «Fuera»)**.
  - Simulación (`tests/simulation/`):
    - cobertura del intervalo de Newcombe con un par fijo (≥ 93 % de 10 000 repeticiones);
    - tasa de congelamientos falsos con disparidad real 0, con 30, 100, 500 y 2 000 casos por celda (≤ 5 % con ≥ 500 casos por celda; el resultado se documenta).
  - Versión SemVer de la librería (NFR-U9-54).
  - Resumen en `aidlc-docs/construction/bias-monitoring/code/library.md`.
  - Diseño: NFR-U9-50, ~~51~~ (diferido con `mutmut`), 53, 54.
  - **Aceptación**: `uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py --cov=vectra_disparity --cov-branch --cov-fail-under=100` (las pruebas de la librería viven en `bias-monitoring/tests`; revisión del plan de tareas de U9, 2026-10-10); ~~`uv run mutmut run --paths-to-mutate …`~~ (diferido, T3); `uv run pytest bias-monitoring/tests/simulation -m simulation` (en el workflow nocturno y en los PR que cambien `stats` o `freeze_rule`, Paso 15; el workflow está diferido, T4, así que en esta tarea la corre `make -C bias-monitoring check`).

### Precisiones

- **Estructura de §1, entera.** El esqueleto crea **todos** los directorios del árbol «Estructura de destino» del plan (§1):
  - `bias-monitoring/` con `Makefile`, `pyproject.toml` y `.importlinter`;
  - `disparity/` con su `pyproject.toml` y `src/vectra_disparity/` con `__init__.py`, `counts.py`, `stats.py` y `disparity.py`;
  - `src/vectra_bias/` con `__init__.py`, `config.py` (Paso 2) y los demás módulos de §1 como **módulos vacíos** con docstring, para que import-linter tenga qué contratar: `freeze_rule.py`, `context.py`, `window.py`, `registry_client.py`, `freeze_client.py`, `publish.py`, `run.py`, `dashboard.py`, `freezes.py`, `compare.py`, `cache.py` y `app.py`;
  - `chart/templates/` y `chart/values-monitoring-policy.yaml` (Paso 2, con los cinco parámetros de INF-U9-03: `threshold_pp: 5`, `n_min: 30`, `window_days: 30`, `schedule: "2,17,32,47 * * * *"` y `stale_after: 1h`);
  - `policies/conftest/`;
  - `observability/rules/`, `observability/rules/tests/`, `observability/runbooks/` y `observability/dashboards/`;
  - `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/doubles/`, `tests/simulation/` y `tests/load/`.

  Los directorios que estos pasos no llenan (`chart/templates/`, `policies/conftest/`, los de `observability/`, `tests/integration/`, `tests/load/`) se crean vacíos con `.gitkeep`. **No** se crean `bias.json` (Paso 13, D), `Chart.yaml` ni plantillas (Paso 12), ni `Dockerfile` (Paso 11). **No** se crean `migrations/` ni `frontend/`: el Paso 17 exige que no existan. §1 no lista `tests/e2e/`, así que no se crea.
- **Dos miembros del workspace.** `bias-monitoring/disparity/pyproject.toml` (paquete `vectra-disparity`, `dependencies = []`) y `bias-monitoring/pyproject.toml` (paquete `vectra-bias`, con `vectra-contracts`, `vectra-common` y `vectra-disparity`). Agrega los dos a `[tool.uv.workspace].members` y a `[tool.uv.sources]` del `pyproject.toml` raíz, y regenera `uv.lock`. Las dependencias de desarrollo directas (Fairlearn, pandas, numpy, pinneadas como el resto) van al grupo `dev` de la raíz, junto a `vectra-bias` y `vectra-disparity` editables, como hizo U5: CA-1 fija `uv sync --frozen` sin grupos. Si al abrir el PR ya se fusionó otra tarea que tocó el workspace (U04-T01 corre en paralelo), el orquestador rebasa y vuelve a correr `uv lock`.
- **Tipos de U0 y librería sin dependencias.** `CountTable`, `CellResult`, `BandResult` y `AttributeResult` son tipos de U0 §9.4 (`contracts/python/vectra_contracts/src/vectra_contracts/models/monitoring.py`), pero `vectra_disparity` no puede importar `vectra_contracts` (Paso 1). La librería define sus propias estructuras (por ejemplo `dataclasses` congeladas) con **los mismos nombres de campo** que U0, y las cifras en `Decimal` cuantizado a 4 decimales (`decimal`, «salida en `Decimal4`»). Una prueba (en `tests/`, que sí puede importar U0) valida la salida de la librería contra los modelos de U0: `AttributeResult.model_validate(...)` pasa, y un `CellResult` insuficiente nunca trae `rate`. `counts.py` arma la `CountTable` desde `MonitoringMarginalCount` recibidos como mapeos o atributos, sin importar U0.
- **`counts_from_records` y BR-U9-01.** Los registros llevan el `outcome` de BR-U7-04/05; solo `favorable` cuenta como favorable. `revision_requerida` y `desfavorable` cuentan como **no** favorables (BR-U9-01). Esta es la regla que U5 tuvo que corregir en su doble (`reference-model/src/vectra_reference/proxy.py`, docstring; `CANDIDATAS.md`, entrada «U5, `proxy.py` (codificador, U05-T03)»).
- **Conteos de U5 para el Paso 4.** U5 no exporta conteos. El codificador genera **una vez** un archivo con las `CountTable` agregadas (por atributo, grupo y banda: `favorable` y `total`; nunca filas) del dataset `validation` de U5 para el modelo base y para la variante proxy (`proxy/run-1`, que es la que corre la demo, DD-1), con las etiquetas de `monitoring_labels` y los outcomes de `outcomes_of` de U5. El archivo va en `bias-monitoring/tests/doubles/` con el script que lo produjo y su procedencia (commit de U5, semilla, corrida). Las pruebas de U9 leen el archivo; ni `vectra_bias` ni `vectra_disparity` importan `vectra_reference`. Como contraste (no es un criterio), U5 midió con su doble 4,61 pp en la base y 11,66 pp en la variante (`CANDIDATAS.md`, misma entrada): si la librería da otra cifra, regístralo en la bitácora como hallazgo.
- **Rutas de la aceptación del Paso 4.** El plan escribe `tests/property/test_counts.py` y `tests/unit/test_disparity_examples.py` relativos a `bias-monitoring/`. Los comandos de CA-5 usan la ruta completa desde la raíz, como el Paso 5.
- **Valores de Newcombe (1998).** Transcribe los pares y los intervalos del método 10 de la tabla publicada (Newcombe, R. G. 1998, *Statistics in Medicine* 17: 873–890) y cita la tabla en la prueba. No inventes valores de referencia ni los calcules con la propia implementación.
- **Simulación y BR-U9-11.** La tasa de congelamientos falsos usa la condición de BR-U9-11 (agregada del modelo > umbral **y** límite inferior del intervalo > 0). `freeze_rule` llega en el Bloque C, así que en esta tarea la simulación evalúa esa condición directamente sobre la salida de la librería. La tasa medida por tamaño de celda se escribe en `library.md`.
- **Parámetros fuera de rango.** Los rangos son los de INF-U9-03: umbral entre 1 y 20 pp, `n_min` ≥ 30, ventana entre 7 y 90 días, W ≥ 30 min, y horario y plazo según INF-U9-03. `config.py` carga el archivo y falla al arrancar si un valor sale de rango. La regla de `conftest` con los mismos rangos es del Paso 12.
- **PBT-U9-03 y `publish`.** PBT-U9-03 se corre entera sobre `disparity`. Su cláusula «nunca publica una tasa» se comprueba sobre `publish`, que el plan pone en el Paso 7 (Bloque C). No es un recorte: es el reparto del plan.
- **Cobertura.** `[tool.coverage.run] source` de la raíz solo mide U0. Como U5 (`CANDIDATAS.md`, entrada «U5, cobertura (codificador, U05-T04)»), usa un `bias-monitoring/pytest.ini` y un `coveragerc` propios, con el marcador `simulation` registrado.
- **`make -C bias-monitoring check`.** Corre en orden lint (`ruff check` y `ruff format --check`), import-linter, las pruebas con el perfil `ci` y la cobertura del Paso 5, y la simulación (`-m simulation`), porque esta tarea crea `stats`. Termina en 0.
- **Plan.** Marca `[x]` los Pasos 1 a 5, con `(U09-T01)`. En el Paso 5, la nota «`mutmut` diferido por la demo (T3)».

**Fuera** (recházalo aunque lo veas roto o tentador):

- **`mutmut` del Paso 5** sobre `stats` y `disparity` y NFR-U9-51. Recorte E\*F: enmienda §3, U9, fila «5 · 10 Resúmenes»: «Sin `mutmut` (T3). La simulación estadística del Paso 5 se queda (P-14)»; y §2 regla 3: «Las pruebas que miden y no son PBT (mutación, …) caen en T3 también donde la tabla del alcance marcó E. Pasa en … U9 Pasos 5 y 10». La dependencia `mutmut` sí entra en el Paso 1 (ya está en el grupo `dev`).
- **Reemplazar el doble de U5** (`disparity_by_attribute` y `model_aggregate` de `reference-model/src/vectra_reference/proxy.py`) por la librería. Lo pide una candidata, no el plan de U9: `CANDIDATAS.md`, «U5, `proxy.py` (codificador, U05-T03): `disparity_by_attribute` y `model_aggregate` son un **doble** de `vectra_disparity` de U9 … Reemplazarlo por `disparity_by_band` y `counts_from_records` cuando exista U9, y comprobar que da las mismas cifras». Queda para una tarea propia. No toques `reference-model/`.
- **Reemplazar el doble de U4** en `validation_job` (plan de U4 §1, línea «doble mientras no exista»). Es de U4.
- Bloques C a G de U9 (Pasos 6 a 18): `window`, `freeze_rule`, `context`, los clientes, `publish`, `run`, el servicio, el chart y su `ConfigMap`, la regla de `conftest` de rangos, la línea de `CODEOWNERS`, el `Dockerfile`, las alertas y el dashboard. Los módulos de `vectra_bias` distintos de `config.py` quedan vacíos.
- El workflow de CI de U9 y el nocturno (Paso 15, D por T4).
- La prueba de arquitectura de P-U9-04 «ningún módulo fuera de `vectra_disparity` construye un `CellResult` con `rate`» sobre los consumidores: llega cuando existan (Bloques C y D).
- Cambios a U0, a U1 o a `reference-model/`. Si un tipo de U0 §9.4 no encaja con la librería, se reporta.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md` (§1, Bloques A y B, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §3 U9, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U9, §4, §5.2, §5.3, §6 P-14)
- `aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md` (BR-U9-01..07, 11, 13)
- `aidlc-docs/construction/bias-monitoring/functional-design/domain-entities.md` (§1.1, §2)
- `aidlc-docs/construction/bias-monitoring/functional-design/business-logic-model.md` (§3: PBT-U9-01, 02, 03, 06, pruebas de ejemplo y validación estadística)
- `aidlc-docs/construction/bias-monitoring/nfr-requirements/nfr-requirements.md` (NFR-U9-03, 30, 31, 50, 53, 54) y `tech-stack-decisions.md`
- `aidlc-docs/construction/bias-monitoring/nfr-design/nfr-design-patterns.md` (P-U9-02, 03, 04, 05)
- `aidlc-docs/construction/bias-monitoring/infrastructure-design/infrastructure-design.md` (INF-U9-03)
- `contracts/python/vectra_contracts/src/vectra_contracts/models/monitoring.py` (tipos de U0 §9.4) y `models/base.py` (`Decimal4`)
- `contracts/tests/conftest.py` (perfiles de Hypothesis de U0)
- `reference-model/src/vectra_reference/proxy.py` (doble, `monitoring_labels`, `outcomes_of`) y `reference-model/src/vectra_reference/release.py` (origen de los conteos de U5)
- `CANDIDATAS.md` (entradas «U5, `proxy.py`» y «U5, cobertura»)
- `reference-model/pyproject.toml`, `reference-model/Makefile`, `reference-model/pytest.ini`, `reference-model/coveragerc` y `reference-model/.importlinter` como ejemplo de miembro del workspace

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`.

- [ ] **CA-1** — Esqueleto, dependencias y los cuatro contratos de imports (Paso 1; P-U9-04, 05; NFR-U9-30).
  ```bash
  uv sync --frozen && uv run lint-imports --config bias-monitoring/.importlinter
  ```
  Esperado: código 0, con los cuatro contratos del Paso 1 listados como `KEPT`. **Rojo primero:** un `import httpx` en `freeze_rule.py` y un `import vectra_bias.freeze_client` en `app.py` hacen fallar sus contratos; un `import decimal` en `stats.py` no rompe nada, y un `import pydantic` sí.

- [ ] **CA-2** — Árbol de dependencias de runtime de `vectra_disparity` vacío (Paso 1; P-U9-05).
  ```bash
  uv tree --frozen --package vectra-disparity --no-dev && uv run pytest bias-monitoring/tests/unit/test_disparity_dependencies.py -v
  ```
  Esperado: `uv tree` imprime una sola línea, `vectra-disparity v<versión>`, sin hijos. La prueba lee `bias-monitoring/disparity/pyproject.toml` y `uv.lock` y comprueba que `vectra-disparity` no declara dependencias.

- [ ] **CA-3** — Estructura completa de §1, sin `migrations/` ni `frontend/`.
  ```bash
  cd bias-monitoring && for p in Makefile pyproject.toml .importlinter disparity/pyproject.toml disparity/src/vectra_disparity/counts.py disparity/src/vectra_disparity/stats.py disparity/src/vectra_disparity/disparity.py src/vectra_bias/config.py src/vectra_bias/freeze_rule.py src/vectra_bias/context.py src/vectra_bias/window.py src/vectra_bias/registry_client.py src/vectra_bias/freeze_client.py src/vectra_bias/publish.py src/vectra_bias/run.py src/vectra_bias/dashboard.py src/vectra_bias/freezes.py src/vectra_bias/compare.py src/vectra_bias/cache.py src/vectra_bias/app.py chart/templates chart/values-monitoring-policy.yaml policies/conftest observability/rules/tests observability/runbooks observability/dashboards tests/unit tests/property tests/integration tests/doubles tests/simulation tests/load; do test -e "$p" || echo "FALTA $p"; done; test ! -d migrations && test ! -d frontend && echo OK
  ```
  Esperado: ninguna línea `FALTA` y `OK` al final.

- [ ] **CA-4** — Constantes y parámetros (Paso 2; INF-U9-03; P-U9-02, 03; NFR-U9-03; BR-U9-13).
  ```bash
  uv run pytest bias-monitoring/tests/unit/test_config.py -v
  ```
  Esperado: pasan los tres casos del plan, uno por viñeta: el peor caso (≈ 186 s, calculado desde las constantes de `config.py`, no escrito a mano) < 600 s; ninguna constante se lee de variables de entorno (la prueba cambia el entorno y comprueba que nada cambia, además de buscar `os.environ` y `getenv` en `config.py`); un archivo de parámetros con un valor fuera de cada rango de INF-U9-03 hace fallar la carga. También pasa un caso con el `values-monitoring-policy.yaml` real, que carga los cinco valores. **Rojo primero:** con `n_min: 20` en el archivo de prueba, la carga debe fallar; regístralo antes de escribir la validación.

- [ ] **CA-5** — `stats` contra Newcombe (1998) (Paso 3; BR-U9-03, 04).
  ```bash
  uv run pytest bias-monitoring/tests/unit/test_stats.py -v
  ```
  Esperado: pasan los pares de la tabla publicada (al menos los del método 10), con tolerancia 1e−4, más Wilson y la combinación de varianzas. La salida es `Decimal` con 4 decimales.

- [ ] **CA-6** — `counts` y `disparity`: PBT-U9-01, 02, 03 y 06 y las pruebas de ejemplo (Paso 4; BR-U9-01..07; P-U9-04; NFR-U9-31; US-301).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py bias-monitoring/tests/unit/test_disparity_examples.py -v
  ```
  Esperado: todos pasan, y la salida muestra un caso por viñeta: PBT-U9-01 (oráculo de Fairlearn, `MetricFrame(selection_rate)` y `demographic_parity_difference`, tolerancia 1e−9), PBT-U9-02, PBT-U9-03, PBT-U9-06, la banda `region = insular` con 12 casos, el grupo con una celda insuficiente (`population_difference_partial = true`), y los conteos de U5 (variante proxy ≥ 10 pp, base < 5 pp). Además, un caso valida la salida contra los modelos de U0 (`AttributeResult`, `CellResult`). **Rojo primero:** contar `revision_requerida` como favorable hace fallar el caso de los conteos de U5 o un caso de BR-U9-01.

- [ ] **CA-7** — Cobertura de ramas del 100 % en la librería (Paso 5; NFR-U9-50).
  ```bash
  uv run pytest bias-monitoring/tests/unit/test_stats.py bias-monitoring/tests/unit/test_disparity_examples.py bias-monitoring/tests/property/test_disparity.py bias-monitoring/tests/property/test_counts.py --cov=vectra_disparity --cov-branch --cov-fail-under=100
  ```
  Esperado: código 0, con `TOTAL … 100%` sobre `vectra_disparity`, no sobre U0.

- [ ] **CA-8** — Simulación estadística y resumen (Paso 5; NFR-U9-53).
  ```bash
  uv run pytest bias-monitoring/tests/simulation -m simulation -v && grep -nE "30|100|500|2 ?000" aidlc-docs/construction/bias-monitoring/code/library.md
  ```
  Esperado: la cobertura del intervalo de Newcombe es ≥ 93 % en 10 000 repeticiones; la tasa de congelamientos falsos con ≥ 500 casos por celda es ≤ 5 %; `library.md` existe y documenta la tasa medida para 30, 100, 500 y 2 000 casos por celda, con la limitación del par extremo para muestras chicas.

- [ ] **CA-9** — Versión SemVer de la librería (Paso 5; NFR-U9-54).
  ```bash
  uv run python -c "import re, importlib.metadata as m, vectra_disparity as d; v = m.version('vectra-disparity'); assert d.__version__ == v and re.fullmatch(r'\d+\.\d+\.\d+', v), v; print(v)"
  ```
  Esperado: imprime la versión (por ejemplo `1.0.0`) y termina en 0. La misma versión figura en `library.md`.

- [ ] **CA-10** — `check` de la unidad (RL-4) y de U1, porque el diff toca el workspace.
  ```bash
  make -C bias-monitoring check && make -C platform check
  ```
  Esperado: código 0 en los dos. El de U9 incluye lint, import-linter, las pruebas con el perfil `ci`, la cobertura del 100 % de la librería y la simulación.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_disparity_dependencies.py`: el árbol de runtime de `vectra_disparity` está vacío (Paso 1).
- `tests/unit/test_config.py`: las tres viñetas del Paso 2, más la carga del archivo real.
- `tests/unit/test_stats.py`: Wilson, Newcombe (método 10) contra la tabla de Newcombe (1998) y la combinación de varianzas.
- `tests/property/test_disparity.py`: PBT-U9-01 (oráculo de Fairlearn), PBT-U9-02 y PBT-U9-03, con los generadores del BLM §3 (1 a 7 grupos por atributo, 3 bandas, conteos de 0 a 5 000, celdas alrededor de `n_min`, `no_informado` presente o ausente; en PBT-U9-02, factores k que no cambian el estado de ninguna celda).
- `tests/property/test_counts.py`: PBT-U9-06 (`counts_from_records` y la expansión a filas son inversas; la tabla de un rango es la suma de las de cualquier partición de 30 días).
- `tests/unit/test_disparity_examples.py`: `region = insular` con 12 casos, grupo con una celda insuficiente, conteos de U5 (base y variante), validación contra los modelos de U0 y BR-U9-01 con `revision_requerida`.
- `tests/simulation/`: cobertura de Newcombe y tasa de congelamientos falsos, con la marca `simulation`.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U09-T01.md`: como mínimo, el de CA-1 (import prohibido), el de CA-4 (`n_min` fuera de rango que carga sin error) y el de CA-6 (`revision_requerida` como favorable). El par falla-pasa es la prueba.

---

## Notas

- Archivos que se **modifican en su sitio**: `pyproject.toml` raíz, `uv.lock` y `aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md` (casillas de los Pasos 1 a 5). Nada de duplicados con sufijo.
- Archivo nuevo de documentación que pide el plan: `aidlc-docs/construction/bias-monitoring/code/library.md`.
- La librería la importan después U4 (`model-validation-job`) y U5. Su API pública es la del BLM y del plan: `counts_from_records(records)`, la `CountTable` desde los conteos de un rango, `disparity_by_band(counts, attribute, n_min)` y la agregada del modelo con su atributo disparador. No cambies esos nombres.
- `n_min` es un parámetro de `disparity_by_band`, no una constante de la librería: el valor 30 viene de `values-monitoring-policy.yaml` (INF-U9-03).
- PBT-U9-01..08 nunca se recortan. En esta tarea entran las cuatro del Bloque B (01, 02, 03 y 06); las demás son de los Bloques C y D.
- La simulación tarda; si `make check` pasa de unos minutos, anótalo en la bitácora con el tiempo medido. No bajes las 10 000 repeticiones.
