# Infraestructura compartida — Vectra Risk

Lo que U1 `platform-foundation` provee a las demás unidades. Cada unidad la **consume**
desde su chart y su Infrastructure Design; no la redefine. Fuente:
`construction/platform-foundation/infrastructure-design/`.

---

## 1. Qué recibe cada unidad

| Recurso | Cómo se consume | Unidades |
|---|---|---|
| Namespace con deny-all y PriorityClass | El chart declara `namespace` y `priorityClassName` | Todas las que despliegan |
| Flujos de red | Los flujos y las rutas viven solo en `platform/network/flows.yaml`. El inventario ya está ahí: cada unidad **verifica** los suyos y agrega por PR solo lo que falte (`http_routes` para la autorización de Linkerd por ruta, con `_catch_all` y `_probes`). El generador produce NetworkPolicies y políticas de Linkerd. Prometheus llega al puerto 8081 de cada pod por el `Server` `metrics-8081` del namespace, sin nada en el chart (revisión de consistencia entre unidades, 2026-11-01) | U2–U12 |
| mTLS (Linkerd) | Anotación de inyección en el namespace; identidad = ServiceAccount | U2–U12 |
| Cluster de PostgreSQL | Un `Cluster` de CloudNativePG por base; la unidad dueña provee el esquema, las migraciones (F44) y los grants; U1 crea los roles (§4 de `component-dependency.md`, INF-U1-02) y entrega a cada consumidor el Secret `pg-role-<rol>` (`roleConsumers` de `platform/data/chart/values.yaml`). Bases: `registry`, `case`, `governance` y `keycloak` (revisión de consistencia entre unidades, 2026-11-01) | U3 (`registry-db`), U4 (`governance-db`), U8 (`case-db`), U2 (`keycloak-db`) |
| Buckets de MinIO | Credenciales `minio-*` por ESO; un bucket por propósito. Las crea U1 (`extraSecrets` de `platform/data/chart/values.yaml`; las exclusivas de kind, en `values-kind.yaml`) y el chart de la unidad solo las monta (revisión de consistencia entre unidades, 2026-11-01) | U4/U6 (`model-store`), U4 (`validation-datasets`) |
| Secretos | U1 es dueña de `pg-role-*` y `minio-*`, para todos sus consumidores; los demás (llaves de cliente de Keycloak y otros propios de la unidad), `ExternalSecret` en el chart de la unidad (revisión de consistencia entre unidades, 2026-11-01) | Todas |
| Certificados | `Certificate` de cert-manager (borde, PostgreSQL y Keycloak, quinta revisión de coherencia entre unidades, 2026-10-31). El certificado público de la CA está en la bóveda y cada cliente de Keycloak lo recibe por su `ExternalSecret` | U2 (gateway y Keycloak), U3/U4/U8 (TLS a PostgreSQL), todos los clientes de F05, F50 y F94 (CA) |
| Métricas | Endpoint `/metrics` en el puerto 8081 (U0; el servicio arranca con `vectra_common.ops_server.run_service`); `ServiceMonitor` en el chart con `honorLabels: true`, para que la etiqueta `service` que emite U0 no pase a `exported_service`. Una regla de la unidad filtra por `job` o por las etiquetas que U0 declara en cada métrica, no por una etiqueta `service` propia: `vectra_circuit_state`, por ejemplo, solo declara `dependency` (revisión de consistencia entre unidades, 2026-11-01) | Todas |
| Trazas y logs | OTLP al Collector (U0); stdout JSON recogido por Alloy | Todas |
| Variables de U0 | `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL` y `VECTRA_CA_BUNDLE` (obligatorias; sin ellas no arranca); `VECTRA_OTLP_ENDPOINT` (con `http://`; sin ella no exporta) y `VECTRA_TRACE_RATIO`; con identidad de servicio, `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y `VECTRA_CLIENT_KEY_ID` (`vectra_common.service_token`; ninguna unidad escribe su propio cliente de `/token`) | Todas |
| API de U0 para servicios | Arranque con `vectra_common.ops_server.run_service(app)`. Token de servicio con `service_token.provider_from_env(audience, scopes)`, pasado como `token_source` a `DependencyClient`; `deps.call` lo envía y reintenta una vez ante un 401. `context.query` trae el `query_model` ya validado; `app_factory.respond` devuelve un 202 o un 304; `DependencyTimeout` es un 504; `Principal.client_id` es el `azp` (revisión de consistencia entre unidades, 2026-11-01) | Todas las que exponen una API o llaman a otro servicio |
| Dashboards | `ConfigMap` en el namespace de la unidad, con la etiqueta `vectra.io/dashboard` y la anotación `grafana_folder`; Grafana los descubre en todos los namespaces (revisión de consistencia entre unidades, 2026-11-01) | U9, U10, U11 |
| Alertas y runbooks | `PrometheusRule` con `severity` y `runbook_url` hacia `platform/runbooks/` | Todas |
| Políticas de admisión | Las cargas cumplen las políticas de Kyverno (digest firmado, `restrict-registries`, `runAsNonRoot`, `readOnlyRootFilesystem` con `emptyDir` donde haga falta, límites, prioridad, `vectra.io/criticality`, spread y PDB); `make -C platform check-chart` las comprueba en el PR, con los values de cada entorno (revisión de consistencia entre unidades, 2026-11-01) | Todas |
| CI | Workflows reutilizables `tests`, `supply-chain`, `evidence`, `forbidden-steps`, `policies` (con el input `path`, el chart de la unidad relativo a `vectra-risk/`, y `namespace`) (revisión de consistencia entre unidades, 2026-11-01) | Todas (incluida U0, que reemplaza su job provisional de auditoría de dependencias) |
| GitOps | Una entrada por componente en `vectra-risk-gitops/components.yaml`, en la wave que le corresponde. `generate.py` escribe `apps/` y `envs/`, así que nada se escribe a mano ahí (`--check` falla). Los values por entorno van en `vectra-risk-gitops/values/<env>/<componente>.yaml`, que se agrega solo. Todo vive en el monorepo, con el prefijo `vectra-risk/` (revisión de consistencia entre unidades, 2026-11-01) | Todas |

## 2. Reglas para las unidades consumidoras

- No crear Services `LoadBalancer` (solo el api-gateway de U2).
- No crear NetworkPolicies, `Server`, `HTTPRoute` ni otras políticas de Linkerd a mano: se generan desde `flows.yaml` (revisión de consistencia entre unidades, 2026-11-01).
- No guardar Secrets en Git: solo `ExternalSecret`.
- Toda carga declara `priorityClassName`, recursos, `topologySpreadConstraints` y PDB, o Kyverno la rechaza.
- Todo `Deployment` y `StatefulSet` de un chart de unidad lleva la etiqueta `vectra.io/criticality` (`critical`, `high` o `medium`). Los que generan KServe y Envoy Gateway no: se la agrega Kyverno (`add-criticality-to-generated`) (revisión de consistencia entre unidades, 2026-11-01).
- Los pods llevan `app.kubernetes.io/name`, con el mismo valor que el selector de su PDB: `require-pdb` los relaciona por esa etiqueta (revisión de consistencia entre unidades, 2026-11-01).
- Un `InferenceService` inactivo lleva la etiqueta `vectra.io/serving-state: inactivo` y la anotación `vectra.io/hpa-exempt`, que lo excluyen de las reglas de 2 réplicas y de PDB. Sin verificar: que KServe propague etiquetas y anotaciones al `Deployment` (Paso 19 de U1) (revisión de consistencia entre unidades, 2026-11-01).
- El HPA se exige sobre el render del PR (regla `hpa.rego`, `make -C platform check-chart`); al admitir solo se audita, así que no tiene que existir antes que el `Deployment` (revisión de consistencia entre unidades, 2026-11-01).
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
