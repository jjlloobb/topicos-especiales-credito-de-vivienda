# LogFieldsDropped

- **Severidad**: SEV3
- **Alerta**: `LogFieldsDropped` (U1; contrato P-U0-04 de U0)

## Síntoma
`vectra_log_fields_dropped_total{service, event}` creció en los últimos 15 min: un servicio intentó registrar un campo que `LogRecord` no permite.

## Impacto
El filtro `allowlist_filter` descartó el campo: **no salió** a los logs, así que no es una fuga de datos. Se perdió información de diagnóstico, y puede ser señal de un código que intentó registrar PII. La métrica no lleva el nombre ni el valor del campo, a propósito (NFR-U0-13).

## Diagnóstico
1. Identifica servicio y evento en Prometheus: `sum by (service, event) (increase(vectra_log_fields_dropped_total[15m]))`.
2. Compara con el último despliegue de ese servicio: `kubectl -n vectra-app rollout history deployment/<servicio>`.
3. Reproduce en local con `VECTRA_LOG_STRICT=1`: el modo estricto lanza `LogContractViolation` y nombra la clave en la traza. No lo actives en producción.

## Mitigación
- Si la clave es legítima y sin PII: PR que la agregue a `LogRecord` en U0, con su revisión.
- Si no lo es: PR que quite la clave de la llamada de log. El campo sigue descartado mientras tanto, así que no hace falta revertir de urgencia.
- Si la clave podía contener PII, avisa a cumplimiento con el servicio y el evento, sin copiar valores.

## Escalamiento
SEV3: no exige COE. Si el análisis muestra que un dato personal salió por otra vía distinta de este filtro, trátalo como incidente de seguridad y sube la severidad.

## Verificación
`promtool test rules platform/observability/rules/tests/*.yaml` en el repositorio; en el clúster, `increase(vectra_log_fields_dropped_total[15m])` vuelve a 0 y la alerta deja de estar `firing` en Alertmanager.
