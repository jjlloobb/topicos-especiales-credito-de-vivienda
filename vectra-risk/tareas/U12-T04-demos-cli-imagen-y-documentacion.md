# U12-T04 — Guiones de las cuatro demos, CLI por secciones, manifiesto, imagen y documentación de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que implementa:** ninguna propia. La trazabilidad del plan (§3) nombra el Paso 12 en US-111, 303, 305 y 603 y en las demos de US-304, 503, 504 y 505. Aquí se escriben los guiones, la herramienta que el operador ejecuta y su imagen. Las corre el operador en kind (Paso 18, U12-T05).
**Depende de:**
- **U12-T03 fusionada en `main`** (PR #___, commit de fusión `_______`: **por completar al fusionar**). Su contrato es `tareas/U12-T03-escenarios-y-mediciones.md`, sección «Lo que T04 y T05 necesitan de esta tarea». **Al empezar, lee `aidlc-docs/construction/system-verification/code/scenarios.md`**: las firmas reales rigen sobre lo que esta tarea supone. Lo que se da por sentado:
  - una función por sección (`rt5`, `rt3`, `rt2-setup`, `rt2`) y la de `SIM-NORMAL`, con parámetros (`runId`, `started_at`, versiones del proxy, prefijos del model-store, semillas, plazos);
  - el resultado de tres valores (`scenarios/outcome.py`), su conversión a `report.Evidence` (ninguna si es `no ejecutado`) y el motivo de cada `no ejecutado`;
  - las fases de `rt2` y `rt3` como puntos de retoma, y las consultas guardadas (`QueryResult`);
  - RT-3 con la decisión P-2 (a) del usuario: obligatorios RT3-a, c, d y F22.
- **U12-T02** (PR #___, **por completar**; leída en `.claude/worktrees/u12-t02`, `639a22f`): `clock.Clock`; `clients/` (`oidc`, `bff`, `registry`, `prom`, `loki`, `k8s_read`); `simulator`; `driver` con `run_decisions(...)` y `DEMO_VOLUME = 2000`; `guard.SECTIONS` con las 14 secciones y `STAGING_SECTIONS = ("prepare", "decisions", "u11", "report")` (`guard.py`, líneas 43 a 46); `guard.check_job_patch` (línea 95) y `check_reactivation` (línea 102); `evidence.prepare(text, secrets)` (línea 182); `.importlinter` con 6 contratos; `Makefile` con `check: lint types imports test`.
- **U12-T01** (en `main`): `report.build` y `report.render`, `report.MANIFEST_LIMIT` (`report.py`, línea 48), `ELEMENT_IDS` con las cuatro demos (`journey-7-3`, `journey-7-4`, `rt-5`, `dashboard`; línea 29), `report/story-map.yaml`, `tests/unit/test_kubectl_verbs.py` (`scan_tree` recorre `src/`, `demos/`, `Makefile`, `README.md` y `Dockerfile`). `manifest.py` y `cli.py` existen vacíos.
- **U01-T09** ya está en `main` (`8dc7499`): monitor del proxy de Linkerd solo en `vectra-mock`.
- **No depende** de U02-T22 ni de U00-T04 (en curso). Ver «Reparación temporal del realm».

Es código, guiones, imagen y documentación **sin clúster** (RL-5). Usa Docker local para construir y arrancar la imagen.
**Rama:** `tarea/U12-T04`, desde `origin/main` **después** de fusionar U12-T03.

Bloques E y F del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`), según `aidlc-docs/construction/plans/demo-recorte-funcional.md` §4 (fila U12: «A+B (1–4) · C (5–6) · D (8, 10) · E+F (12, 13, 15, 17) · G+H (18–19)») y §8. Es la cuarta de cinco. La enmienda rige sobre el alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 12 Demos | **E** | Entra completo | Enmienda §3 U12, fila «12 Demos: E, E, Los cuatro guiones, `verify/*.sh` y los PR preparados (F22 con `env_disabled.kind`, P-19)» |
| 13 CLI, manifiesto y `CODEOWNERS` | **E\*F** | Entran 8 secciones. Se difieren 6 secciones, dos de los tres values del parche y la prueba de `CODEOWNERS` | Enmienda §3 U12, fila «13 CLI: E\*, E\*F, Secciones `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report` (sale `pii`). El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`). Se difiere la prueba de `CODEOWNERS` con `branch-protection-check`, porque depende de U4 Paso 14, que está en D» |
| 14 N/A | **N/A** | Se comprueba aquí (necesita la imagen) | Enmienda §3 U12, fila «14 · 15: N/A · E\*» |
| 15 Imagen | **E\*** | Se difieren escaneo, SBOM y firma | Alcance §3 U12, fila «14 N/A · 15 Imagen: N/A · E\*, T1»; T1: «Firma Cosign, SBOM y attestations de imágenes y paquetes. Las imágenes se construyen y se publican **por digest** en `kind-registry`» |
| 16 Workflow de CI | **D** | No entra | Enmienda §3 U12, fila «16: D, D»; alcance: T4 |
| 17 Documentación y trazabilidad | **E\*F** | README de lo que entra; trazabilidad con lista | Enmienda §3 U12, fila «17: E, E\*F, README de lo que entra; trazabilidad con lista» |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6. No hay PBT nuevas; PBT-U12-01 a 04 siguen verdes.

**Tamaño.** Es la tarea más grande de U12: 4 guiones, 4 `verify`, los PR preparados, la CLI con 8 secciones, el manifiesto, la sección `u11` (que ningún paso del plan define), la imagen con Chromium y el README. **Recomendación del redactor: partirla en dos por bloque**, para que cada una quepa en 2 rondas: **T04a = Bloque E (Pasos 12 y 13; CA-1 a CA-15)** y **T04b = Bloque F (Pasos 14, 15 y 17; CA-16 a CA-24, más CA-25 a CA-28 repetidos)**, T04b tras T04a. Los criterios ya están agrupados así. Decide el usuario (P-1).

**Decisiones del usuario que rigen** (`DECISIONES-LOOP.md` §9 y §10):
- **RT-3 en la demo:** pasa con RT3-a, c y d (422) más F22. RT3-b y «a y d desplegados» se calculan y se informan; solo bajan el resultado si dan `falla`.
- **RT-2:** se niega solo por celdas **alcanzables**; D2 usa **1** versión del proxy (DD-1).
- **Emisor:** solo el público (`https://vectra.localtest.me/auth/realms/vectra`). La aserción de servicio lleva `aud` = emisor; U00-T04 (en curso) lo corrige en `vectra_common`, que U12 no usa.
- **Realm:** U02-T22 (en curso) corrige los alias y desactiva `VERIFY_PROFILE`.
- **Memoria de kind:** requests de 128 MiB solo en kind para U8, U10 y U11; `BUDGET_GIB = 11.8` (`platform/tests/test_kind_profile.py`, línea 34), con todo menos U12.
- **U03-T07 aparcada:** U3 puede dar 504 al cron de U9 bajo carga. Riesgo aceptado para D2: el guion lo dice.

**U12 no suma memoria al clúster.** Comprobado: no hay entrada de U12 en `vectra-risk-gitops/components.yaml` ni chart en `system-verification/`; el Paso 14 es N/A. La imagen **no** corre como Job: corre en la estación del operador (`deployment-architecture.md` §1). `BUDGET_GIB` no cambia. Sí usa memoria **del host**, que kind comparte (14 GiB): Chromium y Python. El README fija un límite (`--memory`, P-9) y U12-T05 lo mide.

**Lección que esta tarea aplica** (enmienda §8): un guion que nombra un recurso, una ruta, un usuario o un comando que no existe solo se descubre delante del público. Por eso cada nombre de un guion, de un `verify` y de un PR preparado está en «Lo que los guiones tocan de verdad», con ruta y línea, y una prueba lo comprueba recorriendo `demos/` (CA-2).

---

## Alcance

**Dentro:** los Pasos 12, 13, 15 y 17 del plan (y la comprobación del 14). Texto del plan, sin recortes salvo lo que el recorte difiere, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque E — Demos, informe y CLI

- [ ] **Paso 12 — Demos** (E)
  - Guiones `journey-7-3.md`, `journey-7-4.md`, `rt-5.md` y `dashboard.md` con los pasos del presentador, las lecturas y las llamadas a la API, y un `verify/<demo>.sh` por demo que comprueba cada paso.
  - Los cambios al clúster (artefacto alterado, modelo proxy, Jobs de prueba) son PRs preparados en `demos/prs/`, que el operador sincroniza antes.
  - Diseño: BR-U12-09.
  - **Aceptación**: la prueba del Paso 1 sobre `demos/`; `shellcheck system-verification/demos/verify/*.sh`.

- [ ] **Paso 13 — CLI por secciones, manifiesto y `CODEOWNERS`** (E\*F)
  - `cli`: secciones `prepare`, ~~`network`,~~ `decisions`, ~~`rt1`, `rt4`,~~ `rt5`, `rt3`, `rt2-setup`, `rt2`, ~~`load`, `pii`,~~ `u11`, ~~`resilience`,~~ `report`, en el orden de business-logic-model §2.1, con retoma desde una sección y evidencia al terminar cada una. **(Diferidas `network`, `rt1`, `rt4`, `load`, `pii` y `resilience`: enmienda §3 U12, fila «13»: «Secciones `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report` (sale `pii`)»; §1.5, fila U12. La CLI las conoce y responde `no ejecutado`: ver Precisiones.)**
  - **`prepare`** (revisión del plan de tareas de U12, 2026-10-10): primera sección, **antes** del PR de los Jobs de prueba. Genera el `runId` de la verificación, escribe el manifiesto inicial con ese `runId` y `started_at = ahora`, y produce el parche de values de kind (`probes.runId`, y el de U8 para RT-5) que el operador usa en el PR. Así los Jobs de prueba terminan **después** de `started_at`, y el oráculo de X04 y X06 (Paso 9) puede aceptarlos. Sin `prepare`, las demás secciones se niegan a correr. **(El parche solo toca `case-management`: enmienda §3 U12, fila «13»: «El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`)». X04 y X06 son del Paso 9, diferido.)**
  - `manifest`: `manifest.json` con SHA-256 por archivo, `started_at`, semillas, `generator_version`, digests (leídos del clúster), tamaño de `test` y las **solicitudes repetidas** entre escenarios (misma fila de U5 enviada en dos escenarios, NFR-U12-11); tope de 50 MB.
  - **`runId`** (pendientes posteriores al cierre, 2026-10-10): un solo `runId` por verificación, generado por `prepare` con el formato `AAAAMMDD-HHMM` a partir de `started_at` en UTC, truncado al minuto (el que exige `rebuild-runid-check` de U3; pendientes consolidados, 2026-10-10); es el `probes.runId` de los ~~tres~~ Jobs (~~`x04-probe-<runId>` de U9, `x06-probe-<runId>` de U3 y~~ `rt5-demo-<runId>` de U8). El manifiesto guarda ese `runId` y los nombres esperados de los ~~tres~~ Jobs; el oráculo de cada uno compara contra ellos. **(Solo `rt5-demo-<runId>`: misma cita de la fila «13».)**
  - `prepare` **se niega** si ya existe un `manifest.json` en el directorio de la verificación: así una retoma nunca reinicia `started_at` a mitad de camino. Para empezar otra verificación se usa un directorio nuevo.
  - **Tiempo medido** (NFR-U12-31): cada sección registra en el manifiesto su inicio y su fin, y el informe muestra la duración por sección y la total, con las esperas de los PRs del operador aparte.
  - **Consultas guardadas** (NFR-U12-50): cada consulta a Prometheus y a Loki que usa un oráculo se guarda en la evidencia con su texto, su ventana de tiempo y el `correlation_id` o prefijo de la corrida.
  - `CODEOWNERS` del monorepo: `system-verification/evidence/` para los equipos `calidad` y `cumplimiento` (crearlos si no existen).
  - Diseño: NFR-U12-10, 20, 30; INF-U12-04.
  - **Aceptación**: `uv run pytest system-verification/tests/integration/test_cli.py` (interrumpir en `rt3` y retomar → no se repiten las anteriores; manifiesto con todos los campos; > 50 MB → resumen y hash; `network` sin `prepare` → se niega; `prepare` con un manifiesto existente → se niega y `started_at` no cambia; dos escenarios con la misma fila de U5 → el manifiesto la lista; el informe muestra la duración por sección; cada evidencia con oráculo de Prometheus o Loki incluye su consulta; `prepare` → manifiesto con `runId` y `started_at` y el parche de values con ese `runId` ~~en los tres archivos de values~~; `started_at = 2026-10-12T14:07:31Z` → `runId = 20261012-1407` (pendientes consolidados, 2026-10-10); revisión del plan de tareas de U12, 2026-10-10)~~; un PR de fixture que toca solo `system-verification/evidence/` pide la aprobación de *code owners* (prueba de `branch-protection-check` de U4).~~ **(El parche va en un archivo, `values/kind/case-management.yaml`. Diferida la prueba con `branch-protection-check`: enmienda §3 U12, fila «13»: «Se difiere la prueba de `CODEOWNERS` con `branch-protection-check`, porque depende de U4 Paso 14, que está en D». `network` es una sección diferida: el caso «sin `prepare` → se niega» se prueba con `decisions`.)**

### Bloque F — Imagen, CI y documentación

- [ ] **Paso 14 — Repositorio, migraciones, frontend y despliegue en el clúster: N/A** (N/A; se comprueba aquí, CA-16)
  - U12 no tiene base de datos, interfaz ni recursos de Kubernetes.
  - **Aceptación**: `test ! -d system-verification/chart && test ! -d system-verification/migrations`; la imagen no contiene manifiestos de Kubernetes.

- [ ] **Paso 15 — Imagen** (E\*)
  - Python oficial por digest, sin privilegios; incluye `kubectl`, Playwright y su Chromium por versión fijada (el Chromium sin interfaz del login del Paso 5). **k6 no va en esta imagen** (pendientes posteriores al cierre, 2026-10-10): corre en su propio contenedor (`grafana/k6` por digest), con límites de 2 CPU y 2 GiB, que **el operador** lanza en la red de kind con el comando que imprime la sección `load` (Paso 11, INF-U12-05; pendientes consolidados, segunda tanda, 2026-10-10);
  - **sandbox de Chromium** (pendientes posteriores al cierre, 2026-10-10): el contenedor corre como usuario no root con el perfil `seccomp` que publica Playwright para Chromium (`chrome.json`) y espacios de nombres de usuario sin privilegios; **nunca** con `--no-sandbox`. Si el host no los permite, la sección que necesita login termina con un error claro;
  - la imagen se construye, ~~se escanea, lleva SBOM y se firma con `sign-image.yml` de U1~~ (frase separada, pendientes consolidados, 2026-10-10). **(Diferido por la demo, T1: alcance §3 U12, fila «14 N/A · 15 Imagen: N/A · E\*, T1»; T1: «Firma Cosign, SBOM y attestations de imágenes y paquetes». El escaneo se difiere con el mismo criterio que en U11-T03, U08-T05 y U10-T05; ver «Contradicciones» 14.)**
  - Diseño: INF-U12-01.
  - **Aceptación**: `hadolint system-verification/Dockerfile`; ~~el SBOM lista `kubectl`, Playwright y Chromium con su versión y **no** `k6`;~~ prueba de humo: Chromium arranca con el sandbox activo bajo el perfil `seccomp` (`chrome://sandbox` sin errores). **(Sin SBOM, T1. Las versiones y la ausencia de `k6` se comprueban dentro de la imagen, CA-17, como «sin numpy» en U9: enmienda §3 U9, fila «11».)**

- [ ] ~~**Paso 16 — Workflow de CI**~~ **(Diferido por la demo: enmienda §3 U12, fila «16: D, D»; T4. No entra; ver «Fuera».)**

- [ ] **Paso 17 — Documentación y trazabilidad** (E\*F)
  - `system-verification/README.md`: cómo ejecutar cada sección, requisitos (K16, PRs preparados, `runId` de los Jobs en formato `AAAAMMDD-HHMM` y el sync manual de las ~~**tres Applications** `bias-monitoring`, `decision-registry-rebuild` y~~ `case-management`; pendientes consolidados, 2026-10-10), presupuesto de tiempo (con las esperas de PRs aparte), cómo leer el informe y su límite. **(Solo `case-management`: enmienda §3 U12, fila «13». «README de lo que entra»: enmienda §3 U12, fila «17».)**
  - El README dice también cómo llegan al contenedor el kubeconfig, el certificado raíz y la sesión de Vault **sin escribirse en disco** (montajes de solo lectura del kubeconfig y del certificado; token de Vault como variable de entorno; sistema de archivos de solo lectura salvo el directorio de evidencias y un `tmpfs`; deployment-architecture §2b),~~ y cómo lanzar el contenedor de k6 con sus límites~~ (pendientes posteriores al cierre, 2026-10-10). **(k6 es de la sección `load`, Paso 11, diferido: enmienda §3 U12, filas «8b · 9 · 11: D» y «17: README de lo que entra».)**
  - Trazabilidad de cada BR-U12 a una prueba. **(Con la lista «Diferido por la demo»: enmienda §3 U12, fila «17»: «trazabilidad con lista»; §2, regla 4.)**
  - **Aceptación**: `test -s system-verification/README.md`; `uv run python platform/tests/test_traceability.py --unit system-verification --all`.

### Estructura de destino (§1 del plan): lo que esta tarea crea o llena

```text
vectra-risk/system-verification/
|-- Makefile  .importlinter  pyproject.toml          # se modifican (objetivos nuevos; punto de entrada `vectra-verification`)
|-- Dockerfile  Dockerfile.dockerignore  README.md   # nuevos (Pasos 15 y 17)
|-- seccomp/chrome.json                              # nuevo: el perfil que publica Playwright, copiado con su origen y su SHA-256 (P-8)
|-- src/vectra_verification/
|   |-- cli.py  manifest.py                          # Paso 13 (hoy vacios)
|   |-- store.py                                     # nuevo, no esta en §1 (P-5): el UNICO escritor de `evidence/`, con el filtro
|   `-- scenarios/u11.py                             # nuevo, no esta en §1 (P-4): la seccion `u11` y la evidencia `dashboard`
|-- demos/
|   |-- journey-7-3.md  journey-7-4.md  rt-5.md  dashboard.md
|   |-- verify/   journey-7-3.sh  journey-7-4.sh  rt-5.sh  dashboard.sh  (y `lib.sh` si hay codigo comun)
|   `-- prs/      f22-apagado/  rt5-run-id/  rt3-staging/  proxy-staging/  promocion/     # un directorio por PR preparado
|-- evidence/                                        # sigue vacio (solo `.gitkeep`): lo llena el operador en U12-T05
`-- tests/
    |-- unit/         test_demos_closed_world.py  test_prepared_prs.py  test_store.py  test_manifest.py  test_u11.py
    |-- integration/  test_cli.py
    `-- image/        test_image.py                  # fuera de `make test`: lo corre `make test-image`

vectra-risk/aidlc-docs/construction/system-verification/code/cli.md                  # nuevo
vectra-risk/aidlc-docs/construction/system-verification/evidence/cierre-demo.md      # nuevo, SOLO la seccion «Diferido por la demo» (CA-23)
```

`test_cli.py` es el nombre de la aceptación del plan: es fijo. Los demás son una propuesta; lo que cambies va a la bitácora. Los criterios filtran con `-k`.

**No** se crean: `scenarios/rt1.py`, `rt4.py`, `x_network.py`, `x_behavior.py`, `logs_pii.py`, `case_size.py` ni nada en `load/` (diferidos); `chart/` ni `migrations/` (Paso 14); `.github/workflows/system-verification.yml` (Paso 16).

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas (CA-26).
2. `aidlc-docs/construction/system-verification/code/cli.md`: nuevo. Si cambias una firma de T02 o T03, también `clients.md` o `scenarios.md`.
3. `aidlc-docs/construction/system-verification/evidence/cierre-demo.md`: nuevo, con el encabezado «en curso; lo completa U12-T05» y **solo** la sección `## Diferido por la demo`. La necesita la aceptación del Paso 17.
4. `.github/CODEOWNERS` (en la raíz del repositorio, **no** en `vectra-risk/`): **no debería cambiar**. La línea `vectra-risk/system-verification/evidence/ @jjlloobb @joseluisjedi` ya existe (línea 9). Solo se toca si P-7 decide otra cosa.
5. `case-management/Makefile`, **una línea** (la 68, objetivo `policy-chart`): solo si P-3 = (a). Ver «Contradicciones» 2.
6. `system-verification/tests/doubles/keycloak_tc.py`: es de la unidad; va aquí por la condición de «Reparación temporal del realm».
7. `CANDIDATAS.md` y `bitacoras/U12-T04.md` (nuevo).
8. `uv.lock` y `pyproject.toml` raíz: no deberían cambiar (un punto de entrada no cambia el lock). Si cambian, la bitácora dice por qué.

`platform/`, `vectra-risk-gitops/`, `model-serving/`, `governance/`, `console/`, `product-metrics/`, `identity-edge/` y `contracts/` **se leen, no se editan**. Los PR preparados son archivos de `demos/prs/`: **los abre el operador**, no esta tarea. Las pruebas los aplican en una copia de trabajo temporal y los revierten (CA-3).

### Lo que los guiones tocan de verdad

Comprobado al redactar sobre `origin/main` `8dc7499`. Verifícalo en tu rama y anota «igual» o lo que cambió.

**PR preparados (`demos/prs/`)**

| PR | Archivo y clave | Estado en `main` | Application que se sincroniza |
|---|---|---|---|
| `f22-apagado` | `platform/network/flows.yaml`, línea 6: `env_disabled: { kind: [], staging: [], prod: [] }` → `kind: [F22]`. Más lo regenerado: `platform/network/generated/kind/vectra-app.yaml`, `vectra-serving.yaml` y `connectivity-suite.yaml` | Existe. `generate.py`, línea 391, lee `env_disabled`. Medido con `build("kind", …)`: desaparecen **5** recursos: `NetworkPolicy` `allow-f22-explainability-service-to-explainer-egress` (`vectra-app`), y en `vectra-serving` `NetworkPolicy` `allow-f22-to-explainer-ingress`, `AuthorizationPolicy` `f22-explainer-8080`, `MeshTLSAuthentication` `f22-explainer-8080-mtls` y `Server` `explainer-8080` | `network` (`components.yaml`, línea 37: `platform/network/generated/{env}`, sin `connectivity-suite.yaml`), con prune |
| `rt5-run-id` | `vectra-risk-gitops/values/kind/case-management.yaml`: agrega `runId` bajo `probes:` (líneas 5 y 6: `probes.enabled: true`) | Existe. El formato `^[0-9]{8}-[0-9]{4}$` lo valida **la plantilla** (`case-management/chart/templates/rt5-demo-job.yaml`, línea 9, con `fail`), no un `conftest`: `policies/conftest/values.rego` solo lo **rechaza** en staging y producción | `case-management` (`apps/kind/case-management.yaml`: `targetRevision: main`, tres `valueFiles`), con prune |
| `rt3-staging` | `vectra-risk-gitops/values/kind/model-serving.yaml`, clave `inferenceServices` (hoy `[]`): una entrada `{ modelVersionId: <M1>, storageUri: "s3://model-store/adversarial/rt3/RT3-a/", profile: staging }` | El esquema lo admite (`model-serving/docs/values.md`; `adversarial/` solo en `staging`). El nombre es `isvc-<8 hex de M1>` en `vectra-staging`: **RT3-a y RT3-d no caben a la vez** (`model-serving/docs/paso-11-kind.md`, líneas 136 a 143: «uno a la vez») | `model-serving` |
| `proxy-staging` | Mismo archivo y clave: `{ modelVersionId: <M2>, storageUri: "s3://model-store/<M2>/", profile: staging }`, antes de `rt2-setup` | Igual. `<M2>` es el `model_version_id` de `reference-model/.out/proxy/run-1/manifest.json` | `model-serving` |
| `promocion` | No es un parche: los cuatro PR los crea `promotion-tool` (`governance/promotion_tool/vectra_promotion/cli.py`, líneas 31 a 37: `list-promotable`, `create-promotion-pr`, `post-activation-pr`, `rollback-pr`, `mark-active … --evidence`) | Existe. La invocación completa está en `governance/docs/paso-20-kind.md`, líneas 174 a 232 | `model-serving` |

- **Los digests no son un PR preparado.** Ningún archivo de `vectra-risk-gitops/values/kind/` trae hoy una clave de digest, `values/kind/product-metrics.yaml` no existe, y todos los charts llevan el digest de ejemplo (`sha256:00…`): los pods quedarían en `ImagePullBackOff`. Es un prerrequisito de instalación del operador (U12-T05), con el `docs/imagenes.md` de cada unidad. El README lo lista; no va en `demos/prs/`.
- `M1` y `M2` solo existen tras `make -C reference-model release`: los PR `rt3-staging` y `proxy-staging` son **plantillas** con ese hueco, no parches fijos (P-6).
- Todas las Applications apuntan a `main`: cada PR preparado se **fusiona** antes del sync.

**Lo que un `verify/*.sh` puede leer** (`platform/rbac/verification-operator/k16.yaml`)

| Namespace | Recursos y verbos de K16 |
|---|---|
| `vectra-app` | `pods` y `jobs` (`get`, `list`, `watch`); `horizontalpodautoscalers`; `pods/log` (`get`); `pods/portforward` (`create`) |
| `vectra-serving` | `pods`, `horizontalpodautoscalers`, `inferenceservices.serving.kserve.io` |
| `vectra-observability` | `pods`; `pods/portforward` |
| `vectra-edge`, `vectra-identity`, `vectra-data` | `pods` |
| `vectra-mock`, `vectra-staging`, el namespace de Argo CD, `vault` | **nada** |

K16 **no** da: `cronjobs`, `deployments`, `services`, `networkpolicies`, `prometheusrules`, `applications`, `configmaps` ni `secrets`, en ningún namespace. El contador del mock y las alertas se leen por Prometheus, no por `kubectl`.

| Qué lee un `verify` | Nombre real | Dónde está |
|---|---|---|
| Job de RT-5 | `job/rt5-demo-<runId>` en `vectra-app`; su pod, con `-l job-name=rt5-demo-<runId>` | `rt5-demo-job.yaml`, líneas 11 a 31 |
| Pod del registro | `-l app.kubernetes.io/name=decision-registry-service` en `vectra-app`, puerto 8080 | `decision-registry/chart/values.yaml`, línea 49 |
| Pod de Prometheus | `-l app.kubernetes.io/name=prometheus` en `vectra-observability`, puerto 9090 | Valor de partida de U12-T02, **sin comprobar en kind** |
| `InferenceService` activo y del proxy | `isvc-<8 hex finales del model_version_id>` en `vectra-serving` | `model-serving/docs/values.md` |
| Alertas | `CoreWriteAttempt` (sin `for:`, ventana de 5 min) y `FailClosedPersistente` (`for: 1m`) | `case-management/chart/templates/prometheusrule.yaml`, línea 22; `platform/observability/rules/platform-rules.yaml`, líneas 143 a 150 |
| Series | `vectra_core_write_attempts_total`; `vectra_cases_failclosed_persistent`; `inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"}`; `vectra_bias_last_run_timestamp` y `vectra_bias_last_run_ok` | La tabla de U12-T03 |
| Cron de bias | `2,17,32,47 * * * *` | `bias-monitoring/chart/values-monitoring-policy.yaml`, línea 7 |
| Agregador de U3 | `*/5 * * * *` | `decision-registry/chart/values.yaml`, línea 29 |

**Lo que el presentador abre**

| Qué | Nombre real | Dónde está |
|---|---|---|
| Consola | `https://vectra.localtest.me/` | `guard.py`, línea 37; `vectra-risk-gitops/values/kind/console-spa.yaml` |
| Bandeja y detalle | `/casos` y `/casos/:caseId`: roles `analista` y `cro` | `console/spa/src/views/shared/routes.ts`, líneas 41 y 42 |
| Modelos | `/modelos` y `/modelos/:modelId`: `ingeniero_riesgo`, `cro`, `cumplimiento` | líneas 47 y 48 |
| Congelamientos | `/congelamientos`: `cumplimiento` y `cro`. `/congelamientos/:freezeId` (el paquete y `ResolveFrozenDialog`): **solo `cumplimiento`** | líneas 52 y 53; `views/governance/FreezeContextView.tsx` |
| Vistas **diferidas** (muestran el marcador «no disponible»; el guion **no** las abre) | `/fallos` (`PersistentFailures`), `/sesgo` (`BiasDashboard`), `/politicas`, `/fuentes`, `/expedientes`, `/integridad`, `/casos/nuevo` | líneas 43 a 51: `entry: false` |
| Textos que se ven | «En sincronización», «No disponible», «Modelo congelado», «Congelado» | `console/spa/src/i18n/labels.es.json`, líneas 5 a 7 y 125 |
| Usuarios semilla | `analista-1`, `analista-2` (`analista`); `ingeniero-1`, `ingeniero-2` (`ingeniero_riesgo`); `cro-1`, `cro-2` (`cro`); `cumplimiento-1`, `cumplimiento-2` (`cumplimiento`); `operacion-1`, `operacion-2` (`operacion`) | `identity-edge/keycloak/realm/realm.kind.yaml`, líneas 689 a 812 |
| Dashboard de producto | «Producto», uid `vectra-producto-panel`, carpeta `Vectra / Producto` (equipos `cro`, `cumplimiento`, `ingeniero_riesgo`: `View`). Paneles: «North Star de ayer», «Recomendaciones sostenidas (aproximación)», «Tasa de consulta de la explicación y piso F», «Días bajo el piso» | `product-metrics/observability/dashboards/product.json`; `platform/observability/grafana/folder-permissions.yaml`, línea 4 |
| Dashboard de operación | «Operación», uid `vectra-operacion-panel`, carpeta `Vectra / Operación` (equipo `operacion`: `Edit`) | `platform/observability/dashboards/operacion.json`; `kustomization.yaml`, línea 10 |
| **Grafana por el gateway** | La ruta `/grafana` existe, pero Grafana **no** tiene `root_url`, `serve_from_sub_path` ni OIDC | `platform/observability/values/kube-prometheus-stack.yaml` (sin `grafana.ini`); `CANDIDATAS.md`, línea 82. Ver «Contradicciones» 1 y P-2 |

**Tiempos reales**

| Demo | Tiempo | De dónde sale |
|---|---|---|
| D1 | **≥ 19,3 min** del primer caso de sonda a `no_disponible`; ≈ 21 min hasta `FailClosedPersistente` en `firing` (gauge cada 30 s, `for: 1m`). Aparte: 2 PR con su sync (apagar y revertir) | `case-management/src/vectra_case/config.py`, líneas 35 a 38 (30 s × 2^(n−1), ±20 %, 6 intentos) |
| D2 | **> 75 min** con 1 versión: lote (1 500 a 10/s ≈ 2,5 min), `freeze` (hasta 30 min), 3 corridas de bias (≈ 45 min), reactivación, 1 corrida más (≤ 15 min), barrido de U8 (5 min). Aparte: 4 PR de `promotion-tool` y 2 de `proxy-staging` | Cron de bias cada 15 min; `tareas/U12-T03…`, «Contradicciones» 9 |
| D3 | El Job tarda segundos. `CoreWriteAttempt` no tiene `for:` y su expresión mira 5 min: **la alerta se ve en `firing` unos 5 min y se apaga sola** | `prometheusrule.yaml`, líneas 22 a 28 |
| D4 | Día D: `decisions` estima 2 000 / 10 + 2 000 × 1 s + 300 s ≈ 42 min y **no empieza si no termina antes de las 23:00 UTC** (18:00 de Colombia): hay que lanzarla antes de ≈ 22:18 UTC (17:18). Día D + 1: empieza a las 00:00 UTC (19:00 de Colombia del día D); la pasada completa de U11 es a las **02:30 UTC** más hasta 10 min de desfase (≈ 21:30 a 21:40 de Colombia del día D) | `guard.py`, líneas 49 a 51 y 109; `product-metrics/src/vectra_product/config.py`, líneas 14 y 15 |

### Precisiones

**Paso 13 — CLI** (NFR-U12-03, 10, 20, 30, 31, 32, 50; BR-U12-11, 13)

- **Punto de entrada:** `vectra-verification <sección> [opciones]`, en `[project.scripts]`; también `python -m vectra_verification.cli`. Una subcomando por cada una de las 14 secciones de `guard.SECTIONS`.
- **Secciones que entran:** `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report`, en el orden de business-logic-model §2.1. **Las 6 diferidas** (`network`, `rt1`, `rt4`, `load`, `pii`, `resilience`) existen como subcomando: no hacen ninguna solicitud, escriben en el manifiesto «diferida por la demo» con la cita, y salen con el código de `no ejecutado`. Así el informe las lista (alcance §3 U12, fila 13: «Las demás quedan registradas como `no ejecutado` (BR-U12-11)»).
- **Barreras, en este orden y antes de la primera solicitud:** `guard.check_environment` (emisor y host), `guard.check_section`, y las propias: `decisions` → `guard.check_decisions` (barrera horaria, y ≤ 100 en staging); la reactivación solo dentro de `rt2`. En staging: `prepare` sin parche (`check_job_patch`), `decisions`, `u11` y `report`; lo demás se niega.
- **Códigos de salida** (P-10): `0` = la sección terminó y todo lo suyo es `pasa`; `1` = algún `falla`; `2` = `no ejecutado` (faltó un prerrequisito, o es una sección diferida); `3` = la herramienta se negó (barrera, uso, `prepare` ausente o repetido). `falla` y `no ejecutado` nunca comparten código ni texto.
- **`--help`** (general y de cada sección): código 0, sin red, sin leer la bóveda, sin escribir archivos y **sin importar** `playwright` ni `pyarrow`.
- **Retoma:** el manifiesto guarda, por sección, `started_at`, `finished_at` y estado. Una sección terminada no se repite salvo con `--redo`. Una sección interrumpida se retoma en la fase que U12-T03 expone. `--from <sección>` corre desde ahí en orden. **Ninguna** sección espera a un PR dentro de otra: las esperas del operador se registran aparte (NFR-U12-31).
- **Todo lo que va a `evidence/` pasa por un solo escritor** (`store.py`): llama a `evidence.prepare` con `Credentials.secret_values()` antes de escribir, escribe en un temporal y renombra. Si el filtro falla, **no queda archivo**. Una prueba estática comprueba que ningún otro módulo de `src/` abre un archivo para escribir (CA-9).
- **`decisions`:** `run_decisions` de U12-T02 y, al final, `SIM-NORMAL` de U12-T03 con el `RunReport`. **El conductor debe esperar a `listo`** (F-04 de `revisiones/U12-T02/ronda-1.md`, destino U12-T03): la tarea de U12-T03 **no lo recoge** (comprobado: no nombra `not_ready` ni el conductor). Si al crear la rama sigue sin resolver, entra aquí: la sección sondea con el reloj inyectado hasta que no quede ningún caso del `RunReport` en `en_evaluacion`, o hasta un plazo, **antes** de lanzar el conductor (CA-8). Si U12-T03 ya lo resolvió, se comprueba y no se duplica.
- **`u11`** (hueco del plan: ningún paso define su oráculo; P-4). Produce la evidencia `dashboard`. Con `PromClient`:
  - se niega con `no ejecutado` (`u11_antes_de_d_mas_1`) si el día UTC actual no es posterior al día UTC en que terminó `decisions` (del manifiesto);
  - lee **las mismas expresiones que los paneles** de `product.json`: «North Star de ayer» (`vectra:product_north_star_ratio:dedup{period="day", channel="all", outcome="all", model_version_id="all"}`), «Recomendaciones sostenidas», «Tasa de consulta» y «Días bajo el piso». La prueba las **toma del archivo**, no las copia;
  - `pasa` si las cuatro tienen valor y `ALERTS{alertname="ProductMetricsStale", alertstate="firing"}` no tiene puntos; una serie ausente es `falla` con su nombre, salvo antes de las 02:40 UTC del día D + 1 más el plazo de la pasada, que es `no ejecutado`;
  - **no** verifica `RuidoExplicacion` (BR-U12-06: se verifica con `promtool`, no en kind). La evidencia lo dice.
- **Evidencias de las cuatro demos** (hueco del plan; P-4). `report.ELEMENT_IDS` trae `journey-7-3`, `journey-7-4`, `rt-5` y `dashboard`, y el mapa las exige (US-111, 303, 305, 603, 304, 503 a 505), pero ningún paso dice quién las escribe. Aquí: **las escribe la sección de cada demo**, con el escritor único: `rt3` → `RT-3` y `journey-7-3` (F22 más la escalada a `no_disponible` y `FailClosedPersistente`, con `wait_for_escalation`); `rt2` → `RT-2`, `RT2-LATENCY` y `journey-7-4` (el paquete y la resolución con MFA); `rt5` → `RT-5` y `rt-5`; `u11` → `dashboard`. Los `verify/*.sh` **no escriben evidencias**: imprimen.
- **`report`:** `verification-report.md` con `report.render`: encabezado con `MANIFEST_LIMIT`; una fila por elemento y por historia, con su estado; duración por sección y total, con las esperas del operador aparte; y una sección «No ejecutado y por qué», con el motivo de cada uno (diferido por la demo, prerrequisito, K16). Se puede generar en cualquier momento.

**Paso 13 — `prepare`** (INF-U12-02)

- Genera el `runId` (`AAAAMMDD-HHMM` de `started_at` en UTC, truncado al minuto), escribe el manifiesto inicial y el parche. **No hace ninguna solicitud**: ni clúster, ni bóveda, ni gateway. Recibe por parámetro el directorio de la verificación, el `commit` y el operador (la imagen no trae `git`; P-10).
- **El parche** es un diff unificado que `git apply` acepta sobre `main`: agrega `runId: "<runId>"` bajo `probes:` en `vectra-risk-gitops/values/kind/case-management.yaml`, **entre comillas** (sin ellas YAML lo leería como texto igual, pero un `runId` solo de dígitos no). No toca `bias-monitoring` ni `decision-registry-rebuild`, ni ningún archivo de staging o producción. Se escribe en el directorio de la verificación.
- Se niega si ya hay `manifest.json` (y `started_at` no cambia). En staging no produce parche.

**Paso 13 — manifiesto**

- `manifest.json`: SHA-256 por archivo; `started_at`; `runId` y el nombre esperado `rt5-demo-<runId>`; semillas; `generator_version`; tamaño de `test`; solicitudes repetidas entre escenarios; `commit`; operador; por sección, inicio, fin y estado; y los digests **leídos del clúster** al empezar cada sección que lo toca (`imageID` de los pods de los namespaces de K16), no en `prepare`.
- **No lleva** secretos ni datos del solicitante: ningún token, contraseña, semilla, llave ni campo de `ApplicationIn`; solo `case_id`, conteos y posiciones de fila (CA-10).
- Tope de 50 MB: lo que lo supere se sustituye por un resumen y el hash del original.

**Paso 12 — guiones y `verify`** (BR-U12-09)

- **Cada guion** (`demos/<demo>.md`) tiene: prerrequisitos; tiempo real (la tabla de arriba); una tabla numerada de pasos con **quién** (presentador u operador), **qué hace**, **qué se ve y dónde** (ruta de la SPA, panel, texto) y **qué `verify` lo comprueba**; qué deja sucio y cómo se limpia; y qué saldrá `no ejecutado`. Los pasos son los de la enmienda §1.1 a §1.4, **con las correcciones de «Contradicciones»**.
- **Cada `verify/<demo>.sh <paso>`:** comprueba el estado esperado tras ese paso y sale con 0 (como se esperaba), 1 (no) o 2 (no se pudo leer). Solo usa: `kubectl` con `get`, `logs`, `auth can-i` y `port-forward`, sobre lo que K16 da; la API de lectura de Prometheus por `127.0.0.1` tras un `port-forward` a un pod; y los archivos que la sección ya escribió en el directorio de la verificación. **No** inicia sesión, no lee la bóveda, no escribe en `evidence/` (P-5). Lleva `--context` literal o `"${KUBE_CONTEXT:-kind-vectra}"`.
- **Palabras que el detector de verbos rechaza en `demos/`, `README.md` y `Dockerfile`** (`test_kubectl_verbs.py`, líneas 143 a 158): el nombre del binario de Argo CD seguido de cualquier texto (también como nombre de namespace), y el de `kubectl` seguido de una palabra que no sea un verbo permitido. Los guiones dicen «sincroniza la Application `network` en Argo CD, con prune» y no escriben la orden. La orden de `promotion-tool` con su `--diff-command` (que contiene un `diff` de `kubectl`) **no se copia**: se remite a `governance/docs/paso-20-kind.md`.
- **D1 (`journey-7-3.md`):** el presentador mira `/casos` con un usuario que la herramienta no esté usando en ese momento (P-11). **No** abre `/fallos`: está diferida (P-16 de la enmienda sigue pendiente). «Escala como incidente técnico» se enseña con `FailClosedPersistente`. El paso `rt3-staging` va marcado **opcional**: K16 no llega a `vectra-staging`, así que su resultado es `no ejecutado` (decisión del usuario), y RT3-a y RT3-d van uno a la vez. Los casos `no_disponible` y la alerta **siguen activos** en D2 y D4: el guion lo dice.
- **D2 (`journey-7-4.md`):** orden real: `proxy-staging` → `rt2-setup` → promoción (4 órdenes de `promotion-tool`, por referencia) → `rt2`. El paquete se enseña en `/congelamientos/:freezeId` con `cumplimiento`. Quién reactiva: P-12. Avisa del riesgo de U03-T07 (504 al cron) y de que `/sesgo` no se abre.
- **D3 (`rt-5.md`):** PR `rt5-run-id` → sync → Job → `rt5`. **La alerta se enseña en los 5 min siguientes al Job**; después, con la evidencia de `rt5` (`query_range`).
- **D4 (`dashboard.md`):** día D y día D + 1 con las horas de la tabla; el aviso del arranque de `product-metrics` (dashboard vacío hasta 30 min si arrancó antes que el registro); el aviso del día 1 del mes (falta `month_to_date`); y el acceso a Grafana según P-2.

**Paso 12 — detector de verbos y F-06** (`CANDIDATAS.md`, línea 649; P-13)

El detector **se amplía**, no se relaja. Cada forma aceptada tiene un fixture en `allowed/`, y cada forma vecina que debe seguir cayendo, uno en `prohibited/`:

| Forma | Decisión | Por qué no abre un hueco |
|---|---|---|
| `POD=$(kubectl get pods … -o name)` | **Se acepta** si la orden de dentro tiene un verbo permitido | Es la forma que INF-U12-03 manda (elegir el pod y reenviar a `pod/<nombre>`). El verbo de dentro se juzga igual. `K=kubectl` y `$(which kubectl)` siguen cayendo |
| `kubectl port-forward … &` | Ya pasa (`&` es separador) | — |
| `nohup`, `watch`, `xargs`, `eval`, `env`, `sudo`, `exec` delante | **Se siguen rechazando** | Un `verify` no es interactivo y no los necesita; `xargs` y `eval` traen el verbo de otra parte |
| `kubectl --context "$(ctx)" get` | **Se sigue rechazando** | El contexto va literal: evita correr contra otro clúster |
| El binario como **ruta o referencia**, no como orden: lo que sigue empieza por `/`, `:`, `@` o `https://` (`COPY … /usr/local/bin/kubectl /…`, la URL de descarga) | **Se acepta**, solo en `Dockerfile` | `kubectl` no ejecuta nada con ese primer argumento. Una palabra, una variable (`$V`) o una bandera desconocida siguen cayendo |
| Prosa Markdown | **Sin cambio**: el nombre solo, en código en línea, ya pasa | La regla de redacción va en `cli.md` |
| Archivos `*.patch` de `demos/prs/` | Se juzgan **solo las líneas añadidas** (`+`) | El contexto de `flows.yaml` (línea 4) nombra el namespace de Argo CD en una lista: sin esto, el parche de F22 hace fallar la prueba. Una línea añadida con una orden prohibida sigue cayendo |

**Paso 15 — imagen** (INF-U12-01; NFR-U12-01, 04)

- `system-verification/Dockerfile`, multi-etapa, contexto en la raíz de `vectra-risk/`; cada `FROM` por digest (el de los demás: `docker.io/library/python:3.12-slim@sha256:aa943ce4…`, `product-metrics/Dockerfile`, línea 6). Sin `vectra_common`.
- **Usuario sin root y uid arbitrario.** `USER 65532:65532`, pero el operador la corre con `--user "$(id -u):$(id -g)"` para poder escribir en el directorio de evidencias de su checkout. La imagen debe funcionar con **cualquier** uid sin root: `HOME` en el `tmpfs`, y los navegadores en una ruta legible por todos (`PLAYWRIGHT_BROWSERS_PATH`).
- **Sistema de archivos de solo lectura:** `--read-only`, con el directorio de evidencias montado y un `tmpfs`.
- **Playwright 1.64.0 con el Chromium de su revisión (1248)**, instalado en la construcción; ningún otro navegador.
- **Sandbox:** perfil `seccomp/chrome.json` y espacios de nombres de usuario; **nunca** `--no-sandbox`. Sin ellos, error claro.
- **CA para los dos caminos TLS** (F-02 de `revisiones/U12-T02/ronda-1.md`): el archivo montado se pasa como `ca_file`; Node lo recibe por `NODE_EXTRA_CA_CERTS` y Chromium por la huella SPKI que U12-T02 calcula con esa CA. **Nada más:** sin `ignore_https_errors`, sin `--ignore-certificate-errors` a secas, sin `NODE_TLS_REJECT_UNAUTHORIZED`, sin instalar la CA en el almacén del sistema.
- **`kubectl` de la versión del clúster** (`platform/kind/cluster.yaml`, línea 18: `kindest/node:v1.37.0`), con su SHA-256 verificado en la construcción. **Sin** el binario de Argo CD, sin `helm`, sin `k6`, sin `git`, sin manifiestos de Kubernetes.
- **Red:** en kind, `vectra.localtest.me`, la API de Kubernetes del kubeconfig y los `port-forward` son `127.0.0.1` del host: el contenedor corre con `--network host`. El README lo dice.
- `docs` de la imagen dentro del README: construir, comprobar y la orden `docker run` completa. **Publicarla (push y digest) es del operador** (U12-T05); aquí no se hace.

**Paso 17 — README y trazabilidad**

- `README.md` de lo que entra: las 8 secciones con su orden y sus códigos de salida; las 6 diferidas; prerrequisitos del operador (abajo); la orden `docker run`; **los tiempos reales de cada demo**; cómo leer el informe y su límite; y **qué marcará `no ejecutado` y por qué**: US-106, 109, 604, 608, 609 y 610 (secciones diferidas), US-603 (falta `X01`) y US-305 (falta `X03`) aunque RT-5 y `journey-7-4` pasen, RT3-b y «a y d desplegados», y `RT2-LATENCY` con 1 medición (`CANDIDATAS.md`, línea 641).
- **Prerrequisitos del operador:** U1 a U11 instalados con digests reales; política y modelo de referencia activos; paquetes proxy y RT-3 en el model-store (`model-serving/docs/paso-11-kind.md`, línea 55); K16; **el camino a la bóveda** (P-9); el certificado raíz exportado; las semillas TOTP que el presentador necesita en su teléfono (P-11); el eco de U2 y la `ServiceAccount` temporal de U4 retirados; `CASE_ALLOW_TEST_SCENARIOS` (`allowTestScenarios: true`, ya en los values de kind).
- **Trazabilidad:** tabla BR-U12-01 a 13 → prueba, en `cli.md`. La lista «Diferido por la demo» en `evidence/cierre-demo.md`, con el formato de `platform/tests/test_traceability.py` (líneas 13 y 14): identificador, paso del plan, cita, qué falta. Hoy quedan sin trazar tras U12-T03: INF-U12-04 y NFR-U12-31 (**se trazan aquí**, Paso 13) e INF-U12-05 (Paso 11, diferido: **va en la lista**). Comprueba el conjunto en tu rama.
- **`Makefile`:** `check: lint types imports test shellcheck image test-image links traceability`. `test` ignora `tests/image/`. Se agrega `check-fast` (sin `image` ni `test-image`) para el ciclo corto; el revisor corre `check`.

**Reparación temporal del realm** (`DECISIONES-LOOP.md` §10; `tareas/U02-T22…`, línea 263)

`tests/doubles/keycloak_tc.py` repara el realm por la API de administración (`repair_shared_authenticator_configs`, línea 225; `complete_user_profiles`, línea 268; se llaman en las líneas 432 y 435). **Mientras existan, esconden el defecto.** Decisión: **la retirada entra en esta tarea si, al crear la rama, U02-T22 está en `main`** (CA-15 lo comprueba con una orden). Si no está, no se toca, y queda como primera línea de «Lo que T05 necesita»: U12-T05 no puede dar por bueno el login de kind con la reparación puesta.

**Plan.** Marca `[x] (U12-T04)` los Pasos 12, 13, 15 y 17, con sus notas (13: «8 secciones; parche solo de `case-management`; prueba de `CODEOWNERS` diferida»; 15: «sin escaneo, SBOM ni firma (T1)»; 17: «README de lo que entra; trazabilidad con lista»). El 14, `[x] (U12-T04)` con «N/A comprobado». El 16 sigue en `[ ]` con «(diferido por la demo: enmienda §3 U12)» antes del título.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Secciones `network`, `rt1`, `rt4`, `load`, `pii` y `resilience`**, más allá del subcomando que responde `no ejecutado`. Enmienda §3 U12, fila «13»: «Secciones `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report` (sale `pii`)».
- **`bias-monitoring` y `decision-registry-rebuild` en el parche de `prepare`**, y los Jobs `x04-probe` y `x06-probe`. Misma fila: «El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`)».
- **La prueba de `CODEOWNERS` con `branch-protection-check`.** Misma fila: «Se difiere la prueba de `CODEOWNERS` con `branch-protection-check`, porque depende de U4 Paso 14, que está en D».
- **Escaneo, SBOM y firma de la imagen**, y la línea de aceptación del SBOM. T1; alcance §3 U12, fila «14 N/A · 15 Imagen».
- **k6:** ni en la imagen ni en el README. Paso 11, diferido.
- **Paso 16** (workflow de CI) y `mutmut`. T4 y T3.
- **Abrir, fusionar o sincronizar un PR; publicar la imagen; ejecutar una sección contra kind.** Es de U12-T05 y del operador.
- **Editar otras unidades:** no se configura el OIDC de Grafana, no se amplía K16, no se cambia `flows.yaml`, no se escribe un digest en `values/kind/`. La única excepción posible es la línea de `case-management/Makefile` (P-3).
- **Pasos 18 y 19:** la verificación en kind, el resto de `cierre-demo.md` y el cierre.
- **Cualquier llamada a un clúster.** El kind de la máquina puede estar arriba: no se usa.

---

## Candidatas (`CANDIDATAS.md`)

Números de línea de `main` (`8dc7499`); las de la rama `tarea/U12-T02` se citan por su hallazgo.

**Se atienden aquí:**

| Dónde | Candidata | Qué se hace |
|---|---|---|
| Línea 649 (F-06 de U12-T01) | El detector de verbos rechaza formas legítimas | La tabla de «detector de verbos y F-06» (CA-4) |
| Rama T02, F-02 de la ronda 1 | La CA para Node y para Chromium en la imagen | CA-20 |
| Rama T02, F-04 de la ronda 1 | El conductor no espera a `listo` (destino U12-T03, que **no** la recoge) | `decisions` espera antes del conductor (CA-8), si sigue abierta |
| Línea 641 | El informe marcará `no ejecutado` varias historias | El informe y el README lo dicen, con el motivo (CA-13, CA-21) |
| Línea 639 | Nadie comprueba el ≥ 85 % (Paso 16 diferido) | Ya está en `make test` desde U12-T02; se conserva (CA-25) |
| Línea 615 | `probes.enabled` distingue kind | `prepare` solo agrega `runId`; no toca `enabled` (CA-11) |
| Rama T02 (`test_kubectl_verbs.py`) | `-n <namespace>` va después del verbo en las listas de Python | Se anota en `cli.md`; el detector no cambia en eso |
| `tareas/U02-T22…`, línea 263 | Retirar la reparación del realm | Condicionada (CA-15) |
| Línea 82 | Grafana sin `root_url` ni OIDC | Solo el guion de D4, según P-2. El arreglo es de U1 |

**Para U12-T05** (no las atiendas; van en «Lo que T05 necesita»):

- Línea 640 y rama T02 (F-06 de la ronda 1): K16 y el camino a la bóveda; la lista de hosts de la bóveda es global.
- Líneas 684 y 615, y `case-management/docs/imagenes.md`: digests de ejemplo e `ImagePullBackOff`.
- Rama T02: selectores y puertos de Prometheus y Loki, sin comprobar.
- Líneas 402 y 412: el eco de U2 y la `ServiceAccount` temporal `console-bff` de U4.
- Línea 598: `product-metrics` arranca antes que el registro.
- Líneas 619 y 679: memoria real de U8 y del BFF con 2 000 decisiones.
- Líneas 631, 659 y 675: CSP real, `/callback` y el `iss` de cada destino.
- Línea 689: las etiquetas reales de la serie del proxy de Linkerd.
- Línea 634: las constantes de la estimación de `decisions` (1 s por caso, 300 s).

**Se quedan** (no son de U12-T04 ni de T05): líneas 207 (marcadores de `LOGS-NO-PII`, diferido), 636, 638 y 642 (textos del diseño), 650 a 652 (generadores y evasiones con intención), 252 (AUC del proxy), 40, 47 y 48 (OIDC de Grafana, U1).

---

## Contradicciones entre plan, recorte, diseño y `main`

Vistas al redactar. **Las que romperían una demo delante del público, primero.** Deja en `CANDIDATAS.md` las que no estén ya.

1. **D4: el presentador no puede abrir Grafana por el gateway.** La enmienda §1.4 dice «El presentador abre Grafana `product.json`». La ruta `/grafana` existe y el realm trae el cliente `grafana` (`realm.kind.yaml`, línea 1008), pero los values de Grafana no tienen `grafana.ini`: ni `root_url`, ni `serve_from_sub_path`, ni `generic_oauth` (`CANDIDATAS.md`, líneas 40, 47 y 82, abiertas). Tampoco se pueden enseñar los permisos de carpeta por rol. P-2.
2. **D3: el PR de `runId` deja en rojo `make -C case-management check`.** `case-management/Makefile`, línea 68 (objetivo `policy-chart`): `! grep -rn "runId" vectra-risk-gitops/values/*/case-management.yaml …`. El comodín incluye `kind`: en cuanto el parche de `prepare` está en `main`, el objetivo falla. La regla de `conftest` solo prohíbe `runId` en staging y producción. P-3.
3. **D3: la alerta `CoreWriteAttempt` dura unos 5 min.** No tiene `for:` y su expresión compara con `offset 5m`. Si el presentador tarda, ya no está en `firing`. El guion lo fija; después de esa ventana se enseña la evidencia de `rt5`.
4. **D2: ¿quién reactiva?** La enmienda §1.2 pone la resolución en la SPA (`ResolveFrozenDialog`, el presentador); el plan (Paso 8) y U12-T03 (fase 9 de `rt2`) hacen que la reactive **la herramienta** con `cumplimiento-1`. No pueden hacerlo los dos, y Keycloak rechaza un TOTP repetido en la misma ventana si comparten usuario. P-12.
5. **D1 y D2: el presentador necesita contraseña y TOTP.** Todo login de la consola pide TOTP. Las semillas están en la bóveda (`identity/synthetic-users`), y `credentials.USERS` solo trae 5 usuarios, los mismos que la herramienta usa. Ningún documento dice cómo llegan al teléfono del presentador ni qué usuario usa. P-11.
6. **D1: `/fallos` está diferida.** «Escala como incidente técnico» no se puede enseñar con `PersistentFailures` (`routes.ts`, línea 44: `entry: false`); P-16 de la enmienda sigue pendiente. Se enseña la alerta.
7. **D1: RT3-a y RT3-d «desplegados» no caben a la vez** (mismo nombre `isvc-<8 hex de M1>` en `vectra-staging`), y K16 no lee ese namespace. El plan habla de «`a` y `d`, desplegados por PR». Van uno a la vez, opcionales, y su resultado es `no ejecutado`.
8. **D1: F22 apagado quita 5 recursos, no 4.** La enmienda §1.1 dice «2 NetworkPolicy, `MeshTLSAuthentication` y `AuthorizationPolicy`»; también cae el `Server` `explainer-8080`. Qué `last_cause` resulta (`timeout` o `explainer_unavailable`) se ve en kind.
9. **Todas: la imagen no alcanza nada sin `--network host`, ni escribe evidencias con el uid 65532.** `deployment-architecture.md` §2b habla de montajes y variables, no de la red ni del uid. En kind, el gateway, la API y la bóveda reenviada son `127.0.0.1` del host, y el checkout es del uid del operador.
10. **Todas: K16 no da camino a la bóveda** (`CANDIDATAS.md`, línea 640). `credentials` admite `127.0.0.1`, pero K16 no da `port-forward` en `vault`. En kind el kubeconfig del operador es de administrador y funciona; no por K16. P-9.
11. **El plan no define la sección `u11` ni quién escribe las cuatro evidencias de demo.** Paso 13 lista `u11`; ningún paso da su oráculo. El mapa exige `journey-7-3`, `journey-7-4`, `rt-5` y `dashboard`. Sin ellas, US-111, 303, 304, 503, 504 y 505 saldrían `no ejecutado` aunque todo pase. P-4.
12. **Los digests no pueden ser un PR preparado**, y el comentario de `values/kind/case-management.yaml` (línea 4) dice que `prepare` agrega el `runId` «en el PR de los digests». El `runId` cambia en cada verificación; los digests, no. Son PR distintos.
13. **`CODEOWNERS`: el plan pide los equipos `calidad` y `cumplimiento`; `main` tiene dos personas** (`.github/CODEOWNERS`, línea 9, con el comentario «Hasta que existan los equipos del banco»). Un equipo que no existe invalida el archivo. P-7.
14. **T1 no nombra el escaneo.** Dice «Firma Cosign, SBOM y attestations». Las tareas de despliegue fusionadas (U11-T03, U08-T05, U10-T05) difirieron también el escaneo con esa cita. Aquí se sigue el precedente.
15. **El encargo de esta tarea hablaba de «la regla de conftest que valida el formato del `runId`»: no existe.** Lo valida la plantilla de Helm. CA-3 usa `helm template`.
16. **El detector de verbos choca con sus propios entregables:** el contexto del parche de F22, la instalación de `kubectl` en el `Dockerfile`, y la orden de `promotion-tool`. Resuelto en la tabla de F-06.
17. **`demo-kind-alcance.md` §3 U12, fila 13, incluye `pii`;** la enmienda la saca. Rige la enmienda.
18. **NFR-U12-31 presupuesta «6 a 8 h»** con 5 corridas y carga. Con el recorte: D1 ≈ 25 min, D2 > 75 min, D4 ≈ 42 min más el día siguiente. El README da las cifras reales.
19. **`deployment-architecture.md` §2 y el Paso 17 hablan de tres Applications**; con el recorte es una, y `decision-registry-rebuild` no existe en `components.yaml`.

---

## Preguntas abiertas

**P-1, P-2, P-3, P-8 y P-12 necesitan al usuario antes de despachar.** Las demás no: si nadie responde, rige la recomendación y el codificador la anota en `cli.md`.

- **P-1 — ¿Se parte la tarea? (necesita al usuario).**
  - (a) **Recomendada.** Dos tareas por bloque: T04a (Pasos 12 y 13) y T04b (Pasos 14, 15 y 17). Es la partición original del plan (bloques E y F).
  - (b) Una sola, como dice la enmienda §4. Riesgo alto de pasar de 2 rondas.
- **P-2 — Cómo abre Grafana el presentador en D4 (necesita al usuario).**
  - (a) **Recomendada para la demo.** Por `port-forward` a su pod (K16 lo da en `vectra-observability`), con la cuenta `grafana-admin`. El guion dice que los permisos por rol no se enseñan.
  - (b) Una tarea corta de U1 que configure `root_url`, `serve_from_sub_path` y `generic_oauth`. No está medido que Grafana admita `private_key_jwt` con ES256 (`CANDIDATAS.md`, línea 47).
  - (c) Enseñar solo la lectura de `u11` y capturas. Pierde el dashboard en vivo.
- **P-3 — La línea 68 de `case-management/Makefile` (necesita al usuario: toca U8).**
  - (a) **Recomendada.** Cambiarla aquí para que solo mire staging, producción y los values del chart. Una línea; es lo que `conftest` ya dice.
  - (b) No tocarla: `make -C case-management check` queda en rojo mientras el `runId` esté en `main`. El README lo avisa.
  - (c) Que el operador revierta el PR del `runId` al terminar cada verificación. El Job se poda y la evidencia de D3 deja de poder repetirse.
- **P-4 — La sección `u11` y las evidencias de las demos.**
  - (a) **Recomendada.** `scenarios/u11.py`, y cada sección escribe además la evidencia de su demo, como en Precisiones.
  - (b) Un subcomando nuevo que registre la salida de `verify`. Cambia `guard.SECTIONS` y mete salida de shell en `evidence/`.
- **P-5 — Qué puede leer un `verify` y quién escribe en `evidence/`.**
  - (a) **Recomendada.** `verify` lee `kubectl` (K16), Prometheus por `port-forward` y los archivos ya escritos; no escribe. Un solo escritor, `store.py`.
  - (b) `verify` inicia sesión y llama al BFF. Tokens en un guion de shell.
- **P-6 — Los PR que dependen de `M1` y `M2`.**
  - (a) **Recomendada.** Plantillas con el hueco marcado y el fragmento YAML exacto; la prueba las rellena con un `model_version_id` de fixture y corre `helm template`.
  - (b) Que la CLI los genere. Más código y otra sección.
- **P-7 — `CODEOWNERS`.**
  - (a) **Recomendada.** No tocarlo: la línea existe con dos personas. La candidata de los equipos queda abierta.
  - (b) Escribir `@<org>/calidad` y `@<org>/cumplimiento`. GitHub marca el archivo como inválido si no existen.
- **P-8 — Descargas para construir la imagen (necesita al usuario).** La base de Python ya está en el Docker local. Hacen falta, por red: los paquetes de sistema de Chromium (`apt`), Chromium revisión 1248 para Linux (≈ 170 MB, estimación), el binario de `kubectl` v1.37 (≈ 55 MB, estimación) y el perfil `chrome.json`. `hadolint` y `shellcheck` no están en el PATH: el primero sale de `platform/install-tools.sh`; el segundo, de `uvx --from shellcheck-py`, como en `governance/Makefile`, línea 83.
  - (a) **Recomendada.** Autorizarlas, todas con versión y SHA-256 fijados.
  - (b) Sin red: la aceptación del Paso 15 no se puede cumplir.
- **P-9 — Camino a la bóveda y límite de memoria.**
  - (a) **Recomendada.** En kind el operador reenvía la bóveda con su kubeconfig de administrador y pasa `VAULT_ADDR=http://127.0.0.1:<puerto>`; el README dice que no es K16. `--memory 1g` como valor de partida, a medir en U12-T05.
  - (b) Ampliar K16 con `port-forward` en `vault`. Es de U1.
- **P-10 — Códigos de salida, `commit` y operador.**
  - (a) **Recomendada.** 0, 1, 2 y 3 como en Precisiones; `--commit` y `--operator` obligatorios en `prepare`.
  - (b) Instalar `git` en la imagen. Más superficie, y `subprocess` solo se permite en `k8s_read`.
- **P-11 — Usuarios del presentador.**
  - (a) **Recomendada.** D1: `analista-2` o `cro-2`; D2: `cumplimiento-2` para mirar. El operador lee sus semillas de la bóveda y las carga en el teléfono antes. El guion lo lista como prerrequisito. Si la bóveda no trae los «-2», se dice en la bitácora y se usa el «-1» fuera de las ventanas de la herramienta.
  - (b) Los mismos «-1». Choque de TOTP.
- **P-12 — Quién reactiva en D2 (necesita al usuario).**
  - (a) **Recomendada.** Una opción de `rt2`: por omisión reactiva la herramienta (sirve para ensayar); con `--reactivation presenter`, `rt2` **espera** la entrada `frozen_resolution` como espera los pasos del operador, y el presentador reactiva en la SPA. Amplía `scenarios/rt2.py` de U12-T03.
  - (b) Siempre la herramienta; el presentador solo enseña el paquete. No se ve el step-up en vivo.
  - (c) Siempre el presentador. Los ensayos sin presentador no producen RT-2.
- **P-13 — F-06.** (a) **Recomendada:** la tabla de Precisiones. (b) No tocar el detector y escribir los guiones esquivándolo: el parche de F22 y el `Dockerfile` no pasan.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, Bloques E y F, y los Pasos 18 y 19)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1 entero, §2, §3 U12, §5, §6, §8) y `demo-kind-alcance.md` (§1, §2, §3 U12, §6)
- `DECISIONES-LOOP.md` (§6, §9 y §10)
- `aidlc-docs/construction/system-verification/`: `business-rules.md` (BR-U12-06, 09 a 13), `business-logic-model.md` §2, `domain-entities.md` §3 y §4, `nfr-requirements.md`, `infrastructure-design.md` (INF-U12-01 a 04) y `deployment-architecture.md`
- `aidlc-docs/construction/system-verification/code/`: `logic.md`, `clients.md` y `scenarios.md`
- `tareas/U12-T03-escenarios-y-mediciones.md`, `U12-T02-clientes-simulador-y-conductor.md` y, para la imagen, `U11-T03-despliegue-y-cierre.md`
- `revisiones/U12-T01/ronda-2.md` (F-06) y `revisiones/U12-T02/ronda-1.md` (F-02 y F-04)
- Los archivos de «Lo que los guiones tocan de verdad»
- `governance/docs/paso-20-kind.md`, `model-serving/docs/paso-11-kind.md`, `model-serving/docs/values.md`, `reference-model/docs/release.md`
- Los «Pendiente en U12» de `aidlc-docs/construction/{case-management,console,product-metrics}/evidence/cierre-demo.md` y `platform-foundation/evidence/cierre-acotado.md`

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Ninguno usa un clúster. Ninguno admite pruebas omitidas ni `xfail`: sin Docker, la prueba **falla**. `H=platform/.tools/bin` (tras `bash platform/install-tools.sh`).

### Bloque E (Pasos 12 y 13)

- [ ] **CA-1** — Estructura y contratos de imports.
  ```bash
  uv sync --frozen && uv run lint-imports --config system-verification/.importlinter && cd system-verification && for p in src/vectra_verification/cli.py src/vectra_verification/manifest.py src/vectra_verification/store.py src/vectra_verification/scenarios/u11.py demos/journey-7-3.md demos/journey-7-4.md demos/rt-5.md demos/dashboard.md demos/verify/journey-7-3.sh demos/verify/journey-7-4.sh demos/verify/rt-5.sh demos/verify/dashboard.sh demos/prs/f22-apagado demos/prs/rt5-run-id demos/prs/rt3-staging demos/prs/proxy-staging demos/prs/promocion tests/integration/test_cli.py; do test -s "$p" || test -d "$p" || echo "FALTA $p"; done; test ! -e chart && test ! -e migrations && uv run vectra-verification --help >/dev/null && echo OK
  ```
  Esperado: todos los contratos `kept` (los de U12-T03 más los nuevos: `cli` es el único que importa a la vez `scenarios`, `driver` y `store`; `store` es el único de `src/` con escritura de archivos; `scenarios.u11` sin E/S directa); ninguna línea `FALTA`; `OK`. **Rojo primero:** un `import subprocess` en `cli.py` rompe su contrato; regístralo.

- [ ] **CA-2** — Mundo cerrado de los guiones (lección de la enmienda §8).
  ```bash
  uv run pytest system-verification/tests/unit/test_demos_closed_world.py -v
  ```
  Esperado: pasan. La prueba **recorre** `demos/` (guiones, `verify` y `prs`) y extrae cada nombre; ninguno está escrito a mano en la prueba como «permitido»:
  - cada **ruta de la SPA** está en `console/spa/src/views/shared/routes.ts` con `entry: true`, y el rol del usuario que el guion nombra está en sus `roles`;
  - cada **usuario** está en `realm.kind.yaml` con ese rol;
  - cada **namespace** está en `platform/network/flows.yaml` (`meshed_namespaces` o `system_namespaces`), y cada **Application**, en `vectra-risk-gitops/components.yaml`;
  - cada **alerta** y cada **serie** aparece, tal cual, en un archivo de reglas, de métricas o de dashboards del repositorio;
  - cada **dashboard** (título, uid, carpeta y panel) está en `product.json` u `operacion.json` y en `folder-permissions.yaml` o `kustomization.yaml`;
  - cada **archivo y clave de values** que un PR nombra existe, y cada **ruta de documento** citada existe;
  - cada **sección de la CLI** que un guion o un `verify` invoca es un subcomando real (se compara con el analizador de `cli.py`), con opciones que existen;
  - cada **paso** de la tabla de un guion nombra un `verify` y un número de paso que ese `verify` acepta;
  - los cuatro guiones traen su tiempo real (D1 «19,3», D2 «75», D3 «5 min», D4 «23:00 UTC» y «02:30 UTC»).

  **Rojo primero** (mutaciones sobre una copia de `demos/`, una prueba por cada una): `/fallos` en un guion; `/congelamientos/:freezeId` con `cro-1`; el usuario `analista-3`; el namespace `vectra-apps`; la alerta `CoreWriteAttempts`; la Application `decision-registry-rebuild`; el panel «North Star de hoy»; la sección `pii`; una opción de la CLI que no existe. Cada una debe fallar nombrando el archivo y la línea.

- [ ] **CA-3** — Los PR preparados se aplican limpios, dejan verdes las pruebas de su unidad y **se revierten**.
  ```bash
  git status --short | grep -v "^??" ; uv run pytest system-verification/tests/unit/test_prepared_prs.py -v && git status --short -- platform vectra-risk-gitops case-management model-serving; echo "limpio=$?"
  ```
  Esperado: código 0, y el último `git status` **vacío**: la prueba trabaja sobre una copia temporal dentro del worktree (`git worktree add` o una copia de los archivos tocados; nunca `/tmp`) y la borra. Pasan:
  - `f22-apagado/apagar.patch`: `git apply --check` sobre `origin/main`; aplicado, `uv run python platform/network/generate.py --check` da 0 (el parche trae lo regenerado) y `uv run pytest platform/network/tests -q` pasa; el diff de recursos es **exactamente** los 5 de la tabla; `staging` y `prod` no cambian ni un byte;
  - `f22-apagado/revertir.patch` deja el árbol idéntico a `origin/main`;
  - el parche de `prepare` (generado en la prueba con un `runId` de ejemplo): `git apply --check`; aplicado, `helm template` de `case-management` con los tres `valueFiles` de `apps/kind/case-management.yaml` rinde **un** `Job` `rt5-demo-<runId>`; `conftest` de `values.staging` y `values.prod` sigue verde; y la orden de la línea 68 del `Makefile` de U8 da el resultado que P-3 decida (con (a), 0);
  - `rt3-staging` y `proxy-staging`, rellenos con un `model_version_id` de fixture: `helm template ms model-serving/chart -f vectra-risk-gitops/envs/kind/values.yaml -f <values parchado>` da 0 y rinde `isvc-<8 hex>` en `vectra-staging`; con RT3-a y RT3-d a la vez, `helm` falla con «repetido» (el README del PR lo dice);
  - `promocion/README.md` nombra las cuatro órdenes tal como están en `vectra_promotion/cli.py`.

  **Rojo primero:** un `apagar.patch` sin los archivos regenerados hace fallar `generate.py --check`; uno con `enabled: false` en F22 cambia `staging` y `prod` y debe fallar. Regístralos.

- [ ] **CA-4** — Verbos de `kubectl` sobre `demos/`, `src/`, `README.md` y `Dockerfile`, con la decisión de F-06; y `shellcheck`.
  ```bash
  uv run pytest system-verification/tests/unit/test_kubectl_verbs.py -v && uvx --from shellcheck-py shellcheck system-verification/demos/verify/*.sh; echo "rc=$?"; ls system-verification/tests/fixtures/kubectl/allowed system-verification/tests/fixtures/kubectl/prohibited
  ```
  Esperado: `rc=0`. `test_real_files_have_no_findings` pasa con los archivos reales. Hay un fixture por cada fila de la tabla de F-06: en `allowed/`, la sustitución asignada con `get`, la ruta del binario en un `COPY` y un parche cuyo contexto nombra el namespace de Argo CD; en `prohibited/`, la sustitución asignada con `delete`, `K=kubectl`, `kubectl $V pods`, `nohup` y `watch` delante, `--context "$(ctx)"`, y un parche con una línea **añadida** `kubectl apply`. Todos los casos de U12-T01 siguen pasando sin cambios. **Rojo primero:** un `kubectl exec` en `verify/rt-5.sh` y la orden literal de sincronizar de Argo CD en `journey-7-3.md` hacen fallar la prueba; regístralo.

- [ ] **CA-5** — Cada orden de `verify/*.sh` cabe en K16.
  ```bash
  uv run pytest system-verification/tests/unit/test_demos_closed_world.py -v -k k16
  ```
  Esperado: pasan. La prueba lee `platform/rbac/verification-operator/k16.yaml` y, por cada orden de `kubectl` de cada `verify`, comprueba recurso, verbo y namespace (`logs` = `pods/log`; `port-forward` = `pods/portforward`, siempre a `pod/…`, nunca a `svc/…`). Cada `verify` corre contra el doble de `kubectl` de U12-T02 y un doble de Prometheus: estado esperado → 0; distinto → 1; el doble no responde → 2. **Rojo primero:** `kubectl get cronjobs -n vectra-app`, `kubectl get pods -n vectra-mock` y `port-forward svc/…` deben fallar cada uno con su motivo.

- [ ] **CA-6** — CLI: barreras, `--help` y códigos de salida (NFR-U12-03, 32).
  ```bash
  uv run pytest system-verification/tests/integration/test_cli.py -v -k "guard or help or exit"
  ```
  Esperado: pasan, cada uno comprobando **cero solicitudes** (HTTP, `kubectl` y bóveda) cuando la herramienta se niega:
  - emisor o host de producción → código 3; `rt5`, `rt3`, `rt2-setup` y `rt2` en staging → 3; `decisions` con 2 000 en staging → 3;
  - `decisions` a las 22:30 UTC (reloj falso) → 3; a una hora en que la estimación termina antes de las 23:00 → corre;
  - una reactivación fuera de `rt2` → `GuardError`;
  - `--help` general y de las 14 secciones → 0, sin archivos nuevos, sin red, y `playwright` y `pyarrow` no quedan en `sys.modules`;
  - las 6 secciones diferidas → código 2, cero solicitudes y su línea en el manifiesto con la cita;
  - una sección con `pasa` → 0; con `falla` → 1; con `no ejecutado` → 2; los tres textos son distintos.

  **Rojo primero:** llamar a `guard.check_section` después de abrir la sesión hace fallar «cero solicitudes»; regístralo.

- [ ] **CA-7** — La aceptación del Paso 13, literal.
  ```bash
  uv run pytest system-verification/tests/integration/test_cli.py -v
  ```
  Esperado: pasan, con las funciones de sección de U12-T03 sobre sus dobles:
  - interrumpir en `rt3` y retomar → las anteriores no se repiten (se cuentan las solicitudes);
  - manifiesto con todos los campos; > 50 MB → resumen y hash;
  - `decisions` sin `prepare` → se niega (código 3); `network` sin `prepare` → se niega igual, antes de decir «diferida»;
  - `prepare` con un manifiesto existente → se niega y `started_at` no cambia;
  - dos escenarios con la misma fila de U5 → el manifiesto la lista;
  - el informe muestra la duración por sección, con las esperas del operador aparte;
  - cada evidencia con oráculo de Prometheus incluye su consulta, con texto y ventana;
  - `prepare` → manifiesto con `runId` y `started_at`, y el parche con ese `runId`; `started_at = 2026-10-12T14:07:31Z` → `runId = 20261012-1407`.

  **Rojo primero:** reiniciar `started_at` en la retoma hace fallar el cuarto caso; regístralo.

- [ ] **CA-8** — `decisions`: espera a `listo`, volumen y `SIM-NORMAL`.
  ```bash
  uv run pytest system-verification/tests/integration/test_cli.py -v -k decisions
  ```
  Esperado: pasan: con un doble que deja los casos en `en_evaluacion` durante N sondeos, el conductor **no** empieza antes y decide todos (reloj falso, cero `sleep` reales); vencido el plazo, la sección informa cuántos quedaron sin decidir y no lo oculta; `SIM-NORMAL` se evalúa al final con el `RunReport`; el manifiesto registra enviados y decididos. **Rojo primero:** con el conductor de U12-T02 tal cual, los casos tardíos quedan sin decidir; regístralo (o registra que U12-T03 ya lo resolvió, con su prueba).

- [ ] **CA-9** — El filtro sobre **todo** lo que se escribe en `evidence/` (NFR-U12-05).
  ```bash
  uv run pytest system-verification/tests/unit/test_store.py system-verification/tests/unit/test_evidence_filter.py -v
  ```
  Esperado: pasan:
  - una prueba estática (AST) recorre `src/`: ninguna llamada a `open` en modo de escritura, `write_text`, `write_bytes`, `json.dump` a archivo ni `shutil` fuera de `store.py`;
  - una corrida completa con dobles, con los secretos de `Credentials.secret_values()` cargados: ningún archivo del directorio (evidencias, manifiesto, informe y parche) contiene un secreto;
  - por cada sección, un resultado al que la prueba inyecta un JWT → la escritura falla, el código es distinto de 0 y **no queda archivo** ni temporal;
  - el log del Job y el JSON de `kubectl` se escriben sin que el token `root` de kind los bloquee.

  **Rojo primero:** un `Path.write_text` directo en `manifest.py` hace fallar la prueba estática; regístralo.

- [ ] **CA-10** — El manifiesto (NFR-U12-10, 11, 20, 31).
  ```bash
  uv run pytest system-verification/tests/unit/test_manifest.py -v
  ```
  Esperado: pasan: cada campo de la lista de Precisiones; el SHA-256 de cada archivo coincide; un byte cambiado en una evidencia → su elemento sale `no ejecutado` en el informe; el manifiesto no contiene ningún nombre de campo de `ApplicationIn` (la prueba los toma de `vectra_contracts`) ni ningún valor de `secret_values()`; los digests vienen de la lectura del clúster de cada sección y `prepare` no deja ninguno.

- [ ] **CA-11** — `prepare` (INF-U12-02).
  ```bash
  uv run pytest system-verification/tests/integration/test_cli.py -v -k prepare
  ```
  Esperado: pasan: cero solicitudes (los dobles de `kubectl`, bóveda y gateway cuentan 0, y `prepare` corre **sin** `VAULT_ADDR` ni kubeconfig); el `runId` cumple `^[0-9]{8}-[0-9]{4}$`; el parche solo nombra `vectra-risk-gitops/values/kind/case-management.yaml` y solo añade la línea del `runId`; `probes.enabled` no cambia; en staging no hay parche. **Rojo primero:** un parche que también toca `values/kind/bias-monitoring.yaml` debe fallar.

- [ ] **CA-12** — La sección `u11` y la evidencia `dashboard` (BR-U12-06).
  ```bash
  uv run pytest system-verification/tests/unit/test_u11.py -v
  ```
  Esperado: pasan: las cuatro expresiones salen de `product.json` (la prueba compara con los paneles por su título); con valor y sin `ProductMetricsStale` → `pasa`; el mismo día UTC de `decisions` → `no ejecutado`; una serie ausente pasado el plazo → `falla` con su nombre; la alerta en `firing` → `falla`; Prometheus no responde → `no ejecutado`; la evidencia dice que `RuidoExplicacion` no se verifica en kind. **Rojo primero:** aceptar una serie vacía como `pasa`; regístralo.

- [ ] **CA-13** — El informe (BR-U12-11, 13; NFR-U12-21).
  ```bash
  uv run pytest system-verification/tests/integration/test_cli.py -v -k report
  ```
  Esperado: pasan, con una verificación de doble en la que todo lo que entra pasa:
  - encabezado con el límite del manifiesto; una fila por cada uno de los 26 elementos y por cada historia;
  - US-101, 111 y 303 `pasa`; US-304, 503, 504 y 505 `demostrada`; **US-603 y US-305 `no ejecutado`** (faltan `X01` y `X03`); US-106, 109, 604, 608, 609 y 610 `no ejecutado`;
  - la sección «No ejecutado y por qué» da un motivo a cada uno;
  - `RT2-LATENCY` dice «1 medición» y cita DD-1; las celdas inalcanzables aparecen;
  - sin `rt3` corrida, RT-3 y US-111 `no ejecutado`, nunca `pasa`; con `journey-7-3` ausente y RT-3 en `pasa`, US-111 `no ejecutado`.

- [ ] **CA-14** — Cada sección escribe la evidencia de su demo.
  ```bash
  uv run pytest system-verification/tests/integration/test_cli.py -v -k demo_evidence
  ```
  Esperado: pasan: `rt3` → `RT-3` y `journey-7-3`; `rt2` → `RT-2`, `RT2-LATENCY` y `journey-7-4`; `rt5` → `RT-5` y `rt-5`; `u11` → `dashboard`. `journey-7-3` es `no ejecutado` si no se esperó la escalada; `journey-7-4` es `falla` si no hubo `frozen_resolution` con MFA. Con P-12 (a): en modo `presenter` la herramienta no envía la reactivación y espera la entrada.

- [ ] **CA-15** — Reparación temporal del realm.
  ```bash
  grep -n "VERIFY_PROFILE" identity-edge/keycloak/realm/realm.kind.yaml; echo "u02t22=$?"; grep -n "repair_shared_authenticator_configs\|complete_user_profiles" system-verification/tests/doubles/keycloak_tc.py; echo "reparacion=$?"
  ```
  Esperado: **si `u02t22=0`** (U02-T22 está en `main` y el realm declara la acción), `reparacion=1` (las dos funciones y sus llamadas se quitaron) y `uv run pytest system-verification/tests/integration/test_oidc_headless.py -v` pasa sin ellas. **Si `u02t22=1`**, `reparacion=0`, nada cambia en ese archivo, y la bitácora y «Lo que T05 necesita» lo dicen.

### Bloque F (Pasos 14, 15 y 17)

- [ ] **CA-16** — Paso 14, N/A.
  ```bash
  test ! -d system-verification/chart && test ! -d system-verification/migrations && ! grep -n "system-verification" vectra-risk-gitops/components.yaml; echo "rc=$?"
  ```
  Esperado: `rc=0`. «La imagen no contiene manifiestos de Kubernetes» lo comprueba CA-17.

- [ ] **CA-17** — La imagen: `hadolint`, base por digest y contenido.
  ```bash
  $H/hadolint system-verification/Dockerfile && ! grep -nE "^FROM " system-verification/Dockerfile | grep -v "@sha256:" && ! grep -rnE "no-sandbox|ignore_https_errors|ignore-certificate-errors([^-]|$)|NODE_TLS_REJECT_UNAUTHORIZED" system-verification/Dockerfile system-verification/src && make -C system-verification image && uv run pytest system-verification/tests/image/test_image.py -v -k content
  ```
  Esperado: código 0. Dentro de la imagen: Python 3.12; `playwright` 1.64.0 y **solo** Chromium, revisión 1248; `kubectl` v1.37.x; `vectra_verification` y `vectra_contracts` instalados y **no** `vectra_common`; **no** existen los binarios de Argo CD, `helm`, `k6`, `git` ni `curl`; ningún archivo con `apiVersion:` y `kind:` (manifiestos); usuario por omisión 65532; ningún archivo con permisos de escritura para otros fuera de `/tmp`. **Rojo primero:** un `FROM` por etiqueta falla la segunda orden.

- [ ] **CA-18** — El contenedor real arranca (lección de CA-4 de U11-T03).
  ```bash
  uv run pytest system-verification/tests/image/test_image.py -v -k run
  ```
  Esperado: pasan, con `docker run --rm --read-only --tmpfs /tmp --user 12345:12345 --memory 1g` y el directorio de la verificación montado desde el worktree:
  - `--help` → 0, y el directorio montado sigue vacío;
  - `prepare` → 0: `manifest.json` y el parche aparecen en el directorio montado, con dueño 12345, y pasan el filtro;
  - `prepare` otra vez → 3;
  - sin el montaje de evidencias → error claro, no una traza;
  - `rt5` contra dobles (un `kubectl` de doble montado por delante en el `PATH` y un Prometheus de doble en un puerto libre) → escribe `RT-5` y `rt-5`; el `kubectl` real de la imagen responde a `version --client`;
  - el contenedor no deja ningún archivo fuera del montaje y del `tmpfs`.

  Registra la orden `docker run` exacta y la memoria del contenedor. **Rojo primero:** con `--user 12345` y `HOME` sin definir en el `tmpfs`, Playwright no arranca; regístralo.

- [ ] **CA-19** — Chromium con el sandbox activo (aceptación del Paso 15).
  ```bash
  uv run pytest system-verification/tests/image/test_image.py -v -k sandbox
  ```
  Esperado: pasan: con `--security-opt seccomp=system-verification/seccomp/chrome.json`, Chromium arranca sin interfaz, `chrome://sandbox` no informa errores y la línea de órdenes del proceso no trae `--no-sandbox`; **sin** el perfil, la sección que necesita login termina con un error claro y código 2, no colgada. `seccomp/chrome.json` lleva en un comentario del README su origen y su SHA-256.

- [ ] **CA-20** — La CA en los dos caminos TLS, y nada más (F-02 de U12-T02).
  ```bash
  uv run pytest system-verification/tests/image/test_image.py -v -k tls
  ```
  Esperado: pasan, con un servidor HTTPS de prueba cuyo certificado firma una CA generada en la prueba, y el formulario de login de U12-T02 corriendo **dentro del contenedor**:
  - con esa CA montada: la navegación (Node) y un subrecurso (Chromium) cargan;
  - con **otra** CA montada: fallan los dos, con `OidcError`;
  - sin CA: fallan los dos;
  - un certificado válido para otro nombre: fallan los dos;
  - el almacén de CA del sistema de la imagen no cambia entre corridas.

  **Rojo primero:** pasar solo `NODE_EXTRA_CA_CERTS` (sin la huella de Chromium) hace fallar el subrecurso; regístralo.

- [ ] **CA-21** — README (Paso 17).
  ```bash
  test -s system-verification/README.md && uv run pytest system-verification/tests/unit/test_demos_closed_world.py -v -k readme
  ```
  Esperado: pasan. El README tiene: las 8 secciones en orden y las 6 diferidas; la orden `docker run` con `--read-only`, `--tmpfs`, `--network host`, `--user`, `--security-opt seccomp=`, `--memory`, el kubeconfig y el certificado en solo lectura, y el token de la bóveda **como variable, no como archivo**; los tiempos reales de las cuatro demos; los prerrequisitos de Precisiones; «cómo leer el informe» con su límite; y la tabla «Qué saldrá `no ejecutado` y por qué». La prueba comprueba que cada opción de la orden existe en la CLI, que la orden es la misma que usa `test_image.py`, y que no aparece `k6` ni las Applications diferidas.

- [ ] **CA-22** — `CODEOWNERS`.
  ```bash
  grep -n "vectra-risk/system-verification/evidence/" ../.github/CODEOWNERS && git diff origin/main...HEAD --stat -- ../.github/CODEOWNERS
  ```
  Esperado: una línea, y el `--stat` vacío (P-7 (a)). El encabezado del informe nombra `CODEOWNERS` (CA-13).

- [ ] **CA-23** — Trazabilidad con la lista (Paso 17; `DECISIONES-LOOP.md` §6).
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; echo "rc=$?"; grep -n "^## Diferido por la demo" -A8 aidlc-docs/construction/system-verification/evidence/cierre-demo.md; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: `rc=0`. La lista trae INF-U12-05 (Paso 11) y solo identificadores sin código ni prueba, cada uno con su paso y su cita. INF-U12-04 y NFR-U12-31 quedan **trazados**, no en la lista. El segundo `--all` da, para las demás unidades, el mismo conjunto que en la base. `cli.md` trae la tabla BR-U12-01 a 13 → prueba, y las BR diferidas (05, 08, 08b y 12) dicen «diferida» con su cita.

- [ ] **CA-24** — Enlaces y frases prohibidas.
  ```bash
  uv run python platform/tests/test_links.py && uv run python contracts/tools/forbidden_phrases.py system-verification/README.md system-verification/demos/*.md
  ```
  Esperado: los dos en 0.

### Comunes

- [ ] **CA-25** — Cobertura al umbral del plan (NFR-U12-40).
  ```bash
  uv run pytest system-verification/tests --ignore=system-verification/tests/image --cov=vectra_verification --cov-branch --cov-fail-under=85 && uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100
  ```
  Esperado: los dos en 0. `cli`, `manifest` y `store` no bajan de 90 % de ramas cada uno. Sin `# pragma: no cover` nuevos.

- [ ] **CA-26** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso (12|13|14|15|17) " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; grep -nE "^- \[ \] .*\*\*Paso 16 " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: cinco líneas marcadas con `(U12-T04)` y sus notas; el 16 sin marcar, con su nota de diferido; el diff muestra solo esas seis casillas.

- [ ] **CA-27** — `check` de la unidad, con su tiempo, y sin contenedores huérfanos (RL-4).
  ```bash
  uptime; time make -C system-verification check; uptime; docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -iE "u12t04|keycloak|prometheus|postgres"; echo "restantes=$?"
  ```
  Esperado: código 0 y `restantes=1` (o solo los que ya estaban: lístalos antes). Referencia: ≈ 10 a 11 min en U12-T02 y menos de 15 esperados tras U12-T03. **Esta tarea añade** (estimación, sin medir): pruebas de la CLI y de `demos/`, menos de 1 min; construir la imagen, 5 a 8 min sin caché y ≈ 1 min con ella; `test-image`, 2 a 3 min. Total esperado: **≈ 20 min** con caché, hasta 30 sin ella y con carga. Por eso existe `check-fast`. Anota los tiempos reales y los `uptime`.

- [ ] **CA-28** — Lock y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/|CANDIDATAS\.md$|bitacoras/U12-T04\.md$|aidlc-docs/construction/system-verification/code/|aidlc-docs/construction/system-verification/evidence/cierre-demo\.md$|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$|case-management/Makefile$)"; echo "fuera=$?"; git diff origin/main...HEAD --stat -- vectra-risk/case-management/Makefile vectra-risk/uv.lock; ls system-verification/evidence
  ```
  Esperado: `uv lock --check` en 0; `fuera=1`; `case-management/Makefile` con 1 línea cambiada solo si P-3 = (a); `evidence/` solo con `.gitkeep`.

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_demos_closed_world.py` (CA-2, CA-5, CA-21) y `test_prepared_prs.py` (CA-3).
- `tests/unit/test_kubectl_verbs.py`, ampliada, con sus fixtures (CA-4).
- `tests/integration/test_cli.py` (CA-6 a CA-8, CA-11, CA-13, CA-14); `tests/unit/test_store.py`, `test_manifest.py` y `test_u11.py` (CA-9, CA-10, CA-12).
- `tests/image/test_image.py` (CA-17 a CA-20).
- **Rojo primero:** antes de cada arreglo, reproduce el fallo y regístralo en `bitacoras/U12-T04.md`; como mínimo los nombrados en CA-1 a CA-4, CA-6, CA-7, CA-9, CA-11, CA-12, CA-17, CA-18 y CA-20. Las mutaciones nombradas son un mínimo: el revisor traerá otras.
- **Lo que el revisor de U12 suele encontrar:** una barrera que mira solo la primera forma de un caso; una prueba que pasa con el oráculo vacío; una lista de «permitidos» escrita a mano que deja de comprobar nada. Para la prueba de mundo cerrado: si se borra la fuente (por ejemplo, una ruta de `routes.ts`), el guion debe fallar.

---

## Restricciones del entorno

Las de U12-T02 y U12-T03, más las de la imagen:

- **No copies el repositorio a `/tmp`.** Es un tmpfs con cuota. Temporales dentro del worktree, en una carpeta sin versionar (`platform/.tools/tmp/u12t04/`): `TMPDIR`, la copia de trabajo de CA-3, el directorio de verificación de las pruebas y el contexto de Docker.
- **Máquina compartida y muy cargada.** Al redactar: `load average: 11.95, 15.42, 15.07` y ≈ 4 GiB disponibles de 14. Anota `uptime` con cada medida. **Las esperas usan el reloj inyectado, nunca `sleep` real.** Una prueba que falla por tiempo se repite en frío antes de darla por rota. No corras `make -C platform check` ni las suites de otras unidades: de ellas, solo las órdenes de CA-3.
- **Docker es compartido** con kind (`vectra-control-plane`, `vectra-worker`, `vectra-worker2`, `kind-registry` en `127.0.0.1:5001`) y con otros codificadores. Contenedores con el prefijo `u12t04-`, puertos al azar, `--memory` siempre. **Bórralos al terminar**, también tras una corrida interrumpida. Nada de `docker system prune`. **No publiques la imagen** en `kind-registry`.
- **Las pruebas de la imagen usan `--network host`** solo si el doble lo exige; aun así, puertos libres pedidos al sistema. Nunca 443, 8080, 8081, 8443, 8200 ni 9090.
- **Sin clúster.** Hay un kubeconfig que funciona: **no lo uses**. Ninguna prueba ejecuta el `kubectl` del host ni llama a `vectra.localtest.me`. El `kubectl` de la imagen solo corre `version --client`.
- **Descargas:** solo las de P-8, con versión y SHA-256. Las imágenes de Keycloak, config-cli, PostgreSQL y Prometheus ya están.
- **Navegadores del host:** `make test` sigue usando `~/.cache/ms-playwright` (revisión 1248). No los borres ni reinstales; nada de `sudo`. La imagen instala los suyos en la construcción.
- **No toques el árbol principal ni otros worktrees.** No uses `git stash` sin etiqueta.
- **Otros codificadores en paralelo:** U02-T22 (`identity-edge/`) y U00-T04 (`contracts/`). Esta tarea no toca ninguno de los dos. Si otra tarea toca `uv.lock`, el orquestador fusiona `origin/main`.

---

## Notas

- **Orden sugerido:** (1) leer `scenarios.md` y verificar «Lo que los guiones tocan de verdad»; (2) prueba de concepto de la imagen: Chromium con sandbox, uid arbitrario y solo lectura, **antes** de escribir nada más (es lo de más riesgo); (3) `store`, `manifest` y `prepare`; (4) `cli` con sus barreras y la retoma; (5) `u11` y las evidencias de demo; (6) el detector y F-06; (7) los PR preparados y su prueba; (8) los guiones y `verify`, con la prueba de mundo cerrado; (9) `Dockerfile`, README, trazabilidad, plan y bitácora.
- Archivos que se **modifican en su sitio**: `cli.py`, `manifest.py`, `Makefile`, `.importlinter`, `pyproject.toml` de la unidad, `test_kubectl_verbs.py`, `scenarios/rt2.py` (solo con P-12 (a)), `driver.py` o la sección `decisions` (CA-8), el plan y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`.
- **Enlaces:** `test_links.py` lee como enlace un corchete cerrado seguido de un paréntesis. Cuidado con los patrones de `grep` en los guiones, el README y la bitácora.
- **Candidatas nuevas** que esta tarea deja, si no están ya: «Contradicciones» 1 a 5, 8 a 10, 12, 13 y 19; la línea 68 del `Makefile` de U8 si P-3 no es (a); las semillas de los usuarios «-2»; y lo que encuentres al verificar las tablas.
- **Bitácora** `bitacoras/U12-T04.md`: la salida real de cada comando; la verificación de las tablas («igual» o corregida); los pares falla-pasa; la decisión de P-1 a P-13; las versiones y SHA-256 de lo descargado; el digest local de la imagen; el tiempo de cada `make check` con sus `uptime`; los contenedores antes y después. **Ningún secreto.**

### Lo que T05 necesita de esta tarea

U12-T05 (Pasos 18 y 19) es la verificación consolidada (enmienda §8). Recibe la CLI, la imagen, los guiones con sus `verify` y los PR preparados. **Lo que solo se puede comprobar en kind**, reunido de los cierres y de las candidatas:

- **Antes de nada**
  - U02-T22 en `main` y el realm reimportado; la reparación de `keycloak_tc.py` retirada si no lo hizo esta tarea; desbloquear a los usuarios que hayan fallado un login.
  - U00-T04 en `main`: sin la `aud` corregida ningún servicio obtiene token y ninguna demo arranca.
  - Publicar las imágenes de U3 a U11 y fijar los digests reales (hoy, de ejemplo: `ImagePullBackOff`); crear `values/kind/product-metrics.yaml`; construir en un mismo commit las de governance, scoring y casos.
  - Retirar el eco de U2 y la `ServiceAccount` temporal `console-bff` de U4 antes del sync de U10.
  - Política activa, modelo de referencia `activo`, y los paquetes proxy y RT-3 en el model-store.
  - Publicar la imagen de U12 y correrla por digest; medir su memoria en el host.
- **Acceso del operador**
  - El camino a la bóveda (P-9) y la lectura de las 5 credenciales y las 2 llaves; las semillas del presentador (P-11).
  - K16 de verdad: que cada `verify` funcione con el grupo `vectra-verification-operators`, y qué pasa en `vectra-staging`.
  - Los selectores y puertos de Prometheus y del registro; el certificado raíz exportado; el login por el gateway real, con el emisor público y los `redirect_uri` reales.
  - `CASE_ALLOW_TEST_SCENARIOS` activo y los límites del gateway (`auth-login`, `auth-token`, `console`) con 2 000 casos.
- **U1:** la suite de conectividad; `Watchdog` recibido; el target `linkerd-proxy` de `vectra-mock` en `up == 1`; la serie `inbound_http_authz_deny_total` con `namespace` y `route_name` reales.
- **U8:** el Job `rt5-demo-<runId>` con el `runId` de `prepare`; `CoreWriteAttempt` en `firing` y cuánto dura; el valor real de `l5d-proxy-error`; las dos llaves por ESO; `sslmode=verify-full`; `vectra_cases_failclosed_persistent` raspado; memoria con 2 000 decisiones; el apagado del worker.
- **U10:** login, `/callback` y recarga con `prompt=none`; la CSP real; el step-up de `cumplimiento-1` y `ResolveFrozenDialog`; F03, F10, F11 y F14; el `iss` en cada destino; la cookie de afinidad; memoria del BFF.
- **U11:** las métricas del día D + 1; la `PrometheusRule` cargada y el `ConfigMap` del dashboard descubierto en `Vectra / Producto`; la llave por ESO; memoria con 2 000 decisiones; y **el orden de arranque** (dashboard vacío hasta 30 min).
- **U2:** los tokens reales (`acr`, `amr`, `aud`), y Grafana según P-2.
- **Las cuatro demos, ensayadas con reloj:** D1 (qué `last_cause` da F22 apagado; los 19,3 min; que la reversión devuelva el flujo a `listo`; los casos `no_disponible` que quedan); D2 (que U3 no dé 504 al cron; las métricas de bias por el Pushgateway; más de 75 min; el rollback); D3 (la ventana de 5 min de la alerta; la retención de 3 días); D4 (lanzar `decisions` antes de las 22:18 UTC; leer tras las 02:40 UTC; el día 1 del mes).
- **Medir y corregir:** las constantes de `guard` (1 s por caso, 300 s); los plazos por omisión de cada espera; el `--memory` de la imagen.
- **Cierre:** el resto de `evidence/cierre-demo.md` (esta tarea deja solo «Diferido por la demo»), `make -C system-verification check` y el PR de verificación.
