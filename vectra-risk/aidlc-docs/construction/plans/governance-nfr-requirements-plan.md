# Plan de NFR Requirements — U4 `governance`

**Alcance:** requisitos no funcionales y stack de `governance-service`, `model-validation-job`
y `promotion-tool`, sobre el Functional Design aprobado (BR-U4-01..17).

**Ya decidido** (no se pregunta):
- Python 3.12 + FastAPI + Pydantic v2 + `vectra_common`, psycopg 3, Alembic y Hypothesis (U0, U3);
- `governance-db` en CloudNativePG (10 Gi + 5 Gi; U1);
- criticidad High (U1); readiness = su base (P-U1-04);
- K01 (Jobs solo en `vectra-staging`); F08 para `promotion-tool` con token de usuario, MFA y `governance:promotion` (U2);
- caché de `serving-config` en scoring ≤ 5 s (BR-U4-14).

---

## Parte A — Preguntas

Escribe la letra después de cada `[Answer]:`.

## Question 1 — Disponibilidad: governance en la ruta de cada recomendación (Availability)
scoring lee `serving-config` en cada evaluación (con caché ≤ 5 s). Si governance no
responde, `serving_state = no_disponible` y **todas** las recomendaciones salen como
fail-closed. Governance pasa a ser, en la práctica, parte del SLO de la ruta de
recomendación.

A) **Sin configuración vencida**: scoring nunca usa una `serving-config` de más de 5 s (podría no ver un congelamiento). Para que esto no degrade el SLO, governance se trata como dependencia del SLO de 99,5 %:
   - ≥ 2 réplicas repartidas por zona, PDB y HPA;
   - `GET /v1/serving-config` servido desde una copia en memoria que se recalcula en cada transición confirmada, sin consultar la base en cada request;
   - alerta `ServingConfigUnavailable` (SEV1) si falla más del 1 % durante 5 min.

   (Recomendado: conserva la garantía del congelamiento)

B) Permitir que scoring use la última `serving-config` conocida hasta 60 s si governance no responde

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2 — Objetivos de rendimiento (Performance)

A)
   - `GET /v1/serving-config`: **p95 ≤ 20 ms** (incluido el 304 con `If-None-Match`), con 6 réplicas de scoring consultando cada 5 s.
   - Transiciones con firma (aprobar, activar, reactivar): **p95 ≤ 500 ms**, incluido el append al registro.
   - `model-validation-job`: **≤ 30 min** con el dataset de validación de U5 (el plazo de corte sigue en 2 h).

   (Recomendado)

B) Sin objetivos propios

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 3 — Identidad y controles de `promotion-tool` y del repositorio GitOps (Security, US-204, AUTONOMIA-01)
`promotion-tool` corre en la estación del ingeniero y abre PRs en `vectra-risk-gitops`.

A)
   - **Sin credenciales de larga duración**: el login con Keycloak usa PKCE con loopback (token en memoria). Para Git y GitHub, el ingeniero usa **su propia** identidad (`gh auth` o SSH); no hay un token de servicio compartido.
   - **Commits firmados** (Sigstore `gitsign` o GPG), y CI los verifica.
   - **Protección de rama** en `vectra-risk-gitops`: merge solo por PR, con al menos 1 aprobación de una persona distinta del autor (CODEOWNERS por directorio), checks de CI obligatorios y sin push directo ni force-push.

   (Recomendado: separa a quien propone el cambio de quien lo aprueba también en Git)

B) Un token de servicio compartido para crear los PRs

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4 — Retención de los datos de governance (Compliance)
Para defender una decisión hay que saber qué modelo y qué política estaban vigentes.

A) **10 años**, alineado con NFR-U3-01: las versiones de modelo, políticas, fuentes, transiciones e informes de validación nunca se borran (`retirado` e `historica` son estados, no borrados). Los artefactos del model-store de versiones que alguna vez estuvieron `activo` se conservan también 10 años (bucket con retención) **[VERIFICAR]** (recomendado)

B) Solo mientras la versión esté en uso, más 12 meses

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5 — Librerías de integración (Tech Stack)

A)
   - **Cliente oficial de Kubernetes para Python** para crear y seguir los Jobs (K01), con el ServiceAccount acotado y timeouts explícitos;
   - **GitHub CLI (`gh`)** invocado por `promotion-tool` con la sesión del ingeniero, más `git` con firma;
   - la librería de disparidad de U9 como dependencia de ruta del workspace en `model-validation-job`;
   - **ONNX Runtime**, `xgboost` y `lightgbm` **solo** en `model-validation-job` (que sí ejecuta inferencia en staging), nunca en `governance-service`.

   (Recomendado)

B) Llamadas HTTP directas a la API de Kubernetes y de GitHub, sin librerías

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 6 — Aislamiento y recursos del `model-validation-job` (Security / Compute)
Es el único componente de U4 que carga artefactos de modelo y ejecuta inferencia.

A) Pod en `vectra-staging` con `runAsNonRoot`, `readOnlyRootFilesystem`, sin token de la API de Kubernetes (`automountServiceAccountToken: false`) y sin egress.
   - Solo puede leer el model-store (credencial de solo lectura, F31), llamar al KServe de staging (F30) y enviar el informe a governance (F32).
   - Límites de 2 CPU y 4 GiB, `activeDeadlineSeconds: 7200` (igual al plazo de BR-U4-05) y prioridad `vectra-low`.

   (Recomendado)

B) Mismo perfil que los servicios, sin límites específicos

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Parte B — Checklist de ejecución

- [x] 1. Analizar el Functional Design de U4 y los NFR heredados
- [x] 2. Recoger y validar las respuestas
- [x] 3. Generar `construction/governance/nfr-requirements/nfr-requirements.md`
- [x] 4. Generar `construction/governance/nfr-requirements/tech-stack-decisions.md`
- [x] 5. Verificar el cumplimiento de las extensiones (autorrevisión de la tabla contra el cuerpo)
