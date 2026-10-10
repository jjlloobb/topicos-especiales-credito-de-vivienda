# Plan de NFR Requirements — U10 `console`

**Alcance:** requisitos no funcionales y stack de los dos componentes de U10, sobre el
Functional Design aprobado (BR-U10-01..19, PBT-U10-01..06):
- `console-bff`: los 27 endpoints de C03, sin estado, con rol, MFA y regla de objeto;
- `console-spa`: React + TypeScript, servida por el api-gateway en `/` (F02, perfil `spa` de U2).

**Ya decidido** (no se pregunta):
- **Identidad (U2):** cliente público `vectra-console` con PKCE S256; access token de 300 s; refresh con rotación; sesión SSO de 1 800 s de inactividad y 36 000 s como máximo (BR-U2-06); tokens solo en memoria (BR-U2-07, BR-U10-05); step-up en ventana emergente (BR-U10-06).
- **Borde (U2):** un solo origen; `/api/console/**` con 20 req/s por `sub` y ráfaga de 40, cuerpo ≤ 64 KiB; CSP del perfil `spa`: `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'none'`.
- **Contratos (U0):** cliente TS generado (`contracts/ts`, `openapi-fetch`, `decimal.js`); `vectra_common` (`create_app`, `deps.call` con timeout obligatorio y circuit breaker, allowlist de logs, `authz.denied`).
- **Carga de referencia:** 200 usuarios concurrentes (NFR-U2-10).
- **Requisitos del PRD:** WCAG 2.1 AA como objetivo de la SPA (NFR-USA-01); textos en español externalizados (FR-UI-06); autorización en el servidor (FR-UI-07).
- **Criticidad (unit-of-work):** BFF High, SPA Medium. Q4 pregunta cómo encaja esto con la PriorityClass `vectra-normal` que hoy tiene el BFF en P-U1-09.

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Latencia del BFF (Performance; F10–F14)
El BFF agrega su propio tiempo (JWT, rol, MFA, objeto, serialización) al del servicio de destino.

A) **Presupuesto propio y objetivos por tipo de endpoint**:
   - sobrecosto propio del BFF p95 ≤ 30 ms, medido como la diferencia entre la latencia del BFF y la del servicio de destino;
   - endpoints de paso: p95 ≤ el del destino + 30 ms (por ejemplo, `get_case` de U8 + 30 ms);
   - `get_dossier` (registro y case-service **en paralelo**): p95 ≤ 1 s;
   - `get_disparity` (governance y bias **en serie**): p95 ≤ el de bias + 200 ms;
   - `get_me`: p95 ≤ 20 ms (sin llamadas a otros servicios);
   - medido con 200 usuarios concurrentes (NFR-U2-10), con un perfil de uso por rol en k6.

   (Recomendado)

B) Un solo objetivo para todo el BFF: p95 ≤ 1 s

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Rendimiento de la SPA (Performance; Usability)

A) **Presupuestos de carga y de interacción**:
   - JavaScript inicial ≤ 250 KiB comprimido, con rutas cargadas a demanda por rol;
   - primera vista útil (bandeja con datos) p75 ≤ 2,5 s en la red del banco, medida con Lighthouse CI en kind (LCP ≤ 2,5 s, CLS ≤ 0,1);
   - detalle de un caso desde la bandeja p75 ≤ 1 s;
   - CI falla si el bundle supera el presupuesto.

   (Recomendado)

B) Sin presupuestos explícitos; se mide en la demostración

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Escalado del BFF (Scalability)

A) **HPA de 2 a 6 réplicas por CPU al 70 %**, como case-service (U8):
   - 200 usuarios concurrentes con el perfil de Q1 no superan 2 réplicas al 50 % de CPU;
   - el BFF no guarda estado (BR-U10-02), así que escala sin afinidad de sesión;
   - un cliente HTTP por servicio de destino con su límite de conexiones (U0 NFR-U0-23 (d)), dimensionado para 6 réplicas sin saturar a los destinos.

   (Recomendado)

B) 2 réplicas fijas con la exención `vectra.io/hpa-exempt`, como el servicio HTTP de U9

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Disponibilidad y criticidad (Availability)
`unit-of-work.md` declara el BFF como **High**. P-U1-09 le asigna `vectra-normal`.

A) **El BFF pasa a `vectra-high`**; la SPA queda en `vectra-normal`:
   - sin el BFF, ningún analista puede decidir ni ningún aprobador actuar, y el SLO de disponibilidad de la consola es el del BFF;
   - SLO del BFF 99,5 % mensual en horario operativo (sin contar caídas de los servicios de destino, que tienen su propio SLO);
   - 2 réplicas mínimas en zonas distintas y PDB `minAvailable: 1`;
   - la SPA es estática: 2 réplicas, spread por zona y PDB; si cae, el gateway devuelve 503 en `/` y la API sigue respondiendo;
   - se corrige P-U1-09 (U1).

   (Recomendado)

B) Todo en `vectra-normal`, y se corrige la criticidad de `unit-of-work.md` a Medium

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Degradación por servicio de destino (Reliability; RESILIENCY-10)

A) **Aislamiento por destino**:
   - un circuit breaker por servicio de destino en `deps.call` (case, governance, registry, explainability, bias), con los umbrales de U7 (≥ 50 % de fallos en 20 llamadas dentro de 30 s; semiabierto a los 10 s);
   - timeouts del BFF hacia cada destino = p99 del destino + margen, siempre menores que el timeout de la SPA (10 s) y con `x-vectra-deadline` propagado;
   - si un destino cae, solo fallan sus vistas (503 `dependency_unavailable` con el mensaje del catálogo); las demás siguen. Por ejemplo, con bias caído, la bandeja y la decisión funcionan;
   - la composición de `get_dossier` sigue BR-U10-03 (case caído → sin identificadores);
   - los `POST` **no** se reintentan en el BFF (decisión, aprobaciones): el usuario ve el error y decide. Los `GET` tampoco: la SPA vuelve a pedir en el siguiente refresco.

   (Recomendado)

B) Reintento automático de un `GET` fallido en el BFF, una vez, con 200 ms de espera

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Inactividad y cierre de sesión en la SPA (Security; SECURITY-12)
La sesión SSO de Keycloak vence a los 1 800 s de inactividad (BR-U2-06).

A) **Aviso y cierre alineados con Keycloak**:
   - inactividad de la SPA = sin interacción del usuario (teclado, ratón o foco), no solo sin llamadas; el refresco automático de la bandeja **no** cuenta como actividad;
   - a los 25 min sin actividad, un diálogo «tu sesión se cerrará en 5 min», con «seguir»; a los 30 min, logout (BR-U10-05) y regreso al login;
   - un formulario con contenido sin enviar muestra el aviso, pero no evita el cierre (los datos no se guardan fuera de la memoria);
   - logout en una pestaña cierra la sesión en todas (evento `storage` o `BroadcastChannel`, sin tokens en el mensaje).

   (Recomendado)

B) Sin control propio: la SPA se entera al fallar el refresh

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — CSP estricta y librerías de la SPA (Security; SECURITY-04)
El perfil `spa` de U2 no permite `'unsafe-inline'` ni `'unsafe-eval'`: ni estilos en línea ni CSS-in-JS que inyecte `<style>` en tiempo de ejecución.

A) **Librerías compatibles con la CSP, y Trusted Types**:
   - estilos con CSS Modules, compilados en el build (sin CSS-in-JS en tiempo de ejecución); componentes accesibles sin estilos (por ejemplo, React Aria) en lugar de librerías de UI que inyectan estilos;
   - gráficos de la vista de sesgo con SVG renderizado por React (sin `eval` ni estilos en línea), o solo el embebido de Grafana;
   - PDF del expediente generado en el navegador con una librería sin `eval`;
   - se agrega a la CSP de U2 `require-trusted-types-for 'script'` y `trusted-types 'none'` (la SPA nunca asigna HTML), que refuerza BR-U10-11;
   - prueba de Playwright: cero violaciones de CSP en la consola del navegador recorriendo todas las vistas.

   (Recomendado)

B) Relajar la CSP con `style-src 'unsafe-inline'` para usar una librería de UI con CSS-in-JS

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Navegadores soportados (Usability; Maintainability)

A) **Navegadores corporativos actuales**: las dos últimas versiones estables de Chrome y Edge y la ESR vigente de Firefox, en escritorio, con un ancho mínimo de 1 280 px. Sin soporte móvil. Playwright corre en Chromium y Firefox. (Recomendado)

B) Además, Safari y tabletas

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Verificación de accesibilidad WCAG 2.1 AA (Usability; NFR-USA-01)

A) **Automática más una revisión manual**:
   - `axe-core` en las pruebas de Playwright de cada vista y de cada diálogo, sin violaciones `serious` ni `critical`;
   - `eslint-plugin-jsx-a11y` en CI;
   - una lista de chequeo manual por vista (teclado de punta a punta, foco visible, lector de pantalla NVDA en los flujos de decisión y de aprobación, contraste 4,5:1), adjunta al PR como evidencia;
   - el step-up en ventana emergente anuncia la apertura y devuelve el foco al formulario al cerrarse.

   (Recomendado)

B) Solo `axe-core` automático

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Stack del BFF (Tech Stack)

A) **Python 3.12 + FastAPI + `vectra_common`**, como el resto de los servicios: reusa el registro de contratos (`RouteContract`), la autenticación, los errores, los logs con allowlist y `deps.call` de U0, y la matriz rol × endpoint sale del mismo registro (BR-U10-19). (Recomendado)

B) Node.js + TypeScript, compartiendo tipos con la SPA. Habría que reimplementar en TS la autorización, los errores y el logging de U0

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Stack de la SPA (Tech Stack)

A) **React 18 + TypeScript estricto + Vite**:
   - enrutamiento con React Router; datos con TanStack Query (refrescos de BR-U10-10, caché en memoria);
   - OIDC con `oidc-client-ts` configurado con almacenamiento en memoria (`InMemoryWebStorage`), y el step-up con su `signinPopup`;
   - formularios con validación desde el esquema de U0;
   - i18n con catálogos JSON (`messages.es.json`, `labels.es.json`) y una librería de formato (`Intl`), sin texto en los componentes;
   - pruebas con Vitest, Testing Library, fast-check (PBT-U10-04..06) y Playwright (extremo a extremo);
   - versiones fijadas en el `package-lock.json`, `npm ci` en CI.

   (Recomendado)

B) Otro framework (Vue, Angular). Perdería el cliente TS de U0 ya pensado para React

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12 — Errores del navegador (Reliability; Observability)
Hoy nada registra un error de JavaScript en el navegador. No hay telemetría externa (sin egress).

A) **Endpoint propio en el BFF, mínimo**:
   - `POST /api/console/client-errors` (28.º endpoint de C03, cualquier rol de negocio, sin MFA), con `{error_code, route_template, app_version, correlation_id?}`: sin mensajes, sin trazas, sin URL completa ni datos del formulario;
   - límite de 10 por minuto por sesión en la SPA y el rate limit de U2;
   - el BFF lo emite como evento `console.client_error` (catálogo de U0 §8.1) y como métrica `vectra_console_client_errors_total{error_code}`, con una alerta si sube después de un despliegue.

   (Recomendado)

B) Sin telemetría del navegador: solo los logs del BFF

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13 — Cadena de suministro de npm (Security; SECURITY-10)

A) **Las mismas reglas que Python**:
   - `npm ci` desde `package-lock.json` con integridad; sin scripts de instalación (`--ignore-scripts`), salvo una lista explícita;
   - `npm audit` y Trivy sobre el lockfile en `supply-chain.yml` de U1; un hallazgo crítico o alto sin excepción vigente bloquea el PR;
   - SBOM de la imagen de la SPA con Syft y firma con Cosign;
   - la imagen de la SPA es un servidor estático sin privilegios (`nginx-unprivileged`, `readOnlyRootFilesystem`), y solo sirve archivos: `index.html` sin caché (`no-store`) y los recursos con hash `immutable`;
   - las cabeceras de seguridad las pone el gateway (U2), no la imagen.

   (Recomendado)

B) Servir la SPA desde el BFF (un solo contenedor)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 14 — Pruebas y mantenibilidad (Maintainability; PBT-02..10)

A) **Umbrales como el resto de las unidades**:
   - BFF: cobertura de ramas 100 % en `object_rules` y `errors`, ≥ 90 % en el resto; `mutmut` en `object_rules`;
   - SPA: cobertura de ramas 100 % en `stepup` y en la validación de la decisión, ≥ 80 % en el resto; mutación con Stryker en `stepup`;
   - PBT-U10-01..06 con perfiles `ci` y `nightly` y la semilla impresa (fast-check en la SPA, Hypothesis en el BFF);
   - la matriz rol × endpoint (BR-U10-19) corre en cada PR que toca el BFF o el registro de contratos;
   - Playwright extremo a extremo en kind con Keycloak real, ejecutado por el operador (AUTONOMIA-01), más una versión con dobles en CI.

   (Recomendado)

B) Solo pruebas extremo a extremo, sin umbrales por módulo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Plan de trabajo

- [x] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [x] `nfr-requirements.md` (NFR-U10-xx): rendimiento, escalado, disponibilidad, seguridad, fiabilidad, usabilidad, mantenibilidad, cada uno con su verificación
- [x] `tech-stack-decisions.md`: BFF, SPA, pruebas, imagen y cadena de suministro
- [x] Cambios a otras unidades (U1 P-U1-09 según Q4; U2 CSP según Q7; U0 §8.1 y C03 según Q12) registrados
- [x] Tabla de cumplimiento de extensiones
- [x] Registrar en `audit.md` y actualizar `aidlc-state.md`
