# Ronda 3 — U02-T13

VEREDICTO: NO-VERDE

Revisé `vectra-risk/` en HEAD 0f18aaf. La tarea está en el blob 5be4aa20…, el esperado. CA-1 a CA-6 pasan con mis propias ejecuciones (CA-5 y CA-6 en serie). Cuatro puntos del arbitraje quedan cerrados: la expresión B11, `KeycloakMetricsDown` con su runbook, los casos de F-02 y el artefacto de F-03. Dos cosas no cierran:
- **Los límites del runbook no coinciden con lo que mido.** El arbitraje pedía que `break-glass-login.md` los describiera «tal como se midieron».
- **La bitácora trae una salida de CA-2 que este diff no puede producir.**

El worktree estaba limpio antes y sigue limpio después (`git status --short` vacío). Hice todas las mutaciones sobre una copia en el scratchpad.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Reglas válidas, cada alerta dispara y no dispara | `promtool check rules … && promtool test rules …/tests/*.yaml` | pasa: 12 reglas, SUCCESS x3, exit 0 (7.6 s) |
| 2 | Runbooks | `test_runbooks.py --root identity-edge && … --operational` | pasa: «24 alertas…» y «11 runbooks operativos…», exit 0 |
| 3 | Reglas = diseño | `uv run pytest identity-edge/tests/unit/test_alert_rules.py -q` | pasa: 75 passed en 5.9 s. Solo lee archivos |
| 4 | Imagen | `uv run pytest identity-edge/tests/unit/test_keycloak_image.py -q` | pasa: 92 passed en 0.4 s. Solo parsea el Dockerfile |
| 5 | `check` de U2 con `rules` y `runbooks` | `uv sync --frozen && make -C identity-edge check` | pasa: 2473 passed en 19:08, ninguna omitida, exit 0. `rules` y `runbooks` corren dentro |
| 6 | U1, en serie después de CA-5 | `make -C platform check-local` | pasa: exit 0 en 2m50s |

## Cierre del arbitraje de la ronda 2
- **Expresión de B11: cerrado.** `BreakGlassLogin` es la expresión de B11 carácter por carácter, con `X` igual al contador de B10 más `error=""`. El CR tiene los mismos `groups` (diff vacío) y su `namespace` es `vectra-observability`.
- **`KeycloakMetricsDown`: cerrado.** Tiene SEV2, `for` de 5m y `(up{job="keycloak"} == 0) or absent(up{job="keycloak"})`. Lleva el runbook nuevo. Tiene casos con up a 0, up ausente, sin serie, y de no disparo antes del `for` (4m). El conjunto de runbooks es el plan, más `valkey-zone-failback`, más `keycloak-metrics-down`.
- **Escenarios A, A2, B, C y D: cerrado.**
  - `b11_scenarios.py gen` regenera un archivo idéntico a `identity-edge-rules-b11-test.yaml` (`diff -q` sin salida).
  - `probe` da A 2-6, A2 4-8, B 0-4, C 14-18 y D 15-19. Promtool lo confirma, porque el archivo fija la expectativa minuto a minuto y pasa.
  - B dispara también en el minuto 0, y es correcto: en ese momento la rama 2 ve `1 > X*0`.
  - Los dos casos de hueco de la ronda 2 siguen sin disparar. «Up de otro pod» y «sin up» disparan a los 7m, como dice B11.
- **F-02: cerrado.** Los casos H, H_ns, H_job, H_pod y H_noup matan `on(pod)`, `up` sin `job` y `on(namespace)`.
- **F-03: cerrado.** Corrí `mutaciones.py` sobre una copia y la salida es idéntica a `mutaciones-ronda-3.txt`: 70 mutaciones, 0 sobreviven, exit 0.
- **Runbook con los límites medidos: NO cerrado.** Ver F-05.

## Hallazgos

### F-04 · ROJO · vectra-risk/bitacoras/U02-T13.md:295 · Evidencia de CA-2 que este diff no puede producir
La bitácora pone `--root identity-edge --operational -> 4 runbooks operativos con su runbook en regla (exit 0)`. Con este diff, ese comando da **11**: en mi corrida directa, y también dentro de `make check` (ca5.log:196). «4» es lo que imprime `test_runbooks.py --operational` **sin** `--root`, es decir, los runbooks de U1. Lo comprobé: `uv run python platform/tests/test_runbooks.py --operational` imprime «4 runbooks operativos…».

Por tanto, la evidencia de la segunda mitad de CA-2 en esta ronda es de otro comando. El criterio pasa con mi ejecución. Se corrige sustituyendo esa línea por la salida real del comando que dice haber corrido.

### F-05 · NARANJA · vectra-risk/identity-edge/runbooks/break-glass-login.md:12-13 (y la misma clase en CANDIDATAS.md:123, revisiones/U02-T13/b11_scenarios.py:36 y 38, bitácora:289) · Los límites que se presentan como «medidos» no son los que se miden
Medí con promtool, un eval por minuto. Los scripts están en `scratchpad/r3/scripts/myprobe*.py`.

**Falso positivo, línea 12.** El texto dice: «Prometheus no raspa nada durante 5 a 10 minutos, sin marcas de *stale* … dispara una vez, durante 1 minuto».
- **El escenario no corresponde al texto.** G2 pone una marca `stale` en `X` (`1x5 stale _x7 1x12`) y ninguna en `up`.
- **Sin marcas de stale en ninguna serie,** que es lo que describe el texto, no hay falso positivo con huecos de 2, 4, 5, 6, 7, 8, 9, 10 ni 12 min: siempre `[]`. Lo mismo pasa si las dos series llevan `stale`.
- **Con el propio modelo de G2,** el falso positivo dura bastante más que 1 minuto:

  | Hueco de `up` | Minutos en que dispara | Duración |
  |---|---|---|
  | 2 min | [11, 12] | 2 min |
  | 4 min | [11-14] | 4 min |
  | 6 min | [12-14] | 3 min |
  | 8 min (G2) | [14] | 1 min |
  | 10 min | [] | no dispara |

  El rango «5 a 10 min» y la duración de «1 minuto» salen de un solo punto, G2, generalizado.

**Omisión, línea 13.** El texto dice «si el pod se reinicia durante un hueco de scrape de **más de 10 minutos**». Lo que mido:
- **Con el modelo de E del codificador** (`X` con stale, `up` sin stale), la omisión ya ocurre con huecos de 9 y 10 min. No hace falta pasar de 10.
- **Sin marcas de stale,** la omisión empieza en 4 min: huecos de 4, 5, 6 y 7 dan `[]`, y huecos de 2 y 3 sí disparan.
- **Hay además una omisión que el runbook no menciona.** El pod se reinicia de forma normal (up=0 durante 3 evals), el contador previo valía 1, y el primer login cae justo en el scrape en que vuelve el pod. Resultado: `[]`, nunca dispara.
- **Hay retrasos tras un reinicio.** Un login 1 min después de volver el scrape solo dispara en el minuto 14: 4 min tarde y durante 1 min.

**Lo que pido.** Escribir en el runbook y en CANDIDATAS los límites con las mediciones reales y con el modelo de staleness explícito: qué series llevan marca de stale y por qué. Si no, el falso positivo «medido» describe una condición que no lo produce.

Es la misma clase que F-01 de la ronda 2: el operador de un SEV1 lee un límite que no es cierto.

### F-06 · AMARILLO · vectra-risk/identity-edge/observability/rules/tests/ · Dos mutaciones no equivalentes de B11 sobreviven a promtool
Corrí 19 mutaciones mías sobre una copia (`scratchpad/r3/scripts/mymut.py`). Sobreviven tres:
- **`last_over_time(X[1h] offset 10m)`** en lugar de `offset 5m`.
- **Sin `error=""` en la `N` de la rama 3.** Con ella, un login fallido sobre una serie nueva dispararía un SEV1. Hoy el script del codificador solo quita el `error=""` de la rama `increase`.
- **`or K*0` sin `error=""`.** Esta es equivalente, porque `N` solo trae series con `error=""`.

Las dos no equivalentes las detecta la comparación exacta contra B11 de `test_alert_rules.py` (CA-3). Lo comprobé: `rule_problems` devuelve «la expresion no es la de B11» en los dos casos. Por eso no bloquea. Aun así, la capa de promtool no tiene ningún caso de login fallido sobre una serie nueva en la rama 3.

### F-07 · AMARILLO · vectra-risk/identity-edge/tests/unit/test_alert_rules.py:234 · Vuelve un literal de diseño en pytest
`assert md["severity"] == "SEV2" and md["for"] == "5m" …` fija con literales lo que fija B11. Es la clase de F-03 de la ronda 1, que se cerró en la ronda 2. Es un control del parser: la comparación de fondo sí lee el diseño.

### F-08 · AMARILLO · vectra-risk/identity-edge/tests/strategies/theme_checks.py:88 · Docstring obsoleto
Dice «las dos de metricas de eventos de B10», pero `design_event_metric_options()` devuelve una sola opción desde la corrección de B10.

## Barrido del diff frente a main
- **Alcance correcto.** 44 archivos. Los que no son reglas, monitores ni runbooks son la corrección de B10 arbitrada en la ronda 1 (Dockerfile, `values/common.yaml`, `rendered/*`, `keycloak.rego`, estrategias y pruebas) o la enmienda de diseño del orquestador (014c54f).
- **Sin desborde.** No se toca `platform/observability/`, `flows.yaml` ni `vectra-risk-gitops`.
- **Sin regresiones** en CA-5 ni en CA-6.

## Tareas candidatas (defectos reales fuera de alcance)
- Un login poco después de reiniciar el pod puede no disparar, o disparar con retraso, por la rama 3 de B11 (mediciones de F-05). Si se quiere cerrarlo, la vía es el ruler de Loki, que ya está en CANDIDATAS, o revisar B11. Es decisión del orquestador.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/r3/ca1.log, ca2.log, ca5.log, ca6.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/r3/mut.txt (mi corrida de `mutaciones.py`)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/bd4f46f2-73d6-4b17-847d-159bed1070fb/scratchpad/r3/scripts/ (myprobe3.py, myprobe4.py, myprobe5.py, mymut.py, pyc.py)

```
VEREDICTO: NO-VERDE
ROJO|vectra-risk/bitacoras/U02-T13.md:295|evidencia de CA-2 «4 runbooks operativos» que no puede salir de --root identity-edge (da 11)
NARANJA|vectra-risk/identity-edge/runbooks/break-glass-login.md:12-13|límites de B11 descritos como medidos que no coinciden con la medición (FP de G2 y omisión de >10 min)
INFORME: revisiones/U02-T13/ronda-3.md
```
