#!/usr/bin/env python3
"""Humo de kind (U12-T06, Paso 18): el login por rol, el flujo base y la consola, con los clientes de `vectra_verification`.

No es una seccion de la CLI ni escribe en `evidence/` de la herramienta: imprime un resumen que el operador pega en la plantilla de su fase. Nunca imprime un token, una cookie, una
contrasena ni una semilla; de la cookie solo dice si esta y de los claims, solo los que la plantilla pide. Pasa por `guard`: solo corre contra kind (el emisor y el host, exactos).
Lo ejecuta el operador **desde la imagen de U12** (lleva Chromium y las dependencias); ver `docs/paso-18-kind.md`.

    humo.py login                  los cinco usuarios de `credentials.USERS` entran por el gateway real: iss, aud, acr, amr, roles y auth_time (K-27 a K-29)
    humo.py flujo --delivery D     una solicitud `normal` por el gateway llega a `listo` con `registry_entry_id`; el detalle y la explicacion por el BFF; una decision de analista-1;
                                   `/api/console/models` con ingeniero-1 y `/api/console/freezes` con cumplimiento-1. Informa el estado HTTP de cada llamada (K-30, K-31, K-36, K-38)
    humo.py consola                la SPA real en Chromium sin interfaz: login por redireccion completa, recarga, eventos `securitypolicyviolation` y la cookie de afinidad (K-35)
    humo.py modelos                el JSON `[{model_version_id, state}]` de `/api/console/models` (con ingeniero-1), para `estado-final.sh --modelos -`

`flujo --delivery D`: D es la entrega de U5; dentro de la imagen, `/verification/reference-model/.out` (la ruta relativa por omision no existe alli y da 2).
Opciones comunes: `--issuer`, `--gateway-host` y `--ca-file` (o `VERIFICATION_ISSUER`, `VERIFICATION_GATEWAY_HOST` y `VERIFICATION_CA_FILE`), como la CLI. La boveda, por `VAULT_ADDR` y
`VAULT_TOKEN`. Salida: 0 bien, 1 hallazgos, 2 no se pudo (falta un prerrequisito o una lectura), 3 la herramienta se nego (la barrera de entorno).

Los codigos TOTP no se pueden reusar dentro de su ventana de 30 s: espera 30 s antes de repetir un comando con los mismos usuarios (un codigo rechazado cuenta para el bloqueo por fuerza bruta).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import ssl
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, TextIO
from urllib.parse import urlsplit

import httpx
from vectra_contracts.catalog import CaseState, Decision, FinalOutcome, Outcome
from vectra_contracts.models.api import DecisionIn
from vectra_verification import guard
from vectra_verification.clients._api import ApiError, RunTag
from vectra_verification.clients.bff import BASE, BffClient
from vectra_verification.clients.gateway import GatewayClient
from vectra_verification.clients.oidc import OidcClient, OidcError, server_spki_pin
from vectra_verification.clock import Clock
from vectra_verification.credentials import USERS, Credentials, CredentialsError
from vectra_verification.driver import JUSTIFICATION
from vectra_verification.guard import GuardError
from vectra_verification.scenarios.common import list_all_models
from vectra_verification.simulator import read_delivery

ROLE_OF: Final = {
    "analista-1": "analista",
    "analista-2": "analista",
    "ingeniero-1": "ingeniero_riesgo",
    "cro-1": "cro",
    "cumplimiento-1": "cumplimiento",
}
BFF_AUDIENCE: Final = "console-bff"
SPA_AFFINITY_COOKIE: Final = "vectra-spa-route"
DEFAULT_TIMEOUT: Final = 300.0
POLL_SECONDS: Final = 3.0
UUID_IN_PATH: Final = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}")
# A quien apunta un 401 en cada llamada (K-30): el destino que recibe el token del navegador (F10 a F14).
DESTINATIONS: Final = (
    ("/api/intake/", "case-service (ingesta)"),
    ("/explanation-views", "explainability-service y case-service"),
    ("/decision", "case-service"),
    ("/api/console/cases", "case-service"),
    ("/api/console/models", "governance-service"),
    ("/api/console/freezes", "bias-monitoring-service"),
)
HINTS: Final = {
    "token_issuer_not_allowed": "el iss del token no es el publico del entorno: el emisor que publica Keycloak o el que valida el servicio (U2; EMISOR en la guia)",
    "login_rejected": "Keycloak rechazo el formulario: contrasena o TOTP mal (si repetiste un comando antes de 30 s, es el reuso del TOTP), usuario bloqueado, o el realm viejo (U2)",
    "login_form_missing": "no hay formulario de Keycloak: el emisor o el gateway no responden como se espera (U2)",
    "login_timeout": "el login no termino a tiempo: Keycloak lento o colgado (U2)",
    "browser_error": "Chromium no pudo completar la navegacion (TLS, red o la CA): revisa --ca-file y el sandbox de la imagen",
    "browser_launch_error": "Chromium no arranca: revisa el perfil seccomp y el sandbox de la orden docker run (README de la imagen)",
    "acr_not_mfa": "el token no trae acr = mfa: el flujo de autenticacion del realm no pide el segundo factor (U2, realm)",
    "token_audience_invalid": "el token no trae la aud console-bff (U2, realm)",
    "vault_session_missing": "faltan VAULT_ADDR y VAULT_TOKEN",
}


class HumoError(Exception):
    """Un fallo del humo con un codigo estable; el mensaje no lleva credenciales."""


@dataclass
class Recorder:
    """El estado HTTP de cada llamada, tomado de un gancho de respuesta del cliente (el cliente no lo expone)."""

    calls: list[tuple[str, str, int]] = field(default_factory=list)

    def attach(self, client: Any) -> None:
        client._http.event_hooks["response"].append(self._hook)  # noqa: SLF001

    def _hook(self, response: httpx.Response) -> None:
        path = UUID_IN_PATH.sub("{id}", response.request.url.path)
        self.calls.append((response.request.method, path, response.status_code))


@dataclass
class World:
    environment: guard.Environment
    oidc: Any
    credentials: Credentials
    clock: Clock
    transport: httpx.BaseTransport | None
    verify: ssl.SSLContext | bool
    close: Callable[[], None]

    def bff(self, user: str, recorder: Recorder | None = None) -> BffClient:
        client = BffClient(
            self.environment,
            self.oidc.login(user),
            RunTag("humo", secrets.token_hex(4)),
            transport=self.transport,
            verify=self.verify,
        )
        if recorder is not None:
            recorder.attach(client)
        return client


def build_world(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    *,
    vault_transport: httpx.BaseTransport | None = None,
    transport: httpx.BaseTransport | None = None,
    clock: Clock | None = None,
) -> World:
    """La barrera de entorno primero (antes de cualquier solicitud); despues la boveda y el cliente OIDC. Solo kind."""
    environment = guard.check_environment(args.issuer, args.gateway_host)
    if environment.name != guard.KIND.name:
        raise GuardError(f"humo_only_in_kind:{environment.name}")
    credentials = Credentials.from_environ(environment, environ, vault_transport)
    ca = Path(args.ca_file) if args.ca_file else None
    verify: ssl.SSLContext | bool = ssl.create_default_context(cafile=str(ca)) if ca else True
    the_clock = clock or Clock()
    oidc = OidcClient(environment, credentials, the_clock, ca_file=ca)
    return World(environment, oidc, credentials, the_clock, transport, verify, oidc.close)


def explain(error: Exception) -> str:
    code = str(error).split(":", 1)[0]
    hint = HINTS.get(code)
    return f"{code}: {hint}" if hint else str(error)


# ---- login -----------------------------------------------------------------------------------------------------------------------------------------


def login(world: World, out: TextIO) -> int:
    """Los cinco usuarios por el gateway real: iss, aud, acr, amr, roles y auth_time. Nunca el token."""
    failures = 0
    for user in USERS:
        try:
            session = world.oidc.login(user)
        except (OidcError, CredentialsError) as error:
            out.write(f"FALLA {user}: {explain(error)}\n")
            failures += 1
            continue
        claims = session.claims
        audience = claims.get("aud", [])
        audiences = [audience] if isinstance(audience, str) else list(audience)
        roles = claims.get("roles", [])
        roles = [roles] if isinstance(roles, str) else list(roles)
        amr = claims.get("amr", [])
        auth_time = session.auth_time.isoformat() if session.auth_time else "-"
        problems = []
        if claims.get("iss") != world.environment.issuer:
            problems.append(f"iss distinto del publico ({world.environment.issuer})")
        if session.acr != "mfa":
            problems.append("acr distinto de mfa")
        if BFF_AUDIENCE not in audiences:
            problems.append(f"aud sin {BFF_AUDIENCE}")
        if ROLE_OF[user] not in roles:
            problems.append(f"sin el rol {ROLE_OF[user]}")
        out.write(
            f"{'FALLA' if problems else 'OK   '} {user}: iss={claims.get('iss')} aud={audiences} acr={session.acr} amr={list(amr)} roles={roles} auth_time={auth_time}"
            + (f"  <- {'; '.join(problems)}" if problems else "")
            + "\n"
        )
        failures += bool(problems)
    out.write(
        f"login: {len(USERS) - failures} de {len(USERS)} usuarios bien; espera 30 s antes de repetir un comando con los mismos usuarios (reuso del TOTP)\n"
    )
    return 1 if failures else 0


# ---- flujo -----------------------------------------------------------------------------------------------------------------------------------------


def destination_of(path: str) -> str:
    return next((name for needle, name in DESTINATIONS if needle in path), "el destino de la llamada")


def report_calls(recorder: Recorder, out: TextIO) -> int:
    """El estado de cada llamada (sin repetir los sondeos) y los 401 y 429 con su destino. Devuelve cuantos hallazgos hubo."""
    counts: Counter[tuple[str, str, int]] = Counter(recorder.calls)
    for (method, path, status), n in sorted(counts.items()):
        out.write(f"  {status} {method} {path}" + (f" x{n}" if n > 1 else "") + "\n")
    found = 0
    for (method, path, status), _ in sorted(counts.items()):
        if status == 401:
            out.write(
                f"FALLA 401 en {method} {path}: el destino {destination_of(path)} rechaza el token (emisor o aud; K-30, K-31)\n"
            )
            found += 1
        elif status == 429:
            out.write(f"FALLA 429 en {method} {path}: limite del gateway (K-37)\n")
            found += 1
    return found


def decision_for(detail: Any) -> DecisionIn:
    """La decision mas simple y valida: sigue la recomendacion; si pide revision, la resuelve con justificacion."""
    recommendation = detail.recommendation
    if recommendation is None:
        raise HumoError("case_without_recommendation")
    if recommendation.outcome is Outcome.REVISION_REQUERIDA:
        return DecisionIn(
            decision=Decision.RESUELVE_REVISION,
            final_outcome=FinalOutcome.FAVORABLE,
            used_factors=["ninguno"],
            justification=JUSTIFICATION,
        )
    final = (
        FinalOutcome.FAVORABLE if recommendation.outcome is Outcome.FAVORABLE else FinalOutcome.DESFAVORABLE
    )
    return DecisionIn(
        decision=Decision.SIGUE, final_outcome=final, used_factors=["ninguno"], justification=""
    )


def flujo(world: World, args: argparse.Namespace, out: TextIO, *, population: Any = None) -> int:
    recorder = Recorder()
    clock = world.clock
    try:
        population = population or read_delivery(Path(args.delivery), clock.now())
        service = world.oidc.service_session("channel-simulator", ("intake:submit",))
        gateway = GatewayClient(
            world.environment,
            service.bearer,
            RunTag("normal", secrets.token_hex(4)),
            transport=world.transport,
            verify=world.verify,
        )
        recorder.attach(gateway)
        analyst = world.bff("analista-1", recorder)
    except (OidcError, CredentialsError, ApiError, OSError, ValueError) as error:
        out.write(f"NO SE PUDO preparar el flujo: {explain(error)}\n")
        return 2
    failed = False
    try:
        reference = gateway.submit_application(population.applications[0], f"humo-{secrets.token_hex(8)}")
        out.write(
            f"solicitud aceptada: caso {reference.case_id} (la cabecera de escenario se acepto: K-36)\n"
        )
        deadline = clock.monotonic() + args.timeout
        detail = analyst.get_case(reference.case_id)
        while detail.state is not CaseState.LISTO and clock.monotonic() < deadline:
            clock.sleep(POLL_SECONDS)
            detail = analyst.get_case(reference.case_id)
        if detail.state is not CaseState.LISTO:
            out.write(
                f"FALLA el caso no llego a listo en {args.timeout:.0f} s: quedo en {detail.state.value} (causa {detail.last_cause or '-'}; K-31, K-15, R-5)\n"
            )
            failed = True
        else:
            entry = detail.recommendation.registry_entry_id if detail.recommendation else None
            if not entry:
                out.write("FALLA el caso esta listo pero la recomendacion no trae registry_entry_id\n")
                failed = True
            else:
                out.write(f"OK   caso listo con registry_entry_id {entry}\n")
            analyst.record_explanation_view(reference.case_id)
            ref = analyst.record_decision(reference.case_id, decision_for(detail))
            out.write(f"OK   decision registrada con ack: registry_entry_id {ref.registry_entry_id}\n")
        models = world.bff("ingeniero-1", recorder).list_models(page=1, page_size=50)
        out.write(f"OK   /api/console/models con ingeniero-1: {len(models.items)} versiones\n")
        world.bff("cumplimiento-1", recorder)._send("GET", f"{BASE}/freezes")  # noqa: SLF001 - la lectura simple, sin modelo
        out.write("OK   /api/console/freezes con cumplimiento-1\n")
    except ApiError as error:
        out.write(f"FALLA {error}\n")
        failed = True
    except (OidcError, CredentialsError, HumoError) as error:
        out.write(f"FALLA {explain(error)}\n")
        failed = True
    out.write("estado HTTP de cada llamada:\n")
    return 1 if (report_calls(recorder, out) or failed) else 0


# ---- modelos ---------------------------------------------------------------------------------------------------------------------------------------


def modelos(world: World, out: TextIO, err: TextIO) -> int:
    try:
        models = list_all_models(world.bff("ingeniero-1"))
    except (OidcError, CredentialsError, ApiError) as error:
        err.write(f"NO SE PUDO leer los modelos: {explain(error)}\n")
        return 2
    out.write(
        json.dumps([{"model_version_id": m.model_version_id, "state": str(m.state)} for m in models]) + "\n"
    )
    return 0


# ---- consola ---------------------------------------------------------------------------------------------------------------------------------------

CSP_LISTENER: Final = """
document.addEventListener('securitypolicyviolation', (e) => {
  window.__humoCsp({directive: e.violatedDirective, blocked: String(e.blockedURI).slice(0, 80), disposition: e.disposition});
});
"""


def launch_options(extra_args: Sequence[str]) -> dict[str, Any]:
    """Como se lanza Chromium: sin interfaz y **con** su sandbox (Playwright lo apaga por omision; aqui se pide). Un solo sitio, para que una prueba lo fije."""
    return {"headless": True, "chromium_sandbox": True, "args": list(extra_args)}


def consola(world: World, args: argparse.Namespace, out: TextIO) -> int:
    """Abre la SPA real, hace el login por redireccion completa (sin interceptar el `redirect_uri`), recarga y cuenta los `securitypolicyviolation`. El sandbox de Chromium siempre activo."""
    from playwright.sync_api import Error as PlaywrightError  # noqa: PLC0415 - solo si se pide `consola`
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    url = args.spa_url or f"https://{world.environment.host}/"
    user = "analista-1"
    try:
        password = world.credentials.user_password(user).reveal()
        parts = urlsplit(url)
        launch_args = []
        if parts.scheme == "https":
            ca = Path(args.ca_file) if args.ca_file else None
            pin = server_spki_pin(parts.hostname or "", parts.port or 443, ca)
            launch_args.append(f"--ignore-certificate-errors-spki-list={pin}")
    except (CredentialsError, OidcError, OSError) as error:
        out.write(f"NO SE PUDO preparar la consola: {explain(error)}\n")
        return 2
    violations: list[dict[str, str]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_options(launch_args))
            try:
                context = browser.new_context(ignore_https_errors=False, service_workers="block")
                context.expose_function("__humoCsp", lambda payload: violations.append(payload))
                context.add_init_script(CSP_LISTENER)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.locator("input[name=username]").wait_for(timeout=30_000)
                page.locator("input[name=username]").fill(user)
                page.locator("input[name=password]").fill(password)
                page.locator("[type=submit]").first.click(no_wait_after=True)
                page.locator("input[name=otp]").wait_for(timeout=30_000)
                page.locator("input[name=otp]").fill(world.oidc.otp_code(user))
                page.locator("[type=submit]").first.click(no_wait_after=True)
                page.wait_for_url(
                    lambda u: "/auth/" not in u and "/callback" not in u and "state=" not in u, timeout=30_000
                )
                page.wait_for_load_state("networkidle", timeout=30_000)
                logged_in = urlsplit(page.url).path
                page.reload(wait_until="networkidle", timeout=30_000)
                after_reload = urlsplit(page.url).path
                cookie = any(c["name"] == SPA_AFFINITY_COOKIE for c in context.cookies())
            finally:
                browser.close()
    except PlaywrightError as error:
        if "sandbox" in str(error).lower():
            out.write(
                "FALLA Chromium no arranca con su sandbox: el host no permite espacios de nombres de usuario sin privilegios o falta el perfil seccomp de la orden docker run "
                "(README de la imagen). La herramienta nunca lo desactiva\n"
            )
        else:
            out.write(
                f"FALLA Chromium no completo la consola ({type(error).__name__}): revisa la CA y la red de la imagen\n"
            )
        return 1
    out.write(
        f"OK   login por redireccion completa; la SPA quedo en {logged_in}; tras recargar, en {after_reload} (sin volver al formulario)\n"
    )
    found = 0
    if "/auth/" in after_reload:
        out.write(
            "FALLA tras recargar la SPA volvio al formulario: la renovacion silenciosa (prompt=none) no funciona\n"
        )
        found += 1
    out.write(f"securitypolicyviolation: {len(violations)}\n")
    for violation in violations:
        out.write(
            f"FALLA CSP {violation.get('disposition')}: {violation.get('directive')} bloqueo {violation.get('blocked')}\n"
        )
    found += len(violations)
    out.write(
        f"cookie {SPA_AFFINITY_COOKIE}: {'presente' if cookie else 'AUSENTE'} (solo se dice si esta; nunca su valor)\n"
    )
    if not cookie:
        out.write("FALLA la cookie de afinidad del gateway no llego al navegador (K-35)\n")
        found += 1
    return 1 if found else 0


# ---- entrada ---------------------------------------------------------------------------------------------------------------------------------------


def parser(environ: Mapping[str, str]) -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="humo.py", description=__doc__.split("\n", 1)[0] if __doc__ else None)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--issuer", default=environ.get("VERIFICATION_ISSUER", guard.KIND.issuer))
    common.add_argument("--gateway-host", default=environ.get("VERIFICATION_GATEWAY_HOST", guard.KIND.host))
    common.add_argument("--ca-file", default=environ.get("VERIFICATION_CA_FILE"))
    sub = top.add_subparsers(dest="command", metavar="login|flujo|consola|modelos", required=True)
    sub.add_parser("login", parents=[common])
    flow = sub.add_parser("flujo", parents=[common])
    flow.add_argument(
        "--delivery",
        default="reference-model/.out",
        help="la entrega de U5 (datasets/test.parquet); dentro de la imagen, /verification/reference-model/.out (la ruta por omision es relativa)",
    )
    flow.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="segundos hasta que el caso llegue a listo"
    )
    sub.add_parser("modelos", parents=[common])
    console = sub.add_parser("consola", parents=[common])
    console.add_argument("--spa-url", default=None, help="por omision https://<host del gateway>/")
    return top


def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
    world: World | None = None,
    vault_transport: httpx.BaseTransport | None = None,
    transport: httpx.BaseTransport | None = None,
    clock: Clock | None = None,
    population: Any = None,
) -> int:
    env = os.environ if environ is None else environ
    stdout, stderr = out or sys.stdout, err or sys.stderr
    args = parser(env).parse_args(argv)
    try:
        the_world = world or build_world(
            args, env, vault_transport=vault_transport, transport=transport, clock=clock
        )
    except GuardError as error:
        stderr.write(f"LA HERRAMIENTA SE NIEGA: {error}\n")
        return 3
    except CredentialsError as error:
        stderr.write(f"NO SE PUDO: {explain(error)}\n")
        return 2
    try:
        if args.command == "login":
            return login(the_world, stdout)
        if args.command == "flujo":
            return flujo(the_world, args, stdout, population=population)
        if args.command == "modelos":
            return modelos(the_world, stdout, stderr)
        return consola(the_world, args, stdout)
    finally:
        the_world.close()


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["HINTS", "World", "build_world", "main"]
