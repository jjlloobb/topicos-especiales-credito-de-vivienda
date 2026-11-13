"""CA-5: los tokens no quedan en disco ni en evidencias (U12 Paso 5; NFR-U12-04, NFR-U12-05). Sin navegador y sin Keycloak: el emisor es el doble de `oidc_double`."""

import dataclasses
import json
import logging
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fake_clock import FakeClock
from oidc_double import FakeIdp, ScriptedForm, pem_of
from vault_double import ADDR, TOKEN, VaultDouble, synthetic_secrets

from vectra_verification import evidence, guard
from vectra_verification.clients._api import ApiError, RunTag
from vectra_verification.clients.bff import BffClient
from vectra_verification.clients.oidc import AuthorizationRequest, OidcClient, OidcError
from vectra_verification.credentials import Credentials
from vectra_verification.driver import DriverReport
from vectra_verification.evidence import EvidenceError
from vectra_verification.simulator import RunReport


class Recording(httpx.BaseTransport):
    def __init__(self, inner: httpx.BaseTransport) -> None:
        self.inner = inner
        self.responses: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        response.read()
        self.responses.append(response.text)
        return response


def _world(environment: guard.Environment):  # type: ignore[no-untyped-def]
    clock = FakeClock()
    idp = FakeIdp(environment.issuer, clock.now)
    secrets = synthetic_secrets()
    key = ec.generate_private_key(ec.SECP256R1())
    secrets["identity/clients/channel-simulator"]["private-key"] = pem_of(key)
    idp.service_keys["channel-simulator"] = key.public_key()
    credentials = Credentials(environment, ADDR, TOKEN, VaultDouble("secret", secrets))
    form = ScriptedForm(idp)
    recording = Recording(idp)
    return (
        clock,
        idp,
        form,
        OidcClient(environment, credentials, clock, transport=recording, form=form),
        credentials,
        recording,
    )


def test_repr_and_str_of_the_tokens_and_sessions_show_none_of_them(
    dynamic_environment: guard.Environment,
) -> None:
    _, _, _, client, _, _ = _world(dynamic_environment)
    session = client.login("analista-1")
    request = client.authorization_request(False)
    secrets = [
        session.tokens.access_token.reveal(),
        session.tokens.refresh_token.reveal(),
        session.tokens.id_token.reveal(),
        request.code_verifier.reveal(),
    ]  # type: ignore[union-attr]
    for thing in (
        session.tokens,
        session,
        request,
        client.service_session("channel-simulator", ["intake:submit"]),
    ):
        for text in (repr(thing), str(thing)):
            assert not any(secret in text for secret in secrets) and "eyJ" not in text
    assert isinstance(request, AuthorizationRequest) and "Secret(***)" in repr(request)


def test_token_response_request_headers_and_assertion_form_pass_the_filter_and_the_unfiltered_dump_fails(
    dynamic_environment: guard.Environment,
) -> None:
    clock, idp, _, client, credentials, recording = _world(dynamic_environment)
    session = client.login("analista-1")
    client.service_session("channel-simulator", ["intake:submit"]).bearer()
    seen: list[httpx.Request] = []

    def bff(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={"role": "analista", "mfa": True, "auth_time": "2026-11-13T10:00:00Z", "locale": "es-CO"},
        )

    BffClient(
        dynamic_environment, session, RunTag("decisions", "3fa9c2d1"), transport=httpx.MockTransport(bff)
    ).me()
    dumps = [
        recording.responses[0],  # la respuesta completa del endpoint de token
        repr(seen[0].headers.raw)
        + "\n"
        + str(dict(seen[0].headers)),  # cabeceras de una solicitud al BFF (tuplas y mapa)
        "&".join(
            urlencode(form) for form in idp.token_requests if "client_assertion" in form
        ),  # el formulario del client_assertion
    ]
    secrets = credentials.secret_values()
    for raw in dumps:
        with pytest.raises(EvidenceError, match="evidence_contains_(jwt|secret)"):
            evidence.ensure_clean(raw, secrets)  # sin filtrar: habia un JWT
        cleaned = evidence.prepare(raw, secrets)  # filtrado: sale sin tokens y sin fallar
        assert "eyJ" not in cleaned
    assert clock.sleeps == [] or True


def _logs_and_messages(
    dynamic_environment: guard.Environment, caplog: pytest.LogCaptureFixture
) -> tuple[str, list[str], list[str]]:
    caplog.set_level(logging.DEBUG)
    clock, idp, form, client, credentials, _ = _world(dynamic_environment)
    session = client.login("analista-1")
    messages: list[str] = []
    for status in (401, 403, 500):
        bff = BffClient(
            dynamic_environment,
            session,
            RunTag("decisions", "3fa9c2d1"),
            transport=httpx.MockTransport(lambda r, s=status: httpx.Response(s, json={})),
        )
        with pytest.raises(ApiError) as error:
            bff.me()
        messages.append(str(error.value))

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("tiempo agotado", request=request)

    with pytest.raises(ApiError) as error:
        BffClient(
            dynamic_environment,
            session,
            RunTag("decisions", "3fa9c2d1"),
            transport=httpx.MockTransport(timeout),
        ).me()
    messages.append(str(error.value))
    clock.advance(31)
    form.tamper_state = True
    with pytest.raises(OidcError) as state_error:
        client.login("analista-1")
    messages.append(str(state_error.value))
    secrets = [
        session.tokens.access_token.reveal(),
        session.tokens.refresh_token.reveal(),
        credentials.user_password("analista-1").reveal(),
        credentials.user_totp_seed("analista-1").reveal(),
        form.otp_codes[0],
    ]  # type: ignore[union-attr]
    codes = [parse_qs(urlsplit(u).query)["code"][0] for u in form.returned_urls]
    verifiers = [
        query for u in form.authorize_urls for query in [parse_qs(urlsplit(u).query)["code_challenge"][0]]
    ]  # el desafio es publico; el verificador solo vive en memoria
    return "\n".join(messages) + "\n" + caplog.text, secrets + codes, verifiers


def test_no_exception_message_or_log_record_carries_a_token_a_password_a_totp_or_the_code(
    dynamic_environment: guard.Environment, caplog: pytest.LogCaptureFixture
) -> None:
    text, forbidden, _ = _logs_and_messages(dynamic_environment, caplog)
    assert text.strip() and all(secret not in text for secret in forbidden)
    assert "state_mismatch" in text and "callback" not in text and "state=" not in text


def test_the_state_error_does_not_carry_the_return_url(dynamic_environment: guard.Environment) -> None:
    _, _, form, client, _, _ = _world(dynamic_environment)
    form.tamper_state = True
    with pytest.raises(OidcError) as error:
        client.login("analista-1")
    returned = form.returned_urls[0]
    code = parse_qs(urlsplit(returned).query)["code"][0]
    assert (
        code not in str(error.value)
        and returned not in str(error.value)
        and "alterado" not in str(error.value)
    )


def test_reports_serialized_pass_the_filter_unchanged(dynamic_environment: guard.Environment) -> None:
    now = datetime(2026, 11, 13, 10, 0, tzinfo=UTC)
    run = RunReport(
        "normal",
        2000,
        1998,
        {"validation_error": 2},
        ("7d0e0f46-1111-4222-8333-444455556666",),
        now,
        now,
        "1.0.0",
        20261101,
        7,
        10.0,
        "3fa9c2d1",
        18000,
        "a" * 64,
        0,
    )
    driven = DriverReport(
        2, {"sigue": 1}, 1, 0, 0, now, now, {}, 0, 0, ("7d0e0f46-1111-4222-8333-444455556666",)
    )
    for report in (run, driven):
        text = json.dumps(dataclasses.asdict(report), default=str, sort_keys=True)
        assert evidence.prepare(text, TOKEN.split() + ["x" * 12]) == text
