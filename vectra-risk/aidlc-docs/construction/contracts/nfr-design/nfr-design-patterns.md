# Patrones de NFR Design — U0 `contracts`

Decisiones del plan (`contracts-nfr-design-plan.md`): Q1–Q9 = A, Q10 = C. Cada patrón
indica los NFR que satisface y cómo se verifica. Los IDs `P-U0-xx` se referencian en el
plan de tareas.

---

## 1. Patrones de seguridad

### P-U0-01 — Fábrica única de aplicación (Q1)
- `vectra_common.create_app(service_name, contract, handlers)` es la **única** forma de crear una app de servicio.
- Monta el pipeline ASGI en un orden fijo:

```text
1. TelemetryMiddleware     traceparent -> correlation_id (BR-U0-62)
2. AuthnMiddleware         JWT + JWKS (BR-U0-70)
3. AuthzDependency         require(scopes, roles, mfa) por ruta (BR-U0-71, 72)
4. BodyGuard               content-type, JSON válido, tamaño <= 32 KiB (BR-U0-21, 31)
5. Pydantic strict         validación de esquema (BR-U0-20..36)
6. handler del servicio
7. ProblemHandler          VectraError -> Problem; resto -> internal_error (BR-U0-60)
8. AccessLog               un LogRecord por request (BR-U0-50)
```

- Los health checks y `/metrics` se montan en una app separada en el puerto 8081, sin las capas 2–5.
- **Verificación**: una prueba inspecciona el stack de una app creada con `create_app` y compara el orden exacto. import-linter prohíbe que los servicios importen `fastapi.FastAPI` directamente.
- **Satisface**: NFR-U0-01, 15; SECURITY-08, 15.

### P-U0-02 — Autorización declarativa con auditoría al arrancar (Q2)
- Cada ruta declara `Security(require(scopes={Scope.X}, roles={Role.Y}, mfa=bool))`.
- `Scope` y `Role` son `Enum` generados desde el catálogo (domain-entities §7.2), así que un scope inexistente falla en el type-check y al importar.
- Al arrancar, `create_app` recorre las rutas del puerto 8080 y falla si alguna no tiene el marcador `require` (deny by default).
- **Verificación**: PBT-U0-09 (semántica); prueba de arranque con una ruta sin marcador → `ContractViolation`.
- **Satisface**: NFR-U0-15; BR-U0-71, 72; SECURITY-08.

### P-U0-03 — Invariante de `Recommendation` en tres capas (Q4)

| Capa | Mecanismo | Qué impide |
|---|---|---|
| 1. Estructural | `model_validator` en `Recommendation`, también al deserializar: versión de modelo igual en recomendación, explicación y diccionario; `factuality_check == "passed"`; `registry_entry_id` no vacío; `score`/`confidence` en [0, 1] | Que circule una `Recommendation` inconsistente, aunque venga por la red |
| 2. Construcción | `Recommendation` y `Ready` exigen un token privado del módulo `outcome`; sin él, la construcción lanza `ContractViolation`. La deserialización usa `RecommendResult.from_wire()`, que aplica la capa 1 | Construir directamente en proceso, saltándose `check_preconditions`/`build_outcome` |
| 3. Dependencias | import-linter prohíbe importar `vectra_contracts.outcome._internal` fuera de `outcome` | Obtener el token desde otro módulo |

- **Verificación**: PBT-U0-01; pruebas que construyen directamente → error; `from_wire` con versiones distintas → error; contrato de import-linter en CI.
- **Satisface**: AUTONOMIA-06; NFR-U0-02, 22, 40, 41.

### P-U0-04 — Allowlist de logs con conteo de descartes (Q5)
- `structlog` termina en un procesador `allowlist_filter` que conserva solo las claves de `LogRecord`.
- Cada clave descartada incrementa `vectra_log_fields_dropped_total{service, event}`, sin el nombre ni el valor del campo.
- El `logging` estándar de terceros se redirige al mismo pipeline (`structlog.stdlib.ProcessorFormatter`).
- **Modo `strict`** (`VECTRA_LOG_STRICT=1`, activado en desarrollo y CI): en vez de descartar, lanza `LogContractViolation`, así que la prueba falla.
- Alerta en producción si `vectra_log_fields_dropped_total` crece (la regla de alerta la define U1).
- **Verificación**: PBT-U0-07; prueba en modo `strict` con una clave no permitida → excepción; prueba con un log de `httpx` con PII → ausente en la salida.
- **Satisface**: NFR-U0-13; AUTONOMIA-05; SECURITY-03.

### P-U0-05 — Jerarquía cerrada de errores (Q6)
- `VectraError(code)` tiene una subclase por `code` del catálogo (`ValidationFailed`, `Unauthenticated`, `Forbidden`, `MfaRequired`, `NotFound`, `ConflictState`, `PayloadTooLarge`, `RateLimited`, `DependencyUnavailable`, `MalformedRequest`, `UnsupportedMediaType`).
- El `ProblemHandler` traduce **solo** `VectraError`; cualquier otra excepción se convierte en `internal_error`, con un log de tipo y `error_code`, sin `str(exc)` (BR-U0-52).
- Las excepciones de dependencias se envuelven en el punto de llamada con el helper `vectra_common.deps.call(...)`, que aplica el timeout y convierte `httpx.TimeoutException` y los errores de conexión en `DependencyUnavailable`.
- **Verificación**: PBT-U0-08; prueba de que una excepción de terceros que llega al handler da `internal_error`.
- **Satisface**: SECURITY-15; NFR-U0-12; BR-U0-60, 61.

## 2. Patrones de resiliencia

### P-U0-06 — Cache de JWKS con single-flight (Q3)

```text
validar token(kid):
  si kid en cache y cache vigente (10 min)      -> verificar firma
  si kid desconocido o cache vencida:
     si hubo refresco hace < 30 s               -> usar cache vigente; si no la hay -> 503
     si no: adquirir lock (single-flight)
            GET JWKS con timeout 2 s, 1 intento
            ok    -> reemplazar cache, verificar
            falla -> cache vigente ? verificar con ella : DependencyUnavailable (503)
```

- El cache es en memoria y por proceso; no hay cache compartido.
- El límite de 1 refresco cada 30 s hace de circuit breaker: protege a Keycloak de ráfagas de `kid` falsos.
- Métrica `vectra_jwks_refresh_total{result=ok|error|throttled}`.
- **Verificación**: prueba con un servidor JWKS falso que cuenta las llamadas (100 requests concurrentes → 1 llamada); prueba con el JWKS caído y la cache vencida → 503 (NFR-U0-11, 12).
- **Satisface**: NFR-U0-11, 12; RESILIENCY-10 (timeout explícito y fail-fast).

### P-U0-07 — Helper de llamadas a dependencias (Q6)
- `vectra_common.deps.call(client, request, timeout)` exige un timeout explícito, sin valor por defecto, y envuelve los errores de transporte (P-U0-05).
- Los servicios lo usan para KServe, explainability, el registro y governance.
- **Circuit breaker por dependencia** también en `deps` (precisado por U7 NFR Requirements Q4): estados cerrado, abierto y semiabierto con ventana deslizante. Cada servicio declara sus umbrales por dependencia. Abierto → la llamada falla de inmediato con `DependencyUnavailable`, sin salir del proceso. Métrica `vectra_circuit_state{dependency}`.
- **Presupuesto propagado y aislamiento** (precisado el 2026-10-03 por U7 NFR Design Q1 y Q4):
  - `call(..., deadline=)` usa `min(timeout, deadline − ahora)` y propaga la cabecera `x-vectra-deadline` (RFC 3339 con milisegundos); `vectra_common.deadline` la lee en el servicio que recibe y descarta una cabecera mal formada o en el pasado;
  - un `httpx.AsyncClient` por dependencia con su propio límite de conexiones; la espera de una conexión libre cuenta dentro del timeout.
- Antes decía que el circuit breaker era responsabilidad de cada servicio; se centralizó para que todos compartan la misma semántica y la misma métrica.
- **Verificación**: regla de lint que prohíbe llamar a `httpx` directamente fuera de `vectra_common.deps`; prueba de que `call` sin timeout no compila (parámetro obligatorio); **propiedad stateful** del circuit breaker: para toda secuencia de éxitos, fallos y paso del tiempo, el estado coincide con un modelo de referencia, y en estado abierto nunca se emite una llamada.
- **Satisface**: RESILIENCY-10 (timeouts y circuit breaking); NFR-RES-11.

### P-U0-08 — Enfoque de pruebas de resiliencia del proyecto (Q10 = C, RESILIENCY-14)
- **Decisión del proyecto**: la ejecución se difiere a Operations. Cada unidad con runtime documenta sus escenarios en su NFR Design o Infrastructure Design.
- Escenarios mínimos ya identificados, con su unidad dueña:

| Escenario | Resultado esperado | Unidad |
|---|---|---|
| Caída de una zona de fallo | Servicios y PostgreSQL siguen en la otra zona | U1 |
| Réplica síncrona de BD caída o rezagada | Alarma; el registro no confirma appends sin réplica | U1, U3 |
| explainability caído | `FailClosed(explainer_unavailable)`; caso `no_disponible` tras el presupuesto | U7, U8 |
| Keycloak caído con la cache de JWKS vencida | 503 `dependency_unavailable`; nunca un token sin verificar | U0, U2 |
| Restore del registro desde backup | `verify_chain` sin rupturas tras el restore | U3 |

- Lo que aporta U0: la prueba de Keycloak caído es unitaria y corre en CI (P-U0-06).
- El seguimiento de resultados lo define Operations, que hoy es placeholder.

## 3. Patrones de rendimiento

### P-U0-09 — Presupuesto medido en CI
- `pytest-benchmark` con los casos `pipeline`, `outcome` y `derive`, más el umbral de NFR-U0-01..03.
- Se compara contra el umbral absoluto, no contra la corrida anterior, para evitar falsos positivos por ruido.
- **Verificación**: `pytest contracts/tests/bench -m benchmark --benchmark-json=benchmark.json` y un script que falla si p95 o p99 superan el umbral.

### P-U0-10 — Contexto decimal propio (Q9)
- `VECTRA_DECIMAL_CTX = Context(prec=28, rounding=ROUND_HALF_UP, traps=[InvalidOperation, DivisionByZero])`.
- `finance` y la cuantización operan con `localcontext(VECTRA_DECIMAL_CTX)`; nunca leen ni modifican el contexto global.
- **Verificación**: prueba que cambia el contexto global (`prec=5`, `ROUND_DOWN`) y comprueba que los resultados de `finance` no cambian; PBT-U0-03 y PBT-U0-05.
- **Satisface**: BR-U0-10, 14; NFR-U0-22.

### P-U0-11 — Trazas con muestreo completo y allowlist (Q8)
- Muestreo `ParentBased(TraceIdRatioBased(VECTRA_TRACE_RATIO))`, con un valor por defecto de `1.0`.
- Un `SpanProcessor` aplica a los atributos de span la misma allowlist que los logs (P-U0-04).
- La auto-instrumentación de `httpx` y FastAPI está configurada para **no** capturar cuerpos, query strings ni cabeceras salvo `traceparent`.
- **Verificación**: prueba con un exportador en memoria: los atributos de span ⊆ allowlist y ningún valor de PII generado aparece.
- **Satisface**: NFR-RES-06; AUTONOMIA-05; NFR-U0-16.

## 4. Patrón de contratos

### P-U0-12 — Registro de contratos de rutas (Q7)
- `vectra_contracts.routes` declara, por servicio, cada ruta como dato: `RouteContract(service, method, path, request_model, response_model, scopes, roles, mfa, mfa_max_age=900, port=8080)`.
- Del registro se generan:
  - las specs `contracts/openapi/{service}.yaml` (NFR-U0-30);
  - el catálogo de scopes y clientes para el realm de U2;
  - la matriz rol × endpoint de US-602.
- `create_app(service, contract, handlers)` vincula cada handler a su `RouteContract` y falla si falta un handler o si sobra uno.
- **Verificación**: `make -C contracts openapi && git diff --exit-code`; prueba de arranque con un handler de más o de menos → `ContractViolation`; `oasdiff` (NFR-U0-33).
- **Satisface**: NFR-U0-30, 33; NFR-MNT-01; BR-U0-90..93.

## 5. Escalabilidad

**N/A en U0.** Las funciones son puras y sin estado compartido, así que escalan con cada
servicio. El único estado es el cache de JWKS por proceso (P-U0-06): con N réplicas hay a
lo sumo N refrescos cada 30 s hacia Keycloak, una carga despreciable.

## 6. Cumplimiento de extensiones (NFR Design U0)

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-05 | Cumple | P-U0-04, P-U0-11 (logs y trazas con allowlist; sin egress) |
| AUTONOMIA-06 | Cumple | P-U0-03 (tres capas) |
| AUTONOMIA-01..04 | N/A en esta etapa | Se verifican en el plan de tareas |
| SECURITY-03 | Cumple | P-U0-04 |
| SECURITY-05 | Cumple | P-U0-01 (capas 4–5) |
| SECURITY-08 | Cumple | P-U0-01, P-U0-02 |
| SECURITY-15 | Cumple | P-U0-05, P-U0-06 |
| RESILIENCY-10 | Cumple (alcance de U0) | P-U0-06, P-U0-07: timeouts obligatorios, presupuesto propagado, un cliente por dependencia y circuit breaker en `deps`; cada servicio fija sus umbrales (U7, U8). Antes decía que el circuit breaker lo diseñaban U7 y U8, desactualizado desde U7 NFR Requirements Q4 (precisado el 2026-10-03 por U7 NFR Design Q1) |
| RESILIENCY-14 | Cumple | P-U0-08: enfoque C registrado para el proyecto, con los escenarios mínimos y sus dueños |
| RESILIENCY-otros | N/A en U0 | Sin runtime propio |
| PBT-01..10 | Sin cambios | Las propiedades del FD siguen vigentes; P-U0-03 y P-U0-10 añaden pruebas de ejemplo |
