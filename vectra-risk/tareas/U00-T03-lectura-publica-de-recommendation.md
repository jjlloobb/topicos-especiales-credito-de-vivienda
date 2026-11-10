# U00-T03 — Vía pública para anidar y leer una `Recommendation` ya registrada, y token privado cerrado en todo el workspace

**Unidad:** U0 `contracts` (con un ajuste mínimo en U8 `case-management`)
**Historias que implementa:** US-111 (invariante de `Recommendation`) y, de forma indirecta, US-107 (detalle del caso con su recomendación).
**Depende de:**
- **U08-T02 fusionada en `main`**: esta tarea retira el rodeo temporal que deja su ronda 2 en `case-management/src/vectra_case/views.py` y la excepción de `case-management/.importlinter`.
- En `main`: U00-T01 y U00-T02, ya fusionadas (tipos de `Recommendation` y ruptura del import circular de `outcome`).

**Se despacha** cuando U08-T02 esté en `main`, y **antes de U08-T03**, el Bloque D de U8, que lee la recomendación persistida para armar `CaseDetail`. Todavía no hay un archivo `tareas/U08-T03-*`: quien lo redacte debe poner a U00-T03 en su «Depende de».
**Rama:** `tarea/U00-T03`, desde `origin/main`.

Origen: hallazgo F-01 (NARANJA) de `revisiones/U08-T02/ronda-1.md` y su arbitraje (`revisiones/U08-T02/arbitraje-ronda-1.md`). Decisión del usuario del 2026-11-10: «ronda 2 de contención en U8 más una tarea de U0».

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea.

---

## El problema, con evidencia

P-U0-03 (`aidlc-docs/construction/contracts/nfr-design/nfr-design-patterns.md`, «Invariante de `Recommendation` en tres capas») tiene tres capas:

| Capa | Mecanismo | Qué impide |
|---|---|---|
| 1. Estructural | `model_validator` de `Recommendation` (versiones iguales, `registry_entry_id` no vacío, `score` y `confidence` en [0, 1]), también al deserializar | Que circule una `Recommendation` inconsistente |
| 2. Construcción | `Ready` y `Recommendation` exigen el token privado de `outcome`; la deserialización usa `RecommendResult.from_wire()`, que aplica la capa 1 | Construir en proceso saltándose `check_preconditions` y `build_outcome` |
| 3. Dependencias | import-linter prohíbe `vectra_contracts.outcome._internal` fuera de `outcome` (`logical-components.md`, «Reglas de dependencia») | Obtener el token desde otro módulo |

Hoy pasan dos cosas, las dos medidas por el orquestador sobre `main` (`fe0c9f3`):

1. **No hay ninguna forma pública de anidar una `Recommendation` ya construida.** El validador `after` de `_Guarded` (`contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py`, `_require_token`) vuelve a correr cuando la instancia va dentro de otro modelo, y la rechaza sin el token. Con `class W(StrictModel): r: Recommendation | None`, las tres formas fallan con `ContractViolation: Recommendation solo se construye con las fabricas de outcome`:
   - `W(r=rec)`;
   - `W.model_validate({"r": rec})`;
   - `W.model_validate_json(...)`.

   Por eso `CaseDetail` (`models/api.py`), que tiene `recommendation: Recommendation | None`, no se puede construir en U8 ni leer desde JSON en el BFF de U10 sin el token.
2. **La capa 3 solo protege módulos de U0.** El contrato `token-privado` de `contracts/.importlinter` lista como `source_modules` solo submódulos de `vectra_contracts` y `vectra_common`. Un paquete de otra unidad (`vectra_case`, `scoring`, el BFF…) puede importar `vectra_contracts.outcome._internal` sin que ningún linter lo detecte. U08-T02 lo hizo (F-01). Con el token a la vista, el revisor fabricó una `Recommendation` con `registry_entry_id="inventado"` (sonda: `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/scripts/probe.py`).

Una nota que fija el alcance: **`RecommendResult.from_wire()` ya permite, por diseño, leer de JSON una `Recommendation` cuyo `registry_entry_id` es cualquier cadena no vacía.** P-U0-03 acepta eso: en la red solo rige la capa 1. Esta tarea no cambia ese poder. Lo que hace es llevar el mismo poder a los contenedores de forma pública, y cerrar el token para que nadie construya una `Recommendation` en proceso fuera de `build_outcome`.

---

## Alcance

**Dentro:**

1. **Anidar sin token (capa 2 intacta).** `_Guarded` acepta como valor una instancia **ya construida** de su propia clase sin volver a exigir el token, y lo sigue exigiendo siempre que la construcción parta de datos (dict o JSON). Mecanismo recomendado (P-1): convertir `_require_token` en un `model_validator(mode="wrap")` que devuelve el valor tal cual si `isinstance(data, cls)`, y si no, exige el token antes de llamar a `handler`. El orquestador lo probó en una réplica mínima (`/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/u0t03/espiga.py`):
   - anidar la instancia funciona;
   - un dict sin token falla;
   - un JSON contenedor sin token falla.

   Se conservan:
   - `ContractViolation` (no `ValidationError`) en la construcción directa;
   - el mensaje `"<Clase> solo se construye con las fabricas de outcome"` (`test_p_u0_03_violation_messages`);
   - `model_construct` prohibido.
2. **Leer contenedores desde JSON (capa 1).** Una función pública en `vectra_contracts.outcome`, `read_wire(model, data)` (nombre según P-2), que valida el JSON de un modelo que contiene `Recommendation` (por ejemplo `CaseDetail`) aplicando la capa 1 a la recomendación anidada, igual que `RecommendResult.from_wire()`.
   - **Rechaza `Ready`**, y cualquier modelo que lo contenga, con `ContractViolation`. `Ready` solo sale de `check_preconditions`.
   - `RecommendResult.from_wire()` se mantiene y puede reutilizar `read_wire` por dentro.
   - Se exporta en `__all__` y se documenta en `contracts/README.md`, en la sección del invariante.
3. **Token cerrado en todo el workspace (capa 3).**
   - Una prueba de U0, `contracts/tests/unit/test_token_privado_workspace.py`, recorre con `ast` **todo** el código Python del workspace (`vectra-risk/**/*.py`, sin `.venv`, `node_modules` ni `__pycache__`; la lista de raíces se deriva de los miembros del workspace en `pyproject.toml`, no se escribe a mano).
   - Falla si algún archivo fuera de `contracts/python/vectra_contracts/src/vectra_contracts/outcome/` hace cualquiera de estas cosas:
     - importa `vectra_contracts.outcome._internal` (`import`, `from … import`, también dentro de funciones);
     - nombra `CONSTRUCTION_TOKEN`;
     - pasa la cadena `"vectra_contracts.outcome._internal"` a `importlib.import_module` o a `__import__`.
   - Las pruebas de U0 en `contracts/tests/` que hoy usan el token, si las hay, quedan en una lista de permitidos explícita y comentada dentro de la prueba, con el porqué de cada una.
   - El contrato `token-privado` de `contracts/.importlinter` no se relaja.
4. **U8 deja de usar el token.**
   - `case-management/src/vectra_case/views.py` (`case_detail`) construye `CaseDetail` sin importar `_internal`, anidando la instancia de `CaseRow.recommendation`.
   - Se retira la excepción de `vectra_case.views` en `case-management/.importlinter`, y el contrato queda prohibiendo `vectra_contracts.outcome._internal` a **todo** `vectra_case`.
   - Se retira el comentario «RODEO TEMPORAL» de `views.py`, y las notas de `logic.md` y `CANDIDATAS.md` que lo anuncian se marcan como cerradas, citando U00-T03.
   - Las pruebas de U08-T02 (`case-management/tests/`) pasan **sin cambiar ninguna aserción**. Solo se permite cambiar la forma en que los dobles obtienen una `Recommendation`, si hoy usan el token. Para eso deben usar `build_outcome` o `RecommendResult.from_wire`.
5. **Documentación.** Se añade una fila o nota a P-U0-03 en `nfr-design-patterns.md` y a «Reglas de dependencia» en `logical-components.md` con lo siguiente:
   - anidar una instancia no exige el token;
   - `read_wire` es la lectura pública de contenedores y rechaza `Ready`;
   - la capa 3 se verifica en todo el workspace con la prueba de AST.

   El Paso 4 del plan de U0 (`aidlc-docs/construction/plans/contracts-code-generation-plan.md`) recibe una sub-viñeta `(U00-T03)` con su aceptación. No se reescribe el texto existente.

**Fuera:**

- Cambiar lo que comprueba la capa 1 (por ejemplo, verificar contra el registro que el `registry_entry_id` exista). U0 es puro y no hace E/S (NFR-U0-22). Ver P-3.
- Los otros AMARILLO de U08-T02 (F-02 a F-05) y la candidata de U0 sobre `anonymized` ⇒ sin `identifiers` en `CaseDetail`. Siguen en `CANDIDATAS.md`.
- Añadir razones a `ProblemReason` (F-04 de U08-T02). Se decide antes del Bloque D de U8, en otra tarea.
- Tocar los `.importlinter` de otras unidades. La prueba de AST de U0 cubre el workspace entero, también las unidades futuras como el BFF de U10.
- Cualquier cambio de comportamiento en `check_preconditions`, `build_outcome` o `_first_cause`.

---

## Archivos de contexto

- `contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py` y `outcome/_internal.py`
- `contracts/python/vectra_contracts/src/vectra_contracts/models/api.py` (`CaseDetail`) y `models/base.py` (`StrictModel`)
- `contracts/.importlinter`, `contracts/Makefile`, `contracts/README.md`, `contracts/tools/mutation.py` (lista `_internal.py`)
- `contracts/tests/unit/test_outcome.py` (BR-U0-01, BR-U0-06, P-U0-03) y `contracts/tests/property/test_logic.py` (PBT-U0-01)
- `aidlc-docs/construction/contracts/nfr-design/nfr-design-patterns.md` (P-U0-03) y `nfr-design/logical-components.md` («Reglas de dependencia»)
- `aidlc-docs/construction/plans/contracts-code-generation-plan.md` (Paso 4)
- `case-management/src/vectra_case/views.py`, `case-management/.importlinter`, `case-management/tests/doubles/case_strategies.py`, `aidlc-docs/construction/case-management/code/logic.md`
- `revisiones/U08-T02/ronda-1.md` (F-01 y las candidatas de U0) y `revisiones/U08-T02/arbitraje-ronda-1.md`
- `CANDIDATAS.md`: las entradas «U0, `CaseDetail.recommendation`» y «U0, P-U0-03»

---

## Criterios de aceptación

Todos los comandos se corren desde `vectra-risk/`. Cada criterio de comportamiento lleva **rojo previo**: se registra en la bitácora con el comando y su salida real, sobre `main` o sobre una mutación revertida.

- [ ] **CA-1 — Anidar una instancia ya construida, sin token.** Pruebas nuevas en `contracts/tests/unit/test_outcome.py`:
  - `CaseDetail.model_validate({..., "recommendation": rec})` con `rec = build_outcome(...)` devuelve un `CaseDetail` cuya `recommendation is rec` o es igual a ella;
  - un modelo de prueba `W(r=rec)` funciona.
  ```bash
  uv run pytest contracts/tests/unit/test_outcome.py -v -k "nest"
  ```
  Esperado: pasa. **Rojo previo:** las mismas pruebas sobre `main` fallan con `ContractViolation`.
- [ ] **CA-2 — La capa 2 sigue cerrada.** Siguen pasando sin cambios `test_br_u0_01_direct_construction_forbidden`, `test_p_u0_03_violation_messages` y la prohibición de `model_construct`. Hay pruebas nuevas en las que **lanzan `ContractViolation`**:
  - `Recommendation.model_validate(dict_valido)` sin contexto;
  - `CaseDetail.model_validate({..., "recommendation": dict_valido})` sin contexto;
  - `CaseDetail.model_validate_json(json)` sin contexto.
  ```bash
  uv run pytest contracts/tests/unit/test_outcome.py -v
  ```
  Esperado: pasa. **Rojo previo, por mutación:** un `_Guarded` que acepta cualquier dict cuando hay una instancia en algún nivel, o que no exige el token, hace fallar al menos una de estas pruebas. Se revierte y se registra.
- [ ] **CA-3 — `read_wire` aplica la capa 1 y rechaza `Ready`.** Pruebas nuevas:
  - `read_wire(CaseDetail, case_detail.model_dump_json()) == case_detail`, en un ida y vuelta;
  - con `explanation.model_version_id` distinto del de la recomendación → error;
  - con `registry_entry_id = ""` → error;
  - `read_wire(Ready, ...)` → `ContractViolation`;
  - `RecommendResult.from_wire` conserva su comportamiento: siguen pasando `test_br_u0_06_from_wire_roundtrip_by_kind` y `test_p_u0_03_from_wire_with_different_versions_fails`.
  ```bash
  uv run pytest contracts/tests/unit/test_outcome.py -v -k "read_wire or from_wire"
  ```
  Esperado: pasa. **Rojo previo:** sobre `main` no existe `read_wire` (`ImportError`).
- [ ] **CA-4 — PBT-U0-01 sigue en pie y cubre el anidado.** La propiedad de `contracts/tests/property/test_logic.py` añade la ida y vuelta de un `CaseDetail` con la recomendación de `build_outcome` por `read_wire`.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests/property/test_logic.py -v
  ```
  Esperado: pasa, con la semilla impresa.
- [ ] **CA-5 — Token cerrado en todo el workspace.**
  ```bash
  uv run pytest contracts/tests/unit/test_token_privado_workspace.py -v
  ```
  Esperado: pasa sobre la rama. La prueba imprime cuántos archivos recorrió y la lista de raíces derivada de `pyproject.toml`.
  - **Rojo previo, con tres variantes:** sobre `main` + el `views.py` de U08-T02 la prueba falla y nombra `case-management/src/vectra_case/views.py`. Lo mismo pasa con un archivo temporal que hace `importlib.import_module("vectra_contracts.outcome._internal")` dentro de una función, y con otro que hace `from vectra_contracts.outcome import _internal`. Los tres se registran y se revierten.
- [ ] **CA-6 — U8 sin el token.**
  ```bash
  ! grep -rnE "outcome\._internal|CONSTRUCTION_TOKEN" case-management/ \
    && uv run lint-imports --config case-management/.importlinter \
    && make -C case-management check
  ```
  Esperado: el grep no encuentra nada, import-linter da todos los contratos `KEPT` (incluido el que prohíbe `_internal` a todo `vectra_case`, sin excepciones) y `make check` da rc 0. `git diff origin/main -- case-management/tests/` no cambia ninguna línea `assert`, como mucho los dobles.
- [ ] **CA-7 — La sonda del revisor deja de funcionar.**
  ```bash
  uv run python -I /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/39ddc0f6-774f-4959-a13e-16729575788a/scratchpad/scripts/probe.py case-management/tests/doubles; test $? -ne 0
  ```
  Esperado: la sonda termina con error (`ImportError` de `_CONTEXT`). Si el archivo ya no existe en esta máquina, la bitácora reproduce su contenido (está citado en `revisiones/U08-T02/ronda-1.md`) en `contracts/tests/unit/test_token_privado_workspace.py` como caso negativo.
- [ ] **CA-8 — Documentación y plan.**
  ```bash
  grep -n "read_wire" contracts/README.md aidlc-docs/construction/contracts/nfr-design/nfr-design-patterns.md \
    && grep -n "U00-T03" aidlc-docs/construction/plans/contracts-code-generation-plan.md aidlc-docs/construction/contracts/nfr-design/logical-components.md \
    && grep -n "U00-T03" CANDIDATAS.md
  ```
  Esperado: cada grep encuentra al menos una línea. El Paso 4 del plan conserva su texto y su `[x]`, con la sub-viñeta nueva al final.
- [ ] **CA-9 — Sin regresiones en ninguna unidad que importe `vectra_contracts`.**
  ```bash
  make -C contracts check \
    && make -C case-management check \
    && make -C scoring-explainability check \
    && make -C decision-registry check \
    && make -C governance check \
    && make -C bias-monitoring check \
    && make -C model-serving check \
    && make -C reference-model check \
    && make -C platform check
  ```
  Esperado: rc 0 en todos. `make -C contracts check` incluye la regeneración del OpenAPI y del TypeScript con `git diff --exit-code`: `read_wire` no cambia ningún esquema. Si falta alguna herramienta de platform, se instala con `platform/install-tools.sh`. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6.

---

## Plan de pruebas

| Qué | Dónde | Rojo previo |
|---|---|---|
| Anidar una instancia sin token | `contracts/tests/unit/test_outcome.py` | `main`: `ContractViolation` |
| Construir desde datos sin token sigue fallando (dict, dict anidado, JSON anidado) | `test_outcome.py` | mutación de `_Guarded` |
| `read_wire`: ida y vuelta, capa 1 y `Ready` rechazado | `test_outcome.py` | `main`: no existe |
| PBT-U0-01 con `CaseDetail` | `contracts/tests/property/test_logic.py` | — (amplía una propiedad que ya existe) |
| Token cerrado en el workspace (AST) | `contracts/tests/unit/test_token_privado_workspace.py` | tres variantes de import |
| U8 sin token | `case-management/tests/` sin cambiar aserciones | grep y import-linter sobre `main` + U08-T02 |

---

## Preguntas abiertas

**P-1 — Cómo se acepta una instancia ya construida.** Hay dos opciones:
- **(a)** un validador `wrap` en `_Guarded` que devuelve la instancia si `isinstance(data, cls)` y exige el token en cualquier otro caso. Es la que propone esta tarea, probada en una réplica mínima;
- **(b)** tipar `CaseDetail.recommendation` con un modelo de lectura sin guarda, como propuso el codificador de U08-T02 en `CANDIDATAS.md`.

**Recomendación: (a).** Con (b), un `CaseDetail` podría llevar una recomendación que nunca pasó por `build_outcome` ni por la capa 1, y U10 tendría dos tipos para lo mismo. Con (a), el único modo de obtener una instancia sigue siendo `build_outcome` o `from_wire`/`read_wire`. Si no hay respuesta, rige la recomendación.

**P-2 — Forma de la lectura pública de contenedores.** Puede ser una función genérica `outcome.read_wire(model, data)` que rechaza `Ready`, o un `from_wire` por cada contenedor (`CaseDetail.from_wire`, …). **Recomendación: la genérica en `outcome`.** El token sigue sin salir de `outcome`, no hay que tocar `models/api.py`, lo que evita reabrir el import circular que cerró U00-T02, y sirve al BFF de U10 para cualquier contenedor. Si no hay respuesta, rige la recomendación.

**P-3 — ¿La rehidratación verifica algo más que la capa 1?** Por ejemplo, que el `registry_entry_id` exista en el registro. **Recomendación: no, en U0.** U0 es puro (NFR-U0-22) y P-U0-03 ya acepta la capa 1 para todo lo que llega por la red. Quien necesite la prueba de que se registró la obtiene del registro: U8 lo guarda en `recommendation_entry_id`, y el BFF de U10 lee el dossier de U3. Si no hay respuesta, rige la recomendación.

---

## Notas

- **Origen:** `revisiones/U08-T02/ronda-1.md`, F-01, NARANJA. El revisor mostró dos cosas: una `Recommendation` *sin* `registry_entry_id` es imposible (capa 1), pero una con un identificador inventado se fabricaba con el token expuesto. Esta tarea cierra el token. No cambia la capa 1.
- **No suavizar contratos:** ningún cambio en `contracts/.importlinter` puede quitar módulos de `token-privado` ni añadir excepciones.
- **Bitácora:** `bitacoras/U00-T03.md`, con el acuse del hash de esta tarea, cada rojo y cada verde con su salida real, y la respuesta a P-1, P-2 y P-3 según lo que diga el usuario o, si no responde, la recomendación.
