"""PBT-U4-05 y ejemplos de BR-U4-11 y BR-U4-14, y P-U4-07. Paso 5, `serving_config`."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.models.governance import ChannelRule, ModelVersion, NormativeParams, PolicyVersion, ServingConfig

from vectra_governance.serving_config import compose, compute_etag

NOW = datetime(2026, 11, 9, 15, tzinfo=UTC)
FROM = datetime(2026, 11, 1, tzinfo=UTC)
#: domain-entities §5: los campos de `serving_config`, mas el `etag` (que no entra en el propio calculo).
SECTION_5_FIELDS = {
    "model_version_id",
    "state",
    "policy_version_id",
    "cutoff",
    "low_confidence_threshold",
    "channel_rules",
    "feature_dictionary_version",
    "inference_service",
    "normative_current",
    "effective_from",
    "etag",
}


def model(
    version: str = "mv-2026-09-01-abc12345",
    state: str = "activo",
    isvc: str = "isvc-abc12345",
    dictionary: str = "fd-1",
) -> ModelVersion:
    return ModelVersion(
        model_version_id=version,
        state=state,  # type: ignore[arg-type]
        artifact_uri="s3://model-store/a",
        artifact_format="xgboost_json",
        artifact_sha256="a" * 64,
        explainer_uri="s3://model-store/e",
        explainer_sha256="b" * 64,
        inference_service=isvc,
        manifest_uri="s3://model-store/m",
        manifest_sha256="c" * 64,
        feature_dictionary_version=dictionary,
        data_sources=[],
        registered_by="sub-a",
        investigation=False,
        created_at=FROM,
        updated_at=FROM,
    )


def policy(
    version: str = "p1",
    state: str = "activa",
    normative: list[NormativeParams] | None = None,
    cutoff: str = "0.5000",
    low_confidence_threshold: str = "0.2000",
    channel_rules: list[ChannelRule] | None = None,
) -> PolicyVersion:
    return PolicyVersion(
        policy_version_id=version,
        state=state,  # type: ignore[arg-type]
        proposed_by="sub-a",
        created_at=FROM,
        cutoff=cutoff,  # type: ignore[arg-type]
        low_confidence_threshold=low_confidence_threshold,  # type: ignore[arg-type]
        channel_rules=channel_rules or [],
        normative=normative or [],
    )


def normative(
    start: date = date(2026, 1, 1), end: date | None = None, cap: str = "0.2500"
) -> NormativeParams:
    return NormativeParams(
        vis_max_property_value=150_000_000,
        usury_cap_ea=cap,
        effective_from=start,
        effective_to=end,
        source_ref="r",
    )


def config(**changes: Any) -> ServingConfig:
    base = compose(model(), policy(normative=[normative()]), FROM, NOW)
    assert base is not None
    return base.model_copy(update=changes)


def etag_of(item: ServingConfig) -> str:
    return compute_etag(item)


def canonical_fields(item: ServingConfig) -> dict[str, Any]:
    """El contenido que el etag cubre, leido por el oraculo sin pasar por el modulo (todo menos `etag`)."""
    return {key: value for key, value in item.model_dump(mode="json").items() if key != "etag"}


# --- PBT-U4-05 ------------------------------------------------------------------------------------------------------

_VERSIONS = st.sampled_from(["mv-2026-09-01-abc12345", "mv-2026-10-01-def67890"])
_ISVC = st.sampled_from(["isvc-abc12345", "isvc-def67890"])
_NORMATIVE = st.one_of(
    st.none(),
    st.builds(
        NormativeParams,
        vis_max_property_value=st.sampled_from([100, 200]),
        usury_cap_ea=st.sampled_from(["0.2500", "0.3000"]),
        effective_from=st.sampled_from([date(2026, 1, 1), date(2026, 6, 1)]),
        effective_to=st.sampled_from([None, date(2027, 1, 1)]),
        source_ref=st.sampled_from(["r", "s"]),
    ),
)
_CONFIGS = st.builds(
    ServingConfig,
    model_version_id=_VERSIONS,
    state=st.sampled_from(["activo", "congelado"]),
    policy_version_id=st.sampled_from(["p1", "p2"]),
    cutoff=st.sampled_from(["0.5000", "0.6000"]),
    low_confidence_threshold=st.sampled_from(["0.2000", "0.3000"]),
    channel_rules=st.sampled_from([[], [ChannelRule(channel="web", cutoff="0.7000")], [ChannelRule(channel="web")]]),
    feature_dictionary_version=st.sampled_from(["fd-1", "fd-2"]),
    effective_from=st.sampled_from([FROM, FROM + timedelta(seconds=1), FROM + timedelta(microseconds=1)]),
    inference_service=_ISVC,
    etag=st.just(""),
    normative_current=_NORMATIVE,
)


@given(a=_CONFIGS, b=_CONFIGS)
def test_pbt_u4_05_equal_etag_iff_equal_canonical_content(a: ServingConfig, b: ServingConfig) -> None:
    same_content = canonical_fields(a) == canonical_fields(b)
    assert (etag_of(a) == etag_of(b)) == same_content


@given(a=_CONFIGS, field=st.sampled_from(sorted(SECTION_5_FIELDS - {"etag"})), other=_CONFIGS)
def test_pbt_u4_05_a_pair_that_differs_in_one_field_or_in_none(
    a: ServingConfig, field: str, other: ServingConfig
) -> None:
    """Pares construidos a proposito: iguales salvo en `field` (que puede coincidir por azar) o en nada."""
    b = a.model_copy(update={field: getattr(other, field)})
    assert (etag_of(a) == etag_of(b)) == (getattr(a, field) == getattr(b, field))
    assert etag_of(a) == etag_of(a.model_copy())  # ningun campo: el mismo etag


@given(item=_CONFIGS)
def test_pbt_u4_05_etag_is_sha256_of_the_jcs_of_all_fields_but_etag(item: ServingConfig) -> None:
    """Oraculo independiente: JSON con claves ordenadas y sin espacios (JCS para estos tipos: cadenas, enteros y nulos)."""
    jcs = json.dumps(canonical_fields(item), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert etag_of(item) == hashlib.sha256(jcs.encode()).hexdigest()
    assert etag_of(item.model_copy(update={"etag": "lo-que-sea"})) == etag_of(
        item
    )  # el etag no entra en su calculo


# --- Ejemplos ---------------------------------------------------------------------------------------------------------


def test_br_u4_14_changing_only_inference_service_changes_the_etag() -> None:
    """BR-U4-14; domain-entities §5: un cambio de `InferenceService` en `mark_active` dispara la convergencia."""
    a = compose(model(isvc="isvc-abc12345"), policy(), FROM, NOW)
    b = compose(model(isvc="isvc-def67890"), policy(), FROM, NOW)
    assert a is not None and b is not None
    assert a.model_copy(update={"inference_service": b.inference_service, "etag": b.etag}) == b
    assert a.etag != b.etag


def test_br_u4_11_a_change_of_normative_current_changes_the_etag() -> None:
    p = policy(
        normative=[
            normative(end=date(2026, 11, 10), cap="0.2500"),
            normative(start=date(2026, 11, 10), cap="0.3000"),
        ]
    )
    before = compose(model(), p, FROM, datetime(2026, 11, 10, 4, 59, 59, tzinfo=UTC))
    after = compose(model(), p, FROM, datetime(2026, 11, 10, 5, tzinfo=UTC))  # 00:00 de Bogota
    assert before is not None and after is not None
    assert before.normative_current is not None and after.normative_current is not None
    assert (
        before.normative_current.usury_cap_ea == "0.2500" and after.normative_current.usury_cap_ea == "0.3000"
    )
    assert before.etag != after.etag
    same_day = compose(model(), p, FROM, datetime(2026, 11, 10, 20, tzinfo=UTC))
    assert same_day is not None and same_day.etag == after.etag  # mismo contenido, mismo etag


def test_br_u4_11_expired_normative_gives_null_normative_current_and_still_a_config() -> None:
    result = compose(model(), policy(normative=[normative(end=date(2026, 11, 1))]), FROM, NOW)
    assert result is not None and result.normative_current is None


def test_br_u4_14_frozen_version_is_served_with_its_state() -> None:
    result = compose(model(state="congelado"), policy(), FROM, NOW)
    assert result is not None and result.state == "congelado"
    assert result.etag != compose(model(state="activo"), policy(), FROM, NOW).etag  # type: ignore[union-attr]


def test_br_u4_14_without_a_servable_version_or_an_active_policy_there_is_no_config() -> None:
    """El tipo de U0 exige las dos cosas: la composicion devuelve `None` (la API decide que responde, Pasos 9 y 10)."""
    assert compose(None, policy(), FROM, NOW) is None
    assert compose(model(), None, FROM, NOW) is None
    for state in ("registrado", "en_validacion", "aprobado", "inactivo", "retirado"):
        assert compose(model(state=state), policy(), FROM, NOW) is None
    for state in ("propuesta", "rechazada", "historica"):
        assert compose(model(), policy(state=state), FROM, NOW) is None


def test_p_u4_07_the_config_has_only_the_fields_of_the_u0_type() -> None:
    result = compose(model(), policy(normative=[normative()]), FROM, NOW)
    assert result is not None
    assert set(result.model_dump()) == set(ServingConfig.model_fields) == SECTION_5_FIELDS
    assert "bias_monitoring_age_s" not in result.model_dump()
    assert result.etag == compute_etag(result) and len(result.etag) == 64
    assert result.inference_service == "isvc-abc12345"  # el de la version, no uno derivado
    assert result.model_version_id == "mv-2026-09-01-abc12345" and result.policy_version_id == "p1"
    assert result.feature_dictionary_version == "fd-1" and result.effective_from == FROM


def test_u04_t09_compose_copies_the_three_policy_fields_of_the_active_policy() -> None:
    rules = [ChannelRule(channel="web", cutoff="0.7000"), ChannelRule(channel="agencia")]
    result = compose(model(), policy(cutoff="0.6500", low_confidence_threshold="0.1500", channel_rules=rules), FROM, NOW)
    assert result is not None
    assert result.cutoff == "0.6500" and result.low_confidence_threshold == "0.1500"
    assert result.channel_rules == rules


def test_u04_t09_policies_that_differ_only_in_a_policy_parameter_have_different_etags() -> None:
    base = compose(model(), policy(), FROM, NOW)
    assert base is not None
    variants = [
        policy(cutoff="0.5001"),
        policy(low_confidence_threshold="0.2001"),
        policy(channel_rules=[ChannelRule(channel="web", cutoff="0.7000")]),
    ]
    etags = {compose(model(), v, FROM, NOW).etag for v in variants}  # type: ignore[union-attr]
    assert len(etags) == 3 and base.etag not in etags
    assert compose(model(), policy(channel_rules=[ChannelRule(channel="web", cutoff="0.7000")]), FROM, NOW).etag != compose(  # type: ignore[union-attr]
        model(), policy(channel_rules=[ChannelRule(channel="web", cutoff="0.7100")]), FROM, NOW
    ).etag  # type: ignore[union-attr]
