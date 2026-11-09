# U04-T05b — `promotion-tool` y codificación de features del `model-validation-job`

**Unidad:** U4 `governance`
**Historias que implementa:** US-204 y US-208 (`promotion-tool`).
**Depende de:**
- U04-T05 (PR #101): `model-validation-job` y lanzador;
- **U06-T02**: `model-serving/chart/values.schema.json` y `model-serving/docs/values.md`, el esquema de `vectra-risk-gitops/values/<env>/model-serving.yaml`.

**Se despacha** cuando U04-T05 y U06-T02 estén fusionados en `main`.
**Rama:** `tarea/U04-T05b`, desde `origin/main`.

Origen: `revisiones/U04-T05/decision-paso-12.md` (decisión del usuario, 2026-11-09). El Paso 12 salió de U04-T05 porque el esquema de values de U6 no existía. La corrección de `proposed_rate_ea` la agregó el usuario a esta tarea el mismo día (candidata de U04-T05, ronda 2).

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. `--all` según `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:**

### Parte 1 — Paso 12, `promotion-tool` (E\*F)

El alcance, la aceptación y los pares rojo-verde del Paso 12 son los de `tareas/U04-T05-promotion-tool-y-validation-job.md` («Paso 12» y CA-1), sin cambios. Léelos allí. Resumen:
- `list_promotable`, `create_promotion_pr` (un solo commit firmado con el `InferenceService` de la versión y la evidencia `helm template` y `kubectl diff`), `post_activation_pr`, `rollback_pr` y `mark_active`.
- Se difiere `retire_inference_service` (enmienda §3 U4).
- Login PKCE con loopback y el token solo en memoria; `gh` con la sesión del ingeniero; **nunca** sincroniza ni aplica.

Lo que cambia frente a U04-T05: **el esquema ya existe**. `promotion-tool` edita `vectra-risk-gitops/values/<env>/model-serving.yaml` según `model-serving/docs/values.md`, y cada YAML que genera se valida contra `model-serving/chart/values.schema.json` y se renderiza con `helm template model-serving/chart`. No se inventa ningún campo. Si el esquema no permite expresar algún PR, **detente y repórtalo**: es un defecto de U06-T02.

### Parte 2 — Codificación de `proposed_rate_ea` en el Job (candidata de U04-T05, ronda 2)

- `governance/validation_job/vectra_validation/features.py` codifica **por nombre**, igual que el predictor de U6 (`categorical_encoding` del paquete), y no por el tipo del `FeatureValue`. `proposed_rate_ea` entra como numérica, como la entrena U5.
- El fixture de las pruebas entrena con `vectra_reference.train.encode` (la codificación real de U5), no con la matriz del propio Job.
- Cubre también el paso de `confidence` y canal en `validate` (NARANJA de la ronda 2): una mutación `confidence="1.0000"` debe hacer fallar una prueba.

**Fuera:**

- `retire_inference_service`.
- Cambios en U0 (`derive` y `FeatureSpecItem` siguen igual; la candidata de U0 sobre el tipo de cada feature sigue abierta), en U5 o en U6. Si el esquema de U6 no basta, se reporta.
- Los demás literales del Job (`n_min`, umbral, `auc_target`) y las candidatas de imagen: siguen en `CANDIDATAS.md`.
- Cualquier `kubectl`, `argocd` o sync (AUTONOMIA-01).

---

## Archivos de contexto

- `tareas/U04-T05-promotion-tool-y-validation-job.md` (Paso 12 y CA-1) y `revisiones/U04-T05/` (decisión, rondas 1 y 2).
- `aidlc-docs/construction/plans/governance-code-generation-plan.md` (Paso 12) y `aidlc-docs/construction/governance/` (BR-U4-08, 09; NFR-U4-20, 21).
- `model-serving/chart/values.schema.json`, `model-serving/docs/values.md` y `model-serving/tests/unit/test_promotion_renders.py` (U06-T02).
- `model-serving/` de U06-T01: cómo codifica el predictor (`categorical_encoding`).
- `reference-model/src/vectra_reference/train.py` (`encode`) y el `feature_spec.json` del paquete.
- `governance/validation_job/` y `governance/tests/unit/test_validation_job.py`.

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 12: el CA-1 de U04-T05, más la validación contra el esquema de U6.
  ```bash
  uv run pytest governance/tests/unit/test_promotion_tool.py -v
  ! grep -rE "argocd app sync|kubectl apply|helm (install|upgrade)" governance/promotion_tool/
  ```
  Esperado: código 0 en los dos, con los casos del CA-1 de U04-T05. Además, para cada uno de los cuatro PR, el values que genera `promotion-tool` pasa `values.schema.json` y `helm template model-serving/chart` lo renderiza con el resultado que espera `test_promotion_renders.py` de U6 (mismo fixture de partida).

- [ ] **CA-2** — Parte 2: codificación por nombre.
  ```bash
  uv run pytest governance/tests/unit/test_validation_job.py -v
  ```
  Esperado: pasan, y en particular:
  - con un modelo entrenado con `vectra_reference.train.encode`, la matriz del Job tiene `proposed_rate_ea` numérica en todas las filas (nunca -1);
  - con el modelo base real de U5, el AUC que calcula el Job coincide con el de U5 dentro de 1e-3 (hoy ≈ 0,863, no 0,848);
  - la mutación `confidence="1.0000"` en `validate` hace fallar una prueba.

  Rojo primero en la bitácora: con el código actual, la prueba del AUC falla con ≈ 0,848.

- [ ] **CA-3** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C governance check && make -C platform check
  ```
  Esperado: código 0. Si `check-tools` falla por herramientas ausentes en el worktree, corre `platform/install-tools.sh` (descarga con SHA-256) o el respaldo `test_ci.py`, y regístralo.

- [ ] **CA-4** — Plan: Paso 12 `[x] (U04-T05b, acotado a la demo)`, sin la nota «pasa a U04-T05b».

---

## Notas

- Archivos nuevos: `governance/promotion_tool/`. Se modifican en su sitio: `governance/validation_job/`, `governance/tests/`, `governance/pyproject.toml`, el plan y `CANDIDATAS.md` (marca resueltas las candidatas de `proposed_rate_ea` y de `confidence` sin prueba).
- **Bitácora:** `bitacoras/U04-T05b.md`, con los pares rojo-verde (PR de dos commits, token en archivo, AUC 0,848 → 0,863, mutación de `confidence`).
