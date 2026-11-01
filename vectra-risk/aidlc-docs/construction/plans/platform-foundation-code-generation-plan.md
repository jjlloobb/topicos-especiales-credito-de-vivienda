# Plan de tareas (Code Generation Part 1) — U1 `platform-foundation`

**Este plan es la única fuente de verdad para generar el código de U1.**

> **Estado (2026-10-31):** Code Generation Part 2 en curso; P17 de `cross-unit-review5-followup-questions.md` levantó la restricción para U0 y U1. Una casilla marcada significa que su comando de aceptación corrió y pasó. Ver §5.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U1 `platform-foundation`: la base de Kubernetes, sin lógica de negocio |
| Historias (dueña) | US-604 (base de red y egress), US-605, US-606, US-607, US-608, US-610 |
| Ubicación | `vectra-risk/platform/` y `vectra-risk/vectra-risk-gitops/`, en el monorepo |
| Datos propios | La infraestructura de las bases; los esquemas son de cada unidad |
| Depende de | U0 (puerto 8081, métricas y logs del middleware; `verify_chain` llega con U3 y la CLI `case-retention` con U8) |
| Lo consumen | Todas las unidades que despliegan (`construction/shared-infrastructure.md`) |

**Diseño de entrada:**
- NFR Requirements: `construction/platform-foundation/nfr-requirements/` (NFR-U1-01..44).
- NFR Design: `construction/platform-foundation/nfr-design/` (P-U1-01..12).
- Infrastructure Design: `construction/platform-foundation/infrastructure-design/` (INF-U1-01..10).
- Inventario: `inception/application-design/component-dependency.md` (F01–F124, K01–K14 y K16–K21, X01–X10; precisado el 2026-10-08: el inventario creció con los Infrastructure Design de U2, U3, U4, U7 y U8).

### Cómo se cumple AUTONOMIA-01 en este plan

AUTONOMIA-01 prohíbe aplicar cambios a un clúster sin aprobación humana, **incluido el
clúster de desarrollo** usado durante CONSTRUCTION. Por eso las verificaciones de este plan
son de dos clases:

| Clase | Qué incluye | Quién la ejecuta |
|---|---|---|
| **Estática** | `helm lint`/`template`, `kyverno test`, `conftest`, `promtool`, generadores con `--check`, `actionlint`, `kubectl diff` (solo lectura) | CI, de forma autónoma |
| **En kind (con aprobación)** | Instalación, simulacros de zona y de restore, pruebas de conectividad y de admisión | **Un operador humano**, después de un PR aprobado (Paso 19), siguiendo el runbook; adjunta la evidencia al PR |

Cuando NFR Requirements, NFR Design o Infrastructure Design dicen «verificación en kind»,
se refieren a la segunda clase. Ningún workflow de CI aplica manifiestos: lo impide
`forbidden-steps.yml` (Paso 17).

### Estructura de destino

```text
vectra-risk/platform/
|-- Makefile                      # check (todas las verificaciones estáticas)
|-- kind/                         # cluster.yaml (1 cp + 4 workers, 2 zonas), calico, registry
|-- network/                      # flows.yaml, generate.py, generated/, tests/
|-- mesh/                         # values de Linkerd y jerarquía de cert-manager
|-- namespaces/                   # chart de namespaces: PSA, vectra.io/mesh + anotación de Linkerd (Paso 5)
|-- policies/                     # Kyverno (políticas + tests), PSA, PriorityClasses, cuotas
|-- data/                         # CloudNativePG (operador + 4 Cluster), MinIO, backups
|-- secrets/                      # ESO, ClusterSecretStore por entorno, Vault (kind)
|-- observability/                # values, PrometheusRules + tests, dashboards
|-- restore-drill/                # CronJob, RBAC K12, script
|-- rbac/verification-operator/   # K16: ClusterRole de nodes y Role por namespace, solo kind y staging (pendientes posteriores al cierre, 2026-10-10)
|-- runbooks/                     # _template.md, coe-template.md, uno por alerta, operación
|-- docs/                         # criticality.md, capacity.md, install.md
`-- tests/                        # pruebas de políticas, de reglas, de estructura

vectra-risk/.github/workflows/    # reutilizables: tests, supply-chain, evidence, forbidden-steps, policies

vectra-risk-gitops/
|-- apps/{kind,staging,prod}/root.yaml
|-- apps/{env}/<componente>.yaml  # una Application por componente, con wave
`-- envs/{kind,staging,prod}/     # values por entorno
```

---

## 2. Pasos

### Bloque A — Estructura

- [x] **Paso 1 — Esqueleto de `platform/` y de `vectra-risk-gitops`**
  - Directorios de §1, `platform/Makefile` con el objetivo `check`, `.github/pull_request_template.md` con la sección obligatoria «Rollback» (NFR-U1-44).
  - **Aceptación**: `make -C platform check` existe y termina en 0 sobre el esqueleto; `test -f vectra-risk-gitops/apps/kind/root.yaml`.

- [x] **Paso 2 — Configuración de kind**
  - `platform/kind/cluster.yaml`: 1 control-plane + 4 workers con `topology.kubernetes.io/zone` (`zone-a` ×2, `zone-b` ×2) y CNI por defecto deshabilitado (para Calico). Cifrado de Secrets en etcd (`EncryptionConfiguration`). Registro local `kind-registry` y `cloud-provider-kind`.
  - Solo archivos de configuración: crear el clúster es parte del Paso 19.
  - Diseño: INF-U1-01, 04, 05, 09; NFR-U1-24.
  - **Aceptación**: `python platform/tests/test_kind_config.py` (4 workers, 2 zonas, `disableDefaultCNI: true`, cifrado de etcd configurado).

### Bloque B — Red y malla

- [x] **Paso 3 — Inventario de flujos y generador**
  - `network/flows.yaml` con **todos** los flujos de `component-dependency.md` (F01–F124, incluidos F119–F121 del seguimiento de la quinta revisión, y F112–F118 de la cuarta revisión de coherencia entre unidades, 2026-10-31; F90–F105 de U2, U3, U4 y U8, F106 del CronJob de bias de U9 hacia el Pushgateway, F107 de `registry-aggregator` y F108 del Job de reset de U3; F109 (Grafana → Alertmanager, silencios), F110 (Job y CronJob de permisos de carpetas de Grafana) y F111 (`x06-probe`, solo kind) (pendientes posteriores al cierre, 2026-10-10); F09 con `enabled: false`; F22 admite `enabled: false` **solo en kind**, para el PR de RT-3, y una prueba lo rechaza en staging y producción (quinta revisión de coherencia entre unidades, 2026-10-31); quinta revisión del FD de U9, 2026-10-10), cada uno con origen, destino (namespace + ServiceAccount), puerto, `target_port` si difiere (seguimiento de la quinta revisión de coherencia, 2026-10-31), dirección e ID; `network/forbidden.yaml` con X01–X10. **F27** (`POST /v1/models/{id}/freeze`) tiene como origen **solo** el ServiceAccount `bias-monitoring-job` de los pods del CronJob de U9, no el servicio HTTP `bias-monitoring-service` (INF-U9-04; revisión del FD de U10, 2026-10-10, B13).
  - `flows.yaml` admite un origen **externo** (`origin: external`, fuera del clúster) para los flujos que entran por el gateway desde fuera, como F01 y F07 (el simulador de U12 desde la estación del operador): `generate.py` no crea `NetworkPolicy` de salida para ese origen, solo la de entrada del gateway, y la suite de conectividad prueba F07 desde fuera (pendientes posteriores al cierre, 2026-10-10).
  - `network/generate.py`: deny-all por namespace, un allow por flujo, DNS como única excepción común, un egress a la API de Kubernetes por cada binding K con pod (sin K09 ni K16; cuarta revisión de coherencia entre unidades, 2026-10-31), `Server` + `AuthorizationPolicy` de Linkerd y la suite de conectividad (un caso permitido y uno bloqueado por flujo; X01–X10 como casos bloqueados; para F27, el permitido sale del pod del CronJob y el bloqueado, de `bias-monitoring-service`; revisión del FD de U10, 2026-10-10, B13; bloqueados de U10: `console-spa` → cualquier servicio de `vectra-app`, `console-bff` → `vectra-data` y `console-bff` → `vectra-serving`, INF-U10-04, Infrastructure Design de U10, 2026-10-10; de U12: F07 desde fuera del clúster por el gateway (sin `channel-simulator` en `vectra-mock`), F111 (`x06-probe` → `registry-db-rw`) solo en kind, el selector de F27 por `vectra.io/workload: bias-monitoring-job` que admite los pods de `x04-probe` (prueba de `generate.py`), y el binding K16 solo en kind y staging (revisión del Infrastructure Design de U12, 2026-10-10), Infrastructure Design de U12, 2026-10-10; de U11: `product-metrics` → `case-service` y `governance-service` bloqueados, un pod que no es Prometheus → 8081 de `product-metrics` bloqueado, y `/readyz` del kubelet → 200 con el `Server` de Linkerd aplicado, INF-U11-04, Infrastructure Design de U11, 2026-10-10).
  - Diseño: NFR-U1-20; P-U1-01, P-U1-02; INF-U1-06. Historia: US-604.
  - **Aceptación**:
    - `python platform/network/generate.py --check` (los manifiestos versionados coinciden con los generados);
    - `pytest platform/network/tests` (todo ID de `component-dependency.md` aparece en `flows.yaml`, con una prueba que extrae los IDs del Markdown, sin un rango fijo, así que también cubre los flujos que agreguen las unidades siguientes; `vectra-restore-drill` tiene exactamente F75, F80, F83, F87, F114, F98 o F99 según el entorno, F118 solo en kind y el egress de K12; un ServiceAccount sin binding K no llega a la API, y `governance-service` sí, con K01; cuarta revisión de coherencia entre unidades, 2026-10-31).

- [x] **Paso 4 — Linkerd y cert-manager**
  - Values de Linkerd: HA, `linkerd-cni`, `default-inbound-policy: deny` en los namespaces de Vectra, anotación de sidecar nativo en `vectra-restore-drill` (P-U1-05).
  - cert-manager: trust anchor de 1 año, issuer intermedio de 48 h, `Certificate` del borde y de PostgreSQL (90 días, renovación a los 60).
  - Diseño: P-U1-02, 03, 06; NFR-U1-21, 22.
  - **Aceptación**: `helm template` de Linkerd y cert-manager con los values de prod + `conftest test` (HA = 3 réplicas, CNI activo, duraciones y renovaciones esperadas, anotación de sidecar nativo presente en `vectra-restore-drill`).

### Bloque C — Políticas y recursos

- [x] **Paso 5 — Políticas de Kyverno y PSA**
  - Políticas:
    - `verify-images`: firma Cosign y registro permitido por entorno;
    - `disallow-latest`;
    - `require-run-as-non-root`, `disallow-privileged`, `disallow-host-path`, `require-ro-rootfs`;
    - `require-resources`, `require-priority-class`, `require-spread-and-pdb`, `require-hpa-bounds` (admite un Deployment sin HPA solo con la anotación `vectra.io/hpa-exempt` no vacía, `replicas ≥ 2` y PDB; NFR-U1-12; precisado el 2026-10-10 por U9 NFR Requirements). Alcance de `require-spread-and-pdb` y `require-hpa-bounds`: `vectra-app`, `vectra-edge`, `vectra-identity`, `vectra-serving` y `vectra-mock`; `vectra-observability` queda fuera (seguimiento de la quinta revisión de coherencia, 2026-10-31);
    - `restrict-loadbalancer` (solo el api-gateway), `disallow-plain-secrets`, `disallow-argocd-auto-sync` (cubre también la Application `decision-registry-rebuild` de U3);
    - no hay `restrict-manual-jobs`: se descartó con K15. Los Jobs de reconstrucción de U3 los crea Argo CD desde la Application `decision-registry-rebuild` tras un PR y un sync manual (revisión del FD de U10, 2026-10-10, B13);
    - `require-criticality-label`, `disallow-rbac-wildcards`;
    - `add-native-sidecar-to-jobs` (**mutación**, P-U1-05): agrega la anotación del sidecar nativo de Linkerd al pod template de todo Job o CronJob de un namespace con la etiqueta `vectra.io/mesh: enabled`, incluidos los que crea CloudNativePG, y nunca rechaza. Selecciona por esa etiqueta porque Kyverno solo ve etiquetas, y la anotación `linkerd.io/inject: enabled` no lo es (cuarta y séptima revisión del FD de U9; redacción en la octava revisión del FD de U9, 2026-10-10).
  - **Chart `platform/namespaces`** (octava revisión del FD de U9, 2026-10-10): crea cada namespace de Vectra con la etiqueta de PSA `restricted`, la etiqueta `vectra.io/mesh: enabled` y la anotación `linkerd.io/inject: enabled` en los mallados (siempre las dos juntas), y la anotación del sidecar nativo; los values listan qué namespaces están mallados: exactamente los de P-U1-14 (revisión del Infrastructure Design de U10, 2026-10-10).
  - Etiquetas de PSA `restricted` por namespace. Kyverno en HA con `failurePolicy: Fail` y exclusiones de `kube-system`, `kyverno` y `linkerd`.
  - Diseño: NFR-U1-01, 04, 12, 25, 27, 43; P-U1-05, 06, 09; INF-U1-05, 09. Historias: US-605, US-606, US-607.
  - **Aceptación**: `kyverno test platform/policies/`, con un caso que pasa y uno que falla por política. Casos nombrados (revisión del NFR Requirements de U9, 2026-10-10):
    - Grafana y Pushgateway con 1 réplica en `vectra-observability` → admitidos, y el mismo Deployment en `vectra-app` → rechazado (seguimiento de la quinta revisión de coherencia, 2026-10-31);
    - `require-hpa-bounds`: Deployment sin HPA y sin `vectra.io/hpa-exempt` → rechazado; con la anotación, 2 réplicas y PDB → admitido; con la anotación y 1 réplica → rechazado;
    - `add-native-sidecar-to-jobs`: CronJob de `vectra-app` sin la anotación → admitido con la anotación agregada; Job `join` de CloudNativePG en `vectra-data` (con `ownerReference` a un `Cluster`) → admitido con la anotación, nunca rechazado; Job hook de `keycloak-config-cli` y CronJob `realm-drift` en `vectra-identity`, y un Job en `vectra-mock` → admitidos con la anotación; Job en un namespace sin la etiqueta `vectra.io/mesh` → sin cambios;
    - **binding K16** (U12 INF-U12-03; revisión del Infrastructure Design de U12, 2026-10-10): `platform/rbac/verification-operator/` con el `ClusterRole` de `nodes` y un `Role` por namespace según la tabla de INF-U12-03, renderizado **solo** con los values de kind y staging; `conftest` sobre el render de producción → sin K16; `kyverno test` de `disallow-rbac-wildcards` con K16 → admitido (no tiene comodines); la regla `verification-operator-verbs` de **`conftest`** (no `disallow-rbac-wildcards`, que solo mira comodines) rechaza un K16 con cualquier verbo fuera de `get`, `list`, `watch` y `create` sobre `pods/portforward` o `selfsubjectaccessreviews`, con fixtures que agregan `delete` o `pods/exec` → rechazados (pendientes posteriores al cierre, 2026-10-10);
    - **sujeto de K16** (pendientes posteriores al cierre, 2026-10-10): el grupo `vectra-verification-operators`. En kind, el kubeconfig del operador es un certificado de cliente con ese grupo en `O=` (lo emite el runbook de instalación de kind); en staging, un grupo del proveedor de identidad del banco para la API de Kubernetes, administrado fuera de Vectra. Ningún `ServiceAccount` está en K16;
    - `require-hpa-bounds` con `product-metrics` (2 réplicas fijas, `vectra.io/hpa-exempt` con justificación y PDB) → admitido; sin la anotación → rechazado (pendientes posteriores al cierre, 2026-10-10);
    - chart de namespaces: todo namespace con la anotación `linkerd.io/inject: enabled` tiene la etiqueta `vectra.io/mesh: enabled`, y viceversa; la lista mallada es exactamente la de P-U1-14;
    - `add-native-sidecar-to-jobs`: un Job en `vectra-edge` y otro en `vectra-observability` → admitidos con la anotación (revisión del Infrastructure Design de U10, 2026-10-10);
    - `require-hpa-bounds`: `console-spa` con la exención, 2 réplicas y PDB → admitido; un `InferenceService` de `vectra-staging` con 1 réplica → admitido (fuera del alcance); uno de `vectra-serving` con 1 réplica → rechazado; uno de `vectra-serving` con 1 réplica, `vectra.io/serving-state: inactivo` y `vectra.io/hpa-exempt` → admitido; el mismo con `serving-state: activo` → rechazado (segunda revisión del Infrastructure Design de U10, 2026-10-10).

- [x] **Paso 6 — PriorityClasses, cuotas y límites**
  - Las 4 PriorityClasses de P-U1-09; `ResourceQuota` y `LimitRange` por namespace (máximo del HPA + 30 %), **con el proxy de Linkerd** de P-U1-14 en cada pod mallado (revisión del Infrastructure Design de U10, 2026-10-10).
  - `console-spa` (U10) es el segundo Deployment con `vectra.io/hpa-exempt` (2 réplicas fijas, NFR-U10-12), y `product-metrics` (U11 INF-U11-01) el tercero (pendientes posteriores al cierre, 2026-10-10).
  - **Pushgateway** (P-U1-13): 1 réplica con PVC de persistencia y `--persistence.interval=1m`; `Server` y `HTTPRoute` de Linkerd por identidad y método.
  - La cuota de `vectra-app` y la de `vectra-mock` suman los aportes declarados por las unidades: INF-U7-02 (U7, recalculado con el proxy y los pods del rollout: requests ≈ 6,37 CPU / 4,91 GiB y limits ≈ 27,3 CPU / 11,38 GiB; revisión de coherencia entre unidades, 2026-10-10), INF-U8-05 (U8, recalculado con el proxy y los pods del rollout: `vectra-app` ≈ 6,44 CPU / 5,3 GiB de requests y ≈ 29,9 CPU / 12,35 GiB de limits; `vectra-mock` 0,59 / 2,93 CPU y 328 / ≈ 998 MiB, con el limit de 128 MiB del proxy, pendientes consolidados, 2026-10-10; pendientes posteriores al cierre, 2026-10-10) e INF-U9-01 (U9, con el sidecar y el 30 % de margen ya incluido; ver la viñeta siguiente), INF-U3-03 (U3: requests ≈ 6,70 CPU / 5,91 GiB y limits ≈ 29,25 CPU / 13,49 GiB, con el servicio, los CronJobs, la migración y un Job de reconstrucción a la vez) e INF-U4-01 (U4: requests ≈ 3,71 CPU / 2,99 GiB y limits ≈ 16,25 CPU / 6,99 GiB) (revisión de coherencia entre unidades, 2026-10-10; antes «los de U3 y U4 cuando existan»), y el de U11 (NFR-U11-14: 3 pods en el peor momento, 2 réplicas y 1 de `maxSurge`, con el proxy y el 30 % de margen ya incluido; requests ≈ 0,78 CPU / 1,05 GiB y limits ≈ 3,9 CPU / 2,44 GiB; NFR Requirements de U11, 2026-10-10; pendientes posteriores al cierre, 2026-10-10) (precisado el 2026-10-08, revisión del Infrastructure Design de U8).
  - La cuota de `vectra-app` suma también los Jobs de reconstrucción de U3, `registry-aggregator-rebuild-<runId>` y `registry-aggregator-reset-<runId>`, de la Application aparte `decision-registry-rebuild` (INF-U3-03), mientras corren (revisión del NFR Requirements de U9, 2026-10-10; revisión del FD de U10, 2026-10-10, B13). El aporte de U9 se suma **con** el sidecar de Linkerd y el 30 % de margen ya incluido, para 4 pods en el peor momento (2 del servicio, 1 de su `maxSurge` y 1 del CronJob) (INF-U9-01: requests ≈ 1,04 CPU / 0,75 GiB y limits ≈ 5,2 CPU / 1,95 GiB; antes 3 pods sin el del rollout; pendientes posteriores al cierre, 2026-10-10), porque la cuota cuenta el sidecar nativo; los recursos del proxy son los de P-U1-14, que coinciden con los usados en INF-U9-01 e INF-U10-01 (revisión del FD de U10, B8, y del Infrastructure Design de U10, 2026-10-10).
  - La cuota de `vectra-app` suma el BFF de U10 y la de `vectra-edge`, la SPA de U10, con el sidecar (INF-U10-01, con los pods del rollout: requests ≈ 3,19 CPU / 2,4 GiB y 0,78 CPU / 0,26 GiB; limits ≈ 13,7 CPU / 5,7 GiB y 3,64 CPU / 0,97 GiB; segunda revisión del Infrastructure Design de U10, 2026-10-10). Regla general: cada unidad dimensiona su aporte con los pods del peor momento, incluido el `maxSurge` de su rollout.
  - La cuota de `vectra-staging` suma un `model-validation-job` (500m / 1 GiB de requests y 2 CPU / 4 GiB de limits, más el proxy; quinta revisión de coherencia entre unidades, 2026-10-31), los `InferenceService` de staging de U6 y el predictor de la versión activa de U4 INF-U4-05 durante una `source_comparison` (quinta revisión del FD de U9, 2026-10-10).
  - La cuota de `vectra-serving` usa el aporte de U6 (INF-U6-01): requests ≈ 17,16 CPU / 14,86 GiB y limits ≈ 59,8 CPU / 32,2 GiB, con el proxy y el 30 %. Caben en el pool `general`, con su mínimo de 4 nodos por zona (INF-U1-01; cuarta revisión de coherencia entre unidades, 2026-10-31).
  - La cuota de `vectra-data` usa los recursos de INF-U1-02: requests ≈ 18,98 CPU / 68 GiB y limits ≈ 44,2 CPU / 137,8 GiB, con el proxy y el 30 % (seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - La cuota de `vectra-edge` suma el aporte de U2: requests ≈ 5,72 CPU / 3,64 GiB y limits ≈ 25,35 CPU / 9,18 GiB; con la SPA, ≈ 6,5 CPU / 3,9 GiB y ≈ 28,99 CPU / 10,15 GiB. La de `vectra-identity`: requests ≈ 4,68 CPU / 7,68 GiB y limits ≈ 20,15 CPU / 16,25 GiB (INF-U2-06; seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - Los Jobs de prueba de U12 en kind (`x04-probe`, `x06-probe`, `rt5-demo`) no tienen aporte propio: los absorbe el margen del 30 % (revisión de coherencia entre unidades, 2026-10-10).
  - Diseño: NFR-U1-13; P-U1-09; INF-U3-03; INF-U4-01; INF-U7-02; INF-U8-05; INF-U9-01; INF-U10-01; INF-U4-05; NFR-U11-14; INF-U6-01.
  - **Aceptación**: `conftest test platform/policies/quotas/` (todo namespace de Vectra tiene cuota y límites); `kyverno test` del caso «Pod sin `priorityClassName` → rechazado».

### Bloque D — Datos y secretos

- [x] **Paso 7 — CloudNativePG y los 4 clusters**
  - Operador (2 réplicas). Por cluster:
    - 3 instancias, anti-afinidad obligatoria por nodo y reparto preferido por zona;
    - `minSyncReplicas: 1`, `maxSyncReplicas: 2`; `syncReplicaElectionConstraint` por `topology.kubernetes.io/zone`, para que la síncrona esté en otra zona (US-605; seguimiento de la quinta revisión de coherencia, 2026-10-31);
    - `walStorage` y tamaños de INF-U1-02;
    - `max_connections` inicial;
    - TLS con certificados de cert-manager;
    - toleration del pool `data`;
    - recursos del pool `data` de INF-U1-02;
    - `PriorityClass` `vectra-critical`.
    - `managed.roles` con los roles de `component-dependency.md` §4 y su `passwordSecret`, con un `ExternalSecret` en `vectra-data` y otro en el namespace de cada consumidor (INF-U1-02; cuarta revisión de coherencia entre unidades, 2026-10-31);
    - `skip-inbound-ports: "8000"` en las instancias y el `Server` de 5432 con `NetworkAuthentication` para F80 (P-U1-02; cuarta revisión de coherencia entre unidades, 2026-10-31).
  - Backups con Barman Cloud hacia el S3 fuera del sitio (F70): `archive_timeout: 60s`, `ScheduledBackup` diario, `retentionPolicy: 30d`, backup mensual con prefijo `monthly/` (lifecycle de 12 meses en el bucket) y object lock en los buckets de `registry-db`.
  - Diseño: NFR-U1-02, 05, 06, 23 (backups cifrados del lado del servidor); INF-U1-02, 03; P-U1-08. Historias: US-605, US-608.
  - **Aceptación**: `helm template` + `conftest test platform/data/` (3 instancias, sync, `archive_timeout = 60s`, retención de 30 días, WAL separado, `sslmode` exigido, toleration y prioridad; `syncReplicaElectionConstraint` por zona; cada rol de §4 en `managed.roles`, con una prueba que los extrae del Markdown; cuarta revisión de coherencia entre unidades, 2026-10-31). En kind (Paso 19): conmutación por error con NetworkPolicy y políticas de Linkerd aplicadas.

- [x] **Paso 8 — MinIO**
  - Modo distribuido con 4 pods en el pool `data` (2 por zona); buckets `model-store`, `validation-datasets`, `loki` (versionado + object lock de 90 días) y `tempo` (lifecycle de 7 días); usuarios de solo lectura para KServe y validación. **Solo en kind**: `vectra-registry-checkpoints`, `vectra-registry-archive` y `vectra-model-archive` con object lock (F118). Tráfico entre pods por F115 (cuarta revisión de coherencia entre unidades, 2026-10-31).
  - Diseño: INF-U1-03; NFR-U1-30.
  - **Aceptación**: `helm template` + `conftest test platform/data/minio/` (4 réplicas, reparto por zona, buckets con la configuración esperada).

- [x] **Paso 9 — External Secrets y Vault (kind)**
  - ESO; `ClusterSecretStore` por entorno (Vault en kind, la bóveda del banco en staging/prod con F74); Vault en modo dev solo para kind; binding K11 limitado a los namespaces de Vectra.
  - Diseño: NFR-U1-24; INF-U1-10.
  - **Aceptación**: `kyverno test` de `disallow-plain-secrets`; `grep -rL "kind: Secret" vectra-risk-gitops/` devuelve todos los archivos (ningún Secret plano); `conftest` sobre el RBAC de ESO (sin comodines, solo los namespaces declarados).

### Bloque E — Observabilidad y operación

- [x] **Paso 10 — Stack de observabilidad**
  - CRDs de Prometheus Operator en la wave 0 (cuarta revisión de coherencia entre unidades, 2026-10-31), Prometheus (2 réplicas, 30 días), Alertmanager (3 réplicas con gossip F116, receptor F72 por `severity`, `Watchdog` cada 5 min), Loki (MinIO, `retention_enabled: false`, retención por lock y lifecycle), Tempo (7 días), OTel Collector, Grafana Alloy, Pushgateway (F87, F88, F106, F112 y F113; alerta `PushgatewayDown`) y Grafana.
  - **Permisos de carpetas de Grafana** (FD de U11, 2026-10-10, U11 BR-U11-13 y U9 INF-U9-05): `platform/observability/grafana/folder-permissions.yaml` (carpetas `Vectra / Sesgo` → equipos `cro` y `cumplimiento`; `Vectra / Producto` → `cro`, `cumplimiento` e `ingeniero_riesgo`; carpeta de operación → `operacion` con `Edit` (Infrastructure Design de U11, 2026-10-10)), aplicado por el Job idempotente `grafana-folder-permissions` (hook `PostSync` de la Application de observabilidad, F110) que **crea las carpetas con UID fijo si no existen**, porque los dashboards de U9 y U11 llegan en la wave 5 (cuarta revisión de coherencia entre unidades, 2026-10-31), y quita los permisos de rol de esas carpetas y deja solo los de equipo; CronJob horario en modo comprobación que publica `vectra_grafana_folder_permissions_drift` al Pushgateway (F113) (alerta `GrafanaFolderPermissionsDrift`, SEV3). Token de una cuenta de servicio de Grafana por ESO.
  - Diseño: NFR-U1-30, 31, 34; INF-U1-07, 08; P-U1-07. Historia: US-610.
  - **Aceptación**: `helm template` + `conftest test platform/observability/` (retenciones, sin remote-write, receptor F72 configurado, Loki sin compactor de borrado); `uv run pytest platform/tests/test_grafana_folder_permissions.py` con un Grafana de Testcontainers (carpeta inexistente → el Job la crea y un dashboard posterior queda dentro con esos permisos; cuarta revisión de coherencia entre unidades, 2026-10-31; carpeta con permisos de rol → el Job los quita; segunda corrida → sin cambios; comprobación con deriva → métrica 1); en kind (Paso 19), los usuarios de U2: `ingeniero-1` → `Vectra / Producto` 200 y `Vectra / Sesgo` 403, `operacion-1` y `analista-1` → 403 en las dos, `cro-1` y `cumplimiento-1` → 200 en las dos (FD de U11, 2026-10-10).

- [x] **Paso 11 — Reglas, SLO y runbooks**
  - `PrometheusRule` con todas las alertas de `logical-components.md` §3 **salvo** `AuthDeniedBurst`, que es de U2 (P-U2-09), las reglas de grabación del SLO y los burn rates (P-U1-11); `promtool` comprueba que ningún `alertname` de U1 aparece también en las reglas de U2 (segunda revisión de coherencia entre unidades, 2026-10-10).
  - `FailClosedPersistente` = `max(vectra_cases_failclosed_persistent) > 0` con `for: 1m` (gauge de U8; P-U1-11), no sobre el SLI de recomendación usable (tercera revisión de coherencia entre unidades, 2026-10-10).
  - Runbook por alerta con la plantilla de P-U1-10; `coe-template.md`.
  - Incluye `GrafanaFolderPermissionsDrift` (Job y CronJob de permisos de carpetas, Paso 10) con su runbook `grafana-folder-permissions-drift`, que explica cómo reaplicar el Job con un sync de la Application de observabilidad (Infrastructure Design de U11, 2026-10-10).
  - Diseño: NFR-U1-32; P-U1-10, 11. Historia: US-610.
  - `PostgresVolumeUsageHigh` con una regla de ausencia por `Cluster`, de la forma `(count(...) or vector(0)) < 6` según INF-U1-02, y no un `absent()` común a los cuatro (precisado el 2026-10-08, revisión del Infrastructure Design de U8).
  - **Aceptación**: `promtool test rules platform/observability/rules/tests/*.yaml` (cada alerta se dispara con series sintéticas; `FailClosedPersistente`: gauge en 1 en dos réplicas → una sola alerta tras 1 min, gauge en 0 → no dispara, razón usable baja con el gauge en 0 → no dispara (tercera revisión de coherencia entre unidades, 2026-10-10); el caso de `PostgresVolumeUsageHigh` quita las series de un solo `Cluster`, `case-db`, con los otros tres reportando, y debe disparar) y `python platform/tests/test_runbooks.py` (toda regla tiene `severity` válida y un `runbook_url` hacia un archivo existente).

- [x] **Paso 12 — Dashboards como código**
  - Dashboards de seguridad, resiliencia, operación y SLO en JSON. La carpeta de operación (equipo `operacion`) incluye el panel de operación de U11 (NFR-U11-41: ciclo, entradas leídas, recomputación diaria y breaker hacia U3; NFR Requirements de U11, 2026-10-10).
  - Diseño: NFR-U1-33.
  - **Aceptación**: `python platform/tests/test_dashboards.py` (JSON válido, fuentes de datos por UID, sin consultas a métricas inexistentes en las reglas).

### Bloque F — Resiliencia

- [x] **Paso 13 — `restore-drill`**
  - CronJob semanal en `vectra-restore-drill` (prioridad `vectra-low`, sidecar nativo de Linkerd); script que crea el `Cluster` efímero, corre `verify_chain` (CLI de U3), empuja las métricas al Pushgateway (F87) y destruye el cluster; RBAC K12 con su egress a la API; `verify_chain` llega al cluster por F114 y lee la llave pública por F98 o F99 (cuarta revisión de coherencia entre unidades, 2026-10-31); credencial de solo lectura para F75, limitada a los prefijos de `registry-db` y `case-db` en `vectra-backups` y al bucket `vectra-registry-checkpoints` (precisado el 2026-10-06, revisión del FD de U8: cubre la restauración de `case-db` sin un flujo nuevo).
  - Diseño: P-U1-05; NFR-U1-06, 07. Historia: US-608.
  - **Aceptación**: `helm template` + `conftest test platform/restore-drill/` (anotación de sidecar nativo, RBAC sin comodines, credencial distinta de la de F70 y cuya política de bucket solo permite lectura sobre los prefijos de `registry-db` y `case-db` y `vectra-registry-checkpoints`); `pytest platform/restore-drill/tests` (el script termina con error si `verify_chain` no devuelve «íntegra»).
  - **Dependencia**: la CLI `verify_chain` llega con U3. Hasta entonces, el script usa una interfaz con un doble de prueba.
  - **Restauración de `case-db`** (precisado el 2026-10-06, revisión del FD de U8): segundo cluster efímero desde el backup de `case-db`, `case-retention` (CLI de U8; doble de prueba hasta que exista) y conteo de identificadores vencidos. `pytest platform/restore-drill/tests`: un conteo > 0 hace fallar el script y pone `vectra_restore_drill_retention_violations` > 0; `promtool test rules` de `RestoreDrillRetentionViolation` (SEV2) y la prueba de que tiene `runbook_url`.
  - Diseño adicional: NFR-U1-07 precisado; BR-U8-20.

- [x] **Paso 14 — Runbooks de operación**
  - `install.md` (incluida la suite de conformidad del CNI como paso previo, INF-U1-04), `zone-failover.md`, `site-restore.md`, `trust-anchor-rotation.md`, y `docs/criticality.md` y `docs/capacity.md`.
  - `install.md` incluye (pendientes posteriores al cierre, 2026-10-10):
    - **la espera de `product-metrics` en la wave 5**: su readiness exige una instantánea (U11 INF-U11-01), y cada réplica hace una pasada completa antes de quedar lista. Con el volumen esperado son minutos, pero con 10 veces el volumen la pasada puede durar hasta 75 min por réplica, y el rollout de las dos réplicas, una tras otra, hasta **≈ 2,5 h**. Argo CD no pasa a la wave 6 hasta que la wave 5 está `Healthy`. El runbook lo dice, explica cómo distinguir esta espera de una falla (`vectra_product_full_pass_in_progress = 1` y `vectra_product_entries_read_total` creciendo) y que con U3 caído la réplica queda lista enseguida;
    - la emisión en kind del certificado de cliente del operador de verificación con el grupo `vectra-verification-operators` (sujeto de K16) y la exportación de la CA del borde que usa U12.
  - Diseño: NFR-U1-01, 07, 08, 10; P-U1-03; INF-U1-04.
  - **Aceptación**: `python platform/tests/test_runbooks.py --operational` (los cuatro existen, siguen la plantilla y cada paso de verificación nombra un comando).

### Bloque G — GitOps

- [x] **Paso 15 — Argo CD y app-of-apps**
  - Argo CD (values); `AppProject` `vectra-{env}` por entorno (P-U1-12; seguimiento de la cuarta revisión de coherencia, 2026-10-31); `root.yaml` por entorno; una `Application` por componente con las waves 0–6 de P-U1-12; values por entorno (registro de imágenes, Git del espejo, StorageClass, tamaños).
  - Diseño: P-U1-12; INF-U1-01..03, 09; NFR-U1-23 (StorageClass cifrada por entorno), 43. Historia: US-607.
  - **Aceptación**: `kyverno test` de `disallow-argocd-auto-sync` sobre `vectra-risk-gitops/apps/`; `python platform/tests/test_waves.py` (cada Application tiene wave y el orden coincide con P-U1-12); `conftest` de los `AppProject` (ninguna Application con `project: default`, sin comodines en repositorios ni destinos; seguimiento de la cuarta revisión de coherencia, 2026-10-31).

- [x] **Paso 16 — Lint y render de todos los charts**
  - `helm lint` de todos los charts y snapshots de `helm template` por entorno, versionados para revisarlos en el PR.
  - Historia: US-605.
  - **Aceptación**: `make -C platform render && git diff --exit-code platform/rendered/`; `conftest test platform/rendered/prod/` (topologySpread por zona y PDB en todos los Deployments, como exige US-605; y la anotación del sidecar nativo **explícita** en el pod template de cada Job y CronJob renderizado, incluidos los Jobs de reconstrucción de U3, que se renderizan desde `decision-registry/chart-rebuild/` (Application aparte `decision-registry-rebuild`, wave 6; revisión del FD de U10, 2026-10-10, B13) con `--set monitoringRebuild.runId=test` en una variante del render (aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10), para que la mutación de Kyverno nunca cambie un recurso de Git; sexta revisión del FD de U9, 2026-10-10).

### Bloque H — CI

- [x] **Paso 17 — Workflows reutilizables**
  - `tests.yml` (con la semilla de PBT registrada), `supply-chain.yml` (Trivy, Syft, Cosign; falla con hallazgos críticos o altos sin excepción vigente), `evidence.yml` (`helm template` y `kubectl diff` contra un kind efímero del propio workflow, como artefactos del PR; seguimiento de la quinta revisión de coherencia, 2026-10-31), `forbidden-steps.yml` (falla si aparecen `kubectl apply`, `helm install`/`upgrade`, `terraform apply` o `argocd app sync`) y `policies.yml` (`kyverno test`, `promtool`, `conftest`, `actionlint`). Input `runner` parametrizado.
  - El workflow de U0 (`contracts.yml`) reemplaza su job provisional `pip-audit`/`npm audit` por `supply-chain.yml`.
  - Diseño: NFR-U1-26, 40..42. Historia: US-606.
  - **Aceptación**: `actionlint .github/workflows/*.yml`; `python platform/tests/test_forbidden_steps.py` (un workflow de fixture con `kubectl apply` hace fallar `forbidden-steps`, y un Dockerfile de fixture con `latest` hace fallar el CI, US-606; seguimiento de la quinta revisión de coherencia, 2026-10-31); `grep -L "secrets.KUBECONFIG" .github/workflows/*.yml` devuelve todos los archivos.

- [x] **Paso 18 — Resumen del código de U1**
  - `aidlc-docs/construction/platform-foundation/code/README.md`: componente → archivos → verificación → NFR/P/INF.
  - **Aceptación**: `python platform/tests/test_traceability.py` (cada NFR-U1-xx, P-U1-xx e INF-U1-xx aparece en algún archivo de `platform/` o de `vectra-risk-gitops/`).

### Bloque I — Verificación en kind (con aprobación humana)

- [ ] **Paso 19 — Puerta de aprobación e instalación en kind**
  - **Requisito previo**: un PR con los Pasos 1–18 aprobado por un humano. La aprobación queda registrada en el PR.
  - El **operador** crea el clúster kind (`kind create cluster --config platform/kind/cluster.yaml`), corre la suite de conformidad del CNI y sincroniza manualmente las waves 0–6 en Argo CD, siguiendo `runbooks/install.md`.
  - **Aceptación**: evidencia adjunta al PR: salida de la suite de conformidad, `argocd app list -o json` (todas `Synced`/`Healthy`, ninguna con `automated`), `linkerd check` y `kubectl get clusters.postgresql.cnpg.io -A`.

- [ ] **Paso 20 — Simulacros en kind**
  - El operador ejecuta, con evidencia:
    1. la suite de conectividad (permitidos y bloqueados, X01–X10);
    2. el rechazo de un Pod con `latest` y de otro sin firma;
    3. la autorización de Linkerd entre ServiceAccounts;
    4. el fallo de zona (drain de `zone-a`: bloqueo de escrituras, reclonado y tiempo medido, NFR-U1-03; Kyverno y Linkerd siguen admitiendo; el reclonado **crea su Job `join`**, que recibe la anotación del sidecar nativo por mutación y llega a `Complete`; cuarta revisión del FD de U9, 2026-10-10);
    4b. durante ese fallo de zona, `MinioWriteQuorumLost` dispara y los modelos ya desplegados siguen sirviendo (seguimiento de la quinta revisión de coherencia, 2026-10-31);
    5. el restore del sitio en un kind limpio (≤ 4 h, `verify_chain` «íntegra»);
    6. `restore-drill` manual (el Job llega a `Complete` y `restartPolicy: Always` en el proxy);
    7. el `Watchdog` recibido;
    8. las pruebas de readiness de P-U1-04 (`case-db` caída; explainability o governance caídos).
  - Los puntos 5, 6 y 8 dependen de U3, U7 y U8: aquí se marcan como pendientes, y su evidencia completa la entrega la sección `resilience` de U12, con `governance-db` y `registry-db` (BR-U12-08b; seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - Historias: US-604, US-605, US-608, US-610.
  - **Aceptación**: un archivo de evidencia por simulacro adjunto al PR, con comando, salida y resultado esperado contra el obtenido.

- [x] **Paso 21 — Prueba de carga: diferida**
  - NFR-U1-11 (20/s durante 15 min) necesita los servicios de U7 y U8 y el simulador de U12. La ejecuta U12 sobre esta plataforma; los máximos del HPA y `max_connections` se recalculan con su resultado: U12 los informa y un PR a los values de U1 los aplica (seguimiento de la quinta revisión de coherencia, 2026-10-31).
  - **Aceptación**: `grep -q "NFR-U1-11" aidlc-docs/construction/plans/system-verification-code-generation-plan.md` cuando exista ese plan (la verificación la hereda U12).

### Bloque J — Cierre

- [x] **Paso 22 — Repositorio, migraciones y frontend: N/A**
  - U1 no tiene capa de repositorio, migraciones (los esquemas son de cada unidad, F44) ni frontend.
  - **Aceptación**: `test ! -d platform/migrations && test ! -d platform/frontend`.

- [ ] **Paso 23 — Cierre de la unidad**
  - Verificación final de cumplimiento (RESILIENCY, SECURITY, AUTONOMIA).
  - **Aceptación**: `make -C platform check`, que corre en orden todas las verificaciones **estáticas** de los Pasos 2–18 y termina en 0. Las de kind (Pasos 19–20) se revisan como evidencia en el PR, no en `check`.

---

## 3. Trazabilidad

| Historia | Pasos |
|---|---|
| US-604 (base de red y egress) | 3, 19, 20 |
| US-605 (Helm multi-zona) | 5, 7, 8, 16, 19, 20 |
| US-606 (CI con evidencia) | 5, 17 |
| US-607 (Argo CD manual) | 5, 15, 19 |
| US-608 (backups y restore) | 7, 13, 20 |
| US-610 (observabilidad e incidentes) | 10, 11, 12, 20 |

| Diseño | Pasos |
|---|---|
| NFR-U1-01..08 (disponibilidad) | 5, 7, 13, 14, 20 |
| NFR-U1-10..13 (capacidad) | 5, 6, 14, 21 |
| NFR-U1-20..27 (seguridad) | 3, 4, 5, 7, 9, 15, 17 |
| NFR-U1-30..34 (observabilidad) | 10, 11, 12 |
| NFR-U1-40..44 (cambios y CI) | 1, 5, 15, 17 |
| P-U1-01..12 | 3, 4, 5, 6, 7, 10, 11, 13, 15, 20 |
| INF-U1-01..10 | 2, 3, 5, 7, 8, 9, 10, 14, 15 |

## 4. Cumplimiento de extensiones (plan de tareas U1)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Nada se aplica sin aprobación: CI solo hace verificaciones estáticas (`forbidden-steps.yml`, Paso 17); la instalación y los simulacros en kind los ejecuta un operador después de un PR aprobado (Pasos 19–20) |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación o una evidencia con comando |
| AUTONOMIA-03 | Cumple | `disallow-rbac-wildcards`; X01 en la suite de conectividad (Pasos 3, 5) |
| AUTONOMIA-05 | Cumple | Egress solo por `flows.yaml` (F70–F76), probado en el Paso 20 |
| RESILIENCY-01..15 | Cumple | Pasos 5–7, 10–14, 20; RESILIENCY-14 = C (simulacros documentados y ejecutados por el operador) |
| SECURITY-01/06/07/09/10/12/13/14 | Cumple | Pasos 3–5, 7, 9, 11, 17 |
| PBT | N/A en U1 | Sin código de aplicación; `tests.yml` ejecuta los PBT de las demás unidades con la semilla registrada |

## 5. Estado de la ejecución y desviaciones (2026-10-31)

`make -C platform check` corre pytest (`test_integration.py` incluida), `kyverno test`, las políticas contra todo lo renderizado en los namespaces de Vectra, promtool, conftest y actionlint. Resultado de la última corrida: §5, y `aidlc-docs/audit.md`.

### Pasos sin marcar

| Paso | Qué falta |
|---|---|
| 19, 20 | Los ejecuta un operador después de un PR aprobado (AUTONOMIA-01) |
| 23 | Su comando pasa; se marca cuando se cierren los pasos anteriores |

### Desviaciones

1. `vectra-risk-gitops/` vive dentro del monorepo, no en un repositorio propio; las rutas de las `Application` llevan el prefijo `vectra-risk/`.
2. Las `Application` se generan con `vectra-risk-gitops/generate.py` desde `components.yaml`.
3. Las aceptaciones `test_kind_config.py`, `test_dashboards.py` y `test_forbidden_steps.py` están reunidas en `platform/tests/test_platform.py` y `platform/tests/test_ci.py`. `test_runbooks.py`, `test_waves.py`, `test_links.py` y `test_traceability.py` son comandos propios, con los argumentos que citan los planes (`--section` de `test_traceability.py` aún no existe).
4. Los charts upstream se descargan a `platform/.charts/` (ignorado por Git) y se renderizan en `test_upstream_charts.py`; `platform/rendered/` versiona solo los charts y manifiestos propios.
5. En los Pasos 4, 6, 7, 8, 9 y 13, lo que la aceptación pedía a `conftest` lo comprueba pytest (`test_platform.py`, `test_upstream_charts.py`). `conftest` corre sobre `rendered/prod` y `apps/prod` con las reglas de `policies/rego/platform.rego`, que son menos.
6. Se agregaron F122 (Prometheus → kube-state-metrics) y K20: dos alertas de U1 necesitan esa fuente.
7. El Grafana real de Testcontainers corrió sobre Podman sin root: el usuario local no tiene acceso a `/var/run/docker.sock`. En CI se usa Docker.
8. El PDB se relaciona con el Deployment por `app.kubernetes.io/name`; un PDB con otro selector no cuenta.
9. `external-secrets` corre con `rbac.create: false`: el chart concede Secrets en todo el clúster, contra K11. Lo reemplaza `platform/secrets/eso-rbac-cluster.yaml`.
10. La firma no está en `supply-chain.yml`, que solo escanea: está en `sign-image.yml`, con llave (sin `id-token`), que llama quien publica la imagen (revisión de consistencia entre unidades, 2026-11-01). Los planes de las unidades que dicen «firmada por `supply-chain.yml`» se refieren a este par.
11. `kubectl diff` de `evidence.yml` solo evalúa tipos del núcleo de Kubernetes, de clúster o de un namespace que exista en el kind efímero: no se aplica nada, así que allí no hay CRDs ni namespaces de Vectra. Lo excluido queda en `evidence/kubectl-diff/resources/limits.txt`.

### Decisiones de la corrección de integración (2026-10-31, opción A)

10. **node-exporter apagado**, no exceptuado: necesita `hostNetwork` y `hostPath`, y ninguna regla, dashboard ni flujo del inventario lo usa. Es más estricto que la excepción con namespace propio; para recuperarlo hace falta esa excepción y un flujo nuevo.
11. Alloy lee los logs por la API (K13), sin `hostPath`.
12. Se apagaron el webhook de Prometheus Operator, las reglas por defecto de `kube-prometheus-stack`, los dashboards por defecto, el gateway y las cachés de Loki y las cachés de Tempo: requerían flujos fuera del inventario o alertas sin runbook.
13. Prometheus usa el token proyectado que el kubelet rota, sin `Secret` de larga vida.
14. La configuración de Alertmanager la arma External Secrets, porque lleva la URL del relay.
15. `add-priority-to-minio-job` agrega la prioridad al Job posterior de MinIO, por nombre: el chart no la admite.
16. Nuevos en el inventario: F123 (Job de MinIO), F124 (API → `trust-manager`) y K21 (`trust-manager`). Nuevos usuarios de MinIO: `loki-writer` y `tempo-writer`, cada uno limitado a su bucket.
17. `MinIO` se etiqueta con criticidad `high`; NFR-U1-01 no lo clasifica.

### Por confirmar

- **Imágenes de MinIO y mc:** `quay.io/minio`, `docker.io/minio` y `ghcr.io/minio` rechazan la consulta anónima; solo responde `cgr.dev/chainguard/minio`, de un tercero y solo con `latest`. Por defecto, `platform/data/minio/Dockerfile` compila desde los tags del código, pero **esa construcción nunca se ha ejecutado**, porque se denegó compilar código externo en esta máquina. MinIO es AGPL-3.0: cumplimiento debe revisarlo antes de distribuir la imagen.
- **Cuatro imágenes con digest de ceros** (`restore-drill`, `grafana-folder-permissions`, `minio`, `mc`): se reemplazan al publicarlas. `restore-drill` además espera las CLI de U3 y U8. Hasta entonces, esos pods no pueden arrancar.
- **`readOnlyRootFilesystem`** se exige en todo, y algunas imágenes upstream podrían necesitar un `emptyDir` adicional: solo se ve al arrancarlas (Paso 19).
- La prueba de integración cubre los charts HTTP; los OCI (`envoy-gateway`, `kserve`) no se renderizan, y sus namespaces no están bajo estas políticas.
- `test_every_workload...` asume 8 nodos para los DaemonSet al sumar la cuota de producción.

- `require-pdb` y `require-hpa-bounds` consultan la API solo en un clúster; `kyverno test` les inyecta el resultado. La consulta real y el `ClusterRole` de `platform/policies/rbac/` se comprueban en el Paso 19.
- Con los verbos de K11 (`create`, `update`, `get`), ESO podría necesitar además `list`, `watch` o `patch` sobre `secrets`: se comprueba en el Paso 19.
- `pod_cidr` y `api_server_cidr` de staging y prod valen `0.0.0.0/32`, que no autoriza a nadie, hasta que el banco entregue los rangos. Las URL `git.banco.internal` y `charts.banco.internal` son provisionales.
- En kind, `api_server_cidr` supone la red de Docker `172.18.0.0/16`.
- El backup mensual con prefijo `monthly/` no se logra con un `ScheduledBackup` sobre el mismo almacén, y la retención de 30 días podría borrarlo.
- `syncReplicaElectionConstraint` podría chocar con NFR-U1-03 tras perder una zona (Paso 20).
- Las versiones de chart de `components.yaml` no se han instalado.
- Kyverno 1.19 marca `ClusterPolicy` como obsoleta, con migración a `ValidatingPolicy`. Sigue funcionando en la CLI.
- `verify-images` lleva una llave de marcador (`REEMPLAZAR_POR_ENTORNO`), que rechaza las imágenes de esos registros hasta configurarla, y no tiene caso en `kyverno test` porque necesita firmas reales (Paso 20).
- Las pruebas de promtool validan la lógica con series sintéticas, no que las métricas existan: los nombres de CloudNativePG, MinIO, Linkerd y Kyverno se comprueban en el Paso 19.
- Hay tres nombres de registro en uso: `registro.vectra.internal`, `registro.banco.internal/vectra` y `kind-registry:5000`. `restrict-registries` admite los tres; falta unificarlos por entorno.

## 6. Corrección de consistencia entre unidades (2026-11-01)

U1 se corrigió junto con U0 y los planes de U2 a U12, después de comprobar que no entregaba lo que las demás unidades esperan. Sin clúster: los Pasos 19 y 20 siguen pendientes, y lo que depende del comportamiento real de Linkerd, CloudNativePG, MinIO, KServe, Envoy Gateway y Keycloak sigue sin verificar.

Decisiones:

- GitOps sigue en el monorepo; una `Application` es una entrada de `components.yaml`, y los valores de una unidad van en `vectra-risk-gitops/values/<env>/<componente>.yaml`.
- U1 es dueña de los secretos `pg-role-*` y `minio-*`.
- Los namespaces de operadores se comunican libremente por dentro (F125), llegan a la API (F126) y reciben sus webhooks (F127).
- Las rutas de Linkerd de `governance-service` son una por camino, con todos sus clientes y sin solapes, comprobadas contra las rutas de U0.
- `verify-images` no se instala en kind. La firma es con llave (`sign-image.yml`), no sin llave.
- `require-hpa-bounds` audita al admitir; el HPA se exige sobre el render en el PR (`hpa.rego`).
- MinIO: se mantiene la opción A, con `docker-entrypoint.sh`; la imagen sigue sin construirse, y AGPL-3.0 sigue sin revisión de cumplimiento.
- Excepciones de Trivy con vencimiento 2027-02-01: `AVD-KSV-0053` y `AVD-KSV-0114` (`.trivyignore`). Requieren aprobación del dueño del repositorio.

Tareas humanas para la separación de funciones en un solo repositorio (decisión del usuario, 2026-11-01): crear los equipos, pasarles las reglas de `.github/CODEOWNERS` y exigir la revisión de code owners en la rama protegida. Hasta entonces, todas las reglas apuntan al dueño del repositorio.

Protección de `main` (2026-11-01): checks obligatorios `checks`, `forbidden / forbidden`, `policies / policies`, `tests / tests`, `evidence / evidence`, `supply-chain / scan` y `rollback-note`, y revisión de code owners. `platform.yml` y `contracts.yml` corren en todo PR y en cada push a `main`, sin filtro de rutas, porque un check obligatorio que no corre deja el PR esperando. `enforce_admins` queda apagado: con un solo dueño, GitHub no deja aprobar el PR propio, y sin esa salida nadie podría fusionar. Al crear los equipos, se enciende.
