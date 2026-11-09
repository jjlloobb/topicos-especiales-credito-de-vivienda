# Arbitraje de la ronda 1 — U03-T04

Orquestador, 2026-11-09. Informe: `revisiones/U03-T04/ronda-1.md`. Salió NO-VERDE con un NARANJA, cinco AMARILLO y ningún ROJO. Los criterios 1 a 4a pasan en las corridas del revisor. El 4b (`make -C platform check`) sale con 2 solo porque faltan `k6` y `egctl` en `platform/.tools/bin`; los pasos sustantivos pasan, y el diff no toca `platform/`.

## Decisión: no se abre ronda 2 (RL-2) y se abre el PR

RL-2 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6) dice que solo un ROJO bloquea. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las cuatro demos.

- **F-01 (NARANJA)**, `backoffLimit: 0` en el CronJob `registry-aggregator`, contra el `backoffLimit: 1` de INF-U3-03. No rompe la demo 7.4: si una corrida falla, la siguiente corrida del CronJob retoma desde la marca de agua (la transacción del lote deshace la marca y los conteos juntos, como verificó el revisor con una mutación). Pasa a candidata: llevarlo a 1 y ajustar `aggregator.rego` y `test_chart.py`.
- **F-02 a F-06 (AMARILLO)** pasan a candidatas. F-04 es del entorno, no del diff, y el CI corre `make -C platform check` completo.

## `checkpoint`: decisión del usuario y enmienda del alcance

- El revisor confirma que el vacío de diseño de BR-U3-08 es real.
- El usuario eligió la **opción A** el 2026-11-09: firmar el `recorded_at` de la entrada cubierta (`checkpoint_seq`), con el cambio de `verify.check_checkpoint` y de domain-entities §2.1.
- Ese mismo día aprobó `aidlc-docs/construction/plans/demo-recorte-funcional.md`, que difiere `checkpoint` del Paso 11 (§3, U3). Por eso `checkpoint.py` y sus dos casos no entran en esta tarea. La opción A queda registrada en `CANDIDATAS.md` para el cierre completo.
- `verify`, `archive`, `worm` y las políticas HCL ya estaban implementados y probados. Se quedan (§7 de la enmienda).
