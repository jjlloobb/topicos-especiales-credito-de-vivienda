# AuthDeniedBurst

- **Severidad**: SEV2
- **Alerta**: `AuthDeniedBurst` (U2)

## Síntoma
Más de 20 denegaciones por minuto durante 5 minutos: `LOGIN_ERROR` de `keycloak_user_events_total` (`event="login"` con `error` distinto de vacío) más `vectra_authz_denied_total` de U0 (401 y 403).

## Impacto
Puede ser un ataque (relleno de credenciales, enumeración) o una regresión (un despliegue que rompió la autorización). Los usuarios legítimos pueden estar quedando fuera.

## Diagnóstico
1. Separa las dos fuentes en Grafana (Explore, Prometheus): `sum by (error, client_id, realm) (rate(keycloak_user_events_total{event="login",error!=""}[5m]))` y `sum by (code, route_template) (rate(vectra_authz_denied_total[5m]))`.
2. Si dominan los `error` de Keycloak, mira los eventos en el log: `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=500`.
3. Si domina una `route_template` de U0, mira el despliegue reciente: `kubectl get pods -A --sort-by=.metadata.creationTimestamp`.
4. Relaciona con el límite de tasa: la alerta `RateLimitBackendDown` en `rate-limit-backend-down.md`.

## Mitigación
1. Con un solo origen o un solo `client_id`, bloquéalo en el gateway (`identity-edge/gateway/routes.yaml`, por PR).
2. Si hubo credenciales válidas tras muchos fallos, fuerza el cambio de contraseña de esas cuentas desde la consola de administración, con port-forward aprobado (BR-U2-12).
3. Si es una regresión de U0, revierte el despliegue en Git.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`platform/runbooks/coe-template.md`).

## Verificación
- En Grafana, la suma de las dos expresiones del diagnóstico (`rate(...[5m]) * 60`) queda por debajo de 20 durante 10 minutos: `amtool alert query alertname=AuthDeniedBurst` ya no la lista.
- La alerta deja de estar `firing` en Alertmanager (`amtool alert query alertname=AuthDeniedBurst`).
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
