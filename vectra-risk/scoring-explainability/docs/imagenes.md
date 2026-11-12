# Imágenes de `scoring-explainability` en kind

Dos imágenes, una por servicio: `scoring-service` y `explainability-service`. Las construye este repositorio; el push y el digest real los hace el **operador** en la verificación consolidada de U12 Paso 18 (enmienda §8; AUTONOMIA-01). Sin firma Cosign, SBOM ni escaneo (T1 de la demo) y sin workflow de CI (T4). **Estos comandos no se ejecutan en la tarea de despliegue (U07-T04) más allá del `build` y las comprobaciones locales.**

## Construir (desde `vectra-risk/`)

```bash
make -C scoring-explainability image-scoring image-explainability
# docker build -t localhost:5001/vectra/scoring-service:dev -f scoring-explainability/scoring/Dockerfile .          (contexto: la raíz de vectra-risk/)
# docker build -t localhost:5001/vectra/explainability-service:dev -f scoring-explainability/explainability/Dockerfile .
```

Qué lleva cada imagen final: Python 3.12 (imagen base fijada por digest en cada `FROM`), el servicio (`vectra-scoring` o `vectra-explainability`) y sus dependencias del workspace (`vectra-contracts`, `vectra-common`). La de explainability lleva además las plantillas `template_v1.txt` y `applicant_v1.txt` (en `explainability/templates/` del paquete). Corren como `65532:65532`, igual que el `runAsUser` y el `runAsGroup` del chart, y arrancan con `vectra_common.ops_server.run_service(app)` (8080 y 8081) desde `scoring.app.main` y `explainability.app.main`. **No llevan** `pytest`, `hypothesis`, `hatchling`, cliente de LLM ni librería de circuit breaking (NFR-U7-32, NFR-U7-43).

## Comprobar (local, sin clúster)

```bash
platform/.tools/bin/hadolint scoring-explainability/*/Dockerfile
for s in scoring-service explainability-service; do
  docker image inspect localhost:5001/vectra/$s:dev --format '{{.Config.User}}'   # 65532:65532
  # «sin cliente de LLM ni circuit breaking» se comprueba con `pip list` en la imagen, no en un SBOM (el SBOM esta diferido, T1)
  docker run --rm --entrypoint sh localhost:5001/vectra/$s:dev -c '! pip list 2>/dev/null | grep -iE "^(openai|anthropic|langchain[a-z-]*|pybreaker|circuitbreaker|aiobreaker|purgatory[a-z-]*|pytest|hypothesis) " && echo OK'
done
docker run --rm --entrypoint sh localhost:5001/vectra/explainability-service:dev -c 'for p in template_v1.txt applicant_v1.txt; do find / -name $p 2>/dev/null | grep -q . || exit 1; done && echo OK-plantillas'
grep -nE '^FROM .*@sha256:[0-9a-f]{64}' scoring-explainability/*/Dockerfile
```

## Publicar (operador, U12 Paso 18)

Igual que `identity-edge/docs/paso-16-kind.md` §3, `decision-registry/docs/imagen-kind.md` y `bias-monitoring/docs/imagenes.md`:

```bash
docker push localhost:5001/vectra/scoring-service:dev
docker push localhost:5001/vectra/explainability-service:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/scoring-service:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/explainability-service:dev
```

El digest sale en el `inspect` (`localhost:5001/vectra/<servicio>@sha256:…`). Un PR lo escribe en `images.scoring.digest` y `images.explainability.digest` de los values de kind (`vectra-risk-gitops/values/kind/scoring-explainability.yaml`) y regenera las Applications con `uv run python vectra-risk-gitops/generate.py`. Hasta entonces el chart renderiza con los digests de ejemplo (`sha256:…0005` y `…0006`) y los pods quedarían en `ImagePullBackOff`.

## Un solo commit y un solo PR para governance, scoring y explainability (C-3)

`ServingConfig` (U0 §9.3) es un `StrictModel` con `additionalProperties: false`, y desde U04-T09 trae `cutoff`, `low_confidence_threshold` y `channel_rules`. Un consumidor con el tipo viejo **rechaza** la respuesta nueva y falla cerrado (`serving_config_unavailable`); `oasdiff` no lo marca como cambio incompatible. Por eso:

- construye las imágenes de `governance-service`, `scoring-service` y `explainability-service` **del mismo commit** (`make -C governance image`, `make -C scoring-explainability image-scoring image-explainability`);
- sube sus tres digests a los values de kind en **un solo PR** (`values/kind/governance.yaml` si existe y `values/kind/scoring-explainability.yaml`);
- `governance` y `scoring-explainability` ya van en la misma wave 5 de `components.yaml`, pero la wave no ordena un digest viejo de uno con uno nuevo del otro: el PR único sí.

U8 (`case-service` y `case-worker`, que también leen `serving-config`) debe tenerlo en cuenta: la entrada de `CANDIDATAS.md` sigue abierta para esa unidad. `evidence/cierre-demo.md` lo lleva en «Pendiente en U12».
