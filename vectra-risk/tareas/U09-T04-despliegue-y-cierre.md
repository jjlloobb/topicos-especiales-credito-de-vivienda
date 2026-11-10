# U09-T04 — Imagen, chart, Application, trazabilidad y cierre acotado de `bias-monitoring`

**Unidad:** U9 `bias-monitoring`
**Historias que implementa:** ninguna nueva. Empaqueta, despliega por GitOps y cierra lo que implementan los Pasos 1 a 10. El chart sostiene la parte de despliegue de US-303 y US-308: el CronJob es el único que congela, con su identidad y su horario.
**Depende de:**
- U09-T03, el servicio HTTP con `vectra_bias.app` y `services.md`, fusionado en `main`. Hoy está en revisión, en la rama `tarea/U09-T03`;
- en `main`, como contratos: U1 (`flows.yaml`, `forbidden.yaml`, cuotas, `require-hpa-bounds` con exención, sidecar nativo, `check-chart`), U2 (clientes `bias-monitoring-service` y `bias-monitoring-job` del realm y `identity/clients/<id>` en la bóveda de kind), U3 (Service `decision-registry-service`, F26) y U4 (Service `governance-service` con la ruta `freeze`, F27; `biasUrl` en `governance/chart/values.yaml`, F25).

**Se despacha** cuando U09-T03 esté fusionada en `main`.
**Rama:** `tarea/U09-T04`, desde `origin/main`.

Bloque E del plan de U9 (`aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md`) más el cierre: la tarea «E+cierre (11, 12, 14, 17, 18)» de `demo-recorte-funcional.md` §8. La verificación en kind (Paso 16) se consolida en U12 (enmienda §8). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 11 Dockerfile y cadena de suministro | **E\*F** | Entran una imagen con los dos puntos de entrada, base por digest, `runAsNonRoot`, `readOnlyRootFilesystem`, sin numpy, scipy, pandas, Fairlearn ni scikit-learn, y `hadolint`. Se difieren la firma, el SBOM y el escaneo (T1). «Sin numpy» se comprueba con `pip list` en la imagen, no en el SBOM | Enmienda §3 U9, fila 11; alcance §3 U9; T1 |
| 12 Chart, parámetros, cuota y flujos | **E\*** | Completo, con el perfil de DD-3 b: values de kind existentes y 2 réplicas fijas. Se difieren el Job `x04-probe-<runId>`, su `conftest` y sus fixtures de `probes.runId` (T5) | Enmienda §3 U9, fila 12; alcance §3 U9; T5, T6; DD-3 |
| 13 Alertas, runbooks y dashboard | **D** | Entero fuera | T2; enmienda §3 U9, fila «13 · 15» |
| 14 Applications, carga y trazabilidad | **E\*** | Entran la Application (wave 5) y la trazabilidad de cada BR-U9 a una prueba, con la lista de diferidos. Se difieren el script k6 y su `k6 inspect` | Enmienda §3 U9, fila 14; T3; P-4 |
| 15 Workflow de CI | **D** | Entero fuera | T4; enmienda §3 U9, fila «13 · 15» |
| 16 Verificación en kind | — | Queda `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». Sus escenarios de demo (1, 3 con una medición y 5) los cubre U12 | Enmienda §3 U9, fila 16, y §8 |
| 17 Repositorio, migraciones y frontend: N/A | **N/A** | — | — |
| 18 Cierre de la unidad | **E\*** | Cierre acotado, con `evidence/cierre-demo.md` | Enmienda §3 U9, fila «17 · 18», y §8; alcance §2.4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

**Lección de U04-T06 y U04-T08** (`revisiones/U04-T06/ronda-1.md`, F-01; `revisiones/U04-T08/`): un chart que renderiza bien no prueba que el contenedor arranque. El pod de governance no arrancaba porque nada lo ejecutaba con sus variables reales, y después le faltaba la identidad del servicio (`ExternalSecret` con la llave `private_key_jwt`). Aquí el contenedor real arranca con las variables **que pone el chart**, y la identidad de los dos procesos llega por el chart (CA-3 y CA-4).

---

## Alcance

**Dentro:** los Pasos 11, 12, 14, 17 y 18 del plan, con su texto y su aceptación, salvo lo que se difiere arriba. Léelos allí. Precisiones:

### Paso 11 — Imagen (E\*F)

- `bias-monitoring/Dockerfile`, multi-stage, como `decision-registry/Dockerfile`, con contexto en la raíz de `vectra-risk/`:
  - base Python oficial, con cada `FROM` fijado por digest;
  - usuario `65532:65532`, el mismo `runAsUser` y `runAsGroup` del chart;
  - solo el runtime de `vectra_bias`, `vectra_disparity` y sus dependencias del workspace (U0), sin dependencias de desarrollo;
  - **una imagen con dos puntos de entrada** (P-U9-05): `python -m vectra_bias.app` para el servicio y `python -m vectra_bias.run` para el CronJob. El chart elige con `command` o `args`.
- Target `image` en `bias-monitoring/Makefile`, con el tag `localhost:5001/vectra/bias-monitoring:dev`.
- El push a `kind-registry` y el digest real los hace el operador en la verificación consolidada de U12 Paso 18 (enmienda §8). Deja los comandos (build, push, digest y el PR de values de kind) en `bias-monitoring/docs/imagenes.md`, sin ejecutarlos, como `scoring-explainability/docs/imagenes.md` (U07-T04). Sin firma ni SBOM (T1) y sin workflow nuevo (T4).
- Diseño: P-U9-05; NFR-U9-54.

### Paso 12 — Chart, parámetros, cuota y flujos (E\*)

- `bias-monitoring/chart/`. Hoy solo existe `values-monitoring-policy.yaml`.
- **Servicio** (INF-U9-01):
  - `Deployment` de 2 réplicas fijas, con la anotación `vectra.io/hpa-exempt`, `maxSurge: 1` y `maxUnavailable: 0`;
  - `Service` `bias-monitoring-service` con 8080 y 8081, porque F14 y F25 llegan a él;
  - `PodDisruptionBudget` `minAvailable: 1`, spread por zona y `vectra-normal`;
  - requests de 100m / 128 MiB y limits de 500m / 256 MiB;
  - readiness `/readyz` y liveness en 8081 (NFR-U9-12);
  - `ServiceAccount` `bias-monitoring-service`, su `ExternalSecret` y su `ServiceMonitor` (8081, F60);
  - `lifecycle.preStop.sleep.seconds: 5`, como dejó dicho U09-T03 («el `preStop` de 5 s es un campo del `Deployment`: va con el chart»).
  - **El nombre y el puerto del Service** son los que ya usa governance: `biasUrl: http://bias-monitoring-service.vectra-app.svc.cluster.local:8080` en `governance/chart/values.yaml` (candidata de U04-T08 en `CANDIDATAS.md`).
- **CronJob** (INF-U9-02):
  - `schedule` tomado de `values-monitoring-policy.yaml` y nunca escrito en la plantilla, con `timeZone: Etc/UTC`;
  - `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 300`, `backoffLimit: 0`, `activeDeadlineSeconds: 600`, `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 3` y `vectra-high`;
  - anotación explícita del sidecar nativo de Linkerd (P-U1-05);
  - etiqueta `vectra.io/workload: bias-monitoring-job` en los pods, la que seleccionan F27 y F50;
  - `ServiceAccount` `bias-monitoring-job` y su `ExternalSecret`;
  - requests de 100m / 128 MiB y limits de 500m / 256 MiB.
  - **`activeDeadlineSeconds`** sale de la misma fuente que `config.ACTIVE_DEADLINE_SECONDS` de U9, o una prueba compara los dos. Es la candidata de U09-T01 F-04 en `CANDIDATAS.md`.
- **Identidad de los dos procesos** (INF-U9-04; lección de U04-T08):
  - un `ExternalSecret` por proceso, desde `identity/clients/bias-monitoring-service` e `identity/clients/bias-monitoring-job` (propiedad `private-key`), con el formato de `governance/chart/templates/service-identity.yaml`, montado de solo lectura;
  - las variables del `Deployment` son **exactamente** `vectra_bias.app.REQUIRED`, más las opcionales que use: `VECTRA_REGISTRY_URL`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_ID`, `VECTRA_CLIENT_KEY_PATH`, `VECTRA_OIDC_ISSUER` y `VECTRA_JWKS_URL`. `app.py` dice que «U09-T04 compara los nombres»;
  - las del CronJob son las que lee `vectra_bias.run.build_deps` y el proveedor de token de U0: `VECTRA_REGISTRY_URL`, `VECTRA_GOVERNANCE_URL`, `VECTRA_PUSHGATEWAY_URL`, `VECTRA_POLICY_PATH`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_ID` y `VECTRA_CLIENT_KEY_PATH`;
  - ninguna con un valor por omisión incrustado en la plantilla: salen de values con `required`;
  - **ninguna constante del código** (timeouts, reintentos, caché, razón de inválidas, atraso máximo) aparece como variable de entorno (INF-U9-03).
- **`values-monitoring-policy.yaml`** (INF-U9-03; BR-U9-13):
  - el chart lo monta como `ConfigMap` en la ruta de `VECTRA_POLICY_PATH` del CronJob y, si el servicio lo lee, también en el servicio;
  - regla de `conftest` con los rangos de INF-U9-03: umbral de 1 a 20 pp, `n_min` ≥ 30, ventana de 7 a 90 días, W ≥ 30 min, horario con intervalo de 5, 10 o 15 min y desfase de 1 a 4 min, W ≥ 4 × el intervalo, y `activeDeadlineSeconds` ≤ el intervalo en segundos;
  - **`CODEOWNERS`**: ver P-1.
- **Cuota** (INF-U9-01): el aporte de U9 ya está en `platform/policies/quotas/quotas.yaml` (`U9: { requests: [1.04, 0.75], limits: [5.2, 1.95] }`). Comprueba que coincide con INF-U9-01 y que el render cabe. El plan dice `conftest test platform/policies/quotas/`, pero en el repositorio esa comprobación es `platform/policies/quotas/render.py --check` y `test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota`. Usa esas y regístralo, como U07-T04. Si el aporte no coincide, **repórtalo**: no edites U1.
- **Flujos** (INF-U9-04): verifica que F14, F25, F26, F27 (solo desde `bias-monitoring-job`), F50, F60 y F106 están en `platform/network/flows.yaml`, sin flujos nuevos, y que `forbidden.yaml` sigue negando servicio → Pushgateway. El caso `x04-probe` → Keycloak se difiere con el probe (T5). Si algo falta, **repórtalo**: no edites U1.
- **Perfil demo (T6):** DD-3 b. Sin `values-kind-demo.yaml`; los values de kind mantienen las 2 réplicas fijas.
- Reglas de admisión del plan: imagen por digest (de ejemplo, como los otros charts), `runAsNonRoot`, `readOnlyRootFilesystem` con `emptyDir` si algo escribe en disco, sin `privileged` ni `hostPath`, recursos, `priorityClassName`, `vectra.io/criticality`, 2 réplicas o más, spread, PDB por `app.kubernetes.io/name` y HPA o `vectra.io/hpa-exempt` (`aidlc-docs/construction/shared-infrastructure.md` §2).
- `bias-monitoring/policies/conftest/` con las reglas del plan. Cada regla tiene un caso que falla con una mutación del render.
- Diseño: INF-U9-01 a 04; NFR-U9-10, 11, 12, 13, 30, 34; BR-U9-13; P-U9-05.

### Presupuesto de memoria de kind (`DECISIONES-LOOP.md` §7)

- U9 pide en kind 2 réplicas × (128 + 20) MiB ≈ **0,29 GiB** de Deployment. El CronJob no cuenta: `requested_gib()` suma `Deployment` y `StatefulSet`.
- Con la Application de U9 en `components.yaml`, `test_kind_profile.py::test_the_profile_requests_fit_the_budget` puede fallar con el tope actual. Si falla, esta tarea **sube `BUDGET_GIB`** a la cifra que dé `requested_gib()` con U9 incluida, redondeada hacia arriba a 0,1 GiB, con el comentario de la decisión (§7: «se vuelve a revisar con cada unidad nueva»).
- **Umbral de detención:** el `BUDGET_GIB` de `main` en la base de la rama + 0,29 + 0,2 GiB. **Si la cifra medida pasa del umbral, detente y repórtalo** con la cifra, el desglose por unidad y las opciones. No cambies los requests de U9 por tu cuenta.

### Paso 14 — Application y trazabilidad (E\*)

- Entrada `bias-monitoring` en `vectra-risk-gitops/components.yaml`: `wave: 5`, `namespace: vectra-app`, `path: bias-monitoring/chart`, `env_values: true` y `values: [bias-monitoring/chart/values-monitoring-policy.yaml]`. `generate.py` escribe una Application por entorno, sin `syncPolicy.automated`.
- **Trazabilidad (P-4).** `test_traceability.py --unit bias-monitoring --all` termina en 0 con la lista «Diferido por la demo» de `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md`:
  - cada fila lleva el identificador, el paso que lo implementaría y la cita del recorte (T1, T2, T3, T4, T5, §3 o §8 de la enmienda);
  - solo entran identificadores de partes diferidas:
    - lo del Paso 13 (T2) y del Paso 15 (T4);
    - `mutmut` de los Pasos 5 y 10 (NFR-U9-51, T3; candidata de U09-T01 ronda 4);
    - la carga del Paso 14 (NFR-U9-02, T3);
    - `x04-probe` (T5);
    - lo que solo verifica el Paso 16 (consolidado en U12, §8);
  - los identificadores de los Pasos 1 a 12 que entran se trazan en el código o en las pruebas, no en la lista;
  - el codificador corre primero la prueba, registra qué identificadores marca y justifica cada uno.
- `test_traceability.py` no ve las BR en párrafos en negrita (candidata de U03-T02). Por eso hay además un `git grep` por cada BR-U9 (CA-7), como en U3 y U7.
- Diseño: P-U1-12; NFR-U9-02. Su medición con carga se difiere con k6 (T3).

### Paso 16 — Consolidado en U12

- Queda `[ ]` en el plan con la nota «consolidado en U12 Paso 18 (enmienda §8)». Esta tarea no lleva guía de kind.

### Paso 17 — N/A

- U9 no tiene base de datos, migraciones ni interfaz.

### Paso 18 — Cierre acotado (E\*)

- `make -C bias-monitoring check` corre en orden las verificaciones estáticas, las propiedades, la simulación y las pruebas de integración de los Pasos 1 a 14 que entran, incluidos el chart (CA-3) y la admisión (CA-5), y termina en 0.
- `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md` completo, con el formato de `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md` (U07-T04) o, si U07-T04 no está fusionada, el de `aidlc-docs/construction/model-serving/evidence/cierre-demo.md`:
  - **Comprobado:** cada paso que entra, con su comando y su resultado;
  - **Diferido por la demo:** la lista de P-4, más los Pasos 13 (T2) y 15 (T4), `mutmut` (T3), k6 (T3), firma, SBOM y escaneo (T1), `x04-probe` (T5) y los escenarios 2 y 4 y E1–E5 y E7 del Paso 16, cada uno con su destino;
  - **Pendiente en U12:** los escenarios 1 (conectividad), 3 (RT-2 con una medición, DD-1) y 5 (duración y pico de memoria de una corrida, NFR-U9-04 y DD-3) del Paso 16, más el push de la imagen, que verifica U12 Paso 18 (enmienda §8);
  - la decisión de P-2 (PBT-U9-05), con las cifras medidas.
- RL-4: al cerrar la unidad, el `make check` de todas las unidades corre una vez (CA-11).

### Plan

- Pasos 11 y 12: `[x] (U09-T04, acotado a la demo)`. Paso 14: `[x] (U09-T04, acotado a la demo)`. Paso 17: `[x] (U09-T04)`. Paso 18: `[x] (U09-T04, acotado a la demo)`.
- Pasos 13 y 15: `[ ]` con «diferido por la demo (T2)» y «diferido por la demo (T4)».
- Paso 16: `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».

**Fuera** (rechazar aunque se vea roto o tentador):

- El Paso 13 completo: `PrometheusRule`, las cuatro alertas de P-U9-06, sus runbooks, `promtool`, `test_runbooks.py --root bias-monitoring` y `observability/dashboards/bias.json` (T2; la vista de sesgo la da la consola, U10 Paso 14).
- El Paso 15 completo: `.github/workflows/bias-monitoring.yml`, la regla de rutas y el nocturno (T4).
- Firma, SBOM, escaneo, `sign-image.yml` y `supply-chain.yml` (T1).
- `tests/load/dashboard.js` y `k6 inspect` (T3).
- El Job `x04-probe-<runId>`, `probes.runId`, sus fixtures de staging y prod, y el caso de conectividad `x04-probe` → Keycloak (T5).
- Guía, scripts y escenarios de kind (Paso 16): van en U12 (enmienda §8).
- Push de la imagen, digest real y cualquier `kubectl`, `helm install`, `argocd` o sync (AUTONOMIA-01).
- `values-kind-demo.yaml` o 1 réplica (DD-3 eligió la b).
- Cambios en U0, U3 y U4. En U1, solo `BUDGET_GIB` y su comentario en `platform/tests/test_kind_profile.py`, lo que `generate.py` genera y, según P-1, `.github/CODEOWNERS`.
- Cambios de comportamiento en `vectra_bias` o `vectra_disparity`. Si el chart revela un defecto del código de U09-T02 o U09-T03, **repórtalo** y no lo arregles aquí, salvo P-2.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md`: §1, Pasos 11 a 18, §3, §4 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U9, §5.3 (T6 frente a la admisión), §6 (P-4, P-14) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §3 U9, §5 (DD-1, DD-3) y §6.
- `DECISIONES-LOOP.md` §6, §7 y §8.
- `aidlc-docs/construction/bias-monitoring/infrastructure-design/` (INF-U9-01 a 05 y `deployment-architecture.md`) y `nfr-design/nfr-design-patterns.md` (P-U9-02, 05).
- `aidlc-docs/construction/bias-monitoring/code/library.md` y `code/services.md` (U09-T03).
- `bias-monitoring/src/vectra_bias/app.py` (`REQUIRED`, `OPTIONAL`, `main`), `run.py` (`build_deps`, `main`), `config.py` (`POLICY_PATH`, `ACTIVE_DEADLINE_SECONDS`) y `tests/integration/test_entrypoint.py` (U09-T03: arranca el proceso real contra dobles HTTP).
- `aidlc-docs/construction/shared-infrastructure.md` §2.
- `decision-registry/Dockerfile`, `decision-registry/chart/` (CronJob del agregador con sidecar nativo) y `decision-registry/Makefile` (`policy-chart-u1`); `governance/chart/` (`service-identity.yaml`, `values.yaml` con `biasUrl`) y `governance/Makefile`.
- `tareas/U03-T05-despliegue-y-calidad.md`, `tareas/U04-T06-despliegue-y-calidad.md`, `tareas/U04-T08-punto-de-entrada-del-servicio.md` y `tareas/U07-T04-despliegue-y-cierre.md`: la misma tarea hecha para U3, U4 y U7.
- `platform/network/flows.yaml`, `platform/network/forbidden.yaml`, `platform/policies/quotas/quotas.yaml` y `render.py`, `platform/policies/kyverno/` y `platform/policies/rego/`.
- `platform/kind/vault_paths.py` (`service_account_clients()`), `identity-edge/keycloak/realm/realm.kind.yaml` (clientes `bias-monitoring-service` y `bias-monitoring-job`).
- `vectra-risk-gitops/components.yaml`, `generate.py` y `README.md`; `platform/tests/test_waves.py`, `test_kind_profile.py`, `test_integration.py`, `integration.py`, `test_traceability.py` y `test_traceability_cli.py`.
- `.github/CODEOWNERS`.
- `CANDIDATAS.md`: el pánico de Kyverno en `check-chart` (U03-T04 y U04-T05), la trazabilidad de BR en negrita (U03-T02), U9 `ACTIVE_DEADLINE_SECONDS` (U09-T01 F-04), NFR-U9-51 en diferidos (U09-T01 ronda 4), PBT-U9-05 (U09-T02 F-01) y el Service de F25 (U04-T08).

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 11: imagen.
  ```bash
  platform/.tools/bin/hadolint bias-monitoring/Dockerfile
  make -C bias-monitoring image
  docker image inspect localhost:5001/vectra/bias-monitoring:dev --format '{{.Config.User}}'
  docker run --rm --entrypoint sh localhost:5001/vectra/bias-monitoring:dev -c '! pip list 2>/dev/null | grep -iE "^(numpy|scipy|pandas|fairlearn|scikit-learn|pytest|hypothesis) " && echo OK'
  docker run --rm --entrypoint python localhost:5001/vectra/bias-monitoring:dev -c 'import vectra_bias.app, vectra_bias.run, vectra_disparity; print("OK-entradas")'
  grep -nE '^FROM .*@sha256:[0-9a-f]{64}' bias-monitoring/Dockerfile
  ```
  Esperado: `hadolint` en 0, usuario `65532:65532`, `OK`, `OK-entradas` y cada `FROM` por digest. Si `hadolint` no está en `platform/.tools/bin` del worktree, usa el del checkout principal tras comparar la versión con `tools.env`.

- [ ] **CA-2** — Paso 12: render, esquema y `conftest` del chart.
  ```bash
  for env in kind staging prod; do uv run python platform/tests/integration.py --chart bias-monitoring/chart --namespace vectra-app --env $env --out /tmp/u9-$env; done
  for env in kind staging prod; do platform/.tools/bin/kubeconform -strict -summary -schema-location default -schema-location 'bias-monitoring/tests/fixtures/crds/{{.ResourceKind}}.json' /tmp/u9-$env/*.yaml; done
  for env in kind staging prod; do platform/.tools/bin/conftest test --policy bias-monitoring/policies/conftest /tmp/u9-$env/*.yaml; done
  uv run pytest bias-monitoring/tests/unit/test_chart.py -v
  ```
  Esperado: código 0. Los CRD de `ExternalSecret` y `ServiceMonitor` se guardan como fixture, con su fuente en la bitácora. `test_chart.py` tiene un caso por regla que falla con una mutación. Como mínimo:
  - réplicas del servicio distintas de 2, o sin `vectra.io/hpa-exempt`;
  - sin PDB, o sin spread;
  - `priorityClassName` cambiado: servicio distinto de `vectra-normal` o CronJob distinto de `vectra-high`;
  - recursos distintos de INF-U9-01;
  - sin `preStop.sleep` de 5 s;
  - `schedule` escrito en la plantilla en vez de salir de `values-monitoring-policy.yaml`;
  - `concurrencyPolicy` distinto de `Forbid`, `backoffLimit` ≠ 0, `startingDeadlineSeconds` ≠ 300 o `activeDeadlineSeconds` ≠ 600;
  - sin la anotación del sidecar nativo;
  - pods del CronJob sin `vectra.io/workload: bias-monitoring-job`;
  - un `Secret` en el render;
  - una constante del código como variable de entorno (por ejemplo `CACHE_TTL_SECONDS`);
  - fixtures de `values-monitoring-policy.yaml` fuera de rango: umbral 0 y 21, `n_min` 29, ventana 6 y 91, W de 20 min, intervalos de 6 y 12 min, desfase 0, W < 4 × intervalo, y 5 min con `activeDeadlineSeconds: 600`. Cada uno falla, y los valores actuales pasan;
  - un `x04-probe` en el render, que no debe aparecer con ningún values (T5).

- [ ] **CA-3** — Paso 12: identidad y variables de los dos procesos (lección de U04-T08).
  ```bash
  uv run pytest bias-monitoring/tests/unit/test_chart.py -k "identity or env" -v
  uv run python -c "import sys; sys.path.insert(0, 'platform/kind'); import vault_paths as v; c = v.service_account_clients(); assert {'bias-monitoring-service', 'bias-monitoring-job'} <= set(c), c; print('OK-boveda')"
  grep -nE "clientId: bias-monitoring-(service|job)$" identity-edge/keycloak/realm/realm.kind.yaml
  ```
  Esperado: código 0 y `OK-boveda`. Las pruebas comprueban sobre el render de los tres entornos:
  - el conjunto de variables del contenedor del `Deployment` contiene `vectra_bias.app.REQUIRED`, importado del código y no copiado; las del CronJob contienen las que lee `vectra_bias.run.build_deps` y el proveedor de token de U0;
  - `VECTRA_CLIENT_ID` vale `bias-monitoring-service` en el servicio y `bias-monitoring-job` en el CronJob;
  - `VECTRA_CLIENT_KEY_PATH` apunta a un archivo del volumen del `ExternalSecret` de su proceso, montado de solo lectura;
  - cada `ExternalSecret` lee `identity/clients/<su cliente>`, propiedad `private-key`;
  - `VECTRA_POLICY_PATH` apunta al `ConfigMap` de `values-monitoring-policy.yaml`;
  - el CronJob usa la `ServiceAccount` `bias-monitoring-job` y el servicio la `bias-monitoring-service`;
  - el `Service` se llama `bias-monitoring-service` y expone 8080, y coincide con `biasUrl` de `governance/chart/values.yaml` (F25), leído del archivo;
  - `activeDeadlineSeconds` del CronJob es igual a `vectra_bias.config.ACTIVE_DEADLINE_SECONDS`.

  Rojo de cada caso en la bitácora: quitar una variable de `REQUIRED` del chart, cambiar el `clientId`, montar la llave sin `readOnly`, renombrar el Service a `bias-monitoring`.

- [ ] **CA-4** — Paso 11 y 12: el contenedor real arranca con las variables que pone el chart.
  ```bash
  uv run pytest bias-monitoring/tests/integration/test_image.py -v
  ```
  Esperado: código 0. La prueba toma las variables y la política del render de kind (CA-2). Solo cambia las URLs por las de dobles HTTP locales del registro, de Keycloak (`/token` y JWKS), de governance y del Pushgateway (`tests/doubles/`, U09-T03), y la llave por una de prueba en el mismo path. Luego corre la imagen de CA-1 con `docker run` y la raíz de solo lectura:
  - con `python -m vectra_bias.app`, `GET /readyz` en 8081 responde 200, y `GET /v1/freezes` en 8080, con un token del doble, responde según el contrato de U0;
  - con `python -m vectra_bias.run`, la corrida termina con el código de salida de una corrida completa contra los dobles y empuja sus métricas al doble del Pushgateway;
  - sin `VECTRA_REGISTRY_URL`, el servicio no arranca y el log nombra la variable, nunca su valor.

  Si Docker no está disponible, la prueba **falla**; no se salta. Registra en la bitácora el `docker run` exacto y su salida.

- [ ] **CA-5** — Paso 12: admisión de U1 en los tres entornos.
  ```bash
  make -C platform check-chart CHART=bias-monitoring/chart NAMESPACE=vectra-app
  ```
  Esperado: código 0, Kyverno con `fail: 0`, `require-hpa-bounds` admite la exención, y `conftest` de `platform/policies/rego` (incluido `--namespace hpa`) en 0. Si Kyverno entra en pánico por recursos repetidos entre entornos (candidata de U03-T04 y U04-T05), agrega un target `policy-chart-u1` en `bias-monitoring/Makefile` con un entorno por directorio, como `decision-registry/Makefile`, y regístralo.

- [ ] **CA-6** — Paso 12: cuota, flujos y `CODEOWNERS`.
  ```bash
  uv run python platform/policies/quotas/render.py --check \
    && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -v \
    && uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -v \
    && for id in F14 F25 F26 F27 F50 F60 F106; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done \
    && grep -nE "id: F27, from: \[bias-monitoring-job\]," platform/network/flows.yaml \
    && grep -nE "from: bias-monitoring-service, to: pushgateway" platform/network/forbidden.yaml
  uv run pytest bias-monitoring/tests/unit/test_chart.py -k "codeowners or flows" -v
  ```
  Esperado: código 0, ninguna línea «falta» y las dos líneas encontradas. Una prueba de `test_chart.py` compara las etiquetas y `ServiceAccount` del render con `flows.yaml`. Otra comprueba que una regla de `.github/CODEOWNERS` cubre `vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml`, según P-1.

- [ ] **CA-7** — Paso 14: Application y trazabilidad (P-4).
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/bias-monitoring.yaml; done \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/bias-monitoring.yaml \
    && grep -n "values-monitoring-policy.yaml" vectra-risk-gitops/apps/*/bias-monitoring.yaml
  uv run python platform/tests/test_traceability.py --unit bias-monitoring --all \
    && for n in $(seq -w 1 22); do git grep -qiE "BR-U9-$n([^0-9]|$)" -- bias-monitoring/tests || echo "BR-U9-$n sin prueba"; done
  grep -n "Diferido por la demo" -A40 aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md
  ```
  Esperado: código 0 y ninguna línea «sin prueba». Hay una Application por entorno, con wave `"5"`, sin `syncPolicy.automated` y con `values-monitoring-policy.yaml` en sus `valueFiles`. `--all` cumple la regla de `DECISIONES-LOOP.md` §6 con su enmienda. NFR-U9-51 está en la lista. La lista no contiene identificadores de los Pasos 1 a 12 que entran. Si una BR-U9 solo la cubre una parte diferida (por ejemplo BR-U9-21 y 22, del Paso 13), va en la lista con su cita y se excluye del `git grep` en la bitácora, con el porqué.

- [ ] **CA-8** — Presupuesto de kind.
  ```bash
  uv run pytest platform/tests/test_kind_profile.py -v
  git diff origin/main -- platform/tests/test_kind_profile.py
  ```
  Esperado: código 0. Si el diff no está vacío, solo cambia `BUDGET_GIB` y su comentario, con la cifra medida con U9 (redondeada hacia arriba a 0,1 GiB) y la cita de `DECISIONES-LOOP.md` §7. La cifra no pasa del umbral de la sección «Presupuesto». Si pasa, es una detención, no un ROJO del codificador.

- [ ] **CA-9** — Paso 17: N/A.
  ```bash
  test ! -d bias-monitoring/migrations && test ! -d bias-monitoring/frontend
  ```
  Esperado: código 0.

- [ ] **CA-10** — Paso 18: cierre.
  ```bash
  make -C bias-monitoring check && make -C platform check
  grep -nE "^## (Comprobado|Diferido por la demo|Pendiente en U12)" aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md
  test -s bias-monitoring/docs/imagenes.md
  ```
  Esperado: código 0 y las tres secciones. El `check` de U9 incluye el chart (CA-2 y CA-3), la admisión (CA-5) y la prueba de imagen (CA-4), y **falla** si falta una herramienta. No se salta con rc 0: es la candidata F-02 de U04-T07, `revisiones/U04-T07/ronda-1.md`.

- [ ] **CA-11** — RL-4: el `make check` de todas las unidades, una vez al cerrar U9.
  ```bash
  for u in contracts platform identity-edge decision-registry governance reference-model model-serving scoring-explainability bias-monitoring; do make -C $u check || echo "FALLA $u"; done
  ```
  Esperado: ninguna línea «FALLA». Si una unidad ajena falla y el fallo también ocurre en `origin/main`, regístralo con la salida: no es de esta tarea. Si `scoring-explainability` todavía no tiene `check` en `main`, anótalo.

- [ ] **CA-12** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/bias-monitoring-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso 1[1-8] "
  ```
  Esperado:
  - Pasos 11, 12, 14 y 18 en `[x] (U09-T04, acotado a la demo)`;
  - Paso 17 en `[x] (U09-T04)`;
  - Paso 13 en `[ ]` con «diferido por la demo (T2)»;
  - Paso 15 en `[ ]` con «diferido por la demo (T4)»;
  - Paso 16 en `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».

  Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U09-T04.md`:
- `replicas: 1` en el servicio, o sin `vectra.io/hpa-exempt` (Kyverno o `conftest` falla);
- sin PDB;
- `vectra-high` en el servicio, o `vectra-normal` en el CronJob;
- `concurrencyPolicy: Allow` y `backoffLimit: 1`;
- `schedule` literal en la plantilla;
- sin la anotación del sidecar nativo;
- sin `vectra.io/workload: bias-monitoring-job` en los pods del CronJob;
- `values-monitoring-policy.yaml` con intervalo de 12 min, y con 5 min y `activeDeadlineSeconds: 600`;
- una variable de `REQUIRED` fuera del `Deployment` (CA-3 falla, y CA-4 no arranca);
- la llave del `ExternalSecret` montada sin `readOnly`;
- el Service renombrado (la prueba contra `biasUrl` falla);
- `numpy` instalado en la imagen (la orden de CA-1 falla);
- `FROM python:3.12-slim` sin digest (la orden de CA-1 falla);
- `syncPolicy.automated` en `apps/kind/bias-monitoring.yaml` (Kyverno falla);
- `wave: 4` en `components.yaml` (`test_waves.py` falla);
- un identificador del Paso 12 en la lista de diferidos, o uno diferido fuera de ella (`test_traceability.py` falla).

---

## Preguntas abiertas

**P-1 — `CODEOWNERS`.** El Paso 12 pide una línea de `CODEOWNERS` con la ruta `vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml`. `.github/CODEOWNERS` ya tiene la regla `**/values-monitoring-policy.yaml @jjlloobb @joseluisjedi`, que cubre ese archivo. Hay dos opciones:
- (a) dejar la regla con comodín y comprobar con una prueba que cubre la ruta;
- (b) agregar además la línea literal.

**Recomendación: (a).** Cumple el propósito de INF-U9-03 sin tocar un archivo de gobierno del repositorio, y la prueba evita que se pierda. Si el usuario no responde, rige la recomendación.

**P-2 — PBT-U9-05 (120 × 80 frente a NFR-U9-52).** En U09-T02 se aceptó 120 × 80 en `test_run_machine.py` porque se estimaba que 500 × 80 tardaría más de 6 minutos (≈ 0,15 s por corrida). El codificador de U09-T03 midió en esta máquina, con el perfil `ci`, 29 s con 120 × 80 y 2 min 17 s con 500 × 80, a ≈ 16 ms por corrida. Las cifras están en `aidlc-docs/construction/bias-monitoring/code/services.md`, sección «PBT-U9-05 frente a NFR-U9-52». Hay dos opciones:
- (a) volver al 500 × 80 literal de NFR-U9-52 en esta tarea y quitar esa sección de `services.md`;
- (b) mantener 120 × 80 y dejarlo nombrado en `cierre-demo.md`.

**Recomendación: (a).** Las PBT no se recortan (alcance §2.1), y la razón del ajuste ya no se sostiene con la medición. Es un cambio de configuración de la prueba, no de comportamiento. Si el usuario elige (a), CA-10 corre con el valor nuevo y la bitácora registra el tiempo. **Decide el usuario antes de despachar.**

---

## Notas

- **Presupuesto de kind:** ver la sección del Alcance. Registra en la bitácora la cifra con y sin U9, y el desglose por unidad.
- **U07-T04 en paralelo:** si U07-T04 sube `BUDGET_GIB` antes, parte de la cifra de `main` en la base de tu rama. Si las dos tareas tocan `components.yaml` o `test_kind_profile.py` a la vez, el orquestador resuelve el conflicto al integrar.
- Archivos que se modifican en su sitio:
  - en `bias-monitoring/`: `Dockerfile`, `chart/`, `policies/`, `tests/` y `Makefile`;
  - `vectra-risk-gitops/components.yaml` y lo generado;
  - `platform/tests/test_kind_profile.py`, solo `BUDGET_GIB`;
  - el plan y `CANDIDATAS.md`;
  - `.github/CODEOWNERS`, solo si P-1 = (b);
  - `tests/property/test_run_machine.py` y `code/services.md`, solo si P-2 = (a).
- Archivos nuevos: `bias-monitoring/docs/imagenes.md`, `bias-monitoring/tests/integration/test_image.py` y `aidlc-docs/construction/bias-monitoring/evidence/cierre-demo.md`.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- Docker está disponible para construir y correr la imagen.
- **Bitácora:** `bitacoras/U09-T04.md`, con:
  - los pares falla-pasa;
  - la lista de diferidos razonada;
  - la fuente de los CRD de fixture;
  - el `docker run` de CA-4;
  - la memoria de kind;
  - la decisión de P-1 y P-2.
