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
HARMLESS = ["bash", "base64", "mktemp", "mv", "chmod", "stat", "dirname", "mkdir", "realpath", "tr", "head", "rm"]

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
    # Como el kubectl real: un posicional `a/b` es TIPO/NOMBRE (se contesta por `a`, sin mirar `b`); el subrecurso solo llega con --subresource.
    positional=(); subresource=""; scope=cluster; rest=("${args[@]:2}")
    while [ "${#rest[@]}" -gt 0 ]; do
      case "${rest[0]}" in
        --subresource=*) subresource="${rest[0]#--subresource=}" ;;
        --subresource) subresource="${rest[1]:-}"; rest=("${rest[@]:1}") ;;
        -n) scope="${rest[1]:-}"; rest=("${rest[@]:1}") ;;
        -*) ;;
        *) positional+=("${rest[0]}") ;;
      esac
      rest=("${rest[@]:1}")
    done
    verb="${positional[0]}"; resource="${positional[1]%%/*}"
    [ -z "$subresource" ] || resource="$resource/$subresource"
    answer=no
    case "$verb" in get|list|watch) answer=yes ;; esac
    case "$resource" in secrets|pods/exec|pods/portforward|pods/attach|nodes/proxy|pods/proxy|services/proxy|nodes/log|'*') answer=no ;; esac
    for override in $FAKE_OVERRIDES; do
      # `verbo:recurso=respuesta` vale en todos los ambitos; `verbo:recurso@ambito=respuesta` solo en ese (`cluster` es -A)
      { [ "${override%%=*}" = "$verb:$resource" ] || [ "${override%%=*}" = "$verb:$resource@$scope" ]; } && answer="${override##*=}"
    done
    if [ "$answer" = no ] && [ "$FAKE_REASON" = si ]; then echo "no - RBAC: denied"; else echo "$answer"; fi
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
        "FAKE_TOKEN_B64": TOKEN_B64, "FAKE_CA_B64": CA_B64, "FAKE_KUBECTL_FAILS": "no", "FAKE_OVERRIDES": "", "FAKE_REASON": "no",
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


def asked_rows(tmp_path: Path) -> set[tuple[str, str, str]]:
    """(verbo, recurso con la forma `recurso/subrecurso`, ambito) de cada `auth can-i` que hizo el guion, leidas de los argumentos reales."""
    rows = set()
    for line in calls(tmp_path):
        if " auth can-i " not in line:
            continue
        words = line.split(" auth can-i ")[1].split()
        verb, resource, *rest = words
        sub = next((w.split("=", 1)[1] for w in rest if w.startswith("--subresource=")), "")
        scope = "cluster" if "-A" in rest else rest[rest.index("-n") + 1]
        rows.add((verb, f"{resource}/{sub}" if sub else resource, scope))
    return rows


# La tabla EXACTA que `check` debe preguntar y la respuesta que espera: (esperado, verbo, recurso con la forma `recurso/subrecurso`). Cambiar o quitar una fila del guion la hace fallar.
EXPECTED_ROWS = [
    ("yes", "get", "pods"), ("yes", "list", "deployments"), ("yes", "get", "pods/log"), ("yes", "list", "applications.argoproj.io"), ("yes", "list", "externalsecrets.external-secrets.io"),
    ("no", "get", "secrets"), ("no", "list", "secrets"), ("no", "delete", "deployments"), ("no", "delete", "pods"), ("no", "delete", "*"), ("no", "create", "pods"),
    ("no", "create", "deployments"), ("no", "patch", "deployments"), ("no", "update", "deployments"), ("no", "create", "pods/exec"), ("no", "create", "pods/portforward"),
    ("no", "create", "pods/attach"), ("no", "impersonate", "users"), ("no", "get", "nodes/proxy"), ("no", "get", "pods/proxy"), ("no", "get", "services/proxy"),
    ("no", "get", "nodes/log"), ("no", "create", "serviceaccounts/token"), ("no", "escalate", "clusterroles"), ("no", "bind", "clusterroles"),
]  # fmt: skip
NAMESPACES = ("vectra-app", "vectra-edge", "vectra-data")
# Filas que solo se preguntan en `cluster` (sus peticiones reales van sin namespace). `bind clusterroles` NO: una RoleBinding la concede en su namespace.
CLUSTER_ONLY = {("get", "nodes/proxy"), ("get", "nodes/log"), ("escalate", "clusterroles")}


def exact_table() -> set[tuple[str, str, str, str]]:
    table = {(expected, scope, verb, resource) for scope in (*NAMESPACES, "cluster") for expected, verb, resource in EXPECTED_ROWS if scope == "cluster" or (verb, resource) not in CLUSTER_ONLY}
    return {*table, ("yes", "cluster", "get", "nodes")}


def test_readonly_kubeconfig_check_table_is_exactly_the_expected_rows(tmp_path: Path, good_file: Path):
    """Quitar, cambiar o sustituir una fila del guion (incluida su respuesta esperada) hace fallar esta prueba: se compara con el conjunto exacto."""
    result = run(tmp_path, "check", str(good_file))
    printed = set()
    for line in result.stdout.splitlines():
        words = line.split()
        if len(words) == 6 and words[5] == "ok":
            printed.add((words[0], words[2], words[3], words[4]))
    expected = exact_table()
    assert len(expected) == 92
    assert printed == expected, (sorted(expected - printed), sorted(printed - expected))
    assert asked_rows(tmp_path) == {(verb, resource, scope) for _, scope, verb, resource in expected}


def test_readonly_kubeconfig_check_sees_bind_clusterroles_granted_by_a_rolebinding_in_a_namespace(tmp_path: Path, good_file: Path):
    """F-01: una RoleBinding a un ClusterRole concede `bind` solo en su namespace; con `-A` no se ve. Un `yes` solo con `-n vectra-app` debe dar rojo."""
    result = run(tmp_path, "check", str(good_file), FAKE_OVERRIDES="bind:clusterroles@vectra-app=yes")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "can-i bind clusterroles (vectra-app)" in result.stderr
    assert "Filas: 92; distintas de lo esperado: 1" in result.stdout


def test_readonly_kubeconfig_check_asks_for_subresources_with_the_flag_never_as_one_argument(tmp_path: Path, good_file: Path):
    """`kubectl auth can-i get pods/proxy` es TIPO/NOMBRE (el pod llamado `proxy`), no el subrecurso: ninguna llamada lleva una barra en el recurso."""
    run(tmp_path, "check", str(good_file))
    lines = [line.split(" auth can-i ")[1] for line in calls(tmp_path) if " auth can-i " in line]
    assert lines
    for line in lines:
        verb, resource, *_ = line.split()
        assert "/" not in resource, line
    assert "get pods --subresource=proxy -n vectra-app" in lines
    assert "get nodes --subresource=proxy -A" in lines
    assert "create pods --subresource=exec -n vectra-data" in lines
    assert "get pods --subresource=log -n vectra-edge" in lines


def test_readonly_kubeconfig_the_fake_answers_a_slash_as_type_name_like_the_real_kubectl(tmp_path: Path):
    """El falso es fiel en lo que importa: `pods/proxy` posicional contesta por `pods`; `--subresource` si mira el subrecurso."""
    env = environment(tmp_path)

    def ask(*words: str) -> str:
        return subprocess.run([str(tmp_path / "bin/kubectl"), "auth", "can-i", *words], env=env, capture_output=True, text=True, check=False).stdout.strip()

    assert ask("get", "pods/proxy", "-n", "x") == "yes"
    assert ask("get", "pods", "--subresource=proxy", "-n", "x") == "no"
    assert ask("get", "pods", "--subresource", "proxy") == "no"
    assert ask("get", "pods", "--subresource=log") == "yes"


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
    assert set(env) <= {"PATH", "HOME", "FAKE_DIR", "FAKE_SERVER", "FAKE_CONTEXTS", "FAKE_TOKEN_B64", "FAKE_CA_B64", "FAKE_KUBECTL_FAILS", "FAKE_OVERRIDES", "FAKE_REASON"}
    assert "KUBECONFIG" not in env and os.pathsep not in env["PATH"]
    assert sorted(p.name for p in (tmp_path / "bin").iterdir()) == sorted(["kubectl", *HARMLESS])


def test_readonly_kubeconfig_check_takes_the_first_word_of_a_no_with_a_reason(tmp_path: Path, good_file: Path):
    """F-04: `kubectl auth can-i` imprime `no - <motivo>` cuando el SAR trae `reason`: sigue siendo un no."""
    result = run(tmp_path, "check", str(good_file), FAKE_REASON="si")
    assert result.returncode == 0, result.stdout + result.stderr
    wrong = run(tmp_path, "check", str(good_file), FAKE_REASON="si", FAKE_OVERRIDES="get:pods=no")
    assert wrong.returncode == 1 and "can-i get pods (" in wrong.stderr


def test_readonly_kubeconfig_write_leaves_no_temporary_file_when_it_is_cut_short(tmp_path: Path):
    """F-05: si `mv` falla (o el proceso muere) despues de `mktemp`, el temporal con el token no queda."""
    env = environment(tmp_path)
    (tmp_path / "bin/mv").unlink()
    (tmp_path / "bin/mv").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (tmp_path / "bin/mv").chmod(0o755)
    result = subprocess.run([str(SCRIPT), "write", str(written(tmp_path))], env=env, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode != 0 and list(written(tmp_path).parent.iterdir()) == []


def test_readonly_kubeconfig_write_refuses_the_admin_kubeconfig(tmp_path: Path):
    admin = tmp_path / "home/.kube/config"
    admin.parent.mkdir(parents=True)
    admin.write_text("admin\n", encoding="utf-8")
    by_default = run(tmp_path, "write", str(admin))
    assert by_default.returncode == 2 and admin.read_text(encoding="utf-8") == "admin\n"
    elsewhere = tmp_path / "elsewhere/admin-kubeconfig"
    elsewhere.parent.mkdir()
    elsewhere.write_text("admin\n", encoding="utf-8")
    from_env = run(tmp_path, "write", str(elsewhere), KUBECONFIG=f"{tmp_path}/otro:{elsewhere}")
    assert from_env.returncode == 2 and elsewhere.read_text(encoding="utf-8") == "admin\n" and "administrador" in from_env.stderr


def test_readonly_kubeconfig_write_only_overwrites_a_file_it_wrote_itself(tmp_path: Path):
    stranger = written(tmp_path)
    stranger.parent.mkdir()
    stranger.write_text("apiVersion: v1\nkind: Config\nusers: [{name: otro}]\n", encoding="utf-8")
    refused = run(tmp_path, "write", str(stranger))
    assert refused.returncode == 2 and "otro" in stranger.read_text(encoding="utf-8")
    stranger.unlink()
    assert run(tmp_path, "write", str(stranger)).returncode == 0
    assert run(tmp_path, "write", str(stranger)).returncode == 0  # el suyo, de una corrida anterior (tras recrear el cluster)
