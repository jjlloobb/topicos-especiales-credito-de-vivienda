"""Despliegue de Keycloak (U02-T07, Paso 5): lectura del diseno, render y conftest.

Los valores (hostnames, recursos, repositorio, claves de la boveda, TLS) se leen del diseno, no de constantes.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[3]
EDGE = _ROOT / "identity-edge"
KEYCLOAK = EDGE / "keycloak"
POLICY = KEYCLOAK / "policy"
VALUES = KEYCLOAK / "values"
RENDERED = KEYCLOAK / "rendered"
CHART = _ROOT / "platform" / ".charts" / "keycloakx" / "keycloakx"
HELM = _ROOT / "platform" / ".tools" / "bin" / "helm"
CONFTEST = _ROOT / "platform" / ".tools" / "bin" / "conftest"
ENVS = ("kind", "staging", "prod")
NAMESPACE = "vectra-identity"
# Los ExternalSecret de la excepcion de kind (U02-T19, INF-U2-05a); el resto son los de INF-U2-01.
CONFIG_CLI_EXTERNAL_SECRETS = frozenset({"keycloak-bootstrap-admin", "keycloak-realm-clients-jwks", "keycloak-realm-synthetic-users"})

_FD = _ROOT / "aidlc-docs" / "construction" / "identity-edge"
BUSINESS_RULES = (_FD / "functional-design" / "business-rules.md").read_text(encoding="utf-8")
INFRASTRUCTURE = (_FD / "infrastructure-design" / "infrastructure-design.md").read_text(encoding="utf-8")
NFR_REQUIREMENTS = (_FD / "nfr-requirements" / "nfr-requirements.md").read_text(encoding="utf-8")
NFR_PATTERNS = (_FD / "nfr-design" / "nfr-design-patterns.md").read_text(encoding="utf-8")


def _subsection(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = re.search(r"^#{1,3} ", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


INF_U2_01 = _subsection(INFRASTRUCTURE, "### INF-U2-01")
INF_U2_05A = _subsection(INFRASTRUCTURE, "### INF-U2-05a")
INF_U2_05B = _subsection(INFRASTRUCTURE, "### INF-U2-05b")
INF_U2_06 = _subsection(INFRASTRUCTURE, "### INF-U2-06")
INF_U2_08 = _subsection(INFRASTRUCTURE, "### INF-U2-08")
P_U2_04 = _subsection(NFR_PATTERNS, "### P-U2-04")


# --- diseno -----------------------------------------------------------------------------------

def design_public_hostnames() -> dict[str, str]:
    """entorno -> hostname publico de la tabla de INF-U2-01."""
    found = {}
    for env in ENVS:
        m = re.search(rf"^\| {env} \| `([\w.-]+)` \|", INF_U2_01, re.MULTILINE)
        assert m, f"INF-U2-01 no fija el hostname de {env}"
        found[env] = m.group(1)
    return found


def design_admin_hostname() -> str:
    m = re.search(r"`hostname-admin` = `([\w.-]+)`", INF_U2_01)
    assert m, "INF-U2-01 no fija hostname-admin"
    return m.group(1)


def design_hostname_path() -> str:
    m = re.search(r"`hostname` = el público con el path `(/\w+)`", INF_U2_01)
    assert m, "INF-U2-01 no fija el path de hostname"
    return m.group(1)


def design_keycloak_resources() -> dict[str, dict[str, str]]:
    """Requests y limits de Keycloak de la tabla de INF-U2-06, como cantidades de Kubernetes."""
    m = re.search(r"^\| Keycloak \| ([^|]+) \| ([^|]+) \|", INF_U2_06, re.MULTILINE)
    assert m, "INF-U2-06 no fija los recursos de Keycloak"

    def pair(cell: str) -> dict[str, str]:
        cpu, memory = (part.strip() for part in cell.split("/"))
        cpu_m = re.fullmatch(r"(\d+m|\d+) ?(CPU)?", cpu)
        mem_m = re.fullmatch(r"(\d+) GiB", memory)
        assert cpu_m and mem_m, f"recurso con otra forma: {cell}"
        return {"cpu": cpu_m.group(1), "memory": f"{mem_m.group(1)}Gi"}

    return {"requests": pair(m.group(1)), "limits": pair(m.group(2))}


def design_max_ram_percentage() -> str:
    m = re.search(r"^\| Keycloak \|[^|]+\|[^|]+\| `(-XX:MaxRAMPercentage=\d+)` \|", INF_U2_06, re.MULTILINE)
    assert m, "INF-U2-06 no fija MaxRAMPercentage"
    return m.group(1)


def design_event_success_level() -> tuple[str, str]:
    """(variable, valor) de la nota H11 de BR-U2-16: el listener `jboss-logging` escribe los eventos de exito en `info`."""
    m = re.search(r"Nota H11.*?variable `(KC_SPI_EVENTS_LISTENER__JBOSS_LOGGING__SUCCESS_LEVEL)=(\w+)`", BUSINESS_RULES, re.DOTALL)
    assert m, "BR-U2-16 no fija la variable de la nota H11"
    return m.group(1), m.group(2)


def design_replicas() -> tuple[int, int]:
    """(minimo, maximo) del HPA de P-U2-04."""
    m = re.search(r"HPA de (\d) a (\d)", P_U2_04)
    assert m, "P-U2-04 no fija el HPA"
    return int(m.group(1)), int(m.group(2))


def design_pdb_min_available() -> int:
    m = re.search(r"PDB `minAvailable: (\d+)`", P_U2_04)
    assert m
    return int(m.group(1))


def design_image_repositories() -> dict[str, str]:
    """entorno -> repositorio de la imagen (INF-U2-08, enmienda Q2)."""
    m = re.search(r"repositorio `([\w./-]+)` \(`([\w./:-]+)` en kind\)", INF_U2_08)
    assert m, "INF-U2-08 no fija el repositorio"
    return {"kind": m.group(2), "staging": m.group(1), "prod": m.group(1)}


def design_chart_version() -> str:
    m = re.search(r"`keycloakx` de codecentric, versión \*\*([\d.]+)\*\*", INF_U2_08)
    assert m, "INF-U2-08 no fija la version del chart"
    return m.group(1)


def design_vault_entries() -> dict[str, str]:
    """clave de la boveda -> propiedad, para los ExternalSecret de este paso (INF-U2-01 e INF-U2-05a)."""
    ca = re.search(r"`(identity/ca)`, propiedad `([\w.-]+)`", INF_U2_01)
    assert ca, "INF-U2-01 no fija la clave de la CA"
    prop = re.search(r"propiedades `([\w-]+)` \(PEM", INF_U2_01)
    assert prop, "INF-U2-01 no fija la propiedad de la llave de los clientes"
    prefix = re.search(r"`(identity/clients)/<clientId>`", INF_U2_01)
    assert prefix
    clients = re.findall(r"^  - `([\w-]+)`: su cuenta de servicio", INF_U2_05A, re.MULTILINE)
    assert clients == ["keycloak-config-cli", "keycloak-reader"], clients
    entries = {ca.group(1): ca.group(2)}
    for client in clients:
        entries[f"{prefix.group(1)}/{client}"] = prop.group(1)
    return entries


def design_certificate() -> dict[str, Any]:
    """SAN (en orden), vigencia y renovacion de INF-U2-05b."""
    san = re.search(r"SAN `([\w.-]+)` y `([\w.-]+)`", INF_U2_05B)
    days = re.search(r"(\d+) días, se renueva a los (\d+)", INF_U2_05B)
    assert san and days, "INF-U2-05b no fija los SAN y la vigencia"
    return {
        "sans": [san.group(1), san.group(2)],
        "duration": f"{int(days.group(1)) * 24}h",
        "renewBefore": f"{(int(days.group(1)) - int(days.group(2))) * 24}h",
    }


def design_hpa_utilization() -> int:
    """Objetivo de utilizacion de CPU de NFR-U2-01."""
    row = re.search(r"^\| NFR-U2-01 \|(.*)$", NFR_REQUIREMENTS, re.MULTILINE)
    assert row
    m = re.search(r"objetivo de utilización del (\d+) %", row.group(1))
    assert m, "NFR-U2-01 no fija el objetivo de utilizacion"
    return int(m.group(1))


def design_secret_names() -> dict[str, str]:
    """clave de la boveda -> nombre del Secret que crea su ExternalSecret (INF-U2-01, D-5)."""
    m = re.search(r"Nombres de los Secret[^\n]*: `([\w-]+)` \(de `([\w/]+)`\), `([\w-]+)` y `([\w-]+)` \(de `([\w/]+)/<clientId>`\)", INF_U2_01)
    assert m, "INF-U2-01 no fija los nombres de los Secret"
    ca, ca_key, first, second, prefix = m.groups()
    return {ca_key: ca, f"{prefix}/{first.removesuffix('-client')}": first, f"{prefix}/{second.removesuffix('-client')}": second}


def design_internal_issuer() -> str:
    """El ClusterIssuer de kind (INF-U2-01, D-3); staging y prod nunca lo usan."""
    m = re.search(r"`ClusterIssuer` del certificado interno: `([\w-]+)` en kind", INF_U2_01)
    assert m, "INF-U2-01 no fija el issuer de kind"
    return m.group(1)


def design_ports() -> dict[str, int]:
    """Puertos de `keycloak` en platform/network/flows.yaml: 8443 (F05/F50), 7800 (F117), 9000 (F60)."""
    flows = yaml.safe_load((_ROOT / "platform" / "network" / "flows.yaml").read_text(encoding="utf-8"))["flows"]
    ports = {}
    for flow in flows:
        if "keycloak" in flow["to"] and flow["id"] in {"F05", "F117", "F60"}:
            ports[flow["id"]] = flow["port"]
    assert ports == {"F05": 8443, "F117": 7800, "F60": 9000}, ports
    return ports


# --- render y conftest --------------------------------------------------------------------------

REALM_KIND = KEYCLOAK / "realm" / "realm.kind.yaml"


def helm_command(env: str, *extra: str) -> list[str]:
    """Como `render-keycloak`: kind suma el realm de Git (`--set-file`) para el ConfigMap del Job de `keycloak-config-cli` (U02-T19)."""
    realm = ["--set-file", f"vectra.configCli.realm={REALM_KIND}"] if env == "kind" else []
    return [
        str(HELM), "template", "keycloak", str(CHART), "--namespace", NAMESPACE, "--skip-tests",
        "-f", str(VALUES / "common.yaml"), "-f", str(VALUES / f"{env}.yaml"), *realm, *extra,
    ]  # fmt: skip


def render(env: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(helm_command(env, *extra), capture_output=True, text=True, check=False)  # noqa: S603 - herramienta fija de platform/.tools


def load(env: str) -> list[dict[str, Any]]:
    text = (RENDERED / env / "keycloak.yaml").read_text(encoding="utf-8")
    return [d for d in yaml.safe_load_all(text) if d]


def statefulset(docs: list[dict[str, Any]]) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == "StatefulSet"]
    return found


def find(docs: list[dict[str, Any]], kind: str, name: str) -> dict[str, Any]:
    (found,) = [d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name]
    return found


def event_tags_problems(docs: list[dict[str, Any]], name: str, value: str) -> list[str]:
    """B10 corregido: el contenedor de Keycloak lleva `name=value` (con `clientId`) en su entorno de arranque."""
    env = container_env(docs).get(name)
    if env is None:
        return [f"falta la variable {name}"]
    if env.get("value") != value:
        return [f"{name} debe ser {value!r}: {env.get('value')!r}"]
    return []


def container_env(docs: list[dict[str, Any]]) -> dict[str, Any]:
    return {e["name"]: e for e in statefulset(docs)["spec"]["template"]["spec"]["containers"][0]["env"]}


def conftest(docs: list[dict[str, Any]]) -> tuple[int, str]:
    """Corre las dos pasadas de `make policy-keycloak` sobre `docs`. Devuelve (codigo mayor, salida)."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "keycloak.yaml"
        target.write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        first = subprocess.run([str(CONFTEST), "test", "--policy", str(POLICY), str(target)], capture_output=True, text=True, check=False)  # noqa: S603 - herramienta fija de platform/.tools
        second = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
            [str(CONFTEST), "test", "--combine", "--namespace", "keycloak_set", "--policy", str(POLICY), str(target)],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
    return max(first.returncode, second.returncode), first.stdout + first.stderr + second.stdout + second.stderr


def policy_rules() -> set[str]:
    """Los identificadores de los `# regla: x` de las politicas."""
    rules = set()
    for path in sorted(POLICY.glob("*.rego")):
        rules |= set(re.findall(r"^# regla: ([\w-]+)$", path.read_text(encoding="utf-8"), re.MULTILINE))
    return rules


KYVERNO = _ROOT / "platform" / ".tools" / "bin" / "kyverno"
U1_POLICIES = _ROOT / "platform" / "policies"
STATIC_POLICIES = (
    "disallow-latest require-run-as-non-root disallow-privileged disallow-host-path require-ro-rootfs require-resources "
    "require-priority-class require-criticality-label disallow-plain-secrets disallow-rbac-wildcards restrict-loadbalancer restrict-registries"
).split()  # las mismas que STATIC_POLICIES de platform/Makefile


def kyverno(docs: list[dict[str, Any]]) -> tuple[bool, str]:
    """Aplica las politicas estaticas de U1. Aprueba solo si alguna regla vio un recurso y ninguna fallo."""
    with tempfile.TemporaryDirectory() as tmp:
        policies = Path(tmp) / "policies"
        policies.mkdir()
        for name in STATIC_POLICIES:
            (policies / f"{name}.yaml").write_text((U1_POLICIES / "kyverno" / f"{name}.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        resources = Path(tmp) / "resources"
        resources.mkdir()
        (resources / "keycloak.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        run = subprocess.run([str(KYVERNO), "apply", str(policies), "--resource", str(resources)], capture_output=True, text=True, check=False)  # noqa: S603 - herramienta fija de platform/.tools
    output = run.stdout + run.stderr
    ok = re.search(r"pass: [1-9]\d*, fail: 0, warn: 0, error: 0", output) is not None
    return ok, output
