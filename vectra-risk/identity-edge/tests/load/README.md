# Prueba de carga de U2 (U02-T15, Paso 14)

`identity.js` es la especificación de NFR-U2-10..12. **La ejecución es del Paso 16** (operador, kind, con aprobación). Aquí solo se
valida en estático: `make -C identity-edge load-inspect` (parte de `check`) corre `k6 inspect` sin entorno y compara umbrales,
escenarios y perfil con el diseño. k6 es el binario pinneado de `platform/tools.env` (excepción J2 a la regla de U12).

## Escenarios y umbrales

| Escenario | Qué hace |
|---|---|
| `users` | 200 VUs (`load-001..200`): login del navegador de `vectra-console` (PKCE S256) y renovación del token cada 60 s. Un login por VU: 200 en 2 min = 1,7/s (J5). |
| `services` | 10 clientes de servicio (J6), `client_credentials` con `private_key_jwt` ES256 cada 300 s. |
| `jwks` | 20 lecturas/s del JWKS del realm. |
| `console-burst` | `load-001` contra `/api/console/**` (eco): 5/s y 9 s de 40/s cada 30 s. Por encima de 20/s se espera 429 con `Retry-After: 1`. |
| `overhead` | `load-002`, el mismo request al eco por el gateway y directo; NFR-U2-11 en `handleSummary` (J3). |

Umbrales (`thresholds`): `http_req_duration{flow:login}` p95 < 500, `{flow:token}` p95 < 200, `{flow:jwks}` p95 < 50, `http_req_failed` < 1 %
(un 429 en los logins cuenta como fallo, J5), `checks` > 99 %. Perfil: 2 min de subida y 15 min sostenidos (J7). El `flow:login` mide el GET
de autorización y el POST de la contraseña; el canje del código y la renovación son `flow:token`.

## Antes de correr (Paso 16)

1. `uv run python identity-edge/tests/load/seed_users.py create` crea `load-001..200` (rol `analista`, sin OTP: su subflujo de MFA solo
   aplica si ya hay factor configurado). `delete` los borra. Variables: `VECTRA_E2E_ADMIN_URL` (con `/auth`), `VECTRA_E2E_ADMIN_USER`,
   `VECTRA_E2E_ADMIN_PASSWORD`, `K6_LOAD_PASSWORD` (≥ 14 caracteres, política del realm) y, si hace falta, `VECTRA_E2E_ADMIN_CA_BUNDLE`.
2. El eco del Paso 13 desplegado como `console-bff`, y un port-forward a él.
3. Variables de k6: `K6_BASE_URL` (`https://vectra.localtest.me`), `K6_ECHO_DIRECT_URL` (el port-forward, `http://127.0.0.1:<puerto>`),
   `K6_CLIENT_KEYS_DIR` (ruta **absoluta** con `<clientId>.pem`, llave ES256 en PKCS#8 `BEGIN PRIVATE KEY`, desde Vault; J6), `K6_LOAD_PASSWORD`.
   La CA del gateway: `SSL_CERT_FILE=<bundle>` (k6 no tiene opción propia). Sin esas variables `setup()` falla nombrándolas.
4. `make -C identity-edge load` (no entra en `check`). Escribe `summary.json` y `overhead-verdict.json` en `identity-edge/.tools/load/`.
   k6 v2.3.0 sale en 0 aunque `handleSummary` falle, por eso el target lee el veredicto y sale con error si NFR-U2-11 no se cumple.

## NFR-U2-12 (J3): consulta PromQL

El servicio de rate limit publica (v1.9.3, `statsd_conf.yaml` de Envoy Gateway) el histograma `ratelimit_service_response_time_seconds`
con la etiqueta `grpc_method`. El operador corre esto durante la carga y exige **≤ 0,002** (2 ms):

```promql
histogram_quantile(0.95, sum by (le) (rate(ratelimit_service_response_time_seconds_bucket{grpc_method="ShouldRateLimit"}[1m])))
```

Mide el tiempo de servicio (incluida la llamada a Valkey), no la red entre Envoy y el servicio. Si el exportador usa los buckets por
defecto (el primero es 5 ms), el cuantil se interpola dentro de ese bucket y 2 ms no se resuelve: en ese caso se anota el resultado y la
fracción `sum(rate(..._bucket{le="0.005"}[1m])) / sum(rate(..._count[1m]))` (ver la bitácora de U02-T15).

NFR-U2-30, CPU de Valkey < 50 % durante la misma carga:

```promql
max by (pod) (rate(container_cpu_usage_seconds_total{namespace="vectra-edge",pod=~"valkey-.*",container="valkey"}[1m]))
  / on (pod) max by (pod) (kube_pod_container_resource_limits{namespace="vectra-edge",pod=~"valkey-.*",container="valkey",resource="cpu"})
```
