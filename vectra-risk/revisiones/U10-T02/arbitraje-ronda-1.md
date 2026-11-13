# U10-T02 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, **sin ningún ROJO**: los 12 criterios pasan con la ejecución del revisor sobre `5f6d774`, incluido `make -C console check` (rc 0), y el diff no se sale del alcance. El veredicto no se cambia.

Rige RL-2 y RL-3 (`demo-kind-alcance.md` §6): solo un ROJO abre otra ronda. No se abre la ronda 2 y la tarea pasa a revisión humana con el veredicto tal cual.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: la prueba del pool agotado pasa igual sin pool | Pasa a `CANDIDATAS.md`, con destino U10-T03 o U10-T04 | Es una prueba débil, no un defecto del comportamiento: el revisor demostró con una sonda propia que el límite de 20 conexiones sí rige |
| F-02 AMARILLO: puertos fijos 8080/8081 | Pasa a `CANDIDATAS.md` | El origen es de U0 (`run_service` no acepta puertos), fuera del alcance |
| F-03 AMARILLO: `page_size` 100 sin nombre | Pasa a `CANDIDATAS.md` | Irreal hoy; no lo ve el usuario |
