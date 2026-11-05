# BreakGlassLogin

- **Severidad**: SEV1
- **Alerta**: `BreakGlassLogin` (U2)

## Síntoma
Hubo un login con éxito en el cliente `security-admin-console` (`keycloak_user_events_total{event="login",client_id="security-admin-console",error=""}`), en cualquier realm. La métrica de Keycloak 26.8.1 no lleva el usuario: la alerta no distingue quién entró (decisión B10).

**Límites de la alerta** (la expresión lleva dos ramas): `increase` ve los logins sobre una serie que ya existía; para el primer login de una serie nueva, la segunda rama solo dispara si el target `keycloak` se raspó con `up == 1` hace 5 minutos (así un hueco de scrape no la dispara por un login antiguo). Riesgo residual: el primer login de un pod que lleva menos de 5 minutos raspándose, o de uno cuyo target no se raspaba hace 5 minutos, no dispara hasta el siguiente login. Si `up{job="keycloak"}` falla durante una sesión de break-glass, busca los eventos `LOGIN` en Loki o en el log, como en el diagnóstico.

## Impacto
En prod, el único humano con `realm-admin` es `break-glass`, y la consola solo se alcanza por `hostname-admin` interno con un port-forward aprobado (BR-U2-12). Un login ahí sin aprobación es un acceso administrativo no autorizado. Cualquier otro humano que entre también es SEV1.

## Diagnóstico
1. Busca la aprobación del port-forward y de la ventana de break-glass (registro de cambios del banco).
2. ¿Quién fue? Eventos `LOGIN` con `clientId=security-admin-console` en Loki (Grafana, Explore) o en el log: `kubectl -n vectra-identity logs -l app.kubernetes.io/name=keycloak --tail=500`.
3. Sesiones activas del realm desde la consola de administración, o `kubectl -n vectra-identity get pods -l app.kubernetes.io/name=keycloak`.
4. Cambios hechos: revisa los eventos de administración y corre el diff del realm (`realm-drift.md`).

## Mitigación
1. Con aprobación, registra el uso y rota la credencial de `break-glass` al terminar.
2. Sin aprobación, cierra las sesiones del realm, rota la credencial de `break-glass` en la bóveda y abre un incidente de seguridad.
3. Si hubo cambios de configuración, `RealmDrift` también va a disparar: reconcilia desde Git con `keycloak-config-cli`.

## Escalamiento
SEV1: COE en 5 días hábiles (`platform/runbooks/coe-template.md`) y aviso inmediato a seguridad de la información.

## Verificación
- `kubectl -n vectra-identity get cronjob realm-drift` muestra una ejecución reciente sin diferencias nuevas.
- La alerta deja de estar `firing` en Alertmanager (`amtool alert query alertname=BreakGlassLogin`); es una ventana de `increase` de 5 minutos.
- `promtool test rules identity-edge/observability/rules/tests/*.yaml` en el repositorio (la alerta dispara y no dispara con series sintéticas).
