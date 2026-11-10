# Cierre de U9 con alcance acotado a la demo

**Estado: pendiente de revisión; verificación en kind pendiente de U12 Paso 18.** U9 queda cerrada **para kind** (`demo-kind-alcance.md` §3, U9), no para staging ni prod. U09-T01 a U09-T03 crearon la librería, el CronJob, el servicio y sus pruebas; U09-T04 agrega la imagen, el chart, la Application, la trazabilidad y este cierre. El codificador no corrió nada contra el clúster (AUTONOMIA-01): el contenedor real corre con Docker local contra dobles.

## Comprobado

Lo del codificador, sin clúster, desde `vectra-risk/` (la salida de cada comando está en `bitacoras/U09-T04.md`):

| Paso | Punto | Comando | Resultado |
|---|---|---|---|
| 11 | Imagen: `hadolint`, usuario `65532:65532`, sin numpy, scipy, pandas, Fairlearn, scikit-learn, pytest ni hypothesis (`pip list` en la imagen), los dos puntos de entrada importan, cada `FROM` por digest | `platform/.tools/bin/hadolint bias-monitoring/Dockerfile`; `make -C bias-monitoring image`; los `docker run` de `docs/imagenes.md` | `hadolint` 0; `65532:65532`; `OK`; `OK-entradas`; 2 de 2 `FROM` con `@sha256` |
| 12 | Render, esquema y reglas del chart en kind, staging y prod: 10 documentos por entorno | `integration.py --chart bias-monitoring/chart`, `kubeconform -strict` con los CRD de `ExternalSecret` y `ServiceMonitor` (`tests/fixtures/crds/`), `conftest` de `policies/conftest/` (por documento y `--combine --namespace chart_set`) | `Valid: 10, Invalid: 0` ×3; `660 passed` y `14 passed` ×3 |
| 12 | Una mutación del render por regla de `conftest`, los rangos de `values-monitoring-policy.yaml` y la identidad de los dos procesos | `uv run pytest bias-monitoring/tests/unit/test_chart.py` | `139 passed` |
| 11 y 12 | El contenedor real arranca con las variables que pone el chart (servicio: `/readyz` 200 y `GET /v1/freezes` con token; CronJob: corrida completa que congela y empuja sus métricas; sin `VECTRA_REGISTRY_URL` no arranca y el log nombra la variable sin su valor), con raíz de solo lectura | `uv run pytest bias-monitoring/tests/integration/test_image.py` | `4 passed` |
| 12 | Admisión de U1 (Kyverno `fail: 0`, `rego` y `--namespace hpa`) por entorno; `require-hpa-bounds` admite la exención | `make -C bias-monitoring policy-chart-u1` | `pass: 18, fail: 0` ×3; `70 passed` y `3 passed` ×3. `make -C platform check-chart` entra en pánico (Kyverno, tres entornos en un directorio; candidata de U03-T04 y U04-T05), por eso el objetivo propio |
| 12 | Cuota, flujos y `CODEOWNERS` | `render.py --check`; `test_every_workload_declares_requests_and_limits_and_fits_the_quota`; `generate.py --check` de red; `platform/network/tests`; `test_chart.py -k "codeowners or flows"` | 0; `1 passed`; 0; `211 passed`; `7 passed`. F14, F25, F26, F27 (solo `bias-monitoring-job`), F50, F60 y F106 están en `flows.yaml`, sin flujos nuevos; `forbidden.yaml` sigue negando servicio → Pushgateway |
| 14 | Application `bias-monitoring` (wave 5, sin `syncPolicy.automated`, con `values-monitoring-policy.yaml` en `valueFiles`) en los tres entornos | `generate.py --check`; `test_waves.py`; `kyverno apply disallow-argocd-auto-sync.yaml` ×3 | 0; `52/49/51 Applications en orden`; `pass: 1, fail: 0` ×3 |
| 14 | Trazabilidad con la lista «Diferido por la demo» | `test_traceability.py --unit bias-monitoring --all` y el `git grep` de cada BR-U9 sobre `bias-monitoring/tests` | `35 identificadores con trazabilidad`, rc 0; BR-U9-01 a 20 con prueba (BR-U9-21 y 22 son del Paso 13, en la lista) |
| 14 | Presupuesto de memoria de kind | `uv run pytest platform/tests/test_kind_profile.py` | `6 passed`. `requested_gib()` = 9,2656 GiB con U9 (8,9766 sin ella; suma 2 réplicas × (128 + 20) MiB = 0,2891 GiB); `BUDGET_GIB` 9,0 → 9,3 (`DECISIONES-LOOP.md` §7). Umbral de detención 9,49 GiB: no se pasó |
| 17 | N/A: sin base de datos, migraciones ni interfaz | `test ! -d bias-monitoring/migrations && test ! -d bias-monitoring/frontend` | 0 |
| 18 | `make -C bias-monitoring check`: `ruff`, import-linter, pruebas con el perfil `ci`, propiedades (PBT-U9-05 con 500 × 80), cobertura de ramas de la librería (100 %) y de `vectra_bias` (99,92 %; 100 % en `freeze_rule`, `context` y `window`), simulación (7), chart, imagen, admisión y trazabilidad | `make -C bias-monitoring check` | rc 0 en 22 min 55 s con la máquina libre y en 4 304 s en la corrida del revisor con la máquina cargada (ver «Decisiones», P-2) |
| 18 | `make -C platform check` y el `make check` de todas las unidades (RL-4), corrida en serie del revisor sobre `6414508` | `make -C <unidad> check` | **6 de 9 en rc 0:** bias-monitoring 4 304 s, platform 795 s, governance 793 s, reference-model 855 s, model-serving 452 s, scoring-explainability 631 s. **3 con rc 2, ajenos al diff** (U9 no toca esas unidades): identity-edge (3 217 s), una sola prueba falla, `test_t1_supply_chain_skips_exactly_the_three_realm_configmaps` (2 771 pasan), fallo previo de `8d2cabd`, destino **U02-T20**; decision-registry (1 327 s), una sola prueba falla, `test_f04_300_mil…` (668 pasan), el límite de 2 s bajo carga, destino **U03-T07**; contracts (324 s), solo `bench_gate`: `test_bench_pipeline p95 = 5.266 ms (limite 5.0)` con carga de 10 a 14, destino la candidata del bench bajo carga (U04-T09) |

## Decisiones

- **P-1 (`CODEOWNERS`) = (a).** La regla `**/values-monitoring-policy.yaml @jjlloobb @joseluisjedi` de `.github/CODEOWNERS` ya cubre `vectra-risk/bias-monitoring/chart/values-monitoring-policy.yaml`; no se tocó el archivo de gobierno. `test_chart.py::test_codeowners_a_rule_covers_values_monitoring_policy` lo comprueba y otra prueba muestra que sin la regla la ruta queda descubierta. El usuario no respondió: rige la recomendación de la tarea.
- **P-2 (PBT-U9-05) = (a), decisión del usuario del 2026-11-10.** `test_run_machine.py` vuelve a **500 ejemplos × 80 pasos**, la letra de NFR-U9-52; se retira el ajuste a 120 × 80 de U09-T02. Cifras medidas en esta máquina, perfil `ci`: el archivo tarda **44 s con 120 × 80 y 1 min 52 s con 500 × 80** (≈ 16 ms por corrida del CronJob, no 0,15 s). `make property` pasa de ≈ 2 min a 3 min 20 s. **Costo que conviene saber:** `coverage-bias` repite las pruebas con la medición de ramas y el archivo tarda mucho más con la traza activa: el objetivo entero dura **13 min 20 s**, y `make -C bias-monitoring check` en total **22 min 55 s**. La sección «PBT-U9-05 frente a NFR-U9-52» de `code/services.md` se quitó, como pedía P-2 (a): las cifras viven aquí y en la bitácora. Si el costo del `check` resulta excesivo, lo único que cambia es `max_examples` en `test_run_machine.py`, y eso es una decisión del usuario.
- **El chart lee `values-monitoring-policy.yaml` con `.Files`.** `platform/tests/integration.py` `render_env` (lo usan `test_kind_profile.py` y `test_integration.py`) no pasa los `values` de un componente de tipo `path`: sin esto el chart no rendía allí (`required`). Las plantillas toman los cinco parámetros del archivo del chart o, encima, de los values que Argo CD le pasa con ese mismo archivo (`valueFiles` de la Application), siempre con `required`. Ninguno está en `values.yaml` ni en una plantilla. Candidata de U1 en `CANDIDATAS.md`.

## Pendiente en U12

Escenarios del Paso 16 que verifica U12 Paso 18 (enmienda §8), más el push de la imagen:

| Punto | Qué verifica U12 |
|---|---|
| Escenario 1 (conectividad) | F14, F25, F26, F27, F50, F60 y F106 en kind; X04 con `bias-monitoring-service` → governance negado |
| Escenario 3 (RT-2 con una medición, DD-1) | La variante proxy congela con una corrida real del CronJob |
| Escenario 5 (duración y pico de memoria de una corrida, NFR-U9-04 y DD-3) | Duración de una corrida y pico de memoria bajo los 256 MiB del límite |
| Push de la imagen y digest real | `bias-monitoring/docs/imagenes.md`: `docker push`, digest en `vectra-risk-gitops/values/kind/bias-monitoring.yaml` y `generate.py` |
| `ExternalSecret` de las dos llaves | Que ESO materialice `bias-monitoring-service-client` y `bias-monitoring-job-client` desde `identity/clients/<id>` de la bóveda de kind |

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit bias-monitoring --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los identificadores de los Pasos 1 a 12 que entran **no** aparecen: se trazan en el código, el chart, las políticas y las pruebas. La prueba marcó al empezar siete identificadores sin trazabilidad: tres son de los Pasos 1 a 12 y se trazaron (NFR-U9-11 y NFR-U9-13 en las reglas de `policies/conftest/`, NFR-U9-34 en `test_chart.py`); cuatro son de partes diferidas y están abajo. BR-U9-21 y BR-U9-22 los ve `git grep` y no la herramienta (están en párrafos en negrita), por eso tienen fila.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| NFR-U9-40 | Paso 13 (`PrometheusRule` con las cuatro alertas y `promtool test rules`) | Enmienda §3 U9, fila «13 · 15»; T2 | Las alertas `MonitoreoSesgoDetenido`, `BiasFreezeFailed`, `DisparidadDecisionHumana` y `BiasInvalidEntries` con su `runbook_url`. Las métricas que las alimentan sí las publica el CronJob (BR-U9-20) |
| P-U9-06 | Paso 13 (`PrometheusRule`, runbooks, `test_runbooks.py --root bias-monitoring`) | Enmienda §3 U9, fila «13 · 15»; T2 | El patrón de alertas de P-U9-06 y sus runbooks |
| INF-U9-05 | Paso 13 (reglas, runbooks y `observability/dashboards/bias.json` como código) | Enmienda §3 U9, fila «13 · 15»; T2 | Reglas, runbooks y dashboard como código; la vista de sesgo la da la consola (U10 Paso 14) |
| BR-U9-21 | Paso 13 (`MonitoreoSesgoDetenido`) | Enmienda §3 U9, fila «13 · 15»; T2 | La alerta con `absent()` y W y 2W tomados de `stale_after`. La métrica `vectra_bias_last_success_timestamp` sí existe |
| BR-U9-22 | Paso 13 (alertas de la unidad) | Enmienda §3 U9, fila «13 · 15»; T2 | `BiasFreezeFailed`, `DisparidadDecisionHumana` y `BiasInvalidEntries`; el `authz.denied` de cada 403 sí está (NFR-U9-32) |
| NFR-U9-51 | Pasos 5 y 10 (`mutmut` en `stats`, `disparity` y `freeze_rule`, con 0 sobrevivientes sin justificar) | Enmienda §3 U9, Pasos 5 y 10; T3 (candidata de U09-T01, ronda 4) | `mutmut run` en CI. Las pruebas por ejemplos, las propiedades y la cobertura de ramas del 100 % sí corren (NFR-U9-50) |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| Alertas, runbooks y dashboard (`PrometheusRule`, `promtool`, `test_runbooks.py`, `bias.json`) | Paso 13 | T2; enmienda §3 U9, fila «13 · 15» | Fuera de la demo; la vista de sesgo la da la consola (U10 Paso 14) |
| Workflow de CI (`.github/workflows/bias-monitoring.yml`, regla de rutas, nocturno) | Paso 15 | T4; enmienda §3 U9, fila «13 · 15» | Fuera de la demo; la simulación y `mutmut` quedan sin su corrida nocturna |
| Script de carga `tests/load/dashboard.js` y `k6 inspect` | Paso 14 | T3; enmienda §3 U9, fila 14 | Fuera de la demo (NFR-U9-02 y la prueba de carga de NFR-U9-11) |
| `mutmut` en `stats`, `disparity` y `freeze_rule` | Pasos 5 y 10 | T3 | Fuera de la demo (NFR-U9-51) |
| Firma de la imagen, SBOM y escaneo | Paso 11 | T1; enmienda §3 U9, fila 11 | Fuera de la demo; la imagen va fijada por digest, sin firmar |
| Job `x04-probe-<runId>`, su `conftest`, `probes.runId` y el caso `x04-probe` → Keycloak | Paso 12 | T5; T6; DD-3 | Fuera de la demo; X04 lo cubre la negación de `forbidden.yaml` y la prueba de conectividad de U1 |
| Escenarios 2 y 4 y E1 a E5 y E7 del Paso 16 | Paso 16 | Enmienda §3 U9, fila 16, y §8 | Fuera de la demo; E1 a E5 y E7 los cubren las pruebas de integración con dobles (`test_run.py`, `test_image.py`) |
| Escenarios 1, 3 y 5 del Paso 16 | Paso 16 | Enmienda §8 | Pendiente en U12 Paso 18 (arriba) |
| Perfil de 1 réplica (`values-kind-demo.yaml`) | Paso 12 | T6; DD-3 b | Descartado: los values de kind mantienen las 2 réplicas fijas |
