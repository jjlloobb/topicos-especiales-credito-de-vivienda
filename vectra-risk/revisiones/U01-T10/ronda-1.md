VEREDICTO: NO-VERDE

# Ronda 1 — U01-T10

Revisada la punta 13f83ff contra `origin/main` (3ac14a3, la base de fusión). Nada se ejecutó contra `kind-vectra`. Las mutaciones se hicieron en una copia (`git archive`). `check-local` corrió una sola vez. El worktree quedó limpio.

**Nota del orquestador:** el PR #176 se fusionó en `main` (baf38d1) antes de que esta revisión terminara. Los hallazgos se atienden en U01-T11, que nace de esta rama y toca los mismos archivos (ver `arbitraje-ronda-1.md`).

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | `registry-db` con 2 instancias y minSync 1; los otros clusters con 1; staging y prod sin cambios | `pytest platform/tests/test_kind_profile.py -v` (124 s, 8 pasan, 0 omitidas); render del chart `data` en kind, staging y prod, en la rama y en main, comparados con `diff` | pasa. Staging y prod: diff vacío. Kind: solo `registry-db` cambia, a `instances: 2`, `minSyncReplicas: 1`, `maxSyncReplicas: 1` |
| 2 | La política de `validation-readonly` lee `model-store` y `validation-datasets` y no escribe | el comando literal del criterio (`-k minio`) | **falla**: ese comando no ejecuta la prueba nueva (F-01) |
| 3 | metrics-server como Application de kind, por digest, dentro de Kyverno | `generate.py --check` rc 0; `test_waves.py` kind 58, prod 54, staging 56; `kyverno apply` de las 19 políticas al render en `vectra-observability` | pasa. Kyverno: 11 pass, 0 fail |
| 4 | La bóveda de kind declara requests y limits | `grep -A6 resources platform/operators/vault-kind.yaml` y `helm template` del chart | pasa: 100m/256Mi en requests y en limits |
| 5 | El presupuesto cuenta lo pedido | `pytest ... -k budget`, más un desglose propio | pasa tal como está escrito. Sigue contando de menos (F-03) |
| 6 | El runbook pasa sus comprobadores | `test_runbooks.py --operational` y `test_links.py` | pasa, rc 0 (4 runbooks, 598 archivos) |
| 7 | `check-local` en verde | `make -C platform check-local` | pasa, rc 0. 930 pasan, ninguna omitida, 4 min 34 s |

## Hallazgos

### F-01 · ROJO · CA-2, `platform/tests/test_upstream_charts.py:167` · El comando del criterio no ejecuta la prueba nueva y pasa aunque la política esté rota
- El criterio es `-k minio`, pero el nombre de la prueba (`test_validation_readonly_reads_model_store_...`) no contiene «minio»: el filtro la deja fuera. `--collect-only -k minio` recoge solo 4 pruebas, todas anteriores a la tarea.
- En la copia, quitando `model-store` y añadiendo `s3:PutObject` en `values.yaml` y `values-kind.yaml`, el comando del criterio da `4 passed, 21 deselected`, rc 0.
- El «4 passed, 21 deselected» que la bitácora presenta como verde de CA-2 no pudo ejecutar la prueba nueva.
- **La prueba en sí es buena:** con `-k validation_readonly` pasan 2 de 2; con las mismas mutaciones falla (quitar `model-store` da `AssertionError: ('s3:GetObject', 'arn:aws:s3:::model-store')` en base y en kind; añadir PutObject da «Extra items ... s3:PutObject»).
- **Arreglo:** que el nombre de la prueba contenga `minio`.

### F-02 · NARANJA · `platform/data/chart/values-kind.yaml:5-6`, `platform/runbooks/install.md:18` · El procedimiento del simulacro de failover (Paso 20) deja de funcionar
El `instances` de cada cluster gana ahora sobre el global, y `values-kind.yaml` lo fija en todos (2 en `registry-db`, 1 en los otros tres). El `instances: 3` / `zoneConstraint: true` global que documentan los dos archivos ya no surte efecto: en main ese override da los 4 clusters con 3 instancias y `maxSyncReplicas: 2`; en la rama, `registry-db` con 2 y los otros tres con 1. El texto y el mecanismo deben volver a coincidir.

### F-03 · NARANJA · `platform/tests/test_kind_profile.py:38` · `BUDGET_GIB = 13.4` se presenta como «cifra medida», pero quedan fuera cosas pedidas que se conocen
El desglose cuadra: pico de 13,3672 GiB = 10,9414 de workloads + 2,4258 de InferenceServices; la suma de la bitácora es correcta. No se cuenta, todo dentro de kind:

| Qué falta | Por qué no entra | Memoria pedida |
|---|---|---|
| Data plane de Envoy | `EnvoyProxy` lo crea en tiempo de ejecución; 2 réplicas; envoy 256 Mi + shutdown-manager 32 Mi (`identity-edge/gateway/generated/kind/envoyproxies.yaml:20-74`) | 576 Mi |
| Controlador de Envoy Gateway | chart OCI que `render_env` no renderiza; 2 réplicas de 128 Mi (`platform/operators/envoy-gateway.yaml:6-10`) | 256 Mi |
| ratelimit | 2 réplicas de 64 Mi (`envoy-gateway.yaml:43-48`) | 128 Mi |
| Controlador de KServe | chart OCI, no renderizado | sin cifra |

Son al menos 0,94 GiB más: el pico real ronda 14,3 GiB en una máquina de 15. Aparte, los Jobs y CronJobs no entran en la cuenta (minio-post-job 384 Mi, keycloak-config-cli 256 Mi, registry-aggregator 256 Mi, entre otros), ni `model-validation-job`, que se crea en tiempo de ejecución.

### F-04 · NARANJA · `platform/operators/metrics-server-kind.yaml:3` · La imagen hay que descargarla y nadie lo preguntó
`docker image ls` no tiene ninguna imagen de metrics-server, y `certs.d` de kind solo espeja `kind-registry:5000` y `registro.vectra.internal`: el nodo bajará `registry.k8s.io/metrics-server/metrics-server` de internet al sincronizar. El digest es correcto (`sha256:89258156…aee2`), bajar de origen es coherente con los demás operadores (cert-manager, kyverno, vault) y ninguna política de Kyverno cubre `kube-system`. Es un hallazgo porque la bitácora lo afirma («el clúster la bajará al sincronizar») en vez de plantearlo como pregunta: falta la autorización del usuario.

### F-05 · AMARILLO · `platform/runbooks/install.md:18` · Frase duplicada
«Para el simulacro de failover de zona (Paso 20) no sirve para el simulacro de failover de zona (Paso 20)». Se corrige con F-02.

### F-06 · AMARILLO · bitácora · No hubo rojo primero para la prueba de metrics-server

### F-07 · AMARILLO · `install.md`, «Vault reiniciado» paso 2 y «Tras reiniciar la máquina» · Detalles que las Notas no dicen
`kubectl delete pod --all`, «esperando a que vuelva a Running» y el paso de `docker ps` no salen de las Notas; son razonables, pero no están marcados como no medidos. El resto del runbook sigue el orden de CA-6, con PostgreSQL y Keycloak como no medidos y el Job de MinIO como procedimiento.

### F-08 · AMARILLO · Otros
El límite de CPU de 100m de la bóveda no está medido. El AppProject de kind admite ahora `kube-system` como destino. `instances: 0` en un cluster cae al valor global (`default` trata el 0 como vacío).

## Comprobado leyendo, sin clúster
- **Réplica síncrona:** con 2 instancias y min = max = 1, CNPG configura `ANY 1 (...)` y PostgreSQL informa `sync_state = 'quorum'`, que acepta `SYNC_STANDBYS` (`decision-registry/src/vectra_registry/health.py:31-33`).
- **Plantilla `min(2, instances-1)`:** renderizada con 1, 2, 3 y 4 instancias da: sin campos de sincronía, 1/1, 1/2 y 1/2. Cumplen `maxSyncReplicas` < `instances` (regla tomada del conocimiento de CNPG; el CRD solo trae `minimum: 0`).
- **Programación:** la anti-afinidad obligatoria por hostname cabe en los 2 workers (zone-a y zone-b); `zoneConstraint` es false en kind. `registry-db-ro` tendrá una réplica detrás si las dos programan.
- **metrics-server:** no hay NetworkPolicy en `kube-system` ni GlobalNetworkPolicy de Calico, y `kube-system` no tiene malla; el AppProject ya admitía `APIService`; la wave 1 está bien.
- **Job de validación:** `run.py:58-63` solo lee: la política basta.
- **Fuera de alcance:** sin cambios en `decision-registry/`, `governance/`, `reference-model/` ni `identity-edge/`; Applications de staging y prod idénticas a main.

## Tareas candidatas
- El presupuesto de kind debe contar los objetos creados en tiempo de ejecución (`EnvoyProxy`, ratelimit, los charts OCI) y los Jobs.
- Espejar metrics-server, y los operadores de origen en general, en `kind-registry`, para que la demo sea portable.

```
VEREDICTO: NO-VERDE
ROJO|CA-2, platform/tests/test_upstream_charts.py:167|El comando del CA (-k minio) no ejecuta la prueba nueva: pasa con la política rota
NARANJA|platform/data/chart/values-kind.yaml:5-6, install.md:18|El override global instances: 3 del simulacro de failover ya no surte efecto
NARANJA|platform/tests/test_kind_profile.py:38|El presupuesto no cuenta el data plane de Envoy, el controlador de Envoy Gateway ni ratelimit (≥0,94 GiB)
NARANJA|platform/operators/metrics-server-kind.yaml:3|La imagen hay que descargarla de registry.k8s.io y no se pidió autorización
INFORME: revisiones/U01-T10/ronda-1.md
```
