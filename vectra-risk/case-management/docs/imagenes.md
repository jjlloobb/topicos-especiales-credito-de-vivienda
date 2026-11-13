# Imágenes de `case-management` en kind

Dos imágenes: `case-management` (una imagen y tres órdenes: `case-service`, `case-worker` y el Job de migración; P-U8-10) y `core-banking-mock` (con su fixture). Las construye este repositorio; el push y el digest real los hace el **operador** en la verificación consolidada de U12 Paso 18 (enmienda §8; AUTONOMIA-01). Sin firma Cosign, SBOM ni escaneo (T1 de la demo) y sin workflow de CI (T4). **Estos comandos no se ejecutan en la tarea de despliegue (U08-T05) más allá del `build` y las comprobaciones locales.**

## Construir (desde `vectra-risk/`)

```bash
make -C case-management image image-mock
# docker build -t localhost:5001/vectra/case-management:dev -f case-management/Dockerfile .                       (contexto: la raíz de vectra-risk/)
# docker build -t localhost:5001/vectra/core-banking-mock:dev -f case-management/core_banking_mock/Dockerfile .
```

Qué lleva cada imagen final: Python 3.12 (imagen base fijada por digest en cada `FROM`) y el runtime con sus dependencias del workspace (`vectra-contracts`, `vectra-common`).

- **`case-management`**: `vectra-case`, más `alembic.ini` y `migrations/` en `/app` (el Job de migración corre `alembic -c /app/alembic.ini upgrade head`). El `CMD` es el de `case-service` (`python -m vectra_case.app`, 8080 y 8081); el chart fija la orden del worker (`python -m vectra_case.worker`, solo 8081) y la de la migración. No lleva `core_banking_mock`. El plan nombra también `case-retention`: su CLI es del Paso 16 (diferido, T5) y la imagen no tiene punto de entrada para ella.
- **`core-banking-mock`**: `core-banking-mock` y el fixture en `/app/fixtures/credits.json`, la ruta de `core_banking_mock.app.DEFAULT_FIXTURES` (sin ConfigMap ni volumen; INF-U8-02). No lleva `vectra_case`.

Las dos corren como `65532:65532`, igual que el `runAsUser` y el `runAsGroup` del chart, y **no llevan** `pytest`, `hypothesis`, `ruff`, `mypy`, `hatchling` ni librería de circuit breaking (NFR-U8-34).

## Comprobar (local, sin clúster)

```bash
platform/.tools/bin/hadolint case-management/Dockerfile case-management/core_banking_mock/Dockerfile
for i in case-management core-banking-mock; do
  docker image inspect localhost:5001/vectra/$i:dev --format '{{.Config.User}}'   # 65532:65532
  # «sin circuit breaking» se comprueba con `pip list` en la imagen, no en un SBOM (el SBOM esta diferido, T1)
  docker run --rm --entrypoint sh localhost:5001/vectra/$i:dev -c '! pip list 2>/dev/null | grep -iE "^(pybreaker|circuitbreaker|aiobreaker|purgatory[a-z-]*|pytest|hypothesis|ruff|mypy|hatchling) " && echo OK'
done
docker run --rm --entrypoint sh localhost:5001/vectra/case-management:dev -c 'test -s /app/alembic.ini && test -d /app/migrations/versions && echo OK-migraciones'
docker run --rm --entrypoint python localhost:5001/vectra/core-banking-mock:dev -c 'from core_banking_mock.app import DEFAULT_FIXTURES, load_credits; print(len(load_credits(DEFAULT_FIXTURES)) > 0)'
grep -nE '^FROM .*@sha256:[0-9a-f]{64}' case-management/Dockerfile case-management/core_banking_mock/Dockerfile
uv run pytest case-management/tests/integration/test_image.py -v    # arranca los cuatro contenedores con lo que pone el chart (CA-4)
```

## Publicar (operador, U12 Paso 18)

Igual que `scoring-explainability/docs/imagenes.md`, `identity-edge/docs/paso-16-kind.md` y `bias-monitoring/docs/imagenes.md`:

```bash
docker push localhost:5001/vectra/case-management:dev
docker push localhost:5001/vectra/core-banking-mock:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/case-management:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/core-banking-mock:dev
```

El digest sale en el `inspect` (`localhost:5001/vectra/<imagen>@sha256:…`). Un PR lo escribe en `images.caseManagement.digest` y `images.coreMock.digest` de los values de kind (`vectra-risk-gitops/values/kind/case-management.yaml`) y regenera las Applications con `uv run python vectra-risk-gitops/generate.py`. Hasta entonces el chart renderiza con los digests de ejemplo (`sha256:…0007` y `…0008`) y los pods quedarían en `ImagePullBackOff`. U12 (`prepare`) agrega en ese mismo PR el `probes.runId` del Job `rt5-demo-<runId>`.

## Un solo commit y un solo PR para governance, scoring, explainability y case-management (C-4)

`ServingConfig` (U0 §9.3) es un `StrictModel` con `additionalProperties: false`, y desde U04-T09 trae `cutoff`, `low_confidence_threshold` y `channel_rules`. Un consumidor con el tipo viejo **rechaza** la respuesta nueva y falla cerrado (`serving_config_unavailable`); `oasdiff` no lo marca como cambio incompatible. `case-service` y `case-worker` también leen `serving-config` (F104). Por eso:

- construye las imágenes de `governance-service`, `scoring-service`, `explainability-service` y `case-management` **del mismo commit** (`make -C governance image`, `make -C scoring-explainability image-scoring image-explainability`, `make -C case-management image image-mock`);
- sube sus digests a los values de kind en **un solo PR** (`values/kind/governance.yaml` si existe, `values/kind/scoring-explainability.yaml` y `values/kind/case-management.yaml`);
- `governance`, `scoring-explainability` y `case-management` van en la misma wave 5 de `components.yaml`, pero la wave no ordena un digest viejo de uno con uno nuevo del otro: el PR único sí.
