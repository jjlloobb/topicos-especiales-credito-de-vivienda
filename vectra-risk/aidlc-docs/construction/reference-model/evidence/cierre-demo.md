# Cierre de U5 con alcance acotado a la demo (U05-T04)

**Estado: pendiente de revisión.** Esto rebaja los Pasos 8 y 9 del plan de U5 (`demo-kind-alcance.md` §3, U5): U5 queda cerrada **para kind**, no para staging ni prod. U5 es una herramienta offline sin runtime; nada de lo de abajo corrió contra el clúster.

## Comprobado

| Punto | Resultado |
|---|---|
| `make -C reference-model check` | Termina en 0: ruff, import-linter (3 contratos intactos), 141 pruebas, runbook de entrega, trazabilidad y Paso 11 |
| Cobertura de ramas (NFR-U5-33) | 93,96 % en `vectra_reference` (mínimo 90 %); 100 % en `envelope/confidence.py` (40 sentencias, 12 ramas) |
| Propiedades PBT-U5-01 a 07 | Con Hypothesis, perfil `ci` (500 ejemplos), dentro de las 141 pruebas |
| Procedimiento de entrega (Paso 9, acotado) | `reference-model/docs/release.md` sigue la plantilla, cada paso de verificación nombra un comando |
| Verificación de SHA-256 (NFR-U5-03) | `reference-model/scripts/verify_release.py`: un paquete bueno pasa; uno con un archivo alterado, uno con un archivo faltante o no listado, un manifiesto ilegible y un nombre fuera del directorio fallan. Se corrió también sobre la salida real de `make release` (bitácora) |
| Trazabilidad | `test_traceability.py` ve 11 identificadores NFR-U5; los BR-U5 y PBT-U5 se rastrean a mano en `code/README.md` (la prueba no los reconoce), con el `grep` en la bitácora |
| Paso 11 (N/A) | `reference-model/chart` y `reference-model/migrations` no existen |

## No comprobado o diferido

| Punto | Situación | Destino propuesto |
|---|---|---|
| Paso 8: workflow `reference-model.yml`, release OCI firmada, SBOM y attestation | Sin implementar; queda `[ ]` en el plan | Cierre completo de U5 (staging); T1 y T4 |
| NFR-U5-01, NFR-U5-02, NFR-U5-20 | Sin código ni prueba: son del Paso 8. `test_traceability.py` los da por cubiertos porque `release.md` los nombra | Mismo destino |
| Parte de release del Paso 9: descarga, `cosign verify`, `cosign verify-attestation` | NFR-U5-03 pide `cosign verify`; en la demo el procedimiento usa `make release` local y verifica solo los SHA-256 | Mismo destino (T1) |
| Subida real al MinIO de kind y registro en U4 | **No se ejecutó**: lo hace el operador (AUTONOMIA-01). Los comandos de `release.md` pasos 3 y 5 y las verificaciones 1 a 4 no se probaron contra un MinIO. El paso 4 (registro) espera a U4 **[PENDIENTE U4]** | Operador, antes de la demo; U4 |
| Subida del dataset de validación | Ninguna identidad de diseño escribe en `validation-datasets`; `release.md` usa la raíz de MinIO | Candidata en `CANDIDATAS.md` (U1) |
| Igualdad de bytes entre máquinas (NFR-U5-10) | Solo se probó en esta máquina | Paso 8 (CI en runner estándar) |
| Duración de la entrega ≤ 30 min (NFR-U5-20) | No se midió en un runner estándar; la entrega local con la variante proxy y el adversarial tarda varios minutos | Paso 8 |

## Candidatas abiertas de U5 más relevantes

- **Margen de 0,39 pp de la base (BR-U5-06):** la disparidad del modelo base es 4,61 pp contra el límite de 5. Es determinista con la semilla de referencia, pero cualquier cambio del generador o del modelo puede romperla. Decidir si se acota también `region_adjust`.
- ~~**Doble de U9 en `proxy.py`**~~ — resuelta en U05-T05: `proxy.py` usa `vectra_disparity` (ver «Retrabajo U05-T05»).
- **`derive` de U0:** un campo `Decimal4` (`proposed_rate_ea`) sale como `CategoryFeature` con la cadena `"0.1250"`; U5 lo trata como numérico y U6 tendrá que hacer lo mismo.
- **Variante proxy:** su AUC (0,825) queda bajo el mínimo de 0,85, que BR-U5-08 solo exige al modelo base; no calibra su propia política.
- **RT-1 «bidi»:** `ApplicationIn` de U0 rechaza U+202E y los de ancho cero, así que los casos bidi usan hebreo y árabe.
- **Nuevas de esta tarea:** la política de `validation-datasets`, el reconocimiento de BR-U5 y PBT-U5 en `test_traceability.py`, la cobertura de la raíz que solo mide U0, y las rutas y `*_uri` de U4 (todas en `CANDIDATAS.md`).

## Retrabajo U05-T05

Variante proxy más fuerte para la regla R4 y librería real de U9 en `proxy.py` (arbitraje de la ronda 2 de U09-T01, decisión del usuario del 2026-11-09). BR-U5-14 queda enmendada: la variante debe dar **>= 18 pp** por `region` y R4 debe congelarla en **>= 95 %** de las muestras `stratified` reales.

| Punto | Antes | Después |
|---|---|---|
| Medición en `proxy.py` | Doble propio (`disparity_by_attribute`, `model_aggregate`) | `counts_from_records` + `disparity_by_band` + `model_aggregate` de `vectra_disparity`, con el `outcome` de BR-U7-04/05 (`revision_requerida` no es favorable). Con la configuración vieja la librería real dio 4,61 y 11,66 pp (el doble: 4,6119 y 11,6579) |
| Agregada del modelo base (`region`, `validation`) | 4,6119 pp (doble) | 4,61 pp (la librería cuantiza a 4 decimales de fracción; ver «Ids contra `main`») |
| Agregada de la variante (`region`, `validation`) | 11,66 pp | **25,41 pp** |
| Congelamiento de la variante con R4, 2 000 muestras `stratified` de `test` (semilla 20261109) | 7,75 % | **99,45 %** |
| Congelamiento del modelo base con R4, las mismas muestras | no medido | **0,50 %** |
| Parámetros (`generator.yaml`, `proxy`) | zona 0,012 / 0,036 / 0,030; detalle 0,020 / 0,010 | x1,6: zona 0,0192 / 0,0576 / 0,048; detalle 0,032 / 0,016. `min_disparity_pp` pasa de 10 a 18 |

Las muestras salen del dataset `test` real (18 000 filas), con la composición de BR-U12-06: al azar hasta >= 30 casos por celda de U9 de los cuatro atributos y completadas a 1 500. Una celda con menos de 30 casos en todo `test` toma los que hay (la primera muestra tiene 65 celdas y la menor trae 4). Prueba: `reference-model/tests/simulation/test_r4_freeze_rate.py`; comando: `make -C reference-model simulation` (unos 6 min; no entra en `check`).

### Ids contra `main` (`bb86d71`)

Comparado con el release de `bb86d71` (`origin/main`, `python -m vectra_reference.release`) y con el de la rama, cada uno en su directorio, con SHA-256 por archivo. **El modelo base y RT-3 sí cambian.** `disparity_pp` del manifiesto base pasa de 4,6119 (cifra del doble) a 4,61 (la librería cuantiza a `Decimal4`); ese valor entra en el hash del id. Decisión del usuario del 2026-11-09 (arbitraje de la ronda 1, opción b): se aceptan los ids nuevos, porque el 4,6119 solo existía por el doble que la tarea quitó a propósito y nada está desplegado (`revisiones/U05-T05/arbitraje-ronda-1.md`).

| Paquete | `model_version_id` en `main` | En la rama |
|---|---|---|
| Modelo base (`package/`) | `mv-2026-01-01-51241dc4` | `mv-2026-01-01-8a98ab02` |
| Variante `proxy/run-1` | `mv-2026-01-01-7241d354` | `mv-2026-01-01-f12bfeaf` |
| `proxy/run-2` | `mv-2026-01-01-fa147805` | `mv-2026-01-01-bed07b8f` |
| `proxy/run-3` | `mv-2026-01-01-d2baab53` | `mv-2026-01-01-c8d04261` |
| `proxy/run-4` | `mv-2026-01-01-2a799484` | `mv-2026-01-01-eb22dae6` |
| `proxy/run-5` | `mv-2026-01-01-ea69c19d` | `mv-2026-01-01-253e325d` |
| RT-3 (a, b, c, d): `model_version_id` de cada paquete | `mv-2026-01-01-51241dc4` | `mv-2026-01-01-8a98ab02` |
| RT-3: `altered_model_version_id` (`adversarial/manifest.json`) | `mv-2026-01-01-cf3f3cce` | `mv-2026-01-01-d8ee71f9` |

Archivos de la entrega fuera de `proxy/` (40 en cada lado): **26 cambian y 14 quedan idénticos byte a byte**.

- Cambian: los cinco JSON con el id de `package/` (`manifest`, `domain_envelope`, `explainer`, `feature_dictionary`, `feature_spec`), los mismos cinco en cada paquete `adversarial/rt3/RT3-{a,b,c,d}/` (20) y `adversarial/manifest.json`: 26 en total, todos llevan el id dentro. En `proxy/` cambian 30 de 35 archivos; los 5 idénticos son los `predictor.json`.
- Idénticos (SHA-256): `package/predictor.json` y los `predictor.json` de RT-3 a-d `11abaebbe714954f…`; `package/background.csv` y los `background.csv` de RT-3 a-d `c9e3642b19b27c25…`; `datasets/train.parquet` `d637b5f331db15e1…`; `datasets/validation.parquet` `7e9f8919c75c642d…`; `datasets/test.parquet` `ceb4e7c41c3f6790…`; `reference-policy.json` `9050ed1cb8cd827f…`.

Las cifras `51241dc4` y `cf3f3cce` aparecen todavía en las bitácoras y revisiones de U05-T03, U05-T04 y U09-T01 como registro histórico; no se reescriben. El resto del repositorio ya no las cita (`u5_counts.json` trae `base_run` 8a98ab02). `model-serving/tests/integration/test_predictor.py` (U6) no existe en esta rama, así que no hay URL que ajustar aquí.

**Cambio de U9:** `bias-monitoring/tests/doubles/u5_counts.json` se regeneró con su script **después** del commit del código (`u5_commit` = `0da820f`, que incluye `a870276`); `test_disparity_examples.py` cambia por la decisión del orquestador (variante en 25,41 pp). `make -C bias-monitoring check` termina en 0. Queda como candidata solo la recalibración de `DSTAR_T`.

## Quién ejecutó

Un agente escribió el procedimiento, el script de verificación y las pruebas, y corrió `make check` y `make release` en local (con salida en un directorio temporal). No tocó el clúster, el MinIO ni la bóveda (AUTONOMIA-01). La subida y el registro los ejecuta una persona con sus credenciales.
