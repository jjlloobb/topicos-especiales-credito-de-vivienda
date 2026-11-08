# Arbitraje de la ronda 1 — U05-T02

Orquestador, 2026-11-08. Informe: `revisiones/U05-T02/ronda-1.md` (NO-VERDE por un ROJO). Ritmo RL-2: la ronda 2 es la última.

## Decisiones del usuario (2026-11-08)

1. **F-01 (ROJO) — se reformula PBT-U5-03 y se mantiene la fórmula.** Business-logic-model §3 de U5 queda enmendado así: `c_rango` es no creciente cuando una feature numérica se aleja de [p1, p99] y las demás quedan fijas, y `confidence ≤ c_rango` para toda entrada. La monotonía ya no se exige sobre `confidence` completa. BR-U5-12 no cambia.
2. **F-02 — tolerancia absoluta de 1e-4 para la suma de contribuciones más `base_value` contra el margen.** Quedan enmendados NFR-U5-30, NFR-U6-01, el plan de U5 (Paso 5) y el plan de U6 (Paso del explicador). La paridad con `shap` sigue en 1e-6.

Las enmiendas al diseño ya están en la rama, en el commit del arbitraje.

## Qué entra en la ronda 2

- **F-01:** `tests/property/test_envelope.py` implementa la PBT-U5-03 enmendada:
  - `confidence` ∈ [0, 1];
  - `confidence` = 0 con cualquier categoría no vista;
  - `c_rango` no creciente al alejarse;
  - `confidence ≤ c_rango`.

  Borra el contraejemplo de `vectra-risk/.hypothesis/`, que no está versionado, o asegúrate de que la propiedad nueva lo trata como caso válido. **Rojo primero:** con una mutación que hace crecer `c_rango` al alejarse, la propiedad falla.
- **F-02:** el valor `explainer_margin_tolerance: 1.0e-4` de `generator.yaml` ya coincide con el diseño. Cita en el comentario NFR-U5-30 y la fecha de la enmienda. La candidata de la tolerancia en `CANDIDATAS.md` queda como resuelta.
- **F-03:** el comentario de `features.py` dice que la envolvente usa el ingreso crudo. La candidata de `monthly_income` en log menciona su efecto en Mahalanobis.
- **F-04:** corrige las cifras de RT-4 en la bitácora y en `CANDIDATAS.md`, con un máximo de 0,0013.
- **F-05:** si falta un archivo listado, la copia del validador de U4 lanza `RegistrationRejected` (BR-U4-06, cualquier fallo da 422), con una prueba que lo cubra. La prueba de aceptación también corre sobre el paquete de referencia, o se explica en la bitácora por qué basta `small_release`.
- **F-06:** queda solo como candidata, como ya está anotada.

## Aceptación de la ronda 2

Los CA-1 a CA-5 de la tarea, **incluido `make -C platform check`**, que no corrió en la ronda 1. En CA-4, la suma se mide con 1e-4. Corre `make -C reference-model check` al menos dos veces seguidas (o con `--hypothesis-seed` distintas) y registra las dos corridas en la bitácora, para descartar que la suite pase solo por la semilla.
