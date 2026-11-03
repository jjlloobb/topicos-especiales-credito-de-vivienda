# Ronda 5 — U02-T08

VEREDICTO: VERDE

Revisé el sha `32fffe5`. El diff de la ronda va de `9e8230e` a `32fffe5`, en tres commits:
- `80998a4`: la enmienda del orquestador. Toca solo la tarea.
- `589f894`: solo `vectra-risk/platform/tests/test_platform.py`, con +10 y −2 líneas.
- `32fffe5`: solo la bitácora y `revisiones/U02-T08/ronda-4-respuesta.md`.

El hash de la tarea coincide (`20bebafb…`). El codificador no tocó nada más que la prueba, la respuesta y la bitácora. El worktree sigue limpio después de la revisión.

Los 8 criterios pasan, y la guarda de U1 exige ahora la lista exacta de cuatro archivos. No queda ningún hallazgo nuevo.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 6 | `uv run pytest …test_realm_diff.py -q -rs && HYPOTHESIS_PROFILE=ci uv run pytest …test_realm_normalize.py -q` | pasa: 204 passed y 5 passed (30,5 s) |
| 2 | Reglas de la proyección | `uv run pytest identity-edge/tests/unit/test_realm_diff.py -q -rs` | pasa: 204 passed, 0 omitidas |
| 3 | Jobs contra Keycloak y Pushgateway falsos | `uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -rs` | pasa: 137 passed |
| 4 | Render y políticas | `make -C identity-edge render-jobs policy-jobs && uv run pytest …-k render` | pasa: conftest 555/555 y 5/5 ×3; 98 passed. El nuevo render sale idéntico a `rendered/` |
| 5 | `keycloak-reader` con tres roles | `realm_lint.py …realm.*.yaml && pytest …test_realm_lint.py …test_realm_files.py` | pasa: 629 passed |
| 6 | Dockerfile y políticas de U1 | `hadolint … && make -C identity-edge policy-jobs-u1` | pasa: Kyverno `pass: 16, fail: 0` ×3; conftest 35/35 y 3/3 ×3 |
| 7 | Regresión, ahora con `check-local` | `uv sync --frozen --offline && make -C identity-edge check && make -C platform check-tools && make -C platform check-local` | pasa: rc=0. `check` da 1509 passed; `check-tools` da `pass: 239, fail: 0`; `check-local` da 619 passed, `helm lint` 2/2 y los 203 Markdown sin enlaces rotos |
| 8 | Escaneo de U1 | `trivy fs --scanners misconfig … --skip-files <leído de supply-chain.yml> vectra-risk` (Trivy 0.76.1, sobre una copia limpia) | pasa: rc=0; los tres `identity-jobs.yaml` aparecen escaneados |

En CA-7 agregué `--offline` porque no hay red.

**`check-local` necesita un repositorio git.** La primera corrida fue sobre una copia hecha con `git archive` y falló una sola prueba, `test_ci.py::test_no_platform_or_gitops_file_is_git_ignored`, porque `git ls-files` devolvió 128 al no haber repositorio. Es un defecto de mi copia, no del diff. Repetí CA-7 completo en un clon local (`git clone` del worktree con checkout en `32fffe5`) y terminó en 0.

## La guarda exige la lista exacta (mutaciones sobre una copia de `supply-chain.yml`)
| Mutación de `skip-files` | `test_trivy_skips_only_the_kind_secret_read_and_the_realm_configmaps` |
|---|---|
| Sin tocar | 1 passed |
| Comodín `rendered/*/realm-configmap.yaml` | **falla** |
| Directorio `rendered/prod` en lugar del archivo | **falla** |
| Un archivo de más (`rendered/prod/identity-jobs.yaml`) | **falla** |
| Uno de menos (sin prod) | **falla** |
| Espacio tras la coma | **falla** |
| Una segunda línea `skip-files:` | **falla** (por el desempaquetado `(value,) =`) |

La prueba se renombró. No queda ninguna referencia al nombre viejo en código, workflows ni Makefiles. Solo aparece en la bitácora y en la enmienda de la tarea, como historia.

## Hallazgos
Ninguno nuevo en esta ronda. F-14 de la ronda 4 (rojo sin salida) queda corregido para esta ronda: la sección «Ronda 5» trae el rojo y el verde con sus salidas reales, sin `$(…)` sin expandir. F-15 sigue como candidata.

## Tareas candidatas
- Ninguna nueva. Una observación fuera de alcance: ninguna guarda cubre `skip-dirs` del mismo paso de Trivy, y se podría omitir `identity-edge/jobs/rendered` entero desde ahí sin que fallen ni esta prueba ni `test_t1_*`. Puede ir a `CANDIDATAS.md`.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/logs5/ (ca1, ca3–ca6, ca8, ca7.txt de la copia sin git y ca7-clon.txt del clon)

```
VEREDICTO: VERDE
INFORME: revisiones/U02-T08/ronda-5.md
```

VEREDICTO: VERDE
