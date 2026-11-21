# `vectra-lectura`: servidor MCP de solo lectura para el loop

Un servidor MCP por stdio que da a los agentes del loop **seis lecturas acotadas** del clúster local `kind-vectra`, con la identidad `vectra-readonly-agent` ([`platform/rbac/readonly-agent/`](../../platform/rbac/readonly-agent/readonly-agent-kind.yaml), [`platform/kind/readonly-kubeconfig.md`](../../platform/kind/readonly-kubeconfig.md)). No hay más herramientas que las de la tabla.

## Las herramientas (la allowlist)

| Herramienta | Qué lee | Verbo de Kubernetes | Recurso | Argumentos |
|---|---|---|---|---|
| `argo_applications` | Sync y salud de cada Application, primero las que no están `Synced` y `Healthy` | `list` | `applications.argoproj.io` en `argocd` | ninguno |
| `pods` | Fase, contenedores listos, reinicios y motivo de espera | `list` | `pods` | `namespace` |
| `events` | Eventos del más nuevo al más viejo, con el mensaje recortado | `list` | `events` | `namespace`, `only_warnings` |
| `inference_services` | Si cada InferenceService de KServe está listo, el motivo y la URL | `list` | `inferenceservices.serving.kserve.io` | `namespace` |
| `workloads` | Réplicas deseadas y listas | `list` | `deployments.apps`, `statefulsets.apps`, `daemonsets.apps` o `jobs.batch` | `namespace`, `kind` |
| `permissions` | Lo que la propia cuenta puede hacer: ocho preguntas fijas y el resumen de `kubectl auth can-i --list` | `create` de `selfsubjectaccessreviews` y `selfsubjectrulesreviews` (una pregunta al API: no guarda nada) | `authorization.k8s.io` | `namespace` |

Por debajo solo hay dos órdenes: `kubectl get <recurso> -n <namespace> -o json` y `kubectl auth can-i ...`. El nombre con el que Claude Code las ve es `mcp__vectra-lectura__<herramienta>`:

```
mcp__vectra-lectura__argo_applications
mcp__vectra-lectura__pods
mcp__vectra-lectura__events
mcp__vectra-lectura__inference_services
mcp__vectra-lectura__workloads
mcp__vectra-lectura__permissions
```

## Lo que NO hay, y por qué

| No hay | Por qué |
|---|---|
| Escritura (`apply`, `create`, `delete`, `patch`, `scale`, `rollout`, sync de Argo CD) | AUTONOMIA-01: el destino del agente es un pull request, no un cambio en el clúster. El `ClusterRole` tampoco la concede |
| `exec`, `attach`, `port-forward`, `cp` | Entrar a un pod es leer sus secretos montados y ejecutar con su identidad. El `ClusterRole` no tiene `pods/exec` |
| Lectura de `Secret` | El `ClusterRole` no nombra `secrets`; `workloads(kind="secrets")` se rechaza antes de llamar a `kubectl` |
| Logs de pods | El `ClusterRole` sí da `pods/log`, pero un log puede traer datos de solicitantes o credenciales y no se puede acotar por campos. Queda fuera a propósito |
| ConfigMaps, nodos, RBAC y el resto de lo que el `ClusterRole` permite leer | La lista es la mínima que usan el loop y la demo. Añadir una lectura es un cambio revisado en cuatro sitios (ver abajo) |
| Una herramienta genérica («ejecuta esta orden», «`kubectl get` de lo que sea») | Una orden libre no se puede poner en una allowlist. Cada recurso es un literal del código |
| Recursos, *prompts* o transporte HTTP de MCP | Solo herramientas, solo stdio: el servidor no escucha en ningún puerto |

## Las capas que frenan

1. **El servidor**: registra seis herramientas; pedir otra responde `Unknown tool`.
2. **Los argumentos**: `namespace` debe ser una etiqueta DNS (`[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?`) y `kind` uno de cuatro literales. Lo demás se rechaza sin lanzar ninguna orden. Los argumentos van como elementos de una lista, sin intérprete de órdenes.
3. **`kubectl`**: un solo archivo (`kubectl.py`) lo invoca, con los verbos `get` y `auth can-i` escritos como literales; el recurso de `get` sale de una lista cerrada. El proceso hijo recibe solo `PATH`, `HOME` y `KUBECONFIG` (el de solo lectura).
4. **El arranque**: el servidor termina con código 2 si el kubeconfig no es el de `vectra-readonly-agent` (archivo 0600, un solo contexto `kind-*`, autenticación solo por `token`, y `sub` del token igual a `system:serviceaccount:argocd:vectra-readonly-agent`), o si `kubectl auth can-i` no responde «no» a `create pods`, `delete pods`, `patch deployments`, `get secrets`, `list secrets`, `create pods/exec` e `impersonate users`. Sin respuesta del API tampoco arranca.
5. **El RBAC del clúster**: aunque todo lo anterior fallara, la cuenta solo tiene `get`, `list` y `watch`, y no sobre `secrets`.
6. **Claude Code**: `permissions.allow` nombra las seis herramientas una por una, sin comodines; los `deny` de `kubectl`, `helm`, `argocd`, `docker` y `kind` siguen igual. El revisor las lleva en su `tools:` (su invariante 6 le pide leer el estado de vuelta); el codificador no las tiene (su regla 8 lo aparta del clúster).

Qué no hace `permissions.allow`: no impide que una sesión use otra herramienta, solo evita la pregunta de aprobación para estas seis. Lo que restringe es el `tools:` de cada agente y lo que el servidor registra.

## Salidas

Cada respuesta lleva campos elegidos (nunca el objeto entero: sin `env`, anotaciones ni `data`), como mucho 50 elementos, 240 caracteres por texto y 16 000 en total. `total` dice cuántos había y `truncated` si se cortó. Lo que parece un JWT o un `password=...` en un mensaje se cambia por `<oculto>`.

## Uso

```bash
platform/kind/readonly-kubeconfig.sh write    # el operador, una vez (y tras recrear el clúster)
platform/kind/readonly-kubeconfig.sh check
uv run python loop/mcp-solo-lectura/demo_cliente.py lecturas   # tres lecturas reales por MCP
uv run python loop/mcp-solo-lectura/demo_cliente.py frenos     # lo que se rechaza
```

Claude Code lo arranca desde `.mcp.json` (raíz del repositorio) con `uv run --frozen --project vectra-risk vectra-mcp-lectura` y pide aprobar el servidor la primera vez. El kubeconfig es el de `VECTRA_READONLY_KUBECONFIG` o, si no está, `~/.kube/kind-vectra-readonly`. La variable `KUBECONFIG` no se lee.

Con el clúster apagado el servidor no arranca: no puede confirmar la identidad. Claude Code lo muestra como servidor fallido y las herramientas no aparecen.

## Añadir o quitar una herramienta

Son cuatro sitios y una prueba (`tests/test_allowlist.py`) falla si no coinciden: `server.py` (`TOOL_NAMES` y la función), `permissions.allow` de `.claude/settings.json`, el `tools:` de `.claude/agents/revisor.md` y la tabla de este archivo. Si lee un recurso nuevo, también `READ_RESOURCES` en `kubectl.py`, y el recurso debe estar en el `ClusterRole`.

## Pruebas

`make -C loop/mcp-solo-lectura check` (ruff, mypy y pytest; sin clúster, `kubectl` es un doble). Evidencia contra el clúster real: [`aidlc-docs/construction/system-verification/evidence/sustentacion/mcp/`](../../aidlc-docs/construction/system-verification/evidence/sustentacion/mcp/README.md).

SDK: `mcp==2.3.0` (el SDK oficial de Python; en la serie 2 `FastMCP` se llama `MCPServer`).
