# Infrastructure Design — U4 `governance`

Decisiones del plan (`governance-infrastructure-design-plan.md`, Q1–Q2 = A). Se apoya en la
infraestructura compartida de U1. Los IDs `INF-U4-xx` se referencian en el plan de tareas.

---

## 1. Cómputo (Q1)

### INF-U4-01 — Recursos y escalado

| Componente | Requests | Limits | Escalado / límite | PriorityClass |
|---|---|---|---|---|
| `governance-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 %; spread por zona; PDB `minAvailable: 1` | `vectra-high` |
| Job de migración | 100m / 128 MiB | 500m / 256 MiB | `activeDeadlineSeconds: 600` | `vectra-normal` |
| `model-validation-job` | (NFR-U4-23) | 2 CPU / 4 GiB | `activeDeadlineSeconds: 7200` | `vectra-low` |
| `model-archive` (CronJob diario) | 100m / 256 MiB | 500m / 512 MiB | `activeDeadlineSeconds: 3600`; `concurrencyPolicy: Forbid`; sidecar nativo de Linkerd | `vectra-low` |

- **Aporte a la cuota de `vectra-app`** (NFR-U1-13; revisión de coherencia entre unidades, 2026-10-10). Peor momento: el servicio en el máximo del HPA más su `maxSurge` (7 pods), la migración y `model-archive`, con el proxy de P-U1-14 y el 30 %:

  | | Requests | Limits |
  |---|---|---|
  | Servicio: 7 × (250m + 100m) y 7 × (256 + 20) MiB | 2,45 CPU / 1 932 MiB | 10,5 CPU / 4 480 MiB |
  | Migración y `model-archive`, con el proxy | 0,4 CPU / 424 MiB | 2 CPU / 1 024 MiB |
  | **Total + 30 %** | **≈ 3,71 CPU / 2,99 GiB** | **≈ 16,25 CPU / 6,99 GiB** |

  `model-validation-job` corre en `vectra-staging` y entra en esa cuota (INF-U4-05), no en esta.
- La imagen del servicio incluye `tzdata` para `America/Bogota` (P-U4-05).
- `governance-db` (INF-U1-02, `max_connections` 50): 6 réplicas × 5 (P-U4-04) + migración + `model-archive` + operador ≈ 37.

## 2. Archivo de artefactos de modelo (Q2; NFR-U4-31)

### INF-U4-02 — `model-archive`
- CronJob diario que busca las versiones que llegaron alguna vez a `activo` y todavía no tienen `archived_uri`. Para cada una:
  1. lee el artefacto y el explicador del bucket `model-store` (MinIO in-cluster, F101);
  2. los sube a `vectra-model-archive/{model_version_id}/` en el S3 del banco fuera del sitio (F100), con object lock **`COMPLIANCE` de 10 años** (el mismo destino y modo que los buckets de U3, INF-U3-01);
  3. descarga lo subido y verifica el SHA-256 contra `artifact_sha256` y `explainer_sha256`;
  4. solo si coinciden, registra `archived_uri` y `archived_at` en la versión (F102, rol `gov_archiver`).
- El bucket `vectra-model-archive` tiene **cifrado del lado del servidor** habilitado por defecto, y todo acceso va por **TLS** (las solicitudes sin TLS se rechazan por política del bucket). Igual que INF-U3-01, pero configurado en este bucket: el cifrado se fija bucket por bucket y no se hereda por compartir el destino.
- No lleva datos de solicitantes: solo artefactos de modelo.
- El servicio de la API **no** hace este egress (AUTONOMIA-05 aplicado por identidad, como en U3).
- Alerta `ModelArchivePending` (SEV2) si una versión `activo` o `inactivo` pasa 48 h sin `archived_uri`.
- **[VERIFICAR]** con el área de almacenamiento del banco que su S3 soporta `COMPLIANCE` (pendiente también desde U3).
- En kind, el bucket vive en MinIO con object lock.

### INF-U4-03 — Rol `gov_archiver`
Permisos en `governance-db`: `SELECT` sobre `model_versions` y `transitions` (tabla única de transiciones, precisada el 2026-10-06), y
`UPDATE (archived_uri, archived_at)` sobre `model_versions` (permiso por columna). Sin
permiso sobre `state`. Los triggers de P-U4-06 siguen aplicando.

## 3. Red

### INF-U4-04 — Flujos nuevos (agregados a `component-dependency.md`)

| ID | Origen | Destino | Puerto | Tipo | Propósito |
|---|---|---|---|---|---|
| F101 | `model-archive` | MinIO, bucket `model-store` (`vectra-data`) | 9000 | R | Leer artefactos y explicadores |
| F102 | `model-archive` | `governance-db` | 5432 | W | Registrar `archived_uri`/`archived_at` (rol `gov_archiver`) |

Egress:

| ID | Origen | Destino | Puerto | Contenido |
|---|---|---|---|---|
| F100 | `model-archive` | S3 del banco fuera del sitio, bucket `vectra-model-archive` (WORM `COMPLIANCE`, 10 años) | 443 | Artefactos de modelo y explicadores; **sin datos de solicitantes** |

Los demás flujos del servicio ya existían (F11, F18, F24, F25, F27, F30–F32, F41, F47, K01).

**F27 (`freeze`)** (precisado el 2026-10-10 por U9 Infrastructure Design Q4): la `AuthorizationPolicy` de Linkerd de la ruta `POST /v1/models/{id}/freeze` admite **solo** la identidad `bias-monitoring-job` (ServiceAccount del CronJob de U9); la `NetworkPolicy` admite solo los pods del CronJob. El servicio HTTP de bias queda bloqueado en L7 aunque tuviera un token válido.

### INF-U4-05 — Versión activa en KServe de staging para `source_comparison` (segunda revisión del FD de U9, 2026-10-08)
- X08 impide que el `model-validation-job` llame a `vectra-serving`. Para comparar una fuente, el ingeniero abre un PR en el repositorio GitOps que agrega a los values de staging de U6 un `InferenceService` **solo predictor** (sin explicador) con el artefacto de la versión `activo`, tomado del model-store; se aplica con sync manual (AUTONOMIA-01), igual que el de la candidata. Al terminar la comparación, otro PR lo retira.
- Recursos: los de un predictor de staging de U6 (250m / 256 MiB; 1 CPU / 512 MiB; 1 réplica; `vectra-low`). El aporte a la cuota de `vectra-staging` es **un predictor más** durante la comparación; U1 lo suma (NFR-U1-13, Paso 6 de su plan).
- `start_source_comparison` comprueba que existan los dos `InferenceService` (BR-U4-13); si no, 409.
- **Verificación**: `conftest` sobre los values de staging (el `InferenceService` de la versión activa es solo predictor, 1 réplica, `vectra-low`); en kind (operador), una comparación completa con el modelo de referencia y su variante dentro de NFR-U4-12.

## 4. Cambios aplicados a otros artefactos

Registrados en `audit.md` (desde el 2026-10-03; filas posteriores con su fecha):

| Artefacto | Cambio |
|---|---|
| `component-dependency.md` §2.4 | F101, F102 |
| `component-dependency.md` §5 | F100 |
| `component-dependency.md` §4 (roles de base) | `gov_archiver` |
| `component-dependency.md` §7 y §9; `unit-of-work.md` U4; `application-design.md` | Rangos F01–F102; egress F70–F79, F99, F100 (registro histórico del 2026-10-03; el rango vigente es F01–F108) |
| U4 FD `domain-entities.md` §1.1 | Campos `archived_uri` y `archived_at` en `ModelVersion` |
| U4 NFR Design P-U4-08 | Alerta `ModelArchivePending` |
| INF-U4-05; values de staging de U6; U1 cuota de `vectra-staging` | Predictor de la versión activa en KServe de staging para `source_comparison` (segunda revisión del FD de U9, 2026-10-08) |
| INF-U4-04 (F27); `AuthorizationPolicy` de la ruta `freeze`; plan de U4 (Paso 16) | `POST /v1/models/{id}/freeze` solo para la identidad `bias-monitoring-job` (U9 Infrastructure Design Q4, 2026-10-10) |
| Plan de U4 (Paso 14, `branch-protection-check`) | Verifica la protección de `main` en los dos repositorios, con la aprobación de los *code owners* (revisión del FD de U10, 2026-10-10, A5) |

## 5. Cumplimiento de extensiones (Infrastructure Design U4)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-08 / 09 | Cumple | INF-U4-01 (HPA, spread, PDB) |
| RESILIENCY-11 / 12 | Cumple | INF-U4-02 (copia fuera del sitio que sobrevive a la pérdida del sitio) |
| RESILIENCY-05 / 07 | Cumple | INF-U4-02 (`ModelArchivePending`) |
| SECURITY-01 | Cumple | INF-U4-02: `vectra-model-archive` con cifrado del lado del servidor y acceso solo por TLS |
| SECURITY-06 | Cumple | INF-U4-03 (rol por columna, sin permiso sobre `state`) |
| SECURITY-07 | Cumple | INF-U4-04 (flujos y egress inventariados) |
| SECURITY-13 | Cumple | INF-U4-02 (WORM `COMPLIANCE`, verificación del SHA-256 tras subir) |
| AUTONOMIA-04 | Cumple | INF-U4-03 (el archivador no puede cambiar `state`; triggers de P-U4-06) |
| AUTONOMIA-05 | Cumple | INF-U4-02, 04 (F100 sin datos de solicitantes; la API sin egress) |
