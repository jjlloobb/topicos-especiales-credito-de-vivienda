"""La allowlist esta en cuatro sitios y deben decir lo mismo: el servidor (`TOOL_NAMES` y lo que registra), `.mcp.json`, `permissions.allow` de
`.claude/settings.json` y el `tools:` de los agentes. Esta prueba lee los cuatro y el README."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from vectra_mcp_readonly.kubectl import Kubectl
from vectra_mcp_readonly.server import SERVER_NAME, TOOL_NAMES, build_server

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]
PREFIX = f"mcp__{SERVER_NAME}__"
EXPECTED = {"argo_applications", "pods", "events", "inference_services", "workloads", "permissions"}
FORBIDDEN_NAME = re.compile(
    r"exec|apply|delete|create|patch|scale|secret|run|command|shell|write|edit|rollout|sync|log|forward"
)


def _registered(kubectl: Kubectl) -> list:
    return asyncio.run(build_server(kubectl).list_tools())


def _settings() -> dict:
    return json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _agent_tools(name: str) -> list[str]:
    text = (REPO / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")
    front = text.split("---", 2)[1]
    line = next(row for row in front.splitlines() if row.startswith("tools:"))
    return [tool.strip() for tool in line.removeprefix("tools:").split(",")]


def test_the_server_registers_exactly_the_closed_list(kubectl: Kubectl) -> None:
    names = [tool.name for tool in _registered(kubectl)]
    assert sorted(names) == sorted(TOOL_NAMES) and len(names) == len(set(names))
    assert set(names) == EXPECTED


def test_no_tool_name_or_parameter_suggests_a_write_or_a_free_command(kubectl: Kubectl) -> None:
    for tool in _registered(kubectl):
        assert FORBIDDEN_NAME.search(tool.name) is None, tool.name
        properties = tool.input_schema.get("properties", {})
        assert set(properties) <= {"namespace", "kind", "only_warnings"}, (tool.name, properties)
        assert (
            tool.annotations is not None
            and tool.annotations.read_only_hint is True
            and tool.annotations.destructive_hint is False
        )


def test_settings_allow_is_exactly_the_registered_tools_one_by_one(kubectl: Kubectl) -> None:
    allow = _settings()["permissions"]["allow"]
    mcp_entries = [entry for entry in allow if entry.startswith("mcp__")]
    assert sorted(mcp_entries) == sorted(PREFIX + tool.name for tool in _registered(kubectl))
    assert not any("*" in entry for entry in mcp_entries), "sin comodines: cada herramienta se nombra"
    assert f"mcp__{SERVER_NAME}" not in allow, (
        "el nombre del servidor solo permitiria todas sus herramientas, tambien las futuras"
    )
    assert allow == mcp_entries, "la allowlist del proyecto solo tiene las lecturas MCP"


def test_settings_keep_the_denies_and_enable_nothing_else() -> None:
    settings = _settings()
    deny = set(settings["permissions"]["deny"])
    for verb in (
        "apply",
        "create",
        "delete",
        "patch",
        "edit",
        "replace",
        "scale",
        "rollout",
        "annotate",
        "label",
    ):
        assert {f"Bash(kubectl {verb} *)", f"Bash(kubectl * {verb} *)"} <= deny, verb
    assert {
        "Bash(helm install *)",
        "Bash(helm upgrade *)",
        "Bash(argocd app sync *)",
        "Bash(kind delete *)",
        "Bash(docker rm *)",
    } <= deny
    assert len(deny) >= 32
    assert not any(entry.startswith("mcp__") for entry in deny)
    assert "enableAllProjectMcpServers" not in settings


def test_mcp_json_declares_only_this_server_over_stdio_without_credentials() -> None:
    servers = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert list(servers) == [SERVER_NAME]
    server = servers[SERVER_NAME]
    assert (
        server["type"] == "stdio" and server["command"] == "uv" and server["args"][-1] == "vectra-mcp-lectura"
    )
    text = json.dumps(server)
    assert "KUBECONFIG=" not in text and ".kube/config" not in text and "token" not in text.lower()
    assert "KUBECONFIG" not in server.get("env", {})


def test_the_reviewer_has_exactly_these_mcp_tools_and_the_coder_has_none() -> None:
    reviewer = [tool for tool in _agent_tools("revisor") if tool.startswith("mcp__")]
    assert sorted(reviewer) == sorted(PREFIX + name for name in TOOL_NAMES)
    assert [tool for tool in _agent_tools("revisor") if not tool.startswith("mcp__")] == [
        "Bash",
        "Read",
        "Grep",
        "Glob",
    ]
    assert _agent_tools("codificador") == ["Bash", "Read", "Edit", "Write", "Grep", "Glob"]


def test_the_readme_table_lists_exactly_the_tools() -> None:
    readme = (PACKAGE / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z_]+)` \|", readme, flags=re.MULTILINE)
    assert sorted(rows) == sorted(TOOL_NAMES)
    for name in TOOL_NAMES:
        assert PREFIX + name in readme


@pytest.mark.parametrize(
    "extra", ["mcp__vectra-lectura__exec", "mcp__vectra-lectura__*", "mcp__vectra-lectura", "mcp__otro__leer"]
)
def test_the_comparison_detects_a_drift(extra: str, kubectl: Kubectl) -> None:
    allow = [*_settings()["permissions"]["allow"], extra]
    registered = sorted(PREFIX + tool.name for tool in _registered(kubectl))
    assert sorted(entry for entry in allow if entry.startswith("mcp__")) != registered
