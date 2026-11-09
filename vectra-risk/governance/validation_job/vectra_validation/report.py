"""Arma el `ValidationReport` (F32) y lo envia con `private_key_jwt` (F50)."""

import asyncio
from typing import Protocol

import httpx
from vectra_common.service_token import ServiceTokenProvider
from vectra_contracts.models.governance import SyncCheck, ValidationReport
from vectra_contracts.models.monitoring import InitialDisparity

from vectra_validation.errors import ValidationJobError
from vectra_validation.metrics import decimal4
from vectra_validation.templates import DISCLAIMER

SEND_TIMEOUT = 10.0


class ReportSender(Protocol):
    def send(self, model_version_id: str, report: ValidationReport) -> None: ...


def build_report(
    auc: float, auc_target: str, disparity: InitialDisparity, sync: SyncCheck, dataset_ref: str
) -> ValidationReport:
    """`auc_meets_target` compara los valores ya redondeados a 4 decimales, los que lee el CRO."""
    auc_text = decimal4(auc)
    return ValidationReport(
        auc_roc=auc_text,
        auc_target=auc_target,
        auc_meets_target=float(auc_text) >= float(auc_target),
        initial_disparity=disparity,
        sync_check=sync,
        dataset_ref=dataset_ref,
        disclaimer=DISCLAIMER,
    )


class HttpReportSender:
    """`PUT /v1/models/{id}/validation-report` con el token de servicio del cliente `model-validation-job` (scope `governance:validation-report`)."""

    def __init__(
        self,
        base_url: str,
        tokens: ServiceTokenProvider,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._tokens = tokens
        self._client = httpx.Client(base_url=base_url, timeout=httpx.Timeout(SEND_TIMEOUT), transport=transport)

    def send(self, model_version_id: str, report: ValidationReport) -> None:
        try:
            token = asyncio.run(self._tokens.token())
            response = self._client.put(
                f"/v1/models/{model_version_id}/validation-report",
                content=report.model_dump_json(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        except Exception as error:  # noqa: BLE001  # cualquier fallo de token o red: el Job termina sin informe
            raise ValidationJobError("report_not_sent") from error
        if response.status_code not in (200, 204):
            raise ValidationJobError("report_rejected")
