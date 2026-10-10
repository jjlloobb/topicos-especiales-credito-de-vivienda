# Requisitos no funcionales — U10 `console`

Decisiones del plan (`console-nfr-requirements-plan.md`, Q1–Q14 = A). Las verificaciones
«en kind» las ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las demás corren
en CI.

Los IDs `NFR-U10-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Rendimiento (Q1, Q2; NFR-PER-01)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-01 | **Sobrecosto propio del BFF** (JWT, rol, MFA, regla de objeto y serialización) p95 ≤ 30 ms: la latencia de un endpoint de paso es, como máximo, la del servicio de destino + 30 ms en el p95 | Prueba de carga k6 en kind con un perfil de uso por rol y 200 usuarios concurrentes (NFR-U2-10); comparación entre la métrica del BFF y la del destino para la misma ruta |
| NFR-U10-02 | **Composiciones**: `get_dossier` (registro y case-service **en paralelo**) p95 ≤ el del registro (NFR-U3-21: 2 s) + 30 ms (decía 1 s, que el registro no puede cumplir; corregido en el NFR Design de U10, 2026-10-10, Q2); `get_disparity` (governance y luego bias, **en serie**) p95 ≤ el de bias + 200 ms; `get_me` p95 ≤ 20 ms (sin llamadas a otros servicios) | La misma prueba de carga; prueba de integración que comprueba que las dos llamadas de `get_dossier` salen en paralelo (doble lento de 500 ms en cada una → respuesta < 700 ms) |
| NFR-U10-03 | **JavaScript inicial** ≤ 250 KiB comprimido; las rutas de cada rol se cargan a demanda | Presupuesto en el build (Vite con `size-limit`): CI falla si se supera |
| NFR-U10-04 | **Primera vista útil** (bandeja con datos) p75 ≤ 2,5 s en la red del banco: LCP ≤ 2,5 s y CLS ≤ 0,1. **Detalle de un caso** desde la bandeja p75 ≤ 1 s | Lighthouse CI en kind (operador), con la red limitada al perfil de la red del banco; medición de Playwright del paso bandeja → detalle |

## 2. Escalabilidad (Q3)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-10 | **BFF con HPA de 2 a 6 réplicas por CPU al 70 %**, sin afinidad de sesión (sin estado, BR-U10-02). 200 usuarios concurrentes con el perfil de NFR-U10-01 no superan 2 réplicas al 50 % de CPU | Prueba de carga de NFR-U10-01: réplicas y CPU durante la prueba |
| NFR-U10-11 | Un cliente HTTP por servicio de destino con su límite de conexiones (U0 NFR-U0-23 (d)), dimensionado para que 6 réplicas no saturen a ningún destino (la suma de los límites ≤ la capacidad declarada del destino) | Prueba de unidad sobre la configuración; revisión en NFR Design contra la capacidad de cada destino |
| NFR-U10-12 | La SPA es estática y no escala por carga: 2 réplicas fijas con la exención `vectra.io/hpa-exempt` | `conftest` sobre el chart |

## 3. Disponibilidad (Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-20 | **Criticidad**: BFF **High**, con la PriorityClass `vectra-high`; SPA **Medium**, con `vectra-normal`. Sin el BFF nadie decide ni aprueba | `conftest`: `priorityClassName` por Deployment |
| NFR-U10-21 | **SLO del BFF**: 99,5 % mensual de respuestas sin error propio (sin contar las de `dependency_unavailable` causadas por un destino caído, que cuentan en el SLO de ese destino), en horario operativo | Recording rule de la razón de 5xx propios del BFF; alerta de *burn rate* (se fija en NFR Design) |
| NFR-U10-22 | BFF y SPA con ≥ 2 réplicas en zonas distintas y PDB `minAvailable: 1`. Si la SPA cae, el gateway responde 503 en `/` y la API sigue respondiendo | `conftest` (spread y PDB); simulacro de zona de U1 en kind |

## 4. Fiabilidad y degradación (Q5; RESILIENCY-10)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-30 | **Circuit breaker por destino** (case, governance, registry, explainability, bias) en `deps.call`, con los umbrales de U7: ≥ 50 % de fallos en 20 llamadas dentro de 30 s y semiabierto a los 10 s. Fallo = timeout, conexión o 5xx; un 4xx no cuenta | Pruebas de integración con dobles: el circuito de un destino se abre tras 20 llamadas fallidas y los demás siguen cerrados |
| NFR-U10-31 | **Timeouts hacia cada destino** = p99 declarado del destino + margen, siempre < 10 s (el timeout de la SPA), con `x-vectra-deadline` propagado. Los valores se fijan en NFR Design | Pruebas con dobles lentos: cada llamada corta en su timeout y la cabecera llega al doble |
| NFR-U10-32 | **Aislamiento por vista**: si un destino cae, solo fallan sus vistas, con 503 `dependency_unavailable` y el mensaje del catálogo; las demás siguen. Con bias caído, la bandeja, el detalle y la decisión funcionan | Prueba de extremo a extremo con cada destino detenido por turno (dobles en CI; servicios reales en kind) |
| NFR-U10-33 | **Sin reintentos en el BFF**: ni los `POST` (el usuario ve el error y decide) ni los `GET` (la SPA vuelve a pedir en su siguiente refresco) | Prueba con un doble que cuenta las llamadas: un 503 → exactamente una llamada |
| NFR-U10-34 | **Errores del navegador** (Q12): endpoint `POST /api/console/client-errors` (endpoint 28 de C03; cualquier rol de negocio; sin MFA) con `{error_code, route_template, app_version, correlation_id?}`. `error_code` es un catálogo cerrado (`render_error`, `chunk_load_failed`, `unhandled_rejection`, `api_contract_mismatch`, `stepup_failed`, `csp_violation`); un valor fuera del catálogo → 422. Sin mensajes, trazas, URL completa ni datos de formularios. La SPA envía ≤ 10 por minuto por sesión. El BFF emite el evento `console.client_error` (U0 §8.1) y la métrica `vectra_console_client_errors_total{error_code}`, con las seis series creadas en 0 al arrancar (tercera revisión del Infrastructure Design de U10, 2026-10-10), con una alerta si la tasa sube después de un despliegue (umbral en NFR Design) | PBT-U0-07 en modo strict sobre el evento; prueba de que un cuerpo con campos extra o con un mensaje libre → 422; prueba de la SPA: 20 errores en un minuto → 10 envíos |

## 5. Seguridad (Q6, Q7, Q13; SECURITY-04, 08, 10, 12)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-40 | **Inactividad** de la sesión, compartida entre pestañas: cuentan teclado, puntero, foco, `wheel` y `scroll`; el refresco automático no cuenta. A los 25 min, diálogo «tu sesión se cerrará en 5 min» con «seguir»; a los 30 min, logout (BR-U10-20; antes remitía a BR-U10-05; revisión del Infrastructure Design de U10, 2026-10-10). Un formulario sin enviar no evita el cierre | Pruebas de la SPA con reloj simulado: 24 min → sin aviso; 25 min → aviso; «seguir» → reinicia; 30 min → logout; el refresco de la bandeja no reinicia el contador |
| NFR-U10-41 | **Logout en todas las pestañas**: un logout se propaga por `BroadcastChannel`, sin tokens ni datos en el mensaje | Prueba de Playwright con dos pestañas |
| NFR-U10-42 | **CSP estricta sin excepciones**: sin `'unsafe-inline'` ni `'unsafe-eval'`; estilos compilados en el build (CSS Modules); componentes sin estilos inyectados (React Aria); gráficos en SVG de React; PDF del expediente con una librería sin `eval`. Se agrega a la CSP de U2 `require-trusted-types-for 'script'; trusted-types 'none'` | Playwright recorre todas las vistas y diálogos con un listener de `securitypolicyviolation`: cero violaciones; prueba de las cabeceras del gateway (U2) con las directivas nuevas |
| NFR-U10-43 | **Sin HTML de datos**: `dangerouslySetInnerHTML` prohibido por ESLint en todo el proyecto (BR-U10-11); Trusted Types con `'none'` lo hace fallar también en tiempo de ejecución | ESLint en CI; prueba de que `free_text` con `<script>` se muestra como texto |
| NFR-U10-44 | **Cadena de suministro de npm**: `npm ci` desde `package-lock.json` con integridad y `--ignore-scripts` (salvo una lista explícita versionada); `npm audit` y Trivy sobre el lockfile en `supply-chain.yml` de U1, con bloqueo por hallazgo crítico o alto sin excepción vigente; SBOM con Syft y firma con Cosign de las dos imágenes | `supply-chain.yml`; prueba de que el lockfile existe y `npm ci --ignore-scripts` termina en 0 |
| NFR-U10-45 | **Imagen de la SPA**: servidor estático sin privilegios (`nginx-unprivileged`, `runAsNonRoot`, `readOnlyRootFilesystem`), solo archivos; `index.html` con `Cache-Control: no-store` y los recursos con hash `public, max-age=31536000, immutable`. Las cabeceras de seguridad las pone el gateway (U2), no la imagen | `hadolint`; prueba de las cabeceras de caché con `curl` en kind; `conftest` del contexto de seguridad |
| NFR-U10-46 | **Autorización** en el BFF (BR-U10-01) y otra vez en el destino; matriz rol × endpoint (BR-U10-19) en cada PR que toca el BFF o el registro de contratos | Matriz generada (PBT-U10-01) |

## 6. Usabilidad (Q8, Q9; NFR-USA-01, FR-UI-06)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-50 | **Navegadores**: las dos últimas versiones estables de Chrome y Edge y la ESR vigente de Firefox, en escritorio, con ancho mínimo de 1 280 px; sin soporte móvil | Playwright en Chromium y Firefox; `browserslist` del build con esos objetivos |
| NFR-U10-51 | **WCAG 2.1 AA**: `axe-core` sin violaciones `serious` ni `critical` en cada vista y diálogo; `eslint-plugin-jsx-a11y` en CI; lista de chequeo manual por vista (teclado de punta a punta, foco visible, NVDA en los flujos de decisión y aprobación, contraste 4,5:1) adjunta al PR | Playwright + `@axe-core/playwright`; evidencia manual en el PR |
| NFR-U10-52 | El step-up anuncia la apertura de la ventana (región `aria-live`) y devuelve el foco al control que la abrió en **< 1 s** después de que la ventana se cierra (revisión del Infrastructure Design de U10, 2026-10-10) | Prueba de Playwright del foco; ítem de la lista manual |
| NFR-U10-53 | Ningún texto en los componentes: todo sale de `messages.es.json` y `labels.es.json` (FR-UI-06); fechas y números con `Intl` en `es-CO` | Regla de ESLint que rechaza literales de texto en JSX; PBT-U10-06 |

## 7. Mantenibilidad y pruebas (Q10, Q11, Q14; PBT-02..10)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U10-60 | **BFF**: cobertura de ramas 100 % en `object_rules` y `errors`, ≥ 90 % en el resto; `mutmut` en `object_rules` con 0 sobrevivientes sin justificar | `pytest-cov` y `mutmut` en CI |
| NFR-U10-61 | **SPA**: cobertura de ramas 100 % en `stepup` y en la validación de la decisión, ≥ 80 % en el resto; mutación con Stryker en `stepup` | Vitest con `@vitest/coverage-v8`; Stryker en CI |
| NFR-U10-62 | PBT-U10-01..06 con perfiles `ci` y `nightly` y la semilla impresa (Hypothesis en el BFF, fast-check en la SPA) | Workflow de CI; la semilla en el log |
| NFR-U10-63 | Extremo a extremo: Playwright con dobles en CI y con Keycloak y los servicios reales en kind, ejecutado por el operador (AUTONOMIA-01) | Workflow de CI; evidencia del operador |
| NFR-U10-64 | TypeScript estricto (`strict`, `noUncheckedIndexedAccess`) y `mypy --strict` en el BFF | CI |

## 8. Pendientes para NFR Design (resueltos)

Todos se resolvieron en el NFR Design de U10: timeouts y conexiones en P-U10-04, alertas en
P-U10-10, perfil de carga y de red en P-U10-11 (segunda revisión del Infrastructure Design de U10, 2026-10-10: antes figuraban como abiertos).

## 9. Cumplimiento de extensiones (NFR Requirements U10)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-04 | Cumple | NFR-U10-42, 43, 45 |
| SECURITY-08 | Cumple | NFR-U10-46 |
| SECURITY-10 | Cumple | NFR-U10-44 |
| SECURITY-12 | Cumple | NFR-U10-40, 41 |
| SECURITY-14 | Cumple | NFR-U10-34, 46 (`authz.denied` y errores del navegador) |
| SECURITY-15 | Cumple | NFR-U10-32, 34 (sin detalles en errores ni en la telemetría) |
| RESILIENCY-01 / 02 | Cumple | NFR-U10-20 |
| RESILIENCY-08 / 09 | Cumple | NFR-U10-10, 12, 22 |
| RESILIENCY-10 | Cumple | NFR-U10-30, 31, 33 |
| RESILIENCY-05 / 07 | Cumple | NFR-U10-21, 34 |
| PBT-02..10 | Cumple | NFR-U10-60..63 |
| AUTONOMIA-01 | Cumple | Las pruebas con clúster las ejecuta el operador (NFR-U10-04, 63) |
| AUTONOMIA-02 | Cumple | Cada requisito tiene su verificación |

## 10. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio | Origen |
|---|---|---|
| U1 P-U1-09 y plan de U1 (Paso 6) | BFF en `vectra-high`; SPA en `vectra-normal` | Q4 |
| U2 domain-entities §4.1 (perfiles `spa` y `api`), BR-U2-13 y plan de U2 | CSP con `require-trusted-types-for 'script'; trusted-types 'none'` | Q7 |
| `component-methods.md` C03; `unit-of-work.md` U10; U10 BR-U10-01 y BR-U10-19 | Endpoint 28: `report_client_error` (`POST /api/console/client-errors`) | Q12 |
| U0 domain-entities §8 (`LogRecord`) y §8.1 | Campo `app_version` en la allowlist; evento `console.client_error` (`error_code`, `route_template`, `app_version`) | Q12 |
