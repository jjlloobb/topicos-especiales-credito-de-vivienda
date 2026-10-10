# Decisiones de stack — U11 `product-metrics`

Decisiones del plan (`product-metrics-nfr-requirements-plan.md`, Q1–Q9 = A) y heredadas de U0
y U1. Versiones fijadas en `uv.lock`.

---

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje | Python 3.12 | U0 |
| Proceso | Un proceso `asyncio` con `vectra_common.process.init(kind="service")`; **sin FastAPI** ni `RouteContract`, porque no hay rutas de negocio | Q7 |
| Métricas y sondas | `vectra_common.ops_server` (nuevo en U0): `/metrics` (`prometheus-client`), `/healthz` y `/readyz` en 8081 | Q7 |
| Cliente HTTP | `vectra_common.deps.call` hacia U3 (F28), timeout de 5 s por página, breaker de U7 | Q4, U0 |
| Identidad | Cliente `product-metrics` de Keycloak con `private_key_jwt` (token por `deps`), solo `registry:read:metrics` | Q6, U2 |
| Tipos | `vectra_contracts` (proyección `metrics`, `FailClosedCause.category`) | U0 |
| Reglas | `gen_rules.py` genera la regla de desincronía desde el catálogo de U0; `promtool` las prueba | FD, Q8 |
| PBT | Hypothesis, incluida `RuleBasedStateMachine` (PBT-U11-02) | U0 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Q8 |
| Logging | Logger con la allowlist de U0 | U0 |

## Descartado

| Opción | Motivo |
|---|---|
| FastAPI con `create_app` solo para `/metrics` | Trae el pipeline de autorización sin ninguna ruta que lo use (Q7) |
| CronJob que empuja al Pushgateway | Sin estado incremental entre corridas y con la dependencia del Pushgateway (Q2) |
| Una réplica con una exención nueva | NFR-U1-12 exige ≥ 2; la deduplicación en las consultas resuelve las series repetidas (Q2) |
| Base de datos propia para la historia | Los meses cerrados se recalculan del registro cada día (Q3); la unidad no tiene datos propios |
