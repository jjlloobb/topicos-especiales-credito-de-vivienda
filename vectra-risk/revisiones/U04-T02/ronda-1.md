# Ronda 1 — U04-T02

VEREDICTO: VERDE

Corrí los siete criterios. Los siete pasan; CA-7 pasa por el plan B, que autorizaste. No encontré ningún ROJO ni NARANJA. Dejo cinco AMARILLOS, que no bloquean.

Revisé el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u04-t02` en `dd1065f`, con el diff `9352400..dd1065f`. El blob de la tarea es `69e1b61…` y coincide con el que me diste. Al terminar, `git status --short --ignored` solo muestra cachés ignoradas (`.hypothesis/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.import_linter_cache/` y `platform/.charts/`), así que el worktree queda limpio. Para CA-6 hice `git fetch origin main`, y eso movió una referencia remota; no tocó ninguna fuente.

Alcance: el commit del codificador toca 11 archivos, todos dentro del alcance. `CANDIDATAS.md` y la tarea vienen del commit del orquestador (`387f84d`). `git diff --stat 9352400..HEAD -- contracts reference-model platform governance/migrations` sale vacío, y `.importlinter` está intacto.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `model_fsm` | `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_model_fsm.py -v` | pasa: 19 passed en 0,42 s. Con `--hypothesis-show-statistics`, la PBT con contexto da 500 casos que pasan, 0 inválidos. El tiempo se explica porque es lógica pura y el producto completo tiene 1 848 combinaciones |
| 2 | `policy` | `... test_policy.py -v` | pasa: 17 passed en 3,06 s |
| 3 | `serving_config` | `... test_serving_config.py -v` | pasa: 9 passed en 1,71 s |
| 4 | `registration` | `... test_registration.py -v --durations=5` | pasa: 29 passed en 5,59 s. Construye un paquete real de U5 con `run_release` (2,37 s de preparación). Ninguna prueba se omitió |
| 5 | Trazabilidad | los tres comandos de CA-5 | pasa: `governance: 34 identificadores con trazabilidad` (código 0), `OK-resumen` y ninguna línea `FALTA` |
| 6 | Pureza | `lint-imports`, `git diff --exit-code origin/main -- governance/.importlinter` y el `grep` | pasa: 2 contratos KEPT, `OK-contrato-intacto` y el `grep` sin salida. Además, `registration.py` solo importa `hashlib`, `json`, `collections.abc`, `dataclasses`, `typing` y `vectra_contracts` |
| 7a | `make -C governance check` | el de la tarea | pasa: código 0, con ruff, mypy, 2 KEPT y 114 passed en 28,28 s, sin omitidas |
| 7b | `make -C platform check` | el de la tarea | **código 2**, igual que informó el codificador. Todo `check-local` pasa, y falla `check-tools` en `Makefile:42` (`test -x platform/.tools/bin/kyverno && …`) porque `ls platform/.tools` da `No such file or directory`. No descargué las herramientas. Corrí el plan B: `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib` da **274 passed en 5,33 s**. El diff no toca `platform/`, así que `check-tools` no puede verse afectado; lo corre el CI del PR |

## Verificación independiente del rojo primero

No edité el código. Hice las mutaciones en memoria, con un plugin de pytest en la carpeta temporal (`-p mutplug`, ruta abajo), sin escribir en las fuentes. Todas las pruebas las detectan:
- **PBT-U4-02.** Mutación A: `("congelado","mark_active")` admitida y `cro` agregado a `reactivar`. Mutación B: solo `cro` en `reactivar`. Cada una tumba 4 pruebas: el producto completo, las filas, la PBT con contexto y US-305.
- **PBT-U4-03.** `bogota_date` cambiado para que devuelva la fecha en UTC: 5 pruebas fallan, entre ellas `test_vigencia_changes_at_midnight_of_bogota_and_not_at_19_00`.
- **PBT-U4-05.** `etag` sin `inference_service`: 4 pruebas fallan, las tres PBT y el ejemplo de BR-U4-14. El oráculo de la PBT es independiente del módulo: usa `json.dumps(sort_keys)` y `hashlib`.
- **PBT-U4-06.** `has_executable_magic` cambiado para que siempre dé `False`: 3 pruebas fallan.

Sobre los tres puntos que pediste revisar:
- **El oráculo de PBT-U4-02.** `ORACLE` es una tabla literal escrita en la prueba, con las 17 filas de BR-U4-01, incluidas las de US-306 y BR-U4-02/10 por contexto. No importa `TRANSITIONS` ni `ACTORS` del módulo; solo importa `ACTIONS`, y `test_actions_are_the_oracle_actions` lo compara contra el oráculo. El producto es 11 estados × 14 acciones × 12 actores: 4 roles con y sin MFA, los dos jobs, `scoring-service` y `sistema`.
- **Que registration nunca deserialice.** `pickle.loads`/`load` y `joblib.load` se reemplazan por trampas, y `onnx`, que no está instalado, se reemplaza en `sys.modules`. Se aplica sobre el paquete válido, sobre bytes mágicos, sobre RT3-a, b, c y d, sobre `.joblib` y sobre un manifiesto ilegible. `test_the_trap_really_traps` demuestra que la trampa dispara.
- **El reloj de Bogotá, en los dos bordes.** La prueba cubre 23:59:59 → 00:00:00 de Bogotá (cambia la vigencia) y 18:59:59 → 19:00:00 de Bogotá (no cambia, aunque en UTC ya es el día 10). Además, una PBT recorre ±3 h alrededor de las 05:00 UTC.

## Hallazgos

### F-01 · AMARILLO · `model_fsm.py` (`raise ConflictState("active_version_frozen")`) · Literal de un valor que ya está en el catálogo de U0
`active_version_frozen` ya existe como `vectra_contracts.catalog.ProblemReason.ACTIVE_VERSION_FROZEN`, en el catálogo cerrado de `reason`. El módulo puede importarlo, porque `vectra_contracts` está permitido. No es NARANJA: el valor no es nuevo y la comparación de `StrEnum` da igual. Lo mismo vale para el resto de los motivos (`approver_is_registrant`, `source_not_approved`, `policy_not_proposed` y los de `registration`): **no** están en el catálogo cerrado, así que el Paso 10 no puede ponerlos en `reason`. Ver la tarea candidata.

### F-02 · AMARILLO · `policy.py` (`validate_normative`) · `KeyError` en vez de `PolicyInvalid` con entradas que no son modelos
`error.errors()[0]["ctx"]["error"]` supone que el primer error es el del `model_validator`. Lo probé: `validate_normative([{'x':1}])` lanza `KeyError 'ctx'` y `validate_normative(['nope'])` lanza `KeyError 'error'`. Respeta el tipo declarado (`Sequence[NormativeParams]`, mypy strict), pero si el Paso 10 le pasa datos sin parsear, el resultado sería un 500.

### F-03 · AMARILLO · `test_registration.py` (`deserializers_forbidden`) · `import joblib` sin respaldo
CA-4 dice «si un módulo no está instalado, se reemplaza su nombre en `sys.modules`». Para `onnx` se hace; para `joblib` no. Hoy funciona porque `joblib` 1.6.0 está en `uv.lock`, y si faltara la prueba fallaría con ruido, no en silencio.

### F-04 · AMARILLO · `registration.py` (el orden de las comprobaciones) · Motivo de una extensión prohibida en un archivo obligatorio
Si `predictor.json` pasa a llamarse `predictor.pkl`, el rechazo sale con `manifest_missing_file:predictor.json` y no con `forbidden_extension`. El rechazo es correcto y está probado; solo el motivo es menos claro.

### F-05 · AMARILLO · `bitacoras/U04-T02.md` · «ver candidata» sin candidata
La bitácora dice que la validación de la justificación de `reject`, `reactivar`, `descartar` e `investigar` «es del endpoint… ver candidata», pero `CANDIDATAS.md` no tiene ninguna entrada de U04-T02.

## Tareas candidatas (defectos reales fuera de alcance)
- U4, Paso 10: hay que traducir los `reason` internos de `model_fsm`, `policy` y `registration` al catálogo cerrado de U0 (`ProblemReason`). Solo `active_version_frozen` puede salir como `reason`; los demás tienen que quedar en logs o evidencia, nunca en el problem+json.
- U4, Paso 10: la validación de la justificación en `reject`, `reactivar`, `descartar` e `investigar` (BR-U4-01, columna Condición) no está en ninguna capa todavía.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/5282962e-b894-499b-8246-ba5c297470a1/scratchpad/gov-check.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/5282962e-b894-499b-8246-ba5c297470a1/scratchpad/platform-check.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/5282962e-b894-499b-8246-ba5c297470a1/scratchpad/mut/mutplug.py` (el plugin de las mutaciones en memoria)

No escribí el informe en el repositorio: no tengo herramientas de escritura. El orquestador puede guardar este texto en `vectra-risk/revisiones/U04-T02/ronda-1.md`.

```
VEREDICTO: VERDE
AMARILLO|governance/src/vectra_governance/model_fsm.py (ConflictState("active_version_frozen"))|literal de un valor que ya está en ProblemReason de U0
AMARILLO|governance/src/vectra_governance/policy.py (validate_normative)|KeyError en vez de PolicyInvalid con entradas que no son modelos
AMARILLO|governance/tests/property/test_registration.py (deserializers_forbidden)|import joblib sin respaldo en sys.modules
AMARILLO|governance/src/vectra_governance/registration.py (orden de comprobaciones)|extensión prohibida en un archivo obligatorio da manifest_missing_file
AMARILLO|bitacoras/U04-T02.md|«ver candidata» sin candidata registrada
INFORME: revisiones/U04-T02/ronda-1.md
```
