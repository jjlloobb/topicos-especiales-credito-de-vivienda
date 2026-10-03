# Patrones de NFR Design — U7 `scoring-explainability`

Decisiones del plan (`scoring-explainability-nfr-design-plan.md`, Q1–Q4 = A). Los IDs
`P-U7-xx` se referencian en Infrastructure Design y en el plan de tareas. Las verificaciones
en kind las ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las demás corren
en CI.

---

## 1. Presupuestos de tiempo

### P-U7-01 — Presupuesto propagado y explicación en paralelo (Q1)
- **Presupuesto previo al registro en scoring**: al recibir `POST /v1/recommendations`, scoring fija `pre_deadline = llegada + 700 ms`.
  - Cada llamada antes del registro usa `timeout = min(timeout propio de NFR-U7-10, pre_deadline − ahora)`. Esto aplica a `serving-config`, `:predict` y explainability.
  - Si el presupuesto restante es ≤ 0 antes de una llamada, esa llamada no se hace y se aplica la causa de su dependencia (S2 de BR-U0-08).
- **Hacia explainability**:
  - scoring envía la cabecera `x-vectra-deadline` con un instante absoluto en RFC 3339 con milisegundos: `min(ahora + 800 ms, pre_deadline)`.
  - explainability corta todo su trabajo en `min(deadline − 50 ms, llegada + 700 ms)` y, si ese instante llega, responde 504. scoring lo trata como `timeout`.
  - Una cabecera ausente, mal formada o en el pasado se trata como «sin presupuesto externo» y aplica solo el tope de 700 ms. La llamada F12 (resumen al solicitante) no la envía.
  - El tope propio de 700 ms acota el efecto de un desfase de reloj entre nodos (sincronizados por NTP en U1).
- **En explainability, en paralelo**:
  - con la caché del diccionario fría, la consulta del diccionario (F103) y `:explain` (F22) se lanzan a la vez con `asyncio.TaskGroup`;
  - la verificación de versión, la cobertura del diccionario, la narrativa y la factualidad corren cuando ambas terminan;
  - si una falla, la otra se cancela.
- **El helper es de U0**: `vectra_common.deps.call(..., deadline=...)` recorta el timeout al presupuesto restante y propaga la cabecera. `vectra_common.deadline` lee la cabecera entrante. U7 no implementa su propia aritmética de presupuesto.
- Los timeouts de NFR-U7-10 quedan como **máximos por llamada**. El que rige es el menor entre ese y el presupuesto restante.
- **Verificación**:
  - prueba unitaria de `deps.call` en U0: el timeout efectivo nunca supera el presupuesto restante;
  - **propiedad**: para todo presupuesto y toda secuencia de latencias de las dependencias, scoring responde antes de `llegada + 700 ms + 250 ms` (fail_closed best effort, P-U7-02) + 50 ms de margen de proceso, salvo cuando el registro ya fue invocado para una `recommendation`;
  - prueba de integración con caché fría: diccionario a 400 ms y `:explain` a 400 ms → explicación en ~400 ms, no ~800 ms;
  - cabecera en el pasado → 504 inmediato;
  - cabecera a 1 h en el futuro o mal formada → explainability sigue cortando a los 700 ms (una cabecera manipulada no extiende el presupuesto).
- **Satisface**: NFR-U7-04, 10; RESILIENCY-10; SECURITY-11, 15.

### P-U7-02 — Append al registro: presupuesto propio y un reintento (Q2)

| Escritura | Intentos | Timeout por intento | Reintenta ante |
|---|---|---|---|
| `recommendation` (desde `Ready`) | 2 (el original + 1) con la misma `idempotency_key` | 2,5 s (P-U3-02) | 503, timeout o error de conexión. Nunca ante 4xx |
| `fail_closed` (best effort, BR-U7-16) | 1 | 250 ms | — (el caso reevalúa, BR-U0-08) |

- El reintento sale de inmediato, con un jitter de 0 a 100 ms. Si el circuito del registro está abierto, el reintento no se hace.
- Peor caso de una solicitud con el registro degradado: 0,7 s + 2 × 2,5 s + 0,1 s + 0,25 s ≈ **6,1 s**. Queda fuera del p99 (NFR-U7-04 precisado). El timeout de case-service hacia scoring debe superarlo: **≥ 7 s** (pendiente para U8, §8).
- Un 409 de idempotencia (misma llave y otro contenido) es un defecto, no una caída. Se responde `FailClosed(registry_unavailable)`, se registra el log `registry.idempotency_conflict` y se incrementa la métrica que dispara `RegistryIdempotencyConflict` (SEV2).
- Alerta `RegistryAppendSlow` (SEV2): p99 del append de scoring > 1 s durante 5 min.
- **Verificación**:
  - registro doble que falla una vez → dos llamadas con la misma llave y una sola entrada;
  - registro doble lento (3 s) → `FailClosed(registry_unavailable)` en ≤ 6,1 s y métrica `vectra_registry_append_abandoned_total` = 1;
  - un 4xx → un solo intento;
  - `promtool test rules` de las dos alertas.
- **Satisface**: NFR-U7-04 (precisado), 12; BR-U7-15, 16; RESILIENCY-10.

## 2. Evidencia

### P-U7-03 — Recomendaciones escritas y no entregadas: distinguibles (Q3)
- **Caso límite**: el registro confirma el commit después de que scoring dejó de esperar. Pasa cuando los dos intentos vencen o fallan, o cuando el circuito se abre antes del reintento. Queda una entrada `recommendation` que no se entregó.
- **Cómo se distingue**:
  1. scoring cuenta cada abandono en `vectra_registry_append_abandoned_total`, y la alerta `RegistryAppendAbandoned` (SEV2) se dispara con cualquier valor > 0 en 15 min, porque cada abandono **puede** dejar una entrada no entregada;
  2. case-service guarda en el caso el `registry_entry_id` de la `Recommendation` que recibió (U8);
  3. la entrada `human_decision` lleva `recommendation_entry_id`. Lo llena **case-service** con el valor guardado en el caso, nunca el cliente: no está en `DecisionIn` (cambio en U0 domain-entities §5.2);
  4. el expediente (U3, BR-U3-14) calcula `delivery_status` para cada entrada `recommendation` del caso:
     - `entregada`: alguna `human_decision` del caso la referencia;
     - `no_entregada`: el caso tiene una `human_decision` que referencia otra;
     - `pendiente_de_decision`: todavía no hay una `human_decision`.
  5. las proyecciones `monitoring` y `metrics` llevan el `seq` de cada `recommendation` y el `recommendation_entry_id` de cada `human_decision`, para que U9 y U11 cuenten solo las recomendaciones entregadas;
  6. el resumen al solicitante usa la recomendación **entregada**:
     - el BFF envía el `recommendation_entry_id` del caso a explainability;
     - explainability lee esa entrada (proyección `explanation`, ahora con `seq`) y comprueba que pertenece al `case_id` (BR-U7-13 precisada).
- **BR-U0-08 precisada**: todo lo que se **entrega** está en el registro, construido solo desde `Ready`. Una entrada puede existir sin haberse entregado, y queda identificada como tal.
- **Supuesto**: un caso recibe una sola `Recommendation` por cada decisión humana. Si U8 permite reevaluar un caso, su FD revisa el cálculo de `delivery_status` (§8).
- **Verificación**:
  - prueba de integración de scoring: el registro confirma a los 2,6 s en los dos intentos → `FailClosed(registry_unavailable)`; la entrada existe y la métrica sube;
  - prueba de U3: un caso con dos `recommendation` y una `human_decision` que referencia la segunda → la primera sale `no_entregada`;
  - prueba de explainability (caso de abuso: pedir el resumen de un caso ajeno): un `recommendation_entry_id` de otro caso → 409, sin datos parciales;
  - en U3: proyección `explanation` con un `seq` de otro caso → página vacía (Paso 8 del plan de U3).
- **Satisface**: AUTONOMIA-06 (ninguna recomendación sale sin registro); SECURITY-11 (caso de abuso del resumen de un caso ajeno); SECURITY-13 (la evidencia distingue lo entregado de lo no entregado); FR-REG-04.

## 3. Aislamiento y resiliencia

### P-U7-04 — Un cliente por dependencia (bulkhead, Q4)

| Servicio | Dependencia (flujo) | Conexiones máx. por pod | Circuit breaker → causa |
|---|---|---|---|
| scoring | KServe `:predict` (F19) | 20 | `timeout` |
| scoring | explainability (F20) | 20 | `explainer_unavailable` |
| scoring | registro (F21) | 10 | `registry_unavailable` |
| scoring | `serving-config` (F18) | 5 | `serving_config_unavailable` |
| explainability | KServe `:explain` (F22) | 20 | → 503 hacia scoring (`explainer_unavailable`) |
| explainability | diccionario, governance (F103) | 5 | → 503 hacia scoring (`explainer_unavailable`) |
| explainability | registro, proyección `explanation` (F23) | 5 | → 503 hacia el BFF |

- Cada fila es un `httpx.AsyncClient` propio con `Limits(max_connections=N)`. El tiempo que se espera por una conexión libre (`pool timeout`) cuenta dentro del timeout de la llamada (P-U7-01).
- Los umbrales del circuit breaker son los de NFR-U7-11, iguales para todas las filas. El circuit breaker y la métrica `vectra_circuit_state{dependency}` son los de `vectra_common.deps` (P-U0-07, NFR-U7-43).
- Un 503 por saturación de KServe (P-U6-05) cuenta como fallo para el circuito de esa dependencia.
- **Coherencia con U6**:
  - 20 conexiones × 6 pods de scoring superan la capacidad del predictor (16 × 4). El exceso recibe 503 inmediato y falla cerrado. Ese es el bulkhead previsto, no una cola.
  - Al pico de diseño (10/s, p95 30 ms) la concurrencia real es < 1 por pod.
- **Verificación**:
  - prueba de integración con KServe doble colgado: las 20 conexiones a `:predict` se agotan y una explicación pedida en paralelo responde en su tiempo normal;
  - `conftest`/prueba unitaria sobre los límites configurados por cliente.
- **Satisface**: RESILIENCY-10; NFR-U7-11, 43.

### P-U7-05 — Cachés de configuración
- **`serving-config`** en scoring y explainability:
  - caché en memoria por pod de ≤ 5 s, revalidada con `If-None-Match` y `etag` (BR-U7-01; propagación de congelamiento ≤ 6 s, BR-U4-14);
  - si la revalidación falla con la entrada vencida → `serving_state = no_disponible`. Nunca se usa una entrada vencida.
- **Diccionario**:
  - caché en memoria por `feature_dictionary_version`, sin expiración, porque el diccionario de una versión es inmutable (BR-U4-18);
  - máximo 4 versiones por pod (LRU), suficiente para la activa, la `inactivo` del rollback y dos más;
  - precarga al arrancar (NFR-U7-21).
- **Verificación**:
  - congelar en la prueba de integración → la siguiente solicitud tras ≤ 6 s responde `FailClosed(model_frozen)`;
  - caché del diccionario con 5 versiones → se descarta la menos usada;
  - caché vencida + governance caído → `serving_config_unavailable`.
- **Satisface**: NFR-U7-21; AUTONOMIA-04, 06.

### P-U7-06 — Escalado y disponibilidad
- Cada servicio:
  - `Deployment` con ≥ 2 réplicas y `topologySpreadConstraints` por zona;
  - PDB con `minAvailable: 1`;
  - HPA de 2 a 6 por CPU al 70 %, con estabilización de 60 s hacia arriba y 300 s hacia abajo;
  - readiness solo con el proceso (P-U1-04) y liveness del proceso;
  - `PriorityClass` `vectra-high` (P-U1-09);
  - sidecar nativo de Linkerd (P-U1-05).
- **Verificación**: `helm template` + `conftest`. En kind (operador): prueba de carga de U12 con reinicio de réplicas durante la prueba (NFR-U7-22).
- **Satisface**: NFR-U7-20..22; RESILIENCY-01, 06, 08, 09.

## 4. Seguridad

### P-U7-07 — Sin salida y sin datos del solicitante en la telemetría
- `NetworkPolicy` y `AuthorizationPolicy` de U1 y U2:
  - scoring solo sale a F18, F19, F20 y F21;
  - explainability solo sale a F22, F23 y F103;
  - ninguno sale a X01 ni X02.
- Etiquetas de métricas restringidas a `outcome`, `cause`, `reason`, `dependency`, `result`, `attempt` y `stage`. Una prueba falla si aparece cualquier otra.
- Plantillas `template:v1` y `applicant:v1` empaquetadas en la imagen como archivos versionados. Una prueba verifica que la imagen no contiene clientes de LLM (NFR-U7-32).
- **Verificación**:
  - suite de conectividad de U1 (operador en kind);
  - prueba de etiquetas de métricas;
  - prueba de registro de `NarrativeGenerator`.
- **Satisface**: NFR-U7-30..32; AUTONOMIA-03, 05; SECURITY-03.

## 5. Observabilidad

### P-U7-08 — Métricas y alertas de U7

| Métrica | Etiquetas |
|---|---|
| `vectra_recommendations_total` | `outcome` (`favorable`, `desfavorable`, `revision_requerida`, `fail_closed`) |
| `vectra_scoring_failclosed_total` | `cause` (las 10 causas de U0). Es la métrica de BR-U7-03, sobre la que U4 calcula `PromotionMismatchPersistent` (BR-U4-08) |
| `vectra_explanations_total` | `result` (`ok`, `version_mismatch`, `feature_dictionary_incomplete`, `factuality_failed`, `timeout`, `unavailable`, `error`) |
| `vectra_dependency_duration_seconds` (histograma) | `dependency` |
| `vectra_deadline_exhausted_total` | `stage` (`serving_config`, `predict`, `explain`, `dictionary`) |
| `vectra_registry_append_attempts_total` | `attempt` (`1`, `2`), `result` |
| `vectra_registry_append_abandoned_total` | — |
| `vectra_circuit_state` (U0) | `dependency` |

| Alerta | Severidad | Condición |
|---|---|---|
| `CircuitOpen` | SEV2 | Algún circuito abierto más de 2 min |
| `RegistryAppendSlow` | SEV2 | P-U7-02 |
| `RegistryAppendAbandoned` | SEV2 | P-U7-03 |
| `RegistryIdempotencyConflict` | SEV2 | Cualquier conflicto en 15 min (P-U7-02) |
| `FactualityFailed` | SEV2 | Cualquier `factuality_failed` en 15 min. Con una plantilla determinista no debería ocurrir: indica divergencia entre generador y validador |
| `ExplainerVersionMismatch` | SEV2 | Cualquier `version_mismatch` en 15 min (P-U6-02 lo hace imposible por despliegue; si aparece es un defecto o un ataque RT-3). Complementa a `PromotionMismatchPersistent` de U4, que se dispara si el `version_mismatch` dura más de 10 min |
| `RecommendationLatencyHigh` | SEV3 | p95 de `POST /v1/recommendations` > 400 ms durante 15 min |

- Métricas en el puerto 8081 (convención de U0) con `ServiceMonitor`. Toda alerta lleva `runbook_url` (P-U1-10).
- Alertas de otras unidades relacionadas con U7: `PromotionMismatchPersistent` (U4, sobre `vectra_scoring_failclosed_total{cause="version_mismatch"}`) y `FailClosedPersistente` (U1, P-U1-11). Esta última sale de `vectra_cases_failclosed_persistent` de case-service (U8, `services.md`), no de una métrica de U7. Antes, esta tabla decía que `FailClosedPersistente` usaba una métrica de U7 y que esa métrica llevaba `cause` en `vectra_recommendations_total`, en lugar del nombre de BR-U7-03 (corregido el 2026-10-03 al preparar el plan de tareas de U7).
- **Verificación**: `promtool test rules scoring-explainability/observability/rules/tests/*.yaml` y el test de runbooks de U1.
- **Satisface**: RESILIENCY-05, 07, 15; SECURITY-14.

### P-U7-09 — Escenarios de resiliencia (RESILIENCY-14, enfoque C de P-U0-08)

| Escenario | Resultado esperado |
|---|---|
| explainability caído | `FailClosed(explainer_unavailable)` en < 1 s; tras 20 llamadas el circuito se abre y responde en < 50 ms (NFR-U7-11) |
| KServe saturado (503 de P-U6-05) | `FailClosed(timeout)`; ninguna recomendación sin explicación |
| governance caído con la caché vencida | `FailClosed(serving_config_unavailable)` |
| Registro sin réplica síncrona | `FailClosed(registry_unavailable)` en ≤ 6,1 s; `RegistryAppendAbandoned` se dispara; el expediente marca la entrada, si quedó, como `no_entregada` tras la decisión |
| Promoción azul/verde con tráfico | 0 `version_mismatch` (comparte el escenario de P-U6-02) |

- Se documentan aquí y se ejecutan en Operations (P-U0-08). Las pruebas de integración con dobles de P-U7-01..05 cubren la lógica en CI.
- **Satisface**: RESILIENCY-14.

## 6. Cumplimiento de extensiones (NFR Design U7)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | P-U7-06, 07, 09: lo que se verifica en kind lo ejecuta el operador después de un PR aprobado |
| AUTONOMIA-02 | Cumple | Cada patrón tiene su «Verificación» |
| AUTONOMIA-03 | Cumple | P-U7-07 (sin salida a X01) |
| AUTONOMIA-04 | Cumple | P-U7-05 (nunca se usa una `serving-config` vencida; el congelamiento llega en ≤ 6 s) |
| AUTONOMIA-05 | Cumple | P-U7-07 (sin salida a X02; telemetría sin datos del solicitante) |
| AUTONOMIA-06 | Cumple | P-U7-01, 02, 03, 05: presupuestos que terminan en fail-closed; ninguna recomendación sin registro |
| SECURITY-03 | Cumple | P-U7-07 (etiquetas de métricas acotadas) |
| SECURITY-11 | Cumple | Casos de abuso con prueba: P-U7-03 (resumen pedido con un `recommendation_entry_id` de otro caso → 409; en U3, `seq` de otro caso → página vacía) y P-U7-01 (cabecera `x-vectra-deadline` manipulada, en el pasado o muy en el futuro → no extiende el presupuesto). Se suma a los casos RT-1 y RT-3 de U5 ya citados en el FD (BR-U7-12, PBT-U7-08) y a `ExplainerVersionMismatch` (P-U7-08) (agregado el 2026-10-03 por revisión del usuario) |
| SECURITY-13 | Cumple | P-U7-03 (la evidencia distingue lo entregado de lo no entregado; el resumen usa la recomendación entregada) |
| SECURITY-14 | Cumple | P-U7-08 |
| SECURITY-15 | Cumple | P-U7-01, 02, 04 (fallos acotados en tiempo y cerrados) |
| RESILIENCY-01 | Cumple | P-U7-06 (`vectra-high`, P-U1-09) |
| RESILIENCY-02 | Cumple | P-U7-01, 02 (presupuesto de la ruta crítica; el caso del registro degradado queda explícito fuera del p99) |
| RESILIENCY-05 / 07 / 15 | Cumple | P-U7-08 |
| RESILIENCY-06 | Cumple | P-U7-06 (readiness solo con el proceso) |
| RESILIENCY-08 / 09 | Cumple | P-U7-06 |
| RESILIENCY-10 | Cumple | P-U7-01, 02, 04 |
| RESILIENCY-14 | Cumple | P-U7-09 (enfoque C) |
| PBT-06 | Cumple | Propiedad stateful del circuit breaker (U0, P-U0-07) |
| PBT-08 / 09 | Cumple | NFR-U7-42; propiedad de P-U7-01 con el perfil `ci` |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

Las mismas filas están en la tabla de cambios a otras unidades de U7 (`functional-design/business-rules.md` §6), que es el registro acumulado de la unidad.

| Artefacto | Cambio | Origen |
|---|---|---|
| U7 NFR-U7-04, NFR-U7-10 | NFR-U7-04 precisado: un registro degradado queda fuera del p99. NFR-U7-10: los timeouts son máximos dentro del presupuesto propagado | Q1, Q2 |
| U7 BR-U7-13, BR-U7-15; business-logic-model §2.3; domain-entities §4 | BR-U7-13: el resumen usa el `recommendation_entry_id` que envía el BFF (flujo §2.3 y `ApplicantSummaryRequest`). BR-U7-15: reintento solo ante 503, timeout o error de conexión | Q2, Q3 |
| U0 business-rules BR-U0-08, BR-U0-35 | BR-U0-08: lo que se entrega está en el registro, y una entrada no entregada queda identificada. BR-U0-35: case-service compara contra la recomendación guardada en el caso | Q3 |
| U0 domain-entities §5.2 `human_decision` y §9.1 | Campo `recommendation_entry_id`, lo llena case-service; tipo nuevo `ApplicantSummaryRequest` | Q3 |
| U0 NFR Design P-U0-07 y su fila RESILIENCY-10; plan de tareas Paso 10 | `deps.call(..., deadline=)`, `vectra_common.deadline` y un cliente por dependencia con límite de conexiones; la fila de cumplimiento ya no dice que U7 y U8 diseñan el circuit breaker | Q1, Q4 |
| U3 BR-U3-14, domain-entities §3 y §4.1; plan de tareas Paso 8 | `delivery_status` por `recommendation` en el expediente; `seq` y `recommendation_entry_id` en las proyecciones; filtros de `EntryFilter` en el Paso 8 | Q3 |
| `component-methods.md` (explainability `applicant_summary`) | Recibe `case_id` y `recommendation_entry_id` | Q3 |

## 8. Pendiente para U8 `case-management`
- Guardar en el caso el `registry_entry_id` de la `Recommendation` recibida y llenar con él `human_decision.recommendation_entry_id` (P-U7-03).
- Timeout de case-service hacia scoring ≥ 7 s (P-U7-02).
- Si U8 permite reevaluar un caso con decisión pendiente, revisar `delivery_status` (P-U7-03).

## 9. Pendiente para U9 `bias-monitoring` y U11 `product-metrics`
- Contar solo las `recommendation` entregadas: las que referencia una `human_decision` por `recommendation_entry_id` (proyecciones `monitoring` y `metrics`, P-U7-03).
