# AI-DLC State Tracking

## Project Information
- **Project Name**: Vectra Risk
- **Project Type**: Greenfield
- **Start Date**: 2026-09-26T13:02:25Z
- **Current Phase**: CONSTRUCTION
- **Current Stage**: CONSTRUCTION - U8 case-management - Functional Design (esperando aprobación)
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
- [ ] Functional Design — EXECUTE
- [ ] NFR Requirements — EXECUTE
- [ ] NFR Design — EXECUTE
- [ ] Infrastructure Design — EXECUTE
- [ ] Code Generation — EXECUTE Part 1 (Planning) únicamente
- [ ] Build and Test — FUERA DE ALCANCE (instrucción del usuario)

### 🟡 OPERATIONS PHASE
- [ ] Operations — PLACEHOLDER

## Current Status
- **Lifecycle Phase**: CONSTRUCTION
- **Current Stage**: U8 case-management — Functional Design
- **Next Stage**: U8 case-management — NFR Requirements

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
| U8 case-management | EN CURSO | pendiente | pendiente | pendiente | pendiente |
| U9 bias-monitoring | pendiente | pendiente | pendiente | pendiente | pendiente |
| U10 console | pendiente | pendiente | pendiente | pendiente | pendiente |
| U11 product-metrics | pendiente | pendiente | pendiente | pendiente | pendiente |
| U12 system-verification | pendiente | pendiente | SKIP | pendiente | pendiente |
