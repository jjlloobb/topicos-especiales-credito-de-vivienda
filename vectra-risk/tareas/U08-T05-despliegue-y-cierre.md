# U08-T05 — Imágenes, chart, `CoreWriteAttempt`, Application, documentación y cierre acotado de `case-management`

**Unidad:** U8 `case-management`
**Historias que implementa:** US-609 (HPA en su chart, Paso 20), US-603 (la escritura al core es imposible: la alerta `CoreWriteAttempt` y su runbook, Paso 21; el Job `rt5-demo-<runId>`, Paso 20) y US-112 (Paso 21: solo la prueba del nombre de `vectra_cases_failclosed_persistent`; sus alertas están diferidas), según la trazabilidad del plan (§3). Los Pasos 19, 22, 23, 25 y 26 no tienen historia propia: empaquetan, despliegan por GitOps y cierran lo que implementan los Pasos 1 a 18.
**Depende de:**
- **U08-T04 fusionada en `main`** (PR #148; hash de fusión: **por completar al fusionar**): `case-worker`, `core-banking-mock` y `aidlc-docs/construction/case-management/code/services.md`, que deja escritos el entorno y el arranque de cada proceso;
- en `main`, como contratos (comprobado al redactar, sobre `210da56`):
  - U0: `contracts/openapi/case-service.yaml` y `contracts/openapi/core-banking-mock.yaml`; `vectra_common.ops_server` (`/metrics`, `/healthz` y `/readyz` en 8081; la API en 8080);
  - U1, red: F04, F07, F10, F15, F16, F17, F104, F40, F105, F44, F50 y F60 en `platform/network/flows.yaml` (líneas 152 a 221), con `case-worker` como origen de F15, F40 y F104; `http_routes.core-banking-mock` (líneas 65 a 67) con `_catch_all: core-mock-catch-all`; los `Server` `core-banking-mock-8080` y `metrics-8081` y la `HTTPRoute` `core-mock-catch-all` ya generados en `platform/network/generated/kind/vectra-mock.yaml`; X01 y los tres casos `U8` en `platform/network/forbidden.yaml` (líneas 3, 4 y 15 a 17);
  - U1, cuota: `U8: { requests: [6.44, 5.3], limits: [29.9, 12.35] }` en `vectra-app` y `U8: { requests: [0.59, 0.32], limits: [2.93, 0.98] }` en `vectra-mock` (`platform/policies/quotas/quotas.yaml`, líneas 10 y 34);
  - U1, datos: `case-db` con la base `case` y el dueño `case_migrator` (`platform/data/chart/values.yaml`, líneas 34 a 52); los Secrets `pg-role-case-app`, `pg-role-case-worker`, `pg-role-case-retention` y `pg-role-case-migrator` en `vectra-app` (`roleConsumers`, líneas 89 a 92; claves `username` y `password`); el certificado `postgres-server-tls` y el Bundle `vectra-internal-ca`;
  - U1, alertas: `FailClosedPersistente` = `max(vectra_cases_failclosed_persistent) > 0` (`platform/observability/rules/platform-rules.yaml`, líneas 143 a 150) y su runbook `platform/runbooks/fail-closed-persistente.md`;
  - U1, pruebas: `FIXED_WAVES["case-management"] = 5` (`platform/tests/test_waves.py`, línea 31); `EXPECTED_WAVES[5]` **sin** `case-management` (`platform/tests/test_platform.py`, línea 285); `BUDGET_GIB = 10.4` (`platform/tests/test_kind_profile.py`, línea 24). `kyverno-test.yaml` no tiene casos propios de U8: rigen los generales de `require-spread-and-pdb`, `require-hpa-bounds` y `add-native-sidecar-to-jobs`;
  - GitOps: `vectra-risk-gitops/components.yaml` **sin** entrada de U8; `vectra-risk-gitops/values/<env>/` existe (hoy solo `model-serving` y `scoring-explainability`); `envs/<env>/values.yaml` trae `imageRegistry` y `mockEnabled`;
  - U2: clientes `case-service` (con `core:read-credit`) y `case-worker` en `identity-edge/keycloak/realm/realm.kind.yaml` (líneas 1069 y 1092). El mock no tiene cliente: solo valida;
  - U3, U4 y U7: `decision-registry-service` (F16), `governance-service` (F104) y `scoring-service` (F15), los tres en 8080.

Sin clúster (AUTONOMIA-01). Todo se verifica con `helm template`, `kubeconform`, `conftest`, `kyverno test`, `promtool`, Docker local contra dobles y las pruebas de `platform/`. **Nada de `kubectl apply`, `helm install`, `argocd` ni sync.**
**Rama:** `tarea/U08-T05`, desde `origin/main`.

Bloque G del plan de U8 (`aidlc-docs/construction/plans/case-management-code-generation-plan.md`) más el cierre: la tarea «G+cierre (19–23, 25, 26)» de `aidlc-docs/construction/plans/demo-recorte-funcional.md` §8, la quinta y última de U8. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 19 Dockerfiles y cadena de suministro | **E\*F** | Entran las dos imágenes (base por digest, `runAsNonRoot`, `readOnlyRootFilesystem`) y `hadolint`. Se difieren el escaneo, el SBOM, la firma y la prueba sobre el SBOM (P-5) | Alcance §3 U8, fila «19: E\*, T1»; enmienda §3 U8, fila «19: T1, más la prueba sobre el SBOM» |
| 20 Chart, values, cuotas y flujos | **E\*F** | Entra completo, con el Job `rt5-demo` y el perfil de DD-3 b (sin `values-kind-demo.yaml`, 2 réplicas y HPA). **Sale la plantilla del CronJob `case-retention`** | Alcance §3 U8, fila «20: E\*, T6; el Job `rt5-demo` entra»; enmienda §3 U8, fila «20 Chart», y §6 P-12 («Quitar la plantilla»); DD-3 |
| 21 Alertas y runbooks | **E\*** | Entran `CoreWriteAttempt` (regla, `promtool` y runbook) y la prueba del nombre de `vectra_cases_failclosed_persistent`. Se difieren las otras ocho alertas y sus runbooks | Alcance §3 U8, fila «21: Solo `CoreWriteAttempt`; el resto T2»; enmienda §3 U8, fila «21 Alertas»; T2 |
| 22 Documentación | **E\*F** | Entran `api.md`, el OpenAPI exportado y `check_openapi.py`. Se difieren `retention.md` y el `conftest` de la firma | Enmienda §3 U8, fila «22 Documentación» |
| 23 Applications, carga y trazabilidad | **E\*** | Entran la Application y la trazabilidad con la lista «Diferido por la demo». Se difiere el script k6 | Alcance §3 U8, fila «23: Carga (T3)»; enmienda §3 U8, fila «23: k6 (T3); trazabilidad con lista (BR-U8-20)» |
| 24 Verificación en kind | — | Queda `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». La fila de §3 dice que entran los escenarios 1, 5 y 7 y se difieren el 2, 3, 4, 6 y la carga; §8 pasa los que entran a U12 | Enmienda §3 U8, fila «24 Kind», y §8 |
| 25 Frontend: N/A | **N/A** | — | Enmienda §3 U8, fila «25 · 26» |
| 26 Cierre de la unidad | **E\*** | Cierre acotado, con `evidence/cierre-demo.md`. Se difiere la evidencia de kind en el PR | Enmienda §3 U8, fila «25 · 26», y §8; alcance §2.4 |

El Paso 16 (CLI `case-retention`) sigue diferido (D, T5; enmienda §3 U8, fila «16»). No es de esta tarea.

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09.

Lo que U8 sostiene en las demos (enmienda §1):
- **Flujo base, D1, D2 y D4:** `case-service` y `case-worker` desplegados, con la base migrada. En D1, `vectra_cases_failclosed_persistent` alimenta `FailClosedPersistente` de U1.
- **D3 (RT-5):** el Job `rt5-demo-<runId>` y la alerta `CoreWriteAttempt` **son la evidencia**. El oráculo de U12 lee el log del Job (403 con `l5d-proxy-error`), la alerta en Prometheus y `vectra_core_write_attempts_total` en 0. Ninguno de los tres se recorta.

U08-T01 a U08-T04 escribieron el código. Esta tarea escribe **lo que lo lleva al clúster**: las dos imágenes, el chart, la regla, la Application y el cierre.

---

**Dos lecciones que esta tarea aplica:**
- **U04-T06 y U04-T08** (`revisiones/U04-T06/ronda-1.md`, F-01): un chart que renderiza bien no prueba que el contenedor arranque. Aquí los **cuatro** contenedores reales (`case-service`, `case-worker`, el Job de migración y el mock) arrancan con las variables y los archivos **que pone el chart** (CA-4).
- **Enmienda §8**: los revisores encontraron cuatro defectos que habrían roto el flujo base en kind sin que ninguna prueba fallara. En U8 los equivalentes son tres: una variable que el chart no pone y el proceso exige (los tres procesos arrancan con `KeyError` si falta una; `services.md`, «Variables de entorno»); el fixture del mock fuera de la imagen; y el Job `rt5-demo` con una etiqueta que la `NetworkPolicy` del mock no admite, que deja D3 sin evidencia de la capa L7 (INF-U8-03).

---

## Alcance

**Dentro:** los Pasos 19, 20, 21, 22, 23, 25 y 26 del plan. Texto del plan, sin recortes salvo lo que la tabla de arriba difiere, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque G — Despliegue y operación

- [ ] **Paso 19 — Dockerfiles y cadena de suministro** (E\*F)
  - Una imagen para `case-service`, `case-worker`, `case-retention` y la migración (P-U8-10), y otra para el mock con sus fixtures; base Python oficial pinneada por digest, `runAsNonRoot` y `readOnlyRootFilesystem`.
  - Construidas, ~~escaneadas, con SBOM y firmadas con `sign-image.yml` de U1; el escaneo y el SBOM son de `supply-chain.yml`~~. (T1; alcance §3 U8, fila 19)
  - Diseño: P-U8-10; NFR-U8-34.
  - **Aceptación**: `hadolint case-management/Dockerfile case-management/core_banking_mock/Dockerfile`; ~~prueba sobre el SBOM: ninguna librería de circuit breaking.~~ (T1; enmienda §3 U8, fila 19: ver P-5)

- [ ] **Paso 20 — Chart, values, cuotas y flujos** (E\*F)
  - `case-service` y `case-worker`: `Deployment`, `Service`, `HorizontalPodAutoscaler` (2–6, CPU 70 %, estabilización 60/300 s), `PodDisruptionBudget`, `ServiceAccount` propia, `ExternalSecret` de la llave `private_key_jwt`, la contraseña del rol de base desde `pg-role-case-app` o `pg-role-case-worker`, que entrega U1 (INF-U1-02; revisión de consistencia entre unidades, 2026-11-01), y `ServiceMonitor`; recursos y probes de INF-U8-04; spread por zona; `vectra-high`; sidecar nativo de Linkerd.
    - `case-service`: `preStop.sleep` de 5 s y `terminationGracePeriodSeconds: 20`;
    - `case-worker`: `terminationGracePeriodSeconds: 30`.
  - ~~`case-retention`: `CronJob` (`schedule` y `timeZone` desde los values, `Forbid`, `startingDeadlineSeconds: 3600`, `activeDeadlineSeconds: 7200`, `backoffLimit: 2`), `vectra-low`, sidecar nativo, y `pg-role-case-retention` de U1 (revisión de consistencia entre unidades, 2026-11-01).~~ (enmienda §3 U8, fila 20: «Se quita la plantilla del CronJob `case-retention`»; §6 P-12)
  - Job de migración como hook de sync (F44), con la `ServiceAccount` `migration-case`, la etiqueta `vectra.io/workload: migration-case` y `pg-role-case-migrator` (revisión de consistencia entre unidades, 2026-11-01), con `case_migrator`, `vectra-low` y la fila de `retention_settings` desde los values.
  - `core-banking-mock` solo con `coreMock.enabled = true`: 2 réplicas, `vectra.io/hpa-exempt` con su justificación (quinta revisión de coherencia entre unidades, 2026-10-31), PDB, `vectra-low`, namespace `vectra-mock`. El chart no crea el `Server` ni las `HTTPRoute`: U1 los genera desde `http_routes.core-banking-mock` de `flows.yaml`, con `GET /v1/credits/{id}` autorizada solo para `case-service` y `core-mock-catch-all` sin `AuthorizationPolicy` (INF-U8-03; revisión de consistencia entre unidades, 2026-11-01).
  - **Job `rt5-demo-<runId>`** (U12; pendientes posteriores al cierre, 2026-10-10): solo con los values de kind y con `probes.runId` (pendientes consolidados, 2026-10-10: ya no en staging), con la `ServiceAccount` `case-service`; envía `POST /v1/credits/{id}/status` al mock y deja en su log el 403 del proxy (INF-U8-03); `backoffLimit: 0`, sidecar nativo, **sin** `ttlSecondsAfterFinished` (se poda al cambiar `probes.runId`). `conftest`: `probes.runId` en los values de staging o de producción → falla; el Job no aparece con ellos ni sin `probes.runId` (pendientes consolidados, 2026-10-10); el selector del `Service` de `case-service` no coincide con las etiquetas del Job (seguimiento de la cuarta revisión de coherencia, 2026-10-31).
  - Values de producción, en `vectra-risk-gitops/values/prod/case-management.yaml` (revisión de consistencia entre unidades, 2026-11-01): `core.enabled = false`, `coreMock.enabled = false`, `allowTestScenarios = false`.
  - Aporte de U8 a las cuotas de `vectra-app` y `vectra-mock` en `platform/policies/quotas/` de U1 (INF-U8-05).
  - Comprobar en `platform/network/flows.yaml` F04, F07, F10, F15, F16, F17, F40, F44, F50, F60, F104 y F105, con `case-worker` como origen de F15, F40 y F104, y X01 en la suite de conectividad.
  - Diseño: INF-U8-01, 02, 03, 04, 05, 06, 07; P-U8-07, 10; NFR-U8-10, 12, 14, 20, 26, 43, 44. Historia: US-609.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test case-management/policies/conftest/`, que verifica:
    - HPA 2–6, PDB, `topologySpreadConstraints`, `priorityClassName`, requests y limits;
    - `preStop.sleep` y `terminationGracePeriodSeconds ≥ 20` en `case-service`, `≥ 30` en `case-worker`; la anotación del sidecar en ~~el CronJob y~~ el Job; (el CronJob: P-12)
    - en los values de producción: `core.enabled = false`, `coreMock.enabled = false`, `allowTestScenarios = false`, y ningún recurso del mock renderizado;
    - ninguna constante de INF-U8-07 como variable de entorno.

    Además, `kyverno test` (sin excepción a `require-spread-and-pdb`), `conftest test platform/policies/quotas/` (cuota ≥ suma de aportes) y `uv run python platform/network/generate.py --check`.

- [ ] **Paso 21 — Alertas y runbooks** (E\*)
  - `PrometheusRule` con:
    - ~~`CaseEvidencePending` y `CaseEvidenceAbandoned` (P-U8-04);~~ (T2; alcance §3 U8, fila 21)
    - ~~`CaseRetentionMissing` y `CaseRetentionOverdue` (P-U8-07);~~ (T2; alcance §3 U8, fila 21)
    - ~~`CaseApiUnavailable`, `CaseJobsOverdue`, `CaseFirstAttemptFailureHigh` (con su regla de grabación) y `ScoringRequestRejected` (P-U8-08);~~ (T2; alcance §3 U8, fila 21)
    - `CoreWriteAttempt` con la expresión de INF-U8-03, renderizada solo con `coreMock.enabled = true`.
  - `FailClosedPersistente` (U1), ~~`AuthDeniedBurst` (U2) y `PostgresVolumeUsageHigh` (U1)~~ no se definen aquí: se prueba que las métricas de U8 que las alimentan existen con esos nombres. (La prueba de las otras dos: T2; la enmienda §3 U8, fila 21, solo nombra `vectra_cases_failclosed_persistent`)
  - Un runbook por alerta. El de `CoreWriteAttempt` explica que en la demostración de RT-5 es la evidencia esperada y la limitación del `offset 5m` si el pod del mock se reemplaza (INF-U8-03).
  - Diseño: P-U8-04, 06, 07, 08; INF-U8-03, 08; NFR-U8-03, 45, 46. Historias: US-112, US-603.
  - **Aceptación**: `promtool test rules case-management/observability/rules/tests/*.yaml`:
    - cada alerta con series en los dos lados del umbral;
    - ~~`CaseApiUnavailable` sin `up{job="case-service"}` durante 2 min → dispara;~~ (T2)
    - ~~`CaseRetentionMissing` con la serie ausente 1 h → dispara;~~ (T2; P-12)
    - `CoreWriteAttempt`: la serie de Linkerd **arranca en 1** y dispara; una denegación con otro `route_name` no dispara; el contador del mock de 0 a 1 dispara.

    Además, `uv run python platform/tests/test_runbooks.py --root case-management` y `helm template` con los values de producción → sin `CoreWriteAttempt`.

- [ ] **Paso 22 — Documentación** (E\*F)
  - ~~`case-management/docs/retention.md`: plazos, fuente única (`retention_settings`), riesgo aceptado de los respaldos y los tres **[VERIFICAR]**, con un espacio para la firma de cumplimiento; el despliegue a producción la exige (NFR-U8-47).~~ (enmienda §3 U8, fila 22: «Se difieren `retention.md` y el conftest de la firma en `values/prod`»)
  - `case-management/docs/api.md` y el OpenAPI exportado de `case-service` y del mock.
  - Diseño: BR-U8-20; NFR-U8-47.
  - **Aceptación**: `uv run python case-management/tools/check_openapi.py` (el OpenAPI versionado coincide con el de la app) ~~y una regla de `conftest` sobre `vectra-risk-gitops/values/prod/case-management.yaml` que exige el value con la referencia a la firma de `retention.md`: `generate.py` no escribe anotaciones propias en una Application (revisión de consistencia entre unidades, 2026-11-01).~~ (enmienda §3 U8, fila 22)

- [ ] **Paso 23 — Applications, especificación de carga y trazabilidad** (E\*)
  - Entradas en `vectra-risk-gitops/components.yaml` con `wave: 5` (migración como hook, `case-service`, `case-worker`~~, CronJob~~): `case-management` en todos los entornos y la del mock con `envs: [kind, staging]`. `generate.py` escribe las Applications, sin auto-sync (revisión de consistencia entre unidades, 2026-11-01). (El CronJob: P-12. La entrada del mock: P-3)
  - ~~Script k6 para U12: 10 solicitudes/s de ingesta con la consola en paralelo, umbrales de NFR-U8-01 y el histograma de NFR-U8-02.~~ (T3; alcance §3 U8, fila 23)
  - Trazabilidad de cada BR-U8 a una prueba.
  - Diseño: P-U1-12; NFR-U8-01, 02.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`; `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; ~~`k6 inspect case-management/tests/load/cases.js`~~; `uv run python platform/tests/test_traceability.py --unit case-management --all`. (`k6 inspect`: T3)

### Bloque H — Verificación en kind (con aprobación humana)

- [ ] ~~**Paso 24 — Puerta de aprobación y escenarios en kind**~~ — **no entra**: consolidado en U12 Paso 18 (enmienda §8). Va en «Fuera» y en «Pendiente en U12» del cierre.

### Bloque I — Cierre

- [ ] **Paso 25 — Frontend: N/A** (N/A)
  - La consola es de U10.
  - **Aceptación**: `test ! -d case-management/frontend`.

- [ ] **Paso 26 — Cierre de la unidad** (E\*)
  - **Aceptación**: `make -C case-management check`, que corre en orden las verificaciones estáticas, las migraciones, las propiedades y las pruebas de integración de los Pasos 1–23 y termina en 0. ~~Las de kind (Paso 24) se revisan como evidencia en el PR.~~ (enmienda §8)

### Estructura de destino (§1 del plan): lo que esta tarea crea

```text
vectra-risk/case-management/
|-- Dockerfile                                   # nuevo (Paso 19): una imagen, tres órdenes (servicio, worker, migración)
|-- core_banking_mock/Dockerfile                 # nuevo (Paso 19): el mock con `fixtures/credits.json`
|-- Makefile                                     # se amplía: image, image-mock, chart, policy-chart, policy-chart-u1, quota-flows, rules, runbooks, openapi, links, traceability
|-- docs/
|   |-- api.md                                   # nuevo (Paso 22)
|   |-- openapi/  case-service.yaml  core-banking-mock.yaml   # nuevo: el OpenAPI exportado (P-7)
|   `-- imagenes.md                              # nuevo: build, push, digest y PR de values de kind, sin ejecutarlos (como U7 y U9)
|-- tools/check_openapi.py                       # nuevo (Paso 22); sale `tools/.gitkeep`
|-- chart/
|   |-- Chart.yaml  values.yaml                  # nuevos; los defaults son los de producción (P-2)
|   |-- values-kind.yaml                         # nuevo: lo que `render_env("kind")` debe ver (P-1 y P-2)
|   `-- templates/  _helpers.tpl  case-service.yaml  case-worker.yaml  migration-job.yaml  core-banking-mock.yaml
|                   rt5-demo-job.yaml  serviceaccounts.yaml  identity.yaml  servicemonitors.yaml  prometheusrule.yaml
|-- policies/conftest/  *.rego                   # nuevo (Paso 20): reglas del render y de los values por entorno
|-- observability/
|   |-- rules/case-management.rules.yaml         # nuevo: el `spec` de la `PrometheusRule` renderizada, versionado
|   |-- rules/tests/core-write-attempt.yaml      # nuevo: casos de `promtool`
|   `-- runbooks/core-write-attempt.md           # nuevo (Paso 21)
`-- tests/
    |-- unit/  test_chart.py  test_rules.py  test_openapi.py   # nuevos
    |-- integration/test_image.py                # nuevo (CA-4)
    |-- fixtures/crds/  externalsecret.json  servicemonitor.json  prometheusrule.json   # nuevos
    `-- load/.gitkeep                            # se queda: k6 sigue diferido (T3)
```

Los nombres de las plantillas son orientativos; los demás son los que nombran los criterios. **No** se crea `templates/retention-cronjob.yaml` (P-12) ni `docs/retention.md`. Fuera de `case-management/`, uno por uno:

- `vectra-risk-gitops/components.yaml` (la entrada `case-management`) y lo que `generate.py` escribe (`apps/<env>/case-management.yaml` y lo que cambie en `apps/<env>/`);
- `vectra-risk-gitops/values/kind/case-management.yaml`, `values/staging/case-management.yaml` y `values/prod/case-management.yaml` (nuevos; Paso 20);
- `platform/tests/test_platform.py`: **solo** `case-management` en `EXPECTED_WAVES[5]`. Sin esa palabra `make -C platform check` falla; es la candidata de la plantilla de despliegue (C-5);
- `platform/tests/test_kind_profile.py`: **solo** `BUDGET_GIB` y su comentario, y solo si la cifra medida no cabe en el tope de la base (sección «Presupuesto»);
- `aidlc-docs/construction/case-management/evidence/cierre-demo.md` (nuevo), `aidlc-docs/construction/case-management/code/services.md` (solo «Arranque y apagado», con lo que decida P-4), el plan (casillas), `CANDIDATAS.md` y `bitacoras/U08-T05.md`.

Nada más de `platform/`: ni `flows.yaml`, ni `quotas.yaml`, ni `kyverno-test.yaml`, ni las reglas de U1.

### Precisiones

#### Paso 19 — Imágenes

- `case-management/Dockerfile` y `case-management/core_banking_mock/Dockerfile`, multi-stage, como `scoring-explainability/scoring/Dockerfile` y `bias-monitoring/Dockerfile`, con contexto en la raíz de `vectra-risk/`:
  - cada `FROM` fijado por digest;
  - usuario `65532:65532`, el mismo `runAsUser` y `runAsGroup` del chart;
  - solo el runtime y sus dependencias del workspace (U0), sin dependencias de desarrollo.
- **Imagen `case-management`** (P-U8-10): una imagen y tres órdenes, que fija el chart:
  - `python -m vectra_case.app` (`case-service`; 8080 y 8081);
  - `python -m vectra_case.worker` (`case-worker`; solo 8081);
  - `alembic -c /app/alembic.ini upgrade head` (migración), así que la imagen lleva `alembic.ini` y `migrations/` en `/app`.

  El plan nombra también `case-retention`: la imagen es la misma, pero su CLI es del Paso 16 (D) y el chart no la invoca. No se añade ningún punto de entrada para ella.
- **Imagen `core-banking-mock`**: `python -m core_banking_mock.app` (8080 y 8081) y el fixture en **`/app/fixtures/credits.json`**, la ruta de `core_banking_mock.app.DEFAULT_FIXTURES`. Una prueba compara la ruta del `COPY` con la constante importada. Sin `ConfigMap` ni volumen (INF-U8-02). La imagen no lleva `vectra_case`.
- Targets `image` e `image-mock` en `case-management/Makefile`, con los tags `localhost:5001/vectra/case-management:dev` y `localhost:5001/vectra/core-banking-mock:dev`. `check` construye las dos **antes** de `test_image.py` (candidata de U09-T04, F-03: la prueba no puede pasar con una imagen vieja).
- `case-management/docs/imagenes.md`, como `scoring-explainability/docs/imagenes.md`: build, comprobaciones locales, y el push, el digest real y el PR de values de kind **sin ejecutarlos**. Los hace el operador en U12 Paso 18. Debe decir que las imágenes de `governance`, `scoring-explainability` y `case-management` se construyen **del mismo commit** y sus digests suben en un solo PR (C-4).
- En `chart/values.yaml`, los dos digests son de ejemplo y distintos de los que ya usan los otros charts (hoy van del `…0001` al `…0006`): los dos siguientes libres en la base de la rama. No pueden ser 64 ceros (`test_placeholder_digests_are_only_on_images_we_build`).
- «Ninguna librería de circuit breaking» (NFR-U8-34): ver P-5.

#### Paso 20 — Chart

- **Nombres** (los que espera `platform/network/flows.yaml`, líneas 90, 91, 107 y 125):
  - `case-service` y `case-worker`: `Deployment`, `Service` y `ServiceAccount` con ese nombre y `app.kubernetes.io/name` igual, en `vectra-app`;
  - migración: `ServiceAccount` `migration-case` y etiqueta `vectra.io/workload: migration-case` en el pod;
  - `core-banking-mock`: `Deployment`, `Service` y `ServiceAccount` `core-banking-mock`, en `vectra-mock`, con el namespace explícito en cada recurso (P-3).
- **Puertos:** `Service` de `case-service` con 8080 y 8081; el de `case-worker` **solo** 8081 (el worker no abre 8080); el del mock con 8080 (F17) y 8081 (F60 a `ns:vectra-mock`). Un `ServiceMonitor` por cada uno, en 8081, con `honorLabels: true` (como `scoring-explainability/chart/templates/servicemonitors.yaml`).
- **Recursos** (INF-U8-04), en `chart/values.yaml`, que es lo que rinden staging y prod: `case-service` 250m / 256 MiB y 1 CPU / 512 MiB; `case-worker` 200m / 256 MiB y 1 CPU / 512 MiB; migración 100m / 128 MiB y 500m / 256 MiB; mock 50m / 64 MiB y 250m / 128 MiB. El request de memoria de kind es P-1.
- **Réplicas y HPA.** Cada `Deployment` declara `replicas: 2`: `test_kind_profile.py` cuenta `spec.replicas` (1 si falta). El HPA de 2 a 6 va en los tres entornos (DD-3 b; `require-hpa-bounds`), como en U7. `deployment-architecture.md` dice «kind usa 2 réplicas fijas»: se lee como el mínimo del HPA, no como un chart sin HPA. Los tres `Deployment` usan `maxSurge: 1` y `maxUnavailable: 0` (INF-U8-05).
- **Sondas:** readiness `/readyz` cada 5 s y liveness cada 10 s, las dos en 8081, sin `startupProbe`. INF-U8-04 llama `/livez` a la liveness, pero `vectra_common.ops_server` sirve `/healthz`: el chart usa **`/healthz`** (C-3). Una prueba compara las rutas con las de `ops_server`, importadas y no copiadas, como `scoring-explainability/tests/unit/test_chart.py::test_probes_the_paths_are_routes_that_ops_server_serves`.
- **Variables de cada contenedor:** exactamente las de `services.md` («Arranque y apagado» y «Variables de entorno»):
  - `case-service`: `CASE_DB_DSN`, `CASE_GOVERNANCE_URL`, `CASE_REGISTRY_URL`, `CASE_CORE_ENABLED`, `CASE_CORE_URL` (solo con `core.enabled = true`), `CASE_ALLOW_TEST_SCENARIOS`, `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL`, `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y, si alguna URL es `https://`, `VECTRA_CA_BUNDLE`;
  - `case-worker`: `CASE_DB_DSN`, `CASE_GOVERNANCE_URL`, `CASE_SCORING_URL`, `VECTRA_CLIENT_ID`, `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y `VECTRA_CA_BUNDLE`;
  - migración: `CASE_DATABASE_URL`, `RETENTION_DECIDED_YEARS`, `RETENTION_UNDECIDED_YEARS` y `RETENTION_INTAKE_KEYS_DAYS` (`migrations/env.py`, `RETENTION_VARIABLES`);
  - mock: `VECTRA_OIDC_ISSUER`, `VECTRA_JWKS_URL` y `VECTRA_CA_BUNDLE`;
  - las URL salen de `flows.yaml` (Service y puerto de F15, F16, F17 y F104), leídas del archivo en la prueba;
  - ninguna con valor por omisión incrustado en la plantilla: salen de values con `required`;
  - **ninguna constante de `vectra_case/config.py`** aparece como variable de entorno (INF-U8-07). La prueba recorre los nombres públicos de `config.py`, importado.
- **Base de datos** (INF-U8-01; `governance/chart/templates/service.yaml`, líneas 55 a 60): el DSN va **sin credenciales**. `PGUSER` y `PGPASSWORD` salen del Secret de U1 de cada proceso: `pg-role-case-app` (`case-service`), `pg-role-case-worker` (`case-worker`) y `pg-role-case-migrator` (migración). El chart no crea ningún `Secret` ni `ExternalSecret` para la base. El host es `case-db-rw.vectra-data.svc.cluster.local` y la base es `case`. El `sslmode` es P-6.
- **Identidad** (INF-U8-01): un `ExternalSecret` por cliente (`identity/clients/case-service` e `identity/clients/case-worker`, propiedad `private-key`), con el formato de `governance/chart/templates/service-identity.yaml`, montado de solo lectura. El mock y la migración no tienen llave. Ningún `Secret` en el render.
- **Apagado** (INF-U8-06): `preStop.sleep.seconds: 5` y `terminationGracePeriodSeconds: 20` en `case-service`; `case-worker` sin `preStop`. El valor del worker es P-4. Una prueba compara el del chart con `vectra_case.config.WORKER_TERMINATION_GRACE` (mayor o igual), importado.
- **Job de migración:** hook de sync de Argo CD (`argocd.argoproj.io/hook: Sync`, como `governance/chart/templates/migration-job.yaml`), `vectra-low`, anotación del sidecar nativo, `backoffLimit` y `activeDeadlineSeconds` explícitos. Los tres plazos (`retention.decided_years`, `retention.undecided_years` y `retention.intake_keys_days`) son values con `required` y llegan como las tres variables `RETENTION_*`. `retention.schedule` y `retention.timeZone` **no** existen en `values.yaml`: salen con el CronJob (P-12).
- **`core-banking-mock`** (INF-U8-02): solo con `coreMock.enabled = true`. 2 réplicas fijas, `vectra.io/hpa-exempt` con su justificación, PDB `minAvailable: 1`, spread por zona, `vectra-low`, `vectra.io/criticality: low`. Sin `Server`, `HTTPRoute` ni `AuthorizationPolicy` en el chart: son de U1.
- **Job `rt5-demo-<runId>`** (INF-U8-03), solo con `probes.runId`:
  - `ServiceAccount` `case-service`; pod con `app.kubernetes.io/name: case-service` (lo que admite la `NetworkPolicy` del mock) y **sin** `vectra.io/workload: case-service`;
  - el `Service` y el PDB de `case-service` seleccionan `app.kubernetes.io/name` **y** `vectra.io/workload: case-service`, y los pods del `Deployment` llevan las dos;
  - usa la imagen `case-management`, sin la llave de Keycloak montada y sin variables de la base;
  - envía `POST /v1/credits/<id>/status` a la misma URL del core que `CASE_CORE_URL`, sin token, y escribe en su salida el código de respuesta y la cabecera `l5d-proxy-error`. Termina con 0 **solo** si la respuesta es 403; con cualquier otra (o sin conexión) termina distinto de 0. Así `completionTime` existe cuando la evidencia es la esperada (plan de U12, Paso 8);
  - `backoffLimit: 0`, `restartPolicy: Never`, anotación del sidecar nativo, **sin** `ttlSecondsAfterFinished`, `vectra-low`;
  - `probes.runId` cumple `^[0-9]{8}-[0-9]{4}$` (INF-U12-02); con otro formato el render falla.
- **Values por entorno** (P-2):
  - `chart/values.yaml`: `core.enabled: false`, `coreMock.enabled: false`, `allowTestScenarios: false` y sin `probes.runId`. Un render sin values de entorno es el de producción;
  - `vectra-risk-gitops/values/prod/case-management.yaml`: los tres en `false`, **escritos** (la regla de `conftest` lee este archivo);
  - `vectra-risk-gitops/values/staging/case-management.yaml`: `core.enabled: true`, `coreMock.enabled: true` y `allowTestScenarios: true`;
  - kind: lo mismo que staging, repartido según P-2. Ninguno de los tres archivos trae `probes.runId`: lo añade U12 (`prepare`) en el de kind.
- **`conftest`** en `case-management/policies/conftest/`, con las reglas del plan. Dos entradas distintas:
  - **el render** de cada entorno: HPA, PDB, spread, `priorityClassName`, recursos, `preStop`, los dos plazos de gracia, la anotación del sidecar en los Jobs, ninguna constante como variable, ningún recurso del mock ni `CoreWriteAttempt` en prod, ningún `CronJob`, y el selector del `Service` frente a las etiquetas del Job;
  - **los archivos de values** de staging y prod: `probes.runId` presente → falla; en prod, cualquiera de los tres interruptores distinto de `false` → falla.

  Cada regla tiene en `test_chart.py` un caso que falla con una mutación.
- **Cuota (INF-U8-05).** Los aportes de U8 ya están en `quotas.yaml` y coinciden con INF-U8-05. Incluyen el CronJob, que no se rinde. Una prueba recalcula el aporte desde el render de staging (HPA al máximo más 1 pod de `maxSurge` por `Deployment`, el Job de migración, el proxy de 100m / 20 MiB y 500m / 128 MiB, y el 30 %) y comprueba que **no supera** la línea de `quotas.yaml`, leída del archivo, y que la diferencia en `vectra-app` es el término del CronJob de INF-U8-05. En `vectra-mock` las cuatro cifras coinciden. El plan dice `conftest test platform/policies/quotas/`, pero en el repositorio esa comprobación es `platform/policies/quotas/render.py --check` y `test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota`. Usa esas y regístralo, como U7, U9 y U11. Si un aporte no cuadra, **repórtalo**: no edites U1.
- **Conexiones (NFR-U8-14).** Una prueba calcula 12 × `config.CASE_DB_POOL_MAX` × 1,2 + 2 y comprueba que no supera `maxConnections` de `case-db` en `platform/data/chart/values.yaml` (100). La medición con carga se difiere (T3).
- **Flujos.** Los doce del plan ya están en `flows.yaml`, y X01 en `forbidden.yaml`. Sin flujos nuevos. F105 (`case-retention`) se queda en U1 aunque el CronJob no se rinda. Si algo falta, **repórtalo**: no edites U1. La ejecución de la suite de conectividad en kind es de U12.
- **Admisión** (reglas del plan): imagen por digest, `runAsNonRoot`, `readOnlyRootFilesystem` (con `emptyDir` solo si algo escribe en disco; CA-4 lo decide con `--read-only`), sin `privileged` ni `hostPath`, recursos, `priorityClassName`, `vectra.io/criticality` (`high` en `case-service` y `case-worker`, NFR-U8-20), 2 réplicas, spread, PDB por `app.kubernetes.io/name` y HPA o `vectra.io/hpa-exempt`.
- **Perfil demo (T6):** DD-3 b. Sin `values-kind-demo.yaml` y sin 1 réplica.

#### Presupuesto de memoria de kind (`DECISIONES-LOOP.md` §7)

La máquina de la demo tiene 14 GiB. `BUDGET_GIB` está en 10,4 con U7 (`requested_gib()` = 10,3438 GiB). U11-T03 lo lleva a 10,7 (128 MiB solo en kind, su P-1) y falta U10. §7 ya dio por inviable un pico de ≈ 13 GiB. Por eso esta tarea **no sube `BUDGET_GIB` sin más**:

1. **Mide primero.** Antes de tocar `components.yaml`, anota la cifra de la base de la rama con la orden de CA-12. Con la Application agregada, mídela otra vez.
2. **Aporte de U8**, réplicas × (request + 20 MiB de proxy). Los Jobs no cuentan: `requested_gib()` suma `Deployment` y `StatefulSet`.

   | Componente | Por diseño (INF-U8-04) | Con P-1 = (b) |
   |---|---|---|
   | `case-service` | 2 × (256 + 20) = 552 MiB | 2 × (128 + 20) = 296 MiB |
   | `case-worker` | 2 × (256 + 20) = 552 MiB | 2 × (128 + 20) = 296 MiB |
   | `core-banking-mock` | 2 × (64 + 20) = 168 MiB | 168 MiB (no cambia) |
   | **Total** | **1 272 MiB = 1,2422 GiB** | **760 MiB = 0,7422 GiB** |

   La diferencia entre las dos mediciones debe ser esa cifra (± 0,001). Si no lo es, algo más cambió o `render_env("kind")` no ve lo que Argo CD despliega (P-2): **detente y repórtalo**.
3. **El request de kind** va en `case-management/chart/values-kind.yaml`, que entra por `kind_values` en `components.yaml` (como `postgres`). `render_env` sí pasa `kind_values`; **no** pasa `vectra-risk-gitops/values/kind/<nombre>.yaml` (C-9), así que un override puesto allí no lo vería `test_kind_profile.py`. Las réplicas, los limits (512 MiB), el HPA y los PDB no cambian, y staging y prod siguen en INF-U8-04 (una prueba lo fija, como `test_kind_serving_halves_memory_requests_and_staging_and_prod_keep_inf_u6_01`).
4. `BUDGET_GIB` sube a la cifra medida con U8, redondeada hacia arriba a 0,1 GiB, con el comentario de la decisión y la cita de §7. Nunca más arriba. Sobre la base de hoy (10,3438): 11,1 con (b) y 11,6 con (a). Si U11-T03 ya está en `main` (10,6329): 11,4 con (b) y 11,9 con (a). Parte siempre de la cifra de la base de tu rama.
5. **Proyección, que no decide el codificador.** Suma a la cifra medida lo que todavía no tenga Application: U11 (0,2891 GiB) y U10 (INF-U10-01: `console-bff`, 2 × (256 + 20) MiB; `console-spa`, 2 × (32 + 20) MiB; 0,6406 GiB). Al redactar esta tarea da ≈ **12,0 GiB con (b)** y ≈ **12,5 GiB con (a)**. Recalcúlala con lo que haya en `main` y déjala en la bitácora y en el cierre.
6. **Detención.** Si la cifra medida no cuadra (punto 2), o si la proyección llega a **13,0 GiB**, no subas `BUDGET_GIB`: **detente y repórtalo** con la cifra, el desglose por unidad y las opciones. Es una detención, no un ROJO del codificador. No cambies réplicas, limits ni requests fuera de lo que P-1 fija.
7. En la prueba de los contenedores reales (CA-4), anota la memoria de `case-service` y de `case-worker` en reposo (`docker stats --no-stream`). Es el dato que justifica o desmiente P-1 = (b), sin umbral.

#### Paso 21 — `CoreWriteAttempt`

- **Una alerta y ninguna regla de grabación.** La `PrometheusRule` del chart tiene exactamente un `alertname`, `CoreWriteAttempt`, con la expresión de INF-U8-03, literal:

  ```text
  increase(vectra_core_write_attempts_total[5m]) > 0
  or
  sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"})
    - (sum(inbound_http_authz_deny_total{namespace="vectra-mock", route_name="core-mock-catch-all"} offset 5m) or vector(0))
    > 0
  ```

  Sin `for`, con `severity: SEV2` (tabla de eventos de P-U8-06) y `runbook_url` relativo a `vectra-risk/` (como `governance/observability/governance-rules.yaml`). La descripción distingue las dos series: la del mock indica, además, que Linkerd dejó pasar el `POST`.
- El `route_name` de la expresión sale de `http_routes.core-banking-mock._catch_all` de `flows.yaml`, o una prueba compara los dos.
- Se rinde **solo** con `coreMock.enabled = true`. En prod el render no tiene ninguna `PrometheusRule`.
- **Dónde vive cada cosa** (como U11-T03): `case-management/observability/rules/case-management.rules.yaml` es el `spec` de la `PrometheusRule` **renderizada**, versionado. `make -C case-management rules` lo regenera desde el render de kind, **falla si el versionado difiere**, comprueba que el de staging es idéntico y corre `promtool`. Los casos de `rules/tests/` apuntan a ese archivo. No nombres ningún directorio `generated` ni `rendered` dentro de `case-management/`: `test_traceability.py` y `test_runbooks.py` los saltan.
- **Casos de `promtool`**, uno con nombre por cada afirmación de la aceptación:
  - la serie de Linkerd nace en 1 → dispara;
  - una denegación con otro `route_name` (por ejemplo, la de `metrics-8081`) → no dispara;
  - el contador del mock pasa de 0 a 1 → dispara;
  - el contador del mock se queda en 0 y no hay serie de Linkerd → no dispara (el otro lado del umbral);
  - la serie de Linkerd en 1 desde hace más de 5 min, sin eventos nuevos → deja de disparar;
  - el caso de D3: la serie de Linkerd nace en 1 y el contador del mock **sigue en 0** → dispara.
- **Prueba del nombre** (`test_rules.py`): saca los nombres de métrica de la expresión de `FailClosedPersistente` de `platform/observability/rules/platform-rules.yaml`, leída del archivo, y comprueba que `vectra_case.metrics` registra una serie con ese nombre, importado. Lo mismo entre la expresión de `CoreWriteAttempt` y `core_banking_mock.metrics`. Renombrar la métrica en el código debe hacer fallar la prueba.
- **Runbook** `case-management/observability/runbooks/core-write-attempt.md`, con las secciones de `platform/runbooks/_template.md` y un comando en cada paso de «Verificación». Dice las dos cosas del plan: que en la demostración de RT-5 la alerta **es la evidencia esperada**, y la limitación del `offset 5m` si el pod del mock se reemplaza (revisar los logs de denegación del proxy y del mock). Ningún texto pasa `forbidden_phrases.py`.

#### Paso 22 — Documentación

- `case-management/docs/api.md`: las 9 rutas de `case-service` y las 2 del mock, con rol o scope, códigos de respuesta y los `reason` que salen a la red (`decision_already_recorded`, `model_frozen_after_recommendation`); la `Idempotency-Key`; los valores de `credit_status` (`no_integrado` con `core.enabled = false`); las variables de entorno de cada proceso; y qué quedó diferido (la retención). Con enlaces relativos al OpenAPI exportado y al runbook.
- OpenAPI exportado y `tools/check_openapi.py`: ver P-7.

#### Paso 23 — Application y trazabilidad

- Entrada en `components.yaml` (P-3): `{ name: case-management, wave: 5, namespace: vectra-app, path: case-management/chart, env_values: true, kind_values: [case-management/chart/values-kind.yaml] }`, con un comentario como el de las otras unidades. `generate.py` escribe una Application por entorno, sin `syncPolicy.automated`, y agrega solo `values/<env>/case-management.yaml` a sus `valueFiles` (`generate.value_files`).
- Va en la wave 5 con `governance` y `scoring-explainability` (C-4): `ServingConfig` es estricto y un consumidor con el tipo viejo falla cerrado.
- **Trazabilidad.** `python3 -B platform/tests/test_traceability.py --unit case-management --all` marca hoy **14** identificadores (comprobado al redactar, sobre `deb0a21` de `tarea/U08-T04`). Destino de cada uno:

  | Identificador | Destino | Dónde se traza (o por qué se difiere) |
  |---|---|---|
  | INF-U8-05 | **Trazar** | La prueba de `test_chart.py` que recalcula el aporte y lo compara con `quotas.yaml` |
  | NFR-U8-10 | **Trazar** | `chart/templates/case-service.yaml` y `case-worker.yaml`; prueba: dos `Deployment`, la misma imagen por digest y distinta orden |
  | NFR-U8-12 | **Trazar** | Regla de `conftest` de réplicas, spread, PDB y HPA de 2 a 6. La alerta `CaseJobsOverdue` va en el cierre como diferida, sin fila |
  | NFR-U8-14 | **Trazar** | La prueba de conexiones de `test_chart.py`. La medición con carga va en el cierre como «no comprobado», sin fila |
  | NFR-U8-20 | **Trazar** | `vectra.io/criticality: high` en los dos `Deployment` y su regla. La alarma `CaseApiUnavailable` va en el cierre como diferida, sin fila |
  | NFR-U8-34 | **Trazar** | `case-management/Dockerfile` y la comprobación de `test_image.py` (P-5). El contrato de `.importlinter` no cuenta: la herramienta no lee archivos sin sufijo |
  | NFR-U8-40 | **Trazar** | La plantilla que arma el DSN y la regla de `sslmode` (P-6) |
  | NFR-U8-42 | **Trazar** | Se cita en la prueba que **ya** comprueba las etiquetas de las métricas (`tests/integration/test_app.py`, Paso 13). Sin cambio de comportamiento |
  | NFR-U8-44 | **Trazar** | La regla de `conftest` sobre `values/prod/case-management.yaml` |
  | INF-U8-08 | **Diferir** | Paso 24, escenario 6 (ampliar el volumen), y la parte de `PostgresVolumeUsageHigh` del Paso 21; enmienda §3 U8, filas «24 Kind» y «21 Alertas»; T2 |
  | NFR-U8-46 | **Diferir** | Paso 16 (CLI) y las tres métricas de retención del Paso 11; enmienda §3 U8, filas «16» y «11»; T5 |
  | NFR-U8-47 | **Diferir** | Paso 22 (`retention.md` y el `conftest` de la firma); enmienda §3 U8, fila «22 Documentación» |
  | NFR-U8-51 | **Diferir** | Paso 8 (`mutmut`); enmienda §3 U8, fila «8 Resumen», y §2 regla 3; T3 |
  | P-U8-07 | **Diferir** | Paso 16 y el CronJob del Paso 20; enmienda §3 U8, filas «16» y «20 Chart»; §6 P-12 |

  - La lista «Diferido por la demo» de `cierre-demo.md` tiene **exactamente** esas cinco filas más la de **BR-U8-20** (enmienda §3 U8, fila «23»: «trazabilidad con lista (BR-U8-20)»; Pasos 16 y 22). Cada fila lleva el identificador, el paso y la cita. La herramienta acepta la fila de BR-U8-20 porque no cuenta las BR entre los identificadores de la unidad (candidata de U03-T02): `0003_guards.py` y `case_fsm.py` ya la citan por `guard_vencido` y no estorban.
  - Cada identificador que se traza se cita en el artefacto que lo implementa o en la prueba que lo verifica. Citarlo solo en `docs/api.md` no cuenta.
  - **Ningún archivo de `case-management/` escribe** `INF-U8-08`, `NFR-U8-46`, `NFR-U8-47`, `NFR-U8-51` ni `P-U8-07`: la herramienta rechaza una fila diferida cuyo identificador «ya tiene código o prueba».
  - La herramienta solo lee archivos con sufijo conocido, `Makefile` y `Dockerfile` (`CANDIDATAS.md`, «`test_traceability.py:33,110`»).
  - Corre la prueba al empezar, registra lo que marca y justifica cada identificador en la bitácora. Si la lista difiere de las 14 de arriba, dilo.
- **BR-U8 a una prueba.** `test_traceability.py` no ve las BR. Por eso hay un `git grep` por cada una (CA-11), como en U7, U9 y U11. Hoy quedan **6 sin prueba**: BR-U8-03, 04, 14, 17, 20 y 13b. Las de los Pasos 9 a 13 (03, 04, 13b, 14 y 17) se citan en la prueba que ya las ejerce (`test_intake.py`, `test_app.py`, `test_sweeps.py`, `test_decision.py`); si ninguna lo hace, se escribe. BR-U8-20 va en la lista y el `git grep` la exceptúa.

#### Candidatas que se atienden aquí (`CANDIDATAS.md`)

Los números de línea son los del `CANDIDATAS.md` de la rama `tarea/U08-T04` (`deb0a21`), que trae las candidatas de sus cuatro rondas; si se mueven al fusionar, busca por el texto. El codificador marca cada una («~~…~~ **Atendida en U08-T05:** …»).

- **C-1 · `terminationGracePeriodSeconds` del `case-worker` (línea 550; U08-T04, ronda 2, F-04).** El peor caso real del apagado es ≈ 34 s (toma en curso ≤ 4 s + drenaje de 20 s + 10 s de `GRACEFUL_SHUTDOWN` de las sondas) y el plan dice 30 s. Ver P-4.
- **C-2 · Apagado de `case-service` y `RECONCILER_LEASE` (línea 521; U08-T03).** Ver P-4.
- **C-3 · `/livez` en el diseño de U8 (línea 511).** El chart usa `/healthz` y una prueba lo ata a `ops_server`. El texto de INF-U8-04 no se toca: la corrección del diseño sigue abierta.
- **C-4 · Orden de despliegue de U4, U7 y U8 (línea 481).** Wave 5 y `docs/imagenes.md` con las imágenes del mismo commit y un solo PR de digests. Con esto la candidata queda cerrada para U8.
- **C-5 · `EXPECTED_WAVES` (líneas 303 y 517).** Nombrado arriba entre los archivos de U1 que esta tarea toca. La candidata de la plantilla (`loop/plantilla-tarea.md`) sigue abierta: es del loop.
- **C-6 · `check-chart` y el PDB repetido (líneas 345, 400 y 467).** No se arregla U1: `make -C case-management policy-chart-u1` rinde un entorno por directorio, como `bias-monitoring/Makefile`. Ver CA-5 y «Restricciones del entorno».
- **C-7 · Frontera del TTL de la caché de `serving-config` (línea 576; U08-T04, ronda 4, F-01).** `ServingConfigClient` usa `edad <= SERVING_CONFIG_CACHE_TTL` (5 s; `governance_client.py`, línea 77) y el modelo de PBT-U8-01 usa `<`, con un `FakeClock` que suma tiempo real. Dos cambios, solo de pruebas:
  - PBT-U8-01 corre con un reloj cuya parte real está congelada, para que el modelo y el código lean la misma edad;
  - una prueba con nombre ejerce la frontera: a los 5 s exactos la caché sirve, a los 5 s más un instante vuelve a leer. La mutación `<=` → `<` en `governance_client.py` debe hacerla fallar (rojo en la bitácora).

  El modelo y el código quedan con el mismo operador. `governance_client.py` no cambia.
- **C-8 · `crd_to_schema.py` duplicado (líneas 468 y 516).** Aquí **no** se copia otra vez: los esquemas de `tests/fixtures/crds/` se generan invocando el de `bias-monitoring/tests/fixtures/crds/`, y la bitácora anota la orden y la fuente de cada CRD.
- **C-9 · `render_env` sin los values de la unidad (líneas 466 y 512).** No se arregla U1; se rodea con P-2 y una prueba que compara los dos renders.
- **C-10 · `sslmode` en los charts (línea 236).** Solo la parte de U8: ver P-6. U3 y U4 no se tocan.

### Plan

- Pasos 19, 20, 21, 22 y 23: `[x]` con `(U08-T05)` y la nota de lo diferido, en el estilo de los Pasos 10, 11 y 18 (por ejemplo, «— firma, SBOM y escaneo diferidos por la demo (T1)»; «— sin el CronJob `case-retention` (P-12)»; «— solo `CoreWriteAttempt`; el resto, T2»; «— `retention.md` y el `conftest` de la firma diferidos»; «— k6 diferido (T3)»).
- Paso 25: `[x] (U08-T05)`.
- Paso 26: `[x] (U08-T05)` con «— cierre acotado a la demo».
- Paso 16: `[ ]` con «diferido por la demo (T5)».
- Paso 24: `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».

### Cierre acotado (Paso 26)

`aidlc-docs/construction/case-management/evidence/cierre-demo.md`, con el formato de `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md` y el de `bias-monitoring`:

- **Comprobado:** cada paso que entra (también los de U08-T01 a U08-T04, en una fila cada tarea), con su comando y su resultado; la memoria de kind con y sin U8 y la proyección; las cifras de CA-14 y CA-15.
- **Decisiones:** P-1 a P-7, con la opción que rigió y quién la decidió; lo que quedó «no comprobado» de NFR-U8-14.
- **Pendiente en U12** (lo que verifica U12 Paso 18, enmienda §8):
  - escenario 7 del Paso 24: el Job `rt5-demo-<runId>` con el `runId` de `prepare` dispara `CoreWriteAttempt` con `vectra_core_write_attempts_total` en 0 (enmienda §6 P-13: «La de U12 es la que cuenta»);
  - escenario 1: la suite de conectividad (`case-service` → scoring denegado; `case-worker` → scoring permitido; `case-worker` → registro y core denegados; el mock alcanza solo el JWKS);
  - escenario 5: PBT-U8-07 abreviado contra el registro real;
  - push de las dos imágenes y digests reales, en el mismo PR que los de `governance` y `scoring-explainability` (`docs/imagenes.md`);
  - que ESO materialice las dos llaves y que los cuatro `pg-role-case-*` existan en `vectra-app`;
  - que el hook de migración corra antes de que los `Deployment` queden `Ready`, y que `sslmode` (P-6) conecte de verdad con `case-db`;
  - que Prometheus cargue la `PrometheusRule` y raspe los tres `ServiceMonitor`: `vectra_cases_failclosed_persistent` visible para `FailClosedPersistente` (D1);
  - memoria real de `case-service` y `case-worker` con 2 000 decisiones, frente al request de kind de P-1;
  - el apagado real del worker en un `rollout restart` (P-4).
- **Diferido por la demo:** las seis filas de la lista y, sin identificador propio, cada uno con su destino:
  - el Paso 16 (CLI `case-retention`, PBT-U8-08 y la corrida de P-U8-07; T5) y, con él, la plantilla del CronJob, `retention.schedule` y `retention.timeZone` (P-12);
  - `mutmut` (Paso 8, T3) y el umbral de cobertura de `retention` (Paso 18);
  - firma, SBOM, escaneo y la prueba sobre el SBOM (Paso 19, T1);
  - las ocho alertas del Paso 21 que no entran, `CaseEvidenceDiscarded` (Paso 10), sus runbooks y las pruebas del nombre para `AuthDeniedBurst` y `PostgresVolumeUsageHigh` (T2);
  - `retention.md` y el `conftest` de la firma (Paso 22);
  - el script k6 y `k6 inspect` (Paso 23, T3);
  - los escenarios 2, 3, 4 y 6 y la carga del Paso 24 (enmienda §3 U8, fila 24).

**Fuera** (rechazar aunque se vea roto o tentador):

- **El CronJob `case-retention`:** su plantilla, `retention.schedule`, `retention.timeZone`, un value `retention.enabled` (P-12 lo descartó) y cualquier punto de entrada de retención en la imagen. **El Paso 16** entero.
- **Paso 24 completo:** guía, scripts y escenarios de kind; cualquier `kubectl`, `helm install`, `argocd` o sync; el push de las imágenes y los digests reales; un `runId` manual (AUTONOMIA-01; enmienda §8).
- Firma, SBOM, escaneo, `sign-image.yml` y `supply-chain.yml` (T1).
- Las alertas `CaseEvidencePending`, `CaseEvidenceAbandoned`, `CaseEvidenceDiscarded`, `CaseRetentionMissing`, `CaseRetentionOverdue`, `CaseApiUnavailable`, `CaseJobsOverdue`, `CaseFirstAttemptFailureHigh` (con su regla de grabación) y `ScoringRequestRejected`, y sus runbooks (T2). U08-T04 dejó escrita la expresión de la razón de primer intento en `services.md`: se queda allí.
- `docs/retention.md` y la regla de `conftest` de la firma (enmienda §3 U8, fila 22).
- `tests/load/cases.js` y `k6 inspect` (T3). `mutmut` (T3).
- `values-kind-demo.yaml` o 1 réplica (DD-3 eligió la b).
- Un `Server`, una `HTTPRoute` o una `AuthorizationPolicy` en el chart; un `Secret` o un `ExternalSecret` para la base; un `ConfigMap` para el fixture.
- **Cambios en U0, U2, U3, U4 y U7.** En U1, solo lo nombrado en «Estructura de destino». En particular, quedan fuera con su destino:
  - `ops_server.serve_ops_only`, bajar `GRACEFUL_SHUTDOWN` y el `-15` de `run_service` (líneas 543 y 561) → U0;
  - `http_method` en `authz.denied` (línea 544) → U0;
  - `httpx.Timeout` por fase (línea 524) → U0;
  - los puertos fijos 8080 y 8081 en las pruebas (líneas 551 y 560) → U0. Aquí solo se evita chocar (ver «Restricciones del entorno»);
  - `EXPECTED_WAVES` y `FIXED_WAVES` solapadas (línea 170), el pánico de `check-chart` (C-6), `STATIC_POLICIES` copiada (línea 472), `render_env` (C-9), `crd_to_schema.py` en `platform/` (C-8) y `test_traceability.py` sin archivos sin sufijo (línea 531) → U1;
  - el caso de PBT-10 de `core:read-credit` contra el realm de producción (línea 119) → U2.
- **De U8, fuera:**
  - las migraciones de U08-T01 y sus candidatas (líneas 445, 447 y 520);
  - `RECONCILER_LEASE` por fila (línea 522), el single-flight de `serving-config` (línea 548) y la decisión pendiente de un caso que vence (línea 549): cambian comportamiento;
  - el texto de INF-U8-06 («responde a los 10 s», línea 545) y el de INF-U8-04 (`/livez`): diseño;
  - PBT-U8-01 con la corrida real de retención (línea 546): depende del Paso 16;
  - el caso `late_after_retake` que no discrimina (línea 577; ronda 4, F-02): los otros dos casos sí discriminan;
  - las candidatas de U08-T02 sobre `decision`, `views` y `backoff` (líneas 485 y 487 a 490).
- Cambios de comportamiento en `vectra_case` y en `core_banking_mock`. Esta tarea no toca `src/`. Si el chart o las imágenes revelan un defecto del código de U08-T01 a U08-T04, **repórtalo** y no lo arregles aquí.
- Editar el texto de los diseños o del plan, salvo las casillas del plan.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/case-management-code-generation-plan.md`: §1, Pasos 19 a 26, §3, §4 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1.0, §1.1 y §1.3 (D3), §2, §3 U8, §6 (P-4, P-11, P-12 y P-13) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §3 U8, §5 (DD-3) y §6.
- `DECISIONES-LOOP.md` §6, §7, §8 y §9.
- `aidlc-docs/construction/case-management/`: `infrastructure-design/infrastructure-design.md` (INF-U8-01 a 08) y `deployment-architecture.md`; `nfr-design/nfr-design-patterns.md` (P-U8-06, 08 y 10); `nfr-requirements/nfr-requirements.md`.
- `aidlc-docs/construction/case-management/code/services.md` («Arranque y apagado», «Variables de entorno», «Arranque y apagado del worker», «`core-banking-mock`») y `code/database.md`.
- `aidlc-docs/construction/system-verification/infrastructure-design/infrastructure-design.md` (INF-U12-02: `probes.runId`) y el Paso 8 del plan de U12 (el oráculo de RT-5).
- `case-management/`: `Makefile`, `alembic.ini`, `migrations/env.py`, `src/vectra_case/` (`app.py`, `worker.py`, `config.py`, `metrics.py`, `governance_client.py`), `core_banking_mock/` (`app.py`, `auth.py`, `metrics.py`, `fixtures/credits.json`) y `tests/doubles/` (`mock_auth.py`, `scoring_double.py`, `registry_double.py`, `u8_support.py`, `worker_support.py`).
- `bitacoras/U08-T04.md`, `revisiones/U08-T04/` (ronda 2, F-04; ronda 4, F-01) y `tareas/U08-T04-worker-y-core-mock.md` («Fuera»).
- La misma tarea hecha en otras unidades: `tareas/U11-T03-despliegue-y-cierre.md`, `tareas/U07-T04-despliegue-y-cierre.md`, `tareas/U09-T04-despliegue-y-cierre.md` y `revisiones/U09-T04/` (F-01 a F-03).
- `scoring-explainability/`: los dos `Dockerfile`, `chart/` (dos servicios con HPA, `externalsecrets.yaml`, `servicemonitors.yaml`), `policies/conftest/`, `Makefile`, `docs/imagenes.md`, `tests/unit/test_chart.py` y `tests/integration/test_image.py`.
- `governance/chart/templates/`: `migration-job.yaml` (hook de sync, `PGUSER` y `PGPASSWORD`), `service.yaml` y `service-identity.yaml`. `governance/observability/` y `governance/runbooks/compensation-event-pending.md`: una alerta de la demo con su `promtool` y su runbook.
- `bias-monitoring/`: `Makefile` (`policy-chart`, `policy-chart-u1`), `tests/fixtures/crds/` y `docs/imagenes.md`.
- `platform/`: `network/flows.yaml`, `network/forbidden.yaml`, `network/generated/<env>/vectra-mock.yaml` y `vectra-app.yaml`, `policies/quotas/quotas.yaml` y `render.py`, `policies/kyverno/`, `policies/rego/`, `data/chart/values.yaml`, `restore-drill/cronjob.yaml` y `drill.py` (`verify-full` con `vectra-internal-ca`), `observability/rules/platform-rules.yaml`, `runbooks/_template.md`, `tools.env`, `charts.sh` y `Makefile`.
- `platform/tests/`: `integration.py` (`render_env` y `chart_renders`), `test_integration.py`, `test_kind_profile.py`, `test_platform.py`, `test_waves.py`, `test_traceability.py`, `test_runbooks.py` y `test_links.py`.
- `vectra-risk-gitops/`: `components.yaml`, `generate.py` (`value_files`), `envs/<env>/values.yaml` y `values/<env>/`.
- `contracts/openapi/case-service.yaml` y `core-banking-mock.yaml`; `contracts/python/vectra_common/src/vectra_common/ops_server.py`; `contracts/tools/forbidden_phrases.py`.
- `identity-edge/keycloak/realm/realm.kind.yaml` (clientes `case-service` y `case-worker`) y `platform/kind/vault_paths.py`.
- `CANDIDATAS.md`: las líneas citadas en «Candidatas que se atienden aquí» y en «Fuera».

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ninguno toca el clúster. Los renders van a `platform/.tools/integration/u8/`, **no a `/tmp`** (ver «Restricciones del entorno»); las órdenes usan `OUT=platform/.tools/integration/u8`. Tras cada criterio va lo que pasa **hoy** en `tarea/U08-T04` (`deb0a21`), que es lo que queda en `main` al fusionar el PR #148.

- [ ] **CA-1** — Paso 19: las dos imágenes.
  ```bash
  platform/.tools/bin/hadolint case-management/Dockerfile case-management/core_banking_mock/Dockerfile
  make -C case-management image image-mock
  for i in case-management core-banking-mock; do docker image inspect localhost:5001/vectra/$i:dev --format '{{.Config.User}} {{json .Config.Cmd}}'; done
  for i in case-management core-banking-mock; do docker run --rm --entrypoint sh localhost:5001/vectra/$i:dev -c '! pip list 2>/dev/null | grep -iE "^(pybreaker|circuitbreaker|aiobreaker|purgatory[a-z-]*|pytest|hypothesis|ruff|mypy|hatchling) " && echo OK'; done
  docker run --rm --entrypoint python localhost:5001/vectra/case-management:dev -c 'import vectra_case.app, vectra_case.worker, alembic; print("OK-entradas")'
  docker run --rm --entrypoint sh localhost:5001/vectra/case-management:dev -c 'test -s /app/alembic.ini && test -d /app/migrations/versions && echo OK-migraciones'
  docker run --rm --entrypoint python localhost:5001/vectra/core-banking-mock:dev -c 'from core_banking_mock.app import DEFAULT_FIXTURES, load_credits; print(len(load_credits(DEFAULT_FIXTURES)) > 0)'
  docker run --rm --entrypoint python localhost:5001/vectra/core-banking-mock:dev -c 'import vectra_case' ; echo "rc=$?"
  for f in case-management/Dockerfile case-management/core_banking_mock/Dockerfile; do grep -c '^FROM ' $f; grep -cE '^FROM .*@sha256:[0-9a-f]{64}' $f; done
  uv run lint-imports --config case-management/.importlinter
  test -s case-management/docs/imagenes.md && grep -c "mismo commit" case-management/docs/imagenes.md
  ```
  Esperado: `hadolint` en 0; `65532:65532` en las dos y el `Cmd` de cada una (el de `case-management` es el del servicio; el worker y la migración los fija el chart); `OK` dos veces; `OK-entradas`; `OK-migraciones`; `True`; `rc=1` (el mock no lleva `vectra_case`); los dos conteos de `FROM` iguales en cada archivo; el import-linter sin contratos rotos; al menos `1`. Si `hadolint` no está en `platform/.tools/bin` del worktree, ver «Restricciones del entorno».
  **Hoy falla:** no hay `Dockerfile` ni targets de imagen (`test -f case-management/Dockerfile` da 1). El import-linter ya pasa.

- [ ] **CA-2** — Paso 20: render, esquema y `conftest` del chart.
  ```bash
  OUT=platform/.tools/integration/u8
  for env in kind staging prod; do rm -rf $OUT/$env && uv run python platform/tests/integration.py --chart case-management/chart --namespace vectra-app --env $env --out $OUT/$env; done
  for env in kind staging prod; do platform/.tools/bin/kubeconform -strict -summary -schema-location default -schema-location 'case-management/tests/fixtures/crds/{{.ResourceKind}}.json' $OUT/$env/*.yaml; done
  for env in kind staging prod; do platform/.tools/bin/conftest test --policy case-management/policies/conftest $OUT/$env/*.yaml; done
  for env in kind staging prod; do grep -h "^kind:" $OUT/$env/*.yaml | sort | uniq -c; done
  uv run pytest case-management/tests/unit/test_chart.py -v
  ```
  Esperado: código 0 e `Invalid: 0` en los tres entornos. El inventario por entorno:
  - **prod:** 2 `Deployment`, 2 `Service`, 2 `HorizontalPodAutoscaler`, 2 `PodDisruptionBudget`, 3 `ServiceAccount` (`case-service`, `case-worker`, `migration-case`), 2 `ExternalSecret`, 2 `ServiceMonitor` y 1 `Job` (migración). Ningún recurso en `vectra-mock`, ninguna `PrometheusRule`, ningún `CronJob`;
  - **kind y staging:** lo de prod más, en `vectra-mock`, 1 `Deployment`, 1 `Service`, 1 `PodDisruptionBudget`, 1 `ServiceAccount` y 1 `ServiceMonitor` del mock, y 1 `PrometheusRule`. Sin `probes.runId`, ningún Job `rt5-demo`.

  `test_chart.py` tiene un caso por regla que falla con una mutación del render. Como mínimo:
  - HPA con mínimo ≠ 2, máximo ≠ 6, CPU ≠ 70 % o estabilización ≠ 60 / 300 s; un `Deployment` de `vectra-app` sin HPA; el mock sin `vectra.io/hpa-exempt` o con la justificación vacía;
  - sin PDB o con `minAvailable` ≠ 1; sin spread por zona; `replicas` ≠ 2; estrategia distinta de `maxSurge: 1` y `maxUnavailable: 0`;
  - `priorityClassName` ≠ `vectra-high` en `case-service` o `case-worker`, o ≠ `vectra-low` en la migración, el mock o el Job `rt5-demo`; sin `vectra.io/criticality`;
  - requests o limits distintos de INF-U8-04 en staging o prod; en kind, un request de memoria distinto del de P-1; `values-kind.yaml` con algo más que lo que P-1 y P-2 fijan;
  - `case-service` sin `preStop.sleep` de 5 s o con `terminationGracePeriodSeconds` < 20; `case-worker` con menos de 30, o con menos que `config.WORKER_TERMINATION_GRACE`; un `preStop` en `case-worker`;
  - liveness que no es `/healthz` en 8081 (por ejemplo `/livez`); readiness que no es `/readyz` en 8081; un `startupProbe`;
  - el `Service` de `case-worker` con el 8080; el del mock sin el 8080 o sin el 8081;
  - un Job sin la anotación del sidecar nativo; el de migración sin el hook de sync, con otra `ServiceAccount` o sin `vectra.io/workload: migration-case`;
  - un `CronJob` en el render; un `Server`, una `HTTPRoute` o una `AuthorizationPolicy`; un `Secret`;
  - un recurso del mock o la `PrometheusRule` con los values de prod;
  - imagen sin digest; sin `runAsNonRoot` o sin `readOnlyRootFilesystem`; los dos `Deployment` de `vectra-app` con imágenes distintas o con la misma orden (NFR-U8-10).

  **Hoy falla:** `chart/` solo tiene `templates/.gitkeep`; no hay `Chart.yaml`, y `policies/conftest/` y `tests/fixtures/` están vacíos.

- [ ] **CA-3** — Paso 20: variables, base, identidad y el Job `rt5-demo`.
  ```bash
  uv run pytest case-management/tests/unit/test_chart.py -k "env or dsn or identity or probes or rt5 or constants or kind_render" -v
  grep -nE "clientId: (case-service|case-worker)$" identity-edge/keycloak/realm/realm.kind.yaml
  uv run python -c "import sys; sys.path.insert(0, 'platform/kind'); import vault_paths as v; c = v.service_account_clients(); assert {'case-service', 'case-worker'} <= set(c); print('OK-boveda')"
  grep -nE "case_(app|worker|migrator): \[vectra-app\]" platform/data/chart/values.yaml
  OUT=platform/.tools/integration/u8
  rm -rf $OUT/rt5 && mkdir -p $OUT/rt5 && platform/.tools/bin/helm template case-management case-management/chart -n vectra-app -f vectra-risk-gitops/envs/kind/values.yaml -f case-management/chart/values-kind.yaml -f vectra-risk-gitops/values/kind/case-management.yaml --set probes.runId=20261112-0900 > $OUT/rt5/kind.yaml
  grep -c "name: rt5-demo-20261112-0900" $OUT/rt5/kind.yaml; ! grep -n "ttlSecondsAfterFinished" $OUT/rt5/kind.yaml
  platform/.tools/bin/conftest test --policy case-management/policies/conftest $OUT/rt5/kind.yaml
  ! platform/.tools/bin/helm template case-management case-management/chart -n vectra-app -f vectra-risk-gitops/envs/kind/values.yaml -f case-management/chart/values-kind.yaml --set probes.runId=manual > /dev/null 2>&1
  ```
  Esperado: código 0, dos líneas del realm, `OK-boveda`, tres líneas de `roleConsumers`, `1` en el conteo del Job, y la última orden confirma que un `runId` con otro formato no rinde. Las pruebas comprueban sobre el render de los tres entornos:
  - el conjunto de variables de cada contenedor es el de «Precisiones» y coincide con lo que leen `Settings.from_env`, `WorkerSettings.from_env`, `migrations/env.py` y U0. `CASE_CORE_URL` existe en kind y staging y **no** en prod; `CASE_CORE_ENABLED` y `CASE_ALLOW_TEST_SCENARIOS` valen `true` en kind y staging y `false` en prod;
  - `VECTRA_CLIENT_ID` vale `case-service` o `case-worker` según el proceso, y `VECTRA_CLIENT_KEY_PATH` apunta a un archivo del volumen del `ExternalSecret` de **ese** proceso, montado de solo lectura;
  - cada DSN va sin usuario ni clave, apunta a `case-db-rw.vectra-data.svc.cluster.local` y a la base `case`, y lleva el `sslmode` de P-6; `PGUSER` y `PGPASSWORD` salen del `pg-role-*` de su rol, y ningún proceso recibe el Secret de otro;
  - las URL de scoring, governance, registro y core apuntan al Service y al puerto de F15, F104, F16 y F17 de `flows.yaml`, leídos del archivo;
  - ninguna variable lleva el nombre de una constante pública de `vectra_case.config`;
  - las etiquetas y la `ServiceAccount` de cada pod son las de `flows.yaml`;
  - el Job `rt5-demo`: `ServiceAccount` `case-service`, `app.kubernetes.io/name: case-service`, sin `vectra.io/workload`, sin la llave ni variables de la base, `backoffLimit: 0`; el selector del `Service` y el del PDB de `case-service` **no** coinciden con sus etiquetas y **sí** con las del `Deployment`;
  - **`kind_render`:** los `Deployment` de U8 que ve `integration.render_env("kind")` (nombre, réplicas y request de memoria) son los mismos que rinde la orden de CA-2 para kind (P-2).

  Rojo de cada caso en la bitácora: quitar `CASE_SCORING_URL` del worker, cruzar los dos `pg-role-*`, montar la llave sin `readOnly`, poner `/livez`, añadir `vectra.io/workload: case-service` al Job, poner `LEASE` como variable.
  **Hoy falla:** no existe `test_chart.py` ni el chart. Las órdenes del realm, de la bóveda y de `roleConsumers` ya pasan.

- [ ] **CA-4** — Pasos 19 y 20: los cuatro contenedores reales arrancan con lo que pone el chart.
  ```bash
  uptime
  uv run pytest case-management/tests/integration/test_image.py -v
  ```
  Esperado: código 0. La prueba toma de **el render de kind** (CA-2 y CA-3) la orden, los argumentos y las variables de cada contenedor. Solo cambia: los hosts de las URL y del DSN por los de un PostgreSQL de Testcontainers y los dobles HTTP de `tests/doubles/`; el `sslmode`, si el PostgreSQL local no tiene TLS (y lo anota); la llave por una de prueba en la misma ruta; y `PGUSER` y `PGPASSWORD` por los de los roles locales. Cada contenedor corre con `docker run --read-only --user 65532:65532` y en este orden:
  1. **Migración** (la orden del Job): termina con 0; las tablas existen; la fila de `retention_settings` tiene los tres plazos de los values; una segunda corrida termina con 0 y no cambia `created_at`. Sin `RETENTION_UNDECIDED_YEARS`, termina distinto de 0 **antes** de tocar la base.
  2. **`case-service`**: `/healthz` y `/readyz` responden 200 en el puerto publicado del 8081; `/metrics` trae `vectra_cases_failclosed_persistent` y `vectra_case_jobs_overdue`; el 8080 responde 401 a `GET /v1/cases` sin token. `docker stop` con el plazo de gracia del chart: sale con 0 o 143, **nunca 137**, y la bitácora anota los segundos.
  3. **`case-worker`**: `/readyz` 200 en 8081 y **nada** escucha en 8080; `/metrics` trae `vectra_case_attempts_total` con sus series en 0. `docker stop` con el plazo de P-4: sale con **0** dentro del plazo. Sin `CASE_SCORING_URL`: no arranca.
  4. **`core-banking-mock`**: `/metrics` recién arrancado trae `vectra_core_write_attempts_total 0.0`; `GET /v1/credits/<id del fixture>` con un token del emisor doble (`tests/doubles/mock_auth.py`) responde 200, lo que prueba que el fixture está en la imagen y se lee con el sistema de archivos de solo lectura; `POST /v1/credits/<id>/status` responde 403 y la métrica pasa a 1.
  5. **Job `rt5-demo`** (la orden del render con `probes.runId`): contra un doble que responde 403 con la cabecera `l5d-proxy-error`, termina con 0 y su salida trae `403` y `l5d-proxy-error`; contra el mock real del punto 4 (sin proxy: 401), termina distinto de 0.

  Si Docker no está disponible, la prueba **falla**; no se salta. Ningún contenedor usa el 8080 ni el 8081 **del host** como puerto fijo: publica puertos libres, como `bias-monitoring/tests/integration/test_image.py`. Registra en la bitácora cada `docker run`, su salida, el tiempo de cada apagado y la memoria en reposo de `case-service` y `case-worker` (`docker stats --no-stream`).
  **Hoy falla:** no hay imágenes ni prueba.

- [ ] **CA-5** — Paso 20: admisión de U1 en los tres entornos.
  ```bash
  make -C case-management policy-chart-u1
  platform/.tools/bin/kyverno test platform/policies/kyverno
  ! grep -rn "PolicyException" platform/policies case-management/chart
  ! grep -nE "case-service|case-worker|core-banking-mock" platform/policies/kyverno/require-spread-and-pdb.yaml
  git diff --exit-code origin/main -- platform/policies platform/network
  ```
  Esperado: código 0, Kyverno con `fail: 0` y `conftest` de `platform/policies/rego` (incluido `--namespace hpa`, que admite la exención del mock) en 0, en kind, staging y prod. Ningún `PolicyException` y ninguna exclusión de U8 en `require-spread-and-pdb` (los dos `grep` no imprimen nada), y el `diff` vacío. `policy-chart-u1` rinde **un entorno por directorio** dentro de `platform/.tools/integration/u8/`, como `bias-monitoring/Makefile`: `make -C platform check-chart CHART=case-management/chart` entra en pánico con el PDB repetido entre entornos (C-6) y además borra `platform/.tools/integration/chart`. No la uses con `platform/.tools` enlazado al árbol principal.
  **Hoy falla** la primera orden (no hay target ni chart). La segunda ya pasa.

- [ ] **CA-6** — Paso 20: cuota, conexiones y flujos.
  ```bash
  uv run python platform/policies/quotas/render.py --check \
    && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -v \
    && uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -q \
    && for id in F04 F07 F10 F15 F16 F17 F40 F44 F50 F60 F104 F105; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done \
    && grep -nE "id: F15, from: \[case-worker\], to: \[scoring-service\], port: 8080" platform/network/flows.yaml \
    && grep -nE "id: F40, from: \[case-service, case-worker\]" platform/network/flows.yaml \
    && grep -nE "id: F104, from: \[case-worker, case-service\]" platform/network/flows.yaml \
    && grep -cE "id: X01, from: (scoring-service|explainability-service), to: core-banking-mock" platform/network/forbidden.yaml \
    && grep -n "_catch_all: core-mock-catch-all" platform/network/flows.yaml \
    && grep -n "U8: { requests: \[6.44, 5.3\], limits: \[29.9, 12.35\] }" platform/policies/quotas/quotas.yaml \
    && grep -n "U8: { requests: \[0.59, 0.32\], limits: \[2.93, 0.98\] }" platform/policies/quotas/quotas.yaml
  uv run pytest case-management/tests/unit/test_chart.py -k "quota or connections or flows or catch_all" -v
  ```
  Esperado: código 0, ninguna línea «falta» y `2` en el conteo de X01. Las pruebas de `test_chart.py`:
  - recalculan el aporte de U8 desde el render de staging y lo comparan con las dos líneas de `quotas.yaml`, con el término del CronJob aparte (INF-U8-05);
  - comprueban las conexiones contra `maxConnections` de `case-db` (NFR-U8-14);
  - leen `platform/network/generated/kind/vectra-mock.yaml` y comprueban que la `HTTPRoute` `core-mock-catch-all` existe **sin** `AuthorizationPolicy`, que la de `GET /v1/credits/{id}` solo admite a `case-service`, y que el `route_name` de la alerta es ese nombre.

  **Hoy:** la primera orden completa ya pasa (los `grep` se comprobaron al redactar). Falla la segunda: no existe `test_chart.py`.

- [ ] **CA-7** — Paso 20: los values por entorno.
  ```bash
  for env in kind staging prod; do test -s vectra-risk-gitops/values/$env/case-management.yaml || echo "falta $env"; done
  platform/.tools/bin/conftest test --policy case-management/policies/conftest --namespace values.prod vectra-risk-gitops/values/prod/case-management.yaml
  platform/.tools/bin/conftest test --policy case-management/policies/conftest --namespace values.staging vectra-risk-gitops/values/staging/case-management.yaml
  ! grep -rn "runId" vectra-risk-gitops/values/*/case-management.yaml case-management/chart/values.yaml case-management/chart/values-kind.yaml
  ! grep -rnE "schedule|timeZone" case-management/chart/values.yaml
  uv run pytest case-management/tests/unit/test_chart.py -k "values_prod or values_staging or run_id or retention_values" -v
  ```
  Esperado: código 0 y ninguna línea «falta». Las reglas sobre **los archivos** de values van en los paquetes Rego `values.prod` y `values.staging`, aparte de las del render (paquete `main`). Las pruebas, con copias mutadas de esos archivos:
  - `probes.runId` en el de staging o en el de prod → `conftest` falla;
  - en el de prod, `core.enabled: true`, `coreMock.enabled: true` o `allowTestScenarios: true`, o cualquiera de los tres ausente → falla;
  - con `probes.runId` y los values de staging o de prod, el Job `rt5-demo` no aparece en el render; sin `probes.runId` tampoco aparece en kind;
  - con `retention.undecided_years` ausente, el chart no rinde; cambiar el valor cambia `RETENTION_UNDECIDED_YEARS` del Job de migración.

  **Hoy falla:** los tres archivos no existen.

- [ ] **CA-8** — Paso 21: `CoreWriteAttempt`, su runbook y la prueba del nombre.
  ```bash
  mkdir -p platform/.tools/tmp && export TMPDIR=$PWD/platform/.tools/tmp
  make -C case-management rules
  platform/.tools/bin/promtool check rules case-management/observability/rules/case-management.rules.yaml
  platform/.tools/bin/promtool test rules case-management/observability/rules/tests/*.yaml
  uv run python -c "import yaml; d = yaml.safe_load(open('case-management/observability/rules/case-management.rules.yaml')); r = [x for g in d['groups'] for x in g['rules']]; print(sorted(x.get('alert', 'RECORD') for x in r))"
  uv run pytest case-management/tests/unit/test_rules.py -v
  uv run python platform/tests/test_runbooks.py --root case-management
  ls case-management/observability/runbooks/*.md
  grep -ciE "evidencia esperada" case-management/observability/runbooks/core-write-attempt.md; grep -c "offset 5m" case-management/observability/runbooks/core-write-attempt.md
  uv run python contracts/tools/forbidden_phrases.py case-management/observability/runbooks/*.md case-management/docs/*.md
  ! grep -rn "CoreWriteAttempt" platform/.tools/integration/u8/prod/
  git status --short case-management/observability/
  ```
  Esperado: código 0; `SUCCESS` en `promtool`; `['CoreWriteAttempt']` (una alerta, ninguna regla de grabación); un solo runbook, `core-write-attempt.md`; al menos `1` en los dos conteos; `forbidden_phrases.py` no imprime nada; el render de prod no nombra la alerta; y el `git status` final vacío (regenerar no cambia nada). Hay un caso de `promtool` con nombre por cada uno de los seis de «Precisiones», y la bitácora lleva la tabla afirmación → archivo y caso. `test_rules.py` comprueba:
  - la expresión es la de INF-U8-03 (las dos series, la resta con `offset 5m` y `or vector(0)`, sin `increase()` sobre la serie de Linkerd);
  - el `spec` es idéntico en kind y en staging y es el archivo versionado;
  - `severity` y `runbook_url` presentes, y el archivo del runbook existe;
  - **los nombres:** `vectra_cases_failclosed_persistent` (de la regla de U1) está en `vectra_case.metrics`, y `vectra_core_write_attempts_total` en `core_banking_mock.metrics`.

  Rojo en la bitácora: `increase()` sobre la serie de Linkerd (el caso «nace en 1» deja de disparar); sin el filtro de `route_name` (el caso del otro `route_name` dispara); la métrica renombrada en `metrics.py` (la prueba del nombre falla).
  **Hoy falla:** `observability/rules/tests/` y `observability/runbooks/` solo tienen `.gitkeep`; `test_runbooks.py --root case-management` no encuentra alertas.

- [ ] **CA-9** — Paso 22: documentación y OpenAPI.
  ```bash
  uv run python case-management/tools/check_openapi.py
  uv run pytest case-management/tests/unit/test_openapi.py -v
  test -s case-management/docs/api.md
  uv run python platform/tests/test_links.py --root case-management
  for s in "/v1/intake/applications" "/v1/cases/{id}/decision" "/v1/cases/{id}/explanation-views" "/v1/cases/{id}/retry" "/v1/credits/{id}" "Idempotency-Key" "no_integrado" "decision_already_recorded" "CASE_DB_DSN"; do grep -qF "$s" case-management/docs/api.md || echo "falta $s"; done
  test ! -e case-management/docs/retention.md
  ```
  Esperado: código 0 y ninguna línea «falta». `test_openapi.py` comprueba que `check_openapi.py` termina en 1, sin escribir nada, cuando: el archivo exportado se edita a mano; a la app le falta una ruta del contrato; la app sirve una ruta que el contrato no tiene. Con P-7 = (a), los dos archivos exportados existen y `check_openapi.py` los compara con `build_app().openapi()` de cada app y con `contracts/openapi/`.
  **Hoy falla:** `tools/` y `docs/` solo tienen `.gitkeep`.

- [ ] **CA-10** — Paso 23: Application.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/case-management.yaml; done \
    && platform/.tools/bin/kyverno test platform/policies/kyverno \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/case-management.yaml \
    && ! grep -rn "automated" vectra-risk-gitops/apps/*/case-management.yaml
  for env in kind staging prod; do grep -c "values/$env/case-management.yaml" vectra-risk-gitops/apps/$env/case-management.yaml; done
  grep -c "values-kind.yaml" vectra-risk-gitops/apps/kind/case-management.yaml vectra-risk-gitops/apps/staging/case-management.yaml vectra-risk-gitops/apps/prod/case-management.yaml
  ls vectra-risk-gitops/apps/prod/ | grep -c "core-banking-mock"
  uv run pytest platform/tests/test_platform.py -k "every_component_is_in_its_wave or gitops_manifests_match_components" -v
  git diff origin/main -- platform/tests/test_platform.py | grep -E "^[-+]" | grep -vcE "^(\+\+\+|---) "
  ```
  Esperado: código 0. Una Application por entorno, con wave `'5'`, sin `syncPolicy.automated` y con su `values/<env>/case-management.yaml` (`1` en cada entorno). `values-kind.yaml`: `1` en kind y `0` en staging y prod. `0` Applications del mock en prod. El `diff` de `test_platform.py` tiene `2` líneas: la de `EXPECTED_WAVES[5]`, quitada y puesta.
  **Hoy:** `generate.py --check` y `test_waves.py` pasan, pero no existe `apps/<env>/case-management.yaml` y los `grep` fallan.

- [ ] **CA-11** — Paso 23: trazabilidad (P-4 de la enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit case-management --all \
    && for n in 01 02 03 04 05 06 07 08 09 10 11 12 13 13b 14 15 16 17 18 19 21 22; do git grep -qiE "BR-U8-$n([^0-9b]|$)" -- case-management/tests case-management/core_banking_mock/tests case-management/observability/rules/tests || echo "BR-U8-$n sin prueba"; done
  uv run python platform/tests/test_traceability.py --all | grep -c "U8-"
  grep -n "^## Diferido por la demo" -A12 aidlc-docs/construction/case-management/evidence/cierre-demo.md
  grep -rnE "(INF-U8-08|NFR-U8-46|NFR-U8-47|NFR-U8-51|P-U8-07)([^0-9]|$)" case-management/; echo "rc=$?"
  ```
  Esperado: código 0 y ninguna línea «sin prueba» (BR-U8-20 no está en el bucle: va en la lista); `0` en el conteo de `--all` (y `--all`, sin `--unit`, cumple la regla «sin fallos nuevos» de `DECISIONES-LOOP.md` §6 frente a la base); la lista tiene exactamente seis filas (INF-U8-08, NFR-U8-46, NFR-U8-47, NFR-U8-51, P-U8-07 y BR-U8-20); la última orden no imprime nada y da `rc=1`.
  **Hoy falla:** 14 identificadores sin trazabilidad (INF-U8-05 y 08; NFR-U8-10, 12, 14, 20, 34, 40, 42, 44, 46, 47 y 51; P-U8-07) y 6 BR sin prueba (BR-U8-03, 04, 13b, 14, 17 y 20). No existe `evidence/cierre-demo.md`.

- [ ] **CA-12** — Presupuesto de memoria de kind.
  ```bash
  uptime
  uv run python -c "import sys; sys.path.insert(0, 'platform/tests'); import test_kind_profile as t; print(round(t.requested_gib([*t.declared_inference_services(), *t.PEAK_INFERENCE_SERVICES]), 4), t.BUDGET_GIB)"
  uv run pytest platform/tests/test_kind_profile.py -v
  git diff origin/main -- platform/tests/test_kind_profile.py
  grep -nE "Proyecci[oó]n" aidlc-docs/construction/case-management/evidence/cierre-demo.md
  ```
  Esperado: la segunda orden se corre **dos veces**, antes y después de agregar la Application, y las dos cifras quedan en la bitácora. La diferencia es el aporte de U8: **0,7422 GiB** con P-1 = (b) o 1,2422 GiB con (a). Las pruebas pasan. El `diff` solo cambia `BUDGET_GIB` y su comentario, con la cifra medida redondeada hacia arriba a 0,1 GiB y la cita de `DECISIONES-LOOP.md` §7. El cierre lleva la proyección con U10 (y con U11, si no está en `main`). Si la cifra no cuadra o la proyección llega a 13,0 GiB, es una **detención** (sección «Presupuesto»), no un ROJO del codificador.
  **Hoy:** la orden debe imprimir `10.3438 10.4` (la cifra del comentario de `test_kind_profile.py` y del cierre de U7; no se volvió a correr al redactar, porque el worktree de preparación no tiene `platform/.charts`). Con la Application agregada y sin tocar el tope, `test_the_profile_requests_fit_the_budget` falla: es el rojo esperado.

- [ ] **CA-13** — Candidata C-7: la frontera del TTL.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest case-management/tests/property/test_case_machine.py -q -p no:cacheprovider
  uv run pytest case-management/tests/integration/test_worker_clients.py -k "ttl" -v
  git diff origin/main --stat -- case-management/src
  git diff origin/main -- CANDIDATAS.md | grep -c "Atendida en U08-T05"
  ```
  Esperado: código 0; el `diff` de `case-management/src` **vacío**; al menos `4` en el conteo (C-1, C-4, C-7 y C-10; las demás se atienden sin cerrarse). La bitácora lleva el rojo: con `<=` cambiado a `<` en `governance_client.py` (línea 77), la prueba `ttl` falla y PBT-U8-01 no. La prueba de la frontera va en `tests/integration/test_worker_clients.py` y lleva `ttl` en el nombre.
  **Hoy falla:** ninguna prueba ejerce los 5 s exactos (`revisiones/U08-T04/ronda-4.md`, F-01: la mutación sobrevive).

- [ ] **CA-14** — Pasos 25 y 26: N/A y cierre.
  ```bash
  test ! -d case-management/frontend
  uptime; time make -C case-management check
  uptime; time make -C platform check
  grep -nE "^## (Comprobado|Decisiones|Pendiente en U12|Diferido por la demo)" aidlc-docs/construction/case-management/evidence/cierre-demo.md
  grep -n "^check:" case-management/Makefile
  ```
  Esperado: código 0 y las cuatro secciones. El `check` de U8 corre, en orden: `lint` (ruff, mypy, import-linter), las pruebas con el perfil `ci` y la cobertura (≥ 95 % en `vectra_case` y 100 % en los ocho módulos), `image` e `image-mock`, la prueba de los contenedores, el chart (CA-2, CA-3 y CA-7), la admisión (CA-5), cuota y flujos (CA-6), `rules` (deriva del archivo versionado y `promtool`), runbooks, `check_openapi.py`, enlaces y trazabilidad. **Falla** si falta una herramienta (`promtool`, `helm`, `kubeconform`, `conftest`, `kyverno`, `hadolint`, Docker): no se salta con rc 0 (candidata F-02 de U04-T07; no copies el `rules` de `governance/Makefile`, que lo omite). `make -C platform check` va porque el diff toca `test_platform.py`, `test_kind_profile.py` y `components.yaml` (RL-4). Registra la duración y el `uptime` de cada uno.
  **Hoy:** `make -C case-management check` pasa con `lint` y `test`. Falla el `grep` del cierre.

- [ ] **CA-15** — RL-4: el `make check` de todas las unidades, una vez al cerrar U8.
  ```bash
  for u in contracts platform identity-edge decision-registry governance reference-model model-serving scoring-explainability bias-monitoring case-management console product-metrics; do uptime; make -C $u check || echo "FALLA $u"; done
  ```
  Esperado: ninguna línea «FALLA». Las unidades corren **en serie**: varias usan los puertos 8080 y 8081 del host, y con la máquina cargada las pruebas con límite de tiempo fallan. Si una unidad ajena falla y el fallo también ocurre en `origin/main`, regístralo con la salida y su causa: no es de esta tarea. El cierre cita las cifras (lección de U09-T04, F-02: el cierre sin la evidencia fue un NARANJA).

- [ ] **CA-16** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/case-management-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso (16|19|2[0-6]) "
  git diff origin/main -- aidlc-docs/construction/plans/case-management-code-generation-plan.md | grep -E "^[-+]" | grep -vcE "^(\+\+\+|---) "
  ```
  Esperado: Pasos 19, 20, 21, 22, 23, 25 y 26 en `[x]` con `(U08-T05)` y su nota; Paso 16 en `[ ]` con «diferido por la demo (T5)»; Paso 24 en `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». El segundo conteo es `18`: nueve líneas quitadas y nueve puestas, ningún otro cambio en el texto del plan.
  **Hoy:** los nueve pasos están en `[ ]` sin nota.

---

## Plan de pruebas

Se escriben en esta tarea: `tests/unit/test_chart.py`, `test_rules.py` y `test_openapi.py`; `tests/integration/test_image.py`; los casos de `promtool` de `observability/rules/tests/`; y la prueba de C-7.

**Rojo primero**, con cada par falla-pasa en `bitacoras/U08-T05.md`. El verde de una propiedad va siempre con el perfil `ci`.

- `replicas: 1` en `case-worker`, o el mock sin `vectra.io/hpa-exempt` (`conftest` o el `rego` de U1 falla);
- HPA de 1 a 6; `terminationGracePeriodSeconds: 10` en `case-service`; `case-service` sin `preStop`;
- `/livez` como liveness;
- un 8080 en el `Service` de `case-worker`;
- `CASE_SCORING_URL` fuera del `Deployment` del worker (CA-3 falla, y en CA-4 el contenedor no arranca);
- `pg-role-case-app` en el worker (CA-3 falla);
- `LEASE` o `SCORING_TIMEOUT` como variable de entorno;
- el fixture copiado a otra ruta en el `Dockerfile` del mock (CA-1 y CA-4 fallan);
- `alembic.ini` fuera de la imagen (CA-1 falla y la migración de CA-4 no arranca);
- `pybreaker` en las dependencias de la imagen (la orden de CA-1 falla);
- `FROM python:3.12-slim` sin digest (el conteo de CA-1 no cuadra);
- `coreMock.enabled: true` en `values/prod/case-management.yaml` (`conftest` falla, y el render de prod trae el mock);
- `probes.runId` en `values/staging/case-management.yaml` (`conftest` falla);
- el Job `rt5-demo` con `vectra.io/workload: case-service`, o con `ttlSecondsAfterFinished`;
- el Job que termina con 0 ante un 401 (el punto 5 de CA-4 falla);
- un `CronJob` en el render;
- `increase()` sobre la serie de Linkerd; la alerta sin el filtro de `route_name`; una segunda alerta en la `PrometheusRule`;
- `vectra_cases_failclosed_persistent` renombrada en `metrics.py`;
- un `runbook_url` hacia un archivo que no existe (`test_runbooks.py` falla);
- una ruta quitada del OpenAPI exportado (`check_openapi.py` termina en 1);
- `syncPolicy.automated` en `apps/kind/case-management.yaml` (Kyverno falla);
- `wave: 4` en `components.yaml` (`test_waves.py` falla);
- `NFR-U8-44` en la lista de diferidos, y `NFR-U8-46` citado en `docs/api.md` (`test_traceability.py` falla las dos veces);
- `<=` → `<` en el TTL de `serving-config` (C-7).

---

## Preguntas abiertas

**P-1 necesita la decisión del usuario antes de despachar.** En las demás, si nadie responde, rige la recomendación.

- **P-1 · Request de memoria de `case-service` y `case-worker` en kind.** INF-U8-04 fija 256 MiB por réplica («los valores son iniciales y se ajustan con la prueba de carga de U12») y `deployment-architecture.md` dice que kind es como staging con 2 réplicas. La prueba de carga está diferida (T3) y la máquina tiene 14 GiB.
  - (a) 256 MiB también en kind, la letra del diseño: U8 suma 1,2422 GiB y la proyección con U10 y U11 queda en ≈ 12,5 GiB.
  - (b) **128 MiB solo en kind** para los dos (recomendada), en `chart/values-kind.yaml`: U8 suma 0,7422 GiB y la proyección queda en ≈ 12,0 GiB. Mismo patrón que la opción (c) de `DECISIONES-LOOP.md` §7 para U6 y que P-1 (b) de U11-T03: solo el request, sin tocar réplicas, HPA, PDB ni limits (512 MiB), y staging y prod siguen en el diseño. El mock ya pide 64 MiB y no cambia. La memoria real se anota en CA-4 y se comprueba en U12.
  - (c) Otra cifra que el usuario indique.

  Es una desviación del diseño para un entorno, como las de U6 y U11: por eso la decide el usuario. Un request más bajo que el uso real no rompe el pod (el limit sigue en 512 MiB), pero deja al planificador contar menos memoria de la que se usa.

- **P-2 · Dónde van los values de kind para que `render_env` los vea.** El plan pone los values por entorno en `vectra-risk-gitops/values/<env>/case-management.yaml`, y `generate.py` los pasa a Argo CD. Pero `platform/tests/integration.py` `render_env` **no** los pasa (C-9): solo `envs/<env>/values.yaml` y `kind_values`. Si `coreMock.enabled: true` y el request de kind van solo allí, `test_kind_profile.py` no cuenta el mock ni el override.
  - (a) **Defaults de producción en `chart/values.yaml`; `chart/values-kind.yaml` por `kind_values` con lo que las pruebas de U1 deben ver** (recomendada): `core.enabled: true`, `coreMock.enabled: true` y el request de P-1. `values/kind/case-management.yaml` lleva el resto (`allowTestScenarios: true`; después, los digests y `probes.runId`). Una prueba compara los dos renders de kind (CA-3, `kind_render`). Costo: kind tiene dos archivos, y el `render_env("staging")` de U1 no ve el mock (el `--chart` de la unidad sí).
  - (b) Todo en `values/kind/case-management.yaml`, como dice el plan, y `render_env` pasa los values de la unidad. Es el arreglo correcto, pero cambia una herramienta de U1 que usan todas las unidades.
  - (c) Todo en `values/kind/case-management.yaml` sin tocar U1: el presupuesto de kind cuenta de menos (168 MiB del mock y el override). No se recomienda.

- **P-3 · El mock: ¿una Application o dos?** El Paso 20 rinde el mock dentro del chart «solo con `coreMock.enabled = true`» y §1 tiene un solo `chart/`. El Paso 23 pide «la del mock con `envs: [kind, staging]`», una segunda entrada en `components.yaml`.
  - (a) **Una sola Application, `case-management`** (recomendada): el chart pone el namespace `vectra-mock` en cada recurso del mock, como `governance` con `vectra-staging` y `model-serving` con su predictor de staging. «Solo kind y staging» lo da `coreMock.enabled`, que la regla de `conftest` fija en prod. Coincide con `FIXED_WAVES` (solo `case-management`) y con U12, que sincroniza «tres Applications», una de ellas `case-management`.
  - (b) Dos entradas con el mismo `path`. La segunda necesita un value nuevo que apague la parte de casos, que INF-U8-07 no tiene.
  - (c) Un chart aparte para el mock. §1 no lo tiene, y `coreMock.enabled` dejaría de gobernar el despliegue.

  Con (a), la frase del Paso 23 sobre la entrada del mock no se cumple a la letra: el codificador la deja como candidata de corrección del plan.

- **P-4 · Plazos de gracia frente al apagado real** (C-1 y C-2).
  - **`case-worker`.** El plan e INF-U8-06 dicen `terminationGracePeriodSeconds: 30`; `services.md` y la revisión de U08-T04 (ronda 2) dan ≈ 34 s de peor caso.
    - (a) **40 s en el chart** (recomendada): cumple la aceptación (`≥ 30`) y cubre el peor caso; `config.WORKER_TERMINATION_GRACE` (30 s) se queda como mínimo, y la prueba exige `chart ≥ config`. La cuota no cambia.
    - (b) 30 s, la letra del plan: en el peor caso el kubelet mata el proceso 4 s antes; lo no terminado se retoma al vencer el arrendamiento (BR-U8-07). Sin pérdida, pero el apagado deja de ser «ordenado».
    - (c) Bajar `GRACEFUL_SHUTDOWN` en U0 o apagar las sondas en paralelo. Cambia U0 o `src/`: fuera de esta tarea.
  - **`case-service`.** El plan dice 20 s; un lote del reconciliador puede durar hasta 125 s (`RECONCILER_LEASE`).
    - (a) **20 s, como el plan** (recomendada): con el registro sano un lote dura milisegundos; un lote cortado deja las filas arrendadas 125 s y el reconciliador las reenvía con la misma llave (reenvío idempotente, sin pérdida). `services.md` y `docs/api.md` lo dicen así.
    - (b) Subirlo a ≈ 140 s. Alarga cada rollout sin evitar ninguna pérdida.

- **P-5 · La «prueba sobre el SBOM» del Paso 19.** La fila 19 de la enmienda dice «T1, más la prueba sobre el SBOM». T1 difiere el SBOM, así que no hay sobre qué correr la prueba.
  - (a) **Se difiere con T1 y la misma comprobación se hace sin SBOM** (recomendada): `pip list` dentro de las dos imágenes (CA-1) y el contrato de import-linter que ya existe. Es la lectura de la fila gemela de U6 («T1, más la prueba sobre el SBOM (la cubre import-linter)») y lo que hicieron U07-T04 y U09-T04.
  - (b) La prueba entra: se genera un SBOM local con `syft` solo para ella. `syft` no está en `platform/tools.env`, y T1 difiere el SBOM.

- **P-6 · `sslmode` de los DSN.** El Paso 3 y NFR-U8-40 piden `sslmode=verify-full`. Los charts de U3 y U4 usan `require` porque no montan la CA (`CANDIDATAS.md`, línea 236).
  - (a) **`verify-full` con la CA interna** (recomendada): el chart monta el `ConfigMap` `vectra-internal-ca` y el DSN lleva `sslrootcert`, como `platform/restore-drill/cronjob.yaml` (líneas 44 a 48) y `drill.py`. El certificado de `case-db` es `postgres-server-tls`, de esa CA. Que el nombre del certificado cubra `case-db-rw.vectra-data.svc.cluster.local` se comprueba en U12; va en «Pendiente en U12».
  - (b) `require`, como U3 y U4, con la candidata abierta. NFR-U8-40 quedaría trazado a medias.

- **P-7 · El «OpenAPI versionado» del Paso 22.** El plan pide «el OpenAPI exportado de `case-service` y del mock» y que `check_openapi.py` compare «el OpenAPI versionado» con el de la app. El contrato de U0 ya está en `contracts/openapi/`.
  - (a) **Exportado en `case-management/docs/openapi/` y comparado en los dos sentidos** (recomendada): `check_openapi.py` falla si el exportado difiere de `build_app().openapi()` y si las rutas (método y plantilla) difieren de `contracts/openapi/<servicio>.yaml`. `--write` lo regenera.
  - (b) Sin exportar: solo se compara la app con `contracts/openapi/`. No cumple «el OpenAPI exportado».

---

## Restricciones del entorno

- **`/tmp` es un tmpfs con cuota y está casi lleno.** No copies el repositorio ni corras `npm ci` allí. Los renders van a `platform/.tools/integration/u8/`. `promtool test rules` escribe en `TMPDIR`: usa `export TMPDIR=$PWD/platform/.tools/tmp` (CA-8). Lo mismo para cualquier `tempfile` grande de las pruebas.
- **Máquina compartida y cargada** (hasta 3 codificadores, RL-5). Anota `uptime` junto a cada medida de tiempo o de memoria. Una prueba con límite de tiempo que falla con carga alta se repite en frío antes de darla por rota, y se anotan las dos corridas.
- **Puertos 8080 y 8081 fijos.** `run_service` de U0 y `vectra_case.worker` abren esos puertos en el host durante `test_service_shutdown.py` y `test_worker_shutdown.py`, y las suites de U9, U10 y U11 hacen lo mismo. Corre las suites **en serie** y no lances dos `make check` a la vez. Los contenedores de CA-4 publican puertos libres.
- **`platform/.tools` y `platform/.charts` no están versionados.** En un worktree nuevo, `make -C platform check` y las órdenes con `platform/.tools/bin/` fallan. **No enlaces esos directorios enteros al árbol principal**: en U11-T03, un `make -C platform check-chart` corrido en un worktree con el enlace borró `platform/.tools/integration/chart` del árbol principal. Crea `platform/.tools/` real en el worktree y enlaza o copia **solo** `platform/.tools/bin`; `integration/` y `tmp/` son del worktree. Compara las versiones con `platform/tools.env`. Regístralo en la bitácora.
- **Charts de U1.** `platform/.charts` se llena con `platform/charts.sh` (`make -C platform charts`), que baja también los charts OCI (`envoy-gateway`, `kserve*`). Sin ellos `render_env` no rinde los charts upstream (CA-12 no corre) y fallan 33 pruebas de `platform/network/tests/test_edge_selectors.py` (`CANDIDATAS.md`, línea 291). O cópialo del árbol principal (36 MB), sin enlazarlo.
- **Docker** está disponible para construir y correr las imágenes y para Testcontainers.
- **Otros codificadores en paralelo** (U10 y U11): no toques sus directorios. Si otra tarea toca a la vez `components.yaml`, `test_kind_profile.py`, `EXPECTED_WAVES` o los digests de ejemplo, el orquestador resuelve el conflicto al integrar; tú partes de la base de tu rama.

---

## Notas

- **Orden sugerido**, para que lo que sostiene las demos quede primero: imágenes (Paso 19) → chart de `case-service`, `case-worker` y migración → contenedores reales (CA-4) → mock, Job `rt5-demo` y `CoreWriteAttempt` (D3) → values por entorno y `conftest` → Application y memoria de kind → OpenAPI y `api.md` → C-7 → trazabilidad y cierre.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `case-management/`; `test_runbooks.py` tampoco mira dentro de `tests/`.
- **Enlaces:** `test_links.py` lee como enlace cualquier corchete cerrado seguido de un paréntesis fuera de un bloque de código. Cuidado con los patrones de `grep` en los Markdown nuevos.
- Archivos que se modifican en su sitio:
  - en `case-management/`: `Makefile`, `tests/` (las citas de NFR-U8-42 y de las BR, y C-7) y `chart/`. **Nada de `src/`, `core_banking_mock/src/` ni `migrations/`**;
  - `vectra-risk-gitops/components.yaml` y lo generado;
  - `platform/tests/test_platform.py` (solo `EXPECTED_WAVES[5]`) y `platform/tests/test_kind_profile.py` (solo `BUDGET_GIB`);
  - `aidlc-docs/construction/case-management/code/services.md` (P-4), el plan (casillas) y `CANDIDATAS.md`.
- Archivos nuevos: los de «Estructura de destino», los tres `values/<env>/case-management.yaml` y `aidlc-docs/construction/case-management/evidence/cierre-demo.md`.
- **Candidatas nuevas que la tarea debe dejar en `CANDIDATAS.md`:** la frase del Paso 23 sobre la Application del mock (P-3); `terminationGracePeriodSeconds: 30` del plan y de INF-U8-06 frente a los 40 s del chart (P-4); `deployment-architecture.md`, «kind usa 2 réplicas fijas», frente al HPA en los tres entornos; el `sslmode` de U3 y U4 si P-6 = (a) funciona (el mismo montaje les sirve); y lo que CA-4 revele del código de salida de `case-service` tras `SIGTERM` dentro de un contenedor.
- **Bitácora:** `bitacoras/U08-T05.md`, con:
  - los pares falla-pasa;
  - la tabla afirmación del Paso 21 → caso de `promtool`;
  - la lista de diferidos razonada y la justificación de cada identificador trazado;
  - la fuente de los CRD de fixture;
  - cada `docker run` de CA-4, su salida, el tiempo de cada apagado y la memoria en reposo;
  - la memoria de kind (dos mediciones y proyección);
  - la decisión de P-1 a P-7;
  - la duración de cada `make check` con su `uptime`.
