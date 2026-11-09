# Arbitraje de la ronda 1 — U09-T01

Orquestador, 2026-11-09. Informe: `revisiones/U09-T01/ronda-1.md`. NO-VERDE por un ROJO (F-01, CA-8).

## Decisiones

- **F-01 (ROJO), BR-U9-11. Decisión del usuario, 2026-11-09: corregir la regla.** No se acepta como
  limitación ni se sube `n_min`. La regla actual elige el par extremo (`max − min` entre hasta 6
  grupos), que nunca es negativo, y toma el máximo sobre 4 atributos sin corregir la multiplicidad.
  Con disparidad real 0 congela el 97,4 % de las veces con 500 casos por celda. En la demo eso
  congelaría también el modelo de referencia (D4, flujo base).

  En la ronda 2, el codificador **elige y documenta** una regla que controle la multiplicidad (por
  ejemplo, un intervalo con Bonferroni sobre pares y atributos, o un grupo de referencia fijado de
  antemano). La regla tiene que cumplir las **tres** condiciones siguientes, y la simulación las
  mide y lo prueba sin `xfail`:
  1. **CA-8.** La tasa de congelamientos falsos con disparidad real 0 es ≤ 5 % con ≥ 500 casos por
     celda. Además, `library.md` documenta la tasa para 30, 100, 500 y 2 000 casos.
  2. **El modelo base no congela en la demo.** Con la disparidad del modelo base de U5 (4,61 pp,
     `revisiones/U05-T03/`) y celdas de 30 a 100 casos, la tasa de congelamiento es ≤ 5 %.
  3. **La variante proxy sí congela en D2 (RT-2).** Con la disparidad de la variante proxy de U5
     (11,66 pp) y el lote `stratified` de BR-U12 (~1 500 casos, ≥ 30 por celda), la tasa de
     congelamiento es ≥ 95 %.

  Si no hay una regla que cumpla las tres a la vez, el codificador **se detiene** y lo reporta con
  las cifras medidas. No elige en silencio cuál de las tres sacrificar.

  El cambio de diseño se escribe en BR-U9-11
  (`aidlc-docs/construction/bias-monitoring/functional-design/business-rules.md`) y en la BLM §3
  (`business-logic-model.md`, la viñeta de la simulación), con la fecha y la cita de esta decisión.
  La regla sigue en las mismas unidades (pp) y conserva el umbral de 5 pp sobre la agregada. Si BR-U9-04
  o BR-U9-05 cambian, también se actualizan, y la PBT que los cubre se ajusta sin recortarla.
- **F-02 (AMARILLO).** Desaparece con F-01: el `xfail` se quita.
- **F-03, F-04 y F-05 (AMARILLO)** pasan a `CANDIDATAS.md`.

Ronda 2, la última por RL-2: F-01 y nada más. Después, CA-4 a CA-10 completos.
