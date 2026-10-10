# Plan de NFR Design — U10 `console`

**Alcance:** convertir NFR-U10-01..64 en patrones y componentes lógicos, y fijar lo que el
NFR dejó para esta etapa (§8 de `nfr-requirements.md`): timeouts y límites de conexiones por
destino, alertas, perfil de carga y perfil de red.

**Ya decidido** (no se pregunta):
- el Functional Design (BR-U10-01..19) y el NFR Requirements (NFR-U10-01..64);
- BFF sin estado, en `vectra-high`, con HPA de 2 a 6; SPA estática en `vectra-normal`, 2 réplicas;
- un circuit breaker por destino con los umbrales de U7; sin reintentos en el BFF;
- tokens solo en memoria; el BFF reenvía el token del usuario en `Authorization`. Como no hay cookies de sesión, no hay superficie de CSRF (el `state` del step-up y el `Origin` del `postMessage` ya están en BR-U10-06);
- severidades del proyecto (P-U1-10): SEV1 → 15 min, SEV2 → 1 h, SEV3 → siguiente día hábil, todas con `runbook_url`.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q1, Q3, Q5 |
| Scalability Patterns | Q1 (límites de conexiones con 6 réplicas); el resto ya está en NFR-U10-10..12 |
| Performance Patterns | Q2, Q6, Q7 |
| Security Patterns | Sin preguntas nuevas: NFR-U10-40..46 ya fijan la CSP, Trusted Types, la inactividad, la cadena de suministro y la autorización. Q5 cubre el sesgo de versión, que también es un tema de integridad del código servido |
| Logical Components | Q3, Q7 |
| Observabilidad | Q4 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Timeouts y límites de conexiones por destino (Resilience / Scalability; NFR-U10-11, 31)
Cada timeout es el p99 declarado del destino (o 2 × su p95 si no declara p99) más un margen, y
siempre menor que los 10 s de la SPA.

A)
   | Destino (operaciones) | Objetivo declarado | Timeout del BFF | Conexiones por réplica del BFF |
   |---|---|---|---|
   | case: `list_cases`, `get_case`, `list_persistent_failures` | p95 ≤ 300 ms; `get_case` p99 ≤ 800 ms (NFR-U8-01) | 1,5 s | 20 |
   | case: `record_decision`, `create_manual_application`, `record_explanation_view`, `retry_case` | p95 ≤ 300 ms (con el append síncrono) | 3 s | (las mismas 20) |
   | governance: lecturas | p95 ≤ 500 ms (supuesto: no declarado) | 1,5 s | 10 |
   | governance: transiciones con firma | p95 ≤ 500 ms (NFR-U4-11) | 3 s | (las mismas 10) |
   | registry: `get_case_dossier` | p95 ≤ 2 s (NFR-U3-21) | 5 s | 5 |
   | registry: `verify_chain` (inicio, ver Q3) | — | 3 s | (las mismas 5) |
   | explainability: `applicant_summary` | p95 ≤ 500 ms (NFR-U7-03) | 2 s | 5 |
   | bias: `get_dashboard` | sin caché p95 ≤ 2 s (NFR-U9-02) | 5 s | 5 |
   | bias: `list_freezes`, `get_context_package` | p95 ≤ 500 ms | 1,5 s | (las mismas 5) |

   - Con 6 réplicas: 120 conexiones hacia case y 60 hacia governance; NFR Design de U8 y U4 lo confirman contra sus pools.
   - `x-vectra-deadline` = el momento de entrada + 9 s, así que ninguna cadena supera el timeout de la SPA.
   - Un timeout de un `POST` (decisión, aprobación) devuelve 503 `dependency_unavailable` y el mensaje «no se sabe si quedó registrada; recarga el caso». El estado real lo muestra la recarga (la idempotencia de U8 y de U4 evita el doble registro).

   (Recomendado)

B) Un solo timeout de 5 s para todos los destinos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Objetivo de `get_dossier` (Performance; NFR-U10-02)
NFR-U10-02 fijó `get_dossier` en p95 ≤ 1 s, pero el registro declara su expediente en
p95 ≤ 2 s (NFR-U3-21, que incluye la verificación `range`). El objetivo de U10 no se puede
cumplir.

A) **Alinear**: `get_dossier` p95 ≤ el del registro + 30 ms (≈ 2,03 s); case-service va en paralelo y no suma. Se corrige NFR-U10-02. La SPA muestra un indicador de carga desde los 300 ms. (Recomendado)

B) Mantener 1 s y pedir a U3 un expediente más rápido (por ejemplo, la verificación `range` aparte y bajo demanda)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Verificación de integridad bajo demanda (Resilience / Logical Components)
`run_integrity_check` (C03) llama a `verify_chain`, y una verificación `full` puede tardar
horas (`registry-verify-full`: 21 600 s). Una respuesta síncrona no cabe en los 10 s de la SPA.

A) **Asíncrona, con consulta del estado**:
   - `POST /api/console/integrity-checks` → registry `POST /v1/integrity-checks` responde **202** con `{check_id, mode, started_at}`; una sola `full` a la vez (409, ya en el plan de U3);
   - nuevo endpoint 29 de C03: `get_integrity_check(check_id)` (`GET /api/console/integrity-checks/{id}`, `cro`, sin MFA) → registry `GET /v1/integrity-checks/{id}` con `{status: en_curso | verified | not_verified | fallida, progress, report?}`;
   - la corre el propio `decision-registry-service` en una tarea en segundo plano sobre la réplica, con su propio pool y prioridad baja, y guarda el resultado en una tabla `integrity_checks`. No lanza un Job: el servicio no tiene permiso para crear Jobs (AUTONOMIA-01, K-bindings de U1). Si el pod se reinicia, la verificación queda `fallida` y el CRO la relanza;
   - la SPA consulta cada 30 s mientras la vista esté abierta;
   - se registran los cambios a U3 (endpoint, tabla y tarea) y a C03.

   (Recomendado)

B) Limitar la verificación bajo demanda al modo `range` del último mes (síncrona, ≤ 10 s), y dejar la `full` solo en el CronJob mensual

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Alertas del BFF (Observabilidad; NFR-U10-21, 34)

A)
   | Alerta | Expresión | `for` | Severidad |
   |---|---|---|---|
   | `ConsoleBffErrorBudgetFastBurn` | razón de 5xx propios (sin `dependency_unavailable`) > 14,4 × (1 − 0,995) en 1 h **y** en 5 min | 2 min | SEV2 |
   | `ConsoleBffErrorBudgetSlowBurn` | > 6 × (1 − 0,995) en 6 h **y** en 30 min | 15 min | SEV3 |
   | `ConsoleBffDown` | `absent(up{job="console-bff"} == 1)` o 0 réplicas listas | 5 min | SEV2 |
   | `ConsoleDependencyCircuitOpen` | `max by (dependency) (vectra_circuit_state{service="console-bff"}) == 2` (abierto) | 5 min | SEV3 (el destino tiene su propia alerta) |
   | `ConsoleClientErrorsSpike` | `sum(rate(vectra_console_client_errors_total[15m])) * 60 > 1` (más de 1 error por minuto) **o** cualquier `chunk_load_failed` o `csp_violation` en 15 min | 15 min | SEV3 |
   | `ConsoleAuthzDeniedBurst` | ya existe en U2 (`AuthDeniedBurst`); el BFF solo aporta la métrica | — | — |

   Las tasas de *burn* son las del libro de SRE de Google para un SLO de 99,5 % a 30 días. (Recomendado)

B) Solo `ConsoleBffDown` y la alerta de errores del navegador

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Sesgo de versión en un despliegue (Resilience)
Con recursos con hash, una pestaña abierta antes del despliegue pide un fragmento que la imagen
nueva ya no tiene (`chunk_load_failed`), justo cuando el usuario puede estar escribiendo una
justificación.

A) **Dos versiones de recursos y aviso sin recarga forzada**:
   - la imagen de la SPA incluye los recursos con hash de la versión **anterior** además de los nuevos (el build los copia de la imagen previa por digest), así que una pestaña vieja sigue cargando sus fragmentos durante una versión;
   - `version.json` (sin caché) con la versión desplegada; la SPA lo consulta cada 5 min y, si cambió, muestra un aviso no bloqueante «hay una versión nueva; recarga cuando termines»;
   - si aun así falla un fragmento, el error se reporta (`chunk_load_failed`) y la SPA muestra el mensaje con un botón de recarga, sin recargar sola;
   - la API es compatible hacia atrás durante una versión (BR-U0-91 ya exige subir la mayor ante un cambio incompatible).

   (Recomendado)

B) Recarga automática al detectar una versión nueva

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Perfiles de carga y de red (Performance; NFR-U10-01, 04)

A)
   - **k6, 200 usuarios concurrentes en 30 min**: 150 analistas (bandeja cada 15 s, 1 detalle por minuto, 1 consulta de la explicación y 1 decisión cada 5 min), 20 CRO (bandeja, fallos persistentes y expediente cada 10 min), 15 de cumplimiento (dashboard de sesgo y congelamientos cada 5 min), 15 ingenieros de riesgo (modelos y fuentes cada 5 min). Con tokens reales de Keycloak de kind.
   - **Lighthouse CI**: perfil de red del banco de 20 Mbit/s de bajada, 5 Mbit/s de subida y 40 ms de RTT, CPU sin ralentizar (equipos de escritorio corporativos), caché fría.

   (Recomendado)

B) Solo la mezcla por defecto de k6, sin perfil por rol

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Caché en el BFF para `get_disparity` (Performance / Logical Components)
`get_disparity` llama a governance (`list_models(state=activo,congelado)`) antes de bias en
cada consulta.

A) **Sin caché en el BFF**: governance responde en p95 ≤ 500 ms, la consulta es poco frecuente (15 usuarios de cumplimiento y 20 de CRO) y una caché haría que, tras un congelamiento, el dashboard mostrara la versión anterior unos segundos. Bias ya tiene su caché de 15 min (P-U9-03). El BFF sigue sin estado. (Recomendado)

B) Caché de 30 s por réplica para la versión servible

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-design-patterns.md` (P-U10-xx): autorización en tres pasos, composición, aislamiento por destino, timeouts y presupuesto, step-up y sesión, CSP y Trusted Types, sesgo de versión, telemetría del navegador, alertas, escenarios de falla
- [x] `logical-components.md`: módulos del BFF y de la SPA, clientes por destino, imagen estática
- [x] Cambios a otras unidades (U3 y C03 según Q3; NFR-U10-02 según Q2) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
