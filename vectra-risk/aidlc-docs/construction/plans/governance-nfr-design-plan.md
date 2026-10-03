# Plan de NFR Design — U4 `governance`

**Alcance:** convertir NFR-U4-01..41 en patrones y componentes lógicos. Lo principal:
- cómo convergen las réplicas en ≤ 1 s (NFR-U4-05);
- dónde corre el reconciliador de BR-U4-17;
- cómo se siguen los Jobs de validación;
- en qué zona horaria se evalúan las vigencias normativas;
- si la base agrega una barrera propia contra la reactivación indebida.

**Ya decidido** (no se pregunta): el Functional Design (BR-U4-01..17, con BR-U4-14 en ≤ 6 s),
el stack de `tech-stack-decisions.md`, la plataforma de U1 y RESILIENCY-14 = C.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q2, Q3 |
| Scalability Patterns | **Sin preguntas nuevas**: HPA y réplicas ya están en NFR-U4-03; `serving-config` se sirve desde memoria (NFR-U4-04) |
| Performance Patterns | Q1 |
| Security Patterns | Q5 |
| Logical Components | Q2, Q3, Q4 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Mecanismo de convergencia entre réplicas (Resilience / Performance, NFR-U4-05)

A) **`LISTEN/NOTIFY` de PostgreSQL + sondeo de respaldo**:
   - al confirmar una transición, la misma transacción ejecuta `NOTIFY serving_config, '<etag>'`;
   - cada réplica mantiene una conexión `LISTEN` y recalcula su copia al recibir la notificación;
   - como `NOTIFY` se pierde si la conexión se cae, cada réplica además consulta el `etag` de la base **cada 1 s** y recalcula si cambió;
   - al arrancar, la réplica carga su copia **antes** de declararse lista.

   (Recomendado: convergencia casi inmediata, y el sondeo garantiza el límite de 1 s aunque falle la notificación)

B) Solo sondeo cada 500 ms

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Dónde corre el reconciliador de transiciones pendientes (Resilience, BR-U4-17)

A) **Tarea de fondo en cada réplica**, sin elección de líder: cada 10 s toma las transiciones `pendiente_registro` con `SELECT ... FOR UPDATE SKIP LOCKED` (dos réplicas nunca procesan la misma) y reintenta el append con su `idempotency_key`. Las que pasan 24 h pendientes se marcan `abandonada` y alertan. Lo mismo vale para los eventos `freeze` pendientes (`FreezeEventPending`) (recomendado)

B) CronJob separado cada minuto

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Seguimiento de los Jobs de validación (Resilience / Logical Components, K01)

A) **Sin watch**: governance crea el Job (K01) y espera el informe por F32. Un barrido cada minuto (la misma tarea de fondo de la Q2) marca `validacion_fallida` por `timeout` las corridas con `deadline_at` vencido; antes consulta el estado del Job (`get`) para registrar el motivo (`failed`, `deadline`, `sin informe`). Los Jobs tienen `ttlSecondsAfterFinished: 86400`. Los logs (`pods/log`) se leen solo bajo demanda del ingeniero (recomendado: menos conexiones largas a la API de Kubernetes)

B) Un watch permanente sobre los Jobs de `vectra-staging`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Zona horaria de las vigencias normativas (Logical Components, BR-U4-11)
`normative_at(policy, hoy)` depende de qué es «hoy». Las certificaciones de la
Superintendencia rigen por fechas calendario de Colombia.

A) **`America/Bogota`** para todas las fechas de vigencia y para «hoy». Cada réplica recalcula `normative_current` en cada transición **y** a las 00:00:00 de Bogotá; el sondeo de la Q1 cubre el cambio de día aunque falle el temporizador. Las alertas `NormativeParamsExpiring` usan la misma zona. Los timestamps del registro siguen en UTC (recomendado)

B) UTC para todo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Barrera en la base contra la reactivación indebida (Security, AUTONOMIA-04)
Hoy la reactivación está protegida por el endpoint (rol, MFA, step-up), por `model_fsm` y por
el script de CI (BR-U4-03). Un error de código en otra ruta que escriba directamente en la
tabla esquivaría `model_fsm`.

A) **Trigger en `governance-db`** que rechaza cualquier `UPDATE` de `state` de `congelado` a `activo` salvo que la transacción haya fijado `SET LOCAL vectra.frozen_resolution = '<transition_id>'`, lo que solo hace el handler de `frozen-resolution` después de autorizar. Otro trigger rechaza cualquier cambio a `congelado` cuyo `transition_id` no corresponda a una transición de `freeze`. Con esto la base es una cuarta barrera (recomendado)

B) Mantener solo las barreras de la aplicación y del CI

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/governance/nfr-requirements/` (NFR-U4-01..41, stack)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/governance/nfr-design/nfr-design-patterns.md`
- [x] 4. Generar `construction/governance/nfr-design/logical-components.md` (diagrama validado)
- [x] 5. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
