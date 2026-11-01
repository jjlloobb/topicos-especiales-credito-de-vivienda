# GrafanaFolderPermissionsDrift

- **Severidad**: SEV3
- **Alerta**: `GrafanaFolderPermissionsDrift` (U1)

## Síntoma
Permisos de carpeta distintos de `folder-permissions.yaml`.

## Impacto
Acceso indebido a dashboards.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.
3. Lee el log del CronJob: `kubectl logs -n vectra-observability job/<ultimo-grafana-folder-check>`. Un equipo que falta aparece como `Deriva en <carpeta>`; el Job lo crea en su siguiente sync. Un 401 no es deriva: es el token vencido o sin crear, y el CronJob falla sin empujar la métrica (`install.md`, token de Grafana).

## Mitigación
Reaplica el Job con un sync de la Application de observabilidad.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
