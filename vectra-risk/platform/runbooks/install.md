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
`kind/cluster.yaml` y los `*-kind.yaml` forman un perfil liviano para la máquina de la demo, de 14,8 GiB (`MemTotal` 15535356 kB): tres nodos (un plano de control y dos workers, `kind/cluster.yaml`), sin Loki, Tempo ni Alloy (ver «Qué instala kind»), una instancia de PostgreSQL por base (salvo `registry-db`, que lleva 2 con una réplica síncrona porque el `/readyz` del registro la exige) y nada más en HA. Este perfil no sirve para el simulacro de failover de zona (Paso 20): ese va en una máquina de al menos 32 GiB con `kind/cluster-ha.yaml`, y sigue el procedimiento de «Simulacro de failover de zona (Paso 20)» (más abajo): copiar `platform/kind/postgres-failover.yaml` a `vectra-risk-gitops/values/kind/postgres.yaml`, regenerar con `generate.py`, llevar el cambio a `main` y deshacerlo al terminar.

- **Memoria:** `free -h` debe mostrar al menos 8 GiB disponibles, y la swap sin llenar. Cierra navegadores, Teams y máquinas virtuales de otros laboratorios. Con menos, la instalación puede matar pods o congelar el escritorio.
- **Docker:** usa Docker Engine nativo (`docker-ce`). Corre sin VM, y en 14,8 GiB la VM de Docker Desktop, con los 10 GiB que necesitaría, deja poco al sistema. Sin VM tampoco hay límite que proteja el escritorio: el mínimo de `free -h` de arriba es la protección. Docker Desktop también sirve en una máquina más grande, con al menos 10 GiB de memoria en su configuración. kind sobre Podman sin root no sirve aquí: no puede abrir el puerto 443 ni darle a Calico lo que necesita.
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
- **Qué instala kind (U01-T11):** todo lo de `vectra-risk-gitops/apps/kind/` salvo `loki`, `tempo` y `alloy`, que **no se instalan en kind** (≈ 1,07 GiB y 1,3 CPU pedidos; ninguna demo ni U12 los lee). Staging y prod los siguen instalando. En kind Grafana solo lee Prometheus y el `otel-collector` termina sus trazas en el exportador `debug`. Los requests de CPU de kind también son menores (proxy de Linkerd 20m y pods de serving 100m; los limits no cambian). Son valores **no medidos** en el clúster: si `kubectl top` los desmiente, se suben en `platform/mesh/linkerd-kind.yaml` y `vectra-risk-gitops/values/kind/model-serving.yaml`. **Serving no escala en kind (U01-T12):** `maxReplicas` = `minReplicas` = 2 en el perfil `prod` de `values/kind/model-serving.yaml`; con 100m de request el HPA al 60 % subiría a 4 y 6 réplicas con casi cualquier tráfico (+3,23 GiB por InferenceService de prod, que nadie contaba). **Ningún HPA de kind crece más allá de lo contado (U01-T13):** `decision-registry`, `governance`, `scoring-service`, `explainability-service`, `case-service`, `case-worker` y `console-bff` van de 2 a 2 solo en kind, y el data plane de Envoy corre con **1 réplica fija** (HPA de 1 a 1; staging y prod siguen en 2 y de 2 a 6). **Presupuesto del pico de D2** (`platform/tests/test_kind_profile.py`, requests y no uso real, con el Job de validación y `kube-system`): 13,73 GiB con Keycloak de 1 a 1 (el HPA de kind, U12-T08; `BUDGET_GIB` = 13,8; serían 14,75 con 2 réplicas) frente a los 14,8 GiB de la máquina; el tope de CPU pedida es 10,7 (`CPU_BUDGET`): reparte pesos entre los 8 núcleos físicos que comparten los tres nodos y no es capacidad.
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
# Con nombre, en segundo plano y con reinicio, como kind-registry: sobrevive al reinicio de la máquina (U01-T16)
docker run -d --restart=always --name cloud-provider-kind --network kind -v /var/run/docker.sock:/var/run/docker.sock \
  registry.k8s.io/cloud-provider-kind/cloud-controller-manager:v0.12.0@sha256:1b97632e5dfec8f83c7e970cf18cedb9e6b707e272011d712cabf6ab59d323c9
```
Antes se lanzaba con `--rm` en otra terminal y no sobrevivía a un reinicio: si el que corre es de esa forma (sin nombre, `docker ps --filter ancestor=…` lo muestra), páralo con `docker stop` y lánzalo así. **Si, al volver, corrige solo la dirección del Service y los destinos del balanceador, no se sabe sin un clúster**: no se pudo leer su documentación ni su código en esta tarea (U01-T16) y no se midió. Por eso `platform/kind/gateway-address.sh` es un paso del runbook tras cada reinicio (ver «Tras reiniciar la máquina»).

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
`platform/kind/seed-vault.sh` escribe todas las rutas que piden los `ExternalSecret`; las saca de lo renderizado con `platform/kind/vault_paths.py` (`uv run python platform/kind/vault_paths.py list` las muestra). Para cada propiedad **conserva** lo que ya exista en la bóveda; si falta, la **recupera** del `Secret` que un `ExternalSecret` dejó en el clúster (solo copias literales; en una instalación nueva no hay ninguno); y solo si no hay de dónde recuperarla la **genera** al azar. Al terminar imprime, por ruta, cuántas conservó, recuperó y generó (con los nombres de las generadas, nunca los valores). También crea `vault-token`, el Secret con el que ESO entra a Vault. Puede repetirse. Si la misma propiedad está en dos `Secret` con valores distintos, se detiene y dice dónde (no elige en silencio).

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

### Simulacro de failover de zona (Paso 20)
Solo con `kind/cluster-ha.yaml` (≥ 32 GiB). Argo CD **no** agrega solo el archivo de values: la lista `valueFiles` de `apps/kind/postgres.yaml` sale de `generate.py`, que añade `values/kind/postgres.yaml` solo si existe. Copiar el archivo sin regenerar deja `generate.py --check` en rc 1 y la Application sin el override. Además, Argo CD lee `targetRevision: main`: el cambio tiene que estar en `main`. Desde `vectra-risk/`:

```bash
# simulacro-failover: aplicar
cp platform/kind/postgres-failover.yaml vectra-risk-gitops/values/kind/postgres.yaml
uv run python vectra-risk-gitops/generate.py
uv run python vectra-risk-gitops/generate.py --check
```

Lleva `vectra-risk-gitops/values/kind/postgres.yaml` y `vectra-risk-gitops/apps/kind/postgres.yaml` a `main` (PR), sincroniza `postgres` en Argo CD y comprueba `kubectl get cluster -n vectra-data` (3 instancias en `registry-db`, `case-db`, `governance-db` y `keycloak-db`). **No medido en un clúster:** una prueba (`test_kind_profile.py`) ejecuta estos comandos en una copia y comprueba el render con los `valueFiles` de la Application. Al terminar el simulacro, deshazlo y lleva también ese cambio a `main`:

```bash
# simulacro-failover: deshacer
rm vectra-risk-gitops/values/kind/postgres.yaml
uv run python vectra-risk-gitops/generate.py
uv run python vectra-risk-gitops/generate.py --check
```

### Vault reiniciado
Vault dev guarda todo en memoria. Si el pod se reinicia (o la máquina), lo sembrado se pierde y los `ExternalSecret` quedan en `False` («could not get secret data from provider»), pero **los `Secret` destino siguen con los valores de antes** (`deletionPolicy: Retain`; medido el 2026-11-16, dos minutos después de reiniciar la máquina: 71 `ExternalSecret` en `False` y los 71 `Secret` presentes). Desde U01-T16 la siembra **recupera antes de generar**: devuelve a la bóveda los valores de esos `Secret`, y solo genera lo que no tiene de dónde recuperar. Antes generaba todo al azar, y las claves nuevas dejaban de coincidir con las que guardan Keycloak, MinIO, Grafana, PostgreSQL y Valkey.

**Si el informe de la siembra termina en «Todo se conservó o se recuperó: nada que realinear», los pasos 4 a 8 no hacen falta.** Si generó algo, esos pasos son el camino para **lo generado** (el informe dice qué: ruta y nombre de propiedad). Lo que sigue de los pasos 4 a 8 se **midió en `kind-vectra` el 2026-11-14**, cuando la siembra generaba todo; lo que no se midió lo dice. La recuperación se probó con ejecutores falsos (U01-T16) y **aún no se ha corrido en el clúster**. Si la máquina también se reinició, empieza por «Tras reiniciar la máquina». Desde U01-T10 el pod de la bóveda declara requests y limits iguales (256 Mi, QoS Guaranteed): ya no es lo primero que mata el OOM, pero un reinicio sigue borrando todo.
1. **Límites de inotify.** Si `linkerd-cni` falla en los workers con `couldn't initialize inotify: too many open files`, mira `sysctl fs.inotify.max_user_instances` (era 128). Con 1024 (y `max_user_watches` 1048576, persistente en `/etc/sysctl.d/`) arrancó; ver «Antes de instalar».
2. **Recrear los pods con malla.** Los pods con proxy creados antes del arreglo no se recuperan solos: `linkerd-network-validator` falla con «Failed to validate networking configuration». Se borran, en este orden: primero los de `linkerd`, luego los de `vectra-data` y luego los de `vectra-observability` (`kubectl delete pod -n <namespace> --all`, esperando a que cada namespace vuelva a `Running`: la forma del comando y la espera son el procedimiento propuesto y **no salen de lo medido el 2026-11-14**). Para el resto de los namespaces con malla no se midió.
3. **Resiembra.** `platform/kind/seed-vault.sh` y, después, `platform/kind/seed-vault.sh identity`. Cada una imprime una línea por ruta (`ruta: conservadas N, recuperadas N, generadas N (nombres)`) y el cierre que dice si hay algo que realinear; **léelo antes de seguir** (medido el 2026-11-14, cuando la siembra generaba todo: las dos devolvieron los `ExternalSecret` a sincronizados, con claves **nuevas**). La segunda, además, fuerza el refresco de los `ExternalSecret` de **todos** los namespaces que leen `identity/` o `edge/valkey` (los saca de los `ExternalSecret` del clúster: `vault_paths.py identity-namespaces`), no solo de tres. Qué se recupera y qué no:
   - **Se recupera** lo que un `Secret` guarda como copia literal del valor de la bóveda: contraseñas de los roles de PostgreSQL, claves de MinIO, `grafana/admin`, el token de `grafana/folder-permissions` (si el `Secret` aún tiene el real, `seed-vault.sh grafana-token` no hace falta), el administrador de arranque, las contraseñas y semillas TOTP de los usuarios sintéticos y la llave privada de cada cliente (los `*-client` de U3 a U11). El `jwks` de un cliente se recupera **con** su llave privada, del mismo par: si el `jwks` recuperado no corresponde a la privada, o no hay privada, no se mezclan (en el segundo caso se genera el par entero y se informa).
   - **No se recupera, y se genera nuevo** (el informe lo dice). Son **seis rutas** en `identity`, y qué hacer con cada una:
     1. `identity/clients/channel`, `identity/clients/channel-simulator` y `identity/clients/verification-reader` (`generadas 2 (jwks, private-key)`): ningún chart ni `identity-edge` declara un `ExternalSecret` de su llave privada, así que solo vivía en la bóveda y en el directorio de las pruebas e2e (`/run/user/<uid>/vectra-e2e-keys`, un tmpfs que un reinicio borra). Se genera el par entero (nunca la privada de un lado y el `jwks` de otro). Keycloak conserva los `jwks` viejos hasta reimportar el realm: hasta entonces fallan `channel-simulator` (F07) y `verification-reader`, es decir, la verificación de U12. Paso 8.
     2. `identity/clients/grafana` (`jwks`): solo vive dentro de una plantilla (`toJson`) y no tiene llave privada. Mismo paso 8.
     3. `edge/valkey` (`ratelimit`, `replication`, `sentinel`, `sentinel-peer`; `exporter` y `sentinel-ratelimit` sí tienen copia literal): solo viven dentro de archivos compuestos. Paso 9, **enseguida**.
     4. `identity/break-glass` (`BREAK_GLASS_PASSWORD`): ningún `ExternalSecret` la lee (el realm de kind no la usa); se genera siempre y no hay nada que realinear. El informe la marca «nadie la lee» y **no cuenta** en el cierre: con las otras cinco recuperadas, el cierre sigue diciendo «nada que realinear».
     Una plantilla solo cuenta como copia literal si es exactamente `{{ .clave }}`, sin nada alrededor (espacios, saltos de línea, otro texto): ESO conserva ese contorno y el valor del `Secret` ya no sería el de la bóveda.
   - **Se conservan fijos** los nombres (`username` de los roles, `accessKey` de MinIO, `admin`, la URL del relay), y la CA sale siempre de `vectra-internal-ca` (cert-manager).
4. **Claves de MinIO.** Solo si el informe generó una `minio/*`. Con las claves recuperadas MinIO conserva las suyas y coinciden. Lo medido el 2026-11-14, con claves nuevas: `argocd app sync minio` termina bien y **no cambia nada**: el Job `minio-post-job` solo crea un usuario si no existe («User already exists»), así que MinIO sigue con las claves viejas. Síntomas (de cuando estaban Tempo y Loki): Tempo en `CrashLoopBackOff` con «signature does not match» y Loki con 403. Lo que lo arregló fue un Job de una sola vez, en `vectra-data`, que corre el script `add-user` del chart forzando `mc admin user add` para los 12 usuarios de MinIO de entonces (10 sin Loki ni Tempo), con `priorityClassName: vectra-normal` (Kyverno lo exige en ese namespace). **Decisión: va como procedimiento y no como manifiesto versionado.** Ese Job no se conservó, no hay clúster para volver a probarlo en esta tarea, y un manifiesto sin probar en `platform/` entraría en lo que renderizan y evalúan las pruebas. Pasos: (a) toma el script de `kubectl get configmap minio -n vectra-data -o jsonpath='{.data.add-user}'`; (b) crea un Job con la imagen `mc` del chart (`mcImage` de `platform/data/minio/values-kind.yaml` o `values.yaml`), `priorityClassName: vectra-normal`, los volúmenes y Secret de ese script (los `existingSecret` de los usuarios) y los `resources` y `securityContext` de `makePolicyJob`; (c) cambia en una copia del script la creación de cada usuario por `mc admin user add` incondicional. Es el único paso de esta lista que hay que rehacer a mano, y no está medido cuánto del script se puede reutilizar sin cambios. Candidata: versionar este Job (ver el informe de U01-T10).
5. **Tempo y Loki** (solo si los reactivaste; kind ya no los instala, y esto se midió cuando sí estaban). Después del paso 4, reinicia los pods de Tempo (`kubectl rollout restart` de sus Deployments y StatefulSets en `vectra-observability`). Loki se midió con 403 antes del paso 4; que se recupere solo con las claves nuevas no se midió, comprueba sus logs.
6. **Grafana.** Solo si el informe generó `grafana/admin`. La clave de `admin` del Secret daba 401 (la base de Grafana conserva la vieja; medido el 2026-11-14 con claves nuevas). Fíjala con `kubectl exec -n vectra-observability deploy/kube-prometheus-stack-grafana -c grafana -- grafana cli admin reset-admin-password "$(kubectl get secret grafana-admin -n vectra-observability -o jsonpath='{.data.admin-password}' | base64 -d)"`. Luego `platform/kind/seed-vault.sh grafana-token` (si el token se generó como marcador, no si se recuperó) y `argocd app sync grafana-config`. (Con 256 MiB de límite el `grafana cli` no cabía; ya está en 512 MiB.)
7. **PostgreSQL.** Solo si el informe generó una `postgres/roles/*`. CloudNativePG aplica las contraseñas nuevas de los roles gestionados al cambiar sus Secret; reinicia los pods que las leen. **No se midió** en la sesión del 2026-11-14.
8. **Identidad (Keycloak).** **No medido tras un reinicio.** Keycloak se instaló el 2026-11-15 (ver abajo). Con todo recuperado, Keycloak conserva el administrador de arranque, las contraseñas y OTP de los usuarios y las llaves de cliente del realm, y coinciden con la bóveda: nada que hacer. Lo que el informe diga generado en `identity/` (los tres pares de `channel`, `channel-simulator` y `verification-reader`, el `jwks` de `grafana`, y, si faltara el `Secret`, contraseñas o semillas de usuarios o `identity/keycloak-admin`) ya no coincide con lo que Keycloak guarda en el realm importado y en PostgreSQL. **Procedimiento propuesto, no medido:** (a) `argocd app sync keycloak`, para que el hook `keycloak-config-cli` reimporte el realm con los `jwks` nuevos (si el primer sync termina en `Failed`, repítelo: ver «Lo medido el 2026-11-15», punto 3); (b) `argocd app wait keycloak --health --timeout 900`; (c) comprueba que el Job `keycloak-config-cli` terminó (`kubectl get jobs -n vectra-identity`) y corre `system-verification/docs/kind/identidad.sh` (solo lectura). Contraseñas de usuarios que ya existen: `config-cli` no las reaplica (K-27), y el administrador de arranque solo se crea al primer arranque; para eso no hay procedimiento medido y no se adivina aquí.
9. **Valkey y `envoy-ratelimit`** (solo si el informe generó `edge/valkey`). **No medido.** Tras `seed-vault.sh identity`, ESO reescribe los `Secret` `valkey-acl` (`vectra-edge`) y `envoy-ratelimit-valkey` (`envoy-gateway-system`) con las claves nuevas, pero Valkey carga su ACL al arrancar, los Sentinel componen su configuración al arrancar y el `ratelimit` lee sus variables al crearse el pod. Mientras no se reinicien, todo sigue con las viejas; cualquier reinicio parcial (OOM, desalojo) deja un lado con la clave nueva y otro con la vieja y da `WRONGPASS` en el `ratelimit`, y como `/auth/**` falla cerrado (`failure_mode_deny`) el login responde 503. Reinicia **juntos y enseguida**: `kubectl rollout restart statefulset/valkey-a statefulset/valkey-b statefulset/sentinel-a statefulset/sentinel-b -n vectra-edge` y el Deployment del `ratelimit` en `envoy-gateway-system` (`kubectl get deploy -n envoy-gateway-system` para su nombre, que no se verificó aquí; `rollout restart` de ese). Qué mirar después: `kubectl rollout status` de cada uno, que los pods de Valkey y Sentinel estén `Running` y que los logs de `ratelimit` no traigan `WRONGPASS`; y un login por el gateway (`humo login`, la función de la guía de U12).

### Lo medido el 2026-11-15 al desplegar U2 en kind
Cuatro hechos de `kind-vectra`, en el orden en que salen al instalar. Lo que no se midió lo dice.
1. **Pods con malla tras sincronizar `linkerd-control-plane`.** Los pods con malla creados antes del sync siguieron en `Running`, pero su proxy rechazaba las conexiones entrantes sin registrar nada. El proxy de `keycloak-db-1` dejó en su log `Unexpected policy controller response; retrying with a backoff … "initial item not received within timeout"`, y Keycloak veía `Connection reset` al negociar TLS con PostgreSQL (métrica del proxy cliente: `outbound_tcp_errors_total{error="i/o"}`; del servidor: `inbound_tcp_errors_total{error="i/o",target_port="4143"}`, sin `authz_allow` ni `authz_deny`). Recrear el pod de la base lo arregló; ese día se recrearon todos los pods con malla anteriores al sync (las cuatro bases, MinIO y los de observabilidad). Tras sincronizar `linkerd-control-plane` de nuevo, recrea los pods con malla que ya existían: `kubectl delete pod -n <namespace> <pod>` (la espera a que vuelvan a `Running` no se midió).
2. **Credenciales del plugin de Calico.** `/etc/cni/net.d/calico-kubeconfig` dejó de refrescarse en dos nodos (el archivo de `vectra-worker` tenía 27 h) y los pods nuevos de ese nodo quedaban en `ContainerCreating` con `plugin type="calico" failed (add): error getting ClusterInformation: connection is unauthorized: Unauthorized`. Recrear el pod `calico-node` del nodo afectado lo arregló (`kubectl delete pod -n kube-system <calico-node-del-nodo>`). No se midió por qué dejaron de refrescarse.
3. **Doble sync de `keycloak`.** El primer `argocd app sync keycloak` terminó en `Failed` («the HPA controller was unable to get the target's current scale: statefulsets.apps "keycloak" not found») y no corrió el hook `keycloak-config-cli`; el segundo sync terminó bien e importó el realm. Ese sync también espera a `BackendTLSPolicy/keycloak`, que no está sano hasta sincronizar `gateway`. Procedimiento propuesto, **no medido**: sincroniza `gateway` antes de `keycloak` y repite `keycloak` si termina en `Failed`.
4. **`vectra.localtest.me` no llega al gateway.** `https://vectra.localtest.me` resuelve a 127.0.0.1:443, que `platform/kind/cluster.yaml` mapea al nodo de control, y ahí **no escucha nada**. El gateway responde en la IP del `LoadBalancer` que asigna `cloud-provider-kind` (172.18.0.7 ese día), alcanzable desde la máquina en Linux: `curl --resolve vectra.localtest.me:443:<ip> https://vectra.localtest.me/...`, con `<ip>` de `kubectl get svc -n vectra-edge` (la columna `EXTERNAL-IP` del Service del gateway; esa forma de leerla no se midió). Cómo debe llegar la máquina al gateway (el mapeo del 443, un `NodePort`, `/etc/hosts`) **no está decidido**.

La malla y lo que no trae identidad (U01-T14): con `default-inbound-policy: deny`, `platform/network/generate.py` autoriza ahora (a) el origen externo de F01, F07 y F08 hacia el 10443 del gateway (`Server` `api-gateway-10443`, `opaque`, con `NetworkAuthentication` y `AuthorizationPolicy` `api-gateway-10443-external` sobre `external_cidr` de `flows.yaml`; en kind es la red de Docker `172.18.0.0/16`, y `0.0.0.0/32` en staging y prod hasta que el banco entregue el rango), y (b) las sondas del kubelet por HTTPS de Keycloak al 9000 (`NetworkAuthentication` `keycloak-9000-probes-nodes` y `AuthorizationPolicy` `keycloak-9000-probes` sobre `keycloak-9000`, con `node_cidr` y `pod_cidr`). Los síntomas que tenían antes: `Connection denied server.kind=default server.name=deny` en el proxy del gateway, y `Connection denied server.name=keycloak-9000 tls=None(NoClientHello)` con `Startup probe failed: … EOF` en Keycloak. Si en el clúster quedan los recursos `tmp-*` con la etiqueta `vectra.io/temporal: "true"` que se aplicaron a mano mientras tanto, bórralos tras sincronizar `network` (no se midió el borrado).

### Tras reiniciar la máquina
Una máquina reiniciada pierde, además de la bóveda: (1) los `sysctl` que no estaban en `/etc/sysctl.d/` (ver «Antes de instalar»); (2) `cloud-provider-kind`, si se lanzó con `--rm` (antes de U01-T16) y no con `--restart=always` (paso 4); (3) la bóveda, porque su pod se recrea; y (4) la dirección del gateway: Docker reasigna las de la red `kind`. Medido el 2026-11-16, dos minutos después de reiniciar: los pods volvieron solos a `Running`; el balanceador del gateway (`kindccm-…`) pasó de `172.18.0.7` a `172.18.0.2` mientras el Service `api-gateway` de `vectra-edge` seguía anunciando `172.18.0.7`, con destinos viejos en el balanceador; `cloud-provider-kind` no estaba corriendo y `https://vectra.localtest.me` no conectaba. Orden:
1. **`sysctl`** y **contenedores** de kind y del registro: `sysctl fs.inotify.max_user_instances` (1024) y `docker ps` (los nodos, `kind-registry`, `cloud-provider-kind`). `kind-registry` y `cloud-provider-kind` llevan `--restart=always`: vuelven con Docker. El orden y este paso no salen de lo medido el 2026-11-14.
2. **`cloud-provider-kind`.** Si no aparece en `docker ps`, lánzalo como en el paso 4 de «Mitigación» (con nombre, `-d` y `--restart=always`). Mientras no corre, los `LoadBalancer` no se corrigen.
3. **La dirección del gateway.** `platform/kind/gateway-address.sh` (solo lectura: lee la dirección externa del Service del gateway, comprueba que responde en el 443 y la compara con lo que resuelve `vectra.localtest.me`). Si sale 0, sigue. Si sale 1 (responde, pero el nombre resuelve a otra dirección), imprime la línea que hace falta; es una **orden del operador** (el guion no escribe `/etc/hosts`): `sudo sed -i '/vectra\.localtest\.me/d' /etc/hosts && echo '<dirección> vectra.localtest.me' | sudo tee -a /etc/hosts`. Si sale 5, `kubectl` falló (el Service no existe o la API no contesta): no hay línea que proponer; arregla eso primero. Si sale 3 o 4 (el Service sin dirección, o no responde), `cloud-provider-kind` todavía no lo corrigió: espera unos segundos y repite. Si tras reiniciarlo (`docker restart cloud-provider-kind`) el Service sigue anunciando la dirección vieja, no se sabe sin un clúster cómo se corrige (candidata; no medido). La máquina llega al gateway por `/etc/hosts` con la dirección del `LoadBalancer`: no se recrea el clúster ni se cambia `kind/cluster.yaml`.
4. **Pods con malla y certificados de la malla.** Ver el paso 2 de «Vault reiniciado» y el párrafo de «Tras suspender la máquina» (abajo).
5. **La siembra, con recuperación.** `kubectl wait -n vault pod/vault-0 --for=condition=Ready` y los pasos 3 de «Vault reiniciado»: `platform/kind/seed-vault.sh` y `platform/kind/seed-vault.sh identity`. Con el informe en «nada que realinear», termina ahí; si generó algo, los pasos 4 a 8 de «Vault reiniciado» son para lo generado. No se midió cuánto tarda el clúster en volver a `Ready` tras un reinicio.

### Lo medido el 2026-11-19 tras reiniciar la máquina
Primera corrida completa de «Tras reiniciar la máquina» y de la siembra con recuperación en `kind-vectra` (orquestador; de las 01:49 a las 02:35 UTC del 2026-11-20, con la máquina en calma). Lo que no se midió lo dice.
1. **Los pods no volvieron solos.** Veinte minutos después del reinicio había 49 pods en `Unknown` y los tres de `linkerd` en `BackOff` por `linkerd-network-validator`, con `fs.inotify.max_user_instances` ya en 1024 y los contenedores de kind, `kind-registry` y `cloud-provider-kind` arriba. El 2026-11-16 habían vuelto solos en dos minutos: no cuentes con ello.
2. **Recrear los pods con malla funcionó, en este orden:** todos los de `linkerd` (`kubectl delete pod -n linkerd --all`; los tres Deployments listos en menos de un minuto), y después solo los pods en `Unknown` de cada namespace, no todos: `vectra-data` (las cuatro bases de CNPG en «Cluster in healthy state» y MinIO, en un minuto), `vectra-observability`, `vectra-identity`, `vectra-edge`, y un minuto más tarde `vectra-app`, `vectra-serving` y `vectra-mock`. A los tres minutos no quedaba ningún pod sin listo. La carga de la máquina llegó a 49 mientras arrancaban.
3. **La siembra.** `seed-vault.sh` cerró con «Todo se conservó o se recuperó: nada que realinear» (MinIO, PostgreSQL, Grafana y respaldos, todo recuperado): los pasos 4 a 7 de «Vault reiniciado» no hicieron falta y siguen sin medirse. `seed-vault.sh identity` recuperó el administrador de arranque, los 20 valores de los usuarios sintéticos y la llave de cada cliente con `ExternalSecret`, y generó lo que el runbook anuncia: las cuatro de `edge/valkey`, los pares de `channel`, `channel-simulator` y `verification-reader`, el `jwks` de `grafana` y `break-glass`. Los 71 `ExternalSecret` quedaron `SecretSynced` en menos de tres minutos.
4. **Paso 9 (Valkey y `envoy-ratelimit`), medido.** El Deployment se llama `envoy-ratelimit`. Con los `ExternalSecret` ya sincronizados: `kubectl rollout restart statefulset/valkey-a statefulset/valkey-b statefulset/sentinel-a statefulset/sentinel-b -n vectra-edge` y `kubectl rollout restart deployment/envoy-ratelimit -n envoy-gateway-system`, juntos. Los cinco rollouts terminaron en menos de un minuto, sin `WRONGPASS` en los logs de `envoy-ratelimit`, y 30 peticiones seguidas a `/auth/**` respondieron 200 sin ningún `RLSE`.
5. **Paso 8 (Keycloak), medido.** `argocd app sync keycloak` terminó bien **al primer intento** (con `gateway` sincronizado antes) y el Job `keycloak-config-cli` completó en 55 s, con los `jwks` nuevos. Después: `humo login` 5 de 5 y `humo flujo` entero (la solicitud por el canal con la llave nueva, la decisión y la consola, todo 200 o 204). Las contraseñas y los TOTP de los usuarios siguieron valiendo (recuperados, no generados).
6. **La dirección del gateway.** El Service `api-gateway` siguió en `172.18.0.7` y respondía; `/etc/hosts` tenía `172.18.0.2` de un reinicio anterior. `gateway-address.sh` imprimió la línea que faltaba; tras ponerla el operador, salió 0.
7. **La sesión de `argocd`.** El CLI respondió `token is expired`: se repite el `argocd login` del paso de instalación, con `ARGOCD_OPTS` exportada.
8. **Lo que falló solo por el reinicio y se arregló solo:** las ejecuciones de los CronJob que cayeron con el clúster abajo (`grafana-folder-check`, `registry-aggregator`, `bias-monitoring-job`) quedaron en `Error` y la siguiente pasó; `grafana-config` volvió a `Healthy` con ella.

**Applications `OutOfSync` (medido el mismo día).** Con `ServerSideApply=true` y la comparación por omisión de Argo CD, los campos que el servidor rellena solo (`action: replace` de un `PodMonitor`, `weight: 1` de un `HTTPRoute`, los de un `Cluster` de CNPG o una `ClusterPolicy`) dejaban `OutOfSync` a `gateway`, `identity-monitors`, `postgres`, `kyverno-policies`, `observability-monitors` y `kyverno`, aunque `argocd app diff` no mostrara nada. Desde el PR #214 cada Application lleva `argocd.argoproj.io/compare-options: ServerSideDiff=true` y esas seis quedaron `Synced`. Siguen `OutOfSync` y `Healthy` dos, que se aceptan con esta nota: `linkerd-control-plane` (el chart genera certificados distintos en cada render) y `kserve-crd` (ver `CANDIDATAS.md`).

**Espera de `product-metrics` en la wave 5:** su readiness exige una instantánea, y cada réplica hace una pasada completa antes de quedar lista. Con 10 veces el volumen esperado, el rollout puede tardar hasta unas 2,5 h, y Argo CD no pasa a la wave 6 hasta entonces. Es una espera y no una falla si `vectra_product_full_pass_in_progress = 1` y `vectra_product_entries_read_total` crece. Con U3 caído, la réplica queda lista enseguida.

**Tras suspender la máquina (medido el 2026-11-16):** si un pod nuevo se queda en `Init:1/2` y su `linkerd-proxy` registra `invalid peer certificate: certificate expired` al hablar con `linkerd-identity-headless` o `linkerd-dst-headless`, el plano de control de la malla tiene su propio certificado vencido (vive 24 h; tras ≈ 19 h de suspensión no se había renovado; la causa exacta no está confirmada). Comprueba la edad de los pods de `linkerd` (`kubectl --context kind-vectra get pods -n linkerd`) y reinícialos, la identidad primero: `kubectl --context kind-vectra rollout restart deployment/linkerd-identity -n linkerd`, espera al rollout, y después `kubectl --context kind-vectra rollout restart deployment/linkerd-destination deployment/linkerd-proxy-injector -n linkerd`. Los pods atascados arrancan solos en el siguiente reinicio de su proxy. Un pod de datos con el proxy de más de 24 h necesita lo mismo.

## Escalamiento
Si una wave no llega a `Healthy`, detén la instalación y abre un issue con la evidencia.

## Verificación
- `argocd app list -o json`: todas `Synced` y `Healthy`, ninguna con `automated`.
- `linkerd check`.
- `kubectl get clusters.postgresql.cnpg.io -A`: `registry-db` con 2 instancias y una réplica síncrona; las otras con 1.
- `kubectl top nodes` responde (metrics-server, solo kind; los HPA lo necesitan).
- `kubectl get externalsecrets.external-secrets.io -A`: todos `SecretSynced`.
- `curl -s localhost:5001/v2/_catalog`: las cuatro imágenes de U1 del paso 5 (`restore-drill`, `grafana-folder-permissions`, `minio`, `mc`), más las de las demás unidades que ya se hayan publicado.
