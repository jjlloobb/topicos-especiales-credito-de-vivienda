# Patrones de NFR Design — U2 `identity-edge`

Decisiones del plan (`identity-edge-nfr-design-plan.md`, Q1–Q6 = A). Los IDs `P-U2-xx` se
referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind las
ejecuta el operador después de un PR aprobado (AUTONOMIA-01).

---

## 1. Resiliencia

### P-U2-01 — Modo de fallo del rate limit por ruta (Q1, NFR-U2-21)

| Ruta | Si Valkey o el servicio de rate limit no responden |
|---|---|
| `/auth/**` | **fail-closed**: 503 `dependency_unavailable` (además, el bloqueo de Keycloak sigue activo) |
| `/api/console/**`, `/api/intake/**`, `/api/promotion/**` | **fail-open**: la request sigue; los servicios autentican y autorizan igual (U0) |

**Implementación en orden de preferencia.** Se verifica contra la versión de Envoy Gateway
pinneada en el plan de tareas y se registra en `audit.md` cuál se usó:
1. **Nativa**: dos `BackendTrafficPolicy` (una para `/auth/**` con el modo de fallo cerrado y otra para el resto con fail-open), si la API de la versión pinneada expone ese modo en el rate limit global.
2. **Parche acotado**: una `EnvoyPatchPolicy` que fija `failure_mode_deny: true` **solo** en el filtro de rate limit de la ruta de `/auth/**`. Una prueba sobre la configuración renderizada de Envoy (`egctl config envoy-proxy`) falla si una actualización rompe el parche.
3. **Gateway separado**: `/auth/**` en un `Gateway` propio con un `EnvoyProxy` configurado en fail-closed.

- **Alternativa elegida** (enmienda del 2026-11-04, decisión W3 del usuario al preparar U02-T10), comprobada contra Envoy Gateway v1.9.3:
  - la 1 no existe: `rateLimit.failClosed` es global del controlador y responde 500;
  - la 3 tampoco sirve: un `Gateway` separado comparte ese mismo ajuste del controlador;
  - se usa la 2. Envoy Gateway crea un filtro de rate limit por dominio, y cada política con reglas `shared` tiene su dominio. Los dos contadores por IP de `/auth/**` van en la política de ruta de `/auth/**`, que es una sola porque `/auth/**` no reintenta (X1). Su `mergeType: StrategicMerge` la mezcla con `edge-rate-limits`. Una segunda `BackendTrafficPolicy` en el `Gateway` queda `Conflicted` en v1.9.3, y `mergeType` solo vale sobre rutas (enmienda del 2026-11-04, decisión X1 del usuario en la ronda 1 de U02-T10). Una `EnvoyPatchPolicy` fija en el filtro de ese dominio `failure_mode_deny: true` y `status_on_error: 503`, y el 503 lleva `Problem` `dependency_unavailable`;
  - el límite global de 200/s sigue en `edge-rate-limits` y falla abierto;
  - el controlador habilita `extensionApis.enableEnvoyPatchPolicy`.
- **Verificación**: en kind, con Valkey escalado a 0 → `GET /api/console/me` = 200 y `POST /auth/realms/vectra/protocol/openid-connect/token` = 503.
- **Satisface**: NFR-U2-21; SECURITY-15; RESILIENCY-10.

### P-U2-02 — Timeouts, reintentos y outlier detection (Q4)

| Ruta | Timeout | Reintentos |
|---|---|---|
| `/api/console/**` | 15 s | Solo `GET`/`HEAD`: 1 reintento ante `connect-failure`, presupuesto del 20 %. Sin reintento ante `503`: el BFF ya agotó su presupuesto y superaría los 10 s de la SPA (cuarta revisión de coherencia entre unidades, 2026-10-31) |
| `/api/intake/**` | 5 s | **Ninguno** (solo `POST`) |
| `/api/promotion/**` | 10 s | Solo el `GET`; el `POST` de activación **nunca** |
| `/auth/**` | 10 s | Solo `GET`/`HEAD` |
| `/grafana/**` | 30 s | Solo `GET`/`HEAD` |

- `/auth/**` no reintenta (enmienda del 2026-11-04, decisión X1 del usuario en la ronda 1 de U02-T10). En Envoy Gateway v1.9.3, separar sus reglas por método para reintentar solo `GET`/`HEAD` partiría en dos cada contador por IP de P-U2-01, que tiene que quedar exacto.
- Cifras de los «solo `GET`/`HEAD`» de promoción y `/grafana/**` (`/auth/**` ya no reintenta, decisión X1): las de `/api/console/**`, es decir, 1 reintento ante `connect-failure`, presupuesto del 20 % y sin reintento ante `503` (enmienda del 2026-11-04, decisión D-4 del usuario tras la ronda 1 de U02-T09).
- **Nunca** se reintentan `POST`, `PUT` ni `PATCH`: un reintento podría duplicar una decisión, una aprobación o una solicitud.
- **Outlier detection**: 5 errores 5xx consecutivos sacan un pod del balanceo por 30 s, hasta el 50 % de los pods del backend. En `/api/console/**` cuentan **solo los errores de conexión** (`splitExternalLocalOriginErrors` y `consecutiveLocalOriginFailures`), porque un 503 `dependency_unavailable` del BFF no indica un pod enfermo (seguimiento de la cuarta revisión de coherencia, 2026-10-31).
- **Verificación**: `conftest` sobre las `BackendTrafficPolicy` renderizadas (ningún reintento en métodos no idempotentes; `/api/console/**` no expulsa por 5xx); en kind, un backend de prueba que devuelve 503 a un `POST` recibe exactamente 1 llamada.
- **Satisface**: RESILIENCY-10; NFR-U2-11.

### P-U2-03 — JWKS en el gateway (Q5)
- El filtro JWT trae la JWKS por la URL **interna** de Keycloak (`keycloak.vectra-identity.svc:8443`, F50), no por el gateway. La refresca cada 5 min y conserva la última válida si Keycloak no responde.
- Esta diferencia con U0, que deja de validar al vencer su cache (P-U0-06), es intencional: el gateway es la primera capa y cada servicio vuelve a validar con las reglas de U0.
- Una llave retirada (P-U2-05) deja de aceptarse en el gateway en ≤ 5 min.
- **Verificación**: en kind, Keycloak caído → el gateway sigue validando tokens vigentes; el servicio de destino responde 503 cuando vence su cache de 10 min.
- **Satisface**: NFR-U2-05; RESILIENCY-10.

### P-U2-04 — Keycloak tolerante a fallos
- 2 réplicas repartidas por zona, HPA de 2 a 4, PDB `minAvailable: 1`; Infinispan embebido con `jdbc-ping`; sesiones persistentes en `keycloak-db` (NFR-U2-01, 02).
- Readiness = su base (`keycloak-db`), según P-U1-04. Liveness y readiness en el puerto de gestión (9000), que no se expone en el gateway.
- Valkey: primaria + réplica + 3 Sentinel repartidos por zona. Un failover de Sentinel dura segundos y reinicia los contadores, lo que se acepta porque son efímeros.
- **Verificación**: escenario NFR-U2-02 en kind; borrar la primaria de Valkey → Sentinel promueve la réplica y el rate limit se recupera.

## 2. Seguridad

### P-U2-05 — Rotación de las llaves de firma (Q3)
- Cada 90 días se agrega por realm como código una llave nueva (RS256 o ES256) con mayor prioridad, que pasa a firmar.
- La anterior queda **pasiva** (publicada en JWKS, sin firmar) durante 24 h y después se desactiva.
- Runbook `signing-key-rotation.md`. Alerta `SigningKeyAgeHigh` (SEV3) a los 80 días, calculada desde la fecha de creación de la llave activa que publica el CronJob `signing-key-age` (seguimiento de la quinta revisión de coherencia, 2026-10-31). Esa fecha es la métrica `vectra_signing_key_created_timestamp_seconds`, el `notBefore` del certificado de la llave (INF-U2-09; enmienda del 2026-11-03, decisión R4 del usuario al preparar U02-T08).
- **Verificación**: en kind, rotación con tokens emitidos antes y después: los dos se aceptan durante el solapamiento y el anterior se rechaza tras desactivar la llave.
- **Satisface**: SECURITY-12; NFR-U2-24.

### P-U2-06 — Claves de rate limit solo de datos verificados (Q2)

| Ruta | Clave del descriptor | Origen |
|---|---|---|
| `/api/console/**`, `/api/promotion/**` | `sub` | Claim del JWT validado, copiado a la cabecera interna `x-vectra-sub` |
| `/api/intake/**` | `azp` | Claim del JWT validado, copiado a `x-vectra-azp` |
| `/auth/**` | IP de origen | Dirección que fija Envoy desde el balanceador de confianza (NFR-U2-23) |

- Las cabeceras internas se **eliminan** de la request entrante antes del filtro JWT (un cliente no puede inyectarlas) y otra vez antes de enviar la request al backend.
- «Cabeceras internas» = toda cabecera con el prefijo reservado `x-vectra-` (incluidas `x-vectra-sub`, `x-vectra-azp` y `x-vectra-deadline` de U7). Una cabecera legítima de un cliente externo no puede usar ese prefijo; por ejemplo, el simulador usa `X-Test-Scenario` (precisado el 2026-10-06 por U8 FD Q9).
- **Cabeceras de aplicación**: `Idempotency-Key` (obligatoria en `POST /v1/intake/applications` y en el alta manual, BR-U8-02 y 04) y `X-Test-Scenario` (BR-U8-03) **pasan intactas**. El gateway no las elimina, no las reescribe y no las usa como clave (precisado el 2026-10-06, revisión del FD de U8).
- **Verificación**: en kind, un cliente que manda `x-vectra-sub: otro` no cambia su contador; el backend de eco no recibe las cabeceras internas y **sí** recibe intactas `Idempotency-Key` (en `/api/intake/**` y `/api/console/**`) y `X-Test-Scenario` (en `/api/intake/**`), byte a byte (precisado el 2026-10-06, revisión del FD de U8).
- **Satisface**: NFR-U2-20; SECURITY-11.

### P-U2-07 — Access log del gateway con allowlist
- Campos: `timestamp`, `route_name`, `method`, `status`, `duration_ms`, `upstream_cluster`, `correlation_id` (el `trace-id` de `traceparent`), `client_ip` y `response_flags`.
- **Nunca**: query string, cuerpo, `Authorization`, cookies ni cabeceras internas. Formato JSON a stdout, recogido por Alloy hacia Loki (U1).
- **Verificación**: prueba con una request que lleva un token y una query con datos → no aparecen en el log.
- **Satisface**: SECURITY-02, 03; AUTONOMIA-05.

## 3. Usabilidad

### P-U2-08 — Tema de login en español (Q6)
- Tema `vectra`, hijo de `keycloak.v2`: logo y colores del banco, textos en `messages_es.properties` (locale por defecto `es`), sin JavaScript propio ni recursos externos.
- CSP estricta en `/auth/**` (BR-U2-13).
- Marca Vectra mientras el banco no entregue la suya (enmienda del 2026-11-02, decisión P3 del usuario al preparar U02-T06):
  - logo `vectra-logo.svg`: SVG propio con la palabra «Vectra», sin `<script>`, sin `<image>` y sin referencias de otro origen;
  - color primario `#0B3D5C` (botones, encabezado) y de acento `#C2410C` (enlaces y foco), sobre fondo `#FFFFFF`;
  - contraste sobre `#FFFFFF`: primario 11,44:1 y acento 5,18:1, ambos ≥ 4,5:1 (WCAG 2.1 AA, texto normal).
- Referencia de claves de `messages_es.properties` (enmienda del 2026-11-02, decisión P4 del usuario): los `messages_en.properties` de los temas `base` y `keycloak.v2` (login) de la versión de Keycloak de INF-U2-08, guardados con su checksum en `identity-edge/tests/fixtures/keycloak-<versión>/`.
  - Toda clave de `messages_es.properties` existe en esa referencia.
  - Están traducidas las claves literales `msg("…")` de las plantillas de login (`login.ftl`), TOTP (`login-otp.ftl`, `login-config-totp.ftl`) y cambio de contraseña (`login-update-password.ftl`), con las comunes que incluyen (`template.ftl`, `buttons.ftl`, `field.ftl`, `password-commons.ftl`), siempre que existan en la referencia. Las plantillas están en el mismo directorio de fixtures.
- Objetivo WCAG 2.1 AA: contraste, etiquetas de formulario y foco visible.
- **Verificación**: Playwright + `axe-core` sobre las páginas de login, TOTP y cambio de contraseña sin violaciones serias ni críticas; prueba de que el tema no carga recursos de otro origen.
- **Satisface**: NFR-USA-01; SECURITY-04.

## 4. Observabilidad

### P-U2-09 — Métricas y alertas de U2

| Alerta | Severidad | Fuente |
|---|---|---|
| `KeycloakDown` | SEV1 | Ninguna réplica lista |
| `RateLimitBackendDown` | SEV2 | Servicio de rate limit o Valkey sin respuesta (con `/auth/**` en fail-closed) |
| `AuthDeniedBurst` | SEV2 | Eventos de Keycloak + 401/403 de U0 |
| `BreakGlassLogin` | SEV1 | Evento de login del usuario `break-glass` |
| `RealmDrift` | SEV2 | `vectra_realm_drift > 0`, que el CronJob de comparación empuja al Pushgateway (F112; cuarta revisión de coherencia entre unidades, 2026-10-31) |
| `RoleConflict` | SEV2 | Evento de la federación LDAP |
| `SigningKeyAgeHigh` | SEV3 | Métrica de `signing-key-age`, en el Pushgateway (F112, `/metrics/job/signing-key-age`; revisión de consistencia entre unidades, 2026-11-01) |
| `LdapUnavailable` | SEV2 | Fallos de conexión de la federación LDAP (solo prod; agregado en INF-U2-07) |
| `GatewayHighLatency` | SEV3 | Diferencia entre el p95 de la latencia de Envoy hacia el cliente y el p95 hacia el backend > 5 ms sostenida 15 min. Es una aproximación: NFR-U2-11 se mide con la prueba con y sin gateway (seguimiento de la quinta revisión de coherencia, 2026-10-31) |

- Keycloak expone métricas en el puerto de gestión (9000); Envoy y el servicio de rate limit, sus estadísticas. Todos llevan `ServiceMonitor`. F60 solo abre el 8081 en `vectra-edge`: U2 agrega por PR a `flows.yaml` el flujo de cada puerto de estadísticas cuando lo fije (revisión de consistencia entre unidades, 2026-11-01).
- Toda alerta tiene `runbook_url` (P-U1-10).
- **Verificación**: `promtool test rules identity-edge/observability/rules/tests/*.yaml` (cada alerta se dispara con series sintéticas) y el test de runbooks de U1 (`severity` válida y `runbook_url` hacia un archivo existente).

#### Fuentes, umbrales y despliegue (enmienda del 2026-11-05, decisiones B1–B9 del usuario al preparar U02-T13)

Al preparar el Paso 11, el orquestador comparó la tabla con lo que el código emite hoy. 4 de las 9 alertas no tenían ninguna métrica que las alimentara, solo 2 tenían umbral y ninguna tenía `for`. Rige lo siguiente:

| Alerta | Severidad | Expresión (fuente) | `for` |
|---|---|---|---|
| `KeycloakDown` | SEV1 | `kube_statefulset_status_replicas_ready{namespace="vectra-identity",statefulset="keycloak"} == 0` (kube-state-metrics de U1) | 1m |
| `RateLimitBackendDown` | SEV2 | Réplicas disponibles en 0 de `envoy-ratelimit` (`envoy-gateway-system`) o del StatefulSet de Valkey, según kube-state-metrics, **o** `redis_up == 0` del exportador (9121) (B4), **o** ausente la serie de kube-state-metrics del Deployment o del StatefulSet (`absent(...)`, B13) **B17**: las ramas por ausencia van con `absent_over_time(...[10m])` y kube-state-metrics arriba. | 2m |
| `AuthDeniedBurst` | SEV2 | Más de 20 denegaciones por minuto: `LOGIN_ERROR` de `keycloak_user_events_total` + `vectra_authz_denied_total` de U0 (B1, B3) | 5m |
| `BreakGlassLogin` | SEV1 | ~~Un `LOGIN` del usuario `break-glass` en `keycloak_user_events_total` (B1)~~ **Superada por B10:** un `login` en `keycloak_user_events_total` con `client_id="security-admin-console"`, en cualquier realm | 0m |
| `RealmDrift` | SEV2 | `vectra_realm_drift > 0` (Pushgateway, `job="realm-drift"`) | 0m |
| `RoleConflict` | SEV2 | ~~`increase(vectra_role_conflict_total[15m]) > 0`, `for` 5m~~ **B12:** `increase(vectra_role_conflict_total[15m]) > 0` **o** una serie nueva (`vectra_role_conflict_total > 0 unless vectra_role_conflict_total offset 5m`), **con la guarda de B16**. **Métrica de contrato** (B2): todavía no la emite nada; la fuente sigue en `CANDIDATAS.md` | 0m |
| `SigningKeyAgeHigh` | SEV3 | Edad de `vectra_signing_key_created_timestamp_seconds` > 80 días | 1h |
| `LdapUnavailable` | SEV2 | ~~`increase(vectra_ldap_connection_failures_total[5m]) > 0`, `for` 5m~~ **B12:** `increase(vectra_ldap_connection_failures_total[5m]) > 0` **o** una serie nueva (`vectra_ldap_connection_failures_total > 0 unless vectra_ldap_connection_failures_total offset 5m`), **con la guarda de B16**. **Métrica de contrato** (B2). Una sola regla para todos los entornos: en kind y staging no hay series, así que no dispara (B9) | 0m |
| `GatewayHighLatency` | SEV3 | p95 de `envoy_http_downstream_rq_time` − p95 de `envoy_cluster_upstream_rq_time` > 5 ms, **B14:** el downstream solo del listener HTTP del `api-gateway` y el upstream solo de los clusters de sus rutas (sin el cluster del rate limit ni los listeners de estadísticas y de readiness) | 15m |
| `KeycloakMetricsDown` | SEV2 | `up{job="keycloak"} == 0` o ausente (B11) | 5m |
| `RealmDriftStale` | SEV3 | `time() - push_time_seconds{job="realm-drift"} > 26h`, **o** ausente el grupo (`absent(push_time_seconds{job="realm-drift"})`, B13; **B17**: `absent_over_time(...[10m])` con el Pushgateway arriba). El CronJob corre a diario (B8); runbook `realm-drift` | 0m |
| `SigningKeyAgeStale` | SEV3 | `time() - push_time_seconds{job="signing-key-age"} > 3h`, **o** ausente el grupo (`absent(push_time_seconds{job="signing-key-age"})`, B13; **B17**: `absent_over_time(...[10m])` con el Pushgateway arriba). El CronJob corre cada hora (B8); runbook `signing-key-rotation` | 0m |

- **B11** (2026-11-05, decisión del usuario tras la ronda 2 de revisión de U02-T13; `revisiones/U02-T13/ronda-2.md`). Con el contador de eventos, un login aislado no se detecta bien en Prometheus. Rige:
  - **`BreakGlassLogin`**: con `X` el contador de B10 y `N = (X > 0 unless X offset 5m)`, la expresión es `(increase(X[5m]) > 0) or (N > (last_over_time(X[1h] offset 5m) or X * 0)) or (N and on(namespace, pod) (up{job="keycloak"} offset 5m == 1))`. Así una serie que no se vio en la última hora cuenta como login nuevo;
  - **límites aceptados**: un falso positivo si el hueco de scrape dura más de 1 h, y una omisión si el pod se reinicia durante el hueco y luego hay un login. El runbook `break-glass-login` los describe tal como se midieron;
  - **alerta nueva `KeycloakMetricsDown`**, SEV2, `for` 5m: `up{job="keycloak"} == 0` o ausente (`absent(up{job="keycloak"})`). Runbook `keycloak-metrics-down`. Sin ella, `BreakGlassLogin` puede quedar ciega sin que nadie lo sepa.
- **B1**: la imagen de Keycloak activa las métricas de eventos de usuario (`user-event-metrics`), con lo que existe `keycloak_user_events_total`. La opción y si es de build se comprueban en la documentación y el código de 26.8.1.
- **B10** (2026-11-05, decisión del usuario tras la parada de la ronda 1 de U02-T13). La métrica de 26.8.1 emite `event`, `error`, `realm`, `idp` y `client_id`, pero no el usuario: `MicrometerUserEventMetricsEventListenerProvider.java`. Por eso `BreakGlassLogin` no puede filtrar por `break-glass` y dispara con cualquier `login` en `security-admin-console`. Las razones:
  - en prod, `break-glass` es el único humano con `realm-admin`;
  - `keycloak-config-cli` también tiene `realm-admin`, pero entra por `client_credentials` y emite `client_login`, no `login`;
  - la consola solo se alcanza por `hostname-admin` interno, con port-forward aprobado (BR-U2-12).

  Cualquier otro humano que entre ahí también es SEV1.

  **Corrección del 2026-11-05 (orquestador, tras la ronda 1 de U02-T13).** En `EventOptions.java` de 26.8.1, `event-metrics-user-enabled` es de build (`buildTime(true)`), pero `event-metrics-user-tags` es de ejecución (`buildTime(false)`), y `kc.sh build` lo ignora. Por eso:
  - `--event-metrics-user-enabled=true` va en el `kc.sh build` de la imagen;
  - `KC_EVENT_METRICS_USER_TAGS=realm,clientId` va en el `extraEnv` de `identity-edge/keycloak/values/common.yaml`, el arranque de los tres entornos.

  La expresión de la alerta precisa dos cosas:
  - `error=""`, porque `LOGIN_ERROR` también se emite como `event="login"`;
  - una rama para la primera muestra de una serie nueva, porque `increase` no la ve.
- **B2**: `RoleConflict` y `LdapUnavailable` se escriben contra nombres de métrica de contrato y se prueban con series sintéticas. Su fuente queda pendiente en `CANDIDATAS.md`; para `ROLE_CONFLICT`, ver BR-U2-17.
- **B5**: los `ServiceMonitor`/`PodMonitor` de Keycloak (HTTPS, 9000), Envoy (19001), `envoy-ratelimit` (19001) y el exportador de Valkey (9121) son del Paso 11 y viven en `identity-edge/observability/`. Cada familia de métricas de las reglas tiene quien la emita, un monitor o una fuente de U1 (kube-state-metrics, Pushgateway), y un puerto F60.
- **B6**: el `PrometheusRule` sigue el patrón de U1: un archivo de grupos que leen promtool y las pruebas, más el CR en `vectra-observability`, con la prueba de que los dos tienen los mismos `groups`. El Paso 12 suma las entradas `identity-rules` e `identity-monitors` en wave 4.
- **B7**: el runbook operativo de la vuelta de la primaria de Valkey a la zona A (INF-U2-04) es del Paso 11. No tiene alerta y se valida con `test_runbooks.py --operational`.

#### Endurecimiento de las alertas (enmienda del 2026-11-06, decisiones B12–B15 del usuario tras revisar el PR 71)

La revisión de código del PR 71 (U02-T13) encontró que la tabla, aplicada al pie de la letra, deja alertas que callan. Rige lo siguiente; lo aplica U02-T17:

- **B12** (`LdapUnavailable`, `RoleConflict`): `increase` no ve la primera muestra de una serie que nace con el primer evento, y en `LdapUnavailable` una ventana de 5m con `for` 5m no dispara con un fallo corto. Las dos llevan la rama de serie nueva (`X > 0 unless X offset 5m`, la misma de B11) y `for` 0m.
- **B13** (`RateLimitBackendDown`, `RealmDriftStale`, `SigningKeyAgeStale`): una serie ausente no es un valor 0, y la comparación no devuelve nada. Cada una lleva `or absent(...)` sobre la serie de la que depende: la del Deployment `envoy-ratelimit` y la del StatefulSet de Valkey en kube-state-metrics, y `push_time_seconds` de cada grupo del Pushgateway. En kind, si los CronJobs no corren, las dos `*Stale` disparan: es lo esperado y lo dice el runbook.
- **B14** (`GatewayHighLatency`): la suma de todos los listeners y clusters de Envoy mezcla las llamadas gRPC al rate limit y los listeners de estadísticas y de readiness. El p95 de downstream se filtra al listener HTTP del `api-gateway` y el de upstream a los clusters de sus rutas. Los nombres de las etiquetas (`envoy_http_conn_manager_prefix`, `envoy_cluster_name` u otros) y sus valores se confirman en Envoy Gateway v1.9.3 antes de escribirlos.
- **B15** (`BreakGlassLogin`): se acepta como límite el reinicio normal del pod, medido en U02-T13 (escenarios `RN_0` a `RN_6` del runbook `break-glass-login`). Si el login cae en el mismo scrape en que vuelve el pod y el contador ya valía 1, no dispara; de 1 a 4 min después, dispara con retraso. Queda junto a los límites de B11. La solución en la fuente (ruler de Loki sobre el evento `LOGIN`) sigue en `CANDIDATAS.md`.

- **B16** (2026-11-07, decisión del usuario tras la revisión de código del PR 74; enmienda B12). La rama de serie nueva sola (`X > 0 unless X offset 5m`, `for` 0m) también dispara cuando un contador que ya valía más de 0 vuelve después de un hueco de scrape de 5 min o más, sin ningún fallo nuevo. `LdapUnavailable` y `RoleConflict` llevan la misma guarda que `BreakGlassLogin` en B11: `(increase(X[w]) > 0) or (N > (last_over_time(X[1h] offset 5m) or X * 0)) or (N and on(job, instance) (up offset 5m == 1))`, con `N = (X > 0 unless X offset 5m)` y `w` la ventana de cada una (15m y 5m). El `on(...)` se une por las etiquetas del target que raspa la serie. Como la fuente de las dos métricas está en `CANDIDATAS.md`, se fijan `job` e `instance`, y promtool comprueba la unión. Valen los mismos límites aceptados de B11.
- **B17** (2026-11-07, misma decisión; enmienda B13). Con `for` 0m, un `absent()` dispara con un solo scrape fallido, y la falla del exportador se informa como falla del componente. Las ramas por ausencia de B13 pasan a `absent_over_time(serie[10m])` y se condicionan a que el exportador esté arriba (`and on() (up{job="<exportador>"} == 1)`): kube-state-metrics para `RateLimitBackendDown`, el Pushgateway para las dos `*Stale`. La caída del exportador la informa su propia alerta: `PushgatewayDown` de U1 para el Pushgateway. La caída de kube-state-metrics la informa `KubeStateMetricsDown`, una alerta nueva de U1 (SEV2, `for` 5m), porque `defaultRules` del chart está apagado (ampliación del 2026-11-07, decisión del usuario).

## 5. Cumplimiento de extensiones (NFR Design U2)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-05 / 07 / 15 | Cumple | P-U2-09 |
| RESILIENCY-06 | Cumple | P-U2-04 |
| RESILIENCY-08 | Cumple | P-U2-04 |
| RESILIENCY-09 | Cumple | P-U2-04: HPA de 2 a 4 réplicas para Keycloak (el HPA de Envoy, de 2 a 6, está en NFR-U2-03) |
| RESILIENCY-10 | Cumple | P-U2-01, 02, 03 |
| SECURITY-02 / 03 | Cumple | P-U2-07 |
| SECURITY-04 | Cumple | P-U2-08 |
| SECURITY-11 | Cumple | P-U2-06 |
| SECURITY-12 | Cumple | P-U2-05 |
| SECURITY-14 | Cumple | P-U2-09 |
| SECURITY-15 | Cumple | P-U2-01 |
| AUTONOMIA-01 | Cumple | Rotación de llaves y realm por PR + sync manual; verificaciones en kind por el operador |
| AUTONOMIA-02 | Cumple | Cada patrón, de P-U2-01 a P-U2-09, tiene su línea de «Verificación» con un comando o un escenario concreto |
| AUTONOMIA-05 | Cumple | P-U2-07 (access log sin datos de solicitantes) |
