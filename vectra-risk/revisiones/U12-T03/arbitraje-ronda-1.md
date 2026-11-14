# U12-T03 — Arbitraje de la ronda 1 (orquestador, 2026-11-13)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con dos ROJO: dos oráculos que dan un resultado falso frente al código real. Los dos nacen del texto de la tarea, no de un descuido del codificador, así que este arbitraje **enmienda la tarea**. Es la última ronda (RL-2).

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: F22 deja de esperar con `attempts ≥ 1`, que U8 pone al tomar el trabajo: `falla` falsa en D1 | **Entra en la ronda 2**, con la enmienda de abajo | RT-3 daría `falla` justo cuando el sistema produce la evidencia esperada |
| F-02 ROJO: «3 corridas más de bias» cuenta la corrida que congeló: `pasa` tras 2 | **Entra en la ronda 2**, con la enmienda de abajo | El oráculo de D2 daría `pasa` sin cumplirse la condición |
| F-03 NARANJA: `rt5.ranged` pide `start > end` en la costura | **Entra en la ronda 2** | Da un `no ejecutado` con un código falso; el arreglo es de unas líneas |
| F-04 NARANJA: `RT2-LATENCY` sale `no ejecutado` cuando no llega `freeze` al tope | **Entra en la ronda 2** | El sistema respondió y no detectó: es `falla`. Un resultado falso de un elemento del informe |
| F-05 NARANJA: un `port-forward` caído (`K8sError`) o un `OidcError` escapan de `rt2` y `rt3` como excepción | **Entra en la ronda 2** | En kind es el fallo más probable de la corrida; debe dar `no ejecutado` con su código y conservar los sub-resultados y la retoma |
| F-07 AMARILLO: tres huecos de prueba (403 de RT3-b, estado de los casos nuevos, retención contra t1) | **Entra en la ronda 2** (solo esos tres y la costura de F-03) | Son pruebas que faltan sobre ramas que deciden un resultado |
| F-10 AMARILLO: `scenarios.md:111` dice que RT-5 tiene sub-resultados | **Entra en la ronda 2** | Una línea |
| F-06 AMARILLO: 401 y 429 cuentan como `falla` | `CANDIDATAS.md` | Riesgo bajo: las sesiones se renuevan solas |
| F-08 AMARILLO: «máximo ≥ 1» no distingue un contador que quedó de un ensayo anterior | `CANDIDATAS.md`, destino U12-T06 | Es el texto literal del plan; el log y la alerta lo cubren. La guía de kind lo advierte |
| F-09 AMARILLO: `combine` no exige que estén los obligatorios | `CANDIDATAS.md` | Hoy `rt3()` no llega a ese caso |

## Enmienda de la tarea (rige sobre `tareas/U12-T03-escenarios-y-mediciones.md`)

- **Espera de F22 (línea 256 de la tarea, y donde repita «`attempts ≥ 1`»).** El oráculo de F22 no deja de esperar por `attempts`: espera a que **cada caso de la sonda salga de `en_evaluacion`** (U8 escribe `attempts` al tomar el trabajo, `case-management/src/vectra_case/job_queue.py`, y el caso sigue en `en_evaluacion` mientras la llamada a scoring está en vuelo, hasta `SCORING_TIMEOUT`). Al vencer el plazo que ya existe, un caso que sigue en `en_evaluacion` da el código que ya existe para ese caso. `_rt3b`, que usa el mismo `cases`, queda igual de corregido.
- **«3 corridas más de bias» (P-5 y línea 289 de la tarea).** No se cuentan las corridas con marca posterior al `recorded_at` del `freeze`: la corrida que congeló termina después de escribir el `freeze` (`bias-monitoring/src/vectra_bias/run.py`), así que su marca es posterior y no es «una más». La referencia es **la primera marca `vectra_bias_last_run_timestamp` mayor o igual que el `recorded_at` del `freeze`** (la de la corrida que congeló), y se cuentan las corridas correctas (`vectra_bias_last_run_ok == 1`) **estrictamente posteriores a esa**. La misma corrección se aplica a `no_recongela`: una corrida que estaba en vuelo durante la reactivación no cuenta como posterior.

## Lo que se espera de la ronda 2

- **F-01 y F-02:** el cambio de arriba, con el doble corregido para que modele el sistema real: `rt2_world.case_state` devuelve `en_evaluacion` con `attempts ≥ 1` mientras dura la llamada; el doble de bias congela **dentro** de una corrida y fija la marca de fin después. Rojo primero: con los dobles corregidos y el oráculo sin corregir, las pruebas nuevas fallan como el revisor describe (`race.log` y `edge.log`, caso 10). La prueba que fijaba el comportamiento viejo se corrige, no se borra.
- **F-03:** `ranged` nunca pide `start > end`; prueba de la costura (lo que sobra, menor que `step`) contra Prometheus real, y una unitaria que mate «saltar un punto en la costura».
- **F-04:** sin `freeze` al tope de 2 700 s, `RT2-LATENCY` es `falla`.
- **F-05:** `K8sError` y `OidcError` dentro de `rt2`, `rt3`, `rt5` y `sim_normal` dan `no ejecutado` con un código estable; se conservan los sub-resultados ya calculados y el punto de retoma.
- **F-07:** las tres pruebas que faltan.
- **F-10:** la línea de `scenarios.md`.
- `scenarios.md` y la bitácora recogen la enmienda. Nada más cambia.
- **Se vuelven a correr:** CA-1, CA-4, CA-7, CA-10, CA-11, CA-12, CA-14, CA-18, CA-22 (`make -C system-verification check`, con las semillas) y CA-25.
