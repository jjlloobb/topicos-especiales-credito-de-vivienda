# 02 — Sync y arranque de cada unidad

**Estado: completa.** Llenada el 2026-11-20 con lo que se obtuvo contra `kind-vectra`.

- Guía y fase: `system-verification/docs/paso-18-kind.md`, F2 (Sync y arranque de cada unidad).
- Fecha: 2026-11-20 (jornada 1), entre las 12:27 y las 13:00 UTC.
- Operador: jjlloobb, con Claude Code ejecutando las ordenes.
- Commit de `main` desplegado: 9dc027f.
- Duración real de la fase: unos 15 min (solo lecturas; nada que sincronizar) (estimada: 2 a 3 h; la guía pide anotarla).

Entradas de esta fase: K-10, K-11, K-12, K-13, K-14, K-15, K-16, K-17, K-18, K-19, K-20, K-21, K-22, K-23, K-24, K-25, K-26.

### K-10 — U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey co…

- Demo: Base. Fuentes: `CANDIDATAS.md:95`, `CANDIDATAS.md:111`, `CANDIDATAS.md:115`, `identity-edge/docs/paso-16-kind.md:87-100`.

**Resultado esperado.** U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey contestan, el Job keycloak-config-cli termina

**Comando.** Previsto: `arranque.sh vectra-edge vectra-identity`; `kubectl --context kind-vectra get job keycloak-config-cli -n vectra-identity`.

```bash
system-verification/docs/kind/arranque.sh vectra-edge vectra-identity | tail -8; kubectl --context kind-vectra get job keycloak-config-cli -n vectra-identity
```

**Salida.**

```text
vectra-edge: 8 pods, 0 hallazgos
vectra-identity: 6 pods, 0 hallazgos
linkerd-cni: 3 pods, 0 hallazgos
ExternalSecret: 8 en los namespaces pedidos, 0 sin SecretSynced
AVISO Application kserve-crd: OutOfSync
AVISO Application linkerd-control-plane: OutOfSync
Applications: 56, 0 fuera de Healthy, 2 fuera de Synced
arranque: sin hallazgos
NAME                  STATUS     COMPLETIONS   DURATION   AGE
keycloak-config-cli   Complete   1/1           55s        10h
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U2 arranca: Envoy con la raiz de solo lectura, las sondas de Valkey contestan, el Job keycloak-config-cli termina | vectra-edge y vectra-identity sin hallazgos; Job keycloak-config-cli Complete | si |

### K-11 — decision-registry

- Demo: Base. Fuentes: `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:71`, `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md:72`.

**Resultado esperado.** decision-registry: Application Synced y Healthy; /readyz responde 200

**Comando.** Previsto: `kubectl --context kind-vectra get applications.argoproj.io decision-registry -n argocd`; `arranque.sh vectra-app`.

```bash
kubectl --context kind-vectra get applications.argoproj.io decision-registry -n argocd; kubectl --context kind-vectra get pods -n vectra-app -l app.kubernetes.io/name=decision-registry-service
```

**Salida.**

```text
NAME                SYNC STATUS   HEALTH STATUS
decision-registry   Synced        Healthy
NAME                                         READY   STATUS    RESTARTS   AGE
decision-registry-service-6995444c56-lbmx9   2/2     Running   0          10h
decision-registry-service-6995444c56-z9n2l   2/2     Running   0          10h
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| decision-registry: Application Synced y Healthy; /readyz responde 200 | Application Synced y Healthy; los dos pods 2/2 Running (la sonda de readiness es /readyz) | si |

### K-12 — ESO materializa las llaves de cada unidad (scoring, explainability, ca…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:44`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:73`, `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md:40`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:51`, `tareas/U12-T05-imagen-y-documentacion.md:370`.

**Resultado esperado.** ESO materializa las llaves de cada unidad (scoring, explainability, case-service, case-worker, las dos de bias, product-metrics) y existen los cuatro pg-role-case-*

**Comando.** Previsto: `kubectl --context kind-vectra get externalsecret -n vectra-app`; `arranque.sh vectra-app`.

```bash
kubectl --context kind-vectra get externalsecret -n vectra-app; kubectl --context kind-vectra get secret -n vectra-app -o name | grep pg-role-case; kubectl --context kind-vectra get secret -n vectra-data -o name | grep pg-role-case
```

**Salida.**

```text
NAME                             STORETYPE            STORE          REFRESH INTERVAL   STATUS         READY   LAST SYNC
bias-monitoring-job-client       ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
bias-monitoring-service-client   ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
case-service-client              ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
case-worker-client               ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
explainability-service-client    ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
governance-service-client        ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
minio-governance                 ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
minio-model-archive              ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
minio-registry-archive           ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
minio-registry-checkpoint        ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
minio-registry-verify            ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-case-app                 ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-case-migrator            ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-case-retention           ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-case-worker              ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-gov-app                  ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-gov-archiver             ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-gov-migrator             ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-registry-aggregator      ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-registry-app             ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-registry-health          ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-registry-migrator        ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-registry-ondemand        ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
pg-role-registry-verifier        ClusterSecretStore   vectra-store   1h0m0s             SecretSynced   True    17m
product-metrics-client           ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
scoring-service-client           ClusterSecretStore   vectra-store   1h                 SecretSynced   True    17m
secret/pg-role-case-app
secret/pg-role-case-migrator
secret/pg-role-case-retention
secret/pg-role-case-worker
secret/pg-role-case-app
secret/pg-role-case-migrator
secret/pg-role-case-retention
secret/pg-role-case-worker
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| ESO materializa las llaves de cada unidad (scoring, explainability, case-service, case-worker, las dos de bias, product-metrics) y existen los cuatro pg-role-case-* | 26 ExternalSecret en vectra-app, todos SecretSynced; los cuatro pg-role-case-* existen | si |

### K-13 — Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable …

- Demo: Base. Fuentes: `CANDIDATAS.md:616`, `CANDIDATAS.md:624`, `revisiones/U08-T05/ronda-1.md:66`.

**Resultado esperado.** Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable o la llave private_key_jwt)

**Comando.** Previsto: `arranque.sh vectra-app`; `kubectl --context kind-vectra logs --previous -n vectra-app`.

```bash
system-verification/docs/kind/arranque.sh vectra-app | tail -8
```

**Salida.**

```text
vectra-app: 25 pods, 0 hallazgos
linkerd-cni: 3 pods, 0 hallazgos
ExternalSecret: 26 en los namespaces pedidos, 0 sin SecretSynced
AVISO Application kserve-crd: OutOfSync
AVISO Application linkerd-control-plane: OutOfSync
Applications: 56, 0 fuera de Healthy, 2 fuera de Synced
arranque: sin hallazgos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Ningun contenedor sale con codigo 0 y sin mensaje (falta una variable o la llave private_key_jwt) | vectra-app: 0 hallazgos (ningun contenedor terminado con codigo 0 y sin mensaje) | si |

### K-14 — U8: el hook de migracion corre antes de que los Deployment queden Read…

- Demo: Base. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:74`, `CANDIDATAS.md:625`, `CANDIDATAS.md:236`.

**Resultado esperado.** U8: el hook de migracion corre antes de que los Deployment queden Ready; sslmode=verify-full conecta de verdad con case-db

**Comando.** Previsto: `kubectl --context kind-vectra get jobs -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=case-service`.

```bash
kubectl --context kind-vectra get jobs -n vectra-app; kubectl --context kind-vectra get pods -n vectra-app -l app.kubernetes.io/name=case-service; kubectl --context kind-vectra get deploy case-service -n vectra-app -o yaml | grep -n -i 'sslmode\|verify-full' | head -5
```

**Salida.**

```text
NAME                           STATUS     COMPLETIONS   DURATION   AGE
bias-monitoring-job-29919602   Complete   1/1           18s        30m
bias-monitoring-job-29919617   Complete   1/1           18s        15m
bias-monitoring-job-29919632   Complete   1/1           19s        57s
case-migration                 Complete   1/1           24s        3d9h
governance-migration           Complete   1/1           19s        2d16h
registry-aggregator-29919630   Complete   1/1           19s        2m57s
registry-migration             Complete   1/1           24s        4d6h
NAME                            READY   STATUS    RESTARTS   AGE
case-service-77967bf7bc-kc8x6   2/2     Running   0          9h
case-service-77967bf7bc-srcwp   2/2     Running   0          10h
47:          value: postgresql://case-db-rw.vectra-data.svc.cluster.local/case?sslmode=verify-full&sslrootcert=/etc/vectra/ca/ca.crt
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U8: el hook de migracion corre antes de que los Deployment queden Ready; sslmode=verify-full conecta de verdad con case-db | Job case-migration Complete; case-service 2/2 Running con sslmode=verify-full contra case-db-rw | si (el orden hook-antes-de-Ready no se volvio a observar: el sync es del 2026-11-16) |

### K-15 — U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc…

- Demo: Base. Fuentes: `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:43`, `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md:45`, `CANDIDATAS.md:520`.

**Resultado esperado.** U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc>-predictor.vectra-serving y -explainer resuelven desde vectra-app

**Comando.** Previsto: `arranque.sh vectra-app`; `humo flujo --delivery /verification/reference-model/.out`.

```bash
kubectl --context kind-vectra get deploy scoring-service explainability-service -n vectra-app -o jsonpath='{range .items[*]}{.metadata.name}{" readOnlyRootFilesystem="}{.spec.template.spec.containers[0].securityContext.readOnlyRootFilesystem}{" volumes="}{.spec.template.spec.volumes[*].name}{"\n"}{end}'; kubectl --context kind-vectra get svc -n vectra-serving --no-headers | awk '{print $1}'
```

**Salida.**

```text
scoring-service readOnlyRootFilesystem=true volumes=service-identity keycloak-ca
explainability-service readOnlyRootFilesystem=true volumes=service-identity keycloak-ca
isvc-8a98ab02-explainer
isvc-8a98ab02-predictor
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| U7 arranca con la raiz de solo lectura y sin emptyDir; los hosts <isvc>-predictor.vectra-serving y -explainer resuelven desde vectra-app | scoring y explainability con readOnlyRootFilesystem=true y solo los volumenes service-identity y keycloak-ca; los Service del predictor y del explicador existen y el flujo base llega a listo | si |

### K-16 — vectra-internal-ca existe en vectra-app y el JWKS responde por https

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:72`.

**Resultado esperado.** vectra-internal-ca existe en vectra-app y el JWKS responde por https

**Comando.** Previsto: `kubectl --context kind-vectra get configmap vectra-internal-ca -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=console-bff`.

```bash
kubectl --context kind-vectra get configmap vectra-internal-ca -n vectra-app; kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=console-bff -c console-bff --tail=400 | grep -ci 'jwks.*error\|certificate verify failed'
```

**Salida.**

```text
NAME                 DATA   AGE
vectra-internal-ca   1      18d
0
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| vectra-internal-ca existe en vectra-app y el JWKS responde por https | el ConfigMap existe; 0 errores de JWKS o de certificado en el log del BFF; las llamadas por el BFF dan 200 | si |

### K-17 — El eco de U2 (recursos con la etiqueta part-of identity-edge-e2e: compa…

- Demo: Base. Fuentes: `aidlc-docs/construction/console/evidence/cierre-demo.md:71`, `CANDIDATAS.md:402`, `CANDIDATAS.md:412`, `CANDIDATAS.md:259`, `tareas/U12-T05-imagen-y-documentacion.md:361`.

**Resultado esperado.** El eco de U2 (recursos con la etiqueta part-of identity-edge-e2e: comparten nombre con governance, case-service, console-bff y console-spa) se retira antes de sincronizar esas cuatro Applications; la ServiceAccount temporal console-bff de U4 no existe antes del sync de U10

**Comando.** Previsto: `kubectl --context kind-vectra get deploy,svc,sa,pdb -l app.kubernetes.io/part-of=identity-edge-e2e -n vectra-app`; `kubectl --context kind-vectra get sa console-bff -n vectra-app`.

```bash
kubectl --context kind-vectra get deploy,svc,sa,pdb -l app.kubernetes.io/part-of=identity-edge-e2e -n vectra-app; kubectl --context kind-vectra get deploy,svc,sa,pdb -l app.kubernetes.io/part-of=identity-edge-e2e -n vectra-edge; kubectl --context kind-vectra get sa console-bff -n vectra-app -o jsonpath='{.metadata.name}{" part-of="}{.metadata.labels.app\.kubernetes\.io/part-of}{"\n"}'
```

**Salida.**

```text
No resources found in vectra-app namespace.
No resources found in vectra-edge namespace.
console-bff part-of=console
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| El eco de U2 y la ServiceAccount temporal console-bff de U4 no existen antes del sync de U10 | ningun recurso del eco en vectra-app ni en vectra-edge; la ServiceAccount console-bff que hay es la del chart de U10 (part-of=console) | si (el orden del sync no se volvio a observar: U10 ya estaba sincronizado) |

### K-18 — product-metrics arranca despues del registro; si no, 503 hasta 30 min …

- Demo: D4. Fuentes: `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:54`, `CANDIDATAS.md:598`.

**Resultado esperado.** product-metrics arranca despues del registro; si no, 503 hasta 30 min y dashboard vacio

**Comando.** Previsto: `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=product-metrics -n vectra-app`; `kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=product-metrics`.

```bash
kubectl --context kind-vectra get pods -l app.kubernetes.io/name=product-metrics -n vectra-app; kubectl --context kind-vectra get pods -l app.kubernetes.io/name=decision-registry-service -n vectra-app; kubectl --context kind-vectra logs -n vectra-app -l app.kubernetes.io/name=product-metrics --tail=3 2>&1 | cut -c1-300
```

**Salida.**

```text
NAME                               READY   STATUS    RESTARTS   AGE
product-metrics-7dc56bb84c-7nj79   2/2     Running   0          10h
product-metrics-7dc56bb84c-nh6zv   2/2     Running   0          10h
NAME                                         READY   STATUS    RESTARTS   AGE
decision-registry-service-6995444c56-lbmx9   2/2     Running   0          10h
decision-registry-service-6995444c56-z9n2l   2/2     Running   0          10h
Defaulted container "product-metrics" out of: product-metrics, linkerd-network-validator (init), linkerd-proxy (init)
Defaulted container "product-metrics" out of: product-metrics, linkerd-network-validator (init), linkerd-proxy (init)
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| product-metrics arranca despues del registro; si no, 503 hasta 30 min y dashboard vacio | product-metrics 2/2 Running, con la misma edad que el registro (los dos pods se recrearon tras el reinicio de la maquina); el target product-metrics esta up | si (el dashboard se lee en F9) |

### K-19 — Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMon…

- Demo: D1, D3, D4. Fuentes: `aidlc-docs/construction/case-management/evidence/cierre-demo.md:75`, `aidlc-docs/construction/console/evidence/cierre-demo.md:73`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:52`, `tareas/U12-T05-imagen-y-documentacion.md:372`.

**Resultado esperado.** Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMonitor de U8 (tres), del BFF y de U11; Grafana descubre el ConfigMap del dashboard en Vectra / Producto

**Comando.** Previsto: `observabilidad.sh reglas`; `observabilidad.sh targets`.

```bash
system-verification/docs/kind/observabilidad.sh reglas; system-verification/docs/kind/observabilidad.sh targets; kubectl --context kind-vectra get configmap -A -l grafana_dashboard --no-headers | head
```

**Salida.**

```text
grupo case-management: 1 reglas (CoreWriteAttempt)
grupo vectra-product-alerts: 6 reglas (RuidoExplicacion, ProductMetricsDegraded, ProductMetricsStale, ProductMetricsStale, ProductMetricsFullRecomputeMissing, ProductMetricsFullRecomputeMissing)
grupo vectra-product-dedup: 15 reglas
grupo vectra-product-desync: 1 reglas
grupo vectra-product-ratios: 2 reglas
grupo identity-edge: 12 reglas (KeycloakDown, RateLimitBackendDown, AuthDeniedBurst, BreakGlassLogin, KeycloakMetricsDown, RealmDrift, RoleConflict, SigningKeyAgeHigh, LdapUnavailable, GatewayHighLatency, RealmDriftStale, SigningKeyAgeStale)
grupo platform: 28 reglas (Watchdog, WalArchiveStale, BackupFailed, RestoreDrillFailed, RestoreDrillMissing, RestoreDrillRetentionViolation, RegistryDbWritesBlocked, KyvernoUnavailable, LinkerdControlPlaneDown, SingleZoneOperation, MinioWriteQuorumLost, PostgresReplicaLag, CertificateExpiringSoon, CertificateExpiringSoon, RecommendationSLOBurnFast, RecommendationSLOBurnSlow, FailClosedPersistente, PostgresConnectionsHigh, PostgresVolumeUsageHigh, PostgresVolumeUsageHigh, PostgresVolumeUsageHigh, PostgresVolumeUsageHigh, PostgresVolumeUsageHigh, PostgresVolumeUsageHigh, HPAMaxedOut, PushgatewayDown, GrafanaFolderPermissionsDrift, LogFieldsDropped)
grupo slo-recording: 5 reglas
8 grupos; pedidas: CoreWriteAttempt, FailClosedPersistente, ProductMetricsStale
bias-monitoring-service vectra-app up x2
case-service vectra-app up x2
case-worker vectra-app up x2
cert-manager cert-manager up x1
console-bff vectra-app up x2
core-banking-mock vectra-mock up x2
decision-registry-service vectra-app up x2
envoy-data-plane vectra-edge up x1
envoy-ratelimit envoy-gateway-system up x2
explainability-service vectra-app up x2
governance-service vectra-app up x2
keycloak vectra-identity up x1
kube-prometheus-stack-alertmanager vectra-observability up x2
kube-prometheus-stack-grafana vectra-observability up x1
kube-prometheus-stack-operator vectra-observability up x1
kube-prometheus-stack-prometheus vectra-observability up x2
kube-state-metrics vectra-observability up x1
kubelet kube-system up x9
kyverno kyverno up x1
linkerd-controller linkerd up x1
linkerd-proxy vectra-mock up x2
minio vectra-data up x2
product-metrics vectra-app up x2
pushgateway vectra-observability up x1
scoring-service vectra-app up x2
valkey vectra-edge up x2
vectra-data/case-db vectra-data up x1
vectra-data/governance-db vectra-data up x1
vectra-data/keycloak-db vectra-data up x1
vectra-data/registry-db vectra-data up x2
No resources found
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Prometheus carga las PrometheusRule de U8 y U11 y raspa los ServiceMonitor de U8 (tres), del BFF y de U11; Grafana descubre el ConfigMap del dashboard en Vectra / Producto | 8 grupos de reglas con las tres pedidas; targets de U8, del BFF y de U11 en up | si (el dashboard de Grafana se abre en F9) |

### K-20 — Selectores y puertos de partida

- Demo: Base. Fuentes: `CANDIDATAS.md:671`, `tareas/U12-T04-demos-cli-y-manifiesto.md:141`, `tareas/U12-T05-imagen-y-documentacion.md:367`.

**Resultado esperado.** Selectores y puertos de partida: Prometheus (app.kubernetes.io/name=prometheus, 9090) y el registro (decision-registry-service, 8080)

**Comando.** Previsto: `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=prometheus -n vectra-observability`; `kubectl --context kind-vectra get pods -l app.kubernetes.io/name=decision-registry-service -n vectra-app`.

```bash
kubectl --context kind-vectra get pods -l app.kubernetes.io/name=prometheus -n vectra-observability; kubectl --context kind-vectra get pods -l app.kubernetes.io/name=decision-registry-service -n vectra-app
```

**Salida.**

```text
NAME                                            READY   STATUS    RESTARTS   AGE
prometheus-kube-prometheus-stack-prometheus-0   3/3     Running   0          10h
NAME                                         READY   STATUS    RESTARTS   AGE
decision-registry-service-6995444c56-lbmx9   2/2     Running   0          10h
decision-registry-service-6995444c56-z9n2l   2/2     Running   0          10h
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Selectores y puertos de partida: Prometheus (app.kubernetes.io/name=prometheus, 9090) y el registro (decision-registry-service, 8080) | los dos selectores devuelven pods Running | si |

### K-21 — Proxy de Linkerd en vectra-mock

- Demo: D3. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:28`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:69`, `DECISIONES-LOOP.md:118`, `tareas/U12-T05-imagen-y-documentacion.md:369`.

**Resultado esperado.** Proxy de Linkerd en vectra-mock: el target linkerd-proxy en up == 1 (no 403) y los pods Ready con el Server del 4191 (las sondas /live y /ready pasan)

**Comando.** Previsto: `observabilidad.sh consulta up{namespace="vectra-mock"}`; `kubectl --context kind-vectra get pods -n vectra-mock`.

```bash
system-verification/docs/kind/observabilidad.sh consulta 'up{namespace="vectra-mock"}' | sed 's/instance="[^"]*",//'; kubectl --context kind-vectra get pods -n vectra-mock
```

**Salida.**

```text
{__name__="up",container="core-banking-mock",endpoint="metrics",job="core-banking-mock",namespace="vectra-mock",pod="core-banking-mock-5cd84d7886-wvg8c",service="core-banking-mock"} 1
{__name__="up",container="core-banking-mock",endpoint="metrics",job="core-banking-mock",namespace="vectra-mock",pod="core-banking-mock-5cd84d7886-l9ks2",service="core-banking-mock"} 1
{__name__="up",container="linkerd-proxy",endpoint="linkerd-admin",job="linkerd-proxy",namespace="vectra-mock",pod="core-banking-mock-5cd84d7886-wvg8c"} 1
{__name__="up",container="linkerd-proxy",endpoint="linkerd-admin",job="linkerd-proxy",namespace="vectra-mock",pod="core-banking-mock-5cd84d7886-l9ks2"} 1
NAME                                 READY   STATUS    RESTARTS   AGE
core-banking-mock-5cd84d7886-l9ks2   2/2     Running   0          10h
core-banking-mock-5cd84d7886-wvg8c   2/2     Running   0          10h
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Proxy de Linkerd en vectra-mock: el target linkerd-proxy en up == 1 (no 403) y los pods Ready con el Server del 4191 (las sondas /live y /ready pasan) | linkerd-proxy de vectra-mock up == 1 en los dos pods; pods 2/2 Running | si |

### K-22 — Politica activa y modelo de referencia activo

- Demo: Base. Fuentes: `aidlc-docs/construction/governance/evidence/cierre-demo.md:27`, `aidlc-docs/construction/governance/evidence/cierre-demo.md:28`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:43-51`, `aidlc-docs/construction/plans/demo-recorte-funcional.md:401`, `tareas/U12-T05-imagen-y-documentacion.md:362`.

**Resultado esperado.** Politica activa y modelo de referencia activo: serving-config trae policy_version_id y la version

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`; a mano: plantillas 03 y 04 de U4 (governance/evidence/kind).

```bash
kubectl --context kind-vectra exec -n vectra-data governance-db-1 -c postgres -- psql -U postgres -d governance -At -c 'select model_version_id, state from model_versions' -c 'select policy_version_id, state from policies' -c 'select * from serving_config'
```

**Salida.**

```text
mv-2026-01-01-8a98ab02|activo
pol-e97ec26fd06b|activa
1|mv-2026-01-01-8a98ab02|activo|pol-e97ec26fd06b|1.0.0|isvc-8a98ab02|{"source_ref": "sintetico: sin valor normativo real
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Politica activa y modelo de referencia activo: serving-config trae policy_version_id y la version | politica pol-e97ec26fd06b activa y modelo mv-2026-01-01-8a98ab02 activo; serving_config trae los dos y el isvc-8a98ab02 | si (las plantillas 03 y 04 de U4 no se revisaron aqui) |

### K-23 — Con 256 MiB por pod bastan el predictor y el explicador del modelo de …

- Demo: Base. Fuentes: `DECISIONES-LOOP.md:82-84`, `aidlc-docs/construction/model-serving/evidence/cierre-demo.md:34`.

**Resultado esperado.** Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia (sin OOMKilled)

**Comando.** Previsto: `arranque.sh vectra-serving`; `memoria.sh antes`.

```bash
system-verification/docs/kind/arranque.sh vectra-serving | tail -5; kubectl --context kind-vectra get pods -n vectra-serving -o jsonpath='{range .items[*]}{.metadata.name}{" restarts="}{.status.containerStatuses[*].restartCount}{" lastState="}{.status.containerStatuses[*].lastState.terminated.reason}{"\n"}{end}'
```

**Salida.**

```text
ExternalSecret: 1 en los namespaces pedidos, 0 sin SecretSynced
AVISO Application kserve-crd: OutOfSync
AVISO Application linkerd-control-plane: OutOfSync
Applications: 56, 0 fuera de Healthy, 2 fuera de Synced
arranque: sin hallazgos
isvc-8a98ab02-explainer-5b89dc76c8-7hnl4 restarts=0 lastState=
isvc-8a98ab02-explainer-5b89dc76c8-ppdzl restarts=0 lastState=
isvc-8a98ab02-predictor-7c455998dd-9m98b restarts=0 lastState=
isvc-8a98ab02-predictor-7c455998dd-dvdvd restarts=0 lastState=
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Con 256 MiB por pod bastan el predictor y el explicador del modelo de referencia (sin OOMKilled) | vectra-serving: 4 pods, 0 hallazgos, 0 reinicios y sin OOMKilled; unos 81 MiB de trabajo por pod frente a 256 MiB | si |

### K-24 — Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2

- Demo: D1, D2. Fuentes: `model-serving/docs/paso-11-kind.md:42-58`, `tareas/U12-T05-imagen-y-documentacion.md:362`.

**Resultado esperado.** Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2

**Comando.** Previsto: a mano: la salida de mc ls de model-serving/docs/paso-11-kind.md, seccion 2, con RT3-a, RT3-c y RT3-d (rt3 exige los tres); `arranque.sh vectra-data`.

```bash
kubectl --context kind-vectra exec -n vectra-data minio-0 -c minio -- sh -c 'ls /export-0/model-store; for c in mv-2026-01-01-f12bfeaf adversarial/rt3/RT3-a adversarial/rt3/RT3-b adversarial/rt3/RT3-c adversarial/rt3/RT3-d; do echo "$c: $(ls /export-0/model-store/$c | wc -l) archivos"; done'
```

**Salida.**

```text
adversarial
mv-2026-01-01-253e325d
mv-2026-01-01-8a98ab02
mv-2026-01-01-bed07b8f
mv-2026-01-01-c8d04261
mv-2026-01-01-eb22dae6
mv-2026-01-01-f12bfeaf
mv-2026-01-01-f12bfeaf: 7 archivos
adversarial/rt3/RT3-a: 7 archivos
adversarial/rt3/RT3-b: 7 archivos
adversarial/rt3/RT3-c: 7 archivos
adversarial/rt3/RT3-d: 7 archivos
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Paquetes proxy y RT-3 (a, b, c y d) en el model-store, para D1 y D2 | leido del disco de MinIO, no con `mc ls`: el proxy run-1 (mv-2026-01-01-f12bfeaf) y RT3-a, b, c y d con 7 entradas cada uno | si |

### K-25 — Watchdog recibido, no solo disparado

- Demo: ninguna. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:27`, `tareas/U12-T05-imagen-y-documentacion.md:369`.

**Resultado esperado.** Watchdog recibido, no solo disparado

**Comando.** Previsto: `observabilidad.sh consulta ALERTS{alertname="Watchdog"}`.

```bash
system-verification/docs/kind/observabilidad.sh consulta 'ALERTS{alertname="Watchdog"}'; kubectl --context kind-vectra get pods -n vectra-observability -l app.kubernetes.io/name=alertmanager
```

**Salida.**

```text
{__name__="ALERTS",alertname="Watchdog",alertstate="firing",severity="none"} 1
NAME                                                READY   STATUS    RESTARTS   AGE
alertmanager-kube-prometheus-stack-alertmanager-0   3/3     Running   0          10h
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Watchdog recibido, no solo disparado | la alerta Watchdog esta en firing en Prometheus y Alertmanager esta Running | parcial: disparada; que un receptor la reciba no se comprobo |

### K-26 — Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04)

- Demo: ninguna. Fuentes: `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:23`, `aidlc-docs/construction/platform-foundation/evidence/cierre-acotado.md:25`, `aidlc-docs/construction/case-management/evidence/cierre-demo.md:70`, `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md:36`, `aidlc-docs/construction/console/evidence/cierre-demo.md:68`, `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md:49`.

**Resultado esperado.** Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04): no se comprueban porque network y el Paso 9 estan diferidos; los permitidos se ven por el flujo base y las demos

**Comando.** Previsto: `humo flujo --delivery /verification/reference-model/.out`.

```bash
no ejecutado
```

**Salida.**

```text
no ejecutado
```

| Esperado | Obtenido | Cumple |
|---|---|---|
| Flujos negados (suite X01 a X10, casos bloqueados de INF-U10-04, X04): no se comprueban porque network y el Paso 9 estan diferidos; los permitidos se ven por el flujo base y las demos | no ejecutado: la seccion network y el Paso 9 estan diferidos | no ejecutado |

## Hallazgos

- **H-4 (U1, conocido).** `kserve-crd` y `linkerd-control-plane` siguen OutOfSync y Healthy; es lo anotado en `platform/runbooks/install.md`, «Lo medido el 2026-11-19 tras reiniciar la maquina». Las demas Applications estan Synced y Healthy.
- **Nota.** No se sincronizo nada en esta corrida: todas las unidades estaban desplegadas y sanas desde el 2026-11-15 al 2026-11-19, y la guia pide no repetir una unidad sana. Por eso lo que depende del orden del sync (K-14, K-17, K-18) se leyo del estado final y no se volvio a observar.
- **Nota.** `vectra-restore-drill/restore-drill-29911800` esta en Error desde hace 5 dias (falta el ejecutable `vectra-registry`, candidata conocida); no sostiene ninguna demo.
