# Ronda 2 — U08-T02

VEREDICTO: VERDE

Revisé el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u08-t02`, sha 2392da8, sobre 8ec3979. El alcance es el de «Lo que se espera de la ronda 2» de `revisiones/U08-T02/arbitraje-ronda-1.md`. Los 8 criterios pasan con mi ejecución, la contención de F-01 cumple lo arbitrado y no queda ningún ROJO ni NARANJA. Quedan dos AMARILLO nuevos que no bloquean. El worktree terminó limpio: `git status --short` da 0 líneas y `sweeps.py` quedó intacto.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`, comandos literales)
| # | Criterio | Comando | Resultado |
|---|---|---|---|
| 1 | `case_fsm` y comparación con la migración | `uv run pytest case-management/tests/unit/test_case_fsm.py -v` | pasa: 19 |
| 2 | PBT-U8-02 | `HYPOTHESIS_PROFILE=ci uv run pytest …/property/test_backoff.py -v` | pasa: 9, perfil `ci` con 500 ejemplos |
| 3 | PBT-U8-03 y ejemplos | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_decision.py …/unit/test_decision_examples.py -v` | pasa: 13, perfil `ci` |
| 4 | PBT-U8-04 | `HYPOTHESIS_PROFILE=ci uv run pytest …/property/test_views.py -v` | pasa: 16, perfil `ci` |
| 5 | import-linter | `uv run lint-imports --config case-management/.importlinter` | rc=0: 4 kept, 0 broken; `private-token` KEPT con 1 import ignorado |
| 6 | cobertura de ramas del 100 % | comando literal de CA-6 | rc=0: TOTAL 108/0/14/0, 100 %, 80 pasan |
| 7 | `logic.md` y plan | comando literal de CA-7 | rc=0: `mutmut` en las líneas 60 y 62; 5 líneas `[x]` con `(U08-T02)` |
| 8 | `make -C case-management check` | `make -C case-management check` | rc=0: ruff y mypy (24 archivos), 4 contratos kept, 188 pasan, ninguna omitida, 100 % |

No corrí `make -C platform check`: el diff 8ec3979..2392da8 no toca `platform/`.

## Verificación de lo arbitrado
**F-01, contención:**
- **Nombres del módulo.** `views.py` ya no tiene `_CONTEXT` ni ningún import del token a nivel de módulo. Mi sonda del módulo cargado da `_CONTEXT` ausente, nada parecido al token en `case_detail.__code__.co_consts` y `__closure__ = None`. `test_no_name_of_the_views_module_holds_the_token` lo comprueba.
- **Sonda de la ronda 1.** `…/scratchpad/scripts/probe.py` ya no fabrica: da `ImportError: cannot import name '_CONTEXT'`.
- **Contrato `private-token`.** Se aplica a todo `vectra_case`, con una sola excepción (`vectra_case.views -> vectra_contracts.outcome._internal`) documentada en el `.importlinter`, en `logic.md` y en `CANDIDATAS.md`. Lo probé sobre una copia en el scratchpad:
  - importar `_internal` en `sweeps.py` lo rompe (BROKEN);
  - importarlo en `decision.py` también lo rompe, así que la excepción cubre solo `views`.
- **Rojo previo, real.** Sin el contrato y con el import en `sweeps.py`, `lint-imports` termina con rc=0 (3 kept, 0 broken). Con el contrato, rc≠0. La prueba `test_another_module_importing_the_token_breaks_lint_imports` pasa.
- **Rodeo temporal registrado** en `logic.md` y en `CANDIDATAS.md`.

**F-06:** corregido. El diff de la bitácora no tiene líneas borradas, la línea original «11 + 1» sigue en la ronda 1 y la corrección a 13 está en la ronda 2.

**F-02 a F-05:** las cuatro entradas están en `CANDIDATAS.md`, cada una citando `revisiones/U08-T02/ronda-1.md`.

## Hallazgos
### R2-01 · AMARILLO · `contracts/.../outcome/__init__.py:31` (U0) · El token se alcanza por otras rutas que el contrato no ve
Hice lo que pediste: intenté llegar al token desde fuera de `case_detail` (`…/scratchpad/scripts/probe2.py`). Estas rutas **fabrican** una `Recommendation` con `registry_entry_id="inventado"`:
- `from vectra_contracts.outcome import CONSTRUCTION_TOKEN`: U0 lo reexporta sin querer, porque `outcome` lo importa a nivel de módulo. Puesto en `sweeps.py`, el contrato sigue **KEPT** (4 kept, 0 broken), porque import-linter prohíbe módulos, no nombres.
- `sys.modules["vectra_contracts.outcome._internal"]` y `importlib.import_module(...)` armado con una cadena dinámica: el análisis estático no los ve.
- Un espía sobre `CaseDetail.model_validate` captura el `context` que pasa `case_detail`.

U8 no puede cerrar estas rutas con import-linter. Es justo lo que retira U00-T03, y no lo exijo aquí. La docstring de `test_private_token.py` («ni llega a otro módulo») promete más de lo que la prueba garantiza: conviene matizarla. **Tarea candidata para U00-T03:** que `outcome` no deje `CONSTRUCTION_TOKEN` como atributo público del paquete.

### R2-02 · AMARILLO · `case-management/tests/unit/test_private_token.py:46-59` · La prueba reescribe un fuente del árbol
La prueba escribe en `src/vectra_case/sweeps.py` y lo restaura en un `finally`. Tiene dos riesgos:
- Si el proceso muere de golpe (SIGKILL o timeout de CI), el worktree queda sucio con un import prohibido.
- Si se corre en paralelo (xdist, o dos `make check` a la vez), otra prueba puede importar el `sweeps.py` alterado.

Sería mejor copiar el paquete a un `tmp_path`, o usar un `.importlinter` temporal que apunte a un módulo sonda fuera de `src`. En esta revisión no dejó residuos.

## Tareas candidatas (defectos reales fuera de alcance)
- U00-T03: quitar la reexportación de `CONSTRUCTION_TOKEN` en `vectra_contracts.outcome` (R2-01), además de la vía pública de lectura de `CaseDetail` que ya está prevista.
- U8: que `test_private_token.py` no escriba en `src/` (R2-02).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/r2-ca5.txt`, `r2-ca6.txt` y `r2-ca8.txt`
- Sonda de rutas del token: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/scripts/probe2.py`

```
VEREDICTO: VERDE
AMARILLO|contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py:31|El token sigue alcanzable como vectra_contracts.outcome.CONSTRUCTION_TOKEN sin romper private-token (para U00-T03)
INFORME: revisiones/U08-T02/ronda-2.md
```
