# U04-T03 — Evidencia en dos fases, reconciliador, barridos y convergencia de `governance`

**Unidad:** U4 `governance`
**Historias que implementa:** US-203, US-205, US-206, US-208 y US-305, en su parte de servicio sin HTTP: las transiciones con evidencia y la propagación de `serving-config`.
**Depende de:** U04-T02 (PR 93), ya en `main`. Usa `model_fsm`, `policy` y `serving_config` de esa tarea.
**Rama:** `tarea/U04-T03`, creada desde `origin/main` (`c620c4f`).
**Requisito para despachar:** que el usuario apruebe Q-1 a Q-5 de `aidlc-docs/construction/plans/governance-bloque-d-precisiones.md`. Esta tarea está escrita con esas recomendaciones.

Primera mitad del Bloque D del plan de U4 (Pasos 8 y 9), según el reparto de Q-5. A eso se suma la migración `0004` de Q-1, Q-2 y Q-4, y la función de la llave de Q-3. Alcance de la enmienda (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §3, U4):
- Paso 8 **E\*F**: entran las dos fases, la excepción de `freeze`, el reconciliador (P-U4-02, puntos 1–4), el barrido en modo `validacion` y PBT-U4-07. PBT-U4-01 entra sin el invariante de `source_candidate_for` (P-5). Se difiere la rama `source_comparison` del barrido. `CompensationEventPending` entra como regla con `promtool` (P-3).
- Paso 9 **E**.

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 8 y 9 del plan (`aidlc-docs/construction/plans/governance-code-generation-plan.md`, Bloque D), con su texto y su aceptación, salvo lo que la enmienda difiere y se nombra abajo. Léelos allí. Además:

1. **Migración `0004`** (Q-1, Q-2 y Q-4 de las precisiones):
   - `guard_unfreeze` rechaza toda salida de `congelado` salvo a `activo` o `retirado` con la `frozen_resolution` confirmada de cumplimiento;
   - `investigation` solo pasa de `false` a `true` en una versión `congelado` que sigue `congelado`, con la resolución `investigar`; cualquier otro cambio se rechaza;
   - el trigger del `NOTIFY` lleva `WHEN (NEW.etag IS DISTINCT FROM OLD.etag)` y nunca notifica con payload vacío.

   Sin `downgrade`, como `0001`–`0003`.
2. **La llave (Q-3).** Una sola función, `uuid5(NAMESPACE_URL, f"urn:vectra:governance:{entity_type}:{entity_id}:{n}")`, que usan el servicio y las pruebas. `test_migrations.py` deja su fórmula propia y la importa.

Precisiones:

- **«Contra el servicio», sin HTTP.** Los endpoints son de U04-T04 (Pasos 10 y 11). Aquí el «servicio» es la capa de operaciones de `evidence.py`, `background.py` y `convergence.py`:
  - `register`, `start_validation`, `receive_report`, `approve`/`reject`, `mark_active`, `retire`, `freeze` y `frozen_resolution`;
  - las de política: proponer, aprobar y rechazar.

  Cada operación recibe un actor ya autenticado y llama a `model_fsm`/`policy` (U04-T02). U04-T04 envolverá estas operaciones en handlers. PBT-U4-01 y PBT-U4-07 corren contra esta capa y Testcontainers.
- **Las operaciones de US-306 quedan fuera** de esta tarea: fuentes, `start_source_comparison` y `source-counts`. Las decide Q-6 en U04-T04. La tabla `transitions` ya admite `entity_type = data_source`. Si PBT-U4-07 genera transiciones de fuente, que sean de las operaciones existentes en `policy`/`model_fsm`; si no hay ninguna, PBT-U4-07 cubre modelo y política, y la parte de fuente se registra como diferida con Q-6.
- **Errores de dominio.** Los `Forbidden`/`ConflictState` de `model_fsm` suben tal cual. La traducción a `vectra_common.errors` y a `ProblemReason` es de U04-T04. La excepción es `transition_pending`, que ya está en BR-U4-17: el `ConflictState` lleva `reason = "transition_pending"`, como literal estable o como `ProblemReason` si existe en U0.
- **El registro.** El append de U3 es `POST /v1/entries` (contrato en `vectra_contracts.routes`, servicio `decision-registry-service`; tipos en `vectra_contracts/models/registry.py`). Para las pruebas, escribe un **doble** que reproduzca la semántica de U3:
  - la misma llave con el mismo contenido devuelve el ack original;
  - la misma llave con otro contenido da 409 (BR-U3-06);
  - puede fallar o tardar al azar.

  Mira `decision-registry/src/vectra_registry/append.py` para copiar la semántica, no el código. El cliente real (`httpx`, con timeouts) va en `evidence.py`; el doble lo sustituye por inyección.
- **Payloads.** `model_event`, `policy_event`, el `freeze` con `frozen_at` y `transicion_descartada` usan los tipos de U0. El evento `freeze` lleva aquí el `FreezeContext` que recibe la operación, tal cual. Agregarle `data_sources` e `initial_disparity`, y la reducción por tamaño de BR-U4-15, es del Paso 10.
- **Jobs.** El barrido de validaciones vencidas consulta el Job para registrar el motivo (P-U4-02). Define la interfaz mínima de lectura en `k8s_jobs.py` y usa un doble en las pruebas. El cliente real de Kubernetes y el lanzador son de U04-T04.
- **Métricas y alertas.** Los gauges que necesitan las reglas (pendientes de `freeze`, de compensación, abandonadas y `vectra_serving_config_age_seconds`) se exponen con `vectra_common.metrics`. La regla `CompensationEventPending` va en `governance/observability/` con su prueba `promtool test rules` (P-3). Las demás alertas de P-U4-08 y sus runbooks siguen diferidos (Paso 17, T2).
- **Convergencia (Paso 9).**
  - Dos réplicas son dos instancias del servicio en el mismo proceso de prueba contra el mismo PostgreSQL de Testcontainers.
  - «Cortar la conexión `LISTEN`» se hace con `pg_terminate_backend` sobre esa conexión.
  - «Pausar la base» es `docker pause` del contenedor desde la prueba, o lo que Testcontainers ofrezca. Si el entorno no lo permite, dilo en la bitácora; no lo simules con un doble.
- **Pools (P-U4-04).** `tx` 2, `read` 1, `background` 1 y `listen` 1: 5 por réplica, leídos con `pg_stat_activity` por `application_name`.
- **Plan.** Marca `[x]` los Pasos 8 y 9 con `(U04-T03, acotado a la demo)` en el 8 y `(U04-T03)` en el 9.

**Fuera:**

- Endpoints, handlers, `RouteContract`, OpenAPI, autenticación y step-up (Paso 10). Tampoco el resumen `api-summary.md` (Paso 11).
- US-306 entera (Q-6), la rama `source_comparison` del barrido y el invariante de `source_candidate_for` en PBT-U4-01 (P-5).
- `promotion-tool`, `validation_job` y el lanzador real de Jobs (Pasos 10, 12 y 13).
- Las alertas distintas de `CompensationEventPending`, los runbooks y el chart (Pasos 16 y 17).
- Cambios a U0, U1 o U3. Si algo falta allí (por ejemplo, un `ProblemReason`), detente y repórtalo.

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md` (§1 y Pasos 8–9)
- `aidlc-docs/construction/plans/governance-bloque-d-precisiones.md` (Q-1 a Q-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U4 y §6: P-3, P-5)
- `aidlc-docs/construction/governance/functional-design/business-rules.md` (§1, §3, §5, §7 y §8: BR-U4-01, 02, 05, 08, 11, 14, 15 y 17)
- `aidlc-docs/construction/governance/functional-design/business-logic-model.md` (§2 y §3: PBT-U4-01 y 07)
- `aidlc-docs/construction/governance/functional-design/domain-entities.md` (§1.3, §2.1 y §5)
- `aidlc-docs/construction/governance/nfr-requirements/nfr-requirements.md` (NFR-U4-04, 05, 06, 10 y 40)
- `aidlc-docs/construction/governance/nfr-design/nfr-design-patterns.md` (P-U4-01, 02, 04, 05 y 08)
- `governance/src/vectra_governance/` (U04-T02), `governance/migrations/` y `governance/tests/integration/governance_pg.py` (U04-T01)
- `contracts/python/vectra_contracts/src/vectra_contracts/models/registry.py`, `routes/__init__.py`, `catalog.py` y `contracts/python/vectra_common/src/vectra_common/metrics.py`
- `decision-registry/src/vectra_registry/append.py` (la semántica del append) y `decision-registry/tests/` (como ejemplo de PBT stateful con Testcontainers)
- `CANDIDATAS.md` (F-03, F-04 y F-05 de U04-T01; candidatas de U04-T02)

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1** — Migración `0004` (Q-1, Q-2 y Q-4).
  ```bash
  uv run pytest governance/tests/integration/test_migrations.py -v
  ```
  Esperado: siguen pasando los 40 casos de U04-T01, más los casos nuevos:
  - `congelado → inactivo` con el rol de la aplicación → excepción, con y sin variable;
  - `congelado → aprobado` → excepción;
  - `investigation` de `true` a `false` → excepción;
  - `investigation` cambiada en una versión `activo` → excepción;
  - el camino legítimo de `investigar` pasa;
  - un `UPDATE` de `serving_config` que no cambia el `etag` no notifica, y nunca llega un payload vacío.

  Lectura de vuelta con SQL real: el `state` y el `investigation` leídos después del intento, y `LISTEN` desde otra conexión.

- [ ] **CA-2** — Paso 8, con la aceptación del plan salvo la rama `source_comparison`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_stateful_*.py governance/tests/integration/test_evidence.py -v
  ```
  Esperado: todo pasa, con 2 réplicas y el doble del registro fallando al azar. La salida muestra un caso por cada viñeta de la aceptación del Paso 8:
  - ninguna transición distinta de `freeze` cambia el estado sin ack;
  - ningún evento se duplica;
  - abandono más transición nueva con la abandonada ya escrita → un solo evento y el estado de la abandonada;
  - `frozen_resolution` con el `freeze` pendiente → `ConflictState` `transition_pending`;
  - `freeze` con un `mark_active` pendiente → la versión queda `congelado`, el par queda `descartada` sin aplicar aunque llegue el ack, la destino no pasa a `activo`, y la cadena del doble tiene `freeze` y después los `transicion_descartada`;
  - una compensación pendiente más de 24 h no pasa a `abandonada`, sigue bloqueando la `frozen_resolution` y sube el gauge de `CompensationEventPending`;
  - un `ValidationRun` `validacion` vencido → la versión a `validacion_fallida`, con el motivo leído del doble del Job.

  PBT-U4-01 (stateful, todas las invariantes de business-logic-model §3 salvo `source_candidate_for`) y PBT-U4-07 (stateful) corren con el perfil `ci`. La lectura de vuelta es con SQL sobre `transitions` y `model_versions`, y sobre la cadena del doble, no con valores de retorno.

- [ ] **CA-3** — Regla `CompensationEventPending` (P-3).
  ```bash
  promtool check rules governance/observability/*.yaml && promtool test rules governance/observability/tests/*.yaml
  ```
  Esperado: `SUCCESS` en los dos. Si `promtool` no está en el PATH, usa `platform/.tools/bin/promtool`. Si no existe en el worktree, dilo en la bitácora y corre la parte de pytest que lea la regla; el CI corre `check-tools`.

- [ ] **CA-4** — Paso 9.
  ```bash
  uv run pytest governance/tests/integration/test_convergence.py governance/tests/integration/test_pools.py -v
  ```
  Esperado: todo pasa:
  - `freeze` en A → B sirve el `etag` nuevo en ≤ 1 s, también con la conexión `LISTEN` de B terminada;
  - con la base pausada, la última copia se sirve durante 29 s y a los 30 s responde 503 (o el error que la capa de servicio defina para eso); el gauge de edad crece y vuelve a 0 al reanudar;
  - `If-None-Match` con el `etag` vigente → «sin cambios» (304 en U04-T04);
  - una réplica recién arrancada no está lista hasta cargar la copia;
  - la copia cambia al pasar las 00:00 de Bogotá, con reloj simulado;
  - `pg_stat_activity` cuenta 5 conexiones por réplica.

- [ ] **CA-5** — Una sola fórmula de la llave (Q-3).
  ```bash
  git grep -nE 'uuid5\(' -- governance/ | grep -v 'urn:vectra:governance' ; git grep -c 'urn:vectra:governance' -- governance/src
  ```
  Esperado: el primer comando no imprime nada, salvo la definición única si la prueba de la línea la importa. El segundo da `1` en un solo archivo de `src`.

- [ ] **CA-6** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C governance check
  make -C platform check
  ```
  Esperado: código 0 en los dos. Si `make -C platform check` falla en `check-tools` porque `platform/.tools` no existe en el worktree, o por un 504, regístralo y corre `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib`. El CI del PR corre el resto.

## Plan de pruebas

- `governance/tests/integration/test_migrations.py`: los casos nuevos de `0004`.
- `governance/tests/property/test_stateful_model.py` (PBT-U4-01) y `test_stateful_evidence.py` (PBT-U4-07): `RuleBasedStateMachine` contra la capa de servicio, Testcontainers y el doble del registro.
- `governance/tests/integration/test_evidence.py`: un caso por viñeta de la aceptación del Paso 8.
- `governance/tests/integration/test_convergence.py` y `test_pools.py`: las viñetas del Paso 9.
- `governance/observability/tests/`: la prueba de `promtool` de `CompensationEventPending`.
- **Rojo primero**, registrado en `bitacoras/U04-T03.md`:
  - el trigger viejo deja pasar `congelado → inactivo`;
  - sin la revalidación de la transacción 2, PBT-U4-07 encuentra un estado aplicado sin ack o una `descartada` aplicada;
  - sin el sondeo de 1 s, la convergencia con `LISTEN` cortado falla;
  - con un pool de más, `pg_stat_activity` da 6.

## Notas

- Archivos que se modifican en su sitio:
  - `governance/src/vectra_governance/{evidence,background,convergence,pools,k8s_jobs}.py`;
  - `governance/tests/integration/test_migrations.py`;
  - `governance/Makefile`, si `check` necesita la prueba de reglas;
  - el plan (casillas).

  Nada de duplicados con sufijo.
- Docker está disponible para Testcontainers. `docker run -p` desde la terminal puede estar negado a los agentes, pero Testcontainers funcionó en U04-T01 y U04-T02.
- Las PBT stateful con Testcontainers son lentas. Ajusta `max_examples` y `stateful_step_count` con el perfil `ci` de U0 sin bajar las invariantes, y registra los tiempos.
- Si Q-1 a Q-5 se aprueban con cambios, el orquestador corrige esta tarea antes de despacharla.
