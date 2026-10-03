# Plan de NFR Design — U0 `contracts`

**Alcance:** convertir NFR-U0-01..46 en patrones y componentes lógicos de
`vectra_contracts`, `vectra_common` y el cliente TS. U0 no tiene runtime propio, así que
los patrones son de **librería**: cómo se componen el middleware, la autorización, el cache
de JWKS, la protección del invariante, el logging, los errores y la generación de specs.

**Categorías obligatorias y su aplicabilidad:**

| Categoría | Aplica a U0 | Preguntas |
|---|---|---|
| Resilience Patterns | Sí, a la dependencia de Keycloak (JWKS) y a cómo se prueba la resiliencia del proyecto | Q3, Q10 |
| Scalability Patterns | **N/A**: funciones puras y sin estado compartido; el único estado es el cache de JWKS por proceso (Q3) | — |
| Performance Patterns | Sí, por el presupuesto del middleware (NFR-U0-01..03) | Q1, Q8 |
| Security Patterns | Sí: autorización, invariante, logs, errores | Q2, Q4, Q5, Q6 |
| Logical Components | Sí: fábrica de app, registro de contratos de rutas, cache de JWKS | Q1, Q3, Q7 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Composición del pipeline común (Logical Components / Performance)

A) **Fábrica única** `vectra_common.create_app(service_name, contract)` que monta el pipeline ASGI en el orden fijo de business-logic-model §2.1 (telemetría → authz → validación → errores → log de acceso). Ningún servicio arma su propio stack. Una prueba de U0 verifica el orden de los middlewares (recomendado: el orden es parte del control de seguridad, y un solo lugar lo hace cumplir)

B) Middlewares independientes que cada servicio compone, con una guía de orden documentada

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Declaración de la autorización por ruta (Security)

A) **Dependencia de FastAPI** `Security(require(scopes=…, roles=…, mfa=…))` en cada ruta. Al arrancar, `create_app` recorre las rutas del puerto 8080 y falla si alguna no tiene el marcador `require` (NFR-U0-15). El catálogo de scopes de domain-entities §7.2 es un `Enum`: un scope inexistente no compila (recomendado)

B) Un decorador `@authorize(...)` sobre cada handler, con la misma verificación al arrancar

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Cache de JWKS y llamada a Keycloak (Resilience / Logical Components)

A) **Cache en memoria por proceso** con *single-flight*: un solo refresco concurrente (lock de asyncio) aunque lleguen muchas requests a la vez. Timeout de 2 s (conexión y total) y un solo intento por refresco. El límite de 1 refresco cada 30 s (NFR-U0-11) actúa como *circuit breaker* natural. Sin cache compartido (Redis), así que no hay infraestructura nueva. Métrica `vectra_jwks_refresh_total{result}` (recomendado)

B) Cache compartido en Redis entre réplicas, con refresco por un proceso aparte

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Cómo se impide saltarse la fábrica de `Recommendation` (Security, AUTONOMIA-06)
case-service tiene que **deserializar** la `Recommendation` que le responde scoring, así
que el tipo no puede ser imposible de construir fuera de `build_outcome`.

A) Tres capas:
   1. **Invariante estructural** en un `model_validator` de `Recommendation`, que se aplica a toda instancia, también al deserializar: versiones de modelo iguales en la recomendación, la explicación y el diccionario; `factuality_check == "passed"`; `registry_entry_id` no vacío; `score`/`confidence` en [0, 1].
   2. **Construcción en proceso** solo con un token privado del módulo `outcome`. `Recommendation(...)` y `Ready(...)` directos fallan; la deserialización usa `RecommendResult.from_wire()`.
   3. **import-linter** prohíbe importar `vectra_contracts.outcome._internal` fuera del módulo.

   Una prueba verifica que construir directamente falla (recomendado)

B) Solo el `model_validator` estructural (capa 1)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Claves que la allowlist descarta en los logs (Security, NFR-U0-13)

A) Se descartan **y se cuentan**: métrica `vectra_log_fields_dropped_total{service, event}`, sin el nombre ni el valor del campo, más una alerta si sube en producción. En desarrollo y CI, un modo `strict` hace **fallar la prueba** cuando se intenta registrar una clave fuera de la allowlist (recomendado: detecta temprano los intentos de registrar PII)

B) Se descartan en silencio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Traducción de excepciones a `Problem` (Security, SECURITY-15)

A) **Jerarquía cerrada** `VectraError` con un `code` del catálogo (p. ej. `ConflictState`, `NotFound`, `DependencyUnavailable`). El handler global traduce solo esas excepciones; cualquier otra se convierte en `internal_error`. Las excepciones de dependencias (`httpx.TimeoutException`, errores de conexión) se envuelven en `DependencyUnavailable` en el punto de llamada, nunca en el handler (recomendado: el handler no adivina)

B) El handler global mapea tipos de excepción de terceros a códigos con una tabla

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Contratos de rutas y generación de specs (Logical Components, NFR-U0-30)

A) **Registro de contratos en `vectra_contracts`**: por servicio, cada ruta se declara como dato (método, path, modelo de request y de response, scopes, roles, MFA). De ahí salen:
   - las specs OpenAPI;
   - el catálogo de scopes que consume U2;
   - la tabla rol × endpoint de US-602.

   Cada servicio **vincula** sus handlers a ese registro, y `create_app` falla si falta una ruta o si sobra una (recomendado: U0 es la única fuente y los servicios no pueden desviarse)

B) Las specs se generan desde la app FastAPI real de cada servicio y se copian a `contracts/openapi/`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Muestreo de trazas (Performance / Observability)
El volumen esperado de un banco mediano es bajo (cientos a pocos miles de solicitudes al día).

A) **Parent-based con 100 %** por defecto, configurable por variable de entorno. Los spans no llevan atributos de PII: un procesador de spans aplica la misma allowlist que los logs (recomendado: con el volumen bajo, la trazabilidad completa ayuda al expediente y a los incidentes)

B) Muestreo del 10 % y siempre los errores (tail sampling en el Collector de U1)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Precisión decimal compartida (Performance / Correctness)

A) Un **contexto `Decimal` explícito** de U0 (`VECTRA_DECIMAL_CTX`: precisión 28, `ROUND_HALF_UP`, trampas `InvalidOperation` y `DivisionByZero` activadas) que `finance` y la cuantización usan con `localcontext()`. Nunca se toca el contexto global del proceso (recomendado: deterministas aunque un servicio cambie el contexto global)

B) Usar el contexto global de `decimal` configurado al arrancar cada servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Enfoque de pruebas de resiliencia del proyecto (RESILIENCY-14; NFR-RES-14)
NFR-RES-14 dejó esta pregunta para NFR Design. U0 es la primera unidad que llega aquí,
así que la respuesta se registra **para todo el proyecto**. Los escenarios concretos los
documenta cada unidad con runtime.

A) Usar una práctica existente del banco de DR testing, game days o chaos engineering (indica la referencia después de `[Answer]:`)

B) No existe práctica: AI-DLC propone un calendario de pruebas de DR y un plan de experimentos de caos para adoptar

C) **Diferir a Operations**: cada unidad con runtime documenta sus escenarios en su NFR Design o Infrastructure Design (caída de zona, réplica de BD caída, explainability caído → fail-closed, Keycloak caído → 503, restore del registro con verificación de la cadena) y se ejecutan en Operations (recomendado: el alcance actual termina en los planes de tareas y Operations es placeholder)

X) Other (describe after [Answer]: tag below)

[Answer]: C

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/contracts/nfr-requirements/` (NFR-U0-01..46, stack)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/contracts/nfr-design/nfr-design-patterns.md`
  - [x] 3.1 Patrones de seguridad (pipeline, authz, invariante, logs, errores)
  - [x] 3.2 Patrones de resiliencia (JWKS) y enfoque de pruebas de resiliencia (RESILIENCY-14)
  - [x] 3.3 Patrones de rendimiento (presupuesto, contexto decimal, muestreo)
  - [x] 3.4 Escalabilidad: N/A justificado
- [x] 4. Generar `construction/contracts/nfr-design/logical-components.md` (componentes, dependencias, diagrama validado)
- [x] 5. Verificar el cumplimiento de las extensiones
- [x] 6. Registrar la respuesta de RESILIENCY-14 en `aidlc-state.md` como decisión del proyecto
