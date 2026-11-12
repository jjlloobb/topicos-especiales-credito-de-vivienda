# U11-T01 — Esqueleto, configuración, lógica pura y estado de `product-metrics`

**Unidad:** U11 `product-metrics`
**Historias que implementa:** US-503 (North Star), US-504 (métrica de ruido) y US-505 (métricas operativas y de producto), en su parte de cálculo (Paso 3). Los Pasos 1, 2, 4 y 5 no tienen historia propia en la trazabilidad del plan (§3).
**Depende de:** U0 y U1 en `main`. Usa la proyección `metrics` de U3 (ya en `main`, `decision-registry/src/vectra_registry/projections.py`) solo a través de un **doble** en `tests/doubles/`; no necesita U3, U7 ni U8 desplegados. Es código estático, lógica pura y pruebas sin clúster (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6).
**Rama:** `tarea/U11-T01`, que parte de `origin/main`.

Bloques A y B del plan de U11 (Pasos 1 a 5), juntos en una tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fusión «A+B», enmienda P-2) y §8 (U11 queda en 3 tareas: A+B · C+D · E+cierre). Los Pasos 1 a 4 entran **completos** (E). El Paso 5 entra como **E\*F**: sin `mutmut` (enmienda §3, U11, fila «5»; §2 regla 3). Las PBT del bloque no se recortan. Rige el ritmo RL-1 a RL-5: una tarea por bloque fusionado, máximo 2 rondas, y solo un ROJO bloquea.

La demo que sostiene U11 es D4 (enmienda §1, «Día D + 1»): el presentador abre `product.json` y ve North Star, sostenida, tasa de consulta y días bajo el piso. Esta tarea escribe el cálculo de esas cifras; el proceso, la publicación y el despliegue son de U11-T02 (C+D) y U11-T03 (E y cierre).

---

## Alcance

**Dentro:** los Pasos 1 a 5 del plan. Texto del plan, sin recortes salvo el `mutmut` del Paso 5, que se marca abajo y va en «Fuera»:

### Bloque A — Estructura y configuración

- [ ] **Paso 1 — Esqueleto de `product-metrics/`**
  - Directorios de §1; `pyproject.toml` como miembro del workspace de `uv` (depende de `vectra_contracts` y `vectra_common`).
  - import-linter: `compute`, `noise` y `model` sin E/S; ningún módulo importa `httpx` fuera de `vectra_common.deps`; ningún módulo importa FastAPI.
  - Diseño: NFR-U11-21; tech-stack.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config product-metrics/.importlinter && make -C product-metrics check` sobre el esqueleto.

- [ ] **Paso 2 — Constantes y parámetros**
  - `config.py`: ciclo de 5 min, 02:30 UTC + desfase de 0 a 10 min, plazo de 75 min, reintentos de la completa (15 min, 6 veces), timeout de 5 s, página de 1 000, parámetros del breaker de `deps.call` en modo `consecutive_failures` de U0 (`consecutive_failures=3`, `open_for=60s`, `close_after=1`; pendientes consolidados, 2026-10-10), ventanas de 35 días y 6 meses.
  - `params.py`: lee el `ConfigMap` de `values-product-metrics-policy.yaml` (F, S, N y targets) y falla al arrancar con un valor fuera de rango.
  - Diseño: BR-U11-09, 11; NFR-U11-04, 09; P-U11-01, 02.
  - **Aceptación**: `uv run pytest product-metrics/tests/unit/test_config.py test_params.py` (valores de la tabla; rangos dentro y fuera; ninguna constante desde variables de entorno).

### Bloque B — Lógica pura y estado

- [ ] **Paso 3 — `model`, `compute` y `noise`**
  - `model`: decisión con `__slots__`, códigos enteros del catálogo de U0 y cadenas internadas (P-U11-04).
  - `compute(entries, params, now) -> BusinessMetrics`: atribución por la recomendación resuelta, North Star con desglose, sostenida, tasa de consulta, tiempo de originación con `first_evaluation`, no atribuibles, exclusiones (catálogo, `actor_role ≠ analista`, `decided_at > recorded_at + 5 min`) y `degraded`; periodos `day`, `30d`, `month_to_date` y los 6 `month`; conteos con todos los cortes y razones solo totales o por un corte.
  - `noise.days_below_floor`.
  - Diseño: BR-U11-01..10; domain-entities §3. Historias: US-503, US-504, US-505.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/property/test_compute.py tests/property/test_noise.py tests/unit/test_compute_examples.py`: PBT-U11-01, 03, 04, 06 y 07; las pruebas de ejemplo de business-logic-model §3 que no dependen de E/S.

- [ ] **Paso 4 — `state` y `reader`**
  - `reader`: `GET /v1/entries?projection=metrics&entry_type=human_decision&…&seq_after=…&limit=1000` con `deps.call` y su breaker en modo `consecutive_failures` (U0 NFR-U0-23 (i); no hay breaker propio en U11; pendientes consolidados, 2026-10-10); una página a la vez bajo un `asyncio.Lock` único; nunca avanza `last_seq` más allá de la última página confirmada.
  - `state`: pasada completa en una sola lectura desde el día 1 del sexto mes cerrado − 1 día, plegando cada página en los contadores por mes y guardando solo las decisiones de 35 días; estado nuevo construido aparte y reemplazo atómico; después, lectura incremental desde el `last_seq` de la pasada.
  - Diseño: BR-U11-11; P-U11-01, 02, 04; NFR-U11-01, 02, 09..12.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/property/test_state_machine.py tests/integration/test_reader.py` (doble de U3):
    - PBT-U11-02 (stateful, con pasadas intercaladas y fallos a mitad);
    - el doble cuenta las conexiones simultáneas y falla si ve 2;
    - una página fallida no avanza `last_seq`; 3 fallos seguidos → breaker abierto; 1 éxito en semiabierto → cerrado;
    - una entrada de 40 días va a su contador de mes y no al estado de 35 días.

- [ ] **Paso 5 — Resumen de la lógica** (E\*F)
  - Cobertura de ramas **100 %** en `compute` y `noise`; ~~`mutmut` en `compute` y `noise`~~ **(diferido por la demo, T3; ver «Fuera»)**.
  - Resumen en `aidlc-docs/construction/product-metrics/code/logic.md`.
  - Diseño: NFR-U11-30 (la parte de cobertura; la de `mutmut` se difiere), 31.
  - **Aceptación**: `uv run pytest product-metrics/tests/unit product-metrics/tests/property --cov=vectra_product.compute --cov=vectra_product.noise --cov-branch --cov-fail-under=100`; ~~`uv run mutmut run --paths-to-mutate …`~~ (diferido, T3).

### Precisiones

- **Estructura de §1, entera.** El esqueleto crea **todos** los directorios y módulos del árbol «Estructura de destino» del plan (§1):
  - `product-metrics/` con `Makefile`, `pyproject.toml`, `.importlinter`, `pytest.ini` y `coveragerc`;
  - `src/vectra_product/` con `__init__.py`, `config.py` y `params.py` (Paso 2), `model.py`, `compute.py` y `noise.py` (Paso 3), `state.py` y `reader.py` (Paso 4), y `scheduler.py`, `collector.py` y `main.py` como **módulos vacíos** con docstring, para que import-linter tenga qué contratar;
  - `tools/` (sin `gen_rules.py`, que es del Paso 12);
  - `chart/templates/` vacío y `chart/values-product-metrics-policy.yaml` (Paso 2, con los valores de domain-entities §4);
  - `policies/conftest/`;
  - `observability/rules/`, `observability/rules/tests/`, `observability/runbooks/` y `observability/dashboards/`;
  - `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/doubles/` y `tests/volume/`.

  Los directorios que estos pasos no llenan se crean vacíos con `.gitkeep`. **No** se crean `Chart.yaml` ni plantillas (Paso 11), `Dockerfile` (Paso 10), `product.json` (Paso 13) ni el workflow (Paso 14). **No** se crean `migrations/` ni `frontend/`: el Paso 9 exige que no existan.
- **Miembro del workspace.** Paquete `vectra-product` en `product-metrics/pyproject.toml`, con `vectra-contracts` y `vectra-common` (`prometheus-client` llega por `vectra-common`, que lo pinnea en 0.26.0; no se declara aparte). Agrégalo a `[tool.uv.workspace].members`, a `[tool.uv.sources]` y, editable, al grupo `dev` del `pyproject.toml` raíz, como U9 y U8; regenera `uv.lock`. Si al abrir el PR ya se fusionó otra tarea que tocó el workspace (U07-T04, U08-T03 o U03-T07 corren en paralelo), el orquestador fusiona `origin/main` y vuelve a correr `uv lock`.
- **Paquetes de prueba sin colisión** (`CANDIDATAS.md`, «Todas las unidades, paquetes de prueba», F-06 de U07-T03): **no** pongas `__init__.py` en `tests/`, `tests/unit/`, `tests/property/` ni `tests/integration/`. Usa `--import-mode=importlib` en `product-metrics/pytest.ini`, como `bias-monitoring/pytest.ini`, y nombres de archivo de prueba que no repitan los de otras unidades cuando eso cause un choque (`test_state_machine.py`, `test_reader.py` y `test_compute.py` hoy no chocan).
- **Semilla impresa también en verde** (NFR-U11-31; `CANDIDATAS.md`, «Todas las unidades (revisor, U07-T02): imprimir la semilla de Hypothesis también en las corridas verdes»): `product-metrics/tests/conftest.py` registra los perfiles `dev`, `ci` y `nightly` y fija e imprime la semilla en el encabezado de pytest, como `scoring-explainability/tests/conftest.py`.
- **Validación entrada por entrada (BR-U11-10).** `MetricsProjection` de U0 es un `StrictModel`: validar la página entera con él haría que una sola entrada con un `decision` desconocido tumbara la página, y BR-U11-10 exige excluirla y contarla. Por eso el `reader` valida el sobre de la página (`items` y `next_seq_after`) y entrega cada ítem crudo; `model` convierte cada ítem en una decisión compacta o en un marcador de inválida, con su `seq`, y `compute` cuenta las inválidas en `invalid_entries`. El `seq` de una inválida va solo al log (nunca a una etiqueta). Las inválidas también avanzan `last_seq`: no se vuelven a leer.
- **Reglas de exclusión (BR-U11-10), todas:** valor fuera del catálogo de U0 (`decision`, `used_factors`, `channel`, `outcome`, `actor_role`), `actor_role ≠ analista`, `decided_at > recorded_at + 5 min` y un campo obligatorio ausente. `degraded = invalid_entries / total > 0,01` sobre la ventana de 30 días.
- **Meses cerrados y la firma de `compute`.** Ver P-1. Con la recomendación, la función pura que pliega una decisión en los contadores de su mes vive en `compute` (sin E/S) y `state` la usa al leer cada página; `compute` recibe la instantánea de `state` (decisiones de 35 días y contadores de los 6 meses) y produce los cuatro periodos. PBT-U11-02 compara contra una recomputación completa sobre la unión, así que la equivalencia cubre también los meses.
- **Candado y ciclo omitido (P-U11-02).** El `asyncio.Lock` único vive en el `reader` (Paso 4). La lectura incremental **no espera** el candado: si está tomado, devuelve «omitida» sin leer. El `scheduler` (Paso 6, U11-T02) solo la llama y suma `vectra_product_cycles_skipped_total`. Así PBT-U11-02 puede intercalar pasadas completas e incrementales en esta tarea, sin el `scheduler`.
- **Cliente hacia U3.** El `reader` llama con `vectra_common.deps.call` (timeout de 5 s por página, sin reintentos dentro del ciclo, NFR-U11-09) y el token de servicio de `vectra_common.service_token` (cliente `product-metrics`, un solo scope `registry:read:metrics`, NFR-U11-20). En las pruebas, el doble de U3 acepta un token de prueba; ninguna prueba toca Keycloak.
- **Doble de U3** (`tests/doubles/`): implementa `GET /v1/entries` con `projection=metrics`, `entry_type`, `recorded_from`, `seq_after`, `limit` (≤ 1 000) y `next_seq_after`, con la recomendación resuelta dentro de cada `human_decision` (o `null`), con la misma forma que `decision-registry/src/vectra_registry/projections.py` (`_metrics`) y `contracts/.../models/registry.py` (`MetricsProjection`, `MetricsRecommendationRef`). Una prueba valida lo que sirve el doble contra `MetricsProjection` para que no diverja del contrato. Cuenta las conexiones simultáneas y falla si ve 2; puede inyectar fallos por número de página y latencia.
- **PBT-U11-07 y `publish`.** PBT-U11-07 («la suma de los conteos publicados por corte es igual al total `all`, y la razón total es `sum(numerador) / sum(denominador)`») se corre en esta tarea sobre la salida de `compute` (`BusinessMetrics`), que ya trae los conteos por corte y las razones de dos niveles. La comprobación sobre las series de `/metrics` llega con el `collector` (Paso 6, U11-T02). No es un recorte: es el reparto del plan. Lo mismo vale para PBT-U11-05, que es entera del Paso 6.
- **Pruebas de ejemplo del Paso 3** (business-logic-model §3, las que no dependen de E/S). Entran:
  - 10 decisiones (4 con vista y factores: 2 `sigue`, 1 `se_aparta`, 1 `resuelve_revision`; 3 vistas con `["ninguno"]`; 3 sin vista) → North Star 0,4 con desglose 2, 1, 1 (US-503);
  - un día sin decisiones → sin tasa publicada para ese día (no 0);
  - tasa de consulta de 0,5 con N = 50 durante 3 días seguidos y F = 0,6 → `days_below_floor = 3` (US-504; la parte «`RuidoExplicacion` dispara con S = 3» es `promtool`, Paso 12);
  - los mismos 3 días con 40 decisiones cada uno → la cuenta no suma;
  - un caso `manual`, con `attempt = 2` o descongelado con `attempt = 1` y `first_evaluation = false` → fuera del tiempo de originación;
  - `day` a las 10:00 UTC no incluye las decisiones de hoy; el 1 del mes no se publica `month_to_date` y `month` incluye el mes anterior completo, entre los 6 cerrados;
  - `decided_at` 3 min después de `recorded_at` → válida; 10 min después → excluida; `actor_role = cro` → excluida;
  - una entrada con `decision` desconocido → excluida, con `invalid_entries = 1`;
  - 2 % de entradas inválidas → `degraded = 1`;
  - y, de NFR-U11-11, una decisión del 30 de septiembre registrada el 5 de octubre cambia `month="2026-09"` en la recomputación del 6 de octubre (sobre `state` y `compute`, con reloj fijo).

  Quedan para U11-T02 (Pasos 6 y 7, dependen de E/S): reinicio a mitad, decisión sobre una recomendación de hace 60 días y referencia a una `freeze`, registro caído 31 min, allowlist de `/metrics`. Quedan para U11-T03 (Pasos 12 y 13): `gen_rules.py --check`, `promtool` y dashboard.
- **Parámetros fuera de rango** (BR-U11-09, domain-entities §4): 0 < F < 1, 1 ≤ S ≤ 14, N ≥ 30, `target_complete_response`, `target_origination_ratio` y `target_sustained_ratio_month6` entre 0 y 1, `target_origination_hours` > 0, `target_north_star` `null` o entre 0 y 1. `params.py` carga el archivo y falla al arrancar si un valor sale de rango. La regla de `conftest` con los mismos rangos es del Paso 11.
- **`make -C product-metrics check`.** Corre en orden lint (`ruff check` y `ruff format --check`), mypy en modo estricto sobre `vectra_product`, import-linter, las pruebas con el perfil `ci` (semilla impresa) y la cobertura del 100 % del Paso 5. Termina en 0. No corre `-m volume` (Paso 7, diferido).
- **Plan.** Marca `[x]` los Pasos 1 a 5 con `(U11-T01)`; en el Paso 5, la nota «`mutmut` diferido por la demo (T3)».

**Fuera** (recházalo aunque lo veas roto o tentador):

- **`mutmut` del Paso 5** sobre `compute` y `noise`, y la parte de NFR-U11-30 que lo pide. Recorte E\*F: enmienda §3, U11, fila «5»: «Sin `mutmut` (T3)»; y §2 regla 3, que nombra «U11 Pasos 5 y 7». `mutmut` ya está en el grupo `dev` de la raíz; no hace falta agregarlo.
- Bloques C a G de U11 (Pasos 6 a 18): `scheduler`, `collector`, `main`, `/metrics` y `/readyz`, PBT-U11-05, la prueba de volumen, la imagen, el chart (salvo `values-product-metrics-policy.yaml`), `gen_rules.py`, reglas y alertas, dashboards, runbooks, workflow, Application, README y cierre. Los módulos `scheduler.py`, `collector.py` y `main.py` quedan vacíos.
- La línea de `CODEOWNERS` (ya existe en `main`: `**/values-product-metrics-policy.yaml`) y los flujos F28, F50 y F60 (ya están en `platform/network/flows.yaml`): no se tocan.
- El cliente `product-metrics` de Keycloak (U2) y su `ExternalSecret` (Paso 11).
- Cambios a U0, a U1 o a U3. Si `MetricsProjection` o la proyección de U3 no encajan con lo que pide U11, se reporta como candidata, no se arregla aquí.

---

## Preguntas

- **P-1 — Meses cerrados y la firma `compute(entries, params, now)`.** El Paso 3 pide que `compute` produzca los 6 `month`, pero el Paso 4 y NFR-U11-12 dicen que los meses cerrados **no** viven como entradas: `state` los pliega en contadores y solo guarda 35 días. Con solo 35 días de entradas, `compute` no puede calcular los meses.
  - (a) **Recomendada.** La función de plegado (decisión → contador de su mes y cortes) es pura y vive en `compute`; `state` la usa al leer y entrega a `compute` una instantánea con las decisiones de 35 días y los contadores de los 6 meses. La firma queda `compute(snapshot, params, now)` (con `entries` = la instantánea). PBT-U11-01/03/07 se corren sobre instantáneas generadas plegando entradas generadas, y PBT-U11-02 cubre la equivalencia incremental frente a completa, meses incluidos.
  - (b) `compute` recibe todas las entradas de los 6 meses y se pliega en cada ciclo. Contradice NFR-U11-12 y P-U11-04 (memoria), así que no se recomienda.
  - Si no hay respuesta, rige (a), y el codificador anota en `logic.md` la firma real.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/product-metrics-code-generation-plan.md` (§1, Bloques A y B, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1 D4, §2, §3 U11, §4, §8)
- `aidlc-docs/construction/product-metrics/functional-design/business-rules.md` (BR-U11-01..11)
- `aidlc-docs/construction/product-metrics/functional-design/domain-entities.md` (§1 a §4)
- `aidlc-docs/construction/product-metrics/functional-design/business-logic-model.md` (§2.2, §2.3 y §3: PBT-U11-01..04, 06, 07 y pruebas de ejemplo)
- `aidlc-docs/construction/product-metrics/nfr-requirements/nfr-requirements.md` (NFR-U11-01, 02, 04, 09..12, 20, 21, 30, 31) y `tech-stack-decisions.md`
- `aidlc-docs/construction/product-metrics/nfr-design/nfr-design-patterns.md` (P-U11-01, 02, 04)
- `contracts/python/vectra_contracts/src/vectra_contracts/models/registry.py` (`EntryFilter`, `MetricsProjection`, `MetricsRecommendationRef`) y `models/api.py` (`Page`, `next_seq_after`)
- `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` (catálogos y códigos)
- `contracts/python/vectra_common/src/vectra_common/deps.py` (`BreakerConfig`, `CircuitBreaker`, `call`) y `service_token.py`
- `decision-registry/src/vectra_registry/projections.py` (`_metrics`, `_recommendation_ref`) y `queries.py` (paginación por `seq`)
- `bias-monitoring/pyproject.toml`, `bias-monitoring/Makefile`, `bias-monitoring/pytest.ini`, `bias-monitoring/coveragerc`, `bias-monitoring/.importlinter` y `scoring-explainability/tests/conftest.py` como ejemplo de miembro del workspace y de semilla impresa
- `CANDIDATAS.md` (entradas «Todas las unidades, paquetes de prueba» y «Todas las unidades (revisor, U07-T02)»)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`.

- [ ] **CA-1** — Esqueleto, dependencias y contratos de imports (Paso 1; NFR-U11-21).
  ```bash
  uv sync --frozen && uv run lint-imports --config product-metrics/.importlinter
  ```
  Esperado: código 0, con los contratos del Paso 1 listados como `KEPT` (`compute`, `noise` y `model` sin E/S; `httpx` solo vía `vectra_common.deps`; sin FastAPI). **Rojo primero:** un `import httpx` en `compute.py`, un `import asyncio` en `noise.py` y un `import fastapi` en `state.py` hacen fallar cada uno su contrato; regístralo antes de dejar los contratos. Sobre `main` hoy: `Could not find product-metrics/.importlinter.`, código 1.

- [ ] **CA-2** — Estructura completa de §1, sin `migrations/` ni `frontend/`.
  ```bash
  cd product-metrics && for p in Makefile pyproject.toml .importlinter pytest.ini coveragerc src/vectra_product/config.py src/vectra_product/params.py src/vectra_product/model.py src/vectra_product/compute.py src/vectra_product/noise.py src/vectra_product/state.py src/vectra_product/reader.py src/vectra_product/scheduler.py src/vectra_product/collector.py src/vectra_product/main.py tools chart/templates chart/values-product-metrics-policy.yaml policies/conftest observability/rules/tests observability/runbooks observability/dashboards tests/unit tests/property tests/integration tests/doubles tests/volume; do test -e "$p" || echo "FALTA $p"; done; test ! -d migrations && test ! -d frontend && ! find tests -name __init__.py | grep -q . && echo OK
  ```
  Esperado: ninguna línea `FALTA` y `OK` al final (también comprueba que no hay `__init__.py` en `tests/`).

- [ ] **CA-3** — Constantes y parámetros (Paso 2; BR-U11-09, 11; NFR-U11-04, 09; P-U11-01, 02).
  ```bash
  uv run pytest product-metrics/tests/unit/test_config.py product-metrics/tests/unit/test_params.py -v
  ```
  Esperado: pasan los valores de la tabla del Paso 2 (cada uno por su nombre, incluido el `BreakerConfig` con `consecutive_failures=3`, `open_for=60`, `close_after=1`, que se construye sin error con `vectra_common.deps`); ninguna constante se lee de variables de entorno (la prueba cambia el entorno y comprueba que nada cambia, además de buscar `os.environ` y `getenv` en `config.py` y `params.py`); un archivo con un valor fuera de **cada** rango de BR-U11-09 falla la carga; el `chart/values-product-metrics-policy.yaml` real carga F = 0,6, S = 3, N = 50 y los targets de domain-entities §4, con `target_north_star` nulo. **Rojo primero:** con `noise_min_decisions: 20` la carga debe fallar; regístralo antes de escribir la validación. Sobre `main` hoy: `file or directory not found`, código 4.

- [ ] **CA-4** — `model`, `compute` y `noise`: PBT-U11-01, 03, 04, 06 y 07 y las pruebas de ejemplo (Paso 3; BR-U11-01..10; US-503, 504, 505).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/property/test_compute.py product-metrics/tests/property/test_noise.py product-metrics/tests/unit/test_compute_examples.py -v
  ```
  Esperado: todos pasan; el encabezado muestra el perfil `ci` y la semilla; la salida muestra una prueba por PBT (01, 03, 04, 06, 07) y un caso por cada ejemplo de «Pruebas de ejemplo del Paso 3» de las Precisiones. Los oráculos de PBT-U11-01, 04 y 06 cuentan **por definición** (BR-U11-03, 04, 05, 07), no reusan `compute`. **Rojo primero:** contar en el numerador de la North Star una decisión con `used_factors = ["ninguno"]`, o dejar entrar al tiempo de originación un caso con `attempt = 1` y `first_evaluation = false`, hace fallar PBT-U11-01 o PBT-U11-06 y su ejemplo; regístralo.

- [ ] **CA-5** — `state` y `reader`: PBT-U11-02 y el `reader` con el doble de U3 (Paso 4; BR-U11-11; P-U11-01, 02, 04; NFR-U11-01, 02, 09..12).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/property/test_state_machine.py product-metrics/tests/integration/test_reader.py -v
  ```
  Esperado: pasan PBT-U11-02 (stateful: lotes arbitrarios por `seq`, pasadas completas intercaladas con incrementales que se omiten mientras la pasada lee, fallos a mitad de la pasada, lectura incremental posterior desde el `last_seq` de la pasada; el resultado es igual a una recomputación completa sobre la unión, meses incluidos) y un caso por cada viñeta del Paso 4: el doble falla si ve 2 conexiones simultáneas; fallo en la página 3 de 5 → `last_seq` queda en la página 2 y la siguiente lectura sigue desde ahí; 3 fallos seguidos → breaker abierto; 1 éxito en semiabierto → cerrado; una entrada de 40 días va a su contador de mes y no al estado de 35 días; una incremental con el candado tomado vuelve «omitida» sin leer. Otra prueba valida lo que sirve el doble contra `MetricsProjection`. **Rojo primero:** avanzar `last_seq` antes de confirmar la página, o dejar que la incremental espere el candado, hace fallar PBT-U11-02 o el caso de la página 3; regístralo.

- [ ] **CA-6** — Cobertura de ramas del 100 % en `compute` y `noise`, y resumen (Paso 5; NFR-U11-30, 31).
  ```bash
  uv run pytest product-metrics/tests/unit product-metrics/tests/property --cov=vectra_product.compute --cov=vectra_product.noise --cov-branch --cov-fail-under=100 && grep -nE "compute|days_below_floor|mutmut" aidlc-docs/construction/product-metrics/code/logic.md
  ```
  Esperado: código 0, con `TOTAL … 100%` sobre esos dos módulos (no sobre U0); `logic.md` existe, describe la firma real de `compute` (P-1), el plegado de los meses y `days_below_floor`, y dice que `mutmut` está diferido por la demo.

- [ ] **CA-7** — `check` de la unidad (RL-4) y de U1, porque el diff toca el workspace.
  ```bash
  make -C product-metrics check && make -C platform check
  ```
  Esperado: código 0 en los dos, corridos **en serie**, con `uptime` antes y después de cada uno en la bitácora. El de U11 incluye lint, mypy, import-linter, las pruebas con el perfil `ci` y la cobertura del 100 %. Sobre `main` hoy: `make: *** product-metrics: No such file or directory.  Stop.`, código 2.

- [ ] **CA-8** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso [1-5] " aidlc-docs/construction/plans/product-metrics-code-generation-plan.md && git diff origin/main -- aidlc-docs/construction/plans/product-metrics-code-generation-plan.md | grep -E "^[-+]- \[" 
  ```
  Esperado: los Pasos 1 a 5 en `[x]` con `(U11-T01)`, el 5 con la nota de `mutmut`; ningún otro paso cambia.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/conftest.py`: perfiles `dev`, `ci` y `nightly`, y la semilla fija e impresa en el encabezado.
- `tests/unit/test_config.py` y `tests/unit/test_params.py`: los casos del Paso 2 y la carga del archivo real.
- `tests/property/test_compute.py`: PBT-U11-01, 03, 06 y 07, con los generadores del business-logic-model §3 (todas las combinaciones de `decision`, `used_factors`, `explanation_viewed_before`, `channel`, `outcome`, `attempt` y referencias válidas o nulas; permutaciones, duplicados por `seq` y `recorded_at` hasta 24 h después del momento de negocio).
- `tests/property/test_noise.py`: PBT-U11-04 contra un oráculo que recorre los días.
- `tests/unit/test_compute_examples.py`: los ejemplos de las Precisiones.
- `tests/property/test_state_machine.py`: PBT-U11-02 (`RuleBasedStateMachine`) con el doble de U3.
- `tests/integration/test_reader.py`: las viñetas del Paso 4 y la validación del doble contra `MetricsProjection`.
- `tests/doubles/`: el doble de U3.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U11-T01.md`, como mínimo los de CA-1, CA-3, CA-4 y CA-5. El par falla-pasa es la prueba.

---

## Notas

- Archivos que se **modifican en su sitio**: `pyproject.toml` raíz, `uv.lock` y `aidlc-docs/construction/plans/product-metrics-code-generation-plan.md` (casillas de los Pasos 1 a 5). Nada de duplicados con sufijo.
- Archivo nuevo de documentación que pide el plan: `aidlc-docs/construction/product-metrics/code/logic.md`.
- **Bitácora** `bitacoras/U11-T01.md`: la salida real de cada comando, pegada, con rutas absolutas a los logs largos y **sin plantillas sin expandir** (`CANDIDATAS.md`, «Bitácoras», F-07 de U09-T04 y F-12 de U03-T06). Incluye la semilla de cada corrida con Hypothesis.
- **Máquina compartida:** corre los `make check` en serie, nunca en paralelo, con `uptime` antes y después; usa una carpeta propia en el scratchpad para logs y temporales. Si una corrida pasa de 2 horas sin avanzar, detenla, anótalo y repítela.
- PBT-U11-01..07 nunca se recortan. En esta tarea entran las seis de los Bloques A y B (01, 02, 03, 04, 06 y 07); PBT-U11-05 es del Paso 6.
- U11 no tiene datos propios: no hay migraciones, ni base de datos, ni nada que limpiar en kind.
