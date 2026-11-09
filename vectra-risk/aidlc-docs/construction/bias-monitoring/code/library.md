# Librería `vectra_disparity` — resumen (U9, Pasos 3 a 5)

Versión SemVer: **1.0.0** (`bias-monitoring/disparity/pyproject.toml` y `vectra_disparity.__version__`; NFR-U9-54). Solo biblioteca
estándar (`math`, `decimal`, `fractions`, `dataclasses`): el árbol de dependencias de runtime está vacío (P-U9-05).

## API pública

| Función | Módulo | Qué hace |
|---|---|---|
| `counts_from_records(records)` | `counts` | `dict[atributo, CountTable]` desde filas etiquetadas (`sexo`, `rango_edad`, `region`, `estrato`, `banda`, `outcome`). Solo `outcome = favorable` cuenta como favorable; `revision_requerida` y `desfavorable` no (BR-U9-01) |
| `counts_from_marginals(marginals)` | `counts` | Lo mismo desde los `MonitoringMarginalCount` de un rango (mapeos u objetos con `attribute`, `group`, `band`, `result`, `count`) |
| `disparity_by_band(counts, attribute, n_min)` | `disparity` | `AttributeResult`: celdas con supresión (P-U9-04), diferencia por banda con par extremo e intervalo de Newcombe, agregada ponderada con su intervalo y diferencia sin bandas (`population_difference_partial`) |
| `aggregate_lower_limit(counts, attribute, n_min, z=3,14)` | `disparity` | Límite inferior de la agregada del atributo con la z de Bonferroni de BR-U9-11 (regla R4); `None` si es «muestra insuficiente». Es lo que `freeze_rule` compara con el umbral, sobre el atributo disparador |
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

`bias-monitoring/tests/simulation/`, 10 000 repeticiones, semilla fija (`make -C bias-monitoring simulation`, 1 min).

**Cobertura del intervalo de Newcombe** (par fijo 0,55 vs 0,45, 100 casos cada uno): **94,7 %** (mínimo exigido 93 %).

**Regla de congelamiento medida: R4** (BR-U9-11, decisión del usuario del 2026-11-09): congela si el límite inferior de la agregada
del atributo disparador, con `z = 3,14` (Bonferroni de una cola, 0,05 / 60 comparaciones; cuantil exacto 3,1440), es **> 5 pp**. La
regla anterior (agregada > 5 pp y límite inferior de 95 % > 0) congelaba el 97,4 % con 500 casos por celda. La simulación usa la
librería real (`aggregate_lower_limit`), 10 000 repeticiones, semilla fija, sin `xfail`.

**Condición 1 — congelamientos falsos** con disparidad real 0 (todas las celdas con tasa 0,5), los cuatro atributos (2, 6, 6 y 6
grupos informados) y tres bandas:

| Casos por celda | 30 | 100 | 500 | 2 000 |
|---|---|---|---|---|
| Regla anterior (R0) | 100 % | 100 % | 97,4 % | 0,1 % |
| **R4** | 56,1 % | 9,0 % | **0,01 %** | **0 %** |

Exigido: ≤ 5 % con ≥ 500 casos por celda (cumple). **Limitación conocida** (la del par extremo): con 30 y 100 casos por celda R4 aún
congela falsamente (56 % y 9 %): el intervalo no corrige del todo la elección del par extremo entre 6 grupos con muestras chicas.

**Condición 2 — modelo base de U5** (4,61 pp medidos por la librería; tasas reales de `u5_counts.json`, las celdas de menos de 30
casos toman la tasa agrupada de su banda):

| Casos por celda | 30 | 50 | 100 |
|---|---|---|---|
| Regla anterior (R0) | 99,9 % | 100 % | 100 % |
| **R4** | **0,8 %** | **1,3 %** | **1,1 %** |

Exigido: ≤ 5 % con 50 a 100 casos por celda y, en 30, ≤ 6 % (cumple; el 5,2 % de la exploración era una aproximación de Wald, la
librería da 0,8 %).

**Condición 3 — D\* (requisito para U5).** Con el lote `stratified` de BR-U12-06 (~1 500 casos: 250 por celda en `sexo` y 83 en los
otros tres atributos) la variante proxy de U5 de hoy (11,66 pp) congela solo el **43,4 %**. D\* es la disparidad mínima de una variante
proxy con la que R4 congela ≥ 95 %: la **agregada que mide la librería sobre los conteos de la variante debe ser ≥ 17,5 pp** (el
cruce del 95 % está en 17,4 pp; en 17,47 pp congela el 95,35 %). En la disparidad real de la simulación (media por banda de max − min
de las tasas reales del atributo disparador, sin ponderar por banda) son 15,9 a 16,0 pp. La variante sintética interpola entre el modelo base y el proxy
de U5 (`t` = 0 y 1) y extrapola (`t` = 1,71, tasas en [0, 1]); `revisiones/U09-T01/busqueda-dstar-ronda-3.py` hace la búsqueda:

| agregada de la librería (pp) | 11,66 (proxy actual) | 13,98 | 15,63 | 17,42 | 17,47 (D\*) | 18,25 | 20,04 |
|---|---|---|---|---|---|---|---|
| congela con `stratified` | 43,4 % | 72,6 % | 88,3 % | 95,0 % | 95,35 % | 97,4 % | 99,1 % |

(Las cifras de 11,66 a 20,04 pp salen de 3 000 repeticiones, salvo las de 17,42 y 17,47 pp, de 10 000; la prueba usa 10 000.)

**Requisito para U5 (U05-T05):** la variante proxy de la demo debe llevar una disparidad por `region` (el atributo disparador de las
dos variantes) de **al menos 17,5 pp** medida con `disparity_by_band` sobre el dataset de RT-2, o RT-2 debe usar un lote mayor. El
doble `tests/doubles/u5_counts.json` no cambia en U09-T01.

**Cobertura y margen.** El intervalo de la agregada publicado (`aggregate_ci_95`, z = 1,96) no cambia. El ejemplo de BLM §3 con 6 pp
y 2 000 casos por celda ya no congela con R4 (límite ≈ 3,1 pp); con 12 pp sí.

## Cobertura y mutación

Cobertura de ramas **100 %** en `stats`, `counts` y `disparity` (`make -C bias-monitoring coverage`). `mutmut` queda diferido por la
demo (T3, enmienda §3): la dependencia está instalada, pero no se corre.
