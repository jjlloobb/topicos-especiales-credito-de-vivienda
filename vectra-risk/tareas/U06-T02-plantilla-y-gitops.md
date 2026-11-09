# U06-T02 — Plantilla del `InferenceService`, esquema de values de `promotion-tool`, flujos y Application de `model-serving`

**Unidad:** U6 `model-serving`
**Historias que implementa:** US-204 (plantilla atómica) y US-609 (escalado de KServe), en su parte estática.
**Depende de:** U06-T01 (PR #100, en `main`): imágenes del predictor y del explicador.
**Rama:** `tarea/U06-T02`, desde `origin/main`.
**La consume:** U04-T05b (`promotion-tool`), que escribe sobre el esquema de values que fija esta tarea. Por eso el esquema es **el entregable central**.

Bloques C y D del plan de U6 (`aidlc-docs/construction/plans/model-serving-code-generation-plan.md`), fusionados como «C+D (6–8, 10)» (`demo-recorte-funcional.md` §4):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 6 Plantilla del `InferenceService` | **E** | Completo: perfiles `prod`, `inactive` y `staging` | Enmienda §3 U6 |
| 7 Integración con `promotion-tool` | **E** | Completo: el esquema de values para los cuatro PR (promoción, post-activación, rollback **y retiro**: comparte esquema y prueba) y la credencial `minio-kserve` | Enmienda §3 U6 |
| 8 Flujos por etiqueta | **E** | F19, F22, F30 y F46 | Enmienda §3 U6 |
| 9 Alertas y runbooks | **D** | Entero fuera, incluido el `ServiceMonitor`. P-3 (`ModelPackageIntegrityFailed`) solo entraría si `journey-7-3` la muestra, y ese guion es de U12 | T2; P-3 |
| 10 Applications, cobertura y trazabilidad | **E** | Trazabilidad con la lista de diferidos (P-4) | Enmienda §3 U6 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. `--all` según `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:** los Pasos 6, 7, 8 y 10 del plan, con su texto y su aceptación. Léelos allí. Precisiones:

- **Paso 6, plantilla** (`model-serving/chart/`):
  - `isvc-<8 hex>` derivado del `model_version_id`. Predictor y explicador con el mismo `storageUri` y la misma anotación de versión (la que verifica el cargador de U06-T01). Etiquetas `vectra.io/component` (`predictor` o `explainer`; en staging solo `predictor`). `ServiceAccount` `kserve-model`.
  - Perfiles: `prod` (HPA por CPU al 60 %, predictor 2–4, explicador 2–6, spread, PDB, `vectra-high`), `inactive` (1 réplica fija, `vectra-normal`, con `vectra.io/serving-state: inactivo` y `vectra.io/hpa-exempt`) y `staging` (1 réplica, recursos reducidos, `vectra-low`, solo predictor; INF-U4-05).
  - Probes de INF-U6-01 y `emptyDir` de 1 GiB.
  - Imágenes por digest, con el digest de ejemplo, como los otros charts. El digest real lo pone el operador en kind (Paso 11).
- **Paso 7, esquema de values.** El chart declara **un** `values.schema.json` (JSON Schema) que define `vectra-risk-gitops/values/<env>/model-serving.yaml`: la lista de `InferenceService` declarados, cada uno con su `model_version_id`, su `storageUri`, su perfil y lo que necesite el chart. Debe permitir expresar los cuatro PR:
  - **promoción:** agregar un `InferenceService` nuevo junto al activo;
  - **post-activación:** bajar el anterior a `inactive`;
  - **rollback:** devolver una versión `inactive` a `prod`;
  - **retiro:** quitar una versión `inactive`.

  `helm` valida los values contra el esquema. Documéntalo en `model-serving/docs/values.md`, con un ejemplo por tipo de PR, para que U04-T05b lo use sin inventar campos. Los nombres que fija el diseño (INF-U6-01 y 02, y el plan) se respetan; lo que el diseño no fija lo decides aquí y lo dejas en la bitácora con su razón.
- **Paso 7, credencial.** Monta `minio-kserve` (`kserve-readonly`, F46), de U1, en `vectra-serving` y `vectra-staging`. Sin `ExternalSecret` propio.
- **Paso 7, prueba.** `model-serving/tests/unit/test_promotion_renders.py` parte de un values de fixture, aplica cada uno de los cuatro cambios **como los haría `promotion-tool`** (edición del YAML según `docs/values.md`), renderiza y comprueba el resultado esperado. El activo nunca queda con menos de 2 réplicas.
- **Paso 8.** Verifica en `platform/network/flows.yaml` los destinos de F19, F22, F30 y F46 por etiqueta, y que X08 sigue bloqueado. Si algo falta, **repórtalo**: no edites U1.
- **Paso 10.**
  - Entrada `model-serving` en `vectra-risk-gitops/components.yaml` con `wave: 6`. Una Application por entorno, sin `syncPolicy.automated`. Values por entorno en `vectra-risk-gitops/values/<env>/model-serving.yaml`, que en esta tarea **no declaran ningún `InferenceService`**: los agrega `promotion-tool` por PR.
  - Cobertura de ramas ≥ 90 % y 100 % en `package_loader`, midiendo los paquetes de `model-serving` (no el `source` de la raíz).
  - Trazabilidad con la lista «Diferido por la demo» en `aidlc-docs/construction/model-serving/evidence/cierre-demo.md`, que esta tarea crea solo con esa sección (benchmark T3, firma y SBOM T1, Paso 9 T2, y lo que la prueba marque de esos pasos).
  - Resumen en `aidlc-docs/construction/model-serving/code/README.md`.

**Fuera:**

- Paso 9 completo: `PrometheusRule`, runbooks y `ServiceMonitor` (T2).
- Pasos 11 a 13 (kind y cierre): van en U06-T03.
- `promotion-tool` (U04-T05b) y cualquier cambio en `governance/`.
- Perfil de 1 réplica para el activo en kind (DD-3 eligió la b). Ver la nota del presupuesto.
- Cambios en U0, U1, U4 o U5. Si falta algo, **detente y repórtalo**.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/model-serving-code-generation-plan.md`: §1, Pasos 6 a 10 y «Reglas de admisión».
- `aidlc-docs/construction/model-serving/` (INF-U6-01, 02; P-U6-02, 04, 06; NFR-U6-02, 11, 20, 21, 31).
- `aidlc-docs/construction/governance/infrastructure-design/infrastructure-design.md` (INF-U4-05) y `aidlc-docs/construction/plans/governance-code-generation-plan.md` (Paso 12: los cuatro PR).
- `revisiones/U04-T05/decision-paso-12.md` (por qué el esquema se fija aquí).
- `model-serving/` (U06-T01), `decision-registry/chart/` y `tareas/U03-T05-despliegue-y-calidad.md` (formato de chart, conftest, Application y `cierre-demo.md`).
- `platform/network/flows.yaml`, `platform/data/minio/values.yaml` (`minio-kserve`), `platform/policies/` y `vectra-risk-gitops/`.

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 6: render por perfil, CRD y políticas.
  ```bash
  for p in prod inactive staging; do helm template ms model-serving/chart -f model-serving/tests/fixtures/values-$p.yaml > /tmp/u6-$p.yaml && platform/.tools/bin/kubeconform -strict -schema-location default -schema-location 'model-serving/tests/fixtures/crds/{{.ResourceKind}}.json' /tmp/u6-$p.yaml; done
  platform/.tools/bin/conftest test --policy model-serving/policies/conftest /tmp/u6-*.yaml
  ```
  Esperado: código 0. Cada regla de `policies/conftest/` tiene un caso que falla con una mutación (como mínimo: `storageUri` o anotación distintos entre componentes, nombre que no sale del `model_version_id`, una ruta `adversarial/` en prod, el activo con menos de 2 réplicas, prioridad equivocada por perfil). El CRD de `InferenceService` de KServe v0.21.0 (la versión de `components.yaml`) se guarda como fixture, con su fuente en la bitácora.

- [ ] **CA-2** — Paso 7: esquema y los cuatro PR.
  ```bash
  uv run pytest model-serving/tests/unit/test_promotion_renders.py -v
  test -s model-serving/chart/values.schema.json && test -s model-serving/docs/values.md
  helm template ms model-serving/chart -f model-serving/tests/fixtures/values-invalid.yaml; test $? -ne 0
  ```
  Esperado: pasan los cuatro tipos de PR, y un values que viola el esquema hace fallar `helm template`.

- [ ] **CA-3** — Paso 8.
  ```bash
  uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -v
  ```
  Esperado: código 0. Una prueba de `model-serving/tests/unit/` compara las etiquetas del render con los selectores de F19, F22, F30 y F46.

- [ ] **CA-4** — Paso 10: Application y admisión.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/model-serving.yaml; done
  ```
  Esperado: código 0, wave `"6"` y sin `syncPolicy.automated`. Si `make -C platform check-chart` entra en pánico con recursos repetidos (candidata de U04-T05), usa un entorno por directorio, como U3, y regístralo.

- [ ] **CA-5** — Paso 10: cobertura y trazabilidad.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests --cov=vectra_predictor --cov=vectra_explainer --cov=vectra_serving_common --cov-branch --cov-fail-under=90
  uv run python platform/tests/test_traceability.py --unit model-serving --all
  ```
  Esperado: código 0, y 100 % en `package_loader`. Ajusta los nombres de los paquetes `--cov` a los reales de U06-T01.

- [ ] **CA-6** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C model-serving check && make -C platform check
  ```
  Esperado: código 0. Si `test_kind_profile.py` falla por el presupuesto, aplica la nota.

- [ ] **CA-7** — Plan: Pasos 6, 7, 8 y 10 `[x] (U06-T02)`; Paso 9 `[ ]` con «diferido por la demo (T2)».

---

## Notas

- **Presupuesto de memoria de kind (detención con reporte).** Esta tarea no declara `InferenceService` en los values de kind, así que no debería cambiar `test_kind_profile.py`. Si lo cambia, o si ves que el perfil `prod` (2 predictores + 2 explicadores) no cabe con lo que ya pide U1–U4 (`BUDGET_GIB`), **regístralo con la cifra** para U06-T03. No cambies `BUDGET_GIB` ni el perfil.
- Archivos que se modifican en su sitio: `model-serving/`, `vectra-risk-gitops/components.yaml` y lo generado, `vectra-risk-gitops/values/<env>/model-serving.yaml`, el plan y `CANDIDATAS.md`. Nuevo: `aidlc-docs/construction/model-serving/evidence/cierre-demo.md` (solo «Diferido por la demo») y `code/README.md`.
- **Bitácora:** `bitacoras/U06-T02.md`, con cada decisión del esquema que el diseño no fijaba.
