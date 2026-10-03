# Requisitos no funcionales — U4 `governance`

Decisiones del plan (`governance-nfr-requirements-plan.md`, Q1–Q6 = A). Las verificaciones
«en kind» las ejecuta el operador después de un PR aprobado (AUTONOMIA-01); las demás
corren en CI (Testcontainers incluido).

Los IDs `NFR-U4-xx` se referencian en NFR Design, Infrastructure Design y el plan de tareas.

---

## 1. Disponibilidad (Q1)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U4-01 | **Governance es dependencia del SLO de la ruta de recomendación** (99,5 %, U1): si no responde, scoring falla cerrado en todas las evaluaciones | Documentado en `docs/slo.md`; el SLO de U1 (P-U1-11) incluye `ServingConfigUnavailable` |
| NFR-U4-02 | **Nunca configuración vencida**: scoring no usa una `serving-config` de más de 5 s (BR-U4-14). No hay modo «última conocida» | Prueba de U7 (definida aquí como requisito): governance caído 6 s → scoring responde `serving_config_unavailable` |
| NFR-U4-03 | ≥ 2 réplicas repartidas por zona, PDB y HPA; readiness = `governance-db` (P-U1-04) | `helm template` + `conftest` |
| NFR-U4-04 | `GET /v1/serving-config` se sirve desde una **copia en memoria** de cada réplica, recalculada en cada transición confirmada; no consulta la base en cada request | Prueba de integración: con la base pausada, `serving-config` sigue respondiendo la última copia confirmada |
| NFR-U4-05 | **Convergencia entre réplicas ≤ 1 s**: cuando una réplica confirma una transición, las demás actualizan su copia en ≤ 1 s (el mecanismo lo fija NFR Design) | Prueba con 2 réplicas y Testcontainers: `freeze` en la réplica A → la réplica B sirve el `etag` nuevo en ≤ 1 s |
| NFR-U4-06 | **Límite de propagación del congelamiento: ≤ 6 s** (1 s de convergencia + 5 s de caché de scoring). **Precisa BR-U4-14**, que decía ≤ 5 s sin contar la convergencia entre réplicas | Prueba de extremo a extremo en kind: `freeze` → la primera `FailClosed(model_frozen)` en ≤ 6 s |
| NFR-U4-07 | Alerta `ServingConfigUnavailable` (SEV1) si más del 1 % de las lecturas de `serving-config` falla durante 5 min | `promtool test rules` |

## 2. Rendimiento (Q2)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U4-10 | `GET /v1/serving-config`: p95 ≤ 20 ms, incluido el 304, con 6 réplicas de scoring consultando cada 5 s | Prueba de carga k6 en kind (operador) |
| NFR-U4-11 | Transiciones con firma: p95 ≤ 500 ms, incluido el append al registro | Misma prueba |
| NFR-U4-12 | `model-validation-job`: ≤ 30 min con el dataset de validación de U5 (plazo de corte de 2 h, BR-U4-05) | Ejecución en kind con el modelo de referencia (operador) |

## 3. Seguridad

| ID | Requisito | Origen | Verificación |
|---|---|---|---|
| NFR-U4-20 | `promotion-tool` sin credenciales de larga duración: Keycloak con PKCE loopback (token en memoria) y Git/GitHub con la identidad del propio ingeniero; ningún token de servicio compartido | Q3, SECURITY-12 | Revisión del código: ningún archivo de configuración guarda tokens; prueba de que el token de Keycloak no se escribe en disco |
| NFR-U4-21 | Commits firmados (Sigstore `gitsign` o GPG) en `vectra-risk-gitops`; CI verifica la firma | Q3, SECURITY-13 | Check de CI que rechaza un commit sin firma válida |
| NFR-U4-22 | Protección de rama en `vectra-risk-gitops`: merge solo por PR, ≥ 1 aprobación de una persona distinta del autor (CODEOWNERS), checks obligatorios, sin push directo ni force-push | Q3, AUTONOMIA-01, SECURITY-13 | `gh api repos/{owner}/vectra-risk-gitops/branches/main/protection` muestra la configuración esperada (script versionado) |
| NFR-U4-23 | `model-validation-job` aislado: `runAsNonRoot`, `readOnlyRootFilesystem`, `automountServiceAccountToken: false`, sin egress; solo F30, F31 (solo lectura) y F32 | Q6, SECURITY-06, 07 | `conftest` sobre el Job; `flows.yaml` |
| NFR-U4-24 | Librerías de inferencia (ONNX Runtime, `xgboost`, `lightgbm`) **solo** en la imagen del `model-validation-job`; la imagen de `governance-service` no las incluye (BR-U4-06) | Q5, SECURITY-13 | Prueba sobre el `uv.lock`/SBOM de la imagen del servicio: ninguna de esas librerías presente |
| NFR-U4-25 | Cliente de Kubernetes con el ServiceAccount de K01 (solo `batch/jobs` y `pods/log` en `vectra-staging`) y timeouts explícitos | Q5, SECURITY-06 | `kubectl auth can-i --list --as=system:serviceaccount:vectra-app:governance-service` en kind |

## 4. Datos y retención (Q4)

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U4-30 | **Retención de 10 años** (alineada con NFR-U3-01): versiones, políticas, fuentes, transiciones e informes nunca se borran; `retirado` e `historica` son estados | Ningún endpoint ni rol de base con `DELETE` sobre esas tablas (prueba SQL) |
| NFR-U4-31 | Artefactos del model-store de toda versión que estuvo `activo`: retención de 10 años en el bucket **[VERIFICAR]** | Configuración de retención del bucket `model-store` (U1), con una prueba en MinIO |

## 5. Pruebas

| ID | Requisito | Verificación |
|---|---|---|
| NFR-U4-40 | PBT-U4-01 y 07 (stateful) con `RuleBasedStateMachine` y Testcontainers; el resto con el perfil `ci` | `HYPOTHESIS_PROFILE=ci uv run pytest governance/tests/property` |
| NFR-U4-41 | Cobertura de ramas ≥ 95 % y **100 %** en `model_fsm`, `policy` y `evidence`; mutation testing en `model_fsm` | `pytest --cov --cov-branch` + `mutmut` |

## 6. Cumplimiento de extensiones (NFR Requirements U4)

Revisada contra el cuerpo del documento antes de presentarla.

| Regla | Estado | Evidencia |
|---|---|---|
| RESILIENCY-01 / 02 | Cumple | NFR-U4-01 (governance dentro del SLO) |
| RESILIENCY-05 / 07 | Cumple | NFR-U4-07 |
| RESILIENCY-06 | Cumple | NFR-U4-03 |
| RESILIENCY-08 / 09 | Cumple | NFR-U4-03 |
| RESILIENCY-10 | Cumple | NFR-U4-04 (la copia en memoria sobrevive a la base pausada), NFR-U4-25 (timeouts) |
| SECURITY-06 | Cumple | NFR-U4-23, 25 |
| SECURITY-07 | Cumple | NFR-U4-23 |
| SECURITY-11 | Cumple | NFR-U4-22: la protección de rama (merge solo por PR, aprobador distinto del autor, sin push directo ni force-push, verificada con un script) lleva la prevención de abuso de BR-U4-03 hasta el repositorio GitOps |
| SECURITY-12 | Cumple | NFR-U4-20 |
| SECURITY-13 | Cumple | NFR-U4-21, 22, 24 |
| SECURITY-15 | Cumple | NFR-U4-02 (sin configuración vencida → fail-closed) |
| AUTONOMIA-01 | Cumple | NFR-U4-22 (merge solo por PR aprobado por otra persona) |
| AUTONOMIA-02 | Cumple | Cada requisito tiene su verificación |
| AUTONOMIA-04 | Cumple | NFR-U4-02, 06 (el congelamiento se propaga en ≤ 6 s y nunca se ignora por una configuración vencida) |
| AUTONOMIA-05 | Cumple | NFR-U4-23: `model-validation-job` sin egress, con solo F30, F31 (solo lectura) y F32 permitidos |
| PBT-06 / 08 / 09 | Cumple | NFR-U4-40 |

## 7. Cambios a otros artefactos (registrados en `audit.md`)

| Artefacto | Cambio |
|---|---|
| U4 FD BR-U4-14 y domain-entities §6 | Límite de propagación del congelamiento: ≤ 6 s (1 s de convergencia + 5 s de caché), antes ≤ 5 s |
| U7 (pendiente) | Prueba de NFR-U4-02: sin `serving-config` de más de 5 s |
| U1 (pendiente para Infrastructure Design de U4) | Retención de 10 años en el bucket `model-store` para versiones que estuvieron activas |
