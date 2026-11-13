# ProductMetricsFullRecomputeMissing

Alerta `ProductMetricsFullRecomputeMissing` (SEV3) de `product-metrics/observability/rules/product-metrics.rules.yaml`, por réplica y en dos ramas (NFR-U11-42): la de edad (`time() - vectra_product_last_full_recompute_timestamp > 93600`, es decir 26 horas, sin espera) y la de ausencia (la réplica está arriba y nunca publicó esa marca, durante 26 horas). Las dos callan mientras la pasada completa avanza en esa réplica.

## Síntoma

Una réplica no completa la recomputación diaria (02:30 UTC más un desfase de 0 a 10 minutos) hace más de 26 horas. La etiqueta `branch` dice si ya hubo una pasada completa exitosa (`edad`) o si nunca la hubo (`ausencia`, por ejemplo con U3 caído desde que la réplica arrancó).

## Impacto

El estado incremental de la réplica sigue publicando, pero no se reconstruyen los 6 meses cerrados ni se corrigen las decisiones tardías de un mes cerrado (BR-U11-11): los valores `month` pueden quedar desactualizados. Los ciclos de 5 minutos y los demás paneles no se ven afectados.

## Diagnóstico

1. ¿Qué réplica? La etiqueta `pod`. ¿La otra tiene la marca al día? Compara `vectra_product_last_full_recompute_timestamp` en las dos réplicas.
2. ¿La pasada falla o vence? Los reintentos son cada 15 minutos, hasta 6 veces; la pasada tiene un plazo de 75 minutos y se comprueba entre páginas. Busca en el log los registros de estado `fallida` (con `error_code` y el número de `attempt`):

```bash
kubectl --context kind-vectra -n vectra-app logs <pod> | grep fallida | tail -30
```

3. ¿U3 responde y pagina a tiempo? Panel «Ciclo de product-metrics» de `operacion.json` (p95 de la duración del ciclo `full`) y «Breaker hacia U3». Una pasada de más de 75 minutos indica que U3 es lento: sigue `decision-registry/runbooks/`.
4. ¿Hubo reinicios que cortaron la pasada? `kubectl --context kind-vectra -n vectra-app get pods -l app.kubernetes.io/name=product-metrics` (la columna de reinicios). Un apagado a mitad de pasada la descarta, y la réplica nueva la repite al arrancar.

## Mitigación

1. Restablece U3 si es la causa; el proceso reintenta solo.
2. Si U3 responde y la pasada sigue venciendo, reinicia la réplica para que haga una pasada completa al arrancar (el PDB deja la otra en pie): `kubectl --context kind-vectra -n vectra-app delete pod <pod>`.
3. No cambies el plazo ni los reintentos: son constantes del código (`vectra_product.config`) y cambiarlas exige un PR.

## Escalamiento

Si la alerta pasa de un día o hay una pasada que vence cada noche, escala al responsable de U11 y al de U3 (el tamaño de la proyección `metrics`). Registra el caso en el análisis posterior (`platform/runbooks/coe-template.md`).

## Verificación

```bash
# La marca de la última recomputacion completa es reciente (desde una réplica, puerto 8081):
kubectl --context kind-vectra -n vectra-app exec <pod> -- python -c "import time,urllib.request;l=[x for x in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if x.startswith('vectra_product_last_full_recompute_timestamp')];print(l, time.time())"
# Y ninguna pasada en curso trabada:
kubectl --context kind-vectra -n vectra-app exec <pod> -- python -c "import urllib.request;print([x for x in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if x.startswith('vectra_product_full_pass_in_progress')])"
```

Esperado: la marca con menos de 26 horas (93 600 s) de diferencia con la hora actual y `vectra_product_full_pass_in_progress` en `0.0`.
