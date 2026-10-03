# Infrastructure Design — U6 `model-serving`

Decisiones del plan (`model-serving-infrastructure-design-plan.md`, Q1–Q2 = A). Se apoya en
la infraestructura compartida de U1. Los IDs `INF-U6-xx` se referencian en el plan de tareas.

---

## 1. Cómputo (Q1)

### INF-U6-01 — Recursos y probes

| Componente | Entorno | Requests | Limits | Réplicas | PriorityClass |
|---|---|---|---|---|---|
| Predictor | prod (activo) | 500m / 512 MiB | 1 CPU / 1 GiB | HPA de 2 a 4 (CPU 60 %) | `vectra-high` |
| Explicador | prod (activo) | 500m / 512 MiB | 2 CPU / 1 GiB | HPA de 2 a 6 (CPU 60 %) | `vectra-high` |
| Predictor y explicador | prod (inactivo, ≤ 7 días) | 500m / 512 MiB | Iguales al activo | 1 fija, sin HPA (INF-U6-02) | `vectra-normal` |
| Predictor y explicador | staging | 250m / 256 MiB | 1 CPU / 512 MiB | 1 fija | `vectra-low` |

- `startupProbe`: `periodSeconds: 5`, `failureThreshold: 30` (hasta 150 s para descargar y verificar el paquete, P-U6-03).
- Readiness cada 5 s (paquete verificado); liveness cada 10 s (proceso vivo).
- `emptyDir` de 1 GiB para el paquete. Pool `general`; spread por zona y PDB en el activo.

## 2. Ciclo de vida de los `InferenceService` (Q2)

### INF-U6-02 — Réplicas del inactivo y secuencia de PRs
Todos los cambios entran por PR + sync manual (AUTONOMIA-01). La baja del inactivo **no** va
en el PR de promoción: ese sync ocurre antes de `mark_active`, con la versión anterior todavía
activa, y la dejaría con 1 réplica por debajo del mínimo de 2 (NFR-U1-04). Por eso son tres PR,
todos generados por `promotion-tool`:

| # | PR | Cuándo | Efecto |
|---|---|---|---|
| 1 | Promoción | Versión `aprobado` | Agrega `isvc-<nueva>` con los mínimos de producción; no toca el activo |
| — | `mark_active` | Tras el sync del PR 1 y con `isvc-<nueva>` listo | `serving-config.inference_service` apunta a la nueva; la anterior pasa a `inactivo` |
| 2 | Post-activación | Después de `mark_active` | Baja `isvc-<anterior>` a 1 réplica por componente, sin HPA |
| 3 | Retiro | La anterior lleva más de 7 días `inactivo` | Elimina `isvc-<anterior>` |

**Rollback (US-208)**:
1. PR que restaura los mínimos de producción y el HPA en `isvc-<anterior>`;
2. sync y espera a que esté listo con 2 réplicas;
3. `mark_active` de la anterior;
4. PR post-activación que baja la que dejó de estar activa.

Nunca hay un `InferenceService` activo con menos de 2 réplicas.

- **Cuotas de `vectra-serving`** (NFR-U1-13): el activo en su máximo (4 predictores + 6 explicadores) + 1 + 1 del inactivo, + 30 % de margen. Para el escenario de rollback, el activo en su máximo + el que se restaura con sus mínimos (2 + 2) cabe dentro de ese 30 %.
- La alerta `InferenceServiceNotReady` distingue el activo (SEV1) del inactivo (SEV3) por la etiqueta que lee de `serving-config`.

## 3. Red, almacenamiento y mensajería

- **Sin flujos nuevos**: F19, F22, F30 y F46 cubren los `InferenceService` por etiqueta (`vectra.io/component=predictor|explainer`).
- **Almacenamiento**: N/A (paquete en `emptyDir`).
- **Mensajería**: N/A (solo request/response síncrono).

## 4. Cambios aplicados a otros artefactos

Registrados en `audit.md` (2026-10-03):

| Artefacto | Cambio |
|---|---|
| U4 FD BR-U4-09 | `promotion-tool` genera tres PR: promoción, post-activación (baja el inactivo a 1 réplica) y retiro; el rollback restaura los mínimos antes de `mark_active` |
| U4 plan de tareas, Paso 12 | Comando `post_activation_pr` y la secuencia de rollback |
| U6 NFR Design P-U6-02 | Secuencia con el PR post-activación y la restauración de mínimos en el rollback |

## 5. Cumplimiento de extensiones (Infrastructure Design U6)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| AUTONOMIA-01 | Cumple | INF-U6-02 (cada cambio de réplicas o de versión entra por PR + sync manual) |
| AUTONOMIA-06 | Cumple | INF-U6-02 (`mark_active` solo con el nuevo listo; sin versiones mezcladas) |
| RESILIENCY-06 | Cumple | INF-U6-01 (`startupProbe` y readiness = paquete verificado) |
| RESILIENCY-08 / 09 | Cumple | INF-U6-01 (HPA, spread, PDB en el activo), INF-U6-02 (el activo nunca baja de 2 réplicas) |
| SECURITY-07 | Cumple | §3 (sin flujos nuevos; acceso por etiqueta dentro del inventario) |
