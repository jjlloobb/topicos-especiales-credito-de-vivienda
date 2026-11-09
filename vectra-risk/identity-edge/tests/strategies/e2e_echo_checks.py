"""Comprobaciones estaticas del backend de eco de kind (U02-T14, H1): el servidor en el proceso y los manifiestos.

Los nombres, la SA, las etiquetas y los puertos salen de `platform/network/flows.yaml` y de `gateway/routes.yaml`; nada va a mano.
"""

import http.client
import importlib.util
import json
import re
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[3]
ECHO_DIR = _ROOT / "identity-edge" / "tests" / "e2e" / "echo"
SERVER = ECHO_DIR / "server.py"
MANIFESTS = ECHO_DIR / "manifests.yaml"
DOCKERFILE = ECHO_DIR / "Dockerfile"
SCHEMAS = _ROOT / "identity-edge" / "tests" / "fixtures" / "k8s-schemas" / "v1.34.12-standalone-strict"
TOOLS = _ROOT / "platform" / ".tools" / "bin"
U1_POLICIES = _ROOT / "platform" / "policies"
FLOWS = _ROOT / "platform" / "network" / "flows.yaml"
ROUTES = _ROOT / "identity-edge" / "gateway" / "routes.yaml"
REGISTRY = "kind-registry:5000/"
# Los cuatro servicios destino que el eco reemplaza (H1) y la ruta de `routes.yaml` que llega a cada uno.
ECHOED = ("console-spa", "console-bff", "case-service", "governance-service")


# --- servidor ----------------------------------------------------------------------------------------------


def load_server(path: Path = SERVER) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_echo_{abs(hash(str(path)))}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def serving(module: ModuleType) -> Iterator[int]:
    """Levanta el eco en el proceso, en un puerto efimero."""
    httpd = module.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


# Valores con bytes que un servidor descuidado cambiaria: mayusculas, minusculas, puntuacion y no ASCII.
IDEMPOTENCY_KEY = "Req-7F3a9c2e-0B1d-4E55-9a6f-ÁÉ_~:+=/"
TEST_SCENARIO = "Escenario-RECHAZO_por_Política/1"


def roundtrip(module: ModuleType, headers: list[tuple[str, str]], body: bytes = b"", method: str = "POST") -> dict[str, Any]:
    with serving(module) as port:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.putrequest(method, "/api/intake/v1/intake/applications", skip_host=False, skip_accept_encoding=True)
            for name, value in headers:
                conn.putheader(name, value.encode("utf-8"))
            conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            reply = conn.getresponse()
            raw = reply.read()
        finally:
            conn.close()
    assert reply.status == 200, reply.status
    return json.loads(raw)


def call(port: int, method: str, path: str, headers: list[tuple[str, str]] | None = None, body: bytes = b"") -> tuple[int, dict[str, Any]]:
    """Una peticion al eco que ya esta sirviendo en `port`: el estado y el JSON de la respuesta."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.putrequest(method, path, skip_accept_encoding=True)
        for name, value in headers or []:
            conn.putheader(name, value.encode("utf-8"))
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        reply = conn.getresponse()
        return reply.status, json.loads(reply.read() or b"{}")
    finally:
        conn.close()


def echoed_value(reply: dict[str, Any], name: str) -> str | None:
    for key, value in reply["headers"]:
        if key.lower() == name.lower():
            return str(value)
    return None


def server_problems(module: ModuleType) -> list[str]:
    """El eco devuelve `Idempotency-Key` y `X-Test-Scenario` byte a byte, el tamano del cuerpo y las `x-vectra-*` que recibe."""
    found: list[str] = []
    sent = [
        ("Idempotency-Key", IDEMPOTENCY_KEY),
        ("X-Test-Scenario", TEST_SCENARIO),
        ("x-vectra-sub", "forged"),
    ]
    try:
        reply = roundtrip(module, sent, body=b"x" * 1234)
    except Exception as error:  # noqa: BLE001 - un eco roto puede fallar de cualquier forma
        return [f"el eco no respondio: {error!r}"]
    for name, value in sent:
        got = echoed_value(reply, name)
        if got is None or got.encode("utf-8") != value.encode("utf-8"):
            found.append(f"{name} no volvio byte a byte: {got!r}")
    if reply.get("body_bytes") != 1234:
        found.append(f"body_bytes = {reply.get('body_bytes')!r}, esperado 1234")
    return found


# --- manifiestos -------------------------------------------------------------------------------------------


def manifest_docs(path: Path = MANIFESTS) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def design() -> dict[str, dict[str, Any]]:
    """Por servicio: namespace, SA, nombre y puerto, de `flows.yaml` y `routes.yaml`."""
    flows = yaml.safe_load(FLOWS.read_text(encoding="utf-8"))
    routes = yaml.safe_load(ROUTES.read_text(encoding="utf-8"))
    ports = {r["backend"]["service"]: (r["backend"]["namespace"], r["backend"]["port"]) for r in routes["routes"]}
    out: dict[str, dict[str, Any]] = {}
    for service in ECHOED:
        workload = flows["workloads"][service]
        namespace, port = ports[service]
        assert workload["ns"] == namespace, service
        out[service] = {"namespace": namespace, "sa": workload["sa"], "name": workload["name"], "port": port}
    return out


def _of(docs: list[dict[str, Any]], kind: str, name: str) -> dict[str, Any] | None:
    return next((d for d in docs if d.get("kind") == kind and d["metadata"]["name"] == name), None)


def probe_problems(service: str, container: dict[str, Any], port: int) -> list[str]:
    """Sondas `exec` por el loopback del pod (F-05).

    Los cuatro servicios destino tienen un `Server` de Linkerd con rutas (`platform/network/generated/kind/`): en un `Server` con
    rutas Linkerd deja de autorizar solo las sondas del kubelet (`generate.py`, `probe_routes`) y `flows.yaml` no declara
    `_probes` para ellos, así que un `httpGet` o un `tcpSocket` del kubelet daría 403 y los pods nunca llegarían a Ready. El `exec`
    corre dentro del contenedor y llega por el loopback, que la malla no intercepta.
    """
    found: list[str] = []
    for name in ("readinessProbe", "livenessProbe"):
        probe = container.get(name)
        if probe is None:
            found.append(f"{service}: falta {name}")
        elif "exec" not in probe:
            found.append(f"{service}: {name} no es `exec`: el kubelet recibiría 403 de Linkerd")
        elif f"127.0.0.1:{port}" not in " ".join(probe["exec"].get("command", [])):
            found.append(f"{service}: {name} no consulta 127.0.0.1:{port}")
    return found


def structure_problems(docs: list[dict[str, Any]]) -> list[str]:
    """Nombres, SA, etiquetas, puerto e imagen contra el diseno."""
    found: list[str] = []
    want = design()
    kinds = sorted({d["kind"] for d in docs})
    if kinds != ["Deployment", "PodDisruptionBudget", "Service", "ServiceAccount"]:
        found.append(f"tipos inesperados: {kinds}")
    for service, spec in want.items():
        for kind in ("Deployment", "Service", "ServiceAccount", "PodDisruptionBudget"):
            doc = _of(docs, kind, spec["sa"] if kind == "ServiceAccount" else spec["name"])
            if doc is None:
                found.append(f"{service}: falta {kind}")
                continue
            if doc["metadata"].get("namespace") != spec["namespace"]:
                found.append(f"{service}: {kind} en el namespace {doc['metadata'].get('namespace')!r}, esperado {spec['namespace']}")
        dep = _of(docs, "Deployment", spec["name"])
        svc = _of(docs, "Service", spec["name"])
        if dep is not None:
            pod = dep["spec"]["template"]
            labels = pod["metadata"]["labels"]
            if labels.get("app.kubernetes.io/name") != spec["name"]:
                found.append(f"{service}: la etiqueta app.kubernetes.io/name del pod es {labels.get('app.kubernetes.io/name')!r}")
            if dep["spec"]["selector"]["matchLabels"].get("app.kubernetes.io/name") != spec["name"]:
                found.append(f"{service}: el selector del Deployment no usa app.kubernetes.io/name = {spec['name']}")
            if "vectra.io/criticality" not in labels or "vectra.io/criticality" not in dep["metadata"].get("labels", {}):
                found.append(f"{service}: falta vectra.io/criticality")
            if pod["spec"].get("serviceAccountName") != spec["sa"]:
                found.append(f"{service}: serviceAccountName {pod['spec'].get('serviceAccountName')!r}, esperado {spec['sa']}")
            containers = pod["spec"]["containers"]
            if [p["containerPort"] for c in containers for p in c.get("ports", [])] != [spec["port"]]:
                found.append(f"{service}: el puerto del contenedor no es {spec['port']}")
            for constraint in pod["spec"].get("topologySpreadConstraints", []):
                if constraint.get("labelSelector", {}).get("matchLabels", {}).get("app.kubernetes.io/name") != spec["name"]:
                    found.append(f"{service}: un topologySpreadConstraints no selecciona app.kubernetes.io/name = {spec['name']}")
            for container in containers:
                if not container["image"].startswith(REGISTRY):
                    found.append(f"{service}: imagen fuera de {REGISTRY}: {container['image']}")
                found += probe_problems(service, container, spec["port"])
            if dep["spec"].get("replicas", 1) < 2:
                found.append(f"{service}: menos de 2 replicas")
        if svc is not None:
            if svc["spec"]["selector"].get("app.kubernetes.io/name") != spec["name"]:
                found.append(f"{service}: el Service no selecciona app.kubernetes.io/name = {spec['name']}")
            if [p["port"] for p in svc["spec"]["ports"]] != [spec["port"]]:
                found.append(f"{service}: el puerto del Service no es {spec['port']}")
            if dep is not None:
                container_ports = [p for c in dep["spec"]["template"]["spec"]["containers"] for p in c.get("ports", [])]
                reachable = {p.get("name") for p in container_ports} | {p["containerPort"] for p in container_ports}
                for port in svc["spec"]["ports"]:
                    if port.get("targetPort", port["port"]) not in reachable:
                        found.append(f"{service}: el targetPort {port.get('targetPort')!r} del Service no existe en el contenedor")
        pdb = _of(docs, "PodDisruptionBudget", spec["name"])
        if pdb is not None and pdb["spec"]["selector"].get("matchLabels", {}).get("app.kubernetes.io/name") != spec["name"]:
            found.append(f"{service}: el PodDisruptionBudget no selecciona app.kubernetes.io/name = {spec['name']}")
    names = sorted(d["metadata"]["name"] for d in docs if d["kind"] == "Deployment")
    if names != sorted(s["name"] for s in want.values()):
        found.append(f"Deployments {names}, esperados {sorted(s['name'] for s in want.values())}")
    return found


def kubeconform(docs: list[dict[str, Any]]) -> tuple[bool, str]:
    """`kubeconform -strict` sin `-ignore-missing-schemas`, con los esquemas del directorio versionado (sin red)."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "echo.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        run = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
            [
                str(TOOLS / "kubeconform"), "-strict", "-summary",
                "-schema-location", str(SCHEMAS) + "/{{ .ResourceKind }}{{ .KindSuffix }}.json",
                tmp,
            ],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
    output = run.stdout + run.stderr
    return run.returncode == 0 and re.search(r"Valid: [1-9]\d*, Invalid: 0, Errors: 0, Skipped: 0", output) is not None, output


def conftest(docs: list[dict[str, Any]]) -> tuple[bool, str]:
    """Las reglas Rego de U1: por documento y, con `--combine`, las del render entero (`hpa`)."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "echo.yaml").write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding="utf-8")
        outputs = []
        codes = []
        for extra in ([], ["--combine", "--namespace", "hpa"]):
            run = subprocess.run(  # noqa: S603 - herramienta fija de platform/.tools
                [str(TOOLS / "conftest"), "test", *extra, "--policy", str(U1_POLICIES / "rego"), str(Path(tmp) / "echo.yaml")],
                capture_output=True, text=True, check=False,
            )  # fmt: skip
            codes.append(run.returncode)
            outputs.append(run.stdout + run.stderr)
    return all(c == 0 for c in codes), "\n".join(outputs)


def dockerfile_problems(text: str) -> list[str]:
    found: list[str] = []
    if not re.search(r"^FROM \S+@sha256:[0-9a-f]{64}\s*$", text, re.M):
        found.append("la imagen base no va por digest")
    if not re.search(r"^USER \d+", text, re.M):
        found.append("falta USER numerico")
    if "server.py" not in text:
        found.append("no copia server.py")
    return found
