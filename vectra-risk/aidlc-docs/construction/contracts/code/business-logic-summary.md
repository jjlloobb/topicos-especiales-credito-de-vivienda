# Resumen de la lógica de negocio — U0

| Reglas | Archivo | Pruebas |
|---|---|---|
| BR-U0-01..08 | `vectra_contracts/outcome/__init__.py`, `outcome/_internal.py` | `tests/unit/test_outcome.py`, `tests/examples/test_logic_examples.py`, `tests/property/test_logic.py` (PBT-U0-01, 02, 12) |
| BR-U0-10..14 | `vectra_contracts/finance.py`, `decimal_ctx.py` | `tests/unit/test_finance.py`, PBT-U0-03, 04, 05 |
| BR-U0-15, 20..36 | `vectra_contracts/models/`, `validation.py` | `tests/unit/test_models.py`, PBT-U0-11 |
| BR-U0-37, 38 | `vectra_contracts/validation.py`, `models/registry.py` | `tests/unit/test_business_time.py`, `test_fail_closed_payload.py`, PBT-U0-15, 16 |
| BR-U0-40..43 | `vectra_contracts/labels.py`, `dane.py`, `data/` | `tests/unit/test_labels.py`, `test_derive_spec.py`, `test_data_integrity.py`, PBT-U0-06 |
| BR-U0-80, 81 | `vectra_contracts/dictionary.py` | `tests/unit/test_dictionary.py`, PBT-U0-10 |
| BR-U0-94 | `contracts/forbidden-phrases.yaml`, `tools/forbidden_phrases.py` | `tests/unit/test_forbidden_phrases.py` |
| BR-U0-95 | `models/registry.py`, `validation.py` | `tests/unit/test_models.py`, PBT-U0-13 |

`feature_vector_hash` usa `vectra_contracts/canonical.py` (RFC 8785). Datos DANE: 1122 municipios y 33
departamentos, obtenidos de datos.gov.co el 2026-10-31; la fecha de corte y la tabla de regiones siguen `[VERIFICAR]`.
