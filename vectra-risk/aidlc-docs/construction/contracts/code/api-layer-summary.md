# Resumen de la capa de API — U0

Pipeline (`vectra_common/app_factory.py`): Telemetry → AccessLog → ProblemHandler → Authn → `require` → BodyGuard → Pydantic → handler. `app.state.pipeline` lo declara en el orden lógico de P-U0-01.

| Patrón | Archivo | Pruebas |
|---|---|---|
| P-U0-01, 12 | `app_factory.py`, `vectra_contracts/routes/` | `tests/unit/test_app_factory.py`, `test_routes.py` |
| P-U0-02 | `authz.py` | `tests/unit/test_authz.py`, `test_require_app.py`, PBT-U0-09 |
| P-U0-03 | `vectra_contracts/outcome/` | `tests/unit/test_outcome.py` |
| P-U0-04 | `logging.py` | `tests/unit/test_logging.py`, PBT-U0-07 |
| P-U0-05 | `errors.py` | `tests/unit/test_errors.py`, PBT-U0-08 |
| P-U0-06 | `jwks_cache.py`, `authn.py` | `tests/unit/test_jwks_cache.py`, `test_authn.py` |
| P-U0-07 | `deps.py`, `deadline.py`, `process.py` | `tests/unit/test_deps.py`, `test_deadline.py`, PBT-U0-14 |
| P-U0-11 | `telemetry.py` | `tests/unit/test_telemetry.py` |
| NFR-U0-48 | `ops_server.py` | `tests/unit/test_ops_server.py` |

Las respuestas exactas (400, 401, 403, `mfa_required`, 415, 422, 503, 504) están en `tests/examples/test_api_examples.py`.
