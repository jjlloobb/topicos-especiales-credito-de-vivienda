# U02-T15 — Arbitraje de la ronda 1 (orquestador, 2026-11-06)

Informe: `ronda-1.md`, NO-VERDE.

| Hallazgo | Decisión | Por qué |
|---|---|---|
| Decisión 1 del codificador: sustituto de J3 | **El usuario lo ratifica** | En k6 v2.3.0 `handleSummary` no puede cambiar el código de salida (lo comprobó el revisor). Se enmiendan la nota J3 del plan, NFR-U2-11/12 y la tarea |
| Decisión 2 del codificador: rol `analista` | Se acepta | El revisor lo verificó contra el diseño y el realm. El comportamiento real de Keycloak se mira en el Paso 16 |
| F-01 NARANJA: el sustituto de J3 sin pruebas | Entra en la ronda 2 | Ahora es el mecanismo ratificado; debe tener pruebas |
| F-02 NARANJA: literales del diseño en pruebas | Entra en la ronda 2 | La tarea lo prohíbe |
| F-03 NARANJA: umbral `checks` sin fuente | Entra en la ronda 2 | J5 lo exige como fallo |
| F-04, F-05, F-06 AMARILLO | Entran en la ronda 2 | Arreglos acotados dentro de la tarea |
| F-07 AMARILLO: candidatas fuera de `CANDIDATAS.md` | **Lo hace el orquestador** al abrir el PR | Evita chocar con el PR 71 (U02-T13). El codificador no toca `CANDIDATAS.md` |

## Lo que se espera de la ronda 2

- **F-01**: un caso con la diferencia de p95 por encima de NFR-U2-11 que demuestre `ok:false` en `overhead-verdict.json` y salida distinta de cero de `make -C identity-edge load`, y uno por debajo que salga en 0. Las mutaciones M11, M12, M13 y M20 del revisor deben morir. Los tramos `gateway` y `direct` apuntan a destinos distintos en la prueba falsa, y la prueba lo comprueba.
- **F-02**: las pruebas leen los valores del diseño (NFR, nota del Paso 14, `routes.yaml`, realm) en vez de repetirlos; los patrones de `MUTANTS` se derivan de esos mismos valores.
- **F-03**: el umbral de `checks` se deriva de J7 (o se justifica su fuente en el diseño) y `threshold_problems` lo comprueba; M19 debe morir.
- **F-04**: una prueba falla si el POST de `login-actions` deja de etiquetarse `flow:login` (M18).
- **F-05**: las dos pruebas de copia mutada corren el oráculo real sobre la copia.
- **F-06**: bitácora y docstring de `load_checks.py` dicen que `thresholds` y `scenarios` salen en el primer nivel del JSON de `k6 inspect` v2.3.0.
- Los criterios CA-1 a CA-6 siguen igual. Los 5 fallos de `test_e2e_inventory.py` en CA-5 son de U02-T16, que está en revisión; si U02-T16 llega a `main` antes, se integra `main`.
