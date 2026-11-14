# PR `proxy-staging`: la versión del proxy en staging (D2)

**Plantilla.** `proxy.patch.tpl` lleva el hueco `@@M2@@`: el `model_version_id` de `reference-model/.out/proxy/run-1/manifest.json` (existe tras `make -C reference-model release`). Se sustituye y se aplica
a `vectra-risk-gitops/values/kind/model-serving.yaml` **antes de `rt2-setup`**; el PR agrega `{ modelVersionId: <M2>, storageUri: "s3://model-store/<M2>/", profile: staging }`. El operador lo fusiona y
sincroniza la Application `model-serving`. En D2 se usa **una** versión del proxy (DD-1).
