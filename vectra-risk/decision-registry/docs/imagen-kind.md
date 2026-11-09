# Imagen de `decision-registry` en kind

La imagen es una sola para el servicio, la CLI `vectra-registry` (CronJob del agregador) y las migraciones de Alembic (Job de migración, F44). Lo que cambia es el `command` del chart. La construye este repositorio; el push y el digest real los hace el **operador** en el Bloque H (AUTONOMIA-01). Sin firma Cosign, SBOM ni attestations (T1 de la demo) y sin workflow de CI (T4).

## Construir (desde `vectra-risk/`)

```bash
make -C decision-registry image
# docker build -t localhost:5001/vectra/decision-registry:dev -f decision-registry/Dockerfile .   (contexto: la raíz de vectra-risk/)
```

Qué lleva la imagen final: Python 3.12 (imagen base fijada por digest en cada `FROM`), `vectra-decision-registry` y sus dependencias del workspace (`vectra-contracts`, `vectra-common`), `alembic.ini` y `migrations/`. Corre como `65532:65532`, igual que el chart. No lleva `pytest`, `hypothesis`, `testcontainers` ni `hatchling`.

## Comprobar

```bash
docker run --rm --entrypoint vectra-registry localhost:5001/vectra/decision-registry:dev --help
docker image inspect localhost:5001/vectra/decision-registry:dev --format '{{.Config.User}}'   # 65532:65532
docker run --rm --entrypoint sh localhost:5001/vectra/decision-registry:dev -c 'python -c "import vectra_registry, vectra_common" && ! python -c "import pytest" 2>/dev/null && echo OK-runtime'
```

## Publicar (operador, Bloque H)

Igual que `identity-edge/docs/paso-16-kind.md` §3:

```bash
docker push localhost:5001/vectra/decision-registry:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/decision-registry:dev
```

El digest sale en el `inspect`. Un PR lo escribe en `image.digest` de los values de kind (`vectra-risk-gitops/values/kind/decision-registry.yaml`, que `generate.py` agrega solo al volver a correrse) junto con `checkpoint.publicKeys` y `checkpoint.keyFingerprint`. Hasta entonces el chart renderiza con el digest de ejemplo y los pods quedarían en `ImagePullBackOff`.
