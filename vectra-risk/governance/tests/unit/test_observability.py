"""La regla `CompensationEventPending` (P-3) y la metrica que publica el reconciliador coinciden (respaldo de `promtool`)."""

from pathlib import Path

import yaml
from vectra_common.metrics import REGISTRY
from vectra_governance import background  # noqa: F401  (registra los gauges)

RULES = Path(__file__).resolve().parents[2] / "observability" / "governance-rules.yaml"


def test_la_regla_lee_la_metrica_que_publica_el_reconciliador() -> None:
    document = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    (rule,) = [r for g in document["groups"] for r in g["rules"] if r.get("alert") == "CompensationEventPending"]
    assert rule["labels"]["severity"] == "SEV2" and rule["annotations"]["runbook_url"]
    assert "vectra_governance_compensation_events_pending" in rule["expr"]
    assert REGISTRY.get_sample_value("vectra_governance_compensation_events_pending") is not None
