"""Lectura minima del Job de validacion (K01 `get`; P-U4-02, P-U4-03). Sin watch: una consulta por vencimiento.

El barrido de validaciones vencidas (`background.py`) pregunta por el Job solo para **registrar el motivo** del
`validacion_fallida`. El cliente real de Kubernetes y el lanzador del Job son del Paso 10 (U04-T04); aqui solo la interfaz
y la clasificacion, que no hacen E/S.
"""

from dataclasses import dataclass
from typing import Final, Literal, Protocol

JobReason = Literal["failed", "deadline", "sin informe"]
REASONS: Final = ("failed", "deadline", "sin informe")


@dataclass(frozen=True)
class JobInfo:
    """Lo que el barrido necesita del Job: si fallo y si lo cancelo el `activeDeadlineSeconds`."""

    failed: bool = False
    deadline_exceeded: bool = False


class JobReader(Protocol):
    def get(self, job_name: str) -> JobInfo | None:
        """El Job, o `None` si ya no existe (el TTL lo borro)."""
        ...


def reason_of(info: JobInfo | None) -> JobReason:
    """`deadline` si el Job vencio por su plazo; `failed` si fallo; si no, o si ya no existe, `sin informe` (BR-U4-05)."""
    if info is not None and info.deadline_exceeded:
        return "deadline"
    if info is not None and info.failed:
        return "failed"
    return "sin informe"
