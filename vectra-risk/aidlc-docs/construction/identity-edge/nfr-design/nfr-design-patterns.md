# Patrones de NFR Design — U2 `identity-edge`

Decisiones del plan (`identity-edge-nfr-design-plan.md`, Q1–Q6 = A). Los IDs `P-U2-xx` se
referencian en Infrastructure Design y en el plan de tareas. Las verificaciones en kind las
ejecuta el operador después de un PR aprobado (AUTONOMIA-01).

---

## 1. Resiliencia

### P-U2-01 — Modo de fallo del rate limit por ruta (Q1, NFR-U2-21)

| Ruta | Si Redis o el servicio de rate limit no responden |
|---|---|
| `/auth/**` | **fail-closed**: 503 `dependency_unavailable` (además, el bloqueo de Keycloak sigue activo) |
| `/api/console/**`, `/api/intake/**`, `/api/promotion/**` | **fail-open**: la request sigue; los servicios autentican y autorizan igual (U0) |

**Implementación en orden de preferencia.** Se verifica contra la versión de Envoy Gateway
pinneada en el plan de tareas y se registra en `audit.md` cuál se usó:
1. **Nativa**: dos `BackendTrafficPolicy` (una para `/auth/**` con el modo de fallo cerrado y otra para el resto con fail-open), si la API de la versión pinneada expone ese modo en el rate limit global.
2. **Parche acotado**: una `EnvoyPatchPolicy` que fija `failure_mode_deny: true` **solo** en el filtro de rate limit de la ruta de `/auth/**`. Una prueba sobre la configuración renderizada de Envoy (`egctl config envoy-proxy`) falla si una actualización rompe el parche.
3. **Gateway separado**: `/auth/**` en un `Gateway` propio con un `EnvoyProxy` configurado en fail-closed.

- **Verificación**: en kind, con Redis escalado a 0 → `GET /api/console/me` = 200 y `POST /auth/realms/vectra/protocol/openid-connect/token` = 503.
- **Satisface**: NFR-U2-21; SECURITY-15; RESILIENCY-10.

### P-U2-02 — Timeouts, reintentos y outlier detection (Q4)

| Ruta | Timeout | Reintentos |
|---|---|---|
| `/api/console/**` | 15 s | Solo `GET`/`HEAD`: 1 reintento ante `connect-failure` o `503`, presupuesto del 20 % |
| `/api/intake/**` | 5 s | **Ninguno** (solo `POST`) |
| `/api/promotion/**` | 10 s | Solo el `GET`; el `POST` de activación **nunca** |
| `/auth/**` | 10 s | Solo `GET`/`HEAD` |
| `/grafana/**` | 30 s | Solo `GET`/`HEAD` |

- **Nunca** se reintentan `POST`, `PUT` ni `PATCH`: un reintento podría duplicar una decisión, una aprobación o una solicitud.
- **Outlier detection**: 5 errores 5xx consecutivos sacan un pod del balanceo por 30 s, hasta el 50 % de los pods del backend.
- **Verificación**: `conftest` sobre las `BackendTrafficPolicy` renderizadas (ningún reintento en métodos no idempotentes); en kind, un backend de prueba que devuelve 503 a un `POST` recibe exactamente 1 llamada.
- **Satisface**: RESILIENCY-10; NFR-U2-11.

### P-U2-03 — JWKS en el gateway (Q5)
- El filtro JWT trae la JWKS por la URL **interna** de Keycloak (`keycloak.vectra-identity.svc:8443`, F50), no por el gateway. La refresca cada 5 min y conserva la última válida si Keycloak no responde.
- Esta diferencia con U0, que deja de validar al vencer su cache (P-U0-06), es intencional: el gateway es la primera capa y cada servicio vuelve a validar con las reglas de U0.
- Una llave retirada (P-U2-05) deja de aceptarse en el gateway en ≤ 5 min.
- **Verificación**: en kind, Keycloak caído → el gateway sigue validando tokens vigentes; el servicio de destino responde 503 cuando vence su cache de 10 min.
- **Satisface**: NFR-U2-05; RESILIENCY-10.

### P-U2-04 — Keycloak tolerante a fallos
- 2 réplicas por zona, HPA de 2 a 4, PDB `minAvailable: 1`; Infinispan embebido con `jdbc-ping`; sesiones persistentes en `keycloak-db` (NFR-U2-01, 02).
- Readiness = su base (`keycloak-db`), según P-U1-04. Liveness y readiness en el puerto de gestión (9000), que no se expone en el gateway.
- Redis: primaria + réplica + 3 Sentinel repartidos por zona. Un failover de Sentinel dura segundos y reinicia los contadores, lo que se acepta porque son efímeros.
- **Verificación**: escenario NFR-U2-02 en kind; borrar la primaria de Redis → Sentinel promueve la réplica y el rate limit se recupera.

## 2. Seguridad

### P-U2-05 — Rotación de las llaves de firma (Q3)
- Cada 90 días se agrega por realm como código una llave nueva (RS256 o ES256) con mayor prioridad, que pasa a firmar.
- La anterior queda **pasiva** (publicada en JWKS, sin firmar) durante 24 h y después se desactiva.
- Runbook `signing-key-rotation.md`. Alerta `SigningKeyAgeHigh` (SEV3) a los 80 días, calculada desde la fecha de creación de la llave activa que expone un exportador.
- **Verificación**: en kind, rotación con tokens emitidos antes y después: los dos se aceptan durante el solapamiento y el anterior se rechaza tras desactivar la llave.
- **Satisface**: SECURITY-12; NFR-U2-24.

### P-U2-06 — Claves de rate limit solo de datos verificados (Q2)

| Ruta | Clave del descriptor | Origen |
|---|---|---|
| `/api/console/**`, `/api/promotion/**` | `sub` | Claim del JWT validado, copiado a la cabecera interna `x-vectra-sub` |
| `/api/intake/**` | `azp` | Claim del JWT validado, copiado a `x-vectra-azp` |
| `/auth/**` | IP de origen | Dirección que fija Envoy desde el balanceador de confianza (NFR-U2-23) |

- Las cabeceras internas se **eliminan** de la request entrante antes del filtro JWT (un cliente no puede inyectarlas) y otra vez antes de enviar la request al backend.
- **Verificación**: en kind, un cliente que manda `x-vectra-sub: otro` no cambia su contador; el backend de eco no recibe las cabeceras internas.
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
- Objetivo WCAG 2.1 AA: contraste, etiquetas de formulario y foco visible.
- **Verificación**: Playwright + `axe-core` sobre las páginas de login, TOTP y cambio de contraseña sin violaciones serias ni críticas; prueba de que el tema no carga recursos de otro origen.
- **Satisface**: NFR-USA-01; SECURITY-04.

## 4. Observabilidad

### P-U2-09 — Métricas y alertas de U2

| Alerta | Severidad | Fuente |
|---|---|---|
| `KeycloakDown` | SEV1 | Ninguna réplica lista |
| `RateLimitBackendDown` | SEV2 | Servicio de rate limit o Redis sin respuesta (con `/auth/**` en fail-closed) |
| `AuthDeniedBurst` | SEV2 | Eventos de Keycloak + 401/403 de U0 |
| `BreakGlassLogin` | SEV1 | Evento de login del usuario `break-glass` |
| `RealmDrift` | SEV2 | CronJob de comparación del realm |
| `RoleConflict` | SEV2 | Evento de la federación LDAP |
| `SigningKeyAgeHigh` | SEV3 | Exportador de antigüedad de llaves |
| `LdapUnavailable` | SEV2 | Fallos de conexión de la federación LDAP (solo prod; agregado en INF-U2-07) |
| `GatewayHighLatency` | SEV3 | Sobrecosto de p95 > 5 ms sostenido 15 min (NFR-U2-11) |

- Keycloak expone métricas en el puerto de gestión (9000); Envoy y el servicio de rate limit, sus estadísticas. Todos llevan `ServiceMonitor` y su flujo de scrape en `flows.yaml`.
- Toda alerta tiene `runbook_url` (P-U1-10).
- **Verificación**: `promtool test rules identity-edge/observability/rules/tests/*.yaml` (cada alerta se dispara con series sintéticas) y el test de runbooks de U1 (`severity` válida y `runbook_url` hacia un archivo existente).

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
