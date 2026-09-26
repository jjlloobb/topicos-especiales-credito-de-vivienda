# Laboratorio 2 (Módulo 5) – Operar el clúster: scheduling, almacenamiento, exposición, RBAC y diagnóstico

**Módulo 5 · sesión 7 · en clase · 120–140 minutos.** En el Laboratorio 1 construiste un
clúster. Hoy lo operas: decides dónde corre cada Pod, le das disco, lo actualizas sin
tumbarlo, lo expones al mundo, le pones permisos y lo diagnosticas cuando se rompe.

| Bloque | Paso | Tiempo | ¿Se puede dejar para casa? |
|---|---|---|---|
| Un clúster `kind` de 3 nodos | 0 | ~8 min | No |
| Taints, tolerations y afinidad | 1 | ~15 min | No |
| PV, PVC y aprovisionamiento dinámico | 2 | ~15 min | No |
| Deployment frente a StatefulSet | 3 | ~15 min | No |
| Actualizar y revertir un Deployment | 4 | ~15 min | No |
| NodePort frente a `port-forward` | 5 | ~12 min | No |
| `metrics-server`, `kubectl top` y HPA | 6 | ~15 min | No |
| Diagnosticar un contenedor que se cae | 7 | ~8 min | No |
| RBAC: un ServiceAccount y una persona | 8 | ~20 min | No |
| Ingress frente a Gateway API | 9 | ~20 min | En parte |
| Observabilidad: Helm y Grafana | 10 | ~12 min | **Sí** |
| **Anexo**: cambiar de CNI (kindnet, Calico, Cilium) | A1–A3 | ~35 min | **Sí: no se hace en clase** |

> La idea central de esta sesión cabe en una frase: **administrar Kubernetes es decidir, y
> cada decisión deja una huella verificable en la terminal.** Dónde corre un Pod, qué disco
> usa, quién puede tocarlo, por dónde entra el tráfico: nada de eso «pasa». Alguien lo
> decidió, y hoy ese alguien eres tú.

---

## Objetivo

Al terminar vas a poder responder, señalando evidencia en tu terminal:

1. ¿Por qué un Pod queda `Pending` y qué frase exacta distingue «falta un taint tolerado»
   de «no hay nodo que cumpla la afinidad»?
2. ¿Por qué un PVC recién creado no tiene PV, y qué evento te lo dice?
3. ¿Qué hace un StatefulSet que un Deployment con volumen no puede hacer?
4. ¿Qué diferencia real hay entre `NodePort` y `kubectl port-forward`, más allá del puerto?
5. Si `kubectl auth can-i --as=…` dice `no`, pero al probar con el token la operación
   funciona, ¿quién mintió?
6. ¿Qué hace un Ingress que un Gateway hace mejor, y qué objeto separa los papeles?

**Requisito:** módulo 4 completo y Laboratorio 1 de este módulo.

**Entorno:** Linux con Docker Engine activo, `kind`, `kubectl` y `helm`. Todo se crea y se
borra en la sesión. Cuenta con **6 GiB de RAM libres** (8 GiB si haces el Paso 10).

---

## Paso 0: Un clúster de 3 nodos (8 min)

Un solo nodo no sirve para hoy: para hablar de scheduling hacen falta nodos entre los que
elegir.

```bash
cat > kind-cka.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: cka
nodes:
- role: control-plane
  image: kindest/node:v1.37.0
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 8080
    protocol: TCP
  - containerPort: 443
    hostPort: 9443
    protocol: TCP
- role: worker
  image: kindest/node:v1.37.0
- role: worker
  image: kindest/node:v1.37.0
EOF

kind create cluster --config kind-cka.yaml
```

Tres decisiones dentro de ese archivo, y las tres se usan más adelante:

- **`image: kindest/node:v1.37.0`** fija la versión. Es la misma a la que actualizaste el
  clúster de kubeadm en el Laboratorio 1.
- **`node-labels: "ingress-ready=true"`** etiqueta el control plane. El Paso 9 la usa para
  colocar ahí el controlador de Ingress.
- **`extraPortMappings`** publica los puertos 80 y 443 del nodo control-plane en los puertos
  8080 y 9443 de tu portátil. Sin esto no podrías abrir el sitio web del Paso 9 en tu
  navegador.

**Salida real de esta máquina** (recortada):

```
 ✓ Preparing nodes 📦 📦 📦 
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
 ✓ Joining worker nodes 🚜
Set kubectl context to "kind-cka"
```

> **Si te sale este error, léelo, no lo pelees:**
>
> ```
> docker: Error response from daemon: failed to set up container networking:
> driver failed programming external connectivity on endpoint cka-control-plane:
> failed to bind host port 0.0.0.0:8443/tcp: address already in use
> ```
>
> Significa que **otro programa de tu portátil ya usa ese puerto**. No es un problema de
> Kubernetes. Averigua quién y elige otro `hostPort`:
>
> ```bash
> ss -ltnp | grep :8443
> ```
>
> En la máquina donde se verificó este laboratorio el 8443 estaba ocupado, y por eso el
> archivo de arriba usa **9443**. Cambia el número, no el diseño.

```bash
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl get nodes -o wide
```

**Salida real de esta máquina:**

```
NAME                STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE                       KERNEL-VERSION            CONTAINER-RUNTIME
cka-control-plane   Ready    control-plane   17s   v1.37.0   172.18.0.4    <none>        Debian GNU/Linux 13 (trixie)   6.17.0-1032-oem (amd64)   containerd://2.3.4
cka-worker          Ready    <none>          6s    v1.37.0   172.18.0.5    <none>        Debian GNU/Linux 13 (trixie)   6.17.0-1032-oem (amd64)   containerd://2.3.4
cka-worker2         Ready    <none>          6s    v1.37.0   172.18.0.3    <none>        Debian GNU/Linux 13 (trixie)   6.17.0-1032-oem (amd64)   containerd://2.3.4
```

> **Compara con el Laboratorio 1.** Allí `KERNEL-VERSION` era `6.8.0-138-generic`, distinto
> al de tu portátil, porque cada nodo era una VM con su kernel. Aquí los tres nodos dicen
> `6.17.0-1032-oem`: **el kernel de tu portátil**, porque son contenedores. Por eso `kind`
> sirve para aprender scheduling, almacenamiento y RBAC (lo de hoy), y no sirve para
> practicar `modprobe` ni instalación de nodos (lo de ayer).

Comprueba también la política de *version skew* en acción:

```bash
kubectl version
```

**Salida real de esta máquina:**

```
Client Version: v1.36.1
Kustomize Version: v5.8.1
Server Version: v1.37.0
```

Cliente 1.36.1 contra servidor 1.37.0: **una versión menor de diferencia, soportada**. Si tu
`kubectl` fuera 1.34 contra un API server 1.37, algunos comandos podrían comportarse raro.

---

## Paso 1: Taints, tolerations y afinidad (15 min)

### 1.1 La marca que ya está puesta

```bash
kubectl get nodes -o custom-columns='NODO:.metadata.name,TAINTS:.spec.taints[*].key'
```

**Salida real de esta máquina:**

```
NODO                TAINTS
cka-control-plane   node-role.kubernetes.io/control-plane
cka-worker          <none>
cka-worker2         <none>
```

Un **taint** es una marca que el nodo se pone a sí mismo para repeler Pods. Una
**toleration** es el permiso que un Pod lleva para ignorar esa marca. El control plane
viene con el taint puesto de fábrica, y por una razón sensata: si el API server y tus
aplicaciones compiten por la misma memoria, pierdes el clúster entero, no una aplicación.

### 1.2 Un Deployment normal: nunca toca el control plane

```bash
kubectl create deployment fuera --image=nginx:1.29-alpine --replicas=4
kubectl rollout status deployment/fuera --timeout=180s
kubectl get pods -l app=fuera -o custom-columns='POD:.metadata.name,NODO:.spec.nodeName'
```

**Salida real de esta máquina:**

```
deployment.apps/fuera created
deployment "fuera" successfully rolled out
POD                     NODO
fuera-fbcc68dff-678sk   cka-worker
fuera-fbcc68dff-8xn6m   cka-worker2
fuera-fbcc68dff-tqqkh   cka-worker2
fuera-fbcc68dff-vh4d6   cka-worker
```

Cuatro réplicas repartidas entre los **dos** workers. Cero en el control plane. Nadie
configuró eso: es el taint del 1.1 haciendo su trabajo.

### 1.3 Un Deployment que sí entra al control plane

Para aterrizar **dentro** del control plane hacen falta **dos** cosas distintas, y
confundirlas es el error clásico:

- una **toleration**, que da permiso para ignorar el taint;
- una **nodeAffinity**, que obliga a elegir ese nodo.

La toleration sola no te lleva ahí, solo te deja. La afinidad sola no puede, porque el
taint la bloquea.

```bash
cat > dentro.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dentro
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dentro
  template:
    metadata:
      labels:
        app: dentro
    spec:
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        operator: Exists
        effect: NoSchedule
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: node-role.kubernetes.io/control-plane
                operator: Exists
      containers:
      - name: nginx
        image: nginx:1.29-alpine
EOF

kubectl apply -f dentro.yaml
kubectl rollout status deployment/dentro --timeout=180s
kubectl get pods -l app=dentro -o custom-columns='POD:.metadata.name,NODO:.spec.nodeName'
```

**Salida real de esta máquina:**

```
deployment.apps/dentro created
deployment "dentro" successfully rolled out
POD                       NODO
dentro-7b86864966-wdl2c   cka-control-plane
```

**Dentro del control plane.** Así es como llegan ahí los agentes de monitoreo, los
controladores de Ingress y los CNIs.

### 1.4 La demostración de que hacen falta las dos

Quita la toleration y deja solo la afinidad:

```bash
sed '/tolerations:/,/effect: NoSchedule/d; s/name: dentro/name: sin-toleracion/; s/app: dentro/app: sin-toleracion/' dentro.yaml > sin-toleracion.yaml
kubectl apply -f sin-toleracion.yaml
kubectl get pods -l app=sin-toleracion
```

**Salida real de esta máquina:**

```
deployment.apps/sin-toleracion created
NAME                              READY   STATUS    RESTARTS   AGE
sin-toleracion-5466dfc8f8-shbjx   0/1     Pending   0          12s
```

`Pending`. **`Pending` no es un error: es una decisión del scheduler, y el scheduler la
explica.** Pregúntale:

```bash
kubectl describe pod -l app=sin-toleracion | grep -A6 "Events:"
```

**Salida real de esta máquina:**

```
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  12s   default-scheduler  0/3 nodes are available: 1 node(s) had untolerated taint(s), 2 node(s) didn't match Pod's node affinity/selector. preemption: 0/3 nodes are available: 3 Preemption is not helpful for scheduling.
```

Léelo como un informe forense, porque lo es:

- **`1 node(s) had untolerated taint(s)`** = el control plane, que sí cumple la afinidad,
  pero repele al Pod porque no lleva toleration.
- **`2 node(s) didn't match Pod's node affinity/selector`** = los dos workers, que
  aceptarían al Pod pero no cumplen la afinidad.
- **`preemption: … is not helpful`** = el scheduler evaluó desalojar Pods de menor prioridad
  y concluyó que tampoco resolvería nada.

Tres nodos, tres motivos, cero adivinanza. **En el examen CKA, este mensaje resuelve el
problema; no lo leas por encima.**

```bash
kubectl delete deployment sin-toleracion
```

---

## Paso 2: PV, PVC y aprovisionamiento dinámico (15 min)

### 2.1 Quién crea el disco

```bash
kubectl get storageclass
kubectl get storageclass standard -o jsonpath='{"provisioner: "}{.provisioner}{"\nvolumeBindingMode: "}{.volumeBindingMode}{"\nreclaimPolicy: "}{.reclaimPolicy}{"\n"}'
```

**Salida real de esta máquina:**

```
NAME                 PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
standard (default)   rancher.io/local-path   Delete          WaitForFirstConsumer   false                  2m32s

provisioner: rancher.io/local-path
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
```

Tres campos que gobiernan todo lo que sigue:

| Campo | Qué significa aquí |
|---|---|
| `provisioner: rancher.io/local-path` | quién fabrica el disco: en `kind`, un directorio del nodo |
| `volumeBindingMode: WaitForFirstConsumer` | **no** crea el disco hasta saber en qué nodo correrá el Pod |
| `reclaimPolicy: Delete` | al borrar el PVC, el PV y los datos se borran |

### 2.2 Un PVC solo, sin Pod

```bash
kubectl create -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: datos
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 1Gi
EOF

kubectl get pvc datos
kubectl get pv
```

**Salida real de esta máquina:**

```
persistentvolumeclaim/datos created
NAME    STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
datos   Pending                                      standard       <unset>                 6s
No resources found
```

`Pending`, y **no existe ningún PV**. Otra vez: no es un fallo. Pregunta:

```bash
kubectl describe pvc datos | grep -A4 "Events:"
```

**Salida real de esta máquina:**

```
Events:
  Type    Reason                Age              From                         Message
  ----    ------                ----             ----                         -------
  Normal  WaitForFirstConsumer  6s (x2 over 6s)  persistentvolume-controller  waiting for first consumer to be created before binding
```

«**waiting for first consumer**». Un disco local solo sirve en **un** nodo. Si Kubernetes lo
creara ahora, tendría que elegir nodo a ciegas y podría clavar el Pod en el nodo equivocado
para siempre. Así que espera a que el scheduler decida, y **entonces** crea el disco ahí.

### 2.3 El Pod que desbloquea el volumen

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: escritor
spec:
  containers:
  - name: app
    image: busybox:1.37
    command: ["sh","-c","echo \"escrito el $(date -u) por $(hostname)\" >> /datos/registro.txt; sleep 3600"]
    volumeMounts:
    - name: vol
      mountPath: /datos
  volumes:
  - name: vol
    persistentVolumeClaim:
      claimName: datos
EOF

kubectl wait --for=condition=Ready pod/escritor --timeout=180s
kubectl get pvc datos
kubectl get pv
```

**Salida real de esta máquina:**

```
pod/escritor created
pod/escritor condition met
NAME    STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
datos   Bound    pvc-dbfa98ff-3333-442a-a329-43a9b0e827e2   1Gi        RWO            standard       <unset>                 22s
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM           STORAGECLASS   VOLUMEATTRIBUTESCLASS   REASON   AGE
pvc-dbfa98ff-3333-442a-a329-43a9b0e827e2   1Gi        RWO            Delete           Bound    default/datos   standard       <unset>                          4s
```

Fíjate en las edades: el PVC lleva 22 segundos, **el PV lleva 4**. El disco nació cuando
apareció el Pod, no cuando pediste el disco. Ahí está `WaitForFirstConsumer`, medido.

Y mira dónde nació:

```bash
kubectl exec escritor -- cat /datos/registro.txt
kubectl get pod escritor -o jsonpath='{.spec.nodeName}{"\n"}'
kubectl get pv -o jsonpath='{.items[0].spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]}{"\n"}'
```

**Salida real de esta máquina:**

```
escrito el Mon Aug 31 14:51:59 UTC 2026 por escritor
cka-worker2
cka-worker2
```

El Pod está en `cka-worker2` y **el PV lleva una `nodeAffinity` que lo clava a
`cka-worker2`**. Ese es el precio del almacenamiento local: el dato tiene domicilio fijo.

### 2.4 El dato sobrevive al Pod

```bash
kubectl delete pod escritor
kubectl get pvc datos
```

**Salida real de esta máquina:**

```
pod "escritor" deleted from default namespace
NAME    STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
datos   Bound    pvc-dbfa98ff-3333-442a-a329-43a9b0e827e2   1Gi        RWO            standard       <unset>                 61s
```

El Pod se fue; el PVC y el PV siguen `Bound`. Ahora monta el mismo PVC en un Pod nuevo:

```bash
kubectl run lector --image=busybox:1.37 --restart=Never --overrides='{"spec":{"containers":[{"name":"lector","image":"busybox:1.37","command":["sleep","3600"],"volumeMounts":[{"name":"vol","mountPath":"/datos"}]}],"volumes":[{"name":"vol","persistentVolumeClaim":{"claimName":"datos"}}]}}'
kubectl wait --for=condition=Ready pod/lector --timeout=180s
kubectl exec lector -- cat /datos/registro.txt
kubectl get pod lector -o jsonpath='{.spec.nodeName}{"\n"}'
```

**Salida real de esta máquina:**

```
pod/lector condition met
escrito el Mon Aug 31 14:51:59 UTC 2026 por escritor
cka-worker2
```

**El texto lo escribió `escritor`, que ya no existe, y lo está leyendo `lector`.** Y el
Pod nuevo aterrizó en `cka-worker2`: no por casualidad, sino porque la `nodeAffinity` del PV
obligó al scheduler.

```bash
kubectl delete pod lector
```

---

## Paso 3: Deployment frente a StatefulSet (15 min)

Un Deployment con un PVC funciona… hasta que necesitas **tres** réplicas, cada una con **su
propio** disco y **su propio** nombre. Eso es un StatefulSet.

```bash
cat > sts.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: cola
spec:
  clusterIP: None
  selector:
    app: cola
  ports:
  - port: 80
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: cola
spec:
  serviceName: cola
  replicas: 3
  selector:
    matchLabels:
      app: cola
  template:
    metadata:
      labels:
        app: cola
    spec:
      containers:
      - name: app
        image: busybox:1.37
        command: ["sh","-c","echo \"soy $(hostname)\" > /datos/identidad.txt; sleep 3600"]
        volumeMounts:
        - name: datos
          mountPath: /datos
  volumeClaimTemplates:
  - metadata:
      name: datos
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
EOF

kubectl apply -f sts.yaml
kubectl rollout status statefulset/cola --timeout=300s
```

**Salida real de esta máquina:**

```
service/cola created
statefulset.apps/cola created
Waiting for 3 pods to be ready...
Waiting for 2 pods to be ready...
Waiting for 1 pods to be ready...
partitioned roll out complete: 3 new pods have been updated...
```

Fíjate en que las réplicas **no** arrancan a la vez: 3, luego 2, luego 1. Un StatefulSet
crea sus Pods **en orden**, uno detrás de otro. Un Deployment los lanza todos de golpe.

```bash
kubectl get pods -l app=cola -o custom-columns='POD:.metadata.name,NODO:.spec.nodeName'
kubectl get pvc
```

**Salida real de esta máquina:**

```
POD      NODO
cola-0   cka-worker
cola-1   cka-worker2
cola-2   cka-worker2

NAME           STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
datos          Bound    pvc-dbfa98ff-3333-442a-a329-43a9b0e827e2   1Gi        RWO            standard       <unset>                 90s
datos-cola-0   Bound    pvc-25928158-e546-48b8-87da-2b574be06d6d   1Gi        RWO            standard       <unset>                 16s
datos-cola-1   Bound    pvc-2191163c-bd50-4f3a-bc18-79c015323838   1Gi        RWO            standard       <unset>                 8s
datos-cola-2   Bound    pvc-b8f0122f-9b73-410f-9c06-1aef3e33ae88   1Gi        RWO            standard       <unset>                 5s
```

Dos cosas que un Deployment no te da:

- **Nombres predecibles**: `cola-0`, `cola-1`, `cola-2`. No hay hash aleatorio.
- **Un PVC por Pod**, con nombre derivado: `datos-cola-0`, `datos-cola-1`, `datos-cola-2`.
  Eso lo genera `volumeClaimTemplates`: no es *un* volumen compartido, es *una plantilla*
  que se instancia por réplica.

```bash
for p in cola-0 cola-1 cola-2; do printf "%s -> " $p; kubectl exec $p -- cat /datos/identidad.txt; done
```

**Salida real de esta máquina:**

```
cola-0 -> soy cola-0
cola-1 -> soy cola-1
cola-2 -> soy cola-2
```

### 3.1 La prueba de identidad

```bash
kubectl delete pod cola-1
kubectl wait --for=condition=Ready pod/cola-1 --timeout=180s
kubectl get pod cola-1 -o custom-columns='POD:.metadata.name,PVC:.spec.volumes[0].persistentVolumeClaim.claimName'
```

**Salida real de esta máquina:**

```
pod "cola-1" deleted from default namespace
pod/cola-1 condition met
POD      PVC
cola-1   datos-cola-1
```

**Volvió con el mismo nombre y reclamó el mismo disco.** Ahora el contraste:

```bash
kubectl delete pod $(kubectl get pods -l app=fuera -o name | head -1 | cut -d/ -f2)
kubectl get pods -l app=fuera --no-headers -o custom-columns=':.metadata.name'
```

**Salida real de esta máquina:**

```
pod "fuera-fbcc68dff-f9rn7" deleted from default namespace
fuera-fbcc68dff-jf8dm
fuera-fbcc68dff-p7vdj
fuera-fbcc68dff-sxz48
fuera-fbcc68dff-wndg5
```

El Pod borrado (`…-f9rn7`) **no volvió**: nació otro, con otro nombre. Para un Deployment,
las réplicas son intercambiables. Para un StatefulSet, cada una es alguien.

### 3.2 Y por eso el DNS funciona distinto

```bash
kubectl run dnstest --image=busybox:1.37 --restart=Never --rm -i -- \
  nslookup cola-0.cola.default.svc.cluster.local
```

**Salida real de esta máquina** (recortada):

```
Name:	cola-0.cola.default.svc.cluster.local
Address: 10.244.1.11
```

**Un nombre DNS por réplica.** Eso es lo que hace posible que una base de datos replicada
sepa quién es el primario y a quién replicar. Con un Deployment solo tendrías el nombre del
Service y un Pod cualquiera detrás.

| | Deployment | StatefulSet |
|---|---|---|
| Nombres | aleatorios (`web-7fbc…-dch5h`) | ordinales (`cola-0`) |
| Creación | todas a la vez | en orden, 0 → 1 → 2 |
| Volumen | uno compartido, o ninguno | uno por réplica (`volumeClaimTemplates`) |
| Al recrear un Pod | nace otro distinto | vuelve **el mismo**, con su disco |
| DNS | el del Service | uno por réplica |
| Se usa para | web, API sin estado | bases de datos, colas, quórum |

---

## Paso 4: Actualizar y revertir un Deployment (15 min)

### 4.1 Una actualización que sale bien

```bash
kubectl get deploy fuera -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl rollout history deployment/fuera
kubectl set image deployment/fuera nginx=nginx:1.30-alpine
kubectl rollout status deployment/fuera --timeout=180s
kubectl get rs -l app=fuera -o custom-columns='RS:.metadata.name,DESEADO:.spec.replicas,LISTO:.status.readyReplicas,IMAGEN:.spec.template.spec.containers[0].image'
```

**Salida real de esta máquina** (recortada):

```
nginx:1.29-alpine
REVISION  CHANGE-CAUSE
1         <none>

deployment.apps/fuera image updated
Waiting for deployment "fuera" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "fuera" rollout to finish: 1 old replicas are pending termination...
deployment "fuera" successfully rolled out

RS                 DESEADO   LISTO    IMAGEN
fuera-6fc4db4b5c   4         4        nginx:1.30-alpine
fuera-fbcc68dff    0         <none>   nginx:1.29-alpine
```

**El ReplicaSet viejo no se borra: se deja en 0 réplicas.** Ese es el mecanismo entero del
rollback: la vuelta atrás no reconstruye nada, solo vuelve a subir un ReplicaSet que ya
existe.

### 4.2 Una actualización que sale mal

```bash
kubectl set image deployment/fuera nginx=nginx:no-existe-999
kubectl get pods -l app=fuera
```

**Salida real de esta máquina:**

```
deployment.apps/fuera image updated
NAME                     READY   STATUS             RESTARTS   AGE
fuera-696865dbc7-4kgpb   0/1     ImagePullBackOff   0          25s
fuera-696865dbc7-zpxwv   0/1     ImagePullBackOff   0          25s
fuera-6fc4db4b5c-8z6pz   1/1     Running            0          34s
fuera-6fc4db4b5c-msl7l   1/1     Running            0          39s
fuera-6fc4db4b5c-xgt9m   1/1     Running            0          39s
```

**Este es el momento más importante del paso.** Dos Pods nuevos rotos, y **tres viejos
todavía sirviendo tráfico**. La estrategia `RollingUpdate` por defecto (`maxUnavailable: 25%`,
`maxSurge: 25%`) no derriba lo que funciona hasta que lo nuevo está listo. **Tu sitio nunca
se cayó.**

```bash
kubectl rollout status deployment/fuera --timeout=20s
echo "código de salida: $?"
```

**Salida real de esta máquina:**

```
Waiting for deployment "fuera" rollout to finish: 2 out of 4 new replicas have been updated...
error: timed out waiting for the condition
código de salida: 1
```

`rollout status` devuelve **1**. Ese código de salida es lo que un pipeline de CI/CD usa
para decidir que hay que revertir.

### 4.3 Revertir

```bash
kubectl rollout history deployment/fuera
kubectl rollout undo deployment/fuera
kubectl rollout status deployment/fuera --timeout=180s
kubectl get deploy fuera -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

**Salida real de esta máquina:**

```
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
3         <none>

deployment.apps/fuera rolled back
deployment "fuera" successfully rolled out
nginx:1.30-alpine
```

`undo` sin argumentos vuelve **una** revisión atrás: de la rota (3) a la anterior (2), que
era `1.30-alpine`. Para elegir destino:

```bash
kubectl rollout undo deployment/fuera --to-revision=1
kubectl rollout status deployment/fuera --timeout=180s
kubectl get deploy fuera -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl rollout history deployment/fuera
```

**Salida real de esta máquina:**

```
deployment.apps/fuera rolled back
deployment "fuera" successfully rolled out
nginx:1.29-alpine
REVISION  CHANGE-CAUSE
3         <none>
4         <none>
5         <none>
```

Volviste a `1.29-alpine`, la revisión 1… **y el historial ahora empieza en 3 y termina en
5.** Revertir **no** retrocede el contador: crea una revisión nueva con contenido viejo. Es
un `git revert`, no un `git reset`. Si esto te sorprende en el examen, pierdes minutos.

> **`CHANGE-CAUSE` sale `<none>` porque nadie lo escribió.** Ponlo tú y tu historial se
> vuelve legible:
> ```bash
> kubectl annotate deployment/fuera kubernetes.io/change-cause="imagen a 1.30 por CVE-XXXX" --overwrite
> ```

---

## Paso 5: NodePort frente a `port-forward` (12 min)

Las dos exponen un Service. No son alternativas: son herramientas para problemas distintos.

### 5.1 NodePort

```bash
kubectl expose deployment fuera --type=NodePort --port=80 --name=fuera-nodeport
kubectl get svc fuera-nodeport
```

**Salida real de esta máquina:**

```
service/fuera-nodeport exposed
NAME             TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
fuera-nodeport   NodePort   10.96.203.52   <none>        80:31393/TCP   0s
```

`80:31393/TCP`: el puerto 80 del Service se publica en el **31393 de todos los nodos**.

> **Espera a que haya endpoints antes de probar.** Si lanzas el `curl` en el mismo segundo
> en que creas el Service, obtendrás `000` y creerás que algo está roto. `kube-proxy`
> necesita un momento para programar las reglas:
> ```bash
> kubectl get endpointslices -l kubernetes.io/service-name=fuera-nodeport
> ```

```bash
NP=$(kubectl get svc fuera-nodeport -o jsonpath='{.spec.ports[0].nodePort}')
for n in cka-control-plane cka-worker cka-worker2; do
  ip=$(kubectl get node $n -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
  printf "%-20s %-12s -> " "$n" "$ip"
  docker exec cka-control-plane curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 "http://$ip:$NP"
done
```

**Salida real de esta máquina:**

```
cka-control-plane    172.18.0.4   -> 200
cka-worker           172.18.0.5   -> 200
cka-worker2          172.18.0.3   -> 200
```

**Los tres nodos responden 200, incluido el control plane, que no tiene ni un Pod de
`fuera`.** Eso es `kube-proxy`: el puerto está abierto en *todos* los nodos y el tráfico se
reenvía a donde sí haya un Pod.

Y como los nodos de `kind` son contenedores en una red Docker alcanzable desde tu portátil:

```bash
IP=$(kubectl get node cka-worker -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
curl -s -o /dev/null -w "$IP:$NP -> HTTP %{http_code}\n" --max-time 5 "http://$IP:$NP"
```

**Salida real de esta máquina:**

```
172.18.0.5:31393 -> HTTP 200
```

### 5.2 `port-forward`

```bash
kubectl port-forward svc/fuera-nodeport 18080:80 &
curl -s -o /dev/null -w 'localhost:18080 -> HTTP %{http_code}\n' --max-time 5 http://127.0.0.1:18080
ss -ltn 'sport = :18080'
```

**Salida real de esta máquina:**

```
localhost:18080 -> HTTP 200
State  Recv-Q Send-Q Local Address:Port  Peer Address:Port
LISTEN 0      4096       127.0.0.1:18080      0.0.0.0:*          
LISTEN 0      4096           [::1]:18080         [::]:*          
```

**Mira las direcciones de escucha: `127.0.0.1` y `[::1]`.** Solo tu propia máquina. Ni
siquiera otra IP de tu propio portátil:

```bash
HOSTIP=$(ip -4 -o addr show $(ip route show default | awk '{print $5}' | head -1) | awk '{print $4}' | cut -d/ -f1)
curl -s -o /dev/null -w "$HOSTIP:18080 -> HTTP %{http_code}\n" --max-time 4 "http://$HOSTIP:18080"
```

**Salida real de esta máquina:**

```
192.168.10.11:18080 -> HTTP 000
```

`000` significa que la conexión ni siquiera se estableció. Y ahora la diferencia decisiva:

```bash
kill %1
curl -s -o /dev/null -w 'HTTP %{http_code}\n' --max-time 4 http://127.0.0.1:18080
```

**Salida real de esta máquina:**

```
HTTP 000
```

**Mataste el proceso y el acceso murió con él.**

| | NodePort | `kubectl port-forward` |
|---|---|---|
| Vive en | el clúster, como objeto | tu terminal, como proceso |
| Escucha en | todos los nodos | solo `127.0.0.1` |
| Sobrevive a cerrar la terminal | sí | **no** |
| Necesita permisos RBAC | sobre Services | sobre `pods/portforward` |
| Para qué sirve | exponer de verdad | depurar, entrar a algo que no quieres publicar |

> **Regla práctica:** si otra persona tiene que poder llegar, es un Service. Si solo tú,
> durante cinco minutos y para mirar por dentro, es `port-forward`. Publicar una base de
> datos con NodePort «para depurar» es cómo se filtran las bases de datos.

---

## Paso 6: `metrics-server`, `kubectl top` y el escalado automático (15 min)

### 6.1 Kubernetes no mide nada por defecto

```bash
kubectl top nodes
```

**Salida real de esta máquina:**

```
error: Metrics API not available
```

`kubectl top` no lee de los nodos: lee de la **Metrics API**, que **no viene instalada**.

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system get deploy metrics-server
```

**Salida real de esta máquina** (recortada):

```
service/metrics-server created
deployment.apps/metrics-server created
apiservice.apiregistration.k8s.io/v1beta1.metrics.k8s.io created

NAME             READY   UP-TO-DATE   AVAILABLE   AGE
metrics-server   0/1     1            0           40s
```

`0/1`. **No arranca.** Diagnostica como en el Laboratorio 1: al log.

```bash
kubectl -n kube-system logs deploy/metrics-server --tail=5
```

**Salida real de esta máquina:**

```
E0831 14:55:28.510728       1 scraper.go:149] "Failed to scrape node" err="Get \"https://172.18.0.4:10250/metrics/resource\": tls: failed to verify certificate: x509: cannot validate certificate for 172.18.0.4 because it doesn't contain any IP SANs" node="cka-control-plane"
I0831 14:55:29.118284       1 server.go:192] "Failed probe" probe="metric-storage-ready" err="no metrics to serve"
```

El error es exacto: **el certificado del kubelet no incluye la IP como SAN**, así que
`metrics-server` se niega a hablarle. Es correcto que se niegue: eso es TLS haciendo su
trabajo. En un clúster de laboratorio se acepta el riesgo explícitamente:

```bash
kubectl -n kube-system patch deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deployment/metrics-server --timeout=240s
```

> **`--kubelet-insecure-tls` NO se pone en producción.** En un clúster real se arregla la
> causa: que los certificados del kubelet los firme la CA del clúster (`serverTLSBootstrap:
> true` en la configuración del kubelet, más la aprobación de los CSR). Aquí lo usamos
> porque el objetivo es aprender `top`, no montar una PKI. Que quede escrito.

```bash
kubectl top nodes
kubectl top pods -A --sort-by=memory | head -8
```

**Salida real de esta máquina:**

```
NAME                CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
cka-control-plane   136m         0%       688Mi           1%          
cka-worker          121m         0%       239Mi           0%          
cka-worker2         37m          0%       253Mi           0%          

NAMESPACE     NAME                                        CPU(cores)   MEMORY(bytes)   
kube-system   kube-apiserver-cka-control-plane            42m          267Mi           
kube-system   kube-controller-manager-cka-control-plane   17m          61Mi            
kube-system   kube-scheduler-cka-control-plane            10m          26Mi            
default       fuera-fbcc68dff-p7vdj                       0m           18Mi            
default       dentro-7b86864966-wdl2c                     0m           18Mi            
```

Lee la tabla como un administrador: el control plane consume **688 MiB**, casi tres veces
más que un worker, y el `kube-apiserver` solo ya son 267 MiB. Ahora entiendes por qué el
control plane viene con un taint.

> **`kubectl top` es consumo *actual*, no *reservas*.** Un `MEMORY(%)` bajo no significa que
> haya sitio: el scheduler decide con `requests`, no con el uso real. Los dos números se
> miran juntos.

### 6.2 Escalado automático (HPA)

`kubectl top` acaba de habilitar algo más: sin Metrics API no hay HPA.

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cpu-app
spec:
  replicas: 1
  selector: { matchLabels: { app: cpu-app } }
  template:
    metadata: { labels: { app: cpu-app } }
    spec:
      containers:
      - name: app
        image: registry.k8s.io/hpa-example
        ports: [{ containerPort: 80 }]
        resources:
          requests: { cpu: "50m" }
          limits:   { cpu: "200m" }
EOF

kubectl expose deployment cpu-app --port=80
kubectl rollout status deploy/cpu-app --timeout=300s
kubectl autoscale deployment cpu-app --cpu=50% --min=1 --max=6
kubectl get hpa cpu-app
```

**Salida real de esta máquina:**

```
horizontalpodautoscaler.autoscaling/cpu-app autoscaled
NAME      REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
cpu-app   Deployment/cpu-app   cpu: 2%/50%   1         6         1          45s
```

> **`requests: cpu: 50m` no es decorativo.** El HPA calcula el porcentaje **contra el
> `request`**, no contra la capacidad del nodo. Sin `requests`, el HPA no tiene
> denominador y no funciona. Es el fallo número uno con HPA.

Genera carga y observa:

```bash
kubectl run generador --image=busybox:1.37 --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://cpu-app > /dev/null; done"

for i in $(seq 1 8); do kubectl get hpa cpu-app --no-headers; sleep 30; done
```

**Salida real de esta máquina:**

```
cpu-app   Deployment/cpu-app   cpu: 2%/50%     1   6   1   0s
cpu-app   Deployment/cpu-app   cpu: 44%/50%    1   6   1   30s
cpu-app   Deployment/cpu-app   cpu: 402%/50%   1   6   4   60s
cpu-app   Deployment/cpu-app   cpu: 70%/50%    1   6   6   90s
cpu-app   Deployment/cpu-app   cpu: 79%/50%    1   6   6   2m
cpu-app   Deployment/cpu-app   cpu: 74%/50%    1   6   6   3m
cpu-app   Deployment/cpu-app   cpu: 83%/50%    1   6   6   3m30s
cpu-app   Deployment/cpu-app   cpu: 70%/50%    1   6   6   4m
```

La historia completa en ocho líneas: **2% → 44% → 402%** de CPU, y las réplicas **1 → 4 →
6**, tope del `--max`. El HPA no sube de una en una: calcula cuántas necesita y salta.

Ahora quita la carga y **no toques nada más**:

```bash
kubectl delete pod generador
kubectl get hpa cpu-app
```

**Salida real de esta máquina, unos seis minutos después de parar el generador:**

```
NAME      REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
cpu-app   Deployment/cpu-app   cpu: 2%/50%   1         6         6          11m
```

La CPU ya bajó a **2 %**, y sin embargo siguen **6 réplicas**. No está roto. El HPA baja de
inmediato pero reduce despacio: espera una **ventana de estabilización de 5 minutos** en la
que el uso tiene que mantenerse bajo, para no entrar en un ciclo de subir y bajar. Ten
paciencia y vuelve a mirar:

**Salida real de esta máquina, a los 18 minutos:**

```
NAME      REFERENCE            TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
cpu-app   Deployment/cpu-app   cpu: 2%/50%   1         6         1          18m
```

De vuelta a **1 réplica**, sola. **Subir es urgente (tus usuarios esperan); bajar no lo es
(solo cuesta dinero).** Esa asimetría está deliberadamente escrita en el HPA.

```bash
kubectl delete hpa cpu-app
kubectl delete deployment cpu-app
kubectl delete svc cpu-app
```

---

## Paso 7: Diagnosticar un contenedor que se cae (8 min)

**Troubleshooting es el 30 % del examen CKA.** Este es el procedimiento, en cuatro capas.

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: roto
spec:
  replicas: 1
  selector: { matchLabels: { app: roto } }
  template:
    metadata: { labels: { app: roto } }
    spec:
      containers:
      - name: app
        image: busybox:1.37
        command: ["sh","-c","echo 'arrancando...'; sleep 3; echo 'ERROR: falta /config/app.conf'; exit 1"]
EOF
```

Espera un par de minutos a que entre en `CrashLoopBackOff` (los primeros reintentos son
inmediatos; el estado `CrashLoopBackOff` aparece cuando el kubelet empieza a espaciarlos).

**Capa 1 — el estado:**

```bash
kubectl get pods -l app=roto
```

**Salida real de esta máquina:**

```
NAME                    READY   STATUS             RESTARTS      AGE
roto-6b46997dc6-jmg7w   0/1     CrashLoopBackOff   5 (68s ago)   4m23s
```

`CrashLoopBackOff` **no es la causa**: es «arranca, muere, y el kubelet espera cada vez más
para reintentar». La causa está más abajo.

**Capa 2 — el estado anterior del contenedor:**

```bash
kubectl describe pod -l app=roto | grep -A5 "Last State"
```

**Salida real de esta máquina:**

```
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Mon, 31 Aug 2026 10:09:44 -0500
      Finished:     Mon, 31 Aug 2026 10:09:47 -0500
```

**`Exit Code: 1`** y tres segundos entre `Started` y `Finished`. Ya sabes que la aplicación
arrancó y se mató sola. Aprende a leer los códigos: `0` salida limpia, `1` error de la
aplicación, `137` = 128+9, matado por SIGKILL (casi siempre **OOMKilled**), `143` = 128+15,
SIGTERM.

**Capa 3 — los logs del intento anterior.** Esta es la bandera que separa a quien aprueba
de quien no:

```bash
POD=$(kubectl get pod -l app=roto -o jsonpath='{.items[0].metadata.name}')
kubectl logs $POD --previous
```

**Salida real de esta máquina:**

```
arrancando...
ERROR: falta /config/app.conf
```

**Ahí está la causa, con todas las letras.** `kubectl logs` a secas te mostraría el
contenedor **actual**, que quizá aún no ha escrito nada o ni siquiera arrancó.
**`--previous` te da los logs del que ya murió**, que es justo el que falló.

> Si `--previous` responde `unable to retrieve container logs for containerd://…`, es que
> el contenedor anterior ya fue recogido por la limpieza. Espera a que se vuelva a caer y
> repite: en `CrashLoopBackOff` siempre hay otra oportunidad.

**Capa 4 — los eventos:**

```bash
kubectl get events --field-selector involvedObject.name=$POD --sort-by=.lastTimestamp \
  -o custom-columns='TIPO:.type,RAZON:.reason,MENSAJE:.message' | tail -5
```

**Salida real de esta máquina:**

```
TIPO      RAZON       MENSAJE
Normal    Scheduled   Successfully assigned default/roto-6b46997dc6-jmg7w to cka-worker
Normal    Pulled      Container image "busybox:1.37" already present on machine and can be accessed by the pod
Normal    Created     Container created
Normal    Started     Container started
Warning   BackOff     Back-off restarting failed container app in pod roto-6b46997dc6-jmg7w_default(...)
```

Los eventos descartan lo que **no** falló: se programó bien (no es scheduling), la imagen
estaba (no es registro), el contenedor arrancó (no es el runtime). Por eliminación, es la
aplicación. Y la capa 3 ya te dijo por qué.

```bash
kubectl delete deployment roto
```

> **El orden importa y se memoriza:** `get` (estado) → `describe` (código de salida) →
> `logs --previous` (causa) → `events` (descartar el entorno).

---

## Paso 8: RBAC, un ServiceAccount y una persona (20 min)

Kubernetes distingue dos clases de identidad: las **ServiceAccounts**, que son objetos del
clúster y sirven para programas; y los **usuarios**, que **no son objetos** y salen de un
certificado o de un proveedor externo. Vas a crear uno de cada.

### 8.1 Un ServiceAccount con permisos mínimos

```bash
kubectl create serviceaccount lector-sa
kubectl create role lector-pods --verb=get,list,watch --resource=pods
kubectl create rolebinding lector-sa-binding --role=lector-pods --serviceaccount=default:lector-sa
```

Tres objetos con tres papeles: **quién** (ServiceAccount), **qué se puede hacer** (Role),
**quién puede hacer qué** (RoleBinding). Un Role sin RoleBinding no da nada.

```bash
for verbo in "get pods" "list pods" "delete pods" "get secrets"; do
  printf "%-14s -> " "$verbo"
  kubectl auth can-i $verbo --as=system:serviceaccount:default:lector-sa
done
```

**Salida real de esta máquina:**

```
get pods       -> yes
list pods      -> yes
delete pods    -> no
get secrets    -> no
```

### 8.2 La trampa: `--token` sobre tu kubeconfig de administrador

Vas a probarlo «de verdad» con un token. Y vas a caer en la trampa a propósito:

```bash
TOKEN=$(kubectl create token lector-sa --duration=1h)
APISERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d > ca.crt

kubectl --server="$APISERVER" --certificate-authority=ca.crt --token="$TOKEN" delete pod -l app=fuera
```

**Salida real de esta máquina:**

```
pod "fuera-fbcc68dff-jf8dm" deleted from default namespace
pod "fuera-fbcc68dff-p7vdj" deleted from default namespace
pod "fuera-fbcc68dff-sxz48" deleted from default namespace
```

**¡Borró los Pods!** Pero `auth can-i` acababa de decir `no`. ¿Quién mintió? Ninguno de los
dos. Pregúntale al API server quién cree que eres:

```bash
kubectl --server="$APISERVER" --certificate-authority=ca.crt --token="$TOKEN" auth whoami
```

**Salida real de esta máquina:**

```
ATTRIBUTE                                           VALUE
Username                                            kubernetes-admin
Groups                                              [kubeadm:cluster-admins system:authenticated]
Extra: authentication.kubernetes.io/credential-id   [X509SHA256=2668885764bf24b364b3fb82b6f51a97869bd91b08a61c70cedfe601e769154e]
```

**`kubernetes-admin`.** La bandera `--token` no reemplazó tu kubeconfig: **lo complementó**.
Tu contexto activo sigue aportando el certificado de cliente de administrador, y **cuando
hay certificado y token a la vez, gana el certificado**. Nunca actuaste como el
ServiceAccount.

La forma correcta es un kubeconfig limpio, sin ese certificado:

```bash
kubectl config set-cluster kind-cka --server="$APISERVER" --certificate-authority=ca.crt --embed-certs=true --kubeconfig=sa.kubeconfig
kubectl config set-credentials lector-sa --token="$TOKEN" --kubeconfig=sa.kubeconfig
kubectl config set-context sa --cluster=kind-cka --user=lector-sa --namespace=default --kubeconfig=sa.kubeconfig
kubectl config use-context sa --kubeconfig=sa.kubeconfig

kubectl --kubeconfig=sa.kubeconfig auth whoami
```

**Salida real de esta máquina:**

```
ATTRIBUTE                                           VALUE
Username                                            system:serviceaccount:default:lector-sa
UID                                                 34704724-d298-40ba-8340-efd505351f97
Groups                                              [system:serviceaccounts system:serviceaccounts:default system:authenticated]
Extra: authentication.kubernetes.io/credential-id   [JTI=c165fbe3-54e2-44eb-9873-dfbe01af28db]
```

Ahora sí. Prueba los límites:

```bash
kubectl --kubeconfig=sa.kubeconfig get pods -l app=fuera --no-headers | wc -l
kubectl --kubeconfig=sa.kubeconfig delete pod -l app=fuera
kubectl --kubeconfig=sa.kubeconfig get secrets
kubectl --kubeconfig=sa.kubeconfig get nodes
```

**Salida real de esta máquina:**

```
4
Error from server (Forbidden): pods "fuera-fbcc68dff-b295n" is forbidden: User "system:serviceaccount:default:lector-sa" cannot delete resource "pods" in API group "" in the namespace "default"
Error from server (Forbidden): secrets is forbidden: User "system:serviceaccount:default:lector-sa" cannot list resource "secrets" in API group "" in the namespace "default"
Error from server (Forbidden): nodes is forbidden: User "system:serviceaccount:default:lector-sa" cannot list resource "nodes" in API group "" at the cluster scope
```

Tres denegaciones, y cada mensaje trae los cuatro datos de una decisión RBAC: **quién**
(`User "…lector-sa"`), **qué verbo** (`delete`, `list`), **qué recurso** (`pods`, `secrets`,
`nodes`) y **dónde** (`in the namespace "default"` frente a `at the cluster scope`). Lee esa
última parte: un Role **no puede** dar permiso sobre nodos, porque los nodos no viven en
ningún namespace.

> **Lección:** `auth can-i --as=` es la herramienta correcta para **auditar**, y no necesita
> las credenciales de nadie. Si vas a probar con credenciales reales, usa un kubeconfig
> separado o te estarás engañando.

### 8.3 Una persona: `ana`, con certificado

Un usuario no se crea con `kubectl create user`: ese comando no existe. Se crea firmando un
certificado donde **`CN` es el nombre de usuario** y **`O` es el grupo**.

```bash
openssl genrsa -out ana.key 2048
openssl req -new -key ana.key -out ana.csr -subj "/CN=ana/O=operaciones"
openssl req -in ana.csr -noout -subject
```

**Salida real de esta máquina:**

```
subject=CN = ana, O = operaciones
```

Ahora pídele al clúster que lo firme, con el mismo mecanismo que usó tu worker en el
Laboratorio 1:

```bash
cat > ana-csr.yaml <<EOF
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ana
spec:
  request: $(base64 -w0 ana.csr)
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 86400
  usages:
  - client auth
EOF

kubectl apply -f ana-csr.yaml
kubectl get csr ana
```

**Salida real de esta máquina:**

```
certificatesigningrequest.certificates.k8s.io/ana created
NAME   AGE   SIGNERNAME                            REQUESTOR          REQUESTEDDURATION   CONDITION
ana    0s    kubernetes.io/kube-apiserver-client   kubernetes-admin   24h                 Pending
```

`Pending`: **un humano tiene que aprobarlo**. Ese humano eres tú:

```bash
kubectl certificate approve ana
kubectl get csr ana
kubectl get csr ana -o jsonpath='{.status.certificate}' | base64 -d > ana.crt
openssl x509 -in ana.crt -noout -subject -dates
```

**Salida real de esta máquina:**

```
certificatesigningrequest.certificates.k8s.io/ana approved
NAME   AGE   SIGNERNAME                            REQUESTOR          REQUESTEDDURATION   CONDITION
ana    9s    kubernetes.io/kube-apiserver-client   kubernetes-admin   24h                 Approved,Issued
subject=O = operaciones, CN = ana
notBefore=Aug 31 14:52:16 2026 GMT
notAfter=Sep  1 14:52:16 2026 GMT
```

`Approved,Issued`, y el certificado **caduca en 24 horas** porque así lo pediste con
`expirationSeconds`. Arma su kubeconfig:

```bash
kubectl config set-cluster kind-cka --server="$APISERVER" --certificate-authority=ca.crt --embed-certs=true --kubeconfig=ana.kubeconfig
kubectl config set-credentials ana --client-certificate=ana.crt --client-key=ana.key --embed-certs=true --kubeconfig=ana.kubeconfig
kubectl config set-context ana --cluster=kind-cka --user=ana --namespace=default --kubeconfig=ana.kubeconfig
kubectl config use-context ana --kubeconfig=ana.kubeconfig

kubectl --kubeconfig=ana.kubeconfig auth whoami
kubectl --kubeconfig=ana.kubeconfig get nodes
```

**Salida real de esta máquina:**

```
ATTRIBUTE                                           VALUE
Username                                            ana
Groups                                              [operaciones system:authenticated]
Extra: authentication.kubernetes.io/credential-id   [X509SHA256=ac2b3d1b34a67a0ebce91c35d9c950231036207c0c6f4c04e93c797045072da2]

Error from server (Forbidden): nodes is forbidden: User "ana" cannot list resource "nodes" in API group "" at the cluster scope
```

**El clúster ya sabe quién es `ana` y que pertenece al grupo `operaciones`** (eso es
autenticación) **y aun así no la deja hacer nada** (eso es autorización). Son dos etapas
distintas, y confundirlas es el error conceptual más común de RBAC.

### 8.4 ClusterRole y ClusterRoleBinding, al grupo

```bash
kubectl create clusterrole ver-nodos --verb=get,list,watch --resource=nodes
kubectl create clusterrolebinding operaciones-ve-nodos --clusterrole=ver-nodos --group=operaciones
kubectl --kubeconfig=ana.kubeconfig get nodes
```

**Salida real de esta máquina:**

```
clusterrole.rbac.authorization.k8s.io/ver-nodos created
clusterrolebinding.rbac.authorization.k8s.io/operaciones-ve-nodos created
NAME                STATUS   ROLES           AGE     VERSION
cka-control-plane   Ready    control-plane   8m28s   v1.37.0
cka-worker          Ready    <none>          8m17s   v1.37.0
cka-worker2         Ready    <none>          8m17s   v1.37.0
```

Ata al **grupo**, no a la persona. Cuando entre alguien nuevo al equipo, le firmas un
certificado con `O=operaciones` y ya tiene los permisos. Cuando se va, le revocas el
certificado. **No tocas ni un RoleBinding.**

### 8.5 El detalle que cae en el examen: ClusterRole + RoleBinding

Un ClusterRole no obliga a dar permisos en todo el clúster. Si lo atas con un **RoleBinding**
en vez de un ClusterRoleBinding, sus permisos quedan **limitados a ese namespace**:

```bash
kubectl create namespace produccion
kubectl create rolebinding ana-lee-en-produccion --clusterrole=view --user=ana -n produccion

printf "ana get pods -n produccion -> "; kubectl auth can-i get pods --as=ana -n produccion
printf "ana get pods -n default    -> "; kubectl auth can-i get pods --as=ana -n default
```

**Salida real de esta máquina:**

```
ana get pods -n produccion -> yes
ana get pods -n default    -> no
```

**El mismo ClusterRole (`view`), dos resultados distintos**, según el tipo de binding. Esa
es la razón de que existan ClusterRoles predefinidos (`view`, `edit`, `admin`): se escriben
una vez y se reutilizan namespace por namespace.

| Objeto | Alcance de lo que define | Alcance de lo que concede |
|---|---|---|
| `Role` | un namespace | ese namespace |
| `ClusterRole` | todo el clúster | depende del binding |
| `RoleBinding` | – | **un** namespace (aunque ate un ClusterRole) |
| `ClusterRoleBinding` | – | **todo** el clúster |

---

## Paso 9: Ingress frente a Gateway API (20 min)

Con NodePort, cada servicio que publiques se lleva un puerto raro. Un **Ingress** resuelve
eso: un solo punto de entrada en el 80/443 que reparte por nombre de host o por ruta.

### 9.1 Dos sitios web

```bash
cat > sitios.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sitio-azul
spec:
  replicas: 2
  selector: { matchLabels: { app: sitio-azul } }
  template:
    metadata: { labels: { app: sitio-azul } }
    spec:
      containers:
      - name: web
        image: hashicorp/http-echo:1.0.0
        args: ["-text=SITIO AZUL"]
        ports: [{ containerPort: 5678 }]
---
apiVersion: v1
kind: Service
metadata:
  name: sitio-azul
spec:
  selector: { app: sitio-azul }
  ports: [{ port: 80, targetPort: 5678 }]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sitio-verde
spec:
  replicas: 2
  selector: { matchLabels: { app: sitio-verde } }
  template:
    metadata: { labels: { app: sitio-verde } }
    spec:
      containers:
      - name: web
        image: hashicorp/http-echo:1.0.0
        args: ["-text=SITIO VERDE"]
        ports: [{ containerPort: 5678 }]
---
apiVersion: v1
kind: Service
metadata:
  name: sitio-verde
spec:
  selector: { app: sitio-verde }
  ports: [{ port: 80, targetPort: 5678 }]
EOF

kubectl apply -f sitios.yaml
kubectl rollout status deploy/sitio-azul --timeout=180s
kubectl rollout status deploy/sitio-verde --timeout=180s
```

**Salida real de esta máquina** (recortada):

```
deployment.apps/sitio-azul created
service/sitio-azul created
deployment.apps/sitio-verde created
service/sitio-verde created
deployment "sitio-azul" successfully rolled out
deployment "sitio-verde" successfully rolled out
```

### 9.2 El controlador de Ingress

Un objeto `Ingress` **no hace nada por sí solo**: es una petición. Hace falta un controlador
que la lea y programe un proxy real.

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller --timeout=300s
kubectl -n ingress-nginx get pods -o wide
kubectl get ingressclass
```

**Salida real de esta máquina:**

```
pod/ingress-nginx-controller-596f5b6bcf-q6dsd condition met
NAME                                        READY   STATUS    RESTARTS   AGE   IP            NODE          NOMINATED NODE   READINESS GATES
ingress-nginx-controller-596f5b6bcf-q6dsd   1/1     Running   0          25s   10.244.2.24   cka-worker2   <none>           <none>
NAME    CONTROLLER             PARAMETERS   AGE
nginx   k8s.io/ingress-nginx   <none>       25s
```

**Está en `cka-worker2`, y ese es un problema.** Compruébalo:

```bash
curl -s -o /dev/null -w 'http://localhost:8080 -> HTTP %{http_code}\n' --max-time 5 http://localhost:8080
```

**Salida real de esta máquina:**

```
http://localhost:8080 -> HTTP 000
```

Nada. Diagnostica en vez de reinstalar:

```bash
kubectl -n ingress-nginx get deploy ingress-nginx-controller \
  -o jsonpath='{"nodeSelector: "}{.spec.template.spec.nodeSelector}{"\nports: "}{.spec.template.spec.containers[0].ports}{"\n"}'
```

**Salida real de esta máquina:**

```
nodeSelector: {"kubernetes.io/os":"linux"}
ports: [{"containerPort":80,"hostPort":80,"name":"http","protocol":"TCP"},{"containerPort":443,"hostPort":443,"name":"https","protocol":"TCP"},{"containerPort":8443,"name":"webhook","protocol":"TCP"}]
```

Ya está el diagnóstico completo, y es puro Paso 1: el controlador usa **`hostPort: 80`**,
es decir, el puerto 80 **del nodo donde caiga**; pero tu `extraPortMappings` del Paso 0 mapea
el 8080 de tu portátil al puerto 80 **del control plane**. Y su `nodeSelector` solo pide
`linux`, así que aterrizó en un worker. **El proxy está escuchando en la puerta equivocada.**

La corrección es lo que aprendiste en el Paso 1: `nodeSelector` + `toleration`.

```bash
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=strategic -p '{
  "spec": {"template": {"spec": {
    "nodeSelector": {"kubernetes.io/os": "linux", "ingress-ready": "true"},
    "tolerations": [{"key":"node-role.kubernetes.io/control-plane","operator":"Exists","effect":"NoSchedule"}]
  }}}
}'
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=300s
kubectl -n ingress-nginx get pods -o wide
curl -s -o /dev/null -w 'http://localhost:8080 -> HTTP %{http_code}\n' --max-time 8 http://localhost:8080
```

**Salida real de esta máquina:**

```
deployment "ingress-nginx-controller" successfully rolled out
NAME                                        READY   STATUS    RESTARTS   AGE   IP           NODE                NOMINATED NODE   READINESS GATES
ingress-nginx-controller-5856557796-pcgsk   1/1     Running   0          20s   10.244.0.6   cka-control-plane   <none>           <none>
http://localhost:8080 -> HTTP 404
```

Ahora está en `cka-control-plane` y responde **404**. Un 404 aquí es una **buena** noticia:
el proxy contesta, pero todavía no hay ninguna regla que encaje.

### 9.3 El Ingress

```bash
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: sitios
spec:
  ingressClassName: nginx
  rules:
  - host: azul.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend: { service: { name: sitio-azul, port: { number: 80 } } }
  - host: verde.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend: { service: { name: sitio-verde, port: { number: 80 } } }
EOF

kubectl get ingress sitios
curl -s --max-time 8 -H 'Host: azul.local'  http://localhost:8080/
curl -s --max-time 8 -H 'Host: verde.local' http://localhost:8080/
curl -s -o /dev/null -w 'Host: otro.local -> HTTP %{http_code}\n' --max-time 8 -H 'Host: otro.local' http://localhost:8080/
```

**Salida real de esta máquina:**

```
NAME     CLASS   HOSTS                    ADDRESS   PORTS   AGE
sitios   nginx   azul.local,verde.local             80      10s
SITIO AZUL
SITIO VERDE
Host: otro.local -> HTTP 404
```

**Un solo puerto, dos sitios, enrutado por la cabecera `Host`.** El `-H 'Host: …'` sustituye
al DNS: le dice a `curl` que finja que pidió ese nombre. En producción esto lo haría un
registro DNS real apuntando al Ingress.

### 9.4 Lo mismo, con Gateway API

Gateway API es el sucesor de Ingress, y su idea central es **separar responsabilidades**:

| Objeto | Quién lo escribe | Qué decide |
|---|---|---|
| `GatewayClass` | quien administra el clúster | qué implementación se usa |
| `Gateway` | quien administra la red | puertos, protocolos, certificados TLS, qué hosts se aceptan |
| `HTTPRoute` | **quien desarrolla la aplicación** | a qué Service va cada ruta |

En un Ingress, esas tres decisiones viven en el mismo objeto, y por eso las anotaciones
propietarias (`nginx.ingress.kubernetes.io/…`) se multiplicaron: no había dónde ponerlas.

Primero las CRDs (Gateway API **no** viene en Kubernetes; se instala):

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.1/standard-install.yaml
kubectl get crd | grep gateway.networking.k8s.io
```

**Salida real de esta máquina:**

```
backendtlspolicies.gateway.networking.k8s.io   Namespaced   v1(storage)           2026-08-31T14:59:34Z
gatewayclasses.gateway.networking.k8s.io       Cluster      v1(storage),v1beta1   2026-08-31T14:59:34Z
gateways.gateway.networking.k8s.io             Namespaced   v1(storage),v1beta1   2026-08-31T14:59:34Z
grpcroutes.gateway.networking.k8s.io           Namespaced   v1(storage)           2026-08-31T14:59:34Z
httproutes.gateway.networking.k8s.io           Namespaced   v1(storage),v1beta1   2026-08-31T14:59:34Z
listenersets.gateway.networking.k8s.io         Namespaced   v1(storage)           2026-08-31T14:59:35Z
referencegrants.gateway.networking.k8s.io      Namespaced   v1,v1beta1(storage)   2026-08-31T14:59:35Z
tcproutes.gateway.networking.k8s.io            Namespaced   v1(storage)           2026-08-31T14:59:35Z
tlsroutes.gateway.networking.k8s.io            Namespaced   v1(storage)           2026-08-31T14:59:35Z
udproutes.gateway.networking.k8s.io            Namespaced   v1(storage)           2026-08-31T14:59:35Z
```

Fíjate en `tcproutes`, `tlsroutes` y `udproutes`: **Gateway API no es solo HTTP.** Ingress
nunca supo hacer TCP ni UDP.

Ahora un controlador que las implemente (NGINX Gateway Fabric, con Helm):

```bash
helm install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
  --create-namespace -n nginx-gateway \
  --set service.type=NodePort \
  --wait --timeout 5m

kubectl get gatewayclass
```

**Salida real de esta máquina:**

```
Pulled: ghcr.io/nginx/charts/nginx-gateway-fabric:2.6.7
NAME: ngf
STATUS: deployed
NAME    CONTROLLER                                   ACCEPTED   AGE
nginx   gateway.nginx.org/nginx-gateway-controller   True       12s
```

```bash
kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: puerta
spec:
  gatewayClassName: nginx
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    hostname: "*.local"
    allowedRoutes:
      namespaces:
        from: Same
EOF

kubectl get gateway puerta
kubectl get pods,svc -l gateway.networking.k8s.io/gateway-name=puerta
```

**Salida real de esta máquina:**

```
NAME     CLASS   ADDRESS   PROGRAMMED   AGE
puerta   nginx             True         20s

NAME                               READY   STATUS    RESTARTS   AGE
pod/puerta-nginx-b76bb75d5-m9r6b   1/1     Running   0          20s

NAME                   TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
service/puerta-nginx   LoadBalancer   10.96.234.102   <pending>     80:30567/TCP   20s
```

`PROGRAMMED: True`, y **el Gateway creó su propio Deployment y su propio Service**. Eso es
otra diferencia con Ingress: allí el proxy es único y compartido; aquí cada Gateway puede
tener el suyo, con su ciclo de vida.

El `EXTERNAL-IP: <pending>` es correcto: `kind` no trae balanceador de nube. Usaremos el
NodePort `30567`.

```bash
kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ruta-azul
spec:
  parentRefs:
  - name: puerta
  hostnames: ["azul.local"]
  rules:
  - matches:
    - path: { type: PathPrefix, value: / }
    backendRefs:
    - name: sitio-azul
      port: 80
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ruta-verde
spec:
  parentRefs:
  - name: puerta
  hostnames: ["verde.local"]
  rules:
  - matches:
    - path: { type: PathPrefix, value: / }
    backendRefs:
    - name: sitio-verde
      port: 80
EOF

kubectl get httproute
```

**Salida real de esta máquina:**

```
NAME         HOSTNAMES         AGE
ruta-azul    ["azul.local"]    12s
ruta-verde   ["verde.local"]   12s
```

### 9.5 La prueba, y una trampa de red que enseña mucho

```bash
GWPORT=$(kubectl get svc puerta-nginx -o jsonpath='{.spec.ports[0].nodePort}')
NODEIP=$(kubectl get node cka-worker -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
curl -s --max-time 8 -H 'Host: azul.local' http://$NODEIP:$GWPORT/
```

**Salida real de esta máquina:**

```
(nada: se agota el tiempo)
```

En el Paso 5 los **tres** nodos respondían al NodePort. Aquí no. La diferencia:

```bash
kubectl get svc puerta-nginx -o jsonpath='{"externalTrafficPolicy: "}{.spec.externalTrafficPolicy}{"\n"}'
kubectl get pod -l gateway.networking.k8s.io/gateway-name=puerta -o custom-columns='POD:.metadata.name,NODO:.spec.nodeName'
```

**Salida real de esta máquina:**

```
externalTrafficPolicy: Local
POD                            NODO
puerta-nginx-b76bb75d5-m9r6b   cka-worker2
```

**`externalTrafficPolicy: Local`.** Con `Cluster` (el valor por defecto, el del Paso 5)
cualquier nodo acepta y reenvía. Con `Local`, **solo responde el nodo que tiene el Pod**, a
cambio de conservar la IP de origen del cliente y ahorrar un salto de red. Es un intercambio
deliberado, muy común en controladores de entrada.

```bash
POD_NODE=$(kubectl get pod -l gateway.networking.k8s.io/gateway-name=puerta -o jsonpath='{.items[0].spec.nodeName}')
NODEIP=$(kubectl get node $POD_NODE -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
echo "el Pod vive en $POD_NODE ($NODEIP), NodePort $GWPORT"
curl -s --max-time 8 -H 'Host: azul.local'  http://$NODEIP:$GWPORT/
curl -s --max-time 8 -H 'Host: verde.local' http://$NODEIP:$GWPORT/
```

**Salida real de esta máquina:**

```
el Pod vive en cka-worker2 (172.18.0.3), NodePort 30567
SITIO AZUL
SITIO VERDE
```

**Los mismos dos sitios, servidos ahora por Gateway API**, conviviendo con el Ingress del
9.3 que sigue funcionando en el 8080. Ese es el camino real de migración: los dos a la vez,
y se apaga el viejo cuando el nuevo está probado.

| | Ingress | Gateway API |
|---|---|---|
| Estado | estable, congelado | estable (v1), en evolución |
| Viene en Kubernetes | sí | **no**: se instalan CRDs |
| Protocolos | HTTP/HTTPS | HTTP, gRPC, TLS, TCP, UDP |
| Quién configura qué | un solo objeto, un solo dueño | `Gateway` (red) y `HTTPRoute` (aplicación), separados |
| Extensiones | anotaciones propietarias | campos tipados y `policies` |
| Entre namespaces | complicado | `ReferenceGrant`, explícito |

---

## Paso 10: Ver el clúster entero en Grafana (12 min)

Este paso se puede hacer en casa. Necesita **2 GiB de RAM adicionales**.

`kube-prometheus-stack` es un chart de Helm que instala Prometheus, Grafana,
`kube-state-metrics`, `node-exporter` y decenas de dashboards ya hechos.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm show chart prometheus-community/kube-prometheus-stack | grep -E '^(name|version|appVersion)'
```

**Salida real de esta máquina:**

```
appVersion: v0.93.1
name: kube-prometheus-stack
version: 88.6.2
```

**Nunca instales un chart con los valores por defecto sin mirarlos.** Los de este chart
asumen un clúster de producción. Este archivo lo ajusta a un portátil:

```bash
cat > valores-observabilidad.yaml <<'EOF'
# Perfil ligero para un portatil: sin Alertmanager, retencion corta,
# y limites de memoria explicitos. Los dashboards de Grafana llegan igual.
alertmanager:
  enabled: false
grafana:
  adminPassword: "topicos2026"
  service:
    type: NodePort
    nodePort: 30300
prometheus:
  prometheusSpec:
    retention: 2h
    resources:
      requests: { memory: "400Mi", cpu: "100m" }
      limits:   { memory: "1Gi" }
prometheusOperator:
  resources:
    requests: { memory: "100Mi", cpu: "50m" }
EOF

helm install obs prometheus-community/kube-prometheus-stack \
  --version 88.6.2 \
  --create-namespace -n observabilidad \
  -f valores-observabilidad.yaml \
  --wait --timeout 12m
```

**Salida real de esta máquina** (la instalación tardó `1m20s`):

```
NAME: obs
LAST DEPLOYED: Mon Aug 31 09:59:42 2026
NAMESPACE: observabilidad
STATUS: deployed
REVISION: 1
```

```bash
kubectl -n observabilidad get pods
helm list -n observabilidad
```

**Salida real de esta máquina:**

```
NAME                                                  READY   STATUS    RESTARTS   AGE
obs-grafana-7f68f68f59-t7llj                          3/3     Running   0          67s
obs-kube-prometheus-stack-operator-7bccd8bdbc-l4vgk   1/1     Running   0          67s
obs-kube-state-metrics-7f45f5467c-mj8mc               1/1     Running   0          67s
obs-prometheus-node-exporter-8kxm5                    1/1     Running   0          67s
obs-prometheus-node-exporter-jgtks                    1/1     Running   0          67s
obs-prometheus-node-exporter-l6dhj                    1/1     Running   0          67s
prometheus-obs-kube-prometheus-stack-prometheus-0     2/2     Running   0          56s

NAME	NAMESPACE     	REVISION	UPDATED                	STATUS  	CHART                       	APP VERSION
obs 	observabilidad	1       	2026-08-31 10:02:09    	deployed	kube-prometheus-stack-88.6.2	v0.93.1    
```

Reconoce las piezas: **tres** `node-exporter` (un DaemonSet, uno por nodo, métricas del
sistema operativo), **un** `kube-state-metrics` (métricas de los objetos de la API: cuántos
Deployments, cuántos Pods `Pending`), **un** Prometheus (guarda las series) y **un** Grafana
(las dibuja).

### 10.1 Entrar a Grafana

```bash
NODEIP=$(kubectl get node cka-worker -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
echo "Abre en tu navegador:  http://$NODEIP:30300     usuario: admin   clave: topicos2026"
curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 http://$NODEIP:30300/login
```

**Salida real de esta máquina:**

```
Abre en tu navegador:  http://172.18.0.5:30300     usuario: admin   clave: topicos2026
HTTP 200
```

Si tu navegador no llega a la red de `kind`, usa lo que aprendiste en el Paso 5:

```bash
kubectl -n observabilidad port-forward svc/obs-grafana 3000:80
# y abre http://localhost:3000
```

Los dashboards que trae el chart:

```bash
curl -s -u admin:topicos2026 "http://$NODEIP:30300/api/search?type=dash-db&limit=12" \
  | python3 -c "import json,sys; [print(' -', x['title']) for x in json.load(sys.stdin)]"
```

**Salida real de esta máquina:**

```
 - CoreDNS
 - etcd
 - Grafana Overview
 - Kubernetes / API server
 - Kubernetes / Compute Resources /  Multi-Cluster
 - Kubernetes / Compute Resources / Cluster
 - Kubernetes / Compute Resources / Namespace (Pods)
 - Kubernetes / Compute Resources / Namespace (Workloads)
 - Kubernetes / Compute Resources / Node (Pods)
 - Kubernetes / Compute Resources / Nodes Overview
 - Kubernetes / Compute Resources / Pod
 - Kubernetes / Compute Resources / Workload
```

Abre **Kubernetes / Compute Resources / Cluster**: es la vista del clúster entero. Y
compárala con el Paso 6: `kubectl top` te da un número de ahora; Grafana te da la serie
temporal, por namespace y por workload. Es la misma métrica, con memoria.

### 10.2 Comprobar que Prometheus mide de verdad

```bash
kubectl -n observabilidad port-forward svc/obs-kube-prometheus-stack-prometheus 19090:9090 &
sleep 5
curl -s "http://127.0.0.1:19090/api/v1/query?query=count(kube_node_info)" \
  | python3 -c "import json,sys; print('nodos:', json.load(sys.stdin)['data']['result'][0]['value'][1])"
curl -s "http://127.0.0.1:19090/api/v1/targets?state=active" | python3 -c "
import json,sys
from collections import Counter
d=json.load(sys.stdin)['data']['activeTargets']
c=Counter(t['labels'].get('job','?') for t in d)
print('targets activos:',len(d))
for k,v in sorted(c.items()): print(f'  {k}: {v}')"
kill %1
```

**Salida real de esta máquina:**

```
nodos: 3
targets activos: 26
  apiserver: 1
  coredns: 2
  kube-controller-manager: 1
  kube-etcd: 1
  kube-proxy: 3
  kube-scheduler: 1
  kube-state-metrics: 1
  kubelet: 9
  node-exporter: 3
  obs-grafana: 1
  obs-kube-prometheus-stack-operator: 1
  obs-kube-prometheus-stack-prometheus: 2
```

**26 objetivos, y ahí está tu control plane completo**: `apiserver`, `kube-etcd`,
`kube-scheduler`, `kube-controller-manager`, `kube-proxy` en los tres nodos, `kubelet` con
nueve endpoints. Cada caja del diagrama de arquitectura del módulo 4, ahora emitiendo
métricas.

---

## Limpieza (3 min)

```bash
kind delete cluster --name cka
docker ps -a --filter "name=cka-" --format '{{.Names}}'
rm -f ana.key ana.crt ana.csr ana-csr.yaml ca.crt sa.kubeconfig ana.kubeconfig
rm -f kind-cka.yaml dentro.yaml sin-toleracion.yaml sts.yaml sitios.yaml valores-observabilidad.yaml
```

`docker ps -a` no debe listar nada. Si hiciste el anexo, borra también `kind delete cluster
--name cni` y `--name ebpf`.

---

## Síntesis: qué hiciste y qué demostraste

| Lo que hiciste | Lo que demuestra |
|---|---|
| `dentro.yaml` con toleration + afinidad | Entrar al control plane necesita **permiso** y **elección**, no una sola |
| `FailedScheduling: 1 untolerated taint(s), 2 didn't match affinity` | `Pending` es un informe, no un error |
| PVC `Pending` → aparece el Pod → PV en 4 s | `WaitForFirstConsumer` retrasa el disco hasta saber el nodo |
| `nodeAffinity` del PV = nodo del Pod | El almacenamiento local le pone domicilio fijo al dato |
| `datos-cola-0/1/2` y `cola-1` que vuelve igual | `volumeClaimTemplates` da identidad; un Deployment da réplicas |
| RS viejo en 0 réplicas | El rollback no reconstruye: reactiva |
| Revisión 1 → historial 3,4,5 | `undo` avanza el contador; es `git revert`, no `git reset` |
| NodePort en 3 nodos / `port-forward` solo en `127.0.0.1` | Uno es un objeto del clúster, el otro un proceso tuyo |
| `IP SANs` en el log de metrics-server | El fallo estaba escrito; `--kubelet-insecure-tls` es deuda, no solución |
| HPA 1 → 6 con CPU al 402 % | El HPA mide contra `requests`; sin `requests` no hay HPA |
| `logs --previous` con el mensaje real | El contenedor actual no tiene la respuesta; el muerto sí |
| `auth whoami` diciendo `kubernetes-admin` | Con certificado y token a la vez, gana el certificado |
| `ana` autenticada y prohibida a la vez | Autenticación y autorización son dos etapas |
| `view` con RoleBinding solo en `produccion` | El binding decide el alcance, no el ClusterRole |
| Ingress en el nodo equivocado por `hostPort` | El Paso 1 resolvió un problema del Paso 9 |
| `externalTrafficPolicy: Local` | Conservar la IP de origen cuesta que solo un nodo responda |
| 26 targets en Prometheus | Cada componente del módulo 4 emite métricas |

---

## Cómo conecta con el resto del curso

- **Laboratorio 1 de este módulo:** allí instalaste el clúster; aquí lo operas. El taint del
  control plane, los static pods y el diagnóstico por logs son los mismos.
- **Módulo 6 (CKAD):** el desarrollador escribe `HTTPRoute`, `Deployment` y `PersistentVolumeClaim`.
  Tú, como administrador, escribes `Gateway`, `StorageClass`, `ResourceQuota` y RBAC. Hoy
  viste la frontera exacta.
- **Módulo 7 (CKS):** el RBAC del Paso 8 es la superficie de ataque principal de un clúster.
  Allí lo auditarás buscando escaladas de privilegio.
- **Módulo 8 (producción):** `helm install` del Paso 10 es una operación manual. En GitOps,
  ese mismo chart lo aplica un controlador desde Git, y el loop de reconciliación se extiende
  hasta el repositorio.

---

## Para profundizar

- Taints y tolerations — <https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/>
- Asignar Pods a nodos (afinidad) — <https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/>
- Volúmenes persistentes — <https://kubernetes.io/docs/concepts/storage/persistent-volumes/>
- StatefulSets — <https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/>
- Deployments: rollouts y rollbacks — <https://kubernetes.io/docs/concepts/workloads/controllers/deployment/>
- Services y `externalTrafficPolicy` — <https://kubernetes.io/docs/concepts/services-networking/service/>
- HorizontalPodAutoscaler — <https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/>
- RBAC — <https://kubernetes.io/docs/reference/access-authn-authz/rbac/>
- Certificados y CSR — <https://kubernetes.io/docs/reference/access-authn-authz/certificate-signing-requests/>
- Ingress — <https://kubernetes.io/docs/concepts/services-networking/ingress/>
- Gateway API — <https://gateway-api.sigs.k8s.io/>
- Migrar de Ingress a Gateway API — <https://gateway-api.sigs.k8s.io/guides/migrating-from-ingress/>
- Depurar Pods — <https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/>

---

# Anexo opcional (para casa): cambiar de CNI

No se hace en clase y no se evalúa en la sesión. Necesita **4 GiB de RAM libres** y crea dos
clústeres `kind` adicionales.

El plugin **CNI** (Container Network Interface) es la pieza que le da una IP a cada Pod y
hace que se vean entre nodos. Kubernetes **no trae uno**: en el Laboratorio 1 instalaste
Flannel a mano, y `kind` te instala `kindnet` sin preguntarte. Cambiarlo es una decisión de
arquitectura, y aquí vas a ver **en qué se diferencian de verdad**, midiendo en vez de
creyendo.

## A1: Un clúster sin CNI (10 min)

```bash
cat > kind-cni.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: cni
networking:
  disableDefaultCNI: true
  podSubnet: "192.168.0.0/16"
nodes:
- role: control-plane
  image: kindest/node:v1.37.0
- role: worker
  image: kindest/node:v1.37.0
EOF

kind create cluster --config kind-cni.yaml
kubectl --context kind-cni get nodes
kubectl --context kind-cni get pods -n kube-system -o wide | grep -E 'coredns|NAME'
```

**Salida real de esta máquina:**

```
NAME                STATUS     ROLES           AGE   VERSION
cni-control-plane   NotReady   control-plane   10s   v1.37.0
cni-worker          NotReady   <none>          0s    v1.37.0

NAME                       READY   STATUS    RESTARTS   AGE   IP       NODE     NOMINATED NODE   READINESS GATES
coredns-559f6c778d-h5kw5   0/1     Pending   0          1s    <none>   <none>   <none>           <none>
coredns-559f6c778d-l2gx7   0/1     Pending   0          1s    <none>   <none>   <none>           <none>
```

Exactamente el mismo cuadro del Paso 3.3 del Laboratorio 1: nodos `NotReady`, CoreDNS
`Pending` sin nodo. **Sin CNI no hay red de Pods, y sin red de Pods no hay clúster
utilizable.** El `podSubnet: 192.168.0.0/16` no es capricho: es el rango por defecto de
Calico, que instalas ahora.

## A2: Calico (12 min)

Calico se instala con un **operador** (el patrón que verás en el módulo 8): un controlador
que gestiona la instalación a partir de un objeto de configuración.

```bash
kubectl --context kind-cni apply --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/projectcalico/calico/v3.32.2/manifests/tigera-operator.yaml
kubectl --context kind-cni -n tigera-operator rollout status deploy/tigera-operator --timeout=300s

kubectl --context kind-cni apply -f - <<'EOF'
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
    - name: default-ipv4-ippool
      blockSize: 26
      cidr: 192.168.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
---
apiVersion: operator.tigera.io/v1
kind: APIServer
metadata:
  name: default
spec: {}
EOF

kubectl --context kind-cni wait --for=condition=Ready node --all --timeout=420s
kubectl --context kind-cni get nodes
kubectl --context kind-cni get pods -n kube-system -o wide | grep coredns
```

**Salida real de esta máquina:**

```
node/cni-control-plane condition met
node/cni-worker condition met
NAME                STATUS   ROLES           AGE   VERSION
cni-control-plane   Ready    control-plane   89s   v1.37.0
cni-worker          Ready    <none>          79s   v1.37.0

coredns-559f6c778d-h5kw5   1/1   Running   0   81s   192.168.87.66   cni-control-plane   <none>   <none>
coredns-559f6c778d-l2gx7   1/1   Running   0   81s   192.168.87.65   cni-control-plane   <none>   <none>
```

`Ready`, y las IPs de Pod salen de **`192.168.x.x`**, el pool que declaraste. Cambiar de CNI
cambia el plan de direccionamiento entero.

## A3: La comparación, medida (13 min)

### A3.1 ¿Aplican NetworkPolicy los dos?

Es la pregunta que todo el mundo cree saber. **Mídela.**

```bash
cat > prueba-netpol.sh <<'SCRIPT'
#!/usr/bin/env bash
CTX="$1"; K="kubectl --context $CTX"
$K create namespace pruebared >/dev/null 2>&1
$K -n pruebared run servidor --image=nginx:1.29-alpine --labels=rol=servidor >/dev/null 2>&1
$K -n pruebared expose pod servidor --port=80 >/dev/null 2>&1
$K -n pruebared wait --for=condition=Ready pod/servidor --timeout=180s >/dev/null 2>&1
printf "  antes de la politica:    "
$K -n pruebared run c1 --image=curlimages/curl:8.19.0 --restart=Never --rm -i --quiet -- \
   curl -s -o /dev/null -w '%{http_code}\n' --max-time 6 http://servidor 2>/dev/null | tr -d '\r'
$K -n pruebared apply -f - >/dev/null 2>&1 <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: denegar-todo-entrante
spec:
  podSelector: {}
  policyTypes: ["Ingress"]
EOF
sleep 8
printf "  despues de denegar-todo: "
out=$($K -n pruebared run c2 --image=curlimages/curl:8.19.0 --restart=Never --rm -i --quiet -- \
   curl -s -o /dev/null -w '%{http_code}\n' --max-time 6 http://servidor 2>/dev/null | tr -d '\r')
echo "${out:-(sin respuesta)}"
SCRIPT
chmod +x prueba-netpol.sh

echo "### CNI = kindnet (cluster cka)"; ./prueba-netpol.sh kind-cka
echo "### CNI = Calico (cluster cni)"; ./prueba-netpol.sh kind-cni
```

**Salida real de esta máquina:**

```
### CNI = kindnet (cluster cka)
  antes de la politica:    200
  despues de denegar-todo: 000
### CNI = Calico (cluster cni)
  antes de la politica:    200
  despues de denegar-todo: 000
```

**Los dos aplican la política.** Y esto contradice la mitad de los blogs que encontrarás:
durante años `kindnet` **no** implementó NetworkPolicy, y la recomendación estándar era
«para practicar NetworkPolicy, instala Calico». En la versión de `kindnet` que trae `kind`
v0.32 ya no hace falta.

> **La lección no es sobre kindnet: es sobre el método.** Una afirmación técnica de hace dos
> años puede ser falsa hoy. Tardaste treinta segundos en medirlo en tu propia máquina.
> Mídelo siempre.

### A3.2 Entonces, ¿en qué se diferencian?

```bash
echo "=== kindnet ==="
kubectl --context kind-cka -n kube-system get ds kindnet \
  -o custom-columns='DS:.metadata.name,IMAGEN:.spec.template.spec.containers[0].image,NODOS:.status.desiredNumberScheduled'
kubectl --context kind-cka get pods -A --no-headers | grep -c kindnet
kubectl --context kind-cka get crd | grep -cE 'projectcalico|tigera'

echo "=== Calico ==="
kubectl --context kind-cni get pods -n calico-system --no-headers | wc -l
kubectl --context kind-cni get crd | grep -cE 'projectcalico|tigera'
kubectl --context kind-cni get ippools.crd.projectcalico.org \
  -o custom-columns='POOL:.metadata.name,CIDR:.spec.cidr,ENCAP:.spec.vxlanMode'
```

**Salida real de esta máquina:**

```
=== kindnet ===
DS        IMAGEN                                          NODOS
kindnet   docker.io/kindest/kindnetd:v20260820-69b56db7   3
3
0
=== Calico ===
8
31
POOL                  CIDR             ENCAP
default-ipv4-ippool   192.168.0.0/16   CrossSubnet
```

**3 Pods y 0 CRDs frente a 8 Pods y 31 CRDs.** Ahí está la diferencia real: no es «uno hace
red y el otro no», es **cuánta superficie de administración te entrega cada uno**. Calico
trae su propia API (`ippools`, políticas globales, jerarquías de tiers) y por tanto su propio
coste operativo.

Míralo también en el kernel de un nodo:

```bash
echo "-- kindnet:"; docker exec cka-worker ip route | grep -E '^10\.244' | head -3
echo "-- Calico:";  docker exec cni-worker ip route | grep -E '192\.168|blackhole' | head -3
```

**Salida real de esta máquina:**

```
-- kindnet:
10.244.0.0/24 via 172.18.0.4 dev eth0 
10.244.1.11 dev vethb2bab330 scope host 
10.244.1.12 dev vethc17fd0f0 scope host 
-- Calico:
192.168.87.64/26 via 172.18.0.6 dev eth0 proto 80 onlink 
blackhole 192.168.119.128/26 proto 80 
192.168.119.129 dev cali1020bde6575 scope link metric 1024
```

`kindnet` reparte **un `/24` por nodo** y crea rutas de host planas. Calico reparte **bloques
`/26`** (el `blockSize` que declaraste), les pone `proto 80` (su propio protocolo de rutas) y
añade una ruta **`blackhole`** para su propio bloque, de modo que el tráfico a direcciones no
asignadas se descarta en el nodo en vez de dar vueltas por la red.

## A4: Cilium, y por qué existe eBPF (opcional, 10 min extra)

Cilium no reemplaza solo al CNI: **puede reemplazar a `kube-proxy`**. Crea un clúster sin
ninguno de los dos:

```bash
cat > kind-cilium.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ebpf
networking:
  disableDefaultCNI: true
  kubeProxyMode: "none"
nodes:
- role: control-plane
  image: kindest/node:v1.37.0
- role: worker
  image: kindest/node:v1.37.0
EOF

kind create cluster --config kind-cilium.yaml
kubectl --context kind-ebpf get pods -n kube-system --no-headers | grep -c kube-proxy
```

**Salida real de esta máquina:**

```
0
```

**Cero Pods de `kube-proxy`.** Ahora Cilium:

```bash
helm repo add cilium https://helm.cilium.io/ && helm repo update
APIIP=$(docker inspect ebpf-control-plane -f '{{.NetworkSettings.Networks.kind.IPAddress}}')
helm install cilium cilium/cilium --namespace kube-system \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost="$APIIP" \
  --set k8sServicePort=6443 \
  --set operator.replicas=1 \
  --kube-context kind-ebpf --wait --timeout 10m

kubectl --context kind-ebpf wait --for=condition=Ready node --all --timeout=420s
POD=$(kubectl --context kind-ebpf -n kube-system get pods -l k8s-app=cilium -o jsonpath='{.items[0].metadata.name}')
kubectl --context kind-ebpf -n kube-system exec $POD -c cilium-agent -- cilium-dbg status \
  | grep -iE 'KubeProxyReplacement|Routing|Masquerading'
```

**Salida real de esta máquina:**

```
KubeProxyReplacement:    True   [eth0    172.18.0.8 ... (Direct Routing)]
Routing:                 Network: Tunnel [vxlan]   Host: Legacy
Masquerading:            IPTables [IPv4: Enabled, IPv6: Disabled]
```

`KubeProxyReplacement: True`. Ahora la prueba que lo cierra todo:

```bash
kubectl --context kind-ebpf create deployment web --image=nginx:1.29-alpine --replicas=2
kubectl --context kind-ebpf expose deployment web --port=80
kubectl --context kind-ebpf rollout status deploy/web --timeout=240s
kubectl --context kind-ebpf run probe --image=curlimages/curl:8.19.0 --restart=Never --rm -i --quiet -- \
  curl -sS -o /dev/null -w 'HTTP %{http_code}\n' --max-time 10 http://web

printf "kindnet + kube-proxy (cka-worker):   "; docker exec cka-worker  sh -c 'iptables-save | grep -c KUBE-SVC'
printf "Cilium sin kube-proxy (ebpf-worker): "; docker exec ebpf-worker sh -c 'iptables-save | grep -c KUBE-SVC'

kubectl --context kind-ebpf -n kube-system exec $POD -c cilium-agent -- cilium-dbg service list | head -8
```

**Salida real de esta máquina:**

```
HTTP 200

kindnet + kube-proxy (cka-worker):   96
Cilium sin kube-proxy (ebpf-worker): 0

ID   Frontend                Service Type   Backend                             
1    10.96.114.236:443/TCP   ClusterIP      1 => 172.18.0.8:4244/TCP (active)   
2    10.96.0.10:53/TCP       ClusterIP      1 => 10.0.0.46:53/TCP (active)      
                                            2 => 10.0.0.66:53/TCP (active)      
3    10.96.0.10:53/UDP       ClusterIP      1 => 10.0.0.46:53/UDP (active)      
                                            2 => 10.0.0.66:53/UDP (active)      
4    10.96.0.10:9153/TCP     ClusterIP      1 => 10.0.0.46:9153/TCP (active)    
                                            2 => 10.0.0.66:9153/TCP (active)    
```

Lee las tres cosas juntas y tendrás toda la historia:

1. **`HTTP 200`**: el Service funciona perfectamente.
2. **96 reglas `KUBE-SVC` de iptables en un clúster, 0 en el otro.** En el módulo 4 viste a
   `kube-proxy` escribiendo reglas de iptables por cada Service. Aquí no hay ninguna.
3. **La tabla de servicios vive dentro de Cilium**, en programas eBPF cargados en el kernel.

Y ahí está la razón de existir de eBPF en redes de Kubernetes: con iptables, cada Service
añade reglas a una lista que el kernel recorre **en orden**; con miles de Services eso se
nota. Con eBPF es una búsqueda en una tabla hash. En un clúster de laboratorio no verás la
diferencia; en uno de 5.000 Services, sí.

| | kindnet | Calico | Cilium |
|---|---|---|---|
| Pods de red | 3 (1 por nodo) | 8 | 1 por nodo + operador |
| CRDs propias | 0 | 31 | decenas |
| NetworkPolicy estándar | sí (verificado) | sí | sí |
| Políticas ampliadas (L7, DNS, global) | no | sí | sí |
| Puede sustituir a `kube-proxy` | no | parcialmente | **sí** (verificado) |
| Dónde balancea los Services | iptables (`kube-proxy`) | iptables o eBPF | **eBPF** |
| Observabilidad incluida | no | métricas | Hubble (flujos L3-L7) |
| Cuándo elegirlo | aprender, CI | política de red y escala en empresa | escala grande, L7, observabilidad |

## Limpieza del anexo

```bash
kind delete cluster --name cni
kind delete cluster --name ebpf
rm -f kind-cni.yaml kind-cilium.yaml prueba-netpol.sh
kind get clusters
```

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
