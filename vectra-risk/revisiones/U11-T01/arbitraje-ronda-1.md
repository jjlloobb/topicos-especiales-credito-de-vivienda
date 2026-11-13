# U11-T01 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un ROJO (F-01). Los 8 criterios pasan como comando; el ROJO es de fondo: PBT-U11-01 no compara la tasa de consulta (BR-U11-07) con un oráculo, y dos mutaciones de la ventana de 7 días sobreviven a toda la suite. Es una de las cifras de la demo D4.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: PBT-U11-01 sin oráculo de la tasa de consulta | **Entra en la ronda 2** | La definición de la PBT nombra BR-U11-07 y la tarea pide la PBT entera. Las PBT no se recortan |
| F-02 NARANJA: NFR-U11-21 y NFR-U11-10, de pasos cubiertos, sin trazar | **Entra en la ronda 2**, solo esos dos | DECISIONES-LOOP §6: un identificador de un paso que la tarea cubre debe quedar trazado |
| F-02, NFR-U11-02 | **No se cita en esta tarea** | Su evidencia es la prueba de volumen del Paso 7, diferida por la demo (enmienda §3, U11, fila «7»). U11-T02 prohíbe escribirlo en `product-metrics/`; va en «Diferido por la demo» del cierre (U11-T03) |
| F-03 NARANJA: rangos de BR-U11-09 como literales en `params.py` | **Entra en la ronda 2** | El Paso 11 (U11-T03) necesita los mismos rangos con nombre; el arreglo es acotado |
| F-04 AMARILLO: PBT-U11-02 acepta una pasada parcial publicada | **Entra en la ronda 2** | Es la fuerza de una PBT de la tarea, y la mutación del revisor ya está descrita |
| F-05 AMARILLO: comentario colgante | **Entra en la ronda 2** | Trivial |
| F-06 AMARILLO: `channel` vacío rechazado contra el contrato; `1 << 16` y `"human_decision"` como literales | **Entra en la ronda 2** | Excluir una entrada válida de U3 cambia las cifras; el arreglo es acotado |
| Candidata: `test_traceability.py` no lee archivos sin sufijo | Pasa a `CANDIDATAS.md` | Es de U1 (`platform/`) |

## Lo que se espera de la ronda 2
- **F-01:**
  - PBT-U11-01 compara con un oráculo que cuenta por definición la tasa de consulta de 7 días por `decided_at`, total y por canal (`explanation_view`), y las ventanas diarias (`explanation_view_daily`);
  - las dos mutaciones del revisor (ventana diaria de 8 días y semana publicada de 8 días, en `compute.py`) quedan en rojo, y la bitácora registra las dos salidas;
  - el código de `compute` no cambia salvo que el oráculo encuentre un defecto real; si lo encuentra, se registra el rojo y se arregla.
- **F-02:** NFR-U11-21 y NFR-U11-10 quedan citados donde se implementan, en archivos que `test_traceability.py` lee. NFR-U11-02, 03 y 13 **no** se escriben en `product-metrics/`.
- **F-03:** los rangos de F, S, N y de los targets pasan a constantes tipadas con nombre (en `config.py` o junto a `params`), y `parse` y sus mensajes las usan. Las pruebas de rangos siguen pasando.
- **F-04:** la pasada con fallo en una página debe terminar en error y dejar el estado anterior; la mutación del revisor (`try/except ReadError: pass` en `state.full_pass`) queda en rojo con PBT-U11-02.
- **F-05:** se completa o se quita el comentario.
- **F-06:** `channel` vacío se acepta si el contrato de U0 lo admite (se comprueba contra `MetricsRecommendationRef`), con una prueba; el tope de `model_version_id` sale del contrato o se quita; `"human_decision"` usa `EntryType`.
- **`CANDIDATAS.md`:** la candidata de `test_traceability.py` y los archivos sin sufijo.
- **Se vuelven a correr:** CA-1 a CA-8, con `make -C product-metrics check` y `make -C platform check` en serie, y `test_traceability.py --all` en la base y en la rama.

Es la última ronda (RL-2). Si F-01 sigue en ROJO, la tarea se para y va al usuario.
