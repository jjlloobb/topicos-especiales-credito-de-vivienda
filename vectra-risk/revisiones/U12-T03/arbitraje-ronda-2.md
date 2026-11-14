# U12-T03 — Arbitraje de la ronda 2 (orquestador, 2026-11-13)

Informe: `ronda-2.md`. Veredicto NO-VERDE, con un ROJO (F-11). F-01, F-03, F-04, F-05, F-07 y F-10 quedaron cerrados.

**Ronda 3 acotada, autorizada por el usuario (2026-11-13)** como excepción a RL-2, igual que en U08-T04. El ROJO no es un descuido del codificador: nace de la enmienda del arbitraje de la ronda 1, que supuso que la marca de la corrida que congeló es posterior al `recorded_at` del `freeze`. Contra el U9 real no lo es.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-11 ROJO: la referencia de «3 corridas más» no es la corrida que congeló | **Entra en la ronda 3**, con la enmienda de abajo | El oráculo de D2 exigiría 4 corridas, justo en el tope de 3 600 s: `no ejecutado` falso en buena parte de las corridas |
| F-12 NARANJA: un 4xx en la fase `freeze` da `RT2-LATENCY` `falla` con el texto «sin freeze al tope» | **Entra en la ronda 3** | Es una condición de una línea en el código que F-04 tocó en la ronda 2, y da un texto falso |
| F-13 AMARILLO: `port-forward` de Prometheus caído al armar la nota del tope | `CANDIDATAS.md` | Caso raro |
| F-14 AMARILLO: cuatro mutaciones que sobreviven | `CANDIDATAS.md` | Huecos de prueba, no resultados falsos |
| F-15 AMARILLO: `no_recongela` exige siempre 2 corridas | `CANDIDATAS.md`, destino U12-T06 | Duplica una espera; 30 de 4 000 simulaciones dan `no ejecutado`. La guía de kind lo advierte |

## Enmienda (sustituye a la del arbitraje de la ronda 1 para «3 corridas más de bias»)

U9 publica `vectra_bias_last_run_timestamp = int(finished_at)` (`bias-monitoring/src/vectra_bias/publish.py:133`): la marca va **truncada al segundo**. El `recorded_at` del `freeze` lleva microsegundos y cae, casi siempre, en el mismo segundo que `finished_at`. Por eso la marca de la corrida que congeló suele quedar **por debajo** del `recorded_at`.

La referencia es **la primera marca `vectra_bias_last_run_timestamp` mayor o igual que `floor(recorded_at)`** (el `recorded_at` truncado al segundo), y se cuentan las corridas correctas (`vectra_bias_last_run_ok == 1`) estrictamente posteriores a esa. La frase «su marca es posterior al `recorded_at`» del arbitraje de la ronda 1 y de `scenarios.md` es falsa y se corrige.

## Lo que se espera de la ronda 3

- **F-11:** `count_bias_runs` con `floor(recorded_at)`. El doble `rt2_world` publica la marca como el sistema real: un entero, el segundo truncado del fin de la corrida, a milisegundos del `freeze` (no un `float` a +1 s). Rojo primero: con el doble corregido y el oráculo sin corregir, una prueba nueva falla porque exige 4 corridas (el caso 16 de `edge.log` del revisor). Casos: `finished_at` en el mismo segundo que `recorded_at` (el habitual) y `finished_at` que cruza al segundo siguiente; en los dos, la que congeló más 2 no basta y más 3 da `pasa`.
- **F-12:** `RT2-LATENCY` es `falla` por «sin freeze al tope» solo si lo que faltó es `rt2_freeze_ausente`; un 4xx en la fase `freeze` no produce ese texto. Con su prueba.
- `scenarios.md`: la sección de la enmienda, corregida.
- Nada más cambia: ni `no_recongela` (F-15), ni lo demás.
- **Se vuelven a correr:** CA-11 (RT-2), CA-18, CA-22 (`make -C system-verification check`, con las semillas) y CA-25.
