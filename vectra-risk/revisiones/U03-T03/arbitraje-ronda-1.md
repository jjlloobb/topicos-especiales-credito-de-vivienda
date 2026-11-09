# Arbitraje de la ronda 1 — U03-T03

Orquestador, 2026-11-08. Informe: `revisiones/U03-T03/ronda-1.md`, NO-VERDE por dos ROJO. Ritmo RL-2: la ronda 2 es la última.

## Decisiones

- **F-01 (ROJO) — entra.** Agrega un caso con un `fail_closed` válido para U0 que lleve `{cause, retryable, attempt, escalated_at}` (escalamiento por reintentos agotados) y lo envíe desde `registry:append:scoring`. Debe dar **403**, tanto en la prueba de integración como en la unitaria de `scope_permits`. **Rojo primero:** con la mutación R21 (`payload.local_cause is None`, sin exigir `escalated_at is None`), la prueba falla.
- **F-02 (ROJO) — entra.** El expediente es `not_verified` si la última `full` terminada dio `inconsistente`, y lo sigue siendo hasta que una `full` posterior dé `integra` (BR-U3-13). Toma `first_inconsistent_seq` y `reason` de su `report`. La prueba usa un tramo **limpio** y una última `full` inconsistente; otra, que una `full` posterior `integra` devuelve el expediente a `verified`. **Rojo primero:** con el código de la ronda 1, el caso del tramo limpio falla.
- **F-03 (NARANJA) — entra en parte.** Se renombra la prueba para que diga 422 (U0, BR-U0-38) y no 403. La contradicción entre la viñeta del plan («→ 403») y U0, que rechaza antes del handler, va a `CANDIDATAS.md` para decisión del usuario. No se toca U0. El orquestador no enmienda el plan sin esa decisión.
- **F-04 (AMARILLO) — entra, porque afecta a la demo 7.4.** `POST /v1/monitoring/daily:query` la usa U9 para el freeze. Suma con `GROUP BY` en SQL, en vez de traer las filas diarias, sin cambiar la respuesta. Agrega una prueba de volumen con al menos 300 000 filas en `monitoring_daily` (3 versiones × ≈ 594 celdas × 180 días) que responda dentro de los 2 s del pool `projections`, y regístrala en la bitácora. Si no cabe en 2 s, **detente y repórtalo**.
- **F-05 (AMARILLO).**
  - El script de mutaciones trabaja sobre una copia, no sobre el worktree.
  - Los contenedores huérfanos los detiene el usuario.
- **Las dos candidatas nuevas del revisor** (resultados `inconsistente` de `incremental` y `nightly` fuera de `integrity_checks`; conexiones ociosas sin revisión en `pools.py`) van a `CANDIDATAS.md`.

## Aceptación de la ronda 2

Los CA-1 a CA-6 de la tarea, más los casos nuevos de F-01, F-02 y F-04. Corre `make -C decision-registry check`, `make -C contracts check` y `make -C platform check` completos.
