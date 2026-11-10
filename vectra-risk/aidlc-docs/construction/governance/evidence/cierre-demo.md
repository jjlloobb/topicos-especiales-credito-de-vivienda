# Cierre de U4 con alcance acotado a la demo (U04-T07)

**Estado: pendiente de revisión.** U4 `governance` queda cerrada **para kind**, no para staging ni prod (`demo-recorte-funcional.md` §2.4, §3 U4). Lo que corre contra el clúster lo ejecuta el operador (AUTONOMIA-01): el codificador escribió la guía, los scripts y las plantillas de evidencia y no tocó ningún clúster. Las filas de kind de abajo dicen «pendiente del operador» hasta que se adjunte la evidencia.

## Comprobado

Lo que se verificó sin clúster, con los comandos de la bitácora (`bitacoras/U04-T07.md`).

| Punto | Resultado | Evidencia |
|---|---|---|
| `make -C governance check` | Termina en 0: ruff, mypy estricto, import-linter, `promtool`, `shellcheck`, 585 pruebas con cobertura de ramas de 97,17 % (mínimo 95 %; 100 % en `model_fsm`, `policy` y `evidence`), chart con `conftest`, Kyverno por entorno (`pass: 19, fail: 0` en kind, staging y prod) y el pod del runbook (`pass: 8, fail: 0`) | Bitácora, «Cierre» |
| Pruebas del runbook de la política (`test_kind_runbook.py`) | Detecta cada variante mala de F-03 (cliente en local con hosts internos, `bash <<EOF`, nombres cortos, cercos `sh`, «…», `REEMPLAZA_POR_…`, Secrets, token exportado, verificación tras la limpieza, archivo temporal sin borrar) y el runbook nuevo pasa | Bitácora, rojo y verde |
| CA-7: `kyverno apply` de las políticas de kind sobre lo que crea el runbook | `pass: 8, fail: 0` sobre el pod efímero y la ServiceAccount; el Secret del runbook anterior daba `fail: 1` | `make -C governance policy-runbook`; bitácora |
| Scripts `governance/docs/kind/*.sh` | `shellcheck` en 0; `test_kind_scripts.py` los corre con `--dry-run` y contra dobles de `kubectl`, `docker`, `uv` y `make`: el token nunca aparece en un argumento, ninguno aplica, instala ni sincroniza | [`test_kind_scripts.py`](../../../governance/tests/unit/test_kind_scripts.py) |
| Guía del operador (Paso 20) | `docs/paso-20-kind.md` con el arranque y los escenarios 2, 3, 4 y 7: cada sección tiene el comando, la salida esperada y su archivo de evidencia | [`paso-20-kind.md`](../../../governance/docs/paso-20-kind.md) |
| Frontend (Paso 21) | N/A: `test ! -d governance/frontend` | Bitácora |
| Trazabilidad | `test_traceability.py --unit governance --all` en 0, con NFR-U4-02, 06 y 12 trazados por la guía | Bitácora |

## Pendiente del operador y de otras unidades

Evidencia de kind: una plantilla por punto en [`kind/`](kind/), todas en «pendiente del operador».

| Punto | Estado | Evidencia | Depende de |
|---|---|---|---|
| Imágenes y PR de digests | Pendiente del operador | [`01-imagenes.md`](kind/01-imagenes.md) | |
| Sync de la wave 5 | Pendiente del operador | [`02-sync.md`](kind/02-sync.md) | U1, U2 y U3 sanos |
| Arranque: política activa (P-7) | Pendiente del operador | [`03-arranque-politica.md`](kind/03-arranque-politica.md) | Sync |
| Arranque: registro del modelo; convención de rutas de `release.md` (candidata de U05-T04) | Pendiente del operador | [`04-arranque-modelo.md`](kind/04-arranque-modelo.md) | Paquete de U5 subido |
| Escenario 2: validación, informe en menos de 30 min (NFR-U4-12) | Pendiente del operador | [`05-escenario-2-validacion.md`](kind/05-escenario-2-validacion.md) | Política activa |
| Escenario 3: promoción de punta a punta (US-204) | Pendiente del operador | [`06-escenario-3-promocion.md`](kind/06-escenario-3-promocion.md) | U6 C+D fusionado |
| Escenario 4: rollback (US-208) | Pendiente del operador | [`07-escenario-4-rollback.md`](kind/07-escenario-4-rollback.md) | Escenario 3 |
| Escenario 7: `freeze` hasta `serving-config` en 6 s o menos (NFR-U4-06) | Pendiente del operador; el extremo a extremo, **pendiente de U7 Paso 18** y U9 | [`08-escenario-7-freeze.md`](kind/08-escenario-7-freeze.md) | U7, U9; lo mide U12 |
| NFR-U4-02: governance caído 6 s, scoring responde `serving_config_unavailable` | Pendiente de U7 (la prueba es de U7) | | U7 |
| Memoria de `vectra-app` antes y después (DD-3 b) | Pendiente del operador | [`09-memoria.md`](kind/09-memoria.md) | |
| Paso 20 del plan | `[ ]` con la nota «guía lista, pendiente del operador»; pasa a `[x]` cuando se adjunte la evidencia | | Operador |

**Diferidos sin escenario en esta guía** (T3 y siguientes, en la lista de abajo y en `demo-recorte-funcional.md` §3 U4): escenario 1 (k6, T3), 5 (`governance-db` pausada), 6 (registro caído), 8 (`branch-protection-check`, Paso 14) y 9 (US-306).

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit governance --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los Pasos 16, 17 (`slo.md`, `CompensationEventPending`), 18 y 19 (cobertura y trazabilidad) entraron en U04-T06 y se trazan en el chart, las pruebas y el `Makefile`; el Paso 20 (guía) y el 22 (este cierre) entran en U04-T07.

La prueba marcaba 14 identificadores sin trazabilidad al empezar U04-T06. Cuatro quedaron cubiertos por lo que entró (INF-U4-04: F44, F47, F101, F102 y la ruta `freeze` en `test_chart.py`; NFR-U4-01: `docs/slo.md`; NFR-U4-03: el chart y `test_chart.py`; NFR-U4-41: la cobertura de ramas del `Makefile`, sin `mutmut`). **U04-T07 quitó de esta lista NFR-U4-02, NFR-U4-06 y NFR-U4-12**: la guía del operador (`docs/paso-20-kind.md`, escenarios 2 y 7) los traza y la prueba exige que un identificador con trazabilidad no esté aquí; su evidencia de kind sigue pendiente del operador (ver «Pendiente»). Siete identificadores quedan en esta lista.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| INF-U4-02 | Paso 15 (`model-archive`) | Enmienda §3 U4, Paso 15; T5 | CronJob diario de archivo, bucket `vectra-model-archive` con WORM `COMPLIANCE` y verificación del SHA-256 |
| NFR-U4-31 | Paso 15 (`model-archive`) y bucket `model-store` de U1 | Enmienda §3 U4, Paso 15; T5 | Retención de 10 años de los artefactos de toda versión que estuvo `activo`, con **[VERIFICAR]** y una prueba en MinIO |
| NFR-U4-22 | Paso 14 (`branch-protection-check`) | Enmienda §3 U4, Paso 14; T4 | Verificación de la protección de `main` del monorepo (≥ 1 aprobación de una persona distinta del autor) |
| NFR-U4-07 | Paso 17 (alerta `ServingConfigUnavailable`, SEV1) | Enmienda §3 U4, Paso 17; T2 | Las demás alertas de P-U4-08 y sus runbooks; solo entra `CompensationEventPending` (P-3) |
| NFR-U4-10 | Paso 19 (script k6 de `serving-config`) | Enmienda §3 U4, Paso 19; T3 | p95 ≤ 20 ms con 12 clientes cada 5 s y una lectura de `feature_spec` por cliente de U8 al cambiar de versión |
| NFR-U4-11 | Paso 19 (script k6 de transiciones con firma) | Enmienda §3 U4, Paso 19; T3 | p95 ≤ 500 ms incluido el append al registro |
| NFR-U4-13 | Prueba de carga de U10 en kind | Pendiente de U04-T07 (guía de kind de U4) y de la prueba de carga de U10; no diferido por el recorte | Lecturas desde el BFF con p95 ≤ 300 ms y 200 usuarios: la prueba es de U10 |

Diferidos sin identificador que la prueba vea (se anotan aquí para que no se pierdan): el invariante de `source_candidate_for` de PBT-U4-01 con US-306 (P-5), `mutmut` en `model_fsm` (Paso 19, T3), el CronJob `model-archive`, `pg-role-gov-archiver`, `minio-model-archive`, F100 y los values de staging de INF-U4-05 (Paso 16, T5/T6) y las alertas y runbooks de P-U4-08 distintos de `CompensationEventPending` (Paso 17, T2).
