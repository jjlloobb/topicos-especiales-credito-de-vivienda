# Conformidad de U0 con su diseño (2026-11-02)

Informe del revisor de conformidad (`opus`, solo lectura), guardado tal cual por el orquestador. El orquestador reprodujo R1 y N1. Pedido del usuario: «revisa la implementacion hasta ahora este de acuerdo al diseno».

---

## Revisión de conformidad con el diseño: U0 `contracts` (rama `main`, 7bfb7ec)

Revisé solo lectura. Exporté `main` con `git archive` a `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/60e58df0-e00f-424b-9e70-38ce42865a5f/scratchpad/design-u0/repo` e inicialicé ahí un git propio para que funcione el `git diff --exit-code` del Makefile. `uv sync` y `npm ci` corrieron sin red. Entre `main` y la rama de trabajo solo cambian `vectra-risk/pyproject.toml` y `uv.lock`, nada en `contracts/`.

### Resumen
- Las 24 aceptaciones del plan pasan hoy, salvo `actionlint`, que no está instalado. `make -C contracts check` termina con código 0.
- Hay un hallazgo ROJO, así que **U0 queda NO-CONFORME**: `Recommendation.outcome` y `reasons` no son enumerados cerrados y el contrato acepta valores inventados.
- Hay un hallazgo NARANJA: un import circular hace fallar `import vectra_contracts.outcome` cuando es el primer import del proceso.
- Los demás hallazgos son menores (AMARILLO).

### Tabla de pasos (todo verificado por mí, salvo donde se indica)

| Paso | Artefactos | Aceptación corrida | Resultado |
|---|---|---|---|
| 1 | pyproject/uv.lock/package.json/Makefile | `uv lock --check`, `uv sync --frozen`, `import vectra_contracts, vectra_common` | OK |
| 2 | `.importlinter`, `conftest.py` | `lint-imports` (3 kept, 0 broken); `--collect-only` imprime `hypothesis profile: ci` | OK (ver A1) |
| 3 | catalog, models, forbidden-phrases (yaml, tool), CODEOWNERS | mypy --strict (38 archivos, sin errores); test_models + business_time + fail_closed_payload + forbidden_phrases: 72 passed; la línea de CODEOWNERS existe | Pasa, pero ver R1 |
| 4 | outcome/, _internal | test_outcome: 16 passed | Pasa, pero ver N1 |
| 5 | finance, labels, dictionary, canonical, validation, data/ | 6 archivos: 41 passed | OK (ver A3) |
| 6 | tests/strategies, property | `-m "not common"` perfil ci: 15 passed | OK |
| 7 | examples logic | `-m logic`: 47 passed | OK |
| 8 | business-logic-summary.md | `traceability --section logic`: 40 reglas | OK (ver A5) |
| 9 | routes/ | test_routes: 15 passed | OK |
| 10 | vectra_common/* | los 10 archivos: 98 passed; test_deps_stateful (ci): 1 passed | OK |
| 11 | examples api | `-m api`: 17 passed | OK |
| 12 | property common | `-m common` (ci): 5 passed | OK |
| 13 | api-layer-summary.md | `--section api`: 11 reglas | OK |
| 14 | sin `repository/` | `test ! -d` | OK |
| 15 | openapi/*.yaml, scopes-catalog, matriz | codegen + `git diff --exit-code` sin diff (dentro de make check) | OK |
| 16 | contracts/ts | typecheck + lint | OK |
| 17 | test/client.test.ts | vitest: 8 passed | OK |
| 18 | contracts-and-client-summary.md | `test -s` | OK |
| 19 | bench + bench_gate | pipeline p95 1,50 ms / p99 1,54 ms; outcome p99 0,047 ms; derive p99 0,58 ms, todo bajo umbral | OK (ver A2) |
| 20 | cobertura, mutación, trazabilidad | cobertura de ramas 97,78 % (fail-under 95); coverage_gate al 100 % en outcome, authz, deps, deadline y logging; `mutation.py`: 645 killed, 7 survived, todos en la allowlist; `--all`: 56 reglas | OK |
| 21 | `.github/workflows/contracts.yml`, test_versioning | test_versioning: 4 passed; `--section versioning`: 4; grep de kubectl/helm/terraform sin coincidencias | OK, salvo `actionlint`, **no corrido** |
| 22 | README, CHANGELOG | `test -s` + grep `contracts-v0.1.0` | OK |
| 23 | sin chart ni Dockerfile | `test !` | OK |
| 24 | `make -C contracts check` | exit=0 (455 passed) | OK (ver A4) |

### Hallazgos

**R1 (ROJO): `Recommendation.outcome` es `str` y `reasons` es `list[str]`; el diseño pide enumerados cerrados.**
- Archivo: `vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py` (clase `Recommendation`).
- Lo que pide el diseño:
  - domain-entities §3.3: `outcome: favorable | desfavorable | revision_requerida` y `reasons: list[ReasonCode]`.
  - BR-U0-20: enumeraciones válidas.
  - NFR-U0-14: deserialización estricta.
  - P-U0-03, capa 1: ninguna `Recommendation` inconsistente circula, «aunque venga por la red».
  - Lo incumple un tipo del Paso 3, que está marcado `[x]`.
- Evidencia: tomé una `Recommendation` válida, le puse `outcome="aprobado_a_ciegas"` y `reasons=["cualquier_cosa"]`, y `RecommendResult.from_wire(...)` la aceptó: imprime `ACEPTADO: aprobado_a_ciegas ['cualquier_cosa']`.
- El defecto pasa a la spec generada: `contracts/openapi/scoring-service.yaml` líneas 398-408 tienen `outcome: type: string` y `reasons: items: type: string`, sin `enum`. Por eso el cliente TS tampoco restringe el campo.
- `PolicyResult` sí usa `Outcome` y `list[ReasonCode]`. La pérdida ocurre solo en `Recommendation`.

**N1 (NARANJA): import circular en `vectra_contracts.outcome` y `vectra_contracts.dictionary`.**
- La cadena es `outcome` → `dictionary` → `models/__init__` → `models/api.py:29` (`from vectra_contracts.outcome import Recommendation`) → `outcome`.
- Evidencia: con `python -I -c "import vectra_contracts.outcome"` en un intérprete limpio sale `ImportError: cannot import name 'Recommendation' from partially initialized module 'vectra_contracts.outcome'`. Lo mismo pasa con `vectra_contracts.dictionary`: no puede importar `covers`.
- Los demás módulos importan bien. La suite pasa solo porque otro import carga antes `vectra_contracts.models`.
- Impacto: el plan (Paso 4 y README) indica a los servicios usar `check_preconditions`/`build_outcome`. Un servicio cuyo primer import sea `vectra_contracts.outcome` no arranca. Ninguna prueba importa los módulos de forma aislada.

**A1 (AMARILLO): `datetime.now` no tiene una regla de lint que lo prohíba en `vectra_contracts`.**
- Referencia: NFR-U0-22 y Paso 2 («import-linter que prohíbe `datetime.now`»).
- `.importlinter` prohíbe `vectra_common`, `fastapi`, `httpx`, `os` y `random`, pero no `datetime.now`; import-linter no puede expresar esa regla. Ruff tampoco selecciona DTZ: `select = ["E","F","I","B","UP","S","BLE","T20"]`.
- Hoy se cumple de hecho: `grep` de `datetime.now|.now(|utcnow` en `vectra_contracts/src` no encuentra nada. La regla no está automatizada.

**A2 (AMARILLO): el benchmark `derive` mide con un `FeatureSpec` vacío.**
- Archivo: `contracts/tests/bench/test_bench.py`, con `FeatureSpec(model_version_id="m", features=[])`.
- NFR-U0-03 exige ≤ 2 ms p99 para la derivación de features. Con la spec vacía no se recorre ninguna feature, así que el umbral se verifica en un caso que no representa la carga real.

**A3 (AMARILLO): falta la prueba de NFR-U0-21.**
- NFR-U0-21, citado en el Paso 5, pide comparar el conjunto de códigos DIVIPOLA contra la versión publicada anterior.
- `grep NFR-U0-21` en `contracts/tests` no encuentra nada. `test_data_integrity.py` solo tiene `test_tables_loaded` y `test_one_altered_byte_fails_on_import`.
- Es atenuante que todavía no exista la etiqueta `contracts-v*` contra la cual comparar.

**A4 (AMARILLO): `make check` no corre todas las aceptaciones de los pasos 2–23, aunque el Paso 24 dice que sí.**
- Faltan en el Makefile:
  - `actionlint` y el grep del Paso 21;
  - `test_versioning` como paso propio (sí corre dentro de la suite);
  - la mutación del Paso 20 (corre en CI, no en `check`);
  - `traceability --section` para logic, api y versioning (solo corre `--all`);
  - `test -s` del README, del CHANGELOG y del resumen del Paso 18.
- Además, los comandos de los Pasos 3, 5 y 10 están escritos con nombres de archivo sueltos (`test_business_time.py`) y no corren tal cual. Lo probé: `uv run pytest contracts/tests/unit/test_models.py test_business_time.py` da `no tests ran`. Yo los corrí con rutas completas.

**A5 (AMARILLO): la trazabilidad de NFR-U0-35 solo verifica que el texto aparezca.**
- `tools/traceability.py` busca el texto `BR-U0-NN` o `br_u0_NN` en cualquier `.py` de `tests/`, y un comentario basta.
- Además, `br_u0_NN_MM` cuenta solo los extremos del rango. Por ejemplo, BR-U0-27 solo se traza por `test_br_u0_26_27_amounts`; esa prueba existe y es pertinente.
- Muestreé las reglas de mayor riesgo y sí tienen pruebas reales: 01–08, 37, 38, 50–53, 60–62, 70–73, 80–81 y 90–93. Por eso es menor.

**A6 (AMARILLO): `vectra_common/decimal_ctx.py` es solo un reexport con 0 % de cobertura.**
- Nada lo importa, salvo la lista de `mutation.py`. Es inocuo y el plan lo nombra en la estructura de destino.

### Conforme (verificado por mí)
- **Tabla BR-U0-02/03/04 en `_first_cause`:** coincide fila por fila en orden y semántica, incluidas la discrepancia de versión pedida (S2, U8 Q1), la ausencia válida tras una causa anterior y `retryable=false` solo para `model_frozen`.
- **Token privado:** `Recommendation(...)`, `Ready(...)`, `model_construct` y `model_validate` sin token lanzan `ContractViolation`.
- **Catálogos contra el diseño:**
  - `FailClosedCause`: 10 valores en el orden de BR-U0-02.
  - `ProblemReason`: 7. `CreditStatus`: 8, con `no_integrado`.
  - `ProblemCode`: incluye `deadline_exceeded`.
  - `Scope`: los 18 de §7.2, con `core:read-credit`/`core:write-credit`. `Role`: 4.
  - `FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"]` es el esperado.
  - `LogEvent`: los 10 de §8.1. `LOG_RECORD_FIELDS`: igual a §8, más `exception_type`, desvío documentado.
- **Frases prohibidas:** el YAML de BR-U0-94 trae exactamente las 17 frases del diseño.
- **Autorización:** `authz.is_authorized` sigue BR-U0-71, con `any_scopes` documentado como desvío. `mfa_satisfied` sigue BR-U0-72: `acr=="mfa"` y edad ≤ 900 s.
- **Autenticación:** `authn` acepta solo RS256/ES256, usa leeway 30 s y exige `exp`, `iss`, `aud` y `sub` (NFR-U0-10).
- **Logs:** `logging.allowlist_filter` descarta claves fuera de la allowlist, cuenta los descartes y tiene modo strict (P-U0-04).
- **CI** (`contracts.yml`) incluye:
  - los pasos que pide el Paso 21;
  - `oasdiff` omitido si no hay etiqueta;
  - el artefacto `.hypothesis/` y `benchmark.json`;
  - el job nocturno;
  - mutación en cada PR.

### Líneas de hallazgo
ROJO|vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/outcome/__init__.py|domain-entities §3.3, BR-U0-20, NFR-U0-14, P-U0-03 capa 1 (Paso 3)|Recommendation.outcome es str y reasons es list[str]; from_wire acepta outcome/reasons fuera del catálogo y la spec de scoring sale sin enum
NARANJA|vectra-risk/contracts/python/vectra_contracts/src/vectra_contracts/models/api.py|P-U0-03, plan Paso 4 y README (uso de check_preconditions/build_outcome)|Import circular outcome→dictionary→models→models.api→outcome: `import vectra_contracts.outcome` como primer import falla con ImportError
AMARILLO|vectra-risk/contracts/.importlinter|NFR-U0-22, plan Paso 2|datetime.now no tiene regla de lint que lo prohíba (import-linter no puede; ruff sin DTZ); hoy no hay usos
AMARILLO|vectra-risk/contracts/tests/bench/test_bench.py|NFR-U0-03, P-U0-09|El benchmark derive usa un FeatureSpec vacío y no mide la derivación real
AMARILLO|vectra-risk/contracts/tests/unit/test_data_integrity.py|NFR-U0-21 (plan Paso 5)|Falta la prueba que compara los códigos DIVIPOLA contra la versión publicada anterior
AMARILLO|vectra-risk/contracts/Makefile|plan Paso 24 (y comandos de los Pasos 3, 5 y 10)|make check no corre todas las aceptaciones de los pasos 2–23; los comandos del plan con nombres de archivo sueltos no corren tal cual
AMARILLO|vectra-risk/contracts/tools/traceability.py|NFR-U0-35|La trazabilidad solo busca el texto (un comentario basta; los rangos cuentan los extremos)
AMARILLO|vectra-risk/contracts/python/vectra_common/src/vectra_common/decimal_ctx.py|P-U0-10, estructura del plan|Reexport sin uso con 0 % de cobertura

CONFORMIDAD U0: NO-CONFORME
