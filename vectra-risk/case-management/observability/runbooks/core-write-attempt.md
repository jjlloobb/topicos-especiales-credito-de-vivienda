# CoreWriteAttempt

- **Severidad**: SEV2
- **Alerta**: `CoreWriteAttempt` (U8), en `case-management/observability/rules/case-management.rules.yaml`; solo se rinde con `coreMock.enabled = true` (kind y staging).

Dispara con `increase(vectra_core_write_attempts_total[5m]) > 0` (el mock recibió un `POST /v1/credits/{id}/status`) o con una denegación nueva de la ruta `core-mock-catch-all` en `vectra-mock` (la serie `inbound_http_authz_deny_total` de Linkerd, que **nace en 1** y por eso la expresión la resta desplazada 5 minutos).

## Síntoma

Alguien intentó escribir en el core bancario. El core es de solo lectura (RT-5, US-603): la capa L7 de Linkerd debe rechazar con 403 todo lo que no sea `GET /v1/credits/{id}` de `case-service`, y el mock rechaza la escritura aunque llegue.

- Si dispara la serie de **Linkerd**: el proxy denegó el `POST` (la capa L7 funcionó).
- Si dispara el **contador del mock**: el `POST` llegó al mock, es decir, Linkerd lo dejó pasar. Es el caso grave: la capa L7 falló.

**En la demostración de RT-5 (D3) la alerta es la evidencia esperada.** El Job `rt5-demo-<runId>` envía un `POST` al mock; el proxy lo deniega (403 con `l5d-proxy-error`), la serie de Linkerd nace en 1 y la alerta dispara con `vectra_core_write_attempts_total` en 0. Un contador del mock mayor que 0 en esa demostración sí es un fallo.

## Impacto

En la demostración, ninguno: es la prueba de que la escritura es imposible. Fuera de ella, un intento real de escribir en el core, o una regla L7 rota que lo habría permitido.

## Diagnóstico

1. ¿Es la demostración? Busca un Job `rt5-demo-*` reciente: `kubectl --context kind-vectra -n vectra-app get jobs -l app.kubernetes.io/part-of=case-management`.
2. ¿Qué serie disparó? Consulta las dos en Prometheus:

```bash
kubectl --context kind-vectra -n vectra-observability exec prometheus-kube-prometheus-stack-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=vectra_core_write_attempts_total'
kubectl --context kind-vectra -n vectra-observability exec prometheus-kube-prometheus-stack-prometheus-0 -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=inbound_http_authz_deny_total%7Bnamespace%3D%22vectra-mock%22%2Croute_name%3D%22core-mock-catch-all%22%7D'
```

3. Quién lo envió: los registros de denegación del proxy del mock y los del mock:

```bash
kubectl --context kind-vectra -n vectra-mock logs deploy/core-banking-mock -c linkerd-proxy | grep -i "authz\|forbidden"
kubectl --context kind-vectra -n vectra-mock logs deploy/core-banking-mock -c core-banking-mock | grep -i "write\|403"
```

4. **Limitación del `offset 5m`**: la serie de Linkerd es del pod del mock. Si el pod se reemplaza (un rollout, un reinicio) la serie vieja desaparece y la nueva nace en 1 o en el valor que tenga: una denegación ya registrada puede dispararla otra vez, y una denegación que ocurrió justo antes del reemplazo puede no verse. Ante la duda, no te fíes solo de la alerta: revisa los registros de denegación del proxy y del mock (paso 3).

## Mitigación

1. En la demostración de RT-5 no hay nada que mitigar: anota la alerta como evidencia y verifica que `vectra_core_write_attempts_total` siga en 0.
2. Si el contador del mock creció: Linkerd dejó pasar un `POST`. Revisa que la `HTTPRoute` `core-mock-catch-all` y el `Server` `core-banking-mock-8080` existan en `vectra-mock` y que no haya una `AuthorizationPolicy` para esa ruta (`kubectl --context kind-vectra -n vectra-mock get httproute,authorizationpolicy,server`). Son de U1 (`platform/network/flows.yaml`, `http_routes.core-banking-mock`): no las edites a mano; corrige `flows.yaml` y regenera.
3. No habilites `core:write-credit` para nadie: la escritura al core es imposible por diseño.

## Escalamiento

Si el contador del mock creció fuera de la demostración, escala de inmediato al responsable de U1 (red) y de seguridad: la capa L7 que protege al core falló. Registra el caso en el análisis posterior (`platform/runbooks/coe-template.md`).

## Verificación

```bash
# El contador del mock sigue en 0 en cada réplica (desde un pod con python, a 8081):
kubectl --context kind-vectra -n vectra-mock exec deploy/core-banking-mock -c core-banking-mock -- python -c "import urllib.request;print([l for l in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if l.startswith('vectra_core_write_attempts_total')])"
# La alerta, en Alertmanager (en la demostración, firing; después, sin alertas nuevas):
kubectl --context kind-vectra -n vectra-observability exec alertmanager-kube-prometheus-stack-alertmanager-0 -c alertmanager -- wget -qO- 'http://localhost:9093/api/v2/alerts?filter=alertname%3DCoreWriteAttempt'
# Las reglas del repositorio:
promtool test rules case-management/observability/rules/tests/core-write-attempt.yaml
```

Esperado: el contador en `0.0`; la alerta `firing` solo mientras dure la serie nueva de Linkerd (5 minutos) y `SUCCESS` en `promtool`.
