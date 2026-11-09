# Precisiones antes del Bloque D de U4 `governance`

**Estado: PENDIENTE DE APROBACIÓN del usuario** (orquestador, 2026-11-09).

Precisa P-U4-06, BR-U4-03 y BR-U4-17, y el reparto del Bloque D. Recoge las candidatas F-03, F-04 y F-05 de U04-T01 (`CANDIDATAS.md`, revisor, ronda 1) y la pregunta P-1 de `demo-recorte-funcional.md`, que la enmienda dejó abierta para U4 US-306. No cambia ningún otro BR, NFR ni INF de U4.

Rutas relativas a `vectra-risk/`.

## 1. `guard_unfreeze` deja salir de `congelado` por `inactivo` (F-03)

**Hoy.** El trigger de la migración `0001` (`governance/migrations/versions/0001_governance_schema.py`) solo actúa cuando `NEW.state IN ('activo','retirado')`. `gov_app` tiene `UPDATE (state)`, y el `CHECK` admite `inactivo`. Por eso un `UPDATE … SET state = 'inactivo'` desde `congelado` pasa sin resolución, y después `inactivo → activo` tampoco lo vigila el trigger. Es una reactivación en dos pasos sin cumplimiento.

El código copió P-U4-06 al pie de la letra; el hueco es del diseño. Las otras barreras sí lo cubren:
- `model_fsm` (U04-T02) rechaza `congelado → inactivo`, porque no está en BR-U4-01;
- el endpoint solo deja pasar a `cumplimiento`.

Pero el trigger es la «cuarta barrera» de P-U4-06, y debe sostenerse sola.

**Precisión propuesta (Q-1).** `guard_unfreeze` rechaza **toda** actualización con `OLD.state = 'congelado'` y `NEW.state IS DISTINCT FROM OLD.state`, salvo que:
- `NEW.state` sea `activo` o `retirado`, **y**
- exista la `frozen_resolution` confirmada de cumplimiento con `to_state = NEW.state`.

Cualquier otro destino (`inactivo`, `aprobado`, etc.) se rechaza siempre, con o sin variable. La tabla de P-U4-06 cambia así:

| Trigger | Rechaza | Salvo que |
|---|---|---|
| `guard_unfreeze` | Todo `UPDATE model_versions` que saque una versión de `congelado`, y todo cambio de `investigation` | La salida sea a `activo` o `retirado` **y** exista la `frozen_resolution` de §P-U4-06 con `to_state` igual al estado nuevo. Para `investigation`, ver Q-2 |

**Q-2, `investigation`.** Hoy solo se vigila si `OLD.state = 'congelado'`. Fuera de `congelado`, BR-U4-01 no tiene ninguna fila que la cambie. Propuesta:
- `investigation` solo puede cambiar de `false` a `true`, en una versión `congelado` que sigue `congelado`, con la resolución `investigar`;
- cualquier otro cambio, en cualquier estado, se rechaza;
- `reactivar` y `descartar` no la tocan: queda como marca histórica de que la versión estuvo en investigación.

**Dónde se aplica.** Una migración `0004` que reemplaza la función, con sus pruebas en `test_migrations.py`, en la tarea U04-T03 (§4).

## 2. La llave UUIDv5 (F-04)

BR-U4-17 dice «`UUIDv5(entity_type:entity_id, n)`», pero no fija ni el namespace ni cómo se compone el nombre. U3 ya tiene su convención: `uuid5(NAMESPACE_URL, "urn:vectra:decision-registry:genesis")` (`decision-registry/migrations/versions/0001_registry_entries.py`).

**Precisión propuesta (Q-3).**

```
idempotency_key = uuid5(NAMESPACE_URL, f"urn:vectra:governance:{entity_type}:{entity_id}:{n}")
```

Se escribe así en BR-U4-17 y en domain-entities §1.3. La calcula el servicio (Paso 8) en una sola función, que importan el servicio y las pruebas. `test_migrations.py` deja de usar su fórmula propia (líneas 18–20) e importa esa función.

## 3. `NOTIFY` en cualquier `UPDATE` (F-05)

Hoy `notify_serving_config` notifica en todo `UPDATE` de `serving_config`, y con `etag` nulo manda un payload vacío. El Paso 9 (convergencia) depende de esa señal.

**Precisión propuesta (Q-4).** El trigger se dispara con `WHEN (NEW.etag IS DISTINCT FROM OLD.etag)` y nunca notifica con payload vacío. Entra en la misma migración `0004`.

## 4. Reparto del Bloque D (Q-5)

La enmienda deja el Bloque D (Pasos 8–11) como una sola tarea. También lo marca como el bloque de U4 que más riesgo tiene de pasar de 2 rondas (§4: dos PBT stateful y convergencia con 2 réplicas), y lista «U4 a 7» como alternativa conservadora.

**Propuesta.** Partirlo en dos tareas:
- **U04-T03 = Pasos 8 y 9**, más la migración `0004` de §1 y §3: evidencia en dos fases, reconciliador, barridos, PBT-U4-01 y 07, convergencia y pools;
- **U04-T04 = Pasos 10 y 11**: endpoints y resumen.

U4 pasa de 6 a 7 tareas. El orden de dependencias no cambia, porque el Paso 10 usa las operaciones del Paso 8.

## 5. P-1 para U4 US-306 (Q-6, solo afecta a U04-T04)

De las 21 rutas de `governance-service` en el registro de U0, cinco son de US-306:
- `GET` y `POST /v1/data-sources`;
- `POST /v1/data-sources/{id}/comparisons`;
- `PUT /v1/validation-runs/{run_id}/source-counts`;
- `POST /v1/data-sources/{id}/decision`.

`create_app` exige su handler. La enmienda dejó abierto elegir entre (a) implementarlas y (b) un stub con un código nuevo `not_implemented` en U0.

| Opción | Qué implica |
|---|---|
| **(a) Implementarlas en el servicio** | Los handlers son finos: alta y lista de fuentes, condiciones de BR-U4-13 con sus 409, guardar los conteos, cliente F25 hacia U9 (`/v1/source-comparisons`, que U9 implementa igual porque `create_app` lo exige) y decisión con su 409 sin informe. El lanzador del Job ya existe por la validación; `mode` es un parámetro. **Siguen diferidos** el modo `source_comparison` del `model-validation-job` (Paso 13) y la rama `source_comparison` del barrido. Entran las líneas de aceptación de esas rutas en el Paso 10 |
| (b) Stub con `not_implemented` | Cambia U0: `ProblemCode`, OpenAPI y tipos TS. El BFF (U10) hereda el stub en sus rutas de paso, y PBT-U10-01 tiene que saberlo |

**Recomendación: (a).** No toca U0, el contrato queda honesto y el costo está en el servicio, no en tres unidades.

## 6. Preguntas

| Id | Pregunta | Recomendación |
|---|---|---|
| Q-1 | `guard_unfreeze` rechaza toda salida de `congelado` salvo a `activo`/`retirado` con resolución | Sí |
| Q-2 | `investigation` solo `false → true` en `congelado` con `investigar`; marca histórica | Sí |
| Q-3 | Llave `uuid5(NAMESPACE_URL, "urn:vectra:governance:{entity_type}:{entity_id}:{n}")` | Sí |
| Q-4 | `NOTIFY` solo si cambia el `etag`, nunca con payload vacío | Sí |
| Q-5 | Bloque D en dos tareas (8–9 y 10–11); U4 a 7 tareas | Sí |
| Q-6 | P-1 para U4 US-306 | (a) |

Al aprobarse:
- se actualizan P-U4-06, BR-U4-17 y domain-entities §1.3;
- en `CANDIDATAS.md`, F-03, F-04 y F-05 de U04-T01 se marcan como resueltas por este documento;
- se registra en `aidlc-docs/audit.md`.
