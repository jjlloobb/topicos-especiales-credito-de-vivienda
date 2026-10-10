# Reglas de negocio — U10 `console`

Decisiones del plan (`console-functional-design-plan.md`, Q1–Q12 = A). Los IDs `BR-U10-xx`
se referencian en los planes de tareas. La UI **oculta**, pero **no protege** (FR-UI-07): toda
regla de acceso vive en el BFF y se vuelve a validar en el servicio de destino.

---

## 1. BFF (US-602, SECURITY-08)

**BR-U10-01 — Tres controles por endpoint, en orden.** Para cada uno de los 29 endpoints de
`component-methods.md` C03:
1. **función**: el rol del token está en la columna «Roles»; si no → 403 `forbidden`;
2. **MFA**: si la columna lo pide, `acr = mfa` y `auth_time` ≤ 900 s (BR-U0-72); si no → 403 `mfa_required`;
3. **objeto**: la regla de la columna «Objeto» (por ejemplo, `record_decision` solo con el caso `listo` → si no, 409).

Cada 401 o 403 emite `authz.denied` con `principal_subject` y la métrica de BR-U0-73. Después
el BFF propaga el token del usuario y el `correlation_id` al servicio de destino, que vuelve a
validar rol y objeto.

**BR-U10-02 — Sin estado.** El BFF no guarda datos ni sesiones: compone respuestas de case,
governance, registry, explainability y bias (F10–F14). Las únicas cachés son las de los
servicios de destino.

**BR-U10-03 — Composiciones del BFF.**
- `get_disparity`: primero `list_models(state=activo,congelado)` en governance (F11), para obtener la versión **servible**, y después `get_dashboard` de bias con esa versión (U9 BR-U9-18).
- `get_dossier` (Q11; precisado en la revisión del Infrastructure Design de U10, 2026-10-10): `get_case_dossier` del registro más `get_case_identifiers` de case-service (U8, `GET /v1/cases/{id}/identifiers`, roles `cro` y `cumplimiento`; `get_case` no sirve porque `cumplimiento` no tiene acceso a la bandeja), unidos por `case_id`:
  - registro sin respuesta → 503;
  - case-service sin respuesta (timeout, conexión, 5xx o circuito abierto) → expediente **sin** identificadores y con `identifiers_unavailable = true`;
  - case-service responde 403 o 404 → el BFF responde ese mismo error, porque es una falla de autorización o de datos, no una caída;
  - caso anonimizado → sin identificadores y con `anonymized = true`.
- Las demás operaciones son de paso: un endpoint del BFF, un servicio de destino.

**BR-U10-04 — Errores genéricos** (SECURITY-15, US-611). El BFF devuelve el `Problem` de U0
(`code`, `reason?`, `correlation_id`) sin `detail` ni trazas. Un error del servicio de destino
se traduce a su `code`; un error inesperado → 500 `internal_error`.

## 2. Sesión y tokens en la SPA (Q1, Q2; SECURITY-12)

**BR-U10-05 — Tokens solo en memoria.**
- El access token y el refresh token viven solo en la memoria de la SPA. Nunca en `localStorage`, `sessionStorage`, cookies legibles por JavaScript ni la URL.
- El refresh rota en cada uso y se revoca si se reusa (BR-U2-06).
- Recargar la página o abrir otra pestaña hace un login silencioso (`prompt=none`) contra la sesión de Keycloak. Si no hay sesión, se muestra el login.
- Logout: borra la memoria y llama al `end_session_endpoint` de Keycloak.

**BR-U10-06 — Step-up a mitad de una acción** (Q2; BR-U2-04). Se hace en una **ventana
emergente**, para que la ventana principal no se recargue y el cuerpo del formulario siga en
memoria. Una redirección completa recargaría la SPA y lo borraría (revisión del FD de U10, 2026-10-10), A1.
- **Activación del usuario** (revisión del Infrastructure Design de U10, 2026-10-10): los navegadores bloquean un `window.open` que no sale directamente de un clic. Por eso la ventana se abre siempre dentro del manejador de un clic:
  - si el token ya muestra que falta MFA reciente (`acr ≠ mfa` o `auth_time` de hace más de 900 s, leídos de `SessionInfo`), el botón de confirmación de una acción con MFA dice «Verificar y confirmar» y abre la ventana en el mismo clic, antes de enviar;
  - si el BFF responde de todos modos 403 `mfa_required` (por ejemplo, porque el plazo venció entre la lectura y el envío), la SPA muestra un diálogo con el botón «Verificar identidad», que abre la ventana en su clic.
- Al abrir la ventana, la SPA genera en memoria `state`, `nonce` y el `code_verifier` de PKCE, y abre con `window.open` el endpoint de autorización de Keycloak (`/auth/...`, mismo origen) con `prompt=login`, `max_age=0` y `acr_values=mfa`. El `redirect_uri` es `/stepup-callback` de la SPA.
- La página `/stepup-callback` **no** canjea el código ni guarda nada. Envía `{code, state}` a `window.opener` con `postMessage(msg, location.origin)` y se cierra.
- La ventana principal acepta el mensaje solo si `event.origin` es su propio origen, `event.source` es la ventana que abrió y el `state` coincide. Después canjea el código con el `code_verifier`, valida el `nonce` del ID token y que `acr = mfa`, reemplaza los tokens en memoria y reintenta la acción **una sola vez** con el mismo cuerpo.
- Si la ventana fue bloqueada, se cerró sin responder o no respondió en 5 min, no hay reintento. El formulario sigue con su contenido y muestra «la verificación no se completó; vuelve a confirmar la acción».
- Si el reintento falla, se muestra el error y no se reintenta.
- Al terminar, el `state`, el `nonce` y el `code_verifier` se borran siempre. Nada del step-up toca `sessionStorage`, `localStorage` ni la URL de la ventana principal.
- Funciona porque la SPA y Keycloak comparten el origen (U2 INF: un solo origen). Si U2 agregara `Cross-Origin-Opener-Policy`, debe ser `same-origin`, que mantiene `window.opener` entre páginas del mismo origen.

## 3. Casos (Q3–Q6; US-102, 104, 106, 107, 108, 109, 110, 112, 501, 502)

**BR-U10-07 — Estado de crédito** (Q3; resuelve el pendiente de U8 INF-U8-02). `credit_status`
suma el valor **`no_integrado`**, que case-service devuelve con `core.enabled = false`.
`no_disponible` queda solo para el core caído o lento. La consola muestra «Estado de crédito
no integrado» o «Estado de crédito no disponible por ahora».

**BR-U10-08 — Consulta de la explicación** (Q4; US-501, BR-U8-19).
- El detalle de un caso `listo` o `decidido` muestra el resultado (`outcome`, score, marcas de baja confianza y de `revision_requerida`). La narrativa y los factores están en un panel que se abre con el botón «Ver explicación».
- Abrir el panel llama a `record_explanation_view` una vez por sesión de vista del caso. U8 garantiza una sola entrada por (caso, usuario).
- Si la llamada falla, el panel se muestra igual y el error se registra; la consulta queda pendiente en U8 (BR-U8-18).
- Abrir el detalle sin abrir el panel **no** cuenta como consulta.

**BR-U10-09 — Formulario de decisión** (Q5; BR-U8-16, BR-U0-35, 36).
- Opciones: `sigue` y `se_aparta`, y además `resuelve_revision` solo si el `outcome` es `revision_requerida`.
- **Factores usados**: lista de los `feature_id` del `shap_vector`, con su etiqueta en español y en el orden de la narrativa, o la casilla exclusiva «Ninguno».
- **Justificación**: obligatoria en `se_aparta` y `resuelve_revision`, con un contador de 20 a 2000 caracteres que cuenta igual que el servidor (sin espacios en los bordes).
- En `se_aparta`, `final_outcome` se elige explícitamente y es distinto del de la recomendación.
- Un diálogo de confirmación resume la decisión antes de enviarla. El botón queda deshabilitado mientras la solicitud está en curso.
- La validación del cliente usa las mismas reglas, pero decide el servidor. Un 422 se muestra en su campo (`invalid_params`); un 409 `decision_already_recorded` muestra el aviso y recarga el caso con la decisión registrada.

**BR-U10-09b — Decisión sin step-up** (revisión del Infrastructure Design de U10, 2026-10-10, Q1 = A). `record_decision` no exige MFA
reciente: la decisión es una recomendación humana sobre un caso, no la aprobación de un artefacto
que cambia el sistema, y el analista decide decenas de casos por jornada. **Corrección** (segunda revisión del Infrastructure Design de U10, 2026-10-10): la
pregunta decía que el login del analista ya exige TOTP, y no es así: para `analista` el MFA es
«disponible, no obligatorio» (U2 domain-entities §1.1), así que una decisión puede registrarse con
`acr = pwd`. La entrada `human_decision` guarda `acr` y `auth_time` como evidencia (U8 BR-U8-18, U3 BR-U3-16 y U0 §5.1 lo exigen para todo actor de usuario; segunda revisión del Infrastructure Design de U10, 2026-10-10). **[VERIFICAR]** con
cumplimiento y el comité: es una decisión de negocio que deben confirmar.

**BR-U10-10 — Bandeja y refresco** (Q6; US-107, NFR-PER-01).
- **Filtros** (`CaseFilter` de U0): estado (por omisión, todos menos `vencido`, que se ve con el filtro explícito), canal, fecha de creación y «modelo congelado tras la recomendación» (`model_frozen_after_recommendation`). Ninguno lleva datos del solicitante, así que todos pueden ir en la URL.
- **Sin búsqueda por nombre** (revisión del FD de U10, 2026-10-10), A3: buscar por `applicant_display` pondría el nombre en la URL, el historial y los logs de acceso. Ninguna historia lo pide. El campo «Ir al caso» acepta un `case_id` (UUID, que no es un dato personal) y abre el detalle directamente.
- **Orden y página**: por `created_at`, con paginación del servidor (páginas de ≤ 100).
- **Refresco**: la bandeja se vuelve a pedir cada 15 s mientras la pestaña está visible. El detalle de un caso `en_evaluacion` o `en_sincronizacion` se pide cada 3 s hasta que cambia de estado, con un máximo de 2 min. Sin WebSockets.
- Los estados se muestran con color **y** texto, nunca solo con color.

**BR-U10-11 — Datos del solicitante en pantalla** (pendientes de U8 R1 y BR-U8-01).
- La bandeja identifica al solicitante solo con `applicant_display`.
- El detalle muestra la solicitud sin etiquetas de monitoreo (`sex`, `socioeconomic_stratum`).
- `free_text` se muestra **escapado**, como texto plano, nunca interpretado como HTML ni Markdown. En React, nunca con `dangerouslySetInnerHTML`; una regla de ESLint lo prohíbe en todo el proyecto.

## 4. Gobierno y vigilancia (Q9, Q10; US-201..206, 304..307)

**BR-U10-12 — Vistas por rol** (Q9; FR-UI-07, BR-U2-01). Un usuario tiene exactamente un rol de negocio.

La tabla sale de la columna «Roles» de `component-methods.md` C03, que manda (revisión del FD de U10, 2026-10-10), A2.
Una prueba compara las rutas de la SPA con C03 (BR-U10-19).

| Rol | Vistas (endpoints de C03) |
|---|---|
| `analista` | Bandeja y detalle (`list_cases`, `get_case`); alta manual; consulta de la explicación; decisión; resumen para el solicitante; políticas (lectura) |
| `ingeniero_riesgo` | Modelos (lista, detalle e informe; registro y validación, con MFA); fuentes (lista; propuesta y comparación, con MFA) |
| `cro` | Bandeja y detalle (sin decidir); resumen para el solicitante; fallos persistentes y `retry`; expediente; verificación de integridad (MFA); modelos (lectura y aprobación, con MFA); políticas (lectura, propuesta y aprobación, con MFA); fuentes (lectura); dashboard de sesgo; lista de congelamientos (sin el paquete de contexto) |
| `cumplimiento` | Expediente; modelos (lectura); resolución de un congelamiento (MFA); políticas (lectura); fuentes (lectura y decisión, con MFA); dashboard de sesgo; congelamientos (lista y paquete de contexto) |

El menú se arma con `get_me()`. Una ruta de la SPA a la que el rol no llega muestra «sin
acceso» sin llamar al BFF, pero cada endpoint lo valida igual.

**BR-U10-13 — Resolución de un congelamiento** (Q10; US-304, US-305).
- La vista muestra el paquete de contexto completo: antes, después, últimos 7 días, atributo disparador, grupos y bandas implicados, fuentes de datos y disparidad de validación. Siempre lleva el `disclaimer`.
- Las tres acciones (`reactivar`, `descartar`, `investigar`) exigen justificación y MFA.
- `reactivar` muestra además un aviso: la ventana de monitoreo empieza al día siguiente y habrá un periodo de «muestra insuficiente» (U9 §8b).

**BR-U10-14 — Decisión de una fuente** (Q10; US-306).
- La vista muestra el `PrePostReport`: por atributo, antes, después y la diferencia, con el `disclaimer`.
- `aprobar` y `rechazar` exigen justificación y MFA. Sin informe, los botones no aparecen, y el servidor responde 409 de todos modos.

**BR-U10-15 — Celdas insuficientes.** Una celda con «muestra insuficiente» se muestra así,
nunca como 0 ni vacía, y su tasa nunca se calcula en el cliente.

**BR-U10-16 — Dashboard embebido** (U9 INF-U9-05). La vista de sesgo embebe `bias.json` de
Grafana en un `iframe` del mismo origen (`/grafana/**`, perfil `grafana` de U2). Encima del
iframe, la leyenda «mide y alerta, no certifica» es un texto propio de la consola.

## 5. Textos (Q7, Q8; FR-BIA-08, SECURITY-15)

**BR-U10-17 — Catálogo cerrado de mensajes** (Q7).
- Hay un mensaje en español por cada `code` y cada `reason` del catálogo de U0 §6. Por ejemplo, `decision_already_recorded` → «Otra persona ya registró la decisión de este caso. Se muestra la decisión registrada.».
- Un `code` desconocido muestra un mensaje genérico con el `correlation_id` para soporte.
- Nunca se muestra el `detail` del servidor ni una traza.
- Los avisos de negocio también vienen del mismo catálogo: `model_frozen_after_recommendation`, baja confianza, `revision_requerida`, caso anonimizado y crédito no integrado.

**BR-U10-18 — Frases prohibidas** (Q8; FR-BIA-08). La lista, la comparación y la aprobación de
sus cambios son las de U0 BR-U0-94, que no se repiten aquí (revisión del Infrastructure Design de U10, 2026-10-10). U10 aplica
`contracts/tools/forbidden_phrases.py` a `messages.es.json`, `labels.es.json` y `console.json`.

## 6. Verificación de US-602 (Q12)

**BR-U10-19 — Matriz rol × endpoint.**
- Se genera desde el registro de contratos de U0 (`RouteContract`).
- Para cada uno de los 29 endpoints (27 del FD, `report_client_error` del NFR Requirements de U10, Q12, y `get_integrity_check` del NFR Design de U10, Q3), prueba los 4 roles, un token sin rol de negocio, uno expirado, uno con otra audiencia, uno con `acr = pwd` y uno con `acr = mfa` pero `auth_time` de hace más de 900 s (revisión del Infrastructure Design de U10, 2026-10-10). Según las columnas «Roles» y «MFA», espera 2xx, 401 (`unauthenticated`), 403 con `code = forbidden` o 403 con `code = mfa_required`. `mfa_required` es un 403 de U0 §6, no un estado aparte; la prueba compara el status y el `code` (revisión del FD de U10, 2026-10-10), B19.
- Las rutas de la SPA por rol (BR-U10-12) se comparan con la misma columna «Roles».
- Para cada endpoint con regla de objeto, agrega al menos un caso negativo.
- Cada 401 o 403 deja `authz.denied` con `principal_subject`.
- La matriz se publica como `role-endpoint-matrix.md` (U0, Paso 15) y se compara con `component-methods.md` C03.

## 6b. Sesión, versión y errores del navegador (absorbidos del NFR; revisión del Infrastructure Design de U10, 2026-10-10)

**BR-U10-20 — Inactividad** (NFR-U10-40, 41).
- Cuentan como actividad `keydown`, `pointerdown`, `focusin`, `wheel` y `scroll`. El refresco automático y las respuestas del BFF no cuentan.
- La inactividad es **de la sesión, no de la pestaña**: cada pestaña difunde un mensaje `activity` por `BroadcastChannel("vectra-console")` como máximo cada 30 s, y todas reinician su contador. Así, trabajar en una pestaña no cierra la sesión por otra que quedó quieta.
- A los 25 min sin actividad en ninguna pestaña, diálogo «tu sesión se cerrará en 5 min», con «seguir». A los 30 min, logout en todas las pestañas con el mensaje `logout` (sin datos).
- Un formulario sin enviar no evita el cierre.

**BR-U10-21 — Aviso de versión** (P-U10-06). La SPA consulta `version.json` cada 5 min. Si cambió,
muestra el aviso no bloqueante «hay una versión nueva; recarga cuando termines». Si falla la
carga de un fragmento, muestra el mensaje con un botón de recarga. Nunca recarga sola.

**BR-U10-22 — Errores del navegador** (NFR-U10-34, P-U10-09).
- El `reporter` de la SPA traduce cada error a un `error_code` del catálogo cerrado de `ClientErrorReport` (U0 §9.5) y lo envía a `report_client_error`, como máximo 10 por minuto por sesión.
- Nunca envía mensajes, trazas, la URL con parámetros ni datos de formularios.
- El módulo `client_errors` del BFF valida el cuerpo, emite `console.client_error` y suma la métrica.

## 7. Cambios a otras unidades (registrados en `audit.md`)

| Unidad | Cambio | Motivo |
|---|---|---|
| U0 domain-entities §1.2 (`CaseDetail.credit_status`) y tipo nuevo `CreditStatus` | `en_estudio \| aprobado \| desembolsado \| rechazado \| cancelado \| sin_credito \| no_disponible \| no_integrado` | Q3 |
| U8 BR-U8-21, NFR-U8-25, domain-entities §5, plan de tareas (Paso 12) | Con `core.enabled = false`, `credit_status = no_integrado` (antes `no_disponible`) | Q3 |
| U0 §1.2 (`CaseFilter`) y U8 BR-U8-13 y plan (Paso 13) | `model_frozen_after_recommendation?: bool`; sin campo de búsqueda por texto | Revisión del FD de U10, A3 y A4 |
| U2 domain-entities §2 (`vectra-console`), tabla de cambios de business-rules y plan de tareas | Redirect URI exacto `/stepup-callback` para el step-up en ventana emergente | Revisión del FD de U10, A1 |
| U8 (C04, BR-U8-13b, plan Paso 13) y U0 §9.2 | Endpoint `get_case_identifiers` (`GET /v1/cases/{id}/identifiers`, `cro` y `cumplimiento`) con `CaseIdentifiers` (`identifiers?`, `anonymized`), solo para el expediente | revisión del Infrastructure Design de U10, 2026-10-10 |
| U0 §9.5 (tipos del BFF) | `SessionInfo` y `ConsoleDossier`; `RegistryDossier` e `IntegrityStatus` se quedan en U0 §9.6 (dueña U3) | Revisión del FD de U10, B1 |
| U0 §6 (`reason`) | Agrega `no_active_version` y `active_version_frozen` (con `conflict_state`), que U4 BR-U4-13 ya usaba y faltaban en el catálogo cerrado | Q7 (la prueba del catálogo de mensajes lo detectó) |
| U0 business-rules §9b (BR-U0-94) y plan de U0 (Paso 3) | Lista única `contracts/forbidden-phrases.yaml`, herramienta `contracts/tools/forbidden_phrases.py` y `CODEOWNERS` de cumplimiento | Q8 |
| U4 BR-U4-07 y plan (Paso 13); U9 business-rules §6, INF-U9-05 y plan | Sus pruebas usan la lista única de U0 en lugar de listas propias | Q8 |
