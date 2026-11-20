# Ronda 1 — U01-T21

VEREDICTO: VERDE

Revisé HEAD `3828b26` contra la base `2231db2`. El hash de la tarea es `f637a3e4dca6fa41abdcc346d57d8230db5e0554` y coincide. Corrí todo con `KUBECONFIG=/nonexistent`, con `PATH` sin `/snap/bin` y sin `gh`. Las copias de `.tools` y `.charts` y los guiones del scratchpad ya están borrados. Al terminar, `git status --short` sale vacío; solo quedan `__pycache__`, que están ignorados.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Los estados de D2 caben y el exceso sigue contando | `uv run pytest platform … -k "kind_profile and (inactive or declared or peak or budget)"` (con `--collect-only` antes) | pasa: `15 passed, 1078 deselected in 49.45s`. El filtro recoge las 4 pruebas nuevas, la de la medición, (a)/(b), (c) y (d), además de las de presupuesto y pico de U01-T20 |
| 1r | Rojo primero | la `peak_with_declared` de `2231db2`, copiada literal y puesta en lugar de la nueva, ejecutando las funciones de prueba sin tocar el código | (c) **falla** y (d) **falla**; el resto pasa |
| 2 | Archivo entero con los values de `main` | `uv run pytest platform/tests/test_kind_profile.py …` | pasa: `36 passed in 97.82s` |
| 2m | Archivo entero con los values mutados a lo que escribe `post-activation-pr` (M1 `inactive`, M2 `prod` añadida al final; restaurado con `git checkout`) | el mismo comando | pasa: `36 passed in 96.25s`. Las pruebas de presupuesto y máquina leen la mutación: `5 passed` en el filtro `fit_the_budget or fits_the_machine or in_kind_values` |
| 3 | `platform` como la CI (con `.charts`, sin `.tools`), una sola vez | `uv run pytest platform --rootdir=platform --import-mode=importlib -p no:cacheprovider -q -rs` | rc=0: `1093 passed in 239.89s`, 0 saltadas |

## Lo que pediste apretar

**1. Números del paso 1.** Rendí el chart de U6 para kind y salen idénticos a los del codificador. `prod` pide 1,0781 GiB y 0,48 núcleos, `inactive` 0,5391 y 0,24, y el predictor de `staging` 0,2695 y 0,12. El pico proyectado es de 13,7344 GiB y 10,665 núcleos, frente a 13,8 y 10,7 de tope. Un `inactive` pide menos que un `prod` en memoria y también en CPU, y `test_inactive_costs_less_than_prod_in_memory_and_cpu` lo fija.

**2. Que la regla no esconda memoria.** Comparé lo contado con lo que reserva el clúster, renderizado estado por estado, más lo que no es serving: 11,3086 GiB y 9,585 núcleos. En los 19 estados que probé se cumple que lo reservado es menor o igual que lo contado, en memoria y en CPU. La razón es estructural: un `inactive` en un hueco `prod` cuenta 1,08 GiB y reserva 0,54, así que la regla nunca cuenta de menos. Recorrí la secuencia de PR (memoria contada / reservada, en GiB):

| Paso | Declarado | Contado | Reservado | Prueba |
|---|---|---|---|---|
| D2-0 | M1 prod | 13,7344 | 12,3867 | verde |
| F8.1, PR `proxy-staging` | M1 prod, M2 staging | 13,7344 | 12,6562 | verde |
| F8.3, promoción de M2 | M1 prod, M2 staging, M2 prod | 13,7344 | 13,7344 | verde |
| F8.3, `post-activation-pr` M1 | M1 inactive, M2 staging, M2 prod | 13,7344 | 13,1953 | verde |
| F8.7, `rollback-pr` M1 (`restore` no baja a M2) | M1 prod, M2 staging, M2 prod | 13,7344 | 13,7344 | verde |
| `mark-active` | no cambia los values | — | — | — |
| F8.8, retiro de staging | M1 prod, M2 prod | 13,7344 | 13,4648 | verde |
| F8.8, `post-activation-pr` M2 (antes o después del retiro) | M1 prod, M2 inactive [, M2 staging] | 13,7344 | 12,93 / 13,20 | verde |
| paso-20, §6 (promoción, PR 2, rollback, PR 2 de M2) | 2 prod → 1+1i → 2 prod → 1+1i | 13,7344 | ≤ 13,4648 | verde |

Ningún paso de una pasada de D2 declara `staging` + 2 `prod` + 1 `inactive`, ni 1 `prod` + 2 `inactive`, así que no hay ROJO. La excepción es la segunda pasada con otro paquete (F-01 y la candidata 1).

**3. Orden.** Probé todas las permutaciones de los 19 estados y dan el mismo perfil contado. Hice además tres mutaciones de la regla. Si se quita el `sorted`, falla (d). Si un `inactive` puede ocupar también el hueco de `staging`, falla (d). Si se vuelve a sumar el `inactive` encima del pico (la regla de la base), fallan (c) y (d).

**4. Lo que no debe cambiar.** El diff no toca `BUDGET_GIB`, `MACHINE_GIB` ni `CPU_BUDGET`. Solo hay dos bloques: `peak_with_declared` y el sustituto de la prueba que se iba. Un tercer `prod` y un segundo `staging` siguen en rojo, y siguen fijados por `test_declaring_more_…` (sin cambios) y por las dos aserciones nuevas al final de (d). Las pruebas de U01-T20 siguen igual, salvo `test_a_declared_inactive_model_counts_on_top_of_the_peak`, que se borró. Medía justo la regla que la tarea manda cambiar, y la sustituye (d), que fija los mismos +2 pods cuando no queda hueco. No se aflojó nada más.

**5.** Lo cubren las filas 1r y 3 de arriba.

**7. Enmienda de §7.** Recoge lo que se decidió: comparar el mayor de los estados reales y no la suma. Explica la regla y cita los números medidos, que coinciden con los míos. No afirma que algo quepa sin dar la cifra.

**8. Alcance.** No hay desborde. El diff solo toca `test_kind_profile.py`, `DECISIONES-LOOP.md`, `CANDIDATAS.md` (una línea) y la bitácora. No toca values, requests, `promotion-tool` ni el clúster. El codificador dice que `kind_serving_kyverno.py` no cuenta presupuesto, y lo confirmé: `SWEEP_INFERENCE_SERVICES` solo se rinde para la admisión.

## Hallazgos
### F-01 · AMARILLO · `platform/tests/test_kind_profile.py`, docstring de `test_d2_states_with_an_inactive_and_no_free_prod_slot_…` · «no ocurren» no es cierto en una segunda pasada de D2
El docstring dice que «`2 prod + 1 inactive` y `1 prod + 2 inactive` no ocurren». En una pasada de D2 es cierto. Pero `paso-18-kind.md` pide ensayar el otro modo de reactivación al menos una vez (puerta de F8) y ofrece hacerlo «con otro paquete `run-N`» (Calendario, línea 151). Con el `post-activation-pr <M2>` opcional del paso 8 hecho, la promoción de M3 declara M1 prod, M2 inactive, M3 staging y M3 prod. Eso cuenta 14,2734 GiB y reserva 14,2734, por encima de 13,8. La prueba lo pone en rojo, **con razón**: no esconde nada. Por eso no lo marco ROJO contra este diff. Sin el paso opcional, el estado es 3 prod + staging: 14,8125 GiB, también rojo, y eso ya pasaba en la base. Solo corrijo la afirmación: debería decir que no ocurren dentro de una pasada.

### F-02 · AMARILLO · bitácora, tabla «Verde» · «1 prod + 2 inactive: NO cabe» mezcla lo contado con lo reservado
Lo contado es 14,2734 GiB. Lo reservado, en cambio, es 13,4648, o 13,7344 con un staging, y eso sí cabe en 13,8. La prueba lo fija en rojo por la regla de la tarea («nunca baja del pico proyectado»), no porque no quepa. La aserción de (d) `requested_gib(counted) > BUDGET_GIB` está bien. El docstring, «Sobrepasan el tope», debería decir «lo contado sobrepasa».

## Tareas candidatas (defectos reales fuera de alcance)
1. **U12 y U4, `system-verification/docs/paso-18-kind.md`, F8:** la segunda pasada de D2 con otro paquete (M3) supera el presupuesto en cualquier caso. Reserva 14,27 GiB con el PR 2 de M2 hecho y 14,81 sin él, porque el `inactive` no se retira (retiro diferido) y `rollback-pr` deja a M2 en `prod`. Además, el PR de promoción de M3 rompería `tests` en la CI. Hay que decidir si el ensayo del otro modo se hace solo con el mismo paquete y otro día UTC, si se retira el `inactive` o si se acepta el rojo. Además choca con la premisa de la decisión del 2026-11-19: en esa pasada coexisten la promoción y un `inactive`. Lo decide el usuario.
2. **U1 y U6 (no medido):** cuando se pasa de `prod` a `inactive` o al revés y cambia la plantilla del pod (por ejemplo, la prioridad), el despliegue puede crear pods extra mientras dura la actualización (*surge*), y eso no entra en ninguna cuenta. Hay que medirlo en kind con `memoria.sh durante` en el paso F8.3.

## Rutas de transcripciones largas
- Ninguna: borré los guiones y las salidas del scratchpad, como pide el despacho. Las cifras de arriba son las que imprimieron.

```
VEREDICTO: VERDE
AMARILLO|platform/tests/test_kind_profile.py, docstring de test_d2_states_with_an_inactive_and_no_free_prod_slot_…|«no ocurren» no es cierto en una segunda pasada de D2 con otro paquete
AMARILLO|bitacoras/U01-T21.md, tabla Verde|«1 prod + 2 inactive: NO cabe» mezcla lo contado con lo reservado
INFORME: revisiones/U01-T21/ronda-1.md
```
