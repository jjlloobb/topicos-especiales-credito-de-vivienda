# Resumen de la lógica — U11 `product-metrics` (Paso 5, U11-T01)

Código en `vectra-risk/product-metrics/src/vectra_product/`. Lo que hay en esta tarea: `config`, `params`, `model`, `compute`,
`noise`, `reader` y `state`. `scheduler`, `collector` y `main` son módulos vacíos con docstring (Paso 6, U11-T02).

## Firma real de `compute` (P-1, opción a)

El plan decía `compute(entries, params, now)`. Los meses cerrados **no** viven como entradas (NFR-U11-12), así que con solo 35 días
de entradas `compute` no podría producir los 6 `month`. La firma real es:

```python
compute(snapshot: Snapshot, params: Params, now: datetime) -> BusinessMetrics
```

`Params` y `Snapshot` viven en `model.py` (para que `compute` no importe nada con E/S; `params.py` los carga y valida y reexporta `Params`).
`Snapshot` es lo que `state` entrega: `entries` (las decisiones y excluidas de los últimos 35 días, por `seq`) y
`months` (los contadores de cada mes, por índice de mes). `compute` es una función pura, sin E/S (import-linter lo comprueba:
`model`, `compute` y `noise` no importan `httpx`, `asyncio`, `yaml`, `prometheus_client` ni `vectra_common`).

## Plegado de los meses (`compute.fold`, `compute.absorb`)

- `fold(counts, decision)` suma una decisión atribuible en un `Counter` de llaves `(etiqueta, canal, resultado, modelo | decisión)`.
  Las etiquetas son `DEN` (atribuibles), `NUM` (numerador de la North Star), `BRK` (desglose por `decision`), `SUS` (`sigue`) y `VIEW`
  (explicación vista). De esos contadores salen los conteos con todos los cortes y las razones totales o por un corte.
- `absorb(entries, months, entry, today)` es lo que `state` llama con cada entrada: la pliega en el contador de **su mes** y, si su
  `decided_at` es de los últimos 35 días, la guarda en el estado. Pliega el mes aunque todavía no sea de los cerrados (el reloj avanza
  entre pasadas y el mes en curso se cierra sin que nadie lo relea); no pliega nada más viejo que el sexto mes cerrado.
- La lectura incremental también pliega en los contadores de mes. El diseño dice que una decisión tardía de un mes cerrado entra
  «en la recomputación del día siguiente»; plegarla al leerla es más fresco y conserva la equivalencia exigida por PBT-U11-02, que
  compara contra una recomputación completa sobre la unión, meses incluidos. La pasada completa diaria sigue siendo la que corrige
  cualquier deriva y reconstruye los contadores desde cero.
- `snapshot_of(entries, now)` es la instantánea de una pasada completa sobre una colección de entradas (sin repetir `seq`): es el
  oráculo de PBT-U11-02 y el generador de instantáneas de PBT-U11-01, 03, 06 y 07.

## `compute`

Periodos (BR-U11-08), todos en días UTC completos y sin el día en curso:

| Periodo | Rango |
|---|---|
| `day` | ayer |
| `30d` | los 30 días que terminan ayer |
| `month_to_date` | del día 1 del mes en curso a ayer; el día 1 de cada mes **no** se publica |
| `month` | los 6 meses cerrados anteriores, con `month="AAAA-MM"`; siempre los 6, con conteos en 0 si no hay datos |

Cada periodo trae `north_star` (celdas `(canal, resultado, modelo)` con numerador y denominador, desglose `(kind, canal,
resultado)`, razón total y razón por un solo corte), `sustained` (celdas `(canal, resultado)`, total y por un corte) y
`unattributable` (sin dato en los meses). Una razón con denominador 0 tiene `rate = None` (no 0). Las razones por corte son la suma
de los conteos de las celdas, nunca un promedio de razones (PBT-U11-07).

También: `explanation_view` (ventana de 7 días que termina ayer, total y por canal), `explanation_view_daily` (la ventana de 7 días
que termina cada día con la ventana completa en el estado), `noise_days_below_floor`, `origination` (por día de `evaluated_at`:
cuenta, p50, p80, p95 por rango más cercano y la fracción bajo el target), `invalid_entries` (ventana de 30 días) y `degraded`
(más del 1 % de excluidas sobre las entradas de esa ventana; exactamente 1 % no degrada).

Exclusiones (`model.parse_entry`, BR-U11-10): valor fuera del catálogo de U0 (`decision`, `used_factors` con las reglas de
`check_used_factors`, `channel`, `outcome`, `actor_role`), `actor_role ≠ analista`, `decided_at > recorded_at + 5 min` y un campo
obligatorio ausente o con el tipo equivocado. La excluida conserva su `seq` (que va solo al log) y el día de `decided_at` (o el de
`recorded_at`, o ninguno). `recorded_at` solo interviene en el margen de 5 min: el resultado no depende de él (PBT-U11-03).
Una `recommendation` nula es una decisión válida y no atribuible.

## `days_below_floor` (`noise.py`)

`days_below_floor(windows, floor, min_decisions)` recibe las ventanas de 7 días que terminan cada día (de la más vieja a la que
termina ayer) y cuenta hacia atrás: menos de N decisiones no suma ni reinicia; tasa < F suma; tasa ≥ F para. F se compara como el
decimal del archivo (`Fraction(repr(floor))`): una tasa exactamente igual a F no cuenta como bajo el piso.

Como la ventana es móvil, «tres días seguidos bajo el piso» son tres ventanas consecutivas. Las pruebas de ejemplo de la tarea
(50 decisiones con tasa 0,5 → 3; 40 decisiones → no suma) se armaron con las decisiones de un solo día, de modo que las tres
ventanas tengan exactamente 50 o 40; con 40 decisiones en **cada** uno de los 3 días, las ventanas de los dos últimos ya suman 80 y
120 (≥ N) y la cuenta es 2 (`test_with_7_day_windows_40_decisions_on_each_of_3_days_reach_n_from_the_second_day`).

## `reader` y `state`

- `reader`: `GET /v1/entries?projection=metrics&entry_type=human_decision&limit=…&seq_after=…&recorded_from=…` (la ruta sale del
  contrato de U0), con `deps.call` (timeout 5 s, sin reintentos), el breaker de U0 en modo `consecutive_failures` (3, 60 s, 1) y el
  token de `vectra_common.service_token`. Valida solo el sobre (`items`, `next_seq_after`, orden y progreso de `seq`) y entrega los
  items crudos. Un `asyncio.Lock` único: la pasada completa lo espera; la incremental no (si está tomado, devuelve «omitida» sin leer).
  Una página a la vez.
- `state`: la pasada completa lee desde el día 1 del sexto mes cerrado menos 1 día, arma el estado aparte, lo reemplaza con una sola
  asignación y, con el candado tomado, lee enseguida desde su `last_seq`. `last_seq` solo avanza con una página aplicada entera; una
  página que falla no se aplica, y una pasada fallida deja intacto el estado vigente.

## Qué queda fuera

`mutmut` sobre `compute` y `noise` está **diferido por la demo (T3)** (enmienda §3, U11, fila «5»; §2 regla 3). Cobertura de ramas
del 100 % en `compute` y `noise`: `make -C product-metrics coverage`.
