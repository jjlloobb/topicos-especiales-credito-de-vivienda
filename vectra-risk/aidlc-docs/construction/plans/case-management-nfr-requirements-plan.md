# Plan de NFR Requirements — U8 `case-management`

**Alcance:** requisitos no funcionales y stack de `case-service` (API, worker de evaluación,
reconciliador de evidencia, barridos y CronJob `case-retention`) y de `core-banking-mock`,
sobre el Functional Design aprobado (BR-U8-01..22).

**Ya decidido** (no se pregunta):
- Python 3.12, FastAPI, Pydantic v2, `vectra_common` (`create_app`, `deps.call` con timeout obligatorio y circuit breaker, `deadline`), `vectra_contracts` (`derive`, validación, `check_business_time`), Hypothesis (U0);
- cola transaccional en `evaluation_jobs` con `FOR UPDATE SKIP LOCKED`, backoff de 6 intentos (≈ 15,5 min), timeout de 7 s hacia scoring, evidencia en dos fases con outbox y reconciliador, abandono a las 24 h (FD);
- volumen de diseño: 2 solicitudes/s sostenidas y picos de 10/s (NFR-U1-10); prueba de carga a 20/s durante 15 min (NFR-U1-11, límite del simulador ajustado en U2);
- `case-db` con criticidad **High**, 3 instancias y réplica síncrona en otra zona (NFR-U1-01, 02); si cae la zona con 2 instancias, las escrituras se bloquean hasta que haya réplica (NFR-U1-03);
- dependencias: `POST /v1/recommendations` p95 ≤ 400 ms y p99 ≤ 1 s (NFR-U7-01); append al registro p95 ≤ 50 ms (NFR-U3-20); `serving-config` p95 ≤ 20 ms con caché ≤ 5 s (NFR-U4-10);
- readiness solo con las dependencias propias de datos: `case-db` (P-U1-04);
- sin egress (X02); X01 en dos capas (NetworkPolicy + Linkerd L7) hacia el core.

**Pendiente heredado del FD** (§8 de U8): las lecturas de `serving-config` de case-service se
suman a las de scoring y hay que verificarlas contra NFR-U4-10/11 y el script k6 de U4 (Q4).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Latencia de la API de case-service (Performance)
Ninguna operación síncrona espera a scoring: la ingesta solo crea el caso y su trabajo.

A)
   | Operación | Objetivo |
   |---|---|
   | `POST /v1/intake/applications` y `POST /v1/cases` (validación + caso + trabajo en una transacción) | p95 ≤ 200 ms |
   | `GET /v1/cases` (bandeja, página ≤ 100) | p95 ≤ 300 ms |
   | `GET /v1/cases/{id}` (incluye el core con timeout de 500 ms en casos `decidido`) | p95 ≤ 300 ms, p99 ≤ 800 ms |
   | `POST /v1/cases/{id}/decision` (incluye el append síncrono al registro) | p95 ≤ 300 ms |
   | `POST /v1/cases/{id}/explanation-views` | p95 ≤ 200 ms |

   Medidas a 10 solicitudes/s de ingesta, con la consola en paralelo. (Recomendado: holgado frente a las dependencias de U3 y U4, y deja el presupuesto del BFF para U10)

B) Un solo objetivo para toda la API: p95 ≤ 1 s

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Tiempo hasta `listo` (Performance, NFR-PER-01)
NFR-PER-01 pide la recomendación disponible cuando el analista abre el caso.

A) Desde la ingesta hasta `listo`, cuando scoring responde con una `Recommendation` al primer intento: **p95 ≤ 5 s** a 10 solicitudes/s. Se mide con el histograma `vectra_case_time_to_ready_seconds` (de `created_at` a `listo`), que excluye los casos que pasaron por `en_sincronizacion`, porque esos dependen del backoff. (Recomendado: scoring tarda ≤ 1 s en el p99; el resto es la espera en la cola)

B) p95 ≤ 60 s

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Ajuste: fijar el intervalo de sondeo de la cola de `evaluation_jobs` en 500 ms como máximo, para que el p95 ≤ 5 s sea alcanzable. Añadir la métrica `vectra_case_first_attempt_failure_ratio` (casos que no llegan a `listo` al primer intento), porque el histograma excluye los casos que pasaron por `en_sincronizacion` y ocultaría esos fallos.

## Question 3 — Topología y escalado del worker (Scalability)

A)
   - **Dos Deployments con la misma imagen**: `case-service` (API, barridos y reconciliador) y `case-worker` (evaluación). Así una carga de evaluaciones no compite con la consola.
   - El worker es asíncrono, con **16 trabajos en vuelo por réplica**. Con 2 réplicas son 32 en vuelo, unas 80 evaluaciones/s a 400 ms cada una: 4× el pico de prueba.
   - Los dos Deployments tienen ≥ 2 réplicas repartidas por zona, PDB y **HPA de 2 a 6 por CPU al 70 %**, como el resto de servicios (NFR-U1-12). La plataforma no tiene métricas personalizadas para el HPA.
   - El retraso de la cola se vigila con la métrica `vectra_case_jobs_overdue` (trabajos con `run_at` vencido hace más de 30 s y sin tomar) y una alerta, con umbral en NFR Design.
   - Los barridos (BR-U8-10, 14) y el reconciliador corren en todas las réplicas de `case-service`; `SKIP LOCKED` evita el trabajo duplicado.

   (Recomendado)

B) Un solo Deployment con la API y el worker en el mismo proceso

C) Worker escalado por la longitud de la cola con KEDA (componente nuevo de plataforma en U1)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Ajuste: el worker toma el trabajo con `locked_until = ahora + 30 s` en una transacción corta y **no retiene conexión ni transacción** mientras espera a scoring (hasta 7 s), porque hay 16 trabajos en vuelo por réplica con un pool de a lo sumo 5 conexiones. El HPA por CPU no reacciona a una cola atrasada (el worker espera E/S): la protección real es el margen de 4× y la alerta sobre `vectra_case_jobs_overdue`.

## Question 4 — Carga sobre governance (pendiente del FD; NFR-U4-10/11)
Cada réplica de `case-worker` lee `serving-config` con caché ≤ 5 s. Con el máximo de 6 réplicas
de scoring y 6 de `case-worker`, governance recibe hasta 12 clientes cada 5 s (≈ 2,4 req/s,
casi todas 304). El `feature_spec` se cachea sin expiración por versión (LRU de 4), así que solo
se lee al cambiar de versión.

A) Ampliar **NFR-U4-10** a «12 clientes (6 de scoring y 6 de `case-worker`) cada 5 s» con el mismo p95 ≤ 20 ms, y el script k6 del plan de U4 (Paso 19) a 12 clientes más una lectura de `feature_spec` por cliente al cambiar de versión. NFR-U4-11 no cambia: case-service no hace transiciones. Se registra en el §7 de este NFR (recomendado: el margen es amplio y la prueba lo confirma)

B) Sin cambios en U4: la carga adicional es despreciable

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Disponibilidad y modos de fallo (Availability / Reliability)

A)
   - Criticidad **High** para `case-service` y `case-worker`, como `case-db` (NFR-U1-01). Fuera del SLO de 99,5 % de la ruta de recomendación (NFR-RES-02), pero con su propia alarma: si la API de casos no responde, el canal reintenta con la misma `Idempotency-Key`.
   - **`case-db` sin escritura** (NFR-U1-03 o caída): la ingesta, el alta manual y la decisión responden `503` y no se crea ni se cambia nada; las lecturas siguen si queda una instancia. El canal reintenta con la misma llave (BR-U8-02).
   - **Registro caído**: la decisión responde `503` y queda `pendiente_registro` (BR-U8-18); las evaluaciones siguen, porque las escribe scoring.
   - **governance o scoring caídos**: los casos pasan a `en_sincronizacion` y escalan a los 15,5 min (BR-U8-07, 09).
   - **Core caído**: `get_case` responde con `credit_status = no_disponible` (BR-U8-21).
   - `core-banking-mock`: 2 réplicas y PDB, como cualquier Deployment de Vectra (NFR-U1-04), con criticidad **Low** y sin base de datos (datos sembrados por fixtures).

   (Recomendado)

B) Igual que A, pero con `core-banking-mock` en 1 réplica y una excepción a la política `require-spread-and-pdb`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Ajuste: corregir la viñeta del registro caído. Con el registro caído la decisión responde `503` y queda `pendiente_registro` (BR-U8-18), **y** scoring responde `FailClosed(registry_unavailable)` porque añade la recomendación de forma síncrona (BR-U0-08): los casos pasan a `en_sincronizacion` y escalan a los 15,5 min, igual que con governance o scoring caídos. Las evaluaciones no siguen.

## Question 6 — Timeouts y circuit breakers de case-service (Resilience, RESILIENCY-10)

A)
   | Llamada (con `deps.call`) | Timeout | Circuit breaker |
   |---|---|---|
   | `case-worker` → `serving-config` | 500 ms | Sí; abierto → `serving_config_unavailable` sin llamar |
   | `case-worker` → `feature_spec` | 1 s | Sí (el mismo de governance) |
   | `case-worker` → scoring | 7 s (FD) | Sí; abierto → `scoring_unreachable` sin llamar, y el intento cuenta |
   | case-service → registro (decisión, consulta, reconciliador) | 2,5 s (U3) | Sí; abierto → 503 en la decisión, sin llamar |
   | case-service → core | 500 ms (FD) | Sí; abierto → `no_disponible` sin llamar |

   Mismo breaker que U7 (`vectra_common.deps`, NFR-U0-23): se abre con ≥ 50 % de fallos en 20 llamadas dentro de 30 s y pasa a semiabierto a los 10 s. Ningún reintento fuera de los ya definidos (backoff del caso, reconciliador, 401 de scoring). (Recomendado)

B) Solo timeouts, sin circuit breakers

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Ajuste: solo cuentan como fallo del circuit breaker los timeouts, los errores de conexión y los 5xx. Los 4xx de scoring (`scoring_rejected`) no cuentan, para que una solicitud defectuosa no abra el circuito de todos los casos. Confirmar este criterio en `vectra_common.deps` (NFR-U0-23).

## Question 7 — Protección de los identificadores en `case-db` (Security)
`case_identifiers` guarda PII directa y `cases.application.free_text` puede contenerla.

A)
   - Cifrado del volumen (StorageClass cifrada, U1) y de los backups (F70), TLS en toda conexión (NFR-SEC-01).
   - Mínimo privilegio en la base: `case_app` lee y escribe `case_identifiers`, pero no puede borrarla; `case_retention` es el único que borra (FD); sin acceso de otros servicios (solo case-service tiene credenciales de `case-db`).
   - **Sin cifrado por columna**: el crypto-shredding se descartó en U0 Q7, y la eliminación por retención es un `DELETE` de una fila.
   - Ningún log, métrica ni traza lleva identificadores (BR-U0-50..53); el log `case.viewed` solo lleva `user_id`, `case_id` y rol.

   (Recomendado: coherente con U0 Q7 y U3)

B) Igual que A, más cifrado de `case_identifiers` en la aplicación con una llave de la bóveda (Vault Transit en kind)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Stack de persistencia y pruebas (Tech Stack)

A)
   - **psycopg 3** (async) con pool ≤ 5 conexiones por réplica, como U3 y U4; Alembic con el Job de migración y el rol `case_migrator`.
   - Trigger `guard_vencido` y tabla de transiciones permitidas en las migraciones (FD).
   - `case-retention` es una CLI del mismo paquete (`python -m vectra_case.retention --dsn …`), que el CronJob y el `restore-drill` de U1 ejecutan igual.
   - `core-banking-mock`: FastAPI sin base, con fixtures en un archivo versionado.
   - Pruebas: Testcontainers (PostgreSQL), dobles de scoring, governance y del registro (este último validado con las pruebas de append de U3), k6 para la carga en kind.

   (Recomendado)

B) SQLAlchemy 2 (async) como ORM sobre psycopg 3

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Ajuste: con 6 réplicas de `case-service` y 6 de `case-worker` son 12 clientes de `case-db` (12 × 5 conexiones, más el 20 % de `P-U1-08`, el CronJob `case-retention` y el Job de migración). Registrarlo en el §7 para que `max_connections` de `case-db` lo cubra.

## Question 9 — Umbral de calidad de pruebas (Maintainability / Testing)
`case_fsm`, `validate_decision` y `views` deciden qué ve el analista y qué decisión vale.

A) Cobertura de ramas **≥ 95 %** en case-service y **100 %** en `case_fsm`, `backoff`, `decision`, `views`, `intake` y `evidence`. **Mutation testing** con `mutmut` en `case_fsm`, `validate_decision` y `views`, con 0 sobrevivientes sin justificar. PBT-U8-01..08 con el perfil `ci` (recomendado: el mismo nivel que U4 y U7)

B) Cobertura ≥ 85 % sin mutation testing

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Ajuste: la cobertura del 100 % incluye también `evaluation`, `sweeps` y `retention` (este último borra identificadores). `mutmut` incluye también `backoff` (función pura, PBT-U8-02).

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U8 y los NFR heredados (NFR-PER-01, NFR-RES, NFR-SEC; U1, U3, U4, U7)
- [x] 2. Recoger y validar las respuestas (Q1–Q9 = A; ajustes en Q2, Q3, Q5, Q6, Q8 y Q9)
- [x] 3. Generar `construction/case-management/nfr-requirements/nfr-requirements.md`
- [x] 4. Generar `construction/case-management/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Registrar los cambios a otras unidades (Q4: NFR-U4-10 y el script k6 de U4)
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
