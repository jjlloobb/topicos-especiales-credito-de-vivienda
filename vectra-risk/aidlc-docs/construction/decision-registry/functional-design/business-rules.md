# Reglas de negocio — U3 `decision-registry`

Los IDs `BR-U3-xx` se referencian en los planes de tareas. La validación de los payloads
es de U0 (BR-U0-20..38, 95); aquí se fija lo propio del registro.

---

## 1. Append-only (US-401)

**BR-U3-01 — Solo `INSERT` y `SELECT`.** El rol `registry_app` no tiene `UPDATE`,
`DELETE` ni `TRUNCATE` (X06). Un intento falla con `permission denied`.

**BR-U3-02 — Segunda barrera.** Un trigger `BEFORE UPDATE OR DELETE OR TRUNCATE` sobre
`registry_entries` lanza una excepción para cualquier rol. Un superusuario puede
deshabilitarlo; esa manipulación la detectan los checkpoints (BR-U3-08).
El trigger y la regla de solo-anexar aplican a `registry_entries` y a la cadena, **no** a las
tablas derivadas del agregador (BR-U3-17), que se reconstruyen desde la cadena (precisado el 2026-10-08 por U9 FD).

**BR-U3-03 — Escritores autorizados.** Solo las identidades con `registry:append:case`,
`registry:append:scoring` o `registry:append:governance` pueden escribir, y cada una solo
sus tipos:

| Scope | `entry_type` permitidos |
|---|---|
| `registry:append:scoring` | `recommendation`, `fail_closed` |
| `registry:append:case` | `human_decision`, `explanation_view`, `fail_closed` |
| `registry:append:governance` | `model_event`, `policy_event`, `data_source_event`, `freeze`, `frozen_resolution` |

La regla de `fail_closed` es simétrica (precisado el 2026-10-06, revisión del FD de U8):
- desde `registry:append:scoring`, solo entradas **sin** `local_cause` ni `escalated_at` (una por intento, BR-U7-16); con cualquiera de ellos → `403 forbidden`;
- desde `registry:append:case`, solo entradas **con** `escalated_at` (el escalamiento, BR-U8-09); una entrada por intento desde ese scope → `403 forbidden`.

`genesis` y `checkpoint` solo los escribe el propio registro. Si un cliente los envía,
responde `403 forbidden`.

## 2. Escritura (Q4, Q5, Q9, Q10)

**BR-U3-04 — Serialización.** Cada append ocurre en una transacción con
`pg_advisory_xact_lock(<llave fija>)`:
0. buscar la `idempotency_key` (BR-U3-06): si existe, devolver el ack original o 409 sin escribir; si es nueva, comprobar la ventana de `occurred_at` (BR-U3-05) y `check_business_time` (BR-U0-37), y responder 422 si falla alguna (precisado el 2026-10-06, revisión del FD de U8);
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
si no, `validation_error`. La ventana se comprueba **después** de la búsqueda de
idempotencia y **solo para una llave nueva**. Un reintento cuya llave ya existe se resuelve
por BR-U3-06, aunque haya pasado más tiempo. `occurred_at` es el momento del **intento** de
escritura. Cuando el hecho de negocio es anterior (outbox de U8, reconciliador de U4), su
momento viaja en el payload (`decided_at`, `viewed_at`, `frozen_at`, `escalated_at`; U0
§5.2) (precisado el 2026-10-06). Ese momento está acotado por BR-U0-37: ≤ `occurred_at` y como
mucho 7 días antes; si no, `validation_error`. La cota la aplica la función
`vectra_contracts.validation.check_business_time` de U0, que el append llama (precisado el 2026-10-06, revisión del FD de U8). Como la ventana, esa cota se comprueba **solo para
llaves nuevas** y después de la búsqueda de idempotencia: un reenvío de una evidencia que ya
está en la cadena (por ejemplo, la decisión abandonada de BR-U8-18, reenviada semanas después)
recibe su ack original (precisado el 2026-10-06, revisión del FD de U8). `recorded_at`, la hora de la base, sigue siendo
la referencia de orden.

**BR-U3-06 — Idempotencia.** `idempotency_key` es obligatoria y única:
- si existe y sus **campos de negocio** (`entry_type`, `idempotency_key`, `actor`, `case_id`, `model_version_id`, `policy_version_id` y `payload`) coinciden con los de la nueva solicitud → se devuelve el `RegistryAck` original, sin escribir. No se comparan `seq`, `recorded_at`, `occurred_at` (cambia en cada intento, BR-U3-05), `correlation_id` (un reintento corre en otra traza) ni `contract_version` (puede haber un despliegue entre intentos) (precisado el 2026-10-06, revisión del FD de U8);
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

| `range` | Para el expediente (BR-U3-14) | Checkpoint anterior → checkpoint posterior o cabeza |

Precisado el 2026-10-03 por U3 NFR Requirements Q4: el re-hash completo nocturno no escala
a 10 años (~150 GB). Una reescritura sigue siendo detectable cada noche por la cadena de
checkpoints (BR-U3-12, paso 5 y 6).

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
- `freeze`: `{kind: system, id: bias-monitoring-job}` (el CronJob de U9, la única identidad que congela; antes `bias-monitoring-service`; revisión del FD de U9, 2026-10-08, H4);
- `model_event` `informe_validacion` y `validacion_fallida` enviados por el Job: `{kind: service, id: model-validation-job}`;
- `model_event` `validacion_fallida` por vencimiento del plazo: `{kind: system, id: governance-service}`;
- `model_event` `transicion_descartada` (compensación de U4 BR-U4-17): `{kind: system, id: governance-service}` (precisado el 2026-10-06, revisión del FD de U8).

Cuando el evento es una firma con MFA, el actor lleva `acr` y `auth_time` (BR-U0-72).
Precisado el 2026-10-03 al revisar los cambios de U4: la versión anterior solo exceptuaba
`freeze` y dejaba sin cubrir los eventos del Job de validación.

**BR-U3-17 — Agregador de monitoreo** (precisado el 2026-10-08 por U9 FD, Q4, Q5, CQ1, CQ2, CQ4 de U9; revisión del FD de U9, 2026-10-08: H2, H5, H6, H12).
- Un proceso propio, `registry-aggregator` (CronJob cada 5 min), con el rol `registry_aggregator`: `SELECT` sobre `registry_entries` y escritura **solo** sobre las tablas derivadas de domain-entities §1.3. No puede escribir `registry_entries` ni hacer `TRUNCATE`.
- **Marginales por atributo**: cada entrada válida suma una vez en cada uno de los cuatro atributos (`sexo`, `rango_edad`, `region`, `estrato`), con su grupo, su banda y su resultado. Nunca se guarda la combinación de las cuatro etiquetas: no hace falta para la métrica de U9 y podría reidentificar a una persona. Son hasta 198 filas por día y versión en `modelo` (22 grupos × 3 bandas × 3 resultados) y hasta 396 en `humana` (22 × 3 × 2 resultados × 3 decisiones) (cuarta revisión del FD de U9, 2026-10-10).
- **Lote** (una transacción, flujo en business-logic-model §2.5):
  1. `SELECT last_seq FROM monitoring_watermark WHERE id = 1 FOR UPDATE`: si dos corridas se solapan, la segunda espera y nunca cuenta dos veces;
  2. lee hasta 5 000 entradas con `seq > last_seq`, en orden de `seq` y de cualquier tipo; de las que no son `recommendation` ni `human_decision` lee solo el `seq`, y de esas dos solo los campos que usa (versión, momento de negocio, etiquetas, banda, resultado, decisión, `case_id`, `recommendation_entry_id`), extraídos en la consulta, no el `canonical` completo; el tamaño del lote es un value (5 000 por omisión) que se ajusta con la medición de memoria del plan (quinta revisión del FD de U9, 2026-10-10);
  3. suma, resta y avanza la marca hasta el último `seq` leído, y confirma.
- **Iteración**: cada corrida del CronJob repite lotes, cada uno en su transacción, hasta alcanzar la cabeza del registro o hasta 240 s (`activeDeadlineSeconds: 280`, una corrida cada 5 min) (segunda revisión del FD de U9, 2026-10-08).
- **Una recomendación por caso** (`monitoring_case_index`, que guarda solo `case_id`, `counted_seq`, `evaluated_at` y `fixed_by_decision`; para restar, las etiquetas, la versión, el día y el resultado se releen de `registry_entries` por `counted_seq`, así que la combinación de etiquetas nunca se guarda fuera del registro; segunda revisión del FD de U9, 2026-10-08):
  - sin decisión, cuenta la recomendación **válida** más reciente del caso por `evaluated_at` (en empate, el mayor `seq`); si llega una más reciente, resta la anterior de sus celdas y suma la nueva;
  - una `human_decision` fija la recomendación que referencia (`recommendation_entry_id` → `seq`): si no es la que se contaba, resta esa y suma la referenciada; desde entonces el caso queda fijado y una recomendación posterior a la decisión **no** cambia nada;
  - una recomendación con etiquetas inválidas nunca reemplaza a la contada: va a inválidas;
  - una `human_decision` que referencia una recomendación con etiquetas **inválidas** también **fija** el caso: se resta la contada, si había, y el caso queda con `fixed_by_decision = true` y `counted_seq = NULL` (si el caso no tenía fila en el índice, se crea con el `evaluated_at` de la recomendación referenciada; séptima revisión del FD de U9, 2026-10-10) (no cuenta en `modelo`); así una recomendación válida posterior no entra en `modelo` en lugar de la entregada (sexta revisión del FD de U9, 2026-10-10).
- **Decisiones humanas**: suman en la población `humana` con las etiquetas de la recomendación referenciada (leída de `registry_entries` por `seq`), por `decided_at`, con `final_outcome` y `decision`. Si la referenciada no existe o tiene etiquetas inválidas, la decisión cuenta como inválida. Si la referenciada **no existe**, o existe pero **no es una `recommendation`** (se trata igual que inexistente; sexta revisión del FD de U9, 2026-10-10), no hay versión a la que atribuirla: suma en `monitoring_entry_totals` con `model_version_id = '-'` (fila **no atribuible**) y su `seq` va a `monitoring_invalid` (cuarta revisión del FD de U9, 2026-10-10). La proyección la devuelve aparte, como un solo valor `unattributable_invalid` sobre el `unattributable_range` de la solicitud (no pertenece a ninguna versión) (sexta revisión del FD de U9, 2026-10-10).
- **Totales**: cada entrada `recommendation` o `human_decision` suma 1 en `monitoring_entry_totals.total` de su versión y día, sea válida o no; las inválidas suman además en `invalid`, y su `seq` va a `monitoring_invalid`.
- **Atraso**: 0 si `last_seq` es la cabeza del registro; si no, `now() − recorded_at` de la entrada `last_seq + 1`. Así un registro sin tráfico nunca aparece atrasado. El servicio lo calcula cada 60 s con el pool `projections` y lo expone como gauge `vectra_registry_monitoring_lag_seconds` en su puerto de métricas (F60; sin Pushgateway); la proyección `monitoring_daily` lo devuelve con cada respuesta (segunda revisión del FD de U9, 2026-10-08). Con más de 30 min → alerta `MonitoringAggregatorStale` (SEV2), y U9 no congela con conteos atrasados (BR-U9-10).
- **Retención**: las filas con `day` de más de 180 días se borran en cada corrida, en su propia transacción (en `monitoring_case_index`, por el `evaluated_at` guardado); una entrada más vieja que eso no se agrega.
- **Lectura**: la proyección `monitoring_daily` (`POST /v1/monitoring/daily:query`, de solo lectura, con el `MonitoringQuery` de U0 en el cuerpo; cada rango con `from_day ≤ to_day`, si no → 422; `unattributable_invalid` es un único valor sobre el `unattributable_range` pedido, 0 si no se pidió; séptima revisión del FD de U9, 2026-10-10) **agrega en el servidor**: recibe hasta 12 rangos de días por solicitud (4 por versión evaluada: 3 de `modelo` y 1 de `humana`; con más versiones, bias hace varias solicitudes; tercera revisión del FD de U9, 2026-10-10) y devuelve, por rango, la suma de conteos por (población, versión, atributo, grupo, banda, resultado, decisión), sin el día; así una solicitud de 12 rangos con 3 versiones devuelve unas 3 000 filas (hasta ~7 200 con celdas densas) y no cientos de miles (quinta revisión del FD de U9, 2026-10-10), y no retiene el pool `projections`, que comparte con `explanation` (segunda revisión del FD de U9, 2026-10-08).
- **Reconstrucción** (qué hace):
  1. `vectra-registry aggregator reset`, con `registry_migrator` (flujo **F108**; F44 es solo del Job de migración del sync): en una transacción, y tomando antes la fila de `monitoring_watermark` con `FOR UPDATE` (así espera a que termine el lote en curso del CronJob), vacía las **cuatro** tablas de conteo e índice y deja la fila `id = 1` con `last_seq` = el `seq` anterior a la primera entrada con `recorded_at ≥ now() − 181 días` (0 si el registro es más corto). La fila no se borra, porque el `FOR UPDATE` del lote la necesita.
  2. `vectra-registry aggregator run --until-head`, con `registry_aggregator` (F107): itera sin el tope de 240 s hasta la cabeza. Son ~181 días, ~1,8 M entradas con el volumen de NFR-U3-30, ~360 lotes; objetivo **≤ 1 h**, con 90 min de `activeDeadlineSeconds` como margen (NFR-U3-24).
  - **Por qué 181 días**: el momento de negocio de una entrada nunca es posterior a su `occurred_at` (BR-U0-37), y `occurred_at` supera a `recorded_at` a lo sumo en 5 min (BR-U3-05); el día extra cubre esos 5 min y el corte por fecha UTC. Una entrada registrada antes del corte tiene su día fuera de los 180 días de retención.
  - **El CronJob no se suspende**: sigue corriendo y sus lotes se intercalan con los del Job, porque los dos toman la marca con `FOR UPDATE` y ninguno cuenta dos veces. Solo suma throughput.
  - Las tablas son derivadas y `verify_chain` no las toca; el append no cambia.
- **Exclusión mutua** (aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10, hallazgo 2): `aggregator reset` y `aggregator run --until-head` toman al empezar un *advisory lock* de PostgreSQL con una llave fija de la reconstrucción (`pg_try_advisory_lock`) y lo sostienen hasta terminar; si ya está tomado, terminan con error sin tocar nada. Así nunca corren dos reconstrucciones a la vez ni un reset durante un rebuild, que haría retroceder la marca de agua. El CronJob del agregador no toma ese lock: lo serializa el `FOR UPDATE` de la marca.
- **Lanzamiento del runbook `monitoring-rebuild`** (aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10; reemplaza los dos diseños anteriores, hooks de sync y K15):
  - los Jobs viven en una **Application de Argo CD aparte**, `decision-registry-rebuild` (chart propio en `decision-registry/chart-rebuild/`, mismos namespace y roles), y no en la del registro: así un sync largo del rebuild nunca bloquea un sync o un rollback de `decision-registry-service`, que es Critical (revisión del Infrastructure Design de U9, 2026-10-10);
  - ese chart renderiza los dos Jobs como **recursos normales** (no hooks) **solo** cuando el value `monitoringRebuild.runId` está fijado: `registry-aggregator-reset-<runId>` en una `sync-wave` y `registry-aggregator-rebuild-<runId>` en la siguiente. Argo CD espera a que el reset termine (`Healthy`) antes de aplicar el rebuild;
  - el runbook es un **PR** que fija un `runId` nuevo y un **sync manual con prune** aprobado (AUTONOMIA-01); el prune retira los Jobs del `runId` anterior. **Formato del `runId`**: `AAAAMMDD-HHMM` (UTC) del momento del PR. Un check de CI del repositorio GitOps rechaza un `runId` que ya figure en `rebuild-history.yaml`, y el mismo PR lo agrega ahí (revisión del Infrastructure Design de U9, 2026-10-10). Los crea Argo CD (K04) con el pod spec revisado en el PR: nadie puede cambiar imagen, comando ni volúmenes, y no hay binding nuevo ni excepción a AUTONOMIA-01;
  - un Job completado **no** se vuelve a ejecutar en un sync posterior, porque el recurso existe y no cambió. Si el PR que quita el `runId` se olvida, no pasa nada; el siguiente `runId` reemplaza al anterior y el sync poda los Jobs viejos. Por eso no llevan `ttlSecondsAfterFinished`: si Kubernetes los borrara, Argo CD los recrearía y la reconstrucción volvería a correr;
  - **a verificar en kind** (Paso 18): si la versión de Argo CD que se fije espera la salud de la última `sync-wave`, el sync queda en curso hasta que termine el rebuild (≤ 90 min); es aceptable porque ese sync no lleva otros cambios de U3;
  - **si el rebuild supera 1 h** (revisión del Infrastructure Design de U9, 2026-10-10): no hace falta relanzarlo. El CronJob del agregador nunca se suspende y sigue avanzando desde la marca de agua, así que, si el Job vence a los 90 min o falla, el CronJob completa la reconstrucción a su ritmo (unas 12 corridas por hora). El runbook vigila el atraso: si baja, se espera; si no baja durante 2 h, se escala a SEV1 y se investiga (por ejemplo, una entrada que hace fallar el lote) antes de un `runId` nuevo;
  - **un Job fallido no pasa desapercibido**: tras el reset, el atraso del agregador es de ~181 días y `MonitoringAggregatorStale` salta; el runbook la silencia durante 2 h, y si el rebuild falla o no termina, el atraso no baja y la alerta vuelve al vencer el silencio. Un Job que no obtiene el *advisory lock* también falla y deja la alerta activa.
  - **`MonitoreoSesgoDetenido` es esperada** durante la reconstrucción (revisión del plan de tareas de U9, 2026-10-10): mientras el agregador esté atrasado, las corridas de U9 fallan por atraso (BR-U9-10) y la alerta salta a W. El runbook la silencia junto con `MonitoringAggregatorStale`, con el mismo vencimiento de 2 h (y la de SEV1 a 2W también), y anota en el silencio el `runId`. Si al vencer el silencio el atraso no bajó, las dos vuelven.

## 6. Alertas

| Alerta | Severidad | Origen |
|---|---|---|
| `RegistryChainBroken` | SEV1 | BR-U3-13, 14 |
| `RegistryDbWritesBlocked` | SEV1 | BR-U3-04 (sin réplica síncrona; definida en U1) |
| `RegistryVerificationFailed` | SEV2 | BR-U3-13 |
| `CheckpointExportFailed` | SEV2 | BR-U3-08 |
| `CheckpointMissing` | SEV2 | Sin checkpoint en más de 2 h |
| `RegistryEntryLarge` | SEV3 | BR-U3-07 |
| `MonitoringAggregatorStale` | SEV2 | BR-U3-17 (precisado el 2026-10-08 por U9 FD) |

## 7. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 `RegistryEntryIn` | `idempotency_key` obligatoria | Q5 |
| U0 §5.2 | `entry_type` `genesis` y `checkpoint` | Q1, Q3 |
| U0 §5.3 | `seq` contiguo, `contract_version` y `canonical`; el BFF une los identificadores | Q2, Q7 |
| U0 BR-U0-08 | La `idempotency_key` del append es fija por intento de evaluación | Q5 |
| `component-methods.md` (BFF `get_dossier`) | El BFF compone el expediente con registry + case | Q7 |
| Infraestructura (U3 Infrastructure Design) | Bucket WORM `registry-checkpoints` y llave Ed25519 en la bóveda | Q1 |
| U3 (esta unidad), por U9 FD 2026-10-08 | BR-U3-17 (agregador), rol `registry_aggregator`, proyecciones `monitoring_daily` y `monitoring_freezes`, PBT-U3-09, alerta `MonitoringAggregatorStale`; flujo F107 | U9 FD Q4, Q8; CQ1, CQ2, CQ4 |
| U3 (esta unidad), revisión del FD de U9, 2026-10-08 | Marginales por atributo; esquema de las tablas derivadas (domain-entities §1.3) con `monitoring_entry_totals`; definición del atraso; `FOR UPDATE` de la marca; retención y reconstrucción; `monitoring_freezes` con `frozen_resolution`; actor del `freeze` = `bias-monitoring-job` | H1, H2, H4, H5, H6, H12 |
| U3 (esta unidad), tercera revisión del FD de U9, 2026-10-10 | Reset con `last_seq` antes de los últimos días de retención; volúmenes alineados con NFR-U3-30; rangos por versión y varias solicitudes | FD de U9 |
| U3 (esta unidad), cuarta revisión del FD de U9, 2026-10-10 | 181 días con la justificación corregida; decisión sin recomendación como fila no atribuible; filas de `humana`; purga del índice por `evaluated_at` | FD de U9 |
| U3 (esta unidad), quinta revisión del FD de U9, 2026-10-10 | Orden del total en el agregador; lectura de solo los campos usados y lote configurable; índice por `recorded_at`; `aggregator run`; escenarios del agregador | FD de U9 |
| U3 (esta unidad), sexta revisión del FD de U9, 2026-10-10 | Referencia que no es `recommendation` como inexistente; decisión sobre una inválida fija el caso; Job a demanda de reconstrucción; `POST …:query`; `unattributable_invalid` único | FD de U9 |
| U3 (esta unidad), séptima revisión del FD de U9, 2026-10-10 | Job a demanda en la infraestructura (INF-U3-03/04) y su identidad; `Forbid` no lo cubre; validación de rangos; fila nueva del índice; buckets unificados; generador sintético en el tech-stack | FD de U9 |
| U3 (esta unidad), octava revisión del FD de U9, 2026-10-10 | F108 para el reset; Jobs a demanda en el inventario, logical-components y deployment-architecture; NFR-U3-24 y 42 precisados | FD de U9 |
| U3 (esta unidad), revisión del NFR Requirements de U9, 2026-10-10 | ~~Los Jobs a demanda se lanzan como hooks de sync de Argo CD activados por `monitoringRebuild.runId`, tras un PR y un sync manual; sin binding nuevo~~ **Reemplazado** por la revisión siguiente | NFR Requirements de U9 |
| U3 (esta unidad), revisión del NFR Requirements de U9, 2026-10-10 (segunda) | ~~Lanzamiento con CronJobs suspendidos y `kubectl create job --from` por un operador (K15, `restrict-manual-jobs`), TTL de 7 días, sin suspender el CronJob; falla visible por `MonitoringAggregatorStale`; BR-U3-11 y BR-U3-17 reorganizados~~ **Reemplazado** (salvo la reorganización de BR-U3-11 y 17) | NFR Requirements de U9 |
| U3 (esta unidad), aclaración del NFR Requirements de U9 (Q1 = A), 2026-10-10 | Jobs normales en Git con `runId` y `sync-wave`, creados por Argo CD tras un PR y un sync manual; *advisory lock* de la reconstrucción; sin K15 ni `restrict-manual-jobs` | NFR Requirements de U9 |
| U3 (esta unidad), revisión del Infrastructure Design de U9, 2026-10-10 | Application aparte `decision-registry-rebuild`; `runId` con fecha, historial y check de CI; sync con prune; contingencia si el rebuild supera 1 h | Infrastructure Design de U9 |
