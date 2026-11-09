# Ronda 1 — U03-T03

VEREDICTO: NO-VERDE

Hay dos ROJO. Los seis CA pasan con mis propias corridas, pero en BR-U3-03 una prueba no prueba lo que dice (la mutación sobrevive) y BR-U3-13 no se cumple en un caso que demostré con una sonda. El worktree quedó limpio (`git status` vacío, HEAD `0d3f94d`) y mis contenedores los recogió el reaper.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí (desde `vectra-risk/` del worktree) | Resultado |
|---|---|---|
| 1 | `HYPOTHESIS_PROFILE=ci uv run pytest …test_append_*.py …test_append.py -v` | pasa: `100 passed in 447.08s`, 0 omitidas. La 07 tarda 133 s, la 08 134 s y la 01 stateful 89 s, así que no se saltaron |
| 2 | `uv run pytest test_dossier.py test_queries.py test_integrity_api.py -v` | pasa: `87 passed in 91.29s` |
| 3 | `uv run pytest test_health.py -v && make -C contracts openapi && git diff --exit-code contracts/openapi/` | pasa: `8 passed in 25.04s`, el diff sale vacío |
| 4 | `uv run python platform/tests/test_traceability.py --unit decision-registry --section api`, más el grep de BR-U3-01..07 y 13..16 | pasa: exit 0, «41 identificadores». Las 11 BR aparecen en `tests/` |
| 5 | `HYPOTHESIS_PROFILE=ci uv run pytest test_verify.py test_projections.py -v` | pasa: `13 passed in 238.93s` |
| 6 | `make -C decision-registry check && make -C contracts check && make -C platform check` | pasa: U3 exit 0 (ruff, mypy, `2 kept, 0 broken`, `410 passed in 987.94s`); U0 exit 0 (`502 passed`); U1 exit 0 |

## Mutaciones, mías, sobre una copia hecha con `git archive`
Corrí 20 mutaciones más 2 de la candidata 2 con 5 semillas cada una. Usé el venv del worktree con `PYTHONPATH` apuntando a la copia.
- **Mueren:** R01 (`occurred_at` en la llave), R02 (ventana antes de la búsqueda), R03 (sin `check_business`), R04 (case acepta un fail_closed sin `escalated_at`), R06 (sin `remote_apply`), R07 (reintento sin barrera WAL), R08 (WARNING ignorado), R09 (sin `cancel_safe`), R10 (sin actor de gobierno), R11 (daily que no suma), R12 (202 con una activa), R14, R16 (paginación), R15 (explanation sin `case_id`), R17 (readiness solo `sync`), R18 (referencia de 60 días).
- **Candidata 1:** R19 (sin `actor_role`) y R20 (sin `policy_version_id`) mueren.
- **Candidata 2:** quitar `context_package` del freeze y quitar `received_at` de metrics fallan con las semillas 1 a 5.
- **Sobreviven:** R05/R21 (ver F-01) y R13. R13 quita la búsqueda de una activa en `request_check`; sobrevive porque el índice único parcial y el `except UniqueViolation` dan el mismo 200, así que no es un defecto.
- No volví a correr M15 (F-05).

## Desviaciones declaradas
1. **`statement_timeout`.** La afirmación es correcta. Mi sonda: standby con el replay pausado, `statement_timeout = 300` y `remote_apply`. El `COMMIT` tardó **4,07 s**, que es lo que tardé en reanudar el standby, sin ningún aviso, así que el temporizador no cubre la espera síncrona. BR-U3-04 se mantiene:
   - Con el standby pausado, A da 503, una llave nueva B da 503 y el reintento de A da 503.
   - Al reanudar, A da 200 con `seq = 2` y B da 200 con `seq = 3`, con 4 filas en total.
   - El reintento espera al standby (R07 lo mata). No hay ack sin réplica ni duplicados.
2. **BR-U3-16 estricta.** Coincide con la lista cerrada de U3 y con U4:
   - BR-U4-01: el congelado lo hace solo `bias-monitoring-job`; los eventos del Job de validación salen de `model-validation-job`; el vencimiento lo marca el sistema.
   - BR-U4-17: `transicion_descartada` la escribe `governance-service`.
   - Los eventos derivados (`inactivado`, `historica`, `evaluacion_iniciada`) llevan el actor del usuario.
   - No encontré ningún evento legítimo de U4 que quede fuera.
3. **PBT-U3-01 con 50 ejemplos.** NFR-U3-51 pide los 500 del perfil `ci` solo para PBT-U3-02..08; para PBT-U3-01 exige una `RuleBasedStateMachine` contra Testcontainers, sin cifra. Ni el plan ni el diseño exigen 500, así que no hay hallazgo.
- **Pools.** `POOL_SIZES` da append 2/0,5 s, dossier 1/2 s, projections 1/2 s y health 1/1 s, igual que P-U3-04. Una conexión cancelada o a medias se descarta.

## Hallazgos
### F-01 · ROJO · `test_append.py:139-149`, BR-U3-03 simétrica · la condición `escalated_at` del lado scoring no está probada
`scope_permits` exige `local_cause is None and escalated_at is None`. La prueba de la viñeta «fail_closed con `escalated_at` desde scoring → 403» usa `escalated()`, que trae también `local_cause`, de modo que basta la condición de `local_cause` para rechazarla. U0 acepta un fail_closed con `cause` y `escalated_at` (lo comprobé con `FailClosedPayload.model_validate_json`; es el escalamiento por reintentos agotados). La mutación R21 (`payload.local_cause is None`, sin la parte de `escalated_at`) **sobrevive** contra `unit/test_append_rules.py` y todo `test_append.py -k 'br_u3_03 or fail_closed'`: `66 passed`. Con ella, un token scoring podría escribir un escalamiento, cosa que según BR-U0-38 solo hace case-service.
**Arreglo:** un caso con `{cause, retryable, attempt, escalated_at}` desde scoring → 403, en la prueba de integración y en la unitaria.

### F-02 · ROJO · `dossier.py:119` y `test_dossier.py:137`, BR-U3-13 · un expediente posterior a una `full` inconsistente sale `verified`
BR-U3-13 dice que todo expediente posterior muestra «integridad NO verificada» hasta que una `full` vuelva a dar `integra`. Mi sonda: un caso con la cadena íntegra y la última `full` terminada con `inconsistente`. Resultado: `integrity.status = "verified"` mientras `last_full_verification.result = "inconsistente"`, en la misma respuesta. La prueba `test_br_u3_13_…_todo_expediente_posterior_dice_not_verified` solo cubre un tramo que contiene la fila alterada (no hay checkpoints, así que el tramo va de 0 a la cabeza); no prueba lo que dice su nombre.
**Arreglo:** marcar `not_verified` si la última `full` dio `inconsistente`, tomando `first_inconsistent_seq` y `reason` de su `report`, y escribir la prueba con un tramo limpio.

### F-03 · NARANJA · `test_append.py:144`, viñeta del Paso 7 · `local_cause` sin `escalated_at` desde scoring da 422, no 403
El plan pide 403, pero U0 (BR-U0-38) rechaza ese payload con 422 antes del handler, así que el 403 no se puede alcanzar sin tocar U0. La prueba se llama `…_es_403` y comprueba 422, y la contradicción entre el plan y U0 no está en `CANDIDATAS.md`. La propiedad fail-closed se cumple, porque no se escribe nada. Hay que renombrar la prueba y registrar la contradicción; la enmienda del plan la hace el orquestador.

### F-04 · AMARILLO · `queries.py:226-243` · `daily:query` trae las filas diarias y suma en Python
La suma ocurre en el servicio y la respuesta va agregada, así que cumple BR-U3-17. Pero la prueba solo siembra 2 430 filas. Con 3 versiones, unas 594 celdas y hasta 180 días serían unas 300 000 filas por solicitud, y eso no está medido contra los 2 s del pool `projections`, que comparte con `explanation`. Un `GROUP BY` en SQL lo acotaría.

### F-05 · AMARILLO · higiene del bucle
- Siguen vivos los contenedores que dejó el codificador (`optimistic_lewin`, `naughty_varahamihira`, con más de 3 h), además de `brave_yalow`, de otra sesión.
- `run_mutations.py` del codificador escribe sobre el worktree, aunque restaura los archivos.

## Seguridad y alcance
- **Seguridad:** las rutas usan el `RouteContract` de U0: `dossiers` para cro/cumplimiento, `integrity-checks` para cro con `mfa=True`, `any_scopes` en `/v1/entries`. Las pruebas de analista → 403, cro sin MFA y token de servicio → 403 pasan dentro de CA-2. `projections.Forbidden` se traduce a 403 sin datos parciales.
- **Alcance:** `git diff 5dedc70..HEAD` no toca `reference-model/`, `identity-edge/`, `platform/` ni `contracts/`; no hay desborde. Las cuatro candidatas están atendidas y tachadas en `CANDIDATAS.md` (de F-05 no volví a correr la mutación).

## Tareas candidatas (defectos reales fuera de alcance)
- BR-U3-13 también cubre los resultados `inconsistente` de `incremental` y `nightly`, que no quedan en `integrity_checks`, así que la API no puede verlos. El diseño tiene que decidir dónde se guardan.
- `pools.py` no revisa las conexiones ociosas ni les pone vida máxima: tras una conmutación, el primer uso da un 503 y después se recupera.

```
VEREDICTO: NO-VERDE
ROJO|decision-registry/tests/integration/test_append.py:139|BR-U3-03: escalated_at desde scoring sin probar (R21 sobrevive)
ROJO|decision-registry/src/vectra_registry/dossier.py:119|BR-U3-13: expediente "verified" con la última full inconsistente
NARANJA|decision-registry/tests/integration/test_append.py:144|local_cause sin escalated_at da 422, el plan pide 403 y la prueba se llama _es_403
AMARILLO|decision-registry/src/vectra_registry/queries.py:226|daily:query trae todas las filas diarias y suma en Python, sin medir a volumen real
AMARILLO|bucle|contenedores del codificador vivos; su script de mutaciones escribe en el worktree
INFORME: revisiones/U03-T03/ronda-1.md
```
