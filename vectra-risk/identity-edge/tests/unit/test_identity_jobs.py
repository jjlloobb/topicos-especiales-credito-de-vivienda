"""`realm-drift` y `signing-key-age` (U02-T08, CA-3 y CA-4): los jobs contra un Keycloak y un Pushgateway falsos."""

import datetime
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import fake_keycloak as fake
import jobs_design as design
import jwt
import keycloak_admin
import pytest
import realm_drift
import signing_key_age
import yaml
from realm_exports import ENVS, REALM_DIR, keycloak_view, load_git
from vectra_common import deps
from vectra_common.service_token import ASSERTION_TYPE

SIGNED_AT = datetime.datetime(2026, 8, 20, 6, 30, 15, tzinfo=datetime.UTC)


class Environment:
    """Lo que el CronJob recibe: variables de entorno, la llave de `keycloak-reader` y el realm montado."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: str = "kind") -> None:
        self.private, self.public = fake.ec_key_pair()
        key_file = tmp_path / "private-key"
        key_file.write_text(self.private, encoding="utf-8")
        self.realm_file = REALM_DIR / f"realm.{env}.yaml"
        self.token_requests: list[dict[str, Any]] = []
        for name, value in {
            "VECTRA_CLIENT_ID": "keycloak-reader",
            "VECTRA_TOKEN_URL": design.token_url(),
            "VECTRA_CLIENT_KEY_PATH": str(key_file),
            "KEYCLOAK_ADMIN_URL": design.admin_url(),
            "PUSHGATEWAY_URL": design.pushgateway_url(),
            "REALM_FILE": str(self.realm_file),
        }.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr(deps, "post_form_once", self._token_endpoint)
        self.server: fake.FakeKeycloak
        self.pushgateway = fake.FakePushgateway()

    async def _token_endpoint(self, url: str, form: Any, timeout: float) -> Any:
        assert url == design.token_url()
        assert form["grant_type"] == "client_credentials"
        assert form["client_assertion_type"] == ASSERTION_TYPE
        header = jwt.get_unverified_header(form["client_assertion"])
        claims = jwt.decode(
            form["client_assertion"], self.public, algorithms=["ES256"], audience=design.token_url()
        )
        self.token_requests.append({"header": header, "claims": claims})
        return {"access_token": self.server.expected_token, "expires_in": 300}

    def serve(self, realm: dict[str, Any], keys: dict[str, Any] | None = None) -> fake.FakeKeycloak:
        self.server = fake.FakeKeycloak(design.admin_url(), realm, keys)
        return self.server


@pytest.fixture
def env_kind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Environment:
    return Environment(monkeypatch, tmp_path)


async def drift(environment: Environment) -> int:
    return await realm_drift.run_from_env(
        environment.server.get, environment.pushgateway.put, environ=_environ()
    )


def _environ() -> dict[str, str]:
    return dict(os.environ)


# --- realm-drift ------------------------------------------------------------------------------------


@pytest.mark.parametrize("env", ENVS)
async def test_realm_drift_without_changes_pushes_zero(
    env: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = Environment(monkeypatch, tmp_path, env)
    environment.serve(keycloak_view(load_git(env)))
    assert await drift(environment) == 0
    assert environment.pushgateway.puts == [
        (
            design.pushgateway_url() + design.push_paths()["realm-drift"],
            "# TYPE vectra_realm_drift gauge\nvectra_realm_drift 0\n",
        )
    ]


async def test_realm_drift_pushes_the_number_of_differences(env_kind: Environment) -> None:
    kc = keycloak_view(load_git("kind"))
    kc["accessTokenLifespan"] += 1
    kc["requiredActions"] = [a for a in kc["requiredActions"] if a["alias"] != "webauthn-register"]
    kc["roles"]["realm"].append({"name": "rol-sobrante"})
    env_kind.serve(kc)
    assert await drift(env_kind) == 3
    ((url, body),) = env_kind.pushgateway.puts
    assert url == design.pushgateway_url() + "/metrics/job/realm-drift"
    assert body.endswith("vectra_realm_drift 3\n")


async def test_realm_drift_asks_for_the_token_with_an_es256_assertion_of_the_reader(
    env_kind: Environment,
) -> None:
    env_kind.serve(keycloak_view(load_git("kind")))
    await drift(env_kind)
    assert env_kind.token_requests, "no pidio token"
    first = env_kind.token_requests[0]
    assert first["header"]["alg"] == "ES256"
    assert first["claims"]["iss"] == first["claims"]["sub"] == "keycloak-reader"
    assert first["claims"]["aud"] == design.token_url()
    assert env_kind.server.tokens_seen == {f"Bearer {env_kind.server.expected_token}"}


async def test_realm_drift_reads_the_users_one_by_one_and_never_lists_them(env_kind: Environment) -> None:
    git = load_git("kind")
    kc = keycloak_view(git)
    kc["users"].append({"username": "importado-de-ldap", "enabled": True})
    env_kind.serve(kc)
    await drift(env_kind)
    lookups = [q for p, q in env_kind.server.requests if p == "/users"]
    assert sorted(q["username"] for q in lookups) == sorted(u["username"] for u in git["users"])
    assert all(q["exact"] == "true" for q in lookups)
    assert all(set(q) == {"username", "exact"} for q in lookups)
    assert "importado-de-ldap" not in {q["username"] for q in lookups}
    assert all(not p.endswith("/users") or q for p, q in env_kind.server.requests)


async def test_realm_drift_a_user_of_git_missing_in_keycloak_counts_one(env_kind: Environment) -> None:
    kc = keycloak_view(load_git("kind"))
    kc["users"] = [u for u in kc["users"] if u["username"] != "cro-1"]
    env_kind.serve(kc)
    assert await drift(env_kind) == 1


async def test_realm_drift_does_not_read_the_keys_or_write_anything(env_kind: Environment) -> None:
    env_kind.serve(keycloak_view(load_git("kind")))
    await drift(env_kind)
    assert all(p != "/keys" for p, _ in env_kind.server.requests)
    assert len(env_kind.pushgateway.puts) == 1


async def test_realm_drift_only_reads_the_component_types_of_git() -> None:
    # En kind no hay componentes en Git: no se pide ninguno (los de Keycloak son suyos).
    assert "components" not in load_git("kind")


async def test_realm_drift_prod_reads_the_ldap_components(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = Environment(monkeypatch, tmp_path, "prod")
    environment.serve(keycloak_view(load_git("prod")))
    await drift(environment)
    assert [q for p, q in environment.server.requests if p == "/components"] == [
        {"type": "org.keycloak.storage.UserStorageProvider"}
    ]


def test_realm_drift_main_fails_without_pushing_when_keycloak_fails(
    env_kind: Environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(url: str, headers: Any) -> Any:
        raise OSError("keycloak no responde")

    env_kind.serve(keycloak_view(load_git("kind")))
    monkeypatch.setattr(keycloak_admin, "urllib_get", broken)
    monkeypatch.setattr(keycloak_admin, "urllib_put", env_kind.pushgateway.put)
    assert realm_drift.main() == 1
    assert env_kind.pushgateway.puts == []


def test_realm_drift_main_succeeds_and_pushes_through_the_injected_transport(
    env_kind: Environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_kind.serve(keycloak_view(load_git("kind")))
    monkeypatch.setattr(keycloak_admin, "urllib_get", env_kind.server.get)
    monkeypatch.setattr(keycloak_admin, "urllib_put", env_kind.pushgateway.put)
    assert realm_drift.main() == 0
    assert len(env_kind.pushgateway.puts) == 1


# --- signing-key-age --------------------------------------------------------------------------------


def key(kid: str, **fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kid": kid, "status": "ACTIVE", "use": "SIG", "algorithm": "RS256", "providerPriority": 100,
        "type": "RSA", "providerId": "rsa-generated",
    }  # fmt: skip
    return {**base, **fields}


def several_keys() -> dict[str, Any]:
    day = datetime.timedelta(days=1)
    return {
        "keys": [
            key(
                "pasiva",
                status="PASSIVE",
                providerPriority=900,
                certificate=fake.certificate(SIGNED_AT - 30 * day),
            ),
            key(
                "cifrado", use="ENC", providerPriority=800, certificate=fake.certificate(SIGNED_AT - 40 * day)
            ),
            key(
                "otro-algoritmo",
                algorithm="ES256",
                providerPriority=700,
                certificate=fake.certificate(SIGNED_AT - 50 * day),
            ),
            key("menor-prioridad", providerPriority=50, certificate=fake.certificate(SIGNED_AT - 60 * day)),
            key("la-correcta", providerPriority=100, certificate=fake.certificate(SIGNED_AT)),
            key(
                "desactivada",
                status="DISABLED",
                providerPriority=950,
                certificate=fake.certificate(SIGNED_AT - 70 * day),
            ),
        ]
    }


async def signing(environment: Environment) -> int:
    return await signing_key_age.run_from_env(
        environment.server.get, environment.pushgateway.put, environ=_environ()
    )


async def test_signing_key_age_chooses_the_right_key_among_several(env_kind: Environment) -> None:
    env_kind.serve(keycloak_view(load_git("kind")), several_keys())
    assert await signing(env_kind) == int(SIGNED_AT.timestamp())
    assert env_kind.pushgateway.puts == [
        (
            design.pushgateway_url() + design.push_paths()["signing-key-age"],
            "# TYPE vectra_signing_key_created_timestamp_seconds gauge\n"
            f'vectra_signing_key_created_timestamp_seconds{{kid="la-correcta",algorithm="RS256"}} {int(SIGNED_AT.timestamp())}\n',
        )
    ]
    assert env_kind.token_requests[0]["claims"]["iss"] == "keycloak-reader"


async def test_signing_key_age_uses_the_default_signature_algorithm_of_the_realm(
    env_kind: Environment,
) -> None:
    keys = several_keys()
    env_kind.serve(keycloak_view(load_git("kind")), keys)
    original = env_kind.server._route

    def route(path: str, query: dict[str, str]) -> Any:
        found = original(path, query)
        return {**found, "defaultSignatureAlgorithm": "ES256"} if path == "" else found

    env_kind.server._route = route  # type: ignore[method-assign]
    await signing(env_kind)
    ((_, body),) = env_kind.pushgateway.puts
    assert 'kid="otro-algoritmo",algorithm="ES256"' in body


@pytest.mark.parametrize(
    "mutate",
    [
        lambda keys: keys["keys"].pop(4),  # sin la correcta, queda la de menor prioridad
    ],
    ids=["lower-priority-wins-only-when-alone"],
)
async def test_signing_key_age_falls_back_to_the_next_priority_only_when_the_best_is_gone(
    env_kind: Environment, mutate: Callable[[dict[str, Any]], Any]
) -> None:
    keys = several_keys()
    mutate(keys)
    env_kind.serve(keycloak_view(load_git("kind")), keys)
    await signing(env_kind)
    ((_, body),) = env_kind.pushgateway.puts
    assert 'kid="menor-prioridad"' in body


@pytest.mark.parametrize(
    "keys",
    [
        {"keys": [key("sin-certificado")]},
        {"keys": [key("certificado-vacio", certificate="")]},
        {"keys": [key("certificado-roto", certificate="no-es-base64!")]},
        {"keys": [key("der-roto", certificate="AAAA")]},
        {"keys": []},
        {"keys": [key("pasiva", status="PASSIVE", certificate=fake.certificate(SIGNED_AT))]},
        {
            "keys": [
                key("a", certificate=fake.certificate(SIGNED_AT)),
                key("b", certificate=fake.certificate(SIGNED_AT)),
            ]
        },
    ],
    ids=["no-certificate", "empty-certificate", "not-base64", "not-der", "no-keys", "only-passive", "tie"],
)
def test_signing_key_age_fails_without_pushing_when_there_is_no_usable_certificate(
    env_kind: Environment, monkeypatch: pytest.MonkeyPatch, keys: dict[str, Any]
) -> None:
    env_kind.serve(keycloak_view(load_git("kind")), keys)
    monkeypatch.setattr(keycloak_admin, "urllib_get", env_kind.server.get)
    monkeypatch.setattr(keycloak_admin, "urllib_put", env_kind.pushgateway.put)
    assert signing_key_age.main() == 1
    assert env_kind.pushgateway.puts == []


def test_signing_key_age_main_succeeds_through_the_injected_transport(
    env_kind: Environment, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_kind.serve(keycloak_view(load_git("kind")), several_keys())
    monkeypatch.setattr(keycloak_admin, "urllib_get", env_kind.server.get)
    monkeypatch.setattr(keycloak_admin, "urllib_put", env_kind.pushgateway.put)
    assert signing_key_age.main() == 0
    assert len(env_kind.pushgateway.puts) == 1


def test_the_label_values_are_escaped() -> None:
    body = signing_key_age.metrics_body('a"b\\c\nd', "RS256", 5).decode()
    assert 'kid="a\\"b\\\\c\\nd"' in body


def test_the_jobs_read_the_realm_file_as_it_is_in_git() -> None:
    for env in ENVS:
        assert yaml.safe_load((REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8")) == load_git(env)
