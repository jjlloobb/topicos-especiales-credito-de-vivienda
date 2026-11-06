# Vuelta de la primaria de Valkey a la zona A

- **Severidad**: ninguna (operativo, sin alerta)
- **Alerta**: ninguna: INF-U2-04

## Síntoma
Tras una caída de la zona A, Sentinel promovió `valkey-b` a primaria. La zona A volvió y `valkey-b` sigue de primaria. Mientras eso dure, una caída de la zona B deja 1 de 3 Sentinel, sin promoción, y `/auth/**` responde 503 hasta que vuelva la zona.

## Impacto
Ninguno inmediato: el rate limit funciona. Es un riesgo aceptado del MVP (INF-U2-04) mientras la primaria esté en B.

## Diagnóstico
1. Confirma que la zona A volvió: `kubectl get nodes -L topology.kubernetes.io/zone`.
2. Pods de Valkey y Sentinel sanos: `kubectl -n vectra-edge get pods -l app.kubernetes.io/part-of=identity-edge -o wide`.
3. ¿Quién es la primaria? `kubectl -n vectra-edge exec sentinel-a-0 -c sentinel -- valkey-cli --user ratelimit -p 26379 sentinel master ratelimit` (si el campo `ip` o `name` apunta a `valkey-b`, falta la vuelta).
4. `valkey-a` está replicando de `valkey-b` y `valkey-b` no tiene réplicas atrasadas.

## Mitigación
1. `replica-priority` favorece a A (10 en `valkey-a`, 100 en `valkey-b`): al caer la primaria actual, Sentinel promueve a `valkey-a`. La vuelta consiste en provocar esa caída controlada de `valkey-b`.
2. Hazlo en una hora de poco tráfico: `/auth/**` responde 503 durante la conmutación (5 s de `down-after-milliseconds` más la promoción) y los contadores de rate limit se pierden (Valkey no persiste; INF-U2-04).
3. Borra el pod, sin evicción: `kubectl -n vectra-edge delete pod valkey-b-0`. El StatefulSet lo recrea, pregunta a Sentinel por la primaria y entra como réplica de `valkey-a`.
4. `SENTINEL FAILOVER` no está disponible para el usuario `ratelimit` de Sentinel (sus ACL no incluyen `+sentinel|failover`): por eso se usa el borrado del pod.

## Escalamiento
Si pasados 2 minutos `/auth/**` sigue en 503 o Sentinel no promueve a `valkey-a`, trátalo como `RateLimitBackendDown` (`rate-limit-backend-down.md`). Es SEV2: COE en 5 días hábiles (`platform/runbooks/coe-template.md`).

## Verificación
- `kubectl -n vectra-edge exec sentinel-a-0 -c sentinel -- valkey-cli --user ratelimit -p 26379 sentinel master ratelimit` muestra a `valkey-a` como primaria.
- `kubectl -n vectra-edge get statefulset valkey-a valkey-b` muestra los dos `READY 1/1`.
- `kubectl -n envoy-gateway-system get deployment envoy-ratelimit` sigue con sus réplicas disponibles y `/auth/**` ya no responde 503.
