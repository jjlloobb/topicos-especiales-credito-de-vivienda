# Plan de Functional Design — U3 `decision-registry`

**Alcance de la unidad** (`unit-of-work.md` §1): `decision-registry-service`, que incluye:
- append serializado con hash encadenado;
- confirmación tras la réplica síncrona;
- consultas filtradas por rol y scope;
- expediente de un caso;
- `verify_chain` como API, CLI y CronJob.

Además, el esquema y las migraciones de `registry-db` y los roles `registry_app` (solo
`INSERT`/`SELECT`) y `registry_migrator`. Es el **único componente Critical**.

**Historias (dueña):** US-401 (append-only encadenado), US-402 (verificador), US-403
(expediente), US-404 (eventos de gobierno).

**Ya decidido** (no se pregunta):
- tipos `RegistryEntryIn`, `RegistryEntry`, `RegistryAck` y los payloads por `entry_type` (U0 domain-entities §5, incluido `actor.acr`/`auth_time` para firmas);
- datos seudonimizados, sin identificadores directos ni `free_text` (BR-U0-95);
- entrada `recommendation` construida solo desde `Ready` (BR-U0-08);
- RPO 0 ante fallo de zona con réplica síncrona; si no hay réplica, las escrituras se bloquean (U1 NFR-U1-03);
- `restore-drill` usa la CLI `verify_chain` y espera «íntegra» (P-U1-05);
- la compatibilidad con la Ley 1581 (retención y supresión) se decide en el **NFR Requirements de U3**, no aquí.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Qué impide reescribir la cadena entera (Business Rules, US-401/402)
Una cadena de hashes simple detecta una edición aislada. Pero un superusuario de la base
puede editar un registro y **recalcular todos los hashes siguientes**, y la cadena volvería
a verificar.

A) **Hash SHA-256 encadenado + anclas firmadas fuera de la base**:
   - cada hora (y en cada `verify_chain` completo) se emite un *checkpoint* `{seq, hash, timestamp}` firmado con una llave Ed25519 que entrega ESO desde la bóveda, a la que la base no tiene acceso;
   - el checkpoint se guarda en el registro y se copia a un bucket con object lock (WORM) fuera del alcance del rol de la base;
   - el verificador compara la cadena contra los checkpoints: una reescritura posterior a un checkpoint queda en evidencia aunque los hashes cuadren.

   (Recomendado)

B) HMAC-SHA256 encadenado con una llave fuera de la base, sin checkpoints

C) Solo la cadena SHA-256, sin anclas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Qué bytes se hashean (Business Rules / Domain Model)
Los payloads se definen con el contrato de U0, que va a evolucionar (BR-U0-90..93). Si el
verificador volviera a serializar entradas antiguas con un contrato nuevo, los hashes
podrían dejar de coincidir sin que nadie haya manipulado nada.

A) **Se guardan los bytes canónicos exactos** (JSON canónico RFC 8785, JCS) de cada entrada en una columna `canonical`, junto con `contract_version`. El hash se calcula **sobre esos bytes** y el verificador **nunca** vuelve a serializar: recalcula el hash de los bytes guardados y comprueba que corresponden a las columnas consultables (recomendado)

B) Se guardan las columnas y el verificador serializa de nuevo con el contrato vigente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Contenido del hash y entrada génesis (Domain Model)

A) `hash = SHA-256(prev_hash ‖ canonical)`, donde `canonical` incluye `seq`, `entry_type`, `actor`, `occurred_at`, `recorded_at`, `correlation_id`, las referencias (`case_id`, `model_version_id`, `policy_version_id`) y el `payload`. La **entrada génesis** (`seq = 0`, `entry_type = genesis`) tiene `prev_hash` de 64 ceros y registra la versión del esquema, la versión del contrato y la huella de la llave pública de los checkpoints (recomendado)

B) Hash solo del `payload` más `prev_hash`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Serialización de las escrituras (Business Logic)

A) **Un escritor a la vez por transacción**: `pg_advisory_xact_lock` sobre una llave fija, lectura de la cabeza (`seq`, `hash`), cálculo del hash, `INSERT` y `COMMIT`, que espera la réplica síncrona (`synchronous_commit = remote_apply`). `seq` es contiguo y sin huecos (restricción `seq = cabeza + 1` verificada en la inserción). El ack solo se devuelve después del commit. Con el volumen de diseño (decenas de escrituras por segundo como máximo), el lock no es cuello de botella (recomendado)

B) Una secuencia de PostgreSQL y un encadenador asíncrono que calcula los hashes después

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Reintentos y duplicados (Business Rules)
scoring y case reintentan cuando el registro no responde a tiempo, y la escritura pudo haber
quedado hecha.

A) **`idempotency_key` obligatoria** en `RegistryEntryIn` (UUID que genera el cliente, el mismo en cada reintento):
   - si la llave ya existe con el **mismo** `canonical` (sin `recorded_at`), se devuelve el ack original;
   - si existe con contenido **distinto**, responde `409 conflict_state`.

   Restricción `UNIQUE` en la base (recomendado: un reintento nunca duplica una recomendación ni una decisión)

B) Sin idempotencia: los duplicados se filtran al consultar

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Qué ve cada consumidor (Business Rules, FR-REG-04)

A) **Proyecciones por scope o rol**, aplicadas en el servicio:

   | Consumidor | Qué puede leer |
   |---|---|
   | `cro`, `cumplimiento` (BFF) | Todo, incluido el expediente y la verificación |
   | `analista` (BFF) | **Nada directo** del registro; sus vistas vienen de case-service |
   | explainability (`registry:read:explanation`) | Solo la `explanation` de la entrada `recommendation` de un `case_id` dado |
   | bias (`registry:read:monitoring`) | `recommendation` (sin `explanation` ni `feature_vector`) y `human_decision` (sin `justification`), con `monitoring_labels` |
   | product-metrics (`registry:read:metrics`) | `recommendation`, `human_decision` y `explanation_view` **sin** `payload` sensible: solo tipo, outcome, decisión, `used_factors`, `explanation_viewed_before` y timestamps |

   (Recomendado)

B) Todos los consumidores autorizados leen las entradas completas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Expediente y su estado de integridad (Business Logic, US-403)

A) El expediente de un caso contiene:
   - todas sus entradas, en orden de `seq`, con los bytes canónicos tal como se guardaron (la narrativa se reproduce byte a byte);
   - los identificadores directos, que trae de case-service **solo** para `cro`/`cumplimiento` (F13);
   - un **estado de integridad**, que verifica el tramo de la cadena desde el checkpoint anterior a la primera entrada del caso hasta el checkpoint posterior a la última (o la cabeza), más el resultado y la fecha de la última verificación completa.

   Si el tramo no verifica, el expediente se entrega marcado «integridad NO verificada» y se emite `RegistryChainBroken` (recomendado: rápido aunque la cadena sea larga)

B) Verificación de la cadena completa en cada solicitud de expediente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Modos y frecuencia del verificador (Business Logic, US-402)

A) **Incremental cada 15 min** (desde el último checkpoint verificado) y **completo cada noche** (CronJob), más bajo demanda (API para `cro` con MFA, y CLI).
   - Códigos de salida de la CLI: `0` íntegra, `1` inconsistencia (informa el primer `seq` inconsistente y el motivo: hash, enlace, checkpoint o hueco de `seq`), `2` error de ejecución.
   - Cualquier `1` → `RegistryChainBroken` (SEV1).

   (Recomendado)

B) Solo bajo demanda

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Tiempos de la entrada (Domain Model)

A) `recorded_at` lo fija **la base** (`clock_timestamp()`) dentro del lock y es **no decreciente** en `seq` (si el reloj retrocede, se usa el `recorded_at` anterior). `occurred_at` lo manda el cliente y se acepta si está a no más de 5 min del reloj del servicio; si no, `validation_error`. Los dos entran en el hash (recomendado)

B) Solo `occurred_at`, enviado por el cliente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Tamaño máximo de una entrada (Business Rules)
La entrada `recommendation` lleva la explicación completa (~20 KB).

A) **64 KiB** por `canonical`; si es mayor, `413 payload_too_large`, y el cliente no recorta (en scoring eso termina en `registry_unavailable` → fail-closed). Alerta si alguna entrada supera los 48 KiB (recomendado)

B) Sin límite

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto (unit-of-work, story map, tipos de U0, flujos F13/F16/F21/F23/F24/F26/F28, F42, F44, X06, P-U1-05)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/decision-registry/functional-design/domain-entities.md` (tablas, columnas, checkpoints, proyecciones, expediente, informe de integridad)
- [x] 4. Generar `construction/decision-registry/functional-design/business-rules.md`
- [x] 5. Generar `construction/decision-registry/functional-design/business-logic-model.md` (append, idempotencia, checkpoint, verificación, expediente; propiedades PBT, incluida la stateful de US-401)
- [x] 6. Verificar el cumplimiento de las extensiones
