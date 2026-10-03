# Plan de tareas (Code Generation Part 1) — U0 `contracts`

**Este plan es la única fuente de verdad para generar el código de U0.**

> **Alcance del trabajo actual (instrucción del usuario, `aidlc-state.md`):** aquí se
> detiene U0. Code Generation Part 2 y Build and Test **no** se ejecutan. Las casillas
> quedan en `[ ]` para quien implemente.

---

## 1. Contexto de la unidad

| Aspecto | Valor |
|---|---|
| Unidad | U0 `contracts`: habilitadora, sin historias propias |
| Contribuye a | US-111 (invariante de sincronía), US-601/US-602 (middleware de authn/authz), US-604 (logger sin PII), US-611 (errores genéricos) |
| Proyecto | Greenfield, monorepo multi-unidad |
| Ubicación del código | `vectra-risk/contracts/` en la raíz del workspace (nunca en `aidlc-docs/`) |
| Datos propios | Ninguno: sin base de datos, sin migraciones |
| Despliegue | Ninguno: librerías que importan los servicios; sin chart ni imagen propia |
| Depende de | Nada en build. En runtime usa Keycloak (JWKS) y el OTel Collector, que llegan con U1 y U2 |
| Consumen U0 | U2 (catálogo de scopes), U3, U4, U7, U8, U9, U11 (librerías), U10 (cliente TS), U5 (derivación de features), U12 (pruebas) |

**Diseño de entrada:**
- Functional Design: `construction/contracts/functional-design/` (BR-U0-01..95, PBT-U0-01..13).
- NFR Requirements: `construction/contracts/nfr-requirements/` (NFR-U0-01..46, stack).
- NFR Design: `construction/contracts/nfr-design/` (P-U0-01..12, componentes lógicos).

**Restricciones transversales de este plan:**
- **AUTONOMIA-01**: ninguna tarea toca un clúster. U0 no tiene `kubectl`, `helm` ni `terraform`. El destino de cada tarea es un PR con evidencia (salida de pruebas).
- **AUTONOMIA-02**: cada tarea tiene un criterio de aceptación que se verifica con un comando.
- **PBT-01..10**: cada propiedad PBT-U0-xx tiene su tarea (Paso 6 y Paso 12), con los generadores de NFR-U0-44 y los perfiles de NFR-U0-42.

### Estructura de destino

```text
vectra-risk/
|-- pyproject.toml                     # workspace uv (raíz)
|-- uv.lock
|-- package.json                       # workspace npm (raíz)
`-- contracts/
    |-- Makefile                       # openapi, ts, check, bench
    |-- openapi/                       # specs generadas y versionadas
    |-- python/
    |   |-- vectra_contracts/
    |   |   |-- pyproject.toml
    |   |   `-- src/vectra_contracts/
    |   |       |-- models/            # tipos de dominio y de API
    |   |       |-- outcome/           # check_preconditions, build_outcome, _internal
    |   |       |-- finance.py  labels.py  dictionary.py  validation.py
    |   |       |-- canonical.py       # JCS (RFC 8785)
    |   |       |-- catalog.py         # Scope, Role, ReasonCode, códigos de error
    |   |       |-- routes/            # registro de contratos por servicio
    |   |       `-- data/              # divipola.csv, regions.csv, MANIFEST.json
    |   `-- vectra_common/
    |       |-- pyproject.toml
    |       `-- src/vectra_common/
    |           |-- app_factory.py  authn.py  jwks_cache.py  authz.py
    |           |-- errors.py  deps.py  logging.py  telemetry.py  metrics.py
    |           `-- decimal_ctx.py
    |-- ts/                            # cliente TypeScript
    |   |-- package.json  src/  test/
    |-- tools/                         # codegen, traceability, bench_gate
    `-- tests/
        |-- strategies/                # generadores Hypothesis compartidos
        |-- unit/  property/  examples/  bench/  arch/
        `-- conftest.py                # perfiles ci / nightly
```

---

## 2. Pasos

### Bloque A — Estructura del proyecto

- [ ] **Paso 1 — Workspace y paquetes vacíos**
  - Crear `pyproject.toml` raíz (workspace `uv`, Python 3.12), los `pyproject.toml` de `vectra_contracts` y `vectra_common` (dependencia de ruta de uno al otro, en ese sentido), `package.json` raíz con el workspace `contracts/ts` y `contracts/Makefile`.
  - Dependencias pinneadas: pydantic v2, fastapi, pyjwt[crypto], structlog, opentelemetry-sdk + exporter OTLP, prometheus-client, httpx; dev: pytest, hypothesis, pytest-cov, pytest-benchmark, mutmut, import-linter, ruff, mypy.
  - NFR: NFR-U0-31, 32. Reglas: BR-U0-90 (una sola versión SemVer, `0.1.0`, compartida por `vectra_contracts`, `vectra_common` y `contracts/ts`).
  - **Aceptación**: `uv lock --check && uv sync --frozen && uv run python -c "import vectra_contracts, vectra_common"`.

- [ ] **Paso 2 — Contratos de arquitectura (import-linter) y perfiles de pruebas**
  - `contracts/.importlinter`, con estas reglas:
    - `vectra_contracts` no importa `vectra_common`, `fastapi`, `httpx`, `os`, `random` ni `datetime.now`;
    - solo `outcome` importa `outcome._internal`;
    - solo `vectra_common.deps` importa `httpx`.
  - `tests/conftest.py`: perfiles Hypothesis `ci` (500 ejemplos, `print_blob=True`) y `nightly` (10 000).
  - NFR: NFR-U0-22, 42, 43; P-U0-03, P-U0-07.
  - **Aceptación**: `uv run lint-imports --config contracts/.importlinter` pasa; `HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests --collect-only` muestra el perfil `ci`.

### Bloque B — Lógica de negocio (`vectra_contracts`)

- [ ] **Paso 3 — Catálogos y tipos de dominio**
  - `catalog.py`: `Scope` (domain-entities §7.2, incluidos `core:read-credit` y `core:write-credit`), `Role`, `ReasonCode`, `FailClosedCause` (10, en el orden de BR-U0-02), `ProblemCode`.
  - `models/`: todos los tipos de domain-entities §1–§9 en Pydantic v2 `strict`, `extra="forbid"`; `Decimal4`/`Decimal` como cadena con patrón (BR-U0-15); `FeatureValue` discriminado; `RecommendResult` discriminado por `kind`; `LogRecord`.
  - Reglas: BR-U0-15, 20..36, 95. Historias: US-111, US-602.
  - **Aceptación**: `uv run mypy --strict contracts/python` sin errores; `uv run pytest contracts/tests/unit/test_models.py` (campos extra → error; `Decimal4` numérico → error; enums cerrados).

- [ ] **Paso 4 — Invariante en dos fases**
  - `outcome/`: `check_preconditions` (causas 1–9), `build_outcome` (causa 10), `Ready` y `Recommendation` con un token privado en `_internal`, `model_validator` estructural y `RecommendResult.from_wire()`.
  - Reglas: BR-U0-01..08. Patrón: P-U0-03. Historia: US-111. Extensión: AUTONOMIA-06.
  - **Aceptación**: `uv run pytest contracts/tests/unit/test_outcome.py` (incluye la construcción directa de `Recommendation(...)` y `Ready(...)` → `ContractViolation`, y `from_wire` con versiones distintas → error).

- [ ] **Paso 5 — Finanzas, etiquetas, diccionario, JCS y datos DANE**
  - `decimal_ctx` (P-U0-10), `finance.py` (BR-U0-10..14), `labels.py` (BR-U0-40..43), `dictionary.py` (BR-U0-80..81), `canonical.py` (JCS para `feature_vector_hash`), `validation.py` (validaciones cruzadas de BR-U0-22..28, 32..35).
  - `data/`: snapshot DIVIPOLA y tabla de regiones con `MANIFEST.json` (fecha de corte, fuente, SHA-256), verificado al importar. **[VERIFICAR]** la fecha de corte vigente.
  - NFR: NFR-U0-20, 21, 22.
  - **Aceptación**: `uv run pytest contracts/tests/unit/test_finance.py test_labels.py test_dictionary.py test_canonical.py test_data_integrity.py test_derive_spec.py` (un byte alterado en `divipola.csv` → error al importar; `derive` con un `feature_spec` de fixture aplica la búsqueda y el campo de identificación de origen no aparece en el `FeatureVector`, agregado por U5 FD).

- [ ] **Paso 6 — Generadores y propiedades de la lógica de negocio**
  - `tests/strategies/`: solicitud colombiana realista, `FeatureVector`, `MonitoringLabels`, `Explanation`, `ExplainerError`, `ServingState`, `Principal` (NFR-U0-44).
  - Propiedades: PBT-U0-01 (oráculo por tabla de verdad de las 10 causas y las dos fases, incluida la discrepancia de versión pedida agregada por U8 FD Q1), 02 (round-trip JSON de todos los tipos), 03, 04, 05, 06, 10, 11, 12, 13.
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests/property -m "not common"`; cada falla imprime la semilla.

- [ ] **Paso 7 — Pruebas de ejemplo obligatorias de la lógica (PBT-10)**
  - Tabla de verdad nombrada de `build_outcome` (una por causa y por par de causas que prueba la precedencia), cuota de un crédito calculado a mano, hash JCS de un vector conocido, matriz de `DecisionIn` contra cada `outcome` (BR-U0-35), contexto decimal global alterado sin efecto (P-U0-10), `PolicyDraft` con vigencias normativas solapadas → `validation_error` (BR-U0-33) (agregado al revisar los cambios de U4). La prueba de `normative_current` nulo pasa a U7: produce `revision_requerida` con `parametro_normativo_no_vigente`, no un fail-closed (U7 FD Q1).
  - **Aceptación**: `uv run pytest contracts/tests/examples -m logic`.

- [ ] **Paso 8 — Resumen de la lógica de negocio**
  - `aidlc-docs/construction/contracts/code/business-logic-summary.md`: módulos, reglas implementadas (BR → archivo → prueba).
  - **Aceptación**: `uv run python contracts/tools/traceability.py --section logic` encuentra cada BR-U0-01..43, 80..81, 95 en `contracts/tests/`.

### Bloque C — Capa de API (registro de contratos y `vectra_common`)

- [ ] **Paso 9 — Registro de contratos de rutas**
  - `routes/`: un `RouteContract` por ruta de cada servicio (case, scoring, explainability, governance, bias, registry, core-banking-mock, console-bff), con scopes, roles y MFA según `component-methods.md` y `component-dependency.md` §2.
  - Patrón: P-U0-12. Historia: US-602.
  - **Aceptación**: `uv run pytest contracts/tests/unit/test_routes.py` (toda ruta declara requisitos; `POST /v1/credits/{id}/status` exige `core:write-credit`; ningún scope fuera del catálogo).

- [ ] **Paso 10 — Middleware y fábrica de app**
  - `telemetry.py` (P-U0-11, BR-U0-62), `jwks_cache.py` + `authn.py` (P-U0-06, BR-U0-70, NFR-U0-10..12), `authz.py` (P-U0-02, BR-U0-71..73), `errors.py` (P-U0-05, BR-U0-60..61), `deps.py` (P-U0-07: timeout obligatorio y circuit breaker con propiedad stateful, agregado por U7 NFR Q4; `deadline=` con la cabecera `x-vectra-deadline` y un cliente por dependencia con límite de conexiones, agregados por U7 NFR Design Q1 y Q4), `deadline.py` (lectura de la cabecera entrante), `logging.py` (P-U0-04, BR-U0-50..53), `metrics.py`, `app_factory.py` (P-U0-01: orden fijo, puerto 8081 separado, verificación de rutas contra el registro y deny by default).
  - Historias: US-601, US-602, US-604, US-611.
  - **Aceptación**: `uv run pytest contracts/tests/unit/test_app_factory.py test_authn.py test_jwks_cache.py test_authz.py test_errors.py test_logging.py test_telemetry.py test_deps.py test_deadline.py`.

- [ ] **Paso 11 — Pruebas de ejemplo de la capa de API**
  - Respuestas exactas para 400, 401 (`alg=none`, `HS256`, `aud` sin el servicio, vencido por 31 s), 403, `mfa_required` (sin `acr = mfa`, y con `auth_time` de 901 s frente a 900 s aceptado), 415 y 422. Un token con varias audiencias que incluye el servicio → aceptado (BR-U0-70 precisado por U2).
  - JWKS caído con cache vencida → 503; 100 requests concurrentes con `kid` desconocido → 1 refresco.
  - Log de `httpx` con PII → ausente; modo `strict` con clave no permitida → excepción.
  - Excepción de terceros → `internal_error`; app con una ruta sin requisitos o un handler de más → falla al arrancar.
  - Orden exacto del stack de middlewares.
  - **Aceptación**: `uv run pytest contracts/tests/examples -m api`.

- [ ] **Paso 12 — Propiedades de la capa de API**
  - PBT-U0-07 (logging), 08 (errores), 09 (authz como oráculo de conjuntos, con MFA).
  - **Aceptación**: `HYPOTHESIS_PROFILE=ci uv run pytest contracts/tests/property -m common`.

- [ ] **Paso 13 — Resumen de la capa de API**
  - `aidlc-docs/construction/contracts/code/api-layer-summary.md`: pipeline, patrones P-U0-01..07, 11 y 12 → archivos → pruebas.
  - **Aceptación**: `uv run python contracts/tools/traceability.py --section api` encuentra cada BR-U0-50..73 en las pruebas.

### Bloque D — Capa de repositorio

- [ ] **Paso 14 — N/A**: U0 no tiene persistencia (sin datos propios). Cada unidad dueña de una base define su repositorio.
  - **Aceptación**: `test ! -d contracts/python/vectra_contracts/src/vectra_contracts/repository` (no existe la carpeta).

### Bloque E — Generación de specs y cliente TypeScript

- [ ] **Paso 15 — Generación de specs, catálogo para U2 y matriz US-602**
  - `tools/codegen.py` + `make -C contracts openapi`: specs `openapi/{service}.yaml`, `openapi/scopes-catalog.json` (para el realm de U2) y `openapi/role-endpoint-matrix.md` (US-602).
  - NFR: NFR-U0-30. Reglas: BR-U0-93 (las specs salen solo del registro de contratos de U0, la fuente autoritativa).
  - **Aceptación**: `make -C contracts openapi && git diff --exit-code contracts/openapi/`.

- [ ] **Paso 16 — Cliente TS**
  - `contracts/ts`: tipos con `openapi-typescript`, cliente `openapi-fetch`, utilidades `decimal.js` para `Decimal4`; regla de ESLint que prohíbe `Number(`/`parseFloat` sobre tipos `Decimal*`.
  - NFR: NFR-U0-34.
  - **Aceptación**: `npm run -w contracts/ts typecheck && npm run -w contracts/ts lint`.

- [ ] **Paso 17 — Propiedades y pruebas del cliente TS**
  - fast-check + Vitest: round-trip de `RecommendResult` (por `kind`), `Decimal4` como cadena sin pérdida, `FeatureValue`.
  - NFR: NFR-U0-45.
  - **Aceptación**: `npm run -w contracts/ts test` (semilla impresa en cada falla).

- [ ] **Paso 18 — Resumen del cliente y las specs**
  - `aidlc-docs/construction/contracts/code/contracts-and-client-summary.md`.
  - **Aceptación**: `test -s aidlc-docs/construction/contracts/code/contracts-and-client-summary.md`.

### Bloque F — Calidad, compatibilidad y CI

- [ ] **Paso 19 — Benchmarks y umbrales**
  - `tests/bench/` con los casos `pipeline`, `outcome` y `derive`; `tools/bench_gate.py` con los umbrales de NFR-U0-01..03.
  - **Aceptación**: `uv run pytest contracts/tests/bench -m benchmark --benchmark-json=benchmark.json && uv run python contracts/tools/bench_gate.py benchmark.json`.

- [ ] **Paso 20 — Cobertura, mutación y trazabilidad**
  - Configuración de cobertura de ramas (≥ 95 % global; 100 % en `outcome`, `authz`, `logging`), `mutmut` en `outcome` y `authz` con `mutmut-allowlist.txt`, y `tools/traceability.py` completo (cada BR-U0-xx tiene al menos una prueba).
  - NFR: NFR-U0-35, 40, 41.
  - **Aceptación**: `uv run pytest contracts/tests --cov --cov-branch --cov-fail-under=95`, `uv run python contracts/tools/coverage_gate.py` (umbral por módulo), `uv run mutmut run` y `uv run mutmut results` sin sobrevivientes fuera de la allowlist, y `uv run python contracts/tools/traceability.py --all`.

- [ ] **Paso 21 — Workflow de CI de U0**
  - `.github/workflows/contracts.yml`, que corre en cada PR que toca `contracts/`:
    - `uv sync --frozen`, ruff, mypy e import-linter;
    - pruebas con el perfil `ci` y la semilla impresa, guardando `.hypothesis/` como artefacto;
    - cobertura, benchmark y specs sin diff;
    - `oasdiff breaking --fail-on ERR` contra la última etiqueta `contracts-vX.Y.Z` (se omite si todavía no hay etiqueta);
    - pruebas TS.
  - Reglas: BR-U0-91 (un cambio incompatible exige subir la versión mayor) y BR-U0-92 (el build falla si no se sube).
  - Pruebas de versionado en `contracts/tests/unit/test_versioning.py`, una por regla:
    - BR-U0-90: las versiones de los tres paquetes son iguales;
    - BR-U0-91: con specs de fixture que eliminan un campo y sin subir la mayor, `tools/version_gate.py` falla, y subiéndola pasa;
    - BR-U0-92: `version_gate.py` invoca `oasdiff breaking` y propaga su código de salida;
    - BR-U0-93: no existe ninguna spec en `contracts/openapi/` sin su `RouteContract` en el registro.
  - Job nocturno con el perfil `nightly` y `mutmut`.
  - El escaneo de dependencias y el SBOM se agregan cuando existan los workflows reutilizables de U1 (NFR-U0-17); mientras tanto, queda un job `pip-audit` + `npm audit`.
  - **AUTONOMIA-01**: el workflow no tiene pasos `kubectl`, `helm` ni `terraform`; la verificación de pasos prohibidos de U1 lo cubrirá cuando exista.
  - **Aceptación**: `actionlint .github/workflows/contracts.yml`, `! grep -E "kubectl|helm (install|upgrade)|terraform apply" .github/workflows/contracts.yml`, `uv run pytest contracts/tests/unit/test_versioning.py` y `uv run python contracts/tools/traceability.py --section versioning` (encuentra BR-U0-90..93 en las pruebas).

### Bloque G — Documentación y artefactos de despliegue

- [ ] **Paso 22 — Documentación**
  - `contracts/README.md`: cómo un servicio usa `create_app`, `require`, `deps.call`, `check_preconditions`/`build_outcome`; política de versiones (BR-U0-90..93); cómo actualizar DIVIPOLA.
  - `CHANGELOG.md` de `contracts` con la versión inicial `0.1.0` y la etiqueta `contracts-v0.1.0`.
  - **Aceptación**: `test -s contracts/README.md && grep -q "contracts-v0.1.0" contracts/CHANGELOG.md`.

- [ ] **Paso 23 — Artefactos de despliegue: N/A**
  - U0 no se despliega. La etiqueta OCI `vectra.contracts.version` (NFR-U0-32) la aplican los charts de cada servicio y la verifica U1.
  - **Aceptación**: `test ! -d contracts/chart && test ! -f contracts/Dockerfile`.

- [ ] **Paso 24 — Cierre de la unidad**
  - Verificación final de cumplimiento (AUTONOMIA, SECURITY, PBT).
  - `aidlc-docs/construction/contracts/code/README.md` con el índice de los resúmenes.
  - **Aceptación**: `make -C contracts check`, que corre en orden los comandos de aceptación de los pasos 2–23 y termina con código 0.

---

## 3. Trazabilidad

| Historia | Aporte de U0 | Pasos |
|---|---|---|
| US-111 | Invariante en dos fases, `RecommendResult`, causas de fail-closed | 3, 4, 6, 7 |
| US-601 | Validación de JWT y JWKS | 10, 11 |
| US-602 | `require`, deny by default, registro de contratos, matriz rol × endpoint | 9, 10, 11, 12, 15 |
| US-604 | Logger con allowlist, trazas con allowlist, sin egress | 10, 11, 12 |
| US-611 | `Problem` genérico, 400/413/415/422 sin valores | 3, 10, 11 |

| Reglas | Aporte | Pasos | Chequeo de trazabilidad |
|---|---|---|---|
| BR-U0-01..43, 80..81, 95 | Lógica de negocio | 3–7 | Paso 8 (`--section logic`) |
| BR-U0-50..73 | Capa de API | 10–12 | Paso 13 (`--section api`) |
| BR-U0-90..93 | Versionado y fuente autoritativa | 1, 15, 21, 22 | Paso 21 (`--section versioning`) |
| Todas | — | — | Paso 20 (`--all`) |

| Propiedad | Paso |
|---|---|
| PBT-U0-01..06, 10..13 | 6 |
| PBT-U0-07..09 | 12 |
| PBT-10 (ejemplos) | 7, 11 |
| PBT TS (fast-check) | 17 |

## 4. Cumplimiento de extensiones (plan de tareas U0)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | Ninguna tarea aplica cambios a un clúster; Paso 21 lo verifica con `grep` |
| AUTONOMIA-02 | Cumple | Cada paso tiene un comando de aceptación |
| AUTONOMIA-03 | Cumple | `core:write-credit` sin titular (Paso 9) |
| AUTONOMIA-04 | Cumple | `model_frozen` no reintentable (Pasos 4 y 6) |
| AUTONOMIA-05 | Cumple | Allowlist de logs y spans; sin egress (Pasos 10–12) |
| AUTONOMIA-06 | Cumple | Invariante en tres capas (Pasos 4, 6, 7) |
| SECURITY-03/05/08/10/15 | Cumple | Pasos 3, 10, 11, 21 |
| PBT-01..10 | Cumple | Pasos 2, 6, 7, 12, 17, 20, 21 |
| RESILIENCY-10 | Cumple (alcance de U0) | `deps.call` con timeout obligatorio; JWKS con timeout (Paso 10) |
