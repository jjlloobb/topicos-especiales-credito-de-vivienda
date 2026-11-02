F-01: Corregido: nueva `test_models_public_api_in_clean_interpreter` (CA-4) en un `python -I` limpio, que lee `dir()` y `models.api` antes de cargar nada; las tres mutaciones de CA-4 la hacen fallar (bitácora, ronda 4) y quedaron revertidas.
F-02: Corregido: `import typing` + `if typing.TYPE_CHECKING:` sin alias y `del typing`; grimp con `exclude_type_checking_imports=True` ya no encuentra la cadena outcome -> ... -> outcome, y `import *` no filtra nombres.
F-03: Aceptado como está: la lista `_LAZY_API_NAMES` queda a mano y la cubre la prueba, que falla si cambia `api.py` sin actualizarla.
