# Ronda 1 — U06-T02

VEREDICTO: NO-VERDE

Punta revisada `edc0b8f` (base `bc8158a`). Worktree limpio antes y después de la revisión. Ningún ROJO. Un NARANJA: rompe el
explicador en el Paso 11. Fuente de KServe consultada: `git clone --branch v0.21.0` de `kserve/kserve`.

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Render por perfil, CRD y políticas | `helm template` ×3 + `kubeconform -strict` con el CRD; `conftest test --policy model-serving/policies/conftest` | pasa: Valid 5/3/3; `319 passed`, exit 0. `test_chart.py` (mutación por cada `# regla:`) dentro de los 126 de CA-5 |
| 2 | Esquema y los cuatro PR | `pytest test_promotion_renders.py -v`; `test -s` ×2; `helm template … values-invalid.yaml; test $? -ne 0` | pasa: `14 passed in 13.80s` (lee el render, no solo el código de salida); exit 0 |
| 3 | Flujos por etiqueta | `generate.py --check && pytest platform/network/tests`; `pytest test_flows_labels.py -v` | pasa: `211 passed in 22.10s`; `9 passed` (F19, F22, F30, F46 y X08) |
| 4 | Application y admisión | `vectra-risk-gitops/generate.py --check && test_waves.py && kyverno apply …` ×3 | pasa: kind 50, staging 49, prod 47; `pass: 1, fail: 0` ×3; wave `'6'`, sin `automated` |
| 5 | Cobertura y trazabilidad | `pytest model-serving/tests --cov=… --cov-branch --cov-fail-under=90`; `test_traceability.py --unit model-serving --all` | pasa: `126 passed` (sin omitidos) en 110 s, 92,15 %; `package_loader.py 70 0 20 0 100%`; 24 identificadores |
| 6 | `check` de la unidad y de U1 | `make -C model-serving check` (2 min 11 s) y `make -C platform check` (9 min 49 s) | pasa: exit 0 y exit 0 (`789 passed`, `81 tests passed`) |
| 7 | Casillas del plan | `git diff bc8158a -- …/model-serving-code-generation-plan.md` | pasa: 6, 7, 8 y 10 `[x] (U06-T02)`; 9 `[ ] (diferido por la demo (T2))` |

## Hallazgos

### F-01 · NARANJA · `model-serving/chart/templates/inferenceservice.yaml:89-90` · El explicador arranca sin `command` y KServe le agrega `args`
En v0.21.0, `CustomExplainer.GetContainer` (`pkg/apis/serving/v1beta1/explainer_custom.go:70-95`) **siempre** agrega a `containers[0]`
los argumentos `--model_name <isvc> --predictor_host <pred>.<ns> --http_port 8080`, y `Explainer.Reconcile` (`components/explainer.go:120-126`)
los escribe en el pod. La imagen de U06-T01 solo declara `CMD ["python", "-m", "vectra_explainer"]` (`explainer/Dockerfile:26`), y
`python:3.12-slim` no tiene `ENTRYPOINT`. En Kubernetes, `args` sin `command` reemplaza el `CMD`: el contenedor ejecutaría `--model_name`
y quedaría en `CrashLoopBackOff`. Todo `profile: prod` e `inactive` tendría el explicador caído, y `:explain` dejaría de funcionar en el Paso 11.
El predictor no tiene este problema: `CustomPredictor.GetContainer` no agrega argumentos.
Corrección dentro del alcance: `command: ["python", "-m", "vectra_explainer"]` en el contenedor del explicador (y, por simetría, el del
predictor), junto con una regla de `conftest` que exija `command` y su caso de mutación. `vectra_explainer.__main__` no lee `sys.argv`,
así que los argumentos que agrega KServe se ignoran.

### F-02 · AMARILLO · `inferenceservice.yaml:65`, bitácora y `CANDIDATAS.md` · La anotación `storage-initializer-sourceuri` no tiene efecto
`internal.serving.kserve.io/storage-initializer-sourceuri` está en `ServiceAnnotationDisallowedList` (`pkg/constants/constants.go:548-554`), y
el controlador la filtra de las anotaciones del componente (`explainer.go:98`). Lo que sí funciona es la variable `STORAGE_URI` del
`kserve-container`: `GetStorageUri()` de `CustomPredictor` y de `CustomExplainer` la lee y el controlador vuelve a escribir la anotación
(`explainer.go:78-83`). Ya comprobé en el código fuente algo que la candidata dejaba abierto: el storage initializer **sí** se inyecta en
el explicador. También comprobé que declarar antes el volumen `kserve-provision-location` y el montaje en `/mnt/models` no causa
duplicados (`pkg/utils/storage.go:76-160` deduplica por nombre). Ojo: el inyector reescribe `STORAGE_URI` a `/mnt/models` dentro del pod
(`storage_initializer_injector.go`, bucle sobre `CustomSpecStorageUriEnvVarKey`). Hoy no rompe nada, porque `service.py` usa
`MODEL_DIR`. Conviene quitar la anotación, o comentarla como redundante, y corregir el texto de la candidata.

### F-03 · AMARILLO · bitácora, CA-4 · «`check-chart` falla con `pass: 0`» es impreciso
`make -C platform check-chart CHART=model-serving/chart` primero entra en **pánico** (`panic: serviceaccounts "kserve-model" already exists`,
porque junta los tres entornos). Es el caso que la nota de CA-4 ya anticipaba. Al aplicar `STATIC_POLICIES` a un solo entorno con un
`InferenceService` `prod`, confirmé `pass: 0, fail: 0`. La sustitución por `policy-chart-u1` es aceptable: las políticas estáticas
seleccionan Pod/Deployment, que este chart no renderiza, y Kyverno las aplica en el clúster sobre el `Deployment` que genera KServe.

### F-04 · AMARILLO · `nfr-design-patterns.md:22` · «primeros 8 hex» en el diseño
El chart usa los 8 hex **finales** (`trunc -8`), igual que `isvc_name` (`governance/src/vectra_governance/api.py:212-214`) y que el
patrón `^isvc-[0-9a-f]{8}$` de los contratos. Como `mv-<fecha>-<8 hex>` tiene un solo bloque de 8 hex, la decisión es correcta. El
texto del diseño induce a error: conviene una enmienda de redacción (no es de esta tarea).

## Dictámenes pedidos

1. **Esquema.** Sirve tal como está para U04-T05b. Expresa los cuatro PR con ediciones mínimas de `profile` o de la lista:
   promoción = agregar `prod`; post-activación = `prod→inactive` (1 réplica); rollback = `inactive→prod` (mínimos 2/2);
   retiro = quitar `inactive`. Coincide con el Paso 12 de governance y con INF-U4-05 (`staging`: solo predictor, 1 réplica,
   `vectra-low`, en `vectra-staging`; la clave es la pareja versión/namespace, así que caben la activa y la candidata en staging).
   El nombre con los 8 hex finales es coherente con governance (ver F-04). Que `storageUri` sea el **directorio** coincide con
   governance, que lee el paquete desde `manifest_uri.rsplit("/", 1)[0]` (`api.py:243`), y con `reference-model/docs/release.md:63`
   (`model-store/${MV}/`). U04-T05b debe derivarlo así: `dirname(manifest_uri) + "/"`.
2. **Ediciones fuera de U6: las tres se ratifican.** `EXPECTED_WAVES 6: {"model-serving"}` es una consecuencia obligada:
   `test_every_component_is_in_its_wave` compara contra `components.yaml`, y sin esa línea CA-6 falla. Hay precedente idéntico en `ad868d4`
   (U03-T05, `decision-registry`). La línea del README reemplaza una nota que la entrada wave 6 dejaba falsa. La prueba de
   `test_package_loader.py` solo agrega un test, sin tocar código de producción, en la misma unidad. Cierra la rama 82, que CA-5 exige
   al 100 %, y lo comprobé corriendo la cobertura.
3. **Plantilla sin `ServingRuntime`.** Es válida para el CRD y el controlador de v0.21.0: `kubeconform` pasa; `autoScaling` con
   `behavior`, `autoscalerClass: none` (`AutoscalerClassNone`) y el modo `RawDeployment` (`platform/operators/kserve.yaml`) están
   soportados, y el storage initializer se inyecta por `STORAGE_URI`. El riesgo serio es F-01. **Credencial `minio-kserve`: con lo que
   entrega U1, el flujo base de la demo se rompe en kind.** `CreateSecretVolumeAndEnv` solo reconoce un Secret S3 si tiene la clave
   `AWS_SECRET_ACCESS_KEY`, o la que configure `credentials.s3.s3SecretAccessKeyName` (`pkg/credentials/service_account_credentials.go:282-294`).
   El endpoint sale de la anotación `serving.kserve.io/s3-endpoint` o de `credentials.s3.s3Endpoint`. U1 entrega `accessKey`/`secretKey`
   sin anotaciones, y `kserve.yaml` solo fija `deploymentMode`. El init container quedaría sin credenciales y apuntando a AWS, así que
   ningún predictor llegaría a Ready. Es un defecto de U1, fuera del alcance de esta tarea (prohibido tocar U1), y está bien reportado:
   es tarea candidata **bloqueante para U06-T03**.
4. **`check-chart` con `pass: 0`, cubierto por `policy-chart-u1`.** Aceptable. Ver F-03.
5. **Presupuesto de kind.** Hoy `requested_gib()` = **6,012 GiB**, con `BUDGET_GIB` = 6,1 (margen ≈ 0,09 GiB). Cada pod de
   `vectra-serving` pide 512 Mi + 20 Mi de proxy. Perfil `prod` de M1: 4 pods = **+2,08 GiB → 8,09 GiB**. Promoción (M1+M2 en `prod`):
   **+4,16 → 10,17 GiB**. Tras la post-activación (M2 `prod` + M1 `inactive`): **+3,12 → 9,13 GiB**. El predictor de staging suma
   0,27 GiB más. Además, `requested_gib()` solo cuenta Deployment, StatefulSet, DaemonSet, Cluster y Prometheus/Alertmanager, así que **no ve los
   `InferenceService`**: U06-T03 tiene que sumarlos aparte o extender el cálculo. No se cambió `BUDGET_GIB` ni el perfil.

## Tareas candidatas (defectos reales fuera de alcance)
- **U1, bloqueante para U06-T03:** credencial S3 de KServe. Hace falta `credentials.s3` en `platform/operators/kserve.yaml`
  (`s3AccessKeyIDName: accessKey`, `s3SecretAccessKeyName: secretKey`, `s3Endpoint` de MinIO, `s3UseHttps: "0"`) o anotar el Secret
  `minio-kserve`. Detalle en el dictamen 3.
- U1: `check-chart` para charts que solo traen CR (`pass: 0`) y el pánico con recursos repetidos entre entornos (misma clase que la candidata de U04-T05).
- U6 (U06-T03): sumar los `InferenceService` al cálculo del presupuesto de kind (cifras en el dictamen 5).
- U6 (diseño): cambiar «primeros 8 hex» por «8 hex finales» en `nfr-design-patterns.md:22`.
- U4/U6: la prueba de sincronía predictor ↔ explicador de `model-validation-job` (Paso 13 de U4) no tiene explicador en staging. Ya está abierto en INF-U6-02 §3.

## Rutas de transcripciones largas
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/platform-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/ms-check.log
- /tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/checkchart.log
