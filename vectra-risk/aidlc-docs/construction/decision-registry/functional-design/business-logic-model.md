# Modelo de lógica — U3 `decision-registry`

## 1. Módulos lógicos

| Módulo | Responsabilidad | Reglas |
|---|---|---|
| `append` | Autorización por scope y tipo, validación (U0), idempotencia, lock, hash, insert, commit síncrono | BR-U3-03..07 |
| `chain` | Funciones puras: `canonicalize(entry) -> bytes`, `link(prev_hash, canonical) -> hash`, `decode(canonical)` | BR-U3-09, 10 |
| `checkpoint` | Firmar, encadenar y exportar al bucket WORM; rotación con *cross-signing* | BR-U3-08 |
| `verify` | Recorrer un rango y devolver `IntegrityReport` (función pura sobre un iterador de filas + checkpoints) | BR-U3-11..13 |
| `projections` | Proyectar entradas según el consumidor | BR-U3-15 |
| `dossier` | Entradas del caso + verificación `range` | BR-U3-14 |
| `cli` | `vectra-registry verify --mode full|nightly|incremental|range` con códigos 0/1/2; `checkpoint`; `archive`; `aggregator run` (el comando del CronJob `registry-aggregator`; con `--until-head`, el Job a demanda del runbook) y `aggregator reset` (quinta revisión del FD de U9, 2026-10-10) | BR-U3-11, 13, 17 |
| `aggregator` | Conteos de monitoreo por `seq` con marca de agua, una recomendación por caso, inválidas (precisado el 2026-10-08 por U9 FD) | BR-U3-17 |

`chain` y `verify` no tienen E/S: reciben datos y devuelven resultados. Así se prueban
con propiedades y se reutilizan en el servicio, la CLI y `restore-drill`.

## 2. Flujos

### 2.1 Append

```text
POST /v1/entries (token de servicio)
  -> U0: authn, scope, validación del payload (BR-U0-95: sin identificadores)
  -> ¿entry_type permitido para el scope? no -> 403 (BR-U3-03)
  -> fail_closed: ¿forma del payload acorde al scope? (scoring sin local_cause ni escalated_at;
       case solo con escalated_at) no -> 403 (BR-U3-03)
  -> ¿canonical > 64 KiB? -> 413 (BR-U3-07)
  -> BEGIN; pg_advisory_xact_lock
       ¿idempotency_key existe? sí: ¿mismos campos de negocio (sin occurred_at, correlation_id
          ni contract_version)? -> ack original : 409 (BR-U3-06)
       llave nueva: ¿|occurred_at − now| ≤ 5 min? no -> 422 (BR-U3-05)
                    check_business_time(entry, now) (BR-U0-37: momentos de negocio ≤ occurred_at
                    y ≤ 7 días) falla -> 422
       cabeza -> recorded_at = max(now, cabeza.recorded_at) (BR-U3-05)
       canonical = JCS(entry + seq + recorded_at + contract_version)
       hash = SHA-256(prev_hash ‖ canonical)
       INSERT
     COMMIT (synchronous_commit = remote_apply)
       sin réplica -> 503 dependency_unavailable (el cliente: registry_unavailable)
  -> RegistryAck {registry_entry_id = seq, seq, recorded_at}
```

### 2.2 Checkpoint (cada hora)

```text
cabeza (seq_h, hash_h) -> firma Ed25519 de JCS({seq_h, hash_h, recorded_at})
  -> append interno entry_type=checkpoint (por el mismo camino del 2.1)
  -> PUT checkpoints/{seq_h}.json al bucket WORM (object lock)
       falla -> reintento con backoff; CheckpointExportFailed
```

### 2.3 Verificación

```text
verify(rows[from..to], checkpoints_cadena, checkpoints_worm, llave_publica):
  para cada fila en orden:
    seq contiguo? prev_hash == hash anterior? hash == SHA-256(prev ‖ canonical)?
    columnas == decode(canonical)?
    si es checkpoint: firma válida? checkpoint_hash == hash[checkpoint_seq]?
  para cada checkpoint WORM del rango: coincide con la entrada de la cadena?
  -> integra | inconsistente(primer_seq, motivo) | error
```

### 2.4 Expediente

```text
GET /v1/dossiers/{case_id} (cro | cumplimiento)
  -> entradas del caso (índice case_id), en orden de seq
  -> rango: checkpoint anterior a la primera .. checkpoint posterior a la última (o la cabeza)
  -> verify(rango) -> IntegrityStatus
  -> RegistryDossier ; el BFF agrega los identificadores desde case-service
```

### 2.5 Agregador de monitoreo (BR-U3-17; revisión del FD de U9, 2026-10-08, H12)

```text
registry-aggregator (CronJob cada 5 min, rol registry_aggregator)
  TX:
    last_seq = SELECT last_seq FROM monitoring_watermark WHERE id = 1 FOR UPDATE
    lote = registry_entries WHERE seq > last_seq ORDER BY seq LIMIT 5000   (todos los tipos)
    por cada entrada:
      otro tipo -> nada
      recommendation (versión v, día de evaluated_at):
        totals[modelo, v, día].total += 1
        etiquetas inválidas -> totals.invalid += 1 ; monitoring_invalid(seq) ; fin
        índice del caso:
          no existe                         -> sumar sus 4 marginales ; crear índice
          fixed_by_decision                 -> nada (recomendación posterior a la decisión)
          (evaluated_at, seq) > el contado  -> restar el contado ; sumar esta ; actualizar índice
          si no                             -> nada
      human_decision (día de decided_at):
        referenciada = registry_entries[recommendation_entry_id]
        no existe o no es recommendation -> totals[humana, '-', día] (no atribuible): total += 1, invalid += 1 ;
             monitoring_invalid(seq) ; fin
        v = versión de la referenciada ; totals[humana, v, día].total += 1      (una sola vez, ya con v)
        etiquetas inválidas -> totals[humana, v, día].invalid += 1 ; monitoring_invalid(seq) ;
             índice del caso: restar la contada si había ; counted_seq = NULL ; fixed_by_decision = true
             (sin fila previa: crearla con el evaluated_at de la referenciada) ; fin
        sumar 4 marginales en humana (final_outcome, decision)
        índice del caso: si cuenta otra -> restarla y sumar la referenciada ; fixed_by_decision = true
    para restar: etiquetas, versión, día y resultado se releen de registry_entries[counted_seq]
    last_seq = último seq del lote
  COMMIT        (si el proceso muere, el lote completo se repite sin contar dos veces)
  repetir lotes hasta la cabeza o 240 s
  TX aparte: borrar filas con day de más de 180 días; en monitoring_case_index, por evaluated_at
```

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U3-01 | `append` + `verify` | **Stateful (PBT-06, US-401)**: para toda secuencia de comandos (append válido, reintento idempotente con la misma llave, reintento con la misma llave y otro `occurred_at`, `correlation_id` o `contract_version` → ack original aunque hayan pasado más de 5 min, reintento con la misma llave y un momento de negocio de más de 7 días → ack original (la cota solo rige para llaves nuevas, precisado el 2026-10-06, revisión del FD de U8), reintento con la misma llave y otro contenido, checkpoint), la cadena resultante siempre verifica `integra`, `seq` es contiguo, los reintentos iguales no agregan filas y los distintos dan 409 | Stateful (máquina de estados contra un modelo en memoria) | Secuencias de comandos con payloads de los 9 tipos de negocio generados por las estrategias de U0 |
| PBT-U3-02 | `verify` | Para toda cadena válida y **una** manipulación (cambiar un byte de `canonical`, de `hash` o de una columna, borrar una fila, intercambiar dos filas), el verificador da `inconsistente` y el primer `seq` informado es el de la manipulación (o el siguiente, si se borró una fila) | Invariante + oráculo | Cadenas de 1 a 500 entradas y una manipulación aleatoria |
| PBT-U3-03 | `verify` | Para toda cadena válida reescrita por completo desde un `seq` k **anterior** a un checkpoint (con los hashes recalculados), el verificador da `inconsistente` con motivo `checkpoint_mismatch` o `checkpoint_signature` | Invariante | Cadenas con checkpoints y k aleatorio |
| PBT-U3-04 | `chain` | `canonicalize(decode(canonical)) == canonical` para toda entrada (los bytes guardados son un punto fijo de JCS) | Round-trip / idempotencia | Entradas de todos los tipos, con Unicode y decimales |
| PBT-U3-05 | `chain` | La verificación de una cadena escrita con `contract_version` X da el mismo resultado aunque el código del verificador tenga el contrato X+1 (no se vuelve a serializar) | Invariante | Cadenas generadas con un contrato y verificadas con otro que agrega un campo opcional |
| PBT-U3-06 | `projections` | Para toda entrada y todo consumidor, la proyección contiene **solo** los campos permitidos de su fila en domain-entities §3, y `feature_vector`, `justification` y `actor_id` nunca aparecen fuera de `full` | Invariante | Entradas de todos los tipos × los 4 consumidores |
| PBT-U3-07 | `append` | `recorded_at` es no decreciente en `seq` para todo reloj generado (incluso si retrocede) | Invariante | Secuencias de relojes con saltos hacia atrás |
| PBT-U3-08 | `append` | Para una llave nueva, `occurred_at` se acepta ⇔ `|occurred_at − now| ≤ 300 s`; para una llave existente con el mismo contenido, la ventana no aplica (ack original) (precisado el 2026-10-06) | Oráculo | Desfases alrededor de ±300 s |
| PBT-U3-09 | `aggregator` | **Equivalencia** (precisado el 2026-10-08 por U9 FD; revisión del FD de U9, 2026-10-08): para toda secuencia de entradas `recommendation` y `human_decision` (varias recomendaciones por caso, decisiones que referencian una que no es la última, recomendaciones posteriores a la decisión, empates de `evaluated_at`, etiquetas inválidas, una inválida como la más reciente, **decisiones que referencian una recomendación inexistente, una entrada que no es `recommendation` o una recomendación inválida**; quinta y sexta revisión del FD de U9, 2026-10-10) y otras entradas intercaladas y todo punto de corte entre lotes con reinicios, `monitoring_daily` y `monitoring_entry_totals` son iguales al recálculo directo desde las entradas con la regla de una por caso; los conteos nunca son negativos; repetir un lote no cambia nada; dos corridas concurrentes dan el mismo resultado que una (marca con `FOR UPDATE`) | Equivalencia / Idempotencia | Secuencias de 1 a 200 entradas y cortes aleatorios |

**Pruebas de ejemplo obligatorias (PBT-10):**
- `UPDATE`, `DELETE` y `TRUNCATE` con `registry_app` → `permission denied` (US-401);
- con el trigger habilitado, un `UPDATE` de superusuario → excepción;
- superusuario que deshabilita el trigger, edita y recalcula → el verificador lo detecta por checkpoint (US-402);
- expediente de un caso decidido: narrativa byte a byte igual a la guardada; solo `cro` y `cumplimiento` (US-403);
- los 5 tipos de evento de gobierno, con actor y rol (US-404);
- CLI: `exit 0` en una cadena íntegra, `1` en una alterada, `2` con la base caída;
- un append sin réplica síncrona → 503;
- agregador (revisión del FD de U9, 2026-10-08, H12): dos recomendaciones de un caso y una `human_decision` que referencia la primera → cuenta la primera; una recomendación posterior a la decisión → no cambia nada; una recomendación inválida más reciente que la contada → la contada sigue y la inválida suma en `invalid`; `total` cuenta las cuatro entradas;
- agregador sin entradas nuevas durante 2 h (registro sin tráfico) → atraso 0 y sin `MonitoringAggregatorStale`; con una entrada pendiente de hace 31 min → atraso > 30 min y alerta;
- `registry_aggregator` intenta `TRUNCATE` → `permission denied`; `vectra-registry aggregator reset` con `registry_migrator` vacía las cuatro tablas, deja `monitoring_watermark` con `id = 1` y `last_seq` justo antes de la primera entrada de los últimos 181 días (0 en un registro más corto), y el agregador las reconstruye iguales a las que había (tercera revisión del FD de U9, 2026-10-10);
- una corrida con 20 000 entradas pendientes procesa 4 lotes en la misma corrida y termina en la cabeza (segunda revisión del FD de U9, 2026-10-08);
- `monitoring_freezes`: un `freeze` seguido de una `frozen_resolution` con `action = reactivar` → la proyección devuelve el congelamiento con su resolución y el `recorded_at` de la reactivación (segunda revisión del FD de U9, 2026-10-08);
- `human_decision` que referencia una entrada `freeze` (existe, pero no es `recommendation`) → tratada como inexistente: fila no atribuible (sexta revisión del FD de U9, 2026-10-10);
- `human_decision` sobre una recomendación inválida → el caso queda fijado sin recomendación contada; una recomendación válida posterior del caso no suma en `modelo` (sexta revisión del FD de U9, 2026-10-10);
- `unattributable_invalid` (séptima revisión del FD de U9, 2026-10-10): con `unattributable_range` = días 1..10 y una decisión no atribuible en el día 5 y otra en el día 12 → 1; sin `unattributable_range` → 0; el valor no aparece en `totals`;
- `POST /v1/monitoring/daily:query` con un rango de `from_day > to_day` → 422 (séptima revisión del FD de U9, 2026-10-10);
- `human_decision` cuya recomendación referenciada no existe → fila no atribuible (`model_version_id = '-'`) en `monitoring_entry_totals`, con su `seq` en `monitoring_invalid` (cuarta revisión del FD de U9, 2026-10-10);
- purga: filas con `day` de 181 días → borradas en la corrida; de 179 días → intactas; en `monitoring_case_index`, por `evaluated_at` (segunda revisión del FD de U9, 2026-10-08);
- `monitoring_daily` con 12 rangos de hasta 90 días de 3 versiones → como máximo unas 7 200 filas (12 rangos × hasta 594 filas), servidas dentro del tiempo límite de 2 s del pool `projections`; una consulta de `explanation` concurrente no espera más de su límite (segunda revisión del FD de U9, 2026-10-08);
- `registry_verifier` lee `monitoring_daily` → éxito; lee `monitoring_case_index` → `permission denied` (segunda revisión del FD de U9, 2026-10-08).

## 4. Cumplimiento de extensiones (Functional Design U3)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | Alertas con severidad de `business-rules.md` §6 (`RegistryChainBroken` SEV1, `CheckpointMissing`, `CheckpointExportFailed`, `RegistryVerificationFailed`, `RegistryEntryLarge`), dentro del proceso de U1 (P-U1-10) |
| RESILIENCY-07 | Cumple | `MonitoringAggregatorStale` (SEV2) sobre `vectra_registry_monitoring_lag_seconds`, con `absent()` (BR-U3-17; tercera revisión del FD de U9, 2026-10-10) |
| SECURITY-05 | Cumple | Validaciones propias de U3, además de las de U0: tolerancia de ±5 min de `occurred_at` (BR-U3-05) y límite de 64 KiB por entrada (BR-U3-07) |
| SECURITY-06 | Cumple | Roles de base de domain-entities §1.2; scopes por tipo (BR-U3-03) |
| SECURITY-08 | Cumple | Escritura solo por scope y tipo de entrada (BR-U3-03); lectura por proyección según el rol o scope, con 403 y sin datos parciales fuera de lo permitido (BR-U3-15) |
| SECURITY-13 | Cumple | Cadena + checkpoints firmados + WORM (BR-U3-08..12); datos críticos auditables con actor y tiempo |
| SECURITY-14 | Cumple | Registro tamper-evident; alertas §6 |
| SECURITY-15 | Cumple | Sin ack sin commit síncrono (BR-U3-04); expediente marcado si no verifica |
| AUTONOMIA-06 | Cumple | El ack del registro es condición de `Recommendation` (BR-U0-02, causa 10); sin ack → fail-closed |
| AUTONOMIA-05 | Cumple | El registro no recibe ni consulta identificadores directos (BFF compone el expediente) |
| PBT-01 | Cumple | §3 |
| PBT-06 | Cumple | PBT-U3-01 (stateful, pedido explícitamente por US-401) |
| PBT-07 | Cumple | Columna «Generadores» de §3: estrategias de U0 para los payloads, cadenas con manipulaciones y relojes con retrocesos |
| PBT-10 | Cumple | Pruebas de ejemplo de §3 |
