# Plan de NFR Design — U1 `platform-foundation`

**Alcance:** convertir NFR-U1-01..44 en patrones y componentes lógicos de la plataforma:
red, identidad de servicio, salud, alertas e incidentes, SLO, verificación de backups,
aislamiento de recursos, alta disponibilidad de los controladores y estructura GitOps.

**Ya decidido** (no se pregunta):
- RESILIENCY-14 = C (decisión del proyecto);
- el stack de `tech-stack-decisions.md` (CloudNativePG, Linkerd, Kyverno, ESO, cert-manager, observabilidad, CI);
- el proceso de incidentes ligero (R9), cuyo detalle es la Q4.

**Categorías obligatorias:**

| Categoría | Preguntas |
|---|---|
| Resilience Patterns | Q3, Q6, Q9, Q11 |
| Scalability Patterns | Q7, Q8 |
| Performance Patterns | Q7 |
| Security Patterns | Q1, Q2, Q9 |
| Logical Components | Q1, Q4, Q5, Q10, Q12 |

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Cómo se escriben las NetworkPolicies (Security / Logical Components)

A) **Generadas desde un inventario de flujos como datos**: `platform/network/flows.yaml` refleja las tablas de `component-dependency.md` (origen, destino, puerto, ID de flujo). Un generador produce:
   - la NetworkPolicy deny-all por namespace;
   - los allow por flujo;
   - las pruebas de conectividad (un caso permitido y uno bloqueado por flujo).

   Un flujo nuevo exige editar el inventario, y el diff del PR lo muestra (recomendado: el mismo patrón de U0, una fuente y cero deriva)

B) Escritas a mano en el chart de cada componente

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Autorización por identidad en la malla (Security)

A) **Política de entrada `deny` por defecto en Linkerd** para los namespaces de Vectra, con `Server` + `AuthorizationPolicy` por flujo que autorizan solo la ServiceAccount de origen. Es una segunda capa, por identidad, además de la NetworkPolicy, que es por IP. Las dos se generan desde el mismo `flows.yaml` (recomendado: un pod comprometido dentro del mismo namespace no puede hablar con quien no le corresponde)

B) Solo mTLS de Linkerd, sin políticas de autorización; el control de flujo queda en la NetworkPolicy

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Profundidad de la readiness (Resilience; NFR-RES-07, US-610)
NFR-RES-07 dice «readiness profunda (BD, KServe, explainability)». Pero si la readiness de
scoring depende de explainability, una caída de explainability saca a scoring del
balanceo. case-service recibe entonces errores de conexión en vez del `FailClosed`
tipificado, y la falla se propaga en cascada.

A) **Readiness = solo dependencias propias de datos**: su base de datos y, en el caso de scoring, la lectura de `serving-config`. Las dependencias aguas abajo (KServe, explainability, registro) **no** entran en la readiness: su caída la maneja el fail-closed, que es observable y queda registrado. Liveness superficial (el proceso responde), probes de arranque para las cargas lentas y resultados de checks cacheados 5 s para no golpear la base. NFR-RES-07 se precisa en ese sentido (recomendado)

B) Readiness profunda completa, incluidos KServe y explainability, como dice NFR-RES-07 hoy

> **Refinado después de la respuesta (2026-10-03):** scoring tampoco incluye `serving-config` en su readiness, porque su caída tiene la causa tipificada `serving_config_unavailable`. Ver P-U1-04.

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Severidades, enrutamiento y COE (RESILIENCY-15, R9)

A) **Tres severidades:**
   - **SEV1**: ruta de recomendación caída, `registry-db` sin escrituras, cadena de hashes rota o backup/WAL vencido. Respuesta en 15 min dentro del horario operativo.
   - **SEV2**: una zona caída, réplica rezagada, `FailClosedPersistente`, certificados a menos de 7 días o fallos de authz repetidos. Respuesta en 1 h.
   - **SEV3**: lo demás. Siguiente día hábil.

   Alertmanager enruta por la etiqueta `severity` al canal del banco (F72). Cada alerta tiene runbook con plantilla fija (síntoma, impacto, diagnóstico, mitigación, escalamiento). COE obligatorio en 5 días hábiles para SEV1 y SEV2, con acciones de seguimiento (recomendado)

B) Dos niveles (crítico y advertencia), sin COE formal

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Cómo cuenta el fail-closed en el SLO de 99,5 % (Logical Components / Resilience)

A) **Dos indicadores:**
   - **Disponibilidad**: requests a `POST /v1/recommendations` con respuesta 200 tipificada (`Recommendation` **o** `FailClosed`) dentro del timeout, contra el SLO de 99,5 %. El fail-closed es el sistema funcionando bien.
   - **Tasa de recomendación usable** (`Recommendation` / total): se vigila sin SLO, con la alerta `FailClosedPersistente` y un dashboard.

   Alertas de burn rate en dos ventanas (1 h/5 min y 6 h/30 min) sobre la disponibilidad (recomendado: no castiga el comportamiento correcto, pero no lo oculta)

B) El fail-closed cuenta como indisponibilidad en el SLO

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Verificación continua de backups (Resilience, RESILIENCY-12)

A) **Simulacro automático semanal**: un CronJob restaura el último backup + WAL en un cluster efímero de CloudNativePG, en un namespace aislado (`vectra-restore-drill`, sin acceso de red a las aplicaciones). Corre `verify_chain` sobre `registry-db`, publica la métrica `vectra_restore_drill_success` y la duración, y destruye el cluster. Si falla, alerta SEV1 (recomendado: un backup que no se restaura no es un backup)

B) Simulacro manual mensual siguiendo el runbook

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 7 — Conexiones a PostgreSQL (Performance / Scalability)
Volumen de diseño: 2 solicitudes/s sostenidas y picos de 10/s.

A) **Conexiones directas** con pools acotados por pod (máximo 5 por réplica) y `max_connections` dimensionado con el máximo del HPA. Sin PgBouncer: con este volumen no hace falta, y se evitan las incompatibilidades del modo transacción con las sentencias preparadas de `asyncpg` (recomendado)

B) **PgBouncer** (`Pooler` de CloudNativePG) en modo transacción para cada base

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8 — Prioridad y aislamiento de recursos (Scalability, bulkheads)

A) **PriorityClasses**:
   - `vectra-critical`: PostgreSQL, decision-registry-service, Linkerd, Kyverno y CloudNativePG;
   - `vectra-high`: scoring, explainability, case, governance, Keycloak, gateway y KServe;
   - `vectra-normal`: BFF, bias, métricas y observabilidad;
   - `vectra-low`: channel-simulator y jobs batch, que son *preemptibles*.

   Ante falta de capacidad (p. ej. tras perder una zona) se desaloja primero lo prescindible (recomendado)

B) Sin PriorityClasses: solo cuotas por namespace

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 9 — Admisión y controladores durante un fallo (Resilience / Security)
Durante un failover de zona hay que **crear pods**. Si el webhook de Kyverno tiene
`failurePolicy: Fail` y Kyverno estaba en la zona caída, no se admite ningún pod.

A) **Controladores críticos en HA**: Kyverno (3 réplicas del admission controller), el plano de control de Linkerd (modo HA), cert-manager y CloudNativePG, repartidos por zona y con PDB. Kyverno con `failurePolicy: Fail` (admisión fail-closed), excluyendo los namespaces del sistema y el propio `kyverno` para que pueda recuperarse. Alerta SEV1 si Kyverno no tiene réplicas listas (recomendado)

B) Kyverno con `failurePolicy: Ignore`, para no bloquear nunca la admisión

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10 — Estructura del repositorio GitOps (Logical Components)

A) **App-of-apps por entorno** (`kind`, `staging`, `prod`), con una `Application` por componente y **sync waves**:
   - 0: CRDs y operadores;
   - 1: políticas (Kyverno) y malla (Linkerd);
   - 2: datos (PostgreSQL, MinIO);
   - 3: identidad;
   - 4: observabilidad;
   - 5: servicios;
   - 6: InferenceServices.

   Los values por entorno van en overlays. Todo sync sigue siendo manual (recomendado: un sync manual ordenado y legible por el aprobador)

B) ApplicationSets con generadores por directorio

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 11 — Vigilancia del propio sistema de alertas (Resilience)

A) **Alerta `Watchdog` permanente** (dead man's switch) enviada cada 5 min por F72 a un receptor de latido en el canal del banco. Si deja de llegar, el banco sabe que la observabilidad está caída. Además, alertas sobre la salud de Prometheus, Loki y Alertmanager (recomendado)

B) Sin latido externo

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 12 — Rotación de certificados de la malla (Security / Logical Components)

A) **cert-manager gestiona la jerarquía de Linkerd**: un trust anchor con validez de 1 año (alerta 30 días antes y rotación por runbook con dos anchors en paralelo) y un issuer intermedio rotado automáticamente cada 48 h. Los certificados de borde y de PostgreSQL son de 90 días, con renovación automática a los 60 (recomendado)

B) Certificados de Linkerd generados en la instalación, con rotación manual

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar `construction/platform-foundation/nfr-requirements/` (NFR-U1-01..44, stack)
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/platform-foundation/nfr-design/nfr-design-patterns.md`
  - [x] 3.1 Resiliencia (readiness, verificación de backups, HA de controladores, latido)
  - [x] 3.2 Escalabilidad y rendimiento (conexiones, prioridades)
  - [x] 3.3 Seguridad (red desde el inventario, autorización por identidad, certificados)
  - [x] 3.4 Operación (severidades, runbooks, COE, SLO)
- [x] 4. Generar `construction/platform-foundation/nfr-design/logical-components.md` (componentes, sync waves, diagrama validado)
- [x] 5. Verificar el cumplimiento de las extensiones
