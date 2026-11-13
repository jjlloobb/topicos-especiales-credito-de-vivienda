# Ronda 1 — U10-T02

VEREDICTO: NO-VERDE

No hay ningún ROJO. Los 12 CA pasan con mi propia ejecución sobre HEAD `5f6d774`. El diff no se sale del alcance. El NO-VERDE se debe a **un NARANJA**, F-01: la prueba del «pool agotado» no comprueba el pool. Según RL-3, ese hallazgo va a `CANDIDATAS.md` y no bloquea. Esa decisión es del orquestador; yo no rebajo la severidad.

Comprobaciones previas:
- Blob de la tarea: `b7aa52fe316059634995d0732eb5b4a2e6d65352`, coincide.
- Diff `a782f25..5f6d774`: 4 commits y 37 archivos.
- Worktree: `git status --short` vacío al empezar y al terminar.
- Ningún proceso queda escuchando en 8080 ni en 8081.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado (uptime / carga 1 min) |
|---|---|---|---|
| 1 | Rutas, clientes, composición | `uv run pytest …/test_compose.py …/test_clients.py …/test_routes_registry.py -v` | pasa: 85 passed, 0 skip, en 16,3 s. Carga 16,7 → 18,3. El caso de 500 ms con las dos ramas en paralelo tardó 0,51 s (< 0,7) |
| 2 | 30 rutas con su handler y su regla | el `python -c` de la tarea, con las 7 variables | pasa: imprime `30 30`. Carga 17,1 |
| 3 | `client_errors` y métricas | `uv run pytest …/test_client_errors.py …/test_metrics.py -v` | pasa: 20 passed, 0 skip. Carga 18,5 |
| 4 | PBT-U10-01 y ejemplos del FD | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_role_matrix.py …/test_api_examples.py -v` | pasa: 323 passed, 0 skip. La PBT da «500 passing, 0 failing» (`--hypothesis-show-statistics`). Carga 16,7 → 15,0 |
| 5 | La matriz coincide con C03 y con la versionada | `uv run python console/bff/tools/role_matrix.py --check` | pasa: «30 endpoints comparados». Rojo reproducido: con una copia de C03 donde `retry_case` pasa a tener `analista`, sale con rc=1 y nombra la fila |
| 6 | Arranque, sondas y apagado | `uv run pytest …/test_app.py …/test_service_shutdown.py -v` | pasa: 21 passed, en 14,3 s. Carga 12,6 → 13,9 |
| 7 | Cobertura | las dos corridas de la tarea | pasa: 517 passed con el 100 % total (530 sentencias y 88 ramas), y 341 passed con `object_rules` y `errors` al 100 %. No hay `omit`. El único `# pragma: no cover` está en `app.py:122`, en la guarda `__main__`. Carga 12,3 → 17,9 |
| 8 | Sin base de datos | el comando de la tarea | pasa: `OK` |
| 9 | Contratos de imports, sin `httpx` | `lint-imports` + `grep` | pasa: `Contracts: 3 kept, 0 broken.` y el `grep` no imprime nada |
| 10 | Documentación, plan y constantes | el comando de la tarea | pasa: existe `bff-api.md`; salen las 5 líneas de los Pasos 5 a 9 con `(U10-T02)`; imprime `1.5`; la fila 45 de P-U10-04 nombra `get_case_identifiers` |
| 11 | Trazabilidad «sin fallos nuevos» | `--unit console --all \| grep …`; además `--all` en la base (`git archive a782f25`) y en la rama | pasa: el primer `grep` no imprime nada. Base con 67 fallos y rama con 54: **0 nuevos** y desaparecen exactamente los 13 de la tarea |
| 12 | `make -C console check` | `make -C console check` sobre HEAD `5f6d774` | pasa: **rc=0**. Carga 17,7 a las 12:47:22 y 10,3 a las 12:50:27. Dentro: ruff, mypy, import-linter, ESLint, tsc, 517 + 341 pruebas, `role_matrix --check` y vitest (35 de 35) |

## Comprobaciones específicas del encargo
- **`make check` después de `3b7b02b`.** El codificador no lo volvió a correr; lo dice con honestidad en la bitácora, línea 333, donde el verde completo es de `e7fc11f`. Mi corrida sobre HEAD sale con rc=0, también la parte de ESLint de la SPA, con una carga de 17 a 10. No reproduje el timeout de vitest. La evidencia queda al día.
- **`SIGTERM` y `_exit_clean`.** Lo comprobé con un proceso real, `python -m console_bff.app`, y una solicitud en vuelo. El destino tarda 1,4 s y el `SIGTERM` llega a 1,0 s. Resultado:
  - la solicitud en vuelo recibe **200** con el cuerpo completo;
  - una conexión nueva durante el apagado da `ConnectError`;
  - el proceso sale con **código 0** 0,89 s después de la señal.
  
  El manejador de uvicorn está activo durante `serve()`. `_exit_clean` solo actúa antes de escuchar o cuando uvicorn vuelve a emitir la señal, ya terminados el drenaje y el lifespan, que incluye `upstreams.aclose()`. No se salta el apagado ordenado. Con un destino que tarda 4 s, la solicitud en vuelo sale con 503 al vencer el timeout de 1,5 s, y también sale 0. El cierre de los cinco clientes lo fija `test_shutdown_closes_the_five_clients`.
- **Puertos fijos 8080 y 8081.** La prueba es frágil por diseño, pero no hay alternativa: `run_service` de U0 no acepta puertos y la tarea exige `python -m`. Ver F-02.
- **Alcance.** El diff no toca `contracts/`, `vectra_common`, la SPA, el chart, `Dockerfile`, workflows, `uv.lock` ni `pyproject.toml`. Todo está dentro de `console/bff/`, `console/Makefile`, la documentación de U10 y el plan, la bitácora y `CANDIDATAS.md`.

## Mutaciones (sobre una copia en el scratchpad; el worktree no se tocó)
| Mutación | Resultado | La mata |
|---|---|---|
| M01 `analista` de más en `approve_model` | muere | celda `approval-analista` |
| M02 `get_dossier` pierde `cumplimiento` | muere | celda `dossier-cumplimiento` |
| M18 `approve_model` sin `mfa` | muere | celda `approval-acr_pwd` |
| M03 `CONFLICT` no lanza error y deja pasar la escritura | muere | `…409_and_the_destination_gets_zero_writes[record_explanation_view]` |
| M04 `retirement` sin lectura previa | muere | `…zero_writes[retire_model]` |
| M05 `FORBIDDEN` deja pasar | muere | `test_a_forbidden_object_verdict…` |
| M06 `get_dossier` en serie | muere | `test_the_two_branches…run_in_parallel` |
| M07 registro caído sin cancelar case (`gather`) | muere | `test_registry_down_is_503_and_the_case_call_is_cancelled` |
| M15 un 403 de case se vuelve `identifiers_unavailable` | muere | `test_the_dossier_for_compliance_with_a_case_403_is_403` |
| M08 P-2: el timeout sale como 504 | muere | `…cut_at_its_timeout_for_real` |
| M09 P-1: `get_case_identifiers` con 5 s en `config` | muere | `test_config` |
| M10 P-1: usar la clave `case.get_case` en lugar de `get_case_identifiers` | sobrevive, pero es **equivalente** (las dos valen 1,5 s) | — |
| M11 el cliente ignora `CONNECTIONS_PER_REPLICA` (1000) | **sobrevive** | — (F-01) |
| M12 case con 21 conexiones | **sobrevive** | — (F-01) |
| M13 y M19 ventana del breaker en 25 | muere | `test_readyz…circuits_open` y `test_an_open_circuit_answers_503_at_once_with_zero_calls` |
| M16 se ignora un plazo entrante menor | muere | `test_an_incoming_smaller_deadline_wins…` |
| M17 caché de governance en `get_disparity` | muere | `test_disparity_twice_is_two_calls…` |

## Hallazgos
### F-01 · NARANJA · `console/bff/tests/integration/test_clients.py:408-438` · La prueba de «pool agotado» pasa igual sin pool
`_Slow.hold = 3.0` y la llamada número 21 va a la misma ruta lenta con un timeout de 1,5 s. `deps._send` usa `httpx.Timeout(timeout)` por fase, así que:
- con el pool lleno, la llamada corta por `PoolTimeout` a 1,5 s;
- sin límite de conexiones, conecta y corta por `ReadTimeout` a 1,5 s.

El resultado es el mismo, y por eso M11 (1000 conexiones) y M12 (21) sobreviven: 514 passed. Ninguna prueba comprueba que `Upstreams` pase `CONNECTIONS_PER_REPLICA[name]` al `DependencyClient`; `test_config` solo comprueba la constante.

El comportamiento real sí es correcto. Lo demostré con `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t02/probe/pool.py`, donde la llamada 21 va a una ruta **rápida**:
- con 20 conexiones ocupadas: `DependencyTimeout 1.51s`;
- con 19 ocupadas: `200 0.01s`.

Arreglo propuesto: que la llamada 21 vaya a una ruta que responde al instante.

### F-02 · AMARILLO · `test_service_shutdown.py` · Puertos fijos: puede fallar por el entorno y, en un caso estrecho, pasar en falso
Si el puerto está ocupado más de 90 s, la prueba falla; eso ya lo explica el codificador. Además hay una carrera entre `ports_are_free` y el `bind` del hijo. En ese hueco, `wait_for(/readyz)` y la búsqueda de `vectra_console_client_errors_total` pueden contestarse desde **otro** BFF que esté en 8081. `process.poll()` y el código de salida reducen ese riesgo, pero no lo eliminan. El origen es que `run_service` de U0 no acepta puertos; ya está como candidata en `CANDIDATAS.md`.

### F-03 · AMARILLO · `compose.py` (`get_disparity`, `"page_size": 100`) · Literal sin nombre en un punto de decisión
Si governance tuviera más de 100 versiones `activo` o `congelado`, `serviceable_version` decidiría sobre una página incompleta. No lo ve el usuario y es irreal hoy, pero conviene darle nombre o comprobar `total`.

## Tareas candidatas (defectos reales fuera de alcance)
- U0, `ops_server.run_service`: aceptar puertos configurables (evita F-02) y salir con 0 tras un `SIGTERM` ordenado. Ya registrado por el codificador; lo confirmo.

## Rutas de transcripciones largas
- Logs de los CA: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t02/logs/ca1.txt`, `ca3.txt`, `ca4.txt`, `ca6.txt`, `ca7.txt`, `ca12.txt`
- Trazabilidad base y rama: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t02/logs/trace-base.txt`, `trace-rama.txt`
- Drenaje con `SIGTERM`: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t02/logs/drain-1.4s.txt`, `drain-4s.txt`
- Mutaciones: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t02/logs/mutaciones.txt` y `mut-M*.txt`. El script es `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev-u10-t02/mutate.py`

```
VEREDICTO: NO-VERDE
NARANJA|console/bff/tests/integration/test_clients.py:408|La prueba de pool agotado pasa igual sin límite de conexiones (M11 y M12 sobreviven)
INFORME: revisiones/U10-T02/ronda-1.md
```
