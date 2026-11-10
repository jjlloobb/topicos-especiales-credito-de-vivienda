# U08-T01 — Arbitraje de la ronda 1 (orquestador, 2026-11-10)

Informe: `ronda-1.md`, NO-VERDE, sin ningún ROJO. Los ocho criterios de aceptación pasan con la ejecución del revisor.

Rige RL-2 (`demo-kind-alcance.md` §6): «Solo un ROJO bloquea. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las cuatro demos (§1)».

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: las filas 1, 2 y 4 de `guard_vencido` quedan tapadas por `guard_transition` y ninguna prueba las aísla | **Pasa a `CANDIDATAS.md`** | No rompe ninguna demo. La retención de U8 (CronJob y `vencido`) está diferida por el recorte funcional (`demo-recorte-funcional.md` §3 U8). Las tres filas siguen rechazadas por `guard_transition`, de modo que el comportamiento es correcto. Lo que falta es probar la cuarta barrera de forma aislada |
| F-02 AMARILLO: índice único sin predicado; BR-U8-09 no dice si `no_disponible` borra el trabajo | **Pasa a `CANDIDATAS.md`** | Hay que precisarlo antes de U08-T03, que implementa el `retry` |
| F-03 AMARILLO: `retention_runs.finished_at NOT NULL` frente a `finished_at?` | **Pasa a `CANDIDATAS.md`** | Desvío coherente con el propio párrafo del diseño. Queda registrado |

No hay ronda 2. La tarea pasa a revisión humana en un PR, con el veredicto del revisor tal cual (NO-VERDE por un NARANJA) y este arbitraje.
