# Arbitraje de la ronda 1 — U05-T04

Orquestador, 2026-11-09. Informe: `revisiones/U05-T04/ronda-1.md`. Salió NO-VERDE con un NARANJA, cuatro AMARILLO y ningún ROJO. Los tres criterios de aceptación pasan en las corridas del propio revisor.

## Decisión: no se abre ronda 2 (RL-2) y se abre el PR

RL-2 (`aidlc-docs/construction/plans/demo-kind-alcance.md` §6) dice que solo un ROJO bloquea. NARANJA y AMARILLO van a `CANDIDATAS.md`, salvo que rompan una de las cuatro demos. Ninguno la rompe:

- **F-01 (NARANJA)**, `PROXY_RUNS = 5` en `verify_release.py`, repite a mano `proxy.rt2_runs` de `generator.yaml`. Hoy los dos valen 5, y la demo corre 1 versión (DD-1) de las 5 que se generan. El riesgo solo aparece si alguien cambia `rt2_runs`. Pasa a candidata, junto con las cifras incrustadas en `release.md` («5 corridas», «7 archivos», «6 prefijos `mv-…`»).
- **F-02 (AMARILLO)**: el paso 3 de `release.md` usa `minio/root`. Está declarado en el documento, en `cierre-demo.md` y en la candidata de U1 que ya existe. Se agrega a esa candidata marcar el paso como `[PENDIENTE U1]`.
- **F-03 (AMARILLO)**: NFR-U5-01, 02 y 20 cuentan como trazados solo porque se mencionan en «Diferido». Se suma a la candidata de `test_traceability.py` que ya existe.
- **F-04 (AMARILLO)**: `pytest.ini` usa una ruta relativa y desplaza la configuración raíz de pytest. Pasa a candidata.
- **F-05 (AMARILLO)**: `verify_release.py` acepta `"files": []` y no reporta subdirectorios. Pasa a candidata.
