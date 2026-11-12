# U10-T01 — Esqueleto, constantes y lógica pura del BFF de `console`

**Unidad:** U10 `console` (`console-bff` y `console-spa`)
**Historias que implementa:** US-602 y US-611, en la parte de lógica pura (Paso 3). Los Pasos 1, 2 y 4 no tienen historia propia en la trazabilidad del plan (§3).
**Depende de:** U0 (`RouteContract` del BFF, `Problem`, catálogos, `contracts/ts`) y U2 (`realm.{kind,staging,prod}.yaml`), los dos ya en `main`. **No** depende de U3, U4, U7, U8 ni U9: es código estático, lógica pura y pruebas sin clúster ni dobles HTTP (RL-5 de `aidlc-docs/construction/plans/demo-kind-alcance.md` §6). En particular, no espera a U08-T03.
**Rama:** `tarea/U10-T01`, que parte de `origin/main`.

Son los Bloques A y B del plan de U10 (Pasos 1 a 4), juntos en una tarea según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fusión «A+B»).
- Los Pasos 1 a 3 entran **completos** (E).
- El Paso 4 entra como **E\*F**: sin `mutmut` (enmienda §3, U10, fila «4 · 16»; §2 regla 3). La cobertura del 100 % se queda.
- La verificación en kind de U10 (Paso 22) está consolidada en U12 Paso 18 (enmienda §8). El cierre de la unidad va en la última tarea de código de U10, no en esta.
- Rige el ritmo RL-1 a RL-5: una tarea por bloque fusionado, máximo 2 rondas, y solo un ROJO bloquea.

---

## Alcance

**Dentro:** los Pasos 1 a 4 del plan. Va el texto del plan sin recortes, salvo el `mutmut` del Paso 4, que se marca abajo y va en «Fuera».

### Bloque A — Estructura y constantes

- [ ] **Paso 1 — Esqueleto de `console/`**
  - Directorios de §1; `bff/pyproject.toml` como miembro del workspace de `uv` (depende de `vectra_contracts` y `vectra_common`); `spa/package.json` como workspace de npm que depende de `contracts/ts`.
  - import-linter del BFF: `object_rules` y `errors` sin E/S; ningún módulo importa `httpx` fuera de `vectra_common.deps`.
  - ESLint de la SPA: `react/no-danger` (prohíbe `dangerouslySetInnerHTML`), `jsx-a11y`, prohibición de literales de texto en JSX, de `localStorage`, de `sessionStorage` y de `Number(`/`parseFloat` sobre `Decimal*`; TypeScript con `strict` y `noUncheckedIndexedAccess`.
  - Diseño: NFR-U10-43, 53, 64; BR-U10-05, 11.
  - **Aceptación**: `uv sync --frozen && uv run lint-imports --config console/bff/.importlinter`; `npm ci --ignore-scripts -w console/spa && npm run -w console/spa lint && npm run -w console/spa typecheck` sobre el esqueleto; un fixture con `dangerouslySetInnerHTML` y otro con `localStorage.setItem` → ESLint falla.

- [ ] **Paso 2 — Constantes y configuración**
  - BFF `config.py`: timeouts, conexiones por destino y presupuesto de P-U10-04 (incluidos los 4 s de escritura en case y governance).
  - SPA `config/constants.ts`: las constantes de domain-entities §4 (step-up, inactividad, difusión de actividad, consulta de versión, `reporter`, timeout de la API, refrescos).
  - SPA `config/load.ts`: carga `config.json` (solo OIDC y el `uid` de `bias.json`) con `fetch`; falla si falta un campo o aparece uno desconocido.
  - Diseño: P-U10-04; INF-U10-03; domain-entities §4.
  - **Aceptación**: `uv run pytest console/bff/tests/unit/test_config.py` (los valores coinciden con la tabla de P-U10-04; ningún timeout ≥ 9 s); `npm run -w console/spa test -- config` (`IDLE_LOGOUT_SECONDS` = `ssoSessionIdleTimeout` de los tres `realm.{env}.yaml` de U2; un `config.json` con una constante de tiempo → error).

### Bloque B — Lógica pura del BFF

- [ ] **Paso 3 — `object_rules` y `errors`**
  - `object_rules`: una función pura por endpoint con regla de objeto de C03:
    - `record_decision` ⇔ `listo`;
    - `retry_case` ⇔ `no_disponible` y no anonimizado;
    - `approve_model` ⇔ `lista_para_aprobacion`;
    - `resolve_frozen` ⇔ `congelado`;
    - `decide_data_source` ⇔ `en_evaluacion` con informe;
    - `start_validation` ⇔ `registrado` o `validacion_fallida`;
    - `create_applicant_summary` ⇔ `decidido` con `final_outcome = desfavorable` (seguimiento de la quinta revisión de coherencia, 2026-10-31);
    - `retire_model` ⇔ `inactivo`, `rechazado` o `validacion_fallida` (cuarta revisión de coherencia entre unidades, 2026-10-31);
    - `approve_policy` ⇔ `propuesta`;
    - etc.
  - `errors`: traducción de cualquier respuesta de error de un destino al `Problem` de U0 (mismo `code`, o `internal_error`), sin `detail`; un 403 o 404 de un destino se propaga como tal.
  - Diseño: BR-U10-01, 03, 04; P-U10-01, 03. Historias: US-602, US-611.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_object_rules.py tests/property/test_errors.py`: PBT-U10-02 y PBT-U10-03.

- [ ] **Paso 4 — Resumen de la lógica pura** (E\*F)
  - Cobertura de ramas **100 %** en `object_rules` y `errors`; ~~`mutmut` en `object_rules` con 0 sobrevivientes sin justificar~~ **(diferido por la demo, T3; ver «Fuera»)**.
  - Resumen en `aidlc-docs/construction/console/code/bff-logic.md`.
  - Diseño: NFR-U10-60 (la parte de cobertura; la de `mutmut` se difiere).
  - **Aceptación**: `uv run pytest console/bff/tests/unit console/bff/tests/property --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100`; ~~`uv run mutmut run --paths-to-mutate console/bff/src/console_bff/object_rules.py`~~ (diferido, T3).

### Precisiones

- **Estructura de §1, entera.** El esqueleto crea **todos** los directorios del árbol «Estructura de destino» del plan (§1):
  - `console/Makefile`;
  - `bff/` con `pyproject.toml`, `.importlinter`, `src/console_bff/` y los módulos de §1. `config.py` (Paso 2), `object_rules.py` y `errors.py` (Paso 3) llevan código. `routes.py`, `compose.py`, `clients.py`, `client_errors.py`, `metrics.py` y `app.py` quedan como **módulos vacíos** con docstring, para que import-linter tenga qué contratar;
  - `bff/tests/` con `unit/`, `property/`, `integration/`, `doubles/` y `load/`;
  - `spa/` con `package.json`, `vite.config.ts`, `tsconfig.json`, la configuración de ESLint (ver P-1), `.size-limit.json`, `index.html`, `src/config/constants.ts`, `src/config/load.ts`, los directorios `auth/`, `stepup/`, `inactivity/`, `api/`, `i18n/`, `reporter/`, `version/`, `views/{cases,governance,bias,shared}/`, `src/stepup-callback.ts` como módulo vacío, y `tests/{unit,property,e2e,a11y,csp,poc}/`;
  - `chart/templates/`, `policies/conftest/` y `observability/{rules,rules/tests,runbooks,dashboards}/`.

  Los directorios que estos pasos no llenan se crean vacíos con `.gitkeep`. **No** se crean `nginx.conf` ni `Dockerfile` (Paso 17), `Chart.yaml`, plantillas ni values (Paso 18), `console.json` (Paso 19) ni las entradas de `vectra-risk-gitops/components.yaml` (Paso 21). Tampoco se crea `migrations/`, porque el Paso 9 es N/A.
- **Workspace de `uv`.** `console/bff/pyproject.toml` declara el paquete `vectra-console-bff` (módulo `console_bff`, como en §1) y depende de `vectra-contracts` y `vectra-common`.
  - Agrégalo a `[tool.uv.workspace].members` y a `[tool.uv.sources]` del `pyproject.toml` raíz, y regenera `uv.lock`.
  - CA-1 fija `uv sync --frozen` sin grupos, así que `vectra-console-bff` va editable en el grupo `dev` de la raíz, como hicieron U8 y U9.
  - Si al abrir el PR ya se fusionó otra tarea que tocó el workspace (U03-T07, U07-T04 y U08-T03 corren en paralelo), el orquestador rebasa y vuelve a correr `uv lock`.
- **Workspace de npm (P-2).** `console/spa` se agrega a `"workspaces"` del `package.json` raíz, junto a `contracts/ts`, y depende de `@vectra/contracts` con `"*"` (workspace). El lockfile es el `package-lock.json` raíz; no hay un `spa/package-lock.json` aparte.
  - Todas las versiones van fijadas exactas, como en `contracts/ts/package.json`: React, React DOM, Vite, Vitest, TypeScript, ESLint y sus plugins (`eslint-plugin-react`, `eslint-plugin-jsx-a11y`, `@typescript-eslint/*`) y `oidc-client-ts`.
  - El workflow `contracts.yml` corre `npm ci` y `npm audit --audit-level=high` sobre el lockfile raíz, así que esas dependencias quedan auditadas ahí. Una vulnerabilidad alta lo rompe: elige versiones sin avisos altos y regístralo en la bitácora.
- **Reglas de ESLint del Paso 1.**
  - Literales en JSX: `react/jsx-no-literals` (NFR-U10-53).
  - Almacenamiento: `no-restricted-globals` y `no-restricted-properties` para `localStorage` y `sessionStorage`, también como `window.localStorage` (BR-U10-05).
  - `Number(` y `parseFloat`: las mismas reglas que `contracts/ts/eslint.config.mjs`.
  - Los fixtures que deben fallar viven en `spa/tests/unit/eslint-fixtures/`, fuera de lo que lintea `npm run lint`, y una prueba de Vitest los pasa por la API de ESLint (`new ESLint().lintFiles`) y exige error. Así la prueba queda en `make check` sin romper el lint normal.
- **`config.py` del BFF y P-U10-04.**
  - La prueba compara las constantes con la tabla de P-U10-04, leída del documento de diseño o transcrita una sola vez en la prueba con la cita: los timeouts por destino y operación, las conexiones por réplica y el presupuesto de 9 s (`x-vectra-deadline` = entrada + 9 s).
  - «Ningún timeout ≥ 9 s» se comprueba sobre todos los timeouts del módulo.
  - Ninguna constante se lee de variables de entorno.
- **`IDLE_LOGOUT_SECONDS` contra U2.** La prueba de Vitest lee `identity-edge/keycloak/realm/realm.kind.yaml`, `realm.staging.yaml` y `realm.prod.yaml` (los tres de U2; hoy los tres dicen `ssoSessionIdleTimeout: 1800`) y compara. Si necesitas un parser de YAML en la SPA, va como dependencia de desarrollo fijada.
- **`load.ts`.**
  - El esquema de `config.json` es exactamente el de domain-entities §4: `oidc.authority`, `oidc.client_id`, `redirect_uri`, `stepup_redirect_uri` y `grafana.bias_dashboard_uid`.
  - Un campo faltante o desconocido → error.
  - Una constante de la segunda tabla (por ejemplo `IDLE_LOGOUT_SECONDS`) dentro de `config.json` → error.
- **`object_rules`.**
  - Hay una función pura por cada endpoint de C03 (`aidlc-docs/inception/application-design/component-methods.md`) cuya columna «Objeto» dependa del **estado** de un objeto. Cada una recibe ese estado, tipado con los tipos de U0 (`CaseState`, `FinalOutcome`, los `Literal` de estado de `models/governance.py`), y devuelve aceptar, 403 o 409 (P-U10-01). La lista de la viñeta del Paso 3 termina en «etc.»: el codificador la completa contra C03, sin inventar reglas.
  - Las filas con «—» o «el caso existe» no llevan función, porque ese 404 lo da el destino.
  - La regla de `approve_policy` incluye «`rechazada` exige `justification`» (C03, 2026-11-01).
  - El oráculo de PBT-U10-02 es una tabla escrita en la prueba que transcribe la columna «Objeto» de C03, con cita de fila, nunca la propia implementación.
  - Dónde se ata cada regla a su ruta lo decide P-3. En esta tarea, `object_rules` solo expone las funciones y un mapa de nombres de operación a regla.
- **`errors`.**
  - La salida siempre valida como `Problem` de U0 (`vectra_contracts.models.api.Problem`), sin `detail` ni campos extra.
  - El `code` del destino se conserva si pertenece a `ProblemCode`; si no, o si el cuerpo está malformado, sale `internal_error` con estado 500.
  - Un 403 o 404 del destino se propaga con su estado y su `code`.
  - PBT-U10-03 genera códigos, cuerpos arbitrarios y cuerpos malformados.
- **`mypy --strict`** sobre `console/bff/src` (NFR-U10-64), dentro de `make -C console check`.
- **Cobertura.** `[tool.coverage.run] source` de la raíz solo mide U0. Como U8 y U9, usa un `console/bff/pytest.ini` propio con la cobertura apuntada a `console_bff`.
- **`make -C console check`.** Corre en orden:
  - en el BFF: `ruff check`, `ruff format --check`, `mypy --strict` e import-linter;
  - en la SPA: `npm run -w console/spa lint`, `typecheck` y `test`;
  - las pruebas del BFF con el perfil `ci` y la cobertura del 100 % del Paso 4.

  Termina en 0. Los pasos posteriores lo amplían (Paso 24).
- **Plan.** Marca `[x]` los Pasos 1 a 4, con `(U10-T01)`. En el Paso 4, agrega la nota «`mutmut` diferido por la demo (T3)».

**Fuera** (recházalo aunque lo veas roto o tentador):

- **`mutmut` del Paso 4** y la parte de `mutmut` de NFR-U10-60. Recorte E\*F: enmienda §3, U10, fila «4 · 16»: «Sin `mutmut` ni Stryker (T3)»; y §2 regla 3, que nombra «U10 Pasos 4, 16 y 21». La dependencia `mutmut` ya está en el grupo `dev`.
- Bloques C a H de U10 (Pasos 5 a 24): rutas, clientes, composición, `client_errors`, métricas, arranque, la matriz rol × endpoint (PBT-U10-01), toda la SPA más allá de `config/`, imágenes, chart, alertas, workflows, Applications y documentación. Los módulos de `console_bff` distintos de `config.py`, `object_rules.py` y `errors.py` quedan vacíos.
- Atar las reglas de objeto a cada ruta y la prueba de arranque «una ruta sin `object_rule` → error» (P-U10-01): son del Paso 5 (Bloque C), según P-3.
- Candidatas que apuntan a U10 y no son de estos pasos (quedan para los bloques que las tocan):
  - `CANDIDATAS.md` «U4/U10, runbook de política sin BFF» y «U4/U10, `ServiceAccount` `console-bff`»: Bloque F, chart.
  - «U0, `vectra_common` … `principal_role` en los logs de consulta (U8, U9 y U10)»: Bloque C.
  - La lectura de `CaseDetail.recommendation` con `read_wire`, de U00-T03: Bloque C.
- Cambios a U0, a U2 o a `contracts/ts`. Si un tipo o catálogo de U0 no alcanza para `object_rules` o `errors`, se reporta.

---

## Preguntas (si nadie responde, rige la recomendación)

- **P-1 — Formato de la configuración de ESLint.** §1 del plan nombra `spa/.eslintrc.cjs`, pero el repositorio fija ESLint 10 (`contracts/ts/package.json`, `eslint` 10.14.0), que solo admite la configuración plana (`eslint.config.mjs`), igual que `contracts/ts`.
  - **(a) recomendada:** `spa/eslint.config.mjs` plano, con las mismas reglas del Paso 1, y una nota en §1 del plan.
  - (b) Fijar ESLint 8 solo en la SPA para usar `.eslintrc.cjs`. Habría dos versiones mayores de ESLint en el mismo lockfile.
- **P-2 — Lockfile de la SPA.** §1 lista `spa/package-lock.json`, pero la aceptación del Paso 1 usa `npm ci -w console/spa`, que es el modo workspace del `package.json` raíz, y npm genera un único lockfile raíz.
  - **(a) recomendada:** `console/spa` como workspace del `package.json` raíz, con el `package-lock.json` raíz y sin lockfile propio, y una nota en §1.
  - (b) La SPA como proyecto npm independiente con su propio lockfile. La aceptación del Paso 1 dejaría de funcionar tal como está escrita y `@vectra/contracts` habría que enlazarlo a mano.
- **P-3 — Dónde vive la `object_rule` de cada ruta.** P-U10-01 dice que cada `RouteContract` de U0 lleva una `object_rule`, pero el `RouteContract` de U0 (`contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py`) no tiene ese campo.
  - **(a) recomendada:** no tocar U0. `object_rules` expone un mapa `operation_id → regla | None`, y en el Paso 5 (Bloque C) `routes.py` exige al arrancar que las 30 rutas del BFF estén en el mapa, con `None` declarado si no hay regla (deny by default). En esta tarea entran solo las funciones y el mapa.
  - (b) Agregar `object_rule` al `RouteContract` de U0 en una tarea de U0. Toca el contrato compartido de todas las unidades.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/console-code-generation-plan.md` (§1, Bloques A y B, §3)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§2, T1–T6, §6 RL-1 a RL-5)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§2, §3 U10, §4, §8)
- `aidlc-docs/inception/application-design/component-methods.md` (C03, las cinco tablas: columnas «Roles», «MFA» y «Objeto»)
- `aidlc-docs/construction/console/functional-design/business-rules.md` (BR-U10-01, 03, 04, 05, 11)
- `aidlc-docs/construction/console/functional-design/business-logic-model.md` (PBT-U10-02 y 03)
- `aidlc-docs/construction/console/functional-design/domain-entities.md` (§4)
- `aidlc-docs/construction/console/nfr-requirements/nfr-requirements.md` (NFR-U10-43, 53, 60, 64) y `tech-stack-decisions.md`
- `aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md` (P-U10-01, 03, 04)
- `aidlc-docs/construction/console/infrastructure-design/infrastructure-design.md` (INF-U10-03)
- `contracts/python/vectra_contracts/src/vectra_contracts/routes/__init__.py` (`_bff()`, las 30 rutas), `catalog.py` (`ProblemCode`, `CaseState`, `FinalOutcome`, `Role`), `models/api.py` (`Problem`) y `models/governance.py` (estados de modelo, política y fuente)
- `contracts/ts/package.json` y `contracts/ts/eslint.config.mjs` (versiones fijadas y reglas de decimales)
- `identity-edge/keycloak/realm/realm.{kind,staging,prod}.yaml` (`ssoSessionIdleTimeout`)
- `case-management/Makefile`, `case-management/pyproject.toml`, `case-management/pytest.ini` y `case-management/.importlinter`, como ejemplo de miembro del workspace
- `tareas/U09-T01-esqueleto-y-libreria.md` y `tareas/U08-T01-esqueleto-y-migraciones.md` (modelo de esqueleto)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Sobre `main` (`a10b930`) los comandos de CA-1, CA-3, CA-4 y CA-6 fallan (código 1, 1, 4 y 4), porque `console/` no existe. Ese es el rojo esperado.

- [ ] **CA-1** — Esqueleto del BFF, dependencias y contratos de imports (Paso 1; NFR-U10-64).
  ```bash
  uv sync --frozen && uv run lint-imports --config console/bff/.importlinter
  ```
  Esperado: código 0, con los contratos del Paso 1 (`object_rules` y `errors` sin E/S; `httpx` solo desde `vectra_common.deps`) listados como `KEPT`. **Rojo primero:** un `import httpx` en `object_rules.py` y otro en `routes.py` hacen fallar sus contratos.

- [ ] **CA-2** — Estructura completa de §1.
  ```bash
  cd console && for p in Makefile bff/pyproject.toml bff/.importlinter bff/src/console_bff/config.py bff/src/console_bff/object_rules.py bff/src/console_bff/errors.py bff/src/console_bff/routes.py bff/src/console_bff/compose.py bff/src/console_bff/clients.py bff/src/console_bff/client_errors.py bff/src/console_bff/metrics.py bff/src/console_bff/app.py bff/tests/unit bff/tests/property bff/tests/integration bff/tests/doubles bff/tests/load spa/package.json spa/vite.config.ts spa/tsconfig.json spa/.size-limit.json spa/index.html spa/src/config/constants.ts spa/src/config/load.ts spa/src/auth spa/src/stepup spa/src/inactivity spa/src/api spa/src/i18n spa/src/reporter spa/src/version spa/src/views/cases spa/src/views/governance spa/src/views/bias spa/src/views/shared spa/src/stepup-callback.ts spa/tests/unit spa/tests/property spa/tests/e2e spa/tests/a11y spa/tests/csp spa/tests/poc chart/templates policies/conftest observability/rules/tests observability/runbooks observability/dashboards; do test -e "$p" || echo "FALTA $p"; done; test ! -d migrations && echo OK
  ```
  Esperado: ninguna línea `FALTA` y `OK` al final. La configuración de ESLint (`spa/eslint.config.mjs` según P-1) también existe.

- [ ] **CA-3** — ESLint y TypeScript de la SPA (Paso 1; NFR-U10-43, 53, 64; BR-U10-05, 11).
  ```bash
  npm ci --ignore-scripts -w console/spa && npm run -w console/spa lint && npm run -w console/spa typecheck && npm run -w console/spa test -- eslint
  ```
  Esperado: código 0. La prueba `eslint` pasa por ESLint los fixtures de `spa/tests/unit/eslint-fixtures/` y exige un error en cada uno: `dangerouslySetInnerHTML`, `localStorage.setItem`, `window.sessionStorage`, un literal de texto en JSX y `Number(` sobre un `Decimal4`. `tsconfig.json` tiene `strict` y `noUncheckedIndexedAccess` (la prueba lo comprueba). **Rojo primero:** sin `react/no-danger`, el fixture de `dangerouslySetInnerHTML` pasa y la prueba falla.

- [ ] **CA-4** — Constantes y configuración del BFF (Paso 2; P-U10-04).
  ```bash
  uv run pytest console/bff/tests/unit/test_config.py -v
  ```
  Esperado: pasan los casos:
  - cada timeout, límite de conexiones y el presupuesto de 9 s coinciden con P-U10-04 (incluidos los 4 s de las escrituras de case y governance);
  - ningún timeout ≥ 9 s;
  - ninguna constante se lee del entorno.

  **Rojo primero:** con 3 s en la escritura de case, la prueba falla.

- [ ] **CA-5** — Constantes y `config.json` de la SPA (Paso 2; INF-U10-03; domain-entities §4).
  ```bash
  npm run -w console/spa test -- config
  ```
  Esperado: pasan los casos:
  - las constantes coinciden con domain-entities §4;
  - `IDLE_LOGOUT_SECONDS` = `ssoSessionIdleTimeout` de `realm.kind.yaml`, `realm.staging.yaml` y `realm.prod.yaml`;
  - `load.ts` rechaza un `config.json` con un campo faltante, con uno desconocido y con una constante de tiempo;
  - acepta uno completo.

- [ ] **CA-6** — `object_rules` y `errors`: PBT-U10-02 y PBT-U10-03 (Paso 3; BR-U10-01, 03, 04; P-U10-01, 03; US-602, US-611).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_object_rules.py console/bff/tests/property/test_errors.py -v
  ```
  Esperado: todo pasa.
  - PBT-U10-02 recorre los estados de caso, modelo, política y fuente contra la tabla-oráculo que transcribe C03, con una fila por regla.
  - PBT-U10-03 genera respuestas de error y comprueba que la salida valida como `Problem` de U0, sin `detail`, con el mismo `code` o `internal_error`, y con 403 y 404 propagados.

  **Rojo primero:** con `retire_model` sin `validacion_fallida` (la regla anterior a la cuarta revisión de coherencia), PBT-U10-02 falla; con `detail` en la salida, PBT-U10-03 falla.

- [ ] **CA-7** — Cobertura de ramas del 100 % y resumen (Paso 4; NFR-U10-60).
  ```bash
  uv run pytest console/bff/tests/unit console/bff/tests/property --cov=console_bff.object_rules --cov=console_bff.errors --cov-branch --cov-fail-under=100 && test -s aidlc-docs/construction/console/code/bff-logic.md
  ```
  Esperado: código 0, con `TOTAL … 100%` sobre los dos módulos. `bff-logic.md` lista cada regla de objeto con su fila de C03 y la traducción de errores.

- [ ] **CA-8** — `check` de la unidad (RL-4), más U0 y U1, porque el diff toca los workspaces de `uv` y de npm.
  ```bash
  make -C console check && make -C contracts check && make -C platform check
  ```
  Esperado: código 0 en los tres, corridos **en serie**, con `uptime` antes y después de cada uno en la bitácora. `contracts check` corre `npm ci` y las pruebas de `contracts/ts` con el lockfile raíz nuevo. Si su `bench_gate` falla por carga, se anota con la carga y se repite aislado en la rama y en la base. Antes de abrir el PR, corre también `npm audit --audit-level=high`, como `contracts.yml`, y pega la salida.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `bff/tests/unit/test_config.py`: P-U10-04, timeouts < 9 s y nada leído del entorno (Paso 2).
- `bff/tests/property/test_object_rules.py`: PBT-U10-02, con oráculo transcrito de C03.
- `bff/tests/property/test_errors.py`: PBT-U10-03.
- Pruebas unitarias de ejemplo en `bff/tests/unit/` para las ramas que las PBT no alcancen: estado límite por regla, cuerpo vacío, cuerpo no JSON y `code` desconocido.
- `spa/tests/unit/eslint.test.ts`, con los fixtures de `eslint-fixtures/` (Paso 1).
- `spa/tests/unit/config.test.ts`: constantes, realm de U2 y `load.ts` (Paso 2).
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U10-T01.md`. Como mínimo: CA-1 (import prohibido), CA-3 (fixture que pasa sin la regla), CA-4 (timeout de 3 s) y CA-6 (`retire_model` sin `validacion_fallida`). El par falla-pasa es la prueba.

---

## Notas

- Archivos que se **modifican en su sitio**: `pyproject.toml` raíz, `uv.lock`, `package.json` raíz, `package-lock.json` raíz y `aidlc-docs/construction/plans/console-code-generation-plan.md` (casillas de los Pasos 1 a 4, y las notas de P-1 y P-2 en §1). Nada de duplicados con sufijo.
- Archivo nuevo de documentación que pide el plan: `aidlc-docs/construction/console/code/bff-logic.md`.
- PBT-U10-01..06 nunca se recortan. En esta tarea entran las dos del Bloque B (02 y 03). La 01 es del Paso 7, la 04 del 13, la 05 del 11 y la 06 del 12.
- La bitácora pega la **salida real** de cada comando, con rutas absolutas a los logs, y sin plantillas sin expandir del tipo `{open(...)}`. El revisor de U09-T04 marcó ese caso como NARANJA.
- Máquina compartida: corre los `make check` en serie, con `uptime` antes y después. Si una corrida pasa más de 2 horas sin avanzar, detenla, anótalo y repítela.
