"""Servidor MCP por stdio, de solo lectura, para los agentes del loop de Vectra Risk.

Registra **exactamente** las herramientas de `TOOL_NAMES` (la misma lista que `permissions.allow` de `.claude/settings.json`; una prueba compara los dos
sitios). No hay herramienta de escritura, ni `exec`, ni lectura de Secrets, ni una que reciba una orden. `main` comprueba el kubeconfig (`guard`) antes de
abrir el transporte: con uno que no sea el de `vectra-readonly-agent` termina con codigo 2 y el motivo en stderr.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any, Final

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from vectra_mcp_readonly import guard, tools
from vectra_mcp_readonly.kubectl import K8sError, Kubectl, SubprocessRunner

SERVER_NAME: Final = "vectra-lectura"
TOOL_NAMES: Final = ("argo_applications", "pods", "events", "inference_services", "workloads", "permissions")
INSTRUCTIONS: Final = (
    "Lecturas acotadas del cluster kind de Vectra Risk con la identidad de solo lectura vectra-readonly-agent. "
    "No hay herramientas de escritura, exec ni Secrets: lo que no esta en la lista no se puede hacer desde aqui."
)
_READ_ONLY: Final = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def _answer(read: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Un argumento rechazado o un fallo de `kubectl` llega al cliente como error de la herramienta, con su motivo (ya recortado y sin secretos)."""
    try:
        return read()
    except K8sError as error:
        raise ToolError(str(error)) from None


def build_server(kubectl: Kubectl) -> MCPServer:
    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS)

    @server.tool(annotations=_READ_ONLY)
    def argo_applications() -> dict[str, Any]:
        """Estado de sync y salud de las Applications de Argo CD (namespace argocd). Lee: get applications.argoproj.io."""
        return _answer(lambda: tools.argo_applications(kubectl))

    @server.tool(annotations=_READ_ONLY)
    def pods(namespace: str) -> dict[str, Any]:
        """Pods de un namespace: fase, contenedores listos, reinicios y motivo de espera. Lee: get pods."""
        return _answer(lambda: tools.pods(kubectl, namespace))

    @server.tool(annotations=_READ_ONLY)
    def events(namespace: str, only_warnings: bool = False) -> dict[str, Any]:
        """Eventos recientes de un namespace, del mas nuevo al mas viejo (mensajes recortados). Lee: get events."""
        return _answer(lambda: tools.events(kubectl, namespace, only_warnings))

    @server.tool(annotations=_READ_ONLY)
    def inference_services(namespace: str) -> dict[str, Any]:
        """InferenceServices de KServe de un namespace: listo o no, motivo y URL. Lee: get inferenceservices.serving.kserve.io."""
        return _answer(lambda: tools.inference_services(kubectl, namespace))

    @server.tool(annotations=_READ_ONLY)
    def workloads(namespace: str, kind: str = "deployments") -> dict[str, Any]:
        """Replicas deseadas y listas. `kind` es uno de: deployments, statefulsets, daemonsets, jobs. Lee: get <kind>."""
        return _answer(lambda: tools.workloads(kubectl, namespace, kind))

    @server.tool(annotations=_READ_ONLY)
    def permissions(namespace: str) -> dict[str, Any]:
        """Lo que esta identidad puede hacer en un namespace (equivale a `kubectl auth can-i --list`), con las preguntas clave: escribir, exec, Secrets."""
        return _answer(lambda: tools.permissions(kubectl, namespace))

    return server


def prepare(environ: dict[str, str] | os._Environ[str], kubectl_factory: Any = None) -> Kubectl:
    """El `Kubectl` de solo lectura, ya comprobado; lanza `guard.StartupRefused` si el kubeconfig no es el esperado."""
    path = guard.kubeconfig_path(environ)
    context = guard.check_file(path)
    kubectl: Kubectl = (kubectl_factory or (lambda p, c: Kubectl(SubprocessRunner(), p, c)))(
        path.resolve(), context
    )
    guard.check_live(kubectl)
    return kubectl


def main() -> (
    None
):  # pragma: no cover - abre el transporte stdio; `prepare` y `build_server` se prueban aparte
    try:
        kubectl = prepare(os.environ)
    except guard.StartupRefused as refusal:
        sys.stderr.write(f"vectra-mcp-lectura se niega a arrancar: {refusal}\n")
        raise SystemExit(2) from None
    build_server(kubectl).run("stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
