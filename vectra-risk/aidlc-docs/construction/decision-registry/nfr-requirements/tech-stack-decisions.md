# Decisiones de stack — U3 `decision-registry`

Decisiones del plan (`decision-registry-nfr-requirements-plan.md`, Q1–Q6 = A) y heredadas
de U0 y U1. Versiones pinneadas en `uv.lock`.

---

| Área | Decisión | Motivo | Origen |
|---|---|---|---|
| Lenguaje y API | Python 3.12, FastAPI, Pydantic v2, `vectra_common.create_app` | Stack común | U0 |
| Driver | **psycopg 3** (async), pool ≤ 5 por réplica | Control de `synchronous_commit` por transacción y advisory locks | Q6 |
| Base | PostgreSQL de CloudNativePG (`registry-db`), particionado declarativo por rango de `seq` | Crecimiento a 10 años | Q3, U1 |
| Migraciones | Alembic, ejecutado por el Job de migración (F44) con `registry_migrator` | DDL solo en un sync aprobado | U1 |
| JSON canónico | `vectra_contracts.canonical` (JCS, RFC 8785) | Los mismos bytes que U0 | U0 |
| Hash | SHA-256 (`hashlib`) | BR-U3-08..12 | FD |
| Firma de checkpoints | Ed25519 por el motor de la bóveda: **Vault Transit** en kind; bóveda o HSM del banco en prod. Verificación local con `cryptography` | La llave nunca sale de la bóveda | Q5 |
| Archivo | Export mensual a un bucket WORM con object lock de 10 años, vía la API S3 | NFR-U3-04 | Q1 |
| PBT | Hypothesis, incluida `hypothesis.stateful.RuleBasedStateMachine` | PBT-06, PBT-09 | Q6, U0 |
| Integración | **Testcontainers** (PostgreSQL y un doble de la bóveda) en CI | Base real sin clúster | Q6 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | NFR-U3-52 | U0 |
| Carga | k6 (append, expediente) en kind | NFR-U3-20, 21 | Q2 |

## Descartado

| Opción | Motivo |
|---|---|
| Crypto-shredding por caso | Descartado en U0 Q7; la supresión se apoya en la obligación de conservación y la re-identificación se pierde en case-db (Q1=B) |
| Una sola tabla sin particiones | Mantenimiento y verificación más costosos a 10 años (Q3=B) |
| Re-hash completo cada noche | ~150 GB por noche a 10 años (Q4=B) |
| Llave de checkpoints montada como Secret | Un pod comprometido podría robarla (Q5=B) |
| asyncpg y pruebas solo en kind | Integración más lenta y dependiente del operador (Q6=B) |
