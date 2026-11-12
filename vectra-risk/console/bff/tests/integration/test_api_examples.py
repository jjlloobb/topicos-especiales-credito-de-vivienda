"""Paso 7 (CA-4): las pruebas de ejemplo del FD (business-logic-model §3) y un caso negativo por regla de objeto (US-602, US-611).

Las de la ventana emergente y el reintento unico son de la SPA (U10-T03). Aqui: los ejemplos del BFF, la orden de los tres
controles (BR-U10-01), una regla de objeto que rechaza -> 409 y **cero** escrituras en el destino, y la traduccion de errores.
"""

import time
from collections.abc import Callable
from typing import Any

import bff_builders as b
import bff_tokens
import bff_world as w
import pytest
from bff_doubles import problem
from bff_support import Bff, EventLog
from vectra_common.metrics import REGISTRY as METRICS

from console_bff import object_rules
from console_bff.object_rules import ObjectVerdict

CRO = bff_tokens.bearer(["cro"])
ANALISTA = bff_tokens.bearer(["analista"])
CUMPLIMIENTO = bff_tokens.bearer(["cumplimiento"])
INGENIERO = bff_tokens.bearer(["ingeniero_riesgo"])
P = "/api/console"


# --- los cinco ejemplos del FD -----------------------------------------------------------------------------------------


async def test_an_analyst_approving_a_model_is_403_forbidden_with_authz_denied(
    bff: Bff, events: EventLog
) -> None:
    before = (
        METRICS.get_sample_value(
            "vectra_authz_denied_total", {"code": "forbidden", "route_template": P + "/models/{id}/approval"}
        )
        or 0
    )
    response = await bff.client.post(
        f"{P}/models/mv-lista/approval", headers=ANALISTA, json={"decision": "aprobado"}
    )
    assert response.status_code == 403 and response.json()["code"] == "forbidden"
    [event] = events.named("authz.denied")
    assert event == {
        "route_template": P + "/models/{id}/approval",
        "error_code": "forbidden",
        "principal_subject": "user-1",
    }
    assert (
        METRICS.get_sample_value(
            "vectra_authz_denied_total", {"code": "forbidden", "route_template": P + "/models/{id}/approval"}
        )
        == before + 1
    )
    assert bff.doubles.governance.count() == 0  # nada llega al destino


@pytest.mark.parametrize("state", ["expired", "other_audience", "bad_signature"])
async def test_an_expired_foreign_audience_or_badly_signed_jwt_is_401(
    bff: Bff, events: EventLog, state: str
) -> None:
    response = await bff.client.get(f"{P}/cases", headers=bff_tokens.for_state(state, ["analista"]))
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"
    [event] = events.named("authz.denied")
    assert event["error_code"] == "unauthenticated" and "principal_subject" not in event  # P-3 (a)
    assert bff.doubles.case.count() == 0


@pytest.mark.parametrize("state", ["acr_pwd", "stale_auth_time"])
async def test_an_approver_without_recent_mfa_is_403_mfa_required(
    bff: Bff, events: EventLog, state: str
) -> None:
    response = await bff.client.post(
        f"{P}/models/mv-lista/approval",
        headers=bff_tokens.for_state(state, ["cro"]),
        json={"decision": "aprobado"},
    )
    assert response.status_code == 403 and response.json()["code"] == "mfa_required"
    [event] = events.named("authz.denied")
    assert event["error_code"] == "mfa_required" and event["principal_subject"] == "user-1"
    assert bff.doubles.governance.count() == 0


async def test_the_role_check_comes_before_the_mfa_check(bff: Bff) -> None:
    """Un analista sin MFA en una ruta con MFA recibe `forbidden`, no `mfa_required` (BR-U10-01: orden fijo)."""
    response = await bff.client.post(
        f"{P}/models/mv-lista/approval",
        headers=bff_tokens.for_state("acr_pwd", ["analista"]),
        json={"decision": "aprobado"},
    )
    assert response.status_code == 403 and response.json()["code"] == "forbidden"


async def test_decision_already_recorded_is_409_with_the_reason_of_the_destination(bff: Bff) -> None:
    """La carrera de P-U10-01: la lectura dice `listo` y la escritura llega tarde; el destino resuelve con su 409."""
    case = bff.doubles.case
    case.reply(
        "POST", "/v1/cases/{id}/decision", 409, problem(409, "conflict_state", "decision_already_recorded")
    )
    response = await bff.client.post(
        f"{P}/cases/{w.CASE_LISTO}/decision",
        headers=ANALISTA,
        json=w.REQUESTS["post_api_console_cases_id_decision"].body,
    )
    assert response.status_code == 409
    assert (
        response.json()["code"] == "conflict_state"
        and response.json()["reason"] == "decision_already_recorded"
    )
    assert (
        case.count("GET", "/v1/cases/{id}") == 1 and case.count("POST", "/v1/cases/{id}/decision") == 1
    )  # leyo, y la escritura si llego


async def test_the_dossier_for_compliance_with_a_healthy_case_has_the_identifiers(bff: Bff) -> None:
    response = await bff.client.get(f"{P}/cases/{w.CASE_LISTO}/dossier", headers=CUMPLIMIENTO)
    assert response.status_code == 200 and response.json()["identifiers"]["full_name"] == "Ana María Gómez"


async def test_the_dossier_for_compliance_with_case_down_is_identifiers_unavailable(bff: Bff) -> None:
    bff.doubles.case.down()
    response = await bff.client.get(f"{P}/cases/{w.CASE_LISTO}/dossier", headers=CUMPLIMIENTO)
    assert response.status_code == 200 and response.json()["identifiers_unavailable"] is True


async def test_the_dossier_for_compliance_with_a_case_403_is_403(bff: Bff) -> None:
    bff.doubles.case.reply("GET", "/v1/cases/{id}/identifiers", 403, problem(403, "forbidden"))
    response = await bff.client.get(f"{P}/cases/{w.CASE_LISTO}/dossier", headers=CUMPLIMIENTO)
    assert response.status_code == 403 and response.json()["code"] == "forbidden"


# --- un caso negativo por regla de objeto: 409 y cero escrituras --------------------------------------------------------


def _case(bff: Bff, case_id: str, **kwargs: Any) -> None:
    bff.doubles.case.details[case_id] = b.case_detail(case_id, **kwargs)


def _model(bff: Bff, model_id: str, state: str) -> None:
    bff.doubles.governance.add_model(model_id, state)


def _source(bff: Bff, **kwargs: Any) -> None:
    bff.doubles.governance.sources = [b.data_source(w.SOURCE, **kwargs)]


NEGATIVE: list[Any] = [
    # (regla, destino, como dejar el objeto, headers, metodo, ruta, cuerpo)
    (
        "record_explanation_view",
        "case",
        lambda x: _case(x, w.CASE_LISTO, state="en_evaluacion"),
        ANALISTA,
        f"/cases/{w.CASE_LISTO}/explanation-views",
        None,
    ),
    (
        "record_decision",
        "case",
        lambda x: _case(x, w.CASE_LISTO, state="decidido", final_outcome="favorable"),
        ANALISTA,
        f"/cases/{w.CASE_LISTO}/decision",
        w.REQUESTS["post_api_console_cases_id_decision"].body,
    ),
    (
        "create_applicant_summary",
        "case",
        lambda x: _case(x, w.CASE_DECIDIDO, state="decidido", final_outcome="favorable"),
        CRO,
        f"/cases/{w.CASE_DECIDIDO}/applicant-summary",
        None,
    ),
    (
        "retry_case",
        "case",
        lambda x: _case(x, w.CASE_NO_DISPONIBLE, state="listo"),
        CRO,
        f"/cases/{w.CASE_NO_DISPONIBLE}/retry",
        None,
    ),
    (
        "retry_case_anonymized",
        "case",
        lambda x: _case(x, w.CASE_NO_DISPONIBLE, state="no_disponible", anonymized=True),
        CRO,
        f"/cases/{w.CASE_NO_DISPONIBLE}/retry",
        None,
    ),
    (
        "start_validation",
        "governance",
        lambda x: _model(x, "mv-registrado", "aprobado"),
        INGENIERO,
        "/models/mv-registrado/validations",
        None,
    ),
    (
        "start_source_comparison",
        "governance",
        lambda x: _source(x, state="aprobada"),
        INGENIERO,
        f"/data-sources/{w.SOURCE}/comparisons",
        {"candidate_version_id": "mv-cand"},
    ),
    (
        "start_source_comparison_without_candidate_link",
        "governance",
        lambda x: x.doubles.governance.add_model("mv-cand", "registrado"),
        INGENIERO,
        f"/data-sources/{w.SOURCE}/comparisons",
        {"candidate_version_id": "mv-cand"},
    ),
    (
        "start_source_comparison_without_active_version",
        "governance",
        lambda x: x.doubles.governance.models.pop("mv-activo"),
        INGENIERO,
        f"/data-sources/{w.SOURCE}/comparisons",
        {"candidate_version_id": "mv-cand"},
    ),
    (
        "approve_model",
        "governance",
        lambda x: _model(x, "mv-lista", "registrado"),
        CRO,
        "/models/mv-lista/approval",
        {"decision": "aprobado"},
    ),
    (
        "resolve_frozen",
        "governance",
        lambda x: _model(x, "mv-congelado", "activo"),
        CUMPLIMIENTO,
        "/models/mv-congelado/frozen-resolution",
        {"action": "reactivar", "justification": "ok"},
    ),
    (
        "retire_model",
        "governance",
        lambda x: _model(x, "mv-inactivo", "activo"),
        CRO,
        "/models/mv-inactivo/retirement",
        None,
    ),
    (
        "approve_policy",
        "governance",
        lambda x: setattr(x.doubles.governance, "policies", [b.policy_version(w.POLICY, "activa")]),
        CRO,
        f"/policies/{w.POLICY}/approval",
        {"decision": "aprobada"},
    ),
    (
        "decide_data_source",
        "governance",
        lambda x: _source(x, state="aprobada"),
        CUMPLIMIENTO,
        f"/data-sources/{w.SOURCE}/decision",
        {"decision": "aprobada"},
    ),
    (
        "decide_data_source_without_report",
        "governance",
        lambda x: _source(x, state="en_evaluacion", report=False),
        CUMPLIMIENTO,
        f"/data-sources/{w.SOURCE}/decision",
        {"decision": "aprobada"},
    ),
]


def test_every_object_rule_has_a_negative_case() -> None:
    covered = {name.split("_without")[0].removesuffix("_anonymized") for name, *_ in NEGATIVE}
    assert {rule.__name__ for rule in object_rules.OBJECT_RULES.values() if rule is not None} == covered


@pytest.mark.parametrize(
    ("name", "destination", "arrange", "headers", "path", "body"), NEGATIVE, ids=[n[0] for n in NEGATIVE]
)
async def test_a_rejected_object_rule_is_409_and_the_destination_gets_zero_writes(
    bff: Bff,
    name: str,
    destination: str,
    arrange: Callable[[Bff], None],
    headers: dict[str, str],
    path: str,
    body: Any,
) -> None:
    arrange(bff)
    response = await bff.client.post(P + path, headers=headers, json=body)
    assert response.status_code == 409 and response.json()["code"] == "conflict_state", response.text
    assert getattr(bff.doubles, destination).writes() == 0
    assert bff.doubles.explainability.count() == 0
    assert bff.doubles.registry.count() == 0


async def test_an_applicant_summary_without_a_synchronized_recommendation_is_409_without_calling_u7(
    bff: Bff,
) -> None:
    _case(bff, w.CASE_DECIDIDO, state="decidido", final_outcome="desfavorable", entry_id=None)
    response = await bff.client.post(f"{P}/cases/{w.CASE_DECIDIDO}/applicant-summary", headers=CRO)
    assert response.status_code == 409 and response.json()["code"] == "conflict_state"
    assert bff.doubles.explainability.count() == 0


async def test_an_applicant_summary_sends_the_recommendation_entry_id_of_the_case_detail(bff: Bff) -> None:
    _case(bff, w.CASE_DECIDIDO, state="decidido", final_outcome="desfavorable", entry_id="42")
    response = await bff.client.post(f"{P}/cases/{w.CASE_DECIDIDO}/applicant-summary", headers=CRO)
    assert response.status_code == 200 and response.json()["factors"]
    assert bff.doubles.explainability.calls[0].json() == {
        "case_id": w.CASE_DECIDIDO,
        "recommendation_entry_id": "42",
    }


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/policies/pv-inexistente/approval", {"decision": "aprobada"}),
        ("/data-sources/ds-inexistente/decision", {"decision": "aprobada"}),
        ("/data-sources/ds-inexistente/comparisons", {"candidate_version_id": "mv-cand"}),
    ],
)
async def test_an_object_that_is_not_in_the_list_is_404_not_found_without_writes(
    bff: Bff, path: str, body: Any
) -> None:
    """P-U10: no hay lectura por id de politicas y fuentes; si no aparece en la lista, no existe."""
    response = await bff.client.post(
        P + path, headers=bff_tokens.bearer(["cro", "cumplimiento", "ingeniero_riesgo"]), json=body
    )
    assert response.status_code == 404 and response.json()["code"] == "not_found"
    assert bff.doubles.governance.writes() == 0


async def test_a_pre_read_error_is_translated_like_any_destination_error(bff: Bff) -> None:
    bff.doubles.case.reply("GET", "/v1/cases/{id}", 404, problem(404, "not_found"))
    response = await bff.client.post(
        f"{P}/cases/{w.CASE_LISTO}/decision",
        headers=ANALISTA,
        json=w.REQUESTS["post_api_console_cases_id_decision"].body,
    )
    assert response.status_code == 404 and bff.doubles.case.writes() == 0


async def test_a_forbidden_object_verdict_is_a_403_forbidden_without_the_write(
    bff: Bff, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`FORBIDDEN` -> 403 `forbidden` (BR-U10-01); ninguna regla de estado de C03 lo produce, pero el camino existe."""
    rules = dict(object_rules.OBJECT_RULES)
    rules["post_api_console_models_id_approval"] = lambda state: ObjectVerdict.FORBIDDEN
    monkeypatch.setattr(object_rules, "OBJECT_RULES", rules)
    from console_bff.app import build

    app = build(
        bff.doubles.urls(), authenticator=bff_tokens.authenticator(), transports=bff.doubles.transports()
    )
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://bff.test"
    ) as client:
        response = await client.post(
            f"{P}/models/mv-lista/approval", headers=CRO, json={"decision": "aprobado"}
        )
    await app.state.upstreams.aclose()
    assert response.status_code == 403 and response.json()["code"] == "forbidden"
    assert bff.doubles.governance.writes() == 0


# --- traduccion de errores y respuestas 2xx -----------------------------------------------------------------------------


async def test_a_destination_error_with_traces_is_translated_to_a_generic_problem(bff: Bff) -> None:
    """BR-U10-04: sin `detail`, sin trazas, sin campos del destino."""
    bff.doubles.case.reply(
        "GET",
        "/v1/cases",
        500,
        {
            "code": "internal_error",
            "detail": "Traceback (most recent call last): psycopg.OperationalError",
            "stack": "x",
        },
    )
    response = await bff.client.get(f"{P}/cases", headers=ANALISTA)
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert (
        "Traceback" not in response.text
        and "psycopg" not in response.text
        and "detail" not in response.json()
    )


async def test_a_destination_code_outside_the_catalog_is_internal_error(bff: Bff) -> None:
    bff.doubles.case.reply("GET", "/v1/cases", 418, {"code": "soy_una_tetera"})
    response = await bff.client.get(f"{P}/cases", headers=ANALISTA)
    assert response.status_code == 500 and response.json()["code"] == "internal_error"


async def test_a_validation_error_of_the_destination_keeps_its_invalid_params(bff: Bff) -> None:
    bff.doubles.case.reply(
        "POST",
        "/v1/cases",
        422,
        {
            **problem(422, "validation_error"),
            "invalid_params": [{"name": "monthly_income", "reason_code": "greater_than_equal"}],
        },
    )
    response = await bff.client.post(
        f"{P}/cases", headers=ANALISTA, json=w.REQUESTS["post_api_console_cases"].body
    )
    assert response.status_code == 422 and response.json()["invalid_params"][0]["name"] == "monthly_income"


async def test_a_2xx_that_does_not_validate_is_500_and_never_passes_through(bff: Bff) -> None:
    bff.doubles.case.reply("GET", "/v1/cases", 200, {"items": [{"case_id": "no-uuid"}]})
    response = await bff.client.get(f"{P}/cases", headers=ANALISTA)
    assert (
        response.status_code == 500
        and response.json()["code"] == "internal_error"
        and "no-uuid" not in response.text
    )


@pytest.mark.parametrize(
    ("method", "template", "path", "status"),
    [
        ("POST", "/v1/cases/{id}/explanation-views", f"/cases/{w.CASE_LISTO}/explanation-views", 201),
        ("GET", "/v1/cases", "/cases", 302),
    ],
)
async def test_an_undeclared_success_status_or_a_redirect_is_500(
    bff: Bff, method: str, template: str, path: str, status: int
) -> None:
    bff.doubles.case.reply(method, template, status, None if method == "POST" else {"items": []})
    response = await bff.client.request(method, P + path, headers=ANALISTA)
    assert response.status_code == 500 and response.json()["code"] == "internal_error"


async def test_204_routes_answer_204_without_a_body(bff: Bff) -> None:
    for path, headers, body in (
        (f"/cases/{w.CASE_LISTO}/explanation-views", ANALISTA, None),
        ("/models/mv-lista/approval", CRO, {"decision": "aprobado"}),
        (f"/policies/{w.POLICY}/approval", CRO, {"decision": "aprobada"}),
        (
            "/client-errors",
            ANALISTA,
            {"error_code": "render_error", "route_template": "/x", "app_version": "1.0.0"},
        ),
    ):
        response = await bff.client.post(P + path, headers=headers, json=body)
        assert response.status_code == 204 and response.content == b"", path


async def test_the_case_detail_is_read_with_read_wire_and_comes_back_without_inventing_fields(
    bff: Bff,
) -> None:
    response = await bff.client.get(f"{P}/cases/{w.CASE_DECIDIDO}", headers=ANALISTA)
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == w.CASE_DECIDIDO and body["decision"]["final_outcome"] == "desfavorable"
    assert "recommendation" not in body  # el doble no la manda: no se inventa


async def test_the_idempotency_key_is_forwarded_and_never_invented(bff: Bff) -> None:
    body = w.REQUESTS["post_api_console_cases"].body
    await bff.client.post(f"{P}/cases", headers=ANALISTA, json=body)  # sin la cabecera: el BFF no la fabrica
    assert "idempotency-key" not in bff.doubles.case.calls[0].headers
    await bff.client.post(f"{P}/cases", headers={**ANALISTA, "Idempotency-Key": "k-1"}, json=body)
    assert bff.doubles.case.calls[1].headers["idempotency-key"] == "k-1"


async def test_the_request_body_is_forwarded_from_the_validated_model_not_the_input_bytes(bff: Bff) -> None:
    raw = b'{"decision":  "sigue", "final_outcome":"favorable",   "used_factors":["ninguno"], "justification":""}'
    response = await bff.client.post(
        f"{P}/cases/{w.CASE_LISTO}/decision",
        headers={**ANALISTA, "content-type": "application/json"},
        content=raw,
    )
    assert response.status_code == 200
    sent = [c for c in bff.doubles.case.calls if c.method == "POST"][0]
    assert sent.body != raw and sent.json() == {
        "decision": "sigue",
        "final_outcome": "favorable",
        "used_factors": ["ninguno"],
        "justification": "",
    }


# --- get_me (P-8) --------------------------------------------------------------------------------------------------------


async def test_get_me_comes_only_from_the_token_claims(bff: Bff) -> None:
    started = time.monotonic()
    response = await bff.client.get(f"{P}/me", headers=CRO)
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "cro" and body["mfa"] is True and body["locale"] == "es-CO" and body["auth_time"]
    assert sum(d.count() for d in bff.doubles.transports().values()) == 0  # sin llamadas a otros servicios
    assert time.monotonic() - started < 0.5


async def test_get_me_with_several_business_roles_takes_the_first_alphabetically(bff: Bff) -> None:
    response = await bff.client.get(f"{P}/me", headers=bff_tokens.bearer(["cumplimiento", "cro", "analista"]))
    assert response.json()["role"] == "analista"


async def test_get_me_with_a_password_login_reports_mfa_false(bff: Bff) -> None:
    response = await bff.client.get(f"{P}/me", headers=bff_tokens.for_state("acr_pwd", ["analista"]))
    assert response.status_code == 200 and response.json()["mfa"] is False


async def test_get_me_without_auth_time_is_403_forbidden(bff: Bff) -> None:
    response = await bff.client.get(f"{P}/me", headers=bff_tokens.bearer(["analista"], auth_time=None))
    assert response.status_code == 403 and response.json()["code"] == "forbidden"


async def test_an_undeclared_success_status_on_a_route_with_a_body_is_500(bff: Bff) -> None:
    bff.doubles.case.reply("POST", "/v1/cases", 201, b.case_ref())
    response = await bff.client.post(
        f"{P}/cases", headers=ANALISTA, json=w.REQUESTS["post_api_console_cases"].body
    )
    assert response.status_code == 500 and response.json()["code"] == "internal_error"


async def test_a_pre_read_list_that_does_not_validate_is_500_and_nothing_is_written(bff: Bff) -> None:
    bff.doubles.governance.policies = [{"policy_version_id": w.POLICY, "inventado": True}]
    response = await bff.client.post(
        f"{P}/policies/{w.POLICY}/approval", headers=CRO, json={"decision": "aprobada"}
    )
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert bff.doubles.governance.writes() == 0
