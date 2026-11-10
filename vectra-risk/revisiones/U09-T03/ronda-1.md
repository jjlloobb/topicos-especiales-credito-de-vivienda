# Ronda 1 — U09-T03

VEREDICTO: VERDE

Revisé el sha 149057f de `tarea/U09-T03` contra la base `ec08f84`. El blob de la tarea coincide (4180a025…). Corrí yo mismo los nueve criterios. Todos pasan y no queda ningún ROJO ni NARANJA. El worktree quedó limpio al terminar (`git status --short` sin salida; solo aparece la caché ignorada `.import_linter_cache/`). El diff no se sale de su alcance: no toca `pyproject.toml`, `uv.lock` ni otras unidades, y no cambia ninguna aserción de las pruebas de U09-T02.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Paso 9 | el comando literal de CA-1, `HYPOTHESIS_PROFILE=ci … -v` | pasa: 47 passed en 49,9 s, semilla 1136398099, sin omitidas. Con `--hypothesis-show-statistics`, PBT-U9-07 da 500 casos que pasan en cada una de las 2 propiedades |
| 2 | Punto de entrada real | `uv run pytest bias-monitoring/tests/integration/test_entrypoint.py -v` | pasa: 5 passed en 10,5 s. Además lancé yo `python -m vectra_bias.app` (detalle abajo) |
| 3 | Literales y regresión del Bloque C | `! grep -nE …` y después las pruebas de clients, publish y run | pasa: el grep no encuentra nada y salen 54 passed. Los tres archivos de prueba de U09-T02 no cambian en el diff |
| 4 | Imports y arquitectura | `lint-imports` y `test_architecture.py` | pasa: 4 contratos kept, 0 broken; 2 passed |
| 5 | Cobertura, **comando literal sin `-m`** | `HYPOTHESIS_PROFILE=ci uv run pytest bias-monitoring/tests --cov=vectra_bias --cov-branch --cov-fail-under=95 && coverage report --include=… --fail-under=100`, más `test -s services.md` | pasa: **256 passed (con las 7 de simulación) en 9 min 40 s**, semilla 3066580536. Total 99,92 %, los tres módulos puros al 100 %, salida 0, `services.md` no vacío |
| 6 | PBT con el perfil `ci` y NFR-U9-52 | la parte `property` y `coverage` del `make check` de la fila 8, y el `grep` | pasa: property 15 passed (semilla 4158115054); coverage de la librería 43 passed, 100 %. El grep encuentra NFR-U9-52 en los tres archivos y la línea 80 de `services.md` es la sección pedida |
| 7 | Trazabilidad | `test_traceability.py --all` en la rama y en una copia de la base sacada con `git archive` | pasa: ningún fallo nuevo. NFR-U9-02, 12, 32 y 41 quedan trazados; NFR-U9-51 sigue sin traza y no aparece en `bias-monitoring/` (grep vacío). Las 4 líneas de NFR-U0 que solo salen en la copia de la base vienen de correr fuera de git, no de la rama |
| 8 | `make -C bias-monitoring check` | ese mismo comando | pasa: salida 0 en 11 min 42 s. lint, imports, test (191), property (15), coverage (43), coverage-bias (249 passed y 7 deselected, 99,92 %) y simulación (7) |
| 9 | Estado del plan | `git diff ec08f84 -- <plan>` | pasa: solo cambian las dos líneas de los Pasos 9 y 10, en `[x]` con `(U09-T03)` y la nota de `mutmut` |

**Las cuatro cosas que me pediste comprobar:**

1. **CA-5 con el comando literal:** pasa, incluida la simulación (fila 5). La afirmación del codificador sobre `-m "not simulation"` deja de importar: el comando literal también da 0.
2. **Tiempos de PBT-U9-05:** sus cifras se reproducen. Las de la tarea, no.
   - 120 × 80: 18 s en mi máquina (él midió 29 s), semilla 1663144163, 120 casos que pasan.
   - 500 × 80: 130 s (él midió 137 s). Lo corrí con un script del scratchpad que solo cambia `settings` al ejecutar, sin tocar fuentes.
   - Eso son unos 16 ms por corrida, lejos de los ≈ 0,15 s y los más de 6 min que justificaron el 120 × 80.
3. **Interpretaciones, contrastadas con el OpenAPI y los diseños de U9.** El OpenAPI solo dice «Problem» para los errores, sin códigos.
   - **422 por una celda repetida:** se sostiene. La tabla de errores de `domain-entities.md` §5 dice «tablas inválidas → 422». Comprobé además que `vectra_disparity.CountTable` acepta celdas duplicadas sin quejarse: sin esta validación se contarían dos veces.
   - **`pre` y `post` con la ventana de 1970:** lo obliga U0. `DisparityResult` exige `model_version_id`, `window_from` y `window_to`, y `CompareSourceRequest` no trae ninguno. governance no lee esos campos (`evidence.py`), pero los guarda en `data_source_event`. Queda como F-03 y como tarea candidata.
   - **404 sin `version` y 200 con `version`:** se sostiene. `DisparityView.model_version_id` es obligatorio, así que sin versión que resolver no hay nada que devolver. Con una versión pedida, «todo insuficiente» encaja con la supresión de celdas chicas.
   - **`principal_role` unido con comas:** no hay precedente en U0 ni en otras unidades, y el campo está en singular. Queda como F-02.
4. **El proceso real:** lancé `python -m vectra_bias.app` como subproceso, con las 7 variables reales y `PATH`, contra los dobles HTTP de `tests/doubles/http_doubles.py`.
   - Respuestas: `GET /v1/freezes` como cro da 200; `/{id}` como cumplimiento da 200; un id inexistente, 404 `not_found`; `/{id}` como cro, 403; `/v1/disparity?version=v1` da 200 con el `disclaimer`; analista, 403; sin token, 401.
   - `/metrics` en 8081 trae `vectra_bias_cache_lookups_total{result=…}` y `vectra_bias_cache_entries`.
   - Con `SIGTERM` el proceso termina en 0,31 s.
   - `-X importtime` no carga ni `freeze_client` ni `run`.
   - Las llaves de `create_app` son exactamente las cuatro `(método, ruta)` de `REGISTRY["bias-monitoring-service"]`.

## Hallazgos
### F-01 · AMARILLO · `bias-monitoring/Makefile:23-24` y `tests/property/test_run_machine.py:228-230` · Los comentarios dan como hecho una cifra que `services.md` desmiente
Los dos comentarios dicen «~0,15 s por corrida y 500 x 80 pasaba de 6 min». `services.md` (sección «PBT-U9-05 frente a NFR-U9-52») y mi propia medición (130 s para 500 × 80) lo contradicen. El codificador cumplió la letra de la tarea, que le pedía esa razón, pero los tres sitios quedan incoherentes entre sí. Le toca decidir al usuario (ver «Para el orquestador»).

### F-02 · AMARILLO · `src/vectra_bias/app.py` (`_role`) · `principal_role` lista todos los roles del token
El campo es singular y el valor `",".join(sorted(roles))` registra cualquier rol del usuario, también los que no tienen que ver con la ruta (por ejemplo `analista,cumplimiento`). Sería más preciso registrar el rol que autorizó la consulta, es decir, la intersección con `route.roles`. No bloquea.

### F-03 · AMARILLO · `src/vectra_bias/compare.py` (`EPOCH`, `"pre"`/`"post"`) · Valores de relleno en el `PrePostReport`
Son valores inventados que acaban en un registro de auditoría (`data_source_event`). El codificador lo declaró abiertamente. El arreglo de fondo es de U0 (tarea candidata abajo).

### F-04 · AMARILLO · `tests/integration/test_gaps.py:45` · Una prueba sin ninguna aserción
`test_a_service_without_token_source_is_skipped` solo ejecuta `acquire_tokens([None])`: sirve para la cobertura, pero no comprueba nada. Debería afirmar el resultado, por ejemplo que no hubo ninguna llamada a Keycloak.

## Tareas candidatas (defectos reales fuera de alcance)
- U0: en `PrePostReport` (o en un `DisparityResult` de fuente), que `model_version_id` y la ventana sean opcionales, o que `CompareSourceRequest` traiga las versiones activa y candidata. Así no hacen falta «pre», «post» ni 1970.
- U0, `vectra_common`: una convención única para `principal_role` en los logs de consulta, para U8, U9 y U10.

## Para el orquestador
NFR-U9-52 quedó enmendado con una justificación (≈ 0,15 s por corrida, más de 6 min para 500 × 80) que no se reproduce: 500 × 80 cuesta unos 2 min. El usuario debería decidir con la cifra real si quiere el 500 × 80 literal.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/ca5-literal.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/ca8-check.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/trace-branch.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/trace-base.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/manual_launch.py (el arranque manual del proceso real)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/run500.py (la medición de 500 × 80)

```
VEREDICTO: VERDE
AMARILLO|bias-monitoring/Makefile:23-24 y tests/property/test_run_machine.py:228-230|los comentarios dan como hecho una cifra de PBT-U9-05 que services.md desmiente
AMARILLO|src/vectra_bias/app.py (_role)|principal_role lista todos los roles del token
AMARILLO|src/vectra_bias/compare.py (EPOCH, "pre"/"post")|valores de relleno en el PrePostReport, obligados por U0
AMARILLO|tests/integration/test_gaps.py:45|una prueba sin ninguna aserción
INFORME: revisiones/U09-T03/ronda-1.md
```
