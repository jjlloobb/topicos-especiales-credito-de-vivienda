# RestoreDrillRetentionViolation

- **Severidad**: SEV2
- **Alerta**: `RestoreDrillRetentionViolation` (U1)

## Síntoma
Una restauración devolvería identificadores vencidos.

## Impacto
Incumple la retención (BR-U8-20).

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Revisa `case-retention`.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
