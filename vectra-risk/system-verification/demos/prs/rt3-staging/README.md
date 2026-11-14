# PR `rt3-staging`: RT3-a o RT3-d desplegados en `vectra-staging` (D1, opcional)

**No son parches fijos.** El contexto de `values/kind/model-serving.yaml` cambia con lo que `promotion-tool` ya hizo (lista vacía antes de promover el modelo de referencia, una entrada `prod` después), y el estado de la demo
es el segundo. Cada parche se **genera sobre el archivo tal como esté** con `demos/prs/entrada.py` (solo biblioteca estándar; no escribe nada), con el `model_version_id` del modelo de referencia (`<M1>`, que solo existe tras
`make -C reference-model release`):

```
python3 system-verification/demos/prs/entrada.py --version <M1> --storage-uri "s3://model-store/adversarial/rt3/RT3-a/" > rt3-a.patch   # o .../RT3-d/ para RT3-d
git apply rt3-a.patch
```

Cada entrada va con `profile: staging` (los paquetes `adversarial/` solo existen en staging) y su nombre es `isvc-<8 hex de M1>` en `vectra-staging`.

**RT3-a y RT3-d no caben a la vez:** comparten el nombre del `InferenceService`; con las dos entradas `helm template` falla con «repetido». Un caso por PR: cambia la entrada, fusiona y sincroniza la Application `model-serving`.
K16 no lee `vectra-staging`: el resultado de este paso es `no ejecutado` (decisión del usuario) y el paso del guion es opcional.
