"""Autorizacion declarativa (P-U0-02, BR-U0-71, 72)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import Request
from vectra_contracts.catalog import Role, Scope
from vectra_contracts.errors import ContractViolation
from vectra_contracts.models.api import Principal
from vectra_contracts.routes import MFA_MAX_AGE

from vectra_common.errors import Forbidden, MfaRequired

_NO_REQUIREMENTS = "una ruta sin scopes ni roles no puede arrancar (BR-U0-71)"


def is_authorized(
    principal: Principal,
    scopes: frozenset[Scope],
    any_scopes: frozenset[Scope],
    roles: frozenset[Role],
) -> bool:
    """BR-U0-71: un conjunto no declarado no restringe."""
    return (
        scopes <= principal.scopes
        and (not any_scopes or bool(any_scopes & principal.scopes))
        and (not roles or bool(roles & principal.roles))
    )


def mfa_satisfied(principal: Principal, now: datetime, max_age: int = MFA_MAX_AGE) -> bool:
    """BR-U0-72: `acr == "mfa"` y `now - auth_time <= max_age`."""
    if principal.acr != "mfa" or principal.auth_time is None:
        return False
    return (now - principal.auth_time).total_seconds() <= max_age


def authorize(
    principal: Principal,
    scopes: frozenset[Scope],
    any_scopes: frozenset[Scope],
    roles: frozenset[Role],
    mfa: bool,
    now: datetime,
    max_age: int = MFA_MAX_AGE,
) -> None:
    if not is_authorized(principal, scopes, any_scopes, roles):
        raise Forbidden()
    if mfa and not mfa_satisfied(principal, now, max_age):
        raise MfaRequired()


@dataclass(frozen=True)
class Requirement:
    scopes: frozenset[Scope]
    any_scopes: frozenset[Scope]
    roles: frozenset[Role]
    mfa: bool
    max_age: int


def require(
    scopes: frozenset[Scope] = frozenset(),
    roles: frozenset[Role] = frozenset(),
    any_scopes: frozenset[Scope] = frozenset(),
    mfa: bool = False,
    max_age: int = MFA_MAX_AGE,
    clock: Callable[[], datetime] | None = None,
) -> Callable[[Request], Awaitable[None]]:
    """Dependencia con el marcador que `create_app` audita al arrancar (deny by default)."""
    if not scopes and not any_scopes and not roles:
        raise ContractViolation(_NO_REQUIREMENTS)
    requirement = Requirement(scopes, any_scopes, roles, mfa, max_age)

    async def dependency(request: Request) -> None:
        now = (clock or request.app.state.clock)()
        principal: Principal = request.scope["vectra_principal"]
        authorize(principal, scopes, any_scopes, roles, mfa, now, max_age)

    dependency.vectra_requirement = requirement  # type: ignore[attr-defined]
    return dependency
