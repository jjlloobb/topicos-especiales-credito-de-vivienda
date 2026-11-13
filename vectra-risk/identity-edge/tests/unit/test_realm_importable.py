"""Los tres realms se pueden importar con keycloak-config-cli y dejar entrar a un usuario (U02-T22).

Defectos medidos con Keycloak 26.8.1 y config-cli 6.5.1-26.5.5 (ver `docs/realm-importacion.md`):
- (a) un alias de `authenticatorConfig` citado por dos ejecuciones solo se enlaza a la primera; las demas fallan todo login (`loaConditionConfig is null`);
- (b) sin `VERIFY_PROFILE` deshabilitada, un usuario sin `email`, `firstName` ni `lastName` termina el login en esa accion y nunca llega al `redirect_uri`.

Sin Docker: lee los YAML. Los valores salen de `design_values.py`. Las mutaciones se aplican a copias en memoria.
"""

import collections
import copy
from pathlib import Path
from typing import Any

import design_values as design
import pytest
import yaml

REALM_DIR = Path(__file__).resolve().parents[2] / "keycloak" / "realm"
ENVS = ("kind", "staging", "prod")
LOA = "conditional-level-of-authentication"
PROFILE_ACTION = "VERIFY_PROFILE"
PROFILE_FIELDS = ("email", "firstName", "lastName")


def load(env: str) -> dict[str, Any]:
    data = yaml.safe_load((REALM_DIR / f"realm.{env}.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def executions(realm: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(f["alias"], e) for f in realm["authenticationFlows"] for e in f["authenticationExecutions"]]


def citations(realm: dict[str, Any]) -> dict[str, list[str]]:
    """alias de configuracion -> ejecuciones (`flujo#prioridad`) que lo citan."""
    out: dict[str, list[str]] = collections.defaultdict(list)
    for flow, execution in executions(realm):
        if "authenticatorConfig" in execution:
            out[execution["authenticatorConfig"]].append(f"{flow}#{execution['priority']}")
    return dict(out)


def alias_problems(realm: dict[str, Any]) -> list[str]:
    cited = citations(realm)
    declared = [c["alias"] for c in realm["authenticatorConfig"]]
    problems = [f"alias `{a}` declarado {n} veces" for a, n in collections.Counter(declared).items() if n > 1]
    problems += [f"alias `{a}` citado por {len(refs)} ejecuciones: {', '.join(refs)}" for a, refs in sorted(cited.items()) if len(refs) > 1]
    problems += [f"cita a `{a}`, que no esta declarado ({', '.join(refs)})" for a, refs in sorted(cited.items()) if a not in declared]
    problems += [f"`{a}` esta declarado y nadie lo cita" for a in declared if a not in cited]
    return problems


def value_problems(realm: dict[str, Any]) -> list[str]:
    configs = {c["alias"]: c["config"] for c in realm["authenticatorConfig"]}
    loa = design.loa_map()
    amr = design.amr_references()
    problems = []
    for flow, execution in executions(realm):
        alias = execution.get("authenticatorConfig")
        if alias is None or alias not in configs:
            continue
        config = configs[alias]
        authenticator = execution.get("authenticator")
        if authenticator == LOA:
            level = loa["pwd"] if flow == "vectra-level-pwd" else loa["mfa"]
            if config.get("loa-condition-level") != str(level):
                problems.append(f"`{alias}` ({flow}): loa-condition-level {config.get('loa-condition-level')!r}, el diseno dice {level}")
            if config.get("loa-max-age") != str(design.loa_max_age()):
                problems.append(f"`{alias}` ({flow}): loa-max-age {config.get('loa-max-age')!r}, el diseno dice {design.loa_max_age()}")
        elif authenticator in amr:
            if config.get("default.reference.value") != amr[authenticator]:
                problems.append(f"`{alias}` ({flow}, {authenticator}): amr {config.get('default.reference.value')!r}, el diseno dice {amr[authenticator]!r}")
            if config.get("default.reference.maxAge") != str(design.amr_reference_max_age()):
                problems.append(f"`{alias}` ({flow}): maxAge {config.get('default.reference.maxAge')!r}, el diseno dice {design.amr_reference_max_age()}")
    return problems


def local_users(realm: dict[str, Any]) -> list[dict[str, Any]]:
    return [u for u in realm["users"] if "serviceAccountClientId" not in u]


def profile_problems(realm: dict[str, Any]) -> list[str]:
    """Un usuario local sin los tres atributos queda atrapado, salvo que `VERIFY_PROFILE` este declarada y deshabilitada (P-2, opcion c)."""
    action = next((a for a in realm["requiredActions"] if a["alias"] == PROFILE_ACTION), None)
    if action is not None and action.get("enabled") is False:
        return []
    return [f"usuario `{u['username']}` atrapado por VERIFY_PROFILE: sin {', '.join(f for f in PROFILE_FIELDS if not u.get(f))}" for u in local_users(realm) if not all(u.get(f) for f in PROFILE_FIELDS)]


def flow_problems(realms: dict[str, dict[str, Any]]) -> list[str]:
    base = realms["kind"]
    return [
        f"{section} de {env} difiere del de kind"
        for env, realm in realms.items()
        for section in ("authenticationFlows", "authenticatorConfig", "requiredActions")
        if realm[section] != base[section]
    ]


@pytest.fixture(params=ENVS)
def env(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def test_each_execution_has_its_own_config(env: str) -> None:
    assert alias_problems(load(env)) == []


def test_configs_keep_the_design_values(env: str) -> None:
    assert value_problems(load(env)) == []


def test_flows_and_actions_are_equal_in_the_three_realms() -> None:
    assert flow_problems({e: load(e) for e in ENVS}) == []


def test_no_local_user_is_trapped_by_the_profile(env: str) -> None:
    assert profile_problems(load(env)) == []


def test_there_are_users_to_check() -> None:
    """Sin usuarios locales la prueba del perfil no mediria nada (kind: sinteticos; prod: `break-glass`)."""
    assert len(local_users(load("kind"))) >= 10
    assert [u["username"] for u in local_users(load("prod"))] == ["break-glass"]


# --- mutaciones sobre copias en memoria ---------------------------------------------------------------------------


def _find(realm: dict[str, Any], flow: str, authenticator: str) -> dict[str, Any]:
    return next(e for f, e in executions(realm) if f == flow and e.get("authenticator") == authenticator)


def _config(realm: dict[str, Any], alias: str) -> dict[str, Any]:
    return next(c["config"] for c in realm["authenticatorConfig"] if c["alias"] == alias)


def test_mutation_two_executions_share_an_alias() -> None:
    realm = copy.deepcopy(load("kind"))
    victim = _find(realm, "vectra-mfa-cro", LOA)
    other = _find(realm, "vectra-mfa-cumplimiento", LOA)
    victim["authenticatorConfig"] = other["authenticatorConfig"]
    problems = alias_problems(realm)
    assert any("citado por 2 ejecuciones" in p for p in problems), problems


def test_mutation_citation_to_a_missing_alias() -> None:
    realm = copy.deepcopy(load("kind"))
    _find(realm, "vectra-mfa-cro", LOA)["authenticatorConfig"] = "no-existe"
    assert any("no esta declarado" in p for p in alias_problems(realm))


def test_mutation_declared_alias_nobody_cites() -> None:
    realm = copy.deepcopy(load("kind"))
    realm["authenticatorConfig"].append({"alias": "huerfano", "config": {"x": "1"}})
    assert any("`huerfano` esta declarado y nadie lo cita" in p for p in alias_problems(realm))


@pytest.mark.parametrize("key, value", [("loa-condition-level", "1"), ("loa-max-age", "60")])
def test_mutation_loa_value_differs_in_one_role(key: str, value: str) -> None:
    realm = copy.deepcopy(load("kind"))
    alias = _find(realm, "vectra-mfa-cro", LOA)["authenticatorConfig"]
    _config(realm, alias)[key] = value
    problems = value_problems(realm)
    assert len(problems) == 1 and key in problems[0], problems


def test_mutation_crossed_amr() -> None:
    realm = copy.deepcopy(load("kind"))
    alias = _find(realm, "vectra-mfa-cro factor", "webauthn-authenticator")["authenticatorConfig"]
    _config(realm, alias)["default.reference.value"] = "otp"
    problems = value_problems(realm)
    assert len(problems) == 1 and "webauthn-authenticator" in problems[0], problems


def test_mutation_one_realm_flow_differs() -> None:
    realms = {e: copy.deepcopy(load(e)) for e in ENVS}
    realms["staging"]["authenticationFlows"][0]["authenticationExecutions"][0]["requirement"] = "REQUIRED"
    assert flow_problems(realms) == ["authenticationFlows de staging difiere del de kind"]


def test_mutation_profile_action_enabled_traps_a_synthetic_user_and_break_glass() -> None:
    kind = copy.deepcopy(load("kind"))
    for action in kind["requiredActions"]:
        if action["alias"] == PROFILE_ACTION:
            action["enabled"] = True
    assert any("analista-1" in p for p in profile_problems(kind))
    prod = copy.deepcopy(load("prod"))
    prod["requiredActions"] = [a for a in prod["requiredActions"] if a["alias"] != PROFILE_ACTION]
    assert any("break-glass" in p for p in profile_problems(prod))


def test_mutation_profile_is_fine_if_the_user_has_the_three_fields() -> None:
    realm = copy.deepcopy(load("prod"))
    realm["requiredActions"] = [a for a in realm["requiredActions"] if a["alias"] != PROFILE_ACTION]
    for user in local_users(realm):
        user.update(email="a@b.invalid", firstName="a", lastName="b")
    assert profile_problems(realm) == []
