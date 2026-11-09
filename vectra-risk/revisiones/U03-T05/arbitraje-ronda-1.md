# Arbitraje de la ronda 1 — U03-T05

Orquestador, 2026-11-09. Informe: `revisiones/U03-T05/ronda-1.md`. NO-VERDE sin ROJO: CA-11b no pasa (presupuesto de kind) y queda un NARANJA (F-01).

## Decisiones

- **CA-11b, presupuesto de kind (decisión del usuario, 2026-11-09).** `BUDGET_GIB` sube de 5,5 a **6,1 GiB, provisional**, hasta la medición de DD-3 con el Paso 16 de U2. El perfil pide 6,012 GiB con `decision-registry`. Se cambia en la ronda 2, en `platform/tests/test_kind_profile.py`, con un comentario que cite esta decisión y DD-3.
- **F-01 (NARANJA), NFR-U3-41.** Va entero a «Diferido por la demo» en `evidence/cierre-demo.md`, con el Paso 11 (`checkpoint`, T5), y se quita la mención del docstring de `test_chart.py:400`. `checkpoint` ya está diferido por la enmienda (§3, U3, Paso 11), y una mención que no prueba nada no es trazabilidad.
- **F-02 a F-08 (AMARILLO)** pasan a `CANDIDATAS.md`; F-02 completa las de CA-2 y CA-7 que ya había dejado el codificador.
- Antes de la ronda 2 el orquestador integró `origin/main` (`9352400`, U04-T01) en la rama. El único conflicto fue aditivo, en `CANDIDATAS.md`.

Ronda 2, la última por RL-2: solo esos dos cambios. Después, CA-9 y CA-11 completos.
