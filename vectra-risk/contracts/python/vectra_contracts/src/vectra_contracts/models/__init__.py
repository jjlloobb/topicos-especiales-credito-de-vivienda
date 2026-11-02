"""Tipos del contrato."""

import typing
from importlib import import_module as _import_module
from typing import Any as _Any

from vectra_contracts.models.application import *  # noqa: F403
from vectra_contracts.models.base import *  # noqa: F403
from vectra_contracts.models.explanation import *  # noqa: F403
from vectra_contracts.models.features import *  # noqa: F403
from vectra_contracts.models.governance import *  # noqa: F403
from vectra_contracts.models.monitoring import *  # noqa: F403
from vectra_contracts.models.registry import *  # noqa: F403

if typing.TYPE_CHECKING:
    from vectra_contracts.models import api  # noqa: F401
    from vectra_contracts.models.api import *  # noqa: F403

del typing  # solo el guard; `from ... import *` y `dir()` no lo exponen

# `models.api` importa `outcome`, y `outcome` importa `models.base` y otros: si este paquete cargara
# `api` al importarse, el ciclo `outcome -> models -> api -> outcome` dependeria del primer import.
# `api` y los nombres que solo le pertenecen se resuelven de forma perezosa (PEP 562). La API publica
# (`import *`, `dir()`, atributos) es la misma que cuando `api` se cargaba al importar el paquete;
# `tests/unit/test_models_lazy_api.py` la compara contra lo que `api` y los submodulos definen.
_LAZY_API_NAMES = (
    "ApplicantFactor",
    "ApplicantSummary",
    "ApplicantSummaryRequest",
    "CaseDetail",
    "ClientErrorReport",
    "ConsoleDossier",
    "CreditStatus",
    "CreditStatusView",
    "DecisionIn",
    "DecisionRef",
    "DecisionView",
    "Empty",
    "ExplainRequest",
    "InvalidParam",
    "Page",
    "PolicyInputs",
    "Principal",
    "Problem",
    "ProblemCode",
    "ProblemReason",
    "REASON_ALLOWED_CODE",
    "Recommendation",
    "Scope",
    "ScoringRequest",
    "SessionInfo",
    "check_justification",
    "check_used_factors",
)


def __getattr__(name: str) -> _Any:
    if name == "api" or name in _LAZY_API_NAMES:
        api = _import_module("vectra_contracts.models.api")
        value = api if name == "api" else getattr(api, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted({*(n for n in globals() if not n.startswith("_")), "api", *_LAZY_API_NAMES})


def __dir__() -> list[str]:
    return sorted({*globals(), "api", *_LAZY_API_NAMES})
