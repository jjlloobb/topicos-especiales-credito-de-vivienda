"""PBT-U2-06: `generate(routes.yaml)` es determinista, tambien con las entradas permutadas (U02-T09, Paso 7)."""

import random
from typing import Any

import gateway_checks as gc
import route_gen
from hypothesis import given
from hypothesis import strategies as st


def permute(node: Any, rnd: random.Random) -> Any:
    """Misma informacion, otro orden: claves de cada mapa y elementos de cada lista."""
    if isinstance(node, dict):
        keys = list(node)
        rnd.shuffle(keys)
        return {k: permute(node[k], rnd) for k in keys}
    if isinstance(node, list):
        items = [permute(x, rnd) for x in node]
        rnd.shuffle(items)
        return items
    return node


ROUTES = route_gen.load_routes()
VALUES = {env: route_gen.load_values(env) for env in gc.ENVS}


def with_f09(values: dict[str, Any], enabled: bool) -> dict[str, Any]:
    out = permute(values, random.Random(0))
    out["f09"] = {"enabled": enabled}
    return out


@given(rnd=st.randoms(use_true_random=False), env=st.sampled_from(gc.ENVS), f09=st.booleans())
def test_two_runs_with_the_entries_permuted_give_identical_bytes(rnd, env, f09):
    values = with_f09(VALUES[env], f09)
    first = route_gen.generate(ROUTES, values)
    second = route_gen.generate(permute(ROUTES, rnd), permute(values, rnd))
    assert second == first
    assert route_gen.generate(ROUTES, values) == first


@given(env=st.sampled_from(gc.ENVS))
def test_the_output_is_a_pure_function_of_its_inputs(env):
    first = route_gen.generate(ROUTES, VALUES[env])
    assert route_gen.generate(ROUTES, VALUES[env]) == first
    assert all(isinstance(text, str) and text.endswith("\n") for text in first.values())


@given(rnd=st.randoms(use_true_random=False))
def test_generation_does_not_modify_its_inputs(rnd):
    routes = permute(ROUTES, rnd)
    before = repr(routes)
    route_gen.generate(routes, VALUES["kind"])
    assert repr(routes) == before
