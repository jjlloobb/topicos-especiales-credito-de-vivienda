# Plan de Functional Design — U4 `governance`

**Alcance de la unidad** (`unit-of-work.md` §1):
- `governance-service`: máquina de estados del modelo, aprobaciones del CRO y de cumplimiento con MFA, transiciones acotadas por identidad, políticas versionadas con parámetros normativos (VIS y usura) con vigencia, fuentes de datos y `serving-config`;
- esquema de `governance-db`;
- `model-validation-job`;
- CLI `promotion-tool` (PR de un solo commit con evidencia).

**Historias (dueña):** US-201 (registrar versión), US-202 (validación en staging), US-203
(aprobación del CRO), US-204 (promoción atómica vía PR), US-205/206 (política propuesta y
aprobada), US-208 (rollback aprobado), US-305 (decisión de cumplimiento sobre un modelo
congelado).

**Ya decidido** (no se pregunta):
- tipos `ServingConfig`, `PolicyDraft`, `NormativeParams` y `PolicyVersion` (U0 §9.3); eventos del registro (`model_event`, `policy_event`, `data_source_event`, `freeze`, `frozen_resolution`) con actor, `acr` y `auth_time` (U0, U2, U3);
- `freeze` solo con la identidad de bias (`governance:freeze`); salida de `congelado` solo para `cumplimiento` con MFA (AUTONOMIA-04, X03, X04);
- K01: governance solo crea y lee Jobs en `vectra-staging`;
- promoción por PR + sync manual + `mark_active` (S3); step-up de 15 min para firmar (BR-U2-04); aprobador ≠ proponente delegado a U4 (BR-U2-02);
- `serving_config_unavailable` y `model_frozen` como causas de fail-closed (BR-U0-02).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Máquina de estados completa del modelo (Business Logic, FR-MOD-05)
El diseño aprobado tiene el camino feliz (`registrado → en_validacion →
lista_para_aprobacion → aprobado → activo → congelado → retirado`). Faltan el rechazo, el
fallo de validación, qué pasa con la versión activa anterior al activar otra (el rollback de
US-208 necesita volver a ella) y las tres acciones de cumplimiento.

A) **Transiciones**:

   | Desde | Hacia | Quién | Condición |
   |---|---|---|---|
   | — | `registrado` | `ingeniero_riesgo` (MFA) | Checksum válido (Q7) |
   | `registrado` | `en_validacion` | `ingeniero_riesgo` (MFA) | Lanza el Job (K01) |
   | `en_validacion` | `lista_para_aprobacion` | `model-validation-job` | Informe completo con sincronía OK (Q6) |
   | `en_validacion` | `validacion_fallida` | `model-validation-job` o timeout | Sincronía fallida, Job fallido o sin informe en 2 h |
   | `validacion_fallida` | `en_validacion` | `ingeniero_riesgo` (MFA) | Reintento |
   | `lista_para_aprobacion` | `aprobado` / `rechazado` | `cro` (MFA) | Con justificación si rechaza |
   | `aprobado` | `activo` | `ingeniero_riesgo` (MFA) vía `promotion-tool` `mark_active` | Tras el sync manual (Q2) |
   | `activo` | `inactivo` | Sistema, al activar otra versión | La anterior queda reactivable por rollback |
   | `inactivo` | `activo` | `ingeniero_riesgo` (MFA) vía `mark_active` | Rollback (US-208), tras el sync de revert |
   | `activo` | `congelado` | **solo** `bias-monitoring-service` | Umbral superado (U9) |
   | `congelado` | `activo` | **solo** `cumplimiento` (MFA), `reactivar` | Con justificación |
   | `congelado` | `retirado` | **solo** `cumplimiento` (MFA), `descartar` | Con justificación |
   | `congelado` | `congelado` (marca `en_investigacion`) | **solo** `cumplimiento` (MFA), `investigar` | Con justificación; después puede reactivar o descartar |
   | `inactivo`, `rechazado`, `validacion_fallida` | `retirado` | `cro` (MFA) | Retiro definitivo |

   - `retirado` y `rechazado` son terminales (salvo `rechazado → retirado`).
   - Hay como máximo **una** versión `activo` o `congelado` a la vez.

   (Recomendado)

B) Solo el camino feliz del diseño, sin `inactivo`, `rechazado` ni `validacion_fallida`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Qué hace `mark_active` y cómo se protege contra una promoción incompleta (Business Logic, US-204, FR-MOD-04)

A) `mark_active(mv_id)` cambia `serving-config` **en una transacción**: la versión nueva pasa a `activo`, la anterior a `inactivo` y se publica un `serving-config` nuevo con su `etag`. Governance **no** verifica que KServe ya sirva la versión nueva (no tiene flujo hacia KServe). La seguridad la da el fail-closed: si KServe todavía sirve la anterior, scoring recibe un `model_version_id` distinto y responde `version_mismatch` (BR-U0-02) hasta que coincidan. Una alerta `PromotionMismatchPersistent` (SEV2) salta si el desfase dura más de 10 min (recomendado)

B) `mark_active` consulta a KServe antes de cambiar `serving-config` (requiere un flujo nuevo de governance hacia `vectra-serving`)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Separación de funciones en la política (Business Rules, BR-U2-02, FR-POL-03)
En modelos y fuentes, el proponente y el aprobador tienen roles distintos. En la política,
el CRO **propone y aprueba**.

A) **Cuatro ojos**: el CRO que aprueba una política debe ser **distinto** del CRO que la propuso (comparación por `sub`); si son el mismo → `409 conflict_state`. Producción necesita al menos 2 usuarios con rol `cro` (kind y staging ya tienen 2 por rol, U2 Q11). La misma regla aplica a «quien registra ≠ quien aprueba» en modelos, aunque ahí los roles ya difieren (recomendado)

B) El mismo CRO puede proponer y aprobar, en dos acciones explícitas separadas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Activación de la política y vigencia de los parámetros normativos (Business Rules, FR-POL-02, US-206)
El tope de usura cambia con frecuencia (la Superintendencia lo certifica periódicamente).

A) Una política aprobada se activa **de inmediato** (la anterior pasa a `historica`). Dentro de la política, `normative` es una **lista con fechas** de vigencia que no se solapan (BR-U0-33): se pueden cargar por adelantado las vigencias futuras. Scoring usa el parámetro vigente a la fecha de evaluación. **Si no hay ninguno vigente**, `serving-config` lo marca y scoring responde `serving_config_unavailable` (fail-closed). Alerta `NormativeParamsExpiring` (SEV2) 15 días antes de que venza el último y SEV1 el día que vence (recomendado: nunca se evalúa con un tope de usura vencido)

B) Una sola vigencia por política; para cambiar el tope hay que aprobar una política nueva y, si vence, se sigue usando la última

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Cuánto tarda un congelamiento en tener efecto (Business Logic, S4)
scoring lee `serving-config` con una caché corta.

A) `serving-config` lleva un `etag`; scoring lo cachea como máximo **5 s**. Un congelamiento tiene efecto en ≤ 5 s y durante esa ventana todavía pueden salir recomendaciones. La ventana queda documentada como límite aceptado y medida con una prueba (recomendado: simple, sin infraestructura de notificaciones)

B) Notificación activa (push) de governance a scoring en cada cambio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Qué bloquea el paso a `lista_para_aprobacion` (Business Rules, US-202, FR-MOD-02, FR-BIA-07/08)

A) **Bloquea solo la sincronía**: si el explicador no produce vectores para la versión, o produce versiones distintas, la versión va a `validacion_fallida`. El **AUC-ROC** (objetivo > 0,85 **[INTERNO]**) y la **disparidad inicial** se informan al CRO comparados con sus umbrales, pero **no** bloquean: la decisión es del CRO (P1). El informe nunca dice «sin sesgo» ni «aprobado por fairness» (FR-BIA-08) (recomendado)

B) Bloquean también un AUC bajo el objetivo y una disparidad sobre el umbral

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Formatos de artefacto permitidos y deserialización segura (Business Rules, US-201, SECURITY-13)
Los modelos de scikit-learn se guardan normalmente con `pickle`/`joblib`, que ejecuta
código al deserializar.

A) **Solo formatos sin ejecución de código**: ONNX, XGBoost JSON/UBJ y LightGBM texto. `pickle` y `joblib` se rechazan al registrar (por extensión **y** por bytes mágicos), sin deserializar. Governance verifica el checksum SHA-256 leyendo los bytes del model-store (F47). U5 (modelo de referencia) y U6 (serving) se ajustan a estos formatos (recomendado)

B) Permitir `joblib` si el artefacto viene firmado con Cosign por el pipeline del banco

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Fuentes de datos (Domain Model, US-306, FR-BIA-06)

A) `DataSource`: `ds_id`, nombre, descripción, campos que aporta (lista de `feature_id`), propietario, `proposed_by`, `state` (`propuesta → en_evaluacion → aprobada | rechazada`) y `pre_post_report_ref`.
   - Al proponer, governance pide a bias `compare_source` (F27) y pasa a `en_evaluacion`.
   - `cumplimiento` (MFA) decide **solo** si el informe antes/después existe; si no → `409`.
   - Una fuente aprobada **no** cambia el modelo activo: habilita que una versión **futura** la use (se registra en la versión con `data_sources`).

   (Recomendado)

B) Fuentes sin estado: solo un evento de aprobación en el registro

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Monitoreo de sesgo detenido (Business Rules, S4.6; NFR-RES-11)
`services.md` S4.6 dejó abierto qué le pasa al modelo si el último cálculo de disparidad es
demasiado viejo.

A) **Solo alerta, con escalamiento**: `MonitoreoSesgoDetenido` SEV2 al pasar W (la ventana de U9) y SEV1 al pasar 2W. El modelo **sigue sirviendo**: que no se mida no prueba que haya disparidad, y congelar automáticamente sin medición sería una decisión que el monitoreo no puede sostener (P4: el monitoreo mide, no certifica). `serving-config` incluye `bias_monitoring_age_s` para que la consola lo muestre. No se agrega una ruta de congelamiento manual (recomendado)

B) Congelamiento automático al pasar 2W sin cálculo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el contexto (unit-of-work, historias, C09/C10/C18, S3–S5, tipos de U0, K01, X03, X04)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/governance/functional-design/domain-entities.md`
- [x] 4. Generar `construction/governance/functional-design/business-rules.md`
- [x] 5. Generar `construction/governance/functional-design/business-logic-model.md` (máquinas de estado, flujos, PBT incluida la stateful)
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
