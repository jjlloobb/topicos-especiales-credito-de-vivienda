# Ronda 2 — U02-T17

VEREDICTO: VERDE

Lo revisado: el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/wt-U02-T17` en la rama `tarea/U02-T17`, HEAD `842d3f1`. El diff `31e4efb..842d3f1` toca 4 archivos: la bitácora, el runbook `rate-limit-backend-down.md`, `test_alert_rules.py` (una línea) y `identity-edge-rules-b12-b14-test.yaml` (dos comentarios). El hash de la tarea coincide (`51f9db0157e639e44007ed7ae85ed0f5c7a3ff67`). Al terminar, el worktree está limpio (`git status --short` sin salida).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Reglas válidas, B12–B14 | `promtool check rules ... && promtool test rules .../tests/*.yaml` | pasa: rc=0, 5 SUCCESS, 9,9 s |
| 2 | Runbooks en regla | `test_runbooks.py --root identity-edge` y `--operational` | pasa: rc=0, 24 alertas y 11 operativos |
| 3 | Reglas contra la tabla enmendada | `uv run pytest identity-edge/tests/unit/test_alert_rules.py -q` | pasa: 103 passed en 16,6 s (el tiempo cuadra con las traducciones de `egctl`) |
| 4 | U2 sigue cumpliendo | `uv sync --frozen && make -C identity-edge check` | pasa: rc=0, 2671 passed en 17 min 35 s, conftest 112 y 3 passed, ninguna omitida |
| 5 | U1 sigue cumpliendo (en serie, después de CA-4) | `make -C platform check-local` | pasa: rc=0, 745 passed en 2 min 55 s, 2 charts sin fallos |

## Verificación de F-01 (resuelto)
- **El runbook ya no lo da a entender.** `rate-limit-backend-down.md:9` dice que la rama por ausencia de Valkey dispara «solo si faltan las series de los dos StatefulSets». También dice que si falta uno solo no dispara, y que tampoco lo cubren `sum(...) == 0` ni `redis_up`.
- **Coincide con promtool.** Corrí un caso ad hoc, sin tocar el worktree:
  - con solo `valkey-a` (StatefulSet y `redis_up`) y el Deployment sano, `exp_alerts: []` a los 10 min;
  - sin ninguna serie de Valkey, dispara con las etiquetas `{severity: SEV2, namespace: vectra-edge}`, sin `statefulset`.

  Resultado rc=0, SUCCESS (`U02-T17-r2-rev-adhoc.log`). Eso es lo mismo que dice el runbook: «no dice cuál falta».
- **El enlace a la candidata existe.** El runbook cita «Valkey: si desaparece un solo StatefulSet, ninguna alerta avisa», que es literalmente la entrada de `CANDIDATAS.md:153`.
- **La vigilancia nueva falla si el texto cambia.** Ejecuté `runbook_hardening_problems` sobre copias mutadas del directorio de runbooks:
  - original: `[]`;
  - sin «solo si faltan las series de los dos StatefulSets»: lo detecta;
  - con esa frase cambiada por «si falta la serie de un StatefulSet»: lo detecta;
  - con «ninguna alerta cubre la pérdida de uno solo» cambiada por otra: lo detecta;
  - con «CANDIDATAS.md» cambiada por «candidatas»: lo detecta.
- **El rojo previo está registrado** en la bitácora, con el comando y la salida (`1 failed, 102 deselected`). Es coherente con el diff: las tres frases nuevas no estaban en el runbook en `31e4efb`.

## Verificación de F-03 (resuelto)
Las líneas 57 y 159 de `identity-edge-rules-b12-b14-test.yaml` ahora dicen: «un contador quieto en 0 no dispara; uno cuya primera muestra ya vale 7 dispara a 2m ... y se apaga a los 6m». Lo comparé con los casos que siguen:
- `0x30`: sin alertas a 2m ni a 20m;
- `7x40`: alerta SEV2 a 2m, y `[]` a 6m, 20m y 30m.

Esto vale para RoleConflict (líneas 58 a 89) y para LdapUnavailable (160 a 191), y CA-1 pasa con esos casos.

## Sin reapertura
`git diff --name-only 31e4efb..842d3f1` no incluye `identity-edge-rules.yaml` ni `identity-edge-rules.prometheusrule.yaml`, así que ninguna expresión de regla cambia. El único cambio en `test_alert_rules.py` agrega tres frases a `runbook_hardening_problems`. No hay trabajo fuera de alcance.

## Hallazgos
No queda ningún ROJO ni NARANJA.

### F-04 · AMARILLO · `identity-edge/tests/unit/test_alert_rules.py:806` · El enlace solo se busca como `CANDIDATAS.md`
La prueba exige la subcadena `CANDIDATAS.md`, pero no que el título citado exista en `CANDIDATAS.md`. Hoy sí existe (línea 153). Si esa entrada se cierra o se renombra, el runbook apuntaría a nada sin que ninguna prueba lo vea. No bloquea.

## Tareas candidatas
Ninguna nueva. El hueco de un solo StatefulSet de Valkey ya está en `CANDIDATAS.md:153`, y F-02 de la ronda 1 ya quedó como candidata en el arbitraje.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/3934c8af-e6f2-4277-8f10-d98bb85d8e35/scratchpad/U02-T17-r2-rev/U02-T17-r2-rev-ca1.log (también `-ca2.log`, `-ca3.log`, `-ca4.log`, `-ca5.log` y `-adhoc.log` en el mismo directorio)

Borré mis copias temporales (el YAML ad hoc y el script de mutación). Solo quedan los logs `U02-T17-r2-rev-*`.

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_alert_rules.py:806|El enlace a la candidata solo se busca como subcadena «CANDIDATAS.md», no por su título
INFORME: revisiones/U02-T17/ronda-2.md
```
