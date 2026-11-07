# Ronda 5 — U02-T18 (revisión de las rondas 4 y 5 del codificador, diff `524c385..49db24b`)

VEREDICTO: NO-VERDE

Tarea con hash `35ab076e55bd2ce9012a8e155fa7e168e06e1493`, que coincide. Worktree en `49db24b`, limpio antes y después de la revisión (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 7 | El perfil cabe y los renders de staging y prod no cambian | `uv run pytest platform/tests/test_kind_profile.py -q -rs && git diff 0cf1238 -- <6 rutas> --stat` | pasa: 10 passed en 162 s, 0 omitidas; el diff sale vacío |
| 5 | U2 en verde | `uv sync --frozen && make -C identity-edge check` | pasa: exit 0, 2649 passed en 34 min 47 s, kubeconform con `Skipped: 0` |
| 6 | U1 en verde, en serie después de CA-5 | `make -C platform check-local` | pasa: exit 0, 755 passed en 3 min 4 s, sin skips |

Lo que verifiqué aparte:
- **El total de 7,0547 GiB.** Lo recalculé con un script propio en fracciones exactas, a partir del inventario del render de kind, sin usar las funciones de la prueba. Da 7,0546875 GiB (U2 2,5195, U1 3,9492, kserve 0,5859), y `requested_gib()` devuelve lo mismo. El margen es de 0,9453 GiB.
- **KServe.** Rendericé `kserve-resources` v0.21.0 con `helm template`. Crea un solo Deployment, `kserve-controller-manager`, sin `replicas`, con 300 Mi + 300 Mi, como dice la bitácora. En `gateway-helm` solo hay además el Job hook `certgen`, sin requests.
- **Cada regla tiene un caso que falla sin ella.** Hice 10 mutaciones propias, una por regla: HPA, rama `EnvoyProxy`, `envoyHpa`, `shutdown-manager`, proxy de malla del data plane, controlador, ratelimit, suma de kserve, réplicas de kserve y `kube-rbac-proxy`. Las 10 dejan un caso en FAILED, y sin mutación pasan 5 de 5.
- **CI.** No queda en rojo. `check-local` depende del target `charts` (`platform/charts.sh` también baja los OCI), y `policies.yml` corre `make -C platform check`. `tests.yml` y `evidence.yml` corren `make -C platform charts render` antes de pytest.
- **M5 y M4.** `BUDGET_GIB = 8.0` cita M5 y la máquina de 14 GiB. M4 sigue igual: el diff no toca values, `keycloak.rego` ni renders.

## Hallazgos
### F-01 · NARANJA · `platform/tests/test_kind_profile.py` (`envoy_gateway_gib`, `kserve_gib`, `requested_gib`) · la cuenta no lee capas de values que sí cambian lo que se despliega
Es la misma clase de defecto que C-02 (cuenta de menos sin que nadie lo vea). Encontré tres casos:
1. **El overlay de kind no se lee.** La sección «Dentro» pide sacar el controlador y `envoy-ratelimit` de `envoy-gateway.yaml` **y del overlay de kind**. Pero `requested_gib()` solo lee `platform/operators/envoy-gateway.yaml`. Mutación en una copia: `envoy-gateway-kind.yaml` con `deployment.replicas: 3` y `rateLimitDeployment.replicas: 3`. `helm template` ya renderiza `replicas: 3`, y la cuenta sigue en 984,0 MiB.
2. **No se aplica el `rateLimitHpa.minReplicas` de ratelimit.** La regla «un workload con HPA cuenta `max(replicas, minReplicas)`» se aplicó a `envoyHpa` y no a ratelimit. Con `minReplicas: 3` la cuenta sigue en 984,0 MiB. Hoy coincide solo porque los dos valores valen 2.
3. **`kserve_gib` lee solo los valores por defecto del chart e ignora `platform/operators/kserve.yaml`.** Con `kserve.controller.resources.requests.memory: 1Gi` en ese archivo, `helm template` da 1Gi y la cuenta sigue en 984,0 MiB.

La cifra de hoy es correcta, pero un cambio en esas capas cuenta de menos sin que nada falle. Para cada capa falta su caso, con su rojo.
Evidencia: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r5-rev/U02-T18-r5-rev-latent.log`

### F-02 · NARANJA · `identity-edge/runbooks/keycloak-down.md:18` · «es el primer candidato a desalojo» es falso en este kind
El kubelet elige a quién desalojar en este orden: primero los pods cuyo uso supera su request, después la prioridad del pod, y al final el exceso de uso sobre la request. En el render de kind hay **15 pods sin request de memoria y sin `priorityClassName`**, con prioridad 0 y ninguna clase `globalDefault`: cert-manager (3), trust-manager, cloudnative-pg, external-secrets (2), argo-cd (7) y vault. Keycloak lleva `vectra-high`, que vale 100000, así que esos 15 caen antes que él.

Lo demás del texto está bien: 512 Mi de request y 2 Gi de limit en kind, 1 Gi en staging y prod.

La frase la exige la propia tarea («dice que en kind Keycloak es el primer candidato a desalojo»). El defecto está en la especificación, no en el codificador, así que para corregirlo el orquestador tiene que enmendar el texto de la tarea. Una redacción posible: «en kind usa más que su request y entra en el grupo desalojable ante presión de memoria; por `vectra-high`, antes caen los pods de U1 sin request».
Evidencia: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r5-rev/U02-T18-r5-rev-eviction.log`

### F-03 · AMARILLO · `test_kind_profile.py`, `test_the_real_count_includes_what_the_old_count_left_out` · la aserción es débil
Solo comprueba un `>`, sin cifra. Queda en verde aunque falte cualquier componente, siempre que falte otro. Las pruebas sintéticas compensan.

## Tareas candidatas (defectos reales fuera de alcance; cambian el margen que M5 anuncia)
- **Sidecars nativos que no se cuentan.** `pod_memory` no suma los `initContainers` con `restartPolicy: Always`: el `linkerd-proxy` de `linkerd-destination` y de `linkerd-proxy-injector` (2 × 20 Mi). Tampoco cuenta el `config-reloader` que el operador de Prometheus inyecta en Prometheus y en Alertmanager (2 × 32 Mi, `kube-prometheus-stack.yaml:61`). Son ≈ 0,10 GiB que no aparecen: el total real ronda los 7,16 GiB, y el margen para U3–U12 es ≈ 0,84 GiB, no los 0,95 que dicen `CANDIDATAS.md` y M5.
- **Jobs y CronJobs fuera de la cuenta, incluidos los de U2.** `realm-drift` (256 Mi, cada hora), `signing-key-age` (256 Mi, a las 03:00), `grafana-folder-check` (64 Mi, cada 30 min) y `restore-drill` (256 Mi, domingos a las 02:00). A las 03:00 coinciden ≈ 0,6 GiB transitorios, más proxies. Con eso el margen real a esa hora es de ≈ 0,2 GiB.
- **Los 15 pods BestEffort de U1 cuentan 0.** El tope mide reservas, no uso, así que «cabe en 8 GiB» no dice nada del consumo real en la máquina de 14 GiB.
- **El DaemonSet se cuenta fijo × 2.** `cluster-ha.yaml` tiene 4 workers.
- **Estado de lo que pidió el orquestador.** Fuera de lo anterior, no encontré más pods sin contar. MinIO es un StatefulSet de chart, sin operador. Los `Cluster` de CloudNativePG ya se cuentan. kserve y envoy-gateway no crean más pods que los contados. No hay otros charts OCI en kind fuera de `envoy-gateway`, `kserve-crd` (solo CRDs) y `kserve`. En los namespaces `vectra-*` no hay contenedores sin request a los que el LimitRange aplique su `defaultRequest` de 128 Mi.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T18-r5-rev/`. Las copias se borraron y quedaron los logs y `scripts/`.
- `U02-T18-r5-rev-ca7.log`, `U02-T18-r5-rev-ca5.log`, `U02-T18-r5-rev-ca6.log`
- `U02-T18-r5-rev-mutations.log`, `U02-T18-r5-rev-latent.log`
- `U02-T18-r5-rev-recount.log`, `U02-T18-r5-rev-inventory.log`
- `U02-T18-r5-rev-limitranges.log`, `U02-T18-r5-rev-eviction.log`

```
VEREDICTO: NO-VERDE
NARANJA|platform/tests/test_kind_profile.py (envoy_gateway_gib, kserve_gib)|la cuenta ignora el overlay de kind de envoy-gateway, el rateLimitHpa y platform/operators/kserve.yaml
NARANJA|identity-edge/runbooks/keycloak-down.md:18|"primer candidato a desalojo" es falso: 15 pods de U1 sin request ni prioridad caen antes (defecto de la especificación)
AMARILLO|platform/tests/test_kind_profile.py (test_the_real_count_includes_what_the_old_count_left_out)|aserción solo con ">"
INFORME: revisiones/U02-T18/ronda-5.md
```
