# Ronda 1 — U04-T09

VEREDICTO: VERDE

Corrí yo los 10 criterios en `fd283bf` (worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u04-t09`, base `09dd9d8`) y pasan todos. No queda ningún ROJO ni NARANJA, solo cinco AMARILLOS. El hash de la tarea coincide (`ae832077…`). Al terminar, `git status --short` sale vacío: el worktree quedó limpio. Corrí los `make check` en serie y anoté la carga en cada uno (load entre 12 y 22).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Tipo de U0 | `uv run pytest contracts/tests/unit/test_models.py -v -k serving_config` y el `python -c` de la tarea | pasa: 12 passed, `OK` |
| 2 | OpenAPI y TS | el `python -c` de `required` y `make -C contracts check` | pasa: `OK`. La 1.ª corrida dio exit 2 solo en el bench (pipeline p95 10,7 ms con load 20). El bench no importa nada del diff. Repetí el `check` completo: exit 0, y el `git diff --exit-code` de openapi/ts limpio. Luego corrí `make -C contracts bench` tres veces más: las tres en verde (p95 0,9 a 1,2 ms). |
| 3 | compose y etag | `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property/test_serving_config.py -v` | pasa: 11 passed |
| 4 | A y luego B, en ≤ 1 s, con lectura de vuelta | `uv run pytest governance/tests/integration/test_api_policies.py -v -k serving_config` | pasa: 2 passed contra Postgres real (setup de 8,9 s del contenedor) |
| 5 | Sin política activa | `uv run pytest governance/tests/integration/test_convergence.py -v -k "sin_version_servible or no_serving_config or sin_politica"` | pasa: 2 passed |
| 6 | Scoring y proceso real | el `grep` (sin salida), `uv run pytest …test_app.py -v -k "main or policy"`, y el proceso lanzado por mí | pasa: 2 passed (11,3 s), y mi lanzamiento propio (abajo) |
| 7 | PBT de U7 | `HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property -v` | pasa: 17 passed en 452 s, semilla ci 851796612 |
| 8 | Diseños | los 4 `grep` | pasa: cada uno encuentra línea; hay nota U04-T09 en los 3 archivos |
| 9 | Checks | contracts, governance, scoring-explainability, platform y `uv lock --check`, uno por vez | pasa: 514 / 592 / 172 / 802 passed, sin skips, todos exit 0 (contracts, en la 2.ª corrida) |
| 10 | Candidatas | `grep -n "U04-T09" CANDIDATAS.md` | pasa: líneas 429 y 441, las dos «cerrada en U04-T09» |

## Los siete puntos del despacho
1. **CA-4.** La prueba hace los seis pasos en orden:
   - A la propone `cro-1` y la aprueba `cro-2`.
   - Lo servido coincide con `SELECT … FROM policies WHERE state='activa'`.
   - B se mide desde antes de aprobarla, con la caché en `LISTEN`, `wait_for(…, 1.0)` y `monotonic() - started <= 1.0`.
   - El `etag` cambia, e `If-None-Match` con el `etag` de A da 200 con B.
   - El `SELECT` final da A en `historica` y B en `activa`.

   Comprobé que la API sirve desde esa misma caché (`api.py:451`, `cache.lookup`).
2. **CA-6.** Lancé yo `…/.venv/bin/python -m scoring.app`, literal y sin `runpy`, con `REQUIRED_ENV` y los `VECTRA_*` apuntando a dobles HTTP (script: `…/rev-u04-t09-r1/script/launch_real.py`). Resultado:
   - `/readyz` dio 200.
   - Con `cutoff=0.5000`: `pol-A`, `favorable`, `[score_bajo_corte, no_vis]`.
   - Cambié el doble a `cutoff=0.3000`, esperé 5,5 s y repetí: `pol-B`, `desfavorable`, `[score_sobre_corte, no_vis]`.
3. **Sin política activa** sigue igual que hoy:
   - `compose` devuelve `None`.
   - `cache.current()` lanza `ServingConfigUnavailable("no_serving_config")`.
   - La fila queda nula.
   - Por HTTP sale 503 `dependency_unavailable`; `no_serving_config` es el detalle interno, como antes.
4. **Las dos pruebas retiradas de `test_edges.py`.** La rama desaparece de verdad: `_policy` ya no espera nada ni devuelve `None`, y se fueron `asyncio.timeout`, `DEADLINE_EXHAUSTED{stage=serving_config}` y la rama `None`. El caso que queda, una respuesta sin los tres campos, cae en `serving_config_client.py:86-89` (`ValueError`, luego `None`, luego `serving_config_unavailable`). Ver F-02.
5. **El bulkhead de KServe no se debilitó.** Lo comprobé con mutantes: subí el pool de `:predict` con un plugin de pytest fuera del repo (`plugin/mut_pool.py`). Con pool 30 la prueba falla 3/3 (`assert 30 == 20`, `29 == 20`); con pool 21 también falla 3/3 (`assert 21 == 20`). Sin mutar pasa 5/5 con load 15 a 21. Ver F-01.
6. **`oasdiff`** lo corrí por Docker (`tufin/oasdiff`, sin tocar el repo):
   - `breaking --fail-on ERR` da exit 0.
   - `changelog` da 3 `info [response-required-property-added]`.
   - `contracts/tools/version_gate.py --oasdiff <wrapper>` da exit 0.

   Sin cambio de versión mayor.
7. **Consumidores.** Los únicos que parsean `ServingConfig` son governance (`convergence.py`, `evidence.py`), scoring (`serving_config_client.py`) y explainability (`dictionary_cache.py:73`, la precarga); los tres pasan sus `check`. bias-monitoring y case-management no lo leen (en case-management solo hay un comentario en `config.py:46`). No hay console. `promotion_tool` no construye `ServingConfig`. P-2 se sostiene: el único lector de la fila (`convergence.refresh`) recompone desde `policies`.

## Hallazgos
### F-01 · AMARILLO · scoring-explainability/tests/integration/test_clients.py:190-195 · el arreglo de F-03 queda sin cerrar en CANDIDATAS
El cambio está declarado y no debilita la prueba (ver punto 5). No está en «Dentro», aunque tampoco en «Fuera», así que no lo cuento como desborde. Pero F-03 de U07-T03 sigue abierta en `CANDIDATAS.md:440` aunque el arreglo ya está aplicado. Hay que marcarla para que nadie la retome.

### F-02 · AMARILLO · tests/integration/test_edges.py (retiro) · falta una prueba con el `serving-config` de forma vieja
La justificación del retiro se apoya en «200 sin cuerpo». Falta el caso equivalente al que se retiró: un 200 con un `ServingConfig` válido de antes, sin `cutoff`, `low_confidence_threshold` ni `channel_rules`, debe dar `FailClosed(serving_config_unavailable)` sin pedir la explicación.

### F-03 · AMARILLO · test_app.py `_RealProcess` · la prueba no usa `python -m`
La prueba arranca con `python -c` más `runpy` y parchea `ops_server.serve.__kwdefaults__`. Lo cubrí con mi lanzamiento literal. Además, `scoring/app.py` queda en 96 % de cobertura (3 líneas, probablemente `main` y el guard `__main__`, que corren en el subproceso y no se miden). La prueba de «misma foto» toca el privado `_serving._ttl`.

### F-04 · AMARILLO · bitacoras/U04-T09.md (CA-7 y otros) · la bitácora resume en vez de citar
En varios criterios la bitácora resume la salida en lugar de pegar la real, y la semilla de CA-7 no está copiada; la tarea pedía la salida real de cada comando. Yo tengo la semilla: ci 851796612.

### F-05 · AMARILLO · contracts/tests/unit/test_models.py:155-161 · los rechazos no fijan la causa
Las pruebas de rechazo no fijan qué campo provoca el error. En rojo, 11 de las 12 «pasaban» por `extra_forbidden`, no por el campo que falta.

## Tareas candidatas (defectos reales fuera de alcance)
- **Orden de despliegue (U07-T04 y U8):** `ServingConfig` es `StrictModel` con `additionalProperties: false`. Un consumidor construido con el tipo viejo rechaza la respuesta nueva, y al revés: el riesgo es fallar cerrado, no un error silencioso. `oasdiff` no lo marca como incompatible. Hay que desplegar governance y sus consumidores juntos, y avisarle a U8.
- **Bench de contracts:** una sola ronda bajo carga da p95 de 10,7 ms contra un límite de 5 ms. Coincide con la candidata que ya anotó el codificador.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u04-t09-r1/`:
- CA-1 y CA-2: `ca1-ca2a.log`
- CA-3 a CA-5: `ca3-5.log`
- CA-6 y CA-7: `ca6-7.log`
- CA-8 y CA-10: `ca8-ca10.log`
- Proceso real: `real-process.log`
- `oasdiff`: `oasdiff.log`
- Mutantes del bulkhead y corridas sin mutar: `mutation-bulkhead.log`, `bulkhead-unmutated.log`
- CA-9: `ca9-summary.log`, `ca9-{contracts,governance,scoring-explainability,platform,uvlock}.log`, `ca9-contracts-r2.log`, `ca9-contracts-r2-summary.log`, `bench-alone.log`

Sin herramienta de escritura no pude crear `revisiones/U04-T09/ronda-1.md`. El texto del informe es este mensaje; lo tiene que guardar el orquestador.

```
VEREDICTO: VERDE
AMARILLO|scoring-explainability/tests/integration/test_clients.py:190|F-03 de U07-T03 arreglada pero no cerrada en CANDIDATAS.md:440
AMARILLO|scoring-explainability/tests/integration/test_edges.py|falta prueba de serving-config con la forma vieja, sin los tres campos, que dé fail-closed
AMARILLO|scoring-explainability/tests/integration/test_app.py:_RealProcess|usa runpy y no python -m; main() no se mide en cobertura (app.py 96 %)
AMARILLO|vectra-risk/bitacoras/U04-T09.md|salidas resumidas y sin la semilla de CA-7
AMARILLO|contracts/tests/unit/test_models.py:155|los rechazos no fijan el campo que falla
INFORME: revisiones/U04-T09/ronda-1.md
```
