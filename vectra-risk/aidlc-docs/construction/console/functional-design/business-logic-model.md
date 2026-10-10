# Modelo de lógica — U10 `console`

## 1. Módulos lógicos

| Proceso | Módulo | Responsabilidad | Reglas |
|---|---|---|---|
| BFF | `routes` | Los 29 endpoints (incluidos `report_client_error`, NFR-U10-34, y `get_integrity_check`, P-U10-05) como `RouteContract` de U0, con rol, MFA y objeto | BR-U10-01 |
| BFF | `object_rules` | Reglas de objeto por endpoint (funciones puras sobre el estado que devuelve el servicio de destino) | BR-U10-01 |
| BFF | `compose` | `get_disparity` y `get_dossier` | BR-U10-03 |
| BFF | `errors` | Traducción de errores de los servicios al `Problem` de U0 | BR-U10-04 |
| SPA | `auth` | Login con PKCE, tokens en memoria, refresco rotativo, login silencioso; página `/stepup-callback` | BR-U10-05, 06 |
| SPA | `stepup` | Ventana emergente, validación del mensaje y reintento único | BR-U10-06 |
| SPA | `cases` | Bandeja, detalle, explicación, decisión, alta manual, fallos persistentes | BR-U10-07..11 |
| SPA | `governance` | Modelos, políticas, fuentes, congelamientos | BR-U10-12..15 |
| SPA | `bias` | Dashboard de la API y el embebido de Grafana | BR-U10-15, 16 |
| SPA | `i18n` | Catálogos de mensajes y etiquetas | BR-U10-17 |
| SPA | `inactivity` | Contador de la sesión compartido entre pestañas, aviso y logout | BR-U10-20 |
| SPA | `version_watch` | Consulta de `version.json` y aviso | BR-U10-21 |
| SPA | `reporter` | Captura, traducción al catálogo y envío limitado de errores | BR-U10-22 |
| BFF | `client_errors` | Validación de `ClientErrorReport`, evento y métrica | BR-U10-22 |
| CI | `forbidden-phrases-lint` | Lint sobre i18n, plantillas de U4, textos de U9 y `bias.json` | BR-U10-18 |

`object_rules`, `errors`, la validación del formulario de decisión y `stepup` son puros y se
prueban con propiedades.

## 2. Flujos

### 2.1 Login y renovación

```text
SPA sin token -> Authorization Code + PKCE (S256) -> Keycloak -> code -> tokens en memoria
access token vence -> refresh (rota) ; refresh reusado -> Keycloak revoca la sesión -> login
recarga / pestaña nueva -> prompt=none ; sin sesión -> login
```

### 2.2 Acción con MFA (step-up en ventana emergente; revisión del FD de U10, 2026-10-10, A1)

```mermaid
flowchart TD
    act["Usuario confirma una accion con MFA"]
    fresh{"MFA reciente en el token?"}
    call["SPA llama al BFF con el cuerpo en memoria"]
    dlg["Dialogo: boton Verificar identidad (nuevo clic)"]
    ok{"Respuesta"}
    done["Muestra el resultado"]
    gen["Genera state, nonce y code_verifier en memoria"]
    pop["window.open: Keycloak con prompt=login, max_age=0, acr_values=mfa"]
    cb["stepup-callback: postMessage de code y state al opener y cierra"]
    chk{"Origen, ventana y state validos antes de 5 min?"}
    tok["Canjea el code, valida nonce y acr=mfa, reemplaza tokens"]
    retry["Reintenta una sola vez con el mismo cuerpo"]
    keep["Formulario intacto: la verificacion no se completo"]
    err["Muestra el error del catalogo"]
    res{"Respuesta del reintento"}

    act --> fresh
    fresh -->|"si"| call
    fresh -->|"no: Verificar y confirmar, mismo clic"| gen
    call --> ok
    ok -->|"2xx"| done
    ok -->|"403 mfa_required"| dlg --> gen
    gen --> pop --> cb --> chk
    ok -->|"otro error"| err
    chk -->|"si"| tok --> retry --> res
    res -->|"2xx"| done
    res -->|"cualquier error, incluido otro 403"| err
    chk -->|"no, bloqueada o cerrada"| keep
```

### Alternativa en texto

```text
acción con MFA (revisión del Infrastructure Design de U10, 2026-10-10: la ventana siempre se abre en el manejador de un clic)
  ¿el token tiene acr = mfa y auth_time ≤ 900 s? no -> botón «Verificar y confirmar»: abre la ventana en ese clic
  sí -> BFF (cuerpo en memoria de la ventana principal)
  2xx -> resultado
  403 code=mfa_required -> diálogo con «Verificar identidad»; su clic abre la ventana ->
       state, nonce, code_verifier en memoria
       -> window.open(Keycloak /auth, prompt=login, max_age=0, acr_values=mfa,
                      redirect_uri=/stepup-callback)
       -> /stepup-callback: postMessage({code, state}, location.origin); window.close()
          (no canjea, no guarda nada)
       -> ventana principal: origen propio, source = la ventana abierta, state igual, < 5 min ?
            sí -> canjear code (PKCE), nonce y acr=mfa válidos -> tokens nuevos en memoria
                  -> reintentar una vez con el mismo cuerpo -> (2xx | error del catálogo)
            no (bloqueada, cerrada, vencida) -> formulario intacto, «vuelve a confirmar»
       -> state, nonce y code_verifier se borran siempre
  otro error -> mensaje del catálogo (sin detail del servidor)
```

### 2.3 Decisión de un caso

```text
detalle (listo) -> [Ver explicación] -> record_explanation_view (una vez por vista) -> panel
formulario: decisión, factores (o «Ninguno»), final_outcome, justificación (20..2000 sin bordes)
  -> validación local -> diálogo de confirmación -> POST decision (botón deshabilitado)
  200 -> caso decidido ; 422 -> errores por campo ; 409 decision_already_recorded -> aviso + recarga
  503 -> «el registro no responde; la decisión quedó pendiente» (U8 BR-U8-18)
```

### 2.4 Expediente

```text
BFF get_dossier: registry get_case_dossier (F13) y case get_case_identifiers (F10), en paralelo
  registro caído -> 503
  case caído (timeout, conexión, 5xx, circuito) -> expediente sin identificadores, identifiers_unavailable = true
  case responde 403 o 404 -> el BFF devuelve ese error (no es una caída)
  caso anonimizado -> sin identificadores, anonymized = true
SPA: vista con IntegrityStatus; PDF generado en el navegador desde la respuesta
```

## 3. Propiedades testeables (PBT-01)

| ID | Componente | Propiedad | Categoría | Generadores (PBT-07) |
|---|---|---|---|---|
| PBT-U10-01 | BFF `routes` | Para todo endpoint, todo rol y todo estado de token (válido, expirado, otra audiencia, sin rol, `acr = pwd`, `auth_time` vencido), la respuesta es la de la matriz de C03 (2xx, 401, 403 o `mfa_required`) y cada 401/403 emite `authz.denied` | Oráculo | Producto de los 29 endpoints × roles × estados de token |
| PBT-U10-02 | BFF `object_rules` | Para todo estado del objeto generado, la regla acepta ⇔ la columna «Objeto» de C03 lo permite (por ejemplo, `record_decision` ⇔ caso `listo`; `retry_case` ⇔ `no_disponible` y no anonimizado) | Oráculo | Estados de caso, modelo, política y fuente |
| PBT-U10-03 | BFF `errors` | Para todo error de un servicio de destino, la respuesta del BFF es un `Problem` válido de U0 sin `detail` ni campos extra, con el mismo `code` o `internal_error` | Invariante | Respuestas de error generadas (códigos, cuerpos arbitrarios, cuerpos malformados) |
| PBT-U10-04 | SPA validación de decisión | La validación del cliente acepta ⇔ acepta `validate_decision` de U8 (mismo oráculo de PBT-U8-03) | Oráculo | Los generadores de PBT-U8-03 |
| PBT-U10-05 | SPA `stepup` | Para toda secuencia de eventos (403 `mfa_required`; mensajes con origen propio u otro, de la ventana abierta u otra, con `state` igual o distinto; ventana bloqueada o cerrada; vencimiento de 5 min; canje fallido; token sin `acr = mfa`; segundo 403), hay como máximo un reintento por acción, el reintento lleva exactamente el cuerpo original, solo un mensaje válido lo dispara, el estado del step-up se borra siempre y `sessionStorage`, `localStorage` y la URL nunca cambian (revisión del FD de U10, 2026-10-10, A1) | Stateful | Secuencias de eventos con cuerpos que incluyen justificaciones y datos de la solicitud |
| PBT-U10-06 | `i18n` | Para todo `code`, `reason` y valor de enumerado de U0, existe un texto, y ningún texto contiene una frase de la lista prohibida | Invariante | Los catálogos de U0 y los textos |

**Pruebas de ejemplo obligatorias (PBT-10):**
- un analista llama al endpoint de aprobación de modelo → 403 `forbidden` y `authz.denied` (US-602);
- las rutas de la SPA por rol coinciden con la columna «Roles» de C03 (BR-U10-12); por ejemplo, `cro` no ve el paquete de contexto de un congelamiento y `cumplimiento` no ve la bandeja;
- la URL de la bandeja con cualquier combinación de filtros no contiene datos del solicitante (BR-U10-10);
- un JWT expirado, con otra audiencia o mal firmado → 401 (US-602);
- un aprobador sin MFA reciente aprueba → 403 `mfa_required`, ventana emergente y reintento único con la misma justificación → 200 (US-203, US-305);
- token sin MFA reciente → el botón dice «Verificar y confirmar» y la ventana se abre en ese mismo clic (`window.open` llamado de forma síncrona en el manejador); un 403 `mfa_required` inesperado → diálogo y la ventana se abre en el clic de «Verificar identidad» (revisión del Infrastructure Design de U10, 2026-10-10);
- inactividad: actividad en la pestaña A durante 40 min con la pestaña B quieta → ninguna cierra la sesión; 30 min sin actividad en ninguna → logout en las dos; `wheel` y `scroll` cuentan como actividad (BR-U10-20);
- `version.json` cambia → aviso sin recarga; un fragmento que no carga → mensaje con botón y el formulario intacto (BR-U10-21);
- 20 errores en un minuto → 10 envíos, ninguno con mensaje ni URL con parámetros (BR-U10-22);
- expediente para `cumplimiento` con case-service sano → con identificadores; con case-service caído → `identifiers_unavailable = true`; con un 403 de case-service → 403 del BFF, nunca `identifiers_unavailable` (BR-U10-03);
- ventana emergente bloqueada o cerrada sin terminar → sin reintento, con el formulario y su justificación intactos y el aviso «vuelve a confirmar»;
- un `postMessage` de otro origen o con otro `state` → ignorado, sin canje ni reintento;
- abrir el detalle sin abrir la explicación → ninguna llamada a `record_explanation_view`; abrir el panel → una sola llamada (US-501);
- `free_text` con `<script>alert(1)</script>` → se muestra como texto (US-109);
- bandeja por omisión sin casos `vencido`; con el filtro, aparecen (US-107);
- `credit_status = no_integrado` → «Estado de crédito no integrado» (BR-U10-07);
- un caso con baja confianza y uno con `revision_requerida` → sus marcas (US-106);
- `decision_already_recorded` → el aviso del catálogo y el caso recargado con la decisión registrada;
- expediente con case-service caído → sin identificadores y con la marca (US-403);
- vista de congelamiento con el paquete completo y el aviso de `reactivar` (US-304, US-305);
- decisión de una fuente sin `PrePostReport` → sin botones; con informe → antes, después y diferencia (US-306);
- dashboard de sesgo: el `disclaimer` y la leyenda están siempre; las celdas insuficientes dicen «muestra insuficiente» (US-307);
- la lista de fallos persistentes y el `retry` del CRO (US-112).

## 4. Cumplimiento de extensiones (Functional Design U10)

| Regla | Estado | Evidencia |
|---|---|---|
| SECURITY-04 | Cumple | Cabeceras de U2 (perfiles `spa`, `api`, `grafana`); BR-U10-11 (sin `dangerouslySetInnerHTML`) |
| SECURITY-05 | Cumple | BR-U10-09 (validación en cliente y servidor) |
| SECURITY-08 | Cumple | BR-U10-01, 19 (función, MFA y objeto en el servidor; matriz rol × endpoint) |
| SECURITY-12 | Cumple | BR-U10-05, 06 (tokens solo en memoria; step-up en ventana emergente del mismo origen, sin nada en `sessionStorage` ni en la URL) |
| SECURITY-14 | Cumple | BR-U10-01 (`authz.denied` y métrica en cada 401/403) |
| SECURITY-15 | Cumple | BR-U10-04, 17 (errores genéricos, sin `detail`) |
| AUTONOMIA-04 | Cumple | `resolve_frozen` solo para `cumplimiento` con MFA (BR-U10-13) |
| PBT-01 | Cumple | §3 |
| PBT-06 | Cumple | PBT-U10-05 (stateful) |
| PBT-07 | Cumple | Columna «Generadores» de §3 |
| PBT-10 | Cumple | Pruebas de ejemplo de §3 |
