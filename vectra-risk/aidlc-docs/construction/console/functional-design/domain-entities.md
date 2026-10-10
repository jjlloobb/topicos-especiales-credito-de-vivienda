# Entidades de dominio — U10 `console`

U10 no tiene datos propios. Los tipos de las APIs son los de U0 (§1, §9); aquí se describen
los que agrega el BFF, el estado de la SPA y los catálogos de textos.

---

## 1. Tipos del BFF

| Tipo | Campos | Notas |
|---|---|---|
| `SessionInfo` (`get_me`; U0 §9.5) | `role` (uno de los 4 de negocio), `mfa` (`acr = mfa`), `auth_time`, `locale` (`es-CO`) | Solo de los claims del token; sin llamadas a servicios |
| `ConsoleDossier` (`get_dossier`; U0 §9.5) | `RegistryDossier` (U0 §9.6, dueña U3; incluye `IntegrityStatus`) + `identifiers?` de case-service + `identifiers_unavailable: bool` + `anonymized: bool` | BR-U10-03 |
| `DisparityView` | El de U0 §9.4, con la versión servible elegida por el BFF | BR-U10-03 |

Los tipos de esta tabla viven en U0 §9.5 (BR-U0-93); U10 no los redefine (revisión del FD de U10, 2026-10-10, B1).

Los demás endpoints devuelven el tipo de U0 del servicio de destino sin cambios.

## 2. Estado de la SPA

| Estado | Dónde vive | Notas |
|---|---|---|
| Tokens (access y refresh) | Memoria del proceso | Nunca persistidos (BR-U10-05) |
| `SessionInfo` | Memoria | Se renueva con cada token |
| `StepUpAttempt` | Memoria de la ventana principal | `state`, `nonce`, `code_verifier` y la acción pendiente con su cuerpo; un intento a la vez y se borra al terminar (BR-U10-06). Nada en `sessionStorage` ni en la URL (revisión del FD de U10, 2026-10-10, A1) |
| Borradores de formulario (decisión, justificaciones, alta manual) | Memoria del componente | Sobreviven al step-up (ventana emergente); se pierden si el usuario recarga la página |
| Caché de vistas | Memoria (cliente de datos, por ejemplo TanStack Query) | Bandeja 15 s y detalle 3 s mientras está en evaluación (BR-U10-10) |
| Último momento de actividad de la sesión | Memoria de cada pestaña, sincronizada por `BroadcastChannel` | BR-U10-20 (revisión del Infrastructure Design de U10, 2026-10-10) |
| Versión cargada y versión publicada | Memoria | BR-U10-21 |
| Contador del `reporter` | Memoria | BR-U10-22 |
| Filtros de la bandeja | URL (parámetros de consulta) | Solo los campos de `CaseFilter` (estado, canal, fechas, `model_frozen_after_recommendation`, página); ninguno es un dato del solicitante. Sin búsqueda por nombre (BR-U10-10) |

## 3. Catálogos de textos

| Catálogo | Contenido | Regla |
|---|---|---|
| `messages.es.json` | Un mensaje por `code` y `reason` de U0 §6; avisos de negocio | BR-U10-17; una prueba exige un mensaje por cada valor |
| `labels.es.json` | Estados del caso, `outcome`, decisiones, estados de modelo, política y fuente, `credit_status` | Un texto por valor de cada enumerado de U0 |
| `features.es.json` | No existe: las etiquetas de los factores vienen del diccionario de features de la versión (U4, en la `Explanation`) | — |
| `contracts/forbidden-phrases.yaml` (U0) | Frases prohibidas y variantes | BR-U10-18 |

## 4. Configuración de la SPA (tercera revisión del Infrastructure Design de U10, 2026-10-10: separada entre `config.json` y constantes)

**Por entorno, en `config.json`** (ConfigMap del chart, INF-U10-03):

| Parámetro | Valor | Origen |
|---|---|---|
| `oidc.authority`, `oidc.client_id` (`vectra-console`), `redirect_uri`, `stepup_redirect_uri` (`/stepup-callback`) | Por entorno | Values del chart; los dos URI deben estar registrados en el cliente del realm (U2) |
| `grafana.bias_dashboard_uid` | El de `bias.json` | U9 INF-U9-05 |

**Constantes del código** (`console/spa/src/config/constants.ts`), iguales en todos los entornos;
cambiarlas es un cambio de código con su PR y sus pruebas:

| Constante | Valor | Origen |
|---|---|---|
| `STEPUP_TIMEOUT_SECONDS` | 300 | BR-U10-06 |
| `IDLE_WARNING_SECONDS` / `IDLE_LOGOUT_SECONDS` | 1 500 / 1 800 | BR-U10-20; una prueba compara `IDLE_LOGOUT_SECONDS` con `ssoSessionIdleTimeout` de los tres `realm.{env}.yaml` de U2 (1 800 s) |
| `ACTIVITY_BROADCAST_SECONDS` | 30 | BR-U10-20 |
| `VERSION_POLL_SECONDS` | 300 | BR-U10-21 |
| `REPORTER_MAX_PER_MINUTE` | 10 | BR-U10-22 |
| `API_TIMEOUT_SECONDS` | 10 | P-U10-04 |
| `INBOX_REFRESH_SECONDS` | 15 | BR-U10-10 |
| `CASE_REFRESH_SECONDS` / `CASE_REFRESH_MAX_SECONDS` | 3 / 120 | BR-U10-10 |

`config.json` no tiene secretos (es un cliente público) y una prueba falla si aparece en él una de
las constantes de esta segunda tabla.
