# Plan de tareas (Code Generation Part 1) — U1 `platform-foundation`

**Este plan es la única fuente de verdad para generar el código de U1.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U1. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U1 `platform-foundation`: la base de Kubernetes, sin lógica de negocio |
| Historias (dueña) | US-604 (base de red y egress), US-605, US-606, US-607, US-608, US-610 |
| Ubicación | `vectra-risk/platform/` (monorepo) y el repositorio `vectra-risk-gitops` |
| Datos propios | La infraestructura de las bases; los esquemas son de cada unidad |
| Depende de | U0 (puerto 8081, métricas y logs del middleware; `verify_chain` llega con U3) |
| Lo consumen | Todas las unidades que despliegan (`construction/shared-infrastructure.md`) |

**Diseño de entrada:**
- NFR Requirements: `construction/platform-foundation/nfr-requirements/` (NFR-U1-01..44).
- NFR Design: `construction/platform-foundation/nfr-design/` (P-U1-01..12).
- Infrastructure Design: `construction/platform-foundation/infrastructure-design/` (INF-U1-01..10).
- Inventario: `inception/application-design/component-dependency.md` (F01–F111, K01–K14 y K16, X01–X10; precisado el 2026-10-08: el inventario creció con los Infrastructure Design de U2, U3, U4, U7 y U8).

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

- [ ] **Paso 1 — Esqueleto de `platform/` y de `vectra-risk-gitops`**
  - Directorios de §1, `platform/Makefile` con el objetivo `check`, `.github/pull_request_template.md` con la sección obligatoria «Rollback» (NFR-U1-44).
  - **Aceptación**: `make -C platform check` existe y termina en 0 sobre el esqueleto; `test -f vectra-risk-gitops/apps/kind/root.yaml`.

- [ ] **Paso 2 — Configuración de kind**
  - `platform/kind/cluster.yaml`: 1 control-plane + 4 workers con `topology.kubernetes.io/zone` (`zone-a` ×2, `zone-b` ×2) y CNI por defecto deshabilitado (para Calico). Cifrado de Secrets en etcd (`EncryptionConfiguration`). Registro local `kind-registry` y `cloud-provider-kind`.
  - Solo archivos de configuración: crear el clúster es parte del Paso 19.
  - Diseño: INF-U1-01, 04, 05, 09; NFR-U1-24.
  - **Aceptación**: `python platform/tests/test_kind_config.py` (4 workers, 2 zonas, `disableDefaultCNI: true`, cifrado de etcd configurado).

### Bloque B — Red y malla

- [ ] **Paso 3 — Inventario de flujos y generador**
  - `network/flows.yaml` con **todos** los flujos de `component-dependency.md` (F01–F111, incluidos F90–F105 de U2, U3, U4 y U8, F106 del CronJob de bias de U9 hacia el Pushgateway, F107 de `registry-aggregator` y F108 del Job de reset de U3; F09 con `enabled: false`; quinta revisión del FD de U9, 2026-10-10), cada uno con origen, destino (namespace + ServiceAccount), puerto, dirección e ID; `network/forbidden.yaml` con X01–X10. **F27** (`POST /v1/models/{id}/freeze`) tiene como origen **solo** el ServiceAccount `bias-monitoring-job` de los pods del CronJob de U9, no el servicio HTTP `bias-monitoring-service` (INF-U9-04; revisión del FD de U10, 2026-10-10, B13).
  - `network/generate.py`: deny-all por namespace, un allow por flujo, DNS como única excepción común, `Server` + `AuthorizationPolicy` de Linkerd y la suite de conectividad (un caso permitido y uno bloqueado por flujo; X01–X10 como casos bloqueados; para F27, el permitido sale del pod del CronJob y el bloqueado, de `bias-monitoring-service`; revisión del FD de U10, 2026-10-10, B13; bloqueados de U10: `console-spa` → cualquier servicio de `vectra-app`, `console-bff` → `vectra-data` y `console-bff` → `vectra-serving`, INF-U10-04, Infrastructure Design de U10, 2026-10-10; de U12: F07 desde fuera del clúster por el gateway (sin `channel-simulator` en `vectra-mock`), F111 (`x06-probe` → `registry-db-rw`) solo en kind, el selector de F27 por `vectra.io/workload: bias-monitoring-job` que admite los pods de `x04-probe` (prueba de `generate.py`), y el binding K16 solo en kind y staging (revisión del Infrastructure Design de U12, 2026-10-10), Infrastructure Design de U12, 2026-10-10; de U11: `product-metrics` → `case-service` y `governance-service` bloqueados, un pod que no es Prometheus → 8081 de `product-metrics` bloqueado, y `/readyz` del kubelet → 200 con el `Server` de Linkerd aplicado, INF-U11-04, Infrastructure Design de U11, 2026-10-10).
  - Diseño: NFR-U1-20; P-U1-01, P-U1-02; INF-U1-06. Historia: US-604.
  - **Aceptación**:
    - `python platform/network/generate.py --check` (los manifiestos versionados coinciden con los generados);
    - `pytest platform/network/tests` (todo ID de `component-dependency.md` aparece en `flows.yaml`, con una prueba que extrae los IDs del Markdown, sin un rango fijo, así que también cubre los flujos que agreguen las unidades siguientes; `vectra-restore-drill` tiene exactamente F75, F80 y F87).

- [ ] **Paso 4 — Linkerd y cert-manager**
  - Values de Linkerd: HA, `linkerd-cni`, `default-inbound-policy: deny` en los namespaces de Vectra, anotación de sidecar nativo en `vectra-restore-drill` (P-U1-05).
  - cert-manager: trust anchor de 1 año, issuer intermedio de 48 h, `Certificate` del borde y de PostgreSQL (90 días, renovación a los 60).
  - Diseño: P-U1-02, 03, 06; NFR-U1-21, 22.
  - **Aceptación**: `helm template` de Linkerd y cert-manager con los values de prod + `conftest test` (HA = 3 réplicas, CNI activo, duraciones y renovaciones esperadas, anotación de sidecar nativo presente en `vectra-restore-drill`).

### Bloque C — Políticas y recursos

- [ ] **Paso 5 — Políticas de Kyverno y PSA**
  - Políticas:
    - `verify-images`: firma Cosign y registro permitido por entorno;
    - `disallow-latest`;
    - `require-run-as-non-root`, `disallow-privileged`, `disallow-host-path`, `require-ro-rootfs`;
    - `require-resources`, `require-priority-class`, `require-spread-and-pdb`, `require-hpa-bounds` (admite un Deployment sin HPA solo con la anotación `vectra.io/hpa-exempt` no vacía, `replicas ≥ 2` y PDB; NFR-U1-12; precisado el 2026-10-10 por U9 NFR Requirements);
    - `restrict-loadbalancer` (solo el api-gateway), `disallow-plain-secrets`, `disallow-argocd-auto-sync` (cubre también la Application `decision-registry-rebuild` de U3);
    - no hay `restrict-manual-jobs`: se descartó con K15. Los Jobs de reconstrucción de U3 los crea Argo CD desde la Application `decision-registry-rebuild` tras un PR y un sync manual (revisión del FD de U10, 2026-10-10, B13);
    - `require-criticality-label`, `disallow-rbac-wildcards`;
    - `add-native-sidecar-to-jobs` (**mutación**, P-U1-05): agrega la anotación del sidecar nativo de Linkerd al pod template de todo Job o CronJob de un namespace con la etiqueta `vectra.io/mesh: enabled`, incluidos los que crea CloudNativePG, y nunca rechaza. Selecciona por esa etiqueta porque Kyverno solo ve etiquetas, y la anotación `linkerd.io/inject: enabled` no lo es (cuarta y séptima revisión del FD de U9; redacción en la octava revisión del FD de U9, 2026-10-10).
  - **Chart `platform/namespaces`** (octava revisión del FD de U9, 2026-10-10): crea cada namespace de Vectra con la etiqueta de PSA `restricted`, la etiqueta `vectra.io/mesh: enabled` y la anotación `linkerd.io/inject: enabled` en los mallados (siempre las dos juntas), y la anotación del sidecar nativo; los values listan qué namespaces están mallados: exactamente los de P-U1-14 (revisión del Infrastructure Design de U10, 2026-10-10).
  - Etiquetas de PSA `restricted` por namespace. Kyverno en HA con `failurePolicy: Fail` y exclusiones de `kube-system`, `kyverno` y `linkerd`.
  - Diseño: NFR-U1-01, 04, 12, 25, 27, 43; P-U1-05, 06, 09; INF-U1-05, 09. Historias: US-605, US-606, US-607.
  - **Aceptación**: `kyverno test platform/policies/`, con un caso que pasa y uno que falla por política. Casos nombrados (revisión del NFR Requirements de U9, 2026-10-10):
    - `require-hpa-bounds`: Deployment sin HPA y sin `vectra.io/hpa-exempt` → rechazado; con la anotación, 2 réplicas y PDB → admitido; con la anotación y 1 réplica → rechazado;
    - `add-native-sidecar-to-jobs`: CronJob de `vectra-app` sin la anotación → admitido con la anotación agregada; Job `join` de CloudNativePG en `vectra-data` (con `ownerReference` a un `Cluster`) → admitido con la anotación, nunca rechazado; Job hook de `keycloak-config-cli` y CronJob `realm-drift` en `vectra-identity`, y un Job en `vectra-mock` → admitidos con la anotación; Job en un namespace sin la etiqueta `vectra.io/mesh` → sin cambios;
    - **binding K16** (U12 INF-U12-03; revisión del Infrastructure Design de U12, 2026-10-10): `platform/rbac/verification-operator/` con el `ClusterRole` de `nodes` y un `Role` por namespace según la tabla de INF-U12-03, renderizado **solo** con los values de kind y staging; `conftest` sobre el render de producción → sin K16; `kyverno test` de `disallow-rbac-wildcards` con K16 → admitido; un fixture de K16 con `delete` o `exec` → rechazado;
    - chart de namespaces: todo namespace con la anotación `linkerd.io/inject: enabled` tiene la etiqueta `vectra.io/mesh: enabled`, y viceversa; la lista mallada es exactamente la de P-U1-14;
    - `add-native-sidecar-to-jobs`: un Job en `vectra-edge` y otro en `vectra-observability` → admitidos con la anotación (revisión del Infrastructure Design de U10, 2026-10-10);
    - `require-hpa-bounds`: `console-spa` con la exención, 2 réplicas y PDB → admitido; un `InferenceService` de `vectra-staging` con 1 réplica → admitido (fuera del alcance); uno de `vectra-serving` con 1 réplica → rechazado; uno de `vectra-serving` con 1 réplica, `vectra.io/serving-state: inactivo` y `vectra.io/hpa-exempt` → admitido; el mismo con `serving-state: activo` → rechazado (segunda revisión del Infrastructure Design de U10, 2026-10-10).

- [ ] **Paso 6 — PriorityClasses, cuotas y límites**
  - Las 4 PriorityClasses de P-U1-09; `ResourceQuota` y `LimitRange` por namespace (máximo del HPA + 30 %), **con el proxy de Linkerd** de P-U1-14 en cada pod mallado (revisión del Infrastructure Design de U10, 2026-10-10).
  - `console-spa` (U10) es el segundo Deployment con `vectra.io/hpa-exempt` (2 réplicas fijas, NFR-U10-12).
  - **Pushgateway** (P-U1-13): 1 réplica con PVC de persistencia y `--persistence.interval=1m`; `Server` y `HTTPRoute` de Linkerd por identidad y método.
  - La cuota de `vectra-app` y la de `vectra-mock` suman los aportes declarados por las unidades: INF-U7-02 (U7), INF-U8-05 (U8) e INF-U9-01 (U9, con margen y con el sidecar; ver la viñeta siguiente), los de U3 y U4 cuando existan, y el de U11 (NFR-U11-14: 3 pods en el peor momento con el proxy; requests ≈ 0,78 CPU / 1,05 GiB y limits ≈ 3,9 CPU / 2,44 GiB; NFR Requirements de U11, 2026-10-10) (precisado el 2026-10-08, revisión del Infrastructure Design de U8).
  - La cuota de `vectra-app` suma también los Jobs de reconstrucción de U3, `registry-aggregator-rebuild-<runId>` y `registry-aggregator-reset-<runId>`, de la Application aparte `decision-registry-rebuild` (INF-U3-03), mientras corren (revisión del NFR Requirements de U9, 2026-10-10; revisión del FD de U10, 2026-10-10, B13). El aporte de U9 se suma **con** el sidecar de Linkerd (INF-U9-01: requests ≈ 0,78 CPU / 0,56 GiB y limits ≈ 3,9 CPU / 1,46 GiB), porque la cuota cuenta el sidecar nativo; los recursos del proxy son los de P-U1-14, que coinciden con los usados en INF-U9-01 e INF-U10-01 (revisión del FD de U10, B8, y del Infrastructure Design de U10, 2026-10-10).
  - La cuota de `vectra-app` suma el BFF de U10 y la de `vectra-edge`, la SPA de U10, con el sidecar (INF-U10-01, con los pods del rollout: requests ≈ 3,19 CPU / 2,4 GiB y 0,78 CPU / 0,26 GiB; limits ≈ 13,7 CPU / 5,7 GiB y 3,64 CPU / 0,97 GiB; segunda revisión del Infrastructure Design de U10, 2026-10-10). Regla general: cada unidad dimensiona su aporte con los pods del peor momento, incluido el `maxSurge` de su rollout.
  - La cuota de `vectra-staging` suma los `InferenceService` de staging de U6 y el predictor de la versión activa de U4 INF-U4-05 durante una `source_comparison` (quinta revisión del FD de U9, 2026-10-10).
  - Diseño: NFR-U1-13; P-U1-09; INF-U7-02; INF-U8-05; INF-U4-05.
  - **Aceptación**: `conftest test platform/policies/quotas/` (todo namespace de Vectra tiene cuota y límites); `kyverno test` del caso «Pod sin `priorityClassName` → rechazado».

### Bloque D — Datos y secretos

- [ ] **Paso 7 — CloudNativePG y los 4 clusters**
  - Operador (2 réplicas). Por cluster:
    - 3 instancias, anti-afinidad obligatoria por nodo y reparto preferido por zona;
    - `minSyncReplicas: 1`, `maxSyncReplicas: 2`;
    - `walStorage` y tamaños de INF-U1-02;
    - `max_connections` inicial;
    - TLS con certificados de cert-manager;
    - toleration del pool `data`;
    - `PriorityClass` `vectra-critical`.
  - Backups con Barman Cloud hacia el S3 fuera del sitio (F70): `archive_timeout: 60s`, `ScheduledBackup` diario, `retentionPolicy: 30d`, backup mensual con prefijo `monthly/` (lifecycle de 12 meses en el bucket) y object lock en los buckets de `registry-db`.
  - Diseño: NFR-U1-02, 05, 06, 23 (backups cifrados del lado del servidor); INF-U1-02, 03; P-U1-08. Historias: US-605, US-608.
  - **Aceptación**: `helm template` + `conftest test platform/data/` (3 instancias, sync, `archive_timeout = 60s`, retención de 30 días, WAL separado, `sslmode` exigido, toleration y prioridad).

- [ ] **Paso 8 — MinIO**
  - Modo distribuido con 4 pods en el pool `data` (2 por zona); buckets `model-store`, `validation-datasets`, `loki` (versionado + object lock de 90 días) y `tempo` (lifecycle de 7 días); usuarios de solo lectura para KServe y validación.
  - Diseño: INF-U1-03; NFR-U1-30.
  - **Aceptación**: `helm template` + `conftest test platform/data/minio/` (4 réplicas, reparto por zona, buckets con la configuración esperada).

- [ ] **Paso 9 — External Secrets y Vault (kind)**
  - ESO; `ClusterSecretStore` por entorno (Vault en kind, la bóveda del banco en staging/prod con F74); Vault en modo dev solo para kind; binding K11 limitado a los namespaces de Vectra.
  - Diseño: NFR-U1-24; INF-U1-10.
  - **Aceptación**: `kyverno test` de `disallow-plain-secrets`; `grep -rL "kind: Secret" vectra-risk-gitops/` devuelve todos los archivos (ningún Secret plano); `conftest` sobre el RBAC de ESO (sin comodines, solo los namespaces declarados).

### Bloque E — Observabilidad y operación

- [ ] **Paso 10 — Stack de observabilidad**
  - Prometheus (2 réplicas, 30 días), Alertmanager (3 réplicas, receptor F72 por `severity`, `Watchdog` cada 5 min), Loki (MinIO, `retention_enabled: false`, retención por lock y lifecycle), Tempo (7 días), OTel Collector, Grafana Alloy, Pushgateway (F87, F88 y F106; alerta `PushgatewayDown`) y Grafana.
  - **Permisos de carpetas de Grafana** (FD de U11, 2026-10-10, U11 BR-U11-13 y U9 INF-U9-05): `platform/observability/grafana/folder-permissions.yaml` (carpetas `Vectra / Sesgo` → equipos `cro` y `cumplimiento`; `Vectra / Producto` → `cro`, `cumplimiento` e `ingeniero_riesgo`; carpeta de operación → `operacion` con `Edit` (Infrastructure Design de U11, 2026-10-10)), aplicado por el Job idempotente `grafana-folder-permissions` (hook `PostSync` de la Application de observabilidad, F110) que quita los permisos de rol de esas carpetas y deja solo los de equipo; CronJob horario en modo comprobación que publica `vectra_grafana_folder_permissions_drift` (alerta `GrafanaFolderPermissionsDrift`, SEV3). Token de una cuenta de servicio de Grafana por ESO.
  - Diseño: NFR-U1-30, 31, 34; INF-U1-07, 08; P-U1-07. Historia: US-610.
  - **Aceptación**: `helm template` + `conftest test platform/observability/` (retenciones, sin remote-write, receptor F72 configurado, Loki sin compactor de borrado); `uv run pytest platform/tests/test_grafana_folder_permissions.py` con un Grafana de Testcontainers (carpeta con permisos de rol → el Job los quita; segunda corrida → sin cambios; comprobación con deriva → métrica 1); en kind (Paso 19), los usuarios de U2: `ingeniero-1` → `Vectra / Producto` 200 y `Vectra / Sesgo` 403, `operacion-1` y `analista-1` → 403 en las dos, `cro-1` y `cumplimiento-1` → 200 en las dos (FD de U11, 2026-10-10).

- [ ] **Paso 11 — Reglas, SLO y runbooks**
  - `PrometheusRule` con todas las alertas de `logical-components.md` §3, las reglas de grabación del SLO y los burn rates (P-U1-11).
  - Runbook por alerta con la plantilla de P-U1-10; `coe-template.md`.
  - Incluye `GrafanaFolderPermissionsDrift` (Job y CronJob de permisos de carpetas, Paso 10) con su runbook `grafana-folder-permissions-drift`, que explica cómo reaplicar el Job con un sync de la Application de observabilidad (Infrastructure Design de U11, 2026-10-10).
  - Diseño: NFR-U1-32; P-U1-10, 11. Historia: US-610.
  - `PostgresVolumeUsageHigh` con una regla de ausencia por `Cluster`, de la forma `(count(...) or vector(0)) < 6` según INF-U1-02, y no un `absent()` común a los cuatro (precisado el 2026-10-08, revisión del Infrastructure Design de U8).
  - **Aceptación**: `promtool test rules platform/observability/rules/tests/*.yaml` (cada alerta se dispara con series sintéticas; el caso de `PostgresVolumeUsageHigh` quita las series de un solo `Cluster`, `case-db`, con los otros tres reportando, y debe disparar) y `python platform/tests/test_runbooks.py` (toda regla tiene `severity` válida y un `runbook_url` hacia un archivo existente).

- [ ] **Paso 12 — Dashboards como código**
  - Dashboards de seguridad, resiliencia, operación y SLO en JSON. La carpeta de operación (equipo `operacion`) incluye el panel de operación de U11 (NFR-U11-41: ciclo, entradas leídas, recomputación diaria y breaker hacia U3; NFR Requirements de U11, 2026-10-10).
  - Diseño: NFR-U1-33.
  - **Aceptación**: `python platform/tests/test_dashboards.py` (JSON válido, fuentes de datos por UID, sin consultas a métricas inexistentes en las reglas).

### Bloque F — Resiliencia

- [ ] **Paso 13 — `restore-drill`**
  - CronJob semanal en `vectra-restore-drill` (prioridad `vectra-low`, sidecar nativo de Linkerd); script que crea el `Cluster` efímero, corre `verify_chain` (CLI de U3), empuja las métricas al Pushgateway (F87) y destruye el cluster; RBAC K12; credencial de solo lectura para F75, limitada a los prefijos de `registry-db` y `case-db` en `vectra-backups` y `vectra-wal` y al bucket `vectra-registry-checkpoints` (precisado el 2026-10-06, revisión del FD de U8: cubre la restauración de `case-db` sin un flujo nuevo).
  - Diseño: P-U1-05; NFR-U1-06, 07. Historia: US-608.
  - **Aceptación**: `helm template` + `conftest test platform/restore-drill/` (anotación de sidecar nativo, RBAC sin comodines, credencial distinta de la de F70 y cuya política de bucket solo permite lectura sobre los prefijos de `registry-db` y `case-db` y `vectra-registry-checkpoints`); `pytest platform/restore-drill/tests` (el script termina con error si `verify_chain` no devuelve «íntegra»).
  - **Dependencia**: la CLI `verify_chain` llega con U3. Hasta entonces, el script usa una interfaz con un doble de prueba.
  - **Restauración de `case-db`** (precisado el 2026-10-06, revisión del FD de U8): segundo cluster efímero desde el backup de `case-db`, `case-retention` (CLI de U8; doble de prueba hasta que exista) y conteo de identificadores vencidos. `pytest platform/restore-drill/tests`: un conteo > 0 hace fallar el script y pone `vectra_restore_drill_retention_violations` > 0; `promtool test rules` de `RestoreDrillRetentionViolation` (SEV2) y la prueba de que tiene `runbook_url`.
  - Diseño adicional: NFR-U1-07 precisado; BR-U8-20.

- [ ] **Paso 14 — Runbooks de operación**
  - `install.md` (incluida la suite de conformidad del CNI como paso previo, INF-U1-04), `zone-failover.md`, `site-restore.md`, `trust-anchor-rotation.md`, y `docs/criticality.md` y `docs/capacity.md`.
  - Diseño: NFR-U1-01, 07, 08, 10; P-U1-03; INF-U1-04.
  - **Aceptación**: `python platform/tests/test_runbooks.py --operational` (los cuatro existen, siguen la plantilla y cada paso de verificación nombra un comando).

### Bloque G — GitOps

- [ ] **Paso 15 — Argo CD y app-of-apps**
  - Argo CD (values); `root.yaml` por entorno; una `Application` por componente con las waves 0–6 de P-U1-12; values por entorno (registro de imágenes, Git del espejo, StorageClass, tamaños).
  - Diseño: P-U1-12; INF-U1-01..03, 09; NFR-U1-23 (StorageClass cifrada por entorno), 43. Historia: US-607.
  - **Aceptación**: `kyverno test` de `disallow-argocd-auto-sync` sobre `vectra-risk-gitops/apps/`; `python platform/tests/test_waves.py` (cada Application tiene wave y el orden coincide con P-U1-12).

- [ ] **Paso 16 — Lint y render de todos los charts**
  - `helm lint` de todos los charts y snapshots de `helm template` por entorno, versionados para revisarlos en el PR.
  - Historia: US-605.
  - **Aceptación**: `make -C platform render && git diff --exit-code platform/rendered/`; `conftest test platform/rendered/prod/` (topologySpread por zona y PDB en todos los Deployments, como exige US-605; y la anotación del sidecar nativo **explícita** en el pod template de cada Job y CronJob renderizado, incluidos los Jobs de reconstrucción de U3, que se renderizan desde `decision-registry/chart-rebuild/` (Application aparte `decision-registry-rebuild`, wave 6; revisión del FD de U10, 2026-10-10, B13) con `--set monitoringRebuild.runId=test` en una variante del render (aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10), para que la mutación de Kyverno nunca cambie un recurso de Git; sexta revisión del FD de U9, 2026-10-10).

### Bloque H — CI

- [ ] **Paso 17 — Workflows reutilizables**
  - `tests.yml` (con la semilla de PBT registrada), `supply-chain.yml` (Trivy, Syft, Cosign; falla con hallazgos críticos o altos sin excepción vigente), `evidence.yml` (`helm template` y `kubectl diff` como artefactos del PR), `forbidden-steps.yml` (falla si aparecen `kubectl apply`, `helm install`/`upgrade`, `terraform apply` o `argocd app sync`) y `policies.yml` (`kyverno test`, `promtool`, `conftest`, `actionlint`). Input `runner` parametrizado.
  - El workflow de U0 (`contracts.yml`) reemplaza su job provisional `pip-audit`/`npm audit` por `supply-chain.yml`.
  - Diseño: NFR-U1-26, 40..42. Historia: US-606.
  - **Aceptación**: `actionlint .github/workflows/*.yml`; `python platform/tests/test_forbidden_steps.py` (un workflow de fixture con `kubectl apply` hace fallar `forbidden-steps`); `grep -L "secrets.KUBECONFIG" .github/workflows/*.yml` devuelve todos los archivos.

- [ ] **Paso 18 — Resumen del código de U1**
  - `aidlc-docs/construction/platform-foundation/code/README.md`: componente → archivos → verificación → NFR/P/INF.
  - **Aceptación**: `python platform/tests/test_traceability.py` (cada NFR-U1-xx, P-U1-xx e INF-U1-xx aparece en algún archivo de `platform/` o del repositorio GitOps).

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
    5. el restore del sitio en un kind limpio (≤ 4 h, `verify_chain` «íntegra»);
    6. `restore-drill` manual (el Job llega a `Complete` y `restartPolicy: Always` en el proxy);
    7. el `Watchdog` recibido;
    8. las pruebas de readiness de P-U1-04 (`case-db` caída; explainability o governance caídos).
  - Los puntos 5, 6 y 8 dependen de U3, U7 y U8: se marcan como pendientes hasta que esas unidades existan.
  - Historias: US-604, US-605, US-608, US-610.
  - **Aceptación**: un archivo de evidencia por simulacro adjunto al PR, con comando, salida y resultado esperado contra el obtenido.

- [ ] **Paso 21 — Prueba de carga: diferida**
  - NFR-U1-11 (20/s durante 15 min) necesita los servicios de U7 y U8 y el simulador de U12. La ejecuta U12 sobre esta plataforma; los máximos del HPA y `max_connections` se recalculan con su resultado.
  - **Aceptación**: `grep -q "NFR-U1-11" aidlc-docs/construction/plans/system-verification-code-generation-plan.md` cuando exista ese plan (la verificación la hereda U12).

### Bloque J — Cierre

- [ ] **Paso 22 — Repositorio, migraciones y frontend: N/A**
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
