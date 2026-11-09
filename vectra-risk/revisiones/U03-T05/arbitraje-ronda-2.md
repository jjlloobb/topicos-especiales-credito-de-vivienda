# Arbitraje de la ronda 2 — U03-T05

Orquestador, 2026-11-09. Informe: `revisiones/U03-T05/ronda-2.md`. El veredicto del revisor es NO-VERDE, con un ROJO (F-01, CA-9) y dos AMARILLO. El veredicto no se cambia: este arbitraje lo resuelve con una decisión del usuario.

## Decisiones

- **F-01 (ROJO), CA-9 `test_traceability.py --all`. Decisión del usuario, 2026-11-09: regla «sin fallos nuevos».**
  - **La regla.** `--all` cuenta como pasado si cumple dos condiciones a la vez:
    1. cada línea que falla pertenece a una unidad que todavía no cerró para la demo (sin `evidence/cierre-demo.md`);
    2. el conjunto de fallos es idéntico al de `main` en la base de la rama.
  - **Por qué pasa aquí.** El revisor demostró las dos cosas: las 26 líneas son de U4 (`governance`, en curso desde U04-T01), salen iguales en `9352400` y en `c620c4f`, y `--unit decision-registry --all` da rc=0.
  - **Alcance.** La regla rige para todas las tareas del loop de la demo, empezando por U04-T03 y U09-T01. Queda en `DECISIONES-LOOP.md`.
  - **Después.** El arreglo de la herramienta, para que `--all` omita las unidades sin cierre, está en `CANDIDATAS.md`.
- **F-02 y F-03 (AMARILLO).** Van a `CANDIDATAS.md` (commit `076b248`).

Con esto, CA-9 y CA-11 pasan. La tarea pasa a revisión humana.
