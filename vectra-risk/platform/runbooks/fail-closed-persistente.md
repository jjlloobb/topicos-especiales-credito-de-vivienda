# FailClosedPersistente

- **Severidad**: SEV2
- **Alerta**: `FailClosedPersistente` (U1)

## Síntoma
Casos en `no_disponible` tras agotar reintentos.

## Impacto
Las solicitudes no reciben recomendación.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Revisa la causa en la consola; US-112.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
