# Laboratorio 1 (Módulo 5) – El clúster es tuyo: construir, operar y rescatar Kubernetes con kubeadm

**Módulo 5 · sesión 6 · en clase · 95–110 minutos.** En el módulo 4 usaste un clúster que
te regaló `kind` en diez segundos. Hoy no. Hoy vas a instalar Kubernetes tú, componente por
componente, sobre dos máquinas Linux de verdad, y después vas a actualizarlo y a rescatarlo
de un desastre.

| Bloque | Pasos | Tiempo | ¿Se puede dejar para casa? |
|---|---|---|---|
| **Sustrato**: dos máquinas virtuales LXD | 0 | ~12 min | No |
| **Requisitos del host y runtime** | 1 | ~12 min | No |
| **Instalar kubeadm, kubelet y kubectl** | 2 | ~10 min | No |
| **`kubeadm init` y la red de Pods** | 3 | ~18 min | No: aquí está el fallo que hay que ver |
| **Unir el worker y desplegar** | 4 | ~10 min | No |
| **El control plane por dentro** | 5 | ~12 min | No |
| **Actualizar el clúster 1.36 → 1.37** | 6 | ~20 min | No: es el corazón de la sesión |
| **Respaldar y restaurar etcd** | 7 | ~15 min | No |
| **Limpieza** | – | ~3 min | No |
| **Anexo opcional** (certificados y tokens) | A1–A2 | ~20 min | **Sí: no se hace en clase** |

Los pasos 0 a 7 son el laboratorio de la sesión y cada uno depende del anterior.

> La idea central de esta sesión cabe en una frase: **un clúster de Kubernetes es un
> conjunto de procesos de Linux que tú instalas, configuras, actualizas y reparas.** No hay
> nube, no hay magia, no hay botón. Hay `systemd`, `apt`, certificados, una base de datos
> llamada etcd y unos manifiestos en un directorio.

---

## Objetivo

Al terminar, vas a poder responder estas preguntas señalando la evidencia en tu propia
terminal, no repitiendo una definición de memoria:

1. ¿Qué comprueba `kubeadm` **antes** de instalar nada, y por qué el swap y el
   `product_uuid` aparecen en esa lista?
2. ¿Por qué un nodo recién creado dice `NotReady`, y qué frase exacta te lo explica?
3. La documentación oficial pide **un solo** `sysctl`. Tu CNI falló igual. ¿Cómo
   descubriste qué le faltaba, sin buscar en un blog?
4. ¿Por qué `kubeadm upgrade` obliga a hacer `drain` antes de tocar el kubelet, y qué
   pasa con tus Pods mientras tanto?
5. Si borras un objeto del clúster y luego restauras un snapshot de etcd, ¿vuelve? ¿Y qué
   pasa con lo que creaste **después** del snapshot?
6. ¿Por qué `kubectl delete pod etcd-…` no mata a etcd?

**Requisito:** haber pasado por el módulo 1 (`systemd`, `systemctl`, `journalctl`, `apt`) y
por el módulo 4 (Pods, Deployments, Services, el loop de reconciliación). Este laboratorio
se apoya en los dos y lo dice explícitamente cuando lo hace.

**Entorno:** Linux con **LXD** instalado y funcionando (`lxd init` ya ejecutado alguna vez).
Vas a crear dos máquinas virtuales de 2 vCPU y 2,5 GiB cada una: cuenta con **6 GiB de RAM
libres** en tu portátil mientras dure el laboratorio. Al final se borra todo.

> **¿Por qué máquinas virtuales de LXD y no contenedores de LXD?**
> Porque `kubeadm` necesita cosas que un contenedor de sistema no puede darte: cargar
> módulos de kernel (`modprobe br_netfilter`, que harás en el Paso 3), escribir `sysctl` del
> kernel, y manejar cgroups como si fuera la máquina entera. Una VM de LXD tiene **su propio
> kernel**; un contenedor comparte el del host. Lo vas a comprobar con tus ojos en el Paso 1.
> `lxc` es el cliente de LXD y sirve para las dos cosas: la bandera `--vm` es la que decide.

---

## Paso 0: El sustrato, dos máquinas virtuales LXD (12 min)

### 0.1 Verificar LXD

```bash
lxc version
```

**Salida real de esta máquina** (la tuya puede ser otra versión; lo importante es que
responda):

```
Client version: 5.21.7 LTS
Server version: 5.21.7 LTS
```

### 0.2 Una red propia para el laboratorio

No vas a colgar las VMs de la red que ya uses para otras cosas. Creas un puente dedicado:

```bash
lxc network create k8sbr0 ipv4.address=10.55.0.1/24 ipv4.nat=true ipv6.address=none
```

**Salida real de esta máquina:**

```
Network k8sbr0 created
```

> **Si te sale este error, no es culpa tuya:**
>
> ```
> Error: Failed starting network: The DNS and DHCP service exited prematurely:
> exit status 2 ("dnsmasq: failed to create listening socket for 10.55.0.1: Address already in use")
> ```
>
> Significa que **otro proceso de tu máquina ya escucha en el puerto 53** (un MAAS, un
> `dnsmasq` propio, un Pi-hole). LXD arranca su propio `dnsmasq` para dar DHCP y DNS a las
> VMs, y no puede. La solución es apagar el DNS de ese `dnsmasq` y dejarle solo el DHCP,
> repartiendo un resolver público:
>
> ```bash
> lxc network delete k8sbr0
> lxc network create k8sbr0 ipv4.address=10.55.0.1/24 ipv4.nat=true ipv6.address=none \
>   dns.mode=none raw.dnsmasq='port=0'
> printf 'port=0\ndhcp-option=6,1.1.1.1,8.8.8.8\n' | lxc network set k8sbr0 raw.dnsmasq -
> ```
>
> `port=0` apaga el servidor DNS de `dnsmasq` sin tocar el DHCP, y `dhcp-option=6` es la
> opción DHCP estándar «servidores DNS». Esta es exactamente la corrección que hubo que
> aplicar en la máquina donde se verificó este laboratorio.

### 0.3 Un perfil con el tamaño que pide kubeadm

La documentación oficial de `kubeadm` exige **2 GiB de RAM o más por máquina** y **2 vCPU o
más en los nodos de plano de control**. En vez de repetir esos parámetros en cada `lxc
launch`, se declaran una vez en un perfil:

```bash
lxc profile create cka-lab
lxc profile device add cka-lab eth0 nic network=k8sbr0 name=eth0
lxc profile device add cka-lab root disk pool=default path=/ size=20GiB
lxc profile set cka-lab limits.cpu=2 limits.memory=2560MiB
lxc profile show cka-lab
```

**Salida real de esta máquina:**

```
Profile cka-lab created
Device eth0 added to cka-lab
Device root added to cka-lab
name: cka-lab
description: ""
config:
  limits.cpu: "2"
  limits.memory: 2560MiB
devices:
  eth0:
    name: eth0
    network: k8sbr0
    type: nic
  root:
    path: /
    pool: default
    size: 20GiB
    type: disk
used_by: []
project: default
```

### 0.4 Lanzar las dos máquinas

```bash
lxc launch ubuntu:24.04 cka-cp --vm --profile cka-lab
lxc launch ubuntu:24.04 cka-w1 --vm --profile cka-lab
```

La bandera **`--vm`** es la decisión importante del laboratorio: sin ella LXD te daría
contenedores de sistema y `kubeadm` chocaría contra el kernel compartido.

Ahora espera a que las dos pidan su dirección por DHCP. No es instantáneo: la VM arranca un
sistema operativo completo.

```bash
lxc list cka-
```

**Salida real de esta máquina** (tus direcciones serán otras: las reparte el DHCP):

```
+--------+---------+----------------------+------+-----------------+-----------+
|  NAME  |  STATE  |         IPV4         | IPV6 |      TYPE       | SNAPSHOTS |
+--------+---------+----------------------+------+-----------------+-----------+
| cka-cp | RUNNING | 10.55.0.98 (enp5s0)  |      | VIRTUAL-MACHINE | 0         |
+--------+---------+----------------------+------+-----------------+-----------+
| cka-w1 | RUNNING | 10.55.0.190 (enp5s0) |      | VIRTUAL-MACHINE | 0         |
+--------+---------+----------------------+------+-----------------+-----------+
```

> **Anota tus dos direcciones IP ahora.** En este documento aparecen `10.55.0.98`
> (control plane) y `10.55.0.190` (worker). **Cada vez que las veas, sustitúyelas por las
> tuyas.**

Si la columna IPV4 sale vacía, espera y repite: la VM todavía está arrancando.

### 0.5 Cómo se entra a cada máquina

```bash
lxc exec cka-cp -- bash
```

Eso te deja una shell de `root` **dentro** de `cka-cp`. Para salir, `exit`.

> **Convención de este laboratorio.** Cada bloque de comandos dice en qué máquina se
> ejecuta con un comentario en la primera línea:
> `# EN TU PORTÁTIL`, `# DENTRO DE cka-cp`, `# DENTRO DE cka-w1`, o
> `# EN LAS DOS: cka-cp y cka-w1`. Léelo antes de pegar.

---

## Paso 1: Los requisitos que kubeadm comprueba, y el runtime (12 min)

### 1.1 La lista de la documentación oficial, verificada a mano

La página oficial *Installing kubeadm* pide: host Linux compatible, **2 GiB o más de RAM**,
**2 vCPU o más** en el control plane, **hostname, dirección MAC y `product_uuid` únicos por
nodo**, conectividad total entre máquinas, y **swap desactivado**. Compruébalo tú:

```bash
# EN LAS DOS: cka-cp y cka-w1
hostnamectl --static
uname -r
cat /sys/class/dmi/id/product_uuid
ip -o link show enp5s0 | awk '{print $17}'
free -h | head -3
swapon --show || echo "(no hay swap)"
nproc
```

**Salida real de esta máquina, en `cka-cp`:**

```
cka-cp
6.8.0-138-generic
d4ee0033-48d4-44a5-ab37-c168df62165c
00:16:3e:0f:11:ed
               total        used        free      shared  buff/cache   available
Mem:           2.4Gi       329Mi       2.0Gi        19Mi       252Mi       2.1Gi
Swap:             0B          0B          0B
2
```

**Salida real de esta máquina, en `cka-w1`:**

```
cka-w1
6.8.0-138-generic
769c272b-ccfd-4877-8ab7-69218f01ee54
00:16:3e:90:20:1b
               total        used        free      shared  buff/cache   available
Mem:           2.4Gi       352Mi       2.0Gi        19Mi       252Mi       2.0Gi
Swap:             0B          0B          0B
2
```

Léelo línea por línea, porque cada una es un requisito de la lista:

- **`product_uuid` distinto** en las dos (`d4ee0033…` y `769c272b…`) y **MAC distinta**
  (`…0f:11:ed` y `…90:20:1b`). Kubernetes usa esos valores para distinguir nodos. Si
  clonas una VM sin regenerarlos, el segundo nodo puede no registrarse nunca.
- **`Swap: 0B`.** La imagen de Ubuntu Cloud no trae swap, así que este requisito ya se
  cumple. Si tu máquina sí tuviera swap, `swapoff -a` y quitar la línea de `/etc/fstab`.
- **`nproc` = 2** y **2,4 GiB de RAM**: justo el mínimo del control plane.

### 1.2 El kernel propio: la diferencia con `kind`

Este es el contraste directo con el módulo 4. Allí, el «nodo» era un contenedor Docker que
compartía el kernel de tu portátil. Aquí no:

```bash
# EN TU PORTÁTIL
uname -r
lxc exec cka-cp -- uname -r
```

**Salida real de esta máquina:**

```
6.17.0-1032-oem
6.8.0-138-generic
```

**Kernels distintos.** En el módulo 4 estos dos números eran idénticos. Esa diferencia es
toda la diferencia: en el Paso 3 vas a cargar un módulo de kernel dentro de `cka-cp`, y solo
se puede hacer porque ese kernel es suyo.

### 1.3 Activar el reenvío de paquetes IPv4

La documentación oficial de *Container Runtimes* pide exactamente un `sysctl`:

```bash
# EN LAS DOS: cka-cp y cka-w1
cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.ipv4.ip_forward = 1
EOF
sysctl --system > /dev/null
sysctl net.ipv4.ip_forward
```

**Salida real de esta máquina (en las dos):**

```
net.ipv4.ip_forward = 1
```

> **Guarda este momento.** La documentación oficial de hoy pide **solo** esto. Blogs de
> hace tres años piden además `br_netfilter` y dos `sysctl` de puente. En el Paso 3 vas a
> descubrir, con evidencia y no con fe, quién tenía razón y por qué.

### 1.4 Instalar y configurar containerd

Kubernetes no habla con Docker: habla **CRI** con un runtime. Ubuntu 24.04 trae containerd
en sus repositorios:

```bash
# EN LAS DOS: cka-cp y cka-w1
apt-get update
apt-get install -y containerd
containerd --version
```

**Salida real de esta máquina:**

```
containerd github.com/containerd/containerd/v2 2.2.1
```

El paquete de la distribución trae una configuración mínima. La documentación oficial dice
que, si viene de un paquete, hay que regenerarla y activar el *cgroup driver* `systemd`:

```bash
# EN LAS DOS: cka-cp y cka-w1
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
grep -n 'SystemdCgroup' /etc/containerd/config.toml
systemctl restart containerd
systemctl is-active containerd
```

**Salida real de esta máquina:**

```
109:            SystemdCgroup = true
active
```

> **Por qué `SystemdCgroup = true` no es cosmético.** En Linux, los cgroups limitan
> recursos. El kubelet y el runtime tienen que usar **el mismo** gestor de cgroups. Como
> Ubuntu arranca con `systemd` y con cgroup v2, la documentación oficial obliga a que los
> dos usen el driver `systemd`. Si dejas `cgroupfs` en uno de los dos, tienes **dos
> gestores con dos vistas distintas de la memoria disponible**, y el nodo se vuelve
> inestable bajo presión. Es el fallo silencioso más caro de esta lista: no rompe la
> instalación, rompe la producción tres semanas después.

---

## Paso 2: Instalar kubeadm, kubelet y kubectl (10 min)

Vas a instalar **1.36 a propósito**, aunque exista 1.37, porque en el Paso 6 vas a hacer una
actualización de versión menor de verdad.

### 2.1 El repositorio y su llave

```bash
# EN LAS DOS: cka-cp y cka-w1
apt-get update
apt-get install -y apt-transport-https ca-certificates curl gpg
mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.36/deb/Release.key \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.36/deb/ /' \
  > /etc/apt/sources.list.d/kubernetes.list
```

> **Hay un repositorio por versión menor.** Fíjate en el `v1.36` que aparece **dos veces**:
> en la llave y en la línea del repositorio. `pkgs.k8s.io` no es un repositorio con todas
> las versiones dentro: es uno por cada versión menor. Cambiar de 1.36 a 1.37 significa
> cambiar esa cadena, y eso es literalmente el primer paso del Paso 6.

### 2.2 Instalar y **fijar**

```bash
# EN LAS DOS: cka-cp y cka-w1
apt-get update
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl
systemctl enable --now kubelet
```

**Salida real de esta máquina:**

```
kubelet set on hold.
kubeadm set on hold.
kubectl set on hold.
```

> **`apt-mark hold` es el paso que la gente se salta y luego lamenta.** Sin él, un
> `apt-get upgrade` de rutina del sistema operativo puede subirte el `kubelet` sin avisar y
> romper la política de *version skew* de Kubernetes (el kubelet no puede ser más nuevo que
> el API server). Con `hold`, esa actualización accidental se convierte en un error
> explícito de `apt` en vez de en un clúster roto.

### 2.3 Confirmar que las tres versiones coinciden

```bash
# EN LAS DOS: cka-cp y cka-w1
kubeadm version -o short
kubectl version --client=true -o yaml | grep gitVersion | head -1
kubelet --version
```

**Salida real de esta máquina:**

```
v1.36.4
  gitVersion: v1.36.4
Kubernetes v1.36.4
```

Las tres en `v1.36.4`. Eso es lo que quieres antes de `kubeadm init`.

---

## Paso 3: `kubeadm init`, y el fallo que tienes que ver (18 min)

### 3.1 Descargar las imágenes antes de empezar

```bash
# DENTRO DE cka-cp
kubeadm config images pull
```

**Salida real de esta máquina:**

```
I0831 14:25:16.075139    2593 version.go:260] remote version is much newer: v1.37.0; falling back to: stable-1.36
[config/images] Pulled registry.k8s.io/kube-apiserver:v1.36.4
[config/images] Pulled registry.k8s.io/kube-controller-manager:v1.36.4
[config/images] Pulled registry.k8s.io/kube-scheduler:v1.36.4
[config/images] Pulled registry.k8s.io/kube-proxy:v1.36.4
[config/images] Pulled registry.k8s.io/coredns/coredns:v1.14.2
[config/images] Pulled registry.k8s.io/pause:3.10.2
[config/images] Pulled registry.k8s.io/etcd:3.6.8-0
```

Ahí está el control plane completo, en siete imágenes. Reconócelas del módulo 4: son
exactamente las cajas del diagrama de arquitectura. La primera línea, además, te avisa de
que existe 1.37 y de que tu `kubeadm` 1.36 se queda en la serie 1.36: es correcto y
deliberado.

### 3.2 Inicializar el control plane

```bash
# DENTRO DE cka-cp — sustituye la IP por la de TU cka-cp
kubeadm init --pod-network-cidr=10.244.0.0/16 --apiserver-advertise-address=10.55.0.98
```

Dos banderas, dos decisiones:

- **`--pod-network-cidr=10.244.0.0/16`**: el rango de direcciones que se repartirá a los
  Pods. Tiene que coincidir con lo que espere tu plugin CNI. `10.244.0.0/16` es el valor por
  defecto de Flannel, que es el que instalarás en 3.4.
- **`--apiserver-advertise-address`**: en qué dirección anuncia el API server. Con una sola
  interfaz podrías omitirla; se pone explícita para que el certificado y el comando de
  unión salgan con la IP correcta.

**Salida real de esta máquina** (recortada a la parte final, que es la que importa):

```
[control-plane-check] kube-controller-manager is healthy after 4.602587ms
[control-plane-check] kube-scheduler is healthy after 7.831133ms
[control-plane-check] kube-apiserver is healthy after 2.00342381s
[mark-control-plane] Marking the node cka-cp as control-plane by adding the labels: [node-role.kubernetes.io/control-plane node.kubernetes.io/exclude-from-external-load-balancers]
[mark-control-plane] Marking the node cka-cp as control-plane by adding the taints [node-role.kubernetes.io/control-plane:NoSchedule]
[bootstrap-token] Using token: tzayt2.2hmyypmuq1z1yinp
[addons] Applied essential addon: CoreDNS
[addons] Applied essential addon: kube-proxy

Your Kubernetes control-plane has initialized successfully!

To start using your cluster, you need to run the following as a regular user:

  mkdir -p $HOME/.kube
  sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
  sudo chown $(id -u):$(id -g) $HOME/.kube/config

Alternatively, if you are the root user, you can run:

  export KUBECONFIG=/etc/kubernetes/admin.conf

You should now deploy a pod network to the cluster.
Run "kubectl apply -f [podnetwork].yaml" with one of the options listed at:
  https://kubernetes.io/docs/concepts/cluster-administration/addons/

Then you can join any number of worker nodes by running the following on each as root:

kubeadm join 10.55.0.98:6443 --token tzayt2.2hmyypmuq1z1yinp \
	--discovery-token-ca-cert-hash sha256:fc257ada7f08568f5adc1f81f90a8ec136f9e3fbe9f0434b8a27153e8571d10d
```

> **Copia y guarda ahora mismo tu línea `kubeadm join`.** La necesitas en el Paso 4. (Y si
> la pierdes, no pasa nada: en 4.1 se genera otra.)

Dos frases de esa salida merecen que las subrayes:

- **`Marking the node cka-cp as control-plane by adding the taints [node-role.kubernetes.io/control-plane:NoSchedule]`.**
  Acaba de decirte que **el control plane no aceptará cargas de trabajo normales**. En el
  Paso 4.3 lo vas a comprobar sin que nadie te lo cuente.
- **`You should now deploy a pod network to the cluster`.** Kubernetes **no trae red de
  Pods**. Es una pieza que tú eliges e instalas. Es lo siguiente.

### 3.3 Habla con tu clúster

```bash
# DENTRO DE cka-cp
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl get nodes
```

**Salida real de esta máquina:**

```
NAME     STATUS     ROLES           AGE   VERSION
cka-cp   NotReady   control-plane   10s   v1.36.4
```

`NotReady`. No es un error: es un diagnóstico, y el clúster te lo explica si preguntas
bien:

```bash
# DENTRO DE cka-cp
kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].message}'
```

**Salida real de esta máquina:**

```
container runtime network not ready: NetworkReady=false reason:NetworkPluginNotReady message:Network plugin returns error: cni plugin not initialized
```

Ahí está, con todas las letras: **falta el plugin CNI**. Mira qué consecuencia tiene:

```bash
# DENTRO DE cka-cp
kubectl get pods -n kube-system -o wide
```

**Salida real de esta máquina:**

```
NAME                             READY   STATUS              RESTARTS   AGE   IP           NODE     NOMINATED NODE   READINESS GATES
coredns-589f44dc88-vllcd         0/1     Pending             0          0s    <none>       <none>   <none>           <none>
coredns-589f44dc88-zg9hl         0/1     Pending             0          0s    <none>       <none>   <none>           <none>
etcd-cka-cp                      0/1     Running             0          7s    10.55.0.98   cka-cp   <none>           <none>
kube-apiserver-cka-cp            0/1     Running             0          7s    10.55.0.98   cka-cp   <none>           <none>
kube-controller-manager-cka-cp   0/1     Running             0          7s    10.55.0.98   cka-cp   <none>           <none>
kube-proxy-bkw6n                 0/1     ContainerCreating   0          0s    10.55.0.98   cka-cp   <none>           <none>
kube-scheduler-cka-cp            0/1     Running             0          7s    10.55.0.98   cka-cp   <none>           <none>
```

Fíjate en la columna `IP`: etcd, el API server, el controller manager y el scheduler tienen
la IP **del nodo** (`10.55.0.98`), no una IP de Pod. Corren en la red del host. CoreDNS, en
cambio, está `Pending` **sin nodo asignado**, porque necesita una IP de Pod y todavía no
hay quién se la dé.

### 3.4 Instalar la red de Pods (Flannel)

```bash
# DENTRO DE cka-cp
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

**Salida real de esta máquina:**

```
namespace/kube-flannel created
serviceaccount/flannel created
clusterrole.rbac.authorization.k8s.io/flannel created
clusterrolebinding.rbac.authorization.k8s.io/flannel created
configmap/kube-flannel-cfg created
daemonset.apps/kube-flannel-ds created
```

Es un `DaemonSet`: un Pod de Flannel por nodo, hoy y para siempre, también en los nodos que
añadas mañana. Espera al nodo:

```bash
# DENTRO DE cka-cp
kubectl wait --for=condition=Ready node/cka-cp --timeout=180s
kubectl get nodes -o wide
```

**Salida real de esta máquina:**

```
node/cka-cp condition met
NAME     STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
cka-cp   Ready    control-plane   33s   v1.36.4   10.55.0.98    <none>        Ubuntu 24.04.4 LTS   6.8.0-138-generic (amd64)   containerd://2.2.1
```

`Ready`. Perfecto… y engañoso. Mira los Pods de Flannel:

```bash
# DENTRO DE cka-cp
kubectl get pods -n kube-flannel -o wide
```

**Salida real de esta máquina:**

```
NAME                    READY   STATUS   RESTARTS        AGE     IP            NODE     NOMINATED NODE   READINESS GATES
kube-flannel-ds-xmt9n   0/1     Error    5 (115s ago)    3m37s   10.55.0.98    cka-cp   <none>           <none>
```

### 3.5 El fallo real, y cómo se diagnostica sin buscar en Google

`Error`, con 5 reinicios. El clúster no te va a adivinar el problema, pero sí te lo va a
escribir. **Pide los logs, siempre antes que una búsqueda web:**

```bash
# DENTRO DE cka-cp
kubectl logs -n kube-flannel -l app=flannel --tail=6
```

**Salida real de esta máquina** (la última línea es la que resuelve todo):

```
I0831 14:29:25.524743       1 main.go:255] Created subnet manager: Kubernetes Subnet Manager - cka-cp
I0831 14:29:25.525197       1 main.go:540] Found network config - Backend type: vxlan
E0831 14:29:25.525253       1 main.go:292] Failed to check br_netfilter: stat /proc/sys/net/bridge/bridge-nf-call-iptables: no such file or directory
```

Léelo despacio, porque es la lección del paso:

> La documentación oficial de Kubernetes pide **un** `sysctl` (`net.ipv4.ip_forward`) y ya
> no menciona `br_netfilter`. **Y aun así tu clúster falla.** No porque la documentación
> mienta, sino porque dice literalmente: *«algunos plugins pueden esperar otros parámetros
> sysctl, módulos de kernel, etc.; consulta la documentación de tu implementación de red»*.
> Flannel es uno de esos. La diferencia entre saberlo y no saberlo no fue leer un blog: fue
> **leer el log del contenedor que falla**. Ese es el método del CKA entero.

La corrección: cargar los módulos y añadir los dos `sysctl` de puente.

```bash
# EN LAS DOS: cka-cp y cka-w1
cat <<EOF | tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system > /dev/null

lsmod | grep -E '^(overlay|br_netfilter)'
sysctl net.bridge.bridge-nf-call-iptables net.ipv4.ip_forward
```

**Salida real de esta máquina:**

```
br_netfilter           32768  0
overlay               212992  11
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
```

> **Este es el momento que justifica la VM.** `modprobe br_netfilter` carga un módulo en
> **el kernel de `cka-cp`**. En un contenedor de sistema no habría kernel propio que
> modificar y el comando fallaría o, peor, tocaría el kernel de tu portátil. `/etc/modules-load.d/`
> hace que se cargue solo en cada arranque; `modprobe` lo carga ahora, sin reiniciar.

Ahora sí:

```bash
# DENTRO DE cka-cp
kubectl -n kube-flannel rollout status ds/kube-flannel-ds --timeout=180s
kubectl get pods -n kube-flannel -o wide
```

**Salida real de esta máquina:**

```
daemon set "kube-flannel-ds" successfully rolled out
NAME                    READY   STATUS    RESTARTS        AGE     IP            NODE     NOMINATED NODE   READINESS GATES
kube-flannel-ds-xmt9n   1/1     Running   6 (3m14s ago)   6m25s   10.55.0.98    cka-cp   <none>           <none>
```

`1/1 Running`. Los 6 reinicios que quedan en la columna `RESTARTS` son la cicatriz de lo
que acabas de arreglar: la historia del Pod, no su estado.

---

## Paso 4: Unir el worker y desplegar la primera carga (10 min)

### 4.1 Generar el comando de unión

El token que imprimió `kubeadm init` caduca a las 24 horas. En vez de buscarlo en el
historial, se pide uno nuevo:

```bash
# DENTRO DE cka-cp
kubeadm token create --print-join-command
```

**Salida real de esta máquina:**

```
kubeadm join 10.55.0.98:6443 --token oh6x18.607ff1vqzrzzpdaj --discovery-token-ca-cert-hash sha256:fc257ada7f08568f5adc1f81f90a8ec136f9e3fbe9f0434b8a27153e8571d10d
```

Ese comando lleva dos secretos con papeles distintos: el **token** autentica al nodo nuevo
frente al clúster, y el **hash del certificado de la CA** permite al nodo nuevo verificar
que el API server con el que habla es el de verdad. Autenticación mutua, en una línea.

### 4.2 Unir el worker

```bash
# DENTRO DE cka-w1 — pega TU comando, no el de este documento
kubeadm join 10.55.0.98:6443 --token oh6x18.607ff1vqzrzzpdaj \
  --discovery-token-ca-cert-hash sha256:fc257ada7f08568f5adc1f81f90a8ec136f9e3fbe9f0434b8a27153e8571d10d
```

**Salida real de esta máquina** (recortada al final):

```
[preflight] Running pre-flight checks
[preflight] Reading configuration from the "kubeadm-config" ConfigMap in namespace "kube-system"...
[kubelet-start] Starting the kubelet
[kubelet-check] Waiting for a healthy kubelet at http://127.0.0.1:10248/healthz. This can take up to 4m0s
[kubelet-check] The kubelet is healthy after 501.275074ms
[kubelet-start] Waiting for the kubelet to perform the TLS Bootstrap

This node has joined the cluster:
* Certificate signing request was sent to apiserver and a response was received.
* The Kubelet was informed of the new secure connection details.
```

`Certificate signing request was sent to apiserver`: el nodo nuevo **pidió su propio
certificado** y el clúster se lo firmó. En el Laboratorio 2 vas a hacer ese mismo trámite a
mano, pero para una persona en vez de para un nodo.

```bash
# DENTRO DE cka-cp
kubectl wait --for=condition=Ready node/cka-w1 --timeout=240s
kubectl get nodes -o wide
```

**Salida real de esta máquina:**

```
node/cka-w1 condition met
NAME     STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
cka-cp   Ready    control-plane   55s   v1.36.4   10.55.0.98    <none>        Ubuntu 24.04.4 LTS   6.8.0-138-generic (amd64)   containerd://2.2.1
cka-w1   Ready    <none>          16s   v1.36.4   10.55.0.190   <none>        Ubuntu 24.04.4 LTS   6.8.0-138-generic (amd64)   containerd://2.2.1
```

Dos nodos. `ROLES` en `<none>` para el worker es lo normal: «worker» no es un rol que
Kubernetes conozca, es simplemente un nodo sin la etiqueta de control plane.

### 4.3 Desplegar, exponer y comprobar

```bash
# DENTRO DE cka-cp
kubectl create deployment web --image=nginx:1.29-alpine --replicas=3
kubectl rollout status deployment/web --timeout=180s
kubectl get pods -o wide
```

**Salida real de esta máquina:**

```
deployment.apps/web created
deployment "web" successfully rolled out
NAME                   READY   STATUS    RESTARTS   AGE     IP           NODE     NOMINATED NODE   READINESS GATES
web-7fbc579fd4-dch5h   1/1     Running   0          6m10s   10.244.1.3   cka-w1   <none>           <none>
web-7fbc579fd4-kjp7r   1/1     Running   0          6m10s   10.244.1.2   cka-w1   <none>           <none>
web-7fbc579fd4-nxlxr   1/1     Running   0          6m10s   10.244.1.4   cka-w1   <none>           <none>
```

**Las tres réplicas están en `cka-w1`. Ninguna en el control plane.** No es casualidad ni
balanceo: es el *taint* que `kubeadm init` te anunció en el Paso 3.2.

```bash
# DENTRO DE cka-cp
kubectl describe node cka-cp | grep -i taint
```

**Salida real de esta máquina:**

```
Taints:             node-role.kubernetes.io/control-plane:NoSchedule
```

Y las IPs (`10.244.1.2`, `.3`, `.4`) salen del rango que pediste con `--pod-network-cidr`.
Todo encaja. Ahora expón el Deployment y compruébalo de verdad:

```bash
# DENTRO DE cka-cp
kubectl expose deployment web --port=80
kubectl get svc web
kubectl get endpointslices -l kubernetes.io/service-name=web
```

**Salida real de esta máquina:**

```
service/web exposed
NAME   TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
web    ClusterIP   10.97.17.8   <none>        80/TCP    3m19s
NAME        ADDRESSTYPE   PORTS   ENDPOINTS                          AGE
web-2cmcf   IPv4          80      10.244.1.2,10.244.1.3,10.244.1.4   3m19s
```

El `EndpointSlice` del módulo 4, otra vez, con las tres IPs. Y la prueba definitiva:

```bash
# DENTRO DE cka-cp
kubectl run curl --image=curlimages/curl:8.19.0 --restart=Never --rm -i --quiet -- \
  curl -sS -o /dev/null -w 'HTTP %{http_code} desde web:80\n' http://web
```

**Salida real de esta máquina:**

```
HTTP 200 desde web:80
```

**Tienes un clúster de Kubernetes que instalaste tú, sirviendo tráfico.**

---

## Paso 5: El control plane por dentro (12 min)

### 5.1 Los static pods son archivos

```bash
# DENTRO DE cka-cp
ls -l /etc/kubernetes/manifests/
grep -i staticPodPath /var/lib/kubelet/config.yaml
```

**Salida real de esta máquina:**

```
total 16
-rw------- 1 root root 2580 Aug 31 14:25 etcd.yaml
-rw------- 1 root root 3944 Aug 31 14:25 kube-apiserver.yaml
-rw------- 1 root root 3229 Aug 31 14:25 kube-controller-manager.yaml
-rw------- 1 root root 1726 Aug 31 14:25 kube-scheduler.yaml
staticPodPath: /etc/kubernetes/manifests
```

Ahí está resuelto el problema del huevo y la gallina que planteaba el módulo 4: **¿cómo se
crea el API server, si para crear un Pod hace falta el API server?** No se crea por la API.
El kubelet vigila ese directorio y arranca lo que encuentre, sin preguntarle a nadie.

### 5.2 La prueba: borra etcd por la API

```bash
# DENTRO DE cka-cp
kubectl delete pod etcd-cka-cp -n kube-system
kubectl get pod etcd-cka-cp -n kube-system
```

**Salida real de esta máquina:**

```
pod "etcd-cka-cp" deleted from kube-system namespace
NAME          READY   STATUS    RESTARTS   AGE
etcd-cka-cp   1/1     Running   0          8s
```

Lo borraste y **sigue ahí**, con `AGE` de 8 segundos. Porque lo que borraste no era etcd:
era el *mirror pod*, el reflejo que el kubelet publica en la API para que puedas verlo. El
original es `/etc/kubernetes/manifests/etcd.yaml`. **Para parar de verdad un static pod hay
que mover su archivo**, y eso es exactamente lo que harás en el Paso 7.

### 5.3 El kubelet es un servicio de systemd (módulo 1)

Rompe el worker a propósito:

```bash
# DENTRO DE cka-w1
systemctl stop kubelet
```

Espera unos 50 segundos y mira desde el control plane:

```bash
# DENTRO DE cka-cp
kubectl get nodes
kubectl get node cka-w1 -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}{"  "}{.status.conditions[?(@.type=="Ready")].message}'
```

**Salida real de esta máquina:**

```
NAME     STATUS     ROLES           AGE     VERSION
cka-cp   Ready      control-plane   8m51s   v1.36.4
cka-w1   NotReady   <none>          8m12s   v1.36.4

NodeStatusUnknown  Kubelet stopped posting node status.
```

«**Kubelet stopped posting node status**». El API server no sabe si el nodo se incendió o
si le pararon un servicio: solo sabe que dejó de reportar. Ve a la máquina y pregunta con
las herramientas del módulo 1:

```bash
# DENTRO DE cka-w1
systemctl is-active kubelet
journalctl -u kubelet --no-pager -n 5 -o short
```

**Salida real de esta máquina:**

```
inactive
Aug 31 14:33:45 cka-w1 kubelet[2414]: I0831 14:33:45.306403    2414 tlsconfig.go:258] "Shutting down DynamicServingCertificateController"
Aug 31 14:33:45 cka-w1 systemd[1]: Stopping kubelet.service - kubelet: The Kubernetes Node Agent...
Aug 31 14:33:45 cka-w1 systemd[1]: kubelet.service: Deactivated successfully.
Aug 31 14:33:45 cka-w1 systemd[1]: Stopped kubelet.service - kubelet: The Kubernetes Node Agent.
Aug 31 14:33:45 cka-w1 systemd[1]: kubelet.service: Consumed 6.625s CPU time.
```

Diagnóstico cerrado: nadie lo mató, se paró limpiamente. Arréglalo:

```bash
# DENTRO DE cka-w1
systemctl start kubelet
```

```bash
# DENTRO DE cka-cp
kubectl get nodes
```

**Salida real de esta máquina:**

```
NAME     STATUS   ROLES           AGE     VERSION
cka-cp   Ready    control-plane   9m14s   v1.36.4
cka-w1   Ready    <none>          8m35s   v1.36.4
```

> **La secuencia que acabas de hacer es el 30 % del examen CKA**: `kubectl get nodes` →
> `kubectl describe`/`jsonpath` para la razón → entrar al nodo → `systemctl` y
> `journalctl -u kubelet`. Memoriza el orden, no los comandos.

### 5.4 Ver los contenedores por debajo de Kubernetes

```bash
# DENTRO DE cka-w1
apt-get install -y cri-tools
echo "runtime-endpoint: unix:///run/containerd/containerd.sock" > /etc/crictl.yaml
crictl --version
crictl ps
```

**Salida real de esta máquina** (recortada):

```
crictl version v1.36.0
CONTAINER           IMAGE               CREATED             STATE      NAME             POD                     NAMESPACE
23fa304328623       812d47f806db4       2 minutes ago       Running    nginx            web-7fbc579fd4-nxlxr    default
46b56d0cfc682       812d47f806db4       2 minutes ago       Running    nginx            web-7fbc579fd4-dch5h    default
8adab7e40d31e       812d47f806db4       2 minutes ago       Running    nginx            web-7fbc579fd4-kjp7r    default
2787b60185029       1644118ebe089       2 minutes ago       Running    kube-flannel     kube-flannel-ds-7kc6t   kube-flannel
01013835c828a       a5280d36e1aa3       8 minutes ago       Running    kube-proxy       kube-proxy-qnnqm        kube-system
```

`crictl` habla CRI directamente con containerd, sin pasar por el API server. Es la
herramienta que te queda **cuando el API server está caído** y necesitas saber qué corre en
un nodo. Nota que `cri-tools` no venía instalado: en el CKA, instalarlo puede ser el primer
paso de un problema de diagnóstico.

---

## Paso 6: Actualizar el clúster de 1.36 a 1.37 (20 min)

Regla que no se negocia: **una versión menor a la vez**, y **el control plane primero**.

### 6.1 Cambiar de repositorio

```bash
# DENTRO DE cka-cp
sed -i 's|/v1.36/|/v1.37/|' /etc/apt/sources.list.d/kubernetes.list
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.37/deb/Release.key \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg --yes
apt-get update
apt-cache madison kubeadm | head -4
```

**Salida real de esta máquina:**

```
   kubeadm | 1.37.0-1.1 | https://pkgs.k8s.io/core:/stable:/v1.37/deb  Packages
```

Una sola versión disponible: `1.37.0-1.1`. Ese es el `x` de `1.37.x-*` que pide la
documentación.

### 6.2 Actualizar solo el binario de kubeadm

```bash
# DENTRO DE cka-cp
apt-mark unhold kubeadm
apt-get update && apt-get install -y kubeadm='1.37.0-*'
apt-mark hold kubeadm
kubeadm version -o short
```

**Salida real de esta máquina:**

```
kubeadm set on hold.
v1.37.0
```

`kubeadm` en 1.37.0; `kubelet` y `kubectl` siguen en 1.36.4. **Es correcto y es a
propósito**: `kubeadm` es la herramienta que dirige la actualización, no una de las piezas
que se actualiza al mismo tiempo.

### 6.3 Planificar antes de aplicar

```bash
# DENTRO DE cka-cp
kubeadm upgrade plan
```

**Salida real de esta máquina** (recortada):

```
[upgrade/versions] Cluster version: 1.36.4
[upgrade/versions] kubeadm version: v1.37.0
[upgrade/versions] Target version: v1.37.0

Components that must be upgraded manually after you have upgraded the control plane with 'kubeadm upgrade apply':
COMPONENT   NODE      CURRENT   TARGET
kubelet     cka-cp    v1.36.4   v1.37.0
kubelet     cka-w1    v1.36.4   v1.37.0

Upgrade to the latest stable version:

COMPONENT                 NODE      CURRENT   TARGET
kube-apiserver            cka-cp    v1.36.4   v1.37.0
kube-controller-manager   cka-cp    v1.36.4   v1.37.0
kube-scheduler            cka-cp    v1.36.4   v1.37.0
kube-proxy                          1.36.4    v1.37.0
CoreDNS                             v1.14.2   v1.14.6
etcd                      cka-cp    3.6.8-0   3.7.0-0

You can now apply the upgrade by executing the following command:

	kubeadm upgrade apply v1.37.0
```

Este comando es un regalo: te dice **qué actualiza él** (la tabla de abajo: API server,
scheduler, controller manager, kube-proxy, CoreDNS y **etcd**) y **qué tienes que actualizar
tú a mano** (la tabla de arriba: los kubelets, nodo por nodo). Fíjate en que etcd salta de
`3.6.8-0` a `3.7.0-0`: tu base de datos también se actualiza.

### 6.4 Aplicar

```bash
# DENTRO DE cka-cp
kubeadm upgrade apply v1.37.0
```

**Salida real de esta máquina** (recortada al final):

```
[upgrade/staticpods] Moving new manifest to "/etc/kubernetes/manifests/kube-scheduler.yaml" and backing up old manifest to "/etc/kubernetes/tmp/kubeadm-backup-manifests-2026-08-31-14-36-45/kube-scheduler.yaml"
[upgrade/staticpods] Waiting for the kubelet to restart the component
[upgrade/staticpods] Component "kube-scheduler" upgraded successfully!
[upgrade/control-plane] The control plane instance for this node was successfully upgraded!
[upgrade/kubelet-config] The kubelet configuration for this node was successfully upgraded!
[addons] Applied essential addon: CoreDNS
[addons] Applied essential addon: kube-proxy

[upgrade] SUCCESS! A control plane node of your cluster was upgraded to "v1.37.0".

[upgrade] Now please proceed with upgrading the rest of the nodes by following the right order.
```

Mira **cómo** lo hace: *«Moving new manifest to `/etc/kubernetes/manifests/…` and backing up
old manifest to `/etc/kubernetes/tmp/kubeadm-backup-manifests-…`»*. `kubeadm` no reinicia
contenedores: **cambia el archivo del static pod y deja que el kubelet haga el resto**, y
guarda el original por si hay que volver. Es el mismo mecanismo del Paso 5.1, usado para
actualizar.

### 6.5 Vaciar el nodo antes de tocar el kubelet

```bash
# DENTRO DE cka-cp
kubectl drain cka-cp --ignore-daemonsets
kubectl get nodes
```

**Salida real de esta máquina:**

```
node/cka-cp cordoned
Warning: ignoring DaemonSet-managed Pods: kube-flannel/kube-flannel-ds-xmt9n, kube-system/kube-proxy-fqr8l
evicting pod kube-system/coredns-589f44dc88-zg9hl
pod/coredns-589f44dc88-zg9hl evicted
node/cka-cp drained
NAME     STATUS                     ROLES           AGE   VERSION
cka-cp   Ready,SchedulingDisabled   control-plane   13m   v1.36.4
cka-w1   Ready                      <none>          13m   v1.36.4
```

`drain` hace **dos** cosas, y conviene separarlas mentalmente:

1. **`cordoned`** = marca el nodo como no programable (`SchedulingDisabled`). Nada nuevo
   aterrizará aquí. Eso solo lo hace `kubectl cordon`.
2. **`evicting`** = desaloja los Pods que ya estaban, respetando los PodDisruptionBudgets.

Y `--ignore-daemonsets` es obligatorio en la práctica: los Pods de un DaemonSet (Flannel,
kube-proxy) **tienen que** estar en el nodo; si no los ignoras, `drain` se niega a seguir.

### 6.6 Actualizar kubelet y kubectl

```bash
# DENTRO DE cka-cp
apt-mark unhold kubelet kubectl
apt-get update && apt-get install -y kubelet='1.37.0-*' kubectl='1.37.0-*'
apt-mark hold kubelet kubectl
systemctl daemon-reload
systemctl restart kubelet
kubelet --version
```

**Salida real de esta máquina:**

```
kubelet set on hold.
kubectl set on hold.
Kubernetes v1.37.0
```

Si inmediatamente después lanzas un `kubectl`, es probable que veas esto:

```
The connection to the server 10.55.0.98:6443 was refused - did you specify the right host or port?
```

**No te asustes: es esperado.** Acabas de reiniciar el kubelet, y el kubelet es quien
arranca el API server (que es un static pod). Durante unos segundos no hay API server.
Espera a que vuelva:

```bash
# DENTRO DE cka-cp
until kubectl get --raw=/readyz > /dev/null 2>&1; do sleep 5; done
kubectl uncordon cka-cp
kubectl get nodes
```

**Salida real de esta máquina:**

```
node/cka-cp uncordoned
NAME     STATUS   ROLES           AGE   VERSION   
cka-cp   Ready    control-plane   14m   v1.37.0
cka-w1   Ready    <none>          13m   v1.36.4
```

**Ahí tienes el *version skew* en vivo:** control plane en 1.37.0, worker en 1.36.4. Este
estado es **legal y soportado** (el kubelet puede ir hasta tres versiones menores por detrás
del API server). Lo ilegal sería al revés.

### 6.7 Actualizar el worker

```bash
# DENTRO DE cka-w1
sed -i 's|/v1.36/|/v1.37/|' /etc/apt/sources.list.d/kubernetes.list
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.37/deb/Release.key \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg --yes
apt-get update
apt-mark unhold kubeadm && apt-get install -y kubeadm='1.37.0-*' && apt-mark hold kubeadm
kubeadm upgrade node
```

**Salida real de esta máquina:**

```
[upgrade/preflight] Running pre-flight checks
[upgrade/preflight] Skipping prepull. Not a control plane node.
[upgrade/control-plane] Skipping phase. Not a control plane node.
[upgrade/kubeconfig] Skipping phase. Not a control plane node.
[upgrade] Backing up kubelet config file to /etc/kubernetes/tmp/kubeadm-kubelet-config-2026-08-31-14-40-33/config.yaml
[kubelet-start] Writing kubelet configuration to file "/var/lib/kubelet/config.yaml"
[upgrade/kubelet-config] The kubelet configuration for this node was successfully upgraded!
[upgrade/addon] Skipping the addon/coredns phase. Not a control plane node.
```

En un worker es **`kubeadm upgrade node`**, no `apply`. Y mira cuántas fases dice
`Skipping … Not a control plane node`: en un worker lo único que hay que actualizar es la
configuración del kubelet.

Ahora vacía el worker desde el control plane y actualiza su kubelet:

```bash
# DENTRO DE cka-cp
kubectl drain cka-w1 --ignore-daemonsets
```

**Salida real de esta máquina:**

```
evicting pod default/web-7fbc579fd4-dch5h
evicting pod default/web-7fbc579fd4-nxlxr
evicting pod kube-system/coredns-559f6c778d-b8mpj
evicting pod default/web-7fbc579fd4-kjp7r
pod/web-7fbc579fd4-dch5h evicted
pod/web-7fbc579fd4-kjp7r evicted
pod/web-7fbc579fd4-nxlxr evicted
pod/coredns-559f6c778d-x9t6b evicted
pod/coredns-559f6c778d-b8mpj evicted
node/cka-w1 drained
```

Aquí sí se movió trabajo real: tus tres réplicas de `web`.

```bash
# DENTRO DE cka-w1
apt-mark unhold kubelet kubectl
apt-get install -y kubelet='1.37.0-*' kubectl='1.37.0-*'
apt-mark hold kubelet kubectl
systemctl daemon-reload && systemctl restart kubelet
kubelet --version
```

**Salida real de esta máquina:**

```
Kubernetes v1.37.0
```

```bash
# DENTRO DE cka-cp
kubectl uncordon cka-w1
kubectl get nodes -o wide
```

**Salida real de esta máquina:**

```
node/cka-w1 uncordoned
NAME     STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION              CONTAINER-RUNTIME
cka-cp   Ready    control-plane   15m   v1.37.0   10.55.0.98    <none>        Ubuntu 24.04.4 LTS   6.8.0-138-generic (amd64)   containerd://2.2.1
cka-w1   Ready    <none>          14m   v1.37.0   10.55.0.190   <none>        Ubuntu 24.04.4 LTS   6.8.0-138-generic (amd64)   containerd://2.2.1
```

**Clúster completo en v1.37.0, sin haber borrado nada.** Y tu aplicación sobrevivió:

```bash
# DENTRO DE cka-cp
kubectl get deploy,pods -o wide
```

**Salida real de esta máquina:**

```
NAME                  READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES              SELECTOR
deployment.apps/web   3/3     3            3           17m   nginx        nginx:1.29-alpine   app=web

NAME                       READY   STATUS    RESTARTS   AGE    IP            NODE     NOMINATED NODE   READINESS GATES
pod/web-7fbc579fd4-9tpmq   1/1     Running   0          3m9s   10.244.1.11   cka-w1   <none>           <none>
pod/web-7fbc579fd4-vfcnf   1/1     Running   0          3m9s   10.244.1.10   cka-w1   <none>           <none>
pod/web-7fbc579fd4-zfmqs   1/1     Running   0          3m9s   10.244.1.12   cka-w1   <none>           <none>
```

`AGE` del Deployment: 17 minutos. `AGE` de los Pods: 3 minutos. El objeto sobrevivió; los
Pods se recrearon tras el desalojo. Eso es el loop de reconciliación del módulo 4 haciendo
su trabajo durante una operación de mantenimiento.

### 6.8 Regalo: los certificados se renovaron solos

```bash
# DENTRO DE cka-cp
kubeadm certs check-expiration | head -18
```

**Salida real de esta máquina:**

```
CERTIFICATE                EXPIRES                  RESIDUAL TIME   CERTIFICATE AUTHORITY   EXTERNALLY MANAGED
admin.conf                 Aug 31, 2027 14:36 UTC   364d            ca                      no      
apiserver                  Aug 31, 2027 14:36 UTC   364d            ca                      no      
apiserver-etcd-client      Aug 31, 2027 14:36 UTC   364d            etcd-ca                 no      
apiserver-kubelet-client   Aug 31, 2027 14:36 UTC   364d            ca                      no      
controller-manager.conf    Aug 31, 2027 14:36 UTC   364d            ca                      no      
etcd-healthcheck-client    Aug 31, 2027 14:36 UTC   364d            etcd-ca                 no      
etcd-peer                  Aug 31, 2027 14:36 UTC   364d            etcd-ca                 no      
etcd-server                Aug 31, 2027 14:36 UTC   364d            etcd-ca                 no      
front-proxy-client         Aug 31, 2027 14:36 UTC   364d            front-proxy-ca          no      
scheduler.conf             Aug 31, 2027 14:36 UTC   364d            ca                      no      
super-admin.conf           Aug 31, 2027 14:36 UTC   364d            ca                      no      

CERTIFICATE AUTHORITY   EXPIRES                  RESIDUAL TIME   EXTERNALLY MANAGED
ca                      Aug 28, 2036 14:25 UTC   9y              no
```

Todos caducan en **364 días contados desde la hora de la actualización** (`14:36`), no desde
la instalación (`14:25`). `kubeadm upgrade` **renueva los certificados que gestiona**. De ahí
la recomendación operativa: actualizar al menos una vez al año, aunque solo sea por los
certificados. La CA, en cambio, dura 9 años.

---

## Paso 7: Respaldar y restaurar etcd (15 min)

**Todo el estado de tu clúster está en etcd.** Si pierdes etcd, no perdiste «unos objetos»:
perdiste el clúster. Este paso es el que más veces aparece en el examen CKA y el que más
veces se practica mal, porque la mayoría solo hace el `snapshot save`.

### 7.1 Crear algo que se pueda perder

```bash
# DENTRO DE cka-cp
kubectl create configmap estado-critico --from-literal=mensaje="existia-antes-del-snapshot"
kubectl get configmap estado-critico -o jsonpath='{.data.mensaje}'
```

**Salida real de esta máquina:**

```
configmap/estado-critico created
existia-antes-del-snapshot
```

### 7.2 El snapshot

`etcdctl` con la versión correcta ya vive dentro del Pod de etcd. Úsalo desde ahí:

```bash
# DENTRO DE cka-cp
kubectl -n kube-system exec etcd-cka-cp -- etcdctl version
```

**Salida real de esta máquina:**

```
etcdctl version: 3.7.0
API version: 3.7
```

```bash
# DENTRO DE cka-cp
kubectl -n kube-system exec etcd-cka-cp -- etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  snapshot save /var/lib/etcd/snapshot-antes.db
```

**Salida real de esta máquina** (recortada):

```
{"level":"info","ts":"2026-08-31T14:42:25.575189Z","caller":"snapshot/v3_snapshot.go:111","msg":"fetched snapshot","endpoint":"https://127.0.0.1:2379","size":"4.0 MB","took":"62.048635ms","etcd-version":"3.7.0"}
Snapshot saved at /var/lib/etcd/snapshot-antes.db
Server version 3.7.0
```

Los **tres certificados no son opcionales**: etcd solo habla TLS mutuo. Si en el examen te
falla el `snapshot save`, nueve de cada diez veces es una ruta de certificado mal escrita.

```bash
# DENTRO DE cka-cp
ls -lh /var/lib/etcd/snapshot-antes.db
```

**Salida real de esta máquina:**

```
-rw------- 1 root root 3.8M Aug 31 14:42 /var/lib/etcd/snapshot-antes.db
```

El archivo está **en el disco del nodo**, no dentro del contenedor, porque
`/var/lib/etcd` es un `hostPath` montado en el Pod. Un snapshot que se queda en el mismo
nodo que la base de datos no es un respaldo: cópialo fuera.

```bash
# DENTRO DE cka-cp
kubectl -n kube-system exec etcd-cka-cp -- etcdutl snapshot status /var/lib/etcd/snapshot-antes.db --write-out=table
```

**Salida real de esta máquina:**

```
┌──────────┬──────────┬────────────┬────────────┬─────────┐
│   HASH   │ REVISION │ TOTAL KEYS │ TOTAL SIZE │ VERSION │
├──────────┼──────────┼────────────┼────────────┼─────────┤
│ ec596377 │     2737 │        674 │     4.0 MB │   3.7.0 │
└──────────┴──────────┴────────────┴────────────┴─────────┘
```

674 claves: **todo tu clúster**, en 4 MB.

### 7.3 Provocar el desastre

```bash
# DENTRO DE cka-cp
kubectl delete configmap estado-critico
kubectl create configmap creado-despues --from-literal=mensaje="no-deberia-sobrevivir"
kubectl get configmaps
```

**Salida real de esta máquina:**

```
configmap "estado-critico" deleted from default namespace
configmap/creado-despues created
NAME               DATA   AGE
creado-despues     1      0s
kube-root-ca.crt   1      16m
```

### 7.4 Restaurar

La restauración necesita `etcdutl` **fuera** del Pod, porque durante el proceso el Pod de
etcd va a estar apagado. Instala los binarios de la misma versión que ya viste (3.7.0):

```bash
# DENTRO DE cka-cp
cd /tmp
curl -sSL -O https://github.com/etcd-io/etcd/releases/download/v3.7.0/etcd-v3.7.0-linux-amd64.tar.gz
tar xzf etcd-v3.7.0-linux-amd64.tar.gz
install -m 0755 etcd-v3.7.0-linux-amd64/etcdutl /usr/local/bin/etcdutl
install -m 0755 etcd-v3.7.0-linux-amd64/etcdctl /usr/local/bin/etcdctl
etcdutl version
```

**Salida real de esta máquina:**

```
etcdutl version: 3.7.0
API version: 3.7
```

**Paso 1 — apagar el control plane.** Recuerda el Paso 5.2: un static pod no se para con
`kubectl`. Se para moviendo su archivo.

```bash
# DENTRO DE cka-cp
mkdir -p /etc/kubernetes/manifests-off
mv /etc/kubernetes/manifests/*.yaml /etc/kubernetes/manifests-off/
ls -A /etc/kubernetes/manifests/
```

**Salida real de esta máquina:**

```
.kubelet-keep
```

Directorio vacío (el `.kubelet-keep` es un marcador del kubelet). En unos segundos el
kubelet apaga etcd, el API server, el scheduler y el controller manager.

**Paso 2 — restaurar a un directorio NUEVO.** Nunca encima del que está en uso.

```bash
# DENTRO DE cka-cp
etcdutl snapshot restore /var/lib/etcd/snapshot-antes.db --data-dir=/var/lib/etcd-restore
ls -ld /var/lib/etcd-restore/member
```

**Salida real de esta máquina** (recortada a la línea que confirma):

```
2026-08-31T14:43:18Z	info	snapshot/v3_snapshot.go:334	restored snapshot	{"path": "/var/lib/etcd/snapshot-antes.db", "wal-dir": "/var/lib/etcd-restore/member/wal", "data-dir": "/var/lib/etcd-restore", "snap-dir": "/var/lib/etcd-restore/member/snap"}
drwx------ 4 root root 4096 Aug 31 14:43 /var/lib/etcd-restore/member
```

**Paso 3 — apuntar el manifiesto de etcd al directorio nuevo.** Este es el paso que se
olvida y por el que la restauración «no funciona»: restauraste los datos, pero etcd sigue
leyendo los viejos.

```bash
# DENTRO DE cka-cp
sed -i 's#path: /var/lib/etcd$#path: /var/lib/etcd-restore#' /etc/kubernetes/manifests-off/etcd.yaml
grep -B2 -A2 '/var/lib/etcd-restore' /etc/kubernetes/manifests-off/etcd.yaml
```

**Salida real de esta máquina:**

```
89-    name: etcd-certs
90-  - hostPath:
91:      path: /var/lib/etcd-restore
92-      type: DirectoryOrCreate
93-    name: etcd-data
```

**Paso 4 — devolver los manifiestos.**

```bash
# DENTRO DE cka-cp
mv /etc/kubernetes/manifests-off/*.yaml /etc/kubernetes/manifests/
until kubectl get --raw=/readyz > /dev/null 2>&1; do sleep 5; done
kubectl get configmaps
```

**Salida real de esta máquina:**

```
NAME               DATA   AGE
estado-critico     1      79s
kube-root-ca.crt   1      17m
```

**Ahí está la prueba, y es doble:**

- **`estado-critico` volvió.** Lo habías borrado; el snapshot lo tenía.
- **`creado-despues` desapareció.** Lo creaste después del snapshot; para el clúster
  restaurado nunca existió.

Restaurar etcd no es «recuperar lo borrado»: es **viajar en el tiempo al instante exacto del
snapshot**. Todo lo posterior se pierde. Por eso los snapshots se hacen a menudo y por eso
antes de restaurar se piensa dos veces.

### 7.5 Comprobar la salud, y un detalle que confunde

```bash
# DENTRO DE cka-cp
etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health --write-out=table
kubectl get nodes
kubectl get pods -n kube-system | grep etcd
```

**Salida real de esta máquina:**

```
┌────────────────────────┬────────┬─────────────┬───────┐
│        ENDPOINT        │ HEALTH │    TOOK     │ ERROR │
├────────────────────────┼────────┼─────────────┼───────┤
│ https://127.0.0.1:2379 │   true │ 13.441752ms │       │
└────────────────────────┴────────┴─────────────┴───────┘
NAME     STATUS   ROLES           AGE   VERSION
cka-cp   Ready    control-plane   17m   v1.37.0
cka-w1   Ready    <none>          17m   v1.37.0
etcd-cka-cp                      0/1     Pending   0          42s
```

Lee la contradicción: **etcd está sano** (`HEALTH true`), el API server responde, los nodos
están `Ready`… y el Pod `etcd-cka-cp` dice `Pending`. Confírmalo por el otro lado:

```bash
# DENTRO DE cka-cp
crictl ps | grep etcd
kubectl get --raw='/livez?verbose' | grep etcd
```

**Salida real de esta máquina:**

```
e774f6bbd2126  270fbeb697171  58 seconds ago  Running  etcd  cc53a4ce1f332  etcd-cka-cp  kube-system
[+]etcd ok
```

**El contenedor lleva 58 segundos corriendo y el API server dice `[+]etcd ok`.** El
`Pending` de `kubectl get pods` es el *mirror pod* del Paso 5.2, que quedó desincronizado:
al restaurar etcd volviste a una foto donde ese objeto tenía otro identificador. La
API no es la fuente de verdad para un static pod; el archivo y el contenedor sí.

La corrección es decirle al kubelet que vuelva a publicar sus static pods:

```bash
# DENTRO DE cka-cp
systemctl restart kubelet
kubectl get pods -n kube-system -o wide | grep etcd
```

**Salida real de esta máquina:**

```
etcd-cka-cp   1/1   Running   0   3m27s   10.55.0.98   cka-cp   <none>   <none>
```

> **La lección de este paso, en una frase:** cuando la API y el nodo no coinciden, **cree al
> nodo**. `crictl ps`, `journalctl -u kubelet` y `/livez` te dicen lo que de verdad está
> pasando; `kubectl get pods` te dice lo que el API server alcanzó a registrar.

---

## Limpieza (3 min)

```bash
# EN TU PORTÁTIL
lxc delete --force cka-cp cka-w1
lxc profile delete cka-lab
lxc network delete k8sbr0
lxc list cka-
```

**Salida real de esta máquina:**

```
+------+-------+------+------+------+-----------+
| NAME | STATE | IPV4 | IPV6 | TYPE | SNAPSHOTS |
+------+-------+------+------+------+-----------+
```

Nada. Tu portátil quedó como estaba.

---

## Síntesis: qué hiciste y qué demostraste

| Lo que hiciste | Lo que demuestra |
|---|---|
| `lxc launch … --vm` y comparar `uname -r` | Un nodo real tiene su propio kernel; `kind` no |
| `product_uuid`, MAC, `swapon`, `nproc` | Los preflight de `kubeadm` son requisitos de Linux, no burocracia |
| `SystemdCgroup = true` | El kubelet y el runtime tienen que compartir gestor de cgroups |
| `apt-mark hold` | Un `apt upgrade` de rutina puede romper el *version skew* |
| Nodo `NotReady` → mensaje de la condición | El clúster te dice qué le falta si preguntas bien |
| Log de Flannel → `br_netfilter` | La documentación oficial es el punto de partida, no el final: el log manda |
| `taint` del control plane | Que los Pods vayan al worker es una decisión, no azar |
| `kubectl delete pod etcd-…` | Un static pod pertenece al kubelet, no a la API |
| `systemctl stop kubelet` | «Kubelet stopped posting node status» es el síntoma, `journalctl` la causa |
| `kubeadm upgrade plan` / `apply` / `node` | Actualizar es: repo → kubeadm → plan → apply → drain → kubelet → uncordon |
| Skew 1.37 / 1.36 entre nodos | El kubelet puede ir por detrás del API server; nunca por delante |
| `snapshot save` + `restore` + `sed` del manifiesto | Restaurar es viajar al instante del snapshot, y hay que reapuntar el `hostPath` |
| Mirror pod `Pending` con etcd sano | Cuando la API y el nodo discrepan, cree al nodo |

---

## Cómo conecta con el resto del curso

- **Módulo 1 (LFCS):** todo el diagnóstico de nodo fue `systemctl`, `journalctl`, `apt`,
  `sysctl` y `modprobe`. Kubernetes no reemplazó a Linux: se apoyó en él.
- **Módulo 3 (contenedores):** `crictl ps` te enseñó los contenedores OCI bajo los Pods, y
  containerd es el mismo runtime que viste colgando de `dockerd`.
- **Módulo 4 (KCNA):** los Deployments, Services y EndpointSlices se comportaron igual que en
  `kind`. Lo que cambió no fue Kubernetes: fue quién es responsable de que funcione.
- **Laboratorio 2 de este módulo:** allí firmarás un certificado de cliente a mano, igual
  que el clúster hizo por tu worker en el Paso 4.2.
- **Módulo 7 (CKS):** los certificados del Paso 6.8 y el acceso a etcd del Paso 7 son
  exactamente los activos que allí vas a aprender a proteger.

---

## Para profundizar

- Instalar kubeadm — <https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/>
- Container runtimes (cgroup driver, `SystemdCgroup`) — <https://kubernetes.io/docs/setup/production-environment/container-runtimes/>
- Actualizar clústeres kubeadm — <https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/>
- Política de version skew — <https://kubernetes.io/docs/setup/release/version-skew-policy/>
- Operar clústeres etcd (respaldo y restauración) — <https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-etcd/>
- Static Pods — <https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/>
- Mantenimiento de nodos: `cordon`, `drain` — <https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/>
- Documentación de LXD (instancias de tipo VM) — <https://documentation.ubuntu.com/lxd/>

---

# Anexo opcional (para casa)

No se hace en clase y no se evalúa en la sesión. Requiere el clúster del laboratorio, así
que hazlo **antes** de la limpieza (o recrea los pasos 0 a 4).

## A1: Los tokens de unión caducan (10 min)

```bash
# DENTRO DE cka-cp
kubeadm token list
```

Cada token tiene un `TTL`. Cuando expira, `kubeadm join` falla con un error de
autenticación que parece un problema de red y no lo es. Crea uno con caducidad corta y
míralo desaparecer:

```bash
# DENTRO DE cka-cp
kubeadm token create --ttl 5m --description "token de prueba del anexo"
kubeadm token list
```

Preguntas para responder tú: ¿qué pasa si borras **todos** los tokens? ¿Puede unirse un
nodo nuevo? ¿Y sigue funcionando el que ya estaba unido? (Pista: el nodo unido ya tiene su
propio certificado; el token solo sirve para el trámite inicial.)

## A2: Renovar certificados a mano (10 min)

```bash
# DENTRO DE cka-cp
kubeadm certs check-expiration
kubeadm certs renew apiserver
kubeadm certs check-expiration | grep apiserver
```

Después de renovar hay que **reiniciar el componente**, y ya sabes cómo se hace con un
static pod: mover su manifiesto fuera y devolverlo, o reiniciar el kubelet. Compruébalo con
`crictl ps` y verás el contenedor con `CREATED` nuevo.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
