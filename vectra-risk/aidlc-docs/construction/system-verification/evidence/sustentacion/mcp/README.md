# Evidencia del servidor MCP de solo lectura (`vectra-lectura`)

Corrida del 2026-11-21 contra el clúster local `kind-vectra`, con el kubeconfig de solo lectura `~/.kube/kind-vectra-readonly` (identidad `system:serviceaccount:argocd:vectra-readonly-agent`). Ninguna orden escribió en el clúster y el kubeconfig de administrador no se usó. Los archivos no llevan tokens. Servidor: [`loop/mcp-solo-lectura/`](../../../../../../loop/mcp-solo-lectura/README.md), `mcp==2.3.0`, `kubectl` v1.35.10.

Las salidas son las del cliente de demostración (`demo_cliente.py`), que arranca el servidor por stdio y le habla por el protocolo MCP, igual que Claude Code. Solo se guardó la salida estándar; el registro del servidor (stderr) no.

## Lecturas reales

[`lecturas.txt`](lecturas.txt): `tools/list` (las seis herramientas) y cuatro llamadas.

| Llamada | Resultado |
|---|---|
| `argo_applications` | 56 Applications: 54 `Synced` y 2 `OutOfSync` (`kserve-crd`, `linkerd-control-plane`), las 56 `Healthy`. La salida trae 50 y `truncated: true`, con las `OutOfSync` primero |
| `pods` en `vectra-app` | 29 pods: 18 `Running`, 8 `Succeeded` y 3 `Failed` (los que no están sanos salen primero) |
| `inference_services` en `vectra-serving` | 2 InferenceServices, los dos con `ready: "True"` |
| `permissions` en `vectra-app` | `get pods`, `list applications` y `list inferenceservices`: `true`. `get secrets`, `create pods`, `delete pods`, `patch deployments` y `create pods/exec`: `false` |

## Caso frenado

Un agente intenta lo que no le toca. Cada capa lo frena por separado.

| Capa | Intento | Qué pasó | Archivo |
|---|---|---|---|
| El servidor no tiene la herramienta | `exec`, `delete_pod`, `get_secret` | `Unknown tool` | [`frenos-servidor.txt`](frenos-servidor.txt) |
| Validación de argumentos | `workloads` con `kind: "secrets"` | `argumento rechazado: kind 'secrets' no esta en la lista cerrada` | [`frenos-servidor.txt`](frenos-servidor.txt) |
| Validación de argumentos | `namespace` con `; kubectl delete pods --all`, `--as=system:admin` o `../../kube-system` | `argumento rechazado: namespace ... no es una etiqueta DNS`; no se lanzó ninguna orden | [`frenos-servidor.txt`](frenos-servidor.txt) |
| Arranque | Un kubeconfig con certificado de cliente (la forma del de administrador), uno con el token de otra cuenta y uno que no existe | El servidor termina con código 2 y dice el motivo | [`arranque-rechazado.txt`](arranque-rechazado.txt) |
| RBAC del clúster, misma identidad | `kubectl auth can-i` de `create pods`, `delete pods`, `get secrets`, `list secrets`, `create pods/exec` y `patch deployments` | `no` en las seis. `kubectl get secrets -n vectra-app` responde `Forbidden` y nombra a la cuenta | [`frenos-rbac.txt`](frenos-rbac.txt) |
| RBAC del clúster, tabla completa | `platform/kind/readonly-kubeconfig.sh check` | `Filas: 92; distintas de lo esperado: 0; sin respuesta: 0.` | [`frenos-rbac.txt`](frenos-rbac.txt) |

Los kubeconfigs rechazados en el arranque son archivos falsos escritos para esta evidencia (certificado y token inventados, API `127.0.0.1:1`); se borraron al terminar.

## No medido

- El servidor no se cargó desde una sesión de Claude Code con `.mcp.json`: se probó con el cliente del SDK de MCP por stdio. Que Claude Code lo apruebe, lo arranque y aplique `permissions.allow` queda por ver en una sesión real.
- El revisor no se despachó con las herramientas nuevas.

## Repetir

```bash
cd vectra-risk
platform/kind/readonly-kubeconfig.sh check
uv run python loop/mcp-solo-lectura/demo_cliente.py lecturas
uv run python loop/mcp-solo-lectura/demo_cliente.py frenos
```
