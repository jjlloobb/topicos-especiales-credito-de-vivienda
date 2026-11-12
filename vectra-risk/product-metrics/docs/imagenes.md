# Imagen de `product-metrics` en kind

**Una sola imagen, un solo proceso:** `python -m vectra_product.main` (el `CMD`), que sirve 8081 (`/metrics`, `/healthz`, `/readyz`); no hay 8080 ni rutas de negocio. La construye este repositorio; el push y el digest real los hace el **operador** en la verificación consolidada de U12 Paso 18 (enmienda §8; AUTONOMIA-01). Sin firma Cosign, SBOM ni escaneo (T1 de la demo) y sin workflow de CI (T4). **Estos comandos no se ejecutan en la tarea de despliegue (U11-T03) más allá del `build` y las comprobaciones locales.**

## Construir (desde `vectra-risk/`)

```bash
make -C product-metrics image
# hadolint product-metrics/Dockerfile
# docker build -t localhost:5001/vectra/product-metrics:dev -f product-metrics/Dockerfile .   (contexto: la raíz de vectra-risk/)
```

Qué lleva la imagen final: Python 3.12 (imagen base fijada por digest en cada `FROM`), `vectra-product` y sus dependencias del workspace (`vectra-contracts`, `vectra-common`, `pyyaml`). Corre como `65532:65532`, igual que el `runAsUser` y el `runAsGroup` del chart. **No lleva** `pytest`, `hypothesis`, `ruff`, `mypy` ni `hatchling`. FastAPI llega solo como dependencia de `vectra_common`; ningún módulo de `vectra_product` lo importa (import-linter, contrato `sin-fastapi`).

## Comprobar (local, sin clúster)

```bash
platform/.tools/bin/hadolint product-metrics/Dockerfile
docker image inspect localhost:5001/vectra/product-metrics:dev --format '{{.Config.User}} {{json .Config.Cmd}}'   # 65532:65532 ["python","-m","vectra_product.main"]
docker run --rm --entrypoint sh localhost:5001/vectra/product-metrics:dev -c '! pip list 2>/dev/null | grep -iE "^(pytest|hypothesis|ruff|mypy|hatchling) " && echo OK'
docker run --rm --entrypoint python localhost:5001/vectra/product-metrics:dev -c 'import vectra_product.main; print("OK-entrada")'
grep -cE '^FROM .*@sha256:[0-9a-f]{64}' product-metrics/Dockerfile
uv run lint-imports --config product-metrics/.importlinter
# el contenedor real arranca con las variables y el archivo de parametros que pone el chart, contra dobles HTTP locales, con --read-only
uv run pytest product-metrics/tests/integration/test_image.py -v
```

## Publicar (operador, U12 Paso 18)

Igual que `bias-monitoring/docs/imagenes.md`:

```bash
docker push localhost:5001/vectra/product-metrics:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/product-metrics:dev
```

El digest sale en el `inspect` (`localhost:5001/vectra/product-metrics@sha256:…`). Un PR lo escribe en `image.digest` de los values de kind (`vectra-risk-gitops/values/kind/product-metrics.yaml`, que `generate.py` agrega solo cuando el archivo existe y se vuelve a correr) y regenera las Applications con `uv run python vectra-risk-gitops/generate.py`. Hasta entonces el chart renderiza con el digest de ejemplo (`sha256:…0007`) y los pods quedarían en `ImagePullBackOff`.
