"""Ejemplos de borde de `errors` (plan de pruebas de U10-T01): cuerpo vacio, no JSON, `code` desconocido, etc."""

import json

import pytest
from vectra_common.errors import problem_body
from vectra_contracts.catalog import ProblemCode, ProblemReason

from console_bff.errors import translate_error

CID = "a" * 32


def test_same_code_reason_and_status_are_kept() -> None:
    body = json.dumps({"code": "conflict_state", "reason": "decision_already_recorded", "detail": "x"})
    out = translate_error(409, body, CID)
    assert (out.code, out.reason, out.status) == (
        ProblemCode.CONFLICT_STATE,
        ProblemReason.DECISION_ALREADY_RECORDED,
        409,
    )
    assert b"detail" not in problem_body(out)


@pytest.mark.parametrize(
    "body", [b"", b"   ", b"<html>502</html>", b"[1, 2]", b'"texto"', b"\xff\xfe", b"[" * 100_000, "no json"]
)
def test_empty_or_malformed_body_is_internal_error(body: bytes | str) -> None:
    out = translate_error(502, body, CID)
    assert (out.code, out.status) == (ProblemCode.INTERNAL_ERROR, 500)


def test_unknown_code_is_internal_error() -> None:
    assert translate_error(500, json.dumps({"code": "algo_raro"}), CID).code is ProblemCode.INTERNAL_ERROR
    assert translate_error(500, json.dumps({"code": 7}), CID).code is ProblemCode.INTERNAL_ERROR


@pytest.mark.parametrize("status,code", [(403, ProblemCode.FORBIDDEN), (404, ProblemCode.NOT_FOUND)])
def test_403_and_404_with_empty_body_are_propagated(status: int, code: ProblemCode) -> None:
    out = translate_error(status, b"", CID)
    assert (out.code, out.status) == (code, status)


def test_403_mfa_required_is_kept() -> None:
    out = translate_error(403, json.dumps({"code": "mfa_required"}), CID)
    assert (out.code, out.status) == (ProblemCode.MFA_REQUIRED, 403)


def test_404_with_inconsistent_code_follows_the_status() -> None:
    out = translate_error(404, json.dumps({"code": "conflict_state"}), CID)
    assert (out.code, out.status) == (ProblemCode.NOT_FOUND, 404)


def test_reason_not_allowed_for_the_code_is_dropped() -> None:
    out = translate_error(409, json.dumps({"code": "conflict_state", "reason": "factuality_failed"}), CID)
    assert out.reason is None
    assert (
        translate_error(409, json.dumps({"code": "conflict_state", "reason": "inventado"}), CID).reason
        is None
    )


def test_success_status_is_internal_error() -> None:
    assert translate_error(200, json.dumps({"code": "not_found"}), CID).code is ProblemCode.INTERNAL_ERROR


def test_invalid_params_only_for_validation_error_and_only_when_well_formed() -> None:
    params = [{"name": "campo", "reason_code": "missing"}]
    out = translate_error(422, json.dumps({"code": "validation_error", "invalid_params": params}), CID)
    assert [(p.name, p.reason_code) for p in out.invalid_params or []] == [("campo", "missing")]
    other = translate_error(409, json.dumps({"code": "conflict_state", "invalid_params": params}), CID)
    assert other.invalid_params is None
    bad = translate_error(422, json.dumps({"code": "validation_error", "invalid_params": [{"name": 1}]}), CID)
    assert bad.code is ProblemCode.VALIDATION_ERROR and bad.invalid_params is None
    notlist = translate_error(422, json.dumps({"code": "validation_error", "invalid_params": "x"}), CID)
    assert notlist.invalid_params is None


def test_every_problem_code_has_an_error_class() -> None:
    for code in ProblemCode:
        out = translate_error(500, json.dumps({"code": code.value}), CID)
        assert out.code is code
