# Resumen de la lógica pura — U4 `governance`

Bloque C del plan (Pasos 3 a 6). Los cuatro módulos son funciones puras: el contrato `pure-no-io` de import-linter
(`governance/.importlinter`) les prohíbe base de datos, red, archivos, procesos, `asyncio` y `vectra_common`. Ninguno lee
el reloj: el instante entra como parámetro.

| Reglas | Archivo | Pruebas |
|---|---|---|
| BR-U4-01, 02, 04, 10 (tabla de transiciones, una sola versión servible, bias solo congela, cuatro ojos del modelo) | `src/vectra_governance/model_fsm.py` (`transition`, `Actor`, `ModelContext`, `Forbidden`, `ConflictState`, `TRANSITIONS`, `ACTORS`) | `tests/property/test_model_fsm.py` (PBT-U4-02; US-203, US-305) |
| BR-U4-10, 11 (cuatro ojos de la política, activación y vigencia; BR-U0-33; P-U4-05) | `src/vectra_governance/policy.py` (`validate_normative`, `normative_at`, `bogota_date`, `normative_current`, `check_four_eyes`, `approve_policy`) | `tests/property/test_policy.py` (PBT-U4-03, 04; US-205, US-206; reloj simulado de la medianoche de Bogotá) |
| BR-U4-11, 14 (composición y `etag` de `serving-config`; P-U4-07) | `src/vectra_governance/serving_config.py` (`compose`, `compute_etag`) | `tests/property/test_serving_config.py` (PBT-U4-05) |
| BR-U4-06 (registrar sin deserializar) | `src/vectra_governance/registration.py` (`validate_registration`, `VerifiedPackage`, `RegistrationRejected`, `has_executable_magic`) | `tests/property/test_registration.py` (PBT-U4-06; US-201; RT3-a, c, d) |

## Qué hace cada módulo

- **`model_fsm`**. `transition(state, action, actor, context)` devuelve el estado nuevo o **lanza** `Forbidden` (403) o
  `ConflictState` (409). Tiene la tabla de BR-U4-01 completa, incluidas las filas de US-306 (la candidata de una fuente
  no se aprueba ni se activa mientras la fuente no esté `aprobada`). Orden de comprobación: actor (rol, identidad de
  servicio o sistema, y MFA) → estado → contexto (cuatro ojos, fuente, otra versión `congelado`). `congelado → inactivo`
  no existe. El oráculo de PBT-U4-02 es una tabla escrita aparte en la prueba.
- **`policy`**. La validación de la lista normativa es la de U0 (`PolicyDraft`); `normative_at` sigue domain-entities §3.2;
  la fecha es la de `America/Bogota` (UTC−5), y el cambio de vigencia ocurre a las 00:00 de Bogotá (05:00 UTC), no a las
  19:00 de Bogotá (00:00 UTC). `approve_policy` devuelve los dos cambios de estado de la activación como una sola unidad.
- **`serving_config`**. `compose` devuelve el `ServingConfig` de U0, solo con sus campos; el `etag` es el SHA-256 del JCS
  de todos los campos menos el propio `etag`, incluido `inference_service`. Sin versión servible o sin política `activa`
  devuelve `None`.
- **`registration`**. Verifica bytes: formato permitido, extensión y bytes mágicos de pickle/joblib en el manifiesto y en
  cada archivo, SHA-256 de cada archivo y del manifiesto contra lo declarado, y el mismo `model_version_id` en todos
  (RT3-a, c, d). Devuelve el `feature_dictionary` y el `feature_spec` verificados. Nunca llama a un deserializador.

## Decisiones del Bloque C (el diseño no las fija)

| Decisión | Razón |
|---|---|
| `Forbidden` y `ConflictState` se definen en `model_fsm` y `policy` los reutiliza; el Paso 10 los traduce a `vectra_common.errors` | A-1 de U04-T02: `pure-no-io` prohíbe `vectra_common` |
| `Actor(kind, id, role, acr)` propio, con `Role` de U0; el MFA es `acr == "mfa"` y la frescura del step-up es del endpoint | A-2: el tipo de U0 exige `auth_time` y usa `id` en vez de `sub` |
| Con varios fallos a la vez, gana el actor (`Forbidden`) | Un actor sin permiso no aprende el estado de la versión |
| BR-U4-10 en el modelo es `ConflictState` (409), como en la política; sin `registered_by` falla cerrado | BR-U4-10 fija 409 para la política |
| La condición de la fuente de US-306 en `mark_active` solo aplica desde `aprobado` | Es lo que dice la fila de BR-U4-01; el rollback (`inactivo → activo`) no la lleva |
| La justificación de `reject`, `reactivar`, `descartar` e `investigar` no la valida `model_fsm` | Es del endpoint y de los tipos de U0 |
| `compose` devuelve `None` si falta versión servible o política `activa` | El tipo de U0 exige las dos; qué responde la API es de los Pasos 9 y 10 |
| `registration` recibe bytes y los SHA-256 declarados; no lee el model-store | El model-store (F47) es del Paso 10 |
| Los paquetes de prueba de `registration` salen de U5 (`vectra_reference`) | Formato real del manifiesto y paquetes RT-3 |
