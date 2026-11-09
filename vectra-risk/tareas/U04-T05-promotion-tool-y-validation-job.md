# U04-T05 — `promotion-tool` y `model-validation-job` de `governance`

**Unidad:** U4 `governance`
**Historias que implementa:** US-204 y US-208 (`promotion-tool`), US-202 (`model-validation-job`, modo `validacion`).
**Depende de:**
- U04-T04 (endpoints: `mark_active` llama a `POST /v1/models/{id}/activation`; el Job usa el lanzador de `k8s_jobs.py` y `PUT /v1/models/{id}/validation-report`);
- U09-T01 (librería `vectra_disparity`: `counts_from_records` y `disparity_by_band`). La enmienda exige **la librería real de U9**, no un doble (`demo-recorte-funcional.md` §3 U4, Paso 13, y §5.1).

**Se despacha** cuando U04-T04 y U09-T01 estén fusionados en `main`.
**Rama:** `tarea/U04-T05`, desde `origin/main`.

Bloque E del plan de U4 (`aidlc-docs/construction/plans/governance-code-generation-plan.md`), fusionado como «E (12–13)» (`demo-recorte-funcional.md` §4). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 12 `promotion-tool` | **E\*F** | Entran `list_promotable`, `create_promotion_pr`, `post_activation_pr`, `rollback_pr` y `mark_active`. Se difiere `retire_inference_service` | Enmienda §3 U4 |
| 13 `model-validation-job` | **E\*F** | Entra el modo `validacion`: AUC, `initial_disparity` con la librería real de U9, `sync_check` y envío por F32. Se difiere el modo `source_comparison` y su línea de aceptación | Enmienda §3 U4; P-5; Q-6 |
| 14 Scripts de CI | **D** | Entero fuera | T4 |
| 15 `model-archive` | **D** | Entero fuera | T5 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige la regla «sin fallos nuevos» (`DECISIONES-LOOP.md` §6).

---

## Alcance

**Dentro:** los Pasos 12 y 13 del plan, con su texto y su aceptación, salvo lo que se difiere y se nombra abajo. Léelos allí. Precisiones:

### Paso 12 — `promotion-tool` (E\*F)

- CLI en `governance/promotion_tool/`, con estas operaciones:
  - `list_promotable`;
  - `create_promotion_pr`: **un solo commit** que agrega el `InferenceService` `isvc-<8 hex>` de la versión, con predictor y explicador del mismo `model_version_id`, más la evidencia `helm template` y `kubectl diff` contra kind;
  - `post_activation_pr`: baja la versión anterior a 1 réplica por componente;
  - `rollback_pr`: restaura los mínimos de producción de la versión `inactivo` antes de su `mark_active`;
  - `mark_active`: llama a `POST /v1/models/{id}/activation` y fija `inference_service` en `serving-config`.
- Login PKCE con loopback y el token **solo en memoria**. `gh` con la sesión del ingeniero y commit firmado. **Nunca** sincroniza ni aplica (AUTONOMIA-01).
- **Dónde escribe.** Los PR editan `vectra-risk-gitops/values/<env>/model-serving.yaml` (plan de U6, Pasos 7 y 9). U6 todavía no existe, así que el esquema de esos values sale del Infrastructure Design de U6 (`aidlc-docs/construction/model-serving/infrastructure-design/`) y del plan de U6, Paso 6 (perfiles `prod`, `inactive` y `staging`). Escribe ese esquema en un solo módulo de `promotion_tool` y documenta en la bitácora de dónde salió cada campo. Si el diseño de U6 no basta para fijarlo, **detente y repórtalo**: no inventes campos. U6 Paso 7 lo comprobará contra su chart.
- La evidencia `kubectl diff` contra kind se genera con un parámetro que el ingeniero pasa. En las pruebas se reemplaza por un doble: ninguna prueba toca un clúster.
- Diseño: BR-U4-08 y 09; NFR-U4-20 y 21. Historias: US-204 y US-208.

### Paso 13 — `model-validation-job`, modo `validacion` (E\*F)

- Código en `governance/validation_job/`.
- **AUC-ROC**, con `auc_target` y `auc_meets_target`.
- **Disparidad inicial** con la librería real de U9: `counts_from_records` + `disparity_by_band` de `vectra_disparity` (`bias-monitoring/disparity/`), declarada como dependencia del workspace. Nada de doble.
- **Prueba de sincronía** predictor ↔ explicador (`sync_check`).
- **Informe** con el `disclaimer`, enviado por F32 (`PUT /v1/models/{id}/validation-report`) con `private_key_jwt` (F50).
- **Plantilla del Job** que crea el lanzador de U04-T04 (K01): verifica que lleva **explícita** la anotación `config.alpha.linkerd.io/proxy-enable-native-sidecar: "true"` (U1 P-U1-05). Si `k8s_jobs.py` no la pone, agrégala allí.
- **Recursos y seguridad** de INF-U4-01: requests de 500m / 1 GiB, limits de 2 CPU / 4 GiB, `activeDeadlineSeconds: 7200`, `vectra-low`, `runAsNonRoot`, `readOnlyRootFilesystem` y **sin token de Kubernetes**.
- **`ServiceAccount` `model-validation-job` y `ExternalSecret`** en `vectra-staging`, con la llave `private_key_jwt` de su cliente de Keycloak (F32, F50). Van en `governance/chart/`, que hoy está vacío. Crea el chart mínimo que las contenga, como hizo U03-T04 con el CronJob del agregador. El Deployment y lo demás son de U04-T06. El Job monta `minio-validation` (`validation-readonly`, F31), que entrega U1 en `vectra-staging`.
- **Imagen** del Job: la pide el Paso 13 («imagen con las librerías de inferencia»).
  - `governance/validation_job/Dockerfile`, multi-stage, como `decision-registry/Dockerfile`, con contexto en la raíz de `vectra-risk/`.
  - Usuario no root `65532:65532`. `FROM` fijado por digest.
  - Target `image-validation` en `governance/Makefile`. El push a `kind-registry` y el digest real los hace el operador en U04-T07.
  - Sin firma ni SBOM (T1).
- Diseño: BR-U4-07; NFR-U4-12 y 23; P-U4-03; U1 P-U1-05. Historia: US-202.

### Plan

Marca `[x]` los Pasos 12 y 13 con `(U04-T05, acotado a la demo)`. Los Pasos 14 y 15 siguen `[ ]`, con la nota «diferido por la demo (T4)» y «diferido por la demo (T5)».

**Fuera** (rechazar aunque se vea roto o tentador):

- `retire_inference_service` y su PR de retiro (enmienda §3 U4, Paso 12). El esquema de values de U6 incluye el retiro; aquí no se genera.
- El modo `source_comparison` del Job, con su línea de aceptación («solo tablas de conteo»). Lo mismo para la rama `source_comparison` del barrido (P-5; Q-6). Si el Job recibe `mode=source_comparison`, termina con un error explícito y sin enviar nada.
- Pasos 14 y 15 completos.
- El Deployment del servicio, el hook de migración, RBAC, flujos, la Application y la cobertura de la unidad: son de U04-T06.
- Push de imágenes, digest real y cualquier `kubectl`, `argocd` o sync (AUTONOMIA-01).
- Cambios en U0, U1, U5, U6 o U9. Si falta algo allí, detente y repórtalo.
- Las candidatas abiertas de U4 en `CANDIDATAS.md`, salvo que esta tarea toque esa misma línea.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/governance-code-generation-plan.md`: §1, Pasos 12 a 15, §3 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U4 y U6, §5.1 y §6 (P-5, P-7).
- `aidlc-docs/construction/plans/governance-bloque-d-precisiones.md` (Q-6).
- `aidlc-docs/construction/governance/functional-design/` (BR-U4-07, 08 y 09), `nfr-requirements/` (NFR-U4-12, 20, 21 y 23), `nfr-design/` (P-U4-03) e `infrastructure-design/` (INF-U4-01).
- `aidlc-docs/construction/plans/model-serving-code-generation-plan.md` (Pasos 6, 7 y 9) y `aidlc-docs/construction/model-serving/` (esquema de values del `InferenceService`).
- `governance/src/vectra_governance/` (`api.py`, `k8s_jobs.py`, `evidence.py`) y `governance/tests/`.
- `bias-monitoring/disparity/` y `aidlc-docs/construction/bias-monitoring/code/library.md` (API de la librería, regla R4).
- `reference-model/` (paquetes de U5 y `docs/release.md`).
- `contracts/tools/forbidden_phrases.py` y `contracts/forbidden-phrases.yaml`.
- `decision-registry/Dockerfile` y `decision-registry/chart/` (formato de imagen y chart mínimo).
- `platform/network/flows.yaml` (F31, F32, F50).

---

## Criterios de aceptación

Desde `vectra-risk/`. Ningún criterio toca el clúster.

- [ ] **CA-1** — Paso 12: aceptación del plan.
  ```bash
  uv run pytest governance/tests/unit/test_promotion_tool.py -v
  ! grep -rE "argocd app sync|kubectl apply|helm (install|upgrade)" governance/promotion_tool/
  ```
  Esperado: código 0 en los dos. Pasan, como mínimo:
  - con un repositorio git de fixture, el PR de promoción tiene **un solo commit firmado**, y los dos manifiestos tienen el mismo `model_version_id` (lectura de vuelta con `git log` y `git show` sobre el fixture);
  - ningún archivo de configuración guarda tokens: después de un login con un doble del IdP, se recorre `$HOME` y el directorio del fixture y no aparece el token;
  - `post_activation_pr` deja la versión anterior en 1 réplica por componente;
  - `rollback_pr` restaura los mínimos de producción de la versión `inactivo`;
  - `mark_active` llama a `activation` (doble HTTP) con el `inference_service` correcto;
  - `retire_inference_service` no existe en la CLI.

- [ ] **CA-2** — Paso 13: aceptación del plan, salvo la línea de `source_comparison`.
  ```bash
  uv run pytest governance/tests/unit/test_validation_job.py -v
  ```
  Esperado: pasan, como mínimo:
  - con un modelo ONNX de fixture y un explicador que no produce vectores → `sync_check.passed = false`;
  - las plantillas del informe pasan `contracts/tools/forbidden_phrases.py` con la lista única de U0;
  - `initial_disparity` sale de `vectra_disparity` (sin doble): con un dataset de fixture, la tabla coincide con la que calcula la librería directamente;
  - `auc_meets_target` es `false` con un AUC por debajo de `auc_target`;
  - el informe enviado por F32 (doble HTTP) lleva el `disclaimer`;
  - `mode=source_comparison` → error explícito y ningún envío.

- [ ] **CA-3** — Paso 13: plantilla del Job y chart mínimo (lectura de vuelta del render).
  ```bash
  uv run pytest governance/tests/unit/test_validation_job_template.py -v
  helm template governance governance/chart --namespace vectra-staging | grep -nE "kind: (ServiceAccount|ExternalSecret)|automountServiceAccountToken"
  ```
  Esperado: código 0. La prueba lee el manifiesto que genera `k8s_jobs.py` y comprueba la anotación del sidecar nativo, `vectra-staging`, TTL, `activeDeadlineSeconds: 7200`, `backoffLimit: 0`, recursos de INF-U4-01, `vectra-low`, `runAsNonRoot`, `readOnlyRootFilesystem` y `automountServiceAccountToken: false`. El render muestra la `ServiceAccount` `model-validation-job` y su `ExternalSecret`.

- [ ] **CA-4** — Imagen del Job.
  ```bash
  make -C governance image-validation
  docker image inspect localhost:5001/vectra/model-validation-job:dev --format '{{.Config.User}}'
  docker run --rm --entrypoint python localhost:5001/vectra/model-validation-job:dev -c "import onnxruntime, vectra_disparity; print('OK')"
  grep -nE '^FROM .*@sha256:[0-9a-f]{64}' governance/validation_job/Dockerfile
  ```
  Esperado: build en 0, usuario `65532:65532`, `OK` impreso y cada `FROM` fijado por digest.

- [ ] **CA-5** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C governance check && make -C platform check
  ```
  Esperado: código 0 en los dos. Si `make -C platform check` falla en `check-tools` porque `platform/.tools` no existe en el worktree, regístralo y corre `uv run pytest platform/tests/test_ci.py -q -p no:cacheprovider --rootdir=platform --import-mode=importlib`.

- [ ] **CA-6** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/governance-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso 1[2-5]"
  ```
  Esperado: Pasos 12 y 13 en `[x] (U04-T05, acotado a la demo)`; Pasos 14 y 15 en `[ ]` con su nota de diferido. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U04-T05.md`:
- el PR de promoción con dos commits → la prueba de «un solo commit» falla;
- el token escrito en un archivo de configuración → la prueba de tokens falla;
- el explicador sin vectores con `sync_check` forzado a `true` → la prueba falla;
- la plantilla del Job sin la anotación del sidecar nativo → la prueba falla.

Pruebas nuevas: `governance/tests/unit/test_promotion_tool.py`, `test_validation_job.py` y `test_validation_job_template.py`, con dobles del IdP, de `gh`, de la API de governance y del repositorio git.

---

## Notas

- Archivos que se modifican en su sitio: `governance/src/vectra_governance/k8s_jobs.py` (solo si falta la anotación), `governance/Makefile`, `governance/pyproject.toml`, el `pyproject.toml` raíz y `uv.lock` (la dependencia de `vectra-disparity`), el plan y `CANDIDATAS.md`. Nada de duplicados con sufijo.
- Directorios nuevos: `governance/promotion_tool/`, `governance/validation_job/` y el contenido de `governance/chart/`.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades. El orquestador nombra en el despacho cuáles están activos.
- Docker está disponible para construir la imagen.
- **Bitácora:** `bitacoras/U04-T05.md`. Registra el origen de cada campo del esquema de values de U6, los pares falla-pasa y la versión de `vectra_disparity` usada.
