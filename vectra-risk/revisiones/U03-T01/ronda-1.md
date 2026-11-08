# Ronda 1 — U03-T01

VEREDICTO: NO-VERDE (un único NARANJA de cobertura y ningún ROJO; se arregla con una prueba)

Todos los comandos se corrieron sobre el worktree en `488e638` (base `7a0e45f`). La tarea coincide con el blob `d68907e6…`. Las mutaciones se hicieron en una copia sacada con `git archive`. **El worktree quedó limpio** (`git status --short` vacío; solo hay cachés ignoradas).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Esqueleto y contrato «sin E/S» | `uv sync --frozen && uv run lint-imports --config decision-registry/.importlinter` | pasa, exit 0, `KEPT`. Rojo propio en la copia: `socket`, `os`, `pathlib`, `asyncio`, `httpx`, `subprocess`, `urllib.request`, `vectra_common.deps` en `verify.py` y `psycopg` en `projections.py` dan exit 1 los nueve |
| 2 | Migraciones, un caso por viñeta | `uv run pytest decision-registry/tests/integration/test_migrations.py -v -rs` | pasa: **67 pasan, 0 omitidas, 26,2 s** contra un contenedor real |
| 3 | `check` de la unidad | `make -C decision-registry check` | pasa, exit 0 (ruff, mypy strict, lint-imports y 67 pruebas en 25,9 s) |
| 4 | U1 sigue en verde | `make -C platform check` | pasa, exit 0 (`pass: 309, fail: 0`; conftest 322/322; kyverno 81/81) |

**Cada viñeta del Paso 2 tiene un caso, y ese caso falla cuando se rompe la migración.** Apliqué 27 mutaciones, una a la vez, y en 25 cayó al menos un caso:
- **Trigger y TRUNCATE:** el trigger solo en la madre, sin el de las particiones.
- **Grants de `registry_entries`:** `TRUNCATE` y `DELETE` a `registry_app`; `INSERT` a `registry_aggregator`; `INSERT` y `UPDATE` a `registry_ondemand`; `SELECT` a `registry_health`.
- **Génesis:** sin el `CHECK` de génesis única.
- **Particiones:** sin `DEFAULT`, que rompe la plantilla y las 65 pruebas dan error.
- **`idempotency_key`:** sin el trigger de unicidad.
- **Índice de `recorded_at`:** sin él.
- **Tablas derivadas:** `INSERT` en `monitoring_daily` a `registry_app`; `TRUNCATE` de derivadas a `registry_aggregator`; `SELECT` de `monitoring_case_index` a `registry_verifier`; sin `CHECK (count >= 0)`; sin la fila de `monitoring_watermark`.
- **`integrity_checks`:**
  - Grants: `UPDATE (requested_by)` a `registry_ondemand`; `DELETE` a `registry_ondemand`; `UPDATE` a `registry_app`; `INSERT` a `registry_verifier`.
  - `CHECK`: sin el de `report`, con el de `report` en un solo sentido, sin el de `reason` y sin el de progreso.
  - Índice parcial: sin `en_curso`.

Las dos únicas que sobreviven están en F-01.

## Desvíos declarados por el codificador
1. **`registry_idempotency_keys` con trigger `SECURITY DEFINER`.** Es una **necesidad técnica real**. Comprobado en `postgres:17.9`: tanto `CREATE UNIQUE INDEX ON p (k)` como `UNIQUE (k)` dan `ERROR: unique constraint on partitioned table must include all partitioning columns`. BR-U3-04 paso 0 pide buscar la llave, no un `ON CONFLICT`, así que la tabla aparte basta. **No encontré hueco de privilegios.** Lo leí de vuelta en una base migrada:
   - La función es de `registry_migrator` y lleva `proconfig = search_path=public, pg_temp`, con `pg_temp` al final.
   - Su `proacl` solo incluye a `registry_migrator`. `registry_app` recibe `InsufficientPrivilege` al llamarla.
   - `public` es de `pg_database_owner`. Sin `CREATE` para `PUBLIC`, ningún rol de app puede sombrear la tabla.
   - Sobre `registry_idempotency_keys`, ningún rol de app tiene privilegios: los cinco dan `False`.
   - Para el superusuario, `UPDATE`, `DELETE` y `TRUNCATE` lanzan `RaiseException`.
   - Un `INSERT` directo en una partición con la llave repetida da `UniqueViolation`.

   Es un desvío del texto de domain-entities §1 («`uuid UNIQUE`»), pero la semántica se conserva. Si se corrige el diseño lo decide el usuario; ya está en CANDIDATAS.
2. **Triggers de fila y de TRUNCATE por separado, también en cada partición.** Es una **necesidad técnica real**. En 17.9 un trigger por sentencia `BEFORE TRUNCATE` en la madre no impide `TRUNCATE p0`, y `TRUNCATE … FOR EACH ROW` da `not supported`. Las particiones futuras necesitan el suyo (CANDIDATAS).
3. **La génesis depende de `REGISTRY_CHECKPOINT_KEY_FINGERPRINT`.** Es una **necesidad real**: BR-U3-10 y §2.2 exigen la huella en la génesis. Leer la variable de entorno o `config.attributes` es una decisión de implementación. Hay prueba de que, sin la huella, la migración falla y no deja tablas. No hace falta que decida el usuario; el cableado del Job F44 queda para el Bloque E.
4. **`registry_head`.** **No es un desvío.** domain-entities §1.2 da a `registry_app` «`SELECT` sobre la vista de cabeza». El plan de ejecución usa Merge Append con Index Scan Backward sobre las PK.
5. **`postgres:17.9-trixie`.** Es la misma versión mayor y menor y la misma distro que `imageName` de U1, y se deriva de él. No comprobé por mi cuenta lo del entrypoint de CNPG. Es razonable y está registrado en CANDIDATAS. Que esto valga como verificación de la imagen exacta lo decide el usuario o el Paso 18.
6. **Los `CHECK` de `monitoring_daily`.** **No es un desvío**: §1.3 los exige («`CHECK` de cada valor contra el catálogo de U0 §2.2»). Los valores coinciden exactamente con `Sex`, `RangoEdad`, `Region`, `Stratum`, `Band`, `Outcome`, `FinalOutcome` y `Decision` de U0, y `ENTRY_TYPES` con `EntryType`. Ver AMARILLO F-02.

**Alcance:** `reference-model/` no se tocó (diff vacío). En el `pyproject.toml` raíz:
- Se agregó el miembro del workspace, como se pedía.
- Se agregó `vectra-decision-registry` como dependencia de la raíz. Es necesario para que `uv sync --frozen` sin `--all-packages` instale el paquete y CA-1 funcione, así que no hay desborde.
- Se agregaron un marcador `integration` y los ignores de ruff.

En `uv.lock` solo entran alembic, mako, markupsafe, psycopg, psycopg-binary, sqlalchemy, tzdata, zstandard y el paquete propio. `testcontainers` ya estaba.

## Hallazgos
### F-01 · NARANJA · migrations/versions/0001_registry_entries.py:167-181 · La protección de solo-anexar de `registry_idempotency_keys` no tiene prueba
El codificador afirma (CANDIDATAS y comentario de la línea 124) que la tabla tiene «la misma protección de solo-anexar». La protección existe: mi sonda lo confirmó. Pero ninguna prueba la cubre:
- Mutación `upd-idem-quitado`, que quita el trigger de `UPDATE/DELETE` de la tabla: **67 pasan**.
- Mutación `trunc-idem-quitado`, que quita su trigger de `TRUNCATE`: **67 pasan**.

Esta tabla es ahora la que sostiene la unicidad del diseño. Si un superusuario borra una fila, se habilita un duplicado. Falta un caso parametrizado (`UPDATE`, `DELETE` y `TRUNCATE` de superusuario sobre `registry_idempotency_keys` → `RaiseException`) y uno de privilegios de los roles de app. No incumple ninguna viñeta del plan: es cobertura ausente del desvío propio. Bajo RL-1 a RL-5 no bloquea por sí solo; lo dejo en NARANJA porque es su severidad real.

### F-02 · AMARILLO · 0001:28-40, 0002:19-29 · Catálogos de U0 copiados como literales y sin prueba de paridad
Hoy son correctos, y congelarlos en una migración es defendible. Pero «derivados del catálogo» no es exacto: son copias. Una prueba de que `ENTRY_TYPES == tuple(EntryType)` y de que `GROUPS`, `BANDS` y demás coinciden con `get_args(...)` de U0 evitaría que se desvíen en silencio.

### F-03 · AMARILLO · 0001:158 · El comentario nombra una función que no existe
El comentario dice «debe llamar a `registry_guard_truncate`», pero esa función no existe. El trigger usa `registry_forbid_mutation` y se llama `<tabla>_no_truncate`. Esto confunde al PR anual de particiones.

### F-04 · AMARILLO · 0001:56 · El formato de los sellos de tiempo de la génesis no es fijo
`now.isoformat()` omite los microsegundos cuando valen 0, así que el formato de `occurred_at` y `recorded_at` en `canonical` no es estable; conviene usar `isoformat(timespec="microseconds")`. Además, `recorded_at` sale del reloj de Python y no de la base, aunque domain-entities §1 dice «De la base». Importa para el `chain.canonicalize` del Paso 3.

### F-05 · AMARILLO · 0001:42 y 98 · Mensaje de unicidad y forma de la génesis
- La violación de unicidad sale de `registry_idempotency_keys_pkey` en un trigger AFTER, no de `registry_entries`. El append del Bloque D no debe depender del nombre de la restricción.
- `correlation_id` de la génesis es `"0"*32`, que no es un trace-id W3C válido.

## Tareas candidatas (defectos reales fuera de alcance)
- domain-entities §1 marca `model_version_id` y `policy_version_id` como «Índices», pero la lista explícita de índices y el plan los omiten. La migración sigue la lista. Hay que aclarar el diseño.
- domain-entities §1 dice `idempotency_key uuid UNIQUE`, cosa imposible tal como está escrita en una tabla particionada por `seq`. Hay que alinear el texto con `registry_idempotency_keys` (ya está en CANDIDATAS; lo decide el usuario).

**Pendiente de limpieza:** me negaron el permiso para detener el contenedor `postgres:17.9-trixie` que levanté para la prueba de PG17. Fue lanzado con `--rm` y su id está en el scratchpad del orquestador (`pgcid`).

```
VEREDICTO: NO-VERDE
NARANJA|decision-registry/migrations/versions/0001_registry_entries.py:167-181|La protección de solo-anexar de registry_idempotency_keys no tiene prueba (dos mutaciones sobreviven)
INFORME: revisiones/U03-T01/ronda-1.md
```
