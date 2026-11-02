# Ronda 1 — U02-T01

VEREDICTO: NO-VERDE

Hash de la tarea: `10f44abe8d0f55027cdf6f16023b9c8bdd659ead`, coincide. Worktree `wt-U02-T01`, rama `tarea/U02-T01`, sha `a2fc046`, base `d054f11`. Todos los comandos se corrieron desde `vectra-risk/`. Añadí `--offline` para garantizar que no hubiera red. No toqué ningún clúster ni Docker.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `check` con el lock congelado | `uv sync --frozen --offline && make -C identity-edge check` | pasa (exit 0; ruff verde; `1 passed`) |
| 2 | Directorios de §1 con `.gitkeep` | el bucle `test -d` de la tarea, en el worktree y en una copia hecha con `git archive a2fc046` | pasa (no imprime nada; los directorios aparecen en el archive, así que tienen sus `.gitkeep` versionados) |
| 3 | La prueba lee de vuelta el perfil del workspace | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q -k hypothesis_profile` | pasa (`1 passed`; `--collect-only` recoge exactamente 1 prueba) |
| 4 | U0 y U1 no se rompen | `uv sync --frozen && uv run pytest contracts/tests -q -x -p no:cacheprovider && uv run ruff check identity-edge platform contracts` | pasa (`455 passed`, `All checks passed!`) |

### Mutaciones (en una copia aislada bajo `rev-u02t01-r1/copy/`, con su propio venv)
- Una prueba rota en `identity-edge/tests/unit` hace que `make check` termine en 2. Falla como debe.
- Un `import os` sin usar en `identity-edge/tools/bad.py` da `F401` y `make check` termina en 2. Falla como debe.
- Con un `conftest.py` de identity-edge vacío, CA-3 da `1 failed` y `check` termina en 2. Falla como debe.
- Sin `conftest.py` y sin `HYPOTHESIS_PROFILE`, CA-3 da `1 failed` (`default != dev`). Falla como debe.
- Si el conftest de U0 carga siempre `"dev"`, CA-3 con `ci` da `1 failed`. Falla como debe.
- Con `nightly` y sin la variable, la prueba pasa. `make -C <ruta> check` también pasa si se lanza desde `/`.

### Efectos colaterales sobre la suite de `contracts`
- `testpaths` no cambió. `pytest` sin argumentos sigue recogiendo 455 pruebas, ninguna de identity-edge.
- La sesión combinada `contracts/tests identity-edge/tests` da `456 passed`, en los dos órdenes y con los perfiles `ci` y `dev`.
- `contracts/tests` también da `455 passed` al estilo de CI (`--rootdir=contracts/tests --import-mode=importlib`).
- El conftest de U0 se ejecuta dos veces en una sesión combinada, pero `register_profile` sobrescribe el perfil del mismo nombre y no se ve ningún efecto. Lo único que se nota es la cabecera duplicada (F-02).
- Ojo: en la copia, `test_br_u0_94_codeowners` falló porque mi copia no incluía el `.github/CODEOWNERS` de la raíz del repo. Es un artefacto de cómo hice la copia: en el worktree pasa.

### `uv.lock` y CI
- El lock suma 6 líneas: el miembro `vectra-identity-edge` y un paquete `source = { virtual = "identity-edge" }` sin dependencias. Es coherente con un `pyproject.toml` sin `build-system` y con `dependencies = []`. `uv lock --check --offline` lo resuelve en 1 ms.
- CI no queda roto. Todos los workflows hacen `uv sync --frozen`, que acepta el lock nuevo. `contracts.yml` solo lintea `contracts`.
- Ningún workflow corre `identity-edge`, ni `make -C identity-edge check` ni sus pruebas. La tarea dejaba fuera `.github/workflows/`, así que no es desborde; va como candidata.

## Hallazgos
### F-01 · NARANJA · vectra-risk/pyproject.toml:70 · Exención de ruff general e innecesaria para `identity-edge/tests/**`
El diff añade `"identity-edge/tests/**" = ["S", "B", "E501", "BLE", "T20", "I001"]`. Ese código no necesita la exención: `S101` y `E501` ya están ignorados en todo el proyecto (líneas 62–64). Lo comprobé quitando la línea en la copia: `uv run ruff check identity-edge` sigue dando `All checks passed!`.

El efecto es debilitar el mismo `check` que crea la tarea. Con un `try/except Exception: pass` en `identity-edge/tests/unit/test_x.py`, ruff da `All checks passed!`. El mismo archivo en `identity-edge/tools/` da `S110` y `BLE001`. La bitácora lo nombra («per-file-ignore de tests») pero no lo justifica.

Arreglo: quitar la línea. Si una regla llega a hacer falta, exentar esa regla concreta y justificarla.

### F-02 · AMARILLO · vectra-risk/identity-edge/tests/conftest.py:13 · Cabecera del perfil duplicada en una sesión combinada
Reexportar `pytest_report_header` hace que `pytest contracts/tests identity-edge/tests` imprima dos veces `hypothesis profile: ci`. Es cosmético.

### F-03 · AMARILLO · vectra-risk/identity-edge/tests/unit/test_hypothesis_profile.py:9 · Repite el literal `"dev"` del conftest de U0
La prueba repite el valor por defecto de U0. Si U0 cambia ese valor, la prueba falla sin que haya un defecto real. Sería más robusto leer el valor por defecto del módulo de U0, o comparar también los ajustes (`max_examples`) con `settings.get_profile(expected)`.

Nota sin severidad: §1 del plan menciona `tests/e2e/` y `tests/load/`, pero CA-2 no los pide y llegan con los Pasos 13 y 14. No es un defecto de esta tarea.

## Tareas candidatas (defectos reales fuera de alcance)
- CI no ejecuta `make -C identity-edge check` ni `identity-edge/tests`. Hace falta un workflow, o una llamada a `tests.yml` con `path: identity-edge/tests`, para que el `check` de U2 bloquee PRs. La tarea excluía `.github/workflows/`. El codificador no lo apuntó en `CANDIDATAS.md`.

## Evidencia de la bitácora
Las afirmaciones del codificador coinciden con lo que obtuve: el rojo `assert 'default' == 'ci'`, `1 passed`, `455 passed` y ruff verde. Que la suite tarde 0,01 s se explica: es una sola prueba sin estado externo y comprobé que falla si se quita el estado (las mutaciones de arriba).

## Estado final
Al terminar, el worktree queda limpio (`git status --short` vacío) en `a2fc046ddac94362f85ab5f70d25c8ea009c5b6d`, rama `tarea/U02-T01`. Las únicas escrituras fueron cachés ignoradas (`.venv`, `__pycache__`, `.hypothesis`).

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t01-r1/logs/ca1.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t01-r1/logs/ca4.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t01-r1/logs/combined.txt (sesión combinada en la copia; su único fallo es el de CODEOWNERS que falta en la copia)

VEREDICTO: NO-VERDE
NARANJA|vectra-risk/pyproject.toml:70|Exención de ruff general e innecesaria para identity-edge/tests/** que debilita el check
AMARILLO|vectra-risk/identity-edge/tests/conftest.py:13|Cabecera del perfil de Hypothesis duplicada en una sesión combinada
AMARILLO|vectra-risk/identity-edge/tests/unit/test_hypothesis_profile.py:9|La prueba repite el literal "dev" del conftest de U0
INFORME: revisiones/U02-T01/ronda-1.md
