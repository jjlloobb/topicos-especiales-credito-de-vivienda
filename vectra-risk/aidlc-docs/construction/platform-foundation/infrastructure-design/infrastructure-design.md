# Infrastructure Design — U1 `platform-foundation`

Decisiones del plan (`platform-foundation-infrastructure-design-plan.md`, Q1–Q11 = A).
Destino: on-premise, en clústeres Kubernetes del banco conformes a CNCF; sin proveedor de
nube. Los IDs `INF-U1-xx` se referencian en el plan de tareas.

---

## 1. Entornos (Q1, Q11)

| Entorno | Clúster | Uso | Git (F71) | Imágenes (Q10) |
|---|---|---|---|---|
| `kind` | kind local o efímero en CI | Desarrollo, CI, simulacros (fallo de zona, restore) | GitHub | `kind-registry` local |
| `staging` | Clúster del banco **separado** de producción | Pruebas de integración y ensayo de cambios | Espejo Git interno del banco | Registro interno del banco |
| `prod` | Clúster del banco | Operación | Espejo Git interno del banco | Registro interno del banco |

- Los charts son los mismos en los tres entornos; solo cambian los values (`envs/{env}/`).
- El namespace `vectra-staging` existe en los tres entornos y es solo para validar modelos (journey 7.2).
- La réplica GitHub → espejo y GHCR → registro interno la hace el banco con su propio proceso. Ningún componente de Vectra empuja hacia el banco.

## 2. Cómputo (Q2)

### INF-U1-01 — Nodos

| Entorno | Pool | Nodos | Tamaño inicial | Taint | Cargas |
|---|---|---|---|---|---|
| kind | control-plane | 1 | — | — | — |
| kind | workers | 4 (2 en `zone-a`, 2 en `zone-b`) | — | — | Todo |
| prod/staging | `general` | ≥ 4 por zona (antes ≥ 3; se ajusta con la prueba de carga de U12; seguimiento de la cuarta revisión de coherencia, 2026-10-31) | 8 vCPU / 32 GiB (inicial) | — | Servicios, KServe, observabilidad, controladores |
| prod/staging | `data` | ≥ 2 por zona | 8 vCPU / 32 GiB (inicial; antes 4 vCPU / 16 GiB; seguimiento de la quinta revisión de coherencia, 2026-10-31) | `vectra.io/pool=data:NoSchedule` | PostgreSQL y MinIO |

- Los tamaños son iniciales y se ajustan con la prueba de carga (NFR-U1-11) y las cuotas (NFR-U1-13).
- Etiqueta `topology.kubernetes.io/zone` en todos los nodos; en kind se asigna en la configuración del clúster.
- **Justificación de los 4 workers en kind y de los 2 nodos de datos por zona**: con anti-afinidad obligatoria por nodo, la zona que sobrevive necesita un nodo libre para que CloudNativePG clone la réplica nueva (NFR-U1-03).

## 3. Almacenamiento

### INF-U1-02 — Volúmenes de PostgreSQL (Q3)

| Cluster | Datos | WAL | `max_connections` inicial |
|---|---|---|---|
| `registry-db` | 100 Gi | 20 Gi | 100 |
| `case-db` | 50 Gi | 10 Gi | 100 |
| `governance-db` | 10 Gi | 5 Gi | 50 |
| `keycloak-db` | 10 Gi | 5 Gi | 100 |

Cada `Cluster` se inicializa con `bootstrap.initdb` y su base y dueño (2026-11-01): `registry-db` → `registry`, `registry_migrator`; `case-db` → `case`, `case_migrator`; `governance-db` → `governance`, `gov_migrator`; `keycloak-db` → `keycloak`, `keycloak`. El secreto es el `pg-role-*` del dueño. `case` es palabra reservada de SQL: en una sentencia va entre comillas, en una URL de conexión no.

- StorageClass de producción y staging: la del banco, con cifrado, `volumeBindingMode: WaitForFirstConsumer` y `allowVolumeExpansion: true`. En kind se usa `standard`, la StorageClass que kind trae de fábrica, sin cifrado (documentado como no aplicable a NFR-U1-23).
- `max_connections` se calcula con P-U1-08: `(réplicas máximas del HPA × 5) × 1,2 + conexiones del operador y de los backups`. Los valores iniciales cubren hasta 12 réplicas por servicio. `case-db` tiene dos Deployments clientes (`case-service` y `case-worker`, 6 réplicas máximas cada uno = 12 × 5 conexiones), más el CronJob `case-retention` y el Job de migración; el valor inicial lo cubre (precisado el 2026-10-06 por U8 NFR Requirements, NFR-U8-14). Para Keycloak se fija un pool máximo de 20 conexiones por pod. Se recalculan con los máximos reales tras la prueba de carga. `registry-db` suma además la conexión del CronJob `registry-aggregator` (F107, 1 conexión a `-rw`): ≈ 47 en total (U3 INF-U3-04; quinta revisión del FD de U9, 2026-10-10).
- Alertas, para los cuatro `Cluster` (es la única alerta de volumen; U8 la reutiliza para `case-db`, INF-U8-08):

  | Alerta | Condición | Severidad |
  |---|---|---|
  | `PostgresVolumeUsageHigh` | `kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes` de los PVC de un `Cluster` > 0,80 durante 15 min | SEV3 |
  | `PostgresVolumeUsageHigh` | Lo mismo > 0,90 durante 15 min | SEV2 |
  | `PostgresVolumeUsageHigh` | **Una regla por `Cluster`** (`registry-db`, `case-db`, `governance-db`, `keycloak-db`), con la etiqueta `cluster`: `(count(kubelet_volume_stats_capacity_bytes{namespace="vectra-data", persistentvolumeclaim=~"<cluster>-[0-9]+(-wal)?"}) or vector(0)) < 6` durante 15 min. Si el kubelet deja de reportar los volúmenes de ese `Cluster`, o uno solo de ellos, la alerta no calla justo cuando el disco se llena (precisado el 2026-10-08, revisiones del Infrastructure Design de U8) | SEV2 |

  - **Por qué no un solo `absent()`**: `absent()` solo devuelve 1 si no existe **ninguna** serie que coincida. Con un filtro que abarca los cuatro `Cluster`, si deja de reportar solo `case-db`, las otras tres siguen reportando y la alerta calla. Por eso hay una regla por `Cluster`.
  - **Por qué `count < 6`**: cada `Cluster` tiene 3 instancias con un volumen de datos y uno de WAL (INF-U1-02), así que se esperan 6 PVC. El `or vector(0)` cubre el caso sin ninguna serie, que `count()` no devuelve. Si cambia el número de instancias, cambia el 6 (el chart lo calcula de `instances × 2`). Los 15 min absorben la recreación de un PVC durante un failover.
  - `promtool test rules`: 79 % no dispara; 81 % → SEV3; 91 % → SEV2; con los cuatro `Cluster` reportando, **se quitan las series de `case-db`** y a los 15 min dispara la regla de `case-db` (SEV2) y ninguna otra; quitar una sola de las 6 series de `case-db` también dispara; con las 6 series presentes no dispara.

**Recursos iniciales del pool `data`** (seguimiento de la quinta revisión de coherencia, 2026-10-31), que se ajustan con la prueba de carga:

| Componente | Pods | Requests por pod | Limits por pod |
|---|---|---|---|
| `registry-db`, `case-db` | 3 + 3 | 1 CPU / 4 GiB | 2 CPU / 8 GiB |
| `governance-db`, `keycloak-db` | 3 + 3 | 500m / 2 GiB | 1 CPU / 4 GiB |
| MinIO | 4 | 1 CPU / 4 GiB | 2 CPU / 8 GiB |

Con el proxy (P-U1-14), 16 pods suman requests de 14,6 CPU / 52,3 GiB y limits de 34 CPU / 106 GiB. La cuota de `vectra-data`, con el 30 %, es ≈ 18,98 CPU / 68 GiB de requests y ≈ 44,2 CPU / 137,8 GiB de limits. Con una zona caída quedan 10 pods (2 instancias por cluster y 2 de MinIO) con ≈ 9 CPU / 32,2 GiB de requests, frente a los 16 vCPU / 64 GiB de esa zona.

**Roles de base de datos** (cuarta revisión de coherencia entre unidades, 2026-10-31). U1 declara en `managed.roles` de cada `Cluster` todos los roles de `component-dependency.md` §4. Cada contraseña sale de la bóveda: un `ExternalSecret` en `vectra-data` para CloudNativePG y otro, con la misma ruta, en el namespace de cada consumidor, porque un `Secret` no se monta desde otro namespace. Las migraciones de U3, U4 y U8 se conectan con su `*_migrator`, crean los objetos y dan los grants; no crean roles.

### INF-U1-03 — Almacenamiento de objetos (Q4)

> **Decisión (issue 26, 2026-11-02), sin implementar:** `minio/minio` y `minio/mc` están archivados y sin mantenimiento. En staging y prod, `model-store`, `validation-datasets`, `loki` y `tempo` pasarán al S3 del banco, si ofrece object lock, versionado y lifecycle; hay que validarlo con el banco. MinIO queda solo en kind. La tabla siguiente describe lo implementado hoy.

| Uso | Dónde | Bucket | Protección |
|---|---|---|---|
| Backups base y WAL | S3 del banco **fuera del sitio** (F70) | `vectra-backups`; base y WAL bajo `<cluster>/` (Barman escribe `<cluster>/<cluster>/base` y `.../wals`; decidido el 2026-11-01) | Cifrado del lado del servidor; object lock en los de `registry-db` (NFR-U1-06) |
| model-store | **MinIO in-cluster** (`vectra-data`) | `model-store`, `validation-datasets` | Versionado; credenciales de solo lectura para KServe y validación |
| Logs | MinIO in-cluster | `loki` | Object lock de 90 días; retención por lifecycle (NFR-U1-30) |
| Trazas | MinIO in-cluster | `tempo` | Lifecycle de 7 días |

Identidades de MinIO, con su política y su Secret por ESO (2026-11-01): `kserve-readonly`, `validation-readonly`, `loki-writer`, `tempo-writer`, `governance-readonly` (F47, solo `model-store`), `model-archive-writer` (F101; lee `model-store`) y `risk-engineer-upload` (NFR-U5-03). Solo en kind, donde MinIO hace de S3 del banco (F118): `registry-checkpoint`, `registry-archive`, `registry-verify`, `restore-drill`, `postgres-backup` y escritura de `model-archive-writer` en `vectra-model-archive`. El bucket `vectra-backups` solo existe en MinIO en kind.
| Archivo WORM de U3 y U4 (**solo kind**) | MinIO in-cluster (F118) | `vectra-registry-checkpoints`, `vectra-registry-archive`, `vectra-model-archive` | Object lock; en staging y prod son del S3 del banco (cuarta revisión de coherencia entre unidades, 2026-10-31) |

- **MinIO distribuido**: 4 pods en el pool `data` (2 por zona) con erasure coding y un volumen por pod (200 Gi inicial). En kind, 4 pods sobre los 4 workers, con volúmenes `local-path`. Tráfico entre pods por F115 (cuarta revisión de coherencia entre unidades, 2026-10-31).
- **Con una zona caída** (seguimiento de la quinta revisión de coherencia, 2026-10-31): con 2 de 4 pods, MinIO se puede leer pero pierde el quórum de escritura. Decisión del MVP: se acepta. Se detienen las escrituras de logs, trazas y artefactos hasta que vuelva la zona, y los modelos ya desplegados siguen sirviéndose. Alerta `MinioWriteQuorumLost`. Se comprueba en el simulacro de zona.
- **Consecuencia**: no aparece ningún egress nuevo para observabilidad ni para KServe. El único destino S3 externo sigue siendo el de backups (F70).
- La pérdida de MinIO (sitio) afecta logs, trazas y el model-store. Los modelos se reconstruyen desde el pipeline del banco y los logs aceptan RPO en horas (§8.4 de requirements). MinIO **no** guarda datos de solicitantes salvo los logs, que no tienen PII (U0, P-U0-04).

## 4. Red

### INF-U1-04 — CNI (Q5)
- kind: **Calico**, con NetworkPolicy de ingress y egress.
- prod/staging: el CNI del banco **solo si** pasa la suite de conectividad de P-U1-01 (un caso permitido y uno bloqueado por flujo, ingress y egress). Si falla, la instalación exige Calico. La prueba es un paso previo obligatorio del runbook de instalación.

### INF-U1-05 — Borde (Q6)
- Solo el api-gateway (U2) tiene un Service `type: LoadBalancer`. Una política de Kyverno, `restrict-loadbalancer`, rechaza cualquier otro.
- prod/staging: el balanceador L4 del banco, o MetalLB si el banco no tiene uno integrado. kind: `cloud-provider-kind`.

### INF-U1-06 — Namespaces de los controladores (Q7)

| Namespace | Contenido | NetworkPolicy |
|---|---|---|
| `cnpg-system` | Operador de CloudNativePG | deny-all + flujos F80, F81 |
| `cert-manager` | cert-manager + webhook | deny-all + F82 |
| `linkerd` | Plano de control de Linkerd (HA) | deny-all + F83, F84 |
| `linkerd-cni` | DaemonSet de CNI | Solo red del host (sin tráfico de pod) |
| `kyverno` | Admission, background y reports controllers | deny-all + F85, F76 |
| `external-secrets` | ESO | deny-all + F86 (kind) / F74 (prod) |
| `vectra-restore-drill` | CronJob y cluster efímero | deny-all + F75 (egress a backups fuera del sitio) + F87 (egress al Pushgateway, 9091) + F80 (ingress desde el operador CloudNativePG hacia el cluster efímero) + F83 (plano de control de Linkerd) + F114 (5432 del cluster efímero) + F98 en kind o F99 en staging y prod (llave pública) + F118 (solo kind) + egress a la API de K12 (cuarta revisión de coherencia entre unidades, 2026-10-31) |
| `vault` (solo kind) | Vault dev | deny-all + F86 |
| `envoy-gateway-system` | Controlador de Envoy Gateway (U2, INF-U2-02; binding K14) | deny-all + F95 (agregado el 2026-10-08; ingress desde Envoy, cuarta revisión de coherencia entre unidades, 2026-10-31) |

- MinIO se despliega en `vectra-data` (Q7), junto a PostgreSQL.
- Los flujos de cada namespace se declaran en `flows.yaml` y se generan como los demás (P-U1-01).

## 5. Observabilidad (Q8, Q9)

### INF-U1-07 — Componentes y retención

| Componente | Despliegue | Retención | Almacenamiento |
|---|---|---|---|
| Prometheus | 2 réplicas (HA), por zona | 30 días | PVC 100 Gi por réplica |
| Alertmanager | 3 réplicas en cluster (gossip, F116) | — | — |
| Loki | Modo simple escalable, por zona | 90 días (object lock + lifecycle) | MinIO `loki` |
| Tempo | Modo distribuido mínimo | 7 días | MinIO `tempo` |
| OTel Collector | Deployment, 2 réplicas | — | — |
| Pushgateway | 1 réplica con `--persistence.file` y `--persistence.interval=1m`, `vectra-normal`; `Server` y `HTTPRoute` de Linkerd por identidad y método (P-U1-13; antes «sin persistencia», revisión de coherencia entre unidades, 2026-10-10) | Hasta el siguiente push o el borrado del grupo; sobrevive a un reinicio | PVC de 1 GiB (P-U1-13) — (F87, F106, F112 y F113 de entrada, F88 de scrape; F106 = CronJob de bias desde `vectra-app`, revisión del FD de U9, 2026-10-08) |
| **Grafana Alloy** | DaemonSet (logs de stdout → Loki) | — | — |
| Grafana | 1 réplica con `Recreate`, dashboards como código | — | SQLite en un PVC de 1 GiB: los permisos de carpeta y la cuenta de servicio se guardan en la base y no se reconstruyen de Git, así que no puede ser efímera ni repartirse entre réplicas sin base compartida (cuarta revisión de coherencia entre unidades, 2026-10-31) |
| Job y CronJob `grafana-folder-permissions` | Aplica y compara los permisos de carpetas de `folder-permissions.yaml` por la API de Grafana (F110); `GrafanaFolderPermissionsDrift` si difieren | — | Sin estado; la fuente es Git (agregado en revisión de coherencia entre unidades, 2026-10-10; FD de U11, BR-U11-13) |

### INF-U1-08 — Relación con el banco (Q9)
- El stack es **propio** de Vectra y no comparte almacenamiento con el banco.
- Si el banco quiere métricas agregadas, **las lee** desde su lado: federación de Prometheus (`/federate`) con un usuario de solo lectura, a través del api-gateway (F09, deshabilitado por defecto). Vectra no hace remote-write.
- Las alertas salen solo por F72, incluido el latido `Watchdog`.

## 6. Seguridad de la infraestructura

### INF-U1-09 — Imágenes (Q10)
- staging/prod: **solo** el registro interno del banco, alimentado desde GHCR por un proceso del banco. kind: `kind-registry`.
- La política de Kyverno `verify-images` exige la firma Cosign y un registro permitido (`registro.banco.internal/vectra/*` en prod y staging, `registro.vectra.internal/*` para las imágenes propias; `kind-registry:5000/*` en kind, por `restrict-registries`). `verify-images` se instala solo en staging y prod. Para verificar firmas, Kyverno consulta el registro (F76) (revisión de consistencia entre unidades, 2026-11-01).

### INF-U1-10 — Secretos
- ESO + Vault en kind (in-cluster, F86); ESO + la bóveda del banco en staging/prod (egress F74).
- ESO solo escribe Secrets en los namespaces de Vectra que lo declaran (binding K11). Ningún servicio de negocio lee Secrets por la API.
- **Decisión (issue 26, 2026-11-02), sin implementar:** el controlador de ESO necesita `list` y `watch` sobre `secrets` en todo el clúster, y K11 no los da. En staging y prod se usará **una instancia de ESO por namespace**, con `scopedRBAC` y un `SecretStore` por namespace en vez de `vectra-store`. Este modo no se ha probado: si tampoco arranca, la decisión se revisa. En kind sigue `platform/secrets/eso-rbac-secrets-read-kind.yaml`, que lee todos los Secret. Hasta implementarla, ESO no arranca en staging ni prod.

## 7. Cambios aplicados a `component-dependency.md`

Registrados en `audit.md` (2026-10-03):

| Sección | Cambio |
|---|---|
| §0 Puertos | `9000/TCP` pasa a ser «MinIO (model-store, Loki, Tempo)»; se agrega `9091/TCP` (Pushgateway) |
| §1 Namespaces | `vectra-data` incluye MinIO; se agregan `vectra-restore-drill` y los namespaces de controladores |
| §9 Fronteras | Rangos actualizados: egress F70–F76, API de Kubernetes K01–K13 |
| `unit-of-work.md` U1 | Lista de flujos y bindings de U1 actualizada |
| `application-design.md` | Rangos del índice y de SECURITY-06 actualizados (F01–F88, K01–K13) |
| §2.1 | F09: federación de Prometheus para el banco (opcional, deshabilitado por defecto) |
| §2.6 | F66 Loki → MinIO, F67 Tempo → MinIO; agente de logs = Grafana Alloy |
| §2.7 (nueva) | Flujos de plataforma F80–F88 (F87/F88: Pushgateway, según `platform-foundation-infrastructure-design-review-questions.md` Q1=A) |
| §3 | K06 = CloudNativePG; nuevos K07–K13 |
| §5 | F71 precisado (espejo en staging/prod); nuevos egress F74 (ESO → bóveda), F75 (restore drill → backups fuera del sitio, solo lectura), F76 (Kyverno → registro de imágenes) |

## 8. Cumplimiento de extensiones (Infrastructure Design U1)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-08 | Cumple | INF-U1-01 (2 zonas, nodos libres para reclonar), MinIO repartido por zona |
| RESILIENCY-09 | Cumple | Tamaños iniciales con ajuste por la prueba de carga |
| RESILIENCY-11 / 12 | Cumple | INF-U1-03 (backups fuera del sitio, object lock) |
| SECURITY-01 | Cumple | StorageClass cifrada; backups cifrados; en kind se documenta la excepción |
| SECURITY-06 | Cumple | K07–K13 con alcance mínimo |
| SECURITY-07 | Cumple | INF-U1-04, 06 |
| SECURITY-10 | Cumple | INF-U1-09 |
| AUTONOMIA-01 | Cumple | El banco replica Git e imágenes; Vectra no empuja; los cambios entran por sync manual |
| AUTONOMIA-05 | Cumple | INF-U1-03 (sin egress nuevo para observabilidad ni KServe); los egress nuevos (F74–F76) no llevan datos de solicitantes |
