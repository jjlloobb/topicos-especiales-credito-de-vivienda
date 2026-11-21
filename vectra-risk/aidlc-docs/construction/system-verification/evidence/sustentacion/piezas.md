# Qué objeto de Kubernetes implementa cada pieza

Detalle de la sección 2 del `README.md` raíz. Pedido de `modulo8/guia-entrega-proyecto-final.md`, sección 3.2. Las rutas son relativas a la raíz del repositorio. Contado el 21 de noviembre de 2026.

Cada pieza llega al clúster por una `Application` de Argo CD. En `vectra-risk/vectra-risk-gitops/apps/kind/` hay 56, más un `AppProject` (`project.yaml`), repartidas en 7 waves (0 a 6). Ninguna tiene `syncPolicy.automated`.

| Pieza (unidad) | Objetos de Kubernetes | Manifiesto |
|---|---|---|
| Namespaces y Pod Security (U1) | `Namespace` con `pod-security.kubernetes.io/enforce: restricted` | `vectra-risk/platform/namespaces/` |
| Admisión (U1) | 19 `ClusterPolicy` de Kyverno: sin `latest`, sin privilegiados, sin `hostPath`, sin comodines en RBAC, sin auto-sync, registros permitidos | `vectra-risk/platform/policies/kyverno/` |
| Red y malla (U1) | `NetworkPolicy`, y `Server` y `AuthorizationPolicy` de Linkerd, generados desde una lista de 119 flujos | `vectra-risk/platform/network/flows.yaml` |
| Datos (U1) | `Cluster` de CloudNativePG; MinIO con object lock | `vectra-risk/platform/data/` |
| Secretos (U1) | `ExternalSecret` y `ClusterSecretStore` contra Vault | `vectra-risk/platform/secrets/` |
| Observabilidad (U1) | `PrometheusRule`, `ServiceMonitor`, Pushgateway, runbooks | `vectra-risk/platform/observability/` |
| Identidad y borde (U2) | Keycloak, Valkey (`StatefulSet`), Envoy Gateway (`Gateway`, `HTTPRoute`, `SecurityPolicy`), rate limit | `vectra-risk/identity-edge/` |
| Registro de decisiones (U3) | `Deployment`, `HorizontalPodAutoscaler`, `PodDisruptionBudget`, `CronJob`, `Job` | `vectra-risk/decision-registry/chart/` |
| Gobierno de modelos (U4) | `Deployment`, `Job` de validación, `Role` y `RoleBinding`, `ExternalSecret` | `vectra-risk/governance/chart/` |
| Servicio del modelo (U5, U6) | `InferenceService` de KServe (predictor y explicador), `PodDisruptionBudget` | `vectra-risk/model-serving/chart/` |
| Scoring y explicación (U7) | `Deployment`, `HorizontalPodAutoscaler`, `PodDisruptionBudget` | `vectra-risk/scoring-explainability/chart/` |
| Casos y mock del core bancario (U8) | 3 `Deployment`, `Job` de migración, `PrometheusRule` | `vectra-risk/case-management/chart/` |
| Monitoreo de sesgo (U9) | `CronJob`, `Deployment` | `vectra-risk/bias-monitoring/chart/` |
| Consola web (U10) | 2 `Deployment` (SPA y BFF) | `vectra-risk/console/chart/` |
| Métricas de producto (U11) | `Deployment`, `PrometheusRule`, tablero de Grafana en `ConfigMap` | `vectra-risk/product-metrics/chart/` |
| Identidad de los agentes (U1) | `ServiceAccount`, `ClusterRole`, `ClusterRoleBinding` | `vectra-risk/platform/rbac/readonly-agent/readonly-agent-kind.yaml` |
| Servidor MCP `vectra-lectura` (loop) | Ninguno: es un proceso por stdio en la estación. Usa la `ServiceAccount` `vectra-readonly-agent` | `vectra-risk/loop/mcp-solo-lectura/`, `.mcp.json` |

Lo que no es un objeto del clúster:

- **U0** (`vectra-risk/contracts/`): contratos compartidos entre unidades.
- **U5** (`vectra-risk/reference-model/`): genera el modelo de referencia y los datos sintéticos; su salida la sirve U6.
- **U12** (`vectra-risk/system-verification/`): la herramienta de verificación. Corre fuera del clúster, en un contenedor, y solo lee.

Cómo comprobarlo: `grep -rhoE "^kind: \w+" vectra-risk/<unidad>/chart | sort | uniq -c` lista los tipos de cada chart.
