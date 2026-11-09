# Ronda 2 — U03-T03 (sha `62254e2`)

VEREDICTO: VERDE

Los dos ROJO de la ronda 1 están corregidos, y corrí yo los rojos de cada uno. CA-1 a CA-6 pasan con mis propias corridas, con la máquina poco cargada (load 2 a 6 en 8 núcleos). Queda en pie un NARANJA en la prueba de volumen de F-04: no bloquea según RL-2 porque la forma de solicitud que usa U9 responde con mucho margen, pero va a `CANDIDATAS.md`. El worktree quedó limpio (`git status` vacío, HEAD `62254e2`).

## Criterios de aceptación, verificados por mí
| # | Resultado | Carga (`uptime`) |
|---|---|---|
| CA-1 | `101 passed in 120.29s`, 0 omitidas | 4,35 |
| CA-2 | `92 passed in 38.76s` | 3,77 |
| CA-3 | `8 passed in 6.55s`; `make -C contracts openapi` y `git diff --exit-code contracts/openapi/` dan exit 0 | — |
| CA-4 | exit 0, «41 identificadores» | — |
| CA-5 | `13 passed in 63.38s` | — |
| CA-6 U3 | exit 0: ruff, mypy, `2 kept, 0 broken`, `417 passed in 279.92s` | 3,70 |
| CA-6 U0 | exit 0, `502 passed`; el benchmark pasó a la primera, sin repetir | 5,52 |
| CA-6 U1 | exit 0 | 5,83 |

## Rojos de la ronda 1, reproducidos en la copia (`U03-T03-revisor-r2/`)
- **F-01:** con R21 aplicada fallan las dos pruebas nuevas, la de integración `test_br_u3_03_f01_…` y la unitaria `simetrico[escalamiento_con_cause]`. **Corregido.**
- **F-02:** con el código de la ronda 1 fallan los casos «tramo limpio con la última `full` inconsistente → `not_verified`» y «una `full` posterior `integra` → `verified`». El tercer caso, una inconsistente anterior a una `integra`, pasa en las dos versiones, como debe. Una mutación extra que toma cualquier `full` inconsistente y no la última rompe 3 pruebas. `last_full_verification` sigue con `{check_id, finished_at, result}`. **Corregido.**
- **F-03:** la prueba se llama ahora `test_br_u3_03_local_cause_sin_escalated_at_lo_rechaza_u0_con_422_antes_del_scope` y la contradicción entre el plan y U0 quedó en `CANDIDATAS.md`, sin tocar U0 ni el plan. **Corregido.**
- **F-05:** `run_mutations.py` copia el código a `/tmp/u3t03/copy` y corre allí. **Corregido.** Siguen vivos los contenedores huérfanos: `optimistic_lewin`, `naughty_varahamihira` y `brave_yalow`, este de otra sesión. Los tiene que detener el usuario.
- Las dos candidatas nuevas que dejé en la ronda 1 están en `CANDIDATAS.md`.

## F-04: el `GROUP BY` en SQL
**Equivalencia con el oráculo.** Corrí 40 casos aleatorios con semilla fija: poblaciones, versiones (incluida `-`), rangos con y sin versión, `include_versions` y `unattributable_range` sorteados. Comparé la respuesta de la API con `project_monitoring_daily` alimentado como en la ronda 1. Resultado: **0 diferencias**. Además, tres mutaciones del SQL mueren:
- `sum` por `max`;
- sin el filtro de versión;
- `unattributable` sin la ventana.

**Prueba de volumen.** Medí cada solicitud por separado, sin quedarme con la mejor de 3, con 320 760 filas y load de 2 a 5:
- **Caso realista** (12 rangos con versión, la forma que manda U9: «por versión, 4 rangos»): 6 de 6 respuestas 200, entre **0,14 y 0,21 s**. Aquí el mejor de 3 es una forma razonable de medir y no cambia el resultado.
- **Peor caso del codificador** (12 rangos sin versión): 10 respuestas seguidas dieron **0,55 / 0,93 / 0,83 / 1,49 / 1,86 / 1,82 / 2,17 / 3,95 / 9,63 / 3,79 s**, todas 200.

No vi ningún 504.

## Hallazgos
### F-01 · NARANJA · `test_queries.py` (`test_f04_300_mil_…`, función `best_of`) · el mejor de 3 esconde que el peor caso no cumple 2 s, y descarta los 504
- **El peor caso no se sostiene en 2 s.** Con la máquina descargada, 4 de 10 solicitudes seguidas superan los 2 s, hasta 9,6 s. La aserción `heavy_elapsed <= 2.0` pasa solo porque toma el mínimo: la primera medida es la más rápida y luego se degrada.
- **El tope de 2 s es por sentencia, no por solicitud.** `statement_timeout` corta cada una de las ~16 sentencias, nunca la solicitud entera. Por eso no aparece el 504 y la conexión única de `projections` queda tomada hasta 9,6 s. Eso dejaría sin conexión a `explanation`, que solo espera 2 s por ella.
- **La degradación está en la base, no en el servicio.** Ejecuté el SQL directo en el standby, una vez con `prepare_threshold=5` y otra con `None`, y en los dos casos crece de 0,4 a 4,9 s.
- **Los 504 no deberían descartarse.** Tal como está, `best_of` no los cuenta; habría que exigir 200 en las 3 medidas.
- **Qué hacer:** quitar o reetiquetar la aserción del peor caso, que no es la forma que usa U9, o poner un tope por solicitud.
- **Por qué no es ROJO:** la demo 7.4 no se rompe. La forma de U9 da 0,14 s estables y es la que pidió el arbitraje.

## Tareas candidatas (defectos reales fuera de alcance)
- `daily:query` no tiene tope de tiempo por solicitud, así que una consulta sin versión retiene el pool `projections` por más de 2 s.
- Las sentencias preparadas automáticamente sobre la réplica se degradan al repetirse; falta investigar la causa.

```
VEREDICTO: VERDE
NARANJA|decision-registry/tests/integration/test_queries.py (test_f04_300_mil_…, best_of)|el mejor de 3 y descartar los 504 esconden que el peor caso sin versión tarda hasta 9,6 s; el caso realista de U9 va en 0,14 s
INFORME: revisiones/U03-T03/ronda-2.md
```
