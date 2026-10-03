# Infrastructure Design — U3 `decision-registry`

Decisiones del plan (`decision-registry-infrastructure-design-plan.md`, Q1–Q5 = A). Se apoya
en la infraestructura compartida de U1. Los IDs `INF-U3-xx` se referencian en el plan de tareas.

---

## 1. Almacenamiento de evidencia externa (Q1, Q2)

### INF-U3-01 — Buckets WORM en el S3 del banco fuera del sitio

| Bucket | Contenido | Object lock | Retención | Escribe | Lee |
|---|---|---|---|---|---|
| `vectra-registry-checkpoints` | Un objeto por checkpoint (`checkpoints/{seq}.json`) | **COMPLIANCE** | 10 años | `registry-checkpoint` (F77) | `registry-verify-*` (F79), `restore-drill` (F75) |
| `vectra-registry-archive` | NDJSON + zstd mensual y su manifiesto firmado | **COMPLIANCE** | 10 años | `registry-archive` (F78) | `registry-archive` (verificación tras subirlo, F78) |

- Mismo destino que F70 (S3 del banco fuera del sitio) y **buckets separados**, con credenciales distintas por identidad, todas desde ESO.
- Cifrado del lado del servidor y TLS.
- Sobreviven a la pérdida del sitio: después de un restore, la verificación vuelve a comparar la cadena con los checkpoints externos.
- El archivo contiene **datos seudonimizados**. Sigue el precedente de F70: destino dentro de la infraestructura del banco y cifrado (AUTONOMIA-05).
- **[VERIFICAR]** con el área de almacenamiento del banco que su S3 soporta object lock en modo `COMPLIANCE`. Es irreversible: el banco paga 10 años de almacenamiento.
- En kind, los dos buckets viven en MinIO (U1) con object lock, porque no hay un sitio externo que simular.

## 2. Firma (Q3)

### INF-U3-02 — Backend de firma
- **API compatible con Vault Transit** en todos los entornos: Vault dev en kind (F98) y la bóveda del banco en staging y prod (egress F99).
- La llave `vectra-registry-checkpoint` es Ed25519, **no exportable**. Si la bóveda del banco usa un HSM, la llave vive en él detrás de la API de Transit.
- Política de la bóveda: `transit/sign/vectra-registry-checkpoint` solo para las identidades de `registry-checkpoint` y `registry-archive`; `transit/keys/...` (llave pública) en lectura para `registry-verify-*`. La identidad del servicio de la API no tiene ninguna política.
- **[VERIFICAR]** que la bóveda del banco expone Transit o un equivalente compatible.

## 3. Cómputo (Q4)

### INF-U3-03 — Recursos y límites

| Componente | Requests | Limits | Escalado / límite de tiempo | PriorityClass |
|---|---|---|---|---|
| `decision-registry-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 %; spread por zona; PDB | `vectra-critical` |
| `registry-checkpoint` | 100m / 128 MiB | 500m / 256 MiB | `activeDeadlineSeconds: 300` | `vectra-high` |
| `registry-verify-incremental` | 250m / 256 MiB | 1 CPU / 512 MiB | 600 s | `vectra-normal` |
| `registry-verify-nightly` | 500m / 512 MiB | 2 CPU / 1 GiB | 2 700 s | `vectra-normal` |
| `registry-verify-full` | 500m / 512 MiB | 2 CPU / 1 GiB | 21 600 s | `vectra-low` |
| `registry-archive` | 250m / 512 MiB | 1 CPU / 1 GiB | 7 200 s | `vectra-low` |

- Todos los CronJobs: `concurrencyPolicy: Forbid`, sidecar nativo de Linkerd (P-U1-05), `restartPolicy: Never`, `backoffLimit: 1`.
- Un Job que vence su límite → `RegistryVerificationFailed` o `ArchiveExportFailed`.

### INF-U3-04 — Conexiones a `registry-db` (Q5)

| Origen | Conexiones | Servicio de `registry-db` |
|---|---|---|
| Servicio, por réplica: `append` 2 + `dossier` 1 + `health` 1 | 4 | `-rw` |
| Servicio, por réplica: `projections` 1 | 1 | `-ro` |
| `registry-checkpoint` | 1 | `-rw` |
| `registry-verify-*`, `registry-archive` | 1 cada uno | `-ro` |
| Job de migración | 1 | `-rw` |

- Máximo con 6 réplicas: 30 del servicio + 5 de Jobs + las del operador y los backups ≈ **45**, dentro de los 100 de `max_connections` (INF-U1-02).
- **Corrección registrada**: P-U3-04 decía `append` 3 + `read` 2 (un pool sobre dos servidores) y, con la readiness, sumaba 6 conexiones por réplica, por encima del máximo de 5 de P-U1-08. Ahora son 5 sin excepción.

## 4. `registry-db`

### INF-U3-05
- Cluster de CloudNativePG de U1 (INF-U1-02): 3 instancias, 100 Gi + 20 Gi de WAL, expansible; particiones por migración (P-U3-06).
- Servicios: `registry-db-rw` (primaria) y `registry-db-ro` (réplicas).
- Roles gestionados por la migración inicial: `registry_app`, `registry_verifier`, `registry_health` (con `pg_monitor`) y `registry_migrator`. Contraseñas desde ESO; TLS `verify-full`.

## 5. Red

### INF-U3-06 — Flujos nuevos (agregados a `component-dependency.md`)

| ID | Origen | Destino | Puerto | Tipo | Propósito |
|---|---|---|---|---|---|
| F96 | decision-registry-service | `registry-db-ro` | 5432 | R | Proyecciones (pool `projections`) |
| F97 | `registry-checkpoint` → `registry-db-rw`; `registry-verify-*` y `registry-archive` → `registry-db-ro` | `registry-db` | 5432 | A / R | Checkpoint; verificación y archivo |
| F98 | `registry-checkpoint`, `registry-archive` | Vault (`vault`, **solo kind**) | 8200 | S | Firma Transit |

Egress (§5 del inventario):

| ID | Origen | Destino | Puerto | Contenido |
|---|---|---|---|---|
| F77 | `registry-checkpoint` | S3 del banco fuera del sitio, bucket `vectra-registry-checkpoints` | 443 | Checkpoints firmados (`seq`, hash, firma); sin datos de solicitantes |
| F78 | `registry-archive` | S3 del banco fuera del sitio, bucket `vectra-registry-archive` | 443 | Segmentos mensuales de la cadena: **datos seudonimizados, cifrados**, en la infraestructura del banco (precedente de F70) |
| F79 | `registry-verify-*` | S3 del banco fuera del sitio, bucket `vectra-registry-checkpoints` | 443 | Solo lectura de checkpoints |
| F99 | `registry-checkpoint`, `registry-archive` (staging y prod) | Bóveda del banco (API Transit) | 443 | Solo el digest a firmar (NFR-U3-41) |

## 6. Cambios aplicados a otros artefactos

Registrados en `audit.md` (2026-10-03):

| Artefacto | Cambio |
|---|---|
| `component-dependency.md` §0 | Puerto `8200/TCP` (Vault Transit) |
| `component-dependency.md` §2.4 | F96, F97 |
| `component-dependency.md` §2.7 | F98 |
| `component-dependency.md` §5 | F77, F78, F79, F99 |
| `component-dependency.md` §7 y §9; `unit-of-work.md` U3; `application-design.md` | Rangos F01–F99; egress F70–F79 y F99 |
| `decision-registry/nfr-design/nfr-design-patterns.md` P-U3-04 y P-U3-08; `logical-components.md` | Pools corregidos (Q5) |

## 7. Cumplimiento de extensiones (Infrastructure Design U3)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-08 / 09 | Cumple | INF-U3-03 (HPA, spread, PDB) |
| RESILIENCY-10 | Cumple | INF-U3-03 (límites de tiempo de los Jobs), INF-U3-04 (bulkhead dentro del máximo de conexiones) |
| RESILIENCY-11 / 12 | Cumple | INF-U3-01 (evidencia externa que sobrevive a la pérdida del sitio) |
| SECURITY-01 | Cumple | INF-U3-01 (cifrado y TLS), INF-U3-05 (`verify-full`) |
| SECURITY-06 | Cumple | INF-U3-02 (políticas de la bóveda por identidad), INF-U3-05 (roles de base) |
| SECURITY-07 | Cumple | INF-U3-06 (flujos y egress inventariados) |
| SECURITY-12 | Cumple | INF-U3-02 (llave no exportable) |
| SECURITY-13 | Cumple | INF-U3-01 (WORM en `COMPLIANCE`), INF-U3-02 |
| AUTONOMIA-01 | Cumple | Infraestructura por PR + sync manual; particiones por migración |
| AUTONOMIA-05 | Cumple | F77, F79, F99 sin datos de solicitantes; F78 con datos seudonimizados y cifrados en la infraestructura del banco (precedente de F70) |
