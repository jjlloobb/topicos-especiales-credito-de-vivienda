# U09-T02 — Lógica del CronJob de `bias-monitoring`: `window`, `freeze_rule`, `context`, clientes, `publish` y `run`

**Unidad:** U9 `bias-monitoring`
**Historias que implementa:** US-302 (Paso 8), US-303 (Pasos 6 y 8), US-304 (Paso 6, el paquete) y US-308 (Paso 8).
**Depende de:**
- U09-T01 (librería `vectra_disparity` con `aggregate_lower_limit` y `Z_FREEZE`, `config.py`, simulación), en `main`;
- en `main`, como contratos de los dobles: U0 (§9.4 de `monitoring.py`, `REGISTRY`, `deps`, `process`, `service_token`, `canonical`, `LogEvent`), U3 (`POST /v1/monitoring/daily:query` y `GET /v1/monitoring/freezes`), U4 (`POST /v1/models/{id}/freeze` con su 409 y la reducción por tamaño de 60/64 KiB) y U5 (conteos de `tests/doubles/u5_counts.json`, variante proxy de 25,41 pp).

**Se despacha** cuando este archivo esté en `main`. Puede correr en paralelo con otras unidades (RL-5). U09-T03 (Bloque D) usa `registry_client` y espera a esta tarea.
**Rama:** `tarea/U09-T02`, desde `origin/main`.

Bloque C del plan de U9 (`aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md`), Pasos 6, 7 y 8. Es la tarea «C» de `demo-recorte-funcional.md` §4 y §8. **No** se junta con el Bloque D: §4 dice «U9 C con D (cuatro PBT compuestas)» entre los bloques que no conviene juntar (RL-2).

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 6 `window`, `freeze_rule` y `context` | **E** | Completo, con PBT-U9-04 y 08. `freeze_rule` aplica R4 a **todos los atributos** (decisión F-03 (b), abajo) | Enmienda §3 U9, fila «1–4, 6–8»; §5.1, fila «`window` de U9» |
| 7 `registry_client`, `freeze_client` y `publish` | **E** | Completo, con la cláusula de `publish` de PBT-U9-03 | Enmienda §3 U9, fila «1–4, 6–8»: «`publish` y la población humana entran por PBT-U9-05 y P-U9-01» |
| 8 `run` | **E** | Completo, con PBT-U9-05, E1, E3, E4, E5 y E7 con dobles, y la prueba de duración y memoria con dobles | Enmienda §3 U9; §5.1, fila «Agregador de U3» |

Nada de los Pasos 6 a 8 se difiere. Lo que queda fuera es de otros pasos: el Paso 10 (cobertura de `vectra_bias` y `mutmut`, Bloque D y T3), el Paso 15 (D, T4) y el Paso 16 (consolidado en U12 Paso 18, enmienda §8). El cierre de U9 va en U09-T04, la última tarea de código (enmienda §8).

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09.

---

## Decisión del usuario que esta tarea aplica: F-03, opción (b) (2026-11-10)

Origen: hallazgo F-03 de `revisiones/U09-T01/ronda-3.md`; quedó abierto en `revisiones/U09-T01/arbitraje-ronda-3.md`, decisión 3 («Se decide antes del Bloque C de U9»); candidata en `CANDIDATAS.md` («U9, `freeze_rule` / BR-U9-11 (revisor, U09-T01, ronda 3, F-03)»).

- **Regla.** R4 se evalúa sobre **todos los atributos**, no solo sobre el disparador. Una versión evaluada se congela si **algún** atributo con agregada tiene `aggregate_lower_limit` (con `Z_FREEZE`) **> umbral** (5 pp).
- **Razón.** La z de Bonferroni ya corrige por todas las comparaciones de pares × atributos, así que evaluar los cuatro atributos sigue cubierto.
- Si todas las agregadas son «muestra insuficiente», no congela (sin cambio). La población `humana` nunca congela (sin cambio; solo `rule_met` y la alerta).
- **El caso que lo motiva** (F-03, reproducido con la librería al preparar esta tarea):
  - `region`: 6 grupos, 5 con tasa 0,50 y 1 con 0,70, 40 casos por celda en las 3 bandas → agregada 0,2000, límite R4 **0,0132**;
  - `sexo`: F 0,50 y M 0,60, 3 000 casos por celda en las 3 bandas → agregada 0,1000, límite R4 **0,0768**;
  - el disparador (BR-U9-05) es `region`. Con la regla de solo el disparador **no** congela. Con (b) congela por `sexo`.

---

## Alcance

**Dentro:** los Pasos 6 a 8 del plan, con su texto y su aceptación. Léelos allí. Precisiones:

### Paso 6 — `window`, `freeze_rule` y `context` (E)

**`window`** (BR-U9-08):
- Inicio de la ventana de cada versión = el más tardío entre el primer día con datos (`versions` de `MonitoringWindow`) y el **día siguiente (fecha UTC)** al `recorded_at` de su **última** `reactivar` (de `FreezeRecord.resolutions`, con `investigar` y luego `reactivar` como dos resoluciones; BR-U9-19).
- Versiones evaluadas para congelar: las que tienen recomendaciones hoy o ayer (BR-U9-08).
- Rangos por versión (4, BR-U9-15 y domain-entities §1.2): `antes`, `después` y `últimos 7 días` de `modelo`, y `después` de `humana`. Todos respetan el inicio de la ventana. Con menos de 7 días de datos, `antes` es `sin_datos`.
- Los rangos salen de `window_days` de la política (`config.MonitoringPolicy`), no de un 30 escrito a mano. Con `window_days = 30` dan exactamente los de BR-U9-15: `antes` de hoy − 36 a hoy − 7, `después` de hoy − 29 a hoy, `últimos 7 días` de hoy − 6 a hoy.
- Pura: recibe «hoy» como argumento; no lee el reloj.

**`freeze_rule`** (BR-U9-11 enmendada, PBT-U9-04):
- `decide(...) -> FreezeDecision`, pura. El plan escribe `decide(result, threshold)`. La firma exacta es tuya, con estas condiciones:
  - recibe la población, el umbral en pp y, por atributo, el límite R4 ya calculado con `vectra_disparity.aggregate_lower_limit` (z = `Z_FREEZE`) sobre los **mismos** conteos que dieron el `AttributeResult`. **No** reimplementes la fórmula del límite;
  - compara en la escala de la librería: `threshold_pp / 100` (`library.md`, «Escala»);
  - `freeze` ⇔ población `modelo` **y** algún atributo con límite > umbral. La población `humana` nunca da `freeze`, pero sí informa si cumple la regla (para `vectra_bias_rule_met{population="humana"}`, BR-U9-14).
- `FreezeDecision` (domain-entities §2.6): `freeze`, `reason` y, además, los atributos que cumplieron la regla con su límite, ordenados del mayor límite al menor. Motivos con R4: `supera_umbral` (algún límite > umbral), `muestra_insuficiente` (todas las agregadas insuficientes), `intervalo_incluye_cero` (el mayor límite ≤ 0) y `bajo_umbral` (0 < mayor límite ≤ umbral). Escríbelo en §2.6 al enmendar.

**`context`** (BR-U9-15, PBT-U9-08):
- `build_context_package(...) -> FreezeContext` de U0 (`contracts/python/vectra_contracts/src/vectra_contracts/models/monitoring.py`), pura sobre los tres `DisparityResult`.
- Lleva los cinco parámetros de la política y `library_version = vectra_disparity.__version__` (NFR-U9-54).
- `trigger_attribute` sigue siendo el de BR-U9-05: el de la mayor agregada (el mismo que `after.trigger_attribute`).
- **Atributos que cumplieron la regla y su límite.** U0 no tiene un campo propio para esto. `FreezeContext` es `StrictModel` (`extra="forbid"`) y `trigger_attribute` es un solo `Attribute`. El único lugar es `implicated: list[JsonValue]`. Cada elemento de `implicated` es un objeto por atributo que cumplió R4:
  - `attribute`;
  - `freeze_lower_limit`, en forma `Decimal4` (cadena);
  - `bands`: las bandas de ese atributo cuya diferencia supera el umbral, con `band`, `difference` y `extreme_pair`.

  Así se conserva el sentido de BR-U9-15 («grupos y bandas implicados») y se agrega el atributo y su límite. Escríbelo en domain-entities §3.1 y en BR-U9-15 al enmendar.
- ≤ 48 KiB en JCS (`vectra_contracts.canonical.canonicalize`). Si no cabe, quita en orden las celdas de `before`, las de `last_7_days` y las de `after`; conserva siempre las agregadas, las bandas, `trigger_attribute` e `implicated`, y marca `truncated = true` (BR-U9-15). El `freeze` nunca espera por el tamaño.
- Nunca la tasa de una celda insuficiente ni la tasa sin bandas de un grupo con alguna celda insuficiente (BR-U9-06; NFR-U9-31).
- Diseño: BR-U9-08, 11, 14, 15. Historias: US-303, US-304.

**Aceptación del plan y su compatibilidad con R4.** La línea del plan dice «con 40 casos por celda y 6 pp → sin `freeze`; con 2 000 casos y 6 pp → `freeze`». La primera mitad vale con R4 y con (b). **La segunda no**: con 2 000 casos por celda y 6 pp el límite R4 es 0,0315 (medido con la librería al preparar esta tarea), así que no congela, con la regla de solo el disparador ni con (b). La BLM §3 ya lo corrigió con R4 (arbitraje de la ronda 2 de U09-T01, 2026-11-09): «con 2 000 casos por celda y 6 pp, también (≈ 3,1 pp); con 2 000 casos por celda y 12 pp → `freeze`». `library.md` lo repite («Cobertura y margen»). Esta tarea sigue la BLM: 40 y 6 pp → sin `freeze`; 2 000 y 6 pp → sin `freeze`; 2 000 y 12 pp → `freeze`. No cambies el texto del plan; anótalo en la bitácora.

### Paso 7 — `registry_client`, `freeze_client` y `publish` (E)

- `registry_client`:
  - `GET /v1/monitoring/freezes` y `POST /v1/monitoring/daily:query` con los tipos de U0 (`MonitoringQuery`, `MonitoringWindow`, `FreezeRecord`);
  - solicitudes de ≤ 12 rangos; con más de 3 versiones, varias solicitudes, sin omitir ninguna; `unattributable_range` = la ventana de la corrida **solo** en la primera (BR-U9-09; domain-entities §1.2);
  - en el CronJob, `DependencyClient(breaker="disabled")` tras `process.init("batch")`. En el servicio (Bloque D) será con breaker: deja el constructor listo para las dos formas (P-U9-02);
  - timeouts de `config.py` (3 s y 5 s).
- `freeze_client`: solo `POST /v1/models/{id}/freeze`, con el token de `bias-monitoring-job` (`vectra_common.service_token`), timeout de 3 s y 3 reintentos a 1, 2 y 4 s ante timeout, error de conexión o 5xx. Un 409 es éxito para la corrida, sin reintento. Otro 4xx: sin reintento y `freeze` fallido (NFR-U9-22: «sin reintentos fuera de ese caso»).
- `publish`:
  - grupos `run` y `success` con `PUT`; `success` solo en corridas completas (BR-U9-20);
  - grupo `freeze-<model_version_id>` con `PUT` al fallar el `freeze`; `DELETE` con un `freeze` exitoso o 409, o en una corrida **completa** en la que la versión ya no cumple la regla o ya no se evalúa;
  - lista de grupos con `GET /api/v1/metrics` y hasta 16 `DELETE` por corrida (`MAX_STALE_GROUP_DELETES`); cada operación corta a los 5 s; ningún `DELETE` toca un grupo de otro `job`;
  - todas gauges; una celda insuficiente publica solo `vectra_bias_cell_size`, nunca una tasa (PBT-U9-03, cláusula de `publish`; T01 la dejó para este paso);
  - `vectra_bias_aggregate_lower{model_version_id, population, attribute}` publica el **límite R4** de cada atributo, que es el que decide con (b). Escríbelo en BR-U9-20 al enmendar.
- Ningún módulo de `vectra_bias` importa `httpx` (contrato de import-linter): `vectra_common.deps.call` devuelve la respuesta. Las pruebas usan `transport=httpx.MockTransport` en el `DependencyClient`.
- Diseño: BR-U9-07, 12, 20; P-U9-01, 02, 05; NFR-U9-03, 22.

### Paso 8 — `run`: la corrida completa (E)

- Orden de P-U9-01: token → lectura (atraso del agregador e inválidas) → cálculo de **todas** las versiones evaluadas → `freeze` en **todas** las que cumplan la regla (b), aunque falle una → publicación.
- Motivos de falla: `lectura`, `libreria`, `invalidas`, `agregador_atrasado`, `token` y `freeze` (BR-U9-20). Razón de inválidas de BR-U9-09, con `unattributable_invalid` contado una sola vez en el numerador y en el denominador.
- Decisiones humanas con `final_outcome` y tasa de apartamiento (BR-U9-14); su regla es la misma (b) y nunca llama a `freeze`.
- `python -m vectra_bias.run` arranca la corrida (punto de entrada de P-U9-05). Las URL y la llave del cliente llegan por el entorno o por archivo montado, como fije el chart (Paso 12). **No** las pongas en `config.py`: su prueba de U09-T01 busca `os.environ` y `getenv` allí.
- Logs de la corrida solo con los campos de `LOG_RECORD_FIELDS` de U0 (`catalog.py`); las inválidas, solo con `seq` (BR-U9-09; NFR-U9-33). Si te falta un campo, **detente y repórtalo**.
- Código de salida: Pushgateway caído → distinto de cero (BR-U9-20). Para una corrida fallida por otra causa, elige y anota en la bitácora.
- Diseño: BR-U9-08..14, 20; P-U9-01, 07; NFR-U9-01, 20, 21. Historias: US-302, US-303, US-308.

### Enmienda de diseño (F-03 (b), 2026-11-10)

Cada cambio lleva «(F-03 opción (b), decisión del usuario del 2026-11-10)». Archivos, en su sitio:

- `aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md`:
  - **BR-U9-11**: la regla pasa a «**algún** atributo con límite R4 > umbral». Conserva la historia (R0 → R4 del 2026-11-09 → (b)). **Corrige la cuenta de F-04** en el mismo párrafo: las comparaciones reales son 46 (1 + 15 + 15 + 15), con cuantil 3,065; 60 (15 pares × 4 atributos) es una cota, así que `Z_FREEZE = 3,14` se mantiene por conservador. Cambia la línea de D\* con las cifras nuevas (Paso «Re-medición», abajo);
  - **BR-U9-05**: quita «el límite de congelamiento se calcula sobre ese atributo»; el disparador sigue siendo el de la mayor agregada y es el que muestra el paquete;
  - **BR-U9-15**: `implicated` con el atributo y su límite;
  - **BR-U9-20**: `vectra_bias_aggregate_lower` es el límite R4 por atributo.
- `aidlc-docs/construction/bias-monitoring/functional-design/business-logic-model.md`:
  - §2.1, el diagrama (nodo `rule`, línea 35) y la alternativa en texto (línea 70);
  - §3, la fila de PBT-U9-04, el ejemplo RT-2, el ejemplo «intervalo (regla R4, 2026-11-09)» y la «Validación estadística».
- `aidlc-docs/construction/bias-monitoring/functional-design/domain-entities.md`: §2.6 (`FreezeDecision`) y §3.1 (`implicated`).
- `aidlc-docs/construction/bias-monitoring/code/library.md`: la fila de `aggregate_lower_limit` («sobre el atributo disparador»), la regla medida, las tablas de las condiciones y D\*.
- Comentario de `Z_FREEZE` en `bias-monitoring/disparity/src/vectra_disparity/stats.py` (líneas 15–16): la cuenta de 46 y 60. Solo el comentario: **no** cambies `Z_FREEZE` ni la versión de la librería.
- `aidlc-docs/audit.md`: una entrada al final (solo anexar) con la enmienda y su origen.

La palabra «disparador» puede seguir en el texto donde describe BR-U9-05 o la historia de la regla. No puede quedar como la condición de congelamiento vigente.

### Re-medición con la regla (b) (obligatoria)

En `bias-monitoring/tests/simulation/test_statistical_validation.py`, con la librería real, 10 000 repeticiones y sin `xfail`:
- `_freezes` pasa a usar `vectra_bias.freeze_rule` (resuelve la candidata «U9, `freeze_rule` (Bloque C)»). La simulación no reimplementa la regla;
- **rojo primero contra la regla de solo el disparador**: corre la simulación con esa regla y después con (b), con la misma semilla. Las dos columnas van a `library.md`;
- **condición 1**: congelamientos falsos con disparidad real 0, con 30, 100, 500 y 2 000 casos por celda; **≤ 5 % con ≥ 500**;
- **condición 2**: el modelo base de U5 (`u5_counts.json`, 4,61 pp) congela **≤ 5 % con 50 a 100 casos por celda** y **≤ 6 % con 30**, que es lo que documenta `library.md`;
- **condición 3**:
  - la variante proxy **actual** de U5 (`u5_counts.json`, 25,41 pp; t = 1 de `synthetic_variant`) congela **≥ 95 %** con el lote `stratified` (`_stratified_cell`);
  - recalibra D\* con la variante nueva: `DSTAR_T = 1,71` se calibró con el proxy anterior y hoy extrapola a 37,7 pp (candidata «U9, `DSTAR_T` (codificador, U05-T05)»). Busca la t del cruce del 95 % con (b), fija `DSTAR_T` y documenta D\* en pp (agregada de la librería) en `library.md` y en BR-U9-11. Deja el script de búsqueda en `revisiones/U09-T02/busqueda-dstar.py`, como `revisiones/U09-T01/busqueda-dstar-ronda-3.py`;
- **enmascaramiento de F-03**: un caso determinista con los conteos exactos de la decisión (arriba). Con (b) congela por `sexo`; con la regla de solo el disparador no. Va en las pruebas del Paso 6 (CA-2), no en la simulación: una simulación de ese caso no lo muestra limpio, porque la elección del par extremo con 40 casos infla el límite de `region`.

**Si alguna condición falla con (b), detente y repórtalo.** No ajustes la regla, la z ni los tamaños: decide el usuario.

### Plan y candidatas

- Marca `[x]` los Pasos 6, 7 y 8 con `(U09-T02)`. No cambies el texto del plan.
- En `CANDIDATAS.md`, marca como resueltas por U09-T02, con una línea de cómo: «U9, `freeze_rule` (Bloque C)», «U9, `freeze_rule` / BR-U9-11 … F-03», «U9, `business-rules.md` BR-U9-11 … F-04» y «U9, `DSTAR_T`». Agrega estas:
  - **U4**, `governance/validation_job/vectra_validation/disparity.py` (`initial_disparity`): `rule_met` aplica R4 solo sobre el disparador; con (b) debe usar todos los atributos (U4);
  - **U5**, `reference-model/tests/simulation/test_r4_freeze_rate.py`: además de usar `freeze_rule`, la regla vigente es (b). Amplía la entrada que ya existe; no crees otra.

**Fuera** (recházalo aunque lo veas roto o tentador):

- Que `reference-model/tests/simulation/test_r4_freeze_rate.py` use `freeze_rule`. Es candidata de U5 (`CANDIDATAS.md`, «U5, `reference-model/tests/simulation/test_r4_freeze_rate.py` (revisor, U05-T05, ronda 1, AMARILLO)»). Queda fuera salvo que el usuario lo pida. No toques `reference-model/`.
- Alinear `rule_met` del `model-validation-job` de U4 con (b). Es U4: va como candidata.
- El modelo base sobre `test` (5,51 pp; `CANDIDATAS.md`, «U5/U9, modelo base sobre `test`») y el margen de 0,39 pp (BR-U5-06). Son de U5 y de U12. Si la re-medición te da algo nuevo sobre ese riesgo, anótalo en la bitácora.
- Los pares de Newcombe de `test_stats.py` (candidata de U09-T01, ronda 1, F-03), `ACTIVE_DEADLINE_SECONDS` (Paso 12) y `combined_variance` (anotada, sin acción).
- El Paso 10: cobertura de `vectra_bias` (`coveragerc` mide solo `vectra_disparity`) y `mutmut` en `freeze_rule` (NFR-U9-51; T3, enmienda §2 regla 3). Es del Bloque D.
- El servicio HTTP (Paso 9), el chart y sus `ConfigMap`, el `Dockerfile`, las alertas y la verificación en kind (Pasos 9 a 16).
- Cambios a U0, U3, U4 o U5. No cambies `Z_FREEZE`, `aggregate_lower_limit` ni la API de la librería.
- `mutmut`, k6 o cualquier carga (T3), y toda orden contra el clúster (AUTONOMIA-01).

---

## Archivos de contexto

- `aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md`: §1 (estructura, dobles, AUTONOMIA-01), Bloque C (Pasos 6 a 8), §3.
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1.2 (cadena de D2), §2, §3 U9, §4, §5.1 (filas de `window`, agregador y librería), §5.2, §6 (P-14) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md` §2 y §6; `DECISIONES-LOOP.md` §6 con su enmienda.
- `aidlc-docs/construction/bias-monitoring/functional-design/`: `business-rules.md` (BR-U9-05, 07 a 15, 20), `business-logic-model.md` (§2.1, §3: PBT-U9-03, 04, 05, 08, ejemplos y validación estadística) y `domain-entities.md` (§1.2, §1.3, §2.5 a §2.7, §3.1).
- `aidlc-docs/construction/bias-monitoring/nfr-requirements/nfr-requirements.md` (NFR-U9-01, 03, 04, 20, 21, 22, 31, 33, 54); `nfr-design/nfr-design-patterns.md` (P-U9-01, 02, 04, 05, 07) y `nfr-design/logical-components.md`.
- `aidlc-docs/construction/bias-monitoring/code/library.md`.
- `revisiones/U09-T01/arbitraje-ronda-2.md`, `ronda-3.md` (F-03, F-04, F-05) y `arbitraje-ronda-3.md`.
- `bias-monitoring/`: `disparity/src/vectra_disparity/` (`disparity.py`: `aggregate_lower_limit`, `model_aggregate`, `to_dict`; `stats.py`: `Z_FREEZE`), `src/vectra_bias/config.py`, `.importlinter`, `Makefile`, `pytest.ini`, `tests/simulation/test_statistical_validation.py` y `tests/doubles/u5_counts.json`.
- `contracts/python/vectra_contracts/src/vectra_contracts/`: `models/monitoring.py` (`MonitoringQuery`, `MonitoringWindow`, `FreezeRecord`, `DisparityResult`, `FreezeContext`), `routes/__init__.py` (las tres rutas y sus scopes), `canonical.py` y `catalog.py` (`LogEvent`, `LOG_RECORD_FIELDS`).
- `contracts/python/vectra_common/src/vectra_common/`: `deps.py`, `process.py` y `service_token.py`.
- `decision-registry/src/vectra_registry/queries.py` y `api.py` (las dos lecturas); `governance/src/vectra_governance/api.py` (`freeze`) y `evidence.py` (`fit_freeze_package`: 60/64 KiB y vaciado de `implicated` como último recurso).
- `contracts/openapi/decision-registry-service.yaml` y `governance-service.yaml` (formas HTTP de los dobles).
- `CANDIDATAS.md`: las entradas de U9 y las de U5 citadas arriba.

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster. Los dobles HTTP de U3, U4, Keycloak y el Pushgateway viven en `bias-monitoring/tests/doubles/` y siguen los contratos de `vectra_contracts`. El plan escribe varias rutas relativas a `bias-monitoring/`; aquí van completas.

- [ ] **CA-1** — Paso 6: `window` y las PBT del paso.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_freeze_rule.py bias-monitoring/tests/property/test_context.py bias-monitoring/tests/unit/test_window.py -v
  ```
  Esperado: código 0, con la semilla impresa. Pasan:
  - **PBT-U9-04** con un oráculo por tabla de verdad de (b): `freeze` ⇔ población `modelo` y algún atributo con límite > umbral; todo insuficiente → no congela; `humana` nunca da `freeze`. Generadores con límites alrededor de los bordes (4,99 / 5,00 / 5,01 pp) en **cualquier** atributo, no solo en el de la mayor agregada;
  - **PBT-U9-08**: el paquete nunca trae la tasa de una celda insuficiente ni la tasa sin bandas de un grupo con alguna celda insuficiente, ni campos fuera de §3.1; con menos de 7 días de datos, `before = sin_datos`; historia de 0 a 40 días;
  - reactivación con `recorded_at` a las 23:50 UTC del día D → la ventana empieza el día D + 1; con `investigar` y luego `reactivar`, cuenta la `reactivar`;
  - paquete con los catálogos completos (22 grupos × 3 bandas × 3 mediciones) → ≤ 48 KiB, o `truncated = true` con las agregadas, las bandas, `trigger_attribute` e `implicated` intactos;
  - el paquete valida contra `FreezeContext` de U0 y lleva `library_version` = `vectra_disparity.__version__` (NFR-U9-54).

- [ ] **CA-2** — Paso 6: ejemplos de la regla (b).
  ```bash
  uv run pytest bias-monitoring/tests/unit/test_freeze_rule_examples.py -v
  ```
  Esperado: código 0. Pasan, con conteos construidos en la prueba y la librería real:
  - 40 casos por celda y 6 pp → sin `freeze`;
  - 2 000 casos por celda y 6 pp → sin `freeze` (límite ≈ 0,0315; BLM §3, R4). Ver «Aceptación del plan y su compatibilidad con R4»;
  - 2 000 casos por celda y 12 pp → `freeze`;
  - **enmascaramiento de F-03**: `region` (5 grupos a 0,50 y 1 a 0,70, 40 por celda) y `sexo` (0,50 y 0,60, 3 000 por celda) → `freeze`, con `sexo` y su límite 0,0768 en la decisión, y `trigger_attribute = region` en el paquete. `implicated` nombra `sexo` y su `freeze_lower_limit`;
  - conteos de `u5_counts.json`: variante proxy → `freeze` por `region` (límite ≈ 0,2282); modelo base → sin `freeze` (mayor límite ≈ 0,0042).

- [ ] **CA-3** — Paso 7: clientes y `publish`.
  ```bash
  uv run pytest bias-monitoring/tests/integration/test_clients.py bias-monitoring/tests/integration/test_publish.py -v && HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_publish.py -v
  ```
  Esperado: código 0. Pasan **todos** los casos de la aceptación del Paso 7 del plan:
  - cada llamada corta en su timeout, con dobles lentos;
  - 4 versiones → dos solicitudes de rangos (12 + 4) y `unattributable_invalid` tomado una sola vez;
  - `freeze` con 503 persistente → 4 intentos; con 409 → 1 intento y éxito; con 403 → 1 intento y fallido;
  - el grupo `freeze-<v>` persiste tras una corrida que falla antes del cálculo; se borra con un `freeze` exitoso, con un 409, y en una corrida completa en la que `v` ya no cumple la regla o ya no se evalúa;
  - una corrida fallida no borra `last_success`;
  - una versión que deja de evaluarse desaparece del grupo `run`;
  - 20 grupos `freeze-<v>` de versiones que ya no se evalúan → la corrida borra 16 y la siguiente, los 4 restantes; cada operación corta a los 5 s;
  - PBT-U9-03, cláusula de `publish`: con celdas chicas y `no_informado` generados, ninguna serie publica la tasa de una celda insuficiente, y `band = sin_bandas` sigue BR-U9-06 con `partial`.

- [ ] **CA-4** — Paso 8: la corrida.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests/property/test_run_machine.py bias-monitoring/tests/integration/test_run.py -v
  ```
  Esperado: código 0, con la semilla impresa. Pasan **todos** los casos de la aceptación del Paso 8 del plan:
  - **PBT-U9-05** stateful, de 1 a 40 corridas, con reactivaciones intercaladas, Keycloak sin token y dos versiones con un `freeze` que falla solo en una, con todos sus invariantes de la BLM §3, incluido el ciclo de vida de los grupos `freeze-<v>` contra un doble del Pushgateway que registra `PUT` y `DELETE`;
  - RT-2: conteos de la variante proxy → `freeze` con el atributo disparador en el paquete; modelo base → sin `freeze` (US-303);
  - humana alta y modelo bajo → `rule_met{population="humana"}` = 1 y ninguna llamada a `freeze` (US-302);
  - tras el `freeze`, una medición de 1 pp → ninguna llamada (US-303);
  - inválidas al 0,5 % → corrida completa; al 1,5 % → fallida; una decisión no atribuible cuenta una vez en los dos lados;
  - agregador atrasado 45 min → fallida;
  - E1, E3, E4, E5 y E7 de P-U9-07 con dobles;
  - una corrida con 3 versiones y celdas densas dura < 2 min y mide su pico de memoria (NFR-U9-01, 04). Anota el pico en la bitácora. Si pasa del 70 % de 256 MiB, repórtalo (NFR-U9-04).

- [ ] **CA-5** — Re-medición con (b).
  ```bash
  uv run pytest bias-monitoring/tests/simulation -m simulation -v -s && grep -nE "2026-11-10|opci[oó]n \(b\)" aidlc-docs/construction/bias-monitoring/code/library.md
  ```
  Esperado: código 0, sin `xfail` ni `skip`. La salida imprime las cifras de las tres condiciones con (b): falsos ≤ 5 % con ≥ 500 casos; base ≤ 5 % con 50 y 100 y ≤ 6 % con 30; variante proxy actual ≥ 95 % con `stratified`; y D\* recalibrado ≥ 95 %. `library.md` tiene la columna de la regla de solo el disparador y la de (b), con la fecha y la cita.

- [ ] **CA-6** — Enmienda de diseño.
  ```bash
  grep -nE "2026-11-10" aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md aidlc-docs/construction/bias-monitoring/functional-design/business-logic-model.md aidlc-docs/construction/bias-monitoring/functional-design/domain-entities.md aidlc-docs/construction/bias-monitoring/code/library.md aidlc-docs/audit.md
  grep -nE "disparador" aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md aidlc-docs/construction/bias-monitoring/functional-design/business-logic-model.md aidlc-docs/construction/bias-monitoring/code/library.md
  ```
  Esperado: el primer `grep` da al menos una línea por archivo, en BR-U9-11, BR-U9-05, 15 y 20, BLM §2.1 y §3, domain-entities §2.6 y §3.1, y `library.md`. En el segundo, ninguna línea presenta la regla de solo el disparador como vigente: cada aparición describe BR-U9-05 o la historia de la regla. BR-U9-11 dice 46 comparaciones reales y conserva `z = 3,14`.

- [ ] **CA-7** — Imports y arquitectura (P-U9-04, P-U9-05).
  ```bash
  uv run lint-imports --config bias-monitoring/.importlinter && uv run pytest bias-monitoring/tests/unit/test_architecture.py -v
  ```
  Esperado: los cuatro contratos `KEPT`. La prueba de arquitectura comprueba, con una búsqueda estática sobre `bias-monitoring/src/vectra_bias/`, que ningún módulo fuera de `vectra_disparity` construye un `CellResult` con `rate` (P-U9-04; T01 la dejó para cuando existieran los consumidores). **Rojo primero:** un `import vectra_bias.publish` en `context.py` rompe el contrato de módulos puros.

- [ ] **CA-8** — Trazabilidad.
  ```bash
  uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: cumple la regla de `DECISIONES-LOOP.md` §6 con su enmienda. Corre en la base y en la rama. Ningún fallo nuevo es de los Pasos 6 a 8. En particular, P-U9-01, P-U9-07, NFR-U9-01, 20, 21 y 22 (de las líneas «Diseño:» de esos pasos) quedan trazados en el código o las pruebas de `bias-monitoring/`.

- [ ] **CA-9** — `check` de la unidad (RL-4).
  ```bash
  make -C bias-monitoring check
  ```
  Esperado: código 0. Hoy el objetivo `test` del `Makefile` ignora `tests/property` entero, así que las PBT nuevas no correrían. Cambia el `Makefile` para que `check` corra también `test_freeze_rule.py`, `test_context.py`, `test_publish.py` y `test_run_machine.py` con el perfil `ci`, sin correr dos veces las de la librería. Si el diff toca `pyproject.toml` o `uv.lock`, corre además `make -C platform check` y debe dar 0.

- [ ] **CA-10** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso [678] "
  ```
  Esperado: Pasos 6, 7 y 8 en `[x]` con `(U09-T02)`. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

Se escriben **en esta tarea**:
- `tests/unit/test_window.py`, `tests/property/test_freeze_rule.py`, `tests/unit/test_freeze_rule_examples.py` y `tests/property/test_context.py` (Paso 6);
- `tests/integration/test_clients.py`, `tests/integration/test_publish.py` y `tests/property/test_publish.py` (Paso 7);
- `tests/property/test_run_machine.py` y `tests/integration/test_run.py` (Paso 8);
- `tests/unit/test_architecture.py` (P-U9-04);
- los dobles de U3, U4, Keycloak y el Pushgateway en `tests/doubles/`;
- el cambio de `tests/simulation/test_statistical_validation.py` (regla real y D\* nuevo).

**Rojo primero**, con cada par falla-pasa en `bitacoras/U09-T02.md`:
- `freeze_rule` con la regla de solo el disparador → el caso de enmascaramiento de CA-2 no congela, y PBT-U9-04 con su oráculo de (b) falla. Es el rojo de la decisión;
- la simulación con la regla de solo el disparador, antes de (b): sus cifras van a la bitácora y a `library.md`;
- `window` con el mismo día del `recorded_at` → el caso de las 23:50 UTC falla;
- `context` con la tasa de una celda insuficiente → PBT-U9-08 falla;
- un recorte que quita las agregadas → el caso de 48 KiB falla;
- `unattributable_range` en todas las solicitudes → el caso de las 4 versiones falla;
- `freeze_client` que reintenta un 409 → su caso falla;
- `success` empujado en una corrida fallida → PBT-U9-05 falla;
- `freeze` antes de comprobar las inválidas → PBT-U9-05 falla;
- la población `humana` llamando a `freeze` → PBT-U9-04 y PBT-U9-05 fallan;
- `publish` con la tasa de una celda insuficiente → PBT-U9-03 falla.

---

## Notas

- **Puntos de detención** (detente y repórtalo; decide el usuario o el orquestador):
  - una condición de la re-medición falla con (b): condición 1, condición 2, o la variante proxy actual por debajo del 95 % con `stratified`;
  - `FreezeContext` de U0 no admite el atributo y su límite en `implicated` (por ejemplo, la validación de U0, U3 o U4 rechaza los objetos). No se cambia U0;
  - U0, U3 o U4 no exponen algo que los dobles necesitan (un campo, un código de error, la forma de `daily:query`). No inventes campos;
  - falta un campo de log en `LOG_RECORD_FIELDS`.
- **Referencia, no criterio:** al preparar esta tarea, una corrida de 1 000 repeticiones de la simulación de U9 dio las mismas cifras con las dos reglas (falsos: 56,5 % con 30, 9,8 % con 100 y 0 % con 500; base: 1,0 a 1,2 %; proxy actual con `stratified`: 100 %). Con celdas iguales, el atributo de la mayor agregada casi siempre tiene también el mayor límite. Por eso el rojo de la decisión es el caso determinista de F-03, no la simulación. La que cuenta es la corrida de 10 000.
- **Riesgo para U5 y U12:** `reference-model/tests/simulation/test_r4_freeze_rate.py` sigue midiendo con la regla de solo el disparador sobre muestras reales de `test`. Con (b) el modelo base solo puede congelar igual o más. Anótalo en la bitácora; la candidata de U5 lo cubre.
- Archivos que se **modifican en su sitio**:
  - `bias-monitoring/src/vectra_bias/` (`window.py`, `freeze_rule.py`, `context.py`, `registry_client.py`, `freeze_client.py`, `publish.py` y `run.py`);
  - `bias-monitoring/Makefile` y `bias-monitoring/tests/`;
  - el comentario de `Z_FREEZE` en `bias-monitoring/disparity/src/vectra_disparity/stats.py`;
  - `business-rules.md`, `business-logic-model.md` y `domain-entities.md` de `aidlc-docs/construction/bias-monitoring/functional-design/`, y `aidlc-docs/construction/bias-monitoring/code/library.md`;
  - el plan (solo las casillas), `CANDIDATAS.md` y `aidlc-docs/audit.md` (solo anexar).

  Nada de duplicados con sufijo. Archivo nuevo de soporte: `revisiones/U09-T02/busqueda-dstar.py`.
- `dashboard.py`, `freezes.py`, `compare.py`, `cache.py` y `app.py` siguen vacíos: son de U09-T03.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- **Bitácora:** `bitacoras/U09-T02.md`, con:
  - la semilla de cada PBT;
  - los pares falla-pasa;
  - las cifras de la simulación con las dos reglas;
  - la t y el D\* nuevos;
  - el pico de memoria y la duración de CA-4;
  - el código de salida elegido para una corrida fallida;
  - la discrepancia del plan en «2 000 casos y 6 pp».
