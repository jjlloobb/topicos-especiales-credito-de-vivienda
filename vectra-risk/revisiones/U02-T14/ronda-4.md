# Ronda 4 — U02-T14

VEREDICTO: VERDE

F-14 y F-15 están cerrados con la forma que fijó `arbitraje-ronda-3.md`. CA-1 a CA-7 pasan en mi propia ejecución, con CA-5 y CA-6 en serie. El diff de la ronda no tiene desborde ni regresiones. Quedan dos AMARILLO, que no bloquean.

Estado al terminar:
- El worktree está limpio: `git status --short` vacío, HEAD en 2a34093.
- El hash de la tarea es `14cc439c1a4d266146f919e3572ae8dd678b5281`, el esperado.
- Todas las mutaciones las hice sobre una copia `git archive HEAD` en el scratchpad, usando el `.venv` del worktree con `-p no:cacheprovider`.
- No queda ningún proceso mío en marcha.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`, sin `VECTRA_E2E_*` ni `SYNTH_*` en el entorno)
| # | Comando | Resultado |
|---|---|---|
| 1 | `uv sync --frozen && uv run ruff check identity-edge/tests/e2e` | pasa, exit 0 |
| 2 | `env -u VECTRA_E2E_BASE_URL uv run pytest identity-edge/tests/e2e --collect-only -q` | pasa: 26 casos, 0 errores |
| 3 | `uv run pytest identity-edge/tests/unit/test_e2e_inventory.py -q` | pasa, 6 |
| 4 | `uv run pytest identity-edge/tests/unit/test_e2e_echo.py -q` | pasa, 45 |
| 5 | `make -C identity-edge collect-e2e && make -C identity-edge check` | pasa, exit 0. Colecta 26 y corre 2517 casos en 950,67 s. Ningún archivo de `tests/e2e` aparece después de `--ignore=identity-edge/tests/e2e`. Ningún «skip» salvo los `Skipped: 0` de kubeconform y `--skip-tests`/`--skip-crds` de helm |
| 6 | `make -C platform check-local && uv run pytest contracts/tests -q`, en serie después de CA-5 | pasa, exit 0: platform 745, `2 chart(s) linted, 0 chart(s) failed`, contratos 502 |
| 7 | `realm_lint.py` sobre los 3 realms `&& pytest test_realm_lint test_realm_diff test_bruteforce_model -q` | lint exit 0; 816 passed |

Una incidencia del entorno: mi primera corrida de CA-5 y CA-6 escribió en `scratchpad/ca5.log`. Otro proceso, de la revisión de U02-T13 en `wt-U02-T13`, escribía en esa misma ruta del scratchpad. Descarté esa corrida y repetí las dos en un directorio aislado, sin ninguna línea de `wt-U02-T13`. Las cifras de la tabla salen de esa repetición.

## Cierre de F-14
- **Borrados.** Ya no existen `tests/fixtures/realm-baseline-8c18021/` ni la prueba de la foto. `grep -rn "realm-baseline\|8c18021\|only_differ_from_the_baseline"` fuera de `revisiones/` y `bitacoras/` no encuentra nada. En `tests/fixtures/` solo quedan `k8s-schemas` y `keycloak-26.8.1`.
- **Pruebas nuevas.** Están en `test_realm_files.py:651-683` y cada una corre 3 casos (fixture `env`):
  - prioridades estrictamente crecientes en cada flujo;
  - el orden de `vectra-browser forms`, leído de `realm_builders.MFA_ROLES` y de `design.optional_mfa_roles()`;
  - la plantilla nivel < rol (< configurado) < factor.
- **Literales.** No repiten `LINEAR`, 15 ni 3.
- **Mutaciones del arbitraje, corridas por mí.** Cambié cada una de las 21 `priority: 30` de `authenticationFlows` a 57, una por vez, en kind, staging y prod.
  - La de `vectra-browser forms` (`vectra-mfa-cro`: kind L353, staging L353, prod L340) hace fallar `test_the_authentication_flows_have_unique_increasing_priorities[<env>]`.
  - Las 18 restantes sobreviven (ver F-16).
  - La regresión original de F-10, con las 7 a la vez en kind, falla.
- **`accessTokenLifespan` 300→240.** Las 3 pruebas nuevas no fallan. En el archivo completo fallan `test_realm_files_exist_and_pass_realm_lint` y `test_realm_files_parameters_are_those_of_the_design`, que ya existían y fijan el valor del diseño. Es lo esperado y no tiene que ver con la prueba nueva.
- **Mutaciones de orden que elegí yo**, todas en kind, renumerando las prioridades de forma coherente salvo que se indique otra cosa. Resultado con `-k 'kind and (priorities or orders or template)'`:

| Mutación | Resultado |
|---|---|
| intercambiar ingeniero_riesgo↔cro / cro↔cumplimiento | falla 1 |
| cro↔cumplimiento solo en la lista, sin tocar prioridades | falla 2 |
| analista antes de break-glass | falla 1 |
| `vectra-level-pwd` en 2.º puesto | falla 1 |
| operacion antes de cumplimiento | falla 1 |
| prioridad duplicada (cumplimiento=30) | falla 1 |
| quitar analista / quitar break-glass / duplicar operacion | falla 1 cada una |
| en `vectra-mfa-cro`: rol antes que nivel / factor primero / factor que apunta a otro subflujo | falla 1 cada una |
| en analista: `conditional-user-configured` después del factor | falla 1 |
| **operacion↔break-glass** | **pasa** (es la limitación declarada) |
| quitar `conditional-user-configured` de analista | las 3 nuevas pasan; falla `test_realm_files_login_flow_reaches_acr_mfa_for_every_mfa_role`, que ya existía |

- **Evaluación de la limitación declarada.** Es correcta y no la invento:
  - BR-U2-03 (`business-rules.md:22-26`) no fija un orden.
  - `realm_builders.MFA_ROLES` solo nombra ingeniero_riesgo, cro y cumplimiento.
  - `operacion` y `break-glass` solo aparecen en `realm_builders.py:163,171,182`, sin orden de flujo.
  - Ambos subflujos son CONDITIONAL por rol, con el mismo nivel y el mismo factor TOTP/WebAuthn, así que su orden relativo no cambia lo que el usuario debe presentar.
  - Compararlos como conjunto, y exigir además `len(rest) == len(expected_rest)` contra duplicados, es la decisión correcta. Que la prueba fijara un orden sin fuente sería el error.

## Cierre de F-15
- `test_bruteforce_model.py:192-196` deriva `gap = spaced(params)` y `quick = params.quick_login_check_milliseconds / 1000 / 2`. Ya no quedan los 2,0 s ni los 0,1 s.
- **Guarda.** Si cambio la guarda de `bruteforce_model.py:93` por `if previous is not None`, fallan los 3 casos de la prueba. Restaurada, pasan 48.
- **Robustez.** Con `quickLoginCheckMilliSeconds: 5000` y `300` en los 3 realms, la prueba nueva pasa (3/3). La de d6e1307, con 5000, falla 3/3. Ahora la prueba depende del parámetro y no de un margen implícito.

## Barrido del diff de la ronda (`git diff 18ae2c7..HEAD`)
- El diff solo toca la bitácora, borra la línea base (4 archivos) y modifica `test_bruteforce_model.py` (+4/−2) y `test_realm_files.py`.
- `git diff d6e1307 --stat -- identity-edge/keycloak/realm identity-edge/jobs/rendered`: vacío.
- No hay código de producto ni archivos fuera de lo que pidió el arbitraje. Sin desborde.
- La afirmación de la bitácora «153 passed» (realm_files + bruteforce_model) la reproduje en la copia: 153 passed.

## Hallazgos

### F-16 · AMARILLO · `bitacoras/U02-T14.md` (Ronda 4, F-14) · La bitácora no dice que 6 de las 7 `priority: 30` de cada realm no son detectables
- La bitácora cita una sola mutación, la de L353, y presenta el resultado como «la prueba mata la regresión».
- En cada realm, las otras 6 son el subflujo `… factor` de cada `vectra-mfa-<rol>`. Ese subflujo ya es el último, así que 30→57 mantiene el orden, y sobreviven las 18 (6 × 3 realms).
- Es el efecto esperado de usar invariantes en lugar de una foto: el cambio no altera el comportamiento, y detectarlo es trabajo de revisión de diff. Por eso no bloquea.
- La bitácora debería declararlo para que nadie lea «toda `priority: 30`».

### F-17 · AMARILLO · `tests/unit/test_realm_files.py:664,669` · Un literal de alias y un orden alfabético implícito
- En la línea 669, `"vectra-mfa-break-glass"` es un literal. Podría ser `f"vectra-mfa-{BREAK_GLASS}"`, con la constante que ya existe en `realm_lint.py:61`.
- En la línea 664, `sorted(design.optional_mfa_roles())` impondría orden alfabético si algún día hubiera más de un rol opcional. Ninguna fuente fija ese orden, que es la misma limitación de operacion/break-glass. Hoy no tiene efecto, porque solo existe analista.
- Además, la prueba de plantilla (673-683) deduce la opcionalidad del propio subflujo (`"conditional-user-configured" in kinds`) y no del diseño. Quitar esa condición de analista solo lo detecta la prueba que ya existía (ver la tabla). No hay hueco de cobertura, solo una dependencia cruzada.

## Tareas candidatas (defectos reales fuera de alcance)
- Fijar en el diseño (BR-U2-03 o `domain-entities` §1.1) o en una tupla de `realm_builders` el orden completo de los subflujos de `vectra-browser forms`, incluidos `operacion`, `break-glass` y los roles opcionales. Así la prueba podría comparar listas y no conjuntos.
- Higiene del bucle: los revisores de tareas paralelas (U02-T13 y U02-T14) comparten el mismo directorio de scratchpad y nombres de log genéricos (`ca5.log`, `ca6.log`). Un log puede pisar a otro y dar evidencia de otra rama. Cada revisión debería usar un subdirectorio por tarea.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/u02t14-r4/ca5.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/u02t14-r4/ca6.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/order-mutations.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/tasks/buw9ae76q.output (las 21 mutaciones 30→57 y las de `accessTokenLifespan`)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/tools/mut.py (script de las mutaciones de orden)

```
VEREDICTO: VERDE
AMARILLO|bitacoras/U02-T14.md (Ronda 4, F-14)|La bitácora no dice que 6 de las 7 priority: 30 de cada realm no son detectables
AMARILLO|identity-edge/tests/unit/test_realm_files.py:664,669|Un literal de alias y un orden alfabético implícito
INFORME: revisiones/U02-T14/ronda-4.md
```

VEREDICTO: VERDE
