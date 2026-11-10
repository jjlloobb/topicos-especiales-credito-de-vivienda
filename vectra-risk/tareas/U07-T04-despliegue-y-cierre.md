# U07-T04 — Imágenes, chart, Application, trazabilidad y cierre acotado de `scoring-explainability`

**Unidad:** U7 `scoring-explainability`
**Historias que implementa:** ninguna nueva. Empaqueta, despliega por GitOps y mide lo que implementan los Pasos 1 a 13.
**Depende de:**
- U07-T03 (servicios), fusionado en `main`;
- U06-T03 (presupuesto de kind con U6, `BUDGET_GIB` = 8,5) y U04-T06 (chart de governance, que vuelve a subir `BUDGET_GIB`), fusionados en `main`: la cifra de partida del presupuesto es la que dejen.

**Se despacha** cuando U07-T03, U06-T03 y U04-T06 estén fusionados en `main`.
**Rama:** `tarea/U07-T04`, desde `origin/main`.

Bloque E del plan de U7 (`aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`) más el cierre, tarea «E+cierre (14, 15, 17, 19, 20)» de `demo-recorte-funcional.md` §8. La verificación en kind (Paso 18) se consolida en U12 (enmienda §8). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 14 Dockerfiles y cadena de suministro | **E\*** | Entran las dos imágenes, base por digest, `runAsNonRoot`, `readOnlyRootFilesystem`, plantillas en la imagen de explainability y `hadolint`. Se difieren la firma, el SBOM y la prueba sobre el SBOM; la misma comprobación (sin cliente de LLM ni librería de circuit breaking) se hace con `pip list` en la imagen | Alcance §3 U7; enmienda §3 U7; T1 |
| 15 Chart, cuota y flujos | **E\*** | Completo, con el perfil de recursos de DD-3 b (values de kind existentes, 2 réplicas) | Alcance §3 U7; enmienda §3 U7; T6; DD-3 |
| 16 Alertas y runbooks | **D** | Entero fuera, incluida la prueba del nombre de la métrica contra la regla de U4 | T2 |
| 17 Applications, carga y trazabilidad | **E\*** | Entran la Application (wave 5) y la trazabilidad con la lista de diferidos. Se difiere el script k6 y su `k6 inspect` | Enmienda §3 U7; T3; P-4 |
| 18 Verificación en kind | — | Queda `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». Sus escenarios de demo (5, 7 y el humo del flujo base) los cubre U12; el 1–4, 6, 8 y 9 se difieren (P-10) | Enmienda §3 U7 y §8 |
| 19 Repositorio, migraciones y frontend: N/A | **N/A** | — | — |
| 20 Cierre de la unidad | **E\*** | Cierre acotado, sin los Pasos 6 y 9 (según P-1) | Enmienda §3 U7 y §8 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:** los Pasos 14, 15, 17, 19 y 20 del plan, con su texto y su aceptación, salvo lo que se difiere arriba. Léelos allí. Precisiones:

### Paso 14 — Imágenes (E\*)

- `scoring-explainability/scoring/Dockerfile` y `scoring-explainability/explainability/Dockerfile`, multi-stage, como `decision-registry/Dockerfile`, con contexto en la raíz de `vectra-risk/`:
  - base Python oficial con cada `FROM` fijado por digest;
  - usuario `65532:65532`, el mismo `runAsUser`/`runAsGroup` del chart;
  - solo el runtime del servicio y sus dependencias del workspace (U0), sin dependencias de desarrollo;
  - las plantillas (`template_v1.txt`, y `applicant_v1.txt` solo si P-1 eligió (a)) van dentro de la imagen de explainability;
  - arranque con `vectra_common.ops_server.run_service(app)` (8080 y 8081).
- Targets `image-scoring` e `image-explainability` en `scoring-explainability/Makefile`, con tags `localhost:5001/vectra/scoring-service:dev` y `localhost:5001/vectra/explainability-service:dev`.
- El push a `kind-registry` y el digest real los hace el operador en la verificación consolidada de U12 Paso 18 (enmienda §8). Deja los comandos (build, push, digest y el PR de values de kind) en `scoring-explainability/docs/imagenes.md`, sin ejecutarlos. Sin firma ni SBOM (T1) y sin workflow nuevo (T4).
- Diseño: NFR-U7-32; P-U7-07.

### Paso 15 — Chart, cuota y flujos (E\*)

- `scoring-explainability/chart/`, con dos servicios. Por servicio: `Deployment`, `Service` (8080 y 8081), `HorizontalPodAutoscaler`, `PodDisruptionBudget`, `ServiceAccount`, `ExternalSecret` y `ServiceMonitor` (8081).
  - El `ExternalSecret` trae la llave `private_key_jwt` del cliente de Keycloak desde la bóveda (U2; el formato está en `governance/chart/templates/validation-job.yaml`).
  - Recursos y probes de INF-U7-01: requests de 250m / 256 MiB, limits de 1 CPU / 512 MiB; readiness `/readyz` cada 5 s y liveness `/livez` cada 10 s en 8081; sin `startupProbe`.
  - HPA de 2 a 6 por CPU al 70 %, con estabilización de 60 s hacia arriba y 300 s hacia abajo; PDB `minAvailable: 1`; spread por zona; `vectra-high`; sidecar nativo de Linkerd (P-U7-06).
  - `lifecycle.preStop.sleep.seconds: 5` y `terminationGracePeriodSeconds: 20` (INF-U7-03).
  - **Sin variables con los nombres de los presupuestos** (INF-U7-04). El chart solo inyecta URLs y puertos de las dependencias (incluida la plantilla de URL del explicador de U07-T03), audiencias, telemetría y nivel de log.
  - Las etiquetas y `ServiceAccount` son las que espera `platform/network/flows.yaml` (`scoring-service`, `explainability-service`).
  - Reglas de admisión del plan: imagen por digest (de ejemplo, como los otros charts), `runAsNonRoot`, `readOnlyRootFilesystem` con `emptyDir` si algo escribe en disco, sin `privileged` ni `hostPath`, recursos, `priorityClassName`, `vectra.io/criticality`, 2 réplicas o más, spread, PDB por `app.kubernetes.io/name` y HPA (`aidlc-docs/construction/shared-infrastructure.md` §2).
  - El `Deployment` declara `replicas: 2`: `test_kind_profile.py` cuenta `spec.replicas` (1 si falta).
- `scoring-explainability/policies/conftest/` con las reglas del plan: HPA 2–6, PDB, spread, `priorityClassName`, `preStop.sleep`, el período de gracia y la ausencia de variables de presupuesto. Cada regla con un caso que falla con una mutación del render.
- **Cuota (INF-U7-02).** El aporte de U7 ya está en `platform/policies/quotas/quotas.yaml` (`U7: { requests: [6.37, 4.91], limits: [27.3, 11.38] }`). Comprueba que coincide con INF-U7-02 y que el render cabe. El plan dice `conftest test platform/policies/quotas/`, pero en el repositorio esa comprobación es `platform/policies/quotas/render.py --check` y `test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota`; usa esas y regístralo. Si el aporte no coincide, **repórtalo**: no edites U1.
- **Flujos (INF-U7-05).** Verifica que F12, F15, F18 a F23 y F103 están en `platform/network/flows.yaml`, sin flujos nuevos, y que X01 y X02 siguen en `forbidden.yaml`. Si algo falta, **repórtalo**: no edites U1.
- **Perfil demo (T6):** DD-3 b. Sin `values-kind-demo.yaml`; los values de kind mantienen 2 réplicas (`require-hpa-bounds`).
- Diseño: INF-U7-01, 02, 03, 04, 05; P-U7-06; NFR-U7-20, 30.

### Presupuesto de memoria de kind (`DECISIONES-LOOP.md` §7)

- U7 pide en kind 2 servicios × 2 réplicas × (256 + 20) MiB ≈ **1,08 GiB**.
- Con la Application de U7 en `components.yaml`, `test_kind_profile.py::test_the_profile_requests_fit_the_budget` falla con el tope actual. Esta tarea **sube `BUDGET_GIB`** a la cifra que dé `requested_gib()` con U7 incluida, redondeada hacia arriba a 0,1 GiB, con un comentario de la decisión (§7: «se vuelve a revisar con cada unidad nueva»).
- **Umbral de detención:** `BUDGET_GIB` de `main` en la base de la rama + 1,08 + 0,2 GiB (≈ base + 1,3). Ejemplo: con 8,5 en `main`, el tope es 9,8 GiB; si U04-T06 lo deja en ≈ 9,0, el tope es ≈ 10,3 GiB. **Si la cifra medida pasa del umbral, detente y repórtalo** con la cifra, el desglose por unidad y las opciones (bajar requests de U7 en kind como hizo U6 con la opción c, DD-3 a, u otra). No cambies los requests de U7 por tu cuenta.

### Paso 17 — Application y trazabilidad (E\*)

- Entrada `scoring-explainability` en `vectra-risk-gitops/components.yaml`: `wave: 5`, `namespace: vectra-app`, `path: scoring-explainability/chart`, `env_values: true` (como `decision-registry`). `generate.py` escribe una Application por entorno, sin `syncPolicy.automated`. Values en `vectra-risk-gitops/values/<env>/scoring-explainability.yaml`.
- **Trazabilidad (P-4).** `test_traceability.py --unit scoring-explainability --all` en 0 con la lista «Diferido por la demo» de `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md`:
  - cada fila lleva el identificador, el paso que lo implementaría y la cita del recorte (T1, T2, T3, P-1, §3 o §8 de la enmienda);
  - solo entran identificadores de partes diferidas: BR-U7-13, BR-U7-14 y NFR-U7-03 (enmienda §3 U7, Paso 17; salen si P-1 eligió (a)), lo del Paso 16 (T2), `mutmut` del Paso 7 (NFR-U7-41, T3), la carga del Paso 17 (T3) y lo que solo verifica el Paso 18 (consolidado en U12, §8);
  - los identificadores de los Pasos 1 a 15 que entran se trazan en el código o en las pruebas, no en la lista;
  - el codificador corre primero la prueba, registra qué identificadores marca y justifica cada uno.
- `test_traceability.py` no ve las BR-U7 (están en párrafos en negrita; candidata de U03-T02). Por eso hay un `git grep` por BR (CA-6), como en U3.
- Diseño: P-U1-12; NFR-U7-01, 02, 03 (los tres se difieren con k6).

### Paso 18 — Consolidado en U12

- Queda `[ ]` en el plan con la nota «consolidado en U12 Paso 18 (enmienda §8)». Ninguna guía de kind en esta tarea.

### Paso 19 — N/A

- U7 no tiene base de datos, migraciones ni interfaz.

### Paso 20 — Cierre acotado (E\*)

- `make -C scoring-explainability check` corre en orden las verificaciones estáticas, las propiedades y las pruebas de integración de los Pasos 1 a 17 que entran, y termina en 0.
- `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md` completo, con el formato de `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`:
  - **Comprobado:** cada paso que entra, con su comando y su resultado;
  - **Diferido por la demo:** la lista de P-4, más los Pasos 6 y 9 (según P-1), el 16 (T2), `mutmut` (T3), k6 (T3), firma y SBOM (T1), y los escenarios 1–4, 6, 8 y 9 del Paso 18 (P-10), cada uno con su destino;
  - **Pendiente en U12:** los escenarios 5 (promoción → 0 `version_mismatch`), 7 (freeze → `model_frozen` ≤ 6 s) y el humo del flujo base, más el push de las imágenes, que verifica U12 Paso 18 (enmienda §8).
- RL-4: al cerrar la unidad, el `make check` de todas las unidades corre una vez (CA-10).

### Plan

- Paso 14 y 15: `[x] (U07-T04, acotado a la demo)`. Paso 17: `[x] (U07-T04, acotado a la demo)`. Paso 19: `[x] (U07-T04)`. Paso 20: `[x] (U07-T04, acotado a la demo)`.
- Paso 16: `[ ]` con «diferido por la demo (T2)».
- Paso 18: `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».

**Fuera** (rechazar aunque se vea roto o tentador):

- Paso 16 completo: `PrometheusRule`, las siete alertas de P-U7-08, sus runbooks, `promtool`, `test_runbooks.py --root scoring-explainability` y la prueba del nombre de la métrica contra la regla de U4 (T2).
- Firma, SBOM, la prueba sobre el SBOM con `syft`/`grype` y `sign-image.yml` (T1).
- `tests/load/recommendations.js` y `k6 inspect` (T3).
- Guía, scripts y escenarios de kind (Paso 18): van en U12 (enmienda §8).
- Push de imágenes, digest real y cualquier `kubectl`, `helm install`, `argocd` o sync (AUTONOMIA-01).
- `values-kind-demo.yaml` o 1 réplica (DD-3 eligió la b).
- Cambios en U0, y en U1 salvo `BUDGET_GIB` (y su comentario) en `platform/tests/test_kind_profile.py`, `test_traceability.py` si P-4 lo necesita para U7 y lo que `generate.py` genera.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`: §1, Pasos 14 a 20, §3 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U7, §5.3 (T6 frente a la admisión), §6 (P-1, P-4, P-10) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §5 (DD-3) y §6.
- `DECISIONES-LOOP.md` §6 y §7.
- `aidlc-docs/construction/scoring-explainability/infrastructure-design/` (INF-U7-01 a 05, `deployment-architecture.md` §3) y `nfr-design/nfr-design-patterns.md` (P-U7-06, 07).
- `aidlc-docs/construction/shared-infrastructure.md` §2.
- `decision-registry/Dockerfile`, `decision-registry/chart/`, `decision-registry/Makefile` (`policy-chart-u1`) y `tareas/U03-T05-despliegue-y-calidad.md`: la misma tarea hecha para U3.
- `governance/chart/` (`ExternalSecret`) y `model-serving/Makefile` (`kubeconform` con CRD de fixture).
- `platform/network/flows.yaml`, `platform/network/forbidden.yaml`, `platform/policies/quotas/quotas.yaml` y `render.py`, `platform/policies/kyverno/` y `platform/policies/rego/`.
- `vectra-risk-gitops/components.yaml`, `generate.py` y `README.md`; `platform/tests/test_waves.py`, `test_kind_profile.py`, `test_integration.py`, `integration.py`, `test_traceability.py` y `test_traceability_cli.py`.
- `aidlc-docs/construction/reference-model/evidence/cierre-demo.md` y `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md` (formato).
- `CANDIDATAS.md`: el pánico de Kyverno en `check-chart` (U03-T04 y U04-T05) y la trazabilidad de BR en negrita (U03-T02).

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 14: imágenes.
  ```bash
  platform/.tools/bin/hadolint scoring-explainability/*/Dockerfile
  make -C scoring-explainability image-scoring image-explainability
  for s in scoring-service explainability-service; do docker image inspect localhost:5001/vectra/$s:dev --format '{{.Config.User}}'; docker run --rm --entrypoint sh localhost:5001/vectra/$s:dev -c '! pip list 2>/dev/null | grep -iE "^(openai|anthropic|langchain[a-z-]*|pybreaker|circuitbreaker|aiobreaker|purgatory[a-z-]*|pytest|hypothesis) " && echo OK'; done
  docker run --rm --entrypoint sh localhost:5001/vectra/explainability-service:dev -c 'find / -name template_v1.txt 2>/dev/null | grep -q . && echo OK-plantilla'
  grep -nE '^FROM .*@sha256:[0-9a-f]{64}' scoring-explainability/*/Dockerfile
  ```
  Esperado: `hadolint` en 0, usuario `65532:65532` y `OK` en las dos, `OK-plantilla`, y cada `FROM` por digest. Si `hadolint` no está en `platform/.tools/bin` del worktree, usa el del checkout principal tras comparar la versión con `tools.env`.

- [ ] **CA-2** — Paso 15: render, esquema y `conftest` del chart.
  ```bash
  for env in kind staging prod; do uv run python platform/tests/integration.py --chart scoring-explainability/chart --namespace vectra-app --env $env --out /tmp/u7-$env; done
  for env in kind staging prod; do platform/.tools/bin/kubeconform -strict -summary -schema-location default -schema-location 'scoring-explainability/tests/fixtures/crds/{{.ResourceKind}}.json' /tmp/u7-$env/*.yaml; done
  for env in kind staging prod; do platform/.tools/bin/conftest test --policy scoring-explainability/policies/conftest /tmp/u7-$env/*.yaml; done
  uv run pytest scoring-explainability/tests/unit/test_chart.py -v
  ```
  Esperado: código 0. Los CRD de `ExternalSecret` y `ServiceMonitor` se guardan como fixture, con su fuente en la bitácora. `test_chart.py` tiene un caso por regla que falla con una mutación. Como mínimo: HPA fuera de 2–6, sin PDB, sin spread, prioridad distinta de `vectra-high`, recursos distintos de INF-U7-01, sin `preStop.sleep` de 5 s, `terminationGracePeriodSeconds` < 20, una variable con el nombre de un presupuesto (por ejemplo `PRE_REGISTRY_BUDGET`), un `Secret` en el render y etiquetas distintas de las de `flows.yaml`.

- [ ] **CA-3** — Paso 15: admisión de U1 en los tres entornos.
  ```bash
  make -C platform check-chart CHART=scoring-explainability/chart NAMESPACE=vectra-app
  ```
  Esperado: código 0, Kyverno con `fail: 0` y `conftest` de `platform/policies/rego` (incluido `--namespace hpa`) en 0. Si Kyverno entra en pánico por recursos repetidos entre entornos (candidata de U03-T04 y U04-T05), agrega un target `policy-chart-u1` en `scoring-explainability/Makefile` con un entorno por directorio, como `decision-registry/Makefile`, y regístralo.

- [ ] **CA-4** — Paso 15: cuota y flujos.
  ```bash
  uv run python platform/policies/quotas/render.py --check \
    && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -v \
    && uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -v \
    && for id in F12 F15 F18 F19 F20 F21 F22 F23 F103; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done \
    && grep -cE "id: X0[12], from: (scoring|explainability)-service" platform/network/forbidden.yaml
  ```
  Esperado: código 0, ninguna línea «falta» y `4` en la última orden. Una prueba de `test_chart.py` compara las etiquetas del render con `flows.yaml`.

- [ ] **CA-5** — Paso 17: Application.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/scoring-explainability.yaml; done \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/scoring-explainability.yaml
  ```
  Esperado: código 0. Una Application por entorno, wave `"5"` (`FIXED_WAVES` ya la fija) y sin `syncPolicy.automated`.

- [ ] **CA-6** — Paso 17: trazabilidad (P-4).
  ```bash
  uv run python platform/tests/test_traceability.py --unit scoring-explainability --all \
    && for n in 01 02 03 04 05 06 07 08 09 10 11 12 15 16; do git grep -qiE "BR-U7-$n([^0-9]|$)" -- scoring-explainability/tests || echo "BR-U7-$n sin prueba"; done
  grep -n "Diferido por la demo" -A40 aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md
  ```
  Esperado: código 0 y ninguna línea «sin prueba». Si P-1 eligió (a), el bucle incluye también 13 y 14. `--all` cumple la regla de `DECISIONES-LOOP.md` §6 con su enmienda. La lista no contiene identificadores de los Pasos 1 a 15 que entran.

- [ ] **CA-7** — Presupuesto de kind.
  ```bash
  uv run pytest platform/tests/test_kind_profile.py -v
  git diff origin/main -- platform/tests/test_kind_profile.py
  ```
  Esperado: código 0. El diff solo cambia `BUDGET_GIB` y su comentario, con la cifra medida con U7 (redondeada hacia arriba a 0,1 GiB) y la cita de `DECISIONES-LOOP.md` §7. La cifra no pasa del umbral de la sección «Presupuesto»; si pasa, es una detención, no un ROJO del codificador.

- [ ] **CA-8** — Paso 19: N/A.
  ```bash
  test ! -d scoring-explainability/migrations && test ! -d scoring-explainability/frontend
  ```
  Esperado: código 0.

- [ ] **CA-9** — Paso 20: cierre.
  ```bash
  make -C scoring-explainability check && make -C platform check
  grep -nE "^## (Comprobado|Diferido por la demo|Pendiente en U12)" aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md
  test -s scoring-explainability/docs/imagenes.md
  ```
  Esperado: código 0 y las tres secciones. `check` de U7 incluye la cobertura de U07-T02 y U07-T03, el chart (CA-2) y la admisión (CA-3).

- [ ] **CA-10** — RL-4: el `make check` de todas las unidades, una vez al cerrar U7.
  ```bash
  for u in contracts platform identity-edge decision-registry governance reference-model model-serving bias-monitoring scoring-explainability; do make -C $u check || echo "FALLA $u"; done
  ```
  Esperado: ninguna línea «FALLA». Si una unidad ajena falla y el fallo también ocurre en `origin/main`, regístralo con la salida: no es de esta tarea.

- [ ] **CA-11** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso (1[4-9]|20) "
  ```
  Esperado: Pasos 14, 15, 17 y 20 en `[x] (U07-T04, acotado a la demo)`; 19 en `[x] (U07-T04)`; 16 en `[ ]` con «diferido por la demo (T2)»; 18 en `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U07-T04.md`:
- `minReplicas: 1` en un HPA;
- sin PDB en explainability;
- `vectra-normal` en scoring;
- `terminationGracePeriodSeconds: 10`;
- sin `preStop.sleep`;
- una variable `PRE_REGISTRY_BUDGET` en el `Deployment`;
- un `Secret` en el render;
- `syncPolicy.automated` en `apps/kind/scoring-explainability.yaml` (Kyverno falla);
- `wave: 4` en `components.yaml` (`test_waves.py` falla);
- un identificador del Paso 15 en la lista de diferidos, o uno diferido fuera de ella (`test_traceability.py` falla);
- `pybreaker` instalado en la imagen de scoring (la orden de CA-1 falla);
- `FROM python:3.12-slim` sin digest (la orden de CA-1 falla).

---

## Notas

- **Presupuesto de kind:** ver la sección del Alcance. Registra en la bitácora la cifra con y sin U7, y el desglose por unidad.
- **P-1:** la plantilla `applicant_v1.txt`, BR-U7-13, BR-U7-14 y NFR-U7-03 dependen de lo que decidió el usuario para U07-T03. Si P-1 sigue abierta al despachar esta tarea, **detente y repórtalo**.
- Archivos que se modifican en su sitio: `scoring-explainability/` (Dockerfiles, `chart/`, `policies/`, `tests/`, `Makefile`), `vectra-risk-gitops/components.yaml` y lo generado, `vectra-risk-gitops/values/<env>/scoring-explainability.yaml`, `platform/tests/test_kind_profile.py` (solo `BUDGET_GIB`), el plan y `CANDIDATAS.md`. Archivos nuevos: `scoring-explainability/docs/imagenes.md` y `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md`.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- Docker está disponible para construir las imágenes.
- **Bitácora:** `bitacoras/U07-T04.md`, con los pares falla-pasa, la lista de diferidos razonada, la fuente de los CRD de fixture y la memoria de kind.
