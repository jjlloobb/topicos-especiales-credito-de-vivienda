# Decisiones de stack — U1 `platform-foundation`

Decisiones del plan (`platform-foundation-nfr-requirements-plan.md`, Q1–Q14 = A) y de
INCEPTION. Las versiones exactas se pinnean en los charts y en `Chart.lock` del repositorio
GitOps (imágenes por digest, NFR-U1-25).

---

## 1. Plataforma

| Área | Decisión | Motivo | Origen |
|---|---|---|---|
| Kubernetes | Conforme a CNCF, ≥ 1.30, sin APIs de un proveedor de nube | Portabilidad para un banco self-hosted | Q1 |
| Desarrollo y pruebas | kind con 1 nodo de control y 4 workers en 2 zonas simuladas (`topology.kubernetes.io/zone`; INF-U1-01, precisado el 2026-10-08) | Reproducible en CI y en local; permite ensayar el fallo de zona | Q1, Q18 |
| OpenShift | Restricción documentada (sin UIDs fijos, `runAsNonRoot`); no se certifica | Compatibilidad sin coste de certificación | Q1 |
| Empaquetado | Helm (charts por componente) | US-605 | INCEPTION |
| GitOps | Argo CD con sync manual; repositorio `vectra-risk-gitops` | Q19, AUTONOMIA-01 | INCEPTION |

## 2. Datos y almacenamiento

| Área | Decisión | Motivo | Origen |
|---|---|---|---|
| PostgreSQL | **CloudNativePG**: 3 instancias por cluster, `minSyncReplicas = 1`, `maxSyncReplicas = 2`, failover automático | Réplica síncrona y PITR nativos, sin componentes externos | Q2, Q7 |
| Backups | Barman Cloud (integrado en CloudNativePG): backup base diario + WAL continuo (`archive_timeout = 60 s`) | RPO del sitio ≤ 5 min | Q3, Q5 |
| Almacenamiento de objetos | API compatible con S3. **MinIO in-cluster en todos los entornos** para `model-store`, `validation-datasets`, `loki` y `tempo`; backups y WAL en el **S3 del banco fuera del sitio** (`vectra-backups`, `vectra-wal`, F70) (INF-U1-03, precisado el 2026-10-08) | Un solo contrato, portable | Q6; INF-U1-03 |
| Inmutabilidad | Object lock en los buckets de `registry-db` y de Loki | Evidencia regulatoria y logs tamper-evident | Q5, Q8 |

## 3. Seguridad

| Área | Decisión | Motivo | Origen |
|---|---|---|---|
| mTLS en el clúster | **Linkerd** con **linkerd-cni** | mTLS automático sin `NET_ADMIN` en los pods, compatible con PSA `restricted` | Q12, Q10 |
| Certificados | **cert-manager** con una CA interna (borde y PostgreSQL) | TLS 1.2+ donde Linkerd no aplica | Q12 |
| Secretos | **External Secrets Operator**; Vault en kind y la bóveda del banco en producción; cifrado de Secrets en etcd | Sin secretos en Git; la rotación vive en la bóveda | Q9 |
| Admisión | **Kyverno** + Pod Security Admission `restricted` | Políticas como código, con pruebas (`kyverno test`) y verificación de firmas | Q10 |
| Cadena de suministro | **Trivy**, **Syft** (SPDX) y **Cosign** (firma + attestation del SBOM) | SECURITY-10/13 | Q11 |
| Red | NetworkPolicy estándar de Kubernetes (deny-all + allow por flujo). Requiere un CNI que la aplique; en kind, **Calico**; en prod y staging, el CNI del banco si pasa la suite de conectividad (INF-U1-04) | NFR-SEC-07 | INCEPTION |

## 4. Observabilidad

| Componente | Decisión | Retención |
|---|---|---|
| Métricas | Prometheus + Alertmanager | 30 días |
| Logs | Loki + **Grafana Alloy** (DaemonSet; elegido en el Infrastructure Design de U1) | 90 días, con object lock |
| Trazas | Tempo + OpenTelemetry Collector | 7 días |
| Dashboards | Grafana, con dashboards como código | — |
| Pushgateway | Prometheus Pushgateway, 1 réplica sin persistencia, para jobs batch (`restore-drill` F87, CronJob de bias F106); alerta `PushgatewayDown` (tercera revisión del FD de U9, 2026-10-10) | Hasta el siguiente push |
| Pruebas de reglas | `promtool test rules` | — |

## 5. CI (GitHub Actions)

| Workflow reutilizable | Contenido | Requisito |
|---|---|---|
| `tests.yml` | Pruebas por unidad con la semilla de PBT registrada | NFR-U1-42 |
| `supply-chain.yml` | Trivy, Syft y Cosign | NFR-U1-26 |
| `evidence.yml` | `helm template`, `kubectl diff` contra kind, artefactos en el PR | NFR-U1-42 |
| `forbidden-steps.yml` | Falla si aparecen `kubectl apply`, `helm install`/`upgrade`, `terraform apply` o `argocd app sync` | NFR-U1-41 |
| `policies.yml` | `kyverno test`, `promtool test rules`, `actionlint` | NFR-U1-25, 32 |
| Runners | Alojados por GitHub; `runs-on` parametrizado para cambiar a runners propios | Q14, NFR-U1-40 |

## 6. Descartado

| Opción | Motivo |
|---|---|
| OpenShift como destino principal | Reduce la portabilidad (Q1=B) |
| Zalando o Crunchy PGO | CloudNativePG cubre réplica síncrona y PITR con menos piezas (Q2) |
| `archive_timeout` de 300 o 900 s | RPO mayor para la evidencia regulatoria (Q3) |
| Failover manual | Alarga la indisponibilidad sin ganar corrección (Q7=B) |
| Sealed Secrets / SOPS | Secretos cifrados en Git, con una rotación más difícil (Q9) |
| OPA Gatekeeper / solo PSA | Más complejidad, o sin verificación de firmas (Q10) |
| TLS terminado en cada servicio | Cada servicio gestionaría sus certificados (Q12=B) |
