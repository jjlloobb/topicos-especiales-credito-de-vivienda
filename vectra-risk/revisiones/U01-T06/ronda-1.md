# Ronda 1 — U01-T06

VEREDICTO: NO-VERDE

Revisado: `e24573fe6d44b80dfa666227496254c1cf8f18ff` contra `f44ba83`. Los dos criterios de aceptación pasan. El bloqueo viene de dos hallazgos NARANJA: mutantes que sobreviven en comportamiento dentro del alcance y un POST no idempotente que se reintenta.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/`) | Resultado |
|---|---|---|---|
| 1 | Dos respuestas tardías y la tercera bien; el servidor registra 3 peticiones; tarda segundos | `uv run pytest platform/observability/grafana/tests -q -k retries_on_timeout --durations=5` | pasa: `1 passed, 13 deselected in 2.61s` (call 0.47s). La prueba comprueba `len(state["seen"]) == 3` |
| 2 | 403 con 1 petición; tres tiempos de espera terminan en error; toda la suite pasa | `uv run pytest platform/observability/grafana/tests -q --durations=8 -rs` | pasa: `14 passed in 9.26s`, sin omitidas |

Comprobaciones adicionales:
- **Rojo primero:** pruebas de HEAD contra el código de `f44ba83`, en copia temporal. `retries_on_timeout` falla con `TimeoutError: timed out`, como afirma la bitácora. Resultado de la suite: `2 failed, 12 passed`.
- **Tiempo de la suite:** explicado. Las pruebas son reales y no se saltan; la mayor parte del tiempo es el `shutdown` de 0.5 s de cada servidor.
- **`uv run ruff check platform/observability/grafana`:** `All checks passed!`
- **Hash de la tarea:** `5f907a68…` coincide con la bitácora. La tarea no cambió en el diff.
- **Alcance:** solo cambian `folder_permissions.py`, su archivo de pruebas y la bitácora. No hay cambios en límites, CronJob, imágenes ni digests. Sin desborde.
- **Worktree al terminar:** limpio (`git status --short` vacío), HEAD sin cambios. Las mutaciones se hicieron en una copia temporal.

Comportamiento real con sondas propias contra servidores locales (nada contra un clúster):

| Caso | Salida |
|---|---|
| Conexión agotada (backlog saturado) | `urlopen` da `URLError(TimeoutError)`; `request` da `RequestTimeoutError: GET /x agoto el tiempo de espera en 3 intentos` |
| Cabeceras a tiempo y cuerpo atascado dos veces | termina bien, 3 peticiones |
| Conexión rechazada | `URLError` inmediato, 0 esperas |
| Valores por defecto contra socket mudo | falla en 21.0 s (3×5 s + 2 s + 4 s) |
| `main check` como proceso real contra servidor mudo | `exit=1`; última línea `RequestTimeoutError: GET /api/folders/f agoto el tiempo de espera en 3 intentos` |

## Hallazgos

### F-01 · NARANJA · `tests/test_folder_permissions.py:204-234` · Comportamiento dentro del alcance que ninguna prueba protege
Mutaciones sobre `folder_permissions.py` en copia temporal, corriendo la suite completa:

| Mutante | Qué rompe | Resultado |
|---|---|---|
| M1: `time.sleep(BACKOFF * attempt)` pasa a `pass` | «con espera», que es alcance explícito | **sobrevive**, `14 passed` |
| M2: `time.sleep(0)` | ídem | **sobrevive**, `14 passed` |
| M3: `is_timeout` sin la rama `URLError` | tiempo agotado al conectar | **sobrevive**, `14 passed` |
| M5: reintentar cualquier `URLError` no HTTP | reintentos solo ante tiempo agotado | **sobrevive**, `14 passed` |
| M10: mensaje reemplazado por `"error 3"` | «error claro» | **sobrevive**, `14 passed` |

- **M3:** esa rama es la ruta real de un tiempo agotado al conectar (ver sonda), y el servidor lento de las pruebas solo ejercita el tiempo agotado al leer. Hoy funciona, pero borrarla no haría fallar nada.
- **M10:** `match="3"` es demasiado débil para probar que el error sea claro.
- **Qué falta:** afirmar las esperas (por ejemplo, registrar `time.sleep` con `monkeypatch`), un caso de conexión agotada, un caso de conexión rechazada con 1 solo intento, y un `match` sobre método, ruta y tiempo agotado.

Mutantes eliminados correctamente: M4 (solo rama `URLError`), M6b (reintentar solo el 403, lo detecta `test_forbidden_is_not_retried`), M7 (`ATTEMPTS=2`), M8 (`ATTEMPTS=4`), M9 (relanzar el error original). M6 (`if False:`) también muere, pero por pruebas existentes. Descarté M11 porque el mutante estaba mal construido y no aporta evidencia.

### F-02 · NARANJA · `folder_permissions.py:59-69` y `:130` · Reintentar `POST /api/folders` convierte una creación exitosa en un fallo engañoso
`request` reintenta todos los métodos. `ensure_team` tolera el 409, pero `apply` no lo tolera en `POST /api/folders` (línea 130). Si Grafana crea la carpeta y responde tarde, el reintento choca con el duplicado.

Sonda: `apply` contra un doble que crea la carpeta, responde tarde y devuelve 409 al duplicado.
```
HTTPError: HTTP Error 409: Conflict | folder-creado=True | posts=['/api/folders', '/api/folders']
```
La carpeta quedó creada, pero el proceso muere con un conflicto en lugar de terminar bien o dar el error claro que pide la tarea.

Límites de este hallazgo:
- **Código de respuesta:** el 409 es de mi doble; no confirmé qué devuelve el Grafana real ante un UID duplicado. Cualquier 4xx se propaga igual.
- **Impacto:** acotado. Antes del cambio este caso también fallaba, con `TimeoutError`. El Job tiene `backoffLimit: 2`, así que el siguiente pod vería la carpeta y seguiría. `check` solo hace GET y no se ve afectado.
- **Por qué es NARANJA:** el defecto de diagnóstico lo introduce este diff y está dentro del alcance. Falta una prueba de lectura de vuelta para este caso.

### F-03 · AMARILLO · `tests/test_folder_permissions.py:204-207` · Fixture `fast_timeouts` autouse
Baja `TIMEOUT` a 0.2 s en las 14 pruebas, incluidas las anteriores que no lo necesitan. En 9 corridas registradas bajo carga (3×nproc procesos ocupando CPU) todas dieron `14 passed`, con hasta 24.56 s. La décima corrida no quedó registrada en la salida, así que no la cuento. No demostré inestabilidad; solo es un margen estrecho innecesario. Además, `raising=False` en `BACKOFF` ya no hace falta y ocultaría un renombrado de la constante.

### F-04 · AMARILLO · `folder_permissions.py:72` · Código inalcanzable
`raise AssertionError("inalcanzable")` en producción solo se alcanza con `ATTEMPTS=0`. `fast_client` en las pruebas es un envoltorio sin función.

## Sobre la bitácora
Sus afirmaciones coinciden con mis corridas: conteos, rojo con `TimeoutError` y ruff. Su nota de que la prueba del 403 pasa también antes del cambio es correcta: en mi corrida contra la base solo fallan las otras dos. No afirma resolver la causa de los tiempos de espera en kind, como pide la tarea.

## No verificado
- `platform/tests/test_grafana_folder_permissions.py` no se corrió: levanta un Grafana real con testcontainers y no es criterio de esta tarea.
- Nada se ejecutó contra Grafana real ni contra un clúster.

## Tareas candidatas (defectos reales fuera de alcance)
- `push_metric` (`folder_permissions.py:149-154`) hace su propio `urlopen` sin reintentos. Un tiempo agotado contra el Pushgateway sigue tumbando el `check`.
- El Job y el CronJob fijan la imagen por digest (`manifests.yaml`, `sha256:f7610a22…`) y el Dockerfile copia este script. El cambio no llega al clúster hasta publicar imagen y digest nuevos, que esta tarea excluye. Hasta entonces los tiempos de espera en kind no pueden cambiar por este diff.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev/probes/probe.py`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev/probes/main.out`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/tasks/b8etw9go6.output`

NARANJA|tests/test_folder_permissions.py:204-234|Esperas, conexión agotada, conexión rechazada y claridad del error sin proteger (M1, M2, M3, M5, M10 sobreviven)
NARANJA|folder_permissions.py:59-69,130|Reintentar POST /api/folders convierte una creación exitosa en un 409 engañoso
AMARILLO|tests/test_folder_permissions.py:204-207|Fixture autouse baja TIMEOUT en todas las pruebas y raising=False sobra
AMARILLO|folder_permissions.py:72|Código inalcanzable y envoltorio fast_client sin función
INFORME: revisiones/U01-T06/ronda-1.md
VEREDICTO: NO-VERDE
