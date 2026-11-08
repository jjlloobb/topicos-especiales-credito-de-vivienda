# Ronda 1 — U03-T02

VEREDICTO: VERDE (bajo RL-2: no hay ROJO; dos NARANJA y varios AMARILLO van a `CANDIDATAS.md`)

Revisé el worktree en el sha `821d014`, base `3f6d645`. El blob de la tarea coincide (`0b65f4ab…`). Al terminar, el worktree está limpio (`git status` vacío).

## Criterios de aceptación, corridos por mí
| # | Comando | Resultado |
|---|---|---|
| CA-1 | `HYPOTHESIS_PROFILE=ci uv run pytest …/property/test_chain.py -v` | pasa: 5 passed en 31,9 s, 0 omitidas, perfil ci |
| CA-2 | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_verify.py …/test_verify_modes.py -v` | pasa: 36 passed en 386 s. Tardó tanto porque corría al mismo tiempo que CA-6b. Hay un caso por cada uno de los 6 motivos y por cada uno de los 4 modos |
| CA-3 | `HYPOTHESIS_PROFILE=ci uv run pytest …/property/test_projections.py -v` | pasa: 9 passed en 6,2 s |
| CA-4 | `uv run python platform/tests/test_traceability.py --unit decision-registry --section logic` | código 0 («41 identificadores»). En la base `3f6d645` también da 0 (ver F-06) |
| CA-5 | `uv run pytest …/integration/test_migrations.py -v -k "idempotency_keys or genesis"` | pasa: 35 passed, 63 deselected, en 29,9 s, con Testcontainers |
| CA-6a | `make -C decision-registry check` | pasa: ruff y `mypy --strict` limpios, `lint-imports` 1 contrato KEPT, 148 passed en **230 s** (3 min 57 s en total) |
| CA-6b | `make -C platform check` | pasa: conftest 707, 3 y 322 sin fallas, promtool 81, kyverno `pass: 45` y `pass: 309`, `fail: 0` (26 min con la máquina cargada) |

## Lo que pediste mirar
- **`canonicalize`** usa el JCS de U0: `from vectra_contracts.canonical import canonicalize as jcs` en `chain.py:15`. El módulo solo agrega `_plain`, que formatea los sellos y los UUID. No implementa un JCS propio.
- **BR-U3-12, los 6 motivos**: el código los detecta en `verify.py:211-273` y hay un caso fijo por motivo. Los modos hacen lo que dice BR-U3-11:
  - `incremental` empieza en el `from_seq` que se le pasa y comprueba el enlace con la fila anterior;
  - `full` empieza en 0;
  - `range` va de `from_seq` a `to_seq`, recortado a la cabeza;
  - `nightly` recorre todos los checkpoints (enlace, hash, firma y cubierta), re-hashea desde la cubierta del último checkpoint de hace más de 7 días y además el 1 % de los segmentos (`ceil`) con `random.Random(seed)`. La semilla es obligatoria (`ValueError` si falta), `nightly_seed(day)` da una distinta cada noche y `record_sample` entrega la semilla y los segmentos para registrarlos.
- **PBT-U3-02..06**: se ajustan a su definición en business-logic-model. PBT-U3-02 cubre cadenas de 1 a 500 entradas y las cinco manipulaciones del diseño, más una de `prev_hash`. PBT-U3-03 exige `checkpoint_mismatch` o `checkpoint_signature` en `full` y en `nightly`. Las debilidades están en F-01, F-02 y F-05.
- **La desviación `checkpoint_mismatch` en el `seq` del checkpoint es coherente con BR-U3-12.** El paso 5 es una comprobación *de la entrada checkpoint*. Si se informara la fila cubierta, una manipulación del propio checkpoint saldría en un `seq` anterior al manipulado, y eso contradice PBT-U3-02. PBT-U3-03 no fija el `seq`.
- **`projections`**: devuelve `Forbidden` antes de proyectar cualquier fila. Quitar el `_check` de `project_all` es una mutación equivalente, porque `project` vuelve a comprobar y lanza la excepción en la primera fila: no hay datos parciales. Los campos coinciden con §3, salvo `delivery_status` (F-03).
- **Las candidatas de U03-T01**: hay casos de superusuario para `UPDATE`, `DELETE` y `TRUNCATE`, y de privilegios para los 5 roles de app, con `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` y la lectura de vuelta del conteo. La génesis usa `timespec="microseconds"` y la prueba reconstruye `canonical` con `chain.canonicalize`. `recorded_at` sigue saliendo de Python, como pidió la tarea. `0001` se editó en su sitio y la bitácora lo registra. No volví a correr las 4 mutaciones de CA-5 del codificador (ver F-07).
- **Alcance**: el diff no toca `reference-model/` ni nada del servicio, la API, la CLI o los charts. Hay 14 archivos, todos dentro del alcance.

## Hallazgos

### F-01 · NARANJA · `verify.py:121-127` y `tests/chain_builder.py` · `column_mismatch` sin cobertura para `policy_version_id` ni `actor_role`
Quité la línea `and body.get("policy_version_id") == row.policy_version_id` en la copia y CA-2 completo sigue en verde (`36 passed in 451 s`). La causa es que `build_chain` nunca escribe `policy_version_id` ni `actor.role`, y `COLUMN_CHANGES` de PBT-U3-02 no altera esas dos columnas. Con `actor_role` pasa lo mismo por la misma razón; esa mutación no la corrí.

### F-02 · NARANJA · `tests/property/test_projections.py:132` · PBT-U3-06 casi nunca prueba las omisiones de campos
La prueba sortea de manera independiente 11 tipos, 4 consumidores y 5 proyecciones, así que cada combinación válida sale en cerca del 0,5 % de los 500 ejemplos.
- Quitar `context_package` del `freeze` solo falla con 1 de 5 semillas (`--hypothesis-seed=1..5`).
- Quitar `received_at` de `metrics` sobrevive.

Las filtraciones sí se detectan: agregar `actor_id` a `frozen_resolution` falla con las 5 semillas, por el `extra=forbid` de U0. La solución sería sortear solo las combinaciones permitidas.

### F-03 · AMARILLO · `projections.py:73` y `test_projections.py:51` · `delivery_status` en `metrics` no está en domain-entities §3
La lista de campos de §3 para `metrics` no lo incluye: §3 solo dice que la referencia se resuelve «como `delivery_status`». Sí está en el `MetricsProjection` de U0 (`registry.py:394`) y solo sale si lo pasa el servicio. La prueba dice que su lista está «transcrita de §3, independiente del código», pero copia este campo del código. Ya está declarado en `CANDIDATAS.md`.

### F-04 · AMARILLO · `verify.py` · tres mutaciones sobreviven a `test_verify_modes.py`
1. Dejar de comparar el `recorded_at` de la copia WORM.
2. Quitar la comprobación de que la cadena de checkpoints siempre avanza (`nightly`).
3. Aceptar la firma de cualquier llave sin mirar `key_fingerprint`.

### F-05 · AMARILLO · `test_chain.py:247` y `test_verify.py:120` · dos pruebas prueban menos de lo que dicen
- PBT-U3-05 simula el contrato X+1 parcheando `chain.canonicalize`. Solo detecta una re-serialización que pase por ese atributo; una que pasara por los modelos de U0 no está modelada.
- En PBT-U3-03, el bloque «con el WORM, la copia también delata la reescritura» pasa por el recorrido normal de la cadena, no por el WORM: las copias son idénticas a la cadena.

### F-06 · AMARILLO · CA-4 · confirmo que la prueba de trazabilidad es débil, pero la aceptación del Paso 6 se cumple en sustancia
- `section_identifiers` devuelve solo `BR-U3-09..12`: el «y 15» se pierde.
- `own_identifiers` no contiene ninguna de esas reglas: la única `BR-U3` que reconoce como definida es `BR-U3-17`. Por eso el filtro siempre queda vacío.
- En la base `3f6d645` también da código 0.

Lo que pide el texto entre paréntesis («BR-U3-09..12 y 15 aparecen en las pruebas») sí se cumple, y lo comprobé con grep: 09 en `test_chain` y `test_verify_modes`, 10 en `test_chain`, 11 en `test_verify` y `test_verify_modes`, 12 en `test_verify_modes`, 15 en `test_projections`. No es ROJO. Arreglar la prueba queda fuera de alcance y ya está en candidatas.

### F-07 · AMARILLO · evidencia de la bitácora · el rojo primero de CA-5 no lo verifiqué
Las 4 mutaciones de la migración son una afirmación del codificador; no las volví a correr. El código de las pruebas sí es coherente con ellas: `match` sobre «solo de anexar.*{operation}» y comparación de bytes de la génesis.

### F-08 · AMARILLO · tiempo
El `check` de la unidad tardó 230 s en mi corrida y no los 180 s de la bitácora. CA-2 es el grueso: unos 95 s según el codificador, sin carga en la máquina. Ya está en candidatas («costo de PBT-U3-02/03»).

## Tareas candidatas (defectos reales fuera de alcance)
- Las de F-01 y F-02, por RL-2.
- Que `verify` contraste `public_keys` con la huella de la génesis, que es la «llave vigente» de BR-U3-12 y §2.2.

## Limpieza
Quedan corriendo `testcontainers/ryuk` y un `postgres:17.9-trixie`. Los maneja el reaper de Testcontainers; no levanté contenedores fuera de Testcontainers. Las mutaciones se hicieron solo en la copia de `git archive` y la copia quedó restaurada (`cmp` igual al worktree).

```
VEREDICTO: VERDE
NARANJA|verify.py:121-127 / chain_builder.py|column_mismatch sin cobertura para policy_version_id y actor_role (mutación sobrevive)
NARANJA|test_projections.py:132|PBT-U3-06 casi nunca prueba las omisiones de campos (context_package 1/5 semillas; received_at sobrevive)
AMARILLO|projections.py:73|delivery_status en metrics fuera de la lista de §3 (sí está en U0)
AMARILLO|verify.py|WORM recorded_at, monotonía de checkpoints y huella de la llave: mutaciones sobreviven
AMARILLO|test_chain.py:247, test_verify.py:120|PBT-U3-05 depende del punto de parche; el bloque WORM de PBT-U3-03 no prueba el WORM
AMARILLO|CA-4|test_traceability no exige BR-U3-09..12 ni 15 (da 0 en la base); las BR sí aparecen en las pruebas
AMARILLO|bitácora CA-5|rojo primero de la migración no verificado por el revisor
AMARILLO|tiempo|check de la unidad en 230 s, no 180 s
INFORME: revisiones/U03-T02/ronda-1.md
```
