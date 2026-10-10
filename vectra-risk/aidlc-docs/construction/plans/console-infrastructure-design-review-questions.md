# Preguntas de la revisión del Infrastructure Design — U10 `console`

Revisión del 10 oct 2026, 07:57. Los hallazgos concretos ya están aplicados (ver `audit.md`).
Quedan dos puntos que no puedo resolver solo: una decisión de negocio y varios hallazgos que
llegaron sin detalle.

Escribe la letra después de cada `[Answer]:`.

## Question 1 — MFA del analista para decidir (Security; negocio)
Hoy `record_decision` (C03) **no** pide MFA: el analista decide con su sesión normal (login con
TOTP al entrar, `acr = mfa` al inicio). Las aprobaciones de modelos, políticas, fuentes y
congelamientos sí piden MFA reciente (≤ 900 s). La decisión queda en el registro con el usuario,
el rol, el `acr` y el `auth_time` del token.

A) **Mantenerlo sin step-up**: la decisión es una recomendación humana sobre un caso, no la aprobación de un artefacto que cambia el sistema. El analista decide decenas de casos por jornada, y un step-up cada 15 min la haría impracticable. El login ya exige TOTP y el registro guarda `acr` y `auth_time` como evidencia. Se documenta como decisión de negocio a confirmar por el comité (`[VERIFICAR]` con cumplimiento) (Recomendado)

B) **Step-up en `se_aparta` y `resuelve_revision`**: MFA reciente solo cuando el analista se aparta de la recomendación o resuelve una revisión (las decisiones con justificación), y no en `sigue`

C) **Step-up en toda decisión**, con `mfa_max_age` de 900 s

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Hallazgos sin detalle (U4–U8, U11, U12, [VERIFICAR])
Estos puntos llegaron solo con su nombre. No los cambié para no adivinar:

| Unidad | Hallazgo tal como llegó |
|---|---|
| U4 | «NFR-U4-31, 22 y 10» (la anotación del Job de validación sí la entendí y la apliqué: plan de U4, Paso 13) |
| U5 | «pendientes de las revisiones anteriores» |
| U6 | «staging solo con predictor; InferenceServiceNotReady» |
| U7 | «lint, etiquetas y escenarios» (agregué U7 como usuaria de la lista de frases prohibidas, BR-U0-94) |
| U8 | «concurrencia frente a la capacidad del explainer; F104» |
| U11, U12, [VERIFICAR] | «pendientes de las revisiones anteriores» |
| U1 | «KServe vectra-normal inactivo» (la parte de `minReplicas ≥ 2` frente a staging con 1 réplica sí está aplicada: NFR-U1-12) |

A) Los describo abajo, uno por línea, y los aplico en esta etapa

B) Diferirlos: cada uno se resuelve cuando se abra la etapa de su unidad (U11, U12) o se revise su plan (U4–U8), y quedan registrados como pendientes en el `audit.md`

X) Other (please describe after [Answer]: tag below)

[Answer]: B
