# PR `proxy-staging`: la versión del proxy en staging (D2)

**No es un parche fijo.** El contexto de un parche de `values/kind/model-serving.yaml` cambia con lo que `promotion-tool` ya hizo (una lista vacía antes de promover el modelo de referencia; una entrada `prod`
después), y justo ese es el estado de la demo. Por eso el parche se **genera sobre el archivo tal como esté** con `demos/prs/entrada.py` (solo biblioteca estándar; no escribe nada):

```
python3 system-verification/demos/prs/entrada.py --version <M2> --storage-uri "s3://model-store/<M2>/" > proxy.patch
git apply proxy.patch
```

`<M2>` es el `model_version_id` de `reference-model/.out/proxy/run-1/manifest.json` (existe tras `make -C reference-model release`). El parche agrega al final de `inferenceServices` la entrada
`{ modelVersionId: <M2>, storageUri: "s3://model-store/<M2>/", profile: staging }` y se aplica **antes de `rt2-setup`**. El operador lo fusiona y sincroniza la Application `model-serving`. En D2 se usa **una** versión del proxy (DD-1).
