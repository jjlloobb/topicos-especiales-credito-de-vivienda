"""`model-validation-job`, modo `validacion` (Paso 13; BR-U4-07, US-202): AUC, disparidad inicial real de U9, sincronia e informe por F32."""

import json
from decimal import Decimal
from typing import Any

import httpx
import numpy as np
import pytest
import vectra_disparity
from tools.forbidden_phrases import find_violations, load_patterns
from validation_support import (
    BASE_FEATURES,
    DATASET,
    EVALUATED_ON,
    MANIFEST,
    OTHER_VERSION,
    VERSION,
    CapturingSender,
    dataset,
    job_config,
    onnx_bytes,
    package,
    rows,
    xgboost_bytes,
)
from vectra_common.service_token import ServiceTokenProvider
from vectra_contracts.models.governance import SyncCheck, ValidationReport
from vectra_contracts.models.monitoring import AttributeResult, InitialDisparity
from vectra_validation import disparity as disparity_module
from vectra_validation.errors import ValidationJobError
from vectra_validation.metrics import auc_roc
from vectra_validation.models import load_model
from vectra_validation.report import HttpReportSender, build_report
from vectra_validation.run import main, validate
from vectra_validation.s3 import S3Reader
from vectra_validation.sync import sync_check
from vectra_validation.templates import DISCLAIMER, TEMPLATES

DATA = rows()


def onnx_run(**over: Any) -> tuple[Any, CapturingSender, ValidationReport]:
    uri, store = package("predictor.onnx", onnx_bytes(), DATA)
    sender = CapturingSender()
    config = job_config(uri, **over)
    report = validate(config, store, sender, EVALUATED_ON)
    return store, sender, report


def xgboost_run(**over: Any) -> tuple[Any, CapturingSender, ValidationReport]:
    uri, store = package("predictor.json", xgboost_bytes(DATA), DATA)
    sender = CapturingSender()
    report = validate(job_config(uri, **over), store, sender, EVALUATED_ON)
    return store, sender, report


# --- sincronia -------------------------------------------------------------------------------------------------------------


def test_an_onnx_model_with_an_explainer_that_produces_no_vectors_fails_the_sync_check() -> None:
    _, sender, report = onnx_run()
    assert report.sync_check.passed is False
    assert report.sync_check.failure_reason == "explainer_no_vectors"
    assert sender.sent == [(VERSION, report)]  # el informe se envia igual: es lo que lleva a `validacion_fallida` (BR-U4-07)


def test_a_real_xgboost_package_passes_the_sync_check_over_the_sampled_rows() -> None:
    _, _, report = xgboost_run()
    assert report.sync_check.passed is True and report.sync_check.failure_reason is None
    assert report.sync_check.samples_checked == 200
    assert report.sync_check.predictor_version == report.sync_check.explainer_version == VERSION


def test_two_versions_in_the_package_fail_the_sync_check() -> None:
    uri, store = package("predictor.json", xgboost_bytes(DATA), DATA, predictor_version=OTHER_VERSION)
    report = validate(job_config(uri), store, CapturingSender(), EVALUATED_ON)
    assert (report.sync_check.passed, report.sync_check.failure_reason) == (False, "version_mismatch")


def test_contributions_that_do_not_add_up_to_the_margin_fail_the_sync_check() -> None:
    matrix = dataset(DATA).matrix

    class Skewed:
        def contributions(self, m: Any) -> Any:
            return np.ones((m.shape[0], m.shape[1] + 1))

        def margin(self, m: Any) -> Any:
            return np.zeros(m.shape[0])

    result = sync_check(Skewed(), Skewed(), matrix, VERSION, VERSION)  # type: ignore[arg-type]
    assert (result.passed, result.failure_reason) == (False, "margin_mismatch")


# --- AUC -------------------------------------------------------------------------------------------------------------------


def test_auc_roc_matches_known_values_and_counts_ties_as_half() -> None:
    assert auc_roc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == 0.75
    assert auc_roc([0, 1], [0.5, 0.5]) == 0.5
    assert auc_roc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0


def test_auc_is_undefined_with_a_single_class() -> None:
    with pytest.raises(ValidationJobError, match="auc_undefined_single_class"):
        auc_roc([0, 0, 0], [0.1, 0.2, 0.3])


def test_auc_meets_target_is_false_when_the_auc_is_below_the_target() -> None:
    _, _, report = xgboost_run(auc_target="0.9999")
    assert Decimal(report.auc_roc) < Decimal(report.auc_target)
    assert report.auc_meets_target is False
    assert report.sync_check.passed is True  # el AUC se informa; solo la sincronia bloquea (BR-U4-07)


def test_auc_meets_target_is_true_at_the_target_and_above() -> None:
    d = dataset(DATA)
    base = build_report(0.8500, "0.8500", _any_disparity(), _sync_ok(), DATASET)
    assert base.auc_meets_target is True and base.auc_roc == "0.8500"
    assert build_report(0.84994, "0.8500", _any_disparity(), _sync_ok(), DATASET).auc_meets_target is False
    assert d.matrix.shape[0] == len(DATA)


def _sync_ok() -> SyncCheck:
    return SyncCheck(passed=True, predictor_version="v", explainer_version="v", samples_checked=1)


def _any_disparity() -> InitialDisparity:
    return InitialDisparity(attributes=[])


# --- disparidad inicial: la libreria real de U9 ----------------------------------------------------------------------------


def test_initial_disparity_is_the_one_the_u9_library_computes_directly() -> None:
    _, _, report = xgboost_run()
    d = dataset(DATA)
    uri, store = package("predictor.json", xgboost_bytes(DATA), DATA)
    model = load_model("xgboost_json", store.read(uri), tuple(BASE_FEATURES))
    probabilities = model.probability(d.matrix)
    records = [
        {**labels, "outcome": "favorable" if p < 0.08 else "desfavorable"}
        for labels, p in zip(d.monitoring, probabilities, strict=True)
    ]
    counts = vectra_disparity.counts_from_records(records)
    expected = [
        AttributeResult.model_validate(vectra_disparity.to_dict(vectra_disparity.disparity_by_band(counts, a, 30)))
        for a in vectra_disparity.ATTRIBUTES
    ]
    assert report.initial_disparity.attributes == expected
    top = vectra_disparity.model_aggregate(vectra_disparity.disparity_by_band(counts, a, 30) for a in vectra_disparity.ATTRIBUTES)
    assert top is not None
    assert report.initial_disparity.model_aggregate == str(top[1])
    assert report.initial_disparity.trigger_attribute == top[0]
    assert (report.initial_disparity.n_min, report.initial_disparity.threshold_pp) == (30, "5.0000")


def test_the_job_uses_the_real_library_and_not_a_double() -> None:
    assert disparity_module.disparity_by_band is vectra_disparity.disparity_by_band
    assert disparity_module.counts_from_records is vectra_disparity.counts_from_records
    assert disparity_module.aggregate_lower_limit is vectra_disparity.aggregate_lower_limit


# --- informe ---------------------------------------------------------------------------------------------------------------


def test_the_report_templates_pass_the_single_forbidden_phrase_list_of_u0() -> None:
    patterns = load_patterns()
    assert DISCLAIMER and TEMPLATES
    for text in TEMPLATES:
        assert find_violations(text, patterns) == []
    _, _, report = xgboost_run()
    assert find_violations(report.model_dump_json(), patterns) == []


def test_the_forbidden_phrase_check_would_catch_a_bad_template() -> None:
    assert find_violations("El modelo esta libre de sesgo", load_patterns()) != []


def test_the_report_sent_over_f32_carries_the_disclaimer() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    async def poster(url: str, data: Any, timeout: float) -> Any:
        return {"access_token": "tok-1", "expires_in": 60}

    tokens = ServiceTokenProvider(
        "model-validation-job", "https://keycloak/token", _ec_key(), "governance-service", ("governance:validation-report",), poster=poster
    )
    sender = HttpReportSender("http://governance", tokens, transport=httpx.MockTransport(handler))
    _, memory_sender, report = onnx_run()
    sender.send(VERSION, report)
    request = seen[0]
    assert (request.method, request.url.path) == ("PUT", f"/v1/models/{VERSION}/validation-report")
    assert request.headers["authorization"] == "Bearer tok-1"
    body = ValidationReport.model_validate_json(request.content)
    assert body.disclaimer == DISCLAIMER and body == memory_sender.sent[0][1]


def test_a_rejected_report_makes_the_job_fail() -> None:
    async def poster(url: str, data: Any, timeout: float) -> Any:
        return {"access_token": "t", "expires_in": 60}

    tokens = ServiceTokenProvider("c", "https://k/token", _ec_key(), "a", ("s",), poster=poster)
    sender = HttpReportSender("http://g", tokens, transport=httpx.MockTransport(lambda r: httpx.Response(409)))
    _, _, report = onnx_run()
    with pytest.raises(ValidationJobError, match="report_rejected"):
        sender.send(VERSION, report)


def _ec_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


# --- source_comparison: fuera de esta tarea ---------------------------------------------------------------------------------


def test_source_comparison_ends_with_an_explicit_error_and_sends_nothing() -> None:
    uri, store = package("predictor.json", xgboost_bytes(DATA), DATA)
    sender = CapturingSender()
    with pytest.raises(ValidationJobError, match="mode_not_supported"):
        validate(job_config(uri, mode="source_comparison"), store, sender, EVALUATED_ON)
    assert sender.sent == [] and store.reads == []


def test_main_exits_with_1_on_source_comparison_and_on_a_missing_variable(capsys: pytest.CaptureFixture[str]) -> None:
    env = _env(VECTRA_JOB_MODE="source_comparison")
    assert main(env) == 1
    assert "mode_not_supported" in capsys.readouterr().err
    del env["VECTRA_RUN_ID"]
    assert main(env) == 1
    assert "missing_env:VECTRA_RUN_ID" in capsys.readouterr().err


def _env(**over: str) -> dict[str, str]:
    base = {
        "VECTRA_JOB_MODE": "validacion", "VECTRA_RUN_ID": "r", "VECTRA_MODEL_VERSION_ID": VERSION, "VECTRA_MANIFEST_URI": MANIFEST,
        "VECTRA_ARTIFACT_URI": "s3://b/predictor.json", "VECTRA_EXPLAINER_URI": "s3://b/explainer.json", "VECTRA_DATASET_REF": DATASET,
        "VECTRA_GOVERNANCE_URL": "http://g", "VECTRA_S3_ENDPOINT": "http://minio:9000", "VECTRA_S3_ACCESS_KEY": "a",
        "VECTRA_S3_SECRET_KEY": "s", "VECTRA_TOKEN_URL": "https://k/token", "VECTRA_CLIENT_KEY_PATH": "/nonexistent",
    }
    return {**base, **over}


# --- lectura de objetos (F31) -----------------------------------------------------------------------------------------------


def test_the_s3_reader_signs_a_get_with_sigv4_and_returns_the_bytes() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"data")

    reader = S3Reader("http://minio:9000", "validation-readonly", "s3cret", transport=httpx.MockTransport(handler))
    assert reader.read("s3://validation-datasets/mv/validation.parquet") == b"data"
    request = seen[0]
    assert request.url.path == "/validation-datasets/mv/validation.parquet"
    auth = request.headers["authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=validation-readonly/")
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth and "s3cret" not in auth


@pytest.mark.parametrize("status", [403, 404, 500])
def test_the_s3_reader_hides_the_uri_and_the_body_on_failure(status: int) -> None:
    reader = S3Reader("http://m", "a", "s", transport=httpx.MockTransport(lambda r: httpx.Response(status, text="secret-body")))
    with pytest.raises(ValidationJobError) as caught:
        reader.read("s3://b/k")
    assert str(caught.value) == "object_unreadable"


def test_a_malformed_uri_is_refused_before_any_request() -> None:
    reader = S3Reader("http://m", "a", "s", transport=httpx.MockTransport(lambda r: pytest.fail("no request expected")))
    with pytest.raises(ValidationJobError, match="object_uri_invalid"):
        reader.read("https://evil/x")


def test_report_json_has_the_contract_fields() -> None:
    _, _, report = onnx_run()
    assert set(json.loads(report.model_dump_json())) == {
        "auc_roc", "auc_target", "auc_meets_target", "initial_disparity", "sync_check", "dataset_ref", "disclaimer"
    }
