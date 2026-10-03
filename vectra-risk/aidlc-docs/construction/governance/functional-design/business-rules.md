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
| `lista_para_aprobacion` | `aprobado` | `cro` (MFA) | Distinto de `registered_by` (BR-U4-10) |
| `lista_para_aprobacion` | `rechazado` | `cro` (MFA) | Con justificación |
| `aprobado` | `activo` | `ingeniero_riesgo` (MFA), `mark_active` vía `promotion-tool` (F08) | BR-U4-08 |
| `activo` | `inactivo` | Sistema, dentro del mismo `mark_active` de otra versión | — |
| `inactivo` | `activo` | `ingeniero_riesgo` (MFA), `mark_active` | Rollback (US-208), después del sync del revert |
| `activo` | `congelado` | **Solo** `bias-monitoring-service` (`governance:freeze`) | Con paquete de contexto (U9) |
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

**BR-U4-04 — Bias solo congela (X04).** La identidad `bias-monitoring-service` solo puede
llamar a `freeze` y solo sobre la versión `activo`. Cualquier otro endpoint → `403`.

## 2. Registro y validación (Q6, Q7; US-201, US-202)

**BR-U4-05 — Lanzar la validación.** `start_validation` crea un Job en `vectra-staging`
(K01) con la imagen del `model-validation-job`, el `model_version_id`, los URIs y el
dataset de validación, y fija `deadline_at = ahora + 2 h`. Sin informe al vencer el plazo →
`validacion_fallida` (motivo `timeout`).

**BR-U4-06 — Registrar sin deserializar.** Al registrar:
1. `artifact_format` debe ser `onnx`, `xgboost_json`, `xgboost_ubj` o `lightgbm_txt`;
2. governance lee los **bytes** de `manifest.json` y de **cada** archivo que lista (predictor, explicador, fondo, envolvente, diccionario, especificación) en el model-store (F47);
3. rechaza `pickle` y `joblib` por extensión **y** por bytes mágicos (`\x80` + versión de protocolo de pickle, cabecera zip de joblib) en cualquiera de ellos;
4. verifica que cada SHA-256 coincida con el del manifiesto, y el del manifiesto con el declarado;
5. verifica que todos lleven el mismo `model_version_id` (precisado por U5 FD: el paquete tiene más archivos que predictor y explicador).

Nunca carga el modelo. Cualquier fallo → `422 validation_error`, sin crear la versión.

**BR-U4-07 — Qué bloquea.** Solo `sync_check.passed = false` lleva a `validacion_fallida`.
AUC y disparidad inicial se informan con sus umbrales y **no** bloquean: decide el CRO.
El informe incluye el `disclaimer` y nunca usa «sin sesgo», «libre de discriminación» ni
equivalentes (FR-BIA-08). Una prueba busca esas expresiones en las plantillas.

## 3. Promoción (Q2; US-204, US-208)

**BR-U4-08 — `mark_active`.** En **una** transacción:
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
- `normative_current = normative_at(policy, hoy)`. Si es nulo, scoring falla cerrado (`serving_config_unavailable`).
- Alertas: `NormativeParamsExpiring` SEV2 15 días antes del fin de la última vigencia y SEV1 el día que vence.

**BR-U4-12 — Los servicios no escriben política (FR-POL-04).** Ningún scope de servicio
permite escribir políticas: solo el rol `cro` por el BFF. El rol de base de scoring no
existe en `governance-db` (scoring lee por la API, F18).

## 6. Fuentes de datos (Q8; US-306, FR-BIA-06)

**BR-U4-13 — Ciclo de una fuente.**
- Al proponer (`ingeniero_riesgo`, MFA), governance pide `compare_source` a bias (F27) y la fuente pasa a `en_evaluacion`.
- `cumplimiento` (MFA) decide `aprobada` o `rechazada` **solo** si existe `pre_post_report_ref`; si no → `409`.
- Una fuente aprobada no cambia el modelo activo; la puede declarar una versión **futura** en `data_sources`.
- Registrar una versión que declara una fuente no aprobada → `422`.

## 7. `serving-config` y congelamiento (Q5, Q9)

**BR-U4-14 — Propagación.** scoring cachea `serving-config` como máximo 5 s, con
`If-None-Match`. Un congelamiento tiene efecto en **≤ 6 s**: hasta 1 s de convergencia entre
las réplicas de governance (NFR-U4-05) más los 5 s de caché. Es un límite aceptado y medido
(precisado el 2026-10-03 por U4 NFR Requirements, NFR-U4-06; antes decía ≤ 5 s sin contar
la convergencia entre réplicas).

**BR-U4-15 — Congelar es inmediato.** `freeze` aplica el estado `congelado` y recalcula
`serving-config` **en la misma transacción**, antes de escribir el evento en el registro
(BR-U4-17, excepción).

**BR-U4-16 — Monitoreo detenido.** Si `bias_monitoring_age_s` supera W →
`MonitoreoSesgoDetenido` SEV2; si supera 2W → SEV1. El modelo **sigue sirviendo**.
No hay ruta de congelamiento manual.

## 8. Coherencia con el registro (decisión de diseño de este FD)

**BR-U4-17 — Ninguna transición tiene efecto sin evidencia**, salvo el congelamiento:
1. transacción 1: se inserta la `ModelTransition` en `pendiente_registro`; el estado **no** cambia todavía;
2. append al registro con `idempotency_key = transition_id`;
3. transacción 2: con el ack, la transición pasa a `confirmada`, se aplica el estado y se recalcula `serving-config`.

Si el registro no responde, la acción devuelve `503` y la transición queda pendiente, sin
efecto. Un reconciliador reintenta las pendientes con la misma llave (nunca duplica, BR-U3-06);
las que pasan 24 h sin confirmar quedan `abandonada` y se alerta. La misma regla aplica a las
transiciones de política y de fuentes.

**Excepción — `freeze`:** congelar **reduce** el riesgo (deja de servir), así que se aplica de
inmediato (BR-U4-15) y el evento `freeze` se escribe después, con reintentos del reconciliador.
Si el registro está caído, el modelo queda congelado igual y se alerta `FreezeEventPending`
(SEV2) hasta que el evento quede escrito.

## 9. Alertas

| Alerta | Severidad | Regla |
|---|---|---|
| `ModeloCongelado` | SEV1 | BR-U4-15 (definida en S4) |
| `NormativeParamsExpiring` | SEV2 / SEV1 | BR-U4-11 |
| `MonitoreoSesgoDetenido` | SEV2 / SEV1 | BR-U4-16 |
| `PromotionMismatchPersistent` | SEV2 | BR-U4-08 |
| `FreezeEventPending` | SEV2 | BR-U4-17 |
| `GovernanceTransitionAbandoned` | SEV2 | BR-U4-17 |
| `ValidationTimeout` | SEV3 | BR-U4-05 |

## 10. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 `ServingConfig` | `etag`, `normative_current`, `bias_monitoring_age_s` | Q4, Q5, Q9 |
| U0 `ServingState` | `no_disponible` también si `normative_current` es nulo | Q4 |
| U0 `PolicyDraft` / `PolicyVersion` / BR-U0-33 | `normative` como lista sin solapes; estados `propuesta`, `activa`, `rechazada`, `historica`; aprobador ≠ proponente | Q3, Q4 |
| U0 `model_event` | Eventos `validacion_fallida` e `inactivado` | Q1 |
| U0 `policy_event` | `propuesta`, `activada`, `rechazada`, `historica` (sin `aprobada` separada) | Q4; BR-U4-17 (un evento por transición) |
| U0 `data_source_event` | Agrega `evaluacion_iniciada` | Q8; BR-U4-17 |
| U3 BR-U3-16 | Actores de servicio o de sistema para los eventos del Job de validación y del vencimiento del plazo | BR-U4-05, 07 |
| U0 plan de tareas, Paso 7 | Pruebas de BR-U0-33 (vigencias solapadas) y de `normative_current` nulo → fail-closed | Q4 |
| U5, U6 (pendiente) | Artefactos en ONNX, XGBoost JSON/UBJ o LightGBM texto; sin `pickle`/`joblib` | Q7 |
| U7 (pendiente) | Métrica de `version_mismatch` para `PromotionMismatchPersistent`; caché de `serving-config` ≤ 5 s con `If-None-Match` | Q2, Q5 |
| U9 (pendiente) | Definir W e informar la edad del último cálculo a governance | Q9 |
