VEREDICTO: NO-VERDE

# Ronda 1 — U01-T12

Lo marcado «ejecutado» se corrió en una copia privada de `3083aec`; lo marcado «leído» no se ejecutó. Nada contra `kind-vectra`. `check-local` corrió una sola vez. El worktree del codificador quedó limpio.

No hay ningún ROJO. Hay un NARANJA, y por eso el veredicto es NO-VERDE. **Arbitraje del orquestador (2026-11-14):** por RL-2 la tarea sigue a fusión; F-01 a F-04 se atienden en U01-T13, que nace de esta rama y toca el mismo archivo de pruebas.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| CA-1 | Sidecars nativos y Job de validación contados; topes medidos | `pytest platform/tests/test_kind_profile.py ... -k "budget or cpu"` | pasa: `9 passed in 60.19s`. Rojo: con `effective_request` vuelto a la suma de `containers`, `native_sidecars` falla con `0.1 == 0.12` |
| CA-2 | Serving no escala más allá de lo contado | `pytest ... -k serving`; `pytest model-serving/tests -k "chart or values or schema"`; `make -C model-serving policy-chart-u1`; `kyverno apply require-hpa-bounds` sobre los 3 InferenceService del pico | pasa: 4 passed; 74 passed; rc 0, render con `maxReplicas: 2` en predictor y explicador. Kyverno `pass: 2, fail: 0`; con el predictor mutado a `minReplicas: 1`, `pass: 1, fail: 1` |
| CA-3 | El simulacro de failover, tal como está escrito, da 3 instancias | `pytest platform/tests -k failover`; y los bloques de `install.md` ejecutados a mano | pasa: `3 passed`. Con el `install.md` de main, falla |
| CA-4 | Las referencias colgantes cubren reglas, monitores y dashboards | `pytest platform/tests -k "dangling or colgante or references"` y 4 mutaciones | pasa: `2 passed`. Regla, monitor y panel de `slo.json` hacen fallar la prueba. **La de `product.json` no: F-01** |
| CA-5 | Staging y prod no cambian; todo en verde | `make -C platform check-local` (una vez) y el `git diff --stat` del criterio | pasa: `948 passed in 334.00s`, rc 0. Kind 55 Applications, prod 54, staging 56; 612 Markdown sin enlaces rotos. Diff vacío |

## La cuenta (ejecutado, con un script propio)
- **Keycloak en 2:** memoria **15,0547 GiB**, CPU **11,465** (render sin serving 11,4727 / 8,915; serving 2,4258 / 1,08; Job 1,0195 / 0,52; `kube-system` 0,1367 / 0,95). Coincide con el codificador.
- **Keycloak en 1** (rama fusionada): **14,0352 / 10,945**. Coincide.
- **Diferencia con los ≈ 15,15 de la revisión de U01-T11:** allí se sumaron ≈ 0,24 de `kube-system`, incluidos ≈ 100 MiB de etcd, que es un pod estático del plano de control; el codificador lo deja fuera y lo declara.
- **Sigue sin contarse (memoria, según el render):** CronJobs 1,30 GiB (bias 0,14; `registry-aggregator`, `realm-drift`, `signing-key-age` y `restore-drill`, 0,27 cada uno; `grafana-folder-check` 0,08); Jobs de instalación y migración 1,37 GiB (3 de kyverno 0,19; 3 migraciones 0,43; `minio-post-job` 0,39; `keycloak-config-cli` 0,27; `grafana-folder-permissions` 0,08); etcd ≈ 0,1 GiB; pods sin request de memoria (Argo CD (7), cert-manager y trust-manager (4), cnpg, ESO (2), `linkerd-cni`).
- **La máquina tiene 14,82 GiB, no 15** (`MemTotal` 15535356 kB): con Keycloak en 2 faltan ≈ 0,24 GiB, no 0,05; con Keycloak en 1 sobran ≈ 0,78. Ver F-03.

## Keycloak: fusión real con U02-T23 (ejecutado)
Fusionada `origin/tarea/U02-T23` (`c9ed403`) sobre `3083aec` en la copia: un conflicto, solo en `CANDIDATAS.md` (las dos ramas añaden al final). Con el árbol fusionado, `pytest platform/tests/test_kind_profile.py` entero da **`25 passed in 136.25s`**; `test_budget_counts_the_minimum_replicas_of_statefulset_hpas` pasa. Esta rama arregla la CI de #178.

## Serving con `minReplicas` = `maxReplicas` = 2
- **Ejecutado:** el render de kind lo trae en predictor y explicador del perfil prod; pasa `kubeconform -strict` con el CRD de v0.21.0, el rego de `platform/policies/rego` y `require-hpa-bounds`. Staging y prod no cambian.
- **Leído:** el CRD `kserve-crd` v0.21.0 no tiene `x-kubernetes-validations`; el repositorio ya rinde `min == max` en los perfiles `staging` e `inactive` (con `autoscalerClass: none`), así que el webhook acepta la igualdad.
- **Deducido, no comprobado:** con la clase `hpa`, KServe crea un HPA con 2/2. Confirmar con `kubectl get hpa -n vectra-serving` en el Paso 11.
- **Conftest de U6 (ejecutado):** sobre `kind/prod.yaml` da 4 fallos (2 de `active-scaling`, nuevos; 2 de `resources-by-profile`, previos), pero no se ejecuta sobre kind en ningún objetivo de `make` ni en la CI. No fallará; candidata.
- Las pruebas de U4, U6 y U12 que leen los values de kind dan `53 passed`.

## Simulacro de failover (ejecutado a mano)
`aplicar` da rc 0; `helm template` con los `valueFiles` resultantes da los cuatro clusters con 3 instancias y `nodeLabelsAntiAffinity` por zona. `deshacer` da rc 0 y deja el árbol limpio. Copiar el archivo sin regenerar da `generate.py --check` rc 1.

## Hallazgos

### F-01 · NARANJA · `platform/tests/test_kind_profile.py:719` · La prueba de referencias colgantes no ve el dashboard de producto, que kind sí instala
La prueba solo lee `platform/observability/dashboards/*.json`. El render de kind trae el ConfigMap `product-metrics-dashboard` (`vectra-app`, `product.json`), con la etiqueta del sidecar de Grafana. Mutación: en `product-metrics/observability/dashboards/product.json`, el primer `datasource` a `{"type": "loki", "uid": "loki"}` → `1 passed`. La misma mutación en `slo.json` da `1 failed`. Es el único dashboard del render de kind fuera de esa carpeta. Arreglo: leer los dashboards de los ConfigMap del render, no de una carpeta.

### F-02 · AMARILLO · `platform/runbooks/install.md:156-166` y `test_kind_profile.py:613-615` · El procedimiento usa `python3` y la prueba lo cambia por otro intérprete
El resto del repositorio invoca `generate.py` con `uv run python`. En una máquina sin PyYAML en el `python3` del sistema, el bloque falla. La prueba reemplaza `python3 ` por `sys.executable`: no ejecuta el texto tal cual.

### F-03 · AMARILLO · `test_kind_profile.py:56` e `install.md:33` · `MACHINE_GIB = 15.0` no se usa y no es la cifra real
Ninguna aserción la usa. La máquina tiene 14,82 GiB. `install.md` dice «máquina de 14 GiB» (línea 18) y «15 GiB de la máquina» (línea 33).

### F-04 · AMARILLO · `test_kind_profile.py:270-276` · `UNCOUNTED_CPU` omite CronJobs y dos Jobs
`INSTALL_JOBS_CPU` (0,55) no incluye los 6 CronJobs (0,55) ni los Jobs de kyverno y `grafana-folder-permissions` (0,08). Con ellos, 11,5 + 1,83 = 13,33 ≤ 16.

### F-05 · AMARILLO · fusión con #178 · Conflicto en `CANDIDATAS.md`
Las dos ramas añaden al final: se conservan las dos entradas.

## Tareas candidatas
- U6: `model-serving/docs/values.md:40-45` dice que kind solo baja la memoria; no menciona la CPU de 100m ni `maxReplicas` = 2.
- U6: la política conftest `active-scaling` y `resources-by-profile` frente a los values de kind.
- U1: comprobar en el Paso 11 que KServe crea el HPA con 2/2.

```
VEREDICTO: NO-VERDE
NARANJA|platform/tests/test_kind_profile.py:719|la prueba de referencias colgantes no ve product.json, que kind instala; una mutación con Loki pasa
AMARILLO|platform/runbooks/install.md:156-166|el procedimiento usa python3 (no uv run python) y la prueba cambia el intérprete
AMARILLO|platform/tests/test_kind_profile.py:56|MACHINE_GIB=15.0 no se usa; la máquina tiene 14,82 GiB (faltan ≈ 0,24, no 0,05)
AMARILLO|platform/tests/test_kind_profile.py:270-276|UNCOUNTED_CPU omite los CronJobs (0,55) y dos Jobs (0,08)
AMARILLO|vectra-risk/CANDIDATAS.md|conflicto de fusión con U02-T23 (#178), las dos ramas añaden al final
INFORME: revisiones/U01-T12/ronda-1.md
```
