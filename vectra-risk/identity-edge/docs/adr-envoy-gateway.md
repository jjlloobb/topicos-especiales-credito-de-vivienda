# ADR — Envoy Gateway v1.9.3: verificación de la versión pinneada (U02-T10, Paso 8)

Estado: **parcial**. Los puntos 1, 3, 4 y 5 están verificados; el punto 2 (modo de fallo, W3) no se puede expresar como lo pide el diseño y espera una decisión. Código citado: tag `v1.9.3` de `envoyproxy/gateway`, Envoy v1.39.5. Comprobado con `egctl` v1.9.3 (`x translate`) y `gh api repos/envoyproxy/gateway/contents/<ruta>?ref=v1.9.3`.

## 1. Data plane en `vectra-edge` con `deploy.type: GatewayNamespace`
- `internal/provider/kubernetes/controller.go`: `gatewayNamespaceMode: cfg.EnvoyGateway.GatewayNamespaceMode()`; `envoyLabels` de `internal/infrastructure/kubernetes/proxy/resource_provider.go` agrega `GatewayNameLabel` en ese modo. El Deployment y el Service nacen en el namespace del `Gateway`. Se puede: `flows.yaml` y las NetworkPolicies no se tocan.
- Con `GatewayNamespace` el EnvoyProxy de `Gateway.spec.infrastructure.parametersRef` se busca en el namespace del Gateway (`processGatewayParamsRef`); el de la `GatewayClass` lleva `namespace` explícito (`processGatewayClassParamsRef`).
- Hallazgo: el sidecar `shutdown-manager` toma su imagen de `EnvoyGateway.provider.kubernetes.shutdownManager.image` (`expectedShutdownManagerImage`), que el chart fija a `docker.io/envoyproxy/gateway:v1.9.3`, no del `EnvoyProxy`. Kyverno `restrict-registries` y `disallow-latest` lo rechazarían en `vectra-edge`. El diseño no fija el espejo ni el digest: **detenido** (ver informe).
- Hallazgo: `require-criticality-label` valida `metadata.labels` del Deployment, que el controlador arma con `getLabels()` (etiquetas de `Gateway.spec.infrastructure.labels`), no con `pod.labels`.

## 2. Modo de fallo por ruta (P-U2-01): alternativa 2, **bloqueada**
- `internal/xds/translator/ratelimit.go`: un filtro por dominio; dominio = `stripRuleIndexSuffix(rule.Name)` = `<ns>/<política>`; nombre `envoy.filters.http.ratelimit/<ns>/<política>`, más el del listener (`envoy.filters.http.ratelimit`). `failure_mode_deny` solo sale de `GlobalRateLimit.FailClosed` (global del controlador).
- `EnvoyPatchPolicy` (`jsonpatch.go`, `envoypatchpolicy.go`): se verificó con `egctl` que un `JSONPatch` sobre el `Listener` `vectra-edge/api-gateway/https` con `jsonPath` `..http_filters[?(@.name=='envoy.filters.http.ratelimit/vectra-edge/auth-rate-limits')].typed_config` fija `failureModeDeny: true` y `statusOnError: ServiceUnavailable`, y la política queda `Accepted`.
- Bloqueo, comprobado con `egctl` y en `backendtrafficpolicy.go`:
  - `mergeType` solo vale con destinos xRoute (`mergeType can only be used with xRoute targets`): `auth-rate-limits` no puede llevarlo en el `Gateway`.
  - Dos `BackendTrafficPolicy` sobre el mismo `Gateway` sin `sectionName`: la segunda queda `Accepted: False`, `Conflicted` (`resolveBackendTrafficPolicyGatewayTargetRef`).
  - Con una en el `Gateway` y otra en el listener `https`, ambas se aceptan, pero una política de ruta con `mergeType` se mezcla con un solo padre (el del listener si existe, si no el del Gateway; `processBackendTrafficPolicyForRoute`) y `edge-rate-limits` queda `Overridden`: desaparece el filtro y el límite global de 200/s.
- Opciones para el orquestador: (a) contadores de `/auth/**` en las políticas por regla `auth-read` y `auth-write` (dominios `.../auth-read` y `.../auth-write`, verificado aceptado; parte el contador por clase de método); (b) otro diseño de rutas. No se eligió ninguna.

## 3. Servicio de rate limit del controlador (W1)
- `internal/cmd/egctl/translate.go` usa `ratelimit.GetServiceURL(namespace, dnsDomain)`; el filtro apunta al cluster `ratelimit_cluster` que atiende el `envoy-ratelimit` que despliega el controlador (`internal/infrastructure/kubernetes/ratelimit`). Los values no llevan `rateLimit` (prueba `test_envoy_gateway_values.py`).

## 4. IP real (W2)
- `internal/xds/translator/listener.go`: `useRemoteAddress := true` y pasa a `false` si `originalIPDetectionExtensions` no es nil; `xffNumTrustedHops` **resta 1** al valor del usuario (`numTrustedHops: 1` genera `xff_num_trusted_hops: 0` con la extensión `xff` y `use_remote_address: false`: Envoy confía en el `X-Forwarded-For` del cliente).
- Por eso `numTrustedHops: 0` tampoco sirve (también configura la extensión). Hay que omitir `clientIPDetection`. La prueba de xDS no puede mirar solo `xff_num_trusted_hops > 0`: debe exigir `use_remote_address: true` y sin `original_ip_detection_extensions`.

## 5. Binding K14
El chart `gateway-helm` v1.9.3 con los values de `platform/operators/envoy-gateway.yaml` concede, para el ServiceAccount `envoy-gateway`, lo siguiente que K14 no menciona (la prueba `test_everything_the_chart_grants_beyond_k14_is_listed_in_the_adr` exige que cada línea esté aquí). Además, el `ClusterRole` `cluster-infra-manager` da la gestión de Deployments, Services y ConfigMaps en todo el clúster, no solo en `vectra-edge` y `envoy-gateway-system`. **No se recortó**: se reporta.

### Concesiones del chart que K14 no menciona
- `core/events`: create, patch (envoy-gateway-system)
- `core/namespaces`: get, list, watch (cluster)
- `core/nodes`: get, list, watch (cluster)
- `core/pods`: get, list, patch, update, watch (cluster)
- `core/pods/binding`: get, list, patch, update, watch (cluster)
- `core/secrets`: get, list, watch (cluster)
- `core/serviceaccounts`: create, delete, deletecollection, get, list, patch, watch (cluster, envoy-gateway-system)
- `apps/daemonsets`: create, delete, deletecollection, get, list, patch, watch (cluster, envoy-gateway-system)
- `authentication.k8s.io/tokenreviews`: create (cluster)
- `autoscaling/horizontalpodautoscalers`: create, delete, deletecollection, get, list, patch, watch (cluster, envoy-gateway-system)
- `certificates.k8s.io/clustertrustbundles`: get, list, watch (cluster, envoy-gateway-system)
- `coordination.k8s.io/leases`: create, delete, get, list, patch, update, watch (envoy-gateway-system)
- `discovery.k8s.io/endpointslices`: get, list, watch (cluster)
- `gateway.envoyproxy.io/backends/status`: update (cluster)
- `gateway.envoyproxy.io/backendtrafficpolicies/status`: update (cluster)
- `gateway.envoyproxy.io/clienttrafficpolicies/status`: update (cluster)
- `gateway.envoyproxy.io/envoyextensionpolicies/status`: update (cluster)
- `gateway.envoyproxy.io/envoypatchpolicies/status`: update (cluster)
- `gateway.envoyproxy.io/envoyproxies/status`: update (cluster)
- `gateway.envoyproxy.io/securitypolicies/status`: update (cluster)
- `gateway.networking.k8s.io/backendtlspolicies/status`: update (cluster)
- `gateway.networking.k8s.io/gatewayclasses`: get, list, patch, update, watch (cluster)
- `gateway.networking.k8s.io/gatewayclasses/status`: update (cluster)
- `gateway.networking.k8s.io/gateways/status`: update (cluster)
- `gateway.networking.k8s.io/grpcroutes/status`: update (cluster)
- `gateway.networking.k8s.io/httproutes/status`: update (cluster)
- `gateway.networking.k8s.io/listenersets/status`: update (cluster)
- `gateway.networking.k8s.io/tcproutes/status`: update (cluster)
- `gateway.networking.k8s.io/tlsroutes/status`: update (cluster)
- `gateway.networking.k8s.io/udproutes/status`: update (cluster)
- `multicluster.x-k8s.io/serviceimports`: get, list, watch (cluster)
- `policy/poddisruptionbudgets`: create, delete, deletecollection, get, list, patch, watch (cluster, envoy-gateway-system)
