# Guía del operador: Paso 11 de U6 en kind

Paso 11 del plan de U6 (`aidlc-docs/construction/plans/model-serving-code-generation-plan.md`): verificar `model-serving` en `kind-vectra` con evidencia. Lo ejecuta **un operador** después de un PR aprobado (AUTONOMIA-01): el codificador no tocó el clúster.

Alcance de la demo (enmienda §3 U6, `demo-recorte-funcional.md` §4): entran los escenarios 1 (promoción, 0 `version_mismatch`), 2 (rollback, el activo nunca baja de 2 réplicas) y 3 (RT3-a/d no listos, RT3-b listo), más la memoria (DD-3 b). Se difieren el 4 (saturación), el 5 (drenado de zona) y el 6 (carga, T3).

Cada sección trae el **comando**, la **salida esperada** y la **ruta de evidencia** (`aidlc-docs/construction/model-serving/evidence/kind/<escenario>.md`, con `evidence/kind/_plantilla.md`). Todos los comandos corren desde `vectra-risk/`. Los scripts están en `model-serving/docs/kind/`: solo leen y no cambian nada en el clúster.

## 0. Requisitos previos

- `kubectl config current-context` es `kind-vectra`; `argocd login` funciona (`platform/runbooks/install.md` §6).
- U1 sano, y U2, U3 y U4 instalados (`kubectl get applications -n argocd` sin `Degraded`). U01-T08 en `main`: `Secret minio-kserve` con `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` en `vectra-serving` y `vectra-staging`, y `kserve.storage.s3` en la configuración de KServe.
- U04-T07 hecha: política activa y modelo de referencia registrado (P-7). U04-T05b (`promotion-tool`) en `main`.
- Herramientas: `bash platform/install-tools.sh`; `docker`; `uv`.
- Presupuesto: `uv run pytest platform/tests/test_kind_profile.py -v` en verde (kind pide 256 MiB por pod de serving, ver §6).
- Variables que usan las secciones: `M1` (el `model_version_id` activo) y `M2` (el de la versión que se promueve); `I1=isvc-<8 hex finales de M1>`, `I2=isvc-<…M2>`.

## 1. Imágenes

El chart usa `kind-registry:5000/vectra/model-predictor` y `…/model-explainer`, por digest. El digest de `chart/values.yaml` es de ejemplo.

```bash
make -C model-serving image-predictor image-explainer REGISTRY=localhost:5001 TAG=dev
for image in model-predictor model-explainer; do
  docker push localhost:5001/vectra/$image:dev
  docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/$image:dev
done
```

- **Esperado:** dos digests `localhost:5001/vectra/model-…@sha256:<64 hex>`. El registro no cambia el digest al ser visto como `kind-registry:5000`.
- **PR de digests (T1: sin firma):** en `vectra-risk-gitops/values/kind/model-serving.yaml` agrega **solo** las claves `images.predictor.digest` e `images.explainer.digest` (formato `sha256:<64 hex>`), sin tocar `inferenceServices` ni `profiles`:

  ```yaml
  images:
    predictor: { repository: kind-registry:5000/vectra/model-predictor, digest: sha256:<predictor> }
    explainer: { repository: kind-registry:5000/vectra/model-explainer, digest: sha256:<explainer> }
  ```

  Verifica con `helm template ms model-serving/chart -f vectra-risk-gitops/envs/kind/values.yaml -f vectra-risk-gitops/values/kind/model-serving.yaml` (sin `InferenceService` todavía; el esquema valida). Fusiona el PR.
- **Evidencia:** `evidence/kind/imagenes.md` (digests y el diff del PR).

## 2. Paquetes en el model-store

Procedimiento de `reference-model/docs/release.md` (pasos 1 a 3 y 5): `make -C reference-model release verify-release`, y `mc cp --recursive` de cada paquete a `kind/model-store/<model_version_id>/`.

| Para qué | Paquete de U5 | Ruta en el model-store |
|---|---|---|
| M1 | `reference-model/.out/package/` (el base, RT-1) | `model-store/<M1>/` (U04-T07 lo sube y lo registra) |
| M2 (promoción y rollback) | `reference-model/.out/proxy/run-1/` (u otra corrida `proxy/run-N`, solo kind y staging) | `model-store/<M2>/` |
| RT3-a, b, d | `reference-model/.out/adversarial/rt3/RT3-a`, `RT3-b`, `RT3-d` | `model-store/adversarial/rt3/RT3-a/` etc. (el segmento `adversarial/` solo es válido en `staging`, P-U6-03) |

```bash
export MV2="$(python3 -c 'import json; print(json.load(open("reference-model/.out/proxy/run-1/manifest.json"))["model_version_id"])')"
mc cp --recursive /out/proxy/run-1/ "kind/model-store/${MV2}/"
for case in RT3-a RT3-b RT3-d; do mc cp --recursive "/out/adversarial/rt3/${case}/" "kind/model-store/adversarial/rt3/${case}/"; done
mc ls "kind/model-store/${MV2}/"                       # 7 archivos
mc ls kind/model-store/adversarial/rt3/RT3-a/           # 7 archivos
```

- **Registro de M2 en governance:** como en `reference-model/docs/release.md` §4 y la guía de U04-T07 (`POST /v1/models`, validación, informe y `…/approval`); los RT-3 **no** se registran (governance rechaza a, c y d con 422: ese es el caso del escenario 3). Si governance rechaza `proxy/run-1`, prueba otra `proxy/run-N` y **anota cuál** (la tarea pide registrar la elección).
- **Esperado:** M1 y M2 en estado `aprobado`/`activo` según corresponda; `mc ls` con 7 archivos por paquete.
- **Evidencia:** `evidence/kind/paquetes.md` (salidas de `mc ls`, el paquete elegido para M2 y su `model_version_id`).

## 3. Escenario 1: promoción M1 → M2 con tráfico continuo

**Esperado:** 0 respuestas `version_mismatch` durante toda la ventana; cada respuesta trae el `model_version_id` del `InferenceService` que la sirvió.

Con U7 (`scoring-service`) ausente, el tráfico va directo a `:predict` de cada `InferenceService`; la parte con U7 queda pendiente de U7 Paso 18.

**Payload.** Un `{"instances": [<FeatureVector>]}` válido: toma las características de un caso RT-1 de `reference-model/.out/adversarial/` o arma uno con `feature_spec.json` del paquete (la forma está en `model-serving/tests/serving_helpers.py`, `feature_vector_json`). Guárdalo fuera del repositorio (`$XDG_RUNTIME_DIR/vectra-payload.json`); no lleva datos reales.

**3.1 Tráfico sobre M1 (antes de empezar)**

```bash
kubectl -n vectra-serving port-forward svc/${I1}-predictor 8081:80 &          # una terminal; se reinicia si el pod rota
PAYLOAD="${XDG_RUNTIME_DIR:-/tmp}/vectra-payload.json"
model-serving/docs/kind/traffic.sh --url "http://127.0.0.1:8081/v1/models/${I1}:predict" --payload "$PAYLOAD" \
  --versions "$M1" --duration 900 --out /tmp/traffic-m1.log
```

**3.2 Los cuatro PR de `promotion-tool` (U04-T05b)**

Interfaz del Paso 12 de U4 (`create_promotion_pr`, `post_activation_pr`, `rollback_pr`, `mark_active`) y contrato de edición de `model-serving/docs/values.md` (ejemplos 1 a 3). Los argumentos exactos son los de `governance/promotion_tool` cuando U04-T05b esté en `main`; aquí solo importa el efecto sobre `vectra-risk-gitops/values/kind/model-serving.yaml`:

| Orden | Acción | Efecto esperado en el PR (`values.md`) |
|---|---|---|
| 1 | `create_promotion_pr(M2)`, revisión y merge | Agrega al final `{modelVersionId: M2, storageUri: s3://model-store/<M2>/, profile: prod}`; M1 no cambia |
| 2 | Sync manual de la Application `model-serving` | Aparece `$I2` con predictor y explicador, 2 réplicas cada uno |
| 3 | `mark_active(M2)` en governance | `GET /v1/serving-config` da `inference_service: $I2` |
| 4 | `post_activation_pr(M1)`, revisión y merge | M1 pasa de `profile: prod` a `inactive` |
| 5 | Sync manual | M1 queda con 1 réplica por componente, `vectra.io/serving-state: inactivo` y `hpa-exempt` |

```bash
helm template ms model-serving/chart -f vectra-risk-gitops/envs/kind/values.yaml -f vectra-risk-gitops/values/kind/model-serving.yaml   # tras cada merge: el diff coincide con values.md
argocd app sync model-serving                       # pasos 2 y 5; sync manual, la Application no tiene auto-sync
kubectl -n vectra-serving get inferenceservice,deployment,hpa,pdb
kubectl -n vectra-serving wait --for=condition=Ready inferenceservice/${I2} --timeout=300s
```

**3.3 Tráfico sobre M2 (desde que `$I2` está Ready hasta el sync del paso 5)**

```bash
kubectl -n vectra-serving port-forward svc/${I2}-predictor 8082:80 &
model-serving/docs/kind/traffic.sh --url "http://127.0.0.1:8082/v1/models/${I2}:predict" --payload "$PAYLOAD" \
  --versions "$M2" --duration 600 --out /tmp/traffic-m2.log
```

- **Esperado:** ambos scripts terminan con `version_mismatch=0` (código 0). Un código 2 es solo errores de transporte (típicamente el `port-forward` cayó cuando el pod rotó): se anota y se repite esa ventana, pero no es un `version_mismatch`.
- **Comprobaciones de la promoción:** `kubectl -n vectra-serving get inferenceservice` lista `$I1` (inactivo) e `$I2`; `kubectl -n vectra-serving get pods -l vectra.io/inference-service=${I2}` muestra 2 + 2 pods Ready.
- **Evidencia:** `evidence/kind/escenario-1-promocion.md` (comandos, los dos resúmenes de `traffic.sh`, `/tmp/traffic-m*.log` adjuntos, los cuatro enlaces de PR y el `serving-config`).

## 4. Escenario 2: rollback a M1

**Esperado:** el activo nunca baja de 2 réplicas durante el cambio.

El rollback del Paso 12 de U4 (`rollback_pr`, US-208), partiendo de M1 `inactivo` y M2 `prod`:

1. Arranca el muestreo del activo actual (M2) y déjalo corriendo hasta después del paso 5:

   ```bash
   model-serving/docs/kind/sample-replicas.sh --namespace vectra-serving \
     --deployments "${I2}-predictor,${I2}-explainer" --min 2 --duration 420 --interval 2 --out /tmp/replicas-m2.log
   ```
2. `rollback_pr(M1)` con revisión y merge: M1 pasa de `inactive` a `prod` (ejemplo «Rollback» de `values.md`); M2 sigue en `prod`.
3. `argocd app sync model-serving`; espera `kubectl -n vectra-serving wait --for=condition=Ready inferenceservice/${I1} --timeout=300s`. M1 vuelve a 2 + 2 réplicas.
4. `mark_active(M1)` en governance.
5. `post_activation_pr(M2)` (M2 pasa a `inactive`), merge y sync. Muestrea ahora M1 el tiempo que sea posible: `sample-replicas.sh … --deployments "${I1}-predictor,${I1}-explainer"`.

- **Salida esperada de los muestreos:** `muestras=… minimo_observado=2 … bajo_el_minimo=0` (código 0). `minimo_observado` toma el menor entre `spec.replicas` y `status.readyReplicas`.
- **Comprobación del estado inactivo:** `model-serving/docs/kind/check-pods.sh propagation ${I2}-predictor vectra-serving inactivo` imprime `OK`.
- **Evidencia:** `evidence/kind/escenario-2-rollback.md`.

## 5. Escenario 3: artefactos RT-3 en staging

**Esperado:** RT3-a y RT3-d no quedan listos (el `readinessProbe` `/readyz` da 503); RT3-b queda listo. Se despliegan solo en `staging` (P-U6-03), por PR a mano (no los registra governance, que rechaza a, c y d con 422), **uno a la vez**, en `vectra-risk-gitops/values/kind/model-serving.yaml`:

```yaml
inferenceServices:
  # … las entradas activas de M1/M2 se conservan …
  - { modelVersionId: <M1>, storageUri: "s3://model-store/adversarial/rt3/RT3-a/", profile: staging }
```

Para cada caso (a, d, b): cambia `storageUri` en un PR (el nombre del `InferenceService` de staging es `$I1`, mismo `modelVersionId`; reemplaza la entrada, no la repitas), merge y sync.

```bash
argocd app sync model-serving
kubectl -n vectra-staging get inferenceservice,pods -l vectra.io/component=predictor
kubectl -n vectra-staging logs deploy/${I1}-predictor -c kserve-container | tail -20
kubectl -n vectra-staging get pod -l vectra.io/component=predictor -o jsonpath='{.items[0].status.containerStatuses[?(@.name=="kserve-container")].ready}'
```

- **RT3-a y RT3-d, esperado:** el contenedor sigue sin `ready` (`false`), el log trae `embedded_version_mismatch:explainer.json` (a) o `entry_version_mismatch:explainer.json` (d) y `ModelPackageIntegrityFailed`; el pod no aparece en los endpoints. **RT3-b:** `ready` es `true` y `:predict` responde (port-forward al servicio de staging).
- **Nota:** staging solo despliega el predictor (INF-U6-02 §3). Los casos a y d dañan `explainer.json` y su entrada en `manifest.json`; el predictor también verifica el manifiesto completo y falla igual (las pruebas de U06-T01 lo ejercen con el cargador). Si en kind el predictor de staging llega a Ready con a o d, es un defecto: repórtalo en la evidencia.
- **Confirmaciones del riesgo `MODEL_DIR` y de las candidatas de U06-T02** (con el pod de M1 en `vectra-serving`):

```bash
POD="$(kubectl -n vectra-serving get pod -l vectra.io/inference-service=${I1} -o jsonpath='{.items[0].metadata.name}')"
EPOD="$(kubectl -n vectra-serving get pod -l vectra.io/inference-service=${I1},vectra.io/component=explainer -o jsonpath='{.items[0].metadata.name}')"
model-serving/docs/kind/check-pods.sh manifest "$POD" vectra-serving "$M1"        # /mnt/models/manifest.json con MODEL_DIR
model-serving/docs/kind/check-pods.sh initializer "$EPOD" vectra-serving           # el storage initializer también se inyecta en el explicador
model-serving/docs/kind/check-pods.sh init-order "$POD" vectra-serving             # linkerd-proxy antes que storage-initializer (F46, mTLS con MinIO)
model-serving/docs/kind/check-pods.sh propagation ${I1}-predictor vectra-serving inactivo   # con M1 inactivo: KServe propaga serving-state y hpa-exempt al Deployment
```

  (Para `init-order` y `propagation` el pod/Deployment debe estar en el estado correspondiente: `propagation` con M1 `inactive`.) Si el orden de init containers no es el esperado, o la propagación falla, es un defecto de la plantilla de U06-T02 (plan B de la candidata: `ServingRuntime` por namespace): repórtalo y no lo parches desde aquí.
- **Evidencia:** `evidence/kind/escenario-3-rt3.md` (una subsección por caso y las cuatro confirmaciones).

## 6. Memoria

`kubectl top` mide uso real; los requests (lo que reserva el planificador) son los de `platform/tests/test_kind_profile.py`: **276 MiB por pod** (256 + 20 del proxy). Cifra del presupuesto de kind con U6 en el peor momento: **8,4375 GiB** pedidos en total (`BUDGET_GIB = 8.5`), de los cuales U6 aporta 2,43 GiB (9 pods: M1 y M2 en `prod` y el predictor de staging).

| Momento | Pods de U6 | Requests de U6 (MiB) |
|---|---|---|
| Antes (M1 `prod`) | 4 | 1 104 |
| Durante (M1 y M2 `prod`) | 8 (+1 de staging si RT3-b sigue arriba) | 2 208 (2 484) |
| Después (M2 `prod`, M1 `inactive`) | 6 | 1 656 |

```bash
model-serving/docs/kind/memory.sh --namespace vectra-serving --label antes    --budget-mib 1104 --out /tmp/memoria.md
model-serving/docs/kind/memory.sh --namespace vectra-serving --label durante  --budget-mib 2208 --out /tmp/memoria.md   # con ambos Ready, bajo el tráfico del escenario 1
model-serving/docs/kind/memory.sh --namespace vectra-serving --label despues  --budget-mib 1656 --out /tmp/memoria.md
kubectl top nodes
```

- **Esperado:** `uso_total_mib` por debajo del tope en cada fotografía (código 0): 256 MiB por pod bastan para el modelo de referencia. Si un pod se acerca a su límite (1 GiB) o se reinicia por `OOMKilled`, la decisión de §7 de `DECISIONES-LOOP.md` no se sostiene: repórtalo.
- **Evidencia:** `evidence/kind/memoria.md` (`/tmp/memoria.md`, `kubectl top nodes` y los `OOMKilled`, si hubo).

## 7. Diferido y pendiente

- Escenarios 4 (saturación y `ServingSaturation`), 5 (drenado de una zona) y 6 (carga a 20 solicitudes/s): diferidos por la demo (T2, T3, T6).
- Escenario 1 con `scoring-service` (el 0 de `version_mismatch` de punta a punta): pendiente de U7 Paso 18.
- Cierre de la unidad: `aidlc-docs/construction/model-serving/evidence/cierre-demo.md`. Al adjuntar la evidencia, el Paso 11 pasa a `[x] (U06-T03, acotado a la demo)` en el plan.
