# Ronda 3 — U02-T11

VEREDICTO: VERDE

Revisé 0ff4364 de dos formas: el diff de la ronda (`git diff 4ec7946..0ff4364`) y el diff completo contra `main` (`git diff 1cd6bfd..0ff4364`). El hash de la tarea es 3bcb46320b883e4d93853badce5de9d0e2e63101, el esperado. Corrí CA-1 a CA-5 desde `vectra-risk/` uno detrás de otro, y CA-4 terminó antes de empezar CA-5. Los cinco terminan en 0 y no se omite ninguna prueba. Al final el worktree está limpio (`git status --short` sin salida) y sigue en 0ff4364. Las mutaciones las hice en una copia aparte (`git archive 0ff4364`), nunca en el worktree.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Descriptores | `uv run pytest identity-edge/tests/unit/test_ratelimit_config.py -q` | pasa: 34 pruebas en 38,8 s |
| 2 | `envoy-ratelimit` | `make -C identity-edge render-envoy-gateway policy-ratelimit && uv run pytest …test_envoy_gateway_values.py …test_ratelimit_deployment.py -q` | pasa: conftest 1763/1763 y 1/1; pytest 140 pruebas en 55,7 s |
| 3 | Chart de Valkey | `make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && uv run pytest …test_valkey_chart.py -q` | pasa: conftest 112/112 y 3/3 en cada entorno; kyverno `pass: 40, fail: 0` en los tres; pytest 139 pruebas en 25,8 s |
| 4 | K11 | `make -C platform check-local` | pasa: 622 pruebas en 147 s; «223 archivos Markdown sin enlaces rotos» |
| 5 | Regresión | `uv sync --frozen && make -C identity-edge check` | pasa: 2332 pruebas en 778,8 s; ninguna omitida ni deseleccionada |

## Mutaciones mías (copia en scratchpad, volviendo a renderizar cuando toca)
| Mutación | `make policy-valkey/policy-ratelimit` | pytest |
|---|---|---|
| M0, ninguna | 0 | 139 passed |
| M4, solo `sentinel-b` a `zone-a` en prod | 2 | 4 failed; **ahora falla el oráculo**, `follows_the_design[prod]` |
| M4', solo `sentinel-a` a `zone-b` en staging | 2 | 4 failed; falla `follows_the_design[staging]` |
| M4'', solo `sentinel-a` a `zone-b` en kind | 2 | 4 failed; falla `follows_the_design[kind]` |
| S1, zonas `zone-x`/`zone-y` cambiadas a la vez en diseño, values y Rego | 0 | 139 passed: ninguna prueba de pytest copia el valor |
| S7, las mismas zonas cambiadas solo en el diseño | 0 | 12 failed (oráculo, prueba de zonas y prueba nueva de Sentinel) |
| S3, `parallel-syncs` 1 a 3 cambiado a la vez | 0 | 139 passed |
| S5, `grpc` a `http` cambiado a la vez en diseño, `envoy-gateway.yaml` y Rego | 0 | 140 passed |
| S6, `grpc` a `http` cambiado solo en el diseño | 0 | 8 failed (modelo, values y la regla de conftest con `OTHER_PROTOCOL`) |
| S2 y S4, `parallel-syncs` a 2 y down-after a 3000 cambiados a la vez | 0 | 3 failed cada una (F-01 de abajo) |

## Hallazgos de la ronda 2, comprobados contra el código
- **F-01 (NARANJA), cerrado.**
  - En `test_valkey_chart.py:143-146`, la comprobación de zona ya no está dentro del bucle de `priorities`: recorre `zones`, con los cuatro StatefulSet.
  - M4, M4' y M4'' hacen fallar el oráculo por sí solo.
  - La prueba nueva `test_the_zone_of_only_one_sentinel_group_fails_the_oracle_and_conftest` (6 casos) exige `problems == ["sentinel-<g>: zona"]` y que conftest falle.
- **F-02 (NARANJA), cerrado.**
  - Busqué `zone-a`, `zone-b`, `5000`, `60000`, `parallel-syncs`, `down-after`, `failover-timeout` y `grpc` en `identity-edge/tests` y `platform/tests`. No queda ninguna copia de un valor de R6, R7 o R8 en pytest.
  - Los `zone-a` de `platform/tests/test_platform.py:37-40` vienen de antes y no están en el diff: son las zonas de kind de U1.
  - Las pruebas de lectura comprueban ahora que lo leído aparece en el texto del diseño y que cambia si cambia el diseño.
  - S1, S3 y S5 pasan; S6 y S7 fallan.
  - Los literales de Rego siguen en `valkey.rego:260-279` y `ratelimit.rego:91`, aceptados por el arbitraje.
- **F-03 (AMARILLO), cerrado.**
  - En `bitacoras/U02-T11.md:112`, la candidata aparece como «RETIRADA».
  - En la línea 164, la respuesta a F-05 dice «Retirada, sin cambio de código» y aclara que 3d66e5a no toca la bitácora.
  - No está en `CANDIDATAS.md`.
- **Lectores del diseño tras 8f78621.**
  - El commit solo cambia la línea 116 de INF-U2-04.
  - Ningún lector de `tests/strategies/*.py` usa el texto de esa línea. `zones()` lee la línea 150, que no cambió.
  - CA-3 y CA-5 pasan enteros.
- **Bitácora contra el código.**
  - La descripción del cambio coincide con el diff de e05f4a6.
  - Los números coinciden con mis corridas: 139 pruebas en CA-3, 140 en CA-2 y 2332 en CA-5; mis S6 y S7 fallan 8 y 12, como su M12 y M8 de solo diseño.
  - Su rojo de M4 (2 failed, con el oráculo pasando) es lo mismo que vi yo en la ronda 2.
- **Alcance.**
  - La ronda solo toca `test_valkey_chart.py` y `test_ratelimit_deployment.py`, más la bitácora; 8f78621 es del orquestador.
  - No hay desborde de alcance.
  - En el diff contra `main`, ningún archivo nuevo queda fuera de lo que permite la tarea.

## Hallazgos
### F-01 · AMARILLO · `identity-edge/tests/unit/test_valkey_chart.py:257-259` · los valores de mutación de los tiempos de Sentinel son literales fijos
Los casos `sentinel.downAfterMilliseconds=3000`, `failoverTimeout=30000` y `parallelSyncs=2` no copian el valor del diseño. Pero solo mutan algo mientras el diseño no tome justo ese valor. S2 y S4 lo demuestran: si el diseño pasa a 2 o a 3000, y el chart y el Rego cambian con él, fallan 3 casos que ya no mutan nada. El fallo es visible, no oculta nada, y por eso no bloquea. El codificador ya resolvió esta misma clase con `OTHER_PROTOCOL` y con `TIMINGS[n] + "0"` en los casos de conftest; aquí falta aplicar lo mismo, derivando el valor `--set` de `design.sentinel_timings()`. Los valores de zona `banco-z1` y `zona-ajena` son de la misma clase, pero que el diseño los adopte es improbable.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva.

## Notas
- Encontré en `.../scratchpad/r3/` dos archivos que no son míos: `run.sh` (21:55) y `done` (22:11). Los dejó alguien que corrió los CA en el mismo worktree y terminó antes de que empezara mi CA-1 (22:13). No los uso como evidencia. Mis logs reemplazaron los suyos y se reconocen por las líneas `real` y `caN exit`.

## Rutas de transcripciones largas
- Logs de los criterios: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/r3/ca1.log` a `.../scratchpad/r3/ca5.log`
- Resumen de las mutaciones: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/r3/mutations.log`, con el detalle en `mut-*.make.log` y `mut-*.pytest.log` del mismo directorio
- Copia de las mutaciones: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/copy3/vectra-risk`

```
VEREDICTO: VERDE
AMARILLO|identity-edge/tests/unit/test_valkey_chart.py:257-259|valores de mutación de tiempos de Sentinel fijos; dejan de mutar si el diseño adopta 3000, 30000 o 2
INFORME: revisiones/U02-T11/ronda-3.md
```
