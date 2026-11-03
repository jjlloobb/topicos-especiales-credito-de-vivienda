"""Valores de `realm-drift` y `signing-key-age` leidos del diseno (INF-U2-05a, 06, 09; P-U2-05), no escritos a mano."""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
INFRASTRUCTURE = (_FD / "infrastructure-design" / "infrastructure-design.md").read_text(encoding="utf-8")


def _subsection(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = re.search(r"^#{1,3} ", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


INF_U2_06 = _subsection(INFRASTRUCTURE, "### INF-U2-06")
INF_U2_09 = _subsection(INFRASTRUCTURE, "### INF-U2-09")


def _one(pattern: str, text: str = INF_U2_09) -> str:
    found = re.findall(pattern, text)
    assert len(found) == 1, f"el diseno no fija {pattern!r} exactamente una vez: {found}"
    return str(found[0])


def admin_url() -> str:
    return _one(r"`(https://keycloak-admin[\w.-]*:8443/auth/admin/realms/vectra)`")


def token_url() -> str:
    return _one(r"`VECTRA_TOKEN_URL` = `([^`]+)`")


def pushgateway_url() -> str:
    return _one(r"a `(http://pushgateway[\w.-]*:\d+)`")


def push_paths() -> dict[str, str]:
    return {job: f"/metrics/job/{job}" for job in re.findall(r"`PUT /metrics/job/([\w-]+)`", INF_U2_09)}


def schedules() -> dict[str, str]:
    line = _one(r"- \*\*Horarios\*\*[^\n]*")
    return {job: cron for job, cron in re.findall(r"`([\w-]+)` `([^`]+)`", line)}


def concurrency_policy() -> str:
    return _one(r"`concurrencyPolicy: (\w+)`")


def image_repositories() -> tuple[str, str]:
    """(produccion y staging, kind)."""
    registry = _one(r"`(registro\.banco\.internal/vectra/identity-jobs)`")
    kind = _one(r"`(kind-registry:5000/vectra/identity-jobs)`")
    return registry, kind


def base_image() -> str:
    return _one(r"sobre `(docker\.io/library/python:[\w.-]+@sha256:[0-9a-f]{64})`")


def priority_class() -> str:
    return _one(r"prioridad `(vectra-[\w]+)`")


def service_accounts() -> list[str]:
    return re.findall(r"`(realm-drift|signing-key-age)`", _one(r"- Cuentas de servicio ([^\n]*)"))[:2]


def resources() -> dict[str, dict[str, str]]:
    """INF-U2-06, fila de `keycloak-config-cli`, `realm-drift` y `signing-key-age`."""
    m = re.search(
        r"^\| `keycloak-config-cli`, `realm-drift`, `signing-key-age` \| ([^|]+) \| ([^|]+) \|",
        INF_U2_06,
        re.MULTILINE,
    )
    assert m, "INF-U2-06 no fija los recursos de los CronJobs"

    def pair(cell: str) -> dict[str, str]:
        cpu, memory = (part.strip() for part in cell.split("/"))
        mem = re.fullmatch(r"(\d+) (MiB|GiB)", memory)
        assert mem, memory
        return {"cpu": cpu, "memory": f"{mem.group(1)}{'Mi' if mem.group(2) == 'MiB' else 'Gi'}"}

    return {"requests": pair(m.group(1)), "limits": pair(m.group(2))}
