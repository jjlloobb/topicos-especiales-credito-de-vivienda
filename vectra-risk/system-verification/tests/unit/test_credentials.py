"""`credentials` (U12 Paso 2; NFR-U12-04; BR-U12-03): lectura de la boveda KV v2 con un doble, solo en memoria."""

import ast
import os
from datetime import UTC, datetime
from pathlib import Path

import pyotp
import pytest
from vault_double import ADDR, TOKEN, VaultDouble, synthetic_secrets

from vectra_verification import credentials
from vectra_verification.credentials import Credentials, CredentialsError
from vectra_verification.guard import KIND, STAGING


def _credentials(environment=KIND, mount="secret", **kwargs):  # type: ignore[no-untyped-def]
    double = VaultDouble(mount, synthetic_secrets(), **kwargs)
    return Credentials(environment, ADDR, TOKEN, double), double


def test_kind_reads_client_keys_with_mount_secret_and_the_token_header() -> None:
    creds, double = _credentials()
    assert creds.client_key("channel-simulator").reveal().endswith("chan-sim-key")
    assert creds.client_key("verification-reader").reveal().endswith("ver-reader-key")
    assert [r.url.path for r in double.requests] == [
        "/v1/secret/data/identity/clients/channel-simulator",
        "/v1/secret/data/identity/clients/verification-reader",
    ]
    assert all(r.headers["X-Vault-Token"] == TOKEN and r.method == "GET" for r in double.requests)


def test_kind_reads_password_and_totp_seed_of_each_user_from_the_synthetic_users_path() -> None:
    creds, double = _credentials()
    for user in credentials.USERS:
        suffix = user.upper().replace("-", "_")
        assert creds.user_password(user).reveal() == f"pw-{suffix.lower()}-Zq81xk"
        assert (
            creds.user_totp_seed(user).reveal()
            == double.secrets["identity/synthetic-users"][f"SYNTH_{suffix}_TOTP_SEED"]
        )
    assert {r.url.path for r in double.requests} == {"/v1/secret/data/identity/synthetic-users"}
    assert double.count == 1  # el secreto compartido se lee una vez


def test_staging_mount_is_vectra() -> None:
    creds, double = _credentials(STAGING, mount="vectra")
    creds.client_key("verification-reader")
    creds.user_password("analista-1")
    assert [r.url.path for r in double.requests] == [
        "/v1/vectra/data/identity/clients/verification-reader",
        "/v1/vectra/data/identity/synthetic-users",
    ]


def test_staging_refuses_the_cumplimiento_seed_with_zero_requests() -> None:
    creds, double = _credentials(STAGING, mount="vectra")
    with pytest.raises(CredentialsError, match="user_denied_in_staging"):
        creds.user_totp_seed("cumplimiento-1")
    with pytest.raises(CredentialsError, match="user_denied_in_staging"):
        creds.user_password("cumplimiento-1")
    with pytest.raises(CredentialsError, match="user_denied_in_staging"):
        creds.totp("cumplimiento-1", datetime.now(UTC))
    assert double.count == 0


def test_staging_drops_the_cumplimiento_properties_after_reading_the_shared_secret() -> None:
    creds, double = _credentials(STAGING, mount="vectra")
    creds.user_password("analista-1")
    assert double.count == 1
    held = creds.held_properties()
    assert "SYNTH_ANALISTA_1_PASSWORD" in held
    assert not [name for name in held if "CUMPLIMIENTO" in name]
    cumplimiento_values = {
        v for k, v in double.secrets["identity/synthetic-users"].items() if "CUMPLIMIENTO" in k
    }
    assert cumplimiento_values and not cumplimiento_values & creds.secret_values()


def test_kind_keeps_the_cumplimiento_properties() -> None:
    creds, _ = _credentials()
    creds.user_password("analista-1")
    assert "SYNTH_CUMPLIMIENTO_1_TOTP_SEED" in creds.held_properties()


def test_totp_equals_pyotp_at_the_injected_instant() -> None:
    creds, double = _credentials()
    instant = datetime(2026, 11, 12, 10, 0, 7, tzinfo=UTC)
    seed = double.secrets["identity/synthetic-users"]["SYNTH_ANALISTA_1_TOTP_SEED"]
    assert creds.totp("analista-1", instant) == pyotp.TOTP(seed).at(instant)
    assert creds.totp("analista-1", instant) != creds.totp(
        "analista-1", datetime(2026, 11, 12, 10, 5, 0, tzinfo=UTC)
    )


def test_unknown_client_and_user_are_refused_without_requests() -> None:
    creds, double = _credentials()
    with pytest.raises(CredentialsError, match="client_unknown"):
        creds.client_key("case-service")
    with pytest.raises(CredentialsError, match="user_unknown"):
        creds.user_password("operacion-1")
    assert double.count == 0


def test_no_file_is_written_with_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("HOME", "TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"):
        monkeypatch.setenv(name, str(tmp_path))
    import tempfile

    tempfile.tempdir = None  # que `tempfile` relea TMPDIR
    try:
        creds, _ = _credentials()
        creds.client_key("channel-simulator")
        creds.user_password("analista-1")
        creds.totp("analista-1", datetime(2026, 11, 12, tzinfo=UTC))
        repr(creds)
    finally:
        tempfile.tempdir = None
    assert list(tmp_path.rglob("*")) == []
    assert os.getcwd() == str(tmp_path)


def test_credentials_module_has_no_file_writes_by_ast() -> None:
    tree = ast.parse(Path(credentials.__file__).read_text())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "tempfile" not in imported
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            assert not (isinstance(func, ast.Name) and func.id == "open")
            assert not (
                isinstance(func, ast.Attribute)
                and func.attr in {"open", "write_text", "write_bytes", "write", "writelines"}
            )


def test_repr_and_str_show_no_secret() -> None:
    creds, double = _credentials()
    creds.client_key("channel-simulator")
    creds.client_key("verification-reader")
    for user in credentials.USERS:
        creds.user_password(user)
    shown = [
        repr(creds),
        str(creds),
        repr(creds.client_key("channel-simulator")),
        str(creds.user_totp_seed("analista-1")),
    ]
    assert "Credentials(environment='kind'" in shown[0]
    for text in shown:
        for secret in creds.secret_values():
            assert secret not in text


def test_a_403_and_a_missing_path_give_a_clear_error_without_the_token() -> None:
    creds, double = _credentials()
    double.forbidden.add("identity/clients/channel-simulator")
    with pytest.raises(
        CredentialsError, match="vault_status_403:identity/clients/channel-simulator"
    ) as forbidden:
        creds.client_key("channel-simulator")
    del double.secrets["identity/clients/verification-reader"]
    with pytest.raises(
        CredentialsError, match="vault_status_404:identity/clients/verification-reader"
    ) as missing:
        creds.client_key("verification-reader")
    assert TOKEN not in str(forbidden.value) and TOKEN not in str(missing.value)


def test_a_wrong_token_is_a_403_and_the_message_does_not_repeat_it() -> None:
    double = VaultDouble("secret", synthetic_secrets())
    creds = Credentials(KIND, ADDR, "hvs.otro-token-9999", double)
    with pytest.raises(CredentialsError) as error:
        creds.user_password("analista-1")
    assert "hvs.otro-token-9999" not in str(error.value) and "vault_status_403" in str(error.value)


def test_a_missing_property_and_a_bad_response_are_errors() -> None:
    secrets = synthetic_secrets()
    del secrets["identity/clients/channel-simulator"]["private-key"]
    del secrets["identity/synthetic-users"]["SYNTH_ANALISTA_1_PASSWORD"]
    del secrets["identity/synthetic-users"]["SYNTH_ANALISTA_1_TOTP_SEED"]
    creds = Credentials(KIND, ADDR, TOKEN, VaultDouble("secret", secrets))
    with pytest.raises(CredentialsError, match="vault_property_missing:channel-simulator"):
        creds.client_key("channel-simulator")
    with pytest.raises(CredentialsError, match="vault_property_missing:analista-1"):
        creds.user_password("analista-1")
    with pytest.raises(CredentialsError, match="vault_property_missing:analista-1"):
        creds.user_totp_seed("analista-1")


def test_malformed_vault_responses_are_errors() -> None:
    import httpx

    def handler(body: object) -> httpx.MockTransport:
        return httpx.MockTransport(lambda request: httpx.Response(200, json=body))

    for body in ({"x": 1}, {"data": {"data": "texto"}}, {"data": []}):
        with pytest.raises(CredentialsError, match="vault_response_shape"):
            Credentials(KIND, ADDR, TOKEN, handler(body)).client_key("channel-simulator")
    not_json = httpx.MockTransport(lambda request: httpx.Response(200, content=b"no es json"))
    with pytest.raises(CredentialsError, match="vault_response_shape"):
        Credentials(KIND, ADDR, TOKEN, not_json).client_key("channel-simulator")


def test_an_unreachable_vault_is_an_error_without_the_token() -> None:
    import httpx

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"no hay ruta ({request.headers['X-Vault-Token']})")

    with pytest.raises(CredentialsError, match="vault_unreachable") as error:
        Credentials(KIND, ADDR, TOKEN, httpx.MockTransport(boom)).client_key("channel-simulator")
    assert TOKEN not in str(error.value)


def test_from_environ_reads_vault_addr_and_token_and_requires_both() -> None:
    double = VaultDouble("secret", synthetic_secrets())
    creds = Credentials.from_environ(KIND, {"VAULT_ADDR": ADDR, "VAULT_TOKEN": TOKEN}, double)
    creds.user_password("analista-1")
    assert double.requests[0].url.host == "vault.test"
    for environ in (
        {},
        {"VAULT_ADDR": ADDR},
        {"VAULT_TOKEN": TOKEN},
        {"VAULT_ADDR": "", "VAULT_TOKEN": TOKEN},
    ):
        with pytest.raises(CredentialsError, match="vault_session_missing"):
            Credentials.from_environ(KIND, environ, double)


def test_the_vault_token_is_among_the_secrets_the_evidence_filter_checks() -> None:
    creds, _ = _credentials()
    assert TOKEN in creds.secret_values()


def test_an_environment_without_a_vault_is_refused() -> None:
    from vectra_verification.guard import Environment

    with pytest.raises(CredentialsError, match="environment_without_vault"):
        Credentials(Environment("prod", "vectra.banco.internal", "x"), ADDR, TOKEN)
