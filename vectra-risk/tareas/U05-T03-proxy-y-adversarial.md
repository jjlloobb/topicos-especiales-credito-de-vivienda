# U05-T03 — Variante proxy (RT-2) y conjunto adversarial (RT-1, RT-3 y RT-4) de `reference-model`

**Unidad:** U5 `reference-model`
**Historias que implementa:** US-303 (modelo proxy, RT-2), US-106 (RT-4), US-109 (RT-1) y US-111 (RT-3).
**Depende de:** U05-T01 y U05-T02 (PR 81 y 84), ya en `main`.

Bloque D del plan de U5 (Pasos 6 y 7), que entra **completo** en la demo (E). Esta tarea alimenta dos demos de §1 de `aidlc-docs/construction/plans/demo-kind-alcance.md`: el journey 7.4, que usa la variante proxy, y el journey 7.3, que usa los paquetes RT-3. Rige el ritmo RL-1 a RL-5 (§6): máximo 2 rondas, y solo un ROJO bloquea.

## Alcance

**Dentro:** los Pasos 6 y 7 del plan (`aidlc-docs/construction/plans/reference-model-code-generation-plan.md`, «Bloque D»), con su texto, su diseño y su aceptación, **sin recortes**:

- **Paso 6 — Variante proxy (RT-2).**
  - Búsquedas en el `feature_spec`:
    - `zona_vivienda`, con al menos 5 municipios por zona;
    - `canal_originacion_detalle`.
  - Etiqueta con dependencia parcial de esas búsquedas.
  - Disparidad agregada ≥ 10 pp, medida con la librería de U9 o con un doble mientras no exista.
  - `purpose = rt2-demo` en el manifiesto.
  - **5 paquetes**, con `rt2_run` de 1 a 5, `model_version_id` distintos y el mismo predictor.
  - Diseño: BR-U5-06, 14, 15. Historia: US-303.
  - Aceptación: `uv run pytest reference-model/tests/examples/test_proxy.py`. Debe comprobar:
    - disparidad del modelo base < 5 pp y de la variante ≥ 10 pp;
    - ninguna zona con menos de 5 municipios;
    - `municipality_code` no aparece en el `FeatureVector` que produce `derive`;
    - 5 `model_version_id` distintos, todos con el mismo predictor.
- **Paso 7 — Conjunto adversarial.**
  - 20 pares RT-1 (BR-U5-16).
  - 18 casos RT-4, que ya existen desde U05-T02 (BR-U5-17).
  - Paquetes RT-3 (a)–(d), según domain-entities §5 (BR-U5-18).
  - `adversarial/manifest.json`, con el resultado esperado de cada caso.
  - Propiedad PBT-U5-07.
  - Diseño: BR-U5-16..18. Historias: US-106, US-109, US-111.
  - Aceptación:
    - `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_adversarial.py`;
    - `uv run pytest reference-model/tests/examples/test_adversarial_manifest.py`: 42 casos, cada uno con su `expected`; `RT3-a`, `RT3-c` y `RT3-d` los rechaza el validador de manifiesto (la copia de U4 que dejó U05-T02), y `RT3-b` lo acepta.

Precisiones:
- **DD-1 (decisión del usuario):** la demo corre RT-2 con **1** versión del proxy, pero U5 genera las **5**, como dice el plan. Esta tarea genera las 5.
- **Librería de disparidad de U9:** todavía no existe. Usa un doble con la fórmula de disparidad del diseño de U9 (`aidlc-docs/construction/bias-monitoring/functional-design/`) y cita el BR que implementa. Queda reemplazado cuando exista U9 (candidata).
- **RT-3:** cada paquete alterado sale de un paquete válido, con su alteración documentada en el manifiesto adversarial (BR-U5-18). Que `RT3-b` pase el validador es intencional: el diseño espera que lo atrape más adelante la validación (`validacion_fallida`) o el runtime. Verifícalo en domain-entities §5 y cítalo.
- **RT-1:** los textos cubren instrucciones en español y en inglés, HTML y `<script>`, SQL, Markdown, Unicode engañoso (bidi y homoglifos) y uno de 2 000 caracteres (BR-U5-16). Todos son `ApplicationIn` válidas para U0.
- **Candidata F-08 de U05-T02, también entra:** la prueba `test_pbt_u5_03_the_counterexample_of_the_review_is_a_valid_case` usa el contraejemplo real de la ronda 1 de U05-T02 (ITI = 1,0, antigüedad = 1, ltv desde 0,9) y comprueba que `confidence` puede subir mientras `c_rango` no sube y `confidence ≤ c_rango`. Márcala atendida en `CANDIDATAS.md`.
- **`Makefile release`** genera también la variante proxy y el conjunto adversarial, o con un target aparte si tarda demasiado. Regístralo en la bitácora.
- **Plan:** marca `[x]` los Pasos 6 y 7, con `(U05-T03)`.

**Fuera:**
- El workflow de CI y la release firmada (Paso 8, diferido: T1 y T4).
- El procedimiento de entrega (Paso 9) y el cierre (Pasos 10 a 12).
- Cambiar BR-U5-12 o la calibración de U05-T02.

## Archivos de contexto

- `aidlc-docs/construction/plans/reference-model-code-generation-plan.md` (Bloque D)
- `aidlc-docs/construction/plans/demo-kind-alcance.md` (§1, DD-1 y §6)
- `aidlc-docs/construction/reference-model/functional-design/` (BR-U5-06, 14..18; PBT-U5-07; domain-entities §5)
- `aidlc-docs/construction/bias-monitoring/functional-design/` (fórmula de disparidad, para el doble)
- `aidlc-docs/construction/contracts/` (BR-U0-34, `derive` y `feature_spec`) y `contracts/python/vectra_contracts`
- `reference-model/` (lo que dejaron U05-T01 y U05-T02), `revisiones/U05-T02/` y `CANDIDATAS.md`

## Criterios de aceptación

- [ ] **CA-1** — Variante proxy.
  ```bash
  uv run pytest reference-model/tests/examples/test_proxy.py -v
  ```
  Esperado: pasan todas las viñetas de la aceptación del Paso 6, leyendo de disco los 5 paquetes generados.

- [ ] **CA-2** — Conjunto adversarial.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_adversarial.py -v && uv run pytest reference-model/tests/examples/test_adversarial_manifest.py -v
  ```
  Esperado:
  - PBT-U5-07 pasa;
  - el manifiesto tiene 42 casos, cada uno con su `expected`;
  - `RT3-a`, `RT3-c` y `RT3-d` son rechazados y `RT3-b` es aceptado.

- [ ] **CA-3** — Candidata F-08.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_envelope.py -v -k counterexample
  ```
  Esperado: pasa con el contraejemplo real.

- [ ] **CA-4** — `check` de la unidad y de U1.
  ```bash
  make -C reference-model check && make -C platform check
  ```
  Esperado: código 0 en los dos.

## Plan de pruebas

Rojo primero de cada criterio con una mutación. Por ejemplo:
- una zona con 4 municipios;
- `municipality_code` filtrado al `FeatureVector`;
- dos `rt2_run` con el mismo `model_version_id`;
- un par RT-1 que difiere en otro campo;
- `RT3-a` aceptado.

Registra todo en `bitacoras/U05-T03.md`.

## Notas

- Archivos que se modifican en su sitio: `reference-model/src/vectra_reference/{proxy,adversarial,package}.py`, `config/` (catálogo de zona y de canal), `Makefile`, `tests/` y el plan de U5.
- Los artefactos generados no se versionan: van a `.out/`.
- Hay dos revisores trabajando en paralelo sobre `identity-edge/` y `decision-registry/`. No toques esos directorios.
