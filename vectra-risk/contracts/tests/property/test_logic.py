"""Propiedades de la logica de negocio: PBT-U0-01..06, 10..13, 15, 16."""

import json
from datetime import timedelta
from decimal import Decimal, localcontext

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from strategies import domain as d

from vectra_contracts.catalog import Decision, ExplainerError, FailClosedCause, FinalOutcome, LocalCause, Outcome, RegistryError, ServingState
from vectra_contracts.dane import DEPARTMENTS
from vectra_contracts.dictionary import covers
from vectra_contracts.finance import installment, quantize4
from vectra_contracts.labels import age_range, payment_band, region_of
from vectra_contracts.models.api import DecisionIn
from vectra_contracts.models.application import ApplicationIn
from vectra_contracts.models.explanation import FailClosed, PolicyResult, Prediction, RegistryAck
from vectra_contracts.models.features import FeatureVector
from vectra_contracts.models.registry import FailClosedPayload, RegistryEntryIn
from vectra_contracts.outcome import InvalidModelOutput, Ready, Recommendation, RecommendResult, build_outcome, check_preconditions, quantize_prediction, quantize_probability
from vectra_contracts.validation import check_business_time

PRED = Prediction(model_version_id="mv-1", score="0.5000", confidence="0.9000")
POL = PolicyResult(policy_version_id="p", outcome=Outcome.FAVORABLE, reasons=[])
ACK = RegistryAck(registry_entry_id="1", seq=1, recorded_at=d.NOW)


def oracle(state, requested, serving, pred, pol, expl, dic, reg):
    """Implementacion de referencia: la tabla de BR-U0-02 escrita como lista de filas."""
    disc = state is ServingState.ACTIVO and requested != serving
    invalid = isinstance(pred, InvalidModelOutput)
    is_expl = expl is not None and not isinstance(expl, ExplainerError)
    version = pred.model_version_id if isinstance(pred, Prediction) else None
    rows = [
        (FailClosedCause.MODEL_FROZEN, state is ServingState.CONGELADO),
        (FailClosedCause.SERVING_CONFIG_UNAVAILABLE, state is ServingState.NO_DISPONIBLE or (not disc and (pred is None or (pol is None and not invalid)))),
        (FailClosedCause.MODEL_OUTPUT_INVALID, invalid),
        (FailClosedCause.TIMEOUT, expl is ExplainerError.TIMEOUT),
        (FailClosedCause.EXPLAINER_UNAVAILABLE, expl is ExplainerError.UNAVAILABLE or (expl is None and not disc)),
        (FailClosedCause.EXPLAINER_ERROR, expl is ExplainerError.ERROR),
        (FailClosedCause.VERSION_MISMATCH, expl is ExplainerError.VERSION_MISMATCH or (is_expl and expl.model_version_id != version) or (dic is not None and dic.model_version_id != version) or disc),
        (FailClosedCause.FEATURE_DICTIONARY_INCOMPLETE, expl is ExplainerError.FEATURE_DICTIONARY_INCOMPLETE or (dic is None and not disc) or (is_expl and dic is not None and not covers(dic, expl.shap_vector))),
        (FailClosedCause.FACTUALITY_FAILED, expl is ExplainerError.FACTUALITY_FAILED),
        (FailClosedCause.REGISTRY_UNAVAILABLE, not isinstance(reg, RegistryAck)),
    ]
    return next((cause for cause, applies in rows if applies), None)


explainers = st.one_of(st.none(), d.explainer_errors, st.sampled_from([d.explanation(), d.explanation("mv-2"), d.explanation(feature_ids=("z",))]))
dictionaries = st.sampled_from([None, d.dictionary(), d.dictionary("mv-2")])
predictions = st.sampled_from([None, PRED, InvalidModelOutput(model_version_id="mv-1")])


@given(d.serving_states, st.sampled_from(["mv-1", "mv-2"]), st.sampled_from(["mv-1", "mv-2", None]), predictions, st.sampled_from([None, POL]), explainers, dictionaries, st.sampled_from([ACK, RegistryError.UNAVAILABLE, None]))
def test_pbt_u0_01_oracle(state, requested, serving, pred, pol, expl, dic, reg):
    first = check_preconditions(d.CASE, state, requested, serving, pred, pol, expl, dic, d.SHA, d.NOW)
    result = build_outcome(first, reg, d.NOW) if isinstance(first, Ready) else first
    expected = oracle(state, requested, serving, pred, pol, expl, dic, reg)
    if expected is None:
        assert isinstance(result, Recommendation)
        assert (result.score, result.confidence) == (PRED.score, PRED.confidence)
        assert result.explanation == expl and result.policy_version_id == POL.policy_version_id
    else:
        assert isinstance(result, FailClosed) and result.cause is expected
        frozen = expected is FailClosedCause.MODEL_FROZEN
        assert (result.status == "modelo_congelado") == frozen and result.retryable != frozen


round_trip_cases = st.one_of(
    d.application_dicts().map(d.application_from),
    d.feature_vectors,
    d.monitoring_labels,
    st.builds(FailClosed, case_id=d.uuids, status=st.just("en_sincronizacion"), cause=st.sampled_from([c for c in FailClosedCause if c is not FailClosedCause.MODEL_FROZEN]), retryable=st.just(True), occurred_at=st.just(d.NOW)),
    st.builds(DecisionIn, decision=st.just(Decision.SIGUE), final_outcome=st.sampled_from(list(FinalOutcome)), used_factors=st.just(["ninguno"]), justification=st.just("")),
    st.builds(Prediction, model_version_id=st.just("m"), score=d.decimal4, confidence=d.decimal4),
)


@given(round_trip_cases)
def test_pbt_u0_02_round_trip(value):
    assert type(value).model_validate_json(value.model_dump_json()) == value


@given(d.decimal4, d.decimal4)
def test_pbt_u0_02_recommend_result_round_trip(score, confidence):
    prediction = Prediction(model_version_id="mv-1", score=score, confidence=confidence)
    ready = check_preconditions(d.CASE, ServingState.ACTIVO, "mv-1", "mv-1", prediction, POL, d.explanation(), d.dictionary(), d.SHA, d.NOW)
    result = build_outcome(ready, ACK, d.NOW)
    assert RecommendResult.from_wire(result.model_dump_json()) == result


def high_precision(amount, rate, term):
    with localcontext() as ctx:
        ctx.prec = 50
        i = (1 + rate) ** (Decimal(1) / 12) - 1
        return amount * i / (1 - (1 + i) ** (-term))


amounts = st.integers(1, 10**12)
terms = st.integers(12, 360)
rates = st.integers(1, 9999).map(lambda n: Decimal(n) / 10000)


@given(amounts, rates, terms)
def test_pbt_u0_03_installment_oracle(amount, rate, term):
    assert abs(Decimal(installment(amount, rate, term)) - high_precision(Decimal(amount), rate, term)) <= 1


@given(amounts, amounts, rates, rates, terms, terms)
def test_pbt_u0_04_monotonic(a1, a2, r1, r2, t1, t2):
    low_a, high_a = sorted((a1, a2))
    low_r, high_r = sorted((r1, r2))
    low_t, high_t = sorted((t1, t2))
    assert installment(low_a, r1, t1) <= installment(high_a, r1, t1)
    assert installment(a1, low_r, t1) <= installment(a1, high_r, t1)
    assert installment(a1, r1, low_t) >= installment(a1, r1, high_t)


@given(st.decimals(allow_nan=False, allow_infinity=False, min_value=-(10**9), max_value=10**9))
def test_pbt_u0_05_quantize_idempotent(x):
    assert quantize4(quantize4(x)) == quantize4(x)


@given(st.integers(18, 120))
def test_pbt_u0_06_age_total(age):
    assert age_range(age) in {"18-25", "26-35", "36-45", "46-55", "56-65", "66+"}


def test_pbt_u0_06_departments_have_region():
    assert all(region_of(code) for code in DEPARTMENTS)


@given(st.integers(0, 10000), st.integers(0, 10000))
def test_pbt_u0_06_band_monotonic(a, b):
    order = {"lt_20": 0, "20_30": 1, "gt_30": 2}
    low, high = sorted((a, b))
    assert order[payment_band(Decimal(low) / 10000)] <= order[payment_band(Decimal(high) / 10000)]


@given(st.sets(st.sampled_from("abcd")), st.sets(st.sampled_from("abcd"), min_size=0))
def test_pbt_u0_10_covers(dict_ids, vector_ids):
    dic = d.dictionary(feature_ids=tuple(sorted(dict_ids)))
    vector = d.explanation(feature_ids=tuple(sorted(vector_ids))).shap_vector
    assert covers(dic, vector) == (vector_ids <= dict_ids)


MUTATIONS = {
    "term_months": 11, "employment_months": 721, "max_days_past_due_12m": 366, "monthly_income": 10**12 + 7,
    "proposed_rate_ea": "1.5000", "department_code": "98", "phone": "secreto-987", "email": "secreto-sin-arroba",
    "document_number": "SECRETO*", "property_condition": "regalada", "sex": "X",
}


@given(d.application_dicts(), st.sampled_from(sorted(MUTATIONS)))
def test_pbt_u0_11_mutations_fail_without_echoing_value(data, field):
    ApplicationIn.model_validate_json(json.dumps(data))
    try:
        ApplicationIn.model_validate_json(json.dumps({**data, field: MUTATIONS[field]}))
    except ValidationError as exc:
        reported = json.dumps(exc.errors(include_input=False, include_url=False, include_context=False))
        assert str(MUTATIONS[field]) not in reported
    else:
        raise AssertionError("la mutacion debia fallar")


@given(st.floats(allow_nan=True, allow_infinity=True), st.floats(allow_nan=False, min_value=0, max_value=1))
def test_pbt_u0_12_quantization(value, other):
    quantized = quantize_probability(value)
    if value == value and value not in (float("inf"), float("-inf")) and 0.0 <= value <= 1.0:
        assert quantized is not None and Decimal(0) <= Decimal(quantized) <= Decimal(1)
        low, high = sorted((value, other))
        assert Decimal(quantize_probability(low)) <= Decimal(quantize_probability(high))
    else:
        assert quantized is None
        result = check_preconditions(d.CASE, ServingState.ACTIVO, "m", "m", quantize_prediction("m", value, 0.5), None, None, None, d.SHA, d.NOW)
        assert result.cause is FailClosedCause.MODEL_OUTPUT_INVALID


FORBIDDEN = ["full_name", "document_number", "birth_date", "phone", "email", "address", "municipality_code", "free_text"]


@given(st.sampled_from(FORBIDDEN), st.integers(0, 2))
def test_pbt_u0_13_forbidden_keys_any_level(key, depth):
    injected: object = {key: "x"}
    for _ in range(depth):
        injected = {"n": [injected]}
    entry = {
        "entry_type": "model_event",
        "actor": {"kind": "system", "id": "s"},
        "occurred_at": "2026-10-31T12:00:00Z",
        "correlation_id": "0" * 32,
        "idempotency_key": str(d.CASE),
        "payload": {"event": "registrado", "details": {"d": injected}},
    }
    try:
        RegistryEntryIn.model_validate_json(json.dumps(entry))
    except ValidationError:
        pass
    else:
        raise AssertionError("debia rechazarse")
    try:
        FeatureVector.model_validate_json(json.dumps({"features": {key: {"type": "category", "value": "x"}}}))
    except ValidationError:
        pass
    else:
        raise AssertionError("debia rechazarse")


OFFSETS = st.sampled_from([timedelta(0), timedelta(milliseconds=1), timedelta(milliseconds=-1), timedelta(days=7), timedelta(days=7, milliseconds=1), timedelta(days=7, milliseconds=-1), timedelta(hours=-1), timedelta(days=30)])


@given(st.sampled_from(["evaluated_at", "decided_at", "viewed_at", "frozen_at", "escalated_at"]), OFFSETS)
def test_pbt_u0_15_business_time_oracle(field, back):
    moment = d.NOW - back
    accepted = check_business_time({field: moment}, d.NOW) is None
    assert accepted == (moment <= d.NOW and moment >= d.NOW - timedelta(days=7))


@given(st.sampled_from([None, *FailClosedCause]), st.sampled_from([None, *LocalCause]), st.booleans(), st.booleans())
def test_pbt_u0_16_fail_closed_oracle(cause, local, retryable, escalated):
    data = {"cause": cause, "local_cause": local, "retryable": retryable, "attempt": 1, "escalated_at": "2026-10-31T12:00:00Z" if escalated else None}
    exactly_one = (cause is None) != (local is None)
    if local is not None:
        expected_retry = local is not LocalCause.SCORING_REJECTED
    else:
        expected_retry = cause is not FailClosedCause.MODEL_FROZEN
    expected = exactly_one and (local is None or escalated) and retryable == expected_retry
    try:
        FailClosedPayload.model_validate_json(json.dumps(data))
        accepted = True
    except ValidationError:
        accepted = False
    assert accepted == expected

