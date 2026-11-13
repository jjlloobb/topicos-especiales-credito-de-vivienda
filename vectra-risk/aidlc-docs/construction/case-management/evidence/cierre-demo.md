# Cierre de U8 con alcance acotado a la demo

**Estado: pendiente de revisión; verificación en kind pendiente de U12 Paso 18.** U8 `case-management` queda cerrada **para kind** (`demo-kind-alcance.md` §3, U8), no para staging ni prod. U08-T01 a U08-T04 crearon la base, la lógica, `case-service`, `case-worker` y el mock del core; U08-T05 agrega las dos imágenes, el chart, la regla `CoreWriteAttempt`, la Application, la documentación y este cierre. P-1 = (b) (decisión del usuario del 2026-11-12): request de memoria de 128 MiB solo en kind para `case-service` y `case-worker`.

## Comprobado

Lo del codificador, sin clúster, desde `vectra-risk/` (la salida de cada comando está en `bitacoras/U08-T05.md`):

| Paso | Punto | Comando | Resultado |
|---|---|---|---|
| 1 a 8 | Base, lógica pura y propiedades (U08-T01 y U08-T02) | `make -C case-management check` (`test`, perfil `ci`) | Dentro de la suite de abajo; ver «Cierre» |
| 9 a 13 | `case-service`: ingesta, evidencia, reconciliador, barridos y API (U08-T03) | ídem | Dentro de la suite de abajo |
| 14 a 15, 17 y 18 | `case-worker`, `core-banking-mock` y la cobertura (U08-T04) | ídem | Dentro de la suite de abajo; cobertura de ramas ≥ 95 % en `vectra_case` y 100 % en los ocho módulos |
| 19 | Imágenes: `hadolint`, usuario `65532:65532`, `Cmd`, sin circuit breaking ni herramientas de desarrollo (`pip list`), `alembic.ini` y `migrations/` en `/app`, el fixture en `DEFAULT_FIXTURES`, el mock sin `vectra_case`, cada `FROM` por digest, import-linter | Las órdenes de CA-1 | `hadolint` rc 0; `65532:65532` ×2; `OK` ×2; `OK-entradas`; `OK-migraciones`; `True`; `rc=1`; `2/2` y `2/2`; `Contracts: 5 kept, 0 broken` |
| 19/20 | Los cuatro contenedores reales arrancan con lo que pone el chart (migración, `case-service`, `case-worker`, mock y el Job `rt5-demo`), con `--read-only --user 65532:65532` | `uv run pytest case-management/tests/integration/test_image.py -v` | 13 pruebas en rc 0; apagados: `case-service` y `case-worker` salen con 0 en 0,5 s. Memoria en reposo (sin carga): `case-service` 81 a 103 MiB, `case-worker` 62 a 80 MiB, mock 72 MiB |
| 20 | Render, esquema y reglas del chart en kind, staging y prod: 22, 22 y 16 documentos | `integration.py --chart case-management/chart`, `kubeconform -strict` con los CRD de `ExternalSecret`, `ServiceMonitor` y `PrometheusRule`, `conftest` (por documento y `--combine --namespace chart_set`) | `Valid: 22/22/16, Invalid: 0`; `2024/2024/1472 passed` y `21 passed` ×3 |
| 20 | Una mutación del render por regla de `conftest` (≈ 130 casos), los values por archivo y el resto de `test_chart.py` | `uv run pytest case-management/tests/unit/test_chart.py` | Ver «Cierre» |
| 20 | Admisión de U1 (Kyverno, `rego` y `--namespace hpa`) por entorno; sin `PolicyException` ni exclusión de U8 | `make -C case-management policy-chart-u1` | Ver «Cierre» |
| 20 | Cuota (INF-U8-05), conexiones (NFR-U8-14) y flujos | `quota-flows` y las pruebas `quota`, `connections`, `flows` y `catch_all` de `test_chart.py` | Ver «Cierre». Aporte de `vectra-app` recalculado desde el render de staging + término del CronJob = línea de `quotas.yaml`; `vectra-mock` coincide al centésimo |
| 21 | `CoreWriteAttempt`: la expresión de INF-U8-03, seis casos de `promtool` con nombre, el spec versionado = render de kind = render de staging, sin regla en prod | `make -C case-management rules` | `SUCCESS` |
| 21 | La prueba del nombre: `vectra_cases_failclosed_persistent` (regla de U1) está en `vectra_case.metrics` y `vectra_core_write_attempts_total` en `core_banking_mock.metrics` | `uv run pytest case-management/tests/unit/test_rules.py` | `15 passed` |
| 22 | OpenAPI exportado y `check_openapi.py` | `uv run python case-management/tools/check_openapi.py`; `test_openapi.py` | rc 0; `6 passed` |
| 23 | Application `case-management` (wave 5, sin `syncPolicy.automated`) en los tres entornos | `generate.py --check`; `test_waves.py`; `kyverno apply disallow-argocd-auto-sync.yaml` ×3 | 0; `54/51/53 Applications en orden`; `pass: 1, fail: 0` ×3; `'5'` ×3 |
| 23 | Trazabilidad con la lista «Diferido por la demo» y un `git grep` por cada BR-U8 | `test_traceability.py --unit case-management --all` | Ver «Cierre» |
| 25 | N/A: la consola es de U10 | `test ! -d case-management/frontend` | 0 |
| C-7 | La frontera del TTL de `serving-config` | `pytest test_worker_clients.py -k ttl`; `HYPOTHESIS_PROFILE=ci pytest test_case_machine.py` | Con `<=` → `<` en `governance_client.py`, `ttl` falla y PBT-U8-01 (4 pruebas, 2 min 34 s) no |

**Memoria de kind (CA-12; `DECISIONES-LOOP.md` §7).** Se midió `requested_gib()` con el comando de CA-12 antes y después de agregar la Application:

| Medición | `requested_gib()` | `BUDGET_GIB` |
|---|---|---|
| Base de la rama (`origin/main` 5c91bbb, U7 incluida), sin U8 | 10,3438 GiB | 10,4 |
| Con la Application `case-management` (P-1 = b) | 11,0859 GiB | 11,1 (sube; el tope de parada era 13,0 de proyección) |
| Diferencia | 0,7421 GiB (esperado 0,7422 ± 0,001: 2 × (128 + 20) + 2 × (128 + 20) + 2 × (64 + 20) MiB = 760 MiB) | |

Con P-1 = (a) habría sido 1,2422 GiB y 11,6.

### Proyección

Falta sumar lo que todavía no tiene Application en esta base: U11 (0,2891 GiB: `product-metrics`, 2 × (128 + 20) MiB) y U10 (INF-U10-01: `console-bff`, 2 × (256 + 20) MiB; `console-spa`, 2 × (32 + 20) MiB; 0,6406 GiB). 11,0859 + 0,2891 + 0,6406 = **12,0156 GiB**, por debajo del tope de detención de 13,0 GiB (§7 dio por inviable un pico de ≈ 13 GiB). La máquina de la demo tiene 14 GiB. El PR de U11-T03 (#150) cambiará `BUDGET_GIB` (10,4 → 10,7) y `EXPECTED_WAVES[5]`; el orquestador resuelve el conflicto al fusionar.

### Cierre (CA-14 y CA-15)

`make -C case-management check` termina en 0: `lint` (ruff, mypy `--strict`, import-linter con 5 contratos), `670 passed` con el perfil `ci` en 17 min 31 s, cobertura de ramas 96,76 % en `vectra_case` (≥ 95) y 100 % en los ocho módulos, las dos imágenes, la prueba de los contenedores (13 pruebas), el chart en los tres entornos (`Valid: 22/22/16`), la admisión de U1 (`pass: 38/38/28`), la cuota con los flujos, `CoreWriteAttempt` (`SUCCESS` ×2), los runbooks, el OpenAPI, los enlaces y la trazabilidad (52 identificadores). **20 min 26 s** con carga 18,01/16,69/13,52 al empezar (la primera corrida, que falló en `policy-chart-u1` por la criticidad del mock, duró 16 min 38 s con carga 3,67/5,44/5,25). `make -C platform check-local` (802 pruebas, 6 min 56 s, carga 16,49/13,12/10,16) y `check-tools` (4 min 25 s, carga 12,07/12,58/11,18), corridos por separado, terminan en 0.

**RL-4: el `make check` de todas las unidades, en serie** (`uptime` y duración de cada una en `bitacoras/U08-T05.md`, CA-15): `contracts` 217 s, `decision-registry` 1 075 s, `governance` 209 s, `reference-model` 183 s, `model-serving` 122 s, `scoring-explainability` 225 s, `bias-monitoring` 1 010 s, `console` 99 s, `product-metrics` 617 s e `identity-edge` 1 711 s, todas en rc 0, más `platform` y `case-management` (arriba). Dos fallaron la primera vez por el entorno y pasaron al repetirlas: `contracts` (`tsc: not found`, el worktree no tenía `node_modules`; con `npm ci`, rc 0) y `governance` (6 errores de `XMinioServerNotInitialized` en el `setup` con la máquina a carga 8 a 19; en frío, rc 0). Candidatas en `CANDIDATAS.md`.

**Lo que no es como dice la tarea** (detalle en la bitácora): el mock lleva `vectra.io/criticality: medium` y no `low` (la política de U1 solo admite `critical`, `high` y `medium`); `build_app().openapi()` no trae rutas, así que `check_openapi.py` compara `spec_for` de U0 sobre las rutas servidas; el Job `rt5-demo` necesita un interruptor (`probes.enabled`, solo en `values/kind`) para distinguir kind de staging.

## Decisiones

| Pregunta | Opción que rigió | Quién |
|---|---|---|
| P-1. Request de memoria de `case-service` y `case-worker` en kind | (b) 128 MiB solo en kind (`chart/values-kind.yaml`); réplicas, HPA, PDB y limits no cambian; staging y prod siguen en INF-U8-04 (256 MiB). Se aparta de «kind igual a staging» por decisión del usuario | Usuario, 2026-11-12 |
| P-2. Dónde van los values de kind para que `render_env` los vea | (a) Defaults de producción en `chart/values.yaml`; `values-kind.yaml` por `kind_values` (core, mock y el request de P-1); `values/kind/case-management.yaml` lleva el resto (`allowTestScenarios`, `probes.enabled`) | Recomendación de la tarea |
| P-3. El mock: ¿una Application o dos? | (a) Una sola (`case-management`); el chart pone `vectra-mock` en cada recurso del mock y `coreMock.enabled` lo limita a kind y staging | Recomendación de la tarea |
| P-4. Plazos de gracia | (a) `case-worker` 40 s (cubre el peor caso real de ≈ 34 s; `config.WORKER_TERMINATION_GRACE` queda como mínimo) y `case-service` 20 s (la letra del plan) | Recomendación de la tarea |
| P-5. La prueba sobre el SBOM | (a) Se difiere con T1; la misma comprobación se hace con `pip list` en las imágenes y el import-linter | Recomendación de la tarea |
| P-6. `sslmode` de los DSN | (a) `verify-full` con la CA interna (`sslrootcert`; el chart monta `vectra-internal-ca`) | Recomendación de la tarea |
| P-7. El «OpenAPI versionado» | (a) Exportado en `docs/openapi/` y comparado con la app y con `contracts/openapi/` (la app no trae rutas en `openapi()`: se compara el `spec_for` de U0 sobre `app.routes`) | Recomendación de la tarea |

**No comprobado de NFR-U8-14:** la medición de las conexiones con carga (T3). Solo se comprueba el cálculo: 12 réplicas × `CASE_DB_POOL_MAX` × 1,2 + 2 = 74 ≤ 100 (`maxConnections` de `case-db`).

## Pendiente en U12

Lo que verifica U12 Paso 18 (enmienda §8):

- **Escenario 7 del Paso 24:** el Job `rt5-demo-<runId>` con el `runId` de `prepare` dispara `CoreWriteAttempt` con `vectra_core_write_attempts_total` en 0 (enmienda §6 P-13: «La de U12 es la que cuenta»). El oráculo lee el log del Job (403 con `l5d-proxy-error`), la alerta en Prometheus y el contador del mock.
- **Métricas del proxy de Linkerd para D3 (U01-T09, F-02 de U08-T05):** en kind, el target `linkerd-proxy` de `vectra-mock` en `up == 1` (no 403: el `Server` del 4191 sin rutas debe dejar pasar el raspado mTLS de `prometheus` y las sondas `/live` y `/ready`); la serie `inbound_http_authz_deny_total` con `namespace="vectra-mock"` y `route_name="core-mock-catch-all"` tras el 403 real del Job de RT-5 (las etiquetas están **por confirmar**: la documentación de Linkerd 2026.10.2 no las lista para esa métrica); y los pods de `vectra-mock` `Ready` con ese `Server` aplicado.
- **Escenario 1:** la suite de conectividad (`case-service` → scoring denegado; `case-worker` → scoring permitido; `case-worker` → registro y core denegados; el mock alcanza solo el JWKS).
- **Escenario 5:** PBT-U8-07 abreviado contra el registro real.
- **Push de las dos imágenes y digests reales**, en el mismo PR que los de `governance` y `scoring-explainability`, del mismo commit (`case-management/docs/imagenes.md`; C-4). U12 (`prepare`) agrega ahí el `probes.runId`.
- Que ESO materialice las dos llaves (`case-service-client` y `case-worker-client`) y que los cuatro `pg-role-case-*` existan en `vectra-app`.
- Que el hook de migración corra antes de que los `Deployment` queden `Ready`, y que `sslmode=verify-full` (P-6) conecte de verdad con `case-db` (que el nombre de `postgres-server-tls` cubra `case-db-rw.vectra-data.svc.cluster.local`).
- Que Prometheus cargue la `PrometheusRule` y raspe los tres `ServiceMonitor`: `vectra_cases_failclosed_persistent` visible para `FailClosedPersistente` (D1).
- Memoria real de `case-service` y `case-worker` con 2 000 decisiones, frente al request de kind de P-1 (en reposo, en esta tarea: 81 a 103 MiB y 62 a 80 MiB).
- El apagado real del worker en un `rollout restart` (P-4).

## Diferido por la demo

Lista que acepta `platform/tests/test_traceability.py --unit case-management --all` (P-4, `demo-recorte-funcional.md` §2.4 y §6): exactamente estas seis filas (enmienda §3 U8, fila «23»: «trazabilidad con lista (BR-U8-20)»). Cada fila lleva el identificador, el paso del plan que lo implementaría y la cita del recorte. Un identificador de esta lista **no** puede tener código ni prueba en `case-management/`.

| Identificador | Paso del plan | Cita del recorte | Qué falta |
|---|---|---|---|
| INF-U8-08 | Paso 24 (escenario 6, ampliar el volumen) y la parte de `PostgresVolumeUsageHigh` del Paso 21 | Enmienda §3 U8, filas «24 Kind» y «21 Alertas»; T2 | La medición del tamaño por caso y la alerta del volumen de `case-db` |
| NFR-U8-46 | Paso 16 (CLI) y las tres métricas de retención del Paso 11 | Enmienda §3 U8, filas «16» y «11»; T5 | La CLI `case-retention` y sus métricas de retención |
| NFR-U8-47 | Paso 22 (`retention.md` y el `conftest` de la firma) | Enmienda §3 U8, fila «22 Documentación» | El documento de retención con el espacio para la firma de cumplimiento y la regla que la exige en `values/prod` |
| NFR-U8-51 | Paso 8 (`mutmut`) | Enmienda §3 U8, fila «8 Resumen», y §2 regla 3; T3 | `mutmut` en CI |
| P-U8-07 | Paso 16 y el CronJob del Paso 20 | Enmienda §3 U8, filas «16» y «20 Chart»; §6 P-12 | La CLI de retención y la plantilla del CronJob |
| BR-U8-20 | Pasos 16 y 22 | Enmienda §3 U8, fila «23»; T5 | La retención vencida y la anonimización (`guard_vencido` en `0003_guards.py` y `case_fsm.py` ya la citan; la herramienta no cuenta las BR entre los identificadores de la unidad) |

Lo diferido sin identificador propio (no lo mira la herramienta; cada uno con su destino):

| Qué | Paso del plan | Cita del recorte | Destino |
|---|---|---|---|
| El Paso 16 (CLI `case-retention`, PBT-U8-08 y la corrida de P-U8-07) y, con él, la plantilla del CronJob, `retention.schedule` y `retention.timeZone` | Paso 16; Paso 20 | T5; enmienda §3 U8, filas «16» y «20 Chart»; §6 P-12 | Fuera de la demo |
| `mutmut` (Paso 8) y el umbral de cobertura de `retention` (Paso 18) | Pasos 8 y 18 | T3 | Fuera de la demo |
| Firma, SBOM, escaneo y la prueba sobre el SBOM de las imágenes | Paso 19 | T1; enmienda §3 U8, fila 19 | Fuera de la demo; las imágenes van fijadas por digest, sin firmar. «Sin circuit breaking» se comprueba con `pip list` en la imagen (P-5) |
| Las ocho alertas del Paso 21 que no entran, `CaseEvidenceDiscarded` (Paso 10), sus runbooks y las pruebas del nombre para `AuthDeniedBurst` y `PostgresVolumeUsageHigh` | Pasos 10 y 21 | T2; enmienda §3 U8, fila 21 | Fuera de la demo |
| `retention.md` y el `conftest` de la firma | Paso 22 | Enmienda §3 U8, fila 22 | Fuera de la demo |
| El script k6 y `k6 inspect` | Paso 23 | T3; enmienda §3 U8, fila 23 | Fuera de la demo |
| Los escenarios 2, 3, 4 y 6 y la carga del Paso 24 | Paso 24 | Enmienda §3 U8, fila 24, y §8 | Fuera de la demo; el 1, el 5 y el 7 pasan a U12 (arriba) |
| `CaseJobsOverdue` y `CaseApiUnavailable` (NFR-U8-12 y NFR-U8-20 están trazados por el chart) | Paso 21 | T2 | Fuera de la demo |
| Perfil de 1 réplica (`values-kind-demo.yaml`) | Paso 20 | T6; DD-3 b | Descartado: los values de kind mantienen las 2 réplicas del HPA (`require-hpa-bounds`) |
