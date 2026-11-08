# U03-T02 — Lógica pura de `decision-registry`: `chain`, `verify` y `projections`

**Unidad:** U3 `decision-registry`
**Historias que implementa:** US-402 (verificador) y US-403 (expediente), en su parte de lógica pura.
**Depende de:** U03-T01 (PR 80), ya en `main`.

Bloque C del plan de U3 (Pasos 3 a 6), que entra **completo** en la demo (E). Rige el ritmo RL-1 a RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6: una tarea por bloque, máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 3 a 6 del plan (`aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`, Bloque C), con su texto, su diseño y su aceptación **sin recortes**:

- **Paso 3 — `chain`**: `canonicalize` (JCS de U0), `link(prev_hash, canonical)` y `decode`. PBT-U3-04 (punto fijo de JCS) y PBT-U3-05 (verificación con un contrato más nuevo). Diseño: BR-U3-09, 10; domain-entities §1.1. Aceptación: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_chain.py`.
- **Paso 4 — `verify`**: función pura sobre filas y checkpoints, con los modos `incremental`, `nightly` (cadena de checkpoints + 7 días + muestra del 1 % con semilla registrada), `full` y `range`. Detecta los 6 motivos de BR-U3-12 y devuelve `IntegrityReport`. PBT-U3-02 y PBT-U3-03. Diseño: BR-U3-11, 12; NFR-U3-33. Aceptación: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_verify.py decision-registry/tests/unit/test_verify_modes.py`.
- **Paso 5 — `projections`**: las proyecciones de domain-entities §3 (`full`, `explanation`, `metrics`, `monitoring_daily` y `monitoring_freezes`; sin la `monitoring` por filas). Un campo o una proyección no permitidos → `Forbidden`, sin datos parciales. PBT-U3-06. Diseño: BR-U3-15. Aceptación: `HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_projections.py`.
- **Paso 6 — Resumen de la lógica pura**: `aidlc-docs/construction/decision-registry/code/business-logic-summary.md`. Aceptación: `uv run python platform/tests/test_traceability.py --unit decision-registry --section logic` (BR-U3-09..12 y 15 aparecen en las pruebas).

**También entran dos candidatas de U03-T01** (están en `CANDIDATAS.md`):
1. **Prioritaria, la protección de solo-anexar de `registry_idempotency_keys` sin prueba** (revisor, U03-T01, F-01). Agrega a `tests/integration/test_migrations.py`:
   - casos de superusuario: `UPDATE`, `DELETE` y `TRUNCATE` sobre `registry_idempotency_keys` → excepción;
   - casos de privilegios: ningún rol de app puede escribir esa tabla.

   **Rojo primero:** quitando cada trigger de la migración en una copia, el caso correspondiente falla.
2. **El formato de los sellos de tiempo de la génesis** (revisor, U03-T01, F-04). `canonicalize` fija el formato ISO 8601 UTC con microsegundos y `Z`. La génesis de la migración `0001` usa ese mismo formato, con `timespec="microseconds"`. Una prueba exige que la génesis canonizada por la migración sea igual a `canonicalize` aplicado a sus campos. **No** cambies que `recorded_at` salga del reloj de Python en la génesis. Va a candidatas si el diseño pide la base.

   Toca una migración ya fusionada. Como `registry-db` todavía no se ha desplegado en ningún clúster, se edita `0001` en su sitio y no hace falta una migración nueva. Regístralo en la bitácora.

Precisiones:
- `chain`, `verify` y `projections` siguen sin E/S: el contrato de import-linter de U03-T01 tiene que seguir `KEPT`.
- `IntegrityReport`, los tipos de entrada y la lista de proyecciones salen de U0 (`contracts/python/vectra_contracts`) si existen allí. Si no existen, se definen en `decision-registry` y se anota en la bitácora.
- **Plan:** marca `[x]` los Pasos 3 a 6, con `(U03-T02)`.

**Fuera:**
- El servicio, el append, la API, la CLI y los CronJobs (Bloques D y E).
- Las demás candidatas de U3.

## Archivos de contexto

- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md` (Bloque C)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6)
- `aidlc-docs/construction/decision-registry/functional-design/` (BR-U3-09..12 y 15; PBT-U3-02..06; domain-entities §1.1 y §3; business-logic-model)
- `aidlc-docs/construction/decision-registry/nfr-requirements/` (NFR-U3-33)
- `decision-registry/` (lo que dejó U03-T01) y `revisiones/U03-T01/`
- `contracts/python/vectra_contracts` (JCS y tipos de registro)
- `CANDIDATAS.md` (entradas de U03-T01)

## Criterios de aceptación

- [ ] **CA-1** — `chain`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_chain.py -v
  ```
  Esperado: PBT-U3-04 y PBT-U3-05 pasan.

- [ ] **CA-2** — `verify`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_verify.py decision-registry/tests/unit/test_verify_modes.py -v
  ```
  Esperado: PBT-U3-02 y 03 pasan. Hay un caso por cada uno de los 6 motivos de BR-U3-12 y por cada modo.

- [ ] **CA-3** — `projections`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests/property/test_projections.py -v
  ```
  Esperado: PBT-U3-06 pasa. Un campo o una proyección no permitidos dan `Forbidden`, sin datos parciales.

- [ ] **CA-4** — Resumen y trazabilidad.
  ```bash
  uv run python platform/tests/test_traceability.py --unit decision-registry --section logic
  ```
  Esperado: código 0. Si la prueba no admite `--section` o `--unit decision-registry`, **detente y repórtalo**: no cambies la prueba.

- [ ] **CA-5** — Candidatas de U03-T01.
  ```bash
  uv run pytest decision-registry/tests/integration/test_migrations.py -v -k "idempotency_keys or genesis"
  ```
  Esperado: pasan los casos nuevos de `registry_idempotency_keys` y de la génesis canonizada.

- [ ] **CA-6** — `check` de la unidad y de U1.
  ```bash
  make -C decision-registry check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

Rojo primero de cada PBT con una mutación. Por ejemplo:
- `link` sin `prev_hash`;
- `verify` que ignora uno de los 6 motivos;
- `projections` que devuelve datos parciales.

Haz lo mismo con los casos nuevos de CA-5. Registra todo en `bitacoras/U03-T02.md`.

## Notas

Archivos que se modifican en su sitio:
- `decision-registry/src/vectra_registry/{chain,verify,projections}.py`;
- `migrations/versions/0001_registry_entries.py`, solo para el formato de la génesis;
- `tests/integration/test_migrations.py`;
- el plan de U3 y `CANDIDATAS.md`, donde marcas las dos candidatas como atendidas.
