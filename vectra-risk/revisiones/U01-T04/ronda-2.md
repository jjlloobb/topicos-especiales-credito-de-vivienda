# Ronda 2 — U01-T04

VEREDICTO: VERDE

Worktree en `0db8645f3ba8e867f2a85afc7cab7ad0068d9f56`. El código de esta ronda está todo en el commit `0db8645`: `seed-vault.sh` (+2/−2), `tests/test_vault_paths.py` y la bitácora. El commit `7446f2a` solo trae documentos de revisión. `CANDIDATAS.md` no se tocó, lo cual es correcto porque la anota el orquestador.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Sin ExternalSecret: sale con 0, escribe el token y no hace `annotate` | `uv run pytest platform/kind/tests -q -k grafana_token_without_external_secret` | pasa: `1 passed, 21 deselected in 0.23s` |
| 2 | Sin `unbound variable`, y el port-forward recibe la señal | `uv run pytest platform/kind/tests -q -k grafana_token_stops_port_forward` | pasa: `1 passed, 21 deselected in 0.23s` |
| F-01 | Camino de error | `uv run pytest platform/kind/tests -q -k grafana_token_kills_port_forward_on_error` | pasa: `1 passed, 21 deselected in 0.28s` |
| — | Suite completa, lint y sintaxis | `uv run pytest platform/kind/tests -v`; `uv run ruff check platform/kind`; `bash -n` | `22 passed in 1.68s`, todas PASSED y ninguna omitida; `All checks passed!`; ok |

Estrés: 12 procesos en paralelo × 8 corridas de las 4 pruebas de grafana-token. Resultado: `96 × 4 passed`, sin huérfanos.

## Cierre de la ronda 1
- **F-01 (NARANJA): cerrado.** La prueba nueva falla contra `650823f` (falla esa y CA-2: `2 failed, 2 passed`) y contra m7, donde es la única que falla (`1 failed, 3 passed`). Pasa en HEAD.
- **F-02 (AMARILLO): cerrado.** La línea 33 queda como `kubectl --context "$context" port-forward … >/dev/null &`, con el comentario ajustado. Con mi sustituto de un solo proceso (`exec -a kubectl-pf-real sleep 30`, que mantiene la disposición por defecto ante TERM):

  | Script | Camino feliz | Camino de error |
  |---|---|---|
  | `650823f` | rc=0, el proceso **sigue vivo** | rc=1, el proceso **sigue vivo** |
  | HEAD | rc=0, no queda ninguno | rc=1, no queda ninguno |

  El arreglo no depende del `trap` del falso.
- **F-03 (AMARILLO): cerrado en lo que pedía.** El falso instala el trap antes del `sleep`, sobran menos líneas en blanco y el fixture `fakes` limpia. Para probar el fixture forcé un fallo: corrí CA-2 contra `650823f`, donde el falso sobrevive al script. Dio `1 failed in 10.27s` y después `pgrep` salió vacío. Queda un hueco menor (F-01 de esta ronda).

## Mutaciones (transcripción: `mutaciones.txt`)
| Mutación | Resultado |
|---|---|
| Script previo al PR 19 | mueren las 4 |
| `650823f` | muere (CA-2 y la prueba de error) |
| m1 `annotate` incondicional | muere (CA-1) |
| m2 trap sin `kill` | muere (CA-2 y error) |
| m3 volver a `kube port-forward … &` | muere (CA-2 y error) |
| m3b `( kubectl … ) &` | sobrevive, y es **equivalente**: bash 5.3 convierte en exec un subshell con un solo comando |
| m3c `( kubectl …; true ) &` | muere: con un subshell real, `$!` deja de ser kubectl y las pruebas lo detectan |
| m4 `local forward` | mueren las 4 |
| m5 quitar el bloque de `annotate` | muere (CA-1 y la de anotación) |
| m6 quitar el `trap` | muere (CA-2 y error) |
| m7 `kill` al final de la función, sin trap | **muere** (la prueba de error) |
| m8 no escribir en Vault | muere (CA-1) |
| m9 `kill -9` | muere, pero porque el falso registra TERM; con kubectl real sería válido. Además deja huérfanos (F-01) |

La única mutación que sobrevive es m3b, y es equivalente.

## Hallazgos

### F-01 · AMARILLO · platform/kind/tests/test_vault_paths.py:206 · El fixture no limpia el `sleep` si el falso muere sin ejecutar su trap
`pkill -P <pid>` solo encuentra al `sleep` mientras su padre, el kubectl falso, sigue vivo. Con m9 (`kill -9`), el falso muere sin pasar por su trap y el `sleep 60` queda colgado de init. `ps` lo muestra con PPID 4270, así que el fixture no lo ve: después de la corrida de m9 quedaron 4 `sleep 60` (los maté yo). Solo pasa si el falso recibe SIGKILL, así que no afecta a las corridas normales, ni en verde ni en rojo. Se cierra si el falso escribe también el pid del `sleep` o si se mata el grupo de procesos. No bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- Sin novedades. La del bucle de `/api/health` ya la tiene el orquestador para `CANDIDATAS.md`.

## Procesos y estado final
- `pgrep -a sleep` y `pgrep -a kubectl` salen vacíos antes y después de los CA, de la suite y del estrés. Los únicos huérfanos vinieron de m9 (F-01) y los limpié.
- `git -C /home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U01-T04 status --short` sale vacío y HEAD sigue en `0db8645f3ba8e867f2a85afc7cab7ad0068d9f56`.
- Un `rm` de mi copia de trabajo lo bloqueó la comprobación de seguridad porque la ruta dependía de una variable. Lo repetí con `${VAR:?}`, solo dentro de mi carpeta en el scratchpad; no tocó el worktree.

## Rutas de transcripciones largas
Todo en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t04-r2/`:
- `mutaciones.txt` y `mut/`: mutaciones del script
- `stress-*.txt`: estrés

El sustituto de un solo proceso y el curl que falla siguen en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t04-r1/mech/` y `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t04-r1/err/`.

VEREDICTO: VERDE
AMARILLO|platform/kind/tests/test_vault_paths.py:206|el fixture no limpia el `sleep` si el kubectl falso muere por SIGKILL sin ejecutar su trap
INFORME: revisiones/U01-T04/ronda-2.md
