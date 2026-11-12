# U08-T04 — Arbitraje de la ronda 1 (orquestador, 2026-11-12)

Informe: `ronda-1.md`. Veredicto NO-VERDE, con un ROJO (F-01). Los 10 criterios pasan como comando y 18 de 19 mutaciones del revisor mueren. El ROJO es de fondo: el resultado tardío de una toma de un ciclo anterior se aplica al caso cuando `attempts` volvió a 0 (tras congelar y descongelar, o tras el `retry` del CRO), y PBT-U8-01 no lo ve porque su modelo copia la guarda del código. Es el recorrido de la demo D2.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| F-01 ROJO: un resultado tardío de otro ciclo se aplica; el modelo de PBT-U8-01 copia la guarda | **Entra en la ronda 2** | Incumple el invariante de PBT-U8-01 («el resultado de una toma anterior nunca modifica el caso»), que CA-2 exige, y rompe D2 |
| F-02 NARANJA: ninguna prueba distingue `SKIP LOCKED` | **Entra en la ronda 2** | P-U8-01 pide no esperar a la fila bloqueada y nada lo fija; el arreglo es una prueba |
| F-03 AMARILLO: «recién iniciado → 0» depende del orden | **Entra en la ronda 2** | Trivial |
| F-04 AMARILLO: la gracia de 20 s no empieza en el `SIGTERM` | **Entra en la ronda 2** | Es código de esta tarea y U08-T05 necesita el peor caso real para `terminationGracePeriodSeconds` |
| Candidata: decisión `pendiente_registro` cuyo caso vence antes del ack | Queda en `CANDIDATAS.md` | Código de U08-T03; solo ocurre con la retención del Paso 16, diferido; ninguna demo la corre |

## Precisión del diseño que acompaña a F-01
BR-U8-08 dice «como cada toma incrementa el número (BR-U8-07), el resultado tardío de una toma anterior nunca pasa la guarda». Es falso cuando `attempts` vuelve a 0. La ronda 2 precisa BR-U8-08 y business-logic-model §4 con la guarda nueva, igual que la ronda 1 precisó BR-U8-12 (P-1). No cambia ningún comportamiento que el diseño pida: lo hace cumplir.

## Lo que se espera de la ronda 2
- **F-01:**
  - rojo primero: la reproducción del revisor (`test_rev_aba.py`, en su scratchpad; ruta en `ronda-1.md`) pasa a ser una prueba de la tarea, en sus dos variantes (congelar → descongelar, y 403 → `retry` del CRO), y se registra su fallo sobre el código actual;
  - la guarda identifica **la toma**, no el número de intento: por ejemplo con el `locked_until` que fijó esa toma o con un identificador de toma. **Sin migración nueva:** si no hay forma de hacerlo con las columnas que ya existen, el codificador para y lo reporta con las opciones; no cambia `migrations/` por su cuenta;
  - el modelo de PBT-U8-01 deja de copiar la guarda: marca como vigente solo la toma que no tiene otra posterior, sea cual sea el valor de `attempts`. La PBT debe encontrar el defecto sobre el código actual (se registra el rojo, con su semilla) y un contador de recorrido nuevo, «resultado tardío tras reinicio de `attempts`», debe quedar > 0 con el perfil `ci`;
  - BR-U8-08 y business-logic-model §4 quedan precisados; `services.md` lo anota.
- **F-02:** una prueba que falla con `FOR UPDATE` sin `SKIP LOCKED`: con una fila bloqueada por otra transacción, la toma no espera y devuelve otro trabajo o ninguno, dentro de un plazo. La mutación M01 del revisor queda en rojo.
- **F-03:** la prueba no depende del valor absoluto de un contador global ni del orden.
- **F-04:** el apagado empieza la gracia en el `SIGTERM` aunque los 16 huecos estén ocupados, con una prueba; `services.md` dice el peor caso real del apagado, para U08-T05.
- **Se vuelven a correr:** CA-1 a CA-10, con `make -C case-management check`. La cobertura de los 8 módulos sigue al 100 % sin `omit` ni `pragma`.

Es la última ronda (RL-2). Si F-01 sigue en ROJO, la tarea se para y va al usuario.
