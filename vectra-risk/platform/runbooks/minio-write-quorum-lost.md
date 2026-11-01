# MinioWriteQuorumLost

- **Severidad**: SEV2
- **Alerta**: `MinioWriteQuorumLost` (U1)

## Síntoma
MinIO sin quórum de escritura.

## Impacto
Se detienen escrituras de logs, trazas y artefactos; los modelos desplegados siguen.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Recupera la zona; ver INF-U1-03.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
