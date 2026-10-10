# Arquitectura de despliegue — U3 `decision-registry`

Vista de producción (staging igual; kind con MinIO y Vault dev en lugar del S3 y la bóveda
del banco).

---

## 1. Topología

### Diagrama

```mermaid
flowchart TB
    subgraph site["Sitio del banco"]
        subgraph zoneA["Zona A"]
            svcA["registry-service"]
            pgA["registry-db instancia"]
        end
        subgraph zoneB["Zona B"]
            svcB["registry-service"]
            pgB["registry-db instancia"]
        end
        jobs["CronJobs: checkpoint, verify, archive, aggregator; Jobs con runId: rebuild y reset"]
    end
    s3["S3 del banco fuera del sitio: checkpoints y archive WORM"]
    vault["Boveda del banco Transit"]

    svcA --> pgA
    svcB --> pgA
    svcA --> pgB
    svcB --> pgB
    pgA <--> pgB
    jobs --> pgA
    jobs --> pgB
    jobs --> s3
    jobs --> vault
```

### Alternativa en texto

```text
Sitio del banco
  Zona A / Zona B: decision-registry-service (2..6, spread por zona)
                   registry-db (3 instancias, réplica síncrona; -rw primaria, -ro réplicas)
  Servicio -> -rw: append (2), dossier (1), health (1)   ; -> -ro: projections (1)
  CronJobs:
    registry-checkpoint (hora)  -> -rw ; bóveda (F99, firma) ; S3 checkpoints (F77)
    registry-verify-* (15 min / noche / mes) -> -ro ; S3 checkpoints (F79, lectura)
    registry-archive (mes)      -> -ro ; bóveda (F99) ; S3 archive (F78)
    registry-aggregator (5 min) -> -rw (F107; tablas derivadas de monitoreo para U9)
    Jobs de reconstrucción con `runId` del runbook monitoring-rebuild: registry-aggregator-reset -> -rw (F108) ;
      registry-aggregator-rebuild -> -rw (F107)
Fuera del sitio: S3 del banco (WORM COMPLIANCE, 10 años) ; bóveda del banco (Transit, llave no exportable)
```

## 2. Orden de instalación (waves de U1)

| Wave | Componente de U3 | Requisito previo verificable |
|---|---|---|
| 2 | `registry-db` (U1) | `Cluster in healthy state` con standby síncrono |
| 5 | Job de migración (hook): esquema, particiones, roles y génesis | `SELECT seq, entry_type FROM registry_entries WHERE seq = 0` → `genesis` |
| 5 | `decision-registry-service` y CronJobs | `/readyz` = 200; un `vectra-registry verify --mode full` manual → `exit 0` |
| 6 | Application aparte `decision-registry-rebuild` (vacía salvo durante una reconstrucción con `runId`) | `argocd app get decision-registry-rebuild` → `Synced`; un sync o rollback de `decision-registry` no la espera (revisión del Infrastructure Design de U9, 2026-10-10) |

## 3. Escenarios de resiliencia (RESILIENCY-14 = C)

| Escenario | Resultado esperado |
|---|---|
| Fallo de zona | Escrituras bloqueadas mientras CloudNativePG reclona (NFR-U1-03); readiness falla (P-U3-01); los llamadores salen como fail-closed; nunca un ack sin commit síncrono |
| Pérdida del sitio | Restore (U1) + `verify --mode full` contra los checkpoints del S3 externo (sobreviven, INF-U3-01) |
| Bóveda caída | Appends normales; checkpoint atrasado → `CheckpointMissing` |
| S3 externo caído | Checkpoint en la cadena; exportación reintentada → `CheckpointExportFailed`; archivo del mes pendiente → `ArchiveExportFailed` |
| Manipulación directa en la base | `incremental` o `nightly` → `RegistryChainBroken` (SEV1) por checkpoint |
| Agregador suspendido más de 30 min (quinta revisión del FD de U9, 2026-10-10) | `MonitoringAggregatorStale` (SEV2); las corridas de bias fallan por atraso y, a 1 h, `MonitoreoSesgoDetenido`; al reanudar, el agregador itera hasta la cabeza y el atraso vuelve a 0 |
| Tablas derivadas dañadas o borradas (quinta revisión del FD de U9, 2026-10-10) | Runbook `monitoring-rebuild` (PR que fija `monitoringRebuild.runId` y sync manual; Argo CD crea los Jobs; *advisory lock*; aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10): `aggregator reset` con `registry_migrator` y un Job de reconstrucción con `runId` `aggregator run --until-head` que reconstruye los últimos 181 días en ≤ 1 h (NFR-U3-24) (sexta revisión del FD de U9, 2026-10-10); mientras tanto bias falla por atraso, sin congelar con datos parciales; el runbook silencia `MonitoringAggregatorStale` y `MonitoreoSesgoDetenido` (U9) durante 2 h, con el `runId` en el silencio (revisión del plan de tareas de U9, 2026-10-10) |

Se documentan aquí y se ejecutan en Operations.
