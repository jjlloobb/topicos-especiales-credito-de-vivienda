# AI-DLC State Tracking

## Project Information
- **Project Name**: Vectra Risk
- **Project Type**: Greenfield
- **Start Date**: 2026-09-26T13:02:25Z
- **Current Phase**: CONSTRUCTION
- **Current Stage**: CONSTRUCTION - todas las unidades cerradas en el plan de tareas
- **Requirements Depth**: Comprehensive (sistema regulado, alto riesgo, múltiples stakeholders)

## Workspace State
- **Existing Code**: No
- **Programming Languages**: Ninguno (solo documentos Markdown en `entradas/`)
- **Build System**: Ninguno
- **Project Structure**: Empty
- **Reverse Engineering Needed**: No
- **Workspace Root**: /home/jjlloobb/IT/PUJ/MINSC/GitHub/topicos-especiales-credito-de-vivienda/vectra-risk

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Scope Constraint (instrucción del usuario)
- **NO se escribe código**. El trabajo se detiene al terminar el plan de tareas de cada unidad
  (Code Generation Part 1 — Planning). Code Generation Part 2 y Build and Test NO se ejecutan.

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
| Pruebas de resiliencia (RESILIENCY-14, NFR-RES-14) | C: diferir la ejecución a Operations; cada unidad con runtime documenta sus escenarios en NFR Design o Infrastructure Design (escenarios mínimos en `construction/contracts/nfr-design/nfr-design-patterns.md` P-U0-08) | U0 NFR Design, 2026-10-03T09:20:34Z |

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
- **Next Stage**: ninguna dentro del alcance actual (Code Generation Part 2, Build and Test y OPERATIONS fuera de alcance)

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

Antes de Code Generation Part 2 de cualquier unidad, conviene revisar su plan contra su tabla de
cambios, porque las aprobaciones son anteriores a estas revisiones.