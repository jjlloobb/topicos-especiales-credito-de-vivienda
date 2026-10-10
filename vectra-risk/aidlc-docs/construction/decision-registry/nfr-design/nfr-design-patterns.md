# Patrones de NFR Design — U3 `decision-registry`

Decisiones del plan (`decision-registry-nfr-design-plan.md`, Q1–Q7 = A). Los IDs `P-U3-xx`
se referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind
las ejecuta el operador después de un PR aprobado (AUTONOMIA-01).

---

## 1. Resiliencia

### P-U3-01 — Readiness con réplica síncrona (Q1)
- El rol `registry_health` (`pg_monitor`, sin acceso a `registry_entries`) ejecuta:
  - `SELECT 1`;
  - `SELECT count(*) FROM pg_stat_replication WHERE state = 'streaming' AND sync_state IN ('sync', 'quorum')` ≥ 1. Con `minSyncReplicas = 1` y `maxSyncReplicas = 2`, CloudNativePG configura `ANY 1 (…)` y PostgreSQL informa `quorum`, no `sync`; contar solo `sync` dejaría el servicio fuera de balanceo con las dos réplicas sanas (segunda revisión del Infrastructure Design de U10, 2026-10-10).
- Resultado cacheado 5 s (P-U1-04).
- Sin standby síncrono → readiness falla → el pod sale del balanceo → los llamadores reciben error de conexión o 503 y lo tratan como `registry_unavailable` (fail-closed, BR-U0-02) de inmediato.
- Liveness: solo el proceso.
- **Verificación**: Testcontainers con primaria + standby: con el standby detenido, `/readyz` (8081) = 503 en ≤ 5 s; en kind, el escenario de NFR-U1-03.
- **Satisface**: NFR-U3-11; RESILIENCY-06; P-U1-04.

### P-U3-02 — Tiempos límite del append (Q2)

| Límite | Valor | Al vencer |
|---|---|---|
| `lock_timeout` (advisory lock) | 1 s | 503 `dependency_unavailable` |
| `statement_timeout` (incluye el commit síncrono) | 2 s | 503 `dependency_unavailable` |
| Timeout total del handler | 2,5 s | 503 `dependency_unavailable` |

- El servicio **no** reintenta por su cuenta. El llamador reintenta con la **misma** `idempotency_key` (BR-U3-06), y un commit que quedó escrito pero no se confirmó a tiempo se resuelve en ese reintento con el ack original.
- **Verificación**: prueba de integración con el standby pausado → 503 en ≤ 2,5 s; el reintento con la misma llave, una vez reanudado el standby, devuelve el ack original y hay **una** sola fila.
- **Satisface**: RESILIENCY-10; SECURITY-15; NFR-U3-20.

### P-U3-03 — Checkpoint por CronJob (Q3)
- `CronJob registry-checkpoint`: cada hora, `concurrencyPolicy: Forbid`, prioridad `vectra-high`, sidecar nativo de Linkerd (P-U1-05).
- Ejecuta `vectra-registry checkpoint`:
  1. lee la cabeza en la primaria;
  2. pide la firma a la bóveda (Vault Transit; solo con el digest);
  3. hace append por el mismo camino del servicio (rol `registry_app`, lock, hash), con `idempotency_key = UUIDv5(NS_CHECKPOINT, "checkpoint:<hora UTC>")`, porque la columna es `uuid` (BR-U3-06; segunda revisión del FD de U9, 2026-10-08);
  4. exporta al bucket WORM y verifica que el objeto quedó escrito.
- Su ServiceAccount es la **única** con la política de firma en la bóveda. La del servicio de la API no puede firmar.
- **Verificación**: dos ejecuciones manuales en la misma hora → un solo checkpoint; prueba de que la ServiceAccount de la API recibe 403 de la bóveda al intentar firmar.
- **Satisface**: BR-U3-08; NFR-U3-12, 40.

### P-U3-04 — Aislamiento de pools (Q7)

| Pool | Conexiones | Servidor | Rol | Uso | Timeout de espera |
|---|---|---|---|---|---|
| `append` | 2 | Primaria | `registry_app` | Appends | 500 ms |
| `dossier` | 1 | Primaria | `registry_app` (`SELECT`, y el `INSERT` de una solicitud de verificación en `integrity_checks`) | Expediente; registro de una solicitud de verificación (BR-U3-13b; revisión del Infrastructure Design de U10, 2026-10-10) | 2 s |
| `projections` | 1 | Réplica `-ro` | `registry_verifier` | Proyecciones (incluida `monitoring_daily`, agregada en el servidor, y el gauge del atraso del agregador cada 60 s; segunda revisión del FD de U9, 2026-10-08) | 2 s |
| `health` | 1 | Primaria | `registry_health` | Readiness (P-U3-01) | 1 s |

- Total por réplica: **5** (P-U1-08). Corregido el 2026-10-03 en el Infrastructure Design de U3 (Q5): la versión anterior tenía un pool `read` que apuntaba a dos servidores y, con la readiness, sumaba 6 conexiones. Dos conexiones de append alcanzan porque los appends se serializan en el advisory lock (BR-U3-04); más conexiones solo harían cola en el lock. Métrica `vectra_registry_pool_wait_seconds{pool}` y alerta `RegistryAppendPoolSaturated` (SEV2) si la espera p95 del pool `append` supera 100 ms durante 5 min.
- **Verificación**: prueba de carga en kind con expedientes concurrentes mientras corre el append a 50 entradas/s → el p95 del append sigue en ≤ 50 ms.
- **Satisface**: RESILIENCY-10 (bulkhead); NFR-U3-20, 21.

## 2. Escalabilidad y rendimiento

### P-U3-05 — Verificación en la réplica (Q4)
- `incremental`, `nightly`, `full` y el export del archivo leen del servicio `-ro` de CloudNativePG con `registry_verifier`.
- Cada informe declara hasta qué `seq` verificó (`to_seq`, la cabeza que ve la réplica).
- El expediente (verificación `range`) usa la primaria para incluir las entradas recién escritas.
- `full` mensual: CronJob fuera del horario operativo (domingo 02:00), prioridad `vectra-low`.
- **Verificación**: prueba de integración que verifica en el standby con retraso y comprueba que `to_seq` corresponde a la cabeza del standby.
- **Satisface**: NFR-U3-22, 23, 33.

### P-U3-06 — Particiones por migración (Q6)
- La migración inicial crea las particiones (por rango de `seq`) del año en curso y de los **dos siguientes**, con un tamaño estimado por año según NFR-U3-30 (3,6 M entradas) y un margen de 3×.
- Cada año, un PR de migración agrega una partición (F44, sync aprobado).
- Hay una partición **`DEFAULT`** como red de seguridad: si recibe filas, alerta `RegistryDefaultPartitionUsed` (**SEV1**), porque significa que una partición faltó.
- `RegistryPartitionMissing` (SEV2) avisa 30 días antes de necesitar una partición inexistente (NFR-U3-31).
- **Verificación**: prueba con Testcontainers que inserta en el borde de cada partición y una fila fuera de rango (va a `DEFAULT` y dispara la métrica); `promtool test rules` para las dos alertas.
- **Satisface**: NFR-U3-31; AUTONOMIA-01 (sin DDL en tiempo de ejecución).

## 3. Seguridad e integridad

### P-U3-07 — Archivo de 10 años (Q5)
- Job mensual `registry-archive` (prioridad `vectra-low`):
  1. lee de la réplica las entradas del mes anterior **en tramos** de ≤ 10 000 entradas por `seq`, cada uno en su transacción corta, y escribe el archivo de forma incremental; un tramo cancelado por un conflicto de recuperación (`max_standby_streaming_delay = 2s`, BR-U3-13b) se reintenta hasta 3 veces (segunda revisión del Infrastructure Design de U10, 2026-10-10);
  2. escribe `registry-{yyyy-mm}.ndjson.zst`, con una línea por entrada (`seq`, `prev_hash`, `hash`, `canonical` en base64);
  3. arma el manifiesto `{from_seq, to_seq, head_hash, checkpoints, sha256, contract_versions}` y lo firma con la bóveda;
  4. sube los dos al bucket WORM de 10 años, los **vuelve a descargar** y ejecuta `vectra-registry verify --source archive` (sin base de datos);
  5. solo con `exit 0` da el mes por cerrado; si no, `ArchiveExportFailed` (SEV2).
- El formato no depende de la versión de PostgreSQL.
- **Verificación**: prueba de extremo a extremo con MinIO de Testcontainers: export → descarga → verificación `exit 0`; un byte alterado en el archivo → `exit 1`.
- **Satisface**: NFR-U3-04; SECURITY-13; RESILIENCY-11, 12.

### P-U3-08 — Identidades y permisos

| Identidad | Base | Bóveda | Bucket WORM |
|---|---|---|---|
| Servicio (API) | `registry_app` (pools `append` y `dossier`), `registry_verifier` (pool `projections` en la réplica), `registry_health` (pool `health`) | Ninguno | Ninguno |
| `registry-checkpoint` | `registry_app` | Firma (Transit) | Escritura en `registry-checkpoints` |
| `registry-verify` (CronJobs, incluido `registry-verify-ondemand`) | `registry_verifier` en la réplica `-ro` (lectura) y `registry_ondemand` en la primaria `-rw` (solo el estado en `integrity_checks`; segunda revisión del Infrastructure Design de U10, 2026-10-10) | Lectura de la llave pública | Lectura de `registry-checkpoints` |
| `registry-archive` | `registry_verifier` | Firma (Transit) | Escritura en `registry-archive` |
| `registry-aggregator` | `registry_aggregator` (BR-U3-17; segunda revisión del FD de U9, 2026-10-08) | Ninguno | Ninguno |

- Las credenciales de la base y de los buckets las entrega ESO. Sin comodines en las políticas de la bóveda.
- **Verificación**: pruebas de autorización por identidad (cada una recibe 403 fuera de su fila); `conftest` sobre los RBAC y las políticas versionadas de la bóveda.
- **Satisface**: SECURITY-06, 12; NFR-U3-40, 42.

## 4. Observabilidad

### P-U3-09 — Alertas de U3

| Alerta | Severidad | Origen |
|---|---|---|
| `RegistryChainBroken` | SEV1 | BR-U3-13, 14 |
| `RegistryDefaultPartitionUsed` | SEV1 | P-U3-06 |
| `RegistryVerificationFailed` | SEV2 | BR-U3-13 |
| `CheckpointMissing` / `CheckpointExportFailed` | SEV2 | BR-U3-08; P-U3-03 |
| `ArchiveExportFailed` | SEV2 | P-U3-07 |
| `RegistryPartitionMissing` | SEV2 | P-U3-06 |
| `RegistryAppendPoolSaturated` | SEV2 | P-U3-04 |
| `RegistryVolumeFillForecast` | SEV3 | NFR-U3-32 |
| `RegistryGrowthAboveForecast` | SEV3 | NFR-U3-34 |
| `RegistryEntryLarge` | SEV3 | BR-U3-07 |
| `RegistryOnDemandCheckFailed` | SEV3 | BR-U3-13b: una fila pasa a `fallida`, del CRO o mensual (`increase(vectra_registry_integrity_checks_failed_total[15m]) > 0`, sin `for`) |
| `RegistryOnDemandCheckStuck` | SEV3 | BR-U3-13b: una fila `pendiente` con más de 10 min (`vectra_registry_integrity_check_pending_age_seconds > 600`, `for: 5m`): el CronJob no corre |
| `RegistryFullVerificationOverdue` | SEV3 | BR-U3-13b: la última `full` `terminada` tiene más de 35 días (`vectra_registry_last_full_verification_age_seconds > 3024000`) (segunda revisión del Infrastructure Design de U10, 2026-10-10) |

**Emisor de las métricas de la verificación bajo demanda** (segunda revisión del Infrastructure Design de U10, 2026-10-10): `decision-registry-service` las calcula cada 60 s con el pool `projections` (réplica), junto al gauge del atraso del agregador, leyendo `integrity_checks`: `vectra_registry_integrity_check_pending_age_seconds` (la `pendiente` más antigua, 0 si no hay), `vectra_registry_last_full_verification_age_seconds` y `vectra_registry_integrity_checks_failed_total` (número de filas `fallida`; crece de forma monótona porque las filas no se borran, así que Prometheus lo trata como un contador). Los CronJobs no publican métricas propias de esto: el estado vive en la tabla.
| `MonitoringAggregatorStale` | SEV2 | BR-U3-17: `max(vectra_registry_monitoring_lag_seconds) > 1800` durante 5 min, o `absent()` de la serie durante 15 min (segunda revisión del FD de U9, 2026-10-08) |

- Toda alerta tiene `runbook_url` (P-U1-10).
- **Verificación**: `promtool test rules decision-registry/observability/rules/tests/*.yaml` y el test de runbooks de U1.

## 5. Cumplimiento de extensiones (NFR Design U3)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | P-U3-09 |
| RESILIENCY-06 | Cumple | P-U3-01 |
| RESILIENCY-09 | Cumple | P-U3-05, 06 |
| RESILIENCY-10 | Cumple | P-U3-02 (timeouts), P-U3-04 (bulkhead) |
| RESILIENCY-11 / 12 | Cumple | P-U3-07 |
| SECURITY-06 | Cumple | P-U3-08 |
| SECURITY-12 | Cumple | P-U3-03, 08 (solo la identidad de checkpoint firma) |
| SECURITY-13 | Cumple | P-U3-07 (archivo firmado y verificado tras subirlo) |
| SECURITY-14 | Cumple | P-U3-09 |
| SECURITY-15 | Cumple | P-U3-01, 02 (sin réplica o sin commit a tiempo → fail-closed en el llamador) |
| AUTONOMIA-01 | Cumple | P-U3-06 (sin DDL en tiempo de ejecución) |
| AUTONOMIA-02 | Cumple | Cada patrón, de P-U3-01 a P-U3-09, tiene su «Verificación» |
| AUTONOMIA-05 | Cumple | P-U3-08: el servicio de la API, que atiende casi todo el tráfico, no tiene acceso a la bóveda ni a los buckets WORM, así que no tiene ningún destino de salida propio. Las identidades que sí tienen salida solo envían a la bóveda el digest a firmar (P-U3-03, 07). El archivo de 10 años sí contiene datos seudonimizados: si su bucket queda fuera del clúster, debe seguir el precedente de F70 (destino dentro de la infraestructura del banco y cifrado). Lo decide el Infrastructure Design de U3 |
| AUTONOMIA-06 | Cumple | P-U3-01, 02: el registro nunca confirma sin commit síncrono |
