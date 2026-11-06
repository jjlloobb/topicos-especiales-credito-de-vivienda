# BreakGlassLogin

- **Severidad**: SEV1
- **Alerta**: `BreakGlassLogin` (U2)

## Síntoma
Hubo un login con éxito en el cliente `security-admin-console` (`keycloak_user_events_total{event="login",client_id="security-admin-console",error=""}`), en cualquier realm. La métrica de Keycloak 26.8.1 no lleva el usuario: la alerta no distingue quién entró (decisión B10).

**Límites de la alerta** (decisión B11 de P-U2-09; los minutos son los medidos con `promtool`, `revisiones/U02-T13/b11_scenarios.py`). La expresión tiene tres ramas: `increase` sobre 5 minutos; una serie que no se vio en la última hora y aparece con un valor mayor que cualquier valor previo (cuenta como login nuevo); y una serie nueva cuyo pod se raspaba con `up == 1` hace 5 minutos. Con eso:
- **Detecta**: un login sobre una serie que ya existía dispara mientras `increase` lo ve (5 minutos). Un pod nuevo (el login aparece en el minuto 2 o 4) dispara desde que aparece la serie y dura 5 minutos. Un login durante un hueco de scrape (`up == 0`) dispara cuando vuelve el scrape: la serie nueva en el minuto 14 dispara en 14-18, y la serie que ya existía en el minuto 15 dispara en 15-19.
- **Primer scrape**: una serie que ya trae un login en el primer scrape dispara en 0-4 minutos desde que Prometheus la ve. Lo mismo pasa al arrancar Prometheus o un pod: es indistinguible de un login nuevo.
- **Modelo de *staleness* de las mediciones de abajo.** Un «hueco de N min» son N minutos sin muestra de `up`. Cuando un scrape falla, Prometheus escribe `up == 0` y una marca de *stale* en las series del pod. Cuando Prometheus mismo está caído no escribe nada, ni marcas: las últimas muestras se siguen viendo hasta 5 minutos (lookback). Cada medición dice qué serie lleva marca de *stale* al empezar el hueco: ninguna, solo `X` (el contador de logins), solo `up`, o las dos. Los modelos «solo `X`», «solo `up`» y «las dos» son construcciones de los escenarios (`FP_*` y `OM_*` de `LIMITES` en `b11_scenarios.py probe`); no se observaron en un Prometheus real.
- **Falso positivo** (la serie vuelve con el mismo valor, no hubo login). Con ninguna serie con marca, solo `up` con marca o las dos con marca: no dispara con huecos de 2 a 15 minutos. Solo si `X` lleva la marca y `up` no, dispara al volver, y la duración depende del hueco: 2 min de hueco, 2 min de alerta; 3, 3; 4, 4; 5, 4; 6, 3; 7, 2; 8, 1; de 9 a 15 min de hueco, no dispara. La causa: `X` tiene marca y `up offset 5m` aún ve su última muestra por el lookback, así que la serie parece nueva y su pod parecía sano hace 5 minutos. Con un hueco de más de 1 hora (la serie no se vio en la última hora) dispara 5 minutos tras volver, aunque no haya login (escenario `L`).
- **Omisión y disparo parcial** (el pod se reinicia dentro de un hueco y el primer login cae en el scrape en que vuelve la serie; el contador baja de 3 a 1). Con ninguna serie con marca, solo `up` con marca o las dos: con 2 min de hueco dispara 2 min (no los 5 de la ventana), con 3 min dispara 1 min, y **desde 4 min de hueco no dispara**. Con solo `X` con marca: dispara con huecos de 2 a 8 min (con 2 y 3 min dispara, se apaga y vuelve a disparar) y **desde 9 min de hueco no dispara** (el escenario `E`, de 15 min, tampoco).
- **Reinicio normal del pod** (`up == 0` durante 3 scrapes, `X` con marca, el contador previo valía 1): si el login cae en el mismo scrape en que vuelve el pod, **no dispara nunca**, porque el contador vuelve a 1, igual que antes, y ninguna rama lo ve como login. Si el login cae 1 a 4 min después, dispara con retraso: siempre desde 5 min después de que volvió el scrape (la rama 3 mira `up` de hace 5 minutos), o sea de 4 a 1 min tarde, y dura de 1 a 4 min. Desde 5 min después, dispara a tiempo (escenarios `RN_0` a `RN_6`).
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
