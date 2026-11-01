# RecommendationSLOBurnSlow

- **Severidad**: SEV3
- **Alerta**: `RecommendationSLOBurnSlow` (U1)

## Síntoma
Consumo lento del presupuesto de error.

## Impacto
Riesgo para el SLO mensual.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Revisa la tendencia.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
