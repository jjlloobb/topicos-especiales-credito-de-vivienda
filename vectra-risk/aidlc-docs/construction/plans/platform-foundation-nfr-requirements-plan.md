# Plan de NFR Requirements — U1 `platform-foundation`

**Alcance de la unidad** (`unit-of-work.md` §1):
- namespaces y NetworkPolicy deny-all;
- operador y clusters de PostgreSQL (`case-db`, `governance-db`, `registry-db`, `keycloak-db`) con réplica síncrona multi-zona, backups cifrados y WAL fuera del sitio;
- model-store;
- controlador de KServe;
- stack de observabilidad;
- Argo CD con sync manual;
- workflows reutilizables de CI;
- runbooks de restore y failover.

Functional Design = SKIP (sin lógica de negocio).

**Historias (dueña):** US-604 (base de red y egress), US-605, US-606, US-607, US-608, US-610.

**Ya decidido en INCEPTION** (no se vuelve a preguntar):
- clúster local kind/k3d para desarrollo y entrega por PR con evidencia (Q18);
- Argo CD con sync manual y Prometheus/Grafana/Alertmanager in-cluster (Q19);
- DR del sitio por Backup & Restore (R1); RPO = 0 del Decision Registry ante fallo de zona (R2);
- un sitio con ≥ 2 zonas (R7); HPA con mínimo y máximo, validado con carga simulada (R8);
- CI en GitHub Actions (R4); rollback = revert + sync manual (R5); rolling update (R6);
- proceso de incidentes ligero propuesto (R9); SLA propuesto de 99,5 % en horario operativo (NFR-RES-02);
- RESILIENCY-14 = C a nivel proyecto (U0 NFR Design).

**Pendiente según requirements §8.4:** el intervalo de archivado de WAL, que acota el RPO
del registro ante la pérdida del sitio, se fija en esta etapa (Q3).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Plataforma Kubernetes de destino (Tech Stack)
El banco instala Vectra Risk en su propio clúster, que no conocemos.

A) **Kubernetes conforme a CNCF, ≥ 1.30, sin APIs de un proveedor de nube.**
   - Desarrollo y pruebas en kind con 3 nodos etiquetados con 2 zonas simuladas (`topology.kubernetes.io/zone`).
   - La compatibilidad con OpenShift se documenta como restricción: sin UIDs fijos y `runAsNonRoot`. No se certifica.

   (Recomendado: máxima portabilidad para un banco self-hosted)

B) OpenShift como destino principal

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Operador de PostgreSQL (Tech Stack, K06)

A) **CloudNativePG**: réplica síncrona por configuración (`minSyncReplicas`/`maxSyncReplicas`), failover automático, backups base y WAL hacia almacenamiento compatible con S3 vía Barman Cloud, PITR, sin componentes externos (recomendado)

B) Zalando Postgres Operator (Patroni + WAL-G)

C) Crunchy PGO (pgBackRest)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Intervalo de archivado de WAL: RPO del registro ante pérdida del sitio (Availability, §8.4)

A) **`archive_timeout = 60 s`** → RPO del Decision Registry ≤ 5 min ante la pérdida del sitio. Alarma si el último WAL archivado tiene más de 5 min (recomendado: la evidencia regulatoria es lo más valioso del producto)

B) `archive_timeout = 300 s` → RPO ≤ 15 min

C) `archive_timeout = 900 s` → RPO ≤ 30 min

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — RTO del sitio (Availability, R1 «horas»)

A) **RTO ≤ 4 h** para la ruta de recomendación y el Decision Registry, con el runbook de restore probado en kind. Mientras tanto, los casos quedan en `no_disponible`: el fail-closed hace que la caída cueste velocidad, no corrección (recomendado)

B) RTO ≤ 8 h (una jornada operativa)

C) RTO ≤ 24 h

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Retención de backups (Reliability / Compliance)

A) Backup base **diario** y PITR por **30 días**, más un backup mensual retenido **12 meses**. Para `registry-db` se aplica **object lock (WORM)** en el bucket durante todo el periodo de retención. La retención regulatoria del registro mismo **[VERIFICAR]** con cumplimiento y la Superintendencia (normalmente años) y se decide en U3 (recomendado)

B) Backup base semanal y PITR por 14 días, sin WORM

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Almacenamiento de backups fuera del sitio y model-store (Tech Stack, F70)

A) **API compatible con S3** como único contrato: almacenamiento de objetos del banco en producción y **MinIO** en kind. Cifrado del lado del servidor, TLS, credenciales por Secret y bucket separado por propósito (`backups`, `wal`, `model-store`). El model-store usa el mismo contrato (recomendado: un solo tipo de almacenamiento, portable)

B) Volumen NFS del banco para backups y PVC para el model-store

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Failover de zona (Availability, RESILIENCY-08/13)

A) **Automático**:
   - CloudNativePG promueve la réplica síncrona (objetivo ≤ 60 s);
   - los Deployments tienen `topologySpreadConstraints` por zona, PodDisruptionBudget y ≥ 2 réplicas;
   - Keycloak y el api-gateway también tienen ≥ 2 réplicas.

   El runbook de failover cubre la verificación posterior y la vuelta a dos zonas (recomendado)

B) Manual, con un runbook ejecutado por un operador

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Retención y protección de la observabilidad (Security, SECURITY-14)

A) **Loki 90 días**, con almacenamiento de objetos con object lock (tamper-evident; las aplicaciones no pueden borrar sus logs). **Prometheus 30 días**, **Tempo 7 días**. Dashboards de seguridad y de resiliencia versionados como código (recomendado)

B) 90 días para todo, sin object lock

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Gestión de secretos (Security, NFR-SEC-12)

A) **External Secrets Operator** con un proveedor intercambiable: la bóveda del banco en producción y HashiCorp Vault en kind. No hay secretos en Git, ni siquiera cifrados. Además, cifrado de Secrets en etcd (recomendado: la rotación vive en la bóveda y el banco ya suele tener una)

B) **Sealed Secrets**: secretos cifrados en el repositorio GitOps

C) SOPS + age con un plugin de Argo CD

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Políticas de admisión (Security, CKS)

A) **Kyverno**, con políticas como código y pruebas (`kyverno test`):
   - imágenes por digest, sin `latest`, y firma verificada;
   - `runAsNonRoot`, sin `privileged` ni `hostPath`, `readOnlyRootFilesystem`;
   - límites de recursos obligatorios;
   - Applications de Argo CD sin `syncPolicy.automated`;
   - además, Pod Security Admission `restricted` por namespace.

   (Recomendado)

B) OPA Gatekeeper con las mismas reglas

C) Solo Pod Security Admission

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Cadena de suministro en CI (Security, SECURITY-10/13, US-606)

A) **Trivy** (imágenes, dependencias, IaC y Dockerfiles), **Syft** (SBOM SPDX) y **Cosign** (firma de imágenes y adjunto del SBOM como attestation). Kyverno verifica la firma al admitir (Q10). Falla el build si hay hallazgos críticos o altos sin excepción documentada (recomendado)

B) Trivy y Syft, sin firma de imágenes

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12 — Cifrado en tránsito dentro del clúster (Security, NFR-SEC-01)

A) **Linkerd** para mTLS automático entre todos los pods de Vectra (identidad por ServiceAccount, rotación de certificados incluida), más **cert-manager** para los certificados del borde y de PostgreSQL (TLS cliente-servidor). Las NetworkPolicies se mantienen como segunda capa (recomendado: TLS 1.2+ en toda conexión sin pedirle a cada servicio que gestione certificados)

B) **cert-manager** con una CA interna y TLS terminado en cada servicio (uvicorn), sin malla

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 13 — Volumen de diseño para escalado y prueba de carga (Scalability, R8)
Un banco mediano procesa del orden de cientos a pocos miles de solicitudes de vivienda al día.

A) **Diseño para 2 solicitudes/s sostenidas** en la ruta de recomendación, con picos de 10/s. La prueba de carga simulada valida **20/s durante 15 min** (2× el pico), con el HPA escalando sin errores ni fail-closed por saturación. Los mínimos y máximos por servicio salen de esa prueba (recomendado)

B) Diseño para 10 solicitudes/s sostenidas y una prueba a 50/s

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 14 — Runners de CI (Security, AUTONOMIA-05)

A) **Runners alojados por GitHub**, con solo datos sintéticos (U5) y sin credenciales del clúster: el CI nunca toca el clúster (AUTONOMIA-01). El banco puede cambiarlos a runners propios sin cambiar los workflows (recomendado)

B) Runners auto-hospedados dentro de la red del banco desde el inicio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el alcance de U1, sus historias y los NFR heredados (NFR-SEC-01/06/07/10/12/13/14, NFR-RES-01..15, §8.4)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/platform-foundation/nfr-requirements/nfr-requirements.md`
  - [x] 3.1 Disponibilidad y recuperación (SLA, RTO, RPO por capa, failover)
  - [x] 3.2 Escalabilidad y capacidad (volumen de diseño, HPA, cuotas)
  - [x] 3.3 Seguridad de la plataforma (red, secretos, admisión, cadena de suministro, cifrado)
  - [x] 3.4 Observabilidad y retención
  - [x] 3.5 Gestión de cambios y CI (sin pasos prohibidos)
- [x] 4. Generar `construction/platform-foundation/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Verificar el cumplimiento de las extensiones (RESILIENCY-01..15, SECURITY, AUTONOMIA-01/05)
