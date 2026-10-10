# Reglas de negocio — U4 `governance`

Los IDs `BR-U4-xx` se referencian en los planes de tareas. La autenticación, el step-up
(15 min) y la validación de estructura son de U0 y U2.

---

## 1. Máquina de estados del modelo (Q1; FR-MOD-05, US-201..204, 208, 305)

**BR-U4-01 — Transiciones permitidas.** Solo estas, con su actor:

| Desde | Hacia | Actor | Condición |
|---|---|---|---|
| — | `registrado` | `ingeniero_riesgo` (MFA) | BR-U4-06 |
| `registrado` | `en_validacion` | `ingeniero_riesgo` (MFA) | Lanza el Job (BR-U4-05) |
| `en_validacion` | `lista_para_aprobacion` | `model-validation-job` (`governance:validation-report`) | Informe completo con `sync_check.passed` (BR-U4-07) |
| `en_validacion` | `validacion_fallida` | `model-validation-job` o el sistema | Sincronía fallida, Job fallido o sin informe en 2 h |
| `validacion_fallida` | `en_validacion` | `ingeniero_riesgo` (MFA) | Reintento |
| `lista_para_aprobacion` | `aprobado` | `cro` (MFA) | Distinto de `registered_by` (BR-U4-10); si tiene `source_candidate_for`, la fuente debe estar `aprobada` (si no → 409, BR-U4-13; segunda revisión del FD de U9, 2026-10-08) |
| `lista_para_aprobacion` | `rechazado` | `cro` (MFA) | Con justificación |
| `aprobado` | `activo` | `ingeniero_riesgo` (MFA), `mark_active` vía `promotion-tool` (F08) | BR-U4-08; si tiene `source_candidate_for`, la fuente debe estar `aprobada` (si no → 409; segunda revisión del FD de U9, 2026-10-08) |
| `activo` | `inactivo` | Sistema, dentro del mismo `mark_active` de otra versión | — |
| `inactivo` | `activo` | `ingeniero_riesgo` (MFA), `mark_active` | Rollback (US-208), después del sync del revert |
| `activo` | `congelado` | **Solo** `bias-monitoring-job`, el CronJob de U9 (`governance:freeze`; antes `bias-monitoring-service`, revisión del FD de U9, 2026-10-08) | Con paquete de contexto (U9) |
| `congelado` | `activo` | **Solo** `cumplimiento` (MFA), `reactivar` | Con justificación |
| `congelado` | `retirado` | **Solo** `cumplimiento` (MFA), `descartar` | Con justificación |
| `congelado` | `congelado` + `investigation = true` | **Solo** `cumplimiento` (MFA), `investigar` | Con justificación |
| `inactivo`, `rechazado`, `validacion_fallida` | `retirado` | `cro` (MFA) | Retiro definitivo |

Cualquier otra combinación de estado, actor o transición → `403 forbidden` (actor
equivocado) o `409 conflict_state` (estado equivocado).

**BR-U4-02 — Una sola versión servible.** Como máximo una versión en `activo` o
`congelado` (restricción única parcial en la base). `mark_active` de una versión mientras
otra está `congelado` → `409`: un modelo congelado no se reemplaza por promoción, lo
resuelve cumplimiento (AUTONOMIA-04).

**BR-U4-03 — Sin reactivación automática (AUTONOMIA-04, X03).** No existe ningún Job,
CronJob, webhook ni reintento que lleve un modelo de `congelado` a `activo`. La única ruta es
`POST /v1/models/{id}/frozen-resolution` con `action = reactivar`, rol `cumplimiento` y
`acr = mfa` con `auth_time` ≤ 15 min. Un script de CI busca en el repositorio cualquier otra
escritura de `state = 'activo'` desde `congelado` y falla si la encuentra (US-305).

**BR-U4-04 — Bias solo congela (X04).** La identidad `bias-monitoring-job` (el CronJob de U9; el servicio HTTP `bias-monitoring-service` no tiene `governance:freeze`, revisión del FD de U9, 2026-10-08) solo puede
llamar a `freeze` y solo sobre la versión `activo`. Cualquier otro endpoint → `403`.

## 2. Registro y validación (Q6, Q7; US-201, US-202)

**BR-U4-05 — Lanzar la validación.** `start_validation` crea un Job en `vectra-staging`
(K01) con la imagen del `model-validation-job`, el `model_version_id`, los URIs y el
dataset de validación, y fija `deadline_at = ahora + 2 h`. Sin informe al vencer el plazo →
`validacion_fallida` (motivo `timeout`).
- **Modo `source_comparison`** (BR-U4-13; revisión del FD de U9, 2026-10-08, H7): el Job recibe `mode = source_comparison`, `source_id`, la versión candidata y la versión `activo`. X08 impide que el Job llame a `vectra-serving`, así que la versión activa se despliega **también en KServe de staging** (un `InferenceService` de staging con el mismo artefacto del model-store, por PR y sync manual, como la candidata) y el Job usa F30 para las dos. Si vence el plazo en este modo, el `ValidationRun` queda `timeout`, la fuente sigue `en_evaluacion` sin informe y **ninguna** versión cambia de estado (no hay `validacion_fallida`); el ingeniero puede relanzar.

**BR-U4-06 — Registrar sin deserializar.** Al registrar:
1. `artifact_format` debe ser `onnx`, `xgboost_json`, `xgboost_ubj` o `lightgbm_txt`;
2. governance lee los **bytes** de `manifest.json` y de **cada** archivo que lista (predictor, explicador, fondo, envolvente, diccionario, especificación) en el model-store (F47);
3. rechaza `pickle` y `joblib` por extensión **y** por bytes mágicos (`\x80` + versión de protocolo de pickle, cabecera zip de joblib) en cualquiera de ellos;
4. verifica que cada SHA-256 coincida con el del manifiesto, y el del manifiesto con el declarado;
5. verifica que todos lleven el mismo `model_version_id` (precisado por U5 FD: el paquete tiene más archivos que predictor y explicador).

Nunca carga el modelo. Cualquier fallo → `422 validation_error`, sin crear la versión.
Al registrar con éxito, governance guarda una copia del `feature_dictionary.json` verificado
en la versión (U7 FD Q4), y también del `feature_spec.json` con sus tablas de búsqueda (precisado el 2026-10-06 por U8 FD Q1).

**BR-U4-18 — Diccionario de features.** `GET /v1/models/{id}/feature-dictionary` devuelve el
diccionario guardado de esa versión. Solo lo puede leer la identidad con
`governance:read-dictionary` (explainability-service, F103). El diccionario de una versión
no cambia nunca, así que el llamador lo puede cachear por `model_version_id` sin límite de
tiempo (agregado por U7 FD Q4).

**BR-U4-19 — `feature_spec`.** `GET /v1/models/{id}/feature-spec` devuelve el `feature_spec`
verificado de esa versión, con sus tablas de búsqueda. Solo lo puede leer la identidad con
`governance:read-feature-spec` (case-service, F104). Es inmutable por versión y se puede
cachear sin límite (agregado por U8 FD Q1).

**BR-U4-07 — Qué bloquea.** Solo `sync_check.passed = false` lleva a `validacion_fallida`.
AUC y disparidad inicial se informan con sus umbrales y **no** bloquean: decide el CRO.
El informe incluye el `disclaimer` y nunca usa «sin sesgo», «libre de discriminación» ni
equivalentes (FR-BIA-08). Una prueba aplica a las plantillas la lista única de U0 (`contracts/forbidden-phrases.yaml`, BR-U0-94; precisado el 2026-10-10 por U10 FD, Q8).

## 3. Promoción (Q2; US-204, US-208)

**BR-U4-08 — `mark_active`.** En **una** transacción, como una sola unidad de evidencia (BR-U4-17; precisado el 2026-10-06, revisión del FD de U8):
- la versión destino pasa a `activo`;
- la que estaba `activo` pasa a `inactivo`;
- `serving-config` se recalcula con un `etag` nuevo y con `inference_service` apuntando al `InferenceService` de la versión destino (azul/verde, U6 NFR Design Q2).

Governance no consulta a KServe. Si KServe todavía sirve otra versión, scoring falla
cerrado con `version_mismatch` (BR-U0-02) hasta que coincidan. La métrica de `version_mismatch`
que emite scoring (U7) alimenta la alerta `PromotionMismatchPersistent` (SEV2) si dura más
de 10 min.

**BR-U4-09 — Promoción solo por PR.** `promotion-tool create_promotion_pr` solo acepta
versiones `aprobado` (o `inactivo`, para un rollback). Genera un PR de **un solo commit**
que **agrega** el `InferenceService` de la versión (`isvc-<8 hex>`, predictor y explicador con el mismo `storageUri`) sin tocar el activo, con la evidencia `helm
template` y `kubectl diff`. Después de `mark_active`, un PR **post-activación** baja el `InferenceService` de la versión anterior a 1 réplica por componente, y un PR de **retiro** lo elimina cuando lleva más de 7 días `inactivo`. En un rollback, un PR restaura primero los mínimos de producción del `InferenceService` anterior, y `mark_active` se ejecuta solo cuando está listo con 2 réplicas. Todos los genera `promotion-tool` (precisado por U6 NFR Design Q2 e Infrastructure Design INF-U6-02). Nunca sincroniza ni aplica (AUTONOMIA-01). Un script de CI
verifica en el PR: un solo commit, las dos piezas con el mismo `model_version_id` y la
evidencia adjunta.

## 4. Separación de funciones (Q3; BR-U2-02)

**BR-U4-10 — Cuatro ojos.** Quien aprueba es distinto de quien propuso o registró
(comparación por `sub`):
- política: el CRO que aprueba ≠ el CRO que propuso (`409` si coinciden);
- modelo: el `cro` que aprueba ≠ `registered_by` (ya garantizado por roles distintos, pero también se verifica);
- fuente: el `cumplimiento` que decide ≠ `proposed_by`.

Producción necesita al menos 2 usuarios con rol `cro`.

## 5. Política (Q4; FR-POL-01..04, US-205, US-206)

**BR-U4-11 — Activación y vigencia.**
- Aprobar una política `propuesta` la deja `activa` de inmediato; la anterior pasa a `historica` y `serving-config` se recalcula.
- `normative` es una lista de vigencias que no se solapan; se pueden cargar vigencias futuras.
- `normative_current = normative_at(policy, hoy)`. Si es nulo, la política de scoring produce `revision_requerida` con el motivo `parametro_normativo_no_vigente` (US-207); **no** es un fail-closed (precisado el 2026-10-03 por U7 FD Q1: alinea con US-207).
- Alertas: `NormativeParamsExpiring` SEV2 15 días antes del fin de la última vigencia y SEV1 el día que vence.

**BR-U4-12 — Los servicios no escriben política (FR-POL-04).** Ningún scope de servicio
permite escribir políticas: solo el rol `cro` por el BFF. El rol de base de scoring no
existe en `governance-db` (scoring lee por la API, F18).

## 6. Fuentes de datos (Q8; US-306, FR-BIA-06)

**BR-U4-13 — Ciclo de una fuente.**
- Al proponer (`ingeniero_riesgo`, MFA), la fuente pasa a `en_evaluacion` (precisado el 2026-10-08 por U9 FD, Q10):
  1. el ingeniero registra una **versión candidata** que declara la fuente. Se admite aunque la fuente no esté aprobada, solo porque está `en_evaluacion`, y queda marcada `source_candidate_for = source_id`: no puede aprobarse ni activarse mientras la fuente no esté `aprobada`;
  2. el ingeniero (MFA) lanza la comparación con `start_source_comparison(source_id, candidate_version_id)` (`POST /v1/data-sources/{id}/comparisons`; BFF solo para `ingeniero_riesgo`, como `start_validation`) (segunda revisión del FD de U9, 2026-10-08). Condiciones, si no → `409 conflict_state`:
     - la fuente está `en_evaluacion` y no tiene otra comparación `lanzado`;
     - la candidata tiene `source_candidate_for = source_id` y está en `registrado`, `validacion_fallida` o `lista_para_aprobacion` (la comparación no cambia su estado);
     - existe una versión `activo`: sin versión `activo` → `reason = no_active_version`; si la versión servible está `congelado` → `reason = active_version_frozen` (no se compara contra un modelo congelado);
     - los `InferenceService` de staging de la candidata y de la versión activa existen (INF-U4-05);

     governance lanza el `model-validation-job` en modo `source_comparison` (BR-U4-05): puntúa el mismo dataset de validación con la versión `activo` («antes») y con la candidata («después») y devuelve por F32 (`PUT /v1/validation-runs/{run_id}/source-counts`, scope `governance:validation-report`; solo para un `ValidationRun` en modo `source_comparison` y estado `lanzado`, y solo una vez: otro modo o estado → 409; segunda revisión del FD de U9, 2026-10-08) **tablas de conteo por atributo** (grupo × banda × resultado), nunca filas;
  3. governance llama a `compare_source(source_id, pre, post)` en bias por **F25** (antes decía F27, que es el `freeze`) y guarda el `PrePostReport` en `data_sources.pre_post_report` (revisión del FD de U9, 2026-10-08, H7).
- `cumplimiento` (MFA) decide `aprobada` o `rechazada` **solo** si existe `pre_post_report`; si no → `409`. El evento de la decisión (`data_source_event`) lleva el `PrePostReport`, con la regla de tamaño de U9 BR-U9-15 (≤ 48 KiB; si no, sin las celdas).
- Una fuente aprobada no cambia el modelo activo; la puede declarar una versión **futura** en `data_sources`.
- Registrar una versión que declara una fuente no aprobada → `422`, salvo la candidata del punto 1.

## 7. `serving-config` y congelamiento (Q5, Q9)

**BR-U4-14 — Propagación.** scoring, y también case-service (F104, `governance:read-serving`, U8 BR-U8-05), cachea `serving-config` como máximo 5 s, con
`If-None-Match`. Las lecturas de case-service se suman a las de scoring; el NFR de U8 debe verificarlas contra NFR-U4-10/11 y el script k6 de U4 (precisado el 2026-10-06, revisión del FD de U8). Un congelamiento tiene efecto en **≤ 6 s**: hasta 1 s de convergencia entre
las réplicas de governance (NFR-U4-05) más los 5 s de caché. Es un límite aceptado y medido
(precisado el 2026-10-03 por U4 NFR Requirements, NFR-U4-06; antes decía ≤ 5 s sin contar
la convergencia entre réplicas). Si una réplica de governance queda aislada de la base, el
límite es ≤ 35 s: sirve su copia como máximo 30 s sin confirmarla y después responde 503
(NFR-U4-04; segunda revisión del Infrastructure Design de U10, 2026-10-10).

**BR-U4-15 — Congelar es inmediato.** `freeze` aplica el estado `congelado` y recalcula
`serving-config` **en la misma transacción**, antes de escribir el evento en el registro
(BR-U4-17, excepción). Antes de escribir el evento, governance agrega al `FreezeContext` que
envía bias (U9 BR-U9-15) las `data_sources` de la versión y su `initial_disparity` de la
validación (precisado el 2026-10-08 por U9 FD, BR-U9-16).
**Tamaño del evento** (segunda revisión del FD de U9, 2026-10-08): el registro rechaza más de 64 KiB (BR-U3-07). El paquete de bias
llega con ≤ 48 KiB (BR-U9-15). Si el evento supera 60 KiB, `initial_disparity` se reduce a sus
agregadas; si aún supera 64 KiB, `data_sources` se reduce a sus ids. Con eso el evento cabe
siempre, y `FreezeEventPending` nunca reintenta un evento que el registro rechazaría por
tamaño.

**BR-U4-16 — Monitoreo detenido.** `MonitoreoSesgoDetenido` es la regla de U9 (BR-U9-21):
SEV2 a W (1 h) y SEV1 a 2W, sobre la métrica `vectra_bias_last_success_timestamp`. El modelo
**sigue sirviendo**. No hay ruta de congelamiento manual. Governance no recibe la edad del
cálculo: bias solo puede llamar a `freeze` (X04) (precisado el 2026-10-08 por U9 FD; antes usaba `bias_monitoring_age_s`).

## 8. Coherencia con el registro (decisión de diseño de este FD)

**BR-U4-17 — Ninguna transición tiene efecto sin evidencia**, salvo el congelamiento:
1. transacción 1: se inserta la `Transition` (tabla `transitions`, domain-entities §1.3) en `pendiente_registro`; el estado **no** cambia todavía;
2. append al registro con `idempotency_key = UUIDv5(entity_type:entity_id, n)`. `n` es el número de la transición de esa entidad (versión de modelo, política o fuente): sus transiciones **no abandonadas** + 1, es decir, cuenta también las pendientes. Un índice único parcial `(entity_type, entity_id, n) WHERE status <> 'abandonada'` lo garantiza (tabla única `transitions` para las tres entidades; precisado el 2026-10-06, revisión del FD de U8). La llave es determinista: una transición nueva después de un abandono reutiliza la llave de la abandonada (precisado el 2026-10-06);
3. transacción 2: con el ack, se **revalida** que la transición siga `pendiente_registro` y que el estado actual de la entidad sea su `from_state`. Si es así, la transición pasa a `confirmada`, se aplica el estado y se recalcula `serving-config`. Si no (por ejemplo, la versión ya está `congelado`), no se aplica nada y la transición queda `descartada` (precisado el 2026-10-06, revisión del FD de U8).

Si el registro no responde, la acción devuelve `503` y la transición queda pendiente, sin
efecto. Un reconciliador reintenta las pendientes con la misma llave (nunca duplica, BR-U3-06), con un `occurred_at` nuevo en cada intento (BR-U3-05 precisada el 2026-10-06; sin eso, un reintento después de 5 min se rechazaría siempre). El payload del evento y el `correlation_id` original se guardan al crear la transición y se reenvían sin cambios (precisado el 2026-10-06, revisión del FD de U8);
las que pasan 24 h sin confirmar quedan `abandonada` y se alerta. La misma regla aplica a las
transiciones de política y de fuentes, guardadas en la misma tabla `transitions` (domain-entities §1.3). La activación de una política (`propuesta → activa` de la nueva y `activa → historica` de la anterior, BR-U4-11) forma una unidad, igual que `mark_active` (precisado el 2026-10-06, revisión del FD de U8).

**Una sola transición pendiente por entidad** (precisado el 2026-10-06):
- Una transición nueva, distinta de `freeze`, sobre una entidad con otra pendiente se rechaza con `409 conflict_state` y `reason = transition_pending`. El usuario la repite cuando la anterior se confirme o se abandone.
- Así, dos acciones concurrentes nunca calculan el mismo `n`, y los eventos de una entidad entran a la cadena en orden de `n`. Por ejemplo, una `frozen_resolution` nunca queda antes de su `freeze`: cumplimiento no puede resolver mientras el `freeze` siga pendiente.
- **`freeze` es la excepción**, porque reduce el riesgo. Se aplica aunque haya otra transición pendiente en la versión (en la práctica, el `activo → inactivo` de un `mark_active` en curso), y **en la misma transacción descarta** esa transición y su unidad completa (ver abajo). Toma el `n` siguiente; el `n` de la descartada queda reservado.
- El reconciliador escribe los eventos de cada entidad **estrictamente en orden de `n`**. Las `n` de las transiciones `descartada` nunca se escriben: el orden las **salta** y pasa a la siguiente `n` pendiente (precisado el 2026-10-06, revisión del FD de U8).
- Una fila de compensación (`transicion_descartada`) sin escribir **es una transición pendiente**: bloquea las transiciones nuevas de la entidad, incluida una `frozen_resolution`, hasta que se confirme (`409 conflict_state`, `reason = transition_pending`). Así la resolución de cumplimiento nunca entra en la cadena antes de la compensación (precisado el 2026-10-06, revisión del FD de U8).
- Una compensación **nunca se abandona**, igual que el evento `freeze`: abandonarla dejaría en la cadena un evento original sin efecto y sin marca, y desbloquearía la `frozen_resolution` sin compensación escrita. Sigue reintentando; como no lleva momento de negocio, la cota de BR-U0-37 no la vence. Mientras exista una pendiente, se alerta `CompensationEventPending` (SEV2) (precisado el 2026-10-06, revisión del FD de U8).

**Unidad de `mark_active`** (precisado el 2026-10-06, revisión del FD de U8): `aprobado → activo` de la versión destino y `activo → inactivo` de la anterior forman **una sola unidad** (`unit_id`). Solo se confirma cuando las dos tienen ack, y se aplica, se descarta, **se abandona y se recupera siempre completa**:
- **Abandono a las 24 h**: si una mitad sigue sin ack, la unidad entera deja de confirmarse. Las mitades sin ack quedan `abandonada` (su `n` se puede reutilizar). Las mitades que sí tenían ack quedan `descartada` (su `n` queda reservado), y por cada una se escribe un `transicion_descartada` con motivo `abandono`, porque su evento ya está en la cadena sin haber tenido efecto.
- **Recuperación**: el conflicto tras un abandono (abajo) solo puede confirmar una unidad completa. Si la otra mitad ya está `descartada`, la mitad recuperada también queda `descartada`, con su `transicion_descartada`, y nunca se aplica sola. Si un `freeze` descarta la mitad de la versión anterior, la versión destino **no** pasa a `activo`. Promover no puede descongelar (BR-U4-02, AUTONOMIA-04): la promoción se repite después de la resolución de cumplimiento.

**Rastro de una transición descartada** (precisado el 2026-10-06, revisión del FD de U8): por cada transición descartada, governance crea un `model_event` con `event = transicion_descartada` (`details`: la `idempotency_key` descartada y el motivo, p. ej. `freeze`), con su propio `n` en la entidad. En la versión congelada va después del `freeze`. El reconciliador lo escribe. Así, si el evento original sí llegó al registro con el ack perdido, la cadena muestra que no tuvo efecto; si no llegó, la compensación queda igual, explícita. **Cómo se guarda**: como una fila de `Transition` (`entity_type = model_version`) sin cambio de estado (`from_state = to_state`, `kind = compensacion`), con su propio `n` y su llave UUIDv5(`entity_type`:`entity_id`, n). Sigue el mismo ciclo `pendiente_registro → confirmada` y nunca aplica estado. Actor: `{kind: system, id: governance-service}` (BR-U3-16).

**Conflicto tras un abandono** (precisado el 2026-10-06): si una transición nueva recibe 409 del
registro (la abandonada sí se había escrito y se perdió el ack), governance reenvía la
abandonada con su llave, obtiene el ack original, la revalida como en el paso 3 y, si procede,
la confirma y aplica **ese** estado. Si pertenece a una unidad, aplica la regla de recuperación
de la unidad: se confirma solo la unidad completa (precisado el 2026-10-06, revisión del FD de U8). La nueva se rechaza con `409 conflict_state`. Así el
registro nunca tiene dos eventos para la misma transición.

**Excepción — `freeze`:** congelar **reduce** el riesgo (deja de servir), así que se aplica de
inmediato (BR-U4-15) y el evento `freeze` se escribe después, con reintentos del reconciliador; el payload lleva `frozen_at` (U0 §5.2, agregado el 2026-10-06).
Si el registro está caído, el modelo queda congelado igual y se alerta `FreezeEventPending`
(SEV2) hasta que el evento quede escrito.

## 9. Alertas

| Alerta | Severidad | Regla |
|---|---|---|
| `ModeloCongelado` | SEV1 | BR-U4-15 (definida en S4) |
| `NormativeParamsExpiring` | SEV2 / SEV1 | BR-U4-11 |
| `MonitoreoSesgoDetenido` | SEV2 / SEV1 | BR-U4-16; la define U9 (BR-U9-21) |
| `PromotionMismatchPersistent` | SEV2 | BR-U4-08 |
| `FreezeEventPending` | SEV2 | BR-U4-17 |
| `CompensationEventPending` | SEV2 | BR-U4-17: una `transicion_descartada` sin escribir; nunca se abandona (precisado el 2026-10-06, revisión del FD de U8) |
| `GovernanceTransitionAbandoned` | SEV2 | BR-U4-17 |
| `ValidationTimeout` | SEV3 | BR-U4-05 |

## 10. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 `ServingConfig` | `etag`, `normative_current` (`bias_monitoring_age_s` se agregó aquí y se quitó por el FD de U9, 2026-10-08) | Q4, Q5, Q9 |
| U0 `ServingState` | ~~`no_disponible` también si `normative_current` es nulo~~ — revertido por U7 FD Q1 (US-207): sin normativa vigente → `revision_requerida` | Q4; U7 Q1 |
| U0 `PolicyDraft` / `PolicyVersion` / BR-U0-33 | `normative` como lista sin solapes; estados `propuesta`, `activa`, `rechazada`, `historica`; aprobador ≠ proponente | Q3, Q4 |
| U0 `model_event` | Eventos `validacion_fallida` e `inactivado` | Q1 |
| U0 `policy_event` | `propuesta`, `activada`, `rechazada`, `historica` (sin `aprobada` separada) | Q4; BR-U4-17 (un evento por transición) |
| U0 `data_source_event` | Agrega `evaluacion_iniciada` | Q8; BR-U4-17 |
| U3 BR-U3-16 | Actores de servicio o de sistema para los eventos del Job de validación y del vencimiento del plazo | BR-U4-05, 07 |
| U0 plan de tareas, Paso 7 | Prueba de BR-U0-33 (vigencias solapadas); la de `normative_current` nulo pasa a U7 | Q4; U7 Q1 |
| U5, U6 (pendiente) | Artefactos en ONNX, XGBoost JSON/UBJ o LightGBM texto; sin `pickle`/`joblib` | Q7 |
| U7 (pendiente) | Métrica de `version_mismatch` para `PromotionMismatchPersistent`; caché de `serving-config` ≤ 5 s con `If-None-Match` | Q2, Q5 |
| ~~U9 (pendiente)~~ **Resuelto** | Definir W e informar la edad del último cálculo a governance: W = 1 h y la alerta sale de una métrica de bias; se quita `bias_monitoring_age_s` (precisado el 2026-10-08 por U9 FD) | Q9 |
| U4 (esta unidad), por U9 FD | BR-U4-13 (candidata de evaluación, job en modo `source_comparison`, F25), BR-U4-15 (paquete), BR-U4-16, domain-entities §5, PBT-U4-05 | U9 FD Q7, Q9, Q10 |
| U4 (esta unidad), revisión del FD de U9, 2026-10-08 | BR-U4-01 y BR-U4-04 con la identidad `bias-monitoring-job`; `guard_freeze`; BR-U4-05 con el modo `source_comparison` y su vencimiento; BR-U4-13 con `pre_post_report` guardado; `ValidationRun` con `mode`; `initial_disparity` con el formato de U9; business-logic-model §2.5; P-U4-07 | H4, H7, H11 |
| U0 `model_event` | Evento `transicion_descartada` (compensa una transición descartada por un `freeze` o por el abandono de una unidad) | BR-U4-17; precisado el 2026-10-06, revisión del FD de U8 |
| U3 BR-U3-16 | Actor de `transicion_descartada`: `{kind: system, id: governance-service}` | BR-U4-17; precisado el 2026-10-06, revisión del FD de U8 |
