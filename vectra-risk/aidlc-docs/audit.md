# AI-DLC Audit Log — Vectra Risk

## Initial User Request
**Timestamp**: 2026-09-26T13:02:25Z
**User Input**: "Using AI-DLC, lee entradas/prd.md y entradas/pvb.md y especifica el producto que describen.
No escribas código: este trabajo se detiene al terminar el plan de tareas de cada unidad."
**AI Response**: Se muestra mensaje de bienvenida AI-DLC; se inicia INCEPTION con Workspace Detection.
**Context**: Workflow start. Restricción registrada: detenerse al final de Code Generation Part 1 (plan de tareas por unidad); no generar código.

---

## Workspace Detection
**Timestamp**: 2026-09-26T13:02:25Z
**User Input**: N/A
**AI Response**: Workspace analizado. No existe `aidlc-docs/aidlc-state.md`. No hay archivos de código ni de build; solo `AGENTS.md`, `.aidlc-rule-details/` y `entradas/*.md` (prd, pvb, icp, mercado, critica). Proyecto greenfield. Reverse Engineering se omite. Extensiones detectadas: security-baseline (opt-in), resiliency-baseline (opt-in), property-based-testing (opt-in), limite-autonomia (sin opt-in → siempre aplicada).
**Context**: INCEPTION - Workspace Detection completada; avance automático a Requirements Analysis.

---

## Requirements Analysis — Preguntas de verificación emitidas
**Timestamp**: 2026-09-26T13:02:25Z
**User Input**: N/A
**AI Response**: Leídos `entradas/prd.md` y `entradas/pvb.md`. Profundidad: Comprehensive. Se detectaron conflictos entre PRD, PVB y la extensión de límite de autonomía (fail-closed en Módulos 4-5 vs AUTONOMIA-06; freeze automático como Should vs objeción/red-teaming que lo asumen activo; tier Enterprise "self-hosted" del PVB vs Principio 2; TBD de arquitectura de la narrativa de explicación). Creado `aidlc-docs/inception/requirements/requirement-verification-questions.md` con preguntas de negocio, técnicas y opt-in de extensiones.
**Context**: INCEPTION - Requirements Analysis, GATE: esperando respuestas del usuario.

---
## Requirements Analysis — Respuestas del usuario
**Timestamp**: 2026-09-26T13:19:54Z
**User Input**: "ya respondi"
**AI Response**: Leído `requirement-verification-questions.md`. Respuestas: Q1=A, Q2=A, Q3=A, Q4=A, Q5=C, Q6=C, Q7=C, Q8=A, Q9=A, Q10=C, Q11=B, Q12=B, Q13=A, Q14=A, Q15=A, Q16=A, Q17=A, Q18=A, Q19=A, Q20=B; Security=A, Resiliency=A, PBT=A. Análisis de contradicciones: ninguna detectada. Extensiones activadas; reglas completas cargadas (security-baseline.md, resiliency-baseline.md, property-based-testing.md). La extensión Resiliency exige preguntas de seguimiento antes de finalizar requisitos (RESILIENCY-02, -03, -04, -08, -15) y se detecta tensión entre RESILIENCY-09 (autoscaling) y PRD §8 Won't have ("autoscaling y pruebas de carga a escala real"). Creado `requirement-followup-questions.md`.
**Context**: INCEPTION - Requirements Analysis, GATE: esperando respuestas de seguimiento.

---
## Requirements Analysis — Respuestas de seguimiento y generación de requisitos
**Timestamp**: 2026-09-26T13:25:31Z
**User Input**: "ya respondi"
**AI Response**: Leído `requirement-followup-questions.md`. Respuestas: R1=A, R2=A, R3=B, R4=A, R5=A, R6=B, R7=A, R8=A, R9=B. Sin contradicciones; ambigüedad R1 (Backup & Restore, horas) + R2 (RPO 0 del registro) resuelta por capas (RPO 0 ante fallo de zona vía réplica síncrona; archivado continuo de WAL fuera del sitio ante pérdida del sitio), documentada en requirements.md §8.4 y señalada para revisión. Generado `aidlc-docs/inception/requirements/requirements.md` (Comprehensive). Cumplimiento de extensiones: sin hallazgos bloqueantes.
**Context**: INCEPTION - Requirements Analysis completada; se presenta solicitud de aprobación.

---

## Requirements Analysis — Solicitud de aprobación
**Timestamp**: 2026-09-26T13:25:31Z
**User Input**: N/A
**AI Response**: Se presenta mensaje de completitud con opciones "Request Changes" / "Approve & Continue" (siguiente etapa: User Stories).
**Context**: INCEPTION - Requirements Analysis, GATE de aprobación.

---
## Requirements Analysis — Aprobación
**Timestamp**: 2026-09-26T13:36:39Z
**User Input**: "Approve & Continue"
**AI Response**: Requisitos aprobados. Requirements Analysis marcada completa. Inicio de User Stories (Part 1 - Planning).
**Context**: INCEPTION - Requirements Analysis APROBADA.

---

## User Stories — Part 1 Planning
**Timestamp**: 2026-09-26T13:36:39Z
**User Input**: N/A
**AI Response**: Evaluación de necesidad documentada en `inception/plans/user-stories-assessment.md` (Execute = Yes). Creado `inception/plans/story-generation-plan.md` con checklist y preguntas embebidas.
**Context**: INCEPTION - User Stories, GATE: esperando respuestas del plan.

---
## User Stories — Respuestas del plan
**Timestamp**: 2026-09-26T13:41:05Z
**User Input**: "ya respondi"
**AI Response**: Respuestas leídas: Q1=C, Q2=A, Q3=A, Q4=A, Q5=C, Q6=B, Q7=A, Q8=A. Sin ambigüedades ni contradicciones. Enfoque resultante añadido al plan (Parte C). Se solicita aprobación explícita del plan antes de la generación (Step 13).
**Context**: INCEPTION - User Stories Part 1, GATE: aprobación del plan.

---
## User Stories — Aprobación del plan
**Timestamp**: 2026-09-26T13:41:05Z
**User Input**: "Aprobado"
**AI Response**: Plan de historias aprobado. Ejecutada Part 2 - Generation: `inception/user-stories/personas.md` (6 personas) y `inception/user-stories/stories.md` (6 épicas, 49 historias, Gherkin + Verificación, matriz de trazabilidad, mapa de demos Sesión 16, verificación INVEST). Todos los pasos del plan marcados [x]. Cumplimiento de extensiones: sin hallazgos bloqueantes.
**Context**: INCEPTION - User Stories Part 2 completada.

---

## User Stories — Solicitud de aprobación
**Timestamp**: 2026-09-26T13:41:05Z
**User Input**: N/A
**AI Response**: Se presenta mensaje de completitud con opciones "Request Changes" / "Approve & Continue" (siguiente: Workflow Planning).
**Context**: INCEPTION - User Stories, GATE de aprobación.

---
## User Stories — Aprobación
**Timestamp**: 2026-09-26T13:46:11Z
**User Input**: "Approve & COntinue"
**AI Response**: Historias y personas aprobadas. User Stories marcada completa. Inicio de Workflow Planning.
**Context**: INCEPTION - User Stories APROBADA.

---

## Workflow Planning — Plan generado
**Timestamp**: 2026-09-26T13:46:11Z
**User Input**: N/A
**AI Response**: Creado `inception/plans/execution-plan.md`. EXECUTE: Application Design, Units Generation, Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation Part 1. SKIP: Reverse Engineering. FUERA DE ALCANCE: Code Generation Part 2, Build and Test. Riesgo: High. Mermaid validado (IDs alfanuméricos, etiquetas sin comillas) + alternativa en texto. AI Prompt: "Ready to proceed with this plan?"
**Context**: INCEPTION - Workflow Planning, GATE de aprobación.

---
## Workflow Planning — Cambios solicitados
**Timestamp**: 2026-09-26T13:53:54Z
**User Input**: "Request Changes: incluye Application Design y Units Generation en el plan de ejecución.
El entregable de este trabajo son las unidades de trabajo y sus tareas; sin esas dos
etapas no existe."
**AI Response**: Ambas etapas ya figuraban como EXECUTE, pero con estilo de etapa condicional. Se reclasificaron como OBLIGATORIAS (no omitibles) en diagrama, texto alternativo y lista de fases; se agregó la sección "Entregable de este trabajo" (application design → unidades de trabajo → plan de tareas por unidad). Se vuelve a solicitar aprobación.
**Context**: INCEPTION - Workflow Planning, cambios aplicados; GATE de aprobación.

---
## Workflow Planning — Aprobación
**Timestamp**: 2026-09-26T14:05:03Z
**AI Prompt**: "Ready to proceed with this plan?"
**User Response**: "execution-plan is ok"
**Status**: Approved
**Context**: Plan con Application Design y Units Generation obligatorias; CONSTRUCTION por unidad hasta Code Generation Part 1.

---

## Application Design — Plan y preguntas
**Timestamp**: 2026-09-26T14:05:03Z
**User Input**: N/A
**AI Response**: Creado `inception/plans/application-design-plan.md` con checklist y 8 preguntas de diseño (límites de componentes, orquestación, sincronía/asincronía, gateway, co-ubicación del explicador, mecanismo de congelamiento, métricas de negocio).
**Context**: INCEPTION - Application Design, GATE: esperando respuestas.

---
## Application Design — Respuestas y generación
**Timestamp**: 2026-09-26T15:38:17Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q8 = A. Sin ambigüedades ni contradicciones. Generados en `inception/application-design/`: components.md (18 componentes con criticidad), component-methods.md (tipos compartidos, contrato de sincronía, firmas), services.md (flujos S1–S9), component-dependency.md (matriz, Mermaid validado + alternativa en texto, fronteras de confianza), application-design.md (consolidado + compliance). Checklist del plan marcado [x]. Sin hallazgos bloqueantes de extensiones.
**Context**: INCEPTION - Application Design completada; solicitud de aprobación (Request Changes / Approve & Continue → Units Generation).

---
## Application Design — Cambios solicitados
**Timestamp**: 2026-09-26T15:56:04Z
**User Input**: "Request changes: La matriz de dependencias está incompleta para el propósito que ella misma se asigna. y component-methods.md no tiene tabla de endpoints para console-bff (C03) y La tabla de cumplimiento de application-design.md §7 dice \"SECURITY-01..15 | Cumple a nivel de diseño\" pero la columna de evidencia solo nombra explícitamente unas 10 de las 15 reglas (faltan 04, 09, 10, 12, 13 en esa fila, aunque sí aparecen en components.md en otras secciones)"
**AI Response**: (1) component-dependency.md reescrito como inventario cerrado: namespaces, flujos de red F01–F73 con puerto/controles, acceso a API de Kubernetes K01–K06, roles de BD, egress cerrado (backup WAL, Git de Argo CD, notificación Alertmanager, federación IdP futura), flujos prohibidos X01–X10 con su prueba; se corrigieron omisiones (columna BFF inexistente, BDs, observabilidad, leyenda J sin uso: governance crea Jobs en staging → K01). (2) component-methods.md: tabla de endpoints de console-bff con rol, MFA, regla de objeto y destino. (3) application-design.md §7 reescrito una fila por regla (AUTONOMIA, SECURITY-01..15, RESILIENCY-01..15, PBT) con evidencia o motivo N/A. components.md alineado (C09 K01, C16 clientes/keycloak-db, C17 F72).
**Context**: INCEPTION - Application Design, cambios aplicados; nueva solicitud de aprobación.

---
## Application Design — Aprobación
**Timestamp**: 2026-09-26T16:16:15Z
**User Input**: "Approve & Continue"
**AI Response**: Application Design aprobada y marcada completa. Inicio de Units Generation Part 1 (Planning).
**Context**: INCEPTION - Application Design APROBADA.

---

## Units Generation — Part 1 Planning
**Timestamp**: 2026-09-26T16:16:15Z
**User Input**: N/A
**AI Response**: Creado `inception/plans/unit-of-work-plan.md` con descomposición propuesta, checklist y 8 preguntas (granularidad, scoring+explainability, contratos compartidos, organización del código y repositorio GitOps, equipo, secuencia vs módulos del curso, modelo de referencia, verificación de sistema/red-teaming).
**Context**: INCEPTION - Units Generation, GATE: esperando respuestas.

---
## Units Generation — Respuestas del plan
**Timestamp**: 2026-09-26T16:20:14Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q8 = A. Sin ambigüedades ni contradicciones. Descomposición resultante añadida al plan (Parte D): 13 unidades (U0 contracts ... U12 system-verification). AI Prompt: "Unit of work plan complete. Review the plan in aidlc-docs/inception/plans/unit-of-work-plan.md. Ready to proceed to generation?"
**Context**: INCEPTION - Units Generation Part 1, GATE: aprobación del plan.

---
## Units Generation — Aprobación del plan y generación
**Timestamp**: 2026-09-26T16:33:59Z
**User Input**: "Approved & Continue"
**AI Response**: Plan de unidades aprobado. Part 2 ejecutada: unit-of-work.md (13 unidades U0–U12, etapas de CONSTRUCTION por unidad con justificación de omisiones, organización del código en monorepo + repo vectra-risk-gitops, mapa a módulos del curso), unit-of-work-dependency.md (matriz, orden secuencial, ruta crítica, Mermaid + texto, recursos compartidos; dependencia runtime U4↔U9 resuelta vía contrato U0, sin ciclo de construcción), unit-of-work-story-map.md (49/49 historias con dueña, contribuyentes y verificación e2e; RT-1..5 y X01–X10 asignados; 18/18 componentes asignados). Árbol de directorios convertido a ASCII (ascii-diagram-standards). Checklist del plan [x]. Sin hallazgos bloqueantes.
**Context**: INCEPTION - Units Generation completada; solicitud de aprobación (→ CONSTRUCTION).

---
## Units Generation — Aprobación
**Timestamp**: 2026-09-26T16:43:40Z
**User Input**: "Approve & Continue"
**AI Response**: Units Generation aprobada. INCEPTION completa. Inicio de CONSTRUCTION con U0 contracts — Functional Design (plan y preguntas).
**Context**: Transición INCEPTION → CONSTRUCTION.

---
## U0 contracts — Functional Design: plan y preguntas
**Timestamp**: 2026-09-26T16:43:40Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/contracts-functional-design-plan.md` con 8 preguntas (campos de la solicitud, PII/redacción, categorías de MonitoringLabels, datos de entrada en el registro, diccionario de features, modelo de errores, versionado, representación de montos/tasas) y checklist.
**Context**: CONSTRUCTION - U0 contracts - Functional Design, GATE: esperando respuestas.

---
## U0 contracts — Functional Design: respuestas y generación
**Timestamp**: 2026-09-26T16:58:26Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q8 = A, sin ambigüedades. Generados domain-entities.md, business-rules.md (BR-U0-01..92), business-logic-model.md (11 propiedades PBT). Correcciones de consistencia detectadas al cruzar catálogo de scopes con inventario cerrado de flujos: (1) eliminado scope registry:append:bias (bias no escribe al registro); (2) agregado flujo F08 promotion-tool -> api-gateway -> governance (solo list_promotable/mark_active, token de usuario ingeniero_riesgo con MFA + scope governance:promotion) en component-dependency.md, que el inventario aprobado omitía.
**Context**: CONSTRUCTION - U0 contracts - Functional Design completada; solicitud de aprobación.

---
## U0 contracts — Functional Design: revisión solicitada por el usuario
**Timestamp**: 2026-10-03T03:33:54Z
**User Input**: "revisa la fase de CONSTRUCCION si se deben realizar algunos refinamientos"
**AI Response**: Revisado el FD de U0 contra component-methods, component-dependency, unit-of-work y extensiones. Hallazgos: 3 bloqueantes (H1 firma/precedencia de build_outcome contradice BR-U0-02 y PBT-U0-01 — AUTONOMIA-06; H2 doble transporte de FailClosed 200 vs 503; H3 score/confidence float vs Q8), 3 importantes (H4 tipos de contrato faltantes; H5 serialización JSON de Decimal; H6 divergencia con component-methods y cambio F08 a artefacto aprobado), 5 menores (M1–M5) e higiene (*original.md, .swp en extensión autonomia). Creado `construction/plans/contracts-functional-design-review-questions.md` con 8 preguntas. La etapa permanece en Request Changes hasta resolverlas.
**Context**: CONSTRUCTION - U0 contracts - Functional Design, GATE: esperando respuestas de la revisión.

---
## U0 contracts — Functional Design: respuestas de la revisión y cambios
**Timestamp**: 2026-10-03T03:45:13Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q8 = A, sin ambigüedades. Aplicados los cambios a domain-entities.md, business-rules.md y business-logic-model.md (detalle en la Parte C de `construction/plans/contracts-functional-design-review-questions.md`). Nuevas reglas BR-U0-06, 07, 15, 31..34, 93, 95; reescritas BR-U0-01..03, 62, 71, 73; nuevas propiedades PBT-U0-12 y PBT-U0-13; redefinidas PBT-U0-01, 02 y 09. Corrección adicional en BR-U0-71: los roles se evalúan por intersección, no por subconjunto (con subconjunto, un endpoint para «analista, cro» exigía los dos roles a la vez).
**Cambio a artefacto aprobado de INCEPTION**: `inception/application-design/component-methods.md` recibe una nota que declara a U0 fuente autoritativa de los contratos (Q6=A). Se deja constancia también del flujo F08 agregado a `component-dependency.md` el 2026-09-26T16:58:26Z.
**Context**: CONSTRUCTION - U0 contracts - Functional Design actualizado; solicitud de aprobación.

---
## U0 contracts — Functional Design: segunda revisión
**Timestamp**: 2026-10-03T08:46:07Z
**User Input**: "Revise primero si todo lo generado en la fase CONSTRUCCION esta bien o necesita refinarse"
**AI Response**: Segunda revisión del FD de U0 (única unidad con trabajo en CONSTRUCTION). Hallazgos importantes: N1 ciclo entre build_outcome y el registro (la entrada recommendation necesita el resultado antes del ack); N2 la firma no admite dependencias no invocadas; N3 salida inválida del modelo mapeada a serving_config_unavailable; N4 DecisionIn no cubre revision_requerida. Menores: N5 canonicalización de feature_vector_hash; N6 deny by default vs health/metrics en 8081; N7 payload recommendation sin evaluated_at ni feature_vector_hash. Creado `construction/plans/contracts-functional-design-review2-questions.md` con 4 preguntas. La etapa sigue sin aprobar.
**Context**: CONSTRUCTION - U0 contracts - Functional Design, GATE: esperando respuestas de la segunda revisión.

---
## U0 contracts — Functional Design: respuestas de la segunda revisión y cambios
**Timestamp**: 2026-10-03T08:52:01Z
**User Input**: "ya la respondi"
**AI Response**: Respuestas Q1..Q4 = A, sin ambigüedades. Aplicados: invariante en dos fases (check_preconditions → Ready → registro → build_outcome) con BR-U0-01..03 reescritas y BR-U0-08 nueva; dependencias opcionales (S2); causa model_output_invalid (catálogo de 10); resuelve_revision y BR-U0-35; JCS para feature_vector_hash; BR-U0-71 limitado al puerto 8080; payload recommendation con evaluated_at y feature_vector_hash. PBT-U0-01 y PBT-U0-12 actualizadas. Nota de component-methods.md ajustada a 10 causas. Detalle en la Parte C de `construction/plans/contracts-functional-design-review2-questions.md`.
**Context**: CONSTRUCTION - U0 contracts - Functional Design actualizado; solicitud de aprobación.

---
## U0 contracts — Functional Design: aprobación
**Timestamp**: 2026-10-03T08:58:44Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U0 aprobado. Inicio de U0 contracts — NFR Requirements (plan y preguntas).
**Context**: CONSTRUCTION - U0 contracts - Functional Design completado → NFR Requirements.

---
## U0 contracts — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T08:58:44Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/contracts-nfr-requirements-plan.md` con 11 preguntas (fuente de verdad de contratos, Python/uv, distribución, librería JWT y JWKS, fallo de Keycloak, presupuesto de latencia, umbral de calidad de pruebas, cliente TS y decimales, oasdiff, snapshot DIVIPOLA, structlog) y checklist. Disponibilidad y escalabilidad marcadas N/A para U0 (sin runtime propio).
**Context**: CONSTRUCTION - U0 contracts - NFR Requirements, GATE: esperando respuestas.

---
## Revisión de component-methods.md contra U0
**Timestamp**: 2026-10-03T09:05:15Z
**User Input**: "revisa primero component-method.md si requiere correcion"
**AI Response**: Revisado `inception/application-design/component-methods.md` contra el FD aprobado de U0 y component-dependency.md. Hallazgos: C1 bloque de tipos y párrafo del invariante desactualizados (float, 7 causas, invariante de una fase); C2 apply_policy recibe `app` y devuelve Outcome (U0: PolicyInputs → PolicyResult); C3 append lista a bias y devuelve RegistryEntryRef (U0: RegistryAck); C4 query omite explainability (F23); C5 record_decision sin resuelve_revision; C6 regla de JWT sin aclarar el puerto 8081; C7 hueco en U0: no hay scope para core-banking-mock (F17) y deny by default lo bloquearía. Creado `construction/plans/contracts-component-methods-review-questions.md` con 2 preguntas (C1, C7); C2–C6 se corrigen sin preguntar. Las preguntas de NFR Requirements de U0 siguen pendientes.
**Context**: CONSTRUCTION - U0 contracts - NFR Requirements en espera; revisión lateral de un artefacto de INCEPTION.

---
## Revisión de component-methods.md — respuestas y cambios
**Timestamp**: 2026-10-03T09:09:32Z
**User Input**: "ya respondi"
**AI Response**: component-methods-review Q1..Q2 = A. Aplicado C1–C7 (detalle en la Parte D de `construction/plans/contracts-component-methods-review-questions.md`).
**Cambio a artefactos aprobados**: `inception/application-design/component-methods.md` (tipos compartidos, C04, C05, C12, C15, encabezado) y `component-dependency.md` (controles de F17); FD aprobado de U0 (`domain-entities.md` §7.2: scopes `core:read-credit` y `core:write-credit`).
**Context**: Corrección lateral; continúa CONSTRUCTION - U0 contracts - NFR Requirements.

---
## U0 contracts — NFR Requirements: respuestas
**Timestamp**: 2026-10-03T09:09:32Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q11 = A, sin ambigüedades. Se generan nfr-requirements.md y tech-stack-decisions.md.
**Context**: CONSTRUCTION - U0 contracts - NFR Requirements, generación de artefactos.

---
## U0 contracts — NFR Requirements: generación
**Timestamp**: 2026-10-03T09:09:32Z
**User Input**: N/A
**AI Response**: Generados `construction/contracts/nfr-requirements/nfr-requirements.md` (NFR-U0-01..46: rendimiento, seguridad, confiabilidad y datos, mantenibilidad, calidad de pruebas; disponibilidad y escalabilidad N/A justificadas; cumplimiento de extensiones) y `tech-stack-decisions.md` (Python 3.12 + uv, Pydantic v2 code-first, PyJWT, structlog, OTel, openapi-typescript + openapi-fetch + decimal.js, Hypothesis + fast-check, oasdiff, mutmut, pytest-benchmark, import-linter). Vitest queda como propuesta a confirmar en U10. Checklist del plan [x]. Sin hallazgos bloqueantes.
**Context**: CONSTRUCTION - U0 contracts - NFR Requirements completada; solicitud de aprobación.

---
## U0 contracts — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T09:16:13Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U0 aprobado. Inicio de U0 contracts — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U0 contracts - NFR Requirements completado → NFR Design.

---
## U0 contracts — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T09:16:13Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/contracts-nfr-design-plan.md` con 10 preguntas (fábrica de app, declaración de authz, cache de JWKS single-flight, protección de la fábrica de Recommendation, campos descartados en logs, jerarquía de errores, registro de contratos de rutas, muestreo de trazas, contexto Decimal, enfoque de pruebas de resiliencia RESILIENCY-14 a nivel proyecto). Escalabilidad N/A justificada.
**Context**: CONSTRUCTION - U0 contracts - NFR Design, GATE: esperando respuestas.

---
## U0 contracts — NFR Design: respuestas y generación
**Timestamp**: 2026-10-03T09:20:34Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q9 = A, Q10 = C, sin ambigüedades. Generados `construction/contracts/nfr-design/nfr-design-patterns.md` (P-U0-01..12: fábrica única de app, authz declarativa con auditoría al arrancar, invariante en tres capas, allowlist de logs con conteo y modo strict, jerarquía cerrada de errores, cache de JWKS single-flight, helper de dependencias con timeout obligatorio, enfoque de pruebas de resiliencia C, presupuesto en CI, contexto decimal propio, trazas al 100 % con allowlist, registro de contratos de rutas; escalabilidad N/A) y `logical-components.md` (inventario, métricas, diagrama Mermaid con alternativa en texto, reglas de import-linter, dependencias externas). RESILIENCY-14 = C registrado como decisión del proyecto en aidlc-state.md. Checklist del plan [x].
**Context**: CONSTRUCTION - U0 contracts - NFR Design completada; solicitud de aprobación.

---
## U0 contracts — NFR Design: aprobación
**Timestamp**: 2026-10-03T09:26:29Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U0 aprobado. Infrastructure Design de U0 = SKIP (sin despliegue, según unit-of-work.md §2). Inicio de Code Generation Part 1 (plan de tareas) de U0.
**Context**: CONSTRUCTION - U0 contracts - NFR Design completado → Code Generation Part 1.

---
## U0 contracts — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T09:26:29Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/contracts-code-generation-plan.md` (24 pasos en 7 bloques: estructura, lógica de negocio, capa de API, repositorio N/A, specs y cliente TS, calidad y CI, documentación y despliegue N/A), cada paso con comando de aceptación (AUTONOMIA-02) y sin acciones sobre clúster (AUTONOMIA-01). Trazabilidad a US-111, 601, 602, 604, 611 y a PBT-U0-01..13. AI Prompt: "Plan de tareas de U0 listo para revisión. ¿Request Changes o Continue to Next Stage (U1 platform-foundation)?". Por instrucción del usuario, Part 2 no se ejecuta.
**Context**: CONSTRUCTION - U0 contracts - Code Generation Part 1, GATE: aprobación del plan.

---
## U0 contracts — Code Generation Part 1: cambios solicitados
**Timestamp**: 2026-10-03T09:34:47Z
**User Input**: "Request Changes, acotado al Paso 2 (agregar random a la lista de imports prohibidos). Es el único punto que de verdad necesita corregirse antes de que este plan de tareas quede como el artefacto final de U0 — que es, además, donde se detiene todo este trabajo para esta unidad."
**AI Response**: Paso 2 del plan corregido: `random` agregado a los imports prohibidos de `vectra_contracts` en import-linter, alineado con NFR-U0-22. Sin otros cambios. Se vuelve a solicitar aprobación del plan.
**Context**: CONSTRUCTION - U0 contracts - Code Generation Part 1, GATE: aprobación del plan.

---
## U0 contracts — Code Generation Part 1: cambios solicitados (versionado)
**Timestamp**: 2026-10-03T09:37:53Z
**User Input**: "Request Changes Las reglas de versionado (BR-U0-90..93) no aparecen citadas explícitamente por ID en ningún paso ni en los chequeos de trazabilidad intermedios (Paso 8 cubre 01..43, 80..81, 95; Paso 13 cubre 50..73) — solo quedarían cubiertas por el chequeo final --all del Paso 20. La implementación en sí está ahí (Pasos 1, 15 y 21 claramente la cubren: uv.lock único, generación de specs, oasdiff en CI), solo falta que algún paso las cite por número para que la auditoría no dependa únicamente del chequeo final."
**AI Response**: BR-U0-90 citada en el Paso 1, BR-U0-93 en el Paso 15 y BR-U0-91/92 en el Paso 21. El Paso 21 agrega test_versioning.py (una prueba por regla, con un version_gate sobre specs de fixture) y el chequeo intermedio `traceability.py --section versioning`. Se agrega a §3 una tabla regla → pasos → chequeo de trazabilidad. Observación: el Paso 22 ya citaba BR-U0-90..93, pero solo como contenido del README, sin chequeo. Se vuelve a solicitar aprobación.
**Context**: CONSTRUCTION - U0 contracts - Code Generation Part 1, GATE: aprobación del plan.

---
## U0 contracts — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T09:39:46Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U0 aprobado; es el artefacto final de U0 (Part 2 y Build and Test fuera de alcance). U0 completa. Inicio de U1 platform-foundation — NFR Requirements (Functional Design = SKIP).
**Context**: CONSTRUCTION - U0 completada → U1 NFR Requirements.

---
## U1 platform-foundation — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T09:39:46Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/platform-foundation-nfr-requirements-plan.md` con 14 preguntas (plataforma Kubernetes, operador de PostgreSQL, archive_timeout/RPO del sitio, RTO, retención de backups con WORM, almacenamiento S3-compatible, failover de zona, retención de observabilidad, secretos, admisión, cadena de suministro, mTLS, volumen de diseño, runners de CI). Lo ya decidido en INCEPTION y RESILIENCY-14 no se vuelve a preguntar.
**Context**: CONSTRUCTION - U1 platform-foundation - NFR Requirements, GATE: esperando respuestas.

---
## U1 platform-foundation — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T09:53:52Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q14 = A, sin ambigüedades. Generados `construction/platform-foundation/nfr-requirements/nfr-requirements.md` (NFR-U1-01..44) y `tech-stack-decisions.md`. Consecuencias registradas: (1) NFR-U1-03: con 2 zonas y RPO 0 (R2), la caída de la zona con 2 de 3 instancias bloquea las escrituras hasta clonar una réplica nueva (fail-closed, nunca RPO > 0); se recomienda una tercera zona en producción. (2) Linkerd requiere linkerd-cni para ser compatible con PSA restricted. (3) Loki con object lock exige retención por lifecycle del bucket, no por el compactor. (4) ESO, el almacenamiento de objetos de Loki/Tempo y el model-store pueden introducir egress y namespaces no presentes en el inventario cerrado de component-dependency.md; se formalizan en el Infrastructure Design de U1. Calico en kind queda como propuesta. Checklist del plan [x].
**Context**: CONSTRUCTION - U1 platform-foundation - NFR Requirements completada; solicitud de aprobación.

---
## U1 platform-foundation — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T10:01:39Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U1 aprobado. Inicio de U1 platform-foundation — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U1 - NFR Requirements completado → NFR Design.

---
## U1 platform-foundation — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T10:01:39Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/platform-foundation-nfr-design-plan.md` con 12 preguntas (NetworkPolicies desde un inventario de flujos, autorización por identidad en Linkerd, profundidad de la readiness frente a NFR-RES-07, severidades/COE, conteo del fail-closed en el SLO, simulacro de restore semanal, conexiones a PostgreSQL, PriorityClasses, HA de controladores y failurePolicy de Kyverno, estructura GitOps, Watchdog, rotación de certificados). RESILIENCY-14 no se repite (decisión del proyecto).
**Context**: CONSTRUCTION - U1 platform-foundation - NFR Design, GATE: esperando respuestas.

---
## U1 platform-foundation — NFR Design: respuestas y generación
**Timestamp**: 2026-10-03T10:06:56Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q12 = A, sin ambigüedades. Generados `construction/platform-foundation/nfr-design/nfr-design-patterns.md` (P-U1-01..12) y `logical-components.md` (inventario con waves y PriorityClasses, diagrama Mermaid con alternativa en texto, alertas por severidad, pendientes para Infrastructure Design). Checklist del plan [x].
**Cambio a artefacto aprobado**: `inception/requirements/requirements.md` NFR-RES-07 precisado (Q3=A): la readiness incluye solo dependencias propias de datos. US-610 («BD caída → readiness de scoring falla») se cumple vía governance-db → serving-config, ya que scoring no tiene base propia.
**Context**: CONSTRUCTION - U1 platform-foundation - NFR Design completada; solicitud de aprobación.

---
## U1 platform-foundation — NFR Design: cambios solicitados (P-U1-04)
**Timestamp**: 2026-10-03T10:11:59Z
**User Input**: "Request Changes, acotado a P-U1-04: la readiness de scoring-service no debería depender de governance/serving-config, por la misma razón exacta que ya se usó para excluir a explainability y al registro."
**AI Response**: P-U1-04 corregido: scoring-service sin dependencias en su readiness; governance/serving-config pasa a la lista de dependencias excluidas (su caída produce FailClosed(serving_config_unavailable)); criterio explícito: una dependencia entra en la readiness solo si su caída no tiene una causa tipificada de fail-closed. Verificación ampliada (governance caído → scoring listo + FailClosed). Nota de NFR-RES-07 en requirements.md ajustada en el mismo sentido. Consecuencia registrada: el escenario de US-610 («BD caída → readiness de scoring falla») ya no se cumple literalmente; su intención se verifica sobre case, governance y registry. El texto de US-610 en stories.md queda pendiente de ajuste (no modificado: fuera del alcance pedido).
**Context**: CONSTRUCTION - U1 platform-foundation - NFR Design, GATE: aprobación.

---
## U1 platform-foundation — NFR Design: cambios solicitados (US-610)
**Timestamp**: 2026-10-03T10:16:34Z
**User Input**: "Request Changes ajuste de texto en US-610 de stories.md y lo que haga falta"
**AI Response**: US-610 en `inception/user-stories/stories.md` ajustada: el escenario «dependencia caída» se reemplaza por «base de datos propia caída» (case-db → case-service no listo) y «dependencia aguas abajo caída» (explainability o governance caídos → scoring listo y FailClosed tipificado); la Verificación se actualiza en el mismo sentido. P-U1-04: el párrafo de conflicto se reemplaza por la referencia al ajuste. Plan de NFR Design: nota de refinamiento bajo la Q3 (scoring sin serving-config en la readiness). Revisadas las demás referencias a readiness (application-design.md RESILIENCY-06, unit-of-work-story-map.md): no requieren cambio.
**Cambio a artefacto aprobado**: `inception/user-stories/stories.md` (US-610).
**Context**: CONSTRUCTION - U1 platform-foundation - NFR Design, GATE: aprobación.

---
## U1 platform-foundation — NFR Design: aprobación
**Timestamp**: 2026-10-03T10:19:24Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U1 aprobado. Inicio de U1 platform-foundation — Infrastructure Design (plan y preguntas).
**Context**: CONSTRUCTION - U1 - NFR Design completado → Infrastructure Design.

---
## U1 platform-foundation — Infrastructure Design: plan y preguntas
**Timestamp**: 2026-10-03T10:19:24Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/platform-foundation-infrastructure-design-plan.md` con 11 preguntas (entornos, nodos y pools, volúmenes de PostgreSQL, destino S3 en producción, CNI, exposición del borde, namespaces de controladores, agente de logs, relación con la observabilidad del banco, registro de imágenes, servidor Git de Argo CD). Mensajería N/A: ya decidido sin broker (cola transaccional en PostgreSQL).
**Context**: CONSTRUCTION - U1 platform-foundation - Infrastructure Design, GATE: esperando respuestas.

---
## U1 platform-foundation — Infrastructure Design: respuestas y generación
**Timestamp**: 2026-10-03T10:24:05Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q11 = A, sin ambigüedades. Generados `construction/platform-foundation/infrastructure-design/infrastructure-design.md` (INF-U1-01..10: entornos, nodos y pools, volúmenes y max_connections, almacenamiento de objetos con MinIO in-cluster y backups fuera del sitio, CNI, borde, namespaces de controladores, observabilidad, imágenes, secretos), `deployment-architecture.md` (topología por zonas, namespaces, orden de instalación por waves, escenarios de resiliencia) y `construction/shared-infrastructure.md`. Checklist del plan [x].
**Cambios a artefactos aprobados**: `inception/application-design/component-dependency.md` (§0 puerto 9000; §1 namespaces; F09 federación opcional; F63 Alloy; F66–F67; nueva §2.7 F80–F87; K06 = CloudNativePG y K07–K13; F71 precisado; egress F74–F76; rangos de §7 y §9); `unit-of-work.md` (flujos y bindings de U1); `application-design.md` (rangos F01–F87, K01–K13).
**Context**: CONSTRUCTION - U1 platform-foundation - Infrastructure Design completada; solicitud de aprobación.

---
## U1 platform-foundation — Infrastructure Design: observación sobre vectra-restore-drill
**Timestamp**: 2026-10-03T10:34:36Z
**User Input**: "En INF-U1-06, la fila de vectra-restore-drill lista solo F75 como su flujo permitido — pero F87 (restore-drill → Prometheus, para publicar vectra_restore_drill_success) también se origina en ese namespace, y no aparece en esa fila. Es probable que la fuente real (flows.yaml, según P-U1-01) sí lo tenga completo y esta tabla en infrastructure-design.md sea solo un resumen ilustrativo — pero vale la pena confirmarlo para que no falte ese flujo cuando se genere el NetworkPolicy real del namespace."
**AI Response**: Confirmado que flows.yaml no existe (se crea en Code Generation, fuera de alcance); la fuente actual es component-dependency.md. Corregidas la fila de INF-U1-06 (F75 + F87 + F80) y la fila de F80 en component-dependency.md (incluye el cluster efímero de vectra-restore-drill). Hallazgo adicional: F87 es ambiguo (push o scrape: direcciones opuestas), usa el puerto 8081 en vez de 9091 y no hay Pushgateway en el inventario. Creado `construction/plans/platform-foundation-infrastructure-design-review-questions.md` con 1 pregunta.
**Cambio a artefacto aprobado**: `inception/application-design/component-dependency.md` (F80).
**Context**: CONSTRUCTION - U1 platform-foundation - Infrastructure Design, GATE: esperando respuesta.

---
## U1 platform-foundation — Infrastructure Design: respuesta de la revisión (F87)
**Timestamp**: 2026-10-03T10:38:05Z
**User Input**: "ya respondi"
**AI Response**: Q1 = A. Pushgateway agregado: F87 redefinido (restore-drill → Pushgateway, 9091, egress), F88 nuevo (Prometheus → Pushgateway), puerto 9091 en §0. Actualizados component-dependency.md, unit-of-work.md, application-design.md (rangos F80–F88 / F01–F88), infrastructure-design.md (INF-U1-06 con dirección de cada flujo, INF-U1-07, §7), deployment-architecture.md, logical-components.md (inventario, diagrama y texto) y nfr-design-patterns.md P-U1-05 (NetworkPolicies, push, RestoreDrillMissing con push_time_seconds). Detalle en la Parte C de `construction/plans/platform-foundation-infrastructure-design-review-questions.md`.
**Cambios a artefactos aprobados**: component-dependency.md, unit-of-work.md, application-design.md (INCEPTION); nfr-design-patterns.md y logical-components.md (NFR Design aprobado de U1).
**Context**: CONSTRUCTION - U1 platform-foundation - Infrastructure Design; solicitud de aprobación.

---
## U1 platform-foundation — Infrastructure Design: cambios solicitados (sidecar nativo)
**Timestamp**: 2026-10-03T10:42:18Z
**User Input**: "Request Changes, agrega el sidecar nativo de Linkerd en P-U1-05"
**AI Response**: P-U1-05 (nfr-design-patterns.md) actualizado: anotación config.alpha.linkerd.io/proxy-enable-native-sidecar en el namespace vectra-restore-drill y en el pod template del CronJob; explicación del problema (proxy que impide que el Job termine), cobertura de los Jobs de bootstrap de CloudNativePG, requisitos (Kubernetes ≥ 1.29, versión de Linkerd fijada en Chart.lock) y verificación ampliada (Job Complete y restartPolicy Always del proxy).
**Cambio a artefacto aprobado**: NFR Design de U1 (P-U1-05).
**Context**: CONSTRUCTION - U1 platform-foundation - Infrastructure Design; solicitud de aprobación.

---
## U1 platform-foundation — Infrastructure Design: aprobación
**Timestamp**: 2026-10-03T10:44:59Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U1 aprobado. Inicio de Code Generation Part 1 (plan de tareas) de U1.
**Context**: CONSTRUCTION - U1 - Infrastructure Design completado → Code Generation Part 1.

---
## U1 platform-foundation — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T10:44:59Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/platform-foundation-code-generation-plan.md` (23 pasos en 10 bloques: estructura, red y malla, políticas, datos y secretos, observabilidad, resiliencia, GitOps, CI, verificación en kind con aprobación humana, cierre). Aclaración de AUTONOMIA-01: las verificaciones se dividen en estáticas (CI, autónomas) y en kind (ejecutadas por un operador tras un PR aprobado, con evidencia adjunta), porque la regla incluye el clúster de desarrollo. La prueba de carga (NFR-U1-11) se difiere a U12. AI Prompt: "Plan de tareas de U1 listo para revisión. ¿Request Changes o Continue to Next Stage (U2 identity-edge)?". Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U1 platform-foundation - Code Generation Part 1, GATE: aprobación del plan.

---
## U1 platform-foundation — Code Generation Part 1: observación sobre la trazabilidad
**Timestamp**: 2026-10-03T10:50:25Z
**User Input**: "La tabla resumen de trazabilidad (§3) lista NFR-U1-10..13 como cubiertas en los pasos \"6, 14, 21\" — pero NFR-U1-12 (límites de HPA) en realidad se implementa en el Paso 5 (la política require-hpa-bounds), que sí la cita correctamente en su propia línea de \"Diseño\". Es solo la tabla resumen final la que no refleja ese paso — la implementación y la cita a nivel de paso están bien, nada que corregir en la sustancia."
**AI Response**: Corregida la fila NFR-U1-10..13 (agrega el Paso 5). Al cruzar toda la tabla contra las líneas «Diseño» aparecieron desfases del mismo tipo, también corregidos: NFR-U1-20..27 (+7, +15), NFR-U1-40..44 (+5, por NFR-U1-43), P-U1-01..12 (+20, por P-U1-04), INF-U1-01..10 (+3, +14). Además, dos requisitos no se citaban en ningún paso aunque la implementación existía: NFR-U1-20 (agregado al Paso 3) y NFR-U1-23 (agregado a los Pasos 7 y 15).
**Context**: CONSTRUCTION - U1 platform-foundation - Code Generation Part 1, GATE: aprobación del plan.

---
## U1 platform-foundation — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T10:52:00Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U1 aprobado; artefacto final de U1 (Part 2 y Build and Test fuera de alcance). U1 completa. Inicio de U2 identity-edge — Functional Design.
**Context**: CONSTRUCTION - U1 completada → U2 Functional Design.

---
## U2 identity-edge — Functional Design: plan y preguntas
**Timestamp**: 2026-10-03T10:52:00Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/identity-edge-functional-design-plan.md` con 12 preguntas (separación de funciones, método de MFA, step-up para aprobaciones, fuerza bruta, vida de tokens y sesiones, autenticación de identidades de servicio, audiencia del token propagado por el BFF, límites del gateway, cabeceras y embebido de Grafana, realm como código y consola admin, usuarios por entorno, eventos de Keycloak).
**Context**: CONSTRUCTION - U2 identity-edge - Functional Design, GATE: esperando respuestas.

---
## U2 identity-edge — Functional Design: respuestas y generación
**Timestamp**: 2026-10-03T10:56:48Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q12 = A, sin ambigüedades. Generados `construction/identity-edge/functional-design/domain-entities.md` (realm, ACR, claims, clientes de usuario y de servicio con scopes de U0, usuarios por entorno, rutas del gateway F01–F09 con límites y perfiles de cabeceras, eventos, parámetros), `business-rules.md` (BR-U2-01..17) y `business-logic-model.md` (módulos, flujos de login, step-up, client credentials y gateway; PBT-U2-01..08; pruebas de ejemplo). Checklist del plan [x].
**Cambios a artefactos aprobados de U0**: `contracts/functional-design/business-rules.md` BR-U0-70 (`aud` contiene el servicio, Q7) y BR-U0-72 (step-up con acr = mfa y auth_time ≤ mfa_max_age, Q3); `domain-entities.md` (`Principal` con acr y auth_time en lugar de mfa; `RegistryEntryIn.actor` con acr y auth_time); `business-logic-model.md` PBT-U0-09; `contracts/nfr-design/nfr-design-patterns.md` (`RouteContract.mfa_max_age`); `plans/contracts-code-generation-plan.md` Paso 11 (pruebas de bordes de 900 s y audiencia múltiple).
**Context**: CONSTRUCTION - U2 identity-edge - Functional Design completada; solicitud de aprobación.

---
## U2 identity-edge — Functional Design: aprobación
**Timestamp**: 2026-10-03T11:05:10Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U2 aprobado. Inicio de U2 identity-edge — NFR Requirements (plan y preguntas).
**Context**: CONSTRUCTION - U2 - Functional Design completado → NFR Requirements.

---
## U2 identity-edge — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T11:05:10Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/identity-edge-nfr-requirements-plan.md` con 9 preguntas (despliegue de Keycloak, HA y sesiones, rendimiento de identidad, disponibilidad y sobrecosto del gateway, rate limiting local o global, TLS en el borde, IP de origen real, política de contraseñas, pruebas).
**Context**: CONSTRUCTION - U2 identity-edge - NFR Requirements, GATE: esperando respuestas.

---
## U2 identity-edge — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T11:07:50Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q9 = A, sin ambigüedades. Generados `construction/identity-edge/nfr-requirements/nfr-requirements.md` (NFR-U2-01..42) y `tech-stack-decisions.md`. Consecuencias registradas: (1) NFR-U2-05: impacto de una caída de Keycloak (sin logins ni refresh; identidades de servicio sin renovar → fail-closed); SEV1. (2) NFR-U2-21: modo de fallo de Redis por ruta (fail-open en consola e ingesta, fail-closed en /auth/**), pendiente de confirmar en NFR Design que Envoy Gateway lo permite por política. (3) Redis y el servicio de rate limit no están en el inventario de component-dependency.md; se formalizan en el Infrastructure Design de U2. Checklist del plan [x].
**Context**: CONSTRUCTION - U2 identity-edge - NFR Requirements completada; solicitud de aprobación.

---
## U2 identity-edge — NFR Requirements: cambios solicitados (§7)
**Timestamp**: 2026-10-03T11:12:03Z
**User Input**: "Request Changes, acotado a completar la tabla §7 con las filas que faltan (listadas arriba), citando la evidencia que ya existe en el propio documento. No hace falta rediseñar nada — solo que la tabla final diga lo que el resto del documento ya demuestra."
**AI Response**: El mensaje no incluía la lista de filas; se derivó del documento (reglas con evidencia en el cuerpo y ausentes en §7). Agregadas a §7: RESILIENCY-05/07 (NFR-U2-05), RESILIENCY-14 (NFR-U2-05), SECURITY-07 (NFR-U2-27), PBT-06 (NFR-U2-42), PBT-08 (NFR-U2-40), PBT-10 (NFR-U2-42). Sin cambios de diseño.
**Context**: CONSTRUCTION - U2 identity-edge - NFR Requirements, GATE: aprobación.

---
## U2 identity-edge — NFR Requirements: cambios solicitados (§7, cinco filas)
**Timestamp**: 2026-10-03T11:15:00Z
**User Input**: "Request Changes, acotado a estas cinco filas. Ya quedó claro que el diseño subyacente está bien — es, otra vez, solo la tabla resumen la que necesita terminar de decir lo que el resto del documento ya sostiene." + lista pegada: SECURITY-08 (modelo de step-up/roles de U2 FD), SECURITY-14 (AuthDeniedBurst; KeycloakDown), SECURITY-15 (NFR-U2-21), RESILIENCY-03/04 (keycloak-config-cli como hook de sync manual, U2 FD Q10), RESILIENCY-15 (KeycloakDown = SEV1, proceso de U1).
**AI Response**: Agregadas a §7 las cinco filas con la evidencia indicada: RESILIENCY-03/04, RESILIENCY-15, SECURITY-08, SECURITY-14 y SECURITY-15. Sin cambios de diseño.
**Context**: CONSTRUCTION - U2 identity-edge - NFR Requirements, GATE: aprobación.

---
## U2 identity-edge — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T11:18:11Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U2 aprobado. Inicio de U2 identity-edge — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U2 - NFR Requirements completado → NFR Design.

---
## U2 identity-edge — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T11:18:11Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/identity-edge-nfr-design-plan.md` con 6 preguntas (implementación del modo de fallo por ruta de NFR-U2-21, origen de las claves del rate limit, rotación de llaves de firma, timeouts/reintentos/outlier detection, JWKS en el gateway, tema de login). Se declara que no está confirmado si Envoy Gateway expone el modo de fallo por política; la Q1 propone verificarlo en el plan de tareas con alternativas ordenadas.
**Context**: CONSTRUCTION - U2 identity-edge - NFR Design, GATE: esperando respuestas.

---
## U2 identity-edge — NFR Design: respuestas y generación
**Timestamp**: 2026-10-03T11:20:48Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q6 = A, sin ambigüedades. Generados `construction/identity-edge/nfr-design/nfr-design-patterns.md` (P-U2-01..09: modo de fallo del rate limit por ruta con tres alternativas ordenadas a verificar contra la versión pinneada; timeouts, reintentos solo idempotentes y outlier detection; JWKS en el gateway; Keycloak y Redis tolerantes a fallos; rotación de llaves de firma; claves de rate limit solo de datos verificados; access log con allowlist; tema de login en español con WCAG; alertas) y `logical-components.md` (inventario, diagrama Mermaid con alternativa en texto, flujos nuevos para el Infrastructure Design). Checklist del plan [x].
**Context**: CONSTRUCTION - U2 identity-edge - NFR Design completada; solicitud de aprobación.

---
## U2 identity-edge — NFR Design: observación sobre §5
**Timestamp**: 2026-10-03T11:24:58Z
**User Input**: (contenido pegado) "Dos filas faltantes en la tabla de cumplimiento (§5), aplicando el mismo criterio que ya usé antes — RESILIENCY-09 (autoscaling): P-U2-04 ya dice explícitamente \"HPA de 2 a 4\" para Keycloak — AUTONOMIA-02: Cada patrón (P-U2-01 a P-U2-09) tiene su propia línea de \"Verificación\" con un comando o escenario concreto — es exactamente lo que exige la regla, y además U0 y U1 sí incluyeron esta fila en sus propias tablas de NFR Design"
**AI Response**: Agregadas a §5 las filas RESILIENCY-09 (P-U2-04) y AUTONOMIA-02. Verificación previa: P-U2-09 no tenía línea de «Verificación»; se le agregó (promtool + test de runbooks de U1) para que la fila AUTONOMIA-02 sea cierta. Observación: las tablas de NFR Design de U0 y U1 no incluyen una fila AUTONOMIA-02 (U0 la tiene en NFR Requirements y en el plan de tareas; U1 en NFR Requirements y en el plan de tareas).
**Context**: CONSTRUCTION - U2 identity-edge - NFR Design, GATE: aprobación.

---
## U2 identity-edge — NFR Design: aprobación
**Timestamp**: 2026-10-03T11:26:41Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U2 aprobado. Inicio de U2 identity-edge — Infrastructure Design (plan y preguntas).
**Context**: CONSTRUCTION - U2 - NFR Design completado → Infrastructure Design.

---
## U2 identity-edge — Infrastructure Design: plan y preguntas
**Timestamp**: 2026-10-03T11:26:41Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/identity-edge-infrastructure-design-plan.md` con 6 preguntas (hostnames, ubicación del controlador y del data plane de Envoy Gateway, implementación de Redis/Valkey, recursos iniciales, federación LDAP, empaquetado de Keycloak con el tema). Mensajería N/A; entornos, balanceador, certificados, secretos, registro y observabilidad heredados de U1.
**Context**: CONSTRUCTION - U2 identity-edge - Infrastructure Design, GATE: esperando respuestas.

---
## U2 identity-edge — Infrastructure Design: respuestas y generación
**Timestamp**: 2026-10-03T11:29:07Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q6 = A, sin ambigüedades. Generados `construction/identity-edge/infrastructure-design/infrastructure-design.md` (INF-U2-01..08: hostname único, Envoy Gateway con controlador en envoy-gateway-system y data plane en vectra-edge sujeto a verificación de versión, servicio de rate limit con gRPC en 8083, Valkey 8 sin persistencia con ACL, keycloak-db, recursos iniciales, LDAPS, imagen propia de Keycloak) y `deployment-architecture.md`. Decisión adicional: gRPC del rate limit en 8083 porque 8081 está reservado para health y métricas (convención de U0). Checklist del plan [x].
**Cambios a artefactos aprobados**: `component-dependency.md` (§0 puertos 6379/26379/8083/18000 y 9000 de gestión de Keycloak; §1 vectra-edge, vectra-identity y envoy-gateway-system; nueva §2.8 F90–F95; K14; rangos de §7 y §9); `unit-of-work.md` (flujos de U2); `application-design.md` (F01–F95, K01–K14); `identity-edge/nfr-design/logical-components.md` (puerto 8083); `identity-edge/nfr-design/nfr-design-patterns.md` (alerta LdapUnavailable); `construction/shared-infrastructure.md` (§4: lo que provee U2).
**Context**: CONSTRUCTION - U2 identity-edge - Infrastructure Design completada; solicitud de aprobación.

---
## U2 identity-edge — Infrastructure Design: cambios solicitados (§8)
**Timestamp**: 2026-10-03T11:34:36Z
**User Input**: "Request Changes, acotado a agregar SECURITY-13 en la tabla de §8 de infrastructure-design.md, citando INF-U2-08"
**AI Response**: Agregada a §8 la fila SECURITY-13, citando INF-U2-08 (integridad de artefactos: base pinneada por digest, build en CI, Trivy, firma Cosign verificada por verify-images de U1). Sin otros cambios.
**Context**: CONSTRUCTION - U2 identity-edge - Infrastructure Design, GATE: aprobación.

---
## U2 identity-edge — Infrastructure Design: aprobación
**Timestamp**: 2026-10-03T11:36:53Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U2 aprobado. Inicio de Code Generation Part 1 (plan de tareas) de U2.
**Context**: CONSTRUCTION - U2 - Infrastructure Design completado → Code Generation Part 1.

---
## U2 identity-edge — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T11:36:53Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/identity-edge-code-generation-plan.md` (18 pasos en 7 bloques: estructura, Keycloak, gateway, plataforma, pruebas e2e y de carga, verificación en kind con aprobación humana, cierre). La verificación de la versión pinneada de Envoy Gateway (namespace del data plane y modo de fallo por ruta) se hace con traducción offline (`egctl x translate`) y queda en un ADR. AI Prompt: "Plan de tareas de U2 listo para revisión. ¿Request Changes o Continue to Next Stage (U3 decision-registry)?". Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U2 identity-edge - Code Generation Part 1, GATE: aprobación del plan.

---
## U2 identity-edge — Code Generation Part 1: autorrevisión de trazabilidad
**Timestamp**: 2026-10-03T11:36:53Z
**User Input**: N/A
**AI Response**: Antes de solicitar aprobación se cruzó la tabla §3 con las líneas «Diseño» de cada paso. Correcciones: citas agregadas (NFR-U2-40 en Paso 3; NFR-U2-25 en Paso 4; NFR-U2-20, 23, 40, 41 en Paso 7; NFR-U2-05 en Paso 11); filas ajustadas (BR-U2-02 aclarado como de U4; NFR-U2-01..05 +11; NFR-U2-20..27 +4; INF-U2-01..08 sin el Paso 7, que no cita INF).
**Context**: CONSTRUCTION - U2 identity-edge - Code Generation Part 1, GATE: aprobación del plan.

---
## U2 identity-edge — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T11:40:12Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U2 aprobado; artefacto final de U2 (Part 2 y Build and Test fuera de alcance). U2 completa. Inicio de U3 decision-registry — Functional Design.
**Context**: CONSTRUCTION - U2 completada → U3 Functional Design.

---
## U3 decision-registry — Functional Design: plan y preguntas
**Timestamp**: 2026-10-03T11:40:12Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/decision-registry-functional-design-plan.md` con 10 preguntas (protección contra la reescritura de la cadena, bytes que se hashean, contenido del hash y génesis, serialización de escrituras, idempotencia, proyecciones por consumidor, expediente e integridad, modos del verificador, tiempos de la entrada, tamaño máximo). Ley 1581 diferida al NFR Requirements de U3, como se decidió en U0.
**Context**: CONSTRUCTION - U3 decision-registry - Functional Design, GATE: esperando respuestas.

---
## U3 decision-registry — Functional Design: respuestas y generación
**Timestamp**: 2026-10-03T11:44:51Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q10 = A, sin ambigüedades. Generados `construction/decision-registry/functional-design/domain-entities.md` (tabla, roles de BD, checkpoints, proyecciones, expediente, informe), `business-rules.md` (BR-U3-01..16, alertas) y `business-logic-model.md` (módulos, flujos, PBT-U3-01..08 con la stateful de US-401, pruebas de ejemplo). Interpretación de Q7: el BFF compone el expediente (registry + identificadores de case-service) para que el registro nunca toque identificadores directos ni tenga flujo hacia ellos. Checklist del plan [x].
**Cambios a artefactos aprobados**: U0 `domain-entities.md` (§5.1 idempotency_key; §5.2 genesis y checkpoint; §5.3 seq contiguo, contract_version, canonical, composición por el BFF); U0 `business-rules.md` BR-U0-08 (idempotency_key fija por intento); `inception/application-design/component-methods.md` (BFF get_dossier compone registry + case).
**Context**: CONSTRUCTION - U3 decision-registry - Functional Design completada; solicitud de aprobación.

---
## U3 decision-registry — Functional Design: autorrevisión de la tabla de cumplimiento
**Timestamp**: 2026-10-03T11:44:51Z
**User Input**: N/A
**AI Response**: Antes de solicitar aprobación se cruzó la tabla §4 de business-logic-model.md con el cuerpo de los tres artefactos. Agregadas las filas RESILIENCY-05/07/15 (alertas con severidad de business-rules §6) y PBT-07 (columna de generadores de §3). Corregida la referencia de SECURITY-06 a «domain-entities §1.2».
**Context**: CONSTRUCTION - U3 decision-registry - Functional Design, GATE: aprobación.

---
## U3 decision-registry — Functional Design: observación sobre §4
**Timestamp**: 2026-10-03T11:51:32Z
**User Input**: (contenido pegado) "Dos reglas con evidencia real en el documento, sin fila en la tabla de cumplimiento (§4 de business-logic-model.md) — SECURITY-08 (control de acceso): BR-U3-03 (solo ciertos scopes pueden escribir ciertos entry_type) y BR-U3-15 (proyecciones por rol, con 403 y sin datos parciales si se pide algo fuera de lo permitido) — SECURITY-05 (validación de entradas): BR-U3-05 (tolerancia de occurred_at) y BR-U3-07 (límite de 64 KiB) — son reglas de validación propias de U3, no solo lo heredado de U0"
**AI Response**: Verificado que BR-U3-03, 05, 07 y 15 existen con ese contenido y que §4 no tenía esas filas. Agregadas SECURITY-05 y SECURITY-08 con la evidencia indicada. Sin cambios de diseño.
**Context**: CONSTRUCTION - U3 decision-registry - Functional Design, GATE: aprobación.

---
## U3 decision-registry — Functional Design: aprobación
**Timestamp**: 2026-10-03T11:52:56Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U3 aprobado. Inicio de U3 decision-registry — NFR Requirements (plan y preguntas).
**Context**: CONSTRUCTION - U3 - Functional Design completado → NFR Requirements.

---
## U3 decision-registry — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T11:52:56Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/decision-registry-nfr-requirements-plan.md` con 6 preguntas (retención/supresión y Ley 1581 con archivo de largo plazo, objetivos de rendimiento, crecimiento a 10 años y particionado, costo de la verificación completa nocturna, custodia de la llave de checkpoints, driver y pruebas de integración). Se señalan dos tensiones: la retención de backups de U1 (12 meses) frente a una retención regulatoria de años, y el costo de BR-U3-11 (verificación completa nocturna) a 10 años.
**Context**: CONSTRUCTION - U3 decision-registry - NFR Requirements, GATE: esperando respuestas.

---
## U3 decision-registry — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T11:55:51Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q6 = A, sin ambigüedades. Generados `construction/decision-registry/nfr-requirements/nfr-requirements.md` (NFR-U3-01..52: retención de 10 años [VERIFICAR], sin supresión en el registro [VERIFICAR], pérdida de re-identificación vía U8, archivo WORM mensual de 10 años; disponibilidad heredada de U1; rendimiento; particionado; verificación en dos niveles; firma por la bóveda; pruebas) y `tech-stack-decisions.md`. Tabla de cumplimiento revisada contra el cuerpo antes de presentarla. Checklist del plan [x].
**Cambios a artefactos aprobados**: U3 FD (BR-U3-08 firma por la bóveda; BR-U3-11 modos incremental/nightly/full mensual/range; domain-entities §2.1, §5, §6; business-logic-model `cli`); U0 domain-entities §5.4 y BR-U0-95 (remiten a la decisión de U3). Pendientes: U8 (eliminación de identificadores al vencer la retención de case-db, NFR-U3-03) y U3 Infrastructure Design (buckets WORM y flujo hacia la bóveda).
**Context**: CONSTRUCTION - U3 decision-registry - NFR Requirements completada; solicitud de aprobación.

---
## U3 decision-registry — NFR Requirements: cambios solicitados (capacidad y §7)
**Timestamp**: 2026-10-03T12:03:53Z
**User Input**: "Request Changes, con dos partes de distinto peso: (1) la reconciliación de NFR-U3-20/NFR-U3-30 — esto sí toca la sustancia del diseño de capacidad, no solo una tabla; y (2) las dos filas de cumplimiento, del mismo tipo que las rondas anteriores" + contenido pegado: SECURITY-14 (NFR-U3-04, 12, 31, 32: cuatro alertas nombradas con severidad) y SECURITY-15 (NFR-U3-12: si la bóveda no responde, los appends siguen).
**AI Response**: (1) Nueva §3.1 que separa volumen esperado (~2 000 solicitudes/día × ~5 entradas = ~10 000 entradas/día; base del almacenamiento) de capacidad de diseño (pico de U1 10 solicitudes/s × ≤ 2 entradas síncronas = 20 entradas/s, con margen 2,5× = 50 entradas/s; base del rendimiento), con la derivación de entradas por solicitud. NFR-U3-20 y NFR-U3-30 reescritos para citar su base. Se aclara que los "2 solicitudes/s sostenidas" de NFR-U1-10 son capacidad, no volumen esperado (sostenerlos serían ~1,3 TB/año). Nuevo NFR-U3-34 con la alerta RegistryGrowthAboveForecast (3× el volumen esperado durante 7 días). Se corrige la justificación de la Q2 del plan ("10 veces el pico de U1"), que era incorrecta: 50 entradas/s son 2,5× el pico síncrono. (2) Agregadas a §7 SECURITY-14 (incluye la alerta nueva) y SECURITY-15; ajustadas las filas RESILIENCY-05/07/15 y 08/09.
**Context**: CONSTRUCTION - U3 decision-registry - NFR Requirements, GATE: aprobación.

---
## U3 decision-registry — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T12:06:26Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U3 aprobado. Inicio de U3 decision-registry — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U3 - NFR Requirements completado → NFR Design.

---
## U3 decision-registry — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T12:06:26Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/decision-registry-nfr-design-plan.md` con 7 preguntas (readiness con réplica síncrona, tiempos límite del append, emisión de checkpoints con varias réplicas, dónde corre la verificación, formato del archivo de 10 años, creación de particiones frente a AUTONOMIA-01, pools separados para escrituras y lecturas).
**Context**: CONSTRUCTION - U3 decision-registry - NFR Design, GATE: esperando respuestas.

---
## U3 decision-registry — NFR Design: respuestas y generación
**Timestamp**: 2026-10-03T12:08:52Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q7 = A, sin ambigüedades. Generados `construction/decision-registry/nfr-design/nfr-design-patterns.md` (P-U3-01..09: readiness con standby síncrono vía registry_health, tiempos límite del append sin reintento interno, checkpoint por CronJob con idempotencia por hora e identidad de firma separada, pools separados, verificación en la réplica, particiones por migración con DEFAULT de seguridad, archivo NDJSON+zstd con manifiesto firmado y verificación tras subirlo, identidades y permisos, alertas) y `logical-components.md` (inventario, diagrama Mermaid con alternativa en texto, pendientes para Infrastructure Design). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambio a artefacto aprobado**: U3 FD `domain-entities.md` §1.2 (rol registry_health).
**Context**: CONSTRUCTION - U3 decision-registry - NFR Design completada; solicitud de aprobación.

---
## U3 decision-registry — NFR Design: observación sobre §5 (AUTONOMIA-05)
**Timestamp**: 2026-10-03T12:13:35Z
**User Input**: "Una fila faltante en la tabla de cumplimiento (§5) — P-U3-08 es, literalmente, un inventario de egress cerrado por identidad — y es un ejemplo particularmente claro del principio: la fila del servicio de la API dice explícitamente \"Ninguno | Ninguno\" para bóveda y bucket WORM, es decir, el componente que atiende la mayoría del tráfico no tiene ningún egress propio. Eso es AUTONOMIA-05 por definición, y no aparece citada en ningún lado de la tabla."
**AI Response**: Agregada la fila AUTONOMIA-05 citando P-U3-08 (API sin bóveda ni buckets) y P-U3-03/07 (solo el digest va a la bóveda). Matiz registrado: P-U3-08 es una tabla de permisos (la salida de red la impone flows.yaml), y el archivo de 10 años contiene datos seudonimizados; si su bucket queda fuera del clúster debe seguir el precedente de F70 (infraestructura del banco, cifrado), a decidir en el Infrastructure Design de U3.
**Context**: CONSTRUCTION - U3 decision-registry - NFR Design, GATE: aprobación.

---
## U3 decision-registry — NFR Design: aprobación
**Timestamp**: 2026-10-03T12:16:10Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U3 aprobado. Inicio de U3 decision-registry — Infrastructure Design (plan y preguntas).
**Context**: CONSTRUCTION - U3 - NFR Design completado → Infrastructure Design.

---
## U3 decision-registry — Infrastructure Design: plan y preguntas
**Timestamp**: 2026-10-03T12:16:10Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/decision-registry-infrastructure-design-plan.md` con 5 preguntas (ubicación de los buckets WORM, modo del object lock, backend de firma en producción, recursos y límites de tiempo de los Jobs, corrección de P-U3-04). Hallazgo al preparar el plan: P-U3-04 (aprobado) define un pool «read» que apunta a dos servidores, lo que en realidad son dos pools; sumando la readiness de P-U3-01 quedan 6 conexiones por réplica, por encima del máximo de 5 de P-U1-08. Mensajería N/A.
**Context**: CONSTRUCTION - U3 decision-registry - Infrastructure Design, GATE: esperando respuestas.

---
## U3 decision-registry — Infrastructure Design: respuestas y generación
**Timestamp**: 2026-10-03T12:19:30Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q5 = A, sin ambigüedades. Generados `construction/decision-registry/infrastructure-design/infrastructure-design.md` (INF-U3-01..06: buckets WORM COMPLIANCE de 10 años en el S3 del banco fuera del sitio [VERIFICAR soporte de COMPLIANCE]; firma con API compatible con Vault Transit, llave no exportable [VERIFICAR]; recursos y límites de tiempo de los Jobs; conexiones dentro del máximo de 5 por réplica; registry-db; flujos) y `deployment-architecture.md`. Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: `decision-registry/nfr-design/nfr-design-patterns.md` P-U3-04 (pools append 2, dossier 1, projections 1, health 1 = 5; la versión anterior sumaba 6 con un pool sobre dos servidores) y P-U3-08; `logical-components.md` (pools y nota de pendientes resueltos); `component-dependency.md` (puerto 8200; F96, F97, F98; egress F77, F78, F79, F99; F75 incluye la lectura de checkpoints para verificar tras un restore; rangos de §7 y §9); `unit-of-work.md` (flujos de U3); `application-design.md` (F01–F99).
**Context**: CONSTRUCTION - U3 decision-registry - Infrastructure Design completada; solicitud de aprobación.

---
## U3 decision-registry — Infrastructure Design: aprobación
**Timestamp**: 2026-10-03T12:24:50Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U3 aprobado. Inicio de Code Generation Part 1 (plan de tareas) de U3.
**Context**: CONSTRUCTION - U3 - Infrastructure Design completado → Code Generation Part 1.

---
## U3 decision-registry — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T12:24:50Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/decision-registry-code-generation-plan.md` (20 pasos en 9 bloques: estructura, datos, lógica pura, servicio, CLI y Jobs, despliegue y operación, calidad, verificación en kind con aprobación humana, cierre). Integración con Testcontainers en CI (sin clúster). La trazabilidad §3 se verificó con un script contra las líneas «Diseño» de cada paso; se corrigieron tres desfases (BR-U3-10 también en el Paso 3; cita de NFR-U3-20..23 y P-U3-04 agregada al Paso 17; P-U3 sin el Paso 4 y con los Pasos 8 y 17). AI Prompt: "Plan de tareas de U3 listo para revisión. ¿Request Changes o Continue to Next Stage (U4 governance)?". Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U3 decision-registry - Code Generation Part 1, GATE: aprobación del plan.

---
## U3 decision-registry — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T12:28:30Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U3 aprobado; artefacto final de U3 (Part 2 y Build and Test fuera de alcance). U3 completa. Inicio de U4 governance — Functional Design.
**Context**: CONSTRUCTION - U3 completada → U4 Functional Design.

---
## U4 governance — Functional Design: plan y preguntas
**Timestamp**: 2026-10-03T12:28:30Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/governance-functional-design-plan.md` con 9 preguntas (máquina de estados completa del modelo, mark_active y promoción incompleta, cuatro ojos en la política, activación y vigencia de parámetros normativos, latencia del congelamiento, qué bloquea la validación, formatos de artefacto y deserialización segura, fuentes de datos, monitoreo de sesgo detenido de S4.6).
**Context**: CONSTRUCTION - U4 governance - Functional Design, GATE: esperando respuestas.

---
## U4 governance — Functional Design: respuestas y generación
**Timestamp**: 2026-10-03T12:32:15Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q9 = A, sin ambigüedades. Generados `construction/governance/functional-design/domain-entities.md`, `business-rules.md` (BR-U4-01..17, alertas) y `business-logic-model.md` (módulos, flujos, PBT-U4-01..07 con dos stateful, pruebas de ejemplo por historia). Decisión de diseño propia, no preguntada, registrada en BR-U4-17: ninguna transición tiene efecto sin evidencia en el registro (dos fases con idempotency_key = transition_id y reconciliador), con la excepción de freeze, que se aplica de inmediato porque reduce el riesgo. Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados de U0**: domain-entities (ServingState, model_event, ServingConfig con etag/normative_current/bias_monitoring_age_s, PolicyDraft con normative como lista, PolicyVersion con estados propuesta/activa/rechazada/historica y aprobador ≠ proponente); business-rules BR-U0-33 (vigencias sin solaparse). Pendientes para U5, U6, U7 y U9 listados en business-rules §10.
**Context**: CONSTRUCTION - U4 governance - Functional Design completada; solicitud de aprobación.

---
## U4 governance — Functional Design: autorrevisión de la tabla de cumplimiento
**Timestamp**: 2026-10-03T12:32:15Z
**User Input**: N/A
**AI Response**: La fila AUTONOMIA-03 afirmaba algo que el cuerpo no sostiene explícitamente; se cambió a «N/A en U4» con la evidencia del inventario (F17 y core:read-credit solo de case-service).
**Context**: CONSTRUCTION - U4 governance - Functional Design, GATE: aprobación.

---
## U4 governance — Functional Design: observación sobre §4 (SECURITY-11)
**Timestamp**: 2026-10-03T12:37:44Z
**User Input**: "Un hallazgo en la tabla de cumplimiento (§4 de business-logic-model.md) — BR-U4-03 describe un script de CI que busca activamente en el repositorio cualquier otra ruta de escritura hacia congelado → activo fuera del endpoint aprobado, y falla si la encuentra. Eso es exactamente un caso de abuso probado — la misma categoría de evidencia que SECURITY-11 pide, y que Application Design ya había definido como \"casos de abuso: flujos prohibidos... + RT\". No aparece citada en la tabla."
**AI Response**: Verificado contra el texto de SECURITY-11 (separación de la lógica crítica, defensa en profundidad, rate limiting, casos de abuso). Agregada la fila SECURITY-11 citando BR-U4-03 (caso de abuso probado y defensa en profundidad), BR-U4-04 y BR-U4-10 (otros casos de abuso) y model_fsm (lógica crítica aislada); el rate limiting queda en U2.
**Context**: CONSTRUCTION - U4 governance - Functional Design, GATE: aprobación.

---
## U4 governance — Functional Design: aprobación
**Timestamp**: 2026-10-03T12:39:24Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U4 aprobado. Inicio de U4 governance — NFR Requirements (plan y preguntas).
**Context**: CONSTRUCTION - U4 - Functional Design completado → NFR Requirements.

---
## U4 governance — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T12:39:24Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/governance-nfr-requirements-plan.md` con 6 preguntas (governance en la ruta de cada recomendación y política de configuración vencida, rendimiento, identidad de promotion-tool y protección del repositorio GitOps, retención de los datos de governance, librerías de integración, aislamiento del model-validation-job). Hallazgo: al leer serving-config en cada evaluación, governance queda de hecho dentro del SLO de la ruta de recomendación.
**Context**: CONSTRUCTION - U4 governance - NFR Requirements, GATE: esperando respuestas.

---
## U4 governance — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T12:41:45Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q6 = A, sin ambigüedades. Generados `construction/governance/nfr-requirements/nfr-requirements.md` (NFR-U4-01..41) y `tech-stack-decisions.md`. Consecuencia de Q1 registrada: servir serving-config desde memoria por réplica exige convergencia entre réplicas (≤ 1 s, NFR-U4-05), que se suma a la caché de 5 s de scoring; el límite de propagación del congelamiento pasa a ≤ 6 s (NFR-U4-06). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: U4 FD BR-U4-14 y domain-entities §6 (≤ 6 s en lugar de ≤ 5 s). Pendientes: U7 (prueba de NFR-U4-02), Infrastructure Design de U4 (retención de 10 años del bucket model-store, NFR-U4-31).
**Context**: CONSTRUCTION - U4 governance - NFR Requirements completada; solicitud de aprobación.

---
## U4 governance — NFR Requirements: cambios solicitados (§6)
**Timestamp**: 2026-10-03T12:45:29Z
**User Input**: (contenido pegado) "El hallazgo más importante: la convergencia entre réplicas, que el FD original no contempló [...] Dos filas faltantes en la tabla de cumplimiento (§6 de nfr-requirements.md) — AUTONOMIA-05: NFR-U4-23 dice explícitamente que model-validation-job no tiene egress, solo F30, F31 (lectura) y F32 — es un inventario de egress cerrado declarado sin rodeos — SECURITY-11: NFR-U4-22 (protección de rama: solo por PR, aprobador distinto del autor, sin push directo ni force-push, verificado con un script) extiende la prevención de casos de abuso que ya vimos en el FD (BR-U4-03) hasta la infraestructura de Git misma — Recomendación: Request Changes, acotado a esas dos filas. El resto —incluida la corrección de la convergencia entre réplicas, que es sustancialmente más importante que cualquier hallazgo de tabla— lo apruebo sin reservas."
**AI Response**: Verificado el contenido de NFR-U4-22 y NFR-U4-23 y que §6 no tenía esas filas. Agregadas SECURITY-11 y AUTONOMIA-05 con la evidencia indicada. Sin otros cambios.
**Context**: CONSTRUCTION - U4 governance - NFR Requirements, GATE: aprobación.

---
## U4 governance — Verificación de los cambios retroactivos a U0
**Timestamp**: 2026-10-03T12:48:25Z
**User Input**: "la confirmación sobre los cambios retroactivos a U0 (ServingConfig, ServingState, PolicyDraft/PolicyVersion, BR-U0-33) — la doy por abierta hasta que la resuelvas, antes de considerar completo el Functional Design de U4."
**AI Response**: Verificados en los archivos de U0: ServingState (no_disponible también con normative_current nulo), ServingConfig (etag, normative_current, bias_monitoring_age_s), PolicyDraft (normative como lista), PolicyVersion (propuesta/activa/rechazada/historica; aprobador ≠ proponente), BR-U0-33 (vigencias sin solaparse) y model_event (validacion_fallida, inactivado): todos aplicados. Hallazgos y correcciones: (1) policy_event seguía con aprobada y activada por separado y sin historica, contradiciendo «aprobar = activar»; corregido a propuesta/activada/rechazada/historica. (2) data_source_event no tenía evento para la transición propuesta → en_evaluacion, que BR-U4-17 exige; agregado evaluacion_iniciada. (3) BR-U3-16 solo exceptuaba freeze del actor humano, pero informe_validacion/validacion_fallida los envía el Job (actor de servicio) o el vencimiento del plazo (actor de sistema); precisado. (4) El plan de tareas de U0 no probaba BR-U0-33 ni el fail-closed por normative_current nulo; agregado al Paso 7. Comprobado que cada transición de U4 (modelo, política, fuente) tiene su tipo de evento. Registrado en business-rules §10 de U4.
**Cambios a artefactos aprobados**: U0 domain-entities §5.2 (policy_event, data_source_event); U3 business-rules BR-U3-16; U0 plan de tareas Paso 7; U4 business-rules §10.
**Context**: CONSTRUCTION - U4 governance - cierre de la verificación del Functional Design; NFR Requirements de U4 pendiente de aprobación.

---
## U4 governance — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T12:50:53Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U4 aprobado (con la verificación de los cambios retroactivos a U0 cerrada). Inicio de U4 governance — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U4 - NFR Requirements completado → NFR Design.

---
## U4 governance — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T12:50:53Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/governance-nfr-design-plan.md` con 5 preguntas (convergencia entre réplicas, ubicación del reconciliador, seguimiento de los Jobs de validación, zona horaria de las vigencias normativas, trigger en la base contra la reactivación indebida).
**Context**: CONSTRUCTION - U4 governance - NFR Design, GATE: esperando respuestas.

---
## U4 governance — NFR Design: respuestas y generación
**Timestamp**: 2026-10-03T12:54:11Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q5 = A, sin ambigüedades. Generados `construction/governance/nfr-design/nfr-design-patterns.md` (P-U4-01..08: convergencia con LISTEN/NOTIFY y sondeo de 1 s; reconciliador y barridos sin líder con SKIP LOCKED; Jobs sin watch; conexiones por réplica = 5 incluyendo listen y background; vigencias en America/Bogota con recálculo a medianoche; triggers guard_unfreeze/guard_freeze como cuarta barrera; copia en memoria sin datos sensibles; alertas) y `logical-components.md` (inventario, diagrama Mermaid con alternativa en texto, pendientes). Se dimensionaron las conexiones desde el inicio para respetar P-U1-08 (lección de U3). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Context**: CONSTRUCTION - U4 governance - NFR Design completada; solicitud de aprobación.

---
## U4 governance — NFR Design: observación sobre §5 (RESILIENCY-10)
**Timestamp**: 2026-10-03T12:57:11Z
**User Input**: "Un hallazgo en la tabla de cumplimiento (§5 de nfr-design-patterns.md) — RESILIENCY-10 cita P-U4-01, 02 y 03, pero no P-U4-04 — que es, literalmente, el mismo patrón de bulkhead (pools separados por función: tx, read, background, listen) que ya vimos en U3 con P-U3-04, y que en la tabla de U3 sí se citó bajo RESILIENCY-10 como \"bulkhead\". Aquí el patrón gemelo se quedó sin esa misma cita."
**AI Response**: Verificado que P-U4-04 es un bulkhead y que U3 lo citaba bajo RESILIENCY-10. Agregado P-U4-04 a la fila RESILIENCY-10 de §5. Sin otros cambios.
**Context**: CONSTRUCTION - U4 governance - NFR Design, GATE: aprobación.

---
## U4 governance — NFR Design: aprobación
**Timestamp**: 2026-10-03T12:58:28Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U4 aprobado. Inicio de U4 governance — Infrastructure Design (plan y preguntas).
**Context**: CONSTRUCTION - U4 - NFR Design completado → Infrastructure Design.

---
## U4 governance — Infrastructure Design: plan y preguntas
**Timestamp**: 2026-10-03T12:58:28Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/governance-infrastructure-design-plan.md` con 2 preguntas (recursos y escalado del servicio; retención de 10 años de los artefactos de modelo, que hoy viven en MinIO in-cluster y se perderían con el sitio). Comprobado de antemano: governance-db cabe en max_connections 50 con 6 réplicas × 5; los flujos existentes cubren el servicio; mensajería N/A.
**Context**: CONSTRUCTION - U4 governance - Infrastructure Design, GATE: esperando respuestas.

---
## U4 governance — Infrastructure Design: respuestas y generación
**Timestamp**: 2026-10-03T13:01:30Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q2 = A, sin ambigüedades. Generados `construction/governance/infrastructure-design/infrastructure-design.md` (INF-U4-01..04: recursos y HPA; CronJob model-archive con copia WORM COMPLIANCE de 10 años fuera del sitio y verificación del SHA-256; rol governance_archiver con permiso por columna; flujos F100–F102) y `deployment-architecture.md`. Los IDs F70–F79 y F96–F99 estaban tomados; los nuevos son F100–F102. Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x]. (Un reemplazo de relleno en el script de actualización hizo fallar una aserción a mitad de camino; se detectó y se reaplicó la parte pendiente.)
**Cambios a artefactos aprobados**: `component-dependency.md` (F101, F102, egress F100, rol governance_archiver, rangos de §7 y §9); `unit-of-work.md` (flujos de U4); `application-design.md` (F01–F102); U4 FD domain-entities (archived_uri, archived_at); U4 NFR Design (alerta ModelArchivePending; pendientes resueltos).
**Context**: CONSTRUCTION - U4 governance - Infrastructure Design completada; solicitud de aprobación.

---
## U4 governance — Infrastructure Design: nombre del rol de archivo
**Timestamp**: 2026-10-03T13:01:30Z
**User Input**: N/A
**AI Response**: Renombrado el rol governance_archiver a gov_archiver en infrastructure-design.md y component-dependency.md, para seguir la convención existente del inventario (gov_app, gov_migrator).
**Context**: CONSTRUCTION - U4 governance - Infrastructure Design, GATE: aprobación.

---
## U4 governance — Infrastructure Design: cambios solicitados (cifrado)
**Timestamp**: 2026-10-03T13:07:34Z
**User Input**: "Request Changes, agrega el cifrado y la fila SECURITY-01"
**AI Response**: INF-U4-02: el bucket vectra-model-archive declara explícitamente cifrado del lado del servidor por defecto y acceso solo por TLS (política del bucket), con la aclaración de que se configura por bucket y no se hereda del destino. Agregada la fila SECURITY-01 en §5. Sin otros cambios.
**Context**: CONSTRUCTION - U4 governance - Infrastructure Design, GATE: aprobación.

---
## U4 governance — Infrastructure Design: aprobación
**Timestamp**: 2026-10-03T13:08:38Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U4 aprobado. Inicio de Code Generation Part 1 (plan de tareas) de U4.
**Context**: CONSTRUCTION - U4 - Infrastructure Design completado → Code Generation Part 1.

---
## U4 governance — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T13:08:38Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/governance-code-generation-plan.md` (22 pasos en 9 bloques: estructura, datos, lógica pura, servicio, herramientas y Jobs, despliegue, calidad, verificación en kind con aprobación humana, cierre). Dependencias de U5, U6, U7 y U9 cubiertas con dobles de prueba y marcadas como pendientes en el Paso 20. La trazabilidad §3 se verificó con el script; un desfase (P-U4 sin el Paso 17) corregido; segunda corrida: 0 desfases. AI Prompt: "Plan de tareas de U4 listo para revisión. ¿Request Changes o Continue to Next Stage (U5 reference-model)?". Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U4 governance - Code Generation Part 1, GATE: aprobación del plan.

---
## U4 governance — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T13:12:18Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U4 aprobado; artefacto final de U4 (Part 2 y Build and Test fuera de alcance). U4 completa. Inicio de U5 reference-model — Functional Design.
**Context**: CONSTRUCTION - U4 completada → U5 Functional Design.

---
## U5 reference-model — Functional Design: plan y preguntas
**Timestamp**: 2026-10-03T13:12:18Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/reference-model-functional-design-plan.md` con 8 preguntas (método de generación, función de la etiqueta, features del modelo base, formato del predictor y del explicador, origen de la confidence para RT-4, variante proxy para RT-2, composición del conjunto adversarial, tamaño/partición/versionado). Hallazgo: la confidence que exige RT-4 no puede ser la probabilidad del modelo; se propone una envolvente de dominio calculada en el entrenamiento.
**Context**: CONSTRUCTION - U5 reference-model - Functional Design, GATE: esperando respuestas.

---
## U5 reference-model — Functional Design: respuestas y generación
**Timestamp**: 2026-10-03T13:20:20Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q8 = A, sin ambigüedades. Generados `construction/reference-model/functional-design/domain-entities.md` (configuración del generador, datasets, paquete de modelo con manifiesto, features base, variante proxy, conjunto adversarial), `business-rules.md` (BR-U5-01..18) y `business-logic-model.md` (módulos, flujo de entrega, PBT-U5-01..07, pruebas de ejemplo). Consecuencias: (1) el paquete tiene más archivos que predictor y explicador → U4 verifica el manifiesto y cada archivo; (2) la variante proxy necesita búsquedas por versión → derive de U0 recibe feature_spec. Corrección propia antes de presentar: los primeros borradores decían que municipality_code entraba al FeatureVector; BR-U0-34 lo impide y la búsqueda ocurre dentro de derive, así que solo llega zona_vivienda (≥ 5 municipios por zona). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: U0 business-logic-model §2.3 (derive con feature_spec) y plan de tareas Paso 5 (prueba de derive con especificación); U4 FD domain-entities (manifest_uri/manifest_sha256) y BR-U4-06 (verificación de cada archivo del manifiesto y mismo model_version_id); U4 plan de tareas Paso 6. Pendientes para U6 (confidence con la envolvente) y U7/U8 (FeatureVector con el feature_spec activo).
**Context**: CONSTRUCTION - U5 reference-model - Functional Design completada; solicitud de aprobación.

---
## U5 reference-model — Functional Design: observación sobre §4 (SECURITY-11)
**Timestamp**: 2026-10-03T13:27:52Z
**User Input**: "Un hallazgo en la tabla de cumplimiento (§4 de business-logic-model.md) — El módulo adversarial completo (BR-U5-16..18) existe específicamente para construir casos de abuso deliberados — inyección en free_text (RT-1), artefactos desincronizados (RT-3), entradas fuera de dominio (RT-4). Eso es exactamente lo que SECURITY-11 pide como evidencia — de hecho, Application Design definió esa regla citando textualmente \"RT-1..5\" como su categoría de evidencia. No aparece citada en la tabla de U5."
**AI Response**: Verificado en application-design.md que SECURITY-11 cita los casos de abuso X01–X10 + RT-1..5. Agregada la fila SECURITY-11 citando BR-U5-16..18, con la aclaración de que U5 construye los casos y U12 los ejecuta. Sin cambios de diseño.
**Context**: CONSTRUCTION - U5 reference-model - Functional Design, GATE: aprobación.

---
## U5 reference-model — Functional Design: aprobación
**Timestamp**: 2026-10-03T13:29:02Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U5 aprobado. Inicio de U5 reference-model — NFR Requirements (plan y preguntas). NFR Design e Infrastructure Design de U5 = SKIP (unit-of-work §2).
**Context**: CONSTRUCTION - U5 - Functional Design completado → NFR Requirements.

---
## U5 reference-model — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T13:29:02Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/reference-model-nfr-requirements-plan.md` con 4 preguntas (ejecución en CI y entrega al model-store sin credenciales del clúster en CI, reproducibilidad completa del modelo, tiempo de la entrega, librerías).
**Context**: CONSTRUCTION - U5 reference-model - NFR Requirements, GATE: esperando respuestas.

---
## U5 reference-model — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T13:31:30Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q4 = A, sin ambigüedades. Generados `construction/reference-model/nfr-requirements/nfr-requirements.md` (NFR-U5-01..34) y `tech-stack-decisions.md`. Precisión: «ninguna librería llega a producción» vale para shap, scikit-learn y xgboost; la función compartida envelope.confidence sí corre en el transformer de U6 y queda limitada a numpy y la biblioteca estándar (NFR-U5-32). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Context**: CONSTRUCTION - U5 reference-model - NFR Requirements completada; solicitud de aprobación.

---
## U5 reference-model — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T13:33:47Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U5 aprobado. NFR Design e Infrastructure Design = SKIP. Inicio de Code Generation Part 1 (plan de tareas) de U5.
**Context**: CONSTRUCTION - U5 - NFR Requirements completado → Code Generation Part 1.

---
## U5 reference-model — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T13:33:47Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/reference-model-code-generation-plan.md` (12 pasos en 6 bloques: estructura, datos, modelo y confianza, variante proxy y conjunto adversarial, entrega en CI, calidad y cierre). Trazabilidad verificada con el script: 0 desfases en la tabla. El script se amplió para detectar reglas BR sin citar en ningún paso; encontró BR-U5-06 (disparidad base < 5 pp) sin citar y se agregó al Paso 6. Al pasar el script ampliado por los planes aprobados: U0 sin reglas sin citar (sus citas están en el texto de cada paso, no en líneas «Diseño»); U3 y U4 sin desfases; U2 con 8 desfases de formato en su tabla §3 (incluye los Pasos 3, 4, 14 y 16 en filas cuyos IDs esos pasos no citan en sus líneas «Diseño»/«Historia»), no corregidos: se informan al usuario. AI Prompt: "Plan de tareas de U5 listo para revisión. ¿Request Changes o Continue to Next Stage (U6 model-serving)?". Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U5 reference-model - Code Generation Part 1, GATE: aprobación del plan.

---
## U2 identity-edge — Alineación de la tabla de trazabilidad del plan de tareas
**Timestamp**: 2026-10-03T13:38:47Z
**User Input**: "Request Changes, alinea la tabla §3 del plan de U2"
**AI Response**: Los 8 desfases venían de pasos que implementan lo que la tabla les atribuye pero no lo citaban en sus líneas «Diseño»/«Historia». Se agregaron las citas que el contenido del paso sostiene: Paso 3 (Historia US-601, por la prueba del realm exportado), Paso 4 (BR-U2-13, CSP estricta en /auth posible sin JavaScript propio), Paso 8 (Historia US-611, cabeceras y errores del gateway), Paso 9 (Historia US-611, 429 por rate limiting), Paso 14 (Diseño NFR-U2-10..12), Paso 16 (Diseño NFR-U2-02, 04, 10..12, 21, 22, 30; P-U2-01, 02, 05; PBT-U2-08; Historias US-601, US-611). En la tabla, US-611 suma el Paso 9. Script de verificación: 0 desfases; BR-U2-02 sigue sin citar a propósito (lo implementa U4, como dice la tabla).
**Cambio a artefacto aprobado**: `construction/plans/identity-edge-code-generation-plan.md` (citas de los Pasos 3, 4, 8, 9, 14, 16 y fila US-611).
**Context**: Corrección lateral; U5 Code Generation Part 1 sigue esperando aprobación.

---
## U5 reference-model — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T13:40:29Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U5 aprobado; artefacto final de U5 (Part 2 y Build and Test fuera de alcance). U5 completa. Inicio de U6 model-serving — NFR Requirements (Functional Design = SKIP).
**Context**: CONSTRUCTION - U5 completada → U6 NFR Requirements. Desde aquí las entradas de auditoría se escriben con Python para evitar la expansión de backticks del shell.

---
## U6 model-serving — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T13:40:29Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/model-serving-nfr-requirements-plan.md` con 5 preguntas (cálculo de SHAP en runtime, integridad y versión al cargar, rendimiento y escalado, staging, imágenes y firma). Inconsistencia encontrada: U5 definió explainer.json en modo interventional y validó con shap solo en CI, pero ningún artefacto define qué calcula los SHAP en runtime; la Q1 lo resuelve y puede precisar U5.
**Context**: CONSTRUCTION - U6 model-serving - NFR Requirements, GATE: esperando respuestas.

---
## U6 model-serving — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T13:43:19Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q5 = A, sin ambigüedades. Generados `construction/model-serving/nfr-requirements/nfr-requirements.md` (NFR-U6-01..41: TreeSHAP nativo de XGBoost, misma revisión, verificación del manifiesto al arrancar, model_version_id en cada respuesta, confidence con la librería de U5; rendimiento y escalado; staging aislado; imágenes propias firmadas; sin egress; sin modo degradado) y `tech-stack-decisions.md`. Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: U5 FD domain-entities §3 (explainer.json en modo tree_path_dependent; background.csv solo referencia); U5 NFR-U5-30 y tech-stack (validación de pred_contribs contra shap tree_path_dependent y suma con el margen); U5 plan de tareas Paso 5.
**Context**: CONSTRUCTION - U6 model-serving - NFR Requirements completada; solicitud de aprobación.

---
## U6 model-serving — NFR Requirements: observación sobre §6 (SECURITY-11)
**Timestamp**: 2026-10-03T13:46:00Z
**User Input**: "Un hallazgo en la tabla de cumplimiento de U6 (§6 de nfr-requirements.md) — NFR-U6-03 (verificación de integridad al arrancar) se prueba explícitamente \"con los artefactos RT-3 de U5\" — es decir, usa los casos de abuso deliberadamente construidos por U5 para confirmar que el componente rechaza correctamente un paquete desincronizado. Es la misma categoría de evidencia que ya identifiqué como SECURITY-11 tanto en U4 como en U5 (\"RT-1..5\", según la definición original de Application Design), y no está citada en la tabla de U6."
**AI Response**: Verificado que NFR-U6-03 se prueba con los artefactos RT-3 de U5. Agregada la fila SECURITY-11 citando NFR-U6-03 (caso de abuso probado y defensa en profundidad frente a la verificación de U4) y NFR-U6-22. Sin cambios de diseño.
**Context**: CONSTRUCTION - U6 model-serving - NFR Requirements, GATE: aprobación.

---
## U6 model-serving — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T13:49:53Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U6 aprobado. Inicio de U6 model-serving — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U6 - NFR Requirements completado → NFR Design.

---
## U6 model-serving — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T13:49:00Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/model-serving-nfr-design-plan.md` con 4 preguntas (composición de :predict en un solo componente, reemplazo de versión azul/verde frente a rolling update, métrica de escalado, límite de concurrencia por pod). Hallazgos: (1) transformer + servidor de XGBoost en RawDeployment son dos Deployments con un salto extra dentro del presupuesto de 30 ms y riesgo de revisiones distintas; (2) un rolling update del mismo InferenceService mezcla versiones de predictor y explicador durante el despliegue.
**Context**: CONSTRUCTION - U6 model-serving - NFR Design, GATE: esperando respuestas.

---
## U6 model-serving — NFR Design: respuestas y generación
**Timestamp**: 2026-10-03T13:52:08Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q4 = A, sin ambigüedades. Generados `construction/model-serving/nfr-design/nfr-design-patterns.md` (P-U6-01..06: predictor de un solo proceso; azul/verde por versión; verificación del paquete al arrancar; HPA por CPU; límite de concurrencia con 503 inmediato; alertas) y `logical-components.md` (inventario, diagrama Mermaid con alternativa en texto, pendientes). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: U6 NFR Requirements (NFR-U6-02, 05, 10, 11, 30 y tech-stack: un solo predictor, sin transformer ni servidor de XGBoost de KServe; un isvc por versión); U0 ServingConfig (inference_service); U4 FD BR-U4-08 (mark_active fija inference_service), BR-U4-09 (el PR agrega el isvc nuevo; retiro a los 7 días de inactivo) y domain-entities (inference_service); U4 plan de tareas Paso 12; component-dependency F19/F22 (por etiqueta, con el isvc de serving-config); U5 FD/NFR/plan (transformer → predictor de U6).
**Context**: CONSTRUCTION - U6 model-serving - NFR Design completada; solicitud de aprobación.

---
## U6 model-serving — NFR Design: observación sobre inference_service en serving-config de U4
**Timestamp**: 2026-10-03T13:58:00Z
**User Input**: (contenido pegado) "El hallazgo: inference_service falta exactamente donde más importa — P-U6-02 dice explícitamente: \"Requiere agregar inference_service a ServingConfig (U0)\". Y BR-U4-08 (de U4) confirma que serving-config se recalcula \"con inference_service apuntando al InferenceService de la versión destino\". Pero revisé la tabla de serving-config en domain-entities.md de U4 (§5) línea por línea, y el campo no está [...] Se agregó correctamente a ModelVersion (§1.1 [...]), pero no a ServingConfig, que es lo que scoring y explainability realmente leen y cachean. [...] Cambiar inference_service durante mark_active no generaría un etag nuevo [...] el diseño de azul/verde de U6 depende de un campo que, tal como está escrito ahora mismo domain-entities.md de U4, no existe en el tipo que de verdad importa."
**AI Response**: Confirmado: el contrato de U0 (ServingConfig) sí tenía inference_service, pero la tabla §5 de U4 (la fila serving_config que governance calcula, sirve y sobre la que calcula el etag) no lo tenía. Agregado inference_service a U4 domain-entities §5; la definición del etag ahora dice explícitamente que cubre todos los campos salvo bias_monitoring_age_s, incluido inference_service, de modo que mark_active dispara la convergencia (P-U4-01) y el límite de ≤ 6 s (BR-U4-14). Plan de tareas de U4, Paso 5: prueba de ejemplo «cambiar solo inference_service cambia el etag».
**Cambios a artefactos aprobados**: U4 FD domain-entities §5; U4 plan de tareas Paso 5.
**Context**: CONSTRUCTION - U6 model-serving - NFR Design, GATE: aprobación.

---
## U6 model-serving — NFR Design: aprobación
**Timestamp**: 2026-10-03T14:01:54Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U6 aprobado. Inicio de U6 model-serving — Infrastructure Design (plan y preguntas).
**Context**: CONSTRUCTION - U6 - NFR Design completado → Infrastructure Design.

---
## U6 model-serving — Infrastructure Design: plan y preguntas
**Timestamp**: 2026-10-03T14:01:54Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/model-serving-infrastructure-design-plan.md` con 2 preguntas (recursos y probes por componente; réplicas del InferenceService inactivo durante los 7 días de rollback y cuotas de vectra-serving). Sin flujos nuevos; almacenamiento y mensajería N/A.
**Context**: CONSTRUCTION - U6 model-serving - Infrastructure Design, GATE: esperando respuestas.

---
## U6 model-serving — Infrastructure Design: respuestas y generación
**Timestamp**: 2026-10-03T14:05:00Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q2 = A. Generados `construction/model-serving/infrastructure-design/infrastructure-design.md` (INF-U6-01: recursos y probes; INF-U6-02: ciclo de vida de los InferenceService y cuotas) y `deployment-architecture.md`. Corrección propia de la redacción de la opción A de la Q2: decía que el PR de promoción bajaba la versión anterior a 1 réplica «en el mismo sync», pero ese sync ocurre antes de mark_active, con la anterior todavía activa, lo que la dejaría por debajo del mínimo de 2 réplicas (NFR-U1-04). Se mantiene la decisión (inactivo a 1 réplica) con la baja en un PR post-activación, y el rollback restaura los mínimos antes de mark_active. Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: U4 FD BR-U4-09 (tres PR: promoción, post-activación y retiro; rollback con restauración previa); U4 plan de tareas Paso 12 (post_activation_pr, rollback_pr); U6 NFR Design P-U6-02.
**Context**: CONSTRUCTION - U6 model-serving - Infrastructure Design completada; solicitud de aprobación.

---
## U6 model-serving — Infrastructure Design: aprobación
**Timestamp**: 2026-10-03T14:08:03Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U6 aprobado. Inicio de Code Generation Part 1 (plan de tareas) de U6.
**Context**: CONSTRUCTION - U6 - Infrastructure Design completado → Code Generation Part 1.

---
## U6 model-serving — Code Generation Part 1: plan y solicitud de aprobación
**Timestamp**: 2026-10-03T14:08:03Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/model-serving-code-generation-plan.md` (13 pasos en 6 bloques: estructura, imágenes de serving, plantilla y políticas, operación, verificación en kind con aprobación humana, cierre). Trazabilidad verificada con el script: 0 desfases en la tabla; ningún NFR-U6 ni P-U6 sin citar. AI Prompt: "Plan de tareas de U6 listo para revisión. ¿Request Changes o Continue to Next Stage (U7 scoring-explainability)?". Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U6 model-serving - Code Generation Part 1, GATE: aprobación del plan.

---
## U6 model-serving — Code Generation Part 1: aprobación
**Timestamp**: 2026-10-03T14:09:39Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U6 aprobado; artefacto final de U6 (Part 2 y Build and Test fuera de alcance). U6 completa. Inicio de U7 scoring-explainability — Functional Design.
**Context**: CONSTRUCTION - U6 completada → U7 Functional Design.

---
## U7 scoring-explainability — Functional Design: plan y preguntas
**Timestamp**: 2026-10-03T14:09:39Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/scoring-explainability-functional-design-plan.md` con 7 preguntas (parámetro normativo no vigente, semántica del score, orden de las reglas y combinación de motivos, origen del diccionario de features, plantilla de la narrativa, validación de factualidad, resumen al solicitante). Hallazgos: (1) conflicto entre US-207 (revisión requerida sin parámetro vigente) y U4 BR-U4-11/U0 ServingState (fail-closed); (2) no existe flujo para que explainability obtenga el diccionario de features que U0 Q5 le asignó.
**Context**: CONSTRUCTION - U7 scoring-explainability - Functional Design, GATE: esperando respuestas.

---
## U7 scoring-explainability — Functional Design: respuestas y generación
**Timestamp**: 2026-10-03T15:41:41Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q7 = A, sin ambigüedades. Generados `construction/scoring-explainability/functional-design/domain-entities.md`, `business-rules.md` (BR-U7-01..16) y `business-logic-model.md` (módulos, flujos de recomendación, explicación y resumen; PBT-U7-01..08; pruebas de ejemplo por historia). Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados (Q1, US-207)**: U0 ServingState y ServingConfig.normative_current (normative nulo ya no es no_disponible), ReasonCode (parametro_normativo_no_vigente), plan de tareas de U0 Paso 7; U4 BR-U4-11, domain-entities §5, business-logic-model (prueba y fila AUTONOMIA-06), NFR Design P-U4-05 (y se quitó la fila AUTONOMIA-06 de su tabla, que dependía del fail-closed), plan de tareas de U4 §4.
**Cambios a artefactos aprobados (Q4)**: U0 catálogo de scopes (governance:read-dictionary); U2 realm (cliente explainability con el scope y la audiencia governance-service); U4 domain-entities (feature_dictionary), BR-U4-06 y nueva BR-U4-18, plan de tareas Paso 10 y su trazabilidad (verificada: 0 desfases); component-dependency (F103); component-methods C09 (get_feature_dictionary); application-design (F01–F103).
**Context**: CONSTRUCTION - U7 scoring-explainability - Functional Design completada; solicitud de aprobación.

---
## U7 scoring-explainability — Functional Design: precisión de BR-U7-13
**Timestamp**: 2026-10-03T15:48:00Z
**User Input**: N/A
**AI Response**: Autorrevisión antes de presentar: BR-U7-13 hacía que explainability comprobara la decisión final desfavorable, pero su proyección del registro (BR-U3-15) solo trae la explicación. Se precisó: el BFF comprueba la decisión desfavorable (regla de objeto de C03) y explainability comprueba que exista la explicación registrada. Mismo ajuste en el flujo §2.3 del modelo de lógica.
**Context**: CONSTRUCTION - U7 scoring-explainability - Functional Design, GATE: aprobación.

---
## U7 scoring-explainability — Functional Design: observación sobre §4 (SECURITY-13)
**Timestamp**: 2026-10-03T15:55:00Z
**User Input**: "Un hallazgo en la tabla de cumplimiento de U7 (business-logic-model.md §4) — BR-U7-08 y la tabla de errores de domain-entities.md §5 ya establecen una verificación de integridad en tiempo real genuina: que la predicción y la explicación sean exactamente de la misma versión antes de que exista cualquier Recommendation. Esto es un mecanismo de integridad de datos específico de U7, distinto de los que Application Design ya citó para SECURITY-13 (checksums de artefactos, cadena de hashes del registro) — y no aparece citado en la tabla de U7."
**AI Response**: Agregada la fila SECURITY-13 citando BR-U7-08 y domain-entities §5 (verificación de versión en runtime) y BR-U7-15 (recomendación auditable en el registro), con la nota de que la regla principal de la verificación de versión es AUTONOMIA-06 y que aquí se cita como el componente de integridad de datos de SECURITY-13. Sin cambios de diseño.
**Context**: CONSTRUCTION - U7 scoring-explainability - Functional Design, GATE: aprobación.

---
## U4 governance — Precisión de P-U4-05 tras U7 FD Q1
**Timestamp**: 2026-10-03T16:02:00Z
**User Input**: "todavía necesito ver cómo quedó P-U4-05 — su texto original decía \"AUTONOMIA-06 (nunca se evalúa con un tope vencido)\", que ya no sería exacto ahora que scoring sí evalúa con un tope vencido (solo que fuerza revision_requerida en vez de aprobar silenciosamente)."
**AI Response**: La cita de AUTONOMIA-06 ya se había quitado al aplicar U7 FD Q1 (también su fila en la tabla), pero la línea «Satisface» seguía diciendo «nunca se evalúa con un tope vencido», que se puede leer como que la solicitud no se evalúa. Reescrita: el tope vencido nunca se usa (normative_current pasa a nulo y la tasa no se compara contra ningún tope); la solicitud sí se evalúa y la política fuerza revision_requerida con parametro_normativo_no_vigente; sin aprobación silenciosa ni fail-closed. Se deja constancia del texto anterior y de por qué cambió.
**Cambio a artefacto aprobado**: U4 NFR Design P-U4-05.
**Context**: Corrección lateral; Functional Design de U7 pendiente de aprobación.

---
## U7 scoring-explainability — Functional Design: aprobación
**Timestamp**: 2026-10-03T16:01:21Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U7 aprobado. Inicio de U7 scoring-explainability — NFR Requirements (plan y preguntas).
**Context**: CONSTRUCTION - U7 - Functional Design completado → NFR Requirements.

---
## U7 scoring-explainability — NFR Requirements: plan y preguntas
**Timestamp**: 2026-10-03T16:01:21Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/scoring-explainability-nfr-requirements-plan.md` con 5 preguntas (latencia objetivo de la recomendación que NFR-PER-01 dejó a fijar aquí, timeouts y circuit breakers, disponibilidad y escalado, implementación del circuit breaker, umbral de calidad de pruebas).
**Context**: CONSTRUCTION - U7 scoring-explainability - NFR Requirements, GATE: esperando respuestas.

---
## U7 scoring-explainability — NFR Requirements: respuestas y generación
**Timestamp**: 2026-10-03T16:03:59Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1..Q5 = A, sin ambigüedades. Generados `construction/scoring-explainability/nfr-requirements/nfr-requirements.md` (NFR-U7-01..43: latencia de la recomendación p95 ≤ 400 ms / p99 ≤ 1 s, timeouts y circuit breakers, sin reintentos salvo el append, sin modo degradado, escalado, seguridad y calidad) y `tech-stack-decisions.md`. Tabla de cumplimiento revisada contra el cuerpo. Checklist del plan [x].
**Cambios a artefactos aprobados**: U0 NFR Design P-U0-07 (circuit breaker centralizado en vectra_common.deps, con propiedad stateful; antes era responsabilidad de cada servicio); U0 plan de tareas Paso 10; requirements.md NFR-PER-01 (latencia fijada en NFR-U7-01).
**Context**: CONSTRUCTION - U7 scoring-explainability - NFR Requirements completada; solicitud de aprobación.

---
## U7 scoring-explainability — NFR Requirements: aprobación
**Timestamp**: 2026-10-03T16:10:17Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U7 aprobado. Inicio de U7 scoring-explainability — NFR Design (plan y preguntas).
**Context**: CONSTRUCTION - U7 - NFR Requirements completado → NFR Design.

---
## U7 scoring-explainability — NFR Design: plan y preguntas
**Timestamp**: 2026-10-03T16:11:00Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/scoring-explainability-nfr-design-plan.md` con 4 preguntas. Hallazgos al cruzar timeouts y latencias aprobados: (1) explainability en serie (diccionario 500 ms + :explain 500 ms) no cabe en los 800 ms que espera scoring; (2) el append al registro (2,5 s + reintento, U3) supera el p99 de 1 s en que NFR-U7-04 promete el fail-closed; (3) caso límite: una entrada recommendation puede quedar escrita y no entregada si el commit se confirma después de que scoring dejó de esperar, lo que contradice BR-U0-08 en ese extremo. Q4: aislamiento de conexiones por dependencia.
**Context**: CONSTRUCTION - U7 scoring-explainability - NFR Design, GATE: esperando respuestas.

---
## U7 scoring-explainability — NFR Design: respuestas y artefactos
**Timestamp**: 2026-10-03T16:14:19Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1–Q4 = A. Generados `construction/scoring-explainability/nfr-design/nfr-design-patterns.md` (P-U7-01..09) y `logical-components.md` (Mermaid validado + alternativa en texto).
**Context**: CONSTRUCTION - U7 - NFR Design.

---

## U7 NFR Design — precisiones derivadas y cambios a otros artefactos
**Timestamp**: 2026-10-03T16:20:11Z
**User Input**: N/A
**AI Response**: Precisiones derivadas de las respuestas, que no estaban explícitas en las opciones:
(a) Q1 generalizada a toda la fase previa al registro: presupuesto de 700 ms desde la llegada a scoring, porque las llamadas en serie (serving-config 500 + :predict 300 + explainability 800) también rompían NFR-U7-04.
(b) fail_closed best effort con timeout de 250 ms, para que el fail-closed quepa en 1 s.
(c) Peor caso con registro degradado ≈ 6,1 s, por lo que el timeout de case-service hacia scoring debe ser ≥ 7 s (pendiente U8).
(d) Q3 obliga a que el resumen al solicitante lea la recomendación entregada (BFF envía recommendation_entry_id) y a que las proyecciones monitoring/metrics lleven seq y recommendation_entry_id (pendiente U9/U11).
(e) Corregida fila RESILIENCY-10 de U0, desactualizada desde U7 NFR Req Q4.
Corregidos en autorrevisión: IDs de flujo (F18/F20/F21, no F14/F15/F16), PriorityClass vectra-high (P-U1-09) y namespace vectra-app.
Archivos modificados: U7 nfr-requirements.md (NFR-U7-04, 10); U7 business-rules.md (BR-U7-13, 15), business-logic-model.md §2.3, domain-entities.md §4; U0 business-rules.md (BR-U0-08, BR-U0-35), domain-entities.md (§5.2 human_decision.recommendation_entry_id, §9.1 ApplicantSummaryRequest), nfr-design-patterns.md (P-U0-07 y fila RESILIENCY-10), contracts-code-generation-plan.md (Paso 10); U3 business-rules.md (BR-U3-14), domain-entities.md (§3 proyecciones, §4.1 delivery_status), decision-registry-code-generation-plan.md (Paso 8); component-methods.md (explainability applicant_summary).
**Context**: CONSTRUCTION - U7 - NFR Design, esperando aprobación.

---

## U7 NFR Design — prompt de aprobación
**Timestamp**: 2026-10-03T16:20:11Z
**AI Response**: Presentado el mensaje de cierre de 2 opciones (Request Changes / Continue to Next Stage).
**Context**: CONSTRUCTION - U7 - NFR Design, GATE de aprobación.

---
## U7 NFR Design — Request Changes: rastro de cambios a U0 y U3
**Timestamp**: 2026-10-03T16:24:18Z
**User Input**: "El hallazgo: el rastro de auditoría hacia U0 y U3 no se actualizó

La tabla "Cambios a otras unidades" de business-rules.md §6 sigue siendo exactamente la misma que antes de esta ronda de NFR Design — solo tiene las filas de los cambios de Q1–Q7 del Functional Design. No aparece ninguna fila nueva para:

U0: Q3 dice explícitamente "la entrada human_decision lleva un campo nuevo, recommendation_entry_id... (cambio en el payload de U0)" — un cambio real a un tipo ya aprobado de U0.
U3: Q3 dice "el expediente (U3) marca como «no entregada» toda entrada recommendation del caso que no corresponde..." — y el propio checklist de este plan de NFR Design (punto 5) lista a U3 explícitamente como una unidad que necesita el cambio aplicado y registrado (a diferencia de U8, que marca como "pendiente" porque todavía no existe). Dado que U3 ya completó sus cuatro etapas y su plan de tareas, esto implicaría una corrección real a artefactos de U3 ya aprobados — y no tengo manera de confirmar que ocurrió."
**AI Response**: Hallazgo confirmado: la tabla §6 de `scoring-explainability/functional-design/business-rules.md` no tenía las filas de NFR Design (solo se habían registrado en `nfr-design/nfr-design-patterns.md` §7 y en audit.md). Verificado con grep que los cambios a U0 y U3 sí estaban aplicados, cada uno con su nota «precisado el 2026-10-03 por U7 NFR Design»: U0 BR-U0-08 (línea 80), BR-U0-35 (línea 125), domain-entities §5.2 human_decision (línea 237) y §9.1 ApplicantSummaryRequest (línea 341), P-U0-07 (línea 89) y fila RESILIENCY-10 (línea 160), plan Paso 10; U3 BR-U3-14 (línea 117), domain-entities §3 (línea 75) y §4.1 (línea 85), plan Paso 8 (línea 122). Agregadas 11 filas a la tabla §6 (U0 ×5, U3 ×3, component-methods, U8 pendiente, U9/U11 pendiente); nota en nfr-design-patterns §7 que remite a §6 como registro acumulado de la unidad.
**Context**: CONSTRUCTION - U7 - NFR Design, esperando aprobación.

---
## U7 NFR Design — verificación del contenido real en U3
**Timestamp**: 2026-10-03T16:26:36Z
**User Input**: "Esta tabla es la promesa de U7 de lo que cambió en U3 — no son los propios artefactos de U3 ya corregidos. ¿Puedes confirmar o subir el contenido real de nfr-design-patterns.md de U7 (que se quedó fuera de esta subida) y los artefactos de U3 (business-rules.md, domain-entities.md) para verificar que BR-U3-14 y los campos de §3/§4.1 quedaron como se describe aquí?"
**AI Response**: Mostrado el texto literal de U3 BR-U3-14, domain-entities §3 y §4.1, plan Paso 8, y la estructura de U7 nfr-design-patterns.md (229 líneas, P-U7-01..09, §6–§9). Script de trazabilidad del plan de U3: 0 desfases, ninguna BR sin citar. Hueco encontrado en el cambio propio: la proyección `explanation` lee por `seq`, pero `EntryFilter` (component-methods) no estaba definido. Agregados al Paso 8 del plan de U3 los filtros `case_id`, `entry_type`, `seq` y el rango de `recorded_at`, y un criterio de aceptación (un `seq` de otro caso devuelve una página vacía).
**Context**: CONSTRUCTION - U7 - NFR Design, esperando aprobación.

---
## U7 NFR Design — Request Changes: fila SECURITY-11
**Timestamp**: 2026-10-03T16:29:52Z
**User Input**: "Un hallazgo en la tabla de cumplimiento (§6)

P-U7-03 incluye una prueba de abuso real: "un recommendation_entry_id de otro caso → 409" — alguien intentando pedir el resumen de un caso ajeno. Es exactamente la categoría de evidencia que SECURITY-11 pide ("casos de abuso"), la misma que ya vengo citando en U4, U5 y en el propio Functional Design de U7 (BR-U7-12, el conjunto RT-1). No aparece citada en esta tabla."
**AI Response**: Hallazgo confirmado con grep: SECURITY-11 no aparecía en el NFR Design de U7. Agregada la fila SECURITY-11 en §6, que cita P-U7-03 (resumen de un caso ajeno → 409; `seq` de otro caso en U3 → página vacía) y P-U7-01. Se agregó también, en la «Verificación» de P-U7-01, un caso de abuso que no tenía prueba: una cabecera `x-vectra-deadline` muy en el futuro o mal formada no extiende el presupuesto (tope de 700 ms). SECURITY-11 agregado a las líneas «Satisface» de P-U7-01 y P-U7-03.
**Context**: CONSTRUCTION - U7 - NFR Design, esperando aprobación.

---
## U7 scoring-explainability — NFR Design: aprobación
**Timestamp**: 2026-10-03T16:31:50Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U7 aprobado. Inicio de U7 — Infrastructure Design.
**Context**: CONSTRUCTION - U7 - NFR Design completado → Infrastructure Design.

---

## U7 scoring-explainability — Infrastructure Design: plan y preguntas
**Timestamp**: 2026-10-03T16:33:00Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/scoring-explainability-infrastructure-design-plan.md` con 3 preguntas: Q1 recursos y aporte a la cuota de vectra-app; Q2 apagado ordenado (hallazgo: ninguna unidad define preStop ni terminationGracePeriodSeconds; un SIGTERM durante un append, que puede durar hasta ~6,1 s, dejaría entradas no entregadas por un simple despliegue); Q3 presupuestos de tiempo como constantes en el código o en los values de Helm.
**Context**: CONSTRUCTION - U7 - Infrastructure Design, GATE: esperando respuestas.

---
## U7 scoring-explainability — Infrastructure Design: respuestas y artefactos
**Timestamp**: 2026-10-03T16:34:48Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1–Q3 = A. Generados `construction/scoring-explainability/infrastructure-design/infrastructure-design.md` (INF-U7-01..05) y `deployment-architecture.md` (Mermaid validado + alternativa en texto). Precisiones: el preStop usa la acción `sleep` nativa de Kubernetes (≥ 1.30), sin binario en la imagen; prueba unitaria que relaciona el período de gracia con el peor caso del append. Corregido en autorrevisión: la identidad de servicio usa `private_key_jwt` (U2 §2.2), no un secreto de cliente. Sin cambios en U0 ni U1 (no hay chart común). Agregada en la tabla §6 de U7 la fila del pendiente para U8 (case-service escribe en el registro y debe adoptar INF-U7-03).
**Context**: CONSTRUCTION - U7 - Infrastructure Design, esperando aprobación.

---
## U7 — Corrección en el NFR Design aprobado (P-U7-08), detectada al preparar el plan de tareas
**Timestamp**: 2026-10-03T16:41:00Z
**User Input**: "Continue to Next Stage" (aprobación del Infrastructure Design de U7, 2026-10-03T16:39:39Z)
**AI Response**: Infrastructure Design de U7 aprobado. Al cruzar métricas para el plan de tareas se detectaron dos errores propios en P-U7-08, ya aprobado: (1) la métrica de fail-closed por causa se llamaba `vectra_recommendations_total{cause}`, cuando BR-U7-03 fija `vectra_scoring_failclosed_total{cause}`, que usa U4 para `PromotionMismatchPersistent` (BR-U4-08); (2) la tabla atribuía `FailClosedPersistente` a una métrica de U7, cuando sale de `vectra_cases_failclosed_persistent` de case-service (U8, services.md). Corregido P-U7-08: dos métricas separadas, sin la fila de FailClosedPersistente y con una nota sobre las alertas de otras unidades; ExplainerVersionMismatch se documenta como complemento de PromotionMismatchPersistent.
**Context**: CONSTRUCTION - U7 - Infrastructure Design aprobado → Code Generation Part 1.

---
## U7 scoring-explainability — Code Generation Part 1: plan de tareas
**Timestamp**: 2026-10-03T16:43:10Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/scoring-explainability-code-generation-plan.md` con 20 pasos en 7 bloques: estructura y presupuestos; lógica pura (policy, narrative, factuality, applicant); explainability-service; scoring-service; despliegue y operación; verificación en kind por el operador; cierre. Script de trazabilidad: un desfase inicial (NFR-U7-41 citado en el Paso 5 y ausente de la tabla), ya corregido; resultado final: 0 desfases y ninguna BR-U7 sin citar. Verificado también que todos los NFR-U7, P-U7-01..09 e INF-U7-01..05 se citan en algún paso. Conforme a la instrucción del usuario, no se ejecutan Code Generation Part 2 ni Build and Test.
**Context**: CONSTRUCTION - U7 - Code Generation Part 1, GATE de aprobación.

---
## U7 scoring-explainability — plan de tareas: aprobación
**Timestamp**: 2026-10-03T16:45:48Z
**User Input**: "Continue to Next Stage"
**AI Response**: Plan de tareas de U7 aprobado. U7 completa (FD, NFR Req, NFR Design, Infra Design, plan de tareas). Inicio de U8 case-management — Functional Design.
**Context**: CONSTRUCTION - U7 cerrada → U8 Functional Design.

---

## U8 case-management — Functional Design: plan y preguntas
**Timestamp**: 2026-10-03T16:52:00Z
**User Input**: N/A
**AI Response**: Creado `construction/plans/case-management-functional-design-plan.md` con 9 preguntas. Hallazgos: (Q1) case-service no tiene flujo hacia governance ni hacia el model-store, pero derive necesita el feature_spec de la versión activa (pendiente de U5 §7), y hay una carrera vector/modelo si se activa otra versión entre la ingesta y la evaluación; (Q4) ambigüedad entre BR-U0-08, BR-U7-16 y services.md S2 sobre quién escribe las entradas fail_closed. Además: máquina de estados (Q2), reintentos y cola transaccional (Q3), reglas de la decisión con evidencia en dos fases (Q5), consultas de la explicación (Q6), retención (Q7, NFR-U3-03), estado de crédito (Q8) e ingesta (Q9).
**Context**: CONSTRUCTION - U8 - Functional Design, GATE: esperando respuestas.

---
## U8 case-management — Functional Design: respuestas y artefactos
**Timestamp**: 2026-10-03T16:52:30Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1–Q9 = A. Generados `construction/case-management/functional-design/domain-entities.md`, `business-rules.md` (BR-U8-01..22) y `business-logic-model.md` (máquina de estados con Mermaid validado y alternativa en texto, flujos, PBT-U8-01..08 con dos stateful, pruebas de ejemplo por historia, tabla de cumplimiento revisada contra el cuerpo).
Cambios en otras unidades, con nota «precisado el 2026-10-03 por U8 FD Qn»:
- U0: ScoringRequest.model_version_id; check_preconditions con requested/serving_model_version_id; BR-U0-02, causas 2, 5, 7 y 8 (la discrepancia de versión pedida produce version_mismatch y hace válidas las ausencias); BR-U0-08 (fail_closed: se reintenta con el caso); BR-U0-36 nueva (justificación); CaseDetail; scopes governance:read-serving (+case-service) y governance:read-feature-spec (nuevo); logic-model §2.2 y PBT-U0-01; plan Paso 6; rango BR-U0-20..36 en business-logic-model, NFR Design, plan Paso 3 y U3 business-rules.
- U2: cliente case-service con los dos scopes y la audiencia governance-service; P-U2-06 define el prefijo reservado x-vectra-.
- U4: BR-U4-06 guarda el feature_spec; BR-U4-19 nueva; domain-entities campo feature_spec; plan Paso 10 y tabla §3.
- U7: BR-U7-01 (comparación de versión), BR-U7-16, PBT-U7-07, plan Paso 11.
- Inventario: F104, component-methods (C04 retry_case, C09 get_feature_spec, BFF retry_case), application-design (F01–F104), unit-of-work (U8 y U4), services.md S2.
- U5 FD §7: pendiente resuelto.
Precisiones propias: (1) la cabecera de escenario se renombró de X-Vectra-Scenario a X-Test-Scenario, porque el gateway elimina las cabeceras internas y lo seguro es tratar x-vectra- como prefijo reservado; así un cliente externo tampoco puede inyectar x-vectra-deadline; (2) BR-U8-20: la anonimización no agrega transiciones; los casos anonimizados no se reevalúan. Corregido en autorrevisión: la referencia al patrón de U2 es P-U2-06, no P-U2-04. Pendiente para el NFR de U8: verificar la carga extra sobre serving-config contra NFR-U4-10/11.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: respaldo de RESILIENCY-10 en U0
**Timestamp**: 2026-10-06T02:32:15Z
**User Input**: "Hallazgos
1. nfr-requirements.md §7 dice que el circuit breaker no es de U0

La fila RESILIENCY-* dice: "N/A en U0 ... RESILIENCY-10 (timeouts y circuit breaker) se aplica en los servicios que usan las librerías". Eso dejó de ser cierto cuando U7 lo centralizó en vectra_common.deps. Ahora U0 implementa los timeouts obligatorios, la propagación del deadline y el breaker, y U7 depende de eso. Falta:

La fila RESILIENCY-10 como "Cumple (alcance de la librería)".
Un requisito NFR-U0-xx con su verificación: timeout obligatorio, breaker abierto = falla inmediata sin salir del proceso, y propiedad stateful más test_deps.py.

U7 cita NFR-RES-11 y RESILIENCY-10 hacia U0, pero ningún requisito de U0 los respalda."
**AI Response**: Hallazgo confirmado: la fila «RESILIENCY-* | N/A en U0» de `contracts/nfr-requirements/nfr-requirements.md` §7 estaba desactualizada desde U7 NFR Requirements Q4, y ningún NFR-U0 respaldaba `vectra_common.deps`. Cambios: (1) NFR-U0-23 nuevo en §3 (timeout obligatorio, presupuesto propagado, circuit breaker abierto = falla inmediata sin salir del proceso, un cliente por dependencia, httpx solo en deps), con su verificación: test_deps.py, test_deadline.py, propiedad stateful y regla de import-linter; (2) §7: fila RESILIENCY-10 «Cumple (alcance de la librería)», fila RESILIENCY-otras N/A y fila PBT-06 Cumple; (3) también desactualizado y corregido: el FD de U0 decía «PBT-06: N/A, sin componentes con estado» (business-logic-model, párrafo y tabla); (4) P-U0-07 «Satisface» y plan de U0, Paso 10, citan NFR-U0-23; (5) U7 NFR-U7-11 y NFR-U7-43 citan NFR-U0-23.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: PBT-06 entre unidades y PBT-U0-14
**Timestamp**: 2026-10-06T02:37:25Z
**User Input**: "2. PBT-06 queda inconsistente entre unidades
U0 hoy: en la última versión del business-logic-model.md de U0 que vi, PBT-06 figura como "N/A: sin componentes con estado". Este nfr-requirements.md no lo menciona.
U7: su tabla dice PBT-06 | Cumple | Propiedad stateful del circuit breaker (U0).
Lo que falta: esa propiedad no tiene un ID en la lista de propiedades de U0 (PBT-U0-01..13). Hace falta un PBT-U0-14 y cambiar la fila de PBT-06 a "Cumple"."
**AI Response**: Verificado: la fila PBT-06 de U0 (business-logic-model y nfr-requirements) ya decía «Cumple» desde la corrección de las 02:32 (el usuario vio la versión anterior), pero la propiedad no tenía ID. Cambios: (1) PBT-U0-14 nuevo en la tabla de propiedades de U0 (stateful del circuit breaker contra un modelo de referencia; nunca hay una llamada con el circuito abierto; una sola llamada de prueba en semiabierto; timeout ≤ presupuesto), con sus generadores; (2) módulo `deps` agregado a la tabla de módulos de U0, donde faltaba; (3) las filas PBT-06 de U0 (FD y NFR), la verificación de NFR-U0-23 y P-U0-07 citan PBT-U0-14; (4) plan de U0: PBT-U0-01..14, Paso 10 con test_deps_stateful.py y fila en la tabla de propiedades; (5) U7: NFR-U7-11, las filas PBT-06 del NFR y del NFR Design citan PBT-U0-14, y la fila PBT-06 del FD de U7 se precisó (N/A en la lógica de U7; el breaker es de U0 y lo cubre PBT-U0-14), para que no contradiga al NFR.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: flujo §2.1 de U7 sin la comparación temprana de versión
**Timestamp**: 2026-10-06T02:43:21Z
**User Input**: "Hallazgo nuevo

U7 business-logic-model.md §2.1 no muestra la comparación temprana de versión. El flujo de recomendación sigue diciendo si activo: KServe :predict .... BR-U0-02 (causa 7, extendida por U8) establece que con requested_model_version_id ≠ serving_model_version_id scoring no invoca KServe ni el explicador. El flujo debería leer algo como si activo y la versión pedida = la de serving-config: :predict ..., y si no coincide, ir a check_preconditions sin llamadas. Sin ese paso, el flujo contradice a U0 por omisión. PBT-U7-07 ya lo cubre en sus generadores, pero el flujo no."
**AI Response**: Hallazgo confirmado. Corregido el flujo §2.1 de U7 (rama de versión distinta sin llamadas → check_preconditions → version_mismatch, antes de :predict). La misma omisión existía en la fuente: la secuencia de BR-U0-08, paso 2 («si activo: predecir…»), corregida con las dos ramas, y en `services.md` S1 paso 3.1, también corregido.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Decisión: deps en los umbrales de cobertura y mutación de U0
**Timestamp**: 2026-10-06T02:45:57Z
**User Input**: "3. Umbrales de cobertura y mutación sin deps (decisión para ti, no es un defecto)

NFR-U0-40 exige 100 % de ramas en outcome, authz y logging, y NFR-U0-41 aplica mutation testing a outcome y authz. Esos módulos recibieron esa exigencia porque un error silencioso en ellos rompe una garantía de seguridad. El estado del breaker decide si se llama a una dependencia que está fallando, y eso sostiene el fail-closed de todos los servicios. Mi recomendación es sumar la máquina de estados de deps a ambas listas; si prefieres el 95 % general, déjalo anotado como decisión."
**AI Response**: Decisión: se adopta la recomendación. `deps` entra en NFR-U0-40 (100 % de ramas) y en NFR-U0-41 (mutmut sobre la máquina de estados del breaker y la aritmética del presupuesto). Motivo: un mutante que sobreviva en el umbral o en el semiabierto rompería el fail-closed de todos los servicios sin que lo detecte una prueba de ningún servicio. Actualizados: NFR-U0-40, NFR-U0-41 y la fila AUTONOMIA-06 de §7 (nfr-requirements), tech-stack-decisions y el plan de tareas de U0 (configuración de cobertura y mutmut).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: stack de U0 y seis puntos pendientes
**Timestamp**: 2026-10-06T02:48:39Z
**User Input**: "4. tech-stack-decisions.md omite dos dependencias

El plan de tareas pinnea httpx y prometheus-client, y el stack de U7 atribuye httpx a U0 ("solo vía vectra_common.deps"). Ninguna de las dos aparece en el stack de U0. prometheus-client ya faltaba antes de U7; httpx es la que hace visible el hueco ahora.

Siguen abiertos de rondas anteriores
Diseño funcional de U8:
La ventana de occurred_at (±5 min de BR-U3-05) contra los reintentos del outbox.
La aritmética de BR-U8-07 (31 min contra 930 s).
La exclusión de casos anonimizados en BR-U8-15.
La fila de SECURITY-14.
Application Design:
DELETE en case_app, o un rol de retención.
Los siete documentos que aún describen el mundo anterior a F104."
**AI Response**: Nota: los seis puntos «abiertos de rondas anteriores» no constaban en esta sesión ni en audit.md; se atienden ahora. Todos verificados y corregidos:
(1) U0 tech-stack-decisions: filas httpx (solo en vectra_common.deps, NFR-U0-23) y prometheus-client (8081, BR-U0-73, vectra_circuit_state).
(2) occurred_at: defecto real que también afectaba al reconciliador de U4 (un reintento después de 5 min se rechazaría siempre). U3 BR-U3-05: la ventana aplica solo a llaves nuevas y después de la idempotencia. BR-U3-06: la comparación excluye occurred_at. Actualizados el flujo §2.1, PBT-U3-01, PBT-U3-08 y el plan Paso 7. U0: occurred_at = intento; payloads con decided_at, escalated_at? y frozen_at. U4: el reconciliador fija un occurred_at nuevo y freeze lleva frozen_at. U8: BR-U8-18, BR-U8-09, outbox sin occurred_at y PBT-U8-07 con reintentos tardíos.
(3) BR-U8-07: el total correcto es 930 s ≈ 15,5 min, no 31 min. El texto de Q3 listaba un retraso de más; se conservan los parámetros explícitos (base de 30 s, factor 2, 6 intentos). PBT-U8-02 actualizada.
(4) BR-U8-15 y BR-U8-19 excluyen los casos anonimizados (409).
(5) Fila SECURITY-14 en la tabla de cumplimiento del FD de U8.
(6) Inventario §4: case_app con DELETE solo sobre evaluation_jobs; rol nuevo case_retention (DELETE en case_identifiers y evaluation_jobs, UPDATE por columna en cases); flujo F105 (CronJob case-retention); BR-U8-20 lo usa; rango F01–F105.
(7) Documentos anteriores a F104 corregidos: component-dependency §7 (diagrama y texto; también faltaba la arista F103), unit-of-work-dependency (matriz, diagrama U4→U8 y orden de construcción), components.md (C04 y C09), services.md S1 paso 2, unit-of-work.md U8 (contenido y flujos) y U0 business-logic-model §2.3. Son 6 documentos (7 secciones); si la lista del usuario tiene otro, falta identificarlo.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: precisiones en U8
**Timestamp**: 2026-10-06T03:00:07Z
**User Input**: "Precisiones en U8
Momentos de negocio sin cota. Antes occurred_at estaba a ±5 min del reloj; ahora un decided_at de hace un año pasaría. recorded_at sigue siendo la hora de la base, así que no se pierde la referencia. Sugiero que U0 valide *_at ≤ occurred_at y una edad máxima de pendiente, y que BR-U3-05 lo diga. Para que la cota tenga sentido, U8 necesita definir esa edad máxima y una alerta de evidencia pendiente (en U4 la abandona a las 24 h). Esto último puede ir en NFR Design.
viewed_at falta en la tabla de U8. BR-U3-05 lo lista, pero la fila de U0 §5.2 de U8 menciona solo decided_at, escalated_at y frozen_at, y BR-U8-19 dice "momento" sin nombrar el campo.
El doble del registro en PBT-U8-07. El texto no dice que implemente BR-U3-05/06 (ventana solo para llaves nuevas, contenido sin occurred_at). Si el doble es permisivo, la prueba no habría detectado el defecto original. Hay que decirlo, o añadir una prueba de integración contra U3.
Casos anonimizados. La regla está en BR-U8-15 y BR-U8-19, pero no en los flujos §3.2/§3.3, ni en la tabla de errores de domain-entities §6, ni en ninguna prueba de ejemplo. Además, un caso listo que se anonimiza queda listo para siempre, porque no hay transición nueva. ¿La bandeja los oculta por anonymized, o conviene un estado terminal (vencido)? También confirma que quieres bloquear explanation_view en casos decidido anonimizados: ahí solo pierde la métrica de consulta."
**AI Response**: Decisiones y cambios:
(1) Cota: BR-U0-37 nueva (evaluated_at, decided_at, viewed_at, frozen_at y escalated_at ≤ occurred_at, y a lo sumo 7 días antes); BR-U3-05 la cita. 7 días porque el freeze de U4 no se abandona. U8: evidencia `abandonada` a las 24 h (como U4), la decisión abandonada libera el caso para una decisión nueva; la alerta de evidencia pendiente queda para el NFR Design de U8. Rango de validación BR-U0-20..37.
(2) viewed_at: nombrado en BR-U8-19, en el flujo §3.3 y en la fila de U0 §5.2 de la tabla §8.
(3) PBT-U8-07: el doble implementa BR-U3-05/06 y BR-U0-37, se valida con las pruebas de append de U3 (Paso 7) y hay una integración contra el registro real en kind.
(4) Anonimizados: estado terminal nuevo `vencido` (U0 §1.2, components.md C04), en lugar de ocultarlos en la bandeja, porque un caso oculto seguiría `listo`. Los no decididos pasan a `vencido` en la transacción del CronJob; `case_retention` puede actualizar `state` solo para `vencido`. BR-U8-12 (transición), BR-U8-15/19/20, domain-entities §1.1/§3.2/§6, flujos §3.2/§3.3, máquina de estados (Mermaid y texto), PBT-U8-01/04/08 y tres pruebas de ejemplo nuevas. Confirmado: explanation_view **no** se bloquea en casos decidido anonimizados (no expone datos y conserva la métrica); se retiró el bloqueo.
Corregido en autorrevisión: `decisions.case_id` era único e impedía decidir después de un abandono; ahora es un índice único parcial sobre pendiente_registro/confirmada.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: doble human_decision, diagrama, vencido y pendientes
**Timestamp**: 2026-10-06T03:06:32Z
**User Input**: "Hallazgos
1. Abandonar y volver a decidir puede dejar dos human_decision en el registro
[...] A. Que la llave de human_decision sea determinista por caso, UUIDv5(case_id, "human_decision") [...] B. No liberar el caso al abandonar [...] Cualquiera de las dos implica ampliar PBT-U8-07 [...]
2. El diagrama de §2 no tiene en_evaluacion → vencido [...]
3. Propagación de vencido y privilegios de case_retention [...] stories.md (US-107) [...] bandeja de U10 [...] trigger, como en P-U4-06 [...]
4. Falta una prueba nombrada para BR-U0-37 (menor) [...]
Sigue pendiente de rondas anteriores
U0: nfr-requirements.md §6 ("el único estado..."), NFR-U0-23(b) con deadline "en el futuro", y deadline.py fuera de las listas de 100 % y mutmut. [...]
U0 y U7: nfr-design-patterns.md y logical-components.md de U0, y la tabla §7 de U7 nfr-requirements.md.
Application Design: no pude verificar el inventario (F105, case_retention, case_app), unit-of-work-dependency.md, components.md, el diagrama de component-dependency.md §7, services.md S2/S4 ni la tabla de impacto de application-design.md §2."
(Entrada larga, resumida con [...] solo en las partes que repiten texto de artefactos; el texto completo está en la transcripción de la sesión.)
**AI Response**:
(1) Opción A adoptada en U8 y aplicada también a U4. U8: llave UUIDv5(case_id,"human_decision"); se conserva el payload abandonado; ante un 409 del registro se reenvía la abandonada, se confirma y la nueva recibe 409 decision_already_recorded. fail_closed de escalamiento: UUIDv5(case_id,"fail_closed",ciclo). PBT-U8-07: nunca más de una human_decision por caso; prueba de ejemplo. U4: BR-U4-17 con llave UUIDv5(entidad, n), mismo manejo del conflicto; domain-entities §1.3 (transition_number, idempotency_key); PBT-U4-07; plan Paso 8.
(2) Arista en_evaluacion → vencido agregada al Mermaid; validado (stateDiagram-v2, 19 aristas, coincide con la tabla de BR-U8-12 y con la alternativa en texto).
(3) US-107: escenario de casos vencidos. BR-U8-13: la bandeja excluye vencido por defecto (filtro explícito). Pendiente para U10. Trigger guard_vencido en BR-U8-20 (implementación en NFR Design); fila de case_retention aclarada en el inventario.
(4) Plan de U0, Paso 3: ejemplos de BR-U0-37.
Pendientes: U0 §6 (dos estados por proceso: JWKS y breaker); NFR-U0-23(b) (pasado → 504, futuro → nunca extiende); deadline en NFR-U0-40/41, tech-stack y plan; logical-components de U0 (deps con estado del breaker, componente deadline, métrica vectra_circuit_state); tabla §7 de U7 (fila NFR-U0-23 / PBT-U0-14). Application Design: services.md S2 (parámetros), S4 (frozen_at, reconciliador, aviso de listo, MonitoreoSesgoDetenido resuelto) y la tabla de impacto de application-design §2 (registry, governance, bias). El inventario, unit-of-work-dependency, components.md y el diagrama de §7 ya estaban corregidos; se mostró su texto literal.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: orden de transiciones en U4, Problem.reason, ciclo y Application Design
**Timestamp**: 2026-10-06T03:14:29Z
**User Input**: "Hallazgos
1. En U4, n = confirmadas + 1 choca con la excepción de freeze (serio) [...] Propongo: n = transiciones no abandonadas + 1 [...] Un índice único parcial (entidad, n) WHERE status <> 'abandonada'. Que una transición nueva espere a que la anterior de la misma entidad esté confirmada. [...]
2. decision_already_recorded no está en el catálogo de errores de U0 [...] Sugiero conflict_state con un campo reason = decision_already_recorded [...]
3. ciclo está sin definir en la llave de fail_closed [...] Define ciclo como el contador de escalaciones del caso.
4. Retoques residuales en Application Design (services.md S2 y S1 paso 5; components.md C05 y C06; unit-of-work-dependency.md U7×U4; component-dependency.md §7 nota F105; application-design.md §6 Pendientes)."
(Entrada larga, resumida con [...] solo en las partes que explican el escenario; el texto completo está en la transcripción de la sesión.)
**AI Response**:
(1) Propuesta adoptada en U4 BR-U4-17: n = no abandonadas + 1; índice único parcial (entidad, n) WHERE status <> 'abandonada'; una sola transición pendiente por entidad (la nueva → 409 conflict_state, reason transition_pending); freeze como excepción (se aplica aunque haya una pendiente y toma el n siguiente); el reconciliador escribe en orden de n; una pendiente con un freeze detrás no se abandona a las 24 h (cota de 7 días, FreezeEventPending). Consecuencia detectada en autorrevisión: el reconciliador sin líder (P-U4-02) podía escribir n y n+1 de la misma entidad en paralelo; ahora solo toma la menor pendiente por entidad. Actualizados domain-entities §1.3, business-logic-model §2.2 y PBT-U4-07 (orden de n, nunca una frozen_resolution sin freeze, a lo sumo una pendiente) y el plan de U4, Pasos 2 y 8.
(2) U0 §6: Problem.reason opcional con catálogo cerrado (decision_already_recorded, transition_pending), solo con conflict_state; PBT-U0-08 actualizada; U8 BR-U8-18, domain-entities §6 (fila nueva) y business-logic-model usan conflict_state + reason.
(3) ciclo = cases.escalation_count tras incrementarlo (campo nuevo en domain-entities §1.1).
(4) services.md S2 (paso 3.1 + 3.4–3.6) y S1 paso 5 (case-service escribe, solo la primera vez); components.md C05 (comparación de versión) y C06 (diccionario F103); unit-of-work-dependency U7×U4 (diccionario F103); component-dependency §7 (nota con F105; F103/F104 sí aparecen); application-design §6 (todo resuelto con su referencia; solo queda abierta la ventana W y la muestra mínima de U9).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## Reversión de todos los archivos al estado anterior a U8
**Timestamp**: 2026-10-06T03:30:26Z
**User Input**: "devolver a la version todos los archivos desde cuando empezamos la U8"
**AI Response**: Restaurados todos los artefactos al estado del 2026-10-03T16:45:48Z (U7 aprobada, U8 sin iniciar). Procedimiento:
1. Respaldo del estado previo en el scratchpad de la sesión: `backup-antes-de-revertir-U8-20261006T032854Z.tar.gz` (todo `aidlc-docs/`).
2. `git checkout e1c74be` de los 29 archivos modificados después de ese commit. El commit «Units of project 08» (2026-10-03 17:44Z) ya contenía la primera versión del FD de U8.
3. Borrados `construction/case-management/` y `construction/plans/case-management-functional-design-plan.md`.
4. Deshechos, con reemplazos inversos verificados por aserción, los cambios de U8 FD que contenía el commit: U0 (BR-U0-01/02/08, BR-U0-36, logic-model §2.2, PBT-U0-01, CaseDetail, ScoringRequest, scopes, plan), U2 (cliente case-service, P-U2-06), U4 (BR-U4-06, BR-U4-19, feature_spec, plan), U7 (BR-U7-01/16, PBT-U7-07, plan Paso 11), inventario (F104, component-methods, application-design, unit-of-work, services S2), U5 §7 y el rango BR-U0-20..36 → 20..35.
5. `aidlc-state.md`: U8 pendiente; siguiente etapa U8 Functional Design.
Verificación: ninguna referencia a U8 FD, F104, F105, BR-U8-*, feature-spec, BR-U0-36/37, BR-U4-19, PBT-U0-14 ni a cambios del 2026-10-06 fuera de audit.md.
Efecto colateral, informado al usuario: también se pierden las correcciones a otras unidades hechas durante la revisión del FD de U8 (NFR-U0-23, PBT-U0-14, deps/deadline en los umbrales, flujo §2.1 de U7, occurred_at en U3/U4, llaves deterministas en U4, Problem.reason, retoques de Application Design). Siguen disponibles en el respaldo.
`audit.md` no se revierte: por regla del proyecto solo admite añadidos; se conserva el historial y se agrega esta entrada.
**Context**: CONSTRUCTION - reversión al estado anterior a U8.

---
## U8 case-management — Functional Design: reinicio sobre la versión revertida
**Timestamp**: 2026-10-06T03:47:39Z
**User Input**: "sobre esta version empezamos a trabajar"
**AI Response**: Se toma como base la versión revertida (U7 completa, U8 sin iniciar). Creado de nuevo `construction/plans/case-management-functional-design-plan.md` con 11 preguntas. Las opciones recomendadas incorporan los resultados de la revisión revertida: F104 con comparación temprana de versión; estado vencido; backoff de 15,5 min o 31 min a elegir; escalamiento con llave por ciclo; llave determinista de human_decision y Problem.reason; X-Test-Scenario. Q10 y Q11 plantean dos defectos previos fuera de U8 que la reversión volvió a abrir: la ventana de occurred_at (U3/U4) y el respaldo en U0 del circuit breaker de U7.
**Context**: CONSTRUCTION - U8 - Functional Design, GATE: esperando respuestas.

---
## U8 case-management — Functional Design: respuestas y artefactos
**Timestamp**: 2026-10-06T04:07:08Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1–Q11 = A. Esta combinación coincide con el estado final de la versión revisada que se guardó antes de revertir (respaldo `backup-antes-de-revertir-U8-20261006T032854Z.tar.gz`). Se restauraron desde ese respaldo los 32 archivos de diseño y el directorio `construction/case-management/`, sin tocar audit.md, aidlc-state.md ni el plan nuevo; diff -rq lo confirma. Ajustes al plan vigente: cabecera Q1–Q11 = A; se quitaron dos notas que remitían a la redacción de las preguntas revertidas (BR-U8-03, BR-U8-07); nota en §8 sobre el origen de las filas «Revisión 2026-10-06»; fila Q11 nueva en §8 (cambios en U0 y U7). Trazabilidad: U3, U4 y U7, 0 desfases y ninguna BR sin citar; U0, los mismos falsos desfases de siempre (plan con formato anterior al script).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---

## U8 FD — prompt de aprobación
**Timestamp**: 2026-10-06T04:08:27Z
**AI Response**: Presentado el mensaje de cierre de 2 opciones.
**Context**: CONSTRUCTION - U8 - Functional Design, GATE de aprobación.

---
## U8 FD (gate abierto) — Request Changes: revisión de la versión restaurada
**Timestamp**: 2026-10-06T04:20:26Z
**User Input**: "Hallazgos (Altos: reintentos tardíos con 409 por correlation_id y contract_version en BR-U3-06; llave de idempotencia de scoring sin definir; proyecciones de U3 sin el momento de negocio y explanation_view sin su recomendación; el analista no ve la solicitud; PersistentFailure, CaseFilter y retry_case en component-methods; respaldos de case-db con identificadores eliminados. Medios y bajos: US-501 y services.md S1 paso 5; almacenamiento «escapado» de US-109/FR-ING-04 frente a BR-U0-29; rango F01–F104 frente a F105; estado de la propagación.)"
(Entrada larga, resumida en sus títulos; el texto completo está en la transcripción de la sesión.)
**AI Response**: Propagación: verificada con grep en disco; F104, F105, case_retention, retry_case, get_feature_spec, vencido en US-107 y governance:read-feature-spec ya estaban (la copia del usuario era anterior a la restauración). Faltaban de verdad PersistentFailure y CaseFilter.
Corregido:
- U3 BR-U3-06: compara solo campos de negocio (sin occurred_at, correlation_id ni contract_version); actualizados el flujo, PBT-U3-01 y el plan Paso 7. U8 (outbox) y U4 (reconciliador) conservan el correlation_id y el payload originales.
- U0 BR-U0-08 y U7 BR-U7-15/16: la llave de scoring es un UUID v4 por solicitud, nunca derivado de case_id ni de attempt.
- U3 §3: evaluated_at, decided_at y viewed_at en monitoring y metrics; U0 §5.2: recommendation_entry_id en explanation_view (BR-U8-19); pendiente para U9 y U11.
- U0 §1.2: CaseFilter y PersistentFailure; component-methods: tipos de list_persistent_failures, filtros de list_cases, MFA explícito en retry_case del BFF.
- US-501 (escenario de aperturas posteriores) y services.md S1 paso 5.
- free_text: BR-U8-01 (tal cual, con consultas parametrizadas, escape al presentar en U10) y precisión de FR-ING-04 en requirements.md.
- Rango F01–F105 en la tabla §8.
Decisiones llevadas a `construction/plans/case-management-functional-design-review-questions.md`: R1 (qué ve el analista) y R2 (respaldos frente a la Ley 1581).
**Context**: CONSTRUCTION - U8 - Functional Design, GATE: esperando respuestas de revisión.

---
## U8 FD (gate abierto) — Request Changes: freeze con mark_active pendiente, evaluated_at y R1
**Timestamp**: 2026-10-06T04:29:01Z
**User Input**: "Hallazgos — Siguen abiertos: el defecto serio de U4 no está resuelto en BR-U4-17 (freeze con un mark_active pendiente: la segunda transacción dejaría la versión congelada como inactivo y la nueva como activo; propuesta: revalidar from_state y tratar el par de mark_active como unidad; reflejarlo en PBT-U4-01 y PBT-U4-07). La proyección monitoring no trae evaluated_at. R1 deja visibles la edad y la región. Nota menor: en BR-U4-17 el último punto de la lista se mezcla con el párrafo del reenvío de la abandonada."
**AI Response**: (1) U4 BR-U4-17: la transacción 2 revalida (sigue pendiente y estado = from_state; si no, `descartada` sin efecto); mark_active es una unidad (unit_id) que se confirma o se descarta completa (también en BR-U4-08); el freeze descarta en su transacción las pendientes de la versión y su unidad, y crea por cada una un model_event `transicion_descartada` (evento nuevo en U0 §5.2), escrito después del freeze. Se quitó la regla de «no abandonar con un freeze detrás», que ya no aplica. El párrafo del conflicto tras un abandono va aparte, como pidió el usuario. Actualizados domain-entities §1.3 (descartada, unit_id), el flujo §2.2, PBT-U4-01 y PBT-U4-07, P-U4-02 y el plan Paso 8. (2) U3 §3: evaluated_at en las recomendaciones de monitoring. (3) R1 reescrita con tres opciones: A (ocultar sexo y estrato y aceptar, documentado, que la edad y la región se vean; U9 vigila la disparidad humana), B (ocultar todas las fuentes) y C (mínimo).
**Context**: CONSTRUCTION - U8 - Functional Design, GATE: esperando respuestas de revisión R1–R2.

---
## U8 FD (gate abierto) — Request Changes: unidad de mark_active y alta de transicion_descartada
**Timestamp**: 2026-10-06T04:35:15Z
**User Input**: "Hallazgos — El abandono a las 24 h no está definido para la unidad (una mitad abandonada y otra con ack; la ruta de conflicto confirmaría una transición suelta). Propuesta: abandonar y recuperar siempre por unidad completa. transicion_descartada no está dado de alta: falta en U0 §5.2 y en la fila de §10 de BR-U4; falta el actor en BR-U3-16; falta cómo se guarda (propuesta: fila sin cambio de estado con su propia llave). El Paso 2 del plan de U4 no menciona unit_id ni descartada; debe probar que el n de una descartada sigue reservado."
**AI Response**: Verificado: U0 §5.2 ya tenía transicion_descartada (línea 241, agregado en la ronda anterior); el resto faltaba. Cambios: BR-U4-17, la unidad se abandona y se recupera completa (mitades sin ack → abandonada; con ack → descartada + transicion_descartada con motivo abandono; una recuperación solo confirma la unidad completa). Almacenamiento: ModelTransition con kind = compensacion, from_state = to_state, su propio n y su llave; actor de sistema. domain-entities §1.3 con `kind`. Fila nueva en §10 de BR-U4 (U0 model_event y U3 BR-U3-16). BR-U3-16 con el actor `{kind: system, id: governance-service}`. PBT-U4-07 ampliada. Plan de U4, Paso 2: columnas unit_id y kind, estado descartada y prueba del n reservado frente al reutilizable.
**Context**: CONSTRUCTION - U8 - Functional Design, GATE: esperando respuestas de revisión R1–R2.

---
## U8 FD — respuestas de revisión R1 y R2
**Timestamp**: 2026-10-06T04:39:24Z
**User Input**: "ya respondi"
**AI Response**: R1 = A, R2 = A. R1: U0 §1.2 (CaseSummary.applicant_display; CaseDetail.application sin sex ni socioeconomic_stratum); BR-U8-13b nueva (vistas, riesgo aceptado de edad y región visibles con vigilancia de U9, log case.viewed, anonimizados sin identificadores); domain-entities §4; PBT-U8-04 y una prueba de ejemplo; filas SECURITY-03 y SECURITY-08; pendiente para U10. R2: BR-U8-20 (case-retention después de cada restauración de case-db, antes de que case-service quede listo; el restore-drill actual solo restaura registry-db; riesgo residual de los respaldos de 12 meses, [VERIFICAR] con cumplimiento); NFR-U1-07 con el paso nuevo del runbook; pendiente para el plan de tareas de U1; fila AUTONOMIA-05.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---

## U8 FD — prompt de aprobación
**Timestamp**: 2026-10-06T04:40:46Z
**AI Response**: Presentado el mensaje de cierre de 2 opciones.
**Context**: CONSTRUCTION - U8 - Functional Design, GATE de aprobación.

---
## U8 FD (gate abierto) — Request Changes: identifiers en CaseDetail, PBT-U8-04 y NFR-U1-07
**Timestamp**: 2026-10-06T04:45:57Z
**User Input**: "Hallazgos — Por pulir: CaseDetail no tiene dónde llevar los identificadores (propuesta: identifiers?, ausente en anonimizados, mencionado en el cambio de U0 §1.2). PBT-U8-04 se contradice (la bandeja «nunca contiene identificadores» y trae applicant_display). NFR-U1-07 promete más de lo que se prueba: elegir entre extender el simulacro para restaurar case-db o redactarlo como «documentado, no probado». Confirmar que U1 respalda case-db con PITR."
**AI Response**: Verificado: U1 respalda case-db igual que las demás bases (paso de clusters de datos del plan de U1: Barman Cloud, WAL continuo, backup base diario, PITR de 30 días y mensuales de 12 meses), y F75 permite leer cualquier backup. Decisión: extender el simulacro, porque AUTONOMIA-02 exige verificar todo requisito. Cambios: (1) U0 §1.2 y U8 §4: CaseDetail con `application` (sin el grupo de identificación ni las etiquetas de monitoreo) e `identifiers?` (ausente si el caso está anonimizado); BR-U8-13b. (2) PBT-U8-04: «sin identificadores completos», con applicant_display como única identificación. (3) NFR-U1-07 (verificación), P-U1-05 (paso 2b: segundo cluster efímero de case-db, case-retention, 0 identificadores vencidos, métrica vectra_restore_drill_retention_violations) y el plan de U1, Paso 13; BR-U8-20 lo cita como probado; pendiente para el plan de U8: CLI case-retention.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: tabla de 12 hallazgos y 2 pendientes
**Timestamp**: 2026-10-06T04:53:57Z
**User Input**: "Hallazgos (tabla): 1 reenvío de la decisión abandonada frente a la cota de 7 días de BR-U0-37; 2 intentos que no llegan a scoring sin entrada fail_closed (contra services.md S2); 3 escalamiento con retryable = false frente a PBT-U0-01; 4 explanation_view abandonado con explanation_viewed_before = true; 5 catálogo de reason sin los de U7 y code de los dos 422; 6 BR-U8-03 sin cliente channel-simulator en U2; 7 alta manual sin idempotencia e intake_keys sin limpieza; 8 X01 «por red» frente a NetworkPolicy sin métodos HTTP; 9 model_frozen_after_recommendation nunca se apaga; 10 fila 20..36 junto a 20..37 en §8; 11 BR-U8-19 sin rol; 12 trabajo en curso que termina con el caso vencido y 4xx de scoring reintentados. Además: llave de scoring no consta en §8; alerta de vectra_restore_drill_retention_violations falta en NFR-U1-32."
**AI Response**: Verificado: la llave de scoring sí estaba en §8 (fila de U0 BR-U0-08 y U7 BR-U7-15/16; la copia del usuario era anterior). Corregido: (1) BR-U0-37 y BR-U3-05: la cota se aplica solo a llaves nuevas, después de la idempotencia. (2) S2 y BR-U8-09: las entradas por intento solo cuando scoring respondió; los fallos locales quedan en el caso, en vectra_case_attempts_total y en el escalamiento con local_cause (U0 §5.2). (3) Escalamiento con retryable según BR-U0-04 (true); lo marca escalated_at. (4) BR-U8-17 cuenta solo consultas confirmadas; BR-U8-19 reenvía el payload original de una consulta abandonada. (5) U0 §6: code unprocessable_explanation (422) y reasons version_mismatch, feature_dictionary_incomplete y factuality_failed; PBT-U0-08; U7 domain-entities §5. (6) Cliente channel-simulator en U2, solo fuera de producción; BR-U8-03 lo reconoce por azp. (7) Idempotency-Key también en el alta manual (alcance usuario + llave); case-retention borra intake_keys de más de 30 días (rol actualizado). (8) X01 en dos capas: NetworkPolicy L3/L4 y Linkerd HTTPRoute + AuthorizationPolicy L7; BR-U8-22. (9) El barrido apaga model_frozen_after_recommendation. (10) Fila de rango unificada en 20..37. (11) BR-U8-19 solo analista. (12) Resultado tardío descartado si el caso cambió (UPDATE condicionado; log evaluation.result_discarded); BR-U0-06 y BR-U8-08: 5xx y transporte se reintentan, 401 un reintento con token nuevo, otros 4xx escalan de inmediato con scoring_rejected y la alerta ScoringRequestRejected (pendiente para NFR Design). NFR-U1-32 incluye RestoreDrillFailed (con retention violations) y RestoreDrillMissing.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: propagación a entidades y lógica, y precisiones en U0 y U1
**Timestamp**: 2026-10-06T05:08:02Z
**User Input**: "Hallazgos: 1 las correcciones no llegaron a domain-entities ni a business-logic-model de U8 (scoring_rejected, local_cause, evaluation.result_discarded, limpieza de intake_keys, Idempotency-Key del alta manual, channel-simulator, apagado de la marca, reenvío de la consulta abandonada; last_cause desactualizado; PBT-U8-01, 06 y 07 deben cubrirlos); 2 la frase final de BR-U0-08 dice retryable = false; 3 encabezado de la tabla de reason y descripción de local_cause; 4 BR-U0-37 sin función ni llamador; 5 si el reintento por 401 cuenta en los 6; 6 alerta de retention violations (SEV2, runbook_url) en NFR-U1-32 y §8; 7 fechas 2026-10-03 por U8 FD; 8 justificación de las 24 h en BR-U8-18."
**AI Response**: (1) domain-entities: last_cause con las causas locales, IntakeKey con alcance (client_id o user_id), created_at y limpieza, test_scenario_id solo con channel-simulator. business-logic-model: flujo §3.1 (causas locales, 401, otros 4xx, UPDATE condicionado y result_discarded, escalamiento con retryable según BR-U0-04), §3.3 (reenvío de la consulta abandonada), PBT-U8-01, 06 y 07 ampliadas y cuatro pruebas de ejemplo nuevas. Consecuencia propia detectada: scoring_rejected escala desde en_evaluacion; transición nueva en BR-U8-12, en el Mermaid (validado) y en la alternativa en texto, y BR-U8-09 lo cita. (2) BR-U0-08 corregida. (3) Encabezado de la tabla de reason y reason por fila; local_cause redefinida («no terminó con un RecommendResult»). (4) check_business_time en vectra_contracts.validation, fuera del pipeline, llamada por el registro solo para llaves nuevas; U0 logic-model, plan Paso 3 (test_business_time.py) y plan de U3 Paso 7. (5) El 401 se reintenta dentro del mismo intento y no consume uno de los 6. (6) RestoreDrillRetentionViolation SEV2 con runbook_url en P-U1-05, NFR-U1-32 y el plan de U1 Paso 13; fila en §8. (7) 11 menciones «2026-10-03 por U8 FD» → 2026-10-06. (8) BR-U8-18: las 24 h se alinean con U4 y acotan el bloqueo del caso.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: cause del escalamiento con scoring_rejected, NFR-U1-32, check_business_time y verificación de §8
**Timestamp**: 2026-10-06T05:14:43Z
**User Input**: "Hallazgos: 9 Decisión tuya: qué cause lleva la entrada de escalamiento cuando local_cause = scoring_rejected (cause sigue siendo obligatorio y BR-U8-09 no define valor para el 4xx). 6 Falta la alerta de vectra_restore_drill_retention_violations en las alarmas mínimas (U1 NFR-U1-32). 16 check_business_time no tiene propiedad ni ejemplos propios en la lógica de U0. 10–15 Sin poder verificar: U2, U3, U4, U7, U5 y Application Design (cambios del §8 de U8)."
**AI Response**: (9) Decisión: la entrada fail_closed lleva **exactamente uno** de cause (catálogo de U0, si el último intento terminó en FailClosed) o local_cause (si no terminó con un RecommendResult). No se fuerza una causa que no ocurrió; se retiró el mapeo a timeout/serving_config_unavailable. retryable según BR-U0-04 con cause; con local_cause, false solo para scoring_rejected. PBT-U0-01 rige los FailClosed de build_outcome, y esta entrada no es uno de ellos. Actualizados U0 §5.2, BR-U8-09 y el flujo §3.1. (6) Verificado: NFR-U1-32 ya incluía RestoreDrillRetentionViolation SEV2 con runbook_url desde la ronda anterior (la copia del usuario era anterior). (16) PBT-U0-15 nueva (oráculo de bordes de check_business_time) y ejemplo obligatorio en business-logic-model §3; plan de U0: PBT-U0-01..15, Paso 6 y tabla de propiedades. (10–15) Evidencia mostrada con grep: U2 (cliente case-service, channel-simulator, prefijo reservado), U3 (campos de negocio, cota solo para llaves nuevas, delivery_status, actor de transicion_descartada), U4 (BR-U4-19, llave UUIDv5(entidad, n), unidad de mark_active, rastro de descartadas, filas de §10), U5 (pendiente resuelto), U7 (comparación de versión, UUID v4, unprocessable_explanation, PBT-U0-14) y Application Design (F104, F105, case_retention, retry_case, PersistentFailure, CaseFilter, vencido en US-107, services S1).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: validación de cause/local_cause
**Timestamp**: 2026-10-06T05:19:33Z
**User Input**: "Hallazgos 1 La regla «exactamente uno de cause o local_cause» solo está escrita en la definición del payload. No hay regla de validación asociada ni propiedad o ejemplo que la pruebe. Tampoco se prueba que retryable = false solo ocurra con scoring_rejected. El plan no menciona local_cause en ningún paso (U0 lógica y plan, Pasos 3 y 6). 2 BR-U0-04 y BR-U0-08: BR-U0-04 solo conoce las causas del catálogo y hay que extenderla a las locales; BR-U0-08 dice «retryable según BR-U0-04», incompleto para scoring_rejected. 3 No está escrito en la definición del payload que local_cause solo lo escribe case-service (los scopes de U3 ya lo limitan, pero conviene que U0 lo diga)."
**AI Response**: (1) BR-U0-38 nueva (exactamente uno de cause o local_cause; local_cause solo con escalated_at; retryable coherente), PBT-U0-16 (oráculo por tabla de verdad), ejemplo obligatorio; plan de U0: Paso 3 (modelo FailClosedPayload con local_cause y escalated_at; test_fail_closed_payload.py con 5 ejemplos) y Paso 6 (PBT-U0-16); PBT-U0-01..16. Rango de validación BR-U0-20..38 en las cinco referencias y en §8 de U8. (2) BR-U0-04 extendida a las causas locales (false solo para scoring_rejected); BR-U0-08 cita BR-U0-38 y la extensión. (3) U0 §5.2: local_cause y escalated_at solo los escribe case-service; U3 BR-U3-03: desde registry:append:scoring → 403.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: 8 ajustes de redacción
**Timestamp**: 2026-10-06T05:27:17Z
**User Input**: "Ajustes de redacción propuestos (8, ninguno aplicado ni registrado en el §8): 1 U3 BR-U3-03, aceptar desde el scope case solo fail_closed con escalated_at; 2 U3 BR-U3-05, nombrar check_business_time; 3 U4 BR-U4-14, case-service lee serving-config y nota de NFR-U4-10/11; 4 U4 BR-U4-17, las compensaciones sin escribir cuentan como pendientes y bloquean, incluida la frozen_resolution; 5 U4 BR-U4-17, el reconciliador salta las n descartadas; 6 U7 BR-U7-16, quitar «el caso la reintenta»; 7 U7 BR-U7-16, scoring solo cause; 8 U7 BR-U7-01, serving_state se evalúa primero."
**AI Response**: Aplicados los 8 y registrados en una fila de §8 de U8: BR-U3-03 (regla simétrica: scoring sin local_cause ni escalated_at; case solo con escalated_at; lo contrario → 403); BR-U3-05 (check_business_time); BR-U4-14 (case-service lector y verificación en el NFR de U8); BR-U4-17 (las n descartadas se saltan; las compensaciones pendientes bloquean las transiciones nuevas, incluida frozen_resolution, con transition_pending); BR-U7-16 (el intento siguiente produce su entrada; scoring solo cause; 403 si no); BR-U7-01 (model_frozen antes que version_mismatch, por precedencia).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: abandono de compensaciones
**Timestamp**: 2026-10-06T05:31:36Z
**User Input**: "Hallazgos 9 ¿Se abandonan las compensaciones (transicion_descartada) a las 24 h? No consta ni en BR-U4-17 ni en el §8. Si se abandonan, la cadena queda con el evento original sin efecto y sin marca que lo diga, y se desbloquea la frozen_resolution sin compensación escrita. Propuesta: no abandonarlas, con alerta propia o reutilizando FreezeEventPending, igual que el freeze (U4 BR-U4-17)."
**AI Response**: Propuesta adoptada con alerta propia. BR-U4-17: una compensación nunca se abandona; sigue reintentando (sin momento de negocio, la cota de BR-U0-37 no la vence) y mientras exista pendiente se alerta CompensationEventPending (SEV2). Actualizados la tabla de alertas de BR-U4 §9, P-U4-02 (paso 4 nuevo y su tabla de alertas), PBT-U4-07 (una compensación nunca queda abandonada y sigue bloqueando la frozen_resolution), el plan de U4 Paso 8 (prueba y promtool) y la fila en §8 de U8.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: pendientes de U4 y paquete de revisión
**Timestamp**: 2026-10-06T05:35:55Z
**User Input**: "Hallazgos 1. U4: fila de CompensationEventPending en §9; descripción del Paso 8 sin la compensación; Paso 17 debe agregar CompensationEventPending con runbook_url y el §8 de U8 no cita ese paso; verificar domain-entities §1.3. Para el 1 y el 4 necesito el business-rules.md y el domain-entities.md de U4 con nombres distintos. 2. Sin verificar: U3, U7, U1, U2, U5 y Application Design (lista detallada)."
**AI Response**: Verificado: la fila de CompensationEventPending ya estaba en la tabla de alertas de BR-U4 (línea 193). Corregido: plan de U4, Paso 8 (menor n por entidad, sin abandono para freeze y compensaciones, CompensationEventPending) y Paso 17 (CompensationEventPending en la PrometheusRule, con runbook_url); fila de §8 de U8 con los Pasos 8 y 17. Dos huecos más encontrados en la lista de «sin verificar»: PBT-U7-07 no explicitaba «congelado con versión distinta → model_frozen» (agregado, con serving_state en los generadores) y el Paso 7 del plan de U3 no probaba el 403 simétrico de BR-U3-03 (agregado); fila nueva en §8. Paquete para el usuario con nombres prefijados por unidad: scratchpad `para-revision/` y `para-revision-20261006.tar.gz` (29 archivos: U0, U1, U2, U3, U4, U5, U7, Application Design, stories y requirements).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: flujo §2.1 de U7 y Paso 7 de U3
**Timestamp**: 2026-10-06T05:41:43Z
**User Input**: "Hallazgos 1. Ajustes de redacción (4, ninguno registrado en el §8): 1 el flujo §2.1 de U7 no muestra la rama «si congelado → model_frozen sin llamadas»; 2 el mismo flujo dice «idempotency_key del intento», debe decir UUID v4 propio de la solicitud; 3 el primer punto del Paso 7 del plan de U3 describe el diseño anterior; 4 la prueba del 403 de scoring no cubre local_cause. 2. Sin verificar: U3, U4, U7, U1, U2, U5 y Application Design."
**AI Response**: (1, 2) Flujo §2.1 de U7: rama congelado → model_frozen sin llamadas antes de la comparación de versión; llave = UUID v4 de la solicitud (y el del fail_closed, otro UUID v4). (3) Primer punto del Paso 7 del plan de U3 al día: forma del payload por scope, idempotencia por campos de negocio, ventana y check_business_time solo para llaves nuevas. (4) Prueba de fail_closed con local_cause desde scoring → 403. Fila de §8 de U8 actualizada. Paquete de revisión regenerado con los archivos al día.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: flujo de append de U3 y BR-U3-04
**Timestamp**: 2026-10-06T05:45:53Z
**User Input**: "Hallazgos 1. U3: 1 el flujo §2.1 no muestra check_business_time tras la ventana de ±5 min, solo para llaves nuevas; 2 la comprobación del scope no menciona la forma del payload de fail_closed, y PBT-U3-01 no incluye «misma llave con un momento de negocio de más de 7 días → ack original»; 3 los pasos de BR-U3-04 no incluyen la búsqueda de idempotencia ni las comprobaciones de llave nueva. Ninguno está registrado en el §8 de U8."
**AI Response**: Aplicados los tres. Flujo §2.1 de U3: comprobación de la forma del payload de fail_closed por scope (403) y check_business_time tras la ventana, solo para llaves nuevas (422). PBT-U3-01: misma llave con un momento de negocio de más de 7 días → ack original. BR-U3-04: paso 0 nuevo (búsqueda de idempotencia; si la llave es nueva, ventana y check_business_time). Fila nueva en §8 de U8. Paquete de revisión actualizado.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Solicitud de verificación
**Timestamp**: 2026-10-06T05:50:00Z
**User Input**: "2. Sin verificar (los archivos con los cambios no los he visto): U4 domain-entities §1.3; U7 Paso 11 y referencias a NFR-U0-23 y PBT-U0-14; U1 RestoreDrillRetentionViolation (NFR-U1-32, P-U1-05, Paso 13); U2 channel-simulator, scopes, audiencia y P-U2-06; U5 §7; Application Design (F104/F105, component-methods, components, services S1/S2, unit-of-work*, US-107/US-501, FR-ING-04, U0 §2.3)."
**AI Response**: Sin cambios: todos los puntos estaban aplicados. Se mostró al usuario el texto literal de cada uno, extraído del disco con grep y con número de línea.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: 5 ajustes de redacción
**Timestamp**: 2026-10-06T21:54:46Z
**User Input**: "1. Ajustes de redacción listos para redactar (5, sin registrar en el §8 de U8)
#    Pendiente    Dónde
1    Las transiciones de política y de fuentes de datos no tienen dónde guardar transition_number, idempotency_key ni pendiente_registro: las entidades y el Paso 2 solo definen model_transitions, pero BR-U4-17 les aplica la misma regla. Propuesta: tipo de entidad más entity_id (índice (entity_type, entity_id, transition_number)), o una tabla por entidad    U4 entidades §1.3 y plan Paso 2
2    El Paso 11 dice "idempotency_key fija por intento". Debe decir UUID v4 por solicitud, nunca derivado de case_id ni de attempt, reutilizado por el reintento del append, y otro UUID para el fail_closed. Falta el ejemplo "congelado con versión distinta → FailClosed(model_frozen)" y que scoring escribe solo cause    plan de U7, Paso 11
3    La frase de derive ("nunca identificadores directos") choca con que zona_vivienda se busca sobre el municipio, que está en el grupo de identificación. Debe decir que derive lo recibe pero nunca lo devuelve ni lo usa como clave (BR-U0-34)    U5 §7 y U0 lógica §2.3
4    La fila U6 (pendiente) (cálculo de confidence con domain_envelope.json) probablemente quedó obsoleta, porque U6 ya cerró su diseño    U5 §7 y U6
5    Confirmar que la credencial de solo lectura de F75 cubre el backup de case-db, o decidir si hace falta un flujo nuevo    U1 plan y component-dependency.md"
**AI Response**: Aplicados los 5 y registrados en cuatro filas nuevas de §8 de U8. (1) Decisión: una sola tabla `transitions` con `entity_type` (`model_version` | `policy` | `data_source`) y `entity_id`, índice único parcial `(entity_type, entity_id, transition_number) WHERE status <> 'abandonada'` y llave UUIDv5(`entity_type`:`entity_id`, n). Actualizados U4 domain-entities §1.3 (más referencias en §3.1 y §4), BR-U4-17, business-logic-model §2.1 (decía `idempotency_key=transition_id`, obsoleto) y PBT-U4-07, P-U4-02, INF-U4-03, plan Pasos 2 y 8, y `component-dependency.md` (`gov_archiver`). Consecuencia propia: la activación de una política (`activa` + `historica`) forma una unidad, como `mark_active`. (2) Paso 11 de U7: UUID v4 por solicitud, nunca derivado de `case_id` ni de `attempt`, reutilizado solo por el reintento del append; otro UUID v4 para el `fail_closed` con solo `cause`; ejemplos nuevos: congelado con versión distinta → `model_frozen`, llaves distintas con el mismo `attempt` y `fail_closed` sin `local_cause` ni `escalated_at`. (3) U5 §7 y U0 §2.3: `derive` recibe el campo de identificación como origen de la búsqueda, pero nunca lo devuelve ni lo usa como clave (BR-U0-34). (4) Fila U6 de U5 §7 marcada como resuelta por NFR-U6-05 y P-U6-01 (verificado en disco). (5) No hace falta un flujo nuevo, porque F75 lee el mismo destino que F70. La credencial de solo lectura queda limitada a los prefijos de `registry-db` y `case-db` y a `vectra-registry-checkpoints`, en F75, P-U1-05 y el Paso 13 de U1 (con su comprobación en `conftest`).
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: guard_unfreeze sobre transitions
**Timestamp**: 2026-10-06T22:03:50Z
**User Input**: "Pendiente    Dónde
1    El trigger guard_unfreeze exige "una model_transitions confirmada con ese id", y esa tabla ya es transitions con entity_type = model_version. Ninguna fila del §8 lo cita (ni guard_unfreeze ni model_transitions)    U4 nfr-design-patterns.md"
**AI Response**: P-U4-06: `guard_unfreeze` exige una fila confirmada de `transitions` con ese id, `entity_type = model_version`, `entity_id` igual a la versión actualizada, `kind = cambio_estado`, `from_state = congelado`, `to_state` igual al estado nuevo (`congelado` para `investigar`) y actor `cumplimiento`. La «acción `frozen_resolution`» no era una columna de la entidad. `guard_freeze` queda atado igual a la entidad. Plan de U4, Paso 2: la variable apuntando a una resolución de otra versión, o a una transición de política o de fuente, → excepción. La fila de §8 de U8 cita P-U4-06, los dos triggers y el nombre anterior `model_transitions`. Verificado con grep: ya no hay menciones de `model_transitions` fuera de los registros históricos.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Solicitud de verificación: U1, U2, U7 y Application Design
**Timestamp**: 2026-10-06T22:05:57Z
**User Input**: "Unidad    Qué falta comprobar
U1    Texto de NFR-U1-32 en el documento de requisitos (la alerta ya consta en el NFR Design y en el plan)
U2    Ruta del gateway para channel-simulator, límite de tasa por azp (el volumen N del simulador podría toparse con el de un canal real), P-U2-06 y MFA de retry_case
U7    Referencias a NFR-U0-23 y PBT-U0-14 en NFR-U7-11 y 43 y en la tabla de §7 de requisitos
Application Design    El índice F01–F105 en application-design.md; retry_case, get_feature_spec, PersistentFailure y CaseFilter en component-methods.md; vencido en components.md; services.md S1 y S2; unit-of-work*.md; US-107 y US-501 en stories.md; FR-ING-04 en requirements.md"
**AI Response**: Verificados sin cambios: NFR-U1-32 (línea 67 de U1 nfr-requirements); P-U2-06 (clave `azp`, cabeceras `x-vectra-`); NFR-U7-11, NFR-U7-43, la fila PBT-06 y la fila de §7 de U7; application-design.md (F01–F105), component-methods (PersistentFailure, retry_case BFF y case, CaseFilter, get_feature_spec), components C04 (`vencido`), services S1 y S2, unit-of-work.md (F104 y F105), unit-of-work-dependency.md, US-107, US-501 y FR-ING-04. Huecos corregidos: (1) la ruta de intake de U2 solo admitía JWT de `channel`, así que el simulador (`azp = channel-simulator`) recibía 403. Ahora admite los dos, el simulador solo fuera de producción, y BR-U2-11 permite un conjunto de `azp` por ruta. (2) El límite de 10 req/s por `azp` impedía la prueba de NFR-U1-11 (20/s durante 15 min). Decisión: límite propio de 30 req/s, ráfaga 60, para `channel-simulator`, solo fuera de producción. El contador está separado del del canal real y no consume su cuota. (3) El Paso 2 del plan de U2 no creaba el cliente `channel-simulator`; ahora lo crea solo en kind y staging, y `realm-lint` falla si aparece en prod. El Paso 7 tiene las pruebas de la ruta y de los descriptores. (4) BR-U8-11 dice explícitamente «sin MFA», alineada con component-methods. (5) `unit-of-work-story-map.md`: US-101 cita F07 y US-109 dice «almacenamiento tal cual» (FR-ING-04). Fila nueva en §8 de U8.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: cabeceras de aplicación en el gateway y redacción de MFA en §8
**Timestamp**: 2026-10-06T22:19:56Z
**User Input**: "1. Abiertos (2, ambos de redacción)
#    Hallazgo    Dónde    Propuesta
1    No hay prueba de que Idempotency-Key y X-Test-Scenario lleguen intactas a case-service a través del gateway. Idempotency-Key no aparece en ningún archivo de U2, y NFR-U2-42 solo habla de "cabeceras" en general. Es obligatoria en POST /v1/intake/applications y en el alta manual (BR-U8-02 y 04)    U2 P-U2-06 o NFR-U2-42, y plan de U2    Añadirlas a la verificación con el backend de eco: ambas llegan intactas y x-vectra-* no
2    Las filas del §8 de U8 dicen "MFA explícito en retry_case" y "retry sin MFA explícito", pero BR-U8-11 dice que el retry del CRO va sin MFA. "MFA explícito" puede leerse como que se exige    §8 de U8    Reescribir como "columna MFA = no en retry_case del BFF" y "retry sin MFA (BR-U8-11)"
2. Sin verificar (no he visto los archivos con los cambios)
Documento    Qué falta comprobar
application-design.md    Índice de flujos F01–F105
component-methods.md    retry_case (sin MFA), get_feature_spec, PersistentFailure, CaseFilter
components.md    vencido en C04 y la mención del diccionario en C09
services.md    S1 (paso 5: escribe case-service, solo la primera consulta) y S2 (3.a con version_mismatch)
unit-of-work.md, unit-of-work-dependency.md    U8 y U4, y la matriz con F103 y F104
stories.md    US-107 (escenario vencido) y US-501 (solo la primera consulta)
requirements.md    FR-ING-04 (texto libre tal cual, escapado al presentar)"
**AI Response**: (1) P-U2-06: `Idempotency-Key` y `X-Test-Scenario` pasan intactas (el gateway no las elimina, no las reescribe y no las usa como clave). La verificación con el backend de eco las comprueba byte a byte en `/api/intake/**` y `/api/console/**`, y comprueba que no llega ninguna `x-vectra-*`. También se actualizaron NFR-U2-42 y el Paso 13 del plan de U2. (2) Filas del §8 reescritas tal como se propuso. Verificación: se mostró el texto literal de application-design.md, component-methods.md (incluidos `CaseFilter` y `PersistentFailure` en U0 §1.2), components.md (C04 y C09), services.md (S1 3.1 y paso 5, S2), unit-of-work.md, unit-of-work-dependency.md, US-107, US-501 y FR-ING-04. Hueco encontrado: la celda U8 → U4 de la matriz no citaba F104, mientras que la de U7 cita F103; corregida. Fila nueva en §8 de U8.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD (gate abierto) — Request Changes: verificación de US-107
**Timestamp**: 2026-10-06T22:26:28Z
**User Input**: "Detalle menor

La línea de verificación de US-107 dice "fixtures de los 4 estados". Ahora existe el escenario de vencido, así que debería decir "los cuatro estados y un caso vencido" para que la prueba e2e lo cubra. No afecta al diseño."
**AI Response**: Verificación de US-107 actualizada: fixtures de los 4 estados y un caso `vencido`, oculto por defecto y visible con el filtro explícito. La fila de US-107 en §8 de U8 lo menciona.
**Context**: CONSTRUCTION - U8 - Functional Design, esperando aprobación.

---
## U8 FD — Aprobación
**Timestamp**: 2026-10-06T22:28:34Z
**User Input**: "Aprobado, continúa con NFR Requirements de U8"
**AI Response**: Functional Design de U8 aprobado. Inicio de NFR Requirements de U8: análisis del FD y de los NFR heredados; plan con preguntas en `construction/plans/case-management-nfr-requirements-plan.md`.
**Context**: CONSTRUCTION - U8 - Functional Design aprobado → NFR Requirements.

---
## U8 NFR Requirements — Plan y preguntas
**Timestamp**: 2026-10-06T22:40:00Z
**User Input**: (sin entrada nueva; continúa la aprobación del FD)
**AI Response**: Plan creado en `construction/plans/case-management-nfr-requirements-plan.md` con 9 preguntas: latencia de la API, tiempo hasta `listo`, topología y escalado del worker, carga sobre governance (pendiente del FD: NFR-U4-10 y k6 de U4), disponibilidad y modos de fallo, timeouts y circuit breakers, protección de identificadores en `case-db`, stack de persistencia y pruebas, y umbral de calidad de pruebas.
**Context**: CONSTRUCTION - U8 - NFR Requirements, esperando respuestas.

---
## U8 NFR Requirements — Respuestas del usuario
**Timestamp**: 2026-10-06T22:34:01Z
**User Input**: "ya respondi"
**AI Response**: Respuestas leídas del plan: Q1–Q9 = A, con estos ajustes: Q2, sondeo de la cola ≤ 500 ms y métrica `vectra_case_first_attempt_failure_ratio`; Q3, el worker no retiene conexión ni transacción durante la llamada, y el HPA por CPU no protege una cola atrasada; Q5, con el registro caído las evaluaciones tampoco siguen (`registry_unavailable`); Q6, solo timeouts, errores de conexión y 5xx cuentan como fallo del breaker; Q8, 12 clientes de `case-db` en `max_connections`; Q9, 100 % también en `evaluation`, `sweeps` y `retention`, y `mutmut` en `backoff`. Sin ambigüedades: no hacen falta preguntas de seguimiento. Generados `case-management/nfr-requirements/nfr-requirements.md` (NFR-U8-01..53) y `tech-stack-decisions.md`. Cambios a otras unidades: U4 NFR-U4-10 y el script k6 del Paso 19 (12 clientes); U0 NFR-U0-23, P-U0-07, PBT-U0-14 (comando `call_4xx`) y el Paso 10 del plan (un 4xx no cuenta como fallo); U1 Infrastructure Design (`max_connections` de `case-db`); `requirements.md` NFR-PER-01 (NFR-U8-02).
**Context**: CONSTRUCTION - U8 - NFR Requirements, esperando aprobación.

---
## U8 NFR Requirements (gate abierto) — Request Changes: SECURITY-14, case-retention y pendiente del §8
**Timestamp**: 2026-10-06T22:42:48Z
**User Input**: "Pendientes
#    Pendiente    Dónde
1    NFR-PER-01 en requirements.md: el tiempo hasta listo queda fijado en NFR-U8-02    requirements.md
2    Falta SECURITY-14: ni fila en el §8 ni requisito para las alertas de authz.denied, WriteAttempt, el gauge vectra_cases_failclosed_persistent y el log case.retry_requested    NFR de U8 (NFR-U8-45)
3    Ningún requisito para case-retention: frecuencia diaria, lotes e idempotencia sin bloquear la API, métrica de identificadores vencidos sin borrar y alerta si no corre en 2 días; y los [VERIFICAR] de 10 y 2 años y de 12 meses de respaldos    NFR de U8 (NFR-U8-46)
4    Marcar como resuelta la fila "Pendiente para U8 NFR Requirements" del §8 del diseño funcional (NFR-U8-15, NFR-U4-10 y el Paso 19 de U4 ya lo cubren)"
**AI Response**: (1) Verificado sin cambios: NFR-PER-01 (línea 303 de requirements.md) ya remitía a NFR-U8-02 desde la ronda anterior. (2) NFR-U8-45: `authz.denied` → `AuthDeniedBurst`; `WriteAttempt` → `vectra_core_write_attempts_total` y alerta `CoreWriteAttempt`; gauge → `FailClosedPersistente`; logs de `case.retry_requested` y `case.viewed` retenidos ≥ 90 días, más `vectra_case_retries_total`. Fila SECURITY-14 en §8. (3) NFR-U8-46: ejecución diaria con `Forbid`, lotes de ≤ 500 con `SKIP LOCKED`, idempotencia, métricas expuestas por case-service sin flujo nuevo, `CaseRetentionMissing` (> 2 días) y `CaseRetentionOverdue`, y plazos como parámetros. NFR-U8-47: los tres [VERIFICAR] se confirman con cumplimiento en `retention.md` como condición para desplegar en producción. §7 actualizado con lo que queda para NFR Design. (4) La fila pendiente del §8 del FD de U8 queda marcada como resuelta.
**Context**: CONSTRUCTION - U8 - NFR Requirements, esperando aprobación.

---
## U8 NFR Requirements (gate abierto) — Request Changes: precisiones de retención y X01
**Timestamp**: 2026-10-06T22:45:14Z
**User Input**: "Precisiones para NFR Design
CaseRetentionOverdue y filas bloqueadas. NFR-U8-46(b) dice que una fila tomada por la API se procesa en la corrida siguiente. Con la alerta definida como "quedan identificadores vencidos después de una corrida", esas filas la dispararían falsamente. El umbral debe exigir que persistan tras dos corridas consecutivas.
El job necesita dónde registrar su corrida. El requisito dice que "el job registra en case-db" la última corrida, pero ni las entidades del diseño funcional ni los roles tienen una tabla para eso (retention_runs) ni el permiso del rol case_retention para escribirla. Está anotado como pendiente de NFR Design; conviene añadirlo a las entidades.
X01 y el scraping del mock. X01 dice que solo case-service puede llegar a core-banking-mock, pero Prometheus necesita leer su puerto de métricas (F60 incluye vectra-mock) para que funcione CoreWriteAttempt. Hay que precisar que X01 rige el puerto de datos y que el de métricas (8081) admite a Prometheus.
Pendientes
#    Pendiente    Dónde
1    NFR-PER-01 en requirements.md: el tiempo hasta listo queda fijado en NFR-U8-02    requirements.md
2    Las tres precisiones de arriba    NFR Design de U8 y component-dependency.md (X01)"
**AI Response**: (1) Ya estaba aplicado; se mostró el texto literal de la línea 303 de requirements.md. (2a) NFR-U8-46(e): `CaseRetentionOverdue` solo si dos corridas exitosas consecutivas terminan con `overdue_remaining > 0`. (2b) U8 domain-entities §1.4 `RetentionRun` (tabla `retention_runs`). `component-dependency.md`: `case_retention` solo con `INSERT` y `case_app` solo con `SELECT`. NFR-U8-46(d) remite a la tabla. (2c) X01 rige el puerto de datos del mock (8080); el de métricas (8081) admite a Prometheus (F60), solo para `GET /metrics`. §7 y §9 del NFR actualizados.
**Context**: CONSTRUCTION - U8 - NFR Requirements, esperando aprobación.

---
## Consulta de estado
**Timestamp**: 2026-10-08T01:57:11Z
**User Input**: "muestrame el estado"
**AI Response**: Resumen de aidlc-state.md: U0–U7 completas; U8 case-management en NFR Requirements (gate abierto, esperando aprobación); U9–U12 pendientes.
**Context**: CONSTRUCTION - U8 - NFR Requirements, esperando aprobación.

---
## U8 NFR Requirements — Aprobación
**Timestamp**: 2026-10-08T02:01:51Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U8 aprobado. Se inicia U8 NFR Design: plan con preguntas en `construction/plans/case-management-nfr-design-plan.md`.
**Context**: CONSTRUCTION - U8 case-management - NFR Requirements aprobado → NFR Design.

---
## U8 NFR Design — Respuestas del plan y generación de artefactos
**Timestamp**: 2026-10-08T02:11:24Z
**User Input**: "ya respondi"
**AI Response**: Respuestas leídas: Q1–Q6 = A, sin ambigüedades ni contradicciones. Generados `case-management/nfr-design/nfr-design-patterns.md` (P-U8-01..10) y `logical-components.md` (diagrama Mermaid con alternativa en texto). Cambios a otros artefactos: U8 BR-U8-20 (plazos en `retention_settings`) y §8 (dos pendientes de NFR Design resueltos, fila nueva); U8 domain-entities §1.5 `RetentionSettings`; NFR-U8-46(f) y §7; `component-dependency.md` §4 (`SELECT` sobre `retention_settings` para `case_app` y `case_retention`; `case_migrator` escribe la fila); U0 P-U0-08 (remite a P-U8-09).
**Context**: CONSTRUCTION - U8 - NFR Design, esperando aprobación.

---
## U8 NFR Design (gate abierto) — Request Changes: siete hallazgos
**Timestamp**: 2026-10-08T02:18:27Z
**User Input**: "Hallazgos abiertos de U8 NFR Design

Son siete. Los cuatro primeros conviene arreglarlos antes de pasar a Infrastructure Design. No volví a verificar los archivos de U8 desde el primer envío.

Medios

1. A case_retention le faltan permisos SELECT

Dónde: matriz de roles de logical-components.md y component-dependency.md §4. Hoy solo tiene SELECT sobre cases y retention_settings.
Por qué falla: en PostgreSQL, un DELETE … WHERE exige SELECT sobre las columnas que lee.
Lo que falta:
Sobre case_identifiers y evaluation_jobs, para borrar por case_id.
Sobre intake_keys.created_at, para la limpieza de 30 días.
Sobre decisions.decided_at, porque el plazo de 10 años cuenta desde la decisión y cases no guarda esa fecha.
Sobre case_identifiers, para calcular overdue_remaining.
Efecto: la prueba de 2 000 casos de NFR-U8-46 fallaría con «permission denied».
Arreglo: SELECT por columna sobre esas tablas.

2. Dos alertas no disparan cuando desaparecen los datos

CaseApiUnavailable usa sum(up{job="case-service"}) == 0. Si caen todos los pods, el descubrimiento retira el target y la expresión no devuelve nada.
CaseRetentionMissing usa max(…last_success_timestamp). Si nunca hubo una corrida exitosa, la métrica no existe y la alerta no salta.
Arreglo:
Añadir absent(up{job="case-service"}) al primer caso.
En el segundo, exportar la métrica en 0 hasta la primera corrida exitosa, o usar absent().
Añadir un caso «sin serie» a los promtool test rules.

3. user_id no está en la allowlist de logs de U0

La allowlist (U0 domain-entities §8) permite principal_subject y principal_role, pero no user_id.
U8 lo usa en P-U8-06, NFR-U8-45(d), BR-U8-11 y BR-U8-13b, para case.viewed y case.retry_requested.
Consecuencia: el procesador descartaría el campo y los dos eventos de auditoría quedarían sin actor. La prueba de P-U8-06 que usa PBT-U0-07 fallaría en modo strict.
Arreglo en el lado de U8, sin tocar U0: usar principal_subject y principal_role, como ya hace authz.denied (BR-U0-73).
Bajo-medios

4. La etiqueta attempt no está en la lista permitida de P-U8-06

P-U8-08 usa attempt="1" en vectra_case_attempts_total. La lista de P-U8-06 es result, cause, state, entry_type, dependency, code, route_template.
La prueba «sin etiquetas fuera de la lista» fallaría.
Arreglo: añadir attempt (1..6) a la lista.

5. Los contadores no se inicializan en 0

Aplica a vectra_case_evidence_abandoned_total{entry_type} y a vectra_case_attempts_total{result="scoring_rejected"}.
Con increase(), el primer evento de una serie nueva se pierde. Es justo el caso que ScoringRequestRejected y CaseEvidenceAbandoned quieren detectar.
Arreglo: crear cada combinación de etiquetas en 0 al arrancar.
Bajos

6. La API de decisión y el reconciliador comparten el pool de 10 conexiones al registro

Con el registro lento pero vivo, un lote de 100 evidencias podría dejar sin conexiones a la decisión síncrona (p95 ≤ 300 ms, NFR-U8-01).
P-U8-02 aísla dependencias entre sí, pero no consumidores de la misma dependencia.
Arreglo: limitar el reconciliador, por ejemplo a 4 envíos simultáneos, y probarlo.

7. No está definido cómo se identifica case-worker

Los flujos F15, F104 y F40 nombran a case-service como origen, y U2 define un cliente de Keycloak llamado case-service.
Infrastructure Design debe fijar si los dos Deployments comparten ServiceAccount y cliente, o si se añade case-worker a esos flujos. Hoy no figura en los pendientes de logical-components.md §3.
Cosméticos
business-rules §8, fila «Pendiente para U10»: tiene dos celdas en vez de tres.
business-rules §8, fila «Pendiente para U9 y U11»: repite «Revisión 2026-10-06» y queda con una celda de más.
La tabla de cumplimiento dice que cada patrón tiene su «Verificación», pero P-U8-09 no tiene esa sección."
**AI Response**: Los siete hallazgos se confirmaron contra los archivos (allowlist de U0 §8 sin `user_id`; BR-U0-73 con `principal_subject`). (1) `case_retention` con `SELECT` por columna sobre `case_identifiers (case_id)`, `evaluation_jobs (case_id)`, `intake_keys (created_at)` y `decisions (case_id, decided_at, state)`, en la matriz de logical-components §1 y en component-dependency §4; P-U8-07 cuenta el plazo de 10 años desde `decisions.decided_at` y la prueba corre con el rol real. (2) `CaseApiUnavailable` con `absent(up{job="case-service"})`; `vectra_case_retention_last_success_timestamp` vale `retention_settings.created_at` hasta la primera corrida (columna nueva en domain-entities §1.5), y `CaseRetentionMissing` también con `absent()`; casos «sin serie» en `promtool`. (3) `case.viewed` y `case.retry_requested` con `principal_subject` y `principal_role` en P-U8-06, BR-U8-11, BR-U8-13b, NFR-U8-42 y NFR-U8-45(d). (4) `attempt` (1..6) en la lista de etiquetas. (5) Contadores con todas sus combinaciones en 0 al arrancar, con prueba. (6) Reconciliador con a lo sumo 4 envíos en vuelo, con prueba (P-U8-02, 04). (7) Identidad de `case-worker` como pendiente en logical-components §3. Cosméticos: celdas de las dos filas del §8 de business-rules corregidas; P-U8-09 con su «Verificación».
**Context**: CONSTRUCTION - U8 - NFR Design, esperando aprobación.

---
## U8 NFR Design (gate abierto) — Request Changes: tres hallazgos menores
**Timestamp**: 2026-10-08T02:22:54Z
**User Input**: "Hallazgos pendientes de U8 NFR Design

Quedan tres, todos menores, y ninguno bloquea el paso a Infrastructure Design. Los siete hallazgos anteriores y los cosméticos están cerrados.

1. NFR-U8-46(d) no recoge la regla de la métrica de retención

Dónde: NFR-U8-46(d) de nfr-requirements.md y la tabla de cambios de P-U8 §6.
Problema: (d) define vectra_case_retention_last_success_timestamp como el de «la última corrida exitosa». P-U8-07 y domain-entities §1.5 dicen que, si no hay ninguna corrida exitosa, vale retention_settings.created_at. Los requisitos y el diseño describen la métrica distinto.
Arreglo:
Añadir esa cláusula a NFR-U8-46(d).
Añadir una fila a la tabla de P-U8 §6.

2. Falta verificar que el upsert de retention_settings no pisa created_at

Dónde: P-U8-05, la verificación con Testcontainers.
Problema: created_at no cambia y es la base de la alerta CaseRetentionMissing en instalaciones nuevas. Si el INSERT … ON CONFLICT DO UPDATE lo sobrescribiera, cada migración reiniciaría ese plazo de 2 días. Hoy ninguna verificación lo comprueba.
Arreglo: añadir esta prueba: migrar dos veces con valores distintos de retention.* y comprobar que created_at queda igual mientras updated_at y los plazos sí cambian.

3. Cosmético: la viñeta del plazo de 10 años rompe la numeración

Dónde: P-U8-07, «Corrida».
Problema: la viñeta «el plazo de 10 años se cuenta desde decisions.decided_at…» quedó entre los pasos 1 y 2, al mismo nivel que la lista numerada. Al renderizar, la numeración puede reiniciarse.
Arreglo: moverla dentro del paso 1, con una sangría más."
**AI Response**: (1) NFR-U8-46(d): la métrica vale `retention_settings.created_at` mientras no haya una corrida exitosa; fila nueva en P-U8 §6. (2) P-U8-05: el upsert actualiza los plazos y `updated_at` pero nunca `created_at`, y la verificación con Testcontainers migra dos veces con valores distintos y comprueba que `created_at` no cambia. (3) P-U8-07: la viñeta del plazo de 10 años quedó dentro del paso 1, con una sangría más.
**Context**: CONSTRUCTION - U8 - NFR Design, esperando aprobación.

---
## U8 NFR Design — Aprobación
**Timestamp**: 2026-10-08T02:30:25Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U8 aprobado. Se inicia U8 Infrastructure Design: plan con preguntas en `construction/plans/case-management-infrastructure-design-plan.md`.
**Context**: CONSTRUCTION - U8 case-management - NFR Design aprobado → Infrastructure Design.

---
## U8 Infrastructure Design — Respuestas del plan y generación de artefactos
**Timestamp**: 2026-10-08T02:38:19Z
**User Input**: "ya respondi"
**AI Response**: Respuestas leídas: Q1–Q7 = A, sin ambigüedades. Generados `case-management/infrastructure-design/infrastructure-design.md` (INF-U8-01..08) y `deployment-architecture.md`. Precisión agregada en INF-U8-03: `HTTPRoute` de captura sin autorización en el mock, para que Linkerd responda 403 medido y no 404 sin ruta. Cambios a otros artefactos: `component-dependency.md` (F15 desde case-worker; F40, F104 con case-worker; F50 con case-worker y core-banking-mock solo JWKS; rol `case_worker` y `case_app` sin consumo de la cola; X01 con evidencia por capa; diagrama); U0 §7.2 (scopes); U2 clientes (`case-worker` nuevo); U7 INF-U7-05, deployment-architecture y logical-components (origen de F15); U8 NFR-U8-41, P-U8-06 (`CoreWriteAttempt` con dos series), logical-components (matriz y pendiente resuelto), BR-U8-22 y §8; U1 deployment-architecture (`vectra-mock` solo kind y staging).
**Context**: CONSTRUCTION - U8 - Infrastructure Design, esperando aprobación.

---
## U8 Infrastructure Design (gate abierto) — Request Changes: quince hallazgos
**Timestamp**: 2026-10-08T02:53:40Z
**User Input**: "Quedan 4 hallazgos de fondo, 8 menores en U8 y 4 menores en U7. Con el deployment-architecture.md de U1 ya no tengo archivos sin ver. Los de U8 siguen abiertos en los archivos que subiste.

De fondo (requieren decisión)

#    Hallazgo    Dónde    Propuesta
1    En producción no hay mock ni flujo hacia un core real. P-U8-06 dice «en producción el core es el del banco», pero el inventario no tiene egress hacia él y X01 no aplica en L7 a un host externo. El diagrama «Vista de producción» dibuja el mock.    INF-U8-02, P-U8-06, F17 y §5 de component-dependency.md, deployment-architecture.md    Elegir una opción. a) core.enabled = false y credit_status = no_disponible sin llamar ni abrir el breaker. b) Agregar un flujo de egress hacia el core real.
2    case_app conserva UPDATE sobre todas las columnas de cases, incluidas recommendation y recommendation_entry_id. Un pod de la API comprometido podría escribir una recomendación falsa.    INF-U8-01, §4 de component-dependency.md, logical-components.md    UPDATE por columna para case_app, y una prueba de que no puede escribir esas dos.
3    La tabla de transiciones está sin definir. Solo case_worker recibe SELECT sobre ella, pero case_app y case_retention también escriben state. BR-U8-12 habla de un CHECK sobre esa tabla, y un CHECK de PostgreSQL no puede consultar otra tabla.    INF-U8-01, BR-U8-12, matriz de logical-components.md    Definir el mecanismo: trigger SECURITY DEFINER o clave foránea compuesta. Incluir la tabla en la matriz.
4    CoreWriteAttempt pierde el primer evento. La serie de Linkerd nace en 1 y increase() no cuenta ese primer evento.    INF-U8-03, tabla de P-U8-06    sum(inbound_http_authz_deny_total{namespace="vectra-mock"}) - (sum(… offset 5m) or vector(0)) > 0. El caso de promtool debe arrancar en 1.

Menores en U8

#    Hallazgo    Dónde
5    El Job de RT-5 debe llevar la etiqueta de pod que admite la NetworkPolicy del mock. Si no, la NetworkPolicy lo descarta sin métrica.    INF-U8-03
6    La alerta de denegaciones debe filtrar por la ruta de captura. Si no, cualquier denegación del mock, como un scrape mal autorizado, dispara CoreWriteAttempt.    INF-U8-03, P-U8-06
7    CaseDbVolumeFilling necesita absent(). Si el kubelet deja de reportar el volumen, la alerta calla justo cuando el disco se llena. Tampoco pude confirmar que U1 «no tiene» una alerta de volumen.    INF-U8-08
8    NFR-U8-41 dice «Solo case-service tiene credenciales de case-db». NFR-U8-45(b) dice que cada WriteAttempt dispara la alerta. Ninguno está en la lista de §7 de INF-U8.    nfr-requirements.md, INF-U8 §7
9    La fila serving_config_client, feature_spec_cache dice «ambos» y debería ser solo case-worker. En §3, solo la identidad está tachada, y recursos, flujos, values y alertas también quedaron resueltos.    logical-components.md
10    La prueba de ejemplo de P-U8-06 («POST al mock → 403, WriteAttempt y métrica en 1») contradice INF-U8-03. Debe decir que es una prueba del mock aislado, sin proxy.    P-U8-06
11    La línea «Originación» del texto alternativo sigue con case-service → scoring. El patrón de cola en §8 dice case-service. Las listas «sin API de Kubernetes» y «Sin egress» no nombran a case-worker ni a case-retention. Falta un separador en X01. La tabla de namespaces no dice que vectra-mock solo existe en kind y staging (U1 ya lo dice).    component-dependency.md
12    Las filas viejas de §8 (U0 §7.2 y U2 realm) dicen que case-service lee feature-spec. Falta la fila de U1 deployment-architecture.md en el registro de cambios (el cambio sí está en U1). La tabla de módulos del modelo de lógica asigna evaluation a case-service.    business-rules.md, business-logic-model.md

Menores en U7

#    Hallazgo    Dónde
13    «El timeout de case-service hacia scoring ≥ 7 s» y «case-service guarda el registry_entry_id de la Recommendation que recibió» ahora corresponden a case-worker.    P-U7-02, P-U7-03 punto 2 y §8 de nfr-design-patterns.md
14    Las dos filas «U8 (todavía sin artefactos)» ya no son ciertas.    §6 de business-rules.md de U7
15    La caché del diccionario tiene dos filas que se contradicen: «sin vencimiento» y «se descarta a las 24 h». P-U7-05 dice sin expiración y LRU de 4 versiones.    §6 de domain-entities.md de U7"
**AI Response**: Los quince hallazgos se confirmaron. El mensaje anuncia cuatro menores de U7, pero lista tres (13–15). Hallazgo 1 (core en producción): requiere decisión del usuario; pregunta en `construction/plans/case-management-infrastructure-design-clarification-questions.md`, sin cambios hasta la respuesta. Aplicados los otros catorce: (2) `case_app` con `UPDATE (state, attempts, model_frozen_after_recommendation, updated_at)` sobre `cases`; (3) tabla `case_transitions (from_state, to_state, db_role)` y trigger `guard_transition` `SECURITY DEFINER` (compara con `session_user`), también en `INSERT`; BR-U8-12 sin el `CHECK`; fila en la matriz; (4, 6) `CoreWriteAttempt` con resta contra `offset 5m` y filtro `route_name="core-mock-catch-all"`, promtool arrancando en 1; (5) etiqueta de pod del Job de RT-5; (7) `absent()` en `CaseDbVolumeFilling` y texto sobre la búsqueda en U1; (8) NFR-U8-41 y NFR-U8-45(b) y filas en §7; (9) caché en `case-worker` y §3 resuelto; (10) prueba del mock aislado; (11) Originación, §8, listas de K8s y egress, separador de X01 y tabla de namespaces; (12) filas viejas anotadas, fila de U1 y módulo `evaluation` en `case-worker`; (13–15) U7 P-U7-02, P-U7-03, §8, business-rules §6 y domain-entities §6.
**Context**: CONSTRUCTION - U8 - Infrastructure Design, esperando la aclaración del hallazgo 1.

---
## Consulta de estado
**Timestamp**: 2026-10-08T03:28:00Z
**User Input**: "cual es su estado"
**AI Response**: Informado el estado: U8 Infrastructure Design con el gate abierto; la pregunta del hallazgo 1 ya tiene respuesta A en el archivo de aclaración, todavía sin aplicar. Sin cambios a artefactos.
**Context**: CONSTRUCTION - U8 - Infrastructure Design.

---
## U8 Infrastructure Design (gate abierto) — Request Changes: segunda revisión
**Timestamp**: 2026-10-08T03:28:43Z
**User Input**: "Esta es la misma lista que te mostré antes, sin cambios, porque no subiste archivos corregidos desde entonces. Quedan 1 hallazgo de fondo, 1 sobre case_worker, 5 menores en U8, 7 en U1, 1 en U2 y 4 cosméticos en U7.

De fondo (U8)

#    Hallazgo    Cambio
1    Q1 = A (core deshabilitado en producción) sin aplicar. Los archivos aún dicen «en producción el core es el del banco».    INF-U8-02: agregar core.enabled = false con conftest. BR-U8-21, NFR-U8-25 y 31: agregar el caso «no_disponible sin llamar y sin contar para el breaker». P-U8-06: cambiar su línea. F17 y X01 quedan «solo kind y staging», con una nota en §5. INF-U8 §7 y §8 y business-rules §8 registran el pendiente de la integración real.
N1    case_worker puede falsificar evidencia. Tiene INSERT en evidence_outbox «solo fail_closed», pero un permiso no restringe valores. Un worker comprometido podría insertar una human_decision y el reconciliador la enviaría con el scope de case-service.    Una política RLS con WITH CHECK (entry_type = 'fail_closed') en INF-U8-01, en la matriz de logical-components.md y en component-dependency.md §4. Más una prueba de migraciones: otro entry_type → error.

Menores en U8

#    Hallazgo    Dónde
7'    U1 ya tiene PostgresVolumeUsageHigh (80 % SEV3, 90 % SEV2, para los cuatro clusters). Retirar CaseDbVolumeFilling y citar la de U1. Se quita de §8 el pendiente «generalizarla».    INF-U8-08, §8
N2    Citar P-U1-08 («sin PgBouncer, conexiones directas») en INF-U8-01, porque guard_transition depende de session_user.    INF-U8-01
N3    Una línea de runbook: si el pod del mock se reemplaza dentro de los 5 minutos posteriores a un evento, la resta con offset 5m puede ocultar el evento siguiente.    INF-U8-03
N4    La fila de INF-U8 en business-rules §8 no cita NFR-U8-45.    business-rules.md §8
N5    case_fsm y backoff figuran solo en case-service, pero el worker también los usa.    business-logic-model.md §1

U1

#    Hallazgo    Dónde
7'-U1    PostgresVolumeUsageHigh no tiene el caso absent() y no aparece en la tabla de alertas.    INF-U1-02, logical-components.md §3
U1-a    Falta la fila case-worker → case-db en la tabla de readiness.    P-U1-04
U1-b    La lista de vectra-low no nombra a core-banking-mock.    P-U1-09
U1-c    Dice «kind con 3 nodos»; INF-U1-01 dice 4 workers. También deja «Calico, a confirmar» y «Alloy o Promtail, a elegir», ya resueltos.    tech-stack-decisions.md §1, §3, §4
U1-d    La fila de almacenamiento de objetos dice «MinIO en kind» con buckets backups y wal; INF-U1-03 pone MinIO en todos los entornos y los backups fuera del sitio.    tech-stack-decisions.md §2
U1-e    La fila «MinIO (solo kind)» tiene la misma contradicción, y los pendientes de §4 siguen sin marcar como resueltos.    logical-components.md §1 y §4
U1-f    Dice «solo existen los bindings K01–K06»; el inventario va hasta K14.    NFR-U1-27
U1-g    La cuota de vectra-app y vectra-mock aún no suma los aportes de U7 y U8. Es trabajo del chart, no de documentos.    NFR-U1-13, Code Generation de U1

U2

#    Hallazgo    Dónde
U2-a    Con el core deshabilitado en producción, case-service no debería tener core:read-credit ni la audiencia core-banking-mock en el realm de producción. Agregar la nota y una prueba del realm.    domain-entities.md §2.2

Cosméticos en U7

#    Hallazgo    Dónde
U7-a    Marcar como resuelta la fila «Pendiente para U8 (case-service): adoptar INF-U7-03».    INF-U7 §5
U7-b    Marcar como resueltos los puntos 1 y 3 de §8.    nfr-design-patterns.md, §8
U7-c    Marcar como resuelto el encabezado «Pendiente para el Infrastructure Design de U7».    logical-components.md §3
U7-d    Fusionar las dos filas de la caché del diccionario y quitar el «Antes decía…».    domain-entities.md §6
"
**AI Response**: Aplicados los 19 hallazgos. (1) Q1 = A: `core.enabled = false` en producción con `conftest` (INF-U8-02); `no_disponible` sin llamar y sin contar para el breaker en BR-U8-21, NFR-U8-25 y 31; NFR-U8-43, BR-U8-22 y P-U8-06 al día; F17 y X01 «solo kind y staging» con nota en §5 de `component-dependency.md`; deployment-architecture como vista de staging; pendiente de Operations en INF-U8 §7 y §8 y business-rules §8. (N1) RLS `worker_fail_closed_only` en `evidence_outbox` con prueba de migraciones, en INF-U8-01, logical-components §1 y `component-dependency.md` §4. (7') `CaseDbVolumeFilling` retirada; se cita `PostgresVolumeUsageHigh`. (N2) P-U1-08 citado en INF-U8-01. (N3) limitación de `offset 5m` para el runbook. (N4) NFR-U8-45 en business-rules §8. (N5) `case_fsm` y `backoff` en los dos procesos; además `retention` pasa a `case-retention` en business-logic-model §1 y la fila de módulos de logical-components se separa por proceso. U1: `absent()` y tabla de condiciones en INF-U1-02 y fila en logical-components §3; `case-worker` en P-U1-04; `core-banking-mock` y `case-retention` en `vectra-low` (P-U1-09); tech-stack §1–§4 (kind 1+4, MinIO en todos los entornos, Calico, Alloy); logical-components §1 y §4 resueltos; NFR-U1-27 hasta K14; U1-g como paso del chart (Paso 6 del plan de U1). U2: nota y prueba del realm de producción sin `core:read-credit` ni audiencia `core-banking-mock` (domain-entities §2.2 y Paso 2 del plan de U2, que además pasa a 9 clientes de servicio). U7: INF-U7 §5, §8 puntos 1 y 3, logical-components §3 y caché del diccionario en una fila. Punto abierto informado al usuario: con `no_disponible` la consola no puede distinguir «no integrado» de «core caído».
**Context**: CONSTRUCTION - U8 - Infrastructure Design, esperando aprobación.

---
## U8 Infrastructure Design (gate abierto) — Request Changes: tercera revisión
**Timestamp**: 2026-10-08T03:41:16Z
**User Input**: "Estos son los hallazgos abiertos. Solo U1-h tiene efecto real, y el resto es redacción.

Con efecto

#    Hallazgo    Dónde
U1-h    El absent() de PostgresVolumeUsageHigh usa un filtro con los cuatro clusters. absent() solo devuelve 1 si no existe ninguna serie que coincida. Si el kubelet deja de reportar solo case-db, las otras tres siguen reportando y la alerta calla. Eso contradice la prueba escrita: «sin serie de un Cluster durante 15 min → SEV2». Hay que usar un absent() por cluster, o count(...) < N con el número esperado de PVC. La prueba de promtool debe quitar la serie de un cluster.    INF-U1-02 y Paso 11 del plan de U1

U1 (redacción)

#    Hallazgo    Dónde
U1-i    El §6 tiene tres preguntas abiertas (Loki y Tempo, model-store, bindings K0x). INF-U1-03 e INF-U1-06 ya las resolvieron.    nfr-requirements.md §6
U1-j    Dicen «F01–F73», «F01–F88» y «K01–K13». component-dependency.md llega a F105 y K14. La prueba «todo ID del Markdown está en flows.yaml» fallaría para F90–F105 si se corre solo con el plan de U1.    P-U1-01 y plan de U1 (§1, Paso 3)

U2 (redacción)

#    Hallazgo    Dónde
U2-b    Mezcla de Redis y Valkey. INF-U2-04, component-dependency.md y el plan de Code Generation dicen Valkey. logical-components.md, P-U2-01, P-U2-04, NFR-U2-21/27/30 y tech-stack-decisions.md siguen con Redis. La imagen que se pinnea y se firma depende de cuál sea.    Cinco archivos de U2
U2-c    logical-components.md pone el controlador de Envoy Gateway en vectra-edge. INF-U2-02 y K14 lo ponen en envoy-gateway-system.    logical-components.md §1
U2-d    La prueba del realm de producción (sin core:read-credit para case-service) no aparece en realm-lint ni en las pruebas de ejemplo.    business-logic-model.md §1 y §3
U2-e    NFR-U2-10 y el Paso 14 del plan dicen «8 identidades de servicio». Con case-worker son 9.    nfr-requirements.md, plan de U2
U2-f    El Paso 3 del plan no incluye la regla «case-service en prod sin core:read-credit ni audiencia core-banking-mock». Está solo en el Paso 2.    Plan de U2, Paso 3

U8 (redacción)

#    Hallazgo    Dónde
C1    BR-U8-09 dice «case-service escribe una entrada fail_closed». La inserta el case-worker en el outbox y la envía el reconciliador de case-service.    business-rules.md
C2    Faltan los calificativos «solo kind y staging» en la fila del core de P-U8-02 y P-U8-03, en E6 de P-U8-09, en «Prometheus → core-mock» y en «scrapea los tres Deployments».    nfr-design-patterns.md, logical-components.md, deployment-architecture.md
C3    La fila del Job de migración no menciona guard_transition, las políticas RLS ni las filas de case_transitions. case-retention y la migración dicen PriorityClass «—», pero INF-U8-04 las pone en vectra-low.    logical-components.md §1
C4    CreditStatus solo da no_disponible si el core no respondió. Falta «o si core.enabled = false».    domain-entities.md §5
C5    NFR-U8-41 no menciona la RLS de evidence_outbox ni guard_transition.    nfr-requirements.md
C6    Faltan los calificativos «solo kind y staging» en NFR-U8-26 y NFR-U8-45(b).    nfr-requirements.md
C7    La fila «Migraciones» no menciona guard_transition, la RLS ni retention_settings. La fila de core-banking-mock no dice «solo kind y staging».    tech-stack-decisions.md
C8    El §1 lista el contenido de vectra-app sin case-worker, case-retention ni los Jobs de migración.    component-dependency.md §1
C9    Dicen «en producción el core es el del banco» y definen CoreWriteAttempt con una sola serie. Los documentos de diseño ya lo corrigieron. Conviene una nota «superado por Q1 = A e INF-U8-03».    Planes de U8 (NFR Design Q4, Infrastructure Design Q3)
"
**AI Response**: Aplicados los 17 hallazgos. (U1-h) `PostgresVolumeUsageHigh`: una regla de ausencia por `Cluster`, `(count(...{persistentvolumeclaim=~"<cluster>-[0-9]+(-wal)?"}) or vector(0)) < 6`, con la explicación de por qué un `absent()` común calla; la prueba de promtool quita solo las series de `case-db`; Paso 11 del plan de U1 al día. (U1-i) NFR-U1 §6 con las cuatro filas resueltas. (U1-j) P-U1-01 y plan de U1 (§1 y Paso 3) con F01–F105 y K01–K14, y la prueba de completitud sin rango fijo; las filas históricas del 2026-10-03 en INF-U1 §7 no se tocaron. (U2-b) Redis → Valkey en nfr-requirements, nfr-design-patterns, logical-components y tech-stack-decisions. (U2-c) controlador en `envoy-gateway-system`. (U2-d) regla de `realm-lint` y prueba de ejemplo del realm de producción en business-logic-model §1 y §3. (U2-e) 9 identidades en NFR-U2-10 y el Paso 14. (U2-f) regla y caso de aceptación en el Paso 3. (C1) BR-U8-09: la inserta `case-worker` y la envía el reconciliador. (C2) «solo kind y staging» en P-U8-02, P-U8-03, E6 de P-U8-09, §8 de nfr-design-patterns, F60 en logical-components y deployment-architecture. (C3) Job de migración con `guard_transition`, `case_transitions` y RLS; `vectra-low` para retención y migración. (C4) `CreditStatus` con `core.enabled = false`. (C5) NFR-U8-41 con RLS, `UPDATE` por columna y `guard_transition`. (C6) NFR-U8-26 y 45(b). (C7) tech-stack de U8. (C8) `vectra-app` con `case-worker`, `case-retention` y los Jobs de migración de U3, U4 y U8. (C9) notas «superado» en NFR Design Q4 e Infrastructure Design Q3 de U8; además en Infrastructure Design Q7 (`CaseDbVolumeFilling`).
**Context**: CONSTRUCTION - U8 - Infrastructure Design, esperando aprobación.

---
## U8 Infrastructure Design (gate abierto) — Request Changes: cuarta revisión
**Timestamp**: 2026-10-08T03:49:17Z
**User Input**: "Ningún hallazgo con efecto sigue abierto, en U1, U2, U7 ni U8. Quedan cinco cosméticos y dos puntos de diseño para el plan de Code Generation de U8.

Cosméticos abiertos (solo redacción)

#    Qué    Dónde
U8-cos    Bajo la cabecera «Todos resueltos», tres viñetas siguen sin tachar. El texto de la identidad de case-worker tampoco se ajustó al «Resuelto».    U8 logical-components.md §3
U2-g    NFR-U2-21 conserva la frase «Pendiente de NFR Design». También omite /api/promotion/** entre las rutas fail-open. El diagrama dibuja el controlador de Envoy Gateway dentro de vectra-edge.    U2 nfr-requirements.md y logical-components.md §2
U1-k    envoy-gateway-system no aparece en INF-U1-06, en deployment-architecture.md §2 ni en la wave 0. component-dependency.md ya lo tiene.    U1 infrastructure-design.md y deployment-architecture.md
U1-p    Falta un paréntesis de apertura en la frase count(...) or vector(0)) < 6. La regla de INF-U1-02 está bien escrita.    Plan de U1, Paso 11
"
**AI Response**: Aplicados los cuatro cosméticos listados. (U8-cos) logical-components §3: las cinco viñetas tachadas con su referencia, y el texto de la identidad reescrito como resuelto. (U2-g) NFR-U2-21 sin «Pendiente de NFR Design» (remite a P-U2-01) y con `/api/promotion/**` entre las rutas fail-open, también en la fila SECURITY-15; diagrama y texto con el controlador en `envoy-gateway-system`. (U1-k) `envoy-gateway-system` en INF-U1-06 (F95, K14), en deployment-architecture §2 y en la wave 0. (U1-p) paréntesis del Paso 11. El mensaje anuncia cinco cosméticos y dos puntos de diseño para el plan de Code Generation de U8, pero solo lista cuatro cosméticos; se pidió al usuario el que falta y los dos puntos de diseño.
**Context**: CONSTRUCTION - U8 - Infrastructure Design, esperando aprobación.

---
## U8 Infrastructure Design (gate abierto) — Request Changes: quinta revisión
**Timestamp**: 2026-10-08T03:54:29Z
**User Input**: "Cosmético abierto

#    Qué    Dónde
U1-p    Falta un paréntesis de apertura en la frase (count(...) or vector(0)) < 6``. La regla de INF-U1-02 está bien escrita.    Plan de U1, Paso 11
"
**AI Response**: El paréntesis de apertura ya estaba en el archivo desde la revisión anterior (`(count(...) or vector(0)) < 6`). Para que no se lea como desbalanceado, se quitaron los paréntesis externos que envolvían la expresión y la cita: «de la forma `(count(...) or vector(0)) < 6` según INF-U1-02».
**Context**: CONSTRUCTION - U8 - Infrastructure Design, esperando aprobación.

---
## U8 Infrastructure Design — Aprobación
**Timestamp**: 2026-10-08T03:55:19Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U8 aprobado. Inicia Code Generation Part 1 (plan de tareas) de U8; Part 2 fuera de alcance por instrucción del usuario.
**Context**: CONSTRUCTION - U8 - Infrastructure Design aprobado; siguiente: plan de tareas.

---
## U8 Code Generation Part 1 — Plan de tareas generado (solicitud de aprobación)
**Timestamp**: 2026-10-08T03:59:42Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Plan de tareas en `construction/plans/case-management-code-generation-plan.md`: 26 pasos en 9 bloques (estructura y configuración; migraciones de `case-db` con roles, `guard_transition`, `guard_vencido` y RLS; lógica pura con PBT-U8-02..04 y mutación; `case-service` con intake, evidencia, barridos, core y API; `case-worker` con clientes, cola y evaluación con PBT-U8-01 y 05; CLI de retención y mock; despliegue con chart, alertas, documentación y Applications; verificación en kind con aprobación humana; cierre). Trazabilidad generada por script: las 8 historias propias más US-109 y US-609, BR-U8-01..22 y 13b, NFR-U8-01..53, P-U8-01..10, INF-U8-01..08 y PBT-U8-01..08 cubiertos. Los dos puntos de diseño anunciados por el usuario en la cuarta revisión no llegaron; se pide incorporarlos en la revisión del plan. Prompt de aprobación: «Request Changes / Approve plan».
**Context**: CONSTRUCTION - U8 - Code Generation Part 1, esperando aprobación.

---
## U8 Code Generation Part 1 — Request Changes: dos puntos de diseño
**Timestamp**: 2026-10-08T04:04:30Z
**User Input**: "Los dos puntos de diseño pendientes siguen sin resolverse en el plan.

Con efecto (2)

Guarda de intento, Paso 15 (y Pasos 3 y 11).
Problema: el Paso 15 aplica el resultado con UPDATE … AND attempts = :attempt. :attempt sale de evaluation_jobs.attempt (1 a 6), pero cases.attempts vale 0 antes del primer intento. Los Pasos 11 y 3 también ponen attempts = 0 al reintentar. Con esa guarda, el primer resultado podría descartarse como evaluation.result_discarded.
Segundo riesgo: la prueba de E5 (worker detenido, otro lo retoma tras 30 s, el resultado tardío del primero se descarta) solo pasa si cada toma cambia el valor comparado. Si el reintento tras vencer el arrendamiento no incrementa attempt, el resultado tardío pasaría la guarda.
Corrección propuesta: en la transacción de toma (job_queue), fijar cases.attempts = evaluation_jobs.attempt y que toda toma, incluida la que sigue a un arrendamiento vencido, incremente attempt. La guarda queda attempts = :attempt, como dice NFR-U8-11.
Prueba que falta en el Paso 15: primer intento exitoso → listo; resultado tardío tras la retoma → descartado.
Quién decide: esta corrección toca el diseño (P-U8-01/NFR-U8-11), así que decides tú cuál adoptar.
INSERT de case_worker en evidence_outbox, Pasos 3, 10 y 15.
Problema: case_worker no tiene SELECT sobre esa tabla. Su INSERT no puede usar RETURNING. ON CONFLICT DO UPDATE tampoco, y DO NOTHING hay que probarlo. Con la llave UUIDv5(case_id, "fail_closed", ciclo), un reintento tras un commit incierto puede chocar con la llave única.
Corrección propuesta: el INSERT sin RETURNING ni ON CONFLICT, con unique_violation tratado como éxito.
Prueba que falta en el Paso 3 o 15: repetir el INSERT con la misma llave con el rol real → no falla el escalamiento.
"
**AI Response**: Se adoptaron las dos correcciones propuestas. (1) Cada toma, incluida la retoma tras un arrendamiento vencido, incrementa `evaluation_jobs.attempt` (los trabajos nuevos nacen en 0) y lo copia a `cases.attempts`; la guarda compara con el número de esa toma; la reprogramación solo fija `run_at` y `last_cause`. Agregado que la propuesta no cubría: si la retoma llevaría el número a 7 (worker perdido en el intento 6), el caso escala en la misma transacción con `local_cause = scoring_unreachable`, sin llamar a scoring; así un caso que tumba al worker no se retoma para siempre. Actualizados BR-U8-07/08/09, domain-entities §2.1, business-logic-model §3.1, PBT-U8-01 (comandos `worker_lost` y `late_result`) y ejemplos, NFR-U8-11, P-U8-01 (SQL de la toma y verificaciones), business-rules §8. (2) `INSERT` simple de `case_worker` en un `SAVEPOINT`, en la misma transacción que el cambio de estado, sin `RETURNING` ni `ON CONFLICT`; `unique_violation` sobre la llave = éxito y vuelta al `SAVEPOINT` (sin el savepoint, el error abortaría la transacción del escalamiento). Actualizados BR-U8-09 e INF-U8-01. Plan: Paso 3 (repetición del INSERT con el rol real; RETURNING y ON CONFLICT DO UPDATE → error de permisos), Paso 11 (trabajos nuevos con attempt = 0) y Paso 15 (toma, guarda, escalamiento y cuatro pruebas nuevas).
**Context**: CONSTRUCTION - U8 - Code Generation Part 1, esperando aprobación.

---
## U8 Code Generation Part 1 — Request Changes: índice de evidence_outbox y CHECK de attempt
**Timestamp**: 2026-10-08T04:12:47Z
**User Input**: "Hallazgo nuevo con efecto: falta el índice único de evidence_outbox

Qué falta: BR-U8-09 e INF-U8-01 dicen que un unique_violation sobre la llave de idempotencia se trata como éxito. El Paso 3 lo prueba. Pero domain-entities §3.1 define evidence_outbox.idempotency_key sin ninguna restricción de unicidad, y el Paso 3 solo menciona dos índices (el del trabajo vivo y el de explanation_views). Sin ese índice, el INSERT repetido no lanza nada y la prueba no pasa.
Por qué no basta un UNIQUE simple: tras el abandono de una decisión, la decisión nueva usa la misma llave UUIDv5(case_id, "human_decision") en una fila nueva (BR-U8-18). Un UNIQUE simple la rechazaría. Hace falta un índice único parcial, WHERE state <> 'abandonada', con la misma lógica del índice de decisions.
Dónde corregir: domain-entities §3.1 y el Paso 3. Agregar en el Paso 3 una prueba de que una decisión nueva tras un abandono inserta su fila sin chocar.

Aclaración menor, también en domain-entities §2.1 y el Paso 15

Qué falta: domain-entities dice attempt 0..6, pero la SQL de P-U8-01 escribe attempt + 1 y recién después pregunta por 7. Si la tabla lleva un CHECK de 0 a 6, esa escritura falla justo en el caso que debe escalar.
Corrección: que la toma lea attempt antes y escale sin incrementar cuando vale 6.
"
**AI Response**: Aplicados los dos. (1) Índice único parcial `UNIQUE (idempotency_key) WHERE state <> 'abandonada'` en domain-entities §3.1 y el Paso 3, con la prueba pedida (decisión nueva tras un abandono inserta sin chocar; una segunda fila viva choca). Consecuencia detectada al aplicarlo: en el conflicto tras un abandono (BR-U8-18), confirmar la anterior mientras la nueva sigue viva violaría los índices parciales de `decisions` y de `evidence_outbox`, que se comprueban por sentencia; BR-U8-18 fija ahora el orden en una transacción (la nueva a `abandonada`, después la anterior a `confirmada`), con prueba de los dos órdenes en el Paso 3. El Paso 3 también lista el índice parcial de `decisions`, que faltaba. (2) `CHECK (attempt BETWEEN 0 AND 6)`; la toma decide con el valor leído y, con 6, escala sin incrementar: BR-U8-07, domain-entities §2.1, P-U8-01 (SQL), business-logic-model §3.1 y PBT-U8-01, Pasos 3 y 15. Fila nueva en business-rules §8.
**Context**: CONSTRUCTION - U8 - Code Generation Part 1, esperando aprobación.

---
## U8 Code Generation Part 1 — Aprobación
**Timestamp**: 2026-10-08T04:15:32Z
**User Input**: "Approve plan"
**AI Response**: Plan de tareas de U8 aprobado. U8 queda cerrada (Code Generation Part 2 y Build and Test fuera de alcance). Siguiente: U9 bias-monitoring — Functional Design.
**Context**: CONSTRUCTION - U8 cerrada; inicia U9 Functional Design.

---
## U9 Functional Design — Plan y preguntas
**Timestamp**: 2026-10-08T04:19:26Z
**User Input**: (sin entrada nueva; continúa tras "Approve plan" de U8)
**AI Response**: Creado `construction/plans/bias-monitoring-functional-design-plan.md` con 12 preguntas: definición de la disparidad (Q1), decisiones humanas (Q2), muestra mínima y ruido estadístico (Q3), ventana, frecuencia y W (Q4), recomendaciones entregadas (Q5), regla y fallos de congelamiento (Q6), paquete de contexto (Q7), dónde quedan los resultados (Q8), monitoreo detenido y `bias_monitoring_age_s` (Q9), origen del «después» de `compare_source` (Q10), API del dashboard (Q11) y errores de una corrida (Q12). Hallazgos en otras unidades anotados: P-U7-03 frente a lo que el registro marca como entregado; `bias_monitoring_age_s` sin productor posible por X04; BR-U4-13 cita F27 en lugar de F25.
**Context**: CONSTRUCTION - U9 - Functional Design, esperando respuestas.

---
## U9 Functional Design — Respuestas y aclaraciones
**Timestamp**: 2026-10-08T04:23:13Z
**User Input**: "ya respondí"
**AI Response**: Respuestas leídas: Q1, Q2, Q5, Q6, Q7, Q9, Q11 = A; Q3 = A con regla de congelamiento por la agregada ponderada (> 5 pp y límite inferior del intervalo combinado > 0); Q4 = A con lectura de conteos agregados por día; Q8 = A con dos precisiones (agregado también para el «antes» y `get_disparity`; Pushgateway sin valores de celdas insuficientes y flujo nuevo); Q10 = A con tablas de conteo por atributo; Q12 = X (las inválidas se excluyen y alertan; la corrida falla solo por encima del 1 %). Conflictos detectados: el agregado de Q4 no cabe en el pool `projections` de U3 (1 conexión, 2 s); Q5 (una por caso) necesita que el agregador aplique la regla; el «antes» de Q7 con granularidad diaria; los `seq` de Q12 no llegan con conteos. Creado `construction/plans/bias-monitoring-functional-design-clarification-questions.md` con 4 preguntas.
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aclaraciones.

---
## U9 Functional Design — Aclaraciones respondidas y artefactos generados
**Timestamp**: 2026-10-08T04:31:52Z
**User Input**: "ya respondí"
**AI Response**: Aclaraciones: CQ1 = A con rol propio del agregador limitado a las tablas derivadas; CQ2 = A con desempate por `seq` y etiquetas de la recomendación referenciada; CQ3 = A más la agregada de los últimos 7 días; CQ4 = A con tope de 100 `seq` y el 1 % sobre válidas más inválidas. Generados `construction/bias-monitoring/functional-design/` business-rules.md (BR-U9-01..22), domain-entities.md y business-logic-model.md (PBT-U9-01..08, ejemplos y validación estadística). Agregados por criterio propio: la corrida falla si el agregador de U3 está atrasado más de 30 min (alerta `MonitoringAggregatorStale` en U3); la versión candidata de una fuente (`source_candidate_for`) en U4, porque BR-U4-13 rechazaba registrar una versión con una fuente no aprobada; limitación documentada del intervalo, que no corrige la elección del par extremo. Cambios a otras unidades: U3 (BR-U3-02, nueva BR-U3-17, rol `registry_aggregator`, proyecciones `monitoring_daily` y `monitoring_freezes`, retiro de `monitoring` por filas, PBT-U3-09, alerta, plan Pasos 2, 5, 8, 12, 13 y 14); U0 (`ServingConfig` sin `bias_monitoring_age_s`; `context_package` del `freeze`); U4 (BR-U4-13, 15, 16, domain-entities §5 y `source_candidate_for`, PBT-U4-05, alertas, plan Pasos 5, 10 y 13); inventario (F25, F26, F27, F106, F107, namespaces, texto alternativo), `component-methods` C11, `services` S4 y S5, `unit-of-work` U3 y U9; pendientes de U9 resueltos en U7 y U8.
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: revisión consolidada
**Timestamp**: 2026-10-08T04:42:43Z
**User Input**: "Esta es la lista consolidada de lo que sigue abierto después de revisar U0, U3, U4, U7, U8, U9 y el inventario. No modifiqué ningún archivo tuyo.

Con efecto

H1. Un modelo reactivado se vuelve a congelar casi de inmediato (U9, U3).

Tras frozen_resolution = reactivar, la ventana de 30 días conserva los datos sesgados y la siguiente corrida (≤ 15 min) vuelve a superar 5 pp. Además el barrido de U8 (BR-U8-10) devuelve los casos a en_evaluacion cada 5 min, así que los casos oscilan.
Corrección: la ventana de la versión empieza en el máximo entre la activación y el día siguiente a la última reactivación. La proyección monitoring_freezes de U3 debe incluir las frozen_resolution (acción y fecha). Agregar «reactivar» a PBT-U9-05 y un ejemplo.

H2. monitoring_daily guarda la combinación de las cuatro etiquetas (U9 domain-entities §1.1, U3).

Son unas 6 800 filas por día y versión solo para el modelo, y unas 250 mil por corrida. El límite de 2 s del pool projections no se sostiene, y la combinación contradice la razón de Q10 (reidentificación).
Corrección: marginales por atributo (atributo, grupo, banda, resultado, día), unas 200 filas por día.

H3. Las métricas de Pushgateway no alcanzan para las alertas (BR-U9-20, BLM §2.1).

vectra_bias_run_failures_total es un contador empujado por un proceso que muere en cada corrida, así que nunca acumula. Debe ser un gauge.
El diagrama termina la corrida fallida sin publicar nada, pero BiasFreezeFailed y BiasInvalidEntries dependen de esa publicación.
Un PUT borra last_success_timestamp y dispara absent(). Hay que fijar POST o llaves de grupo separadas.
Las series de versiones que ya no se evalúan quedan viejas.
DisparidadDecisionHumana necesita el límite inferior o un booleano, y hoy no se publica.

H4. La tabla §9 de BR-U9 omite cambios en otras unidades.

U2/U0: el CronJob necesita su propio cliente (governance:freeze, registry:read:monitoring). Hoy el servicio HTTP también podría congelar. Hay que decidir también el actor.id (BR-U3-16, guard_freeze, BR-U4-01 y BR-U4-04).
U0 §9: faltan DisparityView, FreezeSummary, PrePostReport, CompareSourceRequest y MonitoringWindow. BR-U0-93 dice que los contratos viven solo en U0.
U1: el ingreso al Pushgateway para F106 solo admite a restore-drill.

H5. El atraso del agregador no está definido (U3 BR-U3-17).

«Más de 30 min respecto de la cabeza» no precisa la medida. Un registro sin tráfico nocturno haría fallar todas las corridas de bias.
Corrección: hay entradas con seq mayor que la marca y la más antigua tiene recorded_at de hace más de 30 min. Con la marca igual a la cabeza, el atraso es 0.

H6. Las tablas derivadas de U3 no tienen esquema.

Faltan columnas, llaves, CHECK (count >= 0), retención (≥ 90 días) y quién reconstruye desde seq = 0 (el rol tiene DELETE, no TRUNCATE). Este es el lugar para aplicar H2.

H7. source_comparison no está cerrado (U4).

No queda dicho cómo se puntúa la versión activa desde staging (F30 y X08).
F32 y ValidationRun no tienen modo ni source_id, y el vencimiento a las 2 h aplicaría validacion_fallida a la versión.
pre_post_report_ref apunta a algo que ninguna entidad guarda.
No hay flujo ni ejemplos de US-306 en el business-logic-model.
Menores
H8. Pesos de BR-U9-04: falta decir si la suma de n_b es solo sobre bandas con diferencia y si no_informado cuenta en n_b.
H9. PBT-U9-02: «multiplicar por k deja los valores iguales» es falso si una celda cruza n_min.
H10. Tamaño de FreezeContext (unos 40 KB estimados) frente a los 64 KiB de BR-U3-07. Si lo excede, el registro responde 413 y FreezeEventPending se queda reintentando. Falta una regla: aplicar el congelamiento y reducir el paquete (máximo 48 KiB) y una prueba con los catálogos completos.
H11. initial_disparity (U4 domain-entities §2.2) debe ser el resultado de la librería de U9 (AttributeResult por atributo, con n_min, agregada e intervalo).
H12. BLM de U3 sin flujo del agregador ni ejemplos de PBT-10. Falta SELECT … FOR UPDATE sobre la fila de monitoring_watermark. Casos borde: una recomendación inválida como la más reciente, qué cuenta total_entries y una recomendación posterior a la decisión.
Cosméticos
U3:
La tabla de proyecciones de domain-entities §3 está rota por una línea en blanco.
La fila monitoring debe marcarse «retirada».
El plan de U3 sigue con BR-U3-01..16 y PBT-U3-01..08 en §1 y §3 (faltan BR-U3-17 y PBT-U3-09).
En el Paso 12, el segundo path de pytest no lleva el prefijo decision-registry/.
U4:
P-U4-07 todavía dice «edad del monitoreo».
La primera fila de BR §10 lista bias_monitoring_age_s.
El BLM §2.2 no menciona lo que agrega governance.
El plan §1 dice BR-U4-01..17 (se usan hasta la 19).
Inventario y unit-of-work:
component-dependency §4 no lista registry_aggregator.
component-methods C10 no muestra el modo source_comparison.
unit-of-work omite el agregador en el contenido y los roles de U3.
U7 y U8:
El punto 5 de P-U7-03 cita la proyección monitoring (retirada).
La fila «U3 §3 monitoring» de U8 §8 tiene el mismo problema.
En BR-U8-07, la reprogramación debería fijar locked_until = NULL.
U9: la ventana por días UTC no dice si incluye el día parcial de t−30 d.
"
**AI Response**: Aplicados todos los hallazgos. Decisiones tomadas: (H4) el CronJob usa un cliente nuevo `bias-monitoring-job` con `governance:freeze` y `registry:read:monitoring`; el servicio HTTP queda solo con `registry:read:monitoring`; actor del `freeze` = `{kind: system, id: bias-monitoring-job}` (U9 BR-U9-12, U3 BR-U3-16, U4 BR-U4-01/04 y `guard_freeze`, U0 §7.2, U2 §2.2 y plan Pasos 2, 3 y 14, inventario F27). (H7) la versión activa se despliega también en KServe de staging (X08) y el Job usa F30 para las dos; `ValidationRun` con `mode`, `source_id` y `baseline_version_id`; timeout en ese modo sin cambios de estado; F32 con `PUT /v1/validation-runs/{run_id}/source-counts`; `DataSource.pre_post_report` guardado; flujo §2.5 y ejemplos en el BLM de U4. Resto: (H1) inicio de la ventana = máx(primer día con datos, día siguiente a la última reactivación); `monitoring_freezes` con `frozen_resolution`; PBT-U9-05 y ejemplo. (H2) marginales por atributo en U9 y U3. (H3) gauges en dos grupos de Pushgateway (`success` solo en corridas completas; `run` siempre, con PUT que retira series viejas), `rule_met`, `aggregate_lower`, `freeze_failed`; el diagrama publica también en la corrida fallida. (H4) U0 §9.4 con los contratos de U9; U1 Pushgateway admite F106. (H5) atraso definido por la entrada más antigua pendiente. (H6) esquema de las cinco tablas derivadas (se agrega `monitoring_entry_totals`), retención de 180 días y reconstrucción con `registry_migrator`. (H8) pesos sin `no_informado` y solo bandas con diferencia. (H9) PBT-U9-02 acotada. (H10) paquete ≤ 48 KiB con recorte ordenado y `truncated`; governance recorta `initial_disparity` sobre 60 KiB. (H11) `initial_disparity` con el formato de la librería. (H12) flujo del agregador, `FOR UPDATE` y ejemplos en el BLM de U3. Cosméticos de U3, U4, inventario, unit-of-work, U7, U8 y U9 aplicados (incluido `locked_until = NULL` en la reprogramación de BR-U8-07 y del plan de U8).
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos de U4 y U3
**Timestamp**: 2026-10-08T05:06:39Z
**User Input**: "Hallazgos abiertos (consolidado)

Todos son de redacción o de cobertura en los documentos. Ninguno cambia el diseño de fondo.

U4 governance (9)
Falta el endpoint para lanzar la comparación. start_source_comparison aparece en BLM §2.5, pero ningún documento define quién lo ejecuta, con qué MFA ni con qué estado de la candidata. Tampoco hay endpoint con scope para PUT …/source-counts (F32). Propuesta: ingeniero con MFA, como start_validation.
Barrido de 60 s de P-U4-02. Sigue aplicando validacion_fallida a todo ValidationRun vencido, mientras BR-U4-05 dice que source_comparison solo pasa a timeout. Los dos textos se contradicen.
Casos límite de la versión activa.
No se define qué pasa si no hay versión activo (propongo 409) o si está congelado.
Nadie dice cómo ni quién despliega la versión activa en KServe de staging. Ni deployment-architecture ni INF-U4 lo recogen, y su InferenceService extra no figura en las cuotas de vectra-staging.
Tope de 64 KiB del evento freeze. Sin respaldo final, un evento que aún lo supere da 413 y FreezeEventPending reintenta sin fin. La regla de 60 KiB está en BLM §2.2 y U9, pero no en BR-U4-15. Propuesta: último recurso, reducir data_sources a sus ids.
Pruebas que faltan (del BLM ya salieron las de timeout y US-306): endpoint source-counts, migración de ValidationRun.mode y evento mayor de 60 KiB.
logical-components de U4 desactualizado. Dice "bias-monitoring → freeze" (ahora es el CronJob bias-monitoring-job) y cita compare_source (F27) cuando es F25.
NFR-U4-12 solo cubre validacion. El modo source_comparison puntúa el dataset con dos modelos, y su límite de 2 CPU / 4 GiB y el plazo de 2 h no están medidos.
BR-U4-01 y PBT-U4-01 sin la candidata (cosmético). La tabla de transiciones no incluye la condición source_candidate_for. Solo existe el ejemplo de 409.
pre_post_report_ref contra U0. BR-U4-13 dice que el evento lleva el PrePostReport completo (≤ 48 KiB), pero U0 §5.2 define pre_post_report_ref. Está listado en U0 más abajo.
U3 decision-registry (8)
Lectura de las tablas derivadas. Ningún rol de lectura tiene SELECT explícito sobre ellas: registry_app solo ve registry_entries y registry_verifier figura como "Solo SELECT". La proyección sale del pool projections con registry_verifier, así que basta aclarar esa concesión. Tampoco se define de dónde sale la métrica de atraso de MonitoringAggregatorStale (gauge del servicio o Pushgateway, que no tiene flujo para eso).
BR-U3-17 sin iteración de lotes. Con 5 000 entradas por corrida cada 5 min, reconstruir ~650k entradas tarda unas 11 h. Propongo iterar hasta alcanzar la cabeza o activeDeadlineSeconds.
monitoring_case_index guarda las 4 etiquetas junto a case_id. Contradice "nunca se guarda la combinación". Propongo guardar counted_seq, day y versión, y releer las etiquetas de registry_entries, o reformular la regla.
Ejemplos que faltan en BLM §3: monitoring_freezes con reactivar, purga de 180 días y tamaño o paginación de F26.
Reset y la fila id = 1. "Vacía las cinco tablas y pone last_seq = 0": si vacía la marca, el FOR UPDATE no encuentra fila. Debe decir "vacía las cuatro y deja id = 1 con last_seq = 0".
El registry-aggregator no aparece en los documentos de NFR e infraestructura de U3. Falta en logical-components, deployment-architecture, INF-U3-03 (recursos, deadline, sidecar de Linkerd, PriorityClass), INF-U3-04 (conexiones), INF-U3-05 (rol registry_aggregator), INF-U3-06 (F107; el rango F01–F99 sigue desactualizado), P-U3-08, P-U3-09 (MonitoringAggregatorStale) y NFR-U3-42, además de requisitos de rendimiento y almacenamiento de las tablas derivadas.
F26 contra el pool projections. Tiene 1 conexión con espera de 2 s para todas las proyecciones, y monitoring_daily devuelve unas 24–30k filas por consulta. Puede bloquear a explanation. Propongo paginar, agregar en el servidor o darle su propio pool dentro de las 5 conexiones por réplica.
Cosmético: llave idempotente del checkpoint. P-U3-03 usa checkpoint:<hora UTC>, pero la columna es uuid. Propongo UUIDv5.
"
**AI Response**: Aplicados los 17 hallazgos. U4: `start_source_comparison` (`POST /v1/data-sources/{id}/comparisons`, `ingeniero_riesgo` con MFA) con sus condiciones y 409 `no_active_version` / `active_version_frozen`; `PUT …/source-counts` con scope `governance:validation-report`, solo en runs `source_comparison` `lanzado`; barrido de P-U4-02 por modo; INF-U4-05 (predictor de staging de la versión activa por PR y sync manual, aporte a la cuota de `vectra-staging`) y deployment-architecture; BR-U4-15 con la escalera de tamaño (60 KiB → agregadas; 64 KiB → `data_sources` por ids); pruebas en el plan (endpoint, migración de `mode`, evento > 60 KiB, comparación sin activo); logical-components (F25, `bias-monitoring-job`); NFR-U4-12 con el modo `source_comparison` (≤ 60 min); BR-U4-01 y PBT-U4-01 con `source_candidate_for`; `CHECK` de `ValidationRun`; U0 `data_source_event.pre_post_report`; `component-methods` (BFF y governance). U3: `SELECT` explícito de `registry_verifier` sobre las tablas derivadas salvo el índice por caso; gauge `vectra_registry_monitoring_lag_seconds` del servicio y alerta con su expresión; iteración de lotes hasta la cabeza o 240 s; `monitoring_case_index` sin etiquetas (se releen por `counted_seq`); reset que deja la fila `id = 1`; ejemplos (reactivar, purga, tamaño); agregador en logical-components, deployment-architecture, INF-U3-03/04/05/06, P-U3-08/09, NFR-U3-42 y nuevos NFR-U3-24 (rendimiento) y NFR-U3-35 (almacenamiento); F26 con agregación en el servidor por rango (hasta 12 rangos, propagado a U9 domain-entities, U0 §9.4 y el plan de U3); llave del checkpoint como UUIDv5. El mensaje menciona hallazgos de U0 «más abajo» que no llegaron; solo se aplicó el de `pre_post_report_ref`.
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10
**Timestamp**: 2026-10-10T09:12:17Z
**User Input**: "Hallazgos consolidados (2026-10-10)

No hay archivos nuevos desde la última revisión, así que la lista es la misma. Ningún archivo subido fue modificado.

U9 bias-monitoring (FD: domain-entities, BLM, business-rules)
resolved_at contra recorded_at. El FD de U9 §1.3 usa resolved_at, y U0 §9.4 y U3 usan recorded_at. BR-U9-08 no dice qué fecha fija el “día siguiente”. Hay que unificar en recorded_at, en fecha UTC.
Desfase de un día en el BLM §2.1. Dice “t-30d a t” y “antes t-37d..t-7d”. BR-U9-08 y BR-U9-15 dicen hoy−29..hoy y hoy−36..hoy−7.
Rangos por versión.
El texto dice “3 por versión”, pero cada versión necesita 3 de modelo y 1 de decisión humana, o sea 4. Con 12 caben 3 versiones.
No se define qué pasa con una cuarta versión (por ejemplo, tras un rollback). Propongo solicitudes de ≤12 rangos, nunca omitir una versión, y una prueba.
PrePostReport sin regla de recorte. U0 §5.2 remite a BR-U9-15, que solo cubre FreezeContext. Faltan el tope de 48 KiB, el orden de recorte y truncated en BR-U9-17 y §3.2.
Falla del Pushgateway sin definir. Propongo registrar el error, terminar con código distinto de cero y no afectar el congelamiento.
Cosméticos.
BR-U9-18 usa “la más reciente con datos” y lo aprobado es “la activa”.
BR-U9 §9 lista 3 tablas y son 5.
BR-U9-16 omite el segundo paso de BR-U4-15 (más de 64 KiB reduce data_sources a ids).
§9 no tiene fila para la segunda revisión.
U4 governance (plan y documentos)
Falta la prueba del timeout de source_comparison (Pasos 8 y 10), y el barrido distinguido por modo.
Falta el escenario de US-306 en kind y el tope de 60 min en el Paso 20.
INF-U4-05 sigue ausente de la cabecera, del Paso 16 y de la trazabilidad (todo dice 01..04). Falta también el conftest de los valores del staging.
Falta BR-U4-15 en la línea “Diseño” del Paso 10. No hay prueba de que el data_source_event de aprobada y rechazada lleve pre_post_report (≤48 KiB).
La dependencia vectra_disparity de validation_job no está en el Paso 1 ni en unit-of-work.
component-methods C09 freeze_model dice “solo identidad bias-monitoring” y debe decir bias-monitoring-job.
U3 decision-registry
NFR-U3-24 y NFR-U3-35 sin paso ni trazabilidad en el plan.
Faltan la reconstrucción en ≤1 h, el atraso p95 ≤10 min, los 12 rangos p95 ≤200 ms y los tamaños de las tablas.
NFR-U3-24 habla de 1 año y ~3,6 M entradas, y BR-U3-17 de 180 días y ~650 000. Hay que alinearlos antes.
Paso 2 del plan. Tiene la frase del registry_aggregator mezclada con la del UUIDv5.
Paso 12 del plan. Su línea “Diseño” no cita BR-U3-17, PBT-U3-09 ni NFR-U3-24, 35 y 42. Su aceptación omite la purga a los 181 y 179 días y monitoring_freezes con reactivar.
Paso 8 del plan. No prueba el gauge del atraso (0 con la marca igual a la cabeza y el registro inactivo), ni resolution.recorded_at, ni versions.
F60. No consta que sea un flujo de scrape del servicio.
domain-entities §3. Debe alinearse con U0: first_day y last_day, y totals por rango.
NFR-U3-35. case_index dice “<2 M filas” frente a unos 360 000 estimados.
Cosméticos. “180 días por day” en §1.3 cuando case_index no tiene day, y falta la fila de MonitoringAggregatorStale en BLM §4.
U2
La regla “governance:freeze solo para bias-monitoring-job” falta en realm-lint, PBT-U2-03 y BR-U2 §8. BR-U2 §8 tampoco recoge case-worker ni bias-monitoring-job.
U1
P-U1-09 no clasifica el CronJob de bias.
El sidecar nativo de Linkerd debe ser obligatorio en todo CronJob mallado de vectra-app.
P-U1-01 dice F01–F105 y ahora es F01–F107.
El Pushgateway no figura en el tech-stack y no tiene alerta propia (PushgatewayDown).
U0
BR-U0-93 sigue sin verificar (regla de 60 KiB).
"
**AI Response**: Aplicados todos los hallazgos. U9: reactivación por `recorded_at` en fecha UTC (§1.3, BR-U9-08, ejemplo); BLM §2.1 con hoy−29..hoy, hoy−36..hoy−7 y hoy−6..hoy; 4 rangos por versión y varias solicitudes de ≤ 12 sin omitir versiones (con prueba de 4 versiones); recorte del `PrePostReport` a 48 KiB con `truncated` (BR-U9-17, §3.2, U0 §9.4); Pushgateway caído (log, salida distinta de cero, el `freeze` no depende); versión activa por omisión enviada por el BFF (F11), con respaldo en la más reciente; §9 con las cinco tablas, el segundo paso de BR-U4-15 y filas de la segunda y tercera revisión. U4: barrido por modo y timeout de `source_comparison` probados (Pasos 8 y 10); US-306 en kind con el tope de 60 min (Paso 20); INF-U4-05 en la cabecera, el Paso 16 (con `conftest` de los values de staging) y la trazabilidad; BR-U4-15 en el Paso 10 y prueba del `pre_post_report` en `data_source_event`; dependencia `vectra_disparity` en el Paso 1 y en unit-of-work; C09 `freeze_model` con `bias-monitoring-job`. U3: NFR-U3-24 y 35 en el Paso 17 y la trazabilidad (y en el 12); volúmenes alineados (188 días, ~1,9 M entradas con NFR-U3-30, reset con `last_seq` antes de la primera entrada de los últimos 188 días; `monitoring_case_index` ≈ 360 000); frase del Paso 2 separada; Paso 12 con su línea Diseño y la purga y `monitoring_freezes`; Paso 8 con el gauge, `resolution.recorded_at`, `versions` y el tope de 12 rangos; F60 documentado en INF-U3-06; domain-entities §3 alineado con U0; retención del índice por `evaluated_at`; fila de `MonitoringAggregatorStale` en el §4 del BLM. U2: `governance:freeze` solo en `bias-monitoring-job` en `realm-lint` y PBT-U2-03; BR-U2 §8 con `case-worker` y `bias-monitoring-job`. U1: CronJob de bias y `registry-aggregator` en `vectra-high` (P-U1-09); sidecar nativo obligatorio en todo Job/CronJob mallado con la política `require-native-sidecar-in-jobs` (P-U1-05, Paso 5); P-U1-01 con F01–F107; Pushgateway en tech-stack y alerta `PushgatewayDown`. U0: BR-U0-93 verificado: la forma y los topes de tamaño del `context_package` del `freeze` viven ahora en U0 §5.2 (antes remitían a U9), y `PrePostReport` lleva `truncated`.
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10 04:28
**Timestamp**: 2026-10-10T09:30:00Z
**User Input**: "Hallazgos consolidados (2026-10-10, 04:28)

Ningún archivo subido fue modificado. Esta versión incorpora la revisión de los 9 documentos de U3.

Riesgo (prioridad alta)
U1: require-native-sidecar-in-jobs puede bloquear a CloudNativePG.
La política exige la anotación en el pod template de todo Job de vectra-data. Los Jobs initdb, join y recovery los crea el operador y no la llevan, y la anotación del namespace no se hereda.
Con failurePolicy: Fail, Kyverno rechazaría el join que reclona la réplica tras un fallo de zona (NFR-U1-03).
Propuesta: que la política acepte la anotación del namespace, o que sea mutate.
Añadir un kyverno test con un Job cuyo ownerReference sea un Cluster. El escenario 4 del Paso 20 debe verificar que el reclonado crea su Job.
U9 bias-monitoring
BR-U9-18, versión por omisión. Dice “la activa”, pero tras un congelamiento ya no hay versión activo. Debe ser “la servible (activa o congelada)”.
FreezeSummary (§3.4). Falta resolution?, que U0 §9.4 sí tiene. Añadirlo también en BR-U9-19.
CompareSourceRequest (§3.2). U0 define list[CountTable] y U9 dict[atributo, CountTable]. BR-U9-17 además lo describe como “(grupo, banda, resultado) → conteo”, cuando CountTable guarda favorable y total.
Infrastructure Design de U9 (sin subir). Debe incluir backoffLimit: 0 del CronJob y el ExternalSecret de la clave privada de bias-monitoring-job.
Riesgos por documentar.
BiasInvalidEntries puede durar 30 días por una sola entrada inválida.
Periodo ciego tras reactivar.
El Pushgateway sin persistencia deja absent() hasta ~15 min tras un reinicio.
U0 contracts
§5.2 data_source_event. Remite a BR-U9-15 y debe remitir a BR-U9-17.
§9.4 MonitoringMarginalCount.result. Debe ser outcome | final_outcome.
§9.4 CompareSourceRequest. Alinear lista contra dict (ver U9). Recomiendo la lista de U0.
Pruebas de §9.4 (menor). Faltan pruebas de ejemplo o reglas de validación para:
La escalera de tamaño de freeze (48/60/64 KiB).
Hasta 12 rangos por solicitud.
total ≥ favorable en CountTable.
O bien declarar en el BLM que las aplican U9 y U3.
U3 decision-registry

Menores de antes (siguen abiertos):

BLM §2.5, decisión humana con recomendación inexistente. No hay versión que atribuir en totals[humana, v, día]. Definir la fuente, o una fila no atribuible.
BR-U3-17, 188 días. La justificación está invertida. Bastan ~181 días. El 188 es seguro, pero la explicación del margen no aplica.
BLM §2.5, purga. Menciona solo day. case_index se purga por evaluated_at.
BLM §3. Dice “12 rangos de 2 versiones” y deben ser 3.
INF-U3-04. Cuenta 6 Jobs y son 7.
Filas de humana.
Llegan hasta 396 por día y versión (22 grupos × 3 bandas × 2 resultados × 3 decisiones). La documentación dice ~200.
Con 3 versiones y 180 días, monitoring_daily supera las 250 000 filas de NFR-U3-35 (~324 000 con celdas densas).
"
**AI Response**: Aplicados todos. U1: la política pasa a ser de mutación (`add-native-sidecar-to-jobs`): agrega la anotación a todo Job/CronJob de un namespace mallado, incluidos los de CloudNativePG, y nunca rechaza; `kyverno test` con un Job `join` con `ownerReference` a un `Cluster`; escenario 4 del Paso 20 verifica que el reclonado crea su Job y llega a `Complete`. U9: versión por omisión = la servible (activa o congelada); `FreezeSummary.resolution` y `list_freezes`; `CompareSourceRequest` como `list[CountTable]` (lista de U0) y descripción de `CountTable` con `favorable`/`total`; nueva §8b de riesgos aceptados (alerta de inválidas de hasta 30 días, periodo ciego tras reactivar, Pushgateway sin persistencia) y pendientes del Infrastructure Design (`backoffLimit: 0`, `Forbid`, `ExternalSecret` de `bias-monitoring-job`); filas de `humana`. U0: `data_source_event` remite a BR-U9-17; `result: outcome | final_outcome`; `CompareSourceRequest` sin atributos repetidos; validación de estructura de §9.4 (≤ 12 rangos, `favorable ≤ total`, cuatro atributos) con pruebas en el Paso 3 del plan de U0, y la escalera de tamaño declarada como regla de U9 y U4. U3: decisión con recomendación inexistente como fila no atribuible (`model_version_id = '-'`); 181 días con la justificación corregida (el momento de negocio nunca es posterior a `recorded_at`) en BR-U3-17, BLM, NFR-U3-24 y plan; purga del índice por `evaluated_at`; 3 versiones en el ejemplo de 12 rangos; INF-U3-04 con 7 Jobs (≈ 47 conexiones); filas de `humana` (hasta 396) y NFR-U3-35 a < 350 000 filas.
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10 04:35
**Timestamp**: 2026-10-10T09:37:26Z
**User Input**: "Hallazgos consolidados (2026-10-10, 04:35)

Abiertos
Proyección de la fila no atribuible (U3 + U0 + U9)
La fila no atribuible no llega a U9.
La decisión humana sin recomendación referenciada queda con versión '-', pero totals se pide por rango y versión, así que no cae en ninguno.
Definir el campo en U3 §3 y en U0 §9.4 MonitoringWindow (por ejemplo unattributable_invalid), y reflejarlo en U9 §1.2 y BR-U9-09.
Verificar que la razón inválidas/total del 1 % (BR-U9-09, BR-U9-10) siga bien definida.
U9: falta una prueba de ejemplo del caso en el BLM.
U0 (menor): falta nombre para el tipo de la lista de ≤ 12 rangos.
U3 decision-registry
BLM §2.5, orden de pasos. totals[humana, v, día].total += 1 se ejecuta antes de leer la referenciada, cuando v aún no se conoce. En la rama “no existe” se suma otra vez en '-'. Mover el += 1 dentro de cada rama.
PBT-U3-09. Los generadores no incluyen “decisión que referencia una recomendación inexistente”.
BR-U3-17, cosméticos.
Dice *_at ≤ occurred_at ≤ recorded_at, pero occurred_at puede superar a recorded_at hasta 5 min (el día extra lo cubre; decirlo).
“Unos cientos de filas” cuando con 3 versiones son ~3 000.
“Unas pocas corridas” cuando son ~12.
NFR-U3-24, verificación. Sigue “Benchmark en CI con Testcontainers” para el rebuild de 1,8 M entradas. Separar CI escalado de kind.
Memoria del agregador (INF-U3-03). 512 MiB de límite con lotes de 5 000 entradas de ~20 KB. Medir y ajustar. Además, leer canonical solo de recommendation y human_decision.
Índice por recorded_at. Lo necesita el reset del agregador y no existe (domain-entities §1 y plan Paso 2).
CLI. El BLM cli y el plan (Paso 11) listan verify, checkpoint, archive y aggregator reset. Falta aggregator run, el comando del CronJob.
deployment-architecture §3. Sin escenario del agregador (suspendido más de 30 min, rebuild con el runbook monitoring-rebuild).
Plan de U3.
Paso 17: la aceptación bench ≤ 30 s mezcla el rebuild y el atraso.
Paso 18: falta escenario del agregador en kind.
Falta la prueba de decisión con recomendación inexistente.
Falta la prueba de purga de case_index por evaluated_at.
Falta la medición de memoria.
Paso 14: “las 11 alertas de P-U3-09 y MonitoringAggregatorStale” cuenta dos veces esa alerta.
F60. Confirmar en component-dependency que es el scrape del registro (INF-U3-06 lo declara).
U1 platform-foundation
P-U1-09. No lista el predictor de staging de INF-U4-05 en vectra-low.
Trazabilidad. NFR-U1-25 no cita add-native-sidecar-to-jobs, NFR-U1-32 no cita PushgatewayDown, y la línea “Diseño” del Paso 5 no cita P-U1-05.
Plan.
Cabecera y Paso 3 siguen en F01–F105.
Paso 10 con Pushgateway “(F87/F88)” sin F106.
Paso 6 sin el predictor de staging en las cuotas.
Hay que añadir F106 y F107 a flows.yaml.
Cosméticos.
Mermaid de logical-components y deployment-architecture sin F106, y el texto de la ola 5 omite el CronJob de bias.
INF-U1-02 no menciona la conexión de F107.
Argo CD. Dejar escrito que los charts llevan la anotación del sidecar explícita, para que la mutación sea una red de seguridad y no genere deriva.
U9 bias-monitoring
Sin subir: NFR, Infrastructure Design y plan. Deben cumplir §8b: backoffLimit: 0, Forbid, vectra-high, sidecar nativo y ExternalSecret de la clave privada de bias-monitoring-job.
U4 governance
US-306. Falta en la tabla de trazabilidad (§3) y en la cabecera de historias del plan. Solo aparece en el Paso 20.
Rutas. unit-of-work §3.1 usa validation-job/ y promotion-tool/, y el plan validation_job/ y promotion_tool/.
U2 identity-edge
BLM §3. Faltan pruebas de ejemplo de governance:freeze: realm-lint rechaza ese scope en otro cliente, y contra el realm exportado solo bias-monitoring-job lo obtiene.
Plan. BR-U9 §9 dice que se actualizó (Pasos 2 y 14), pero no está subido.
component-methods
C03 get_disparity. No dice que el BFF consulta governance (F11) y envía la versión.
C12. No lista GET /v1/monitoring/daily ni /monitoring/freezes, y sigue nombrando a bias como consumidor de GET /v1/entries.
Inventario y cosméticos
component-dependency §7 (arista BM→GOV, que ahora es el CronJob) y §4 (registry_migrator “no se usa en runtime” contra el reset).
services.md S9.
"
**AI Response**: Aplicados todos. Fila no atribuible: campo `unattributable_invalid` por rango en U3 domain-entities §3, U0 §9.4 `MonitoringWindow` y U9 §1.2; BR-U9-09 define la razón de la corrida (no atribuibles en numerador y denominador); ejemplo en el BLM de U9; tipo `MonitoringQuery` en U0. U3: orden del BLM §2.5 corregido (el total se suma una vez, ya con la versión); generador de PBT-U3-09 con decisiones sin recomendación; BR-U3-17 con la tolerancia de 5 min de `occurred_at`, ~3 000 filas por solicitud y ~12 corridas; lectura de solo los campos usados y lote configurable; NFR-U3-24 con verificación separada en CI escalado y kind; INF-U3-03 con la estimación de memoria; índice por `recorded_at` (domain-entities §1 y Paso 2); `aggregator run` en el BLM y el Paso 11; deployment-architecture §3 con agregador suspendido y reconstrucción; plan con Paso 17 separado por benchmark (incluida la memoria), Paso 18 con el escenario del agregador, pruebas de la decisión sin recomendación y de la purga del índice, Paso 14 sin doble conteo; F60 confirmado en `component-dependency`. U1: predictor de staging en `vectra-low`; NFR-U1-25 con la mutación y NFR-U1-32 con `PushgatewayDown`; Paso 5 cita P-U1-05; cabecera y Paso 3 con F01–F107 (F106 y F107 en `flows.yaml`); Paso 10 con F106; Paso 6 con la cuota de `vectra-staging`; Mermaid y texto de la ola 5 con el CronJob de bias; INF-U1-02 con la conexión de F107; nota de Argo CD (anotación explícita en los charts; la mutación es red de seguridad, sin deriva). U4: US-306 como historia en la que participa, en la cabecera y la trazabilidad; rutas de unit-of-work alineadas con el plan (`validation_job/`, `promotion_tool/`). U2: pruebas de ejemplo de `governance:freeze`. `component-methods`: C03 `get_disparity` con F11 y la versión servible; C12 con `monitoring_daily` y `monitoring_freezes` y sin bias en `GET /v1/entries`. Inventario: arista del CronJob en §7, `registry_migrator` en §4; `services.md` S9. No aplica: el NFR, el Infrastructure Design y el plan de U9 todavía no existen (son etapas siguientes; §8b fija lo que deben cumplir); el plan de U2 sí está actualizado en el repositorio (Pasos 2, 3 y 14).
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10 04:46
**Timestamp**: 2026-10-10T09:48:47Z
**User Input**: "Hallazgos consolidados (2026-10-10, 04:46)

Abiertos
Proyección de la fila no atribuible (U9, U0, U3)
U9 BR-U9-09. unattributable_invalid es un valor de la ventana, independiente de la versión. Cada rango humana lo devuelve, así que hay que decir que se toma una sola vez. “Los rangos «después»” debe incluir modelo y humana.
Valor en rangos modelo. U0 lo pone en toda fila de totals, y U3 y U9 lo describen solo para humana. Definir que vale 0.
U0, plan, Paso 3. La prueba dice “13 MonitoringRangeRequest” y debe usar MonitoringQuery.
U9 BR §9. Falta la fila “Quinta revisión”.
U3, plan. El Paso 8 no menciona unattributable_invalid, y la trazabilidad de BR-U3-17 y NFR-U3-24/35 no cita los Pasos 17 y 18.
Codificación de monitoring_daily (U0, U3, C12)
C12 y el Paso 8 de U3 dicen GET, pero la solicitud es una lista de hasta 12 rangos de 5 campos. Falta decidir si va en el cuerpo (POST) o en parámetros repetidos.
U3 decision-registry
Referenciada que existe pero no es recommendation. BR-U3-17, PBT-U3-09 y el Paso 12 no la cubren. Tratarla como inexistente.
Decisión sobre una recomendación inválida. Falta definir si el caso queda fijado (fixed_by_decision). Si no, una recomendación válida posterior se cuenta en modelo.
Reconstrucción de ≤ 1 h sin margen. 12 corridas de 5 min son exactamente 60 min, y el Paso 18 exige ≤ 1 h. Opciones: Job a demanda en bucle en el runbook, o declarar ≤ 1,5 h.
BR-U3-17. “El día extra cubre el corte por fecha UTC” aparece dos veces.
NFR-U3 §7. MonitoringAggregatorStale no figura en RESILIENCY-05/07/15 ni en SECURITY-14, y NFR-U3-24 no nombra la alerta.
Plan, Paso 13. Falta el ServiceMonitor del gauge del atraso, y F60 no está en la comprobación de flows.yaml.
logical-components de U3 (lista de la CLI) sin subir.
U4 governance y BFF
Versión servible para get_disparity. El BFF la consulta (F11), pero C09 no define la operación. Opción sin endpoint nuevo: list_models filtrado por activo o congelado. Reflejarlo en C09 y en el propósito de F11, y agregar la prueba al Paso 10 de U4 (con un analista da 403).
U1 platform-foundation
P-U1-05, alcance del sidecar nativo. La regla enumera 4 namespaces, y quedan fuera vectra-identity (Job hook keycloak-config-cli, CronJob realm-drift) y vectra-mock. Un Job mallado sin sidecar nativo no completa, y un hook colgado bloquea la wave 3. Definir “todo namespace mallado” y agregar un caso de kyverno test.
Plan, Paso 16. El conftest sobre lo renderizado no verifica que cada Job y CronJob lleve la anotación explícita.
Texto de la wave 5 en logical-components omite registry-aggregator (cosmético).
Inventario
unit-of-work U10. Dice “29 endpoints” y C03 suma 27: 1 de sesión, 10 de casos, 7 de modelos, 3 de políticas, 3 de fuentes y 3 de vigilancia.
component-dependency §1. vectra-app lista solo el CronJob registry-aggregator. Faltan registry-checkpoint, registry-verify-*, registry-archive y model-archive.
X04. Agregar la prueba de que el servicio HTTP de bias → freeze da 403.
U9 bias-monitoring
NFR, Infrastructure Design y plan sin subir. Deben cumplir §8b: backoffLimit: 0, Forbid, vectra-high, sidecar nativo y ExternalSecret de la clave privada de bias-monitoring-job.
"
**AI Response**: Aplicados todos. Fila no atribuible: `unattributable_invalid` pasa a ser un **solo** valor por solicitud, sobre un `unattributable_range` nuevo de `MonitoringQuery` (fuera de `totals`, así que no se repite ni hay que definir su valor en los rangos de `modelo`); BR-U9-09 lo toma una vez y cuenta los rangos «después» de `modelo` y de `humana`; U0, U3 y U9 alineados; fila de la quinta y de la sexta revisión en BR-U9 §9. `monitoring_daily` pasa a `POST /v1/monitoring/daily:query` con el `MonitoringQuery` en el cuerpo (C12, U0, plan de U3). U3: referenciada que no es `recommendation` = inexistente (no atribuible); decisión sobre una recomendación inválida fija el caso con `counted_seq = NULL`; reconstrucción con Job a demanda `aggregator run --until-head` en el runbook (≤ 1 h con margen); frase duplicada eliminada; NFR-U3 §7 (RESILIENCY-05/07/15, SECURITY-14) y NFR-U3-24 con `MonitoringAggregatorStale`; plan Pasos 8 (POST y `unattributable_invalid`), 12 (casos nuevos), 13 (`ServiceMonitor` y F60), 18 (Job a demanda) y trazabilidad con los Pasos 17 y 18; logical-components con la CLI completa. U4 y BFF: C09 `list_models(state=activo,congelado)`, F11 con ese propósito, BR-U9-18 y prueba en el Paso 10 de U4 (analista → 403). U1: «namespace mallado» = con `linkerd.io/inject: enabled` (incluye `vectra-identity` y `vectra-mock`), con casos de `kyverno test`; Paso 16 verifica la anotación explícita en lo renderizado; ola 5 con `registry-aggregator`. Inventario: U10 con 27 endpoints; `vectra-app` con todos los CronJobs de U3 y `model-archive`; X04 con la prueba del servicio HTTP de bias → `freeze` → 403. No aplica: NFR, Infrastructure Design y plan de U9 son etapas siguientes (§8b).
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos abiertos consolidados
**Timestamp**: 2026-10-10T09:58:35Z
**User Input**: "Hallazgos abiertos consolidados

A. Técnico y de mayor riesgo
U1, P-U1-05 y Paso 5 (Kyverno).
La política selecciona por “la etiqueta linkerd.io/inject: enabled del namespace”.
En Linkerd, inject es una anotación, y el namespaceSelector de Kyverno solo ve etiquetas.
Hay que verificarlo.
Si es así, la política necesita una etiqueta propia puesta por el chart de namespaces (por ejemplo vectra.io/mesh: enabled) o un apiCall que lea la anotación.
El Paso 5 debe probar el caso del namespace sin esa marca.
U0, plan, Paso 9 y Paso 15. POST /v1/monitoring/daily:query no se registra como ruta de solo lectura con registry:read:monitoring. Sin ese registro, la verificación de rutas de create_app la rechazaría.
U3, Job a demanda del runbook monitoring-rebuild:
infrastructure-design no lo define. INF-U3-03 no tiene su fila (activeDeadlineSeconds: 5400, recursos, PriorityClass, backoffLimit, sidecar nativo). INF-U3-04 no cuenta su conexión.
No se dice con qué identidad corre aggregator reset (registry_migrator desde ESO). F107 solo cubre al agregador.
Falta aclarar que Forbid no lo cubre: sin suspender el CronJob solapan, y solo los frena el FOR UPDATE.
En el plan de U3, ningún paso crea su plantilla en el chart ni prueba --until-head.
B. U0 (plan)
Paso 3: no valida unattributable_range (from_day ≤ to_day) ni unattributable_invalid ≥ 0.
C. U3
Plan, Paso 8. La descripción del endpoint omite unattributable_range, y no hay prueba de from_day > to_day → 422.
BLM:
La fila cli no menciona --until-head.
Falta una prueba de ejemplo del valor único de unattributable_invalid: con y sin unattributable_range, una decisión dentro del rango y otra fuera.
PBT-U3-09 tiene un paréntesis de cierre sobrante.
Lectura de monitoring_daily (BR-U3-17 y domain-entities §3): no dice POST …:query, ni “0 si no se pidió”, ni from_day ≤ to_day.
Fila de índice sin precedente. Si una decisión fija un caso cuya recomendación inválida no creó fila, el BLM no define el evaluated_at de la fila nueva. Propongo el evaluated_at de la recomendación referenciada.
Domain-entities §1.3 (monitoring_entry_totals) dice solo “cuya recomendación no existe”. Debe decir también “o no es recommendation”.
Historial de cambios: BR §7 y NFR §8 no tienen filas de las revisiones tercera a sexta.
Nombres de bucket sin unificar: registry-checkpoints y registry-archive en logical-components; vectra-registry-checkpoints y vectra-registry-archive en infrastructure-design.
tech-stack de U3 sin subir. El generador sintético ya está en el plan (Paso 17); falta verificar que tech-stack lo liste.
D. U9
Domain-entities §1.2 y BLM siguen en “por rango”. Deben decir valor único por solicitud.
BR-U9-09 no nombra unattributable_range. Debe decir que bias lo envía con la ventana de la corrida (hoy − 29 a hoy), en la primera solicitud.
NFR, Infrastructure Design y plan sin subir. Además, §8b: backoffLimit: 0, Forbid, vectra-high, sidecar nativo y ExternalSecret de la clave privada de bias-monitoring-job.
E. U1 y U2
U1, Paso 5: no hay caso de kyverno test para vectra-mock ni para el CronJob realm-drift. (Menor.)
U1, Paso 6: la cuota de vectra-app debe sumar también el Job a demanda de U3.
U2: el plan (Pasos 2 y 14) sin subir.
"
**AI Response**: Aplicados todos. (A) U1: confirmado que en Linkerd `inject` es una anotación; la mutación selecciona ahora por la etiqueta propia `vectra.io/mesh: enabled`, que pone el chart de namespaces junto con la anotación, con una prueba de que van siempre juntas y casos de `kyverno test` sin la etiqueta, en `vectra-mock` y para `realm-drift`. U0: `RouteContract.read_only` para un `POST` de consulta (P-U0-12), con `POST /v1/monitoring/daily:query` declarado así en el Paso 9 y la spec comprobada en el Paso 15. U3: Jobs a demanda `registry-aggregator-rebuild` y `registry-aggregator-reset` en INF-U3-03 (5400 s / 300 s, `backoffLimit: 0`, sidecar, PriorityClass), su conexión en INF-U3-04 y en F107; el reset corre con la credencial de `registry_migrator` vía ESO (F44); `Forbid` no cubre al Job a demanda: el runbook suspende el CronJob y, si se solapan, el `FOR UPDATE` serializa; plantillas y prueba de `--until-head` en el Paso 12. (B) U0: validación de `from_day ≤ to_day` y `unattributable_invalid ≥ 0` en el Paso 3. (C) U3: Paso 8 con `unattributable_range` y 422 por rango invertido; BLM con `--until-head`, ejemplo del valor único de `unattributable_invalid` y paréntesis de PBT-U3-09 corregido; BR-U3-17 y domain-entities §3 con `POST …:query`, 0 sin rango y `from_day ≤ to_day`; fila nueva del índice con el `evaluated_at` de la referenciada; §1.3 «o no es `recommendation`»; historial de BR §7 y NFR §8 con las revisiones tercera a séptima; buckets `vectra-registry-*` unificados en logical-components; generador sintético en el tech-stack. (D) U9: §1.2, BLM y BR-U9-09 con `unattributable_range` en la primera solicitud y valor único. (E) U1: cuota de `vectra-app` con el Job a demanda de U3. No aplica: NFR, Infrastructure Design y plan de U9 (etapas siguientes, §8b); el plan de U2 está en el repositorio (séptima revisión del FD de U9, 2026-10-10).
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10 05:06
**Timestamp**: 2026-10-10T10:07:42Z
**User Input**: "Hallazgos consolidados (2026-10-10 05:06)

A. Inventario, infraestructura y U3
Inventario, F107/F44. component-dependency no dice que registry-aggregator-rebuild use F107 ni cuál es el flujo del reset. INF-U3-04 conecta reset a registry-db-rw con registry_migrator, pero F44 es del Job de migración (hallazgo 26 de la lista anterior).
Inventario §4. Las filas de registry_aggregator y registry_migrator no incluyen los Jobs a demanda en “Usado por”. Hoy solo citan el Job de migración y el runbook a mano.
Inventario §1 y unit-of-work. La lista de CronJobs de vectra-app y los flujos de U3 no traen los Jobs rebuild y reset.
BR-U3-17. Tiene el typo “Objetivo: objetivo ≤ 1 h”.
U3 logical-components y deployment-architecture. El inventario, el diagrama y el texto alterno no listan los Jobs a demanda. Solo los menciona la fila de la CLI y el escenario de resiliencia.
NFR-U3-42. Dice que registry_aggregator tiene “solo escritura sobre las tablas derivadas”, pero también lee registry_entries. Tampoco dice que reset usa registry_migrator.
NFR-U3-24. Atribuye la reconstrucción en ≤ 1 h a aggregator reset, pero la hace run --until-head. Además falta explicar que el activeDeadlineSeconds de 5400 s (90 min) es un margen sobre el objetivo de 1 h.
NFR-U3 §8. La fila “U3 Infrastructure Design (pendiente)” quedó vieja, porque ese diseño ya existe.
Plan de U3, Paso 12. La plantilla de reset no menciona sidecar, vectra-normal ni cuota, que sí están en INF-U3-03.
B. U0 y U1
U0, read_only. El plan lo usa (Pasos 9 y 15), pero no está definido en el FD ni en el NFR de U0 (RouteContract, P-U0-12, BR-U0-71..73). El §9 de U9 afirma que P-U0-12 ya lo trae, y no he recibido esos archivos para comprobarlo.
U0 domain-entities §9.4. No dice la regla de unattributable_range (from ≤ to) ni unattributable_invalid ≥ 0.
U1, chart de namespaces. Ningún paso define el chart que pone vectra.io/mesh: enabled junto con la anotación.
U1, Paso 5. El paréntesis quedó mal redactado.
U1, P-U1-05. El texto de nfr-design-patterns (3810281c) sigue seleccionando por linkerd.io/inject, pero Kyverno solo ve etiquetas.
C. U9
BLM §2.3 y pruebas. El flujo de GET /v1/disparity no menciona que el BFF envía la versión servible (list_models(state=activo,congelado)), y no hay prueba de ejemplo para el valor por omisión ni para cuando no llega.
NFR, Infrastructure Design y plan. No los he visto, y §8b los deja pendientes. El Infrastructure Design debe fijar backoffLimit: 0, Forbid, vectra-high, sidecar nativo y el ExternalSecret de bias-monitoring-job.
D. Otras unidades y transversales
U2. Plan, Pasos 2 y 14: cliente bias-monitoring-job y pruebas de governance:freeze.
flows.yaml, INF-U7-02 y NFR-U1-13.
unit-of-work §3.1. Menciona archive_job/ (menor).
U10:
applicant_display y filtro vencido.
Advertencias decision_already_recorded y model_frozen_after_recommendation.
Escapado de free_text.
Texto “estado de crédito no integrado”.
Leyenda y lint de frases prohibidas (FR-BIA-08).
U11. Medir con evaluated_at, decided_at y viewed_at, y solo con recomendaciones entregadas.
U12:
Demo RT-5 y medición case-db.
Volumen demo RT-2: 36 celdas ≥ 30 casos solo en región y estrato.
Latencia de detección ≈ 20 min.
"
**AI Response**: Aplicados. (A) Flujo nuevo F108 para el Job a demanda `registry-aggregator-reset` (rol `registry_migrator`; F44 queda solo para el Job de migración del sync); F107 incluye el Job `registry-aggregator-rebuild`; inventario §4 («Usado por») y §1 con los Jobs a demanda; unit-of-work U3 (contenido y flujos F107/F108); typo de BR-U3-17 corregido y margen de 90 min explicado; logical-components (inventario, diagrama, texto) y deployment-architecture con los Jobs a demanda; NFR-U3-42 (lectura de `registry_entries`; `registry_migrator` en el reset) y NFR-U3-24 (la reconstrucción la hace `run --until-head`; 5400 s es margen); fila vieja de NFR-U3 §8 marcada resuelta; INF-U3-03/06 y plan Pasos 12 (reset con sidecar, `vectra-normal`, cuota, F108) y 13 (F108 en `flows.yaml`). (B) U0: regla de `read_only` en BR-U0-71 (además de P-U0-12); las reglas de §9.4 (`from_day ≤ to_day`, `unattributable_invalid ≥ 0`) ya están en el párrafo «Validación de estructura» de U0 domain-entities. U1: chart `platform/namespaces` en el Paso 5 (PSA, `vectra.io/mesh` y la anotación, siempre juntas); paréntesis del Paso 5 reescrito; P-U1-05 vigente ya selecciona por `vectra.io/mesh` (la copia revisada era anterior); rangos F01–F108 en P-U1-01, el plan de U1 y application-design. (C) U9: BLM §2.3 con `list_models(state=activo,congelado)` del BFF y ejemplos de la versión por omisión y sin versión. (D) Pendientes para U10, U11 y U12 registrados en U9 §8b (lint FR-BIA-08, versión servible, medición de U11, volumen de la demo RT-2 y latencia ≈ 20 min); los de U8 para U10 y U12 siguen en U8; `archive_job/` en unit-of-work §3.1. No aplica: NFR, Infrastructure Design y plan de U9 (etapas siguientes); el plan de U2 ya tiene el cliente y las pruebas (Pasos 2, 3 y 14).
**Context**: CONSTRUCTION - U9 - Functional Design, esperando aprobación.

---
## U9 Functional Design — Aprobación
**Timestamp**: 2026-10-10T10:14:20Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U9 aprobado. Inicia NFR Requirements de U9.
**Context**: CONSTRUCTION - U9 - Functional Design aprobado; siguiente: NFR Requirements.

---
## U9 NFR Requirements — Plan y preguntas
**Timestamp**: 2026-10-10T10:15:29Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/bias-monitoring-nfr-requirements-plan.md` con 9 preguntas: duración de la corrida y latencia de detección (Q1), latencia de la API (Q2), criticidad por proceso (Q3), escalado del servicio (Q4), librería estadística en runtime (Q5), calidad y simulación (Q6), seguridad y privacidad del dashboard, incluida la inferencia por resta (Q7), escenarios de resiliencia (Q8) y recursos del CronJob (Q9).
**Context**: CONSTRUCTION - U9 - NFR Requirements, esperando respuestas.

---
## U9 NFR Requirements — Respuestas y artefactos
**Timestamp**: 2026-10-10T10:23:10Z
**User Input**: "ya respondí"
**AI Response**: Respuestas: Q2, Q3, Q4, Q5, Q6, Q9 = A; Q1 = A con detección p95 ≤ 30 min (atraso p95 del agregador ≤ 10 min) y `activeDeadlineSeconds: 600`; Q3 con la criticidad de C11 separada en `components.md` y `application-design.md`; Q4 con la exención de `require-hpa-bounds`; Q7 = A con la regla sin inferencia por resta aplicada a la diferencia sin bandas; Q8 = A con E5 precisado y E7 (Keycloak caído). Sin ambigüedades. Verificado: `principal_role` ya está en la allowlist de U0 §8 (sin cambio); NFR-U1-12 exigía HPA en todo servicio, así que se agregó la exención `vectra.io/hpa-exempt` (NFR-U1-12 y Paso 5 del plan de U1, con `kyverno test`). Generados `construction/bias-monitoring/nfr-requirements/nfr-requirements.md` (NFR-U9-01..54) y `tech-stack-decisions.md`. Cambios: U9 FD BR-U9-06, 18, 20, §8b, domain-entities y PBT-U9-03; U0 §9.4 (`population_difference_partial`); `components.md` y `application-design.md`; U1 NFR-U1-12 y plan Paso 5.
**Context**: CONSTRUCTION - U9 - NFR Requirements, esperando aprobación.

---
## U9 NFR Requirements (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10 05:28
**Timestamp**: 2026-10-10T10:30:12Z
**User Input**: "Hallazgos consolidados (10 oct 2026, 05:28)

A. Jobs a demanda y su documentación (U3, inventario)
Quién lanza los Jobs rebuild y reset y con qué identidad. Falta decidirlo frente a AUTONOMIA-01, a Argo CD (OutOfSync) y a K01–K14.
Octava revisión. Falta su fila en BR-U3 §7.
NFR-U3 §8. Dice “segunda a séptima”.
infrastructure-design §6. Dice “F01–F107” y no registra F107 ni F108.
component-dependency §7. La frase de flujos omitidos no menciona F96, F97, F107 ni F108.
logical-components de U3. No tiene los Jobs a demanda (no ha sido vuelto a subir).
unit-of-work, U4 Contenido. Omite el CronJob model-archive.
B. U0
read_only. No está definido como campo de RouteContract ni en P-U0-12. domain-entities no lo menciona.
BR-U0-71. “Scopes de lectura” y “sin efectos” no están definidos.
C. U1
P-U1-09. No incluye los Jobs a demanda.
Plan de U1. La estructura no tiene el directorio namespaces/.
Paso 6. La cuota solo cubre rebuild.
Paso 5. El paréntesis está enredado.
NFR-U1-12. Falta subir la actualización de la exención de HPA. Solo está el Paso 5 del plan.
D. U9
NFR §8 sin aplicar en el FD. Faltan BR-U9-06, 18 y 20, domain-entities de U9 §2.4 y §8b (≈ 20 → ≈ 27 min).
PBT-U9-03 y PBT-U9-08. NFR-U9-31 las extiende a la diferencia sin bandas, pero el BLM no lo dice.
Infrastructure Design y plan de U9. Siguen sin llegar. Deben recoger backoffLimit: 0, Forbid, vectra-high, el sidecar y el ExternalSecret de bias-monitoring-job.
NFR Design de U9. Siguen sin llegar. Debe fijar los timeouts de NFR-U9-03.
Pendientes duplicados. Los de U10, U11 y U12 aparecen en U8 y en U9 §8b.
"
**AI Response**: Aplicados. (A) Decisión: los Jobs a demanda de U3 se renderizan como hooks de sync de Argo CD solo con el value `monitoringRebuild.runId`; el runbook es un PR (que también suspende el CronJob) y un sync manual (AUTONOMIA-01); los crea Argo CD con su identidad (K04), sin binding nuevo, sin recursos fuera de Git y sin `OutOfSync`; reset antes que rebuild por `sync-wave`; un segundo PR los quita. Reflejado en BR-U3-17, INF-U3-03, deployment-architecture y plan Paso 12 (con prueba de `helm template` con y sin `runId`). Filas de la octava revisión y de esta en BR-U3 §7; NFR-U3 §8 «segunda a octava»; infrastructure-design §6 con F01–F108 y la fila de F107/F108; §7 de `component-dependency` cita F96, F97, F106, F107 y F108; `model-archive` en el contenido de U4 de unit-of-work. (B) U0: `RouteContract` con `read_only` definido también en domain-entities §7.1b (ya estaba en P-U0-12); BR-U0-71 define «scope de lectura» y «sin efectos» y cómo lo comprueba el registro de contratos. (C) U1: P-U1-09 con los Jobs a demanda (rebuild `vectra-high`, reset `vectra-normal`) y el servicio HTTP de bias en `vectra-normal`; directorio `namespaces/` en la estructura del plan; cuota del Paso 6 con los dos Jobs; aceptación del Paso 5 reescrita en casos nombrados; NFR-U1-12 ya tenía la exención (copia revisada anterior). (D) U9: los cambios de NFR §8 en el FD ya estaban aplicados (BR-U9-06, 18, 20, domain-entities §2.4, §8b con ≈ 27 min; copia revisada anterior); PBT-U9-08 extendida a la diferencia sin bandas (PBT-U9-03 ya lo estaba); §8b deja solo los pendientes propios de U9 para U10, U11 y U12 y remite a U7 y U8 para los demás. No aplica: NFR Design, Infrastructure Design y plan de U9 (etapas siguientes).
**Context**: CONSTRUCTION - U9 - NFR Requirements, esperando aprobación.

---
## U9 NFR Requirements (gate abierto) — Request Changes: hallazgos consolidados 2026-10-10 05:37
**Timestamp**: 2026-10-10T10:39:07Z
**User Input**: "Hallazgos consolidados (10 oct 2026, 05:37)

A. U3: lanzamiento de los Jobs a demanda (nuevos)
Salvaguarda del runId. Mientras runId siga fijado, cualquier sync repite el reset y la reconstrucción (≈ 1 h con bias fallando por atraso). Si el segundo PR se olvida, pasa en cada sync. Falta una alerta o regla.
Cabos sueltos de los hooks.
Los Jobs de runId anteriores se acumulan (falta ttlSecondsAfterFinished).
El rebuild bloquea el sync de toda la Application hasta 90 min.
Ninguna alerta cubre un hook fallido.
El Paso 14 y el Paso 18 (punto 8) no prueban el flujo PR, hook y sync.
BR-U3-11. El párrafo “Precisado el 2026-10-03…” parte la tabla y la fila range no se renderiza.
BR-U3-17. El bullet “Iteración” es ilegible: mezcla CronJob, Job, Argo CD y runbook con paréntesis anidados. Conviene un bullet “Lanzamiento del runbook”.
B. Inventario y arquitectura
§4 de component-dependency. Faltan registry_verifier y registry_health, y no dice qué rol usan checkpoint y archive.
F26. Describe la proyección “por día”, y ahora es POST …:query sumado por rango.
F107/F108 y §8. No dicen que los Jobs a demanda son hooks de sync bajo K04.
Árboles de §3.1 de unit-of-work. U1 y U3 no coinciden con la estructura de sus planes (baja prioridad).
U1 Paso 16. El conftest de Jobs renderizados no ve los Jobs a demanda sin runId. Falta una nota cruzada o una variante con runId.
C. U9
Registro de cambios del NFR Requirements. El §9 solo registra los de U9, U0 §9.4, components.md y U1 (NFR-U1-12 y Paso 5). Faltan los de U3 (hooks), U0 (BR-U0-71 y §7.1b) y U1 (P-U1-09, Paso 6, namespaces/ y casos del Paso 5).
Marca parcial. partial (BR-U9-06) frente a population_difference_partial (entidades y U0). El label partial no está en la firma de vectra_bias_disparity.
E7 (Keycloak caído). BR-U9-20 no tiene motivo de falla para la falta de token, y falta un ejemplo de prueba y un generador en PBT-U9-05.
Eventos de log. disparity.viewed y freeze_context.viewed (NFR-U9-32) no están en el FD ni en el catálogo de eventos de U0 (BR-U0-51).
Etapas sin llegar. Faltan NFR Design (timeouts de NFR-U9-03), Infrastructure Design y plan. Estos deben cubrir backoffLimit: 0, Forbid, vectra-high, sidecar y el ExternalSecret de bias-monitoring-job.
D. U0 y U1
Plan y P-U0-12 de U0. No están subidos. Falta confirmar el campo read_only y la prueba de arranque que rechaza un POST con scopes de lectura y sin read_only.
Idempotency-Key. BR-U0-71 la menciona sin una referencia dentro de U0 a dónde se exige.
"
**AI Response**: Aplicados. (A) Se reemplaza la decisión anterior de hooks de sync: los hooks se repetían en cada sync mientras el value siguiera fijado, bloqueaban la Application y acumulaban Jobs. Ahora el chart renderiza siempre dos CronJobs suspendidos como plantilla (`registry-aggregator-reset`, `registry-aggregator-rebuild`, `ttlSecondsAfterFinished: 604800`); un operador crea los Jobs con `kubectl create job --from` (binding nuevo K15, solo `create` de Jobs y `get` de CronJobs en `vectra-app`, con la política de Kyverno `restrict-manual-jobs`); los Jobs quedan como hijos del CronJob, sin deriva en Argo CD; el CronJob del agregador no se suspende (el `FOR UPDATE` de la marca serializa los lotes y el reset espera el lote en curso); un rebuild fallido se ve porque `MonitoringAggregatorStale` vuelve al vencer el silencio del runbook. BR-U3-17 reorganizado en Iteración, Reconstrucción y Lanzamiento; tabla de BR-U3-11 reparada; INF-U3-03, deployment-architecture, plan Pasos 12, 14 y 18 con el flujo probado. (B) `component-dependency`: K15, roles `registry_verifier` y `registry_health` en §4 y rol de checkpoint y archive; F26 con `POST …:query` sumado por rango; F107 y F108 con el lanzamiento; patrón de CronJob suspendido en §8; rangos K01–K15 en U1, application-design y el plan de U1; árboles de U1 y U3 de unit-of-work alineados con sus planes; Paso 16 de U1 con los CronJobs suspendidos. (C) U9: `population_difference_partial` unificado y etiqueta `partial` en `vectra_bias_disparity`; motivo `token` (E7) con ejemplo y generador en PBT-U9-05; eventos `disparity.viewed` y `freeze_context.viewed` en BR-U9-18/19 y en un catálogo de eventos nuevo en U0 §8.1 (BR-U0-51 lo cita; prueba en el Paso 10 del plan de U0); NFR §8 con las filas de U3, U0, U1 y U9. (D) U0: `read_only` ya estaba en P-U0-12 y en el Paso 9 (con la prueba de arranque); BR-U0-71 aclara que la `Idempotency-Key` es regla de las unidades dueñas (U8 BR-U8-02). No aplica: NFR Design, Infrastructure Design y plan de U9 (etapas siguientes).
**Context**: CONSTRUCTION - U9 - NFR Requirements, esperando aprobación.

---
## U9 NFR Requirements (gate abierto) — Request Changes: hallazgos 2026-10-10 05:49
**Timestamp**: 2026-10-10T10:50:56Z
**User Input**: "Hallazgos abiertos (10-oct, 05:49)

Bloquea la ruta crítica
#    Hallazgo    Dónde    Qué falta
1    restrict-manual-jobs eludible. Solo comprueba el ownerReference, que escribe el cliente. Quien tenga K15 puede crear un Job que lo cite pero cambie imagen, comando o volúmenes. El reset corre con registry_migrator (DDL sobre registry-db), lo que rompe X06, X05 y SECURITY-06.    BR-U3-17, plan de U1 Paso 5    Fijar el pod template (SA, imagen por digest, comando, volúmenes y envFrom iguales al CronJob) o verificar el UID del dueño. Añadir un caso negativo.
2    Dos Jobs a demanda a la vez. kubectl create job --from no respeta Forbid. Un reset durante un rebuild hace retroceder la marca.    INF-U3-04, BR-U3-17    Rechazar un Job nuevo si ya hay otro reset o rebuild activo, o exigirlo en el runbook. Cambiar el texto “con el CronJob suspendido”, que ya no es cierto.
3    Excepción a AUTONOMIA-01 sin registrar. Con K15, un humano crea Jobs sin pasar por Argo CD.    NFR-U1-43, P-U1-12, component-dependency §9.5, application-design §7.1, fila de infraestructura de U3    Anotar la excepción y su evidencia: audit log de Kubernetes y un paso del runbook para guardarlo.
4    K15 sin dueño en U1.    Plan de U1, NFR-U1-27, unit-of-work (dice “K02–K13”)    Role/RoleBinding, definición del grupo de operadores, su simulación en kind, prueba kubectl auth can-i y corregir “K02–K13”.
5    restrict-manual-jobs no está en NFR-U1-25 ni tiene patrón de NFR Design.    NFR-U1-25, P-U1    Requisito con kyverno test positivo y negativo, y un P-U1-13.
"
**AI Response**: (pendiente de aclaración) Los cinco hallazgos dependen de mantener K15. Antes de editar se pregunta al usuario cómo lanzar los Jobs a demanda (archivo de aclaración).
**Context**: CONSTRUCTION - U9 - NFR Requirements, esperando aclaración.

---
## U9 NFR Requirements — Aclaración respondida y aplicada
**Timestamp**: 2026-10-10T10:53:55Z
**User Input**: "ya respondi"
**AI Response**: Q1 = A. La reconstrucción de U3 usa Jobs normales en Git (no hooks): el chart renderiza `registry-aggregator-reset-<runId>` y `registry-aggregator-rebuild-<runId>` solo con `monitoringRebuild.runId`, en `sync-wave` sucesivas, sin `ttlSecondsAfterFinished`; el runbook es un PR con un `runId` nuevo y un sync manual; los crea Argo CD (K04). Un *advisory lock* de PostgreSQL impide dos reconstrucciones a la vez (hallazgo 2). Se retiran K15 y `restrict-manual-jobs`, con lo que los hallazgos 1, 3, 4 y 5 dejan de aplicar. Queda a verificar en kind si el sync espera la salud del último wave. Actualizados BR-U3-17 y §7, INF-U3-03/04, deployment-architecture, plan de U3 (Pasos 12 y 18), `component-dependency` (K15 retirado, F107, F108, §8, rango K01–K14), U1 (NFR-U1-27, plan Pasos 5 y 16, application-design) y los registros de cambios de U9.
**Context**: CONSTRUCTION - U9 - NFR Requirements, esperando aprobación.

---

## U9 NFR Requirements — Aprobación
**Timestamp**: 2026-10-10T10:57:22Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U9 aprobado. Inicia NFR Design de U9.
**Context**: CONSTRUCTION - U9 - NFR Requirements aprobado; siguiente: NFR Design.

---
## U9 NFR Design — Plan y preguntas
**Timestamp**: 2026-10-10T10:58:11Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/bias-monitoring-nfr-design-plan.md` con 6 preguntas: timeouts y circuit breaker por dependencia (Q1), caché del dashboard (Q2), expresiones y ventanas de las alertas (Q3), corrida con varias versiones y `freeze` fallido (Q4), lugar de la supresión de celdas chicas (Q5), imagen y procesos (Q6).
**Context**: CONSTRUCTION - U9 - NFR Design, esperando respuestas.

---
## U9 NFR Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T11:03:16Z
**User Input**: "ya respondi"
**AI Response**: Q1–Q6 = A, sin ambigüedades. Generados `construction/bias-monitoring/nfr-design/nfr-design-patterns.md` (P-U9-01..07: corrida todo o nada con todas las versiones, timeouts y reintentos con el CronJob sin breaker, caché con single-flight, supresión en la librería, identidades y procesos, alertas con sus expresiones, escenarios E1–E7) y `logical-components.md` (inventario, diagrama, texto alternativo, presupuesto de la corrida ≈ 1,5 min en el peor caso, pendientes para el Infrastructure Design). Cambios: U0 NFR-U0-23 (c), P-U0-07 y Paso 10 del plan (modo `breaker="disabled"` solo para procesos batch); U0 §9.4 (`CellResult` insuficiente sin `rate`); U9 BR-U9-12 (varias versiones).
**Context**: CONSTRUCTION - U9 - NFR Design, esperando aprobación.

---

## U9 NFR Design — Aprobación
**Timestamp**: 2026-10-10T11:06:54Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U9 aprobado. Inicia Infrastructure Design de U9.
**Context**: CONSTRUCTION - U9 - NFR Design aprobado; siguiente: Infrastructure Design.

---
## U9 Infrastructure Design — Plan y preguntas
**Timestamp**: 2026-10-10T11:07:40Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/bias-monitoring-infrastructure-design-plan.md` con 5 preguntas: recursos del servicio y aporte a la cuota (Q1), horario del CronJob desfasado del agregador de U3 (Q2), configuración y aprobación de cumplimiento del umbral (Q3), barrera de red para `freeze` con dos ServiceAccounts y Linkerd (Q4), dashboard de Grafana como código (Q5). Storage y Messaging: N/A.
**Context**: CONSTRUCTION - U9 - Infrastructure Design, esperando respuestas.

---
## U9 Infrastructure Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T11:10:43Z
**User Input**: "ya repsondi"
**AI Response**: Q1–Q5 = A, sin ambigüedades. Generados `construction/bias-monitoring/infrastructure-design/infrastructure-design.md` (INF-U9-01 recursos y cuota; INF-U9-02 CronJob `2,17,32,47 * * * *` UTC con `startingDeadlineSeconds: 300`; INF-U9-03 `values-monitoring-policy.yaml` con `CODEOWNERS` de cumplimiento y rangos por `conftest`; INF-U9-04 dos ServiceAccounts y tres barreras para `freeze`; INF-U9-05 reglas, runbooks y dashboard `bias.json`) y `deployment-architecture.md`. Cambios: U4 INF-U4-04 y plan Paso 16 (`AuthorizationPolicy` de `freeze` solo para `bias-monitoring-job`); U1 plan Paso 6 (aporte de U9 a la cuota); `component-dependency` F27.
**Context**: CONSTRUCTION - U9 - Infrastructure Design, esperando aprobación.

---

## U9 Infrastructure Design (gate abierto) — Request Changes: hallazgos
**Timestamp**: 2026-10-10T11:14:35Z
**User Input**: "Hallazgos

Alta
U3, N1: el sync de unos 90 min del rebuild bloquea el rollback del registro. Un solo Application contiene los Jobs de reconstrucción y el despliegue del registro, que es el componente Critical.
Propuesta: una Application aparte, decision-registry-rebuild.
Toca el Paso 15 y BR-U3-17 de U3, el §8 y F107/F108 de component-dependency, y la fila 89 del §8 de NFR Requirements de U9.
Media
U3, N2: falta prune y la regla del runId. El runbook debe exigir el sync con prune para retirar los Jobs viejos. Falta un formato de runId con fecha y un check del PR que rechace uno ya usado.
U3: sin plan si el rebuild supera 1 h. El objetivo es ≤ 1 h con un plazo de 90 min, y no hay contingencia definida.
U9, alertas: P-U9-06 e INF-U9-05 dejan 3600 y 7200 s escritos a mano, pero W (stale_after) es un valor que aprueba cumplimiento. La PrometheusRule debe generarse con W y 2W, con una prueba en promtool.
U9, schedule: la regla de conftest cubre umbral, n_min, ventana y W, pero no el horario. Hay que definir un rango o decir que no lo tiene.
U9, BiasFreezeFailed: se apaga si la corrida siguiente falla antes del cálculo, aunque la versión siga sin congelar. Hasta que salte MonitoreoSesgoDetenido pasa hasta 1 h sin alerta.
Propuesta: mantener la métrica hasta que un freeze tenga éxito.
U0, NFR-U0-23: la cláusula del breaker disabled está pegada después de “(e)” con la etiqueta “(c)” repetida, y la columna de verificación no tiene su prueba.
U0, Paso 3 del plan: falta la prueba de CellResult con muestra_insuficiente y rate → error. El §9.4 de domain-entities dice que el Paso 3 la trae.
U0, orden de pasos: la prueba de que create_app rechaza un POST de solo lectura sin read_only está en el Paso 9, pero create_app se construye en el Paso 10.
U9, BR-U9-22: mantiene max(...) y dice que las expresiones se fijan en NFR Design. P-U9-06 ya las fijó con max by (model_version_id).
"
**AI Response**: Aplicados. U3: Application aparte `decision-registry-rebuild` (wave 6) para los Jobs de reconstrucción, de modo que un sync largo no bloquee el sync ni el rollback del registro (BR-U3-17, INF-U3-03, deployment-architecture, plan Paso 15, `component-dependency` §8 y F107/F108, fila de U9 NFR §8); `runId` con formato `AAAAMMDD-HHMM`, historial `rebuild-history.yaml` y check de CI que rechaza uno repetido; sync manual con prune; contingencia si el rebuild supera 1 h (el CronJob nunca suspendido termina la reconstrucción; si el atraso no baja en 2 h, SEV1). U9: la `PrometheusRule` genera W y 2W desde `stale_after` (P-U9-06, INF-U9-05) con `promtool` generado para cada valor; rango del horario en `conftest` (intervalo de 5 a 15 min, desfase de 1 a 4 min respecto del agregador, W ≥ 4 × intervalo); `BiasFreezeFailed` en un grupo del Pushgateway por versión que solo se borra con un `freeze` exitoso o 409 (BR-U9-20, P-U9-01, 06); BR-U9-22 remite a las expresiones de P-U9-06. U0: NFR-U0-23 con la cláusula (f) bien numerada y su prueba en la columna de verificación; prueba de `CellResult` insuficiente con `rate` en el Paso 3; prueba de `create_app` con `read_only` movida del Paso 9 al Paso 10.
**Context**: CONSTRUCTION - U9 - Infrastructure Design, esperando aprobación.

---
## U9 Infrastructure Design — Aprobación
**Timestamp**: 2026-10-10T11:22:07Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U9 aprobado. Inicia Code Generation Part 1 (plan de tareas) de U9; Part 2 fuera de alcance.
**Context**: CONSTRUCTION - U9 - Infrastructure Design aprobado; siguiente: plan de tareas.

---
## U9 Code Generation Part 1 — Plan de tareas generado (solicitud de aprobación)
**Timestamp**: 2026-10-10T11:23:54Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Plan de tareas en `construction/plans/bias-monitoring-code-generation-plan.md`: 17 pasos en 7 bloques (estructura y configuración; librería `vectra_disparity` con oráculo de Fairlearn, mutación y simulación; lógica del CronJob; servicio HTTP; despliegue con chart, parámetros de cumplimiento, alertas generadas desde W y dashboard; verificación en kind; cierre). Trazabilidad generada por script: US-301..304, 306..308, BR-U9-01..22, NFR-U9-01..54, P-U9-01..07, INF-U9-01..05 y PBT-U9-01..08 cubiertos (BR-U9-16 y NFR-U9-33 se asignaron a los Pasos 15 y 9 tras la primera pasada). Prompt de aprobación: «Request Changes / Approve plan».
**Context**: CONSTRUCTION - U9 - Code Generation Part 1, esperando aprobación.

---
## U9 Code Generation Part 1 — Request Changes: hallazgos
**Timestamp**: 2026-10-10T11:27:00Z
**User Input**: "Hallazgos

Media
U9, Paso 5: el comando de cobertura (pytest bias-monitoring/disparity --cov=vectra_disparity) apunta a un directorio sin pruebas. Debe apuntar a bias-monitoring/tests.
U9, workflow de CI: ningún paso crea el workflow de la simulación nocturna, mutmut y la regla de rutas (NFR-U9-53). Falta un paso como el Paso 21 de U0.
U9, horario fijo en el Paso 12: el CronJob lleva el horario escrito, pero INF-U9-03 lo define como un value. El Paso 2 dice que la aplicación lo lee del archivo de parámetros, y el código no lo usa.
U9, BiasFreezeFailed atascada: el grupo freeze-<id> solo se borra con un freeze exitoso o un 409. Si la versión deja de cumplir la regla o de evaluarse, la alerta SEV1 queda activa. Hoy solo se resuelve a mano con el runbook. El Paso 7 tampoco prueba el borrado con 409.
U3, plan: el chart de los Jobs de reconstrucción no aparece en la estructura ni en el Paso 12. El Paso 15 dice que va en la Application aparte, sin ruta. Propuesta: chart-rebuild/.
U3, runbook monitoring-rebuild: durante el rebuild salta MonitoreoSesgoDetenido (a W = 1 h sin corrida exitosa), y el runbook solo silencia MonitoringAggregatorStale. Hay que silenciarla también, con vencimiento, o documentarla como esperada. Afecta BR-U3-17, la fila 75 de deployment-architecture, el Paso 18 y el runbook de U9.
"
**AI Response**: Aplicados. U9: Paso 5 con el comando de cobertura sobre las pruebas de la librería en `bias-monitoring/tests`; Paso 15 nuevo, workflow de CI de U9 (PR, regla de rutas para `mutmut` y simulación, nocturno), con los pasos siguientes renumerados (kind = 16, N/A = 17, cierre = 18) y la trazabilidad regenerada; el `schedule` del CronJob sale de `values-monitoring-policy.yaml` (Paso 12) y el Paso 2 aclara que la app usa umbral, `n_min` y ventana y solo informa horario y W; el grupo `freeze-<id>` también se borra en una corrida completa en la que la versión ya no cumple la regla o ya no se evalúa (BR-U9-20, P-U9-01, Paso 7 con la prueba del 409 y de esos casos). U3: `decision-registry/chart-rebuild/` en la estructura y en los Pasos 12 y 15 del plan y en BR-U3-17; el runbook `monitoring-rebuild` silencia también `MonitoreoSesgoDetenido` con vencimiento de 2 h y el `runId` (BR-U3-17, deployment-architecture, Pasos 14 y 18; runbook de U9 en el Paso 13 de su plan).
**Context**: CONSTRUCTION - U9 - Code Generation Part 1, esperando aprobación.

---
## U9 Code Generation Part 1 — Aprobación
**Timestamp**: 2026-10-10T11:31:14Z
**User Input**: "Approve plan"
**AI Response**: Plan de tareas de U9 aprobado. U9 queda cerrada (Code Generation Part 2 y Build and Test fuera de alcance). Siguiente: U10 console — Functional Design.
**Context**: CONSTRUCTION - U9 cerrada; inicia U10 Functional Design.

---
## U10 Functional Design — Plan y preguntas
**Timestamp**: 2026-10-10T11:33:01Z
**User Input**: (sin entrada nueva; continúa tras "Approve plan" de U9)
**AI Response**: Creado `construction/plans/console-functional-design-plan.md` con 12 preguntas: tokens en el navegador (Q1), step-up a mitad de un formulario (Q2), «estado de crédito no integrado» con un valor propio de `credit_status` (Q3, hallazgo heredado de U8), cuándo se registra la consulta de la explicación (Q4), formulario de decisión (Q5), bandeja y refresco (Q6), catálogo de mensajes de error (Q7), lista única de frases prohibidas (Q8), vistas por rol (Q9), congelamiento y fuente (Q10), composición del expediente (Q11) y matriz de US-602 (Q12).
**Context**: CONSTRUCTION - U10 - Functional Design, esperando respuestas.

---
## U10 Functional Design — Respuestas
**Timestamp**: 2026-10-10T11:38:00Z
**User Input**: "ya respondí"
**AI Response**: Respuestas leídas: Q1–Q12 = A, sin ambigüedades. No hacen falta preguntas de aclaración.
**Context**: CONSTRUCTION - U10 - Functional Design, generación de artefactos.

---
## U10 Functional Design — Artefactos y cambios a otras unidades
**Timestamp**: 2026-10-10T11:40:04Z
**User Input**: (sin entrada nueva; continúa tras "ya respondí")
**AI Response**: Creados en `construction/console/functional-design/`: `business-rules.md` (BR-U10-01..19), `domain-entities.md`, `business-logic-model.md` (flujos, PBT-U10-01..06, pruebas de ejemplo, cumplimiento de extensiones) y `frontend-components.md`. Cambios a otras unidades: Q3, `credit_status = no_integrado` con `core.enabled = false` (U0 `CaseDetail`/`CreditStatus`; U8 BR-U8-21, NFR-U8-25, domain-entities §5, business-logic-model, INF-U8-02, deployment-architecture, plan Paso 12 y tabla de cambios de U8); Q7, `reason` `no_active_version` y `active_version_frozen` agregados al catálogo cerrado de U0 §6 (U4 BR-U4-13 ya los usaba); Q8, lista única `contracts/forbidden-phrases.yaml` (U0 BR-U0-94, plan de U0 Paso 3 con herramienta y CODEOWNERS), referenciada desde U4 BR-U4-07 y su plan, U9 business-rules §6, INF-U9-05 y su plan. Checklist del plan marcado.
**Context**: CONSTRUCTION - U10 - Functional Design, esperando aprobación.

---
## U10 Functional Design — Request Changes: hallazgos abiertos (10 oct, 06:45)
**Timestamp**: 2026-10-10T11:46:42Z
**User Input**: "Hallazgos abiertos (10 oct, 06:45)

A. Decisiones o errores de lógica (corregir antes de aprobar)
#    Unidad    Hallazgo
A1    U10    Step-up MFA: la redirección a Keycloak recarga la SPA y borra la memoria, así que el cuerpo del formulario nunca sobrevive. BR-U10-06, flujo 2.2, PBT-U10-05 y su prueba de ejemplo. Salida: step-up en ventana emergente (window.open + postMessage), o aceptar que el usuario siempre re-confirma y decirlo en la regla
A2    U10    Roles por vista: BR-U10-12 y frontend-components no coinciden. El frontend da a cumplimiento Modelos y Políticas, y a cro Fuentes de datos. Hay que fijarlo contra la columna «Roles» de C03
A3    U10 / U0    Búsqueda en la bandeja: BR-U10-10 busca por applicant_display (lleva el nombre), pero domain-entities de U10 dice que los filtros viven en la URL sin datos del solicitante
A4    U0    CaseFilter no tiene model_frozen_after_recommendation? ni q? (filtros de BR-U10-10)
A5    U9    values-monitoring-policy.yaml vive en el monorepo, pero el CODEOWNERS está en GitOps; la revisión de cumplimiento puede no aplicarse
A6    U9    Peor caso de la corrida (Paso 2): no cuenta los pushes y borrados de los grupos freeze-<v> (≈ 100 s). Regla conftest: activeDeadlineSeconds ≤ intervalo, y los intervalos de 6 y 12 min rompen el desfase
A7    U9    Faltan pruebas en el Paso 9: imagen sin módulo de freeze, respuestas con umbral/n_min/W, readiness con el registro caído, series de /metrics, disparity.viewed en cache hit
B. Consistencia entre documentos

U0

B1. Faltan los tipos propios del BFF en §9 (SessionInfo, Dossier de la consola); falta confirmar dónde viven RegistryDossier e IntegrityStatus.
B2. Plan de U0, Paso 3: no recoge CreditStatus, los dos reason nuevos (no_active_version, active_version_frozen) ni la prueba de «un mensaje por cada code y reason».
B3. Modelo de lógica: sin fila del módulo forbidden_phrases ni sus pruebas de ejemplo.
B4. breaker=\"disabled\" falta en logical-components, el modelo de lógica, PBT-U0-14 y tech-stack.
B5. BR-U0-37 repite una frase. El §8.1 no tiene eventos de U2, U3, U4 ni U6.

U9

B6. Paso 9 del plan: «ninguna frase de la lista de U10» debe citar forbidden_phrases.py y la lista de U0, como ya hace el Paso 13.
B7. P-U9-06: viñeta «persisten hasta un freeze exitoso» desactualizada. «(c)» debe ser «(f)» en P-U9-02 y en NDP §7. Falta la fila de U0 §9.4 en NDP §7 y la de revisión del plan en BR-U9 §9 y NDP §7.
B8. deployment-architecture y F106 no mencionan los grupos por versión ni que success se publica solo si la corrida fue completa. Falta documentar el solapamiento con el lote del agregador (≤ 240 s) y la cuota con y sin el sidecar de Linkerd.
B9. Paso 1 dice tres dependencias de desarrollo y el Paso 11 dice cuatro (con scipy). El Paso 10 no nombra la herramienta de cobertura. Al Paso 15 le falta el grep prohibido de kubectl, helm install y terraform apply.

U3

B10. BR-U3-11: la fila range quedó fuera de la tabla. BR-U3 §7 sin fila de revisión del plan. INF-U3 §6 con fecha 2026-10-03 y sin filas de la Application aparte ni de los Jobs.
B11. Paso 15 sin wave 6 ni dónde se hace la comprobación del runId. Paso 12: el conftest debe nombrar chart-rebuild/. Falta decidir si el ExternalSecret de registry_migrator va siempre o solo con runId.
B12. Runbook monitoring-rebuild: comprobar vectra_bias_last_run_failure{reason} antes de dar por esperada la alerta silenciada. Paréntesis sobrante en la fila 75 de deployment-architecture.

U1 y U4

B13. U1: el Paso 3 y la suite de conectividad no dicen que F27 es solo desde el CronJob. Los Pasos 5, 6 y 16 deben citar la Application aparte. NFR-U1-25/27/43, P-U1-09 y P-U1-12 conservan el residuo de K15.
B14. U4: INF-U4 §4 desactualizado (fecha 2026-10-03; sin F27 ni INF-U4-05; dice «F01–F102»).

U8

B15. domain-entities §5: paréntesis anidado y repetido en la fila CreditStatus.
B16. Las filas históricas de BR-U8 §8 y de INF-U8 §7 siguen diciendo «no_disponible sin llamar»; anotarlas como superadas por la Q3.
B17. El modelo de lógica no tiene la prueba de ejemplo «core.enabled = false → no_integrado, cero llamadas».

U10

B18. ManualApplicationForm cita BR-U10-06 (step-up), pero el alta manual no pide MFA.
B19. BR-U10-19 trata mfa_required como una respuesta aparte de 403; en U0 es un 403 con ese code.
C. Redacción
C1. La nota «Revisada contra el cuerpo… antes de presentarla» sigue en NDP §6 y INF-U9 §5 (U9), en el plan de U9 §3, INF-U4 §5, el plan de U3 §3, INF-U3 §7, y ahora también en el modelo de lógica de U10 y de U8, INF-U8 §6 y NFR-U8 §8.
C2. U0: BR-U0-37 repite una frase.
C3. U0: disabled falta además en BR-U0-71… (ver B4).
D. Pendientes de otras unidades, sin cambios
U2: plan, Pasos 2 y 14; flows.yaml; INF-U7-02; NFR-U1-13.
U10 (heredados): applicant_display, filtro vencido, avisos decision_already_recorded y model_frozen_after_recommendation, escape de free_text, leyenda y lint FR-BIA-08, embeber bias.json. Casi todos ya resueltos por el FD de U10; falta contrastarlos con el código.
U11: medir con evaluated_at, decided_at y viewed_at, solo recomendaciones entregadas.
U8 / U12: demo RT-5 y case-db; RT-2 con 36 celdas ≥ 30 casos, solo región y estrato.
[VERIFICAR] con cumplimiento: retención de 10 y 2 años, riesgo residual de respaldos a 12 meses, Ley 1581, NFR-U8-47.
38 de 958 archivos sin copiar."
**AI Response**: Aplicados. A1: step-up en ventana emergente del mismo origen (`window.open` + `postMessage` desde `/stepup-callback`, validación de origen, ventana y `state`, reintento único con el cuerpo en memoria; si la ventana se bloquea o cierra, no hay reintento y el formulario queda intacto); nada en `sessionStorage`; BR-U10-06, flujo 2.2 con el reintento terminal, PBT-U10-05, pruebas de ejemplo y domain-entities; U2 registra el redirect URI `/stepup-callback`. A2: BR-U10-12 y frontend-components rehechos desde la columna «Roles» de C03 (`cro` solo ve la lista de congelamientos; `cumplimiento` modelos y políticas en lectura; `cro` fuentes en lectura; resumen para el solicitante agregado). A3/A4: sin búsqueda por nombre (solo «Ir al caso» por `case_id`); `CaseFilter.model_frozen_after_recommendation?` en U0, BR-U8-13, U8 BLM y plan Paso 13. A5: CODEOWNERS de `values-monitoring-policy.yaml` en el monorepo y en GitOps; `branch-protection-check` de U4 verifica los dos repositorios con `require_code_owner_reviews`. A6: peor caso con lectura de grupos, PUT/DELETE por versión y hasta 16 DELETE por corrida (≈ 184 s); intervalos admitidos 5, 10 o 15 min y `activeDeadlineSeconds` ≤ intervalo (INF-U9-03, P-U9-02, BR-U9-20, plan Pasos 2, 7 y 12). A7: pruebas del Paso 9 (los cinco parámetros en las respuestas, `freeze_client` fuera de `sys.modules`, readiness con el registro caído, `/metrics`, `disparity.viewed` con caché); `window_days`, `schedule` y `stale_after_s` en `DisparityView` y `FreezeContext` (U0 §9.4 y U9 domain-entities). B1: U0 §9.5 (`SessionInfo`, `ConsoleDossier`) y §9.6 (`RegistryDossier`, `IntegrityStatus`, dueña U3). B2: plan de U0 Paso 3 (`ProblemReason`, `CreditStatus`, `CaseFilter`, tipos del BFF) y Paso 16 (arreglos constantes para la prueba de U10). B3: módulo `forbidden_phrases` y sus ejemplos en el BLM de U0. B4: `breaker="disabled"` en BLM, PBT-U0-14, logical-components y tech-stack (BR-U0-71 es de autorización y no aplica). B5/C2: BR-U0-37 sin la frase repetida; §8.1 aclara que U2, U3, U4, U6 y U10 no tienen eventos propios. B6–B9: U9 Paso 9 cita `forbidden_phrases.py`; P-U9-06 actualizado, «(f)» en P-U9-02 y NDP §7, filas de U0 §9.4 y de la revisión del plan en NDP §7 y BR-U9 §9; deployment-architecture con los grupos, el solapamiento con el agregador y la cuota; F106 con los grupos; cuota con y sin sidecar (supuesto del proxy pendiente de U1); dependencias de desarrollo directas y transitivas, pytest-cov, grep prohibido en el Paso 15. B10–B12: fila `range` dentro de la tabla de BR-U3-11; filas de BR-U3 §7 e INF-U3 §6; wave 6 y workflow del `runId` en el repositorio GitOps; `conftest` sobre `chart-rebuild/`; `ExternalSecret` de `registry_migrator` solo con `runId`; comprobación de `vectra_bias_last_run_failure{reason}` en el runbook; paréntesis corregido. B13: U1 F27 solo desde el CronJob (Paso 3 y suite), Application aparte en Pasos 5, 6 y 16 y en P-U1-12 (wave 6), residuos de K15 en NFR-U1-25, 27, 43 y P-U1-09. B14: INF-U4 §4 con fecha, rango vigente, INF-U4-05, F27 y el check. B15–B17: fila `CreditStatus` reescrita; filas históricas marcadas como superadas por Q3; pruebas de ejemplo de `no_integrado` y del core caído en el BLM de U8. B18: alta manual sin MFA. B19: `mfa_required` como 403 con ese `code`. C1: notas «Revisada/Verificada/Generada … antes de presentarla» quitadas de todos los artefactos (30 archivos). D: sin cambios.
**Context**: CONSTRUCTION - U10 - Functional Design, Request Changes aplicados; esperando aprobación.

---
## U10 Functional Design — Aprobación
**Timestamp**: 2026-10-10T12:21:18Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U10 aprobado. Inicia NFR Requirements de U10.
**Context**: CONSTRUCTION - U10 - Functional Design aprobado.

---
## U10 NFR Requirements — Plan y preguntas
**Timestamp**: 2026-10-10T12:24:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/console-nfr-requirements-plan.md` con 14 preguntas: latencia del BFF (Q1), rendimiento de la SPA (Q2), escalado del BFF (Q3), criticidad y PriorityClass del BFF (Q4), degradación por destino (Q5), inactividad y cierre de sesión (Q6), CSP estricta, librerías y Trusted Types (Q7), navegadores (Q8), verificación WCAG 2.1 AA (Q9), stack del BFF (Q10), stack de la SPA (Q11), errores del navegador (Q12), cadena de suministro de npm e imagen estática (Q13), pruebas y umbrales (Q14).
**Context**: CONSTRUCTION - U10 - NFR Requirements, esperando respuestas.

---
## U10 NFR Requirements — Respuestas y artefactos
**Timestamp**: 2026-10-10T12:25:16Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1–Q14 = A, sin ambigüedades. Creados `construction/console/nfr-requirements/nfr-requirements.md` (NFR-U10-01..64) y `tech-stack-decisions.md`. Cambios a otras unidades: U1 P-U1-09 (`console-bff` en `vectra-high`, `console-spa` en `vectra-normal`; Q4); U2 domain-entities §4.1, BR-U2-13, tabla de cambios y plan (CSP con `require-trusted-types-for 'script'; trusted-types 'none'`; Q7); `component-methods.md` C03 y `unit-of-work.md` (endpoint 28 `report_client_error`); U10 BR-U10-01, 19 y business-logic-model (28 endpoints); U0 §8 (`app_version` en la allowlist), §8.1 (evento `console.client_error`) y §9.5 (`ClientErrorReport`) (Q12). Checklist del plan marcado.
**Context**: CONSTRUCTION - U10 - NFR Requirements, esperando aprobación.

---
## U10 NFR Requirements — Aprobación
**Timestamp**: 2026-10-10T12:36:04Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U10 aprobado. Inicia NFR Design de U10.
**Context**: CONSTRUCTION - U10 - NFR Requirements aprobado.

---
## U10 NFR Design — Plan y preguntas
**Timestamp**: 2026-10-10T12:40:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/console-nfr-design-plan.md` con 7 preguntas: timeouts y conexiones por destino (Q1), objetivo de `get_dossier` incompatible con NFR-U3-21 (Q2), verificación de integridad asíncrona (Q3), alertas del BFF (Q4), sesgo de versión en un despliegue (Q5), perfiles de carga y de red (Q6), caché en el BFF para `get_disparity` (Q7).
**Context**: CONSTRUCTION - U10 - NFR Design, esperando respuestas.

---
## U10 NFR Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T12:38:36Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q7 = A, sin ambigüedades. Creados `construction/console/nfr-design/nfr-design-patterns.md` (P-U10-01..11, escenarios E1–E7) y `logical-components.md`. Cambios a otras unidades: NFR-U10-02 corregido (`get_dossier` ≤ registro 2 s + 30 ms; Q2); U3 BR-U3-13b, domain-entities §1.2 y §5.0 (tabla `integrity_checks`, permisos de `registry_app`), tabla de cambios y plan Paso 8 (verificación asíncrona: 202, `GET /v1/integrity-checks/{id}`, tarea en segundo plano, `fallida` por interrupción; Q3); `component-methods.md` C03 y registro, `component-dependency.md` F13, `unit-of-work.md` (29 endpoints); U10 BR-U10-01, 19, business-logic-model y frontend-components; U0 §9.6 (`IntegrityCheckRef`, `IntegrityCheckStatus`). Pendiente para U8 y U4: confirmar 120 y 60 conexiones desde 6 réplicas del BFF. Checklist marcado.
**Context**: CONSTRUCTION - U10 - NFR Design, esperando aprobación.

---
## U10 NFR Design — Aprobación
**Timestamp**: 2026-10-10T12:47:00Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U10 aprobado. Inicia Infrastructure Design de U10.
**Context**: CONSTRUCTION - U10 - NFR Design aprobado.

---
## U10 Infrastructure Design — Plan y preguntas
**Timestamp**: 2026-10-10T12:50:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/console-infrastructure-design-plan.md` con 6 preguntas: recursos y cuotas (Q1), recursos de la versión anterior en la imagen de la SPA (Q2), malla y políticas de red (Q3), configuración por entorno (Q4), dashboard y runbooks (Q5), entornos y pruebas de extremo a extremo (Q6). Almacenamiento y mensajería sin preguntas, con la justificación en el plan.
**Context**: CONSTRUCTION - U10 - Infrastructure Design, esperando respuestas.

---
## U10 Infrastructure Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T12:49:09Z
**User Input**: "ya respondi"
**AI Response**: Respuestas Q1–Q6 = A, sin ambigüedades. Creados `construction/console/infrastructure-design/infrastructure-design.md` (INF-U10-01..06) y `deployment-architecture.md`. Cambios a otras unidades: U1 plan Paso 6 (aporte de U10 a las cuotas de `vectra-app` y `vectra-edge`), Paso 3 (casos bloqueados SPA → `vectra-app`, BFF → `vectra-data` y `vectra-serving`), P-U1-08 (única excepción: la conexión `integrity` de U3); U2 plan y tabla de cambios (usuarios de prueba por rol con TOTP solo en kind, `realm-lint`); U3 P-U3-04 (conexión `integrity` 0 o 1 en la réplica), BR-U3-13b, domain-entities y plan Paso 8 (una sola verificación en curso de cualquier modo; estado por el pool `dossier`); U10 P-U10-05 alineado. Checklist marcado.
**Context**: CONSTRUCTION - U10 - Infrastructure Design, esperando aprobación.

---
## U10 Infrastructure Design — Request Changes: hallazgos abiertos (10 oct 2026, 07:57)
**Timestamp**: 2026-10-10T12:59:34Z
**User Input**: "Hallazgos abiertos (10 oct 2026, 07:57)

U10 console

Infrastructure Design

⚠ Ventana del rolling update de la SPA: un pod viejo no tiene los recursos de N.
⚠ Rollback y saltos de release: la imagen N−1 no trae los recursos de N, y un salto de N−1 a N+1 rompe las pestañas abiertas.
⚠ BFF en kind sin HPA: le falta vectra.io/hpa-exempt, y require-hpa-bounds lo rechaza.
⚠ Confirmar que vectra-edge y el data plane del gateway están en la malla. U1 no los lista.
La ruta de los archivos no coincide entre el plan y el documento (console/spa/… frente a console-spa/…).
P-U10-06 pone el digest previo en el values del chart, e INF-U10-02 lo pone en previous-image.txt.
P-U10-04 remite al «§6» y debe ser el «§7».
El fallback a index.html no se acota a rutas sin extensión.
config.json por subPath no se actualiza en caliente. Hace falta una anotación con el checksum para reiniciar los pods.

NFR Design

ConsoleClientErrorsSpike usa increase > 0 con for: 15m, así que un solo chunk_load_failed nunca dispara.
La codificación de vectra_circuit_state (== 2) no está definida.
Inactividad por pestaña y logout por BroadcastChannel; scroll y wheel.
get_disparity frente al p95 de governance (el p95 de governance es un supuesto).
Timeout de 3 s de la decisión frente a los 2,5 s del registro.
La lista de pools pendientes omite U3, U7 y U9.
Faltan pod-deletion-cost y el escenario E7 en el Paso 18.
Menores: tipo «R» en F13, «28.º», redacción de RESILIENCY-14, estructura de unit-of-work, BR-U10-18 repite la lista y NFR-U10-40 remite a BR-U10-05.

Functional Design y Requirements

Popup de step-up: el diálogo de frontend-components §4 frente a BR-U10-06 y §2.2, y la activación del usuario.
NFR-U10-52 no dice «<1 s».
get_case para cumplimiento en el expediente: ¿403 o caso caído?
BR-U10-19 no incluye auth_time vencido.
El FD no absorbe los componentes del NFR: diálogo de inactividad a los 25/30 min, reporter, aviso de versión, módulo client_errors y parámetros de configuración.
NFR-U1-12 y el Paso 6 de U1 (hpa-exempt para console-spa) y el Paso 7 de U2.
U3 decision-registry
⚠ La API no tiene permisos de bóveda ni de bucket (P-U3-08). La verificación completa o range por API no puede validar firmas ni comparar con el WORM (BR-U3-12, pasos 5 y 6).
⚠ Una fila en_curso huérfana bloquea el único cupo hasta que algún pod reinicie, porque el barrido es solo al arrancar. El bloqueo ahora es de cualquier modo.
⚠ Checkpoint tras cada full (BR-U3-08) frente a BR-U3-13b: la API no puede firmar.
P-U3-04 dice que el pool dossier es «solo SELECT», pero ahora escribe integrity_checks.
El business-logic-model no tiene el flujo asíncrono, el módulo, las pruebas de ejemplo ni la máquina de estados.
logical-components no muestra la tabla integrity_checks ni el pool integrity.
El 409 no informa el check_id en curso, y no hay consulta de la verificación actual.
Falta una alerta para el pool dossier, que ahora comparte el latido, y para una verificación fallida.
last_full_verification no tiene tipo ni lugar de escritura (la full mensual del CronJob es de solo lectura).
BR-U3-01 y BR-U3-02 no mencionan la excepción de integrity_checks.
terminada / error / fallida: falta precisar la relación.
Las claves de los advisory locks de BR-U3-04 y BR-U3-17 no se declaran distintas.
Por confirmar: lectura larga en el standby síncrono con remote_apply (conflicto de recuperación o replay retrasado).
Plan de U3: el Paso 2 no incluye integrity_checks ni sus permisos, el Paso 7 no menciona el pool integrity, y el Paso 18 no tiene la prueba de matar el pod a mitad de verificación. También falta INF-U3-03 (fila de reset), P-U3-08 y P-U3-04, que no vi completos.
U0
⚠ max_body_bytes falta en RouteContract, y el BodyGuard de 32 KiB choca con las entradas de 64 KiB.
⚠ IntegrityReport no está en U0 (solo en U3) y no hay IntegrityCheckRequest. run_integrity_check no tiene argumento mode.
Faltan reglas de estructura para los §9.5 y §9.6: terminada ⇔ informe, fallida ⇔ motivo, progress.checked ≤ total y not_verified ⇔ motivo y primer seq.
IntegrityStatus (to_checkpoint_seq (o head)), last_full_verification y los valores de delivery_status no tienen tipo.
BR-U0-94 no se puede verificar con lint (no es una lista única), U7 falta en la lista de usuarios y la prueba «sesgos sin medir» no prueba el límite de palabra.
forbidden_phrases falta en el inventario, el tech-stack y el NFR (INF-U10-05 ya lo usa).
Falta definir dónde se declara process_kind; «504» no está en el catálogo; BR-U0-72 duplica el step-up.
Catálogo de scopes: intake:submit con channel/channel-simulator, y core:read-credit «solo kind y staging».
«(segunda)» con paréntesis anidados; P-U0-08 frente a RESILIENCY-14 de U1; plan de U0, Pasos 3 (pruebas §9.6) y 10.
U2 identity-edge
⚠ BR-U2-13 y PBT-U2-05 dicen que solo /grafana/** permite frame-ancestors 'self', pero el perfil auth también lo permite.
⚠ BR-U2-04 y el §2.2 describen una redirección completa, no el popup, /stepup-callback ni postMessage. Tampoco hay prueba del popup en el Paso 13.
Los usuarios de prueba de kind figuran solo en el §8 de las reglas. Faltan en el §3 de domain-entities, con nombres, y la prueba de realm-lint que los rechaza en staging y producción. Además, un usuario por rol no permite probar aprobador ≠ proponente.
/stepup-callback y el callback del login no están en la tabla de rutas cerradas del gateway. Cross-Origin-Opener-Policy en /auth/** por confirmar.
El §4 dice «cualquier rol» en el gateway y BR-U2-15 dice 403 en el BFF para un usuario sin rol.
El límite de 10 req/min por IP en /auth/** detrás de un NAT bancario.
analista sin MFA toma decisiones: ¿lo confirma el negocio?
U1 platform-foundation
⚠ Pushgateway sin persistencia ni autenticación (F106 GET/DELETE necesita una política que lo controle).
Namespaces mallados: la lista omite vectra-observability, vectra-serving y vectra-edge. Los casos de prueba del Paso 5 tampoco incluyen vectra-edge.
NFR-U1-13 y P-U1-09 (cuotas) no consideran proxy.resources; falta KServe vectra-normal inactivo y minReplicas ≥ 2 frente a staging con 1 réplica.
NFR-U1-12 nombra solo a bias-monitoring-service como hpa-exempt.
Flujo de silencios de Alertmanager; el paso 2b de P-U1-05 con el rol real case_retention.
Las waves de Envoy Gateway y Valkey; la redacción «se ejecutan en Operations».
U4–U9 y D
U4: NFR-U4-31, 22 y 10; la anotación del Job de validación de governance.
U5: pendientes de las revisiones anteriores.
U6: staging solo con predictor; InferenceServiceNotReady.
U7: lint, etiquetas y escenarios.
U8: concurrencia frente a la capacidad del explainer; F104.
U9: logical-components desactualizado, for: 30m y la propiedad de borrado en Pushgateway.
U11, U12 y [VERIFICAR]: pendientes de las revisiones anteriores."
**AI Response**: Aplicados los hallazgos concretos. U3: verificación bajo demanda rediseñada (la API solo registra la solicitud: 202, o 200 con la activa y `already_active`; la ejecuta el CronJob `registry-verify-ondemand` con la identidad de verificación, que valida firmas y el bucket WORM; barrido de huérfanas en cada corrida; relación de estados; la `full` mensual pasa por la misma tabla y define `last_full_verification`; lectura del standby en tramos cortos con `hot_standby_feedback` y `max_standby_streaming_delay = 2s`; llaves de advisory lock declaradas y distintas; BR-U3-01, 02, 04, 08 precisados; tabla `integrity_checks` con CHECK y permisos; BLM §2.6 con máquina de estados, módulo y pruebas; P-U3-04 (pool `dossier` con el INSERT), P-U3-08, P-U3-09 (dos alertas), logical-components, INF-U3-03 y plan Pasos 2, 8, 12, 14, 18); se quitó la conexión `integrity` y la excepción de P-U1-08. U10: afinidad por cookie para el rollout; «versión anterior» = digest en producción, rollback como release nuevo; HPA 2/2 en kind; malla de `vectra-edge`; rutas `console/spa/`; fallback solo sin extensión; ConfigMap sin subPath con checksum; alertas (`ConsoleChunkOrCspError` sin `for`); codificación del circuito; inactividad de la sesión compartida y con `wheel`/`scroll`; governance p95 declarado por U4 (NFR-U4-13); timeouts de escritura 4 s; pools pendientes de U3, U7 y U9; E7; ventana emergente abierta en un clic (botón «Verificar y confirmar» o diálogo); NFR-U10-52 < 1 s; `get_case_identifiers` para el expediente de `cumplimiento` (403 ≠ caída); BR-U10-19 con `auth_time` vencido; BR-U10-20..22 (inactividad, versión, errores) y parámetros; menores (F13 R/W, «28.º», RESILIENCY-14, unit-of-work, BR-U10-18, NFR-U10-40). U0: `max_body_bytes` en `RouteContract` (80 KiB para el append, 64 KiB para `freeze`); `IntegrityCheckRequest`, `IntegrityReport`, `DossierEntry`, `LastFullVerification`, `CaseIdentifiers` y reglas de estructura de §9.5/9.6; `deadline_exceeded` 504; `process_kind` y codificación del circuito en NFR-U0-23; BR-U0-94 con frases literales y U7; `forbidden_phrases` en logical-components, tech-stack y NFR-U0-47; BR-U0-72 sin repetir el step-up; scopes `intake:submit` y `core:read-credit`; P-U0-08 alineado con U1; plan Pasos 3 y 10. U2: step-up en ventana emergente en BR-U2-04, BLM §2.2 y Paso 13; `auth` y `grafana` con `frame-ancestors 'self'`; COOP `same-origin`; rutas `/callback` y `/stepup-callback`; afinidad por cookie; dos usuarios nombrados por rol en kind y staging; 403 en el gateway sin rol; `/auth/**` a 600 req/min por IP (NAT). U1: P-U1-13 (Pushgateway con persistencia y autorización por identidad y método), P-U1-14 (namespaces mallados y `proxy.resources`), NFR-U1-12 y 13, silencios por F109 (nuevo), waves de Envoy Gateway y Valkey, `case_retention` real en 2b, redacción de RESILIENCY-14. U4: NFR-U4-13 y anotación del Job de validación. U8: `get_case_identifiers`. U9: logical-components, presupuesto ≈ 186 s, `for` de `DisparidadDecisionHumana` = 2 × intervalo, invariante del ciclo de vida de `freeze-<v>`. Preguntas en `construction/plans/console-infrastructure-design-review-questions.md`: MFA del analista para decidir (Q1) y hallazgos sin detalle de U4–U8, U11, U12 y [VERIFICAR] (Q2).
**Context**: CONSTRUCTION - U10 - Infrastructure Design, Request Changes aplicados; esperando respuestas a 2 preguntas.

---
## U10 Infrastructure Design — Respuestas a la revisión
**Timestamp**: 2026-10-10T13:20:00Z
**User Input**: "ya respondí"
**AI Response**: Q1 = A: `record_decision` sigue sin step-up; registrado como BR-U10-09b con [VERIFICAR] con cumplimiento y el comité. Q2 = B: hallazgos sin detalle diferidos y registrados en `construction/console/infrastructure-design/infrastructure-design.md` §8 — U4 («NFR-U4-31, 22 y 10»), U5 (pendientes anteriores), U6 («staging solo con predictor; InferenceServiceNotReady»), U7 («lint, etiquetas y escenarios»), U8 («concurrencia frente a la capacidad del explainer; F104»), U1 («KServe vectra-normal inactivo»), U11, U12 y [VERIFICAR].
**Context**: CONSTRUCTION - U10 - Infrastructure Design, esperando aprobación.

---
## U10 Infrastructure Design — Request Changes: hallazgos abiertos (segunda revisión)
**Timestamp**: 2026-10-10T14:55:33Z
**User Input**: "Hallazgos abiertos

U10 console (bloquean el Infrastructure Design)
#    Hallazgo    Dónde
1    Falta comprobar al promover que el digest «anterior» coincide con el de producción. Guardarlo en una etiqueta de la imagen y reconstruir si difiere.    INF-U10-02
2    signinPopup con InMemoryWebStorage contradice el flujo manual de BR-U10-06. Especificar popup manual con la API de bajo nivel o validar con una prueba de concepto.    P-U10-07, logical-components, tech-stack
3    BR-U10-09b dice que human_decision guarda acr y auth_time, pero U3 BR-U3-16 y U8 BR-U8-18 no lo exigen. Escribirlo en BR-U8-18 y confirmar que el Actor de U0 lo admite.    BR-U8-18, U0
U10 (no bloquean)
#    Hallazgo
4    Cuota frente a maxSurge: 100% de la SPA (4 pods) y al rollout del BFF (8 pods). Confirmar el margen del namespace.
5    Timeouts y límites de conexión: constantes del código o ConfigMap.
6    Filas históricas desactualizadas: P-U10-05 §7, NFR-U10 §8 y already_active en frontend-components.
U3 decision-registry
La API comparte el rol registry_verifier.
registry_app aparece con UPDATE en domain-entities §1.2.
NFR-U3-43: el 409 queda obsoleto.
La full mensual se omite si hay una verificación activa. Falta decidir qué pasa entonces.
Una full mensual fallida debería ser SEV3.
Faltan los emisores de métricas.
El archivado no va en chunks y choca con max_standby_streaming_delay de 2 s.
El readiness usa sync_state y no el quórum.
F97, F98, F99 e INF-U3-04.
U4 governance
NFR-U4-04 necesita fijar la edad máxima de la copia en memoria de la configuración.
Una versión inactiva con 1 réplica choca con NFR-U1-12.
U9 bias-monitoring
Permisos GET y DELETE del Pushgateway.
La organización de Grafana para bias.json.
El margen de RT-2 es ≈ 28 min frente a 30.
U2 identity-edge
Queda una frase sobrante en BR-U2-13.
La fila de BR-U2 §8 quedó desactualizada.
Falta el rol operacion en Grafana.
U1 platform-foundation
La wave 6 del deployment-architecture omite decision-registry-rebuild.
Las aprobaciones de aidlc-state son anteriores a las revisiones."
**AI Response**: Aplicados. U10: (1) etiqueta OCI `vectra.io/previous-digest` y check `spa-previous-digest-check` obligatorio en el PR de promoción (reconstruir si difiere); (2) step-up con la API de bajo nivel `OidcClient` (sin `signinPopup`) en P-U10-07, logical-components y tech-stack, con prueba de concepto obligatoria; (3) `acr` y `auth_time` obligatorios en todo actor de usuario (U0 §5.1, BR-U3-16, BR-U8-18 y plan de U8 y U0); (4) cuota con los pods del rollout (BFF 7 con `maxSurge: 1`, SPA 4), también en el plan de U1; (5) timeouts y conexiones como constantes del código; (6) filas históricas marcadas como superadas, NFR-U10 §8 resuelto, `already_active` en frontend-components. Corrección propia: BR-U10-09b y la pregunta Q1 decían que el login del analista exige TOTP; U2 §1.1 dice que para `analista` el MFA es opcional, así que una decisión puede quedar con `acr = pwd` (corregido y señalado al usuario). U3: rol `registry_ondemand` aparte y `registry_verifier` de solo lectura; `registry_app` sin `UPDATE`; NFR-U3-43 con 200 y `already_active`; la `full` mensual la encola `registry-verify-ondemand` (se elimina `registry-verify-full`) y `RegistryFullVerificationOverdue` (SEV3); toda `fallida` SEV3; métricas emitidas por el servicio desde `integrity_checks`; archivo en tramos; readiness con `sync_state IN ('sync','quorum')`; F97, F98, F99 e INF-U3-04. U4: NFR-U4-04 con edad máxima de 30 s (503 después) y `ServingConfigStale`; BR-U4-14 ≤ 35 s con una réplica aislada; inactivo con 1 réplica admitido por etiqueta y anotación (NFR-U1-12, U1 plan, U6 INF-U6-02). U9: carpeta `Vectra / Sesgo` solo para `cumplimiento` y `cro`; permisos `PUT`/`DELETE`/`GET` en el Pushgateway; margen de RT-2 ≈ 28 min documentado con la acción si se supera. U2: frase sobrante de BR-U2-13; fila de §8 superada; rol técnico `operacion` y equipos de Grafana. U1: wave 6 con `decision-registry-rebuild`. `aidlc-state.md`: sección de revisiones posteriores a la aprobación.
**Context**: CONSTRUCTION - U10 - Infrastructure Design, esperando aprobación.

---
## U10 Infrastructure Design — Condiciones antes de aprobar
**Timestamp**: 2026-10-10T15:12:42Z
**User Input**: "Condiciones antes de aprobar

INF-U10-05 dice «cinco alertas» y P-U10-10 tiene seis. A ConsoleChunkOrCspError le falta un runbook_url. Puede apuntar a console-client-errors-spike.
Los contadores vectra_console_client_errors_total deben iniciar en 0 para los seis error_code. Si no, increase() no ve el primer error y la alerta con for: 0 no dispara.
La imagen de la SPA que se reconstruye por el check del digest debe volver a pasar por staging. Ahora INF-U10-03 y INF-U10-02 se contradicen en eso.
Hay que decir cómo se omite la etapa previous en el primer release.
Hay que decidir si los parámetros de sesión, versión y reporter de domain-entities §4 van en config.json o son constantes.
En INF §8, «NFR-U4-10» y «KServe inactivo» ya están resueltos. Hay que quitarlos.

Los puntos 3 y 4 son los más importantes. El 1 y el 2 son rápidos de aplicar."
**AI Response**: Aplicadas las seis. (1) INF-U10-05 con seis alertas; runbooks de cada alerta en P-U10-10, con `ConsoleChunkOrCspError` → `console-client-errors-spike` (sección para `csp_violation`). (2) Las seis series de `vectra_console_client_errors_total` se crean en 0 al arrancar (P-U10-09, NFR-U10-34), con prueba de `/metrics` y de `promtool` 0 → 1. (3) Una imagen reconstruida es una imagen nueva: vuelve a staging antes de producción; `spa-previous-digest-check` también falla si el digest no figura en el historial de staging (INF-U10-02 y 03 alineados). (4) Primer release: `ARG PREVIOUS_IMAGE` con valor por omisión `no-previous` (etapa `FROM scratch` del mismo Dockerfile con manifiesto vacío), etiqueta `vectra.io/previous-digest = none`, aceptada por el check solo si producción no tiene digest. (5) `config.json` solo con lo que cambia por entorno (OIDC y el `uid` de `bias.json`); los tiempos y límites son constantes de `console/spa/src/config/constants.ts`, con prueba de `IDLE_LOGOUT_SECONDS` contra `ssoSessionIdleTimeout` de los realms (domain-entities §4, INF-U10-03). (6) INF §8: U4 queda con «NFR-U4-31 y 22»; fila de U1 «KServe inactivo» quitada.
**Context**: CONSTRUCTION - U10 - Infrastructure Design, esperando aprobación.

---
## U10 Infrastructure Design — Aprobación
**Timestamp**: 2026-10-10T15:15:03Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U10 aprobado. Inicia Code Generation Part 1 (plan de tareas) de U10.
**Context**: CONSTRUCTION - U10 - Infrastructure Design aprobado.

---
## U10 Code Generation Part 1 — Plan de tareas
**Timestamp**: 2026-10-10T15:25:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/console-code-generation-plan.md` con 24 pasos en 8 bloques: estructura y constantes (1–2), lógica pura del BFF (3–4), API del BFF con la matriz rol × endpoint (5–8), repositorio N/A (9), SPA con la prueba de concepto del step-up como puerta (10–16), despliegue y operación con la imagen de dos versiones, el check del digest anterior y el release a staging (17–21), escenarios en kind por el operador (22), documentación y cierre (23–24). Trazabilidad de historias, diseño y PBT-U10-01..06, y tabla de cumplimiento. Esperando aprobación del plan.
**Context**: CONSTRUCTION - U10 - Code Generation Part 1, esperando aprobación.

---
## U10 Code Generation Part 1 — Aprobación
**Timestamp**: 2026-10-10T15:19:16Z
**User Input**: "Approve Plan"
**AI Response**: Plan de tareas de U10 aprobado. U10 queda cerrada (Code Generation Part 2 y Build and Test fuera de alcance). Siguiente: U11 product-metrics — Functional Design.
**Context**: CONSTRUCTION - U10 cerrada; inicia U11 Functional Design.

---
## U11 Functional Design — Plan y preguntas
**Timestamp**: 2026-10-10T15:30:00Z
**User Input**: (sin entrada nueva; continúa tras "Approve Plan" de U10)
**AI Response**: Creado `construction/plans/product-metrics-functional-design-plan.md` con 11 preguntas: qué cuenta en la North Star (Q1), «sostenidas por el comité» sin registro del comité (Q2), tiempo de originación (Q3), % con score y explicación y fail-closed desde métricas de U7 (Q4), métrica de ruido y `RuidoExplicacion` (Q5), cálculo periódico sin estado (Q6), recomendación entregada y momentos de negocio (Q7), cortes sin datos por persona (Q8), targets (Q9), acceso al dashboard (Q10), calidad de datos (Q11). Hallazgos señalados: FR-MET-05 sin entidad de comité y FR-MET-03 sin `fail_closed` en la proyección `metrics`.
**Context**: CONSTRUCTION - U11 - Functional Design, esperando respuestas.

---
## U11 Functional Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T15:22:54Z
**User Input**: "ya respondí"
**AI Response**: Respuestas: Q1–Q5 y Q7–Q11 = A (notas en Q3, Q5, Q8 y Q10); Q6 = X: "A, con dos ajustes. (1) Lectura incremental por `seq` en cada ciclo de 5 min y una recomputación completa de 35 días una vez al día, para no repetir 288 lecturas completas al día por réplica sobre el pool `projections` de U3. (2) Las `recommendation` se leen por `evaluated_at` con un margen mayor que el de las decisiones, o el registro resuelve `recommendation_entry_id`; si no, una decisión sobre una recomendación vieja saldría como «no atribuible»." Se eligió que el registro resuelva la referencia en el servidor. Creados `construction/product-metrics/functional-design/business-rules.md` (BR-U11-01..14), `domain-entities.md` y `business-logic-model.md` (PBT-U11-01..06, pruebas de ejemplo, cumplimiento). Cambios: U0 §5.2 (`received_at`, `channel`, `attempt` en `recommendation`) y §9.1 (`received_at` en `ScoringRequest`); U7 (copia los campos); U8 BR-U8-06 (`received_at`); U3 proyección `metrics` (campos nuevos, recomendación resuelta en el servidor, filtros) y plan Paso 8; U1 plan Paso 10 (Job `grafana-folder-permissions` y comprobación de deriva) y F110 nuevo (rangos F01–F110); U9 INF-U9-05 (mismo Job, prueba con `ingeniero-1` y `operacion-1`); pendientes de U8 y U7 para U11 marcados como resueltos. Checklist marcado.
**Context**: CONSTRUCTION - U11 - Functional Design, esperando aprobación.

---
## U11 Functional Design — Condiciones para aprobar
**Timestamp**: 2026-10-10T15:34:56Z
**User Input**: "Condiciones para aprobar

Cortes no agregables. vectra_product_north_star_ratio y vectra_product_recommendation_sustained_ratio se publican solo como razón por channel, outcome y model_version_id. Falta publicar numerador y denominador, o una serie all.
Significado de day y month. BR-U11-08 no define day (¿ayer completo o el día en curso?), ni month (¿mes calendario cerrado o en curso?).
Tipos de entrada. El estado en memoria guarda solo decisions, y compute no usa MetricsExplanationView. Tampoco usa final_outcome, actor_role ni case_id, y no hay serie con actor_role. Hay que definir su uso o eliminarlos de domain-entities §1.
Regla de completitud (BR-U11-06). La lista de causas de desincronía va «por nombre» sin una prueba contra el catálogo de causas de U0. Si U0 cambia, la regla se desfasa en silencio.
Tolerancia de decided_at > recorded_at. BR-U11-10 excluye esas entradas sin margen. Define un margen de tolerancia, o justifica por qué BR-U0-37 garantiza que no ocurre.
Cota de 7 días de BR-U0-37 para received_at. U0 §5.2/BR-U0-37 y el Paso 7 del plan de U3 deben excluir received_at de esa cota. Un caso congelado o no disponible más de 7 días haría rechazar la recommendation.
Casos de originación estándar (BR-U11-05). attempt = 1 no excluye los casos descongelados o reintentados que ya fallaron, porque BR-U8-10 y BR-U8-11 reinician attempts. Añade first_evaluation al payload de recommendation, o acepta el sesgo y déjalo escrito."
**AI Response**: Aplicadas las siete. (1) Conteos `numerator`/`denominator` con todos los cortes y razones solo totales (`all`) o por un corte; el dashboard divide sumas; PBT-U11-07. (2) Periodos en días UTC completos sin el día en curso: `day` = ayer, `30d` hasta ayer, `month_to_date` hasta ayer, `month` = mes anterior cerrado. (3) U11 lee solo `human_decision` con la recomendación resuelta; tabla de campos con su uso; `actor_role` valida (`analista`); fuera `case_id`, `final_outcome`, `MetricsRecommendation` y `MetricsExplanationView` como entradas. (4) `FailClosedCause.category` en U0 (`desincronia` = `version_mismatch`, `feature_dictionary_incomplete`); la regla se genera con `gen_rules.py` y CI corre `--check`. (5) Margen de 5 min, justificado por BR-U0-37 + la ventana de ±5 min de BR-U3-05. (6) `received_at` fuera de la cota de 7 días de BR-U0-37, con pruebas en el plan de U0 (Paso 3) y de U3 (Paso 7). (7) `first_evaluation` en `ScoringRequest` y en el payload de `recommendation` (U0, U7, U3); U8 lo calcula con `cases.ever_degraded` (nuevo), con pruebas en su plan.
**Context**: CONSTRUCTION - U11 - Functional Design, esperando aprobación.

---
## U11 Functional Design — Corrección de texto
**Timestamp**: 2026-10-10T15:40:00Z
**User Input**: "Antes de aprobar, corrige una cosa, que es solo de texto. En business-rules §7, las filas de U7 (copia al payload), de U8 (envío a scoring) y de U3 (proyección y Paso 8) deben nombrar first_evaluation. Hoy solo lo nombran las filas de U0 y la de U8 que lo calcula. U3 domain-entities ya lo tiene, así que en U3 solo falta el Paso 8 del plan."
**AI Response**: Corregido: las filas de U7, U8 (envío) y U3 de business-rules §7 nombran `first_evaluation` (en la de U3, también dentro del objeto `recommendation` resuelto), y el Paso 8 del plan de U3 lo incluye en la proyección `metrics`.
**Context**: CONSTRUCTION - U11 - Functional Design, esperando aprobación.

---
## U11 Functional Design — Aprobación
**Timestamp**: 2026-10-10T15:40:21Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U11 aprobado. Inicia NFR Requirements de U11.
**Context**: CONSTRUCTION - U11 - Functional Design aprobado.

---
## U11 NFR Requirements — Plan y preguntas
**Timestamp**: 2026-10-10T15:45:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/product-metrics-nfr-requirements-plan.md` con 9 preguntas: tiempos del ciclo (Q1), réplicas y series duplicadas (Q2), historia más allá de los 30 días de Prometheus para el target «al mes 6» (Q3), resiliencia ante el registro (Q4), recursos (Q5), seguridad (Q6), stack sin FastAPI (Q7), pruebas (Q8), observabilidad del servicio (Q9).
**Context**: CONSTRUCTION - U11 - NFR Requirements, esperando respuestas.

---
## U11 NFR Requirements — Respuestas y artefactos
**Timestamp**: 2026-10-10T15:43:32Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q9 = A, con notas (presupuesto de la lectura completa con los 6 meses y desfase aleatorio; deduplicación también en alertas y alertas de réplica por réplica; meses republicados y plegados en contadores; sin series al arrancar sin datos y `absent()`; cuota con el proxy; sin flujo nuevo; `ops_server` en U0; recomputación del arranque cuenta y panel en la carpeta de operación). Creados `construction/product-metrics/nfr-requirements/nfr-requirements.md` (NFR-U11-01..42) y `tech-stack-decisions.md`. Cambios: U11 FD BR-U11-08, 11 y 14 y domain-entities §5; U0 NFR-U0-48, logical-components y plan Paso 10 (`vectra_common.ops_server`); U1 plan Pasos 6 (cuota de U11) y 12 (panel de operación); U2 plan (cliente `product-metrics` con un solo scope). Checklist marcado.
**Context**: CONSTRUCTION - U11 - NFR Requirements, esperando aprobación.

---
## U11 NFR Requirements — Correcciones antes de NFR Design
**Timestamp**: 2026-10-10T15:52:36Z
**User Input**: "Antes de pasar a NFR Design, corrige estos dos puntos

absent() por réplica (NFR-U11-08 y BR-U11-14). absent(x) solo dispara si no existe ninguna serie. Con 2 réplicas, si una deja de publicar y la otra no, ProductMetricsStale y ProductMetricsFullRecomputeMissing no se activan. La condición debe comparar contra up{job=\"product-metrics\"}, por ejemplo con unless on(pod). Agrega un promtool test para «una réplica ausente y otra presente».
Allowlist de series (NFR-U11-40 y domain-entities §5). vectra_product_cycle_duration_seconds{kind}, vectra_product_entries_read_total{kind} y vectra_product_last_full_recompute_timestamp no están en la tabla de §5. La prueba «exactamente las de esta tabla» fallaría. Agrégalas, o aclara que la allowlist de producto no incluye las métricas del ciclo."
**AI Response**: Corregidos. (1) `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing` comparan con `up{job="product-metrics"} == 1 unless on (pod) <serie>` en lugar de `absent()`, con `promtool test rules` para una réplica sin la serie y la otra con ella (dispara solo para la primera), las dos sin la serie y las dos con la serie (NFR-U11-08, BR-U11-14). (2) Las series del ciclo (`vectra_product_cycle_duration_seconds{kind}`, `vectra_product_entries_read_total{kind}`, `vectra_product_last_full_recompute_timestamp`) y `vectra_circuit_state{dependency="decision-registry"}` entran en la allowlist de domain-entities §5 en una tabla de operación; la prueba usa las dos tablas más las series estándar de U0 (NFR-U11-40).
**Context**: CONSTRUCTION - U11 - NFR Requirements, esperando aprobación.

---
## U11 NFR Requirements — Aprobación
**Timestamp**: 2026-10-10T15:54:45Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U11 aprobado. Inicia NFR Design de U11.
**Context**: CONSTRUCTION - U11 - NFR Requirements aprobado.

---
## U11 NFR Design — Plan y preguntas
**Timestamp**: 2026-10-10T15:56:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/product-metrics-nfr-design-plan.md` con 6 preguntas: paginación y filtros de lectura (Q1), recomputación diaria sin estados mezclados (Q2), publicación coherente con un `Collector` sobre una instantánea (Q3), deduplicación con recording rules `:dedup` (Q4), estructuras en memoria (Q5), escenarios de falla E1–E5 (Q6).
**Context**: CONSTRUCTION - U11 - NFR Design, esperando respuestas.

---
## U11 NFR Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T15:56:42Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q6 = A, con notas (una sola pasada para 36 días y 6 meses; deduplicación por `seq` y reemplazo conjunto de estado, contadores y `last_seq`; series de operación fuera de la instantánea; `:dedup` también para las razones; memoria con códigos enteros y `__slots__`, la prueba decide; E6 y E7). Creados `construction/product-metrics/nfr-design/nfr-design-patterns.md` (P-U11-01..06, E1–E7) y `logical-components.md`. Cambios: U3 plan Paso 8 (paginación por clave en `metrics`); U11 FD BR-U11-11 (una sola pasada) y PBT-U11-02 (recomputaciones intercaladas). Checklist marcado.
**Context**: CONSTRUCTION - U11 - NFR Design, esperando aprobación.

---
## U11 NFR Design — Condiciones para aprobar
**Timestamp**: 2026-10-10T16:02:39Z
**User Input**: "condiciones para aprobar

Condiciones

El arranque debe leer los 6 meses. BR-U11-11 dice que al arrancar se leen 36 días, mientras que P-U11-01 y logical-components hablan de la pasada completa. Si el arranque lee solo 36 días, después de un despliegue el dashboard queda sin los 6 meses hasta 24 h. Aclara que el arranque hace la misma pasada de ≈ 193 días y corrige el primer punto de BR-U11-11.
Las lecturas a U3 deben ir en serie. P-U11-02 deja correr los incrementales mientras la pasada completa lee, lo que contradice NFR-U11-01 («nunca en paralelo») y satura el pool projections de U3, que tiene una sola conexión. Corrígelo con un candado en el reader y, al terminar la pasada, una lectura incremental desde su last_seq en lugar de reaplicar entradas. La opción A que elegí en la Q2 tenía ese defecto."
**AI Response**: Corregidos. (1) BR-U11-11: el arranque hace la misma pasada completa que la diaria (desde el día 1 del sexto mes cerrado − 1 día, ~184 a ~215 días según el día del mes); P-U11-01 y business-logic-model alineados. (2) P-U11-02 reescrito: candado único en el `reader` para toda lectura a U3; un ciclo incremental con el candado tomado se omite y se cuenta (`vectra_product_cycles_skipped_total`); al terminar la pasada, reemplazo del estado y una lectura incremental desde su `last_seq`, sin reaplicar entradas. Agregado: plazo de 75 min para la pasada y `vectra_product_full_pass_in_progress`, que `ProductMetricsStale` excluye, porque con 10 veces el volumen la pasada puede durar hasta 60 min y la alerta de 30 min dispararía sin falla; escenario E8; PBT-U11-02 verifica que nunca hay dos lecturas a U3 a la vez. NFR-U11-08, domain-entities §5 y logical-components actualizados.
**Context**: CONSTRUCTION - U11 - NFR Design, esperando aprobación.

---
## U11 NFR Design — Aprobación
**Timestamp**: 2026-10-10T16:05:31Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Design de U11 aprobado. Inicia Infrastructure Design de U11.
**Context**: CONSTRUCTION - U11 - NFR Design aprobado.

---
## U11 Infrastructure Design — Plan y preguntas
**Timestamp**: 2026-10-10T16:07:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/product-metrics-infrastructure-design-plan.md` con 6 preguntas: exención de HPA y sondas (Q1), archivo de parámetros (Q2), red sin puerto de API (Q3), reglas, dashboards y runbooks (Q4), entornos y prueba de volumen sin identidad de escritura (Q5), credencial del cliente de Keycloak (Q6). Almacenamiento y mensajería sin preguntas, con la justificación en el plan.
**Context**: CONSTRUCTION - U11 - Infrastructure Design, esperando respuestas.

---
## U11 Infrastructure Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T16:07:51Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q6 = A, con notas. Creados `construction/product-metrics/infrastructure-design/infrastructure-design.md` (INF-U11-01..06) y `deployment-architecture.md`. Ajuste propio a la nota de Q1: la mitigación «sincronizar una réplica a la vez» no se puede hacer con un sync de Argo CD (aplica el `Deployment` entero) y pausar el rollout exigiría `kubectl rollout pause` (AUTONOMIA-01). Se reemplaza por una readiness lista con instantánea o con U3 sin responder, con `progressDeadlineSeconds: 4800`: el rollout espera solo y con U3 caído no se bloquea (NFR-U11-07 actualizado). Otros cambios: NFR-U11-02 y 13 (verificación en CI a 10 veces con doble y kind a 1 vez; la medición contra U3 real a 10 veces queda para Operations); U1 NFR-U1-12 (exención de `product-metrics`), plan Paso 3 (casos de conectividad de U11), Paso 10 (carpeta de operación en `folder-permissions.yaml`) y Paso 11 (runbook `grafana-folder-permissions-drift`); pendiente para U12 (datos de demostración con volumen). Checklist marcado.
**Context**: CONSTRUCTION - U11 - Infrastructure Design, esperando aprobación.

---
## U11 Infrastructure Design — Condiciones para aprobar
**Timestamp**: 2026-10-10T16:14:16Z
**User Input**: "Condiciones para aprobar

Condiciones

Readiness demasiado amplia (INF-U11-01 y NFR-U11-07). Hoy dice que /readyz es 200 si «la primera pasada falló por U3». Un timeout o el plazo de 75 min con U3 lento pero vivo también cuentan como fallo, y la réplica quedaría lista sin datos. Entonces el rollout reemplazaría la segunda réplica y el dashboard quedaría vacío. Limítala a «el breaker hacia U3 está abierto» y define qué pasa cuando el breaker se cierra sin instantánea (vuelve a 503).
Cambio a U0 sin registrar. NFR-U0-48 dice que ops_server usa las mismas sondas que create_app, pero /readyz de U11 depende de la instantánea y del breaker. Registra que ops_server recibe un predicado de readiness, con un caso nuevo en test_ops_server.py.
Cambio a U1 sin registrar. La fila «bias, BFF, métricas → solo su proceso» de P-U1-04 contradice la nueva readiness de product-metrics. Cambia esa fila y regístralo en el §7 del Infrastructure Design de U11."
**AI Response**: Aplicadas. (1) `/readyz` = instantánea publicada o breaker hacia U3 abierto o semiabierto; una pasada fallida o vencida ya no basta; con el breaker cerrado y sin instantánea vuelve a 503 (INF-U11-01, NFR-U11-07, deployment-architecture). Agregado: breaker propio de U11 (3 fallos seguidos, semiabierto a los 60 s, 1 éxito para cerrar), porque los umbrales de U7 no se alcanzan con lecturas en serie (NFR-U11-09, P-U11-01, E6); semiabierto cuenta como abierto para no oscilar; `publishNotReadyAddresses: true` para que Prometheus siga viendo una réplica no lista. (2) U0 NFR-U0-48, logical-components y plan Paso 10: predicado de readiness opcional en `ops_server`, con casos en `test_ops_server.py`. (3) U1 P-U1-04: fila propia de `product-metrics`. Los tres cambios en el §7 del Infrastructure Design de U11.
**Context**: CONSTRUCTION - U11 - Infrastructure Design, esperando aprobación.

---
## U11 Infrastructure Design — Aprobación
**Timestamp**: 2026-10-10T16:18:58Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U11 aprobado. Inicia Code Generation Part 1 (plan de tareas) de U11.
**Context**: CONSTRUCTION - U11 - Infrastructure Design aprobado.

---
## U11 Code Generation Part 1 — Plan de tareas
**Timestamp**: 2026-10-10T16:18:58Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/product-metrics-code-generation-plan.md` con 18 pasos en 7 bloques: estructura y parámetros (1–2), lógica pura y estado con PBT-U11-01..07 (3–5), proceso y publicación con el predicado de readiness y la prueba de volumen a 10 veces con el doble de U3 (6–8), repositorio y frontend N/A (9), despliegue y operación con reglas generadas, `:dedup`, alertas por réplica, dashboards y runbooks (10–15), escenarios en kind por el operador (16), documentación y cierre (17–18). Trazabilidad de US-503..505, diseño y propiedades; tabla de cumplimiento. Esperando aprobación del plan.
**Context**: CONSTRUCTION - U11 - Code Generation Part 1, esperando aprobación.

---
## U11 Code Generation Part 1 — Ajustes al plan
**Timestamp**: 2026-10-10T16:21:09Z
**User Input**: "Ajustes en el plan de U11

Paso 11: agrega las sondas del Deployment (livenessProbe sobre /healthz y readinessProbe sobre /readyz, ambas en 8081) y una verificación en conftest de que existen. Agrega también el Server y la AuthorizationPolicy de Linkerd (solo Prometheus y las sondas del kubelet).
Paso 6, aceptación: agrega pruebas de:
SIGTERM: no toma ciclos nuevos, termina la página en curso en ≤ 10 s y descarta la pasada a medias;
el desfase de 0 a 10 min de la pasada diaria (NFR-U11-04);
los 6 reintentos de la pasada completa cada 15 min, con reloj simulado (NFR-U11-09).
Paso 6, readiness: agrega el caso «primera pasada vencida con U3 lento y sin 3 fallos seguidos → 503»."
**AI Response**: Aplicados. Paso 11: `livenessProbe` (`/healthz`) y `readinessProbe` (`/readyz`) en 8081, `Server` y `AuthorizationPolicy` de Linkerd solo para Prometheus con las sondas del kubelet por la autorización automática, y su verificación en `conftest`. Paso 6: pruebas de `SIGTERM` (sin ciclos nuevos, página en curso ≤ 10 s, pasada a medias descartada), del desfase de 0 a 10 min, de los 6 reintentos cada 15 min con reloj simulado y del caso de readiness «primera pasada vencida con U3 lento y sin 3 fallos seguidos → 503».
**Context**: CONSTRUCTION - U11 - Code Generation Part 1, esperando aprobación.

---
## U11 Code Generation Part 1 — Aprobación
**Timestamp**: 2026-10-10T16:22:22Z
**User Input**: "Approve Plan"
**AI Response**: Plan de tareas de U11 aprobado. U11 queda cerrada (Code Generation Part 2 y Build and Test fuera de alcance). Siguiente: U12 system-verification — Functional Design.
**Context**: CONSTRUCTION - U11 cerrada; inicia U12 Functional Design.

---
## U12 Functional Design — Plan y preguntas
**Timestamp**: 2026-10-10T16:23:52Z
**User Input**: (sin entrada nueva; continúa tras "Approve Plan" de U11)
**AI Response**: Creado `construction/plans/system-verification-functional-design-plan.md` con 10 preguntas: qué envía el simulador (Q1), verificación de cada RT con oráculo (Q2), X01–X10 sobre la suite de U1 más pruebas de comportamiento (Q3), carga combinada de US-609 (Q4), conductor de decisiones para kind y staging (Q5), volúmenes de demostración (Q6), latencia de RT-2 con 5 corridas (Q7), guiones de las demos con verificación (Q8), dónde corre cada cosa (Q9), informe generado desde las evidencias (Q10). Hallazgo: las demos de U11 y la disparidad humana de U9 necesitan `human_decision`, que el simulador no crea.
**Context**: CONSTRUCTION - U12 - Functional Design, esperando respuestas.

---
## U12 Functional Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T16:28:12Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q10 = A, con notas en Q1, Q5, Q6 y Q7. Comprobaciones: U5 trae `train`/`validation`/`test` y el manifiesto adversarial (pares RT-1, 18 casos RT-4, 4 paquetes RT-3), sin una población `rt2_proxy`: la variante proxy es un modelo, así que RT-2 usa una muestra estratificada de `test` (sin cambio a U5); `analista-1` y `analista-2` ya existen en U2 §3; BR-U8-15 no exige asignación y la consulta de la explicación no exige MFA (C03). Corregido respecto de la pregunta Q2: RT-4 son los 18 casos de U5, no 200. Creados `construction/system-verification/functional-design/business-rules.md` (BR-U12-01..11), `domain-entities.md` y `business-logic-model.md` (orden de la verificación, conductor, PBT-U12-01..04, pruebas de ejemplo, cumplimiento). Cambio a U11: el plan (Paso 16) verifica en kind el día siguiente a las decisiones y deja `RuidoExplicacion` para `promtool` y el reloj simulado. Checklist marcado.
**Context**: CONSTRUCTION - U12 - Functional Design, esperando aprobación.

---
## U12 Functional Design — Condición para aprobar
**Timestamp**: 2026-10-10T16:30:56Z
**User Input**: "Condicion para aprobarCondición. El informe tiene una fila por historia (US-101, 106, 109, 111, 303, 305, 603, 604 y 609). Ningún documento dice qué RT, X o demo cubre cada una. Sin esa tabla, el generador del informe no puede decidir cuándo una historia pasa. Agrega en domain-entities.md §4 un mapa historia → evidencias."
**AI Response**: Agregado en domain-entities §4.1 (identificadores de evidencia nuevos: `SIM-NORMAL`, `RT2-LATENCY`, `LOGS-NO-PII`, `LOAD`, `CASE-SIZE`) y §4.2 (mapa historia → evidencias para las 9 historias, con la regla: pasa si todas pasan, falla si alguna falla, si no `no ejecutado`; vive en `story-map.yaml` y el generador falla ante una historia sin fila o una evidencia desconocida). Para US-604 hacía falta una evidencia de logs sin PII que no existía: BR-U12-12 (consulta de Loki por los identificadores `SYN-` y los nombres de U5, 0 resultados). BR-U12-13 con la regla; PBT-U12-02, pruebas de ejemplo y el orden de la verificación actualizados.
**Context**: CONSTRUCTION - U12 - Functional Design, esperando aprobación.

---
## U12 Functional Design — Aprobación
**Timestamp**: 2026-10-10T16:33:18Z
**User Input**: "Continue to Next Stage"
**AI Response**: Functional Design de U12 aprobado. Inicia NFR Requirements de U12 (NFR Design: SKIP según `aidlc-state.md`).
**Context**: CONSTRUCTION - U12 - Functional Design aprobado.

---
## U12 NFR Requirements — Plan y preguntas
**Timestamp**: 2026-10-10T16:35:00Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/system-verification-nfr-requirements-plan.md` con 9 preguntas: desde dónde corren las herramientas (Q1), barreras contra el entorno equivocado (Q2), credenciales solo en memoria (Q3), reproducibilidad (Q4), integridad de las evidencias (Q5), duración y ejecución por secciones (Q6), stack (Q7), calidad del código de U12 (Q8), trazabilidad de una corrida (Q9).
**Context**: CONSTRUCTION - U12 - NFR Requirements, esperando respuestas.

---
## U12 NFR Requirements — Respuestas y artefactos
**Timestamp**: 2026-10-10T16:35:44Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q9 = A, con notas (identidad de lectura a definir en el Infrastructure Design; tamaño de `test` y celdas insuficientes en la evidencia, con `rt2` que se niega; límite del manifiesto y protección por `CODEOWNERS`; esperas de PRs fuera del presupuesto; `decisions` dentro de un día UTC). Creados `construction/system-verification/nfr-requirements/nfr-requirements.md` (NFR-U12-01..50) y `tech-stack-decisions.md`. Pendientes para el Infrastructure Design: identidad de lectura (posible cambio a U2), imagen y contenedor de k6, `CODEOWNERS` de las evidencias. Checklist marcado.
**Context**: CONSTRUCTION - U12 - NFR Requirements, esperando aprobación.

---
## U12 NFR Requirements — Condición para aprobar
**Timestamp**: 2026-10-10T16:39:10Z
**User Input**: "condiciones para aprobar

Condición. Agrega a los pendientes del Infrastructure Design (§8 de nfr-requirements.md) dos puntos que hoy chocan con el diseño de «fuera del clúster y solo lectura»:

X04 y X06:
X04 exige llamar a governance con la identidad de bias-monitoring-job.
X06 exige un UPDATE con registry_app en la base.
Ninguna de las dos cosas se puede hacer desde fuera del clúster con solo get y auth can-i (NFR-U12-43).
El Infrastructure Design debe decidir el mecanismo. Puede ser un Job de demostración de U1 o U4 que U12 solo lee, como el Job de RT-5 de U8, o permitir kubectl exec en NFR-U12-43 con su justificación.
Acceso desde fuera: el gateway solo expone /api/intake/** y /api/console/**. El registro, Prometheus y Loki son internos. NFR-U12-02 define la identidad de lectura, pero no el camino de acceso, que puede ser port-forward o una ruta publicada.

Nota. BR-U12-03 dice «TOTP desde ESO» y NFR-U12-04 dice «Vault con la sesión del operador». Unifica la redacción. No bloquea."
**AI Response**: Agregados a nfr-requirements §8 los dos pendientes: el mecanismo de X04 y X06 (Job de demostración de la unidad dueña que U12 solo lee, o `kubectl exec` con justificación) y el camino de acceso a registro, Prometheus y Loki (port-forward o ruta publicada, con su efecto en X09). Unificada la redacción: BR-U12-03 y NFR-U12-04 dicen que las credenciales se leen del Vault de kind o la bóveda de staging con la sesión del operador, en las mismas rutas que usa ESO, y que la herramienta no usa ESO.
**Context**: CONSTRUCTION - U12 - NFR Requirements, esperando aprobación.

---
## U12 NFR Requirements — Aprobación
**Timestamp**: 2026-10-10T16:42:08Z
**User Input**: "Continue to Next Stage"
**AI Response**: NFR Requirements de U12 aprobado. NFR Design: SKIP. Inicia Infrastructure Design de U12.
**Context**: CONSTRUCTION - U12 - NFR Requirements aprobado.

---
## U12 Infrastructure Design — Plan y preguntas
**Timestamp**: 2026-10-10T16:42:08Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/system-verification-infrastructure-design-plan.md` con 5 preguntas: mecanismo de X04 y X06 con Jobs de prueba de U9 y U3 que U12 solo lee (Q1), camino de acceso a registro, Prometheus y Loki con `port-forward` y un cliente `verification-reader` solo en kind y staging, con la medición de la latencia de RT-2 (Q2), evidencias en el monorepo por PR (Q3), capacidad de kind para la carga (Q4), imagen y entornos (Q5).
**Context**: CONSTRUCTION - U12 - Infrastructure Design, esperando respuestas.

---
## U12 Infrastructure Design — Corrección del plan
**Timestamp**: 2026-10-10T16:44:00Z
**User Input**: (sin entrada nueva)
**AI Response**: Al revisar U1 se corrigió el plan: kind tiene 4 workers (no 6) en Q4, y se agregó un hallazgo: el inventario y U1 ubican `channel-simulator` dentro del clúster (`vectra-mock`), lo que contradice NFR-U12-01; el Infrastructure Design registrará el cambio de `vectra-mock` y del origen de F07.
**Context**: CONSTRUCTION - U12 - Infrastructure Design, esperando respuestas.

---
## U12 Infrastructure Design — Respuestas y artefactos
**Timestamp**: 2026-10-10T16:46:37Z
**User Input**: "ya respondí"
**AI Response**: Respuestas Q1–Q5 = A, con notas. Creados `construction/system-verification/infrastructure-design/infrastructure-design.md` (INF-U12-01..05) y `deployment-architecture.md`. Correcciones al FD aprobado de U12 encontradas por las notas: (1) el registro no guarda `free_text` (BR-U0-95), así que RT-1 se verifica por el BFF con `analista-1` y no hace falta un scope sensible (BR-U12-04); (2) el inicio de la latencia de RT-2 pasa a ser el menor `recorded_at` del lote, la única definición conservadora (BR-U12-07, `Rt2Measurement`, PBT-U12-04). Otros cambios: BR-U12-05 (X04 y X06 desde Jobs de prueba); NFR-U12-43 (`logs` y `port-forward`); planes de U9 (`x04-probe`) y U3 (`x06-probe`) solo en kind; U2 (`verification-reader` solo en kind y staging); binding K16 en el inventario y en NFR-U1-27; `channel-simulator` fuera del clúster en el inventario (§1, F07) y en U1 (deployment-architecture, plan Paso 3); equipos `calidad` y `cumplimiento` en `CODEOWNERS`. Checklist marcado.
**Context**: CONSTRUCTION - U12 - Infrastructure Design, esperando aprobación.

---
## U12 Infrastructure Design — Correcciones antes de aprobar
**Timestamp**: 2026-10-10T16:53:23Z
**User Input**: "Corregir antes de aprobar

Flujo de red de X06. El Job x06-probe necesita un flujo propio hacia registry-db-rw, porque U1 aplica deny-all. Sin él, X06 daría timeout en vez de permission denied. Se registra como flujo nuevo en component-dependency.md, flows.yaml y los Pasos 3 de U1 y 13 de U3. Para X04, hay que confirmar que el selector de F27 admite los pods de ese Job.
K16 completo. INF-U12-05 y NFR-U12-10 leen nodos, InferenceService y digests, pero K16 solo da get sobre pods, jobs y hpa. Faltan nodes (con un ClusterRole) y inferenceservices, además de los namespaces de cada lectura. En U1, además, ningún paso crea el binding K16 ni lo prueba con kyverno test.
Jobs de prueba y Argo CD. Quita ttlSecondsAfterFinished de x04-probe y x06-probe, igual que en los Jobs de reconstrucción: sin TTL y con poda al cambiar el runId. Con TTL, a las 24 h la Application queda OutOfSync y el siguiente sync repite el Job. Además hay que aclarar que probes.runId no choca con “sin runId no hay recursos” en chart-rebuild/."
**AI Response**: Corregidos. (1) Flujo F111 (`x06-probe` → `registry-db-rw`, solo kind) en el inventario, `flows.yaml` (Paso 3 de U1) y el Paso 13 de U3; rango F01–F111. F27 selecciona por la etiqueta `vectra.io/workload: bias-monitoring-job`, que llevan también los pods de `x04-probe` (con la misma `ServiceAccount`), así que el rechazo es el 403 de Linkerd; prueba de `generate.py`. (2) K16 completo: `ClusterRole` para `nodes`, `Role` por namespace para `pods` (seis namespaces, digests), `jobs` y `pods/log` en `vectra-app`, HPA en `vectra-app` y `vectra-edge`, `inferenceservices` en `vectra-serving`, `pods/portforward` en `vectra-app` y `vectra-observability`; creado en el Paso 5 de U1 (`platform/rbac/verification-operator/`, solo kind y staging) con `conftest` sobre el render de producción y `kyverno test`. (3) `x04-probe` y `x06-probe` sin `ttlSecondsAfterFinished`, podados al cambiar `probes.runId`; en `chart-rebuild/`, `probes.runId` y `monitoringRebuild.runId` son independientes («sin ninguno de los dos no hay recursos»), con su `conftest`; BR-U3-17 y los planes de U3 y U9 actualizados.
**Context**: CONSTRUCTION - U12 - Infrastructure Design, esperando aprobación.

---
## U12 Infrastructure Design — Cambios para el plan de tareas
**Timestamp**: 2026-10-10T16:56:36Z
**User Input**: "ambios para el plan de tareas de U12:

K16 sin los HPA de vectra-serving. Falta el permiso get, list y watch sobre horizontalpodautoscalers en ese namespace. Sin él, BR-U12-08 no puede leer los HPA de KServe en RawDeployment, ni INF-U12-05 sumar sus máximos.
Evidencia vieja de X04 y X06. Sin TTL, un Job completado se queda en el clúster. El oráculo de U12 debe comprobar que el runId coincide con el del manifiesto y que completionTime es posterior al inicio de la verificación."
**AI Response**: Aplicados en el Infrastructure Design (INF-U12-02 y 03), el inventario (K16) y el FD (BR-U12-05 y pruebas de ejemplo): K16 con `get`, `list` y `watch` sobre `horizontalpodautoscalers` en `vectra-serving`; el oráculo de X04 y X06 acepta un Job solo si su `runId` es el del manifiesto y su `completionTime` es posterior al inicio de la verificación, y si no lo marca `no ejecutado`. Se trasladan al plan de tareas cuando se apruebe el Infrastructure Design (el mensaje no lo aprobó de forma explícita).
**Context**: CONSTRUCTION - U12 - Infrastructure Design, esperando aprobación.

---
## U12 Infrastructure Design — Aprobación
**Timestamp**: 2026-10-10T16:59:00Z
**User Input**: "Continue to Next Stage"
**AI Response**: Infrastructure Design de U12 aprobado. Inicia Code Generation Part 1 (plan de tareas) de U12, con los dos cambios del mensaje anterior (HPA de `vectra-serving` en K16 y evidencia vieja de los Jobs de prueba) incluidos en los Pasos 9 y 11.
**Context**: CONSTRUCTION - U12 - Infrastructure Design aprobado.

---
## U12 Code Generation Part 1 — Plan de tareas
**Timestamp**: 2026-10-10T16:59:20Z
**User Input**: (sin entrada nueva; continúa tras "Continue to Next Stage")
**AI Response**: Creado `construction/plans/system-verification-code-generation-plan.md` con 19 pasos en 8 bloques: estructura y barreras (1–2), lógica pura con PBT-U12-01, 02, 04 (3–4), clientes, simulador y conductor con PBT-U12-03 (5–6), escenarios RT, X y mediciones con oráculos probados contra respuestas incorrectas y la carga (7–11), demos, CLI por secciones, manifiesto y `CODEOWNERS` (12–13), N/A, imagen, CI y documentación (14–17), primera verificación completa en kind por el operador (18), cierre (19). Esperando aprobación del plan.
**Context**: CONSTRUCTION - U12 - Code Generation Part 1, esperando aprobación.

---
## U12 Code Generation Part 1 — Correcciones antes de aprobar
**Timestamp**: 2026-10-10T17:02:10Z
**User Input**: "Corregir antes de aprobar

Frescura de X04 y X06 (bloqueante). El Paso 18 exige que los Jobs de prueba ya estén sincronizados antes de empezar. El Paso 9 exige que su completionTime sea posterior al started_at del manifiesto. Con ese orden, los Jobs siempre terminan antes y X04 y X06 salen siempre no ejecutado. La salida es una sección prepare previa al PR de los Jobs, que fije el runId y el started_at. Afecta los Pasos 9, 13 y 18.
RT-2 sin el paquete completo. BR-U12-04 y el Paso 16 de U9 piden verificar data_sources e initial_disparity en el freeze. El Paso 8 no lo comprueba. Falta el oráculo y su prueba con un paquete incompleto → falla.
Step-up de MFA sin navegador. La reactivación de RT-2 depende de él. Hay que fijar en el Paso 5 cómo un cliente sin navegador completa el flujo de code y state del BFF."
**AI Response**: Corregidos. (1) Sección `prepare` (Paso 13) que fija `runId` y `started_at` y produce el parche de values para el PR de los Jobs de prueba; las demás secciones se niegan sin ella; Paso 9 compara con ese `started_at`; Paso 18 con el orden `prepare` → PR y sync de los Jobs → `network` y siguientes; orden de business-logic-model §2.1 actualizado. (2) Oráculo del paquete completo de RT-2 en el Paso 8 (`FreezeContext` válido según U0 §9.4 más `data_sources` e `initial_disparity` no vacíos, leídos por `monitoring_freezes`), con prueba de un paquete incompleto → `falla`; BR-U12-04 precisado. (3) Paso 5: el BFF no hace el flujo OIDC; la herramienta actúa como el cliente `vectra-console` con PKCE, llena el formulario de Keycloak con Playwright y Chromium sin interfaz (contraseña y TOTP de `pyotp`), intercepta el `redirect_uri` antes de cargar la SPA, valida `state`, canjea el `code` y valida `nonce` y `acr`; prueba contra un Keycloak de Testcontainers; Playwright agregado al stack de U12.
**Context**: CONSTRUCTION - U12 - Code Generation Part 1, esperando aprobación.

---
## U12 Code Generation Part 1 — Aprobación
**Timestamp**: 2026-10-10T17:05:37Z
**User Input**: "Approve Plan"
**AI Response**: Plan de tareas de U12 aprobado. U12 queda cerrada. Con esto, todas las unidades (U0–U12) están cerradas en su plan de tareas aprobado; Code Generation Part 2, Build and Test y OPERATIONS quedan fuera del alcance actual, según la instrucción del usuario registrada en `aidlc-state.md`.
**Context**: CONSTRUCTION cerrada en los planes de tareas.

---
## Pendientes tras el cierre de CONSTRUCTION — Solicitud
**Timestamp**: 2026-10-10T17:56:06Z
**User Input**: "realizar estos pendientes

U12 (plan de tareas y diseño)
deployment-architecture §2 todavía pone el PR de los Jobs como paso 1. Falta prepare. NFR-U12-30 tampoco lista prepare entre las secciones.
El Job de RT-5 no tiene la regla de frescura (mismo runId y completionTime posterior a started_at). El Paso 8 no la menciona.
El Paso 13 no aclara qué runId guarda el manifiesto (x04, x06 y RT-5).
prepare debe negarse a correr si ya existe un manifiesto de esa verificación. Si no, se reinicia started_at a mitad de camino.
Chequeos de NFR sin paso:
Cobertura ≥ 85 % en el resto del código (NFR-U12-40).
Tiempo medido en el informe (NFR-U12-31).
Solicitudes repetidas en el manifiesto (NFR-U12-11).
Consultas de Prometheus y Loki guardadas como evidencia (NFR-U12-50).
k6 está en la imagen, pero el diseño lo quiere en un contenedor aparte de 2 CPU y 2 GiB. El README no dice cómo llegan el kubeconfig y la sesión de Vault al contenedor sin escribirse en disco.
Las demos US-304, 503, 504 y 505 (§1 y trazabilidad) no aparecen en domain-entities §4. Hay que citar su origen o quitarlas.
Login con Playwright:
Keycloak rechaza reusar un código TOTP en la misma ventana de 30 s, así que dos logins seguidos de cumplimiento-1 deben esperar a la ventana siguiente.
Chromium sin privilegios necesita resolver el sandbox.
Infrastructure Design de U12 (menores)
La regla de K16 que rechaza delete y exec debe aplicarla conftest, no disallow-rbac-wildcards.
Textos viejos “K01–K14” en component-dependency §9.4 y en application-design (SECURITY-06 y encabezado).
El §4 de registry_app no menciona x06-probe. El §1 del contenido de vectra-app omite los Jobs de prueba.
U3, Pasos 12, 13 y 15: siguen diciendo “sin/solo con monitoringRebuild.runId”. El Paso 13 debe nombrar F111 en la aceptación.
platform/rbac/ no está en el árbol de U1.
El grupo de operadores de K16 no está definido.
No está claro si el Job de X04 envía un token.
deployment-architecture no describe el camino estación → gateway (IP, host, CA) ni quién hace commit y abre el PR de evidencia.
generate.py necesita un tipo de origen externo para F07. Hay que revisar las cuotas de U8 y de vectra-mock.
Confirmar que la proyección metrics de U3 devuelve case_id y recorded_at, y que FreezeSummary expone el recorded_at del freeze.
U9 Paso 12 y U3 Paso 12 no nombran el conftest de los Jobs de prueba en la aceptación. U2 Paso 3 no tiene casos nombrados de realm-lint para verification-reader.
Heredados de otras unidades
U0
Falta el breaker de deps.call (3 fallos seguidos, semiabierto a los 60 s, 1 éxito), con test_deps.py y una extensión de PBT-U0-14.
test_ops_server.py no está en la aceptación del Paso 10, y ops_server.py no está en el árbol del Paso 1.
U1
El Paso 3 no nombra F109 ni F110.
El Paso 6 conserva las cifras de 3 pods de U11 y U9, sin el margen del 30 %.
Falta un caso nombrado de require-hpa-bounds para product-metrics.
Falta una nota en el runbook sobre la sincronización de U11 (≈ 2,5 h).
U2: faltan casos nombrados de realm-lint para product-metrics y para el MFA de operacion.
U3
Faltan pruebas de paginación (límite > 1 000 → 422; next_seq_after nulo al final) y seq_after en EntryFilter.
registry_ondemand no está en el Paso 2 ni en §1.2.
Falta la prueba first_evaluation en el Paso 8.
Falta el runbook RegistryOnDemandCheckStuck.
U8: faltan cases.ever_degraded, received_at y first_evaluation.
U11
for de ProductMetricsStale.
Texto viejo de absent().
Exclusión del full-pass.
NFR-U11-04.
Casos de readiness de NFR-U11-07.
GrafanaFolderPermissionsDrift frente a las cuatro alertas.
La etiqueta month."
**AI Response**: Pendientes aplicados (2026-10-10T18:05:37Z), cada cambio marcado «pendientes posteriores al cierre, 2026-10-10»:
- U12: `prepare` en deployment-architecture y NFR-U12-30; frescura de RT-5; `runId` del manifiesto; `prepare` rechaza si ya hay manifiesto; pasos para ≥ 85 % de cobertura, tiempo por sección, solicitudes repetidas y consultas guardadas; k6 en su propio contenedor `grafana/k6`; credenciales en el README; demostraciones de US-304 y US-503..505; espera de la siguiente ventana TOTP en Playwright; sandbox de Chromium por perfil seccomp (nunca `--no-sandbox`); camino de la estación (§2b).
- Inventario y U1: F109, F110, F111 y K16 (con regla `conftest`), textos de K01–K14 y K16, filas `registry_app`, `registry_ondemand` y `vectra-app`, origen externo de F07; Paso 6 con las cifras de U8, U9 y U11 y el margen del 30 %; caso `require-hpa-bounds` de `product-metrics`; nota de sync de ≈ 2,5 h; `rbac/verification-operator/` en el árbol.
- U2: casos de `realm-lint` para `verification-reader`, `product-metrics` y MFA de `operacion`.
- U0: modo `consecutive_failures` del breaker (NFR-U0-23 (i), PBT-U0-14, logical-components, Paso 10 con `test_deps.py`); `test_ops_server.py` en la aceptación del Paso 10; `deadline.py`, `process.py` y `ops_server.py` en el árbol; `EntryFilter` y `Page.next_seq_after` en domain-entities §9.6 con su prueba en el Paso 3.
- U3: `registry_ondemand` y sus grants en el Paso 2 (ya estaba en domain-entities §1.2); pruebas de paginación y de `first_evaluation` en el Paso 8; `runId` independiente de `probes.runId`; F111 y `conftest` de `x06-probe`; `recorded_at` en `monitoring_freezes`; Paso 14 con 15 alertas (14 filas) y los runbooks que faltaban (`registry-full-verification-overdue`, `registry-verification-failed`, `checkpoint-export-failed`, `registry-entry-large`); fila `MonitoringAggregatorStale` devuelta a la tabla de P-U3-09.
- U8: columna `cases.ever_degraded` (Paso 3); `received_at` y `first_evaluation` en el `ScoringRequest` (Paso 15) con pruebas; Job `rt5-demo-<runId>` (Paso 20 e INF-U8-03), sin TTL, con `conftest`; cuotas de INF-U8-05 recalculadas.
- U9: `x04-probe` con token y 403 de Linkerd; cuota de 4 pods.
- U11: `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing` en dos reglas (edad `for: 0`, ausencia `for: 30m` / `26h`), las dos excluyen la pasada, coherente en BR-U11-14, NFR-U11-08, NFR-U11-42 y P-U11-06; textos de `absent()` retirados; `GrafanaFolderPermissionsDrift` marcada como de U1 (U11 tiene cuatro alertas); NFR-U11-04 con prueba determinista; NFR-U11-07 con los casos de readiness; etiqueta `month` en domain-entities §5.
- `aidlc-state.md`: fila nueva en «Revisiones posteriores a la aprobación».
**Context**: Pendientes posteriores al cierre de CONSTRUCTION.

---

---

## Consulta de estado tras los pendientes
**Timestamp**: 2026-10-10T18:15:43Z
**User Input**: "cual es su estado"
**AI Response**: Estado informado: INCEPTION completa; CONSTRUCTION cerrada en el plan de tareas de U0–U12 (Code Generation Part 2, Build and Test y OPERATIONS fuera de alcance por instrucción del usuario); lote de pendientes posteriores al cierre aplicado; cambios sin commit en el repositorio.
**Context**: Consulta de estado; sin cambios a los documentos de diseño.

---

## Pendientes consolidados — Solicitud
**Timestamp**: 2026-10-10T19:09:46Z
**User Input**: "pendiente consolidados

U12 (infrastructure-design, deployment-architecture, plan)
rt5-demo solo en kind. INF-U12-02 acota a kind solo x04-probe y x06-probe. Hay que decir “los tres Jobs” y agregar el conftest de U8 que rechaza probes.runId en staging y producción.
Formato del runId. Falta fijar AAAAMMDD-HHMM, derivado de started_at, con una prueba. El check de GitOps de U3 lo exige.
Tres Applications. El parche de prepare toca los values de U9, de U3 (chart-rebuild/) y de U8. Hay que sincronizar tres Applications, y lo mismo vale para el Paso 18 del plan y el README.
Dónde corre k6. Unificar en que siempre va en su propio contenedor, lanzado por el operador. NFR-U12-01 dice “si la estación no alcanza”, y el diagrama dice siempre. El k6 inspect del Paso 11 necesita k6 en CI.
port-forward a un Service. K16 no da get sobre services. Agregarlo en vectra-app y vectra-observability, o aclarar que el port-forward va al pod.
Oráculo de RT-5. auth can-i para tres identidades exige impersonación, que K16 no tiene, e INF-U8-03 solo demuestra una. Usar el 403 del proxy, la alerta y el contador en 0. Las otras dos identidades las cubre X01.
FreezeRecord.recorded_at. Confirmar que U12 lee el recorded_at de la entrada freeze (el sobre). Si es así, U0 no cambia.
Redacción del plan. Frase suelta en el Paso 15 (“construida, escaneada, con SBOM y firmada…”).
Cobertura. El Paso 16 no tiene el comando --cov-fail-under=85.
Modelo de lógica §2.2. Dice “TOTP desde ESO”, y NFR-U12-04 dice Vault.
U8 (infrastructure-design y plan)
ever_degraded sin permiso. Agregar la columna al UPDATE de case_worker en INF-U8-01 y en component-dependency §4. No debe estar en el de case_app. Verificación: el worker la pone en true, case_app recibe error de permisos y el trigger impide volver a false.
rt5-demo en staging. INF-U8-03 y el Paso 20 del plan dicen “kind y staging”. Debe ser solo kind. El conftest debe rechazar también staging y no solo producción.
Memoria de vectra-mock. Los limits dicen 749 MiB. Con el proxy de 128 MiB da ≈ 998 MiB (3 × 256 × 1,3). Corregir también en U1 Paso 6.
U9
x04-probe en el Infrastructure Design. Falta un bullet en INF-U9-04, otro en §7 y una fila en §6, con el runId, solo kind y el conftest. INF-U12-02 ya describe el Job completo.
U11
“Breaker propio”. Aparece en P-U11-01, NFR-U11-09 y los Pasos 2 y 4 del plan. Debe decir que usa deps.call en modo consecutive_failures de U0, con 3 fallos, 60 s y 1 éxito.
last_full_recompute_timestamp al arrancar. Debe no emitirse hasta la primera pasada exitosa. Si arranca en 0 con U3 caído, ProductMetricsFullRecomputeMissing dispara de inmediato. Agregar un caso de promtool.
35 o 36 días. BR-U11-11 dice “36 días” en la recomputación diaria y todo lo demás dice 35.
Cosmético
E8 aparece antes de E6 en P-U11 §3."
**AI Response**: Pendientes consolidados aplicados (2026-10-10), cada cambio marcado «pendientes consolidados, 2026-10-10»:
- U12: «los tres Jobs» (`x04-probe`, `x06-probe`, `rt5-demo`) solo en kind, con `conftest` de U9, U3 y U8 que rechaza `probes.runId` en staging y producción; `runId` `AAAAMMDD-HHMM` de `started_at` en UTC con prueba (Pasos 13 y 18, INF-U12-02); un PR y sync manual de tres Applications (`bias-monitoring`, `decision-registry-rebuild`, `case-management`) en INF-U12-02, deployment-architecture, Pasos 17 (README) y 18; k6 siempre en su contenedor `grafana/k6` (NFR-U12-01, diagrama en texto, Pasos 11, 15 y 16 con `k6 inspect` en CI); `port-forward` siempre a un pod (K16 sin `services`); oráculo de RT-5 = 403 del proxy, `CoreWriteAttempt` y contador en 0, sin `auth can-i` de otras identidades (BR-U12-04, Paso 8); `recorded_at` del `freeze` leído del sobre `RegistryEntry` por `GET /v1/entries`: U0 no cambia (INF-U12-03, U3 domain-entities y Paso 8); frase separada en el Paso 15; `--cov-fail-under=85` en el Paso 16; BLM §2.2 con Vault; filas nuevas en INF-U12 §6.
- U8: `ever_degraded` en el `UPDATE` de `case_worker` (INF-U8-01 y `component-dependency.md` §4), excluida de `case_app`, con pruebas (worker → éxito, `case_app` → permisos, volver a `false` → trigger `guard_ever_degraded`); `rt5-demo` solo en kind con `conftest` que rechaza staging y producción (INF-U8-03, Paso 20); memoria de `vectra-mock` ≈ 998 MiB de limits (3 × 256 × 1,3) en INF-U8-05 y en U1 Paso 6.
- U9: Job `x04-probe` en INF-U9-04 (bloque propio), §6 y §7; etiqueta de F27 alineada con el inventario (`vectra.io/workload: bias-monitoring-job`).
- U11: «breaker propio» reemplazado por el breaker de `deps.call` en modo `consecutive_failures` de U0 (3, 60 s, 1) en NFR-U11-09, P-U11-01, INF-U11 y Pasos 2 y 4; `vectra_product_last_full_recompute_timestamp` no se emite hasta la primera pasada completa exitosa, con caso de `promtool` y prueba de `/metrics`; 35 días en BR-U11-11 y P-U11-01; E6–E8 en orden.
**Context**: CONSTRUCTION cerrada en los planes; lote de correcciones consolidadas.

---

## Pendientes consolidados (segunda tanda) — Solicitud
**Timestamp**: 2026-10-10T19:21:00Z
**User Input**: "Pendientes consolidados

U12 system-verification (plan de tareas)
Paso 5. Dice «port-forward a decision-registry-service». Debe decir «a un pod de» (la regla es port-forward siempre a un pod, nunca a svc/…).
Paso 15. Dice que la sección load lanza k6, pero NFR-U12-01 y la arquitectura dicen que lo lanza el operador. Falta definir cómo vuelve el resultado: k6 escribe su resumen en el directorio de evidencia montado, y load imprime el comando exacto y lee ese resumen.
Paso 8 (oráculo de RT-5). rt5 corre horas después del Job, y CoreWriteAttempt usa una ventana de 5 minutos. Hay que anclar la consulta en el completionTime del Job rt5-demo y agregar una prueba.
Datos de demostración. No hay una línea que fije su volumen para la prueba de U11 en kind (ver U11, punto 1).
U8 case-management
INF-U8-03, línea final. Dice «Solo existe en kind y staging, como el mock». Debe decir que la alerta y el mock existen en kind y staging, y que el Job rt5-demo es solo kind.
§7. Falta una fila que registre los cambios de ever_degraded (permisos de case_worker) y de rt5-demo solo en kind.
U9 bias-monitoring
INF-U9-04, secreto de x04-probe. Debe decir que reutiliza el ExternalSecret del CronJob, sin Secret nuevo, como x06-probe.
INF-U9-04, red. Debe aclarar si F50 (token de Keycloak) selecciona por vectra.io/workload: bias-monitoring-job. Si no, el Job no obtiene token y la prueba da timeout. Falta un caso de conectividad x04-probe → Keycloak permitido.
INF-U9-01, cuota. Una línea que diga que el pod transitorio de x04-probe no está en los 4 pods y que lo absorbe el margen del 30 %.
INF-U9-04, verificación. El bloque del probe no tiene su propia línea de «Verificación».
Plan de U9, Paso 12. No lo re-subiste; no puedo confirmar que tenga la aceptación del conftest de probes.runId.
U11 product-metrics
INF-U11-06 y última fila de §7. Siguen diciendo que los datos de demostración de U12 «no están definidos». Se cierra con el punto 4.
U3 decision-registry
Fila metrics de domain-entities §3. No menciona el filtro entry_type, el limit (≤ 1 000) ni next_seq_after, que U11 usa. Basta una línea de referencia al Paso 8 del plan."
**AI Response**: Segunda tanda aplicada (marcas «pendientes consolidados, segunda tanda, 2026-10-10»):
- U12 plan: Paso 5, `port-forward` a un pod de `decision-registry-service`; Pasos 11 y 15, k6 lo lanza el operador con el comando que imprime `load`, el resumen va a `evidence/…/load/k6-summary-<runId>.json` del directorio montado y `load` lo lee (ausente o viejo → `no ejecutado`); Paso 8, oráculo de RT-5 anclado en [startTime, completionTime + 15 min] del Job `rt5-demo` con `query_range` (alerta, denegaciones de Linkerd, contador del mock en 0), con pruebas y `no ejecutado` si la retención no cubre; Paso 6, volumen de demostración de 2 000 casos `normal` decididos (BR-U12-06).
- U8: línea final de INF-U8-03 (alerta y mock en kind y staging, `rt5-demo` solo kind); tres filas en §7 (`ever_degraded`, `rt5-demo`, memoria de `vectra-mock`).
- U9: `x04-probe` reutiliza el `ExternalSecret` del CronJob; F50 selecciona el CronJob y `x04-probe` por `vectra.io/workload: bias-monitoring-job` (INF-U9-04, `component-dependency.md` F50, plan Paso 12) con caso de conectividad `x04-probe` → Keycloak permitido; línea de cuota en INF-U9-01 (pod transitorio absorbido por el 30 %); bloque «Verificación del probe»; Paso 12 con `conftest` que rechaza `probes.runId` en staging y producción y sus fixtures.
- U11: INF-U11-06 y fila de §6/§7 cerradas con los 2 000 casos de U12.
- U3: fila `metrics` de domain-entities §3 con `entry_type`, `seq_after`, `limit` ≤ 1 000 y `next_seq_after`, con referencia a U0 §9.6 y al Paso 8.
**Context**: CONSTRUCTION cerrada en los planes; segunda tanda de correcciones consolidadas.

---

## Pendientes consolidados (tercera tanda) — Solicitud
**Timestamp**: 2026-10-10T19:26:53Z
**User Input**: "Pendientes consolidados

U12 system-verification (plan de tareas)
Paso 8, oráculo de RT-5. Usa increase(inbound_http_authz_deny_total{…}[…]) ≥ 1. La serie de Linkerd nace en 1 con la primera denegación (INF-U8-03 lo explica), así que increase() da 0 y el oráculo diría falla aunque el 403 ocurrió.
Cambio propuesto: max_over_time(…[t0, t1+15m]) >= 1, o la resta contra offset con or vector(0) de INF-U8-03.
Agregar una prueba donde la serie nace en 1.
U11 product-metrics
Plan, Paso 16. El requisito previo dice «datos de demostración de U12 (pendiente para U12)». Ya están definidos: 2 000 casos del Paso 6 de U12.
infrastructure-design, INF-U11-06 y última fila de §7. Siguen diciendo «no definidos» en la versión que vi. La auditoría dice que se corrigió, pero falta que re-subas el archivo para confirmarlo.
U3 decision-registry
Plan, Paso 8. Dice «aunque la consulta solo pida 36 días» y U11 ya usa 35.
domain-entities §3, fila metrics. Falta confirmar que tenga entry_type, seq_after, limit ≤ 1 000 y next_seq_after. La auditoría dice que se aplicó, pero la versión que vi es anterior. Falta que la re-subas.
U9 bias-monitoring (infrastructure-design)
INF-U9-01, cifras de la cuota. Las cifras de la línea del pod transitorio (≈ 0,24 CPU y 0,17 GiB; ≈ 1,2 CPU y 0,45 GiB) son el tamaño del margen del 30 %, no el del probe. Recalculé el probe: ≈ 0,20 CPU y 0,11 GiB de requests; ≈ 0,91 CPU y 0,33 GiB de limits. Hay que reformular la frase.
INF-U9-04, lista de flujos. Dice que F27 sale «solo del CronJob», pero la barrera de red 3 también admite a x04-probe en kind. Agregar «y, en kind, de x04-probe».
§7, último punto. El pendiente del Job x04-probe en el Paso 12 ya está aplicado y puede marcarse como resuelto."
**AI Response**: Tercera tanda aplicada (marcas «pendientes consolidados, tercera tanda, 2026-10-10»):
- U12 plan, Paso 8: RT-5 usa `max_over_time(sum(inbound_http_authz_deny_total{…})[t0, t1 + 15 min]) ≥ 1` en lugar de `increase()`, porque la serie nace en 1; pruebas nuevas: serie que nace en 1 y no crece → `pasa`; serie ausente → `falla`.
- U11 plan, Paso 16: requisito previo con los 2 000 casos de U12 (BR-U12-06, Paso 6). Confirmado con `grep`: INF-U11-06 (línea 120, fila kind de la tabla) y la fila de §6 ya citan los 2 000 casos; no queda «no definidos» ni «pendiente para U12» en U11.
- U3: Paso 8 con 35 días; confirmado que la fila `metrics` de domain-entities §3 tiene `entry_type`, `seq_after`, `limit` ≤ 1 000 y `next_seq_after`.
- U9 INF: frase del pod transitorio separada (probe ≈ 0,20 CPU / 0,11 GiB de requests y ≈ 0,91 CPU / 0,33 GiB de limits, frente al margen ≈ 0,24 / 0,17 y ≈ 1,2 / 0,45); F27 «solo del CronJob y, en kind, de `x04-probe`»; último punto de §7 marcado como resuelto.
**Context**: Tercera tanda de correcciones consolidadas.

---

## Pendientes abiertos — Solicitud
**Timestamp**: 2026-10-10T19:33:04Z
**User Input**: "Pendientes abiertos

Son dos y ninguno bloquea la aprobación.

#    Unidad    Dónde    Qué falta    Gravedad
1    U12    Plan, Paso 8, oráculo de RT-5    max_over_time(sum(...)[t0, t1 + 15 min]) no es PromQL válido sin subconsulta. Hay que fijar una de estas dos formas: max_over_time(sum(...)[ventana:paso]), o query_range con el máximo calculado en el oráculo. Conviene añadir una prueba contra promtool o un Prometheus real.    Menor, pero el oráculo fallaría al ejecutarse.
2    U3    domain-entities §1.2, tabla de roles    La fila registry_verifier tiene una celda de menos y su «Usado por» quedó dentro de los permisos. La fila registry_ondemand tiene una celda de más. Su «Usado por» («CLI y CronJob de verificación, restore-drill») parece copiado de registry_verifier, porque restore-drill es de solo lectura.    Cosmético, pero la columna puede dar a entender que restore-drill escribe."
**AI Response**: Aplicados (marca «pendientes abiertos, 2026-10-10»):
1. U12 plan, Paso 8: el oráculo de RT-5 usa `/api/v1/query_range` con `step = 15s` y expresiones instantáneas válidas (`ALERTS{…}`, `sum(inbound_http_authz_deny_total{…})`, `sum(vectra_core_write_attempts_total)`); el máximo y la presencia se calculan en Python; retención por `prometheus_tsdb_lowest_timestamp_seconds` ≤ t0. Prueba nueva `tests/integration/test_rt5_promql.py` contra un Prometheus real (Testcontainers) sobre un bloque creado con `promtool tsdb create-blocks-from openmetrics`, incluido el caso de la serie que nace en 1; corre en CI (Paso 16).
2. U3 domain-entities §1.2: fila `registry_verifier` con su celda «Usado por» restituida (pool `projections`, CLI y CronJobs de verificación y archivo en `-ro`, `restore-drill` de solo lectura); fila `registry_ondemand` sin la celda sobrante, con «Usado por» = solo la CLI de `registry-verify-ondemand`, y la aclaración de que ni la API ni `restore-drill` lo tienen. Las cinco filas tienen 3 celdas.
**Context**: Dos pendientes menores tras la tercera tanda.

---

## Pendientes abiertos (último) — Solicitud
**Timestamp**: 2026-10-10T19:36:22Z
**User Input**: "Pendientes abiertos

Queda uno solo. No bloquea la aprobación.

#    Unidad    Dónde    Qué falta    Gravedad
1    Transversal (U3 y U10)    component-dependency §4, fila registry_ondemand, columna «Usado por»    Dice «Los CronJobs de verificación (registry-verify-*)». Ese comodín incluye registry-verify-incremental y registry-verify-nightly, que leen con registry_verifier en registry-db-ro (F97). Debe decir «el CronJob registry-verify-ondemand», como en F97, domain-entities §1.2 y el Paso 12 del plan de U3.    Menor, solo redacción."
**AI Response**: Corregida la columna «Usado por» de la fila `registry_ondemand` en `component-dependency.md` §4: «El CronJob `registry-verify-ondemand`» (los demás `registry-verify-*` leen con `registry_verifier` en `registry-db-ro`, F97). La fila `registry_verifier` (pool `projections`, `registry-verify-*`, `registry-archive`, `restore-drill`) no cambia.
**Context**: Último pendiente abierto, solo redacción.

---

## Revisión de coherencia entre unidades — Solicitud
**Timestamp**: 2026-10-10T19:40:52Z
**User Input**: "revisar si las unidades son coherentes para el proyecto"
**AI Response**: Revisión transversal, sin cambios a los documentos. Controles que pasan: 89 flujos definidos y todas las referencias F existen; bindings K01–K14 y K16 (K15 retirado a propósito); catálogo de scopes de U0 = scopes de los clientes de U2; clientes de Keycloak referenciados existen en U2; rutas `/v1/…` referenciadas existen en component-methods; eventos de log dentro del catálogo de U0 §8.1; cifras del proxy (P-U1-14) iguales en todas las unidades; 49 historias en el mapa de unidades y en algún plan; nombres de K16 y de `probes.runId` / `monitoringRebuild.runId` consistentes; waves 0–6 coherentes.
Hallazgos: (1) cuota de `vectra-app`: U3 y U4 no declaran aporte y el de U7 (INF-U7-02) no incluye el proxy ni los pods del rollout; (2) el plan de U7 no tiene tarea ni prueba para copiar `received_at`, `channel`, `attempt` y `first_evaluation` al payload de `recommendation` (sí están en BR-U7 y U0 §5.3), y el Paso 3 de U0 no los prueba; (3) «Depende de» del plan de U12 cita la proyección `monitoring`, retirada; (4) la matriz de unit-of-work-dependency §1 no refleja dependencias que los planes sí declaran; (5) `ServingConfigStale` (NFR-U4-04) no está en P-U4-08 ni en el plan de U4; (6) `GrafanaFolderPermissionsDrift` y el Job de F110 solo aparecen en el plan de U1, no en sus documentos de diseño; (7) casillas genéricas de CONSTRUCTION sin marcar en aidlc-state.md. Se ofrece aplicar las correcciones.
**Context**: Revisión transversal de U0–U12 tras el cierre de CONSTRUCTION en los planes.

---

## Correcciones de la revisión de coherencia — Solicitud
**Timestamp**: 2026-10-10T19:45:54Z
**User Input**: "sí, aplica las correcciones con tu propuesta"
**AI Response**: Correcciones aplicadas (marca «revisión de coherencia entre unidades, 2026-10-10»):
1. Cuotas de `vectra-app`: INF-U3-03 con fila de la migración (100m / 128 MiB; 500m / 256 MiB) y aporte ≈ 6,70 CPU / 5,91 GiB de requests y ≈ 29,25 CPU / 13,49 GiB de limits (servicio con `maxSurge` + CronJobs, migración y un rebuild a la vez, con el proxy y el 30 %); INF-U4-01 con aporte ≈ 3,71 CPU / 2,99 GiB y ≈ 16,25 CPU / 6,99 GiB (`model-validation-job` va a `vectra-staging`); INF-U7-02 recalculado a ≈ 6,37 CPU / 4,91 GiB y ≈ 27,3 CPU / 11,38 GiB (14 pods con el proxy); U1 Paso 6 con las tres cifras, los Jobs de prueba de U12 absorbidos por el margen y la línea de diseño completa.
2. Plan de U7, Paso 11: tarea y prueba para copiar `received_at`, `channel`, `attempt` y `first_evaluation` al payload de `recommendation`; «Depende de» con esos campos de U0. Plan de U0, Paso 3: pruebas de que `ScoringRequest` y el payload los exigen.
3. Plan de U12: «Depende de» con `monitoring_freezes` (no la `monitoring` retirada), U4 y U6.
4. `unit-of-work-dependency.md`: matriz con U1 → U0, U3; U4 → U5, U6; U5 → U1, U9; U6 → U0, U4; U7 → U5; U11 → U7, U8; nota de las dependencias en dos sentidos sin ciclo (U5 ↔ U9, U1 → U3, U4 → U5/U6); grafo con U4 → U6, U7 → U11, U8 → U11 (sigue acíclico); orden en texto y tabla de recursos compartidos actualizados.
5. `ServingConfigStale` agregada a P-U4-08 y al plan de U4 (Paso 9: gauge `vectra_serving_config_age_seconds`, 503 a los 30 s, prueba con la base pausada corregida; Paso de alertas).
6. Diseño de U1: `GrafanaFolderPermissionsDrift` en logical-components; Job y CronJob `grafana-folder-permissions` (F110) en INF-U1. Hallazgo adicional corregido: la tabla de INF-U1 decía Pushgateway «sin persistencia», contra P-U1-13; ahora dice PVC de 1 GiB con `--persistence.interval=1m`.
7. `aidlc-state.md`: casillas de CONSTRUCTION marcadas (Build and Test y Operations siguen fuera de alcance) y fila nueva en «Revisiones posteriores a la aprobación».
**Context**: Aplicar los 7 hallazgos de la revisión de coherencia; cuotas de U3 y U4 dimensionadas con los recursos de sus Infrastructure Design, con el proxy, el `maxSurge` y el 30 %.

---

## Segunda revisión de coherencia entre unidades — Solicitud
**Timestamp**: 2026-10-10T19:54:53Z
**User Input**: "revisar si las unidades son coherentes para el proyecto"
**AI Response**: Segunda pasada, sin cambios a los documentos. Pasan otra vez: flujos, rutas, scopes y clientes, eventos de log; las correcciones de la primera pasada están en su lugar. Controles nuevos que pasan: PriorityClasses (`vectra-critical`, `-high`, `-normal`, `-low`) y namespaces usados existen en U1; las tres exenciones de HPA (bias, `console-spa`, `product-metrics`) coinciden en U1, U9, U10 y U11; cuotas de U10 y U11 iguales en su unidad y en U1 Paso 6; presupuestos de `max_connections` alcanzan; los Pasos citados entre unidades (U1 3, 5, 10, 11; U2 3; U3 12, 13, 15; U4 16; U8 20; U9 12, 16; U11 16) existen con el contenido esperado; `MonitoreoSesgoDetenido` cubre edad y ausencia.
Hallazgos: (1) `AuthDeniedBurst` está en la tabla de alertas de U1 (logical-components §3, cuyo plan crea «todas las alertas de §3») y en P-U2-09 (cuyo plan también la crea): quedaría dos veces en Prometheus; (2) NFR-U1-12 dice «salvo un Deployment» y lista tres; (3) el catálogo de componentes (`components.md`, `application-design.md`) describe `channel-simulator` como «CLI / Job», cuando ahora corre fuera del clúster en la imagen de U12, y no tiene `case-worker`, que U8 separó como Deployment con identidad propia. Se ofrece aplicar las correcciones.
**Context**: Segunda pasada transversal tras aplicar las correcciones de la primera.

---

## Correcciones de la segunda revisión de coherencia — Solicitud
**Timestamp**: 2026-10-10T19:57:33Z
**User Input**: "sí, aplica las correcciones con tu propuesta"
**AI Response**: Aplicadas (marca «segunda revisión de coherencia entre unidades, 2026-10-10»):
1. `AuthDeniedBurst` queda solo en U2 (P-U2-09): U1 logical-components §3 la marca como definida en U2, y el Paso 11 del plan de U1 la excluye de su `PrometheusRule`, con una comprobación de que ningún `alertname` de U1 se repite en las reglas de U2.
2. NFR-U1-12: «salvo los Deployments con réplicas fijas… (hoy tres)».
3. Catálogo de componentes: C04 lista sus procesos (`case-service`, `case-worker` con su identidad, cliente y rol, y el CronJob `case-retention`); C14 `channel-simulator` corre fuera del clúster dentro de la imagen de U12 (F07 externo). Tabla de `application-design.md` actualizada. Fila nueva en `aidlc-state.md`.
**Context**: Tres hallazgos de la segunda revisión de coherencia.

---

## Tercera revisión de coherencia entre unidades — Solicitud
**Timestamp**: 2026-10-10T20:00:00Z
**User Input**: "revisar si las unidades son coherentes para el proyecto"
**AI Response**: Tercera pasada, sin cambios a los documentos. Controles nuevos que pasan: todo identificador NFR, BR, INF, P y PBT citado existe (los huecos dentro de rangos como NFR-U10-01..64 son numeración por bloques, a propósito); métricas consumidas entre unidades existen con las mismas etiquetas (`vectra_recommendations_total{outcome}` con `fail_closed`, `vectra_scoring_failclosed_total{cause}`, `vectra_core_write_attempts_total`, `vectra_circuit_state`); roles de negocio y `operacion` coherentes entre U0, U2 y U10; puertos de Keycloak (8443 interno) iguales en el inventario y en U2.
Hallazgos: (1) `FailClosedPersistente`: U1 (P-U1-11, dueña de la alerta) la ata al SLI «recomendación usable» (`Recommendation` / total) y nunca nombra su métrica, mientras `services.md`, U7, U8 y US-112 dicen que sale del gauge `vectra_cases_failclosed_persistent` de U8 (casos en `no_disponible`); el plan de U8 solo prueba que el gauge existe, así que U1 construiría otra regla; (2) `unit-of-work.md`, entrada de U8, sigue describiendo a `case-service` como quien arma el vector y llama a scoring, sin `case-worker` (la misma desactualización ya corregida en `components.md`). Se ofrece aplicar las correcciones.
**Context**: Tercera pasada transversal, con controles distintos de las dos anteriores (identificadores citados entre unidades, métricas, historias dueñas).

---

## Correcciones de la tercera revisión de coherencia — Solicitud
**Timestamp**: 2026-10-10T20:02:40Z
**User Input**: "sí, aplica las correcciones con tu propuesta"
**AI Response**: Aplicadas (marca «tercera revisión de coherencia entre unidades, 2026-10-10»):
1. `FailClosedPersistente`: P-U1-11 la separa del SLI de recomendación usable (que queda solo como dashboard) y la define como `max(vectra_cases_failclosed_persistent) > 0` con `for: 1m`, sobre el gauge de U8; logical-components §3 con la expresión; plan de U1, Paso 11, con la regla y casos de `promtool` (dos réplicas → una alerta; gauge en 0 → no dispara; razón usable baja con el gauge en 0 → no dispara).
2. `unit-of-work.md`, entrada de U8: `case-service` sin el armado del vector ni la llamada a scoring; nuevas viñetas de `case-worker` (cola, F104, `derive`, F15, identidad y rol propios) y del CronJob `case-retention`. Fila nueva en `aidlc-state.md`.
**Context**: Dos hallazgos de la tercera revisión de coherencia.

---

## Consulta de estado tras las revisiones de coherencia
**Timestamp**: 2026-10-10T20:04:55Z
**User Input**: "cual es su estado"
**AI Response**: Estado informado: INCEPTION completa; CONSTRUCTION cerrada en los planes de U0–U12 (Part 2, Build and Test y OPERATIONS fuera de alcance); pendientes consolidados y tres revisiones de coherencia aplicados, sin hallazgos abiertos; cambios sin commit.
**Context**: Consulta de estado; sin cambios a los documentos de diseño.

---
