"""BR-U0-60, 61; P-U0-05."""

import json

from pydantic import BaseModel, ValidationError

from vectra_common.errors import ConflictState, DeadlineExceeded, RateLimited, UnprocessableExplanation, VectraError, problem_body, to_problem, validation_failed
from vectra_contracts.catalog import PROBLEM_STATUS, ProblemCode, ProblemReason


class M(BaseModel):
    a: int


def test_br_u0_61_closed_fields():
    body = json.loads(problem_body(to_problem(ConflictState(ProblemReason.TRANSITION_PENDING), "c")))
    assert set(body) == {"type", "title", "status", "code", "correlation_id", "reason"}
    assert body["status"] == 409 and body["reason"] == "transition_pending"


def test_br_u0_60_generic_error_is_internal():
    problem = to_problem(VectraError(), "c")
    assert problem.code is ProblemCode.INTERNAL_ERROR and problem.status == 500


def test_statuses_follow_catalog():
    assert to_problem(DeadlineExceeded(), "c").status == 504
    assert to_problem(RateLimited(), "c").status == PROBLEM_STATUS[ProblemCode.RATE_LIMITED]
    assert to_problem(UnprocessableExplanation(ProblemReason.FACTUALITY_FAILED), "c").status == 422


def test_br_u0_30_validation_reports_name_and_code_never_value():
    try:
        M.model_validate({"a": "SECRETO-123"})
    except ValidationError as exc:
        error = validation_failed(exc)
    body = problem_body(to_problem(error, "c")).decode()
    assert "SECRETO-123" not in body
    assert json.loads(body)["invalid_params"][0]["name"] == "a"
