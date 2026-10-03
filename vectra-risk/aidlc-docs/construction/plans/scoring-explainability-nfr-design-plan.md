# Plan de NFR Design — U7 `scoring-explainability`

**Alcance:** convertir NFR-U7-01..43 en patrones. Al cruzar los timeouts aprobados con los
objetivos de latencia aparecieron **dos inconsistencias** y **un caso límite** que hay que
resolver aquí (Q1–Q3).

**Ya decidido** (no se pregunta): el Functional Design, el circuit breaker de
`vectra_common.deps`, la caché de `serving-config` y del diccionario, el escalado y
RESILIENCY-14 = C.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q2, Q3, Q4 |
| Scalability Patterns | **Sin preguntas nuevas**: HPA y servicios sin estado ya en NFR-U7-20..22 |
| Performance Patterns | Q1, Q2, Q4 |
| Security Patterns | **Sin preguntas nuevas**: sin egress, métricas sin datos del solicitante y plantillas versionadas ya en NFR-U7-30..32 |
| Logical Components | Q3, Q4 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Los timeouts internos de explainability no caben en el de scoring (Resilience / Performance)
**Inconsistencia en NFR-U7-10.** scoring espera a explainability 800 ms. Pero, con la caché
del diccionario fría, explainability hace en serie la llamada al diccionario (500 ms) y la
de `:explain` (500 ms): hasta 1 s, más que los 800 ms que espera scoring.

A) **Presupuesto propagado y llamadas en paralelo**:
   - scoring envía el tiempo restante en una cabecera `x-vectra-deadline` (instante absoluto);
   - explainability lanza **en paralelo** la consulta del diccionario (si no está en caché) y `:explain`, y corta todo al llegar a `min(deadline − 50 ms, 700 ms)`;
   - si vence → 504 → `timeout`.

   Los timeouts individuales de NFR-U7-10 quedan como máximos, nunca por encima del presupuesto propagado (recomendado)

B) Mantenerlas en serie y aceptar `timeout` cuando la caché está fría

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — El timeout del registro supera el p99 de la recomendación (Performance / Resilience)
**Inconsistencia entre NFR-U7-01/04 y U3.** El p99 de la recomendación es de 1 s y un
fail-closed por timeout debe responder dentro de ese p99. Pero el append al registro tiene
hasta 2,5 s (P-U3-02), más un reintento con la misma llave (BR-U7-15).

A) **Mantener el presupuesto del registro y precisar el requisito**:
   - el registro conserva sus 2,5 s, porque recortarlo dejaría más entradas escritas y no entregadas (Q3);
   - NFR-U7-04 se precisa: el fail-closed por timeout o circuito abierto de **KServe, explainability o `serving-config`** responde dentro del p99 (1 s); un registro degradado puede llevar la respuesta hasta ~5 s (2,5 s + reintento) y queda fuera del p99, con su propia alerta (`RegistryAppendSlow`, SEV2, si el p99 del append supera 1 s durante 5 min).

   (Recomendado: la coherencia de la evidencia prevalece sobre la latencia en el caso degradado)

B) Recortar el timeout del cliente del registro al presupuesto restante (≤ 1 s en total)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Entradas `recommendation` escritas pero no entregadas (Logical Components / Business Rules)
**Caso límite.** Si el registro confirma el commit después de que scoring dejó de esperar
(los dos intentos vencidos), queda en el registro una entrada `recommendation` que **no se
entregó**: scoring respondió `FailClosed(registry_unavailable)`. Eso contradice «lo que
queda en el registro es exactamente lo que se entrega» (BR-U0-08) en ese caso extremo.

A) **Hacerlas distinguibles en lugar de imposibles**:
   - case-service guarda en el caso el `registry_entry_id` de la recomendación que **sí** recibió (U8);
   - la entrada `human_decision` lleva un campo nuevo, `recommendation_entry_id`, con la recomendación sobre la que decidió el analista (cambio en el payload de U0);
   - el expediente (U3) marca como «no entregada» toda entrada `recommendation` del caso que no corresponde a la recomendación recibida por el caso.
   - BR-U0-08 se precisa: lo que se **entrega** siempre está en el registro; una entrada puede existir sin haberse entregado, y queda identificada como tal.

   (Recomendado: un protocolo de dos fases distribuido sería mucho más complejo para un caso raro)

B) Aceptar el caso sin marcarlo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Aislamiento de conexiones por dependencia (Resilience / Performance, bulkhead)

A) **Un cliente `httpx` por dependencia** en cada pod, con su propio límite de conexiones:

   | Servicio | Dependencia | Conexiones máx. |
   |---|---|---|
   | scoring | KServe `:predict` | 20 |
   | scoring | explainability | 20 |
   | scoring | registro | 10 |
   | scoring | `serving-config` | 5 |
   | explainability | KServe `:explain` | 20 |
   | explainability | diccionario y registro | 5 cada uno |

   Si una dependencia lenta agota sus conexiones, no afecta a las demás. Esperar una conexión libre cuenta dentro del timeout de la llamada (recomendado)

B) Un solo cliente compartido para todas las dependencias

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/scoring-explainability/nfr-requirements/` (NFR-U7-01..43)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/scoring-explainability/nfr-design/nfr-design-patterns.md`
- [x] 4. Generar `construction/scoring-explainability/nfr-design/logical-components.md` (diagrama validado)
- [x] 5. Aplicar y registrar los cambios a artefactos aprobados (NFR-U7, U0, U3, U8 pendiente) según las respuestas
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
