"""Las propiedades stateful del Bloque D corren contra PostgreSQL real (Testcontainers): comparten los fixtures de `integration/`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))

from governance_pg import pg, roles, template_db  # noqa: E402, F401
