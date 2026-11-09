# Entrega de U5 al model-store (kind)

Procedimiento del **operador**: una persona con sus propias credenciales (NFR-U5-03, AUTONOMIA-01). Ninguna tarea, agente ni CI sube al MinIO ni toca el clúster. Alcance de la demo (`demo-kind-alcance.md` §3, U5): sin release firmada; se genera `make release` en local, se verifica cada SHA-256 y se sube al MinIO de `kind-vectra`. Lo que queda fuera está en «Diferido por la demo (T1)».

Todos los comandos corren desde `vectra-risk/`.

## Síntoma

Hay que dejar disponible en `kind-vectra` el modelo de referencia (RT-1) y el dataset de validación, y las 5 corridas de la variante proxy `rt2-demo` (RT-2), para que U4 los registre (US-201) y U9 y U6 los usen (US-202).

## Impacto

Sin esta entrega U4 no tiene un `manifest.json` que registrar y no hay modelo que servir. Subir un paquete alterado deja un modelo sin la integridad que U4 verifica en BR-U4-06; por eso el paso 2 es previo a cualquier subida. El model-store es versionado y la identidad de subida no puede borrar (`DeleteObject` no está en `model-store-upload`): lo subido por error no se retira desde aquí.

## Diagnóstico

Antes de empezar:

1. `kind-vectra` está arriba y MinIO sano: `kubectl --context kind-vectra -n vectra-data rollout status statefulset/minio --timeout=60s`.
2. La imagen `mc` está en el registro local (`platform/runbooks/install.md`, paso 5): `curl -s http://localhost:5001/v2/mc/tags/list`.
3. Los buckets existen y tienen los nombres del diseño de U1: `model-store` (modelos; U4 y U6) y `validation-datasets` (dataset de validación; U4).

## Mitigación

### 1. Generar la entrega en local

`make -C reference-model release` produce en `reference-model/.out/`: `datasets/` (`train`, `validation` y `test`, en Parquet), `package/` (el modelo base, RT-1), `proxy/run-1` a `proxy/run-5` (variante `rt2-demo`), `adversarial/` y `reference-policy.json`. Tarda unos minutos; `make -C reference-model release-base` genera solo `datasets/` y `package/`, y entonces el paso 2 se corre sobre `package` y la parte de la variante proxy se omite.

```bash
make -C reference-model release
```

### 2. Verificar cada SHA-256 del manifiesto

`reference-model/scripts/verify_release.py` solo usa la biblioteca estándar. Compara cada archivo del `manifest.json` de `package` y de las 5 corridas proxy, y falla si un archivo falta, difiere o no está en el manifiesto. **Si falla, no subas nada.**

```bash
make -C reference-model verify-release
```

Para un paquete suelto: `python3 reference-model/scripts/verify_release.py reference-model/.out/package`. El Parquet de validación no está en el manifiesto; anota su SHA-256 para compararlo después de subirlo: `sha256sum reference-model/.out/datasets/validation.parquet`.

### 3. Subir al MinIO de kind

El ingeniero lee su clave en la bóveda de kind y llega a MinIO por un `port-forward` (`platform/runbooks/install.md`, «Secretos de Vault»). Deja el `port-forward` corriendo en otra terminal.

```bash
kubectl --context kind-vectra -n vectra-data port-forward svc/minio 9000
```

`mc` va en la imagen de la plataforma (`localhost:5001/mc:dev`). Se usa `MC_HOST_kind` en vez de un alias guardado, para que la clave no quede en disco. Los directorios se montan de solo lectura.

```bash
export KEY="$(kubectl --context kind-vectra exec -n vault vault-0 -- env VAULT_TOKEN=root vault kv get -field=secretKey secret/minio/engineer-upload)"
export MC_HOST_kind="http://risk-engineer-upload:${KEY}@127.0.0.1:9000"
mc() { docker run --rm --network host -e MC_HOST_kind -v "$PWD/reference-model/.out:/out:ro" --entrypoint /usr/bin/mc localhost:5001/mc:dev "$@"; }
export MV="$(python3 -c 'import json; print(json.load(open("reference-model/.out/package/manifest.json"))["model_version_id"])')"
```

Paquete base al bucket `model-store`, en un prefijo por `model_version_id`:

```bash
mc cp --recursive /out/package/ "kind/model-store/${MV}/"
```

Dataset de validación al bucket `validation-datasets`. **Atención:** la política `model-store-upload` de `risk-engineer-upload` solo cubre `model-store` (`platform/data/minio/values-kind.yaml`); ninguna identidad de diseño escribe en `validation-datasets`. Hasta que U1 lo resuelva (candidata en `CANDIDATAS.md`), este paso lo hace el administrador de la demo con la raíz de MinIO, `minio/root` en la bóveda, y queda anotado en la bitácora de la entrega:

```bash
export MC_HOST_kind="http://$(kubectl --context kind-vectra exec -n vault vault-0 -- env VAULT_TOKEN=root vault kv get -field=user secret/minio/root):$(kubectl --context kind-vectra exec -n vault vault-0 -- env VAULT_TOKEN=root vault kv get -field=password secret/minio/root)@127.0.0.1:9000"
mc cp /out/datasets/validation.parquet "kind/validation-datasets/${MV}/validation.parquet"
```

La ruta `<bucket>/<model_version_id>/<archivo>` es la convención de este procedimiento; U4 no fija todavía un diseño de rutas **[PENDIENTE U4: confirmar la ruta de `artifact_uri`, `explainer_uri` y `manifest_uri`]**.

### 4. Registrar la versión en U4 (US-201)

U4 todavía no existe. El diseño de U4 lo registra con `POST /v1/models` (`ModelRegistration` en `contracts/openapi/governance-service.yaml`; rol `ingeniero_riesgo`, con MFA). Los campos salen del paquete subido: `artifact_uri` y `artifact_sha256` (de `predictor.json`), `explainer_uri` y `explainer_sha256` (de `explainer.json`), `manifest_uri` y `manifest_sha256`, y `artifact_format = xgboost_json`. **[PENDIENTE U4: el servicio no está desplegado; este paso se ejecuta cuando exista `governance-service` en kind.]**

```bash
python3 -c 'import hashlib, json; m = json.load(open("reference-model/.out/package/manifest.json")); print(m["model_version_id"], hashlib.sha256(open("reference-model/.out/package/manifest.json", "rb").read()).hexdigest()); [print(f["name"], f["sha256"]) for f in m["files"]]'
```

### 5. Variante proxy `rt2-demo` (BR-U5-15)

Los 5 paquetes de `proxy/run-1` a `proxy/run-5` se suben igual que el base, cada uno con su `model_version_id`, y **solo en kind y en staging**: en producción no se suben nunca. Es un modelo con una proxy discriminatoria a propósito, para la demostración de RT-2.

```bash
for n in 1 2 3 4 5; do
  id="$(python3 -c "import json; print(json.load(open('reference-model/.out/proxy/run-$n/manifest.json'))['model_version_id'])")"
  mc cp --recursive "/out/proxy/run-$n/" "kind/model-store/${id}/"
done
```

## Escalamiento

- `verify-release` falla con una release recién generada: es un defecto de U5 (el empaquetado ya verifica sus propios SHA-256). Abre un issue y no subas nada.
- `mc` responde `Access Denied` en `model-store`: la clave de la bóveda no coincide con la de MinIO; sigue «Vault reiniciado» de `platform/runbooks/install.md`.
- `Access Denied` en `validation-datasets` con `risk-engineer-upload`: es lo esperado hoy (paso 3); usa la raíz como allí se indica.
- La ruta o el contrato de registro cambian en U4: se corrige este documento, no el paquete.

## Verificación

1. El paquete base está completo en el model-store: `mc ls "kind/model-store/${MV}/"` lista los 7 archivos (`predictor.json`, `explainer.json`, `background.csv`, `domain_envelope.json`, `feature_dictionary.json`, `feature_spec.json` y `manifest.json`).
2. Lo subido es lo verificado: `mc cat "kind/model-store/${MV}/manifest.json" | sha256sum` da el mismo valor que `sha256sum reference-model/.out/package/manifest.json`.
3. El dataset llegó íntegro: `mc cat "kind/validation-datasets/${MV}/validation.parquet" | sha256sum` da el valor anotado en el paso 2.
4. Las 5 corridas proxy están en el model-store: `mc ls kind/model-store/` muestra 6 prefijos `mv-…` (el base y las 5 corridas).
5. El procedimiento sigue la plantilla: `uv run python platform/tests/test_runbooks.py --operational --root reference-model/docs`.

## Diferido por la demo (T1)

La demo no usa la release firmada del Paso 8 del plan de U5 (workflow `.github/workflows/reference-model.yml`; destino: staging). Cuando exista, este procedimiento gana antes del paso 2:

- la **descarga** de la release OCI publicada con `oras`, en lugar de `make release` en local;
- `cosign verify` de la firma con la misma llave de `verify-images`;
- `cosign verify-attestation` de la procedencia (commit, `generator_version` y semilla);
- el SBOM de Syft como parte de lo descargado.

NFR-U5-03 pide hoy `cosign verify` en el procedimiento: en la demo no se cumple esa parte. La verificación de cada SHA-256 (paso 2) sí se cumple.

El Paso 8 también lleva, y por eso se difieren con él, NFR-U5-01 (entrega en un workflow sin credenciales del clúster), NFR-U5-02 (release firmada, con SBOM y procedencia) y NFR-U5-20 (entrega en 30 min o menos en un runner estándar). En la demo no tienen código ni prueba: `platform/tests/test_traceability.py` los da por cubiertos solo porque este documento los nombra, y `cierre-demo.md` los lista como no comprobados.
