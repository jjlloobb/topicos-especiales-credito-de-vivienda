"""Raiz de las pruebas de U8.

`--import-mode=importlib` deriva el nombre de modulo de la ruta bajo `case-management/`: `core_banking_mock/tests/test_x.py` seria
`core_banking_mock.tests.test_x`, y pytest crearia un `core_banking_mock` vacio que tapa el paquete instalado. Importar el paquete real
primero deja ese nombre ocupado y los modulos de prueba cuelgan de el.
"""

import core_banking_mock  # noqa: F401
