# Ronda 2 — U00-T03

VEREDICTO: NO-VERDE. No hay ROJO. Quedan en pie dos NARANJA, y uno de ellos (F-01) es la misma clase de ruta que R2-01 decía cerrar.

Revisé la rama `tarea/U00-T03` en HEAD `1fc5368`, con el diff de la ronda `c3ce006..1fc5368`. El blob de la tarea es `6606d212…`, como se esperaba. Al terminar, `git status --short` del worktree no muestra nada: quedó limpio.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Anidar sin token | `uv run pytest contracts/tests/unit/test_outcome.py -v -k nest` | pasa, 5/5 |
| 2 | La capa 2 sigue cerrada | `uv run pytest contracts/tests/unit/test_outcome.py -v` | pasa, 31/31 |
| 3 | `read_wire` y `from_wire` | `… -k "read_wire or from_wire"` | pasa, 10/10 |
| 4 | PBT-U0-01 | `HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests/property/test_logic.py -v` | pasa, 15/15. La semilla no se imprime (F-05 de la ronda 1, ya en candidatas) |
| 5 | Token cerrado en el workspace (prueba AST) | `uv run pytest contracts/tests/unit/test_token_privado_workspace.py -v -s` | pasa, 16/16: 13 raíces, 545 de 548 archivos. Ver F-01 |
| 6 | U8 sin el token | `! grep` sobre `*.py`, `lint-imports --config case-management/.importlinter` | el grep queda limpio y salen 4 contratos KEPT |
| 7 | La sonda del revisor ya no sirve | `uv run python -I …/scripts/probe.py case-management/tests/doubles` | `ImportError: _CONTEXT`, rc=1 |
| 8 | Documentación | los tres grep | encuentran líneas en los cinco archivos |
| make | `make -C contracts check` | en serie, con carga de 13,6 a 15,7 | **rc=2**, solo en `bench_gate`: pipeline p95 de 6,77 ms con límite de 5. Las 531 pruebas, la cobertura y la trazabilidad pasan. Los pasos que no se alcanzaron (openapi, generación de TS, `git diff --exit-code`, typecheck, lint y test de TS, comprobaciones finales) los corrí a mano: todos rc=0. Corrí el bench alternando rama y base con carga de 21 a 25. La rama falla una vez y pasa otra (pipeline p95 entre 1,25 y 6,76 ms). `derive` y pipeline no tocan `outcome`. **Es carga, no el diff.** |
| make | `make -C case-management check` | carga de 15,7 a 27 | rc=0, 191 pruebas, 4 contratos KEPT |

**`test_p_u7_01_…_before_1_s`.** La corrí aislada 5 veces en la rama y 5 en la base, alternando y con la misma carga (17 a 30). En la base usé el `src` de `vectra_contracts` de `c3ce006` por `PYTHONPATH`. Pasó 5/5 en la rama (7,7 a 12,3 s) y 5/5 en la base (8,4 a 11,3 s), sin diferencia. Un microbench de `from_wire` alternado da entre 80 y 560 µs por llamada en las dos versiones: el ruido de la carga tapa cualquier diferencia. La prueba mide un umbral de 1 s con retrasos inyectados de 0,2 a 2 s, así que la `ContextVar` (del orden de µs) no puede explicar un fallo. **Conclusión: no hay latencia medible que venga del diff.**

**Usos legítimos.**
- U7: las integraciones `test_orchestrator.py`, `test_shutdown.py` y `test_edges.py`, que leen con `from_wire`, dan 67/67.
- U8: los dobles que usan `from_wire` pasan dentro de su `make`.
- U3 (`decision-registry`) no importa `outcome` (`grep` vacío), así que no hay nada que verificar ahí.

## Hallazgos
### F-01 · NARANJA · `outcome/__init__.py:41-56,144-150` · Se fabrican `Ready` y `Recommendation` sin `_internal`. La primera ruta es un import estático que la prueba AST no ve.
El espía de la ronda 1 (`robo.py`) ya no funciona: sale `ContractViolation: Evil no es un contenedor`. La ventana de acuñación se sigue alcanzando por otras rutas. En todas, la `Recommendation` sale con `registry_entry_id='inventado'` y el `Ready` sale fuera de `check_preconditions`:
- **Por nombre, estático** (`probes/por_nombre.out`): `from vectra_contracts.outcome import _minting` seguido de `with _minting(): Recommendation.model_validate_json(raw)`. El detector AST, aplicado a esa fuente, devuelve `[]`, y import-linter no lo ve porque prohíbe módulos, no nombres. Es la misma clase que R2-01: `outcome` expone como atributo un equivalente del token. En `main` no existía (la ronda 1 lo introdujo como `_context` y la ronda 2 lo convirtió en `_minting`).
- **`__module__` falso** (`variantes.out`, línea A): `class Evil(StrictModel): __module__ = "vectra_contracts.falso"`. La «lista cerrada» es en realidad un `startswith` sobre un atributo que controla quien llama. Variante B2: una subclase de `CaseDetail` con `__module__` reasignado.
- **Espía sobre `CaseDetail.model_validate_json`** (línea D): `read_wire` llama a ese método dentro de `_minting()`, así que el espía acuña sin tener el token. R2-01 nombraba justamente esta ruta. `test_read_wire_does_not_leak_the_token_through_the_context_of_a_contract_model` solo comprueba que no haya token en `context`, no que el espía no pueda fabricar.
- **asyncio** (línea E): una tarea creada dentro de la ventana hereda la copia del contexto con el token y fabrica después de que `read_wire` termina.

Lo que sí está bien:
- Un genérico `Page[Evil]` queda rechazado: su `__module__` es `__main__`.
- La `ContextVar` vuelve a `None` tras una excepción.
- Otra tarea concurrente no ve el token.
- Sin contexto, la construcción sigue fallando.

Hay dos textos que afirman más de lo que se cumple:
- `CANDIDATAS.md` (R2-01) dice «lista cerrada de contenedores» y «ruta por nombre» cerrada, y da como abiertas solo rutas «que no se cierran con análisis estático». `_minting` sí se cierra con análisis estático, y no está listado.
- `nfr-design-patterns.md:52` dice que «un modelo ajeno no corre sus validadores con la `ContextVar` activa».

El arbitraje pedía que el cierre «diga lo que de verdad cierra», y no lo hace.

Arreglo posible:
1. Mover `_MINTING` y `_minting` a `outcome/_internal.py`, que ya está protegido por import-linter y por el AST.
2. O añadir esos nombres al detector.
3. Sustituir el `startswith` por un conjunto explícito de clases, o por `model in {…}`.
4. Corregir los dos textos.

### F-02 · cerrado · `_Guarded.model_copy`
`model_copy()`, `model_copy(deep=True)`, `model_copy(update=…)` y `__replace__` lanzan `ContractViolation`, tanto en `Recommendation` como en `Ready` (`probes/copias.out`). `copy.copy`, `deepcopy` y `pickle` devuelven instancias iguales al original, y la copia congelada rechaza `setattr`, así que no reabren la ruta.

### F-03 · cerrado · `case-management/tests/unit/test_private_token.py`
- La negativa es real y escribe solo en `tmp_path`: tras correrla, no hay archivos nuevos en `src/`.
- Hice mi propia mutación (`forbidden_modules` cambiado a `vectra_contracts.catalog`, en una copia en `mut/`) y la negativa la mata (`AssertionError`).
- Están restaurados `hasattr(views, "CONSTRUCTION"+"_TOKEN")` y `_holds_token`, este último con su propia prueba.

### F-04 · AMARILLO · `test_private_token.py:22` · `_holds_token` tiene poco alcance
Solo entra en `dict`, `list`, `tuple`, `set` y `frozenset`, hasta profundidad 3. No mira atributos de objetos, `functools.partial` ni closures. Además, la cadena partida existe solo para esquivar el grep de CA-6. No bloquea.

### F-05 · AMARILLO · `CANDIDATAS.md` · El diff no toca líneas ajenas
`git diff 7d4e5e6..1fc5368 -- CANDIDATAS.md` tiene 4 líneas borradas, y las cuatro son entradas propias de la tarea, reescritas o tachadas. Es correcto en forma; el problema es el contenido, ya cubierto en F-01.

## Tareas candidatas (defectos reales fuera de alcance)
- U0: `bench_gate` (pipeline p95 y derive p99) excede el límite con carga de 20 o más, tanto en la rama como en la base. Es intermitente.
- U0, límite aceptado en F-06 de la ronda 1: un estado de pickle manipulado (`__setstate__` con `registry_entry_id=""`) produce una instancia sellada que se anida en `CaseDetail` (`copias.out`, última línea). Equivale al ataque con `__new__`.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u00-t03-r2/`:
- CA-1 a CA-8: `ca1-8.log`
- `make` en serie: `serie.txt`, `make-contracts.log` y `make-case-management.log`
- Pasos de contracts corridos a mano: `contracts-resto.log`
- Bench y prueba de tiempo: `bench.log`, `p_u7_01.log` y `micro.out`
- Integraciones de U7: `u7-aislados.log`
- Sondas, con su salida en el `.out` del mismo nombre: `probes/robo-r2.out`, `probes/variantes.py`, `probes/por_nombre.py` y `probes/copias.py`
- Mutación de F-03: `mut/`

```
VEREDICTO: NO-VERDE
NARANJA|contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py:41-56,144-150|ventana de acuñación alcanzable sin _internal: `from vectra_contracts.outcome import _minting` (estático, el AST no lo ve), __module__ falso, espía en model_validate_json, tarea asyncio; CANDIDATAS y nfr-design afirman lista cerrada y ruta por nombre cerrada
AMARILLO|case-management/tests/unit/test_private_token.py:22|_holds_token solo entra en dict/list/tuple/set hasta profundidad 3
INFORME: revisiones/U00-T03/ronda-2.md
```
