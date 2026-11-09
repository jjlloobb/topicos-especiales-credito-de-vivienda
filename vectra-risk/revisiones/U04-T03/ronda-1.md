# Ronda 1 — U04-T03

VEREDICTO: VERDE (bajo RL-2: no hay ningún ROJO. El único NARANJA, F-01, pasa a `CANDIDATAS.md`. Sin RL-2 el veredicto sería NO-VERDE por F-01)

Comprobaciones previas:
- Hash de la tarea: `git hash-object` = `4d35ded9ae7cec9916bb0799635ac9c8fade9f3a`. Coincide.
- Rama en `108161a`. Diff `ef4736c..108161a`: 24 archivos.
- El worktree quedó limpio después de la revisión (`git status --short` vacío). Los mutantes que corrí viven solo en el scratchpad.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Migración `0004` (Q-1, Q-2, Q-4) | `uv run pytest governance/tests/integration/test_migrations.py -v` | pasa: 57 passed in 15.07s (los 40 de U04-T01 más 17 nuevos: `congelado→{inactivo,aprobado,…}` con y sin variable, `investigation` true→false, `investigation` en `activo`, el camino de `investigar`, NOTIFY sin cambio de `etag` y sin payload vacío) |
| 2 | Paso 8, PBT-U4-01 y PBT-U4-07 | `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_stateful_*.py governance/tests/integration/test_evidence.py -v` | pasa: 17 passed in 25.07s (PBT-U4-07 tardó 9.30s y PBT-U4-01 5.68s; hay un caso por cada viñeta). Ver la nota sobre el tiempo |
| 3 | `CompensationEventPending` con `promtool` | `promtool check rules …` y `promtool test rules …`, con el `promtool` del árbol principal | pasa: `SUCCESS: 1 rules found` / `SUCCESS`, rc=0. Es la versión 3.15.1, que coincide con `PROMETHEUS_VERSION=v3.15.1` de `tools.env` (idéntico en los dos árboles) |
| 4 | Paso 9: convergencia y pools | `uv run pytest governance/tests/integration/test_convergence.py governance/tests/integration/test_pools.py -v` | pasa: 11 passed in 43.18s (la prueba de la base pausada de verdad dura 32.24s) |
| 5 | Una sola fórmula de la llave | `git grep -nE 'uuid5\(' … \| grep -v …` y `git grep -c 'urn:vectra:governance' -- governance/src` | pasa: el primero no imprime nada y el segundo da `evidence.py:1`. Calculé aparte el UUID fijo de la prueba (`35cb2877-…7976`) y coincide |
| 6 | `make check` de la unidad y de U1 | `make -C governance check` y `make -C platform check`, más el respaldo `test_ci.py` | governance: rc=0, ruff limpio, 2 contratos kept, 167 passed in 89.69s, **pero el objetivo `rules` se omitió** (F-01). platform: `check-local` pasa y `check-tools` falla en `test -x platform/.tools/bin/kyverno…`, como la tarea preveía. Respaldo `test_ci.py`: 274 passed |

Notas sobre lo que el codificador pidió mirar:

1. **PBT-U4-07 sin precondición.** Reproduje su mutante en una copia del scratchpad, cargada con `PYTHONPATH`: quité el filtro `status == pendiente_registro` y `_still_valid` de `_finish_locked`. Resultado: `1 failed in 55.83s`. El contraejemplo es `freeze_during_a_promotion(ack_only=True, freeze_first=False, i=0, mode='down', settle=False, who='a')`, y lo corta `guard_unfreeze` (`InsufficientPrivilege … congelada solo sale a activo o retirado, no a inactivo`). El mutante muere, aunque lo detecta la defensa de la base de datos, no un invariante de la máquina. Matices en F-03.
2. **Sondeo de 0,5 s.** NFR-U4-04 pide confirmar la copia «al menos cada 1 s», y NFR-U4-05 y P-U4-01 piden convergencia ≤ 1 s también con `LISTEN` caído. Con un sondeo de 1 s exacto, el peor caso supera 1 s por el tiempo de la consulta, así que 0,5 s cumple la letra y la cota. No es un hallazgo. La prueba corta de verdad la conexión `governance:b:listen` con `pg_terminate_backend` (cuenta 1) e impide la reconexión.
3. **`make -C platform check`.** El diff no toca U1. El árbol principal tampoco tiene completo `platform/.tools` (faltan `kubeconform`, `egctl` y `k6`), así que `check-tools` no se puede correr entero en ninguno de los dos. Se acepta el respaldo que prevé la tarea.
4. **`promtool` del árbol principal.** Su versión coincide con `tools.env`. CA-3 queda verificado por mí.

**Tiempos.** Los perfiles PBT terminan en unos 9 s porque las máquinas fijan `max_examples=25` (variable `U4_STATEFUL_EXAMPLES`) y `stateful_step_count=40`, sea cual sea el perfil. El mutante necesitó 55 s para morir, así que no hay salto silencioso: las máquinas corren de verdad contra PostgreSQL.

## Hallazgos

### F-01 · NARANJA · `governance/Makefile` (objetivo `rules`) · la prueba de la regla se omite en silencio y nadie la corre en el CI
- **Qué pasa:** `make -C governance check` termina en código 0 imprimiendo `promtool no disponible: se omite (lo corre el CI)`.
- **Por qué es falso que la corra el CI:**
  - `check-tools` (`platform/Makefile:41-52`) solo corre `promtool` sobre `platform/observability/rules`.
  - `.github/workflows/tests.yml` solo corre `pytest`.
  - Ningún workflow ni objetivo corre `governance/observability/tests/*.yaml`.
- **Consecuencia:** la prueba de `CompensationEventPending` solo existe si alguien la corre a mano. `test_observability.py` lee el YAML, pero no evalúa la regla.
- **Contexto:** la premisa venía de la propia tarea («el CI corre `check-tools`»), por eso no lo marco ROJO. CA-3 pasa con mi ejecución.
- **Corrección propuesta:** que `rules` falle si no encuentra `promtool`, o agregar las reglas de governance a `check-tools` o al CI.

### F-02 · AMARILLO · `tests/property/test_stateful_*.py:44/48` · `HYPOTHESIS_PROFILE=ci` no cambia nada en las máquinas stateful
Los 25 ejemplos están fijos por variable de entorno, sin pasar por el perfil. Está documentado y es la misma decisión que U3, pero el comando de CA-2 sugiere 500 ejemplos.

### F-03 · AMARILLO · `evidence.py:674` (`_still_valid` en `_finish_locked`) · la mitad «estado == from_state» de la revalidación no la mata ninguna prueba
Corrí dos mutantes más estrechos contra PBT-U4-07 y `test_evidence.py`, y los dos sobreviven (16 passed):
- mut2: sin `_still_valid` en la TX2;
- mut3: el filtro de estado deja pasar las `descartada`.

Cada mitad cubre a la otra en los escenarios probados. Con el `GLOBAL_LOCK`, `_ensure_free` y el `freeze` que descarta dentro de su propia transacción, mut2 parece un mutante equivalente. Conviene dejarlo escrito o cubrirlo con un caso que lo distinga.

### F-04 · AMARILLO · `evidence.py:131` y `:118-119` · literales en el cliente real
La ruta `"/v1/entries"` está incrustada en vez de tomarse de `vectra_contracts.routes`, y los timeouts `2.5`/`1.0` van en la firma. U3 hace lo mismo con la ruta, y estos valores no los ve el usuario.

## Tareas candidatas (defectos reales fuera de alcance)
- Correr `promtool` sobre `governance/observability/` en el CI y en `check-tools` (es la solución de fondo de F-01, en U1).
- El `runbook_url` `governance/runbooks/compensation-event-pending.md` todavía no existe (los runbooks son del Paso 17, ya diferidos).
- `ruff format --check` marca 14 archivos de governance (lo anotó el codificador; `check` solo corre `ruff check`).
- La rama `source_comparison`, `source_candidate_for` y la parte de fuentes de PBT-U4-07 siguen diferidas por P-5 y Q-6. No es un hallazgo.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/gov-check.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/plat-check.txt`
- Mutantes: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/aedc6fa7-798a-4ae8-9684-b7a8b42aa668/scratchpad/mut1`, `…/scratchpad/mut2` y `…/scratchpad/mut3`

| SEVERIDAD | ubicación | resumen |
|---|---|---|
| NARANJA | governance/Makefile (objetivo `rules`) | `check` omite `promtool` en silencio y ni el CI ni `check-tools` corren las reglas de governance |
| AMARILLO | tests/property/test_stateful_*.py:44/48 | el perfil `ci` no cambia los 25 ejemplos de las máquinas stateful |
| AMARILLO | evidence.py:674 | la mitad `_still_valid` de la revalidación de la TX2 no la mata ninguna prueba (probable mutante equivalente) |
| AMARILLO | evidence.py:118-131 | ruta `/v1/entries` y timeouts como literales en el cliente real |

```
VEREDICTO: VERDE
NARANJA|governance/Makefile:rules|check omite promtool en silencio y ningún CI corre las reglas de governance (pasa a CANDIDATAS por RL-2)
INFORME: revisiones/U04-T03/ronda-1.md
```
