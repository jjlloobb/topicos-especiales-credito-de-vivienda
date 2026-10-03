# Decisiones de stack — U4 `governance`

Decisiones del plan (`governance-nfr-requirements-plan.md`, Q1–Q6 = A) y heredadas.
Versiones pinneadas en `uv.lock`.

---

| Área | Decisión | Componente | Origen |
|---|---|---|---|
| Lenguaje y API | Python 3.12, FastAPI, Pydantic v2, `vectra_common.create_app` | Servicio | U0 |
| Base | psycopg 3 (async), Alembic | Servicio | U3 |
| Kubernetes | Cliente oficial de Kubernetes para Python, con el ServiceAccount de K01 | Servicio (lanzar Jobs) | Q5 |
| Git y GitHub | GitHub CLI (`gh`) con la sesión del ingeniero; `git` con `gitsign` o GPG | `promotion-tool` | Q3, Q5 |
| Login de la CLI | OIDC con PKCE y redirect loopback contra Keycloak (cliente `promotion-tool`, U2) | `promotion-tool` | U2, Q3 |
| Inferencia | ONNX Runtime, `xgboost`, `lightgbm` | **Solo** `model-validation-job` | Q5, Q6 |
| Disparidad | Librería de U9 (dependencia de ruta del workspace) | `model-validation-job` | Q5 |
| PBT | Hypothesis, incluido `RuleBasedStateMachine` | Pruebas | U0 |
| Integración | Testcontainers (PostgreSQL) | Pruebas | U3 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Pruebas | U0 |
| Carga | k6 | Pruebas en kind | Q2 |

## Descartado

| Opción | Motivo |
|---|---|
| Configuración vencida hasta 60 s | Podría ocultar un congelamiento (Q1=B) |
| Token de servicio compartido para los PRs | Rompe la atribución y la separación entre autor y aprobador (Q3=B) |
| Retener solo mientras se usa + 12 meses | No permite defender decisiones antiguas (Q4=B) |
| HTTP directo a Kubernetes y GitHub | Más código propio en integraciones sensibles (Q5=B) |
| Job de validación con el perfil de los servicios | Es el único componente que ejecuta inferencia; necesita aislamiento propio (Q6=B) |
