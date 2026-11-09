# Ronda 1 — U05-T04

VEREDICTO: NO-VERDE

No hay ningún ROJO: los tres criterios de aceptación pasan en mis propias corridas. El veredicto es NO-VERDE por un solo NARANJA, F-01 (un literal incrustado que repite un valor de la configuración). Según la regla RL-4 de §6, solo un ROJO bloquea; esa decisión la toma el orquestador, no yo.

Lo revisado: rama `tarea/U05-T04` en `29284a4` contra la base `85ebd65`, 15 archivos. El archivo de la tarea tiene el hash `cb787a4`, que coincide con el que me dieron. El diff no toca `decision-registry/` ni nada fuera de `vectra-risk/{reference-model,aidlc-docs,bitacoras,tareas,CANDIDATAS.md}`. El worktree quedó limpio al terminar: `git status --short` sale vacío y HEAD sigue en `29284a4`.

## Criterios de aceptación, verificados por mí
Todo corrió desde `vectra-risk/` del worktree, en secuencia y en fresco. Las salidas están en el scratchpad.

| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Procedimiento de entrega y script de SHA | `uv run python platform/tests/test_runbooks.py --operational --root reference-model/docs && uv run pytest reference-model/tests -k "verify_release" -v` | **pasa**, código 0. `1 runbooks operativos con su runbook en regla`; `7 passed, 134 deselected in 0.79s`. Los 0,79 s se explican: son subprocesos sobre paquetes diminutos en `tmp_path`, sin estado externo |
| 1b | El paquete alterado hace fallar la verificación (con datos reales) | `make -C reference-model verify-release` sobre `.out` real; luego, sobre una copia en el scratchpad, agregué un byte a `proxy/run-3/predictor.json` y después borré `proxy/run-5` | **pasa**. Real: 6 `ok`, código 0. Alterado: `FALLA …run-3: sha256 distinto en predictor.json`, código 1. Sin run-5: `se esperaban package y 5 corridas proxy, hay 5`, código 1 |
| 2 | Cobertura ≥ 90 %, 100 % en `confidence.py`, trazabilidad | `uv run pytest reference-model/tests --cov --cov-branch --cov-fail-under=90 && uv run python platform/tests/test_traceability.py --unit reference-model --all` | **pasa**, código 0. `141 passed in 195.77s`; total 93,63 %; `confidence.py 40 0 12 0 100%`; `reference-model: 11 identificadores con trazabilidad` |
| 3a | Paso 11 N/A | `test ! -d reference-model/chart && test ! -d reference-model/migrations` | **pasa**, código 0 |
| 3b | `make -C reference-model check` | `make -C reference-model check` | **pasa**, código 0, 5 min 10 s. Corrió ruff check y format, `lint-imports` (3 contratos intactos), `141 passed`, 93,96 %, `coverage report` al 100 % en `confidence.py`, runbooks, trazabilidad y not-applicable, en ese orden |
| 3c | `make -C platform check` | `make -C platform check` | **pasa**, código 0. `pass: 309, fail: 0, warn: 0, error: 0, skip: 0` |
| 3d | Enlaces | `uv run python platform/tests/test_links.py` | **pasa**, código 0. `327 archivos Markdown sin enlaces rotos` |

La evidencia de la bitácora es coherente con el diff. El 93,96 % que reporta el codificador coincide exactamente con mi `make check`. El rojo previo que registra (61 % midiendo U0, y NFR-U5-01/02/03/20 sin trazabilidad) cuadra con el estado de `85ebd65`.

También cotejé contra la plataforma, sin ejecutarlos, los nombres que usa `release.md`. Todos existen y coinciden:
- las rutas de la bóveda `minio/engineer-upload` (`secretKey`) y `minio/root` (`user`/`password`), en `platform/data/chart/values.yaml:107,114`;
- la imagen `localhost:5001/mc:dev` y su `/usr/bin/mc`, en el Dockerfile `--target client`;
- `svc/minio` y `statefulset/minio` en `vectra-data`, y el contexto `kind-vectra`;
- los buckets `model-store` y `validation-datasets`, en `values-kind.yaml:13` y el diseño de U1;
- `POST /v1/models` con `ModelRegistration` y `artifact_format: xgboost_json`, en `governance-service.yaml:769,1691`.

## Hallazgos

### F-01 · NARANJA · `vectra-risk/reference-model/scripts/verify_release.py:24` · `PROXY_RUNS = 5` repite a mano `proxy.rt2_runs` de la configuración
El aprobado o la falla de `--out` depende de `len(found) != 1 + PROXY_RUNS`, y ese número aparece en el mensaje que lee el operador. El valor de verdad está en `reference-model/config/generator.yaml:124` (`rt2_runs: 5`), y `release.py:267` lo lee de ahí. Si alguien cambia `rt2_runs`, `make release` produce N corridas y `verify-release` falla, o deja pasar, contra un 5 que nada sincroniza. Ninguna prueba lo detectaría: `test_verify_release.py:47` también fija 4 y 5.

Barrido de la clase: en código, esta es la única instancia. En el documento, `release.md` incrusta las mismas cifras como texto de verificación: «5 corridas» (pasos 2 y 5), «lista los 7 archivos» (Verificación 1) y «muestra 6 prefijos `mv-…`» (Verificación 4). Este último además falla en cuanto el bucket tenga una entrega previa. Hay que corregirlas junto con el script.

Posibles arreglos, todos dentro del alcance:
- que el Makefile pase `--proxy-runs` leído de la configuración;
- o que el script lea `rt2_runs` de la configuración;
- o, como mínimo, una prueba que compare `PROXY_RUNS` con `generator.yaml`.

### F-02 · AMARILLO · `vectra-risk/reference-model/docs/release.md`, paso 3 · el procedimiento manda usar la raíz de MinIO
La tarea y NFR-U5-03 piden subir con las credenciales del ingeniero. El documento indica subir el dataset de validación con `minio/root`. El vacío de diseño es real: `risk-engineer-upload` solo tiene `model-store-upload`. Arreglarlo es trabajo de U1, fuera de alcance, y la candidata ya está anotada. Aun así, prescribir la raíz convierte un atajo en procedimiento. Mejor marcar el paso como `[PENDIENTE U1]` y dejar el uso de la raíz como excepción explícita del administrador. No bloquea: está declarado con transparencia en el documento, en `cierre-demo.md` y en las candidatas.

### F-03 · AMARILLO · trazabilidad · NFR-U5-01, 02 y 20 pasan solo porque se nombran en `release.md`
`test_traceability.py` los da por cubiertos por una mención en la sección «Diferido». El codificador lo declara en tres sitios, el diferimiento lo sanciona `demo-kind-alcance.md` (Paso 8 D) y la candidata está anotada. Aun así, CA-2 los cuenta dentro de los «11 identificadores con trazabilidad» sin que haya código detrás.

### F-04 · AMARILLO · `vectra-risk/reference-model/pytest.ini:3` · ruta relativa al directorio de trabajo y pérdida de la configuración raíz
`--cov-config=reference-model/coveragerc` solo resuelve si pytest se lanza desde `vectra-risk/`. Además, el `pytest.ini` desplaza el `[tool.pytest.ini_options]` raíz (`asyncio_mode`, `markers`). Hoy no afecta: no hay marcadores ni pruebas asíncronas en U5, y la candidata está anotada.

### F-05 · AMARILLO · `vectra-risk/reference-model/scripts/verify_release.py:39-50` · casos de borde
Un manifiesto con `"files": []` en un directorio vacío devuelve `ok`. Los subdirectorios dentro del paquete no se reportan como «no listados», porque solo se miran archivos. Riesgo bajo; conviene exigir al menos un archivo y señalar las entradas que no sean archivos.

Fuera de los hallazgos, sobre la invariante 6: las pruebas del script leen el `stderr` (el motivo concreto), no solo el código de salida. Y el script no cambia estado.

## Tareas candidatas (defectos reales fuera de alcance)
- U1: política de escritura de `risk-engineer-upload` sobre `validation-datasets` (ya en `CANDIDATAS.md`).
- `platform/tests/test_traceability.py`: reconocer BR y PBT en párrafos, y exigir una marca explícita para los diferidos en vez de aceptar una mención suelta (ya en `CANDIDATAS.md`).
- U3 y U4: comprobar qué mide `--cov` sin argumento en sus planes (ya en `CANDIDATAS.md`).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/u05t04r1/summary.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/u05t04r1/ca1.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/u05t04r1/ca2.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/u05t04r1/ca3-ref.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/u05t04r1/ca3-plat.log`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/4b74319d-fa8c-408a-94c3-00933d95328f/scratchpad/u05t04r1/ca3-links.log`

```
VEREDICTO: NO-VERDE
NARANJA|vectra-risk/reference-model/scripts/verify_release.py:24|PROXY_RUNS = 5 repite a mano proxy.rt2_runs de la configuración
INFORME: revisiones/U05-T04/ronda-1.md
```
