# Ronda 1 — U02-T12

VEREDICTO: NO-VERDE

Hay un hallazgo en ROJO: tal como lo arbitró el orquestador, el selector de `envoy-gateway` deja a F95 y K14 sin efecto. Los cinco criterios pasan, el diseño T1–T5 se cumple y el worktree quedó limpio. Hash de la tarea: `72e4ded6…` (coincide). `git status --short` al terminar: vacío.

## Criterios de aceptación, verificados por mí (sha eb99051, desde `vectra-risk/`)
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `generate.py --check && pytest platform/network/tests -q` | pasa: 196 passed en 10,1 s, exit 0 |
| 2 | `pytest platform/network/tests/test_edge_selectors.py -q` | pasa: 42 passed en 1,7 s. El tiempo es razonable: no hay estado externo, solo render de los modelos |
| 3 | `make -C identity-edge check-valkey-rendered policy-valkey policy-valkey-u1 && pytest …/test_valkey_chart.py -q` | pasa: conftest 3072, 9×3, 112 y 3 por entorno sin fallos; 174 passed en 32 s, exit 0 |
| 4 | `pytest platform/tests/test_integration.py -q && make -C platform check-local` | pasa: 56 passed en 66 s; check-local con 730 passed y helm lint de 2 charts, exit 0 |
| 5 | `uv sync --frozen && make -C identity-edge check`, en serie después de CA-4 | pasa: 2367 passed en 775 s, sin omitidas, exit 0 |

El comando envoltorio en segundo plano terminó con 1, pero ese 1 sale del `ls | head`/`tail` final. Cada CA dejó su propio `exit 0` en `ca3.txt`, `ca4.txt` y `ca5.txt`.

## Hallazgos

### F-01 · ROJO · `platform/network/flows.yaml:146` (F95, K14) · el selector del controlador no selecciona su pod
`envoy-gateway: { ns: envoy-gateway-system, sa: envoy-gateway, name: envoy-gateway }` genera `podSelector: {app.kubernetes.io/name: envoy-gateway}` en dos sitios:
- `allow-f95-to-envoy-gateway-ingress`;
- `allow-k8s-api-k14`.

Lo comprobé en `generated/prod/envoy-gateway-system.yaml`.

El pod real tiene otras etiquetas. `helm template envoy-gateway platform/.charts/envoy-gateway/gateway-helm --namespace envoy-gateway-system --skip-crds -f platform/operators/envoy-gateway.yaml` devuelve:
- etiquetas del pod: `{'control-plane': 'envoy-gateway', 'app.kubernetes.io/name': 'gateway-helm', 'app.kubernetes.io/instance': 'envoy-gateway'}`;
- SA: `envoy-gateway`.

El upstream lo confirma (`gh api repos/envoyproxy/gateway/contents/charts/gateway-helm/templates/envoy-gateway-deployment.yaml?ref=v1.9.3`). El template usa `eg.selectorLabels` → `eg.name` = `default .Chart.Name .Values.nameOverride` = `gateway-helm`, y no hay `nameOverride` en los values.

Consecuencia: con el `deny-all` del namespace quedan cerrados el xDS (18000) del data plane hacia el controlador y la salida del controlador a la API (K14). Es la misma clase de defecto que F-12 de U02-T10 y F-01 de U02-T11. Lo que sí coincide con component-dependency K14 y con ADR §5: la SA, el namespace y el RBAC (`test_k14_*`, dentro de CA-5).

Tres observaciones más:
- La tarea mandaba «si falta algo, detente y repórtalo». El codificador lo reportó, pero solo en CANDIDATAS, y siguió adelante.
- `EDGE_WORKLOADS` de `test_edge_selectors.py` no incluye `envoy-gateway`, así que ninguna prueba lo detecta.
- Arreglo esperado: seleccionar por `control-plane: envoy-gateway` (o por las etiquetas del chart) y sumar `envoy-gateway`, con su caso contrario, a `test_edge_selectors.py`. El pod real debe salir del render del chart, no de un literal. Después hay que sacar la entrada de `CANDIDATAS.md`.

### F-02 · AMARILLO · `platform/network/generate.py:155-164` · `unmeshed_source` como lista no se valida
`any(s.get("name") in unmeshed …)`: si un nombre de la lista tiene una errata o no es origen del flujo, no se genera ninguna autorización por red y no hay ningún error. Los casos contrarios solo cubren quitar la clave. Basta una aserción en `build` de que cada entrada de la lista está en `from`.

### F-03 · AMARILLO · `generate.py:178-187` · nombre `*-operator-network` heredado de F80
Ahora también nombra la `NetworkAuthentication` de `envoy-ratelimit` (F91 y F61), que no es un operador. El nombre confunde, pero no cambia el comportamiento.

### F-04 · AMARILLO · `platform/network/tests/test_edge_flows.py:298-305` · la prueba de F80 no compara con `main`
Solo mira los nombres de las `NetworkAuthentication` y el tipo de la autorización del 8000. Lo que garantiza de verdad «F80 genera lo mismo que en `main`» es `--check`. Lo comprobé en el diff: `git diff --stat 4e1c702..eb99051` no toca `vectra-data.yaml`, y en `vectra-identity.yaml` solo cambian los selectores de Z1. Hoy se cumple; la prueba es más débil de lo que dice su nombre.

### F-05 · AMARILLO · `identity-edge/tests/unit/test_valkey_chart.py:549,551` · literal `{"name": "valkey-acl", "key": "sentinel-lookup-password"}`
El diseño no fija esa clave (es interna del chart), así que no choca con la nota de literales, pero se podría leer de `templates/support.yaml` o de la regla.

## Juicio de lo que pidió el orquestador
- **`unmeshed_ports: [5432]` en F80.** Correcto y mínimo. La tarea exige a la vez generalizar `unmeshed_source` y que F80 no cambie, y esta es la única forma de cumplir las dos. Que el 8000 del operador no esté autorizado por red ya pasaba en `main`; la candidata es legítima.
- **`unmeshed_source` como lista en F61.** Aceptable. Una línea aparte con el mismo id habría chocado en el nombre de la NetworkPolicy de entrada de `otel-collector`. Comprobé `f61-opentelemetry-collector-4317-operator-network` y su AuthorizationPolicy en `vectra-observability.yaml`. El hueco de validación está en F-02.
- **Los `Server` `valkey-6379` y `sentinel-6379` pasan a `opaque`.** Lo pide la tarea («si el puerto es opaco, el Server se declara opaque, como el 5432»), y corrige una incoherencia previa: `network_ports` ya abría el 4143 para el 6379 porque está en `LINKERD_OPAQUE_PORTS`, mientras el Server decía `unknown`. Solo cambian esos 6 `Server` (2 por 3 entornos); lo conté sobre el diff.
- **Candidata «F91 genera `sentinel-6379` y `valkey-26379`».** La causa **no es este diff**. En `main`, `generated/prod/vectra-edge.yaml` ya tiene `valkey-26379` (línea 561) y `sentinel-6379` (727), que vienen de F91 y F93. Este diff solo les cuelga además una `NetworkAuthentication` (inocua, porque ningún pod atiende esos puertos). La candidata está bien planteada.
- **Cambios en `vectra-app` y `vectra-identity`.** Son exactamente lo que pide Z1: solo cambia el `podSelector` del origen `api-gateway` (`app.kubernetes.io/name` → `gateway.envoyproxy.io/owning-gateway-name`), en 3 sitios de `vectra-app` y 2 de `vectra-identity` por entorno.
- **T4 contra Linkerd edge-26.10.2.** Confirmado con `gh api`:
  - `.proxy-version` = v2.372.0;
  - en `linkerd/app/core/src/serve.rs` (release/v2.372.0), el bucle `listen.next()` acepta antes de `new_accept.new_service`;
  - en `linkerd/app/inbound/src/server.rs` (líneas 95–142), `ConnectTcp` va dentro del stack de forward, es decir, después de aceptar.
  - Las líneas que cita la bitácora coinciden. Las de `proxy-init` no las volví a abrir.
- **T5 contra Valkey 8.1.11.** Confirmado en `src/valkey-cli.c`:
  - línea 87: `CLI_AUTH_ENV "REDISCLI_AUTH"`;
  - `cliAuth` (1536–1558): `AUTH user pass` con `--user`, `AUTH pass` sin él;
  - `cliConnect` (1677–1679): solo AUTH, SELECT y proto;
  - `parseEnv` (2900–2904).

  En el chart: `exporter` tiene `+ping` (`support.yaml:59`), el `ratelimit` de Sentinel tiene `+auth +hello +ping` (67), `exporter-password` existe en `valkey-acl` (75) y el pod de Sentinel lleva `REDISCLI_AUTH` (`sentinel.yaml:70`). Los comandos del render coinciden byte a byte con INF-U2-04 y con `probe_scripts` de la regla.

## Tareas candidatas (defectos reales fuera de alcance)
- Las cinco de `CANDIDATAS.md` del codificador son válidas. La primera la absorbe F-01.
- Nueva: la `livenessProbe` `exec` de Valkey falla con `-LOADING` mientras carga un RDB grande (6×10 s), cosa que el `tcpSocket` no hacía. Comprobarlo en kind junto con la candidata de `timeoutSeconds` (Paso 16).

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca1.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca2.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca3.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca4.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/ca5.txt
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a5f47c1d-22ac-4197-93fc-650bebd6a13b/scratchpad/eg.yaml (render del controlador)

No tengo herramienta de escritura, así que no escribí `revisiones/U02-T12/ronda-1.md`. Este mensaje es el informe; versionarlo le toca al orquestador.

```
VEREDICTO: NO-VERDE
ROJO|platform/network/flows.yaml:146 (F95, K14)|el selector app.kubernetes.io/name: envoy-gateway no selecciona el pod del controlador de gateway-helm v1.9.3 (lleva app.kubernetes.io/name: gateway-helm)
INFORME: revisiones/U02-T12/ronda-1.md
```
