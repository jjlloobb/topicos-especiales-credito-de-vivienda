# Plan de NFR Design — U8 `case-management`

**Alcance:** convertir NFR-U8-01..53 en patrones y componentes lógicos, y cerrar los
pendientes del §7 del NFR. Al cruzar los requisitos con el diseño funcional apareció
**una inconsistencia** que hay que resolver aquí (Q2).

**Ya decidido** (no se pregunta):
- el Functional Design;
- dos Deployments con la misma imagen, el HPA y el margen de 4× (NFR-U8-10..14);
- la cola en `evaluation_jobs` con `SKIP LOCKED` y sondeo ≤ 500 ms (NFR-U8-04, 11);
- los timeouts y el circuit breaker de `vectra_common.deps` (NFR-U8-30..34);
- el umbral de dos corridas de `CaseRetentionOverdue` (NFR-U8-46(e));
- RESILIENCY-14 = C (la ejecución de los escenarios se difiere a Operations);
- las severidades del proyecto (P-U1-10): SEV1 → 15 min, SEV2 → 1 h, SEV3 → siguiente día hábil, todas con `runbook_url`.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q5 |
| Scalability Patterns | Q3 (umbral de la cola atrasada). **Sin más preguntas**: réplicas, HPA y pool ya están en NFR-U8-10..14 |
| Performance Patterns | Q3, Q6 |
| Security Patterns | Q2, Q4 |
| Logical Components | Q1, Q2, Q6 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Alertas de evidencia pendiente y abandonada (Resilience; pendiente del FD, BR-U8-18)
Una decisión `pendiente_registro` bloquea el caso: el analista no puede volver a decidir hasta
la confirmación o hasta el abandono a las 24 h. Una entrada `fail_closed` abandonada deja un
escalamiento sin evidencia en el registro.

A) **Dos alertas sobre el outbox**, siguiendo el estilo de U4 (P-U4-02). El reconciliador expone `vectra_case_evidence_pending_oldest_seconds{entry_type}` y `vectra_case_evidence_abandoned_total{entry_type}`:

   | Alerta | Condición | Severidad |
   |---|---|---|
   | `CaseEvidencePending` | Una `human_decision` o un `fail_closed` lleva más de **30 min** `pendiente_registro` | SEV2 |
   | `CaseEvidencePending` | Una `explanation_view` lleva más de **2 h** pendiente | SEV3 |
   | `CaseEvidenceAbandoned` | Cualquier abandono de `human_decision` o `fail_closed` en los últimos 15 min | SEV2 |
   | `CaseEvidenceAbandoned` | Abandono de una `explanation_view` | SEV3 |

   30 min deja 23,5 h para actuar antes del abandono, y una `explanation_view` pendiente no bloquea nada (solo puede subestimar `explanation_viewed_before`, BR-U8-17). (Recomendado)

B) Una sola alerta SEV2 para todos los tipos: pendiente más de 1 h o cualquier abandono

C) Solo la alerta de abandono (SEV2), sin aviso previo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Cómo sabe el trigger `guard_vencido` que la retención venció (Security / Logical Components)
**Inconsistencia entre BR-U8-20 y NFR-U8-46(f).** BR-U8-20 dice que el trigger solo permite
`state = vencido` «con la retención vencida». Pero NFR-U8-46(f) deja los plazos como
**parámetros** del job (`retention.undecided_years = 2`), no como datos de la base. Si el
trigger no conoce el plazo, no puede comprobar esa condición. Si lo lleva fijo en su código,
hay dos fuentes del mismo valor.

A) **Plazos en una tabla de la base, con una sola fuente**:
   - tabla `retention_settings`, de una sola fila (`decided_years`, `undecided_years`, `intake_keys_days`);
   - la escribe solo `case_migrator`, con el Job de migración, a partir de los values de Helm (F44);
   - `case_retention` y `case_app` solo la leen;
   - el job **lee** los plazos de esa tabla, no de sus argumentos;
   - `guard_vencido` comprueba:
     - `current_user = 'case_retention'`;
     - un estado de origen no terminal;
     - `created_at + undecided_years < now()`.

   Cambiar un plazo exige un PR a los values y una migración, igual que hoy. Además queda trazado en `case-db`. (Recomendado)

B) El trigger solo comprueba el rol y el estado de origen, y la fecha la garantiza el job con sus pruebas (PBT-U8-08)

C) Plazos fijos dentro de la función del trigger, duplicados en los values del job, con una prueba de CI que verifica que coinciden

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Umbrales operativos (Performance / Scalability; NFR-U8-03, 12, 20 y FD)
Pendientes del §7: la alarma de indisponibilidad de la API, la cola atrasada, los fallos al
primer intento y `ScoringRequestRejected`.

A) **Esta tabla**, con las métricas agregadas con `max()` entre réplicas cuando son gauges calculados por cada pod:

   | Alerta | Condición | Severidad |
   |---|---|---|
   | `CaseApiUnavailable` | Sin réplicas `Ready` de `case-service` (`up` = 0) durante 2 min, **o** > 5 % de respuestas 5xx (sin contar los 503 de `pendiente_registro`) durante 5 min | SEV2 |
   | `CaseJobsOverdue` | `vectra_case_jobs_overdue` > 0 durante 5 min (trabajos vencidos hace > 30 s sin tomar) | SEV2 |
   | `CaseFirstAttemptFailureHigh` | `vectra_case_first_attempt_failure_ratio` > 0,10 durante 15 min, con ≥ 20 casos en la ventana | SEV3 |
   | `ScoringRequestRejected` | `increase(vectra_case_attempts_total{result="scoring_rejected"}[5m])` > 0 | SEV2 |

   SEV2 para la API porque es criticidad High aunque esté fuera del SLO (NFR-U8-20); SEV3 para los fallos al primer intento porque esos casos se recuperan con el backoff y, si no, ya dispara `FailClosedPersistente`. (Recomendado)

B) Lo mismo, pero `CaseApiUnavailable` como SEV1, igual que la ruta de recomendación

C) Lo mismo, pero `CaseFirstAttemptFailureHigh` como SEV2 con un umbral de 0,05

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Severidad de las alertas de seguridad y de retención (Security; NFR-U8-45, 46)
> **Superado** (anotado el 2026-10-08): «en producción el core es el del banco» lo reemplaza la aclaración Q1 = A del Infrastructure Design (core deshabilitado en producción, INF-U8-02), y la expresión de `CoreWriteAttempt` con una sola serie la reemplaza INF-U8-03 (dos series; la de Linkerd con resta contra `offset 5m`). Los documentos de diseño vigentes son P-U8-06, INF-U8-02 e INF-U8-03.

`core-banking-mock` solo existe fuera de producción: en producción el core es el del banco,
con sus propios controles.

A) **Esta tabla**:

   | Alerta | Condición | Severidad |
   |---|---|---|
   | `CoreWriteAttempt` | `increase(vectra_core_write_attempts_total[5m])` > 0 | SEV2 (en la demostración es la evidencia esperada de RT-5; el runbook lo dice) |
   | `CaseRetentionMissing` | Última corrida exitosa hace más de 2 días | SEV2 |
   | `CaseRetentionOverdue` | Dos corridas exitosas consecutivas con `overdue_remaining > 0` | SEV2 |

   `CaseRetentionOverdue` es SEV2 y no SEV1: los identificadores siguen cifrados y con acceso restringido, y hay 1 h para responder. (Recomendado)

B) `CoreWriteAttempt` y `CaseRetentionOverdue` como SEV1: el primero es un intento de violar RT-5 y el segundo, un incumplimiento de la Ley 1581

C) Lo mismo que A, pero `CaseRetentionMissing` como SEV3

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Escenarios de resiliencia de U8 (Resilience; P-U0-08, decisión C)
Se documentan aquí y se ejecutan en Operations.

A) **Estos seis**:

   | Escenario | Resultado esperado |
   |---|---|
   | scoring caído | Casos en `en_sincronizacion`; circuito abierto tras 20 llamadas; `no_disponible` a los ~15,5 min; `FailClosedPersistente` |
   | explainability caído (P-U0-08) | `FailClosed(explainer_unavailable)`; el caso sigue el backoff y queda `no_disponible` al agotar los intentos |
   | Registro caído durante una decisión | 503; decisión `pendiente_registro`; `CaseEvidencePending` a los 30 min; el reconciliador confirma al volver el registro y el caso pasa a `decidido` |
   | Failover de `case-db` | 503 en las escrituras durante el failover; ningún caso duplicado al reintentar el canal con la misma `Idempotency-Key` |
   | Un pod de `case-worker` muere a mitad de una llamada | El trabajo se retoma al vencer `locked_until` (≤ 30 s); el resultado del intento anterior, si llega, se descarta por `attempt` (BR-U8-08) |
   | Core caído | `get_case` responde con `credit_status = no_disponible` dentro de su p99 |

   (Recomendado)

B) Solo los dos escenarios mínimos de P-U0-08 que tocan a U8 (explainability caído y registro caído)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Aislamiento de conexiones por dependencia (Performance / Logical Components, bulkhead)
Como en U7 (Q4): un worker con 16 trabajos en vuelo no debe agotar las conexiones que
necesita para leer `serving-config`.

A) **Un cliente `httpx` por dependencia** en cada pod, con su propio límite. Esperar una conexión libre cuenta dentro del timeout de la llamada:

   | Proceso | Dependencia | Conexiones máx. |
   |---|---|---|
   | `case-worker` | scoring | 16 (= trabajos en vuelo) |
   | `case-worker` | governance (`serving-config` y `feature_spec`) | 4 |
   | `case-service` | registro (decisión, reconciliador) | 10 |
   | `case-service` | governance (barrido de BR-U8-10/14) | 2 |
   | `case-service` | core | 10 |

   (Recomendado)

B) Un solo cliente compartido por proceso

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/case-management/nfr-requirements/` (NFR-U8-01..53) y los pendientes del FD
- [x] 2. Recoger y validar las respuestas (Q1–Q6 = A)
- [x] 3. Generar `construction/case-management/nfr-design/nfr-design-patterns.md`
- [x] 4. Generar `construction/case-management/nfr-design/logical-components.md` (diagrama validado)
- [x] 5. Aplicar y registrar los cambios a artefactos aprobados (FD de U8 BR-U8-20, §8 y domain-entities §1.5; NFR-U8-46(f) y §7; `component-dependency.md` §4; P-U0-08). U1 P-U1-10 sin cambios: las severidades nuevas siguen su tabla
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
