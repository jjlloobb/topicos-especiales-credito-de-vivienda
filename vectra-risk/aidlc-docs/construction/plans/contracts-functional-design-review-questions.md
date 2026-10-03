# Revisión del Functional Design — U0 `contracts`

**Fecha:** 2026-10-03T03:33:54Z
**Alcance revisado:** `construction/contracts/functional-design/` (domain-entities, business-rules,
business-logic-model) contrastado con `component-methods.md`, `component-dependency.md`,
`unit-of-work.md` y las extensiones activas (AUTONOMIA, SECURITY, RESILIENCY, PBT).

La etapa sigue esperando aprobación. Estos hallazgos se resuelven con «Request Changes»
antes de pasar a NFR Requirements.

---

## Parte A — Hallazgos

### Bloqueantes (contradicciones internas o con extensiones)

**H1 — `build_outcome` no puede decidir todas sus causas.**
- La firma de BR-U0-01 no recibe el estado del modelo (congelado), el estado de `serving-config` ni el tipo de error del explicador.
- Aun así, BR-U0-03 ordena `model_frozen`, `serving_config_unavailable`, `timeout`, `explainer_unavailable` y `explainer_error`.
- BR-U0-02 dice «Recommendation **si y solo si** se cumplen las cuatro condiciones». Con el modelo congelado y las cuatro condiciones cumplidas, BR-U0-02 devuelve `Recommendation` y BR-U0-03 devuelve `FailClosed`.
- PBT-U0-01 hereda esa contradicción, así que el oráculo de la tabla de verdad no está bien definido.
- Afecta a AUTONOMIA-06, que es bloqueante.

**H2 — `FailClosed`: ¿cuerpo tipificado o error 503?**
- `component-methods.md` define `recommend() -> Recommendation | FailClosed` como «respuesta tipificada».
- domain-entities §6 define además el `code` `fail_closed` con status 503 para las APIs internas.
- Así hay dos formas de transportar el mismo resultado, y U7 y U8 no sabrían cuál implementar.

**H3 — `score` y `confidence` siguen como `float`.**
- domain-entities §3.3 hereda los campos de `component-methods.md`, donde son `float`.
- Q8=A prohíbe el punto flotante binario en las reglas de política. `apply_policy` compara `score` contra el punto de corte, que es una regla de política.

### Importantes (huecos que bloquearán unidades posteriores)

**H4 — Faltan tipos del contrato.** U0 promete el OpenAPI de todas las APIs, pero el FD no
define `ScoringRequest`, `ExplainRequest`, `Prediction`, `PolicyResult`/`Outcome`,
`RegistryAck`, `DecisionIn`, `ApplicantSummary`, `ServingConfig` ni `PolicyVersion` (con los
parámetros VIS y usura con vigencia). `build_outcome` usa `prediction`, `policy_result` y
`registry_ack` sin que estén definidos.

**H5 — No está definida la representación JSON de los `Decimal`.**
- Q8 fija `Decimal4`, pero no dice si en JSON va como número o como cadena.
- Con número, el cliente TypeScript pierde precisión y PBT-U0-02 (round-trip) puede fallar.
- La unión `Decimal | int | str` de `FeatureVector.features` también es ambigua al deserializar.

**H6 — Divergencia con artefactos de INCEPTION ya aprobados.**
- El FD amplía el catálogo `FailClosed.cause` de 7 a 9 valores, con `feature_dictionary_incomplete` y `serving_config_unavailable`.
- También añade `base_value` y `feature_dictionary_version` a `Explanation`.
- `component-methods.md` no se actualizó. Por otro lado, el flujo F08 sí se agregó a `component-dependency.md`, que estaba aprobado.
- Hace falta decidir qué documento manda y dejar constancia de esos cambios.

### Menores (los corrijo sin preguntar al aplicar los cambios)

- **M1**: BR-U0-62 no aclara si `correlation_id` es el mismo `trace_id` o un ID distinto. `LogRecord` tiene los dos.
- **M2**: BR-U0-71 no dice qué pasa si un endpoint declara roles **y** scopes a la vez. Propongo exigir los dos (AND).
- **M3**: falta un `code` para JSON malformado o un content-type no soportado (400/415). Propongo `malformed_request`.
- **M4**: el log `authz.denied` no identifica al principal. Sin eso no se puede alertar por fallos repetidos del mismo sujeto (SECURITY-14). Propongo `principal_subject`, que es el `sub` opaco de Keycloak, no PII.
- **M5**: PBT-U0-01 tiene que redefinirse según cómo se resuelva H1.

### Higiene del repositorio (no son del FD)

- Hay copias `*original.md` en `inception/plans/` y `construction/plans/`, que no forman parte de la estructura AI-DLC. Se pueden borrar o mover fuera de `aidlc-docs/`. No las toco sin tu orden.
- Hay un archivo swap de vim, `.aidlc-rule-details/extensions/autonomia/limite/.limite-autonomia.md.swp`. Indica una edición abierta o interrumpida de una regla bloqueante, así que conviene revisar que `limite-autonomia.md` quedó como esperas.

---

## Parte B — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1
¿Cómo se resuelve H1 (entradas y causas de `build_outcome`)?

A) `build_outcome` recibe explícitamente `serving_state` (`activo` \| `congelado` \| `no_disponible`) y un error tipificado del explicador (`timeout` \| `unavailable` \| `error`). BR-U0-02 se reescribe como «Recommendation ⇔ ninguna de las 9 causas aplica», y la tabla de verdad cubre todas (recomendado: una sola función decide todo y es testeable de punta a punta)

B) Las causas previas a la predicción (`model_frozen`, `serving_config_unavailable`) se verifican en scoring **antes** de llamar a `build_outcome`, que solo evalúa las 7 restantes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
¿Cómo viaja `FailClosed` en las APIs internas (H2)?

A) Como **200 con cuerpo tipificado**: unión discriminada por `kind` (`recommendation` \| `fail_closed`). Se elimina el `code` `fail_closed` del catálogo de `Problem`; los 503 quedan solo para `dependency_unavailable` (recomendado: es un resultado de negocio esperado, no un error de transporte)

B) Como **503 `Problem`** con `code=fail_closed` y los campos de `FailClosed` como extensión del problema

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3
¿Qué tipo tienen `score` y `confidence` en el contrato (H3)?

A) `Decimal4` en [0, 1]. scoring cuantiza la salida flotante de KServe en la frontera, antes de aplicar la política. La cuantización usa BR-U0-14 y se registra el valor ya cuantizado (recomendado)

B) `float`, con la comparación contra el punto de corte hecha en `Decimal` dentro de `apply_policy`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
¿Dónde se definen los tipos que faltan (H4)?

A) En el FD de U0 ahora: forma de los campos, validaciones y dueño de cada tipo. Las unidades dueñas (U4, U7, U8) solo detallan su comportamiento (recomendado: U0 existe para fijar contratos primero)

B) Cada unidad dueña define sus tipos en su propio FD y U0 los incorpora después con un bump de versión

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
¿Cómo se serializan los decimales en JSON (H5)?

A) Montos `COP` como entero JSON (≤ 10¹² < 2⁵³, sin pérdida). `Decimal4` y `Decimal` como **cadena** con patrón (`^-?\d+\.\d{4}$` para `Decimal4`). Los valores de `FeatureVector` como objeto `{type, value}` para eliminar la ambigüedad de la unión (recomendado)

B) Todo como número JSON, aceptando la conversión en el cliente TS

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6
¿Qué documento manda cuando el FD de U0 amplía un tipo de INCEPTION (H6)?

A) El FD de U0 es la fuente autoritativa de los contratos. En `component-methods.md` se añade una nota que remite a U0, y los cambios (9 causas, campos nuevos de `Explanation`, F08) se registran en audit.md como cambio a un artefacto aprobado (recomendado)

B) Se actualiza también `component-methods.md` para que los dos documentos digan lo mismo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7
El registro inmutable guarda `feature_vector`, `monitoring_labels` y `case_id`. Son datos
**seudonimizados**: siguen siendo datos personales y no se pueden borrar. ¿Cómo se trata?

A) Se mantiene el diseño (Q4=A), se documenta explícitamente como dato seudonimizado y se marca **[VERIFICAR]** con cumplimiento la compatibilidad con la Ley 1581 de 2012 (supresión y retención). La decisión final queda para el NFR de U3 (recomendado)

B) Se agrega ya un requisito: el `feature_vector` del registro se cifra con una llave por caso. Así, «borrar» equivale a destruir la llave (crypto-shredding) sin romper la cadena de hashes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
Las regiones Insular y Amazonía tendrán muestras muy pequeñas, que es justo lo que Q3
quería evitar. ¿Qué se hace?

A) Se mantienen las 6 regiones en U0. La regla de muestra mínima (no calcular disparidad bajo un n mínimo y reportarlo como «muestra insuficiente») se fija en el FD de U9 (recomendado: U0 define la etiqueta y U9 decide cómo se usa)

B) Se fusionan Insular con Caribe y Amazonía con Orinoquía en la tabla de U0

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte C — Resolución (Q1–Q8 = A)

- [x] H1 → BR-U0-01..03 reescritas: `build_outcome` recibe `serving_state`, `ExplainerError` y `RegistryError`, y decide las 9 causas; PBT-U0-01 redefinida
- [x] H2 → BR-U0-06 y domain-entities §3.5: `RecommendResult` en 200, discriminado por `kind`; se elimina el `code` `fail_closed`
- [x] H3 → BR-U0-07: `score`/`confidence` como `Decimal4`, cuantizados en la frontera; PBT-U0-12
- [x] H4 → domain-entities §3.6 y §9: `Prediction`, `PolicyResult`, `ReasonCode`, `RegistryAck`, `ScoringRequest`, `PolicyInputs`, `ExplainRequest`, `ApplicantSummary`, `DecisionIn`, `DecisionRef`, `ServingConfig`, `PolicyDraft`, `NormativeParams`, `PolicyVersion`; BR-U0-32..34
- [x] H5 → BR-U0-15: decimales como cadena, `FeatureValue` discriminado; PBT-U0-02 ampliada
- [x] H6 → BR-U0-93 y nota en `component-methods.md` que remite a U0; cambios registrados en audit.md
- [x] Q7 → domain-entities §5.4 y BR-U0-95 (seudonimización, [VERIFICAR] Ley 1581, decisión en NFR de U3); PBT-U0-13
- [x] Q8 → nota en domain-entities §2.2: muestra mínima en el FD de U9
- [x] M1 → BR-U0-62: `correlation_id` = `trace-id` W3C; se quita `trace_id` duplicado de `LogRecord`
- [x] M2 → BR-U0-71: scopes como subconjunto **y** roles como intersección (un endpoint con «analista, cro» acepta cualquiera de los dos); deny by default sin requisitos declarados; PBT-U0-09 ajustada
- [x] M3 → `malformed_request` (400) y `unsupported_media_type` (415); BR-U0-31
- [x] M4 → `principal_subject` en `LogRecord` y en BR-U0-73 (no como etiqueta de métrica)
- [x] M5 → incluido en H1
