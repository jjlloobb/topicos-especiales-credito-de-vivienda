# Código de U5 `reference-model`

Generado el 2026-11-08, con el alcance de la demo (`demo-kind-alcance.md` §3, U5). Código en `vectra-risk/reference-model/`; uso en `reference-model/docs/release.md`. Herramienta offline, sin runtime: sus artefactos entran por U4 y los sirve U6.

- [Procedimiento de entrega al model-store](../../../../reference-model/docs/release.md)
- [Cierre acotado a la demo](../evidence/cierre-demo.md)

Verificación: `make -C reference-model check` (ruff, import-linter, pruebas con cobertura de ramas, runbook de entrega, trazabilidad y Paso 11). Entrega: `make -C reference-model release`, `make -C reference-model verify-release`.

Cobertura: ≥ 90 % de ramas en `vectra_reference` y 100 % en `envelope/confidence.py` (NFR-U5-33); `reference-model/pytest.ini` apunta `--cov` a `vectra_reference` en lugar de a la cobertura de U0 de la raíz.

## Trazabilidad a código de los identificadores sin referencia en él (2026-11-08)

`platform/tests/test_traceability.py` solo reconoce los identificadores de U5 que están en tablas o encabezados (los NFR-U5). Los BR-U5 están en párrafos y los PBT-U5 llevan otro prefijo, así que esa prueba no los ve: se rastrean aquí a mano, y la bitácora de U05-T04 trae el `grep` que lo demuestra.

### Reglas de negocio y propiedades

| Identificador | Código | Prueba |
|---|---|---|
| BR-U5-01 | `reference-model/src/vectra_reference/generate.py` | `reference-model/tests/unit/test_config_drives_output.py` |
| BR-U5-02, BR-U5-04 | `reference-model/src/vectra_reference/generate.py` | `reference-model/tests/unit/test_generate_sha256.py` |
| BR-U5-03 | `reference-model/src/vectra_reference/generate.py` | `reference-model/tests/property/test_generate.py` |
| BR-U5-05 | `reference-model/src/vectra_reference/generate.py` | `reference-model/tests/examples/test_train.py` (el AUC es su efecto) |
| BR-U5-06, BR-U5-14, BR-U5-15 | `reference-model/src/vectra_reference/proxy.py` | `reference-model/tests/examples/test_proxy.py` |
| BR-U5-07, BR-U5-08 | `reference-model/src/vectra_reference/train.py` | `reference-model/tests/examples/test_train.py` |
| BR-U5-09, BR-U5-10 | `reference-model/src/vectra_reference/package.py` | `reference-model/tests/property/test_package.py` |
| BR-U5-11 | `reference-model/src/vectra_reference/envelope/fit.py` | `reference-model/tests/property/test_envelope.py` |
| BR-U5-12 | `reference-model/src/vectra_reference/envelope/confidence.py` | `reference-model/tests/property/test_envelope.py` |
| BR-U5-13 | `reference-model/src/vectra_reference/envelope/calibrate.py` | `reference-model/tests/property/test_envelope.py` |
| BR-U5-16, BR-U5-17, BR-U5-18 | `reference-model/src/vectra_reference/adversarial.py` | `reference-model/tests/property/test_adversarial.py`, `reference-model/tests/examples/test_adversarial_manifest.py` |
| PBT-U5-01, PBT-U5-02 | `reference-model/src/vectra_reference/generate.py` | `reference-model/tests/property/test_generate.py` |
| PBT-U5-03, PBT-U5-04 | `reference-model/src/vectra_reference/envelope/confidence.py` | `reference-model/tests/property/test_envelope.py` |
| PBT-U5-05, PBT-U5-06 | `reference-model/src/vectra_reference/package.py` | `reference-model/tests/property/test_package.py` |
| PBT-U5-07 | `reference-model/src/vectra_reference/adversarial.py` | `reference-model/tests/property/test_adversarial.py` |

### Requisitos no funcionales sin referencia en el código

| Identificador | Archivo |
|---|---|
| NFR-U5-03 | `reference-model/docs/release.md` y `reference-model/scripts/verify_release.py` (prueba: `reference-model/tests/unit/test_verify_release.py`). Sin `cosign verify` en la demo |
| NFR-U5-10 | `reference-model/src/vectra_reference/train.py` |
| NFR-U5-30 | `reference-model/src/vectra_reference/explainer_validation.py` |
| NFR-U5-31 | `reference-model/src/vectra_reference/envelope/fit.py` |
| NFR-U5-32 | `reference-model/src/vectra_reference/envelope/confidence.py` |
| NFR-U5-33 | `reference-model/Makefile` (`test`) |
| NFR-U5-34 | `reference-model/src/vectra_reference/generate.py` |

### Diferido por la demo (Paso 8 del plan)

| Identificador | Situación |
|---|---|
| NFR-U5-01, NFR-U5-02, NFR-U5-20 | Sin workflow, release firmada ni medición de duración: el Paso 8 queda `[ ]`. Los nombra `reference-model/docs/release.md` («Diferido por la demo»), y por eso `test_traceability.py` no los marca; no están implementados |
