# Reglas de negocio — U0 `contracts`

Los IDs `BR-U0-xx` se referencian en los planes de tareas.

---

## 1. Invariante de sincronía (AUTONOMIA-06, US-111)

**BR-U0-01 — Dos fases, una sola tabla (R1, S1).** `Recommendation` no se construye
directamente. Solo existen estas dos funciones puras:

```text
check_preconditions(case_id, serving_state, requested_model_version_id,
                    serving_model_version_id?, prediction?, policy_result?,
                    explanation | ExplainerError ?, dictionary?, now)
    -> Ready | FailClosed

build_outcome(ready: Ready, registry_ack | RegistryError ?, now)
    -> Recommendation | FailClosed
```

- `check_preconditions` evalúa las causas 1–9 de BR-U0-02 y es la **única** que construye `Ready`.
- `build_outcome` solo evalúa la causa 10 y es la **única** que construye `Recommendation`.
- `requested_model_version_id` es el de `ScoringRequest` (la versión cuyo `feature_spec` armó el vector) y `serving_model_version_id` el de `serving-config` (ausente si no se pudo leer) (precisado el 2026-10-03 por U8 FD Q1).
- Los tipos de entrada están en domain-entities §3.6. Ninguna rama fuera de estas dos funciones puede producir `Ready` ni `Recommendation`.

**BR-U0-02 — Tabla de causas.** Una causa aplica cuando:

| # | Causa | Fase | Aplica si |
|---|---|---|---|
| 1 | `model_frozen` | precondiciones | `serving_state == congelado` |
| 2 | `serving_config_unavailable` | precondiciones | `serving_state == no_disponible`, o falta `prediction` o `policy_result` sin que haya discrepancia de versión pedida (causa 7) |
| 3 | `model_output_invalid` | precondiciones | la salida de KServe no es finita o está fuera de [0, 1] (BR-U0-07) |
| 4 | `timeout` | precondiciones | el explicador devolvió `ExplainerError.timeout` |
| 5 | `explainer_unavailable` | precondiciones | el explicador devolvió `ExplainerError.unavailable`, **o** falta el resultado del explicador sin que aplique una causa anterior (S2) ni haya discrepancia de versión pedida (causa 7) |
| 6 | `explainer_error` | precondiciones | el explicador devolvió `ExplainerError.error` |
| 7 | `version_mismatch` | precondiciones | el explicador devolvió `ExplainerError.version_mismatch`, o `explanation.model_version_id ≠ prediction.model_version_id`, o `dictionary.model_version_id ≠ prediction.model_version_id` (BR-U0-81), **o** `requested_model_version_id ≠ serving_model_version_id` con `serving_state == activo` (discrepancia de versión pedida: scoring no invoca a KServe ni al explicador, y esas ausencias son válidas, S2) (precisado el 2026-10-03 por U8 FD Q1) |
| 8 | `feature_dictionary_incomplete` | precondiciones | el explicador devolvió `ExplainerError.feature_dictionary_incomplete`, o falta `dictionary` sin discrepancia de versión pedida, o `covers(dictionary, explanation.shap_vector)` es falso |
| 9 | `factuality_failed` | precondiciones | el explicador devolvió `ExplainerError.factuality_failed` |
| 10 | `registry_unavailable` | registro | se recibió `RegistryError`, **o** falta el resultado del registro (S2) |

Una `Explanation` entregada siempre tiene `factuality_check == "passed"` (es un literal),
así que la factualidad fallida solo llega como `ExplainerError`.

**BR-U0-03 — Precedencia.** Si aplica más de una causa, `FailClosed.cause` es la de **menor
número**. El orden es fijo y forma parte del contrato.

**BR-U0-04 — Reintentable.** `retryable = true` para todas las causas salvo `model_frozen`,
que solo se resuelve con una acción humana (AUTONOMIA-04). El presupuesto de reintentos de
case-service termina en `no_disponible` para cualquier causa reintentable.

**BR-U0-05 — Sin respaldos.** No existe ningún parámetro, valor por defecto ni rama que
construya una `Explanation` sustituta. Las revisiones de código y la prueba PBT-U0-01 lo
verifican.

**BR-U0-06 — Transporte del resultado (R2).** `POST /v1/recommendations` responde **200**
con `RecommendResult`, discriminado por `kind`. El fail-closed nunca viaja como error
HTTP. Los 4xx y 5xx de esa ruta solo significan fallos de transporte, autenticación o
validación (`Problem`), y case-service los trata como reintentables.

**BR-U0-07 — Cuantización de la predicción (R3, S3).** scoring convierte el `score` y la
`confidence` flotantes de KServe a `Decimal4` con `ROUND_HALF_UP` **en la frontera**,
antes de aplicar la política. Esa conversión es el único punto donde existe un `float`.
La política, la `Recommendation` y el registro usan el valor cuantizado. Un valor fuera
de [0, 1] o no finito (`NaN`, `inf`) produce `model_output_invalid`, nunca un recorte
silencioso.

**BR-U0-08 — Secuencia en scoring (S1, S2).**

```text
1. leer serving-config            -> serving_state (no_disponible si falla)
2. si activo: predecir + cuantizar (BR-U0-07) + aplicar política
3. si hay prediction válida: llamar al explicador
4. check_preconditions(...)       -> FailClosed: registrar fail_closed (best effort) y responder
                                  -> Ready: seguir
5. append entrada recommendation construida SOLO desde Ready (+ evaluated_at, feature_vector_hash),
   con una idempotency_key fija por intento de evaluación (reintentos del append reusan la misma)
6. build_outcome(ready, ack | RegistryError) -> responder RecommendResult (200)
```

- Una dependencia que no se invocó se pasa **ausente**. Una ausencia solo es válida si ya aplicó una causa anterior (S2). Si no, se trata como la causa de su dependencia (5 o 10).
- La entrada `recommendation` se escribe solo con lo que contiene `Ready`, así que todo lo que se **entrega** está en el registro, exactamente como se entregó. Al revés no siempre: si el registro confirma el commit después de que scoring dejó de esperar, queda una entrada que no se entregó. Esa entrada queda identificada: `human_decision.recommendation_entry_id` apunta a la entregada y el expediente marca las demás como `no_entregada` (BR-U3-14; P-U7-03) (precisado el 2026-10-03 por U7 NFR Design Q3).
- Si el registro no responde en el paso 4, el `FailClosed` igual se entrega; la entrada `fail_closed` se reintenta con el caso. Eso significa que el **intento siguiente** del caso produce su propia entrada (BR-U7-16), no que se reintente la misma escritura. case-service no duplica las entradas por intento: escribe **una** sola entrada `fail_closed` (`retryable = false`) cuando el caso agota los reintentos (BR-U8-09) (precisado el 2026-10-03 por U8 FD Q4).

## 2. Cálculos financieros (Q8=A)

**BR-U0-10 — Tasa mensual equivalente.** `i_m = (1 + tasa_ea)^(1/12) − 1`, calculada con
`Decimal` de precisión ≥ 28 dígitos. No se usa `float`.

**BR-U0-11 — Cuota.** `cuota = monto · i_m / (1 − (1 + i_m)^(−n))`, con `n = term_months`.
Se redondea al peso con `ROUND_HALF_UP`.

**BR-U0-12 — Relación cuota/ingreso.** `installment_to_income = cuota / (monthly_income + other_income)`,
cuantizada a 4 decimales. Si el ingreso total es 0, la solicitud es **inválida**
(`validation_error`).

**BR-U0-13 — LTV.** `loan_to_value = requested_amount / property_value`, con 4 decimales.

**BR-U0-14 — Cuantización idempotente.** Toda tasa y todo cociente se cuantiza a 4
decimales. Cuantizar un valor ya cuantizado no lo cambia.

**BR-U0-15 — Representación JSON (R5).** `COP` e `int` viajan como entero JSON; `Decimal4`
y `Decimal` como cadena con el patrón de domain-entities. Un `Decimal4` recibido como
número JSON, o como cadena con más o menos de 4 decimales, es `validation_error`. Nunca
se redondea al deserializar.

## 3. Validación estructural de la solicitud

Estas reglas son de **forma**. Las reglas de **política** (punto de corte, VIS, usura)
viven en U7 y U4, no aquí.

| ID | Regla | Error |
|---|---|---|
| BR-U0-20 | Todos los campos obligatorios presentes; tipos y enumeraciones válidos | `validation_error` |
| BR-U0-21 | Longitudes máximas de §1.1 de domain-entities; payload total ≤ 32 KiB | `validation_error` / `payload_too_large` |
| BR-U0-22 | `document_number`: CC entre 5 y 10 dígitos; CE, PA y PPT alfanumérico de 5 a 15 caracteres | `validation_error` |
| BR-U0-23 | `email` con formato RFC 5322 simplificado; `phone` en E.164 o nacional de 10 dígitos | `validation_error` |
| BR-U0-24 | Edad a la fecha de evaluación entre 18 y 120 años | `validation_error` |
| BR-U0-25 | `department_code` en la tabla DANE de 33 entradas; `municipality_code` pertenece al departamento | `validation_error` |
| BR-U0-26 | Montos en COP: 0 ≤ valor ≤ 10¹²; `requested_amount` > 0; `property_value` > 0 | `validation_error` |
| BR-U0-27 | `requested_amount` ≤ `property_value` (restricción de forma; el LTV máximo es de política) | `validation_error` |
| BR-U0-28 | `proposed_rate_ea` en (0, 1) con 4 decimales exactos | `validation_error` |
| BR-U0-29 | `free_text`: se acepta cualquier Unicode imprimible hasta 2000 caracteres; se guarda **tal cual**, nunca se interpreta, nunca pasa al modelo ni al generador de narrativa y se escapa al presentarse (RT-1) | — |
| BR-U0-30 | Los errores de validación informan el nombre del campo y un `reason_code`, **nunca el valor recibido** | — |
| BR-U0-31 | Cuerpo que no es JSON válido → `malformed_request`; `Content-Type` distinto de `application/json` → `unsupported_media_type` | `malformed_request` / `unsupported_media_type` |
| BR-U0-32 | `DecisionIn.used_factors`: 1 a 20 `feature_id` sin repetir, **o** exactamente `["ninguno"]`; `"ninguno"` nunca se combina con otros valores | `validation_error` |
| BR-U0-35 | `DecisionIn` (S4): `sigue` exige `final_outcome == recommendation.outcome`; `se_aparta` exige `final_outcome ≠ recommendation.outcome`; `resuelve_revision` solo es válido si `recommendation.outcome == revision_requerida`, y `sigue`/`se_aparta` solo si es `favorable` o `desfavorable`. U0 fija la regla; la comprobación contra el caso la implementa U8, con la recomendación cuyo `registry_entry_id` guardó el caso, que es también el `recommendation_entry_id` de la entrada `human_decision` (precisado el 2026-10-03 por U7 NFR Design Q3) | `conflict_state` |
| BR-U0-33 | `PolicyDraft`: `cutoff` y `low_confidence_threshold` en [0, 1]; en cada `normative`, `effective_to`, si existe, es posterior a `effective_from`, y las vigencias de la lista no se solapan (U4 FD Q4); `channel_rules` sin canales repetidos | `validation_error` |
| BR-U0-34 | `FeatureValue`: el `value` concuerda con su `type`; las claves de `features` no incluyen campos de identificación de §1.1 ni `free_text` | `validation_error` |
| BR-U0-36 | `DecisionIn.justification`: en `se_aparta` y `resuelve_revision` es obligatoria, de 20 a 2000 caracteres después de quitar los espacios del inicio y del final; en `sigue` puede estar vacía (precisado el 2026-10-03 por U8 FD Q5) | `validation_error` |

## 4. Derivación de `MonitoringLabels` (Q3=A)

**BR-U0-40 — Edad.** Se calcula a la fecha de evaluación. Rangos cerrados por la izquierda:
`18-25`, `26-35`, `36-45`, `46-55`, `56-65`, `66+`. La función está definida para
cualquier edad válida (18–120) y cada edad cae en exactamente un rango.

**BR-U0-41 — Región.** Tabla fija de departamento DANE a región natural, con asignación
por región **predominante**.

| Región | Departamentos | # |
|---|---|---|
| Andina | Antioquia, Boyacá, Caldas, Cundinamarca, Huila, Norte de Santander, Quindío, Risaralda, Santander, Tolima, Bogotá D.C. | 11 |
| Caribe | Atlántico, Bolívar, Cesar, Córdoba, La Guajira, Magdalena, Sucre | 7 |
| Pacífica | Cauca, Chocó, Nariño, Valle del Cauca | 4 |
| Orinoquía | Arauca, Casanare, Meta, Vichada | 4 |
| Amazonía | Amazonas, Caquetá, Guainía, Guaviare, Putumayo, Vaupés | 6 |
| Insular | San Andrés, Providencia y Santa Catalina | 1 |
| **Total** | | **33** |

Varios departamentos pertenecen a más de una región natural (p. ej. Antioquia, Valle,
Cauca, Nariño). Aquí se asignan a su región predominante. **[VERIFICAR]** la convención
con el área de riesgo del cliente piloto. La tabla es un dato versionado, no código.

**BR-U0-42 — Banda de capacidad de pago.** Según `installment_to_income`:
- `lt_20` si < 0.2000;
- `20_30` si está entre 0.2000 y 0.3000, ambos incluidos;
- `gt_30` si > 0.3000.

El límite del 30 % es referencia de política para vivienda **[VERIFICAR contra la norma
vigente]**. Los límites son parámetros versionados.

**BR-U0-43 — Sexo y estrato.** Se copian tal cual. Si no vienen, van como `no_informado`.
Nunca se infieren.

## 5. Redacción de logs (Q2=A, US-604)

**BR-U0-50 — Allowlist.** El logger de `vectra_common` solo emite los campos de
`LogRecord` (domain-entities §8). Todo campo adicional se **descarta**, no se enmascara.

**BR-U0-51 — Mensaje del log.** El campo `event` es un identificador de evento del
catálogo (p. ej. `recommendation.fail_closed`). No es texto libre, así que nunca
interpola valores.

**BR-U0-52 — Excepciones.** Las excepciones se registran solo con su tipo y `error_code`.
El `str(exc)` y el stack trace **no** van a los logs agregados.

**BR-U0-53 — Sin etiquetas de monitoreo.** Las `MonitoringLabels` y cualquier campo de
§1.1 nunca se registran, ni siquiera en nivel DEBUG.

## 6. Errores (Q6=A, US-611)

**BR-U0-60 — Toda excepción se traduce.** Cualquier excepción no controlada se convierte
en `Problem` con `code = internal_error` y un `title` genérico.

**BR-U0-61 — Campos cerrados.** `Problem` solo contiene los campos de domain-entities §6.

**BR-U0-62 — Ciclo de vida del correlation ID.** El `correlation_id` **es** el `trace-id`
W3C (32 hex) de `traceparent`. No hay un segundo identificador. Si la request no trae
`traceparent` válido, se genera uno nuevo. Se propaga a toda llamada saliente y se
devuelve en la cabecera `traceparent` y en el campo `correlation_id` de `Problem`.

## 7. Autorización común (US-602)

**BR-U0-70 — Token.** Se valida en cada request: firma (JWKS de Keycloak), `exp`, `nbf`,
`iss` y que `aud` **contenga** el identificador del servicio (semántica de RFC 7519; precisado el 2026-10-03 por U2 FD Q7, porque el token de usuario que propaga el BFF lleva varias audiencias). Si falla, responde `unauthenticated`.

**BR-U0-71 — Scopes y roles.** Un endpoint declara `required_scopes`, `required_roles` o
ambos. Se autoriza **si y solo si** `required_scopes ⊆ principal.scopes` **y**
`required_roles ∩ principal.roles ≠ ∅` (un conjunto no declarado no restringe). Un
endpoint que no declara ninguno de los dos se rechaza al arrancar el servicio (deny by
default). No se usan comodines. Esta regla aplica al puerto de la API (8080). Los health
checks y `/metrics` viven en el puerto 8081, no exponen rutas de negocio y no pasan por
este middleware (`component-dependency.md` §puertos).

**BR-U0-72 — MFA y step-up.** Si un endpoint declara `mfa_required`, el principal necesita
`acr == "mfa"` **y** `now − auth_time ≤ mfa_max_age` (por defecto 900 s; precisado el
2026-10-03 por U2 FD Q3). Si no se cumple cualquiera de las dos, responde `mfa_required` y
la SPA re-autentica con `prompt=login` y `max_age=0`. Las entradas del registro que firma
un usuario en esos endpoints guardan su `acr` y su `auth_time` (domain-entities §5.1).

**BR-U0-73 — Registro de fallos.** Cada 401 o 403 emite un log con
`event=authz.denied` y `principal_subject` (si el token se pudo leer), y la métrica
`vectra_authz_denied_total{code, route_template}`, que alimenta las alertas de
SECURITY-14. `principal_subject` va en el log, **no** como etiqueta de la métrica
(evita una cardinalidad sin límite).

## 8. Diccionario de features (Q5=A)

**BR-U0-80 — Cobertura.** `covers(dictionary, shap_vector)` es verdadero si y solo si
todo `feature_id` del vector tiene una entrada. Si no, la explicación falla con
`feature_dictionary_incomplete`.

**BR-U0-81 — Pertenencia a la versión.** El diccionario pertenece a **una** versión de
modelo. Usar el diccionario de otra versión es `version_mismatch`.

## 9. Versionado (Q7=A)

**BR-U0-90 — Versión única.** El paquete de contratos tiene una sola versión SemVer
(specs, `vectra_contracts`, `vectra_common` y el cliente TS).

**BR-U0-91 — Cambio incompatible.** Si se elimina un campo, cambia de tipo o se endurece
la validación de una entrada, sube la versión mayor. El mismo PR del monorepo actualiza
a todos los consumidores.

**BR-U0-92 — Compatibilidad en CI.** CI compara el OpenAPI contra la versión anterior
publicada. Si detecta un cambio incompatible sin subir la versión mayor, el build falla.

**BR-U0-93 — Fuente autoritativa (R6).** Si un tipo de U0 difiere de `component-methods.md`,
manda U0. Las unidades dueñas detallan el comportamiento, pero no redefinen la forma de un
tipo: si necesitan cambiarla, el cambio se hace en U0 con su versión.

## 10. Datos del registro (R7)

**BR-U0-95 — Seudonimización.** Las entradas del registro solo contienen datos
seudonimizados (domain-entities §5.4). Ningún tipo de `payload` admite campos de
identificación de §1.1 ni `free_text`; la validación de `RegistryEntryIn` los rechaza con
`validation_error`. La compatibilidad con la Ley 1581 de 2012 queda **[VERIFICAR]** con
cumplimiento; resuelto en el NFR Requirements de U3 (NFR-U3-01..04, 2026-10-03).
