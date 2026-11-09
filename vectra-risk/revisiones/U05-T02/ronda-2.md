# Ronda 2 — U05-T02

VEREDICTO: VERDE

Revisé el sha `96cea22` en la rama `tarea/U05-T02`. Corrí yo mismo los CA-1 a CA-5, incluido `make -C platform check`, y todos pasan. El ROJO de la ronda 1 (F-01) quedó cerrado según la enmienda del usuario, y no queda ningún ROJO ni NARANJA en pie. Quedan tres AMARILLO, ninguno bloquea.

## Criterios de aceptación, verificados por mí
| # | Comando que corrí | Resultado |
|---|---|---|
| 1 | `test_train.py`, dentro de la suite completa (corridas 1 y 2) | pasa |
| 2 | `HYPOTHESIS_PROFILE=ci ... test_envelope.py --cov=...confidence --cov-fail-under=100 --hypothesis-seed=777` | pasa: 21 pruebas; `confidence.py` con 40 sentencias y 12 ramas al 100 % |
| 3 | `uv run pytest reference-model/tests -k numpy_only -v` | pasa: 2 pruebas |
| 4 | `test_package.py` y `test_explainer_parity.py`, dentro de la suite completa | pasa, con la suma medida contra 1e-4 |
| 5a | `make -C reference-model check`, corrida 1 (semilla aleatoria del perfil `ci`) | pasa: ruff bien, 3 contratos de import-linter cumplidos, 91 pruebas en 482 s, RC=0 |
| 5b | La misma orden de pytest del Makefile con `--hypothesis-seed=20261108` | pasa: 91 pruebas en 443 s, RC=0 |
| 5c | `make -C platform check` | pasa: 745 pruebas, 2 charts sin fallos, 81/81 pruebas de Kyverno, promtool e integración, RC=0 |

## Comprobación de las correcciones
- **F-01, cerrado.** `test_envelope.py` cubre las cuatro partes de la PBT-U5-03 enmendada (business-logic-model §3):
  - `confidence` en [0, 1];
  - 0 con una categoría no vista;
  - `c_rango` no crece al alejarse, partiendo desde dentro o desde fuera del rango;
  - `confidence ≤ c_rango`.

  Hice el rojo yo mismo en copias de `git archive`:
  - mutante A, con `c_rango = outside/len` (crece al alejarse): fallan 2 pruebas, la de monotonía de `c_rango` y la del caso del revisor;
  - mutante B, con `confidence = c_dist` (sin el `min`): falla 1 prueba, la de una feature apenas fuera de rango.

  Con el código real, mi contraejemplo de la ronda 1 (`scripts/mono.py`) se trata ahora como caso válido. `confidence` sigue subiendo (0,0135413076162 → …639), pero `c_rango` baja de 1,0 a 0,889 y `confidence ≤ c_rango` en los 7 desplazamientos que probé. La propiedad no se debilitó más allá de la enmienda. `.hypothesis/` se borró, y BR-U5-12 no cambió.
- **F-02, cerrado.** `generator.yaml` cita la enmienda del 2026-11-08, y la candidata quedó marcada como resuelta.
- **F-03, cerrado.** El comentario de `features.py` y la candidata ya dicen que la envolvente usa el ingreso crudo (efecto sobre Mahalanobis), y que `proposed_rate_ea` se trata como numérica.
- **F-04, cerrado.** El máximo de RT-4 figura como 0,0013 en `CANDIDATAS.md` y en la bitácora.
- **F-05, cerrado.**
  - Si falta un archivo listado, la copia de U4 lanza `RegistrationRejected("file_missing:…")`; si falta el manifiesto, `manifest_missing`. Las dos tienen prueba.
  - `test_the_u4_validator_accepts_the_reference_package` usa `reference_release` y pasa en mis dos corridas.
- **F-06.** Queda solo como candidata.
- **Enmiendas de diseño del commit a300f5e.** El contenido es coherente en los cinco documentos: 1e-4 absoluto para la suma en NFR-U5-30, NFR-U6-01 y los planes de U5 y U6, y 1e-6 para la paridad con `shap`. En el resto de `aidlc-docs` no queda ningún 1e-6 aplicado a la suma: las dos menciones restantes, en los planes de NFR de U5 y de U6, hablan de la paridad con `shap`.

## Hallazgos
### F-07 · AMARILLO · `model-serving/nfr-requirements/nfr-requirements.md:15` y `plans/model-serving-code-generation-plan.md:78` · paréntesis sin cerrar
- **NFR-U6-01:** dice `(tolerancia absoluta 1e-4: … 8,5e-6(enmienda … U05-T02);`. Se abren dos paréntesis y se cierra uno, y falta un espacio antes de `(enmienda`.
- **Plan de U6:** dice `(tolerancia absoluta 1e-4, NFR-U6-01(enmienda … U05-T02), y la respuesta…`. El mismo problema.
- **NFR-U5-30 y plan de U5:** dicen `U6 NFR Q1;enmienda`, sin espacio.

No cambia el sentido, pero ese es el texto que U6 leerá como criterio.

### F-08 · AMARILLO · `tests/property/test_envelope.py`, `test_pbt_u5_03_the_counterexample_of_the_review_is_a_valid_case` · el nombre promete más de lo que prueba
La prueba usa los puntos medios de la caja, no mi contraejemplo (ITI = 1,0, antigüedad = 1, ltv desde 0,9). Tampoco comprueba que `confidence` suba. Fija lo que hace falta (que `c_rango` no crezca y que `confidence ≤ c_rango`), pero no ese caso concreto.

### F-09 · AMARILLO · `bitacoras/U05-T02.md`, Ronda 2, CA-2 · cifra inexacta
La bitácora dice «23 passed», pero `test_envelope.py` tiene 21 pruebas: mi corrida las recogió y pasaron las 21. El total de 91 sí coincide.

## Tareas candidatas
- Corregir la puntuación de las enmiendas de F-07 la próxima vez que se toquen esos documentos.

## Estado del worktree
Limpio: solo cachés ignoradas. El HEAD sigue en `96cea22`. Corrí los mutantes en copias del scratchpad, con su propio `.hypothesis`.

```
VEREDICTO: VERDE
AMARILLO|model-serving nfr-requirements.md:15, model-serving-code-generation-plan.md:78|paréntesis sin cerrar en las enmiendas de 1e-4
AMARILLO|tests/property/test_envelope.py (the_counterexample_of_the_review)|la prueba no usa el contraejemplo real
AMARILLO|bitacoras/U05-T02.md Ronda 2 CA-2|«23 passed», en realidad son 21 pruebas
INFORME: revisiones/U05-T02/ronda-2.md
```

Nota del orquestador: F-07 lo corrigió el orquestador en este mismo PR, porque el texto de las enmiendas era suyo.
