"""`seed-vault.sh identity` (U02-T19, B-2): las rutas `identity/` y `edge/valkey` con valores de forma real, probadas con dobles de Vault y de kubectl.

Nada de esto toca un clúster: Vault es un diccionario, la CA sale de un certificado generado aquí y `kubectl` es un script.
"""

import base64
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import jwt
import pyotp
import pytest
import yaml
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import vault_paths as vp  # noqa: E402

SEED_VAULT = Path(os.environ.get("SEED_VAULT_SCRIPT", HERE / "seed-vault.sh"))
REALM = yaml.safe_load(vp.REALM_KIND.read_text(encoding="utf-8"))
SERVICE_CLIENTS = sorted(c["clientId"] for c in REALM["clients"] if c.get("serviceAccountsEnabled"))
JWKS_CLIENTS = sorted(c["clientId"] for c in REALM["clients"] if "$(env:CLIENT_" in str(c.get("attributes", {}).get("jwks.string", "")))
SYNTH_PROPERTIES = sorted(set(re.findall(r"\$\(env:(SYNTH_[A-Z0-9_]+)\)", vp.REALM_KIND.read_text(encoding="utf-8"))))


def make_ca_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "vectra-internal-ca")])
    now = datetime.datetime.now(datetime.UTC)
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
    cert = cert.not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1)).sign(key, hashes.SHA256())
    return cert.public_bytes(serialization.Encoding.PEM).decode()


CA_PEM = make_ca_pem()


class FakeVault:
    """Doble de `Vault`: lo que `vault kv get/put` haria, en memoria."""

    def __init__(self, initial: dict[str, dict[str, str]] | None = None) -> None:
        self.store = {path: dict(data) for path, data in (initial or {}).items()}
        self.writes: list[str] = []

    def read(self, path: str) -> dict[str, str]:
        return dict(self.store.get(path, {}))

    def write(self, path: str, data: dict[str, str]) -> None:
        self.store[path] = dict(data)
        self.writes.append(path)


def seed(vault: FakeVault, keys_dir: Path) -> list[str]:
    written, _ = vp.seed_identity(vault, lambda: CA_PEM, keys_dir)
    return written


@pytest.fixture
def keys_dir(tmp_path: Path) -> Path:
    return tmp_path / "vectra-e2e-keys"


@pytest.fixture
def seeded(keys_dir: Path) -> FakeVault:
    vault = FakeVault()
    seed(vault, keys_dir)
    return vault


# --- las rutas ----------------------------------------------------------------------------------------------------


def test_list_has_every_identity_path_and_the_valkey_one():
    listed = {path for path in vp.listing() if path.startswith(("identity/", "edge/valkey"))}
    wanted = {"identity/ca", "identity/synthetic-users", "identity/break-glass", "identity/keycloak-admin", "edge/valkey"}
    wanted |= {f"identity/clients/{c}" for c in JWKS_CLIENTS}
    assert wanted <= listed, wanted - listed
    assert len(JWKS_CLIENTS) == 15 and len(SERVICE_CLIENTS) == 14


def test_the_command_line_list_prints_them():
    out = subprocess.run([sys.executable, str(HERE / "vault_paths.py"), "list"], capture_output=True, text=True, check=True).stdout
    assert "identity/ca ca.crt" in out and "identity/keycloak-admin username" in out and "edge/valkey ratelimit" in out


def test_list_properties_match_what_the_external_secrets_and_the_realm_read():
    refs = vp.listing()
    assert refs["identity/ca"] == {"ca.crt"}
    assert refs["identity/keycloak-admin"] == {"username", "password"}
    assert refs["identity/break-glass"] == {"BREAK_GLASS_PASSWORD"}
    assert refs["identity/synthetic-users"] == set(SYNTH_PROPERTIES) and len(SYNTH_PROPERTIES) == 20
    assert all("jwks" in refs[f"identity/clients/{c}"] for c in JWKS_CLIENTS)
    assert all(("private-key" in refs[f"identity/clients/{c}"]) == (c in SERVICE_CLIENTS) for c in JWKS_CLIENTS)


def test_u1_seed_does_not_write_identity_paths():
    class Recorder(FakeVault):
        pass

    vault = Recorder()
    done = vp.seed(vault)
    assert done and not [p for p in done if p.startswith(("identity/", "edge/"))]


# --- los pares ES256 -------------------------------------------------------------------------------------------


def test_every_service_client_has_a_readable_pkcs8_es256_key(seeded: FakeVault):
    for client in SERVICE_CLIENTS:
        pem = seeded.store[f"identity/clients/{client}"]["private-key"]
        assert pem.startswith("-----BEGIN PRIVATE KEY-----"), client  # PKCS#8, no "EC PRIVATE KEY" ni "RSA"
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        assert isinstance(key, ec.EllipticCurvePrivateKey) and key.curve.name == "secp256r1"


def test_the_jwks_validates_a_token_signed_with_its_private_key(seeded: FakeVault):
    for client in SERVICE_CLIENTS:
        data = seeded.store[f"identity/clients/{client}"]
        jwks = jwt.PyJWKSet.from_json(data["jwks"])
        (jwk,) = jwks.keys
        token = jwt.encode({"iss": client, "aud": "x"}, data["private-key"], algorithm="ES256", headers={"kid": jwk.key_id})
        assert jwt.decode(token, jwk.key, algorithms=["ES256"], audience="x")["iss"] == client


def test_the_jwks_is_one_public_es256_signing_key_without_private_material(seeded: FakeVault):
    for client in JWKS_CLIENTS:
        keys = json.loads(seeded.store[f"identity/clients/{client}"]["jwks"])["keys"]
        assert len(keys) == 1
        assert keys[0]["kty"] == "EC" and keys[0]["crv"] == "P-256" and keys[0]["alg"] == "ES256" and keys[0]["use"] == "sig"
        assert "d" not in keys[0]


def test_the_kid_is_the_rfc7638_thumbprint_and_is_stable(seeded: FakeVault):
    for client in SERVICE_CLIENTS:
        data = seeded.store[f"identity/clients/{client}"]
        (jwk,) = json.loads(data["jwks"])["keys"]
        canonical = json.dumps({k: jwk[k] for k in ("crv", "kty", "x", "y")}, separators=(",", ":"), sort_keys=True)
        digest = hashes.Hash(hashes.SHA256())
        digest.update(canonical.encode())
        assert jwk["kid"] == base64.urlsafe_b64encode(digest.finalize()).rstrip(b"=").decode()
        again = vp.public_jwk(vp.load_private(data["private-key"]))  # derivar de nuevo da el mismo kid
        assert again == jwk


def test_each_client_has_its_own_pair(seeded: FakeVault):
    keys = [seeded.store[f"identity/clients/{c}"]["private-key"] for c in SERVICE_CLIENTS]
    kids = {json.loads(seeded.store[f"identity/clients/{c}"]["jwks"])["keys"][0]["kid"] for c in JWKS_CLIENTS}
    assert len(set(keys)) == len(keys) and len(kids) == len(JWKS_CLIENTS)


def test_a_client_without_a_service_account_only_gets_a_jwks(seeded: FakeVault):
    grafana = seeded.store["identity/clients/grafana"]
    assert set(grafana) == {"jwks"}


# --- idempotencia: nunca se regenera un par ------------------------------------------------------------------------------


def assert_second_run_changes_nothing(run, keys_dir: Path) -> None:
    vault = FakeVault()
    run(vault, keys_dir)
    first = json.loads(json.dumps(vault.store))
    first_files = {p.name: p.read_bytes() for p in keys_dir.iterdir()}
    vault.writes.clear()
    second = run(vault, keys_dir)
    assert second == [] and vault.writes == [], f"la segunda corrida escribio {second}"
    assert vault.store == first, "la segunda corrida cambio la boveda"
    assert {p.name: p.read_bytes() for p in keys_dir.iterdir()} == first_files, "la segunda corrida cambio las llaves locales"


def test_a_second_run_changes_nothing(keys_dir: Path):
    assert_second_run_changes_nothing(seed, keys_dir)


def test_a_seed_that_regenerates_the_pairs_fails_the_idempotency_check(keys_dir: Path, monkeypatch):
    def regenerating(path, data, wants_private):
        key = ec.generate_private_key(ec.SECP256R1())
        result = dict(data)
        result["jwks"] = vp.jwks_text(key)
        if wants_private:
            result["private-key"] = vp.private_pem(key)
        return result

    monkeypatch.setattr(vp, "client_pair", regenerating)
    with pytest.raises(AssertionError, match="segunda corrida"):
        assert_second_run_changes_nothing(seed, keys_dir)


def test_existing_values_are_kept_and_only_the_missing_ones_are_added(keys_dir: Path):
    first = FakeVault()
    seed(first, keys_dir)
    vault = FakeVault({"identity/synthetic-users": {"SYNTH_CRO_1_PASSWORD": "Conservada123456"}, "identity/clients/channel": dict(first.store["identity/clients/channel"])})
    seed(vault, keys_dir)
    assert vault.store["identity/synthetic-users"]["SYNTH_CRO_1_PASSWORD"] == "Conservada123456"  # noqa: S105
    assert set(vault.store["identity/synthetic-users"]) == set(SYNTH_PROPERTIES)
    assert vault.store["identity/clients/channel"] == first.store["identity/clients/channel"]


def test_a_private_key_without_jwks_gets_the_jwks_derived_from_it_and_the_key_is_kept(keys_dir: Path):
    pem = vp.private_pem(ec.generate_private_key(ec.SECP256R1()))
    vault = FakeVault({"identity/clients/channel": {"private-key": pem}})
    seed(vault, keys_dir)
    data = vault.store["identity/clients/channel"]
    assert data["private-key"] == pem and data["jwks"] == vp.jwks_text(vp.load_private(pem))


def test_a_jwks_that_does_not_match_its_private_key_is_refused_not_rewritten(keys_dir: Path):
    other = vp.jwks_text(ec.generate_private_key(ec.SECP256R1()))
    pem = vp.private_pem(ec.generate_private_key(ec.SECP256R1()))
    vault = FakeVault({"identity/clients/channel": {"private-key": pem, "jwks": other}})
    with pytest.raises(RuntimeError, match="no corresponde"):
        seed(vault, keys_dir)
    assert vault.store["identity/clients/channel"] == {"private-key": pem, "jwks": other} and vault.writes == []


def test_a_jwks_without_a_private_key_is_refused_for_a_signing_client(keys_dir: Path):
    jwks = vp.jwks_text(ec.generate_private_key(ec.SECP256R1()))
    vault = FakeVault({"identity/clients/channel": {"jwks": jwks}})
    with pytest.raises(RuntimeError, match="sin `private-key`"):
        seed(vault, keys_dir)
    assert vault.store["identity/clients/channel"] == {"jwks": jwks}


def test_a_private_key_that_is_not_es256_is_refused(keys_dir: Path):
    from cryptography.hazmat.primitives.asymmetric import rsa

    rsa_pem = rsa.generate_private_key(65537, 2048).private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    with pytest.raises(ValueError, match="ES256"):
        seed(FakeVault({"identity/clients/channel": {"private-key": rsa_pem}}), keys_dir)


# --- usuarios sinteticos, administrador, break-glass, CA -----------------------------------------------------------------


def test_every_totp_seed_is_valid_base32_for_pyotp(seeded: FakeVault):
    seeds = {k: v for k, v in seeded.store["identity/synthetic-users"].items() if k.endswith("_TOTP_SEED")}
    assert len(seeds) == 10
    for name, value in seeds.items():
        assert re.fullmatch(r"[A-Z2-7]{32}", value), name
        assert base64.b32decode(value) and re.fullmatch(r"\d{6}", pyotp.TOTP(value).now()), name


def test_passwords_are_long_unique_and_safe_to_substitute_into_yaml(seeded: FakeVault):
    passwords = {k: v for k, v in seeded.store["identity/synthetic-users"].items() if k.endswith("_PASSWORD")}
    passwords["keycloak-admin"] = seeded.store["identity/keycloak-admin"]["password"]
    passwords["break-glass"] = seeded.store["identity/break-glass"]["BREAK_GLASS_PASSWORD"]
    assert len(passwords) == 12
    assert len(set(passwords.values())) == len(passwords)
    for name, value in passwords.items():
        assert re.fullmatch(r"[A-Za-z][A-Za-z0-9]{13,}", value), name  # >= 14 (politica del realm), empieza por letra, sin simbolos de YAML
        assert yaml.safe_load(f"value: {value}")["value"] == value


def test_the_admin_username_is_fixed_and_the_ca_is_the_clusters_certificate(seeded: FakeVault):
    assert seeded.store["identity/keycloak-admin"]["username"] == "admin"
    assert seeded.store["identity/ca"] == {"ca.crt": CA_PEM}
    assert "PRIVATE KEY" not in seeded.store["identity/ca"]["ca.crt"]


def test_valkey_values_are_random_and_present(seeded: FakeVault):
    assert seeded.store["edge/valkey"] and all(len(v) >= 32 for v in seeded.store["edge/valkey"].values())


def test_the_ca_is_read_from_the_cert_manager_secret_and_never_its_key():
    calls = []

    def run(command, stdin):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=base64.b64encode(CA_PEM.encode()).decode(), stderr="")

    assert vp.ca_from_cluster("kind-vectra", run)() == CA_PEM
    (command,) = calls
    assert command[:5] == ["kubectl", "--context", "kind-vectra", "get", "secret"] and "vectra-internal-ca" in command and "cert-manager" in command
    assert command[-1] == r"jsonpath={.data.tls\.crt}" and not any("tls.key" in part for part in command)


def test_the_ca_is_not_read_when_vault_already_has_it(keys_dir: Path):
    vault = FakeVault()
    seed(vault, keys_dir)
    vault.writes.clear()

    def must_not_be_called() -> str:
        raise AssertionError("se volvio a leer la CA del clúster")

    assert vp.seed_identity(vault, must_not_be_called, keys_dir)[0] == []


@pytest.mark.parametrize("stdout", ["", base64.b64encode(b"no es un certificado").decode()])
def test_a_missing_or_invalid_ca_stops_the_seed(stdout):
    run = lambda *_: SimpleNamespace(returncode=0, stdout=stdout, stderr="")  # noqa: E731
    with pytest.raises((RuntimeError, ValueError)):
        vp.ca_from_cluster("kind-vectra", run)()


# --- el directorio local para e2e y k6 -----------------------------------------------------------------------------------


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_local_files_have_restrictive_permissions(seeded: FakeVault, keys_dir: Path):
    assert mode(keys_dir) == 0o700
    files = sorted(keys_dir.iterdir())
    assert {p.name for p in files} == {*(f"{c}.pem" for c in SERVICE_CLIENTS), "ca.crt", "env"}
    assert all(mode(p) == 0o600 for p in files), {p.name: oct(mode(p)) for p in files}


def test_the_local_keys_are_the_vault_keys_in_the_format_the_tests_read(seeded: FakeVault, keys_dir: Path):
    for client in SERVICE_CLIENTS:
        assert (keys_dir / f"{client}.pem").read_text(encoding="utf-8") == seeded.store[f"identity/clients/{client}"]["private-key"]
    assert (keys_dir / "ca.crt").read_text(encoding="utf-8") == CA_PEM


def test_an_existing_loose_directory_is_tightened(tmp_path: Path):
    loose = tmp_path / "keys"
    loose.mkdir(mode=0o755)
    (loose / "channel.pem").write_text("viejo", encoding="utf-8")
    (loose / "channel.pem").chmod(0o644)
    seed(FakeVault(), loose)
    assert mode(loose) == 0o700 and mode(loose / "channel.pem") == 0o600


def test_the_env_file_exports_what_the_e2e_and_k6_suites_need(seeded: FakeVault, keys_dir: Path):
    command = f"source {keys_dir}/env && env"
    out = subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=True, env={"PATH": os.environ["PATH"]}).stdout
    got = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    assert got["VECTRA_E2E_CLIENT_KEYS_DIR"] == str(keys_dir) == got["K6_CLIENT_KEYS_DIR"]
    assert got["VECTRA_E2E_CA_BUNDLE"] == str(keys_dir / "ca.crt")
    assert got["VECTRA_E2E_BASE_URL"] == "https://vectra.localtest.me"
    assert got["VECTRA_E2E_ADMIN_USER"] == "admin" and got["VECTRA_E2E_ADMIN_PASSWORD"] == seeded.store["identity/keycloak-admin"]["password"]
    for name in SYNTH_PROPERTIES:
        assert got[name] == seeded.store["identity/synthetic-users"][name]


def test_the_keys_cannot_go_inside_the_repository():
    with pytest.raises(ValueError, match="dentro del repositorio"):
        vp.local_files(HERE / "llaves", {})


def test_the_e2e_support_reads_the_key_files_the_seed_writes(seeded: FakeVault, keys_dir: Path):
    """`service_token` abre `<VECTRA_E2E_CLIENT_KEYS_DIR>/<clientId>.pem` (e2e_support.py) y k6 `${K6_CLIENT_KEYS_DIR}/<client>.pem`."""
    load_js = (HERE.parents[1] / "identity-edge/tests/load/identity.js").read_text(encoding="utf-8")
    clients = re.search(r"const SERVICE_CLIENTS = \[(.*?)\];", load_js, re.DOTALL)
    assert clients
    for client in re.findall(r"'([\w-]+)'", clients.group(1)):
        assert (keys_dir / f"{client}.pem").is_file(), client
    for client in ("channel", "scoring-service"):  # los que usan las pruebas e2e
        assert (keys_dir / f"{client}.pem").is_file()


# --- sin secretos en la salida ----------------------------------------------------------------------------------------


def secret_values(vault: FakeVault) -> set[str]:
    return {value for data in vault.store.values() for value in data.values() if len(value) >= 8}


def test_no_secret_appears_in_the_standard_output_of_the_cli(keys_dir: Path, monkeypatch, capsys):
    vault = FakeVault()
    monkeypatch.setattr(vp, "Vault", lambda *_: vault)
    monkeypatch.setattr(vp, "ca_from_cluster", lambda *_: lambda: CA_PEM)
    assert vp.main(["vault_paths.py", "seed-identity", "kind-vectra", "root", str(keys_dir)]) == 0
    out = capsys.readouterr()
    assert out.out and secret_values(vault)
    for value in secret_values(vault):
        assert value not in out.out and value not in out.err
    assert "BEGIN" not in out.out + out.err and str(keys_dir / "env") in out.out
    assert "sembrada identity/clients/channel" in out.out


def test_the_cli_second_run_says_nothing_changes(keys_dir: Path, monkeypatch, capsys):
    vault = FakeVault()
    monkeypatch.setattr(vp, "Vault", lambda *_: vault)
    monkeypatch.setattr(vp, "ca_from_cluster", lambda *_: lambda: CA_PEM)
    vp.main(["vault_paths.py", "seed-identity", "kind-vectra", "root", str(keys_dir)])
    capsys.readouterr()
    vp.main(["vault_paths.py", "seed-identity", "kind-vectra", "root", str(keys_dir)])
    out = capsys.readouterr().out
    assert not [line for line in out.splitlines() if line.startswith("sembrada ")] and "nada cambia" in out


def test_vault_receives_the_values_by_stdin_only(keys_dir: Path):
    calls = []

    def run(command, stdin):
        calls.append((command, stdin))
        if "get" in command and "kv" in command:
            return SimpleNamespace(returncode=vp.NOT_FOUND, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    vp.seed_identity(vp.Vault("kind-vectra", "root", run), lambda: CA_PEM, keys_dir)
    puts = [(c, s) for c, s in calls if "put" in c]
    assert len(puts) == len(vp.listing()) - len([p for p in vp.listing() if not p.startswith(("identity/", "edge/"))])
    for command, stdin in puts:
        for value in json.loads(stdin).values():
            assert len(value) < 16 or value not in " ".join(command)  # "admin" (el usuario) no es un secreto


# --- el script, con un kubectl y un vault falsos ----------------------------------------------------------------------------

FAKE_KUBECTL = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_DIR/kubectl.log"
all="$*"
case "$all" in
  *"get crd"*) exit 1 ;;
  *"get secret vectra-internal-ca"*) base64 -w0 < "$FAKE_DIR/ca.pem" ;;
  *"kv get"*)
    path="${all##*secret/}"
    file="$FAKE_DIR/vault/$path.json"
    if [ -f "$file" ]; then printf '{"data":{"data":%s}}' "$(cat "$file")"; else exit 2; fi ;;
  *"kv put"*)
    path="${all##*secret/}"; path="${path% -}"
    mkdir -p "$(dirname "$FAKE_DIR/vault/$path")"
    cat > "$FAKE_DIR/vault/$path.json" ;;
esac
"""


def run_identity(tmp_path: Path, keys_dir: Path) -> subprocess.CompletedProcess[str]:
    fake = tmp_path / "bin"
    fake.mkdir(exist_ok=True)
    (fake / "kubectl").write_text(FAKE_KUBECTL, encoding="utf-8")
    (fake / "kubectl").chmod(0o755)
    (tmp_path / "ca.pem").write_text(CA_PEM, encoding="utf-8")
    uv = shutil.which("uv")
    assert uv
    env = {**os.environ, "PATH": f"{fake}:{Path(uv).parent}:/usr/bin:/bin", "FAKE_DIR": str(tmp_path), "VECTRA_E2E_KEYS_DIR": str(keys_dir)}
    return subprocess.run([str(SEED_VAULT), "identity"], env=env, capture_output=True, text=True, timeout=120, check=False)


def vault_files(tmp_path: Path) -> dict[str, bytes]:
    return {str(p.relative_to(tmp_path)): p.read_bytes() for p in sorted((tmp_path / "vault").rglob("*.json"))}


def test_the_script_seeds_identity_with_fakes_and_a_second_run_changes_nothing(tmp_path: Path, keys_dir: Path):
    first = run_identity(tmp_path, keys_dir)
    assert first.returncode == 0, first.stderr
    seeded = vault_files(tmp_path)
    assert "vault/identity/ca.json" in seeded and "vault/edge/valkey.json" in seeded and "vault/identity/clients/channel.json" in seeded
    assert not [name for name in seeded if "platform" in name or "postgres" in name]  # solo U2
    keys_before = {p.name: p.read_bytes() for p in keys_dir.iterdir()}
    second = run_identity(tmp_path, keys_dir)
    assert second.returncode == 0, second.stderr
    assert vault_files(tmp_path) == seeded
    assert {p.name: p.read_bytes() for p in keys_dir.iterdir()} == keys_before
    assert "nada cambia" in second.stdout and not [line for line in second.stdout.splitlines() if line.startswith("sembrada ")]
    for value in secret_values(SimpleNamespace(store={name: json.loads(raw) for name, raw in seeded.items()})):
        assert value not in first.stdout + first.stderr + second.stdout + second.stderr


def test_the_script_passes_values_by_stdin_not_by_argument(tmp_path: Path, keys_dir: Path):
    assert run_identity(tmp_path, keys_dir).returncode == 0
    log = (tmp_path / "kubectl.log").read_text(encoding="utf-8")
    seeded = vault_files(tmp_path)
    secrets_in_vault = secret_values(SimpleNamespace(store={name: json.loads(raw) for name, raw in seeded.items()}))
    assert secrets_in_vault and not [v for v in secrets_in_vault if v in log]
    assert "tls.key" not in log


def test_the_script_refuses_a_context_that_is_not_kind_in_identity_mode(tmp_path: Path):
    (tmp_path / "kubectl").write_text(f'#!/bin/sh\ntouch "{tmp_path}/llamado"\n', encoding="utf-8")
    (tmp_path / "kubectl").chmod(0o755)
    result = subprocess.run([str(SEED_VAULT), "identity"], env={"PATH": f"{tmp_path}:/usr/bin:/bin", "VECTRA_KIND_CONTEXT": "produccion"}, capture_output=True, text=True, check=False)
    assert result.returncode == 2 and not (tmp_path / "llamado").exists()
