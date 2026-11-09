"""Prueba de sincronia predictor <-> explicador (BR-U4-07): lo unico que bloquea (`sync_check.passed = false`)."""

import numpy as np
from vectra_contracts.models.governance import SyncCheck

from vectra_validation.models import Explainer, Matrix, Predictor

SAMPLES = 200
MARGIN_TOLERANCE = 1e-4  # NFR-U6-01: suma de contribuciones + sesgo = margen, tolerancia absoluta


def sync_check(
    predictor: Predictor,
    explainer: Explainer,
    matrix: Matrix,
    predictor_version: str,
    explainer_version: str,
    *,
    samples: int = SAMPLES,
    tolerance: float = MARGIN_TOLERANCE,
) -> SyncCheck:
    """Pasa si las dos piezas son de la misma version y, en las primeras `samples` filas, el explicador devuelve un vector por
    fila cuya suma (con el sesgo) reproduce el margen del predictor. Un explicador que no produce vectores no pasa."""
    sample = matrix[:samples]

    def result(passed: bool, reason: str | None = None) -> SyncCheck:
        return SyncCheck(
            passed=passed,
            predictor_version=predictor_version,
            explainer_version=explainer_version,
            samples_checked=int(sample.shape[0]),
            failure_reason=reason,
        )

    if predictor_version != explainer_version:
        return result(False, "version_mismatch")
    contributions = explainer.contributions(sample)
    if contributions is None or contributions.shape != (sample.shape[0], sample.shape[1] + 1):
        return result(False, "explainer_no_vectors")
    error = float(np.max(np.abs(contributions.sum(axis=1) - predictor.margin(sample))))
    if not error <= tolerance:  # `not <=` tambien atrapa NaN
        return result(False, "margin_mismatch")
    return result(True)
