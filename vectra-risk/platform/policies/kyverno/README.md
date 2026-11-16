# Políticas de Kyverno

`kyverno test platform/policies/` ejecuta `kyverno-test.yaml`. Kyverno corre en HA con `failurePolicy: Fail`, y excluye `kube-system`, `kyverno` y `linkerd` (P-U1-06).

## Lo que KServe crea en `vectra-serving`

`require-min-replicas` (`require-spread-and-pdb.yaml`) exime los Deployment con la etiqueta `serving.kserve.io/inferenceservice` en `vectra-serving`, igual que el data plane de Envoy Gateway en `vectra-edge`. Con HPA (perfil `prod` de U6), KServe v0.21.0 no fija `spec.replicas` del Deployment: solo lo hace con `serving.kserve.io/autoscalerClass: none` (`deployment_reconciler.go`, línea 173), y tampoco lo toca al actualizarlo, así que el apiserver lo deja en 1 y el HPA lo sube. El mínimo de 2 del modelo activo no se pierde: lo vigila `active-inference-service-needs-two-replicas` (`require-hpa-bounds.yaml`) sobre el `InferenceService` (`minReplicas >= 2`, el mínimo del HPA), y el rego de `model-serving/policies/conftest` sobre el chart.

Los fixtures `kserve-prod-no-replicas` y `kserve-prod-one-replica` de `fixtures/resources.yaml` son el Deployment que KServe genera para el `prod` que rinde el chart de U6 (`kserve_deployment` en `platform/tests/kind_serving_kyverno.py`). Ese script, que corre en `make -C platform check-tools`, evalúa todas las políticas contra los Deployment y Pod generados para `prod`, `staging` e `inactive`, y comprueba que los fixtures no se desfasen del chart.
