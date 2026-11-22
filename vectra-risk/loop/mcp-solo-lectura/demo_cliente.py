"""Cliente MCP de demostracion: arranca el servidor por stdio (como lo haria Claude Code) y muestra las lecturas y los frenos.

    uv run python loop/mcp-solo-lectura/demo_cliente.py lecturas     # lista de herramientas y tres lecturas reales
    uv run python loop/mcp-solo-lectura/demo_cliente.py frenos       # lo que no se puede: herramienta inexistente y argumentos rechazados

Usa el kubeconfig de `VECTRA_READONLY_KUBECONFIG` (o `~/.kube/kind-vectra-readonly`). Solo lee: las unicas ordenes que llegan al cluster son las del servidor.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(command=sys.executable, args=["-m", "vectra_mcp_readonly.server"])
READS: list[tuple[str, dict[str, Any]]] = [
    ("argo_applications", {}),
    ("pods", {"namespace": "vectra-app"}),
    ("inference_services", {"namespace": "vectra-serving"}),
    ("permissions", {"namespace": "vectra-app"}),
]
BLOCKED: list[tuple[str, dict[str, Any]]] = [
    ("exec", {"namespace": "vectra-app", "pod": "x", "command": "sh"}),
    ("delete_pod", {"namespace": "vectra-app", "name": "x"}),
    ("get_secret", {"namespace": "vectra-app", "name": "x"}),
    ("workloads", {"namespace": "vectra-app", "kind": "secrets"}),
    ("pods", {"namespace": "vectra-app; kubectl delete pods --all"}),
    ("pods", {"namespace": "--as=system:admin"}),
    ("events", {"namespace": "../../kube-system"}),
]


def out(text: str) -> None:
    sys.stdout.write(text + "\n")


async def call(session: ClientSession, name: str, arguments: dict[str, Any]) -> None:
    out(f"\n$ tools/call {name} {json.dumps(arguments, ensure_ascii=False)}")
    try:
        result = await session.call_tool(name, arguments)
    except Exception as error:  # noqa: BLE001 - la demo muestra cualquier rechazo del protocolo
        out(f"RECHAZADO por el protocolo: {type(error).__name__}: {error}")
        return
    text = "\n".join(getattr(block, "text", "") for block in result.content)
    out(f"{'ERROR de la herramienta' if result.is_error else 'ok'}:\n{text}")


async def main(mode: str) -> None:
    async with stdio_client(SERVER) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = await session.list_tools()
        out("$ tools/list")
        for tool in listed.tools:
            out(f"  {tool.name}({', '.join(tool.input_schema.get('properties', {}))})")
        for name, arguments in READS if mode == "lecturas" else BLOCKED:
            await call(session, name, arguments)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("lecturas", "frenos"):
        sys.stderr.write("Uso: demo_cliente.py lecturas | frenos\n")
        raise SystemExit(2)
    asyncio.run(main(sys.argv[1]))
