# Ronda 1 — U06-T01

VEREDICTO: VERDE (RL-1..RL-5: ningún ROJO; un NARANJA y varios AMARILLO pasan a candidatas)

Rama `tarea/U06-T01` @ `fcec273`, base `bb86d71`. Worktree limpio antes y después de mi revisión (salvo este informe).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Paso 1 | `uv sync --frozen && uv run lint-imports --config model-serving/.importlinter && make -C model-serving check` | pasa, rc=0: `1 kept, 0 broken`; ruff, mypy --strict; `36 passed in 47.97s` (perfil ci) |
| 2 | Paso 2 | `uv run pytest model-serving/tests/unit/test_package_loader.py model-serving/tests/unit/test_concurrency.py -v` | pasa: `24 passed in 36.11s`, 0 omitidas; RT3-a/d no listos, byte alterado en 4 archivos, N+1 → 503 por HTTP |
| 3 | Paso 3 | `pytest .../integration/test_predictor.py -v`; `HYPOTHESIS_PROFILE=ci pytest model-serving/tests -k "PBT_U5_04 or pbt_u5_04" -v` | pasa: `7 passed`; `2 passed, 34 deselected in 48.18s`, `hypothesis profile: ci` (500 ejemplos) |
| 4 | Paso 4 | `HYPOTHESIS_PROFILE=ci pytest .../property/test_explainer.py -v` | pasa: `3 passed in 47.34s`, perfil ci |
| 5 | Paso 5 | hadolint (checkout principal, v2.15.1 = `tools.env`), `make -C model-serving image-predictor image-explainer`, `docker image inspect`, `pip list`, `grep FROM@sha256` | pasa: hadolint rc=0; build rc=0; `65532:65532` y `OK` en las dos; 4/4 `FROM` por digest |
| 6 | check unidad + U1 | `make -C model-serving check && make -C platform check` | unidad rc=0. platform: `check-local` verde (`789 passed`, helm lint, trazabilidad, runbooks, waves, `372 archivos Markdown sin enlaces rotos`); `check-tools` falla por `kubeconform`/`egctl`/`k6` ausentes también en el checkout principal (no es del diff). Respaldo: `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib` → `274 passed in 4.53s` (pruebas estáticas, el tiempo es coherente) |
| 7 | Casillas del plan | `git diff bb86d71...HEAD -- .../model-serving-code-generation-plan.md` | pasa: solo 5 casillas, con las marcas pedidas |

Las suites de pruebas tardan 36–48 s: corren la entrega real de U5 (`run_release`) por sesión; no hay omisiones.

## Verificaciones adicionales (las pedidas en el encargo)

**1. `--all` (DECISIONES-LOOP §6 con enmienda).** Corrí `test_traceability.py --all` en la rama (rc=1) y sobre `git archive bb86d71` (rc=1). Diferencia: en la base `model-serving: sin código, se omite`; en la rama 14 ids nuevos, todos de U6 (sin `cierre-demo.md`). Cruce con los pasos del plan:
- Pasos 6–11 (no cubiertos): INF-U6-01/02, NFR-U6-02, 11, 12, 20, 21, 22, 31, P-U6-02, 04 → admitidos por la enmienda.
- NFR-U6-10 (Pasos 3, 4 y 11): su verificación es «prueba de carga de U12 en kind»; la tabla de la tarea difiere el benchmark (T3). Recortado por intención.
- NFR-U6-30, 32 (Paso 5): la verificación de ambos (supply-chain + `kyverno test`; políticas de Kyverno sobre el pod) está diferida (T1, plantilla del Paso 6).
**Dictamen: `--all` cuenta como pasado con el mismo criterio por intención que U09-T01 ronda 4** (sigue abierta la candidata para aclarar el texto de §6). Ver F-03 sobre la etiqueta de NFR-U6-32.

**2. `envelope` no declarado.** Correcto en lo técnico y cumple NFR-U6-01: `vectra_reference/__init__.py` y `envelope/__init__.py` son solo docstrings; `confidence.py` importa `math`, `decimal`, `numpy`. Import-linter es efectivo sobre ese código: `vectra_reference` es root package y el contrato `forbidden` revisa cadenas indirectas. Lo comprobé con una config temporal (en el scratchpad) que prohíbe `vectra_reference.envelope.confidence` → `vectra_predictor is not allowed to import vectra_reference.envelope.confidence` (cadena `app→core→confidence`), y otra que prohíbe `shap/sklearn/pandas/xgboost` desde `confidence` → `KEPT`. Las imágenes copian los mismos archivos fuente que el linter analiza. En desarrollo funciona por el grupo `dev` de la raíz, pero el `pyproject` de U6 no declara lo que importa (F-01).

**3. `xgboost --no-deps`.** `uv.lock`: numpy 2.5.4, scipy 1.18.1, xgboost 3.4.1 (cuyas deps son numpy, scipy y `nvidia-nccl-cu13`). En las dos imágenes, `importlib.metadata`: `numpy 2.5.4, scipy 1.18.1, xgboost 3.4.1`, `shap None`, `sklearn None` y ningún `nvidia-*`. **Carga del modelo real:** generé una entrega de U5 (`run_release`) y la pasé por stdin (sin `-v`) a `docker run --read-only --tmpfs /tmp`; levanté `python -m vectra_predictor`/`vectra_explainer` reales con `MODEL_VERSION_ID=mv-2026-01-01-51241dc4`: `/readyz 200`; 5 filas de `test`: score y `confidence` **idénticos** a los del host (p. ej. `0.001058 0.7606`); `:explain` → 12 contribuciones y suma+base = logit del score (`-6.850701`); el histograma cuenta 5 por componente. Con una anotación errónea: `/readyz 503`, `vectra_serving_package_integrity_failed_total{component="predictor"} 1.0` y log `ModelPackageIntegrityFailed ... reason=manifest_version_mismatch`. Esto cubre la pieza que la bitácora dejó para el Paso 11.

**4. Fixtures reales.** `conftest.py` usa `vectra_reference.release.run_release` (modelo base real, AUC exigido) y `vectra_reference.adversarial.rt3_cases` sobre ese paquete; PBT-U5-04 compara con `vectra_reference.envelope.confidence` importado de U5, no con una copia. La propiedad de la suma compara `Explainer` contra el margen de `Predictor` (componentes distintos y el mismo paquete). El único doble (`_BlockingPredictor`) está en la prueba HTTP del semáforo, donde corresponde.

**5. Forma HTTP.** Ni el diseño de U6 ni el de U7 (`scoring-explainability/functional-design/*`, `nfr-design/logical-components.md`, plan U7 Pasos 8, 10 y 11) fijan el cuerpo: solo dicen «`:predict` → score, confidence, model_version_id» y «`:explain` → contribuciones, base_value, model_version_id». Lo implementado (`instances` de 1 → `predictions`/`explanations`) es v1 de KServe, como pide el plan de U6, y los nombres de los campos coinciden con U7. No contradice nada; queda sin fijar del lado de U7 (la candidata del codificador es correcta).

## Hallazgos

### F-01 · NARANJA · model-serving/pyproject.toml:6-15 · Dependencia `envelope` no declarada; la tarea pedía detenerse
La tarea dice: «si falta algo allí (por ejemplo, que `envelope` no se pueda importar como dependencia), **detente y repórtalo**». El codificador lo resolvió solo y la bitácora lo llama «sin vacío de especificación que bloquee». La solución es sólida y la verifiqué (punto 2), pero no cumple el texto del Paso 1 («`pyproject.toml` con … la librería `envelope` de U5»). `vectra-model-serving` importa `vectra_reference` sin declararlo: `uv sync --package vectra-model-serving` no lo instalaría, y nada automatiza que la lista de COPY del Dockerfile siga a `confidence.py` si este gana un import interno (`vectra_reference.features`, por ejemplo). Por RL pasa a candidata. El orquestador debe ratificar la desviación, y la candidata de extraer `vectra-envelope` ya está en `CANDIDATAS.md`. Conviene añadir una prueba de humo de import dentro de la imagen.

### F-02 · AMARILLO · tests/property/test_explainer.py · NFR-U6-01 pide 1 000 filas de `test`
La verificación del NFR dice «para 1 000 filas de `test`». La prueba usa 500 vectores generados (perfil ci) más 1 fila de `test`. El plan (Paso 4) la formula por generación, y eso es lo que rige. Añadir el barrido sobre las filas de `test` costaría poco.

### F-03 · AMARILLO · bitácora, «Trazabilidad» · NFR-U6-32 mal etiquetado; ids de pasos posteriores citados
NFR-U6-32 no trata de «firma y SBOM»: trata de `runAsNonRoot`, `readOnlyRootFilesystem` y `automountServiceAccountToken: false` en el pod. La parte de imagen sí entró (`USER 65532:65532`, y la imagen corre con `--read-only`, como verifiqué). En sentido inverso, `concurrency.py` y `test_concurrency.py` citan NFR-U6-41 (Paso 11), y `metrics.py`/`package_loader.py` citan P-U6-06 (Paso 9). P-U6-05 «satisface NFR-U6-41», así que son defendibles, pero adelantan como trazados ids cuya verificación es de pasos posteriores.

### F-04 · AMARILLO · predictor/Dockerfile, explainer/Dockerfile · Cada imagen lleva el paquete de la otra
El wheel de `model-serving` empaqueta los tres paquetes. La imagen del explicador trae `vectra_predictor`, que no podría importarse ahí porque falta `vectra_reference`. Es inofensivo, pero es código muerto en la imagen.

### F-05 · AMARILLO · Dockerfiles:16 · Transitivas de `vectra_contracts`/`vectra_common` sin fijar a `uv.lock`
Solo numpy, scipy y xgboost están fijados. El resto se resuelve en el build, igual que en `decision-registry/Dockerfile`. Es un defecto de clase de las imágenes de Python del repo, no solo de esta tarea.

## Tareas candidatas (defectos reales fuera de alcance)
- `platform/.tools` del checkout principal sin `kubeconform`, `egctl` ni `k6`: `make -C platform check` no puede dar rc=0 en ningún worktree (ya visto en U04-T04).
- DECISIONES-LOOP §6: aclarar el caso de ids parcialmente implementados en un paso cubierto cuya *verificación* está diferida (NFR-U6-30/32), junto con la candidata abierta de U09-T01 ronda 4.
- Fijar las dependencias transitivas de las imágenes Python a `uv.lock` (p. ej. `uv export --frozen` → `pip install -r`), para todas las unidades (F-05).
- Prueba de humo `python -c "import vectra_<c>.__main__"` dentro de cada imagen en el Makefile de U6 (F-01, F-04).

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/ca1.log, ca2.log, ca3a.log, ca3b.log, ca4.log, ca5-build.log, ca6-platform.log
- …/scratchpad/trace-branch.log, trace-base.log (y b.txt / r.txt con los conjuntos de fallos)
