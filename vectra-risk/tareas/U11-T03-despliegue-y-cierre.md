# U11-T03 — Imagen, chart, reglas, dashboard, Application, documentación y cierre acotado de `product-metrics`

**Unidad:** U11 `product-metrics`
**Historias que implementa:** US-503 (North Star: su panel en `product.json`, Paso 13), US-504 (métrica de ruido con alerta: `RuidoExplicacion` con `promtool`, Paso 12, y su panel, Paso 13) y US-505 (métricas operativas y de producto: reglas de respuesta completa y de desincronía, Paso 12, y sus paneles, Paso 13), según la trazabilidad del plan (§3). Los Pasos 10, 11, 15, 17 y 18 no tienen historia propia: empaquetan, despliegan por GitOps y cierran lo que implementan los Pasos 1 a 9.
**Depende de:**
- **U11-T02 fusionada en `main`** (PR #145, `28ee5ae`): `scheduler`, `collector` (con `PRODUCT_SERIES`, `OPERATION_SERIES` y `TARGET_METRICS`), `main` y `aidlc-docs/construction/product-metrics/code/process.md`, que deja escrito el entorno y el arranque que esta tarea necesita;
- en `main`, como contratos:
  - U0: `vectra_contracts.catalog.FAIL_CLOSED_CAUSES_BY_CATEGORY` y `vectra_common.ops_server` (`/metrics`, `/healthz`, `/readyz`);
  - U1: F28, F50 y F60 en `flows.yaml`, los tres casos `U11` de `forbidden.yaml`, el aporte `U11` de `quotas.yaml`, los casos `product-metrics` y `product-metrics-no-exempt` de `kyverno-test.yaml`, el `Server` `metrics-8081` generado, el sidecar de dashboards (`vectra.io/dashboard`, `grafana_folder`), `folder-permissions.yaml` con `Vectra / Producto` y `operacion.json`;
  - U2: cliente `product-metrics` del realm (solo `registry:read:metrics`) e `identity/clients/product-metrics` en la bóveda de kind;
  - U3: Service `decision-registry-service` en 8080 (F28);
  - U7: `vectra_recommendations_total{outcome}` y `vectra_scoring_failclosed_total{cause}` (`scoring-explainability/scoring/src/scoring/metrics.py`).

Sin clúster (AUTONOMIA-01). Todo se verifica con `helm template`, `kubeconform`, `conftest`, `promtool`, Docker local contra dobles y las pruebas de `platform/`. **Nada de `kubectl apply`, `helm install`, `argocd` ni sync.**
**Rama:** `tarea/U11-T03`, desde `origin/main`.

Bloque E del plan de U11 (`aidlc-docs/construction/plans/product-metrics-code-generation-plan.md`) más el cierre: la tarea «E+cierre (10–13, 15, 17, 18)» de `aidlc-docs/construction/plans/demo-recorte-funcional.md` §8, la tercera y última de U11. La enmienda rige donde difiera del alcance (`demo-kind-alcance.md`):

| Paso | Estado | Entra · se difiere | Cita |
|---|---|---|---|
| 10 Imagen | **E\*** | Entran el `Dockerfile` (base por digest, `runAsNonRoot`, `readOnlyRootFilesystem`), `hadolint` y la regla de import-linter. Se difieren el escaneo, el SBOM, la firma y la frase de la aceptación sobre el SBOM | Alcance §3 U11, fila «10 Imagen: E\*, T1»; enmienda §3 U11, fila «10 · 11: T1 · T6» |
| 11 Chart, cuotas y flujos | **E\*** | Completo, con el perfil de DD-3 b: sin `values-kind-demo.yaml`, 2 réplicas fijas. El único ajuste de kind es el request de memoria (P-1) | Alcance §3 U11, fila «11: E\*, T6»; enmienda §3 U11, fila «10 · 11»; DD-3; `DECISIONES-LOOP.md` §7 |
| 12 Reglas generadas y alertas | **E** | Completo: las reglas generadas, las `:dedup`, las cuatro alertas y su `promtool` | Enmienda §3 U11, fila «12 Reglas: E\* o **E** … dependen de P-3»; §6 P-3, aprobada el 2026-11-09 con su recomendación («Entran las de U11 … como reglas con `promtool`») |
| 13 Dashboards y runbooks | **E\*** | Entra `product.json` completo y el panel de ciclos omitidos en `operacion.json`. De los runbooks entran los cuatro que un `runbook_url` exige; se difiere `product-metrics-parameter-change` (P-2) | Enmienda §3 U11, fila «13: `product.json` completo; runbooks (T2)»; §6 P-3 («Sus runbooks, solo si `runbook_url` lo exige») |
| 14 Workflow de CI | **D** | Entero fuera. Queda `[ ]` con «diferido por la demo (T4)». Sus comprobaciones corren en `make -C product-metrics check` (T4: «las pruebas corren con el `make check` de la unidad») | Alcance §3 U11, fila «14: D, T4»; enmienda §3 U11, fila «14: D» |
| 15 Application y trazabilidad | **E** | Completo, con la lista «Diferido por la demo» (P-4 de la enmienda) | Enmienda §3 U11, fila «15 · 17 · 18: E · E · E\*»; §2 regla 4 |
| 16 Verificación en kind | — | Queda `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». La fila de §3 dice: «Entran el 5 (métricas D + 1), el 4 (permisos de carpeta, si el presentador usa `cro-1`/`cumplimiento-1`) y el 1 (conectividad mínima). Se difieren el 2 (E1–E8) y el 3 (rollouts)». §8 pasa los tres que entran a U12 | Enmienda §3 U11, fila «16 Kind», y §8 |
| 17 Documentación | **E** | Completo | Enmienda §3 U11, fila «15 · 17 · 18» |
| 18 Cierre de la unidad | **E\*** | Cierre acotado, con `evidence/cierre-demo.md`. Se difieren el workflow nocturno y la evidencia de kind en el PR | Enmienda §3 U11, fila «15 · 17 · 18», y §8; alcance §2.4 |

Rige RL-1 a RL-5 (`demo-kind-alcance.md` §6): máximo 2 rondas, y solo un ROJO bloquea. Para `test_traceability.py --all` rige `DECISIONES-LOOP.md` §6, con su enmienda del 2026-11-09.

La demo que sostiene U11 es D4 (enmienda §1.4): el día D + 1 el presentador abre `product.json` en Grafana y ve North Star, sostenida, tasa de consulta y `vectra_product_noise_days_below_floor`. U11-T01 escribió el cálculo y U11-T02 la publicación en `/metrics`. Esta tarea escribe **lo que hay entre `/metrics` y la pantalla**: las reglas `:dedup`, el dashboard, el chart que los instala y la imagen que corre.

---

**Dos lecciones que esta tarea aplica:**
- **U04-T06 y U04-T08** (`revisiones/U04-T06/ronda-1.md`, F-01): un chart que renderiza bien no prueba que el contenedor arranque. Aquí el contenedor real arranca con las variables **que pone el chart** y con el archivo de parámetros **que monta el chart** (CA-4).
- **Enmienda §8**: los revisores encontraron cuatro defectos que habrían roto el flujo base en kind sin que ninguna prueba fallara. En U11 el equivalente es un panel vacío: una expresión de `product.json` que nombra una serie que ninguna regla graba, o una etiqueta que el `collector` no emite. Por eso CA-9 exige el **mundo cerrado** dashboard → reglas → `collector`.

---

## Alcance

**Dentro:** los Pasos 10, 11, 12, 13, 15, 17 y 18 del plan. Texto del plan, sin recortes salvo lo que la tabla de arriba difiere, que va ~~tachado~~ con su cita y en «Fuera»:

### Bloque E — Despliegue y operación

- [ ] **Paso 10 — Imagen** (E\*)
  - Python oficial por digest, `runAsNonRoot`, `readOnlyRootFilesystem`; construida, ~~escaneada, con SBOM y firmada con `sign-image.yml` de U1; el escaneo y el SBOM son de `supply-chain.yml`~~ (T1; alcance §3 U11, fila 10).
  - **Aceptación**: `hadolint product-metrics/Dockerfile`; ningún módulo de `product-metrics` importa FastAPI (import-linter). ~~El SBOM sí lo lista, como dependencia de `vectra_common` (revisión de consistencia entre unidades, 2026-11-01).~~ (T1)

- [ ] **Paso 11 — Chart, cuotas y flujos** (E\*)
  - `Deployment` de 2 réplicas fijas con `vectra.io/hpa-exempt` y su justificación, `RollingUpdate` con `maxSurge: 1` y `maxUnavailable: 0`, `progressDeadlineSeconds: 4800`, PDB, spread por zona, `vectra-normal`, `terminationGracePeriodSeconds: 10`.
  - Sondas del `Deployment` (revisión del plan de tareas de U11, 2026-10-10): `livenessProbe` HTTP sobre `/healthz` y `readinessProbe` HTTP sobre `/readyz`, las dos en 8081; sin `startupProbe` larga (INF-U11-01).
  - `Service` solo con 8081 y `publishNotReadyAddresses: true`; `ServiceMonitor`.
  - Sin `Server` ni `AuthorizationPolicy` en el chart: 8081 lo cubre el `Server` `metrics-8081` del namespace, que U1 genera desde F60 y solo admite la identidad de Prometheus (revisión de consistencia entre unidades, 2026-11-01); las sondas del kubelet pasan por la autorización automática de sondas de Linkerd (INF-U11-04; revisión del plan de tareas de U11, 2026-10-10).
  - `ServiceAccount` con `automountServiceAccountToken: false`; `ExternalSecret` de la llave del cliente.
  - `ConfigMap` de `values-product-metrics-policy.yaml` sin `subPath` y con `checksum/config`; regla de ruta en `.github/CODEOWNERS`, el único del monorepo, para producto y riesgo (revisión de consistencia entre unidades, 2026-11-01).
  - Aporte a la cuota de `vectra-app` (NFR-U11-14) en `platform/policies/quotas/` de U1.
  - Flujos F28, F50 y F60 a verificar en `platform/network/flows.yaml`, donde ya están (revisión de consistencia entre unidades, 2026-11-01), con los casos bloqueados de INF-U11-04.
  - Diseño: INF-U11-01..04; NFR-U11-05, 14, 20, 21.
  - **Aceptación**: `helm template` con cada values + `kubeconform` + `conftest test product-metrics/policies/conftest/` (réplicas, exención, estrategia, plazos, `livenessProbe` en `/healthz` y `readinessProbe` en `/readyz` en 8081 presentes, `publishNotReadyAddresses`, sin token montado, sin `subPath`, `checksum/config`, `Server` y `AuthorizationPolicy` de Linkerd en 8081 solo para Prometheus, rangos de los parámetros dentro y fuera; revisión del plan de tareas de U11, 2026-10-10); `kyverno test` de U1 (`require-hpa-bounds`); `conftest test platform/policies/quotas/`; `uv run python platform/network/generate.py --check`; `CODEOWNERS` con la línea del archivo.

- [ ] **Paso 12 — Reglas generadas y alertas** (E)
  - `tools/gen_rules.py` genera, desde `vectra_contracts.catalog.FailClosedCause`, la regla `vectra:product_desync_failclosed:rate1h`, y desde la allowlist, las recording rules `:dedup`.
  - `PrometheusRule` del chart con `vectra:product_complete_response_ratio:1h` y `:1d`, las `:dedup` y las alertas de P-U11-06 (`RuidoExplicacion` con S del archivo; `ProductMetricsStale` y `ProductMetricsFullRecomputeMissing`, cada una en dos reglas: edad con `for: 0` y ausencia con `up … unless on (pod)` y `for` de 30 min y 26 h, las dos sin disparar durante la pasada; pendientes posteriores al cierre, 2026-10-10). `GrafanaFolderPermissionsDrift` no va aquí: es de U1.
  - Diseño: BR-U11-06, 14; P-U11-05, 06; NFR-U11-06, 08, 32.
  - **Aceptación**: `uv run python product-metrics/tools/gen_rules.py --check`; `promtool test rules product-metrics/observability/rules/tests/*.yaml`:
    - cada alerta a los dos lados del umbral;
    - una réplica sin la serie y la otra con ella (las dos con `up = 1`) → `ProductMetricsStale` solo para la primera;
    - la pasada en curso → no dispara ninguna rama;
    - la rama de edad dispara al superar el umbral sin esperar un `for`; la de ausencia, solo tras su `for`;
    - la `PrometheusRule` de U11 tiene exactamente cuatro `alertname`;
    - réplica recién arrancada con U3 caído (`up = 1`, sin `vectra_product_last_full_recompute_timestamp`) → `ProductMetricsFullRecomputeMissing` no dispara al arrancar ni a las 25 h, y dispara por la rama de ausencia a las 26 h; con la serie en 0 dispararía de inmediato, por eso el `Collector` no la emite (pendientes consolidados, 2026-10-10);
    - dos réplicas idénticas → una sola `RuidoExplicacion`;
    - `vectra:product_complete_response_ratio:1h` con 98 repartidos entre `favorable`, `desfavorable` y `revision_requerida` y 2 `fail_closed` → 0,98 (cuarta revisión de coherencia entre unidades, 2026-10-31).

- [ ] **Paso 13 — Dashboards y runbooks** (E\*)
  - `product.json` (carpeta `Vectra / Producto`): North Star con desglose, tasa de consulta con el piso y los días bajo el piso, sostenida con la nota de aproximación, originación con el target, respuesta completa y fail-closed, no atribuibles, excluidas y degradado; solo series `:dedup`; targets como líneas.
  - Sin `operation.json` propio: `platform/observability/dashboards/operacion.json` de U1 (carpeta `Vectra / Operación`) es el dueño de ciclo, entradas leídas, recomputación diaria y breaker (plan de U1, Paso 12). U11 le agrega por PR el panel que falta, ciclos omitidos (`vectra_product_cycles_skipped_total`), y solo `product.json` queda en su chart, como `ConfigMap` con la etiqueta `vectra.io/dashboard` y la anotación `grafana_folder` (revisión de consistencia entre unidades, 2026-11-01).
  - Runbooks `product-noise`, `product-metrics-degraded`, `product-metrics-stale`, `product-metrics-full-recompute-missing` y ~~`product-metrics-parameter-change`~~ (T2; enmienda §3 U11, fila 13, y §6 P-3: ver P-2).
  - Diseño: BR-U11-12, 13; INF-U11-05; NFR-U11-33, 41.
  - **Aceptación**: `uv run pytest product-metrics/tests/unit/test_dashboards.py` (ninguna referencia a series `vectra_product_*` crudas salvo en las dos alertas por réplica; ninguna razón calculada como promedio de razones; la nota de aproximación y «sin target acordado» presentes); `uv run python contracts/tools/forbidden_phrases.py product-metrics/observability/dashboards/*.json`; `uv run python platform/tests/test_runbooks.py --root product-metrics`.

- [ ] ~~**Paso 14 — Workflow de CI**~~ — **no entra** (D, T4; alcance §3 U11, fila 14). Va en «Fuera».

- [ ] **Paso 15 — Application y trazabilidad** (E)
  - Entrada `product-metrics` en `vectra-risk-gitops/components.yaml` con `wave: 5` y `values: [product-metrics/chart/values-product-metrics-policy.yaml]`; `generate.py` escribe una Application por entorno, sin auto-sync (revisión de consistencia entre unidades, 2026-11-01).
  - Trazabilidad de cada BR-U11 a una prueba.
  - **Aceptación**: `uv run python vectra-risk-gitops/generate.py --check`; `uv run python platform/tests/test_waves.py`; `kyverno test` de `disallow-argocd-auto-sync`; `uv run python platform/tests/test_traceability.py --unit product-metrics --all`.

### Bloque F — Verificación en kind

- [ ] ~~**Paso 16 — Puerta de aprobación y escenarios en kind**~~ — **no entra**: consolidado en U12 Paso 18 (enmienda §8). Va en «Fuera» y en «Pendiente en U12» del cierre.

### Bloque G — Documentación y cierre

- [ ] **Paso 17 — Documentación** (E)
  - `product-metrics/README.md`: qué mide cada métrica y qué no (la nota de aproximación de la sostenida), parámetros y targets **[INTERNO]**, ciclo de lectura, deduplicación, readiness y runbooks.
  - **Aceptación**: `test -s product-metrics/README.md`; `platform/tests/test_links.py`.

- [ ] **Paso 18 — Cierre de la unidad** (E\*)
  - **Aceptación**: `make -C product-metrics check`, que corre en orden las verificaciones estáticas, las propiedades, las pruebas de integración y de reglas de los Pasos 1–15 y termina en 0. ~~La prueba de volumen corre en el workflow nocturno; las de kind (Paso 16) se revisan como evidencia en el PR.~~ (T3 y T4; enmienda §8)

### Estructura de destino (§1 del plan): lo que esta tarea crea

```text
vectra-risk/product-metrics/
|-- Dockerfile                                   # nuevo (Paso 10)
|-- README.md                                    # nuevo (Paso 17)
|-- Makefile                                     # se amplía: image, rules, policy-chart, policy-chart-u1, quota-flows, runbooks, links, traceability
|-- docs/imagenes.md                             # nuevo: build, push, digest y PR de values de kind, sin ejecutarlos (como U7 y U9)
|-- src/vectra_product/  config.py  params.py  main.py   # solo los tres cambios de «Candidatas que se atienden»
|-- tools/gen_rules.py                           # nuevo (Paso 12); sale `tools/.gitkeep`
|-- chart/
|   |-- Chart.yaml  values.yaml  values-kind.yaml           # nuevos; `values-kind.yaml` solo si P-1 = (b)
|   |-- values-product-metrics-policy.yaml                  # ya existe; no cambia
|   |-- files/  generated-rules.yaml  product.json          # P-4 (a): lo que el chart lee con `.Files`
|   `-- templates/  _helpers.tpl  deployment.yaml  service.yaml  pdb.yaml  serviceaccount.yaml  identity.yaml
|                   configmap.yaml  servicemonitor.yaml  prometheusrule.yaml  dashboard.yaml
|-- policies/conftest/  *.rego                   # nuevo (Paso 11)
|-- observability/
|   |-- rules/product-metrics.rules.yaml         # nuevo: el `spec` de la `PrometheusRule` renderizada, versionado
|   |-- rules/tests/*.yaml                       # nuevo: casos de `promtool`
|   |-- runbooks/  product-noise.md  product-metrics-degraded.md  product-metrics-stale.md  product-metrics-full-recompute-missing.md
|   `-- dashboards/product.json                  # nuevo (Paso 13)
`-- tests/
    |-- unit/  test_chart.py  test_gen_rules.py  test_dashboards.py    # nuevos
    |-- integration/test_image.py                # nuevo
    |-- fixtures/crds/  externalsecret.json  servicemonitor.json  prometheusrule.json   # nuevos
    `-- volume/.gitkeep                          # se queda: la prueba de volumen sigue diferida
```

Los nombres de las plantillas son orientativos; los demás son los que nombran los criterios. Fuera de `product-metrics/`:

- `vectra-risk-gitops/components.yaml` y lo que `generate.py` escribe (`apps/<env>/product-metrics.yaml` y lo que cambie en `apps/<env>/`);
- `platform/observability/dashboards/operacion.json`: **solo** el panel nuevo de ciclos omitidos;
- `platform/tests/test_kind_profile.py`: **solo** `BUDGET_GIB` y su comentario;
- `platform/tests/test_platform.py`: **solo** `product-metrics` en `EXPECTED_WAVES[5]`. Sin esa palabra `make -C platform check` falla; es la candidata de la plantilla de despliegue (`CANDIDATAS.md`, líneas 303 y 517), que aquí se nombra de antemano;
- `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md` (nuevo), `aidlc-docs/construction/product-metrics/code/process.md` (el texto de P-6), el plan (casillas), `CANDIDATAS.md` y `bitacoras/U11-T03.md`.

### Precisiones

#### Paso 10 — Imagen

- `product-metrics/Dockerfile`, multi-stage, como `bias-monitoring/Dockerfile`, con contexto en la raíz de `vectra-risk/`:
  - cada `FROM` fijado por digest;
  - usuario `65532:65532`, el mismo `runAsUser` y `runAsGroup` del chart;
  - solo el runtime de `vectra_product` y sus dependencias del workspace (U0), sin dependencias de desarrollo;
  - `CMD ["python", "-m", "vectra_product.main"]` (`process.md`, «Comando de arranque de la imagen»); `EXPOSE 8081` y ningún 8080.
- Target `image` en `product-metrics/Makefile`, con el tag `localhost:5001/vectra/product-metrics:dev`. `check` construye la imagen **antes** de `test_image.py`, para que la prueba no pase con una imagen vieja (candidata de U09-T04, F-03).
- `product-metrics/docs/imagenes.md`, como `bias-monitoring/docs/imagenes.md`: build, comprobaciones locales, y el push, el digest real y el PR de values de kind (`vectra-risk-gitops/values/kind/product-metrics.yaml`) **sin ejecutarlos**. Los hace el operador en U12 Paso 18.
- En `chart/values.yaml`, el digest es uno de ejemplo, distinto de los que ya usan los otros charts (hoy van del `…0001` al `…0006`): el siguiente libre en la base de la rama. No puede ser 64 ceros (`test_placeholder_digests_are_only_on_images_we_build`).
- «Sin FastAPI» se comprueba con import-linter, que ya tiene el contrato `sin-fastapi`. La parte del SBOM se difiere (T1).

#### Paso 11 — Chart

- **Nombres** (los que espera `platform/network/flows.yaml`, línea 106): `Deployment`, `Service` y `ServiceAccount` se llaman `product-metrics`, con `app.kubernetes.io/name: product-metrics`, en `vectra-app`. El `Service` **debe** llamarse `product-metrics`: el `ServiceMonitor` no fija `jobLabel`, así que `job` es el nombre del `Service`, y las ramas de ausencia de las alertas usan `up{job="product-metrics"}`. Una prueba ata los dos.
- **Recursos** (INF-U11-01, NFR-U11-13): requests 100m / 256 MiB y limits 500m / 512 MiB en `chart/values.yaml`, que es lo que rinden staging y prod. El request de memoria de kind es P-1.
- **Sondas:** `/healthz` y `/readyz` en 8081, sin `startupProbe`. Una prueba compara las rutas con las que sirve `vectra_common.ops_server`, importadas y no copiadas, como `scoring-explainability/tests/unit/test_chart.py::test_probes_the_paths_are_routes_that_ops_server_serves`. El diseño de U11 ya dice `/healthz`: la candidata de `/livez` (`CANDIDATAS.md`, línea 511) es de los diseños de U7 y U8 y no se toca aquí.
- **Variables del contenedor:** exactamente las de la tabla «Entorno y arranque» de `process.md`:
  - `VECTRA_REGISTRY_URL` (F28: el Service y el puerto de `decision-registry-service` de `flows.yaml`), `VECTRA_CLIENT_ID` (igual a `vectra_product.config.CLIENT_ID`, importado), `VECTRA_TOKEN_URL`, `VECTRA_CLIENT_KEY_PATH` y, si alguna URL es `https://`, `VECTRA_CA_BUNDLE` con el `ConfigMap` `vectra-internal-ca`, como `bias-monitoring/chart`;
  - `VECTRA_POLICY_PATH` es opcional: o no se pone y el `ConfigMap` se monta en `vectra_product.params.POLICY_PATH`, o se pone y coincide con el montaje. La prueba compara con la constante importada;
  - ninguna con valor por omisión incrustado en la plantilla: salen de values con `required`;
  - **ninguna constante de `config.py`** (ciclo, plazo, reintentos, timeout, página, breaker, ventanas) aparece como variable de entorno.
- **Identidad** (INF-U11-03): un `ExternalSecret` desde `identity/clients/product-metrics`, propiedad `private-key`, con el formato de `bias-monitoring/chart/templates/identity.yaml`, montado de solo lectura. Ningún `Secret` en el render. `automountServiceAccountToken: false` en la `ServiceAccount` y en el pod.
- **`values-product-metrics-policy.yaml`** (INF-U11-02; BR-U11-09):
  - `platform/tests/integration.py` `render_env` no pasa los `values` de un componente de tipo `path` (`CANDIDATAS.md`, líneas 466 y 512), así que el chart debe rendir **sin** recibir ese archivo por `-f`. Haz lo que hizo U9: las plantillas lo leen del chart con `.Files` y, encima, de los values que Argo CD le pasa con ese mismo archivo, siempre con `required`. Ninguno de los ocho parámetros se repite en `values.yaml`;
  - el `ConfigMap` lleva el archivo entero, se monta como directorio (sin `subPath`) y el `Deployment` lleva `checksum/config` = sha256 del `data` del `ConfigMap` renderizado (la prueba lo recalcula);
  - la `PrometheusRule` toma S (`noise_sustain_days`) del mismo archivo;
  - la regla de `conftest` evalúa **el `data` del `ConfigMap` renderizado**, no el archivo suelto, con los rangos de BR-U11-09: 0 < F < 1, 1 ≤ S ≤ 14 entero, N ≥ 30 entero, targets entre 0 y 1, `target_origination_hours` > 0 y `target_north_star` nulo o entre 0 y 1; las ocho claves, ni una más ni una menos;
  - **paridad con el proceso** (lección de U09-T04, F-01: la regla admitía valores que el CronJob rechazaba): una prueba pasa la misma tabla de fixtures por `vectra_product.params.parse` y por `conftest`, y los dos dan el mismo veredicto en cada fila. La tabla incluye tipos, no solo rangos (CA-3);
  - los rangos de la regla salen de `config.py` o una prueba los compara: mover una constante de rango en `config.py` hace fallar una prueba si la regla no la sigue (candidata F-07, abajo);
  - **`CODEOWNERS`:** `.github/CODEOWNERS` ya tiene `**/values-product-metrics-policy.yaml @jjlloobb @joseluisjedi`. No se toca; una prueba comprueba que la regla cubre `vectra-risk/product-metrics/chart/values-product-metrics-policy.yaml` y otra que sin la regla la ruta queda descubierta (decisión P-1 (a) de U09-T04, que aquí se repite).
- **Sin `Server` ni `AuthorizationPolicy` en el chart:** ver P-3.
- **Cuota (NFR-U11-14).** El aporte de U11 ya está en `platform/policies/quotas/quotas.yaml` (`U11: { requests: [0.78, 1.05], limits: [3.9, 2.44] }`) y coincide con INF-U11-01: 3 pods × (contenedor + proxy de 100m / 20 MiB y 500m / 128 MiB) × 1,3. Una prueba de `test_chart.py` recalcula las cuatro cifras desde el render de `prod` y las compara con la línea de `quotas.yaml`, leída del archivo. El plan dice `conftest test platform/policies/quotas/`, pero en el repositorio esa comprobación es `platform/policies/quotas/render.py --check` y `test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota`. Usa esas y regístralo, como U7 y U9. Si el aporte no coincide, **repórtalo**: no edites U1.
- **Flujos (INF-U11-04).** F28, F50 y F60 ya están en `flows.yaml`, y los tres casos bloqueados en `forbidden.yaml` (líneas 26 a 28: `product-metrics` → `case-service`, `product-metrics` → `governance-service` y `case-service` → 8081 de `product-metrics`). Sin flujos nuevos. Si algo falta, **repórtalo**: no edites U1. La ejecución de la suite de conectividad en kind es de U12.
- **Admisión** (reglas del plan): imagen por digest, `runAsNonRoot`, `readOnlyRootFilesystem` (con `emptyDir` solo si algo escribe en disco; CA-4 lo decide con `--read-only`), sin `privileged` ni `hostPath`, recursos, `priorityClassName`, `vectra.io/criticality`, 2 réplicas, spread, PDB por `app.kubernetes.io/name` y `vectra.io/hpa-exempt` con la justificación de INF-U11-01. Ningún `HorizontalPodAutoscaler`.
- `product-metrics/policies/conftest/` con las reglas del plan. Cada regla tiene en `test_chart.py` un caso que falla con una mutación del render.
- **Perfil demo (T6):** DD-3 b. Sin `values-kind-demo.yaml` y sin 1 réplica.

#### Presupuesto de memoria de kind (`DECISIONES-LOOP.md` §7)

La máquina de la demo tiene 14 GiB. `BUDGET_GIB` está en 10,4 con U7 (`requested_gib()` = 10,3438 GiB) y faltan U8, U10, U11 y U12. §7 ya dio por inviable un pico de ≈ 13 GiB. Por eso esta tarea **no sube `BUDGET_GIB` sin más**:

1. **Mide primero.** Antes de tocar `components.yaml`, anota la cifra de la base de la rama con la orden de CA-13. Con la Application agregada, mídela otra vez.
2. **El request de memoria de kind** va tan bajo como P-1 permita. Con P-1 = (b) es 128 MiB por pod, en `product-metrics/chart/values-kind.yaml`, que entra por `kind_values` en `components.yaml` (como `postgres`). `render_env` sí pasa `kind_values`; **no** pasa `vectra-risk-gitops/values/kind/<nombre>.yaml` (`CANDIDATAS.md`, línea 512), así que un override puesto allí no lo vería `test_kind_profile.py`. `values-kind.yaml` solo contiene el request de memoria: las réplicas, los limits, el PDB y la exención no cambian, y staging y prod siguen en INF-U11-01 (una prueba lo fija, como `test_kind_serving_halves_memory_requests_and_staging_and_prod_keep_inf_u6_01`).
3. **Aporte esperado de U11:** 2 réplicas × (128 + 20) MiB = **0,2891 GiB** con P-1 = (b), o 2 × (256 + 20) MiB = 0,5391 GiB con P-1 = (a). La diferencia entre las dos mediciones debe ser esa cifra (± 0,001). Si no lo es, algo más cambió: **detente y repórtalo**.
4. `BUDGET_GIB` sube a la cifra medida con U11, redondeada hacia arriba a 0,1 GiB (10,7 con (b) sobre la base de hoy; 10,9 con (a)), con el comentario de la decisión y la cita de §7. Nunca más arriba. Si otra tarea ya subió el tope en `main`, parte de la cifra de la base de tu rama.
5. **Proyección, que no decide el codificador.** Suma a la cifra medida los requests de kind que el diseño fija para lo que todavía no tiene Application: U8 (INF-U8-04: `case-service` y `case-worker`, 2 × (256 + 20) MiB cada uno; `core-banking-mock`, 2 × (64 + 20) MiB) y U10 (INF-U10-01: `console-bff`, 2 × (256 + 20) MiB; `console-spa`, 2 × (32 + 20) MiB). Al redactar esta tarea da ≈ 1,88 GiB más: ≈ 12,5 GiB con (b) y ≈ 12,8 GiB con (a). Recalcúlala con lo que haya en `main` y déjala en la bitácora y en el cierre.
6. **Detención.** Si la cifra medida no cuadra (punto 3), o si la proyección llega a **13,0 GiB**, no subas `BUDGET_GIB`: **detente y repórtalo** con la cifra, el desglose por unidad y las opciones. Es una detención, no un ROJO del codificador. No cambies réplicas, limits ni requests fuera de lo que P-1 fija.
7. En la prueba del contenedor real (CA-4), anota la memoria del contenedor tras la primera pasada (`docker stats --no-stream`). Es un dato para U12, sin umbral.

#### Paso 12 — Reglas

- **Son cuatro alertas y seis reglas.** El texto del Paso 12 nombra tres alertas en su paréntesis, pero su aceptación exige «exactamente cuatro `alertname`», P-U11-06 y BR-U11-14 listan cuatro, y el Paso 13 pide el runbook `product-metrics-degraded`. Falta `ProductMetricsDegraded` en la enumeración, no en el diseño. Entran las cuatro, con las expresiones y los `for` de la tabla de P-U11-06:
  - `RuidoExplicacion`: `vectra:product_noise_days_below_floor:dedup >= S`, `for: 0`;
  - `ProductMetricsDegraded`: `vectra:product_metrics_degraded:dedup == 1`, `for: 1h`;
  - `ProductMetricsStale`: dos reglas (edad `> 1800` con `for: 0`; ausencia con `for: 30m`);
  - `ProductMetricsFullRecomputeMissing`: dos reglas (edad `> 93600` con `for: 0`; ausencia con `for: 26h`).

  Todas SEV3, con `severity` y `runbook_url`. Deja la corrección del texto del plan como candidata.
- **`tools/gen_rules.py`:**
  - la regla de desincronía sale de `vectra_contracts.catalog.FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"]` (hoy `version_mismatch` y `feature_dictionary_incomplete`), con las causas ordenadas;
  - las `:dedup` salen de `vectra_product.collector.PRODUCT_SERIES`: **exactamente una por clave**, con el nombre `vectra:<serie sin el prefijo vectra_>:dedup` y la expresión `max without (instance, pod) (<serie>)` (P-U11-05). Ninguna para `OPERATION_SERIES`;
  - la salida es determinista (dos corridas, mismos bytes);
  - `--check` termina en 1 si el archivo versionado difiere del generado, y no escribe nada.
- `vectra:product_complete_response_ratio:1h` y `:1d` (BR-U11-06) van escritas en la plantilla: (`outcome` distinto de `fail_closed`) / (todos los `outcome`) de `vectra_recommendations_total`.
- **Dónde vive cada cosa** (P-4): helm solo lee con `.Files` lo que está dentro de `chart/`. Por eso:
  - `gen_rules.py` escribe `product-metrics/chart/files/generated-rules.yaml`, y la plantilla `prometheusrule.yaml` lo incluye;
  - `product-metrics/observability/rules/product-metrics.rules.yaml` es el `spec` de la `PrometheusRule` **renderizada** (con S ya sustituida), versionado. `make -C product-metrics rules` lo regenera desde el render y **falla si el versionado difiere**, y comprueba que el `spec` es idéntico en kind, staging y prod. Así `promtool` prueba lo que se despliega, y la orden literal del plan funciona en un checkout limpio;
  - los casos de `rules/tests/*.yaml` apuntan a ese archivo.
- No nombres ningún directorio `generated` ni `rendered` dentro de `product-metrics/`: `test_traceability.py` y `test_runbooks.py` los saltan.
- **Casos de `promtool`**, uno con nombre por viñeta de la aceptación del plan, más los que piden P-U11-05, P-U11-06 y NFR-U11-08:
  - `ProductMetricsDegraded` a los dos lados (59 min no dispara; 1 h dispara) y dos réplicas con `degraded = 1` → una sola alerta;
  - las dos réplicas sin la serie (`up = 1`) → `ProductMetricsStale` para las dos;
  - dos réplicas idénticas → cada `:dedup` vale lo que una réplica (no el doble);
  - `vectra:product_desync_failclosed:rate1h` cuenta `version_mismatch` y `feature_dictionary_incomplete` y no cuenta una causa de otra categoría.

#### Paso 13 — Dashboard y runbooks

- `product-metrics/observability/dashboards/product.json` es el archivo canónico (§1 del plan y las órdenes de aceptación). El chart lo publica como `ConfigMap` desde una copia en `chart/files/product.json`; una prueba exige que el `data` del `ConfigMap` renderizado sea byte a byte el archivo canónico (P-4).
- El `ConfigMap` lleva la etiqueta y la anotación que lee el sidecar de Grafana de U1, **leídas de** `platform/observability/values/kube-prometheus-stack.yaml` (`sidecar.dashboards.label` y `folderAnnotation`), y el título de carpeta `Vectra / Producto`, que debe existir en `platform/observability/grafana/folder-permissions.yaml` con `View` para `cro`, `cumplimiento` e `ingeniero_riesgo` y para nadie más (BR-U11-13). La prueba lee los dos archivos; no los edita.
- `product.json`: `datasource.uid` `prometheus` (como `operacion.json`), zona horaria de Colombia y, en cada panel, el periodo que usa (BR-U11-08).
- **Paneles** (BR-U11-12), todos presentes: North Star con su desglose (`sustentada`, `cambiada`, `revision_resuelta`); tasa de consulta con el piso y los días bajo el piso; sostenida con la nota literal de BR-U11-04 («aproximación: mide si la decisión siguió la recomendación; la revisión del comité no está en el sistema»); originación con el target; respuesta completa y fail-closed por desincronía; no atribuibles; excluidas; aviso de datos degradados. La North Star sin target muestra «sin target acordado».
- Los targets son líneas de referencia tomadas de `vectra:product_target:dedup{metric=…}`, no números escritos en el JSON.
- Una razón que combina cortes se calcula como `sum(…_decisions:dedup{part="numerator"}) / sum(…_decisions:dedup{part="denominator"})`, nunca con `avg` de razones (P-U11-05).
- **Mundo cerrado** (lo que evita un panel vacío en D4), en `test_dashboards.py`:
  - toda serie que nombra una expresión de `product.json` es un `record` de `product-metrics.rules.yaml`;
  - toda `:dedup` graba una clave de `collector.PRODUCT_SERIES`;
  - todo nombre de etiqueta de un selector está en el conjunto de etiquetas de esa serie en `PRODUCT_SERIES`, y los valores de `metric` están en `collector.TARGET_METRICS`;
  - los paneles que D4 enseña (North Star, sostenida, tasa de consulta y días bajo el piso) usan un periodo que tiene datos el día D + 1: `day` o `30d` (`7d` en la tasa de consulta), no solo `month`.
- **Panel de ciclos omitidos** en `platform/observability/dashboards/operacion.json`: un panel más, con `vectra_product_cycles_skipped_total` (serie de operación, cruda: ese dashboard es de U1 y no entra en la regla de `:dedup`), el mismo `datasource` y un `id` y un `gridPos` libres. Nada más cambia en ese archivo. `platform/tests/test_platform.py::test_dashboards` debe seguir pasando.
- **Runbooks** (P-2): los cuatro de las alertas, en `product-metrics/observability/runbooks/`, con las secciones de `platform/runbooks/_template.md` y un comando en cada paso de «Verificación». `runbook_url` es la ruta relativa a `vectra-risk/` (como `governance/observability/governance-rules.yaml`). `product-noise.md` dice que es una señal de **producto** (revisar cómo se usa la explicación con el piloto), no una falla técnica (BR-U11-14). Ningún texto pasa `forbidden_phrases.py`.

#### Paso 15 — Application y trazabilidad

- Entrada en `components.yaml`: `{ name: product-metrics, wave: 5, namespace: vectra-app, path: product-metrics/chart, env_values: true, values: [product-metrics/chart/values-product-metrics-policy.yaml] }`, más `kind_values: [product-metrics/chart/values-kind.yaml]` si P-1 = (b), con un comentario como el de las otras unidades. `generate.py` escribe una Application por entorno, sin `syncPolicy.automated`. `FIXED_WAVES` de `test_waves.py` ya fija la wave 5.
- **Trazabilidad.** `python3 -B platform/tests/test_traceability.py --unit product-metrics --all` da hoy rc 1 con **16** identificadores (comprobado al redactar, sobre `28ee5ae`). Destino de cada uno:

  | Identificador | Destino | Dónde se traza (o por qué se difiere) |
  |---|---|---|
  | INF-U11-02 | **Trazar** | `chart/templates/configmap.yaml`, la regla de rangos de `policies/conftest/` y la prueba de `CODEOWNERS` |
  | INF-U11-03 | **Trazar** | `chart/templates/serviceaccount.yaml` e `identity.yaml`; regla de `conftest` del token y del `Secret` |
  | INF-U11-04 | **Trazar** | `chart/templates/service.yaml` (solo 8081) y la prueba de flujos y de `metrics-8081` |
  | INF-U11-05 | **Trazar** | `chart/templates/prometheusrule.yaml` y `dashboard.yaml` |
  | NFR-U11-05 | **Trazar** | Regla de `conftest` de réplicas, exención, PDB y spread |
  | NFR-U11-06 | **Trazar** | `tools/gen_rules.py` y la prueba de deduplicación de `test_dashboards.py` |
  | NFR-U11-13 | **Trazar** (P-5) | `chart/values.yaml` (requests y limits) y la regla de recursos. Su **medición** con 10 veces el volumen va en el cierre como «no comprobado», sin fila en la lista |
  | NFR-U11-14 | **Trazar** | La prueba de `test_chart.py` que recalcula el aporte y lo compara con `quotas.yaml` |
  | NFR-U11-32 | **Trazar** | `tools/gen_rules.py` y `observability/rules/tests/*.yaml` |
  | NFR-U11-33 | **Trazar** | `tests/unit/test_dashboards.py` |
  | NFR-U11-41 | **Trazar** | La prueba de `test_dashboards.py` que comprueba el panel de ciclos omitidos en `operacion.json` y que `product.json` no tiene series de operación |
  | NFR-U11-42 | **Trazar** | Las dos reglas de `ProductMetricsFullRecomputeMissing` y sus casos de `promtool` |
  | P-U11-05 | **Trazar** | `tools/gen_rules.py` y `test_gen_rules.py` |
  | P-U11-06 | **Trazar** | `chart/templates/prometheusrule.yaml` y `observability/rules/tests/*.yaml` |
  | NFR-U11-02 | **Diferir** | Paso 7, prueba de volumen (`-m volume`); enmienda §3 U11, fila «7», y §2 regla 3; T3 |
  | NFR-U11-03 | **Diferir** | Paso 7, benchmark de `compute` con el volumen × 10; enmienda §3 U11, fila «7», y §2 regla 3; T3 |

  - La lista «Diferido por la demo» de `cierre-demo.md` tiene **exactamente** esas dos filas, cada una con el identificador, el paso y la cita.
  - Cada identificador que se traza se cita en el artefacto que lo implementa o en la prueba que lo verifica. Citarlo solo en el `README.md` no cuenta.
  - **Ningún archivo de `product-metrics/` escribe `NFR-U11-02` ni `NFR-U11-03`** (ni el README, ni un runbook, ni un comentario): la herramienta rechaza una fila diferida cuyo identificador «ya tiene código o prueba».
  - La herramienta solo lee archivos con sufijo conocido, `Makefile` y `Dockerfile` (`CANDIDATAS.md`, línea 531): no cuentes con una cita en `.importlinter`, `.helmignore` u otro archivo sin sufijo.
  - Corre la prueba al empezar, registra lo que marca y justifica cada identificador en la bitácora.
- **BR-U11 a una prueba.** `test_traceability.py` no ve las BR, que están en párrafos en negrita (candidata de U03-T02). Por eso hay un `git grep` por cada una (CA-12), como en U7 y U9. Hoy quedan **7 sin prueba**: BR-U11-02, 04, 06, 08, 12, 13 y 14. Las de los Pasos 3 y 4 (02, 04 y 08) se citan en la prueba que ya las ejerce; si ninguna lo hace, se escribe. BR-U11-04 y 08 se citan además en `test_dashboards.py` (la nota de aproximación; el periodo en cada panel); BR-U11-06 y 14, en `test_gen_rules.py` y en los casos de `promtool`; BR-U11-12 y 13, en `test_dashboards.py` y `test_chart.py`.

#### Candidatas que se atienden aquí (`CANDIDATAS.md`)

Son de `product-metrics`, baratas, y varias las necesita el despliegue. El codificador marca cada una en `CANDIDATAS.md` («~~…~~ **Atendida en U11-T03:** …»), como hizo U11-T02.

- **C-1 · F-07 de U11-T01, ronda 2 (NARANJA; línea 536).** El rango de `target_origination_hours` pasa a una constante con nombre en `config.py`, y `params.parse` y su mensaje la usan. Va **antes** de escribir la regla de `conftest`, que usa los mismos rangos.
- **C-2 · F-01 de U11-T02 (NARANJA; línea 559).** Una prueba fija que la página en vuelo **termina** al recibir `SIGTERM`: lee lo que completó el doble cuando el proceso sale, antes de parar los servidores, o exige que el apagado dure al menos la latencia que le quedaba a la página. Un `scheduler` que cancela la página debe hacerla fallar.
- **C-3 · F-02 de U11-T02 (NARANJA; línea 560).** Dos pruebas con reloj simulado: una pasada justo por debajo de 75 min termina y otra justo por encima vence (cambiar el plazo a 90 min debe hacer fallar una); y una segunda pasada diaria que también falla hace **sus** 6 reintentos (sin el reinicio diario de `_retries` debe fallar).
- **C-4 · F-03 de U11-T02 (NARANJA; línea 561).** Ver P-6.
- **C-5 · F-04 de U11-T02 (AMARILLO; línea 562).** Una prueba determinista para la rama `incremental_after_full_failed` de `state.py`: la pasada completa termina y la lectura incremental que sigue, con el candado tomado, falla.
- **C-6 · F-06 de U11-T02 (AMARILLO; línea 564), la parte de U11.** `main` sube a WARNING los loggers de `uvicorn` y `httpx`, y una prueba del proceso real exige que ninguna línea del log se quede solo con `level`, `timestamp` y `service`. U0 no se toca.
- **C-7 · `make check` corre las propiedades dos veces con `ci` (línea 557).** Ninguna prueba corre dos veces con el perfil `ci` dentro de `check`. La orden del Paso 5 (cobertura del 100 % de `compute` y `noise` con `tests/unit` y `tests/property`) y la del Paso 8 (≥ 90 %) se conservan tal cual: lo que cambia es que `test` no repite lo que `coverage` ya corre, como en `bias-monitoring/Makefile`.
- **C-8 · `EXPECTED_WAVES` (líneas 303 y 517).** Nombrado arriba entre los archivos de U1 que esta tarea toca. La candidata de la plantilla (`loop/plantilla-tarea.md`) sigue abierta: es del loop.
- **C-9 · `platform/.tools` en un worktree nuevo (línea 534).** Ver «Notas».
- **C-10 · Rojos de Hypothesis con el perfil `dev` (línea 558).** Ver «Plan de pruebas».

### Plan

- Pasos 10, 11 y 13: `[x]` con `(U11-T03)` y la nota de lo diferido, en el estilo de los Pasos 5 y 7 (por ejemplo, «— firma, SBOM y escaneo diferidos por la demo (T1)»).
- Pasos 12, 15 y 17: `[x] (U11-T03)`.
- Paso 18: `[x] (U11-T03)` con «— cierre acotado a la demo».
- Paso 14: `[ ]` con «diferido por la demo (T4)».
- Paso 16: `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)».

### Cierre acotado (Paso 18)

`aidlc-docs/construction/product-metrics/evidence/cierre-demo.md`, con el formato de `aidlc-docs/construction/scoring-explainability/evidence/cierre-demo.md` y el de `bias-monitoring`:

- **Comprobado:** cada paso que entra (también los de U11-T01 y U11-T02, en una fila cada tarea), con su comando y su resultado; la memoria de kind con y sin U11 y la proyección; las cifras de CA-16 y CA-17.
- **Decisiones:** P-1 a P-6, con la opción que rigió y quién la decidió; las cuatro alertas frente a las tres del texto del plan; lo que quedó «no comprobado» de NFR-U11-13.
- **Pendiente en U12** (lo que verifica U12 Paso 18, enmienda §8):
  - escenario 5 del Paso 16: North Star, sostenida, tasa de consulta y `ProductMetricsStale` con datos reales, el día siguiente a las 2 000 decisiones (BR-U12-06). Los periodos excluyen el día en curso y son días **UTC**;
  - escenario 4: permisos de `Vectra / Producto` con los usuarios de U2, si el presentador usa `cro-1` o `cumplimiento-1`;
  - escenario 1: conectividad mínima (F28, F50, F60 y los tres casos bloqueados; `/readyz` del kubelet);
  - push de la imagen y digest real (`docs/imagenes.md`);
  - que ESO materialice la llave desde `identity/clients/product-metrics`;
  - que Prometheus cargue la `PrometheusRule` de `vectra-app` y Grafana descubra el `ConfigMap` del dashboard;
  - memoria real del pod con 2 000 decisiones (NFR-U11-13 «kind a 1 vez»), frente al request de kind de P-1;
  - **orden de arranque en la wave 5:** si `product-metrics` arranca antes de que `decision-registry-service` responda, la primera pasada falla y el siguiente intento es a los 15 min (`process.md`, P-1 (a) y P-2 (b) de U11-T02): el dashboard queda vacío hasta entonces y `/readyz` da 503 hasta 30 min. El operador debe saberlo antes de D4.
- **Diferido por la demo:** las dos filas de la tabla de arriba y, sin identificador propio, cada uno con su destino:
  - el Paso 14 (T4);
  - `mutmut` (Paso 5, T3) y la prueba de volumen con la medición de NFR-U11-13 (Paso 7, T3);
  - firma, SBOM y escaneo (Paso 10, T1);
  - `product-metrics-parameter-change` (Paso 13, T2; P-2);
  - los escenarios 2 (E1–E8) y 3 (rollouts) del Paso 16 (enmienda §3 U11, fila 16);
  - la reconciliación de INF-U11-01 («unos 15 s») con NFR-U11-09 (`CANDIDATAS.md`, línea 555).

**Fuera** (rechazar aunque se vea roto o tentador):

- **Paso 14 completo:** `.github/workflows/product-metrics.yml`, `actionlint`, la prueba del disparador `contracts/**` y el workflow nocturno (T4).
- **Paso 16 completo:** guía, scripts y escenarios de kind; cualquier `kubectl`, `helm install`, `argocd` o sync; el push de la imagen y el digest real (AUTONOMIA-01; enmienda §8).
- Firma, SBOM, escaneo, `sign-image.yml` y `supply-chain.yml` (T1).
- La prueba de volumen (`tests/volume/`, `-m volume`), el benchmark de `compute` y `mutmut` (T3).
- El runbook `product-metrics-parameter-change` (T2), salvo P-2 = (b).
- `values-kind-demo.yaml` o 1 réplica (DD-3 eligió la b).
- Un `operation.json` propio, un `Server` o una `AuthorizationPolicy` en el chart, un HPA y un puerto 8080.
- **Cambios en U0, U2, U3 y U7.** En U1, solo lo nombrado en «Estructura de destino». En particular, quedan fuera con su destino:
  - `test_traceability.py` no lee archivos sin sufijo (línea 531) → U1;
  - `render_env` sin los `values` de la unidad (líneas 466 y 512) → U1;
  - el pánico de `check-chart` (líneas 345 y 400) y `STATIC_POLICIES` copiada (línea 472) → U1;
  - `crd_to_schema.py` duplicado (líneas 468 y 516) → U1. Aquí **no** se copia una cuarta vez: los esquemas de `tests/fixtures/crds/` se generan invocando el de `bias-monitoring/tests/fixtures/crds/`, y la bitácora anota la orden y la fuente de cada CRD;
  - `/livez` en los diseños de U7 y U8 (línea 511) → U0 o esos diseños;
  - el `-15` de `ops_server.serve` (líneas 437 y 556) y `httpx.Timeout` por fase (línea 524) → U0;
  - `next_seq_after` con una página vacía (línea 535) → U3;
  - `EXPECTED_WAVES` y `FIXED_WAVES` solapadas (línea 170) → U1.
- **De U11, fuera:**
  - INF-U11-01 («unos 15 s») frente a NFR-U11-09 (línea 555) → diseño de U11, antes del rollout con U3 caído. El README describe lo que el código hace (30 min);
  - el ejemplo ambiguo de ruido de `business-logic-model.md` §3 (línea 532) → diseño de U11. El README sí explica la ventana móvil de 7 días sin esa ambigüedad;
  - F-05 de U11-T02 (línea 563): el efecto es equivalente; se queda como está.
- Cambios de comportamiento en `vectra_product` fuera de C-1, C-4 y C-6. Si el chart o la imagen revelan un defecto del código de U11-T01 o U11-T02, **repórtalo** y no lo arregles aquí.
- Editar el texto de los diseños o del plan, salvo las casillas del plan.

---

## Archivos de contexto

- `aidlc-docs/construction/plans/product-metrics-code-generation-plan.md`: §1, Pasos 10 a 18, §3, §4 y «Reglas de admisión».
- `aidlc-docs/construction/plans/demo-recorte-funcional.md`: §1.4 (D4), §2, §3 U11, §6 (P-3, P-4) y §8.
- `aidlc-docs/construction/plans/demo-kind-alcance.md`: §2 (T1 a T6), §3 U11, §5 (DD-3) y §6.
- `DECISIONES-LOOP.md` §6, §7 y §8.
- `aidlc-docs/construction/product-metrics/`: `infrastructure-design/` (INF-U11-01 a 06 y `deployment-architecture.md`), `nfr-design/nfr-design-patterns.md` (P-U11-05, 06 y §3), `nfr-requirements/nfr-requirements.md`, `functional-design/business-rules.md` (BR-U11-04, 06 a 09, 12 a 14) y `functional-design/domain-entities.md` (§4 y §5).
- `aidlc-docs/construction/product-metrics/code/process.md` («Entorno y arranque», «Qué se publica y cuándo») y `code/logic.md`.
- `product-metrics/`: `Makefile`, `src/vectra_product/` (`main.py`, `collector.py`, `config.py`, `params.py`, `scheduler.py`, `state.py`), `chart/values-product-metrics-policy.yaml`, `tests/integration/` (`test_process.py`, `test_main_process.py`) y `tests/doubles/` (`http_servers.py`, `registry_double.py`, `process_world.py`).
- `bitacoras/U11-T01.md`, `bitacoras/U11-T02.md`, `revisiones/U11-T02/ronda-1.md` y `arbitraje-ronda-1.md`.
- La misma tarea hecha para U9 y U7: `tareas/U09-T04-despliegue-y-cierre.md`, `tareas/U07-T04-despliegue-y-cierre.md`, `revisiones/U09-T04/` (F-01: paridad de la regla con el proceso) y `revisiones/U07-T04/ronda-1.md`.
- `bias-monitoring/`: `Dockerfile`, `chart/` (`.Files`, `identity.yaml`, `servicemonitor.yaml`), `policies/conftest/`, `Makefile` (`policy-chart`, `policy-chart-u1`), `docs/imagenes.md`, `tests/unit/test_chart.py`, `tests/integration/test_image.py` y `tests/fixtures/crds/`.
- `governance/observability/` y `governance/runbooks/compensation-event-pending.md`: una alerta de la demo con su `promtool` y su runbook (P-3 de la enmienda).
- `platform/`: `network/flows.yaml`, `network/forbidden.yaml`, `network/generated/<env>/vectra-app.yaml` (`metrics-8081`), `policies/quotas/quotas.yaml` y `render.py`, `policies/kyverno/` (`kyverno-test.yaml`), `policies/rego/`, `observability/dashboards/operacion.json`, `observability/values/kube-prometheus-stack.yaml`, `observability/grafana/folder-permissions.yaml`, `runbooks/_template.md`, `tools.env` y `Makefile`.
- `platform/tests/`: `integration.py`, `test_integration.py`, `test_kind_profile.py`, `test_platform.py`, `test_waves.py`, `test_traceability.py`, `test_runbooks.py` y `test_links.py`.
- `vectra-risk-gitops/components.yaml`, `generate.py` y `README.md`.
- `contracts/python/vectra_contracts/src/vectra_contracts/catalog.py` y `contracts/tools/forbidden_phrases.py`.
- `identity-edge/keycloak/realm/realm.kind.yaml` (cliente `product-metrics`) y `platform/kind/vault_paths.py`.
- `../.github/CODEOWNERS` (la raíz del repositorio; `vectra-risk/` no tiene `.github/`).
- `CANDIDATAS.md`: las líneas citadas en «Candidatas que se atienden aquí» y en «Fuera».

---

## Criterios de aceptación

Desde `vectra-risk/`, con las herramientas de `platform/install-tools.sh`. Ninguno toca el clúster. Tras cada criterio va lo que pasa **hoy** en `origin/main` (`28ee5ae`).

- [ ] **CA-1** — Paso 10: imagen.
  ```bash
  platform/.tools/bin/hadolint product-metrics/Dockerfile
  make -C product-metrics image
  docker image inspect localhost:5001/vectra/product-metrics:dev --format '{{.Config.User}} {{json .Config.Cmd}}'
  docker run --rm --entrypoint sh localhost:5001/vectra/product-metrics:dev -c '! pip list 2>/dev/null | grep -iE "^(pytest|hypothesis|ruff|mypy|hatchling) " && echo OK'
  docker run --rm --entrypoint python localhost:5001/vectra/product-metrics:dev -c 'import vectra_product.main; print("OK-entrada")'
  grep -c '^FROM ' product-metrics/Dockerfile; grep -cE '^FROM .*@sha256:[0-9a-f]{64}' product-metrics/Dockerfile
  uv run lint-imports --config product-metrics/.importlinter
  test -s product-metrics/docs/imagenes.md
  ```
  Esperado: `hadolint` en 0; `65532:65532 ["python","-m","vectra_product.main"]`; `OK`; `OK-entrada`; los dos conteos de `FROM` iguales; `Contracts: 3 kept, 0 broken`; código 0. Si `hadolint` no está en `platform/.tools/bin` del worktree, ver «Notas».
  **Hoy falla:** no hay `Dockerfile` ni target `image` (`test -f product-metrics/Dockerfile` da 1). El import-linter ya pasa.

- [ ] **CA-2** — Paso 11: render, esquema y `conftest` del chart.
  ```bash
  for env in kind staging prod; do uv run python platform/tests/integration.py --chart product-metrics/chart --namespace vectra-app --env $env --out /tmp/u11-$env; done
  for env in kind staging prod; do platform/.tools/bin/kubeconform -strict -summary -schema-location default -schema-location 'product-metrics/tests/fixtures/crds/{{.ResourceKind}}.json' /tmp/u11-$env/*.yaml; done
  for env in kind staging prod; do platform/.tools/bin/conftest test --policy product-metrics/policies/conftest /tmp/u11-$env/*.yaml; done
  uv run pytest product-metrics/tests/unit/test_chart.py -v
  ```
  Esperado: código 0 y `Invalid: 0` en los tres entornos. El render tiene exactamente estos documentos: `Deployment`, `Service`, `PodDisruptionBudget`, `ServiceAccount`, `ExternalSecret`, `ServiceMonitor`, `PrometheusRule` y dos `ConfigMap` (parámetros y dashboard). `test_chart.py` tiene un caso por regla que falla con una mutación del render. Como mínimo:
  - réplicas distintas de 2; sin `vectra.io/hpa-exempt`, o con la justificación vacía; un `HorizontalPodAutoscaler` en el render;
  - estrategia distinta de `RollingUpdate` con `maxSurge: 1` y `maxUnavailable: 0`; `progressDeadlineSeconds` ≠ 4800; `terminationGracePeriodSeconds` ≠ 10;
  - sin PDB o con `minAvailable` ≠ 1; sin spread por zona; `priorityClassName` ≠ `vectra-normal`; sin `vectra.io/criticality`;
  - limits distintos de 500m / 512 MiB o request de CPU ≠ 100m; request de memoria ≠ 256 MiB en staging o prod; en kind, distinto del de P-1; `values-kind.yaml` con algo más que ese request;
  - `livenessProbe` que no es `/healthz` en 8081; `readinessProbe` que no es `/readyz` en 8081; un `startupProbe`;
  - `Service` con otro puerto además de 8081 (por ejemplo 8080); sin `publishNotReadyAddresses: true`; `Service` con un nombre distinto del `job` de las alertas;
  - `automountServiceAccountToken` distinto de `false` en la `ServiceAccount` o en el pod;
  - el `ConfigMap` montado con `subPath`; sin `checksum/config`, o con uno que no es el sha256 del `data`;
  - un `Server` o una `AuthorizationPolicy` en el render (P-3); un `Secret` en el render;
  - imagen sin digest; sin `runAsNonRoot` o sin `readOnlyRootFilesystem`.

  **Hoy falla:** `chart/` solo tiene `values-product-metrics-policy.yaml` y `templates/.gitkeep`; no hay `Chart.yaml`.

- [ ] **CA-3** — Paso 11: identidad, variables, sondas y parámetros.
  ```bash
  uv run pytest product-metrics/tests/unit/test_chart.py -k "identity or env or probes or params or checksum" -v
  uv run python -c "import sys; sys.path.insert(0, 'platform/kind'); import vault_paths as v; assert 'product-metrics' in v.service_account_clients(); print('OK-boveda')"
  grep -nE "clientId: product-metrics$" identity-edge/keycloak/realm/realm.kind.yaml
  uv run pytest product-metrics/tests/unit/test_params.py product-metrics/tests/unit/test_config.py -v
  ! grep -nE "hours <= 0" product-metrics/src/vectra_product/params.py
  ```
  Esperado: código 0 y `OK-boveda`. Las pruebas comprueban sobre el render de los tres entornos:
  - el conjunto de variables del contenedor es el de `process.md`; `VECTRA_CLIENT_ID` vale `vectra_product.config.CLIENT_ID` y la ruta de los parámetros es `vectra_product.params.POLICY_PATH`, los dos **importados**;
  - `VECTRA_CLIENT_KEY_PATH` apunta a un archivo del volumen del `ExternalSecret`, montado de solo lectura; el `ExternalSecret` lee `identity/clients/product-metrics`, propiedad `private-key`;
  - `VECTRA_REGISTRY_URL` apunta al Service y al puerto de F28 de `flows.yaml`, leídos del archivo;
  - ninguna variable lleva el nombre de una constante de `config.py` (por ejemplo `CYCLE_SECONDS` o `FULL_PASS_DEADLINE_SECONDS`);
  - las rutas de las sondas son rutas que sirve `vectra_common.ops_server`;
  - S de `RuidoExplicacion` es `noise_sustain_days` del `ConfigMap` renderizado;
  - **paridad de rangos:** la misma tabla pasa por `params.parse` y por `conftest`, con el mismo veredicto en cada fila. Filas mínimas: el archivo actual (pasa); `noise_floor` 0, 1 y `"0.6"`; `noise_sustain_days` 0, 15, 3.5 y `true`; `noise_min_decisions` 29 y `"50"`; `target_complete_response` 1.1 y −0.1; `target_origination_hours` 0 y −1; `target_origination_ratio` 1.5; `target_sustained_ratio_month6` 2; `target_north_star` 1.2, `"x"` y `null` (pasa); una clave de menos y una de más.

  Rojo de cada caso en la bitácora: quitar `VECTRA_TOKEN_URL` del `Deployment`, cambiar el `clientId`, montar la llave sin `readOnly`, poner `/livez`, subir `NOISE_SUSTAIN_DAYS_MAX` a 15 en `config.py` sin tocar la regla.
  **Hoy falla:** no existe `test_chart.py`, y el último `grep` encuentra `params.py:69` (C-1). Las órdenes de la bóveda y del realm ya pasan.

- [ ] **CA-4** — Pasos 10 y 11: el contenedor real arranca con lo que pone el chart.
  ```bash
  uv run pytest product-metrics/tests/integration/test_image.py -v
  ```
  Esperado: código 0. La prueba toma las variables y el `data` del `ConfigMap` de parámetros del render de kind (CA-2). Solo cambia las URLs por las de dobles HTTP locales del registro y del emisor de token (`tests/doubles/http_servers.py`, U11-T02) y la llave por una de prueba en la misma ruta. Corre la imagen de CA-1 con `docker run --read-only --user 65532:65532`:
  - `/healthz` responde 200 enseguida; `/readyz` pasa de 503 a 200 cuando termina la primera pasada; `/metrics` trae `vectra_product_north_star_decisions` y ninguna serie `vectra_product_*` fuera de la allowlist;
  - `docker stop` (SIGTERM, 10 s de gracia): el contenedor sale con código **0** en ≤ 10 s;
  - sin `VECTRA_REGISTRY_URL`: sale con código 3 y el log trae `registry_url_missing`;
  - con `noise_sustain_days: 15` en el archivo montado: sale con código 2 sin servir nada;
  - ninguna línea del log se queda solo con `level`, `timestamp` y `service` (C-6).

  Si Docker no está disponible, la prueba **falla**; no se salta. No uses el 8081 del host como puerto fijo (otros agentes corren servicios en la misma máquina): publica un puerto libre, como `bias-monitoring/tests/integration/test_image.py`. Registra en la bitácora el `docker run` exacto, su salida y la memoria del contenedor tras la primera pasada.
  **Hoy falla:** no hay imagen ni prueba.

- [ ] **CA-5** — Paso 11: admisión de U1 en los tres entornos.
  ```bash
  make -C platform check-chart CHART=product-metrics/chart NAMESPACE=vectra-app
  platform/.tools/bin/kyverno test platform/policies/kyverno
  ```
  Esperado: código 0, Kyverno con `fail: 0`, y `conftest` de `platform/policies/rego` (incluido `--namespace hpa`, que admite la exención) en 0. La segunda orden incluye los casos `product-metrics` (pasa) y `product-metrics-no-exempt` (falla) de `require-hpa-bounds`. Si `check-chart` entra en pánico por recursos repetidos entre entornos (candidata conocida: el chart tiene PDB), la vía es `make -C product-metrics policy-chart-u1`, con un entorno por directorio, como `bias-monitoring/Makefile`; regístralo.
  **Hoy falla** la primera orden (el chart no rinde). La segunda ya pasa.

- [ ] **CA-6** — Paso 11: cuota, flujos, `metrics-8081` y `CODEOWNERS`.
  ```bash
  uv run python platform/policies/quotas/render.py --check \
    && uv run pytest "platform/tests/test_integration.py::test_every_workload_declares_requests_and_limits_and_fits_the_quota" -v \
    && uv run python platform/network/generate.py --check && uv run pytest platform/network/tests -v \
    && for id in F28 F50 F60; do grep -q "id: $id," platform/network/flows.yaml || echo "falta $id"; done \
    && grep -nE "id: F28, from: \[product-metrics\], to: \[decision-registry-service\], port: 8080" platform/network/flows.yaml \
    && grep -cE "id: U11, from: (product-metrics|case-service)," platform/network/forbidden.yaml \
    && grep -n "U11: { requests: \[0.78, 1.05\], limits: \[3.9, 2.44\] }" platform/policies/quotas/quotas.yaml \
    && grep -nE "^\*\*/values-product-metrics-policy\.yaml " ../.github/CODEOWNERS
  uv run pytest product-metrics/tests/unit/test_chart.py -k "codeowners or flows or quota or metrics_8081" -v
  git diff --exit-code origin/main -- platform/network platform/policies ../.github/CODEOWNERS
  ```
  Esperado: código 0, ninguna línea «falta», `3` en el conteo de `forbidden.yaml` y el `diff` vacío. Las pruebas de `test_chart.py`:
  - comparan las etiquetas y la `ServiceAccount` del render con `flows.yaml`;
  - recalculan el aporte a la cuota desde el render de `prod` y lo comparan con `quotas.yaml` (NFR-U11-14);
  - leen `platform/network/generated/<env>/vectra-app.yaml` y comprueban que el `Server` `metrics-8081` cubre el 8081 y que su `AuthorizationPolicy` solo admite la identidad de Prometheus (P-3);
  - comprueban la regla de `CODEOWNERS`.

  **Hoy:** la primera orden completa ya pasa (los `grep` se comprobaron al redactar). Falla la segunda: no existe `test_chart.py`.

- [ ] **CA-7** — Paso 12: reglas generadas.
  ```bash
  uv run python product-metrics/tools/gen_rules.py --check
  uv run pytest product-metrics/tests/unit/test_gen_rules.py -v
  make -C product-metrics rules
  platform/.tools/bin/promtool check rules product-metrics/observability/rules/product-metrics.rules.yaml
  git status --short product-metrics/
  ```
  Esperado: código 0 y el `git status` final vacío (regenerar no cambia nada). `test_gen_rules.py` comprueba:
  - las causas de la regla de desincronía son las de `FAIL_CLOSED_CAUSES_BY_CATEGORY["desincronia"]`; con una causa más en esa categoría (parche de la prueba), `--check` termina en 1;
  - una `:dedup` por clave de `collector.PRODUCT_SERIES`, con su nombre y su expresión, y ninguna de `OPERATION_SERIES`;
  - la salida es determinista;
  - con el archivo versionado editado a mano, `--check` termina en 1;
  - el `spec` de la `PrometheusRule` es idéntico en los tres entornos y es el archivo `product-metrics.rules.yaml`.

  **Hoy falla:** `tools/` solo tiene `.gitkeep`.

- [ ] **CA-8** — Paso 12: alertas con `promtool`.
  ```bash
  platform/.tools/bin/promtool test rules product-metrics/observability/rules/tests/*.yaml
  uv run python -c "import yaml; d = yaml.safe_load(open('product-metrics/observability/rules/product-metrics.rules.yaml')); a = [r['alert'] for g in d['groups'] for r in g['rules'] if 'alert' in r]; print(sorted(set(a)), len(a))"
  uv run pytest product-metrics/tests/unit/test_gen_rules.py -k "alert" -v
  ```
  Esperado: `SUCCESS` en cada archivo; `['ProductMetricsDegraded', 'ProductMetricsFullRecomputeMissing', 'ProductMetricsStale', 'RuidoExplicacion'] 6`; la prueba pasa (cuatro `alertname` exactos, cada regla con `severity: SEV3` y `runbook_url`, y las series crudas `vectra_product_*` solo en las dos alertas por réplica y como fuente de una `:dedup`). Hay un caso de `promtool` con nombre por cada viñeta de la aceptación del Paso 12 y por cada uno de «Precisiones». La bitácora lleva la tabla viñeta → archivo y caso.
  **Hoy falla:** `observability/rules/tests/` solo tiene `.gitkeep`.

- [ ] **CA-9** — Paso 13: dashboard.
  ```bash
  uv run pytest product-metrics/tests/unit/test_dashboards.py -v
  uv run python contracts/tools/forbidden_phrases.py product-metrics/observability/dashboards/*.json
  uv run python -c "import json; d = json.load(open('platform/observability/dashboards/operacion.json')); print(sum('vectra_product_cycles_skipped_total' in t['expr'] for p in d['panels'] for t in p['targets']), len(d['panels']))"
  uv run pytest platform/tests/test_platform.py -k "dashboards" -v
  git diff origin/main --stat -- platform/observability/
  ```
  Esperado: código 0; la segunda orden no imprime nada; `1 5`; el `diff` solo toca `operacion.json`. `test_dashboards.py` tiene, como mínimo, un caso que falla con cada una de estas mutaciones de `product.json`:
  - una serie `vectra_product_*` cruda en una expresión;
  - un `sum` sobre una serie que no es `:dedup` (NFR-U11-06);
  - una razón combinada con `avg` de `…_ratio`;
  - sin la nota de aproximación literal, o sin «sin target acordado»;
  - un panel de BR-U11-12 quitado;
  - un target escrito como número en vez de salir de `vectra:product_target:dedup`;
  - **mundo cerrado:** una serie que ninguna regla graba; una etiqueta que el `collector` no emite para esa serie; un `metric` fuera de `TARGET_METRICS`;
  - un panel de D4 que solo consulta `period="month"`;
  - un panel sin su periodo, o el dashboard sin la zona horaria de Colombia (BR-U11-08);
  - una serie de operación del ciclo en `product.json` (NFR-U11-41).

  Y sobre el render: el `data` del `ConfigMap` es el archivo canónico byte a byte, la etiqueta y la anotación son las del sidecar de U1, y la carpeta está en `folder-permissions.yaml` con los tres equipos de BR-U11-13.
  **Hoy falla:** no existen `product.json` ni `test_dashboards.py`, y la tercera orden imprime `0 4`.

- [ ] **CA-10** — Paso 13: runbooks.
  ```bash
  uv run python platform/tests/test_runbooks.py --root product-metrics
  ls product-metrics/observability/runbooks/*.md
  grep -ciE "señal de producto|no es una falla técnica" product-metrics/observability/runbooks/product-noise.md
  uv run python contracts/tools/forbidden_phrases.py product-metrics/observability/runbooks/*.md product-metrics/README.md
  ```
  Esperado: código 0; los cuatro runbooks de P-2 (a) y ninguno más; al menos `1`; la última orden no imprime nada. Cada `runbook_url` de las seis reglas apunta a un archivo que sigue la plantilla.
  **Hoy falla:** la primera orden da rc 1 con «product-metrics: sin alertas que revisar».

- [ ] **CA-11** — Paso 15: Application.
  ```bash
  uv run python vectra-risk-gitops/generate.py --check && uv run python platform/tests/test_waves.py \
    && for env in kind staging prod; do platform/.tools/bin/kyverno apply platform/policies/kyverno/disallow-argocd-auto-sync.yaml --resource vectra-risk-gitops/apps/$env/product-metrics.yaml; done \
    && grep -n "sync-wave" vectra-risk-gitops/apps/*/product-metrics.yaml \
    && grep -n "values-product-metrics-policy.yaml" vectra-risk-gitops/apps/*/product-metrics.yaml \
    && ! grep -rn "automated" vectra-risk-gitops/apps/*/product-metrics.yaml
  grep -c "values-kind.yaml" vectra-risk-gitops/apps/kind/product-metrics.yaml vectra-risk-gitops/apps/staging/product-metrics.yaml vectra-risk-gitops/apps/prod/product-metrics.yaml
  uv run pytest platform/tests/test_platform.py -k "every_component_is_in_its_wave or gitops_manifests_match_components" -v
  ```
  Esperado: código 0. Una Application por entorno, con wave `'5'`, sin `syncPolicy.automated` y con `values-product-metrics-policy.yaml` en sus `valueFiles`. Con P-1 = (b), el conteo de `values-kind.yaml` es `1` en kind y `0` en staging y prod.
  **Hoy:** `generate.py --check` y `test_waves.py` pasan (53, 50 y 52 Applications), pero no existe `apps/<env>/product-metrics.yaml` y los `grep` fallan.

- [ ] **CA-12** — Paso 15: trazabilidad (P-4 de la enmienda).
  ```bash
  uv run python platform/tests/test_traceability.py --unit product-metrics --all \
    && for n in $(seq -w 1 14); do git grep -qiE "BR-U11-$n([^0-9]|$)" -- product-metrics/tests product-metrics/observability/rules/tests || echo "BR-U11-$n sin prueba"; done
  uv run python platform/tests/test_traceability.py --all | grep -c "U11-"
  grep -n "^## Diferido por la demo" -A8 aidlc-docs/construction/product-metrics/evidence/cierre-demo.md
  grep -rnE "NFR-U11-0(2|3)([^0-9]|$)" product-metrics/; echo "rc=$?"
  ```
  Esperado: código 0 y ninguna línea «sin prueba»; `0` en el conteo de `--all` (y `--all`, sin `--unit`, cumple la regla «sin fallos nuevos» de `DECISIONES-LOOP.md` §6 frente a la base); la lista tiene exactamente las filas de NFR-U11-02 y NFR-U11-03; la última orden no imprime nada y da `rc=1`.
  **Hoy falla:** rc 1 con 16 identificadores (INF-U11-02 a 05; NFR-U11-02, 03, 05, 06, 13, 14, 32, 33, 41 y 42; P-U11-05 y 06), y 7 BR sin prueba (BR-U11-02, 04, 06, 08, 12, 13 y 14). No existe `evidence/cierre-demo.md`.

- [ ] **CA-13** — Presupuesto de memoria de kind.
  ```bash
  uv run python -c "import sys; sys.path.insert(0, 'platform/tests'); import test_kind_profile as t; print(round(t.requested_gib([*t.declared_inference_services(), *t.PEAK_INFERENCE_SERVICES]), 4), t.BUDGET_GIB)"
  uv run pytest platform/tests/test_kind_profile.py -v
  git diff origin/main -- platform/tests/test_kind_profile.py
  grep -nE "Proyecci[oó]n" aidlc-docs/construction/product-metrics/evidence/cierre-demo.md
  ```
  Esperado: la primera orden se corre **dos veces**, antes y después de agregar la Application, y las dos cifras quedan en la bitácora. La diferencia es el aporte de U11 (0,2891 GiB con P-1 = (b)). Las pruebas pasan. El `diff` solo cambia `BUDGET_GIB` y su comentario, con la cifra medida redondeada hacia arriba a 0,1 GiB y la cita de `DECISIONES-LOOP.md` §7. El cierre lleva la proyección con U8 y U10. Si la cifra no cuadra o la proyección llega a 13,0 GiB, es una **detención** (sección «Presupuesto»), no un ROJO del codificador.
  **Hoy:** la primera orden debe imprimir `10.3438 10.4` y las pruebas pasar. La cifra es la del comentario de `test_kind_profile.py` y la del cierre de U7; no se volvió a correr al redactar, porque el worktree de preparación no tiene `platform/.charts`. Con la Application agregada y sin tocar el tope, `test_the_profile_requests_fit_the_budget` falla: es el rojo esperado.

- [ ] **CA-14** — Candidatas C-1 a C-7.
  ```bash
  HYPOTHESIS_PROFILE=ci uv run pytest product-metrics/tests/integration/test_process.py product-metrics/tests/integration/test_main_process.py -v
  for i in 1 2 3; do uv run pytest product-metrics/tests -p no:cacheprovider -m "not volume" -q --cov=vectra_product.state --cov-branch --cov-report=term-missing | grep -E "state\.py"; done
  ! grep -n "capture_signals" product-metrics/src/vectra_product/main.py
  grep -n "add_signal_handler" aidlc-docs/construction/product-metrics/code/process.md
  git diff origin/main -- CANDIDATAS.md | grep -c "Atendida en U11-T03"
  ```
  Esperado: código 0; las tres líneas de `state.py` son **iguales** y no listan la rama de `incremental_after_full_failed` entre las que faltan; con P-6 = (a) el tercer `grep` no encuentra nada y `process.md` atribuye el código de salida 0 al manejador del bucle; al menos `7` en el conteo. La bitácora lleva el rojo de C-2 y de C-3: un `scheduler` que cancela la página en vuelo, el plazo cambiado a 90 min y el reinicio diario de `_retries` quitado hacen fallar, cada uno, una prueba con nombre.
  **Hoy falla:** `main.py:67-72` tiene `capture_signals`; ninguna prueba distingue los tres defectos de C-2 y C-3 (sobreviven, `revisiones/U11-T02/ronda-1.md`); la cobertura de `state.py` cambia entre corridas.

- [ ] **CA-15** — Paso 17: documentación.
  ```bash
  test -s product-metrics/README.md
  uv run python platform/tests/test_links.py --root product-metrics
  grep -c "\[INTERNO\]" product-metrics/README.md
  for s in "aproximación" "max without (instance, pod)" "/readyz" "02:30" "product-noise" "values-product-metrics-policy.yaml"; do grep -qF "$s" product-metrics/README.md || echo "falta $s"; done
  ```
  Esperado: código 0, al menos `1` y ninguna línea «falta». El README cubre lo que pide el Paso 17: qué mide cada métrica y qué no (la nota de aproximación de la sostenida; la tasa de consulta con su ventana móvil de 7 días y la cuenta de días bajo el piso, sin la ambigüedad de la línea 532 de `CANDIDATAS.md`), parámetros y targets **[INTERNO]**, ciclo de lectura, deduplicación, readiness (con lo que el código hace si U3 está caído al arrancar: 30 min, no «unos 15 s») y los runbooks, con un enlace relativo a cada uno. Dice también qué runbook quedó diferido.
  **Hoy falla:** no hay README (`test -s` da 1; `test_links.py` da rc 1 con «Sin Markdown que revisar»).

- [ ] **CA-16** — Paso 18: cierre.
  ```bash
  make -C product-metrics check && make -C platform check
  grep -nE "^## (Comprobado|Decisiones|Pendiente en U12|Diferido por la demo)" aidlc-docs/construction/product-metrics/evidence/cierre-demo.md
  grep -n "^check:" product-metrics/Makefile
  ```
  Esperado: código 0 y las cuatro secciones. El `check` de U11 corre, en orden: `lint`, `types`, `imports`, las pruebas con el perfil `ci`, la cobertura (100 % en `compute` y `noise`; ≥ 90 % en el resto), `gen_rules.py --check`, `rules` (deriva del archivo versionado y `promtool`), `image`, la prueba de imagen, el chart (CA-2 y CA-3), la admisión (CA-5), cuota y flujos (CA-6), runbooks, enlaces y trazabilidad. **Falla** si falta una herramienta (`promtool`, `helm`, `kubeconform`, `conftest`, `kyverno`, `hadolint`, Docker): no se salta con rc 0 (candidata F-02 de U04-T07; no copies el `rules` de `governance/Makefile`, que lo omite). Registra la duración y la carga de la máquina (`uptime`).
  **Hoy:** `make -C product-metrics check` pasa con sus cinco objetivos (`lint types imports test coverage`; ≈ 16 min en la corrida de U11-T02). Falla el `grep` del cierre.

- [ ] **CA-17** — RL-4: el `make check` de todas las unidades, una vez al cerrar U11.
  ```bash
  for u in contracts platform identity-edge decision-registry governance reference-model model-serving scoring-explainability bias-monitoring case-management console product-metrics; do uptime; make -C $u check || echo "FALLA $u"; done
  ```
  Esperado: ninguna línea «FALLA». Las unidades corren **en serie**: con la máquina cargada, las pruebas con límite de tiempo fallan. Si una unidad ajena falla y el fallo también ocurre en `origin/main`, regístralo con la salida y su causa: no es de esta tarea. El cierre cita las cifras (lección de U09-T04, F-02: el cierre sin la evidencia fue un NARANJA).

- [ ] **CA-18** — Estado del plan.
  ```bash
  git diff origin/main -- aidlc-docs/construction/plans/product-metrics-code-generation-plan.md | grep -E "^\+- \[.\] \*\*Paso 1[0-8] "
  git diff origin/main -- aidlc-docs/construction/plans/product-metrics-code-generation-plan.md | grep -E "^[-+]" | grep -vcE "^(\+\+\+|---) "
  ```
  Esperado: Pasos 10, 11, 12, 13, 15, 17 y 18 en `[x]` con `(U11-T03)` y su nota; Paso 14 en `[ ]` con «diferido por la demo (T4)»; Paso 16 en `[ ]` con «consolidado en U12 Paso 18 (enmienda §8)». El segundo conteo es `18`: nueve líneas quitadas y nueve puestas, ningún otro cambio en el texto del plan.
  **Hoy:** los nueve pasos están en `[ ]` sin nota.

---

## Plan de pruebas

Se escriben en esta tarea: `tests/unit/test_chart.py`, `test_gen_rules.py` y `test_dashboards.py`; `tests/integration/test_image.py`; los casos de `promtool` de `observability/rules/tests/`; y las pruebas de C-2, C-3, C-5 y C-6 en `tests/integration/`.

**Rojo primero**, con cada par falla-pasa en `bitacoras/U11-T03.md`. Para el rojo de una propiedad de Hypothesis usa el perfil `dev`; con `ci`, solo reducir el contraejemplo puede tardar más de 5 min (C-10). El verde siempre va con `ci`.

- `replicas: 1`, o sin `vectra.io/hpa-exempt` (`conftest` o el `rego` de U1 falla);
- `progressDeadlineSeconds: 600` y `terminationGracePeriodSeconds: 30`;
- `/livez` como liveness;
- un puerto 8080 en el `Service`; `publishNotReadyAddresses: false`;
- `automountServiceAccountToken: true`;
- el `ConfigMap` con `subPath`; el `checksum/config` fijo;
- un `Server` en el render;
- `noise_sustain_days: 15` en el archivo: falla `conftest` **y** el contenedor sale con 2 (CA-3 y CA-4);
- `NOISE_SUSTAIN_DAYS_MAX = 15` en `config.py` sin tocar la regla (la prueba de paridad falla);
- `VECTRA_TOKEN_URL` fuera del `Deployment` (CA-3 falla, y en CA-4 el contenedor no llega a `/readyz` 200);
- el `Service` renombrado (la prueba del `job` de las alertas falla);
- una causa nueva en la categoría `desincronia` (`gen_rules.py --check` termina en 1);
- una `:dedup` quitada del archivo generado (`--check` termina en 1, y la prueba de mundo cerrado falla si un panel la usa);
- `absent(…)` en lugar de `up … unless on (pod)` en la rama de ausencia (el caso «una réplica sin la serie y la otra con ella» falla);
- la rama de edad con `for: 30m` (el caso «dispara sin esperar un `for`» falla);
- sin el `unless` de la pasada en curso (el caso «la pasada en curso» falla);
- una quinta alerta en la `PrometheusRule` (el conteo de CA-8 falla);
- `sum(vectra_product_north_star_decisions)` en un panel;
- `period="montly"` (con la errata) en un selector del dashboard (mundo cerrado);
- un `runbook_url` hacia un archivo que no existe (`test_runbooks.py` falla);
- `syncPolicy.automated` en `apps/kind/product-metrics.yaml` (Kyverno falla);
- `wave: 4` en `components.yaml` (`test_waves.py` falla);
- `NFR-U11-05` en la lista de diferidos, y `NFR-U11-02` citado en el README (`test_traceability.py` falla las dos veces);
- `FROM python:3.12-slim` sin digest (el conteo de CA-1 no cuadra);
- `pytest` instalado en la imagen (la orden de CA-1 falla).

---

## Preguntas

**P-1 necesita la decisión del usuario antes de despachar.** En las demás, si nadie responde, rige la recomendación.

- **P-1 · Request de memoria de `product-metrics` en kind.** INF-U11-01 y NFR-U11-13 fijan 256 MiB por réplica «a confirmar con la prueba de memoria», y `deployment-architecture.md` dice que kind es igual a staging. La prueba de memoria está diferida (T3) y la máquina tiene 14 GiB.
  - (a) 256 MiB también en kind, la letra del diseño: U11 suma 0,54 GiB y `BUDGET_GIB` pasa a 10,9.
  - (b) **128 MiB solo en kind** (recomendada), con `chart/values-kind.yaml`: U11 suma 0,29 GiB y el tope pasa a 10,7. Mismo patrón que la opción (c) de `DECISIONES-LOOP.md` §7 para U6: solo el request, sin tocar réplicas ni limits (512 MiB), y staging y prod siguen en el diseño. P-U11-04 estima unos 15 MB de estado con 70 000 decisiones, y kind tiene 2 000. La memoria real se comprueba en U12.
  - (c) Otra cifra que el usuario indique.

  Es una desviación del diseño para un entorno, como la de U6: por eso la decide el usuario.

- **P-2 · Runbooks (Paso 13; P-3 de la enmienda).** La fila 13 difiere los runbooks (T2), y P-3 dice «solo si `runbook_url` lo exige». Las cuatro alertas entran y cada una lleva `runbook_url` (INF-U11-05), que `test_runbooks.py --root product-metrics` exige con archivo.
  - (a) **Entran los cuatro de las alertas; se difiere `product-metrics-parameter-change`** (recomendada): es lo que hizo U4 con `CompensationEventPending`.
  - (b) Entran los cinco. El quinto es una página y el README lo enlazaría.
  - (c) Ninguno: las alertas van sin `runbook_url`. Contradice INF-U11-05 y deja en rojo la aceptación del Paso 13.

- **P-3 · `Server` y `AuthorizationPolicy`: el Paso 11 se contradice.** Su alcance (revisión del 2026-11-01), INF-U11-04 y `deployment-architecture.md` dicen que el chart **no** los declara. Su aceptación (revisión del 2026-10-10) pide a `conftest` «`Server` y `AuthorizationPolicy` de Linkerd en 8081 solo para Prometheus».
  - (a) **Rige el alcance y el diseño** (recomendada): la regla de `conftest` del chart exige que no haya ninguno, y «8081 solo para Prometheus» se comprueba sobre lo que U1 genera (`platform/network/generated/<env>/vectra-app.yaml`). Es la revisión más reciente.
  - (b) El chart declara los suyos. Duplica el `Server` `metrics-8081` de U1 sobre el mismo puerto.

  El codificador deja la corrección del texto de la aceptación como candidata.

- **P-4 · Archivos que el chart necesita y viven fuera de `chart/`.** §1 del plan pone las reglas en `observability/rules/` y el dashboard en `observability/dashboards/product.json`, y el Paso 13 dice que `product.json` «queda en su chart». Helm solo lee con `.Files` lo que está dentro del directorio del chart.
  - (a) **Copia en `chart/files/` con comprobación de igualdad** (recomendada): los archivos canónicos son los de `observability/` y los de `chart/files/` no pueden diferir (`gen_rules.py --check`, `make rules` y una prueba de bytes).
  - (b) Enlaces simbólicos dentro de `chart/`. Depende de cómo los resuelvan helm y el repo-server de Argo CD.
  - (c) Mover los canónicos a `chart/` y cambiar las rutas de las órdenes del plan.

- **P-5 · NFR-U11-13: ¿trazado o diferido?** `process.md` dejó abierto si NFR-U11-02, 03 y 13 iban a «Diferido por la demo». NFR-U11-13 tiene dos partes: los requests y limits (Paso 11, que entra) y su medición con 10 veces el volumen (Paso 7, diferida).
  - (a) **Se traza en el chart y la medición va como «no comprobado» en el cierre** (recomendada): un identificador de un paso que entra no puede ir en la lista (`DECISIONES-LOOP.md` §6), y la herramienta rechaza la fila si el chart lo cita. Es lo que U7 hizo con NFR-U7-03.
  - (b) Va en la lista y ni el chart ni las reglas lo citan. Deja sin traza los recursos del `Deployment`.

- **P-6 · `_OpsServer.capture_signals` (C-4).** El revisor de U11-T02 midió que el manejador del bucle (`loop.add_signal_handler`) basta para salir con 0, que el override es redundante y que ninguna prueba lo ejerce; el docstring de `main.py` y `process.md` le atribuyen el código 0.
  - (a) **Quitar el override y corregir los dos textos** (recomendada), si las pruebas del proceso real (código 0 tras `SIGTERM` con una página en vuelo, C-2) y la del contenedor (CA-4) siguen en verde.
  - (b) Dejarlo y corregir solo los textos. Rige también si con (a) alguna de esas pruebas falla; en ese caso la bitácora dice cuál y por qué, y `capture_signals` deja de ser «redundante».

---

## Notas

- **Orden sugerido**, para que lo que sostiene D4 quede primero: C-1 → chart (Paso 11) → `gen_rules.py` y reglas (Paso 12) → `product.json` (Paso 13) → imagen y contenedor real (Paso 10, CA-4) → Application y memoria de kind (Paso 15) → runbooks y README → candidatas de pruebas (C-2, C-3, C-5, C-6, C-7) → trazabilidad y cierre.
- **`platform/.tools` no está versionado** (C-9): en un worktree nuevo, `make -C platform check` y las órdenes con `platform/.tools/bin/` fallan. Enlaza o copia `platform/.tools` y `platform/.charts` del checkout principal y compara las versiones con `platform/tools.env` antes de empezar. Regístralo en la bitácora.
- **Presupuesto de kind:** ver la sección del Alcance. Registra la cifra con y sin U11, el desglose por unidad y la proyección.
- **Otros codificadores en paralelo** (U8 y U10): no toques sus directorios. Si otra tarea toca a la vez `components.yaml`, `test_kind_profile.py`, `EXPECTED_WAVES` o el siguiente digest de ejemplo, el orquestador resuelve el conflicto al integrar; tú partes de la base de tu rama.
- **Puertos:** ninguna prueba usa el 8080 ni el 8081 del host como puerto fijo.
- **Nombres que rompen las herramientas:** nada de directorios `generated`, `rendered` ni `dist` dentro de `product-metrics/`; `test_runbooks.py` tampoco mira dentro de `tests/`.
- Archivos que se modifican en su sitio:
  - en `product-metrics/`: `Makefile`, `src/vectra_product/config.py`, `params.py` y `main.py` (solo C-1, C-4 y C-6), `tests/` y `chart/`;
  - `vectra-risk-gitops/components.yaml` y lo generado;
  - `platform/tests/test_kind_profile.py` (solo `BUDGET_GIB`), `platform/tests/test_platform.py` (solo `EXPECTED_WAVES[5]`) y `platform/observability/dashboards/operacion.json` (solo el panel nuevo);
  - `aidlc-docs/construction/product-metrics/code/process.md` (P-6), el plan (casillas) y `CANDIDATAS.md`.
- Archivos nuevos: los de «Estructura de destino» y `aidlc-docs/construction/product-metrics/evidence/cierre-demo.md`.
- **Candidatas nuevas que la tarea debe dejar en `CANDIDATAS.md`:** el texto del Paso 12 que nombra tres alertas; la aceptación del Paso 11 que pide `Server` y `AuthorizationPolicy` (P-3); la ubicación de los archivos del chart en §1 del plan (P-4); el arranque de `product-metrics` antes que el registro en la wave 5.
- Docker está disponible para construir y correr la imagen.
- **Bitácora:** `bitacoras/U11-T03.md`, con:
  - los pares falla-pasa;
  - la tabla viñeta del Paso 12 → caso de `promtool`;
  - la lista de diferidos razonada y la justificación de cada identificador trazado;
  - la fuente de los CRD de fixture;
  - el `docker run` de CA-4, su salida y la memoria del contenedor;
  - la memoria de kind (dos mediciones y proyección);
  - la decisión de P-1 a P-6;
  - la duración de cada `make check` con su `uptime`.
