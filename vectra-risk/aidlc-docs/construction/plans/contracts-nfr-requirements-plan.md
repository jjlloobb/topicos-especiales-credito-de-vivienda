# Plan de NFR Requirements — U0 `contracts`

**Alcance:** U0 no se despliega. Sus requisitos no funcionales son los de un **paquete de
librerías y especificaciones** que usan todos los servicios: corrección, rendimiento del
middleware, seguridad de autenticación, compatibilidad de contratos y calidad de pruebas.
La disponibilidad, la escalabilidad y la recuperación son de cada servicio (U1–U11), no
de U0.

**Ya decidido en INCEPTION** (no se vuelve a preguntar):
- servicios en Python con FastAPI y SPA en React con TypeScript;
- monorepo con `contracts/` (openapi, `vectra_contracts`, `vectra_common`, cliente TS);
- PBT con Hypothesis (Python) y fast-check (TypeScript) (NFR-TST-01);
- OpenTelemetry con exportador solo dentro del clúster;
- una sola versión SemVer para todo el paquete y actualización de consumidores en el mismo PR (Q7 del FD).

---

## Parte A — Preguntas

Escribe la letra de tu elección después de cada `[Answer]:`.

## Question 1 — Fuente de verdad de los contratos (Tech Stack)
U0 tiene tipos con reglas que OpenAPI no expresa por sí solo: el invariante de dos fases,
`Decimal4` como cadena y uniones discriminadas.

A) **Code-first**: los modelos Pydantic v2 de `vectra_contracts` son la fuente. Las specs OpenAPI se **generan** desde ellos y se versionan en `contracts/openapi/`. CI falla si la spec generada difiere de la versionada. El cliente TS se genera desde la spec (recomendado: una sola definición y las validaciones viven junto al tipo)

B) **Spec-first**: las specs OpenAPI se escriben a mano y los modelos Pydantic se generan desde ellas (p. ej. `datamodel-code-generator`). La lógica de dominio (`check_preconditions`, `finance`, `labels`) se escribe aparte, sobre los modelos generados

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Versión de Python y gestión del workspace (Tech Stack)

A) **Python 3.12** y **uv** con workspace del monorepo: un `uv.lock` único, y `vectra_contracts` y `vectra_common` como dependencias de ruta de cada servicio (recomendado: lockfile único, resolución rápida y reproducible, cumple NFR-SEC-10)

B) Python 3.11 y Poetry, con un lockfile por servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Distribución de los paquetes (Maintainability)

A) **Solo dentro del monorepo**: los servicios consumen `vectra_contracts`, `vectra_common` y el cliente TS por ruta del workspace, sin publicarlos en ningún índice. La versión SemVer existe para el control de compatibilidad (BR-U0-92) y la trazabilidad en las imágenes (recomendado: coherente con Q7 del FD; sin dependencia de un índice externo)

B) Publicarlos en un índice interno de paquetes del banco (p. ej. Artifactory o Nexus) y consumirlos por versión

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Validación de JWT: librería y JWKS (Security)

A) **PyJWT** con `PyJWKClient`.
   - Las JWKS de Keycloak se cachean por 10 minutos.
   - Si llega un `kid` desconocido, se refresca una sola vez, con un límite de 1 refresco cada 30 s.
   - Algoritmos permitidos: solo `RS256`/`ES256`. Se rechazan `none` y `HS*`.
   - Tolerancia de reloj: 30 s.

   (Recomendado: librería mínima, una superficie de ataque pequeña y una lista de algoritmos explícita)

B) **Authlib / joserfc**, con la misma política de cache y de algoritmos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Keycloak no disponible y la cache de JWKS vencida (Security / Reliability)

A) **Fail-closed con 503**. Si la JWKS no se puede obtener y la cache venció, toda request autenticada responde `dependency_unavailable` (503). Nunca se acepta un token sin verificar su firma. Mientras la cache esté vigente, se sigue validando con ella (recomendado: coherente con SECURITY-15 y P3)

B) Extender la cache vencida hasta 1 hora mientras Keycloak no responde, y fallar después

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Presupuesto de latencia del middleware común (Performance)
El pipeline de `vectra_common` (telemetría → authz → validación → errores → log) se
ejecuta en cada request de todos los servicios, incluida la ruta de recomendación.

A) **p95 ≤ 5 ms y p99 ≤ 15 ms** de sobrecosto por request con la JWKS en cache y un payload de 32 KiB. `check_preconditions` + `build_outcome` ≤ 1 ms p99. Se mide con un benchmark en CI (`pytest-benchmark`) que falla si se supera el umbral (recomendado: deja casi todo el presupuesto de la ruta de recomendación a KServe y al explicador)

B) Sin presupuesto propio en U0. La latencia se mide solo de punta a punta en cada servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Umbral de calidad de pruebas de U0 (Maintainability / Testing)
Un error en U0 se propaga a todos los servicios.

A) **Cobertura de ramas ≥ 95 %** en `vectra_contracts` y `vectra_common`, y **100 %** en `outcome`, `authz` y `logging`. **Mutation testing** (`mutmut`) en `outcome` y `authz`, con 0 mutantes sobrevivientes no justificados. Hypothesis con perfil `ci` (500 ejemplos por propiedad, semilla impresa) en cada PR y perfil `nightly` (10 000 ejemplos) (recomendado)

B) Cobertura de líneas ≥ 85 % y Hypothesis con la configuración por defecto (100 ejemplos)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Generador del cliente TypeScript y decimales en la SPA (Tech Stack / Usability)

A) **`openapi-typescript` + `openapi-fetch`**: solo tipos y un cliente delgado, sin código de runtime generado. `Decimal4` y `Decimal` llegan como `string` y se muestran con `decimal.js`. Nunca se convierten a `number` (recomendado: respeta BR-U0-15 y genera un bundle pequeño)

B) `openapi-generator` (typescript-fetch), con clases de modelo generadas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Herramienta de compatibilidad de OpenAPI (Maintainability, BR-U0-92)

A) **`oasdiff`** en CI contra la spec de la última versión etiquetada. Sus reglas de cambio incompatible exigen subir la versión mayor (recomendado: maduro y detecta cambios en requests y responses)

B) Comparación propia con un script sobre las specs JSON

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Tabla DANE de departamentos y municipios (Reliability / Data)
BR-U0-25 valida `municipality_code` contra su departamento, y la región sale de esa tabla
(BR-U0-41).

A) **Snapshot versionado de DIVIPOLA** (DANE) empaquetado en `vectra_contracts` como dato, con fecha de corte, fuente y checksum verificado al cargar. Actualizarlo es un cambio de versión menor. **[VERIFICAR]** la fecha de corte vigente al construir (recomendado: no hay egress en runtime, AUTONOMIA-05)

B) Validar solo el formato del código (5 dígitos que empiezan con el código del departamento), sin la tabla de municipios

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Librería de logging estructurado (Tech Stack, BR-U0-50..53)

A) **`structlog`** con un procesador final de allowlist que descarta toda clave fuera de `LogRecord`, salida JSON a stdout y el agente de logs del clúster como único destino. El `logging` estándar de las librerías de terceros se redirige al mismo pipeline, así que también pasa por la allowlist (recomendado)

B) `logging` estándar con un `Formatter` JSON propio que aplica la allowlist

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U0 y los NFR de requirements (NFR-SEC-03/05/08/09/10/14/15, NFR-RES-06/11, NFR-TST-01..05, NFR-PER-01, NFR-MNT-01)
- [x] 2. Recoger y validar las respuestas (sin ambigüedades)
- [x] 3. Generar `construction/contracts/nfr-requirements/nfr-requirements.md`
  - [x] 3.1 Rendimiento (presupuesto del middleware y de las fábricas)
  - [x] 3.2 Seguridad (JWT/JWKS, logs sin PII, errores, deserialización estricta)
  - [x] 3.3 Confiabilidad (fail-closed ante dependencias de identidad; datos DANE)
  - [x] 3.4 Mantenibilidad (fuente de verdad, compatibilidad, distribución)
  - [x] 3.5 Calidad de pruebas (cobertura, mutación, perfiles PBT, semillas)
  - [x] 3.6 Disponibilidad y escalabilidad: N/A justificado (U0 no tiene runtime propio)
- [x] 4. Generar `construction/contracts/nfr-requirements/tech-stack-decisions.md` (incluye PBT-09)
- [x] 5. Verificar el cumplimiento de las extensiones (SECURITY, RESILIENCY, PBT, AUTONOMIA)
