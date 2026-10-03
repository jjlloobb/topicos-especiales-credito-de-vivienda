# Plan de NFR Design — U3 `decision-registry`

**Alcance:** convertir NFR-U3-01..52 en patrones y componentes lógicos: readiness y
tiempos límite del commit síncrono, emisión de checkpoints con varias réplicas, dónde corre
la verificación, formato del archivo de 10 años, creación de particiones y aislamiento entre
escrituras y lecturas pesadas.

**Ya decidido** (no se pregunta): el Functional Design (BR-U3-01..16, con los modos de
verificación precisados), el stack de `tech-stack-decisions.md`, la plataforma de U1
(P-U1-04 para readiness, P-U1-08 para conexiones) y RESILIENCY-14 = C.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q2, Q3, Q7 |
| Scalability Patterns | Q4, Q6 |
| Performance Patterns | Q2, Q4, Q7 |
| Security Patterns | Q3, Q5 |
| Logical Components | Q3, Q5, Q6 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Readiness: qué es «escritura posible» (Resilience, NFR-U3-11)
NFR-U3-11 dice que la readiness exige escritura posible, con la réplica síncrona
disponible. `registry_app` no puede leer `pg_stat_replication`, y sin réplica síncrona un
commit de PostgreSQL espera indefinidamente.

A) **Readiness con un rol de monitoreo aparte**:
   - un rol `registry_health` con `pg_monitor` (solo lectura de estadísticas) comprueba la conexión y que `pg_stat_replication` tenga al menos un standby en estado `sync`;
   - el resultado se cachea 5 s (P-U1-04);
   - sin standby síncrono, el pod sale del balanceo y los llamadores ven `registry_unavailable` (fail-closed) de inmediato, sin esperar un timeout.

   (Recomendado)

B) Readiness = `SELECT 1`; la falta de réplica se detecta solo por el timeout del commit (Q2)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Tiempos límite del append (Resilience / Performance)

A) Por transacción:
   - `lock_timeout = 1 s` (espera del advisory lock);
   - `statement_timeout = 2 s`;
   - un timeout total de 2,5 s en el handler.

   Si se vencen, responde `503 dependency_unavailable` y el llamador lo trata como `registry_unavailable`. El servicio **no** reintenta por su cuenta: el reintento es del llamador, con la misma `idempotency_key` (BR-U3-06), así que nunca se duplica. Un commit que no se confirmó a tiempo y sí quedó escrito se resuelve en el reintento por idempotencia (recomendado)

B) Sin tiempos límite propios; se usan los del llamador

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Quién emite el checkpoint cada hora con varias réplicas (Logical Components / Resilience)

A) **CronJob** `registry-checkpoint` (cada hora, `concurrencyPolicy: Forbid`) que ejecuta `vectra-registry checkpoint`:
   - usa el mismo camino de append (rol `registry_app`, lock, hash) y la firma de la bóveda (Vault Transit), y luego exporta al bucket WORM;
   - la `idempotency_key` del checkpoint se deriva de la hora (`checkpoint:2026-10-03T12`), así que una segunda ejecución no crea un segundo checkpoint;
   - su ServiceAccount es la **única** con permiso de firma en la bóveda.

   (Recomendado: sin elección de líder dentro del servicio, y la identidad que firma queda separada de la que atiende la API)

B) Elección de líder entre las réplicas del servicio, que emite el checkpoint desde un hilo interno

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Dónde corre la verificación (Scalability / Performance)

A) **En una réplica de solo lectura** (servicio `-ro` de CloudNativePG) con el rol `registry_verifier`, para no cargar la primaria. Por el retraso de replicación, cada corrida verifica hasta la cabeza **que ve la réplica** y lo informa (`to_seq`). Hay una excepción: el expediente usa la primaria, porque necesita incluir las entradas recién escritas (recomendado)

B) Todo contra la primaria

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Formato del archivo de 10 años (Logical Components / Security, NFR-U3-04)

A) **NDJSON comprimido con zstd por mes**: una línea por entrada con `seq`, `prev_hash`, `hash` y `canonical` en base64, más un **manifiesto** firmado por la bóveda con `{from_seq, to_seq, head_hash, checkpoints, sha256 del archivo, contract_versions}`.
   - El formato no depende de la versión de PostgreSQL y lo verifica la misma CLI (`verify --source archive`) sin una base.
   - El Job lee de la réplica, sube el archivo, lo vuelve a descargar y lo verifica antes de dar el mes por cerrado.

   (Recomendado)

B) `pg_dump` de la partición del mes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Creación de particiones (Scalability, NFR-U3-31)
Una extensión como `pg_partman` crea particiones sola, en tiempo de ejecución. Pero en este
proyecto el DDL solo entra por migraciones en un sync aprobado (F44, AUTONOMIA-01).

A) **Particiones creadas por migraciones**: la migración inicial crea las particiones del año en curso y de los **dos siguientes**; cada año, un PR de migración agrega una partición más. La alerta `RegistryPartitionMissing` avisa si faltan menos de 30 días para necesitar una partición que no existe. Hay una partición `DEFAULT` como red de seguridad, con una alerta SEV1 si recibe filas (recomendado)

B) `pg_partman` con creación automática

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Aislamiento entre escrituras y lecturas (Resilience / Performance, bulkhead)

A) **Dos pools separados en el servicio**:
   - pool de **append** con 3 conexiones a la primaria;
   - pool de **lectura** con 2 conexiones: el expediente va a la primaria, las proyecciones a la réplica.

   Un expediente lento o una ráfaga de consultas no puede quitarle conexiones a los appends. Cada pool tiene su timeout y su métrica de saturación (`vectra_registry_pool_wait_seconds{pool}`). El total por réplica sigue en ≤ 5 conexiones (P-U1-08) (recomendado)

B) Un solo pool para todo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/decision-registry/nfr-requirements/` (NFR-U3-01..52, stack)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/decision-registry/nfr-design/nfr-design-patterns.md`
- [x] 4. Generar `construction/decision-registry/nfr-design/logical-components.md` (diagrama validado)
- [x] 5. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
