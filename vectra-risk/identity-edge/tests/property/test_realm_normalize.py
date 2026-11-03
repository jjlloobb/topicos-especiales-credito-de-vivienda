"""PBT-U2-04 (U02-T08, BR-U2-12): `normalize` es idempotente y el ruido de Keycloak no genera diferencias."""

import copy
import random
from typing import Any

import realm_diff
from hypothesis import given, settings
from hypothesis import strategies as st
from realm_exports import ENVS, keycloak_view, load_git

_REALMS = {env: load_git(env) for env in ENVS}
_envs = st.sampled_from(ENVS)
_text = st.text(alphabet="abcdefghij0123456789-_", min_size=1, max_size=12)


def _walk(node: Any, path: realm_diff.Path, visit: Any) -> None:
    if isinstance(node, dict):
        visit(node, path)
        for key, value in node.items():
            _walk(value, realm_diff.child_path(path, key), visit)
    elif isinstance(node, list):
        for item in node:
            _walk(item, path, visit)


def _noisy(realm: dict[str, Any], seed: int, token: str) -> dict[str, Any]:
    """Cambia solo secretos, IDs internos y timestamps (las listas exactas de `realm_diff`) y el orden de las entidades."""
    out = copy.deepcopy(realm)

    def visit(node: dict[str, Any], path: realm_diff.Path) -> None:
        for field in realm_diff.SECRET_FIELDS.get(path, ()):
            node[field] = f"{token}-secreto-{field}"
        for field in realm_diff.ID_FIELDS.get(path, ()):
            node[field] = f"{token}-id-{field}"
        for field in realm_diff.TIMESTAMP_FIELDS.get(path, ()):
            node[field] = seed + len(token)

    _walk(out, (), visit)
    rnd = random.Random(seed)  # noqa: S311 - orden de prueba, no criptografia
    for key in (
        "clients",
        "clientScopes",
        "users",
        "requiredActions",
        "authenticationFlows",
        "authenticatorConfig",
    ):
        rnd.shuffle(out[key])
    return out


@given(env=_envs, token=_text)
@settings(deadline=None)
def test_normalize_is_idempotent_on_exports_with_noise(env: str, token: str) -> None:
    export = _noisy(keycloak_view(_REALMS[env]), 1, token)
    once = realm_diff.normalize(export)
    assert realm_diff.normalize(once) == once


@given(env=_envs, seed=st.integers(0, 10_000), token=_text)
@settings(deadline=None)
def test_normalize_does_not_depend_on_order_or_noise(env: str, seed: int, token: str) -> None:
    base = keycloak_view(_REALMS[env])
    assert realm_diff.normalize(_noisy(base, seed, token)) == realm_diff.normalize(base)
    assert realm_diff.normalize(keycloak_view(_REALMS[env], token)) == realm_diff.normalize(base)


@given(env=_envs, seed=st.integers(0, 10_000), token=_text, other=_text)
@settings(deadline=None)
def test_two_exports_that_differ_only_in_secrets_ids_or_timestamps_have_zero_differences(
    env: str, seed: int, token: str, other: str
) -> None:
    git = _REALMS[env]
    first = _noisy(keycloak_view(git, token), seed, token)
    second = _noisy(keycloak_view(git, other), seed + 1, other)
    assert realm_diff.drift_count(first, second) == 0
    assert realm_diff.drift_count(git, first) == 0
    # Sin pasar por las tablas de `realm_diff`: solo cambian los valores que escribe `keycloak_view`.
    assert realm_diff.drift_count(keycloak_view(git, token), keycloak_view(git, other)) == 0


@given(env=_envs, value=st.integers(0, 10**6))
@settings(deadline=None)
def test_a_real_change_survives_the_noise(env: str, value: int) -> None:
    git = _REALMS[env]
    export = keycloak_view(git)
    export["accessTokenLifespan"] = git["accessTokenLifespan"] + 1 + value
    assert realm_diff.drift_count(git, _noisy(export, 3, "x")) == 1


_scalars = st.one_of(st.none(), st.booleans(), st.integers(-5, 5), _text)
_json = st.recursive(
    _scalars,
    lambda inner: st.one_of(st.lists(inner, max_size=3), st.dictionaries(_text, inner, max_size=3)),
    max_leaves=12,
)


@given(extra=st.dictionaries(_text, _json, max_size=4))
@settings(deadline=None)
def test_normalize_is_idempotent_on_arbitrary_documents(extra: dict[str, Any]) -> None:
    doc = {**keycloak_view(_REALMS["kind"]), **{f"x-{k}": v for k, v in extra.items()}}
    once = realm_diff.normalize(doc)
    assert realm_diff.normalize(once) == once
