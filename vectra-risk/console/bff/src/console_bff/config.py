"""Constantes del BFF: timeouts, conexiones por destino y presupuesto (P-U10-04; INF-U10-03).

Son constantes del codigo, no values ni variables de entorno: cambiarlas es un cambio de codigo con su PR
y sus pruebas (segunda revision del Infrastructure Design de U10, 2026-10-10). Este modulo no importa `os`.
"""

from types import MappingProxyType
from typing import Final

# Presupuesto: `x-vectra-deadline` = momento de entrada al BFF + 9 s. El timeout efectivo de cada llamada es
# `min(timeout, deadline - ahora)` (U0 NFR-U0-23 (b)). Ninguna cadena supera los 10 s de la SPA.
DEADLINE_BUDGET_SECONDS: Final = 9.0
SPA_API_TIMEOUT_SECONDS: Final = 10.0

# Replicas del BFF con las que se dimensionan las conexiones (P-U10-04, «Conexiones con 6 réplicas»).
REPLICAS: Final = 6

# case: lecturas.
CASE_READ_TIMEOUT_SECONDS: Final = 1.5
# case: escrituras. Peor caso de U8 ~ 2,5 s (timeout de case hacia el registro) + la base: 4 s (antes 3 s).
CASE_WRITE_TIMEOUT_SECONDS: Final = 4.0
# governance: lecturas y transiciones con firma (append sincrono al registro, 2,5 s).
GOVERNANCE_READ_TIMEOUT_SECONDS: Final = 1.5
GOVERNANCE_WRITE_TIMEOUT_SECONDS: Final = 4.0
# registry.
REGISTRY_DOSSIER_TIMEOUT_SECONDS: Final = 5.0
REGISTRY_INTEGRITY_TIMEOUT_SECONDS: Final = 3.0
# explainability.
EXPLAINABILITY_SUMMARY_TIMEOUT_SECONDS: Final = 2.0
# bias.
BIAS_DASHBOARD_TIMEOUT_SECONDS: Final = 5.0
BIAS_READ_TIMEOUT_SECONDS: Final = 1.5

# Conexiones por replica y por destino; las de un destino se comparten entre sus operaciones.
CONNECTIONS_PER_REPLICA: Final = MappingProxyType(
    {
        "case": 20,
        "governance": 10,
        "registry": 5,
        "explainability": 5,
        "bias": 5,
    }
)

# Timeout por operacion, con la clave «destino.operacion» (P-U10-04).
OPERATION_TIMEOUT_SECONDS: Final = MappingProxyType(
    {
        "case.list_cases": CASE_READ_TIMEOUT_SECONDS,
        "case.get_case": CASE_READ_TIMEOUT_SECONDS,
        "case.list_persistent_failures": CASE_READ_TIMEOUT_SECONDS,
        "case.record_decision": CASE_WRITE_TIMEOUT_SECONDS,
        "case.create_manual_application": CASE_WRITE_TIMEOUT_SECONDS,
        "case.record_explanation_view": CASE_WRITE_TIMEOUT_SECONDS,
        "case.retry_case": CASE_WRITE_TIMEOUT_SECONDS,
        "governance.read": GOVERNANCE_READ_TIMEOUT_SECONDS,
        "governance.transition": GOVERNANCE_WRITE_TIMEOUT_SECONDS,
        "registry.get_case_dossier": REGISTRY_DOSSIER_TIMEOUT_SECONDS,
        "registry.run_integrity_check": REGISTRY_INTEGRITY_TIMEOUT_SECONDS,
        "registry.get_integrity_check": REGISTRY_INTEGRITY_TIMEOUT_SECONDS,
        "explainability.applicant_summary": EXPLAINABILITY_SUMMARY_TIMEOUT_SECONDS,
        "bias.get_dashboard": BIAS_DASHBOARD_TIMEOUT_SECONDS,
        "bias.list_freezes": BIAS_READ_TIMEOUT_SECONDS,
        "bias.get_context_package": BIAS_READ_TIMEOUT_SECONDS,
    }
)


def total_connections(destination: str) -> int:
    """Conexiones hacia un destino con todas las replicas: 120 case, 60 governance, 30 los demas."""
    return CONNECTIONS_PER_REPLICA[destination] * REPLICAS
