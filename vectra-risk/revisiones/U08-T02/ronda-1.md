# Ronda 1 — U08-T02

VEREDICTO: NO-VERDE

Los 8 criterios pasan con mis propias ejecuciones y no hay ningún ROJO. El veredicto es NO-VERDE por un solo NARANJA (F-01): `views.py` usa el token privado de U0. Según RL-1..RL-5 solo un ROJO bloquea, así que decidir si se fusiona le toca al orquestador. Yo no rebajo la severidad.

Revisé el worktree `/home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/.claude/worktrees/u08-t02` en el sha af22e5a0, con base f6a8524. El blob de la tarea es 08ed34e3, el mismo que cita la bitácora. Al terminar, el worktree está limpio: `git status --short` da 0 líneas y solo quedan cachés ignorados.

## Criterios de aceptación, verificados por mí (desde `vectra-risk/`)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | `case_fsm` y la comparación con la migración | `uv run pytest case-management/tests/unit/test_case_fsm.py -v` | pasa: 19 pruebas en 0,46 s |
| 2 | backoff, PBT-U8-02 | `HYPOTHESIS_PROFILE=ci uv run pytest …/property/test_backoff.py -v` | pasa: 9 pruebas, perfil `ci` con max_examples=500 |
| 3 | decision, PBT-U8-03 y ejemplos | `HYPOTHESIS_PROFILE=ci uv run pytest …/test_decision.py …/unit/test_decision_examples.py -v` | pasa: 13 pruebas en 1,42 s, perfil `ci` |
| 4 | views, PBT-U8-04 | `HYPOTHESIS_PROFILE=ci uv run pytest …/property/test_views.py -v` | pasa: 16 pruebas en 5,06 s, perfil `ci` |
| 5 | import-linter | `uv run lint-imports --config case-management/.importlinter` | rc=0: 3 kept, 0 broken |
| 6 | cobertura de ramas del 100 % | el comando literal de CA-6 | rc=0: TOTAL 109/0/14/0, 100 %, 78 pruebas |
| 7 | `logic.md` y el plan | el comando literal de CA-7 | rc=0: menciona `mutmut` y salen 5 líneas `[x]` con `(U08-T02)` |
| 8 | `make -C case-management check` | `make -C case-management check` | rc=0: ruff y mypy (24 archivos), 3 contratos kept, 186 pruebas, 100 %, sin ninguna omitida, 34 s |

Los tiempos son coherentes con lo que se ejecuta. CA-8 levanta Testcontainers y no hay pruebas omitidas.

**Comparación con la migración (comprobada de verdad).** La prueba carga `migrations/versions/0003_guards.py` por ruta y exige igualdad de conjuntos con 16 pares. La migración no cambia en el diff. Hice mutaciones sobre una copia en el scratchpad (cada una falla `test_fsm_table_equals_case_transitions_of_the_migration`):
- quitar `en_evaluacion → no_disponible` de `case_fsm` (el rojo de la tarea);
- quitar `listo → vencido` de la copia de la migración;
- añadir un par extra a la migración.

Con eso queda probada la igualdad en los dos sentidos.

**Mutaciones de la bitácora, reproducidas por mí** (copia en `…/scratchpad/vr`, el worktree no se tocó):
- **PBT-U8-02:** un jitter de ±25 % falla las dos propiedades. El exponente mal escrito falla la cota de la suma. Aceptar el intento 6 falla `[6]`.
- **PBT-U8-03, solo la propiedad:**
  - aceptar un factor ajeno al `shap_vector`: falla;
  - poner el 409 antes que el 422: falla;
  - quitar BR-U0-35: falla;
  - dejar que `ninguno` no exima: falla.
- **PBT-U8-04, solo la propiedad:**
  - pasar `application` tal cual: falla con `extra_forbidden`;
  - recomendación en cualquier estado: falla;
  - `credit_status` y `decision` siempre presentes: falla;
  - `recommendation_entry_id` siempre presente: falla;
  - el documento completo en `applicant_display`: falla;
  - `last_cause` siempre presente: falla en `test_attempts_and_last_cause_follow_the_state`.

## Hallazgos

### F-01 · NARANJA · `case-management/src/vectra_case/views.py:27,37` · El token privado de U0 sale de `outcome` y abre un camino para fabricar `Recommendation`
- **Qué dice el diseño.** P-U0-03, capa 3 (`contracts/nfr-design/nfr-design-patterns.md:38-46`; `logical-components.md:118`) dice «Solo `outcome` importa `vectra_contracts.outcome._internal`». Lo que esa capa quiere impedir es justo «obtener el token desde otro módulo».
- **Qué hace el diff.** `views.py` lo importa y lo deja visible a nivel de módulo como `_CONTEXT = {"token": CONSTRUCTION_TOKEN}`.
- **Ningún linter lo caza.** El contrato `token-privado` de `contracts/.importlinter` solo lista módulos de U0, y `case-management/.importlinter` no lo prohíbe. Por eso CA-5 pasa.
- **Prueba** (`…/scratchpad/scripts/probe.py`): `Recommendation.model_validate_json(json.dumps(d), context=vectra_case.views._CONTEXT)` con `registry_entry_id="inventado"` devuelve **una `Recommendation` fabricada fuera de `build_outcome`, sin ningún `RegistryAck` real**.
- **Sobre la pregunta del orquestador.**
  - No se puede fabricar una `Recommendation` *sin* `registry_entry_id`: la capa 1 la rechaza con `ValidationError`.
  - Sí se puede fabricar una con un identificador de registro inventado, saltándose `check_preconditions` y `build_outcome` (AUTONOMIA-06).
- **La necesidad es real.** Comprobé que quitar el contexto hace fallar `test_decidido_carries_credit_status_and_decision` con `ContractViolation`.
- **El codificador lo reportó** en `CANDIDATAS.md`, pero el rodeo que aplicó rompe el invariante en lugar de solo reportarlo.
- **Por qué NARANJA y no ROJO.** No rompe ningún criterio y no modifica U0.
- **Arreglo.** Hay que cerrarlo antes del Bloque D, que va a leer el JSON de la base. Dos opciones: corregir primero U0 (la candidata ya propone cómo), o en U8 al menos no dejar el token importable (por ejemplo, un `_CONTEXT` local dentro de la función) y añadir `vectra_contracts.outcome._internal` a los `forbidden_modules` de U8 con una excepción documentada. La decisión es del orquestador.

### F-02 · AMARILLO · `tests/property/test_views.py` (`make_row`) · La dimensión «anonimizado» de PBT-U8-04 es vacía para `identifiers`
- `make_row` pone `identifiers=None` siempre que `anonymized=True`, así que la aserción `(detail.identifiers is not None) == (not anonymized)` la garantiza el generador, no `views`.
- Mutantes que sobreviven a la propiedad:
  - `"identifiers": row.identifiers`;
  - `applicant_display` que ignora `anonymized`.
- Los dos los caza el ejemplo `test_anonymized_detail_drops_identifiers_even_if_the_row_carries_them`, por eso no bloquea.
- Lo que conviene es generar también filas anonimizadas que traigan identificadores.

### F-03 · AMARILLO · `tests/property/test_backoff.py` · Ninguna prueba exige que haya jitter
- Cambiar `return nominal * rng.uniform(...)` por `return nominal` deja las 9 pruebas verdes. Las cotas de PBT-U8-02 lo admiten.
- `mutmut` está diferido (T3), pero una prueba barata como «semillas distintas dan retrasos distintos» cerraría el hueco.

### F-04 · AMARILLO · `src/vectra_case/decision.py:20,35,37` · Literales fuera del catálogo y constante mutable
- `Rechazo.reason: str` usa `"used_factors_not_in_shap_vector"` y `"decision_incoherent_with_outcome"`, que no están en `ProblemReason`, el catálogo cerrado de U0.
- `Problem.reason` es de tipo `ProblemReason | None`, así que si el Bloque D propaga ese texto la validación falla. Hoy no es visible para el usuario; por eso es AMARILLO y no NARANJA.
- `NO_FACTORS = ["ninguno"]` es una lista mutable sin `Final` y repite el literal de `validation.py:81`.

### F-05 · AMARILLO · `src/vectra_case/views.py` (`persistent_failure`) · Dos anomalías del mismo tipo, dos tratamientos
- Si falta `since`, lanza `ValueError`.
- Si falta `last_cause`, la convierte en silencio a `""` (`row.last_cause or ""`).
- Un caso `no_disponible` siempre tiene causa (intento 6 o `scoring_rejected`). Conviene tratar las dos anomalías igual o justificar la diferencia en `logic.md`.

### F-06 · AMARILLO · `bitacoras/U08-T02.md` · Conteo mal escrito en el verde de CA-3
- La bitácora dice «11 + 1 passed». Lo real son 13: 2 de la propiedad y 11 ejemplos, y su propio rojo suma 13 (3 fallan y 10 pasan).
- No es evidencia falsa sobre ningún aprobado, pero el número está mal.

## Juicio de las decisiones declaradas
1. **Token privado:** es F-01, NARANJA.
2. **Precedencia 422 antes que 409:** está bien. El BLM:92 lista `422 | 409 | ok` en ese orden, CA-3 se cumple en los dos códigos y la elección está registrada en `logic.md` y en `CANDIDATAS.md`. Sin hallazgo.
3. **Elecciones de `views`:** coinciden con el diseño y con la OpenAPI.
   - `last_cause` y `credit_status` se pueden anular en `CaseDetail` (`contracts/openapi/case-service.yaml:291,306`).
   - `credit_status` solo en `decidido` sigue BR-U8-21.
   - `applicant_display` vacío si el caso está anonimizado sigue domain-entities de U0:77.
   - `PersistentFailure.last_cause` es obligatorio en la OpenAPI (línea 842), y de ahí viene F-05.
   - El `ValueError` de `persistent_failure` está probado.
4. **Cambios fuera de la lista de archivos:** no hay desborde.
   - `COV_PURE` en el `Makefile` lo pide la tarea («make check suma … la cobertura del 100 %»).
   - `tests/doubles/case_strategies.py` lo pide la tarea («copia el patrón a `case-management/tests/` y cita el origen»), y lo cita.
   - Borrar `.gitkeep` es consecuencia de poblar el directorio.
   - Las 3 entradas de `CANDIDATAS.md` son el canal de reporte.
   - No hay cambios en U0 ni en la migración.

## Tareas candidatas (defectos reales fuera de alcance)
- **U0, P-U0-03:** el contrato `token-privado` solo protege módulos de U0. Debería prohibir `vectra_contracts.outcome._internal` a todos los consumidores (`vectra_case`, BFF y demás) o publicar en U0 una vía de lectura segura. Complementa la candidata del codificador sobre `CaseDetail.recommendation`.
- **U0 o U8:** `ProblemReason` no tiene razones para un factor ajeno ni para la incoherencia con BR-U0-35. Hay que decidirlo antes del Bloque D (relacionado con F-04).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/ca2.txt`, `ca3.txt`, `ca4.txt`, `r-ca5.txt`, `r-ca6.txt`, `r-ca8.txt`
- Script de mutaciones: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/scripts/mut.sh`
- Prueba de fabricación con el token: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/scripts/probe.py`

```
VEREDICTO: NO-VERDE
NARANJA|case-management/src/vectra_case/views.py:27|El token privado CONSTRUCTION_TOKEN sale de outcome (rompe P-U0-03 capa 3) y permite fabricar Recommendation con registry_entry_id inventado
INFORME: revisiones/U08-T02/ronda-1.md
```
