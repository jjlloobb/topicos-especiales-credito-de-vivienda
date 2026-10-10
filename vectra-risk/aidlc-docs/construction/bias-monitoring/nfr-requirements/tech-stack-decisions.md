# Decisiones de stack — U9 `bias-monitoring`

---

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje y API | Python 3.12, FastAPI, Pydantic v2, `vectra_common.create_app` (servicio HTTP) | U0 |
| Contratos | `vectra_contracts`: tipos de U0 §9.4 (`MonitoringQuery`, `MonitoringWindow`, `CountTable`, `FreezeContext`, `PrePostReport`, `DisparityView`, …) | U0, FD |
| Clientes HTTP | `httpx` solo a través de `vectra_common.deps.call`, con timeout obligatorio y circuit breaker (F26, F27) | U0 |
| Librería `vectra_disparity` | **Python puro**: solo la biblioteca estándar (`math`; `decimal` para la salida en `Decimal4`). Wilson, Newcombe (método 10) y combinación de varianzas implementados en `stats`. Sin numpy, scipy ni pandas en runtime. La usan el CronJob, el servicio, el `model-validation-job` de U4 y U5 | Q5 |
| Dependencias de desarrollo | Fairlearn, pandas y numpy, solo para el oráculo de PBT-U9-01 y la simulación estadística | Q5 |
| CronJob | El mismo paquete con un punto de entrada `python -m vectra_bias.run`; métricas al Pushgateway con el cliente de `prometheus-client` (`push_to_gateway` con `PUT` por grupo) | FD, BR-U9-20 |
| Base de datos | Ninguna (lee conteos agregados del registro) | FD |
| PBT | Hypothesis, incluida `RuleBasedStateMachine` (PBT-U9-05) | U0 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Q6 |
| Carga | k6 en kind (NFR-U9-02) | Q2 |
| Versionado de la librería | SemVer; la versión viaja en el paquete de contexto | Q6 |

## Descartado

| Opción | Motivo |
|---|---|
| numpy y scipy en runtime | Imagen más grande y más superficie de escaneo para pocas fórmulas (Q5 = B) |
| Corrida cada 5 min | Triplica la carga sobre el registro para ganar unos minutos de detección (Q1 = B) |
| HPA en el servicio HTTP | Carga baja; la caché de 15 min absorbe las consultas (Q4 = B) |
| Simulación estadística en cada PR | Tarda minutos; corre cada noche y en los PR que cambian `stats` o `freeze_rule` (Q6 = B) |
