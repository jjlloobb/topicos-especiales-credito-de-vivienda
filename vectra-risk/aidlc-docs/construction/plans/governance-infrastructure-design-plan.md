# Plan de Infrastructure Design — U4 `governance`

**Alcance:** asignar los componentes de `nfr-design/logical-components.md` a la
infraestructura de U1 y cerrar sus pendientes: recursos y escalado del servicio, y la
retención de 10 años de los artefactos de modelo (NFR-U4-31).

**Heredado** (no se pregunta):
- entornos y pool `general` (U1);
- `governance-db` (10 Gi + 5 Gi, `max_connections` 50; INF-U1-02): con 6 réplicas × 5 conexiones (P-U4-04) + Job de migración + operador ≈ 35, cabe;
- model-store en MinIO in-cluster, buckets `model-store` y `validation-datasets` (INF-U1-03);
- recursos y aislamiento del `model-validation-job` (NFR-U4-23);
- flujos F11, F18, F24, F25, F27, F30–F32, F41, F47 y K01, que cubren el servicio sin cambios (`LISTEN/NOTIFY` va por F41).

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Heredado de U1 | — |
| Compute Infrastructure | Sí | Q1 |
| Storage Infrastructure | Sí | Q2 |
| Messaging Infrastructure | **N/A**: `LISTEN/NOTIFY` de PostgreSQL para la convergencia (P-U4-01); sin broker | — |
| Networking Infrastructure | Solo si la Q2 agrega un flujo | Q2 |
| Monitoring Infrastructure | Heredado de U1; alertas en P-U4-08 | — |
| Shared Infrastructure | Heredado (U1, U2, U3) | — |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Recursos y escalado del servicio (Compute)

A)

| Componente | Requests | Limits | Escalado |
|---|---|---|---|
| `governance-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA de 2 a 6 por CPU al 70 %; spread por zona; PDB `minAvailable: 1`; prioridad `vectra-high` |
| Job de migración | 100m / 128 MiB | 500m / 256 MiB | `activeDeadlineSeconds: 600` |

Imagen con `tzdata` para `America/Bogota` (P-U4-05) (recomendado)

B) Réplicas fijas (3), sin HPA

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Retención de 10 años de los artefactos de modelo (Storage, NFR-U4-31)
El bucket `model-store` vive en MinIO **dentro** del clúster (INF-U1-03), que se pierde con
el sitio. Para defender una decisión de hace años hace falta poder recuperar el artefacto
exacto que la produjo; el registro solo guarda su checksum.

A) **Copia WORM fuera del sitio al activar**: un CronJob diario `model-archive` copia el artefacto y el explicador de toda versión que llegó a `activo` y todavía no está archivada a un bucket `vectra-model-archive` del S3 del banco fuera del sitio. Usa object lock `COMPLIANCE` de 10 años (mismo destino y modo que los buckets de U3), verifica el SHA-256 tras subir y registra el URI archivado en la versión.
   - Agrega un egress (F7x): no lleva datos de solicitantes, solo artefactos de modelo.
   - El servicio de la API no hace este egress.

   (Recomendado)

B) No archivar: el banco conserva los artefactos en su propio pipeline de entrenamiento; Vectra solo guarda el checksum **[VERIFICAR con el banco]**

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar NFR Design de U4 y la infraestructura compartida
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/governance/infrastructure-design/infrastructure-design.md`
- [x] 4. Generar `construction/governance/infrastructure-design/deployment-architecture.md` (diagrama validado)
- [x] 5. Actualizar `component-dependency.md` si la Q2 agrega un flujo; registrar en `audit.md`
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
