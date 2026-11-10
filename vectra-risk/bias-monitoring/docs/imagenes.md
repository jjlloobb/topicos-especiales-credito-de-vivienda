# Imagen de `bias-monitoring` en kind

**Una sola imagen con dos puntos de entrada** (P-U9-05): `python -m vectra_bias.app` (el servicio `bias-monitoring-service`, 8080 y 8081; es el `CMD`) y
`python -m vectra_bias.run` (el CronJob `bias-monitoring-job`, el único que congela). El chart elige con `command`. La construye este repositorio; el push y el
digest real los hace el **operador** en la verificación consolidada de U12 Paso 18 (enmienda §8; AUTONOMIA-01). Sin firma Cosign, SBOM ni escaneo (T1 de la
demo) y sin workflow de CI (T4). **Estos comandos no se ejecutan en la tarea de despliegue (U09-T04) más allá del `build` y las comprobaciones locales.**

## Construir (desde `vectra-risk/`)

```bash
make -C bias-monitoring image
# docker build -t localhost:5001/vectra/bias-monitoring:dev -f bias-monitoring/Dockerfile .   (contexto: la raíz de vectra-risk/)
```

Qué lleva la imagen final: Python 3.12 (imagen base fijada por digest en cada `FROM`), `vectra-bias`, `vectra-disparity` y sus dependencias del workspace
(`vectra-contracts`, `vectra-common`, `pyyaml`). Corre como `65532:65532`, igual que el `runAsUser` y el `runAsGroup` del chart. **No lleva** numpy, scipy, pandas,
Fairlearn ni scikit-learn (solo sirven a las pruebas y a la simulación), ni `pytest`, `hypothesis` o `hatchling`.

## Comprobar (local, sin clúster)

```bash
platform/.tools/bin/hadolint bias-monitoring/Dockerfile
docker image inspect localhost:5001/vectra/bias-monitoring:dev --format '{{.Config.User}}'   # 65532:65532
# «sin numpy» se comprueba con `pip list` en la imagen, no en un SBOM (el SBOM esta diferido, T1)
docker run --rm --entrypoint sh localhost:5001/vectra/bias-monitoring:dev -c '! pip list 2>/dev/null | grep -iE "^(numpy|scipy|pandas|fairlearn|scikit-learn|pytest|hypothesis) " && echo OK'
docker run --rm --entrypoint python localhost:5001/vectra/bias-monitoring:dev -c 'import vectra_bias.app, vectra_bias.run, vectra_disparity; print("OK-entradas")'
grep -nE '^FROM .*@sha256:[0-9a-f]{64}' bias-monitoring/Dockerfile
# el contenedor real arranca con las variables que pone el chart, contra dobles HTTP locales (CA-4)
uv run pytest bias-monitoring/tests/integration/test_image.py -v
```

## Publicar (operador, U12 Paso 18)

Igual que `identity-edge/docs/paso-16-kind.md` §3 y `decision-registry/docs/imagen-kind.md`:

```bash
docker push localhost:5001/vectra/bias-monitoring:dev
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/vectra/bias-monitoring:dev
```

El digest sale en el `inspect` (`localhost:5001/vectra/bias-monitoring@sha256:…`). Un PR lo escribe en `image.digest` de los values de kind
(`vectra-risk-gitops/values/kind/bias-monitoring.yaml`, que `generate.py` agrega solo cuando el archivo existe y se vuelve a correr) y regenera las
Applications con `uv run python vectra-risk-gitops/generate.py`. Hasta entonces el chart renderiza con el digest de ejemplo
(`sha256:…0004`) y los pods quedarían en `ImagePullBackOff`. El CronJob y el servicio comparten ese digest: una sola imagen.
