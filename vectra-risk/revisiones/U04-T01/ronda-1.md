# Ronda 1 — U04-T01

VEREDICTO: NO-VERDE

En el código no encontré ningún ROJO ni ningún NARANJA. El veredicto es NO-VERDE por una sola razón: no pude correr CA-5 ni CA-7 completos, y VERDE exige que yo haya corrido todos los criterios. Todo lo que sí corrí pasa. Por RL-3 (solo un ROJO bloquea), si sigue adelante lo decide el orquestador.

Revisé el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u04-t01` en `14ff16c` y comprobé el diff `0a5c990..14ff16c`. Al terminar, el worktree está limpio. Solo hay cachés ignoradas: `.import_linter_cache/` y un `platform/.charts/` a medio bajar, que dejó `charts.sh`.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | import-linter | `uv sync --frozen && uv run lint-imports --config governance/.importlinter` | pasa: los 2 contratos KEPT, código 0 |
| 2 | Extras separados | los dos `uv export ... \| grep -Eic` | pasa: `0` y `3` |
| 3 | Estructura de §1 | el bucle `test -e` | pasa: ninguna línea FALTA y aparece `OK-sin-frontend` |
| 4 | Migraciones | `uv run pytest governance/tests/integration/test_migrations.py -v -rs` | pasa: 40 passed en 12,27 s (13,7 s reales, con el contenedor de verdad), ninguno omitido |
| 5 | `psql` independiente | el comando de CA-5 tal cual | **no se pudo correr**: el permiso de `docker run -p 55432:5432` me lo negaron dos veces, también después de que el usuario dijo «te doy permisos». También me negaron un script equivalente con Testcontainers, y no lo intenté de otra forma |
| 6 | `make -C governance check` | el de la tarea | pasa: ruff, `mypy --strict` (11 archivos), 2 KEPT, 40 passed, código 0 |
| 7 | `make -C platform check` | el de la tarea | **no se pudo correr**: `charts.sh` falló con `504 Gateway Time-out` al bajar alloy-1.15.0 de github.com. Corrí a mano las partes que dependen de `uv`, ver F-02 |

El diff no toca `platform/`: `git diff --name-only 0a5c990..14ff16c | grep -c '^vectra-risk/platform/'` da `0`. Fuera de `governance/` solo cambian `pyproject.toml`, `uv.lock`, el plan, la bitácora y la tarea.

## Hallazgos

### F-01 · NARANJA · CA-5 · Lectura de vuelta con `psql` sin evidencia fresca (entorno, no código)
No pude correr CA-5. Lo que cubren las pruebas que sí corrí:
- **Cubierto, con el mismo SQL contra la misma imagen `postgres:17.9-trixie`:**
  - `test_estructura_declarada` lee las tablas en `pg_tables` y comprueba que los índices únicos parciales son exactamente `{model_versions_one_live, policies_one_active, transitions_entity_n}` con el mismo `LIKE '%UNIQUE%WHERE%'`. También comprueba que los triggers son exactamente `{guard_unfreeze, guard_freeze, notify_serving_config}`.
  - `test_ningun_rol_tiene_delete_...` comprueba `DELETE` y `TRUNCATE` con `has_table_privilege` para los 3 roles sobre las 6 tablas, más de lo que pide CA-5.
  - `test_gov_archiver_no_puede_cambiar_state` lee `information_schema.column_privileges` y obtiene `[archived_at, archived_uri]`.
- **Sin cubrir:** el camino de `env.py` que toma `GOVERNANCE_DATABASE_URL`. Las pruebas fijan `sqlalchemy.url` en el `Config` (`governance_pg.py:71`) y nunca usan la variable. Tampoco se cubre migrar como `gov_migrator` por TCP desde el host.

Leyendo `env.py:12` el camino parece correcto, pero leer no es correr. Hace falta que alguien con permiso de Docker corra CA-5 tal cual.

### F-02 · NARANJA · CA-7 · `make -C platform check` sin terminar (entorno)
El objetivo `charts` falla por el 504, antes de llegar a nada del diff. Corrí a mano las piezas de `check-local` que dependen del workspace y de `uv.lock`, que es lo único del diff que puede afectar a U1. Todas terminaron con código 0:
- `ruff check platform vectra-risk-gitops`;
- los tres `generate.py`/`render.py --check`;
- `test_traceability`, `test_runbooks`, `test_waves` y `test_links`.

`uv run pytest platform ...` no dio ninguna salida en 500 s y lo mató el `timeout`, igual que le pasó al codificador. Por lo que dice el Makefile, la prueba de Grafana necesita `DOCKER_HOST`. No pude aislar la causa. `check-tools` necesita `platform/.tools`, que no existe en el worktree.

### F-03 · AMARILLO · `migrations/versions/0001_governance_schema.py:50-51` · `guard_unfreeze` deja salir de `congelado` en dos pasos
Este hallazgo agrupa dos casos de la misma clase: el trigger protege menos de lo que dice el invariante de BR-U4-03.
- **(a)** El trigger solo actúa cuando `NEW.state IN ('activo','retirado')`. `gov_app` tiene `UPDATE (state)`, y el `CHECK` admite `inactivo`. Un `UPDATE ... SET state='inactivo'` desde `congelado` pasa sin variable, y después `inactivo → activo` tampoco lo vigila nadie. Es una reactivación sin resolución de cumplimiento, y BR-U4-03 dice que la única ruta es `frozen-resolution`.
- **(b)** Los cambios de `investigation` solo se vigilan si `OLD.state = 'congelado'`, mientras que P-U4-06 dice «cambios de `investigation`» sin condición.

El código copia la tabla de P-U4-06 al pie de la letra, como pedía la tarea. Por eso es un hueco del diseño y no un desvío del codificador: va como tarea candidata, no se exige aquí. Lo deduje leyendo el trigger. No lo ejecuté, porque no puedo agregar pruebas.

### F-04 · AMARILLO · `tests/integration/test_migrations.py:18-20` · La prueba de «llaves distintas» fija una interpretación propia de UUIDv5
`key()` usa `uuid5(NAMESPACE_URL, f"{entity_type}:{entity_id}:{n}")`. La fórmula del diseño, «UUIDv5(`entity_type:entity_id`, n)», no fija ni el namespace ni cómo se combina `n`. La tarea permitía que la llave la calculara el servicio. Aun así, la prueba no comprueba nada de la migración más allá de que las dos inserciones caben, y el Bloque C/D tendrá que alinear esa fórmula o reescribir la prueba.

### F-05 · AMARILLO · `0001_governance_schema.py:100` · `notify_serving_config` notifica en cualquier `UPDATE`
Notifica aunque no cambie el `etag`, y con `COALESCE(NULL,'')` envía un payload vacío. No hace daño, porque las réplicas recalculan igual, pero sería más limpio filtrar con `WHEN (NEW.etag IS DISTINCT FROM OLD.etag)`.

## Las decisiones de la bitácora, contra el diseño
- **`report jsonb` en `validation_runs`:** cabe en A-2. Correcta.
- **Llave de idempotencia con índice no único:** correcta. BR-U4-17 dice que una transición nueva después de un abandono «reutiliza la llave de la abandonada», y un `UNIQUE` rompería ese camino.
- **Trigger `notify_serving_config` con `pg_notify`:** es la forma que recomienda la tarea. La prueba confirma que antes del `COMMIT` no llega nada, que llega el `etag` correcto y que con rollback no llega nada.
- **Fila génesis de `serving_config` con campos nulos:** la tarea la permite. Coincide con que `gov_app` tenga `SELECT, UPDATE` y no `INSERT`.
- **`guard_freeze` acepta `pendiente_registro`:** correcta, y además necesaria. BR-U4-15 y la excepción de BR-U4-17 aplican el `freeze` antes del ack, y P-U4-06 no exige `confirmada` para el `freeze`.
- **Alcance:** no hay desbordes. No hay handlers ni `vectra_disparity`, y la A-1 queda como comentario en `governance/pyproject.toml`.

## Tareas candidatas (defectos reales fuera de alcance)
- Precisar P-U4-06 y BR-U4-03: `guard_unfreeze` debería rechazar **cualquier** salida de `congelado` que no sea `activo` o `retirado` con resolución, y definir el alcance de los cambios de `investigation` (F-03).
- Fijar en el diseño la fórmula exacta de UUIDv5 (namespace y nombre) para BR-U4-17 (F-04).
- `pytest platform` se cuelga sin dar salida cuando no hay `DOCKER_HOST`: debería fallar rápido o declarar que lo omite.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/ca7.log` (el 504 de `charts.sh`)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/tasks/bq6s7vjs3.output` (las piezas de `platform` y el `timeout` de su pytest)

```
VEREDICTO: NO-VERDE
NARANJA|CA-5|psql independiente no ejecutado: docker run -p denegado por permisos (sin cubrir el camino GOVERNANCE_DATABASE_URL de env.py)
NARANJA|CA-7|make -C platform check no termina: 504 en charts.sh y pytest platform sin salida en 500 s
AMARILLO|governance/migrations/versions/0001_governance_schema.py:50|guard_unfreeze deja salir de congelado en dos pasos (copia literal de P-U4-06; tarea candidata)
AMARILLO|governance/tests/integration/test_migrations.py:18|la fórmula UUIDv5 de la prueba no está fijada por el diseño
AMARILLO|governance/migrations/versions/0001_governance_schema.py:100|NOTIFY en cualquier UPDATE, con payload vacío si el etag es nulo
INFORME: revisiones/U04-T01/ronda-1.md
```
