"""Propiedades de la capa de API: PBT-U0-07, 08, 09."""

import io
import json
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from strategies import domain as d

from vectra_common import errors as e
from vectra_common import logging as vlog
from vectra_common.authz import authorize
from vectra_contracts.catalog import LOG_RECORD_FIELDS, LogEvent, ProblemCode, ProblemReason, REASON_ALLOWED_CODE
from vectra_contracts.models.api import Principal

pytestmark = pytest.mark.common
PII_KEYS = st.sampled_from(["full_name", "email", "document_number", "address", "free_text", "sexo", "phone", "campo_nuevo"])
PII_VALUES = st.sampled_from(["Ana María Gómez", "ana@example.com", "1020304050", "Cra 7 # 45-10", "3001234567"])
ERRORS = [e.MalformedRequest, e.UnsupportedMediaType, e.ValidationFailed, e.Unauthenticated, e.Forbidden, e.MfaRequired, e.NotFound, e.ConflictState, e.PayloadTooLarge, e.RateLimited, e.DependencyUnavailable, e.UnprocessableExplanation, e.DeadlineExceeded, e.VectraError]


@given(st.dictionaries(PII_KEYS, PII_VALUES, min_size=1))
def test_pbt_u0_07_only_allowlist_and_no_pii(fields):
    out = io.StringIO()
    vlog.configure("pbt", out)
    vlog.log_event(LogEvent.CASE_VIEWED, case_id="c", **fields)
    line = out.getvalue()
    record = json.loads(line)
    assert set(record) <= LOG_RECORD_FIELDS
    assert not any(value in line for value in fields.values())


@given(st.sampled_from(ERRORS), st.sampled_from([None, *ProblemReason]))
def test_pbt_u0_08_problem_closed(kind, reason):
    allowed = reason is not None and REASON_ALLOWED_CODE[reason] is kind.code
    try:
        problem = e.to_problem(kind(reason), "c")
    except ValidationError:
        assert reason is not None and not allowed
        return
    assert reason is None or allowed
    body = json.loads(e.problem_body(problem))
    assert set(body) <= {"type", "title", "status", "code", "correlation_id", "reason", "invalid_params"}
    assert body["code"] in {c.value for c in ProblemCode}


@given(st.text(max_size=40))
def test_pbt_u0_08_generic_never_leaks(message):
    error = e.VectraError()
    error.args = (message,)
    body = e.problem_body(e.to_problem(error, "c")).decode()
    assert json.loads(body)["code"] == "internal_error"


@given(
    d.scope_sets, d.role_sets, st.sampled_from(["mfa", "pwd", None]), st.sampled_from([0, 899, 900, 901, 5000]),
    d.scope_sets, d.scope_sets, d.role_sets, st.booleans(),
)
def test_pbt_u0_09_oracle(p_scopes, p_roles, acr, age, scopes, any_scopes, roles, mfa):
    principal = Principal(subject="s", kind="user", scopes=p_scopes, roles=p_roles, acr=acr, auth_time=d.NOW - timedelta(seconds=age), token_expiry=d.NOW)
    expected = (
        scopes <= p_scopes
        and (not any_scopes or bool(any_scopes & p_scopes))
        and (not roles or bool(roles & p_roles))
        and (not mfa or (acr == "mfa" and age <= 900))
    )
    try:
        authorize(principal, scopes, any_scopes, roles, mfa, d.NOW)
        assert expected
    except (e.Forbidden, e.MfaRequired):
        assert not expected
