# Ronda 2 — U01-T06

VEREDICTO: NO-VERDE

Revisado: `56d44a8` contra `f44ba83`. Los dos criterios de aceptación pasan y el comportamiento es correcto, también contra Grafana 13.3.0 real. El bloqueo es de cobertura: el código nuevo de F-02 quedó con dos mutantes vivos, N1 y N3, y la prueba de F-02 no ejercita el caso que nombra.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | Dos respuestas tardías y la tercera bien; el servidor registra 3 peticiones; tarda segundos | `uv run pytest platform/observability/grafana/tests -q -k retries_on_timeout --durations=5` | pasa: `1 passed, 18 deselected in 1.71s` (call 0.45 s). La prueba comprueba `len(state["seen"]) == 3` |
| 2 | 403 con 1 petición; tres tiempos de espera terminan en error; toda la suite pasa | `uv run pytest platform/observability/grafana/tests -q --durations=8 -rs` | pasa: `19 passed in 9.71s`, sin omitidas |

Comprobaciones adicionales:
- **Hash de la tarea:** `5f907a68…` coincide con la bitácora, y la tarea no cambia en el diff.
- **`uv run ruff check platform/observability/grafana`:** `All checks passed!`
- **Tiempo de la suite:** explicado. La mayor parte es el `shutdown` de 0.5 s de cada servidor.
- **Rojo de la ronda 2:** pruebas de `2340030` contra el código de `e24573f`, en copia. Da `1 failed, 18 passed`, y falla `test_folder_created_by_a_timed_out_attempt_is_not_an_error`, como afirma la bitácora.
- **Carga:** 3 corridas seguidas con 3×nproc procesos ocupando CPU durante 45 s dieron `19 passed` (20.64 s, 9.84 s, 9.64 s). Es una muestra pequeña y no prueba estabilidad. El kill final de esos procesos terminó también mi shell, sin afectar a estas corridas.
- **Alcance:** en el código solo cambian `folder_permissions.py` y su archivo de pruebas. No cambian límites, CronJob, imágenes ni digests. Sin desborde.
- **Límites del Job:** `manifests.yaml` no define `activeDeadlineSeconds`, así que el peor caso de 21 s por petición no choca con ningún plazo de Kubernetes. `check` y `apply` siguen corriendo hasta terminar.
- **Worktree al terminar:** limpio, HEAD `56d44a8`. Las mutaciones y sondas se hicieron en copias temporales. El contenedor de sonda se eliminó y no queda ningún contenedor de Grafana corriendo.

## Estado de los hallazgos de la ronda 1

| Hallazgo | Estado | Evidencia mía |
|---|---|---|
| F-01 | **Resuelto** | M1, M2, M3, M5 y M10 mueren, con los mismos conteos que afirma la bitácora (tabla abajo) |
| F-02, comportamiento | **Resuelto** | Sonda contra Grafana real (abajo) |
| F-02, prueba de lectura de vuelta | **No resuelto** | Ver F-05 |
| F-03 | **Resuelto** | `grep` sin `autouse` ni `raising=False` |
| F-04 | **Resuelto** | `grep` sin `AssertionError` ni `fast_client` |

### Mutantes (suite completa, copia temporal)

| Mutante | Resultado |
|---|---|
| Base sin mutar | `19 passed` |
| M1 `sleep` → `pass` | muere, 2 failed |
| M2 `sleep(0)` | muere, 1 failed |
| M3 sin rama `URLError` | muere, 1 failed |
| M4 solo rama `URLError` | muere, 3 failed |
| M5 reintenta todo `URLError` | muere, 2 failed |
| M6b reintenta solo el 403 | muere, 1 failed |
| M7 `ATTEMPTS=2` | muere, 4 failed |
| M8 `ATTEMPTS=4` | muere, 3 failed |
| M9 relanza el error original | muere, 3 failed |
| M10 mensaje `"error 3"` | muere, 2 failed |
| N2 `ensure_folder` sin tolerar 409 | muere, 1 failed |
| N5 reintenta 4xx salvo 403 | muere, 7 failed |
| N6 reintenta 409 | muere, 2 failed |
| N7 espera constante | muere, 1 failed |
| N8 `apply` sin `ensure_folder` | muere, 1 failed |
| N9 `BACKOFF=0` | muere, 1 failed |
| N10 `urlopen` sin `timeout` | muere, 5 failed |
| N11 mensaje sin los intentos | muere, 1 failed |
| **N1 `ensure_folder` traga todo `HTTPError`** | **sobrevive**, `19 passed` |
| **N3 solo se reintenta GET** | **sobrevive**, `19 passed` |
| **N4 se reintentan los 5xx** | **sobrevive**, `19 passed` |

### Sondas de comportamiento contra Grafana 13.3.0 real (local, nada contra un clúster)

Esta sonda confirma el supuesto que el codificador dejó sin verificar: el Grafana real devuelve 409 ante un UID duplicado.

| Petición `POST /api/folders` | Respuesta |
|---|---|
| Mismo UID, mismo título | `409 "a folder with the same UID already exists"` |
| Mismo UID, otro título | `409`, mismo mensaje |
| Otro UID, mismo título | `200`: el título duplicado no da 409, así que la tolerancia no oculta ese caso |
| UID inválido | `400` |

- **Extremo a extremo, con un proxy local que retrasa la primera respuesta de cada POST:** `apply OK`.
  - Secuencia: `POST /api/teams` 200 y luego 409; `POST /api/folders` 200 y luego 409; `POST .../permissions` 200 y 200.
  - Lectura de vuelta: `drift` da 0, la carpeta y el equipo existen, y los permisos son `[('rev2-team', None, 1)]`.
- **Conexión agotada real (backlog saturado):** `RequestTimeoutError GET /x agoto el tiempo de espera en 3 intentos`, con causa `URLError(TimeoutError('timed out'))`.
- **`platform/tests/test_grafana_folder_permissions.py`:** `4 passed in 52.60s`, desde una copia, con la imagen local y `TESTCONTAINERS_RYUK_DISABLED=true`.

## Hallazgos

### F-05 · NARANJA · `tests/test_folder_permissions.py:293-303` · La prueba de F-02 no pasa por ningún tiempo agotado, y reintentar POST queda sin proteger
La prueba `test_folder_created_by_a_timed_out_attempt_is_not_an_error` no contiene ningún tiempo agotado. Crea la carpeta de antemano, fuerza `folder_exists` a `False` y comprueba `fake.writes.count("/api/folders") == 1`, o sea un solo POST y ningún reintento. Eso prueba «un 409 directo se tolera», no el caso que nombra ni el que pedía F-02: Grafana crea la carpeta, responde tarde, se reintenta y llega el 409.

Demostración: el mutante N3, que añade `method != 'GET' or` a la condición de relanzar en la línea 67, deja `19 passed`. Las pruebas de reintento con servidor lento solo usan GET. La bitácora justifica haber elegido no excluir POST «para no perder la reintentabilidad pedida», pero ninguna prueba protege esa decisión.

Qué falta: una prueba donde el doble cree la carpeta, responda tarde al primer POST y devuelva 409 al segundo. Debe leer de vuelta 2 POST, la carpeta creada y los permisos finales. Mi sonda con proxy muestra que el código actual ya la pasaría. Además, conviene renombrar la prueba actual según lo que de verdad prueba, o sustituirla.

### F-06 · NARANJA · `folder_permissions.py:84-90` · `ensure_folder` no tiene prueba de que los demás errores se propagan
El mutante N1 sustituye el `if exc.code != HTTP_CONFLICT: raise` por `pass` y deja `19 passed`. Un 403 o un 500 al crear la carpeta podría silenciarse sin que falle nada. `ensure_team` tiene su prueba equivalente, `test_other_team_errors_are_raised`, pero el método gemelo que introdujo este retrabajo no. Es cobertura ausente en código nuevo. Falta una prueba que compruebe que un 403 en `POST /api/folders` llega como `HTTPError` desde `ensure_folder`.

### F-07 · AMARILLO · `folder_permissions.py:66` · El comentario promete que los 5xx no se reintentan, y nada lo protege
El mutante N4 sobrevive. El comportamiento actual es correcto y la tarea solo excluye expresamente los 4xx, por eso no bloquea. Una prueba con un 500 y 1 petición lo cerraría, y puede aprovechar el `slow_server` existente.

### F-08 · AMARILLO · `tests/test_folder_permissions.py:281-290` · La prueba de conexión rechazada real no cuenta intentos
La bitácora dice «simulada y real con 1 intento», pero la prueba real solo comprueba `sleeps == []`, sin contar peticiones. Lo sostiene indirectamente que toda repetición va precedida de una espera. Tiene además un `import socket` local y una carrera menor entre cerrar el socket y usar el puerto.

### F-09 · AMARILLO · `folder_permissions.py:48` · La línea larga de `is_timeout` añade una divergencia de formato
La bitácora dice que `ruff format --check` ya fallaba antes de la tarea, y es cierto: en `f44ba83` también da `2 files would be reformatted`. Pero el trozo `@@ -45,7 +45,9 @@` de esta comprobación cae en `is_timeout`, que es código de este diff. Es menor, porque el formato no es criterio de la tarea.

## Sobre la bitácora y la respuesta
Coinciden con mis corridas: conteos, rojo de la ronda 2 y conteos de mutantes. Dos matices:
- «F-02: Corregido» es cierto para el comportamiento, pero no para la prueba de lectura de vuelta que pedía la ronda 1 (F-05).
- El «SUPUESTO NO VERIFICADO» sobre el 409 queda verificado por mí en 13.3.0, la misma versión que usa la prueba de integración. No hace falta conservarlo como riesgo abierto.

La bitácora tampoco afirma que esto resuelva la causa de los tiempos de espera en kind, como pide la tarea.

## No verificado
- Nada se ejecutó contra un clúster.
- No probé versiones de Grafana distintas de 13.3.0.
- La estabilidad bajo carga solo tiene las 3 corridas citadas.

## Tareas candidatas (defectos reales fuera de alcance)
Siguen en pie las dos de la ronda 1, y ninguna figura en `CANDIDATAS.md` (`grep` de `U01-T06` y `push_metric` sin resultados):
- `push_metric` (`folder_permissions.py:158-163`) hace su propio `urlopen` sin reintentos. Un tiempo agotado contra el Pushgateway sigue tumbando el `check`.
- El Job y el CronJob fijan la imagen por digest. El cambio no llega al clúster hasta publicar imagen y digest nuevos, que esta tarea excluye.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev2/mut.out`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev2/probes/mut.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev2/probes/real.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev2/probes/e2e.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev2/probes/connect.py`

NARANJA|tests/test_folder_permissions.py:293-303|La prueba de F-02 no pasa por ningún tiempo agotado; reintentar POST sin proteger (N3 sobrevive)
NARANJA|folder_permissions.py:84-90|ensure_folder sin prueba de que los demás errores se propagan (N1 sobrevive)
AMARILLO|folder_permissions.py:66|Los 5xx sin reintento no están protegidos (N4 sobrevive)
AMARILLO|tests/test_folder_permissions.py:281-290|La prueba de conexión rechazada real no cuenta intentos
AMARILLO|folder_permissions.py:48|La línea de is_timeout añade una divergencia de ruff format
INFORME: revisiones/U01-T06/ronda-2.md
VEREDICTO: NO-VERDE
