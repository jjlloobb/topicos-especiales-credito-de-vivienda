# Plan de NFR Requirements — U7 `scoring-explainability`

**Alcance:** requisitos no funcionales y stack de `scoring-service` y `explainability-service`,
sobre el Functional Design aprobado (BR-U7-01..16). Incluye fijar la latencia objetivo de la
recomendación, que NFR-PER-01 dejó **[INTERNO]** «a fijar en NFR Requirements».

**Ya decidido** (no se pregunta):
- Python 3.12 + FastAPI + `vectra_common` (`create_app`, `deps.call` con timeout obligatorio), Hypothesis (U0);
- presupuestos de las dependencias: `:predict` p95 ≤ 30 ms, `:explain` p95 ≤ 150 ms (U6); append p95 ≤ 50 ms (U3); `serving-config` p95 ≤ 20 ms con caché ≤ 5 s (U4);
- pico de diseño de 10 solicitudes/s y prueba a 20/s (U1); criticidad High (U1);
- sin egress (X02) ni acceso al core (X01); readiness según P-U1-04 (ningún servicio de U7 tiene dependencias propias de datos).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Latencia objetivo de la recomendación (Performance, NFR-PER-01)
Suma de los presupuestos de las dependencias: ~30 + 150 + 50 + overhead ≈ 260 ms en el p95.

A)
   - `POST /v1/recommendations` (de punta a punta en scoring): **p95 ≤ 400 ms** y **p99 ≤ 1 s** a 10 solicitudes/s.
   - `POST /v1/explanations`: **p95 ≤ 250 ms**.
   - `POST /v1/applicant-summaries`: **p95 ≤ 500 ms**.
   - Una solicitud que se resuelve como `FailClosed` por timeout también responde dentro del p99.

   (Recomendado: muy por debajo del objetivo de originación de < 1 h; el margen absorbe la cola del registro y de KServe)

B) p95 ≤ 1 s y p99 ≤ 3 s

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Timeouts y circuit breakers (Resilience, RESILIENCY-10)

A)
   - **Timeouts por llamada** (con `deps.call`):

     | Llamada | Timeout |
     |---|---|
     | scoring → `serving-config` | 500 ms |
     | scoring → KServe `:predict` | 300 ms |
     | scoring → explainability | 800 ms |
     | explainability → KServe `:explain` | 500 ms |
     | explainability → diccionario (governance) | 500 ms |
     | scoring → registro | 2,5 s (U3) |

   - **Circuit breaker por dependencia**: se abre con ≥ 50 % de fallos en las últimas 20 llamadas dentro de 30 s y pasa a semiabierto a los 10 s. Abierto → fail-closed inmediato con la causa de esa dependencia, sin llamar.
   - **Sin reintentos dentro de scoring**, salvo el del append al registro con la misma `idempotency_key` (BR-U7-15), una vez dentro del presupuesto. Los demás reintentos son del caso (U8).

   (Recomendado)

B) Solo timeouts, sin circuit breakers

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Disponibilidad y escalado (Availability / Scalability)

A) Cada servicio con **≥ 2 réplicas** repartidas por zona, PDB y HPA de 2 a 6 por CPU al 70 %. Readiness solo con el proceso (P-U1-04). explainability carga el diccionario de la versión activa al arrancar si governance responde; si no, lo pide en la primera solicitud (recomendado)

B) Réplicas fijas (2), sin HPA

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Implementación del circuit breaker (Tech Stack)

A) **Implementación propia y mínima en `vectra_common.deps`** (estados cerrado, abierto y semiabierto con ventana deslizante), con una propiedad stateful que prueba sus transiciones. Así todos los servicios comparten la misma semántica y la misma métrica (`vectra_circuit_state{dependency}`) (recomendado: pocas líneas, sin una dependencia de terceros en una pieza de seguridad)

B) Una librería de terceros (p. ej. `aiobreaker`)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Umbral de calidad de pruebas (Maintainability / Testing)
`policy`, `narrative` y `factuality` deciden lo que el comité ve.

A) Cobertura de ramas **≥ 95 %** en los dos servicios y **100 %** en `policy`, `narrative`, `factuality` y `orchestrator`. **Mutation testing** con `mutmut` en `policy` y `factuality`, con 0 sobrevivientes sin justificar. PBT-U7-01..08 con el perfil `ci` (recomendado: el mismo nivel que U0 para su invariante)

B) Cobertura ≥ 85 % sin mutation testing

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U7 y los NFR heredados (NFR-PER-01, NFR-RES-10/11, NFR-SEC)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/scoring-explainability/nfr-requirements/nfr-requirements.md`
- [x] 4. Generar `construction/scoring-explainability/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Si la Q4 agrega algo a `vectra_common`, registrar el cambio en U0
- [x] 6. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
