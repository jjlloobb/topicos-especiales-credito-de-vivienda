# U11-T02 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, **sin ningún ROJO**: los 10 criterios pasan con la ejecución del revisor sobre `b5bde13`, incluido `make -C product-metrics check` (rc 0), y el diff no se sale del alcance. El veredicto no se cambia.

Rige RL-2 y RL-3 (`demo-kind-alcance.md` §6): solo un ROJO abre otra ronda. No se abre la ronda 2 y la tarea pasa a revisión humana con el veredicto tal cual.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: ninguna prueba fija que la página en vuelo termine | Pasa a `CANDIDATAS.md`, con destino U11-T03 | Prueba débil; el revisor demostró con una sonda propia que el código real termina la página |
| F-02 NARANJA: plazo de 75 min y reinicio diario de reintentos sin fijar | Pasa a `CANDIDATAS.md`, con destino U11-T03 | Pruebas débiles; el comportamiento actual es el correcto |
| F-03 NARANJA: `capture_signals` redundante y texto que atribuye mal el código 0 | Pasa a `CANDIDATAS.md`, con destino U11-T03 | Código muerto y documentación; no cambia el comportamiento |
| F-04, F-05 y F-06 AMARILLO | Pasan a `CANDIDATAS.md` | No bloquean |

Las desviaciones que el codificador declaró (CA-3 con dos subprocesos, el cambio de `test_reader.py`, el doble de U3 ampliado, P-2 (b)) las juzgó el revisor una por una y ninguna es hallazgo.
