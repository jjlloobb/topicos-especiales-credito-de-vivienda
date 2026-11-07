# GatewayHighLatency

- **Severidad**: SEV3
- **Alerta**: `GatewayHighLatency` (U2)

## Síntoma
El p95 de `envoy_http_downstream_rq_time` menos el p95 de `envoy_cluster_upstream_rq_time` supera 5 ms durante 15 minutos. Es una aproximación del sobrecosto del gateway: NFR-U2-11 se mide con la prueba con y sin gateway.

**Qué mide (B14).** El downstream es solo el del listener HTTP del `api-gateway` (`envoy_http_conn_manager_prefix="https-10443"`: Envoy Gateway v1.9.3 llama `https-<puerto del contenedor>` al `stat_prefix` del HCM y suma 10000 al 443 del Gateway). No cuenta los listeners de estadísticas (`eg-stats-http`, 19001) ni de readiness (`eg-ready-http`). El upstream es solo el de los clusters de las rutas (`envoy_cluster_name=~"httproute/vectra-edge/.+"`). No cuenta el cluster del rate limit (`ratelimit_cluster`), los de JWKS de las `SecurityPolicy` (`securitypolicy/...`) ni los del bootstrap. Si cambias el puerto del listener o activas el esquema de nombres V2 de Envoy Gateway, el prefijo cambia y la prueba `test_alert_rules.py` lo detecta.

## Impacto
El gateway agrega latencia a todas las peticiones. Aún no es una caída, pero consume el presupuesto de latencia de los servicios.

## Diagnóstico
1. Estado del data plane: `kubectl -n vectra-edge get pods -l gateway.envoyproxy.io/owning-gateway-name=api-gateway` y `kubectl -n vectra-edge top pods`.
2. HPA del data plane: `kubectl -n vectra-edge get hpa`.
3. Latencia del rate limit (`/auth/**`): `kubectl -n envoy-gateway-system get deployment envoy-ratelimit`.
4. Compara los dos p95 por separado en Grafana (Explore, Prometheus), con `histogram_quantile(0.95, sum by (le) (rate(envoy_http_downstream_rq_time_bucket{job="envoy-data-plane",envoy_http_conn_manager_prefix="https-10443"}[5m])))` y, para el backend, `histogram_quantile(0.95, sum by (le) (rate(envoy_cluster_upstream_rq_time_bucket{job="envoy-data-plane",envoy_cluster_name=~"httproute/vectra-edge/.+"}[5m])))`. Quita el filtro de clusters y mira cada `envoy_cluster_name` para ver qué ruta lo causa.

## Mitigación
1. Si el data plane está saturado (CPU o HPA al máximo), sube las réplicas máximas por PR (`identity-edge/gateway/values/<entorno>.yaml`).
2. Si el sobrecosto viene del rate limit, mira Valkey y `envoy-ratelimit` (`rate-limit-backend-down.md`).
3. Si es el filtro de autenticación (JWT), revisa el refresco del JWKS y la latencia de Keycloak.

## Escalamiento
SEV3: sin COE. Si la latencia degrada el SLO de recomendaciones, sigue `platform/runbooks/recommendation-slo-burn-fast.md`.

## Verificación
- `kubectl -n vectra-edge get hpa` muestra réplicas por debajo del máximo.
- La diferencia de p95 baja de 5 ms (la expresión del diagnóstico) y la alerta deja de estar `firing` en Alertmanager.
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
