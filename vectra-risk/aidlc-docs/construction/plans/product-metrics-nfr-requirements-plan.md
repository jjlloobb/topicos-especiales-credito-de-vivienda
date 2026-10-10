# Plan de NFR Requirements — U11 `product-metrics`

**Alcance:** requisitos no funcionales y stack del servicio `product-metrics`, sobre el
Functional Design aprobado (BR-U11-01..14, PBT-U11-01..07).

**Ya decidido** (no se pregunta):
- **Funcionamiento** (FD): lectura completa de 36 días al arrancar y una vez al día; lectura incremental por `seq` cada 5 min; cálculo puro en memoria; solo `human_decision` con la recomendación resuelta por U3; sin datos persistentes.
- **Alertas** (FD): `RuidoExplicacion`, `ProductMetricsStale` (30 min sin lectura) y `ProductMetricsDegraded`, todas SEV3.
- **Criticidad** (`unit-of-work.md`): Medium. El servicio no está en la ruta de ninguna decisión: si cae, solo se atrasan las métricas.
- **Volumen del registro** (NFR-U3-30): ~10 000 entradas al día en total; las `human_decision` son una fracción (del orden de cientos a pocos miles por día).
- **Prometheus guarda 30 días** (NFR-U1-31).
- **Stack común**: Python 3.12, `vectra_common` (`deps.call` con timeout y circuit breaker, logger con allowlist, métricas en 8081), `vectra_contracts`, Hypothesis.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Tiempos del ciclo (Performance)

A) **Presupuestos por lectura**:
   - lectura incremental (cada 5 min): p95 ≤ 5 s, con páginas de 1 000 entradas;
   - lectura completa de 36 días: ≤ 2 min con el volumen esperado, y ≤ 10 min con 10 veces ese volumen;
   - `compute` sobre 35 días: ≤ 5 s;
   - el pool `projections` de U3 (1 conexión por réplica, 2 s de espera) no debe saturarse: las páginas de U11 van una tras otra, nunca en paralelo, y la lectura completa diaria corre a las 02:30 UTC, fuera del horario operativo.

   (Recomendado)

B) Sin presupuestos explícitos; se mide en kind

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: el presupuesto de la lectura completa debe cubrir también los 6 meses de Q3: ≤ 15 min con el volumen esperado y ≤ 60 min con 10 veces ese volumen, con p95 de página ≤ 1 s (el pool `projections` espera 2 s). Las dos réplicas no deben coincidir en la recomputación diaria: el arranque de la lectura completa lleva un desfase aleatorio de hasta 10 min.

## Question 2 — Réplicas y series duplicadas (Availability / Scalability)
Si dos réplicas publican las mismas series, Prometheus guarda las dos y una suma en el dashboard
daría el doble. Una sola réplica no cumple NFR-U1-12 (≥ 2 réplicas o exención con ≥ 2).

A) **Dos réplicas independientes y deduplicación en las consultas**:
   - 2 réplicas fijas con `vectra.io/hpa-exempt` (carga constante y baja), PDB y spread por zona;
   - cada una lee y calcula por su cuenta (sin coordinación), así que sus valores coinciden salvo en el instante de la lectura;
   - toda consulta del dashboard y toda regla usan `max without (instance, pod) (…)` antes de cualquier `sum`; una prueba sobre `product.json` y las reglas rechaza un `sum` sin esa deduplicación;
   - el doble de lecturas sobre U3 es pequeño (2 lecturas incrementales cada 5 min).

   (Recomendado)

B) Una réplica con una exención nueva en NFR-U1-12 para servicios de criticidad Medium sin efecto en la ruta de decisión

C) CronJob cada 5 min que empuja al Pushgateway, sin servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la deduplicación también vale para las alertas. `RuidoExplicacion` y `ProductMetricsDegraded` usan `max without (instance, pod)` para no dispararse dos veces. `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing` quedan por réplica, porque una réplica atrasada es una falla real, y Alertmanager las agrupa por `alertname`.

## Question 3 — Historia más allá de 30 días (Availability; FR-MET-05 «al mes 6»)
Prometheus guarda 30 días, pero el target de la sostenida es «> 70 % al mes 6» y el PRD sigue
la North Star mes a mes.

A) **El servicio publica los meses cerrados**:
   - en la recomputación diaria, el servicio también lee las `human_decision` de los últimos 6 meses calendario cerrados y publica cada uno como serie con la etiqueta `month="AAAA-MM"` (`period="month"`), para la North Star, la sostenida y la tasa de consulta;
   - así el dashboard muestra 6 meses de historia sin depender de la retención de Prometheus;
   - volumen: del orden de cientos de miles de `human_decision` en 6 meses, leídas una vez al día en páginas, fuera del horario operativo; se mide en el NFR Design;
   - cambia el FD (BR-U11-08 y BR-U11-11), que hoy lee 36 días.

   (Recomendado)

B) Aceptar 30 días de historia y que el seguimiento de 6 meses se haga fuera del sistema

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: (1) un mes cerrado todavía puede cambiar durante los 7 días siguientes a su cierre (BR-U0-37 acepta momentos de negocio hasta 7 días antes de `occurred_at`), así que la recomputación diaria lo republica en lugar de congelarlo. (2) Para que los 6 meses no vivan en memoria (Q5), el servicio pliega cada página en contadores por mes y corte y no guarda las entradas de los meses cerrados; el estado de 35 días de BR-U11-11 sigue guardando las entradas. Se registra como cambio a BR-U11-08 y BR-U11-11.

## Question 4 — Resiliencia ante el registro (Reliability; RESILIENCY-10)

A) **Una sola dependencia, con breaker y sin cascada**:
   - `deps.call` hacia U3 (F28) con timeout de 5 s por página, breaker con los umbrales de U7 y sin reintentos dentro del ciclo: un ciclo fallido se recupera en el siguiente (5 min);
   - la lectura incremental que falla a mitad no avanza `last_seq` más allá de la última página confirmada;
   - una lectura completa diaria que falla se reintenta cada 15 min hasta 6 veces; si sigue fallando, el estado incremental se mantiene y `ProductMetricsStale` avisa si tampoco hay lecturas incrementales;
   - readiness solo del proceso: con U3 caído, el servicio sigue publicando los últimos valores.

   (Recomendado)

B) Readiness ligada al registro (el pod sale del balanceo si U3 cae)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: si U3 está caído al arrancar, el servicio no tiene datos y no publica ninguna serie de producto (nunca ceros). Por eso `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing` (Q9) usan `absent()` además de la edad del timestamp.

## Question 5 — Recursos (Scalability)

A) **Pequeños y medidos**:
   - requests 100m / 256 MiB y limits 500m / 512 MiB por réplica (los 6 meses de Q3 son la mayor parte de la memoria durante la recomputación diaria);
   - una prueba con 10 veces el volumen esperado mide el pico de memoria; si supera el 70 % del límite, se ajusta el límite en el Infrastructure Design;
   - prioridad `vectra-normal`.

   (Recomendado)

B) Los mismos recursos que el servicio HTTP de bias (100m / 128 MiB y 500m / 256 MiB)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: el aporte de U11 a la cuota de su namespace suma las 2 réplicas con el proxy de Linkerd (P-U1-14); se registra como cambio al Paso 6 del plan de U1, que ya dice «cuando exista».

## Question 6 — Seguridad (Security)

A) **Identidad y superficie mínimas**:
   - cliente de Keycloak `product-metrics` con `private_key_jwt` y **solo** el scope `registry:read:metrics` (`realm-lint` lo verifica);
   - sin API de negocio: el proceso solo expone `/metrics` y las sondas en 8081, y `Server` de Linkerd admite solo a Prometheus (F60);
   - logs con la allowlist de U0; el `seq` de una entrada excluida solo en el log, nunca en una métrica;
   - sin egress (AUTONOMIA-05).

   (Recomendado)

B) Además, una API HTTP de lectura de las métricas para la consola

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: F28 (lectura del registro) y F50 (token y JWKS con Keycloak) ya incluyen a `product-metrics` en `component-dependency.md`; no hace falta un flujo nuevo.

## Question 7 — Stack del proceso (Tech Stack)

A) **Python sin FastAPI**:
   - un proceso `asyncio` con `vectra_common.process.init(kind="service")`, `deps.call` hacia U3, `prometheus-client` en 8081 y las sondas de U0;
   - sin FastAPI ni `RouteContract`, porque no hay rutas de negocio; el registro de contratos de U0 no se usa;
   - `gen_rules.py` y la plantilla de reglas en el mismo paquete; `promtool` para probarlas.

   (Recomendado)

B) FastAPI con `create_app` de U0, aunque solo sirva `/metrics`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: no encontré en U0 ni en el plan de U8 un servidor de sondas y métricas en 8081 que funcione sin `create_app`. Si U0 no lo ofrece, este NFR agrega a U0 `vectra_common.ops_server` (métricas, `/healthz` y `/readyz`, sin rutas de negocio) y lo registra como cambio a U0; la alternativa es B.

## Question 8 — Pruebas y calidad (Maintainability; PBT-02..10)

A) **Como las demás unidades**:
   - cobertura de ramas 100 % en `compute` y `noise`, ≥ 90 % en el resto; `mutmut` en `compute` y `noise`;
   - PBT-U11-01..07 con perfiles `ci` y `nightly` y la semilla impresa;
   - `promtool test rules` para las alertas y las recording rules; prueba de `gen_rules.py --check`;
   - prueba del dashboard: deduplicación de Q2, targets, nota de aproximación y `forbidden_phrases.py`;
   - carga en kind (operador) con 10 veces el volumen esperado.

   (Recomendado)

B) Solo pruebas de ejemplo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Observabilidad del propio servicio (Reliability)

A) **Métricas del ciclo**: `vectra_product_cycle_duration_seconds{kind="incremental|full"}`, `vectra_product_entries_read_total{kind}`, `vectra_product_last_full_recompute_timestamp` y el estado del breaker hacia U3, en un panel de operación aparte del de producto (carpeta de operación, equipo `operacion`). Alerta adicional `ProductMetricsFullRecomputeMissing` (SEV3) si pasan 26 h sin una recomputación completa exitosa. (Recomendado)

B) Solo las alertas del FD

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la recomputación completa del arranque cuenta como exitosa para `ProductMetricsFullRecomputeMissing`. El panel de operación va en la carpeta de operación de U1 (Paso 12).

---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-requirements.md` (NFR-U11-xx): rendimiento, disponibilidad, resiliencia, recursos, seguridad, pruebas y observabilidad, cada uno con su verificación
- [x] `tech-stack-decisions.md`
- [x] Cambios a otras unidades y al FD de U11 (por ejemplo, Q3) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
