# Ajustes de U1 para la ruta demo en `kind-vectra`

Análisis de solo lectura, hecho el 2026-11-07 sobre `wt-demo-ruta/vectra-risk` (rama `demo/ruta`, igual a `main` más 3 commits de documentación). Contra el clúster solo se usaron `kubectl get` y `kubectl describe`, además de `docker stats --no-stream` y `ps`/`sysctl`/`free` en el host. No hay metrics-server, así que `kubectl top` responde `Metrics API not available`.

Ramas de U2 sin fusionar: **las ramas locales están por delante de `origin`**.
- `tarea/U02-T18` local (49db24b) ya trae `BUDGET_GIB = 8.0` y cuenta el controlador de KServe. En `origin/tarea/U02-T18` (9b8a28a) sigue `BUDGET_GIB = 5.0`.
- `tarea/U02-T17` local (09d8c26) ya trae `KubeStateMetricsDown`. En `origin/tarea/U02-T17` (3b716ab) solo está la decisión documentada.

Este análisis toma las ramas locales.

---

## 0. Estado actual del clúster: hoy no funciona

Esto no está en el README de la ruta demo, y va antes que todo lo demás.

| Hecho | Evidencia |
|---|---|
| El host se reinició hoy a las 10:04 | `uptime -s` → `2026-11-07 10:04:14` |
| `fs.inotify.max_user_instances` volvió a 128 | `sysctl` → `128`. `platform/runbooks/install.md:31` dice que con 128 `linkerd-cni` falla con `too many open files` y que el valor «no sobrevive a un reinicio» |
| `linkerd-cni` está en CrashLoopBackOff en los dos workers | `linkerd-cni-8qtks` (vectra-worker, 137 reinicios) y `linkerd-cni-f9ldb` (vectra-worker2, 122 reinicios), con `install-cni` terminando con `exitCode 1`. Solo funciona el del control-plane |
| Por eso todos los pods mallados de los workers están `Unknown`, con `linkerd-network-validator` en backoff | Las 4 bases (`registry-db-2`, `case-db-1`, `governance-db-1`, `keycloak-db-1`), `minio-0`, el control plane de Linkerd y toda `vectra-observability` (Prometheus, Grafana, Loki, Tempo, Pushgateway, Alloy, otel) |
| Vault dev perdió lo sembrado | `vault-0` lleva 10 reinicios y arrancó por última vez a las 15:05Z. Los 58 `ExternalSecret` están en `Ready=False` (`SecretSyncedError: could not get secret data from provider`). Hay que seguir el runbook «Vault reiniciado» (`install.md:146-151`): claves nuevas, roles de Postgres, usuarios de MinIO y la clave de admin de Grafana |
| Los backups de las 03:00 quedaron pendientes | `BackupPending … target pod not ready` en `case-db` y `governance-db` |
| En el host no hay holgura de memoria | `free -g`: 10 GiB usados, 4 GiB disponibles, **swap de 3/3 GiB llena**, y eso con casi todo U1 caído. El mayor proceso es `kube-apiserver`, con 2,2 GiB de RSS. Después vienen `argocd-application-controller` (0,72 GiB), Teams, Edge (unos 2 GiB entre todos sus procesos), `claude` y varios `pytest` de worktrees |

**Consecuencia:** antes de cualquier instalación de la demo hay que recuperar U1. Son tres pasos de operador, todos fuera de mis permisos:
1. `sysctl` a 512 y reiniciar `linkerd-cni`;
2. el runbook «Vault reiniciado»;
3. esperar a que las bases y la observabilidad vuelvan.

Cada reinicio del host repite esta recuperación. Para el día de la demo es frágil: ver los ajustes A13 y A14.

---

## 1. RD1: el `PolicyException` de kind

### 1.1 Reglas de U1 que exigen réplicas, HPA, PDB o spread

**Kyverno**, en `platform/policies/kyverno/`. Todas con `Enforce`, salvo que se diga otra cosa. Todas hacen match en los namespaces `vectra-app`, `vectra-edge`, `vectra-identity`, `vectra-serving` y `vectra-mock`. Ninguna mira `vectra-staging`.

| Política / regla | Archivo:línea | Qué exige | ¿Rechaza kind-demo? |
|---|---|---|---|
| `require-spread-and-pdb` / `require-min-replicas` | `require-spread-and-pdb.yaml:13-35` | `Deployment.spec.replicas >= 2`. Exime el `inactivo`+`hpa-exempt` y el data plane de Envoy en `vectra-edge` | **Sí** |
| `require-spread-and-pdb` / `require-zone-spread` | `:36-54` | `topologySpreadConstraints` con `topology.kubernetes.io/zone` | Solo si el chart kind-demo quita el spread. Con 1 réplica el spread no estorba |
| `require-spread-and-pdb` / `require-pdb` | `:57-84` | Un PDB con el mismo `app.kubernetes.io/name` (consulta la API) | Solo si kind-demo quita el PDB. Las tablas de U3, U7, U8, U9 y U10 lo difieren en kind |
| `require-hpa-bounds` / `deployment-needs-hpa-or-exemption` | `require-hpa-bounds.yaml:94-121` | HPA o la anotación `vectra.io/hpa-exempt` | No: `failureAction: Audit` (`:114`). Solo deja un reporte |
| `require-hpa-bounds` / `exempt-needs-two-replicas` | `:122-140` | Con `hpa-exempt`, `replicas >= 2` (salvo `inactivo`) | **Sí**, si kind-demo usa la anotación |
| `require-hpa-bounds` / `active-inference-service-needs-two-replicas` | `:141-158` | `InferenceService` no inactivo con `predictor.minReplicas >= 2` (solo `vectra-serving`) | **Sí** (U6) |
| `require-hpa-bounds` / `inactive-inference-service-needs-exemption` | `:159-174` | El inactivo necesita `hpa-exempt` | No aplica a kind-demo |

**conftest**, en `platform/policies/rego/`. Corre en `make -C platform check-chart`, que renderiza cada entrada de `components.yaml` **también en kind y con sus `kind_values`** (`platform/tests/integration.py:147-165`). Por eso un chart kind-demo falla aquí aunque Kyverno lo admita en el clúster:

| Regla | Archivo:línea |
|---|---|
| `deployment-hpa`: sin HPA ni `hpa-exempt` → deny | `hpa.rego:21-28` |
| `deployment-replicas`: `replicas < 2` → deny | `hpa.rego:41-47` |
| `deployment-pdb`: sin PDB → deny | `hpa.rego:49-55` |
| `zone-spread`: sin spread por zona → deny | `platform.rego:8-19` |

Las cuatro miran los mismos 5 namespaces y no conocen el perfil.

### 1.2 Reglas que van en el `PolicyException`

Propuesta, con un recurso `kyverno.io/v2` `PolicyException` en el namespace `kyverno`:

| `policyName` | `ruleNames` |
|---|---|
| `require-spread-and-pdb` | `require-min-replicas`, `require-zone-spread`, `require-pdb` |
| `require-hpa-bounds` | `exempt-needs-two-replicas`, `active-inference-service-needs-two-replicas` y, opcional, `deployment-needs-hpa-or-exemption`, para no llenar los reportes de Audit |

- **Match:** `kinds: [Deployment, serving.kserve.io/v1beta1/InferenceService]`, `selector.matchLabels: { vectra.io/profile: kind-demo }`.
- **Namespaces:**
  - `vectra-app`: U3, U4, U7, U8, U9, U10 BFF y U11;
  - `vectra-edge`: `console-spa` de U10. El selector por etiqueta deja fuera a Envoy, a Valkey y al resto de U2;
  - `vectra-serving`: U6;
  - `vectra-mock`: `core-banking-mock` de U8.
- **Fuera:** `vectra-identity`, porque U2 ya cabe con sus 2 réplicas y Keycloak es un StatefulSet que estas reglas no ven (CANDIDATAS l. 61), y `vectra-staging`, que ninguna de estas reglas cubre.

RD1 nombra `require-spread-and-pdb` entera, así que entran sus tres reglas.

**Riesgo en `vectra-serving`.** KServe genera el `Deployment` del predictor y del explicador. Que la etiqueta `vectra.io/profile` del `InferenceService` pase a ese `Deployment` **no está verificado**: el diseño de U6 ya lo deja «sin verificar» para `serving-state`/`hpa-exempt`, en `model-serving/infrastructure-design/infrastructure-design.md:27`. Si no se propaga, la excepción por etiqueta no alcanza a esos Deployments. Alternativa, solo en kind: en `vectra-serving`, hacer match por `serving.kserve.io/inferenceservice` (Exists), la etiqueta que KServe pone siempre. Esto se comprueba con el primer `InferenceService` de U6 (comando en A1).

### 1.3 ¿La versión pinneada admite `PolicyException`? Sí, pero está **apagada**

- **Versión.** Chart `kyverno` 3.9.2 (`components.yaml:18`), app v1.19.2 (`tools.env`: `KYVERNO_VERSION=v1.19.2`; imagen `reg.kyverno.io/kyverno/kyverno:v1.19.2` en el clúster).
- **CRD.** Está instalado: `policyexceptions.kyverno.io`, versiones `v2` (storage) y `v2beta1`. También existe `policyexceptions.policies.kyverno.io`, pero ese aplica a las políticas CEL nuevas (`ValidatingPolicy`), no a `ClusterPolicy`. Para las `ClusterPolicy` de U1 hay que usar `kyverno.io/v2`, que la API marca como *deprecated* («will be removed in a future release»). Sirve en 1.19; es deuda si se actualiza Kyverno.
- **Flag.** El admission controller del clúster corre con **`--enablePolicyException=false`**. En el chart 3.9.2, `features.policyExceptions.enabled` vale `false` y `namespace` vale `''` por defecto (`values.yaml:915-920` del chart; `_helpers.tpl:89-91` lo convierte en `--enablePolicyException` / `--exceptionNamespace`). Ni `platform/operators/kyverno.yaml` ni `kyverno-kind.yaml` lo tocan.
- **Qué hace falta.** Solo en `platform/operators/kyverno-kind.yaml`:
  ```yaml
  features:
    policyExceptions: { enabled: true, namespace: kyverno }
  ```
  Con `namespace: kyverno` solo se aceptan excepciones en ese namespace, que solo maneja Argo CD.
- **Coste.** Hay que sincronizar la Application `kyverno` (hoy `OutOfSync` por CRD) y se reinicia el único admission controller. Con `failurePolicy: Fail`, las admisiones se rechazan durante el reinicio.

---

## 2. RD2: `registry-db` con 2 instancias

### 2.1 Dónde se fija el número

- `platform/data/chart/values-kind.yaml:6`: `instances: 1` es **global** (`zoneConstraint: false` en `:7`). `clusters.registry-db` (`:13`) solo fija storage y recursos con el ancla `&small`, que comparten las 4 bases.
- `platform/data/chart/templates/clusters.yaml:12-16`: `instances: {{ $.Values.instances }}`; si es mayor que 1, pone `minSyncReplicas: 1` y **`maxSyncReplicas: 2` fijo**.
  - **No se puede fijar por base.** Hay que leer `$c.instances` con el valor global como respaldo.
  - **Con 2 instancias, `maxSyncReplicas: 2` es inválido.** El webhook de CloudNativePG (1.30.1 en el clúster) exige `maxSyncReplicas` < `instances`. La plantilla tiene que calcular `min(2, instances-1)`. Hay que confirmarlo con `kubectl apply --dry-run=server` al implementar.
- **Encaje en los nodos.** `podAntiAffinityType: required` por `kubernetes.io/hostname` (`clusters.yaml:53-56`). Hay 2 workers sin taint (`vectra-worker` en `zone-a`, `vectra-worker2` en `zone-b`) y el control-plane tiene `NoSchedule`, así que 2 instancias caben, una por zona.
- **Precedente.** El simulacro de failover (`evidence/simulacro-failover-reducido.txt`) ya corrió `registry-db` con 3 instancias, y `cierre-acotado.md` registra que el `join` funciona por el 4143. Por eso la instancia actual se llama `registry-db-2`.

### 2.2 Otras pruebas y políticas de U1 que fijan ese número

| Dónde | Qué fija | Efecto de RD2 |
|---|---|---|
| `platform/tests/test_kind_profile.py:58-61` en `main` y `:112-115` en `tarea/U02-T18` | `test_kind_has_no_synchronous_replica_but_production_does`: en kind, **todas** las `Cluster` con `instances == 1` y sin `minSyncReplicas` | **Falla**. Hay que cambiarla: `registry-db` 2/1/1 y las demás 1 |
| `test_kind_profile.py` (`tarea/U02-T18`), `BUDGET_GIB = 8.0` | Suma `instances × (memoria + proxy)` | +276 MiB. El perfil U1+U2 pide unos 7,0 GiB y queda en ≈ 7,3. Cabe en 8,0 sin U3–U12 (ver §5) |
| `platform/tests/test_platform.py:112-123` | Render de prod: 3 instancias, `minSync 1`, `maxSync 2` | No cambia si la plantilla conserva `maxSync = 2` con 3 instancias |
| `platform/observability/rules/platform-rules.yaml:63-70` (`RegistryDbWritesBlocked`) | Se activa si `expected > 0` y no hay réplica en streaming | Pasa a tener sentido en kind: si el standby cae, se dispara un SEV1, que es justo lo que U3 quiere mostrar |
| `platform-rules.yaml:176-183` (`PostgresVolumeUsageHigh`, `count(...) < 6`) | Espera 6 PVC de `registry-db` (3 instancias × 2) | En kind ya se dispara siempre, con 2 PVC, y con RD2 serían 4. Es ruido preexistente (CANDIDATAS: «`PostgresVolumeUsageHigh` en kind») |
| `platform/restore-drill/restore-cluster.sh:36` | El clúster efímero lleva `instances: 1` | Sin cambio |
| `clusters.yaml:82` `backup.target: prefer-standby` | — | Con RD2, el backup sale del standby: es el comportamiento de prod |

### 2.3 ¿`registry-db-ro` tiene endpoints? **No** (B3 confirmado)

```
endpointslice/registry-db-ro-gh46g   IPv4   <unset>   <unset>
endpointslice/registry-db-rw-vrfpp   IPv4   5432      192.168.109.18
endpointslice/registry-db-r-tncz6    IPv4   5432      192.168.109.18
```
Además, `registry-db` hoy está `Waiting for the instances to become active` por el problema de §0. `spec`: `instances 1`, sin `minSyncReplicas`/`maxSyncReplicas`.

---

## 3. Perfil kind-demo de U1: qué pesa más

### 3.1 Medición real (docker stats, con U1 medio caído)

| Contenedor | Memoria | CPU |
|---|---|---|
| `vectra-control-plane` | 2,67 GiB | 56 % |
| `vectra-worker` | 1,61 GiB | 113 % (crashloops) |
| `vectra-worker2` | 1,10 GiB | 54 % |
| `kind-registry` | 13 MiB | — |
| **Total** | **≈ 5,4 GiB** | |

Con U1 sano la medida era de unos 5,3 GiB (`audit.md:5973`). Hoy la cifra es parecida por otra razón: el apiserver y los crashloops pesan más, y no corren las bases ni la observabilidad. Hay que volver a medir después de recuperar el clúster.

**Procesos más pesados** (RSS en el host, `ps`):

| Proceso | RSS |
|---|---|
| `kube-apiserver` | 2 233 MiB |
| `argocd-application-controller` | 724 MiB |
| `etcd` | 178 MiB |
| `calico kube-controllers` | 146 MiB |
| `kube-controller-manager` | 135 MiB |
| 3 `kubelet` | ≈ 260 MiB entre los tres |
| `cert-manager cainjector` | 91 MiB |
| Kyverno admission | 80 MiB |
| `argocd-repo-server` | 77 MiB |
| CNPG manager | 62 MiB |
| ESO | 57 MiB |
| Vault dev | 53 MiB |

El apiserver, con 2,2 GiB, es el mayor consumidor de U1 en kind. Probablemente se debe al gran número de CRD (Kyverno con más de 20 CRD, KServe, Envoy, Prometheus, CNPG), a los reportes de admisión de Kyverno (`--admissionReports=true`) y a los reintentos de ESO. No está confirmado.

### 3.2 Requests de memoria por pod (lo que cuenta `test_kind_profile.py`)

Total ≈ **5,12 GiB** de requests (sin U2). Por namespace:
- `vectra-observability`: 2 388 MiB;
- `vectra-data`: 1 380 MiB;
- `kserve`: 600 MiB;
- `kyverno`: 320 MiB;
- `envoy-gateway-system`: 256 MiB;
- `kube-system`: 240 MiB.

Las piezas más pesadas:

| Pod | Request | Limit |
|---|---|---|
| `kserve-controller-manager` | 600 MiB (`manager` 300 + **`kube-rbac-proxy` 300**, el valor por omisión del chart; no hay overlay de kind) | 600 MiB |
| `prometheus-…-0` | 564 MiB (512 + reloader + proxy) | 1 216 MiB |
| 4 × CNPG (`registry`, `case`, `governance`, `keycloak`) | 276 MiB cada uno | 1 152 MiB cada uno |
| `minio-0` | 276 MiB | 1 152 MiB |
| Grafana | 276 MiB | 640 MiB |
| `envoy-gateway` (controlador) | 256 MiB | 1 024 MiB |
| Loki `read`/`write`/`backend` | 148 MiB cada uno | 640 MiB cada uno |
| Alloy × 2 (DaemonSet) | 116 MiB cada uno | 448 MiB cada uno |
| Alertmanager | 116 MiB | 320 MiB |
| Tempo × 5 componentes | 84 MiB cada uno | 384 MiB cada uno |
| otel, Pushgateway, operador, kube-state-metrics | 84 MiB cada uno | — |

### 3.3 ¿Hay réplicas de U1 que se puedan bajar? **Prácticamente no**

Todo lo que U1 instala en kind ya corre con 1 réplica:
- Kyverno, Argo CD y Linkerd: `kyverno-kind.yaml`, `argo-cd-kind.yaml` y `linkerd-kind.yaml`;
- Prometheus, Alertmanager, Loki ×3 roles, Tempo y otel: los `*-kind.yaml` de `platform/observability/values/`;
- MinIO: 1 pod con 4 discos;
- CNPG: 1 instancia por base.

Quedan con más de un pod solo los DaemonSets (Alloy, Calico, `linkerd-cni` y kube-proxy, uno por nodo) y CoreDNS ×2, que es de kind, no de U1. Bajar más significaría consolidar o apagar, y eso queda fuera de lo pedido.

Se pueden bajar requests sin apagar nada, y eso sí es perfil kind-demo:
- **KServe:** no tiene `kserve-kind.yaml`. `kube-rbac-proxy` pide 300 Mi y en la práctica usa del orden de decenas de MiB (por confirmar con Prometheus). Un overlay de kind ahorraría unos 250 MiB de requests. `test_kind_profile.py` (T18) lee las requests de los values del chart pinneado (`KSERVE_CHART_VALUES`) y habría que adaptarlo para que lea también el overlay;
- **CNPG:** las 4 bases a 256 Mi. Es una decisión de RD0 (requests mínimas), pero 256 MiB para Postgres ya es bajo.

Consolidar Loki en SingleBinary o Tempo en monolítico ahorraría varios pods. Es un cambio de diseño (INF-U1-07): queda solo apuntado, no se propone.

---

## 4. Lo que U3–U12 esperan de U1 en kind

| Punto | Estado | Evidencia |
|---|---|---|
| **Namespaces** | **Ya está** | `kubectl get ns`: `vectra-app`, `vectra-edge`, `vectra-identity`, `vectra-serving`, `vectra-staging`, `vectra-data`, `vectra-mock`, `vectra-observability` y `vectra-restore-drill`, todos con `pod-security.kubernetes.io/enforce: restricted` y `linkerd.io/inject: enabled` (`platform/namespaces/values.yaml:1`) |
| **Cuotas** | **Ya está** | `quotas.yaml:5-45` tiene los aportes de U3, U4, U7, U8, U9, U10 y U11 (`vectra-app`), U6 (`vectra-serving`), U8 (`vectra-mock`) y U10 (`vectra-edge`). Instaladas: `kubectl get resourcequota -A`. Hoy `vectra-app` va 0/23,3 GiB y `vectra-serving` 0/14,9 GiB |
| **`LimitRange`** | **Ya está** | `quotas.yaml:46`: solo `default` (500m/512Mi) y `defaultRequest` (100m/128Mi), **sin `min` ni `max`**. `vectra-defaults` instalado en los 9 namespaces |
| **Flujos de `flows.yaml`** | **Ya está** | Los que citan las tablas existen: U3 F42, F96, F97, F107, F111 (kind); U4 F24, F25, F30–F32, F41, F47; U6 F19, F22, F46; U7 F12, F15, F18, F20–F23, F103; U8 F04, F10, F16, F17 (kind/staging), F40, F104, F105; U9 F14, F26, F27, F106; U10 F02, F03, F10–F14; U11 F28; comunes F50, F60, F61. `flows.yaml:148-262` |
| **NetworkPolicies generadas** | **Ya está, con sync pendiente** | `platform/network/generated/kind/*.yaml`. La Application `network` está `OutOfSync`, por cambios de U2 en `vectra-app`, `vectra-edge` y `envoy-gateway-system`, y lo mismo `secret-store`. El operador tiene que sincronizar |
| **Bases CNPG por unidad** | **Ya está** (falta RD2) | `registry-db` (U3), `governance-db` (U4), `case-db` (U8) y `keycloak-db` (U2), con sus roles gestionados y `pg-role-*` en `vectra-app` (`data/chart/values.yaml:12-102`). U9, U10 y U11 no tienen base, por diseño |
| **Buckets de MinIO** | **Ya está** | `values-kind.yaml:11-19`: `model-store`, `validation-datasets`, `loki`, `tempo`, `vectra-registry-checkpoints`, `vectra-registry-archive`, `vectra-model-archive` y `vectra-backups` |
| **Usuarios de MinIO, B6** | **Falta** | `values-kind.yaml:22` y `:41` (más `values.yaml:41`/`:52`): `validation-datasets` solo tiene `validation-readonly` (`validation-read`). `risk-engineer-upload` usa `model-store-upload` (`values-kind.yaml:26`), que solo cubre `model-store`. Confirmado: nadie escribe en `validation-datasets` |
| **Vault y ESO** | **Ya está la estructura; hoy está caído** (§0) | `ClusterSecretStore vectra-store` Valid/Ready. Las rutas de las bases (`postgres/roles/<rol>`) y de MinIO (`minio/*`) salen del chart de datos de U1, así que U3, U4 y U8 las reciben sin tocar nada. Pero ver la fila siguiente |
| **Siembra de Vault de las unidades** | **Falta (bloqueo nuevo)** | `platform/kind/vault_paths.py:24-29`: `SOURCES` solo lee manifiestos de U1 (Grafana, `restore-drill` y `platform/secrets/`), más el chart de datos. Los `ExternalSecret` de U2 (`identity/clients/<cliente>` con `private-key`, `identity/ca` y los JWKS que lee el realm, por ejemplo `realm.prod.yaml:892` `$(env:CLIENT_GRAFANA_JWKS)`) y los de U3–U12 (llave `private_key_jwt` de cada cliente; `case-management/infrastructure-design.md:54`) **no se siembran**. Si se agregaran a `SOURCES`, `plan()` (`:93-105`) generaría `token_hex(24)`, que no es ni un JWK ES256 ni una semilla TOTP válida. Ninguna tarea de U2 (ni U02-T19) lo cubre |
| **Vault Transit, B4** | **Falta** (solo si la demo muestra checkpoints) | `grep -i transit` en `platform/` y `vectra-risk-gitops/` solo encuentra la NetworkPolicy F98 (`generated/kind/vault.yaml:135`). No hay motor `transit`, llave `vectra-registry-checkpoint` ni método de autenticación de Kubernetes en Vault (ESO entra con el token `root`). INF-U3-02 (`decision-registry/infrastructure-design.md:27-30`) lo pide. El Paso 11/12 de U3 lo difiere |
| **`ClusterIssuer` interno** | **Ya está** | `clusterissuer/vectra-internal-ca`, `vectra-selfsigned` y `linkerd-trust-anchor`, todos `Ready`. El emisor de Linkerd se renueva el 2026-11-08 a las 13:53Z (vence el 09) |
| **Argo CD de kind y repo, B9** | **Ya está** | Todas las Applications de directorio usan `https://github.com/jjlloobb/topicos-especiales-credito-de-vivienda.git` con `targetRevision: main` (`components.yaml:4`, `generate.py:83`, `apps/kind/root.yaml:12`), sincronizadas en `230e94c`, que es el `main` remoto (`git ls-remote`). Ninguna lleva `automated`. Los PR de promoción tienen que fusionarse en `main` antes del sync: la rama `demo/ruta` no la ve Argo CD. Hay 14 Applications `OutOfSync` (las 5 aceptadas en `cierre-acotado.md` más `network`, `secret-store`, `envoy-gateway`, `root`, `kserve-crd`, `minio`, `restore-drill`, `kube-prometheus-stack` y `kyverno`) |
| **KServe** | **Ya está** | `kserve-controller-manager` 2/2, `defaultDeploymentMode: RawDeployment` (`operators/kserve.yaml:6`), `storageInitializer` `kserve/storage-initializer:v0.21.0` (initContainer, que `restrict-registries` no mira). No hay `ClusterServingRuntime`: U6 trae sus imágenes. Sin verificar que las etiquetas del `isvc` lleguen al `Deployment` (§1.2) |
| **Pushgateway** | **Ya está** (caído hoy) | Componente `pushgateway` (`components.yaml:47`). Rutas por identidad en `flows.yaml:68-76`: `bias-monitoring-job` puede hacer `PUT/DELETE /metrics/job/bias-monitoring` (U9, F106) |
| **Loki** | **Ya está** (caído hoy) | SimpleScalable con 1 réplica por rol (`loki-kind.yaml`), datasource `loki` en Grafana (`kube-prometheus-stack.yaml:103`). Falta el filtro de `username`/`email` en Alloy (CANDIDATAS l. 39). Es dato de empleados, no del solicitante; no debería afectar a `LOGS-NO-PII` de U12, pero hay que confirmar el criterio de U12 |
| **Grafana: carpetas por unidad** | **Ya está la configuración** | `folder-permissions.yaml:3-5`: `vectra-sesgo` (U9), `vectra-producto` (U11) y `vectra-operacion`. El sidecar busca dashboards en `ALL` los namespaces con la etiqueta `vectra.io/dashboard` (`kube-prometheus-stack.yaml:112-117`) |
| **Grafana: acceso de los usuarios** | **Falta** | No hay `generic_oauth`, `root_url` con `/grafana`, `serve_from_sub_path` ni `allow_embedding` en `platform/observability/values/` (el `grep` no devuelve nada). Sin eso: `cro-1` no entra a «Vectra / Producto» (U12 guion paso 13); el iframe de U10 (BR-U10-16), que usa la sesión OIDC de Grafana (`bias-monitoring/infrastructure-design.md:131`), no carga; y la asignación a equipos (`cro`, `cumplimiento`) no existe. Ya está en CANDIDATAS (l. 40, 47, 82) |
| **F46, B5** | **Ya está; B5 está desactualizado** | `flows.yaml:191`: `F46 from [predictor, explainer, staging-isvc, staging-explainer] to [minio]`. Generado: `allow-f46-staging-explainer-to-minio-egress` (`generated/kind/vectra-staging.yaml:286-303`), el ingress en `vectra-data` (`allow-f46-to-minio-ingress`) y la `MeshTLSAuthentication` `f46-minio-9000-mtls` con `kserve-model.vectra-staging`. Las dos NetworkPolicies de staging están **instaladas** (`kubectl get networkpolicy -n vectra-staging`). Lo que sigue «Abierto» es el texto de INF-U6 (`model-serving/infrastructure-design/infrastructure-design.md:53`), no U1 |
| **Firma de imágenes en kind, B8** | **Ya está (excluida)** | `components.yaml:31-32`: `verify-images` con `envs: [staging, prod]`, y en kind no se instala (no aparece en `kubectl get clusterpolicy`). `restrict-registries.yaml:23` admite `registro.vectra.internal/*` y `kind-registry:5000/*`, con el espejo de containerd en `platform/kind/certs.d/registro.vectra.internal/hosts.toml`. Una imagen local sin firma se admite. Firmarla queda diferido (EXT SECURITY-10, U6 Paso 5) |
| **Operador de verificación K16 (U12)** | **Ya está** | Application `verification-operator` Synced/Healthy (`components.yaml:39`) |

---

## 5. Cuotas frente al perfil kind-demo

- **Las `ResourceQuota` no rechazan kind-demo por tamaño.** Están dimensionadas para el máximo del HPA de prod más un 30 % (`quotas.yaml:1`). kind-demo usa una fracción. Ejemplos: U4 en `vectra-staging` pide unos 1,6 GiB en el pico de la validación frente a 3,09 GiB de cuota de requests y 9,45 GiB de limits; U8 mock pide unos 0,15 GiB frente a 0,32 GiB.
- **Pods sin `limits`.** Las cuotas fijan `requests.*` y `limits.*`, así que un contenedor sin ellos sería rechazado por la cuota si no lo rellenara el `LimitRange`. Lo rellena: `LimitRanger` muta antes que la cuota y que los webhooks, con `defaultRequest` 100m/128Mi y `default` 500m/512Mi. El proxy de Linkerd es un sidecar nativo con sus requests y limits (`mesh/linkerd-values.yaml:17-20`). Pero:
  - `require-resources` (Kyverno, `require-resources.yaml:12-25`) y el `kyverno apply` estático de `check-chart` (está en `STATIC_POLICIES`, `Makefile:8`) exigen `requests` y `limits` **explícitos** en cada contenedor del chart. kind-demo tiene que declarar las dos cosas, aunque sean mínimas;
  - **caso borde:** un contenedor con `requests.memory` mayor que 512Mi y **sin** `limits` recibe el limit por defecto de 512Mi y lo rechaza la validación (`request > limit`).
- **Requests mínimas por debajo de un `LimitRange`.** No hay `min` (`render.py:41-49` solo emite `default` y `defaultRequest`), así que no se rechaza nada por bajo.
- **Lo que de verdad limita es la máquina, no la cuota.** Cada nodo de kind anuncia 8 CPU y 14,8 GiB (`describe node`: allocatable), así que el planificador ve 3 × 14,8 GiB y nunca rechaza. La memoria se sobrecomprometerá en silencio contra los 14,8 GiB reales.
  - Requests del clúster: U1 ≈ 5,1 GiB, U1+U2 ≈ 7,0 GiB (T18), RD2 +0,27 y U3–U11 ≈ 3,1–3,6 GiB (tablas de la ruta). En total, **≈ 10,4–10,9 GiB**.
  - Eso **supera el `BUDGET_GIB = 8.0`** de `test_kind_profile.py` (T18) en cuanto las Applications de las unidades entren en `components.yaml`, porque `render_env("kind")` las renderiza.
  - CPU: cada pod mallado pide 100m solo por el proxy. Hoy el clúster pide 5,9 CPU de 8 reales, y U3–U11 suman unos 15 pods estables más los transitorios.

---

## 6. Pendientes de `cierre-acotado.md` y `CANDIDATAS.md` que importan a la demo

| Pendiente | ¿Lo necesita la demo? |
|---|---|
| Failover de zona (20.4/4b) | **No** (RD3 difiere la resiliencia; sería con 32 GiB) |
| 5 Applications `OutOfSync` aceptadas | Hoy son 14 (§4). Las nuevas son syncs pendientes de cambios de U2 en `main` (`network`, `secret-store`, `envoy-gateway`, `root`). **Sí**: el operador tiene que sincronizarlas antes de U3 |
| Suite X01–X10 contra el clúster (20.1) | Es de U12 (`network`). No es un ajuste de U1 |
| Autorización de Linkerd entre ServiceAccounts (20.3) | Se prueba con U3 y U12. Ningún cambio de U1 |
| `Watchdog` recibido (20.7) | U12 |
| `grafana-folder-check` con tiempos agotados y Grafana con 11 reinicios que intenta salir a Internet | **Riesgo para U9, U11 y U12**: el último `grafana-folder-check-29901330` está en `Error`. Revisar cuando el clúster esté sano |
| Grafana `generic_oauth`, `root_url`/`serve_from_sub_path` y equipos (CANDIDATAS l. 40, 47, 82) | **Sí**: U10 (iframe), U11 y U12 (paso 13 del guion) |
| Filtro de Alloy para `username`/`email` (l. 39) | Probablemente no (no es del solicitante); confirmar con `LOGS-NO-PII` de U12 |
| Prueba de render con el overlay de kind (l. «Prueba de render con el overlay de kind…») | **Sí**: kind-demo es justo eso. Va con A1 y A4 |
| El `kyverno test` no ejercita la exención de un `Deployment` inactivo (l. 104) | Encaja con las pruebas de A1 |
| `require-pdb` no acota la exención de Envoy a `vectra-edge` (l. 103) | No |
| `restore-drill` | **Riesgo:** el CronJob corre los domingos a las 02:00 (`kubectl get cronjob`; `cronjob.yaml:10`). El próximo es el **2026-11-08 a las 02:00**. Levanta 2 clústeres efímeros (cuota de 10,4 GiB de requests) y llama a `case-retention`, que la ruta difiere (U8 Paso 16, B5 de U7–U9). Fallará con `RestoreDrillFailed` y consumirá memoria durante la demo. Que se suspenda en kind lo decide el usuario: no se propone apagarlo |

---

## Ajustes propuestos para U1

Ordenados por la unidad que los necesita primero. «EXT» significa que toca una extensión activa y necesita decisión del usuario. RD1 y RD2 ya están decididos.

### A0. Recuperar `kind-vectra` tras el reinicio (operación, sin cambio de repo)
- **Qué:** `sudo sysctl fs.inotify.max_user_instances=512`, reiniciar los pods de `linkerd-cni`, seguir el runbook «Vault reiniciado» (`install.md:146-151`) y sincronizar las Applications `OutOfSync` de U2 (`network`, `secret-store`, `envoy-gateway`, `root`).
- **Archivos:** ninguno.
- **Decisión:** la aprobación del operador (AUTONOMIA-01).
- **Unidad:** todas. Bloquea la instalación de U2 (U02-T19 / Paso 16) y de U3.
- **Comprobación:** `kubectl --context kind-vectra get pods -A | grep -v -E 'Running|Completed'` vacío; `kubectl get externalsecrets -A | grep -c False` igual a 0; `kubectl get applications -n argocd` sin `Degraded`.

### A1. `PolicyException` de kind (RD1)
- **Qué:**
  - **habilitar las excepciones** en el chart de Kyverno, solo en kind (§1.3);
  - **crear un `PolicyException`** `kyverno.io/v2` en `kyverno` con las reglas de §1.2 (`require-spread-and-pdb`: las 3; `require-hpa-bounds`: `exempt-needs-two-replicas`, `active-inference-service-needs-two-replicas` y, opcional, `deployment-needs-hpa-or-exemption`), con match por la etiqueta `vectra.io/profile: kind-demo` en `vectra-app`, `vectra-edge`, `vectra-serving` y `vectra-mock`. En `vectra-serving` hay que decidir entre la etiqueta y `serving.kserve.io/inferenceservice`, según se propague o no (§1.2);
  - **crear una Application** `kyverno-exceptions-kind` con `envs: [kind]` y wave 1, fuera del directorio de `kyverno-policies` para que no se instale en staging ni en prod;
  - **agregar pruebas:**
    - en `kyverno test`, con `exceptions:`, un Deployment de 1 réplica con la etiqueta (pasa) y otro sin ella (falla);
    - un `pytest` que compruebe que la Application solo existe en `apps/kind`;
    - un `pytest` que compruebe que ningún render de staging o prod lleva `vectra.io/profile: kind-demo`.
- **Archivos:**
  - `platform/operators/kyverno-kind.yaml`;
  - nuevo `platform/policies/kyverno-kind/kind-demo-exception.yaml`;
  - `vectra-risk-gitops/components.yaml` y `apps/kind/*` (`generate.py`);
  - `platform/policies/kyverno/kyverno-test.yaml` y `fixtures/`;
  - `platform/tests/test_platform.py` (`EXPECTED_WAVES`; **choca con T18**, que también lo edita: hacerlo después de fusionar T18);
  - `platform/tests/test_kind_profile.py`;
  - la tabla de cumplimiento de extensiones del plan de U1 y la nota de NFR-U1-12 en el comentario de `require-hpa-bounds.yaml:131`.
- **Decisión:** RD1 ya la tomó. Hay que registrar RESILIENCY-08/09 como «excepción solo en kind» en el cumplimiento de U1.
- **Unidad:** U3 (primer Deployment de 1 réplica en `vectra-app`). Después U4, U6, U7, U8, U9, U10 y U11.
- **Comprobación:**
  - `kubectl --context kind-vectra -n kyverno get deploy kyverno-admission-controller -o jsonpath='{.spec.template.spec.containers[0].args}' | tr ',' '\n' | grep -E 'enablePolicyException=true|exceptionNamespace=kyverno'`
  - `kubectl --context kind-vectra get policyexceptions.kyverno.io -n kyverno`
  - `platform/.tools/bin/kyverno test platform/policies/kyverno`
  - con el primer `isvc` de U6: `kubectl -n vectra-serving get deploy -l vectra.io/profile=kind-demo`

### A2. Exención kind-demo en las reglas de conftest
- **Qué:** que `hpa.rego` (`deployment-hpa`, `deployment-replicas`, `deployment-pdb`) y `platform.rego` (`zone-spread`) no nieguen un `Deployment` con `metadata.labels["vectra.io/profile"] == "kind-demo"`. Hay que añadir sus casos `pass`/`fail` en `policies/rego/tests/*/` (lo exige `rego_fixtures.py`). La guarda de A1 («nunca en staging/prod») cubre el riesgo de que la etiqueta llegue a prod, porque `check-chart` renderiza todos los entornos.
- **Archivos:** `platform/policies/rego/hpa.rego`, `platform/policies/rego/platform.rego`, `platform/policies/rego/tests/{deployment-hpa,deployment-replicas,deployment-pdb,zone-spread}/`.
- **Decisión:** es la misma de RD1 (EXT RESILIENCY-08/09). Sin este ajuste, las «Reglas de admisión» de cada plan (`make -C platform check-chart`) fallan aunque el clúster admita.
- **Unidad:** U3 (Paso 13, `check-chart`). Después U4 y U6–U11.
- **Comprobación:** `make -C platform check-tools`, que corre `rego_fixtures.py` y `conftest`, y `make -C platform check-chart CHART=<chart de U3>` con los values kind-demo.

### A3. `registry-db` con 2 instancias en kind (RD2)
- **Qué:**
  - en la plantilla, `instances: {{ $c.instances | default $.Values.instances }}` por base y `maxSyncReplicas` = `min(2, instances-1)`;
  - en `values-kind.yaml`, `registry-db` con `instances: 2`, sin romper el ancla `&small`;
  - adaptar `test_kind_profile.py::test_kind_has_no_synchronous_replica_but_production_does`: `registry-db` 2 con `minSync 1` y `maxSync 1`, las demás 1;
  - el presupuesto sube 276 MiB.
- **Archivos:** `platform/data/chart/templates/clusters.yaml:12-16`, `platform/data/chart/values-kind.yaml:6-20`, `platform/tests/test_kind_profile.py` (versión de T18), y la nota de `install.md:18` («una instancia por base»).
- **Decisión:** RD2 ya la tomó.
- **Unidad:** U3 (Pasos 7 y 9: readiness con standby síncrono; B2 y B3).
- **Comprobación:**
  - `helm template data platform/data/chart -f platform/data/chart/values-kind.yaml | grep -A3 'name: registry-db$'`
  - en el clúster: `kubectl -n vectra-data get cluster registry-db -o jsonpath='{.spec.instances} {.spec.minSyncReplicas} {.spec.maxSyncReplicas} {.status.readyInstances}'` debe dar `2 1 1 2`
  - `kubectl -n vectra-data get endpointslices -l kubernetes.io/service-name=registry-db-ro` con un endpoint

### A4. Presupuesto de memoria del perfil kind con U3–U12
- **Qué:** decidir qué mide `test_kind_profile.py` cuando las Applications de U3–U11 entren en `components.yaml`. Con kind-demo, las requests suben a unos 10,4–10,9 GiB, por encima de `BUDGET_GIB = 8.0` (T18). Hay dos caminos: subir el presupuesto (¿hasta dónde, con 14,8 GiB reales y la swap llena?) o medir U1+U2 por un lado y kind-demo por otro.
- **Archivos:** `platform/tests/test_kind_profile.py` (T18).
- **Decisión:** sí. Es una cifra que fija el usuario, igual que M5 en U02-T18.
- **Unidad:** U3, la primera Application de unidad.
- **Comprobación:** `uv run pytest platform/tests/test_kind_profile.py -q`, más `docker stats --no-stream` después de cada unidad, como dice el README.

### A5. Overlay de KServe para kind (requests mínimas, sin apagar nada)
- **Qué:** un `platform/operators/kserve-kind.yaml` que baje `kube-rbac-proxy` (y quizá `manager`) de 300Mi al uso real medido. Hay que agregarlo como `kind_values` y hacer que `kserve_gib()` de T18 lea también el overlay.
- **Archivos:** `platform/operators/kserve-kind.yaml` (nuevo), `vectra-risk-gitops/components.yaml:24`, `platform/tests/test_kind_profile.py` (`KSERVE_CHART_VALUES`).
- **Decisión:** no es EXT. Es perfil kind (RD0). Opcional: ahorra unos 250 MiB de requests.
- **Unidad:** U6, aunque el ahorro sirve desde ya.
- **Comprobación:** `kubectl -n kserve get deploy kserve-controller-manager -o jsonpath='{range .spec.template.spec.containers[*]}{.name} {.resources.requests.memory}{"\n"}{end}'`.

### A6. Escritura en `validation-datasets` (B6)
- **Qué:** que `risk-engineer-upload` (credenciales del ingeniero, NFR-U5-03) pueda subir el dataset de validación. Dos opciones: ampliar la política `model-store-upload` con `validation-datasets` (en `values.yaml` y en la copia de `values-kind.yaml`, porque Helm reemplaza listas), o crear una política `validation-upload` y adjuntarla al mismo usuario. `docs/release.md` de U5 y `business-logic-model.md:29` dicen «con las credenciales del ingeniero».
- **Archivos:** `platform/data/minio/values.yaml:49,57`, `platform/data/minio/values-kind.yaml:26,46`, la frase de identidades de INF-U1 en `platform-foundation/infrastructure-design/infrastructure-design.md:87` y las pruebas de MinIO (`platform/data/minio/tests/`).
- **Decisión:** sí. Es un cambio de mínimo privilegio en INF-U1 (SECURITY), y además aplica a staging/prod si se toca `values.yaml`. Si se quiere solo kind, va solo en `values-kind.yaml`.
- **Unidad:** U5 Paso 9. Después U4, en la validación real.
- **Comprobación:** con `mc` del operador y las credenciales de `minio/engineer-upload`, `mc cp dataset.parquet vectra/validation-datasets/` termina en 0 y `mc cp` a `vectra-backups` da `Access Denied`. En el render: `helm template … platform/data/minio | grep -A3 model-store-upload`.

### A7. Siembra de Vault para los `ExternalSecret` de las unidades (bloqueo nuevo)
- **Qué:**
  - ampliar `vault_paths.py` para que lea los `ExternalSecret` de los charts de unidad en kind (lo que `integration.render_env("kind")` renderiza), no solo los de U1;
  - darle generadores con tipo a lo que no puede ser aleatorio: un par ES256 por cliente de Keycloak, con la `private-key` en `identity/clients/<cliente>` y su JWKS donde lo lee el realm (`CLIENT_*_JWKS`), las semillas TOTP en Base32 y la CA (`identity/ca`, que se copia de `vectra-internal-ca`).
- **Archivos:** `platform/kind/vault_paths.py:24-29` y `:80-105`, `platform/kind/tests/test_vault_paths.py`, `platform/runbooks/install.md` (Paso 9 y «Vault reiniciado»).
- **Decisión:** sí. Falta decidir quién es el dueño, porque el diseño dice «la llave privada de cada cliente llega por un ExternalSecret (U2)» y ninguna tarea la genera en kind, y también el formato del JWKS.
- **Unidad:** U2 Paso 16 (U02-T19 / la instalación de U2). Después, cada unidad con un cliente de Keycloak (U3, U4, U7, U8, U9, U10 y U11).
- **Comprobación:** `uv run python platform/kind/vault_paths.py list | grep identity/clients`; después de sembrar, `kubectl get externalsecrets -A -o jsonpath='{range .items[?(@.status.conditions[0].status=="False")]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'` vacío.

### A8. Grafana: OIDC, subruta, embebido y equipos
- **Qué:** en `kube-prometheus-stack.yaml` (o su overlay de kind):
  - `grafana.ini` con `server.root_url` en `/grafana/` y `serve_from_sub_path: true`;
  - `auth.generic_oauth` contra el Keycloak de U2, con `private_key_jwt` ES256 si Grafana lo admite (CANDIDATAS l. 47; si no, decidir el método) y `role_attribute_path` desde `roles`;
  - `security.allow_embedding: true` con la `cookie_samesite` que pida U10;
  - en el Job `grafana-folder-permissions`, la asignación de usuarios a los equipos `cro`, `cumplimiento`, `ingeniero_riesgo` y `operacion` (CANDIDATAS l. 40).
- **Archivos:** `platform/observability/values/kube-prometheus-stack.yaml:85-117` (y `-kind.yaml`), `platform/observability/grafana/folder_permissions.py`, `folder-permissions.yaml` y `external-secrets.yaml` (llave del cliente `grafana`), `platform/tests/test_grafana_folder_permissions.py`.
- **Decisión:** sí. Hay que confirmar el método de autenticación del cliente (G1/G2 de CANDIDATAS l. 47) y que el iframe usa la sesión de Grafana (SECURITY-08/12).
- **Unidad:** U9 (carpeta «Vectra / Sesgo», visible en el iframe de U10), U10 (BR-U10-16), U11 (`product.json`) y U12 (guion, paso 13).
- **Comprobación:** `curl -sk https://<gateway>/grafana/api/health` devuelve 200; después de entrar como `cro-1`, `GET /grafana/api/folders/vectra-producto` da 200, y como `analista-1`, 403. Además, la prueba de permisos de carpetas de `make -C platform check-local`.

### A9. Vault Transit en kind (B4), solo si la demo muestra checkpoints
- **Qué:** habilitar `transit` en Vault dev, crear la llave `vectra-registry-checkpoint` (Ed25519, no exportable) y agregar el método `kubernetes` con políticas por identidad (`registry-checkpoint`/`registry-archive` firman; `registry-verify-*` leen la llave pública), sembrado por `seed-vault.sh`.
- **Archivos:** `platform/kind/seed-vault.sh`, `platform/kind/vault_paths.py`, `platform/kind/tests/`, `install.md`.
- **Decisión:** sí. La ruta difiere `checkpoint` y `archive` de U3 (Pasos 11 y 12, EXT SECURITY-13). Solo entra si el usuario los reincorpora.
- **Unidad:** U3 (Pasos 11 y 12), condicional.
- **Comprobación:** `kubectl exec` del operador: `vault read transit/keys/vectra-registry-checkpoint` muestra `type ed25519` y `exportable false`.

### A10. Cerrar B5 en los documentos (sin cambio de código en U1)
- **Qué:** F46 ya cubre `staging-explainer` (`flows.yaml:191`) y está instalado. Basta con marcar B5 como resuelto en `ruta-demo/README.md` y `U3-U6.md`, y pedir a U6 que actualice la nota «Abierto» de INF-U6 §3.
- **Archivos:** `aidlc-docs/construction/plans/ruta-demo/README.md`, `U3-U6.md` (B5) y `aidlc-docs/construction/model-serving/infrastructure-design/infrastructure-design.md:53` (dueño U6).
- **Decisión:** no.
- **Unidad:** U4, en la validación real.
- **Comprobación:** `kubectl --context kind-vectra -n vectra-staging get networkpolicy allow-f46-staging-explainer-to-minio-egress` y `grep -n 'id: F46' platform/network/flows.yaml`.

### A11. Medición de memoria por pod
- **Qué:** no hay metrics-server, así que `kubectl top` no funciona. Para la medición por unidad que pide el README, documentar en `install.md` la consulta de Prometheus `sum by (namespace,pod) (container_memory_working_set_bytes{container!=""})` vía port-forward. Opcionalmente, agregar metrics-server solo en kind (unos 50 MiB). Agregarlo es un componente nuevo y lo decide el usuario.
- **Archivos:** `platform/runbooks/install.md`. Si se agrega metrics-server: `components.yaml` y su values de kind.
- **Decisión:** solo si se agrega metrics-server.
- **Unidad:** U3, la primera medición.
- **Comprobación:** `kubectl --context kind-vectra top pods -A`, o la consulta de PromQL.

### A12. `restore-drill` durante la demo (riesgo; decide el usuario)
- **Qué:** el CronJob semanal (domingo a las 02:00) arranca 2 clústeres efímeros y llama a `case-retention`, que la ruta difiere. Va a fallar (`RestoreDrillFailed`) y a pedir memoria. Opciones: dejarlo como está y aceptar el fallo, o suspenderlo en kind con un values. Lo segundo apaga una pieza, así que no se propone aquí.
- **Archivos:** `platform/restore-drill/cronjob.yaml:10` y, si se decide, un overlay de kind.
- **Decisión:** sí (EXT RESILIENCY-11/12, más B5 de U7–U9).
- **Unidad:** U8, por el Paso 16 diferido. Afecta a cualquier demo que dure un domingo.
- **Comprobación:** `kubectl --context kind-vectra -n vectra-restore-drill get cronjob restore-drill -o jsonpath='{.spec.suspend} {.status.lastScheduleTime}'`.

### A13. Persistir el límite de inotify del host
- **Qué:** `install.md:31` ya documenta el `sysctl`, pero «no sobrevive a un reinicio». Propuesta: indicar `/etc/sysctl.d/99-kind.conf` con `fs.inotify.max_user_instances=512` (y `max_user_watches`), y una comprobación previa en el runbook.
- **Archivos:** `platform/runbooks/install.md`.
- **Decisión:** no. Es documentación de operación; el cambio en el host lo hace el usuario.
- **Unidad:** todas. Es la causa probable de la caída de hoy.
- **Comprobación:** `sysctl fs.inotify.max_user_instances` devuelve 512 después de reiniciar.

### A14. Vault dev se pierde en cada reinicio (riesgo de la demo; decide el usuario)
- **Qué:** con Vault en modo dev (`operators/vault-kind.yaml:1-3`), cada reinicio del host o del pod obliga al runbook completo y cambia todas las claves. Para el día de la demo hay dos opciones:
  - aceptarlo y ensayar el runbook;
  - pasar Vault de kind a almacenamiento persistente (`file`/`raft`, con unseal manual). Es un cambio de INF-U1-10.
- **Archivos:** `platform/operators/vault-kind.yaml`, `platform/kind/seed-vault.sh`, `install.md`.
- **Decisión:** sí (INF-U1-10).
- **Unidad:** todas. Se nota más en U12 (ensayo general).
- **Comprobación:** reiniciar `vault-0` y comprobar que `kubectl get externalsecrets -A` sigue en `True`.

---

## Bloqueos nuevos que no están en el README

1. **El clúster no funciona hoy** (§0): reinicio del host, `linkerd-cni` caído por inotify y Vault vacío. Toda U1 de datos y de observabilidad está `Unknown` (A0, A13 y A14).
2. **Las excepciones de Kyverno están desactivadas** (`--enablePolicyException=false`). RD1 no basta con crear el `PolicyException` (A1).
3. **`check-chart` (conftest) rechaza kind-demo** aunque Kyverno lo admita: `hpa.rego` y `platform.rego` también necesitan la exención (A2).
4. **La plantilla de CNPG no admite instancias por base**, y con 2 instancias `maxSyncReplicas: 2` es inválido. Además, `test_kind_profile.py` fija «todas con 1 instancia» (A3).
5. **El presupuesto de 8 GiB de T18 no alcanza** para U3–U11 en kind-demo (≈ 10,4–10,9 GiB de requests), y el host ya tiene la swap llena (A4).
6. **La siembra de Vault no cubre los `ExternalSecret` de las unidades** y generaría llaves ES256, JWKS y TOTP inválidos (A7).
7. **Grafana sin OIDC, subruta ni embebido:** el iframe de U10, el dashboard de U11 y el paso 13 del guion no funcionan (A8). Ya estaba en CANDIDATAS, pero no como bloqueo de la ruta.
8. **`restore-drill` va a fallar cada domingo** con U8 Paso 16 diferido, y consume memoria (A12).
9. **B5 está resuelto en el código**: solo queda desactualizado el texto (A10).
10. **El `PolicyException` v2 de Kyverno está *deprecated***, y la exención en `vectra-serving` depende de que KServe propague las etiquetas, algo sin verificar (A1).
