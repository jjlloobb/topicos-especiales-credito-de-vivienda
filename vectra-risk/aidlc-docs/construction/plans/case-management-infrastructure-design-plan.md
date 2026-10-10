# Plan de Infrastructure Design — U8 `case-management`

**Alcance:** asignar los componentes de `nfr-design/logical-components.md` a la
infraestructura de U1:
- la identidad de `case-worker` (pendiente del NFR Design, hallazgo 7);
- recursos, cuota y apagado ordenado;
- la configuración;
- el tamaño de `case-db`;
- el despliegue de `core-banking-mock`.

Al cruzar los flujos con P-U8-06 aparecieron **dos inconsistencias** del mock (Q2 y Q3).

**Heredado** (no se pregunta):
- entornos, pool `general` y namespaces `vectra-app` y `vectra-mock` (U1);
- `vectra-high` para `case-service` y `case-worker`, `vectra-low` para el mock (P-U1-09);
- réplicas, HPA y PDB de P-U8-10;
- `case-db` en CloudNativePG con `max_connections = 100`, que cubre las 60 conexiones de NFR-U8-14 con su margen (U1 Infrastructure Design);
- la cola en la tabla `evaluation_jobs`: **sin broker de mensajes**;
- observabilidad: K02, K03, K13 y reglas en una `PrometheusRule` del chart, con `runbook_url` (P-U1-10), como en U7;
- imágenes firmadas y políticas de Kyverno (U1);
- sidecar nativo de Linkerd, también en el CronJob `case-retention`, para que el Job termine (como `restore-drill`, P-U1-05).

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Sí: en qué entornos existe el mock | Q2 |
| Compute Infrastructure | Sí | Q4, Q5 |
| Storage Infrastructure | Sí: tamaño de `case-db` | Q7 |
| Messaging Infrastructure | **N/A**: la cola es la tabla `evaluation_jobs` (P-U8-01); no hay broker | — |
| Networking Infrastructure | Sí: identidad de `case-worker`, JWKS del mock y X01 | Q1, Q2, Q3 |
| Monitoring Infrastructure | Sí: fuente de `CoreWriteAttempt` | Q3 |
| Shared Infrastructure | Sí: aporte de U8 a las cuotas de `vectra-app` y `vectra-mock` (NFR-U1-13) | Q4 |
| Configuración | Sí: qué va en values y qué en el código | Q6 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Identidad de `case-worker` (Networking / Security; hallazgo 7 del NFR Design)
F15, F104 y F40 nombran a `case-service` como origen, y U2 define un solo cliente de
Keycloak `case-service`. Pero desde NFR-U8-10 la evaluación corre en otro Deployment.

A) **Identidad propia en las tres capas** (mínimo privilegio):
   - **ServiceAccount** `case-worker`, que también es su identidad en Linkerd;
   - **cliente de Keycloak** `case-worker`, con solo `case:recommend`, `governance:read-serving` y `governance:read-feature-spec`. El cliente `case-service` pierde `case:recommend`, porque la API ya no llama a scoring;
   - **rol de base** `case_worker`, con:
     - `SELECT` sobre `cases` y `case_identifiers` (para `derive`);
     - `UPDATE` de las columnas de evaluación de `cases`;
     - `SELECT`, `UPDATE` y `DELETE` sobre `evaluation_jobs`;
     - `INSERT` en `evidence_outbox` (la entrada `fail_closed` al escalar, BR-U8-09).
   - `case_app` pierde lo que solo usaba el worker;
   - en el inventario, F15 pasa a tener origen `case-worker`, F104 y F40 lo suman como origen, y se ajustan la `NetworkPolicy`, la `AuthorizationPolicy` y el realm de U2.

   (Recomendado: si un pod de la API queda comprometido, no puede llamar a scoring; si el comprometido es un worker, no puede leer decisiones ni escribir evidencia de decisión)

B) ServiceAccount y cliente de Keycloak propios, pero el mismo rol de base `case_app`

C) Compartir ServiceAccount, cliente y rol con `case-service`, y aclarar en el inventario que `case-service` designa a los dos Deployments

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — El mock no puede validar tokens (Networking / Deployment Environment)
**Inconsistencia.** El mock exige el scope `core:read-credit` y responde 403 sin
`core:write-credit` (BR-U8-22). Para eso tiene que validar el JWT con el JWKS de Keycloak.
Pero `core-banking-mock` **no figura** en F50, el flujo hacia el JWKS de Keycloak, y su
`NetworkPolicy` lo bloquearía.

A) **Agregar el mock a F50, solo para el JWKS** (sin client credentials: el mock no llama a nadie):
   - el mock valida firma, `aud = core-banking-mock` y scope con `vectra_common` (U0), como cualquier servicio;
   - el mock se despliega **solo fuera de producción** (kind y staging); un value del chart lo impide en producción y una política lo verifica;
   - los fixtures van **dentro de la imagen** (versionados y firmados con ella), no en un ConfigMap.

   (Recomendado)

B) El mock confía en la identidad de Linkerd y no valida el JWT. El scope `core:write-credit` deja de ser una barrera.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — `CoreWriteAttempt` no se dispararía (Monitoring / Networking; P-U8-06, X01)
> **Superado en parte** (anotado el 2026-10-08): la expresión con `increase()` sobre la serie de Linkerd la reemplaza INF-U8-03 (resta contra `offset 5m` y filtro por `route_name`), y la alerta solo existe en kind y staging (aclaración Q1 = A, INF-U8-02).

**Inconsistencia.** X01 bloquea en dos capas:
- la `NetworkPolicy` descarta cualquier origen distinto de case-service;
- Linkerd **rechaza en el proxy** cualquier método distinto de `GET` desde case-service.

Por eso un `POST /v1/credits/{id}/status` **nunca llega al mock**: no se crea el
`WriteAttempt` y `vectra_core_write_attempts_total` queda en 0. La alerta y la evidencia de
RT-5 de P-U8-06 dependen de un evento que la propia defensa impide.

A) **La evidencia es la denegación en la primera capa que la ve**:
   - `CoreWriteAttempt` se dispara con `increase(vectra_core_write_attempts_total[5m]) > 0` **o** con `increase(inbound_http_authz_deny_total{namespace="vectra-mock"}[5m]) > 0`, la métrica de denegación del proxy de Linkerd del mock;
   - el `WriteAttempt` del mock queda como **tercera capa**: solo aparece si Linkerd estuviera mal configurado, y en ese caso la alerta lo dice en su descripción;
   - la demostración de RT-5 envía el `POST` desde un pod con la identidad de case-service (un Job de U12), y la evidencia esperada es el 403 del proxy más la alerta;
   - un origen distinto de case-service lo descarta la `NetworkPolicy` sin métrica. Eso ya lo cubre la suite de conectividad de U1.

   (Recomendado)

B) Permitir en Linkerd el `POST` a `/status` desde case-service, para que el mock registre el intento y responda 403 por scope

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Recursos y cuota (Compute / Shared)

A)

| Componente | Requests | Limits | Réplicas |
|---|---|---|---|
| `case-service` | 250m / 256 MiB | 1 CPU / 512 MiB | HPA 2–6 |
| `case-worker` | 200m / 256 MiB | 1 CPU / 512 MiB | HPA 2–6 (espera E/S; la cola atrasada la cubre `CaseJobsOverdue`) |
| `case-retention` (CronJob) | 100m / 128 MiB | 500m / 256 MiB | 1 pod por corrida |
| Job de migración | 100m / 128 MiB | 500m / 256 MiB | 1 pod |
| `core-banking-mock` (`vectra-mock`) | 50m / 64 MiB | 250m / 128 MiB | 2 |

- **Aporte de U8 a la cuota de `vectra-app`**: el máximo del HPA + 30 % (NFR-U1-13), más el CronJob y la migración.
  - Requests: (6 × 250m + 6 × 200m + 100m + 100m) × 1,3 = **3,77 CPU**, y (12 × 256 MiB + 2 × 128 MiB) × 1,3 ≈ **4,2 GiB**.
  - Limits: (12 × 1 CPU + 2 × 500m) × 1,3 = **16,9 CPU**, y (12 × 512 MiB + 2 × 256 MiB) × 1,3 ≈ **8,45 GiB**.
- **Aporte a `vectra-mock`**: requests de 0,13 CPU / 166 MiB y limits de 0,65 CPU / 333 MiB.
- **Probes**: readiness y liveness como en U7 (P-U1-04). La readiness de `case-service` y de `case-worker` comprueba la conexión a `case-db` (NFR-U8-21).

(Recomendado: valores iniciales, ajustables con la prueba de carga de U12)

B) Los mismos recursos para `case-worker` que para `case-service` (250m / 256 MiB)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Apagado ordenado (Compute / Resilience; como INF-U7-03)
En U8 importan dos cosas:
- `case-service` hace el append de la decisión de forma síncrona (hasta 2,5 s);
- `case-worker` puede tener 16 llamadas en vuelo de hasta 15,5 s cada una (P-U8-01). Si se cortan, el trabajo se retoma a los 30 s, pero una `Recommendation` ya escrita queda **no entregada** (P-U7-03).

A) **Drenaje en los dos**:
   - `case-service`: igual que INF-U7-03 (`preStop.sleep 5`, `timeout_graceful_shutdown = 10`, `terminationGracePeriodSeconds: 20`). Además, los barridos y el reconciliador dejan de tomar trabajo al recibir `SIGTERM`;
   - `case-worker`: al recibir `SIGTERM` deja de sondear y espera las llamadas en vuelo hasta 20 s, con `terminationGracePeriodSeconds: 30`, por encima del peor caso de 15,5 s. Lo que no termine se retoma al vencer el arrendamiento (P-U8-01).

   (Recomendado: un despliegue no produce recomendaciones no entregadas)

B) Solo el drenaje de `case-service`, y el worker confía en el arrendamiento

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Configuración: values contra código (Configuración; como INF-U7-04)

A) **Constantes en el código**, salvo lo que depende del entorno o de cumplimiento:
   - **En el código** (`vectra_case/config.py`): timeouts, tamaños de pool, umbrales del circuit breaker, backoff, arrendamiento, sondeo, lotes, límite del reconciliador y plazos del abandono a 24 h. Cambiarlos exige un PR con sus pruebas. Una prueba falla si el peor caso del worker (15,5 s) no cabe en el arrendamiento (30 s) o en el apagado (30 s).
   - **En los values**: URLs, audiencias, el nivel de log, `allow_test_scenarios` (`false` en producción, con política), `retention.*` (P-U8-05) y el horario del CronJob.

   (Recomendado)

B) Todo en los values de Helm, validado al arrancar con Pydantic Settings y con límites

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Tamaño de `case-db` (Storage)
> **Superado en parte** (anotado el 2026-10-08): `CaseDbVolumeFilling` se retiró; el volumen de `case-db` lo vigila `PostgresVolumeUsageHigh` de U1 (INF-U1-02, INF-U8-08).

U1 asignó 50 Gi a `case-db`. Las filas de `cases` no se borran: se anonimizan y se conservan
con la recomendación (BR-U8-20). El PRD no da el volumen de solicitudes (**[VERIFICAR]**).
Estimado por caso:
- `application`: 3 KB;
- `recommendation` con la `Explanation`: 12 KB;
- outbox, decisión e índices: 10 KB.

En total, **~25 KB por caso**: 50 Gi alcanzan para unos 2 millones de casos.

A) **Mantener 50 Gi y vigilar el crecimiento**:
   - documentar el estimado y la fórmula;
   - alerta `CaseDbVolumeFilling` (SEV2) con el volumen al 75 %, si U1 no la tiene ya para todos los `Cluster` (se verifica y, si existe, se reutiliza);
   - la ampliación es un cambio de values del `Cluster` (expansión de volumen de la StorageClass de U1);
   - la prueba de carga de U12 mide el tamaño real por caso.

   (Recomendado)

B) Subir a 100 Gi desde el inicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el FD y el NFR Design de U8 y la infraestructura compartida de U1 y U2
- [x] 2. Recoger y validar las respuestas (Q1–Q7 = A)
- [x] 3. Generar `construction/case-management/infrastructure-design/infrastructure-design.md`
- [x] 4. Generar `construction/case-management/infrastructure-design/deployment-architecture.md` (diagrama validado)
- [x] 5. Aplicar y registrar los cambios a otros artefactos según las respuestas (inventario de flujos y roles, realm de U2, P-U8-06, cuotas de U1)
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
