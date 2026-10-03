# Plan de Infrastructure Design — U3 `decision-registry`

**Alcance:** asignar los componentes de `nfr-design/logical-components.md` a la
infraestructura de U1 y cerrar sus pendientes:
- dónde viven los buckets WORM;
- el backend de firma en producción;
- los flujos hacia la bóveda, hacia `-ro` y hacia los buckets;
- los recursos.

Además, corregir una inconsistencia de P-U3-04 que encontré al preparar este plan (Q5).

**Heredado de U1** (no se pregunta): entornos; pool `general` para el servicio y los
CronJobs; `registry-db` en el pool `data` (100 Gi + 20 Gi de WAL, expansible); ESO;
Linkerd con sidecar nativo para Jobs; Kyverno; observabilidad; MinIO in-cluster; S3 del
banco fuera del sitio para backups (F70).

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Heredado de U1 | — |
| Compute Infrastructure | Sí | Q4 |
| Storage Infrastructure | Sí | Q1, Q2 |
| Messaging Infrastructure | **N/A**: el registro es síncrono; no usa colas | — |
| Networking Infrastructure | Sí | Q1, Q3 (flujos y egress) |
| Monitoring Infrastructure | Heredado de U1; alertas en P-U3-09 | — |
| Shared Infrastructure | Sí | Q3, Q5 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Dónde viven los buckets WORM (Storage / Networking)
Si `registry-checkpoints` viviera en MinIO dentro del clúster, se perdería junto con el
sitio. Tras un restore, la verificación ya no podría comparar la cadena con los checkpoints
externos, que son justamente la defensa contra la reescritura.

A) **Los dos buckets (`registry-checkpoints` y `registry-archive`) en el S3 del banco fuera del sitio**, el mismo destino que F70 pero en buckets separados, con credenciales distintas por identidad, cifrado y object lock. Sobreviven a la pérdida del sitio y siguen el precedente de F70 para datos seudonimizados (destino dentro de la infraestructura del banco, cifrado). Agrega flujos de egress desde los CronJobs de checkpoint, verificación y archivo (recomendado)

B) `registry-checkpoints` en MinIO in-cluster y `registry-archive` fuera del sitio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Modo del object lock (Storage / Compliance)

A) **Modo `COMPLIANCE`** en los dos buckets: nadie, ni el administrador del almacenamiento, puede borrar ni acortar la retención antes de que venza (10 años para el archivo y para los checkpoints). Es irreversible: el banco paga el almacenamiento por 10 años. **[VERIFICAR con el área de almacenamiento del banco que su S3 soporta COMPLIANCE]** (recomendado: es lo que hace creíble la evidencia frente al supervisor)

B) Modo `GOVERNANCE`: un rol privilegiado del banco puede saltarse el lock

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Backend de firma en producción (Shared / Security)

A) **API compatible con Vault Transit** (HashiCorp Vault u OpenBao) en la bóveda del banco, con la llave Ed25519 marcada como no exportable. Si la bóveda del banco usa un HSM, la llave vive en él detrás de la API de Transit. Es la misma interfaz que en kind (Vault dev), así que el código no cambia entre entornos. Flujo de egress de los CronJobs de checkpoint y archivo hacia la bóveda **[VERIFICAR que la bóveda del banco expone Transit o un equivalente compatible]** (recomendado)

B) Llamada directa al HSM del banco por PKCS#11 desde los CronJobs (librerías cliente del HSM en la imagen)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Recursos, HPA y límites de tiempo de los Jobs (Compute)

A)

| Componente | Requests | Limits | Escalado / límite |
|---|---|---|---|
| `decision-registry-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 % |
| `registry-checkpoint` | 100m / 128 MiB | 500m / 256 MiB | `activeDeadlineSeconds: 300` |
| `registry-verify-incremental` | 250m / 256 MiB | 1 CPU / 512 MiB | 600 s |
| `registry-verify-nightly` | 500m / 512 MiB | 2 CPU / 1 GiB | 2 700 s (45 min; el objetivo es ≤ 30 min) |
| `registry-verify-full` | 500m / 512 MiB | 2 CPU / 1 GiB | 21 600 s (6 h) |
| `registry-archive` | 250m / 512 MiB | 1 CPU / 1 GiB | 7 200 s |

Si un Job vence su límite de tiempo, alerta (`RegistryVerificationFailed` o `ArchiveExportFailed`). `max_connections` de `registry-db`: 6 réplicas × 5 + 4 Jobs + operador y backups ≈ 45, dentro de los 100 iniciales (recomendado)

B) Sin límites de tiempo en los Jobs

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Corrección de P-U3-04: conexiones por réplica (Shared / Performance)
**Inconsistencia en un artefacto aprobado.** P-U3-04 define un pool `read` de 2 conexiones
«a la primaria (expediente) y a la réplica (proyecciones)», pero un pool apunta a un solo
servidor, así que en realidad son dos pools. Sumando la readiness de P-U3-01 (rol
`registry_health`, otra conexión), quedan **6** conexiones por réplica, y P-U1-08 fija un
máximo de **5**.

A) **Reajustar a 5 sin excepción**:

   | Pool | Conexiones | Servidor | Rol |
   |---|---|---|---|
   | `append` | **2** | Primaria | `registry_app` |
   | `dossier` | 1 | Primaria | `registry_app` (solo `SELECT`) |
   | `projections` | 1 | Réplica `-ro` | `registry_verifier` |
   | `health` | 1 | Primaria | `registry_health` |

   Dos conexiones de append alcanzan, porque los appends se **serializan** en el advisory lock (BR-U3-04): más conexiones solo harían cola en el lock. El aislamiento entre escrituras y lecturas se mantiene. Se corrige P-U3-04 y se registra (recomendado)

B) Mantener P-U3-04 y aceptar 6 conexiones por réplica como excepción a P-U1-08, recalculando `max_connections`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar NFR Design de U3 y la infraestructura compartida de U1
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/decision-registry/infrastructure-design/infrastructure-design.md`
- [x] 4. Generar `construction/decision-registry/infrastructure-design/deployment-architecture.md` (diagrama validado)
- [x] 5. Actualizar `component-dependency.md` (flujos y egress nuevos), `shared-infrastructure.md` si aplica, y P-U3-04 según la Q5; registrar en `audit.md`
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
