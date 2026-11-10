# Ronda 1 — U08-T01

VEREDICTO: NO-VERDE

El veredicto es NO-VERDE por un solo NARANJA (F-01). No hay ningún ROJO. Los ocho criterios de aceptación pasan con mi propia ejecución. Según RL-3 de `demo-kind-alcance.md` §6, en este bucle solo bloquea un ROJO. Esa decisión es del orquestador. Yo no suavizo la severidad.

## Criterios de aceptación, verificados por mí (worktree `u08-t01`, sha 6555e52, blob de la tarea f5d854a6 coincide)
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | Tres contratos de imports en `KEPT` | `uv sync --frozen && uv run lint-imports --config case-management/.importlinter` | pasa: 3 kept, 0 broken, exit 0 |
| 2 | Estructura de §1, sin `frontend/` | el bucle `test -e` de la tarea | pasa: ninguna línea `FALTA`, `OK`. No hay `Dockerfile`, `Chart.yaml` ni `tests/e2e` |
| 3 | Guardia de AST de `credit` | `uv run pytest case-management/tests/unit -v` | pasa: 15/15 |
| 4 | Constantes tipadas | el mismo comando | pasa: 6/6. `WORKER_WORST_CASE` es una suma de constantes, no un literal |
| 5 | Migraciones con los roles reales | `uv run pytest case-management/tests/migrations -v -rs` | pasa: 108 passed en 16,4 s, 0 skipped, exit 0. Ver `ca5.txt` |
| 6 | Sin `SET ROLE` ni pooler | `! grep -rniE ... && echo OK` | pasa: `OK` |
| 7 | Plan marcado | `grep -nE "^- \[x\] \*\*Paso [123] " ...` | pasa: 3 líneas con `(U08-T01)`. El diff del plan son solo esas 3 casillas |
| 8 | `check` de U8 y de U1 | `make -C case-management check`; `platform/install-tools.sh` y luego `make -C platform check` | pasa: U8 en exit 0 (ruff, mypy --strict, 3 contratos, 129 passed). U1 en exit 0 (802 passed, 81 pruebas de helm, conftest 707/3/343, kyverno 48 y 354 pass) |

Edad de la evidencia:
- Los 16 s de CA-5 son coherentes con un contenedor real: imagen `postgres:<versión de CNPG>` sacada de `platform/data/chart/values.yaml` y roles leídos de `clusters.case-db.roles` con `login`.
- `case_migrator` migra como dueño de la base.
- Cada prueba se conecta con el rol real, sin `SET ROLE`. El superusuario solo prepara datos (con `session_replication_role = replica`) y lee de vuelta.
- Toda viñeta del Paso 3 y los tres casos de `ever_degraded` tienen su prueba con nombre propio, y cada prueba que cambia estado lee el resultado de vuelta con `SELECT`.
- El worktree quedó limpio al terminar (`git status --short` vacío). `platform/.tools/` está en `.gitignore`.

## Hallazgos

### F-01 · NARANJA · `tests/migrations/test_jobs_keys_and_retention.py` (y `0003_guards.py` `GUARD_VENCIDO`) · Tres de las cuatro filas de `guard_vencido` no se prueban
En PostgreSQL, los triggers `BEFORE` se disparan por orden alfabético del nombre: `guard_ever_degraded`, `guard_transition`, `guard_vencido`. `guard_transition` rechaza primero tres casos que P-U8-05 asigna a `guard_vencido`:
- fila 1: `vencido` escrito por un rol que no es `case_retention`;
- fila 2: `decidido` → `vencido`;
- fila 4: `case_retention` escribe otro estado.

Las pruebas aceptan cualquier guarda o piden la equivocada:
- `test_case_app_writes_vencido_raises` y `test_guard_vencido_rejects_a_decided_case` usan `match="guard_"`;
- `test_case_retention_writes_listo_raises` usa `match="guard_transition"`.

Lo demostré con una sonda fuera del repo: migré una base y, como superusuario, reemplacé `guard_vencido` por una versión que solo comprueba la fecha. Los tres casos siguen lanzando `RaiseException`, siempre con `guard_transition: ... no esta permitida al rol ...`. Script: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/probe/probe_vencido.py`.

P-U8-05 llama a este trigger la «cuarta barrera». Hoy sus filas 1, 2 y 4 pueden borrarse sin que la suite lo note. Solo la fila 3, la del plazo, está cubierta, porque ese caso pasa `guard_transition`. El criterio literal («→ excepción») se cumple, así que es NARANJA y no ROJO. Corregirlo exige probar `guard_vencido` aislado y afirmar su mensaje `guard_vencido: ...`. Una forma es deshabilitar `guard_transition` como dueño en la base de esa prueba.

### F-02 · AMARILLO · `0001_case_schema.py` `evaluation_jobs_one_live_job_per_case` · Índice único sin predicado (desvío 3)
Domain-entities §2.1 pide un índice «único parcial», pero la tabla no tiene ninguna columna de estado. Las filas se borran en `listo`, `modelo_congelado` y `vencido` (BR-U8-08, BR-U8-20), así que toda fila está viva y el índice completo equivale al parcial. Sí hay un hueco: BR-U8-09 no dice que el escalamiento a `no_disponible` borre el trabajo. Si U08-T03 lo conserva, el `INSERT` del `retry` choca con este índice. Lo anoto como tarea candidata.

### F-03 · AMARILLO · `0001_case_schema.py` `retention_runs.finished_at NOT NULL` · Difiere de `finished_at?` en domain-entities §1.4
El mismo párrafo del diseño dice que la fila se escribe al terminar, con las dos fechas. El cambio es coherente, pero es un desvío que no está registrado como tal (el desvío 6 lo menciona sin la nulabilidad).

### Desvíos de la bitácora contrastados con el diseño (sin hallazgo)
La bitácora enumera 9 desvíos, no 8.
- **4. `vectra_common` en `root_packages`.** import-linter no acepta un subpaquete externo. Con `allow_indirect_imports`, igual que en `governance/.importlinter`, queda permitido el camino `vectra_case` → `deps` → `httpx`. `vectra_common/__init__` no importa `deps`. Es aceptable.
- **5. `SELECT` por columna de `case_retention` sobre `cases`.** Coincide con el Paso 3 y con `logical-components.md` línea 109. INF-U8-01 rige `ever_degraded` del worker. Correcto.
- **6. Columnas y CHECK no dictados.** `decision_id` como PK, la PK de `explanation_views` y `CHECK (attempts BETWEEN 0 AND 6)` en `cases`. Son coherentes con domain-entities §3.3 y con PBT-U8-01 (`attempts ≤ 6`). El estado `descartada` de `evidence_outbox` coincide con §3.1.
- **7. `RAISE EXCEPTION` con P0001.** El diseño no fija ningún código. Separar P0001 de 42501 hace que las pruebas sean más precisas. Correcto.
- **8. P-1.** Se aplica como lo recomienda la tarea. `created_at` y `updated_at` se leen de vuelta, y se cubren 18 casos de valores inválidos, sin tablas después.
- **P-2.** Se aplica la recomendación: `verify-full` queda para el Paso 20.
- **Literales.** Los plazos 10, 2 y 30 de la primera revisión salen de P-U8-05 y `env.py` siempre los sobrescribe. `RECONCILER_BACKOFF_MIN` y `_MAX` (1 s y 300 s) salen de P-U8-04. No son literales en un punto de decisión.
- **Alcance.** Sin desborde: los módulos de los Bloques C a I están vacíos con docstring, no hay chart, Dockerfile ni frontend, y no se tocó U0 ni U1.

## Tareas candidatas (defectos reales fuera de alcance)
- Precisar en BR-U8-09 o domain-entities §2.1 si el escalamiento a `no_disponible` borra el trabajo. Con el índice único completo, el `retry` lo necesita (afecta a U08-T03).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/ca5.txt` (CA-5)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/ca8a.txt` (`make -C case-management check`)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/ca8b.txt` (`make -C platform check`)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/install.txt` (`install-tools.sh`)

```
VEREDICTO: NO-VERDE
NARANJA|case-management/tests/migrations/test_jobs_keys_and_retention.py (guard_vencido, 0003_guards.py)|Las filas 1, 2 y 4 de guard_vencido quedan tapadas por guard_transition y ninguna prueba las ejerce
INFORME: revisiones/U08-T01/ronda-1.md
```
