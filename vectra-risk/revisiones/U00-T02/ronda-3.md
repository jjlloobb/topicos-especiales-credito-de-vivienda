# Ronda 3 — U00-T02

VEREDICTO: NO-VERDE

El código cumple: los tres criterios pasan, F-01 y F-02 están corregidos, y en ejecución ya no hay ciclo. Queda en pie un NARANJA. La prueba nueva no detecta que se rompa `__dir__`, ni que se pierda la rama `api` de `__getattr__`. Comprobé que esas dos mutaciones rompen la API en un intérprete limpio, y aun así todas las pruebas pasan. Como es la tercera ronda, la tarea pasa a la persona.

**Cómo lo verifiqué.** Usé copias de `git archive 7382fe3`, con el código de `8df3479`: `git diff 8df3479 7382fe3` sin `*.md` está vacío. La copia `repo/` tiene un git propio y los `node_modules` enlazados; `mut/` es para las mutaciones. Todo está en `scratchpad/rev-u00t02-r3/`, con `uv sync --frozen` sin red.

**Estado del worktree.** `wt-U00-T02` está en `7382fe3` y limpio: `git status` sin salida. La copia `repo/` también quedó limpia después de `make check`.

**Respuesta del codificador.** Está en `revisiones/U00-T02/ronda-2-respuesta.md` y responde F-01, F-02 y F-03. `ronda-1-respuesta.md` no cambió. Ningún hallazgo quedó sin respuesta.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | outcome y dictionary como primer import | `uv run python -I -c "import vectra_contracts.outcome" && uv run python -I -c "import vectra_contracts.dictionary"` | pasa: exit 0, sin salida |
| 2 | prueba de import aislado, lista derivada | `uv run pytest contracts/tests -q -k each_module_imports_in_isolation` | pasa: 38 passed |
| 3 | U0 sigue cumpliendo, import-linter intacto | `uv sync --frozen && make -C contracts check` | pasa: EXIT=0. ruff limpio; mypy --strict sin errores en 38 archivos; import-linter 3 KEPT y 0 broken; 501 passed sin skips; cobertura total 98 % (`models/__init__.py` 89 %); trazabilidad 3 passed; bench ok; sin diff de openapi ni de TS; vitest 8 passed |

## Verificación de los hallazgos de la ronda 2
- **F-01, corregido.** El `__init__.py` raíz en el sha es solo `__version__ = "0.1.0"`. `import vectra_contracts.catalog` tarda 7–10 ms (3 corridas), carga `['vectra_contracts', 'vectra_contracts.catalog']` y no carga pydantic. Coincide con la bitácora, que además corrige su afirmación falsa de la ronda 2.
- **F-02, corregido.** En un intérprete limpio, `from vectra_contracts.models import *` exporta **los mismos 207 nombres** que `api_old.json` (`c656de2`), en el mismo orden y sin filtrar nombres nuevos.
  - `import vectra_contracts.models` no precarga `api`.
  - `'api' in dir(m)` es True, y `dir()` no carga `api`.
  - `m.api` devuelve el submódulo.
  - `dir()` solo añade nombres privados: `_Any`, `_LAZY_API_NAMES`, `__all__`…
  - `hasattr` y la identidad con `api` son True para todos los nombres.
- **Ciclo.** En ejecución no lo hay: tras `import vectra_contracts.outcome`, `vectra_contracts.models.api` no está en `sys.modules`. Ver F-02 abajo sobre grimp.
- **F-03, parcialmente corregido.** El conjunto esperado se deriva de verdad con `pkgutil` sobre `models.__path__`. Las mutaciones de `__getattr__` y `__all__` se detectan; las de `__dir__` y de la rama `api` no. Ver F-01 abajo.

## Hallazgos

### F-01 · NARANJA · contracts/tests/unit/test_models_lazy_api.py:10 · La prueba de la API perezosa no detecta que se rompa `__dir__` ni la rama `api` de `__getattr__`
Corrí 10 mutaciones en `mut/` con `pytest test_models_lazy_api.py`:

| Mutación | Resultado de la prueba |
|---|---|
| `__getattr__` siempre lanza `AttributeError` | 2 failed, detectada |
| `__all__` eliminado | detectada |
| `__all__` sin `api` | detectada |
| `__all__` con nombres privados | detectada |
| Falta un nombre en `_LAZY_API_NAMES` | 3 failed, detectada |
| Nombre público nuevo en `api.py` | 3 failed, detectada |
| `__getattr__` sin `globals()[name] = value` | sobrevive; es equivalente, solo afecta al rendimiento |
| `__dir__` devuelve `sorted(globals())` | **sobrevive**, 5 passed |
| `__dir__` sin `"api"` | **sobrevive**, 5 passed |
| `__getattr__` sin la rama `api` (`value = getattr(api, name)`) | **sobrevive**, 5 passed |

Las mutantes que sobreviven sí rompen la API en un intérprete limpio:
- `__dir__` mutado: `"api" in dir(m)` y `"CaseDetail" in dir(m)` son False.
- Sin la rama `api`: `m.api` da `AttributeError`, exactamente la regresión de la ronda 2.

Con cualquiera de las dos, `-k "lazy_api or isolation"` da 43 passed, sin fallos.

**Causa.** La prueba corre en proceso y precarga `api` en la línea 10 (`from vectra_contracts.models import api`). Cuando falla `__getattr__`, el sistema de import enlaza el submódulo como atributo. Además, `test_star_import…` y `test_every_public_name…` guardan los 27 nombres en `globals()` antes de que corra `test_dir_lists_the_same_names` (línea 35). Así, `dir()` y `models.api` pasan aunque `__dir__` y `__getattr__` estén rotos.

**Arreglo posible, sin probar.** Comprobar `dir()`, `models.api` e `import *` en un subproceso `python -I` limpio, igual que hace `test_import_isolation.py`, o con un `importlib.reload` sobre un `sys.modules` limpio.

### F-02 · AMARILLO · contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:4,15 · El alias `_TYPE_CHECKING` esconde el guard a grimp
Corrí `scratchpad/rev-u00t02-r2/cyc2.py` con `exclude_type_checking_imports=True`. En `f7d1e05`, que usaba `TYPE_CHECKING` sin alias, salía «NINGUNA». Ahora vuelve a salir `outcome → models.features → models → models.api → outcome`: grimp no reconoce `if _TYPE_CHECKING:` y cuenta el `import *` de `api` como real.

En ejecución no hay ciclo (comprobado arriba). Pero el análisis estático ya no puede demostrarlo. Si algún día se añade a `.importlinter` un contrato contra ciclos, dará un falso positivo. Con `import typing` y `if typing.TYPE_CHECKING:` el guard seguiría siendo visible a grimp y no filtraría nombres en `import *`, porque `__all__` es explícito.

### F-03 · AMARILLO · contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:24 · `_LAZY_API_NAMES` está escrito a mano
Son 27 literales que duplican lo que ya define `api.py`. Está cubierto: si se añade un nombre a `api.py` y no a la lista, la prueba falla (mutación verificada). Por eso no bloquea, pero es mantenimiento manual cada vez que cambie `api.py`.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r3/ca3.txt (make check completo)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r3/api_new.json (API de `models` en 8df3479; base en `rev-u00t02-r2/api_old.json`)

VEREDICTO: NO-VERDE
NARANJA|contracts/tests/unit/test_models_lazy_api.py:10|La prueba precarga api y corre en proceso: sobreviven mutantes de __dir__ y de la rama api de __getattr__ que rompen dir()/models.api en un intérprete limpio
AMARILLO|contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:15|El alias _TYPE_CHECKING oculta el guard a grimp, que vuelve a ver el ciclo outcome→models→api→outcome
AMARILLO|contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:24|_LAZY_API_NAMES son 27 literales a mano (cubiertos por la prueba)
INFORME: revisiones/U00-T02/ronda-3.md
