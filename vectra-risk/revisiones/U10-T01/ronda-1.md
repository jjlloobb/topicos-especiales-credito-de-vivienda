# Ronda 1 — U10-T01

VEREDICTO: VERDE

Revisé la rama `tarea/U10-T01`: HEAD `5156d3f`, código en `3a36cc9`, base `81a8fd0`. El blob de la tarea `19e7eb1` coincide. Corrí los criterios CA-1 a CA-8 yo mismo y todos terminan en 0. Ninguna prueba se saltó. Las mutaciones las hice sobre una copia (`git archive`) en `.../scratchpad/rev-u10-t01-r1/copy/`. Al terminar, el worktree `u10-t01` sigue limpio (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | import-linter | `uv sync --frozen && uv run lint-imports --config console/bff/.importlinter` | pasa: 3 contratos KEPT. Rojo propio: `import httpx` en `object_rules` y en `routes` rompe 2 contratos; `vectra_common.deps` en `errors` y `os` en `config` rompen el suyo; `httpx` en `compose` rompe `no-httpx`. Con `allow_indirect_imports=False` siguen los 3 KEPT. |
| 2 | Estructura de §1 | el bucle `test -e` de la tarea | pasa: ninguna línea `FALTA`, sale `OK`, y existe `eslint.config.mjs`. No hay `nginx.conf`, `Dockerfile` ni `Chart.yaml`. |
| 3 | ESLint y TypeScript | `npm ci --ignore-scripts -w console/spa && … lint && … typecheck && … test -- eslint` | pasa: 8/8 |
| 4 | `config.py` contra P-U10-04 | `uv run pytest console/bff/tests/unit/test_config.py -v` | pasa: 9/9 en 0,13 s. El tiempo se explica: son constantes puras, sin estado externo. |
| 5 | Constantes y `load.ts` | `npm run -w console/spa test -- config` | pasa: 27/27. Los tres realms dicen 1800. |
| 6 | PBT-U10-02 y PBT-U10-03 | `HYPOTHESIS_PROFILE=ci uv run pytest …test_object_rules.py …test_errors.py -v` | pasa: 21/21 en 17,5 s, con el perfil `ci` activo (500 ejemplos) |
| 7 | Cobertura de ramas y resumen | `uv run pytest … --cov-branch --cov-fail-under=100 && test -s …bff-logic.md` | pasa: 57 pruebas, `TOTAL … 100%` |
| 8 | `check` de U10, U0 y U1, en serie | los tres `make -C {console,contracts,platform} check`, con `uptime` antes y después | pasa: console 0 en 60 s; contracts 0 en 481 s (bench dentro del límite, p95 2,26 ms con límite 5); platform 0 en 1024 s (372 pass, 0 fail). Carga entre 8,5 y 12. |

Otras verificaciones:
- `uv lock --check`: 0.
- `npm ci` sin banderas, en la copia: 0 y sin ERESOLVE.
- `npm audit --audit-level=high`: 0 vulnerabilidades, tanto en la copia como en el worktree.

## Puntos pedidos por el orquestador

**1. Desvío en el `package.json` raíz.**
- Los `devDependencies` en la raíz hacen falta porque npm solo resuelve referencias `$eslint` hacia dependencias directas de la raíz. El codificador lo declara en la bitácora (desvío 1).
- Hay una sola ESLint en el árbol, la 10.14.0 (`npm ls eslint` sale todo *deduped*).
- Comparé el lockfile de la base con el de HEAD: hay 0 paquetes quitados y 0 con versión o bandera `dev` cambiada. `contracts/ts` y los demás miembros no se tocan; el override solo alcanza a los dos plugins.
- Mutaciones de la configuración de ESLint: quité por turno `react/no-danger`, `jsx-no-literals`, el almacenamiento de `no-restricted-globals`, `no-restricted-properties`, el selector de `Number` y el recomendado de `jsx-a11y`. Cada una hace fallar exactamente su caso, con el `ruleId` correcto.
- Probé un archivo con muchas reglas a la vez: ningún error fatal de los plugins con ESLint 10.

**2. `object_rules` y `errors`.**
- Las 11 funciones coinciden con la columna «Objeto» de C03. Las filas «—», «el caso existe», «la verificación existe» y «el congelamiento existe» quedan con `None`.
- El mapa tiene exactamente las 30 rutas.
- Corrí 23 mutaciones propias que no son equivalentes y las 23 mueren. Cubren cada predicado, el mapa (dos intercambios), los estados 409 y 403, la propagación de 403 y 404, `status<400`, el filtro de `reason`, `invalid_params`, `RecursionError` y el `correlation_id`.
  - Hubo además una mutación de `detail` hecha con `model_copy` que sobrevive, pero es equivalente: el `Problem` cerrado no serializa `detail` y `problem_body` no lo emite.
  - La mutación de `detail` del codificador (`__pydantic_extra__`) sí muere sobre la prueba actual.
- `approve_policy`: el 409 sin justificación es coherente con la tarea, que fija aceptar, 403 o 409. Es inalcanzable porque `PolicyDecisionIn` ya responde 422, y está documentado.
- `create_applicant_summary`: limitarlo a `decidido` + `desfavorable` coincide con el texto de la tarea. La omisión de «explicación sincronizada» de C03 está justificada en `bff-logic.md`.

**3. Constantes.**
- `config.py` coincide fila a fila con P-U10-04: 1,5 / 4 / 1,5 / 4 / 5 / 3 / 2 / 5 / 1,5 s; conexiones 20/10/5/5/5; ×6 réplicas.
- `constants.ts` coincide con domain-entities §4.
- Confirmo que P-U10-04 no trae fila para `get_case_identifiers`.
- 6 mutaciones de configuración, las 6 mueren: escritura de case a 3 s, dossier a 9 s, un timeout nuevo de 12 s, governance con 12 conexiones, `os.environ` y 5 réplicas.

**4. Lockfiles:** están bien (ver arriba).

**5. Desbordes:** no hay.
- Fuera de `console/` el diff solo toca el plan, `bff-logic.md`, la bitácora, el `pyproject.toml` raíz, `uv.lock`, el `package.json` raíz y `package-lock.json`.
- No toca U0, U2 ni `contracts/ts`. `CANDIDATAS.md` no cambia.

## Hallazgos
Ninguno es ROJO ni NARANJA.

### F-01 · AMARILLO · `console/spa/eslint.config.mjs:23` · `jsx-no-literals` con `noStrings` también prohíbe atributos
Mi archivo de prueba marca `role="button"`, `id="i"`, `htmlFor="i"` y `href="#"` como errores. NFR-U10-53 habla de texto visible, así que los bloques D a E van a tener que meter cada atributo en una variable. Conviene `ignoreProps: true` o `allowedStrings`.

### F-02 · AMARILLO · `object_rules.py:20-22` · `Literal` de estado copiados a mano
`DataSourceState`, `PolicyState` y `PolicyDecision` son copias de los `Literal` de `models/governance.py`. Ninguna prueba compara `get_args(o.PolicyState)` con la anotación de U0, así que si U0 cambia un estado no salta nada.

### F-03 · AMARILLO · `tests/unit/eslint-fixtures/` · Faltan fixtures para variantes que la regla sí bloquea
No hay fixture para `parseFloat`, `Number.parseFloat`, `sessionStorage` global ni `globalThis.localStorage`. Lo probé a mano y las reglas las bloquean, pero ninguna prueba lo fija.

### F-04 · AMARILLO · bitácora, rojo de CA-6 (`detail`) · La evidencia salió de una versión anterior de la prueba
La salida pegada falla en `test_errors.py:77`. En la versión actual, la aserción está en la línea 92, así que el archivo cambió después del rojo. Rehice la mutación sobre el archivo actual y falla en `:92`, así que el par falla-pasa queda confirmado por mí.

### F-05 · AMARILLO · `config.py:249` y `test_config.py:73` · `SPA_API_TIMEOUT_SECONDS` duplicado y excluido por nombre
`SPA_API_TIMEOUT_SECONDS` (10 s) se excluye por nombre de la regla «ningún timeout ≥ 9 s», y además duplica `API_TIMEOUT_SECONDS` de `constants.ts`, sin una prueba que los ate.

## Tareas candidatas (defectos reales fuera de alcance)
- **P-U10-04 no da timeout ni presupuesto de conexiones para case `get_case_identifiers`**, que usa `get_dossier` en paralelo (Bloque C). Hay que fijarlo en el diseño antes del Paso 5. El codificador solo lo anotó en la bitácora, no en `CANDIDATAS.md`.

## Rutas de transcripciones largas
Carpeta: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/rev-u10-t01-r1/`
- `ca1.log`, `ca3.log`, `ca4.log`, `ca5.log`, `ca6.log`, `ca7.log`
- `ca8-summary.log`, `ca8-console.log`, `ca8-contracts.log`, `ca8-platform.log`
- `npmci-noflags.log`
- `lock-base.json`, `lock-head.json`
- `tools/mut.py`, `tools/eslintmut.py`

```
VEREDICTO: VERDE
AMARILLO|console/spa/eslint.config.mjs:23|jsx-no-literals con noStrings también prohíbe atributos
AMARILLO|console/bff/src/console_bff/object_rules.py:20|Literal de estado copiados sin prueba que los ate a U0
AMARILLO|console/spa/tests/unit/eslint-fixtures/|faltan fixtures de parseFloat, Number.parseFloat, sessionStorage y globalThis
AMARILLO|bitacoras/U10-T01.md:236|rojo de detail sacado de una versión anterior de test_errors.py (reproducido por mí)
AMARILLO|console/bff/tests/unit/test_config.py:73|SPA_API_TIMEOUT_SECONDS excluido por nombre y duplicado con la SPA
INFORME: revisiones/U10-T01/ronda-1.md
```
