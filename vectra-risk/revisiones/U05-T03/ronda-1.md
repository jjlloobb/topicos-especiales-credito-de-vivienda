# Ronda 1 — U05-T03

VEREDICTO: NO-VERDE

Los cuatro criterios pasan en mis corridas. Aun así queda un ROJO: el doble de U9 cuenta como favorables los casos `revision_requerida`, y BR-U9-01 los cuenta como no favorables. Con la regla de outcome completa, la disparidad del modelo base es de **8,70 pp**, así que no cumple BR-U5-06 (< 5 pp). El 4,83 pp del manifiesto sale de ese error de medición.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Variante proxy | `uv run pytest reference-model/tests/examples/test_proxy.py -v` | pasa: 21 pruebas en 315 s, RC=0 |
| 2 | Conjunto adversarial | `HYPOTHESIS_PROFILE=ci uv run pytest .../property/test_adversarial.py -v && uv run pytest .../examples/test_adversarial_manifest.py -v` | pasa: 7 en 170 s y 13 en 368 s, RC=0 |
| 3 | F-08 | `HYPOTHESIS_PROFILE=ci uv run pytest .../property/test_envelope.py -v -k counterexample` | pasa: 1 en 225 s, RC=0 |
| 4 | `check` de U5 y de U1 | `make -C reference-model check && make -C platform check` | pasa: U5 con 132 pruebas; U1 con 745 pruebas, Kyverno 81/81, 707+3+322 pruebas y conftest 45 y 309 sin fallos. RC=0 en 39 min |

Ninguna prueba omitida. Los tiempos se explican porque el fixture `reference_release` entrena el modelo completo. El worktree quedó limpio después y el HEAD sigue en `b69fed0`.

## Hallazgos

### F-01 · ROJO · `reference-model/src/vectra_reference/proxy.py:260-277` (`disparity_pp`) · el doble de U9 no implementa BR-U9-01 y la base no cumple BR-U5-06
- **Qué dice el diseño.** BR-U9-01: «`revision_requerida` cuenta como **no** favorable». BR-U7-04/05 fija el outcome: es `revision_requerida` si `confidence < low_confidence_threshold`, si la tasa supera la usura o si `normative` es nulo; solo si no pasa nada de eso se aplica `score < cutoff` → `favorable`.
- **Qué hace el doble.** Toma como favorable `p < cutoff` y nada más. Así, un caso de baja confianza con p < 0,08 entra como favorable. La docstring dice «`revision_requerida` nunca se cuenta, BR-U9-01», y eso es lo contrario de lo que dice la regla.
- **Medición.** La hice en una copia (`git archive bb11786`) con el mismo código de entrega. Primero `run_release` y `run_proxy_release`; después, sobre `validation` (18 000 filas), el outcome completo: umbral calibrado y usura 0,28 de `reference_policy`. 547 casos salen `revision_requerida`.
  - Base, con el doble: `estrato` **4,8349 pp**, la misma cifra del manifiesto.
  - Base, con BR-U9-01: `estrato` **8,6988 pp**. Por atributo: sexo 0,25; edad 2,85; región 3,04; estrato 8,70.
  - Variante, con el doble: `region` 12,4559. Con BR-U9-01: `region` **12,0854**, que sigue ≥ 10.
- **Por qué es ROJO.**
  - La aceptación del Paso 6 (disparidad base < 5 pp) solo se cumple por el error de medición.
  - La puerta de `run_release` deja pasar una base que la librería real de U9 mediría en 8,7 pp.
  - Puede romper la demo 7.4. BR-U12 corre 2 000 casos `normal` con el modelo de referencia «activo (sin congelar)» antes de RT-2. Si la base supera 5 pp con la cota inferior del intervalo > 0, bias congela el modelo de referencia (BR-U9-11).
  - Las pruebas del doble no tienen ningún caso con `revision_requerida`, así que no lo detectan.
- **Arreglo.**
  - `disparity_pp` debe recibir el outcome de BR-U7-04/05 (confianza con la envolvente del paquete y el umbral calibrado, más la usura) y contar `revision_requerida` como no favorable.
  - Hay que agregar una prueba con una celda de casos `p < cutoff` y baja confianza.
  - Con eso la base da 8,70 pp: o se baja la dependencia por estrato (correlación ingreso ↔ estrato, o casos de baja confianza concentrados en estratos extremos), o se lleva al usuario. Esto ya no es la «candidata de margen»: es un incumplimiento.

### F-02 · AMARILLO · `reference-model/config/catalog/proxy.yaml:5` · el comentario de `zona_4` no coincide con U0
Dice «`zona_4` mezcla pacifico y andina», pero el departamento 18 (Caquetá) es `amazonia` en `DEPARTMENT_REGION`. La zona es pacífica más amazonia.

### F-03 · AMARILLO · `tests/examples/test_proxy.py:302` · el nombre promete más de lo que prueba
`test_a_proxy_package_with_a_safe_zone_feature_or_a_small_zone_fails_verification` solo altera `applicant_safe`. La zona chica la cubre otra prueba, la de la línea 144.

### F-04 · AMARILLO · `tests/property/test_adversarial.py:29-35` · el generador `PRINTABLE` es más estrecho que U0
Excluye `\n`, `\r` y `\t`, que `check_free_text` de U0 sí admite. Los casos RT-1 de Markdown y JSON usan esos caracteres; la propiedad no los genera.

## Lo demás que pediste revisar
- **Zonas y municipio (BR-U5-15, BR-U0-34).** Las 6 zonas tienen entre 101 y 240 municipios. `zona_5` tiene 197: caribe más 88, San Andrés, con 2. Los 33 departamentos están cubiertos. `derive` no saca `municipality_code`, `department_code` ni `broker_id`.
  - Mutaciones (en la copia), todas detectadas: doble sin pesos → falla `..._follows_br_u9_01_to_05`; `no_informado` como extremo → falla `..._ignores_small_cells...`; `n_min = 29` → falla la misma prueba; par RT-1 con otro campo → fallan 3 pruebas de PBT-U5-07.
- **Los 5 paquetes.** Los vuelvo a obtener yo: `ed556f17`, `3a883566`, `c29ff44f`, `d7253076` y `ea595578`. Comparten el mismo `predictor.json`, llevan `rt2-demo` y la copia del validador de U4 los acepta. La base es `f071216b`.
- **RT-3 (a)–(d).** Coinciden con la tabla de domain-entities §5. `RT3-b` pasa U4 y su resultado esperado cita `sync_check`/`validacion_fallida` y `FailClosed`, como dice el diseño. a, c y d se rechazan con el motivo exacto.
- **RT-1 bidi.** Con BR-U0-29 (solo imprimibles), un caso con U+202E no puede ser una `ApplicationIn` válida. Usar hebreo y árabe es la única lectura compatible, y la candidata está bien planteada. No es un hallazgo.
- **F-08.** El contraejemplo tiene la misma forma que el de la revisión (ITI 1,0; antigüedad 1; ltv desde 0,9). La prueba exige que `confidence` suba, que `c_rango` no suba y que `confidence ≤ c_rango`. Basta.
- **AUC 0,8252.** BR-U5-08 está en «§3 Modelo», junto a BR-U5-07 («`feature_spec` del modelo base»), y el flujo del BLM pone esa puerta en el `train` base. La variante tiene su propia puerta (BR-U5-14). Confirmado: no se exige a la variante.
- **Etiqueta por incrementos.** BR-U5-06 solo restringe el dataset base, y la etiqueta base no cambia (la prueba exige `new >= base`). Domain-entities §4 pide «depende en parte», y los incrementos lo cumplen. No es un desvío.
- **Alcance.** No toca `identity-edge/` ni `decision-registry/`, no hay workflow de CI ni release firmada, y la copia del validador de U4 no cambió.

## Tareas candidatas
- Cuando exista `vectra_disparity`, comprobar que el reemplazo del doble usa outcomes y no `p < cutoff`. El aviso debería entrar en la candidata que ya está en `CANDIDATAS.md`.

```
VEREDICTO: NO-VERDE
ROJO|reference-model/src/vectra_reference/proxy.py:260 (BR-U5-06, Paso 6)|el doble de U9 cuenta revision_requerida como favorable (contra BR-U9-01); con el outcome de BR-U7-04/05 la base mide 8,70 pp ≥ 5
INFORME: revisiones/U05-T03/ronda-1.md
```
