# BreakGlassLogin

- **Severidad**: SEV1
- **Alerta**: `BreakGlassLogin` (U2)

## Síntoma
Hubo un login con éxito en el cliente `security-admin-console` (`keycloak_user_events_total{event="login",client_id="security-admin-console",error=""}`), en cualquier realm. La métrica de Keycloak 26.8.1 no lleva el usuario: la alerta no distingue quién entró (decisión B10).

**Límites de la alerta** (decisión B11 de P-U2-09; los minutos son los medidos con `promtool`, `revisiones/U02-T13/b11_scenarios.py`). La expresión tiene tres ramas: `increase` sobre 5 minutos; una serie que no se vio en la última hora y aparece con un valor mayor que cualquier valor previo (cuenta como login nuevo); y una serie nueva cuyo pod se raspaba con `up == 1` hace 5 minutos. Con eso:
- **Detecta**: un login sobre una serie que ya existía dispara mientras `increase` lo ve (5 minutos). Un pod nuevo (el login aparece en el minuto 2 o 4) dispara desde que aparece la serie y dura 5 minutos. Un login durante un hueco de scrape (`up == 0`) dispara cuando vuelve el scrape: la serie nueva en el minuto 14 dispara en 14-18, y la serie que ya existía en el minuto 15 dispara en 15-19.
- **Primer scrape**: una serie que ya trae un login en el primer scrape dispara en 0-4 minutos desde que Prometheus la ve. Lo mismo pasa al arrancar Prometheus o un pod: es indistinguible de un login nuevo.
- **Falso positivo**: si Prometheus no raspa nada durante 5 a 10 minutos (por ejemplo, reinicio del propio Prometheus, sin marcas de *stale*), al volver dispara una vez, durante 1 minuto, porque `up offset 5m` aún ve la última muestra. Con un hueco de más de 1 hora (la serie no se vio en la última hora) dispara 5 minutos tras volver, aunque no haya login.
- **Omisión**: si el pod se reinicia durante un hueco de scrape de más de 10 minutos y luego hay un login (el contador baja, por ejemplo de 3 a 1), no dispara.
- **Alerta ciega**: si el scrape falla (TLS, `NetworkPolicy` del 9000), `KeycloakMetricsDown` (SEV2, `keycloak-metrics-down.md`) avisa tras 5 minutos. Mientras dure, busca los eventos `LOGIN` en Loki o en el log, como en el diagnóstico.

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
