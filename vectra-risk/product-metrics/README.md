# product-metrics (U11)

Calcula en memoria las métricas de producto de Vectra Risk (North Star, tasa de consulta de la explicación y su ruido, recomendaciones sostenidas, tiempo de originación, respuesta completa) leyendo la proyección `metrics` de `decision-registry-service` (U3) y las publica en `/metrics`. No tiene API de negocio ni base de datos: solo el puerto 8081 (`/metrics`, `/healthz`, `/readyz`). Las ve el presentador y el equipo de producto en Grafana, en la carpeta `Vectra / Producto` (`observability/dashboards/product.json`).

## Qué mide cada métrica y qué no

Todos los periodos son días UTC **completos** y no incluyen el día en curso (para que un valor publicado no cambie a lo largo del día). El dashboard muestra la hora de Colombia y dice en cada panel qué periodo usa.

| Métrica | Qué mide | Qué no mide |
|---|---|---|
| **North Star** (`vectra_product_north_star_*`) | Proporción de decisiones donde la explicación cambia o sustenta materialmente la decisión del comité (sustentada, cambiada o revisión resuelta), con su desglose. | No dice si la decisión fue correcta. |
| **Tasa de consulta** (`vectra_product_explanation_view_*`) | Proporción de decisiones en las que se abrió la explicación, en una ventana móvil de **7 días** completos que terminan ayer. | No dice cuánto se leyó la explicación. |
| **Días bajo el piso** (`vectra_product_noise_days_below_floor`) | Cuántos días UTC completos **seguidos**, contando hacia atrás desde ayer, la tasa de consulta de la ventana móvil de 7 días que termina ese día estuvo por debajo del piso F con al menos N decisiones en esa ventana. Un día cuya ventana tiene menos de N decisiones no suma ni reinicia la cuenta; un día con tasa igual o mayor que F la corta. | Es una señal de **producto**, no una falla técnica: avisa (`RuidoExplicacion`) cuando llega a S. |
| **Recomendaciones sostenidas** (`vectra_product_recommendation_sustained_ratio`) | Decisiones que siguieron la recomendación sobre las decisiones atribuibles. | Es una **aproximación**: mide si la decisión siguió la recomendación; la revisión del comité no está en el sistema. La medición real queda pendiente para Operations. |
| **Originación** (`vectra_product_origination_*`) | Percentiles 0,5, 0,8 y 0,95 del tiempo de originación de ayer en los casos estándar, y la razón dentro del target. | No cubre los casos no estándar. |
| **Respuesta completa** (`vectra:product_complete_response_ratio:1h` y `:1d`) | Recomendaciones que no fueron fail-closed sobre todas; con el desglose de fail-closed por desincronía. | Calculada desde `vectra_recommendations_total` de U7, no desde el registro. |
| **No atribuibles, excluidas y degradado** | Decisiones sin recomendación atribuible; entradas del registro que el cálculo excluyó; y el aviso (`vectra_product_metrics_degraded`) cuando se excluye más del 1 % en 30 días. | Con datos degradados las demás métricas pueden no ser completas. |

La tasa de cada día es la de la **ventana móvil de 7 días** que termina ese día (decisiones atribuibles con la explicación vista sobre decisiones atribuibles, por `decided_at`), no la de ese día solo. Por eso 40 decisiones por día durante 3 días seguidos dan una cuenta de 2 y no de 0: la ventana del día 1 tiene 40 decisiones (menos que N = 50, no suma ni reinicia), la del día 2 tiene 80 y la del día 3 tiene 120 (las dos ≥ N y, si su tasa está bajo F, suman). Con S = 3 la alerta dispara cuando la cuenta llega a 3. La serie sale de los datos y no del tiempo que lleva corriendo el proceso: un reinicio no la cambia.

## Parámetros y targets [INTERNO]

Viven solo en [`chart/values-product-metrics-policy.yaml`](chart/values-product-metrics-policy.yaml), que el chart monta como `ConfigMap` (sin `subPath`) y que `params.py` valida al arrancar. Cambiarlos exige la aprobación de producto y riesgo (`CODEOWNERS`, regla `**/values-product-metrics-policy.yaml`) y reinicia las réplicas (`checksum/config`). **[INTERNO]**

| Clave | Valor | Rango |
|---|---|---|
| `noise_floor` (F) | 0,6 | 0 < F < 1 |
| `noise_sustain_days` (S) | 3 | entero de 1 a 14 |
| `noise_min_decisions` (N) | 50 | entero ≥ 30 |
| `target_complete_response` | 1,0 | 0 a 1 |
| `target_origination_hours` | 1 | mayor que 0 |
| `target_origination_ratio` | 0,8 | 0 a 1 |
| `target_sustained_ratio_month6` | 0,7 | 0 a 1 |
| `target_north_star` | nulo | nulo o 0 a 1 |

Sin target acordado para la North Star, su panel dice «sin target acordado». Los targets del dashboard son líneas de referencia tomadas de la serie `vectra:product_target:dedup`, no números escritos en el JSON. El ciclo, los plazos y los reintentos no son parámetros: son constantes de `src/vectra_product/config.py` y cambiarlas exige un PR.

## Ciclo de lectura

- Al arrancar hace una **pasada completa**: lee desde el día 1 del sexto mes cerrado menos 1 día, arma el estado aparte, lo reemplaza de una sola vez y publica.
- Cada día a las **02:30 UTC** más un desfase aleatorio de 0 a 10 minutos por réplica repite la pasada completa. Si falla, la reintenta cada 15 minutos, hasta 6 veces; sin ninguna pasada exitosa, el reintento no tiene tope. El plazo de una pasada es de 75 minutos.
- Cada 5 minutos hace una **lectura incremental** desde el último `seq`. Si la pasada completa tiene el candado, el ciclo se omite y se cuenta en `vectra_product_cycles_skipped_total`. Nunca hay dos lecturas a U3 a la vez.
- `SIGTERM` termina la página en vuelo, descarta la pasada a medias y sale con código 0.

## Deduplicación (dos réplicas, un dashboard)

Las dos réplicas publican los mismos valores. Por cada serie de producto, una recording rule `vectra:<serie>:dedup` la agrega con `max without (instance, pod)` (generadas por `tools/gen_rules.py` desde `collector.PRODUCT_SERIES`), de modo que el dashboard y las alertas de producto usan solo series `:dedup` y dos réplicas valen lo que una. Una razón que combina cortes se calcula como `sum(numerador) / sum(denominador)` sobre los conteos, nunca como promedio de razones. Solo las alertas por réplica leen las series crudas.

## Readiness

`/healthz` es solo el proceso. `/readyz` da 200 si hay una instantánea publicada **o** el breaker hacia U3 está abierto o semiabierto; si no, 503. Con U3 caído al arrancar, el breaker abre al tercer fallo (los reintentos son cada 15 minutos), es decir a los **30 minutos**, no «unos 15 s»: durante esos 30 minutos `/readyz` da 503 y el dashboard queda vacío. En la wave 5, si `product-metrics` arranca antes de que `decision-registry-service` responda, pasa lo mismo hasta el siguiente intento. El `Service` publica también las réplicas no listas (`publishNotReadyAddresses`) para que Prometheus las raspe.

## Alertas y runbooks

La `PrometheusRule` del chart tiene cuatro alertas, todas SEV3 y cada una con su runbook:

- `RuidoExplicacion`: [product-noise](observability/runbooks/product-noise.md), una señal de producto, no una falla técnica.
- `ProductMetricsDegraded`: [product-metrics-degraded](observability/runbooks/product-metrics-degraded.md).
- `ProductMetricsStale`: [product-metrics-stale](observability/runbooks/product-metrics-stale.md).
- `ProductMetricsFullRecomputeMissing`: [product-metrics-full-recompute-missing](observability/runbooks/product-metrics-full-recompute-missing.md).

El runbook `product-metrics-parameter-change` (cambio de parámetros) queda **diferido por la demo** (T2); mientras tanto, el cambio es un PR sobre `values-product-metrics-policy.yaml` con la aprobación de producto y riesgo.

## Cómo se prueba y se despliega

`make -C product-metrics check` corre las verificaciones estáticas, las pruebas con el perfil `ci`, la cobertura, las reglas con `promtool`, la imagen y el contenedor real, el chart con `kubeconform` y `conftest`, la admisión de U1, la cuota, los flujos, los runbooks, los enlaces y la trazabilidad. La imagen y su publicación: [docs/imagenes.md](docs/imagenes.md). La Application está en `vectra-risk-gitops/components.yaml` (wave 5, sin auto-sync) y el request de memoria en kind es de 128 MiB (los 256 MiB de INF-U11-01 rigen en staging y prod).
