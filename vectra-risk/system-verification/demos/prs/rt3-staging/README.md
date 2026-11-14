# PR `rt3-staging`: RT3-a o RT3-d desplegados en `vectra-staging` (D1, opcional)

**Plantillas, no parches fijos.** `RT3-a.patch.tpl` y `RT3-d.patch.tpl` llevan el hueco `{{M1}}`: el `model_version_id` del modelo de referencia, que solo existe tras
`make -C reference-model release`. Sustituye el hueco (por ejemplo con `sed`) y aplica el resultado con `git apply` a `vectra-risk-gitops/values/kind/model-serving.yaml` (`inferenceServices` hoy `[]`).
Cada entrada va con `profile: staging` (los paquetes `adversarial/` solo existen en staging) y su nombre es `isvc-<8 hex de M1>` en `vectra-staging`.

**RT3-a y RT3-d no caben a la vez:** comparten el nombre del `InferenceService`; con las dos entradas `helm template` falla con «repetido». Un caso por PR: cambia la entrada, fusiona y sincroniza la Application `model-serving`.
K16 no lee `vectra-staging`: el resultado de este paso es `no ejecutado` (decisión del usuario) y el paso del guion es opcional.
