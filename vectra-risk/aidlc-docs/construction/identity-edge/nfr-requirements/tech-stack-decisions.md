# Decisiones de stack — U2 `identity-edge`

Decisiones del plan (`identity-edge-nfr-requirements-plan.md`, Q1–Q9 = A). Las versiones
exactas se pinnean por digest en los values del repositorio GitOps.

---

| Área | Decisión | Motivo | Origen |
|---|---|---|---|
| IdP | Keycloak 26.x (imagen oficial, Quarkus), modo producción `start --optimized` | IdP de INCEPTION; sesiones persistentes nativas | INCEPTION, Q1 |
| Despliegue de Keycloak | Chart `keycloakx` (codecentric) | Encaja en Helm + Argo CD sin operador ni bindings nuevos | Q1 |
| Clúster de Keycloak | Infinispan embebido + `jdbc-ping` sobre `keycloak-db` | Sin componentes extra de descubrimiento | Q2 |
| Realm como código | `keycloak-config-cli` como hook de sync | Idempotente; cambios solo por PR | U2 FD Q10 |
| Gateway | Envoy Gateway (Gateway API) | INCEPTION | INCEPTION |
| Rate limiting | Servicio de rate limit de Envoy (`envoyproxy/ratelimit`) + **Redis** con Sentinel | Límites exactos con varias réplicas | Q5 |
| TLS del borde | cert-manager + `ClusterIssuer` de la CA del banco; CA interna de U1 en kind | Certificado de confianza en los navegadores del banco | Q6 |
| IP de origen | `externalTrafficPolicy: Local` o PROXY protocol v2 | Límite por IP y eventos con la IP real | Q7 |
| Hash de contraseñas | Argon2 (predeterminado de Keycloak 26) | NIST SP 800-63B | Q8 |
| MFA | TOTP (required action) + WebAuthn opcional | U2 FD Q2 | U2 FD |
| Pruebas unitarias y PBT | Python 3.12, pytest, **Hypothesis** | Mismo stack que U0 (PBT-09) | Q9 |
| Extremo a extremo | Playwright + `httpx` + `pyotp` | Login real con TOTP y step-up | Q9 |
| Validación de manifiestos | `kubeconform` con CRDs de Gateway API y Envoy Gateway; `conftest` | Estática, en CI | Q9 |
| Carga | k6 o Locust (a elegir en el plan de tareas) | NFR-U2-10 | Q3 |

## Descartado

| Opción | Motivo |
|---|---|
| Keycloak Operator | Agrega un operador y bindings para un solo Deployment (Q1=B) |
| Sesiones solo en memoria | Una caída de zona cerraría sesiones (Q2=B) |
| Rate limiting local | Los límites se multiplican por réplicas; el de login dejaría de ser un control confiable (Q5=B) |
| CA interna en todos los entornos | Exige distribuir una CA de Vectra a los navegadores del banco (Q6=B) |
| Confiar en `X-Forwarded-For` tal cual | Permite falsear la IP y evadir el límite por IP (Q7=B) |
| Complejidad + vencimiento de 90 días | Contrario a NIST SP 800-63B (Q8=B) |
