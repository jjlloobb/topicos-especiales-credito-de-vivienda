"""El BFF **real** (`console_bff.app.build`) en proceso con los dobles de U10 en sus cinco destinos (U12-T02, CA-14; P-3 (a)). Los tokens son los del emisor de prueba de U0 (`bff_tokens`), con el
`sub` del analista. Lo que el conductor ve (rutas, reglas de objeto, validacion de la decision, `Problem`) es el servicio real."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from contract_world import OUTCOMES, case_detail_json
from external_paths import use_u10_doubles
from sync_asgi import BackgroundLoop, SyncASGITransport

use_u10_doubles()
import bff_builders as b  # noqa: E402
import bff_tokens  # noqa: E402
from bff_doubles import Doubles, problem  # noqa: E402
from vectra_common import process  # noqa: E402

from console_bff.app import build  # noqa: E402


class TokenSession:
    """Una sesion con tokens del emisor de prueba: `bearer()` entrega un token del analista; `refresh()` entrega uno nuevo (un 401 inyectado se prueba con `unauthorized_next`)."""

    def __init__(self, user: str, roles: tuple[str, ...] = ("analista",), step_up: bool = False) -> None:
        self.user, self.roles, self.step_up = user, roles, step_up
        self.refreshed = 0
        self.unauthorized_next = 0

    def bearer(self) -> str:
        if self.unauthorized_next > 0:
            self.unauthorized_next -= 1
            return "token-vencido"
        return bff_tokens.bearer(self.roles, sub=self.user)["authorization"].removeprefix("Bearer ")

    def refresh(self) -> None:
        self.refreshed += 1


class RealBff:
    def __init__(self) -> None:
        os.environ.setdefault("VECTRA_LOG_STRICT", "1")
        process.ensure_service()
        self.doubles = Doubles()
        self.decisions: dict[str, int] = {}
        self.decision_conflicts: set[str] = set()
        self.decision_invalid: set[str] = set()
        self.background = BackgroundLoop()
        self.app = build(
            self.doubles.urls(),
            authenticator=bff_tokens.authenticator(),
            transports=self.doubles.transports(),
        )
        self.transport = SyncASGITransport(self.app, self.background)
        self.case_ids: list[str] = []
        responders = self.doubles.case.responders
        responders[("GET", "/v1/cases")] = lambda call: (
            200,
            b.page(
                [self._summary(i) for i in self.case_ids if self.doubles.case.details[i]["state"] == "listo"]
            ),
        )
        responders[("POST", "/v1/cases/{id}/decision")] = self._decision

    def _summary(self, case_id: str) -> dict[str, Any]:
        detail = self.doubles.case.details[case_id]
        return {
            k: detail[k]
            for k in ("case_id", "state", "channel", "created_at", "applicant_display", "outcome", "score")
        }

    def _decision(self, call: Any) -> tuple[int, Any]:
        case_id = call.params["id"]
        self.decisions[case_id] = self.decisions.get(case_id, 0) + 1
        if case_id in self.decision_invalid:
            return 422, problem(422, "validation_error")
        if case_id in self.decision_conflicts:
            return 409, problem(409, "conflict_state", "decision_already_recorded")
        self.doubles.case.details[case_id]["state"] = "decidido"
        return 200, b.decision_ref(case_id)

    def add_cases(self, count: int, *, start: int = 100) -> list[str]:
        added = []
        for i in range(start, start + count):
            case_id = b.uuid_of(i)
            self.doubles.case.details[case_id] = case_detail_json(case_id, "listo", OUTCOMES[i % 3])
            self.case_ids.append(case_id)
            added.append(case_id)
        return added

    def users_seen(self) -> set[str]:
        """Los `sub` de los tokens que el BFF reenvio a U8 (el Authorization del usuario tal cual)."""
        import jwt

        subs: set[str] = set()
        for call in self.doubles.case.calls:
            token = call.headers.get("authorization", "").removeprefix("Bearer ")
            if token:
                subs.add(str(jwt.decode(token, options={"verify_signature": False})["sub"]))
        return subs

    def close(self) -> None:
        self.transport.close()
        self.background.run(self.app.state.upstreams.aclose())
        self.background.close()


def decision_posts(world: RealBff) -> list[Any]:
    return [c for c in world.doubles.case.calls if c.method == "POST" and c.template.endswith("/decision")]


__all__ = ["RealBff", "TokenSession", "decision_posts", "httpx", "json"]
