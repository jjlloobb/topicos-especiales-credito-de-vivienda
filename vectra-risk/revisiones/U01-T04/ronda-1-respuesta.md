# Respuesta a la ronda 1 — U01-T04

F-01: Corregido en el commit de esta ronda: `test_grafana_token_kills_port_forward_on_error` (curl falso con exit 22 en `/tokens`; exige `returncode != 0` y eventos `started`/`terminated`). Contra el script de 650823f falla (`1 failed in 10.31s`) y contra la mutación m7 (sin trap, `kill "$forward"` al final de la función) también (`1 failed in 10.31s`); sobre el script corregido pasa (`1 passed in 0.28s`). El nombre evita el patrón de CA-2, que sigue dando `1 passed`.
F-02: Corregido en el commit de esta ronda: `seed-vault.sh` lanza `kubectl --context "$context" port-forward … >/dev/null &` sin subshell ni `exec`, con el comentario ajustado; CA-2 y la prueba de F-01 pasan.
F-03: Corregido en el commit de esta ronda: el trap del kubectl falso va antes del `sleep`, el fixture `fakes` mata el falso y su `sleep` al terminar aunque la prueba falle (`pgrep -a sleep` y `pgrep -a kubectl` vacíos tras las corridas en rojo) y quedó una sola separación de dos líneas en blanco.
Candidata del revisor (bucle de `/api/health` sin límite): Fuera de alcance: la anota el orquestador en `CANDIDATAS.md`; no se tocó.

## Evidencia fresca
$ pgrep -a sleep; pgrep -a kubectl      -> vacío (antes y después)
$ uv run pytest platform/kind/tests -q -k grafana_token_without_external_secret   -> 1 passed, 21 deselected in 0.23s  (CA-1)
$ uv run pytest platform/kind/tests -q -k grafana_token_stops_port_forward        -> 1 passed, 21 deselected in 0.23s  (CA-2)
$ uv run pytest platform/kind/tests -q                                            -> 22 passed in 1.57s
$ uv run ruff check platform/kind                                                 -> All checks passed!
$ bash -n platform/kind/seed-vault.sh                                             -> ok
