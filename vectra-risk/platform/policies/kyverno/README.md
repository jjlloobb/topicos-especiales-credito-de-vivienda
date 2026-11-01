# Políticas de Kyverno

`kyverno test platform/policies/` ejecuta `kyverno-test.yaml`. Kyverno corre en HA con `failurePolicy: Fail`, y excluye `kube-system`, `kyverno` y `linkerd` (P-U1-06).
