# Componentes de frontend — U10 `console-spa`

React + TypeScript, con el cliente generado de U0 (`contracts/ts`). Textos solo desde los
catálogos i18n (BR-U10-17). Estados con color **y** texto.

---

## 1. Jerarquía

Los roles de cada vista salen de la columna «Roles» de `component-methods.md` C03
(BR-U10-12; revisión del FD de U10, 2026-10-10, A2).

```text
App
|-- AuthProvider              (BR-U10-05: tokens en memoria, refresco, login silencioso)
|-- StepUpProvider            (BR-U10-06: ventana emergente abierta en un clic y reintento único)
|   `-- StepUpDialog          (403 mfa_required inesperado: botón «Verificar identidad»)
|-- InactivityProvider        (BR-U10-20: contador compartido entre pestañas)
|   `-- InactivityDialog      (aviso a los 25 min)
|-- VersionBanner             (BR-U10-21)
|-- ErrorReporter             (BR-U10-22)
|-- Layout
|   |-- RoleMenu              (BR-U10-12, desde get_me)
|   `-- Routes
|       |-- StepUpCallback                (/stepup-callback: postMessage al opener y cierra; sin layout)
|       |-- CasesInbox                    analista, cro
|       |   |-- CaseFilters
|       |   `-- GoToCase                  (por case_id; sin búsqueda por nombre)
|       |-- CaseDetail                    analista, cro
|       |   |-- RecommendationSummary     (outcome, score, marcas)
|       |   |-- ExplanationPanel          (abre -> record_explanation_view)
|       |   |-- ApplicationView           (sin etiquetas de monitoreo; free_text como texto)
|       |   |-- CreditStatusBadge
|       |   |-- ApplicantSummaryButton    analista, cro (caso decidido)
|       |   `-- DecisionForm              analista
|       |-- ManualApplicationForm         analista
|       |-- PersistentFailures            cro (con retry)
|       |-- Dossier                       cro, cumplimiento
|       |-- IntegrityCheck                cro (inicio con MFA; con `already_active` muestra «ya hay una verificación en curso» y sigue esa; estado cada 30 s, P-U10-05; segunda revisión del Infrastructure Design de U10, 2026-10-10)
|       |-- Models / ModelDetail          ingeniero_riesgo, cro y cumplimiento (lectura)
|       |   |-- RegisterModelForm         ingeniero_riesgo (MFA)
|       |   |-- ValidationReportView
|       |   `-- ApproveModelDialog        cro (MFA)
|       |-- Policies / PolicyDetail       analista y cumplimiento (lectura), cro
|       |   `-- ProposePolicyForm / ApprovePolicyDialog   cro (MFA)
|       |-- DataSources / DataSourceDetail   ingeniero_riesgo, cro y cumplimiento (lectura)
|       |   |-- ProposeDataSourceForm / StartComparisonDialog   ingeniero_riesgo (MFA)
|       |   `-- PrePostReportView + DecideDataSourceDialog      cumplimiento (MFA)
|       |-- BiasDashboard                 cumplimiento, cro
|       |   |-- DisparityTables           (API; celdas insuficientes)
|       |   `-- GrafanaEmbed              (bias.json; leyenda propia encima)
|       |-- Freezes                       cumplimiento, cro (lista)
|       `-- FreezeContextView             cumplimiento (get_freeze solo para cumplimiento en C03)
|           `-- ResolveFrozenDialog       cumplimiento (MFA)
`-- ErrorBoundary / ProblemMessage        (BR-U10-17)
```

## 2. Componentes principales

| Componente | Props | Estado | Endpoints del BFF | Reglas |
|---|---|---|---|---|
| `CasesInbox` | — | filtros de `CaseFilter` en la URL; página; refresco cada 15 s si la pestaña está visible | `GET /api/console/cases` | BR-U10-10, 11 |
| `StepUpCallback` | — | ninguno | ninguno (solo `postMessage` al opener) | BR-U10-06 |
| `ApplicantSummaryButton` | `case` | resumen generado | `POST …/{id}/applicant-summary` | BR-U10-12 |
| `CaseDetail` | `caseId` | caso; refresco cada 3 s (máx. 2 min) si está en evaluación | `GET /api/console/cases/{id}` | BR-U10-07, 10, 11 |
| `ExplanationPanel` | `case` | abierto/cerrado; `viewRecorded` por vista | `POST …/explanation-views` | BR-U10-08 |
| `DecisionForm` | `case` (recomendación, `shap_vector`, etiquetas) | decisión, factores, `final_outcome`, justificación, `submitting` | `POST …/decision` | BR-U10-09 |
| `ManualApplicationForm` | — | borrador en memoria | `POST /api/console/cases` (sin MFA en C03; con `Idempotency-Key` generada por envío, U8 BR-U8-02) | BR-U10-09 (envío único), BR-U10-17 |
| `PersistentFailures` | — | lista | `GET …/cases/failures`, `POST …/{id}/retry` | U8 BR-U8-11 |
| `Dossier` | `caseId` | expediente; generación de PDF en el navegador | `GET …/{id}/dossier` | BR-U10-03 |
| `ModelDetail` y diálogos | `modelId` | según la acción | `GET/POST /api/console/models…` | BR-U10-12 |
| `PrePostReportView` + `DecideDataSourceDialog` | `dataSource` | justificación | `POST …/data-sources/{id}/decision` | BR-U10-14, 15 |
| `BiasDashboard` | — | filtros (atributo, ventana) | `GET /api/console/disparity` | BR-U10-15, 16 |
| `Freezes` | — | lista | `GET /api/console/freezes` | BR-U10-12 |
| `FreezeContextView` + `ResolveFrozenDialog` | `freezeId` | acción, justificación | `GET …/freezes/{id}`, `POST …/models/{id}/frozen-resolution` | BR-U10-12, 13 |

## 3. Validación de formularios

| Formulario | Reglas en el cliente (el servidor decide igual) |
|---|---|
| `DecisionForm` | BR-U0-35 (opciones según `outcome`), BR-U0-36 (20..2000 sin bordes), factores ⊆ `shap_vector` o exactamente «Ninguno» (BR-U8-16), `final_outcome` distinto en `se_aparta` |
| `ManualApplicationForm` | Validación de `ApplicationIn` de U0 (BR-U0-20..34) con el esquema generado; `free_text` sin transformar |
| `ProposePolicyForm` | BR-U0-33 (`cutoff`, vigencias sin solapes) |
| Diálogos con justificación (`ResolveFrozenDialog`, `DecideDataSourceDialog`, `ApproveModelDialog` al rechazar) | Justificación obligatoria con su rango |

## 4. Interacción

- **Acciones con MFA** (las de la columna «MFA» de C03): si el token no tiene MFA reciente, el botón de confirmación dice «Verificar y confirmar» y abre la ventana en ese clic; si llega un 403 `mfa_required` de todos modos, `StepUpDialog` ofrece «Verificar identidad» (BR-U10-06; revisión del Infrastructure Design de U10, 2026-10-10). El alta manual, la decisión y el `retry` no piden MFA.
- **Envíos**: botón deshabilitado mientras está en curso; un solo envío por clic.
- **Errores**: `ProblemMessage` con el texto del catálogo y el `correlation_id`.
- **Accesibilidad**: navegación por teclado y etiquetas en todos los controles; estados con texto. El nivel de conformidad se fija en NFR Requirements.
