"""Filtro de evidencias (U12 Paso 2; NFR-U12-05): quita credenciales y falla si queda un JWT o un secreto."""

import pytest

from vectra_verification import evidence
from vectra_verification.evidence import EvidenceError

JWT = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3ZlY3RyYSIsInN1YiI6IngifQ.c2lnbmF0dXJlLXRlc3Q"
)
SEED = "JBSWY3DPEHPK3PXP"
PASSWORD = "pw-analista-1-Zq81xk"


def test_headers_and_token_fields_are_removed() -> None:
    raw = (
        f"> GET /api HTTP/1.1\nAuthorization: Bearer {JWT}\nCookie: session=abc123; other=zzz\nSet-Cookie: sid=987; Path=/\n"
        f'{{"access_token": "{JWT}", "refresh_token": "r-token-1", "id_token": "{JWT}", "client_assertion": "ca-1", "password": "{PASSWORD}", "ok": 1}}\n'
        f"grant_type=password&access_token={JWT}&password={PASSWORD}&scope=openid\n"
    )
    cleaned = evidence.scrub(raw)
    for leaked in (JWT, "abc123", "sid=987", "r-token-1", "ca-1", PASSWORD):
        assert leaked not in cleaned
    assert "Authorization: [REDACTADO]" in cleaned
    assert '"access_token": "[REDACTADO]"' in cleaned
    assert "access_token=[REDACTADO]&password=[REDACTADO]&scope=openid" in cleaned
    assert '"ok": 1' in cleaned and "GET /api HTTP/1.1" in cleaned


def test_curl_and_json_header_forms_are_removed() -> None:
    cleaned = evidence.scrub(
        f'curl -H "Authorization: Bearer {JWT}" -H \'Cookie: a=b\' https://x\n{{"Authorization": "Bearer {JWT}"}}'
    )
    assert JWT not in cleaned and "a=b" not in cleaned
    assert cleaned.startswith('curl -H "Authorization: [REDACTADO]"')


def test_a_clean_output_passes_unchanged() -> None:
    clean = "RT-3 paso: 3 de 3\nid: 7f1c\nsin credenciales\n"
    assert evidence.prepare(clean, {SEED, PASSWORD}) == clean
    assert evidence.scrub(clean) == clean


def test_a_jwt_in_the_body_outside_a_header_fails_generation() -> None:
    with pytest.raises(EvidenceError, match="evidence_contains_jwt") as error:
        evidence.prepare(f"el cuerpo de la respuesta trae {JWT} en un campo suelto", set())
    assert JWT not in str(error.value)


def test_a_header_jwt_alone_is_removed_so_generation_passes() -> None:
    assert JWT not in evidence.prepare(f"Authorization: Bearer {JWT}\n", set())


def test_a_totp_seed_or_a_password_loaded_by_credentials_fails_and_the_error_does_not_repeat_it() -> None:
    for secret in (SEED, PASSWORD):
        with pytest.raises(EvidenceError, match="evidence_contains_secret") as error:
            evidence.prepare(f"salida con {secret} dentro", {SEED, PASSWORD})
        assert secret not in str(error.value)


def test_a_filter_that_only_removes_authorization_would_leave_the_jwt() -> None:
    only_authorization = "Authorization: Bearer x\nbody " + JWT
    assert JWT in only_authorization.replace("Authorization: Bearer x", "")
    with pytest.raises(EvidenceError):
        evidence.prepare(only_authorization, set())


def test_empty_secrets_are_ignored() -> None:
    assert evidence.prepare("salida", {""}) == "salida"


def test_an_unsigned_jwt_is_detected() -> None:
    with pytest.raises(EvidenceError, match="jwt"):
        evidence.ensure_clean("eyJhbGciOiJub25lIn0.eyJzdWIiOiJ4In0.", set())
