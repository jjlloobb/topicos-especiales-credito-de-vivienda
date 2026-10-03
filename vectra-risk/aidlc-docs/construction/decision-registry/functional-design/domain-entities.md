# Entidades de dominio — U3 `decision-registry`

Decisiones del plan (`decision-registry-functional-design-plan.md`, Q1–Q10 = A). Los tipos
de la API (`RegistryEntryIn`, `RegistryEntry`, `RegistryAck`, payloads) son de U0
(domain-entities §5) y no se redefinen aquí; esta unidad define cómo se **almacenan,
encadenan, anclan, proyectan y verifican**.

---

## 1. Tabla `registry_entries` (`registry-db`)

| Columna | Tipo | Notas |
|---|---|---|
| `seq` | `bigint` PK | Contiguo desde 0 (génesis); `seq = cabeza + 1` |
| `idempotency_key` | `uuid` `UNIQUE` | Del cliente (Q5); para `genesis` y `checkpoint` la genera el registro |
| `entry_type` | `text` | Catálogo de U0 §5.2, incluidos `genesis` y `checkpoint` |
| `case_id` | `uuid` nulo | Índice |
| `model_version_id`, `policy_version_id` | `text` nulos | Índices |
| `actor_kind`, `actor_id`, `actor_role` | `text` | `actor_id` = `sub` (usuario o servicio) o `system` |
| `occurred_at` | `timestamptz` | Del cliente, ±5 min (Q9) |
| `recorded_at` | `timestamptz` | De la base, no decreciente (Q9) |
| `correlation_id` | `text` | `trace-id` W3C (U0) |
| `contract_version` | `text` | Versión SemVer del contrato de U0 con que se escribió (Q2) |
| `canonical` | `bytea` | Bytes JCS exactos de la entrada (Q2, Q3); ≤ 64 KiB (Q10) |
| `prev_hash` | `bytea(32)` | Hash de `seq − 1`; 32 bytes en cero para la génesis |
| `hash` | `bytea(32)` | `SHA-256(prev_hash ‖ canonical)` (Q3) |

Las columnas fuera de `canonical` existen **solo para consultar**. La fuente de verdad es
`canonical`, y el verificador comprueba que las columnas coinciden con él (BR-U3-06).

### 1.1 Contenido de `canonical` (Q3)
Objeto JCS con: `seq`, `entry_type`, `idempotency_key`, `actor`, `occurred_at`,
`recorded_at`, `correlation_id`, `case_id?`, `model_version_id?`, `policy_version_id?`,
`contract_version` y `payload`.

### 1.2 Roles de base de datos

| Rol | Permisos | Usado por |
|---|---|---|
| `registry_app` | `INSERT`, `SELECT` sobre `registry_entries`; `SELECT` sobre la vista de cabeza; **sin** `UPDATE`, `DELETE` ni `TRUNCATE` | decision-registry-service (F42) |
| `registry_verifier` | Solo `SELECT` | CLI y CronJob de verificación, `restore-drill` |
| `registry_health` | `pg_monitor` (solo estadísticas; sin acceso a `registry_entries`) | Readiness del servicio: comprueba que haya un standby síncrono (agregado por U3 NFR Design Q1, P-U3-01) |
| `registry_migrator` | DDL | Job de migración (F44), solo en un sync aprobado |

Además, un trigger `BEFORE UPDATE OR DELETE OR TRUNCATE` lanza una excepción (BR-U3-02).

## 2. Checkpoints (Q1)

### 2.1 `Checkpoint` (payload de `entry_type = checkpoint`)

| Campo | Contenido |
|---|---|
| `checkpoint_seq` | `seq` de la última entrada cubierta |
| `checkpoint_hash` | `hash` de esa entrada (hex) |
| `signature` | Ed25519 sobre `JCS({checkpoint_seq, checkpoint_hash, recorded_at})` |
| `key_fingerprint` | SHA-256 de la llave pública |

- La entrada `checkpoint` también se encadena: queda en la cadena **y** se copia como objeto `checkpoints/{checkpoint_seq}.json` a un bucket con object lock (WORM).
- La firma la hace la bóveda (Vault Transit en kind; la bóveda o el HSM del banco en producción): la llave privada **nunca** sale de ella (U3 NFR Q5). `registry-db` y sus roles no tienen acceso a la bóveda ni al bucket.

### 2.2 Llave de checkpoints
- La huella de la llave pública activa está en la entrada `genesis`.
- Si se rota la llave, el registro escribe una entrada `checkpoint` con la llave nueva que lleva también la firma de la anterior sobre la huella nueva (*cross-signing*), y así la cadena de llaves se puede verificar desde la génesis.

## 3. Proyecciones de lectura (Q6)

| Proyección | Para | Entradas | Campos |
|---|---|---|---|
| `full` | `cro`, `cumplimiento` (BFF) | Todas | Todos, incluido `canonical` |
| `explanation` | explainability (`registry:read:explanation`) | Una `recommendation` por `seq`, filtrada por `case_id` (BR-U7-13) | `seq`, `case_id`, `model_version_id`, `payload.explanation` |
| `monitoring` | bias (`registry:read:monitoring`) | `recommendation`, `human_decision` | `recommendation`: `case_id`, `model_version_id`, `policy_version_id`, `score`, `confidence`, `outcome`, `reasons`, `monitoring_labels`, `recorded_at`, `seq`. `human_decision`: `case_id`, `decision`, `final_outcome`, `recommendation_entry_id`, `recorded_at` |
| `metrics` | product-metrics (`registry:read:metrics`) | `recommendation`, `human_decision`, `explanation_view` | `entry_type`, `case_id`, `outcome`, `decision`, `final_outcome`, `used_factors`, `explanation_viewed_before`, `actor_role`, `recorded_at`, `seq`, `recommendation_entry_id` |

- `analista` no tiene proyección: sus vistas vienen de case-service.
- `seq` y `recommendation_entry_id` se agregaron a `explanation`, `monitoring` y `metrics` para que el resumen al solicitante, U9 y U11 usen solo la recomendación entregada (P-U7-03) (precisado el 2026-10-03 por U7 NFR Design Q3).
- Ninguna proyección distinta de `full` incluye `feature_vector`, `justification`, `narrative` fuera de `explanation`, ni `actor_id`.

## 4. Expediente (Q7)

### 4.1 `RegistryDossier` (lo que devuelve el registro)

| Campo | Contenido |
|---|---|
| `case_id` | — |
| `entries` | Todas las entradas del caso en orden de `seq`, con `canonical` en base64 (la narrativa se reproduce byte a byte) y sus campos decodificados. Cada `recommendation` lleva `delivery_status` (`entregada` \| `no_entregada` \| `pendiente_de_decision`), calculado al leer y nunca guardado (BR-U3-14) (precisado el 2026-10-03 por U7 NFR Design Q3) |
| `integrity` | `IntegrityStatus` del tramo (§4.2) |
| `last_full_verification` | Resultado y fecha de la última verificación completa |

### 4.2 `IntegrityStatus`
`status` (`verified` \| `not_verified`), `from_checkpoint_seq`, `to_checkpoint_seq` (o
`head`), `entries_checked`, `first_inconsistent_seq?`, `reason?` (`hash` \| `link` \|
`checkpoint_signature` \| `checkpoint_mismatch` \| `seq_gap` \| `column_mismatch`).

### 4.3 `Dossier` del BFF
`RegistryDossier` más los identificadores directos del caso traídos de case-service, solo
para `cro` y `cumplimiento`. El registro **no** llama a case-service ni recibe
identificadores (sin flujo hacia datos de identificación).

## 5. Informe del verificador (Q8)

### `IntegrityReport`
`mode` (`incremental` \| `nightly` \| `full` \| `range`), `from_seq`, `to_seq`, `entries_checked`,
`checkpoints_checked`, `result` (`integra` \| `inconsistente` \| `error`),
`first_inconsistent_seq?`, `reason?`, `started_at`, `finished_at`.

| Código de salida de la CLI | Significado |
|---|---|
| `0` | `integra` |
| `1` | `inconsistente` (informa el primer `seq` y el motivo) |
| `2` | `error` de ejecución (no se pudo verificar) |

## 6. Parámetros

| Parámetro | Valor | Regla |
|---|---|---|
| Intervalo de checkpoint | 1 h (y al terminar cada verificación completa) | BR-U3-08 |
| Verificación incremental | Cada 15 min | BR-U3-11 |
| Verificación `nightly` | Cada noche | BR-U3-11 |
| Verificación `full` | Cada mes, bajo demanda y en `restore-drill` | BR-U3-11 |
| Margen de `occurred_at` | ±5 min | BR-U3-05 |
| Tamaño máximo de `canonical` | 64 KiB (alerta a 48 KiB) | BR-U3-07 |
