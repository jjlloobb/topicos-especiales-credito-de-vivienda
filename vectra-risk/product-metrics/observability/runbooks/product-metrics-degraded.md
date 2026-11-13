# ProductMetricsDegraded

Alerta `ProductMetricsDegraded` (SEV3) de `product-metrics/observability/rules/product-metrics.rules.yaml`: `vectra:product_metrics_degraded:dedup == 1` durante 1 hora (BR-U11-10, BR-U11-14).

## Síntoma

`vectra_product_metrics_degraded` vale 1: más del 1 % de las entradas de los últimos 30 días se excluyeron del cálculo. El panel «Aviso de datos degradados» de `product.json` dice «datos degradados».

## Impacto

Las métricas de producto se siguen publicando, pero pueden no ser completas: una entrada excluida no cuenta en la North Star, en la sostenida ni en la tasa de consulta. Ninguna decisión del banco cambia; solo se debilita la lectura de producto.

## Diagnóstico

1. Cuántas entradas se excluyen y desde cuándo: panel «Entradas excluidas» (`vectra_product_invalid_entries`, 30 días).
2. Por qué se excluyen: el proceso registra cada entrada excluida con su `seq` (sin datos personales; el registro JSON trae el campo `seq`) en el log de la réplica:

```bash
kubectl --context kind-vectra -n vectra-app logs deploy/product-metrics | grep '"seq"' | tail -20
```

3. Las causas típicas son un `decided_at` por delante de `recorded_at` en más de 5 minutos (relojes desfasados de quien escribe en el registro, U3) o una entrada con un campo que el cálculo no entiende (un cambio de contrato de U0 o de U3 sin la versión nueva del servicio).
4. ¿Hubo un despliegue reciente de `decision-registry-service`, `scoring-service` o `case-service`? Compáralo con la hora en que empezó la exclusión.

## Mitigación

1. Corrige la causa en el servicio que escribe en el registro (U3 o su cliente); `product-metrics` no inventa ni corrige entradas.
2. Las entradas ya excluidas dejan de contar en el siguiente ciclo en que su `decided_at` salga de la ventana de 30 días, o con la recomputación diaria de las 02:30 UTC si la causa quedó corregida.
3. No cambies la regla de exclusión para que la alerta calle: es parte del código de U11 (BR-U11-10) y cambiarla exige un PR.

## Escalamiento

Si pasa de un día o la razón de excluidas sigue creciendo, escala al responsable de U3 (el registro) y al de la unidad que escribe las entradas. Registra el caso en el análisis posterior (`platform/runbooks/coe-template.md`).

## Verificación

```bash
# El aviso vuelve a 0 (desde una réplica, puerto 8081):
kubectl --context kind-vectra -n vectra-app exec deploy/product-metrics -- python -c "import urllib.request;print([l for l in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if l.startswith('vectra_product_metrics_degraded')])"
# Y sin entradas excluidas nuevas en el log:
kubectl --context kind-vectra -n vectra-app logs deploy/product-metrics --since=30m | grep -c '"seq"'
```

Esperado: `vectra_product_metrics_degraded` en `0.0` y el conteo del log en `0`.
