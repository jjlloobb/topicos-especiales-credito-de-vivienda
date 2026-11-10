# U08-T02 — Lógica pura de `case-management`: `case_fsm`, `backoff`, `decision` y `views`

**Unidad:** U8 `case-management`
**Historias que implementa:**
- US-107: estados y vistas (Pasos 4 y 7);
- US-108: contenido de la decisión (Paso 6);
- US-112: transiciones y backoff (Pasos 4 y 5);
- US-502: `se_aparta` y `sigue` (Paso 6).

**Depende de:**
- U08-T01 en `main`: el esqueleto, los contratos de import-linter y la constante `CASE_TRANSITIONS` de la migración;
- U0 en `main`: `CaseState`, `DecisionIn`, `CaseSummary`, `CaseDetail`, `PersistentFailure`, `CaseIdentifiers`, `ApplicationView`, `Recommendation`, y en `vectra_contracts.validation` las funciones `decision_is_coherent`, `check_used_factors` y `check_justification`.

Es lógica pura y pruebas sin clúster (RL-5).
**Se despacha** cuando U08-T01 esté fusionado en `main`.
**Rama:** `tarea/U08-T02`, desde `origin/main`.

Bloque C del plan de U8 (`aidlc-docs/construction/plans/case-management-code-generation-plan.md`, Pasos 4 a 8). Es la tarea «C» de `demo-recorte-funcional.md` §4 y §8. Los Pasos 4 a 7 entran **completos** (E): la enmienda dice «1–7 · E · E · Completos (`retry` y `vencido` en `case_fsm` por PBT-U8-01)» (§3, U8). El Paso 8 entra como **E\*F**: sin `mutmut` (§3, U8, fila «8 Resumen»; §2 regla 3). Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

---

## Alcance

**Dentro:** los Pasos 4 a 8 del plan. Es el texto del plan, sin recortes salvo el `mutmut` del Paso 8, que se marca abajo y va en «Fuera»:

### Bloque C — Lógica pura

- [ ] **Paso 4 — `case_fsm`**
  - `transition(state, event) -> state | Rechazo` con la tabla de BR-U8-12 (la misma que `case_transitions`, sin el rol).
  - `decidido` y `vencido` terminales; `listo` nunca vuelve a evaluarse.
  - Diseño: BR-U8-12. Historias: US-107, US-112.
  - **Aceptación**: `uv run pytest case-management/tests/unit/test_case_fsm.py`: cada fila de BR-U8-12 aceptada, cada par fuera de la tabla rechazado, y una prueba que compara la tabla de `case_fsm` con las filas de `case_transitions` de la migración (sin el rol).

- [ ] **Paso 5 — `backoff`**
  - `schedule(attempt, rng) -> delay`: `30 s · 2^(n−1)` con jitter de ±20 %, máximo 6 intentos.
  - Diseño: BR-U8-07. Historia: US-112.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_backoff.py`: PBT-U8-02.

- [ ] **Paso 6 — `decision`**
  - `validate_decision(DecisionIn, recommendation)`: BR-U0-35 contra `recommendation.outcome`, `used_factors` subconjunto de los `feature_id` del `shap_vector` o exactamente `["ninguno"]`, reglas de `se_aparta`, `sigue` y `resuelve_revision`, justificación de 20 a 2000 caracteres tras recortar los bordes (BR-U0-36).
  - Diseño: BR-U8-16. Historias: US-108, US-502.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_decision.py tests/unit/test_decision_examples.py`:
    - PBT-U8-03;
    - `se_aparta` sin factores ni `ninguno` → 422; `sigue` con `["ninguno"]` → aceptada (US-502).

- [ ] **Paso 7 — `views`**
  - Proyección a `CaseSummary`, `CaseDetail` y `PersistentFailure`:
    - sin `score`, `outcome`, `recommendation` ni `explanation` fuera de `listo` y `decidido`; `attempts` y `last_cause` en `en_sincronizacion` y `no_disponible`;
    - `applicant_display` (nombre + los últimos 4 dígitos del documento) como única identificación en la bandeja;
    - `CaseDetail` con `application` sin `sex` ni `socioeconomic_stratum` e `identifiers?` ausente si el caso está anonimizado;
    - `credit_status` en `CaseDetail` (BR-U8-21).
  - Diseño: BR-U8-13, 13b. Historia: US-107.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_views.py`: PBT-U8-04.

- [ ] **Paso 8 — Resumen de la lógica pura** (E\*F)
  - Cobertura de ramas **100 %** en `case_fsm`, `backoff`, `decision` y `views`.
  - ~~`mutmut` en `case_fsm`, `validate_decision`, `views` y `backoff`, con 0 sobrevivientes sin justificar~~ **(diferido por la demo, T3; ver «Fuera»)**.
  - Resumen en `aidlc-docs/construction/case-management/code/logic.md`.
  - Diseño: NFR-U8-50, ~~51~~ (diferido con `mutmut`), 52.
  - **Aceptación**: `uv run pytest case-management/tests/unit case-management/tests/property --cov=vectra_case.case_fsm --cov=vectra_case.backoff --cov=vectra_case.decision --cov=vectra_case.views --cov-branch --cov-fail-under=100`; ~~`uv run mutmut run --paths-to-mutate …`~~ (diferido, T3).

### Precisiones

- **Rutas de la aceptación.** El plan escribe `tests/unit/test_decision_examples.py` relativo a `case-management/`. Los comandos de los CA usan la ruta completa desde `vectra-risk/`.
- **`case_fsm` (Paso 4).**
  - La tabla es la de BR-U8-12: 10 filas de eventos. Los eventos tienen nombre propio, en el código y en las pruebas:
    - alta (ingesta o alta manual);
    - `Recommendation`;
    - fallo reintentable o scoring sin respuesta con intentos restantes;
    - fallo del intento 6;
    - `scoring_rejected`;
    - `FailClosed(model_frozen)`;
    - barrido con `serving-config` activo;
    - `retry` del CRO;
    - decisión confirmada;
    - retención vencida sin decisión.
  - Entran `retry` y `vencido`, por PBT-U8-01 (enmienda §3).
  - `Rechazo` es un valor de retorno, no una excepción, como dice la firma del plan.
  - Una transición que no cambia de estado (`en_sincronizacion` → `en_sincronizacion`, por un fallo reintentable) es una fila válida.
- **Comparación con `case_transitions`.**
  - `case_fsm` no puede importar la migración (contrato de U08-T01). La prueba sí puede: carga por ruta la revisión de Alembic que declara `CASE_TRANSITIONS` (constante de U08-T01) y compara los conjuntos de pares `(from_state, to_state)` de las dos tablas.
  - Excluye la fila de creación (— → `en_evaluacion`), que en la base cubre la rama `INSERT` de `guard_transition`.
  - Las dos tablas tienen 16 pares, y deben ser **iguales** como conjuntos, no solo una incluida en la otra.
  - **Rojo primero:** quitar `en_evaluacion` → `no_disponible` (`scoring_rejected`) de `case_fsm` hace fallar la comparación.
- **«Cada par fuera de la tabla rechazado».** El universo son los 7 × 7 pares de `CaseState` × cada evento. La prueba es parametrizada o exhaustiva, no por muestra.
- **`backoff` (Paso 5; PBT-U8-02).**
  - `schedule(attempt, rng)` da el retraso antes del intento `attempt + 1`, para `attempt` de 1 a 5: 30 s, 1, 2, 4 y 8 min, con un jitter uniforme de ±20 % tomado de `rng`.
  - El plan no dice qué pasa fuera de 1..5. Después del intento 6 no hay más intentos: el caso escala (BR-U8-09). Elige un comportamiento explícito (por ejemplo `ValueError`), pruébalo y regístralo en la bitácora.
  - PBT-U8-02, entera: para todo intento 1..5 y toda semilla, el retraso está en `[0,8; 1,2] · 30 s · 2^(n−1)`, y la suma de los 5 retrasos está en `[0,8 · 930 s; 1,2 · 930 s]`.
  - `rng` es un parámetro, no un `random` global, para que la propiedad sea reproducible.
- **`decision` (Paso 6; PBT-U8-03).**
  - **Reutiliza U0.** BR-U0-35 es `vectra_contracts.validation.decision_is_coherent`. BR-U0-36 y la forma de `used_factors` las aplica ya el validador de `DecisionIn` (`check_justification` y `check_used_factors`). No las reimplementes.
  - Lo propio de U8 es BR-U8-16: `used_factors` ⊆ `feature_id` de `recommendation.explanation.shap_vector`, o exactamente `["ninguno"]`.
  - **Códigos.** Una violación de BR-U0-35 → `409 conflict_state`. La docstring de U0 dice «U8 la comprueba contra el caso y responde `conflict_state`», y `audit.md` (cuarta revisión de coherencia, 2026-10-31) dice «BR-U0-35 queda en 409». Una violación de factores o de justificación → `422 validation_error`. `validate_decision` devuelve el `ProblemCode` de `vectra_contracts.catalog` (o un `Rechazo` que lo lleve), no un código HTTP escrito a mano.
  - **Oráculo de PBT-U8-03.** El oráculo es una tabla de verdad escrita **aparte** de la implementación. Evalúa la cadena completa: `DecisionIn.model_validate(raw)` y después `validate_decision(...)`. La generación cubre los productos del BLM §4: `decision` × `outcome` de la recomendación × factores (subconjunto, ajeno, `ninguno`, vacío) × justificaciones de 0 a 2001 caracteres con espacios en los bordes. Una justificación de 2001 caracteres la rechaza `DecisionIn`, y el oráculo lo espera como 422.
  - Ejemplos del plan (US-502), en `tests/unit/test_decision_examples.py`: `se_aparta` sin factores ni `ninguno` → 422; `sigue` con `["ninguno"]` → aceptada. Agrega `resuelve_revision` con una recomendación `revision_requerida` → aceptada, y `sigue` con una `revision_requerida` → 409.
- **`views` (Paso 7; PBT-U8-04).**
  - **Entrada.** `views` recibe la fila del caso y sus datos asociados ya leídos: identificadores (o su ausencia), decisión confirmada, `credit_status` y la fecha de entrada a `no_disponible`. No lee la base: eso es del Bloque D (`api.py`).
  - **`score` y `outcome`.** Salen de `recommendation`, solo en `listo` y `decidido`. En los otros cinco estados son `None`, igual que `recommendation`, `recommendation_entry_id` y la explicación.
  - **`attempts` y `last_cause`.** `CaseDetail.attempts` es obligatorio en U0. `last_cause` va en `en_sincronizacion` y `no_disponible`. En los demás estados, el plan no fija si va: elige, prueba y registra.
  - **`applicant_display`.** Es `full_name` + los últimos 4 dígitos de `document_number`. Si el caso está anonimizado, va **vacío** (U0, domain-entities, `CaseSummary`: «vacío si el caso está anonimizado»). Es la **única** identificación de la bandeja.
  - **`application` sin `sex` ni `socioeconomic_stratum`.** `cases.application` guarda `ApplicationIn` sin el grupo de identificación, así que sí lleva `sex` y `socioeconomic_stratum`, que usa el monitoreo. `CaseDetail.application` es `ApplicationView`, que no los tiene. Quítalos **explícitamente** antes de construir el modelo: un `StrictModel` rechazaría el campo extra, y ese error no puede ser la defensa.
  - **`identifiers`.** Presente solo si el caso no está anonimizado, y la marca `anonymized` es coherente con eso (los validadores de U0 ya lo exigen).
  - **`credit_status`.** Lo calcula `credit` (Paso 12, U08-T03) y `views` lo pone en `CaseDetail`. Por BR-U8-21, el core solo se consulta para casos `decidido`. En los demás estados el valor es `None`, porque U0 lo declara opcional. La enmienda (§3, P-11) dice que `credit_status` es obligatorio en `CaseDetail`: eso significa que el código de `credit` entra, no que el campo deje de ser opcional en U0.
  - **`PersistentFailure.since`.** Es la fecha de entrada a `no_disponible` (U0 domain-entities). `views` la recibe como dato. De dónde sale es del Bloque D (P-3, para U08-T03).
  - **PBT-U8-04, entera.** Casos en los 7 estados, con y sin recomendación guardada, anonimizados o no. En ningún estado distinto de `listo` y `decidido` hay `score`, `outcome`, `recommendation` ni `explanation`. La bandeja nunca tiene identificadores completos. Ninguna vista del analista tiene `sex` ni `socioeconomic_stratum`. `identifiers` aparece solo si el caso no está anonimizado.
  - **Rojo primero:** pasar `cases.application` tal cual a `CaseDetail` hace fallar la propiedad, o la construcción del modelo.
- **Generadores.** El BLM pide `ApplicationIn` con PII y texto libre adversarial, y recomendaciones con `shap_vector`. U0 tiene `application_dicts`, `application_from` y `explanation` en `contracts/tests/strategies/domain.py`, pero ninguna unidad importa hoy las pruebas de U0. Copia el patrón a `case-management/tests/` y cita el origen en el archivo; no lo importes por ruta. Los perfiles de Hypothesis son los de U0 (`contracts/tests/conftest.py`), con `ci` = 500 ejemplos y la semilla impresa (NFR-U8-52).
- **`logic.md`.** Documenta:
  - las tablas de `case_fsm`;
  - la regla del backoff y lo que pasa fuera de 1..5;
  - el reparto entre U0 y U8 en `validate_decision`, con los códigos;
  - las reglas de `views`, con las elecciones registradas;
  - la cobertura medida;
  - la nota «`mutmut` diferido por la demo (T3)».
- **`make -C case-management check`.** Suma a lo de U08-T01 la cobertura del 100 % de los cuatro módulos (CA-6). Termina en 0.
- **Plan.** Marca `[x]` los Pasos 4 a 8 con `(U08-T02)`. En el Paso 8, agrega la nota «`mutmut` diferido por la demo (T3)».

**Fuera** (recházalo aunque lo veas roto o tentador):

- **`mutmut` del Paso 8** sobre `case_fsm`, `validate_decision`, `views` y `backoff`, y NFR-U8-51. Es recorte E\*F:
  - enmienda §3, U8, fila «8 Resumen»: «Sin `mutmut` (T3)»;
  - §2 regla 3: «Las pruebas que miden y no son PBT (mutación, …) caen en T3 también donde la tabla del alcance marcó E. Pasa en … U8 Paso 8».
- **PBT-U8-01** (stateful sobre `case_fsm` y `evaluation`). Es del Paso 15 (U08-T04), porque necesita `evaluation`. Por eso `case_fsm` tiene ya `retry` y `vencido`.
- **Los Bloques D a I** (Pasos 9 a 26): servicios, clientes, worker, retención, mock, chart y alertas.
- **La lectura de la base y la fuente de `since`** (P-3, Bloque D).
- **Cambios a U0.** Si un modelo de U0 no encaja con la proyección (por ejemplo, la forma de `ApplicationView`), se reporta, no se corrige aquí.
- **Cambios a la migración de U08-T01.** Si la comparación del Paso 4 encuentra una diferencia, se reporta como hallazgo. No se corrige la revisión en esta tarea.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/case-management-code-generation-plan.md` (§1, Bloque C, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U8, §4, §5.2, §6 P-11, §8)
- `aidlc-docs/construction/case-management/functional-design/business-rules.md` (BR-U8-07, 12, 13, 13b, 16, 21)
- `aidlc-docs/construction/case-management/functional-design/business-logic-model.md` (§2 máquina de estados, §4: PBT-U8-02, 03, 04 y pruebas de ejemplo)
- `aidlc-docs/construction/case-management/functional-design/domain-entities.md` (§1, §4 vistas)
- `aidlc-docs/construction/case-management/nfr-requirements/nfr-requirements.md` (NFR-U8-50, 51, 52)
- `aidlc-docs/construction/case-management/infrastructure-design/infrastructure-design.md` (INF-U8-01, tabla de transiciones)
- `aidlc-docs/construction/contracts/functional-design/domain-entities.md` (`CaseSummary`, `PersistentFailure`)
- `contracts/python/vectra_contracts/src/vectra_contracts/validation.py` (`decision_is_coherent`, `check_used_factors`, `check_justification`)
- `contracts/python/vectra_contracts/src/vectra_contracts/models/api.py` (`DecisionIn`, `CaseDetail`, `DecisionView`) y `models/application.py` (`ApplicationIn`, `ApplicationView`, `CaseSummary`, `PersistentFailure`, `CaseIdentifiers`)
- `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` (`CaseState`, `ProblemCode`, `PROBLEM_STATUS`, `CreditStatus`)
- `contracts/tests/conftest.py` (perfiles de Hypothesis) y `contracts/tests/strategies/domain.py` (generadores de U0)
- `case-management/migrations/versions/` (la revisión con `CASE_TRANSITIONS`, de U08-T01)
- `aidlc-docs/audit.md` (la cuarta revisión de coherencia, 2026-10-31: «BR-U0-35 queda en 409»)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`.

- [ ] **CA-1** — `case_fsm` con la tabla de BR-U8-12 y la comparación con `case_transitions` (Paso 4; BR-U8-12; US-107, US-112).
  ```bash
  uv run pytest case-management/tests/unit/test_case_fsm.py -v
  ```
  Esperado: pasan una prueba por fila de BR-U8-12, el rechazo de cada par fuera de la tabla (exhaustivo), `decidido` y `vencido` terminales, `listo` sin reevaluación, y la igualdad de conjuntos con `CASE_TRANSITIONS` (16 pares). **Rojo primero:** el de la comparación (ver Precisiones).

- [ ] **CA-2** — `backoff`: PBT-U8-02 (Paso 5; BR-U8-07; US-112).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_backoff.py -v
  ```
  Esperado: pasa con el perfil `ci` (500 ejemplos, semilla impresa), con las dos cotas de PBT-U8-02. También pasa el caso del comportamiento fuera de 1..5. **Rojo primero:** un jitter de ±25 % hace fallar la propiedad.

- [ ] **CA-3** — `decision`: PBT-U8-03 y los ejemplos (Paso 6; BR-U8-16; BR-U0-35, 36; US-108, US-502).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_decision.py case-management/tests/unit/test_decision_examples.py -v
  ```
  Esperado: PBT-U8-03 pasa contra el oráculo por tabla de verdad. Pasan `se_aparta` sin factores ni `ninguno` → 422, y `sigue` con `["ninguno"]` → aceptada. Una violación de BR-U0-35 → `conflict_state` (409). Un factor ajeno al `shap_vector` → `validation_error` (422). **Rojo primero:** aceptar un factor ajeno al `shap_vector` hace fallar la propiedad.

- [ ] **CA-4** — `views`: PBT-U8-04 (Paso 7; BR-U8-13, 13b, 21; US-107).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_views.py -v
  ```
  Esperado: pasa con el perfil `ci`, sobre los 7 estados, con y sin recomendación, y anonimizados o no. Hay casos de ejemplo para:
  - `applicant_display` (nombre y los últimos 4 dígitos; vacío si está anonimizado);
  - `application` sin `sex` ni `socioeconomic_stratum`;
  - `credit_status` presente en un caso `decidido`;
  - `last_cause` en `en_sincronizacion` y `no_disponible`;
  - `PersistentFailure` con su `since`.

  **Rojo primero:** el de `application` (ver Precisiones).

- [ ] **CA-5** — Las tres funciones sin E/S (contrato de U08-T01, sin cambios).
  ```bash
  uv run lint-imports --config case-management/.importlinter
  ```
  Esperado: código 0, con los contratos en `KEPT`, ahora con código real en `case_fsm`, `backoff`, `decision` y `views`.

- [ ] **CA-6** — Cobertura de ramas del 100 % (Paso 8; NFR-U8-50, 52).
  ```bash
  uv run pytest case-management/tests/unit case-management/tests/property --cov=vectra_case.case_fsm --cov=vectra_case.backoff --cov=vectra_case.decision --cov=vectra_case.views --cov-branch --cov-fail-under=100
  ```
  Esperado: código 0, con `TOTAL … 100%` sobre los cuatro módulos.

- [ ] **CA-7** — Resumen y plan.
  ```bash
  test -f aidlc-docs/construction/case-management/code/logic.md && grep -n "mutmut" aidlc-docs/construction/case-management/code/logic.md && grep -nE "^- \[x\] \*\*Paso [45678] " aidlc-docs/construction/plans/case-management-code-generation-plan.md
  ```
  Esperado: `logic.md` existe y nombra el diferido de `mutmut`. Salen cinco líneas del plan, cada una con `(U08-T02)`.

- [ ] **CA-8** — `check` de la unidad (RL-4).
  ```bash
  make -C case-management check
  ```
  Esperado: código 0. Incluye lint, `mypy --strict`, import-linter, las migraciones de U08-T01, las propiedades con el perfil `ci` y la cobertura de CA-6.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_case_fsm.py`: las filas de BR-U8-12, el rechazo exhaustivo, los estados terminales y la comparación con `CASE_TRANSITIONS`.
- `tests/property/test_backoff.py`: PBT-U8-02 y el comportamiento fuera de 1..5.
- `tests/property/test_decision.py`: PBT-U8-03 con su oráculo.
- `tests/unit/test_decision_examples.py`: los ejemplos de US-502 y los de BR-U0-35.
- `tests/property/test_views.py`: PBT-U8-04 y los ejemplos de CA-4.
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U08-T02.md`. Como mínimo, los de CA-1, CA-2, CA-3 y CA-4. El par falla-pasa es la prueba.

---

## Notas

- Archivos que se **modifican en su sitio**: los cuatro módulos vacíos de U08-T01 y `aidlc-docs/construction/plans/case-management-code-generation-plan.md` (casillas de los Pasos 4 a 8). Nada de duplicados con sufijo.
- Archivo nuevo de documentación que pide el plan: `aidlc-docs/construction/case-management/code/logic.md`.
- PBT-U8-01..08 nunca se recortan. En esta tarea entran las tres del Bloque C (02, 03 y 04). La 01 es del Paso 15, la 05 del 15, la 06 del 9, la 07 del 10 y la 08 del 16 (esta última, diferida con su código, enmienda §5.2).
- `case_fsm` es la tabla de dominio que `evaluation` (Paso 15), `sweeps` (Paso 11) y `evidence` (Paso 10) van a usar. Su API (`transition`, los eventos y `Rechazo`) queda documentada en `logic.md`.

---

## Preguntas abiertas

- **P-3 — De dónde sale `PersistentFailure.since`** (para U08-T03, no bloquea esta tarea). U0 la define como «la fecha de entrada a `no_disponible`», pero `cases` no tiene esa columna (domain-entities §1.1).
  - **Recomendación:** usar `cases.updated_at`. En `no_disponible` nadie más escribe el caso: `case_app` solo cambia `model_frozen_after_recommendation` en casos `listo`, y la salida es por `retry` o por `vencido`, que cambian el estado. Una prueba de integración en el Bloque D lo comprueba.
  - **Alternativa:** una columna `no_disponible_since` que escribe el worker al escalar. Toca la migración y los grants de U08-T01.
