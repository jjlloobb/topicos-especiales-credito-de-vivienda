# Plan de Functional Design — U10 `console`

**Alcance de la unidad** (`unit-of-work.md` U10):
- `console-bff`: los 27 endpoints de `component-methods.md` C03, con rol, MFA y regla de objeto en el servidor, propagación del token y del correlation ID, y errores genéricos.
- `console-spa` (React + TypeScript): las vistas de las cuatro personas (analista, ingeniero de riesgo, CRO y cumplimiento), dashboards embebidos de Grafana, textos en español y el **lint de frases prohibidas**.
- Sin datos propios.

**Historia (dueña):** US-602 (autorización en servidor por función y por objeto). Además
contribuye a 22 historias de otras unidades (`unit-of-work-story-map.md` §1): las vistas, los
formularios y las acciones de la consola.

**Ya decidido** (no se pregunta):
- **Login:** la SPA es el cliente público `vectra-console` de Keycloak, con Authorization Code + PKCE (U2).
- **MFA:** step-up con `prompt=login`, `max_age=0` y `acr_values=mfa` cuando el BFF responde `mfa_required`, y luego se reintenta la acción (BR-U2-04). Los aprobadores tienen MFA obligatorio (BR-U2-03).
- **Controles del BFF:** en cada endpoint, en este orden, función, MFA y objeto (C03). Los servicios vuelven a validar. `mark_active` no se expone.
- **Cabeceras:** perfiles `spa`, `api` y `grafana` del gateway (U2 §4.1). Grafana se embebe con `frame-ancestors 'self'` y hace su propio OIDC.
- **Contratos:** tipos de U0 (`CaseSummary`, `CaseDetail`, `DisparityView`, `FreezeContext`, `PrePostReport`, …) y cliente TypeScript generado (U0, Paso 16).
- **Pendientes que otras unidades dejaron para U10:**
  - **U8:**
    - bandeja con `applicant_display` y `vencido` oculto por defecto, con filtro;
    - avisos `decision_already_recorded` y `model_frozen_after_recommendation`;
    - `free_text` escapado al presentarlo;
    - detalle sin etiquetas de monitoreo;
    - «estado de crédito no integrado».
  - **U7:** marca de `revision_requerida` y de baja confianza.
  - **U9:** `disclaimer` del dashboard, lint de frases prohibidas (también sobre `bias.json`), versión servible con `list_models(state=activo,congelado)` y embebido de `bias.json`.
  - **U4:** `start_source_comparison` y la decisión de la fuente con el `PrePostReport`.

**Hallazgo que este FD debe resolver:** U8 pide mostrar «estado de crédito no integrado», pero `credit_status` devuelve `no_disponible` tanto con el core caído como con `core.enabled = false`. La consola no puede distinguirlos (Q3).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Dónde viven los tokens en el navegador (Security; SECURITY-12, US-611)
Con un cliente público, los tokens llegan al navegador.

A) **En memoria, con refresh rotativo**:
   - access token y refresh token solo en memoria del proceso de la SPA (nunca `localStorage` ni `sessionStorage`);
   - el refresh rota en cada uso y se revoca si se reusa (BR-U2-06);
   - recargar la página o abrir otra pestaña hace un login silencioso (`prompt=none`) contra la sesión de Keycloak;
   - logout borra la memoria y cierra la sesión de Keycloak.

   (Recomendado: un XSS no encuentra tokens persistidos)

B) **Patrón *token handler***: el BFF guarda los tokens del lado del servidor y la SPA usa una cookie `HttpOnly` + `SameSite=Strict`. Más seguro frente a XSS, pero el BFF deja de ser sin estado y pasa a ser cliente confidencial (cambia U2)

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 2 — La acción que pide MFA a mitad de un formulario (Business Logic; BR-U2-04)
El step-up redirige a Keycloak. Una aprobación, una resolución de congelado o una
justificación larga se perderían al volver.

A) **Borrador en memoria más un intento único después del step-up**:
   - antes de redirigir, la SPA guarda en `sessionStorage` **solo** la intención (endpoint, id del objeto y un `nonce`), nunca el cuerpo con datos sensibles; el cuerpo queda en memoria;
   - si la ventana se recarga y el cuerpo se pierde, el usuario vuelve al formulario con un aviso «vuelve a confirmar»;
   - tras el step-up, la SPA reintenta **una sola vez** la acción; si vuelve a fallar, muestra el error y no reintenta.

   (Recomendado)

B) Hacer el step-up **antes** de abrir cualquier formulario de aprobación (al entrar a la vista), para que nunca se pierda nada. Obliga a re-autenticar aunque el usuario solo mire

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 3 — «Estado de crédito no integrado» (Domain Model; pendiente de U8 INF-U8-02)

A) **Un valor propio en el contrato**:
   - `credit_status` suma el valor `no_integrado`, que `case-service` devuelve con `core.enabled = false`;
   - `no_disponible` queda solo para el core caído o lento;
   - la consola muestra «Estado de crédito no integrado» o «Estado de crédito no disponible por ahora»;
   - cambios en U0 (enumerado), U8 (BR-U8-21, NFR-U8-25) y la prueba de U8 con `core.enabled = false`.

   (Recomendado)

B) Mantener `no_disponible` para los dos y mostrar un solo texto («Estado de crédito no disponible»)

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 4 — Cuándo se registra la consulta de la explicación (Business Rules; US-501, BR-U8-19)
Esta consulta alimenta `explanation_viewed_before` de la decisión y la North Star de U11.

A) **Cuando el analista abre el panel de la explicación**:
   - el detalle del caso muestra el resultado (`outcome`, score, marcas) y un botón «Ver explicación»; la narrativa y los factores están en un panel que se abre con ese botón;
   - abrir el panel llama a `record_explanation_view` una vez por sesión de vista; el BFF y U8 ya garantizan una sola entrada por (caso, usuario);
   - si la llamada falla, el panel se muestra igual (la consulta queda pendiente en U8, BR-U8-18) y se registra el error;
   - abrir el detalle sin abrir el panel **no** cuenta como consulta.

   (Recomendado: mide uso real de la explicación, no solo carga de página)

B) Registrar la consulta al cargar el detalle del caso, con la explicación visible siempre

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 5 — Formulario de decisión (Frontend; US-108, US-502, BR-U8-16)

A)
   - tres opciones: `sigue` y `se_aparta`, y `resuelve_revision` solo si el `outcome` es `revision_requerida` (BR-U0-35);
   - **factores usados**: una lista de los `feature_id` del `shap_vector`, con su etiqueta en español, ordenada como la narrativa; o la casilla exclusiva «Ninguno»;
   - **justificación**: obligatoria en `se_aparta` y `resuelve_revision`, con un contador de 20 a 2000 caracteres que cuenta igual que el servidor (sin espacios en los bordes);
   - en `se_aparta`, `final_outcome` es distinto del de la recomendación y se elige explícitamente;
   - un diálogo de confirmación resume la decisión antes de enviarla;
   - validación en el cliente con las mismas reglas, pero el servidor decide (FR-UI-07); un 422 se muestra en el campo correspondiente;
   - el botón queda deshabilitado mientras la solicitud está en curso, para no duplicar.

   (Recomendado)

B) Igual que A, sin el diálogo de confirmación

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 6 — Bandeja y actualización de casos (Frontend; US-107, NFR-PER-01)
Un caso pasa de `en_evaluacion` a `listo` en p95 ≤ 5 s (NFR-U8-02).

A)
   - **filtros**: estado (por omisión, todos menos `vencido`), canal, fecha y «marcados con modelo congelado»; búsqueda solo por `applicant_display` y `case_id`;
   - **orden** por `created_at`, con paginación del servidor (páginas de ≤ 100);
   - **refresco**: la bandeja se vuelve a pedir cada 15 s mientras la pestaña está visible; el detalle de un caso `en_evaluacion` o `en_sincronizacion` se vuelve a pedir cada 3 s hasta que cambia de estado, con un máximo de 2 min; sin WebSockets;
   - estados con color **y** texto, nunca solo color.

   (Recomendado)

B) Sin refresco automático: un botón «Actualizar»

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 7 — Mensajes de error y avisos (Error Handling; SECURITY-15, US-611)
El BFF devuelve errores genéricos (`Problem` de U0 con `code` y, a veces, `reason`).

A) **Catálogo cerrado de mensajes en español**:
   - un mensaje por `code` y `reason` del catálogo de U0 §6 (por ejemplo, `decision_already_recorded` → «Otra persona ya registró la decisión de este caso. Se muestra la decisión registrada.»; `active_version_frozen`, `transition_pending`, `mfa_required`, `conflict_state`);
   - un `code` desconocido muestra un mensaje genérico con el `correlation_id` para soporte;
   - nunca se muestra el `detail` del servidor ni un stack trace;
   - los avisos de negocio (`model_frozen_after_recommendation`, baja confianza, `revision_requerida`, caso anonimizado) son textos del mismo catálogo;
   - una prueba compara el catálogo de mensajes con los `code` y `reason` de U0: ninguno sin mensaje.

   (Recomendado)

B) Mostrar el `title` del `Problem` tal como llega

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 8 — Lint de frases prohibidas (Business Rules; FR-BIA-08, US-307)
Lo usan U4 (informe), U9 (API y `bias.json`) y U10 (textos de la consola).

A) **Una sola lista versionada en U0, con un lint en CI**:
   - la lista vive en `contracts/forbidden-phrases.yaml` (U0), con frases y variantes: «sin sesgo», «libre de sesgo», «libre de discriminación», «no discrimina», «certifica la equidad», «garantiza la equidad», «imparcial» aplicado al modelo, y sus formas en inglés;
   - comparación sin mayúsculas ni tildes, con límites de palabra;
   - un lint de CI recorre los catálogos i18n de la SPA, las plantillas de U4, los textos de la API de U9 y `bias.json`;
   - cambiar la lista exige la aprobación de cumplimiento (`CODEOWNERS`).

   (Recomendado)

B) Una lista por unidad

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 9 — Vistas por rol y navegación (Frontend; FR-UI-07)

A) **Un menú por rol, sin depender de él para la seguridad**:
   - analista: bandeja, detalle, alta manual, decisión, políticas (lectura);
   - ingeniero de riesgo: modelos, validación, fuentes (propuesta y comparación);
   - CRO: bandeja (lectura), fallos persistentes y `retry`, aprobación de modelos y políticas, expediente, verificación de integridad, dashboard de sesgo (lectura);
   - cumplimiento: dashboard de sesgo, congelamientos y su resolución, decisión de fuentes, expediente;
   - el menú se arma con `get_me()` (roles), pero cada endpoint lo vuelve a validar (FR-UI-07); una ruta de la SPA a la que el rol no llega muestra «sin acceso», sin llamar al BFF;
   - un usuario tiene exactamente un rol de negocio (BR-U2-01).

   (Recomendado)

B) Una sola vista con todas las secciones, deshabilitadas según el rol

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 10 — Resolución de un congelamiento y decisión de una fuente (Frontend; US-304, US-305, US-306)

A)
   - **congelamiento**: la vista muestra el paquete de contexto completo (antes, después, últimos 7 días, atributo disparador, grupos y bandas implicados, fuentes de datos, disparidad de validación) con el `disclaimer`; las tres acciones (`reactivar`, `descartar`, `investigar`) exigen justificación y MFA; `reactivar` muestra además un aviso de que la ventana de monitoreo empieza al día siguiente y que habrá un periodo de «muestra insuficiente» (U9 §8b);
   - **fuente**: la vista muestra el `PrePostReport` (por atributo, antes y después y la diferencia) con el `disclaimer`; `aprobar` y `rechazar` exigen justificación y MFA; sin informe, los botones no aparecen y el servidor responde 409 de todos modos;
   - las celdas con «muestra insuficiente» se muestran así, nunca como 0.

   (Recomendado)

B) Igual que A, sin el aviso del periodo ciego al reactivar

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 11 — Composición del expediente (Integration; US-403, U3 FD Q7)

A)
   - el BFF pide `get_case_dossier` al registro y `get_case` a case-service (identificadores directos) y los une por `case_id`;
   - si case-service no responde, el expediente se devuelve **sin** identificadores y con una marca `identifiers_unavailable`, porque la evidencia del registro es lo esencial; si el registro no responde → 503;
   - un caso anonimizado se muestra sin identificadores y con la marca correspondiente;
   - la descarga es un PDF generado en la SPA a partir de la respuesta, con el estado de integridad (`IntegrityStatus`) visible.

   (Recomendado)

B) Si case-service no responde, 503 para todo el expediente

X) Other (please describe after [Answer]: tag below)

[Answer]:

## Question 12 — Prueba de US-602 (matriz rol × endpoint) (Business Rules; US-602)

A) **Generada desde el registro de contratos de U0**:
   - para cada uno de los 27 endpoints del BFF y cada uno de los 4 roles, más un token sin rol y uno expirado, la prueba espera 200/2xx, 403 o 401 según la columna «Roles» y «MFA»;
   - para cada endpoint con regla de objeto, un caso negativo (por ejemplo, decidir un caso `no_disponible` → 409; resolver un congelamiento con `cro` → 403);
   - cada 401/403 deja `authz.denied` con `principal_subject` y la métrica;
   - la matriz se publica como `role-endpoint-matrix.md` (U0, Paso 15) y se compara con la tabla de `component-methods.md` C03.

   (Recomendado)

B) Pruebas escritas a mano solo para los endpoints con MFA

X) Other (please describe after [Answer]: tag below)

[Answer]:

---

## Parte B — Checklist de ejecución

- [ ] Leer y validar las respuestas; preguntas de aclaración si alguna es ambigua
- [ ] `business-rules.md` (BR-U10-xx): controles del BFF por endpoint, composición, errores, tokens, step-up, lint
- [ ] `domain-entities.md`: vistas y modelos de la SPA, catálogo de mensajes, configuración
- [ ] `business-logic-model.md`: flujos (login, step-up, decisión, consulta de la explicación, congelamiento, fuente, expediente) y propiedades (PBT-U10-xx)
- [ ] `frontend-components.md`: jerarquía de componentes, props y estado, flujos de interacción, validación de formularios y endpoints que usa cada componente
- [ ] Cambios a otras unidades registrados (U0, U8 según Q3; U0 según Q8)
- [ ] Tabla de cumplimiento de extensiones
- [ ] Validar el contenido (Mermaid y texto alternativo) antes de crear los archivos
- [ ] Registrar en `audit.md` y actualizar `aidlc-state.md`
