# U06-T01 — Esqueleto, cargador, predictor, explicador e imágenes de `model-serving`

**Unidad:** U6 `model-serving`
**Historias que implementa:** US-111 (sincronía predictor ↔ explicador) y US-106 (`confidence`), en su parte de serving.
**Depende de:** U0, U1 y U5 en `main` (paquete, artefactos RT-3 y la librería `envelope`). No depende de U4 en esta tarea.
**Rama:** `tarea/U06-T01`, desde `origin/main`. Puede correr en paralelo con U04-T05 (`governance/`) y U05-T05 (`reference-model/`). No toques esos directorios. Si U05-T05 se fusiona durante la tarea, integra `origin/main`: los fixtures que usas son los paquetes RT-3 y el modelo base, que U05-T05 no cambia.

Bloques A y B del plan de U6 (`aidlc-docs/construction/plans/model-serving-code-generation-plan.md`), fusionados como «A+B (1–5)» (`demo-recorte-funcional.md` §4). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 1 Esqueleto | **E** | Completo | Enmienda §3 U6 |
| 2 Cargador y concurrencia | **E** | Completo; el semáforo de concurrencia entra | Enmienda §3 U6 |
| 3 Predictor | **E\*F** | Entran el contrato y PBT-U5-04. Se difiere `tests/bench -m benchmark` (T3) | Enmienda §3 U6 |
| 4 Explicador | **E** | Completo, con la propiedad de la suma (tolerancia 1e-4) | Enmienda §3 U6 |
| 5 Dockerfiles | **E\*F** | Entran las imágenes, `runAsNonRoot`, `readOnlyRootFilesystem`, base por digest y `hadolint`. Se difieren la firma, el SBOM y su prueba (la ausencia de `shap` y `scikit-learn` la cubre import-linter del Paso 1, y aquí además `pip list` en la imagen) y el `kyverno test` de imagen sin firma (T1) | Enmienda §3 U6; T1 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:** los Pasos 1 a 5 del plan, con su texto y su aceptación, salvo lo que se difiere arriba. Léelos allí. Precisiones:

- **Paso 1.** `model-serving/` con la estructura de §1 del plan; miembro del workspace con `xgboost`, `numpy` y la librería `envelope` de U5, **sin** `shap`. Contrato de import-linter: ninguna imagen importa `shap` ni `sklearn` (NFR-U6-01). `model-serving/Makefile` con `check` (lint, mypy estricto, import-linter y pruebas), como `governance/Makefile`.
- **Paso 2.** `common/package_loader.py` y `common/concurrency.py`, según el plan (NFR-U6-03, 40; P-U6-03, 05). Fixtures: los artefactos RT-3 reales de U5 (`reference-model/`), no copias. `ModelPackageIntegrityFailed` se emite como métrica o log, como diga P-U6-03; la regla de alerta se difiere (Paso 9 en D).
- **Paso 3.** `:predict` del protocolo v1 de KServe; `{score, confidence, model_version_id}`; límite de 16; métricas en 8081 con `vectra_common`. PBT-U5-04 (paridad de `confidence` con `envelope.confidence`) corre contra el predictor.
- **Paso 4.** `:explain` con `pred_contribs=True` y `base_value`, en el orden del `feature_spec`, límite de 8. La propiedad: suma de contribuciones + `base_value` = margen del predictor (tolerancia absoluta 1e-4, enmienda del 2026-11-08) y el mismo `model_version_id` que `:predict`.
- **Paso 5.** Dos Dockerfiles (`predictor/` y `explainer/`), multi-stage, como `decision-registry/Dockerfile`, con contexto en `vectra-risk/`: base Python oficial por digest, usuario `65532:65532`, sin dependencias de desarrollo. Targets `image-predictor` e `image-explainer` en el Makefile, con tags `localhost:5001/vectra/model-predictor:dev` y `…/model-explainer:dev`. El push y el digest real son de la verificación en kind (Paso 11).

**Fuera:**

- Lo diferido en la tabla: benchmark (T3), firma, SBOM y su prueba, y `kyverno test` de imagen sin firma (T1).
- Bloques C en adelante: la plantilla del `InferenceService`, el esquema de values de `promotion-tool`, los flujos, la Application y las alertas (Pasos 6 a 13).
- Cambios en U0, U1, U4 o U5. Si falta algo allí (por ejemplo, que `envelope` no se pueda importar como dependencia), **detente y repórtalo**.
- Workflows de CI nuevos (T4).

---

## Archivos de contexto

- `aidlc-docs/construction/plans/model-serving-code-generation-plan.md`: §1, Pasos 1 a 5, §3 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md` §3 U6 y §5.2; `demo-kind-alcance.md` §2 (T1, T3) y §6.
- `aidlc-docs/construction/model-serving/` (NFR-U6-01..41, P-U6-01..06, INF-U6-01..02).
- `reference-model/` (paquetes, artefactos RT-3, `envelope`, `feature_spec.json`, PBT-U5-04 en sus pruebas) y `aidlc-docs/construction/reference-model/evidence/cierre-demo.md`.
- `contracts/python/vectra_common/` (`ops_server`, métricas).
- `governance/Makefile`, `governance/.importlinter` y `decision-registry/Dockerfile` (formatos de referencia).

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 1.
  ```bash
  uv sync --frozen && uv run lint-imports --config model-serving/.importlinter && make -C model-serving check
  ```
  Esperado: código 0. Un contrato que importa `shap` desde el predictor hace fallar `lint-imports` (rojo primero en la bitácora).

- [ ] **CA-2** — Paso 2.
  ```bash
  uv run pytest model-serving/tests/unit/test_package_loader.py model-serving/tests/unit/test_concurrency.py -v
  ```
  Esperado: RT-3 (a) → explicador no listo; (d) → no listo; un byte alterado → no listo y se emite `ModelPackageIntegrityFailed`; la solicitud N+1 con N en curso → 503 inmediato y `vectra_serving_rejected_total{component}` sube.

- [ ] **CA-3** — Paso 3 (sin benchmark).
  ```bash
  uv run pytest model-serving/tests/integration/test_predictor.py -v
  HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests -k "PBT_U5_04 or pbt_u5_04" -v
  ```
  Esperado: el contrato de la respuesta y el `model_version_id` del manifiesto; PBT-U5-04 pasa contra el predictor.

- [ ] **CA-4** — Paso 4.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest model-serving/tests/property/test_explainer.py -v
  ```
  Esperado: la propiedad de la suma con tolerancia 1e-4 y el mismo `model_version_id` que `:predict`.

- [ ] **CA-5** — Paso 5.
  ```bash
  platform/.tools/bin/hadolint model-serving/*/Dockerfile
  make -C model-serving image-predictor image-explainer
  for c in predictor explainer; do docker image inspect localhost:5001/vectra/model-$c:dev --format '{{.Config.User}}'; docker run --rm --entrypoint sh localhost:5001/vectra/model-$c:dev -c '! pip list 2>/dev/null | grep -iE "^(shap|scikit-learn) " && echo OK'; done
  grep -nE '^FROM .*@sha256:[0-9a-f]{64}' model-serving/*/Dockerfile
  ```
  Esperado: `hadolint` en 0, usuario `65532:65532` y `OK` en las dos, y cada `FROM` por digest. Si `hadolint` no está en `platform/.tools/bin` del worktree, usa el del checkout principal tras comparar la versión con `tools.env`.

- [ ] **CA-6** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C model-serving check && make -C platform check
  ```
  Esperado: código 0 en los dos.

- [ ] **CA-7** — Plan: Pasos 1, 2 y 4 `[x] (U06-T01)`; 3 y 5 `[x] (U06-T01, acotado a la demo)`. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U06-T01.md`: el import de `shap`; el cargador con la verificación del SHA-256 quitada; el semáforo sin límite; el explicador sin `base_value` (la propiedad falla).

---

## Notas

- **Kind no se toca.** Las imágenes se construyen en local con Docker.
- Archivos nuevos: todo `model-serving/`. Se modifican en su sitio: el `pyproject.toml` raíz, `uv.lock`, el plan y `CANDIDATAS.md`.
- **Bitácora:** `bitacoras/U06-T01.md`.
