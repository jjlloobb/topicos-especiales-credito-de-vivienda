# Ronda 2 — U12-T03

VEREDICTO: NO-VERDE

Queda un ROJO, en F-02. Contra el U9 real, la referencia de «3 corridas más» casi nunca es la corrida que congeló. U9 publica `vectra_bias_last_run_timestamp = int(finished_at)` (`bias-monitoring/src/vectra_bias/publish.py:133`), mientras que el `recorded_at` del `freeze` lleva microsegundos (`clock_timestamp()` de U3 y `chain.format_timestamp`). Entre ese `recorded_at` y `finished_at` pasan milisegundos: el envío a U3 es síncrono dentro de `governance.freeze` y U9 fija `finished_at` justo después. Por eso, casi siempre, `int(finished_at) < recorded_at`. La referencia pasa a ser la corrida siguiente y el oráculo exige 4 corridas (unos 60 min), justo en el tope `BIAS_TIMEOUT = 3600 s`. El resultado es un `no ejecutado` falso en D2.

Esto también lo pasé por alto yo en la ronda 1: sin el truncado, F-02 solo era cierto cuando `finished_at` cruzaba un segundo. F-01, F-03, F-04, F-05, F-07 y F-10 están cerrados.

Comprobaciones al terminar:
- La tarea es el blob `fdd6a20387f44d0633e21b8020474d19b0ffbb27` y coincide.
- HEAD sigue en 3593f37 y `git status --short` está vacío.
- No queda ningún contenedor mío: Ryuk terminó solo. Los `postgres`, `minio` y `vault` detenidos son ajenos.

## Estado de lo pedido en el arbitraje
| Hallazgo | Estado | Comando y resultado |
|---|---|---|
| F-01 espera de F22 | **cerrado** | `race2.py` simula U8: la toma pone `attempts` sin cambiar el estado, `_RETRY` deja el caso en `en_sincronizacion` y el intento 6 lo lleva a `no_disponible`. La primera lectura, a 0 s, es `en_evaluacion/1`: el oráculo sigue esperando, sale a los 15–30 s con `en_sincronizacion/timeout` y da `pasa`. Un caso nunca vuelve a `en_evaluacion` en el backoff (`job_queue.py:78-81` no toca `state`). La escalada se ve entre 795 y 1230 s, dentro de 1500 s, y es coherente con los 12,4–19,3 min de §1.1. Si se queda en `en_evaluacion/1`, espera 900 s y da `sin_estado_final`; con `attempts=0`, da `sin_intentos`. `_rt3b` usa el mismo `cases`. Las 3 mutaciones de F-01 mueren |
| F-02 «3 corridas más» | **no cerrado (F-11 ROJO)** | En `edge.log`, el caso 10 da 2 y el 10b da 3: con marcas `float` funciona. El caso 16, con marca `int`, da 2 cuando deberían ser 3. Ver F-11 |
| F-03 costura | **cerrado** | `seams.log`: 1 a 3 tramos, sobras de 0 / 0,5 / 7 / 14,999 / 15 / 22 / 30 s, sin `start>end`, sin huecos ni puntos repetidos, todo en la rejilla. Prometheus real: `-k seam` pasa; quitando el corte muere con `query_failed:http_400:bad_data`. «Saltar un punto» muere en la unitaria. «Repetir el punto» es equivalente, porque `ranged` deduplica |
| F-04 sin `freeze` al tope | **cerrado** | `f04.log`: con registro 503, registro sin conexión y registro que cae al minuto 40, la fase da `no ejecutado` y LATENCY también `no ejecutado`. Sin `freeze` da `falla rt2_latencia_sin_freeze`. La mutación muere. Ver F-12 y F-13 |
| F-05 infraestructura | **cerrado** | rt2, rt3 y rt5 tienen pruebas y sus mutaciones mueren. sim_normal lo probé yo (`pf_sim.log`): port-forward caído en la 4.ª lectura, kubectl y OIDC dan `no ejecutado` con código. `AssertionError` y `KeyError` se propagan, 403 da `falla` y 503 `no ejecutado`. Un `OidcError` con `Authorization: Bearer …` sale redactado por `evidence.scrub`, y los `OidcError` reales son códigos fijos |
| F-07 tres pruebas | **cerrado** | Las tres mutaciones mueren: 403 de RT3-b, estado de los casos nuevos y retención contra t1 (`mut.log`, 18–20) |
| F-10 y enmienda | **cerrado** | `scenarios.md:111` corregido; la sección «Enmienda de la ronda 2» está presente. Su frase «su marca es posterior al `recorded_at`» es falsa en el sistema real (F-11) |

## Regresión y alcance
- **`make -C system-verification check`** (carga 3,47 → 1,62; 12 min 39 s): lint y mypy pasan; `Contracts: 7 kept`.
  - Primera pasada: 686 pasan en 507 s, semilla 4061686053, cobertura 95,15 %.
  - Segunda pasada: 584 pasan en 244 s, semilla 3294662796, `report` y `sampler` al 100 %.
  - Ninguna prueba omitida.
- **Otros comandos:** `uv lock --check` sale con 0. `test_links.py` da 567 archivos sin enlaces rotos.
- **Alcance:** el diff `151a20b..HEAD` toca solo `scenarios/`, `tests/`, `scenarios.md`, la bitácora, `revisiones/` y `CANDIDATAS.md` (`fuera=1`).
- **Regla P-2 (a):** los cinco casos dan lo mismo que en la ronda 1. Los casos 8 y 9 ahora dan `sin_estado_final`, que es lo correcto tras la espera.

## Hallazgos
### F-11 · ROJO · `scenarios/rt2.py:144-157` y `tests/doubles/rt2_world.py:360` · la referencia de F-02 no es la corrida que congeló frente al U9 real
- **El oráculo:** `count_bias_runs` toma como referencia la primera marca `>= recorded_at`. Como la marca es `int(finished_at)` y `finished_at` cae en el mismo segundo que `recorded_at`, la marca de la que congeló queda por debajo. La referencia pasa a la corrida siguiente y se exigen 4 corridas.
- **El doble:** añade una marca `float` a +1 s, lo contrario de lo que ocurre en el sistema real.
- **Simulación** (`bias_trunc.log`: cron 2/17/32/47, raspado de 30 s, `ranged` cada 15 s, sondeo de 60 s):
  - si la fase empieza a 15 s del `freeze`, da `no ejecutado`, «2 de 3»;
  - de 45 a 180 s, da `pasa` a 3480–3600 s, en el tope;
  - con δ entre 5 y 45 s, sale `no ejecutado` en 1548 de 4000 corridas simuladas.
- **El contrafactual** con `floor(recorded_at)` da 0 de 4000, con un máximo de 2760 s.
- **Arreglo sugerido:** referencia = primera marca ≥ `floor(recorded_at)`. En el doble, marca `int` a milisegundos del `freeze`. También hay que corregir la frase de `scenarios.md`.

### F-12 · NARANJA (CANDIDATAS) · `rt2.py:1004-1006` · un 4xx en la fase `freeze` da LATENCY `falla` con un texto falso
`no_freeze` mira cualquier `:freeze` en `falla`, no `rt2_freeze_ausente`. Con un 403 en el primer sondeo, LATENCY dice «sin freeze al tope de 2700 s; la detección tardó más de 1800 s» cuando solo habían pasado 1210 s (`f04.log`). Se agrava con F-06. Arreglo sugerido: exigir `"rt2_freeze_ausente" in s.missing`.

### F-13 · AMARILLO · `rt2.py:last_bias_note` · cuando no hay `freeze` al tope y se cae el port-forward de Prometheus mientras se arma la nota, el resultado es `no ejecutado`
El sistema sí respondió y no detectó; la nota solo captura `ObsError` (`f04.log`).

### F-14 · AMARILLO · huecos de prueba (`mut.log`)
Sobreviven cuatro mutaciones:
- `no_recongela` cuenta la corrida que estaba en vuelo (6);
- la captura de infraestructura en la latencia de rt2 (12);
- la de `sim_normal` (16), que el codificador ya había reconocido;
- `kubectl_no_responde` confundido con `port_forward_caido` en rt2/rt3 (17).

Además, en `test_rt5_promql.py:201-205` `start` se asigna dos veces y la primera asignación no sirve para nada.

### F-15 · AMARILLO · `rt2.py:_no_recongela` · siempre exige 2 corridas
La primera que termina tras la reactivación es la referencia, haya estado en vuelo o no. La espera se duplica. En la simulación, 30 de 4000 reactivaciones salen `no ejecutado` con el tope de 1800 s (`recongela.log`).

## Tareas candidatas
- F-12, F-13, F-14 y F-15 (arriba).
- Corregir el texto de la enmienda en `arbitraje-ronda-1.md` y `scenarios.md`: la marca de U9 es `int` y no es posterior al `recorded_at`.

## Rutas de transcripciones largas
Todo está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev2/`:
- `check.log`
- `race.log`
- `edge.log`
- `bias_trunc.log`
- `recongela.log`
- `seams.log`
- `promreal.log`
- `f04.log`
- `pf_sim.log`
- `mut.log`
- `misc.log`

```
VEREDICTO: NO-VERDE
ROJO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:144-157|la referencia de bias no es la corrida que congelo: U9 publica int(finished_at) < recorded_at; exige 4 corridas en el tope de 3600 s y da no ejecutado falso
NARANJA|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:1004-1006|un 4xx en la fase freeze da RT2-LATENCY falla con "sin freeze al tope"
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:492-510|port-forward de Prometheus caido en la nota del tope da no ejecutado
AMARILLO|vectra-risk/system-verification/tests/unit/test_oracles_rt2_rt3_rt5.py|cuatro mutaciones sobreviven (no_recongela en vuelo, infra en latencia, sim_normal, kubectl vs port-forward)
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:750-793|no_recongela exige siempre 2 corridas
INFORME: revisiones/U12-T03/ronda-2.md
```
