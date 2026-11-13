"""Orquesta el Job en modo `validacion` (BR-U4-05, BR-U4-07) y su punto de entrada.

El Job solo lee (F31, model-store) y envia un informe (F32). El modo `source_comparison` es de otra tarea: aqui termina con
`mode_not_supported` y sin enviar nada.
"""

import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from vectra_common.service_token import ServiceTokenProvider
from vectra_contracts.models.features import FeatureSpec
from vectra_contracts.models.governance import ValidationReport

from vectra_validation.confidence import confidence, parse_envelope
from vectra_validation.config import JobConfig, from_env
from vectra_validation.disparity import initial_disparity
from vectra_validation.errors import ValidationJobError
from vectra_validation.features import build_dataset, read_rows
from vectra_validation.metrics import auc_roc
from vectra_validation.models import artifact_format, load_model, parse_explainer
from vectra_validation.outcome import outcome_of
from vectra_validation.report import HttpReportSender, ReportSender, build_report
from vectra_validation.s3 import S3Reader
from vectra_validation.sync import sync_check

SPEC_FILE = "feature_spec.json"
ENVELOPE_FILE = "domain_envelope.json"


class ObjectReader(Protocol):
    def read(self, uri: str) -> bytes: ...


def _sibling(manifest_uri: str, name: str) -> str:
    return manifest_uri.rsplit("/", 1)[0] + "/" + name


def _manifest_version(manifest: bytes, artifact_uri: str) -> str:
    """El `model_version_id` que el manifiesto asigna al archivo del predictor (cada entrada lleva el suyo, BR-U5-09)."""
    try:
        data = json.loads(manifest)
        name = artifact_uri.rsplit("/", 1)[1]
        entries = {entry["name"]: entry for entry in data["files"]}
        return str(entries[name]["model_version_id"])
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise ValidationJobError("manifest_unreadable") from error


def validate(config: JobConfig, store: ObjectReader, sender: ReportSender, evaluated_on: date) -> ValidationReport:
    """Puntua el dataset, arma el informe y lo envia. Devuelve lo enviado."""
    if config.mode != "validacion":
        raise ValidationJobError("mode_not_supported")
    manifest = store.read(config.manifest_uri)
    explainer_spec = parse_explainer(store.read(config.explainer_uri))
    spec = FeatureSpec.model_validate_json(store.read(_sibling(config.manifest_uri, SPEC_FILE)))
    envelope = parse_envelope(store.read(_sibling(config.manifest_uri, ENVELOPE_FILE)))
    model = load_model(
        artifact_format(config.artifact_uri), store.read(config.artifact_uri), explainer_spec.feature_order
    )
    dataset = build_dataset(
        read_rows(store.read(config.dataset_ref)),
        spec,
        explainer_spec.feature_order,
        explainer_spec.categorical_encoding,
        evaluated_on,
    )
    probabilities = model.probability(dataset.matrix)
    outcomes = [
        outcome_of(float(p), confidence(envelope, v), rate, channel, config.policy, evaluated_on)
        for p, v, rate, channel in zip(probabilities, dataset.values, dataset.proposed_rates, dataset.channels, strict=True)
    ]
    report = build_report(
        auc_roc(dataset.defaults, probabilities),
        config.auc_target,
        initial_disparity(dataset.monitoring, outcomes, config.n_min, config.threshold_pp),
        sync_check(
            model,
            model,
            dataset.matrix,
            _manifest_version(manifest, config.artifact_uri),
            explainer_spec.model_version_id,
        ),
        config.dataset_ref,
    )
    sender.send(config.model_version_id, report)
    return report


def token_provider(config: JobConfig) -> ServiceTokenProvider:
    """El proveedor real de tokens (`private_key_jwt`); sin `poster` inyectado, como en el clúster."""
    return ServiceTokenProvider(
        config.client_id,
        config.token_url,
        Path(config.key_path).read_text(encoding="utf-8"),
        config.audience,
        (config.scope,),
        assertion_audience=config.assertion_audience,
        key_id=config.key_id,
    )


def main(env: dict[str, str] | None = None, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> int:
    """Codigo 0 si el informe se envio; 1 si no (el mensaje es un codigo estable, sin datos del dataset)."""
    try:
        config = from_env(dict(os.environ if env is None else env))
        if config.mode != "validacion":
            raise ValidationJobError("mode_not_supported")
        tokens = token_provider(config)
        evaluated_on = date.fromisoformat(config.evaluated_on) if config.evaluated_on else clock().date()
        validate(
            config,
            S3Reader(config.s3_endpoint, config.s3_access_key, config.s3_secret_key),
            HttpReportSender(config.governance_url, tokens),
            evaluated_on,
        )
    except ValidationJobError as error:
        print(f"validation_job_failed: {error}", file=sys.stderr)  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
