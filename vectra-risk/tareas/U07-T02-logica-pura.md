# U07-T02 — Lógica pura de `scoring-explainability`: `policy`, `narrative`, `factuality` y `applicant`

**Unidad:** U7 `scoring-explainability`
**Historias que implementa:** US-103, US-106 y US-207 (`policy`), US-104 (`narrative`), US-105 (`factuality`) y US-110 (`applicant`).
**Depende de:** U07-T01 (esqueleto y presupuestos). Usa U0 (`PolicyResult`, `FeatureVector`, `FeatureDictionary`, `ReasonCode`) y U5 (casos RT-4 de `vectra_reference.adversarial`), ya en `main`.
**Se despacha** cuando U07-T01 esté fusionado en `main`.
**Rama:** `tarea/U07-T02`, desde `origin/main`.

Bloque B del plan de U7 (`aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`), tarea «B (3–5, 7)» de `demo-recorte-funcional.md` §8, ampliada con el Paso 6 por la decisión del usuario sobre P-1 (2026-11-10: opción (a) para U7, como Q-6 en U4; enmienda §6 P-1). La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 3 `policy` | **E** | Completo, con PBT-U7-01 y 02 | Enmienda §3 U7 (Pasos 1–5) |
| 4 `narrative` | **E** | Completo, con PBT-U7-03. Sin `factuality_check = passed` no hay `Ready` (BR-U0-02; BR-U7-10 y 11) | Enmienda §3 U7 (Pasos 1–5) |
| 5 `factuality` | **E** | Completo, con PBT-U7-04 y 05 | Enmienda §3 U7 (Pasos 1–5) |
| 6 `applicant` | **E** | Completo, con **PBT-U7-06**, la plantilla `applicant:v1` y `forbidden_phrases.py`. Sale de D porque P-1 = (a) exige el handler de `/v1/applicant-summaries` (U07-T03) | Decisión del usuario, 2026-11-10; enmienda §6 P-1 |
| 7 Resumen de la lógica pura | **E\*F** | Entran la cobertura de ramas al 100 % y `code/logic.md`. Se difiere `mutmut` | Enmienda §3 U7; §2.3; T3 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:** los Pasos 3, 4, 5, 6 y 7 del plan, con su texto y su aceptación, salvo lo que se difiere arriba. Léelos allí. Precisiones:

### Paso 3 — `policy` (E)

- `scoring/src/scoring/policy.py`: `evaluate(PolicyEvaluationInput) -> PolicyResult`, función pura. `PolicyEvaluationInput` es interno de scoring (`functional-design/domain-entities.md` §2); `PolicyResult` es de U0.
  - Las cinco reglas de BR-U7-04, evaluadas **todas**, con sus motivos acumulados en el orden de la tabla y sin duplicados.
  - `cutoff_efectivo` por canal: el `cutoff` de la regla del canal, si existe; si no, el general.
  - Combinación de BR-U7-05: el resultado más conservador gana.
  - `normative` nulo → `revision_requerida` con `parametro_normativo_no_vigente`, sin fail-closed (BR-U7-06).
  - `baja_confianza` → siempre `revision_requerida` (BR-U7-07).
- Diseño: BR-U7-04, 05, 06, 07; NFR-U7-41. Historias: US-103, US-106, US-207.
- Pruebas: PBT-U7-01 (invariante) y PBT-U7-02 (bordes: igual a la usura no es «sobre», `property_value == vis_max` da `vis`, `score == cutoff` da `desfavorable`), con perfil `ci`. Ejemplos del plan: US-207 (tasa sobre usura y normativa no vigente → `revision_requerida` con los dos motivos) y un caso RT-4 de U5 → `baja_confianza`. El caso RT-4 sale de `vectra_reference.adversarial.rt4_cases` (como `model-serving/tests/conftest.py` usa `rt3_cases`), no de una copia.

### Paso 4 — `narrative` (E)

- `explainability/src/explainability/narrative.py`: `TemplateNarrativeGenerator` (`template:v1`) detrás de la interfaz `NarrativeGenerator`, con **una sola** implementación registrada (NFR-U7-32).
  - Top 5 por |SHAP|, sin ceros, con desempate por `feature_id` (BR-U7-10).
  - Intensidad `fuerte`, `moderada` o `leve` (`domain-entities.md` §3).
  - Encabezado con método, versión de modelo y `template:v1`, más la leyenda post-hoc.
  - Sin números de SHAP.
- La plantilla es `explainability/templates/template_v1.txt`, un archivo versionado de texto.
- Diseño: BR-U7-10; NFR-U7-32. Historia: US-104.
- Pruebas: PBT-U7-03 (determinismo, orden y sin números), la narrativa de un caso fijo idéntica al texto esperado, `contracts/tools/forbidden_phrases.py` sobre la plantilla (BR-U0-94) y una sola implementación de `NarrativeGenerator`.

### Paso 5 — `factuality` (E)

- `explainability/src/explainability/factuality.py`: `FactualityValidator` **independiente** del generador (el contrato de import-linter de U07-T01 lo exige):
  - parte la narrativa en encabezado, líneas y leyenda;
  - reconoce `label_es` y la dirección contra el diccionario;
  - reimplementa por separado la selección y el desempate de BR-U7-10.
- Cualquier diferencia (omisión, reordenamiento, signo invertido, factor ajeno, texto adicional, encabezado o leyenda cambiados) → `False`.
- Diseño: BR-U7-11; NFR-U7-41. Historia: US-105.
- Pruebas: PBT-U7-04 (round-trip `validate(generate(v), v)`), PBT-U7-05 (mutaciones) y una narrativa con un factor invertido → `False`.

### Paso 6 — `applicant` (E)

- `explainability/src/explainability/applicant.py`, función pura `generate`:
  - hasta 3 factores con `applicant_safe = true` y SHAP > 0, en orden de |SHAP| (BR-U7-14);
  - plantilla `applicant:v1` (`explainability/templates/applicant_v1.txt`, archivo versionado) y leyenda post-hoc;
  - ningún campo prohibido (`domain-entities.md` §4: valores SHAP, `model_version_id`, `score`, `confidence`, `policy_version_id`, `feature_vector`, datos de otro caso) ni números;
  - devuelve el `ApplicantSummary` de U0. No se guarda.
- El log `applicant_summary.generated` y la ruta son de U07-T03 (Paso 9).
- Diseño: BR-U7-14. Historia: US-110.
- Pruebas: PBT-U7-06 (invariante: sin campos prohibidos ni números; solo factores `applicant_safe` con SHAP > 0, como máximo 3), el ejemplo de un rechazo sin campos prohibidos y `contracts/tools/forbidden_phrases.py` sobre `applicant:v1` (BR-U0-94).

### Paso 7 — Resumen de la lógica pura (E\*F)

- Cobertura de ramas **100 %** en `policy`, `narrative` y `factuality` (NFR-U7-40).
- Resumen en `aidlc-docs/construction/scoring-explainability/code/logic.md`: qué hace cada módulo, sus PBT y su cobertura, y lo diferido (`mutmut`).
- Diseño: NFR-U7-40, 42 (NFR-U7-41 se difiere con `mutmut`).

### Plan

Marca `[x]` los Pasos 3, 4, 5 y 6 con `(U07-T02)` y el 7 con `(U07-T02, acotado a la demo)`.

**Fuera** (rechazar aunque se vea roto o tentador):

- `mutmut` en `policy` y `factuality` y su allowlist (T3; enmienda §2.3).
- Clientes, `explain`, `dictionary_cache`, `orchestrator`, endpoints, el cliente F23 y el log `applicant_summary.generated` (U07-T03).
- Cambios en U0 o U5. Si falta algo (por ejemplo, un `ReasonCode` de BR-U7-04 que no exista en U0), **detente y repórtalo**.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md`: Pasos 3 a 7 y §3 (trazabilidad).
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §2, §3 U7, §5.2 (PBT) y §6 (P-1, decidida por el usuario el 2026-11-10: opción (a)).
- `aidlc-docs/construction/scoring-explainability/functional-design/`: `business-rules.md` (BR-U7-04 a 11), `domain-entities.md` (§2 entrada de la política, §3 narrativa e intensidad, §4 resumen y campos prohibidos) y `business-logic-model.md` (PBT-U7-01 a 06).
- `aidlc-docs/construction/scoring-explainability/nfr-requirements/nfr-requirements.md` (NFR-U7-32, 40, 42).
- `contracts/python/vectra_contracts/src/vectra_contracts/models/explanation.py` (`PolicyResult`), `models/features.py` (`FeatureDictionary`, `FeatureDictionaryEntry` con `applicant_safe`), `models/api.py` (`ApplicantSummary`, `ApplicantFactor`) y `catalog.py` (`Outcome`, motivos).
- `contracts/tools/forbidden_phrases.py` y `contracts/forbidden-phrases.yaml`.
- `reference-model/src/vectra_reference/adversarial.py` (`rt4_cases`) y `model-serving/tests/conftest.py` (cómo consumir los casos de U5 sin copiarlos).

---

## Criterios de aceptación

Desde `vectra-risk/`. Ninguno toca el clúster.

- [ ] **CA-1** — Paso 3: aceptación del plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_policy.py scoring-explainability/tests/unit/test_policy_examples.py -v
  ```
  Esperado: código 0, con la semilla impresa. Pasan PBT-U7-01, PBT-U7-02, el ejemplo de US-207 con los dos motivos y el caso RT-4 de U5 → `baja_confianza` y `revision_requerida`.

- [ ] **CA-2** — Paso 4: aceptación del plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_narrative.py scoring-explainability/tests/unit/test_narrative_examples.py -v
  uv run python contracts/tools/forbidden_phrases.py scoring-explainability/explainability/templates/template_v1.txt
  ```
  Esperado: código 0 en los dos. Pasan PBT-U7-03, la narrativa del caso fijo idéntica al texto esperado y la prueba de una sola implementación de `NarrativeGenerator`.

- [ ] **CA-3** — Paso 5: aceptación del plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_factuality.py -v
  ```
  Esperado: código 0. Pasan PBT-U7-04, PBT-U7-05 (cada operador de mutación de BR-U7-11 tiene su estrategia) y el factor invertido → `False`.

- [ ] **CA-4** — Paso 6: aceptación del plan.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/property/test_applicant.py -v
  uv run python contracts/tools/forbidden_phrases.py scoring-explainability/explainability/templates/applicant_v1.txt
  ```
  Esperado: código 0 en los dos. Pasan PBT-U7-06 y el ejemplo de un rechazo sin campos prohibidos.

- [ ] **CA-5** — Paso 7: cobertura de ramas (sin `mutmut`).
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest scoring-explainability/tests/unit scoring-explainability/tests/property --cov=scoring --cov=explainability --cov-branch \
    && uv run coverage report --include="*/scoring/policy.py,*/explainability/narrative.py,*/explainability/factuality.py" --fail-under=100
  test -s aidlc-docs/construction/scoring-explainability/code/logic.md
  ```
  Esperado: código 0. El `--cov=policy --cov=narrative --cov=factuality` del plan no mide nada (los módulos viven en los paquetes `scoring` y `explainability`), así que el comando nombra los paquetes y fija el 100 % por módulo. Si los nombres reales de los paquetes difieren, ajústalos y regístralo. Los dos comandos quedan en el `check` de `scoring-explainability/Makefile`.

- [ ] **CA-6** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C scoring-explainability check && make -C platform check
  ```
  Esperado: código 0 en los dos.

- [ ] **CA-7** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/scoring-explainability-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso [3-7] "
  ```
  Esperado: Pasos 3, 4, 5 y 6 en `[x] (U07-T02)`; Paso 7 en `[x] (U07-T02, acotado a la demo)`. Ningún otro cambio en el texto del plan.

---

## Plan de pruebas

**Rojo primero**, con cada par falla-pasa en `bitacoras/U07-T02.md`:
- `proposed_rate_ea >= usury_cap_ea` en lugar de `>` → PBT-U7-02 falla;
- `evaluate` que corta en la primera regla que se cumple → PBT-U7-01 falla (faltan motivos);
- `normative` nulo tratado como fail-closed → el ejemplo de US-207 falla;
- desempate por `label_es` en vez de `feature_id` → PBT-U7-03 falla;
- un SHAP = 0 en la narrativa → PBT-U7-03 falla;
- `factuality` que ignora el signo → PBT-U7-05 falla;
- `factuality` que no comprueba la leyenda → PBT-U7-05 falla;
- una segunda implementación registrada de `NarrativeGenerator` → la prueba de NFR-U7-32 falla;
- una frase de `forbidden-phrases.yaml` en `template_v1.txt` → `forbidden_phrases.py` falla;
- `applicant` que incluye un factor con `applicant_safe = false` o SHAP < 0 → PBT-U7-06 falla;
- `applicant` con 4 factores, o con el `score` en el texto → PBT-U7-06 falla.

---

## Notas

- **P-1 y el Paso 6.** Decisión del usuario del 2026-11-10: P-1 = (a) para U7 (enmienda §6 P-1). El handler de `POST /v1/applicant-summaries` se implementa en U07-T03, y usa el `applicant` de esta tarea.
- Archivos que se modifican en su sitio: `scoring-explainability/` (módulos de la lógica pura, plantilla, pruebas y `Makefile`), el plan y `CANDIDATAS.md`. Archivos nuevos: `scoring-explainability/explainability/templates/applicant_v1.txt` y `aidlc-docs/construction/scoring-explainability/code/logic.md`.
- **Otros codificadores en paralelo:** no toques directorios de otras unidades.
- **Bitácora:** `bitacoras/U07-T02.md`, con la cobertura de partida y la final, la semilla de cada PBT y los pares falla-pasa.
