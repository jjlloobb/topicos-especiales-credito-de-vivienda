# Requisitos no funcionales — U1 `platform-foundation`

Decisiones del plan (`platform-foundation-nfr-requirements-plan.md`, Q1–Q14 = A). Cada
requisito tiene una verificación ejecutable (AUTONOMIA-02). Ninguna verificación aplica
cambios a un clúster compartido: se ejecutan en kind o sobre manifiestos renderizados
(AUTONOMIA-01).

Los IDs `NFR-U1-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Disponibilidad y recuperación (RESILIENCY-01, 02, 08, 11, 12, 13)

### 1.1 Objetivos

| Capa | Objetivo | Origen |
|---|---|---|
| SLA de la ruta de recomendación | 99,5 % mensual en horario operativo **[INTERNO]** | NFR-RES-02 |
| Fallo de zona — Decision Registry | **RPO = 0** (réplica síncrona) | R2 |
| Fallo de zona — PostgreSQL | Promoción automática ≤ 60 s | Q7 |
| Pérdida del sitio — Decision Registry | **RPO ≤ 5 min** (`archive_timeout = 60 s`) | Q3, §8.4 |
| Pérdida del sitio — otras bases | RPO ≤ 5 min (misma configuración) | Q3 |
| Pérdida del sitio — métricas, trazas y dashboards | RPO en horas; aceptable | §8.4 |
| Pérdida del sitio — RTO | **≤ 4 h** para la ruta de recomendación y el registro | Q4 |

### 1.2 Requisitos

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U1-01 | Clasificación de criticidad: `registry-db` = Critical; `case-db`, `governance-db`, `keycloak-db`, KServe y Argo CD = High; observabilidad = Medium | Tabla versionada en `platform/docs/criticality.md`; un test de política verifica que cada chart declara la etiqueta `vectra.io/criticality` |
| NFR-U1-02 | Cada cluster de PostgreSQL tiene 3 instancias: anti-afinidad **obligatoria** por nodo y reparto **preferido** por zona; `minSyncReplicas = 1`, `maxSyncReplicas = 2` | `helm template` + `kyverno test` / `conftest` sobre el `Cluster` de CloudNativePG |
| NFR-U1-03 | **Consecuencia de R2 con 2 zonas** (registrada aquí): si cae la zona que tiene 2 de las 3 instancias, la que sobrevive queda sin réplica síncrona y **las escrituras se bloquean** hasta que CloudNativePG clone una réplica nueva en la zona que sigue viva. El registro devuelve `registry_unavailable` y las recomendaciones salen como fail-closed, nunca con RPO > 0. El tiempo de bloqueo es el de clonar la réplica (minutos, según el tamaño de la base). Se recomienda al banco una **tercera zona** en producción, que elimina ese bloqueo | Escenario en kind: `kubectl drain` de los nodos de una zona simulada → las escrituras fallan, se crea la réplica nueva y las escrituras vuelven; se mide el tiempo |
| NFR-U1-04 | Todos los Deployments de Vectra, Keycloak y el api-gateway tienen ≥ 2 réplicas, `topologySpreadConstraints` por zona y PodDisruptionBudget (`minAvailable: 1`) | `helm template` de los values de producción + política Kyverno `require-spread-and-pdb` en `kyverno test` (US-605) |
| NFR-U1-05 | Archivado continuo de WAL con `archive_timeout = 60 s` y backup base diario hacia almacenamiento compatible con S3 fuera del sitio | Inspección del `ScheduledBackup` y del `Cluster`; alerta `WalArchiveStale` si el último WAL archivado tiene más de 5 min |
| NFR-U1-06 | Retención: PITR de 30 días y un backup mensual retenido 12 meses. Bucket de `registry-db` con **object lock** durante todo el periodo de retención. La retención regulatoria del registro se decide en U3 **[VERIFICAR]** | Configuración de `retentionPolicy`; prueba en MinIO de que borrar un objeto bloqueado falla |
| NFR-U1-07 | Runbook de restore del sitio probado en kind: clúster limpio → restore de base + WAL → `verify_chain` «íntegra» → servicios en `Ready`, dentro de las 4 h del RTO | Job `restore-drill` en kind que mide la duración y guarda la salida de `verify_chain` (US-608) |
| NFR-U1-08 | Runbook de failover de zona con verificación posterior (réplica sincronizada, lag 0, pods repartidos de nuevo) y vuelta a dos zonas | Escenario de NFR-U1-03 + checklist del runbook ejecutado en kind |

## 2. Escalabilidad y capacidad (RESILIENCY-09, R8; Q13)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U1-10 | Volumen de diseño: **2 solicitudes/s sostenidas** y **picos de 10/s** en la ruta de recomendación | Documento de capacidad `platform/docs/capacity.md` |
| NFR-U1-11 | La prueba de carga simulada (channel-simulator) sostiene **20/s durante 15 min** sin errores 5xx ni fail-closed por saturación; el HPA escala dentro de su máximo | Job `load-test` en kind con resultados (p95, errores, réplicas máximas); lo ejecuta U12 sobre la plataforma de U1 |
| NFR-U1-12 | Cada servicio tiene HPA con mínimo (≥ 2) y máximo derivados de la prueba; KServe con `minReplicas ≥ 2` y `maxReplicas` definido | `helm template` + política `require-hpa-bounds` |
| NFR-U1-13 | `ResourceQuota` y `LimitRange` por namespace, documentados y dimensionados para el máximo del HPA + un 30 % de margen | `kubectl get resourcequota -o yaml` en kind; test de política sobre los manifiestos |

## 3. Seguridad de la plataforma

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U1-20 | NetworkPolicy deny-all de ingress y egress en cada namespace de Vectra; solo los flujos de `component-dependency.md` se permiten explícitamente | NFR-SEC-07, AUTONOMIA-05, US-604 | Pruebas de conectividad en kind: un flujo no inventariado → bloqueado; X01–X10 los ejecuta U12 |
| NFR-U1-21 | **Linkerd** con mTLS en todos los pods de Vectra (identidad por ServiceAccount), instalado con **linkerd-cni** para que los pods no necesiten `NET_ADMIN` y sean compatibles con Pod Security Admission `restricted` | NFR-SEC-01, Q12, Q10 | `linkerd check` y `linkerd viz edges` en kind: todas las conexiones entre pods de Vectra aparecen como mTLS |
| NFR-U1-22 | **cert-manager** con una CA interna para el borde (Envoy Gateway) y para TLS cliente-servidor de PostgreSQL (`sslmode=verify-full`); TLS ≥ 1.2 | NFR-SEC-01 | `openssl s_client` contra el gateway y `psql "sslmode=verify-full"` en kind |
| NFR-U1-23 | Cifrado en reposo de los volúmenes de PostgreSQL (StorageClass cifrada del banco; en kind se documenta como no aplicable) y de los backups (cifrado del lado del servidor en S3) | NFR-SEC-01 | Inspección de la StorageClass y de la configuración del bucket |
| NFR-U1-24 | **External Secrets Operator** como única vía para los Secrets de aplicación: la bóveda del banco en producción y HashiCorp Vault en kind. Ningún Secret de aplicación en Git, ni siquiera cifrado. Cifrado de Secrets en etcd habilitado | NFR-SEC-12, Q9 | `grep -r "kind: Secret" vectra-risk-gitops/` solo encuentra `ExternalSecret`; test de política `disallow-plain-secrets` |
| NFR-U1-25 | **Kyverno** con políticas versionadas y probadas: imágenes por digest y firmadas (Cosign), sin `latest`, `runAsNonRoot`, sin `privileged` ni `hostPath`, `readOnlyRootFilesystem`, límites de recursos obligatorios y Applications sin `syncPolicy.automated`. Pod Security Admission `restricted` por namespace | Q10, SECURITY-09/10, US-606, US-607 | `kyverno test platform/policies/` en CI; en kind, un Pod con `latest` → rechazado |
| NFR-U1-26 | Cadena de suministro en CI: Trivy (imágenes, dependencias, IaC, Dockerfiles), Syft (SBOM SPDX) y Cosign (firma + attestation del SBOM). El build falla con hallazgos críticos o altos sin una excepción documentada (`.trivyignore` con justificación y vencimiento) | Q11, SECURITY-10/13, US-606 | Workflow reutilizable `supply-chain.yml`; un Dockerfile con `latest` hace fallar el PR |
| NFR-U1-27 | RBAC de Kubernetes de mínimo privilegio y sin comodines; solo existen los bindings K01–K06, más los de los nuevos controladores (Kyverno, Linkerd, cert-manager, ESO), que se inventarían en Infrastructure Design | NFR-SEC-06, AUTONOMIA-03 | Test de política que rechaza `*` en `verbs`/`resources`; `kubectl auth can-i --list` por ServiceAccount en kind |

## 4. Observabilidad y retención (RESILIENCY-05, 06, 07; SECURITY-14; Q8)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U1-30 | Retención: **Loki 90 días** sobre almacenamiento de objetos con **object lock** (las aplicaciones no pueden borrar ni modificar sus logs). La retención la aplica el lock y el lifecycle del bucket, **no** el compactor de Loki, cuya eliminación queda deshabilitada para no chocar con el lock | Configuración de Loki (`retention_enabled: false`) + prueba en MinIO de que borrar un chunk bloqueado falla |
| NFR-U1-31 | **Prometheus 30 días**, **Tempo 7 días** | Flags y values del chart |
| NFR-U1-32 | Alarmas mínimas de resiliencia: réplica de BD caída o rezagada, `WalArchiveStale`, fallo de backup, operación en una sola zona, HPA saturado, `FailClosedPersistente`, certificados por vencer y fallos repetidos de authn/authz (SECURITY-14). Cada alerta tiene `runbook_url` | Pruebas de reglas con `promtool test rules`; un test verifica que toda regla tiene `runbook_url` |
| NFR-U1-33 | Dashboards de seguridad, resiliencia y operación versionados como código (JSON en el repo) | Lint de dashboards en CI |
| NFR-U1-34 | Ningún componente de observabilidad exporta fuera del clúster salvo F72 (Alertmanager), sin PII | NetworkPolicies de `vectra-observability`; prueba de egress en kind |

## 5. Gestión de cambios y CI (RESILIENCY-03, 04; AUTONOMIA-01; Q14)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U1-40 | CI en runners alojados por GitHub, solo con datos sintéticos y **sin credenciales del clúster**. El cambio a runners propios no exige modificar los workflows (`runs-on` parametrizado) | Revisión de los workflows: ningún secret de kubeconfig; input `runner` en los workflows reutilizables |
| NFR-U1-41 | Ningún workflow ejecuta `kubectl apply`, `helm install`/`upgrade`, `terraform apply` ni `argocd app sync` | Workflow reutilizable `forbidden-steps.yml`: `grep` sobre `.github/workflows/` que falla si encuentra esos comandos (US-606) |
| NFR-U1-42 | Cada PR de infraestructura adjunta `helm template`, `kubectl diff` (contra kind), resultados de pruebas con la semilla de PBT, reporte de vulnerabilidades y SBOM | Workflow reutilizable `evidence.yml`; artefactos visibles en el PR |
| NFR-U1-43 | Argo CD con sync manual: ninguna `Application` tiene `syncPolicy.automated`; el único cambio al clúster es un sync manual aprobado | Política Kyverno + test sobre los manifiestos de las Applications (US-607) |
| NFR-U1-44 | Rollback = revert en Git + sync manual, o `helm rollback` aprobado, con una nota de rollback obligatoria en la plantilla de PR | Plantilla `.github/pull_request_template.md` con la sección «Rollback»; check que falla si está vacía |

## 6. Cambios requeridos al inventario de `component-dependency.md`

Las decisiones Q6, Q8, Q9 y Q12 introducen componentes y flujos que el inventario cerrado
aprobado en INCEPTION no tiene. Se **formalizan en el Infrastructure Design de U1**, que
actualiza `component-dependency.md` y lo registra en `audit.md`:

| Cambio | Motivo |
|---|---|
| Egress nuevo: ESO → bóveda de secretos del banco (solo producción) | Q9 |
| Destino de almacenamiento de objetos de Loki y Tempo: in-cluster (MinIO) o almacenamiento del banco. Si es externo, es un egress nuevo desde `vectra-observability` | Q8; hoy la observabilidad no tiene egress salvo F72 |
| model-store sobre la API S3: confirmar si es in-cluster (`vectra-data`) o del banco | Q6 |
| Namespaces y bindings de Kyverno, Linkerd, cert-manager y ESO (nuevos K0x) | Q10, Q12, Q9 |

## 7. Cumplimiento de extensiones (NFR Requirements U1)

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 | Cumple | NFR-U1-01 |
| RESILIENCY-02 | Cumple | §1.1 (SLA, RTO, RPO por capa) |
| RESILIENCY-03 / 04 | Cumple | NFR-U1-41..44 |
| RESILIENCY-05 / 06 / 07 | Cumple | NFR-U1-32..34; los health checks de cada servicio los define su unidad sobre el puerto 8081 (U0) |
| RESILIENCY-08 | Cumple | NFR-U1-02..04 |
| RESILIENCY-09 | Cumple | NFR-U1-10..13 |
| RESILIENCY-10 | N/A en U1 | Es de los servicios (U0 aporta `deps.call`) |
| RESILIENCY-11 / 12 / 13 | Cumple | NFR-U1-05..08 |
| RESILIENCY-14 | Cumple | Decisión del proyecto = C; los escenarios de NFR-U1-03 y 07 se documentan aquí y se ejecutan en Operations |
| RESILIENCY-15 | Cumple | NFR-U1-32 (`runbook_url`); proceso ligero de R9 en NFR Design |
| SECURITY-01 | Cumple | NFR-U1-21..23 |
| SECURITY-06 | Cumple | NFR-U1-27 |
| SECURITY-07 | Cumple | NFR-U1-20 |
| SECURITY-09 / 10 / 13 | Cumple | NFR-U1-25, 26 |
| SECURITY-12 | Cumple | NFR-U1-24 |
| SECURITY-14 | Cumple | NFR-U1-30, 32 |
| AUTONOMIA-01 | Cumple | NFR-U1-40..43 |
| AUTONOMIA-02 | Cumple | Cada requisito tiene una verificación ejecutable |
| AUTONOMIA-05 | Cumple | NFR-U1-20, 34, 40 |
| PBT-09 | N/A en U1 | Sin código de aplicación; el CI de U1 ejecuta los PBT de las demás unidades con la semilla registrada (NFR-U1-42) |
