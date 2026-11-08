# Ronda 2 — U05-T01

VEREDICTO: VERDE

Revisé el sha `1c401c2` de la rama `tarea/U05-T01`, en el mismo worktree. Corrí yo los CA-1 a CA-5 y todos pasan. Los tres hallazgos que entraron en el arbitraje están corregidos, y sus pruebas fallan cuando reintroduzco el defecto en una copia `git archive`. No queda ningún ROJO ni NARANJA en pie. Al terminar, el worktree no tiene cambios (`git status` vacío); solo quedan las cachés ignoradas de siempre.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `uv sync --frozen && uv run lint-imports --config reference-model/.importlinter` | pasa: 3 contratos KEPT, 0 rotos |
| 2 | `HYPOTHESIS_PROFILE=ci uv run pytest reference-model/tests/property/test_generate.py -v --hypothesis-show-statistics` | pasa: 2 pruebas, con 500 ejemplos válidos cada una, en 80 s |
| 3 | `uv run pytest reference-model/tests -k "sha256 or determinis" -v` | pasa: 5 pruebas. Además generé los datos en dos procesos con `PYTHONHASHSEED=3` y `77`, y los SHA-256 nuevos coinciden (train `82230cc1…`, validation `3460ad99…`, test `698fde96…`) |
| 4 | `uv run pytest reference-model/tests/unit/test_no_real_data.py -v` | pasa: 5 pruebas |
| 5 | `make -C reference-model check && make -C platform check` | pasa. reference-model: ruff OK, 3 KEPT, 27 passed en 184 s, rc=0. platform: 745 passed en 718 s, 81 tests y 707, 3 y 322 checks sin fallos, rc=0 |

Al leer los Parquet nuevos de vuelta del disco:
- **Tamaños**: 84 000, 18 000 y 18 000 filas.
- **Tasa de `default`**: 0,03968, 0,03967 y 0,03972, igual que en la ronda 1.
- **Contenido**: frente a la ronda 1 solo cambia el email, que ahora es `SYN-0000001@example.com`. Los SHA cambian por ese motivo y por nada más, como pedía el arbitraje.

## Hallazgos de la ronda 1, verificados

### F-01 (ROJO) · corregido
La prueba ahora fija los literales y el patrón completo, y no lee las constantes del módulo:
- CC: `^999\d{7}$`
- resto de documentos: `^SYN\d{9}$`
- email: `SYN-\d{7}@example\.com`
- teléfono: `0000\d{6}`

En la copia puse las constantes en `"10"` y `"AB"`, y `test_other_identifiers_are_in_reserved_synthetic_ranges` falló (`1 failed, 4 passed`).

### F-02 (NARANJA, en parte) · corregido
- **Comentario**: `generate.py:30-32` presenta el `999` como «convención sintética del proyecto» con `[VERIFICAR …Registraduría]` y ya no afirma que ese bloque no se asigne a personas.
- **Email con `SYN-`**: U0 lo admite, y lo validaron PBT-U5-02 (500 ejemplos) y la ruta JSON. Si lo vuelvo a pasar a minúsculas (`sid.lower()`), CA-4 falla.
- **Candidata**: amplía el impacto en `LOGS-NO-PII` de U12 para `document_number`, `email` y `full_name`.

### F-03 (NARANJA) · corregido
- `generate.py` ya no tiene literales de decisión. Pasaron a `generator.yaml`: antigüedad (media, tope y edad adulta), `vis_margin`, `undeclared_stratum`, `address`, `brokers`.
- `test_config_drives_output.py` prueba de verdad. Reintroduje cada literal en la copia y la prueba falló cada vez:
  - `% 150` en la dirección: falla `[path5-3-address]`;
  - `cap*0.98` y `cap*1.02`: falla `[path3-0.3-property_value]`;
  - `2` como estrato de `no_informado`: falla `[path4-6-monthly_income]`;
  - `% 40` en los brokers: falla `[path7-2-broker_id]`;
  - `720` y `18` en la antigüedad: fallan 2 casos.

**Las constantes que dejó el codificador son razonables**:
- **Los 365 días de `age_days` y de `birth_date`** son una aproximación de calendario y no un parámetro de distribución.
- **El 365 de `max_days_past_due_12m`** es el tope del contrato de U0 (`le=365`). Lo correcto es que coincida con U0, no que sea configurable.

Una mejora menor sería importar ese tope de U0 en vez de repetirlo, pero no bloquea. También quedan el paso de redondeo a 1000 COP y las conversiones de unidades `/30` y `/12`. Son convenciones de formato, no marginales del diseño.

## Hallazgos nuevos

### F-07 · AMARILLO · CANDIDATAS.md (entrada de NFR-U5-34) · Restos de la redacción anterior
La entrada todavía dice «(CC, bloque reservado)», cuando la frase añadida aclara que es una convención sintética. También falta un punto antes de «Impacto en U12». Es solo redacción.

### F-08 · AMARILLO · generate.py:172 · El tope de U0 está repetido como literal
El `365` de `max_days_past_due_12m` repite el tope de U0. Conviene derivarlo del contrato para que no se desvíe si U0 cambia.

## Tareas candidatas (defectos reales fuera de alcance)
Ninguna nueva. F-04, F-05, F-06 y el valor de la vivienda no VIS ya están en `CANDIDATAS.md`.

```
VEREDICTO: VERDE
AMARILLO|vectra-risk/CANDIDATAS.md (entrada NFR-U5-34)|Restos de «bloque reservado» y falta un punto antes de «Impacto en U12»
AMARILLO|reference-model/src/vectra_reference/generate.py:172|El tope 365 de max_days_past_due_12m repite el de U0 en vez de derivarlo del contrato
INFORME: revisiones/U05-T01/ronda-2.md
```
