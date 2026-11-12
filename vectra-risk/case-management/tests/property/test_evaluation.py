"""PBT-U8-05 (BLM §4; RT-1; BR-U8-06; US-109): el `ScoringRequest` nunca lleva identificadores, `free_text` ni `test_scenario_id`.

Para toda `ApplicationIn` (con PII y texto libre adversarial, del generador de `case_strategies`) y todo `FeatureSpec` valido (derivadas,
campos permitidos y busquedas, incluso busquedas que leen campos de identificacion): (1) el `ScoringRequest` no contiene llaves ni valores
de identificacion, ni `free_text` ni `test_scenario_id`; (2) dos solicitudes que solo difieren en `free_text` producen el mismo
`ScoringRequest`. `build_request` no hace E/S: esta prueba no necesita base.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from case_strategies import IDENTIFICATION, application_dicts, free_texts, split_application
from hypothesis import given
from hypothesis import strategies as st
from vectra_case.evaluation import Taken, build_request
from vectra_contracts.catalog import CaseState
from vectra_contracts.models.features import FeatureSpec

FORBIDDEN_KEYS = {*IDENTIFICATION, "free_text", "test_scenario_id"}
DERIVED = ("installment_cop", "installment_to_income", "loan_to_value", "age_years")
# Campos permitidos como feature; las busquedas pueden leer ademas campos de identificacion (la clave nunca llega al vector).
FIELDS = (
    "employment_type",
    "property_condition",
    "channel",
    "department_code",
    "term_months",
    "employment_months",
)
LOOKUP_SOURCES = (*FIELDS, "municipality_code", "document_type", "email", "full_name")
NEUTRAL = ("alto", "medio", "bajo", "otro", "grupo_a", "grupo_b")
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
CREATED = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@st.composite
def feature_specs(draw: st.DrawFn) -> FeatureSpec:
    items: list[dict[str, Any]] = [
        {"feature_id": f, "origin": "derived"} for f in draw(st.sets(st.sampled_from(DERIVED), min_size=1))
    ]
    for field in draw(st.sets(st.sampled_from(FIELDS))):
        items.append({"feature_id": f"f_{field}", "origin": "field", "source_fields": [field]})
    for i, source in enumerate(draw(st.lists(st.sampled_from(LOOKUP_SOURCES), max_size=3))):
        table = draw(st.dictionaries(st.text(min_size=1, max_size=12), st.sampled_from(NEUTRAL), max_size=3))
        items.append(
            {
                "feature_id": f"l_{i}_{source}",
                "origin": "lookup",
                "source_fields": [source],
                "table": table,
                "default": draw(
                    st.sampled_from(NEUTRAL)
                ),  # siempre hay valor: `derive` rechaza una busqueda sin resultado
            }
        )
    return FeatureSpec.model_validate({"model_version_id": "mv-1", "features": items})


def taken_of(data: dict[str, Any], *, attempt: int = 1, ever_degraded: bool = False) -> Taken:
    identifiers, rest = split_application(data)
    return Taken(
        uuid.uuid4(),
        attempt,
        CaseState.EN_EVALUACION,
        CREATED,
        ever_degraded,
        rest,
        identifiers.model_dump(mode="json"),
    )


def leaves(node: Any, path: str = "") -> list[tuple[str, Any]]:
    if isinstance(node, dict):
        return [leaf for k, v in node.items() for leaf in leaves(v, f"{path}.{k}")]
    if isinstance(node, list):
        return [leaf for i, v in enumerate(node) for leaf in leaves(v, f"{path}[{i}]")]
    return [(path, node)]


def keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in keys(v)}
    return set()


@given(data=application_dicts(), spec=feature_specs(), attempt=st.integers(1, 6), degraded=st.booleans())
def test_pbt_u8_05_the_scoring_request_carries_no_identifier_free_text_or_test_scenario(
    data: dict[str, Any], spec: FeatureSpec, attempt: int, degraded: bool
) -> None:
    taken = taken_of(data, attempt=attempt, ever_degraded=degraded)
    request = build_request(taken, spec, "mv-1", NOW)
    tree = json.loads(request.model_dump_json())
    assert not keys(tree) & FORBIDDEN_KEYS
    pii = {str(data[k]) for k in IDENTIFICATION}
    text = data.get("free_text")
    for path, value in leaves(tree):
        if isinstance(value, str):
            assert value not in pii, path  # ningun valor de identificacion llega como hoja
            if text:  # (un texto corto como "0" es subcadena de un numero cualquiera: solo se compara con las hojas de texto)
                assert value != text and (len(text) < 4 or text not in value), path
    assert request.case_id == taken.case_id and request.attempt == attempt
    assert request.received_at == CREATED  # el `created_at` del caso en todos los intentos
    assert request.first_evaluation is (not degraded and attempt == 1)


@given(data=application_dicts(), spec=feature_specs(), other=free_texts)
def test_pbt_u8_05_two_requests_that_only_differ_in_free_text_produce_the_same_scoring_request(
    data: dict[str, Any], spec: FeatureSpec, other: str | None
) -> None:
    changed = {k: v for k, v in data.items() if k != "free_text"}
    if other is not None:
        changed["free_text"] = other
    first, second = taken_of(data), taken_of(changed)
    object.__setattr__(second, "case_id", first.case_id)  # el mismo caso: lo unico que difiere es `free_text`
    assert build_request(first, spec, "mv-1", NOW) == build_request(second, spec, "mv-1", NOW)
