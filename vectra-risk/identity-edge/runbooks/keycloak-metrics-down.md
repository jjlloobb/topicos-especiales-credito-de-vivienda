# KeycloakMetricsDown

- **Severidad**: SEV2
- **Alerta**: `KeycloakMetricsDown` (U2)

## Síntoma
Prometheus no está raspando las métricas de Keycloak: `up{job="keycloak"} == 0` o la serie `up{job="keycloak"}` no existe (`absent`), durante 5 minutos (decisión B11 de P-U2-09). La expresión está en `identity-edge/observability/rules/identity-edge-rules.yaml`.

## Impacto
Sin las métricas de Keycloak (`keycloak_user_events_total`), `BreakGlassLogin` (SEV1) queda ciega: un login en `security-admin-console` durante el hueco puede no disparar nunca (ver los límites en `break-glass-login.md`). Tampoco se ven los eventos de `AuthDeniedBurst` sobre el login. Keycloak puede seguir sirviendo, así que esta alerta no implica una caída: `KeycloakDown` es la que la señala.

## Diagnóstico
1. Estado de los targets: en Prometheus, `up{job="keycloak"}`, o la página Targets (`kubectl -n vectra-observability port-forward svc/kube-prometheus-stack-prometheus 9090`).
2. Si la serie no existe, mira si el monitor existe: `kubectl -n vectra-identity get podmonitor keycloak` (puerto 9000, HTTPS; `identity-edge/observability/monitors/monitors.yaml`).
3. Si `up` vale 0, el scrape falla: el certificado `keycloak-tls` (`kubectl -n vectra-identity get certificate keycloak-tls`), la `NetworkPolicy` del puerto 9000 (flujo F60 de `platform/network/flows.yaml`) o el endpoint `/metrics` de gestión (`KC_METRICS_ENABLED`, `management` en 9000).
4. Pods: `kubectl -n vectra-identity get pods -l app.kubernetes.io/name=keycloak` y su log: `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=200`.
5. Si los demás targets tampoco aparecen, el problema es de Prometheus (`platform/runbooks/`).

## Mitigación
1. Corrige la causa del scrape: renueva `keycloak-tls`, restablece la `NetworkPolicy` del 9000 desde Git (`vectra-risk-gitops`) o restaura el `PodMonitor`; no edites el clúster a mano.
2. Mientras dure el hueco, las sesiones de `security-admin-console` hay que vigilarlas en Loki o en el log (eventos `LOGIN`, `clientId=security-admin-console`), porque `BreakGlassLogin` no las ve.
3. Al volver el scrape, revisa si hubo logins en `security-admin-console` durante el hueco y trátalos como en `break-glass-login.md`.

## Escalamiento
SEV2: COE en 5 días hábiles si el hueco duró más de una hora o coincidió con una sesión de break-glass (`platform/runbooks/coe-template.md`). Avisa a seguridad de la información si hubo logins sin aprobación durante el hueco.

## Verificación
- `up{job="keycloak"}` vale 1 en cada pod de Keycloak.
- La alerta `KeycloakMetricsDown` deja de estar `firing` en Alertmanager (`amtool alert query alertname=KeycloakMetricsDown`).
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
