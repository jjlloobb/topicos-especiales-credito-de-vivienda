# Ronda 3 — U12-T03

VEREDICTO: VERDE

F-11 y F-12 quedan cerrados y el arreglo no rompe nada de lo ya aprobado. Cerré la revisión con HEAD en f28829d, `git status --short` vacío y ningún contenedor mío: Ryuk terminó solo. La revisión es acotada a esos dos hallazgos; no reabrí nada más.

## Estado de lo pedido
| Hallazgo | Estado | Comando y resultado |
|---|---|---|
| F-11 ROJO | **cerrado** | `rev3/bias.log` (`bias_sweep.py`, código actual; cron 2/17/32/47, raspado de 30 s, sondeo de 60 s): con δ de 5 a 45 s y con δ de 5 a 180 s, **0 de 4 000** dan `no ejecutado` (en la ronda 2 fueron 1 548). Ningún `pasa` llega con menos de 3 corridas reales después de la que congeló. Espera máxima: **2 760 s**, frente a un tope de 3 600. El caso 16 de `edge.log` (marca `int`, mismo segundo) da **3**. Los casos 10, 10b, 11, 12, 13, 14 y 15 dan lo mismo que en la ronda 2 |
| F-12 NARANJA | **cerrado** | `rev3/f04.log` (14 pruebas pasan). Con un 403 en el primer sondeo, RT-2 da `falla rt2_http_403_forbidden` y LATENCY `no ejecutado`, sin el texto «sin freeze al tope». Con 503, sin conexión, y con el registro que cae al minuto 40, todo da `no ejecutado`. Sin `freeze` de verdad al tope, LATENCY da `falla rt2_latencia_sin_freeze` |
| Mutaciones (`rev3/mut.log`) | todas mueren | `ceil` en lugar de `floor`; `>` en lugar de `>=` en la referencia; sin `floor` (el oráculo de la ronda 2); y F-12 sin la condición nueva. Cada una tumba al menos una prueba |

## Casos límite de F-11 (δ = 30 s, sin jitter)
- **`finished_at` en el mismo segundo, que cruza al siguiente, `recorded_at` en un segundo entero, o hueco 0:** en los cuatro da `pasa` a los 2 700 s con 3 corridas reales.
- **Una corrida anterior en el mismo segundo truncado que `floor(recorded_at)`:** no es alcanzable con el cron. El CronJob tiene `concurrencyPolicy: Forbid` y las corridas van cada 15 min, así que la anterior termina unos 900 s antes. Solo podría pasar con un Job lanzado a mano en ese mismo segundo, y la demo no lo hace.
- **Reloj de U3 atrasado respecto del de U9:** con 0,5 a 5 s de atraso, el resultado es correcto (3 corridas). Solo da `pasa` temprano (2 corridas) con un atraso cercano a un ciclo entero (900 s), que en kind no ocurre: todo comparte el reloj del host.
- **Reloj de U3 adelantado:** con ≥ 0,5 s de adelanto, el oráculo pide 4 corridas y llega al tope (`no ejecutado` o `pasa` a los 3 600 s). Falla hacia «esperar de más», nunca hacia `pasa` antes de tiempo. En kind ese desfase es 0.
- **El doble:** comprobado contra el código real. `rt2_world` publica `float(int(finished))` con `finished = recorded + 0,05 s` y un `recorded_at` con fracción. Coincide con `publish.py:133` (`int(report.finished_at.timestamp())`) y con `run.py:312-317` (el `freeze` dentro de la corrida y `finished_at` después).

## `_no_recongela`
El único cambio es la referencia truncada, porque usa la misma `count_bias_runs`; su código no cambió. Frente a mi `recongela.log` queda igual: 28 de 4 000 ahora frente a 30 de 4 000 en la ronda 2, que es ruido de la simulación. No empeora; F-15 sigue en candidatas.

## `scenarios.md`
La sección de la enmienda dice ahora lo que hace el código: marca `int`, referencia igual a la primera marca ≥ `floor(recorded_at)`, corridas estrictamente posteriores, y F-12 solo con `rt2_freeze_ausente`.

## Regresión y alcance
- **`make -C system-verification check`** (uptime 2,09 → 2,23; 12 min 13 s; `EXIT=0`):
  - lint y mypy pasan; `Contracts: 7 kept`;
  - primera pasada: 692 pruebas pasan en 503 s, semilla 172484257, cobertura 95,25 %;
  - segunda pasada: 590 pasan en 222 s, semilla 3076560623, con `report` y `sampler` al 100 %;
  - ninguna prueba omitida.
- **`uv lock --check`:** sale con 0.
- **`test_links.py`:** 570 archivos sin enlaces rotos.
- **Alcance:** `git diff 3593f37..HEAD` solo toca `rt2.py`, `rt2_world.py`, `test_oracles_rt2_rt3_rt5.py`, `scenarios.md`, la bitácora, `revisiones/`, `CANDIDATAS.md` y `DECISIONES-LOOP.md` (`fuera=1`).

## Hallazgos nuevos
### F-16 · AMARILLO (CANDIDATAS) · `rt2.py:count_bias_runs` · un desfase de reloj entre U3 y U9 de ≥ 0,5 s (U3 adelantado) hace esperar una corrida de más
Con U3 adelantado, la referencia salta a la corrida siguiente y el oráculo llega al tope de 3 600 s. Falla hacia `no ejecutado`, nunca hacia `pasa`. En kind no ocurre porque todo usa el reloj del host. Conviene una nota en la guía de U12-T06 si alguna vez se verifica fuera de kind.

## Rutas
Todo está en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev3/`: `check.log`, `bias.log`, `f04.log`, `mut.log` y `misc.log`.

```
VEREDICTO: VERDE
AMARILLO|vectra-risk/system-verification/src/vectra_verification/scenarios/rt2.py:145-160|con U3 adelantado >=0,5 s respecto de U9 el oraculo espera una corrida de mas (falla hacia no ejecutado; no ocurre en kind)
INFORME: revisiones/U12-T03/ronda-3.md
```
