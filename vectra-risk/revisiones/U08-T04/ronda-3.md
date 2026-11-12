# Ronda 3 (acotada): U08-T04

VEREDICTO: NO-VERDE

Los cuatro hallazgos de la ronda 2 están cerrados. Las pruebas nuevas son reales: la de F-01 atrapa M22 y también el contador sin inicializar, y la de F-02 atrapa cada rama mutada por separado. Las dos frases dicen lo que hace el código. El diff no desborda.

El veredicto es NO-VERDE por otra razón: `make -C case-management check` **falló** en mi corrida. El fallo está en PBT-U8-01 y lo reproduzco de forma determinista. Viene de la ronda 2 (`989ecad`): la ronda 3 no lo introdujo, y su arreglo toca la PBT, que el arbitraje deja fuera de esta ronda. Aun así es un criterio que no se cumple, así que va como ROJO (F-01 de abajo). Según el arbitraje, la tarea se para y va al usuario.

Worktree: HEAD `2e76179`, blob de la tarea `c374ce1005f4a06f9e14ebf22311900731508a47`, el mismo. Las mutaciones las apliqué en el worktree y las revertí con `git checkout`. Al terminar, `git status --short` da 0 líneas. No dejé contenedores míos: el `testcontainers-ryuk-fdada488…` de mi `check` ya no existe. Los ryuk y el `goofy_fermi` (product-metrics) que siguen activos son de otras sesiones, de hace segundos. Los `kind`/`vectra-*` y los `Exited (255)` ya estaban antes de empezar (`containers-before.txt`).

## Alcance de la ronda 3
`git diff dc49d5e HEAD --stat` toca 7 archivos: `CANDIDATAS.md`, `services.md`, `business-rules.md`, la bitácora, `test_core_mock.py`, `test_worker.py` y `ronda-3-respuesta.md`. No cambian `evaluation.py`, `job_queue.py`, la PBT ni el código del mock. **No hay desborde.**

## Criterios de aceptación, verificados por mí (en serie, `summary.txt`)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| CA-3 | Cola, evaluación, apagado | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_worker.py …/test_worker_shutdown.py -v` | pasa: 45 passed en 65,8 s, ninguno omitido (carga 13,2 → 10,1) |
| CA-4 | core-banking-mock | pytest del mock `-v` y el `python -c … print('OK')` | pasa: 15 passed en 10,4 s y `OK` |
| CA-6 | Semilla y cobertura | las tres órdenes de la tarea | pasa: `hypothesis profile: ci, seed: 2911753423`; 379 passed, total 96,76 %; los 8 módulos con 650 sentencias y 126 ramas al 100 %. `grep omit\|pragma` sobre src, coveragerc y pytest.ini no da salida |
| CA-7 | import-linter | la orden de la tarea | pasa: 5 kept, 0 broken; los dos `grep` sin salida |
| CA-9 | `make -C case-management check` | `make -C case-management check` (17:35:43, carga 13,67 → 17:56:18, carga 12,03) | **falla**: rc=2. ruff, format y mypy verdes y contratos KEPT, pero `1 failed, 393 passed in 1229.96s`. Falla `test_pbt_u8_01_case_fsm_and_evaluation_against_the_reference_model` |

## Hallazgos
### F-01 · ROJO · `tests/property/test_case_machine.py` (`_arm`/`expected` para `cfg_down`; script `late_after_thaw`) · PBT-U8-01 falla con algunas semillas: el modelo ignora la caché de `serving-config`
- **El ejemplo mínimo.** `start(script='late_after_thaw')` y después `late_result(<toma C, la vigente>, kind=('cfg_down',))`. El modelo espera `en_sincronizacion`; la base dice `listo`.
- **Reproducción determinista.** Puse `@reproduce_failure('6.170.14', b'AABBBwBBAUEBAUEBQQABQQQAAAAAAQEBAEEJQRlBAQ==')` de forma temporal y lo revertí. Sale el mismo `assert 'listo' == 'en_sincronizacion'` en 7,7 s (`pbt-repro.log`).
- **La causa, medida.** Instrumenté `_arm` (también revertido): `DIAG cfg_down cache_age 0.0085` (`pbt-repro-diag.log`). El script termina con `_late(A, rec)`, que refresca la caché, y no avanza el reloj. Así que `cfg_down` encuentra la configuración en caché, con menos de 5 s (`SERVING_CONFIG_CACHE_TTL`, NFR-U8-15). Scoring responde `ok` y el caso queda `listo`.
- **De quién es el error.** El código se comporta como pide el diseño. El defecto está en el modelo de la PBT, que da por hecho que `governance_handler.down = True` siempre produce `serving_config_unavailable`.
- **Por qué no salió antes.** Depende de la semilla: las corridas del codificador y de la ronda 2 pasaron. El script nació en `989ecad` (`git log -S late_after_thaw`). Los scripts que terminan en `_late` sin avanzar el reloj (`late_after_retake`, `late_after_retry`) tienen la misma forma.
- **Arreglo posible.** Que `cfg_down` venza la caché o avance el reloj más de 5 s, o que el modelo espere `listo` si la caché está fresca. Toca la PBT, que está fuera de lo que autorizó el arbitraje. Decide el orquestador o el usuario.

### F-02 · AMARILLO · `business-rules.md` BR-U8-08 · La frase del reloj se pasa un poco
Dice lo que pidió el arbitraje (reloj coherente entre los pods que toman y los que recrean), con dos matices:
- «Solo se sostiene si sus relojes no retroceden» presenta como necesaria una condición que es suficiente. Con desfase, la colisión exige además coincidir al microsegundo.
- El reloj de quien recrea el trabajo no fija `locked_until`, que nace `NULL`. El que cuenta es el de las tomas.

No bloquea.

## Lo que pedía la ronda 3, verificado
- **F-01 (ronda 2), cerrado.**
  - La prueba lanza `sys.executable -I -c` y lee `GET /metrics` del `ops_app` del proceso nuevo. No consulta la variable del módulo y exige `vectra_core_write_attempts_total 0.0`.
  - Base: 15 passed. Sola: 1 passed en 2,4 s. Archivo entero en orden inverso, con la prueba después de los `POST`: 15 passed (`mock-reverse.log`).
  - **M22** (`WRITE_ATTEMPTS.inc(3)` al final de `metrics.py`): `1 failed, 14 passed`, y la que falla es solo la nueva (`mut-M22.log`).
  - **Variante M23**, el contador perezoso: la serie no existe hasta el primer `inc`, y `/metrics` de un proceso nuevo da `[]`. La prueba nueva la atrapa por `StopIteration` en el subproceso y `check=True`. Caen 3 pruebas, entre ellas la nueva (`mut-M23-lazy.log`).
- **F-02 (ronda 2), cerrado.**
  - La prueba parametrizada afirma sobre la lectura de vuelta (`case_row`, `job_row`, outbox vacío).
  - **M21b** (las tres guardas con `OR true`), con `test_worker.py` entero y sin la PBT: `3 failed, 38 passed`. Caen `[model_frozen]`, `[retryable_503]` y `[scoring_403]` (`mut-M21b-full.log`).
  - **Una rama a la vez:** `_FROZEN` → solo `[model_frozen]`; `_RETRY` → solo `[retryable_503]`; `_ESCALATE` → solo `[scoring_403]`, `1 failed, 40 passed`. Cada rama muere por su caso.
  - Mi primer intento con `_ESCALATE` no aplicó la mutación por un error de mi script. Esas corridas sin mutar quedaron renombradas como `worker-base-unmutated.log` y `escalate-attempt1-unmutated.log`, y repetí la mutación bien aplicada.
- **F-04 (ronda 2), cerrado.** `services.md` dice que el caso normal termina cuando terminan las llamadas en vuelo, que tarda segundos con un scoring sano y que 20 s es un tope. Conserva el peor caso de ≈ 34 s. Coincide con lo que medí en la ronda 2.
- **`# noqa: S603`, justificado.** Los argumentos son el intérprete y una constante, sin entrada externa. Ya hay precedentes con el mismo motivo (`bias-monitoring/tests/**`), y `pyproject.toml` ignora S603 en `platform/**`.
- **Candidata del puerto 8081:** está en `CANDIDATAS.md`.

## Tareas candidatas (defectos reales fuera de alcance)
- PBT-U8-01: el comando `cfg_down` modela mal la caché de `serving-config` (F-01). Si el orquestador no lo admite en esta tarea, va como candidata con el blob de `@reproduce_failure` de arriba.

## Rutas de transcripciones largas
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev3-u08-t04/`:
- `summary.txt`
- `check.log`
- `pbt-repro.log`
- `pbt-repro-diag.log`
- `ca3.log`
- `ca4.log`
- `ca6a.log`
- `ca6b.log`
- `ca6c.log`
- `ca7.log`
- `mut-M22.log`
- `mut-M23-lazy.log`
- `mut-M21b-full.log`
- `mut-M21b_FROZEN.log`
- `mut-M21b_RETRY.log`
- `mut-M21b_ESCALATE.log`
- `mock-alone.log`
- `mock-reverse.log`
- `mguard.py`
- `run-cas.sh`
- `containers-before.txt`

```
VEREDICTO: NO-VERDE
ROJO|case-management/tests/property/test_case_machine.py (cfg_down / late_after_thaw), CA-9|PBT-U8-01 falla con algunas semillas en make check: el modelo ignora la caché de serving-config (de la ronda 2, reproducible)
AMARILLO|business-rules.md BR-U8-08|La frase del reloj presenta como necesaria una condición suficiente y nombra el reloj de quien recrea
INFORME: revisiones/U08-T04/ronda-3.md
```
