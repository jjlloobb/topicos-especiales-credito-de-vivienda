# RateLimitBackendDown

- **Severidad**: SEV2
- **Alerta**: `RateLimitBackendDown` (U2)

## Síntoma
El servicio de rate limit (`envoy-ratelimit`, `envoy-gateway-system`) o Valkey (`vectra-edge`) no responde: sin réplicas disponibles según kube-state-metrics, o `redis_up == 0` en el exportador (9121), durante 2 minutos. También dispara **por ausencia** (B13): kube-state-metrics dejó de exponer la serie `kube_deployment_status_replicas_available` del Deployment `envoy-ratelimit` o la `kube_statefulset_status_replicas_available` del StatefulSet de Valkey (`absent(...)`). Una serie ausente no es un valor 0 y la comparación `== 0` no devuelve nada, por eso la alerta la cubre aparte.

**Qué trae la alerta por ausencia.** `absent()` solo conserva las etiquetas de igualdad del selector. La del Deployment trae `namespace="envoy-gateway-system"` y `deployment="envoy-ratelimit"`. La del StatefulSet trae solo `namespace="vectra-edge"`: `statefulset=~"valkey-.+"` es una expresión regular y `absent()` la descarta. Por eso la alerta de Valkey no dice cuál StatefulSet falta: mira ambos (`valkey-a` y `valkey-b`).

## Impacto
`/auth/**` está en fail-closed: el gateway responde 503 mientras el backend de rate limit no conteste. Las demás rutas siguen.

## Diagnóstico
0. Si la alerta es por ausencia (etiquetas de arriba), primero decide si el objeto no existe o si kube-state-metrics no lo expone: `kubectl -n envoy-gateway-system get deployment envoy-ratelimit`, `kubectl -n vectra-edge get statefulset` y `kubectl -n vectra-observability get pods -l app.kubernetes.io/name=kube-state-metrics`. Un Deployment o StatefulSet borrado o renombrado es una caída del rate limit; un kube-state-metrics caído deja ciegas las demás alertas que usan sus series.
1. Servicio de rate limit: `kubectl -n envoy-gateway-system get deployment envoy-ratelimit`.
2. Valkey y Sentinel: `kubectl -n vectra-edge get statefulset,pods -l app.kubernetes.io/part-of=identity-edge`.
3. ¿Quién es la primaria? `kubectl -n vectra-edge exec sentinel-a-0 -c sentinel -- valkey-cli --user ratelimit -p 26379 sentinel master ratelimit`.
4. Zona caída: `kubectl get nodes -L topology.kubernetes.io/zone`.
5. Credenciales: `kubectl -n envoy-gateway-system get externalsecret envoy-ratelimit-valkey` y `kubectl -n vectra-edge get externalsecret`.

## Mitigación
1. Si cayó una zona, deja que Sentinel promueva (5 s más la promoción) y sigue `platform/runbooks/zone-failover.md`. Mientras la primaria esté en la zona B, una caída de B deja 1 de 3 Sentinel, sin promoción: es el riesgo aceptado de INF-U2-04.
2. Cuando la zona A vuelva, devuelve la primaria con `valkey-zone-failback.md`.
3. Si falla el `ExternalSecret`, revisa la clave `edge/valkey` de la bóveda; nunca pongas una contraseña en un ConfigMap.
4. No pases `/auth/**` a fail-open para tapar la alerta.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`platform/runbooks/coe-template.md`).

## Verificación
- `kubectl -n envoy-gateway-system get deployment envoy-ratelimit -o jsonpath='{.status.availableReplicas}'` devuelve 1 o más.
- `kubectl -n vectra-edge get statefulset valkey-a valkey-b` muestra al menos un `READY 1/1`.
- La alerta deja de estar `firing` en Alertmanager.
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
