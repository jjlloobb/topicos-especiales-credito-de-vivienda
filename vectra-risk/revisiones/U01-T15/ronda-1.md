# Ronda 1 — U01-T15

VEREDICTO: NO-VERDE

Todos los criterios pasan con mis propias corridas y no hay ningún ROJO. Aun así el veredicto es NO-VERDE por un NARANJA: la exención deja el mínimo de 2 réplicas del **explicador** activo sin ninguna regla de admisión que lo vigile (F-01). Según la regla RL de este bucle, solo un ROJO bloquea; el orquestador decide si F-01 se arregla en esta ronda o pasa a candidata.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Los fixtures nuevos pasan; con la política de la base fallan | `make -C platform check-tools`, rc 0 (1 m 44 s). Rojo: `kyverno test` sobre una copia de `policies/kyverno` con `require-spread-and-pdb.yaml` de `6cf06e1` | pasa: `88 tests passed and 0 tests failed`, `require-min-replicas` da `Pass / Excluded` en los 2 fixtures. Rojo reproducido: `Want skip, got fail` en `kserve-prod-no-replicas` y `kserve-prod-one-replica`, `86 passed / 2 failed` |
| 2 | Un `prod` con `minReplicas: 1` se rechaza | lo mismo, más `make -C model-serving policy-chart policy-chart-u1`, rc 0 | pasa: `minimum_of_two_is_still_watched` imprime `active-inference-service-needs-two-replicas Fail`. Mutación mía i1 (predictor a 1): `Fail` |
| 3 | pytest de `platform` como la CI | `.tools` (enlace) movido fuera del árbol; `which kyverno conftest promtool`: nada. Corrí `uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q -rs` | pasa: `972 passed in 261.39s`, ninguna omitida. Enlace devuelto igual que estaba |
| 4 | `platform` y `model-serving` en verde | `make -C platform check && make -C model-serving check`, una sola vez | pasa: rc 0 y rc 0 (972 passed, 88 en kyverno test, 707 en conftest) |
| 5 | El barrido está en la bitácora | `grep -n -c 'storage-initializer' bitacoras/U01-T15.md`; `uv run python platform/tests/test_links.py` | pasa: 8; `647 archivos Markdown sin enlaces rotos`, rc 0 |

- **Trazabilidad:** `test_traceability.py --all` en la cabeza da rc 0, así que no hay fallos nuevos.
- **Alcance:** `CANDIDATAS.md` solo recibe líneas al final (0 líneas borradas). El diff no toca ni el chart de U6 ni los archivos de U01-T16 o U12-T09. No hay desborde de alcance.

**Premisa (punto 1 de lo encargado), confirmada por HTTPS** con `raw.githubusercontent.com/kserve/kserve/v0.21.0/...`:
- `deployment_reconciler.go:173-175` solo fija `Spec.Replicas = MinReplicas` cuando `AutoscalerClass == none`.
- Líneas 255-262: con HPA, la comparación ignora `Replicas`.
- Líneas 504-508: en `CheckResultUpdate` deja `Replicas = nil` en el actual y en el deseado antes del parche.
- `predictor.go` `buildObjectMeta`: las etiquetas son la unión de isvc, predictor, `serving.kserve.io/inferenceservice` y `component`.
- `components.yaml` fija `kserve-resources v0.21.0` y `kserve.yaml` usa `deploymentMode: RawDeployment`, así que es el reconciliador que corresponde.

**Estrechez de la exención (punto 2): mutaciones mías** con la regla `require-min-replicas` aislada y `kyverno apply`:
- Deployment de `vectra-serving` sin la etiqueta, con 1 réplica: `Fail`.
- El mismo sin `replicas`: `Fail`.
- Con la etiqueta de KServe y 1 réplica en `vectra-app`, `vectra-edge`, `vectra-identity` y `vectra-mock`: `Fail` en los cuatro.
- Sin la etiqueta en `vectra-serving` con 2 réplicas: `Pass`.
- Un Deployment hecho a mano en `vectra-serving` con la etiqueta y 1 réplica: excluido (ver F-02).

## Hallazgos

### F-01 · NARANJA · `require-spread-and-pdb.yaml:23-38`, `README.md:7`, `require-hpa-bounds.yaml` (`active-inference-service-needs-two-replicas`) · El mínimo de 2 del explicador activo se pierde en la admisión
- **Qué pasa:** la exención alcanza todos los Deployment de KServe en `vectra-serving`, también `isvc-*-explainer`. La regla que según el comentario y el README «vigila el mínimo» solo mira `spec.predictor.minReplicas`.
- **Mutación:** sobre el `prod` que rinde el chart (pico de D2), con las reglas de `InferenceService` de `require-hpa-bounds` aisladas:
  - i1 (`predictor.minReplicas: 1`): **Fail**
  - i2 (`explainer.minReplicas: 1`): **Pass**
  - i3 (sin cambios): Pass
- **Consecuencia:** en el clúster, un `InferenceService` activo con el explicador a 1 réplica se admite, y su Deployment queda exento. Solo lo atrapa el rego `active-min-replicas` de `model-serving/policies/conftest/inferenceservice.rego:85-90` en el PR, no la admisión.
- **Por qué no es ROJO:** CA-2 solo pide el caso del predictor. Pero el punto 3 del alcance dice «el mínimo de 2 réplicas del modelo activo no se pierde», y el README y el comentario de la política lo afirman sin matiz.
- **Arreglo sugerido:** extender `active-inference-service-needs-two-replicas` con `=(explainer): {minReplicas: ">=2"}`, más su fixture y su caso `fail`. O bien documentar la pérdida y llevarla a candidata.

### F-02 · AMARILLO · `require-spread-and-pdb.yaml:35-37` · La exención se apoya en una etiqueta que cualquiera puede poner
Un Deployment cualquiera en `vectra-serving` con `serving.kserve.io/inferenceservice` puesta a mano queda exento (mutación m7: excluido, no aparece en la tabla). Es el mismo patrón que se aceptó para Envoy. Para estrecharla se podría combinar con `subjects` (la cuenta de servicio del controlador de KServe) o con una precondición sobre `ownerReferences[?kind=='InferenceService']`.

### F-03 · AMARILLO · `platform/tests/kind_serving_kyverno.py` (`sweep_policies`) · Un `apiCall` sustituido por 1 puede esconder un rechazo de `require-pdb`
Fuera del clúster, `kyverno apply` no puede resolver el `apiCall`, así que el valor fijo esconde por construcción cualquier rechazo de `require-pdb`, que está en `Enforce`. En las rutas que comprobé, el riesgo está cubierto:
- `sweep()` exige que el chart rinda un PDB con el mismo `namespace` y `app.kubernetes.io/name`.
- Argo CD aplica el PDB (tipo conocido) antes que el `InferenceService` (CRD), y por tanto antes de que KServe cree el Deployment.
- El rollback pasa por GitOps: `governance/promotion_tool`, `values.py`.

`deployment-needs-hpa-or-exemption` solo está en `Audit`, así que ahí no hay riesgo. Lo que falta: escribir esa suposición de orden en el docstring, y una aserción negativa (con `pdbs: 0`, `require-pdb` falla) que demuestre que la regla sigue evaluándose.

### F-04 · AMARILLO · `kind_serving_kyverno.py` (`kserve_deployment`) y fixtures · El modelo difiere un poco de lo que KServe crea de verdad
- En `createRawDefaultDeployment` (`deployment_reconciler.go`, ≈ línea 148), `podMetadata := componentMeta` copia la struct pero comparte el mapa `Labels`. Por eso `app: isvc.<name>` acaba también en `metadata.labels` del Deployment, no solo en la plantilla, y ni el modelo ni los fixtures lo tienen.
- No cambia ninguna regla actual, pero sí lo que compara `fixtures_drift`. Encaja con la segunda candidata nueva: comparar con el clúster en el primer despliegue.
- Aparte, `STORAGE_INITIALIZER.image` incrusta `v0.21.0` en vez de leerlo de `components.yaml`, así que puede desfasarse en silencio si se sube KServe.

## Tareas candidatas (defectos reales fuera de alcance)
- F-02 y F-03, si el orquestador no los quiere en esta tarea.
- Las dos candidatas que añadió el codificador me parecen correctas. No reproduje su control de `initContainers` con `docker.io/evil/init:latest`, pero la lectura de las reglas (`spec.containers` y nada más) lo respalda.

## Limpieza y estado
- **Worktree:** `git status --short` vacío; HEAD `646038cbb5fab51589d2d6671018aee2a9daf480`; `vectra-risk/platform/.tools` vuelve a ser el mismo enlace.
- **Scratchpad:** `rev-u01t15-*` borrado.
- **Efecto lateral que ya existía, no es de esta tarea:** `make check` y `policy-chart-u1` escriben en `platform/.tools/integration`, que por el enlace es el `.tools` compartido del repositorio principal. Pueden pisarse con otros agentes que corren en paralelo.
- **Clúster:** no corrí nada contra él.

VEREDICTO: NO-VERDE
NARANJA|platform/policies/kyverno/require-spread-and-pdb.yaml:35 y require-hpa-bounds.yaml (active-inference-service-needs-two-replicas)|El mínimo de 2 del explicador activo queda sin vigilar en la admisión
INFORME: revisiones/U01-T15/ronda-1.md
