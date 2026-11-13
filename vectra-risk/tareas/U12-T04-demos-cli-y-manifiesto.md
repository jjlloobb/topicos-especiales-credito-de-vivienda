# U12-T04 — Guiones de las cuatro demos, CLI por secciones y manifiesto de `system-verification`

**Unidad:** U12 `system-verification`
**Historias que implementa:** ninguna propia. La trazabilidad del plan (§3) nombra el Paso 12 en US-111, 303, 305 y 603 y en las demos de US-304, 503, 504 y 505. Aquí se escriben los guiones y la herramienta que el operador ejecuta. La imagen y el README son de U12-T05. Las corre el operador en kind (Paso 18, U12-T06).
**Depende de:**
- **U12-T03 fusionada en `main`** (PR #___, commit de fusión `_______`: **por completar al fusionar**). Su contrato es `tareas/U12-T03-escenarios-y-mediciones.md`, sección «Lo que T04 y T06 necesitan de esta tarea». **Al empezar, lee `aidlc-docs/construction/system-verification/code/scenarios.md`**: las firmas reales rigen sobre lo que esta tarea supone. Lo que se da por sentado:
  - una función por sección (`rt5`, `rt3`, `rt2-setup`, `rt2`) y la de `SIM-NORMAL`, con parámetros (`runId`, `started_at`, versiones del proxy, prefijos del model-store, semillas, plazos);
  - el resultado de tres valores (`scenarios/outcome.py`), su conversión a `report.Evidence` (ninguna si es `no ejecutado`) y el motivo de cada `no ejecutado`;
  - las fases de `rt2` y `rt3` como puntos de retoma, y las consultas guardadas (`QueryResult`);
  - RT-3 con la decisión P-2 (a) del usuario: obligatorios RT3-a, c, d y F22.
- **U12-T02** (PR #___, **por completar**; leída en `.claude/worktrees/u12-t02`, `639a22f`): `clock.Clock`; `clients/` (`oidc`, `bff`, `registry`, `prom`, `loki`, `k8s_read`); `simulator`; `driver` con `run_decisions(...)` y `DEMO_VOLUME = 2000`; `guard.SECTIONS` con las 14 secciones y `STAGING_SECTIONS = ("prepare", "decisions", "u11", "report")` (`guard.py`, líneas 43 a 46); `guard.check_job_patch` (línea 95) y `check_reactivation` (línea 102); `evidence.prepare(text, secrets)` (línea 182); `.importlinter` con 6 contratos; `Makefile` con `check: lint types imports test`.
- **U12-T01** (en `main`): `report.build` y `report.render`, `report.MANIFEST_LIMIT` (`report.py`, línea 48), `ELEMENT_IDS` con las cuatro demos (`journey-7-3`, `journey-7-4`, `rt-5`, `dashboard`; línea 29), `report/story-map.yaml`, `tests/unit/test_kubectl_verbs.py` (`scan_tree` recorre `src/`, `demos/`, `Makefile`, `README.md` y `Dockerfile`). `manifest.py` y `cli.py` existen vacíos.
- **U01-T09** ya está en `main` (`8dc7499`): monitor del proxy de Linkerd solo en `vectra-mock`.
- **No depende** de U02-T22 ni de U00-T04 (en curso). Ver «Reparación temporal del realm».

Es código, guiones y pruebas **sin clúster** (RL-5). No construye ninguna imagen.
**Rama:** `tarea/U12-T04`, desde `origin/main` **después** de fusionar U12-T03.

Bloque E del plan de U12 (`aidlc-docs/construction/plans/system-verification-code-generation-plan.md`, Pasos 12 y 13). La enmienda (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §4, fila U12) juntaba «E+F (12, 13, 15, 17)» en una tarea. **El usuario la partió en dos el 2026-11-13** (P-1), por los bloques del plan, para que cada una quepa en 2 rondas. U12 queda en **6 tareas**: T01 A+B (1–4) · T02 C (5–6) · T03 D (8, 10) · **T04 E (12, 13)** · T05 F (14 N/A, 15, 17) · T06 G+H (18–19). Esta es la cuarta. La enmienda rige sobre el alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 12 Demos | **E** | Entra completo | Enmienda §3 U12, fila «12 Demos: E, E, Los cuatro guiones, `verify/*.sh` y los PR preparados (F22 con `env_disabled.kind`, P-19)» |
| 13 CLI, manifiesto y `CODEOWNERS` | **E\*F** | Entran 8 secciones. Se difieren 6 secciones, dos de los tres values del parche y la prueba de `CODEOWNERS` | Enmienda §3 U12, fila «13 CLI: E\*, E\*F, Secciones `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report` (sale `pii`). El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`). Se difiere la prueba de `CODEOWNERS` con `branch-protection-check`, porque depende de U4 Paso 14, que está en D» |
| 14 N/A · 15 Imagen · 17 Documentación | — | **No son de esta tarea:** U12-T05 (`tareas/U12-T05-imagen-y-documentacion.md`) | Decisión del usuario, 2026-11-13 (P-1) |
| 16 Workflow de CI | **D** | No entra | Enmienda §3 U12, fila «16: D, D»; alcance: T4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6. No hay PBT nuevas; PBT-U12-01 a 04 siguen verdes.

**Decisiones del usuario que rigen** (`DECISIONES-LOOP.md` §9 y §10):
- **RT-3 en la demo:** pasa con RT3-a, c y d (422) más F22. RT3-b y «a y d desplegados» se calculan y se informan; solo bajan el resultado si dan `falla`.
- **RT-2:** se niega solo por celdas **alcanzables**; D2 usa **1** versión del proxy (DD-1).
- **Del 2026-11-13, sobre esta tarea** (detalle en «Preguntas»): la tarea se parte en dos (P-1); Grafana en D4 por `port-forward` con `grafana-admin` (P-2); se corrige la línea 68 de `case-management/Makefile` (P-3); la reactivación de D2 es una opción de la herramienta (P-12).
- **Emisor:** solo el público (`https://vectra.localtest.me/auth/realms/vectra`). La aserción de servicio lleva `aud` = emisor; U00-T04 (en curso) lo corrige en `vectra_common`, que U12 no usa.
- **Realm:** U02-T22 (en curso) corrige los alias y desactiva `VERIFY_PROFILE`.
- **Memoria de kind:** requests de 128 MiB solo en kind para U8, U10 y U11; `BUDGET_GIB = 11.8` (`platform/tests/test_kind_profile.py`, línea 34), con todo menos U12.
- **U03-T07 aparcada:** U3 puede dar 504 al cron de U9 bajo carga. Riesgo aceptado para D2: el guion lo dice.

**Lección que esta tarea aplica** (enmienda §8): un guion que nombra un recurso, una ruta, un usuario o un comando que no existe solo se descubre delante del público. Por eso cada nombre de un guion, de un `verify` y de un PR preparado está en «Lo que los guiones tocan de verdad», con ruta y línea, y una prueba lo comprueba recorriendo `demos/` (CA-2).

---

## Alcance

**Dentro:** los Pasos 12 y 13 del plan. Texto del plan, sin recortes salvo lo que el recorte difiere, que va ~~tachado~~ con su cita y en «Fuera»:

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

### Estructura de destino (§1 del plan): lo que esta tarea crea o llena

```text
vectra-risk/system-verification/
|-- Makefile  .importlinter  pyproject.toml          # se modifican (objetivos `shellcheck` y `links`; punto de entrada `vectra-verification`)
|-- src/vectra_verification/
|   |-- cli.py  manifest.py                          # Paso 13 (hoy vacios)
|   |-- store.py                                     # nuevo, no esta en §1 (P-5): el UNICO escritor de `evidence/`, con el filtro
|   |-- scenarios/u11.py                             # nuevo, no esta en §1 (P-4): la seccion `u11` y la evidencia `dashboard`
|   `-- scenarios/rt2.py                             # se amplia: el modo de reactivacion (P-12)
|-- demos/
|   |-- journey-7-3.md  journey-7-4.md  rt-5.md  dashboard.md
|   |-- verify/   journey-7-3.sh  journey-7-4.sh  rt-5.sh  dashboard.sh  (y `lib.sh` si hay codigo comun)
|   `-- prs/      f22-apagado/  rt5-run-id/  rt3-staging/  proxy-staging/  promocion/     # un directorio por PR preparado
|-- evidence/                                        # sigue vacio (solo `.gitkeep`): lo llena el operador en U12-T06
`-- tests/
    |-- unit/         test_demos_closed_world.py  test_prepared_prs.py  test_store.py  test_manifest.py  test_u11.py
    `-- integration/  test_cli.py

vectra-risk/aidlc-docs/construction/system-verification/code/cli.md                  # nuevo
```

`test_cli.py` es el nombre de la aceptación del plan: es fijo. Los demás son una propuesta; lo que cambies va a la bitácora. Los criterios filtran con `-k`.

**No** se crean: `Dockerfile`, `README.md`, `seccomp/`, `tests/image/` ni `evidence/cierre-demo.md` (U12-T05); `scenarios/rt1.py`, `rt4.py`, `x_network.py`, `x_behavior.py`, `logs_pii.py`, `case_size.py` ni nada en `load/` (diferidos); `chart/` ni `migrations/`; `.github/workflows/system-verification.yml` (Paso 16).

### Cambios permitidos fuera de `system-verification/`

Uno por uno. Cualquier otro archivo fuera del directorio es un hallazgo.

1. `aidlc-docs/construction/plans/system-verification-code-generation-plan.md`: solo las casillas de los Pasos 12 y 13 (CA-19).
2. `aidlc-docs/construction/system-verification/code/cli.md`: nuevo. Si cambias una firma de T02 o T03, también `clients.md` o `scenarios.md` (la ampliación de `rt2` va en `scenarios.md`).
3. **`case-management/Makefile`, una línea: la 68, objetivo `policy-chart`** (P-3, autorizado por el usuario el 2026-11-13). Hoy: `! grep -rn "runId" vectra-risk-gitops/values/*/case-management.yaml case-management/chart/values.yaml case-management/chart/values-kind.yaml`. Debe quedar prohibiendo `runId` en `values/staging/case-management.yaml`, en `values/prod/case-management.yaml` y en los dos values del chart, y **no** en `values/kind/case-management.yaml`, que es donde `prepare` lo pone. Ninguna otra línea del `Makefile`, ninguna regla de `conftest` y ninguna prueba de U8 cambian. Prueba: CA-3.
4. `.github/CODEOWNERS` (en la raíz del repositorio): **no cambia** (P-7). La línea `vectra-risk/system-verification/evidence/ @jjlloobb @joseluisjedi` ya existe (línea 9). El punto «`CODEOWNERS` del monorepo» del Paso 13 se cumple comprobándola (CA-13 y CA-21).
5. `system-verification/tests/doubles/keycloak_tc.py`: es de la unidad; va aquí por la condición de «Reparación temporal del realm».
6. `CANDIDATAS.md` y `bitacoras/U12-T04.md` (nuevo).
7. `uv.lock` y `pyproject.toml` raíz: no deberían cambiar (un punto de entrada no cambia el lock). Si cambian, la bitácora dice por qué.

`platform/`, `vectra-risk-gitops/`, `model-serving/`, `governance/`, `console/`, `product-metrics/`, `identity-edge/` y `contracts/` **se leen, no se editan**. De `case-management/` solo esa línea. Los PR preparados son archivos de `demos/prs/`: **los abre el operador**, no esta tarea. Las pruebas los aplican en una copia de trabajo temporal y los revierten (CA-3).

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

- **Los digests no son un PR preparado.** Ningún archivo de `vectra-risk-gitops/values/kind/` trae hoy una clave de digest, `values/kind/product-metrics.yaml` no existe, y todos los charts llevan el digest de ejemplo (`sha256:00…`): los pods quedarían en `ImagePullBackOff`. Es un prerrequisito de instalación del operador (U12-T06), con el `docs/imagenes.md` de cada unidad. El README lo lista; no va en `demos/prs/`.
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
| **Grafana por el gateway** | La ruta `/grafana` existe, pero Grafana **no** tiene `root_url`, `serve_from_sub_path` ni OIDC | `platform/observability/values/kube-prometheus-stack.yaml` (sin `grafana.ini`); `CANDIDATAS.md`, línea 82. **Decidido (P-2, usuario, 2026-11-13):** el presentador entra por `port-forward` al pod de Grafana con `grafana-admin`; los permisos por carpeta y rol no se enseñan |

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
- **Códigos de salida** (P-10, rige la recomendación): `0` = la sección terminó y todo lo suyo es `pasa`; `1` = algún `falla`; `2` = `no ejecutado` (faltó un prerrequisito, o es una sección diferida); `3` = la herramienta se negó (barrera, uso, `prepare` ausente o repetido). `falla` y `no ejecutado` nunca comparten código ni texto.
- **`--help`** (general y de cada sección): código 0, sin red, sin leer la bóveda, sin escribir archivos y **sin importar** `playwright` ni `pyarrow`.
- **Retoma:** el manifiesto guarda, por sección, `started_at`, `finished_at` y estado. Una sección terminada no se repite salvo con `--redo`. Una sección interrumpida se retoma en la fase que U12-T03 expone. `--from <sección>` corre desde ahí en orden. **Ninguna** sección espera a un PR dentro de otra: las esperas del operador se registran aparte (NFR-U12-31).
- **Todo lo que va a `evidence/` pasa por un solo escritor** (`store.py`): llama a `evidence.prepare` con `Credentials.secret_values()` antes de escribir, escribe en un temporal y renombra. Si el filtro falla, **no queda archivo**. Una prueba estática comprueba que ningún otro módulo de `src/` abre un archivo para escribir (CA-9).
- **`decisions`:** `run_decisions` de U12-T02 y, al final, `SIM-NORMAL` de U12-T03 con el `RunReport`. **El conductor debe esperar a `listo`** (F-04 de `revisiones/U12-T02/ronda-1.md`, destino U12-T03): la tarea de U12-T03 **no lo recoge** (comprobado: no nombra `not_ready` ni el conductor). Si al crear la rama sigue sin resolver, entra aquí: la sección sondea con el reloj inyectado hasta que no quede ningún caso del `RunReport` en `en_evaluacion`, o hasta un plazo, **antes** de lanzar el conductor (CA-8). Si U12-T03 ya lo resolvió, se comprueba y no se duplica.
- **`u11`** (hueco del plan: ningún paso define su oráculo; P-4, rige la recomendación). Produce la evidencia `dashboard`. Con `PromClient`:
  - se niega con `no ejecutado` (`u11_antes_de_d_mas_1`) si el día UTC actual no es posterior al día UTC en que terminó `decisions` (del manifiesto);
  - lee **las mismas expresiones que los paneles** de `product.json`: «North Star de ayer» (`vectra:product_north_star_ratio:dedup{period="day", channel="all", outcome="all", model_version_id="all"}`), «Recomendaciones sostenidas», «Tasa de consulta» y «Días bajo el piso». La prueba las **toma del archivo**, no las copia;
  - `pasa` si las cuatro tienen valor y `ALERTS{alertname="ProductMetricsStale", alertstate="firing"}` no tiene puntos; una serie ausente es `falla` con su nombre, salvo antes de las 02:40 UTC del día D + 1 más el plazo de la pasada, que es `no ejecutado`;
  - **no** verifica `RuidoExplicacion` (BR-U12-06: se verifica con `promtool`, no en kind). La evidencia lo dice.
- **Evidencias de las cuatro demos** (hueco del plan; P-4). `report.ELEMENT_IDS` trae `journey-7-3`, `journey-7-4`, `rt-5` y `dashboard`, y el mapa las exige (US-111, 303, 305, 603, 304, 503 a 505), pero ningún paso dice quién las escribe. Aquí: **las escribe la sección de cada demo**, con el escritor único: `rt3` → `RT-3` y `journey-7-3` (F22 más la escalada a `no_disponible` y `FailClosedPersistente`, con `wait_for_escalation`); `rt2` → `RT-2`, `RT2-LATENCY` y `journey-7-4` (el paquete y la resolución con MFA); `rt5` → `RT-5` y `rt-5`; `u11` → `dashboard`. Los `verify/*.sh` **no escriben evidencias**: imprimen.
- **`report`:** `verification-report.md` con `report.render`: encabezado con `MANIFEST_LIMIT`; una fila por elemento y por historia, con su estado; duración por sección y total, con las esperas del operador aparte; y una sección «No ejecutado y por qué», con el motivo de cada uno (diferido por la demo, prerrequisito, K16). Se puede generar en cualquier momento.

**Paso 13 — `prepare`** (INF-U12-02)

- Genera el `runId` (`AAAAMMDD-HHMM` de `started_at` en UTC, truncado al minuto), escribe el manifiesto inicial y el parche. **No hace ninguna solicitud**: ni clúster, ni bóveda, ni gateway. Recibe por parámetro el directorio de la verificación, el `commit` y el operador (la imagen de U12-T05 no trae `git`; P-10).
- **El parche** es un diff unificado que `git apply` acepta sobre `main`: agrega `runId: "<runId>"` bajo `probes:` en `vectra-risk-gitops/values/kind/case-management.yaml`, **entre comillas** (sin ellas YAML lo leería como texto igual, pero un `runId` solo de dígitos no). No toca `bias-monitoring` ni `decision-registry-rebuild`, ni ningún archivo de staging o producción. Se escribe en el directorio de la verificación.
- Se niega si ya hay `manifest.json` (y `started_at` no cambia). En staging no produce parche.

**Paso 13 — manifiesto**

- `manifest.json`: SHA-256 por archivo; `started_at`; `runId` y el nombre esperado `rt5-demo-<runId>`; semillas; `generator_version`; tamaño de `test`; solicitudes repetidas entre escenarios; `commit`; operador; por sección, inicio, fin y estado; y los digests **leídos del clúster** al empezar cada sección que lo toca (`imageID` de los pods de los namespaces de K16), no en `prepare`.
- **No lleva** secretos ni datos del solicitante: ningún token, contraseña, semilla, llave ni campo de `ApplicationIn`; solo `case_id`, conteos y posiciones de fila (CA-10).
- Tope de 50 MB: lo que lo supere se sustituye por un resumen y el hash del original.

**Reactivación de D2: una opción de la herramienta** (P-12, decisión del usuario, 2026-11-13)

- La sección `rt2` gana la opción `--reactivation {tool,presenter}`. Vive en la CLI; `scenarios/rt2.py` de U12-T03 recibe el modo por parámetro. **U12-T03 no lo prevé** (su fase 9 siempre reactiva con la herramienta): la ampliación es un encargo de **esta** tarea, sin reescribir U12-T03 ni cambiar sus oráculos («Contradicciones» 4).
- **`tool` (por omisión):** como en U12-T03: step-up de `cumplimiento-1` y `resolve_frozen(…, section="rt2")`. Sirve para ensayar sin presentador.
- **`presenter`:** la herramienta **no** inicia sesión con ningún usuario de cumplimiento y **no** envía la reactivación. Espera, con el reloj inyectado y un plazo por parámetro, a que el presentador la haga en la consola con **`cumplimiento-2`** (`/congelamientos/:freezeId`, `ResolveFrozenDialog`, step-up). Después **verifica** lo mismo que en el otro modo: la entrada `frozen_resolution` con `action = "reactivar"` en `monitoring_freezes`, la versión `activo`, y sigue con «no se recongela» y el barrido. Vencido el plazo: `no ejecutado`, retomable.
- El MFA del presentador no lo ve la herramienta: lo exige el BFF (`contracts/openapi/role-endpoint-matrix.md`: `frozen-resolution` solo `cumplimiento` con MFA). La evidencia `journey-7-4` dice qué modo se usó y, en `presenter`, que el step-up lo impuso el BFF.
- `cumplimiento-2` existe en el realm (`realm.kind.yaml`, línea 780). **`credentials.USERS` no lo trae** (línea 26) y la herramienta no lo necesita. Que su contraseña y su semilla estén en la bóveda de kind y lleguen al teléfono del presentador es un prerrequisito del guion (P-11) y un punto de U12-T06.
- `guard.check_reactivation` no cambia: la herramienta solo reactiva dentro de `rt2`, y en modo `presenter` no reactiva.

**Paso 12 — guiones y `verify`** (BR-U12-09)

- **Cada guion** (`demos/<demo>.md`) tiene: prerrequisitos; tiempo real (la tabla de arriba); una tabla numerada de pasos con **quién** (presentador u operador), **qué hace**, **qué se ve y dónde** (ruta de la SPA, panel, texto) y **qué `verify` lo comprueba**; qué deja sucio y cómo se limpia; y qué saldrá `no ejecutado`. Los pasos son los de la enmienda §1.1 a §1.4, **con las correcciones de «Contradicciones»**.
- **Cada `verify/<demo>.sh <paso>`:** comprueba el estado esperado tras ese paso y sale con 0 (como se esperaba), 1 (no) o 2 (no se pudo leer). Solo usa: `kubectl` con `get`, `logs`, `auth can-i` y `port-forward`, sobre lo que K16 da; la API de lectura de Prometheus por `127.0.0.1` tras un `port-forward` a un pod; y los archivos que la sección ya escribió en el directorio de la verificación. **No** inicia sesión, no lee la bóveda, no escribe en `evidence/` (P-5). Lleva `--context` literal o `"${KUBE_CONTEXT:-kind-vectra}"`.
- **Palabras que el detector de verbos rechaza en `demos/`, `README.md` y `Dockerfile`** (`test_kubectl_verbs.py`, líneas 143 a 158): el nombre del binario de Argo CD seguido de cualquier texto (también como nombre de namespace), y el de `kubectl` seguido de una palabra que no sea un verbo permitido. Los guiones dicen «sincroniza la Application `network` en Argo CD, con prune» y no escriben la orden. La orden de `promotion-tool` con su `--diff-command` (que contiene un `diff` de `kubectl`) **no se copia**: se remite a `governance/docs/paso-20-kind.md`.
- **D1 (`journey-7-3.md`):** el presentador mira `/casos` con un usuario que la herramienta no esté usando en ese momento (`analista-2` o `cro-2`; P-11). **No** abre `/fallos`: está diferida (P-16 de la enmienda sigue pendiente). «Escala como incidente técnico» se enseña con `FailClosedPersistente`. El paso `rt3-staging` va marcado **opcional**: K16 no llega a `vectra-staging`, así que su resultado es `no ejecutado` (decisión del usuario), y RT3-a y RT3-d van uno a la vez. Los casos `no_disponible` y la alerta **siguen activos** en D2 y D4: el guion lo dice.
- **D2 (`journey-7-4.md`):** orden real: `proxy-staging` → `rt2-setup` → promoción (4 órdenes de `promotion-tool`, por referencia) → `rt2`. El paquete se enseña en `/congelamientos/:freezeId` con `cumplimiento`. **Dos modos de reactivación, los dos documentados en el guion** (P-12, usuario, 2026-11-13; ver «Reactivación de D2»). Avisa del riesgo de U03-T07 (504 al cron) y de que `/sesgo` no se abre.
- **D3 (`rt-5.md`):** PR `rt5-run-id` → sync → Job → `rt5`. **La alerta se enseña en los 5 min siguientes al Job**; después, con la evidencia de `rt5` (`query_range`).
- **D4 (`dashboard.md`):** día D y día D + 1 con las horas de la tabla; el aviso del arranque de `product-metrics` (dashboard vacío hasta 30 min si arrancó antes que el registro); el aviso del día 1 del mes (falta `month_to_date`); y **el acceso a Grafana (P-2, usuario, 2026-11-13): por `port-forward` a su pod en `vectra-observability`, con la cuenta `grafana-admin`**. El guion dice, con esas palabras, que los permisos por carpeta y rol **no se enseñan** en la demo (Grafana no tiene OIDC: candidata abierta de U1).

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

**Reparación temporal del realm** (`DECISIONES-LOOP.md` §10; `tareas/U02-T22…`, línea 263)

`tests/doubles/keycloak_tc.py` repara el realm por la API de administración (`repair_shared_authenticator_configs`, línea 225; `complete_user_profiles`, línea 268; se llaman en las líneas 432 y 435). **Mientras existan, esconden el defecto.** Decisión: **la retirada entra en esta tarea si, al crear la rama, U02-T22 está en `main`** (CA-15 lo comprueba con una orden). Si no está, no se toca, y queda como primera línea de «Lo que U12-T06 necesita» (en `tareas/U12-T05-imagen-y-documentacion.md`): U12-T06 no puede dar por bueno el login de kind con la reparación puesta.

**Plan.** Marca `[x]` con `(U12-T04)` los Pasos 12 y 13. En el 13, la nota «8 secciones; parche solo de `case-management`; prueba de `CODEOWNERS` diferida». Los Pasos 14, 15 y 17 no se tocan (U12-T05). El 16 sigue en `[ ]`.

**Fuera** (recházalo aunque lo veas roto o tentador):

- **Secciones `network`, `rt1`, `rt4`, `load`, `pii` y `resilience`**, más allá del subcomando que responde `no ejecutado`. Enmienda §3 U12, fila «13»: «Secciones `prepare`, `decisions`, `rt5`, `rt3`, `rt2-setup`, `rt2`, `u11` y `report` (sale `pii`)».
- **`bias-monitoring` y `decision-registry-rebuild` en el parche de `prepare`**, y los Jobs `x04-probe` y `x06-probe`. Misma fila: «El parche de `prepare` solo toca `case-management` (sin `bias-monitoring` ni `decision-registry-rebuild`)».
- **La prueba de `CODEOWNERS` con `branch-protection-check`.** Misma fila: «Se difiere la prueba de `CODEOWNERS` con `branch-protection-check`, porque depende de U4 Paso 14, que está en D».
- **Pasos 14, 15 y 17:** el `Dockerfile`, la imagen, `seccomp/`, el `README.md`, la lista «Diferido por la demo» y el cierre de la trazabilidad. Son de U12-T05 (P-1).
- **Paso 16** (workflow de CI) y `mutmut`. T4 y T3.
- **Abrir, fusionar o sincronizar un PR; ejecutar una sección contra kind.** Es de U12-T06 y del operador.
- **Editar otras unidades:** no se configura el OIDC de Grafana, no se amplía K16, no se cambia `flows.yaml`, no se escribe un digest en `values/kind/`, no se agrega `cumplimiento-2` a la bóveda. La única excepción es la línea 68 de `case-management/Makefile` (P-3).
- **Reescribir los oráculos de U12-T03.** De `scenarios/rt2.py` solo el modo de reactivación.
- **Pasos 18 y 19.**
- **Cualquier llamada a un clúster.** El kind de la máquina puede estar arriba: no se usa.

---

## Candidatas (`CANDIDATAS.md`)

Números de línea de `main` (`8dc7499`); las de la rama `tarea/U12-T02` se citan por su hallazgo.

**Se atienden aquí:**

| Dónde | Candidata | Qué se hace |
|---|---|---|
| Línea 649 (F-06 de U12-T01) | El detector de verbos rechaza formas legítimas | La tabla de «detector de verbos y F-06» (CA-4) |
| Rama T02, F-04 de la ronda 1 | El conductor no espera a `listo` (destino U12-T03, que **no** la recoge) | `decisions` espera antes del conductor (CA-8), si sigue abierta |
| Línea 641 | El informe marcará `no ejecutado` varias historias | El informe lo dice, con el motivo (CA-13). El README, en U12-T05 |
| Línea 639 | Nadie comprueba el ≥ 85 % (Paso 16 diferido) | Ya está en `make test` desde U12-T02; se conserva (CA-16) |
| Línea 615 | `probes.enabled` distingue kind | `prepare` solo agrega `runId`; no toca `enabled` (CA-11) |
| Rama T02 (`test_kubectl_verbs.py`) | `-n <namespace>` va después del verbo en las listas de Python | Se anota en `cli.md`; el detector no cambia en eso |
| `tareas/U02-T22…`, línea 263 | Retirar la reparación del realm | Condicionada (CA-15) |
| Línea 82 | Grafana sin `root_url` ni OIDC | Solo el guion de D4, por `port-forward` (P-2). **La candidata sigue abierta**: el arreglo es de U1 |

**Para U12-T05:** rama T02, F-02 de la ronda 1 (la CA para Node y Chromium en la imagen).

**Para U12-T06** (no las atiendas; la lista completa está en «Lo que U12-T06 necesita» de `tareas/U12-T05-imagen-y-documentacion.md`): líneas 640, 684, 598, 619, 679, 631, 659, 675, 689, 634, 402 y 412, y las de la rama T02 sobre selectores, puertos y hosts de la bóveda.

**Se quedan:** líneas 207 (marcadores de `LOGS-NO-PII`, diferido), 636, 638 y 642 (textos del diseño), 650 a 652 (generadores y evasiones con intención), 252 (AUC del proxy), 40, 47 y 48 (OIDC de Grafana, U1).

---

## Contradicciones entre plan, recorte, diseño y `main`

Vistas al redactar. **Las que romperían una demo delante del público, primero.** Deja en `CANDIDATAS.md` las que no estén ya. Las de la imagen y el README están en U12-T05.

1. **D4: el presentador no puede abrir Grafana por el gateway.** La enmienda §1.4 dice «El presentador abre Grafana `product.json`». La ruta `/grafana` existe y el realm trae el cliente `grafana` (`realm.kind.yaml`, línea 1008), pero los values de Grafana no tienen `grafana.ini`: ni `root_url`, ni `serve_from_sub_path`, ni `generic_oauth` (`CANDIDATAS.md`, líneas 40, 47 y 82, abiertas). **Resuelta para la demo (P-2):** `port-forward` con `grafana-admin`; los permisos por carpeta y rol no se enseñan.
2. **D3: el PR de `runId` dejaba en rojo `make -C case-management check`.** `case-management/Makefile`, línea 68: el comodín `values/*/` incluye `kind`. La regla de `conftest` solo prohíbe `runId` en staging y producción. **Resuelta (P-3):** se corrige esa línea aquí.
3. **D3: la alerta `CoreWriteAttempt` dura unos 5 min.** No tiene `for:` y su expresión compara con `offset 5m`. El guion lo fija; después de esa ventana se enseña la evidencia de `rt5`.
4. **D2: ¿quién reactiva?** La enmienda §1.2 pone la resolución en la SPA (el presentador); el plan (Paso 8) y U12-T03 (fase 9 de `rt2`) hacen que la reactive **la herramienta**. **Resuelta (P-12):** los dos modos. **U12-T03 no prevé el modo `presenter`:** su función siempre envía la reactivación. Añadirlo es un encargo de esta tarea, en la CLI y en `scenarios/rt2.py`, sin tocar sus oráculos.
5. **D1 y D2: el presentador necesita contraseña y TOTP.** Todo login de la consola pide TOTP. Las semillas están en la bóveda (`identity/synthetic-users`), y `credentials.USERS` solo trae los cinco «-1». Ningún documento dice cómo llegan al teléfono del presentador. No está comprobado que la bóveda de kind traiga las de los «-2» (P-11): lo dice el guion como prerrequisito y lo comprueba U12-T06.
6. **D1: `/fallos` está diferida.** «Escala como incidente técnico» no se puede enseñar con `PersistentFailures` (`routes.ts`, línea 44: `entry: false`); P-16 de la enmienda sigue pendiente. Se enseña la alerta.
7. **D1: RT3-a y RT3-d «desplegados» no caben a la vez** (mismo nombre `isvc-<8 hex de M1>` en `vectra-staging`), y K16 no lee ese namespace. Van uno a la vez, opcionales, y su resultado es `no ejecutado`.
8. **D1: F22 apagado quita 5 recursos, no 4.** La enmienda §1.1 dice «2 NetworkPolicy, `MeshTLSAuthentication` y `AuthorizationPolicy`»; también cae el `Server` `explainer-8080`. Qué `last_cause` resulta se ve en kind.
9. **El plan no define la sección `u11` ni quién escribe las cuatro evidencias de demo.** Sin ellas, US-111, 303, 304, 503, 504 y 505 saldrían `no ejecutado` aunque todo pase. P-4.
10. **Los digests no pueden ser un PR preparado**, y el comentario de `values/kind/case-management.yaml` (línea 4) dice que `prepare` agrega el `runId` «en el PR de los digests». El `runId` cambia en cada verificación; los digests, no. Son PR distintos.
11. **`CODEOWNERS`: el plan pide los equipos `calidad` y `cumplimiento`; `main` tiene dos personas** (`.github/CODEOWNERS`, línea 9). Un equipo que no existe invalida el archivo. P-7.
12. **No existe una regla de `conftest` que valide el formato del `runId`.** Lo valida la plantilla de Helm. CA-3 usa `helm template`.
13. **El detector de verbos choca con sus propios entregables:** el contexto del parche de F22 y la orden de `promotion-tool`. Resuelto en la tabla de F-06 (que deja lista también la forma que U12-T05 necesita en el `Dockerfile`).
14. **`demo-kind-alcance.md` §3 U12, fila 13, incluye `pii`;** la enmienda la saca. Rige la enmienda.
15. **`deployment-architecture.md` §2 habla de tres Applications**; con el recorte es una, y `decision-registry-rebuild` no existe en `components.yaml`.
16. **K16 no da camino a la bóveda** (`CANDIDATAS.md`, línea 640). No afecta a las pruebas de esta tarea (doble de bóveda); lo resuelve el README de U12-T05 (P-9).

---

## Preguntas

**Todas resueltas. No queda ninguna que necesite al usuario.** La numeración es la de la versión única de esta tarea (PR #165).

- **P-1 — ¿Se parte la tarea?** **Decidido por el usuario (2026-11-13): sí.** U12-T04 = Bloque E; U12-T05 = Bloque F; la verificación en kind pasa a U12-T06.
- **P-2 — Grafana en D4.** **Decidido por el usuario (2026-11-13):** por `port-forward` a su pod, con `grafana-admin`. El guion dice que los permisos por carpeta y rol no se enseñan. La candidata de U1 sigue abierta.
- **P-3 — La línea 68 de `case-management/Makefile`.** **Autorizado por el usuario (2026-11-13):** se cambia aquí; la prohibición de `runId` cubre staging y producción, no kind. Con su prueba (CA-3).
- **P-12 — Quién reactiva en D2.** **Decidido por el usuario (2026-11-13):** opción de la herramienta. Por omisión, la herramienta con `cumplimiento-1`; con `--reactivation presenter`, espera al presentador (`cumplimiento-2`) y verifica.
- **P-4 — La sección `u11` y las evidencias de las demos.** Rige la recomendación: `scenarios/u11.py`, y cada sección escribe además la evidencia de su demo.
- **P-5 — Qué lee un `verify` y quién escribe en `evidence/`.** Rige la recomendación: `verify` lee `kubectl` (K16), Prometheus por `port-forward` y los archivos ya escritos; no escribe. Un solo escritor, `store.py`.
- **P-6 — Los PR que dependen de `M1` y `M2`.** Rige la recomendación: plantillas con el hueco marcado; la prueba las rellena con un `model_version_id` de fixture y corre `helm template`.
- **P-7 — `CODEOWNERS`.** Rige la recomendación: no tocarlo.
- **P-10 — Códigos de salida, `commit` y operador.** Rige la recomendación: 0, 1, 2 y 3; `--commit` y `--operator` obligatorios en `prepare`.
- **P-11 — Usuarios del presentador.** Rige la recomendación: D1 con `analista-2` o `cro-2`; D2 con `cumplimiento-2`. El guion lo lista como prerrequisito, con sus semillas.
- **P-13 — F-06.** Rige la recomendación: la tabla de Precisiones.
- P-8 y P-9 son de U12-T05.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/system-verification-code-generation-plan.md` (§1, Bloque E, y el Paso 18)
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` (§1 entero, §2, §3 U12, §5, §6, §8) y `demo-kind-alcance.md` (§1, §2, §3 U12, §6)
- `DECISIONES-LOOP.md` (§6, §9 y §10)
- `aidlc-docs/construction/system-verification/`: `business-rules.md` (BR-U12-06, 09 a 13), `business-logic-model.md` §2, `domain-entities.md` §3 y §4, `nfr-requirements.md`, `infrastructure-design.md` (INF-U12-01 a 04) y `deployment-architecture.md`
- `aidlc-docs/construction/system-verification/code/`: `logic.md`, `clients.md` y `scenarios.md`
- `tareas/U12-T03-escenarios-y-mediciones.md`, `U12-T02-clientes-simulador-y-conductor.md` y `U12-T05-imagen-y-documentacion.md` (lo que recibe de esta)
- `revisiones/U12-T01/ronda-2.md` (F-06) y `revisiones/U12-T02/ronda-1.md` (F-02 y F-04)
- Los archivos de «Lo que los guiones tocan de verdad»
- `governance/docs/paso-20-kind.md`, `model-serving/docs/paso-11-kind.md`, `model-serving/docs/values.md`, `reference-model/docs/release.md`
- Los «Pendiente en U12» de `aidlc-docs/construction/{case-management,console,product-metrics}/evidence/cierre-demo.md` y `platform-foundation/evidence/cierre-acotado.md`

---

---

## Criterios de aceptación

Todos se corren desde `vectra-risk/`. Ninguno usa un clúster. Ninguno admite pruebas omitidas ni `xfail`: sin Docker, la prueba **falla**.

### Bloque E (Pasos 12 y 13)

- [ ] **CA-1** — Estructura y contratos de imports.
  ```bash
  uv sync --frozen && uv run lint-imports --config system-verification/.importlinter && cd system-verification && for p in src/vectra_verification/cli.py src/vectra_verification/manifest.py src/vectra_verification/store.py src/vectra_verification/scenarios/u11.py demos/journey-7-3.md demos/journey-7-4.md demos/rt-5.md demos/dashboard.md demos/verify/journey-7-3.sh demos/verify/journey-7-4.sh demos/verify/rt-5.sh demos/verify/dashboard.sh demos/prs/f22-apagado demos/prs/rt5-run-id demos/prs/rt3-staging demos/prs/proxy-staging demos/prs/promocion tests/integration/test_cli.py; do test -s "$p" || test -d "$p" || echo "FALTA $p"; done; test ! -e chart && test ! -e migrations && test ! -e Dockerfile && test ! -e README.md && uv run vectra-verification --help >/dev/null && echo OK
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
  - `dashboard.md` nombra el `port-forward` a Grafana, la cuenta `grafana-admin` y la frase de que los permisos por carpeta y rol no se enseñan; `journey-7-4.md` documenta los dos modos de reactivación, con `cumplimiento-1` y `cumplimiento-2`;
  - los cuatro guiones traen su tiempo real (D1 «19,3», D2 «75», D3 «5 min», D4 «23:00 UTC» y «02:30 UTC»).

  **Rojo primero** (mutaciones sobre una copia de `demos/`, una prueba por cada una): `/fallos` en un guion; `/congelamientos/:freezeId` con `cro-1`; el usuario `analista-3`; el namespace `vectra-apps`; la alerta `CoreWriteAttempts`; la Application `decision-registry-rebuild`; el panel «North Star de hoy»; la sección `pii`; una opción de la CLI que no existe. Cada una debe fallar nombrando el archivo y la línea.

- [ ] **CA-3** — Los PR preparados se aplican limpios, dejan verdes las pruebas de su unidad y **se revierten**.
  ```bash
  git status --short | grep -v "^??" ; uv run pytest system-verification/tests/unit/test_prepared_prs.py -v && git status --short -- platform vectra-risk-gitops case-management model-serving; echo "limpio=$?"
  ```
  Esperado: código 0, y el último `git status` **vacío**: la prueba trabaja sobre una copia temporal dentro del worktree (`git worktree add` o una copia de los archivos tocados; nunca `/tmp`) y la borra. Pasan:
  - `f22-apagado/apagar.patch`: `git apply --check` sobre `origin/main`; aplicado, `uv run python platform/network/generate.py --check` da 0 (el parche trae lo regenerado) y `uv run pytest platform/network/tests -q` pasa; el diff de recursos es **exactamente** los 5 de la tabla; `staging` y `prod` no cambian ni un byte;
  - `f22-apagado/revertir.patch` deja el árbol idéntico a `origin/main`;
  - el parche de `prepare` (generado en la prueba con un `runId` de ejemplo): `git apply --check`; aplicado, `helm template` de `case-management` con los tres `valueFiles` de `apps/kind/case-management.yaml` rinde **un** `Job` `rt5-demo-<runId>`; `conftest` de `values.staging` y `values.prod` sigue verde; y, con el parche aplicado y la línea 68 del `Makefile` de U8 ya corregida (P-3), `make -C case-management policy-chart` termina en 0 (es el objetivo entero: anota su tiempo);
  - la comprobación de esa línea **sigue en rojo** si el `runId` aparece en `vectra-risk-gitops/values/staging/case-management.yaml`, en `values/prod/case-management.yaml`, en `case-management/chart/values.yaml` o en `values-kind.yaml`: cuatro casos, sobre la copia temporal;
  - `rt3-staging` y `proxy-staging`, rellenos con un `model_version_id` de fixture: `helm template ms model-serving/chart -f vectra-risk-gitops/envs/kind/values.yaml -f <values parchado>` da 0 y rinde `isvc-<8 hex>` en `vectra-staging`; con RT3-a y RT3-d a la vez, `helm` falla con «repetido» (el README del PR lo dice);
  - `promocion/README.md` nombra las cuatro órdenes tal como están en `vectra_promotion/cli.py`.

  **Rojo primero:** un `apagar.patch` sin los archivos regenerados hace fallar `generate.py --check`; uno con `enabled: false` en F22 cambia `staging` y `prod` y debe fallar. Y con la línea 68 **sin corregir** y el parche aplicado, `policy-chart` falla en esa línea: es el rojo de P-3. Regístralos.

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
  Esperado: pasan: `rt3` → `RT-3` y `journey-7-3`; `rt2` → `RT-2`, `RT2-LATENCY` y `journey-7-4`; `rt5` → `RT-5` y `rt-5`; `u11` → `dashboard`. `journey-7-3` es `no ejecutado` si no se esperó la escalada; `journey-7-4` es `falla` si no hubo `frozen_resolution` con MFA. Los dos modos de «Reactivación de D2»:
  - por omisión (`tool`): la herramienta hace el step-up de `cumplimiento-1` y envía la reactivación (una solicitud, con token de step-up);
  - `--reactivation presenter`: la herramienta **no** inicia sesión con ningún usuario de cumplimiento ni envía la reactivación (0 solicitudes a `frozen-resolution`); sondea con el reloj falso hasta ver la entrada `frozen_resolution` con `action = "reactivar"` y la versión `activo`, y sigue con «no se recongela»;
  - en modo `presenter`, sin la entrada al vencer el plazo → `no ejecutado` con el código del paso pendiente, y la sección se retoma en esa fase; una entrada con `action = "investigar"` → `falla`;
  - la evidencia `journey-7-4` dice qué modo se usó;
  - fuera de `rt2`, la opción no existe (`rt3 --reactivation …` → código 3).

  **Rojo primero:** en modo `presenter`, enviar igualmente la reactivación hace fallar «0 solicitudes»; regístralo.

- [ ] **CA-15** — Reparación temporal del realm.
  ```bash
  grep -n "VERIFY_PROFILE" identity-edge/keycloak/realm/realm.kind.yaml; echo "u02t22=$?"; grep -n "repair_shared_authenticator_configs\|complete_user_profiles" system-verification/tests/doubles/keycloak_tc.py; echo "reparacion=$?"
  ```
  Esperado: **si `u02t22=0`** (U02-T22 está en `main` y el realm declara la acción), `reparacion=1` (las dos funciones y sus llamadas se quitaron) y `uv run pytest system-verification/tests/integration/test_oidc_headless.py -v` pasa sin ellas. **Si `u02t22=1`**, `reparacion=0`, nada cambia en ese archivo, y la bitácora lo dice: la retirada pasa a U12-T06 (está en «Lo que U12-T06 necesita» de `tareas/U12-T05-imagen-y-documentacion.md`).

### Comunes

- [ ] **CA-16** — Cobertura al umbral del plan (NFR-U12-40).
  ```bash
  uv run pytest system-verification/tests --cov=vectra_verification --cov-branch --cov-fail-under=85 && uv run pytest system-verification/tests/unit system-verification/tests/property --cov=vectra_verification.report --cov=vectra_verification.sampler --cov-branch --cov-fail-under=100
  ```
  Esperado: los dos en 0. `cli`, `manifest` y `store` no bajan de 90 % de ramas cada uno. Sin `# pragma: no cover` nuevos.

- [ ] **CA-17** — Trazabilidad (`DECISIONES-LOOP.md` §6, regla «sin fallos nuevos»). El cierre con la lista es de U12-T05.
  ```bash
  uv run python platform/tests/test_traceability.py --unit system-verification --all; uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: el primero puede salir con código 1, y entonces su **única** línea es INF-U12-05 (Paso 11, diferido; U12-T05 lo pone en la lista). **INF-U12-04 y NFR-U12-31 quedan trazados aquí** (Paso 13). El segundo da, para las demás unidades, el mismo conjunto que en la base. `cli.md` trae la tabla BR-U12-09, 10, 11 y 13 → prueba.

- [ ] **CA-18** — Enlaces y frases prohibidas.
  ```bash
  uv run python platform/tests/test_links.py && uv run python contracts/tools/forbidden_phrases.py system-verification/demos/*.md
  ```
  Esperado: los dos en 0.

- [ ] **CA-19** — Plan.
  ```bash
  grep -nE "^- \[x\] \*\*Paso (12|13) " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; grep -nE "^- \[ \] .*\*\*Paso (14|15|16|17) " aidlc-docs/construction/plans/system-verification-code-generation-plan.md; git diff origin/main...HEAD -- aidlc-docs/construction/plans/system-verification-code-generation-plan.md | grep -E "^[-+]- \["
  ```
  Esperado: los Pasos 12 y 13 marcados con `(U12-T04)` y la nota del 13; los Pasos 14 a 17 sin marcar; el diff muestra solo esas dos casillas.

- [ ] **CA-20** — `check` de la unidad, con su tiempo (RL-4).
  ```bash
  uptime; time make -C system-verification check; uptime; docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -iE "keycloak|prometheus|postgres"; echo "restantes=$?"
  ```
  Esperado: código 0, con `check: lint types imports test shellcheck links`, y `restantes=1` (o solo los que ya estaban: lístalos antes). Referencia: ≈ 10 a 11 min en U12-T02 y menos de 15 esperados tras U12-T03. Esta tarea añade menos de 2 min (estimación, sin medir: pruebas de la CLI y de `demos/`, y los `helm template` de CA-3). El `make -C case-management policy-chart` de CA-3 **no** entra en `check`: se corre una vez y se anota. Anota los tiempos y los `uptime`.

- [ ] **CA-21** — Lock, `CODEOWNERS` y alcance del diff.
  ```bash
  uv lock --check && git diff --name-only origin/main...HEAD | grep -vE "^vectra-risk/(system-verification/|CANDIDATAS\.md$|bitacoras/U12-T04\.md$|aidlc-docs/construction/system-verification/code/|aidlc-docs/construction/plans/system-verification-code-generation-plan\.md$|case-management/Makefile$)"; echo "fuera=$?"; git diff origin/main...HEAD --stat -- vectra-risk/case-management/Makefile vectra-risk/uv.lock .github/CODEOWNERS; grep -n "vectra-risk/system-verification/evidence/" ../.github/CODEOWNERS; ls system-verification/evidence; test ! -e system-verification/Dockerfile && test ! -e system-verification/README.md && echo "sin imagen ni README"
  ```
  Esperado: `uv lock --check` en 0; `fuera=1`; `case-management/Makefile` con **1** línea cambiada; `uv.lock` y `CODEOWNERS` sin cambios; la línea de `CODEOWNERS` presente; `evidence/` solo con `.gitkeep`; «sin imagen ni README».

---

## Plan de pruebas

Se escriben **en esta tarea**:

- `tests/unit/test_demos_closed_world.py` (CA-2, CA-5) y `test_prepared_prs.py` (CA-3).
- `tests/unit/test_kubectl_verbs.py`, ampliada, con sus fixtures (CA-4).
- `tests/integration/test_cli.py` (CA-6 a CA-8, CA-11, CA-13, CA-14); `tests/unit/test_store.py`, `test_manifest.py` y `test_u11.py` (CA-9, CA-10, CA-12).
- **Rojo primero:** antes de cada arreglo, reproduce el fallo y regístralo en `bitacoras/U12-T04.md`; como mínimo los nombrados en CA-1 a CA-4, CA-6, CA-7, CA-9, CA-11, CA-12 y CA-14. Las mutaciones nombradas son un mínimo: el revisor traerá otras.
- **Lo que el revisor de U12 suele encontrar:** una barrera que mira solo la primera forma de un caso; una prueba que pasa con el oráculo vacío; una lista de «permitidos» escrita a mano que deja de comprobar nada. Para la prueba de mundo cerrado: si se borra la fuente (por ejemplo, una ruta de `routes.ts`), el guion debe fallar.

---

## Restricciones del entorno

Las de U12-T02 y U12-T03:

- **No copies el repositorio a `/tmp`.** Es un tmpfs con cuota. Temporales dentro del worktree, en una carpeta sin versionar (`platform/.tools/tmp/u12t04/`): `TMPDIR`, la copia de trabajo de CA-3, y el directorio de verificación de las pruebas.
- **Máquina compartida y muy cargada.** Al redactar: `load average: 11.95, 15.42, 15.07` y ≈ 4 GiB disponibles de 14. Anota `uptime` con cada medida. **Las esperas usan el reloj inyectado, nunca `sleep` real.** Una prueba que falla por tiempo se repite en frío antes de darla por rota. No corras `make -C platform check` ni las suites de otras unidades: de ellas, solo las órdenes de CA-3.
- **Docker es compartido** con kind (`vectra-control-plane`, `vectra-worker`, `vectra-worker2`, `kind-registry` en `127.0.0.1:5001`) y con otros codificadores. Esta tarea no construye imágenes; los contenedores son los de Testcontainers de U12-T02 y U12-T03, con nombres y puertos al azar. **Bórralos al terminar**, también tras una corrida interrumpida. Nada de `docker system prune`.
- **Puertos:** libres, pedidos al sistema. Nunca 443, 8080, 8081, 8443, 8200 ni 9090.
- **Sin clúster.** Hay un kubeconfig que funciona: **no lo uses**. Ninguna prueba ejecuta el `kubectl` del host ni llama a `vectra.localtest.me`.
- **Descargas:** ninguna (las de la imagen son de U12-T05). Las imágenes de Keycloak, config-cli, PostgreSQL y Prometheus ya están.
- **Navegadores del host:** `make test` sigue usando `~/.cache/ms-playwright` (revisión 1248). No los borres ni reinstales; nada de `sudo`.
- **No toques el árbol principal ni otros worktrees.** No uses `git stash` sin etiqueta.
- **Otros codificadores en paralelo:** U02-T22 (`identity-edge/`) y U00-T04 (`contracts/`). Esta tarea no toca ninguno de los dos. Si otra tarea toca `uv.lock`, el orquestador fusiona `origin/main`.

---

---

## Notas

- **Orden sugerido:** (1) leer `scenarios.md` y verificar «Lo que los guiones tocan de verdad»; (2) `store`, `manifest` y `prepare`; (3) `cli` con sus barreras y la retoma; (4) el modo de reactivación de `rt2`; (5) `u11` y las evidencias de demo; (6) el detector y F-06; (7) los PR preparados, la línea 68 y su prueba; (8) los guiones y `verify`, con la prueba de mundo cerrado; (9) `cli.md`, plan y bitácora.
- Archivos que se **modifican en su sitio**: `cli.py`, `manifest.py`, `Makefile`, `.importlinter`, `pyproject.toml` de la unidad, `test_kubectl_verbs.py`, `scenarios/rt2.py` (solo el modo de reactivación), `driver.py` o la sección `decisions` (CA-8), `case-management/Makefile` (línea 68), el plan y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- **`Makefile`:** `check: lint types imports test shellcheck links`. `image`, `test-image`, `traceability` y `check-fast` los agrega U12-T05.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `system-verification/`.
- **Enlaces:** `test_links.py` lee como enlace un corchete cerrado seguido de un paréntesis. Cuidado con los patrones de `grep` en los guiones y la bitácora.
- **Candidatas nuevas** que esta tarea deja, si no están ya: «Contradicciones» 3, 5, 8, 10, 11 y 15; las semillas de los usuarios «-2» en la bóveda de kind; y lo que encuentres al verificar las tablas.
- **Bitácora** `bitacoras/U12-T04.md`: la salida real de cada comando; la verificación de las tablas («igual» o corregida); los pares falla-pasa; el tiempo de cada `make check` con sus `uptime`; los contenedores antes y después. **Ningún secreto.**

### Lo que U12-T05 y U12-T06 necesitan de esta tarea

- **U12-T05 (Pasos 14, 15 y 17):**
  - el punto de entrada `vectra-verification`, con `--help` sin efectos y `prepare` sin solicitudes: son lo que la imagen arranca;
  - `cli.md` con las opciones, los códigos de salida, los tiempos de cada demo y la tabla de lo que saldrá `no ejecutado`: de ahí sale el README;
  - el detector de verbos ya ampliado (la ruta del binario en el `Dockerfile`; la prosa del README), y `test_demos_closed_world.py`, que U12-T05 amplía al README;
  - `ca_file` de U12-T02 expuesto como opción de la CLI;
  - lo que queda sin trazar: INF-U12-05, para la lista.
- **U12-T06 (Pasos 18 y 19):** la lista completa está en «Lo que U12-T06 necesita» de `tareas/U12-T05-imagen-y-documentacion.md`. Esta tarea añade:
  - la retirada de la reparación del realm, si CA-15 la dejó pendiente;
  - que el PR de `runId` fusionado deje `make -C case-management policy-chart` en verde sobre `main`;
  - el modo `--reactivation presenter` ensayado de verdad con `cumplimiento-2`, y sus credenciales en la bóveda de kind;
  - Grafana por `port-forward` con `grafana-admin` (dónde está esa credencial y que el dashboard «Producto» cargue);
  - que los cinco recursos de F22 desaparezcan con el sync con prune y vuelvan con la reversión.
