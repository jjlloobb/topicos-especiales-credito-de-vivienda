F-01: Corregido: quitada la exención `identity-edge/tests/**` de `pyproject.toml`; ninguna regla hace falta (ruff pasa sin ella). Un `try/except Exception: pass` en `identity-edge/tests/` vuelve a dar S110 y BLE001 (ver bitácora, Ronda 2).
F-02: Corregido: `identity-edge/tests/conftest.py` ya no reexporta `pytest_report_header`; la sesión combinada imprime la cabecera una sola vez.
F-03: Corregido: la prueba ya no tiene el literal "dev"; el conftest obtiene el perfil por defecto cargando el módulo de U0 sin `HYPOTHESIS_PROFILE` y la prueba lo recibe por la fixture `u0_default_profile`.
