"""CA-2 (U04-T08; INF-U4-01, F47, F24, F25, F50): `config_from_env` de `governance-service`. Una prueba por variable obligatoria ausente (el mensaje la nombra) y la
comparacion de los nombres con las variables del Deployment que renderiza el chart de U04-T06: ninguna sobra ni falta."""

from pathlib import Path

import pytest
from test_chart import render, service_container
from vectra_governance.service import OPTIONAL, REQUIRED, ConfigError, config_from_env

#: Un valor distinto por variable, para ver que cada una llega a su campo.
FULL = {name: f"valor-de-{name.lower()}" for name in REQUIRED}


def chart_env() -> list[str]:
    return [e["name"] for e in service_container(render())["env"]]


def test_the_required_names_are_exactly_the_variables_of_the_rendered_deployment() -> None:
    names = chart_env()
    assert len(names) == len(set(names))
    assert set(REQUIRED) - set(names) == set(), "el codigo exige variables que el chart no pone"
    assert set(names) - set(REQUIRED) == set(), "el chart pone variables que el codigo no lee"


def test_the_optional_variables_are_not_in_the_chart_and_the_peer_and_identity_ones_are_required() -> None:
    assert set(OPTIONAL) & set(chart_env()) == set()
    assert not set(OPTIONAL) & set(REQUIRED)
    peers = {"GOVERNANCE_REGISTRY_URL", "GOVERNANCE_BIAS_URL", "VECTRA_CLIENT_ID", "VECTRA_CLIENT_KEY_PATH", "VECTRA_TOKEN_URL", "VECTRA_ASSERTION_AUDIENCE"}
    assert peers <= set(REQUIRED) and peers <= set(chart_env())


@pytest.mark.parametrize("name", REQUIRED)
def test_a_missing_required_variable_fails_naming_it(name: str) -> None:
    env = {k: v for k, v in FULL.items() if k != name}
    with pytest.raises(ConfigError, match=name):
        config_from_env(env)


@pytest.mark.parametrize("name", REQUIRED)
def test_an_empty_required_variable_is_missing_too(name: str) -> None:
    with pytest.raises(ConfigError, match=name):
        config_from_env({**FULL, name: ""})


def test_all_the_missing_ones_are_named_together() -> None:
    with pytest.raises(ConfigError) as error:
        config_from_env({})
    assert all(name in str(error.value) for name in REQUIRED)


def test_every_variable_reaches_its_field_and_no_secret_leaks_into_the_message() -> None:
    config = config_from_env(FULL)
    assert (config.dsn, config.s3_endpoint, config.s3_access_key, config.s3_secret_key, config.ca_bundle) == (
        FULL["GOVERNANCE_DATABASE_DSN"],
        FULL["GOVERNANCE_S3_ENDPOINT"],
        FULL["GOVERNANCE_S3_ACCESS_KEY"],
        FULL["GOVERNANCE_S3_SECRET_KEY"],
        FULL["VECTRA_CA_BUNDLE"],
    )
    api = config.api
    assert (api.validation_image, api.validation_dataset, api.callback_url, api.job_s3_endpoint, api.job_token_url) == (
        FULL["GOVERNANCE_VALIDATION_IMAGE"],
        FULL["GOVERNANCE_VALIDATION_DATASET"],
        FULL["GOVERNANCE_CALLBACK_URL"],
        FULL["GOVERNANCE_JOB_S3_ENDPOINT"],
        FULL["GOVERNANCE_JOB_TOKEN_URL"],
    )
    with pytest.raises(ConfigError) as error:
        config_from_env({k: v for k, v in FULL.items() if k != "PGUSER"})
    assert FULL["PGPASSWORD"] not in str(error.value) and FULL["GOVERNANCE_S3_SECRET_KEY"] not in str(error.value)


def test_the_identity_and_peers_come_from_the_environment_without_defaults() -> None:
    config = config_from_env(FULL)
    assert (config.registry_url, config.bias_url, config.client_id, config.client_key_path, config.token_url) == (
        FULL["GOVERNANCE_REGISTRY_URL"],
        FULL["GOVERNANCE_BIAS_URL"],
        FULL["VECTRA_CLIENT_ID"],
        FULL["VECTRA_CLIENT_KEY_PATH"],
        FULL["VECTRA_TOKEN_URL"],  # F-03: el token propio no usa GOVERNANCE_JOB_TOKEN_URL
    )
    assert config.token_url != FULL["GOVERNANCE_JOB_TOKEN_URL"] == config.api.job_token_url
    assert config.assertion_audience == FULL["VECTRA_ASSERTION_AUDIENCE"] != config.token_url
    assert config.api.assertion_audience == config.assertion_audience  # el Job recibe la misma (P-2)
    assert (config.client_key_id, config.replica) == (None, config.replica)
    over = config_from_env({**FULL, "VECTRA_CLIENT_KEY_ID": "kid", "GOVERNANCE_REPLICA": "pod-7"})
    assert (over.client_key_id, over.replica) == ("kid", "pod-7")


# --- Tokens de servicio y cliente de Kubernetes del arranque ------------------------------------------------------------------


def test_the_service_token_needs_the_client_key_but_its_absence_is_a_503_not_a_boot_failure(tmp_path: Path) -> None:
    from vectra_common.errors import DependencyUnavailable
    from vectra_contracts.catalog import Scope
    from vectra_governance.service import service_tokens

    config = config_from_env({**FULL, "VECTRA_CLIENT_KEY_PATH": str(tmp_path / "no-esta")})
    token = service_tokens(config)("decision-registry-service", (Scope.REGISTRY_APPEND_GOVERNANCE,))
    with pytest.raises(DependencyUnavailable):
        token()


def test_assertion_audience_the_service_token_is_a_private_key_jwt_for_the_audience_and_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from vectra_common import deps
    from vectra_contracts.catalog import Scope
    from vectra_governance.service import service_tokens

    key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    (tmp_path / "private-key").write_bytes(key)
    posts: list[dict[str, str]] = []

    async def post(url: str, data: dict[str, str], timeout: float) -> dict[str, object]:
        posts.append({"url": url, **data})
        return {"access_token": "tok-1", "expires_in": 300}

    monkeypatch.setattr(deps, "post_form_once", post)
    config = config_from_env({**FULL, "VECTRA_CLIENT_KEY_PATH": str(tmp_path / "private-key")})
    token = service_tokens(config)("bias-monitoring-service", (Scope.BIAS_COMPARE,))
    assert token() == "tok-1" and token() == "tok-1"  # el segundo sale de la cache del proveedor
    assert len(posts) == 1
    assert posts[0]["url"] == FULL["VECTRA_TOKEN_URL"]
    import jwt

    claims = jwt.decode(posts[0]["client_assertion"], options={"verify_signature": False})
    assert claims["aud"] == FULL["VECTRA_ASSERTION_AUDIENCE"] != FULL["VECTRA_TOKEN_URL"]
    assert (posts[0]["audience"], posts[0]["scope"]) == ("bias-monitoring-service", "bias:compare")


def test_the_kubernetes_client_is_in_cluster_and_without_a_serviceaccount_it_fails_when_used(monkeypatch: pytest.MonkeyPatch) -> None:
    from vectra_common.errors import DependencyUnavailable
    from vectra_governance import service

    monkeypatch.setattr(service, "SERVICEACCOUNT", Path("/no/hay/serviceaccount"))
    client = service.kubernetes_client({"KUBERNETES_SERVICE_HOST": "10.0.0.1", "KUBERNETES_SERVICE_PORT": "6443"})
    assert str(client._client.base_url) == "https://10.0.0.1:6443"  # noqa: SLF001
    with pytest.raises(DependencyUnavailable):
        client.get("validation-1")


def test_the_kubernetes_client_sends_the_serviceaccount_token_and_trusts_its_ca(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vectra_governance import service

    (tmp_path / "token").write_text("sa-token\n")
    monkeypatch.setattr(service, "SERVICEACCOUNT", tmp_path)
    client = service.kubernetes_client({})
    assert str(client._client.base_url) == "https://kubernetes.default.svc"  # httpx omite el 443  # noqa: SLF001
    assert client._token() == "sa-token"  # noqa: SLF001
