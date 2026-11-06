# Ronda 4 — U02-T13

VEREDICTO: VERDE

Revisé `vectra-risk/` en HEAD de424f2. La tarea está en el blob 5be4aa2034da42430b30f040cd5638cd7f27718b, el esperado. Corrí yo CA-1 a CA-6, con CA-5 y CA-6 en serie, y pasan todos. Los cinco puntos de `arbitraje-ronda-3.md` (F-04 a F-08) quedan cerrados. Las reglas y el CR no cambiaron desde 0f18aaf. Quedan cuatro AMARILLO, ninguno bloquea. El worktree estaba limpio antes y sigue limpio después (`git status --short` vacío). Todas las copias, mutaciones y logs están en `<scratchpad>/U02-T13-r4/`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Reglas válidas, cada alerta dispara y no dispara | `promtool check rules … && promtool test rules …/tests/*.yaml` | pasa: 12 reglas, SUCCESS x3, exit 0 (10.4 s) |
| 2 | Runbooks | `test_runbooks.py --root identity-edge && … --operational` | pasa: «24 alertas…» exit 0, «11 runbooks operativos…» exit 0 |
| 3 | Reglas = diseño | `uv run pytest identity-edge/tests/unit/test_alert_rules.py -q` | pasa: 75 passed (3.7 s). Solo lee archivos |
| 4 | Imagen | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 92 passed (0.16 s). Solo parsea el Dockerfile |
| 5 | `check` de U2 con `rules` y `runbooks` | `uv sync --frozen && make -C identity-edge check` | pasa: 2473 passed en 15:39, ninguna omitida (Skipped: 0 en kubeconform), exit 0. `rules` y `runbooks` corren dentro (ca5.log:181-194) |
| 6 | U1, después de CA-5 | `make -C platform check-local` | pasa: 745 passed, «253 archivos Markdown sin enlaces rotos», exit 0 (2m23s). Empezó a las 00:03:31, cuando CA-5 ya había terminado |

## Cierre del arbitraje de la ronda 3
- **F-04: cerrado.** En la bitácora, la línea 313 cita «11 runbooks operativos…». Es la misma salida que me da a mí `--root identity-edge --operational`.
- **F-05: cerrado en las cifras.** Cada cifra de `break-glass-login.md:12-15` y de `CANDIDATAS.md:123` sale de un escenario de `LIMITES` o de `SCENARIOS`. Lo comprobé de dos formas:
  - Corrí `b11_scenarios.py probe` sobre una copia. La salida es **idéntica** a `probe-ronda-4.txt` (`diff` vacío).
  - Hice un barrido propio, con otra construcción de las series (6 muestras antes, `mysweep.py`, que no comparte código con el suyo). Cubre los cuatro modelos, huecos de 2 a 15 min, FP, OM, L y RN 0 a 6. Da las mismas duraciones en todos los puntos:
    - falso positivo con `x`: 2, 3, 4, 4, 3, 2 y 1 min para huecos de 2 a 8, y nada desde 9;
    - falso positivo con `none`, `up` y `both`: nunca;
    - omisión con `none`, `up` y `both`: 2 min de alerta con hueco de 2, 1 min con hueco de 3, y nada desde 4;
    - omisión con `x`: nada desde 9 de hueco;
    - RN: con k=0 no dispara nunca; con k de 1 a 4 empieza siempre 5 min después de la vuelta del scrape.
  - Coincide con lo que medí en la ronda 3: falso positivo de G2 con huecos de 2, 4, 6, 8 y 10 min, que dura 2, 4, 3, 1 y 0 min; omisión desde 9 con el modelo de E; omisión desde 4 sin *stale*; RN con k=0 nunca y con k=1 un solo minuto, 4 min tarde.
  - Las cifras ya no se generalizan desde un solo punto. Los comentarios de G2 y E dicen su modelo. `gen` regenera el archivo b11 idéntico (`diff -q` vacío).
  - Queda un residuo en cómo el texto separa los modelos construidos de lo que hace un Prometheus real. Ver F-09.
- **F-06: cerrado.** Lo hice en rojo y en verde (`f06.py`, `f06.txt`):
  - con el archivo b11 de 0f18aaf, sobreviven «N rama 3 sin `error=""`» y «`offset 10m`»;
  - con el de HEAD, las dos quedan DETECTADAS gracias a `Zf` y `Rr`;
  - corrí `mutaciones.py` sobre una copia: la salida es **idéntica** a `mutaciones-ronda-4.txt`, con 72 mutaciones, 0 sobreviven y exit 0.

  Una mutación extra mía, `[1h] offset 6m`, sobrevive. La considero casi equivalente: `N` exige que no haya muestra en (t-10m, t-5m], así que solo cambia el borde de (t-66m, t-65m].
- **F-07: cerrado.** `test_alert_rules.py:234-236` ya no tiene literales. Lo comprobé cambiando el diseño en memoria (`f07.py`):
  - si B11 dice `SEV3`, la prueba falla;
  - si B11 dice `for 10m`, la prueba falla;
  - sin cambios, pasa.
- **F-08: cerrado.** El docstring de `theme_checks.py:88` coincide con `design_event_metric_options()`.
- **Reglas y CR sin cambios:** `git diff --quiet 0f18aaf HEAD -- …/identity-edge-rules.yaml …/identity-edge-rules.prometheusrule.yaml` termina en 0. En `observability/`, desde 0f18aaf, solo cambia `identity-edge-rules-b11-test.yaml`.

## Hallazgos

### F-09 · AMARILLO · identity-edge/runbooks/break-glass-login.md:12 (misma clase en CANDIDATAS.md:123 y b11_scenarios.py:68) · Un modelo real figura como construido y falta el supuesto del intervalo
- **«Las dos» con marca de *stale* no es una construcción.** Es lo que hace Prometheus cuando un target sale del service discovery, por ejemplo cuando un rollout del StatefulSet borra y recrea `keycloak-0`. Lo muestra el código de Prometheus (v3.5.0, `scrape/scrape.go`): `endOfRunStaleness` (1516-1577) llama a `append` con cuerpo vacío, que pone marca en todas las series, y luego a `reportStale` (2143+), que escribe `StaleNaN` en `up`. Línea 12 dice que «las dos» «no se observaron en un Prometheus real», y el párrafo «Reinicio normal» (línea 15) solo modela un reinicio con `up == 0`. Aun así, las conclusiones para el operador valen: medí un reinicio con «las dos» y retorno 2, 3 o 5 min después, con contador previo 1 (`myrnboth.py`). Con k=0 no dispara nunca. Con k de 1 a 4 dispara 5 min después de la vuelta, con el mismo retraso de 4 a 1 min que RN. Por eso es AMARILLO.
- **Falta decir qué mecanismo produce «solo `X`» y «solo `up`».** El arbitraje pedía «por qué ocurre eso en Prometheus». «Solo `X`» es el único modelo con falso positivo, y el texto no dice qué lo causaría.
- **Las cifras suponen scrape y evaluación de 1 min.** Este proyecto usa el valor por defecto de 30 s: no hay `interval` ni en `identity-edge/observability/monitors/` ni en `kube-prometheus-stack.yaml`. A 30 s (`my30s.py`):
  - FP de `x` con hueco de 8 min dura 1.5 min, no 1;
  - RN con login 1 min después lleva 4.5 min de retraso;
  - RN con k=0 sigue sin disparar.

  Lo cualitativo se mantiene, pero los minutos dependen de esa resolución, y el texto no lo dice.

### F-10 · AMARILLO · break-glass-login.md:13 y CANDIDATAS.md:123 · Redacción que no corresponde a la medición
- **«Dispara al volver» no es exacto para huecos de 2 a 4 min.** `FP_x_2` vuelve en el minuto 7 y dispara en [10, 11], es decir 3 min después; con hueco de 3 empieza 2 min después, y con hueco de 4, 1 min después.
- **«dispara 5 minutos tras volver» (escenario L) se lee como un retraso.** Lo medido es que dispara desde la vuelta y durante 5 min (L 76-80, vuelta en 76). Además no depende del modelo: da 5 min en los cuatro, cosa que el texto no dice.
- **CANDIDATAS (2), «con 2 y 3 min dispara solo 2 y 1 min», solo vale para ninguna, `up` y las dos.** Con «solo `X`», `OM_x_2` da [7, 8, 10, 11] y `OM_x_3` da [8, 10, 11, 12]: 4 min en los dos casos.

### F-11 · AMARILLO · identity-edge/tests/unit/test_alert_rules.py:236 · Aserción tautológica
`md["runbook"] in b11_text()` siempre se cumple, porque `b11_metrics_down()` (línea 140) saca `runbook` con una regex sobre ese mismo `b11_text()`. Al quitar el literal se perdió el control del parser sobre el runbook. Se puede comprobar contra el conjunto de runbooks del diseño o contra el archivo.

### F-12 · AMARILLO · bitacoras/U02-T13.md:364 · La salida de CA-6 es de un árbol anterior en un archivo
La bitácora cita «252 archivos Markdown». En HEAD, mi corrida da **253**. Entre 5cc14b9 y de424f2, el único `.md` nuevo es `revisiones/U02-T13/ronda-4-respuesta.md`, así que el codificador corrió CA-6 antes de crear ese archivo. El código es el mismo, y mi corrida, que sí revisa los enlaces de ese archivo, pasa. No lo califico de ROJO por la invariante 3: la evidencia es de esta ronda y del mismo comando, y solo le falta un archivo de documentación del propio codificador. No es una salida de otro comando ni de otro estado del código, como la de F-04. Si el orquestador aplica la invariante al pie de la letra, se cierra volviendo a pegar la salida.

## Barrido del diff de esta ronda (0f18aaf..de424f2)
- **Sin desborde.** Los archivos que cambian son el runbook, `CANDIDATAS.md`, el archivo b11 de promtool, `theme_checks.py` (solo el docstring), `test_alert_rules.py` (solo `test_the_b11_text_is_read`), la bitácora y `revisiones/`. Todos responden a F-04 a F-08. No se tocan las reglas, el CR, `platform/observability/`, `flows.yaml` ni `vectra-risk-gitops`.
- **Sin regresiones:** CA-1 a CA-6 pasan, y mutaciones, `gen` y `probe` dan lo mismo que lo versionado.

## Tareas candidatas (defectos reales fuera de alcance)
- Las mediciones de B11 (`b11_scenarios.py`, las pruebas de promtool) usan 1 min. El Prometheus del proyecto raspa y evalúa cada 30 s por defecto. Si se revisa B11 o se lleva al ruler de Loki, conviene medir a 30 s o fijar `interval` en los monitores de forma explícita. Es decisión del orquestador.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/U02-T13-r4/`:
- logs de los criterios: `ca1.log`, `ca2.log`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`, `ca56-times.txt`;
- `probe.txt`: mi corrida de su `probe`, idéntica a la versionada;
- `mut.txt`: mi corrida de `mutaciones.py`, idéntica a la versionada;
- `mysweep.txt`: barrido independiente; `my30s.txt`: medición a 30 s; `myrnboth.txt`: reinicio con «las dos»;
- `f06.txt`: F-06 en rojo y en verde; `f07.txt`: F-07 con el diseño cambiado;
- `scripts/`: los scripts de esas corridas;
- `scrape.go`: Prometheus v3.5.0, la fuente de F-09.

```
VEREDICTO: VERDE
AMARILLO|vectra-risk/identity-edge/runbooks/break-glass-login.md:12|«las dos» con stale es real (target fuera de SD) y no construido; falta suponer scrape de 1 min
INFORME: revisiones/U02-T13/ronda-4.md
```
