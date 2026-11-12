# ProductMetricsStale

Alerta `ProductMetricsStale` (SEV3) de `product-metrics/observability/rules/product-metrics.rules.yaml`, por réplica y en dos ramas (NFR-U11-08, 42): la de edad (`time() - vectra_product_metrics_last_success_timestamp > 1800`, sin espera) y la de ausencia (`up{job="product-metrics"} == 1` y ninguna lectura exitosa publicada, durante 30 minutos). Las dos callan mientras la pasada completa avanza en esa réplica.

## Síntoma

Una réplica de `product-metrics` no lee de U3 con éxito desde hace más de 30 minutos (rama de edad), o está arriba y nunca publicó una lectura exitosa (rama de ausencia). El dashboard sigue mostrando los últimos valores o, si ninguna réplica leyó, queda vacío. La etiqueta `branch` de la alerta dice cuál rama disparó (`edad` o `ausencia`).

## Impacto

Los valores de producto del dashboard dejan de actualizarse (la otra réplica mantiene el dashboard con `max` entre réplicas mientras esté sana). `/readyz` da 503 hasta 30 minutos si U3 no respondía al arrancar. No hay impacto en las decisiones del banco.

## Diagnóstico

1. ¿Qué réplica es? La etiqueta `pod` de la alerta. ¿Hay otra sana? `kubectl --context kind-vectra -n vectra-app get pods -l app.kubernetes.io/name=product-metrics`.
2. ¿U3 responde? El breaker hacia el registro: panel «Breaker hacia U3» de `operacion.json` (`vectra_circuit_state{dependency="decision-registry"}`). Con el breaker abierto, la causa es U3: sigue `decision-registry/runbooks/` y `platform/runbooks/registry-db-writes-blocked.md`.
3. Logs de la réplica, buscando fallos de lectura o de token:

```bash
kubectl --context kind-vectra -n vectra-app logs <pod> | tail -50
```

4. Si una réplica perdió el token de Keycloak: ¿existe la llave? `kubectl --context kind-vectra -n vectra-app get externalsecret product-metrics-client` debe estar `SecretSynced` (el cliente `product-metrics` de U2 solo tiene el scope `registry:read:metrics`).
5. ¿Es una pasada completa en curso? `vectra_product_full_pass_in_progress` en 1 silencia la alerta hasta el plazo de 75 minutos; si dura más, la pasada venció y la alerta dispara.
6. Orden de arranque (wave 5): si `product-metrics` arrancó antes de que `decision-registry-service` respondiera, la primera pasada falla y el siguiente intento es a los 15 minutos; la rama de ausencia dispara a los 30.

## Mitigación

1. Restablece la dependencia que falla (U3 o la llave del cliente). El proceso reintenta solo: la pasada completa fallida cada 15 minutos y la lectura incremental cada 5.
2. Si solo una réplica está atascada y U3 responde, reinicia esa réplica; el PDB deja la otra en pie: `kubectl --context kind-vectra -n vectra-app delete pod <pod>`. La réplica nueva hace la pasada completa al arrancar.
3. No toques `values-product-metrics-policy.yaml` para esto: los parámetros no afectan la lectura.

## Escalamiento

Si pasa de 1 hora y U3 responde, escala al responsable de U11. Si U3 no responde, al de U3. Registra el caso en el análisis posterior (`platform/runbooks/coe-template.md`).

## Verificación

```bash
# La marca de la última lectura exitosa avanza (desde una réplica, puerto 8081): la edad debe ser menor que 1800 s.
kubectl --context kind-vectra -n vectra-app exec <pod> -- python -c "import time,urllib.request;l=[x for x in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if x.startswith('vectra_product_metrics_last_success_timestamp')];print(l, time.time())"
# La readiness vuelve a 200:
kubectl --context kind-vectra -n vectra-app exec <pod> -- python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8081/readyz').status)"
```

Esperado: la marca cercana a la hora actual (diferencia menor que 1 800 s) y `200`.
