# Reglas de negocio — U3 `decision-registry`

Los IDs `BR-U3-xx` se referencian en los planes de tareas. La validación de los payloads
es de U0 (BR-U0-20..36, 95); aquí se fija lo propio del registro.

---

## 1. Append-only (US-401)

**BR-U3-01 — Solo `INSERT` y `SELECT`.** El rol `registry_app` no tiene `UPDATE`,
`DELETE` ni `TRUNCATE` (X06). Un intento falla con `permission denied`.

**BR-U3-02 — Segunda barrera.** Un trigger `BEFORE UPDATE OR DELETE OR TRUNCATE` sobre
`registry_entries` lanza una excepción para cualquier rol. Un superusuario puede
deshabilitarlo; esa manipulación la detectan los checkpoints (BR-U3-08).

**BR-U3-03 — Escritores autorizados.** Solo las identidades con `registry:append:case`,
`registry:append:scoring` o `registry:append:governance` pueden escribir, y cada una solo
sus tipos:

| Scope | `entry_type` permitidos |
|---|---|
| `registry:append:scoring` | `recommendation`, `fail_closed` |
| `registry:append:case` | `human_decision`, `explanation_view`, `fail_closed` |
| `registry:append:governance` | `model_event`, `policy_event`, `data_source_event`, `freeze`, `frozen_resolution` |

`genesis` y `checkpoint` solo los escribe el propio registro. Si un cliente los envía,
responde `403 forbidden`.

## 2. Escritura (Q4, Q5, Q9, Q10)

**BR-U3-04 — Serialización.** Cada append ocurre en una transacción con
`pg_advisory_xact_lock(<llave fija>)`:
1. leer la cabeza (`seq`, `hash`, `recorded_at`);
2. fijar `recorded_at` (BR-U3-05);
3. construir `canonical` (JCS);
4. calcular `hash = SHA-256(prev_hash ‖ canonical)`;
5. `INSERT` con `seq = cabeza + 1`;
6. `COMMIT` con `synchronous_commit = remote_apply`.

El ack (`RegistryAck`) se devuelve **solo** después del commit. Si el commit no se confirma
(sin réplica síncrona), responde `503 dependency_unavailable` y el cliente lo trata como
`registry_unavailable` (fail-closed, BR-U0-02).

**BR-U3-05 — Tiempos.** `recorded_at = max(clock_timestamp(), recorded_at de la cabeza)`,
así que es no decreciente en `seq`. `occurred_at` se acepta si `|occurred_at − now| ≤ 5 min`;
si no, `validation_error`.

**BR-U3-06 — Idempotencia.** `idempotency_key` es obligatoria y única:
- si existe y su `canonical`, sin `seq` ni `recorded_at`, coincide con el de la nueva solicitud → se devuelve el `RegistryAck` original, sin escribir;
- si existe con contenido distinto → `409 conflict_state`.

La comparación ocurre dentro del lock, así que dos reintentos concurrentes no producen dos
entradas.

**BR-U3-07 — Tamaño.** `canonical` ≤ 64 KiB; si es mayor, `413 payload_too_large`.
El cliente no recorta: en scoring eso termina en fail-closed. Una entrada > 48 KiB emite
la métrica `vectra_registry_entry_size_bytes` por encima del umbral de alerta.

## 3. Cadena y checkpoints (Q1, Q2, Q3)

**BR-U3-08 — Checkpoints.** Cada hora, y al terminar cada verificación completa, el
registro:
1. pide a la bóveda que firme `JCS({checkpoint_seq, checkpoint_hash, recorded_at})` con la llave Ed25519 (motor de firma de la bóveda; la llave **nunca** sale de ella, U3 NFR Q5). Si la bóveda no responde, el checkpoint se atrasa y se alerta `CheckpointMissing`; los appends siguen;
2. agrega una entrada `checkpoint` a la cadena;
3. copia el checkpoint al bucket WORM.

Si la copia al bucket falla, se reintenta y se alerta `CheckpointExportFailed` (SEV2); la
entrada en la cadena se mantiene.

**BR-U3-09 — Bytes canónicos inmutables.** El hash se calcula y se verifica **sobre los
bytes guardados en `canonical`**. El verificador nunca vuelve a serializar con un contrato
más nuevo. Las columnas consultables deben coincidir con los valores decodificados de
`canonical`; si no coinciden → `column_mismatch`.

**BR-U3-10 — Génesis.** La primera migración inserta la entrada `seq = 0`
(`entry_type = genesis`, `prev_hash` de 32 bytes en cero) con la versión del esquema, la
versión del contrato y la huella de la llave pública de checkpoints. No puede haber otra
génesis.

## 4. Verificación (Q8, US-402)

**BR-U3-11 — Modos.**

| Modo | Cuándo | Desde |
|---|---|---|
| `incremental` | Cada 15 min (CronJob) | El último checkpoint verificado |
| `nightly` | Cada noche (CronJob) | Cadena de checkpoints completa (firmas y enlaces) + re-hash de las entradas de los últimos 7 días + re-hash de una muestra aleatoria del 1 % de los segmentos más antiguos (entre checkpoints), distinta cada noche |
| `full` | Cada mes (CronJob, fuera del horario operativo, prioridad baja), bajo demanda (`cro` con MFA, API) y en `restore-drill` | `seq = 0`, re-hash de todo |

Precisado el 2026-10-03 por U3 NFR Requirements Q4: el re-hash completo nocturno no escala
a 10 años (~150 GB). Una reescritura sigue siendo detectable cada noche por la cadena de
checkpoints (BR-U3-12, paso 5 y 6).
| `range` | Para el expediente (BR-U3-14) | Checkpoint anterior → checkpoint posterior o cabeza |

**BR-U3-12 — Qué verifica**, en orden de `seq`:
1. `seq` contiguo (`seq_gap`);
2. `prev_hash` = `hash` de la anterior (`link`);
3. `hash = SHA-256(prev_hash ‖ canonical)` (`hash`);
4. columnas = `canonical` decodificado (`column_mismatch`);
5. cada entrada `checkpoint`: firma válida con la llave vigente (`checkpoint_signature`) y `checkpoint_hash` = `hash` de `checkpoint_seq` en la cadena (`checkpoint_mismatch`);
6. cada checkpoint del bucket WORM coincide con su entrada en la cadena (`checkpoint_mismatch`).

El informe da el **primer** `seq` inconsistente y su motivo.

**BR-U3-13 — Resultado.** `inconsistente` → alerta `RegistryChainBroken` (SEV1) y
`exit 1`. `error` → `exit 2` y alerta `RegistryVerificationFailed` (SEV2). El registro
sigue aceptando appends (para no perder evidencia), pero todo expediente posterior muestra
«integridad NO verificada» hasta que una verificación completa vuelva a dar `integra`.

## 5. Lectura (Q6, Q7; US-403, FR-REG-04)

**BR-U3-14 — Expediente.** `GET /v1/dossiers/{case_id}` (solo `cro` y `cumplimiento`):
- entradas del caso en orden, con `canonical` exacto;
- `IntegrityStatus` del tramo `range`;
- `last_full_verification`;
- `delivery_status` de cada entrada `recommendation`: `entregada` si alguna `human_decision` del caso la referencia en `recommendation_entry_id`; `no_entregada` si el caso tiene una `human_decision` que referencia otra; `pendiente_de_decision` si todavía no hay `human_decision` (P-U7-03) (precisado el 2026-10-03 por U7 NFR Design Q3).

Si el tramo no verifica → `status = not_verified` y alerta `RegistryChainBroken`. El BFF
agrega los identificadores directos desde case-service.

**BR-U3-15 — Proyecciones.** Cada consulta se resuelve con la proyección del consumidor
(domain-entities §3). Pedir una proyección o un campo fuera de lo permitido → `403
forbidden`, sin datos parciales. El filtrado lo hace el servicio, no el cliente.

**BR-U3-16 — Eventos de gobierno (US-404).** Las entradas `model_event`, `policy_event`,
`data_source_event`, `freeze` y `frozen_resolution` que provoca una persona exigen `actor`
con `user_id` y `role`; los eventos derivados dentro de esa misma acción (`inactivado`,
`historica`, `evaluacion_iniciada`) llevan el mismo actor. Las excepciones, con actor de
servicio o de sistema, son:
- `freeze`: `{kind: system, id: bias-monitoring-service}`;
- `model_event` `informe_validacion` y `validacion_fallida` enviados por el Job: `{kind: service, id: model-validation-job}`;
- `model_event` `validacion_fallida` por vencimiento del plazo: `{kind: system, id: governance-service}`.

Cuando el evento es una firma con MFA, el actor lleva `acr` y `auth_time` (BR-U0-72).
Precisado el 2026-10-03 al revisar los cambios de U4: la versión anterior solo exceptuaba
`freeze` y dejaba sin cubrir los eventos del Job de validación.

## 6. Alertas

| Alerta | Severidad | Origen |
|---|---|---|
| `RegistryChainBroken` | SEV1 | BR-U3-13, 14 |
| `RegistryDbWritesBlocked` | SEV1 | BR-U3-04 (sin réplica síncrona; definida en U1) |
| `RegistryVerificationFailed` | SEV2 | BR-U3-13 |
| `CheckpointExportFailed` | SEV2 | BR-U3-08 |
| `CheckpointMissing` | SEV2 | Sin checkpoint en más de 2 h |
| `RegistryEntryLarge` | SEV3 | BR-U3-07 |

## 7. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 `RegistryEntryIn` | `idempotency_key` obligatoria | Q5 |
| U0 §5.2 | `entry_type` `genesis` y `checkpoint` | Q1, Q3 |
| U0 §5.3 | `seq` contiguo, `contract_version` y `canonical`; el BFF une los identificadores | Q2, Q7 |
| U0 BR-U0-08 | La `idempotency_key` del append es fija por intento de evaluación | Q5 |
| `component-methods.md` (BFF `get_dossier`) | El BFF compone el expediente con registry + case | Q7 |
| Infraestructura (U3 Infrastructure Design) | Bucket WORM `registry-checkpoints` y llave Ed25519 en la bóveda | Q1 |
