# Ronda 2 — U07-T03

VEREDICTO: VERDE

F-01 está corregido. Corrí yo mismo los comandos de CA-1 a CA-8 tal como están escritos en la tarea, sin flags extra, y todos terminan en 0. La recolección sigue completa: 173 pruebas, las mismas que en la ronda 1. No quedan ROJO ni NARANJA en pie en este diff; el NARANJA F-02 sigue en `CANDIDATAS.md` por tu arbitraje RL-2, no como arreglo.

Contexto: worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u07-t03`, sha a4ce52e, sobre 51a35b0. El hash de la tarea sigue siendo 09531d55. Al terminar, `git status --short` está vacío: solo hay cachés ignoradas.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Paso 8 | `uv run pytest scoring-explainability/tests/integration/test_explanations.py -v` | pasa (21 passed, 3,35 s; semilla 1357418549) |
| 2 | Paso 9 | `uv run pytest .../test_applicant_summaries.py -v` | pasa (16 passed; semilla 3232978843) |
| 3 | Paso 10 | `uv run pytest .../test_clients.py -v` | pasa (8 passed, 4,58 s) |
| 4 | Paso 11 | `HYPOTHESIS_PROFILE=ci uv run pytest .../property/test_orchestrator.py .../integration/test_orchestrator.py -v`, literal | pasa (32 passed, 45 s; semilla 1167990048 impresa) |
| 5 | Paso 12 | `uv run pytest .../test_app.py .../test_shutdown.py -v` | pasa (15 passed, 5,95 s) |
| 6 | Cobertura | el comando literal de CA-6 con `&& coverage report ... --fail-under=100`, más `test -s services.md` | pasa: 173 passed, total 99,65 %, `orchestrator.py` 100 %; `services.md` rc=0 |
| 7 | `check` de la unidad y de U1 | `make -C scoring-explainability check && make -C platform check` | pasa, rc=0. Unidad: lint, mypy, 3 contratos de import-linter, 173 passed. Platform: 707, 3 y 343 passed; 48 y 354 pass, 0 fail |
| 8 | Estado del plan | el `git diff origin/main -- <plan> \| grep ...` literal | pasa: 6 líneas `[x] (U07-T03)`; el plan tiene 6 inserciones y 6 eliminaciones contra `origin/main` (b8c60f4) |

## Lo que pediste comprobar
1. **Comandos literales:** la tabla de arriba. Ninguno lleva flags añadidos.
2. **Bitácora de la ronda 1:** está corregida y no borrada. El diff de `bitacoras/U07-T03.md` desde 8d90a43 tiene 52 inserciones y 0 eliminaciones. La sección «Ronda 2 → Corrección de la ronda 1» reconoce que CA-4 y CA-6 de la ronda 1 se corrieron con `--import-mode=importlib` y no con el comando literal. Las salidas que publica para la ronda 2 coinciden en forma con las mías: 32 y 173 passed, 99,65 %.
3. **Los `__init__.py`:** no rompen ninguna de las dos recolecciones.
   - El `Makefile`, con `--import-mode=importlib`, sigue recolectando 173 pruebas, igual que en la ronda 1.
   - `make -C platform check` pasa entero.
4. **Regresiones:** no hay. Los cambios de la ronda 2 son solo los dos `__init__.py` vacíos, `CANDIDATAS.md`, la bitácora y `revisiones/U07-T03/ronda-1.md`. El código de `src` no cambió.

## Hallazgos
F-02 a F-05 están registrados en `CANDIDATAS.md`, en las cuatro líneas nuevas con la cita del informe de la ronda 1. Como ninguno tiene un arreglo en el código, los repito aquí para dejar constancia:
- F-02 · NARANJA: las propiedades solas dejan `orchestrator.py` en 91 %. Está en `CANDIDATAS.md`.
- F-03 · AMARILLO: la prueba del bulkhead depende del tiempo de pared. En esta ronda pasó en las tres corridas (CA-3, CA-6 y `make check`).
- F-04 · AMARILLO: el `stage` de la métrica cuando la política se pasa del presupuesto está mal puesto.
- F-05 · AMARILLO: `attested_dictionary` arma un diccionario sintético.

### F-06 · AMARILLO · `tests/integration/__init__.py`, `tests/property/__init__.py` · nombres de paquete que pueden chocar con otras unidades
Los paquetes nuevos se llaman `integration` y `property` a nivel raíz. Ya existen `platform/tests/integration.py` y `decision-registry/tests/property/__init__.py`. Si alguna vez una sola sesión de pytest junta varias unidades, volverá el `import file mismatch`. Hoy ningún comando de la tarea, del `Makefile` ni de platform lo provoca. No bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- Nombres de paquete de prueba únicos por unidad (F-06).
- Siguen las de la ronda 1, ya registradas. La fuente de la política la decidió el usuario y va en U04-T09 (PR #123); no se revisó en esta ronda.

## Rutas de transcripciones largas
Todas en `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/r2/`:
- `ca1.log`, `ca2.log`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`: CA-1 a CA-6;
- `ca7a.log`, `ca7b.log`: los dos `make check`;
- `ca8.log`: la salida del `grep` del plan.

```
VEREDICTO: VERDE
AMARILLO|scoring-explainability/tests/{integration,property}/__init__.py|Los nombres de paquete integration y property pueden chocar si una sesión de pytest junta varias unidades
INFORME: revisiones/U07-T03/ronda-2.md
```
