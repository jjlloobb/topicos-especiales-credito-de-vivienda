"""Un argumento hostil se rechaza antes de llamar a `kubectl`: ni una orden lanzada."""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from vectra_mcp_readonly import tools
from vectra_mcp_readonly.kubectl import Kubectl, Rejected
from vectra_mcp_readonly.server import build_server

HOSTILE = [
    "; rm -rf /",
    "vectra-app; rm -rf /",
    "--as=admin",
    "-A",
    "--all-namespaces",
    "../",
    "../../etc/passwd",
    "vectra app",
    " vectra-app",
    "vectra-app\n",
    "vectra-app\x00",
    "$(id)",
    "`id`",
    "vectra-app|cat",
    "Vectra-App",
    "vectra_app",
    "secret/db-password",
    "secrets",  # como namespace es una etiqueta valida: se prueba aparte, como `kind`
    "pods/exec",
    "a" * 64,
    "-vectra",
    "vectra-",
    "",
    "vectra-app --kubeconfig=/home/u/.kube/config",
    "ñandu",
]
HOSTILE_NAMESPACES = [value for value in HOSTILE if value != "secrets"]
NAMESPACED = ["pods", "events", "inference_services", "workloads", "permissions"]
HOSTILE_KINDS = ["secrets", "secret", "secrets/db-password", "pods/exec", "configmaps", "deployments,secrets", "deployments; rm -rf /", "--as=admin", "../", "Deployments", ""]  # fmt: skip


@pytest.mark.parametrize("tool", NAMESPACED)
@pytest.mark.parametrize("namespace", HOSTILE_NAMESPACES)
def test_a_hostile_namespace_is_rejected_and_nothing_runs(
    tool: str, namespace: str, kubectl: Kubectl, runner
) -> None:
    with pytest.raises(Rejected, match="argumento rechazado"):
        getattr(tools, tool)(kubectl, namespace)
    assert runner.calls == []


@pytest.mark.parametrize("namespace", [None, 7, ["vectra-app"], {"n": 1}, b"vectra-app"])
def test_a_namespace_that_is_not_text_is_rejected(namespace: object, kubectl: Kubectl, runner) -> None:
    with pytest.raises(Rejected):
        tools.pods(kubectl, namespace)  # type: ignore[arg-type]
    assert runner.calls == []


@pytest.mark.parametrize("kind", HOSTILE_KINDS)
def test_a_kind_outside_the_closed_list_is_rejected_and_nothing_runs(
    kind: str, kubectl: Kubectl, runner
) -> None:
    with pytest.raises(Rejected, match="lista cerrada"):
        tools.workloads(kubectl, "vectra-app", kind)
    assert runner.calls == []


def test_asking_for_a_secret_through_the_server_is_a_tool_error_with_the_reason(
    kubectl: Kubectl, runner
) -> None:
    server = build_server(kubectl)
    with pytest.raises(ToolError, match="argumento rechazado: kind 'secrets'"):
        asyncio.run(server.call_tool("workloads", {"namespace": "vectra-app", "kind": "secrets"}))
    with pytest.raises(ToolError, match="argumento rechazado: namespace"):
        asyncio.run(server.call_tool("pods", {"namespace": "vectra-app; kubectl delete pod x"}))
    assert runner.calls == []


@pytest.mark.parametrize(
    "name",
    ["exec", "apply", "delete_pod", "get_secret", "secrets", "run_command", "kubectl", "logs", "scale"],
)
def test_a_tool_that_does_not_exist_cannot_be_called(name: str, kubectl: Kubectl, runner) -> None:
    with pytest.raises(ToolError, match="Unknown tool"):
        asyncio.run(
            build_server(kubectl).call_tool(
                name, {"namespace": "vectra-app", "command": "kubectl delete pod x"}
            )
        )
    assert runner.calls == []


def test_the_rejection_message_clips_the_argument(kubectl: Kubectl) -> None:
    with pytest.raises(Rejected) as caught:
        tools.pods(kubectl, "x" * 5000)
    assert len(str(caught.value)) < 200


def test_can_i_rejects_a_question_that_is_not_a_word(kubectl: Kubectl, runner) -> None:
    for verb, resource, sub in (
        ("get; id", "pods", None),
        ("get", "pods --as=admin", None),
        ("get", "pods", "exec --as=admin"),
        ("--list", "pods", None),
    ):
        with pytest.raises(Rejected):
            kubectl.can_i(verb, resource, "vectra-app", sub)
    assert runner.calls == []
