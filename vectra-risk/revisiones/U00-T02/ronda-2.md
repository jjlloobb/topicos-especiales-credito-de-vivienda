# Ronda 2 — U00-T02

VEREDICTO: NO-VERDE

Todo lo corrí sobre copias de `git archive f7d1e05`. `repo/` tiene un git propio y `node_modules` enlazados; `mut/` es para las mutaciones. Para comparar el «antes», exporté `c656de2` y `c63b7ca` a `b0/` y `base/`. Todo está bajo `scratchpad/rev-u00t02-r2/`, con `uv sync --frozen` sin red. El worktree `wt-U00-T02` está en `f7d1e05` y limpio: `git status` sin salida. La copia `repo/` también quedó limpia después de `make check`, así que la generación de OpenAPI y TS no produjo diff.

Lo importante: el ciclo ya está roto de verdad en `models/__init__.py`. Pero el commit no contiene la mitad del cambio que la bitácora y la respuesta dicen haber hecho. Además, el `__getattr__` perezoso cambia la API pública de `models` y no tiene ninguna prueba.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | outcome y dictionary como primer import | `uv run python -I -c "import vectra_contracts.outcome" && uv run python -I -c "import vectra_contracts.dictionary"` | pasa: exit 0, sin salida |
| 2 | prueba de import aislado, lista derivada | `uv run pytest contracts/tests -q -k each_module_imports_in_isolation` | pasa: 38 passed, ahora incluye `outcome._internal` |
| 3 | U0 sigue cumpliendo, import-linter intacto | `uv sync --frozen && make -C contracts check` | pasa: EXIT=0. ruff limpio; mypy --strict sin errores en 38 archivos; import-linter con 3 KEPT y 0 broken; 496 passed sin skips; cobertura total 97 %; trazabilidad 3 passed; bench ok; sin diff de openapi ni de TS; vitest 8 passed |

**El ciclo, con grimp** (`scratchpad/rev-u00t02-r2/cyc2.py`). Al grafo le añadí las aristas implícitas «submódulo → paquete padre», porque Python ejecuta los `__init__` padres al importar un submódulo.
- Sin los imports de `TYPE_CHECKING`, que es lo que corre de verdad: en `f7d1e05` **no hay ninguna** cadena `outcome → … → outcome`. En `c63b7ca` existía `outcome → models.features → models → models.api → outcome`. El ciclo de ejecución está roto.
- Contando los imports de `TYPE_CHECKING`, queda `outcome → models.explanation → models → models.api → outcome`. Solo existe para mypy, no se ejecuta.

**Mutaciones** (en `mut/`):

| Mutación | Resultado |
|---|---|
| M1: quitar la línea del `__init__` raíz | 38 passed. Esa línea ya no hace falta |
| M3: añadir `catalog, dictionary` y que `ruff --fix` los ponga delante de `models` | 38 passed |
| M3b: el `__init__` re-exporta `outcome` y `ScoringRequest` | 38 passed |
| M4: cargar `outcome` por ruta con `spec_from_file_location` | ok |
| M5: paquete público `nuevo` con un ciclo | detectado, 2 FAILED |
| Módulos privados `_priv_a`/`_priv_b` con ciclo | detectados, 2 FAILED (F-03 de la ronda 1, corregido) |
| Módulo que imprime al importarse | detectado, 1 FAILED (F-04 de la ronda 1, corregido) |

## Hallazgos

### F-01 · ROJO · contracts/python/vectra_contracts/src/vectra_contracts/__init__.py:5 · La evidencia de la ronda 2 no pudo salir de este sha
La bitácora («restaurado a su contenido original (se retira la línea…)») y la respuesta a F-01 («se retira la línea de `vectra_contracts/__init__.py`») dicen que la quitaron. Pero `git show f7d1e05:…/vectra_contracts/__init__.py` todavía tiene `from vectra_contracts import models as _models`, y con ella el comentario de que «fija el orden que resuelve el ciclo», que ahora es falso. El commit no toca ese archivo: `git diff --stat c63b7ca..f7d1e05` no lo lista.

Por eso la evidencia de F-02 («`import vectra_contracts.catalog` … 2 módulos sin pydantic (9 ms)») tampoco corresponde a este sha. Yo mido en `f7d1e05`: **111 ms, 14 módulos `vectra*`, pydantic cargado**. Con la línea quitada (M1) obtengo 16 ms, 2 módulos y sin pydantic, que es lo que afirma la bitácora.

En resumen, **F-02 de la ronda 1 sigue sin corregir en el sha entregado** y hay evidencia que no corresponde al diff (invariante 3). La corrección es quitar la línea, como ya dice la bitácora. M1 demuestra que sin ella todo sigue pasando.

### F-02 · NARANJA · contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:14-38 · La re-exportación perezosa cambia la API pública de `models`
La tarea exige romper el ciclo «sin cambiar la API pública». Comparé `c656de2` con `f7d1e05` usando `scratchpad/rev-u00t02-r2/api.py`:

- **`from vectra_contracts.models import *`** pasa de exportar 207 nombres a 181. Pierde 28, entre ellos 27 de `api` (`CaseDetail`, `Page`, `Empty`, `InvalidParam`, `DecisionIn`, `ExplainRequest`…) y `CreditStatus`. Sin `__all__`, `import *` nunca consulta `__getattr__`. Así que **sí, la falta de `__all__` cambia algo frente a antes**: antes no hacía falta porque `api` se cargaba al importar el paquete.
- `import *` además **filtra nombres nuevos**: `TYPE_CHECKING` e `import_module`.
- **`models.api` como atributo**, en un intérprete limpio, ahora da `AttributeError: module 'vectra_contracts.models' has no attribute 'api'`. Antes devolvía el submódulo. `__getattr__` solo busca nombres dentro de `api`, no el propio submódulo. Por lo mismo, `dir(models)` pierde `api`.
- **Sin cambios**: `hasattr` es True para todos los nombres públicos de `api`, y `getattr(models, n) is getattr(api, n)` en todos. El pickle de una instancia de `Empty` y de la clase `CaseDetail` hace ida y vuelta, porque `__module__` sigue siendo `models.api`.
- **Consumidores**: ningún consumidor del repo usa `import *` sobre el paquete ni `models.api` como atributo. `routes` usa `from vectra_contracts.models import api as a`, `codegen.py` usa `from vectra_contracts.models.api import Problem` y `vectra_common` importa directamente de `models.api`. Por eso OpenAPI, TS y `vectra_common` no cambian, y `make check` no lo nota. Aun así, es un cambio de API pública dentro del alcance.

Una corrección posible, que no probé: un `__all__` explícito igual al conjunto anterior, y que `__getattr__` resuelva también `"api"` con `import_module`.

### F-03 · NARANJA · contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:22-38 · El mecanismo perezoso no tiene ninguna prueba
El informe de cobertura de `make check` marca `models/__init__.py` con **46 %, 10 líneas sin cubrir**: `_api_names`, `__getattr__`, `__dir__` y el `raise AttributeError` nunca se ejecutan en proceso. Las pruebas de aislamiento corren en subprocesos y no cuentan para la cobertura. Ninguna prueba compara los nombres de `models` antes y después, y por eso F-02 pasa sin que nada lo note. Hace falta una prueba que compare `import *`, `dir()`, el acceso a `models.api` y el `AttributeError` de un nombre inexistente.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r2/ca3.txt (make check completo)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r2/cyc2.py (búsqueda de ciclos con aristas implícitas)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r2/api_old.json y api_new.json (API de `models` antes y después)

VEREDICTO: NO-VERDE
ROJO|contracts/python/vectra_contracts/src/vectra_contracts/__init__.py:5|La bitácora dice que la línea se retiró y sigue en el sha; la evidencia de F-02 (9 ms, 2 módulos) no sale de f7d1e05 (111 ms, 14 módulos, pydantic)
NARANJA|contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:14|Sin __all__, import * pierde 27 nombres de api y filtra TYPE_CHECKING/import_module; models.api da AttributeError en un intérprete limpio
NARANJA|contracts/python/vectra_contracts/src/vectra_contracts/models/__init__.py:22|__getattr__/__dir__/_api_names sin ninguna prueba (cobertura del archivo 46 %)
INFORME: revisiones/U00-T02/ronda-2.md
