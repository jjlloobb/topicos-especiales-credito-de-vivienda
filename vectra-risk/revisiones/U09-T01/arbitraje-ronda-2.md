# Arbitraje de la ronda 2 — U09-T01

Orquestador, 2026-11-09. En la ronda 2 el codificador se detuvo, como mandaba el arbitraje de la ronda 1: ninguna de las seis reglas que midió cumple las tres condiciones a la vez (`bitacoras/U09-T01.md`, «Ronda 2»; `revisiones/U09-T01/exploracion-ronda-2.py`). No hubo revisión de la ronda 2 porque el código no cambió.

## Decisiones (del usuario, 2026-11-09)

- **Regla R4 para BR-U9-11.** Una versión se congela si el límite inferior del intervalo de la agregada ponderada del atributo, calculado con z de Bonferroni sobre las comparaciones de pares × atributos (z ≈ 3,14 para 60), es mayor que 5 pp. Si todas las agregadas son «muestra insuficiente», no congela, igual que antes. El codificador fija la z exacta y la justifica.
- **Variante proxy más fuerte en U5**, en vez de un lote más grande o de aceptar el 50 %. RT-2 conserva los ~1 500 casos `stratified` y sus 30 min. El cambio de U5 va en una tarea aparte (U05-T05), que se prepara con la cifra que entrega esta ronda.
- **Ronda 3 autorizada por el usuario**, por encima de RL-2.

## Qué entra en la ronda 3

1. **El diseño.** R4 se escribe en BR-U9-11 y en la BLM §3, con la fecha y la cita de este arbitraje. También en BR-U9-04 y 05 si cambian.
2. **El código.** La librería, las PBT afectadas (sin recortarlas) y `library.md`. Se quita el `xfail`.
3. **La simulación, sin `xfail` y con rojo primero contra R0.** Mide tres cosas:
   - la condición 1: congelamientos falsos ≤ 5 % con ≥ 500 casos por celda;
   - la condición 2: el modelo base (4,61 pp) congela ≤ 5 % con celdas de 30 a 100 casos, o con 50 a 100 si se documenta que en 30 casos el margen es de 5,2 %;
   - la condición 3, **reformulada**: **D\***, la disparidad mínima de la variante proxy con la que R4 congela ≥ 95 % con el lote `stratified` de BR-U12-06. Se prueba con una variante sintética de D\* y se documenta en `library.md` como requisito para U5.
4. **El doble de U5** (`tests/doubles/u5_counts.json`) no cambia en esta tarea: lo regenera U05-T05.
5. **La aceptación.** CA-4 a CA-10 completos, con la regla «sin fallos nuevos» para `--all` (`DECISIONES-LOOP.md` §6, en el PR #94).
