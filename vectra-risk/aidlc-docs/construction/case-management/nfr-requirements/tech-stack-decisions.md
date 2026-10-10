# Decisiones de stack — U8 `case-management`

Decisiones del plan (`case-management-nfr-requirements-plan.md`, Q1–Q9 = A) y heredadas de
U0, U1, U3 y U4. Versiones pinneadas en `uv.lock`.

---

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje y API | Python 3.12, FastAPI, Pydantic v2, `vectra_common.create_app` | U0 |
| Contratos y derivación | `vectra_contracts` (`derive`, validación, `check_business_time`, tipos) | U0 |
| Clientes HTTP | `httpx` (async) solo a través de `vectra_common.deps.call`, con timeout obligatorio y circuit breaker (fallo = timeout, conexión o 5xx) | U0, Q6 |
| Driver | **psycopg 3** (async), pool ≤ 5 por réplica, sin ORM | Q8, U3, U4 |
| Base | PostgreSQL de CloudNativePG (`case-db`), criticidad High | U1 |
| Migraciones | Alembic, ejecutado por el Job de migración (F44) con `case_migrator`; incluye la tabla `case_transitions` con sus filas y el trigger `guard_transition`, el trigger `guard_vencido`, las políticas RLS de `evidence_outbox` y la fila de `retention_settings` (P-U8-05, INF-U8-01; precisado el 2026-10-08) | Q8, FD |
| Cola | Tabla `evaluation_jobs` con `FOR UPDATE SKIP LOCKED`, sondeo ≤ 500 ms, transacciones cortas sin conexión retenida durante la llamada | FD, Q2, Q3 |
| Procesos | Una imagen, dos Deployments (`case-service`, `case-worker`) y el CronJob `case-retention` | Q3 |
| Retención | CLI del mismo paquete (`python -m vectra_case.retention --dsn …`), la misma para el CronJob y el `restore-drill` de U1 | Q8, BR-U8-20 |
| `core-banking-mock` | FastAPI sin base, con fixtures en un archivo versionado; solo kind y staging (INF-U8-02) | Q5, Q8 |
| PBT | Hypothesis, incluida `hypothesis.stateful.RuleBasedStateMachine` (PBT-U8-01, 07) | U0 |
| Integración | Testcontainers (PostgreSQL); dobles de scoring, governance y del registro (este validado con las pruebas de append de U3) | Q8 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Q9 |
| Carga | k6 en kind (U12) | Q1, Q2 |

## Descartado

| Opción | Motivo |
|---|---|
| Un objetivo único de p95 ≤ 1 s para la API | Ocultaría problemas de las dependencias (Q1=B) |
| p95 ≤ 60 s hasta `listo` | No cumple «recomendación disponible al abrir el caso» (Q2=B) |
| API y worker en un solo proceso | Una carga de evaluaciones competiría con la consola (Q3=B) |
| KEDA para escalar por la cola | Componente de plataforma nuevo; el margen de 4× y la alerta de cola atrasada bastan (Q3=C) |
| Sin cambios en U4 | La carga adicional de case-service debe quedar en la prueba de governance (Q4=B) |
| `core-banking-mock` con 1 réplica | Exigiría una excepción a `require-spread-and-pdb` (Q5=B) |
| Solo timeouts | Con una dependencia caída, cada intento esperaría su timeout completo (Q6=B) |
| Cifrado de `case_identifiers` en la aplicación | Contradice U0 Q7 (sin crypto-shredding); la retención es un `DELETE` (Q7=B) |
| SQLAlchemy 2 (ORM) | Las transacciones cortas y el `SKIP LOCKED` se controlan mejor con SQL explícito, como en U3 y U4 (Q8=B) |
| Cobertura ≥ 85 % sin mutación | Insuficiente para la lógica que decide qué ve el analista y qué decisión vale (Q9=B) |
