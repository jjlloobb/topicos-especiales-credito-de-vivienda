# Componentes lógicos — U1 `platform-foundation`

Componentes de plataforma que U1 entrega como charts y manifiestos en
`vectra-risk-gitops`. La asignación final a namespaces, recursos y flujos la hace el
Infrastructure Design de U1.

---

## 1. Inventario

| Componente | Función | Patrón / NFR | Wave | PriorityClass |
|---|---|---|---|---|
| CloudNativePG (operador) | Ciclo de vida de PostgreSQL, failover, backups | NFR-U1-02, 05 | 0 | `vectra-critical` |
| Clusters PostgreSQL ×4 | `case-db`, `governance-db`, `registry-db`, `keycloak-db` (3 instancias c/u) | NFR-U1-02..06 | 2 | `vectra-critical` |
| MinIO in-cluster (todos los entornos; INF-U1-03) | Almacenamiento S3: model-store, `validation-datasets`, Loki, Tempo. Los backups y el WAL van al S3 del banco fuera del sitio (F70), no a MinIO (precisado el 2026-10-08) | Q6; INF-U1-03 | 2 | `vectra-normal` |
| cert-manager | CA interna, certificados del borde, de PostgreSQL y de Linkerd | P-U1-03 | 0 | `vectra-critical` |
| Linkerd (+ linkerd-cni) | mTLS y autorización por identidad | P-U1-02 | 0–1 | `vectra-critical` |
| Kyverno | Admisión y políticas | P-U1-06, 09 | 0–1 | `vectra-critical` |
| External Secrets Operator | Secrets desde la bóveda (Vault en kind) | NFR-U1-24 | 0 | `vectra-high` |
| Vault (solo kind) | Bóveda de desarrollo | NFR-U1-24 | 2 | `vectra-normal` |
| Controlador de KServe | Reconciliar InferenceServices (K05) | INCEPTION | 0 | `vectra-high` |
| Prometheus + reglas | Métricas, SLO, alertas | P-U1-07, 11 | 4 | `vectra-normal` |
| Alertmanager | Enrutamiento por severidad, `Watchdog` por F72 | P-U1-07, 10 | 4 | `vectra-normal` |
| Loki + agente de logs | Logs con object lock, 90 días | NFR-U1-30 | 4 | `vectra-normal` |
| Tempo + OTel Collector | Trazas, 7 días | NFR-U1-31 | 4 | `vectra-normal` |
| Pushgateway | Métricas de jobs batch (`restore-drill`, F87; CronJob de bias de U9, F106, revisión del FD de U9, 2026-10-08) | P-U1-05 | 4 | `vectra-normal` |
| Grafana | Dashboards como código | NFR-U1-33 | 4 | `vectra-normal` |
| Argo CD | GitOps con sync manual | P-U1-12 | 0 | `vectra-normal` |
| `restore-drill` (CronJob) | Simulacro semanal de restore | P-U1-05 | 5 | `vectra-low` |
| Generador de red (`flows.yaml` + `generate.py`) | NetworkPolicies, Linkerd authz, pruebas de conectividad | P-U1-01, 02 | CI | — |
| Workflows reutilizables de CI | tests, supply-chain, evidence, forbidden-steps, policies | NFR-U1-40..42 | CI | — |
| Runbooks y plantillas | Runbook por alerta, COE | P-U1-10 | Repo | — |

## 2. Dependencias

### Diagrama

```mermaid
flowchart TB
    subgraph ci["CI y repositorios"]
        flows["flows.yaml"]
        gen["generate.py"]
        wf["workflows reutilizables"]
        gitops["vectra-risk-gitops"]
    end
    subgraph wave0["Wave 0-1: control"]
        cnpg["CloudNativePG"]
        certm["cert-manager"]
        linkerd["Linkerd + CNI"]
        kyverno["Kyverno"]
        eso["External Secrets"]
        kserve["KServe controller"]
        argocd["Argo CD"]
    end
    subgraph wave2["Wave 2-3: datos e identidad"]
        pg["PostgreSQL x4"]
        s3["Almacenamiento S3"]
        vault["Boveda de secretos"]
    end
    subgraph wave4["Wave 4: observabilidad"]
        prom["Prometheus"]
        am["Alertmanager"]
        loki["Loki"]
        tempo["Tempo + OTel"]
        pushgw["Pushgateway"]
    end
    bank["Canal del banco F72"]
    drill["restore-drill"]
    biascj["CronJob de bias U9"]

    flows --> gen
    gen --> gitops
    wf --> gitops
    gitops --> argocd
    argocd --> wave0
    cnpg --> pg
    pg --> s3
    certm --> linkerd
    certm --> pg
    eso --> vault
    loki --> s3
    tempo --> s3
    prom --> am
    am --> bank
    drill --> s3
    drill --> pushgw
    biascj -->|"F106"| pushgw
    prom --> pushgw
```

### Alternativa en texto

```text
CI:   flows.yaml -> generate.py -> NetworkPolicies + Linkerd authz + pruebas -> vectra-risk-gitops
      workflows reutilizables -> evidencia en el PR (sin tocar el clúster)
GitOps: vectra-risk-gitops -> Argo CD (sync manual, waves 0..6)
Wave 0-1: CloudNativePG, cert-manager, Linkerd (+CNI), Kyverno, ESO, KServe controller
Wave 2-3: PostgreSQL x4 -> S3 (backups + WAL, archive_timeout 60 s)
          cert-manager -> certificados de Linkerd, borde y PostgreSQL
          ESO -> bóveda (Vault en kind; bóveda del banco en prod)
Wave 4:   Loki, Tempo -> S3 ; Prometheus -> Alertmanager -> canal del banco (F72, Watchdog)
Wave 5:   restore-drill -> lee S3, crea cluster efímero, verify_chain, empuja métricas al Pushgateway (F87); Prometheus lo lee (F88)
          CronJob de bias (U9) -> empuja las métricas de cada corrida al Pushgateway (F106)
          registry-aggregator (U3) -> tablas derivadas de monitoreo en registry-db -rw (F107)
```

## 3. Métricas y alertas que introduce U1

| Alerta | Severidad | Patrón |
|---|---|---|
| `WalArchiveStale` (> 5 min) | SEV1 | NFR-U1-05 |
| `BackupFailed` | SEV1 | NFR-U1-05 |
| `RestoreDrillFailed` / `RestoreDrillMissing` | SEV1 | P-U1-05 |
| `RegistryDbWritesBlocked` (sin réplica síncrona) | SEV1 | NFR-U1-03 |
| `KyvernoUnavailable` / `LinkerdControlPlaneDown` | SEV1 | P-U1-06 |
| `SingleZoneOperation` | SEV2 | NFR-U1-32 |
| `PostgresReplicaLag` | SEV2 | NFR-U1-32 |
| `CertificateExpiringSoon` | SEV2 / SEV1 | P-U1-03 |
| `RecommendationSLOBurnFast` / `Slow` | SEV2 / SEV3 | P-U1-11 |
| `FailClosedPersistente` (`max(vectra_cases_failclosed_persistent) > 0` durante 1 min; gauge de U8) | SEV2 | P-U1-11; US-112 (tercera revisión de coherencia entre unidades, 2026-10-10) |
| `AuthDeniedBurst` | SEV2 | SECURITY-14; **definida en U2** (P-U2-09, con sus eventos de Keycloak y los 401/403 de U0): la `PrometheusRule` de U1 no la incluye, para no duplicarla (segunda revisión de coherencia entre unidades, 2026-10-10) |
| `PostgresConnectionsHigh` (> 80 %) | SEV3 | P-U1-08 |
| `PostgresVolumeUsageHigh` (> 80 % SEV3; > 90 % o sin serie SEV2; agregada el 2026-10-08) | SEV3 / SEV2 | INF-U1-02 |
| `HPAMaxedOut` | SEV3 | NFR-U1-32 |
| `PushgatewayDown` (`up{job="pushgateway"} == 0` o `absent()` durante 5 min; sin él no llegan las métricas de `restore-drill` ni de bias; tercera revisión del FD de U9, 2026-10-10) | SEV2 | P-U1-05 |
| `GrafanaFolderPermissionsDrift` | SEV3 | Los permisos de una carpeta de Grafana difieren de `folder-permissions.yaml`; los compara el CronJob de permisos de carpetas (F110; U11 BR-U11-13, U9 INF-U9-05). Runbook `grafana-folder-permissions-drift` (revisión de coherencia entre unidades, 2026-10-10) |
| `Watchdog` | latido | P-U1-07 |

## 4. Pendiente para Infrastructure Design de U1

**Todos resueltos por el Infrastructure Design de U1** (anotado el 2026-10-08):

- ~~Namespaces y bindings K0x de cert-manager, Linkerd, Kyverno y ESO~~ → INF-U1-06; bindings K07–K14 en §3 de `component-dependency.md`.
- ~~Destino del almacenamiento S3 en producción~~ → INF-U1-03: MinIO in-cluster para model-store, Loki y Tempo (sin egress nuevo); backups y WAL en el S3 del banco fuera del sitio (F70).
- ~~Egress de ESO hacia la bóveda del banco~~ → F74.
- ~~`max_connections` por cluster~~ → INF-U1-02.
- ~~CNI de kind y agente de logs~~ → Calico (INF-U1-04) y Grafana Alloy (INF-U1, K13).
