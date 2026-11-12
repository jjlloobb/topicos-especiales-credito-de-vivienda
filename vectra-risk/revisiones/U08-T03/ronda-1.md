# Ronda 1 — U08-T03

VEREDICTO: NO-VERDE

No hay ningún ROJO. Los 9 criterios de aceptación pasan en mi propia corrida; CA-9 tiene una salvedad: `bench_gate` de `contracts` falla por la carga de la máquina, que es la candidata conocida. Quedan tres NARANJA en pie: F-01, F-02 y F-03. Por RL-3 solo un ROJO bloquea; si pasa o no a ronda 2 lo decide el orquestador.

## Criterios de aceptación, verificados por mí
Corrí todo desde `vectra-risk/`, en serie, sobre HEAD `520741a`. El diff no toca nada de `contracts/`: `git diff --stat 5cf2ebb..HEAD -- vectra-risk/contracts` sale vacío.

| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | intake + PBT-U8-06 | el de la tarea, con `-rs` | pasa: 18 passed en 166 s, carga 17 a 20 |
| 2 | evidencia + PBT-U8-07 | el de la tarea | pasa: 44 passed en 301 s, carga 20 a 21 |
| 3 | barrido, retry, gauges | el de la tarea | pasa: 20 passed en 20 s |
| 4 | credit | el de la tarea | pasa: 21 passed |
| 5 | API, degradación, apagado | el de la tarea | pasa: 19 passed en 34 s; el arranque es con `python -m` de verdad |
| 6 | 9 rutas | `build_app()` + `REGISTRY` | pasa: imprime `OK` |
| 7 | import-linter + grep | el de la tarea | pasa: 4 KEPT, 0 broken; el grep sale vacío |
| 8 | docs y plan | el de la tarea | pasa: `services.md` nombra P-5 y la purga; salen 5 líneas `[x]` con `(U08-T03)` |
| 9a | `make -C case-management check` | — | pasa: 298 passed en 12 min 19 s; los 4 módulos puros siguen al 100 %; carga 27 → 15 |
| 9b | `make -C contracts check` | — | 545 passed, pero **`bench_gate` falla**: p95 de pipeline 5,52 ms con límite 5,0; p99 de derive 4,08 ms con límite 2,0; carga 15 → 22. Lo corrí aislado dos veces más con carga 21 a 24 y volvió a fallar (6,18 y 5,50 ms). Como el código de contracts es idéntico al de la base, es la candidata conocida del bench y no es de esta tarea (CA-9 lo prevé). El codificador lo tuvo en verde con carga 8 |

Ninguna prueba se saltó: `-rs` no muestra omisiones y ningún archivo nuevo tiene `skip` ni `xfail`. El worktree quedó limpio antes y después (`git status --short` sale vacío). `CANDIDATAS.md` no aparece en el diff (punto 8).

## Hallazgos

### F-01 · NARANJA · evidence.py:64,492-528 · El arrendamiento de 30 s dura menos que un lote, y dos réplicas reenvían la misma evidencia
Un lote de 100 envíos con 4 en vuelo y `REGISTRY_TIMEOUT` de 2,5 s tarda hasta 62,5 s, y el arrendamiento caduca a mitad del lote. Lo probé en tiempo real, sin mover el reloj: 100 `fail_closed` pendientes, el doble del registro con 2 s de demora (el escenario de la otra línea del mismo CA-2), la réplica A empieza su ciclo y la réplica B arranca 32 s después. Resultado: `claimed_a=100 claimed_b=40 requests=140 duplicated_keys=40`. Es decir, 40 evidencias se enviaron dos veces dentro del ciclo de A.
- No se corrompe nada, porque el registro es idempotente y las 100 terminan `confirmada`.
- Pero la propiedad «2 réplicas → cada evidencia se reintenta una sola vez por ciclo» solo vale si el lote dura menos de 30 s. La prueba `test_two_replicas…` no lo detecta porque usa un 400 instantáneo.
- **Misma clase, en el mismo hallazgo:** `record_decision` y `record_view` insertan con `next_attempt_at = now` (líneas 356-357 y 446-448) y envían de inmediato. El reconciliador puede reclamar la misma fila en ese momento y enviarla en paralelo.
- **¿Puede quedar arrendada para siempre?** No. Si la réplica muere, la fila vuelve a ser elegible a los 30 s, porque `next_attempt_at` vence solo.
- Arreglo posible: un arrendamiento mayor que el peor lote, o renovarlo por fila; y que el envío inmediato inserte con `next_attempt_at = now + LEASE`.
- La prueba está en `…/scratchpad/rev-u08-t03-r1/exp/test_rev_exp.py::test_e1…`.

### F-02 · NARANJA · tests/property/test_evidence.py · PBT-U8-07 no llega al escenario del abandono seguido de una decisión nueva, y si llegara no lo detectaría
- **¿Es la lectura del diseño o una prueba debilitada?** Medir por evidencia es la lectura correcta. El diseño dice que «el momento de negocio no cambia entre intentos», y una decisión nueva con la misma llave tras un abandono es otra evidencia. En ese punto la prueba no está debilitada.
- **Contraejemplo que deja pasar.** La prueba guarda, por llave, un *conjunto* con los momentos de todas las filas que comparten esa llave (`stored[key]`). Así, un envío de la evidencia B con el momento de la evidencia A pasa. Además, «`confirmada` implica entrada en el registro» solo comprueba que la llave esté presente, no que el contenido registrado sea el de la fila confirmada.
- **Mutación que corrí.** Cambié `_resolve_conflict` para que confirme la decisión **nueva**, la que el registro rechazó, en lugar de la abandonada. Con eso, PBT-U8-07 sigue **pasando**. El contador de la mutación marcó `buggy swaps executed: 0`: en 80 ejemplos la máquina nunca recorrió el camino abandono → decisión nueva → 409.
- El diseño exige ese escenario dentro de PBT-U8-07 («incluso con un abandono seguido de una decisión nueva…»), y la tarea pide la PBT «entera».
- Hoy lo cubre solo la prueba de ejemplo `test_abandoned_decision_…`, que sí atraparía esta mutación.
- Arreglo posible:
  - una regla con `@precondition` que fuerce la secuencia `lose_ack` → decisión → más de 24 h → decisión nueva;
  - un invariante que compare el payload de la entrada en el registro con el de la fila `confirmada` (por `registry_entry_id`);
  - y medir el momento por `evidence_id`, no por llave.
- La prueba está en `test_rev_exp.py::test_e3…` (la carga de la máquina pudo influir en el tiempo, no en el recorrido).

### F-03 · NARANJA · evidence.py:171-173 · El 401 por token sin `acr` o sin `auth_time` no tiene prueba
La bitácora lo afirma («Decisiones») y el código lo hace, pero ninguna prueba del diff lo cubre: `grep acr` en `tests/` solo encuentra principales que sí traen `acr`. Lo comprobé yo con mis propios experimentos, para `acr=None` y para `auth_time=None`: decisión 401, consulta 401, 0 filas en el outbox, 0 envíos al registro, y `vectra_authz_denied_total{code=unauthenticated}` sube en 2. Falta que una prueba del diff lo fije. Está en `test_rev_exp.py::test_e2…`.

### F-04 · AMARILLO · evidence.py:422-426 · La consulta abandonada que se reabre pisa `created_at` y `attempts`
No rompe ningún invariante:
- `viewed_at` del payload y `explanation_views.first_viewed_at` se conservan, así que la auditoría queda intacta;
- el índice parcial no puede chocar, porque hay una sola fila por (caso, usuario);
- encaja con BR-U8-19 («continúa pendiente»).

Efectos laterales:
- el outbox pierde su hora de creación original;
- `pending_oldest_seconds` vuelve a 0;
- si se abandona otra vez, `evidence_abandoned_total` cuenta dos veces la misma evidencia y `CaseEvidenceAbandoned` vuelve a dispararse.

Conviene documentarlo o guardar el plazo en otra columna (eso último toca la migración: candidata).

### F-05 · AMARILLO · evidence.py:64-66; sweeps.py:22; db_gauges.py:162-163; governance_client.py:127; db.py:18-19 · Constantes fuera de `config.py`, algunas duplicadas
`evidence.LEASE` y `evidence.BACKOFF_JITTER` repiten nombre (y el jitter también el valor) de `config.LEASE` y `config.BACKOFF_JITTER`, que son del worker. Es confuso para U08-T04. Las demás (`SWEEP_INTERVAL`, `GAUGE_INTERVAL`, `CACHE_TTL`, `ACQUIRE_TIMEOUT`…) son `Final` con nombre, pero viven sueltas en cada módulo.

### F-06 · AMARILLO · bitácora y commit · Evidencia parcial de la corrección a PBT-U8-07
La primera corrida roja de CA-2 («1 failed, 43 passed»), la que motivó cambiar el invariante, no está pegada. Además, el mensaje de `520741a` dice que cambia PBT-U8-07, pero ese commit solo toca la bitácora: la prueba entró en `d5f7bf4`.

### F-07 · AMARILLO · api.py:126 · `handlers(clock)` recibe un parámetro que no usa (`noqa: ARG001`)
`retry_case` toma la hora de `evidence.clock`.

### Otros puntos que revisé y están bien
- **Seguridad de la API (punto 4).** Los permisos de las 9 rutas vienen del `REGISTRY` de U0 y los aplica `create_app`; hay prueba del 403 y del 401 con `authz.denied`. De `outcome` solo se usa `read_wire` (CA-7 en verde).
- **`serving-config` con la forma vieja (punto 5).** Falla cerrado: lanza `ServingConfigInvalid`, el barrido devuelve `skipped`, y la prueba lee de vuelta el estado del caso, la marca y que no haya trabajos.
- **SIGTERM a mitad de lote (punto 6).** La prueba lee de vuelta el outbox y encuentra 12 confirmadas y ninguna pendiente. Por diseño no puede quedar nada a medio enviar: la fila sigue pendiente y arrendada hasta tener el ack.
- **Cobertura (punto 7).** La tarea dice textualmente que el 100 % de los módulos nuevos es del Paso 18 (U08-T04) y que aquí basta con anotarla. El codificador tiene razón y no es hallazgo.
- **`first_evaluation`.** Viaja solo en `RecommendationPayload` (`registry.py:61`), así que pasarlo a U08-T04 es correcto según las Precisiones de la tarea.

## Tareas candidatas (defectos reales fuera de alcance)
- `bench_gate` de contracts es sensible a la carga: falla con carga ≥ 15, con el código idéntico al de la base (la candidata conocida).
- Un plazo de abandono distinto de `created_at` en `evidence_outbox` (F-04) toca la migración de U08-T01.
- Con `SIGTERM`, un lote del reconciliador puede durar hasta unos 62 s: hay que alinearlo con el `terminationGracePeriodSeconds` del chart (U08-T05).

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u08-t03-r1/`:
- `CA1.log` … `CA8.log`, `CA9a.log`, `CA9b.log` y `summary.txt`: cada corrida con su `uptime` antes y después.
- `exp/test_rev_exp.py`: los experimentos E1, E2 y E3 (fuera del worktree).
- `exp.log`: su salida.

```
VEREDICTO: NO-VERDE
NARANJA|evidence.py:64,492-528|El arrendamiento de 30 s dura menos que un lote: 2 réplicas reenvían 40 de 100 evidencias en el mismo ciclo; el envío inmediato también es reclamable
NARANJA|tests/property/test_evidence.py|PBT-U8-07 no recorre el escenario abandono→decisión nueva (0 recorridos) y pasa con una mutación que confirma la decisión equivocada
NARANJA|evidence.py:171-173|El 401 por token sin acr/auth_time funciona, pero no tiene prueba en el diff
AMARILLO|evidence.py:422-426|La consulta reabierta pisa created_at y attempts: el gauge se reinicia y el abandono cuenta dos veces
AMARILLO|evidence.py:64-66 y otros|Constantes fuera de config.py; LEASE y BACKOFF_JITTER duplican nombres de config
AMARILLO|bitácora/commit 520741a|Falta la salida roja que motivó cambiar PBT-U8-07; el mensaje del commit no coincide con su contenido
AMARILLO|api.py:126|handlers(clock) recibe un parámetro que no usa
INFORME: revisiones/U08-T03/ronda-1.md
```
