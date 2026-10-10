# Plan de Functional Design — U11 `product-metrics`

**Alcance de la unidad** (`unit-of-work.md` U11):
- Servicio `product-metrics`: North Star, tasa de consulta de la explicación, tasa sostenida y tiempo de originación, publicados en `/metrics` para Prometheus (C13).
- Recording y alerting rules, incluida `RuidoExplicacion`.
- Dashboards de producto en Grafana como código.
- Sin datos propios: lee el registro por **F28** (proyección `metrics`, scope `registry:read:metrics`).

**Historias (dueña):** US-503 (North Star), US-504 (métrica de ruido con alerta), US-505
(métricas operativas y de producto). Requisitos FR-MET-01..05; los targets son **[INTERNO]**
(PRD §10).

**Ya decidido** (no se pregunta):
- **Proyección `metrics` de U3** (domain-entities §3): `recommendation`, `human_decision` y `explanation_view`, con `entry_type`, `case_id`, `outcome`, `decision`, `final_outcome`, `used_factors`, `explanation_viewed_before`, `actor_role`, `recorded_at`, `seq`, `recommendation_entry_id`, `evaluated_at`, `decided_at` y `viewed_at`. **Sin** `user_id`, `feature_vector` ni `justification`.
- **Métricas que ya publica U7**: `vectra_recommendations_total{outcome}` (incluido `fail_closed`) y `vectra_scoring_failclosed_total{cause}`.
- **Pendientes que otras unidades dejaron para U11:**
  - **U8** (business-rules §8): medir con los momentos de negocio (`evaluated_at`, `decided_at`, `viewed_at`), no con `recorded_at`;
  - **U7** (NFR Design §9): contar solo las recomendaciones **entregadas**, es decir, las que referencia una `human_decision` por `recommendation_entry_id` (P-U7-03).
- **Dashboard en Grafana**: organización `Vectra`, aprovisionado y de solo lectura (como `bias.json`, U9 INF-U9-05); textos sin frases prohibidas (BR-U0-94).

**Hallazgos que este FD debe resolver:**
- FR-MET-05 habla de decisiones «sostenidas sin modificación por el **comité**», pero el sistema no registra ninguna revisión del comité: solo la decisión del analista (Q2).
- La proyección `metrics` no trae las entradas `fail_closed`, así que FR-MET-03 no puede salir del registro tal como está (Q4).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Qué cuenta en la North Star (Business Rules; FR-MET-01, US-503)
US-503: «decisiones con factores marcados, apartadas o sustentadas / total de decisiones».

A) **La explicación pesó en la decisión** (numerador), sobre las decisiones con una recomendación entregada (denominador):
   - una decisión cuenta si `explanation_viewed_before = true` **y** `used_factors ≠ ["ninguno"]`, cualquiera sea la decisión (`sigue`, `se_aparta` o `resuelve_revision`): el analista vio la explicación y declaró qué factores usó;
   - denominador: todas las `human_decision` del periodo que referencian una `recommendation`;
   - además se publican, como desglose, las tres partes: «sustentada» (`sigue` con factores), «cambiada» (`se_aparta` con factores) y «revisión resuelta» (`resuelve_revision` con factores).

   (Recomendado)

B) Solo `used_factors ≠ ["ninguno"]`, sin exigir la consulta de la explicación

C) Solo las decisiones `se_aparta` y `resuelve_revision` con factores (la explicación «cambió» la decisión)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — «Sostenidas por el comité» sin un registro del comité (Business Rules; FR-MET-05, US-505)
El sistema no tiene una entidad de revisión del comité.

A) **Proxy explícito y marcado**: «tasa de recomendaciones sostenidas» = decisiones `sigue` / decisiones con recomendación entregada, publicada con el nombre `vectra_product_recommendation_sustained_ratio` y una nota fija en el panel: «aproximación: mide si la decisión siguió la recomendación; la revisión del comité no está en el sistema». El target (> 70 % al mes 6) queda **[INTERNO]**. La medición real del comité queda como pendiente para Operations (requiere un registro de la revisión del comité). (Recomendado)

B) Agregar en esta unidad una entrada nueva `committee_review` al registro (U0, U3, U8 y U10 cambian)

C) No publicar FR-MET-05 hasta que exista el registro del comité

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Tiempo de originación (Business Rules; FR-MET-04, US-505)
Target **[INTERNO]**: < 1 h en el 80 % de los casos estándar.

A) **Desde la creación del caso hasta la recomendación entregada**:
   - inicio = `occurred_at` de la solicitud en case-service (U8 `created_at`), llevado al registro como `received_at` en el payload de `recommendation` (cambio en U0 §5.2 y U8);
   - fin = `evaluated_at` de la recomendación **entregada** (la que referencia la decisión);
   - «caso estándar» = canal distinto de `manual`, sin `revision_requerida` y sin fail-closed antes de la entrega (`attempt = 1`);
   - se publica el p50, el p80 y el p95 por día y el porcentaje bajo 1 h.

   (Recomendado)

B) Desde `received_at` hasta la decisión humana (`decided_at`), que mide el proceso completo y no solo el sistema

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la opción A mide hasta la recomendación entregada, no hasta la decisión. Si el PRD §10 entiende el tiempo de originación como el proceso completo, se cambia a B antes del Functional Design. La proyección `metrics` de U3 (domain-entities §3 y el scope) agrega `received_at`, `channel` y `attempt` en el payload de `recommendation`.

## Question 4 — % con score y explicación, y frecuencia de fail-closed (Business Rules; FR-MET-03, US-505)
La proyección `metrics` no trae `fail_closed`. U7 ya publica contadores en Prometheus.

A) **Desde las métricas de U7, con recording rules de U11**:
   - «% de solicitudes con score y explicación en el mismo request» = `recommendation` / (`recommendation` + `fail_closed`) de `vectra_recommendations_total`, por intento, en ventanas de 1 h y 1 día. Por la invariante de U0 (BR-U0-01..08) toda `recommendation` lleva su explicación, así que el número mide cuántas solicitudes llegan a una respuesta completa;
   - «frecuencia de fail-closed por desincronía» = `vectra_scoring_failclosed_total{cause="version_mismatch"}` (y las causas de desincronía de BR-U0-02) por hora;
   - U11 no lee el registro para esto.

   (Recomendado)

B) Agregar `fail_closed` a la proyección `metrics` de U3 y calcularlo en el servicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Métrica de ruido y su alerta (Business Rules; FR-MET-02, US-504)

A) **Tasa diaria con piso, ventana y mínimo de muestra**:
   - tasa de consulta = decisiones con `explanation_viewed_before = true` / decisiones, por día de `decided_at`, en una ventana móvil de 7 días;
   - `RuidoExplicacion` (SEV3) dispara si la tasa de la ventana está bajo el piso **F** durante **S** seguidos, y solo si la ventana tiene al menos **N** decisiones (sin muestra, no alerta);
   - valores iniciales **[INTERNO]**, a acordar con el piloto: F = 0,6, S = 3 días, N = 50;
   - F, S y N viven en un archivo de parámetros con `CODEOWNERS` de producto y riesgo, como los parámetros de U9 (INF-U9-03), con rangos validados.

   (Recomendado)

B) Piso fijo sin mínimo de muestra (alerta con pocos casos)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la alerta se calcula sobre una serie «días consecutivos bajo el piso» publicada por el servicio, en lugar de un `for: 3d`, que es frágil ante reinicios.

## Question 6 — Cómo se calcula (Business Logic Model; F28)

A) **Recomputación periódica en el servicio, sin estado propio**:
   - cada 5 min, el servicio lee la proyección `metrics` de los últimos 35 días por `decided_at` (cubre la ventana de 30 días y un margen para escrituras tardías), con paginación por `seq`, y recalcula todas las métricas en memoria;
   - publica gauges en `/metrics`; si la lectura falla, conserva los últimos valores y publica `vectra_product_metrics_last_success_timestamp`, con la alerta `ProductMetricsStale` (SEV3);
   - volumen esperado: decenas de miles de entradas en 35 días, que caben en memoria;
   - el cálculo es una función pura `compute(entries, now) -> BusinessMetrics`, probada con propiedades.

   (Recomendado)

B) Un agregador en U3 (tablas derivadas como las de monitoreo de U9) y una consulta agregada

X) Other (please describe after [Answer]: tag below)

[Answer]: X) A, con dos ajustes. (1) Lectura incremental por `seq` en cada ciclo de 5 min y una recomputación completa de 35 días una vez al día, para no repetir 288 lecturas completas al día por réplica sobre el pool `projections` de U3. (2) Las `recommendation` se leen por `evaluated_at` con un margen mayor que el de las decisiones, o el registro resuelve `recommendation_entry_id`; si no, una decisión sobre una recomendación vieja saldría como «no atribuible».

## Question 7 — Qué recomendación cuenta y con qué momento (Business Rules; pendientes de U7 y U8)

A) **Solo las entregadas, por momento de negocio**:
   - cada decisión se une con la `recommendation` que referencia (`recommendation_entry_id` = `seq`); las recomendaciones sin decisión no cuentan en la North Star, en la de ruido ni en la sostenida;
   - una `explanation_view` cuenta solo si su `viewed_at` es anterior al `decided_at` de la decisión del mismo caso (coincide con `explanation_viewed_before`, que se usa como fuente principal);
   - las métricas se asignan al día de `decided_at`; el tiempo de originación, al día de `evaluated_at`;
   - una decisión cuya recomendación referenciada no existe en la ventana cuenta como **no atribuible** y se publica aparte (`vectra_product_unattributable_decisions`), sin entrar en los cocientes.

   (Recomendado)

B) Contar todas las recomendaciones, entregadas o no

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Cortes y periodos (Business Rules; US-503, US-505)

A) **Pocos cortes, sin datos por persona**:
   - periodos: día, ventana móvil de 30 días y mes calendario (UTC; el dashboard muestra la hora de Colombia);
   - cortes: por canal y por `outcome` de la recomendación; por versión de modelo solo en la North Star;
   - **nunca** por usuario: la proyección no trae `user_id` y las métricas no deben servir para vigilar a un analista; `actor_role` solo como filtro.

   (Recomendado)

B) Además, por analista (exige `user_id` en la proyección)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: la proyección `metrics` de U3 agrega `model_version` y `channel` (con `received_at` y `attempt` de Q3); lo registra el Functional Design como cambio a U3.

## Question 9 — Targets en el dashboard (Business Rules; US-505)

A) **Targets como parámetros versionados**: los targets del PRD §10 (100 % con score y explicación; < 1 h en el 80 %; > 70 % sostenidas al mes 6; North Star «a definir con el piloto») van en el mismo archivo de parámetros de Q5, marcados **[INTERNO]**, y el dashboard los dibuja como líneas de referencia. Un target sin definir (la North Star) se muestra como «sin target acordado». (Recomendado)

B) Targets escritos en el JSON del dashboard

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Quién ve el dashboard (Security; US-503..505)

A) **CRO y cumplimiento**: carpeta `Vectra / Producto` con `View` para los equipos `cro` y `cumplimiento`; `ingeniero_riesgo` también, porque las métricas de fail-closed son de operación del modelo; `analista` no (las métricas describen el trabajo de los analistas). La consola no lo embebe: se abre en Grafana. (Recomendado)

B) Solo CRO

X) Other (please describe after [Answer]: tag below)

[Answer]: A

Nota: los permisos de la carpeta `Vectra / Producto` no deben heredar los del rol de la organización (`ingeniero_riesgo` Viewer, `operacion` Editor). El Functional Design define el mecanismo (API o Job de aprovisionamiento) y la prueba con `ingeniero-1` y `operacion-1`, compartido con el de U9.

## Question 11 — Calidad de los datos (Business Rules)

A) **Exclusión visible**:
   - una decisión con un campo fuera del catálogo (por ejemplo, un `decision` desconocido) o con `decided_at` posterior a `recorded_at` se excluye y se cuenta en `vectra_product_invalid_entries` con su `seq` solo en el log;
   - si las excluidas superan el 1 % de la ventana, las métricas se publican igual pero con `vectra_product_metrics_degraded = 1` y el panel lo muestra.

   (Recomendado)

B) Fallar el cálculo completo, como U9

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `business-rules.md` (BR-U11-xx): definiciones de las cinco métricas, unión con la recomendación entregada, momentos de negocio, cortes, parámetros y targets, calidad de datos, alertas
- [x] `domain-entities.md`: `BusinessMetrics`, entradas leídas, parámetros, series publicadas
- [x] `business-logic-model.md`: flujo de la corrida, función pura `compute`, reglas de Prometheus, propiedades (PBT-U11-xx) y pruebas de ejemplo
- [x] Cambios a otras unidades (por ejemplo, U0 y U8 si Q3 = A) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
