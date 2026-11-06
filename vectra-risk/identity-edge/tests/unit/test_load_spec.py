"""Especificacion de la prueba de carga de U2 (U02-T15, CA-2 y CA-3): `k6 inspect` contra el diseno, sin cluster.

Los valores esperados salen de NFR-U2-10..11, la nota J1-J7 del plan, el realm de kind y `routes.yaml`
(`load_design`), no de literales. Cada comprobacion falla en una copia mutada del script.
"""

import os
import re
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


def test_the_design_values_are_the_ones_of_the_plan():
    """Un control del lector del diseno: si cambia el texto, estos valores se mueven con el."""
    expected = ld.thresholds()
    assert (expected.login_p95_ms, expected.token_p95_ms, expected.jwks_p95_ms) == (500, 200, 50)
    assert expected.failed_rate == 0.01 and expected.overhead_p95_ms == 5
    assert ld.ramp_and_sustain_seconds() == (120, 900) and ld.login_rate_ceiling() == 10
    assert ld.concurrent_users() == 200 and ld.service_identities() == 10 and ld.renew_seconds() == 300
    assert len(ld.service_clients()) == 10 and {"case-worker", "bias-monitoring-job"} <= ld.service_clients()
    assert ld.load_users() == ("load-", 1, 200) and ld.console_limit_per_second() == 20 and ld.console_retry_after() == "1"
    assert ld.load_role() == "analista"


MUTANTS = [
    ("umbral:login", r"p\(95\)<500", "p(95)<600"),
    ("umbral:token", r"p\(95\)<200", "p(95)<250"),
    ("umbral:jwks", r"p\(95\)<50\b", "p(95)<60"),
    ("umbral:failed", r"rate<0\.01", "rate<0.05"),
    ("users:vus", r"const USERS = 200", "const USERS = 100"),
    ("services:clientes", r"'case-worker',\s*", ""),
    ("services:clientes", r"const SERVICE_CLIENTS = \[\s*'[a-z-]+',", "const SERVICE_CLIENTS = ["),
    ("services:clientes", r"const SERVICE_CLIENTS = \[", "const SERVICE_CLIENTS = ['extra-client', "),
    ("console-burst:tasa", r"const BURST_RATE = \d+", "const BURST_RATE = 15"),
    ("users:logins", r"const RAMP_S = 120", "const RAMP_S = 10"),
    ("perfil:users", r"const SUSTAIN_S = 900", "const SUSTAIN_S = 600"),
    ("console-burst:retry-after", r"RETRY_AFTER: '1'", "RETRY_AFTER: '60'"),
    ("overhead:umbral", r"const OVERHEAD_P95_BUDGET_MS = 5", "const OVERHEAD_P95_BUDGET_MS = 7"),
    ("services:renovacion", r"const RENEW_S = 300", "const RENEW_S = 600"),
    ("escenarios", r"\bjwks: \{", "jwks2: {"),
    ("users:nombres", r"USER_PREFIX: 'load-'", "USER_PREFIX: 'carga-'"),
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


def test_the_script_runs_against_a_fake_gateway_scaled_down(tmp_path):
    """El flujo del script (PKCE, `private_key_jwt` ES256, JWKS, 429 de la consola, veredicto) corre con k6 contra un gateway falso.

    El perfil se reduce (10 usuarios, 30 s): solo cambian las constantes de tiempo y tamano, no la logica. No es la prueba de carga.
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
    scaled = SCRIPT_TEXT
    for name, value in (("USERS", 10), ("RAMP_S", 6), ("SUSTAIN_S", 24), ("RENEW_S", 10), ("USER_RENEW_S", 5)):
        scaled, count = re.subn(rf"^const {name} = \d+;", f"const {name} = {value};", scaled, count=1, flags=re.M)
        assert count == 1, name
    script = tmp_path / "identity.js"
    script.write_text(scaled, encoding="utf-8")
    workdir = tmp_path / "out"
    workdir.mkdir()
    with fg.FakeGateway(public, "pw-de-carga", int(ld.console_limit_per_second()), ld.console_retry_after()) as gateway:
        env = {
            "PATH": os.environ["PATH"], "K6_BASE_URL": gateway.url, "K6_ECHO_DIRECT_URL": gateway.url,
            "K6_CLIENT_KEYS_DIR": str(keys_dir), "K6_LOAD_PASSWORD": "pw-de-carga",
        }  # fmt: skip
        done = subprocess.run(  # noqa: S603
            [str(ld.K6), "run", str(script)], env=env, cwd=workdir, capture_output=True, text=True, check=False, timeout=120
        )
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    assert gateway.bad_requests == []
    assert gateway.signed_clients == ld.service_clients()
    prefix, first, _ = ld.load_users()
    assert {f"{prefix}{i:03d}" for i in range(first, first + 10)} <= gateway.logins
    assert gateway.limited > 0
    import json

    verdict = json.loads((workdir / "overhead-verdict.json").read_text(encoding="utf-8"))
    assert verdict["console"]["ok"] is True and verdict["overhead"]["budget_ms"] == ld.thresholds().overhead_p95_ms
    assert verdict["overhead"]["ok"] is True
