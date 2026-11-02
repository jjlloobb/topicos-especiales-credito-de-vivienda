"""La siembra de Vault en kind cubre todo lo que piden los ExternalSecret (INF-U1-10)."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import vault_paths as vp  # noqa: E402

PLATFORM = HERE.parent
#: El script bajo prueba; SEED_VAULT_SCRIPT permite apuntar a una copia anterior para ver la prueba en rojo.
SEED_VAULT = Path(os.environ.get("SEED_VAULT_SCRIPT", HERE / "seed-vault.sh"))
#: Lo que no se instala como manifiesto propio o no contiene manifiestos reales.
IGNORED = {"rendered", ".charts", ".tools", "fixtures", "tests", "templates"}


@pytest.fixture(scope="module")
def documents():
    return vp.all_external_secrets()


@pytest.fixture(scope="module")
def refs(documents):
    return vp.collect(documents)


def test_every_manifest_with_an_external_secret_is_a_source():
    declared = {p for p in PLATFORM.rglob("*.yaml") if not IGNORED & set(p.parts) and re.search(r"^kind:\s*ExternalSecret\s*$", p.read_text(encoding="utf-8"), flags=re.M)}
    assert declared <= set(vp.SOURCES), declared - set(vp.SOURCES)


def test_the_chart_templates_are_rendered_and_cover_expected_paths(refs):
    for path, prop in [
        ("postgres/roles/registry_migrator", "password"),
        ("postgres/roles/keycloak", "username"),
        ("postgres/backup", "secretKey"),
        ("minio/root", "password"),
        ("minio/loki", "accessKey"),
        ("minio/governance", "secretKey"),
        ("minio/model-archive", "secretKey"),
        ("minio/engineer-upload", "secretKey"),
        ("minio/registry-checkpoint", "secretKey"),
        ("minio/registry-archive", "secretKey"),
        ("minio/registry-verify", "secretKey"),
        ("backups/restore-readonly", "secret_access_key"),
        ("backups/restore-readonly", "access_key_id"),
        ("grafana/admin", "password"),
        ("grafana/folder-permissions", "token"),
        ("alertmanager/relay", "url"),
    ]:
        assert prop in refs[path], (path, prop)


def test_plan_gives_every_property_a_value(documents, refs):
    planned = vp.plan(refs, vp.minio_users(documents), lambda _: {})
    for path, properties in refs.items():
        for prop in properties:
            assert planned[path][prop], (path, prop)


def test_pg_role_username_is_the_role(documents, refs):
    planned = vp.plan(refs, vp.minio_users(documents), lambda _: {})
    for path, data in planned.items():
        if path.startswith("postgres/roles/"):
            assert data["username"] == path.rsplit("/", 1)[1]


def test_each_minio_user_has_its_secret_in_vectra_data_and_its_access_key_seeded(documents, refs):
    values = yaml.safe_load(vp.MINIO_VALUES.read_text(encoding="utf-8"))
    planned = vp.plan(refs, vp.minio_users(documents), lambda _: {})
    in_data = {d["metadata"]["name"]: d for d in documents if d["metadata"]["namespace"] == "vectra-data"}
    for user in values["users"]:
        source = in_data[user["existingSecret"]]
        keys = {item["secretKey"]: item["remoteRef"] for item in source["spec"]["data"]}
        assert user["existingSecretKey"] in keys, user
        path = keys[user["existingSecretKey"]]["key"]
        for prop in vp.ACCESS_KEY_PROPERTIES & set(planned[path]):
            assert planned[path][prop] == user["accessKey"], user


def test_every_minio_user_of_the_base_values_is_also_in_kind():
    base = yaml.safe_load((PLATFORM / "data/minio/values.yaml").read_text(encoding="utf-8"))
    kind = yaml.safe_load(vp.MINIO_VALUES.read_text(encoding="utf-8"))
    assert {u["accessKey"] for u in base["users"]} <= {u["accessKey"] for u in kind["users"]}
    assert {p["name"] for p in base["policies"]} <= {p["name"] for p in kind["policies"]}
    assert {b["name"] for b in base["buckets"]} | {"vectra-backups"} <= {b["name"] for b in kind["buckets"]}


def test_every_generated_secret_is_different(documents, refs):
    planned = vp.plan(refs, vp.minio_users(documents), lambda _: {})
    generated = [v for path, data in planned.items() for prop, v in data.items() if vp.fixed_value(path, prop, vp.minio_users(documents)) is None and v != vp.TOKEN_PENDING]
    assert len(generated) == len(set(generated))
    assert all(re.fullmatch(r"[0-9a-f]{48}", v) for v in generated)


def test_existing_values_survive_a_second_seed():
    refs = {"minio/x": {"secretKey", "accessKey"}, "grafana/folder-permissions": {"token"}}
    current = {"minio/x": {"secretKey": "ya", "accessKey": "otro"}, "grafana/folder-permissions": {"token": "real"}}
    planned = vp.plan(refs, {"minio/x": "usuario"}, lambda path: current[path])
    assert planned["minio/x"] == {"secretKey": "ya", "accessKey": "usuario"}
    assert planned["grafana/folder-permissions"] == {"token": "real"}


def test_grafana_token_starts_as_a_visible_placeholder():
    assert vp.plan({"grafana/folder-permissions": {"token"}}, {}, lambda _: {})["grafana/folder-permissions"]["token"] == vp.TOKEN_PENDING


def test_data_from_is_rejected():
    with pytest.raises(ValueError, match="dataFrom"):
        vp.collect([{"metadata": {"name": "x"}, "spec": {"dataFrom": [{}]}}])


def test_vault_values_go_through_stdin_and_never_on_the_command_line():
    calls = []

    def run(command, stdin):
        calls.append((command, stdin))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    vp.Vault("kind-vectra", "t", run).write("minio/x", {"secretKey": "valor-secreto"})
    command, stdin = calls[0]
    assert "valor-secreto" not in " ".join(command) and json.loads(stdin) == {"secretKey": "valor-secreto"}
    assert command[:3] == ["kubectl", "--context", "kind-vectra"] and command[-2:] == ["secret/minio/x", "-"]


def test_vault_read_distinguishes_missing_from_error():
    missing = vp.Vault("c", "t", lambda *_: SimpleNamespace(returncode=vp.NOT_FOUND, stdout="", stderr=""))
    assert missing.read("x") == {}
    found = vp.Vault("c", "t", lambda *_: SimpleNamespace(returncode=0, stdout='{"data":{"data":{"a":"b"}}}', stderr=""))
    assert found.read("x") == {"a": "b"}
    broken = vp.Vault("c", "t", lambda *_: SimpleNamespace(returncode=1, stdout="", stderr="sin conexion"))
    with pytest.raises(RuntimeError, match="sin conexion"):
        broken.read("x")


def test_seed_writes_every_path_once():
    written = {}

    class Fake:
        def read(self, path):
            return {}

        def write(self, path, data):
            written[path] = data

    done = vp.seed(Fake())
    assert set(done) == set(written) == set(vp.collect(vp.all_external_secrets()))


def test_script_refuses_a_context_that_is_not_kind(tmp_path):
    tool = tmp_path / "kubectl"
    tool.write_text(f'#!/bin/sh\ntouch "{tmp_path}/llamado"\n', encoding="utf-8")
    tool.chmod(0o755)
    result = subprocess.run(
        [str(HERE / "seed-vault.sh")],
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "VECTRA_KIND_CONTEXT": "produccion"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert not (tmp_path / "llamado").exists()


KUBECTL = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_DIR/kubectl.log"
case "$*" in
  *"get secret grafana-admin"*) printf 'clave-admin' | base64 ;;
  *"port-forward"*)
    trap 'echo terminated >> "$FAKE_DIR/forward.log"; kill "$child" 2>/dev/null; exit 0' TERM
    sleep 60 >/dev/null 2>&1 & child=$!
    echo $$ > "$FAKE_DIR/forward.pid"
    echo started >> "$FAKE_DIR/forward.log"
    wait "$child" ;;
  *" exec "*) cat > "$FAKE_DIR/vault-stdin" ;;
  *"get externalsecret "*) [ -n "$FAKE_EXTERNAL_SECRET" ] ;;
esac
"""

CURL = r"""#!/usr/bin/env bash
case "$*" in
  *"/api/health"*) ;;
  *"serviceaccounts/search"*) echo '{"serviceAccounts":[]}' ;;
  *"/tokens"*) [ -n "$FAKE_TOKEN_FAILS" ] && exit 22; echo '{"key":"glsa-falso"}' ;;
  *"/api/serviceaccounts"*) echo '{"id":7}' ;;
esac
"""


@pytest.fixture
def fakes(tmp_path):
    """Carpeta de los falsos; al terminar, aunque la prueba falle, mata el port-forward falso y su `sleep`."""
    yield tmp_path
    pid_file = tmp_path / "forward.pid"
    if pid_file.exists():
        pid = pid_file.read_text(encoding="utf-8").strip()
        subprocess.run(["pkill", "-P", pid], check=False)
        subprocess.run(["kill", pid], check=False, stderr=subprocess.DEVNULL)


def run_grafana_token(tmp_path, external_secret, token_fails=False):
    """Corre `seed-vault.sh grafana-token` con kubectl y curl falsos y devuelve su código de salida y su stderr."""
    for name, body in (("kubectl", KUBECTL), ("curl", CURL)):
        tool = tmp_path / name
        tool.write_text(body, encoding="utf-8")
        tool.chmod(0o755)
    # stderr va a un archivo: un port-forward que sobreviva al script heredaria la tuberia y colgaria la lectura.
    with (tmp_path / "stderr").open("w", encoding="utf-8") as stderr:
        result = subprocess.run(
            [str(SEED_VAULT), "grafana-token"],
            env={"PATH": f"{tmp_path}:/usr/bin:/bin", "FAKE_DIR": str(tmp_path), "FAKE_EXTERNAL_SECRET": "si" if external_secret else "", "FAKE_TOKEN_FAILS": "si" if token_fails else ""},
            stdout=subprocess.DEVNULL,
            stderr=stderr,
            timeout=30,
            check=False,
        )
    return SimpleNamespace(returncode=result.returncode, stderr=(tmp_path / "stderr").read_text(encoding="utf-8"))


def forward_events(directory):
    """Espera (hasta 10 s) a que el port-forward falso registre `terminated` y devuelve sus eventos."""
    forward = directory / "forward.log"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "terminated" not in (forward.read_text(encoding="utf-8") if forward.exists() else ""):
        time.sleep(0.1)
    return forward.read_text(encoding="utf-8").split() if forward.exists() else []


def test_grafana_token_without_external_secret(fakes):
    result = run_grafana_token(fakes, external_secret=False)
    assert result.returncode == 0, result.stderr
    log = (fakes / "kubectl.log").read_text(encoding="utf-8")
    assert "get externalsecret grafana-folder-permissions-token" in log
    assert "annotate" not in log
    assert json.loads((fakes / "vault-stdin").read_text(encoding="utf-8")) == {"token": "glsa-falso"}


def test_grafana_token_annotates_when_external_secret_exists(fakes):
    result = run_grafana_token(fakes, external_secret=True)
    assert result.returncode == 0, result.stderr
    assert "annotate externalsecret grafana-folder-permissions-token" in (fakes / "kubectl.log").read_text(encoding="utf-8")


def test_grafana_token_stops_port_forward(fakes):
    result = run_grafana_token(fakes, external_secret=False)
    assert "unbound variable" not in result.stderr, result.stderr
    assert forward_events(fakes) == ["started", "terminated"]


def test_grafana_token_kills_port_forward_on_error(fakes):
    result = run_grafana_token(fakes, external_secret=False, token_fails=True)
    assert result.returncode != 0
    assert forward_events(fakes) == ["started", "terminated"]



def k11(path):
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def test_k11_lets_eso_read_only_the_vault_token_in_kind():
    documents = k11(PLATFORM / "secrets/eso-rbac-k11-kind.yaml")
    role = next(d for d in documents if d["kind"] == "Role" and d["metadata"]["namespace"] == "external-secrets")
    assert role["rules"] == [{"apiGroups": [""], "resources": ["secrets"], "resourceNames": ["vault-token"], "verbs": ["get"]}]


@pytest.mark.parametrize("env", ["kind", "staging"])
def test_k11_covers_the_mock_namespace_outside_prod(env):
    documents = k11(PLATFORM / f"secrets/eso-rbac-k11-{env}.yaml")
    assert {d["kind"] for d in documents if d["metadata"]["namespace"] == "vectra-mock"} == {"Role", "RoleBinding"}


def test_prod_has_no_mock_namespace_grant():
    assert not (PLATFORM / "secrets/eso-rbac-k11-prod.yaml").exists()
    assert "vectra-mock" not in (PLATFORM / "secrets/eso-rbac-k11.yaml").read_text(encoding="utf-8")
