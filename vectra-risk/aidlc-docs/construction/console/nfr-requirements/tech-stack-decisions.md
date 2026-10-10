# Decisiones de stack — U10 `console`

Decisiones del plan (`console-nfr-requirements-plan.md`, Q1–Q14 = A) y heredadas de U0, U1 y
U2. Versiones fijadas en `uv.lock` (BFF) y `package-lock.json` (SPA).

---

## 1. `console-bff`

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje y API | Python 3.12, FastAPI, Pydantic v2, `vectra_common.create_app` | Q10, U0 |
| Rutas y autorización | Registro de contratos de U0 (`RouteContract`) con rol, MFA y regla de objeto; la matriz rol × endpoint sale del mismo registro | Q10, BR-U10-01, 19 |
| Clientes HTTP | `httpx` solo vía `vectra_common.deps.call`: timeout obligatorio, `x-vectra-deadline`, un cliente por destino y circuit breaker | Q5, U0 |
| Composición | `asyncio.TaskGroup` para las llamadas en paralelo de `get_dossier` | Q1 |
| Errores y logs | `Problem` de U0 y logger con allowlist; evento `console.client_error` | Q12, U0 |
| PBT | Hypothesis (perfiles `ci` y `nightly`) | Q14, U0 |
| Cobertura y mutación | `pytest-cov`, `mutmut` | Q14 |
| Tipos | `mypy --strict`, ruff, import-linter | Q14, U0 |

## 2. `console-spa`

| Área | Decisión | Origen |
|---|---|---|
| Lenguaje y build | React 18, TypeScript estricto, Vite; `browserslist` con Chrome y Edge (2 últimas) y Firefox ESR | Q8, Q11 |
| Enrutamiento | React Router, con rutas cargadas a demanda por rol | Q2, Q11 |
| Datos | TanStack Query (caché en memoria; refrescos de BR-U10-10) sobre el cliente `openapi-fetch` de U0 (`contracts/ts`) | Q11, U0 |
| OIDC | `oidc-client-ts`: `UserManager` con `InMemoryWebStorage` para el login y el refresco; para el step-up, la API de **bajo nivel** `OidcClient` (`createSigninRequest` y `processSigninResponse`, con `stateStore` en `InMemoryWebStorage`), con la ventana, el `postMessage` y la validación propios de BR-U10-06. No se usa `signinPopup`, que abre la ventana por su cuenta y procesa la respuesta en la ventana emergente (segunda revisión del Infrastructure Design de U10, 2026-10-10) | Q11, BR-U10-05, 06 |
| Formularios | Validación desde el esquema de U0; contador de la justificación con el mismo recorte que el servidor | Q11, BR-U10-09 |
| Componentes | React Aria (accesibles y sin estilos inyectados) | Q7, Q9 |
| Estilos | CSS Modules compilados en el build; sin CSS-in-JS en tiempo de ejecución | Q7 |
| Gráficos | SVG renderizado por React; el dashboard detallado es el embebido de Grafana | Q7, BR-U10-16 |
| PDF del expediente | Librería de generación en el navegador sin `eval` ni estilos en línea (se fija en el plan de tareas, con la prueba de CSP de NFR-U10-42) | Q7 |
| Decimales | `decimal.js` de U0; ESLint prohíbe `Number(`/`parseFloat` sobre `Decimal*` | U0 |
| i18n | Catálogos JSON (`messages.es.json`, `labels.es.json`) e `Intl` en `es-CO` | Q11, FR-UI-06 |
| Pruebas | Vitest, Testing Library, fast-check, Playwright con `@axe-core/playwright`, Lighthouse CI, Stryker, `@vitest/coverage-v8` | Q2, Q9, Q14 |
| Lint | ESLint con `eslint-plugin-jsx-a11y`, prohibición de `dangerouslySetInnerHTML` y de literales de texto en JSX | Q9, BR-U10-11, 17 |
| Presupuesto del bundle | `size-limit` en CI (≤ 250 KiB comprimido inicial) | Q2 |
| Imagen | `nginx-unprivileged` pinneado por digest, solo archivos estáticos; caché `no-store` en `index.html` e `immutable` en los recursos con hash | Q13 |
| Cadena de suministro | `npm ci --ignore-scripts`, `npm audit`, Trivy, Syft y Cosign (workflows de U1) | Q13 |

## 3. Descartado

| Opción | Motivo |
|---|---|
| BFF en Node.js | Habría que reimplementar en TypeScript la autorización, los errores, el logging con allowlist y `deps.call` de U0 (Q10) |
| Librerías de UI con CSS-in-JS en tiempo de ejecución | Exigen `style-src 'unsafe-inline'` (Q7) |
| Servir la SPA desde el BFF | Mezcla un componente High con uno estático Medium y obliga al BFF a servir archivos (Q13) |
| Telemetría del navegador externa (RUM) | Requiere egress; se usa el endpoint propio del BFF (Q12) |
| WebSockets o SSE | El refresco por sondeo de BR-U10-10 alcanza para la carga de la consola |
