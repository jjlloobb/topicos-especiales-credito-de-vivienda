# Ronda 4 — U00-T02

VEREDICTO: VERDE

La tarea queda lista para fusionar. Los cuatro criterios pasan, incluido el CA-4 nuevo, y las tres mutaciones que sobrevivían en la ronda 3 ahora hacen fallar la suite. Solo queda un AMARILLO, que no bloquea.

**Contra qué juzgué.** Usé la tarea enmendada. En el worktree, `git hash-object vectra-risk/tareas/U00-T02-import-circular.md` da `f48df318bc4069a7b54c92bf52c68bf58cb94113`, que coincide. El commit 61a9655 solo añade el CA-4 y la nota de la enmienda.

**Cómo lo verifiqué.** Usé copias de `git archive 75909cb` en `scratchpad/rev-u00t02-r4/`: `repo/` con un git propio y los `node_modules` enlazados, y `mut/` para las mutaciones. `uv sync --frozen` sin red.

**Alcance y estado del worktree.**
- `wt-U00-T02` está en `75909cb` y limpio: `git status` sin salida. La copia `repo/` también quedó limpia después de `make check`, así que la generación de OpenAPI y TS no produjo diff.
- El diff total de código contra `c656de2` toca 3 archivos, todos dentro del alcance: `models/__init__.py`, `test_import_isolation.py` y `test_models_lazy_api.py`. El `__init__.py` raíz queda igual que en la base.
- `ronda-3-respuesta.md` responde F-01, F-02 y F-03. No queda ningún hallazgo sin respuesta.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | outcome y dictionary como primer import | `uv run python -I -c "import vectra_contracts.outcome" && uv run python -I -c "import vectra_contracts.dictionary"` | pasa: exit 0, sin salida |
| 2 | prueba de import aislado, lista derivada | `uv run pytest contracts/tests -q -k each_module_imports_in_isolation` | pasa: 38 passed |
| 3 | U0 sigue cumpliendo, import-linter intacto | `uv sync --frozen && make -C contracts check` | pasa: EXIT=0. ruff limpio; mypy --strict sin errores en 38 archivos; import-linter 3 KEPT y 0 broken; 502 passed sin skips; cobertura total 98 % (`models/__init__.py` 100 %); trazabilidad 3 passed; bench ok; sin diff de openapi ni de TS; vitest 8 passed |
| 4 | API pública de `models` igual, en un `python -I` limpio | `uv run pytest contracts/tests -q -k models_public_api_in_clean_interpreter` | pasa: 1 passed. El conjunto esperado se deriva con `pkgutil` sobre `m.__path__`. `dir()` y `m.api` se leen antes de cualquier otra cosa que pueda precargar `api` |

## Mutaciones contra `-k "lazy_api or isolation or public_api"`
Sin mutar: 44 passed. Corrí cada mutación por separado y al final restauré con `cmp`.

| Mutación | Resultado |
|---|---|
| `__getattr__` siempre lanza `AttributeError` | 3 failed |
| **`__getattr__` sin la rama `api`** (sobrevivía en la ronda 3) | **1 failed** |
| **`__dir__` devuelve `sorted(globals())`** (sobrevivía en la ronda 3) | **1 failed** |
| **`__dir__` sin `"api"`** (sobrevivía en la ronda 3) | **1 failed** |
| `__all__` eliminado | 2 failed |
| `__all__` sin `api` | 2 failed |
| `__all__` con nombres privados | 2 failed |
| Falta un nombre en `_LAZY_API_NAMES` | 4 failed |
| Nombre público nuevo en `api.py` | 4 failed |
| Sin `del typing` | 3 failed |
| `__getattr__` sin cachear en `globals()` | 44 passed; es equivalente, solo afecta al rendimiento |
| Guard escrito como `if (_T := typing.TYPE_CHECKING):` (mía, nueva) | 44 passed; ver F-01 |

## API de `models` en un intérprete limpio, frente a `rev-u00t02-r2/api_old.json` (c656de2)
- `from vectra_contracts.models import *` exporta **los mismos 207 nombres**, idénticos y en el mismo orden. No pierde ninguno ni añade ninguno.
- `dir()` no pierde nombres; solo añade privados: `_Any`, `_LAZY_API_NAMES`, `__all__`, `__dir__`, `__getattr__`, `_import_module`. `typing` no aparece.
- `hasattr` y la identidad con `api` dan True para todos los nombres.
- `import vectra_contracts.models` no precarga `api`, `'api' in dir(m)` es True, y `m.api` devuelve el submódulo.
- El pickle de `Empty` hace ida y vuelta, y `m.no_existe` da `AttributeError`.

## Ciclo (grimp, con aristas implícitas hijo → padre; script `rev-u00t02-r2/cyc2.py`)
- Con `exclude_type_checking_imports=True`: **NINGUNA** cadena `outcome → … → outcome`.
- Con los imports de `TYPE_CHECKING` incluidos, queda la cadena que solo existe para mypy.
- En ejecución, después de `import vectra_contracts.outcome`, `models.api` no está en `sys.modules`.

## Hallazgos

### F-01 · AMARILLO · contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:15 · Ninguna prueba protege que grimp vea el guard de `TYPE_CHECKING`
Si el guard vuelve a escribirse de una forma que grimp no reconozca (por ejemplo, la mutación con el operador `:=`), toda la suite pasa. Pero el análisis estático vuelve a ver el ciclo, como pasó en la ronda 3. No hay ningún contrato de import-linter contra ciclos, así que hoy no afecta a nada. Si se quiere fijar, puede ir a una tarea aparte.

(La lista `_LAZY_API_NAMES` escrita a mano quedó aceptada por el arbitraje y está cubierta por la prueba; no la repito.)

## Tareas candidatas (defectos reales fuera de alcance)
- Opcional: una prueba o un contrato estático que compruebe que no hay ciclo `outcome → … → outcome` con grimp, para que la ruptura del ciclo no dependa solo del orden de ejecución.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r4/ca3.txt (make check completo)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/tasks/bg1kg8iy8.output (las 12 mutaciones)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r4/api_new.json (API de `models` en 75909cb)

VEREDICTO: VERDE
AMARILLO|contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:15|Ninguna prueba protege que grimp vea el guard de TYPE_CHECKING; si se reescribe con el operador := la suite pasa y el análisis estático vuelve a ver el ciclo
INFORME: revisiones/U00-T02/ronda-4.md
