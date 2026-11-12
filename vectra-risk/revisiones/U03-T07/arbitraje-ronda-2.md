# U03-T07 — Arbitraje de la ronda 2 (orquestador, 2026-11-12)

Informe: `ronda-2.md`. Veredicto NO-VERDE, con un ROJO: con el tope en 1,5 s (opción (a) del arbitraje de la ronda 1), las formas reales de U9 reciben 504 cuando la máquina está cargada (3 de 17 corridas de CA-2, 1 de 15 de CA-3, y `make -C decision-registry check` en exit 2). El codificador midió lo mismo. Ningún margen cumple CA-2 y CA-3 a la vez de forma fiable en esta máquina.

**Decisión del usuario (2026-11-12): la tarea se aparca.** No se abre ronda 3 ni pull request. `main` se queda sin el tope por solicitud.

Por qué:
- La tarea no sostiene el flujo de ninguna demo: es un endurecimiento.
- Fusionar el tope de 1,5 s pondría en riesgo la demo D2: si U3 responde 504 al cron de U9, la corrida de U9 falla con `reason=lectura` y nunca congela (BR-U9-10). La demo corre sobre kind en esta misma máquina, con una carga como la medida.
- Sin el tope, la consulta termina dentro de los 5 s que U9 le concede (`QUERY_TIMEOUT_S`).

Lo que queda:
- La rama `tarea/U03-T07` se conserva con sus dos rondas, sus medidas y este arbitraje.
- La candidata «Prioritaria» de `CANDIDATAS.md` sigue abierta, con destino «después de la demo». El camino que da holgura es la candidata del índice: la consulta sin versión hace `Parallel Seq Scan` (toca migraciones).
- En `main`, la prueba de tiempos de `decision-registry` (`best_of`) sigue pudiendo fallar bajo carga; es la misma candidata.
- Lo aprovechable de la rama cuando se retome: `prepare=False` en las sentencias de `daily:query` con su guarda determinista sobre `pg_prepared_statements`, y el `arm` por sentencia en `monitoring_lag`.
