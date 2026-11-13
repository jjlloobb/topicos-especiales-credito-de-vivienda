"""U10-T03 (CA-3): el emisor OIDC de prueba y el BFF con dobles en un solo proceso (soporte de la PoC del Paso 10 y del Paso 15).

El protocolo se prueba por ASGI en memoria; el arranque como proceso real (puerto elegido, nunca 8080 ni 8081) en un
subproceso. Nombre con prefijo `bff_` (candidata F-06 de U07-T03).
"""

import base64
import hashlib
import json
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
import yaml
from bff_e2e_server import build_server
from bff_oidc import CLIENT_ID, OIDC_PATH, REALM_PATH, decode_claims

ORIGIN = "http://spa.test"
CALLBACK = f"{ORIGIN}/callback"
STEPUP = f"{ORIGIN}/stepup-callback"
VERIFIER = "v" * 64
ROOT = Path(__file__).resolve().parents[4]


def challenge_of(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def auth_query(**over: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": CALLBACK,
        "response_type": "code",
        "scope": "openid",
        "state": "st-1",
        "nonce": "nonce-1",
        "code_challenge": challenge_of(VERIFIER),
        "code_challenge_method": "S256",
        **over,
    }
    return urlencode(params)


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    server = build_server(ORIGIN)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url=ORIGIN) as client:
        client.server = server  # type: ignore[attr-defined]
        yield client


async def login(http: httpx.AsyncClient, user: str = "analista", **over: str) -> httpx.Response:
    """`GET auth` + el envio del formulario; devuelve la redireccion al `redirect_uri`."""
    page = await http.get(f"{OIDC_PATH}/auth?{auth_query(**over)}")
    if page.status_code == 303:  # ya hay sesion de SSO: el emisor responde sin formulario
        return page
    assert page.status_code == 200 and "<script" not in page.text
    query = page.text.split("name='query' value='")[1].split("'")[0]
    import html

    return await http.post(
        f"{OIDC_PATH}/login-actions/authenticate",
        data={"query": html.unescape(query), "username": user},
    )


def code_of(response: httpx.Response) -> str:
    assert response.status_code == 303
    return parse_qs(urlsplit(response.headers["location"]).query)["code"][0]


async def exchange(http: httpx.AsyncClient, code: str, **over: str) -> httpx.Response:
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER,
        **over,
    }
    return await http.post(f"{OIDC_PATH}/token", data=data)


async def test_discovery_and_jwks(http: httpx.AsyncClient) -> None:
    doc = (await http.get(f"{REALM_PATH}/.well-known/openid-configuration")).json()
    assert doc["issuer"] == f"{ORIGIN}{REALM_PATH}"
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "end_session_endpoint"):
        assert doc[key].startswith(f"{ORIGIN}{OIDC_PATH}/")
    assert doc["code_challenge_methods_supported"] == ["S256"]
    keys = (await http.get(f"{OIDC_PATH}/certs")).json()["keys"]
    assert [k["kid"] for k in keys] == ["k1"] and keys[0]["alg"] == "RS256"


async def test_code_flow_with_pkce_returns_the_nonce_and_a_token_for_the_user(
    http: httpx.AsyncClient,
) -> None:
    redirect = await login(http, "cro")
    assert redirect.headers["location"].startswith(f"{CALLBACK}?")
    assert parse_qs(urlsplit(redirect.headers["location"]).query)["state"] == ["st-1"]
    tokens = (await exchange(http, code_of(redirect))).json()
    assert decode_claims(tokens["id_token"])["nonce"] == "nonce-1"
    access = decode_claims(tokens["access_token"])
    assert (access["roles"], access["aud"], access["azp"], access["acr"]) == (
        ["cro"],
        "console-bff",
        CLIENT_ID,
        "pwd",
    )
    assert tokens["token_type"] == "Bearer" and tokens["refresh_token"]


async def test_wrong_code_verifier_is_rejected_and_a_code_works_once(http: httpx.AsyncClient) -> None:
    code = code_of(await login(http))
    bad = await exchange(http, code, code_verifier="otro" * 16)
    assert (bad.status_code, bad.json()) == (400, {"error": "invalid_grant"})
    assert (
        await exchange(http, code)
    ).status_code == 400  # el codigo ya se consumio, aun con el verificador bueno
    assert (await exchange(http, code_of(await login(http)))).status_code == 200


async def test_prompt_none_without_a_session_is_login_required(http: httpx.AsyncClient) -> None:
    redirect = await http.get(f"{OIDC_PATH}/auth?{auth_query(prompt='none')}")
    query = parse_qs(urlsplit(redirect.headers["location"]).query)
    assert (redirect.status_code, query) == (303, {"error": ["login_required"], "state": ["st-1"]})


async def test_prompt_none_with_a_session_returns_a_code_without_a_form(http: httpx.AsyncClient) -> None:
    await login(http)
    redirect = await http.get(f"{OIDC_PATH}/auth?{auth_query(prompt='none')}")
    assert (await exchange(http, code_of(redirect))).status_code == 200


async def test_prompt_login_with_acr_mfa_gives_acr_mfa_and_a_new_auth_time(http: httpx.AsyncClient) -> None:
    server = http.server  # type: ignore[attr-defined]
    now = [1_000_000.0]
    server.issuer.clock = lambda: now[0]
    first = (await exchange(http, code_of(await login(http)))).json()
    now[0] += 1000
    again = await http.get(
        f"{OIDC_PATH}/auth?{auth_query(prompt='login', max_age='0', acr_values='mfa', redirect_uri=STEPUP)}"
    )
    assert again.status_code == 200  # fuerza el formulario aunque haya sesion
    import html

    query = html.unescape(again.text.split("name='query' value='")[1].split("'")[0])
    redirect = await http.post(
        f"{OIDC_PATH}/login-actions/authenticate", data={"query": query, "username": "analista"}
    )
    assert redirect.headers["location"].startswith(f"{STEPUP}?")
    new = (await exchange(http, code_of(redirect), redirect_uri=STEPUP)).json()
    before, after = decode_claims(first["access_token"]), decode_claims(new["access_token"])
    assert (before["acr"], after["acr"]) == ("pwd", "mfa")
    assert after["auth_time"] == before["auth_time"] + 1000
    assert decode_claims(new["id_token"])["acr"] == "mfa"


async def test_a_session_without_mfa_does_not_satisfy_acr_values_mfa_even_with_prompt_none(
    http: httpx.AsyncClient,
) -> None:
    await login(http)
    redirect = await http.get(f"{OIDC_PATH}/auth?{auth_query(prompt='none', acr_values='mfa')}")
    assert parse_qs(urlsplit(redirect.headers["location"]).query)["error"] == ["interaction_required"]


async def test_refresh_rotates_and_a_reused_token_is_rejected_and_revokes_the_family(
    http: httpx.AsyncClient,
) -> None:
    first = (await exchange(http, code_of(await login(http)))).json()

    async def refresh(token: str) -> httpx.Response:
        return await http.post(
            f"{OIDC_PATH}/token",
            data={"grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": token},
        )

    second = (await refresh(first["refresh_token"])).json()
    assert second["refresh_token"] != first["refresh_token"] and second["access_token"]
    reused = await refresh(first["refresh_token"])
    assert (reused.status_code, reused.json()) == (400, {"error": "invalid_grant"})
    assert (await refresh(second["refresh_token"])).status_code == 400  # la familia se revoco


async def test_end_session_closes_the_sso_session(http: httpx.AsyncClient) -> None:
    await login(http)
    out = await http.get(f"{OIDC_PATH}/logout?post_logout_redirect_uri={ORIGIN}/&state=s")
    assert (out.status_code, out.headers["location"]) == (302, f"{ORIGIN}/?state=s")
    redirect = await http.get(f"{OIDC_PATH}/auth?{auth_query(prompt='none')}")
    assert parse_qs(urlsplit(redirect.headers["location"]).query)["error"] == ["login_required"]


async def test_a_token_of_the_issuer_works_on_get_me_of_the_bff_with_doubles(http: httpx.AsyncClient) -> None:
    tokens = (await exchange(http, code_of(await login(http, "ingeniero_riesgo")))).json()
    me = await http.get("/api/console/me", headers={"authorization": f"Bearer {tokens['access_token']}"})
    body = me.json()
    assert (me.status_code, body["role"], body["mfa"]) == (200, "ingeniero_riesgo", False)
    assert (await http.get("/api/console/me")).status_code == 401


async def test_unknown_redirect_uri_and_client_are_not_redirected(http: httpx.AsyncClient) -> None:
    for over in ({"redirect_uri": "https://evil.test/callback"}, {"client_id": "otro"}):
        response = await http.get(f"{OIDC_PATH}/auth?{auth_query(**over)}")
        assert (response.status_code, "location" in response.headers) == (400, False)
    assert (await exchange(http, "x", client_id="otro")).status_code == 401
    refused = await http.post(f"{OIDC_PATH}/token", data={"grant_type": "password", "client_id": CLIENT_ID})
    assert refused.json() == {"error": "unsupported_grant_type"}


async def test_stats_count_calls_and_reset(http: httpx.AsyncClient) -> None:
    await exchange(http, "x")
    stats = (await http.get("/auth/__e2e/stats")).json()
    assert (stats["token"], stats["token_authorization_code"]) == (1, 1)
    await http.post("/auth/__e2e/reset")
    assert (await http.get("/auth/__e2e/stats")).json()["token"] == 0


@pytest.fixture
async def demo() -> AsyncIterator[httpx.AsyncClient]:
    """El mismo servidor con el mundo del recorrido (U10-T04) y el control de pruebas."""
    server = build_server(ORIGIN, demo=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server), base_url=ORIGIN) as client:
        yield client


async def bearer_of(client: httpx.AsyncClient, user: str, **over: str) -> dict[str, str]:
    tokens = (await exchange(client, code_of(await login(client, user, **over)))).json()
    return {"authorization": f"Bearer {tokens['access_token']}"}


async def test_the_demo_world_filters_the_inbox_by_state_and_a_decision_makes_the_case_decided(
    demo: httpx.AsyncClient,
) -> None:
    auth = await bearer_of(demo, "analista")
    everything = (await demo.get("/api/console/cases", headers=auth)).json()["items"]
    only_vencido = (await demo.get("/api/console/cases?state=vencido", headers=auth)).json()["items"]
    default_states = "&".join(f"state={s}" for s in ("listo", "decidido"))
    listed = (await demo.get(f"/api/console/cases?{default_states}", headers=auth)).json()["items"]
    assert {c["state"] for c in only_vencido} == {"vencido"} and len(everything) > len(listed)
    assert {c["state"] for c in listed} == {"listo", "decidido"}
    case_id = "00000000-0000-0000-0000-000000000001"
    detail = (await demo.get(f"/api/console/cases/{case_id}", headers=auth)).json()
    assert detail["application"]["free_text"] == "<script>alert(1)</script>"
    assert detail["credit_status"] == "no_integrado" and detail["recommendation"]["outcome"] == "favorable"
    decision = {
        "decision": "sigue",
        "final_outcome": "favorable",
        "used_factors": ["ninguno"],
        "justification": "",
    }
    assert (
        await demo.post(f"/api/console/cases/{case_id}/decision", json=decision, headers=auth)
    ).status_code == 200
    assert (await demo.get(f"/api/console/cases/{case_id}", headers=auth)).json()["state"] == "decidido"


async def test_the_demo_world_lists_models_without_the_report_and_get_model_has_it(
    demo: httpx.AsyncClient,
) -> None:
    auth = await bearer_of(demo, "cumplimiento")
    listed = await demo.get("/api/console/models", headers=auth)
    assert listed.status_code == 200 and "mv-activo" in {
        m["model_version_id"] for m in listed.json()["items"]
    }
    assert all("validation_report" not in m for m in listed.json()["items"])
    one = (await demo.get("/api/console/models/mv-activo", headers=auth)).json()
    assert one["validation_report"]["auc_meets_target"] is True
    freeze = (await demo.get("/api/console/freezes/freeze-mv-congelado", headers=auth)).json()
    package = freeze["context_package"]
    assert package["before"] == "sin_datos" and package["last_7_days"] == "sin_datos"
    cells = package["after"]["attributes"][0]["cells"]
    assert [c["status"] for c in cells] == ["suficiente", "muestra_insuficiente"] and cells[1].get(
        "rate"
    ) is None  # el BFF omite los nulos


async def test_the_control_takes_a_double_down_counts_calls_and_resets(demo: httpx.AsyncClient) -> None:
    auth = await bearer_of(demo, "cumplimiento")
    assert (await demo.get("/api/console/freezes", headers=auth)).status_code == 200
    assert (await demo.get("/__e2e/count?double=bias&method=GET&template=/v1/freezes")).json() == {"count": 1}
    assert (await demo.post("/__e2e/down", json={"double": "bias"})).status_code == 200
    down = await demo.get("/api/console/freezes", headers=auth)
    assert (down.status_code, down.json()["code"]) == (503, "dependency_unavailable")
    assert (await demo.post("/__e2e/down", json={"double": "bias", "down": False})).status_code == 200
    assert (await demo.get("/api/console/freezes", headers=auth)).status_code == 200
    assert (await demo.post("/__e2e/down", json={"double": "nadie"})).status_code == 400
    assert (await demo.get("/__e2e/count?double=nadie")).status_code == 400
    await demo.post("/__e2e/down", json={"double": "case"})
    assert (await demo.post("/__e2e/reset")).status_code == 200
    assert (await demo.get("/__e2e/count?double=bias")).json() == {"count": 0}
    assert (
        await demo.get("/api/console/cases", headers=auth)
    ).status_code == 403  # `cumplimiento` no ve la bandeja


async def test_force_mfa_required_answers_403_to_the_next_resolutions_only(demo: httpx.AsyncClient) -> None:
    auth = await bearer_of(demo, "cumplimiento", acr_values="mfa")
    path = "/api/console/models/mv-congelado/frozen-resolution"
    body = {"action": "reactivar", "justification": "revisado"}
    assert (await demo.post("/__e2e/force-mfa-required", json={"times": 1})).status_code == 200
    forced = await demo.post(path, json=body, headers=auth)
    assert (forced.status_code, forced.json()["code"]) == (403, "mfa_required")
    count = "/__e2e/count?double=governance&method=POST&template=/v1/models/{id}/frozen-resolution"
    assert (await demo.get(count)).json() == {"count": 0}  # el 403 forzado no llego al destino
    assert (await demo.post(path, json=body, headers=auth)).status_code == 204  # y el siguiente envio si
    assert (await demo.get(count)).json() == {"count": 1}


def test_the_realm_of_u2_registers_the_two_callbacks_this_issuer_accepts() -> None:
    """Dato de U2 (solo lectura): el cliente `vectra-console` tiene `/callback` y `/stepup-callback`."""
    realm = yaml.safe_load((ROOT / "identity-edge/keycloak/realm/realm.kind.yaml").read_text())
    client = next(c for c in realm["clients"] if c["clientId"] == CLIENT_ID)
    assert {uri.rsplit("/", 1)[1] for uri in client["redirectUris"]} == {"callback", "stepup-callback"}
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_the_process_listens_only_on_the_chosen_port_and_never_on_8080_or_8081() -> None:
    port = free_port()
    env = {
        "VECTRA_E2E_PORT": str(port),
        "VECTRA_E2E_ORIGIN": f"http://127.0.0.1:{port}",
        "PATH": "/usr/bin:/bin",
    }
    script = ROOT / "console/bff/tests/doubles/bff_e2e_server.py"
    process = subprocess.Popen(
        [sys.executable, str(script)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )
    try:
        deadline = time.monotonic() + 30
        reply = None
        while reply is None:
            try:
                reply = httpx.get(
                    f"http://127.0.0.1:{port}{REALM_PATH}/.well-known/openid-configuration", timeout=2
                )
            except httpx.TransportError:
                assert process.poll() is None and time.monotonic() < deadline, "el servidor no arranco"
                time.sleep(0.1)
        assert json.loads(reply.text)["issuer"] == f"http://127.0.0.1:{port}{REALM_PATH}"
        listening = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, check=False).stdout
        mine = [line for line in listening.splitlines() if f"pid={process.pid}," in line]
        assert mine and all(f":{port} " in line for line in mine), mine
    finally:
        process.terminate()
        process.wait(timeout=15)


def test_the_server_refuses_the_ports_of_run_service() -> None:
    env = {"VECTRA_E2E_PORT": "8080", "VECTRA_E2E_ORIGIN": "http://127.0.0.1:8080", "PATH": "/usr/bin:/bin"}
    script = ROOT / "console/bff/tests/doubles/bff_e2e_server.py"
    done = subprocess.run(
        [sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode != 0 and "run_service" in done.stderr
