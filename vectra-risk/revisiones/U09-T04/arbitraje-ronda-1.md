# U09-T04 — Arbitraje de la ronda 1 (orquestador, 2026-11-10)

Informe: `ronda-1.md`, con veredicto NO-VERDE. No tiene ningún ROJO.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: `policy-stale` y `policy-ranges` admiten valores de `stale_after` y `n_min` que el CronJob rechaza | **Entra en la ronda 2** | Rompe la compuerta de cambio de INF-U9-03 y BR-U9-13, y es un defecto del propio diff |
| F-02 NARANJA: el cierre no tiene evidencia de CA-10 y CA-11 | **Entra en la ronda 2** | Ya hay evidencia (anexo de `ronda-1.md`). Hay que citarla en la fila 18 y en la bitácora |
| F-03 AMARILLO: `check` no construye la imagen | Pasa a `CANDIDATAS.md` | — |
| F-04 AMARILLO: `EXPECTED_WAVES` | Se acepta como el mínimo necesario | Tiene precedente en U03-T05 y U04-T06 (`CANDIDATAS.md:303`) |
| F-05 AMARILLO: `services.md` | **Entra en la ronda 2** | Arreglarlo es trivial y la cifra es incoherente. Se quita la sección, como pide P-2 (a), o, si se queda, lleva la cifra medida |
| `STATIC_POLICIES` copiada en el Makefile de U9 | Pasa a `CANDIDATAS.md` | — |

## Lo que se espera de la ronda 2
- **F-01:**
  - booleanos aparte por condición;
  - `is_number` en `n_min`, y `stale_after` que solo admita una duración válida;
  - casos de fallo de `conftest` para `"1h30m"`, `"90"`, `"abc"` y `n_min: "abc"`, con su rojo previo registrado en la bitácora.
- **F-02:** la fila 18 de `cierre-demo.md` y la bitácora citan las cifras del anexo, y cada rc ≠ 0 lleva su causa y su destino (U02-T20, U03-T07, candidata del bench).
- **F-05:** se quita la sección de `services.md`, como pide P-2 (a).
- **Corridas de la ronda 2:**
  - Se repiten CA-2, CA-5 y CA-6, más `make -C bias-monitoring check` y `make -C platform check`, en serie.
  - El resto de CA-11 no hace falta repetirlo, porque la ronda 2 solo toca `bias-monitoring` y la documentación.
