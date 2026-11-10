# Ronda 2 — U09-T04

VEREDICTO: NO-VERDE

Revisé la rama `tarea/U09-T04` en `28d4a00c5eb6e118de8a5d763bdf8c7bc8196618`, con el diff de la ronda 2 `c2be6d1..28d4a00`. El blob de la tarea coincide (`f467c7e…`). El diff no toca `platform/`, así que no corrí `make -C platform check`. El worktree quedó limpio (`git status --short` vacío). Para no chocar con otros revisores, CA-2 escribe en `rev-u09-t04-r2/out/` en lugar de `/tmp/u9-$env`.

**No hay ningún ROJO.** Hay dos NARANJA. Por RL-4/RL-5, el orquestador decide si bloquean.

## Criterios de aceptación, verificados por mí (en serie)
| # | Criterio | Comando que corrí (carga antes → después) | Resultado |
|---|---|---|---|
| 2 | Render, esquema y conftest | los cuatro comandos de CA-2, más `--combine chart_set` (9,43 → 9,37; 78 s) | pasa: `Valid: 10` ×3, `650 passed` ×3, `14 passed` ×3, `146 passed`, 0 SKIPPED. Corren los 7 casos nuevos (`W 1h30m`, `W 90`, `W abc`, `n_min abc`, `n_min 30.5`, `umbral abc`, `ventana abc`) |
| 6 | Cuota y flujos | el bloque de CA-6 tal cual (9,37 → 12,56; 127 s) | pasa: `1 passed`, `211 passed`, ninguna línea «falta», F27 en la línea 179 y U9 en la línea 18 de `forbidden.yaml`, rc 0 |
| 10 (U9) | `make -C bias-monitoring check` | (12,56 → 9,40, con picos de 28; 3 619 s) | rc 0: `341 passed`, `15 passed` de propiedades, librería al 100 %, `vectra_bias` al 99,92 % (`399 passed, 7 deselected`, que son las simulaciones), `7 passed` de simulación, `test_image.py ....`, conftest 650/14 ×3, `policy-chart-u1` `pass: 18, fail: 0` ×3, `35 identificadores` |
| 11 | El resto de unidades | no lo repetí: el arbitraje lo exime | el anexo de la ronda 1 sigue siendo la evidencia |

## Lo que pediste verificar
- **F-01, casos de la ronda 1.** `edges.py` hace un render real con `-f` y las dos pasadas de conftest, y aplica `parse_policy` al ConfigMap **renderizado**. Ahora dan FAIL `stale_after` `1h30m`, `90`, `abc`, `90` (int) y `true`, y `n_min` `abc`, `30.5`, `-5`, `true` y `29`. En todos, `parse_policy` también los rechaza.
- **F-01, valores válidos y bordes.** Pasan `1h`, `01h`, umbral 1/20/5.5, ventana 7/90, `n_min` 30 y `30.0` (el chart lo renderiza como `30`). `0s`, `1800s` y `30m` dan FAIL en los dos lados, porque con el horario de 15 min el piso efectivo es 4 × 15 = 60 min.
- **`threshold_pp` y `window_days`.** El endurecimiento es correcto: rangos sin cambio y `abc`/`true`/`7.5`/`0.99`/`20.01` dan FAIL en los dos lados. Está dentro del alcance, porque es la misma regla `policy-ranges` del F-01. No hay desborde.
- **Regex.** `^\d+[smh]$` coincide con `config._DURATION` en ASCII. Solo difiere en dirección conservadora (ver F-08).
- **650 frente a 660, sin pérdida de casos.** Conftest cuenta reglas `deny` × documentos. El paquete `main` tiene common 17 + service 19 + cronjob 29 = 65 reglas; × 10 documentos = 650.
  - `cronjob.rego` pasó de 30 reglas a 29 (`git show c2be6d1:` frente a `28d4a00:`): las 2 de umbral pasan a 1, las 2 de ventana a 1, `n_min` sigue en 1 y las de `stale` pasan de 2 a 3. Neto, −1 × 10 = −10.
  - Ninguna condición desapareció. El diff de `test_chart.py` solo **agrega** filas a `OUT_OF_RANGE`, y siguen pasando los casos de umbral 0/21, ventana 6/91 y `n_min` 29.
- **F-02.** La fila 18 de `cierre-demo.md` y la bitácora coinciden cifra por cifra con el anexo: 4304, 795, 793, 855, 452, 631, 3217/2771, 1327/668 y 324/`5.266 ms`. Los destinos también: U02-T20, U03-T07 y la candidata del bench (U04-T09). Resuelto.
- **F-05.** La sección se quitó de `services.md`, y los comentarios de `Makefile:35` y `test_run_machine.py:229` ahora citan `evidence/cierre-demo.md`. Queda una referencia vieja (F-09).
- **`CANDIDATAS.md`.** `--numstat` da `2 0`: dos entradas añadidas (F-03 y `STATIC_POLICIES`) y ninguna línea quitada.

## Hallazgos

### F-06 · NARANJA · `bias-monitoring/policies/conftest/cronjob.rego` (`integer_in(policy.n_min, 30, 1000000000)`) · queda una instancia de la clase del F-01: `n_min` ≥ 1 000 000 pasa conftest y el CronJob lo rechaza
El chart pasa la política por `fromYaml`/`toYaml` (`_helpers.tpl:14`, `configmap.yaml:12`), y Helm convierte los enteros grandes a float.
- Salida de `edges2.py`:
  - `n_min=1000000` se renderiza como `'1e+06'`, conftest no da FAIL y `parse_policy` lo rechaza con `n_min_not_an_integer`.
  - Con `1000001`, `999999999` y `1000000000` pasa lo mismo, renderizados como `1000001.0`, etc.
- La cota de 1e9 es un literal inventado, que `parse_policy` no tiene (no hay techo en INF-U9-03).
- La prueba `test_a_policy_out_of_range_fails_conftest_and_the_code_refuses_it_too` llama a `parse_policy` con el dict crudo, no con el ConfigMap renderizado, y por eso no lo ve.
- Es poco probable en la práctica, pero es el mismo defecto de la compuerta de BR-U9-13.
- Arreglo: comprobar `parse_policy` sobre el ConfigMap renderizado, y quitar el techo inventado o hacer que la plantilla no convierta los enteros a float.

### F-07 · NARANJA · `bitacoras/U09-T04.md:492,496,507` · la bitácora no tiene la evidencia del rojo, del verde ni de la corrida de la ronda 2
- Los tres bloques de código contienen literalmente `{open(D+'/red-before.txt').read()}`, `{open(D+'/red-after.txt').read()}` y `{open(D+'/run.log').read()}`: plantillas sin expandir.
- El arbitraje exigía «su rojo previo registrado en la bitácora».
- Los archivos sí existen en `scratchpad/cod-u09-t04-r2/`. Los leí, y coinciden con mi corrida: antes, `FAIL=False` en `1h30m`/`90`/`abc`/`n_min abc`; después, FAIL en todos. Aun así, el registro versionado no contiene la evidencia.
- Las cifras propias de la ronda 2 (`make -C bias-monitoring check` rc 0 en 2 608 s, `platform check` rc 0 en 760 s) solo están en el `run.log` que falta.

### F-08 · AMARILLO · `cronjob.rego` `valid_duration` · RE2 frente a `re` de Python
- `\d` de Python acepta dígitos Unicode: `'１h'` da MISMATCH, porque conftest falla y `parse_policy` acepta.
- `$` de Python acepta un `\n` final.
- Las dos diferencias van en dirección conservadora: la compuerta es más estricta que el código. No bloquea.

### F-09 · AMARILLO · `CANDIDATAS.md:392` · el barrido de F-05 quedó incompleto
- La entrada «Resuelta (U09-T04)», que escribió `c690b2d`, sigue diciendo «`code/services.md` guarda la cifra medida (1 min 52 s)», y la sección ya no existe.

## Tareas candidatas
- U9: el chart convierte los enteros de la política a float por `fromYaml`/`toYaml`. Conviene una prueba que valide con `parse_policy` lo renderizado y no el dict de entrada (puede absorberse en F-06).
- U1 (ya registrada): el pánico de Kyverno en `check-chart`.

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u09-t04-r2/summary.txt`: rc, segundos y `uptime`.
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u09-t04-r2/ca2.log`, `ca6.log` y `check.log` (en la misma carpeta).
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u09-t04-r2/edges.txt` y `edges2.txt`, con los scripts `edges.py` y `edges2.py`.

```
VEREDICTO: NO-VERDE
NARANJA|bias-monitoring/policies/conftest/cronjob.rego (integer_in n_min, techo 1000000000)|n_min >= 1e6 pasa conftest y el CronJob lo rechaza (render a float), techo inventado
NARANJA|bitacoras/U09-T04.md:492,496,507|rojo, verde y corrida de la ronda 2 como plantillas {open(...)} sin expandir
AMARILLO|bias-monitoring/policies/conftest/cronjob.rego valid_duration|RE2 frente a re de Python (Unicode y \n final), dirección conservadora
AMARILLO|CANDIDATAS.md:392|sigue citando la sección quitada de code/services.md
INFORME: revisiones/U09-T04/ronda-2.md
```

## Anexo del orquestador: la evidencia de la ronda 2 que falta en la bitácora (F-07)

El codificador dejó esta evidencia en `scratchpad/cod-u09-t04-r2/`, pero la bitácora la cita con plantillas sin expandir. La copio aquí tal cual para que quede versionada. El revisor la leyó y coincide con su propia corrida.

### `red-before.txt` (el rojo previo, sobre `c2be6d1`)
```
stale_after='1h30m': conftest FAIL=False [] | parse_policy rechaza: stale_after_not_a_duration
stale_after='90': conftest FAIL=False [] | parse_policy rechaza: stale_after_not_a_duration
stale_after='abc': conftest FAIL=False [] | parse_policy rechaza: stale_after_not_a_duration
n_min='abc': conftest FAIL=False [] | parse_policy rechaza: n_min_not_an_integer
threshold_pp='abc': conftest FAIL=True ['policy-ranges: threshold_pp abc; el rango es de 1 a 20 pp'] | parse_policy rechaza: threshold_pp_not_a_number
window_days='abc': conftest FAIL=True ['policy-ranges: window_days abc; el rango es de 7 a 90 dias'] | parse_policy rechaza: window_days_not_an_integer
```

### `red-after.txt` (el verde, sobre `28d4a00`)
```
stale_after='1h30m': conftest FAIL=True ['policy-stale: stale_after 1h30m no es una duracion valida (<n>s, <n>m '] | parse_policy rechaza: stale_after_not_a_duration
stale_after='90': conftest FAIL=True ['policy-stale: stale_after 90 no es una duracion valida (<n>s, <n>m o <'] | parse_policy rechaza: stale_after_not_a_duration
stale_after='abc': conftest FAIL=True ['policy-stale: stale_after abc no es una duracion valida (<n>s, <n>m o '] | parse_policy rechaza: stale_after_not_a_duration
n_min='abc': conftest FAIL=True ['policy-ranges: n_min abc; debe ser un entero y el piso es 30'] | parse_policy rechaza: n_min_not_an_integer
threshold_pp='abc': conftest FAIL=True ['policy-ranges: threshold_pp abc; debe ser un numero de 1 a 20 pp'] | parse_policy rechaza: threshold_pp_not_a_number
window_days='abc': conftest FAIL=True ['policy-ranges: window_days abc; debe ser un entero de 7 a 90 dias'] | parse_policy rechaza: window_days_not_an_integer
```

### `run.log` (las corridas de la ronda 2, en serie)
```
uptime antes [cas]:  15:05:31 up  7:17,  1 user,  load average: 12.70, 13.16, 13.61
cas rc=0 256s
uptime despues [cas]:  15:09:47 up  7:22,  1 user,  load average: 11.82, 12.52, 13.26
uptime antes [make -C bias-monitoring check]:  15:09:47 up  7:22,  1 user,  load average: 11.82, 12.52, 13.26
make -C bias-monitoring check rc=0 2608s
uptime despues [make -C bias-monitoring check]:  15:53:15 up  8:05,  1 user,  load average: 6.86, 10.33, 12.51
uptime antes [make -C platform check]:  15:53:15 up  8:05,  1 user,  load average: 6.86, 10.33, 12.51
make -C platform check rc=0 760s
uptime despues [make -C platform check]:  16:05:55 up  8:18,  1 user,  load average: 12.51, 12.42, 12.61
FIN-R2
```
