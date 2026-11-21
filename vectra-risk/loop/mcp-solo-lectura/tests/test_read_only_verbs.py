"""Cada herramienta lanza solo `kubectl get` o `kubectl auth can-i`, con el kubeconfig de solo lectura, y el codigo fuente no tiene otra puerta."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from vectra_mcp_readonly import tools
from vectra_mcp_readonly.kubectl import READ_RESOURCES, Kubectl, Rejected
from vectra_mcp_readonly.server import TOOL_NAMES, build_server

SRC = Path(__file__).resolve().parents[1] / "src" / "vectra_mcp_readonly"
WRITE_WORDS = {"apply", "create", "delete", "patch", "edit", "replace", "scale", "rollout", "exec", "cp", "port-forward", "logs", "annotate", "label", "run", "attach", "debug", "drain", "cordon", "taint", "proxy"}  # fmt: skip
ARGUMENTS = {
    "argo_applications": {},
    "pods": {"namespace": "vectra-app"},
    "events": {"namespace": "vectra-app", "only_warnings": True},
    "inference_services": {"namespace": "vectra-app"},
    "workloads": {"namespace": "vectra-app", "kind": "statefulsets"},
    "permissions": {"namespace": "vectra-app"},
}


def is_read_only(command: tuple[str, ...]) -> bool:
    if command[0] != "kubectl":
        return False
    if command[1] == "get":
        return command[2] in READ_RESOURCES and "secret" not in command[2]
    return command[1:3] == ("auth", "can-i")


def test_arguments_cover_every_tool() -> None:
    assert set(ARGUMENTS) == set(TOOL_NAMES)


@pytest.mark.parametrize("name", sorted(ARGUMENTS))
def test_each_tool_runs_only_read_verbs_with_the_read_only_kubeconfig(
    name: str, kubectl: Kubectl, runner
) -> None:
    result = asyncio.run(build_server(kubectl).call_tool(name, ARGUMENTS[name]))
    assert result.is_error is False
    assert runner.calls, "la herramienta no leyo nada"
    for command, env in zip(runner.calls, runner.envs, strict=True):
        assert is_read_only(command), command
        assert (
            "--kubeconfig=/run/user/1000/kind-vectra-readonly" in command
            and "--context=kind-vectra" in command
        )
        assert not any(a.startswith(("--as", "--token", "--user", "--server", "-f")) for a in command), (
            command
        )
        assert (
            set(env) == {"PATH", "HOME", "KUBECONFIG"}
            and env["KUBECONFIG"] == "/run/user/1000/kind-vectra-readonly"
        )
        # Tras `auth can-i` el verbo es la pregunta (`can-i create pods` no crea nada); en `get` ninguna palabra de escritura.
        assert command[1] != "get" or not WRITE_WORDS & set(command)


def test_the_is_read_only_check_detects_a_write() -> None:
    assert not is_read_only(("kubectl", "delete", "pod", "x"))
    assert not is_read_only(("kubectl", "get", "secrets", "-n", "x"))
    assert not is_read_only(("sh", "-c", "kubectl get pods"))
    assert not is_read_only(("kubectl", "auth", "reconcile", "-f", "x"))
    assert is_read_only(("kubectl", "auth", "can-i", "create", "pods"))


def test_get_refuses_a_resource_outside_the_closed_list(kubectl: Kubectl, runner) -> None:
    for resource in (
        "secrets",
        "secret",
        "secrets.v1",
        "pods/exec",
        "configmaps",
        "nodes",
        "pods,secrets",
        "all",
    ):
        with pytest.raises(Rejected):
            kubectl.get(resource, "vectra-app")
    assert runner.calls == []
    assert not any("secret" in resource for resource in READ_RESOURCES)
    assert set(tools.WORKLOAD_KINDS.values()) <= READ_RESOURCES


# --- Estatica: el codigo fuente no tiene otra forma de lanzar un proceso ni otro verbo de `kubectl` ---


def _sources() -> dict[str, ast.Module]:
    return {path.name: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(SRC.glob("**/*.py"))}


def kubectl_verb_findings(tree: ast.AST) -> list[str]:
    """Toda lista que empieza por `"kubectl"` debe seguir con el literal `"get"` o con `"auth", "can-i"`. Un verbo en una variable es un hallazgo."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List | ast.Tuple) or not node.elts:
            continue
        head = [e.value if isinstance(e, ast.Constant) else None for e in node.elts]
        if head[0] != "kubectl":
            continue
        if not (head[1:2] == ["get"] or head[1:3] == ["auth", "can-i"]):
            found.append(f"linea {node.lineno}: kubectl {head[1:3]}")
    return found


def test_only_kubectl_py_imports_subprocess_and_names_kubectl() -> None:
    for name, tree in _sources().items():
        imported = {
            a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        }
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not imported & {
            "pty",
            "shlex",
            "socket",
            "httpx",
            "requests",
            "urllib",
            "kubernetes",
            "ctypes",
            "importlib",
        }, name
        literals = {
            n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not calls & {
            "os.system",
            "os.popen",
            "eval",
            "exec",
            "os.execv",
            "os.execvp",
            "os.spawnv",
            "__import__",
        }, name
        if name != "kubectl.py":
            assert "subprocess" not in imported, name
            assert "kubectl" not in literals, name


def test_kubectl_py_has_only_the_two_literal_verbs_and_no_shell() -> None:
    tree = _sources()["kubectl.py"]
    assert kubectl_verb_findings(tree) == []
    lists = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.List)
        and n.elts
        and isinstance(n.elts[0], ast.Constant)
        and n.elts[0].value == "kubectl"
    ]
    assert len(lists) == 3  # get, auth can-i y auth can-i --list
    keywords = {k.arg for n in ast.walk(tree) if isinstance(n, ast.Call) for k in n.keywords}
    assert "shell" not in keywords
    assert [
        ast.unparse(n.func)
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and ast.unparse(n.func).startswith("subprocess.")
    ] == ["subprocess.run"]


@pytest.mark.parametrize(
    "source",
    [
        '["kubectl", "delete", "pod", x]',
        '["kubectl", verb, x]',
        '["kubectl", "auth", "reconcile"]',
        '["kubectl", "exec", pod]',
        '("kubectl", "apply")',
    ],
)
def test_the_static_check_detects_another_verb(source: str) -> None:
    assert kubectl_verb_findings(ast.parse(source)) != []
