# U10-T04 — SPA de `console`, vistas de la demo: casos, gobierno, CSP, accesibilidad, extremo a extremo con dobles y resumen

**Unidad:** U10 `console` (`console-spa`)
**Historias que implementa** (plan §3, en la parte que el recorte deja entrar):
- US-102, US-104, US-106, US-107, US-108, US-109, US-110, US-501 y US-502: bandeja, detalle, explicación y decisión (Paso 13);
- US-304, US-305 y US-602: congelamientos, resolución con MFA y vistas por rol (Paso 14);
- US-611: CSP, errores genéricos y extremo a extremo (Paso 15).

Quedan **diferidas con su vista** (ver los tachados): US-112, US-402 y US-403 (Paso 13); US-201, US-203, US-205, US-206, US-306 y US-307 (Paso 14).

**Depende de:**
- **U10-T03 fusionada en `main` antes de despachar, con su puerta en `PASA`** (`bitacoras/U10-T03.md`, «Puerta del Paso 10»). Hoy **no** está en `main`. Esta tarea usa su `auth`, `stepup`, `inactivity`, `api`, `i18n` y `reporter`, su `playwright.config.ts`, el emisor OIDC de prueba y el servidor del BFF con dobles, los navegadores de Playwright ya instalados y `aidlc-docs/construction/console/code/spa.md`. Si la puerta quedó en `FALLA`, esta tarea no se despacha.
- **U10-T02 y U10-T01 en `main`** (PR #142 y #139): el BFF, sus dobles y el esqueleto de la SPA.
- U0 en `main`: `contracts/ts` y `contracts/tools/forbidden_phrases.py`.
- U2 en `main`, **solo como dato de las pruebas**: `identity-edge/gateway/routes.yaml` (perfil `spa`, la CSP).
- **No** depende en runtime de Keycloak ni de U3, U4, U7, U8 o U9: todo corre con dobles (plan §1; RL-5).

Sin clúster (AUTONOMIA-01) y sin base de datos.
**Rama:** `tarea/U10-T04`, desde `origin/main`.

Es la **segunda mitad del Bloque E** del plan de U10 (`aidlc-docs/construction/plans/console-code-generation-plan.md`, Pasos 13 a 16).
- El Bloque E se partió en dos tareas por **decisión del usuario del 2026-11-12**: Pasos 10–12 en U10-T03 y Pasos 13–16 aquí (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §4, alternativa «E partido en 10–12 y 13–16»). U10 queda en **5 tareas**; la tabla de §8 todavía dice 4.
- Los Pasos 13, 14, 15 y 16 entran **E\*F**: lo que la tabla §3 nombra como diferido va tachado, con la cita de su fila. Lo demás entra completo.
- **Las PBT no se recortan** (§5.2: «U10: PBT-U10-01..06»). Aquí entra la 04, entera; la 05 y la 06 (U10-T03) tienen que seguir pasando.
- Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas y solo un ROJO bloquea.

Tarea que sigue en U10:
- **U10-T05**: F y el cierre, Pasos 17, 18, 21, 23 y 24. Los Pasos 19 y 20 están diferidos (§3, fila «19 · 20»: D) y el Paso 22 queda consolidado en U12 Paso 18 (enmienda §8).

---

## Alcance

**Dentro:** los Pasos 13 a 16 del plan. Va el texto del plan; lo tachado es lo que el recorte difiere, con su cita. Las rutas de los comandos se escriben completas desde `vectra-risk/` (ver Precisiones).

### Bloque E — SPA (segunda mitad)

- [ ] **Paso 13 — Vistas de casos** (E\*F)
  - `CasesInbox` (filtros de `CaseFilter` en la URL, «Ir al caso» por `case_id`, refresco de 15 s), `CaseDetail` (refresco de 3 s hasta 2 min), `RecommendationSummary`, `ExplanationPanel` (`record_explanation_view` una vez por vista, solo con rol `analista`, y una prueba de que `cro` no la llama; seguimiento de la quinta revisión de coherencia, 2026-10-31), `ApplicationView` (`free_text` como texto), `CreditStatusBadge` (incluido `no_integrado`), `DecisionForm` (validación igual que el servidor, diálogo de confirmación, botón deshabilitado en curso), ~~`ManualApplicationForm` (`Idempotency-Key` por envío), `PersistentFailures` con `retry`, `ApplicantSummaryButton`, `Dossier` (PDF en el navegador) e `IntegrityCheck` (inicio con MFA, `already_active`, estado cada 30 s)~~.
  - Diseño: BR-U10-07..11, 03; frontend-components. Historias: US-102, 104, 106, 107, 108, 109, 110, ~~112, 402, 403,~~ 501, 502.
  - **Aceptación**: `npm run -w console/spa test -- views/cases`: PBT-U10-04 (mismo oráculo que PBT-U8-03); las pruebas de ejemplo del FD de casos (bandeja sin `vencido` por omisión, `free_text` con `<script>`, `no_integrado`, baja confianza y `revision_requerida`, `decision_already_recorded`, ~~expediente sin identificadores, `retry` del CRO,~~ panel de explicación con una sola llamada y ninguna sin abrirlo); la URL de la bandeja nunca contiene datos del solicitante;
    - (de esta tarea; línea del Paso 11 que necesita la bandeja) el refresco de la bandeja real no reinicia el contador de inactividad.
    - Tachado: §3, U10, fila «13 Casos»: «Entran `CasesInbox`, `CaseDetail`, `RecommendationSummary`, `ExplanationPanel`, `ApplicationView`, `CreditStatusBadge`, `DecisionForm` y PBT-U10-04. Se difieren `ManualApplicationForm`, `PersistentFailures`/`retry` (P-16), `ApplicantSummaryButton`, `Dossier` e `IntegrityCheck`, con sus ejemplos». P-16 sigue pendiente (recorte, «Estado»): «mientras no se decida, `PersistentFailures` y `retry` siguen diferidos».

- [ ] **Paso 14 — Vistas de gobierno y sesgo** (E\*F)
  - `RoleMenu` desde `get_me` con las rutas por rol de BR-U10-12; modelos ~~, políticas y fuentes con sus diálogos con MFA~~ (lista y detalle, **de lectura**); ~~`PrePostReportView` + `DecideDataSourceDialog` (sin informe, sin botones); `BiasDashboard` (`DisparityTables` con celdas insuficientes y `GrafanaEmbed` con la leyenda propia encima);~~ `Freezes` y `FreezeContextView` + `ResolveFrozenDialog` (aviso de `reactivar`).
  - Diseño: BR-U10-12, 13 ~~, 14~~, 15 ~~, 16~~. Historias: ~~US-201, 203, 205, 206,~~ US-304, 305 ~~, 306, 307~~.
  - **Aceptación**: `npm run -w console/spa test -- views/governance views/bias`: las rutas por rol coinciden con la columna «Roles» de C03 (`cro` no ve el paquete de contexto; `cumplimiento` no ve la bandeja); celdas insuficientes nunca muestran 0 ni una tasa; el `disclaimer` ~~y la leyenda~~ siempre presente~~s~~;
    - (de esta tarea; ejemplo del FD) vista de congelamiento con el paquete completo y el aviso de `reactivar` (US-304, US-305);
    - (de esta tarea; ejemplo del FD) un aprobador sin MFA reciente confirma → 403 `mfa_required`, ventana emergente y reintento único con la misma justificación → 200. Se prueba con `ResolveFrozenDialog` (US-305), que es el único diálogo con MFA que entra.
    - Tachado: §3, U10, fila «14 Gobierno y sesgo»: «Entran `RoleMenu`, `Freezes`, `FreezeContextView`, `ResolveFrozenDialog` y `Models`/`ModelDetail` de lectura. `BiasDashboard` (`DisparityTables`) según P-14. Se difieren `Policies`, `DataSources`, `PrePostReportView`, `DecideDataSourceDialog`, `RegisterModelForm`, `ApproveModelDialog`, retiro y `GrafanaEmbed`. Las rutas de la SPA por rol se declaran todas, con un marcador en las diferidas (P-17)». El marcador: §6, P-17, «El marcador».
    - **`BiasDashboard`: diferido con su ruta y el marcador. Decidido por el usuario el 2026-11-12**, sobre §6, P-14, «Solo el paquete». `demo-kind-alcance.md` §3 (U9, fila «13») dice «la vista de sesgo la da la consola (U10 Paso 14)»: la enmienda es posterior y D2 muestra el paquete de contexto, que ya trae las tablas de disparidad.
    - «Celdas insuficientes» **no** se difiere con `BiasDashboard`: el paquete de contexto trae `before`, `after`, `last_7_days` e `initial_disparity` con `CellResult.status = muestra_insuficiente`, y `FreezeContextView` las muestra (BR-U10-15).

- [ ] **Paso 15 — CSP, accesibilidad y extremo a extremo con dobles** (E\*F: «Sobre las vistas que entran», §3, fila «15 CSP, a11y, e2e»)
  - Playwright contra la SPA de Vite y el BFF con dobles: recorrido de todas las vistas y diálogos **que entran** con un listener de `securitypolicyviolation` (0 violaciones con la CSP de U2, Trusted Types incluido) y `@axe-core/playwright` (0 `serious` y `critical`).
  - `index.html` sin `<script>` ni `<style>` en línea; `build.modulePreload.polyfill = false`.
  - `size-limit` ≤ 250 KiB comprimido inicial.
  - Diseño: NFR-U10-03, 42, 50, 51; P-U10-08. Historias: US-611.
  - **Aceptación**: `npx playwright test console/spa/tests/e2e console/spa/tests/csp console/spa/tests/a11y --project=chromium --project=firefox`; `npx size-limit` en 0;
    - (de esta tarea; «Verificación» de NFR-U10-41 y NFR-U10-52) logout en dos pestañas por `BroadcastChannel`; tras cerrarse la ventana del step-up, el foco vuelve al control que la abrió en < 1 s;
    - (de esta tarea; «Verificación» de NFR-U10-32, E1 y E3 de P-U10-05 §5 con dobles) con el doble de bias caído, la bandeja, el detalle y la decisión funcionan y `Freezes` muestra el mensaje de `dependency_unavailable`; con el de case caído, la bandeja muestra el mensaje y `Models` sigue.
    - No entra: la lista de chequeo manual por vista ni NVDA (NFR-U10-51, segunda mitad), que son del Paso 22 (§3, fila «22 Kind»: «Se difieren … NVDA»).

- [ ] **Paso 16 — Resumen del frontend** (E\*F)
  - Cobertura de ramas **100 %** en `stepup` y en la validación de la decisión, ≥ 80 % en el resto; ~~Stryker en `stepup`~~.
  - Resumen en `aidlc-docs/construction/console/code/spa.md`.
  - Diseño: NFR-U10-61, 62.
  - **Aceptación**: `npm run -w console/spa test -- --coverage` con los umbrales por archivo; ~~`npx stryker run console/spa/stryker.conf.json` sin sobrevivientes sin justificar en `stepup`~~.
    - Tachado: §3, U10, fila «4 · 16»: «Sin `mutmut` ni Stryker (T3)»; §2, regla 3.
    - El 100 % de `stepup` ya lo exige y lo deja puesto U10-T03 (decisión del coordinador al partir, 2026-11-12). Aquí **se mantiene** y se agregan el 100 % de la validación de la decisión, el 80 % del conjunto y el resumen completo.

### Precisiones

- **Rutas de la aceptación.** El plan escribe `npx playwright test console/spa/tests/…` y `npx size-limit` sin decir desde dónde. Los CA usan la forma que corre desde `vectra-risk/`: `npx playwright test -c console/spa/playwright.config.ts <filtro>` y `npm exec -w console/spa -- size-limit`. Los filtros de vitest (`views/cases`…) casan con la ruta del archivo de prueba, así que las pruebas viven en `console/spa/tests/unit/views/<grupo>/` y `console/spa/tests/property/views/<grupo>/`.
- **Navegadores de Playwright.** Los instaló U10-T03 (decisión del usuario, 2026-11-12). Si en la máquina no están (`ls ~/.cache/ms-playwright`), se instalan igual: `npx playwright install chromium firefox`, sin `sudo`; si falta una librería del sistema, se para y se reporta.
- **Archivos que esta tarea crea o llena (plan §1, más lo que piden los pasos).** Se borra el `.gitkeep` de cada directorio que recibe archivos.
  - `console/spa/src/views/cases/`: `CasesInbox` (con `CaseFilters` y `GoToCase`), `CaseDetail`, `RecommendationSummary`, `ExplanationPanel`, `ApplicationView`, `CreditStatusBadge`, `DecisionForm` y la validación pura de la decisión en un archivo propio (por ejemplo `decision-validation.ts`; es el archivo con el umbral del 100 %).
  - `console/spa/src/views/governance/`: `Models`, `ModelDetail`, `Freezes`, `FreezeContextView` y `ResolveFrozenDialog`.
  - `console/spa/src/views/bias/`: lo que comparten el paquete de contexto y, cuando entre, el dashboard: la tabla de celdas con «muestra insuficiente». `BiasDashboard` y `GrafanaEmbed` **no** se crean.
  - `console/spa/src/views/shared/`: `Layout`, `RoleMenu`, la tabla de rutas por rol, `ProblemMessage`, el marcador «no disponible» de P-17 y «sin acceso».
  - `console/spa/src/api/`: los hooks por endpoint de las vistas que entran.
  - `console/spa/tests/e2e/`, `tests/csp/` y `tests/a11y/`: las especificaciones de Playwright. `tests/unit/views/` y `tests/property/views/`: las de vitest.
  - `console/spa/src/version/` **sigue vacío** (con su `.gitkeep`): es de la parte diferida.
  - **No** se crean: `console/spa/stryker.conf.json` (diferido), `console/spa/nginx.conf` ni `console/spa/Dockerfile` (Paso 17, U10-T05), `console/spa/lighthouserc.json` (Paso 21).
- **Lo que viene de U10-T03 y cómo se usa.**
  - `App.tsx` y la entrada: aquí se les agregan el enrutador, `Layout` y las rutas, dentro de los proveedores que ya existen. La detección de `/stepup-callback` antes de montar React no se toca.
  - `reporter`: recibe por inyección la función que da la plantilla de la ruta (P-7 de U10-T03). Aquí se sustituye por la del enrutador, y el fallo de un `import()` de vista se conecta a `chunk_load_failed`.
  - `i18n`: se agregan las claves de las vistas a `messages.es.json` y `labels.es.json`. PBT-U10-06 y `forbidden_phrases.py` tienen que seguir pasando con ellas (CA-6).
  - `stepup`: `ResolveFrozenDialog` usa el botón de confirmación y `StepUpDialog` de U10-T03; no se escribe otro flujo.
  - Si el recorrido de este paso destapa un defecto en código de U10-T03: P-5.
- **Dependencias de npm.** Se agregan, **con versión exacta**: React Router (ejecución), `@axe-core/playwright`, `size-limit` y su preset de archivo (desarrollo). El lockfile es el `package-lock.json` raíz. `npm audit --audit-level=high` va en CA-9. No se agrega ninguna librería de PDF, de gráficos ni de fechas: lo que las pedía está diferido o lo cubre `Intl`.
- **El paquete inicial y la carga a demanda (NFR-U10-03).** Cada vista se carga con `React.lazy` desde la tabla de rutas. `.size-limit.json` (hoy `[]`) pasa a medir el JavaScript que `dist/index.html` carga al entrar, con **gzip** y tope de `250 KiB`. `size-limit` usa brotli por omisión, que da un número menor: se fija gzip a propósito y se anota en `spa.md`.
- **`browserslist` (NFR-U10-50).** `package.json` declara las dos últimas versiones de Chrome y de Edge y Firefox ESR; `build.target` de Vite sale de ahí o se fija a mano con los mismos objetivos, y una prueba lo lee.
- **Vistas de casos (BR-U10-07 a 11).**
  - `CasesInbox`: los filtros son los campos de `CaseFilter` y viven en la URL. Por omisión, todos los estados menos `vencido`. «Ir al caso» acepta un UUID y abre el detalle. Refresco cada `INBOX_REFRESH_SECONDS` solo con la pestaña visible. La prueba de la URL es una propiedad sobre combinaciones de filtros: ninguna clave ni valor sale de `applicant_display` ni de la solicitud.
  - `CaseDetail`: refresco cada `CASE_REFRESH_SECONDS` mientras el caso está `en_evaluacion` o `en_sincronizacion`, hasta `CASE_REFRESH_MAX_SECONDS` (es la pantalla de D1). Estados con color **y** texto.
  - `ExplanationPanel`: `record_explanation_view` una vez por vista del caso y solo con rol `analista`; con `cro` el panel abre y la llamada no sale. Si la llamada falla, el panel se muestra igual y el error se reporta.
  - `ApplicationView`: sin `sex` ni `socioeconomic_stratum`; `free_text` como texto.
  - `DecisionForm`: las reglas de BR-U10-09 y de frontend-components §3. 422 → error en su campo; 409 `decision_already_recorded` → aviso y recarga del caso; 409 `conflict_state` → error general y recarga; 503 → el mensaje del catálogo (business-logic-model §2.3). Solo `analista` la ve.
  - Los `Decimal4` (score, tasas) son cadenas: se formatean con `Intl` sin pasar por `Number(` ni `parseFloat`.
  - El oráculo de PBT-U10-04 está en P-2.
- **Vistas de gobierno (BR-U10-12, 13, 15).**
  - `RoleMenu` sale de `get_me`. Una ruta a la que el rol no llega muestra «sin acceso» **sin llamar al BFF** (la prueba cuenta cero solicitudes).
  - **Tabla de rutas por rol.** Vive en un solo módulo de `views/shared/` y cada ruta nombra el `operation_id` de C03 que le da los roles. La prueba compara, ruta por ruta, con la columna «Roles» de C03, leída de `aidlc-docs/inception/application-design/component-methods.md` o transcrita con cita; nunca con `REGISTRY` ni con la propia tabla. Se declaran **todas** las vistas de frontend-components §1, también las diferidas:

    | Vista | Roles (C03) | En esta tarea |
    |---|---|---|
    | `CasesInbox`, `CaseDetail` | `analista`, `cro` | entra |
    | `ManualApplicationForm` | `analista` | marcador |
    | `PersistentFailures` | `cro` | marcador |
    | `Dossier` | `cro`, `cumplimiento` | marcador |
    | `IntegrityCheck` | `cro` | marcador |
    | `Models`, `ModelDetail` | `ingeniero_riesgo`, `cro`, `cumplimiento` | entra, de lectura |
    | `Policies` | `analista`, `cro`, `cumplimiento` | marcador |
    | `DataSources` | `ingeniero_riesgo`, `cro`, `cumplimiento` | marcador |
    | `BiasDashboard` | `cumplimiento`, `cro` | marcador (decidido) |
    | `Freezes` | `cumplimiento`, `cro` | entra |
    | `FreezeContextView` | `cumplimiento` | entra |

  - El marcador es una sola vista con un texto del catálogo. No llama al BFF y pasa por `axe` y por la CSP como las demás. Las rutas de la SPA las eliges tú, salvo `/callback` y `/stepup-callback`, que están registradas en el realm de U2 y ya atiende U10-T03.
  - `Models` y `ModelDetail` son de lectura: sin `RegisterModelForm`, `ApproveModelDialog` ni retiro. El informe de validación: P-1.
  - `FreezeContextView`: el paquete completo de BR-U10-13 (antes, después, últimos 7 días, atributo disparador, grupos y bandas implicados, fuentes de datos, disparidad de validación e historial de resoluciones). `before` y `last_7_days` pueden valer `"sin_datos"`. El `disclaimer`: P-4.
  - `ResolveFrozenDialog`: `reactivar`, `descartar` e `investigar`, con justificación obligatoria (1 a 2000, el rango de `FrozenResolutionIn`) y MFA. `reactivar` muestra el aviso de la ventana de monitoreo. Es el flujo de D2.
- **Paso 15.**
  - Herramienta: **Playwright** (`@playwright/test`) con `@axe-core/playwright`, en los proyectos `chromium` y `firefox`, sobre la configuración de U10-T03.
  - El servidor que se prueba es el **build** (`vite build` + `vite preview`), no el servidor de desarrollo: ver P-3. `vite preview` sirve las cabeceras del perfil `spa`, **leídas** de `identity-edge/gateway/routes.yaml`, y pasa `/api/**` y `/auth/**` al servidor de dobles, para que todo sea un solo origen (BR-U10-06; `connect-src 'self'`).
  - El BFF es el real (`console_bff.app.build` con un transporte por destino) sobre los dobles de U10-T02, y el emisor OIDC es el de prueba de U10-T03. No se usa `run_service` ni los puertos 8080 y 8081. Si el recorrido necesita que un doble caiga o cambie de estado a mitad de una prueba, se agrega al servidor de dobles un control **solo de pruebas**, con su caso en la prueba de Python de U10-T03.
  - El recorrido cubre cada vista y cada diálogo que entra, con los cuatro roles: bandeja, detalle (en los estados `listo`, `en_sincronizacion`, `decidido` y `modelo_congelado`), panel de explicación, formulario y diálogo de confirmación de la decisión, modelos, detalle de modelo, congelamientos, paquete de contexto, `ResolveFrozenDialog`, `StepUpDialog`, `InactivityDialog`, el marcador, «sin acceso» y `ProblemMessage`.
  - El listener de `securitypolicyviolation` se instala antes de cargar la página y la prueba exige **cero** eventos al final de cada recorrido. `axe` corre en cada parada y exige cero `serious` y `critical`.
  - `workers` de Playwright acotado (2 como máximo): la máquina es compartida.
- **Paso 16.**
  - Umbrales en la configuración de vitest: 100 % de ramas en `src/stepup/**` (ya puesto) y en el archivo de la validación de la decisión; ≥ 80 % de ramas en el resto de `src/`. Ningún archivo de `src/` queda fuera con `exclude` para llegar al número; si alguno se excluye, `spa.md` dice cuál y por qué.
  - NFR-U10-62: PBT-U10-04 imprime su semilla y usa los perfiles `ci` y `nightly` que dejó U10-T03.
  - `spa.md` (lo creó U10-T03 con su mitad) queda completo: módulos y qué regla cubre cada uno; la tabla de rutas por rol y cuáles llevan marcador; lo diferido de los Pasos 10 a 16 con su cita; cómo correr la SPA con Vite y los dobles; las respuestas a las preguntas de las dos tareas; y lo que queda para U10-T05 (imagen, `nginx.conf`, `config.json` del chart, `version`).
- **`make -C console check`.** El objetivo de Playwright que dejó U10-T03 (la PoC) pasa a construir, correr `size-limit` y correr también `tests/e2e`, `tests/csp` y `tests/a11y` en los dos navegadores (plan, Paso 24: «las de Playwright con dobles»). `test-spa` corre con los umbrales completos. Todo en serie.
- **Trazabilidad.** Cada identificador que citan los Pasos 13 a 16 queda trazado en el código o en sus pruebas (`DECISIONES-LOOP.md` §6, enmienda del 2026-11-09).
  - Hoy (`main` en `7d05454`) fallan **30** identificadores de `console`; U10-T03 deja trazados 9 y la base de esta rama debe traer **21**.
  - Esta tarea debe dejar trazados **6**: P-U10-08; NFR-U10-03, 42, 50, 51 y 63. Quedan 15.
  - **Trampa:** `test_traceability.py` no lee archivos `.mjs`: cita los identificadores en un `.ts`, `.tsx` o `.json`.
  - Los 15 que quedan son de U10-T05 o están diferidos: INF-U10-02, 04, 05 y 06; NFR-U10-01, 04, 10, 12, 20, 21, 22, 44 y 45; P-U10-06 y 10.
- **Plan.** Marca `[x]` los Pasos 13 a 16, con `(U10-T04)` y «parcial: ver `tareas/U10-T04-spa-vistas-y-e2e.md`».
- **Bitácora.** `bitacoras/U10-T04.md` lleva la salida **real** de cada comando, pegada como texto y con rutas absolutas a los logs. **Junto a toda medida de tiempo va `uptime`**, antes y después: duración de `make check`, de cada corrida de Playwright, el «< 1 s» del foco y cualquier timeout que falle.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Primera mitad del Bloque E, Pasos 10 a 12 (U10-T03)**: la puerta, `auth`, `stepup`, `inactivity`, `api`, `i18n`, `reporter`, el emisor OIDC de prueba y las candidatas de ESLint. Aquí no se reescriben; solo se usan, se amplían donde «Precisiones» lo dice y se corrigen según P-5.
- **Lo diferido por el recorte en estos pasos**, con su cita arriba: `ManualApplicationForm`, `PersistentFailures` y `retry`, `ApplicantSummaryButton`, `Dossier` (y su librería de PDF) e `IntegrityCheck`; `Policies`, `DataSources`, `PrePostReportView`, `DecideDataSourceDialog`, `RegisterModelForm`, `ApproveModelDialog`, el retiro y `GrafanaEmbed`; `BiasDashboard` (decidido); `version` y `VersionBanner` (§3, fila «12»); Stryker. De cada vista queda solo su ruta con el marcador.
- **Bloque F y el cierre (U10-T05)**: `Dockerfile` y `nginx.conf` de la SPA, con las etapas `previous` (Paso 17); el chart, el `ConfigMap` de `config.json` y sus `conftest` (Paso 18); k6, Lighthouse CI y la trazabilidad de cada BR con su lista de diferidos (Paso 21); `console/README.md` (Paso 23); el cierre y `evidence/cierre-demo.md` (Paso 24).
- **Candidata «`console/bff/tests/integration/test_clients.py:408-438` … F-01, NARANJA» (pool agotado; `CANDIDATAS.md`, línea 552): va a U10-T05.** Es una prueba de Python del BFF; no se arregla aquí.
- **Las demás candidatas de U10-T02 sobre el BFF**: puertos fijos de `test_service_shutdown.py` (F-02), `page_size` de `get_disparity` (F-03), `principal_role`, P-2, P-3, P-6, P-7 y P-8. Ninguna se toca.
- **La medida «bandeja → detalle p75 ≤ 1 s» y Lighthouse** (NFR-U10-04): son de los Pasos 21 y 22.
- **Pasos 19 y 20, diferidos** (§3, fila «19 · 20»: D): no hay `console.yml`; la puerta es `make -C console check`.
- **Paso 22**, consolidado en U12 Paso 18 (enmienda §8): Playwright con Keycloak real, NVDA y la lista manual de accesibilidad.
- **Cambios al BFF, a U0 o a U2.** No se toca `console/bff/src/`, ni `contracts/` (tampoco `contracts/ts`: ni arreglos nuevos ni un campo `disclaimer`), ni `identity-edge/` (la CSP se lee, no se cambia). Si la CSP de U2 no deja pasar algo de la SPA, se cambia la SPA y, si no hay forma, se reporta.
- **Excepciones a la CSP o al lint**: nada de `'unsafe-inline'`, de `// eslint-disable` para `react/no-danger`, almacenamiento o literales, ni de políticas de Trusted Types (`trusted-types 'none'`).
- **Estado fuera de la memoria**: nada en `localStorage`, `sessionStorage`, cookies ni IndexedDB. Sin WebSockets ni SSE (tech-stack §3).

---

## Archivos de contexto

- `tareas/U10-T03-spa-acceso-y-base.md`, `bitacoras/U10-T03.md` y `revisiones/U10-T03/` (qué quedó hecho y qué se decidió)
- `aidlc-docs/construction/console/code/spa.md` (U10-T03: módulos, dobles y cómo correrlos), `bff-api.md` y `bff-logic.md`
- `aidlc-docs/construction/plans/console-code-generation-plan.md` (§1 «Estructura de destino», Bloque E: Pasos 13 a 16, §3)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1.0 punto 4, §1.1, §1.2, §1.5, §2, §3 U10, §4, §5.2, §6 P-14, P-16 y P-17, §8)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§6, RL-1 a RL-5)
- `aidlc-docs/construction/console/functional-design/business-rules.md` (BR-U10-03, 07 a 16, 19)
- `aidlc-docs/construction/console/functional-design/business-logic-model.md` (§2.3, §3: PBT-U10-04 y los ejemplos)
- `aidlc-docs/construction/console/functional-design/frontend-components.md` (entero)
- `aidlc-docs/construction/console/functional-design/domain-entities.md` (§2, §3)
- `aidlc-docs/construction/console/nfr-requirements/nfr-requirements.md` (NFR-U10-03, 32, 41, 42, 43, 50, 51, 52, 61, 62, 63) y `tech-stack-decisions.md` (§2, §3)
- `aidlc-docs/construction/console/nfr-design/nfr-design-patterns.md` (P-U10-08 y §5, E1 y E3)
- `aidlc-docs/inception/application-design/component-methods.md` (C03: columnas «Roles» y «MFA»)
- `console/Makefile`, `console/spa/{package.json,vite.config.ts,playwright.config.ts,eslint.config.mjs,.size-limit.json,index.html}`
- `console/spa/src/` entero (lo de U10-T03) y `console/spa/src/config/constants.ts`
- `console/bff/tests/doubles/` (dobles de U10-T02; emisor y servidor del e2e de U10-T03)
- `contracts/ts/src/{index,enums.generated,decimal}.ts` y `contracts/ts/src/generated/console-bff.d.ts`
- `contracts/openapi/console-bff.yaml` y `contracts/openapi/role-endpoint-matrix.md`
- `contracts/tools/forbidden_phrases.py` y `contracts/forbidden-phrases.yaml`
- `contracts/python/vectra_contracts/src/vectra_contracts/validation.py` (`check_used_factors`, `check_justification`, `decision_is_coherent`) y `models/{api,monitoring,governance}.py` (`DecisionIn`, `CaseDetail`, `FreezeRecord`, `CellResult`, `FrozenResolutionIn`)
- `case-management/tests/property/test_decision.py` (PBT-U8-03: `COHERENT` y `oracle`) y `case-management/src/vectra_case/decision.py`
- `bias-monitoring/src/vectra_bias/dashboard.py` (`DISCLAIMER`)
- `identity-edge/gateway/routes.yaml` (perfil `spa`)
- `package.json` raíz y `package-lock.json`
- `DECISIONES-LOOP.md` (§6) y `CANDIDATAS.md` (línea 552 y las que agregó U10-T03)

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`, **en serie**, anotando `uptime` antes y después. Antes del primero: `npm ci --ignore-scripts`.

Estado al redactar (2026-11-12, `origin/main` en `7d05454`, con U10-T02 fusionada y **sin** U10-T03):
- **CA-8 se corrió** con `python3 -B platform/tests/test_traceability.py --unit console --all`: 30 líneas «sin trazabilidad», que incluyen las 6 de esta tarea y las 9 de U10-T03.
- **Comprobado con comandos de solo lectura:** `src/views/` solo tiene `.gitkeep`; `tests/csp` y `tests/a11y` están vacíos; **`tests/e2e` ya no lo está:** U10-T03 dejó ahí `auth.spec.ts` (login por redirección, recarga con `prompt=none` y logout, exigido por el arbitraje de su ronda 1), `vite.e2e.config.ts` y un segundo par de servidor y dobles en `playwright.config.ts`; esta tarea los conserva, los amplía y borra el `.gitkeep`; React Router, `@axe-core/playwright` y `size-limit` no están en `package-lock.json`; `.size-limit.json` es `[]`; no existe `playwright.config.ts` ni `spa.md`.
- **No se corrieron** los demás (el worktree de redacción no tiene `node_modules`). Por lo anterior, hoy fallan porque el código no existe: CA-1 a CA-5 y CA-7. La mitad de ellos seguirá fallando con U10-T03 fusionada, que es el rojo esperado al despachar.
- CA-6 y CA-9 pasarán al despachar con lo de U10-T03 y deben seguir pasando.

- [ ] **CA-1** — Vistas de casos (Paso 13; BR-U10-07 a 11; US-102, 104, 106 a 110, 501, 502).
  ```bash
  npm run -w console/spa test -- views/cases
  ```
  Esperado: código 0, con la semilla impresa. PBT-U10-04 entera (P-2) y los ejemplos que entran: bandeja sin `vencido` por omisión y con el filtro; `free_text` con `<script>alert(1)</script>` como texto (el DOM no tiene ningún `script` nuevo); `no_integrado`; baja confianza y `revision_requerida`; `decision_already_recorded` con aviso y recarga; el panel con una sola llamada y ninguna sin abrirlo; `cro` abre el panel sin llamada; la URL de la bandeja sin datos del solicitante; el botón deshabilitado en curso (dos clics → una solicitud); el refresco de la bandeja no reinicia el contador de inactividad. **Rojo primero:** con `trim()` quitado del contador de la justificación, PBT-U10-04 falla; con la guarda de rol quitada, el caso de `cro` falla.

- [ ] **CA-2** — Vistas de gobierno y rutas por rol (Paso 14; BR-U10-12, 13, 15; US-304, 305, 602).
  ```bash
  npm run -w console/spa test -- views/governance views/bias
  ```
  Esperado: código 0. Casos:
  - cada ruta de la tabla, las diferidas incluidas, coincide con «Roles» de C03; `cro` no ve el paquete de contexto y `cumplimiento` no ve la bandeja;
  - «sin acceso» y el marcador, con cero solicitudes al BFF;
  - una celda `muestra_insuficiente` muestra ese texto, nunca `0`, vacío ni una tasa;
  - el `disclaimer` presente en `FreezeContextView` en todos sus estados, también con `before = "sin_datos"`;
  - el aviso de `reactivar`; justificación obligatoria en las tres acciones;
  - `ResolveFrozenDialog` con el token sin MFA reciente → «Verificar y confirmar»; con un 403 `mfa_required` inesperado → `StepUpDialog`, y un reintento con la misma justificación → 200.

  **Rojo primero:** con `cro` agregado a la ruta de `FreezeContextView`, la comparación con C03 falla y nombra la ruta.

- [ ] **CA-3** — CSP, accesibilidad y extremo a extremo con dobles (Paso 15; NFR-U10-32, 41, 42, 50, 51, 52, 63; P-U10-08; US-611).
  ```bash
  uptime; npx playwright test -c console/spa/playwright.config.ts tests/e2e tests/csp tests/a11y --project=chromium --project=firefox --reporter=list; echo "rc=$?"; uptime
  ```
  Esperado: `rc=0` en los dos navegadores y sin pruebas saltadas. Cero eventos `securitypolicyviolation` y cero hallazgos `serious` o `critical` de `axe` en el recorrido de «Precisiones». La cabecera `Content-Security-Policy` que recibe el navegador es, carácter por carácter, la del perfil `spa` de `identity-edge/gateway/routes.yaml` (una prueba las compara). Más las líneas «(de esta tarea)» del Paso 15: dos pestañas, el foco en < 1 s y los dobles de bias y de case caídos. **Rojo primero:** con un `style="…"` en línea en un componente, la prueba de CSP registra una violación y falla; con un botón sin nombre accesible, la de `axe` falla.

- [ ] **CA-4** — El build: sin código en línea, sin polyfill y dentro del presupuesto (Paso 15; NFR-U10-03; P-U10-08).
  ```bash
  npm run -w console/spa build && ! grep -nE "<script(>| [^>]*>)[^<]|<style|modulepreload-polyfill" console/spa/dist/index.html && ! grep -rlE "tests/poc|eslint-fixtures" console/spa/dist && npm exec -w console/spa -- size-limit; echo "rc=$?"
  ```
  Esperado: `rc=0`. `dist/index.html` solo tiene `<script type="module" src=…>` y `<link rel="stylesheet">`, sin cuerpo en línea; `dist/` no trae nada de la PoC; `size-limit` informa el tamaño con gzip, menor que 250 KiB. Si el script `build` no existe con ese nombre o el `grep` no casa con la forma real del HTML, se ajusta y se anota; lo que no cambia es la condición. **Rojo primero:** con `build.modulePreload.polyfill` en su valor por omisión, o con las vistas importadas de forma estática, se anota qué cambia (el polyfill aparece; el tamaño inicial sube).

- [ ] **CA-5** — Cobertura completa (Paso 16; NFR-U10-61, 62).
  ```bash
  npm run -w console/spa test -- --coverage
  ```
  Esperado: código 0, con los umbrales en la configuración de vitest: 100 % de ramas en `src/stepup/**` y en el archivo de la validación de la decisión; ≥ 80 % en el resto. La bitácora pega la tabla por archivo. **Rojo primero:** con un caso de la validación de la decisión quitado, el comando sale distinto de 0 y nombra el archivo.

- [ ] **CA-6** — Lo de U10-T03 sigue en pie: lint, tipos, PBT-U10-05 y 06, textos y la puerta.
  ```bash
  npm run -w console/spa lint && npm run -w console/spa typecheck && npm run -w console/spa test -- auth stepup inactivity api i18n reporter eslint && uv run python contracts/tools/forbidden_phrases.py console/spa/src/i18n/*.json && ! grep -rnE "eslint-disable|dangerouslySetInnerHTML|localStorage|sessionStorage" console/spa/src && npx playwright test -c console/spa/playwright.config.ts tests/poc --project=chromium --project=firefox --reporter=list; echo "rc=$?"
  ```
  Esperado: `rc=0`, el `grep` sin salida y ninguna «frase prohibida», con las claves nuevas del catálogo incluidas. La PoC pasa igual que en U10-T03 (con la misma excepción de su P-2, si la hubo).

- [ ] **CA-7** — Documentación, plan y estructura.
  ```bash
  grep -cE "^- \[x\] \*\*Paso 1[0-6] " aidlc-docs/construction/plans/console-code-generation-plan.md; grep -cE "^- \[x\] \*\*Paso 1[3-6] .*U10-T04" aidlc-docs/construction/plans/console-code-generation-plan.md; grep -c "U10-T04" aidlc-docs/construction/console/code/spa.md; for d in views/cases views/governance views/shared; do test -n "$(find console/spa/src/$d -type f ! -name .gitkeep | head -1)" || echo "VACIO $d"; done; for d in e2e csp a11y; do test -n "$(find console/spa/tests/$d -type f ! -name .gitkeep | head -1)" || echo "VACIO tests/$d"; done; test ! -e console/spa/stryker.conf.json && test ! -e console/spa/Dockerfile && test ! -e console/spa/nginx.conf && echo OK
  ```
  Esperado: imprime `7` (los siete pasos del Bloque E marcados), `4` (los de esta tarea, con `(U10-T04)`), un número mayor que 0 (`spa.md` nombra esta tarea en su resumen), ninguna línea `VACIO`, y `OK`. Si la marca no queda en la misma línea del paso, el `grep` se ajusta y se anota.

- [ ] **CA-8** — Trazabilidad, con la regla «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).
  ```bash
  uv run python platform/tests/test_traceability.py --unit console --all | grep -E "^(P-U10-08|NFR-U10-(03|42|50|51|63)):" ; uv run python platform/tests/test_traceability.py --unit console --all | grep -c "sin trazabilidad"; uv run python platform/tests/test_traceability.py --all | grep "sin trazabilidad" | sort > /tmp/u10-t04-rama.txt
  ```
  Esperado: el primer `grep` no imprime nada y el conteo de `console` baja de 21 (la base, con U10-T03) a **15**. El archivo se compara con la misma corrida sobre la base de la rama: no hay ninguna línea nueva y las 6 de arriba ya no están. El revisor corre `--all` en la base y en la rama. Si la base no trae 21, se anota cuáles sobran y por qué antes de seguir.

- [ ] **CA-9** — `check` de la unidad (RL-4) y de U0, porque el diff cambia el lockfile de npm.
  ```bash
  uptime; make -C console check; echo "console rc=$?"; uptime; make -C contracts check; echo "contracts rc=$?"; uptime; npm audit --audit-level=high; echo "audit rc=$?"
  ```
  Esperado: `rc=0` en los tres, **en serie**. `console check` incluye ya el build, `size-limit` y Playwright con dobles (PoC, e2e, CSP y accesibilidad). Si `bench_gate` de `contracts` falla por carga, se anota con la carga y una corrida aislada en la rama y en la base.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `console/spa/tests/unit/views/cases/` y `console/spa/tests/property/views/cases/` (PBT-U10-04 y la propiedad de la URL).
- `console/spa/tests/unit/views/governance/` y `views/bias/`: rutas por rol contra C03, modelos de lectura, congelamientos, celdas insuficientes y `ResolveFrozenDialog`.
- `console/spa/tests/e2e/`, `tests/csp/` y `tests/a11y/`: el recorrido de «Precisiones», las cabeceras, dos pestañas, el foco y los dobles caídos.
- Los casos que hagan falta en la prueba de Python del servidor de dobles, si se le agrega un control.
- Una prueba de `browserslist` y `build.target`, y la del texto del `disclaimer` (P-4).
- **Rojo primero:** antes de cada arreglo, el codificador reproduce el fallo y lo registra en `bitacoras/U10-T04.md`, con la salida pegada. Como mínimo los de CA-1 (`trim` y rol), CA-2 (rol de más), CA-3 (estilo en línea y botón sin nombre) y CA-5 (caso quitado). El par falla-pasa es la prueba.

Reglas de las pruebas:
- Reloj simulado en vitest para todo lo que espera (15 s, 3 s, 2 min). Ninguna prueba unitaria duerme de verdad.
- En Playwright no hay `waitForTimeout` fijo: se espera por estado. El único tiempo real medido es el «< 1 s» del foco.
- Los nombres de los módulos de prueba de Python nuevos llevan el prefijo `bff_` (candidata F-06 de U07-T03).

---

## Preguntas abiertas

**Ya decidido por el usuario (2026-11-12), no es pregunta:** el Bloque E se parte en 10–12 y 13–16; `BiasDashboard` queda diferido con el marcador; los navegadores de Playwright se instalan con `npx playwright install chromium firefox`.

Ninguna de las que siguen necesita decisión previa: si no hay respuesta, rige la recomendación.

- **P-1 — El informe de validación en `ModelDetail`.** §1.5 lista `ValidationReportView` entre lo que ninguna demo usa, pero la fila «14» de §3 **no** la nombra entre lo diferido y deja entrar «`Models`/`ModelDetail` de lectura»; C03 dice que `get_model` «incluye el informe de validación».
  - **(a) Recomendada:** `ModelDetail` muestra el informe que trae `get_model`, en modo lectura y sin componente aparte elaborado. La tabla §3 es la que manda y no lo difiere.
  - (b) Diferirlo con las demás vistas de modelos. Hay que agregarlo a la fila «14».
- **P-2 — El oráculo de PBT-U10-04 entre dos lenguajes.** El plan pide «mismo oráculo que PBT-U8-03», que está en Python (`case-management/tests/property/test_decision.py`: la tabla `COHERENT` y `oracle`).
  - **(a) Recomendada:** el oráculo se transcribe a TypeScript, aparte de la implementación y con la cita, con los mismos generadores (largos 0, 1, 19, 20, 21, 1999, 2000 y 2001 con espacios en los bordes; subconjuntos, ajenos, `ninguno` solo, combinado y repetidos). Una prueba lee el archivo de Python como texto y exige que las 18 filas de `COHERENT` sean las mismas. La propiedad es: el cliente acepta ⇔ el oráculo devuelve «acepta» (ni 422 ni 409).
  - (b) Vectores generados desde Python y versionados. La consola pasaría a importar `vectra_case` en sus pruebas, que es otra unidad.
- **P-3 — Contra qué servidor corre el Paso 15.** El plan dice «la SPA de Vite». El servidor de desarrollo de Vite inyecta código en línea (el preámbulo de React Refresh y HMR), que la CSP de U2 bloquea: daría violaciones que no son de la SPA.
  - **(a) Recomendada:** `vite build` y `vite preview`, con las cabeceras del perfil `spa` leídas de `routes.yaml`. Es lo que de verdad se despliega.
  - (b) El servidor de desarrollo con una CSP relajada. Deja de probar la CSP de U2.
- **P-4 — El `disclaimer` de `FreezeContextView`.** BR-U10-13 dice que la vista «siempre lleva el `disclaimer`», pero `FreezeRecord` no trae ese campo (lo traen `DisparityView` y `PrePostReport`).
  - **(a) Recomendada:** un texto propio del catálogo, igual a `DISCLAIMER` de `bias-monitoring/src/vectra_bias/dashboard.py` («mide y alerta, no certifica»), con una prueba que lee ese archivo como texto y los compara. Queda como candidata de U0 (el campo en el paquete).
  - (b) Agregar el campo al contrato. Es un cambio de U0 y de U9.
- **P-5 — Un defecto de U10-T03 que aparece aquí.** El recorrido con la CSP, `axe` y dos navegadores es la primera vez que `auth`, `stepup`, `inactivity` y `reporter` corren en un navegador real con las vistas: puede destapar un estilo en línea, un foco que no vuelve o un diálogo sin nombre accesible.
  - **(a) Recomendada:** se corrige aquí, en su archivo, con su prueba y su rojo, sin cambiar el diseño de P-U10-07 y manteniendo el 100 % de `stepup`; se anota en la bitácora como «defecto de U10-T03» con el caso que lo destapó. Si el arreglo exige cambiar el flujo del step-up (la puerta), se para y se reporta.
  - (b) Reportarlo como candidata y dejar la prueba en `fixme`. El Paso 15 quedaría sin cumplir.

---

## Notas

- **Orden de trabajo.** (1) dependencias, enrutador, `Layout`, tabla de rutas y marcador; (2) Paso 13; (3) Paso 14; (4) Paso 15: primero la CSP sobre el build, que es donde más sorpresas hay; (5) Paso 16 y `check`.
- Archivos que se **modifican en su sitio**:
  - `console/spa/{package.json,vite.config.ts,playwright.config.ts,.size-limit.json,index.html}`, `App.tsx` y la entrada de U10-T03, `console/spa/src/i18n/{messages,labels}.es.json` y, solo según «Precisiones» o P-5, otros archivos de `src/` de U10-T03;
  - `console/bff/tests/doubles/` (solo el control de pruebas del servidor, si hace falta) y su prueba;
  - `package-lock.json` raíz, y `package.json` raíz solo si hace falta un `override`;
  - `console/Makefile`;
  - `aidlc-docs/construction/plans/console-code-generation-plan.md` (casillas) y `aidlc-docs/construction/console/code/spa.md`;
  - `CANDIDATAS.md`.

  Nada de duplicados con sufijo. `console/bff/src/` no cambia.
- **Candidatas de `CANDIDATAS.md`.** Esta tarea no atiende ninguna de las que existen hoy: las de ESLint y la del timeout de `eslint.test.ts` son de U10-T03, y la del «pool agotado» (línea 552) va a U10-T05. Las candidatas nuevas (P-4 y lo que aparezca) se agregan al final.
- **Trampas conocidas.**
  - `tech-stack-decisions.md` §2 dice «React 18», pero `main` tiene React 19.3.1 desde U10-T01. Se sigue con 19; comprueba que React Router lo admite antes de fijar la versión.
  - La CSP de U2 trae `frame-src 'self'` y `connect-src 'self'`: el login silencioso y el emisor tienen que estar en el mismo origen. `require-trusted-types-for 'script'` con `trusted-types 'none'` hace fallar cualquier `innerHTML`, también el de una librería.
  - `React.lazy` y CSS Modules generan `<link>` y `import()`; ninguno puede acabar como estilo o script en línea. Las animaciones de una librería que escriben `style` en línea violan `style-src 'self'`.
  - Python y JavaScript no cuentan igual: `str.strip()` y `trim()` no quitan exactamente los mismos caracteres, y `len()` cuenta puntos de código donde `.length` cuenta unidades UTF-16. `DecisionIn` además rechaza una justificación de más de 2000 caracteres **antes** de recortar. PBT-U10-04 debe generar esos casos (un emoji, espacios raros, 2001 con bordes) y la validación del cliente debe contar como el servidor.
  - TanStack Query: U10-T03 lo dejó sin reintentos y sin refresco al volver el foco. Los refrescos de 15 s y de 3 s van con `refetchInterval`, no cambiando esos valores.
  - La bandeja se refresca «mientras la pestaña está visible»: en Playwright una pestaña en segundo plano cuenta como oculta; tenlo en cuenta en la prueba de dos pestañas.
  - `test_u10_candidates.py` (U10-T02) lee la línea `export const API_TIMEOUT_SECONDS = 10;` de `constants.ts`: no cambies su forma.
  - Bajo carga, Playwright en dos navegadores tarda. Un timeout se anota con `uptime` y se repite aislado; no se suben los tiempos de espera sin anotarlo.
- PBT-U10-01..06 nunca se recortan. En esta tarea entra la 04, entera. La 01 (U10-T02), la 02 y la 03 (U10-T01) y la 05 y la 06 (U10-T03) ya están.
- Máquina compartida (8 núcleos, 14 GiB, varios agentes a la vez): las suites largas (`make -C console check`, `make -C contracts check`, Playwright y la cobertura) van **en serie**, nunca dos a la vez, con `uptime` antes y después. Si una corrida pasa más de 2 horas sin avanzar, se detiene, se anota y se repite.
