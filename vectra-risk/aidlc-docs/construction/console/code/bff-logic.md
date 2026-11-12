# Lógica pura del BFF de `console` (U10, Pasos 1 a 4)

Resumen de `console/bff/src/console_bff/{config,object_rules,errors}.py`, escrito en U10-T01.
Los tres módulos son puros: no hacen E/S, no importan `httpx` ni `vectra_common.deps` y `config` no importa `os`
(contratos de `console/bff/.importlinter`, NFR-U10-64). Cobertura de ramas del 100 % en `object_rules` y `errors`
(NFR-U10-60); `mutmut` queda diferido por la demo (T3, enmienda §3 de U10, fila «4 · 16»).

## 1. `object_rules` (BR-U10-01; P-U10-01; PBT-U10-02)

Cada función recibe el **estado** que devolvió el destino y responde `ObjectVerdict`: `ACCEPT` (200), `FORBIDDEN`
(403) o `CONFLICT` (409). Una discrepancia de estado es 409. El 403 de objeto existe en el tipo por P-U10-01, pero
ninguna regla de estado de C03 lo produce.

| Función | Fila de C03 (columna «Objeto») | Entradas | Acepta cuando |
|---|---|---|---|
| `record_explanation_view` | «Casos», `record_explanation_view` | `CaseState` | `listo` o `decidido` |
| `record_decision` | «Casos», `record_decision` | `CaseState` | `listo` |
| `create_applicant_summary` | «Casos», `create_applicant_summary` | `CaseState`, `FinalOutcome \| None` | `decidido` y `desfavorable` |
| `retry_case` | «Casos», `retry_case` | `CaseState`, `anonymized` | `no_disponible` y no anonimizado |
| `start_validation` | «Modelos», `start_validation` | `ModelState` | `registrado` o `validacion_fallida` |
| `start_source_comparison` | «Modelos», `start_source_comparison` | estado de la fuente, `ds_id`, `source_candidate_for` de la candidata, existe `activo` | fuente `en_evaluacion`, `source_candidate_for == ds_id` y existe una versión `activo` |
| `approve_model` | «Modelos», `approve_model` | `ModelState` | `lista_para_aprobacion` |
| `resolve_frozen` | «Modelos», `resolve_frozen` | `ModelState` | `congelado` |
| `retire_model` | «Modelos», `retire_model` | `ModelState` | `inactivo`, `rechazado` o `validacion_fallida` |
| `approve_policy` | «Políticas», `approve_policy` | estado de la política, decisión, `justification` | `propuesta`; `rechazada` exige `justification` no vacía |
| `decide_data_source` | «Fuentes de datos», `decide_data_source` | estado de la fuente, hay informe | `en_evaluacion` con informe |

Decisiones y límites:

- Las filas con «—» o «el caso existe» (`get_case`, `get_dossier`, `get_integrity_check`, `get_freeze`, listas y altas)
  no llevan función: ese 404 lo da el destino.
- `get_case` dice «sin score si no está `listo` o `decidido`»: eso da forma a la respuesta, no acepta ni rechaza la
  acción, y es del Bloque C.
- `create_applicant_summary`: C03 añade «explicación sincronizada». Ese estado no está en `CaseDetail` como un campo de
  estado propio; lo valida U7 (BR-U7-13) y el BFF envía `recommendation_entry_id` desde el detalle (Bloque C).
- `approve_policy` sin justificación al rechazar sale 409: el contrato admite solo 403 o 409 y no es una falla de
  autorización. En la práctica `PolicyDecisionIn` ya la rechaza con 422 antes; esta rama es defensa en profundidad.
- `OBJECT_RULES` (P-3 (a)) ata cada `operation_id` de las 30 rutas del BFF a su función o a `None` declarado. Una prueba
  exige que sus claves sean exactamente los `operation_id` de `REGISTRY["console-bff"]`. Exigir la regla al arrancar
  es del Paso 5.

## 2. `errors` (BR-U10-04; P-U10-03; PBT-U10-03)

`translate_error(status, body, correlation_id) -> Problem` traduce la respuesta de error de un destino al `Problem`
de U0, con `to_problem` de `vectra_common.errors` (mismos título y estado que cualquier error del BFF):

| Entrada | Salida |
|---|---|
| cuerpo JSON con `code` de `ProblemCode` y `status` ≥ 400 | ese `code` y su estado del catálogo |
| `code` desconocido, no cadena, cuerpo vacío, no JSON, no objeto o con anidación excesiva | `internal_error` (500) |
| `status` 403 o 404 con `code` coherente con ese estado | ese `code` y ese estado (por ejemplo `mfa_required` 403) |
| `status` 403 o 404 con cuerpo malformado o `code` de otro estado | `forbidden` 403 o `not_found` 404 |
| `status` < 400 | `internal_error` |
| `reason` | se conserva solo si `REASON_ALLOWED_CODE` lo admite para el `code` |
| `invalid_params` | se conserva solo con `validation_error` y bien formado (`InvalidParam`) |
| `detail`, trazas y cualquier otro campo | nunca salen |

## 3. `config` (P-U10-04)

Constantes del código (sin variables de entorno): presupuesto de 9 s, timeouts por destino y operación, y conexiones por
réplica (case 20, governance 10, registry 5, explainability 5, bias 5; 6 réplicas dan 120, 60, 30, 30 y 30). Ningún
timeout llega a 9 s. `case.get_case_identifiers` (la lectura que usa `get_dossier`) tiene 1,5 s y comparte las 20 conexiones
de case (P-1 (a) de U10-T02, 2026-11-12; nota fechada en P-U10-04). Los umbrales del circuit breaker (20 llamadas, 50 %, 30 s,
10 s abierto) son constantes `BREAKER_*` de este módulo (NFR-U10-30).

## 4. Verificación

- `HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_object_rules.py console/bff/tests/property/test_errors.py`
- `uv run pytest console/bff/tests/unit console/bff/tests/property --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100`
