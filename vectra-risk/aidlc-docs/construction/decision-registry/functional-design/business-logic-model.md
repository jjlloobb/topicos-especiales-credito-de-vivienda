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
| `cli` | `vectra-registry verify --mode full|nightly|incremental|range` con códigos 0/1/2 | BR-U3-11, 13 |

`chain` y `verify` no tienen E/S: reciben datos y devuelven resultados. Así se prueban
con propiedades y se reutilizan en el servicio, la CLI y `restore-drill`.

## 2. Flujos

### 2.1 Append

```text
POST /v1/entries (token de servicio)
  -> U0: authn, scope, validación del payload (BR-U0-95: sin identificadores)
  -> ¿entry_type permitido para el scope? no -> 403 (BR-U3-03)
  -> ¿canonical > 64 KiB? -> 413 (BR-U3-07)
  -> BEGIN; pg_advisory_xact_lock
       ¿idempotency_key existe? sí: ¿mismo contenido? -> ack original : 409 (BR-U3-06)
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

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U3-01 | `append` + `verify` | **Stateful (PBT-06, US-401)**: para toda secuencia de comandos (append válido, reintento idempotente con la misma llave, reintento con la misma llave y otro contenido, checkpoint), la cadena resultante siempre verifica `integra`, `seq` es contiguo, los reintentos iguales no agregan filas y los distintos dan 409 | Stateful (máquina de estados contra un modelo en memoria) | Secuencias de comandos con payloads de los 9 tipos de negocio generados por las estrategias de U0 |
| PBT-U3-02 | `verify` | Para toda cadena válida y **una** manipulación (cambiar un byte de `canonical`, de `hash` o de una columna, borrar una fila, intercambiar dos filas), el verificador da `inconsistente` y el primer `seq` informado es el de la manipulación (o el siguiente, si se borró una fila) | Invariante + oráculo | Cadenas de 1 a 500 entradas y una manipulación aleatoria |
| PBT-U3-03 | `verify` | Para toda cadena válida reescrita por completo desde un `seq` k **anterior** a un checkpoint (con los hashes recalculados), el verificador da `inconsistente` con motivo `checkpoint_mismatch` o `checkpoint_signature` | Invariante | Cadenas con checkpoints y k aleatorio |
| PBT-U3-04 | `chain` | `canonicalize(decode(canonical)) == canonical` para toda entrada (los bytes guardados son un punto fijo de JCS) | Round-trip / idempotencia | Entradas de todos los tipos, con Unicode y decimales |
| PBT-U3-05 | `chain` | La verificación de una cadena escrita con `contract_version` X da el mismo resultado aunque el código del verificador tenga el contrato X+1 (no se vuelve a serializar) | Invariante | Cadenas generadas con un contrato y verificadas con otro que agrega un campo opcional |
| PBT-U3-06 | `projections` | Para toda entrada y todo consumidor, la proyección contiene **solo** los campos permitidos de su fila en domain-entities §3, y `feature_vector`, `justification` y `actor_id` nunca aparecen fuera de `full` | Invariante | Entradas de todos los tipos × los 4 consumidores |
| PBT-U3-07 | `append` | `recorded_at` es no decreciente en `seq` para todo reloj generado (incluso si retrocede) | Invariante | Secuencias de relojes con saltos hacia atrás |
| PBT-U3-08 | `append` | `occurred_at` se acepta ⇔ `|occurred_at − now| ≤ 300 s` | Oráculo | Desfases alrededor de ±300 s |

**Pruebas de ejemplo obligatorias (PBT-10):**
- `UPDATE`, `DELETE` y `TRUNCATE` con `registry_app` → `permission denied` (US-401);
- con el trigger habilitado, un `UPDATE` de superusuario → excepción;
- superusuario que deshabilita el trigger, edita y recalcula → el verificador lo detecta por checkpoint (US-402);
- expediente de un caso decidido: narrativa byte a byte igual a la guardada; solo `cro` y `cumplimiento` (US-403);
- los 5 tipos de evento de gobierno, con actor y rol (US-404);
- CLI: `exit 0` en una cadena íntegra, `1` en una alterada, `2` con la base caída;
- un append sin réplica síncrona → 503.

## 4. Cumplimiento de extensiones (Functional Design U3)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | Alertas con severidad de `business-rules.md` §6 (`RegistryChainBroken` SEV1, `CheckpointMissing`, `CheckpointExportFailed`, `RegistryVerificationFailed`, `RegistryEntryLarge`), dentro del proceso de U1 (P-U1-10) |
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
