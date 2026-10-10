# Patrones de NFR Design — U11 `product-metrics`

Decisiones del plan (`product-metrics-nfr-design-plan.md`, Q1–Q6 = A, con las notas del
usuario). Los IDs `P-U11-xx` se referencian en el Infrastructure Design y en el plan de tareas.

---

## 1. Lectura y estado

### P-U11-01 — Lectura por `seq` en una sola pasada (Q1; NFR-U11-01, 02, 10)
- Llamada: `GET /v1/entries?projection=metrics&entry_type=human_decision&recorded_from=…&seq_after=…&limit=1000`, en orden de `seq`. Cada página trae `next_seq_after`, y el servicio pide la siguiente solo después de procesar la anterior (nunca en paralelo).
- **Incremental** (cada 5 min): `seq_after = last_seq`, sin `recorded_from`.
- **Completa, en una sola pasada** (nota de Q1), **al arrancar y una vez al día** (02:30 UTC + desfase aleatorio; misma pasada en los dos casos, BR-U11-11; revisión del NFR Design de U11, 2026-10-10): `recorded_from` = día 1 del mes de hace 6 meses − 1 día (margen de la ventana de `occurred_at`), hasta la cabeza. Cada entrada:
  - se pliega en los contadores de su mes por `decided_at` si ese mes es uno de los 6 cerrados;
  - y, si su `decided_at` es de los últimos 35 días, también se guarda en el estado de 35 días.

  Así U3 no lee dos veces los últimos 36 días.
- Una decisión tardía de un mes cerrado que llega por la lectura incremental se refleja en los contadores del mes en la recomputación diaria siguiente, con hasta 24 h de retraso. Es aceptable: el mes cerrado se republica cada día (NFR-U11-11).
- Timeout de 5 s por página; breaker propio: abre con 3 fallos seguidos, semiabierto a los 60 s, cierra con 1 éxito. Los umbrales de U7 (20 llamadas en 30 s) no se alcanzan con lecturas en serie (revisión del Infrastructure Design de U11, 2026-10-10).
- **Verificación**: pruebas con un doble de U3: el orden por `seq` se respeta; una página fallida no avanza `last_seq`; la pasada completa asigna bien una entrada de 40 días al contador de su mes y no al estado de 35 días; nunca hay dos páginas en vuelo.
- **Satisface**: NFR-U11-01, 02, 09, 10; RESILIENCY-10.

### P-U11-02 — Recomputación con las lecturas en serie (Q2; NFR-U11-01, 09; corregida en la revisión del NFR Design de U11, 2026-10-10)
La versión anterior dejaba correr los incrementales mientras la pasada completa leía. Eso
contradecía NFR-U11-01 («nunca en paralelo») y saturaba el pool `projections` de U3, que tiene una
sola conexión por réplica. Ahora:
- **Un candado en el `reader`** (`asyncio.Lock`): toda lectura a U3, incremental o completa, lo toma. Mientras la pasada completa lo tiene, un ciclo incremental que llega **se omite** (no se encola) y se registra en `vectra_product_cycles_skipped_total`.
- La pasada arma el estado nuevo (35 días, contadores de los 6 meses y `last_seq` de la pasada) en una estructura aparte. El estado vigente sigue publicado mientras tanto.
- Al terminar con éxito:
  1. el estado nuevo reemplaza al vigente en una sola asignación, que cambia juntos el estado de 35 días, los contadores y `last_seq`;
  2. con el candado todavía tomado, el `reader` hace **enseguida una lectura incremental** desde el `last_seq` de la pasada, en lugar de reaplicar entradas guardadas; luego libera el candado;
  3. el estado anterior se libera.
- **Plazo de la pasada**: 75 min (por encima de los 60 min de NFR-U11-02 con 10 veces el volumen). Si se agota, la pasada falla, el estado vigente queda intacto y se reintenta cada 15 min hasta 6 veces (NFR-U11-09).
- **Durante la pasada**, `vectra_product_full_pass_in_progress = 1`. `ProductMetricsStale` no dispara mientras la pasada avanza (P-U11-06), porque una pasada larga y sana no es una falla.
- **Verificación**:
  - PBT-U11-02 con recomputaciones completas intercaladas con ciclos incrementales: el resultado es igual al de una recomputación completa sobre la unión, y nunca hay dos lecturas a U3 a la vez (un doble que cuenta las conexiones simultáneas falla si ve 2);
  - un ciclo incremental durante la pasada → omitido y contado;
  - una pasada que vence el plazo → estado intacto y reintento;
  - un scrape durante la pasada → solo el estado vigente.
- **Satisface**: NFR-U11-01, 09; RESILIENCY-10.

### P-U11-03 — Publicación con una instantánea (Q3; NFR-U11-07)
- `compute` produce un `BusinessMetrics` inmutable, que incluye las series de producto y `last_success`. Un `Collector` personalizado de `prometheus-client` lo lee en cada scrape.
- Al final de cada ciclo se reemplaza una sola referencia, así que un scrape nunca mezcla dos ciclos.
- Sin una primera instantánea (arranque con U3 caído), el `Collector` no emite series de producto ni `last_success`.
- Las **series de operación del ciclo** (NFR-U11-40) no dependen de la instantánea y se publican desde el arranque. Así `ProductMetricsStale`, por la rama de `up`, puede evaluarse con U3 caído (nota de Q3).
- **Verificación**: `/metrics` recién arrancado con U3 caído → series de operación sí, de producto no; un scrape concurrente con el reemplazo → solo valores de un ciclo.
- **Satisface**: NFR-U11-07, 40.

### P-U11-04 — Memoria compacta (Q5; NFR-U11-12, 13)
- Las decisiones de 35 días se guardan con solo los campos de domain-entities §1:
  - clases con `__slots__` o tuplas;
  - los valores de catálogo como **códigos enteros**, no cadenas;
  - `model_version_id` y `channel` internados.
- Los 6 meses son contadores por (mes, corte, `part`): unos pocos miles de enteros.
- **Estimación, no medida** (nota de Q5): unos 200 B por decisión y unas 70 000 decisiones en 35 días, ~15 MB. En Python una tupla con cadenas puede pesar varias veces eso, por eso los códigos enteros.
- El pico está en la recomputación (dos estados a la vez, P-U11-02).
- **La prueba decide**: con 10 veces el volumen esperado, si el pico supera el 70 % de 512 MiB, el Infrastructure Design ajusta el límite (NFR-U11-13) y se recalcula el aporte a la cuota (NFR-U11-14; plan de U1, Paso 6).
- **Verificación**: prueba de memoria con `tracemalloc` y en kind con el volumen × 10.
- **Satisface**: NFR-U11-12, 13.

## 2. Reglas y alertas

### P-U11-05 — Deduplicación en recording rules (Q4; NFR-U11-06)
- Por cada serie de producto, y también por cada razón ya publicada (`…_ratio`), una recording rule `vectra:<serie>:dedup = max without (instance, pod) (<serie>)` (nota de Q4).
- El dashboard y las alertas de producto (`RuidoExplicacion`, `ProductMetricsDegraded`) usan **solo** series `:dedup`. Las razones que combinan cortes se calculan como `sum(vectra:…_decisions:dedup{part="numerator"}) / sum(vectra:…_decisions:dedup{part="denominator"})`.
- Las dos alertas por réplica (`ProductMetricsStale`, `ProductMetricsFullRecomputeMissing`) leen las series crudas.
- Una prueba sobre `product.json` y las reglas rechaza cualquier referencia a una serie `vectra_product_*` cruda, salvo en esas dos alertas.
- **Verificación**: la prueba de referencias; `promtool test rules` con dos réplicas idénticas → los `:dedup` iguales a una réplica.
- **Satisface**: NFR-U11-06, 33.

### P-U11-06 — Alertas

| Alerta | Expresión | `for` | Severidad |
|---|---|---|---|
| `RuidoExplicacion` | `vectra:product_noise_days_below_floor:dedup >= <S>` (de `values-product-metrics-policy.yaml`) | 0 | SEV3 |
| `ProductMetricsDegraded` | `vectra:product_metrics_degraded:dedup == 1` | 1 h | SEV3 |
| `ProductMetricsStale` | `((time() - vectra_product_metrics_last_success_timestamp > 1800) or (up{job="product-metrics"} == 1 unless on (pod) vectra_product_metrics_last_success_timestamp)) unless on (pod) (vectra_product_full_pass_in_progress == 1)` (no dispara mientras una pasada completa avanza; la pasada tiene plazo de 75 min; revisión del NFR Design de U11, 2026-10-10) | 30 min | SEV3 |
| `ProductMetricsFullRecomputeMissing` | Igual, con `vectra_product_last_full_recompute_timestamp` y 93 600 s | 26 h en la rama de ausencia; 0 en la de edad | SEV3 |
| `GrafanaFolderPermissionsDrift` | Del Job de U1 (BR-U11-13) | 0 | SEV3 |

- La `PrometheusRule` es una plantilla del chart que toma S del archivo de parámetros, como U9.
- Cada regla lleva `severity` y `runbook_url`. Runbooks: `product-noise` (señal de producto, no falla técnica), `product-metrics-degraded`, `product-metrics-stale` y `product-metrics-full-recompute-missing`.
- **Verificación**: `promtool test rules` para cada alerta a los dos lados del umbral, incluido el caso de una réplica sin la serie y la otra con ella (NFR-U11-08); test de runbooks de U1.
- **Satisface**: NFR-U11-06, 08, 42; RESILIENCY-05, 07, 15.

## 3. Escenarios de falla (Q6; RESILIENCY-14 = C)

| # | Escenario | Resultado esperado |
|---|---|---|
| E1 | Registro caído durante 1 h | Últimos valores publicados; `ProductMetricsStale` a los 30 min por réplica; al volver, la incremental sigue desde `last_seq` |
| E2 | Registro caído al arrancar | Sin series de producto; series de operación sí; `ProductMetricsStale` a los 30 min por la rama de `up` |
| E3 | Una réplica pierde el token de Keycloak | Solo esa réplica deja de actualizar; `ProductMetricsStale` solo para ella; el dashboard sigue con la otra (`:dedup` por `max`) |
| E4 | La recomputación completa falla 6 veces | Estado incremental intacto; `ProductMetricsFullRecomputeMissing` a las 26 h |
| E5 | Un pod muere a mitad de la recomputación | La otra réplica sigue publicando; el pod nuevo hace la pasada completa al arrancar, con los 6 meses |
| E8 | Ciclo incremental durante la pasada completa | Se omite y se cuenta (`vectra_product_cycles_skipped_total`); al terminar la pasada, una lectura incremental desde su `last_seq`; nunca dos lecturas a U3 a la vez (revisión del NFR Design de U11, 2026-10-10) |
| E6 | Registro lento (p95 de página > 5 s) | El timeout falla el ciclo; el breaker abre tras 3 fallos seguidos; se conservan los valores; `ProductMetricsStale` a los 30 min sin lectura exitosa; al cerrarse el breaker, la incremental sigue desde `last_seq` (nota de Q6) |
| E7 | Más del 1 % de entradas excluidas (BR-U11-10) | Se publica igual con `degraded = 1`; `ProductMetricsDegraded` (deduplicada) tras 1 h (nota de Q6) |

Se documentan aquí; los que necesitan clúster los ejecuta el operador en kind tras un PR
aprobado, y la ejecución a escala queda para Operations (U0 P-U0-08). E1, E2, E6 y E7 tienen
también una prueba con dobles en CI.

## 4. Cumplimiento de extensiones (NFR Design U11)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | P-U11-05, 06 |
| RESILIENCY-08 / 09 | Cumple | P-U11-04 |
| RESILIENCY-10 | Cumple | P-U11-01, 02 |
| RESILIENCY-14 | Cumple (C) | §3 |
| SECURITY-03 | Cumple | P-U11-03 (sin identificadores en las series), NFR-U11-22 |
| AUTONOMIA-02 | Cumple | Cada patrón tiene su «Verificación» |
| PBT-06 | Cumple | PBT-U11-02 extendida (P-U11-02) |

## 5. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U3 plan (Paso 8) | `GET /v1/entries` con `projection=metrics` admite `entry_type`, `recorded_from`, `seq_after` y `limit` (≤ 1 000) en orden de `seq`, y devuelve `next_seq_after` | Q1 |
| U11 FD BR-U11-11 | La recomputación diaria lee los 36 días y los 6 meses en una sola pasada desde el sexto mes; las decisiones tardías de un mes cerrado entran en la recomputación siguiente | Q1 |
| U11 FD business-logic-model (PBT-U11-02) | Cubre recomputaciones completas intercaladas con incrementales y fallos a mitad, y que nunca hay dos lecturas a U3 a la vez | Q2; revisión del NFR Design de U11, 2026-10-10 |
| U11 FD BR-U11-11 | El arranque hace la misma pasada completa (6 meses), no solo 36 días | revisión del NFR Design de U11, 2026-10-10 |
| U11 NFR-U11-08 y domain-entities §5 | `ProductMetricsStale` excluye la pasada en curso; series `vectra_product_full_pass_in_progress` y `vectra_product_cycles_skipped_total` | revisión del NFR Design de U11, 2026-10-10 |
