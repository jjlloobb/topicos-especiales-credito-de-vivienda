# U8 `case-management`: resumen de `case-db` (Paso 18, U08-T04)

Resumen de la base tal como está en `main`. Nada de este archivo cambia una migración. Las migraciones están en `case-management/migrations/versions/` y no tienen `downgrade` (como U3 y U4). Las corre `case_migrator`, dueño de las tablas y de la base (U1: `case-db.owner`); cada proceso se conecta con su propio rol, sin `SET ROLE` y sin pooler (P-U1-08), porque `guard_transition` lee `session_user`.

| Revisión | Archivo | Qué crea |
|---|---|---|
| 0001 | `0001_case_schema.py` | Las ocho tablas, los índices únicos y los `CHECK`. |
| 0002 | `0002_grants_and_rls.py` | Los grants por rol y la política RLS de `evidence_outbox`. |
| 0003 | `0003_guards.py` | `case_transitions` y los triggers `guard_transition`, `guard_vencido` y `guard_ever_degraded`. |

`env.py` hace, después de las revisiones y en la misma conexión, el upsert de `retention_settings` con `RETENTION_DECIDED_YEARS`, `RETENTION_UNDECIDED_YEARS` y `RETENTION_INTAKE_KEYS_DAYS` (P-1 de U08-T01).

## Tablas

| Tabla | Clave y restricciones | Nota |
|---|---|---|
| `cases` | PK `case_id`; `state` ∈ los 7 estados; `attempts` y `escalation_count` con `CHECK` (`attempts BETWEEN 0 AND 6`) | `application` (jsonb) sin el grupo de identificación y con `sex` y estrato; `ever_degraded`, `last_cause`, `recommendation`, `recommendation_entry_id`, `model_frozen_after_recommendation`, `anonymized_at`. |
| `case_identifiers` | PK `case_id` → `cases` | Los 8 campos de identificación de U0 §1.1. Su eliminación (BR-U8-20) es un `DELETE` de una fila. |
| `intake_keys` | PK (`scope`, `idempotency_key`) | `body_sha256`; las limpia `case-retention` a los 30 días. |
| `evaluation_jobs` | índice único `evaluation_jobs_one_live_job_per_case` sobre `case_id`; `CHECK (attempt BETWEEN 0 AND 6)`; índice `evaluation_jobs_run_at` | Toda fila está viva: el worker la borra al pasar a `listo`, `modelo_congelado` o `no_disponible`; `case-retention`, al pasar a `vencido`. |
| `evidence_outbox` | PK `evidence_id`; índice único parcial `evidence_outbox_live_key` sobre `idempotency_key` donde `state <> 'abandonada'`; índice parcial `evidence_outbox_pending` | `entry_type` ∈ `human_decision`, `explanation_view`, `fail_closed`; `state` incluye `descartada`; `payload` es la entrada completa del registro. |
| `decisions` | PK `decision_id`; índice único parcial `decisions_live_case` sobre `case_id` donde `state IN ('pendiente_registro', 'confirmada')` | Una `abandonada` no impide decidir. |
| `explanation_views` | PK (`case_id`, `user_id`) | Una fila por analista y caso (BR-U8-19). |
| `retention_runs` | PK `run_id` | La escribe solo `case_retention` (Paso 16, diferido). |
| `retention_settings` | PK `id` con `CHECK (id = 1)` | Una fila: los plazos de retención. Solo la escribe `case_migrator`. |
| `case_transitions` | PK (`from_state`, `to_state`, `db_role`) | Las 16 filas de INF-U8-01. Ningún rol de la aplicación tiene permisos sobre ella: solo la lee `guard_transition`. |

## Grants por rol

| Rol (proceso) | Permisos |
|---|---|
| `case_app` (`case-service`) | `SELECT, INSERT` en `cases` y `UPDATE (state, attempts, model_frozen_after_recommendation, updated_at)`; `SELECT, INSERT, UPDATE` en `case_identifiers`, `decisions`, `explanation_views` y `evidence_outbox`; `SELECT, INSERT` en `evaluation_jobs` e `intake_keys`; `SELECT` en `retention_runs` y `retention_settings`. Sin `DELETE`. |
| `case_worker` (`case-worker`) | `SELECT` en `cases` y `case_identifiers`; `UPDATE (state, attempts, last_cause, recommendation, recommendation_entry_id, escalation_count, ever_degraded, updated_at)` en `cases`; `SELECT, UPDATE, DELETE` en `evaluation_jobs`; `INSERT` en `evidence_outbox` **sin** `SELECT`, de ahí el `INSERT` simple dentro de un `SAVEPOINT`, sin `RETURNING` ni `ON CONFLICT`. |
| `case_retention` (`case-retention`) | `SELECT` por columna en `cases`, `case_identifiers`, `evaluation_jobs`, `intake_keys` y `decisions`; `UPDATE (application, anonymized_at, state)` en `cases`; `DELETE` en `case_identifiers`, `evaluation_jobs` e `intake_keys`; `INSERT` en `retention_runs`; `SELECT` en `retention_settings`. |
| `case_migrator` | Dueño de las tablas y de la base. |

## RLS

`evidence_outbox` tiene RLS activa (sin `FORCE`: no aplica al dueño). La política `worker_fail_closed_only` (`FOR INSERT TO case_worker WITH CHECK (entry_type = 'fail_closed')`) deja al worker insertar solo escalamientos; `app_all` (`FOR ALL TO case_app`) deja todo a `case-service`.

## Triggers (migración 0003)

- `guard_transition` (`BEFORE INSERT OR UPDATE OF state`, `SECURITY DEFINER`, dueño `case_migrator`, `search_path` fijo). En `INSERT` exige `en_evaluacion`, sin recomendación y el rol `case_app`. En `UPDATE` con cambio de estado exige la fila (`OLD.state`, `NEW.state`, `session_user`) en `case_transitions`. La tabla `case_transitions` y `case_fsm.TRANSITIONS` se comparan en `tests/unit/test_case_fsm.py`; con P-1 (a) de U08-T04 el par `en_evaluacion` → `no_disponible` ya estaba en la base, así que la migración no cambia.
- `guard_vencido` (`SECURITY INVOKER`, `current_user`): solo `case_retention` escribe `vencido`, nunca desde `decidido` o `vencido`, y solo si `created_at + undecided_years` ya pasó (plazo de `retention_settings`); `case_retention` no escribe ningún otro estado.
- `guard_ever_degraded`: `ever_degraded` nunca vuelve de `true` a `false`, tampoco con el dueño.

`case_transitions` por rol: `case_worker` (los 8 pares entre `en_evaluacion`/`en_sincronizacion` y `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado`); `case_app` (`modelo_congelado` y `no_disponible` → `en_evaluacion`, `listo` → `decidido`); `case_retention` (los 5 estados no terminales → `vencido`).
