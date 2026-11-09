# Arbitraje de la ronda 1 — U05-T05

Orquestador, 2026-11-09. Informe: `revisiones/U05-T05/ronda-1.md`. NO-VERDE por un ROJO (F-01). Los CA-1 a CA-7 pasan y las cifras se reproducen con otras semillas (variante 0,9945–0,9975; base 0,0045–0,0050).

## Decisión (del usuario, 2026-11-09): opción (b)

F-01: con la librería real, `disparity_pp` del manifiesto base pasa de 4.6119 (cifra del doble) a 4.61 (la librería cuantiza a 4 decimales de fracción). Ese valor entra en el hash del id, así que cambian el id base (`mv-2026-01-01-51241dc4` → `mv-2026-01-01-8a98ab02`), los 4 paquetes RT-3 y `adversarial/manifest.json`. El predictor, `background.csv`, los parquet y la política no cambian.

Se **aceptan los ids nuevos**: el 4.6119 solo existía por el doble, que la tarea quitó a propósito, y nada está desplegado. No se fuerza la precisión vieja en el manifiesto.

## Qué entra en la ronda 2 (la última por RL-2)

1. **Evidencia fiel (F-01).** `cierre-demo.md` y la bitácora comparan **contra `origin/main`** (`bb86d71`), no contra corridas intermedias de la rama: tabla de ids viejos (main) → nuevos para la base, la variante (run-1 a run-5) y los RT-3, y la lista de archivos que cambian y de los que quedan idénticos byte a byte, con el SHA-256 de cada lado. Se cita esta decisión.
2. **Referencias al id viejo.** Fuera de bitácoras y revisiones, en `main` solo aparecen en `bias-monitoring/tests/doubles/u5_counts.json` (ya regenerado) y en la URL `isvc-51241dc4` de `model-serving/tests/integration/test_predictor.py`. Ajusta esa URL **solo** si la prueba deja de pasar con el id nuevo (o si deja de ser coherente con el paquete que carga); córrela y registra el resultado.
3. **F-02 (NARANJA).** Corrige la evidencia desactualizada: en `cierre-demo.md`, «Pendiente de U9 (no se tocó)» ya no es cierto (el check de U9 termina en 0); la entrada nueva de `CANDIDATAS.md` queda solo con la recalibración de `DSTAR_T`; y `u5_counts.json` se regenera **después** del commit del código, para que su `u5_commit` apunte al commit real del que salen los conteos.
4. **Candidatas** (sin código): BR-U12-06 no se puede cumplir al pie de la letra con `test` (4 celdas con < 30 casos en total) y la agregada del modelo base en todo `test` (5,51 pp > 5) con el riesgo de R4 en ventanas grandes. El AMARILLO de la prueba `simulation` (reimplementa R4; `assert SAMPLES >= 2_000` siempre pasa) también va a candidatas.

Nada más. El revisor de la ronda 2 comprueba estos puntos con SHA-256 contra `bb86d71`, CA-2, CA-5 y CA-6, y `--all`.
