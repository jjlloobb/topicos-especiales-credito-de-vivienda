# Cierre de U3 con alcance acotado a la demo

Esta tarea (U03-T05) crea el archivo solo con la sección «Diferido por la demo»; el resto del cierre (lo comprobado, lo no comprobado, quién ejecutó) es de la tarea H+I.

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit decision-registry --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los pasos 13, 15 y 16 no aparecen: son de U03-T05 y se trazan en el chart, las pruebas y el `Makefile`.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| BR-U3-08 | Paso 11 (`checkpoint`) y Paso 12 (CronJob `registry-checkpoint`) | Enmienda §3 U3, Pasos 11 y 12; T5 | El checkpoint horario firmado; depende además de la decisión del `recorded_at` firmado (`CANDIDATAS.md`, U03-T04). `test_traceability.py` no ve las BR-U3 |
| BR-U3-13b | Paso 12 (CronJob `registry-verify-ondemand`, `test_ondemand.py`) | Enmienda §3 U3, Paso 12; T5 | Verificación bajo demanda asíncrona. `test_traceability.py` no ve las BR-U3 |
| INF-U3-02 | Paso 11 (`checkpoint`) y Paso 12 (políticas HCL nuevas) | Enmienda §3 U3, Pasos 11, 12 y 13 (URL de Transit); P-6; T5 | Backend de firma (Transit) y su política por identidad para el checkpoint |
| NFR-U3-12 | Paso 11 (`checkpoint`) y Paso 14 (`CheckpointMissing`) | Enmienda §3 U3, Pasos 11 y 14; T2; T5 | Los appends siguen con la bóveda caída: solo se atrasa el checkpoint, que no existe en la demo |
| NFR-U3-01 | Paso 14 (`docs/retention.md`) | Enmienda §3 U3, Paso 14; T2 | Retención de 10 años documentada, con los **[VERIFICAR]** |
| NFR-U3-02 | Paso 14 (`docs/retention.md`) | Enmienda §3 U3, Paso 14; T2 | Procedimiento de habeas data sin supresión |
| NFR-U3-03 | Paso 14 (`docs/retention.md`) | Enmienda §3 U3, Paso 14; T2 | Dependencia registrada con U8 sobre la pérdida de la re-identificación |
| NFR-U3-32 | Paso 14 (`RegistryVolumeFillForecast`, `docs/capacity.md`) | Enmienda §3 U3, Paso 14; T2 | Alerta de proyección de llenado probada con `promtool` |
| NFR-U3-34 | Paso 14 (`RegistryGrowthAboveForecast`, `docs/capacity.md`) | Enmienda §3 U3, Paso 14; T2 | Alerta de crecimiento por encima del pronóstico |
| NFR-U3-22 | Paso 17 (`tests/bench/test_verify_incremental.py`) | Enmienda §3 U3, Paso 17; T3 | Benchmark de la verificación incremental (≤ 30 s) |
| NFR-U3-23 | Paso 17 (generador de 10 años sintéticos, benchmark `nightly`) | Enmienda §3 U3, Paso 17; T3 | Benchmark de la verificación `nightly` con 36 M de entradas |
