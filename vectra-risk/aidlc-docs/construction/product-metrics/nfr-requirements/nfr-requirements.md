# Requisitos no funcionales — U11 `product-metrics`

Decisiones del plan (`product-metrics-nfr-requirements-plan.md`, Q1–Q9 = A, con las notas del
usuario). Las verificaciones «en kind» las ejecuta el operador después de un PR aprobado
(AUTONOMIA-01); las demás corren en CI.

Los IDs `NFR-U11-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Rendimiento (Q1)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-01 | **Lectura incremental** (cada 5 min): p95 ≤ 5 s, en páginas de 1 000 entradas leídas una tras otra (nunca en paralelo) | Prueba de integración con un doble de U3 con latencia; en kind, la métrica del ciclo |
| NFR-U11-02 | **Lectura completa diaria**, incluidos los 6 meses cerrados de NFR-U11-10: ≤ 15 min con el volumen esperado y ≤ 60 min con 10 veces ese volumen; **p95 de página ≤ 1 s** (el pool `projections` de U3 espera 2 s) | CI con un doble de U3 a 10 veces el volumen de NFR-U3-30 durante 7 meses y con la latencia de página del p95 de U3; kind con el registro real a 1 vez; la medición a 10 veces contra U3 real (contención del pool `projections`) queda para Operations (Infrastructure Design de U11, 2026-10-10, INF-U11-06) |
| NFR-U11-03 | `compute` sobre 35 días: ≤ 5 s | Benchmark en CI con el volumen esperado × 10 |
| NFR-U11-04 | **Sin coincidencia entre réplicas**: la recomputación diaria empieza a las 02:30 UTC más un desfase aleatorio de 0 a 10 min por réplica, fuera del horario operativo | Prueba de unidad determinista del planificador (pendientes posteriores al cierre, 2026-10-10): el desfase se toma de una distribución uniforme en [0, 600] s con un generador inyectable; con semillas fijas, (a) todo desfase de 10 000 sorteos cae en [0, 600] s y la hora de inicio en [02:30, 02:40] UTC; (b) dos réplicas con semillas fijas distintas dan desfases distintos en el día simulado; (c) la misma semilla da la misma secuencia. Sin umbrales estadísticos ni aleatoriedad no sembrada en CI |

## 2. Disponibilidad y series duplicadas (Q2, Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-05 | **2 réplicas fijas** con `vectra.io/hpa-exempt`, PDB `minAvailable: 1` y spread por zona; cada una lee y calcula por su cuenta, sin coordinación | `conftest` sobre el chart; `kyverno test` de `require-hpa-bounds` |
| NFR-U11-06 | **Deduplicación**: toda consulta del dashboard y toda regla de agregación usan `max without (instance, pod) (…)` antes de cualquier `sum`. Las alertas `RuidoExplicacion` y `ProductMetricsDegraded` también, para no dispararse dos veces. `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing` quedan **por réplica**, porque una réplica atrasada es una falla real; Alertmanager las agrupa por `alertname` (nota de Q2) | Prueba sobre `product.json` y las reglas: un `sum` sin deduplicación previa → falla; `promtool test rules` con dos réplicas que publican lo mismo → una sola alerta de ruido |
| NFR-U11-07 | **Readiness** (precisada en el Infrastructure Design de U11, 2026-10-10, INF-U11-01): lista si el proceso tiene una instantánea publicada **o** si el breaker hacia U3 está abierto o semiabierto; una pasada fallida o vencida no basta, y al cerrarse el breaker sin instantánea vuelve a 503 (revisión del Infrastructure Design de U11, 2026-10-10). Así un rollout con U3 sano no reemplaza la segunda réplica hasta que la primera tiene datos, y con U3 caído no se bloquea. Con U3 caído, el servicio sigue publicando los últimos valores. Si U3 está caído **al arrancar**, no hay datos y el servicio no publica ninguna serie de producto (nunca ceros) (nota de Q4) | Pruebas de readiness (pendientes posteriores al cierre, 2026-10-10), con el predicado de `ops_server`: sin instantánea y breaker cerrado → 503; sin instantánea y breaker abierto → 200; sin instantánea y semiabierto → 200; con instantánea y cualquier estado del breaker → 200; pasada fallida o vencida sin instantánea y breaker cerrado → 503; breaker que se cierra sin instantánea → vuelve a 503; el predicado que lanza una excepción → 503. Arranque con U3 caído: `/readyz` 200 cuando el breaker abre y `/metrics` sin series `vectra_product_*` de producto |
| NFR-U11-08 | **Alertas por réplica, también cuando falta la serie** (revisión del NFR Requirements de U11, 2026-10-10): `absent(x)` solo dispara si no existe **ninguna** serie, así que con 2 réplicas no ve una réplica que dejó de publicar mientras la otra sigue. Por eso la ausencia se compara con las réplicas vivas: `ProductMetricsStale` son dos reglas con el mismo nombre: edad, `time() - vectra_product_metrics_last_success_timestamp > 1800` con `for: 0`, y ausencia, `up{job="product-metrics"} == 1 unless on (pod) vectra_product_metrics_last_success_timestamp` con `for: 30m`; ninguna dispara mientras `vectra_product_full_pass_in_progress == 1` en esa réplica (P-U11-02; revisión del NFR Design de U11, 2026-10-10). `ProductMetricsFullRecomputeMissing`, igual con `vectra_product_last_full_recompute_timestamp`: edad > 93 600 s (26 h) con `for: 0` y ausencia con `for: 26h`, también sin disparar durante la pasada (pendientes posteriores al cierre, 2026-10-10). Una réplica caída (`up == 0`) la cubren las alertas de U1 sobre los pods. La lectura completa del arranque cuenta como recomputación exitosa (notas de Q4 y Q9) | `promtool test rules`: serie vieja → dispara; serie presente y reciente en las dos réplicas → no dispara; **una réplica sin la serie y la otra con ella** (las dos con `up = 1`) → dispara solo para la réplica sin la serie; las dos sin la serie → dispara para las dos; con la pasada en curso, ninguna rama dispara; la rama de edad dispara sin esperar otros 30 min (pendientes posteriores al cierre, 2026-10-10); réplica recién arrancada con U3 caído, sin `vectra_product_last_full_recompute_timestamp` → `ProductMetricsFullRecomputeMissing` no dispara antes de 26 h (pendientes consolidados, 2026-10-10) |

## 3. Resiliencia (Q4; RESILIENCY-10)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-09 | `deps.call` hacia U3 (F28) con timeout de 5 s por página y el breaker de `deps.call` en modo `consecutive_failures` de U0 (NFR-U0-23 (i)), con `consecutive_failures=3`, `open_for=60s` y `close_after=1`: abre con 3 fallos seguidos, semiabierto a los 60 s, cierra con 1 éxito; U11 no implementa un breaker propio (pendientes consolidados, 2026-10-10) (los de U7 no se alcanzan con lecturas en serie; revisión del Infrastructure Design de U11, 2026-10-10); **sin reintentos dentro del ciclo**: un ciclo fallido se recupera en el siguiente. Una lectura incremental que falla a mitad no avanza `last_seq` más allá de la última página confirmada. Una lectura completa diaria fallida se reintenta cada 15 min hasta 6 veces; si sigue fallando, el estado incremental se mantiene | Pruebas con dobles: fallo en la página 3 de 5 → `last_seq` queda en la página 2; la siguiente lectura sigue desde ahí; lectura completa fallida → reintentos cada 15 min (reloj simulado) |

## 4. Historia de 6 meses (Q3; FR-MET-05)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-10 | **Meses cerrados**: en la recomputación diaria, el servicio lee también las `human_decision` de los últimos 6 meses calendario cerrados y publica cada mes con la etiqueta `month="AAAA-MM"` (`period="month"`) para la North Star, la sostenida y la tasa de consulta (conteos y razones, BR-U11-08). Así el dashboard muestra 6 meses sin depender de los 30 días de Prometheus | Prueba de integración con 7 meses de datos: se publican exactamente los 6 cerrados |
| NFR-U11-11 | **Un mes cerrado puede cambiar**: BR-U0-37 acepta momentos de negocio hasta 7 días antes de `occurred_at`, así que una decisión del último día de un mes puede registrarse hasta 7 días después. La recomputación diaria **republica** los 6 meses cada día en lugar de congelarlos (nota 1 de Q3) | Prueba: una decisión del 30 de septiembre registrada el 5 de octubre cambia la serie `month="2026-09"` en la recomputación del 6 de octubre |
| NFR-U11-12 | **Los meses no viven como entradas en memoria**: el servicio pliega cada página en contadores por mes y por corte y descarta las entradas de los meses cerrados; solo los 35 días de BR-U11-11 guardan entradas (nota 2 de Q3) | Prueba de memoria con 6 meses × 10 veces el volumen: el pico no crece con el número de entradas de meses cerrados |

## 5. Recursos (Q5)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-13 | requests 100m / 256 MiB y limits 500m / 512 MiB por réplica; `vectra-normal`. El pico de memoria se mide con 10 veces el volumen; si supera el 70 % del límite, se ajusta en el Infrastructure Design | CI con el doble de U3 a 10 veces (`tracemalloc` y RSS); kind a 1 vez (Infrastructure Design de U11, 2026-10-10, INF-U11-06) |
| NFR-U11-14 | **Aporte a la cuota de `vectra-app`** con el proxy de Linkerd (P-U1-14) y los pods del rollout (`maxSurge: 1`, `maxUnavailable: 0`: 3 pods en el peor momento), con el 30 % de margen: requests ≈ 0,78 CPU y 1,05 GiB; limits ≈ 3,9 CPU y 2,44 GiB (nota de Q5) | `conftest test platform/policies/quotas/` |

## 6. Seguridad (Q6)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-20 | Cliente de Keycloak `product-metrics` con `private_key_jwt` y **solo** `registry:read:metrics`; `realm-lint` lo verifica | `realm-lint` de U2 con un caso que agrega otro scope → falla |
| NFR-U11-21 | Sin API de negocio: solo `/metrics`, `/healthz` y `/readyz` en 8081; el `Server` de Linkerd admite solo a Prometheus (F60). Flujos existentes: F28 (registro), F50 (token y JWKS) y F60; no hace falta uno nuevo (nota de Q6) | Suite de conectividad de U1: otro pod → 8081 bloqueado |
| NFR-U11-22 | Logs con la allowlist de U0; el `seq` de una entrada excluida solo en el log, nunca en una métrica; sin egress (AUTONOMIA-05) | PBT-U0-07 en modo strict; PBT-U11-05 |

## 7. Pruebas (Q8; PBT-02..10)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-30 | Cobertura de ramas 100 % en `compute` y `noise`, ≥ 90 % en el resto; `mutmut` en `compute` y `noise` con 0 sobrevivientes sin justificar | `pytest-cov`, `mutmut` |
| NFR-U11-31 | PBT-U11-01..07 con perfiles `ci` y `nightly` y la semilla impresa | Workflow de CI |
| NFR-U11-32 | `promtool test rules` de las alertas y las recording rules; `gen_rules.py --check` | CI |
| NFR-U11-33 | Prueba del dashboard: deduplicación (NFR-U11-06), targets, nota de aproximación de BR-U11-04 y `forbidden_phrases.py` | CI |

## 8. Observabilidad del servicio (Q9)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U11-40 | Métricas del ciclo: `vectra_product_cycle_duration_seconds{kind="incremental\|full"}`, `vectra_product_entries_read_total{kind}`, `vectra_product_last_full_recompute_timestamp` (que **no se emite** hasta la primera pasada completa exitosa: nunca vale 0 al arrancar; pendientes consolidados, 2026-10-10) y el estado del breaker hacia U3 (`vectra_circuit_state{dependency="decision-registry"}` de U0). Están en la allowlist de domain-entities §5, en su sección de operación (revisión del NFR Requirements de U11, 2026-10-10) | Prueba de `/metrics` contra la allowlist completa |
| NFR-U11-41 | Panel de operación aparte del de producto, en la carpeta de operación de U1 (equipo `operacion`; plan de U1, Paso 12) | Prueba del aprovisionamiento |
| NFR-U11-42 | Alerta `ProductMetricsFullRecomputeMissing` (SEV3), por réplica, con una rama de edad y una de ausencia frente a `up` (NFR-U11-08; antes decía `absent()`, pendientes posteriores al cierre, 2026-10-10) | `promtool test rules` |

## 9. Cumplimiento de extensiones (NFR Requirements U11)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | Criticidad Medium; fuera de la ruta de decisión |
| RESILIENCY-05 / 07 / 15 | Cumple | NFR-U11-06, 08, 42 |
| RESILIENCY-08 / 09 | Cumple | NFR-U11-05, 13, 14 |
| RESILIENCY-10 | Cumple | NFR-U11-07, 09 |
| SECURITY-03 | Cumple | NFR-U11-22 |
| SECURITY-06 / 08 | Cumple | NFR-U11-20, 21 |
| AUTONOMIA-05 | Cumple | NFR-U11-22 |
| PBT-02..10 | Cumple | NFR-U11-30..33 |

## 10. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U11 FD BR-U11-08 y BR-U11-11 | Meses cerrados `month="AAAA-MM"` (6) republicados cada día; contadores plegados por mes, sin entradas de meses cerrados en memoria; desfase aleatorio de la recomputación diaria | Q1, Q3 |
| U11 FD BR-U11-14 | Deduplicación en `RuidoExplicacion` y `ProductMetricsDegraded`; `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing` por réplica, con ramas de edad y de ausencia (antes decía `absent()`; pendientes posteriores al cierre, 2026-10-10) | Q2, Q4, Q9 |
| U0 (`vectra_common`, NFR, logical-components, plan Paso 10) | `vectra_common.ops_server`: servidor de 8081 con `/metrics`, `/healthz` y `/readyz`, sin rutas de negocio, para procesos `service` que no usan `create_app` | Q7 |
| U1 plan (Paso 6) | Aporte de U11 a la cuota de `vectra-app` (NFR-U11-14) | Q5 |
| U1 plan (Paso 12) | Panel de operación de U11 en la carpeta de operación | Q9 |
| U2 realm | Cliente `product-metrics` solo con `registry:read:metrics` (verificado por `realm-lint`) | Q6 |
