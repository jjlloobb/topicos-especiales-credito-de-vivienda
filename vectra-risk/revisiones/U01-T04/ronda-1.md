# Ronda 1 — U01-T04

VEREDICTO: NO-VERDE

Hash de la tarea: `95d2cf2176ce01073f4ec47e28c62266f255789e`, coincide. Worktree en `b35dbc9585b9ecd9c18e7022d8c3df7bf6eaa8d3`, base `650823f`. El diff toca 3 archivos: `seed-vault.sh` (+2/−1), `tests/test_vault_paths.py` (+72) y la bitácora.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Sin ExternalSecret: sale con 0, escribe el token y no hace `annotate` (se comprueba leyendo el registro del kubectl falso) | `uv run pytest platform/kind/tests -q -k grafana_token_without_external_secret` | pasa: `1 passed, 20 deselected in 0.21s` |
| 2 | Sin `unbound variable`, y el port-forward recibe la señal | `uv run pytest platform/kind/tests -q -k grafana_token_stops_port_forward` | pasa: `1 passed, 20 deselected in 0.21s` |
| — | Suite completa y lint | `uv run pytest platform/kind/tests -q`; `uv run ruff check platform/kind` | `21 passed in 1.35s`; `All checks passed!` |

Sobre el tiempo de 0.21 s: con `-v --durations` cada prueba aparece como PASSED, ninguna como omitida, y cada una tarda unos 0.11 s de `call` porque arranca bash, python3 y los falsos. No depende de estado externo.

**Rojo reproducido en copias** (`SEED_VAULT_SCRIPT=<copia>`):
- Script previo al PR 19 (`1f2aaf6~1`): CA-1, CA-2 y la prueba de anotación fallan. El error es `line 1: forward: unbound variable` y el script sale con 1.
- Script de `650823f`: falla CA-2 con `['started'] == ['started', 'terminated']` y pasan las otras dos (`1 failed, 2 passed … in 10.54s`).
- En los dos casos quedan huérfanos `bash …/kubectl … port-forward` con un `sleep 60` hijo. Lo vi con `ps` y los limpié yo.

## El defecto del port-forward en 650823f, y por qué el arreglo no depende del falso
Para separarlo del kubectl falso de la prueba, que es un bash con `trap TERM` y un hijo `sleep`, armé otro sustituto: un solo proceso con la disposición por defecto ante TERM, igual que el kubectl real (`exec -a kubectl-pf-real sleep 30`). El curl falso devuelve JSON válido.
- **650823f:** sale con 0, y el proceso del port-forward (pid igual al registrado) **sigue vivo** después de terminar el script. En bash 5.3.9, `kube port-forward … &` hace fork de un subshell que corre la función, y la función hace fork de kubectl, así que `$!` es el subshell. `kill` lo mata a él y kubectl queda adoptado por init.
- **HEAD:** sale con 0 y no queda ningún proceso. `(exec kubectl …) &` hace que el pid del subshell sea el de kubectl.

Con un kubectl real la única diferencia es quién atiende TERM. El falso lo atrapa y escribe `terminated`; el real (Go) termina por la disposición por defecto, porque `port-forward` solo intercepta `os.Interrupt`. El arreglo no depende de ningún detalle del falso. Sigue sin probarse contra un clúster, como dice el arbitraje.

**Camino de error** (curl `/tokens` sale con 22, así que `set -e` aborta con rc=1): HEAD mata el port-forward y no queda nada vivo; `650823f` lo deja vivo. Así que `set -euo pipefail` y el `trap … EXIT` funcionan en los dos caminos.

## Alcance y condiciones del arbitraje
- Cambio en `seed-vault.sh`: solo la línea 33 (el lanzamiento del port-forward) y un comentario en la 32. `seed()`, `kube()`, el `case` y el resto de `grafana_token` quedan idénticos (`git diff 650823f..HEAD -- platform/kind/seed-vault.sh`). Cumple.
- Par falla/pasa de CA-2 sobre `650823f` y sobre el script corregido: está en la bitácora y yo lo reproduje. Cumple.
- Otros modos sin alterar: verificado sobre el diff, y `seed` no comparte código modificado. Cumple.
- No discrepo del arbitraje: CA-2 no podía pasar sin el arreglo, y el arreglo es mínimo.

## Mutaciones (transcripción: `mutaciones-script.txt`)
| Mutación del script | Resultado |
|---|---|
| m1 `annotate` incondicional | muere (CA-1) |
| m2 trap sin `kill` (`trap true`) | muere (CA-2) |
| m3 quitar `exec` dentro de `( … )` | **sobrevive**, y es equivalente: bash 5.3 ya convierte en exec un subshell con un solo comando simple |
| m3b `kubectl … &` sin subshell | **sobrevive**, y es equivalente (ver F-02) |
| m3c la redirección fuera del subshell | sobrevive, equivalente |
| m4 volver a poner `local forward` | muere (las 3) |
| m5 quitar el bloque de `annotate` | muere |
| m6 quitar el `trap` | muere (CA-2) |
| **m7 quitar el `trap` y poner `kill "$forward"` al final de la función** | **sobrevive y NO es equivalente** (F-01) |
| m8 no escribir en Vault | muere (CA-1, `vault-stdin`) |
| m9 `kill -9` | muere, pero solo porque el falso registra TERM. Con kubectl real sería válido. Sin efecto práctico |

Sobre las pruebas: cada aserción tiene al menos una mutación que solo ella detecta. `annotate not in log` atrapa m1, `vault-stdin` atrapa m8, `['started','terminated']` atrapa m2, m6 y `650823f`, y `unbound variable`/rc atrapa m4 y el script previo al PR 19.

## Hallazgos

### F-01 · NARANJA · platform/kind/tests/test_vault_paths.py:232 · CA-2 no cubre que el port-forward se pare cuando el script falla
La razón de usar un `trap … EXIT`, y justo lo que rompía el PR 19, es parar el port-forward en cualquier salida, incluido un aborto por `set -e`. Las tres pruebas solo recorren el camino feliz. La mutación m7 cambia el trap por un `kill` al final de la función, pasa las 3 pruebas y aun así deja huérfano el port-forward cuando hay error. Lo comprobé con un curl que falla en `/tokens`: rc=1 y `kubectl-pf-real 30` sigue vivo. En la práctica eso es el puerto 13000 ocupado en el siguiente intento, que es cuando más se reintenta. Arreglo barato: una prueba con el curl falso fallando en `/tokens` que compruebe `returncode != 0` y `forward.log == ["started","terminated"]`. Es cobertura que falta dentro del alcance (el segundo caso del PR 19).

### F-02 · AMARILLO · platform/kind/seed-vault.sh:33 · `(exec …)` sobra
`kubectl --context "$context" port-forward … >/dev/null &` (m3b) ya hace que `$!` sea kubectl en cualquier versión de bash, sin subshell. El comentario de la línea 32 justifica un mecanismo más complejo de lo necesario. Además, en las dos formas `--context "$context"` repite lo que hace `kube()`. No bloquea.

### F-03 · AMARILLO · platform/kind/tests/test_vault_paths.py:179 · El kubectl falso deja huérfanos cuando una prueba falla, y tiene una carrera teórica
Cuando una prueba falla, como en mis rondas en rojo, quedan `bash kubectl` + `sleep 60` vivos durante 60 s, porque no hay fixture que los limpie. Además el falso instala su `trap TERM` después de lanzar `sleep &`. Si TERM llega antes, el `sleep` queda huérfano y la prueba falla. No lo observé: corrí CA-1+CA-2 120 veces en 12 procesos paralelos sobre 8 CPU y obtuve `120 × 2 passed`, sin huérfanos. Basta con instalar el trap antes del `sleep` y con un finalizador que mate el grupo. También sobran 2 líneas en blanco tras la prueba nueva (5 seguidas).

## Tareas candidatas (defectos reales fuera de alcance)
- `seed-vault.sh:37`: `until curl … /api/health; do sleep 1; done` no tiene límite. Si el port-forward muere (puerto ocupado, servicio inexistente), el script se queda en bucle para siempre.

## Procesos y estado final
- `pgrep -a sleep` y `pgrep -a kubectl` salen vacíos antes y después de correr los CA y el estrés sobre HEAD. Los únicos huérfanos aparecieron en mis corridas en rojo (650823f, el script previo al PR 19, m2/m6/m7) y los maté.
- `git -C /home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U01-T04 status --short` sale vacío (solo cachés ignoradas). HEAD sigue en `b35dbc9585b9ecd9c18e7022d8c3df7bf6eaa8d3`.

## Rutas de transcripciones largas
Todo en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u01t04-r1/`:
- `rojo-pre-pr19.txt` y `rojo-base-650823f.txt`: corridas en rojo
- `mutaciones-script.txt` y `mut/`: mutaciones del script
- `mech/` y `err/`: el sustituto de un solo proceso y el camino de error
- `stress-*.txt`: estrés

VEREDICTO: NO-VERDE
NARANJA|platform/kind/tests/test_vault_paths.py:232|CA-2 solo cubre el camino feliz: quitar el trap y matar al final de la función sobrevive y deja huérfano el port-forward cuando hay error
AMARILLO|platform/kind/seed-vault.sh:33|`(exec kubectl …) &` equivale a `kubectl … &`; el subshell y el comentario sobran
AMARILLO|platform/kind/tests/test_vault_paths.py:179|el kubectl falso deja huérfanos si la prueba falla y pone su trap después de `sleep &`
INFORME: revisiones/U01-T04/ronda-1.md
