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
`kind/cluster.yaml` y los `*-kind.yaml` forman un perfil liviano para una máquina de 14 GiB: dos nodos, una instancia de PostgreSQL por base y nada en HA. Sin réplica síncrona no sirve para el simulacro de failover de zona (Paso 20): ese va en una máquina de al menos 32 GiB con `kind/cluster-ha.yaml`, y `instances: 3` y `zoneConstraint: true` en `vectra-risk-gitops/values/kind/postgres.yaml`.

- **Memoria:** `free -h` debe mostrar al menos 8 GiB disponibles, y la swap sin llenar. Cierra navegadores, Teams y máquinas virtuales de otros laboratorios. Con menos, la instalación puede matar pods o congelar el escritorio.
- **Docker:** usa Docker Engine nativo (`docker-ce`). Corre sin VM, y en 14 GiB la VM de Docker Desktop, con los 10 GiB que necesitaría, deja poco al sistema. Sin VM tampoco hay límite que proteja el escritorio: el mínimo de `free -h` de arriba es la protección. Docker Desktop también sirve en una máquina más grande, con al menos 10 GiB de memoria en su configuración. kind sobre Podman sin root no sirve aquí: no puede abrir el puerto 443 ni darle a Calico lo que necesita.
- **Un solo motor:** cada motor tiene sus propios clústeres e imágenes, así que usa uno durante todo el ensayo. El Docker de snap no se usa: kind lo lista como problema conocido porque puede no tener acceso a `$TMPDIR`. Si está instalado junto a `docker-ce`, puede quedarse con `/var/run/docker.sock` y con sus contenedores ocupar puertos como el 5001 del paso 4. Se desactiva con los comandos de abajo. Eso detiene sus contenedores, incluidos los registros de laboratorios con `--restart=always` como `registro-cks2`, y conserva sus datos; se revierte con `sudo snap start --enable docker`. El grupo `docker` da permiso sobre el motor y en la práctica equivale a acceso de root en la máquina.
  ```bash
  sudo snap stop --disable docker
  sudo systemctl stop docker.service docker.socket
  sudo systemctl start docker.socket docker.service
  sudo usermod -aG docker "$USER"   # cierra sesión y vuelve a entrar, o usa newgrp docker
  ```
  Para comprobarlo: `docker context use default`; `docker version --format '{{.Server.Version}}'` debe dar la misma versión que `dpkg-query -W -f='${Version}' docker-ce`, y `ss -ltn | grep ':5001 '` no debe mostrar nada.
- **Otro clúster:** Docker puede levantar el clúster `kind` que ya exista. Antes de instalar, `kind get clusters`: si `kind` aparece y no lo necesitas, elimínalo con `kind delete cluster --name kind`; si lo necesitas, detén sus contenedores. Compruebas el contexto antes de cada comando: `kubectl config current-context` debe decir `kind-vectra`.
- **Si se queda sin memoria:** detente y no sigas con la siguiente wave. Puedes dejar para el final `loki`, `tempo` y `alloy`.

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
```bash
sync() { for app in "$@"; do argocd app sync "$app" && argocd app wait "$app" --health --timeout 900 || return 1; done; }
sync root argo-cd
# Wave 0
sync cert-manager trust-manager prometheus-operator-crds linkerd-crds linkerd-cni cloudnative-pg \
     external-secrets-rbac external-secrets kyverno envoy-gateway kserve-crd kserve vault
# Wave 1
sync namespaces priority-classes quotas mesh-certificates
kubectl get configmap linkerd-identity-trust-roots -n linkerd   # debe existir antes del plano de control
sync linkerd-control-plane
platform/kind/seed-vault.sh                                    # paso 8
sync secret-store secret-store-env network verification-operator kyverno-context-rbac kyverno-policies   # `verify-images` no se instala en kind
# Wave 2: `postgres` entrega los Secret de MinIO, y MinIO recibe los backups de `postgres`. Ninguno espera al otro.
argocd app sync postgres
kubectl wait -n vectra-data externalsecret --all --for=condition=Ready --timeout=300s
sync minio
argocd app wait postgres --health --timeout 900
# Wave 3
sync grafana-secrets
# Wave 4
sync kube-prometheus-stack pushgateway loki tempo otel-collector alloy observability-rules observability-monitors grafana-dashboards
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
- Emite el certificado de cliente del operador de verificación con el grupo `vectra-verification-operators` en `O=` (sujeto de K16): `openssl req -new -key operador.key -subj "/CN=operador/O=vectra-verification-operators"`.
- Exporta la CA del borde que usa U12: `kubectl get secret -n cert-manager vectra-internal-ca -o jsonpath='{.data.ca\.crt}'`.
- Para subir modelos (NFR-U5-03), el ingeniero lee `minio/engineer-upload` en la bóveda y llega a MinIO con `kubectl port-forward -n vectra-data svc/minio 9000`.

### Vault reiniciado
Vault dev guarda todo en memoria. Si el pod se reinicia, lo sembrado se pierde y `seed-vault.sh` genera **claves nuevas**, que ya no coinciden con las que usan PostgreSQL, MinIO y Grafana. Hay que volver a sincronizarlas:
1. `platform/kind/seed-vault.sh`, que crea las rutas y fuerza el refresco de los `ExternalSecret`.
2. PostgreSQL: CloudNativePG aplica las nuevas contraseñas de los roles gestionados al cambiar sus Secret. Reinicia los pods que las leen.
3. MinIO: `kubectl rollout restart statefulset/minio -n vectra-data` para la raíz y `argocd app sync minio`, cuyo Job vuelve a crear los usuarios.
4. Grafana: la base de Grafana conserva la clave vieja de `admin`. Fíjala con `kubectl exec -n vectra-observability deploy/kube-prometheus-stack-grafana -c grafana -- grafana cli admin reset-admin-password "$(kubectl get secret grafana-admin -n vectra-observability -o jsonpath='{.data.admin-password}' | base64 -d)"`.
5. Paso 9, `seed-vault.sh grafana-token`, y `argocd app sync grafana-config`.

**Espera de `product-metrics` en la wave 5:** su readiness exige una instantánea, y cada réplica hace una pasada completa antes de quedar lista. Con 10 veces el volumen esperado, el rollout puede tardar hasta unas 2,5 h, y Argo CD no pasa a la wave 6 hasta entonces. Es una espera y no una falla si `vectra_product_full_pass_in_progress = 1` y `vectra_product_entries_read_total` crece. Con U3 caído, la réplica queda lista enseguida.

## Escalamiento
Si una wave no llega a `Healthy`, detén la instalación y abre un issue con la evidencia.

## Verificación
- `argocd app list -o json`: todas `Synced` y `Healthy`, ninguna con `automated`.
- `linkerd check`.
- `kubectl get clusters.postgresql.cnpg.io -A`.
- `kubectl get externalsecrets.external-secrets.io -A`: todos `SecretSynced`.
- `curl -s localhost:5001/v2/_catalog`: las cuatro imágenes propias.
