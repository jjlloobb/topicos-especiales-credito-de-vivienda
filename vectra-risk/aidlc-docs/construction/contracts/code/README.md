# Código de U0 `contracts`

Generado el 2026-10-31. Código en `vectra-risk/contracts/`; uso en `contracts/README.md`.

- [Lógica de negocio](business-logic-summary.md)
- [Capa de API](api-layer-summary.md)
- [Specs y cliente](contracts-and-client-summary.md)

Verificación: `make -C contracts check` y `uv run python contracts/tools/mutation.py`.

## Trazabilidad a código de los identificadores sin referencia en él (2026-11-01)

| Identificador | Archivo |
|---|---|
| BR-U0-20, BR-U0-21, BR-U0-32, BR-U0-33 | `contracts/python/vectra_contracts/src/vectra_contracts/validation.py` |
| BR-U0-31 | `contracts/python/vectra_common/src/vectra_common/app_factory.py` (`_body_guard`) |
| NFR-U0-04, NFR-U0-17, NFR-U0-43 | `.github/workflows/contracts.yml` |
| NFR-U0-12 | `contracts/python/vectra_common/src/vectra_common/errors.py` |
| NFR-U0-15 | `contracts/python/vectra_common/src/vectra_common/app_factory.py` (`check_contract`) |
| NFR-U0-31, NFR-U0-32 | `pyproject.toml` |
| NFR-U0-33 | `contracts/tools/version_gate.py` |
| NFR-U0-34 | `contracts/ts/src/index.ts` |
| P-U0-08 | `contracts/tests/unit/test_cross_unit_contract.py` (este patrón deja los escenarios con clúster a U1; aquí queda lo que se prueba sin él) |
