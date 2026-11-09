# Ronda 1 — U05-T05

VEREDICTO: NO-VERDE

Rama `tarea/U05-T05`, punta `72c84d6`, base `bb86d71` (= `origin/main`). Worktree limpio antes y después de la revisión (`git status --short` vacío). Este informe es el único archivo nuevo y no tiene commit.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Librería real, sin el doble | `! grep -nE "def (disparity_by_attribute\|model_aggregate)" .../proxy.py; grep -n vectra_disparity .../proxy.py` | pasa (rc 0; import en la línea 35). Rojo primero: la bitácora registra 4,61 y 11,66 pp. Además mi release de `bb86d71` da 4,6119 y 11,6579 pp |
| 2 | Paso 6 con BR-U5-14 enmendada | `uv run pytest reference-model/tests/examples/test_proxy.py -v -s` | pasa: 23 passed. Imprime base 4,61 pp y run-1..5 25,41 pp (`region`) |
| 3 | Tasa de congelamiento R4 | `uv run pytest reference-model/tests -m simulation -v -s` | pasa: 2 passed (30 min con la máquina cargada). `samples=2000 seed=20261109`, variante 0,9945 y base 0,0050 |
| 4 | Diseño | `grep -n "BR-U5-14" -A6 .../business-rules.md` | pasa: 18 pp, R4 ≥ 95 %, fecha 2026-11-09 y cita del arbitraje |
| 5 | U9 verde y solo los archivos autorizados | `git diff --stat origin/main -- bias-monitoring/ && make -C bias-monitoring check` | pasa: cambian solo `u5_counts.json` y `test_disparity_examples.py`, como autorizó el orquestador. rc 0 (34 + 43 + 6 passed; dstar=0,3768) |
| 6 | `check` de U5 y U1 | `make -C reference-model check && make -C platform check` | pasa: 141 passed y 2 deselected, cobertura 92,93 % y `confidence.py` 100 %. `platform` rc 0 (pass 335, fail 0) |
| 7 | Cierre | lectura de `cierre-demo.md` y `CANDIDATAS.md` | la sección y las tres marcas están, pero el contenido no es fiel (F-01 y F-02) |
| — | `--all` (§6 con la enmienda) | `python3 platform/tests/test_traceability.py --all`, en la rama y en `git archive bb86d71` | pasa: ningún fallo nuevo. reference-model tiene 11 ids trazados. Los fallos de U4 y U9 ya existían en la base |

## Hallazgos
### F-01 · ROJO · `aidlc-docs/construction/reference-model/evidence/cierre-demo.md:45,53` y la bitácora («RT-1/3/4 y modelo base inalterados») · El modelo base y RT-3 sí cambian respecto de `main`, y la evidencia dice lo contrario
El apartado «Fuera» de la tarea dice: «Los paquetes RT-1, RT-3 y RT-4 y el modelo base: no cambian… detente y repórtalo». El codificador comparó la configuración vieja con la nueva, **las dos con el código nuevo**. No comparó contra `main`. Corrí `python -m vectra_reference.release` sobre `git archive bb86d71` y sobre la rama, cada uno con su `--out` en el scratchpad. Después comparé el SHA-256 de cada archivo (sin contar `proxy/`):
- `package/manifest.json`: `"disparity_pp": 4.6119` pasa a `4.61`, porque la librería cuantiza a `Decimal4`. Los metadatos entran en el hash del id, así que **`model_version_id` del modelo base pasa de `mv-2026-01-01-51241dc4` (main) a `mv-2026-01-01-8a98ab02`**. Cambian también `domain_envelope.json`, `explainer.json`, `feature_dictionary.json` y `feature_spec.json`, porque llevan el id dentro.
- RT-3: cambian los 4 paquetes (`altered_model_version_id` pasa de `cf3f3cce` a `d8ee71f9`) y `adversarial/manifest.json`. Los casos RT-1 y RT-4 son iguales salvo la referencia al id base.
- Idénticos: `predictor.json`, `background.csv`, los 3 parquet y `reference-policy.json`.
- En el repo, `u5_counts.json` ya registra el cambio: `"base_run"` pasa de `51241dc4` a `8a98ab02`. Lo mismo dicen U05-T03 ronda 2 y la bitácora de U05-T04, que tenían `51241dc4`.

Aun así, `cierre-demo.md` afirma que el id base «sigue siendo `mv-2026-01-01-8a98ab02`» y que el paquete base y el conjunto adversarial son «idénticos byte a byte a los de antes». Los ids «anteriores» de la variante (`986689d3`…) tampoco son los de main (`7241d354`, `fa147805`, `d2baab53`, `2a799484`, `ea69c19d`). Son ids intermedios de la propia rama. La evidencia es falsa y el punto de detención no se activó. La decisión es del orquestador: (a) que `disparity_pp` del manifiesto no dependa de la cuantización y vuelva a 4,6119, para conservar el id; o (b) aceptar los ids nuevos del modelo base y de RT-3 con decisión explícita. En los dos casos hay que corregir `cierre-demo.md`, la bitácora y las listas de ids «antes».
Transcripciones: `rel-base.txt`, `rel-head.txt`, `out-base.sha` y `out-head.sha`.

### F-02 · NARANJA · `cierre-demo.md:55`, `CANDIDATAS.md` (entrada nueva de U9) y `u5_counts.json` (`u5_commit`) · Hay afirmaciones de evidencia desactualizadas o con procedencia incorrecta (barrido de clase)
- `cierre-demo.md`, «Pendiente de U9 (no se tocó)»: dice que `make -C bias-monitoring check` «ya no termina en 0». Por la decisión del orquestador la prueba ya se cambió, y yo lo corrí con rc 0.
- `CANDIDATAS.md`: la entrada nueva dice «**no se tocó**… Cambiar la cifra fijada por 25,41 pp y renombrar la prueba». Eso ya está hecho. Solo sigue en pie la parte de `DSTAR_T`.
- `u5_counts.json`: `"u5_commit": "bb86d713…"`. Los conteos salieron del código sin commit de esta tarea, no de `bb86d71`, así que la procedencia es falsa.

## Juicios pedidos por el orquestador
1. **Muestreo `stratified`.** El `test` de U5 tiene 18 000 filas y 65 celdas de U9. Cuatro de ellas no llegan a 30 casos en todo `test`: `estrato 6/lt_20` (12), `56-65/lt_20` (21), `66+/20_30` (4) y `66+/gt_30` (10). Todas las muestras tienen esas mismas 4 celdas bajo 30, y ninguna otra (300 de 300). U9 descarta las celdas con < 30 (`n_min`), así que tomar «los que hay» **no cambia R4** y la conclusión se sostiene. Es una interpretación razonable del lote de U12, que aún no existe. Pero muestra que **BR-U12-06 no se puede cumplir al pie de la letra con este `test`**. Se reporta a U12 (ver candidatas).
2. **Reproducibilidad.** Reproduje 25,41 pp, 0,9945 y 0,0050 con la semilla de la prueba. Con otras semillas y N=2 000: la variante da 0,9975 (semilla 1) y 0,9960 (semilla 42), y la base 0,0045 (semilla 1). Con 300 muestras (semilla 99), el límite R4 de la variante tiene p5 = 8,59 pp y p50 = 13,87 pp frente al umbral de 5 pp. En la base, p95 = 2,46 pp. El margen es robusto y no depende de la semilla. La búsqueda del parámetro usó otra semilla (7), así que atiende F-05.
3. **Invariantes.** Se mantienen el predictor, la política y los 3 parquet byte a byte, y BR-U5-15 (las pruebas de CA-2 pasan: zonas ≥ 5 municipios, `municipality_code` fuera del `FeatureVector`, 5 ids con el mismo predictor). **No se mantienen** los JSON del paquete base ni RT-3 (F-01).
4. **BR-U5-14.** Solo cambia ese párrafo de `business-rules.md`, conforme al arbitraje. La nota del Paso 6 dice «retrabajo en U05-T05, BR-U5-14 enmendada» y la casilla sigue `[x]`.
5. **`outcome`.** `counts_of` envía `outcome` a `counts_from_records`, que cuenta como favorable solo `favorable` (`counts.py:70`). `p < cutoff` solo aparece dentro de `outcome_of` (BR-U7-04/05), después de usura y baja confianza. Correcto.

## Notas AMARILLO (no bloquean)
- `test_r4_freeze_rate.py:75-79` reimplementa R4 (disparador más `aggregate_lower_limit > 0,05`) porque la librería todavía no tiene `freeze_rule` (Bloque C). Es la misma forma que usa `test_statistical_validation.py:93-102`. Cuando exista `freeze_rule`, hay que usarla.
- `assert SAMPLES >= 2_000` es tautológico.

## Tareas candidatas (defectos reales fuera de alcance)
- **U12, BR-U12-06:** con el `test` de U5 (18 000 filas), 4 de 65 celdas de U9 no llegan a 30 casos (`66+/20_30` tiene 4). Hay que precisar «≥ 30 en cada celda **alcanzable**», o ampliar `test`, o muestrear de otra partición.
- **U5/U9, modelo base sobre `test`:** la agregada por `region` del modelo base en todo `test` es **5,51 pp**, sobre el límite de 5 de BR-U5-06, que solo se mide en `validation` (4,61). Su límite R4 con 18 000 casos es 1,12 pp y no congela. Con ventanas grandes, el límite tiende a unos 5,5 pp y R4 congelaría el modelo base. Esto amplía la candidata del margen de 0,39 pp.
- La recalibración de `DSTAR_T` sigue como candidata (ya registrada).

## Rutas de transcripciones largas
En `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/`:
- `ca3.txt`, `u05t05-ca2.txt`, `u05t05-bias-check.txt`, `u05t05-ref-check.txt` y `u05t05-platform.txt`
- `rel-base.txt`, `rel-head.txt`, `out-base.sha` y `out-head.sha` (F-01)
- `seeds.py` y `seeds-out.txt` (semillas, celdas y límites)
- `trace-head.txt` y `trace-base.txt`
