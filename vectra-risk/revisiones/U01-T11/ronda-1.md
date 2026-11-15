VEREDICTO: NO-VERDE

# Ronda 1 — U01-T11

Lo marcado «ejecutado» se corrió en una copia privada de `ac9b43f`; lo marcado «leído» no se ejecutó. Nada contra `kind-vectra`. El worktree del codificador quedó limpio.

**Nota del orquestador:** el PR #177 se fusionó en `main` (ab734dd) antes de que esta revisión terminara. No hay ROJO. Los NARANJA se atienden en U01-T12 (F-01, F-02, F-03, F-05, F-06) y en U12-T07 (F-04).

**Incidente del revisor:** su `--deselect` de las pruebas de Grafana no seleccionó nada (la ruta no casa con `--rootdir=platform`), así que las 4 pruebas de Grafana levantaron un contenedor con testcontainers, que se borró solo. Una sola corrida; no tocó `kind-vectra`.

## Criterios de aceptación, verificados por el revisor

| # | Criterio | Comando | Resultado |
|---|---|---|---|
| CA-1 | Loki, Tempo y Alloy fuera de kind, sin referencias colgantes | `generate.py --check`, `test_waves.py`, `network/generate.py --check`; `ls apps/kind` | pasa: rc 0; kind 55, prod 54, staging 56 Applications; 0 archivos `loki`, `tempo` o `alloy` en `apps/kind`. Las 5 pruebas de referencias colgantes fallan con la configuración de 13f83ff. Mutación: sin el override del pipeline del colector falla con `('otlp_grpc/tempo', 'tempo-distributor...')` |
| CA-2 | Keycloak con 1 réplica | (pausado a propósito) | diagnóstico correcto, leído: `keycloak.rego:128-131` rechaza `minReplicas != 2` y `:155` fija el spec del HPA en 2; `policy-keycloak` evalúa los tres entornos; `test_keycloak_deploy.py:300` muta a 1 esperando fallo |
| CA-3 | La CPU cabe en lo programable | `pytest ... -k cpu` | pasa: 4 passed. Con 13f83ff falla: `19.57 <= 10.5`. La cuenta se queda corta: F-01 |
| CA-4 | El presupuesto de memoria baja a lo medido | `pytest ... -k budget` | pasa: 5 passed. Con 13f83ff falla: `14.9296875 <= 13.9` |
| CA-5 | Staging y prod no cambian | `make render` y `git diff --stat 13f83ff -- platform/rendered/{staging,prod} platform/network/generated/{staging,prod} vectra-risk-gitops/apps/{staging,prod}` | pasa: vacío. El arreglo de `k_egress` no cambia nada generado en staging ni prod |
| CA-6 | `install.md` y enlaces | `test_runbooks.py --operational`, `test_links.py` | pasa: rc 0 (602 archivos) |
| CA-7 | Todo en verde | los pasos de `check-local`, una vez | pasa: `942 passed in 265.89s`, rc 0 |
| F-01 (U01-T10) | `-k minio` ejecuta la prueba de `validation-readonly` | `--collect-only -k minio`; mutación (sin `model-store`, con `s3:PutObject`) | pasa: 6/25 seleccionadas. Mutada: `2 failed, 4 passed`. Restaurada: `6 passed` |
| F-02/F-05 | El override del simulacro da 3 instancias en los cuatro clusters | `helm template` con y sin `platform/kind/postgres-failover.yaml` | pasa en el render (3/1/2 y 4 `nodeLabelsAntiAffinity`; sin el override, 2/1/1/1). El procedimiento escrito no funciona: F-02 |
| F-03 (U01-T10) | El presupuesto cuenta Envoy, Envoy Gateway, ratelimit y KServe | `runtime_documents()` y su prueba | pasa |
| F-07 (U01-T10) | Pasos del runbook no medidos, marcados | leído | pasa |
| Fuera | Sin cambios en `identity-edge`, Argo CD ni réplicas de U3 a U11 | `git diff --stat 13f83ff..ac9b43f` | pasa |

## Hallazgos

### F-01 · NARANJA · `platform/tests/test_kind_profile.py:74,80` · Las cuentas no ven los sidecars nativos: la CPU real del pico de D2 supera `CPU_BUDGET`
`pod_cpu` y `pod_memory` solo suman `containers`. En el render de kind, `linkerd-destination` y `linkerd-proxy-injector` llevan su `linkerd-proxy` como `initContainer` con `restartPolicy: Always` (20m y 20Mi cada uno), y el namespace `linkerd` no está en `MESHED`. Recalculado con sidecars nativos y la regla max(init, main): CPU **10,515 > 10,5** (la prueba dice 10,475); memoria 13,8984 GiB (la prueba dice 13,8594), a 1,6 MiB del tope de 13,9. Los dos topes pasan solo porque la cuenta omite esos dos proxies.

### F-02 · NARANJA · `platform/kind/postgres-failover.yaml:3`, `platform/data/chart/values-kind.yaml:6`, `platform/runbooks/install.md:18` · El simulacro de failover sigue con un procedimiento que no funciona
El archivo dice que se copia a `vectra-risk-gitops/values/kind/postgres.yaml` y que «Argo CD lo agrega solo». Es falso: `apps/kind/postgres.yaml` tiene la lista `valueFiles` fija y `generate.py` (`value_files`, línea 90) solo la añade al regenerar. Copiando el archivo: `grep -c values/kind/postgres apps/kind/postgres.yaml` da `0` y `generate.py --check` da rc 1. Faltan regenerar, llevar el cambio a `main` (Argo CD lee `targetRevision: main`) y deshacerlo al terminar. La prueba nueva renderiza con `helm` directamente y no lo detecta.

### F-03 · NARANJA · `vectra-risk-gitops/values/kind/model-serving.yaml:8-17` · Con 100m de request, el HPA de serving escala a `maxReplicas` con muy poca carga, y eso no está contado
Cada pod del perfil prod pide 100m más 20m del proxy. Con el objetivo del 60 %, el umbral es un consumo medio de ≈ 72m por pod (antes ≈ 360m): baja unas 5 veces. Un explicador SHAP con carga en D2 lo pasa casi con cualquier tráfico. Con los dos InferenceService prod del pico (predictor de 2 a 4, explicador de 2 a 6) son 12 pods más: **+3,23 GiB y +1,44 CPU** de requests. El esquema limita `cpuUtilization` a 100 (`values.schema.json:44`), que dejaría el umbral en ≈ 120m. Falta la cifra y una decisión: mitigar, o declararlo y contarlo.

### F-04 · NARANJA · `bitacoras/U01-T11.md:10` · La comprobación previa sobre U12 está incompleta
En `origin/main`, `system-verification/docs/paso-18-kind.md:355,371` (K-20) y `docs/kind/inventario.yaml:184-186` piden `kubectl get pods -l app.kubernetes.io/name=loki -n vectra-observability`, que ya no encuentra ningún pod. La tabla de síntomas (línea 58) y los pasos 4 y 5 del reinicio (92-108) describen Tempo, Loki y «12 usuarios». Ningún código lee Loki (grep en `src`, `demos` y `docs/kind/*.sh`; `observabilidad.sh` solo usa Prometheus).

### F-05 · AMARILLO · `platform/mesh/linkerd-kind.yaml:5`, `model-serving.yaml:10`, `test_kind_profile.py:47-49` · Los «16 núcleos programables» inducen a error
Cada worker anuncia los 8 núcleos del host y los tres nodos comparten esos mismos 8 núcleos físicos. El tope de 16 solo evita pods en `Pending`. Lo pedido real (10,5 + ≈ 1,2 sin contar + ≈ 0,65 del control-plane) ronda 12,4 sobre 8 núcleos: los requests de CPU solo reparten pesos.

### F-06 · AMARILLO · `test_kind_profile.py:51-53` · `UNCOUNTED_CPU` nombra kindnet, que no se instala
La red es Calico (`disableDefaultCNI: true`). `calico-node` pide 250m por nodo (por conocimiento, no descargado): con CoreDNS (0,2), los Jobs (0,3) y el 20 % de margen salen ≈ 1,2, no 1,0.

### F-07 · AMARILLO · prueba de referencias colgantes · No cubre reglas, monitores ni el `uid` de fuente de datos de los dashboards
Hoy ninguno referencia Loki, Tempo ni Alloy (grep). Los comandos de CA-1, CA-3 y CA-4 no seleccionan estas pruebas: solo corren en `check-local`.

## Comprobado, sin hallazgo
- **Colector (render ejecutado):** los pipelines `traces`, `logs` y `metrics` usan el exportador `debug`; `otlp_grpc/tempo` queda definido sin usar. Las trazas y los logs ya no van a ninguna parte en kind; solo quedan en `kubectl logs`.
- **Grafana (render ejecutado):** solo quedan las fuentes Prometheus y Alertmanager.
- **Reglas de U1:** ninguna alerta mira `up` de Loki, Tempo ni Alloy.
- **Proxy a 20m:** clave soportada del chart; `linkerd-network-validator` usa `proxy.resources`; el límite sigue en 500m; no hay LimitRange ni política que limite la proporción.
- **Memoria en el pico de D2:** 13,90 contados + 1,02 del Job de validación + ≈ 0,24 de `kube-system` = **≈ 15,15 GiB de requests, por encima de 15**, sin contar config-cli (0,27), `minio-post-job` (0,375), el aggregator (0,25), lo que no declara request ni el sistema del host. Con el escalado de F-03, ≈ 18,4. Sin el recorte de Keycloak no queda holgura.

## Tareas candidatas
- U12: actualizar K-20 en `paso-18-kind.md` e `inventario.yaml`, la tabla de síntomas y los pasos 4 y 5 del reinicio.
- La prueba de presupuesto debe contar el escenario de `maxReplicas` de serving, o declarar un tope aparte.

```
VEREDICTO: NO-VERDE
NARANJA|platform/tests/test_kind_profile.py:74,80|las cuentas no ven los sidecars nativos; CPU real 10,515 > CPU_BUDGET 10,5
NARANJA|platform/kind/postgres-failover.yaml:3|«Argo CD lo agrega solo» es falso: hace falta regenerar y llevarlo a main
NARANJA|vectra-risk-gitops/values/kind/model-serving.yaml:8-17|HPA al 60 % de 120m: escala a max con +3,23 GiB sin contar
NARANJA|bitacoras/U01-T11.md:10|comprobación previa incompleta: K-20 de la guía de U12 en main pide pods de Loki
AMARILLO|platform/mesh/linkerd-kind.yaml:5|«16 núcleos programables» son 8 físicos compartidos por 3 nodos
AMARILLO|platform/tests/test_kind_profile.py:51-53|UNCOUNTED_CPU nombra kindnet (no instalado) y no calico-node
AMARILLO|platform/tests/test_kind_profile.py|referencias colgantes sin cubrir reglas, monitores ni uid de dashboards
INFORME: revisiones/U01-T11/ronda-1.md
```
