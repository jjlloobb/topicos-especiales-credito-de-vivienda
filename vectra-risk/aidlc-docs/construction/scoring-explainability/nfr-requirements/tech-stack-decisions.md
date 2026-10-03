# Decisiones de stack — U7 `scoring-explainability`

Decisiones del plan (`scoring-explainability-nfr-requirements-plan.md`, Q1–Q5 = A) y heredadas.

---

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje y API | Python 3.12, FastAPI, Pydantic v2, `vectra_common.create_app` | U0 |
| Clientes HTTP | `httpx` (async) solo a través de `vectra_common.deps.call` | U0 |
| Timeouts y circuit breaker | Los de `vectra_common.deps` (implementación propia y mínima, con propiedad stateful) | Q2, Q4 |
| Decimales | `vectra_contracts` (`Decimal4`, contexto propio) | U0 |
| Plantillas | Archivos de texto versionados (`template:v1`, `applicant:v1`), con mensajes en español | FD Q5, Q7 |
| PBT | Hypothesis | U0 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Q5 |
| Carga | k6 (U12) | Q1 |

## Descartado

| Opción | Motivo |
|---|---|
| p95 ≤ 1 s y p99 ≤ 3 s | Holgura innecesaria que ocultaría problemas de las dependencias (Q1=B) |
| Solo timeouts | Bajo una dependencia caída, cada solicitud esperaría su timeout completo (Q2=B) |
| Réplicas fijas | No escala con la carga (Q3=B) |
| Librería de circuit breaking de terceros | Dependencia externa en una pieza de seguridad, y semánticas distintas entre servicios (Q4=B) |
| Cobertura ≥ 85 % sin mutación | Insuficiente para la lógica que ve el comité (Q5=B) |
