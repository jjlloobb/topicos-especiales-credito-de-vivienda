# Arbitraje de la ronda 1 — U07-T01

Orquestador, 2026-11-10. Informe: `revisiones/U07-T01/ronda-1.md`. NO-VERDE por F-01 (ROJO por la regla de `--all` con su enmienda).

## Qué entra en la ronda 2 (la última por RL-2)

1. **F-01.** Trazar NFR-U7-30, NFR-U7-32, NFR-U7-43 y P-U7-07 en un archivo que `platform/tests/test_traceability.py` lea (docstring de la prueba que lo verifica, o comentario del `Makefile` junto al objetivo de `lint-imports`), donde de verdad se cumplen. No cambiar `test_traceability.py`. Correr `--all` en la rama y en `origin/main` y registrar en la bitácora que ningún fallo es de los Pasos 1 o 2.
2. **F-02.** Un comentario en `.importlinter` sobre `vectra_common` como raíz.
3. **F-03 y la candidata del revisor.** A `CANDIDATAS.md`: la estructura sin `pyproject.toml` de unidad (con el juicio del revisor: no hace falta) y que `test_traceability.py` lea `.importlinter`.

Nada más.
