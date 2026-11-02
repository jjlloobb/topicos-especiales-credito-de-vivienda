# Ronda 2 — U02-T02

VEREDICTO: VERDE

F-01 está corregido. Ahora la prueba falla con «no sabe interpretar» o con «faltan directorios» en todas las variantes que daban verde en falso. F-02 queda documentado como §1 ⊆ árbol, tal como arbitraste (docstring de `test_skeleton.py:41-42`).

Queda un caso residual de la misma clase, la primera línea del bloque. Es poco probable y no bloquea (F-03, AMARILLO).

Comprobaciones de base:
- Diff `7c558ae..fa280d3`: solo `test_skeleton.py` (+7/−2), la bitácora y `ronda-1-respuesta.md`.
- Sin red (`UV_OFFLINE=1`), sin clúster y sin Docker.
- Al terminar, el worktree sigue en `fa280d3` y `git status --short --untracked-files=all` sale vacío.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí (desde `vectra-risk/` del worktree) | Resultado |
|---|---|---|---|
| 1 | Existen todos los directorios de §1 | bucle `test -d identity-edge/$d \|\| echo "FALTA $d"` | pasa (sin salida) |
| 2 | La prueba lee §1 del plan y la compara con el árbol | `uv run pytest identity-edge/tests -q -k skeleton_matches_plan -p no:cacheprovider` | pasa: `1 passed, 1 deselected in 0.02s` |
| 3 | El Paso 1 sigue cumpliendo su aceptación | `uv sync --frozen && make -C identity-edge check` | pasa: ruff `All checks passed!`, `2 passed`, exit 0 |

Contra el plan real, la prueba lee exactamente lo mismo que en la ronda 1: los 15 directorios de CA-1 y sus padres. **No salta el fallo «no sabe interpretar».**

## Batería de mutaciones
Todas sobre una copia en `…/scratchpad/rev-u02t02-r2/vectra-risk` (`git archive fa280d3`, venv propio). Restauré el plan tras cada caso y lo verifiqué con `cmp`.

**Árbol.** Quité uno a uno 14 directorios (todos los de CA-1 salvo `tests/unit`, que contiene la propia prueba) y además sustituí `jobs` por un archivo. Todos fallan con `faltan directorios de §1: [<d>]`.

**Las variantes de F-01 de la ronda 1 ya no dan verde en falso.**

| Variante | Resultado |
|---|---|
| `\|-- jobs/ ` (espacio final) con `jobs` ausente | falla `['jobs']` |
| Espacio final tras el comentario, `jobs` ausente | falla `['jobs']` |
| Añadir `policies/` con espacio final | falla `['policies']` |
| Añadir `policies/` con nota sin `#`, con `— nuevo`, con doble espacio o con `+--` | falla «no sabe interpretar» |

**Mutaciones del plan.**

| Cambio | Resultado |
|---|---|
| Añadir `policies/` (con o sin comentario) | falla |
| Añadir `keycloak/extensions/` | falla |
| Añadir `gateway/values/overlays/` (profundidad 2) | falla |
| Añadir `contract/` en el comentario de `tests/` | falla |
| Renombrar `ratelimit/` a `ratelimitx/` | falla |
| Quitar `e2e/` del comentario de `tests/` | falla en la sanidad |
| Quitar `jobs/` del plan, con `jobs` ausente del árbol | pasa: es el subconjunto aceptado en F-02 |

**Formato del bloque.**
- Fallan con estrépito: Unicode `├──`, tabuladores (las dos con «no sabe interpretar»), sangría de 2 espacios (sanidad), valla sin `text` y encabezado renombrado (`IndexError`).
- Una sangría de 3 espacios hace que `realm/` se lea en el nivel superior. Falla con estrépito: `faltan ['realm', 'realm/values']`.
- Pasan, correctamente: CRLF y encabezado `####`.

**Líneas legítimas, que no deben disparar el fallo nuevo.**
- La raíz `vectra-risk/identity-edge/`: no lo dispara.
- Líneas en blanco o con solo espacios, entre entradas, tras la raíz o antes de la raíz: pasan correctamente.
- Una línea separadora que solo contiene `|`, habitual en árboles dibujados, sí lo dispara. El fallo es ruidoso, no un falso verde, y el plan actual no usa esas líneas. Lo dejo como nota, no como hallazgo.

## Hallazgos

### F-03 · AMARILLO · vectra-risk/identity-edge/tests/unit/test_skeleton.py:22 · La primera línea no vacía se descarta sin comprobar que sea la raíz
`lines[1:]` da por hecho que la primera línea es `vectra-risk/identity-edge/`, pero no lo comprueba. Si la raíz desaparece del bloque, la primera entrada se descarta en silencio, justo lo que el comentario de la línea 25 dice evitar.

- Si solo se quita la raíz, se pierde `|-- Makefile`. Es un archivo, así que hoy no tiene efecto.
- Si se quita la raíz y la primera entrada es un directorio, hay falso verde. Lo comprobé con `runbooks/` como primera entrada y `identity-edge/runbooks` ausente: `1 passed`.

Hacen falta dos ediciones a la vez, así que la probabilidad es baja. Por eso no bloquea.

Arreglo de una línea: `assert lines[0] == "vectra-risk/identity-edge/"`, o bien exigir que `lines[0]` no case con `_ENTRY`.

## Tareas candidatas (defectos reales fuera de alcance)
- Ninguna nueva. Las de la ronda 1 las registras tú.

## Rutas de transcripciones largas
- Copia y scripts: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/rev-u02t02-r2/` (`mut.py` con los 29 casos, `parse.py`, `plan.orig`)

AMARILLO|vectra-risk/identity-edge/tests/unit/test_skeleton.py:22|La primera línea no vacía se descarta sin comprobar que sea la raíz
INFORME: revisiones/U02-T02/ronda-2.md
VEREDICTO: VERDE
