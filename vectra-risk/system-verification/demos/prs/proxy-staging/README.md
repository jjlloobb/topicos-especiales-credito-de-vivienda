# PR `proxy-staging`: la versión del proxy en staging (D2)

**No es un parche fijo.** El contexto de un parche de `values/kind/model-serving.yaml` cambia con lo que `promotion-tool` ya hizo (una lista vacía antes de promover el modelo de referencia; una entrada `prod`
después), y justo ese es el estado de la demo. Por eso el parche se **genera sobre el archivo tal como esté** con `demos/prs/entrada.py` (solo biblioteca estándar; no escribe nada):

```
git -C "$PROMO" switch main && git -C "$PROMO" pull --ff-only
(cd "$PROMO/vectra-risk" && python3 system-verification/demos/prs/entrada.py --version <M2> --storage-uri "s3://model-store/<M2>/" > "$VERIF_HOME/proxy.patch")
git -C "$PROMO" switch -c <rama> origin/main && git -C "$PROMO" apply "$VERIF_HOME/proxy.patch"
```

`$PROMO` es el clon limpio de la guía (F0, paso 11) y el parche se escribe **fuera del árbol**: un `.patch` suelto lo dejaría sucio y `promotion-tool` se negaría con `working_tree_dirty`.

`<M2>` es el `model_version_id` de `reference-model/.out/proxy/run-1/manifest.json` (existe tras `make -C reference-model release`). El parche agrega al final de `inferenceServices` la entrada
`{ modelVersionId: <M2>, storageUri: "s3://model-store/<M2>/", profile: staging }` y se aplica **antes de `rt2-setup`**. El operador lo fusiona y sincroniza la Application `model-serving`. En D2 se usa **una** versión del proxy (DD-1).

## Retirar la entrada

Al terminar D2 la entrada `staging` se quita. **No sirve `git apply -R` del parche de alta:** `promotion-tool` reescribe el bloque `inferenceServices` entero (una clave por línea) en cuanto promueve, baja o restaura una versión, y el contexto del parche ya no coincide. `entrada.py --retirar` lee el archivo tal como esté, reconoce la entrada en los dos estilos y deja `inferenceServices: []` si era la única:

```
(cd "$PROMO/vectra-risk" && python3 system-verification/demos/prs/entrada.py --version <M2> --retirar > "$VERIF_HOME/retirar-proxy.patch")
```
