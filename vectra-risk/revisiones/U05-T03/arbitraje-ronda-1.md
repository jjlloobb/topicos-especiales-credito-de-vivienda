# Arbitraje de la ronda 1 — U05-T03

Orquestador, 2026-11-09. Informe: `revisiones/U05-T03/ronda-1.md`, NO-VERDE por un ROJO. Ritmo RL-2: la ronda 2 es la última.

## Decisión sobre F-01 (ROJO) — entra, con dos partes

1. **El doble de U9 sigue BR-U9-01.** `disparity_pp` deja de recibir `p` y recibe el outcome de BR-U7-04/05:
   - `revision_requerida` si `confidence < low_confidence_threshold` (con la envolvente del paquete y el umbral calibrado);
   - `revision_requerida` si la tasa supera la usura o si `normative` es nulo;
   - si no se cumple nada de lo anterior, `favorable` cuando `score < cutoff`.

   `revision_requerida` cuenta como **no** favorable. La docstring se corrige.

   Agrega una prueba con una celda de casos `p < cutoff` y baja confianza, que deben salir no favorables. **Rojo primero:** con el doble de la ronda 1 (`p < cutoff`), esa prueba falla.
2. **La base vuelve a cumplir BR-U5-06 (< 5 pp) medida así.** Ajusta el generador del dataset base (`generator.yaml`: correlaciones, ingreso ↔ estrato, o lo que reduzca la dependencia por estrato) sin romper nada de lo que ya se cumple:
   - AUC de validación ≥ 0,85 (BR-U5-08);
   - calibración de U05-T02: los 18 RT-4 por debajo del umbral y ≥ 95 % de `test` por encima (BR-U5-13);
   - la variante con disparidad ≥ 10 pp (BR-U5-14), medida también con el outcome completo;
   - los demás criterios de U05-T01 a U05-T03.

   La disparidad de la base y la de la variante, medidas con el outcome completo, quedan registradas en la bitácora y en el manifiesto.
   **Si no logras < 5 pp sin romper alguna de esas condiciones, detente y repórtalo** con las cifras: lo decide el usuario. No relajes el umbral ni la definición de outcome.

## AMARILLO — entran, porque son baratos y la ronda se abre de todos modos

- **F-02:** el comentario de `zona_4` dice pacífica + amazonia.
- **F-03:** la prueba se renombra, o se le agrega el caso de zona chica.
- **F-04:** el generador `PRINTABLE` incluye `\n`, `\r` y `\t`, como admite `check_free_text` de U0.

## Candidata

Cuando exista `vectra_disparity`, hay que comprobar que el reemplazo del doble usa outcomes. Ese aviso se agrega a la candidata del doble en `CANDIDATAS.md`.

## Aceptación de la ronda 2

Los CA-1 a CA-4 de la tarea, con el `check` completo de U5 y de U1, más la prueba nueva del doble.
