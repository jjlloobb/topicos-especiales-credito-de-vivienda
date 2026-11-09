# Ronda 1 — U04-T05 (solo Paso 13; Paso 12 → U04-T05b por decisión del usuario)

VEREDICTO: NO-VERDE (ningún ROJO; cinco NARANJA, que por RL-1..RL-5 no bloquean la fusión)

Rama `tarea/U04-T05` @ `cac7b07`, base `be3eec8`. Worktree limpio al terminar (`git status --short` vacío).

## Criterios de aceptación, verificados por mí
| # | Criterio | Comando que corrí | Resultado |
|---|---|---|---|
| 1 | Paso 12 | — | fuera de esta tarea (`decision-paso-12.md`) |
| 2 | Paso 13, pruebas del Job | `uv run pytest governance/tests/unit/test_validation_job.py -v` | pasa, 22 passed en 25 s, 0 omitidas |
| 3 | Plantilla y chart mínimo | `uv run pytest .../test_validation_job_template.py -v`; `helm template ... \| grep -nE ...` | pasa, 5 passed (la de helm corrió, no se omitió); grep: líneas 4, 11 y 16, rc 0 |
| 4 | Imagen | `make -C governance image-validation`; `docker image inspect` (usuario); `docker run ... import onnxruntime, vectra_disparity`; `grep '^FROM .*@sha256'` | pasa: build rc 0 (1 min), `65532:65532`, `OK`, los 2 `FROM` por digest. Además `--read-only` → `missing_env:VECTRA_JOB_MODE`, rc 1, sin escribir |
| 5 | `check` de U4 y U1 | `make -C governance check`; `make -C platform check` → falla en `check-tools` (no hay `platform/.tools`); respaldo `uv run pytest platform/tests/test_ci.py ...` | pasa: 285 passed en 135 s (ruff, mypy --strict 25 archivos, import-linter; promtool omitido, el diff no toca reglas); respaldo 274 passed |
| 6 | Estado del plan | `git diff origin/main -- <plan> \| grep ...` | pasa: 12 `[ ]` con nota de U04-T05b, 13 `[x] (U04-T05, acotado a la demo)`, 14 y 15 con su nota. Solo esas 4 líneas cambian |
| — | `--all` (DECISIONES-LOOP §6, enmienda) | `test_traceability.py --all` en la rama y en `git archive be3eec8` | rc 1 en las dos; la rama no tiene ningún fallo nuevo y quita `INF-U4-01`. Ver F-05 |
| — | hadolint (v2.15.1 = `tools.env`) | `<checkout principal>/platform/.tools/bin/hadolint governance/validation_job/Dockerfile` | **falla**: DL3008, rc 1 (F-04) |
| — | Admisión del Job | `job_manifest()` con imagen `kind-registry:5000/...@sha256` → `kyverno apply` (12 políticas de `check-chart`) y `conftest` | pasa: kyverno pass 8 / fail 0; conftest 7/7. Chart: conftest 14/14 |

## Hallazgos

### F-01 · NARANJA · `vectra_validation/disparity.py:33-36` · `initial_disparity` mide «score bajo el corte», no la tasa favorable del diseño
El Job cuenta `favorable` si `p < cutoff`. El diseño no deja ese criterio abierto:
- domain-entities §2.2 y BR-U4-07 piden la disparidad de la librería de U9;
- BR-U9-01 la define sobre **recomendaciones**, y `revision_requerida` cuenta como NO favorable;
- el `outcome` de la recomendación es el de BR-U7-04/05: reglas 1 a 3 (normativo nulo, tasa sobre la usura, `confidence < low_confidence_threshold`) → `revision_requerida`, y la regla 4 usa el `cutoff_efectivo` del canal;
- la propia librería lo dice (`vectra_disparity/counts.py:17`), y la candidata de U5 (`CANDIDATAS.md:249`) prohíbe expresamente `p < cutoff`.

Con este criterio, todo caso que iría a `revision_requerida` y tiene `p < cutoff` cuenta como favorable. Eso **subestima** la disparidad. Medido en U5: 4,83 pp con `p < cutoff` frente a 8,70 pp con el outcome completo, de un lado al otro del umbral de 5 pp, así que `rule_met` puede salir `false` para un modelo que sí lo cumple.

La prueba no puede detectarlo: el oráculo (`test_validation_job.py:141-144`) repite el mismo `p < 0.08`, así que solo prueba que la llamada a la librería es fiel.

Es implementable dentro del Paso 13:
- `domain_envelope.json` está en el mismo paquete que `feature_spec.json`;
- `proposed_rate_ea` viene en la fila;
- la política (`cutoff`, `channel_rules`, `low_confidence_threshold`, `normative`) la tiene governance y la pasaría el lanzador.

Referencia: `outcome_of` en `reference-model/src/vectra_reference/proxy.py:266`.

**Efecto en la demo D2:** no bloquea. El oráculo de RT-2 pide `initial_disparity` no vacía, y lo está. El congelamiento lo decide U9 con los outcomes reales del registro, no con este valor. Lo que sale mal es la cifra que lee el CRO en la aprobación y la que viaja en el paquete de freeze. Por eso NARANJA y no ROJO.

### F-02 · NARANJA · `vectra_validation/config.py:9-12` y `k8s_jobs.py:job_manifest` · Parámetros de decisión del informe como literales, y el lanzador no pasa ninguno
Ninguno de los cuatro valores contradice el diseño, pero los cuatro deciden algo y viven como literales en el código:

| Valor | Origen en el diseño | Problema |
|---|---|---|
| `auc_target` 0,85 | domain-entities §2.2 [INTERNO] | Coincide, pero decide `auc_meets_target` y está como literal |
| `n_min` 30 y `threshold_pp` 5 | BR-U9-13 | Coinciden, pero BR-U9-13 los hace values de Helm revisados por cumplimiento (`bias-monitoring/chart/values-monitoring-policy.yaml`). Aquí son una segunda fuente que no se entera de un PR de cumplimiento |
| `cutoff` 0,0800 | Ninguno: es la política sintética de U5 (`reference-model/config/generator.yaml:100`) | Decide el `outcome`. Contradice BR-U7-04: debe ser el `cutoff_efectivo` de la política de la versión |

`job_manifest` no emite `VECTRA_CUTOFF`, `VECTRA_N_MIN`, `VECTRA_THRESHOLD_PP` ni `VECTRA_AUC_TARGET`, así que en el clúster rigen siempre los literales.

Lo demás:
- `sync_check` con 200 filas y tolerancia 1e-4: la tolerancia es la de NFR-U6-01. Las 200 filas son una elección (NFR-U6-01 prueba 1 000 en U6) y no contradicen nada.
- `evaluated_on` por el reloj: correcto, porque `derive` lo necesita para la edad. Sin contradicción.

### F-03 · NARANJA · `k8s_jobs.py:job_manifest` · El Job no puede pedir su token: sin `VECTRA_CA_BUNDLE` ni la CA montada
El `DEFAULT_TOKEN_URL` es https. `vectra_common.deps._verify_context` exige `VECTRA_CA_BUNDLE`, y sin él lanza `ContractViolation`. `HttpReportSender.send` la convierte en `report_not_sent`: el Job sale con 1 y **nunca envía el informe**.

Lo reproduje con el `ServiceTokenProvider` real, sin `poster` de prueba, y el `DEFAULT_TOKEN_URL`:
```
error: report_not_sent | cause: ContractViolation VECTRA_CA_BUNDLE no apunta a un archivo: nunca se desactiva la verificacion
governance requests: 0
VECTRA_CA_BUNDLE in env: False | volumes: ['client-key', 'tmp']
```
Las pruebas lo esconden porque inyectan `poster`.

Así se hace en U3: `decision-registry/chart/templates/service.yaml:95,119` monta el ConfigMap `vectra-internal-ca`, que existe en `vectra-staging` (namespace con `vectra.io/mesh: enabled`). Ningún CA cae: se ve en kind (U04-T07). Sin arreglo, `rt2-setup` de D2 se queda en `en_validacion` hasta el timeout.

### F-04 · NARANJA · `governance/validation_job/Dockerfile:21` · hadolint falla (DL3008)
`apt-get install libgomp1` sin versión fijada; hadolint v2.15.1 sale con rc 1. `decision-registry/Dockerfile` pasa con rc 0, y los planes de las demás unidades exigen `hadolint` limpio. Hay dos salidas: fijar la versión de Debian de `libgomp1`, o `# hadolint ignore=DL3008` con su motivo.

### F-05 · NARANJA · Trazabilidad · `NFR-U4-23` sigue sin trazar aunque el Paso 13 lo cubre y lo prueba
`--all` cumple la primera condición de la enmienda: el fallo ya estaba en la base. Pero la enmienda también dice: «un identificador de un paso que la tarea cubre debe quedar trazado».

NFR-U4-23 (`runAsNonRoot`, `readOnlyRootFilesystem`, `automountServiceAccountToken: false`) está en «Diseño» del Paso 13, y `test_validation_job_template.py:59-72` lo verifica, pero no lo nombra. Basta con citarlo. NFR-U4-12 es de kind, a cargo del operador, y NFR-U4-20/21 son del Paso 12: no cuentan.

### F-06 · AMARILLO · `vectra_validation/run.py:73-79` · `sync_check` compara el modelo consigo mismo
Se pasa `model` como predictor y como explicador. Con XGBoost, `pred_contribs` siempre suma el margen, así que en la práctica solo puede fallar `version_mismatch`. No se contrastan `base_value`, `mode` ni `runtime` de `explainer.json` con el booster. Es defendible, porque el runtime del explicador es `pred_contribs`, pero el chequeo es más débil de lo que su nombre sugiere.

### F-07 · AMARILLO · Imagen (pregunta 5)
Cumple el Paso 13 y la admisión, salvo F-04. Tres observaciones:
- **Tamaño**: 1,15 GB, de los que 345 MB son `nvidia-nccl-cu13`.
- **Runtime del servicio**: la imagen lleva `fastapi`, `uvicorn`, `psycopg` y `SQLAlchemy`, porque instala `governance[validation]` entero.
- **Lock**: `pip` resuelve sin `uv.lock`. La imagen trae `protobuf` 7.36.2, mientras el lock y las pruebas usan 5.29.6. El pin `onnx==1.19.1` solo afecta al entorno dev: `onnx` no está en la imagen. Es el mismo patrón de `decision-registry/Dockerfile` (ver candidatas).

### F-08 · AMARILLO · `disparity.py:17` · `FAVORABLE = "favorable"` duplica `vectra_disparity.FAVORABLE`.

## Preguntas del despacho
1. **Criterio de `outcome`**: F-01, NARANJA. Subestima frente al diseño, pero no rompe RT-2.
2. **Valores no fijados**: F-02. `auc_target`, `n_min`, el umbral y la tolerancia salen del diseño; el `cutoff` no. Las 200 filas y `evaluated_on` no contradicen ningún diseño.
3. **Lo verificado en código y pruebas**:
   - librería real: `test_the_job_uses_the_real_library_and_not_a_double` y la lectura de `disparity.py`;
   - `source_comparison`: error, con `store.reads == []` y `sender.sent == []`; `main` sale con 1;
   - plantilla: lleva la anotación del sidecar nativo y los recursos de INF-U4-01, leídos de la tabla del diseño, con `vectra-low`, `automountServiceAccountToken: false` y RO rootfs. Pasa kyverno y conftest.
   
   La candidata F-03 de U04-T04 queda cerrada bien en lo suyo (prioridad y recursos). Falta la CA (F-03 de esta ronda).
4. **`e.get("value")` en `test_api_models.py:143` y `test_api_data_sources.py:147`**: legítimo. La nueva entrada `valueFrom` no tiene `value`, las aserciones solo leen claves con `value`, y la credencial se prueba aparte en `test_validation_job_template.py:79-83`.
5. **Imagen**: F-04 y F-07.

## Tareas candidatas (defectos reales fuera de alcance)
- Loop/U1: `make -C platform check-chart` hace que kyverno entre en pánico cuando los renders de los tres entornos repiten un recurso. Pasa también con `decision-registry/chart`: `poddisruptionbudgets.policy "decision-registry-service" already exists`. Hoy no puede verificar ningún chart.
- Todas las imágenes Python (`decision-registry`, `model-validation-job`) instalan con `pip` sin `uv.lock`: las versiones transitivas de la imagen no son las probadas.
- U4 (U04-T06): `DEFAULT_S3_ENDPOINT` y `DEFAULT_TOKEN_URL` de `k8s_jobs.py` deben venir del chart del Deployment, igual que `callback_url`.
- U6: el explicador de un predictor ONNX (anotado ya por el codificador).

## Rutas de transcripciones largas
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/ca5-governance.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/ca4-build.txt`
- `/tmp/claude-1000/-home-jjlloobb-IT-PUJ-MINSC-GitHub-topicos-especiales-credito-de-vivienda/a779b360-6db9-41e4-ab45-5158f150a043/scratchpad/trace-branch.txt` y `trace-base.txt`
