# RateLimitBackendDown

- **Severidad**: SEV2
- **Alerta**: `RateLimitBackendDown` (U2)

## Síntoma
El servicio de rate limit (`envoy-ratelimit`, `envoy-gateway-system`) o Valkey (`vectra-edge`) no responde: sin réplicas disponibles según kube-state-metrics, o `redis_up == 0` en el exportador (9121), durante 2 minutos.

## Impacto
`/auth/**` está en fail-closed: el gateway responde 503 mientras el backend de rate limit no conteste. Las demás rutas siguen.

## Servicio caído o consulta lenta
Los dos casos dan el mismo 503 de login (`urn:vectra:problem:dependency_unavailable`) y se distinguen por cuánto dura y por lo que dice el registro de acceso del gateway.

| | Servicio de límites caído | Consulta lenta (503 suelto) |
|---|---|---|
| Qué se ve | 503 en **todos** los logins y tokens, de forma sostenida | 503 en uno de varios intentos; el siguiente pasa sin tocar nada |
| Registro de acceso (`api-gateway`, contenedor `envoy`) | `status` 503, `response_flags: RLSE` en cada intento de `/auth/**` | `status` 503, `response_flags: RLSE`, `duration_ms` cerca del plazo del filtro (`timeout` de `fail_closed` en `gateway/routes.yaml`, hoy 500 ms; antes de U02-T26 eran 20 ms de fábrica) |
| `envoy-ratelimit` (`envoy-gateway-system`) | sin réplicas, o errores de Redis en cada llamada | `rate limit call failed with a Redis error: waiting for response from Conn: context canceled` o `… context deadline exceeded`, aislados |
| Alerta | `RateLimitBackendDown` | ninguna |

Cómo verlo: `kubectl -n vectra-edge logs deploy/api-gateway -c envoy | grep RLSE` (o la consulta equivalente en Loki) y mira `duration_ms`; `kubectl -n envoy-gateway-system logs deploy/envoy-ratelimit | grep -E 'context (canceled|deadline exceeded)'`.

Si el 503 es suelto, no es una caída: la consulta a Valkey tardó más que el plazo del filtro (portátil saturado, Valkey tras la malla). El 503 de `/auth/**` es a propósito (fail-closed, P-U2-01): no lo pases a fail-open. Si con la máquina en calma siguen saliendo, mira la carga de los nodos y de Valkey antes de subir el plazo; si lo subes, cámbialo en `routes.yaml` (`fail_closed.timeout`, tope de 2 s en `route_gen`), regenera con `make -C identity-edge route-gen` y no lo dejes sin acotar: mientras espera, el gateway retiene la petición de login. Solo `/auth/**` lleva este plazo; el resto de las rutas, en fail-open, conserva el de fábrica.

## Diagnóstico
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
