# Requisitos no funcionales — U0 `contracts`

Decisiones del plan (`contracts-nfr-requirements-plan.md`, Q1–Q11 = A). U0 es un paquete
de librerías y especificaciones **sin runtime propio**: sus NFR son de corrección,
rendimiento del middleware, seguridad, mantenibilidad y calidad de pruebas. Cada requisito
tiene una verificación ejecutable (AUTONOMIA-02).

Los IDs `NFR-U0-xx` se referencian en NFR Design y en el plan de tareas.

---

## 1. Rendimiento (Q6=A; NFR-PER-01)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U0-01 | El pipeline común de `vectra_common` (telemetría → authz → validación → errores → log) agrega **p95 ≤ 5 ms y p99 ≤ 15 ms** por request, con la JWKS en cache y un payload de 32 KiB | `pytest contracts/tests/bench -m benchmark` (`pytest-benchmark`); CI falla si se supera el umbral |
| NFR-U0-02 | `check_preconditions` + `build_outcome` ≤ **1 ms p99** | Mismo benchmark, caso `outcome` |
| NFR-U0-03 | La derivación de features y etiquetas (`finance` + `labels`) ≤ **2 ms p99** por solicitud | Mismo benchmark, caso `derive` |
| NFR-U0-04 | Los benchmarks corren en un runner con la misma imagen base de los servicios; el resultado se publica como artefacto de CI | Workflow de CI de U0 (artefacto `benchmark.json`) |

## 2. Seguridad

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U0-10 | Validación de JWT con PyJWT: solo `RS256`/`ES256`; se rechazan `none` y `HS*`; se verifican `iss`, `aud`, `exp` y `nbf` con una tolerancia de reloj de 30 s | Q4, BR-U0-70, SECURITY-08 | Pruebas de ejemplo con tokens `alg=none`, `HS256` firmado con la clave pública, `aud` ajena y vencidos por 31 s → 401 |
| NFR-U0-11 | JWKS en cache por 10 min; ante un `kid` desconocido, un refresco con límite de 1 cada 30 s (evita amplificar ataques hacia Keycloak) | Q4 | Prueba con un servidor JWKS falso que cuenta las llamadas: 100 tokens con `kid` desconocido en 30 s → 1 refresco |
| NFR-U0-12 | **Fail-closed de identidad**: si la cache venció y Keycloak no responde, toda request autenticada recibe `dependency_unavailable` (503). Nunca se acepta un token sin verificar su firma | Q5, SECURITY-15, P3 | Prueba con el JWKS caído y la cache vencida → 503; con la cache vigente → 200 |
| NFR-U0-13 | Logs solo con las claves de la allowlist de `LogRecord` (structlog con un procesador final que descarta el resto), incluidos los logs de librerías de terceros redirigidos | Q11, BR-U0-50..53, NFR-SEC-03, AUTONOMIA-05 | PBT-U0-07, más una prueba que emite un log desde `httpx`/`uvicorn` con PII y verifica que no aparece |
| NFR-U0-14 | Deserialización **estricta**: Pydantic v2 en modo `strict` y `extra="forbid"` en todo tipo de entrada; `Decimal4` solo como cadena (BR-U0-15) | Q1, NFR-SEC-05 | PBT-U0-11, más pruebas con campos extra y `Decimal4` numérico → 422 |
| NFR-U0-15 | Un endpoint de la API sin `required_scopes` ni `required_roles` impide arrancar el servicio | BR-U0-71 | Prueba de arranque de una app FastAPI de ejemplo con un endpoint sin declarar → excepción en el startup |
| NFR-U0-16 | Ninguna dependencia de U0 hace llamadas salientes fuera del clúster; el exportador OTLP solo acepta destinos configurados por variable de entorno, sin valores por defecto externos | AUTONOMIA-05, F61 | Prueba que arranca el módulo `telemetry` sin configuración → no exporta; revisión de `uv.lock` por SDKs de terceros (lista de prohibidos en CI) |
| NFR-U0-17 | Dependencias con lockfile (`uv.lock`, `package-lock.json`), escaneo de vulnerabilidades y SBOM, usando los workflows reutilizables de U1 | NFR-SEC-10, SECURITY-10 | Job de CI `deps-scan` de U1 aplicado a `contracts/` sin hallazgos críticos o altos sin justificar |

## 3. Confiabilidad y datos

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U0-20 | La tabla DIVIPOLA (DANE) se empaqueta en `vectra_contracts` con fecha de corte, fuente y checksum SHA-256; si el checksum no coincide, la carga falla. **[VERIFICAR]** la fecha de corte vigente al construir | Q10, BR-U0-25, BR-U0-41 | Prueba que altera un byte del archivo → error al importar el módulo |
| NFR-U0-21 | Actualizar DIVIPOLA o la tabla de regiones sube la versión **menor**; quitar un código sube la **mayor** (endurece la validación, BR-U0-91) | Q10, BR-U0-91 | `oasdiff` no lo detecta (es un dato); lo verifica una prueba que compara el conjunto de códigos contra la versión publicada anterior |
| NFR-U0-22 | Las funciones de dominio de `vectra_contracts` son puras y deterministas: sin E/S, sin reloj implícito (`now` y `evaluated_at` son parámetros) ni aleatoriedad | BR-U0-01, BR-U0-40 | Regla de lint (import-linter) que prohíbe `datetime.now`, `random`, `os` y `httpx` en `vectra_contracts` |
| NFR-U0-23 | **Llamadas a dependencias** en `vectra_common.deps`: (a) `call` exige un timeout explícito, sin valor por defecto; (b) con `deadline=`, el timeout efectivo es `min(timeout, deadline − ahora)` y se propaga `x-vectra-deadline`. `vectra_common.deadline` descarta una cabecera mal formada; una en el pasado agota el presupuesto (504 inmediato); una en el futuro lejano se acepta pero **nunca extiende** el timeout propio de la llamada, porque rige el `min` (precisado el 2026-10-06); (c) circuit breaker por dependencia (cerrado, abierto y semiabierto con ventana deslizante; umbrales declarados por cada servicio): abierto → `DependencyUnavailable` de inmediato, **sin salir del proceso**; métrica `vectra_circuit_state{dependency}`; **solo cuentan como fallo los timeouts, los errores de conexión y los 5xx**: un 4xx es la respuesta de una dependencia sana y no cuenta, para que una solicitud defectuosa no abra el circuito de todas (precisado el 2026-10-06 por U8 NFR Requirements, NFR-U8-32); (d) un cliente por dependencia con límite de conexiones, cuya espera cuenta dentro del timeout; (e) ningún módulo llama a `httpx` fuera de `deps` (agregado el 2026-10-06: U7 centralizó el circuit breaker en `vectra_common.deps`); (f) el circuit breaker es obligatorio salvo en procesos batch (`process_kind="batch"`), que pueden usar `breaker="disabled"` (P-U0-07; precisado el 2026-10-10 por U9 NFR Design Q1); `process_kind` se declara **una vez** al iniciar el proceso: `create_app()` lo fija en `service`, y un proceso batch llama `vectra_common.process.init(kind="batch")` antes de crear clientes; crear un cliente sin proceso inicializado, o inicializarlo dos veces, falla (revisión del Infrastructure Design de U10, 2026-10-10); (g) `vectra_circuit_state{dependency}` vale 0 = cerrado, 1 = semiabierto, 2 = abierto (revisión del Infrastructure Design de U10, 2026-10-10); (h) un `x-vectra-deadline` vencido al llegar responde 504 `deadline_exceeded` (§6; revisión del Infrastructure Design de U10, 2026-10-10) | NFR-RES-11, RESILIENCY-10; U7 NFR Requirements Q4, U7 NFR Design Q1 y Q4 | `contracts/tests/unit/test_deps.py`: `call` sin timeout falla en el chequeo de tipos y en runtime; el timeout efectivo nunca supera el presupuesto restante; la cabecera se propaga; 20 respuestas 4xx no abren el circuito (precisado el 2026-10-06 por U8 NFR Requirements); con el circuito abierto, un servidor doble cuenta **0** llamadas y la respuesta llega en < 1 ms; un pool agotado termina en timeout. `test_deadline.py`: cabecera mal formada, en el pasado o en el futuro. **PBT-U0-14 (stateful, PBT-06)**: para toda secuencia de éxitos, fallos y avance del reloj, el estado del breaker coincide con un modelo de referencia y en estado abierto nunca se emite una llamada. Regla de import-linter: solo `vectra_common.deps` importa `httpx`; (f) `breaker="disabled"` con `process_kind="batch"` → cliente sin breaker y con timeout obligatorio; en un servicio HTTP → error al crear el cliente (revisión del Infrastructure Design de U9, 2026-10-10) |

## 4. Mantenibilidad (Q1, Q2, Q3, Q8, Q9; NFR-MNT-01)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U0-30 | **Code-first**: los modelos Pydantic de `vectra_contracts` son la fuente. Las specs de `contracts/openapi/` se generan y se versionan. CI falla si la spec generada difiere de la versionada | `make -C contracts openapi && git diff --exit-code contracts/openapi/` |
| NFR-U0-31 | Python 3.12 y un workspace `uv` con un `uv.lock` único en la raíz del monorepo; `vectra_contracts` y `vectra_common` como dependencias de ruta | `uv lock --check`; `uv sync --frozen` en CI |
| NFR-U0-32 | Los paquetes **no** se publican en ningún índice; se consumen solo por ruta del workspace. La versión SemVer de U0 se graba como etiqueta OCI `vectra.contracts.version` en cada imagen de servicio | `uv tree` sin índices de terceros para paquetes `vectra_*`; prueba del chart que verifica la etiqueta (U1) |
| NFR-U0-33 | Compatibilidad de API con `oasdiff` contra la spec de la última etiqueta `contracts-vX.Y.Z`; un cambio incompatible sin subir la versión mayor hace fallar el build | `oasdiff breaking --fail-on ERR <base> <head>` en CI |
| NFR-U0-34 | El cliente TS se genera con `openapi-typescript` (solo tipos) y se consume con `openapi-fetch`. `Decimal4`/`Decimal` son `string` en TS y se manejan con `decimal.js`; está prohibido convertirlos a `number` | `npm run -w contracts/ts typecheck`, más una regla de ESLint que prohíbe `Number(`/`parseFloat` sobre tipos `Decimal*` |
| NFR-U0-35 | Cada `BR-U0-xx` está referenciada por al menos una prueba (trazabilidad regla → prueba) | Script de CI que busca cada ID de `business-rules.md` en `contracts/tests/` |

## 5. Calidad de pruebas (Q7; NFR-TST-01..05)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U0-40 | Cobertura de **ramas ≥ 95 %** en `vectra_contracts` y `vectra_common`; **100 %** en los módulos `outcome`, `authz`, `logging`, `deps` y `deadline` (`deps` y `deadline` agregados el 2026-10-06) | `pytest --cov --cov-branch --cov-fail-under=95` y un umbral por módulo con `coverage report --include` |
| NFR-U0-41 | **Mutation testing** con `mutmut` en `outcome`, `authz`, `deps` (máquina de estados del breaker y aritmética del presupuesto) y `deadline` (lectura de la cabecera) (`deps` y `deadline` agregados el 2026-10-06): 0 mutantes sobrevivientes sin justificar (las justificaciones se versionan en `contracts/tests/mutmut-allowlist.txt`) | `mutmut run --paths-to-mutate …` en el job nocturno; el PR que toca esos módulos lo ejecuta también |
| NFR-U0-42 | Hypothesis con perfil `ci` (500 ejemplos por propiedad, `print_blob=True`, semilla impresa) en cada PR y perfil `nightly` (10 000 ejemplos) | `HYPOTHESIS_PROFILE=ci pytest`; job nocturno con `HYPOTHESIS_PROFILE=nightly` |
| NFR-U0-43 | Reproducibilidad: toda falla de PBT imprime la semilla y el ejemplo reducido; la base de ejemplos de Hypothesis se guarda como artefacto de CI | Artefacto `.hypothesis/` en el job; PBT-08 |
| NFR-U0-44 | Generadores de dominio centralizados en `contracts/tests/strategies/` (solicitud colombiana realista, `FeatureVector`, `MonitoringLabels`, `Principal`, `Explanation`, errores del explicador) y reutilizables por otras unidades | NFR-TST-03; las demás unidades los importan, verificado por import-linter |
| NFR-U0-45 | En TS, fast-check con Vitest para el round-trip de los tipos del cliente (`Decimal4` como cadena, uniones por `kind`) | `npm run -w contracts/ts test` |
| NFR-U0-46 | Las pruebas de ejemplo de PBT-10 (business-logic-model §3) son obligatorias además de las propiedades | Lista de pruebas con nombre fijo, verificada por el script de NFR-U0-35 |
| NFR-U0-47 | **Frases prohibidas** (BR-U0-94): `forbidden_phrases.py` corre en CI sobre los archivos que cada unidad declara (U4, U7, U9, U10) y falla con archivo, línea y frase; el YAML tiene `CODEOWNERS` de cumplimiento en el monorepo (BR-U0-94; revisión del Infrastructure Design de U10, 2026-10-10) | `contracts/tests/unit/test_forbidden_phrases.py` (casos del Paso 3 del plan) |
| NFR-U0-48 | **`vectra_common.ops_server`** (NFR Requirements de U11, 2026-10-10, Q7): servidor de 8081 con `/metrics`, `/healthz` y `/readyz` para un proceso `service` que no usa `create_app` (no tiene rutas de negocio); usa el mismo registro de métricas que `create_app` y `process.init(kind="service")`; recibe un **predicado de readiness** opcional (`readiness: Callable[[], bool]`), que por omisión es «solo el proceso», como `create_app`; `/healthz` nunca depende de él (revisión del Infrastructure Design de U11, 2026-10-10) | `contracts/tests/unit/test_ops_server.py`: las tres rutas responden; ninguna otra ruta existe (404); el puerto es 8081; con un predicado que devuelve `false`, `/readyz` → 503 y `/healthz` → 200; con uno que lanza una excepción, `/readyz` → 503 |

## 6. Disponibilidad, escalabilidad y usabilidad

| Aspecto | Estado | Justificación |
|---|---|---|
| Disponibilidad / DR | N/A en U0 | No hay proceso desplegado. La disponibilidad del middleware es la del servicio que lo usa (U3, U4, U7, U8...) |
| Escalabilidad | N/A en U0 | Las funciones son puras y sin estado compartido; escalan con el servicio. Hay dos estados por proceso: el cache de JWKS (NFR-U0-11) y el estado del circuit breaker de cada dependencia (NFR-U0-23). Cada réplica abre su circuito por su cuenta, sin coordinación entre réplicas (precisado el 2026-10-06) |
| Usabilidad | Parcial | Mensajes de `Problem.title` genéricos en español (i18n). La usabilidad de la SPA es de U10 |

## 7. Cumplimiento de extensiones (NFR Requirements U0)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-03 | Cumple | NFR-U0-13 |
| SECURITY-05 | Cumple | NFR-U0-14 |
| SECURITY-08 | Cumple | NFR-U0-10, 11, 15 |
| SECURITY-10 | Cumple | NFR-U0-17, 31 |
| SECURITY-15 | Cumple | NFR-U0-12 |
| SECURITY-01/02/04/06/07/09/11/12/13/14 | N/A en U0 | Infraestructura, borde e identidad (U1, U2); SECURITY-14 ya cubierto en el FD (BR-U0-73) |
| RESILIENCY-10 | Cumple (alcance de la librería) | NFR-U0-23: timeouts obligatorios, presupuesto propagado, un cliente por dependencia y circuit breaker en `vectra_common.deps`. Cada servicio fija sus umbrales y los usa (U7 NFR-U7-10/11/43; U8). Antes esta fila decía «N/A en U0; se aplica en los servicios» (agregado el 2026-10-06: U7 centralizó el circuit breaker en `vectra_common.deps`) |
| RESILIENCY-otras | N/A en U0 | Sin runtime propio: disponibilidad, escalado, health checks y DR son de cada servicio |
| PBT-06 | Cumple | PBT-U0-14, propiedad stateful del circuit breaker (NFR-U0-23) (agregado el 2026-10-06: U7 centralizó el circuit breaker en `vectra_common.deps`) |
| PBT-09 | Cumple | Hypothesis y fast-check (tech-stack-decisions §3) |
| PBT-07 / 08 | Cumple | NFR-U0-42, 43, 44 |
| AUTONOMIA-02 | Cumple | Cada requisito tiene un comando o prueba de verificación |
| AUTONOMIA-05 | Cumple | NFR-U0-13, 16, 20 (sin egress en runtime) |
| AUTONOMIA-06 | Cumple | NFR-U0-02, 22, 40, 41 (pureza, 100 % de ramas y mutación en `outcome` y en `deps`, cuyo breaker sostiene el fail-closed de todos los servicios) |
