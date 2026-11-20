"""El token de `keycloak-reader` con el Keycloak real (U02-T28).

Los jobs `realm-drift` y `signing-key-age` piden su token con `provider_from_env("keycloak", ())`: sin scopes. Keycloak 26.8.1 rechaza un `scope` presente y vacio
(`400 invalid_request`, «Invalid scopes: »). Estas pruebas firman con la llave privada que `realm_stack` generó para el JWKS de `keycloak-reader` e importa el realm de Git sin editar.
"""

import asyncio
import sys

import httpx
import jwt
import pytest
import realm_stack as rs

for _dir in ("jobs", "tools"):
    sys.path.insert(0, str(rs.EDGE / _dir))
import realm_drift  # noqa: E402
import signing_key_age  # noqa: E402
from vectra_common.service_token import provider_from_env  # noqa: E402

JWKS_VARIABLE = "CLIENT_KEYCLOAK_READER_JWKS"
ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"


def _token_url(stack: rs.Stack) -> str:
    return f"{stack.base_url}/auth/realms/{rs.REALM}/protocol/openid-connect/token"


def _issuer(stack: rs.Stack) -> str:
    return f"{stack.base_url}/auth/realms/{rs.REALM}"


def _post_token(stack: rs.Stack, **extra: str) -> httpx.Response:
    """La peticion de `keycloak-reader` a mano: lo que envia `service_token`, con o sin `scope`."""
    kid, private_pem = stack.client_keys[JWKS_VARIABLE]
    now = int(rs.time.time())
    claims = {"iss": "keycloak-reader", "sub": "keycloak-reader", "aud": _issuer(stack), "jti": rs.secrets.token_hex(16), "iat": now, "exp": now + 60}
    assertion = jwt.encode(claims, private_pem, algorithm="ES256", headers={"kid": kid})
    http = stack.client()
    try:
        return http.post(_token_url(stack), data={"grant_type": "client_credentials", "client_assertion_type": ASSERTION_TYPE, "client_assertion": assertion, "audience": "keycloak", **extra})
    finally:
        http.close()


@pytest.fixture
def reader_env(stack: rs.Stack, monkeypatch: pytest.MonkeyPatch) -> rs.Stack:
    """El entorno del Job: las mismas variables que le pone el chart `identity-jobs`, apuntando al Keycloak del arnes."""
    kid, private_pem = stack.client_keys[JWKS_VARIABLE]
    key_file = stack.workdir / "keycloak-reader.key"
    key_file.write_text(private_pem, encoding="utf-8")
    monkeypatch.setenv("VECTRA_CLIENT_ID", "keycloak-reader")
    monkeypatch.setenv("VECTRA_TOKEN_URL", _token_url(stack))
    monkeypatch.setenv("VECTRA_ASSERTION_AUDIENCE", _issuer(stack))
    monkeypatch.setenv("VECTRA_CLIENT_KEY_PATH", str(key_file))
    monkeypatch.setenv("VECTRA_CLIENT_KEY_ID", kid)
    monkeypatch.setenv("VECTRA_CA_BUNDLE", str(stack.pki.ca_file))
    monkeypatch.setenv("KEYCLOAK_ADMIN_URL", f"{stack.base_url}/auth/admin/realms/{rs.REALM}")
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://pushgateway.invalid:9091")
    monkeypatch.setenv("REALM_FILE", str(rs.REALM_FILE))
    return stack


async def _discard_put(url: str, body: bytes) -> None:
    """El Pushgateway no existe aqui: solo se comprueba lo que el Job habria publicado."""
    _PUSHED.append((url, body))


_PUSHED: list[tuple[str, bytes]] = []


def test_reader_token_an_empty_scope_is_rejected_and_no_scope_is_accepted(stack: rs.Stack) -> None:
    """La causa medida en kind: `scope=` vacio da 400 `Invalid scopes`; sin el parametro, 200."""
    empty = _post_token(stack, scope="")
    assert empty.status_code == 400, f"{empty.status_code}: {empty.text}"
    assert "Invalid scopes" in empty.json().get("error_description", ""), empty.text
    absent = _post_token(stack)
    assert absent.status_code == 200, f"{absent.status_code}: {absent.text}"
    assert absent.json()["access_token"]


def test_reader_token_the_provider_of_the_jobs_gets_it_and_reads_the_realm(reader_env: rs.Stack) -> None:
    """`provider_from_env("keycloak", ())` (lo que arma `keycloak_admin.fetch_from_env`) obtiene el token y con el lee `/admin/realms/vectra`."""
    token = asyncio.run(provider_from_env("keycloak", ()).token())
    assert token.count(".") == 2
    http = reader_env.client()
    try:
        realm = http.get(f"/auth/admin/realms/{rs.REALM}", headers={"Authorization": f"Bearer {token}"})
    finally:
        http.close()
    assert realm.status_code == 200, realm.text
    assert realm.json()["realm"] == rs.REALM


def test_reader_token_signing_key_age_runs_against_the_real_keycloak(reader_env: rs.Stack) -> None:
    """El Job completo `signing-key-age` (su `run_from_env`): token, lectura de las llaves y la metrica que iria al Pushgateway."""
    _PUSHED.clear()
    created = asyncio.run(signing_key_age.run_from_env(http_put=_discard_put))
    assert created > 0
    assert len(_PUSHED) == 1 and signing_key_age.METRIC.encode() in _PUSHED[0][1], _PUSHED


def test_reader_token_realm_drift_gets_its_token_and_reads_the_realm(reader_env: rs.Stack) -> None:
    """El Job completo `realm-drift`: obtiene el token y lee el realm. Cuantas diferencias informa (el lector no ve los subflujos, U02-T27) no se afirma aqui."""
    _PUSHED.clear()
    drift = asyncio.run(realm_drift.run_from_env(http_put=_discard_put))
    assert drift >= 0
    assert len(_PUSHED) == 1, _PUSHED
    rs.measure(f"realm-drift contra el Keycloak del arnes: {drift} diferencias")
