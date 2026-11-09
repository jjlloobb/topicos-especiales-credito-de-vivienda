# Ronda 2 — U05-T03

VEREDICTO: VERDE

## Criterios de aceptación, verificados por mí (sha `ac6b8f8`)
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Variante proxy | `uv run pytest reference-model/tests/examples/test_proxy.py -v` | pasa: 23 pruebas en 198 s, RC=0. Incluye la prueba nueva del doble |
| 2 | Conjunto adversarial | `HYPOTHESIS_PROFILE=ci uv run pytest .../property/test_adversarial.py -v && uv run pytest .../examples/test_adversarial_manifest.py -v` | pasa: 7 en 18 s y 13 en 104 s, RC=0 |
| 3 | F-08 | `HYPOTHESIS_PROFILE=ci uv run pytest .../property/test_envelope.py -v -k counterexample` | pasa: 1 en 79 s, RC=0 |
| 4 | `check` de U5 y de U1 | `make -C reference-model check && make -C platform check` | pasa: U5 con ruff limpio y 134 pruebas; U1 con 745 pruebas, Kyverno 81/81, 707+3+322 pruebas y conftest 45 y 309 sin fallos. RC=0 en 13 min |

Ninguna prueba omitida. El worktree quedó limpio y el HEAD sigue en `ac6b8f8`. El alcance se respeta: no hay cambios en `identity-edge/`, `decision-registry/` ni `.github`.

## Las comprobaciones pedidas
1. **El doble (F-01).** `outcome_of` sigue BR-U7-04/05:
   - `revision_requerida` si no hay `normative` vigente, si la tasa supera la usura (estricto: igual no cuenta) o si `confidence` está por debajo del umbral (estricto);
   - si no, `favorable` cuando `p < cutoff` y `desfavorable` en otro caso.

   `disparity_pp` cuenta solo `favorable` (BR-U9-01), y la agregación de BR-U9-02..05 no cambió desde la ronda 1. La política no tiene reglas por canal, así que no hace falta `cutoff_efectivo`.

   Reproduje el rojo en una copia (`U05-T03-revisor-r2/copy`):
   - **M1**, el doble de la ronda 1 (todo lo que no es `desfavorable` cuenta como favorable): falla `test_a_cell_of_cases..._is_not_favorable` con `('region', 0.0) == ('region', 100.0)`;
   - **M2**, sin la regla de baja confianza: fallan las 2 pruebas nuevas;
   - **M3**, usura con `>=`: falla `test_outcome_follows_br_u7_04_and_05`.

   Sin mutaciones, las 2 pruebas pasan.
2. **Las cifras.** Las medí con un outcome calculado en mi script, sin usar `outcome_of`. Usé la confianza de la envolvente, el umbral calibrado de 0,0300 y la usura de 0,28.
   - Base: **4,6119 pp** (`region`), con 478 casos `revision_requerida`. Por atributo: sexo 0,45; edad 2,41; región 4,61; estrato 2,65.
   - Variante: **11,6579 pp** (`region`).

   Las dos coinciden con los manifiestos.
3. **`stratum_slope` de 0,30 a 0,15.**
   - Base: AUC 0,9087 (≥ 0,85).
   - Calibración: umbral 0,0300 y 96,93 % de `test` por encima. `run_release` exige que los 18 RT-4 queden bajo el umbral, y no falló.
   - Determinismo: mi entrega da los mismos ids que la bitácora (base `51241dc4`; proxy `7241d354`, `fa147805`, `d2baab53`, `2a799484` y `ea69c19d`).
   - PBT-U5-01..07 y las pruebas de U05-T01 y U05-T02 entran en los 134 de `make -C reference-model check`, todos verdes.
4. **La variante.** Mide con su propia envolvente y con la política de referencia de la base. Es coherente con domain-entities §4 y BR-U5-14 («medida sobre `validation`», ≥ 10 pp). Que no calibre un umbral propio ya está anotado como candidata.
5. **F-08.** Conserva la forma: ITI 1,0, antigüedad 1 y ltv desde p99 = 0,9, con las demás features dentro de [p1, p99]. La prueba exige que `confidence` suba y que `c_rango` no suba, y pasa con la envolvente nueva.
6. **CA-1 a CA-4.** Completos, en la tabla de arriba.

## Hallazgos
No queda ningún ROJO ni NARANJA en pie. F-02, F-03 y F-04 están corregidos y los verifiqué en el diff.

### F-05 · AMARILLO · `reference-model/config/generator.yaml` (`stratum_slope`) · margen corto de la base
La base queda a 0,39 pp del límite de 5 (4,61 pp, atributo `region`). Es determinista con la semilla de referencia, pero cualquier cambio del generador o del modelo puede pasarla del límite. Ya está registrado en `CANDIDATAS.md`. No bloquea.

## Tareas candidatas
- Las que ya están en `CANDIDATAS.md`: el margen de la base y el aviso de usar outcomes cuando se reemplace el doble por `vectra_disparity`. No agrego otras.

```
VEREDICTO: VERDE
AMARILLO|reference-model/config/generator.yaml (stratum_slope)|disparidad base a 0,39 pp del límite de BR-U5-06 (ya registrado como candidata)
INFORME: revisiones/U05-T03/ronda-2.md
```
