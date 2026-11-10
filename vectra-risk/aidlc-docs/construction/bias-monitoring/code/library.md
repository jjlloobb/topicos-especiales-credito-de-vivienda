# Librería `vectra_disparity` — resumen (U9, Pasos 3 a 5)

Versión SemVer: **1.0.0** (`bias-monitoring/disparity/pyproject.toml` y `vectra_disparity.__version__`; NFR-U9-54). Solo biblioteca
estándar (`math`, `decimal`, `fractions`, `dataclasses`): el árbol de dependencias de runtime está vacío (P-U9-05).

## API pública

| Función | Módulo | Qué hace |
|---|---|---|
| `counts_from_records(records)` | `counts` | `dict[atributo, CountTable]` desde filas etiquetadas (`sexo`, `rango_edad`, `region`, `estrato`, `banda`, `outcome`). Solo `outcome = favorable` cuenta como favorable; `revision_requerida` y `desfavorable` no (BR-U9-01) |
| `counts_from_marginals(marginals)` | `counts` | Lo mismo desde los `MonitoringMarginalCount` de un rango (mapeos u objetos con `attribute`, `group`, `band`, `result`, `count`) |
| `disparity_by_band(counts, attribute, n_min)` | `disparity` | `AttributeResult`: celdas con supresión (P-U9-04), diferencia por banda con par extremo e intervalo de Newcombe, agregada ponderada con su intervalo y diferencia sin bandas (`population_difference_partial`) |
| `aggregate_lower_limit(counts, attribute, n_min, z=3,14)` | `disparity` | Límite inferior de la agregada del atributo con la z de Bonferroni de BR-U9-11 (regla R4); `None` si es «muestra insuficiente». Es lo que `freeze_rule` compara con el umbral, en **cada** atributo (F-03 opción (b), decisión del usuario del 2026-11-10; antes, solo el disparador) |
| `model_aggregate(results)` | `disparity` | Mayor agregada con valor y su atributo disparador (BR-U9-05); `None` si todas son insuficientes |
| `to_dict(value)` | `disparity` | Forma JSON de U0 (`Decimal` a cadena `Decimal4`, tuplas a listas); valida con `AttributeResult.model_validate` |
| `wilson_interval`, `newcombe_difference`, `quantize4` | `stats` | Wilson, Newcombe (método 10) y el redondeo a 4 decimales |

Los tipos de resultado (`CellResult`, `BandResult`, `AttributeResult`, `CountTable`, `CountCell`) son `dataclass` congeladas con
los mismos nombres de campo que los de U0 §9.4; la librería no importa `vectra_contracts`.

## Convenciones que el diseño no fijaba

- **Escala.** Tasas, diferencias, agregadas e intervalos son **proporciones** (la escala de `rate`): 5 pp = `0.0500`. Quien compare con
  el umbral lo divide: `threshold_pp / 100`. Los tipos de U0 solo exigen la forma `Decimal4`.
- **Redondeo.** Mitad hacia arriba a 4 decimales, y solo al final: los cálculos intermedios (comparaciones de tasas, pesos) son
  exactos con `fractions.Fraction`; los intervalos usan `float`. `combined_variance` devuelve `float` porque una varianza de ~1e-4 no
  cabe en 4 decimales; lo que se publica es el intervalo.
- **Empates del par extremo.** Con tasas iguales gana el grupo de menor nombre; siempre son dos grupos distintos.
- **`n_band`** suma las celdas suficientes de la banda sin `no_informado`, también en una banda sin diferencia (no pesa en la agregada).
- **`population_difference_partial`** es `true` si algún grupo distinto de `no_informado` tiene una celda insuficiente; ese grupo se
  excluye de la diferencia sin bandas.

## Simulación estadística (NFR-U9-53)

`bias-monitoring/tests/simulation/`, 10 000 repeticiones, semilla fija (`make -C bias-monitoring simulation`, 4 a 6 min). Desde
U09-T02 la simulación usa `vectra_bias.freeze_rule` (la regla de producción) y no la reimplementa.

**Cobertura del intervalo de Newcombe** (par fijo 0,55 vs 0,45, 100 casos cada uno): **94,7 %** (mínimo exigido 93 %).

**Regla de congelamiento medida: R4 sobre todos los atributos** (BR-U9-11, F-03 opción (b), decisión del usuario del 2026-11-10): congela
si **algún** atributo con agregada tiene un límite inferior, con `z = 3,14` (Bonferroni de una cola), **> 5 pp**. Antes (U09-T01, decisión del
2026-11-09) el límite era solo el del atributo disparador (la mayor agregada, BR-U9-05); la regla anterior a R4 (agregada > 5 pp y límite de
95 % > 0) congelaba el 97,4 % con 500 casos por celda. La simulación usa la librería real, 10 000 repeticiones, semilla fija, sin `xfail`.
La comparación de las dos columnas sale de `revisiones/U09-T02/busqueda-dstar.py condiciones 10000` (misma semilla y mismas muestras).

**Condición 1 — congelamientos falsos** con disparidad real 0 (todas las celdas con tasa 0,5), los cuatro atributos (2, 6, 6 y 6
grupos informados) y tres bandas:

| Casos por celda | 30 | 100 | 500 | 2 000 |
|---|---|---|---|---|
| Regla anterior (R0) | 100 % | 100 % | 97,4 % | 0,1 % |
| R4, solo el disparador (2026-11-09) | 56,11 % | 9,02 % | 0,01 % | 0 % |
| **R4 sobre todos los atributos, opción (b) (2026-11-10)** | 56,11 % | 9,02 % | **0,01 %** | **0 %** |

Exigido: ≤ 5 % con ≥ 500 casos por celda (cumple). Con celdas iguales, el atributo de la mayor agregada casi siempre tiene también el mayor
límite, así que las dos reglas dan las mismas cifras. **Limitación conocida** (la del par extremo): con 30 y 100 casos por celda R4 aún congela
falsamente (56 % y 9 %): el intervalo no corrige del todo la elección del par extremo entre 6 grupos con muestras chicas.

**Condición 2 — modelo base de U5** (4,61 pp medidos por la librería; tasas reales de `u5_counts.json`, las celdas de menos de 30
casos toman la tasa agrupada de su banda):

| Casos por celda | 30 | 50 | 100 |
|---|---|---|---|
| Regla anterior (R0) | 99,9 % | 100 % | 100 % |
| R4, solo el disparador (2026-11-09) | 0,80 % | 1,28 % | 1,06 % |
| **R4 sobre todos los atributos, opción (b) (2026-11-10)** | **0,80 %** | **1,28 %** | **1,07 %** |

Exigido: ≤ 5 % con 50 a 100 casos por celda y, en 30, ≤ 6 % (cumple).

**Condición 3 — variante proxy y D\*.** Con el lote `stratified` de BR-U12-06 (~1 500 casos: 250 por celda en `sexo` y 83 en los
otros tres atributos):
- la variante proxy **actual** de U5 (`u5_counts.json`, 25,41 pp de agregada por `region`; `t = 1` de la variante sintética) congela el **100 %** con la regla (b) (≥ 95 % exigido);
- **D\*** es la disparidad mínima de una variante proxy con la que se congela ≥ 95 %: la **agregada que mide la librería sobre los conteos de la variante debe ser ≥ 18,1 pp** (el cruce del 95 % está en ≈ 17,9 pp; en 18,14 pp congela el 95,58 %). En la disparidad real de la simulación (media por banda de max − min de las tasas reales del atributo disparador, sin ponderar por banda) son 15,9 pp. La variante sintética interpola entre el modelo base y el proxy de U5 (`t` = 0 y 1); `DSTAR_T = 0,69` (tasas en [0, 1]).

`DSTAR_T = 1,71` de U09-T01 se calibró con el proxy anterior de U5 (11,66 pp) como `t = 1`; con el proxy actual (25,41 pp) extrapolaba a 37,7 pp de
disparidad real. Se recalibró con (b) y el proxy actual. `revisiones/U09-T02/busqueda-dstar.py dstar` hace la búsqueda:

| agregada de la librería (pp) | 9,08 | 11,42 | 13,68 | 16,02 | 16,96 | 17,41 | 17,88 | 18,14 (D\*) | 18,38 | 20,71 | 25,41 (proxy actual) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `t` | 0,30 | 0,40 | 0,50 | 0,60 | 0,64 | 0,66 | 0,68 | 0,69 | 0,70 | 0,80 | 1,00 |
| congela con `stratified` | 16,2 % | 36,8 % | 65,0 % | 86,7 % | 90,9 % | 93,1 % | 94,8 % | 95,6 % | 96,2 % | 99,5 % | 100 % |

(Las cifras de 9,08 a 16,02 pp, 20,71 pp y 25,41 pp salen de 3 000 repeticiones; las de 16,96 a 18,38 pp, de 10 000, como la prueba.) Con la regla
del disparador (U09-T01) D\* era 17,5 pp: (b) pide 0,6 pp más porque evalúa el máximo de cuatro límites ruidosos.

**Requisito para U5 (U05-T05, cumplido):** la variante proxy de la demo lleva 25,41 pp por `region`, por encima de D\* = 18,1 pp (el requisito de U09-T01 era 17,5 pp).
El doble `tests/doubles/u5_counts.json` no cambia en U09-T02.

**Riesgo para U5 y U12.** `reference-model/tests/simulation/test_r4_freeze_rate.py` sigue midiendo con la regla del disparador sobre muestras reales de
`test`. Con (b) el modelo base solo puede congelar igual o más (el máximo de cuatro límites es ≥ el de uno); queda en `CANDIDATAS.md` (U5).

**Enmascaramiento de F-03** (caso determinista de `tests/unit/test_freeze_rule_examples.py`, no de la simulación: con 40 casos por celda la
elección del par extremo infla el límite de `region` y la simulación no lo muestra limpio): `region` con 5 grupos a 0,50 y 1 a 0,70 (40 casos por
celda en las 3 bandas; agregada 0,2000, límite R4 0,0132) y `sexo` con 0,50 y 0,60 (3 000 por celda; agregada 0,1000, límite R4 0,0768). El disparador
es `region`; con la regla del disparador no congela, con (b) congela por `sexo`.

**Cobertura y margen.** El intervalo de la agregada publicado (`aggregate_ci_95`, z = 1,96) no cambia. El ejemplo de BLM §3 con 6 pp
y 2 000 casos por celda no congela con R4 (límite 0,0315); con 12 pp sí (0,0918). La viñeta del Paso 6 del plan («2 000 casos y 6 pp → `freeze`») cede ante la BLM corregida.

## Cobertura y mutación

Cobertura de ramas **100 %** en `stats`, `counts` y `disparity` (`make -C bias-monitoring coverage`). `mutmut` queda diferido por la
demo (T3, enmienda §3): la dependencia está instalada, pero no se corre.
