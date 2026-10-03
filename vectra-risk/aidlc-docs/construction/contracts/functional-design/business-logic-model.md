# Modelo de lógica — U0 `contracts`

U0 no tiene servicio propio. Su lógica vive en funciones puras y middleware que usan
todas las unidades.

## 1. Módulos lógicos

| Módulo | Paquete | Responsabilidad | Reglas |
|---|---|---|---|
| `outcome` | `vectra_contracts` | `check_preconditions` y `build_outcome`: invariante de sincronía en dos fases sobre la tabla de 10 causas; cuantización de la predicción | BR-U0-01..08 |
| `finance` | `vectra_contracts` | Tasa mensual, cuota, cuota/ingreso, LTV, cuantización y representación JSON de decimales | BR-U0-10..15 |
| `validation` | `vectra_contracts` | Validadores de `ApplicationIn`, `DecisionIn`, `PolicyDraft`, `FeatureValue` y del resto de las entradas | BR-U0-20..36, 95 |
| `labels` | `vectra_contracts` | `derive_monitoring_labels(application, evaluated_at)` | BR-U0-40..43 |
| `dictionary` | `vectra_contracts` | `covers(dictionary, shap_vector)` | BR-U0-80..81 |
| `logging` | `vectra_common` | Logger JSON con allowlist | BR-U0-50..53 |
| `errors` | `vectra_common` | Handler global y fábrica de `Problem` | BR-U0-60..62 |
| `authz` | `vectra_common` | Validación de JWT, scopes, roles, MFA y métrica de denegaciones | BR-U0-70..73 |
| `telemetry` | `vectra_common` | Propagación de `traceparent` y configuración del exportador OTLP (solo destino in-cluster, F61) | BR-U0-62 |
| `compat` | herramienta de CI | Diferencia de OpenAPI contra la versión publicada | BR-U0-90..92 |

## 2. Flujos

### 2.1 Pipeline de un request en cualquier servicio (orden fijo)

```text
request
  -> telemetry: extraer/crear traceparent, correlation_id
  -> authz: validar token (BR-U0-70) -> scopes/roles (71) -> MFA (72)
       fallo -> Problem 401/403 + log authz.denied + métrica (73)
  -> validation: JSON y content-type (BR-U0-31) -> Problem 400/415
                esquema de entrada (BR-U0-20..34) -> Problem 422 (sin valores)
  -> handler del servicio
  -> errors: toda excepción no controlada -> Problem 500 genérico (60)
  -> logging: un LogRecord de acceso (allowlist)
response (+ correlation_id)
```

### 2.2 `check_preconditions` y `build_outcome` (los usa U7)

```text
check_preconditions(serving_state, requested_model_version_id, serving_model_version_id?,
                    prediction?, policy_result?, explicador?, dictionary?)   (versiones: U8 FD Q1)
  1. recorrer las causas 1..9 de BR-U0-02 en orden
  2. la primera que aplique -> FailClosed(cause, status, retryable)       (BR-U0-03, 04)
  3. si ninguna aplica      -> Ready (única rama que lo construye)

scoring: append(entrada recommendation construida solo desde Ready)      (BR-U0-08)

build_outcome(ready, registro?)
  4. causa 10 aplica        -> FailClosed(registry_unavailable, retryable=true)
  5. si no                  -> Recommendation(kind="recommendation", ...) (única rama)

salida: RecommendResult; scoring la devuelve siempre con HTTP 200        (BR-U0-06)
```

Una dependencia que no se invocó se pasa ausente (S2). Si la lectura de `serving-config`
falla, scoring llama igual a `check_preconditions` con `serving_state = no_disponible`:
la decisión de fail-closed también pasa por la fábrica.

### 2.3 Derivación de features y etiquetas (la usan U8 al ingerir y U5 al sintetizar)

Firma, precisada el 2026-10-03 por U5 FD (BR-U5 §7): `derive(application, evaluated_at,
feature_spec)`. Además de las features estándar, aplica las **búsquedas** del
`feature_spec.json` de la versión activa (tablas incluidas en el paquete), solo sobre campos
permitidos de `ApplicationIn`. El resultado de una búsqueda es una feature nueva (p. ej.
`zona_vivienda`); el campo de origen nunca pasa al `FeatureVector` si es de identificación
(BR-U0-34), y `free_text` nunca se usa. Las mismas entradas dan las mismas features en U5 y
en U8.

```text
ApplicationIn + evaluated_at
  -> finance: installment_cop, installment_to_income, loan_to_value
  -> labels: rango_edad, region (tabla DANE->región), banda (BR-U0-42), sexo, estrato
  -> FeatureVector base (sin identificadores ni free_text)
```

U8 y U5 usan la **misma** función. Así, el modelo se entrena y se sirve con las mismas
derivaciones.

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U0-01 | `outcome` | La composición `check_preconditions` → `build_outcome` devuelve `Recommendation` ⇔ no aplica ninguna de las 10 causas de BR-U0-02; si aplica alguna, `cause` es la de menor número, `status = modelo_congelado` ⇔ `cause = model_frozen` y `retryable = false` ⇔ `cause = model_frozen`. Además, los campos de la `Recommendation` son idénticos a los del `Ready` del que sale | Invariante + oráculo (implementación de referencia por tabla de verdad) | Producto de `serving_state` (3), presencia o ausencia de cada dependencia, salida de KServe válida o inválida, `explanation` o cada `ExplainerError` (6), versión de explicación y de diccionario igual o distinta, versión pedida igual o distinta de la de `serving-config` (U8 FD Q1), cobertura del diccionario, ack, `RegistryError` o ausente |
| PBT-U0-02 | todos los tipos | `parse(serialize(x)) == x` para cada tipo del contrato, serializando a JSON con las reglas de BR-U0-15 (decimales como cadena, `FeatureValue` discriminado, `RecommendResult` por `kind`) | Round-trip | Un generador por tipo de dominio, con restricciones de negocio; decimales con 0 y con 28 dígitos significativos |
| PBT-U0-03 | `finance` | La cuota coincide con un oráculo de alta precisión (`Decimal` a 50 dígitos) con error ≤ 1 peso | Oráculo | Montos 1..10¹², plazos 12..360, tasas 0.0001..0.9999 |
| PBT-U0-04 | `finance` | La cuota es monótona no decreciente en monto y en tasa, y no creciente en plazo | Invariante | Pares de solicitudes que difieren en un solo campo |
| PBT-U0-05 | `finance` | `quantize(quantize(x)) == quantize(x)` | Idempotencia | Decimales arbitrarios |
| PBT-U0-06 | `labels` | La derivación es total: toda edad de 18 a 120 cae en exactamente un rango; los 33 departamentos tienen región; la banda es monótona en `installment_to_income` | Invariante | Edades en el rango y en sus bordes, códigos DANE, ratios cerca de 0.2 y 0.3 |
| PBT-U0-07 | `logging` | Para cualquier diccionario de campos que incluya PII generada, la salida solo contiene claves de la allowlist y ningún valor de PII generado aparece en la cadena emitida | Invariante | Solicitudes realistas y campos extra arbitrarios |
| PBT-U0-08 | `errors` | Para cualquier excepción, la respuesta es un `Problem` con solo los campos permitidos y un `code` del catálogo | Invariante | Tipos de excepción y mensajes arbitrarios (con PII) |
| PBT-U0-09 | `authz` | `authorize(p, ep) == (ep.scopes ⊆ p.scopes) ∧ (ep.roles = ∅ ∨ ep.roles ∩ p.roles ≠ ∅) ∧ (¬ep.mfa ∨ (p.acr = "mfa" ∧ now − p.auth_time ≤ ep.mfa_max_age))` (BR-U0-71, 72), incluidos los bordes de 900 s | Oráculo (operación de conjuntos) | Subconjuntos del catálogo de scopes y roles, con y sin MFA |
| PBT-U0-10 | `dictionary` | `covers(d, v)` es falso ⇔ existe un `feature_id` en `v` ausente de `d` | Invariante | Diccionarios y vectores con solapamiento parcial |
| PBT-U0-11 | `validation` | Toda `ApplicationIn` generada válida pasa; toda mutación de un campo fuera de rango falla con `validation_error` y la respuesta no contiene el valor mutado | Invariante | Generador de solicitudes válidas + mutadores por regla |
| PBT-U0-12 | `outcome` | Para todo `float` de KServe: si es finito y está en [0, 1], la cuantización da un `Decimal4` en [0, 1] y es monótona no decreciente; si no, el resultado es `FailClosed(model_output_invalid)` | Invariante | Flotantes arbitrarios, incluidos `NaN`, `±inf`, `-0.0`, subnormales y valores junto a 0 y 1 |
| PBT-U0-13 | `validation` | Ningún `RegistryEntryIn` ni `FeatureVector` con una clave de identificación de §1.1 o `free_text` pasa la validación (BR-U0-34, 95) | Invariante | Payloads válidos con claves prohibidas inyectadas en cualquier nivel |

**PBT-06 (stateful):** N/A. U0 no tiene componentes con estado mutable. Las máquinas de
estado del caso y del modelo están en U8 y U4.

**Pruebas de ejemplo obligatorias (PBT-10):**
- tabla de verdad completa de `build_outcome` con casos nombrados, uno por cada causa y uno por cada par de causas simultáneas que prueba la precedencia;
- respuesta 200 con `kind = fail_closed` en `POST /v1/recommendations`;
- `feature_vector_hash` de un vector conocido, recalculado con JCS;
- matriz de `DecisionIn` contra cada `outcome` de la recomendación (BR-U0-35);
- cuota de un crédito conocido calculada a mano;
- log con PII real de ejemplo → ausente en la salida;
- 400, 401, 403, `mfa_required`, 415 y 422 con respuestas exactas.

## 4. Cumplimiento de extensiones (Functional Design U0)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-06 | Cumple | BR-U0-01..08: dos funciones puras sobre una sola tabla de 10 causas; solo `check_preconditions` construye `Ready` y solo `build_outcome` construye `Recommendation`; lo registrado es exactamente lo entregado; PBT-U0-01, PBT-U0-12 |
| AUTONOMIA-05 | Cumple | BR-U0-50..53 (allowlist); telemetría solo in-cluster; PBT-U0-07 |
| AUTONOMIA-03 / 04 | Cumple | Catálogo de scopes sin permisos de escritura sobre crédito; `model_frozen` no reintentable (BR-U0-04) |
| AUTONOMIA-01 / 02 | N/A | Aplican a los planes de tareas |
| SECURITY-03 | Cumple | Logging estructurado con correlación (BR-U0-62) y sin PII; PBT-U0-07 |
| SECURITY-05 | Cumple | BR-U0-15, BR-U0-20..34; PBT-U0-11, PBT-U0-13 |
| SECURITY-08 | Cumple | BR-U0-70..72, con deny by default para endpoints sin requisitos declarados; PBT-U0-09 |
| SECURITY-14 | Cumple | BR-U0-73: log `authz.denied` con `principal_subject` y métrica de denegaciones |
| SECURITY-15 | Cumple | BR-U0-60..62, fábrica fail-closed |
| SECURITY-01/02/04/06/07/09/10/11/12/13 | N/A en esta unidad y etapa | Son de infraestructura, borde, CI o identidad (U1 y U2) |
| PBT-01 | Cumple | §3: propiedades identificadas por componente, con categoría |
| PBT-06 | N/A | Sin componentes con estado |
| RESILIENCY-* | N/A | U0 no tiene runtime |
