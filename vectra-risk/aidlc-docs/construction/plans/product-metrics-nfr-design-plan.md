# Plan de NFR Design — U11 `product-metrics`

**Alcance:** convertir NFR-U11-01..42 en patrones y componentes lógicos.

**Ya decidido** (no se pregunta):
- el Functional Design (BR-U11-01..14) y el NFR Requirements (NFR-U11-01..42);
- 2 réplicas independientes, deduplicación con `max without (instance, pod)`, alertas por réplica comparadas con `up`;
- lectura incremental cada 5 min, completa diaria con desfase aleatorio, 6 meses plegados en contadores;
- timeout de 5 s por página, breaker de U7, sin reintentos dentro del ciclo;
- proceso `asyncio` con `vectra_common.ops_server`;
- severidades de P-U1-10.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q2, Q6 |
| Scalability Patterns | Q5 |
| Performance Patterns | Q1, Q5 |
| Security Patterns | Sin preguntas: NFR-U11-20..22 fijan el scope único, el `Server` de Linkerd y la allowlist de logs |
| Logical Components | Q2, Q3, Q4 |
| Observabilidad | Q4 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Paginación y filtros de lectura (Performance; F28)

A) **Keyset por `seq` con filtros del servidor**:
   - `GET /v1/entries?projection=metrics&entry_type=human_decision&recorded_from=…&seq_after=…&limit=1000`, en orden de `seq`; la página trae `next_seq_after` y el servicio pide la siguiente solo cuando procesó la anterior;
   - incremental: `seq_after = last_seq`, sin `recorded_from`;
   - completa de 36 días: `recorded_from = hoy − 36 d`;
   - 6 meses: `recorded_from = día 1 del mes de hace 6 meses − 1 d` (margen de la ventana de `occurred_at`), hasta la cabeza; cada entrada se asigna al mes por `decided_at`, y una de un mes fuera de los 6 se descarta;
   - si U3 no ofrece hoy `seq_after` y `entry_type` en `metrics`, se registran como cambio a U3 (plan, Paso 8).

   (Recomendado)

B) Paginación por `offset`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la lectura completa de 36 días y la de los 6 meses se hacen en **una sola pasada** desde `recorded_from` del sexto mes. Cada página se pliega en los contadores por mes (por `decided_at`) y, si la entrada tiene `decided_at` dentro de los últimos 35 días, también se guarda en el estado de 35 días. Así U3 no lee dos veces los últimos 36 días (NFR-U11-02). Una decisión tardía de un mes cerrado que llega por la lectura incremental se refleja en los contadores del mes en la recomputación diaria siguiente, es decir, con hasta 24 h de retraso (NFR-U11-11).
## Question 2 — Recomputación diaria sin estados mezclados (Resilience / Logical Components)

A) **Construir aparte y cambiar de una vez**:
   - la recomputación completa arma un estado nuevo en una estructura aparte, mientras los ciclos incrementales siguen sobre el estado vigente;
   - al terminar con éxito, el estado nuevo reemplaza al vigente en una sola asignación, y antes se le aplican las entradas incrementales con `seq` mayor que el último que leyó la completa;
   - si la completa falla, el estado vigente sigue intacto y se reintenta según NFR-U11-09;
   - así nunca se publica una mezcla de estado viejo y nuevo.

   (Recomendado)

B) Pausar los incrementales durante la completa

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: al reemplazar el estado, la aplicación de las entradas incrementales posteriores a la completa se deduplica por `seq` (PBT-U11-03: leer dos veces el mismo `seq` no cambia nada). El reemplazo cambia juntos el estado de 35 días, los contadores de los 6 meses y `last_seq`. PBT-U11-02 debe cubrir una recomputación completa intercalada con lecturas incrementales.
## Question 3 — Publicación coherente (Logical Components)

A) **Un `Collector` sobre una instantánea inmutable**: `compute` produce un `BusinessMetrics` inmutable; un `Collector` personalizado de `prometheus-client` lo lee en cada scrape. Una sola referencia se reemplaza al final de cada ciclo, así que un scrape nunca ve la mitad de un ciclo y la otra mitad del siguiente. Mientras no haya una primera instantánea (arranque sin datos), el `Collector` no emite series de producto (NFR-U11-07). (Recomendado)

B) Gauges que se actualizan uno por uno al calcular

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la instantánea incluye las series de producto y `last_success`. Las series de operación del ciclo (NFR-U11-40) no dependen de ella y se publican desde el arranque, para que `ProductMetricsStale` por la rama de `up` pueda evaluarse con U3 caído.
## Question 4 — Deduplicación en un solo lugar (Logical Components / Observabilidad; NFR-U11-06)

A) **Recording rules deduplicadas**:
   - por cada serie de producto, una recording rule `vectra:<serie>:dedup = max without (instance, pod) (<serie>)`;
   - el dashboard y las alertas de producto (`RuidoExplicacion`, `ProductMetricsDegraded`) usan **solo** las series `:dedup`; una prueba sobre `product.json` y las reglas rechaza cualquier referencia a una serie `vectra_product_*` cruda (salvo en las alertas por réplica);
   - las razones del dashboard se calculan como `sum(vectra:…_decisions:dedup{part="numerator"}) / sum(vectra:…_decisions:dedup{part="denominator"})`.

   (Recomendado)

B) `max without (instance, pod)` escrito en cada panel

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: las razones ya publicadas (`…_ratio`) también tienen su recording rule `:dedup`. Las alertas por réplica (`ProductMetricsStale`, `ProductMetricsFullRecomputeMissing`) siguen leyendo las series crudas, y la prueba lo permite solo para esas dos.
## Question 5 — Estructuras en memoria (Performance / Scalability; NFR-U11-12, 13)

A) **Compactas y acotadas**:
   - las decisiones de 35 días se guardan como tuplas con solo los campos de domain-entities §1 (unos 200 B cada una): unas 70 000 decisiones caben en ~15 MB;
   - los 6 meses son contadores por (mes, corte, `part`): unos pocos miles de enteros;
   - el pico está en la recomputación completa (dos estados a la vez, Q2): ~2 × el estado de 35 días, por debajo del límite de 512 MiB incluso con 10 veces el volumen;
   - una prueba con 10 veces el volumen mide el pico y falla por encima del 70 % del límite.

   (Recomendado)

B) Guardar las entradas completas de la proyección

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: los ~200 B por decisión y el «unas 70 000 decisiones» son estimaciones, no medidas: en Python una tupla con cadenas puede pesar varias veces eso. Para acercarse a la cifra se guardan `__slots__` o tuplas con códigos enteros del catálogo (no cadenas) y los identificadores internados. Tras reemplazar el estado, el anterior se libera. La prueba con 10 veces el volumen decide: si el pico supera el 70 % de 512 MiB, se ajusta el límite en el Infrastructure Design (NFR-U11-13) y se recalcula el aporte a la cuota de `vectra-app` (U1, Paso 6; NFR-U11-14).
## Question 6 — Escenarios de falla (Resilience; RESILIENCY-14 = C)

A)
   | # | Escenario | Resultado esperado |
   |---|---|---|
   | E1 | Registro caído durante 1 h | Últimos valores publicados; `ProductMetricsStale` a los 30 min por réplica; al volver, la incremental sigue desde `last_seq` |
   | E2 | Registro caído al arrancar | Sin series de producto; `ProductMetricsStale` a los 30 min por la rama de `up` |
   | E3 | Una réplica pierde el token de Keycloak | Solo esa réplica deja de actualizar; `ProductMetricsStale` solo para ella; el dashboard sigue con la otra (deduplicación por `max`) |
   | E4 | La recomputación completa falla 6 veces | Estado incremental intacto; `ProductMetricsFullRecomputeMissing` a las 26 h |
   | E5 | Un pod muere a mitad de la recomputación | La otra réplica sigue publicando; el pod nuevo hace la lectura completa al arrancar |

   Se documentan aquí; los de kind los ejecuta el operador y la ejecución a escala queda para Operations (U0 P-U0-08). (Recomendado)

B) Solo E1 y E2

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: se agregan dos escenarios a la tabla:
   - **E6** — Registro lento (p95 de página > 5 s): el timeout de 5 s falla el ciclo, el breaker abre tras los umbrales de U7, se conservan los valores y `ProductMetricsStale` dispara a los 30 min si no hay una lectura exitosa; al cerrarse el breaker, la incremental sigue desde `last_seq`.
   - **E7** — Más del 1 % de entradas excluidas (BR-U11-10): se publica igual con `vectra_product_metrics_degraded = 1`, y `ProductMetricsDegraded` dispara tras 1 h (deduplicada).
---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-design-patterns.md` (P-U11-xx): lectura, ciclo y recomputación, publicación, deduplicación, memoria, alertas, escenarios
- [x] `logical-components.md`
- [x] Cambios a otras unidades (por ejemplo, filtros de la proyección en U3) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
