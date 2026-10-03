# Requisitos no funcionales — U2 `identity-edge`

Decisiones del plan (`identity-edge-nfr-requirements-plan.md`, Q1–Q9 = A). Las
verificaciones «en kind» las ejecuta el operador después de un PR aprobado (AUTONOMIA-01,
como en U1); las demás corren en CI.

Los IDs `NFR-U2-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Disponibilidad

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U2-01 | Keycloak: 2 réplicas repartidas por zona, PDB y HPA de 2 a 4 por CPU; clúster Infinispan embebido con descubrimiento `jdbc-ping` sobre `keycloak-db` | `helm template` + `conftest` (réplicas, spread, PDB, HPA, `cache-stack`) |
| NFR-U2-02 | **Sesiones de usuario persistentes** en `keycloak-db`: perder un pod o una zona no cierra las sesiones activas | En kind: login → borrar el pod que atendió la sesión → el refresh sigue funcionando |
| NFR-U2-03 | Envoy (data plane): ≥ 2 réplicas repartidas por zona, PDB y HPA de 2 a 6 por CPU. Controlador de Envoy Gateway: 2 réplicas con elección de líder | `helm template` + `conftest` |
| NFR-U2-04 | Si el controlador de Envoy Gateway cae, el data plane sigue sirviendo con la última configuración | En kind: escalar el controlador a 0 → las rutas siguen respondiendo |
| NFR-U2-05 | **Impacto de una caída de Keycloak**: no hay logins nuevos ni refresh; los access tokens vigentes (≤ 5 min) y la cache de JWKS de los servicios (10 min, U0) mantienen la operación en curso; las identidades de servicio fallan al renovar → los servicios devuelven `dependency_unavailable` y la ruta de recomendación sale como fail-closed. Keycloak con todas sus réplicas caídas = **SEV1** | Escenario documentado para Operations (RESILIENCY-14 = C); regla `KeycloakDown` probada con `promtool` |

## 2. Rendimiento (Q3, Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U2-10 | Con 200 usuarios concurrentes y 8 identidades de servicio renovando cada 5 min: login p95 ≤ 500 ms, endpoint de token p95 ≤ 200 ms, JWKS p95 ≤ 50 ms | Prueba de carga en kind (k6 o Locust) ejecutada por el operador, con el reporte adjunto al PR |
| NFR-U2-11 | Sobrecosto del gateway (TLS + JWT + rate limit + cabeceras) p95 ≤ 5 ms por request | La misma prueba, comparando la latencia con y sin gateway hacia un backend de eco |
| NFR-U2-12 | El rate limiting global agrega p95 ≤ 2 ms (llamada al servicio de rate limit + Redis) | Métrica del servicio de rate limit en la prueba de carga |

## 3. Seguridad

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U2-20 | **Rate limiting global** con el servicio de rate limit de Envoy y Redis: los límites de BR-U2-08 son exactos sin importar el número de réplicas | Q5 | En kind: 3 réplicas de Envoy, 25 req/s del mismo usuario → ~5 req/s rechazadas con 429 en total, no por réplica |
| NFR-U2-21 | **Comportamiento si Redis no responde**: *fail-open* en `/api/console/**` e `/api/intake/**` (los servicios siguen autenticando y autorizando); *fail-closed* en `/auth/**` (login y token devuelven 503), además del bloqueo de Keycloak. **Pendiente de NFR Design**: confirmar que Envoy Gateway permite el modo de fallo por política; si no, se separan las rutas de `/auth/**` en una política propia | Q5 | En kind: Redis caído → consola 200, login 503 |
| NFR-U2-22 | Certificado del borde emitido por la CA del banco (cert-manager + `ClusterIssuer` del banco) en staging y prod; la CA interna de U1 en kind. TLS ≥ 1.2, 1.3 preferido, suites *intermediate* de Mozilla, OCSP stapling si la CA lo soporta | Q6, SECURITY-01 | `testssl.sh` o `sslyze` contra el gateway: sin TLS 1.0/1.1 ni suites débiles |
| NFR-U2-23 | IP real del cliente: `externalTrafficPolicy: Local` o PROXY protocol v2; Envoy confía en `X-Forwarded-For` solo desde el balanceador (1 salto); Keycloak con `proxy-headers=xforwarded` | Q7 | En kind: request con `X-Forwarded-For: 1.2.3.4` falso → el evento de Keycloak y el access log registran la IP real |
| NFR-U2-24 | Política de contraseñas de usuarios locales: longitud ≥ 14, distinta del usuario y del email, historial de 5, Argon2, sin vencimiento periódico; `break-glass` se rota tras cada uso | Q8, SECURITY-12 | `realm-lint` verifica la `passwordPolicy` del realm |
| NFR-U2-25 | Imágenes de Keycloak, Envoy, rate limit y Redis pinneadas por digest y firmadas (políticas de U1) | SECURITY-10 | `kyverno test` de U1 sobre los manifiestos de U2 |
| NFR-U2-26 | Keycloak en modo producción (`start --optimized`), sin proveedores ni temas de terceros no aprobados; la consola de administración solo en `hostname-admin` interno (BR-U2-12) | SECURITY-09 | `conftest` sobre los args del Deployment; prueba de ruta `/auth/admin` → 404 |
| NFR-U2-27 | Redis sin persistencia (contadores efímeros), con autenticación (ACL con contraseña desde ESO), sin exponerse fuera de `vectra-edge` | SECURITY-07, 12 | `conftest` (sin AOF/RDB, ACL configurada) + flujo en `flows.yaml` |

## 4. Escalabilidad

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U2-30 | Keycloak y Envoy escalan por HPA (NFR-U2-01, 03); Redis no escala horizontalmente (una primaria + 1 réplica + 3 Sentinel), suficiente para los contadores de un volumen de decenas de req/s | Prueba de carga NFR-U2-10 sin saturación de Redis (CPU < 50 %) |

## 5. Pruebas (Q9, PBT-09)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U2-40 | `realm-lint`, `route-gen` y sus modelos con Python 3.12 + pytest + Hypothesis; PBT-U2-01..07 con el perfil `ci` (500 ejemplos, semilla impresa) | `HYPOTHESIS_PROFILE=ci pytest identity-edge/tests` |
| NFR-U2-41 | Manifiestos del gateway validados con `kubeconform` y los CRDs de Gateway API y Envoy Gateway | `kubeconform -schema-location … identity-edge/gateway/generated/` |
| NFR-U2-42 | Extremo a extremo con Playwright + `httpx` (login, TOTP con `pyotp`, step-up, bloqueo, cabeceras, 429, 404 de `/auth/admin`) y PBT-U2-08 (modelo de fuerza bruta), en kind, ejecutados por el operador | Reporte de Playwright adjunto al PR |

## 6. Cambios requeridos al inventario de `component-dependency.md`

El rate limiting global (Q5) agrega componentes y flujos que el inventario no tiene. Se
formalizan en el **Infrastructure Design de U2**:
- servicio de rate limit de Envoy y Redis (primaria, réplica, Sentinel) en `vectra-edge`;
- flujos Envoy → servicio de rate limit, servicio de rate limit → Redis, replicación Redis y Sentinel.

## 7. Cumplimiento de extensiones (NFR Requirements U2)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | Keycloak y gateway en criticidad High (U1); NFR-U2-05 describe el impacto de la caída |
| RESILIENCY-03 / 04 | Cumple | Realm aplicado con `keycloak-config-cli` como hook de un sync manual (U2 FD Q10, BR-U2-12; `tech-stack-decisions.md`, fila «Realm como código») |
| RESILIENCY-05 / 07 | Cumple | NFR-U2-05: regla `KeycloakDown` (SEV1) probada con `promtool` |
| RESILIENCY-06 | Cumple | Readiness de Keycloak = su base (`keycloak-db`), según P-U1-04 |
| RESILIENCY-08 / 09 | Cumple | NFR-U2-01, 03, 30 |
| RESILIENCY-10 | Cumple | NFR-U2-21 (modo de fallo de Redis por ruta) |
| RESILIENCY-14 | Cumple | NFR-U2-05: escenario de caída de Keycloak documentado para Operations (decisión del proyecto = C) |
| RESILIENCY-15 | Cumple | NFR-U2-05: `KeycloakDown` = SEV1, dentro del proceso de severidades, runbooks y COE de U1 (P-U1-10) |
| SECURITY-01 | Cumple | NFR-U2-22 |
| SECURITY-02 | Cumple | Access log del gateway (BR-U2-14, Loki) |
| SECURITY-04 / 09 / 11 / 12 | Cumple | NFR-U2-20, 24, 26 y el FD de U2 |
| SECURITY-07 | Cumple | NFR-U2-27: Redis sin exponerse fuera de `vectra-edge`, con su flujo en `flows.yaml` |
| SECURITY-08 | Cumple | Modelo de roles y step-up de U2 FD: un rol de negocio por usuario (BR-U2-01), MFA por rol (BR-U2-03), step-up para firmar (BR-U2-04), JWT validado en el gateway como primera capa (BR-U2-11) |
| SECURITY-10 | Cumple | NFR-U2-25 |
| SECURITY-14 | Cumple | `AuthDeniedBurst`, `BreakGlassLogin`, `RealmDrift` y `RoleConflict` (U2 FD, BR-U2-17); `KeycloakDown` (NFR-U2-05) |
| SECURITY-15 | Cumple | NFR-U2-21: fail-closed en `/auth/**` y fail-open acotado a consola e ingesta si Redis falla; NFR-U2-05: caída de Keycloak → fail-closed en la ruta de recomendación |
| PBT-06 | Cumple | NFR-U2-42: PBT-U2-08, modelo de estados de la fuerza bruta, en kind |
| PBT-08 | Cumple | NFR-U2-40: perfil `ci` con la semilla impresa |
| PBT-09 | Cumple | NFR-U2-40 (Hypothesis) |
| PBT-10 | Cumple | NFR-U2-42: pruebas de extremo a extremo de ejemplo (login, TOTP, step-up, bloqueo, cabeceras, 429, 404 de `/auth/admin`) junto a las propiedades |
| AUTONOMIA-01 / 02 | Cumple | Verificaciones estáticas en CI y en kind por el operador, cada una con su comando |
