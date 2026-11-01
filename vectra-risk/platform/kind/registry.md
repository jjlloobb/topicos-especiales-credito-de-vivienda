# Registro local y LoadBalancer de kind

`runbooks/install.md` levanta el contenedor `kind-registry` y `cloud-provider-kind`, y conecta el registro a la red `kind` (INF-U1-05, 09). Este archivo explica cómo llegan las imágenes a los nodos.

## Resolución de imágenes

Los manifiestos usan `registro.vectra.internal/<imagen>@sha256:...` en todos los entornos. En kind no existe ese registro:

- `cluster.yaml` monta `platform/kind/certs.d` en `/etc/containerd/certs.d` de cada nodo y activa `config_path`.
- `certs.d/registro.vectra.internal/hosts.toml` envía esas descargas a `http://kind-registry:5000`, sin TLS y solo para `pull` y `resolve`.
- `certs.d/kind-registry:5000/hosts.toml` deja usar también el nombre directo. `imageRegistry` de `envs/kind/values.yaml` (`kind-registry:5000`) no lo lee ningún chart ni manifiesto hoy.

Desde el equipo del operador, el registro se publica en `localhost:5001`. La imagen `localhost:5001/restore-drill` es, para el nodo, `registro.vectra.internal/restore-drill`.

## Publicar una imagen

```bash
docker build -t localhost:5001/restore-drill:dev platform/restore-drill
docker push localhost:5001/restore-drill:dev
# El digest que va en el manifiesto:
docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/restore-drill:dev
```

Con Podman: `podman build ...` y `podman push --tls-verify=false localhost:5001/restore-drill:dev`. Con `crane`: `crane push imagen.tar localhost:5001/restore-drill:dev --insecure` y `crane digest localhost:5001/restore-drill:dev --insecure`.

El digest se reemplaza en Git, porque Argo CD despliega lo que hay en Git: un PR por imagen, o varias en uno.

## Sin verificar

El montaje de `certs.d` y el espejo no se han probado en un clúster real: nadie ha creado este clúster todavía.
