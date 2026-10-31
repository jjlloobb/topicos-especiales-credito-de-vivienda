"""BR-U0-24, 40..43."""

from datetime import date
from decimal import Decimal

import pytest
from strategies.domain import application_dict, application_from

from vectra_contracts.dane import DEPARTMENT_REGION
from vectra_contracts.labels import age_range, derive_monitoring_labels, payment_band, region_of
from vectra_contracts.validation import age_at, check_age


def test_br_u0_24_age_limits():
    check_age(date(2008, 10, 31), date(2026, 10, 31))
    with pytest.raises(ValueError, match="age_out_of_range"):
        check_age(date(2008, 11, 1), date(2026, 10, 31))
    with pytest.raises(ValueError, match="age_out_of_range"):
        check_age(date(1900, 1, 1), date(2026, 10, 31))


@pytest.mark.parametrize(
    ("age", "label"),
    [(18, "18-25"), (25, "18-25"), (26, "26-35"), (35, "26-35"), (36, "36-45"), (45, "36-45"), (46, "46-55"), (55, "46-55"), (56, "56-65"), (65, "56-65"), (66, "66+"), (120, "66+")],
)
def test_br_u0_40_age_range(age, label):
    assert age_range(age) == label


@pytest.mark.parametrize("age", [17, 121])
def test_br_u0_40_outside_domain(age):
    with pytest.raises(ValueError):
        age_range(age)


def test_br_u0_40_birthday_boundary():
    assert age_at(date(2000, 11, 1), date(2026, 10, 31)) == 25
    assert age_at(date(2000, 10, 31), date(2026, 10, 31)) == 26


def test_br_u0_41_region_counts():
    counts: dict[str, int] = {}
    for region in DEPARTMENT_REGION.values():
        counts[region] = counts.get(region, 0) + 1
    assert counts == {"andina": 11, "caribe": 7, "pacifica": 4, "orinoquia": 4, "amazonia": 6, "insular": 1}
    assert region_of("05") == "andina" and region_of("88") == "insular" and region_of("76") == "pacifica"


@pytest.mark.parametrize(
    ("ratio", "band"),
    [("0.1999", "lt_20"), ("0.2000", "20_30"), ("0.3000", "20_30"), ("0.3001", "gt_30")],
)
def test_br_u0_42_band(ratio, band):
    assert payment_band(Decimal(ratio)) == band


def test_br_u0_43_copied_never_inferred():
    labels = derive_monitoring_labels(application_from(application_dict()), date(2026, 10, 31))
    assert labels.sexo == "no_informado" and labels.estrato == "no_informado"
    labels = derive_monitoring_labels(application_from(application_dict(sex="F", socioeconomic_stratum="3")), date(2026, 10, 31))
    assert labels.sexo == "F" and labels.estrato == "3"
