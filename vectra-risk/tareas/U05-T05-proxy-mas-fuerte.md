# U05-T05 — Variante proxy más fuerte para la regla R4 y librería real de U9 en `reference-model`

**Unidad:** U5 `reference-model`
**Historias que implementa:** US-303 (modelo proxy, RT-2). Ninguna nueva.
**Depende de:** U09-T01 (PR #98, en `main`): la librería `vectra_disparity` y la regla R4 de BR-U9-11.
**Rama:** `tarea/U05-T05`, desde `origin/main`. Puede correr en paralelo con U04-T05 (que toca `governance/`) y con U06-T01 (que crea `model-serving/`). Tú no toques esos directorios.

Retrabajo del Paso 6 de U5, que ya estaba cerrado para la demo (U05-T03 y U05-T04). Lo pide el arbitraje de la ronda 2 de U09-T01 (`revisiones/U09-T01/arbitraje-ronda-2.md`, decisión del usuario del 2026-11-09): con la regla R4, la variante proxy de hoy (11,66 pp) solo congela el 43 % de las veces con el lote `stratified` de RT-2. El usuario eligió **una variante proxy más fuerte**, en vez de un lote más grande o de aceptar esa tasa. RT-2 conserva los ~1 500 casos `stratified` y sus 30 min.

Rige RL-1 a RL-5 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda.

---

## Alcance

**Dentro:**

1. **Librería real de U9 en `proxy.py`.** `disparity_by_attribute` y `model_aggregate` son hoy un doble de `vectra_disparity` (candidata de U05-T03 en `CANDIDATAS.md`). Se reemplazan por `counts_from_records` + `disparity_by_band` (y la agregada de la librería), declarando `vectra-disparity` como dependencia del workspace.
   - El reemplazo mide con el `outcome` de BR-U7-04/05: `revision_requerida` **no** es favorable (BR-U9-01). Nunca con `p < cutoff`.
   - **Rojo primero:** antes de tocar la variante, con la librería real, las cifras de hoy deben reproducirse: 4,61 pp la base y 11,66 pp la variante (`aidlc-docs/construction/bias-monitoring/code/library.md`). Si no coinciden, **detente y repórtalo**.
2. **Diseño, BR-U5-14** (decisión del usuario, arbitraje de la ronda 2 de U09-T01). Se escribe así, con la fecha y la cita:
   - la variante proxy produce una disparidad agregada por `region` **≥ 18 pp**, medida con `disparity_by_band` de la librería de U9 sobre `validation`. Es D\* = 17,5 pp de `library.md` con el margen que pide el revisor (F-05 de la ronda 3);
   - **y** R4 (BR-U9-11, `aggregate_lower_limit` con `Z_FREEZE`) congela la variante en **≥ 95 %** de muestras `stratified` de BR-U12-06 (~1 500 casos de `test`, ≥ 30 por celda de U9), sacadas del dataset real de U5, no del reparto idealizado de la simulación (F-05).
   - Si no se cumple, la entrega de la variante falla.
   - El modelo base sigue con **< 5 pp** (BR-U5-06) y R4 **no** lo congela en más del 5 % de esas mismas muestras.
   - Actualiza la nota del Paso 6 del plan de U5 (`reference-model-code-generation-plan.md`) con «retrabajo en U05-T05, BR-U5-14 enmendada». La casilla sigue `[x]`.
3. **Variante más fuerte.** Ajusta en `config/generator.yaml` la dependencia de la etiqueta respecto de `zona_vivienda` y `canal_originacion_detalle` (Paso 6), sin tocar BR-U5-15: el municipio nunca llega al `FeatureVector`, cada zona tiene al menos 5 municipios y se mantienen las 5 versiones con `rt2_run` de 1 a 5 y el mismo predictor. Documenta en la bitácora la búsqueda del parámetro (valores probados y su agregada).
4. **Medición de la tasa de congelamiento.** Una prueba marcada `simulation` en `reference-model/tests/` que saca N muestras `stratified` (N ≥ 2 000, semilla fija) del dataset `test` de U5 con la composición de BR-U12-06, aplica R4 con la librería real y comprueba ≥ 95 % para la variante y ≤ 5 % para la base. El reparto de casos por celda sale del muestreo real, no de celdas iguales.
5. **Paquetes y entrega.** Regenera los 5 paquetes de la variante con `release.py` y el procedimiento de `reference-model/docs/release.md`. Los `model_version_id` cambian: actualízalos donde estén escritos (documentación de U5, `cierre-demo.md`) y deja la lista en la bitácora.
6. **Doble de U9.** Regenera `bias-monitoring/tests/doubles/u5_counts.json` con `uv run python bias-monitoring/tests/doubles/generate_u5_counts.py` (lo autoriza `library.md` y la candidata de U09-T01). Después, `make -C bias-monitoring check` debe seguir en 0; si una prueba de U9 cambia de resultado con los conteos nuevos, **detente y repórtalo**: no ajustes umbrales de U9.
7. **Cierre de U5.** Agrega a `aidlc-docs/construction/reference-model/evidence/cierre-demo.md` una sección «Retrabajo U05-T05» con las cifras nuevas (agregada de la base y de la variante, tasas de congelamiento con R4) y los ids nuevos. Marca resueltas en `CANDIDATAS.md` la del doble de U05-T03 y las dos de U05-T05 (U09-T01, rondas 3).

**Fuera:**

- La regla R4, `Z_FREEZE`, D\* y cualquier archivo de `bias-monitoring/` salvo `u5_counts.json` (que se regenera con su script).
- F-03 de U09-T01 (R4 solo sobre el atributo disparador): es una pregunta de diseño abierta para el Bloque C de U9. Mide aquí sobre `region`, que es el disparador en la demo.
- Los paquetes RT-1, RT-3 y RT-4 y el modelo base: no cambian. Si el cambio de configuración los altera, **detente y repórtalo**.
- Registro en governance, MinIO real o kind (AUTONOMIA-01).

---

## Archivos de contexto

- `revisiones/U09-T01/arbitraje-ronda-2.md`, `ronda-3.md` (F-05) y `arbitraje-ronda-3.md`.
- `aidlc-docs/construction/bias-monitoring/code/library.md` (condición 3, D\*, tabla de agregadas y tasas) y `aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md` (BR-U9-01 a 05 y 11).
- `bias-monitoring/disparity/src/vectra_disparity/` y `bias-monitoring/tests/simulation/test_statistical_validation.py` (cómo se mide R4).
- `aidlc-docs/construction/reference-model/functional-design/business-rules.md` (BR-U5-06, 14 y 15) y el plan de U5 (Paso 6).
- `aidlc-docs/construction/system-verification/functional-design/business-rules.md` (BR-U12-06, lote `stratified`).
- `reference-model/src/vectra_reference/proxy.py`, `config/generator.yaml`, `tests/examples/test_proxy.py`, `docs/release.md`.
- `tareas/U05-T03-proxy-y-adversarial.md`, `bitacoras/U05-T03.md` y `CANDIDATAS.md` (entradas de U5 y de U05-T05).

---

## Criterios de aceptación

Desde `vectra-risk/`.

- [ ] **CA-1** — Librería real y rojo primero.
  ```bash
  ! grep -nE "def (disparity_by_attribute|model_aggregate)" reference-model/src/vectra_reference/proxy.py
  grep -n "vectra_disparity" reference-model/src/vectra_reference/proxy.py
  ```
  Esperado: el doble ya no existe y `proxy.py` importa la librería. La bitácora muestra la corrida con la librería real sobre la configuración vieja: 4,61 pp y 11,66 pp.

- [ ] **CA-2** — Aceptación del Paso 6 con BR-U5-14 enmendada.
  ```bash
  uv run pytest reference-model/tests/examples/test_proxy.py -v
  ```
  Esperado: pasan, con las cifras impresas: base < 5 pp; variante ≥ 18 pp por `region`; ninguna zona con < 5 municipios; `municipality_code` fuera del `FeatureVector`; 5 `model_version_id` distintos con el mismo predictor.

- [ ] **CA-3** — Tasa de congelamiento con R4 sobre muestras `stratified` reales.
  ```bash
  uv run pytest reference-model/tests -m simulation -v -s
  ```
  Esperado: variante ≥ 0,95 y base ≤ 0,05, con N ≥ 2 000 y la semilla impresas.

- [ ] **CA-4** — Diseño.
  ```bash
  grep -n "BR-U5-14" -A6 aidlc-docs/construction/reference-model/functional-design/business-rules.md
  ```
  Esperado: 18 pp, la condición de R4 con ≥ 95 %, la fecha y la cita del arbitraje.

- [ ] **CA-5** — U9 sigue verde con los conteos nuevos.
  ```bash
  git diff --stat origin/main -- bias-monitoring/ && make -C bias-monitoring check
  ```
  Esperado: en `bias-monitoring/` solo cambia `tests/doubles/u5_counts.json`, y el check termina en 0.

- [ ] **CA-6** — `check` de la unidad y de U1 (RL-4).
  ```bash
  make -C reference-model check && make -C platform check
  ```
  Esperado: código 0 en los dos.

- [ ] **CA-7** — Cierre: `cierre-demo.md` con la sección «Retrabajo U05-T05» y `CANDIDATAS.md` con las tres entradas marcadas resueltas.

---

## Notas

- Archivos que se modifican en su sitio: `reference-model/` (código, configuración, pruebas, documentación), `reference-model/pyproject.toml`, el `pyproject.toml` raíz y `uv.lock` si hace falta, `bias-monitoring/tests/doubles/u5_counts.json`, BR-U5-14, el plan de U5, `cierre-demo.md` de U5 y `CANDIDATAS.md`.
- **Bitácora:** `bitacoras/U05-T05.md`, con la búsqueda del parámetro, las cifras antes y después y los `model_version_id` nuevos.
