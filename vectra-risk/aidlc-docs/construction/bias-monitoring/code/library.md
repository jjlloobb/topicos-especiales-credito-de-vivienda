# Librería `vectra_disparity` — resumen (U9, Pasos 3 a 5)

Versión SemVer: **1.0.0** (`bias-monitoring/disparity/pyproject.toml` y `vectra_disparity.__version__`; NFR-U9-54). Solo biblioteca
estándar (`math`, `decimal`, `fractions`, `dataclasses`): el árbol de dependencias de runtime está vacío (P-U9-05).

## API pública

| Función | Módulo | Qué hace |
|---|---|---|
| `counts_from_records(records)` | `counts` | `dict[atributo, CountTable]` desde filas etiquetadas (`sexo`, `rango_edad`, `region`, `estrato`, `banda`, `outcome`). Solo `outcome = favorable` cuenta como favorable; `revision_requerida` y `desfavorable` no (BR-U9-01) |
| `counts_from_marginals(marginals)` | `counts` | Lo mismo desde los `MonitoringMarginalCount` de un rango (mapeos u objetos con `attribute`, `group`, `band`, `result`, `count`) |
| `disparity_by_band(counts, attribute, n_min)` | `disparity` | `AttributeResult`: celdas con supresión (P-U9-04), diferencia por banda con par extremo e intervalo de Newcombe, agregada ponderada con su intervalo y diferencia sin bandas (`population_difference_partial`) |
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

**Tasa de congelamientos falsos** de BR-U9-11 (agregada del modelo > 5 pp **y** límite inferior > 0) con disparidad real 0 (todas las
celdas con tasa 0,5), los cuatro atributos (2, 6, 6 y 6 grupos informados) y tres bandas:

| Casos por celda | 30 | 100 | 500 | 2 000 |
|---|---|---|---|---|
| Congelamientos falsos | 100 % | 100 % | **97,4 %** | 0,1 % |

**Hallazgo.** El diseño exige ≤ 5 % con ≥ 500 casos por celda (BLM §3) y la medición da 97,4 % con 500. La causa es la que el BLM
anticipaba para muestras chicas, pero llega mucho más lejos: el intervalo de la agregada (BR-U9-04) se construye con el intervalo de
Newcombe del **par extremo**, que se elige después de ver los datos entre hasta 6 grupos; con 500 casos por celda el rango esperado de
6 tasas es ≈ 5,7 pp (2,53 σ, σ = 2,2 pp), ya sobre el umbral de 5 pp, y el intervalo, que trata el par como fijado de antemano, no
incluye el 0. Con 2 000 casos el rango esperado baja a ≈ 2,8 pp y la tasa cae a 0,1 %. La prueba `test_false_freeze_rate_is_at_most_5_percent_with_500_cases_per_cell`
queda como `xfail(strict=True)` para que `make check` documente el hallazgo sin ocultarlo; si se corrige la regla, pasará a XPASS y fallará
hasta que se quite la marca. Hace falta una decisión de diseño (por ejemplo, exigir más muestra por celda, un intervalo que corrija la
elección del par extremo o un umbral mayor) antes del Bloque C (`freeze_rule`).

## Cobertura y mutación

Cobertura de ramas **100 %** en `stats`, `counts` y `disparity` (`make -C bias-monitoring coverage`). `mutmut` queda diferido por la
demo (T3, enmienda §3): la dependencia está instalada, pero no se corre.
