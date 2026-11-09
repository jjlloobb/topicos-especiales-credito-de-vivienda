# U03-T05 — Chart del servicio, Application de GitOps, cobertura y trazabilidad de `decision-registry`

**Unidad:** U3 `decision-registry`
**Historias que implementa:** ninguna nueva. Esta tarea despliega y mide lo que ya implementan US-401, US-402, US-403 y US-404 (Pasos 2 a 12).
**Depende de:** U03-T04 (CLI y CronJob del agregador), ya fusionado en el PR #91.
**Rama:** `tarea/U03-T05`, desde `origin/main` (`0a5c990`). Corre en paralelo con U04-T01 y U09-T01, que tocan `governance/`, `bias-monitoring/`, el `pyproject.toml` raíz y `uv.lock`; tú no toques esos archivos.

Bloques F y G del plan de U3, fusionados como «F+G (13, 15, 16)» (`aidlc-docs/construction/plans/demo-recorte-funcional.md` §4, enmienda P-2 a RL-1). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 13 Chart, buckets y flujos | **E\*F** | Entran el Deployment, el `ServiceMonitor` y la comprobación de flujos. Se difieren los values de buckets y de Transit | Enmienda §3 U3; alcance §3 U3 (T6) |
| 14 Alertas y runbooks | **D** | Entero fuera de esta tarea | T2 |
| 15 Applications de GitOps | **E\*F** | Entra `decision-registry` (wave 5). Se difieren `decision-registry-rebuild`, `rebuild-history.yaml`, `rebuild-runid-check.yml` y la comprobación de la wave 6 | Enmienda §3 U3 |
| 16 Cobertura, mutación y trazabilidad | **E\*** | Se difiere la mutación. La trazabilidad usa la lista de diferidos | T3; enmienda §2.3 y §3 U3; P-4 |
| 17 Benchmarks | **D** | Entero fuera de esta tarea | T3 |

Rige el ritmo RL-1 a RL-5 (`demo-kind-alcance.md` §6): **máximo 2 rondas**, y **solo un ROJO bloquea**. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las cuatro demos.

---

## Alcance

**Dentro:**

### Paso 13 — Chart del servicio y flujos (E\*F)

Lo que entra está copiado del plan (`decision-registry-code-generation-plan.md`, Paso 13), sin más recortes que los nombrados. Se completa el `decision-registry/chart/` mínimo que dejó U03-T04, que hoy tiene el CronJob `registry-aggregator`, 5 ServiceAccounts y `chart/policy/{aggregator,set}.rego`.

- **Deployment `decision-registry-service`:**
  - HPA de 2 a 6 réplicas, por CPU al 70 %;
  - spread por zona (`topologySpreadConstraints`);
  - PDB;
  - `vectra-critical`;
  - recursos de INF-U3-03: requests de 250m / 256 MiB y limits de 1 CPU / 512 MiB.
- **Puertos y sondas:** 8080 con el contrato y 8081 con `/metrics`, `/healthz` y `/readyz` (`vectra_common.ops_server`). La readiness es la de P-U3-01 y NFR-U3-11.
- **Configuración del servicio:** la que lee `src/vectra_registry/service.py`.
  - Tres DSN, sin credenciales en la URL, igual que el CronJob:
    - `REGISTRY_RW_APP_DSN`, con `registry_app` contra `-rw`;
    - `REGISTRY_RW_HEALTH_DSN`, con `registry_health` contra `-rw`;
    - `REGISTRY_RO_VERIFIER_DSN`, con `registry_verifier` contra `-ro`.
  - Las credenciales salen de los Secrets `pg-role-registry-*` que entrega U1. El chart no crea ningún Secret.
  - `REGISTRY_CHECKPOINT_PUBLIC_KEYS` (candidata de U03-T03, `CANDIDATAS.md`): ver la nota sobre la huella y las llaves en «Notas».
- **Identidad y etiquetas:** las que espera `platform/network/flows.yaml`, es decir, la ServiceAccount `decision-registry-service` y `app.kubernetes.io/name: decision-registry-service`. También las reglas de admisión del plan: imagen por digest, `runAsNonRoot`, `readOnlyRootFilesystem`, sin `privileged` ni `hostPath`, recursos, `priorityClassName`, `vectra.io/criticality`, 2 réplicas o más, spread, PDB por `app.kubernetes.io/name` y HPA (`shared-infrastructure.md` §2).
- **`ServiceMonitor`** del puerto de métricas del servicio (8081). Incluye el gauge `vectra_registry_monitoring_lag_seconds` (F60; sexta revisión del FD de U9, 2026-10-10).
- **Verificar en `platform/network/flows.yaml` de U1**, donde ya están (revisión de consistencia entre unidades, 2026-11-01):
  - F111 (`x06-probe` → `registry-db-rw`, solo kind; revisión del Infrastructure Design de U12, 2026-10-10);
  - F42, F96, F97, F98 (kind), F118 (kind), F77, F78, F79 y F99;
  - F107 (`registry-aggregator` y el Job `registry-aggregator-rebuild` → `registry-db-rw`);
  - F108 (Job `registry-aggregator-reset` → `registry-db-rw`; octava revisión del FD de U9, 2026-10-10);
  - F75 ampliado.

  Si falta alguno, se reporta: no se edita U1 para agregarlo.
- **Perfil de recursos:** decisión DD-3 b del alcance (§5): sin `values-kind-demo.yaml`. El chart usa los values de kind existentes y la memoria se mide (T6). Ver la nota sobre el presupuesto de kind en «Notas».
- **Diseño:** NFR-U3-11, 41; INF-U3-01..06.

### Paso 15 — Application `decision-registry` (E\*F)

- Entrada `decision-registry` en `vectra-risk-gitops/components.yaml`:
  - `wave: 5`, `namespace: vectra-app`, `path: decision-registry/chart`;
  - el **Job de migración como hook**, con la ServiceAccount `migration-registry` y la etiqueta `vectra.io/workload: migration-registry` de F44, más el servicio y los CronJobs;
  - `generate.py` escribe las Applications (revisión de consistencia entre unidades, 2026-11-01).
- El Job de migración va en el chart, con los valores de INF-U3-03:
  - hook de sync de Argo CD;
  - requests de 100m / 128 MiB y limits de 500m / 256 MiB;
  - `activeDeadlineSeconds: 600`;
  - `vectra-normal`;
  - sidecar nativo de Linkerd;
  - corre `alembic upgrade head` con `registry_migrator` (Secret `pg-role-registry-migrator` de U1; F44).
- El render de `decision-registry` **no contiene** los Jobs de reconstrucción ni `x06-probe` (pendientes posteriores al cierre, 2026-10-10).
- Ninguna Application tiene `syncPolicy.automated` (NFR-U1-43).
- **Diseño:** P-U1-12; BR-U3-17.

### Paso 16 — Cobertura y trazabilidad (E\*)

- Cobertura de ramas ≥ 95 % global y **100 %** en `chain`, `verify` y `append` (NFR-U3-52).
- Trazabilidad de cada BR-U3 a una prueba.
- `uv run python platform/tests/test_traceability.py --unit decision-registry --all` termina en 0 con la **lista de «diferido por la demo»** de P-4:
  - La lista va en `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md`, sección «Diferido por la demo». Esta tarea crea el archivo solo con esa sección; el resto del cierre es de la tarea H+I.
  - Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte (T2, T3, T5, P-6 o §3 de la enmienda).
  - `platform/tests/test_traceability.py` (U1) acepta esa lista, con su prueba en `platform/tests/test_traceability_cli.py`.
  - La lista solo puede contener identificadores de pasos o partes diferidas: BR-U3-08 y 13b (enmienda §3), y lo que la prueba marque de los Pasos 11 (lo diferido), 12 (lo diferido), 14 y 17.
  - Los identificadores de los pasos de esta tarea (INF-U3-06 y NFR-U3-52) y los de pasos ya hechos (NFR-U3-10 y 51) se trazan en el código o en las pruebas, no en la lista.
  - Hoy, en `origin/main`, la prueba marca 14 identificadores: INF-U3-02 y 06, y NFR-U3-01, 02, 03, 10, 12, 22, 23, 32, 34, 41, 51 y 52. El codificador lo confirma y deja en la bitácora cuál va a la lista y por qué.

**Agregado al plan, por decisión del usuario (2026-11-09): imagen de `decision-registry` (Paso 13).** El plan de U3 no asigna el `Dockerfile` a ningún paso, pero sin imagen el servicio y el CronJob no arrancan en kind. T1 (alcance §2) dice que las imágenes «se construyen y se publican por digest en `kind-registry`». La candidata de U03-T04 en `CANDIDATAS.md` la pone en el Paso 13.
- `decision-registry/Dockerfile`, multi-stage, como `identity-edge/jobs/Dockerfile` (contexto: la raíz de `vectra-risk/`). La etapa final lleva solo el runtime de `vectra-decision-registry` y sus dependencias del workspace (U0), sin herramientas de build ni dependencias de desarrollo. Usuario no root `65532:65532`, el mismo `runAsUser`/`runAsGroup` del chart. Los entry points son el servicio y la CLI `vectra-registry`. Imagen base fijada por digest; nada de `latest`, porque Kyverno lo rechaza.
- Target `image` en `decision-registry/Makefile`: `docker build -t localhost:5001/vectra/decision-registry:dev -f decision-registry/Dockerfile .`, corrido desde `vectra-risk/`. El `docker push` a `kind-registry` y el digest real en los values de kind los hace el operador en el Bloque H (AUTONOMIA-01). Documéntalo como hace `identity-edge/docs/paso-16-kind.md`.
- Sin firma Cosign, SBOM ni attestations (T1). Nada de workflow de CI nuevo (T4).

**Fuera** (rechazar aunque se vea roto o tentador):

- **Paso 13:**
  - los values de buckets por entorno (MinIO en kind, S3 del banco en staging y prod);
  - la URL de Transit;
  - el `ExternalSecret` de la credencial del S3 del banco.

  Cita: enmienda §3 U3, Paso 13 E\*F.
- **Perfil de demo con 1 réplica y HPA apagado** (`values-kind-demo.yaml`): DD-3 eligió la opción b. Pasar a la a cambia el Infrastructure Design y lo decide el usuario.
- **Paso 14 completo** (T2): `PrometheusRule`, las 15 alertas, los runbooks, `test_runbooks.py --root decision-registry`, `docs/retention.md` y `docs/capacity.md`.
- **Paso 15** (enmienda §3 U3, Paso 15 E\*F):
  - la Application `decision-registry-rebuild` y sus values `vectra-risk-gitops/values/<env>/decision-registry-rebuild.yaml`;
  - `vectra-risk-gitops/rebuild-history.yaml`;
  - `.github/workflows/rebuild-runid-check.yml` y su `actionlint`;
  - `tests/unit/test_rebuild_runid_check.py`;
  - la comprobación de que `decision-registry-rebuild` está en la wave 6;
  - la línea de aceptación sobre el render de `decision-registry-rebuild`.

  `chart-rebuild/` y `x06-probe` siguen diferidos (T5; enmienda §3 U3, Paso 12).
- **Paso 16:** `mutmut` en `chain` y `verify` (T3; enmienda §2.3).
- **Paso 17 completo** (T3).
- **Verificación en kind** (Bloque H, Paso 18): nada de `kubectl`, `argocd` ni sync. AUTONOMIA-01.
- **Los CronJobs diferidos por U03-T04:** `registry-checkpoint`, `registry-verify-*` y `registry-archive` (T5), y las políticas HCL nuevas (P-6).
- **Push de la imagen, digest real en los values de kind, firma y SBOM:** el push y el digest son del Bloque H (operador); la firma y el SBOM, de T1. El chart sigue con el digest de ejemplo.
- **Cambios en U0, y en U1 salvo lo que nombra esta tarea:** `test_traceability.py` y su prueba (P-4), el target de admisión si hace falta y la entrada de `components.yaml` con lo que `generate.py` genera.
  - `flows.yaml`, `test_kind_profile.py` (`BUDGET_GIB`) y la CA de `registry-db` en `vectra-app` (`sslmode`) **no** se tocan: se reportan.
- **Las candidatas abiertas de U03-T04**, como `backoffLimit` del CronJob o el rojo primero de `verify`, salvo que el codificador las cite como ya resueltas en su rama de origen.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/decision-registry-code-generation-plan.md`: Pasos 13 a 17, §3 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U3, §4, §5.3 (T6 frente a la admisión) y §6 (P-2, P-4, P-6).
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §3 U3, §5 (DD-3) y §6 (RL-1 a RL-5).
- `aidlc-docs/construction/decision-registry/infrastructure-design/infrastructure-design.md`: INF-U3-01 a 06, en especial la tabla de INF-U3-03 y la de INF-U3-04.
- `aidlc-docs/construction/decision-registry/infrastructure-design/deployment-architecture.md`: §2, waves.
- `aidlc-docs/construction/decision-registry/nfr-requirements/nfr-requirements.md`: NFR-U3-10, 11, 41, 42, 51 y 52.
- `aidlc-docs/construction/decision-registry/nfr-design/nfr-design-patterns.md`: P-U3-01, 04 y 08.
- `aidlc-docs/construction/platform-foundation/nfr-design/nfr-design-patterns.md`: P-U1-12.
- `aidlc-docs/construction/shared-infrastructure.md` §2.
- `aidlc-docs/inception/application-design/component-dependency.md`: F42, F44, F60, F75, F77 a F79, F96 a F99, F107, F108, F111 y F118.
- `decision-registry/`: lo que dejaron U03-T01 a U03-T04, en especial `chart/`, `Makefile`, `tests/unit/test_chart.py`, `src/vectra_registry/service.py` y `migrations/`.
- `revisiones/U03-T04/` y `CANDIDATAS.md`, entradas de U3: llaves y DSN del servicio, `sslmode`, imagen y `check-chart`.
- `platform/network/flows.yaml`, `platform/network/tests/test_flows.py` y `platform/data/chart/values.yaml` (roles y Secrets `pg-role-*`).
- `vectra-risk-gitops/components.yaml`, `vectra-risk-gitops/generate.py` y `vectra-risk-gitops/README.md`.
- `platform/tests/test_waves.py`, `platform/tests/test_kind_profile.py`, `platform/tests/integration.py`, `platform/tests/test_traceability.py` y `platform/tests/test_traceability_cli.py`.
- `platform/policies/kyverno/` (`disallow-argocd-auto-sync.yaml`, `require-hpa-bounds.yaml`, `require-spread-and-pdb.yaml`) y `platform/policies/rego/`.
- `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`: formato de un `cierre-demo.md` ya hecho.

---

## Criterios de aceptación

Todos los comandos se corren desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ningún criterio toca el clúster: las lecturas de vuelta son sobre el render, los archivos generados y el árbol de git.

- [ ] **CA-1** — Paso 13: chart y `conftest`.
  ```bash
  make -C decision-registry policy-chart && uv run pytest decision-registry/tests/unit/test_chart.py -v
  ```
  Esperado: código 0. `set.rego` (`documents-exact`) lista ahora el Deployment, el HPA, el PDB, el `Service`, el `ServiceMonitor` y el Job de migración, además de lo de U03-T04. Cada `# regla:` nueva tiene en `test_chart.py` un caso que falla con una mutación del render. Como mínimo:
  - HPA con `minReplicas` 1 o `maxReplicas` 7;
  - CPU distinta del 70 %;
  - sin `topologySpreadConstraints` por `topology.kubernetes.io/zone`;
  - sin PDB;
  - prioridad distinta de `vectra-critical`;
  - recursos distintos de INF-U3-03;
  - un DSN con clave en claro;
  - un `ServiceMonitor` que apunta a otro puerto que el de métricas;
  - un Job de migración sin hook, con otra ServiceAccount, sin `vectra.io/workload: migration-registry`, con `activeDeadlineSeconds` distinto de 600 o con una prioridad distinta de `vectra-normal`;
  - un `Job` cuyo nombre empieza por `registry-aggregator-rebuild`, `registry-aggregator-reset` o `x06-probe` → falla;
  - un `Secret` o un `ExternalSecret` → falla.

  `test_todas_las_reglas_de_las_politicas_tienen_caso` sigue en verde.

- [ ] **CA-2** — Paso 13: render por entorno, con los values que usará Argo CD (lectura de vuelta del render).
  ```bash
  for env in kind staging prod; do uv run python platform/tests/integration.py --chart decision-registry/chart --namespace vectra-app --env $env --out /tmp/u3-$env && grep -c "kind: Deployment" /tmp/u3-$env/decision-registry-$env.yaml; done
  ```
  Esperado: tres archivos, uno por entorno, con un Deployment cada uno. El nombre del archivo sale de la entrada de `components.yaml` (CA-6). En el render de kind, el HPA tiene `minReplicas: 2` y `maxReplicas: 6` (DD-3 b).

- [ ] **CA-3** — Paso 13: reglas de admisión de U1 en los **tres** entornos.
  ```bash
  make -C decision-registry policy-chart-u1
  ```
  Esperado: código 0. El target se amplía de `--env kind` a kind, staging y prod, **un entorno por directorio**, para esquivar el `panic` de Kyverno con recursos repetidos (candidata de U03-T04). Kyverno con `pass` > 0 y `fail: 0`, y `conftest` de `platform/policies/rego` (incluido `--namespace hpa`) en 0 para cada entorno.

- [ ] **CA-4** — Paso 13: flujos.
  ```bash
  uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -v \
    && for id in F42 F75 F77 F78 F79 F96 F97 F98 F99 F107 F108 F111 F118; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done \
    && grep -n 'id: F60, from: \[prometheus\], to: \["ns:vectra-app"' platform/network/flows.yaml
  ```
  Esperado: código 0 y ninguna línea «falta». La última orden imprime la fila de F60 con el puerto 8081.
  - `test_every_inventory_id_is_in_flows` cubre los IDs de `component-dependency.md`, y `test_f111_only_in_kind` cubre F111.
  - `test_prometheus_can_scrape_every_pod_of_the_namespace[vectra-app]` cubre el scrape de F60.
  - El render (CA-2) usa en el Deployment las etiquetas de `decision-registry-service`, en el CronJob las de `registry-aggregator` y en el Job las de `migration-registry` de `flows.yaml`. Una prueba de `test_chart.py` lo comprueba contra `flows.yaml`.

- [ ] **CA-5** — Paso 13: `ServiceMonitor`.
  ```bash
  helm template decision-registry decision-registry/chart | yq 'select(.kind == "ServiceMonitor") | .spec.endpoints[].port'
  ```
  Esperado: el nombre del puerto 8081 del `Service` (el mismo que declara el contenedor). Una regla de `chart/policy/` y su caso en `test_chart.py` (CA-1) lo exigen. Si `yq` no está en `platform/.tools/bin`, la bitácora deja la forma equivalente con `uv run python`.

- [ ] **CA-6** — Paso 15: Application `decision-registry` (lectura de vuelta de lo generado).
  ```bash
  uv run python vectra-risk-gitops/generate.py --check \
    && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/decision-registry.yaml; done \
    && platform/.tools/bin/kyverno test platform/policies/kyverno \
    && git ls-files --others --exclude-standard vectra-risk-gitops/apps | grep decision-registry \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/decision-registry.yaml
  ```
  Esperado: código 0.
  - Hay un `apps/<env>/decision-registry.yaml` por entorno, con `argocd.argoproj.io/sync-wave: "5"` y sin `syncPolicy.automated`.
  - Kyverno da `pass` y `fail: 0`.
  - `vectra-risk-gitops/apps/*/decision-registry-rebuild.yaml` no existe (diferido).

- [ ] **CA-7** — Paso 15: el render de `decision-registry` no contiene los Jobs de reconstrucción ni `x06-probe`, y el Job de migración es un hook.
  ```bash
  for env in kind staging prod; do f=/tmp/u3-$env/decision-registry-$env.yaml; ! grep -nE "name: (registry-aggregator-(rebuild|reset)|x06-probe)" $f && grep -n "argocd.argoproj.io/hook" $f; done
  ```
  Esperado: ninguna línea de los Jobs de reconstrucción ni de `x06-probe`, y una línea de hook por entorno (la del Job de migración). Usa los archivos de CA-2.

- [ ] **CA-8** — Paso 16: cobertura de ramas.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest decision-registry/tests --cov=vectra_registry --cov-branch --cov-fail-under=95 \
    && uv run coverage report --include="*/vectra_registry/chain.py,*/vectra_registry/verify.py,*/vectra_registry/append.py" --fail-under=100
  ```
  Esperado: código 0. El informe lista los módulos de `vectra_registry`, no los de `vectra_contracts` ni `vectra_common`.
  - El `--cov` sin argumento del plan mide el `source` de la raíz (`[tool.coverage.run]` de `vectra-risk/pyproject.toml`: solo U0). Por eso el comando nombra `vectra_registry`.
  - Si el codificador prefiere configurar el `source` para que la forma del plan mida U3, cuenta lo mismo: lo deja en la bitácora.
  - Los dos comandos quedan en el `check` de `decision-registry/Makefile`, con el mismo patrón que `reference-model/Makefile`.

- [ ] **CA-9** — Paso 16: trazabilidad de los identificadores, con la lista de diferidos (P-4).
  ```bash
  uv run python platform/tests/test_traceability.py --unit decision-registry --all \
    && uv run pytest platform/tests/test_traceability_cli.py -v \
    && uv run python platform/tests/test_traceability.py --all
  ```
  Esperado: código 0 en las tres.
  - `test_traceability_cli.py` tiene un caso nuevo: un identificador sin código pero en la lista «Diferido por la demo» de `evidence/cierre-demo.md` pasa, y otro que no está en la lista falla.
  - La tercera orden muestra que el cambio no rompe las otras unidades.
  - Lectura de vuelta: `grep -n "Diferido por la demo" -A40 aidlc-docs/construction/decision-registry/evidence/cierre-demo.md` muestra cada identificador con su paso y su cita de recorte, y ninguno de los Pasos 13, 15 o 16.

- [ ] **CA-10** — Paso 16: cada BR-U3 tiene una prueba.
  ```bash
  for n in 01 02 03 04 05 06 07 08 09 10 11 12 13 13b 14 15 16 17; do git grep -qiE "BR-U3-$n([^0-9a-z]|$)|br_u3_${n}([^0-9a-z]|$)" -- decision-registry/tests || echo "BR-U3-$n sin prueba"; done
  ```
  Esperado: ninguna línea. `test_traceability.py` no ve las BR-U3, porque están en párrafos en negrita (candidata de U03-T02). Esta orden es la comprobación del plan, «trazabilidad de cada BR-U3 a una prueba».

- [ ] **CA-11** — `check` de U3 y de U1 (RL-4).
  ```bash
  make -C decision-registry check && make -C platform check
  ```
  Esperado: código 0 en los dos. `check` de U3 incluye ahora la cobertura (CA-8) y la admisión en los tres entornos (CA-3).
  - Si `make -C platform check` falla **solo** en `test_kind_profile.py::test_the_profile_requests_fit_the_budget`, aplica la nota del presupuesto de kind: es una detención, no un ROJO del codificador.

- [ ] **CA-12** — Estado del plan (lectura de vuelta con git).
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/decision-registry-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso 1[3-7]"
  ```
  Esperado:
  - Pasos 13, 15 y 16: `[x] (U03-T05, acotado a la demo)`.
  - Pasos 14 y 17: siguen `[ ]`, con la nota «diferido por la demo» (alcance §2.3).
  - Ningún otro cambio en el texto del plan.

- [ ] **CA-13** — Imagen de `decision-registry` (agregado al Paso 13 por decisión del usuario; T1).
  ```bash
  make -C decision-registry image
  docker run --rm --entrypoint vectra-registry localhost:5001/vectra/decision-registry:dev --help
  docker image inspect localhost:5001/vectra/decision-registry:dev --format '{{.Config.User}}'
  docker run --rm --entrypoint sh localhost:5001/vectra/decision-registry:dev -c 'python -c "import vectra_registry, vectra_common" && ! python -c "import pytest" 2>/dev/null && echo OK-runtime'
  grep -nE '^FROM .*@sha256:[0-9a-f]{64}' decision-registry/Dockerfile
  ```
  Esperado:
  - El build termina en 0.
  - `--help` lista los subcomandos de `vectra-registry`.
  - El usuario es `65532:65532`.
  - Se imprime `OK-runtime`: el runtime importa y no hay dependencias de desarrollo.
  - Cada `FROM` está fijado por digest.

---

## Plan de pruebas

**Rojo primero**, con una mutación por regla. Cada par falla-pasa queda en `bitacoras/U03-T05.md`. Como mínimo:

- `minReplicas: 1` en el HPA;
- quitar el PDB;
- `vectra-high` en el Deployment;
- una contraseña en `REGISTRY_RW_APP_DSN`;
- el `ServiceMonitor` apuntando a `8080`;
- el Job de migración sin la anotación de hook o con la ServiceAccount `decision-registry-service`;
- un `Job` `x06-probe` en el render;
- `syncPolicy.automated` en `apps/kind/decision-registry.yaml` (Kyverno falla);
- `wave: 4` en la entrada de `components.yaml` (`test_waves.py` falla por `FIXED_WAVES`);
- un identificador del Paso 13 en la lista de diferidos, o uno diferido fuera de ella (`test_traceability.py` falla);
- borrar una rama de `chain.py` de las pruebas (el umbral del 100 % falla).

Pruebas que se escriben en esta tarea:

- `decision-registry/tests/unit/test_chart.py`: casos nuevos por regla, y que las etiquetas coincidan con `flows.yaml`.
- `platform/tests/test_traceability_cli.py`: la lista de diferidos.
- Las pruebas que falten para el 100 % de ramas en `chain`, `verify` y `append`, y para el 95 % global. Primero se corre la cobertura y se registra el porcentaje de partida.

---

## Notas

- **Archivos que se modifican en su sitio:**
  - `decision-registry/chart/` (`Chart.yaml`, `values.yaml`, `templates/`, `policy/`);
  - `decision-registry/Makefile`;
  - `decision-registry/tests/`;
  - `vectra-risk-gitops/components.yaml` y lo que `generate.py` escribe en `apps/`;
  - `platform/tests/test_traceability.py` y `platform/tests/test_traceability_cli.py` (P-4);
  - el plan de U3 (CA-12);
  - `CANDIDATAS.md`.

  Archivo nuevo: `aidlc-docs/construction/decision-registry/evidence/cierre-demo.md`, solo con la sección «Diferido por la demo». Nada de duplicados con sufijo.
- **Presupuesto de memoria de kind (detención con reporte):**
  - `test_kind_profile.py` tiene `BUDGET_GIB = 5.5`, un valor provisional que decidió el usuario hasta la medición DD-3 del Paso 16 de U2, que no está registrada. U1 + U2 ya piden 5,47 GiB.
  - Al entrar `decision-registry` en `components.yaml`, su Deployment (≥ 256 MiB + 20 MiB de proxy por réplica) lo pasa.
  - Si CA-11 falla por eso, **detente en ese punto y repórtalo**, con la cifra y las opciones:
    - subir el tope provisional;
    - la opción a de DD-3 (`values-kind-demo.yaml`, que choca con `require-hpa-bounds`; enmienda §5.3);
    - otra que veas.
  - **No cambies `BUDGET_GIB` ni el perfil por tu cuenta.** Lo decide el usuario. El resto de la tarea sigue.
- **Huella y llaves públicas de checkpoints:**
  - El Job de migración necesita `REGISTRY_CHECKPOINT_KEY_FINGERPRINT` para la génesis (BR-U3-10; candidata de U03-T01).
  - El servicio necesita `REGISTRY_CHECKPOINT_PUBLIC_KEYS` (candidata de U03-T03).
  - La URL de Transit y la firma se difieren, así que los dos entran como **values** que el chart pone en un ConfigMap, con `required`, sin leer la bóveda. El valor de kind lo fija el Bloque H. Aquí basta un valor de ejemplo, como el digest de ejemplo de la imagen.
  - Si el diseño exige otra fuente, repórtalo.
- **Imagen:** decisión del usuario del 2026-11-09. Entra en esta tarea (ver «Agregado al plan» en Alcance). Al terminar, marca como resuelta la candidata de U03-T04 sobre la imagen en `CANDIDATAS.md`, dejando el push y el digest para el Bloque H.
- **`sslmode`:** sigue en `require` (candidata de U03-T04, la CA de `registry-db` en `vectra-app`). No lo cambies sin esa CA.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades. El orquestador nombra en el despacho cuáles están activos.
- **Bitácora:** `bitacoras/U03-T05.md`. Registra:
  - la cobertura de partida y la final;
  - la lista de diferidos y la razón de cada uno;
  - los pares falla-pasa;
  - la cifra de memoria de kind con y sin `decision-registry`.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
