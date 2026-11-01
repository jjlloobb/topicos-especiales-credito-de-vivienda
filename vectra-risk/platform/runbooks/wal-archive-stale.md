# WalArchiveStale

- **Severidad**: SEV1
- **Alerta**: `WalArchiveStale` (U1)

## Síntoma
El último WAL archivado tiene más de 5 min.

## Impacto
El RPO ante pérdida del sitio deja de cumplirse.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Revisa F70 y la credencial de backups.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
