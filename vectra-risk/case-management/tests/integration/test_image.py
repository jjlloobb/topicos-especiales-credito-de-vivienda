"""Pasos 19 y 20 (CA-4): los cuatro contenedores reales arrancan con lo que pone el chart (leccion de U04-T06 y U04-T08).

La orden, los argumentos y las variables de cada contenedor salen del render de kind (`helm template` con los values de Argo CD). Solo cambian: los hosts de las URL y del
DSN (por los de un PostgreSQL de Testcontainers y los dobles HTTP de esta prueba, a traves de `host.docker.internal`), el `sslmode` (el PostgreSQL local no tiene TLS:
`disable` en vez de `verify-full`), el `issuer` de los tokens de prueba, la llave (una de prueba en la MISMA ruta) y `PGUSER` y `PGPASSWORD` (los roles locales). Cada contenedor
corre con `--read-only --user 65532:65532 --cap-drop ALL`. Ningun contenedor usa el 8080 ni el 8081 **del host**: publican puertos libres. **Sin Docker la prueba falla; no se salta.**
Se corre con `make -C case-management image image-mock` hecho antes (el objetivo `check` lo hace, y construye ANTES de esta prueba: no puede pasar con una imagen vieja).
"""

import json
import re
import shlex
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import jwt
import mock_auth
import pytest
from case_pg import Db
from chart_render import Doc, render
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CASE_IMAGE = "localhost:5001/vectra/case-management:dev"
MOCK_IMAGE = "localhost:5001/vectra/core-banking-mock:dev"
HOST = "host.docker.internal"
RUN_ID = "20261112-0900"
CREDIT_ID = "11111111-1111-4111-8111-111111111111"  # el primero del fixture de la imagen del mock
ROLE_PASSWORD = {"case_app": "case_app", "case_worker": "case_worker", "case_migrator": "migrator-pass"}
TIMINGS: dict[str, float] = {}


def docker(
    *args: str, timeout: float = 180, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    if args[0] in {
        "run",
        "stop",
        "exec",
    }:  # con `pytest -s` queda el `docker run` exacto en la salida (bitacora de U08-T05)
        print("$ docker", shlex.join(args))  # noqa: T201
    try:
        return subprocess.run(  # noqa: S603, S607 - docker local, sin entrada externa
            ["docker", *args], capture_output=True, text=True, timeout=timeout, check=False, input=input_text
        )
    except FileNotFoundError:
        pytest.fail("Docker no esta disponible: la prueba de las imagenes falla, no se salta (CA-4)")


@pytest.fixture(scope="module", autouse=True)
def images() -> None:
    for image in (CASE_IMAGE, MOCK_IMAGE):
        probe = docker("image", "inspect", image, "--format", "{{.Id}}")
        assert probe.returncode == 0, (
            f"falta la imagen {image}: corre `make -C case-management image image-mock`\n{probe.stderr}"
        )


@pytest.mark.parametrize("image", [CASE_IMAGE, MOCK_IMAGE])
def test_nfr_u8_34_no_circuit_breaking_library_nor_development_tools_in_the_images(image: str) -> None:
    """NFR-U8-34 (P-5 = a): sin SBOM (T1), la comprobacion es `pip list` dentro de la imagen; el breaker es el de `vectra_common.deps`."""
    listed = docker("run", "--rm", "--entrypoint", "pip", image, "list", "--format", "freeze")
    assert listed.returncode == 0 and "vectra-common" in listed.stdout.lower().replace("_", "-"), (
        listed.stderr
    )
    banned = re.compile(
        r"^(pybreaker|circuitbreaker|aiobreaker|purgatory[a-z-]*|pytest|hypothesis|ruff|mypy|hatchling)==",
        re.IGNORECASE | re.MULTILINE,
    )
    assert not banned.search(listed.stdout), banned.findall(listed.stdout)


# --- dobles HTTP (sockets reales, accesibles desde los contenedores) --------------------------------------------------------------------------


class Double:
    """Un servidor HTTP en un puerto libre de todas las interfaces; `handle(method, path, body) -> (status, headers, body)`."""

    def __init__(self, handle: Callable[[str, str, bytes], tuple[int, dict[str, str], bytes]]) -> None:
        outer = self
        self.requests: list[tuple[str, str]] = []

        class Handler(BaseHTTPRequestHandler):
            def _respond(self) -> None:
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.requests.append((self.command, self.path))
                status, headers, payload = handle(self.command, self.path, body)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_PUT = _respond  # noqa: N815

            def log_message(self, *_: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)  # noqa: S104 - el contenedor llega por host.docker.internal
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> "Double":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}"


#: La `aud` que Keycloak acepta en la aserción: su emisor (U00-T04). El render local trae el emisor de produccion; el doble acepta el de prueba.
ASSERTION_AUDIENCE = "https://vectra.localtest.me/auth/realms/vectra"


def keycloak_handle(method: str, path: str, body: bytes) -> tuple[int, dict[str, str], bytes]:
    """`/jwks` con la llave de prueba y `/token` con un token de servicio: lo que un contenedor necesita de Keycloak para arrancar y servir.
    Como Keycloak, `/token` responde 400 `invalid_client` si la `aud` de la aserción no es el emisor configurado."""
    if path == "/jwks":
        return 200, {"content-type": "application/json"}, json.dumps(mock_auth.jwks_document()).encode()
    if path == "/token" and method == "POST":
        assertion = parse_qs(body.decode()).get("client_assertion", [""])[0]
        if jwt.decode(assertion, options={"verify_signature": False}).get("aud") != ASSERTION_AUDIENCE:
            return 400, {"content-type": "application/json"}, json.dumps({"error": "invalid_client"}).encode()
        token = mock_auth.bearer("core:read-credit")["authorization"].removeprefix("Bearer ")
        return (
            200,
            {"content-type": "application/json"},
            json.dumps({"access_token": token, "token_type": "Bearer", "expires_in": 300}).encode(),
        )
    return 404, {}, b""


@pytest.fixture
def keycloak() -> Iterator[Double]:
    double = Double(keycloak_handle).start()
    yield double
    double.stop()


def proxy_403(method: str, path: str, _: bytes) -> tuple[int, dict[str, str], bytes]:
    """El 403 del proxy de Linkerd: sin cuerpo de `Problem` y con la cabecera `l5d-proxy-error`."""
    if method == "POST" and path.endswith("/status"):
        return 403, {"l5d-proxy-error": "unauthorized request on route"}, b""
    return 404, {}, b""


# --- archivos de prueba en las rutas del chart -------------------------------------------------------------------------------------------


def private_key_pem() -> str:
    return mock_auth.KEY.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def ca_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vectra-test-ca")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


# --- el render de kind ---------------------------------------------------------------------------------------------------------------------


def workload(docs: list[Doc], kind: str, name: str) -> Doc:
    return next(d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name)


def container_of(docs: list[Doc], kind: str, name: str) -> Doc:
    return workload(docs, kind, name)["spec"]["template"]["spec"]["containers"][0]  # type: ignore[no-any-return]


def pod_of(docs: list[Doc], kind: str, name: str) -> Doc:
    return workload(docs, kind, name)["spec"]["template"]["spec"]  # type: ignore[no-any-return]


def chart_env(c: Doc) -> dict[str, str]:
    return {e["name"]: e["value"] for e in c["env"] if "value" in e}


class Run:
    """Los argumentos de `docker run` de un contenedor del chart: orden, variables y montajes de solo lectura, con lo minimo cambiado (ver el docstring del modulo)."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.notes: list[str] = []

    def args(
        self,
        c: Doc,
        pod: Doc,
        *,
        overrides: dict[str, str],
        role: str | None = None,
        drop: tuple[str, ...] = (),
        publish: bool = True,
        image: str = CASE_IMAGE,
        mount_key: bool = True,
        bind: str = "127.0.0.1",
    ) -> list[str]:
        env = chart_env(c)
        env.update({k: v for k, v in overrides.items() if k in env})
        if (
            "VECTRA_ASSERTION_AUDIENCE" in env
        ):  # el render local trae el emisor de produccion; el doble de Keycloak acepta el de prueba
            env["VECTRA_ASSERTION_AUDIENCE"] = ASSERTION_AUDIENCE
        if role:
            env["PGUSER"], env["PGPASSWORD"] = role, ROLE_PASSWORD[role]
        args = [
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65532:65532",
            "--add-host",
            f"{HOST}:host-gateway",
        ]
        if publish:  # puertos libres del host (nunca el 8080 ni el 8081)
            args += ["-p", f"{bind}::8080", "-p", f"{bind}::8081"]
        mounts = {m["name"]: m for m in c.get("volumeMounts", [])}
        if "service-identity" in mounts:
            key = self.tmp / f"{uuid.uuid4().hex}.pem"
            key.write_text(private_key_pem(), encoding="utf-8")
            key.chmod(0o444)  # el Secret del chart se monta 0444: el contenedor corre como 65532
            assert env["VECTRA_CLIENT_KEY_PATH"] == f"{mounts['service-identity']['mountPath']}/private-key"
            assert mounts["service-identity"]["readOnly"] is True
            if mount_key:
                args += ["-v", f"{key}:{env['VECTRA_CLIENT_KEY_PATH']}:ro"]
        if "internal-ca" in mounts:
            ca = self.tmp / f"{uuid.uuid4().hex}-ca.crt"
            ca.write_text(ca_pem(), encoding="utf-8")
            ca.chmod(0o444)
            args += [
                "-v",
                f"{ca}:{env['VECTRA_CA_BUNDLE'] if 'VECTRA_CA_BUNDLE' in env else mounts['internal-ca']['mountPath'] + '/ca.crt'}:ro",
            ]
        for name, value in env.items():
            if name not in drop:
                args += ["-e", f"{name}={value}"]
        return [*args, image, *c["command"], *c.get("args", [])]


def pg_dsn(pg_port: int, database: str) -> str:
    """El DSN del chart con el host de PostgreSQL local y `sslmode=disable`: lo unico que cambia (el PostgreSQL de Testcontainers no tiene TLS)."""
    return f"postgresql://{HOST}:{pg_port}/{database}?sslmode=disable"


@contextmanager
def running(args: list[str], prefix: str) -> Iterator[str]:
    name = f"{prefix}-{uuid.uuid4().hex[:8]}"
    started = docker("run", "-d", "--name", name, *args)
    assert started.returncode == 0, started.stderr
    try:
        yield name
    finally:
        docker("rm", "-f", name)


def host_port(name: str, container_port: int) -> int:
    out = docker("port", name, f"{container_port}/tcp").stdout.strip().splitlines()[0]
    return int(out.rsplit(":", 1)[1])


def wait_ok(url: str, name: str, seconds: float = 40.0) -> httpx.Response:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return response
        except httpx.HTTPError:
            pass
        if docker("inspect", name, "--format", "{{.State.Running}}").stdout.strip() != "true":
            break
        time.sleep(0.3)
    logs = docker("logs", name)
    raise AssertionError(f"{url} no respondio 200\n{logs.stdout}{logs.stderr}")


def stop_and_time(name: str, grace: int) -> tuple[float, str]:
    start = time.monotonic()
    stopped = docker("stop", "-t", str(grace), name, timeout=grace + 30)
    elapsed = time.monotonic() - start
    assert stopped.returncode == 0, stopped.stderr
    return elapsed, docker("inspect", name, "--format", "{{.State.ExitCode}}").stdout.strip()


def memory_at_rest(name: str) -> str:
    return docker("stats", "--no-stream", "--format", "{{.MemUsage}}", name).stdout.strip()


def uptime() -> str:
    return Path("/proc/loadavg").read_text(encoding="utf-8").strip()


@pytest.fixture(scope="module")
def kind_docs() -> list[Doc]:
    return render("kind")


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path)


# --- 1. la migracion -------------------------------------------------------------------------------------------------------------------------


def migration_args(
    run: Run, docs: list[Doc], pg_port: int, database: str, *, drop: tuple[str, ...] = ()
) -> list[str]:
    c = container_of(docs, "Job", "case-migration")
    return run.args(
        c,
        pod_of(docs, "Job", "case-migration"),
        overrides={"CASE_DATABASE_URL": pg_dsn(pg_port, database)},
        role="case_migrator",
        drop=drop,
        publish=False,
    )


def test_1_the_migration_job_command_migrates_is_idempotent_and_writes_the_retention_terms_from_the_values(
    pg: Any, empty_db: Db, kind_docs: list[Doc], run: Run
) -> None:
    port = int(pg.get_exposed_port(5432))
    args = migration_args(run, kind_docs, port, empty_db.name)
    expected = {
        c: int(chart_env(container_of(kind_docs, "Job", "case-migration"))[v])
        for c, v in {
            "decided_years": "RETENTION_DECIDED_YEARS",
            "undecided_years": "RETENTION_UNDECIDED_YEARS",
            "intake_keys_days": "RETENTION_INTAKE_KEYS_DAYS",
        }.items()
    }
    first = docker("run", "--rm", *args)
    assert first.returncode == 0, first.stdout + first.stderr
    tables = {
        r[0]
        for r in empty_db.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }
    assert {"cases", "evaluation_jobs", "evidence_outbox", "intake_keys", "retention_settings"} <= tables
    row = empty_db.query(
        "SELECT decided_years, undecided_years, intake_keys_days, created_at FROM retention_settings WHERE id = 1"
    )[0]
    assert (
        dict(zip(("decided_years", "undecided_years", "intake_keys_days"), row[:3], strict=True)) == expected
    )
    second = docker("run", "--rm", *args)
    assert second.returncode == 0, second.stdout + second.stderr
    assert (
        empty_db.query("SELECT created_at FROM retention_settings WHERE id = 1")[0][0] == row[3]
    )  # una segunda corrida no cambia `created_at`


def test_1_without_a_retention_term_the_migration_fails_before_touching_the_database(
    pg: Any, empty_db: Db, kind_docs: list[Doc], run: Run
) -> None:
    args = migration_args(
        run, kind_docs, int(pg.get_exposed_port(5432)), empty_db.name, drop=("RETENTION_UNDECIDED_YEARS",)
    )
    result = docker("run", "--rm", *args)
    assert result.returncode != 0 and "RETENTION_UNDECIDED_YEARS" in result.stdout + result.stderr
    assert (
        empty_db.query("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")[0][0]
        == 0
    )  # antes de tocar la base


# --- 2. case-service -------------------------------------------------------------------------------------------------------------------------


def test_2_case_service_starts_from_the_chart_variables_answers_the_contract_and_stops_cleanly(
    db: Db, pg: Any, keycloak: Double, kind_docs: list[Doc], run: Run
) -> None:
    c, pod = (
        container_of(kind_docs, "Deployment", "case-service"),
        pod_of(kind_docs, "Deployment", "case-service"),
    )
    overrides = {
        "CASE_DB_DSN": pg_dsn(int(pg.get_exposed_port(5432)), db.name),
        "VECTRA_TOKEN_URL": keycloak.url + "/token",
        "VECTRA_JWKS_URL": keycloak.url + "/jwks",
        "VECTRA_OIDC_ISSUER": mock_auth.ISSUER,
    }
    args = run.args(c, pod, overrides=overrides, role="case_app")
    grace = pod["terminationGracePeriodSeconds"]
    with running(args, "case-service-test") as name:
        ops = f"http://127.0.0.1:{host_port(name, 8081)}"
        assert wait_ok(ops + "/readyz", name).status_code == 200
        assert wait_ok(ops + "/healthz", name).status_code == 200
        metrics = httpx.get(ops + "/metrics", timeout=5).text
        assert "vectra_cases_failclosed_persistent" in metrics and "vectra_case_jobs_overdue" in metrics
        assert (
            httpx.get(f"http://127.0.0.1:{host_port(name, 8080)}/v1/cases", timeout=5).status_code == 401
        )  # sin token: el contrato de U0
        rest = memory_at_rest(name)
        elapsed, code = stop_and_time(name, grace)
    TIMINGS["case-service"] = elapsed
    print(
        f"case-service: memoria en reposo {rest}; docker stop -t {grace}: {elapsed:.1f} s, codigo {code}; carga {uptime()}"
    )  # noqa: T201
    assert code in {"0", "143"}, (
        f"SIGTERM: salio con {code} (137 es SIGKILL: no paro dentro del plazo de gracia)"
    )
    assert elapsed < grace


# --- 3. case-worker --------------------------------------------------------------------------------------------------------------------------


def worker_args(
    run: Run, docs: list[Doc], pg_port: int, database: str, keycloak: Double, *, drop: tuple[str, ...] = ()
) -> tuple[list[str], int]:
    c, pod = container_of(docs, "Deployment", "case-worker"), pod_of(docs, "Deployment", "case-worker")
    overrides = {
        "CASE_DB_DSN": pg_dsn(pg_port, database),
        "CASE_SCORING_URL": keycloak.url,
        "CASE_GOVERNANCE_URL": keycloak.url,
        "VECTRA_TOKEN_URL": keycloak.url + "/token",
    }
    return run.args(c, pod, overrides=overrides, role="case_worker", drop=drop), int(
        pod["terminationGracePeriodSeconds"]
    )


def test_3_case_worker_serves_only_the_ops_port_exposes_its_series_and_exits_0_within_the_chart_grace(
    db: Db, pg: Any, keycloak: Double, kind_docs: list[Doc], run: Run
) -> None:
    args, grace = worker_args(run, kind_docs, int(pg.get_exposed_port(5432)), db.name, keycloak)
    with running(args, "case-worker-test") as name:
        ops = f"http://127.0.0.1:{host_port(name, 8081)}"
        assert wait_ok(ops + "/readyz", name).status_code == 200
        metrics = httpx.get(ops + "/metrics", timeout=5).text
        assert re.search(r"^vectra_case_attempts_total\{[^}]*\} 0\.0$", metrics, flags=re.M), (
            "las series de intentos nacen en 0"
        )
        probe = docker(
            "exec",
            name,
            "python",
            "-c",
            "import socket; s = socket.socket(); s.settimeout(2); print(s.connect_ex(('127.0.0.1', 8080)))",
        )
        assert probe.stdout.strip() not in {"0", ""}, "el worker no abre el 8080"
        rest = memory_at_rest(name)
        elapsed, code = stop_and_time(name, grace)
    TIMINGS["case-worker"] = elapsed
    print(
        f"case-worker: memoria en reposo {rest}; docker stop -t {grace}: {elapsed:.1f} s, codigo {code}; carga {uptime()}"
    )  # noqa: T201
    assert code == "0", f"el worker sale con 0 dentro del plazo (P-4); salio con {code}"
    assert elapsed < grace


def test_3_without_the_scoring_url_the_worker_does_not_start(
    db: Db, pg: Any, keycloak: Double, kind_docs: list[Doc], run: Run
) -> None:
    args, _ = worker_args(
        run, kind_docs, int(pg.get_exposed_port(5432)), db.name, keycloak, drop=("CASE_SCORING_URL",)
    )
    result = docker("run", "--rm", *args)
    assert result.returncode != 0 and "CASE_SCORING_URL" in result.stderr, result.stdout + result.stderr


def stops_without_serving(args: list[str], prefix: str, seconds: float = 40.0) -> tuple[str, str]:
    """El contenedor que no puede arrancar termina solo y nunca sirve `/readyz`; devuelve (codigo de salida, registros)."""
    with running(args, prefix) as name:
        end = time.monotonic() + seconds
        while (
            time.monotonic() < end
            and docker("inspect", name, "--format", "{{.State.Running}}").stdout.strip() == "true"
        ):
            time.sleep(0.3)
        state = docker("inspect", name, "--format", "{{.State.Running}} {{.State.ExitCode}}").stdout.split()
        assert state[0] == "false", "el contenedor sin llave sigue vivo: debia terminar"
        logs = docker("logs", name)
        return state[1], logs.stdout + logs.stderr


@pytest.mark.parametrize("how", ["file-not-mounted", "variable-missing"])
def test_3_without_the_key_the_service_does_not_start(
    how: str, db: Db, pg: Any, keycloak: Double, kind_docs: list[Doc], run: Run
) -> None:
    """Un chart que no monta la llave (el defecto de U04-T08) deja al pod sin arrancar. `vectra_common.ops_server.run_service` (U0) sale con 0 cuando el arranque falla
    (uvicorn registra el fallo y vuelve): se anota como candidata; aqui se exige que el contenedor termine y que nunca llegue a servir."""
    c, pod = (
        container_of(kind_docs, "Deployment", "case-service"),
        pod_of(kind_docs, "Deployment", "case-service"),
    )
    overrides = {
        "CASE_DB_DSN": pg_dsn(int(pg.get_exposed_port(5432)), db.name),
        "VECTRA_TOKEN_URL": keycloak.url + "/token",
    }
    drop = ("VECTRA_CLIENT_KEY_PATH",) if how == "variable-missing" else ()
    args = run.args(c, pod, overrides=overrides, role="case_app", drop=drop, mount_key=False, publish=False)
    code, logs = stops_without_serving(args, "case-service-nokey")
    print(f"case-service sin llave ({how}): termina con codigo {code}")  # noqa: T201
    assert '"level": "error"' in logs, logs


# --- 4. core-banking-mock --------------------------------------------------------------------------------------------------------------------


def mock_args(run: Run, docs: list[Doc], keycloak: Double, bind: str = "127.0.0.1") -> list[str]:
    c, pod = (
        container_of(docs, "Deployment", "core-banking-mock"),
        pod_of(docs, "Deployment", "core-banking-mock"),
    )
    overrides = {"VECTRA_JWKS_URL": keycloak.url + "/jwks", "VECTRA_OIDC_ISSUER": mock_auth.ISSUER}
    return run.args(c, pod, overrides=overrides, image=MOCK_IMAGE, bind=bind)


def test_4_the_mock_serves_the_fixture_from_the_image_with_a_read_only_root_and_counts_the_write_attempt(
    keycloak: Double, kind_docs: list[Doc], run: Run
) -> None:
    with running(mock_args(run, kind_docs, keycloak), "core-mock-test") as name:
        ops = f"http://127.0.0.1:{host_port(name, 8081)}"
        api = f"http://127.0.0.1:{host_port(name, 8080)}"
        metrics = wait_ok(ops + "/metrics", name).text
        assert re.search(r"^vectra_core_write_attempts_total 0\.0$", metrics, flags=re.M)
        read = httpx.get(
            f"{api}/v1/credits/{CREDIT_ID}", headers=mock_auth.bearer("core:read-credit"), timeout=10
        )
        assert read.status_code == 200, (
            read.text
        )  # el fixture esta en la imagen y se lee con el sistema de archivos de solo lectura
        assert read.json()["credit_id"] == CREDIT_ID
        write = httpx.post(
            f"{api}/v1/credits/{CREDIT_ID}/status",
            headers=mock_auth.bearer("core:read-credit"),
            json={"credit_id": CREDIT_ID, "status": "desembolsado"},
            timeout=10,
        )
        assert write.status_code == 403
        assert re.search(
            r"^vectra_core_write_attempts_total 1\.0$",
            httpx.get(ops + "/metrics", timeout=5).text,
            flags=re.M,
        )
        rest = memory_at_rest(name)
    print(f"core-banking-mock: memoria en reposo {rest}; carga {uptime()}")  # noqa: T201


# --- 5. el Job rt5-demo ------------------------------------------------------------------------------------------------------------------------


def rt5_args(run: Run, core_url: str) -> list[str]:
    docs = render("kind", "--set", f"probes.runId={RUN_ID}")
    job = next(d for d in docs if d["kind"] == "Job" and d["metadata"]["name"] == f"rt5-demo-{RUN_ID}")
    c = job["spec"]["template"]["spec"]["containers"][0]
    return run.args(c, job["spec"]["template"]["spec"], overrides={"CASE_CORE_URL": core_url}, publish=False)


def test_5_the_rt5_job_exits_0_only_for_the_proxy_403_and_prints_the_code_and_the_header(run: Run) -> None:
    double = Double(proxy_403).start()
    try:
        result = docker("run", "--rm", *rt5_args(run, double.url))
    finally:
        double.stop()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "403" in result.stdout
        and "l5d-proxy-error" in result.stdout
        and "unauthorized request on route" in result.stdout
    )
    assert double.requests == [("POST", f"/v1/credits/{CREDIT_ID}/status")]


def test_5_against_the_real_mock_without_the_proxy_the_job_gets_a_401_and_exits_nonzero(
    keycloak: Double, kind_docs: list[Doc], run: Run
) -> None:
    """Sin proxy, el mock responde 401 (sin token): la evidencia no es la esperada y `completionTime` no existe."""
    with running(mock_args(run, kind_docs, keycloak, bind="0.0.0.0"), "core-mock-rt5") as name:  # noqa: S104 - el Job llega por host.docker.internal
        api = f"http://{HOST}:{host_port(name, 8080)}"
        wait_ok(f"http://127.0.0.1:{host_port(name, 8081)}/readyz", name)
        result = docker("run", "--rm", *rt5_args(run, api))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "401" in result.stdout


def test_5_without_a_connection_the_job_exits_nonzero(run: Run) -> None:
    result = docker("run", "--rm", *rt5_args(run, f"http://{HOST}:1"))
    assert result.returncode == 2 and "sin respuesta" in result.stdout
