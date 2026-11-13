"""Pasos 17 y 18 (CA-4; INF-U10-02; NFR-U10-44; NFR-U10-45): los dos contenedores reales arrancan con lo que **pone el chart** (U04-T06, F-01; U11-T03, CA-4).

Un chart que renderiza bien no prueba que el contenedor arranque. NFR-U10-45: sin root, con el sistema de archivos de solo lectura, con las cabeceras de cache del diseno y sin cabeceras de seguridad (las pone el gateway de U2). La orden, las variables, los montajes, el usuario y los `emptyDir` salen del render de kind
(`helm template` con lo que usa Argo CD). Cada contenedor corre con `docker run --read-only` y el `--user` del chart; los puertos se publican en un puerto libre del host
(nunca el 8080 ni el 8081).

* `console-bff`: solo cambian los hosts de las cinco URL (a un puerto cerrado: los cinco destinos estan caidos) y del JWKS (a un servidor local con TLS que sirve el JWKS de
  `contracts/tests/strategies/auth.py`), y el archivo de la CA, por el certificado de ese servidor **en la misma ruta** que monta el chart. El emisor es el **del chart**: los tokens
  de prueba llevan ese `iss`, asi que un `VECTRA_OIDC_ISSUER` distinto del `authority` de la SPA da 401.
* `console-spa`: el `config.json` es el del `ConfigMap` rendido, montado de solo lectura en el `mountPath` del chart; un `--tmpfs` por cada `emptyDir`, en su ruta; ningun otro volumen.

Sin Docker la prueba **falla**; no se salta. Corre con `make -C console image-bff image-spa` hecho antes (el target `check` lo hace). `VECTRA_IMAGE_TEST_SET` agrega `--set` al
`helm template` (solo para reproducir el rojo de una mutacion del chart). Cada `docker run`, la salida y la memoria en reposo se imprimen (`pytest -s`).
"""

import datetime
import json
import os
import re
import shlex
import socket
import ssl
import subprocess
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from strategies import auth as u0

ROOT = Path(__file__).resolve().parents[4]
BIN = ROOT / "platform" / ".tools" / "bin"
WORK = ROOT / "platform" / ".tools" / "tmp"
STATS = ROOT / "platform" / ".tools" / "integration" / "u10" / "image-stats.txt"
IMAGE_BFF = "localhost:5001/vectra/console-bff:dev"
IMAGE_SPA = "localhost:5001/vectra/console-spa:dev"
HOST_ALIAS = "host.docker.internal"
Doc = dict[str, Any]


def docker(*args: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    if args[0] in {"run", "stop"}:
        print("$ docker", shlex.join(args))
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603, S607
    except FileNotFoundError:
        pytest.fail("Docker no esta disponible: la prueba de la imagen falla, no se salta (CA-4)")


def render(name: str) -> list[Doc]:
    """Lo que Argo CD renderiza para kind: los values del entorno, `kind_values` y `values/kind/<nombre>.yaml`."""
    chart = ROOT / "console" / "chart" / name.removeprefix("console-")
    command = [
        str(BIN / "helm"),
        "template",
        name,
        str(chart),
        "-f",
        str(ROOT / "vectra-risk-gitops/envs/kind/values.yaml"),
    ]
    if name == "console-bff":
        command += ["-f", str(chart / "values-kind.yaml")]
    command += ["-f", str(ROOT / f"vectra-risk-gitops/values/kind/{name}.yaml")]
    command += shlex.split(os.environ.get("VECTRA_IMAGE_TEST_SET", ""))
    out = subprocess.run(command, check=True, capture_output=True, text=True).stdout  # noqa: S603
    return [d for d in yaml.safe_load_all(out) if d]


def of_kind(docs: list[Doc], kind: str, name: str | None = None) -> Doc:
    return next(d for d in docs if d["kind"] == kind and (name is None or d["metadata"]["name"] == name))


def pod_of(docs: list[Doc]) -> Doc:
    return of_kind(docs, "Deployment")["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def workdir() -> Path:
    """Un directorio dentro del worktree (Docker monta lo que esta bajo `/home`; `/tmp` es un tmpfs casi lleno) y legible por el usuario del contenedor."""
    WORK.mkdir(parents=True, exist_ok=True)
    folder = WORK / f"u10-t05-{uuid.uuid4().hex[:8]}"
    folder.mkdir()
    folder.chmod(0o755)
    return folder


@pytest.fixture(scope="module", autouse=True)
def images_are_built() -> None:
    for image, target in ((IMAGE_BFF, "image-bff"), (IMAGE_SPA, "image-spa")):
        probe = docker("image", "inspect", image, "--format", "{{.Id}}")
        assert probe.returncode == 0, (
            f"falta la imagen {image}: corre `make -C console {target}`\n{probe.stderr}"
        )


class Container:
    """Un `docker run -d --read-only --user <el del chart>`; `stop` y `remove` lo borran siempre."""

    def __init__(
        self, image: str, *args: str, container_port: int, extra_ports: tuple[int, ...] = ()
    ) -> None:
        self.name = f"u10-t05-{uuid.uuid4().hex[:8]}"
        self.container_port = container_port
        ports = [f"127.0.0.1::{p}" for p in (container_port, *extra_ports)]
        command = [
            "run",
            "-d",
            "--name",
            self.name,
            "--read-only",
            *[a for p in ports for a in ("-p", p)],
            *args,
            image,
        ]
        started = docker(*command)
        assert started.returncode == 0, started.stderr
        self.ports: dict[int, int] = {}

    def host_port(self, port: int) -> int:
        if port not in self.ports:
            answer = docker("port", self.name, f"{port}/tcp").stdout.strip().splitlines()[0]
            self.ports[port] = int(answer.rsplit(":", 1)[1])
        return self.ports[port]

    def get(self, port: int, path: str, **kwargs: Any) -> httpx.Response | None:
        try:
            return httpx.get(f"http://127.0.0.1:{self.host_port(port)}{path}", timeout=5, **kwargs)
        except (httpx.TransportError, IndexError):
            return None

    def state(self) -> dict[str, Any]:
        return json.loads(docker("inspect", self.name).stdout)[0]["State"]  # type: ignore[no-any-return]

    def logs(self) -> str:
        out = docker("logs", self.name)
        return out.stdout + out.stderr

    def wait_for(
        self, port: int, path: str, status: int | None = 200, seconds: float = 60.0, **kwargs: Any
    ) -> httpx.Response:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            assert self.state()["Running"], (
                f"el contenedor termino al arrancar: {self.state()}\n{self.logs()}"
            )
            answer = self.get(port, path, **kwargs)
            if answer is not None and (status is None or answer.status_code == status):
                return answer
            time.sleep(0.1)
        raise AssertionError(f"{path} no respondio {status} en {seconds} s\n{self.logs()}")

    def wait_for_exit(self, seconds: float = 60.0) -> int:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            state = self.state()
            if not state["Running"]:
                return int(state["ExitCode"])
            time.sleep(0.1)
        raise AssertionError(f"el contenedor no salio en {seconds} s\n{self.logs()}")

    def stop(self, grace: int) -> tuple[int, float]:
        """`docker stop -t <grace>`: el codigo de salida y los segundos que tardo (137 es que Docker tuvo que matarlo)."""
        started = time.monotonic()
        docker("stop", "-t", str(grace), self.name, timeout=grace + 30)
        seconds = time.monotonic() - started
        return int(self.state()["ExitCode"]), seconds

    def memory(self) -> str:
        out = docker(
            "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}} {{.CPUPerc}}", self.name
        ).stdout.strip()
        print("memoria en reposo:", out)
        STATS.parent.mkdir(parents=True, exist_ok=True)
        with STATS.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {out}\n")
        return out

    def remove(self) -> None:
        docker("rm", "-f", self.name)


@contextmanager
def running(
    image: str, *args: str, container_port: int, extra_ports: tuple[int, ...] = ()
) -> Iterator[Container]:
    container = Container(image, *args, container_port=container_port, extra_ports=extra_ports)
    try:
        yield container
    finally:
        container.remove()


# --- console-bff -----------------------------------------------------------------------------------------------------------------------


class JwksServer:
    """El JWKS de `contracts/tests/strategies/auth.py` por HTTPS, con un certificado autofirmado que sirve de CA (el que monta el contenedor en la ruta del chart)."""

    def __init__(self, folder: Path) -> None:
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST_ALIAS)])
        now = datetime.datetime.now(datetime.UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST_ALIAS)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )
        self.ca_dir = folder / "ca"
        self.ca_dir.mkdir()
        self.ca_dir.chmod(0o755)
        (self.ca_dir / "ca.crt").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        (self.ca_dir / "ca.crt").chmod(0o444)
        key_file = folder / "server.key"
        key_file.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        body = json.dumps(u0.jwks_document()).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                return

        self.server = HTTPServer(("0.0.0.0", 0), Handler)  # noqa: S104 - el contenedor llega por la interfaz del puente
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.ca_dir / "ca.crt", key_file)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def bff_chart_env(jwks: JwksServer, drop: tuple[str, ...] = ()) -> tuple[dict[str, str], Doc]:
    """Las variables del `ConfigMap` rendido para kind: solo cambian los hosts de las cinco URL y del JWKS. El emisor y el archivo de la CA son los del chart."""
    docs = render("console-bff")
    env = dict(of_kind(docs, "ConfigMap", "console-bff-config")["data"])
    dead = free_port()
    for name, value in env.items():
        if name.endswith("_URL") and name != "VECTRA_JWKS_URL":
            env[name] = re.sub(r"//[^/:]+:\d+", f"//{HOST_ALIAS}:{dead}", value)
    # https se queda: el servidor local tiene TLS y el contenedor verifica contra la CA de prueba
    env["VECTRA_JWKS_URL"] = re.sub(r"//[^/:]+(:\d+)?", f"//{HOST_ALIAS}:{jwks.port}", env["VECTRA_JWKS_URL"])
    env.pop("VECTRA_OTLP_ENDPOINT")  # F61: el colector no existe aqui; sin el, U0 no exporta
    return {k: v for k, v in env.items() if k not in drop}, pod_of(docs)


def bff_args(env: dict[str, str], pod: Doc, jwks: JwksServer) -> list[str]:
    container = pod["containers"][0]
    user = pod["securityContext"]["runAsUser"]
    (mount,) = [m for m in container["volumeMounts"] if m["readOnly"]]
    args = [
        "--user",
        f"{user}:{pod['securityContext']['runAsGroup']}",
        "--add-host",
        f"{HOST_ALIAS}:host-gateway",
    ]
    args += ["-v", f"{jwks.ca_dir}:{mount['mountPath']}:ro"]
    for name, value in env.items():
        args += ["-e", f"{name}={value}"]
    assert container["command"] == ["python", "-m", "console_bff.app"]
    return args


@pytest.fixture
def jwks() -> Iterator[JwksServer]:
    server = JwksServer(workdir())
    try:
        yield server
    finally:
        server.stop()


def test_the_bff_starts_with_what_the_chart_puts_and_serves_probes_with_every_destination_down(
    jwks: JwksServer,
) -> None:
    env, pod = bff_chart_env(jwks)
    issuer = env["VECTRA_OIDC_ISSUER"]
    with running(IMAGE_BFF, *bff_args(env, pod, jwks), container_port=8080, extra_ports=(8081,)) as c:
        health = c.wait_for(8081, "/healthz")
        assert health.status_code == 200
        assert (
            c.wait_for(8081, "/readyz").status_code == 200
        )  # los cinco destinos caidos: el circuito de cada uno es suyo
        metrics = c.wait_for(8081, "/metrics").text
        zeros = re.findall(
            r'^vectra_console_client_errors_total\{error_code="(\w+)"\} 0\.0$', metrics, flags=re.MULTILINE
        )
        assert len(zeros) == 6, metrics[:1500]
        # el 8080: 401 sin token; 200 con un token del emisor **del chart** (emisor, JWKS y audiencia juntos)
        assert c.wait_for(8080, "/api/console/me", status=401).json()["code"] == "unauthenticated"
        token = u0.bearer(
            iss=issuer, aud="console-bff", azp="vectra-console", roles=["analista"], sub="analista-1"
        )
        me = c.wait_for(8080, "/api/console/me", status=None, headers=token)
        assert me.status_code == 200, (me.status_code, me.text, c.logs())
        # un token de otro emisor (el de keycloak-admin de los otros charts) da 401: el `iss` del token ata el chart al realm
        other = u0.bearer(
            iss="https://keycloak-admin.vectra-identity.svc.cluster.local:8443/auth/realms/vectra",
            aud="console-bff",
            azp="vectra-console",
            roles=["analista"],
        )
        assert c.get(8080, "/api/console/me", headers=other).status_code == 401  # type: ignore[union-attr]
        assert c.state()["Running"]
        user = docker("exec", c.name, "id", "-u").stdout.strip()
        assert user == "65532"
        c.memory()
        code, seconds = c.stop(grace=20)
        print(f"docker stop -t 20 del BFF: codigo {code} en {seconds:.1f} s")
        assert code == 0, f"codigo {code} (137 es que Docker lo mato)\n{c.logs()}"
        assert seconds < 20


def test_the_bff_accepts_the_token_whose_iss_is_the_authority_of_the_spa_config(jwks: JwksServer) -> None:
    """P-4: el `iss` de los tokens del navegador es el `authority` del `config.json` de la SPA; con otro `VECTRA_OIDC_ISSUER` toda la API da 401."""
    env, pod = bff_chart_env(jwks)
    _, config_text, _ = spa_chart()
    authority = json.loads(config_text)["oidc"]["authority"]
    with running(IMAGE_BFF, *bff_args(env, pod, jwks), container_port=8080, extra_ports=(8081,)) as c:
        c.wait_for(8081, "/readyz")
        token = u0.bearer(
            iss=authority, aud="console-bff", azp="vectra-console", roles=["analista"], sub="analista-1"
        )
        answer = c.wait_for(8080, "/api/console/me", status=None, headers=token)
        assert answer.status_code == 200, (answer.status_code, env["VECTRA_OIDC_ISSUER"], authority)


def test_the_bff_without_the_bias_url_ends_with_2_before_listening(jwks: JwksServer) -> None:
    env, pod = bff_chart_env(jwks, drop=("VECTRA_BIAS_URL",))
    with running(IMAGE_BFF, *bff_args(env, pod, jwks), container_port=8080, extra_ports=(8081,)) as c:
        assert c.wait_for_exit() == 2
        assert "VECTRA_BIAS_URL" in c.logs()
        assert c.get(8081, "/healthz") is None  # nunca escucho


def test_the_bff_with_an_https_jwks_and_no_ca_bundle_ends_with_2(jwks: JwksServer) -> None:
    env, pod = bff_chart_env(jwks, drop=("VECTRA_CA_BUNDLE",))
    assert env["VECTRA_JWKS_URL"].startswith("https://")
    with running(IMAGE_BFF, *bff_args(env, pod, jwks), container_port=8080, extra_ports=(8081,)) as c:
        assert c.wait_for_exit() == 2
        assert "VECTRA_CA_BUNDLE" in c.logs()


# --- console-spa -----------------------------------------------------------------------------------------------------------------------


def spa_chart() -> tuple[Doc, str, Doc]:
    docs = render("console-spa")
    config = of_kind(docs, "ConfigMap", "console-spa-config")["data"]["config.json"]
    return pod_of(docs), config, of_kind(docs, "Deployment")


def spa_args(pod: Doc, config_text: str, folder: Path, *, with_tmp: bool = True) -> list[str]:
    container = pod["containers"][0]
    mounts = {m["name"]: m for m in container["volumeMounts"]}
    volumes = {v["name"]: v for v in pod["volumes"]}
    config_dir = folder / "config"
    config_dir.mkdir()
    config_dir.chmod(0o755)
    (config_dir / "config.json").write_text(config_text, encoding="utf-8")
    (config_dir / "config.json").chmod(0o444)
    args = ["--user", f"{pod['securityContext']['runAsUser']}:{pod['securityContext']['runAsGroup']}"]
    for name, mount in mounts.items():
        if "configMap" in volumes[name]:
            args += ["-v", f"{config_dir}:{mount['mountPath']}:ro"]
        elif "emptyDir" in volumes[name]:
            if with_tmp or mount["mountPath"] != "/tmp":
                args += ["--tmpfs", f"{mount['mountPath']}:rw,mode=1777"]
        else:
            pytest.fail(f"un volumen del chart que la prueba no sabe montar: {name}")
    return args


SECURITY_HEADERS = (
    "content-security-policy",
    "x-frame-options",
    "strict-transport-security",
    "referrer-policy",
    "cross-origin-opener-policy",
    "x-content-type-options",
)


def routes_security_headers() -> set[str]:
    """Los nombres de los perfiles `common` y `spa` de `routes.yaml`: los que pone el gateway de U2 y nginx no debe poner."""
    profiles = yaml.safe_load((ROOT / "identity-edge/gateway/routes.yaml").read_text(encoding="utf-8"))[
        "profiles"
    ]
    return {h.lower() for p in ("common", "spa") for h in profiles[p]["set"]}


def test_the_security_headers_the_test_looks_for_are_the_ones_of_the_gateway_profiles() -> None:
    assert routes_security_headers() == set(SECURITY_HEADERS)
    nginx = (ROOT / "console" / "spa" / "nginx.conf").read_text(encoding="utf-8").lower()
    assert not [h for h in routes_security_headers() if h in nginx]


def test_the_spa_serves_the_build_and_the_chart_config_with_the_cache_headers_of_the_design() -> None:
    pod, config_text, _ = spa_chart()
    folder = workdir()
    with running(IMAGE_SPA, *spa_args(pod, config_text, folder), container_port=8080) as c:
        assert c.wait_for(8080, "/healthz").text.strip() == "ok"
        index = c.wait_for(8080, "/")
        body = index.text
        assert index.headers["cache-control"] == "no-store" and '<div id="root">' in body
        assert c.get(8080, "/index.html").text == body  # type: ignore[union-attr]
        assert c.get(8080, "/index.html").headers["cache-control"] == "no-store"  # type: ignore[union-attr]
        # `config.json`: byte a byte el del chart, sin cache
        config = c.get(8080, "/config.json")
        assert config is not None and config.status_code == 200 and config.content == config_text.encode()
        assert config.headers["cache-control"] == "no-store"
        # el fallback: las rutas sin extension dan el mismo `index.html`, sin cache
        for path in (
            "/cases/123",
            "/casos/0b9f1c1e-2c1a-4f6c-9a62-5b7f4b2f6a10",
            "/callback",
            "/stepup-callback",
        ):
            answer = c.get(8080, path)
            assert answer is not None and answer.status_code == 200 and answer.text == body, path
            assert answer.headers["cache-control"] == "no-store", path
        # `assets/`: inmutables y con gzip
        match = re.search(r'src="(/assets/[^"]+\.js)"', body)
        assert match, body
        asset = c.get(8080, match.group(1), headers={"accept-encoding": "gzip"})
        assert asset is not None and asset.status_code == 200
        assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert asset.headers["content-encoding"] == "gzip"
        # lo que no existe es 404, nunca HTML con 200
        missing = c.get(8080, "/assets/no-existe.js")
        assert missing is not None and missing.status_code == 404 and "<div" not in missing.text
        for path in ("/.vite/manifest.json", "/version.json", "/no-existe.css"):
            answer = c.get(8080, path)
            assert answer is not None and answer.status_code == 404 and "<div id" not in answer.text, path
        # ninguna cabecera de seguridad (las pone el gateway de U2) y `Server` sin version
        for path in ("/", "/config.json", match.group(1), "/callback", "/assets/no-existe.js"):
            answer = c.get(8080, path)
            assert answer is not None
            present = {h.lower() for h in answer.headers} & set(SECURITY_HEADERS)
            assert not present, (path, present)
            assert not re.search(r"\d", answer.headers.get("server", "")), answer.headers.get("server")
        user = docker("exec", c.name, "id", "-u").stdout.strip()
        assert user == str(pod["securityContext"]["runAsUser"]) and user != "0"
        c.memory()
        code, seconds = c.stop(grace=20)
        print(f"docker stop del nginx: codigo {code} en {seconds:.1f} s")
        assert code != 137, c.logs()


def test_the_spa_does_not_start_without_the_tmp_empty_dir_of_the_chart() -> None:
    pod, config_text, _ = spa_chart()
    assert any(m["mountPath"] == "/tmp" for m in pod["containers"][0]["volumeMounts"])
    with running(IMAGE_SPA, *spa_args(pod, config_text, workdir(), with_tmp=False), container_port=8080) as c:
        code = c.wait_for_exit(30)
        assert code != 0, "nginx arranco sin /tmp escribible: el emptyDir del chart no haria falta"
        assert "/tmp" in c.logs() or "Permission denied" in c.logs() or "Read-only" in c.logs(), c.logs()


def test_the_spa_chart_mounts_config_json_where_nginx_reads_it_and_not_on_the_root() -> None:
    pod, _, _ = spa_chart()
    mounts = {m["name"]: m for m in pod["containers"][0]["volumeMounts"]}
    assert not mounts["config"]["mountPath"].startswith("/usr/share/nginx/html")
    assert "subPath" not in mounts["config"]
