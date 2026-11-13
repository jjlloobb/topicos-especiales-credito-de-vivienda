# U08-T04 — Arbitraje de la ronda 2 (orquestador, 2026-11-12)

Informe: `ronda-2.md`. Veredicto NO-VERDE, con un ROJO nuevo (F-01 de la ronda 2). El ROJO de la ronda 1 (resultado tardío de otro ciclo) quedó cerrado: la guarda por toma resistió los ataques del revisor y PBT-U8-01 ya no copia la guarda.

RL-2 fija un máximo de 2 rondas. **El usuario autorizó el 2026-11-12 una ronda 3 acotada** a lo que sigue, como excepción: el ROJO que queda es una sola prueba, y es la que fija el contador que sostiene la demo D3.

| Hallazgo (ronda 2) | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: «`GET /metrics` recién iniciado → `vectra_core_write_attempts_total` = 0» quedó sin prueba | **Entra en la ronda 3** | Línea de aceptación del Paso 17 (CA-4); la prueba actual compara contra la variable del módulo |
| F-02 AMARILLO: la guarda de toma en `_FROZEN`, `_RETRY` y `_ESCALATE` solo la cubre la PBT | **Entra en la ronda 3** | Tres pruebas deterministas baratas sobre el arreglo central de la tarea |
| F-03 AMARILLO: BR-U8-08 no dice su supuesto de reloj | **Entra en la ronda 3** | Una frase |
| F-04 AMARILLO: `services.md` exagera el caso normal del apagado | **Entra en la ronda 3** | Una frase; U08-T05 lee ese texto |
| Candidata: el puerto fijo 8081 de `test_worker_shutdown.py` | Pasa a `CANDIDATAS.md` | Choca entre suites concurrentes; no es de esta ronda |

## Lo que se espera de la ronda 3 (y nada más)
- **F-01:** una prueba que arranca el mock en un **proceso nuevo** (por ejemplo `subprocess.run([sys.executable, "-c", …])` con `build_app` y `GET /metrics`) y afirma que `vectra_core_write_attempts_total` vale 0. La métrica se lee de `/metrics`, no de la variable del módulo, y la prueba no depende del orden. La mutación M22 del revisor (`WRITE_ATTEMPTS.inc(3)` al importar `metrics.py`), hecha sobre una copia, queda en rojo, y la bitácora lo registra.
- **F-02:** pruebas deterministas en `test_worker.py` con un resultado tardío de un ciclo anterior que no es `Recommendation`: `model_frozen`, 503 reintentable y 403. La mutación M21b del revisor (guarda anulada en `_FROZEN`, `_RETRY` y `_ESCALATE`) queda en rojo sin depender de la PBT.
- **F-03:** BR-U8-08 dice que la garantía supone un reloj coherente entre los pods que toman y los que recrean el trabajo.
- **F-04:** `services.md` dice que el caso normal del apagado termina cuando terminan las llamadas en vuelo (segundos con un scoring sano) y conserva el peor caso de ≈ 34 s.
- **No se toca nada más:** ni `evaluation.py`, ni `job_queue.py`, ni la PBT, ni el código del mock (salvo que F-01 destape un defecto real, que se registra con su rojo).
- **Se vuelven a correr:** CA-3, CA-4, CA-6, CA-7 y `make -C case-management check` una vez. Los demás criterios no cambian.

Si queda un ROJO tras esta ronda, la tarea se para y va al usuario.
