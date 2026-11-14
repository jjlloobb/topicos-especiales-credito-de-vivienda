"""El estado de retoma de `rt2` como JSON (U12-T04, Paso 13): `Rt2State` y lo que guarda (fases pasadas, lote, `freeze`, mediciones) sale a un archivo y vuelve igual. Logica pura: sin E/S.

Solo se reconstruyen las clases de la lista cerrada `CLASSES`; un nombre desconocido es un error, no un `eval`. Nada de esto lleva datos del solicitante: son `case_id`, conteos, instantes y las lecturas del registro.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any, Final

from vectra_verification import rt2_latency, sampler
from vectra_verification.scenarios.outcome import SubOutcome
from vectra_verification.scenarios.rt2 import CellCheck, Rt2State, VersionState
from vectra_verification.simulator import RunReport

CLASSES: Final = {
    cls.__name__: cls
    for cls in (
        Rt2State,
        VersionState,
        CellCheck,
        SubOutcome,
        RunReport,
        sampler.CellReport,
        rt2_latency.Rt2Measurement,
    )
}


class ResumeError(Exception):
    """El estado guardado no se puede leer; el mensaje empieza por un codigo estable."""


def encode(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        found = {f.name: encode(getattr(value, f.name)) for f in fields(value)}
        return {"__dc__": type(value).__name__, **found}
    if isinstance(value, datetime):
        return {"__dt__": value.isoformat()}
    if isinstance(value, tuple):
        return {"__t__": [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, Mapping):
        return {"__d__": [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ResumeError(f"resume_type_unsupported:{type(value).__name__}")


def decode(value: Any) -> Any:
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if "__dt__" in value:
        return datetime.fromisoformat(value["__dt__"])
    if "__t__" in value:
        return tuple(decode(v) for v in value["__t__"])
    if "__d__" in value:
        return {decode(k): decode(v) for k, v in value["__d__"]}
    if "__dc__" in value:
        cls = CLASSES.get(value["__dc__"])
        if cls is None:
            raise ResumeError(f"resume_class_unknown:{str(value['__dc__'])[:40]}")
        try:
            return cls(**{k: decode(v) for k, v in value.items() if k != "__dc__"})
        except TypeError:
            raise ResumeError(f"resume_shape:{cls.__name__}") from None
    raise ResumeError("resume_shape")
