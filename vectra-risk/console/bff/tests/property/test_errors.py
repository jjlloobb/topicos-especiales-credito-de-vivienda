"""PBT-U10-03 (Paso 3, CA-6): para todo error de un destino, la salida es un `Problem` de U0 valido, sin `detail`
ni campos extra, con el mismo `code` o `internal_error`, y con 403 y 404 propagados.

`HYPOTHESIS_PROFILE=ci uv run pytest console/bff/tests/property/test_errors.py`.
"""

import json
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from vectra_contracts.catalog import PROBLEM_STATUS, REASON_ALLOWED_CODE, ProblemCode, ProblemReason
from vectra_contracts.models.api import Problem

from console_bff.errors import translate_error

CODES = [c.value for c in ProblemCode]
SECRET = "SECRETO-detalle-del-destino"
CID = "0123456789abcdef0123456789abcdef"

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=8),
    lambda children: (
        st.lists(children, max_size=3) | st.dictionaries(st.text(max_size=6), children, max_size=3)
    ),
    max_leaves=8,
)
codes = st.one_of(st.sampled_from(CODES), st.text(max_size=12), st.none(), st.integers())
reasons = st.one_of(st.sampled_from([r.value for r in ProblemReason]), st.text(max_size=12), st.none())
statuses = st.one_of(
    st.integers(min_value=400, max_value=599),
    st.integers(min_value=0, max_value=399),
    st.sampled_from([403, 404]),
)


@st.composite
def problem_like(draw: st.DrawFn) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": draw(st.text(max_size=10)),
        "title": draw(st.text(max_size=10)),
        "status": draw(st.integers()),
        "code": draw(codes),
        "reason": draw(reasons),
        "correlation_id": draw(st.text(max_size=10)),
        "invalid_params": draw(
            st.one_of(
                st.none(),
                json_values,
                st.lists(
                    st.fixed_dictionaries({"name": st.text(max_size=5), "reason_code": st.text(max_size=5)}),
                    max_size=3,
                ),
            )
        ),
        "detail": SECRET,
        "trace": SECRET,
        "extra": draw(json_values),
    }
    return body


bodies = st.one_of(
    problem_like().map(lambda d: json.dumps(d).encode()),
    problem_like().map(json.dumps),
    json_values.map(lambda v: json.dumps(v).encode()),
    st.binary(max_size=60),
    st.text(max_size=40),
    st.just(b""),
)


def _expected_code(status: int, body: bytes | str) -> str:
    """Oraculo independiente: el codigo que debe salir segun BR-U10-04 y BR-U10-03."""
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = None
    target = parsed.get("code") if isinstance(parsed, dict) else None
    if target not in CODES:
        target = None
    if status in (403, 404) and (target is None or PROBLEM_STATUS[ProblemCode(target)] != status):
        return "forbidden" if status == 403 else "not_found"
    if status < 400 or target is None:
        return "internal_error"
    return str(target)


@given(status=statuses, body=bodies)
def test_output_is_always_a_valid_problem_without_detail(status: int, body: bytes | str) -> None:
    out = translate_error(status, body, CID)
    assert Problem.model_validate(out.model_dump()) == out
    dumped = out.model_dump(mode="json", exclude_none=True)
    assert set(dumped) <= {"type", "title", "status", "code", "correlation_id", "reason", "invalid_params"}
    assert "detail" not in dumped and "trace" not in dumped and "extra" not in dumped
    assert SECRET not in json.dumps(dumped)
    assert out.correlation_id == CID


@given(status=statuses, body=bodies)
def test_code_is_kept_or_internal_error(status: int, body: bytes | str) -> None:
    out = translate_error(status, body, CID)
    assert out.code.value == _expected_code(status, body)
    assert out.status == PROBLEM_STATUS[out.code]
    if out.code is ProblemCode.INTERNAL_ERROR:
        assert out.status == 500


@given(status=st.sampled_from([403, 404]), body=bodies)
def test_403_and_404_propagate_with_their_status(status: int, body: bytes | str) -> None:
    out = translate_error(status, body, CID)
    assert out.status == status
    assert out.code in (ProblemCode.FORBIDDEN, ProblemCode.MFA_REQUIRED, ProblemCode.NOT_FOUND)


@given(status=st.integers(min_value=400, max_value=599), code=st.sampled_from(CODES), reason=reasons)
def test_reason_only_when_allowed_for_the_code(status: int, code: str, reason: str | None) -> None:
    out = translate_error(status, json.dumps({"code": code, "reason": reason}), CID)
    if out.reason is not None:
        assert REASON_ALLOWED_CODE[out.reason] is out.code
    if out.code.value == code and reason in {r.value for r in ProblemReason}:
        assert (out.reason is not None) == (REASON_ALLOWED_CODE[ProblemReason(reason)].value == code)
