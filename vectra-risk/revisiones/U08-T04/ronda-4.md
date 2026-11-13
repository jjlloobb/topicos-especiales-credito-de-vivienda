# Ronda 4 (acotada): U08-T04

VEREDICTO: VERDE

El ROJO de la ronda 3 queda cerrado. El modelo de PBT-U8-01 ahora tiene en cuenta la caché de `serving-config` con su propio reloj. Las dos ramas se ejercen y la prueba exige que se ejerzan. La propiedad no se aflojó. PBT-U8-01 pasó en mis 9 semillas, todas distintas de las del codificador. Las mutaciones de la guarda y de la caché mueren. CA-2, CA-6 y `make check` pasan.

Quedan dos AMARILLO, que no bloquean. El primero es una ventana teórica de no determinismo cerca del TTL; la medí y en la práctica no se alcanza. El segundo es que un caso de la prueba fija no discrimina.

Worktree: HEAD `e385a9b`, blob de la tarea `c374ce10…` (coincide). Las mutaciones las apliqué en el worktree y las revertí con `git checkout`. Después de cada una, `git status --short` salió vacío. Al terminar, el worktree tiene 0 líneas sucias. No dejé contenedores: `docker ps` al final muestra solo los 4 `kind`/`vectra-*`, que ya estaban antes (`containers-before.txt`).

## Alcance (punto 1)
- `git diff e5c352c HEAD --stat` toca 4 archivos: `test_case_machine.py`, `business-rules.md`, la bitácora y `ronda-4-respuesta.md`. Nada en `src/`.
- `grep -rn reproduce_failure vectra-risk/case-management/` no da salida (rc=1).
- **No hay desborde.**

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| CA-2 | PBT-U8-05 y PBT-U8-01 | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_evaluation.py …/test_case_machine.py -v -s` (19:37:56, carga 5,60 → 19:40:57, carga 6,72) | pasa: 6 passed en 177 s, ninguno omitido. Encabezado `hypothesis profile: ci, seed: 300680328`. `cfg_down_fresh 89`, `cfg_down_stale 39` |
| CA-6 | Semilla y cobertura | las tres órdenes de la tarea (19:40:57 → 19:47:55, carga 6,3 a 7,1) | pasa: `seed: 2154434683`. 382 passed en 408 s, 0 omitidos, TOTAL 97 %. Los 8 módulos suman 650 sentencias y 126 ramas al 100 % |
| CA-9 | `make -C case-management check` | 19:47:55, carga 7,12 → 19:58:31, carga 6,03 | pasa: rc=0. ruff y format verdes, mypy sin errores, 5 contratos KEPT, 397 passed en 632 s, 97 %, los 8 módulos al 100 % |

## Lo verificado, punto por punto
**2. El modelo de la caché**
- **Reloj propio.** `self.now` avanza en `_advance`, a la par de `h.clock`, y `cache_at` es una marca del modelo. `_through_cache` no lee `w.governance`.
- **Barrido de clase.** Todos los avances del reloj pasan por `_advance`: take, sweep, reconcile, abandon, tick y abandon_decide. `_take` no llama a `serving-config`. El barrido y la API usan otros clientes (`h.sweeper.governance`, `sc_client`), así que no tocan la caché del worker.
- **Frontera.**
  - El código usa `clock() - fetched_at <= TTL` (`governance_client.py:77`, con TTL 5.0). El modelo usa `<`.
  - `FakeClock` es la hora real más un desplazamiento, así que la edad en el código es la edad del modelo más el tiempo real transcurrido (δ). `fetched_at` se fija al volver el fetch, algo después que `cache_at`.
  - Con edad del modelo exactamente 5, δ > 0 hace que el código también la vea vencida: coinciden.
  - Con edad del modelo entre 1 y 4 (solo se llega con `tick(1)`), pueden discrepar si δ > 5 − edad. Ver F-01.
- **`start` avanza 10 s.** El modelo parte con `cache_at=None`, es decir, vencida. La caché del cliente queda con edad ≥ 10 + δ, también vencida. Coinciden al empezar cada ejemplo. Esto no evita la rama fresca: la caché fresca nace dentro del ejemplo, en un `_late` sin avance de reloj. El guion `late_cfg_fresh` la fuerza.
- **Las dos ramas, ejercidas y exigidas.** `assert STATS["cfg_down_fresh"] > 0 and STATS["cfg_down_stale"] > 0` está en el perfil `ci`. Los dos contadores salen > 0 en todas mis corridas (tabla de abajo).

**3. La propiedad no se aflojó**
- `git diff 989ecad HEAD -- case-management/tests/property` cambia solo la PBT, porque la ronda 3 no la tocó. No se quita ninguna línea `assert`: las 5 que aparecen son nuevas. `assert applied is current` y `snapshot(...) == before` siguen igual.
- **Guarda de toma anulada** (las 4 con `OR true`, script `mguard.py` de la ronda 3, semilla 4242): `assert True is False` con `start(script='late_after_thaw')`, `1 failed` en 11 s. **Muere.**
- **TTL de 0 s en el código:** `assert 'en_sincronizacion' == 'listo'` con `start(script='late_cfg_fresh')`, `1 failed` en 23 s. **Muere.**
- **Servir la caché vencida con governance caído** (excepción o respuesta distinta de 200, con caché presente): `assert (2016 - 2015) == 0` con `result(kind=('cfg_down',))`, `1 failed` en 142 s. **Muere.**

**4. Estabilidad** (`HYPOTHESIS_PROFILE=ci … -k pbt_u8_01 --hypothesis-seed=N`, en serie; la carga es la media de 1 min al empezar)

| Semilla | Inicio y carga | Resultado | fresh/stale | Tiempo |
|---|---|---|---|---|
| 11 | 19:04:52 · 4,18 | 1 passed | 218/52 | 187 s |
| 777 | 19:08:02 · 8,53 | 1 passed | 114/70 | 189 s |
| 2026 | 19:11:13 · 6,36 | 1 passed | 64/26 | 194 s |
| 4242 | 19:14:31 · 6,26 | 1 passed | 114/51 | 181 s |
| 31337 | 19:17:34 · 9,75 | 1 passed | 71/48 | 167 s |
| 55555 | 19:20:24 · 5,87 | 1 passed | 121/52 | 163 s |
| 90210 | 19:23:11 · 5,98 | 1 passed | 68/52 | 137 s |
| 123456789 | 19:25:31 · 4,33 | 1 passed | 93/35 | 168 s |
| 3141592 | 19:28:26 · 6,37 | 1 passed | 114/28 | 160 s |

- Terminó a las 19:31:08, con carga 7,33.
- **La semilla de mi `make check` de la ronda 3 no está disponible.** `check.log` corrió con `-q` y no imprime el encabezado; solo trae el blob. Por eso no está en la tabla.
- **La prueba fija sí reproduce la secuencia mínima de la ronda 3.**
  - En `[late_after_thaw]`, `stale[-1]` es la toma C, la vigente; luego viene `late_result(C, ('cfg_down',))`.
  - Con el modelo viejo (`return kind` en lugar de `("rec", …) if fresh`) falla con el mismo `assert 'listo' == 'en_sincronizacion'` de la ronda 3. `[late_after_retry]` también falla así (`fixed-oldmodel.log`).
  - Con HEAD: 3 passed.

**5. BR-U8-08 (F-02 de la ronda 3).** La frase es exacta:
- dice que la condición es suficiente y no necesaria;
- dice que el reloj que cuenta es el de las tomas: `job_queue.py:76` fija `locked_until`;
- los `INSERT INTO evaluation_jobs` de `sweeps.py:71`, `api.py:256` e `intake.py:127` no lo fijan, así que nace `NULL`, como dice la frase.

**F-02 de la ronda 3: cerrado.**

## Hallazgos
### F-01 · AMARILLO · `test_case_machine.py` `_through_cache` · El `<` cubre la edad 5, pero no las edades 1 a 4 frente al tiempo real
- **El problema.** El docstring dice que el tiempo real «solo suma» y que por eso basta con `<`. Eso cubre la edad exacta de 5 s. No cubre otro caso: con la edad del modelo en 4 s (cuatro `tick(1)` seguidos entre el refresco y un `late_result` con `cfg_down`), el código vence la caché si δ > 1 s. En ese caso el modelo espera `listo` y la base dice `en_sincronizacion`, y la PBT fallaría según la semilla y la carga.
- **Lo que medí.** Instrumenté la prueba de forma temporal (revertido) con la semilla 11 y carga 7 (`diag-11.log`):
  - las 218 veces que la rama fresca se ejerció, la edad del modelo fue 0,0;
  - nunca hubo edades de 1 a 4;
  - el δ máximo fue 0,425 s.
- **Por qué no bloquea.** Llegar a la ventana exige cuatro `tick(1)` consecutivos (≈ 1/36 cada uno) seguidos de `late_result` con `cfg_down`. Además, δ tiene que pasar de 1 s. En la práctica no se alcanza.
- **La consecuencia.** La frontera del TTL no queda ejercida: la mutación `<=` → `<` del código no se detectaría.
- **Arreglo posible.** Quitar la parte real del reloj en la PBT, o no ofrecer ticks que sumen menos de 5 s.

### F-02 · AMARILLO · `test_cfg_down_after_a_script_…[late_after_retake]` · Un caso de la prueba fija no discrimina
- En `late_after_retake`, `stale` vale `[A]` y A no es la toma vigente (B ya se aplicó). `late_result(A, cfg_down)` se descarta, así que el caso no espera `listo`, aunque el docstring diga «un `late_result` con la toma vigente… el modelo espera `listo`».
- Con el modelo viejo este caso **pasa** (`fixed-oldmodel.log`: 2 failed, 1 passed).
- El «3 failed» de la bitácora con «caché siempre vencida» viene de la aserción del contador, no del comportamiento.
- Los otros dos casos sí discriminan.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. F-01 puede ir como candidata si el orquestador no la quiere en esta tarea: congelar la parte real de `FakeClock` en PBT-U8-01 para que la frontera del TTL quede determinista y ejercida.

## Rutas de transcripciones largas
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/49cc091b-165b-462c-bd21-884f08200687/scratchpad/rev4-u08-t04/`:
- semillas: `seeds.txt` y `seed-<N>.log` (una por semilla);
- diagnóstico de la frontera: `diag-11.log`;
- prueba fija con el modelo viejo: `fixed-oldmodel.log`;
- mutaciones: `mut-guard.log`, `mut-ttl0.log`, `mut-stale.log`;
- criterios: `crit.txt`, `ca2.log`, `ca6a.log`, `ca6b.log`, `ca6c.log`, `check.log`;
- scripts: `seeds.sh`, `crit.sh`, `diag.py`, `mcache.py`;
- `containers-before.txt`.

```
VEREDICTO: VERDE
AMARILLO|case-management/tests/property/test_case_machine.py (_through_cache)|El `<` cubre la edad 5 pero no las edades 1 a 4 frente al tiempo real; ventana no alcanzada (edad 0 en 218/218, δ máx 0,425 s)
AMARILLO|case-management/tests/property/test_case_machine.py (test_cfg_down_after_a_script…[late_after_retake])|El caso retake no discrimina: la toma no es la vigente y pasa con el modelo viejo
INFORME: revisiones/U08-T04/ronda-4.md
```
