"""Escenarios de las pruebas de `run`: datos sembrados en el doble del registro y las dependencias de una corrida."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from builders import CATALOG, batch_client, table
from vectra_bias import config
from vectra_bias.run import Deps
from vectra_disparity import ATTRIBUTES, CountTable
from world import GOVERNANCE_URL, PUSHGATEWAY_URL, REGISTRY_URL, World

POLICY = config.MonitoringPolicy(
    threshold_pp=Decimal(5), n_min=30, window_days=30, schedule="2,17,32,47 * * * *", stale_after_s=3600
)


def small_counts(level: str, n: int) -> dict[str, CountTable]:
    """Catalogo chico (2 grupos por atributo): `high` = 20 pp en `region` y 0 en el resto; `low` = 0 en todos."""
    counts = {}
    for attribute in ATTRIBUTES:
        groups = CATALOG[attribute][:2]
        rates = dict.fromkeys(groups, 0.5)
        if level == "high" and attribute == "region":
            rates[groups[1]] = 0.7
        counts[attribute] = table(attribute, rates, n)
    return counts


def seed(
    world: World,
    version: str,
    today: date,
    *,
    days: int = 5,
    model: str | None = "low",
    human: str | None = None,
    n: int = 600,
    invalid_per_day: int = 0,
) -> None:
    """`days` dias de datos hasta `today` (inclusive) para `version`, con el nivel de disparidad de cada poblacion."""
    for d in range(days):
        day = today - timedelta(days=d)
        if model is not None:
            world.registry.add_day(version, "modelo", day, small_counts(model, n), invalid=invalid_per_day)
        if human is not None:
            world.registry.add_day(version, "humana", day, small_counts(human, n), decisions=True)


def clear(world: World, version: str) -> None:
    world.registry.rows = [r for r in world.registry.rows if r.version != version]
    for key in [k for k in world.registry.entries if k[0] == version]:
        del world.registry.entries[key]


def make_deps(
    world: World, clock: Callable[[], datetime], *, keycloak=True, policy: config.MonitoringPolicy = POLICY
) -> Deps:
    registry_token = (
        world.keycloak.provider("decision-registry-service", ("registry:read:monitoring",))
        if keycloak
        else None
    )
    governance_token = (
        world.keycloak.provider("governance-service", ("governance:freeze",)) if keycloak else None
    )
    return Deps(
        registry=batch_client("registry", REGISTRY_URL, world.registry.transport(), registry_token),
        governance=batch_client("governance", GOVERNANCE_URL, world.governance.transport(), governance_token),
        pushgateway=batch_client("pushgateway", PUSHGATEWAY_URL, world.pushgateway.transport()),
        policy=policy,
        sleep=world.clock.sleep,
        clock=clock,
    )


NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
