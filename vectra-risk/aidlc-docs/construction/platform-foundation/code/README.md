# Código de U1 `platform-foundation`

Raíces de código: `platform/`, `vectra-risk-gitops/`, `.github/workflows/`, `.github/actions/`

| Componente | Archivos | Verificación | Diseño |
|---|---|---|---|
| Kind | `platform/kind/` | `test_platform.py` | INF-U1-01, INF-U1-04, INF-U1-05, INF-U1-09; NFR-U1-24 |
| Red | `platform/network/` | `network/tests/test_flows.py`, `generate.py --check` | NFR-U1-20, NFR-U1-34; P-U1-01, P-U1-02; INF-U1-06 |
| Malla y certificados | `platform/mesh/` | `test_platform.py` | NFR-U1-21, NFR-U1-22; P-U1-03, P-U1-06, P-U1-14 |
| Políticas | `platform/policies/kyverno/`, `policies/rbac/`, `policies/rego/` | `kyverno test`, `conftest`, `platform/tests/rego_fixtures.py` | NFR-U1-04, NFR-U1-12, NFR-U1-25, NFR-U1-27, NFR-U1-43; P-U1-09 |
| Cuotas | `platform/policies/quotas/` | `test_platform.py` | NFR-U1-13 |
| PostgreSQL | `platform/data/chart/` | `test_platform.py` | NFR-U1-02, NFR-U1-03, NFR-U1-05, NFR-U1-06, NFR-U1-23; INF-U1-02; P-U1-04, P-U1-08 |
| MinIO | `platform/data/minio/` | `test_platform.py`, `test_upstream_charts.py`, `test_integration.py` | INF-U1-03; NFR-U1-30 |
| Secretos | `platform/secrets/`, `platform/operators/external-secrets.yaml` | `test_platform.py`, `test_upstream_charts.py` | NFR-U1-24; INF-U1-10 |
| Observabilidad | `platform/observability/` | `test_platform.py`, `test_upstream_charts.py`, `test_folder_permissions.py`, `test_grafana_folder_permissions.py`, `promtool` | NFR-U1-31, NFR-U1-32, NFR-U1-33; INF-U1-07, INF-U1-08; P-U1-07, P-U1-10, P-U1-11, P-U1-13 |
| Simulacro | `platform/restore-drill/` | `test_drill.py` | NFR-U1-07; P-U1-05 |
| Runbooks | `platform/runbooks/`, `platform/docs/` | `test_platform.py` | NFR-U1-01, NFR-U1-08, NFR-U1-10 |
| Carga | Diferida a `system-verification` | Sección `load` | NFR-U1-11 |
| GitOps | `vectra-risk-gitops/`, `platform/operators/` | `test_platform.py`, `generate.py --check` | P-U1-12 |
| Integración entre piezas | `platform/tests/integration.py`, `platform/resolve_digest.py` | `test_integration.py`, `make -C platform check-integration` | NFR-U1-25; P-U1-01, P-U1-13 |
| CI | `.github/workflows/`, `.github/actions/` | `test_ci.py`, `test_platform.py`, `actionlint` | NFR-U1-26, NFR-U1-40, NFR-U1-41, NFR-U1-42, NFR-U1-44 |

## Identificadores sin mención en el código

Lo que `platform/tests/test_traceability.py` no encuentra citado en las raíces: aquí se nombra el archivo que lo implementa.

| Identificador | Archivo | Qué contiene |
|---|---|---|
| INF-U1-06 | `vectra-risk-gitops/components.yaml` | `system_namespaces` y el namespace de cada controlador |
| INF-U1-08 | `platform/network/flows.yaml` | F09 (federación, deshabilitada) y F72, la única salida de alertas |
| NFR-U1-02 | `platform/data/chart/templates/clusters.yaml` | 3 instancias, anti-afinidad y réplicas síncronas |
| NFR-U1-04 | `platform/policies/kyverno/require-spread-and-pdb.yaml` | Réplicas, reparto por zona y PDB |
| NFR-U1-05 | `platform/data/chart/templates/clusters.yaml` | `archive_timeout` y `ScheduledBackup` |
| NFR-U1-06 | `platform/data/chart/templates/clusters.yaml` | `retentionPolicy`; el object lock está en `platform/data/minio/values.yaml` |
| NFR-U1-08 | `platform/runbooks/zone-failover.md` | Failover de zona y vuelta a dos zonas |
| NFR-U1-20 | `platform/network/generate.py` | NetworkPolicies deny-all y los flujos de `flows.yaml` |
| NFR-U1-23 | `vectra-risk-gitops/envs/prod/values.yaml` | StorageClass cifrada del entorno |
| NFR-U1-33 | `platform/observability/dashboards/operacion.json` | Dashboards como código, junto con `resiliencia.json`, `seguridad.json` y `slo.json` |
| NFR-U1-34 | `platform/network/flows.yaml` | Observabilidad sin más salida que F72 |
| P-U1-04 | `contracts/python/vectra_common/src/vectra_common/ops_server.py` | Liveness y readiness de los servicios |
| P-U1-07 | `platform/observability/rules/platform-rules.yaml` | Alerta `Watchdog` |
| P-U1-10 | `platform/runbooks/_template.md` | Plantilla de runbook; el COE está en `platform/runbooks/coe-template.md` |
| P-U1-11 | `platform/observability/rules/platform-rules.yaml` | Reglas de grabación de los dos indicadores de SLO |

Estado y desviaciones: §5 de `aidlc-docs/construction/plans/platform-foundation-code-generation-plan.md`.
