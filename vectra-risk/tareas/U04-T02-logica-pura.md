# U04-T02 — Lógica pura de `governance`: `model_fsm`, `policy`, `serving_config` y `registration`

**Unidad:** U4 `governance`
**Historias que implementa:** US-201, US-203, US-205, US-206 y US-305, en su parte de lógica pura.
**Depende de:** U04-T01 (PR 92), ya en `main`.
**Rama:** `tarea/U04-T02`, creada desde `origin/main` (`9352400`). Corre en paralelo con U03-T05 y U09-T01 (RL-5).

Bloque C del plan de U4 (Pasos 3 a 7). Entra **completo** (E): la enmienda dice «1–7 · E · Completos» (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §3, U4) y la tabla de §4 lo deja como una tarea propia («A+B · **C** · D (8–11) · …»). Rige el ritmo RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 3 a 7 del plan (`aidlc-docs/construction/plans/governance-code-generation-plan.md`, Bloque C). Su texto, sin recortes:

- [ ] **Paso 3 — `model_fsm`**
  - Función pura con la tabla de BR-U4-01; errores `Forbidden`/`ConflictState`.
  - Propiedad PBT-U4-02 (oráculo sobre el producto completo de estados × acciones × actores).
  - Diseño: BR-U4-01, 02, 04, 10. Historias: US-203, US-305.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_model_fsm.py`.

- [ ] **Paso 4 — `policy`**
  - Validación de la lista normativa (BR-U0-33); `normative_at(policy, fecha)` con fechas en **`America/Bogota`**; cuatro ojos; activación (la anterior pasa a `historica`).
  - Propiedades PBT-U4-03 (incluidos los bordes de la medianoche de Bogotá) y PBT-U4-04.
  - Diseño: BR-U4-10, 11; P-U4-05. Historias: US-205, US-206.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_policy.py`, y la prueba con reloj simulado: el cambio de vigencia ocurre a las 00:00 de Bogotá y no a las 19:00 de Bogotá.

- [ ] **Paso 5 — `serving_config`**
  - Composición de domain-entities §5 (incluido `inference_service`) y `etag` (JCS de todos los campos; sin `bias_monitoring_age_s`, precisado el 2026-10-08 por U9 FD); prueba de ejemplo: cambiar solo `inference_service` cambia el `etag`.
  - Propiedad PBT-U4-05.
  - Diseño: BR-U4-11, 14; P-U4-07.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_serving_config.py`.

- [ ] **Paso 6 — `registration`**
  - Formato permitido, rechazo de `pickle`/`joblib` por extensión y bytes mágicos, SHA-256 sobre los bytes de cada archivo del `manifest.json` (U5) y mismo `model_version_id` en todos; nunca deserializa.
  - Propiedad PBT-U4-06.
  - Diseño: BR-U4-06. Historia: US-201.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_registration.py`, más una prueba que hace fallar a cualquier deserializador si se lo invoca (*monkeypatch* de `pickle.loads`, `joblib.load` y `onnx.load`).

- [ ] **Paso 7 — Resumen de la lógica pura**
  - `aidlc-docs/construction/governance/code/business-logic-summary.md`.
  - **Aceptación**: `uv run python platform/tests/test_traceability.py --unit governance --section logic` (BR-U4-01, 02, 04, 06, 10, 11 y 14 aparecen en las pruebas).

Precisiones:

- **Los cuatro módulos siguen puros.** El contrato `pure-no-io` de `governance/.importlinter` (U04-T01) prohíbe E/S y también `vectra_common`. Pueden importar `vectra_contracts` (tipos de U0, `canonical.canonicalize`), `hashlib`, `datetime`, `zoneinfo`, `dataclasses`, `typing` y similares. No se toca el contrato. Ver A-1 sobre los errores.
- **`model_fsm` (Paso 3).** Implementa `transition(state, action, actor, context) -> new_state | Error` (business-logic-model §1), con la tabla de BR-U4-01 **completa**, incluidas las filas de US-306 (`source_candidate_for` con la fuente no `aprobada` → `ConflictState`). La enmienda difiere US-306 en el servicio, no en la máquina de estados, y PBT-U4-02 recorre el producto completo.
  - Actores: rol (`ingeniero_riesgo`, `cro`, `cumplimiento`, `analista`) con y sin MFA, las identidades de servicio `bias-monitoring-job` y `model-validation-job`, y `sistema`. Usa los nombres de `vectra_contracts` (`Role`, `Actor` en `models/registry.py`) donde existan; no inventes otros. El MFA es `acr = mfa` (BR-U4-03); la frescura de `auth_time` (step-up de 15 min) es del endpoint (Paso 10), no de esta función.
  - Actor equivocado → `Forbidden`; estado equivocado → `ConflictState` (BR-U4-01, último párrafo). Si los dos fallan a la vez, fija un orden, documéntalo en el docstring y pruébalo.
  - BR-U4-02 (`mark_active` con otra versión `congelado` → `ConflictState`) y BR-U4-10 (el `cro` que aprueba ≠ `registered_by`) entran por `context`. BR-U4-04: `bias-monitoring-job` solo produce `freeze` sobre `activo`; cualquier otra acción → `Forbidden`.
  - El oráculo de PBT-U4-02 es una tabla **escrita aparte** en la prueba, copiada de BR-U4-01, no la misma estructura que usa el módulo. Si la prueba importa la tabla del módulo, no prueba nada.
  - `congelado → inactivo` no está en BR-U4-01, así que la función lo rechaza. Es lo que pide la candidata F-03 de U04-T01 (`CANDIDATAS.md`); esta tarea **no** cambia el trigger `guard_unfreeze`.
- **`policy` (Paso 4).**
  - La validación de la lista normativa reutiliza la de U0 (`PolicyDraft` en `vectra_contracts/models/governance.py`, BR-U0-33). No dupliques la regla de solapes; si necesitas una función propia, que llame a la de U0.
  - `normative_at(policy, d)` sigue domain-entities §3.2 (`effective_from ≤ d` y `effective_to` nulo o `d < effective_to`). Agrega la función que convierte un instante UTC a la fecha de `America/Bogota` (P-U4-05). El reloj entra como parámetro; ningún módulo puro llama a `datetime.now()`.
  - Cuatro ojos (BR-U4-10; PBT-U4-04): aprobar ⇔ `approved_by ≠ proposed_by` y rol `cro` con MFA.
  - Activación (BR-U4-11): aprobar una `propuesta` la deja `activa` y la `activa` anterior pasa a `historica`. Es una función pura que devuelve los dos cambios de estado; la persistencia y la evidencia son del Paso 8.
- **`serving_config` (Paso 5).**
  - La composición devuelve el tipo de U0 `ServingConfig` (`vectra_contracts/models/governance.py`). P-U4-07: solo los campos de ese tipo; una prueba lo comprueba.
  - El `etag` es el SHA-256 hex de `canonicalize` (JCS, `vectra_contracts/canonical.py`) de todos los campos de domain-entities §5 salvo el propio `etag`.
  - El tipo de U0 exige versión servible y política activa. Si falta alguna, la composición no produce un `ServingConfig`; devuelve `None` o un error propio. Qué responde la API en ese caso es del Paso 9 o 10. Documenta tu elección en la bitácora.
- **`registration` (Paso 6).**
  - Función pura sobre **bytes**: recibe el formato declarado, los SHA-256 declarados, los bytes de `manifest.json` y los de cada archivo que lista. Leer del model-store (F47) es del Paso 10.
  - El formato del manifiesto es el de U5: `reference-model/src/vectra_reference/package.py` (`build_package`, `_render`) y los paquetes RT3 en `reference-model/src/vectra_reference/adversarial.py`. No cambies U5.
  - Bytes mágicos: pickle (`\x80` + versión de protocolo) y la cabecera zip de joblib, en **cualquier** archivo y con cualquier extensión (PBT-U4-06). Extensión `.pkl`, `.pickle` o `.joblib` → rechazo aunque los bytes no lo sean.
  - El resultado incluye el `feature_dictionary` y el `feature_spec` verificados, que el Paso 10 guarda en la versión (BR-U4-06, último párrafo). Parsear JSON con `json.loads` no es deserializar un modelo; `pickle`, `joblib`, `onnx.load`, `xgboost` y `lightgbm` nunca se llaman.
  - Cualquier fallo → error con un motivo estable (Paso 10 lo traduce a `422 validation_error`).
- **Resumen (Paso 7).** `aidlc-docs/construction/governance/code/business-logic-summary.md`, con el formato de `aidlc-docs/construction/decision-registry/code/business-logic-summary.md`.
- **Plan.** Marca `[x]` los Pasos 3 a 7, con `(U04-T02)`.

**Fuera:**

- Evidencia en dos fases, reconciliador, barridos, convergencia, pools y endpoints (Bloque D, Pasos 8–11). En particular: traducir los errores de `model_fsm` a `vectra_common` (Paso 10), PBT-U4-01 y PBT-U4-07 (Paso 8), la fórmula de la llave UUIDv5 (candidata F-04 de U04-T01) y el temporizador de las 00:00 de Bogotá (P-U4-05, Paso 9).
- Leer del model-store, lanzar Jobs, `promotion-tool` y `validation_job` (Pasos 10, 12 y 13).
- Cambios a las migraciones o a los triggers de U04-T01 (candidatas F-03 y F-05) y al contrato de import-linter.
- Cambios a U0 (`vectra_contracts`, `vectra_common`), a U5 (`reference-model/`) o a U1 (`platform/`). Si algo falta allí, detente y repórtalo.

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md` (§1 y Pasos 3–7)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2 y §6) y `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2 y §3, U4)
- `aidlc-docs/construction/governance/functional-design/business-rules.md` (§1, §2 BR-U4-06, §4, §5 y §7)
- `aidlc-docs/construction/governance/functional-design/business-logic-model.md` (§1 y §3: PBT-U4-02..06 y las pruebas de ejemplo de US-201, 203, 205, 206 y 305)
- `aidlc-docs/construction/governance/functional-design/domain-entities.md` (§1, §3 y §5)
- `aidlc-docs/construction/governance/nfr-design/nfr-design-patterns.md` (P-U4-05 y P-U4-07)
- `aidlc-docs/construction/contracts/functional-design/business-rules.md` (BR-U0-33)
- `contracts/python/vectra_contracts/src/vectra_contracts/models/governance.py`, `models/registry.py`, `canonical.py` y `routes/__init__.py` (`Role`)
- `reference-model/src/vectra_reference/package.py` y `adversarial.py` (formato del paquete y paquetes RT3)
- `governance/.importlinter`, `governance/Makefile` y `governance/tests/conftest.py` (U04-T01)
- `decision-registry/src/vectra_registry/chain.py` y `aidlc-docs/construction/decision-registry/code/business-logic-summary.md`, como ejemplo de lógica pura y de resumen
- `CANDIDATAS.md` (F-03 y F-04 de U04-T01)

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1** — `model_fsm` (Paso 3).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_model_fsm.py -v
  ```
  Esperado: todo pasa. PBT-U4-02 recorre el producto completo (estados × acciones × actores × MFA), con el oráculo escrito aparte. Hay ejemplos para US-203 (`cro` aprueba; `ingeniero_riesgo` aprueba → `Forbidden`), US-305 (`cumplimiento` con MFA reactiva; `cro`, job o `sistema` → `Forbidden`), BR-U4-02, BR-U4-04, BR-U4-10 y `congelado → inactivo` → rechazo.

- [ ] **CA-2** — `policy` (Paso 4).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_policy.py -v
  ```
  Esperado: todo pasa. PBT-U4-03 incluye fechas alrededor de las 05:00 UTC, y la validación rechaza toda lista con solapes. PBT-U4-04 cubre los pares de usuarios y roles. La prueba con reloj simulado comprueba que `normative_current` cambia entre 23:59:59 y 00:00:00 de Bogotá, y **no** entre 18:59:59 y 19:00:00 de Bogotá (00:00 UTC). Hay ejemplos para US-205, US-206 (P2 activa, P1 `historica`) y la vigencia vencida → nulo.

- [ ] **CA-3** — `serving_config` (Paso 5).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_serving_config.py -v
  ```
  Esperado: todo pasa. PBT-U4-05 con pares que difieren en un campo o en ninguno, el ejemplo «solo cambia `inference_service` → cambia el `etag`», el ejemplo de P-U4-07 (solo los campos del tipo de U0) y un cambio de `normative_current` → cambia el `etag`.

- [ ] **CA-4** — `registration` (Paso 6).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_registration.py -v
  ```
  Esperado: todo pasa. PBT-U4-06, la prueba con `pickle.loads`, `joblib.load` y `onnx.load` reemplazados por funciones que fallan (si un módulo no está instalado, se reemplaza su nombre en `sys.modules`), el registro válido de US-201 y el checksum alterado → rechazo. Los paquetes RT3-a, RT3-c y RT3-d se rechazan (BR-U4-06, punto 5), construidos con el formato de U5.

- [ ] **CA-5** — Resumen y trazabilidad (Paso 7). Los docstrings del esqueleto ya citan estos BR y el comando del plan pasa sin pruebas; por eso se lee de vuelta en `governance/tests/`, y BR-U4-14 se comprueba aparte porque el parser de `--section` no lo toma de «11 y 14».
  ```bash
  uv run python platform/tests/test_traceability.py --unit governance --section logic
  test -s aidlc-docs/construction/governance/code/business-logic-summary.md && echo OK-resumen
  for id in 01 02 04 06 10 11 14; do grep -rqE "BR-U4-$id\b|br_u4_$id\b" governance/tests || echo "FALTA BR-U4-$id en tests"; done
  ```
  Esperado: el primero en 0, `OK-resumen` y ninguna línea `FALTA`.

- [ ] **CA-6** — Pureza.
  ```bash
  uv run lint-imports --config governance/.importlinter
  git diff --exit-code origin/main -- governance/.importlinter && echo OK-contrato-intacto
  ! grep -rnE 'datetime\.now|date\.today|time\.time' governance/src/vectra_governance/{model_fsm,policy,serving_config,registration}.py
  ```
  Esperado: los dos contratos `KEPT`, `OK-contrato-intacto`, y el `grep` sin salida.

- [ ] **CA-7** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C governance check
  make -C platform check
  ```
  Esperado: código 0 en los dos. Si `make -C platform check` no termina por la red (504 de github.com), corre `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib` y regístralo; el CI del PR corre el resto.

## Plan de pruebas

- `governance/tests/property/test_model_fsm.py`, `test_policy.py`, `test_serving_config.py` y `test_registration.py`: una PBT por propiedad del plan y los ejemplos de business-logic-model §3 que caen en la lógica pura (US-201, 203, 205, 206 y 305; vigencia vencida).
- Las pruebas citan su `BR-U4-xx` o `PBT-U4-xx` en el nombre o en el docstring.
- **Rojo primero**, registrado en `bitacoras/U04-T02.md`:
  - PBT-U4-02: una fila de la tabla del módulo cambiada a propósito (por ejemplo, `congelado → activo` admitido para `cro`) y la prueba la detecta;
  - PBT-U4-03: `normative_at` con la fecha en UTC en lugar de Bogotá y la prueba del reloj simulado la detecta;
  - PBT-U4-05: un `etag` que omite `inference_service` y la prueba la detecta;
  - PBT-U4-06: la comprobación de bytes mágicos quitada y la prueba la detecta.

## Notas

- Archivos que se modifican en su sitio: los cuatro módulos puros de `governance/src/vectra_governance/` y `aidlc-docs/construction/plans/governance-code-generation-plan.md` (casillas). Nada de duplicados con sufijo.
- **A-1 (arbitrada por el orquestador, 2026-11-09).** El Paso 3 dice «errores `Forbidden`/`ConflictState`». Esas clases están en `vectra_common.errors`, y el contrato `pure-no-io` de U04-T01 prohíbe `vectra_common` en los módulos puros. U3 resolvió lo mismo con errores propios en la lógica pura. Decisión: `model_fsm` define sus propios `Forbidden` y `ConflictState` (o un resultado con esos dos tipos de error), sin importar `vectra_common`. El Paso 10 los traduce a `vectra_common.errors.Forbidden` y `ConflictState`. Usa los mismos nombres para que la traducción sea obvia.
- **A-2.** domain-entities §1.3 nombra al actor de una transición como `{kind, sub, role, acr?, auth_time?}`, y `vectra_contracts.models.registry.Actor` usa `id` en vez de `sub`. Usa el tipo de U0 si te sirve, o uno propio en `model_fsm`, y registra la elección. No cambies U0.
- Si `zoneinfo` no encuentra `America/Bogota` en el entorno, agrega `tzdata` (fijado con `==`) a las dependencias de `governance`, regenera `uv.lock` y regístralo.
