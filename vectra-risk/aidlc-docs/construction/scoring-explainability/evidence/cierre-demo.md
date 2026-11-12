# Cierre de U7 con alcance acotado a la demo

**Estado: pendiente de revisión; verificación en kind pendiente de U12 Paso 18.** U7 queda cerrada **para kind** (`demo-kind-alcance.md` §3, U7), no para staging ni prod. U07-T01 a U07-T03 crearon los dos servicios, sus pruebas y las propiedades; U07-T04 agrega las imágenes, el chart, la Application, la trazabilidad y este cierre. P-1 = (a) (decisión del usuario del 2026-11-10): `applicant-summaries` y su plantilla entran, y BR-U7-13, BR-U7-14 y NFR-U7-03 están trazados a código y pruebas.

## Comprobado

Lo del codificador, sin clúster, desde `vectra-risk/` (la salida de cada comando está en `bitacoras/U07-T04.md`):

| Paso | Punto | Comando | Resultado |
|---|---|---|---|
| 14 | Imágenes: `hadolint`, usuario `65532:65532`, sin cliente de LLM, circuit breaking, `pytest` ni `hypothesis` (`pip list` en la imagen), plantillas dentro de la de explainability, cada `FROM` por digest | `platform/.tools/bin/hadolint scoring-explainability/*/Dockerfile`; `make -C scoring-explainability image-scoring image-explainability`; los `docker run` de `docs/imagenes.md`; el `grep` de los `FROM` | `hadolint` 0; `65532:65532` y `OK` en las dos; `OK-plantillas` (`site-packages/explainability/templates/{template_v1,applicant_v1}.txt`); 4 `FROM` con `@sha256:` de 64 hex |
| 14 | El par falla-pasa: `pybreaker` instalado sobre la imagen de scoring | La orden de `pip list` | Con `pybreaker 1.4.1` imprime la línea y rc 1; sin él, `OK` y rc 0. `hadolint` no rechaza un `FROM` sin digest (rc 0): lo atrapa el `grep` (candidata) |
| 15 | Render, esquema y reglas del chart en kind, staging y prod: 14 documentos por entorno | `integration.py --chart scoring-explainability/chart`, `kubeconform -strict` con los CRD de `ExternalSecret` y `ServiceMonitor` (`tests/fixtures/crds/`), `conftest` de `policies/conftest/` (por documento y `--combine --namespace chart_set`) | `Valid: 14, Invalid: 0` ×3; `756 passed` y `12 passed` ×3 |
| 15 | Una mutación del render por regla de `conftest` (HPA, PDB, spread, prioridad, recursos, `preStop`, gracia, sondas, variables de presupuesto, Secret, etiquetas de `flows.yaml`, imagen, endurecimiento, documentos exactos, identidad), las variables contra el código, las sondas contra `ops_server`, los hosts de KServe y las etiquetas contra `flows.yaml` | `uv run pytest scoring-explainability/tests/unit/test_chart.py` | `104 passed` |
| 15 | Admisión de U1 (Kyverno, `rego` y `--namespace hpa`) por entorno | `make -C scoring-explainability policy-chart-u1` | `pass: 20, fail: 0` ×3; `98 passed` y `3 passed` ×3. `make -C platform check-chart` rinde los tres entornos en un directorio y Kyverno entra en pánico (candidata de U03-T04 y U04-T05): se usa el objetivo con un entorno por directorio |
| 15 | Cuota (INF-U7-02) y flujos (INF-U7-05) | `render.py --check`; `test_every_workload_declares_requests_and_limits_and_fits_the_quota`; `generate.py --check` de red; `platform/network/tests`; el `grep` de F12, F15, F18 a F23 y F103; el de X01 y X02 | 0; `1 passed`; 0; `211 passed`; ninguna línea «falta»; `4`. El aporte de U7 en `quotas.yaml` (`requests [6.37, 4.91]`, `limits [27.3, 11.38]`) coincide con INF-U7-02; sin flujos nuevos |
| 17 | Application `scoring-explainability` (wave 5, sin `syncPolicy.automated`) en los tres entornos | `generate.py --check`; `test_waves.py`; `kyverno apply disallow-argocd-auto-sync.yaml` ×3; `grep sync-wave` | 0; `53/50/52 Applications en orden`; `pass: 1, fail: 0` ×3; `'5'` ×3. Pares: `wave: 4` regenerada → `test_waves.py` rc 1 (`wave 4, se esperaba 5`); `syncPolicy.automated` → Kyverno `fail: 1` |
| 17 | Trazabilidad con la lista «Diferido por la demo» | `test_traceability.py --unit scoring-explainability --all` y el `git grep` de cada BR-U7 sobre `scoring-explainability/tests` | `32 identificadores con trazabilidad`, rc 0; BR-U7-01 a 16 con prueba. Pares: un identificador del Paso 15 en la lista → rc 1 («ya tiene codigo o prueba»); NFR-U7-22 diferido fuera de la lista → rc 1 («sin trazabilidad») |
| 17 | Presupuesto de memoria de kind | `uv run pytest platform/tests/test_kind_profile.py` | `6 passed`. `requested_gib()` = 10,3438 GiB con U7 (9,2656 sin ella; suma 2 servicios × 2 réplicas × (256 + 20) MiB = 1,0781 GiB); `BUDGET_GIB` 9,3 → 10,4 (`DECISIONES-LOOP.md` §7). Umbral de detención 10,58 GiB: no se pasó |
| 19 | N/A: sin base de datos, migraciones ni interfaz | `test ! -d scoring-explainability/migrations && test ! -d scoring-explainability/frontend` | 0 |
| 20 | `make -C scoring-explainability check`: `ruff`, `mypy --strict`, import-linter (3 contratos), toda la suite con el perfil `ci` (`276 passed`), cobertura de ramas (99,28 % en total; scoring 99 %; explainability 99 %; 100 % en `policy`, `narrative`, `factuality` y `orchestrator`), chart, admisión, cuota, flujos y trazabilidad | `make -C scoring-explainability check` | rc 0, 10 min con la carga de la máquina en 6 a 14 |
| 20 | `make -C platform check` y el `make check` de todas las unidades (RL-4), en serie con `uptime` antes y después | `make -C <unidad> check` | **9 de 10 unidades en rc 0, en serie.** scoring-explainability 600 s; identity-edge 1 725 s; governance 666 s; reference-model 397 s; model-serving 324 s; bias-monitoring rc 0 (el reloj de la máquina saltó unas 25 h durante la corrida, así que sus 92 917 s no son de ejecución); case-management 73 s; contracts rc 0 en 411 s (la primera vez falló por falta de `npm ci`: `tsc` no encontrado); platform rc 0 en 931 s (la primera vez falló `test_every_component_is_in_its_wave`: la tabla de waves de U1 no tenía `scoring-explainability`, se agregó). **1 con rc 2, ajena al diff:** decision-registry, 3 pruebas de `test_aggregator` (`test_restar_relee_las_etiquetas...`, `test_una_recomendacion_mas_vieja...`, `test_una_recomendacion_invalida...`) con la carga de la máquina en 8 a 22; aisladas pasan (`3 passed`) y `git diff 10e8f6a -- decision-registry contracts` está vacío |

## Decisiones

- **P-1 (scope `governance:read-serving`, C-4) = (a): se difiere.** El realm de U2 no se toca. La precarga del diccionario activo (NFR-U7-21, P-U7-05) recibe 403 y se omite: la primera explicación lo pide, y eso solo suma latencia a esa primera explicación. No rompe ninguna de las cuatro demos. Destino: U2 (otorgar el scope a `explainability-service` en los tres realms) o el diseño de U7 (quitar la precarga). La entrada de `CANDIDATAS.md` sigue abierta.
- **P-2 (`mutmut`, NFR-U7-41, C-1) = (a): se difiere (T3).** Se quitó el identificador del comentario de `coverage` del `Makefile` (afirmaba algo que nadie comprobó) y NFR-U7-41 entra en la lista de abajo. Cerrada en `CANDIDATAS.md`.
- **La liveness es `/healthz`, no `/livez`.** INF-U7-01 y el plan dicen `/livez`, pero `vectra_common.ops_server` (U0) sirve `/metrics`, `/healthz` y `/readyz`: una sonda a `/livez` daría 404 y reiniciaría los pods en bucle. El chart usa `/healthz`; `test_chart.py::test_probes_the_paths_are_routes_that_ops_server_serves` lo ata al código de U0. El texto del diseño queda por corregir (candidata en `CANDIDATAS.md`).
- **C-2 (hosts de KServe):** `http://{inference_service}-predictor.vectra-serving.svc.cluster.local` y `-explainer`, sin puerto. El `Service` de KServe v0.21.0 expone el 80 (`constants.CommonDefaultHttpPort`, `service_reconciler.go`), como F19 y F22 de `flows.yaml` (`port: 80`, `target_port: 8080`). Cerrada en `CANDIDATAS.md`; la resolución real del nombre en kind queda abajo.
- **Presupuesto de memoria de kind:** `BUDGET_GIB` 9,3 → 10,4 (`DECISIONES-LOOP.md` §7); la cifra medida y el desglose están en `bitacoras/U07-T04.md`.

## Pendiente en U12

Lo que verifica U12 Paso 18 (enmienda §8), más el push de las imágenes:

| Punto | Qué verifica U12 |
|---|---|
| Escenario 5 (promoción azul/verde con tráfico) | 0 `version_mismatch` durante la promoción |
| Escenario 7 (congelamiento) | `FailClosed(model_frozen)` en ≤ 6 s tras el `freeze` |
| Humo del flujo base | `POST /v1/recommendations` de punta a punta en kind: `Recommendation` con `registry_entry_id`, y `POST /v1/explanations` por el BFF |
| Push de las imágenes y digests reales | `scoring-explainability/docs/imagenes.md`: `docker push` de `scoring-service` y `explainability-service` y los digests en `vectra-risk-gitops/values/kind/scoring-explainability.yaml`, más `generate.py` |
| Governance, scoring y explainability del mismo commit (C-3) | Las tres imágenes se construyen del mismo commit y sus digests suben en **un solo PR**: `ServingConfig` es estricto (`additionalProperties: false`) y un consumidor con el tipo viejo falla cerrado. U8 también lee `serving-config` y lo tiene abierto en `CANDIDATAS.md` |
| Resolución de los hosts de KServe (C-2) | Que `<isvc>-predictor.vectra-serving` y `<isvc>-explainer.vectra-serving` resuelvan desde `vectra-app` por la malla (F19, F22) |
| `ExternalSecret` de las dos llaves | Que ESO materialice `scoring-service-client` y `explainability-service-client` desde `identity/clients/<id>` de la bóveda de kind |
| Escritura en disco con la raíz de solo lectura | Que los dos servicios arranquen con `readOnlyRootFilesystem: true` y sin `emptyDir` (el chart no monta ninguno; no se comprobó con un contenedor real en esta tarea) |

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit scoring-explainability --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los identificadores de los Pasos 1 a 15 que entran (incluidos BR-U7-13, BR-U7-14, NFR-U7-03 y P-U7-03, por P-1 = (a)) están trazados en el código o en las pruebas y **no** aparecen.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| NFR-U7-01 | Paso 17 (`tests/load/recommendations.js`, `k6 inspect`) | Enmienda §3 U7, Paso 17; T3 | Prueba de carga de `POST /v1/recommendations`: p95 ≤ 400 ms y p99 ≤ 1 s a 10 solicitudes/s. El cumplimiento del presupuesto por solicitud (700 ms previos al registro) sí está en PBT-U7-07 y la propiedad de P-U7-01 |
| NFR-U7-02 | Paso 17 (`tests/load/recommendations.js`) | Enmienda §3 U7, Paso 17; T3 | Prueba de carga de `POST /v1/explanations`: p95 ≤ 250 ms |
| NFR-U7-22 | Paso 18 (escenario 6: `rollout restart` de scoring durante la carga) | Enmienda §3 U7, Paso 18 y §8; P-10 | Servicios sin estado: cualquier réplica atiende cualquier solicitud, medido con réplicas que se reinician durante la prueba de carga. En el código no hay estado de solicitud entre réplicas (la caché de `serving-config` es por pod y se revalida) |
| NFR-U7-41 | Paso 7 (`mutmut` en `policy` y `factuality`) | Enmienda §3 U7, Paso 7; T3 (candidata de U07-T02, F-02; P-2 = a) | `mutmut run` en CI. Las pruebas por ejemplos, las propiedades y la cobertura de ramas del 100 % en `policy`, `narrative` y `factuality` sí corren (NFR-U7-40) |
| P-U7-09 | Paso 18 (escenarios de resiliencia en kind) | Enmienda §3 U7, Paso 18 y §8; P-10 | Los escenarios de resiliencia de P-U7-09 en kind. Los de la demo (5, 7 y el humo del flujo base) los cubre U12 (arriba); el 1 a 4, 6, 8 y 9 se difieren |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| Alertas y runbooks (`PrometheusRule` con las siete alertas de P-U7-08, `promtool`, `test_runbooks.py --root scoring-explainability`, la prueba del nombre de la métrica contra la regla de U4) | Paso 16 | T2; enmienda §3 U7, fila 16 | Fuera de la demo. Las métricas que las alimentan sí las publican los servicios |
| Firma de las imágenes, SBOM, escaneo y la prueba sobre el SBOM (`syft`/`grype`, `sign-image.yml`) | Paso 14 | T1; enmienda §3 U7, fila 14 | Fuera de la demo; las imágenes van fijadas por digest, sin firmar. «Sin cliente de LLM ni librería de circuit breaking» se comprueba con `pip list` en la imagen |
| Workflow de CI para las imágenes | Paso 14 | T4 | Fuera de la demo |
| Script k6 `tests/load/recommendations.js` y `k6 inspect` | Paso 17 | T3; enmienda §3 U7, fila 17 | Fuera de la demo (NFR-U7-01, 02 y la medición de p95 de NFR-U7-03) |
| Medición de p95 de `POST /v1/applicant-summaries` (≤ 500 ms) | Paso 17 | T3 | NFR-U7-03 está trazado por el Paso 9 (`summaries.py`, `test_applicant_summaries.py`); solo se difiere su medición con carga |
| Escenarios 1 a 4, 6, 8 y 9 del Paso 18 | Paso 18 | Enmienda §3 U7 y §8; P-10 | Fuera de la demo (el 6 y el 9 miden carga; el 8 es la suite de conectividad de U1 en kind) |
| Escenarios 5 y 7 y el humo del flujo base | Paso 18 | Enmienda §8 | Pendiente en U12 Paso 18 (arriba) |
| Scope `governance:read-serving` de `explainability-service` (C-4, P-1 = a) | Paso 12 (precarga, NFR-U7-21, P-U7-05) | Enmienda §6 P-1 | Destino: U2 (realm) o el diseño de U7. Solo suma latencia a la primera explicación |
| Perfil de 1 réplica (`values-kind-demo.yaml`) | Paso 15 | T6; DD-3 b | Descartado: los values de kind mantienen las 2 réplicas del HPA (`require-hpa-bounds`) |
