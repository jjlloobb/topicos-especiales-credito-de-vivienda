# Instalación en kind (Paso 19)

Lo ejecuta un **operador** después de un PR aprobado (AUTONOMIA-01). Ningún agente ni workflow aplica estos pasos. Nada de este procedimiento se ha ejecutado aún de punta a punta.

## Síntoma
Un entorno nuevo sin Vectra Risk.

## Impacto
Sin plataforma no se puede desplegar ninguna unidad.

## Diagnóstico
1. Comprueba las herramientas: `kind version` (v0.33.0), `kubectl version --client`, `helm version`, `docker version` (o `podman version`), `argocd version --client`, `uv --version`.
2. Comprueba que los charts estén descargados: `make -C platform charts`.

Todos los comandos corren desde la carpeta `vectra-risk/` del repositorio, salvo donde se indica, y con `--context kind-vectra` implícito: `kubectl config use-context kind-vectra` tras el paso 2. Otros clústeres de kind del equipo no se tocan.

## Antes de instalar: memoria y Docker
`kind/cluster.yaml` y los `*-kind.yaml` forman un perfil liviano para una máquina de 14 GiB: dos nodos, sin Loki, Tempo ni Alloy (ver «Qué instala kind»), una instancia de PostgreSQL por base (salvo `registry-db`, que lleva 2 con una réplica síncrona porque el `/readyz` del registro la exige) y nada más en HA. Este perfil no sirve para el simulacro de failover de zona (Paso 20): ese va en una máquina de al menos 32 GiB con `kind/cluster-ha.yaml`, y copia `platform/kind/postgres-failover.yaml` (3 instancias por cluster y `zoneConstraint: true`) a `vectra-risk-gitops/values/kind/postgres.yaml`; se quita al terminar.

- **Memoria:** `free -h` debe mostrar al menos 8 GiB disponibles, y la swap sin llenar. Cierra navegadores, Teams y máquinas virtuales de otros laboratorios. Con menos, la instalación puede matar pods o congelar el escritorio.
- **Docker:** usa Docker Engine nativo (`docker-ce`). Corre sin VM, y en 14 GiB la VM de Docker Desktop, con los 10 GiB que necesitaría, deja poco al sistema. Sin VM tampoco hay límite que proteja el escritorio: el mínimo de `free -h` de arriba es la protección. Docker Desktop también sirve en una máquina más grande, con al menos 10 GiB de memoria en su configuración. kind sobre Podman sin root no sirve aquí: no puede abrir el puerto 443 ni darle a Calico lo que necesita.
- **Un solo motor:** cada motor tiene sus propios clústeres e imágenes, así que usa uno durante todo el ensayo. El Docker de snap no se usa: kind lo lista como problema conocido porque puede no tener acceso a `$TMPDIR`. Si está instalado junto a `docker-ce`, puede quedarse con `/var/run/docker.sock` y con sus contenedores ocupar puertos como el 5001 del paso 4. Se desactiva con los comandos de abajo. Eso detiene sus contenedores, incluidos los registros de laboratorios con `--restart=always` como `registro-cks2`, y conserva sus datos; se revierte con `sudo snap start --enable docker`. El grupo `docker` da permiso sobre el motor y en la práctica equivale a acceso de root en la máquina.
  ```bash
  sudo snap stop --disable docker
  sudo systemctl stop docker.service docker.socket
  sudo systemctl start docker.socket docker.service
  sudo usermod -aG docker "$USER"   # cierra sesión y vuelve a entrar, o usa newgrp docker
  ```
  Para comprobarlo: `docker context use default`; `docker version --format '{{.Server.Version}}'` debe dar la misma versión que `dpkg-query -W -f='${Version}' docker-ce`, y `ss -ltn | grep ':5001 '` no debe mostrar nada. Si `ip -br addr | grep fc00:f853` muestra un puente, es la red `kind` que dejó el motor de snap: usa la misma subred IPv6 que kind por omisión y podría chocar al crear la red (no se ha probado). Con el snap ya desactivado, se quita con `sudo ip link delete <puente>`.
- **Credenciales de Docker:** si `~/.docker/config.json` conserva `"credsStore": "desktop"` de una instalación de Docker Desktop, las descargas pueden fallar con `docker-credential-desktop` y un error de `gpg`. Haz una copia del archivo y quita esa clave.
- **Límites de inotify:** con tres nodos, el valor por omisión de `fs.inotify.max_user_instances` (128) no alcanza: `linkerd-cni` falla en los workers con `couldn't initialize inotify: too many open files`. Medido el 2026-11-14: con 1024 (y `fs.inotify.max_user_watches` en 1048576) arranca. Antes de crear el clúster, y de forma persistente: `printf 'fs.inotify.max_user_instances=1024\nfs.inotify.max_user_watches=1048576\n' | sudo tee /etc/sysctl.d/99-vectra-kind.conf && sudo sysctl --system`. Un `sysctl` suelto no sobrevive a un reinicio.
- **Otro clúster:** Docker puede levantar el clúster `kind` que ya exista. Antes de instalar, `kind get clusters`: si `kind` aparece y no lo necesitas, elimínalo con `kind delete cluster --name kind`; si lo necesitas, detén sus contenedores. Compruebas el contexto antes de cada comando: `kubectl config current-context` debe decir `kind-vectra`.
- **Qué instala kind (U01-T11):** todo lo de `vectra-risk-gitops/apps/kind/` salvo `loki`, `tempo` y `alloy`, que **no se instalan en kind** (≈ 1,07 GiB y 1,3 CPU pedidos; ninguna demo ni U12 los lee). Staging y prod los siguen instalando. En kind Grafana solo lee Prometheus y el `otel-collector` termina sus trazas en el exportador `debug`. Los requests de CPU de kind también son menores (proxy de Linkerd 20m y pods de serving 100m; los limits no cambian). Son valores **no medidos** en el clúster: si `kubectl top` los desmiente, se suben en `platform/mesh/linkerd-kind.yaml` y `vectra-risk-gitops/values/kind/model-serving.yaml`.
- **Si se queda sin memoria:** detente y no sigas con la siguiente wave.

## Mitigación

### 1. Llave de etcd
```bash
(cd platform/kind && umask 077 && sed "s|GENERAR_CON_openssl_rand_-base64_32|$(openssl rand -base64 32)|" encryption-config.example.yaml > encryption-config.yaml)
```
`platform/kind/encryption-config.yaml` no va a Git (`.gitignore`).

### 2. Clúster
kind resuelve los `hostPath` de `cluster.yaml` contra el directorio actual; por eso corre **desde `platform/kind`**:
```bash
(cd platform/kind && kind create cluster --config cluster.yaml)
```
El clúster se llama `vectra` y el contexto, `kind-vectra`. Monta la llave y `certs.d`, el espejo de `registro.vectra.internal` (`platform/kind/registry.md`). Con Podman, antepón `KIND_EXPERIMENTAL_PROVIDER=podman`.

### 3. Calico y conformidad del CNI (INF-U1-04)
```bash
kubectl apply --server-side -f https://raw.githubusercontent.com/projectcalico/calico/v3.33.0/manifests/calico.yaml
kubectl wait --for=condition=Ready node --all --timeout=300s
sonobuoy run --e2e-focus NetworkPolicy --wait
```

### 4. Registro local y LoadBalancer (INF-U1-05, 09)
La red `kind` existe desde el paso 2. En kind no hay registro del banco: `kind-registry` hace de `registro.vectra.internal`.
```bash
docker run -d --restart=always --name kind-registry --network kind -p 127.0.0.1:5001:5000 \
  docker.io/library/registry:3.0.0@sha256:6c5666b861f3505b116bb9aa9b25175e71210414bd010d92035ff64018f9457e
# En otra terminal, y déjalo corriendo:
docker run --rm --network kind -v /var/run/docker.sock:/var/run/docker.sock \
  registry.k8s.io/cloud-provider-kind/cloud-controller-manager:v0.12.0@sha256:1b97632e5dfec8f83c7e970cf18cedb9e6b707e272011d712cabf6ab59d323c9
```

### 5. Imágenes propias
Publícalas en `localhost:5001` y reemplaza su digest de ceros por PR, porque Argo CD despliega lo que hay en `main`. Para el nodo, `registro.vectra.internal/x` es `localhost:5001/x` (`platform/kind/registry.md`).
```bash
docker build -t localhost:5001/restore-drill:dev platform/restore-drill
docker build -t localhost:5001/grafana-folder-permissions:dev platform/observability/grafana
docker build -t localhost:5001/minio:dev --target server platform/data/minio
docker build -t localhost:5001/mc:dev --target client platform/data/minio
for image in restore-drill grafana-folder-permissions minio mc; do
  docker push localhost:5001/$image:dev
  docker inspect --format '{{index .RepoDigests 0}}' localhost:5001/$image:dev
done
```
Los digest van en `platform/restore-drill/cronjob.yaml`, `platform/observability/grafana/manifests.yaml` y `platform/data/minio/values.yaml`. Con Podman: `podman push --tls-verify=false`. Con `crane`: `crane push imagen.tar localhost:5001/x:dev --insecure` y `crane digest`.

### 6. Argo CD
Primero con Helm, porque todavía no hay quien lo instale. Después se adopta con su `Application` (mismo nombre de release).
```bash
helm install argo-cd platform/.charts/argo-cd/argo-cd -n argocd --create-namespace \
  -f platform/operators/argo-cd.yaml -f platform/operators/argo-cd-kind.yaml
kubectl -n argocd rollout status deploy/argo-cd-argocd-server --timeout=300s
export ARGOCD_OPTS="--port-forward --port-forward-namespace argocd"
argocd login --username admin --password "$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)"
kubectl apply -f vectra-risk-gitops/apps/kind/project.yaml -f vectra-risk-gitops/apps/kind/root.yaml
argocd repo add ghcr.io/kserve/charts --type helm --name kserve --enable-oci
argocd repo add docker.io/envoyproxy --type helm --name envoyproxy --enable-oci
```

### 7. Sincronizar en orden
Sin auto-sync, las waves no se ordenan solas: este orden es el del operador.
`argocd app wait --health` termina en cuanto ve `Degraded`, y una aplicación puede pasar por ese estado al arrancar, como `kube-prometheus-stack`. Si falla ahí, mira los pods antes de darlo por fallo. También al revés: una aplicación puede verse `Healthy` antes de que un pod empiece a fallar, como `linkerd-cni`.
```bash
sync() { for app in "$@"; do argocd app sync "$app" && argocd app wait "$app" --health --timeout 900 || return 1; done; }
sync root argo-cd
# Wave 0
sync cert-manager trust-manager prometheus-operator-crds linkerd-crds linkerd-cni cloudnative-pg \
     external-secrets-rbac external-secrets-rbac-kind external-secrets kyverno envoy-gateway kserve-crd kserve vault
# Wave 1
sync namespaces priority-classes quotas mesh-certificates
sync metrics-server                                            # solo kind; lo necesitan los HPA
kubectl get configmap linkerd-identity-trust-roots -n linkerd   # debe existir antes del plano de control
sync linkerd-control-plane
platform/kind/seed-vault.sh                                    # paso 8
sync secret-store-env secret-store network   # primero el permiso de leer vault-token; si no, secret-store queda Degraded
sync verification-operator kyverno-context-rbac kyverno-policies   # `verify-images` no se instala en kind
# Wave 2: `postgres` entrega los Secret de MinIO, y MinIO recibe los backups de `postgres`. Ninguno espera al otro.
argocd app sync postgres
kubectl wait -n vectra-data externalsecret --all --for=condition=Ready --timeout=300s
sync minio
argocd app wait postgres --health --timeout 900
# Wave 3
sync grafana-secrets
# Wave 4
sync kube-prometheus-stack pushgateway otel-collector observability-rules observability-monitors grafana-dashboards   # sin loki, tempo ni alloy en kind
platform/kind/seed-vault.sh grafana-token                      # paso 9
sync grafana-config
# Wave 5
sync restore-drill
```

### 8. Secretos de Vault
`platform/kind/seed-vault.sh` genera al azar y escribe todas las rutas que piden los `ExternalSecret`; las saca de lo renderizado con `platform/kind/vault_paths.py` (`uv run python platform/kind/vault_paths.py list` las muestra). Conserva lo que ya exista. También crea `vault-token`, el Secret con el que ESO entra a Vault. Puede repetirse.

### 9. Token de Grafana (F110)
El Job de permisos de carpetas usa una **cuenta de servicio de Grafana** cuyo token llega por ESO. Solo se puede crear con Grafana en marcha, y por eso va entre `kube-prometheus-stack` y `grafana-config`. Hasta entonces, la bóveda tiene `pendiente-de-bootstrap` y el Job falla con 401.

- **En kind**: `platform/kind/seed-vault.sh grafana-token`.
- **En staging y prod**, con las credenciales de `grafana-admin` y por un túnel a Grafana (`kubectl port-forward -n vectra-observability svc/kube-prometheus-stack-grafana 13000:80`):
  ```bash
  curl -u "admin:$CLAVE" -H 'Content-Type: application/json' -X POST http://127.0.0.1:13000/api/serviceaccounts -d '{"name":"folder-permissions","role":"Admin"}'
  curl -u "admin:$CLAVE" -H 'Content-Type: application/json' -X POST http://127.0.0.1:13000/api/serviceaccounts/$ID/tokens -d '{"name":"job"}'
  ```
  Guarda `key` en la bóveda, ruta `grafana/folder-permissions`, propiedad `token`. El SQLite de Grafana conserva la cuenta en su PVC: si se pierde el PVC, repite este paso.

El Job crea los equipos que falten, pero no sus miembros.

### 10. Otros
- **Reactivar Loki, Tempo y Alloy en kind** (solo si la máquina tiene memoria de sobra; **no medido**, no se probó en el clúster): (1) en `vectra-risk-gitops/components.yaml` quita `envs: [staging, prod]` de `loki`, `tempo` y `alloy`; (2) en `platform/network/flows.yaml` quita `envs: [staging, prod]` de los workloads `loki`, `tempo` y `alloy` y del flujo F65 de tres destinos, y borra el F65 de `envs: [kind]`; (3) en `platform/observability/values/kube-prometheus-stack-kind.yaml` borra `additionalDataSources: []`, y en `platform/observability/values/otel-collector-kind.yaml` el pipeline `traces`; (4) en `platform/data/minio/values-kind.yaml` y `platform/data/chart/values-kind.yaml` vuelve a poner los buckets, políticas, usuarios y comandos de `loki` y `tempo` y los cuatro Secret (`minio-loki`, `minio-tempo`, `loki-s3`, `tempo-s3`: copia sus líneas de `values.yaml`); (5) `make -C platform generate`, y sincroniza `postgres`, `minio`, `kube-prometheus-stack`, `loki`, `tempo`, `otel-collector` y `alloy`, y vuelve a sembrar con `platform/kind/seed-vault.sh`. `test_kind_profile.py` falla mientras lo dejes así: ajusta `REMOVED_FROM_KIND` y `BUDGET_GIB`.
- **Retirar Loki, Tempo y Alloy de un clúster que ya los tenía** (operación del operador, **no ejecutada** en esta tarea): tras fusionar el cambio, `argocd app delete loki tempo alloy --cascade`, y borra los Secret `minio-loki`, `minio-tempo`, `loki-s3` y `tempo-s3` y los PVC de Loki y Tempo; los usuarios y buckets `loki` y `tempo` de MinIO se quitan con `mc admin user remove` y `mc rb --force`. Un clúster que no se retira sigue funcionando: Argo CD solo deja de gestionar esas Applications.
- Emite el certificado de cliente del operador de verificación con el grupo `vectra-verification-operators` en `O=` (sujeto de K16): `openssl req -new -key operador.key -subj "/CN=operador/O=vectra-verification-operators"`.
- Exporta la CA del borde que usa U12: `kubectl get secret -n cert-manager vectra-internal-ca -o jsonpath='{.data.ca\.crt}'`.
- Para subir modelos (NFR-U5-03), el ingeniero lee `minio/engineer-upload` en la bóveda y llega a MinIO con `kubectl port-forward -n vectra-data svc/minio 9000`.

### Vault reiniciado
Vault dev guarda todo en memoria. Si el pod se reinicia, lo sembrado se pierde y `seed-vault.sh` genera **claves nuevas**, que ya no coinciden con las que usan PostgreSQL, MinIO y Grafana. Desde U01-T10 el pod declara requests y limits iguales (256 Mi, QoS Guaranteed): ya no es lo primero que mata el OOM, pero un reinicio sigue borrando todo. Lo de abajo es lo que se **midió en `kind-vectra` el 2026-11-14**, en este orden; lo que no se midió lo dice. Si la máquina también se reinició, empieza por «Tras reiniciar la máquina».
1. **Límites de inotify.** Si `linkerd-cni` falla en los workers con `couldn't initialize inotify: too many open files`, mira `sysctl fs.inotify.max_user_instances` (era 128). Con 1024 (y `max_user_watches` 1048576, persistente en `/etc/sysctl.d/`) arrancó; ver «Antes de instalar».
2. **Recrear los pods con malla.** Los pods con proxy creados antes del arreglo no se recuperan solos: `linkerd-network-validator` falla con «Failed to validate networking configuration». Se borran, en este orden: primero los de `linkerd`, luego los de `vectra-data` y luego los de `vectra-observability` (`kubectl delete pod -n <namespace> --all`, esperando a que cada namespace vuelva a `Running`: la forma del comando y la espera son el procedimiento propuesto y **no salen de lo medido el 2026-11-14**). Para el resto de los namespaces con malla no se midió.
3. **Resiembra.** `platform/kind/seed-vault.sh` y, después, `platform/kind/seed-vault.sh identity`. Devolvieron los `ExternalSecret` a sincronizados, con claves **nuevas**. Los pasos 4 a 6 existen por esas claves nuevas.
4. **Claves de MinIO.** `argocd app sync minio` termina bien y **no cambia nada**: el Job `minio-post-job` solo crea un usuario si no existe («User already exists»), así que MinIO sigue con las claves viejas. Síntomas (de cuando estaban Tempo y Loki): Tempo en `CrashLoopBackOff` con «signature does not match» y Loki con 403. Lo que lo arregló fue un Job de una sola vez, en `vectra-data`, que corre el script `add-user` del chart forzando `mc admin user add` para los 12 usuarios de MinIO de entonces (10 sin Loki ni Tempo), con `priorityClassName: vectra-normal` (Kyverno lo exige en ese namespace). **Decisión: va como procedimiento y no como manifiesto versionado.** Ese Job no se conservó, no hay clúster para volver a probarlo en esta tarea, y un manifiesto sin probar en `platform/` entraría en lo que renderizan y evalúan las pruebas. Pasos: (a) toma el script de `kubectl get configmap minio -n vectra-data -o jsonpath='{.data.add-user}'`; (b) crea un Job con la imagen `mc` del chart (`mcImage` de `platform/data/minio/values-kind.yaml` o `values.yaml`), `priorityClassName: vectra-normal`, los volúmenes y Secret de ese script (los `existingSecret` de los usuarios) y los `resources` y `securityContext` de `makePolicyJob`; (c) cambia en una copia del script la creación de cada usuario por `mc admin user add` incondicional. Es el único paso de esta lista que hay que rehacer a mano, y no está medido cuánto del script se puede reutilizar sin cambios. Candidata: versionar este Job (ver el informe de U01-T10).
5. **Tempo y Loki** (solo si los reactivaste; kind ya no los instala, y esto se midió cuando sí estaban). Después del paso 4, reinicia los pods de Tempo (`kubectl rollout restart` de sus Deployments y StatefulSets en `vectra-observability`). Loki se midió con 403 antes del paso 4; que se recupere solo con las claves nuevas no se midió, comprueba sus logs.
6. **Grafana.** La clave de `admin` del Secret daba 401 (la base de Grafana conserva la vieja). Fíjala con `kubectl exec -n vectra-observability deploy/kube-prometheus-stack-grafana -c grafana -- grafana cli admin reset-admin-password "$(kubectl get secret grafana-admin -n vectra-observability -o jsonpath='{.data.admin-password}' | base64 -d)"`. Luego `platform/kind/seed-vault.sh grafana-token` y `argocd app sync grafana-config`. (Con 256 MiB de límite el `grafana cli` no cabía; ya está en 512 MiB.)
7. **PostgreSQL.** CloudNativePG aplica las contraseñas nuevas de los roles gestionados al cambiar sus Secret; reinicia los pods que las leen. **No se midió** en la sesión del 2026-11-14.
8. **Identidad (Keycloak).** **No medido.** Keycloak no estaba instalado el 2026-11-14. Tras `seed-vault.sh identity` puede hacer falta la clave de `keycloak-admin`, las llaves de cliente y `keycloak-config-cli`; no se sabe en qué orden ni cuáles, y este runbook no lo adivina. Se mide cuando se instale.

### Tras reiniciar la máquina
Una máquina reiniciada pierde, además de la bóveda: (1) los `sysctl` que no estaban en `/etc/sysctl.d/` (ver el paso 1 de arriba); (2) `cloud-provider-kind`, que se lanza con `--rm` y **no sobrevive al reinicio**: hay que volver a lanzarlo (paso 4 de «Mitigación», en otra terminal) o los `LoadBalancer` quedan sin dirección; (3) la bóveda, porque su pod se recrea: sigue en «Vault reiniciado». Orden: `sysctl`, contenedores de kind y del registro (`docker ps`; **no medido**: el orden y este paso no salen de lo medido el 2026-11-14), `cloud-provider-kind`, y luego los pasos 2 a 8 de «Vault reiniciado». No se midió cuánto tarda el clúster en volver a `Ready` tras un reinicio.

**Espera de `product-metrics` en la wave 5:** su readiness exige una instantánea, y cada réplica hace una pasada completa antes de quedar lista. Con 10 veces el volumen esperado, el rollout puede tardar hasta unas 2,5 h, y Argo CD no pasa a la wave 6 hasta entonces. Es una espera y no una falla si `vectra_product_full_pass_in_progress = 1` y `vectra_product_entries_read_total` crece. Con U3 caído, la réplica queda lista enseguida.

## Escalamiento
Si una wave no llega a `Healthy`, detén la instalación y abre un issue con la evidencia.

## Verificación
- `argocd app list -o json`: todas `Synced` y `Healthy`, ninguna con `automated`.
- `linkerd check`.
- `kubectl get clusters.postgresql.cnpg.io -A`: `registry-db` con 2 instancias y una réplica síncrona; las otras con 1.
- `kubectl top nodes` responde (metrics-server, solo kind; los HPA lo necesitan).
- `kubectl get externalsecrets.external-secrets.io -A`: todos `SecretSynced`.
- `curl -s localhost:5001/v2/_catalog`: las cuatro imágenes propias.
