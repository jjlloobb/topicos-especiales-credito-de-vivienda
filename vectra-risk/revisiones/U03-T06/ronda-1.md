# Ronda 1 — U03-T06

VEREDICTO: NO-VERDE

The diff has no ROJO and no NARANJA. Every finding against the work is AMARILLO. The verdict is NO-VERDE only because I could not finish my own run of CA-2 and CA-4: I can't confirm `make -C decision-registry check` exiting 0 under the current load, and I didn't finish four of the seven unit checks. Rerun those under lower load (see "Para cerrar") and this should go to VERDE. Under RL-4 (only a ROJO blocks), the diff is not blocked.

Worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u03-t06`, HEAD `9bb355b`, base `fe0c9f3`, `origin/main` = `09dd9d8`. The task hash matches (`70e003a…`). The worktree is clean after the review.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Paso 19 N/A | `test ! -d decision-registry/frontend` | passes, rc 0 |
| 2a | `platform check` | `make -C platform check` | passes: 802 passed (22 min 37 s, load around 40); conftest 81; Kyverno 707/343/3; integration 354 pass, no errors |
| 2b | `decision-registry check` | `make -C decision-registry check`, twice | **not confirmed**. In both runs the only F is `test_queries.py::test_f04_300_mil_filas_diarias_con_12_rangos_responden_en_menos_de_2_s`. Run alone: `assert 2.776 <= 2.0`, load average 38 to 47. Both runs were later killed by an external SIGTERM (exit 144) before the summary. |
| 2c | No code change | `git diff --stat fe0c9f3 / origin/main -- vectra-risk/decision-registry/` | empty in both |
| 3 | Traceability and sections | `test_traceability.py --unit decision-registry --all`, `--section logic`, `--section api`; the CA-3 `grep`; `git diff … \| grep "^-\|"` against base and origin/main | passes: 41 ids, rc 0; all 5 sections present (lines 5/33/66/78/89); "sin filas quitadas" |
| 4 | RL-4, all units | private runs | governance rc 0 (1601 s); platform rc 0. Contracts, reference-model and model-serving were not completed (killed externally). Identity-edge was not run in full, only the single failing test, at 5 refs (see F-01). |
| 5 | Plan state | `git diff fe0c9f3 / origin/main -- …plan.md` (full diff, not only the grep) | passes: only the lines of Pasos 18 (`[ ]` + note), 19 (`[x] (U03-T06)`) and 20 (`[x] (U03-T06, acotado a la demo)`) change |

## Comprobaciones del encargo
1. **Nothing in `cierre-demo.md` claims more than was run.** I re-ran the cheap steps:
   - P1 lint-imports: `2 kept, 0 broken`
   - P3: 5 passed
   - P4: 36 passed
   - P5: 11 passed
   - P6 and P10: rc 0
   - P15: kind 51 / staging 50 / prod 48 Applications
   For the integration steps I compared the counts with `--collect-only`, and they match the document exactly: P2 98, P7 101, P8 92, P9 8, P11 38, P12 38. Each new deferred row cites its step, the amendment and a destination.
2. **The plan changes only Pasos 18, 19 and 20.** Confirmed (CA-5).
3. **`decision-registry/` doesn't change.** The code directory has an empty diff. Under `aidlc-docs/construction/decision-registry/`, only `evidence/cierre-demo.md` changes, which the task requires. No table row was removed.
4. **CA-4 identity-edge:** pre-existing, not caused by this task (F-01).

## Hallazgos
### F-01 · INFO (pre-existing, outside this diff) · `identity-edge/tests/unit/test_identity_jobs.py:425` · test out of step with `supply-chain.yml`
I ran `pytest … -k t1_supply_chain_skips` at several refs, each in a throwaway worktree:
- `8d2cabd^` (`4e711e6`): **1 passed**
- `8d2cabd`: fails with `Left contains one more item: '…/keycloak/rendered/kind/config-cli-realm.yaml'`
- `0fc6203` (merge of PR #85): fails the same way
- base `fe0c9f3`: fails the same way
- `origin/main` `09dd9d8`: fails the same way

`git log -S"keycloak/rendered/kind/config-cli-realm.yaml" -- .github/workflows/supply-chain.yml` returns only `8d2cabd`: "skip it in Trivy (KSV-0109, U02-T19, PR 85)". That commit added a fifth entry to `skip-files` without updating the test, which comes from `3845024` (U02-T08). It is not in `CANDIDATAS.md`. The coder's account in the logbook is correct.

### F-02 · AMARILLO · `cierre-demo.md`, «Candidatas abiertas» · line numbers in `CANDIDATAS.md` not cited
The task asks for each candidate "con su línea". All six cited candidates exist, at lines 254, 192, 199, 200, 201 and 305, but the document gives none of those numbers.

### F-03 · AMARILLO · `cierre-demo.md`, row «Escenarios 1 a 7 y 9 … del 8» · ambiguous destination
The row lists scenarios that are deferred. Its destination, "Consolidado en U12 Paso 18 (enmienda §8); el resto, cierre completo", suggests U12 covers some of them. Under §8, U12 only covers the scenario that is in scope, which belongs under «Pendiente en U12». The deferred scenarios should point to "cierre completo".

### F-04 · AMARILLO · «Comprobado», Pasos 1 and 15 · partial commands
- Paso 1: the cited acceptance includes `uv sync --frozen`, but the logbook only shows `lint-imports`.
- Paso 15: only `test_waves.py` is listed. The `kyverno test` of `disallow-argocd-auto-sync`, which the plan's acceptance also names, runs inside `platform check` but isn't cited.

### F-05 · AMARILLO · `cierre-demo.md:34` · double blank line after `## Diferido por la demo`
Cosmetic.

## Entorno (not the coder's fault)
- The scratchpad is shared with other reviewers (u09-t04, u04-t09). They wrote to my `check-*.log` files with the same names, so I threw away the first `decision-registry` run and repeated it in `scratchpad/rev-u03t06-r1/`.
- The machine was at load average 38 to 47, and some other process sent SIGTERM to my `make` runs.
- The F in `test_f04_300_mil…` is the known candidate at `CANDIDATAS.md:254` and `:305` (2 s timing limit under load). The cierre already lists it. The diff is documentation only and can't change it.

## Para cerrar (orchestrator, under low load)
`make -C decision-registry check` and `make -C {identity-edge,contracts,reference-model,model-serving} check` from the worktree. Expected result: `decision-registry` rc 0, `identity-edge` rc ≠ 0 only because of F-01, the rest rc 0.

## Tareas candidatas (defectos reales fuera de alcance)
- U2: update `test_t1_supply_chain_skips_exactly_the_three_realm_configmaps` to the 5 `skip-files` entries introduced by `8d2cabd` (U02-T19, PR #85).
- U3 (already filed, `CANDIDATAS.md:254/305`): `test_f04_300_mil…` fails under load (2.78 s > 2 s). It supports P-1 (a): `U03-T07` before U12.
- Loop: give each reviewer its own scratchpad, or require unique log names. Parallel reviewers currently overwrite each other's evidence.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/check-platform.log` (platform, mine)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03t06-r1/` (decision-registry and reference-model interrupted, governance rc 0)

```
VEREDICTO: NO-VERDE
INFO|identity-edge/tests/unit/test_identity_jobs.py:425|Fallo preexistente de 8d2cabd (U02-T19, PR #85), no de esta tarea
AMARILLO|cierre-demo.md «Candidatas abiertas»|Faltan las líneas de CANDIDATAS.md
AMARILLO|cierre-demo.md fila escenarios Paso 18|Destino ambiguo entre U12 y cierre completo
AMARILLO|cierre-demo.md Pasos 1 y 15|Comandos de aceptación citados parcialmente
AMARILLO|cierre-demo.md:34|Línea en blanco doble
INFORME: revisiones/U03-T06/ronda-1.md
```

---

No he terminado, y no voy a poder cerrar CA-2 ni CA-4 en este turno. Mi corrida de `make -C decision-registry check` estuvo 25 horas abierta y solo pasó 353 de 669 pruebas, con 3 min 54 s de CPU en total. Por eso la detuve yo mismo (el código 143 es mi propio SIGTERM). Las otras cuatro unidades no llegaron a empezar. El veredicto sigue en NO-VERDE: el diff no tiene ningún ROJO, pero tampoco tengo una corrida propia de CA-2 y CA-4 que lo respalde.

## Anexo de cierre — U03-T06

VEREDICTO: NO-VERDE

HEAD `b4b0ab2`, merge de `origin/main` `5cf2ebb`. La tarea es el blob `70e003a5…` y coincide. El worktree quedó limpio (`git status --short` vacío) y el diff contra `5cf2ebb` toca solo 4 documentos.

## Corridas
| Unidad | rc | Segundos | Carga antes → después | Causa |
|---|---|---|---|---|
| decision-registry | **sin rc** (la detuve yo) | ≈ 90 000 (25 h) y llegó a 353/669 | 7,44 → 13,67 | Se quedó en la prueba 354, `test_append_stateful.py::test_pbt_u3_01…`, con 3:54 de CPU en 25 h. Hasta ahí, una sola F en la #353, `test_queries.py::test_f04_300_mil_filas_diarias_con_12_rangos_responden_en_menos_de_2_s`: es la candidata conocida (`CANDIDATAS.md:254`), que corrige U03-T07, y no viene del diff, que es solo documentación |
| identity-edge | no corrió | — | — | No empezó porque decision-registry seguía en curso |
| contracts | no corrió | — | — | Igual |
| reference-model | no corrió | — | — | Igual |
| model-serving | no corrió | — | — | Igual |

Contexto de la máquina. El reloj saltó de 11:29 a "1 day 12:33" de uptime, lo que apunta a una suspensión o a que el proceso estuvo parado. Además, en `docker ps` hay más de 15 contenedores de Testcontainers vivos desde hace 25 a 32 h (postgres, minio, vault) y un `make -C bias-monitoring check` corriendo en paralelo. No aislé `test_f04` contra `5cf2ebb`: la máquina no lo permitía. La ronda 1 ya la midió aislada, con 2,776 s contra un límite de 2 s, y el fallo es el mismo de la base.

## Criterios de aceptación
| # | Criterio | Resultado |
|---|---|---|
| 1 | Paso 19 N/A | pasa (ronda 1) |
| 2 | decision-registry y platform check | platform da rc 0 (ronda 1). decision-registry **sin confirmar**, con la misma F de `test_f04` |
| 3 | Trazabilidad y las 5 secciones | pasa (ronda 1) |
| 4 | RL-4, todas las unidades | **sin confirmar**: governance y platform dan 0; las otras 5 no terminaron |
| 5 | Estado del plan | pasa (ronda 1) |

## Hallazgos (nuevos por el merge; siguen en pie F-02 a F-05 de la ronda 1, todos AMARILLO)
### F-06 · AMARILLO · `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:31` · cita como pendiente un fallo de identity-edge que ya está resuelto
La línea dice que identity-edge falla en `test_t1_supply_chain_skips_exactly_the_three_realm_configmaps`. U02-T20 (`eaa81a8`, PR #131) ya está en `5cf2ebb`: renombró la prueba y la alineó con las cinco entradas actuales. `CANDIDATAS.md:507` la marca como resuelta. Lo mismo pasa en `bitacoras/U03-T06.md:70-80`, que puede quedarse como histórico si se aclara así. Ninguno de los dos lo comprobé corriendo identity-edge.
### F-07 · AMARILLO · `cierre-demo.md:7`, `:31` y `:91` · la base citada es `fe0c9f3`, pero la rama ahora está sobre `5cf2ebb`
Los resultados de «Comprobado» y de «Quién ejecutó» se midieron sobre `fe0c9f3`. Si se dejan así, hay que decir que no se volvieron a correr después del merge.
### F-08 · AMARILLO · `cierre-demo.md:82` · P-1 aparece como decisión pendiente, pero ya está decidida
El texto dice «abrir… `U03-T07`… la decisión de abrirla es del usuario». `tareas/U03-T07-tope-de-daily-query.md` ya existe en `main` y registra «Decisión del usuario: 2026-11-10, abrir esta tarea». Además, el cierre debería apuntar a esa tarea.

## Para cerrar
Hace falta correr esto con la máquina descargada: sin la suspensión, sin los contenedores huérfanos de 25 a 32 h y sin otras suites en paralelo. Primero `make -C decision-registry check` y después `make -C {identity-edge,contracts,reference-model,model-serving} check`. Si vas a lanzarlo de nuevo, conviene limpiar antes esos contenedores, pero son de otros procesos y yo no los toqué. Usa el script `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t06-cierre/run.sh`: anota rc, segundos y `uptime` de cada unidad.

## Tareas candidatas
- Loop: los contenedores de Testcontainers quedan huérfanos durante días y degradan las corridas siguientes. Hace falta limpiarlos entre rondas.

## Rutas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t06-cierre/check-decision-registry.log` (corrida parcial)
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u03-t06-cierre/collect.txt` (orden de las 669 pruebas, con el que identifiqué la #353)

```
VEREDICTO: NO-VERDE
INFO|CA-2/CA-4|decision-registry check sin rc: detenida a 353/669 tras 25 h; la única F es test_f04_300_mil (candidata conocida, U03-T07); las otras 4 unidades no corrieron
AMARILLO|cierre-demo.md:31|Cita como pendiente el fallo de identity-edge que U02-T20 ya resolvió
AMARILLO|cierre-demo.md:7,31,91|Cita la base fe0c9f3; la rama ahora está sobre 5cf2ebb
AMARILLO|cierre-demo.md:82|P-1 figura como decisión pendiente; U03-T07 ya está abierta por el usuario
INFORME: revisiones/U03-T06/ronda-1.md
```
