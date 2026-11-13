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


# --- Ronda 2 (F-02): el filtro falla cerrado. Lo que queda de un secreto cargado, o un JWT roto, es un error, no evidencia. ---

import json  # noqa: E402

PEM = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\nVJTUt9Us8cKjMzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDu\n-----END PRIVATE KEY-----\n"
QUOTED_PASSWORD = 'pw"secret-1'
ENV_SECRETS = {SEED, PASSWORD, QUOTED_PASSWORD, PEM}


def assert_does_not_leak(raw: str, leaked: str, secrets: set[str] | None = None) -> None:
    """Pasa si `prepare` falla, o si lo que devuelve ya no trae `leaked` (ni su valor sin comillas)."""
    try:
        out = evidence.prepare(raw, ENV_SECRETS if secrets is None else secrets)
    except EvidenceError:
        return
    assert leaked not in out, out


@pytest.mark.parametrize(
    ("raw", "leaked"),
    [
        ('Cookie: KEYCLOAK_SESSION="opaque-sess-123"\n', "opaque-sess-123"),
        ('Set-Cookie: AUTH_SESSION_ID="opaque-777"; Path=/\n', "opaque-777"),
        ('Cookie: a="x1"; b="y2"; c=z3\n', "y2"),
        ('Cookie: a="x1"; b="y2"; c=z3\n', "z3"),
        ("authorization=Bearer opaque-token-9\n", "opaque-token-9"),
        ("Authorization: 'Bearer opaque-token-9' extra-9\n", "extra-9"),
        ("X-Vault-Token: hvs.opaque-vault-5\n", "hvs.opaque-vault-5"),
        ("x-vault-token=hvs.opaque-vault-5\n", "hvs.opaque-vault-5"),
        ('{"Cookie": "sid=opaque-1", "n": 1}', "opaque-1"),
        ('curl -H "Cookie: sid=\\"opaque-2\\"" -H "X-Vault-Token: hvs.o3" https://x', "opaque-2"),
        ('curl -H "Cookie: sid=\\"opaque-2\\"" -H "X-Vault-Token: hvs.o3" https://x', "hvs.o3"),
        ("client_secret=opaque-cs-1&grant_type=client_credentials\n", "opaque-cs-1"),
        ('{"client_secret": "opaque-cs-2"}', "opaque-cs-2"),
        ('{"password": "pw\\"secret-1"}', "secret-1"),
        ('{"password": "a\\\\\\"tail-9"}', "tail-9"),
        ('password=pw"secret-1&x=1', "secret-1"),
        ("password=pw'secret-1&x=1", "secret-1"),
        ('{\\"password\\": \\"nested-pw-7\\"}', "nested-pw-7"),
    ],
)
def test_f02_values_in_quotes_and_other_sensitive_forms_are_removed(raw: str, leaked: str) -> None:
    assert_does_not_leak(raw, leaked, set())


def test_f02_a_header_value_is_removed_up_to_the_end_of_the_line_and_the_next_line_stays() -> None:
    out = evidence.scrub('Cookie: KEYCLOAK_SESSION="opaque-sess-123"; b="q"\nHTTP/1.1 200 OK\n')
    assert out == "Cookie: [REDACTADO]\nHTTP/1.1 200 OK\n"


def test_f02_the_quoted_forms_that_passed_keep_their_shape() -> None:
    assert evidence.scrub('{"password": "pw\\"secret-1", "ok": 1}') == '{"password": "[REDACTADO]", "ok": 1}'
    assert (
        evidence.scrub('{"Authorization": "Bearer x", "ok": 1}')
        == '{"Authorization": "[REDACTADO]", "ok": 1}'
    )


def test_f02_what_a_redaction_leaves_of_a_loaded_password_is_an_error() -> None:
    with pytest.raises(EvidenceError, match="evidence_contains_secret") as error:
        evidence.ensure_clean('"[REDACTADO]"secret-1"', {QUOTED_PASSWORD})
    assert "secret-1" not in str(error.value)


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"k": PEM}),
        json.dumps({"k": PEM}, ensure_ascii=False),
        PEM.replace("\n", "\\n"),
        PEM.replace("\n", ""),
        PEM.replace("\n", " "),
        "body " + PEM.splitlines()[1] + "\r\n" + PEM.splitlines()[2],
        SEED.lower(),
        f"seed {SEED.lower()} fin",
        f"seed {SEED[:8]} {SEED[8:]} fin",
        json.dumps({"p": QUOTED_PASSWORD}),
        QUOTED_PASSWORD.replace('"', "%22"),
        "x " + 'pw"secret-1'[3:] + " y",
    ],
)
def test_f02_a_loaded_secret_in_any_of_its_forms_is_an_error(text: str) -> None:
    with pytest.raises(EvidenceError):
        evidence.ensure_clean(text, ENV_SECRETS)


def test_f02_a_jwt_split_by_a_line_break_or_escaped_in_json_is_an_error() -> None:
    first, rest = JWT[:40], JWT[40:]
    for text in (
        f"{first}\n{rest}",
        f"{first}\r\n  {rest}",
        json.dumps(f"{first}\n{rest}"),
        f"{first} {rest}",
    ):
        with pytest.raises(EvidenceError, match="jwt"):
            evidence.ensure_clean(text, set())


def test_f02_the_seed_case_rule_does_not_make_clean_text_fail() -> None:
    assert (
        evidence.prepare("sin secretos, solo texto normal y corto", ENV_SECRETS)
        == "sin secretos, solo texto normal y corto"
    )
    assert evidence.prepare("pw sin nada mas", ENV_SECRETS) == "pw sin nada mas"
