# U10-T04 — Arbitraje de la ronda 1 (orquestador, 2026-11-13)

Informe: `ronda-1.md`. El revisor escribió NO-VERDE **sin ningún ROJO**: un NARANJA (F-01) y cinco AMARILLO. El veredicto se conserva tal cual en el informe.

**Decisión: no hay ronda 2; la tarea pasa a pull request.** RL-2 (`demo-kind-alcance.md` §6) dice que solo un ROJO bloquea, y que NARANJA y AMARILLO van a `CANDIDATAS.md`. El revisor comprobó que los nueve criterios pasan y que D1, D2 y el flujo base llaman a las rutas reales del BFF. El pull request dice el veredicto y F-01 con claridad, para que el usuario decida si quiere el arreglo antes de fusionar.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 NARANJA: el filtro de fecha de la bandeja manda `-05:00` y el BFF real responde 422 | `CANDIDATAS.md`, con aviso al usuario | Defecto real, pero ninguna demo usa el filtro de fecha. **Riesgo:** si el presentador filtra por fecha en vivo, verá un error de validación |
| F-02 AMARILLO: el 80 % de ramas se mide sobre el total, no por archivo | `CANDIDATAS.md` | Viene de U10-T03; el criterio pasa |
| F-03 AMARILLO: el `<meta>` depende del id interno de react-aria | `CANDIDATAS.md` | La prueba de CSP en e2e lo protege |
| F-04 AMARILLO: el `await` de `acceptStepUp` en `wiring.ts` solo lo cubre la e2e | `CANDIDATAS.md` | La e2e lo detecta (4 casos) |
| F-05 AMARILLO: literales `KNOWN_CHANNELS` y `page_size: 100` | `CANDIDATAS.md` | El primero ya era candidata |
| F-06 AMARILLO: el recorrido de CSP y axe de `cumplimiento` no pasa por `/modelos` | `CANDIDATAS.md` | Otros dos roles cubren la vista |
| CA-8: el revisor no corrió `--all` sobre la base | Se acepta | El conteo de `console` coincide con el de la tarea, y fuera de `console` el diff solo agrega texto |
| `make -C contracts check`: `bench_gate` falló bajo carga y pasó aislado | Se acepta | El diff no toca Python de U0; es la candidata conocida de las medidas de tiempo bajo carga |
