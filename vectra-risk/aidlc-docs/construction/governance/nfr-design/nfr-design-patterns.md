# Patrones de NFR Design — U4 `governance`

Decisiones del plan (`governance-nfr-design-plan.md`, Q1–Q5 = A). Los IDs `P-U4-xx` se
referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind las
ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las de integración usan
Testcontainers en CI.

---

## 1. Resiliencia

### P-U4-01 — Convergencia de `serving-config` entre réplicas (Q1; NFR-U4-04..06)
- La transacción que confirma una transición termina con `NOTIFY serving_config, '<etag>'`.
- Cada réplica:
  - mantiene una conexión `LISTEN serving_config` y, al recibir la notificación, recalcula su copia en memoria;
  - **además** consulta `SELECT etag FROM serving_config` cada **1 s** y recalcula si cambió, lo que cubre las notificaciones perdidas por una conexión caída;
  - al arrancar, carga la copia **antes** de que la readiness pase a 200.
- Si la conexión `LISTEN` se cae, se reconecta con backoff; mientras tanto, el sondeo mantiene el límite de 1 s.
- **Límite resultante**: congelamiento con efecto en ≤ 6 s (BR-U4-14, NFR-U4-06).
- **Verificación**: Testcontainers con 2 réplicas: `freeze` en A → B sirve el `etag` nuevo en ≤ 1 s; repetir con la conexión `LISTEN` de B cortada → sigue en ≤ 1 s por el sondeo; una réplica recién arrancada no responde 200 en `/readyz` hasta tener la copia.
- **Satisface**: NFR-U4-04, 05, 06; RESILIENCY-10.

### P-U4-02 — Reconciliador y barridos sin líder (Q2, Q3; BR-U4-05, 17)
Una tarea de fondo en cada réplica, cada 10 s:
1. toma hasta 20 transiciones `pendiente_registro` con `SELECT ... FOR UPDATE SKIP LOCKED` y reintenta el append con su `idempotency_key` (`transition_id`); con el ack, confirma y aplica (BR-U4-17);
2. las que llevan más de 24 h → `abandonada` + `GovernanceTransitionAbandoned` (SEV2);
3. los eventos `freeze` pendientes se reintentan igual; mientras existan, `FreezeEventPending` (SEV2).

Cada 60 s, la misma tarea:
- toma las `ValidationRun` con `deadline_at` vencido (`SKIP LOCKED`);
- consulta el Job (`get`, K01) para registrar el motivo (`failed`, `deadline`, `sin informe`);
- aplica `validacion_fallida`.

Dos réplicas nunca procesan la misma fila.

- **Verificación**: Testcontainers con 2 réplicas y un doble del registro que falla al azar: ninguna transición se aplica sin ack; ningún evento se duplica (PBT-U4-07); un Job vencido termina en `validacion_fallida` con su motivo.
- **Satisface**: BR-U4-05, 15, 17; RESILIENCY-10.

### P-U4-03 — Seguimiento de Jobs sin watch (Q3; K01)
- governance crea el Job con `ttlSecondsAfterFinished: 86400`, `activeDeadlineSeconds: 7200` y `backoffLimit: 0`, y espera el informe por F32. No mantiene watches abiertos.
- Los logs (`pods/log`) se leen solo cuando el ingeniero los pide desde la consola.
- El cliente de Kubernetes usa timeouts de 5 s por llamada (NFR-U4-25).
- **Verificación**: en kind (operador), lanzar una validación con el modelo de referencia → informe recibido; con un Job forzado a fallar → `validacion_fallida (failed)` en ≤ 60 s.
- **Satisface**: NFR-U4-12, 25; SECURITY-06.

### P-U4-04 — Conexiones por réplica (P-U1-08)

| Pool / conexión | Conexiones | Uso |
|---|---|---|
| `tx` | 2 | Transiciones y escrituras |
| `read` | 1 | Listados, informes, readiness |
| `background` | 1 | Reconciliador y barridos (P-U4-02), sondeo del `etag` (P-U4-01) |
| `listen` | 1 | `LISTEN serving_config` (P-U4-01) |

- Total: **5** por réplica, dentro de P-U1-08.
- `GET /v1/serving-config` no usa ningún pool: responde desde memoria.
- **Verificación**: prueba que cuenta las conexiones de una réplica en Testcontainers (`pg_stat_activity` por `application_name`) = 5.
- **Satisface**: RESILIENCY-10 (bulkhead); P-U1-08.

## 2. Lógica temporal

### P-U4-05 — Vigencias en `America/Bogota` (Q4; BR-U4-11)
- Fechas de vigencia (`effective_from`, `effective_to`) y «hoy» se interpretan en **`America/Bogota`**. Los timestamps del registro siguen en UTC.
- Cada réplica recalcula `normative_current` en cada transición **y** a las 00:00:00 de Bogotá (temporizador). El sondeo de P-U4-01 también recalcula, con la fecha de Bogotá, así que el cambio de día queda cubierto aunque falle el temporizador.
- Un cambio de `normative_current` cambia el `etag`.
- `NormativeParamsExpiring` usa la misma zona: SEV2 15 días antes, SEV1 el día del vencimiento.
- **Verificación**: PBT-U4-03 con fechas alrededor de la medianoche de Bogotá (05:00 UTC); prueba con reloj simulado: a las 23:59:59 y a las 00:00:00 de Bogotá, `normative_current` cambia exactamente al pasar la medianoche, no a las 19:00 de Bogotá (00:00 UTC).
- **Satisface**: BR-U4-11. Un tope vencido **nunca se usa**: al pasar la medianoche de Bogotá del fin de la vigencia, `normative_current` pasa a nulo, así que la tasa no se compara contra ningún tope. La solicitud **sí se evalúa**, pero la política de scoring fuerza `revision_requerida` con el motivo `parametro_normativo_no_vigente` (U7, BR-U7-04..06). No hay aprobación silenciosa ni fail-closed. Precisado el 2026-10-03: antes citaba AUTONOMIA-06 bajo el supuesto, revertido por U7 FD Q1, de que sin vigencia había fail-closed.

## 3. Seguridad

### P-U4-06 — Triggers como cuarta barrera (Q5; AUTONOMIA-04)

| Trigger | Rechaza | Salvo que |
|---|---|---|
| `guard_unfreeze` | `UPDATE model_versions` de `congelado` a `activo` o `retirado`, y cambios de `investigation` | La transacción haya fijado `SET LOCAL vectra.frozen_resolution = '<transition_id>'` **y** exista una `model_transitions` confirmada con ese id, acción `frozen_resolution` y actor con rol `cumplimiento` |
| `guard_freeze` | `UPDATE model_versions` a `congelado` | La transacción haya fijado `SET LOCAL vectra.freeze = '<transition_id>'` y exista la transición `freeze` con actor `bias-monitoring-service` |

- Solo los handlers de `frozen-resolution` y de `freeze`, después de autorizar, fijan esas variables.
- Las barreras quedan así: endpoint (rol, MFA, step-up) → `model_fsm` → **trigger** → script de CI (BR-U4-03).
- **Verificación**: Testcontainers: un `UPDATE` directo de `congelado` a `activo` con el rol de la aplicación → excepción; con la variable fijada pero sin transición confirmada de cumplimiento → excepción; por el handler legítimo → éxito.
- **Satisface**: AUTONOMIA-04; SECURITY-08, 11 (defensa en profundidad).

### P-U4-07 — Copia en memoria sin datos sensibles
`serving-config` solo contiene identificadores de versión, estado, parámetros normativos y
la edad del monitoreo. Servirla desde memoria no expone datos personales (no hay ninguno en
`governance-db`).
- **Verificación**: PBT-U4-05 y una prueba de que la respuesta de `serving-config` solo tiene los campos del tipo de U0.

## 4. Observabilidad

### P-U4-08 — Alertas de U4

| Alerta | Severidad | Origen |
|---|---|---|
| `ServingConfigUnavailable` | SEV1 | NFR-U4-07 |
| `ModeloCongelado` | SEV1 | BR-U4-15 |
| `NormativeParamsExpiring` | SEV2 / SEV1 | P-U4-05 |
| `MonitoreoSesgoDetenido` | SEV2 / SEV1 | BR-U4-16 |
| `PromotionMismatchPersistent` | SEV2 | BR-U4-08 |
| `FreezeEventPending` | SEV2 | P-U4-02 |
| `GovernanceTransitionAbandoned` | SEV2 | P-U4-02 |
| `ServingConfigConvergenceSlow` | SEV2 | Una réplica con un `etag` distinto al de la base durante más de 5 s (P-U4-01) |
| `ModelArchivePending` | SEV2 | Versión `activo` o `inactivo` sin `archived_uri` en 48 h (INF-U4-02) |
| `ValidationTimeout` | SEV3 | P-U4-02, 03 |

- Toda alerta tiene `runbook_url` (P-U1-10).
- **Verificación**: `promtool test rules governance/observability/rules/tests/*.yaml` y el test de runbooks de U1.

## 5. Cumplimiento de extensiones (NFR Design U4)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | P-U4-08 |
| RESILIENCY-06 | Cumple | P-U4-01 (lista solo con la copia cargada) |
| RESILIENCY-10 | Cumple | P-U4-01 (respaldo por sondeo), P-U4-02 (reintentos idempotentes), P-U4-03 (timeouts), P-U4-04 (bulkhead: pools separados por función, así que la tarea de fondo o los listados no le quitan conexiones a las transiciones, y `serving-config` no depende de ningún pool) |
| SECURITY-06 | Cumple | P-U4-03 (K01 sin watch, timeouts) |
| SECURITY-08 | Cumple | P-U4-06 |
| SECURITY-11 | Cumple | P-U4-06 (cuarta barrera: defensa en profundidad) |
| SECURITY-14 | Cumple | P-U4-08 |
| SECURITY-15 | Cumple | P-U4-02 (sin ack, sin efecto), P-U4-05 (sin normativa vigente, `normative_current` nulo y revisión humana obligatoria en U7) |
| AUTONOMIA-02 | Cumple | Cada patrón, de P-U4-01 a P-U4-08, tiene su «Verificación» |
| AUTONOMIA-04 | Cumple | P-U4-06; P-U4-01 (el congelamiento se propaga en ≤ 6 s) |
