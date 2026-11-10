"""`realm-drift` y `signing-key-age` (U02-T08, CA-3 y CA-4): los jobs contra un Keycloak y un Pushgateway falsos."""

import copy
import datetime
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import fake_keycloak as fake
import jobs_checks as jc
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


def _without_algorithm(server: fake.FakeKeycloak, value: Any) -> None:
    original = server._route

    def route(path: str, query: dict[str, str]) -> Any:
        found = original(path, query)
        if path != "":
            return found
        found = dict(found)
        found.pop("defaultSignatureAlgorithm")
        if value is not None:
            found["defaultSignatureAlgorithm"] = value
        return found

    server._route = route  # type: ignore[method-assign]


@pytest.mark.parametrize("value", [None, "", "  "], ids=["absent", "empty", "blank"])
def test_f04_without_the_default_signature_algorithm_the_job_fails_without_pushing(
    env_kind: Environment, monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    env_kind.serve(keycloak_view(load_git("kind")), several_keys())
    _without_algorithm(env_kind.server, value)
    monkeypatch.setattr(keycloak_admin, "urllib_get", env_kind.server.get)
    monkeypatch.setattr(keycloak_admin, "urllib_put", env_kind.pushgateway.put)
    assert signing_key_age.main() == 1
    assert env_kind.pushgateway.puts == []
    assert not hasattr(signing_key_age, "KEYCLOAK_DEFAULT_ALGORITHM")


async def test_the_reader_does_not_read_credentials_nor_the_executions_of_keycloak_flows(
    env_kind: Environment,
) -> None:
    kc = keycloak_view(load_git("kind"))
    kc["authenticationFlows"].append(
        {"alias": "puerta-trasera", "builtIn": True, "authenticationExecutions": []}
    )
    env_kind.serve(kc)
    assert await drift(env_kind) == 1
    paths = [p for p, _ in env_kind.server.requests]
    assert not [p for p in paths if p.endswith("/credentials")]
    assert "/authentication/flows/browser/executions" not in paths
    assert "/authentication/flows/puerta-trasera/executions" in paths


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


# =====================================================================================================
# CA-4: manifiestos de los dos CronJobs (`-k render`)
# =====================================================================================================

Docs = list[dict[str, Any]]
IMAGE_REPOSITORY = {
    "kind": design.image_repositories()[1],
    "staging": design.image_repositories()[0],
    "prod": design.image_repositories()[0],
}


def _image(env: str) -> str:
    values = yaml.safe_load(jc.values_file(env).read_text(encoding="utf-8"))
    assert values["image"]["repository"] == IMAGE_REPOSITORY[env]
    return f"{values['image']['repository']}@{values['image']['digest']}"


@pytest.fixture(params=jc.ENVS)
def render_env(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def test_render_the_versioned_render_is_the_one_of_now(render_env: str) -> None:
    for name in jc.FILES:
        result = jc.render_file(render_env, name)
        assert result.returncode == 0, result.stderr
        assert result.stdout == (jc.RENDERED / render_env / name).read_text(encoding="utf-8")
    assert jc.load(jc.render(render_env).stdout) != [] and len(jc.versioned(render_env)) == 5


def test_t1_the_realm_configmap_has_its_own_file(render_env: str) -> None:
    config_map = jc.load((jc.RENDERED / render_env / "realm-configmap.yaml").read_text(encoding="utf-8"))
    assert [(d["kind"], d["metadata"]["name"]) for d in config_map] == [("ConfigMap", "realm-drift-realm")]
    rest = jc.load((jc.RENDERED / render_env / "identity-jobs.yaml").read_text(encoding="utf-8"))
    assert sorted((d["kind"], d["metadata"]["name"]) for d in rest) == [
        ("CronJob", "realm-drift"),
        ("CronJob", "signing-key-age"),
        ("ServiceAccount", "realm-drift"),
        ("ServiceAccount", "signing-key-age"),
    ]


def _workflow() -> str:
    return (jc.EDGE.parent.parent / ".github" / "workflows" / "supply-chain.yml").read_text(encoding="utf-8")


_KIND_KEYCLOAK = "vectra-risk/identity-edge/keycloak/rendered/kind/keycloak.yaml"


def _expected_skip_files() -> list[str]:
    return [
        "vectra-risk/platform/secrets/eso-rbac-secrets-read-kind.yaml",
        *(f"vectra-risk/identity-edge/jobs/rendered/{env}/realm-configmap.yaml" for env in jc.ENVS),
        "vectra-risk/identity-edge/keycloak/rendered/kind/config-cli-realm.yaml",
    ]


def _skipped(text: str) -> list[str]:
    workflow = yaml.safe_load(text)
    (step,) = [
        s for job in workflow["jobs"].values() for s in job["steps"] if "trivy-action" in s.get("uses", "")
    ]
    return [f.strip() for f in step["with"]["skip-files"].split(",")]


def _assert_skip_files(text: str) -> None:
    skipped = _skipped(text)
    assert skipped == _expected_skip_files()
    assert not [f for f in skipped if any(c in f for c in "*?[")]
    for f in skipped:
        assert (jc.EDGE.parent / f.removeprefix("vectra-risk/")).is_file()
    assert _KIND_KEYCLOAK not in skipped
    assert not [f for f in skipped if "keycloak/rendered/staging" in f or "keycloak/rendered/prod" in f]
    assert "KSV-0109" in text and "realm-lint" in text
    assert "trivyignores: vectra-risk/.trivyignore" in text and "scanners: vuln,misconfig,secret" in text


def test_t1_supply_chain_skips_exactly_the_realm_configmaps_and_the_kind_secret_read() -> None:
    """Decision T1 (U02-T08, KSV-0109) plus the U02-T19 ConfigMap split (PR 85) and KSV-0041 (kind only)."""
    _assert_skip_files(_workflow())


def _mutated(old: str, new: str) -> str:
    text = _workflow()
    line = next(ln for ln in text.splitlines() if "skip-files:" in ln)
    assert old in line
    return text.replace(line, line.replace(old, new))


@pytest.mark.parametrize("index", range(5))
def test_t1_supply_chain_skip_list_fails_when_an_entry_is_removed(index: int) -> None:
    entry = _expected_skip_files()[index]
    mutated = _mutated(entry, "")
    mutated = "\n".join(ln.replace(": ,", ": ").replace(",,", ",").rstrip(",") for ln in mutated.splitlines())
    with pytest.raises(AssertionError):
        _assert_skip_files(mutated)


@pytest.mark.parametrize(
    "extra", [_KIND_KEYCLOAK, "vectra-risk/identity-edge/keycloak/rendered/*/keycloak.yaml"]
)
def test_t1_supply_chain_skip_list_fails_when_an_entry_or_wildcard_is_added(extra: str) -> None:
    last = _expected_skip_files()[-1]
    with pytest.raises(AssertionError):
        _assert_skip_files(_mutated(last, f"{last},{extra}"))


def test_t1_trivyignore_mentions_the_new_skip() -> None:
    text = (jc.EDGE.parent / ".trivyignore").read_text(encoding="utf-8")
    assert "KSV-0109" in text and "realm-configmap.yaml" in text and "KSV-0041" in text


def test_render_the_exact_set_of_documents(render_env: str) -> None:
    docs = jc.versioned(render_env)
    assert sorted((d["kind"], d["metadata"]["name"], d["metadata"]["namespace"]) for d in docs) == [
        ("ConfigMap", "realm-drift-realm", "vectra-identity"),
        ("CronJob", "realm-drift", "vectra-identity"),
        ("CronJob", "signing-key-age", "vectra-identity"),
        ("ServiceAccount", "realm-drift", "vectra-identity"),
        ("ServiceAccount", "signing-key-age", "vectra-identity"),
    ]
    assert [
        d["metadata"]["name"] for d in docs if d["kind"] == "ServiceAccount"
    ] == design.service_accounts()[:2] or sorted(
        d["metadata"]["name"] for d in docs if d["kind"] == "ServiceAccount"
    ) == sorted(design.service_accounts())


def test_render_every_document_is_the_expected_one_complete(render_env: str) -> None:
    docs = jc.versioned(render_env)
    expected = jc.expected_documents(render_env, _image(render_env))
    for want in expected:
        got = jc.find(docs, want["kind"], want["metadata"]["name"])
        assert got == want, f"{want['kind']} {want['metadata']['name']} difiere del esperado"
    assert len(docs) == len(expected)


def test_render_design_values(render_env: str) -> None:
    docs = jc.versioned(render_env)
    schedules, paths = design.schedules(), design.push_paths()
    assert set(schedules) == set(paths) == {"realm-drift", "signing-key-age"}
    for name in schedules:
        job = jc.find(docs, "CronJob", name)
        spec = job["spec"]
        pod = spec["jobTemplate"]["spec"]["template"]["spec"]
        assert spec["schedule"] == schedules[name]
        assert spec["concurrencyPolicy"] == design.concurrency_policy()
        assert pod["serviceAccountName"] == name and pod["priorityClassName"] == design.priority_class()
        assert pod["containers"][0]["resources"] == design.resources()
        env = {e["name"]: e["value"] for e in pod["containers"][0]["env"]}
        assert env["KEYCLOAK_ADMIN_URL"] == design.admin_url()
        assert env["VECTRA_TOKEN_URL"] == design.token_url()
        assert env["PUSHGATEWAY_URL"] == design.pushgateway_url()
        assert env["VECTRA_CLIENT_ID"] == "keycloak-reader"
        repository, digest = pod["containers"][0]["image"].split("@")
        assert repository == IMAGE_REPOSITORY[render_env] and len(digest) == len("sha256:") + 64


def test_render_the_realm_configmap_is_the_realm_file_of_the_environment(render_env: str) -> None:
    config_map = jc.find(jc.versioned(render_env), "ConfigMap", "realm-drift-realm")
    assert config_map["data"] == {"realm.yaml": jc.realm_file(render_env).read_text(encoding="utf-8")}
    assert yaml.safe_load(config_map["data"]["realm.yaml"]) == load_git(render_env)


def test_render_the_realm_configmaps_of_the_environments_differ() -> None:
    texts = {
        env: jc.find(jc.versioned(env), "ConfigMap", "realm-drift-realm")["data"]["realm.yaml"]
        for env in jc.ENVS
    }
    assert len(set(texts.values())) == 3


def test_render_there_is_no_plain_secret(render_env: str) -> None:
    assert not [d for d in jc.versioned(render_env) if d["kind"] in {"Secret", "ExternalSecret"}]
    for name in jc.FILES:
        text = (jc.RENDERED / render_env / name).read_text(encoding="utf-8")
        assert "kind: Secret\n" not in text


@pytest.mark.parametrize(
    "extra", [["--set", "image.digest="], ["--set", "image.digest=null"]], ids=["empty", "null"]
)
def test_render_fails_without_digest(render_env: str, extra: list[str]) -> None:
    result = jc.render(render_env, *extra)
    assert result.returncode != 0
    assert "digest" in result.stderr


def test_render_fails_without_the_realm_of_git(render_env: str) -> None:
    result = jc.render(render_env, realm=False)
    assert result.returncode != 0
    assert "realm" in result.stderr


def test_render_fails_without_repository(render_env: str) -> None:
    result = jc.render(render_env, "--set", "image.repository=")
    assert result.returncode != 0 and "repository" in result.stderr


# --- las politicas: cada regla falla sobre un render alterado ---------------------------------------------


def _cron(docs: Docs, name: str = "realm-drift") -> dict[str, Any]:
    return jc.find(docs, "CronJob", name)


def _pod(docs: Docs, name: str = "realm-drift") -> dict[str, Any]:
    return _cron(docs, name)["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def _container(docs: Docs, name: str = "realm-drift") -> dict[str, Any]:
    return _pod(docs, name)["containers"][0]


def _env(docs: Docs, var: str, name: str = "realm-drift") -> dict[str, Any]:
    (found,) = [e for e in _container(docs, name)["env"] if e["name"] == var]
    return found


def _set_cron(path: list[str | int], value: Any, name: str = "realm-drift") -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = _cron(docs, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _pod_set(key: str, value: Any, name: str = "realm-drift") -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _pod(docs, name)[key] = value

    return mutate


def _container_set(key: str, value: Any, name: str = "realm-drift") -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs, name)[key] = value

    return mutate


def _env_set(var: str, value: Any, name: str = "realm-drift") -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _env(docs, var, name)["value"] = value

    return mutate


def _env_drop(var: str, name: str = "realm-drift") -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _container(docs, name)["env"].remove(_env(docs, var, name))

    return mutate


def _env_add(docs: Docs) -> None:
    _container(docs)["env"].append({"name": "OTRA", "value": "x"})


def _env_from_secret(docs: Docs) -> None:
    _env(docs, "VECTRA_CLIENT_ID").pop("value")
    _env(docs, "VECTRA_CLIENT_ID")["valueFrom"] = {"secretKeyRef": {"name": "x", "key": "y"}}


def _volume(docs: Docs, name: str, who: str = "realm-drift") -> dict[str, Any]:
    (found,) = [v for v in _pod(docs, who)["volumes"] if v["name"] == name]
    return found


def _drop_volume(name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        _pod(docs)["volumes"].remove(_volume(docs, name))

    return mutate


def _volume_set(name: str, path: list[str], value: Any) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        node: Any = _volume(docs, name)
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _add_volume(docs: Docs) -> None:
    _pod(docs)["volumes"].append({"name": "extra", "emptyDir": {}})


def _mount_rw(docs: Docs) -> None:
    _container(docs)["volumeMounts"][0]["readOnly"] = False


def _signing_realm(docs: Docs) -> None:
    pod = _pod(docs, "signing-key-age")
    pod["volumes"].append(
        {
            "name": "realm",
            "configMap": {
                "name": "realm-drift-realm",
                "items": [{"key": "realm.yaml", "path": "realm.yaml"}],
            },
        }
    )
    pod["containers"][0]["volumeMounts"].append(
        {"name": "realm", "mountPath": "/etc/vectra/realm", "readOnly": True}
    )


def _drop_doc(kind: str, name: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.remove(jc.find(docs, kind, name))

    return mutate


def _add_doc(doc: dict[str, Any]) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        docs.append(copy.deepcopy(doc))

    return mutate


def _cm_key(docs: Docs) -> None:
    jc.find(docs, "ConfigMap", "realm-drift-realm")["data"]["otro.yaml"] = "x"


def _sidecar_off(docs: Docs) -> None:
    _cron(docs)["spec"]["jobTemplate"]["spec"]["template"]["metadata"]["annotations"] = {}


def _no_resources_limit(docs: Docs) -> None:
    del _container(docs)["resources"]["limits"]


def _drop_security(docs: Docs) -> None:
    _container(docs)["securityContext"]["readOnlyRootFilesystem"] = False


def _root_pod(docs: Docs) -> None:
    _pod(docs)["securityContext"]["runAsNonRoot"] = False


def _seccomp(docs: Docs) -> None:
    _pod(docs)["securityContext"]["seccompProfile"] = {"type": "Unconfined"}


def _sa_automount(docs: Docs) -> None:
    jc.find(docs, "ServiceAccount", "realm-drift")["automountServiceAccountToken"] = False


def _sa_secrets(docs: Docs) -> None:
    jc.find(docs, "ServiceAccount", "realm-drift")["secrets"] = [{"name": "x"}]


def _init_container(docs: Docs) -> None:
    _pod(docs)["initContainers"] = [{"name": "i", "image": "x"}]


def _second_container(docs: Docs) -> None:
    _pod(docs)["containers"].append({"name": "otro", "image": "x"})


def _wrong_namespace(docs: Docs) -> None:
    _cron(docs)["metadata"]["namespace"] = "default"


def _renamed_cron(docs: Docs) -> None:
    _cron(docs)["metadata"]["name"] = "otro-job"


def _config_map_namespace(docs: Docs) -> None:
    jc.find(docs, "ConfigMap", "realm-drift-realm")["metadata"]["namespace"] = "default"


def _config_map_name(docs: Docs) -> None:
    jc.find(docs, "ConfigMap", "realm-drift-realm")["metadata"]["name"] = "otro-realm"


def _extra_sa(docs: Docs) -> None:
    docs.append(
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {"name": "otra", "namespace": jc.NAMESPACE},
        }
    )


def _sa_other_namespace(docs: Docs) -> None:
    jc.find(docs, "ServiceAccount", "signing-key-age")["metadata"]["namespace"] = "default"


def _digest(value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        repo = _container(docs)["image"].split("@")[0]
        _container(docs)["image"] = repo + value

    return mutate


def _repo(value: str) -> Callable[[Docs], None]:
    def mutate(docs: Docs) -> None:
        digest = _container(docs)["image"].split("@")[1]
        _container(docs)["image"] = f"{value}@{digest}"

    return mutate


# (regla, id, mutacion) -> el mensaje de conftest empieza por la regla.
PER_DOCUMENT: list[tuple[str, str, Callable[[Docs], None]]] = [
    ("cronjob-shape", "name-outside-the-list", _renamed_cron),
    ("cronjob-shape", "namespace", _wrong_namespace),
    ("cronjob-shape", "second-container", _second_container),
    ("cronjob-shape", "init-container", _init_container),
    ("cronjob-shape", "restart-policy", _pod_set("restartPolicy", "OnFailure")),
    ("schedule", "realm-drift-hourly", _set_cron(["spec", "schedule"], "0 * * * *")),
    ("schedule", "signing-key-age-daily", _set_cron(["spec", "schedule"], "0 3 * * *", "signing-key-age")),
    ("schedule", "time-zone", _set_cron(["spec", "timeZone"], "America/Bogota")),
    ("concurrency", "allow", _set_cron(["spec", "concurrencyPolicy"], "Allow")),
    ("concurrency", "replace", _set_cron(["spec", "concurrencyPolicy"], "Replace", "signing-key-age")),
    ("service-account", "other-account", _pod_set("serviceAccountName", "signing-key-age")),
    ("service-account", "default-account", _pod_set("serviceAccountName", "default", "signing-key-age")),
    ("priority", "high", _pod_set("priorityClassName", "vectra-high")),
    ("priority", "none", _pod_set("priorityClassName", "", "signing-key-age")),
    ("resources", "no-limits", _no_resources_limit),
    ("resources", "bigger-memory", lambda d: _container(d)["resources"]["limits"].update(memory="1Gi")),
    (
        "resources",
        "bigger-request",
        lambda d: _container(d, "signing-key-age")["resources"]["requests"].update(cpu="1"),
    ),
    ("image", "tag-only", _container_set("image", "kind-registry:5000/vectra/identity-jobs:1")),
    ("image", "other-repository", _repo("docker.io/library/python")),
    ("image", "short-digest", _digest("@sha256:abc")),
    ("image", "upper-digest", _digest("@sha256:" + "A" * 64)),
    ("command", "other-script", _container_set("command", ["python", "/app/signing_key_age.py"])),
    (
        "command",
        "shell",
        _container_set("command", ["sh", "-c", "python /app/realm_drift.py"], "signing-key-age"),
    ),
    (
        "env",
        "admin-url",
        _env_set("KEYCLOAK_ADMIN_URL", "https://keycloak.vectra-identity.svc:8443/auth/admin/realms/vectra"),
    ),
    (
        "env",
        "token-url",
        _env_set(
            "VECTRA_TOKEN_URL",
            "https://keycloak/auth/realms/vectra/protocol/openid-connect/token",
            "signing-key-age",
        ),
    ),
    ("env", "pushgateway", _env_set("PUSHGATEWAY_URL", "http://pushgateway.vectra-observability.svc:9092")),
    ("env", "client-id", _env_set("VECTRA_CLIENT_ID", "keycloak-config-cli")),
    ("env", "key-path", _env_set("VECTRA_CLIENT_KEY_PATH", "/var/key")),
    ("env", "missing-variable", _env_drop("VECTRA_CA_BUNDLE")),
    ("env", "realm-file-missing", _env_drop("REALM_FILE")),
    ("env", "extra-variable", _env_add),
    ("env", "from-secret", _env_from_secret),
    (
        "volumes",
        "key-from-other-secret",
        _volume_set("reader-key", ["secret", "secretName"], "keycloak-config-cli-client"),
    ),
    (
        "volumes",
        "key-property",
        _volume_set("reader-key", ["secret", "items"], [{"key": "otra", "path": "private-key"}]),
    ),
    (
        "volumes",
        "ca-from-other-secret",
        _volume_set("identity-ca", ["secret", "secretName"], "vectra-internal-ca"),
    ),
    (
        "volumes",
        "ca-property",
        _volume_set("identity-ca", ["secret", "items"], [{"key": "tls.crt", "path": "ca.crt"}]),
    ),
    ("volumes", "realm-missing", _drop_volume("realm")),
    ("volumes", "realm-other-configmap", _volume_set("realm", ["configMap", "name"], "otro")),
    ("volumes", "realm-in-signing-key-age", _signing_realm),
    ("volumes", "extra-volume", _add_volume),
    ("volumes", "writable-mount", _mount_rw),
    ("hardening", "root-pod", _root_pod),
    ("hardening", "seccomp", _seccomp),
    ("hardening", "writable-rootfs", _drop_security),
    ("hardening", "host-network", _pod_set("hostNetwork", True)),
    ("native-sidecar", "off", _sidecar_off),
    ("realm-configmap", "name", _config_map_name),
    ("realm-configmap", "extra-key", _cm_key),
    ("realm-configmap", "namespace", _config_map_namespace),
    (
        "no-plain-secret",
        "secret",
        _add_doc(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "keycloak-reader-client", "namespace": "vectra-identity"},
                "stringData": {"private-key": "x"},
            }
        ),
    ),
    ("service-account-doc", "outside-the-list", _extra_sa),
    ("service-account-doc", "namespace", _sa_other_namespace),
    ("service-account-doc", "secrets", _sa_secrets),
    ("service-account-doc", "automount", _sa_automount),
]
PER_SET: list[tuple[str, str, Callable[[Docs], None]]] = [
    ("documents-exact", "missing-configmap", _drop_doc("ConfigMap", "realm-drift-realm")),
    ("documents-exact", "missing-cronjob", _drop_doc("CronJob", "signing-key-age")),
    ("documents-exact", "missing-account", _drop_doc("ServiceAccount", "realm-drift")),
    (
        "documents-exact",
        "extra-document",
        _add_doc(
            {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "x", "namespace": "vectra-identity"}}
        ),
    ),
    (
        "documents-exact",
        "repeated-document",
        lambda d: d.append(copy.deepcopy(jc.find(d, "ServiceAccount", "realm-drift"))),
    ),
    (
        "service-account-exists",
        "account-not-in-render",
        lambda d: _drop_doc("ServiceAccount", "signing-key-age")(d),
    ),
    ("configmap-mounted", "configmap-not-in-render", _drop_doc("ConfigMap", "realm-drift-realm")),
]


def _messages(result: Any) -> list[str]:
    out: list[str] = []
    for entry in json.loads(result.stdout):
        out += [f["msg"] for f in entry.get("failures") or []]
    return out


def test_render_policies_pass_on_the_versioned_render(render_env: str) -> None:
    docs = jc.versioned(render_env)
    for doc in docs:
        result = jc.conftest([doc])
        assert result.returncode == 0, _messages(result)
    result = jc.conftest(docs, combine=True)
    assert result.returncode == 0, _messages(result)


@pytest.mark.parametrize(
    ("rule", "case", "mutate"), PER_DOCUMENT, ids=[f"{r}:{c}" for r, c, _ in PER_DOCUMENT]
)
def test_render_policy_fails_on_an_altered_render(
    rule: str, case: str, mutate: Callable[[Docs], None]
) -> None:
    docs = copy.deepcopy(jc.versioned("kind"))
    mutate(docs)
    messages: list[str] = []
    for doc in docs:
        result = jc.conftest([doc])
        messages += _messages(result)
    assert any(m.startswith(f"{rule}:") for m in messages), (rule, case, messages)


@pytest.mark.parametrize(("rule", "case", "mutate"), PER_SET, ids=[f"{r}:{c}" for r, c, _ in PER_SET])
def test_render_set_policy_fails_on_an_altered_render(
    rule: str, case: str, mutate: Callable[[Docs], None]
) -> None:
    docs = copy.deepcopy(jc.versioned("prod"))
    mutate(docs)
    result = jc.conftest(docs, combine=True)
    assert any(m.startswith(f"{rule}:") for m in _messages(result)), (rule, case, _messages(result))


def test_render_every_rule_of_the_policies_has_a_failing_case() -> None:
    covered = {rule for rule, _, _ in [*PER_DOCUMENT, *PER_SET]}
    assert jc.rego_rules() == covered


def test_render_the_constants_of_the_policy_are_the_design() -> None:
    rego = (jc.POLICY / "jobs.rego").read_text(encoding="utf-8")
    for value in (
        design.pushgateway_url(), design.admin_url(), design.token_url(), *design.image_repositories(),
        design.priority_class(), *design.schedules().values(),
    ):  # fmt: skip
        assert f'"{value}"' in rego, value
    resources = design.resources()
    for group in resources.values():
        for quantity in group.values():
            assert f'"{quantity}"' in rego


# --- imagen y red --------------------------------------------------------------------------------------


def _dockerfile() -> list[str]:
    return [
        ln.strip()
        for ln in (jc.JOBS / "Dockerfile").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def test_dockerfile_uses_the_base_of_the_design_and_a_numeric_non_root_user() -> None:
    lines = _dockerfile()
    assert lines[0] == f"FROM {design.base_image()}"
    users = [ln.removeprefix("USER ") for ln in lines if ln.startswith("USER ")]
    assert users and users[-1].isdigit() and int(users[-1]) != 0
    values = yaml.safe_load((jc.CHART / "values.yaml").read_text(encoding="utf-8"))
    assert users[-1] == str(65532) and values["namespace"] == jc.NAMESPACE


def test_dockerfile_carries_the_scripts_of_both_jobs_and_the_libraries() -> None:
    text = "\n".join(_dockerfile())
    for script in ("keycloak_admin.py", "realm_drift.py", "signing_key_age.py", "realm_diff.py"):
        assert script in text
    assert "vectra_common" in text and "vectra_contracts" in text
    for env in ENVS:
        for name in ("realm-drift", "signing-key-age"):
            command = jc.find(jc.versioned(env), "CronJob", name)["spec"]["jobTemplate"]["spec"]["template"][
                "spec"
            ]["containers"][0]["command"]
            assert (
                command[0] == "python"
                and command[1].startswith("/app/")
                and command[1].removeprefix("/app/") in text
            )


def test_the_service_accounts_of_the_render_are_the_ones_of_the_network_inventory() -> None:
    flows = yaml.safe_load(
        (jc.EDGE.parent / "platform" / "network" / "flows.yaml").read_text(encoding="utf-8")
    )
    workloads = flows["workloads"] if "workloads" in flows else flows
    found = {name: w for name, w in workloads.items() if name in {"realm-drift", "signing-key-age"}}
    assert set(found) == {"realm-drift", "signing-key-age"}
    for env in ENVS:
        for name, workload in found.items():
            assert workload["ns"] == jc.NAMESPACE and workload["sa"] == name
            assert (
                jc.find(jc.versioned(env), "ServiceAccount", name)["metadata"]["namespace"] == workload["ns"]
            )
            pod = jc.find(jc.versioned(env), "CronJob", name)["spec"]["jobTemplate"]["spec"]["template"]
            assert pod["metadata"]["labels"]["app.kubernetes.io/name"] == workload["name"]


# --- ronda 3: composites de los roles (D-8) y flujos propios (F-09) ------------------------------------


async def test_d8_the_job_reads_the_composites_of_the_roles_that_have_them(env_kind: Environment) -> None:
    kc = keycloak_view(load_git("kind"))
    env_kind.serve(kc)
    assert await drift(env_kind) == 0
    composites = [p for p, _ in env_kind.server.requests if p.endswith("/composites")]
    assert composites == ["/roles/default-roles-vectra/composites"]


async def test_d8_realm_admin_as_a_composite_of_the_default_role_gives_one(env_kind: Environment) -> None:
    kc = keycloak_view(load_git("kind"))
    default = next(r for r in kc["roles"]["realm"] if r["name"] == "default-roles-vectra")
    default["composites"]["client"]["realm-management"] = ["realm-admin"]
    env_kind.serve(kc)
    assert await drift(env_kind) == 1


async def test_f09_a_flow_of_the_list_that_is_not_built_in_is_read_and_counts(env_kind: Environment) -> None:
    kc = keycloak_view(load_git("kind"))
    next(f for f in kc["authenticationFlows"] if f["alias"] == "docker auth")["builtIn"] = False
    env_kind.serve(kc)
    assert await drift(env_kind) == 1
    assert "/authentication/flows/docker auth/executions" in [p for p, _ in env_kind.server.requests]
