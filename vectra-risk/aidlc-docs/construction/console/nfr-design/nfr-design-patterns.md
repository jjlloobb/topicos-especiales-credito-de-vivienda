# Patrones de NFR Design — U10 `console`

Decisiones del plan (`console-nfr-design-plan.md`, Q1–Q7 = A). Los IDs `P-U10-xx` se
referencian en el Infrastructure Design y en el plan de tareas.

---

## 1. Autorización y composición

### P-U10-01 — Tres controles por ruta en el registro de contratos (BR-U10-01; NFR-U10-46)
- Cada uno de los **29** endpoints de C03 es un `RouteContract` de U0 con `required_roles`, `mfa_max_age` (900 s cuando la columna «MFA» lo pide) y una `object_rule`.
- El orden fijo es el middleware de U0 (rol → MFA) y después la regla de objeto. La regla de objeto es una función pura que recibe el estado que devolvió el destino, por ejemplo el caso, y responde aceptar, 403 o 409.
- Cuando la regla depende del estado del objeto, el BFF lee el objeto y aplica la regla antes de reenviar la acción. Por ejemplo, `record_decision` lee el caso y exige `listo`. El destino vuelve a validar igual (defensa en profundidad), así que una carrera entre la lectura y la acción la resuelve el destino con su 409.
- Un `RouteContract` sin `object_rule` explícita (`None` declarado) no arranca: deny by default, como BR-U0-71.
- La matriz rol × endpoint (BR-U10-19) se genera desde el registro.
- **Verificación**: PBT-U10-01 y PBT-U10-02; prueba de arranque con una ruta sin `object_rule` → error.
- **Satisface**: NFR-U10-46; SECURITY-08.

### P-U10-02 — Composición (BR-U10-03; NFR-U10-02)
- `get_dossier`:
  - llama a registry y a case **en paralelo** con `asyncio.TaskGroup`, cada una con su timeout (P-U10-04);
  - si el registro falla → 503 y se cancela la otra llamada;
  - si case falla → expediente sin identificadores, con `identifiers_unavailable = true`.
- **Objetivo corregido** (Q2): `get_dossier` p95 ≤ el del registro (NFR-U3-21: 2 s) + 30 ms. La llamada a case va en paralelo y no suma. NFR-U10-02 decía 1 s. La SPA muestra un indicador de carga desde los 300 ms.
- `get_disparity`: governance (`list_models(state=activo,congelado)`) y después bias, en serie. **Sin caché en el BFF** (Q7): tras un congelamiento, el dashboard nunca muestra la versión anterior. Bias ya tiene su caché de 15 min (P-U9-03).
- **Verificación**: prueba con dobles de 500 ms en las dos ramas de `get_dossier` → < 700 ms; registro caído → 503 y la llamada a case cancelada; prueba de carga en kind.
- **Satisface**: NFR-U10-02; RESILIENCY-10.

## 2. Resiliencia

### P-U10-03 — Aislamiento por destino (NFR-U10-30, 32, 33)
- Un cliente de `deps.call` por destino (case, governance, registry, explainability, bias), cada uno con su circuit breaker: ≥ 50 % de fallos en 20 llamadas dentro de 30 s, semiabierto a los 10 s. Fallo = timeout, conexión o 5xx; un 4xx no cuenta.
- Con un circuito abierto, solo los endpoints de ese destino responden 503 `dependency_unavailable`, de inmediato.
- Sin reintentos en el BFF.
- **Timeout de un `POST`** (decisión, aprobación, alta): 503 `dependency_unavailable` con el mensaje del catálogo «no se sabe si quedó registrada; recarga el caso». La recarga muestra el estado real. El doble registro lo evitan la `Idempotency-Key` del alta (U8 BR-U8-02), la decisión única por caso (U8 BR-U8-18) y las transiciones de U4 (BR-U4-17).
- **Verificación**: prueba con cada destino caído por turno: sus vistas dan 503 y las demás 2xx; con el circuito abierto, el doble cuenta 0 llamadas; un 503 de un `POST` → una sola llamada.
- **Satisface**: NFR-U10-30, 32, 33; RESILIENCY-10.

### P-U10-04 — Timeouts, presupuesto y conexiones (Q1; NFR-U10-11, 31)

| Destino (operaciones) | Objetivo declarado | Timeout del BFF | Conexiones por réplica |
|---|---|---|---|
| case: `list_cases`, `get_case`, `list_persistent_failures` | p95 ≤ 300 ms; `get_case` p99 ≤ 800 ms (NFR-U8-01) | 1,5 s | 20 (compartidas) |
| case: `record_decision`, `create_manual_application`, `record_explanation_view`, `retry_case` | p95 ≤ 300 ms, con el append síncrono; peor caso ≈ 2,5 s (timeout de case hacia el registro, P-U8 F16) + la base | **4 s** (antes 3 s, menor que el peor caso de U8; revisión del Infrastructure Design de U10, 2026-10-10) | (las mismas 20) |
| governance: lecturas | p95 ≤ 300 ms (NFR-U4-13, declarado por U4 en la revisión del Infrastructure Design de U10, 2026-10-10) | 1,5 s | 10 (compartidas) |
| governance: transiciones con firma | p95 ≤ 500 ms (NFR-U4-11), con el append síncrono al registro (2,5 s de timeout) | **4 s** (revisión del Infrastructure Design de U10, 2026-10-10) | (las mismas 10) |
| registry: `get_case_dossier` | p95 ≤ 2 s (NFR-U3-21) | 5 s | 5 (compartidas) |
| registry: `run_integrity_check`, `get_integrity_check` (P-U10-05) | — (solo registran o leen una fila) | 3 s | (las mismas 5) |
| explainability: `applicant_summary` | p95 ≤ 500 ms (NFR-U7-03) | 2 s | 5 |
| bias: `get_dashboard` | sin caché p95 ≤ 2 s (NFR-U9-02) | 5 s | 5 (compartidas) |
| bias: `list_freezes`, `get_context_package` | p95 ≤ 500 ms (NFR-U9-02) | 1,5 s | (las mismas 5) |

- **Dónde viven**: los timeouts, el presupuesto y los límites de conexiones son constantes del código (`console_bff/config.py`), no values; una prueba los compara con esta tabla (segunda revisión del Infrastructure Design de U10, 2026-10-10).
- **Presupuesto**: `x-vectra-deadline` = el momento de entrada al BFF + 9 s; el timeout efectivo de cada llamada es `min(timeout, deadline − ahora)` (U0 NFR-U0-23 (b)). Ninguna cadena supera los 10 s de la SPA.
- **Conexiones con 6 réplicas**: 120 hacia case, 60 hacia governance y 30 hacia cada uno de los demás. U3, U4, U7, U8 y U9 confirman en sus planes de tareas que sus servicios admiten esas conexiones (pendiente registrado en §7; revisión del Infrastructure Design de U10, 2026-10-10).
- **Verificación**: pruebas con dobles lentos: cada llamada corta en su timeout; la cabecera llega al doble con el plazo correcto; un pool agotado termina en timeout dentro del plazo.
- **Satisface**: NFR-U10-11, 31; RESILIENCY-10.

### P-U10-05 — Verificación de integridad asíncrona (Q3; rediseñada en la revisión del Infrastructure Design de U10, 2026-10-10)
- `run_integrity_check(req: IntegrityCheckRequest)` (`POST /api/console/integrity-checks`, `cro` con MFA; `mode: full | range`) → registry `POST /v1/integrity-checks`, que **solo registra** la solicitud:
  - sin otra verificación activa → **202** con `IntegrityCheckRef`;
  - con una activa de cualquier modo → **200** con el `IntegrityCheckRef` de esa y `already_active = true`. La SPA muestra «ya hay una verificación en curso» y sigue esa.
- La ejecuta el CronJob `registry-verify-ondemand` de U3 (cada minuto), con la identidad de verificación, que sí lee la llave pública y el bucket WORM: aplica BR-U3-12 completa, incluidos los pasos 5 y 6. Ni el servicio del registro ni el BFF verifican, así que no hay conexión extra ni excepción a P-U1-08.
- `get_integrity_check(check_id)` (`GET /api/console/integrity-checks/{id}`, `cro`) → `IntegrityCheckStatus` (`pendiente | en_curso | terminada | fallida`). La SPA consulta cada 30 s mientras la vista está abierta.
- Si el pod del CronJob muere, la corrida siguiente marca la fila `fallida` con `interrumpida` en ≤ 3 min y el cupo queda libre (U3 BR-U3-13b).
- **Verificación**: en U3 (plan, Pasos 8 y 12): 202 o 200 con la activa; matar el pod → `fallida`. En U10: la vista con dobles de cada estado y de `already_active`.
- **Satisface**: NFR-U10-31 (nada síncrono supera el plazo); US-402.

### P-U10-06 — Sesgo de versión en un despliegue (Q5)
- La imagen de la SPA incluye los recursos con hash de la versión **anterior** además de los nuevos. El build los copia de la imagen que **está en producción** (su digest se lee de los values de producción en GitOps; INF-U10-02), así que una pestaña abierta antes del despliegue sigue cargando sus fragmentos, también si se saltó un release. Un rollback se hace como release nuevo, y el gateway mantiene cada pestaña en el mismo pod durante el rollout (afinidad por cookie; revisión del Infrastructure Design de U10, 2026-10-10).
- `version.json` (`no-store`) lleva la versión desplegada. La SPA lo consulta cada 5 min y, si cambió, muestra un aviso no bloqueante: «hay una versión nueva; recarga cuando termines».
- Si un fragmento falla de todos modos, se reporta `chunk_load_failed` y aparece el mensaje con un botón de recarga. La SPA nunca recarga sola, para no perder un formulario.
- La API es compatible hacia atrás durante una versión (BR-U0-91).
- **Verificación**:
  - prueba sobre la imagen: contiene los recursos de las dos versiones;
  - Playwright: pestaña de la versión N, despliegue de N+1, navegación a una ruta no cargada → carga sin error y aparece el aviso; con los recursos de N borrados → mensaje con botón y el formulario intacto.
- **Satisface**: RESILIENCY-04; NFR-U10-34.

## 3. Sesión y seguridad del navegador

### P-U10-07 — Sesión en memoria, step-up e inactividad (BR-U10-05, 06; NFR-U10-40, 41)
- `oidc-client-ts`: `UserManager` con `InMemoryWebStorage` para el login, el refresco y el estado de usuario.
- **Step-up con la API de bajo nivel** (segunda revisión del Infrastructure Design de U10, 2026-10-10): `signinPopup` abre la ventana por su cuenta (no siempre dentro del clic) y procesa la respuesta en la ventana emergente, lo que contradice BR-U10-06. Por eso el módulo `stepup` usa `OidcClient` directamente:
  1. en el manejador del clic, `OidcClient.createSigninRequest({prompt: "login", max_age: 0, acr_values: "mfa", redirect_uri: "/stepup-callback"})` genera la URL con `state`, `nonce` y PKCE en un `stateStore` en memoria, y `window.open(url)` se llama de forma síncrona;
  2. `/stepup-callback` solo hace `postMessage({code, state}, location.origin)` y se cierra;
  3. la ventana principal valida origen, ventana y `state`, arma la URL de respuesta y llama a `OidcClient.processSigninResponse(url)`, que canjea el código y valida el `nonce`; después comprueba `acr = mfa` y entrega los tokens nuevos al `UserManager`.
- **Prueba de concepto obligatoria** antes de construir las vistas (Paso del plan de tareas de U10): Playwright en Chromium y Firefox con Keycloak de kind demuestra el flujo completo, sin nada en `sessionStorage` ni en `localStorage`, y con la ventana bloqueada cuando `window.open` se llama fuera del clic.
- **Inactividad** (BR-U10-20): un temporizador de la **sesión** que reinician `keydown`, `pointerdown`, `focusin`, `wheel` y `scroll` en cualquier pestaña. Cada pestaña difunde `activity` por `BroadcastChannel` como máximo cada 30 s. Las respuestas de TanStack Query no lo tocan. Aviso a los 25 min y logout a los 30 (revisión del Infrastructure Design de U10, 2026-10-10).
- **Logout entre pestañas**: `BroadcastChannel("vectra-console")` con el mensaje `{type: "logout"}`, sin datos. Cada pestaña borra su memoria y llama al `end_session_endpoint`.
- **Verificación**: PBT-U10-05; NFR-U10-40, 41.
- **Satisface**: SECURITY-12.

### P-U10-08 — CSP estricta y Trusted Types (NFR-U10-42, 43)
- CSP del perfil `spa` de U2 con `require-trusted-types-for 'script'; trusted-types 'none'`.
- El build no genera estilos ni scripts en línea: Vite con `build.modulePreload.polyfill = false` y sin `<script>` inline en `index.html`; la configuración (`config.json`) se carga con `fetch`.
- Estilos con CSS Modules; componentes de React Aria; gráficos en SVG de React.
- **Verificación**: Playwright con un listener de `securitypolicyviolation` en todas las vistas → 0 violaciones; prueba de que `index.html` no tiene `<script>` ni `<style>` inline.
- **Satisface**: SECURITY-04.

### P-U10-09 — Telemetría del navegador (NFR-U10-34)
- **SPA**: un reportero único engancha `window.onerror`, `unhandledrejection`, `securitypolicyviolation`, los errores de carga de fragmentos y el `ErrorBoundary`. Cada uno se mapea al catálogo cerrado de `error_code`, con un máximo de 10 por minuto. Usa `fetch` con `keepalive`, y nunca envía mensajes, trazas ni la URL con parámetros (solo la plantilla de la ruta).
- **BFF**: valida `ClientErrorReport` (U0 §9.5, `extra = "forbid"`), emite `console.client_error` y suma `vectra_console_client_errors_total{error_code}`. Responde 204.
- **Contadores creados en 0** (tercera revisión del Infrastructure Design de U10, 2026-10-10): al arrancar, el BFF crea la serie de `vectra_console_client_errors_total` para **cada uno** de los seis `error_code` con valor 0. Sin eso, la serie de un código aparece recién con su primer error, `increase()` no tiene un punto anterior y `ConsoleChunkOrCspError` (sin `for`) no dispara con ese primer error. Prueba: `GET /metrics` recién iniciado muestra las seis series en 0; `promtool test rules` con una serie que pasa de 0 a 1 → la alerta dispara.
- **Verificación**: NFR-U10-34.
- **Satisface**: SECURITY-14, 15.

## 4. Observabilidad

### P-U10-10 — Alertas (Q4; NFR-U10-21, 34)

| Alerta | Expresión | `for` | Severidad |
|---|---|---|---|
| `ConsoleBffErrorBudgetFastBurn` | razón de 5xx propios del BFF (sin `dependency_unavailable`) > 14,4 × 0,005 en 1 h **y** en 5 min | 2 min | SEV2 |
| `ConsoleBffErrorBudgetSlowBurn` | > 6 × 0,005 en 6 h **y** en 30 min | 15 min | SEV3 |
| `ConsoleBffDown` | ninguna réplica de `console-bff` lista (`absent` o 0) | 5 min | SEV2 |
| `ConsoleDependencyCircuitOpen` | `max by (dependency) (vectra_circuit_state{service="console-bff"}) == 2` (2 = abierto; codificación de U0 NFR-U0-23 (g)) | 5 min | SEV3 (el destino tiene su propia alerta) |
| `ConsoleClientErrorsSpike` | `sum(rate(vectra_console_client_errors_total[15m])) * 60 > 1` | 15 min | SEV3 |
| `ConsoleChunkOrCspError` | `sum(increase(vectra_console_client_errors_total{error_code=~"chunk_load_failed|csp_violation"}[15m])) > 0` | 0 (un solo error dispara; antes estaba dentro de la alerta anterior con `for: 15m` y nunca disparaba; revisión del Infrastructure Design de U10, 2026-10-10) | SEV3 |

- Los fallos de autorización los cubre `AuthDeniedBurst` de U2 con la métrica de BR-U0-73.
- Recording rules para la razón de errores en 5 min, 30 min, 1 h y 6 h.
- Cada regla lleva `severity` y `runbook_url` (P-U1-10). Runbooks: `console-bff-error-budget` (las dos de *burn rate*), `console-bff-down`, `console-dependency-circuit-open` y `console-client-errors-spike` (`ConsoleClientErrorsSpike` y `ConsoleChunkOrCspError`) (tercera revisión del Infrastructure Design de U10, 2026-10-10).
- **Verificación**: `promtool test rules` con series a los dos lados de cada umbral; un 503 `dependency_unavailable` no cuenta para el presupuesto; test de runbooks de U1.
- **Satisface**: NFR-U10-21, 34; RESILIENCY-05, 07, 15.

### P-U10-11 — Medición del rendimiento (Q6; NFR-U10-01, 03, 04)
- **k6** (operador en kind): 200 usuarios concurrentes durante 30 min, con tokens reales de Keycloak:
  - 150 analistas: bandeja cada 15 s, 1 detalle por minuto, y 1 consulta de la explicación y 1 decisión cada 5 min;
  - 20 de CRO: bandeja, fallos persistentes y expediente cada 10 min;
  - 15 de cumplimiento: dashboard de sesgo y congelamientos cada 5 min;
  - 15 ingenieros de riesgo: modelos y fuentes cada 5 min.

  Umbrales: los de NFR-U10-01, el NFR-U10-02 corregido y NFR-U10-10.
- **Sobrecosto del BFF**: histograma `vectra_bff_dependency_duration_seconds{dependency, route}` junto al de la ruta, para calcular la diferencia del NFR-U10-01.
- **Lighthouse CI**: red de 20 Mbit/s de bajada, 5 Mbit/s de subida y 40 ms de RTT, CPU sin ralentizar, caché fría; LCP ≤ 2,5 s y CLS ≤ 0,1.
- **`size-limit`** en cada PR.
- **Satisface**: NFR-U10-01..04, 10.

## 5. Escenarios de falla (RESILIENCY-14 = C: se documentan aquí; los de kind los ejecuta el operador y la ejecución a escala queda para Operations)

| # | Escenario | Resultado esperado | Dónde |
|---|---|---|---|
| E1 | case-service caído | Bandeja, detalle y decisión → 503 con mensaje; gobierno y sesgo siguen; expediente sin identificadores | CI (dobles) y kind |
| E2 | Registro caído | Expediente e integridad → 503; las decisiones fallan en U8 (503 con la decisión pendiente, BR-U8-18) | CI y kind |
| E3 | bias caído | Dashboard y congelamientos → 503; bandeja y decisión siguen | CI y kind |
| E4 | Keycloak caído | Sin logins ni refresh; los access tokens vigentes (≤ 5 min) siguen; el step-up falla con «la verificación no se completó» y el formulario queda intacto | kind |
| E5 | Una réplica del BFF muere | La otra sigue; la SPA ve a lo sumo un error en una solicitud en curso | kind |
| E6 | Despliegue de la SPA con pestañas abiertas | P-U10-06: sin `chunk_load_failed` y con el aviso | kind |
| E7 | Pod de `registry-verify-ondemand` muerto durante una verificación `full` | La corrida siguiente la marca `fallida` con `interrumpida` en ≤ 3 min; `RegistryOnDemandCheckFailed`; el CRO la relanza (revisión del Infrastructure Design de U10, 2026-10-10; en el Paso 18 de U3, escenario 9) | kind |

## 6. Cumplimiento de extensiones (NFR Design U10)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-04 | Cumple | P-U10-08 |
| SECURITY-08 | Cumple | P-U10-01 |
| SECURITY-12 | Cumple | P-U10-07 |
| SECURITY-14 / 15 | Cumple | P-U10-03, 09, 10 |
| RESILIENCY-04 | Cumple | P-U10-06 |
| RESILIENCY-05 / 07 / 15 | Cumple | P-U10-10 |
| RESILIENCY-10 | Cumple | P-U10-02, 03, 04 |
| RESILIENCY-14 | Cumple (C: documentados aquí; los de kind los ejecuta el operador tras un PR aprobado y la ejecución a escala queda para Operations, U0 P-U0-08) | §5 |
| AUTONOMIA-01 | Cumple | P-U10-05 (sin Jobs creados por el servicio); mediciones en kind por el operador (P-U10-11) |
| AUTONOMIA-02 | Cumple | Cada patrón tiene su «Verificación» |
| PBT-06 | Cumple | PBT-U10-05 (stateful), en P-U10-07 |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U10 NFR-U10-02 | `get_dossier` p95 ≤ el del registro (2 s) + 30 ms (decía 1 s) | Q2 |
| U3 FD (BR-U3-13..15, domain-entities, business-logic-model), NFR Design, plan (Paso 8) | **Superado** por P-U10-05 rediseñada (revisión del Infrastructure Design de U10): la API solo registra la solicitud y la ejecuta el CronJob `registry-verify-ondemand`. Decía: `POST /v1/integrity-checks` responde 202 con `check_id`; `GET /v1/integrity-checks/{id}`; tabla `integrity_checks`; tarea en segundo plano sobre la réplica con pool de 1; `fallida` con `reason = interrumpida` si el pod termina | Q3 |
| `component-methods.md` C03 y C-registry; `unit-of-work.md` U10; U10 BR-U10-01, 19 y business-logic-model | Endpoint 29 `get_integrity_check`; `run_integrity_check` devuelve `IntegrityCheckRef` | Q3 |
| U0 §9.6 | Tipos `IntegrityCheckRef` e `IntegrityCheckStatus` (forma vigente en U0 §9.6: `already_active`, `pendiente`, motivos de `fallida`; la versión de esta fila fue **superada** en la revisión del Infrastructure Design de U10) | Q3 |
| **Pendiente para U3, U4, U7, U8 y U9** (en sus planes de tareas) | Confirmar que sus servicios admiten las conexiones desde 6 réplicas del BFF: 120 (U8), 60 (U4) y 30 cada uno (U3, U7, U9) (P-U10-04; U3, U7 y U9 agregados en la revisión del Infrastructure Design de U10, 2026-10-10) | Q1 |
| U4 NFR-U4-13 | Lecturas de governance por el BFF (`GET /v1/models`, `/v1/policies`, `/v1/data-sources`): p95 ≤ 300 ms (antes un supuesto de U10) | revisión del Infrastructure Design de U10, 2026-10-10 |
| U0 NFR-U0-23 (g) | Codificación de `vectra_circuit_state`: 0 cerrado, 1 semiabierto, 2 abierto | revisión del Infrastructure Design de U10, 2026-10-10 |
