"""U01-T17: `readonly-kubeconfig.sh` escribe un kubeconfig de solo lectura (0600, un contexto, fuera del repositorio) y lo comprueba con `can-i`.

Ninguna prueba toca un cluster: el unico `kubectl` que existe es el falso, en un directorio que es TODO el PATH del guion (mas enlaces a binarios inofensivos),
y el entorno se construye desde cero, sin `os.environ`. El falso deja constancia (`unexpected`) si se le llama con un verbo que el guion no debe usar.
"""

import base64
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
SCRIPT = HERE / "readonly-kubeconfig.sh"
TOKEN = "fake-token-not-a-real-credential"  # noqa: S105 - valor de mentira
TOKEN_B64 = base64.b64encode(TOKEN.encode()).decode()
CA_B64 = base64.b64encode(b"fake-ca-not-a-real-certificate").decode()
HARMLESS = ["bash", "base64", "mktemp", "mv", "chmod", "stat", "dirname", "mkdir", "realpath", "tr", "head"]

KUBECTL = r"""#!/usr/bin/env bash
echo "kubectl $*" >> "$FAKE_DIR/calls.log"
args=("$@")
while [ "${args[0]:-}" = "--kubeconfig" ] || [ "${args[0]:-}" = "--context" ]; do args=("${args[@]:2}"); done
case "${args[0]:-} ${args[1]:-}" in
  "config view")
    [ "$FAKE_KUBECTL_FAILS" = si ] && { echo "error: no configuration" >&2; exit 1; }
    printf '%s' "$FAKE_SERVER" ;;
  "config get-contexts") printf '%s\n' "$FAKE_CONTEXTS" ;;
  "get secret")
    [ "$FAKE_KUBECTL_FAILS" = si ] && { echo 'Error from server (Forbidden): secrets "x" is forbidden' >&2; exit 1; }
    case "$*" in
      *'.data.token'*) printf '%s' "$FAKE_TOKEN_B64" ;;
      *'ca\.crt'*) printf '%s' "$FAKE_CA_B64" ;;
    esac ;;
  "auth can-i")
    [ "$FAKE_KUBECTL_FAILS" = si ] && { echo "Unable to connect to the server" >&2; exit 1; }
    verb="${args[2]}"; resource="${args[3]}"
    answer=no
    case "$verb" in get|list|watch) answer=yes ;; esac
    case "$resource" in secrets|pods/exec|pods/portforward|pods/attach|'*') answer=no ;; esac
    for override in $FAKE_OVERRIDES; do
      [ "${override%%=*}" = "$verb:$resource" ] && answer="${override##*=}"
    done
    echo "$answer"
    [ "$answer" = yes ] ;;
  *) echo "$*" >> "$FAKE_DIR/unexpected"; echo "kubectl falso: orden inesperada: $*" >&2; exit 9 ;;
esac
"""


def environment(tmp_path: Path, **extra: str) -> dict[str, str]:
    fake = tmp_path / "bin"
    fake.mkdir(exist_ok=True)
    (fake / "kubectl").write_text(KUBECTL, encoding="utf-8")
    (fake / "kubectl").chmod(0o755)
    for name in HARMLESS:
        link = fake / name
        if not link.exists():
            link.symlink_to(shutil.which(name) or f"/usr/bin/{name}")
    (tmp_path / "home").mkdir(exist_ok=True)
    env = {
        "PATH": str(fake), "HOME": str(tmp_path / "home"), "FAKE_DIR": str(tmp_path), "FAKE_SERVER": "https://127.0.0.1:6443", "FAKE_CONTEXTS": "kind-vectra",
        "FAKE_TOKEN_B64": TOKEN_B64, "FAKE_CA_B64": CA_B64, "FAKE_KUBECTL_FAILS": "no", "FAKE_OVERRIDES": "",
    }  # fmt: skip
    return {**env, **extra}


def run(tmp_path: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(SCRIPT), *args], env=environment(tmp_path, **extra), capture_output=True, text=True, timeout=60, check=False)
    assert not (tmp_path / "unexpected").exists(), (tmp_path / "unexpected").read_text(encoding="utf-8")  # el falso vio un verbo que el guion no debe usar
    return result


def calls(tmp_path: Path) -> list[str]:
    path = tmp_path / "calls.log"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def written(tmp_path: Path) -> Path:
    return tmp_path / "out" / "kubeconfig"


def test_readonly_kubeconfig_write_makes_a_0600_single_context_file_outside_the_repo(tmp_path: Path):
    target = written(tmp_path)
    result = run(tmp_path, "write", str(target))
    assert result.returncode == 0, result.stdout + result.stderr
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    config = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert [c["name"] for c in config["contexts"]] == ["kind-vectra"] and config["current-context"] == "kind-vectra"
    assert config["users"][0]["user"]["token"] == TOKEN
    assert config["clusters"][0]["cluster"] == {"server": "https://127.0.0.1:6443", "certificate-authority-data": CA_B64}
    assert REPO not in target.resolve().parents
    assert [p.name for p in target.parent.iterdir()] == ["kubeconfig"]  # sin temporales


def test_readonly_kubeconfig_write_never_prints_the_token(tmp_path: Path):
    result = run(tmp_path, "write", str(written(tmp_path)))
    for secret in (TOKEN, TOKEN_B64):
        assert secret not in result.stdout + result.stderr
    assert "--token" not in " ".join(calls(tmp_path))  # ni en los argumentos de un proceso
    assert "--token" not in SCRIPT.read_text(encoding="utf-8")


def test_readonly_kubeconfig_write_only_reads_with_the_admin_context(tmp_path: Path):
    run(tmp_path, "write", str(written(tmp_path)))
    assert calls(tmp_path) == [
        "kubectl --context kind-vectra config view --minify --raw -o jsonpath={.clusters[0].cluster.server}",
        "kubectl --context kind-vectra get secret vectra-readonly-agent-token -n argocd -o jsonpath={.data.token}",
        "kubectl --context kind-vectra get secret vectra-readonly-agent-token -n argocd -o jsonpath={.data.ca\\.crt}",
    ]


def test_readonly_kubeconfig_write_default_path_is_under_home_kube(tmp_path: Path):
    result = run(tmp_path, "write")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "home/.kube/kind-vectra-readonly").is_file()


def test_readonly_kubeconfig_write_refuses_a_path_inside_the_repository(tmp_path: Path):
    inside = REPO / "vectra-risk" / "u01t17-must-not-exist.kubeconfig"
    result = run(tmp_path, "write", str(inside))
    assert result.returncode == 2 and not inside.exists()
    assert "repositorio" in result.stderr and calls(tmp_path) == []
    dotted = run(tmp_path, "write", str(REPO / "vectra-risk" / ".." / "u01t17-must-not-exist.kubeconfig"))
    assert dotted.returncode == 2 and not (REPO / "u01t17-must-not-exist.kubeconfig").exists()


def test_readonly_kubeconfig_refuses_a_context_that_is_not_kind(tmp_path: Path):
    for command in ("write", "check"):
        result = run(tmp_path, command, str(written(tmp_path)), VECTRA_KIND_CONTEXT="produccion")
        assert result.returncode == 2 and "kind" in result.stderr
    assert calls(tmp_path) == []


def test_readonly_kubeconfig_write_says_so_when_kubectl_fails_and_leaves_no_file(tmp_path: Path):
    result = run(tmp_path, "write", str(written(tmp_path)), FAKE_KUBECTL_FAILS="si")
    assert result.returncode == 5 and not written(tmp_path).exists()


def test_readonly_kubeconfig_write_without_a_token_yet_exits_4_and_leaves_no_file(tmp_path: Path):
    result = run(tmp_path, "write", str(written(tmp_path)), FAKE_TOKEN_B64="")
    assert result.returncode == 4 and not written(tmp_path).exists()
    assert "readonly-agent-rbac-kind" in result.stderr


@pytest.fixture
def good_file(tmp_path: Path) -> Path:
    assert run(tmp_path, "write", str(written(tmp_path))).returncode == 0
    (tmp_path / "calls.log").unlink()
    return written(tmp_path)


def test_readonly_kubeconfig_check_passes_when_every_row_is_as_expected(tmp_path: Path, good_file: Path):
    result = run(tmp_path, "check", str(good_file))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout and "esperado" in result.stdout  # imprime la tabla
    assert TOKEN not in result.stdout + result.stderr


def test_readonly_kubeconfig_check_never_asks_anything_but_can_i_and_contexts(tmp_path: Path, good_file: Path):
    run(tmp_path, "check", str(good_file))
    for line in calls(tmp_path):
        assert line.startswith(f"kubectl --kubeconfig {good_file} ")
        assert " auth can-i " in line or line.endswith(" config get-contexts -o name")
        assert "--context kind-vectra" in line or "get-contexts" in line


def test_readonly_kubeconfig_check_table_has_the_minimum_rows(tmp_path: Path, good_file: Path):
    """Quitar una fila de la tabla del guion hace fallar esta prueba."""
    run(tmp_path, "check", str(good_file))
    asked = {line.split(" auth can-i ")[1] for line in calls(tmp_path) if " auth can-i " in line}
    must_say_no = ["get secrets", "delete deployments", "create pods", "patch deployments", "create pods/exec", "create pods/portforward", "delete *", "impersonate users"]
    must_say_yes = ["get pods", "list deployments", "get pods/log", "list applications.argoproj.io", "list externalsecrets.external-secrets.io"]
    for scope in ("-n vectra-app", "-n vectra-edge", "-n vectra-data", "-A"):
        for row in [*must_say_no, *must_say_yes]:
            assert f"{row} {scope}" in asked, (row, scope)
    assert "get nodes -A" in asked


@pytest.mark.parametrize(("override", "row"), [("delete:deployments=yes", "delete deployments"), ("get:pods=no", "get pods"), ("get:secrets=yes", "get secrets"), ("create:pods/exec=yes", "create pods/exec")])
def test_readonly_kubeconfig_check_one_wrong_row_fails_and_names_it(tmp_path: Path, good_file: Path, override: str, row: str):
    result = run(tmp_path, "check", str(good_file), FAKE_OVERRIDES=override)
    assert result.returncode == 1, result.stdout + result.stderr
    verb, resource = row.split(" ")
    assert f"can-i {verb} {resource} (" in result.stderr and "FALLA" in result.stdout


def test_readonly_kubeconfig_check_without_answers_is_not_a_pass(tmp_path: Path, good_file: Path):
    result = run(tmp_path, "check", str(good_file), FAKE_KUBECTL_FAILS="si")
    assert result.returncode == 3 and "OK:" not in result.stdout


def test_readonly_kubeconfig_check_refuses_a_missing_loose_or_multi_context_file(tmp_path: Path, good_file: Path):
    assert run(tmp_path, "check", str(tmp_path / "nope")).returncode == 2
    good_file.chmod(0o644)
    loose = run(tmp_path, "check", str(good_file))
    assert loose.returncode == 2 and "600" in loose.stderr
    good_file.chmod(0o600)
    two = run(tmp_path, "check", str(good_file), FAKE_CONTEXTS="kind-vectra\nkind-admin")
    assert two.returncode == 2 and "un solo contexto" in two.stderr


def test_readonly_kubeconfig_the_fake_records_any_verb_the_script_must_not_use(tmp_path: Path):
    """La red de seguridad funciona: un `kubectl delete` del guion dejaria constancia y `run` fallaria."""
    env = environment(tmp_path)
    subprocess.run([str(tmp_path / "bin/kubectl"), "delete", "-f", "x.yaml"], env=env, capture_output=True, text=True, check=False)
    assert (tmp_path / "unexpected").read_text(encoding="utf-8").strip() == "delete -f x.yaml"


def test_readonly_kubeconfig_tests_never_inherit_the_real_environment(tmp_path: Path):
    env = environment(tmp_path)
    assert set(env) <= {"PATH", "HOME", "FAKE_DIR", "FAKE_SERVER", "FAKE_CONTEXTS", "FAKE_TOKEN_B64", "FAKE_CA_B64", "FAKE_KUBECTL_FAILS", "FAKE_OVERRIDES"}
    assert "KUBECONFIG" not in env and os.pathsep not in env["PATH"]
    assert sorted(p.name for p in (tmp_path / "bin").iterdir()) == sorted(["kubectl", *HARMLESS])
