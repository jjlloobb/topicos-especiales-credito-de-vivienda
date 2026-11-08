# AI-DLC State Tracking

## Project Information
- **Project Name**: Vectra Risk
- **Project Type**: Greenfield
- **Start Date**: 2026-09-26T13:02:25Z
- **Current Phase**: CONSTRUCTION
- **Current Stage**: CONSTRUCTION - todas las unidades cerradas en el plan de tareas
- **Requirements Depth**: Comprehensive (sistema regulado, alto riesgo, múltiples stakeholders)

## Workspace State
- **Existing Code**: Sí, U0 en `contracts/` y U1 en `platform/` y `vectra-risk-gitops/`, en `main` desde el PR 1
- **Programming Languages**: Python 3.12 y TypeScript (U0)
- **Build System**: uv, npm y Make (`contracts/`)
- **Project Structure**: Monorepo multi-unidad: `contracts/` (U0), `platform/` y `vectra-risk-gitops/` (U1); documentación en `aidlc-docs/`
- **Reverse Engineering Needed**: No
- **Workspace Root**: /home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Scope Constraint (instrucción del usuario)
- **Restricción levantada solo para U0 y U1** (P17 de `cross-unit-review5-followup-questions.md`, 2026-10-31): se ejecuta su Code Generation Part 2 y la comprobación de la plataforma en kind, después de la aprobación del conjunto de cambios (P18). Ningún operador humano queda reemplazado: AUTONOMIA-01 sigue vigente.
- **Restricción levantada para U2 `identity-edge`** (instrucción del usuario, 2026-11-02: «termina la prueba de cambio de modelo y luego empieza la siguiente unidad»): su Code Generation Part 2 se ejecuta por tareas del loop (`tareas/U02-*`), cada una en un PR que fusiona una persona. AUTONOMIA-01 sigue vigente: lo que necesite un clúster lo ejecuta un operador después de un PR aprobado (Paso 16).
- **Restricción levantada para U3–U12 con alcance de demo en kind** (aprobación del usuario, 2026-11-08): su Code Generation Part 2 se ejecuta solo con los pasos E y E\* de `construction/plans/demo-kind-alcance.md`, por tareas del loop; los pasos D quedan diferidos. Cada unidad cierra con un cierre acotado a la demo. AUTONOMIA-01 sigue vigente.

## Source Inputs
- `entradas/prd.md` — fuente autoritativa de requisitos
- `entradas/pvb.md` — visión de producto

## Extension Configuration
| Extension | Enabled | Decided At |
|---|---|---|
| Límite de autonomía del agente (AUTONOMIA-01..06) | Yes (siempre aplicada, sin opt-in) | Workflow start |
| Security Baseline | Yes (full, blocking) | Requirements Analysis |
| Resiliency Baseline | Yes (full, blocking) | Requirements Analysis |
| Property-Based Testing | Yes (full enforcement, PBT-01..10) | Requirements Analysis |

## Project-Wide Decisions
| Decisión | Valor | Decidido en |
|---|---|---|
| Pruebas de resiliencia (RESILIENCY-14, NFR-RES-14) | C: diferir la ejecución a Operations; cada unidad con runtime documenta sus escenarios en NFR Design o Infrastructure Design (escenarios mínimos en `construction/contracts/nfr-design/nfr-design-patterns.md` P-U0-08). La sección `resilience` de U12 ejecuta en kind lo que piden US-608 y US-610; la ejecución a escala sigue en Operations (2026-10-31) | U0 NFR Design, 2026-10-03T09:20:34Z |
| Evidencia de AUTONOMIA-03 y AUTONOMIA-06 | Por unidad, con lo que exista en ese momento (dobles y X01), y la demostración completa de RT-3 y RT-5 en U12. Una unidad puede cerrar sin esa demostración, pero la historia no pasa hasta que U12 la entregue (BR-U12-13) | seguimiento de la cuarta revisión de coherencia, 2026-10-31 |
| MinIO en staging y prod | Se reemplaza por el S3 del banco, si ofrece object lock, versionado y lifecycle; MinIO queda solo en kind. Sin implementar | issue 26, 2026-11-02 |
| K11: permisos de ESO en staging y prod | Una instancia de ESO por namespace; en kind sigue el permiso de lectura. Sin implementar ni probar | issue 26, 2026-11-02 |

## Execution Plan Summary
- **Stages to Execute**: Application Design, Units Generation; por unidad: Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation Part 1 (Planning)
- **Stages to Skip**: Reverse Engineering (greenfield); Code Generation Part 2 y Build and Test (fuera de alcance por instrucción del usuario)

## Stage Progress
### 🔵 INCEPTION PHASE
- [x] Workspace Detection
- [x] Reverse Engineering — SKIPPED (greenfield)
- [x] Requirements Analysis — aprobado 2026-09-26T13:36:39Z
- [x] User Stories — aprobado 2026-09-26T13:46:11Z
- [x] Workflow Planning — aprobado 2026-09-26T14:05:03Z
- [x] Application Design — aprobado 2026-09-26T16:16:15Z
- [x] Units Generation — aprobado 2026-09-26T16:43:40Z (13 unidades)

### 🟢 CONSTRUCTION PHASE (por unidad)
- [x] Functional Design — EXECUTE (U0–U12 aprobadas o SKIP; ver tabla por unidad)
- [x] NFR Requirements — EXECUTE (U0–U12)
- [x] NFR Design — EXECUTE (U0–U12 aprobadas o SKIP)
- [x] Infrastructure Design — EXECUTE (U0–U12 aprobadas o SKIP)
- [x] Code Generation — EXECUTE Part 1 (Planning) únicamente (planes de U0–U12 aprobados; Part 2 no se ejecuta)
- [ ] Build and Test — FUERA DE ALCANCE (instrucción del usuario)

### 🟡 OPERATIONS PHASE
- [ ] Operations — PLACEHOLDER

## Current Status
- **Lifecycle Phase**: CONSTRUCTION
- **Current Stage**: CONSTRUCTION cerrada en los planes de tareas de U0–U12
- **Next Stage**: U1 cerrada con alcance acotado a kind (Pasos 19, 20 y 23; `construction/platform-foundation/evidence/cierre-acotado.md`). El failover de zona sigue inconcluso. K11 y MinIO ya tienen decisión (issue 26), sin implementar, y bloquean staging y prod hasta entonces. U2 en construcción (faltan los Pasos 12, 15, 16 y 18); después U3–U12 con el alcance de `construction/plans/demo-kind-alcance.md`.

## Per-Unit Progress (CONSTRUCTION)
| Unidad | FD | NFR Req | NFR Design | Infra Design | Plan de tareas |
|---|---|---|---|---|---|
| U0 contracts | aprobado 2026-10-03T08:58:44Z | aprobado 2026-10-03T09:16:13Z | aprobado 2026-10-03T09:26:29Z | SKIP | aprobado 2026-10-03T09:39:46Z |
| U1 platform-foundation | SKIP | aprobado 2026-10-03T10:01:39Z | aprobado 2026-10-03T10:19:24Z | aprobado 2026-10-03T10:44:59Z | aprobado 2026-10-03T10:52:00Z |
| U2 identity-edge | aprobado 2026-10-03T11:05:10Z | aprobado 2026-10-03T11:18:11Z | aprobado 2026-10-03T11:26:41Z | aprobado 2026-10-03T11:36:53Z | aprobado 2026-10-03T11:40:12Z |
| U3 decision-registry | aprobado 2026-10-03T11:52:56Z | aprobado 2026-10-03T12:06:26Z | aprobado 2026-10-03T12:16:10Z | aprobado 2026-10-03T12:24:50Z | aprobado 2026-10-03T12:28:30Z |
| U4 governance | aprobado 2026-10-03T12:39:24Z | aprobado 2026-10-03T12:50:53Z | aprobado 2026-10-03T12:58:28Z | aprobado 2026-10-03T13:08:38Z | aprobado 2026-10-03T13:12:18Z |
| U5 reference-model | aprobado 2026-10-03T13:29:02Z | aprobado 2026-10-03T13:33:47Z | SKIP | SKIP | aprobado 2026-10-03T13:40:29Z |
| U6 model-serving | SKIP | aprobado 2026-10-03T13:49:53Z | aprobado 2026-10-03T14:01:54Z | aprobado 2026-10-03T14:08:03Z | aprobado 2026-10-03T14:09:39Z |
| U7 scoring-explainability | aprobado 2026-10-03T16:01:21Z | aprobado 2026-10-03T16:10:17Z | aprobado 2026-10-03T16:31:50Z | aprobado 2026-10-03T16:39:39Z | aprobado 2026-10-03T16:45:48Z |
| U8 case-management | aprobado 2026-10-06T22:28:34Z | aprobado 2026-10-08T02:01:51Z | aprobado 2026-10-08T02:30:25Z | aprobado 2026-10-08T03:55:19Z | aprobado 2026-10-08T04:15:32Z |
| U9 bias-monitoring | aprobado 2026-10-10T10:14:20Z | aprobado 2026-10-10T10:57:22Z | aprobado 2026-10-10T11:06:54Z | aprobado 2026-10-10T11:22:07Z | aprobado 2026-10-10T11:31:14Z |
| U10 console | aprobado 2026-10-10T12:21:18Z | aprobado 2026-10-10T12:36:04Z | aprobado 2026-10-10T12:47:00Z | aprobado 2026-10-10T15:15:03Z | aprobado 2026-10-10T15:19:16Z |
| U11 product-metrics | aprobado 2026-10-10T15:40:21Z | aprobado 2026-10-10T15:54:45Z | aprobado 2026-10-10T16:05:31Z | aprobado 2026-10-10T16:18:58Z | aprobado 2026-10-10T16:22:22Z |
| U12 system-verification | aprobado 2026-10-10T16:33:18Z | aprobado 2026-10-10T16:42:08Z | SKIP | aprobado 2026-10-10T16:59:00Z | aprobado 2026-10-10T17:05:37Z |


### Revisiones posteriores a la aprobación (segunda revisión del Infrastructure Design de U10, 2026-10-10)
Las fechas de la tabla son las de la **aprobación original** de cada etapa. Varias unidades ya
aprobadas se modificaron después, por las revisiones de unidades posteriores; cada cambio está en la
tabla de cambios de la unidad afectada y en `audit.md`. Las de más impacto:

| Unidad | Etapas tocadas después de aprobarse | Por qué revisión |
|---|---|---|
| U0 contracts | FD, NFR, NFR Design, plan | FD, NFR, NFR Design e Infrastructure Design de U9 y U10 |
| U1 platform-foundation | NFR, NFR Design, Infra, plan | FD a plan de U9; Infrastructure Design de U10; FD a Infra de U11; Infrastructure Design de U12 (K16, F07) |
| U2 identity-edge | FD, Infra, plan | FD de U9; FD, NFR, Infra de U10; NFR de U11; Infrastructure Design de U12 (`verification-reader`) |
| U3 decision-registry | FD, NFR, NFR Design, Infra, plan | FD a plan de U9; NFR Design e Infra de U10 (verificación bajo demanda); FD y NFR Design de U11 (proyección `metrics`); Infrastructure Design de U12 (`x06-probe`, F111) |
| U4 governance | FD, NFR, Infra, plan | FD de U9; Infrastructure Design de U10 |
| U6 model-serving | Infra | Infrastructure Design de U10 |
| U8 case-management | FD, NFR, Infra, plan | FD e Infrastructure Design de U10 |
| U9 bias-monitoring | FD, NFR, NFR Design, Infra, plan | FD, NFR e Infrastructure Design de U10; FD de U11 (permisos de carpeta); Infrastructure Design de U12 (`x04-probe`) |
| U10 console | FD, NFR | Sus propias etapas posteriores: NFR Requirements y NFR Design (endpoints 28 y 29), Infrastructure Design (step-up, BR-U10-09b a 22) |
| U11 product-metrics | plan | FD de U12 (verificación en kind al día siguiente; `RuidoExplicacion` por `promtool`) |
| Inventario (`component-dependency.md`) | Flujos y bindings | F109–F111 y K16 agregados por U10, U11 y U12; `channel-simulator` fuera del clúster |
| U0, U1, U2, U3, U8, U9, U11, U12 | FD, NFR, NFR Design, Infra y planes | Pendientes posteriores al cierre de CONSTRUCTION (2026-10-10): breaker por fallos seguidos, `EntryFilter` paginado, `registry_ondemand`, `ever_degraded`, `rt5-demo`, alertas de U11 en dos ramas, cierre de los planes de U12 |
| U0, U1, U3, U4, U7, U12; inventario de unidades | Infra (cuotas), NFR Design (alertas) y planes | Revisión de coherencia entre unidades (2026-10-10): cuotas de U3 y U4 declaradas y U7 recalculada; copia de `received_at`, `channel`, `attempt` y `first_evaluation` en el plan de U7; `ServingConfigStale` en P-U4-08; diseño de U1 con `GrafanaFolderPermissionsDrift`, el Job de F110 y el Pushgateway persistente; matriz de dependencias completa |
| U1; catálogo de componentes | NFR, NFR Design y plan; `components.md`, `application-design.md` | Segunda revisión de coherencia (2026-10-10): `AuthDeniedBurst` solo en U2; NFR-U1-12 con las tres exenciones; C04 con `case-worker` y C14 fuera del clúster |
| U1; `unit-of-work.md` | NFR Design y plan | Tercera revisión de coherencia (2026-10-10): `FailClosedPersistente` sobre el gauge de U8; entrada de U8 con `case-worker` |
| U0–U12; inventario de flujos y de métodos | FD, NFR, NFR Design, Infra y planes | Cuarta revisión de coherencia (2026-10-31): flujos F112–F118 y egress a la API de Kubernetes por binding K; `restore-drill`; roles de base en CloudNativePG (U1); oráculos de RT-2 (5 versiones del proxy) y RT-3 (por paquete); `inference_service` en `ExplainRequest`; tipos de gobierno en U0; xDS, CRDs, Grafana, buckets de kind, cuota de `vectra-serving` |
| U0–U12; requisitos e historias | FD, NFR, NFR Design, Infra y planes; FR-BIA-05, US-503, US-603 | Seguimiento de la cuarta revisión (2026-10-31, `cross-unit-review4-followup-questions.md`): North Star con consulta previa; excepción de FR-BIA-05 solo en kind; pool `general` de 4 nodos por zona; `FreezeRecord.resolutions`; `descartada` en evidencia de `explanation_view`; `AppProject` por entorno; outlier del borde; política de referencia de U5 |
| U0–U12; requisitos e inventario | FD, NFR, NFR Design, Infra y planes; RT-5 en requisitos | Quinta revisión de coherencia (2026-10-31): RT-3 con F22 deshabilitado y RT3-c solo en U4; RT-2 con `rt2-setup` y `mark_active`; 30 endpoints en U10; celdas de U9 en `stratified`; 422 en `X-Test-Scenario`; `descartada` en PBT-U8-07; HPA del rate limit; credenciales y recursos de `model-validation-job`; certificado de Keycloak y `VECTRA_CA_BUNDLE`. Quedan abiertas las altas y medias que no eran errores de la cuarta revisión ni bloqueantes |
| U0–U12; requisitos, historias e inventario | FD, NFR, NFR Design, Infra y planes | Seguimiento de la quinta revisión (2026-10-31, `cross-unit-review5-followup-questions.md`): histograma HTTP y buckets en U0; pool `data` de 8 vCPU / 32 GiB y cuotas de `vectra-data`, `vectra-edge` y `vectra-identity`; flujos F119–F121 y bindings K17–K19; MinIO y Sentinel ante una zona caída; carga por el gateway; readiness de governance con la copia en memoria; sección `resilience` de U12; réplica síncrona en otra zona, pendiente de comprobar en kind con NFR-U1-03 |

Antes de Code Generation Part 2 de cualquier unidad, conviene revisar su plan contra su tabla de
cambios, porque las aprobaciones son anteriores a estas revisiones.