# Laboratorio – Kubernetes: primeras cargas de trabajo y el loop de reconciliación

**Módulo 4 · en clase · 70–80 minutos.** Es la primera clase de Kubernetes: el objetivo es
entender cómo funciona la plataforma y desplegar cargas de trabajo básicas. Nada más, y
nada menos.

| Bloque | Pasos | Tiempo | ¿Se puede dejar para casa? |
|---|---|---|---|
| **Preparación** (herramientas y clúster) | 0 | ~7 min | No |
| **Arquitectura, de verdad** | 1 | ~13 min | No |
| **Desplegar cargas de trabajo** | 2 | ~30 min | No: es el corazón de la clase |
| **Auto-reparación y escalado** | 3 | ~20 min | No |
| **Limpieza y síntesis** | – | ~5 min | No |
| **Anexo opcional** (admission, swap, cgroups) | A0–A2 | ~50 min | **Sí: no se hace en clase** |

Los pasos 0 a 3 son el laboratorio de la sesión y cada uno depende del anterior. El
**Anexo opcional** del final es material avanzado para quien quiera seguir en casa: no se
hace en clase y no se evalúa en la sesión.

> La idea central del módulo cabe en una frase: **Kubernetes no ejecuta tu aplicación,
> reconcilia un estado deseado con el estado real, una y otra vez, para siempre.** Todo lo
> que vas a hacer aquí es una forma distinta de ver esa misma frase funcionando. El
> objetivo no es producir un artefacto entregable: es que las palabras que más se repiten
> en Kubernetes (*control plane*, *Pod*, *Deployment*, *Service*, *reconciliación*) dejen
> de ser vocabulario y se conviertan en cosas que viste con tus propios ojos en una
> terminal.

---

## Objetivo

Al terminar, vas a poder responder estas preguntas señalando la evidencia en tu propia
terminal, no repitiendo una definición de memoria:

1. ¿Qué corre realmente en un "nodo" de Kubernetes, y por qué el nodo que vas a usar es,
   literalmente, un contenedor Docker que comparte el kernel de tu máquina (módulo 3)?
2. ¿Por qué `etcd`, `kube-apiserver`, `kube-scheduler` y `kube-controller-manager`
   aparecen como Pods de la nada con `kubectl`, y quién los arranca?
3. ¿Cómo se crea un Pod, un Deployment y un Service **sin memorizar YAML**, y de dónde
   sale el YAML cuando lo necesitas?
4. ¿Cómo llega un `Service` a sus Pods, concretamente, qué objeto guarda esa lista de IPs?
5. ¿Por qué CoreDNS te resuelve `web` por nombre sin que hayas configurado nada, cuando
   en el módulo 3 (paso 8) un `docker run` normal te respondía `ping: bad address 'web'`?
6. Si borras un Pod, ¿vuelve el mismo o aparece otro? ¿Y si lo que muere es solo el
   contenedor, por debajo de Kubernetes?

**Requisito:** haber pasado por el módulo 1 (`systemd`, `systemctl`, `journalctl`) y por
el módulo 3 (contenedores, namespaces, imágenes OCI). Este laboratorio se apoya en los dos
y lo dice explícitamente cuando lo hace.

**Entorno:** Linux con Docker Engine activo, `kind` y `kubectl`. El clúster se crea desde
cero en el Paso 0 y se borra completo al final: no necesitas ningún clúster previo ni
acceso a la nube. (El Anexo opcional añade `openssl`.)

---

## Paso 0: Verificar herramientas y crear el clúster (7 min)

```bash
docker version --format '{{.Server.Version}}'
kind version
kubectl version --client=true
```

**Mínimos verificados para este laboratorio:** `kind` v0.32.0 (necesita conocer la imagen
de nodo v1.36) y `kubectl` v1.36.1. Si tu `kubectl` es más viejo no pasa nada
inmediatamente: la política oficial de *version skew* de Kubernetes dice que **`kubectl`
está soportado dentro de un *minor* de diferencia (más viejo o más nuevo) respecto del
`kube-apiserver`**, así que con un API server 1.36 sirven `kubectl` 1.35, 1.36 y 1.37.
Fuera de ese rango, algunos comandos de este laboratorio pueden comportarse distinto.
(Fuente: `kubernetes.io/releases/version-skew-policy/`.)

**Salida real de esta máquina** (tus versiones pueden ser otras; lo que importa es que no
sean *menores* que estas):

```
29.7.2
kind v0.32.0 go1.26.3 linux/amd64
Client Version: v1.36.1
Kustomize Version: v5.8.1
```

Ahora crea el clúster. `kind` levanta un clúster de Kubernetes usando contenedores Docker
como nodos, y para un clúster de un solo nodo no hace falta ningún archivo de
configuración:

```bash
time kind create cluster --name topicos-m4
kubectl config current-context
kubectl cluster-info
```

**Salida real de esta máquina** (el puerto de `cluster-info` es aleatorio en cada
creación, y el tiempo depende mucho de si ya tenías la imagen en caché):

```
Creating cluster "topicos-m4" ...
 ✓ Ensuring node image (kindest/node:v1.36.1) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-topicos-m4"

real	0m9.645s

kind-topicos-m4
Kubernetes control plane is running at https://127.0.0.1:40691
CoreDNS is running at https://127.0.0.1:40691/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
```

> **Sobre ese `real 0m9.645s`.** Diez segundos es lo que tarda **con la imagen de nodo ya
> descargada** (1.31 GB) en una máquina rápida. La primera vez que la descargues, cuenta
> varios minutos según tu conexión. No te alarmes si tu número es 20 veces mayor: no es un
> error, es la descarga.

> **La imagen del nodo y por qué a veces conviene fijarla.** Sin configuración, `kind`
> v0.32.0 usa su imagen de nodo por defecto, que en esta versión es
> `kindest/node:v1.36.1` (lo ves en la primera línea de la salida). Un *tag* es una
> etiqueta móvil y un *digest* es contenido inmutable, exactamente como viste en el módulo
> 3. Si necesitas que este laboratorio dé el mismo resultado hoy y en seis meses, se fija
> `tag@digest`. El digest verificado en esta máquina el **20 de agosto de 2026** es:
>
> ```
> kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5
> ```
>
> Para el núcleo de este laboratorio no hace falta: el comando de arriba, tal cual, es
> suficiente. Fijar el digest requiere un archivo de configuración de `kind`, y eso lo
> haces en el Anexo opcional.

`kind` acaba de cambiar tu contexto activo de `kubectl` a `kind-topicos-m4`. De aquí en
adelante, todo comando `kubectl` habla con este clúster.

---

## Paso 1: La arquitectura, de verdad (13 min)

Las diapositivas del módulo tienen el diagrama de cajas: API server, etcd, scheduler,
controller manager, kubelet, kube-proxy, runtime, CNI. Aquí vas a tocar cada caja.

### 1.1 El nodo es un contenedor (módulo 3)

```bash
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl get nodes -o wide
```

**Salida real de esta máquina:**

```
NAME                       STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                       KERNEL-VERSION            CONTAINER-RUNTIME
topicos-m4-control-plane   Ready    control-plane   19s   v1.36.1   172.18.0.5    <none>        Debian GNU/Linux 13 (trixie)   6.17.0-1032-oem (amd64)   containerd://2.3.1
```

Tres columnas que valen todo el paso:

- **`CONTAINER-RUNTIME: containerd://2.3.1`**: el runtime es `containerd`, hablando por
  CRI. Es el mismo `containerd` que en el módulo 3 viste colgando de `dockerd` en el
  `pstree`. Kubernetes no habla con Docker: habla CRI con containerd.
- **`KERNEL-VERSION: 6.17.0-1032-oem`**: compáralo con tu host ahora mismo.
- **`INTERNAL-IP: 172.18.0.5`**: una IP de red Docker. Tu "nodo" está en una red bridge de
  Docker.

```bash
uname -r
docker exec topicos-m4-control-plane uname -r
docker ps --filter "name=topicos-m4-control-plane" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
```

**Salida real de esta máquina:**

```
6.17.0-1032-oem
6.17.0-1032-oem

NAMES                      IMAGE                  STATUS
topicos-m4-control-plane   kindest/node:v1.36.1   Up 25 seconds
```

**Exactamente el mismo kernel**, igual que en el Paso 1 del laboratorio del módulo 3. El
"nodo" de Kubernetes que acabas de crear es un contenedor de sistema corriendo sobre el
kernel de tu portátil.

> **Precisión, porque aquí se confunde mucho.** Esto es una particularidad de `kind`
> ("Kubernetes IN Docker"), no de Kubernetes. En un clúster real, un nodo es una máquina
> física o virtual con su propio kernel. Lo que **sí** es idéntico en los dos casos es todo
> lo demás: los mismos binarios, los mismos manifiestos, las mismas APIs. Por eso `kind`
> sirve para aprender y para CI, y por eso no sirve para producción.

### 1.2 El kubelet es un proceso de systemd (módulo 1)

```bash
docker exec topicos-m4-control-plane systemctl is-active kubelet containerd
docker exec topicos-m4-control-plane systemctl status kubelet --no-pager -l | head -14
```

**Salida real de esta máquina** (recortada):

```
active
active

● kubelet.service - kubelet: The Kubernetes Node Agent
     Loaded: loaded (/etc/systemd/system/kubelet.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/kubelet.service.d
             └─10-kubeadm.conf, 11-kind.conf
     Active: active (running) since Fri 2026-08-21 02:19:20 UTC; 17s ago
   Main PID: 806 (kubelet)
      Tasks: 24 (limit: 11423)
     Memory: 36.7M (peak: 38.4M)
        CPU: 583ms
     CGroup: /kubelet.slice/kubelet.service
```

Léelo con los ojos del módulo 1: es una unidad de systemd corriente. Tiene `Drop-In`
(fragmentos que sobreescriben la unidad base, ahí es donde `kubeadm` y `kind` inyectan su
configuración), tiene un `Main PID`, y **vive dentro de su propio cgroup**
(`/kubelet.slice/kubelet.service`). El kubelet no es magia distribuida: es un demonio de
Linux. Si algún día un nodo no arranca, `journalctl -u kubelet` es tu primera parada,
exactamente igual que en el módulo 1.

### 1.3 El control plane son Pods de la nada

```bash
kubectl get pods -n kube-system
```

**Salida real de esta máquina**, capturada apenas el nodo pasó a `Ready`:

```
NAME                                               READY   STATUS              RESTARTS   AGE
coredns-589f44dc88-2nw7k                           0/1     ContainerCreating   0          12s
coredns-589f44dc88-579rf                           0/1     ContainerCreating   0          12s
etcd-topicos-m4-control-plane                      1/1     Running             0          18s
kindnet-c4b27                                      1/1     Running             0          12s
kube-apiserver-topicos-m4-control-plane            1/1     Running             0          18s
kube-controller-manager-topicos-m4-control-plane   1/1     Running             0          18s
kube-proxy-lmg7q                                   1/1     Running             0          12s
kube-scheduler-topicos-m4-control-plane            0/1     Running             0          18s
```

Que CoreDNS salga en `ContainerCreating` y el scheduler en `0/1` es normal: un nodo puede
estar `Ready` (el kubelet responde y la red del nodo funciona) mientras algunos Pods
todavía arrancan o todavía no pasan su *readiness probe*. Repite el comando unos segundos
después y los verás todos en `1/1 Running` (verificado en esta máquina).

Ahí está el diagrama completo del módulo, como Pods reales:

| Pod | Caja del diagrama |
|---|---|
| `etcd-…` | la base de datos: **todo** el estado del clúster |
| `kube-apiserver-…` | la única puerta de entrada; nadie más escribe en etcd |
| `kube-scheduler-…` | decide en qué nodo va cada Pod |
| `kube-controller-manager-…` | ejecuta los controladores (incluido el de ReplicaSet y el de EndpointSlice) |
| `kube-proxy-…` | traduce Services a reglas de red en cada nodo |
| `kindnet-…` | el plugin **CNI** de `kind` (en otro clúster sería Cilium, Calico, Flannel…) |
| `coredns-…` | DNS interno del clúster |

Fíjate en que los cuatro primeros llevan el nombre del nodo pegado
(`-topicos-m4-control-plane`). Eso es la firma de un **static Pod**: no lo creó nadie con
`kubectl`, lo arranca el kubelet leyendo archivos de un directorio del disco.

```bash
docker exec topicos-m4-control-plane ls -1 /etc/kubernetes/manifests/
```

**Salida real de esta máquina:**

```
etcd.yaml
kube-apiserver.yaml
kube-controller-manager.yaml
kube-scheduler.yaml
```

Este es el detalle que resuelve el huevo y la gallina: **¿cómo se crea el API server, si
para crear un Pod hace falta el API server?** No se crea por la API. El kubelet vigila ese
directorio y arranca lo que encuentre, sin preguntarle a nadie. Después, cuando el API
server ya está vivo, el kubelet le reporta esos Pods para que aparezcan en `kubectl get
pods`. Son *mirror pods*: la entrada en la API es un reflejo, el original es el archivo.

### 1.4 El runtime, desde adentro

```bash
docker exec topicos-m4-control-plane crictl ps
```

**Salida real de esta máquina** (recortada a las columnas que importan):

```
CONTAINER      CREATED          STATE     NAME                      NAMESPACE
22fef3765431d  10 seconds ago   Running   kindnet-cni               kube-system
31caf365be4c2  10 seconds ago   Running   kube-proxy                kube-system
4139c4fc0b14f  20 seconds ago   Running   etcd                      kube-system
90156fdaf6718  20 seconds ago   Running   kube-controller-manager   kube-system
9144216757c24  20 seconds ago   Running   kube-scheduler            kube-system
9482a5655bf4a  21 seconds ago   Running   kube-apiserver            kube-system
```

`crictl` es a CRI lo que `docker` es al daemon de Docker: un cliente de línea de comandos
del runtime, por debajo de Kubernetes. Estás viendo los **mismos** contenedores que
`kubectl get pods -n kube-system`, pero desde el otro lado de la frontera: aquí ya no hay
Pods como abstracción, hay contenedores OCI corriendo, igual que los del módulo 3.
Guárdalo: en el Paso 3.2 vas a usar `crictl` para romper algo a propósito.

---

## Paso 2: Desplegar cargas de trabajo (30 min)

Este es el corazón de la clase. Vas a crear las tres cargas básicas de Kubernetes (**Pod**,
**Deployment**, **Service**) y a verlas conectarse entre sí.

### 2.1 Un Pod, y la forma de trabajar que no exige memorizar YAML

Antes de crear nada, mira cómo se escribiría el YAML **sin escribirlo**:

```bash
kubectl run web-uno --image=nginx:1.29-alpine --dry-run=client -o yaml
```

**Salida real de esta máquina:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  labels:
    run: web-uno
  name: web-uno
spec:
  containers:
  - image: nginx:1.29-alpine
    name: web-uno
    resources: {}
  dnsPolicy: ClusterFirst
  restartPolicy: Always
status: {}
```

> **TIP: nadie memoriza el YAML de Kubernetes. Se genera.**
>
> `--dry-run=client` le dice a `kubectl` que **no** envíe nada al clúster, y `-o yaml` que
> imprima el objeto que habría enviado. Combinados, convierten cualquier comando
> imperativo en el manifiesto declarativo equivalente. Redirígelo a un archivo y ya tienes
> el punto de partida, sin buscar la indentación correcta de memoria:
>
> ```bash
> kubectl create deployment my-nginx --image=nginx --replicas=3 --dry-run=client -o yaml > deployment.yaml
> ```
>
> Funciona igual con las tres familias de comandos que vas a usar hoy:
> `kubectl run … --dry-run=client -o yaml` (Pods),
> `kubectl create deployment … --dry-run=client -o yaml` (Deployments) y
> `kubectl expose … --dry-run=client -o yaml` (Services).
>
> No es un truco de laboratorio: es como se trabaja de verdad, y es la técnica que se usa
> en los exámenes de certificación cronometrados, donde escribir YAML a mano cuesta
> minutos que no tienes.

Ahora créalo de verdad, sin `--dry-run`:

```bash
kubectl run web-uno --image=nginx:1.29-alpine
kubectl wait --for=condition=Ready pod/web-uno --timeout=180s
kubectl get pod web-uno -o wide
```

**Salida real de esta máquina:**

```
pod/web-uno created
pod/web-uno condition met
NAME      READY   STATUS    RESTARTS   AGE   IP           NODE                       NOMINATED NODE   READINESS GATES
web-uno   1/1     Running   0          8s    10.244.0.5   topicos-m4-control-plane   <none>           <none>
```

Tienes un Pod corriendo, con su propia IP (`10.244.0.5`, se la dio el plugin CNI). Ahora
bórralo y mira qué pasa:

```bash
kubectl delete pod web-uno
kubectl get pods
```

**Salida real de esta máquina:**

```
pod "web-uno" deleted from default namespace
No resources found in default namespace.
```

Se fue, y **no volvió**. Un Pod suelto no tiene quien lo cuide: si lo borras, o si muere el
nodo, desaparece y ya. Por eso en la práctica casi nunca se crean Pods sueltos, y por eso
existe el siguiente objeto.

### 2.2 Un Deployment, generado con el truco del `--dry-run`

La documentación oficial también está a un comando de distancia, sin salir de la terminal:

```bash
kubectl explain deployment.spec.replicas
```

**Salida real de esta máquina:**

```
GROUP:      apps
KIND:       Deployment
VERSION:    v1

FIELD: replicas <integer>

DESCRIPTION:
    Number of desired pods. This is a pointer to distinguish between explicit
    zero and not specified. Defaults to 1.
```

> **TIP: consultar la documentación oficial es el método, no una muleta.**
>
> La otra mitad de "no memorices YAML" es **consultar `kubernetes.io/docs`**. Es lo que se
> hace en el trabajo real y es coherente con la regla que atraviesa todo este curso: ante
> la duda sobre una API, una bandera o un valor por defecto, no adivines, verifica en la
> fuente oficial. `kubectl explain <recurso>.<campo>` es la misma documentación servida por
> el propio API server, sin navegador y sin internet.
>
> En los exámenes prácticos de la CNCF esto es explícito: la Linux Foundation permite
> abrir *"Kubernetes Documentation: https://kubernetes.io/docs/"* dentro del navegador del
> examen para **CKA, CKAD y CKS** (módulos 5, 6 y 7 de este curso), con la advertencia de
> que *"using the search function on https://kubernetes.io/docs/ is allowed, but you must
> not open external search results"*. (Fuente:
> `docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed`,
> consultada el 20 de agosto de 2026.) Ojo con generalizarlo: **KCNA**, la certificación de
> este módulo, **no aparece** en esa lista, porque es un examen de opción múltiple y no
> práctico. Confirma siempre las reglas en tu propia inscripción antes de presentarte.

Genera el manifiesto con el mismo patrón del TIP anterior, míralo, y recién entonces
aplícalo:

```bash
mkdir -p ~/lab-k8s && cd ~/lab-k8s

kubectl create deployment web --image=nginx:1.29-alpine --replicas=3 --dry-run=client -o yaml > deployment.yaml
cat deployment.yaml
```

**Salida real de esta máquina:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: web
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  strategy: {}
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - image: nginx:1.29-alpine
        name: nginx
        resources: {}
status: {}
```

Léelo antes de aplicarlo, porque aquí está la estructura que se repite en todo Kubernetes:

- **`spec.replicas: 3`**: cuántos Pods quieres. Este es el número que el controlador va a
  defender.
- **`spec.selector.matchLabels`**: **cómo** el Deployment reconoce a "sus" Pods. No los
  reconoce por nombre, los reconoce por etiqueta.
- **`spec.template`**: el molde del Pod. Fíjate en que `template.metadata.labels` coincide
  con el selector: si no coincidieran, el Deployment crearía Pods que después no
  reconocería como propios.

Ahora aplícalo:

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/web --timeout=180s
kubectl get deploy,rs,pods -o wide
```

**Salida real de esta máquina:**

```
deployment.apps/web created
Waiting for deployment "web" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "web" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "web" rollout to finish: 2 of 3 updated replicas are available...
deployment "web" successfully rolled out

NAME                  READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES              SELECTOR
deployment.apps/web   3/3     3            3           1s    nginx        nginx:1.29-alpine   app=web

NAME                             DESIRED   CURRENT   READY   AGE   CONTAINERS   IMAGES              SELECTOR
replicaset.apps/web-7fbc579fd4   3         3         3       1s    nginx        nginx:1.29-alpine   app=web,pod-template-hash=7fbc579fd4

NAME                       READY   STATUS    RESTARTS   AGE   IP           NODE
pod/web-7fbc579fd4-6xs7k   1/1     Running   0          1s    10.244.0.8   topicos-m4-control-plane
pod/web-7fbc579fd4-7dpbg   1/1     Running   0          1s    10.244.0.7   topicos-m4-control-plane
pod/web-7fbc579fd4-vz57m   1/1     Running   0          1s    10.244.0.6   topicos-m4-control-plane
```

(Los nombres con hash y las IPs `10.244.0.x` van a ser distintos en tu máquina.)

Tú creaste **un** objeto y aparecieron **tres niveles**. No es casualidad, es una cadena de
propiedad que puedes leer:

```bash
UNO=$(kubectl get pods -l app=web -o jsonpath='{.items[0].metadata.name}')
kubectl get pod "$UNO" -o jsonpath='{.metadata.name} <- {.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}'
kubectl get rs -l app=web -o jsonpath='{.items[0].metadata.name} <- {.items[0].metadata.ownerReferences[0].kind}/{.items[0].metadata.ownerReferences[0].name}{"\n"}'
```

**Salida real de esta máquina:**

```
web-7fbc579fd4-6xs7k <- ReplicaSet/web-7fbc579fd4
web-7fbc579fd4 <- Deployment/web
```

**Deployment → ReplicaSet → Pod.** Cada eslabón lo crea un controlador distinto vigilando
al anterior. Guárdalo: en el Paso 3 vas a ver ese mismo encadenamiento reaccionar en vivo.

### 2.3 Un Service con `kubectl expose`, y el EndpointSlice

Tres Pods con tres IPs que cambian cada vez que uno se recrea no sirven como dirección
estable. Para eso está el `Service`. Y se crea, otra vez, sin escribir YAML:

```bash
kubectl expose deployment web --port=80 --target-port=80 --dry-run=client -o yaml
```

**Salida real de esta máquina:**

```yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app: web
  name: web
spec:
  ports:
  - port: 80
    protocol: TCP
    targetPort: 80
  selector:
    app: web
status:
  loadBalancer: {}
```

`kubectl expose` copió el selector `app: web` del Deployment. Ese selector es todo el
vínculo entre el Service y los Pods: no hay una lista de nombres en ninguna parte.

```bash
kubectl expose deployment web --port=80 --target-port=80
kubectl get svc web
```

**Salida real de esta máquina:**

```
service/web exposed
NAME   TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
web    ClusterIP   10.96.175.77   <none>        80/TCP    0s
```

Pero el selector no se evalúa en cada paquete: hay un objeto intermedio que guarda la lista
concreta de IPs, y lo mantiene un controlador. Se llama **EndpointSlice**:

```bash
kubectl get endpointslices -l kubernetes.io/service-name=web
kubectl get pods -l app=web -o custom-columns=NAME:.metadata.name,IP:.status.podIP
```

**Salida real de esta máquina:**

```
NAME        ADDRESSTYPE   PORTS   ENDPOINTS                          AGE
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.8   0s

NAME                   IP
web-7fbc579fd4-6xs7k   10.244.0.8
web-7fbc579fd4-7dpbg   10.244.0.7
web-7fbc579fd4-vz57m   10.244.0.6
```

Las tres IPs del EndpointSlice son, exactamente, las tres IPs de tus Pods. Mira quién lo
escribió y qué guarda de cada endpoint:

```bash
kubectl get endpointslice -l kubernetes.io/service-name=web -o jsonpath='{range .items[0].endpoints[*]}{.addresses[0]}{"  ready="}{.conditions.ready}{"  pod="}{.targetRef.name}{"\n"}{end}'
kubectl get endpointslice -l kubernetes.io/service-name=web -o jsonpath='{.items[0].metadata.labels}{"\n"}'
```

**Salida real de esta máquina:**

```
10.244.0.6  ready=true  pod=web-7fbc579fd4-vz57m
10.244.0.7  ready=true  pod=web-7fbc579fd4-7dpbg
10.244.0.8  ready=true  pod=web-7fbc579fd4-6xs7k

{"app":"web","endpointslice.kubernetes.io/managed-by":"endpointslice-controller.k8s.io","kubernetes.io/service-name":"web"}
```

Dos cosas que leer aquí, y con eso basta por hoy:

- **`managed-by: endpointslice-controller.k8s.io`**: este objeto no lo escribió ningún
  humano. Lo escribe un controlador que vive dentro de `kube-controller-manager`, el Pod
  que viste en el Paso 1.3.
- **`ready=true` por endpoint**: no es una lista plana de IPs. Cada entrada lleva su
  estado, y por eso un Pod que se está apagando puede dejar de ser `ready` sin desaparecer
  de golpe. En el Paso 3 vas a ver esa lista moverse sola.

### 2.4 CoreDNS: el contraste con el módulo 3

En el módulo 3 (Paso 8), dos contenedores lanzados con `docker run` normal no podían verse
por nombre: `ping: bad address 'web'`. Hacía falta declarar una red *user-defined* (a mano
o vía Compose) para tener DNS. En Kubernetes eso viene puesto.

```bash
kubectl run cliente --image=alpine:3.20 --restart=Never --command -- sleep 3600
kubectl wait --for=condition=Ready pod/cliente --timeout=180s

kubectl exec cliente -- cat /etc/resolv.conf
kubectl exec cliente -- nslookup web.default.svc.cluster.local
kubectl exec cliente -- wget -qO- --timeout=5 http://web | head -4
```

**Salida real de esta máquina:**

```
search default.svc.cluster.local svc.cluster.local cluster.local
nameserver 10.96.0.10
options ndots:5

Server:		10.96.0.10
Address:	10.96.0.10:53

Name:	web.default.svc.cluster.local
Address: 10.96.175.77

<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
```

Nadie configuró DNS. El `/etc/resolv.conf` lo escribió el kubelet al crear el Pod,
apuntando a `10.96.0.10`, que es la ClusterIP del Service de CoreDNS. Y el nombre corto
`web` funciona por la línea `search`: el resolver prueba `web.default.svc.cluster.local`
primero. La dirección que devolvió el DNS (`10.96.175.77`) es exactamente la ClusterIP del
Service que creaste en 2.3.

> **Dos precisiones honestas sobre este paso.**
>
> 1. Si corres `kubectl exec cliente -- nslookup web` (nombre corto en vez de FQDN), el
>    `nslookup` de BusyBox imprime varios `** server can't find web.svc.cluster.local:
>    NXDOMAIN` **y termina con código de salida 1**, aunque la resolución haya funcionado.
>    No es un fallo del clúster, es que BusyBox reporta como error cada dominio de búsqueda
>    que no resolvió. Por eso arriba usamos el FQDN completo, que sale limpio. El
>    `wget http://web` con el nombre corto sí funciona sin ruido.
> 2. El Service de DNS se llama `kube-dns` aunque el software que corre sea **CoreDNS**:
>    `kubectl get svc -n kube-system kube-dns` te devuelve `10.96.0.10` (verificado en esta
>    máquina). Es compatibilidad hacia atrás con el DNS anterior, que sí se llamaba
>    kube-dns.

---

## Paso 3: Auto-reparación y escalado (20 min)

Ya tienes cargas de trabajo corriendo. Ahora rómpelas.

Todo lo que sigue es el **loop de reconciliación**: cada controlador de Kubernetes hace lo
mismo, para siempre. Observa el estado deseado (`spec`) y el real (`status`), compara, y
actúa para acercarlos. En la bibliografía vas a encontrar ese ciclo con el nombre
**Watch-Diff-Update**. No hay un "instalador" ni un "supervisor de arranque": hay un bucle,
y lo vas a ver correr tres veces en este paso.

### 3.1 Borra un Pod y mira quién lo repone

Abre una **segunda terminal** y déjala mirando:

```bash
# Terminal 2
kubectl get pods -l app=web -w
```

En la **primera** terminal, mata un Pod:

```bash
# Terminal 1
VICTIMA=$(kubectl get pods -l app=web -o jsonpath='{.items[0].metadata.name}')
echo "borrando: $VICTIMA"
kubectl delete pod "$VICTIMA"
```

**Salida real de la terminal 2 en esta máquina** (completa, sin recortar; `-w` repite
líneas porque emite un evento por cada escritura del objeto, aunque a ti te parezcan
iguales):

```
NAME                   READY   STATUS    RESTARTS   AGE
web-7fbc579fd4-6xs7k   1/1     Running   0          7s
web-7fbc579fd4-7dpbg   1/1     Running   0          7s
web-7fbc579fd4-vz57m   1/1     Running   0          7s
web-7fbc579fd4-6xs7k   1/1     Terminating   0          10s
web-7fbc579fd4-wkrgm   0/1     Pending       0          0s
web-7fbc579fd4-6xs7k   1/1     Terminating   0          10s
web-7fbc579fd4-wkrgm   0/1     Pending       0          0s
web-7fbc579fd4-wkrgm   0/1     ContainerCreating   0          0s
web-7fbc579fd4-6xs7k   0/1     Completed           0          10s
web-7fbc579fd4-6xs7k   0/1     Completed           0          10s
web-7fbc579fd4-6xs7k   0/1     Completed           0          10s
web-7fbc579fd4-wkrgm   0/1     ContainerCreating   0          0s
web-7fbc579fd4-wkrgm   1/1     Running             0          0s
```

Lee las tres líneas que importan, en orden:

1. `web-…-6xs7k` pasa a **`Terminating`**: el Pod que borraste.
2. En el **mismo segundo**, aparece `web-…-wkrgm` en **`Pending`**. Es un Pod **nuevo**,
   con **nombre distinto**.
3. Ese Pod nuevo pasa a `ContainerCreating` y luego a `Running`.

Fíjate en el detalle que más se malinterpreta: **el nombre cambió**. Kubernetes no
"reinició" tu Pod ni lo "revivió". El Pod que borraste está muerto y no vuelve. Lo que pasó
es que el ReplicaSet, que estaba observando los Pods con la etiqueta `app=web`, vio que su
`status` bajó a 2 mientras su `spec` seguía en 3, calculó la diferencia y creó **otro** Pod
para cerrarla. Diferencia = 1, acción = crear 1.

Y el EndpointSlice del Paso 2.3 se enteró solo:

```bash
kubectl get pods -l app=web -o custom-columns=NAME:.metadata.name,IP:.status.podIP
kubectl get endpointslices -l kubernetes.io/service-name=web
```

**Salida real de esta máquina:**

```
NAME                   IP
web-7fbc579fd4-7dpbg   10.244.0.7
web-7fbc579fd4-vz57m   10.244.0.6
web-7fbc579fd4-wkrgm   10.244.0.10

NAME        ADDRESSTYPE   PORTS   ENDPOINTS                           AGE
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10   23s
```

Compáralo con el Paso 2.3: antes eran `.6, .7, .8`; ahora son `.6, .7, .10`. **El mismo
objeto** (`web-7tml5`, mismo nombre, 23 segundos de antigüedad) cambió de contenido. La IP
muerta salió y la nueva entró, sin que tocaras nada. Ese es un segundo controlador
corriendo su propio loop sobre el resultado del primero.

### 3.2 Mata el contenedor por debajo de Kubernetes

En 3.1 borraste un **Pod** usando la API. Ahora vas a matar un **contenedor** a espaldas de
Kubernetes, desde el runtime, como si se hubiera caído solo.

Primero mira los contenedores de tus Pods desde el lado del runtime (el mismo `crictl` del
Paso 1.4, ahora filtrado por nombre de contenedor):

```bash
docker exec topicos-m4-control-plane crictl ps --name nginx
```

**Salida real de esta máquina:**

```
CONTAINER      CREATED          STATE     NAME    ATTEMPT   POD ID          POD                    NAMESPACE
664b73607d714  13 seconds ago   Running   nginx   0         cb7afda6733f9   web-7fbc579fd4-wkrgm   default
4e6aa3301b8ce  23 seconds ago   Running   nginx   0         52185c73d4d7f   web-7fbc579fd4-7dpbg   default
a988cd69264d4  23 seconds ago   Running   nginx   0         b7b0bf3183e5b   web-7fbc579fd4-vz57m   default
```

Esos son los contenedores reales que sostienen tus Pods. Fíjate en la columna `ATTEMPT`,
que está en `0` en los tres. Ahora para uno, por su ID de runtime:

```bash
CID=$(docker exec topicos-m4-control-plane crictl ps --name nginx -q | head -1)
POD=$(docker exec topicos-m4-control-plane crictl inspect --output go-template \
        --template '{{index .status.labels "io.kubernetes.pod.name"}}' "$CID")
echo "contenedor: $CID"
echo "pod: $POD"

docker exec topicos-m4-control-plane crictl stop "$CID"
sleep 8
kubectl get pods -l app=web
```

**Salida real de esta máquina** (el ID de contenedor sale recortado aquí por espacio):

```
contenedor: 664b73607d714da94f1669ad3e96c24d…
pod: web-7fbc579fd4-wkrgm

NAME                   READY   STATUS    RESTARTS     AGE
web-7fbc579fd4-7dpbg   1/1     Running   0            32s
web-7fbc579fd4-vz57m   1/1     Running   0            32s
web-7fbc579fd4-wkrgm   1/1     Running   1 (8s ago)   22s
```

**El Pod es el mismo** (`web-7fbc579fd4-wkrgm`, mismo nombre, 22 segundos de edad), pero
ahora marca `RESTARTS 1`. Míralo desde el runtime otra vez:

```bash
docker exec topicos-m4-control-plane crictl ps --name nginx
```

**Salida real de esta máquina:**

```
CONTAINER      CREATED          STATE     NAME    ATTEMPT   POD ID          POD                    NAMESPACE
c7bc42c1b7c52  7 seconds ago    Running   nginx   1         cb7afda6733f9   web-7fbc579fd4-wkrgm   default
4e6aa3301b8ce  31 seconds ago   Running   nginx   0         52185c73d4d7f   web-7fbc579fd4-7dpbg   default
a988cd69264d4  31 seconds ago   Running   nginx   0         b7b0bf3183e5b   web-7fbc579fd4-vz57m   default
```

El **`POD ID` no cambió** (`cb7afda6733f9`), el **ID de contenedor sí** (`c7bc42…` en vez
de `664b73…`) y el `ATTEMPT` pasó de `0` a `1`. Los eventos y el estado del Pod lo cuentan
igual:

```bash
kubectl get events --field-selector involvedObject.name=$POD --sort-by=.lastTimestamp \
  -o custom-columns=FIRST:.firstTimestamp,LAST:.lastTimestamp,COUNT:.count,REASON:.reason,MESSAGE:.message
kubectl get pod $POD -o jsonpath='restartPolicy={.spec.restartPolicy}  restartCount={.status.containerStatuses[0].restartCount}  motivo={.status.containerStatuses[0].lastState.terminated.reason}  exitCode={.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

**Salida real de esta máquina** (recortada en el espaciado para que quepa):

```
FIRST                  LAST                   COUNT   REASON      MESSAGE
2026-08-21T02:19:59Z   2026-08-21T02:19:59Z   1       Scheduled   Successfully assigned default/web-7fbc579fd4-wkrgm to topicos-m4-control-plane
2026-08-21T02:19:59Z   2026-08-21T02:20:14Z   2       Pulled      Container image "nginx:1.29-alpine" already present on machine and can be accessed by the pod
2026-08-21T02:19:59Z   2026-08-21T02:20:14Z   2       Created     Container created
2026-08-21T02:19:59Z   2026-08-21T02:20:14Z   2       Started     Container started

restartPolicy=Always  restartCount=1  motivo=Error  exitCode=137
```

`Scheduled` ocurrió **una** vez (el Pod se programó una sola vez, y sigue en el mismo
nodo), pero `Created` y `Started` llevan `COUNT 2`: una vez al nacer el Pod y otra 15
segundos después, cuando tú mataste el contenedor. El `exitCode=137` es `128 + 9`, o sea
`SIGKILL`: la señal que le llegó al proceso.

**Qué acabas de ver.** El kubelet no adivina el estado de tus contenedores: se lo pregunta
al runtime por CRI, continuamente, y sincroniza lo que encuentra contra lo que el Pod pide.
Cuando containerd le reportó que ese contenedor ya no estaba corriendo, el kubelet aplicó
el `restartPolicy` del Pod (`Always`, el valor por defecto) y le pidió al runtime que
arrancara uno nuevo dentro del **mismo** Pod. Por eso no hubo `Scheduled` nuevo, ni Pod
nuevo, ni IP nueva.

**Los dos loops, uno al lado del otro:**

| Qué rompiste | Quién reacciona | Resultado |
|---|---|---|
| Borraste el **Pod** (3.1) | el controlador de **ReplicaSet** | Pod **nuevo**, nombre distinto, IP distinta |
| Mataste el **contenedor** (3.2) | el **kubelet**, avisado por el runtime | **mismo** Pod, `RESTARTS +1`, misma IP |

Dos niveles distintos, dos controladores distintos, el mismo patrón: observar, comparar,
actuar.

### 3.3 Escalar, y ver la lista de endpoints seguir

Deja una **segunda terminal** mirando los EndpointSlices:

```bash
# Terminal 2
kubectl get endpointslices -l kubernetes.io/service-name=web -w
```

Y en la primera:

```bash
# Terminal 1
kubectl scale deployment/web --replicas=5
kubectl rollout status deployment/web --timeout=120s
kubectl scale deployment/web --replicas=2
```

**Salida real de la terminal 2 en esta máquina** (completa, sin recortar):

```
NAME        ADDRESSTYPE   PORTS   ENDPOINTS                           AGE
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10   32s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10 + 1 more...   35s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10 + 2 more...   35s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10 + 2 more...   38s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10 + 2 more...   38s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10 + 1 more...   38s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7,10.244.0.10               38s
web-7tml5   IPv4          80      10.244.0.6,10.244.0.7                           38s
```

Cuenta los endpoints línea a línea: **3 → 4 → 5**, y luego **5 → 4 → 3 → 2**. Y mira la
columna `AGE`: `32s`, `35s`, `38s`. **Es el mismo objeto todo el tiempo**, `web-7tml5`,
nunca se recreó. Solo cambió de contenido, siete veces, en seis segundos.

(`kubectl` abrevia con `+ N more...` cuando la columna no cabe; el objeto sí tiene todas
las direcciones. Hay dos líneas seguidas con `+ 2 more...` a los `38s`: son dos escrituras
distintas del objeto que en esta vista resumida se ven iguales, porque la columna
`ENDPOINTS` no muestra las condiciones `ready` de cada dirección.)

Reconstruye la cadena de lo que disparaste con un solo `kubectl scale`:

1. Tú cambiaste `spec.replicas` del **Deployment**.
2. El controlador de Deployment ajustó el `spec.replicas` del **ReplicaSet**.
3. El controlador de ReplicaSet vio la diferencia y creó (o borró) **Pods**.
4. El **scheduler** asignó nodo a cada Pod nuevo.
5. El **kubelet** de ese nodo le pidió a **containerd** que arrancara los contenedores.
6. Cuando cada Pod pasó a `Ready`, el controlador de **EndpointSlice** lo añadió a la lista.

Seis componentes. Ninguno se llamó entre sí. Cada uno estaba observando la API y reaccionó
a lo que vio. Eso es el loop de reconciliación, y es toda la arquitectura de Kubernetes:
controladores pequeños, independientes, cada uno empujando el mundo hacia el `spec`.

### 3.4 El último eslabón: `kube-proxy` en el kernel

Falta ver quién convierte esa lista de la API en algo que el kernel entienda. Ese alguien
es `kube-proxy`, y ya lo hizo mientras tú escalabas:

```bash
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=30 | grep -i "Proxier"
docker exec topicos-m4-control-plane iptables-save -t nat | grep "default/web"
```

**Salida real de esta máquina** (recortada; las líneas de `iptables-save` están
**reordenadas** para poder leerlas de arriba abajo, porque `iptables-save` las imprime
agrupadas por cadena y no en el orden en que se recorren; también se quitaron las líneas
`KUBE-MARK-MASQ`, que son de enmascaramiento y no de enrutamiento):

```
I0821 02:19:27.424590       1 server_linux.go:137] "Using iptables Proxier"

-A KUBE-SERVICES -d 10.96.175.77/32 -p tcp -m comment --comment "default/web cluster IP" -m tcp --dport 80 -j KUBE-SVC-LOLE4ISW44XBNF3G
-A KUBE-SVC-LOLE4ISW44XBNF3G -m comment --comment "default/web -> 10.244.0.6:80" -m statistic --mode random --probability 0.50000000000 -j KUBE-SEP-XBXNMJVLFJ54CH32
-A KUBE-SVC-LOLE4ISW44XBNF3G -m comment --comment "default/web -> 10.244.0.7:80" -j KUBE-SEP-BQUKCVYNN2D77XOH
-A KUBE-SEP-XBXNMJVLFJ54CH32 -p tcp -m comment --comment "default/web" -m tcp -j DNAT --to-destination 10.244.0.6:80
-A KUBE-SEP-BQUKCVYNN2D77XOH -p tcp -m comment --comment "default/web" -m tcp -j DNAT --to-destination 10.244.0.7:80
```

Léelo de arriba abajo, es toda la historia del Service en cuatro líneas:

1. Todo lo que va a `10.96.175.77:80` (la ClusterIP) salta a la cadena `KUBE-SVC-…`.
2. Esa cadena tiene dos ramas, y elige la primera **con probabilidad 0.5**. Ese es el
   balanceo de carga: `--mode random`, no un algoritmo sofisticado.
3. Cada rama hace `DNAT` a la IP real de un Pod: `10.244.0.6` y `10.244.0.7`, que son
   exactamente las dos que quedaron en el EndpointSlice después de escalar a 2.

La ClusterIP `10.96.175.77` no existe en ninguna interfaz de red: es una IP ficticia que
solo tiene sentido como criterio de una regla `iptables`. Por eso no puedes hacerle `ping`
y sí puedes conectarte a ella por TCP.

---

## Limpieza (3 min)

```bash
kind delete cluster --name topicos-m4
docker ps --filter "name=topicos-m4" --format '{{.Names}}'   # no debe imprimir nada
rm -rf ~/lab-k8s
```

**Salida real de esta máquina:**

```
Deleting cluster "topicos-m4" ...
Deleted nodes: ["topicos-m4-control-plane"]
```

Borrar el clúster borra los contenedores-nodo y con ellos etcd: todo el estado que creaste
desaparece. La imagen `kindest/node` se queda en tu caché de Docker, que es lo que hace que
la próxima creación tarde diez segundos y no varios minutos.

> Si vas a hacer el **Anexo opcional**, no borres nada todavía: el anexo empieza recreando
> el clúster con una configuración distinta, así que de todos modos vas a tener que borrar
> este. Puedes hacer la limpieza ahora y crear el nuevo después, o saltar directo al
> Anexo A0.

---

## Síntesis: cada componente y lo que le viste hacer

| Componente | Qué le viste hacer, en qué paso |
|---|---|
| **kube-apiserver** | única puerta de entrada; todo lo que hiciste con `kubectl` pasó por él (1.3, 2.x) |
| **etcd** | static Pod en `kube-system`: ahí quedó guardado todo lo que creaste (1.3) |
| **kube-scheduler** | asignó nodo a cada Pod nuevo, incluido el que repuso el ReplicaSet (1.3, 3.1) |
| **kube-controller-manager** | contiene el controlador de ReplicaSet (repuso el Pod, 3.1) y el de EndpointSlice (`managed-by`, 2.3) |
| **kubelet** | unidad de systemd con su propio cgroup (1.2); arranca los static Pods desde `/etc/kubernetes/manifests` (1.3); reinició el contenedor que mataste por CRI (3.2) |
| **kube-proxy** | tradujo la ClusterIP a reglas `iptables` con `DNAT` y `--probability 0.5` (3.4) |
| **containerd (CRI)** | el runtime del nodo; los mismos contenedores vistos con `crictl ps` (1.4, 3.2) |
| **CNI (kindnet)** | dio a cada Pod su IP `10.244.0.x`, enrutable dentro del clúster (2.2) |
| **CoreDNS** | resolvió `web.default.svc.cluster.local` sin configuración previa (2.4) |
| **Pod** | la unidad que se programa; suelto no se auto-repara (2.1), dentro de un Deployment sí (3.1) |
| **Deployment / ReplicaSet** | la cadena de propiedad `Deployment → ReplicaSet → Pod` (2.2) y el loop reaccionando (3.1, 3.3) |
| **Service / EndpointSlice** | la lista viva de IPs listas, actualizada siete veces en seis segundos al escalar (3.3) |
| **`--dry-run=client -o yaml`** | generó el YAML del Pod, del Deployment y del Service sin que memorizaras nada (2.1, 2.2, 2.3) |

---

## Cómo conecta con el resto del curso

- **Módulo 1:** el kubelet del Paso 1.2 es una unidad de systemd corriente, con `Drop-In`,
  `Main PID` y su propio cgroup. Cuando un nodo aparezca `NotReady`,
  `journalctl -u kubelet` va a ser tu primer comando, exactamente como allá.
- **Módulo 3:** el nodo del Paso 1.1 comparte kernel con tu host (`uname -r` idéntico),
  igual que el `docker run` del Paso 1 de aquel laboratorio; `crictl ps` (1.4 y 3.2) te
  enseña que por debajo de los Pods hay contenedores OCI corrientes; y el contraste de
  CoreDNS (2.4) es la otra cara del `ping: bad address 'web'` del Paso 8 de aquel
  laboratorio: la diferencia entre "el DNS lo declaras tú" y "el DNS viene con la
  plataforma".
- **Módulo 5 (CKA):** aquí el loop funciona; allá lo depuras cuando **no** funciona. Los
  comandos de este laboratorio (`kubectl get events`, `crictl ps`, `journalctl -u kubelet`)
  son literalmente el instrumental del dominio de *troubleshooting*. Y el patrón
  `--dry-run=client -o yaml` más la documentación oficial abierta es, literalmente, la
  forma de trabajar en el examen práctico.
- **Módulo 8 (GitOps):** el bucle del Paso 3 es exactamente el bucle de GitOps, con el
  estado deseado movido del `spec` de un objeto al contenido de un repositorio Git. El
  controlador cambia; el patrón es el mismo.

---

## Para profundizar

Lo de arriba lo observaste en tu terminal. Lo que sigue son afirmaciones que un comando no
te puede dar, verificadas contra la documentación oficial el **20 de agosto de 2026**
(Kubernetes 1.36).

**EndpointSlices y por qué existen.** La API `Endpoints` original guardaba todas las IPs de
un Service en un solo objeto, que había que reescribir entero por cada cambio: con miles de
Pods, eso satura al API server y a etcd. El control plane crea *slices* de **hasta 100
endpoints** por defecto, configurable con `--max-endpoints-per-slice` en
`kube-controller-manager` hasta un máximo de **1000**. Los EndpointSlices son la **fuente
de verdad para `kube-proxy`**, y la API `Endpoints` está **deprecada desde v1.33** (el
propio `kubectl` te lo advierte en pantalla si corres `kubectl get endpoints`). (Fuente:
`kubernetes.io/docs/concepts/services-networking/endpoint-slices/`.)

**Version skew.** `kubectl` está soportado dentro de **un** *minor* de diferencia, más
viejo o más nuevo, respecto del `kube-apiserver`. (Fuente:
`kubernetes.io/releases/version-skew-policy/`.)

**Documentación permitida en los exámenes de la CNCF.** Para **CKA, CKAD y CKS** la Linux
Foundation permite abrir `https://kubernetes.io/docs/` en el navegador del examen, con la
restricción de no abrir resultados de búsqueda externos. **KCNA no figura en esa lista.**
(Fuente: `docs.linuxfoundation.org/tc-docs/certification/certification-resources-allowed`.)

**Sobre el examen KCNA.** Este laboratorio cubre material de los dominios de fundamentos de
Kubernetes, orquestación de contenedores y arquitectura cloud native, pero **no** es una
guía de estudio del examen y aquí no se citan pesos de dominio: el currículo se revisa
periódicamente y una tabla copiada de un blog envejece mal. Consulta los pesos vigentes en
la página oficial del examen KCNA de la CNCF, como indica el `README.md` del módulo.

---
---

# Anexo opcional (para casa)

> **Opcional. No se hace en clase y no se evalúa en la sesión.** Es material avanzado para
> quien quiera seguir por su cuenta: dura unos **50 minutos**, exige recrear el clúster con
> una configuración distinta, y toca dos temas que el núcleo del laboratorio deja fuera a
> propósito: **admission control** (cómo se intercepta y modifica lo que entra al clúster) y
> **cgroup v2 con Node Memory Swap** (cómo Kubernetes le pone cuotas de memoria y swap a tus
> contenedores en el kernel).
>
> Hazlo con el archivo abierto, no de memoria. El paso A1.2 (escribir y registrar tu propio
> webhook) es el que más se recuerda a largo plazo y también el que más falla si vas
> improvisando.

| Bloque | Pasos | Tiempo |
|---|---|---|
| Recrear el clúster con configuración de swap | A0 | ~5 min |
| Admission: `LimitRanger` y tu propio webhook | A1 | ~30 min |
| cgroup v2 y Node Memory Swap | A2 | ~15 min |

**Requisito extra:** `openssl` instalado, y swap activo en el host si quieres ver números
reales en A2 (el anexo dice qué cambia si no lo tienes).

## Objetivo del anexo

1. ¿En qué punto exacto del camino de una petición se intercepta y **modifica** un objeto
   antes de guardarlo en `etcd`, y por qué eso pasa dos veces (un plugin compilado en el
   API server y un webhook tuyo)?
2. ¿Por qué un Pod `Guaranteed` no puede usar swap y uno `Burstable` sí, y de dónde sale el
   número exacto de bytes de swap que recibe?
3. ¿Qué relación hay entre la clase de QoS de un Pod y la jerarquía de cgroups v2 en el
   disco del nodo?

---

## A0: Recrear el clúster con configuración de kubelet (5 min)

El paso A2 necesita un kubelet configurado para tolerar y usar swap, y eso solo se puede
hacer **al crear el clúster**. Si todavía tienes el clúster del núcleo, bórralo:

```bash
kind delete cluster --name topicos-m4
```

Escribe la configuración. Cada línea es una decisión que vas a comprobar en A2:

```bash
mkdir -p ~/lab-k8s && cd ~/lab-k8s

cat > kind-topicos-m4.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: topicos-m4
nodes:
  - role: control-plane
    # Imagen fijada por tag + digest: el tag puede reapuntarse, el digest no.
    image: kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5
# Este parche configura el kubelet de TODOS los nodos. Lo verificas en A2.2.
kubeadmConfigPatches:
  - |
    kind: KubeletConfiguration
    failSwapOn: false
    memorySwap:
      swapBehavior: LimitedSwap
EOF

kind create cluster --config kind-topicos-m4.yaml
kubectl wait --for=condition=Ready node --all --timeout=180s
```

Cuatro decisiones deliberadas ahí:

- **`image: …@sha256:…`**: el mismo principio del módulo 3, un tag es una etiqueta móvil y
  un digest es contenido inmutable. Este digest corresponde a `kindest/node:v1.36.1` tal
  como estaba en caché local el **20 de agosto de 2026**; si `kind` te dice que no la
  encuentra, borra la parte `@sha256:…` y déjalo solo en `kindest/node:v1.36.1`, aceptando
  que ya no está fijado.
- **`name: topicos-m4`**: nombre propio, para no chocar con otros clústeres tuyos.
- **`failSwapOn: false`**: sin esto, el kubelet **no arranca** en un nodo con swap. La
  documentación oficial lo dice sin rodeos: *"By default, the kubelet will not start on a
  Linux node that has swap enabled."*
- **`memorySwap.swapBehavior: LimitedSwap`**: el valor por defecto es `NoSwap`. Con
  `NoSwap`, aunque el kubelet tolere el swap, **ningún** workload lo usa.

> **Lo que NO hay que poner aquí, y por qué importa.** Mucho material sobre Node Memory
> Swap te dice que añadas el *feature gate* `NodeSwap`. Eso ya no aplica: la tabla oficial
> de feature gates registra `NodeSwap` como **Alpha en 1.22–1.27, Beta (apagado) en
> 1.28–1.29, Beta (encendido) en 1.30–1.33 y GA desde 1.34**, sin versión de retiro. En un
> clúster 1.36 como este, la funcionalidad está siempre activa y el gate no hace falta. Si
> lo copias de un tutorial viejo, en el mejor de los casos es ruido. (Fuente:
> `kubernetes.io/docs/reference/command-line-tools-reference/feature-gates/`, fila
> `NodeSwap`.)

---

## A1: Admission, modificar lo que entra al clúster (30 min)

Antes de guardar cualquier objeto en etcd, el API server lo pasa por una cadena de
**admission controllers**. Los hay de dos tipos: los que **modifican** el objeto
(*mutating*) y los que solo lo **aceptan o rechazan** (*validating*). Vas a ver los dos
mecanismos que existen: uno compilado dentro del API server, y uno tuyo, colgado por HTTPS.

### A1.1 Un plugin que ya está encendido: LimitRanger (10 min)

```bash
kubectl create namespace admision

cat > limitrange.yaml <<'EOF'
apiVersion: v1
kind: LimitRange
metadata:
  name: limites-por-defecto
  namespace: admision
spec:
  limits:
    - type: Container
      default:            # se aplica como LIMIT si no declaras uno
        cpu: 250m
        memory: 128Mi
      defaultRequest:     # se aplica como REQUEST si no declaras uno
        cpu: 50m
        memory: 64Mi
EOF

kubectl apply -f limitrange.yaml
```

Ahora crea un Pod **sin declarar ningún recurso**:

```bash
kubectl run desnudo -n admision --image=alpine:3.20 --restart=Never --command -- sleep 3600
kubectl wait --for=condition=Ready pod/desnudo -n admision --timeout=120s

kubectl get pod desnudo -n admision -o jsonpath='{.spec.containers[0].resources}' | jq .
kubectl get pod desnudo -n admision -o jsonpath='{.metadata.annotations}' | jq .
kubectl get pod desnudo -n admision -o jsonpath='{.status.qosClass}{"\n"}'
```

**Salida real de esta máquina:**

```json
{
  "limits": {
    "cpu": "250m",
    "memory": "128Mi"
  },
  "requests": {
    "cpu": "50m",
    "memory": "64Mi"
  }
}
```

```json
{
  "kubernetes.io/limit-ranger": "LimitRanger plugin set: cpu, memory request for container desnudo; cpu, memory limit for container desnudo"
}
```

```
Burstable
```

Tú no escribiste ni una línea de `resources`. El objeto que quedó guardado **no es el que
enviaste**: el API server lo modificó en vuelo. Y dejó su firma: la anotación
`kubernetes.io/limit-ranger` dice literalmente qué plugin tocó qué. Esa anotación es la
prueba de que hubo mutación, no una inferencia tuya.

Efecto secundario que vas a necesitar en A2: como ahora `requests` ≠ `limits`, el Pod quedó
en clase de calidad de servicio **`Burstable`**.

`LimitRanger` no lo activaste tú. Está en el conjunto por defecto: la documentación oficial
lista, para Kubernetes 1.36, los plugins encendidos de fábrica, e incluye `LimitRanger`,
`MutatingAdmissionWebhook`, `ValidatingAdmissionWebhook`, `PodSecurity`, `ResourceQuota`,
`ServiceAccount`, `NamespaceLifecycle` y varios más. (Fuente:
`kubernetes.io/docs/reference/access-authn-authz/admission-controllers/`, sección *"Which
plugins are enabled by default?"*.)

Fíjate en que ahí están **`MutatingAdmissionWebhook`** y **`ValidatingAdmissionWebhook`**.
Esos dos plugins no hacen nada por sí solos: son los puntos de extensión que llaman a
webhooks que **tú** registres. Es exactamente lo que vas a hacer ahora.

### A1.2 Tu propio MutatingWebhookConfiguration (20 min)

El plan: un servidor HTTPS mínimo en Python que reciba un `AdmissionReview`, devuelva un
parche JSON que añade una etiqueta, y registrarlo para que el API server lo consulte antes
de crear cualquier Pod **en un solo namespace**.

#### A1.2.1 TLS: por qué es obligatorio y con qué nombre

El API server **solo** habla HTTPS con los webhooks, y valida el certificado contra el
`caBundle` que tú declares. El certificado tiene que ser válido para el nombre DNS interno
del Service, con el formato `<servicio>.<namespace>.svc`.

```bash
mkdir -p ~/lab-webhook && cd ~/lab-webhook

# 1. Una CA propia (solo para este laboratorio)
openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.crt -days 365 \
  -subj "/CN=webhook-ca-topicos"

# 2. La llave y la solicitud del servidor
openssl req -newkey rsa:2048 -nodes -keyout tls.key -out tls.csr \
  -subj "/CN=inyector.webhooks.svc"

# 3. Las extensiones: el SAN es lo que de verdad se valida
cat > ext.cnf <<'EOF'
subjectAltName = DNS:inyector.webhooks.svc
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF

# 4. Firmar
openssl x509 -req -in tls.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out tls.crt -days 365 -extfile ext.cnf

openssl x509 -in tls.crt -noout -subject -ext subjectAltName
```

**Salida real de esta máquina:**

```
subject=CN = inyector.webhooks.svc
X509v3 Subject Alternative Name:
    DNS:inyector.webhooks.svc
```

> **El error número uno de este paso** es poner el nombre solo en el `CN` y no en el
> `subjectAltName`. Los clientes TLS modernos, incluido el API server, ignoran el `CN` para
> verificar el nombre del host: si no hay SAN, el saludo TLS falla y el webhook nunca
> recibe nada. El archivo `ext.cnf` de arriba existe para eso.
>
> `tls.key` es material privado. No lo subas a ningún repositorio, no lo pegues en el chat,
> no lo imprimas en la terminal. Aquí es desechable, pero la costumbre no lo es.

#### A1.2.2 El servidor

```bash
kubectl create namespace webhooks
kubectl create secret tls inyector-tls -n webhooks --cert=tls.crt --key=tls.key

cat > servidor.py <<'PYEOF'
import base64, json, ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

ETIQUETA = "inyectado-por"
VALOR = "webhook-topicos-m4"

class Manejador(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        revision = json.loads(self.rfile.read(n))
        peticion = revision.get("request", {})
        etiquetas = peticion.get("object", {}).get("metadata", {}).get("labels")
        # JSON Patch (RFC 6902). Si el Pod no trae labels, hay que crear el mapa entero.
        if etiquetas is None:
            parche = [{"op": "add", "path": "/metadata/labels",
                       "value": {ETIQUETA: VALOR}}]
        else:
            parche = [{"op": "add", "path": "/metadata/labels/" + ETIQUETA,
                       "value": VALOR}]
        respuesta = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": peticion.get("uid"),      # DEBE ser el uid de la peticion
                "allowed": True,
                "patchType": "JSONPatch",
                "patch": base64.b64encode(json.dumps(parche).encode()).decode(),
            },
        }
        cuerpo = json.dumps(respuesta).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)
        print("mutado: %s/%s" % (peticion.get("namespace"),
                                 peticion.get("name") or "(sin nombre)"), flush=True)

    def log_message(self, formato, *args):
        pass

contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
contexto.load_cert_chain("/tls/tls.crt", "/tls/tls.key")
servidor = HTTPServer(("0.0.0.0", 8443), Manejador)
servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
print("webhook escuchando en :8443", flush=True)
servidor.serve_forever()
PYEOF

kubectl create configmap inyector-codigo -n webhooks --from-file=servidor.py
```

Tres detalles del protocolo que hay que respetar o no funciona:

- El `response.uid` **tiene que ser** el `request.uid` que llegó. Si no coincide, el API
  server descarta la respuesta.
- El parche va **codificado en base64**, y es un JSON Patch (RFC 6902), no un *strategic
  merge patch*.
- Un Pod recién creado puede no tener `metadata.labels`. `add` sobre
  `/metadata/labels/clave` falla si el mapa padre no existe: por eso el `if`.

Desplegarlo es un Deployment y un Service corrientes:

```bash
cat > inyector.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inyector
  namespace: webhooks
spec:
  replicas: 1
  selector:
    matchLabels:
      app: inyector
  template:
    metadata:
      labels:
        app: inyector
    spec:
      containers:
        - name: servidor
          image: python:3.13-slim
          command: ["python", "/codigo/servidor.py"]
          ports:
            - containerPort: 8443
          volumeMounts:
            - name: codigo
              mountPath: /codigo
            - name: tls
              mountPath: /tls
              readOnly: true
      volumes:
        - name: codigo
          configMap:
            name: inyector-codigo
        - name: tls
          secret:
            secretName: inyector-tls
---
apiVersion: v1
kind: Service
metadata:
  name: inyector
  namespace: webhooks
spec:
  selector:
    app: inyector
  ports:
    - port: 443          # el API server siempre llama al 443 por defecto
      targetPort: 8443   # donde escucha Python
EOF

kubectl apply -f inyector.yaml
kubectl rollout status deployment/inyector -n webhooks --timeout=300s
kubectl logs -n webhooks deploy/inyector
```

**Salida real de esta máquina:**

```
deployment "inyector" successfully rolled out
webhook escuchando en :8443
```

(La imagen `python:3.13-slim` es la misma del módulo 3, Paso 7. Si es la primera vez que la
descarga este clúster, tarda un poco.)

#### A1.2.3 Registrar el webhook

```bash
kubectl label namespace admision webhook-topicos=si --overwrite

CA_BUNDLE=$(base64 -w0 ca.crt)

cat > webhook.yaml <<EOF
apiVersion: admissionregistration.k8s.io/v1
kind: MutatingWebhookConfiguration
metadata:
  name: inyector-de-etiquetas
webhooks:
  - name: inyector.topicos.local      # minimo 3 segmentos, tipo dominio
    admissionReviewVersions: ["v1"]
    sideEffects: None
    failurePolicy: Ignore             # ver la nota de abajo antes de cambiarlo
    namespaceSelector:                # <-- el cinturon de seguridad
      matchLabels:
        webhook-topicos: "si"
    rules:
      - operations: ["CREATE"]
        apiGroups: [""]
        apiVersions: ["v1"]
        resources: ["pods"]
        scope: Namespaced
    clientConfig:
      service:
        name: inyector
        namespace: webhooks
        path: /mutar
        port: 443
      caBundle: ${CA_BUNDLE}
EOF

kubectl apply -f webhook.yaml
kubectl get mutatingwebhookconfiguration inyector-de-etiquetas
```

**Salida real de esta máquina:**

```
mutatingwebhookconfiguration.admissionregistration.k8s.io/inyector-de-etiquetas created
NAME                    WEBHOOKS   AGE
inyector-de-etiquetas   1          0s
```

> **Los dos campos que evitan que te quedes sin clúster.**
>
> **`namespaceSelector`.** Sin él, este webhook se consultaría para **cada Pod de cada
> namespace, incluido `kube-system`**. Si el webhook está caído (o simplemente todavía no
> arrancó) y la política es `Fail`, el API server rechaza la creación de todos los Pods del
> clúster, incluidos los del propio webhook: un punto muerto del que se sale a mano.
> Restringirlo a un namespace con una etiqueta que tú controlas es la forma barata de que
> un error tuyo no se coma el control plane.
>
> **`failurePolicy`.** La documentación define los dos valores así: *"`Ignore` means that an
> error calling the webhook is ignored and the API request is allowed to continue. `Fail`
> means that an error calling the webhook causes the admission to fail and the API request
> to be rejected."* Y aclara qué cuenta como error: errores de red, *timeouts*, respuestas
> no-2xx o mal formadas, y (solo para webhooks *mutating*) un parche indescifrable. Aquí
> usamos `Ignore` porque es un laboratorio y preferimos que un fallo nuestro no bloquee
> nada. En un webhook de **seguridad** en producción, `Ignore` sería un agujero: bastaría
> tumbar el webhook para saltarse la política. Ahí se usa `Fail`, y por eso ahí la alta
> disponibilidad del webhook deja de ser opcional. (Fuente:
> `kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/`,
> sección *Failure policy*.)

#### A1.2.4 Comprobarlo: las tres pruebas

**Prueba 1, dentro del alcance y webhook vivo:**

```bash
kubectl run probando -n admision --image=alpine:3.20 --restart=Never --command -- sleep 3600
kubectl get pod probando -n admision --show-labels
kubectl logs -n webhooks deploy/inyector --tail=5
```

**Salida real de esta máquina:**

```
NAME       READY   STATUS              RESTARTS   AGE   LABELS
probando   0/1     ContainerCreating   0          0s    inyectado-por=webhook-topicos-m4,run=probando

webhook escuchando en :8443
mutado: admision/probando
```

Ahí está: `inyectado-por=webhook-topicos-m4`. Tú nunca escribiste esa etiqueta. El `kubectl
run` solo pone `run=probando`. La otra la añadió tu servidor Python, en el milisegundo
entre que el API server recibió el Pod y lo guardó en etcd. Y el log del webhook lo
confirma desde el otro lado.

**Prueba 2, fuera del alcance:**

```bash
kubectl run fuera-de-alcance --image=alpine:3.20 --restart=Never --command -- sleep 300
kubectl get pod fuera-de-alcance --show-labels
```

**Salida real de esta máquina:**

```
NAME               READY   STATUS              RESTARTS   AGE   LABELS
fuera-de-alcance   0/1     ContainerCreating   0          0s    run=fuera-de-alcance
```

Sin etiqueta inyectada. Este Pod está en el namespace `default`, que no tiene
`webhook-topicos=si`, así que el API server ni siquiera llamó al webhook. El
`namespaceSelector` funciona.

**Prueba 3, quitar el webhook:**

```bash
kubectl delete mutatingwebhookconfiguration inyector-de-etiquetas
kubectl run despues-del-borrado -n admision --image=alpine:3.20 --restart=Never --command -- sleep 300
kubectl get pods -n admision --show-labels
```

**Salida real de esta máquina** (se quitó una línea: en la corrida de referencia el Pod
`garantizado` de A2.3 ya existía en este namespace, porque los pasos se ejecutaron en otro
orden al preparar el laboratorio; tú todavía no lo has creado):

```
NAME                  READY   STATUS              RESTARTS   AGE     LABELS
desnudo               1/1     Running             0          2m29s   run=desnudo
despues-del-borrado   0/1     ContainerCreating   0          0s      run=despues-del-borrado
probando              1/1     Running             0          9s      inyectado-por=webhook-topicos-m4,run=probando
```

El servidor Python **sigue corriendo** (no lo borraste), pero el
`MutatingWebhookConfiguration` ya no existe, así que el API server no lo llama.
`despues-del-borrado` nace limpio, mientras `probando` conserva su etiqueta: la mutación
ocurrió una sola vez, al crear el objeto, y quedó grabada en etcd. Borrar el webhook no
deshace lo ya mutado.

Ese es el punto conceptual completo: **el webhook no es un vigilante permanente, es un
interceptor en el momento de escritura.**

> **Contexto que vale la pena saber, aunque no lo usemos aquí.** Los webhooks ya no son la
> única forma de extender admission. Corre
> `kubectl api-resources --api-group=admissionregistration.k8s.io` en este mismo clúster y
> vas a ver, además de los `…webhookconfigurations`, los objetos
> `validatingadmissionpolicies` y `mutatingadmissionpolicies` (verificado en esta máquina,
> ambos en `admissionregistration.k8s.io/v1`). Son políticas escritas en CEL que se evalúan
> **dentro** del API server, sin un servidor HTTPS tuyo en el camino: menos latencia y
> ninguna de las trampas de TLS y disponibilidad que acabas de sortear. Para reglas
> declarativas simples son la opción moderna; los webhooks siguen siendo necesarios cuando
> hace falta lógica arbitraria o consultar sistemas externos.

---

## A2: cgroup v2 y Node Memory Swap (15 min)

Módulo 3, Paso 1: viste `cgroup2fs` y `0::/` dentro de un contenedor. Ahora vas a ver a
Kubernetes usar esa misma jerarquía para algo concreto y medible.

### A2.1 El sustrato

```bash
docker exec topicos-m4-control-plane stat -fc %T /sys/fs/cgroup
docker exec topicos-m4-control-plane cat /proc/swaps
```

**Salida real de esta máquina:**

```
cgroup2fs

Filename				Type		Size		Used		Priority
/swap.img                               file		8388604		0		-2
```

Dos cosas: el nodo usa **cgroup v2**, y ve el swap **del host** (`/swap.img`, 8 GiB), no
uno propio. `/proc/swaps` no está aislado por namespaces, así que el contenedor-nodo lee el
del kernel que comparte contigo. Es, otra vez, el hallazgo del módulo 3.

### A2.2 Lo que el kubelet cree que le configuraste

No confíes en tu archivo YAML: pregúntale al kubelet. El API server sabe hacer de proxy
hacia el endpoint de configuración de cada nodo.

```bash
kubectl get --raw "/api/v1/nodes/topicos-m4-control-plane/proxy/configz" \
  | python3 -m json.tool | grep -A3 -E '"failSwapOn"|"memorySwap"'
```

**Salida real de esta máquina:**

```
        "failSwapOn": false,
        "memorySwap": {
            "swapBehavior": "LimitedSwap"
        },
```

Eso es el kubelet **en ejecución** reportando su configuración efectiva, no lo que tú
escribiste. Es la diferencia entre "lo configuré" y "está configurado", y es exactamente el
tipo de comprobación que el módulo 5 (CKA) te va a pedir bajo cronómetro.

Kubernetes también expone la capacidad de swap en el estado del nodo:

```bash
kubectl get nodes -o go-template='{{range .items}}{{.metadata.name}}: {{if .status.nodeInfo.swap.capacity}}{{.status.nodeInfo.swap.capacity}}{{else}}<unknown>{{end}}{{"\n"}}{{end}}'
```

**Salida real de esta máquina:**

```
topicos-m4-control-plane: 8589930496
```

8 589 930 496 bytes = 8 GiB, el `/swap.img` de tu host visto por Kubernetes.

> **Si tu máquina no tiene swap** (`swapon --show` no imprime nada), esto sigue
> funcionando: `failSwapOn: false` es inofensivo cuando no hay swap, el clúster arranca
> igual y `configz` muestra lo mismo. Lo que cambia es el **estado**: el comando de arriba
> te va a imprimir `<unknown>`, porque, en palabras de la documentación, *"the node does not
> have swap provisioned"*. Y siguiendo la fórmula de A2.4, el `memory.swap.max` de tus
> contenedores será `0`, porque el factor `totalPodsSwapAvailable` vale cero. (Lo primero
> está documentado; lo segundo se deduce de la fórmula oficial. No se pudo verificar en
> esta máquina, que sí tiene swap.)

### A2.3 La regla: qué Pods pueden usar swap

Esta es la parte que hay que leer de la fuente y no de un blog. Con `LimitedSwap`:

> *"With `LimitedSwap`, Pods that do not fall under the Burstable QoS classification (i.e.
> `BestEffort`/`Guaranteed` QoS Pods) are prohibited from utilizing swap memory. […] In
> addition, high-priority pods are not permitted to use swap in order to ensure the memory
> they consume always resides in RAM."*
>
> Fuente: `kubernetes.io/docs/concepts/cluster-administration/swap-memory-management/`

O sea: **solo `Burstable`**. Y el razonamiento no es arbitrario: un Pod `BestEffort` no
declara nada sobre su memoria, así que no hay forma segura de calcularle una cuota; un Pod
`Guaranteed` pidió memoria exacta e inmediatamente disponible, y darle swap rompería
justamente esa promesa.

Compruébalo con el Pod `Burstable` de A1.1 y uno nuevo:

```bash
UID_POD=$(kubectl get pod desnudo -n admision -o jsonpath='{.metadata.uid}')
SLICE="/sys/fs/cgroup/kubelet.slice/kubelet-kubepods.slice/kubelet-kubepods-burstable.slice/kubelet-kubepods-burstable-pod${UID_POD//-/_}.slice"

docker exec topicos-m4-control-plane sh -c \
  "for d in $SLICE/*/; do echo \"\$d\"; echo -n '  memory.max=      '; cat \$d/memory.max; echo -n '  memory.swap.max= '; cat \$d/memory.swap.max; done"
```

**Salida real de esta máquina** (recortada: se acortaron las rutas y se dejaron los dos
contenedores del Pod):

```
…/cri-containerd-0ced74b4….scope/
  memory.max=      134217728
  memory.swap.max= 8626176
…/cri-containerd-80b6abf8….scope/
  memory.max=      max
  memory.swap.max= max
```

Antes de nada, mira la **ruta**: `kubelet-kubepods.slice /
kubelet-kubepods-burstable.slice / …-pod<uid>.slice / cri-containerd-<id>.scope`. La clase
de QoS no es una etiqueta decorativa: es un **nivel real de la jerarquía de cgroups v2** en
el disco. Y hay dos contenedores porque el segundo es el contenedor de pausa (*sandbox*)
del Pod, que no lleva límites.

El contenedor de verdad tiene `memory.max = 134217728` (128 MiB, el límite que le puso
`LimitRanger` en A1.1) y **`memory.swap.max = 8626176`**: unos 8.2 MiB de swap.

Ahora un Pod `Guaranteed`:

```bash
cat > garantizado.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: garantizado
  namespace: admision
spec:
  containers:
    - name: app
      image: alpine:3.20
      command: ["sleep", "3600"]
      resources:
        requests:      # requests == limits  =>  QoS Guaranteed
          cpu: 100m
          memory: 64Mi
        limits:
          cpu: 100m
          memory: 64Mi
EOF

kubectl apply -f garantizado.yaml
kubectl wait --for=condition=Ready pod/garantizado -n admision --timeout=120s
kubectl get pod garantizado -n admision -o jsonpath='QoS={.status.qosClass}{"\n"}'

UID_G=$(kubectl get pod garantizado -n admision -o jsonpath='{.metadata.uid}')
docker exec topicos-m4-control-plane sh -c \
  "for d in \$(find /sys/fs/cgroup -type d -path '*pod${UID_G//-/_}*' -name 'cri-containerd-*'); do echo -n 'memory.max='; cat \$d/memory.max; echo -n 'memory.swap.max='; cat \$d/memory.swap.max; done"
```

**Salida real de esta máquina:**

```
QoS=Guaranteed
memory.max=67108864
memory.swap.max=0
memory.max=max
memory.swap.max=max
```

**`memory.swap.max = 0`.** Cero, no "max". La regla de la documentación no es una
recomendación: es un número que el runtime escribió en un archivo del kernel, y lo acabas
de leer.

### A2.4 De dónde sale el 8626176

La documentación da la fórmula exacta:

> *"Swap limitation is configured as: (`containerMemoryRequest` / `nodeTotalMemory`) ×
> `totalPodsSwapAvailable`"*

Ponle los números de esta máquina:

```bash
kubectl get node topicos-m4-control-plane -o jsonpath='capacity.memory={.status.capacity.memory}{"\n"}'
docker exec topicos-m4-control-plane grep -E "MemTotal|SwapTotal" /proc/meminfo
```

**Salida real de esta máquina:**

```
capacity.memory=65246144Ki
MemTotal:       65246144 kB
SwapTotal:       8388604 kB
```

- `containerMemoryRequest` = 64 MiB = 67 108 864 B (el que puso `LimitRanger`)
- `nodeTotalMemory` = 65 246 144 KiB = 66 812 051 456 B
- `totalPodsSwapAvailable` = 8 589 930 496 B

(67 108 864 / 66 812 051 456) × 8 589 930 496 = **8 628 091 B**

Lo observado fue **8 626 176 B**. La diferencia es de 1 915 bytes, un 0.02 %, y tiene una
explicación exacta: el kernel guarda `memory.swap.max` en múltiplos de página (4 KiB), y
8 626 176 = 2 106 × 4 096 es el múltiplo de página inmediatamente **inferior** a 8 628 091.
La fórmula cuadra. (Verificado en esta máquina; tus números serán otros porque dependen de
la RAM y del swap de tu host.)

Dos consecuencias de esa fórmula, ambas en la documentación:

- Un contenedor `Burstable` cuyo `request` sea igual a su `limit` **no recibe swap**: es la
  forma de renunciar a él sin cambiar de clase de QoS.
- El scheduler **no tiene en cuenta el swap** al ubicar Pods: *"Kubernetes 1.36 does not
  support allocating Pods to nodes in a way that accounts for swap memory usage."* Los Pods
  piden `memory`, no swap. Por eso la documentación recomienda usar *taints* en los nodos
  con swap si no quieres que cualquier carga aterrice ahí.

> **Una nota que la documentación hace explícita y conviene no saltarse:** el proyecto
> Kubernetes **recomienda correr los nodos de control plane sin swap**, porque el control
> plane hospeda sobre todo Pods `Guaranteed` y el impacto de que se le vaya a disco es
> desproporcionado. Este clúster de `kind` tiene un solo nodo que hace de todo, así que
> aquí estamos haciendo justo lo que no se recomienda en producción. Es un laboratorio: la
> configuración existe para que puedas verla, no para copiarla a un clúster real.

> **Sobre `kubectl top nodes --show-swap`.** La documentación describe esa bandera para ver
> el uso de swap por nodo y por Pod, y es la forma cómoda de mirarlo. En este clúster **no
> funciona**: `kind` no instala `metrics-server`. Salida real de esta máquina:
> `error: Metrics API not available`. No es un fallo de configuración del swap, es que
> falta el componente que sirve esas métricas.

---

## Limpieza del anexo (3 min)

```bash
kind delete cluster --name topicos-m4
docker ps --filter "name=topicos-m4" --format '{{.Names}}'   # no debe imprimir nada
rm -rf ~/lab-k8s ~/lab-webhook
```

**Salida real de esta máquina:**

```
Deleting cluster "topicos-m4" ...
Deleted nodes: ["topicos-m4-control-plane"]
```

---

## Para profundizar (anexo)

Verificado contra la documentación oficial el **20 de agosto de 2026** (Kubernetes 1.36).

**Node Memory Swap: en qué etapa está.** El *feature gate* `NodeSwap` fue **Alpha en
1.22–1.27**, **Beta apagado por defecto en 1.28–1.29**, **Beta encendido por defecto en
1.30–1.33** y está en **GA desde 1.34**, sin versión de retiro anunciada. En un clúster
1.36 no hay que declarar ese gate. Lo que sí hay que configurar, siempre, son
`failSwapOn: false` y `memorySwap.swapBehavior`, porque el comportamiento por defecto sigue
siendo `NoSwap`. (Fuente:
`kubernetes.io/docs/reference/command-line-tools-reference/feature-gates/`, fila
`NodeSwap`; y `kubernetes.io/docs/concepts/cluster-administration/swap-memory-management/`.)

**LimitedSwap: la regla completa.** Solo los Pods `Burstable` pueden usar swap; los
`BestEffort` y `Guaranteed` lo tienen prohibido, igual que los Pods de prioridad alta. El
límite por contenedor es `(containerMemoryRequest / nodeTotalMemory) ×
totalPodsSwapAvailable`. Un contenedor `Burstable` con `requests` igual a `limits` renuncia
al swap. El scheduler de 1.36 **no** considera el swap al ubicar Pods. El proyecto
recomienda swap cifrado, en disco dedicado, y nodos de control plane **sin** swap. (Fuente:
`kubernetes.io/docs/concepts/cluster-administration/swap-memory-management/`.)

**Admission: qué está encendido de fábrica.** Para Kubernetes 1.36 los plugins habilitados
por defecto son: `CertificateApproval`, `CertificateSigning`,
`CertificateSubjectRestriction`, `DefaultIngressClass`, `DefaultStorageClass`,
`DefaultTolerationSeconds`, `LimitRanger`, `MutatingAdmissionWebhook`,
`NamespaceLifecycle`, `PersistentVolumeClaimResize`, `PodSecurity`, `Priority`,
`ResourceQuota`, `RuntimeClass`, `ServiceAccount`, `StorageObjectInUseProtection`,
`TaintNodesByCondition`, `ValidatingAdmissionPolicy` y `ValidatingAdmissionWebhook`. Los
controladores de admission están compilados dentro del binario `kube-apiserver` y solo un
administrador del clúster puede configurarlos. (Fuente:
`kubernetes.io/docs/reference/access-authn-authz/admission-controllers/`.)

**Reinvocación: por qué el orden de los mutating es un problema real.** Un webhook
*mutating* puede añadir estructura nueva a un objeto (por ejemplo, un contenedor a un Pod)
sobre la que otros plugins que ya corrieron tendrían opinión. Por eso los plugins *mutating*
compilados **se vuelven a ejecutar** si un webhook modificó el objeto, y los webhooks pueden
pedir lo mismo con `reinvocationPolicy`, que admite `Never` (el predeterminado) o
`IfNeeded`. La documentación también advierte que un webhook que necesite ver el estado
**final** del objeto debe ser *validating*, no *mutating*, porque un objeto puede seguir
cambiando después de que un webhook *mutating* lo vio. (Fuente:
`kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/`.)

**Cómo conecta el anexo con el módulo 7 (CKS).** El `failurePolicy` de A1.2.3 es la decisión
central de todo webhook de política de seguridad: con `Ignore`, tumbar el webhook basta para
saltarse la política. Ahí ya no es un detalle de laboratorio.
