# Ronda 1 — U07-T03

VEREDICTO: NO-VERDE

Hay un ROJO y bloquea: CA-4 y CA-6, ejecutados tal como los escribe la tarea, no recolectan las pruebas. La bitácora dice que esos mismos comandos terminaron con rc=0, y eso no pudo salir de este diff. Con un modo de import que evita el choque de nombres, todo lo demás pasa.

Contexto revisado: worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u07-t03`, sha 8d90a43, base ec08f84. El hash de la tarea es 09531d55 y coincide. Al terminar, el worktree está limpio: solo hay cachés ignoradas (`.coverage`, `.hypothesis`, `platform/.tools`).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Paso 8 | `uv run pytest .../integration/test_explanations.py -v` | pasa (21 passed, 3,8 s) |
| 2 | Paso 9 | `uv run pytest .../integration/test_applicant_summaries.py -v` | pasa (16 passed) |
| 3 | Paso 10 | `uv run pytest .../integration/test_clients.py -v` | pasa (8 passed, 5,4 s) |
| 4 | Paso 11 | `HYPOTHESIS_PROFILE=ci uv run pytest .../property/test_orchestrator.py .../integration/test_orchestrator.py -v`, literal, dos veces | **falla, rc=2**: `import file mismatch`, 1 error de recolección. Con `--import-mode=importlib` da 32 passed en 79 s con la semilla 4125850450 impresa |
| 5 | Paso 12 | `uv run pytest .../test_app.py .../test_shutdown.py -v` | pasa (15 passed, 7,2 s) |
| 6 | Cobertura | el comando literal de CA-6 | **falla, rc=2**, mismo error. Con `--import-mode=importlib`: total 99,65 % y `orchestrator.py` 100 %. Hubo 1 fallo intermitente (F-03). `services.md`: `test -s` rc=0 |
| 7 | `check` de la unidad y de U1 | `make -C scoring-explainability check && make -C platform check` | pasa, rc=0 en los dos. El Makefile usa `--import-mode=importlib`; unidad 173 passed; platform 354/48 pass y 0 fail |
| 8 | Estado del plan | `git diff origin/main -- <plan> \| grep ...` | pasa: Pasos 8 a 13 en `[x] (U07-T03)` y ningún otro cambio en el texto del plan |

## Hallazgos

### F-01 · ROJO · CA-4 y CA-6 · los comandos de la tarea no corren las pruebas, y la evidencia de la bitácora es falsa
- **Causa:** `tests/property/test_orchestrator.py` y `tests/integration/test_orchestrator.py` tienen el mismo nombre de archivo. No hay `__init__.py` y el modo de import por defecto es `prepend`.
- **Salida de pytest:** `imported module 'test_orchestrator' has this __file__ attribute: .../property/test_orchestrator.py which is not the same as ... integration/test_orchestrator.py` → `1 error in 1.24s`, rc=2.
- **Barrido:** es el único nombre repetido (`find ... -name 'test_*.py' | sort | uniq -d`).
- **Evidencia falsa:** la bitácora pone como rc=0 los comandos literales de CA-4 («32 passed in 73.02s») y CA-6 («173 passed»). Esa salida solo sale con `--import-mode=importlib`, que es lo que usan el Makefile y los pares rojo-verde de la bitácora.
- **Arreglo del codificador:** nombres de archivo únicos o paquetes de prueba, y volver a correr los comandos tal como están escritos.
- **Transcripciones:** `ca4.log` y `ca6.log` en el scratchpad.

### F-02 · NARANJA · `tests/property/test_orchestrator.py` · PBT-U7-07 no cubre todas las ramas del `orchestrator`
Corrí solo las propiedades (PBT-U7-07, las dos de PBT-U7-08 y la de P-U7-01) con cobertura, perfil `ci`. `orchestrator.py` queda en **91 %**, con estas líneas sin ejercer:
- 196: `FailClosed` de `build_outcome` cuando el registro no confirma tras un camino que iba bien;
- 208-209: la política se pasa del presupuesto;
- 288-293: conflicto de idempotencia, con su log;
- 295: un 4xx da un solo intento;
- 297-298: `abandoned` y circuito abierto;
- 121: `default_jitter`.

La causa es la estrategia. Para que el registro importe, todo lo anterior tiene que salir bien. Eso ocurre más o menos 1 de cada 650 ejemplos: activo 1/3 · misma versión 1/2 · predict ok 1/6 · explain ok 1/9 · política 1/2. Además, `REGISTRY` no incluye ni `conflict` ni circuito abierto.

El 100 % de CA-6 se alcanza solo gracias a los ejemplos de integración. La invariante «una `Recommendation` solo sale con `registry_entry_id`» casi nunca se pone a prueba contra un registro que falla.

La propiedad de P-U7-01 usa `max_examples=12` sobre 250 combinaciones de latencia (AMARILLO dentro de este mismo hallazgo).

### F-03 · AMARILLO · `tests/integration/test_clients.py:196` · la prueba del bulkhead es intermitente
En la suite completa, con la máquina cargada (load ~7), falló una vez con `assert 0 == 20`: ninguna conexión había llegado a KServe tras el `sleep(0.15)`. Aislada pasó 4 de 4 veces y pasó también dentro de `make check`. La prueba depende del tiempo de pared.

### F-04 · AMARILLO · `scoring/src/scoring/orchestrator.py:209` · etiqueta de métrica equivocada
Si la `PolicySource` se pasa del presupuesto, se incrementa `DEADLINE_EXHAUSTED.labels(stage="serving_config")`. Ese tiempo se agotó en la política, no en `serving-config`.

### F-05 · AMARILLO · `orchestrator.py:77-114` · `attested_dictionary` arma un diccionario sintético
Lo construye con `label_es=feature_id` y frases vacías, solo para satisfacer `check_preconditions`. Ya está como candidata en `CANDIDATAS.md`. Es frágil si U0 llega a leer esos campos.

## Lo que se pidió decidir

**El bloqueo de la política es un hueco de diseño fuera del alcance de esta tarea, no un defecto suyo.**
- `ServingConfig` (`contracts/.../models/governance.py:42-50`) solo trae `policy_version_id`, no los parámetros.
- El diseño de U7 (`domain-entities.md:24`) dice que `cutoff`, `low_confidence_threshold` y `channel_rules` vienen de la «política activa (`policy_version_id` de `serving-config`)».
- La única ruta que sirve políticas es `GET /v1/policies` con `roles=ANA_CRO_CUM` (`routes/__init__.py:227`). No tiene scope de servicio y no hay ruta por id.
- Corregirlo exige tocar U0 y U4, y la tarea lo prohíbe expresamente: «detente y repórtalo».
- El codificador lo resolvió con una `PolicySource` inyectada, sin inventar campos en los dobles, y lo registró como bloqueante en `CANDIDATAS.md`.
- **Hay que escalarlo antes de U07-T04:** mientras no se decida, scoring no se puede desplegar.

**Procesos reales:**
- Arranqué `explainability.app.main` de verdad: `/readyz` responde 200 en 8081.
- `scoring.app.main` termina con `policy_source_undefined`, como se espera y está probado.
- El proceso real de scoring (uvicorn por `ops_server.serve`, desde `doubles/run_scoring.py`) arranca y supera el SIGTERM con la `Recommendation` y una sola entrada en el registro, leída de vuelta.
- La tarea no exige que `main` de scoring arranque en el clúster: eso es U07-T04.

**Rutas de REGISTRY:** las tres están servidas. `test_both_services_start_with_the_handlers_of_every_route_of_the_registry` compara los handlers con `REGISTRY` y pasa.

**Alcance:** el diff solo toca `scoring-explainability/`, el plan, `services.md`, `CANDIDATAS.md` y la bitácora. No hay desborde.

## Tareas candidatas (defectos reales fuera de alcance)
- Política activa para scoring: ampliar `ServingConfig` o crear una ruta con scope `governance:read-serving` (U0/U4). Bloquea el despliegue de scoring.
- Las demás que el codificador ya listó en `CANDIDATAS.md` siguen en pie: el `dictionary` de `check_preconditions`, la causa de un `:predict` caído, el scope de la precarga de explainability, el host de KServe, el texto de INF-U7-03 y la salida `-SIGTERM`.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/`:
- `ca4.log`, `ca6.log`: comandos literales, error de recolección;
- `ca4b.log`, `ca6b.log`: con `--import-mode=importlib`;
- `prop_cov.log`: cobertura de las propiedades solas, 91 %;
- `ca7a.log`, `ca7b.log`: los dos `make check`;
- `test_explanations.log`, `test_applicant_summaries.log`, `test_clients.log`, `ca5.log`: CA-1, CA-2, CA-3 y CA-5.

```
VEREDICTO: NO-VERDE
ROJO|CA-4, CA-6 (tests/property/test_orchestrator.py ~ tests/integration/test_orchestrator.py)|Los comandos de la tarea fallan con rc=2 por el nombre repetido y la bitácora afirma rc=0
INFORME: revisiones/U07-T03/ronda-1.md
```
