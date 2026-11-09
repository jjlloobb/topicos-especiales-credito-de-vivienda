"""PBT-U5-07 (BR-U5-16, BR-U5-17): todo caso RT-1 difiere de su par solo en `free_text`; todo caso RT-4 es valido segun U0
y esta fuera de la envolvente. Se prueba sobre los casos generados y sobre mutaciones de ellos."""

from datetime import date
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.models.application import ApplicationIn
from vectra_reference import adversarial as adv
from vectra_reference.features import row_values
from vectra_reference.generate import (
    application_fields,
    build_rows,
    load_catalog,
    load_config,
    with_overrides,
)
from vectra_reference.release import Release

CONFIG = load_config()
NAMES = load_catalog()
ROWS = [
    {**application_fields(r), "birth_date": r["birth_date"].isoformat()}
    for r in build_rows(with_overrides(CONFIG, n_rows=300, seed=7), NAMES)
]
# U0 (BR-U0-29) admite lo imprimible (`str.isprintable`: ni controles, ni separadores distintos del espacio ASCII) y
# ademas el salto de linea, el retorno de carro y el tabulador.
PRINTABLE = st.text(
    alphabet=st.one_of(
        st.sampled_from(" \n\r\t"),
        st.characters(codec="utf-8", exclude_categories=("Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp")),
    ),
    max_size=2000,
)


def _is_valid(application: dict[str, Any]) -> bool:
    try:
        ApplicationIn.model_validate(
            {**application, "birth_date": date.fromisoformat(str(application["birth_date"]))}
        )
    except ValueError:
        return False
    return True


# RT-1 ------------------------------------------------------------------------------------------------------------


@given(row=st.sampled_from(ROWS), text=PRINTABLE)
def test_pbt_u5_07_a_generated_pair_differs_only_in_free_text(row: dict[str, Any], text: str) -> None:
    base = {**row, "free_text": None}
    case, pair = adv.rt1_pair(base, text)
    assert adv.differs_only_in_free_text(case, pair)
    assert {k for k in case if case[k] != pair[k]} <= {"free_text"}
    assert case["free_text"] == text and pair["free_text"] is None
    assert _is_valid(case) and _is_valid(pair)


@given(data=st.data())
def test_pbt_u5_07_a_mutation_of_another_field_breaks_the_pair(data: st.DataObject) -> None:
    base = {**data.draw(st.sampled_from(ROWS)), "free_text": None}
    case, pair = adv.rt1_pair(base, data.draw(PRINTABLE))
    field = data.draw(st.sampled_from(sorted(k for k in case if k != "free_text")))
    kind = data.draw(st.sampled_from(["change", "drop", "extra"]))
    if kind == "drop":
        del case[field]
    elif kind == "extra":
        case["campo_extra"] = "x"
    else:
        value = case[field]
        case[field] = value + 1 if isinstance(value, int) else f"{value}x" if isinstance(value, str) else "x"
    assert not adv.differs_only_in_free_text(case, pair)


def test_pbt_u5_07_the_20_generated_pairs_hold_the_property() -> None:
    cases = adv.rt1_cases(NAMES)
    assert len(cases) == 20
    for case in cases:
        assert adv.differs_only_in_free_text(case["input"], case["paired_with"])
        assert len(case["input"]["free_text"]) <= 2000


def test_pbt_u5_07_a_pair_that_also_changes_the_amount_is_rejected() -> None:
    case = adv.rt1_cases(NAMES)[0]
    broken = {**case["input"], "requested_amount": case["input"]["requested_amount"] + 1}
    assert not adv.differs_only_in_free_text(broken, case["paired_with"])


# RT-4 ------------------------------------------------------------------------------------------------------------


def test_pbt_u5_07_every_generated_rt4_case_is_valid_and_outside_the_envelope(small_release: Release) -> None:
    assert len(small_release.rt4) == 18
    for case in small_release.rt4:
        assert case["scenario"] == "RT-4"
        assert _is_valid(case["input"])
        adv.check_rt4_application(small_release.envelope, row_values, case["input"])  # no lanza
        assert adv.outside_envelope(small_release.envelope, row_values(case["input"]))


def _oracle_inside(envelope: dict[str, Any], values: dict[str, Any]) -> bool:
    """Oraculo aparte de `outside_envelope`: dentro de [p1, p99] en todas las numericas y con categorias vistas."""
    numeric_ok = all(item["p1"] <= float(values[item["name"]]) <= item["p99"] for item in envelope["numeric"])
    return numeric_ok and all(str(values[n]) in seen for n, seen in envelope["categories"].items())


@given(
    row=st.sampled_from(ROWS),
    income=st.one_of(st.none(), st.integers(1, 10**12)),
    channel=st.one_of(st.none(), st.sampled_from(["sucursal", "canal_raro"])),
    months=st.one_of(st.none(), st.integers(0, 720)),
)
def test_pbt_u5_07_a_mutated_application_is_an_rt4_case_exactly_when_it_is_valid_and_outside(
    small_release: Release, row: dict[str, Any], income: int | None, channel: str | None, months: int | None
) -> None:
    application = {**row}
    if income is not None:
        application["monthly_income"] = income
    if channel is not None:
        application["channel"] = channel
    if months is not None:
        application["employment_months"] = months
    envelope = small_release.envelope
    if not _is_valid(application):
        with pytest.raises(adv.AdversarialError, match="valida"):
            adv.check_rt4_application(envelope, row_values, application)
    elif _oracle_inside(envelope, row_values(application)):
        with pytest.raises(adv.AdversarialError, match="envolvente"):
            adv.check_rt4_application(envelope, row_values, application)
    else:
        adv.check_rt4_application(envelope, row_values, application)  # valida y fuera: es un caso RT-4


def test_pbt_u5_07_a_central_applicant_is_not_an_rt4_case(small_release: Release) -> None:
    central = {k: v for k, v in adv.rt1_base_application(1, NAMES).items()}
    with pytest.raises(adv.AdversarialError, match="envolvente"):
        adv.check_rt4_application(small_release.envelope, row_values, central)
