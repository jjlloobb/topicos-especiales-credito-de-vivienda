# Infraestructura compartida — Vectra Risk

Lo que U1 `platform-foundation` provee a las demás unidades. Cada unidad la **consume**
desde su chart y su Infrastructure Design; no la redefine. Fuente:
`construction/platform-foundation/infrastructure-design/`.

---

## 1. Qué recibe cada unidad

| Recurso | Cómo se consume | Unidades |
|---|---|---|
| Namespace con deny-all y PriorityClass | El chart declara `namespace` y `priorityClassName` | Todas las que despliegan |
| Flujos de red | Cada unidad agrega sus flujos a `platform/network/flows.yaml` por PR; el generador produce NetworkPolicies y políticas de Linkerd | U2–U12 |
| mTLS (Linkerd) | Anotación de inyección en el namespace; identidad = ServiceAccount | U2–U12 |
| Cluster de PostgreSQL | Un `Cluster` de CloudNativePG por base; la unidad dueña provee el esquema, las migraciones (F44) y los roles (§4 de `component-dependency.md`) | U3 (`registry-db`), U4 (`governance-db`), U8 (`case-db`), U2 (`keycloak-db`) |
| Buckets de MinIO | Credenciales por ESO; un bucket por propósito | U4/U6 (`model-store`), U4 (`validation-datasets`) |
| Secretos | `ExternalSecret` en el chart de la unidad | Todas |
| Certificados | `Certificate` de cert-manager (borde y PostgreSQL) | U2 (gateway), U3/U4/U8 (TLS a PostgreSQL) |
| Métricas | Endpoint `/metrics` en el puerto 8081 (U0); `ServiceMonitor` en el chart | Todas |
| Trazas y logs | OTLP al Collector (U0); stdout JSON recogido por Alloy | Todas |
| Alertas y runbooks | `PrometheusRule` con `severity` y `runbook_url` hacia `platform/runbooks/` | Todas |
| Políticas de admisión | Las cargas cumplen las políticas de Kyverno (digest firmado, `runAsNonRoot`, límites, prioridad, spread y PDB) | Todas |
| CI | Workflows reutilizables `tests`, `supply-chain`, `evidence`, `forbidden-steps`, `policies` | Todas (incluida U0, que reemplaza su job provisional de auditoría de dependencias) |
| GitOps | Una `Application` por componente en la wave que le corresponde | Todas |

## 2. Reglas para las unidades consumidoras

- No crear Services `LoadBalancer` (solo el api-gateway de U2).
- No crear NetworkPolicies ni políticas de Linkerd a mano: se generan desde `flows.yaml`.
- No guardar Secrets en Git: solo `ExternalSecret`.
- Toda carga declara `priorityClassName`, recursos, `topologySpreadConstraints` y PDB, o Kyverno la rechaza.
- La readiness sigue P-U1-04: solo dependencias propias sin causa tipificada de fail-closed.

## 3. Valores por defecto

| Parámetro | Valor | Origen |
|---|---|---|
| Réplicas mínimas por servicio | 2 | NFR-U1-04 |
| Conexiones a PostgreSQL por pod | ≤ 5 | P-U1-08 |
| Retención de logs / métricas / trazas | 90 / 30 / 7 días | NFR-U1-30, 31 |
| PITR | 30 días | NFR-U1-06 |
| `archive_timeout` | 60 s | NFR-U1-05 |

## 4. Lo que provee U2 `identity-edge`

| Recurso | Cómo se consume | Unidades |
|---|---|---|
| Hostname único por entorno (INF-U2-01) | La SPA y los servicios construyen URLs relativas al mismo origen | U10, U11 |
| Rutas del gateway | Una unidad que expone algo hacia afuera agrega su entrada a `identity-edge/gateway/routes.yaml` por PR; `route-gen` genera rutas, JWT, límites y cabeceras | U3, U4, U8, U10 (vía BFF) |
| Clientes de Keycloak | Cada identidad de servicio nueva se agrega a `realm.{env}.yaml` con sus scopes del catálogo de U0; la llave privada la entrega ESO | Todas las que llaman a otros servicios |
| JWKS interna | `https://keycloak.vectra-identity.svc:8443/auth/realms/vectra/protocol/openid-connect/certs` (U0 `authn`) | Todas |
| Step-up | Los endpoints con firma declaran `mfa=True` en su `RouteContract` (U0); la SPA maneja `mfa_required` (BR-U2-04) | U4, U8, U10 |
