"""Especificacion de la prueba de carga de U2 (U02-T15, CA-2 y CA-3): `k6 inspect` contra el diseno, sin cluster.

Los valores esperados salen de NFR-U2-10..11, la nota J1-J7 del plan, el realm de kind y `routes.yaml`
(`load_design`), no de literales. Cada comprobacion falla en una copia mutada del script.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import load_checks as lc
import load_design as ld
import pytest

SCRIPT_TEXT = ld.SCRIPT.read_text(encoding="utf-8")


def mutated(tmp_path: Path, pattern: str, replacement: str) -> Path:
    new, count = re.subn(pattern, replacement, SCRIPT_TEXT, count=1)
    assert count == 1, f"la mutacion no encuentra {pattern!r}"
    assert new != SCRIPT_TEXT
    path = tmp_path / "identity.js"
    path.write_text(new, encoding="utf-8")
    return path


def test_the_script_matches_the_design():
    assert lc.inspect_problems(ld.SCRIPT) == []


def test_inspect_runs_without_environment_and_shows_the_thresholds():
    """CA-2: `env -i`, termina en 0 y muestra los tres p95 y `http_req_failed`."""
    done = subprocess.run(  # noqa: S603
        ["/usr/bin/env", "-i", f"PATH={os.environ['PATH']}", str(ld.K6), "inspect", str(ld.SCRIPT)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    expected = ld.thresholds()
    for limit in (expected.login_p95_ms, expected.token_p95_ms, expected.jwks_p95_ms):
        assert f"p(95)\\u003c{limit}" in done.stdout or f"p(95)<{limit}" in done.stdout
    assert "http_req_failed" in done.stdout


def test_the_design_reader_returns_consistent_values():
    """Un control del lector del diseno sin repetir sus valores: que se lean y que sean coherentes entre si."""
    expected = ld.thresholds()
    assert min(expected.login_p95_ms, expected.token_p95_ms, expected.jwks_p95_ms, expected.overhead_p95_ms) > 0
    assert 0 < expected.failed_rate < 1
    ramp, sustain = ld.ramp_and_sustain_seconds()
    assert ramp > 0 and sustain > 0 and ld.login_rate_ceiling() > 0 and ld.renew_seconds() > 0
    prefix, first, last = ld.load_users()
    assert last - first + 1 == ld.concurrent_users()
    assert len(ld.service_clients()) == ld.service_identities()
    assert ld.console_limit_per_second() > 0 and ld.console_retry_after()
    assert ld.load_role() and prefix


def _worse(value: float) -> float:
    return value * 2 + 1


_T = ld.thresholds()
_RAMP, _SUSTAIN = ld.ramp_and_sustain_seconds()
_PREFIX, _, _ = ld.load_users()
_CLIENTS = sorted(ld.service_clients())
# Cada patron y cada reemplazo se derivan del diseno (ld): si el diseno cambia, el patron cambia con el.
MUTANTS = [
    ("umbral:login", rf"p\(95\)<{_T.login_p95_ms}\b", f"p(95)<{_worse(_T.login_p95_ms)}"),
    ("umbral:token", rf"p\(95\)<{_T.token_p95_ms}\b", f"p(95)<{_worse(_T.token_p95_ms)}"),
    ("umbral:jwks", rf"p\(95\)<{_T.jwks_p95_ms}\b", f"p(95)<{_worse(_T.jwks_p95_ms)}"),
    ("umbral:failed", rf"rate<{_T.failed_rate:g}\b", f"rate<{_worse(_T.failed_rate):g}"),
    ("umbral:checks", r"\n\s*checks: \[[^\n]*\n", "\n"),
    ("umbral:checks", r"checks: \['rate>[0-9.]+'\]", f"checks: ['rate>{_T.failed_rate:g}']"),
    ("users:vus", rf"const USERS = {ld.concurrent_users()}\b", f"const USERS = {ld.concurrent_users() // 2}"),
    ("services:clientes", rf"'{_CLIENTS[0]}',\s*", ""),
    ("services:clientes", r"const SERVICE_CLIENTS = \[\s*'[a-z-]+',", "const SERVICE_CLIENTS = ["),
    ("services:clientes", r"const SERVICE_CLIENTS = \[", "const SERVICE_CLIENTS = ['extra-client', "),
    ("console-burst:tasa", r"const BURST_RATE = \d+", f"const BURST_RATE = {int(ld.console_limit_per_second()) - 5}"),
    ("users:logins", rf"const RAMP_S = {_RAMP}\b", "const RAMP_S = 10"),
    ("perfil:users", rf"const SUSTAIN_S = {_SUSTAIN}\b", f"const SUSTAIN_S = {_SUSTAIN // 2}"),
    ("console-burst:retry-after", rf"RETRY_AFTER: '{ld.console_retry_after()}'", f"RETRY_AFTER: '{_worse(int(ld.console_retry_after()))}'"),
    ("overhead:umbral", rf"const OVERHEAD_P95_BUDGET_MS = {_T.overhead_p95_ms}\b", f"const OVERHEAD_P95_BUDGET_MS = {_worse(_T.overhead_p95_ms)}"),
    ("services:renovacion", rf"const RENEW_S = {ld.renew_seconds()}\b", f"const RENEW_S = {ld.renew_seconds() * 2}"),
    ("escenarios", r"\bjwks: \{", "jwks2: {"),
    ("users:nombres", rf"const USER_PREFIX = '{_PREFIX}'", f"const USER_PREFIX = 'x{_PREFIX}'"),
    ("users:nombres", r"env: \{ USER_PREFIX,", "env: { USER_PREFIX: 'x',"),
    ("users:nombres", r"const USER_FIRST = \d+", "const USER_FIRST = 2"),
    ("overhead:umbral", r"MAX_DIFF_P95_MS: String\(OVERHEAD_P95_BUDGET_MS\)", "MAX_DIFF_P95_MS: '50'"),
]


@pytest.mark.parametrize(("marker", "pattern", "replacement"), MUTANTS, ids=[f"{m[0]}:{m[2][:24]}" for m in MUTANTS])
def test_each_check_fails_on_a_mutated_copy(tmp_path, marker, pattern, replacement):
    problems = lc.inspect_problems(mutated(tmp_path, pattern, replacement))
    assert any(p.startswith(marker) for p in problems), f"{marker} no fallo; fallos: {problems}"


def test_a_script_that_needs_environment_at_init_fails_inspect(tmp_path):
    """El init context no puede exigir variables (`inspect` corre sin ellas): la falta se comprueba en `setup()`."""
    path = tmp_path / "identity.js"
    path.write_text(SCRIPT_TEXT + "\nif (!__ENV.K6_BASE_URL) { throw new Error('falta K6_BASE_URL'); }\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="k6 inspect termino en"):
        lc.run_inspect(path)


def test_setup_names_the_missing_variables(tmp_path):
    """La falta de una variable se comprueba en `setup()`, que es lo que corre en el Paso 16: `k6 run` sin entorno falla ahi."""
    done = subprocess.run(  # noqa: S603
        [str(ld.K6), "run", str(ld.SCRIPT)], env={"PATH": os.environ["PATH"]}, cwd=tmp_path,
        capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip
    assert done.returncode != 0
    for variable in ("K6_BASE_URL", "K6_ECHO_DIRECT_URL", "K6_CLIENT_KEYS_DIR", "K6_LOAD_PASSWORD"):
        assert variable in done.stderr + done.stdout, variable
    assert "setup" in done.stderr + done.stdout


def _scaled_script(tmp_path: Path) -> Path:
    """`identity.js` con el perfil reducido (10 usuarios, 30 s): solo cambian constantes de tiempo y tamano, no la logica."""
    scaled = SCRIPT_TEXT
    for name, value in (("USERS", 10), ("RAMP_S", 6), ("SUSTAIN_S", 24), ("RENEW_S", 10), ("USER_RENEW_S", 5)):
        scaled, count = re.subn(rf"^const {name} = \d+;", f"const {name} = {value};", scaled, count=1, flags=re.M)
        assert count == 1, name
    directory = tmp_path / "load"
    directory.mkdir()
    (directory / "identity.js").write_text(scaled, encoding="utf-8")
    return directory


def _run_load(tmp_path: Path, delay_s: float) -> dict:
    """`make -C identity-edge load` sobre el script reducido y dos gateways falsos: el del gateway (con `delay_s` de sobrecosto) y el directo.

    Devuelve el codigo de salida de make, el veredicto, los dos gateways y los puntos de k6 (`K6_OUT=json`).
    """
    import fake_gateway_server as fg
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    public = {}
    for client in ld.service_clients():
        key = ec.generate_private_key(ec.SECP256R1())
        public[client] = key.public_key()
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        (keys_dir / f"{client}.pem").write_bytes(pem)
    load_dir = _scaled_script(tmp_path)
    out = tmp_path / "out"
    limit, retry = int(ld.console_limit_per_second()), ld.console_retry_after()
    # El cliente `vectra-console` solo tiene registrados los redirect URI del realm (https, sin puerto): como Keycloak, el falso los exige.
    registered = ld.console_redirect_uris("127.0.0.1")
    with (
        fg.FakeGateway(public, "pw-de-carga", limit, retry, delay_s, None, registered) as gateway,
        fg.FakeGateway(public, "pw-de-carga", limit, retry) as direct,
    ):
        env = {
            **os.environ, "K6_BASE_URL": gateway.url, "K6_ECHO_DIRECT_URL": direct.url,
            "K6_CLIENT_KEYS_DIR": str(keys_dir), "K6_LOAD_PASSWORD": "pw-de-carga", "K6_OUT": f"json={tmp_path / 'points.json'}",
        }  # fmt: skip
        done = subprocess.run(  # noqa: S603
            [shutil.which("make") or "make", "-C", str(ld.EDGE), "load", f"LOAD={load_dir}", f"LOAD_OUT={out}"],
            env=env, capture_output=True, text=True, check=False, timeout=240,
        )  # fmt: skip
    verdict = json.loads((out / "overhead-verdict.json").read_text(encoding="utf-8"))
    return {"done": done, "out": out, "verdict": verdict, "gateway": gateway, "direct": direct, "points": tmp_path / "points.json"}


@pytest.fixture(scope="module")
def within_budget(tmp_path_factory):
    """Los dos tramos con la misma latencia: la diferencia de p95 queda por debajo de NFR-U2-11."""
    return _run_load(tmp_path_factory.mktemp("within"), 0.0)


@pytest.fixture(scope="module")
def over_budget(tmp_path_factory):
    """El tramo del gateway tarda tres veces el presupuesto de NFR-U2-11 mas que el directo."""
    return _run_load(tmp_path_factory.mktemp("over"), 3 * ld.thresholds().overhead_p95_ms / 1000)


def test_the_script_runs_against_a_fake_gateway_scaled_down(within_budget):
    """El flujo del script (PKCE, `private_key_jwt` ES256, JWKS, 429 de la consola, veredicto) corre con k6 contra un gateway falso."""
    done, gateway = within_budget["done"], within_budget["gateway"]
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert gateway.bad_requests == [] and within_budget["direct"].bad_requests == []
    assert gateway.signed_clients == ld.service_clients()
    prefix, first, _ = ld.load_users()
    assert {f"{prefix}{i:03d}" for i in range(first, first + 10)} <= gateway.logins
    assert gateway.limited > 0
    verdict = within_budget["verdict"]
    assert verdict["console"]["ok"] is True and verdict["overhead"]["budget_ms"] == ld.thresholds().overhead_p95_ms
    assert verdict["overhead"]["ok"] is True
    assert lc.verdict_problems(verdict) == []


def test_the_redirect_uri_is_one_of_the_registered_ones(within_budget):
    """R-05: el redirect URI sale solo del host de `K6_BASE_URL` (sin puerto y siempre https): es uno de los del realm de kind."""
    gateway = within_budget["gateway"]
    assert gateway.redirects_seen, "el script no mando ningun redirect_uri"
    assert gateway.redirects_seen <= ld.console_redirect_uris("127.0.0.1"), gateway.redirects_seen
    assert not [b for b in gateway.bad_requests if "redirect_uri" in b]


def test_a_relogin_in_the_same_vu_does_not_reuse_the_sso_cookie(tmp_path):
    """R-01: tras un login Keycloak deja la cookie SSO en `/auth/realms/vectra/`; el segundo login del VU debe pedir la contrasena otra vez."""
    import fake_gateway_server as fg

    script = tmp_path / "relogin.js"
    script.write_text(
        SCRIPT_TEXT.replace("export function setup() {", "function setup() {")  # sin llaves de servicio ni eco directo
        + """
options.scenarios = { relogin: { executor: 'per-vu-iterations', exec: 'reloginFlow', vus: 1, iterations: 1 } };
options.thresholds = {};
export async function reloginFlow() {
  const first = await login('load-001');
  const second = await login('load-001');
  console.log(`RELOGIN ${first !== null} ${second !== null}`);
}
""",
        encoding="utf-8",
    )
    with fg.FakeGateway({}, "pw-de-carga", 20, "1", allowed_redirects=ld.console_redirect_uris("127.0.0.1")) as gateway:
        env = {
            **os.environ, "K6_BASE_URL": gateway.url, "K6_LOAD_PASSWORD": "pw-de-carga",
        }  # fmt: skip
        done = subprocess.run(  # noqa: S603
            [str(ld.K6), "run", "--quiet", "--no-usage-report", str(script)], env=env, cwd=tmp_path,
            capture_output=True, text=True, check=False, timeout=60,
        )  # fmt: skip
    assert "RELOGIN true true" in done.stdout + done.stderr, done.stdout[-800:] + done.stderr[-800:]
    assert gateway.sso_hits == 0, "el segundo login llego con la cookie SSO: clear() no la borro"
    assert gateway.bad_requests == []


def test_the_two_legs_of_the_overhead_go_to_different_targets(within_budget):
    """El tramo `gateway` va a `K6_BASE_URL` y el `direct` a `K6_ECHO_DIRECT_URL`, y solo el primero pasa por la autenticacion."""
    gateway, direct = within_budget["gateway"], within_budget["direct"]
    assert gateway.overhead_hits > 0 and direct.overhead_hits > 0
    assert gateway.overhead_hits == direct.overhead_hits, "cada iteracion pide el mismo request por los dos tramos"
    assert all("/overhead" in path for path in direct.paths), f"al directo solo llega /overhead: {set(direct.paths)}"
    assert any("/overhead" not in path for path in gateway.paths)


def test_a_p95_difference_over_the_budget_fails_the_verdict_and_make_load(over_budget):
    """J3 (enmienda): `handleSummary` no puede salir con error en k6 v2.3.0; el veredicto `ok:false` y `make load` distinto de cero lo cumplen."""
    verdict = over_budget["verdict"]
    assert verdict["overhead"]["ok"] is False
    assert verdict["overhead"]["diff_p95_ms"] > verdict["overhead"]["budget_ms"]
    assert verdict["overhead"]["budget_ms"] == ld.thresholds().overhead_p95_ms
    assert any(p.startswith("NFR-U2-11") for p in lc.verdict_problems(verdict))
    assert over_budget["done"].returncode != 0, "make load debe salir con error si se excede NFR-U2-11"
    assert "NFR-U2-11" in over_budget["done"].stdout


def test_a_verdict_without_rate_limited_responses_fails():
    ok = {"overhead": {"ok": True, "diff_p95_ms": 0, "budget_ms": 1}, "console": {"ok": True}}
    assert lc.verdict_problems(ok) == []
    assert any(p.startswith("consola") for p in lc.verdict_problems({**ok, "console": {"ok": False}}))
    assert any(p.startswith("NFR-U2-11") for p in lc.verdict_problems({**ok, "overhead": {**ok["overhead"], "ok": False}}))


def test_every_request_is_tagged_with_the_flow_of_its_path(within_budget):
    """Las latencias de cada umbral salen de las peticiones correctas: el POST de `login-actions` va con `flow:login`, etc."""
    # k6 sustituye el tag `url` por `name` cuando el script lo fija: se compara por el nombre de cada request.
    expected = (("login-actions", "login"), ("GET auth", "login"), ("POST token", "token"), ("GET certs", "jwks"),
                ("GET overhead", "overhead"), ("GET /api/console", "console"))  # fmt: skip
    seen: dict[str, set[str]] = {}
    for line in within_budget["points"].read_text(encoding="utf-8").splitlines():
        point = json.loads(line)
        if point.get("type") != "Point" or point["metric"] != "http_req_duration":
            continue
        tags = point["data"]["tags"]
        for fragment, flow in expected:
            if fragment in tags["name"]:
                seen.setdefault(fragment, set()).add(tags.get("flow", ""))
                assert tags.get("flow") == flow, f"{tags['name']} lleva flow={tags.get('flow')}, debe llevar {flow}"
    assert set(seen) == {fragment for fragment, _ in expected}, f"sin peticiones para {set(dict(expected)) - set(seen)}"
