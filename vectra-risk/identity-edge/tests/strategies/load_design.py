"""Valores de diseno de la prueba de carga de U2 (U02-T15, Paso 14), leidos de los documentos y del modelo.

Nada de esto es un literal de la prueba: sale de NFR-U2-10..11 (nfr-requirements), de la nota J1-J7 del Paso 14 del plan,
del realm de kind, de `routes.yaml` y de domain-entities. Los textos son atributos del modulo para que una prueba pueda alterarlos.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from design_values import mfa_required_roles, optional_mfa_roles
from gateway_design import NFR_REQUIREMENTS

_ROOT = Path(__file__).resolve().parents[3]
EDGE = _ROOT / "identity-edge"
PLAN = (_ROOT / "aidlc-docs" / "construction" / "plans" / "identity-edge-code-generation-plan.md").read_text(encoding="utf-8")
REALM = EDGE / "keycloak" / "realm" / "realm.kind.yaml"
# La ventana en segundos de cada `unit` de un contador de `routes.yaml` (Envoy Ratelimit).
WINDOW_SECONDS = {"Second": 1, "Minute": 60, "Hour": 3600, "Day": 86400}
ROUTES = EDGE / "gateway" / "routes.yaml"
SCRIPT = EDGE / "tests" / "load" / "identity.js"
SEED = EDGE / "tests" / "load" / "seed_users.py"
K6 = _ROOT / "platform" / ".tools" / "bin" / "k6"


def realm() -> dict[str, Any]:
    return yaml.safe_load(REALM.read_text(encoding="utf-8"))


def routes() -> dict[str, Any]:
    return yaml.safe_load(ROUTES.read_text(encoding="utf-8"))


def _nfr_row(nfr_id: str) -> str:
    return next(line for line in NFR_REQUIREMENTS.splitlines() if line.startswith(f"| {nfr_id} |"))


def _step_14() -> str:
    """El Paso 14 con cualquier estado del checkbox (`[ ]` o `[x]`)."""
    found = re.search(r"- \[[ xX]\] \*\*Paso 14", PLAN)
    assert found, "el plan no tiene el Paso 14"
    return PLAN[found.start() : PLAN.index("**Paso 15", found.start())]


def _decision(label: str) -> str:
    found = re.search(rf"\*\*{label}\*\*: (.*)", _step_14())
    assert found, f"la nota del Paso 14 no tiene {label}"
    return found.group(1)


@dataclass(frozen=True)
class Thresholds:
    login_p95_ms: int
    token_p95_ms: int
    jwks_p95_ms: int
    overhead_p95_ms: int
    failed_rate: float  # fraccion, no por ciento


def thresholds() -> Thresholds:
    """NFR-U2-10 (login, token, JWKS), NFR-U2-11 (sobrecosto) y J7 (`http_req_failed`)."""
    found = re.search(r"login p95 ≤ (\d+) ms, endpoint de token p95 ≤ (\d+) ms, JWKS p95 ≤ (\d+) ms", _nfr_row("NFR-U2-10"))
    assert found, "NFR-U2-10 sin los tres umbrales"
    overhead = re.search(r"p95 ≤ (\d+) ms por request", _nfr_row("NFR-U2-11"))
    assert overhead, "NFR-U2-11 sin el umbral"
    failed = re.search(r"`http_req_failed` < (\d+(?:[.,]\d+)?) %", _decision("J7"))
    assert failed, "J7 sin el umbral de http_req_failed"
    return Thresholds(
        int(found.group(1)), int(found.group(2)), int(found.group(3)), int(overhead.group(1)),
        float(failed.group(1).replace(",", ".")) / 100,
    )  # fmt: skip


def concurrent_users() -> int:
    found = re.search(r"(\d+) usuarios concurrentes", _nfr_row("NFR-U2-10"))
    assert found
    return int(found.group(1))


def service_identities() -> int:
    found = re.search(r"y (\d+) identidades de servicio", _nfr_row("NFR-U2-10"))
    assert found
    return int(found.group(1))


def renew_seconds() -> int:
    """«renovando cada 5 min» de NFR-U2-10."""
    found = re.search(r"renovando cada (\d+) min", _nfr_row("NFR-U2-10"))
    assert found
    return int(found.group(1)) * 60


def ramp_and_sustain_seconds() -> tuple[int, int]:
    """J7: «2 min de subida y 15 min sostenidos»."""
    found = re.search(r"(\d+) min de subida y (\d+) min sostenidos", _decision("J7"))
    assert found, "J7 sin el perfil"
    return int(found.group(1)) * 60, int(found.group(2)) * 60


def login_rate_ceiling() -> int:
    """J5: los logins por debajo de N/s."""
    found = re.search(r"por debajo de (\d+)/s", _decision("J5"))
    assert found, "J5 sin el techo de logins"
    return int(found.group(1))


def load_users() -> tuple[str, int, int]:
    """J1: `load-001..200` -> (`load-`, 1, 200)."""
    found = re.search(r"(\d+) usuarios `([a-z]+-)(\d+)\.\.(\d+)`", _decision("J1"))
    assert found, "J1 sin los usuarios de carga"
    first, last = int(found.group(3)), int(found.group(4))
    assert last - first + 1 == int(found.group(1))
    return found.group(2), first, last


def service_clients() -> set[str]:
    """J6: los clientes con service account de `realm.kind.yaml`, menos los que nombra la nota del Paso 14."""
    sentence = next(
        line for line in _step_14().splitlines() if "clientes con service account de `realm.kind.yaml`, menos" in line
    )
    excluded = set(re.findall(r"`([a-z-]+)`", sentence.split("menos", 1)[1]))
    accounts = {c["clientId"] for c in realm()["clients"] if c.get("serviceAccountsEnabled")}
    assert excluded <= accounts, f"la nota excluye clientes que no existen: {excluded - accounts}"
    return accounts - excluded


def console_limit_per_second() -> float:
    """El contador `console` de `routes.yaml` en req/s."""
    limit = next(r for r in routes()["rate_limits"] if r["name"] == "console")
    return limit["requests"] / WINDOW_SECONDS[limit["unit"]]


def console_retry_after() -> str:
    return str(next(r for r in routes()["routes"] if r["name"] == "console")["retry_after"])


def load_role() -> str:
    """El rol de los usuarios de carga: opcional segun domain-entities §1.1, sin MFA obligatorio (BR-U2-03) y con login sin TOTP en el realm.

    El realm lo confirma: el subflujo `vectra-mfa-<rol>` del rol lleva `conditional-user-configured`, asi que un usuario sin
    credencial OTP entra solo con contrasena (nivel `pwd`), y `vectra-console` no restringe por rol.
    """
    candidates = sorted(optional_mfa_roles() - mfa_required_roles())
    flows = {f["alias"]: f for f in realm()["authenticationFlows"]}
    viable = []
    for role in candidates:
        flow = flows.get(f"vectra-mfa-{role}")
        if flow and any(e.get("authenticator") == "conditional-user-configured" for e in flow["authenticationExecutions"]):
            viable.append(role)
    assert len(viable) == 1, f"ningun rol (o varios) entra sin TOTP: {candidates} -> {viable}"
    return viable[0]

