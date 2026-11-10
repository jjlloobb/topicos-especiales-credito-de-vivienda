"""`model-validation-job`, modo `validacion` (Paso 13; BR-U4-07, US-202): AUC, disparidad inicial real de U9, sincronia e informe por F32."""

import json
from decimal import Decimal
from typing import Any

import httpx
import numpy as np
import pytest
import vectra_disparity
from tools.forbidden_phrases import find_violations, load_patterns
from vectra_contracts.models.governance import PolicyDraft
from validation_support import (
    DATASET,
    EVALUATED_ON,
    MANIFEST,
    OTHER_VERSION,
    VERSION,
    CapturingSender,
    dataset,
    envelope_bytes,
    job_config,
    onnx_bytes,
    package,
    policy,
    rows,
    xgboost_bytes,
)
from vectra_common.service_token import ServiceTokenProvider
from vectra_contracts.models.governance import SyncCheck, ValidationReport
from vectra_contracts.models.monitoring import InitialDisparity
from vectra_validation import disparity as disparity_module
from vectra_validation.confidence import confidence, parse_envelope
from vectra_validation.disparity import initial_disparity
from vectra_validation.outcome import outcome_of
from vectra_validation.errors import ValidationJobError
from vectra_validation.metrics import auc_roc
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


# --- codificacion por nombre (F-01 de la ronda 2 de U04-T05) ------------------------------------------------------------------


def test_the_job_matrix_is_the_one_u5_trains_with_and_proposed_rate_is_numeric() -> None:
    """`proposed_rate_ea` llega como `CategoryFeature("0.1500")` desde U0, pero U5 la entrena numerica: el Job decide por nombre."""
    from vectra_reference.features import BASE_FEATURES, categorical_vocabulary, row_values
    from vectra_reference.train import encode
    from validation_support import CONFIG

    matrix = dataset(DATA).matrix
    column = BASE_FEATURES.index("proposed_rate_ea")
    assert (matrix[:, column] > 0).all()  # nunca -1
    expected = encode([row_values(r) for r in DATA], BASE_FEATURES, categorical_vocabulary(CONFIG))
    assert np.allclose(matrix, expected, atol=1e-9)


def test_with_a_model_trained_with_the_u5_encoding_the_job_auc_is_the_one_u5_measures() -> None:
    """Medicion de la ronda 2 de U04-T05: 6 000 filas de entrenamiento y 2 000 de validacion; U5 da 0,863 y el Job con -1 daba 0,848."""
    import xgboost as xgb
    from validation_support import CONFIG, parquet
    from vectra_reference.features import BASE_FEATURES, categorical_vocabulary, row_values
    from vectra_reference.train import encode

    data = rows(8000)
    train, validation = data[:6000], data[6000:]
    uri, store = package("predictor.json", xgboost_bytes(train), validation)
    store.objects[DATASET] = parquet(validation)
    report = validate(job_config(uri), store, CapturingSender(), EVALUATED_ON)
    booster = xgb.Booster()
    booster.load_model(bytearray(store.read(uri)))
    matrix = encode([row_values(r) for r in validation], BASE_FEATURES, categorical_vocabulary(CONFIG))
    u5_auc = auc_roc([int(r["default"]) for r in validation], booster.predict(xgb.DMatrix(matrix, feature_names=list(BASE_FEATURES))))
    print(f"AUC U5={u5_auc:.6f} Job={report.auc_roc}")  # noqa: T201
    assert abs(float(report.auc_roc) - u5_auc) < 1e-3


def test_with_the_real_u5_base_model_the_job_auc_matches_the_one_u5_computes_within_1e_3() -> None:
    import xgboost as xgb
    from validation_support import u5_base_release, u5_package_store
    from vectra_reference.features import categorical_vocabulary, read_rows as u5_read_rows, row_values
    from vectra_reference.train import encode

    out = u5_base_release()
    artifact, store, version = u5_package_store(out)
    sender = CapturingSender()
    report = validate(
        job_config(artifact, model_version_id=version, manifest_uri="s3://model-store/u5/manifest.json",
                   explainer_uri="s3://model-store/u5/explainer.json"),
        store, sender, EVALUATED_ON,
    )
    explainer = json.loads(store.read("s3://model-store/u5/explainer.json"))
    validation = u5_read_rows(out / "datasets" / "validation.parquet")
    booster = xgb.Booster()
    booster.load_model(bytearray(store.read(artifact)))
    order = explainer["feature_order"]
    matrix = encode([row_values(r) for r in validation], order, explainer["categorical_encoding"])
    u5_scores = booster.predict(xgb.DMatrix(matrix, feature_names=order))
    u5_auc = auc_roc([int(r["default"]) for r in validation], u5_scores)
    print(f"AUC U5={u5_auc:.6f} Job={report.auc_roc}")  # noqa: T201
    assert abs(float(report.auc_roc) - u5_auc) < 1e-3


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


def _labels(sexo: str) -> dict[str, str]:
    return {"sexo": sexo, "rango_edad": "46-55", "region": "caribe", "estrato": "2", "banda": "gt_30"}


def test_initial_disparity_counts_revision_requerida_as_not_favorable() -> None:
    """Caso a mano (BR-U9-01): F tiene 70 favorables y 30 `revision_requerida` de 100; M tiene 100 favorables de 100."""
    monitoring = [_labels("F")] * 100 + [_labels("M")] * 100
    outcomes = ["favorable"] * 70 + ["revision_requerida"] * 30 + ["favorable"] * 100
    result = initial_disparity(monitoring, outcomes, 30, "5.0000")
    sexo = next(a for a in result.attributes if a.attribute == "sexo")
    rates = {c.group: c.rate for c in sexo.cells if c.band == "gt_30"}
    assert rates == {"F": "0.7000", "M": "1.0000"}  # 70/100 y 100/100; con `p < cutoff` F valdria 1.0000 si las 30 tuvieran score bajo
    assert (result.trigger_attribute, result.model_aggregate, result.rule_met) == ("sexo", "0.3000", True)


def test_initial_disparity_gives_the_same_figure_when_a_review_is_replaced_by_an_unfavorable() -> None:
    monitoring = [_labels("F")] * 100 + [_labels("M")] * 100
    review = ["favorable"] * 70 + ["revision_requerida"] * 30 + ["favorable"] * 100
    unfavorable = ["favorable"] * 70 + ["desfavorable"] * 30 + ["favorable"] * 100
    assert initial_disparity(monitoring, review, 30, "5.0000") == initial_disparity(monitoring, unfavorable, 30, "5.0000")


# Casos a mano de BR-U7-04 y BR-U7-05. Cada fila: (descripcion, probabilidad, confianza, tasa, canal, politica, outcome esperado).
POLICY = policy()
CHANNELS = policy(channel_rules=[{"channel": "sucursal", "cutoff": "0.0500"}, {"channel": "digital", "cutoff": None}])
NORMATIVE_ENDED = policy(
    normative=[
        {
            "vis_max_property_value": 200_000_000,
            "usury_cap_ea": "0.2800",
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
            "source_ref": "sintetico",
        }
    ]
)
OUTCOME_CASES = [
    ("score bajo el corte", 0.05, "0.9000", "0.1500", "sucursal", POLICY, "favorable"),
    ("score igual al corte no es bajo", 0.08, "0.9000", "0.1500", "sucursal", POLICY, "desfavorable"),
    ("score sobre el corte", 0.30, "0.9000", "0.1500", "sucursal", POLICY, "desfavorable"),
    ("normativo nulo (sin lista) con score bajo", 0.01, "0.9000", "0.1500", "sucursal", policy(normative=[]), "revision_requerida"),
    ("normativo nulo (vigencia vencida) con score bajo", 0.01, "0.9000", "0.1500", "sucursal", NORMATIVE_ENDED, "revision_requerida"),
    ("tasa sobre la usura con score bajo", 0.01, "0.9000", "0.2801", "sucursal", POLICY, "revision_requerida"),
    ("tasa igual a la usura no es sobre", 0.01, "0.9000", "0.2800", "sucursal", POLICY, "favorable"),
    ("confianza bajo el minimo con score bajo", 0.01, "0.0299", "0.1500", "sucursal", POLICY, "revision_requerida"),
    ("confianza igual al minimo no es baja", 0.01, "0.0300", "0.1500", "sucursal", POLICY, "favorable"),
    ("las tres causas a la vez", 0.01, "0.0100", "0.3000", "sucursal", policy(normative=[]), "revision_requerida"),
    ("el corte del canal gana: 0,06 sobre 0,05 de sucursal", 0.06, "0.9000", "0.1500", "sucursal", CHANNELS, "desfavorable"),
    ("el corte del canal gana: 0,04 bajo 0,05 de sucursal", 0.04, "0.9000", "0.1500", "sucursal", CHANNELS, "favorable"),
    ("canal sin regla usa el general: 0,06 bajo 0,08", 0.06, "0.9000", "0.1500", "aliado_inmobiliario", CHANNELS, "favorable"),
    ("regla del canal sin corte usa el general", 0.06, "0.9000", "0.1500", "digital", CHANNELS, "favorable"),
]


@pytest.mark.parametrize(("why", "p", "conf", "rate", "channel", "pol", "expected"), OUTCOME_CASES)
def test_the_outcome_is_the_one_br_u7_04_and_br_u7_05_give(
    why: str, p: float, conf: str, rate: str, channel: str, pol: PolicyDraft, expected: str
) -> None:
    assert outcome_of(p, conf, rate, channel, pol, EVALUATED_ON) == expected, why


# Casos a mano de la confianza (BR-U5-12) sobre una envolvente de dos numericas y una categorica: media 0, covarianza identidad
# (la distancia de Mahalanobis es la euclidiana) y deciles 0, 1, 2 de esas distancias.
ENVELOPE = {
    "numeric": [{"name": "a", "p1": -1.0, "p99": 1.0}, {"name": "b", "p1": -1.0, "p99": 1.0}],
    "categories": {"c": ["x", "y"]},
    "mean": [0.0, 0.0],
    "covariance": [[1.0, 0.0], [0.0, 1.0]],
    "distance_quantiles": [0.0, 1.0, 2.0],
}


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"a": 0.0, "b": 0.0, "c": "x"}, "1.0000"),  # d = 0: F = 0, en rango
        ({"a": 1.0, "b": 0.0, "c": "y"}, "0.5000"),  # d = 1: F = 0,5, en rango
        ({"a": 0.5, "b": 0.0, "c": "x"}, "0.7500"),  # d = 0,5: F = 0,25
        ({"a": 5.0, "b": 0.0, "c": "x"}, "0.0000"),  # d = 5 sobre el maximo: F = 1; ademas una numerica fuera de rango
        ({"a": 0.0, "b": 0.0, "c": "z"}, "0.0000"),  # categoria no vista: 0
        ({"a": 1.5, "b": 0.0, "c": "x"}, "0.2500"),  # d = 1,5: c_dist = 0,25; c_rango = 0,5; el minimo es 0,25
    ],
)
def test_confidence_matches_hand_computed_values(values: dict[str, Any], expected: str) -> None:
    assert confidence(ENVELOPE, values) == expected


def test_confidence_accepts_numeric_values_given_as_text() -> None:
    assert confidence(ENVELOPE, {"a": "0.5", "b": "0", "c": "x"}) == "0.7500"


def test_confidence_without_a_feature_is_an_error_and_an_unreadable_envelope_too() -> None:
    with pytest.raises(ValidationJobError, match="feature_missing:b"):
        confidence(ENVELOPE, {"a": 0.0, "c": "x"})
    with pytest.raises(ValidationJobError, match="envelope_unreadable"):
        parse_envelope(b'{"numeric": []}')


def test_confidence_is_the_one_u5_publishes() -> None:
    """La copia del Job (la imagen no lleva `vectra_reference`) da lo mismo que la funcion de U5 sobre las mismas entradas."""
    from vectra_reference.envelope.confidence import confidence as u5_confidence

    envelope = json.loads(envelope_bytes(DATA))
    for row in dataset(DATA).values[:100]:
        assert confidence(envelope, row) == u5_confidence(envelope, row)


def test_the_job_gives_each_row_the_outcome_of_the_policy_and_not_the_score_below_the_cutoff() -> None:
    """Con la politica activa que fija el lanzador, una causa de `revision_requerida` deja a todos como no favorables (tasa 0)."""
    _, _, normal = xgboost_run()
    assert any(c.rate not in (None, "0.0000") for a in normal.initial_disparity.attributes for c in a.cells)
    for why, pol in (
        ("normativo nulo", policy(normative=[])),
        ("usura 0", policy(normative=[{**json.loads(POLICY.normative[0].model_dump_json()), "usury_cap_ea": "0.0000"}])),
    ):
        _, _, report = xgboost_run(policy=pol)
        rates = {c.rate for a in report.initial_disparity.attributes for c in a.cells if c.status == "suficiente"}
        assert rates == {"0.0000"}, why


def test_validate_passes_the_real_confidence_rate_and_channel_of_each_row_to_the_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    """NARANJA F-02 (ronda 2 de U04-T05): el cableado de `confidence`, tasa y canal en `validate` se comprueba fila a fila."""
    from vectra_validation import run as run_module

    seen: list[tuple[float, str, str, str]] = []
    real = run_module.outcome_of

    def spy(probability: float, conf: str, rate: str, channel: str, pol: PolicyDraft, on: Any) -> str:
        seen.append((probability, conf, rate, channel))
        return real(probability, conf, rate, channel, pol, on)

    monkeypatch.setattr(run_module, "outcome_of", spy)
    xgboost_run()
    envelope = parse_envelope(envelope_bytes(DATA))
    expected = [confidence(envelope, v) for v in dataset(DATA).values]
    assert len(seen) == len(DATA)
    assert [s[1] for s in seen] == expected
    assert len(set(expected)) > 1
    assert [s[2] for s in seen] == [str(r["proposed_rate_ea"]) for r in DATA]
    assert [s[3] for s in seen] == [r["channel"] for r in DATA]


def test_a_high_confidence_floor_changes_the_disparity_through_validate() -> None:
    """Punta a punta: un umbral de confianza alto manda a revision a las filas de confianza menor, y la tabla cambia."""
    _, _, base = xgboost_run()
    _, _, strict = xgboost_run(policy=policy(low_confidence_threshold="0.9999"))
    assert base.initial_disparity != strict.initial_disparity


def test_a_channel_cutoff_rule_changes_the_outcome_of_that_channel_only() -> None:
    _, _, base = xgboost_run()
    _, _, strict = xgboost_run(policy=policy(channel_rules=[{"channel": "digital", "cutoff": "0.0001"}]))
    assert base.initial_disparity != strict.initial_disparity


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
        "VECTRA_POLICY": policy().model_dump_json(),
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
