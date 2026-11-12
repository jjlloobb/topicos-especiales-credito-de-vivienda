# Cierre de U3 con alcance acotado a la demo (U03-T06)

**Estado: pendiente de revisión.** U3 `decision-registry` queda cerrada **para kind** (`demo-recorte-funcional.md` §2.4, §3 U3 y §8), no para staging ni prod. U03-T01 a U03-T05 escribieron el código; U03-T06 es solo documentación y verificación: no cambia nada en `decision-registry/`. La verificación en kind (Paso 18) está consolidada en U12 Paso 18 y no la hace esta tarea. El codificador no corrió nada contra el clúster (AUTONOMIA-01).

## Comprobado

Cada paso que entra (1 a 13, 15 y 16), con la tarea que lo hizo, su comando de aceptación y el resultado de esta corrida sobre `fe0c9f3` (2026-11-10). La rama se fusionó después con `origin/main` `5cf2ebb` (incluye U02-T20 y la tarea U03-T07); lo de «Comprobado» **no se volvió a correr** sobre `5cf2ebb`. El diff posterior al `fe0c9f3` es solo documentación de `vectra-risk/`, sin cambios en `decision-registry/`. El detalle y las salidas están en `bitacoras/U03-T06.md`. Los comandos se corren desde `vectra-risk/` con `HYPOTHESIS_PROFILE=ci`.

| Paso | Tarea | Comando de aceptación | Resultado ahora |
|---|---|---|---|
| 1 Esqueleto | U03-T01 | `uv sync --frozen && uv run lint-imports --config decision-registry/.importlinter` | `Contracts: 2 kept, 0 broken`; `uv sync --frozen` es el primer tramo del comando y lo cubre el `make check` en 0 (sin salida propia aparte); el `make check` completo termina en 0 |
| 2 Migraciones | U03-T01 | `uv run pytest decision-registry/tests/integration/test_migrations.py` (Testcontainers) | 98 pruebas, en verde |
| 3 `chain` | U03-T02 | `uv run pytest decision-registry/tests/property/test_chain.py` | 5 pruebas, en verde |
| 4 `verify` | U03-T02 | `uv run pytest decision-registry/tests/property/test_verify.py decision-registry/tests/unit/test_verify_modes.py` | 36 pruebas, en verde |
| 5 `projections` | U03-T02 | `uv run pytest decision-registry/tests/property/test_projections.py` | 11 pruebas, en verde |
| 6 Resumen de la lógica pura | U03-T02 | `uv run python platform/tests/test_traceability.py --unit decision-registry --section logic` | `41 identificadores con trazabilidad`, código 0 |
| 7 Append | U03-T03 | `uv run pytest decision-registry/tests/property/test_append_*.py decision-registry/tests/integration/test_append.py` | 101 pruebas, en verde |
| 8 Proyecciones, expediente y verificación bajo demanda | U03-T03 | `uv run pytest decision-registry/tests/integration/test_dossier.py test_queries.py test_integrity_api.py` | 92 pruebas, en verde |
| 9 Readiness y contratos de rutas | U03-T03 | `uv run pytest decision-registry/tests/integration/test_health.py`; `make -C contracts check` (incluye `git diff --exit-code contracts/openapi/`) | 8 pruebas en verde; contracts termina en 0 |
| 10 Resumen del servicio | U03-T03 | `uv run python platform/tests/test_traceability.py --unit decision-registry --section api` | `41 identificadores con trazabilidad`, código 0 |
| 11 CLI `vectra-registry` (sin `checkpoint`) | U03-T04 | `uv run pytest decision-registry/tests/integration/test_cli.py` (PostgreSQL, MinIO y Vault) | 38 pruebas, en verde |
| 12 CronJobs, identidades y políticas (acotado) | U03-T04 | `make -C decision-registry policy-chart`; `uv run pytest decision-registry/tests/unit/test_vault_policies.py decision-registry/tests/property/test_aggregator.py decision-registry/tests/integration/test_aggregator.py` | `conftest` en verde; 38 pruebas en verde |
| 13 Chart, buckets y flujos (acotado) | U03-T05 | `make -C decision-registry policy-chart policy-chart-u1`; `uv run python platform/network/generate.py --check && uv run pytest platform/network/tests` | `conftest` y Kyverno `pass: 26, fail: 0` en kind, staging y prod; 211 pruebas de red en verde |
| 15 Applications de GitOps (acotado) | U03-T05 | `uv run python platform/tests/test_waves.py`; el `kyverno test` de `disallow-argocd-auto-sync` corre dentro de `make -C platform check` | kind 51, staging 50 y prod 48 Applications en orden; `platform check` en 0 con 802 pruebas, que incluye ese `kyverno test` |
| 16 Cobertura y trazabilidad (acotado; sin mutación) | U03-T05 | `make -C decision-registry coverage`; `... test_traceability.py --unit decision-registry --all` | 669 pruebas; cobertura de ramas 95,93 % (mínimo 95 %); 100 % en `chain`, `verify` y `append`; trazabilidad con 41 identificadores, código 0 |
| 19 Frontend (N/A) | U03-T06 | `test ! -d decision-registry/frontend` | Código 0: U3 no tiene interfaz; el expediente lo muestra la SPA de U10 |
| 20 Cierre (acotado) | U03-T06 | `make -C decision-registry check` | Código 0, 669 pruebas, 7 min 31 s; `platform check` en 0 con 802 pruebas |

`make -C decision-registry check` corre en orden: `ruff`, `mypy --strict`, `lint-imports`, las pruebas con cobertura, la cobertura por módulo, `helm template` con `conftest`, Kyverno y `conftest` de U1 sobre el render de kind, staging y prod, y la trazabilidad. No se tocó el `Makefile`: no falta ningún objetivo de un paso que entra.

`make check` de las demás unidades (RL-4, CA-4) sobre el mismo `fe0c9f3`: `contracts`, `platform`, `governance`, `reference-model` y `model-serving` terminan en 0. `identity-edge` falló en la base `fe0c9f3` en `test_t1_supply_chain_skips_exactly_the_three_realm_configmaps` (el workflow `supply-chain.yml` ya omitía también `config-cli-realm.yaml` de kind). Eso ya no está pendiente: U02-T20 (`eaa81a8`, PR #131), incluida en `5cf2ebb`, renombró y alineó la prueba (`CANDIDATAS.md:507`). No se volvió a correr `identity-edge` sobre `5cf2ebb`.

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit decision-registry --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba: si los tiene, la prueba falla y se quita de aquí. Los pasos 13, 15 y 16 no aparecen: son de U03-T05 y se trazan en el chart, las pruebas y el `Makefile`.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| BR-U3-08 | Paso 11 (`checkpoint`) y Paso 12 (CronJob `registry-checkpoint`) | Enmienda §3 U3, Pasos 11 y 12; T5 | El checkpoint horario firmado; depende además de la decisión del `recorded_at` firmado (`CANDIDATAS.md`, U03-T04). `test_traceability.py` no ve las BR-U3 |
| BR-U3-13b | Paso 12 (CronJob `registry-verify-ondemand`, `test_ondemand.py`) | Enmienda §3 U3, Paso 12; T5 | Verificación bajo demanda asíncrona. `test_traceability.py` no ve las BR-U3 |
| INF-U3-02 | Paso 11 (`checkpoint`) y Paso 12 (políticas HCL nuevas) | Enmienda §3 U3, Pasos 11, 12 y 13 (URL de Transit); P-6; T5 | Backend de firma (Transit) y su política por identidad para el checkpoint |
| NFR-U3-41 | Paso 11 (`checkpoint`) | Enmienda §3 U3, Paso 11; T5 | Trazabilidad del checkpoint horario; sin `checkpoint` no hay qué probar, y una mención en un docstring no es trazabilidad |
| NFR-U3-12 | Paso 11 (`checkpoint`) y Paso 14 (`CheckpointMissing`) | Enmienda §3 U3, Pasos 11 y 14; T2; T5 | Los appends siguen con la bóveda caída: solo se atrasa el checkpoint, que no existe en la demo |
| NFR-U3-01 | Paso 14 (`docs/retention.md`) | Enmienda §3 U3, Paso 14; T2 | Retención de 10 años documentada, con los **[VERIFICAR]** |
| NFR-U3-02 | Paso 14 (`docs/retention.md`) | Enmienda §3 U3, Paso 14; T2 | Procedimiento de habeas data sin supresión |
| NFR-U3-03 | Paso 14 (`docs/retention.md`) | Enmienda §3 U3, Paso 14; T2 | Dependencia registrada con U8 sobre la pérdida de la re-identificación |
| NFR-U3-32 | Paso 14 (`RegistryVolumeFillForecast`, `docs/capacity.md`) | Enmienda §3 U3, Paso 14; T2 | Alerta de proyección de llenado probada con `promtool` |
| NFR-U3-34 | Paso 14 (`RegistryGrowthAboveForecast`, `docs/capacity.md`) | Enmienda §3 U3, Paso 14; T2 | Alerta de crecimiento por encima del pronóstico |
| NFR-U3-22 | Paso 17 (`tests/bench/test_verify_incremental.py`) | Enmienda §3 U3, Paso 17; T3 | Benchmark de la verificación incremental (≤ 30 s) |
| NFR-U3-23 | Paso 17 (generador de 10 años sintéticos, benchmark `nightly`) | Enmienda §3 U3, Paso 17; T3 | Benchmark de la verificación `nightly` con 36 M de entradas |

Piezas diferidas que **no** tienen un identificador propio sin código en el diseño: el `test_traceability.py` no las ve y por eso no entran en la tabla de arriba, pero se difieren con la misma cita. Cada fila nombra el paso, la cita del recorte y el destino. `test_traceability.py --unit decision-registry --all` no marca ningún identificador nuevo (ver bitácora), así que no se agregan filas a la tabla de identificadores.

| Pieza | Paso del plan | Cita del recorte | Qué falta | Destino |
|---|---|---|---|---|
| Alertas y runbooks | Paso 14 | Enmienda §3 U3, fila 14; T2 | `observability/`, `runbooks/`, `docs/retention.md` y `docs/capacity.md` (sus identificadores NFR-U3-01, 02, 03, 12, 32 y 34 están en la tabla de arriba) | Cierre completo (T2) |
| Benchmarks y carga | Paso 17 | Enmienda §3 U3, fila 17; T3 | `tests/bench/`, `tests/load/` y el generador de 10 años (NFR-U3-22 y 23 en la tabla de arriba) | Cierre completo (T3) |
| Paso 11: `verify`, `checkpoint`, `archive`, `aggregator reset` y `--until-head` | Paso 11 | Enmienda §3 U3, Paso 11, y §7 (U03-T04); T5 | Los subcomandos o banderas diferidos. Nota de §7: `verify` y `archive` ya tienen código de U03-T04 y se quedan; `checkpoint` está sin implementar (BR-U3-08, INF-U3-02, NFR-U3-12 y 41 arriba) | Cierre completo (T5) |
| Paso 12: los 5 CronJobs restantes, `test_ondemand.py`, `chart-rebuild/` y las políticas HCL nuevas | Paso 12 | Enmienda §3 U3, Paso 12; P-6; T5 | CronJobs de `checkpoint`, `verify` y `archive`, el de `registry-verify-ondemand` y los Jobs de reconstrucción con `runId` | Cierre completo (T5) |
| Paso 13: los values de buckets y de Transit | Paso 13 | Enmienda §3 U3, Paso 13; T5 | Values de los buckets WORM y de la URL de Transit | Cierre completo (T5) |
| Paso 15: `decision-registry-rebuild`, `rebuild-history.yaml`, `rebuild-runid-check.yml` y la wave 6 | Paso 15 | Enmienda §3 U3, Paso 15; T5 | La Application de reconstrucción, su historial y el workflow que valida el `runId` | Cierre completo (T5) |
| Mutación de `chain` y `verify` | Paso 16 | Enmienda §3 U3, Paso 16; T3 | `uv run mutmut run` sin sobrevivientes fuera de la allowlist | Cierre completo (T3) |
| Escenarios 1 a 7 y 9 de kind; del 8, la suspensión de 35 min, el reconstruir y los silencios | Paso 18 | Enmienda §3 U3, fila 18, y §8; T1 a T6 | Carga k6, benchmark `nightly`, fallo de zona, bóveda y S3 caídos, manipulación de superusuario, `restore-drill`, verificación bajo demanda desde la consola | Cierre completo (enmienda §3 U3, fila 18, y §8) |

## Pendiente en U12

Del Paso 18 solo el escenario que queda dentro del alcance va a U12; los escenarios diferidos de la tabla anterior van a «cierre completo». Lo que **entra** lo verifica el operador en kind dentro de **U12 Paso 18** (enmienda §8). Esta tarea no lleva guía de kind ni scripts. Debe verse:

| Qué | Resultado esperado |
|---|---|
| Wave 5 de `decision-registry` | `Synced` y `Healthy` |
| `GET /readyz` del servicio | 200 |
| Appends del flujo base | Cada uno con ack |
| `registry-aggregator` | Atraso 0 |
| `POST /v1/monitoring/daily:query` tras los 2 000 casos | Resultado mayor que 0 |

## Candidatas abiertas de U3 más relevantes

De `CANDIDATAS.md`, las que afectan a la demo:

- **Prioritaria (antes de la verificación en kind), U03-T03 ronda 2, F-01 (`CANDIDATAS.md:254`):** `test_queries.py` da por buena la aserción del peor caso de `daily:query` tomando el mínimo de 3 medidas y la consulta no tiene tope por solicitud: una consulta sin versión puede retener la única conexión del pool `projections` y dejar sin conexión a `explanation`. La forma de U9, con versión, tarda 0,14 a 0,21 s. **P-1: rige la opción (a)**, dejarla nombrada aquí y la tarea corta de código es `U03-T07`, antes de U12, ya abierta por decisión del usuario el 2026-11-10: `vectra-risk/tareas/U03-T07-tope-de-daily-query.md`.
- La firma de `checkpoint` cubre `recorded_at` de la propia entrada, que el append asigna dentro del lock (`CANDIDATAS.md:192`; U03-T03 y U03-T04; decidido el 2026-11-09: se difiere al cierre completo).
- `fail_closed` con `local_cause` desde `registry:append:scoring`: el plan pide 403 y U0 lo rechaza con 422 antes del handler (`CANDIDATAS.md:199`; U03-T03, F-03).
- Los resultados `inconsistente` de `incremental` y `nightly` no quedan en `integrity_checks`, así que no dejan el expediente en `not_verified` (`CANDIDATAS.md:200`; U03-T03).
- `pools.py` no revisa conexiones ociosas ni les pone vida máxima: tras una conmutación del primario, el primer uso da 503 (`CANDIDATAS.md:201`; U03-T03).
- Pruebas con límite de 2 s (`test_dossier.py:148`, `test_queries.py`) dan 503 o fallan por tiempo con la máquina cargada (`CANDIDATAS.md:305`; U03-T05, ronda 2, F-02).

## Quién ejecutó

El codificador de U03-T06 (agente Claude), el 2026-11-10, sobre `fe0c9f3` (base de la rama `tarea/U03-T06`; la rama se fusionó después con `5cf2ebb` sin repetir las corridas). Sin clúster. La bitácora es `bitacoras/U03-T06.md`.
