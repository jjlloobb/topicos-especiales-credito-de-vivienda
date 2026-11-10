# Cierre de U4 con alcance acotado a la demo

Esta tarea (U04-T06) crea el archivo solo con la sección «Diferido por la demo»; el resto del cierre (lo comprobado, lo no comprobado, quién ejecutó) es de U04-T07.

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit governance --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los Pasos 16, 17 (`slo.md`, `CompensationEventPending`), 18 y 19 (cobertura y trazabilidad) entraron en U04-T06 y se trazan en el chart, las pruebas y el `Makefile`.

La prueba marcaba 14 identificadores sin trazabilidad al empezar la tarea. Se justifican así: cuatro quedaron cubiertos por lo que entra (INF-U4-04: F44, F47, F101, F102 y la ruta `freeze` en `test_chart.py`; NFR-U4-01: `docs/slo.md`; NFR-U4-03: el chart y `test_chart.py`; NFR-U4-41: la cobertura de ramas del `Makefile`, sin `mutmut`). Los diez que siguen son los de esta lista.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| INF-U4-02 | Paso 15 (`model-archive`) | Enmienda §3 U4, Paso 15; T5 | CronJob diario de archivo, bucket `vectra-model-archive` con WORM `COMPLIANCE` y verificación del SHA-256 |
| NFR-U4-31 | Paso 15 (`model-archive`) y bucket `model-store` de U1 | Enmienda §3 U4, Paso 15; T5 | Retención de 10 años de los artefactos de toda versión que estuvo `activo`, con **[VERIFICAR]** y una prueba en MinIO |
| NFR-U4-22 | Paso 14 (`branch-protection-check`) | Enmienda §3 U4, Paso 14; T4 | Verificación de la protección de `main` del monorepo (≥ 1 aprobación de una persona distinta del autor) |
| NFR-U4-07 | Paso 17 (alerta `ServingConfigUnavailable`, SEV1) | Enmienda §3 U4, Paso 17; T2 | Las demás alertas de P-U4-08 y sus runbooks; solo entra `CompensationEventPending` (P-3) |
| NFR-U4-10 | Paso 19 (script k6 de `serving-config`) | Enmienda §3 U4, Paso 19; T3 | p95 ≤ 20 ms con 12 clientes cada 5 s y una lectura de `feature_spec` por cliente de U8 al cambiar de versión |
| NFR-U4-11 | Paso 19 (script k6 de transiciones con firma) | Enmienda §3 U4, Paso 19; T3 | p95 ≤ 500 ms incluido el append al registro |
| NFR-U4-02 | Paso 20 (escenario 7) y prueba de U7 | Enmienda §3 U4, Paso 20; recorte del 2026-11-10 (verificación en kind consolidada en U12) | «Governance caído 6 s → scoring responde `serving_config_unavailable`»: la prueba es de U7 y se corre en kind. U04-T07 lo quita de esta lista si su guía lo traza |
| NFR-U4-06 | Paso 20 (escenario 7, `freeze` ≤ 6 s) | Enmienda §3 U4, Paso 20; recorte del 2026-11-10 | Prueba de extremo a extremo en kind: `freeze` → primera `FailClosed(model_frozen)` en ≤ 6 s. Lo guía U04-T07; lo mide U12 |
| NFR-U4-12 | Paso 20 (escenario 2, validación de referencia) | Enmienda §3 U4, Paso 20; recorte del 2026-11-10 | `model-validation-job` en ≤ 30 min con el dataset de U5 (modo `validacion`; `source_comparison` en 60 min está además diferido con US-306) |
| NFR-U4-13 | Prueba de carga de U10 en kind | Enmienda §3 U4, Paso 20 (escenarios 1, 5, 6, 8 y 9 diferidos); U10 | Lecturas desde el BFF con p95 ≤ 300 ms y 200 usuarios: la prueba es de U10 |

Diferidos sin identificador que la prueba vea (se anotan aquí para que no se pierdan): el invariante de `source_candidate_for` de PBT-U4-01 con US-306 (P-5), `mutmut` en `model_fsm` (Paso 19, T3), el CronJob `model-archive`, `pg-role-gov-archiver`, `minio-model-archive`, F100 y los values de staging de INF-U4-05 (Paso 16, T5/T6) y las alertas y runbooks de P-U4-08 distintos de `CompensationEventPending` (Paso 17, T2).
