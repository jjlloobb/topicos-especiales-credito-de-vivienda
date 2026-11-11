# U8 `case-management`: resumen de la lógica pura (Pasos 4 a 8, U08-T02)

Módulos sin E/S (contrato `pure-no-io` de import-linter): `vectra_case.case_fsm`, `backoff`, `decision` y `views`.

## `case_fsm` (BR-U8-12; US-107, US-112)

API: `transition(state: CaseState | None, event: CaseEvent) -> CaseState | Rechazo`. `None` como estado de partida es el alta. `Rechazo(state, event)` es un valor de retorno, no una excepción. `TRANSITIONS` es la tabla y `TERMINAL = {decidido, vencido}`.

| Evento (`CaseEvent`) | De | A |
|---|---|---|
| `ALTA` | — (`None`) | `en_evaluacion` |
| `RECOMMENDATION` | `en_evaluacion`, `en_sincronizacion` | `listo` |
| `RETRYABLE_FAILURE` | `en_evaluacion`, `en_sincronizacion` | `en_sincronizacion` (la segunda es una fila válida sin cambio de estado) |
| `ATTEMPT_6_FAILED` | `en_sincronizacion` | `no_disponible` |
| `SCORING_REJECTED` | `en_evaluacion`, `en_sincronizacion` | `no_disponible` |
| `MODEL_FROZEN` | `en_evaluacion`, `en_sincronizacion` | `modelo_congelado` |
| `SWEEP_ACTIVE` | `modelo_congelado` | `en_evaluacion` |
| `RETRY` | `no_disponible` | `en_evaluacion` |
| `DECISION_CONFIRMED` | `listo` | `decidido` |
| `RETENTION_EXPIRED` | `en_evaluacion`, `listo`, `en_sincronizacion`, `no_disponible`, `modelo_congelado` | `vencido` |

Son 18 pares (estado, evento) y 16 pares (de, a) distintos sin el alta. Cualquier otro par de los 8 × 10 (`None` + 7 estados, por 10 eventos) es `Rechazo`; las pruebas lo recorren completo. `decidido` y `vencido` no tienen salida; `listo` solo sale por `DECISION_CONFIRMED` y `RETENTION_EXPIRED`, nunca a `en_evaluacion`.

La prueba `test_fsm_table_equals_case_transitions_of_the_migration` carga por ruta `migrations/versions/0003_guards.py` y exige que los 16 pares (de, a) sean **iguales** a `CASE_TRANSITIONS` (sin el rol y sin la fila de creación). `evaluation`, `sweeps` y `evidence` usan esta API.

## `backoff` (BR-U8-07; US-112)

`schedule(attempt, rng: random.Random) -> float` (segundos) es la espera antes del intento `attempt + 1`: `30 · 2^(attempt−1)` con jitter uniforme de ±20 % tomado de `rng` (30 s, 1, 2, 4 y 8 min). Las constantes salen de `config`. **Fuera de 1..5 lanza `ValueError`**: tras el intento 6 no hay más intentos, el caso escala (BR-U8-09). Los valores 0, negativos, 6 y mayores están probados.

## `decision` (BR-U8-16; US-108, US-502)

API: `validate_decision(DecisionIn, Recommendation) -> Rechazo | None`; `None` es «aceptada». `Rechazo(code: ProblemCode, reason)`; el estado HTTP sale de `PROBLEM_STATUS`.

| Regla | Quién | Código |
|---|---|---|
| Justificación de 20 a 2000 caracteres tras recortar, obligatoria salvo en `sigue` (BR-U0-36); máximo 2000 sin recortar | U0: validador de `DecisionIn` (`check_justification`) | 422 antes de llegar |
| Forma de `used_factors`: `["ninguno"]` solo, 1 a 20, sin repetidos | U0: `DecisionIn` (`check_used_factors`) | 422 antes de llegar |
| `used_factors` ⊆ `feature_id` del `shap_vector`, o exactamente `["ninguno"]` | U8 | `validation_error` (422) |
| BR-U0-35 contra `recommendation.outcome` | U0: `decision_is_coherent`; U8 la llama | `conflict_state` (409) |

Elección: si hay ambas violaciones gana la 422 (los datos de la petición se rechazan antes que el estado del caso). PBT-U8-03 usa un oráculo por tabla de verdad (18 combinaciones de BR-U0-35 escritas a mano) sobre la cadena `DecisionIn.model_validate_json` + `validate_decision`.

## `views` (BR-U8-13, 13b, 21; US-107)

Entrada: `CaseRow` (la fila de `cases` y lo ya leído: identificadores, decisión confirmada, `credit_status`, fecha de entrada a `no_disponible`). Salida: `case_summary`, `case_detail`, `persistent_failure`.

- `score`, `outcome`, `recommendation`, `recommendation_entry_id` y explicación: solo en `listo` y `decidido`; `None` en los otros cinco.
- `attempts`: siempre. **`last_cause`: solo en `en_sincronizacion` y `no_disponible`** (elección; `None` en los demás).
- `decision` y `credit_status`: solo en `decidido` (BR-U8-21), `None` en los demás aunque la fila los traiga (elección).
- `applicant_display` = `full_name` + últimos 4 dígitos de `document_number`; vacío si el caso está anonimizado o no hay identificadores. Única identificación de la bandeja.
- `application`: se quitan explícitamente `sex` y `socioeconomic_stratum` y se valida como `ApplicationView` con las reglas JSON.
- `identifiers`: `None` si el caso está anonimizado, aunque la fila los traiga.
- `persistent_failure`: exige `no_disponible` y `no_disponible_since` (`ValueError` si no); `since` es ese dato, `last_cause` es `""` si falta.
- **~~Rodeo temporal (F-01 de la ronda 1; hasta una tarea de U0)~~ CERRADO por U00-T03:** `case_detail` ya no usa el token: anida la instancia de `CaseRow.recommendation`, `.importlinter` prohíbe `outcome._internal` a todo `vectra_case` sin excepciones y `outcome` ya no reexporta el token. Texto histórico: `CaseDetail.recommendation` exige el token privado de `vectra_contracts.outcome` incluso con una instancia válida. `case_detail` lo importa dentro de la función y lo usa solo como contexto de esa validación: ningún nombre del módulo lo contiene (lo prueba `tests/unit/test_private_token.py`). `.importlinter` (contrato `private-token`) prohíbe `vectra_contracts.outcome._internal` a todo `vectra_case` con una única excepción, `vectra_case.views`. Una tarea de U0 publicará una vía pública de lectura de `CaseDetail`; entonces se retiran el import, la excepción y esas pruebas.

## Cobertura (NFR-U8-50, 52)

`uv run pytest case-management/tests/unit case-management/tests/property --cov=vectra_case.case_fsm --cov=vectra_case.backoff --cov=vectra_case.decision --cov=vectra_case.views --cov-branch --cov-fail-under=100`: 100 % de ramas en los cuatro módulos (109 sentencias, 14 ramas, 0 sin cubrir). Perfil `ci` de Hypothesis: 500 ejemplos, semilla impresa.

## `mutmut`

`mutmut` diferido por la demo (T3): NFR-U8-51 queda fuera de esta entrega (enmienda `demo-recorte-funcional.md` §3 U8 fila «8 Resumen» y §2 regla 3).
