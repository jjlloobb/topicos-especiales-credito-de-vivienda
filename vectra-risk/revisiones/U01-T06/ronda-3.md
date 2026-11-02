# Ronda 3 — U01-T06

VEREDICTO: VERDE

Revisado: `8b5fc45` contra `f44ba83`. Los dos criterios de aceptación pasan. F-05, F-06, F-07, F-08 y F-09 están resueltos, y N1, N3 y N4 mueren. Quedan tres hallazgos AMARILLO, ninguno bloquea. No queda ningún ROJO ni NARANJA.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | Dos respuestas tardías y la tercera bien; el servidor registra 3 peticiones; tarda segundos | `uv run pytest platform/observability/grafana/tests -q -k retries_on_timeout --durations=5` | pasa: `1 passed, 21 deselected in 1.11s` (call 0.44 s). La prueba comprueba `len(state["seen"]) == 3` |
| 2 | 403 con 1 petición; tres tiempos de espera terminan en error; toda la suite pasa | `uv run pytest platform/observability/grafana/tests -q --durations=8 -rs` | pasa: `22 passed in 9.60s`, sin omitidas |

Comprobaciones adicionales:
- **Hash de la tarea:** `5f907a68…` coincide con la bitácora, y la tarea no cambia en el diff.
- **`uv run ruff check platform/observability/grafana`:** `All checks passed!`
- **Alcance:** en el código solo cambian `folder_permissions.py` y su archivo de pruebas. No cambian límites, CronJob, imágenes ni digests. Sin desborde.
- **Tiempo de la suite:** explicado. La mayor parte es el `shutdown` de 0.5 s de cada servidor.
- **Estabilidad:** 5 corridas seguidas sin carga dieron `22 passed` (9.61–10.72 s). Con 24 procesos ocupando CPU en 8 núcleos, 3 corridas dieron `22 passed` (10.74, 11.81 y 12.81 s). Es una muestra pequeña y no prueba estabilidad.
- **Integración con Grafana 13.3.0 real:** `platform/tests/test_grafana_folder_permissions.py` dio `4 passed in 11.62s`, desde una copia, con `TESTCONTAINERS_RYUK_DISABLED=true`. No se saltó nada: la misma suite da `4 failed` con el mutante P3. No queda ningún contenedor de Grafana corriendo.
- **Worktree al terminar:** limpio, HEAD `8b5fc45`. Mutaciones y sondas se hicieron en copias temporales.

## Estado de los hallazgos de la ronda 2

| Hallazgo | Estado | Evidencia mía |
|---|---|---|
| F-05 | **Resuelto** | N3 muere por `test_folder_created_by_a_timed_out_post_is_not_an_error`. La prueba lee de vuelta 2 POST, 1 espera y los permisos finales. La anterior se renombró a `test_folder_conflict_on_create_is_tolerated`. Ver F-10 sobre la forma del tiempo agotado |
| F-06 | **Resuelto** | N1 muere por `test_other_folder_errors_are_raised` |
| F-07 | **Resuelto** | N4 muere por `test_server_errors_are_not_retried` |
| F-08 | **Resuelto** | La prueba real cuenta `len(calls) == 1` y M5 la hace fallar. `import socket` está al inicio. La carrera entre cerrar el socket y usar el puerto sigue, pero es insignificante |
| F-09 | **Resuelto** | `ruff format --diff` ya no toca `is_timeout` ni código añadido por este diff. Da `2 files would be reformatted` solo por trozos en código anterior (en `folder_permissions.py`: `desired_items`, `current_items`, `drift`) |

La reescritura de `is_timeout` no cambia el comportamiento: la forma anterior y la nueva coinciden en 11 casos (`TimeoutError`, `socket.timeout`, `URLError` con varias causas, `HTTPError`, `OSError`, `ValueError` y otros).

### Mutantes (suite completa, copia temporal)

Sin mutar da `22 passed`. Todos los mutantes de la ronda 2 mueren:

| Mutante | Fallos | Mutante | Fallos |
|---|---|---|---|
| **N1 traga todo `HTTPError`** | **1** | N5 reintenta 4xx salvo 403 | 9 |
| **N3 solo se reintenta GET** | **1** | N6 reintenta 409 | 3 |
| **N4 se reintentan los 5xx** | **1** | N7 espera constante | 1 |
| M1 `sleep` → `pass` | 3 | N8 `apply` sin `ensure_folder` | 2 |
| M2 `sleep(0)` | 1 | N9 `BACKOFF=0` | 1 |
| M3 sin rama `URLError` | 1 | N10 `urlopen` sin `timeout` | 7 |
| M4 solo rama `URLError` | 4 | N11 mensaje sin los intentos | 1 |
| M5 reintenta todo `URLError` | 2 | N2 sin tolerar 409 | 2 |
| M6b reintenta solo el 403 | 1 | M7 `ATTEMPTS=2` | 4 |
| M8 `ATTEMPTS=4` | 3 | M9 relanza el error original | 3 |
| M10 mensaje `"error 3"` | 2 | | |

Mutantes nuevos de esta ronda:

| Mutante | Resultado |
|---|---|
| P1 `attempt > ATTEMPTS` | muere, 3 failed |
| P4 espera también tras el último intento | muere, 2 failed |
| P5 el reintento pierde el cuerpo del POST | muere, 1 failed |
| P6 `ensure_team` sin tolerar 409 | muere, 1 failed |
| P7 `request` no devuelve el cuerpo | muere, 12 failed |
| P9 no captura `TimeoutError` directo | muere, 4 failed |
| P2 `from exc` → `from None` | **sobrevive**, ver F-11 |
| P3 `ensure_folder` sin `title` | sobrevive a la suite unitaria; **muere en integración** (`4 failed`). Sin hallazgo |
| P8 quitar `isinstance(exc, HTTPError)` | sobrevive porque es equivalente: `HTTPError.reason` es un texto, así que `is_timeout` ya da `False`. Sin hallazgo: la cláusula es redundante, pero hace explícita la intención |

### Las pruebas nuevas contra código anterior

| Pruebas de HEAD contra código de | Resultado |
|---|---|
| `f44ba83`, tal cual | `2 failed, 11 passed, 9 errors`. Los 9 errores son `AttributeError` de fixtures (`BACKOFF`, `time`), no de comportamiento |
| `f44ba83` + `import time`, `BACKOFF` y `RequestTimeoutError` vacía, para ver el comportamiento | `7 failed, 15 passed` |
| `e24573f` (antes de `ensure_folder`) | `3 failed, 19 passed`. `test_folder_created_by_a_timed_out_post_is_not_an_error` falla con `HTTPError 409` |
| `2340030` (solo cambia `is_timeout` después) | `22 passed` |

- **Rojo de CA-1:** en la variante con constantes añadidas, `retries_on_timeout` falla con `TimeoutError: timed out`, como pide el plan de pruebas.
- **Por qué hacen falta esas constantes:** sin `raising=False`, que se quitó por F-03, la fixture ya no llega a correr contra la base pura. El rojo original quedó verificado en la ronda 1.
- **Pasan en la base, y es correcto:** `test_forbidden_is_not_retried`, `test_server_errors_are_not_retried` y las dos de conexión rechazada. Son de regresión, porque la base no reintenta nada. Su valor sale de los mutantes M6b, N4 y M5, que sí las hacen fallar.

### Sondas de comportamiento (locales, nada contra un clúster)

| Caso | Salida |
|---|---|
| POST tardío por socket real: el doble crea la carpeta, tarda más que `TIMEOUT` y da 409 al duplicado | `apply OK`. POST a `/api/folders` 2 veces (409 y el 200 tardío), `drift` 0, permisos `[{'teamId': 1, 'permission': 1}]` |
| Conexión agotada real (backlog saturado) | `RequestTimeoutError GET /x agoto el tiempo de espera en 3 intentos`, con causa `URLError(TimeoutError('timed out'))` |

## Hallazgos

### F-10 · AMARILLO · `tests/test_folder_permissions.py:321-339` y `revisiones/U01-T06/ronda-2-respuesta.md:1` · La respuesta dice «timeout real», pero la prueba lo simula
La prueba recibe la respuesta real del doble, la cierra y lanza `TimeoutError("timed out")` desde un `urlopen` envuelto. El socket no llega a agotar el tiempo. La bitácora lo describe bien («`urlopen` lanza TimeoutError tras la respuesta»); la respuesta, no. No bloquea, por tres razones: la prueba ejercita la secuencia completa, N3 y P5 la hacen fallar, y mi sonda por socket real da el mismo resultado. La prueba tampoco afirma de forma explícita que el segundo POST recibió 409, aunque N2 demuestra que depende de ello.

### F-11 · AMARILLO · `folder_permissions.py:72` · Nada protege la causa encadenada del error final
El mutante P2 (`from None`) deja `22 passed`. El mensaje sigue siendo claro, pero se perdería si el agotamiento fue al conectar o al leer. Bastaría con un `assert isinstance(raised.value.__cause__, TimeoutError)` en una prueba existente.

### F-12 · AMARILLO · `bitacoras/U01-T06.md:61` · El rojo de la ronda 3 no trae comando ni salida propios
La bitácora remite a los `19 passed` de mi informe anterior, y los conteos de N1, N3 y N4 van sin comando. Sus resultados coinciden con los míos (`1 failed, 21 passed` en los tres), así que la afirmación es correcta.

## Sobre la bitácora y la respuesta
Conteos y resultados coinciden con mis corridas: `22 passed`, CA-1 y ruff. El único matiz está en F-10. La bitácora no afirma que esto resuelva la causa de los tiempos de espera en kind, como pide la tarea.

## No verificado
- Nada se ejecutó contra un clúster.
- No repetí la sonda extremo a extremo con proxy contra Grafana real de la ronda 2. Desde `56d44a8` el único cambio de código es `is_timeout`, que no altera el comportamiento en los 11 casos comparados. Sí corrí la integración real y el POST tardío contra un doble.
- No probé versiones de Grafana distintas de 13.3.0.
- La estabilidad bajo carga solo tiene las 3 corridas citadas.

## Tareas candidatas (defectos reales fuera de alcance)
Siguen en pie las dos de rondas anteriores, y ninguna figura en `CANDIDATAS.md` (`grep -c "push_metric\|U01-T06"` da 0). Conviene registrarlas antes de cerrar:
- `push_metric` (`folder_permissions.py:160-165`) hace su propio `urlopen` sin reintentos. Un tiempo agotado contra el Pushgateway sigue tumbando el `check`.
- El Job y el CronJob fijan la imagen por digest. El cambio no llega al clúster hasta publicar imagen y digest nuevos, que esta tarea excluye.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev3.P1RIbT/mut.out`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev3.P1RIbT/mut.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev3.P1RIbT/post.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev3.P1RIbT/eq.py`

AMARILLO|tests/test_folder_permissions.py:321-339|La respuesta dice «timeout real», pero la prueba lo simula
AMARILLO|folder_permissions.py:72|Nada protege la causa encadenada del error final (P2 sobrevive)
AMARILLO|bitacoras/U01-T06.md:61|El rojo de la ronda 3 no trae comando ni salida propios
INFORME: revisiones/U01-T06/ronda-3.md
VEREDICTO: VERDE
