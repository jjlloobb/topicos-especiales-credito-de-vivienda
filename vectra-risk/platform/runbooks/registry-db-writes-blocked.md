# RegistryDbWritesBlocked

- **Severidad**: SEV1
- **Alerta**: `RegistryDbWritesBlocked` (U1)

## Síntoma
`registry-db` sin réplica síncrona.

## Impacto
El registro no confirma escrituras y las recomendaciones fallan cerradas.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Sigue `zone-failover.md`.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
