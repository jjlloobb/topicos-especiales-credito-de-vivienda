# Ronda 1 — U02-T02

VEREDICTO: NO-VERDE

Los tres criterios pasan. Dejo la ronda en NO-VERDE por un hallazgo NARANJA: la prueba lee el plan de verdad, pero una variación mínima del formato del bloque saca un directorio del control sin avisar. Con eso, la prueba puede dar verde en falso.

Contexto comprobado:
- Hash de la tarea `73005d69…` (coincide).
- Worktree `wt-U02-T02` en `925254c`, con base `1999e52`.
- Diff: `tests/unit/test_skeleton.py`, `tests/{e2e,load}/.gitkeep` y la bitácora. Nada fuera de alcance.
- Sin red (`UV_OFFLINE=1`), sin clúster y sin Docker.
- Al terminar, `git status --short --untracked-files=all` sale vacío y HEAD sigue en `925254c`. El worktree está limpio; solo quedan cachés ignoradas.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/` del worktree) | Resultado |
|---|---|---|---|
| 1 | Existen todos los directorios de §1 | bucle `for d in …; do test -d identity-edge/$d \|\| echo "FALTA $d"; done` | pasa (sin salida) |
| 2 | La prueba lee §1 del plan y la compara con el árbol | `uv run pytest identity-edge/tests -q -k skeleton_matches_plan -p no:cacheprovider` | pasa: `1 passed, 1 deselected in 0.02s` |
| 3 | El Paso 1 sigue cumpliendo su aceptación | `uv sync --frozen && make -C identity-edge check` | pasa: ruff `All checks passed!`, `2 passed`, exit 0 |

El tiempo de 0,02 s cuadra: la prueba solo lee un archivo y hace `is_dir`, sin estado externo.

El rojo previo de la bitácora (`faltan … ['tests/e2e','tests/load']`) es coherente con lo que reproduje al quitar esos dos directorios en mi copia.

## Lectura de vuelta: mutaciones en una copia aparte
La copia está en `…/scratchpad/rev-u02t02-r1/vectra-risk` (`git archive 925254c`), con su propio venv creado con `uv sync --frozen` sin red.

**Mutaciones del árbol.**
- Quité uno a uno los 15 directorios de CA-1: la prueba falla con `faltan directorios de §1: [<d>]` en 14 de ellos.
- `tests/unit` es la excepción: al quitarlo desaparece la propia prueba, así que no queda nada que recoger. Es trivial.
- Sustituí `jobs/` por un archivo: falla.

**Mutaciones del plan.**

| Cambio | Resultado |
|---|---|
| Añadir `policies/` en el nivel superior | falla con `['policies']` |
| Añadir `keycloak/extensions/` | falla |
| Añadir `gateway/values/overlays/` (profundidad 2) | falla |
| Añadir `contract/` en el comentario de `tests/` | falla con `['tests/contract']` |
| Renombrar `ratelimit/` a `ratelimitx/` | falla |
| Quitar `e2e/` del comentario de `tests/` | falla en la comprobación de sanidad |
| Quitar la línea `jobs/` del plan | **pasa** (ver F-02) |

**Formato del bloque.**
- Fallan con estrépito, que es lo correcto: caracteres Unicode `├──`, sangría de 2 espacios, tabuladores, valla sin `text`, encabezado renombrado.
- Pasan, correctamente: CRLF y encabezado `####`.
- **Pasan en falso:** espacio final, nota sin `#`, doble espacio tras el marcador y marcador `+--` (ver F-01).

## Hallazgos

### F-01 · NARANJA · vectra-risk/identity-edge/tests/unit/test_skeleton.py:21 · Las entradas de §1 que no casan con la regex se descartan en silencio y dan verde en falso
`_ENTRY` (línea 9) exige el formato exacto `<marcador> <nombre>[  # comentario]$`. Cualquier línea del bloque que no case se salta con `continue` (líneas 21-23), sin aviso. La sanidad de la línea 40 solo protege 4 nombres. Por eso, un cambio cosmético en el plan saca un directorio del control:

- Dejé la línea como `|-- jobs/ ` (un espacio final). `_plan_directories()` ya no contiene `jobs`.
- Además moví `identity-edge/jobs` fuera: **`1 passed`**.
- Añadí `|-- policies/` en cuatro variantes: con espacio final, con `(nuevo, Paso 9)`, con `— nuevo` o como `|--  policies/` (doble espacio). En las cuatro, `policies` no entra en el conjunto esperado y la prueba da **`1 passed`** aunque el directorio no existe.
- Con el marcador `+-- policies/` ocurre lo mismo.

La bitácora (línea 29) reconoce que la prueba depende del formato, pero no lo defiende. Es justo la regresión que CA-2 busca evitar: el esqueleto vuelve a quedar incompleto y la prueba sigue en verde.

Arreglo sugerido:
- Que cualquier línea del bloque que contenga un marcador de árbol y no se pueda interpretar haga fallar la prueba.
- Tolerar el espacio final con `rstrip()`.

El script de mutaciones está en `…/rev-u02t02-r1/mut.py` y el analizador en `…/rev-u02t02-r1/parse.py`.

### F-02 · AMARILLO · test_skeleton.py:41 · La comparación va en un solo sentido: un directorio que sobra respecto a §1 no se detecta
Si se quita `jobs/` del plan, la prueba sigue pasando aunque `identity-edge/jobs/` exista. La tarea pide que el esqueleto no quede incompleto, y eso se cumple, así que no bloquea.

Hacerla bidireccional chocaría hoy con el propio plan: el Paso 3 crea `tests/strategies/` y P-U2-08 usa `observability/rules/tests/`, y §1 no nombra ninguno de los dos (ver la primera tarea candidata). Conviene al menos documentar en la prueba que se trata de un subconjunto.

Otro caso del mismo tipo: una entrada sin barra final (`|-- policies  # directorio`) se trata como archivo y no se comprueba. Es una ambigüedad inherente; lo dejo como nota.

## Auditoría de U2 hasta ahora (`identity-edge/` completo: U02-T01 + U02-T02) frente al plan y los diseños
**Paso 1, punto por punto:**
- Directorios de §1: los 15 hojas y sus padres, con `.gitkeep`. Coinciden exactamente con lo que el analizador extrae del plan.
- `pyproject.toml` es miembro del workspace: está en `members` del `pyproject.toml` raíz y `uv.lock` incluye `vectra-identity-edge`. `uv sync --frozen` pasa.
- `Makefile` con el objetivo `check` (que encadena `lint` y `test`).
- Los perfiles de Hypothesis se importan de `contracts/tests/conftest.py` mediante `tests/conftest.py`, cubiertos por `test_hypothesis_profile.py`.
- La aceptación del paso pasa (CA-3).

**Lo que §1 nombra para otros pasos sigue ausente, como debe:** `keycloak/Dockerfile` (Paso 4), `gateway/routes.yaml` (Paso 7) y `tools/*.py` (Pasos 3, 6 y 7). No hay realm, tema, values, charts, jobs, reglas ni runbooks. **No se adelantó nada.**

**Nada sobra:** solo hay `.gitkeep`, el conftest y las dos pruebas de esqueleto y perfil, que dan soporte al Paso 1. La casilla del Paso 1 sigue sin marcar, como dice el plan (se marca al fusionar).

**Diseños:** busqué en los diseños de U2 menciones a Makefile, pytest, Hypothesis, rutas y e2e/k6. No hay contradicciones:
- `make test` ejecuta `HYPOTHESIS_PROFILE=ci pytest identity-edge/tests`, lo mismo que pide la verificación de NFR-U2-40, y el perfil `ci` de U0 usa 500 ejemplos.
- La pila es pytest + Hypothesis, como fija tech-stack-decisions.
- `tests/e2e` (Playwright) y `tests/load` (k6) cuadran con NFR-U2-42 y con la elección de k6 frente a Locust que tech-stack dejaba al plan.

## Tareas candidatas (defectos reales fuera de alcance)
- **§1 del plan está incompleto respecto a sus propios pasos.** El Paso 3 crea `tests/strategies/` y P-U2-08 usa `observability/rules/tests/`, pero §1 no los lista. Habría que alinearlos antes de endurecer la prueba en los dos sentidos.
- **`make check` recogerá la suite e2e.** El objetivo `test` ejecuta `pytest identity-edge/tests` completo. Cuando el Paso 13 meta pruebas de Playwright que necesitan clúster, `check` (estático, Paso 15) las recogerá. Hará falta excluirlas o marcarlas.

## Rutas de transcripciones largas
- Copia y scripts: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t02-r1/` (`mut.py`, `parse.py`, `plan.orig`)

VEREDICTO: NO-VERDE
NARANJA|vectra-risk/identity-edge/tests/unit/test_skeleton.py:21|Las entradas de §1 que no casan con la regex se descartan en silencio y dan verde en falso
AMARILLO|vectra-risk/identity-edge/tests/unit/test_skeleton.py:41|Comparación en un solo sentido: un directorio sobrante respecto a §1 no se detecta
INFORME: revisiones/U02-T02/ronda-1.md
