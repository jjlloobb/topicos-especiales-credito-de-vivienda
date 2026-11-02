# Ronda 1 — U00-T02

VEREDICTO: NO-VERDE

Hash de la tarea verificado: `git hash-object` da `5bbe4f1a11d2b310133d4a06b7a83583cd097cd0`, coincide. Worktree `wt-U00-T02` en `c63b7ca`, limpio: `git status` sin cambios y solo ignorados preexistentes (`.coverage`, `benchmark.json`). El diff contra `c656de2` toca 3 archivos: `vectra_contracts/__init__.py` (+6), `tests/unit/test_import_isolation.py` (nuevo) y la bitácora. No hay desborde de alcance ni cambios en `.importlinter`. Todo lo corrí sobre copias hechas con `git archive c63b7ca` en `scratchpad/rev-u00t02-r1/{repo,mut}`, con `uv sync --frozen` sin red y los `node_modules` del árbol principal enlazados.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | outcome y dictionary como primer import | `uv run python -I -c "import vectra_contracts.outcome" && uv run python -I -c "import vectra_contracts.dictionary"` | pasa: exit 0, sin salida |
| 2 | prueba de import aislado, lista derivada | `uv run pytest contracts/tests -q -k each_module_imports_in_isolation` | pasa: 37 passed en 23 s, uno por módulo. Los ids recogidos coinciden con los 38 `.py` del árbol menos `outcome._internal` |
| 3 | U0 sigue cumpliendo, import-linter intacto | `uv sync --frozen && make -C contracts check` | pasa: EXIT=0. ruff limpio, mypy sin errores en 38 archivos, import-linter con 3 KEPT y 0 broken, 495 passed sin skips, cobertura total 98 %, trazabilidad 3 passed, bench ok, sin diff de openapi ni de TS, vitest 8 passed |

La prueba roja de la bitácora («2 failed, 35 passed») es coherente con mi mutación M1, que da exactamente lo mismo.

## Hallazgos

### F-01 · NARANJA · contracts/python/vectra_contracts/src/vectra_contracts/__init__.py:5 · El ciclo no se rompe: queda oculto por un orden de import impuesto
La tarea dice dentro del alcance: «La cadena circular […] Se rompe». No se rompió. Las aristas siguen todas en su sitio:
- `models/api.py:29` todavía hace `from vectra_contracts.outcome import Recommendation`. grimp encuentra la cadena `models.api → outcome`.
- `outcome` todavía importa `models.base`, `models.explanation` y `models.features`. Cada uno de esos imports ejecuta `models/__init__`, que vuelve a importar `api`.

El cambio solo obliga a que el ciclo siempre se cargue entrando por `models`. Lo demuestran las mutaciones, todas en `mut/`:
- **M1**, quitar la línea 5: vuelve el `ImportError` del N1 y la prueba lo detecta con 2 FAILED (`dictionary` y `outcome`). Así que la guarda funciona.
- **M3**, añadir al `__init__` una línea legítima `from vectra_contracts import catalog, dictionary` y correr `ruff check --fix`: isort la coloca **antes** de `models as _models`, y todo el paquete deja de importarse (`cannot import name 'covers' from partially initialized module`). La prueba lo detecta, aunque como error de colección y no como fallo por módulo. Con M2, que añade imports `from vectra_contracts.outcome …` y `.dictionary …`, ruff conserva el orden y todo pasa. La fragilidad depende de cómo se escriba el import.
- **M4**, cargar `outcome` por ruta con `spec_from_file_location` sin pasar antes por el paquete: `ImportError: cannot import name 'Recommendation'`. Es artificial, pero confirma que el ciclo sigue ahí.

El arreglo no contradice ni las capas de import-linter (3 KEPT) ni P-U0-03, porque la capa 3 sigue limitada a imports directos. Tampoco los NFR de latencia: NFR-U0-01, 02 y 03 pasan en el bench.

Hay una ruptura real que no cambia la API pública, sin probar por mí: re-exportar los nombres de `models.api` en `models/__init__.py` de forma perezosa, con `__getattr__` de PEP 562 más `__all__` y `__dir__`, de modo que `outcome → models/__init__` ya no arrastre `api`. Otra vía es mover `Recommendation`, pero eso queda fuera de alcance.

Si el orquestador o el diseño prefieren aceptar «orden fijado + prueba de guarda» como cumplimiento, hay que **enmendar el texto de la tarea**. Tal como está escrito, este punto del alcance no se cumple.

### F-02 · AMARILLO · contracts/python/vectra_contracts/src/vectra_contracts/__init__.py:5 · Cualquier import del paquete carga ahora pydantic y todos los modelos
Medí la mediana de 5 corridas de `python -I`:
- Antes del cambio, `import vectra_contracts.catalog` tardaba 14 ms, cargaba 2 módulos `vectra*` y no cargaba pydantic.
- Ahora tarda 264 ms, carga 19 módulos `vectra*` y sí carga pydantic. Lo mismo pasa con `decimal_ctx`.

A los servicios no les afecta, porque `vectra_common` ya importa `models.api`. Pero la bitácora afirma «sin cambios de comportamiento», y el costo de import sí es un efecto observable.

### F-03 · AMARILLO · contracts/tests/unit/test_import_isolation.py:17 · Los módulos privados quedan fuera de la guarda
`startswith("_")` omite `outcome._internal` y cualquier subárbol con `_`. Para probarlo creé el par `_priv_a`/`_priv_b`, con un ciclo entre ambos: la suite no lo ve, aunque `python -I -c "import vectra_contracts._priv_b"` falla. En cambio, un módulo público nuevo con ciclo (M5, `vectra_contracts.nuevo` y `nuevo.b`) **sí** se detecta: 2 FAILED, sin tocar la prueba. La lista se deriva de verdad.

### F-04 · AMARILLO · contracts/tests/unit/test_import_isolation.py:44 · La prueba no exige «sin salida»
CA-1 espera «sin salida», pero la prueba solo afirma `returncode == 0`. Un `DeprecationWarning` o un `print` al importar pasarían sin que la prueba lo note. Bastaría añadir `assert result.stdout == "" and result.stderr == ""`.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Si se elige mover `Recommendation` para romper el ciclo, sería una tarea propia, porque mueve un símbolo público.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r1/ca3.txt (make check completo)
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u00t02-r1/ca2.txt (CA-2 en modo verbose)

VEREDICTO: NO-VERDE
NARANJA|contracts/python/vectra_contracts/src/vectra_contracts/__init__.py:5|El ciclo outcome→models→api→outcome no se rompe: queda oculto por un orden de import impuesto; ruff --fix puede reordenarlo (M3)
AMARILLO|contracts/python/vectra_contracts/src/vectra_contracts/__init__.py:5|Cualquier import del paquete carga pydantic y todos los modelos (14 ms → 264 ms)
AMARILLO|contracts/tests/unit/test_import_isolation.py:17|Los módulos privados (_*) quedan fuera de la guarda de import aislado
AMARILLO|contracts/tests/unit/test_import_isolation.py:44|La prueba no exige salida vacía, aunque CA-1 la pide
INFORME: revisiones/U00-T02/ronda-1.md
