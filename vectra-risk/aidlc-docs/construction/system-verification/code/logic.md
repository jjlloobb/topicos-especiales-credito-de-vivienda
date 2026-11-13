# Resumen de la lógica pura — U12 `system-verification` (Pasos 1 a 4, U12-T01)

Código en `vectra-risk/system-verification/src/vectra_verification/`. Lo que hay en esta tarea: `guard`, `credentials`, `evidence` (Paso 2) y
`sampler`, `rt2_latency`, `story_map`, `report` (Paso 3). `manifest`, `simulator`, `driver` y `cli` son módulos vacíos con docstring (Pasos 6 y 13), y
`clients/`, `scenarios/` y `load/` son paquetes vacíos. U12 depende de `vectra_contracts` y no de `vectra_common` (contrato de import-linter).

## Decisiones de las preguntas abiertas

Nadie respondió; rige la recomendación de la tarea en cada una.

| Pregunta | Decisión | Dónde |
|---|---|---|
| P-1 evidencias repetidas | (a) gana lo peor: `falla` si alguna evidencia íntegra falla; si ninguna falla y alguna no es íntegra, `no ejecutado`; `pasa` solo si todas son íntegras y pasan | `report._worst` |
| P-2 barrera horaria | (a) `volumen / ritmo + volumen × DECISION_SECONDS_PER_CASE + MARGIN_SECONDS`, con 1 s por caso y 300 s de margen (valores iniciales, se miden en el Paso 18); se niega si `ahora + estimado` pasa de las 23:00 UTC del mismo día | `guard.check_decisions` |
| P-3 `story_map` sin E/S | (a) `parse(texto)` es pura y `load(ruta)` es una línea con `pathlib`; `yaml` solo se permite en `story_map` | `story_map`, `.importlinter` |
| P-4 verbos de `kubectl` | (a) lista cerrada: `get`, `auth can-i`, `logs`, `port-forward`; de `argocd` falla toda invocación | `tests/unit/test_kubectl_verbs.py` |
| P-5 cliente de la bóveda | (a) `httpx` contra la API KV v2, sin `hvac` | `credentials` |
| P-6 secciones | (a) las 14 de NFR-U12-30 | `guard.SECTIONS` |
| P-7 tipos de dominio | (a) en el módulo que los produce: `Evidence`, `VerificationReport` y `StoryRow` en `report`; `Rt2Measurement` en `rt2_latency`; el informe de celdas en `sampler` | cada módulo |
| P-8 | No es de esta tarea: el `sampler` informa `disponibles` y `tomadas` por celda, sin rellenar y sin negarse | `sampler.CellReport` |

## `sampler` (BR-U12-01, BR-U12-06; NFR-U12-10, 11)

```python
normal(population: Sequence[Row], volume: int, seed: int) -> tuple[str, ...]
stratified(population: Sequence[Row], volume: int, seed: int, min_per_cell: int = 30) -> StratifiedSample  # ids, cells, short
cell_report(population, ids, min_per_cell) -> tuple[tuple[CellReport, ...], tuple[CellReport, ...]]
```

`Row` lleva el identificador, un grupo por cada uno de los cuatro atributos de U9 y la banda. `stratified` es el procedimiento de `stratified_sample` de
U5: orden al azar con `random.Random(seed)`; se toma una fila si alguna de sus celdas no llega a `min(min_per_cell, disponibles)`; después se completa
al azar hasta `volume`. El volumen es un piso: si cubrir las celdas ya lo supera, la muestra es más grande, como en U5. Una celda que no alcanza
`min_per_cell` toma todas las filas que hay y no se rellena con repetidas; `short` la nombra. Un volumen mayor que la población, un identificador repetido
o `min_per_cell < 1` son errores. Negarse a correr cuando una celda alcanzable queda corta es de la sección `rt2` (Paso 8; P-8).

## `rt2_latency` (BR-U12-07; INF-U12-03)

```python
measure(run: int, recommendation_recorded_at: Sequence[datetime], freeze_recorded_at: datetime) -> Rt2Measurement
```

`latency_seconds = freeze − min(recorded_at del lote)`; `passed` es `latency ≤ 1 800 s` (1 800 exactos pasan). Un lote vacío, una hora fuera de UTC, un
`run` fuera de 1..5 o un `freeze` anterior al inicio son errores; una corrida que supera el límite se registra con `passed = False`.

## `story_map` (BR-U12-13; domain-entities §4.2)

`report/story-map.yaml` tiene las 15 filas de §4.2; las cuatro de demos (US-304, 503, 504, 505) llevan `demonstrated: true`. `parse` falla ante una historia
de §4 sin fila, una historia que no es de §4, una fila sin evidencias, una evidencia que no es uno de los 26 identificadores (`US-609` no lo es: su evidencia es
`LOAD`) y una marca de demo que no coincide.

## `report` (BR-U12-11, BR-U12-13; NFR-U12-20, 21)

```python
build(evidences, declared_hashes, observed_hashes, story_map) -> VerificationReport   # 26 elementos + las historias del mapa = 41 filas
render(report) -> str
```

- Una evidencia es íntegra si su hash está declarado en el manifiesto y observado en disco, y coinciden. Si no, vale `no ejecutado` (NFR-U12-20).
- Una evidencia íntegra vale `falla` si `expected ≠ obtained` o `result = falla`, aunque el otro campo diga `pasa`; si no, `pasa`. Un hash roto tapa la
  contradicción: el contenido de una evidencia alterada no se usa.
- Un elemento: sin evidencias, `no ejecutado`; con varias, gana lo peor (P-1).
- Una historia: `pasa` si pasan todas las evidencias de su fila, `falla` si alguna falla, `no ejecutado` en otro caso (también con una fila vacía).
- Las historias de demos salen con el tipo `demostrada`: el informe no las presenta como verificadas. Su resultado sigue las mismas reglas.
- Cada fila lleva commit, imágenes y fecha de la evidencia más reciente. `render` abre con el límite del manifiesto (NFR-U12-21).

## `guard`, `credentials`, `evidence` (Paso 2)

- `guard`: lista exacta de `issuer` y host de kind y staging (comparación exacta; una prueba la compara con `identity-edge/gateway`); las 14 secciones; en
  staging solo `prepare` (sin el parche de los Jobs de prueba), `decisions` (≤ 100 casos), `u11` y `report`; la reactivación solo dentro de `rt2`; la barrera horaria.
- `credentials`: lee la bóveda por KV v2 (montaje `secret` en kind y `vectra` en staging) con `VAULT_ADDR` y `VAULT_TOKEN`; `cumplimiento-*` fuera de kind da error
  antes de cualquier solicitud y sus propiedades se descartan al leer el secreto compartido; todo en memoria; `repr()` no muestra secretos.
- `evidence`: `scrub` quita cabeceras y campos de credenciales; `ensure_clean` falla ante un JWT o un secreto cargado; `prepare` hace las dos.

## BR-U12 → prueba

| Regla | Prueba |
|---|---|
| BR-U12-01 (`normal` y `stratified`) | `tests/property/test_sampler.py` (PBT-U12-01) |
| BR-U12-06 (volúmenes, celdas de U9) | `test_sampler.py::test_a_population_with_a_small_cell_is_reported_by_the_sampler` y las propiedades de celdas |
| BR-U12-07 (latencia de RT-2) | `tests/property/test_rt2_latency.py` (PBT-U12-04) |
| BR-U12-09 (sin `kubectl apply` ni `argocd app sync`) | `tests/unit/test_kubectl_verbs.py` |
| BR-U12-10 (dónde corre) | `tests/unit/test_guard.py` |
| BR-U12-11 (informe) | `tests/property/test_report.py` (PBT-U12-02) |
| BR-U12-13 (historias) | `test_report.py` y `tests/unit/test_story_map.py` |
| BR-U12-03 (credenciales de los usuarios sintéticos) | `tests/unit/test_credentials.py` |

## Cobertura y `mutmut`

Cobertura de ramas del 100 % en `report` y `sampler` (`make -C system-verification check`; NFR-U12-40). **`mutmut` en `report` está diferido por la
demo (T3):** enmienda del recorte funcional, §3 U12, fila «4»; no se configuró. El ≥ 85 % del resto del paquete se comprueba en el Paso 16 (U12-T04).


## Cambios de U12-T02 sobre `guard`, `credentials` y `evidence` (candidatas F-04, F-07, F-08 y F-09 de la revisión de U12-T01)

- **F-04.** `guard.check_known` exige que el entorno sea **uno de** `guard.ENVIRONMENTS` (la misma instancia, no igual por valor); lo llaman `check_section` (y con él `check_job_patch`, `check_reactivation` y `check_decisions`) y `check_token_issuer`.
  `Credentials` lo exige al crearse y, cuando se conecta de verdad (sin transporte inyectado), exige una dirección de bóveda de `ALLOWED_VAULT_HOSTS` (`vault.vault.svc`, `127.0.0.1`, `localhost`; esquema `http` o `https`). Con un transporte
  inyectado (pruebas) no sale ninguna solicitud y la dirección no se mira. Las pruebas con host dinámico registran su entorno en `guard.ENVIRONMENTS` solo durante la prueba (`dynamic_environment`).
- **F-07.** `_fragments` quita la armadura PEM (`-----BEGIN … -----`, `-----END … -----`) antes de partir el secreto: un certificado ya no da `evidence_contains_secret`; el cuerpo de la llave sigue protegido.
- **F-08.** `scrub` quita el valor de las cabeceras en forma de tupla (`('Cookie', 'x')`, `(b'cookie', b'x')`) y de HAR (`{"name": "Cookie", "value": "x"}`), el `code=` de una URL o formulario (`[?&#]code=`) y los campos `code_verifier` y `otp`. `code` **no** es un campo general: es el
  nombre del código de error de `Problem` y `{"code": "conflict_state"}` sale igual.
- **F-09.** `Credentials.secret_values()` no incluye el token de la bóveda cuando es `root` en kind: es el token de desarrollo escrito en `platform/operators/vault-kind.yaml`, no un secreto, y como valor a buscar rechazaba toda evidencia con `/dev/root` o el logger `root`. Se excluye solo ese valor exacto y solo en kind
  (un largo mínimo habría dejado sin proteger cualquier secreto corto): un token real (`hvs.…`) y `root` en staging siguen protegidos.
