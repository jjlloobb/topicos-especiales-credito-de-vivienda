# Plan de Infrastructure Design — U1 `platform-foundation`

**Alcance:** asignar los componentes lógicos de U1 (`nfr-design/logical-components.md`) a
infraestructura concreta en los entornos de despliegue, y cerrar los pendientes que dejó
NFR Design:
- namespaces y RBAC de los controladores nuevos;
- destino del almacenamiento S3;
- egress de ESO;
- `max_connections`;
- CNI;
- agente de logs.

Al terminar se actualiza el inventario de `component-dependency.md` (flujos, namespaces,
bindings K0x) y se registra en `audit.md`.

**Destino:** on-premise, en el clúster Kubernetes del banco (Q1 de NFR Requirements).
No hay proveedor de nube.

**Categorías obligatorias:**

| Categoría | Aplica | Preguntas |
|---|---|---|
| Deployment Environment | Sí | Q1, Q11 |
| Compute Infrastructure | Sí | Q2 |
| Storage Infrastructure | Sí | Q3, Q4 |
| Messaging Infrastructure | **N/A, ya decidido**: sin broker; cola transaccional en PostgreSQL (`SKIP LOCKED`) en `case-db` y CronJobs (Q4 de Application Design, `services.md`). U1 no aporta infraestructura de mensajería | — |
| Networking Infrastructure | Sí | Q5, Q6, Q7 |
| Monitoring Infrastructure | Sí | Q8, Q9 |
| Shared Infrastructure | Sí | Q9, Q10 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Entornos (Deployment Environment)

A) **Tres entornos, mismos charts y values distintos:**
   - **kind**: desarrollo local y CI efímero;
   - **staging**: un clúster del banco separado de producción;
   - **prod**: el clúster del banco.

   El namespace `vectra-staging` dentro de cada clúster sigue siendo solo para validar modelos (journey 7.2), no un entorno (recomendado)

B) Staging como un conjunto de namespaces dentro del clúster de producción

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Nodos y pools (Compute)
PostgreSQL tiene 3 instancias con anti-afinidad obligatoria por nodo. Para que el fallo de
una zona permita clonar una réplica nueva (NFR-U1-03), la zona que sobrevive necesita un
nodo libre.

A) **kind**: 1 control-plane + **4 workers** (2 por zona simulada).
   **prod**:
   - ≥ 3 nodos por zona;
   - un **pool dedicado para datos** (taint `vectra.io/pool=data:NoSchedule`, solo PostgreSQL y MinIO), con ≥ 2 nodos por zona;
   - un **pool general** para el resto.

   El tamaño exacto sale de la prueba de carga (NFR-U1-11) y de las cuotas (NFR-U1-13) (recomendado)

B) kind con 3 workers; prod con un solo pool compartido

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Volúmenes de PostgreSQL (Storage)
Estimación: unas 2 000 decisiones al día, con la explicación completa (~20 KB por
entrada), dan ~15 GB al año en `registry-db`.

A) Volumen de **datos y de WAL separados** (CloudNativePG `walStorage`):
   - `registry-db` 100 Gi + 20 Gi de WAL;
   - `case-db` 50 Gi + 10 Gi;
   - `governance-db` 10 Gi + 5 Gi;
   - `keycloak-db` 10 Gi + 5 Gi.

   StorageClass del banco con cifrado, `WaitForFirstConsumer` y `allowVolumeExpansion: true`; en kind, `local-path` (sin cifrado, documentado). Alerta al 80 % de uso (recomendado)

B) Un solo volumen por instancia, de 50 Gi para todas las bases

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Destino del almacenamiento S3 en producción (Storage / egress)
Hoy la observabilidad, KServe y los servicios no tienen egress. Solo los backups (F70)
salen del clúster.

A) **MinIO dentro del clúster** en producción (modo distribuido, repartido por zonas, con object lock) para `model-store`, `loki` y `tempo`. Solo los **backups y el WAL** van al almacenamiento S3 **fuera del sitio** del banco (F70, ya existe). No aparece ningún egress nuevo para observabilidad ni para KServe (recomendado: conserva el inventario de AUTONOMIA-05)

B) Almacenamiento S3 del banco (fuera del clúster) para todo; se agregan flujos de egress desde `vectra-observability` y `vectra-serving`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — CNI y aplicación de NetworkPolicy (Networking)

A) **Calico** en kind. En producción se usa el CNI del banco **si** aplica NetworkPolicy de ingress y egress. Una prueba de conformidad en el entorno (la suite de conectividad de P-U1-01) es requisito para instalar. Si el CNI del banco no la aplica, se exige Calico (recomendado)

B) Cilium en todos los entornos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Exposición del borde (Networking)
El api-gateway (Envoy Gateway) es de U2. U1 provee la capacidad de balanceo.

A) **Service `LoadBalancer`**, agnóstico del proveedor: en producción, el balanceador L4 del banco (o MetalLB si el banco no tiene uno integrado); en kind, `cloud-provider-kind`. Solo el api-gateway tiene un Service `LoadBalancer`, y una política de Kyverno lo impone (recomendado)

B) `NodePort` detrás de un balanceador externo configurado a mano

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Namespaces de los controladores nuevos (Networking / Shared)

A) **Namespaces estándar de cada proyecto**: `cert-manager`, `linkerd`, `linkerd-cni`, `kyverno`, `external-secrets`, `cnpg-system` y `minio` (si Q4=A, en `vectra-data`). Cada uno con su NetworkPolicy deny-all y sus flujos en `flows.yaml`, y sus bindings inventariados como K07..K12 (recomendado: charts upstream sin parches y aislamiento por controlador)

B) Un solo namespace `vectra-platform` para todos los controladores

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Agente de logs (Monitoring)

A) **Grafana Alloy** como DaemonSet: recoge los logs de stdout y los envía a Loki; también puede recibir OTLP. Promtail está en fin de vida (recomendado)

B) Promtail

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Relación con la observabilidad del banco (Monitoring / Shared)

A) **Stack propio de Vectra** en `vectra-observability`, sin compartir almacenamiento con el banco. Si el banco quiere métricas agregadas, **las lee** él (federación o remote-read desde su lado, con un usuario de solo lectura); Vectra no empuja nada. Las alertas salen solo por F72 (recomendado: nada sale del clúster por iniciativa de Vectra)

B) Enviar métricas y logs al stack existente del banco (remote-write)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Registro de imágenes (Shared / Supply chain)

A) **Registro interno del banco** (p. ej. Harbor) como única fuente de imágenes en staging y prod, alimentado desde el registro de CI (GHCR) por un proceso de réplica **del lado del banco**. En kind, un registro local (`kind-registry`). Kyverno verifica la firma de Cosign y que el registro sea el permitido (recomendado)

B) Descargar directamente desde GHCR en todos los entornos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Servidor Git para Argo CD (Deployment Environment, F71)

A) **GitHub en kind y CI; espejo Git interno del banco en staging y prod**. Argo CD solo lee del espejo, que el banco sincroniza desde GitHub con su propio proceso. El sync sigue siendo manual (recomendado: el clúster de producción no depende de un servicio externo)

B) GitHub directamente en todos los entornos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar NFR Requirements y NFR Design de U1 (pendientes de `logical-components.md` §4)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/platform-foundation/infrastructure-design/infrastructure-design.md` (asignación componente → infraestructura por entorno; dimensionamiento; `max_connections`)
- [x] 4. Generar `construction/platform-foundation/infrastructure-design/deployment-architecture.md` (topología por zonas, namespaces, flujos nuevos, diagrama validado)
- [x] 5. Generar `construction/shared-infrastructure.md` (lo que U1 provee a las demás unidades)
- [x] 6. Actualizar `inception/application-design/component-dependency.md` (namespaces, flujos, bindings K0x) y registrarlo en `audit.md`
- [x] 7. Verificar el cumplimiento de las extensiones
