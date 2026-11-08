# Ronda 1 — U05-T02

VEREDICTO: NO-VERDE

Revisé la rama `tarea/U05-T02` en el sha `4b31a017`, con la tarea en el blob `96521e3d` (coincide). Hay un solo ROJO, y no es ninguno de los puntos que me pediste mirar: es una propiedad PBT-U5-03 que Hypothesis refutó cuando corrí el CA-5. Los puntos que me pediste mirar quedan en AMARILLO, y varios requieren una decisión tuya.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `uv run pytest reference-model/tests/examples/test_train.py -v` | pasa: 15 pruebas en 161 s, AUC 0,8961 |
| 2 | `HYPOTHESIS_PROFILE=ci ... test_envelope.py --cov=...confidence --cov-fail-under=100` (con ramas) | pasó en esa corrida: 18 pruebas, 36 sentencias y 12 ramas al 100 %. Pero la misma suite falló en el CA-5 (F-01) |
| 3 | `uv run pytest reference-model/tests -k numpy_only -v` | pasa: 2 pruebas |
| 4 | `HYPOTHESIS_PROFILE=ci ... test_package.py test_explainer_parity.py -v` | pasa: 21 pruebas en 558 s |
| 5 | `make -C reference-model check && make -C platform check` | **falla**: 1 fallida y 85 pasadas, RC=2. `make -C platform check` no llegó a correr porque el `&&` cortó la cadena; queda sin verificar en esta ronda |

Comprobaciones aparte, con `run_release` corrido por mí:
- `predictor.json` da `e684c314…` y `manifest.json` da `6b8feff2…`, con id `mv-2026-01-01-26300247`. Son los mismos valores de la bitácora, así que el determinismo se reproduce.
- Calibración: umbral 0,0300, el 96,58 % de `test` queda por encima, y los 18 casos RT-4 dan entre 0,0000 y 0,0013.
- `reference-policy.json` pasa `PolicyDraft.model_validate_json`.
- La copia del validador de U4 acepta el **paquete de referencia**.

## Hallazgos

### F-01 · ROJO · `tests/property/test_envelope.py:113` · PBT-U5-03 (monotonía) refutada; el CA-5 da RC=2
En mi corrida del CA-5, `test_pbt_u5_03_confidence_does_not_increase_as_a_feature_moves_away_from_the_range` falló con `0.013541307639193145 <= 0.013541307616182552`. La prueba tiene un `@reproduce_failure` en el log.

Lo reproduje fuera de pytest (`scripts/mono.py`). Muevo `loan_to_value` hacia arriba desde p99 = 0,9, con las demás features fijas (ITI = 1,0, antigüedad = 1). La distancia d_M **baja** de 13,507165166770726 a 13,50716516218407 entre 0,9 y 0,9625, y por eso `confidence_raw` sube.

No es ruido numérico. La distancia de Mahalanobis es cuadrática en cada coordenada y tiene su mínimo en la media condicional, que puede quedar fuera de [p1, p99]. Así que la fórmula de BR-U5-12 no garantiza la monotonía que afirma PBT-U5-03. La suite verde del codificador y mi CA-2 verde se deben a la semilla aleatoria del perfil `ci`.

Ojo: el contraejemplo quedó guardado en `vectra-risk/.hypothesis/` del worktree, así que la próxima corrida lo repetirá. El arreglo pide una de dos cosas: reformular la propiedad (por ejemplo, sobre `c_rango`, o «no crece a partir de un desplazamiento en que d_M ya crece»), o cambiar la fórmula. Las dos tocan el diseño, así que llévalas al usuario si hace falta.

### F-02 · AMARILLO (decisión del usuario) · `config/generator.yaml` `explainer_margin_tolerance: 1.0e-4` · tolerancia de la suma
- **A qué se aplica el 1e-6.** En el plan de U5 y en NFR-U5-30, el «1e-6, 1 000 filas» va con la paridad con `shap`; la suma no tiene tolerancia propia. Pero esa cláusula dice «precisado por U6 NFR Q1», y **NFR-U6-01** fija 1e-6 justamente para la suma. El plan de U6 (Paso del explicador) repite el 1e-6.
- **Es un límite técnico, no un descuido.** Medí 8,54e-6 con el sesgo de XGBoost (`pred_contribs[:, -1]`), con el `expected_value` de shap (diferencia 0,0) y sumando en float32 o float64: el resultado es el mismo. Las salidas son float32 y el margen máximo es 8,48. Por eso no lo marco ROJO aquí.
- **U6 va a chocar con lo mismo.** La entrada de `CANDIDATAS.md` dice que «no fija tolerancia» y omite NFR-U6-01 y el plan de U6. Eso hay que precisarlo, y lo debe decidir el usuario: o tolerancia absoluta 1e-4, o tolerancia relativa.

### F-03 · AMARILLO (decisión del usuario) · `features.py:22` · `monthly_income` sin log y `proposed_rate_ea` numérica
- **`monthly_income` sin log.** Contradice §3.1. Lo fuerza U0: `derive` no ofrece una transformación logarítmica. La justificación del comentario es parcial: los árboles no cambian con una transformación monótona, pero la envolvente sí, porque Mahalanobis se calcula sobre el ingreso crudo y sesgado. `CANDIDATAS.md` lo dice; el comentario del código no.
- **`proposed_rate_ea` numérica.** §3.1 no fija el tipo. Tratarla como número es razonable. `derive` la entrega como `CategoryFeature`; eso es un defecto de U0 y ya está como candidata.

### F-04 · AMARILLO · `adversarial.py:81-86` y bitácora · casos RT-4 13 y 14, y cifras de la evidencia
- **El diseño no enumera los 18 casos.** BR-U5-17 solo exige dos cosas: que sea una `ApplicationIn` válida y que quede fuera de la envolvente. El código lo comprueba al generar los casos y lo vuelve a probar. Por eso la reescritura no viola ninguna definición.
- **Pero «tasa muy baja» ya no es lo que baja la confianza en el caso 13.** Lo hace `term_months = 12`, el mismo mecanismo del caso 11. Los casos originales cumplían BR-U5-17 y daban 0,05 y 0,13. Eso muestra que una sola feature fuera de rango no se marca como baja confianza: es la debilidad de la fórmula que ya está anotada en `CANDIDATAS.md`.
- **Cifras inexactas.** La bitácora dice «0,0000 a 0,0010» y `CANDIDATAS.md` dice «0,0006». Yo medí un máximo de 0,0013 (RT4-11).

### F-05 · AMARILLO · `tests/property/test_package.py` y `tests/u4_registration_copy.py` · alcance del validador de U4
- **Paquete probado.** La prueba de aceptación de U4 corre sobre `small_release` (6 000 filas), no sobre el paquete de referencia. Yo verifiqué a mano que el de referencia también se acepta.
- **Archivo faltante.** Si falta un archivo listado, la copia lanza `FileNotFoundError` en lugar de `RegistrationRejected`; BR-U4-06 dice «cualquier fallo → 422».
- **Fidelidad.** Por lo demás, cada regla cita el ítem 1 a 5 de BR-U4-06 y corresponde al diseño de U4.

### F-06 · AMARILLO · `test_train.py` · el determinismo no detecta un `nthread` sin fijar
Con 6 000 filas, `nthread` 1, 2, 4 y 8 dan el mismo SHA (`74d8d125…`). Solo `test_training_parameters_are_fixed` protege NFR-U5-10 en esta máquina. Ya está anotado como candidata; queda para el Paso 8.

### Sin hallazgo
- **Alcance.** `adversarial.py` solo genera RT-4: no hay proxy, ni RT-1, ni RT-3. `decision-registry/` no se toca. `features.py`, `calibrate.py` y `explainer_validation.py` caben en los Pasos 3 a 5, y `explainer_validation` ya estaba nombrado en `.importlinter`.
- **Plan y salida.** El plan está marcado `[x]` con `(U05-T02)` y `.out/` está ignorado.
- **`confidence.py`.** Importa solo numpy y la biblioteca estándar, y cuantiza a Decimal4 con redondeo half-up.

## Tareas candidatas
- Reconciliar PBT-U5-03 con BR-U5-12: la monotonía no se cumple con Mahalanobis (ver F-01).
- NFR-U6-01 y el plan de U6: la suma con 1e-6 absoluto es inalcanzable con float32 (ver F-02).
- `derive` de U0: tipos de las features de campo y la feature con log de `monthly_income` (ver F-03).

## Estado del worktree
Limpio: solo cachés ignoradas. El HEAD sigue en `4b31a017`. Hice las mediciones en una copia hecha con `git archive` y no cambié nada en el worktree.

```
VEREDICTO: NO-VERDE
ROJO|reference-model/tests/property/test_envelope.py:113 (CA-2, CA-5)|PBT-U5-03 (monotonía) refutada por Hypothesis; make -C reference-model check RC=2
INFORME: revisiones/U05-T02/ronda-1.md
```
