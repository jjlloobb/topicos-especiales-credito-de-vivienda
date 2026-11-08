# Ronda 1 — U05-T01

VEREDICTO: NO-VERDE

Lo revisé sobre la rama `tarea/U05-T01`, sha `6de022c`, base `7a0e45f`. Corrí yo los cinco criterios y todos pasan. Bloquea un solo ROJO: una prueba de CA-4 no prueba lo que dice su nombre. Su arreglo es trivial. Al terminar, el worktree no tiene cambios ni archivos sin rastrear; solo quedan cachés ignoradas (`.hypothesis/`, `__pycache__`, `.import_linter_cache`).

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `uv sync --frozen && uv run lint-imports --config reference-model/.importlinter` | pasa: 3 KEPT, rc=0. **Rojo primero, reproducido en una copia `git archive`**: con `import sklearn` en `confidence.py` el código de salida es 1 y fallan los contratos «solo envelope.fit» y «envelope.confidence» |
| 2 | `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_generate.py -v --hypothesis-show-statistics` | pasa: 2 pruebas, con 500 ejemplos válidos cada una, en 32,7 s |
| 3 | `uv run pytest reference-model/tests -k "sha256 or determinis" -v` | pasa: 5 pruebas. Además generé los datos en 3 procesos distintos (`PYTHONHASHSEED=1` y `999`, y `make release OUT=<scratch>`) y los tres Parquet dieron SHA-256 idénticos (train `d06645be…`, validation `d9df61af…`, test `cc7a0efa…`). **Mutación**: una columna `time.time_ns()` hace fallar PBT-U5-01 y la prueba de SHA-256 |
| 4 | `uv run pytest reference-model/tests/unit/test_no_real_data.py -v` | pasa: 5 pruebas. Ver F-01 |
| 5 | `make -C reference-model check && make -C platform check` | pasa. reference-model: ruff OK, 3 KEPT, 18 passed en 207 s, rc=0. platform: 745 passed en 792 s, 81 tests y 707, 3 y 322 checks sin fallos, rc=0 |

Lo que comprobé leyendo los Parquet de vuelta del disco:
- **Tamaños**: 84 000, 18 000 y 18 000 filas.
- **Tasa de `default`**: 0,03968, 0,03967 y 0,03972, así que la partición sí está estratificada.
- **Identificadores**: los 120 000 `synthetic_id` llevan `SYN-`.
- **Metadatos**: el clave-valor da `None` y `created_by` no tiene fecha.

## Hallazgos

### F-01 · ROJO · reference-model/tests/unit/test_no_real_data.py:39-44 · La prueba de «rangos sintéticos reservados» es tautológica
`test_other_identifiers_are_in_reserved_synthetic_ranges` compara `document_number` con `gen.CC_RESERVED_PREFIX` y `gen.DOC_SYN_PREFIX`, que son las constantes del propio módulo bajo prueba. En la copia cambié esas constantes a `"10"` (un rango de CC real) y a `"AB"`, y el resultado fue `5 passed in 3.46s`. La prueba no puede fallar con un número de documento con forma real. `document_number` es justo el identificador de `ApplicationIn` que no puede llevar `SYN-`.
- **Arreglo**: fijar los literales esperados en la prueba (`"999"` y `"SYN"`) y comprobar también la longitud o el patrón completo.

### F-02 · NARANJA · generate.py:30-33 y CANDIDATAS.md · El conflicto `SYN-` contra U0 en `document_number` está bien escalado, pero el código afirma un hecho sin verificar
El conflicto es real. U0 exige `^\d{5,10}$` para CC y `^[A-Za-z0-9]{5,15}$` para los demás documentos, así que `SYN-` no cabe. La salida del codificador es razonable: valida contra U0 y registra la candidata.

Lo que falla:
1. El comentario dice «bloque reservado de 10 dígitos que no se asigna a personas (prefijo 999)». Es una afirmación normativa sin fuente y sin `[VERIFICAR]`. Hay que reformularla como convención sintética del proyecto o marcarla `[VERIFICAR]`.
2. La candidata no menciona el impacto en U12: `LOGS-NO-PII` busca `SYN-…` en Loki (system-verification BR-U12-12 y su plan, línea 149). `synthetic_id` no viaja en `ApplicationIn`, así que ese oráculo no vería una fuga de `document_number`, `email` o `full_name`. Agravante: el email usa `syn-` en minúsculas cuando U0 admite `SYN-` en mayúsculas.

La decisión de diseño es del orquestador: precisar NFR-U5-34 y BR-U5-01, y decirle a U12 qué buscar.

### F-03 · NARANJA · generate.py · Parámetros del generador escritos como literales en el código, no en `generator.yaml`
BR-U5-01 dice que el generador solo usa `generator.yaml`, y domain-entities §1 pone la antigüedad en `marginals`. Encontré estos literales en puntos de decisión:
- **Antigüedad laboral**: `rng.exponential(72.0)` en l.160. Es la marginal de antigüedad y no está en la configuración.
- **Tope laboral**: `720` en l.159.
- **Margen VIS**: `cap * 0.98` y `cap * 1.02` en l.176. Además, toda vivienda no VIS sale con un valor de al menos 204 M COP aunque el ingreso sea bajo; ver la fila `SYN-0000001`.
- **Estrato `no_informado`**: se trata como estrato 3 con `2` en l.148.
- **Fecha de nacimiento**: `365` en l.144 y l.280.
- **Dirección**: rangos `150` y `99` en l.294.
- **Brokers**: `40` en l.309.

Hay que moverlos a `marginals`.

### F-04 · AMARILLO · .importlinter, contrato `confidence-solo-numpy` · El contrato es una lista de prohibidos, no de permitidos
Con `import hypothesis` en `confidence.py` el contrato sigue KEPT; lo probé en la copia. Lo compensa la prueba AST `test_confidence_imports_only_numpy_and_the_standard_library`, que sí funciona como lista de permitidos y corre en `check`. Conviene renombrar el contrato o añadir una nota.

### F-05 · AMARILLO · generate.py:333 · `derived_features` es código muerto y su docstring es falsa
Dice «los usa la etiqueta y las pruebas», pero nadie lo llama. La etiqueta recalcula ITI y LTV en float con `_annuity` y no usa U0 `finance`. Las diferencias son mínimas, pero conviene que la etiqueta use U0 o borrar la función.

### F-06 · AMARILLO · Cobertura secundaria
- `GeneratorError` no tiene ninguna prueba directa. PBT-U5-02 lo cubre de forma indirecta: revalida cada fila por JSON y comprueba `len == n_rows`.
- NFR-U5-34 pide recorrer «todos los Parquet», pero la prueba usa `n_rows=3000` y no la entrega de referencia.
- `names.yaml` dice «sílabas inventadas: no son nombres reales», pero incluye Alvarez, Lisbet y Ulmer, que sí existen. No es PII, pero el comentario es inexacto.

### Comprobado sin hallazgo
- **Validación**: el generador valida con `vectra_contracts.models.application.ApplicationIn` del workspace. Lo confirmé con `__file__`, y no hay ningún modelo pydantic propio en `reference-model/`.
- **PBT-U5-01 y 02**: se ajustan a su definición en business-logic-model §3. La 01 usa semillas aleatorias y tamaños de 2 a 60. La 02 usa configuraciones en sus bordes.
- **`[VERIFICAR]`**: `vis_cap_cop` y `target_default_rate` conservan la marca, citan domain-entities §1 y se declaran sintéticos.
- **Alcance**: no se tocó `decision-registry/` (no existe en la rama), y los Pasos 3 a 8 solo tienen stubs con docstring.
- **Workspace**:
  - el `pyproject.toml` raíz agrega solo el miembro, la fuente y `vectra-reference` en `dev`;
  - `uv.lock` es puramente aditivo: 17 paquetes nuevos y ninguna línea quitada;
  - el plan marca los Pasos 1 y 2 con `[x] (U05-T01)`.

## Tareas candidatas (defectos reales fuera de alcance)
- Precisar NFR-U5-34 y BR-U5-01 frente al patrón de documento de U0, y definir qué marcador busca el oráculo `LOGS-NO-PII` de U12 en los campos que sí viajan (amplía F-02).
- `vectra-reference` en el grupo `dev` raíz obliga a toda unidad a descargar xgboost y nccl, unos 290 MB. El codificador ya lo registró en CANDIDATAS.

```
VEREDICTO: NO-VERDE
ROJO|reference-model/tests/unit/test_no_real_data.py:39-44|La prueba de rangos sintéticos reservados es tautológica (compara contra las constantes del módulo)
NARANJA|reference-model/src/vectra_reference/generate.py:30-33|Conflicto SYN- vs U0 en document_number: afirmación «bloque reservado 999» sin fuente ni [VERIFICAR]; impacto en LOGS-NO-PII de U12 no registrado
NARANJA|reference-model/src/vectra_reference/generate.py:144-309|Parámetros del generador escritos como literales en el código (antigüedad 72.0, margen VIS 0.98/1.02, 720, 365, 150/99, 40) en vez de generator.yaml
AMARILLO|reference-model/.importlinter|El contrato de confidence es una lista de prohibidos; el allowlist real lo da la prueba AST
AMARILLO|reference-model/src/vectra_reference/generate.py:333|derived_features es código muerto con docstring falsa; la etiqueta no usa U0 finance
AMARILLO|reference-model/tests|Sin prueba directa de GeneratorError; NFR-U5-34 se prueba con 3000 filas; comentario inexacto en names.yaml
INFORME: revisiones/U05-T01/ronda-1.md
```
