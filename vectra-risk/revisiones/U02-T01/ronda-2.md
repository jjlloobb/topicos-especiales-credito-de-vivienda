# Ronda 2 — U02-T01

VEREDICTO: VERDE

Worktree `wt-U02-T01` en `f34b7308a910e26a84f88074a91e7565033a6eef`. El arreglo está en `b5ce0a4`. Lo revisé contra la ronda 1 (`a2fc046`) y contra la respuesta `revisiones/U02-T01/ronda-1-respuesta.md`. Corrí los comandos desde `vectra-risk/` con `--offline`. Sin red, sin clúster y sin Docker. Las mutaciones se hicieron en una copia `git archive f34b730 vectra-risk .github` bajo `rev-u02t01-r1/r2/copy/`, con su propio venv. Esta vez incluí `.github`, así que el falso fallo de CODEOWNERS de la ronda 1 desaparece.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `check` con el lock congelado | `uv sync --frozen && make -C identity-edge check` | pasa (exit 0, `1 passed`) |
| 2 | Directorios de §1 con `.gitkeep` | el bucle `test -d` de la tarea | pasa (no imprime nada) |
| 3 | Perfil del workspace leído de vuelta | `HYPOTHESIS_PROFILE=ci uv run pytest identity-edge/tests -q -k hypothesis_profile` | pasa (`1 passed`) |
| 4 | U0 y U1 intactos | `uv sync --frozen && uv run pytest contracts/tests -q -x -p no:cacheprovider && uv run ruff check identity-edge platform contracts` | pasa (`455 passed`, `All checks passed!`) |

## Hallazgos de la ronda 1, verificados
- **F-01 (NARANJA): cerrado.** La línea `"identity-edge/tests/**"` ya no está en `pyproject.toml`. Puse un `try/except Exception: pass` en `identity-edge/tests/unit/test_x.py`: ruff da `S110` y `BLE001`, y `make check` termina en 2.
- **F-02 (AMARILLO): cerrado.** La sesión `pytest contracts/tests identity-edge/tests` sin `-q` imprime `hypothesis profile` una sola vez y da `456 passed`.
- **F-03 (AMARILLO): cerrado.** Ya no está el literal `"dev"`. La prueba recibe el perfil por defecto de U0 por la fixture `u0_default_profile`. Mutación: con el valor por defecto de U0 cambiado a `"ci"` y sin la variable, la prueba sigue a U0 y pasa, que es lo esperado.

## Mutaciones (copia aislada)
| Mutación | Resultado |
|---|---|
| Prueba rota en `identity-edge/tests/unit` | `make check` termina en 2 |
| `import os` sin usar en `identity-edge/tools/` | `make check` termina en 2 |
| `try/except Exception: pass` en `identity-edge/tests/` | `S110`, `BLE001`; `check` termina en 2 |
| `conftest.py` de identity-edge vacío | CA-3: `1 error` (falta la fixture) |
| Sin `conftest.py` y sin la variable | `1 error` |
| Se quita el segundo `exec_module` del conftest (la recarga con el entorno real) | CA-3 con `ci`: `1 failed` |
| El conftest de U0 carga siempre `"dev"` | con `ci`: `1 failed` |
| `nightly` y variable sin fijar, sin mutar | `1 passed` en los dos casos |

## Efectos colaterales de cargar U0 «sin `HYPOTHESIS_PROFILE`»
Lo que hace el código (`identity-edge/tests/conftest.py:20-29`):
- Hace `os.environ.pop` de la variable y ejecuta el módulo de U0. Esa ejecución llama a `load_profile` con el valor por defecto.
- En un `finally` repone la variable, si existía.
- Si existía, vuelve a ejecutar el módulo para que `load_profile` cargue el perfil real.

Para comprobar que no altera nada, puse en la copia una sonda en `contracts/tests` y otra en `identity-edge/tests`. Cada una imprime `os.environ["HYPOTHESIS_PROFILE"]`, `settings.get_current_profile_name()` y `settings.default.max_examples`. Las corrí en sesión combinada, en los dos órdenes, con la variable en `ci`, `dev`, `nightly` y sin fijar. En los 8 casos las dos sondas ven lo mismo, y es lo correcto:
- `ci`: 500 ejemplos
- `dev`: 25 ejemplos
- `nightly`: 10000 ejemplos
- sin fijar: la variable sigue sin existir (`env=None`), el perfil es `dev` y son 25 ejemplos.

El entorno queda restaurado y el perfil activo es el que corresponde. Con la variable vacía, `HYPOTHESIS_PROFILE=`, falla igual que el propio U0 (`Profile '' is not registered`): no es una regresión. Los conftests se cargan antes de importar los módulos de prueba, así que el `load_profile` transitorio no se ve en ningún decorador `@settings`.

## Hallazgos
### F-04 · AMARILLO · vectra-risk/identity-edge/tests/conftest.py:20-29 · Mutación transitoria de `os.environ` y dependencia de un atributo privado de U0
La técnica funciona, como muestran las sondas, pero tiene dos debilidades:
- **Es frágil.** Cambia el entorno global durante la carga, hace un `load_profile` intermedio que se descarta y ejecuta el conftest de U0 hasta tres veces por sesión. Con ejecución en paralelo dentro del proceso sería insegura. Hoy no se usa.
- **Depende de un nombre privado.** Lee `default._profile`. Si U0 lo renombra, la colección falla con `AttributeError`; al menos es un fallo ruidoso.

Lo más limpio sería que U0 expusiera una constante pública con el perfil por defecto. Eso toca `contracts/`, así que queda fuera de alcance aquí. No bloquea.

## Tareas candidatas (defectos reales fuera de alcance)
- Exponer en `contracts/tests/conftest.py` una constante pública con el perfil por defecto, para que identity-edge la lea sin mutar el entorno. La candidata de CI de la ronda 1 la anota el orquestador.

## Evidencia de la bitácora
La sección «Ronda 2» coincide con lo que obtuve. El conteo `0` de cabeceras con `-q` está bien explicado en su nota, y yo medí 1 sin `-q`.

## Estado final
El worktree queda limpio (`git status --short` vacío) en `f34b7308a910e26a84f88074a91e7565033a6eef`.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t01-r1/r2/logs/ca1.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t01-r1/r2/logs/ca4.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t01-r1/r2/logs/combined.txt

VEREDICTO: VERDE
AMARILLO|vectra-risk/identity-edge/tests/conftest.py:20-29|Mutación transitoria de os.environ y dependencia del atributo privado _profile de U0
INFORME: revisiones/U02-T01/ronda-2.md
