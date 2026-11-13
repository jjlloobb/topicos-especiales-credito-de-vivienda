"""CA-4: el flujo OIDC sin Keycloak, con reloj falso (U12 Paso 5; INF-U12-03; NFR-U12-04; BR-U12-03). Sin navegador, sin sockets y sin `sleep` real."""

import base64
import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import ec
from fake_clock import FakeClock
from oidc_double import FakeIdp, ScriptedForm, pem_of
from vault_double import ADDR, TOKEN, VaultDouble, synthetic_secrets

from vectra_verification import guard
from vectra_verification.clients import oidc
from vectra_verification.clients.oidc import OidcClient, OidcError
from vectra_verification.credentials import Credentials
from vectra_verification.guard import KIND, GuardError

REPO = Path(__file__).resolve().parents[3]


def _world(environment: guard.Environment, **form_kwargs):  # type: ignore[no-untyped-def]
    clock = FakeClock()
    idp = FakeIdp(environment.issuer, clock.now)
    secrets = synthetic_secrets()
    key = ec.generate_private_key(ec.SECP256R1())
    secrets["identity/clients/channel-simulator"]["private-key"] = pem_of(key)
    idp.service_keys["channel-simulator"] = key.public_key()
    credentials = Credentials(environment, ADDR, TOKEN, VaultDouble("secret", secrets))
    form = ScriptedForm(idp, **form_kwargs)
    client = OidcClient(environment, credentials, clock, transport=idp, form=form)
    return clock, idp, form, client, credentials


def test_the_code_challenge_is_s256_of_the_verifier_rfc7636_vector() -> None:
    assert (
        oidc.code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_the_authorization_url_carries_state_nonce_challenge_and_only_the_step_up_adds_prompt(
    dynamic_environment: guard.Environment,
) -> None:
    _, _, _, client, _ = _world(dynamic_environment)
    login = client.authorization_request(step_up=False)
    query = {k: v[-1] for k, v in parse_qs(urlsplit(login.url).query).items()}
    assert (
        query["response_type"] == "code"
        and query["client_id"] == "vectra-console"
        and query["scope"] == "openid"
    )
    assert query["state"] == login.state and query["nonce"] == login.nonce.reveal()
    assert query["code_challenge_method"] == "S256"
    assert (
        query["code_challenge"]
        == base64.urlsafe_b64encode(hashlib.sha256(login.code_verifier.reveal().encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert query["redirect_uri"].endswith("/callback") and not {"prompt", "max_age", "acr_values"} & set(
        query
    )
    step = {
        k: v[-1] for k, v in parse_qs(urlsplit(client.authorization_request(step_up=True).url).query).items()
    }
    assert (step["prompt"], step["max_age"], step["acr_values"]) == ("login", "0", "mfa")
    assert step["redirect_uri"].endswith("/stepup-callback")


def test_with_guard_kind_the_endpoint_and_both_redirect_uris_are_those_of_the_realm_and_the_gateway_values() -> (
    None
):
    realm_text = (REPO / "identity-edge" / "keycloak" / "realm" / "realm.kind.yaml").read_text()
    realm = yaml.safe_load(
        re.sub(
            r"\$\(env:[A-Z0-9_]+\)", "x", realm_text.replace("$(env:PUBLIC_HOSTNAME)", "vectra.localtest.me")
        )
    )
    console = next(c for c in realm["clients"] if c["clientId"] == "vectra-console")
    host = yaml.safe_load((REPO / "identity-edge" / "gateway" / "values" / "kind.yaml").read_text())[
        "hostname"
    ]
    assert KIND.host == host
    clock = FakeClock()
    client = OidcClient(
        KIND,
        Credentials(KIND, ADDR, TOKEN, VaultDouble("secret", synthetic_secrets())),
        clock,
        transport=httpx.MockTransport(lambda r: httpx.Response(500)),
    )
    assert [client.redirect_uri(False), client.redirect_uri(True)] == [
        u for u in console["redirectUris"] if "vectra.localtest.me" in u
    ]
    assert (
        client.authorization_url
        == f"https://{host}/auth/realms/{realm['realm']}/protocol/openid-connect/auth"
    )
    assert console["publicClient"] and console["attributes"]["pkce.code.challenge.method"] == "S256"


def test_state_nonce_and_verifier_change_on_every_login(dynamic_environment: guard.Environment) -> None:
    clock, _, form, client, _ = _world(dynamic_environment)
    client.login("analista-1")
    clock.advance(31)
    client.login("analista-1")
    urls = [{k: v[-1] for k, v in parse_qs(urlsplit(u).query).items()} for u in form.authorize_urls]
    assert (
        len({u["state"] for u in urls})
        == len({u["nonce"] for u in urls})
        == len({u["code_challenge"] for u in urls})
        == 2
    )


def test_login_returns_the_role_and_mfa(dynamic_environment: guard.Environment) -> None:
    _, _, _, client, _ = _world(dynamic_environment)
    session = client.login("analista-1")
    assert (
        session.claims["roles"] == ["analista"]
        and session.acr == "mfa"
        and session.claims["azp"] == "vectra-console"
    )
    assert "ey" not in repr(session) and "Secret(***)" in repr(session.tokens)


def test_a_different_state_never_reaches_the_token_endpoint(dynamic_environment: guard.Environment) -> None:
    _, idp, form, client, _ = _world(dynamic_environment)
    form.tamper_state = True
    with pytest.raises(OidcError, match="state_mismatch"):
        client.login("analista-1")
    assert idp.token_requests == [] and client.token_requests == 0


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        ("acr_pwd", "acr_not_mfa"),
        ("audience", "token_audience_invalid"),
        ("expired", "token_expired"),
        ("other_key", "token_signature_invalid"),
        ("nonce", "nonce_mismatch"),
    ],
)
def test_a_bad_id_token_is_an_error_and_nothing_is_kept(
    dynamic_environment: guard.Environment, setup: str, expected: str
) -> None:
    clock, idp, form, client, _ = _world(dynamic_environment, acr="pwd" if setup == "acr_pwd" else "mfa")
    if setup == "audience":
        idp.id_overrides["aud"] = "otra-app"
    elif setup == "expired":
        idp.id_overrides["exp"] = int(clock.now().timestamp()) - 5
    elif setup == "other_key":
        idp.sign_with_other_key = True
    elif setup == "nonce":
        form.tamper_nonce = True
    with pytest.raises(OidcError, match=expected):
        client.login("analista-1")


def test_a_token_with_the_production_issuer_is_a_guard_error_and_is_not_used(
    dynamic_environment: guard.Environment,
) -> None:
    _, idp, _, client, _ = _world(dynamic_environment)
    idp.access_overrides["iss"] = "https://vectra.banco.internal/auth/realms/vectra"
    with pytest.raises(OidcError, match="token_issuer_not_allowed"):
        client.login("analista-1")
    with pytest.raises(GuardError):
        guard.check_token_issuer(KIND, "https://vectra.banco.internal/auth/realms/vectra")


@pytest.mark.parametrize(("age", "passes"), [(900, True), (901, False)])
def test_step_up_auth_time_must_be_at_most_900_seconds_old(
    dynamic_environment: guard.Environment, age: int, passes: bool
) -> None:
    _, _, form, client, _ = _world(dynamic_environment)
    form.auth_time_offset = -age
    if passes:
        assert client.step_up("cumplimiento-1").step_up
    else:
        with pytest.raises(OidcError, match="auth_time_too_old"):
            client.step_up("cumplimiento-1")


def test_totp_same_user_same_window_advances_the_fake_clock_to_the_next_window_without_real_sleep(
    dynamic_environment: guard.Environment,
) -> None:
    clock, _, form, client, credentials = _world(dynamic_environment)
    client.login("analista-1")
    window = int(clock.now().timestamp() // 30)
    client.login("analista-1")
    assert len(clock.sleeps) == 1 and int(clock.now().timestamp() // 30) == window + 1
    assert (
        form.otp_codes[1] == credentials.totp("analista-1", clock.now())
        and form.otp_codes[0] != form.otp_codes[1]
    )


def test_totp_another_user_does_not_wait_and_login_then_step_up_of_one_user_does(
    dynamic_environment: guard.Environment,
) -> None:
    clock, _, _, client, _ = _world(dynamic_environment)
    client.login("analista-1")
    client.login("analista-2")
    assert clock.sleeps == []
    client.login("cumplimiento-1")
    client.step_up("cumplimiento-1")
    assert len(clock.sleeps) == 1


def test_a_rejected_login_is_not_retried(dynamic_environment: guard.Environment) -> None:
    _, _, form, client, _ = _world(dynamic_environment)
    form.reject = True
    with pytest.raises(OidcError, match="login_rejected"):
        client.login("analista-1")
    assert form.calls == 1


def test_refresh_keeps_the_new_refresh_token_and_a_used_one_is_rejected(
    dynamic_environment: guard.Environment,
) -> None:
    clock, idp, _, client, _ = _world(dynamic_environment)
    session = client.login("analista-1")
    first = session.tokens.refresh_token
    clock.advance(250)  # quedan < 60 s de los 300
    session.bearer()
    assert (
        session.refreshes == 1
        and session.tokens.refresh_token is not first
        and session.tokens.refresh_token != first
    )
    with pytest.raises(OidcError):
        client.exchange_refresh(first)  # el realm rota: uno ya usado se rechaza


def test_a_rejected_refresh_makes_one_new_login(dynamic_environment: guard.Environment) -> None:
    clock, idp, form, client, _ = _world(dynamic_environment)
    session = client.login("analista-1")
    idp.reject_refresh = True
    clock.advance(250)
    session.bearer()
    assert session.relogins == 1 and form.calls == 2


def test_the_service_assertion_audience_is_the_environment_issuer(
    dynamic_environment: guard.Environment,
) -> None:
    _, idp, _, client, _ = _world(dynamic_environment)
    service = client.service_session("channel-simulator", ["intake:submit"])
    service.bearer()
    assert idp.last_assertion_claims["aud"] == dynamic_environment.issuer
    assert idp.last_assertion_claims["aud"] != client.token_url
    assert service.claims["azp"] == "channel-simulator" and "intake:submit" in service.claims["scope"]
