# Ronda 4 — U02-T08

VEREDICTO: VERDE

Revisé el sha `f75be5b` sobre `b9577ff`. El diff de la ronda va de `d16ae17` a `f75be5b`, en tres commits:
- `3f35d6f`: la enmienda T1 del orquestador.
- `3845024`: el código.
- `f75be5b`: la bitácora y la respuesta.

El hash de la tarea coincide (`fc402388…`). Corrí todo en copias nuevas (`git archive f75be5b`). Trivy corrió sobre una copia limpia, sin `.venv`, `.tools` ni `.charts`, como la ve el CI. Al terminar, el worktree del codificador sigue limpio.

Los 8 criterios pasan. La excepción alcanza solo los tres ConfigMaps del realm, los CronJobs y las ServiceAccount se siguen escaneando, y del workflow solo cambió `skip-files`. Quedan dos AMARILLOS.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Aceptación del Paso 6 | `uv run pytest …test_realm_diff.py -q -rs && HYPOTHESIS_PROFILE=ci uv run pytest …test_realm_normalize.py -q` | pasa: 204 passed y 5 passed (33,5 s; la más lenta tarda 17,7 s, no se saltaron) |
| 2 | Reglas de la proyección | `uv run pytest identity-edge/tests/unit/test_realm_diff.py -q -rs` | pasa: 204 passed, 0 omitidas |
| 3 | Jobs contra Keycloak y Pushgateway falsos | `uv run pytest identity-edge/tests/unit/test_identity_jobs.py -q -rs` | pasa: 137 passed |
| 4 | Render y políticas | `make -C identity-edge render-jobs policy-jobs && uv run pytest …-k render` | pasa: conftest 555/555 y 5/5 ×3; pytest 98 passed. El nuevo render de los dos archivos sale idéntico a `rendered/` |
| 5 | `keycloak-reader` con tres roles | `uv run python …realm_lint.py …realm.*.yaml && uv run pytest …test_realm_lint.py …test_realm_files.py -q` | pasa: 629 passed |
| 6 | Dockerfile y políticas de U1 | `platform/.tools/bin/hadolint … && make -C identity-edge policy-jobs-u1` | pasa: Kyverno `pass: 16, fail: 0` ×3; conftest 35/35 y 3/3 ×3 |
| 7 | Regresión | `uv sync --frozen --offline && make -C identity-edge check && make -C platform check-tools` | pasa: rc=0, 1509 passed, `check-tools` `pass: 239, fail: 0` |
| 8 | Escaneo de U1 (T1) | `trivy fs --scanners misconfig --severity CRITICAL,HIGH --exit-code 1 --skip-check-update --ignorefile vectra-risk/.trivyignore --skip-dirs …fixtures,…rego/tests,vectra-risk/node_modules --skip-files <leído del propio supply-chain.yml> vectra-risk` (Trivy 0.76.1) | pasa: rc=0. Los tres `identity-jobs.yaml` aparecen escaneados, con 0 hallazgos |

En CA-7 agregué `--offline` porque no hay red. En CA-8 el valor de `--skip-files` lo saqué con un script del propio workflow, no lo copié a mano.

**El rojo de CA-8 lo reproduje yo.** Con el `skip-files` anterior (solo el archivo de ESO), Trivy termina en rc=1 con KSV-0109 (HIGH) en los tres `realm-configmap.yaml`, por las claves `client_credentials.use_refresh_token` y `revokeRefreshToken`.

## Lo que pediste comprobar
- **La excepción alcanza solo los tres archivos.** `git diff b9577ff..f75be5b -- .github` toca solo `supply-chain.yml`: 3 líneas de comentario y `skip-files`, que añade exactamente los tres `rendered/<env>/realm-configmap.yaml`, sin comodines. Nada más del workflow cambió: ni scanners, ni severidad, ni `skip-dirs`, ni `trivyignores`. `test_t1_supply_chain_skips_exactly_the_three_realm_configmaps` también lo fija.
- **Los CronJobs se siguen escaneando.** M1: añadí un CronJob inseguro (`hostNetwork`, `privileged`, root, `:latest`) a `rendered/prod/identity-jobs.yaml`. Trivy termina en rc=1 con KSV-0009, 0014, 0017 y 0118 sobre ese archivo.
- **No se puede colar un documento en el archivo omitido.**
  - M2: el mismo CronJob inseguro añadido a `rendered/prod/realm-configmap.yaml`. Trivy da 0, como era de esperar porque ya no mira ese archivo. Pero lo paran cuatro capas: `policy-jobs` (rc=2: `cronjob-shape`, `hardening`, `env`, `concurrency`), `check-jobs-rendered` (rc=2), `policy-jobs-u1` (Kyverno `fail: 7`) y pytest (5 fallos: conjunto exacto, documento completo, render versionado, políticas y `test_t1_…_own_file`).
  - M3: moví el CronJob legítimo `signing-key-age` a la plantilla `realm-configmap.yaml` y volví a renderizar, de forma coherente. Lo para solo `test_t1_the_realm_configmap_has_its_own_file` (3 fallos). `check-jobs-rendered`, `policy-jobs` y `policy-jobs-u1` pasan. Ver F-15.
- **El escáner de secretos no pierde cobertura.** `skip-files` también lo saca de `secret`, pero el contenido del ConfigMap es idéntico a `keycloak/realm/realm.<env>.yaml` (lo exige CA-4), y esos archivos se siguen escaneando. Lo comprobé plantando una llave de AWS en `realm.prod.yaml`: Trivy secret termina en rc=1 y la detecta como CRITICAL en `realm.prod.yaml:1221`.

## Hallazgos
### F-14 · AMARILLO · bitacoras/U02-T08.md:190,193 · El rojo de la bitácora no tiene salida (otra vez la clase de F-06)
La sección «Rojo primero» trae literalmente `$(grep -E "KSV-0109" …/u02t08/r4-red-trivy.txt | head -3)` y `$(tail -1 …)` sin expandir. Además, el archivo `r4-red-trivy.txt` no existe en esa carpeta (solo están `r4-red-pytest.txt` y `r4-green-trivy.txt`). La afirmación de que CA-8 estaba en rojo queda sin evidencia del codificador. No bloquea porque reproduje el rojo yo mismo.

### F-15 · AMARILLO · identity-edge/jobs/policy/set.rego · La regla «cada archivo con lo suyo» solo vive en pytest
M3 muestra que mover un CronJob al archivo omitido solo lo detecta `test_t1_…_own_file`. No hay regla de conftest, y esa prueba tampoco entra en el `-k render` de CA-4, aunque sí en CA-3 y en `make check`. El riesgo es bajo: el documento movido sigue pasando por las reglas de endurecimiento de conftest y Kyverno, y `make check` lo detiene. Una regla en `set.rego` (con `--combine` se ve la ruta de cada archivo) lo dejaría junto al resto de las reglas del render y con su caso que falla.

## Observación (no es de esta ronda)
El escáner helm de Trivy omite `identity-edge/jobs/chart` («realm es obligatorio») porque el chart no renderiza sin `--set-file`. Ya pasaba antes, cuando el `required` estaba en `identity-jobs.yaml`. Lo compensa que Trivy escanea los `rendered/`.

## Tareas candidatas
- Ninguna nueva. F-12 y F-13 siguen en `CANDIDATAS.md`, y siguen en pie las de la ronda 3 (JWKS con literal vacío, `##` en `post.logout.redirect.uris`, host distinto por elemento).

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/logs4/ (ca1, ca3–ca7, ca8-verde, ca8-rojo, m1, m2*, m3*, secret.txt)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/tasks/bha1uyzbz.output (salida completa de M1 y M2)

```
VEREDICTO: VERDE
AMARILLO|vectra-risk/bitacoras/U02-T08.md:190|El rojo de la bitácora no tiene salida
AMARILLO|identity-edge/jobs/policy/set.rego|La regla «cada archivo con lo suyo» solo vive en pytest
INFORME: revisiones/U02-T08/ronda-4.md
```

VEREDICTO: VERDE
