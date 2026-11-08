# Resumen de la lógica pura — U3 `decision-registry`

Bloque C del plan (Pasos 3 a 6). Los tres módulos son funciones puras: el contrato `pure-no-io` de import-linter
(`decision-registry/.importlinter`) les prohíbe base de datos, red, archivos, procesos y `asyncio`.

| Reglas | Archivo | Pruebas |
|---|---|---|
| BR-U3-09, 10 (bytes canónicos inmutables, génesis) | `src/vectra_registry/chain.py` (`canonicalize`, `link`, `decode`, `Row`, `format_timestamp`) | `tests/property/test_chain.py` (PBT-U3-04, 05), `tests/integration/test_migrations.py` (la génesis canonizada por la migración) |
| BR-U3-11, 12 (modos y qué verifica), NFR-U3-33 | `src/vectra_registry/verify.py` (`verify`, `RowSource`, `ListSource`, `sample_segments`, `nightly_seed`) | `tests/property/test_verify.py` (PBT-U3-02, 03), `tests/unit/test_verify_modes.py` (los 6 motivos y los 4 modos) |
| BR-U3-15 (proyecciones) | `src/vectra_registry/projections.py` (`project`, `project_all`, `project_monitoring_daily`, `Forbidden`) | `tests/property/test_projections.py` (PBT-U3-06) |

## Qué hace cada módulo

- **`chain`**. `canonicalize` es JCS (RFC 8785) de U0 más un formato fijo para los sellos de tiempo: ISO 8601 en UTC, con
  microsegundos y `Z` (`2026-11-08T10:00:00.000000Z`). La génesis de la migración `0001` escribe el mismo formato. `link` es
  `SHA-256(prev_hash ‖ canonical)`. `decode` solo lee los bytes guardados, sin contratos de U0: un campo opcional nuevo en un
  contrato más nuevo no cambia nada (PBT-U3-05). Nada del servicio ni del verificador vuelve a serializar una entrada guardada.
- **`verify`**. Recibe una `RowSource` (la CLI de los CronJobs, en el Bloque E, lee tramos de la réplica; las pruebas usan
  `ListSource`) y devuelve el `IntegrityReport` de U0. Detecta los 6 motivos de BR-U3-12 y informa el **menor** `seq`
  inconsistente. Modos: `full` (desde 0), `incremental` (desde la cubierta del último checkpoint verificado), `range` y
  `nightly` (cadena de checkpoints completa, re-hash de los últimos 7 días y de una muestra del 1 % de los segmentos más
  antiguos con semilla; `record_sample` recibe la semilla y los segmentos para registrarlos).
- **`projections`**. Las proyecciones de domain-entities §3: `full`, `explanation`, `metrics`, `monitoring_freezes` (de
  entradas) y `monitoring_daily` (suma de los conteos de las tablas derivadas). Una proyección o un campo no permitidos es
  `Forbidden` y no devuelve datos parciales.

## Decisiones del Bloque C (el diseño no las fija)

| Decisión | Razón |
|---|---|
| `IntegrityReport`, `IntegrityStatus`, `ExplanationProjection`, `MetricsProjection`, `FreezeProjection`, `FrozenResolutionProjection`, `MonitoringQuery` y `MonitoringWindow` salen de U0 (`vectra_contracts.models`); `Row`, `Forbidden`, `Consumer` y las filas de las tablas derivadas se definen en `decision-registry` | Los primeros existen en U0; los segundos son de la capa de datos de U3 |
| Un `checkpoint_mismatch` o `checkpoint_signature` se informa en el `seq` de la fila `checkpoint` | Es la fila cuya afirmación (o firma) no se sostiene; si se informara la fila cubierta, una manipulación del propio checkpoint saldría en un `seq` anterior al manipulado (contraejemplo que halló PBT-U3-02) |
| Un checkpoint que el bucket WORM tiene y la cadena no se informa en `checkpoint_seq + 1` | Detecta el truncado del final de la cadena, que ningún enlace delata |
| Una fila borrada se informa en el `seq` de la siguiente fila (la que ya no sigue a su anterior) | PBT-U3-02 |
| La firma del checkpoint es base64 de los 64 bytes de Ed25519 (se acepta el prefijo `vault:vN:` de Transit) sobre `JCS({checkpoint_seq, checkpoint_hash, recorded_at})`; las llaves públicas llegan crudas (32 bytes) y la huella es su SHA-256 en hex | domain-entities §2.1; el formato exacto lo fija el Paso 12 (`checkpoint.py`) |
| `nightly`: los «últimos 7 días» empiezan en la cubierta del último checkpoint con más de 7 días; los segmentos van de una cubierta a la siguiente | No hace falta una consulta por fecha; el tramo es un poco más largo que 7 días, nunca más corto |
| `delivery_status` sale en la proyección `metrics` de una `recommendation`, y la recomendación referenciada por una `human_decision` la resuelve el servicio y la pasa a `project` | BR-U3-14, domain-entities §3; lo calcula el Bloque D al leer |
| `unattributable_invalid` suma `invalid` de `monitoring_entry_totals` para `model_version_id = '-'` dentro del `unattributable_range`; `invalid_seqs` son los 100 menores de los días pedidos | U9 FD, domain-entities §3 (`monitoring_daily`); si el diseño pedía otra cosa, se corrige en el Paso 8 |
