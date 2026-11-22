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
| NFR-U10-53 | Ningún texto en los componentes: todo sale de `messages.es.json` y `labels.es.json` (FR-UI-06); fechas y números con `Intl` en `es-CO`. **Enmendado el 2026-11-21 (§11, E-1 y E-7):** tres idiomas, español (por omisión), inglés y portugués de Brasil | Regla de ESLint que rechaza literales de texto en JSX; PBT-U10-06; paridad de claves y de marcadores entre los catálogos |

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

## 11. Enmiendas

**Enmienda del 2026-11-21 — pedido del dueño del proyecto para la sustentación.** Hasta esta fecha el diseño fijaba la consola solo en español
(NFR-U10-53, BR-U10-17, tech-stack §2) y el tema lo decidía solo el sistema. No cambian el BFF, las rutas, la API ni la autenticación.

| Id | Qué cambia | Regla que enmienda | Verificación |
|---|---|---|---|
| E-1 | **Idioma español, inglés o portugués de Brasil** (el portugués, por E-7), elegido en un selector de la cabecera y de la pantalla de inicio de sesión. Catálogos `messages.<idioma>.json` y `labels.<idioma>.json` con exactamente las mismas claves y los mismos marcadores. Idioma inicial: la preferencia guardada; si no hay, el `locale` de `get_me` si es uno de los dos; si no, el del navegador si es español o inglés; si no, español. El cambio es inmediato, sin recargar, y actualiza `<html lang>` y el título. Fechas y números con `Intl`: `es-CO` en español y `en-GB` en inglés (día antes del mes y mes con letras, sin ambigüedad; pesos como «COP 1,500,000»), siempre en la zona de Bogotá; los decimales del servidor solo se formatean, no se recalculan. Los textos que entrega el servidor (narrativas, avisos, nombres, identificadores) no se traducen en el cliente. El idioma no viaja al servidor; `SessionInfo.locale` sigue siendo `es-CO`. El login de Keycloak se trata aparte | NFR-U10-53; BR-U10-17; tech-stack §2 (i18n) | vitest: resolución del idioma inicial, cambio, persistencia, paridad de claves y marcadores, formatos por idioma; Playwright: recorrido de las demos en inglés sin ningún texto del catálogo en español a la vista |
| E-2 | **Tema «Sistema» (por omisión), «Claro» u «Oscuro»**, en un selector junto al de idioma. Una sola paleta: cada token de color lleva su valor claro y su valor oscuro con `light-dark()` (los colores no cambian), y `data-theme` en `<html>` fija `color-scheme` y gana al sistema en los dos sentidos. El tema guardado se aplica antes de la primera pintura con un guion del mismo origen en el `<head>` (`theme-boot.js`): la CSP no cambia y sigue sin admitir guiones en línea | NFR-U10-51 (el contraste AA se exige en los dos temas); NFR-U10-42 (sin cambios) | vitest: contraste de cada par texto/fondo en claro y en oscuro; Playwright: `axe` con cada tema forzado en contra del sistema, tamaños de pantalla en oscuro, primera pintura, cero eventos `securitypolicyviolation` |
| E-3 | **Preferencias en `localStorage`**: dos claves (`vectra.console.language`, `vectra.console.theme`), cada una con un valor de un conjunto cerrado, que solo se escriben cuando la persona elige y se validan al leer. No son datos personales ni secretos. Los tokens, el usuario y el estado del login siguen como estaban (memoria y la clave transitoria de `sessionStorage`); sin cookies nuevas. Un solo módulo de `src/` nombra `localStorage` (excepción acotada de ESLint) | BR-U10-05 (que trata de los tokens y no cambia); `code/spa.md` §6 («`localStorage` sigue prohibido») | ESLint y su prueba (un solo archivo); las pruebas del login siguen exigiendo `localStorage` vacío sin elección y ninguna clave en `sessionStorage` al terminar |
| E-4 | **`ui_locales` en las peticiones de autorización**: el login silencioso (`prompt=none`), el interactivo y el step-up llevan el parámetro estándar de OIDC `ui_locales` con el idioma activo de la consola (`es`, `en` o `pt-BR`, que es como Keycloak nombra el portugués de Brasil; nunca texto libre), para que el login de Keycloak salga en el mismo idioma. PKCE, `state`, `nonce`, `redirect_uri`, `prompt`, `max_age` y `acr_values` no cambian. Es la única modificación del flujo de autenticación, autorizada expresamente | BR-U10-05, BR-U10-06 (sin otros cambios); P-U2-08 (`es` por omisión en el realm: compatible) | vitest: los argumentos de las tres peticiones y la URL que construye `oidc-client-ts`; Playwright: las URL de autorización contra el emisor de prueba |
| E-5 | **Marca de agua**: una ilustración propia en SVG dentro del código (el horizonte de un barrio; sin imágenes de terceros, sin texto), decorativa (`aria-hidden`, sin capturar clics), con el token `--watermark` y opacidad 0,1, al pie de las vistas de casos, congelamientos y modelos (fuera de tablas, tarjetas, formularios y diálogos; oculta por debajo de 768 px) y al fondo de la pantalla de inicio de sesión. Se oculta con más contraste, con colores forzados y al imprimir. La CSP no cambia | NFR-U10-51 (el peor caso de contraste sigue en AA); NFR-U10-42 (sin cambios) | vitest: decorativa, token en los dos temas, contraste del peor caso; Playwright: `axe`, sin scroll horizontal, sin pisar contenido ni controles |
| E-6 | **Pasada de usabilidad** (sin rutas, llamadas, datos ni autenticación nuevos; lo que se envía al servidor no cambia). (a) El `case_id` se muestra: completo y con un botón «Copiar» en el detalle del caso, y abreviado (8 caracteres, el completo en `title`) con su botón en la bandeja; «Ir al caso» acepta también la dirección completa del caso pegada (solo se usa el UUID) y su error dice qué forma tiene un identificador. (b) «Copiar» usa `navigator.clipboard.writeText` dentro del clic; si el navegador no lo permite, el valor se muestra seleccionado: no se relaja ninguna política. También copia el código de soporte de un error. (c) Los grupos de monitoreo de un catálogo cerrado (sexo, región, «no informado») llevan etiqueta en los catálogos, con el código en `title`; un `feature_id` (conjunto abierto: la consola no recibe el diccionario de variables) **no** se traduce, solo se presenta sin guiones bajos. (d) El título del documento es «{pantalla} · Vectra Risk» en el idioma en curso (sin sesión, el general); al cambiar de pantalla el foco pasa a `<main>`, la página vuelve arriba y la pantalla se anuncia en una región `aria-live`; hay un enlace «Saltar al contenido». (e) La tarjeta de un congelamiento dice la última resolución registrada y cuándo; «Resolver este congelamiento» **sigue visible** (un congelamiento admite varias resoluciones) con una ayuda, y el 409 del diálogo dice qué pasó y qué hacer. (f) La cabecera dice «Verificación en dos pasos: vigente» o «se pedirá al confirmar», con el mismo criterio que el botón de confirmación (BR-U10-06), y el diálogo explica «Verificar y confirmar» antes de pulsarlo; los avisos del step-up se ven sobre la página y los diálogos. (g) Un `unauthenticated` ofrece «Iniciar sesión de nuevo» (el mismo `login` interactivo, que vuelve a la ruta). (h) Bandeja: vacía con filtro propone quitarlo; una página más allá de la última lo dice; «Más filtros» cuenta los avanzados activos; con 6 páginas o más hay «Ir a la página»; las fechas dicen «hora de Colombia» | BR-U10-10 («Ir al caso» acepta un `case_id`: ahora también la dirección del caso); BR-U10-09 (la «etiqueta en español» de los factores sigue pendiente del diccionario de variables: candidata abierta); BR-U10-13 y BR-U10-06 (sin cambio de reglas: solo textos); E-1 («actualiza el título»: ahora por pantalla); NFR-U10-52 (sin cambios) | vitest: `copy-button`, `cases-inbox`, `case-detail`, `freezes`, `shell`; Playwright: `tests/e2e/usability.spec.ts` (portapapeles real y cero violaciones de la CSP, título, foco, teclado), más `tests/a11y`, `tests/csp` y los tamaños de pantalla |
| E-7 | **Tercer idioma: portugués de Brasil** (`pt` en la consola y en la preferencia guardada; `pt-BR` en `<html lang>`, en el `lang` de su opción del selector, en `Intl` y en `ui_locales`). Catálogos `messages.pt.json` y `labels.pt.json` con exactamente las claves, el orden y los marcadores de los otros dos (incluidas las claves de E-6). El conjunto cerrado de idiomas pasa a `es`, `en`, `pt`; el idioma inicial sigue el mismo orden (preferencia guardada, `locale` de `get_me`, navegador, español) y cualquier `pt-*` del navegador o de `get_me` es portugués. El selector ofrece «Português». Fechas y números con `Intl` en `pt-BR` (fecha corta, «12/11/2026, 15:30»: la media de `pt-BR`, «12 de nov. de 2026», parte las celdas de las tablas), siempre en la zona de Bogotá; los montos siguen siendo pesos colombianos («COP 1.500.000»): **no se convierte moneda**, y los decimales del servidor solo se formatean. Los textos propios de React Aria también van en portugués. Los tres catálogos siguen en el JavaScript inicial (no hizo falta carga diferida: ver el presupuesto de NFR-U10-03 en la bitácora del cambio). La lista de frases prohibidas de U0 no trae frases en portugués: la prueba de paridad comprueba las equivalentes (candidata: ampliarla en U0 con aprobación de cumplimiento) | E-1, E-3 (el valor guardado puede ser `pt`), E-4 (`ui_locales=pt-BR`); NFR-U10-53; BR-U10-17 y BR-U10-18 | vitest: resolución, cambio, persistencia, formatos `pt-BR`, paridad de los tres catálogos, `ui_locales`; Playwright: recorrido de las demos en portugués sin textos del catálogo en español a la vista, `axe` en portugués, tamaños de pantalla desde 360 px en portugués |
