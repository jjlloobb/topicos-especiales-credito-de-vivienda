# ProductNoise: alerta `RuidoExplicacion`

Alerta `RuidoExplicacion` (SEV3) de `product-metrics/observability/rules/product-metrics.rules.yaml`: `vectra:product_noise_days_below_floor:dedup >= S`, donde S es `noise_sustain_days` de `values-product-metrics-policy.yaml` (BR-U11-14). **Es una señal de producto, no una falla técnica**: el sistema funciona; lo que cambia es cómo se usa la explicación.

## Síntoma

La tasa de consulta de la explicación (ventana móvil de 7 días) estuvo por debajo del piso F (`noise_floor`) durante S días UTC completos seguidos hasta ayer, con al menos N decisiones en la ventana de cada día (`noise_min_decisions`); un día con menos de N decisiones no suma ni reinicia la cuenta. El panel «Días bajo el piso» de `product.json` (carpeta `Vectra / Producto`) muestra un valor mayor o igual a S.

## Impacto

El comité está decidiendo sin abrir la explicación: la North Star (decisiones donde la explicación cambia o sustenta la decisión) pierde sentido porque la explicación se vuelve ruido. No hay pérdida de datos ni de disponibilidad y ningún usuario ve un error.

## Diagnóstico

1. Confirma que la métrica es real y no un dato degradado: el panel «Aviso de datos degradados» debe decir «datos completos». Si dice «datos degradados», sigue primero `product-metrics/observability/runbooks/product-metrics-degraded.md`.
2. Mira la tasa de consulta por canal y por día en el panel «Tasa de consulta de la explicación y piso F» (periodo `7d`, días UTC completos que terminan ayer; el día en curso no cuenta).
3. Verifica los parámetros vigentes (los lee el proceso del `ConfigMap`, no de variables de entorno):

```bash
kubectl --context kind-vectra -n vectra-app get configmap product-metrics-policy -o jsonpath='{.data.values-product-metrics-policy\.yaml}'
```

4. Pregunta al equipo de producto y a riesgo si hubo un cambio de proceso en el comité (un canal nuevo, un formato de reunión distinto, una pausa del piloto) que explique que dejen de abrir la explicación.

## Mitigación

1. Revisa con el piloto cómo se usa la explicación: es una conversación de producto, no un cambio de código. No hay nada que reiniciar.
2. No bajes el piso F ni subas S para que la alerta calle: esos parámetros están bajo `CODEOWNERS` y los cambia producto con riesgo (`.github/CODEOWNERS`, regla `**/values-product-metrics-policy.yaml`).
3. Si el piso F ya no es el correcto para el uso real, propone el cambio por PR con la aprobación de producto y de riesgo; el `ConfigMap` lleva `checksum/config`, así que las réplicas se reinician solas con el valor nuevo.

## Escalamiento

Escala al responsable de producto de Vectra Risk y al CRO si la alerta dura más de una semana. Si la causa es técnica (por ejemplo, la consola no muestra la explicación), pasa a U10 y registra el caso en el análisis posterior (`platform/runbooks/coe-template.md`).

## Verificación

```bash
# El valor vuelve por debajo de S (desde una réplica, puerto 8081); el pod se llama product-metrics-...
kubectl --context kind-vectra -n vectra-app exec deploy/product-metrics -- python -c "import urllib.request;print([l for l in urllib.request.urlopen('http://127.0.0.1:8081/metrics').read().decode().splitlines() if l.startswith('vectra_product_noise_days_below_floor')])"
```

Esperado: el valor menor que S y la alerta `RuidoExplicacion` en `resolved` en Alertmanager. Como el cálculo usa días UTC completos, el valor puede tardar hasta un día en bajar tras un cambio de uso.
