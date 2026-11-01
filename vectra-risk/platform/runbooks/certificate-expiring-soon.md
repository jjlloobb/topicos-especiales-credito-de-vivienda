# CertificateExpiringSoon

- **Severidad**: SEV1 / SEV2
- **Alerta**: `CertificateExpiringSoon` (U1)

## Síntoma
Certificado cerca de vencer.

## Impacto
Pérdida de TLS o de identidad.

## Diagnóstico
1. Consulta la alerta en Grafana (carpeta de operación) y su expresión en `platform/observability/rules/platform-rules.yaml`.
2. Lee el estado sin cambiar nada: `kubectl get pods -A -l vectra.io/criticality`.

## Mitigación
Revisa cert-manager; para el ancla, `trust-anchor-rotation.md`.

## Escalamiento
SEV1 y SEV2 exigen COE en 5 días hábiles (`coe-template.md`).

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, la alerta deja de estar `firing` en Alertmanager.
