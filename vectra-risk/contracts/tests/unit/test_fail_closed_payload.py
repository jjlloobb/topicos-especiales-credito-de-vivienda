"""BR-U0-38."""

import json

import pytest
from pydantic import ValidationError

from vectra_contracts.models.registry import FailClosedPayload

AT = "2026-10-31T12:00:00Z"


def p(**over):
    return FailClosedPayload.model_validate_json(json.dumps({"retryable": True, "attempt": 1, **over}))


def test_br_u0_38_both_causes():
    with pytest.raises(ValidationError):
        p(cause="timeout", local_cause="scoring_unreachable", escalated_at=AT)


def test_br_u0_38_no_cause():
    with pytest.raises(ValidationError):
        p()


def test_br_u0_38_rejected_must_not_retry():
    with pytest.raises(ValidationError):
        p(local_cause="scoring_rejected", escalated_at=AT)


def test_br_u0_38_local_cause_requires_escalated_at():
    with pytest.raises(ValidationError):
        p(local_cause="scoring_unreachable")


def test_br_u0_38_valid_local():
    assert p(local_cause="scoring_unreachable", escalated_at=AT).retryable


def test_br_u0_38_frozen_not_retryable():
    with pytest.raises(ValidationError):
        p(cause="model_frozen")
    assert not p(cause="model_frozen", retryable=False).retryable
