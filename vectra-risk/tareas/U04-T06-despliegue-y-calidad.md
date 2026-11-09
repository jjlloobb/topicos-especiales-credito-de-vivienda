# U04-T06 — Chart del servicio, documentación, Application de GitOps, cobertura y trazabilidad de `governance`

**Unidad:** U4 `governance`
**Historias que implementa:** ninguna nueva. Despliega y mide lo que implementan los Pasos 1 a 13.
**Depende de:** U04-T05 (chart mínimo con la `ServiceAccount` y el `ExternalSecret` de `model-validation-job`).
**Se despacha** cuando U04-T05 esté fusionado en `main`.
**Rama:** `tarea/U04-T06`, desde `origin/main`.

Bloques F y G del plan de U4, fusionados como «F+G (16–19)» (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §4). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 16 Chart, flujos y RBAC | **E\*F** | Entran el Deployment (perfil T6, DD-3 b), el hook de migración, `pg-role-gov-app`, `minio-governance`, RBAC K01, el runbook de política en kind (con P-9) y la verificación de la ruta `freeze` solo para `bias-monitoring-job`. Se difieren el CronJob `model-archive`, `pg-role-gov-archiver`, `minio-model-archive`, F100 y los values de staging de INF-U4-05 | Enmienda §3 U4 |
| 17 Alertas, runbooks y documentación | **E\*** | Solo `docs/slo.md`, más el runbook de `CompensationEventPending` (P-3) | Alcance §3 U4 (T2); P-3 |
| 18 Application de GitOps | **E** | Completo | — |
| 19 Cobertura, mutación, trazabilidad y carga | **E\*** | Se difieren `mutmut` y k6. La trazabilidad usa la lista de diferidos (P-4) | T3; P-4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige la regla «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).

---

## Alcance

**Dentro:** los Pasos 16 a 19 del plan (`governance-code-generation-plan.md`), con su texto y su aceptación, salvo lo que se difiere abajo. Léelos allí. Precisiones:

### Paso 16 — Chart, flujos y RBAC (E\*F)

- **Deployment `governance-service`** (INF-U4-01): HPA de 2 a 6 por CPU al 70 %, spread por zona, PDB `minAvailable: 1`, `vectra-high`, requests de 250m / 256 MiB y limits de 1 CPU / 512 MiB.
  - Puertos 8080 (contrato) y 8081 (`/metrics`, `/healthz`, `/readyz`, de `vectra_common.ops_server`).
  - DSN sin credenciales en la URL. Las credenciales salen del Secret `pg-role-gov-app` de U1. El chart no crea ningún Secret.
  - Lectura del model-store con `minio-governance` (`governance-readonly`, F47), de U1.
  - `ServiceMonitor` del puerto 8081.
- **Job de migración como hook** de Argo CD: `ServiceAccount` `migration-governance`, etiqueta `vectra.io/workload: migration-governance` (F44), `pg-role-gov-migrator`, requests de 100m / 128 MiB y limits de 500m / 256 MiB, `activeDeadlineSeconds: 600`, `vectra-normal` y sidecar nativo de Linkerd. Corre `alembic upgrade head`.
- **RBAC K01**: el `Role` y el `RoleBinding` en `vectra-staging` con los que `governance-service` crea y lee los Jobs de validación. Nada más.
- **Runbook de kind para la política**: carga `reference-policy.json` de U5 por la API normal, con **`cro-2` proponiendo y `cro-1` aprobando** (P-9: corrige el «`ingeniero-1`» del plan, que la matriz y BR-U4-10 no permiten), sin ningún atajo en el servicio. Va en `governance/runbooks/kind-politica-de-referencia.md`. Lo ejecuta el operador en U04-T07.
- **Flujos**: verifica en `platform/network/flows.yaml` que estén F44, F47, F101 y F102 (F100 se difiere con `model-archive`), y que las etiquetas del render coincidan con las de `flows.yaml`. Verifica que la ruta `freeze` de `http_routes.governance-service` solo admite la identidad `bias-monitoring-job`. Si algo falta, **repórtalo**: no edites U1.
- **Sin `AuthorizationPolicy` ni `HTTPRoute`** en el chart: las genera U1.
- **Reglas de admisión** del plan: imagen por digest, `runAsNonRoot`, `readOnlyRootFilesystem`, recursos, `priorityClassName`, `vectra.io/criticality`, 2 réplicas o más, spread, PDB y HPA.
- **Perfil de recursos:** DD-3 b. Sin `values-kind-demo.yaml`; el chart usa los values de kind existentes.
- **Imagen del servicio** (agregada al Paso 16 por decisión del usuario, 2026-11-09). El plan de U4 no asigna el `Dockerfile` del servicio a ningún paso, como pasó en U3, donde el usuario lo agregó al Paso 13 (2026-11-09). Sin imagen el servicio no arranca en kind.
  - `governance/Dockerfile`, multi-stage, como `decision-registry/Dockerfile`, con `tzdata` para `America/Bogota` (INF-U4-01, P-U4-05).
  - Solo el runtime de `vectra-governance` y sus dependencias del workspace. Sin ONNX Runtime, `xgboost` ni `lightgbm` (la regla de `sbom-check` del Paso 14, que se difiere, se comprueba aquí con `pip list`).
  - Usuario `65532:65532`, `FROM` por digest, target `image` en `governance/Makefile`. El push y el digest real son de U04-T07. Sin firma ni SBOM (T1).
- Diseño: NFR-U4-03 y 25; INF-U4-01, 04.

### Paso 17 — Documentación (E\*)

- `governance/docs/slo.md` (governance dentro del SLO, NFR-U4-01).
- `governance/runbooks/compensation-event-pending.md`: la regla `CompensationEventPending` (P-3) ya existe y su `runbook_url` apunta a ese archivo, que falta (candidata de U04-T03).
- Las demás alertas de P-U4-08 y sus runbooks se difieren (T2).

### Paso 18 — Application de GitOps (E)

- Entrada `governance` en `vectra-risk-gitops/components.yaml`: `wave: 5`, `namespace: vectra-app`, `path: governance/chart`. Migración como hook, servicio y, en `vectra-staging`, lo de U04-T05.
- `generate.py` escribe las Applications. Values por entorno en `vectra-risk-gitops/values/<env>/governance.yaml`.
- Ninguna Application con `syncPolicy.automated`.
- Si el chart necesita dos Applications por los dos namespaces (`vectra-app` y `vectra-staging`), sigue el patrón que ya use `components.yaml` para casos así y regístralo en la bitácora. Si no hay patrón, detente y repórtalo.

### Paso 19 — Cobertura y trazabilidad (E\*)

- Cobertura de ramas ≥ 95 % global y **100 %** en `model_fsm`, `policy` y `evidence`. El comando nombra `vectra_governance` (el `--cov` sin argumento mide U0; candidata de U05-T04).
- Trazabilidad de cada BR-U4 a una prueba.
- `test_traceability.py --unit governance --all` en 0 con la lista «Diferido por la demo» de P-4, en `aidlc-docs/construction/governance/evidence/cierre-demo.md`. Esta tarea crea el archivo **solo con esa sección**; el resto lo escribe U04-T07.
  - Cada fila lleva el identificador, el paso que lo implementaría y la cita del recorte.
  - Solo entran identificadores de partes diferidas: Pasos 14 y 15, lo diferido de los Pasos 12, 13, 16, 17 y 19, y el invariante de `source_candidate_for` (P-5).
  - El codificador corre primero la prueba, registra qué identificadores marca y justifica cada uno.

**Fuera** (rechazar aunque se vea roto o tentador):

- Paso 16: el CronJob `model-archive`, `pg-role-gov-archiver`, `minio-model-archive`, F100, la credencial del S3 del banco y los values de staging de INF-U4-05 (el predictor de la versión activa para `source_comparison`), con su línea de aceptación `conftest` sobre los values de staging.
- Paso 17: las demás alertas y runbooks (T2).
- Paso 19: `mutmut` y `k6 inspect` (T3).
- Pasos 14 y 15 (T4, T5).
- Perfil de 1 réplica (`values-kind-demo.yaml`): DD-3 eligió la b.
- Push de imágenes, digest real, `kubectl`, `argocd` o sync (AUTONOMIA-01).
- Cambios en U0, y en U1 salvo `test_traceability.py` si P-4 lo necesita (U03-T05 ya lo hizo para U3) y lo que `generate.py` genera.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md`: Pasos 16 a 19, §3 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U4, §5.3 (T6 frente a la admisión) y §6 (P-3, P-4, P-5, P-9).
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §5 (DD-3) y §6.
- `aidlc-docs/construction/governance/infrastructure-design/` (INF-U4-01 a 05) y `nfr-design/` (P-U4-05, 08).
- `aidlc-docs/construction/shared-infrastructure.md` §2.
- `tareas/U03-T05-despliegue-y-calidad.md`, `decision-registry/chart/`, `decision-registry/Dockerfile` y `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md`: la misma tarea hecha para U3.
- `platform/network/flows.yaml`, `platform/data/chart/values.yaml` (`pg-role-gov-*`, `minio-*`), `platform/policies/kyverno/` y `platform/policies/rego/`.
- `vectra-risk-gitops/components.yaml`, `generate.py` y `README.md`; `platform/tests/test_waves.py`, `test_kind_profile.py`, `integration.py`, `test_traceability.py` y `test_traceability_cli.py`.
- `reference-model/` (`reference-policy.json`) y `contracts/openapi/role-endpoint-matrix.md`.

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ningún criterio toca el clúster.

- [ ] **CA-1** — Paso 16: chart y `conftest`.
  ```bash
  helm template governance governance/chart | platform/.tools/bin/conftest test --policy governance/chart/policy - && uv run pytest governance/tests/unit/test_chart.py -v
  ```
  Esperado: código 0. Cada regla de `governance/chart/policy/` tiene en `test_chart.py` un caso que falla con una mutación del render. Como mínimo: HPA fuera de 2–6, CPU distinta del 70 %, sin spread, sin PDB, prioridad distinta de `vectra-high`, recursos distintos de INF-U4-01, un DSN con clave, un `Secret` en el render, Job de migración sin hook o con otra `ServiceAccount`, y un CronJob `model-archive` en el render.

- [ ] **CA-2** — Paso 16: render y admisión de U1 en los tres entornos.
  ```bash
  for env in kind staging prod; do uv run python platform/tests/integration.py --chart governance/chart --namespace vectra-app --env $env --out /tmp/u4-$env; done
  make -C platform check-chart CHART=governance/chart
  ```
  Esperado: código 0. Kyverno con `fail: 0` y `conftest` de `platform/policies/rego` en 0 por entorno (un entorno por directorio, como U3).

- [ ] **CA-3** — Paso 16: flujos y ruta `freeze`.
  ```bash
  uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -v \
    && for id in F44 F47 F101 F102; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done
  ```
  Esperado: código 0 y ninguna línea «falta». Una prueba de `test_chart.py` compara las etiquetas del render con `flows.yaml`, y otra confirma que la ruta `freeze` de `governance-service` solo lista `bias-monitoring-job`.

- [ ] **CA-4** — Paso 16: runbook de política (lectura).
  ```bash
  grep -nE "cro-2|cro-1" governance/runbooks/kind-politica-de-referencia.md && ! grep -n "ingeniero-1" governance/runbooks/kind-politica-de-referencia.md
  ```
  Esperado: `cro-2` propone y `cro-1` aprueba, por `POST /api/console/policies` y `…/approval` (o directo a U4 con el token del rol, si el BFF de U10 no existe todavía; el runbook dice cuál y por qué).

- [ ] **CA-5** — Paso 17.
  ```bash
  test -s governance/docs/slo.md && test -s governance/runbooks/compensation-event-pending.md && make -C governance rules
  ```
  Esperado: código 0, y `make rules` corre `promtool` (no lo omite).

- [ ] **CA-6** — Paso 18: Application.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/governance.yaml; done \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/governance.yaml
  ```
  Esperado: código 0. Una Application por entorno, wave `"5"`, sin `syncPolicy.automated`.

- [ ] **CA-7** — Paso 19: cobertura.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest governance/tests --cov=vectra_governance --cov-branch --cov-fail-under=95 \
    && uv run coverage report --include="*/vectra_governance/model_fsm.py,*/vectra_governance/policy.py,*/vectra_governance/evidence.py" --fail-under=100
  ```
  Esperado: código 0. Los dos comandos quedan en el `check` de `governance/Makefile`.

- [ ] **CA-8** — Paso 19: trazabilidad.
  ```bash
  uv run python platform/tests/test_traceability.py --unit governance --all \
    && for n in 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19; do git grep -qiE "BR-U4-$n([^0-9]|$)" -- governance/tests || echo "BR-U4-$n sin prueba"; done
  ```
  Esperado: código 0 y ninguna línea «sin prueba». `--all` cumple «sin fallos nuevos». La lista de diferidos de `cierre-demo.md` no contiene identificadores de pasos que entran.

- [ ] **CA-9** — Imagen del servicio (agregada al Paso 16 por decisión del usuario).
  ```bash
  make -C governance image
  docker image inspect localhost:5001/vectra/governance:dev --format '{{.Config.User}}'
  docker run --rm --entrypoint sh localhost:5001/vectra/governance:dev -c 'python -c "import vectra_governance, zoneinfo; zoneinfo.ZoneInfo(\"America/Bogota\")" && ! pip list 2>/dev/null | grep -iE "onnxruntime|xgboost|lightgbm" && echo OK'
  ```
  Esperado: usuario `65532:65532` y `OK`.

- [ ] **CA-10** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C governance check && make -C platform check
  ```
  Esperado: código 0 en los dos. Si `make -C platform check` falla **solo** en `test_kind_profile.py::test_the_profile_requests_fit_the_budget`, aplica la nota del presupuesto.

- [ ] **CA-11** — Estado del plan: Pasos 16, 17 y 19 en `[x] (U04-T06, acotado a la demo)`, el 18 en `[x] (U04-T06)`.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U04-T06.md`: `minReplicas: 1`, sin PDB, `vectra-low` en el Deployment, contraseña en el DSN, Job de migración sin hook, un CronJob `model-archive` en el render, `syncPolicy.automated` en la Application, un identificador del Paso 16 en la lista de diferidos y una rama de `model_fsm.py` sin prueba.

---

## Notas

- **Presupuesto de memoria de kind (detención con reporte):** `BUDGET_GIB` está en 6,1. Con governance entra un Deployment de 2 réplicas × (256 + 20) MiB, ≈ 0,54 GiB. Si `test_kind_profile.py` falla por eso, **detente y repórtalo** con la cifra y las opciones (subir el tope, DD-3 a, otra). No cambies `BUDGET_GIB` ni el perfil por tu cuenta.
- `sslmode` de `governance-db`: el mismo que use U3. No lo cambies sin la CA.
- Archivos que se modifican en su sitio: `governance/chart/`, `governance/Makefile`, `governance/tests/`, `vectra-risk-gitops/components.yaml` y lo generado, el plan y `CANDIDATAS.md`. Archivos nuevos: `governance/Dockerfile`, `governance/docs/slo.md`, los dos runbooks y `aidlc-docs/construction/governance/evidence/cierre-demo.md` (solo «Diferido por la demo»).
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- **Bitácora:** `bitacoras/U04-T06.md`, con la cobertura de partida y la final, la lista de diferidos razonada, los pares falla-pasa y la memoria de kind con y sin governance.
