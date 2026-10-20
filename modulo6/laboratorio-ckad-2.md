# Laboratorio 2 (Módulo 6) – Extender, configurar, proteger, desplegar y exponer

**Módulo 6 · sesión 9 · en clase · 160–180 minutos.** En el Laboratorio 1 construiste
`pulso`, la depuraste sin shell y le enseñaste al kubelet cuándo está viva. Hoy la sacas al
mundo: le inventas un tipo de recurso propio, la configuras, la encierras en un namespace
que no perdona, la despliegas sin cortar el servicio, le pones muros de red y la publicas,
primero con Ingress y después con Gateway API, migrando de uno al otro sin apagar nada.

| Bloque | Paso | Tiempo | ¿Se puede dejar para casa? |
|---|---|---|---|
| Clúster `kind` con **Calico** y Whisker | 0 | ~12 min | No |
| Un CRD propio y un controlador de juguete (con RBAC) | 1 | ~25 min | No |
| ConfigMaps y Secrets: tres formas de consumir | 2 | ~10 min | No |
| Seguridad: Pod Security `restricted` y `securityContext` | 3 | ~15 min | No |
| LimitRange y ResourceQuota | 4 | ~8 min | Sí |
| Estrategias de despliegue, **medidas**: rolling, Recreate, blue/green y canary | 5 | ~25 min | No |
| NetworkPolicies con Calico, y cómo **probar** que funcionan | 6 | ~25 min | No |
| De Ingress a Gateway API: una migración real | 7 | ~30 min | En parte |
| **Reto** estilo examen, calificado por script | 8 | ~20 min | No |

> La idea central de esta sesión: **un objeto aceptado no es un comportamiento
> garantizado.** Un CRD sin controlador no hace nada, una NetworkPolicy sin un CNI que la
> aplique no bloquea nada, un Ingress sin controlador no enruta nada y un canary no tiene
> «porcentaje» salvo el que tú midas. Hoy no le crees a `kubectl apply`: **mides**.

---

## Cómo trabajar este laboratorio

Las mismas reglas del Laboratorio 1, que siguen valiendo:

| Técnica | Lo que te pide | De dónde sale |
|---|---|---|
| **Predice, ejecuta, explica** | En cada **🔮 Predice**, escribe tu predicción en `predicciones.md` antes de ejecutar | PRIMM (Sentance, Waite y Kallia, 2019); Predict-Observe-Explain (White y Gunstone, 1992) |
| **Fallo productivo** | Varios pasos fallan **a propósito** (un RBAC incompleto, un puerto equivocado, un guion de más). Lee el error antes de seguir | Kapur (2008) |
| **Medir en vez de creer** | Los despliegues y las políticas se comprueban con **conteos de peticiones**, no con `kubectl get` | Jonassen y Hung (2006): diagnosticar es formular y probar hipótesis |
| **Andamiaje que se retira** | Pasos 0 a 7 con comandos; Paso 8 solo con objetivo y verificador | Kalyuga et al. (2003) |

```bash
mkdir -p ~/lab-ckad-2 && cd ~/lab-ckad-2
echo "# Predicciones del laboratorio 2" > predicciones.md
```

---

## Objetivo

Al terminar vas a poder responder, señalando evidencia en tu terminal:

1. ¿Qué hace un CRD por sí solo, y qué hace falta para que un recurso propio «haga algo»?
2. ¿Por qué `kubectl auth can-i patch anuncios/status` puede decir `no` aunque el permiso
   exista?
3. ¿Qué forma de consumir un ConfigMap se actualiza sola y cuáles no?
4. ¿Por qué el perfil por defecto de `kubectl debug` es rechazado en un namespace
   `restricted`?
5. ¿Cuántas peticiones fallan en un rolling update, en un `Recreate` y en un blue/green?
6. ¿Qué hace un solo guion (`-`) de más en una NetworkPolicy?
7. Al migrar de Ingress a Gateway API, ¿qué se traduce solo y qué **se pierde en silencio**?

**Requisito:** el Laboratorio 1 de este módulo, y la imagen `pulso:1.0` en tu Docker (si la
borraste, repite el Paso 1.2 del Laboratorio 1: `docker build -t pulso:1.0 .` dentro de
`~/lab-ckad-1/pulso`).

**Entorno verificado** (el 26 de septiembre de 2026, en la máquina donde se capturaron todas
las salidas): Docker Engine 29.8.1, `kind` v0.33.0, `kubectl` v1.37.0, Helm v4.3.0, `jq`,
nodos `kindest/node:v1.37.0`, Calico v3.32.2, ingress-nginx controller v1.15.1, Gateway API
v1.6.2, NGINX Gateway Fabric 2.7.2 e `ingress2gateway` v1.2.0. Cuenta con **8 GiB de RAM
libres** y 1,5 GB de descargas.

```bash
kind version; kubectl version --client | head -1; helm version --short; jq --version
docker image inspect pulso:1.0 --format 'pulso:1.0 presente, {{.Size}} bytes'
```

> Todas las salidas marcadas **«Salida real de esta máquina»** se capturaron ejecutando los
> comandos. Los nombres de Pods, IPs y conteos serán **distintos en tu máquina**; la forma
> de la salida no.

---

## Paso 0: Un clúster con Calico (12 min)

### 0.1 ¿Hace falta Calico? Medido, no supuesto

Durante años la regla fue «`kind` trae `kindnet`, y `kindnet` no aplica NetworkPolicies:
para practicarlas instala Calico». **Esa regla ya no es cierta.** Se midió en `kind` v0.33
(`kindnetd:v20260820`, un clúster `kind` normal como el del Laboratorio 1): con una política
«denegar todo» el `wget` se agotó a los 5,00 s, y al borrarla volvió a responder. El Anexo
A3.1 del Laboratorio 2 del módulo 5 trae el script para medirlo tú mismo.

Entonces, ¿por qué Calico hoy? Por tres cosas que `kindnet` no tiene y que vas a usar:

- **Whisker**, una consola que muestra cada flujo de red con su veredicto (`Allow` o `Deny`)
  **y el nombre de la política que lo decidió**. Es la mejor forma de probar que una
  política funciona.
- **Negación explícita** (`action: Deny`) con **orden**, algo que la NetworkPolicy de
  Kubernetes no sabe expresar.
- Es un CNI de producción real, con operador, y vas a ver cómo se instala uno.

### 0.2 El clúster, sin CNI

```bash
cd ~/lab-ckad-2
cat > kind-ckad-red.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ckad-red
networking:
  disableDefaultCNI: true        # sin kindnet: la red la pone Calico
  podSubnet: "192.168.0.0/16"    # el rango por defecto de Calico
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
  - containerPort: 30080
    hostPort: 8081
    protocol: TCP
- role: worker
  image: kindest/node:v1.37.0
- role: worker
  image: kindest/node:v1.37.0
EOF

kind create cluster --config kind-ckad-red.yaml
kubectl get nodes
```

**Salida real de esta máquina:**

```
NAME                     STATUS     ROLES           AGE   VERSION
ckad-red-control-plane   NotReady   control-plane   14s   v1.37.0
ckad-red-worker          NotReady   <none>          0s    v1.37.0
ckad-red-worker2         NotReady   <none>          0s    v1.37.0
```

`NotReady`: sin CNI no hay red de Pods. Los dos puertos publicados se usan en el Paso 7:
`8080` para el Ingress y `8081` para el Gateway.

### 0.3 Calico, según la guía oficial para `kind`

```bash
C=https://raw.githubusercontent.com/projectcalico/calico/v3.32.2/manifests
kubectl create -f $C/v1_crd_projectcalico_org.yaml >/dev/null
kubectl create -f $C/tigera-operator.yaml >/dev/null
kubectl wait --for=condition=Established crd/installations.operator.tigera.io --timeout=180s
kubectl create -f $C/custom-resources.yaml
```

**Salida real de esta máquina:**

```
customresourcedefinition.apiextensions.k8s.io/installations.operator.tigera.io condition met
installation.operator.tigera.io/default created
apiserver.operator.tigera.io/default created
goldmane.operator.tigera.io/default created
whisker.operator.tigera.io/default created
```

> **Por qué está ese `kubectl wait`.** La primera vez que se preparó este laboratorio,
> `custom-resources.yaml` falló con `no matches for kind "Installation"`: el operador crea
> sus propias CRDs unos segundos **después** de arrancar, y el `create` llegó antes. Es una
> carrera. Esperar a que la CRD esté `Established` la elimina.

`custom-resources.yaml` declara cuatro objetos: la instalación, el API server de Calico,
**Goldmane** (agrega los flujos) y **Whisker** (los muestra). Es el patrón operador del
Paso 1, aplicado a la red: declaras qué quieres y un controlador lo construye.

```bash
kubectl wait --for=condition=Ready node --all --timeout=420s
kubectl wait --for=condition=Available tigerastatus --all --timeout=420s
kubectl get tigerastatus
kind load docker-image pulso:1.0 --name ckad-red
```

**Salida real de esta máquina:**

```
node/ckad-red-control-plane condition met
node/ckad-red-worker condition met
node/ckad-red-worker2 condition met
tigerastatus.operator.tigera.io/apiserver condition met
tigerastatus.operator.tigera.io/calico condition met
tigerastatus.operator.tigera.io/goldmane condition met
tigerastatus.operator.tigera.io/ippools condition met
tigerastatus.operator.tigera.io/tiers condition met
tigerastatus.operator.tigera.io/whisker condition met
NAME        AVAILABLE   PROGRESSING   DEGRADED   SINCE   MESSAGE
apiserver   True        False         False      30s     All objects available
calico      True        False         False      25s     All objects available
goldmane    True        False         False      0s      All objects available
ippools     True        False         False      2m5s    All objects available
tiers       True        False         False      25s     All objects available
whisker     True        False         False      10s     All objects available
Image: "pulso:1.0" with ID "sha256:ca2a57e04f95fa70e68d31379add6264fa0dd63b965f2ed1c352a1fd8cea2b5b" not yet present on node "ckad-red-worker", loading...
Image: "pulso:1.0" with ID "sha256:ca2a57e04f95fa70e68d31379add6264fa0dd63b965f2ed1c352a1fd8cea2b5b" not yet present on node "ckad-red-worker2", loading...
Image: "pulso:1.0" with ID "sha256:ca2a57e04f95fa70e68d31379add6264fa0dd63b965f2ed1c352a1fd8cea2b5b" not yet present on node "ckad-red-control-plane", loading...
```

---

## Paso 1: Un CRD propio y un controlador de juguete (25 min)

El currículo del CKAD pide **descubrir y usar** recursos que amplían Kubernetes. Para
entenderlos de verdad, vas a crear uno y a escribir, en 30 líneas de shell, el controlador
que le da vida.

```bash
kubectl create namespace lab2
kubectl config set-context --current --namespace=lab2
```

### 1.1 El tipo: `Anuncio`

```bash
cat > crd-anuncio.yaml <<'EOF'
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: anuncios.ckad.example.com      # <plural>.<grupo>, obligatorio
spec:
  group: ckad.example.com
  scope: Namespaced
  names:
    kind: Anuncio
    singular: anuncio
    plural: anuncios
    shortNames: [anu]
  versions:
  - name: v1
    served: true
    storage: true
    subresources:
      status: {}                       # el status solo lo escribe el controlador
    additionalPrinterColumns:
    - { name: Mensaje,   type: string,  jsonPath: .spec.mensaje }
    - { name: Replicas,  type: integer, jsonPath: .spec.replicas }
    - { name: Publicado, type: boolean, jsonPath: .status.publicado }
    - { name: Edad,      type: date,    jsonPath: .metadata.creationTimestamp }
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required: [mensaje]
            x-kubernetes-validations:
            - rule: "!(self.urgente && self.replicas < 2)"
              message: "un anuncio urgente necesita al menos 2 replicas"
            properties:
              mensaje:
                type: string
                description: "Texto que publicara la aplicacion."
                maxLength: 40
              replicas:
                type: integer
                description: "Cuantas copias de la aplicacion publican el anuncio."
                minimum: 1
                maximum: 5
                default: 1
              urgente:
                type: boolean
                default: false
          status:
            type: object
            properties:
              publicado:
                type: boolean
              replicasListas:
                type: integer
EOF

kubectl apply -f crd-anuncio.yaml
kubectl wait --for=condition=Established crd/anuncios.ckad.example.com
kubectl api-resources --api-group=ckad.example.com
```

**Salida real de esta máquina:**

```
customresourcedefinition.apiextensions.k8s.io/anuncios.ckad.example.com created
customresourcedefinition.apiextensions.k8s.io/anuncios.ckad.example.com condition met
NAME       SHORTNAMES   APIVERSION            NAMESPACED   KIND
anuncios   anu          ckad.example.com/v1   true         Anuncio
```

Tu clúster ya tiene un endpoint REST nuevo, con nombre corto `anu`. Y `kubectl explain`
funciona sobre él, porque lee el esquema que acabas de declarar (dale unos segundos: la
primera vez puede responder `couldn't find resource` mientras el apiserver publica el
esquema):

```bash
sleep 5
kubectl explain anuncio.spec
```

**Salida real de esta máquina:**

```
GROUP:      ckad.example.com
KIND:       Anuncio
VERSION:    v1

FIELD: spec <Object>


DESCRIPTION:
    <empty>
FIELDS:
  mensaje	<string> -required-
    Texto que publicara la aplicacion.

  replicas	<integer>
    Cuantas copias de la aplicacion publican el anuncio.

  urgente	<boolean>
    <no description>
```

### 1.2 El apiserver valida por ti

🔮 **Predice:** de estos tres anuncios, ¿cuáles rechaza el apiserver, y con qué mensaje?

```bash
cat > anuncios-malos.yaml <<'EOF'
apiVersion: ckad.example.com/v1
kind: Anuncio
metadata: { name: sin-mensaje }
spec: { replicas: 2 }
---
apiVersion: ckad.example.com/v1
kind: Anuncio
metadata: { name: demasiadas }
spec: { mensaje: "hola", replicas: 9 }
---
apiVersion: ckad.example.com/v1
kind: Anuncio
metadata: { name: urgente-solo }
spec: { mensaje: "se cae el sistema", urgente: true }
EOF

kubectl apply -f anuncios-malos.yaml
```

**Salida real de esta máquina:**

```
Error from server (Invalid): error when creating "anuncios-malos.yaml": Anuncio.ckad.example.com "sin-mensaje" is invalid: [spec.mensaje: Required value, <nil>: Invalid value: null: some validation rules were not checked because the object was invalid; correct the existing errors to complete validation]
Error from server (Invalid): error when creating "anuncios-malos.yaml": Anuncio.ckad.example.com "demasiadas" is invalid: spec.replicas: Invalid value: 9: spec.replicas in body should be less than or equal to 5
Error from server (Invalid): error when creating "anuncios-malos.yaml": Anuncio.ckad.example.com "urgente-solo" is invalid: spec: Invalid value: un anuncio urgente necesita al menos 2 replicas
```

Tres rechazos, tres mecanismos: `required`, `maximum` y una regla **CEL**
(`x-kubernetes-validations`) que relaciona dos campos. Ninguno necesitó código: la
validación vive en el esquema. Ahora uno válido:

```bash
kubectl apply -f - <<'EOF'
apiVersion: ckad.example.com/v1
kind: Anuncio
metadata: { name: bienvenida }
spec: { mensaje: "hola desde un CRD" }
EOF

kubectl get anuncios
kubectl get anu bienvenida -o jsonpath='{.spec}{"\n"}'
kubectl get deployments,pods
```

**Salida real de esta máquina:**

```
anuncio.ckad.example.com/bienvenida created
NAME         MENSAJE             REPLICAS   PUBLICADO   EDAD
bienvenida   hola desde un CRD   1                      1s
{"mensaje":"hola desde un CRD","replicas":1,"urgente":false}
No resources found in lab2 namespace.
```

Tres observaciones:

- Las columnas `MENSAJE`, `REPLICAS` y `PUBLICADO` son tus `additionalPrinterColumns`.
- `replicas: 1` y `urgente: false` aparecieron solos: son los `default` del esquema.
- **No hay ningún Deployment ni ningún Pod.** El anuncio es un registro en etcd, nada más.
  Un CRD define un **tipo**; alguien tiene que **actuar** sobre él.

Y una cuarta, que sorprende: intenta marcarlo como publicado tú mismo.

```bash
kubectl patch anu bienvenida --type=merge -p '{"status":{"publicado":true}}'
```

**Salida real de esta máquina:**

```
anuncio.ckad.example.com/bienvenida patched (no change)
```

`(no change)`. Con `subresources.status`, el `status` **no se escribe por el endpoint
normal**: tiene su propio endpoint (`/status`) y su propio permiso. Es la frontera entre lo
que el usuario pide (`spec`) y lo que el controlador observa (`status`).

### 1.3 El controlador

Un controlador es un bucle: **observa** el estado deseado (los anuncios), **compara** con el
real (los Deployments) y **actúa**. Este lo hace con `kubectl` dentro de un Pod. La imagen
oficial de `kubectl` es como tu `pulso`: **no trae shell**. Así que construyes una con el
mismo truco multi-stage del Laboratorio 1:

```bash
mkdir -p controlador
cat > controlador/Dockerfile <<'EOF'
# kubectl oficial no trae shell: tomamos solo su binario, como en el Laboratorio 1
FROM registry.k8s.io/kubectl:v1.37.0 AS kubectl
FROM busybox:1.37
COPY --from=kubectl /bin/kubectl /usr/local/bin/kubectl
USER 65534:65534
ENV HOME=/tmp
ENTRYPOINT ["sh", "/controlador/bucle.sh"]
EOF

docker build -q -t controlador:1.0 controlador/
kind load docker-image controlador:1.0 --name ckad-red
```

El bucle vive en un ConfigMap montado como archivo, y el Pod corre con su propia
ServiceAccount:

```bash
cat > controlador.yaml <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: controlador-anuncios
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: controlador-script
data:
  bucle.sh: |
    # Un controlador de juguete: observa Anuncios y los reconcilia en Deployments.
    echo "controlador arrancado como $(id -u), namespace $MI_NAMESPACE"
    while true; do
      for a in $(kubectl get anuncios -o name); do
        n=${a#*/}
        msg=$(kubectl get "$a" -o jsonpath='{.spec.mensaje}')
        rep=$(kubectl get "$a" -o jsonpath='{.spec.replicas}')
        uid=$(kubectl get "$a" -o jsonpath='{.metadata.uid}')
        kubectl apply -f - <<YAML
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: anuncio-$n
      labels: { anuncio: "$n" }
      ownerReferences:
      - { apiVersion: ckad.example.com/v1, kind: Anuncio, name: "$n", uid: "$uid" }
    spec:
      replicas: $rep
      selector: { matchLabels: { anuncio: "$n" } }
      template:
        metadata: { labels: { anuncio: "$n" } }
        spec:
          containers:
          - name: app
            image: pulso:1.0
            env: [{ name: VERSION, value: "$msg" }]
    YAML
        listas=$(kubectl get deploy "anuncio-$n" -o jsonpath='{.status.readyReplicas}')
        kubectl patch "$a" --subresource=status --type=merge \
          -p "{\"status\":{\"publicado\":true,\"replicasListas\":${listas:-0}}}"
      done
      sleep 5
    done
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: controlador-anuncios
spec:
  replicas: 1
  selector: { matchLabels: { app: controlador-anuncios } }
  template:
    metadata: { labels: { app: controlador-anuncios } }
    spec:
      serviceAccountName: controlador-anuncios
      containers:
      - name: controlador
        image: controlador:1.0
        env:
        - name: MI_NAMESPACE
          valueFrom: { fieldRef: { fieldPath: metadata.namespace } }
        volumeMounts: [{ name: script, mountPath: /controlador }]
      volumes:
      - name: script
        configMap: { name: controlador-script }
EOF

kubectl apply -f controlador.yaml
kubectl rollout status deploy/controlador-anuncios --timeout=90s
sleep 8
kubectl logs deploy/controlador-anuncios | head -3
```

**Salida real de esta máquina:**

```
serviceaccount/controlador-anuncios created
configmap/controlador-script created
deployment.apps/controlador-anuncios created
Waiting for deployment "controlador-anuncios" rollout to finish: 0 of 1 updated replicas are available...
deployment "controlador-anuncios" successfully rolled out
controlador arrancado como 65534, namespace lab2
Error from server (Forbidden): anuncios.ckad.example.com is forbidden: User "system:serviceaccount:lab2:controlador-anuncios" cannot list resource "anuncios" in API group "ckad.example.com" in the namespace "lab2"
Error from server (Forbidden): anuncios.ckad.example.com is forbidden: User "system:serviceaccount:lab2:controlador-anuncios" cannot list resource "anuncios" in API group "ckad.example.com" in the namespace "lab2"
```

**Fallo productivo.** El controlador corre, pero su ServiceAccount no puede ni listar
anuncios. Nadie le dio permisos, y en RBAC **la ausencia de permiso es la negación**.
Compruébalo sin su token, suplantándola:

```bash
SA=system:serviceaccount:lab2:controlador-anuncios
kubectl auth can-i list anuncios --as=$SA
```

**Salida real de esta máquina:**

```
no
```

### 1.4 RBAC mínimo, y un segundo error que enseña más

```bash
cat > controlador-rbac.yaml <<'EOF'
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: controlador-anuncios
rules:
- apiGroups: ["ckad.example.com"]
  resources: ["anuncios"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["ckad.example.com"]
  resources: ["anuncios/status"]         # el subrecurso se autoriza aparte
  verbs: ["patch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "create", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: controlador-anuncios
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: controlador-anuncios
subjects:
- kind: ServiceAccount
  name: controlador-anuncios
  namespace: lab2
EOF

kubectl apply -f controlador-rbac.yaml
for v in "list anuncios" "patch anuncios/status" "create deployments" "delete deployments" "get secrets"; do
  printf '%-24s %s\n' "$v" "$(kubectl auth can-i $v --as=$SA)"
done
```

**Salida real de esta máquina:**

```
role.rbac.authorization.k8s.io/controlador-anuncios created
rolebinding.rbac.authorization.k8s.io/controlador-anuncios created
list anuncios            yes
patch anuncios/status    no
create deployments       yes
delete deployments       no
get secrets              no
```

🔮 **Predice:** `patch anuncios/status` dice `no`. ¿Falta el permiso, o la pregunta está mal
hecha?

```bash
kubectl auth can-i patch anuncios --subresource=status --as=$SA
sleep 15
kubectl logs deploy/controlador-anuncios --since=12s | head -2
kubectl get deployments
```

**Salida real de esta máquina:**

```
yes
deployment.apps/anuncio-bienvenida unchanged
Error from server (Forbidden): anuncios.ckad.example.com "bienvenida" is forbidden: User "system:serviceaccount:lab2:controlador-anuncios" cannot get resource "anuncios/status" in API group "ckad.example.com" in the namespace "lab2"
NAME                   READY   UP-TO-DATE   AVAILABLE   AGE
anuncio-bienvenida     1/1     1            1           14s
controlador-anuncios   1/1     1            1           24s
```

Dos lecciones en una salida:

- **La pregunta estaba mal hecha.** Para un subrecurso, `can-i` se pregunta con
  `--subresource=status`. Escrito como `anuncios/status` devuelve un `no` engañoso.
- **El permiso sí estaba incompleto.** El Deployment ya existe (el controlador sí pudo
  crearlo), pero `kubectl patch --subresource=status` también necesita **`get`** sobre
  `anuncios/status`. No lo sabías; el `Forbidden` te lo dijo con el verbo exacto. Así se
  construye un RBAC mínimo: **leyendo los `Forbidden`, no adivinando**.

```bash
kubectl patch role controlador-anuncios --type=json \
  -p '[{"op":"replace","path":"/rules/1/verbs","value":["get","patch"]}]'
sleep 12
kubectl get anuncios
```

**Salida real de esta máquina:**

```
role.rbac.authorization.k8s.io/controlador-anuncios patched
NAME         MENSAJE             REPLICAS   PUBLICADO   EDAD
bienvenida   hola desde un CRD   1          true        39s
```

### 1.5 El bucle de reconciliación, en vivo

🔮 **Predice:** cambias el anuncio a 3 réplicas y otro mensaje. ¿Qué pasa con el Deployment?
¿Y si borras el anuncio?

```bash
kubectl patch anu bienvenida --type=merge -p '{"spec":{"replicas":3,"mensaje":"ahora somos tres"}}'
sleep 20
kubectl get anuncios
kubectl get pods -l anuncio=bienvenida
P=$(kubectl get pod -l anuncio=bienvenida -o name | head -1)
kubectl get --raw "/api/v1/namespaces/lab2/pods/${P#pod/}:8080/proxy/"
kubectl delete anu bienvenida
sleep 5
kubectl get deployments
```

**Salida real de esta máquina:**

```
anuncio.ckad.example.com/bienvenida patched
NAME         MENSAJE            REPLICAS   PUBLICADO   EDAD
bienvenida   ahora somos tres   3          true        59s
NAME                                 READY   STATUS    RESTARTS   AGE
anuncio-bienvenida-fd69c8cd6-2zdzr   1/1     Running   0          19s
anuncio-bienvenida-fd69c8cd6-l7j6n   1/1     Running   0          18s
anuncio-bienvenida-fd69c8cd6-zb8v2   1/1     Running   0          19s
pulso ahora somos tres desde anuncio-bienvenida-fd69c8cd6-2zdzr
anuncio.ckad.example.com "bienvenida" deleted from lab2 namespace
NAME                   READY   UP-TO-DATE   AVAILABLE   AGE
controlador-anuncios   1/1     1            1           61s
```

Tres réplicas, el mensaje nuevo servido por `pulso`, y al borrar el anuncio **su Deployment
desapareció solo**. Eso último no lo hizo tu controlador: lo hizo el **recolector de basura**
de Kubernetes, porque el Deployment llevaba un `ownerReferences` apuntando al anuncio. Es el
patrón operador completo: **el CRD define el tipo, el controlador reconcilia, y los
`ownerReferences` limpian**.

> Un controlador real (hecho con `controller-runtime` o Kubebuilder) usa `watch` en lugar de
> un `sleep 5`, colas con reintentos y *finalizers*. La idea es la misma.

---

## Paso 2: ConfigMaps y Secrets (10 min)

La misma clave, consumida de tres formas:

```bash
cat > config-tres-formas.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: ajustes
data:
  COLOR: azul
---
apiVersion: v1
kind: Pod
metadata:
  name: lector
spec:
  containers:
  - name: app
    image: busybox:1.37
    command: ["sh", "-c", "while true; do echo \"$(date +%T) env=$COLOR volumen=$(cat /ajustes/COLOR) subPath=$(cat /fijo/color.txt)\"; sleep 5; done"]
    env:
    - name: COLOR                       # 1) como variable de entorno
      valueFrom: { configMapKeyRef: { name: ajustes, key: COLOR } }
    volumeMounts:
    - { name: ajustes, mountPath: /ajustes }                             # 2) directorio completo
    - { name: ajustes, mountPath: /fijo/color.txt, subPath: COLOR }      # 3) una clave con subPath
  volumes:
  - name: ajustes
    configMap: { name: ajustes }
EOF

kubectl apply -f config-tres-formas.yaml
kubectl wait --for=condition=Ready pod/lector --timeout=60s
kubectl logs lector
```

**Salida real de esta máquina:**

```
configmap/ajustes created
pod/lector created
pod/lector condition met
11:53:35 env=azul volumen=azul subPath=azul
```

🔮 **Predice:** cambias `COLOR` a `rojo`. ¿Cuál de las tres formas se entera, y cuándo?

```bash
kubectl patch configmap ajustes -p '{"data":{"COLOR":"rojo"}}'
for i in $(seq 1 18); do
  sleep 5; l=$(kubectl logs lector --tail=1); echo "$l"
  echo "$l" | grep -q "volumen=rojo" && break
done
```

**Salida real de esta máquina:**

```
configmap/ajustes patched
11:53:40 env=azul volumen=rojo subPath=azul
```

- **Variable de entorno:** congelada. Se resolvió al arrancar el contenedor.
- **Volumen (directorio completo):** actualizado. En esta máquina tardó lo que ves arriba;
  la documentación advierte que puede tardar hasta el periodo de sincronización del kubelet
  más la caché, cerca de un minuto.
- **`subPath`:** congelado **para siempre**. No es lentitud: es el comportamiento documentado.

Y un Secret, para desmontar un mito:

```bash
kubectl create secret generic credenciales --from-literal=clave='no-es-secreta'
kubectl get secret credenciales -o jsonpath='{.data.clave}{"\n"}'
kubectl get secret credenciales -o jsonpath='{.data.clave}' | base64 -d; echo
kubectl delete pod lector --now
```

**Salida real de esta máquina:**

```
secret/credenciales created
bm8tZXMtc2VjcmV0YQ==
no-es-secreta
pod "lector" deleted from lab2 namespace
```

`base64` es **codificación, no cifrado**: cualquiera con `get secrets` lee la clave. Lo que
protege un Secret es el RBAC (por eso tu controlador tiene `get secrets: no`) y, si un
administrador lo activa, el cifrado en reposo de etcd.

---

## Paso 3: Pod Security `restricted` y `securityContext` (15 min)

### 3.1 Un namespace que no perdona

```bash
kubectl create namespace seguro
kubectl label namespace seguro \
  pod-security.kubernetes.io/enforce=restricted pod-security.kubernetes.io/enforce-version=latest
kubectl -n seguro run raiz --image=busybox:1.37 -- sleep 3600
```

**Salida real de esta máquina:**

```
namespace/seguro created
namespace/seguro labeled
Error from server (Forbidden): pods "raiz" is forbidden: violates PodSecurity "restricted:latest": allowPrivilegeEscalation != false (container "raiz" must set securityContext.allowPrivilegeEscalation=false), unrestricted capabilities (container "raiz" must set securityContext.capabilities.drop=["ALL"]), runAsNonRoot != true (pod or container "raiz" must set securityContext.runAsNonRoot=true), seccompProfile (pod or container "raiz" must set securityContext.seccompProfile.type to "RuntimeDefault" or "Localhost")
```

El admission controller de **Pod Security** te devolvió la lista exacta de lo que falta. Ese
mensaje **es** la receta. `pulso`, con su base distroless `nonroot`, la cumple entera:

```bash
cat > pulso-seguro.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: pulso-seguro
  namespace: seguro
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile: { type: RuntimeDefault }
  containers:
  - name: app
    image: pulso:1.0
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: { drop: ["ALL"] }
EOF

kubectl apply -f pulso-seguro.yaml
kubectl -n seguro wait --for=condition=Ready pod/pulso-seguro --timeout=60s
kubectl -n seguro get pod pulso-seguro -o jsonpath='UID real del contenedor: {.status.containerStatuses[0].user.linux.uid}{"\n"}'
```

**Salida real de esta máquina:**

```
pod/pulso-seguro created
pod/pulso-seguro condition met
UID real del contenedor: 65532
```

`readOnlyRootFilesystem: true` no le molesta a `pulso` porque no escribe en disco. Una app
que escribe en `/tmp` necesitaría un `emptyDir` montado ahí.

### 3.2 Depurar dentro de un namespace `restricted`

🔮 **Predice:** usas el mismo `kubectl debug` del Laboratorio 1. ¿Funciona aquí?

```bash
kubectl -n seguro debug pulso-seguro --image=busybox:1.37 --target=app -c mirar1 -- id
```

**Salida real de esta máquina:**

```
Targeting container "app". If you don't see processes from this container it may be because the container runtime doesn't support this feature.
Error from server (Forbidden): pods "pulso-seguro" is forbidden: violates PodSecurity "restricted:latest": allowPrivilegeEscalation != false (container "mirar1" must set securityContext.allowPrivilegeEscalation=false), unrestricted capabilities (container "mirar1" must set securityContext.capabilities.drop=["ALL"]; container "mirar1" must not include "SYS_PTRACE" in securityContext.capabilities.add)
```

**Rechazado por Pod Security.** El perfil por defecto (`general`) le añade `SYS_PTRACE` al
depurador, y `restricted` no lo admite. Prueba el perfil `restricted`:

```bash
kubectl -n seguro debug pulso-seguro --image=busybox:1.37 --target=app -c mirar2 --profile=restricted -- id
for i in $(seq 1 30); do   # el primer pull de busybox en ese nodo tarda unos segundos
  m=$(kubectl -n seguro get pod pulso-seguro -o jsonpath='{.status.ephemeralContainerStatuses[?(@.name=="mirar2")].state.waiting.message}')
  [ -n "$m" ] && break; sleep 2
done; echo "$m"
```

**Salida real de esta máquina:**

```
Targeting container "app". If you don't see processes from this container it may be because the container runtime doesn't support this feature.
container has runAsNonRoot and image will run as root (pod: "pulso-seguro_seguro(be417e8e-e587-4a31-82ed-8b17225536da)", container: mirar2)
```

Pasó la admisión, pero el kubelet no lo arranca (`CreateContainerConfigError`): busybox corre como root y el Pod exige
`runAsNonRoot`. Falta **un** campo que ningún perfil pone: el usuario. Para eso existe
`--custom`, un fragmento de especificación de contenedor que se mezcla con el perfil:

```bash
cat > depurador-nonroot.yaml <<'EOF'
securityContext:
  runAsUser: 65532
EOF

kubectl -n seguro debug pulso-seguro --image=busybox:1.37 --target=app -c mirar3 \
  --profile=restricted --custom=depurador-nonroot.yaml -- \
  sh -c 'id; grep -E "^(Uid|NoNewPrivs|CapEff|Seccomp):" /proc/1/status; ls /proc/1/root/'
sleep 6
kubectl -n seguro logs pulso-seguro -c mirar3
```

**Salida real de esta máquina:**

```
Targeting container "app". If you don't see processes from this container it may be because the container runtime doesn't support this feature.
uid=65532 gid=0(root) groups=0(root)
Uid:	65532	65532	65532	65532
CapEff:	0000000000000000
NoNewPrivs:	1
Seccomp:	2
ls: /proc/1/root/: Permission denied
```

La prueba del endurecimiento, **vista desde dentro**: `NoNewPrivs: 1`
(`allowPrivilegeEscalation: false`), `CapEff: 0000000000000000` (ninguna capacidad),
`Seccomp: 2` (filtro activo). Y el precio: ni siquiera tu depurador puede leer
`/proc/1/root/`. **Seguridad y depurabilidad tiran en direcciones opuestas**; los perfiles de
`kubectl debug` existen para negociar entre las dos.

---

## Paso 4: LimitRange y ResourceQuota (8 min)

```bash
kubectl create namespace cuotas
cat > cuotas.yaml <<'EOF'
apiVersion: v1
kind: LimitRange
metadata:
  name: por-defecto
  namespace: cuotas
spec:
  limits:
  - type: Container
    default:        { cpu: 200m, memory: 64Mi }   # limits que se rellenan solos
    defaultRequest: { cpu: 50m,  memory: 32Mi }   # requests que se rellenan solos
    max:            { memory: 256Mi }
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: presupuesto
  namespace: cuotas
spec:
  hard:
    pods: "3"
    requests.memory: 100Mi
    limits.memory: 200Mi
EOF

kubectl apply -f cuotas.yaml
kubectl -n cuotas run a --image=pulso:1.0
kubectl -n cuotas get pod a -o jsonpath='{.spec.containers[0].resources}{"\n"}'
```

**Salida real de esta máquina:**

```
namespace/cuotas created
limitrange/por-defecto created
resourcequota/presupuesto created
pod/a created
{"limits":{"cpu":"200m","memory":"64Mi"},"requests":{"cpu":"50m","memory":"32Mi"}}
```

No escribiste `resources` y el Pod los tiene: **LimitRange muta** (rellena defaults).
🔮 **Predice:** la cuota admite 3 Pods. ¿Qué pasa con el cuarto, y con un Deployment de 2
réplicas?

```bash
kubectl -n cuotas run b --image=pulso:1.0
kubectl -n cuotas run c --image=pulso:1.0
kubectl -n cuotas run d --image=pulso:1.0
kubectl -n cuotas create deployment rep --image=pulso:1.0 --replicas=2
sleep 5
kubectl -n cuotas get deployment rep
kubectl -n cuotas get events --field-selector reason=FailedCreate -o jsonpath='{.items[0].message}' | cut -c1-150; echo
```

**Salida real de esta máquina:**

```
pod/b created
pod/c created
Error from server (Forbidden): pods "d" is forbidden: exceeded quota: presupuesto, requested: limits.memory=64Mi,pods=1,requests.memory=32Mi, used: limits.memory=192Mi,pods=3,requests.memory=96Mi, limited: limits.memory=200Mi,pods=3,requests.memory=100Mi
deployment.apps/rep created
NAME   READY   UP-TO-DATE   AVAILABLE   AGE
rep    0/2     0            0           5s
Error creating: pods "rep-7cb8b75cdb-sfjc4" is forbidden: exceeded quota: presupuesto, requested: limits.memory=64Mi,pods=1,requests.memory=32Mi, used
```

El Pod suelto recibe el `403` **en tu cara**. El Deployment, en cambio, se crea sin error y
se queda en `0/2` **en silencio**: quien choca con la cuota es el ReplicaSet, al crear los
Pods, y el mensaje solo aparece **en los eventos del ReplicaSet**. En el examen, un
Deployment en `0/N` sin Pods se diagnostica bajando un nivel: `describe rs`.

---

## Paso 5: Estrategias de despliegue, medidas (25 min)

Aquí no vas a creer lo que dice `kubectl rollout status`: vas a **contar peticiones**. Dos
herramientas, ejecutadas desde un Pod `cliente`:

```bash
kubectl create namespace despliegues
kubectl config set-context --current --namespace=despliegues
kubectl run cliente --image=busybox:1.37 --restart=Never -- sleep 7200
kubectl wait --for=condition=Ready pod/cliente --timeout=60s

cat > contar.sh <<'EOF'
#!/usr/bin/env bash
# contar.sh <service> <n>: manda n peticiones desde el Pod cliente y cuenta quien respondio
kubectl exec cliente -- sh -c "for i in \$(seq 1 ${2:-100}); do wget -qO- -T 2 http://$1; done" \
  | sed 's/ desde.*//' | sort | uniq -c
EOF

cat > medir.sh <<'EOF'
#!/usr/bin/env bash
# medir.sh <service> <segundos>: una peticion cada 0,2 s; cuenta respuestas por version y FALLOS
kubectl exec cliente -- sh -c "fin=\$((\$(date +%s)+$2)); while [ \$(date +%s) -lt \$fin ]; do r=\$(wget -qO- -T 1 http://$1 2>/dev/null); echo \"\${r:-FALLO}\" | cut -d' ' -f1-2; sleep 0.2; done" | sort | uniq -c
EOF

chmod +x contar.sh medir.sh
```

### 5.1 RollingUpdate frente a Recreate

```bash
cat > rolling.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  annotations:
    kubernetes.io/change-cause: "v1 inicial"
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  selector: { matchLabels: { app: web } }
  template:
    metadata: { labels: { app: web } }
    spec:
      containers:
      - name: app
        image: pulso:1.0
        env:
        - { name: VERSION, value: "v1" }
        - { name: STARTUP_SECONDS, value: "3" }
        readinessProbe: { httpGet: { path: /readyz, port: 8080 }, periodSeconds: 1 }
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector: { app: web }
  ports: [{ port: 80, targetPort: 8080 }]
EOF

kubectl apply -f rolling.yaml
kubectl rollout status deploy/web --timeout=90s
```

🔮 **Predice:** mientras cambias de v1 a v2, mandas una petición cada 0,2 s durante 20 s.
¿Cuántas fallan con `maxUnavailable: 0`? ¿Y con `Recreate`?

```bash
./medir.sh web 20 > r1.txt & sleep 3; kubectl set env deploy/web VERSION=v2 >/dev/null; wait
echo "== RollingUpdate"; cat r1.txt

kubectl patch deploy web --type=json -p '[{"op":"replace","path":"/spec/strategy","value":{"type":"Recreate"}}]'
./medir.sh web 20 > r2.txt & sleep 3; kubectl set env deploy/web VERSION=v3 >/dev/null; wait
echo "== Recreate"; cat r2.txt
```

**Salida real de esta máquina:**

```
== RollingUpdate
      2 FALLO
     56 pulso v1
     32 pulso v2
deployment.apps/web patched
== Recreate
      5 FALLO
     15 pulso v2
     57 pulso v3
```

`Recreate` mata todo antes de crear lo nuevo: los `FALLO` son su ventana de indisponibilidad,
garantizada. Pero mira el `RollingUpdate`: aun con `maxUnavailable: 0`, **puede** fallar
alguna petición. Al preparar este laboratorio, tres rondas iguales dieron 3, 2 y 0 fallos. Es
una carrera: el kubelet manda `SIGTERM` al Pod viejo, `pulso` muere al instante, y
`kube-proxy` todavía no lo sacó de sus reglas.

La cura clásica es que el Pod **tarde un poco en morir**: un `preStop` que espere mientras
el resto del clúster se entera. Kubernetes trae una acción `sleep` nativa para eso
(compruébalo: `kubectl explain pod.spec.containers.lifecycle.preStop.sleep`):

```bash
kubectl patch deploy web --type=json -p '[
  {"op":"replace","path":"/spec/strategy","value":{"type":"RollingUpdate","rollingUpdate":{"maxSurge":1,"maxUnavailable":0}}},
  {"op":"add","path":"/spec/template/spec/containers/0/lifecycle","value":{"preStop":{"sleep":{"seconds":5}}}}]'
kubectl rollout status deploy/web --timeout=120s
./medir.sh web 30 > r3.txt & sleep 3; kubectl set env deploy/web VERSION=v4 >/dev/null; wait
echo "== RollingUpdate + preStop sleep 5"; cat r3.txt
```

**Salida real de esta máquina:**

```
deployment.apps/web patched
Waiting for deployment "web" rollout to finish: 1 out of 4 new replicas have been updated...
Waiting for deployment "web" rollout to finish: 2 out of 4 new replicas have been updated...
Waiting for deployment "web" rollout to finish: 3 out of 4 new replicas have been updated...
Waiting for deployment "web" rollout to finish: 1 old replicas are pending termination...
deployment "web" successfully rolled out
== RollingUpdate + preStop sleep 5
      1 FALLO
     60 pulso v3
     77 pulso v4
```

El `preStop` achica la carrera, pero no garantiza cero: en esta corrida quedó **1** `FALLO`
entre 138 peticiones (en las corridas de preparación, 0). Y ojo con cómo mide `medir.sh`: con
`-T 1`, una respuesta que tarda más de un segundo también cuenta como `FALLO`. Compara los
tres números de tu máquina: `Recreate` siempre pierde una ventana entera; las otras dos, a lo
sumo unas pocas peticiones sueltas.

### 5.2 El historial, y un orden que importa

```bash
kubectl rollout history deploy/web
kubectl set env deploy/web VERSION=v5 >/dev/null
kubectl annotate deploy/web kubernetes.io/change-cause="v5: prueba de historial" --overwrite
kubectl rollout status deploy/web --timeout=120s >/dev/null
kubectl rollout history deploy/web | tail -3
```

**Salida real de esta máquina:**

```
deployment.apps/web
REVISION  CHANGE-CAUSE
1         v1 inicial
2         v1 inicial
3         v1 inicial
4         v1 inicial
5         v1 inicial

deployment.apps/web annotated
5         v1 inicial
6         v5: prueba de historial
```

Mira las revisiones 1 a 5: **todas dicen `v1 inicial`**. La anotación vive en el Deployment
(la escribiste en `rolling.yaml`) y cada revisión nueva **copia la que haya en ese momento**.
Nadie la actualizó en los `set env` ni en los `patch`, así que el historial miente cuatro
veces. Solo la revisión 6, anotada a propósito, dice la verdad.

**Primero el cambio, después la anotación.** `change-cause` se copia a la revisión **más
nueva**. Si anotas **antes** del cambio, sobrescribes la causa de la revisión que ya
existía, y el historial miente. Se comprobó en esta versión de Kubernetes: anotando antes,
la revisión anterior quedó con el texto del cambio que aún no se había hecho. Y `--record`
está obsoleto.

```bash
kubectl rollout undo deploy/web
kubectl rollout status deploy/web --timeout=120s >/dev/null
./contar.sh web 10
kubectl delete -f rolling.yaml
```

**Salida real de esta máquina:**

```
Warning: resource deployments/web was previously managed with 'kubectl apply'. Rolling back will not update the kubectl.kubernetes.io/last-applied-configuration annotation, which may cause unexpected behavior on future 'kubectl apply' operations. Consider using 'kubectl apply' with your previous configuration file instead.
deployment.apps/web rolled back
      8 pulso v4
      2 pulso v5
deployment.apps "web" deleted from despliegues namespace
service "web" deleted from despliegues namespace
```

El `undo` volvió a v4, pero 2 de las 10 respuestas todavía vinieron de v5, **después** de que
`rollout status` terminó. Los Pods de v5 seguían en su `preStop` de 5 s, y en ese tiempo
algunas conexiones aún les llegaban mientras el clúster actualizaba sus reglas. Es exactamente
lo que el `preStop` compra: esas peticiones reciben respuesta en vez de un `FALLO`.

### 5.3 Blue/green: un interruptor en el Service

```bash
cat > blue-green.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-azul
spec:
  replicas: 3
  selector: { matchLabels: { app: web, version: azul } }
  template:
    metadata: { labels: { app: web, version: azul } }
    spec:
      containers:
      - name: app
        image: pulso:1.0
        env: [{ name: VERSION, value: "AZUL (v1)" }]
        readinessProbe: { httpGet: { path: /readyz, port: 8080 }, periodSeconds: 2 }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-verde
spec:
  replicas: 3
  selector: { matchLabels: { app: web, version: verde } }
  template:
    metadata: { labels: { app: web, version: verde } }
    spec:
      containers:
      - name: app
        image: pulso:1.0
        env: [{ name: VERSION, value: "VERDE (v2)" }]
        readinessProbe: { httpGet: { path: /readyz, port: 8080 }, periodSeconds: 2 }
---
apiVersion: v1
kind: Service
metadata:
  name: web-bg
spec:
  selector: { app: web, version: azul }      # el interruptor: una sola etiqueta
  ports: [{ port: 80, targetPort: 8080 }]
EOF

kubectl apply -f blue-green.yaml
kubectl rollout status deploy/web-azul --timeout=90s >/dev/null
kubectl rollout status deploy/web-verde --timeout=90s >/dev/null
./contar.sh web-bg 20
```

**Salida real de esta máquina:**

```
deployment.apps/web-azul created
deployment.apps/web-verde created
service/web-bg created
     20 pulso AZUL (v1)
```

Los **dos** Deployments están completos y corriendo; el Service solo mira al azul. 🔮
**Predice:** al cambiar el selector, ¿cuántas peticiones se pierden?

```bash
kubectl exec cliente -- sh -c 'for i in $(seq 1 40); do echo "$(date +%T) $(wget -qO- -T 1 http://web-bg | cut -d" " -f2)"; sleep 0.25; done' > corte.txt &
sleep 3; kubectl patch service web-bg -p '{"spec":{"selector":{"version":"verde"}}}'; wait
awk '{print $2}' corte.txt | uniq -c
grep -c -v -E 'AZUL|VERDE' corte.txt
```

**Salida real de esta máquina:**

```
service/web-bg patched
     12 AZUL
     28 VERDE
0
```

Una columna de azules, una de verdes, y **cero** respuestas vacías (el último número). El
cambio es un solo `patch`, y el rollback es el mismo `patch` al revés, porque el azul **sigue
vivo**. Esa es toda la gracia de blue/green, y también su costo: pagas el doble de réplicas.

### 5.4 Canary: el porcentaje son las réplicas

```bash
kubectl delete -f blue-green.yaml
cat > canary.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-estable
spec:
  replicas: 4
  selector: { matchLabels: { app: tienda, pista: estable } }
  template:
    metadata: { labels: { app: tienda, pista: estable } }
    spec:
      containers:
      - name: app
        image: pulso:1.0
        env: [{ name: VERSION, value: "v1-estable" }]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-canary
spec:
  replicas: 1
  selector: { matchLabels: { app: tienda, pista: canary } }
  template:
    metadata: { labels: { app: tienda, pista: canary } }
    spec:
      containers:
      - name: app
        image: pulso:1.0
        env: [{ name: VERSION, value: "v2-canary" }]
---
apiVersion: v1
kind: Service
metadata:
  name: tienda
spec:
  selector: { app: tienda }        # sin "pista": ve a los dos Deployments
  ports: [{ port: 80, targetPort: 8080 }]
EOF

kubectl apply -f canary.yaml
kubectl rollout status deploy/web-estable --timeout=90s >/dev/null
kubectl rollout status deploy/web-canary --timeout=90s >/dev/null
sleep 2
./contar.sh tienda 200
kubectl scale deploy/web-canary --replicas=4
kubectl rollout status deploy/web-canary --timeout=90s >/dev/null
sleep 2
./contar.sh tienda 200
```

**Salida real de esta máquina:**

```
deployment.apps "web-azul" deleted from despliegues namespace
deployment.apps "web-verde" deleted from despliegues namespace
service "web-bg" deleted from despliegues namespace
deployment.apps/web-estable created
deployment.apps/web-canary created
service/tienda created
    159 pulso v1-estable
     41 pulso v2-canary
deployment.apps/web-canary scaled
    107 pulso v1-estable
     93 pulso v2-canary
```

1 canary entre 5 Pods debería dar 20 %: aquí dio 41 de 200 (20,5 %), y en una corrida de
preparación, 49 de 200 (24,5 %). Con 4 y 4, 93 de 200 en vez de 100. **No hay ningún campo de
peso**: el reparto sale de la proporción de endpoints y `kube-proxy` elige al azar, así que el
porcentaje es **aproximado** y solo se controla escalando. En el Paso 7 verás un canary con
**pesos de verdad**.

```bash
kubectl delete -f canary.yaml
```

---

## Paso 6: NetworkPolicies con Calico, y cómo probar que funcionan (25 min)

### 6.1 El escenario

`web` (dos réplicas de `pulso`) en el namespace `tienda`, y cuatro clientes: `frontend` e
`intruso` en `tienda`, `prometheus` y `otro` en `monitoreo`.

```bash
kubectl create namespace tienda
kubectl create namespace monitoreo
kubectl label namespace monitoreo equipo=observabilidad
kubectl -n tienda create deployment web --image=pulso:1.0 --replicas=2
kubectl -n tienda expose deployment web --port=80 --target-port=8080
for p in frontend intruso; do kubectl -n tienda run $p --image=busybox:1.37 --labels=rol=$p -- sleep 7200; done
for p in prometheus otro; do kubectl -n monitoreo run $p --image=busybox:1.37 --labels=rol=$p -- sleep 7200; done
kubectl -n tienda rollout status deploy/web --timeout=90s
kubectl wait -A --for=condition=Ready pod -l rol --timeout=90s >/dev/null

cat > probar.sh <<'EOF'
#!/usr/bin/env bash
# probar.sh: desde cada Pod cliente, una peticion a web.tienda con 3 s de paciencia
for origen in tienda/frontend tienda/intruso monitoreo/prometheus monitoreo/otro; do
  ns=${origen%/*}; pod=${origen#*/}
  r=$(kubectl -n $ns exec $pod -- sh -c 'inicio=$(date +%s); wget -qO- -T 3 http://web.tienda 2>&1 | head -1; echo "($(( $(date +%s)-inicio )) s)"' | tr '\n' ' ')
  printf '%-22s -> %s\n' "$origen" "$r"
done
EOF

chmod +x probar.sh
echo "== sin politicas"; ./probar.sh
```

**Salida real de esta máquina:**

```
namespace/tienda created
namespace/monitoreo created
namespace/monitoreo labeled
deployment.apps/web created
service/web exposed
pod/frontend created
pod/intruso created
pod/prometheus created
pod/otro created
Waiting for deployment "web" rollout to finish: 0 of 2 updated replicas are available...
Waiting for deployment "web" rollout to finish: 1 of 2 updated replicas are available...
deployment "web" successfully rolled out
== sin politicas
tienda/frontend        -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
tienda/intruso         -> pulso v1 desde web-5dd5cd6fd7-cphpf (0 s)
monitoreo/prometheus   -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
monitoreo/otro         -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
```

Todos llegan en 0 s. **Sin NetworkPolicy, todo Pod habla con todo Pod.**

### 6.2 Denegar todo, abrir un camino

```bash
cat > np-1-denegar.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: denegar-entrada
  namespace: tienda
spec:
  podSelector: {}              # {} = TODOS los Pods del namespace
  policyTypes: [Ingress]
EOF

cat > np-2-frontend.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: permitir-frontend
  namespace: tienda
spec:
  podSelector: { matchLabels: { app: web } }
  policyTypes: [Ingress]
  ingress:
  - from:
    - podSelector: { matchLabels: { rol: frontend } }
    ports: [{ protocol: TCP, port: 8080 }]
EOF

kubectl apply -f np-1-denegar.yaml; sleep 3; echo "== denegar-entrada"; ./probar.sh
kubectl apply -f np-2-frontend.yaml; sleep 3; echo "== + permitir-frontend"; ./probar.sh
```

**Salida real de esta máquina:**

```
networkpolicy.networking.k8s.io/denegar-entrada created
== denegar-entrada
tienda/frontend        -> wget: download timed out (3 s)
tienda/intruso         -> wget: download timed out (3 s)
monitoreo/prometheus   -> wget: download timed out (3 s)
monitoreo/otro         -> wget: download timed out (3 s)
networkpolicy.networking.k8s.io/permitir-frontend created
== + permitir-frontend
tienda/frontend        -> pulso v1 desde web-5dd5cd6fd7-cphpf (0 s)
tienda/intruso         -> wget: download timed out (3 s)
monitoreo/prometheus   -> wget: download timed out (3 s)
monitoreo/otro         -> wget: download timed out (3 s)
```

La firma del bloqueo es **`download timed out` a los 3 s**: la política **descarta** (DROP)
en silencio. Guárdalo contra el `Connection refused` instantáneo de un Service sin endpoints.

### 6.3 Dos trampas de examen, medidas

**Trampa 1: el puerto.** 🔮 **Predice:** cambias el puerto de la política al del Service (80).

```bash
kubectl -n tienda patch netpol permitir-frontend --type=json -p '[{"op":"replace","path":"/spec/ingress/0/ports/0/port","value":80}]'
sleep 3; ./probar.sh | head -1
kubectl -n tienda patch netpol permitir-frontend --type=json -p '[{"op":"replace","path":"/spec/ingress/0/ports/0/port","value":8080}]'
```

**Salida real de esta máquina:**

```
networkpolicy.networking.k8s.io/permitir-frontend patched
tienda/frontend        -> wget: download timed out (3 s)
networkpolicy.networking.k8s.io/permitir-frontend patched
```

Bloqueado. La política se evalúa **en el Pod**, después de que el Service ya tradujo 80 a
8080. **Los puertos de una NetworkPolicy son los del contenedor**, no los del Service.

**Trampa 2: un guion.** Mira la única diferencia entre estas dos políticas:

```bash
cat > np-3-y.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: permitir-prometheus
  namespace: tienda
spec:
  podSelector: { matchLabels: { app: web } }
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: { matchLabels: { equipo: observabilidad } }   # UN elemento con
      podSelector: { matchLabels: { rol: prometheus } }                # dos selectores: Y
EOF

cat > np-4-o.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: permitir-prometheus-o
  namespace: tienda
spec:
  podSelector: { matchLabels: { app: web } }
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector: { matchLabels: { equipo: observabilidad } }   # un guion de mas...
    - podSelector: { matchLabels: { rol: prometheus } }                # DOS elementos: O
EOF

diff np-3-y.yaml np-4-o.yaml
```

🔮 **Predice:** ¿quién de `monitoreo` entra con cada una?

```bash
kubectl apply -f np-3-y.yaml; sleep 3; echo "== Y (un elemento)"; ./probar.sh; kubectl delete -f np-3-y.yaml
kubectl apply -f np-4-o.yaml; sleep 3; echo "== O (dos elementos)"; ./probar.sh; kubectl delete -f np-4-o.yaml
```

**Salida real de esta máquina:**

```
networkpolicy.networking.k8s.io/permitir-prometheus created
== Y (un elemento)
tienda/frontend        -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
tienda/intruso         -> wget: download timed out (3 s)
monitoreo/prometheus   -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
monitoreo/otro         -> wget: download timed out (3 s)
networkpolicy.networking.k8s.io "permitir-prometheus" deleted from tienda namespace
networkpolicy.networking.k8s.io/permitir-prometheus-o created
== O (dos elementos)
tienda/frontend        -> pulso v1 desde web-5dd5cd6fd7-cphpf (0 s)
tienda/intruso         -> wget: download timed out (3 s)
monitoreo/prometheus   -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
monitoreo/otro         -> pulso v1 desde web-5dd5cd6fd7-v848s (0 s)
networkpolicy.networking.k8s.io "permitir-prometheus-o" deleted from tienda namespace
```

- **Un elemento** con `namespaceSelector` **y** `podSelector`: «Pods `prometheus` **dentro
  de** namespaces de observabilidad». Solo entra `prometheus`.
- **Dos elementos** (un `-` de más): «**cualquier** Pod de namespaces de observabilidad,
  **o** Pods `prometheus` de mi propio namespace». Entra `otro`, que no debía.

Un carácter abrió un namespace entero, y `kubectl apply` no te avisó de nada.

### 6.4 Egress: la política que rompe el DNS

```bash
cat > np-5-salida.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-solo-a-web
  namespace: tienda
spec:
  podSelector: { matchLabels: { rol: frontend } }
  policyTypes: [Egress]
  egress:
  - to:
    - podSelector: { matchLabels: { app: web } }
    ports: [{ protocol: TCP, port: 8080 }]
EOF

kubectl apply -f np-5-salida.yaml; sleep 3
W=$(kubectl -n tienda get pod -l app=web -o jsonpath='{.items[0].status.podIP}')
kubectl -n tienda exec frontend -- sh -c "time wget -qO- -T 3 http://web.tienda; wget -qO- -T 3 http://$W:8080/"
```

**Salida real de esta máquina:**

```
networkpolicy.networking.k8s.io/frontend-solo-a-web created
wget: bad address 'web.tienda'
Command exited with non-zero status 1
real	0m 20.01s
user	0m 0.00s
sys	0m 0.00s
pulso v1 desde web-5dd5cd6fd7-cphpf
```

Por **IP** llega; por **nombre**, `bad address` después de **20 s** (los reintentos del
resolvedor, no el `-T 3` de `wget`, que ni siquiera llegó a conectar). La política de
salida solo permite hablar con `web`, y **CoreDNS no es `web`**. Toda política de egress
necesita su excepción de DNS:

```bash
cat > np-6-dns.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-dns
  namespace: tienda
spec:
  podSelector: { matchLabels: { rol: frontend } }
  policyTypes: [Egress]
  egress:
  - to:
    - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } }
      podSelector: { matchLabels: { k8s-app: kube-dns } }
    ports:
    - { protocol: UDP, port: 53 }
    - { protocol: TCP, port: 53 }
EOF

kubectl apply -f np-6-dns.yaml; sleep 3
kubectl -n tienda exec frontend -- sh -c "wget -qO- -T 3 http://web.tienda; wget -qO- -T 3 http://example.com | head -c 60; echo"
```

**Salida real de esta máquina:**

```
networkpolicy.networking.k8s.io/frontend-dns created
pulso v1 desde web-5dd5cd6fd7-cphpf
wget: download timed out
```

`web` responde por nombre, e internet sigue cerrado. Las políticas **se suman**: dos
políticas de egress sobre el mismo Pod permiten la unión de las dos.

### 6.5 La prueba definitiva: Whisker

Hasta aquí infieres el bloqueo por un timeout. Calico te deja **verlo**. Abre Whisker en
tu navegador (déjalo corriendo en otra terminal):

```bash
kubectl -n calico-system port-forward svc/whisker 8082:8081
```

y entra a <http://localhost:8082>. Verás cada flujo, con su acción y la política que lo
decidió. La misma información sale en JSON, lista para la terminal:

```bash
curl -s "localhost:8082/whisker-backend/flows?watch=false" | jq -r '.items[] | select(.action=="Deny")
  | "\(.action)  \(.source_namespace)/\(.source_name) -> \(.dest_namespace)/\(.dest_name):\(.dest_port)  por: \([.policies.enforced[]? | "\(.kind) \(.tier)/\(.name)"] | join(", "))"' | sort | uniq -c
```

**Salida real de esta máquina:**

```
      4 Deny  monitoreo/otro -> tienda/web-5dd5cd6fd7-*:8080  por: EndOfTier default/
      3 Deny  monitoreo/prometheus -> tienda/web-5dd5cd6fd7-*:8080  por: EndOfTier default/
      1 Deny  tienda/frontend -> kube-system/coredns-559f6c778d-*:53  por: EndOfTier default/
      1 Deny  tienda/frontend -> -/PUBLIC NETWORK:80  por: EndOfTier default/
      3 Deny  tienda/frontend -> tienda/web-5dd5cd6fd7-*:8080  por: EndOfTier default/
      6 Deny  tienda/intruso -> tienda/web-5dd5cd6fd7-*:8080  por: EndOfTier default/
```

Cada intento bloqueado de este paso, con origen, destino y puerto. `EndOfTier` significa
«ninguna regla lo permitió, así que cayó al final»: **eso es exactamente un default-deny**.
Si una política no bloquea nada, aquí lo ves como `Allow`, sin necesidad de adivinar.

### 6.6 Lo que Kubernetes no sabe decir: «denegar»

Una NetworkPolicy de Kubernetes **solo permite**; no existe una regla «deniega esto». Calico
sí la tiene, con orden de evaluación:

```bash
cat > gnp-cuarentena.yaml <<'EOF'
apiVersion: projectcalico.org/v3
kind: GlobalNetworkPolicy
metadata:
  name: cuarentena
spec:
  order: 10                              # menor = se evalua antes (las de Kubernetes van en 1000)
  selector: cuarentena == 'si'
  types: [Ingress, Egress]
  ingress:
  - action: Deny                         # una negacion EXPLICITA: Kubernetes no tiene esto
  egress:
  - action: Deny
EOF

kubectl apply -f gnp-cuarentena.yaml
kubectl -n tienda exec frontend -- wget -qO- -T 3 http://web.tienda
kubectl -n tienda label pod frontend cuarentena=si; sleep 3
kubectl -n tienda exec frontend -- wget -qO- -T 3 http://web.tienda
sleep 16
curl -s "localhost:8082/whisker-backend/flows?watch=false" | jq -r '.items[] | select(.action=="Deny" and .source_name=="frontend")
  | "\(.dest_name):\(.dest_port)  por: \([.policies.enforced[]? | "\(.kind) \(.tier)/\(.name)"] | join(", "))"' | sort | uniq -c
kubectl -n tienda label pod frontend cuarentena-
```

**Salida real de esta máquina:**

```
globalnetworkpolicy.projectcalico.org/cuarentena created
pulso v1 desde web-5dd5cd6fd7-cphpf
pod/frontend labeled
wget: bad address 'web.tienda'
command terminated with exit code 1
      1 coredns-559f6c778d-*:53  por: EndOfTier default/
      1 coredns-559f6c778d-*:53  por: GlobalNetworkPolicy default/cuarentena
      1 PUBLIC NETWORK:80  por: EndOfTier default/
      3 web-5dd5cd6fd7-*:8080  por: EndOfTier default/
pod/frontend unlabeled
```

`frontend` tenía permiso explícito para llegar a `web` (tu política del 6.2), y aun así la
cuarentena lo cortó en el primer paso: ni siquiera pudo resolver el nombre (`bad address`).
Whisker nombra a `GlobalNetworkPolicy default/cuarentena` como responsable de ese bloqueo al
DNS; las líneas con `EndOfTier` son los bloqueos de los pasos 6.2 a 6.4, que Whisker aún
recuerda. Es una herramienta de operación (aislar un Pod
comprometido sin tocar las políticas de la aplicación), no algo que el CKAD evalúe: allí la
NetworkPolicy estándar es todo el temario.

Cierra el `port-forward` de Whisker con `Ctrl+C`.

---

## Paso 7: De Ingress a Gateway API, una migración real (30 min)

> **Dónde está esto en el examen.** El currículo CKAD v1.35 pide *«usar reglas de Ingress
> para exponer aplicaciones»*. **Gateway API no aparece en el texto del currículo CKAD** (sí
> en el CKA, y su documentación solo está permitida en el examen CKA). Los pasos 7.1 y 7.2
> son temario; del 7.3 en adelante es **oficio**: lo que vas a hacer en tu trabajo.

### 7.1 Por qué migrar: ingress-nginx se retiró

El 11 de noviembre de 2025, SIG Network anunció el retiro de ingress-nginx: mantenimiento
«best-effort» hasta marzo de 2026 y, después, **ni versiones, ni parches, ni correcciones de
seguridad**, con la recomendación de migrar a Gateway API. Compruébalo en la fuente:

```bash
curl -s https://api.github.com/repos/kubernetes/ingress-nginx | jq '{archived, pushed_at}'
```

**Salida real de esta máquina:**

```
{
  "archived": true,
  "pushed_at": "2026-03-23T16:16:29Z"
}
```

El repositorio está **archivado**: solo lectura. Vas a instalar su última versión (v1.15.1)
para tener algo que migrar, que es exactamente la situación de miles de clústeres hoy.

### 7.2 El «sistema legado»: Ingress con un canary por anotaciones

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.15.1/deploy/static/provider/kind/deploy.yaml >/dev/null
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=strategic \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/os":"linux","ingress-ready":"true"}}}}}'
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=300s
curl -s -o /dev/null -w 'localhost:8080 -> HTTP %{http_code}\n' --max-time 8 http://localhost:8080
```

**Salida real de esta máquina:**

```
deployment.apps/ingress-nginx-controller patched
Waiting for deployment "ingress-nginx-controller" rollout to finish: 1 old replicas are pending termination...
Waiting for deployment "ingress-nginx-controller" rollout to finish: 0 of 1 updated replicas are available...
deployment "ingress-nginx-controller" successfully rolled out
localhost:8080 -> HTTP 404
```

El `patch` es el diagnóstico del Paso 9.2 del Laboratorio 2 del módulo 5: el controlador usa
`hostPort: 80`, y solo el control plane tiene el puerto publicado. El `404` es buena señal: el
proxy responde y aún no hay reglas.

Tres versiones de la app y dos Ingress: uno enruta por ruta, el otro manda el **20 %** a la
versión nueva con las anotaciones de canary propias de ingress-nginx. Y un detalle a
propósito: un límite de peticiones por segundo.

```bash
kubectl create namespace migra
for d in "tienda-v1 v1" "tienda-v2 v2-canary" "api api"; do
  set -- $d
  kubectl -n migra create deployment $1 --image=pulso:1.0
  kubectl -n migra set env deploy/$1 VERSION=$2
  kubectl -n migra expose deploy $1 --port=80 --target-port=8080
done >/dev/null
kubectl -n migra rollout status deploy/tienda-v1 --timeout=90s >/dev/null
kubectl -n migra rollout status deploy/tienda-v2 --timeout=90s >/dev/null
kubectl -n migra rollout status deploy/api --timeout=90s >/dev/null

cat > ingress-legado.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tienda
  namespace: migra
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "50"          # limite de peticiones por segundo
spec:
  ingressClassName: nginx
  rules:
  - host: tienda.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend: { service: { name: tienda-v1, port: { number: 80 } } }
      - path: /api
        pathType: Prefix
        backend: { service: { name: api, port: { number: 80 } } }
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tienda-canary
  namespace: migra
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "20"      # 20 % a la version nueva
spec:
  ingressClassName: nginx
  rules:
  - host: tienda.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend: { service: { name: tienda-v2, port: { number: 80 } } }
EOF

kubectl apply -f ingress-legado.yaml; sleep 5
kubectl -n migra get ingress
curl -s -H 'Host: tienda.local' http://localhost:8080/api
for i in $(seq 1 200); do curl -s -H 'Host: tienda.local' http://localhost:8080/ | cut -d' ' -f1-2; done | sort | uniq -c
```

**Salida real de esta máquina:**

```
namespace/migra created
ingress.networking.k8s.io/tienda created
ingress.networking.k8s.io/tienda-canary created
NAME            CLASS   HOSTS          ADDRESS   PORTS   AGE
tienda          nginx   tienda.local             80      5s
tienda-canary   nginx   tienda.local             80      5s
pulso api desde api-7bd44fc74f-29pzt
    167 pulso v1
     33 pulso v2-canary
```

Funciona, y el canary se acerca al 20 %. Pero fíjate **dónde vive** cada decisión: el peso,
el límite de velocidad y hasta el hecho de ser canary son **anotaciones de texto** que solo
entiende ingress-nginx. Cambiar de controlador es reescribirlas a mano.

### 7.3 Traducir con `ingress2gateway`

`ingress2gateway` es la herramienta del propio SIG Network para esta migración. Lee tus
Ingress y escribe los objetos de Gateway API equivalentes.

```bash
mkdir -p bin
curl -sL https://github.com/kubernetes-sigs/ingress2gateway/releases/download/v1.2.0/ingress2gateway_Linux_x86_64.tar.gz \
  | tar -xz -C bin ingress2gateway
./bin/ingress2gateway version | head -1
./bin/ingress2gateway print --providers=ingress-nginx -n migra --no-color > gateway-convertido.yaml
```

**Salida real de esta máquina** (las advertencias salen por la terminal; el YAML va al archivo):

```
ingress2gateway version: 1.2.0
┌─ WARN  ────────────────────────────────────────
│  Ingress NGINX serves TLS traffic for host "tienda.local" with a self-signed certificate. This behavior will not be translated and the host will not be accessible via HTTPS.
│  source: INGRESS-NGINX
└─
┌─ WARN  ────────────────────────────────────────
│  Unsupported annotation nginx.ingress.kubernetes.io/limit-rps
│  source: INGRESS-NGINX
│  object: : migra/tienda
└─
┌─ WARN  ────────────────────────────────────────
│  Gateway API does not support configuring URL normalization (RFC 3986, Section 6). Please check if this matters for your use case and consult implementation-specific details.
│  source: STANDARD_EMITTER
└─
```

🔮 **Predice, antes de abrir el archivo:** ¿cómo crees que tradujo el canary del 20 %? ¿Y el
límite de velocidad?

```bash
cat gateway-convertido.yaml
```

**Salida real de esta máquina:**

```
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  annotations:
    gateway.networking.k8s.io/generator: ingress2gateway-1.2.0
  name: nginx
  namespace: migra
spec:
  gatewayClassName: nginx
  listeners:
  - hostname: tienda.local
    name: tienda-local-http
    port: 80
    protocol: HTTP
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  annotations:
    gateway.networking.k8s.io/generator: ingress2gateway-1.2.0
  name: tienda-tienda-local
  namespace: migra
spec:
  hostnames:
  - tienda.local
  parentRefs:
  - name: nginx
  rules:
  - backendRefs:
    - name: tienda-v1
      port: 80
      weight: 80
    - name: tienda-v2
      port: 80
      weight: 20
    matches:
    - path:
        type: PathPrefix
        value: /
  - backendRefs:
    - name: api
      port: 80
    matches:
    - path:
        type: PathPrefix
        value: /api
status:
  parents: []
```

Lo que la herramienta hizo bien, y lo que **no pudo** hacer:

- **Los dos Ingress se fundieron en una sola `HTTPRoute`**, y el canary dejó de ser una
  anotación: ahora son **`weight: 80` y `weight: 20`**, campos tipados del estándar.
- Salió un `Gateway` con un listener para `tienda.local`: la parte que en Ingress no tenía
  dueño propio.
- **`limit-rps` se perdió.** Te lo advirtió (`Unsupported annotation`) y lo omitió del YAML.
  Si no lees las advertencias, tu tienda queda **sin límite de velocidad** después de la
  migración y nadie se entera hasta el primer pico de tráfico.

### 7.4 Un controlador para Gateway API

Gateway API no viene en Kubernetes: primero sus CRDs, después una implementación. Aquí,
NGINX Gateway Fabric, con su Service en el `NodePort` 30080 (que `kind` publica en el 8081):

```bash
kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.2/standard-install.yaml >/dev/null
helm install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric --version 2.7.2 \
  --create-namespace -n nginx-gateway \
  --set nginx.service.type=NodePort \
  --set nginx.service.externalTrafficPolicy=Cluster \
  --set 'nginx.service.nodePorts[0].port=30080' \
  --set 'nginx.service.nodePorts[0].listenerPort=80' \
  --wait --timeout 5m | grep -E 'STATUS'
kubectl get gatewayclass
```

**Salida real de esta máquina:**

```
STATUS: deployed
NAME    CONTROLLER                                   ACCEPTED   AGE
nginx   gateway.nginx.org/nginx-gateway-controller   True       12s
```

`externalTrafficPolicy=Cluster` evita la trampa del Paso 9.5 del Laboratorio 2 del módulo 5
(con `Local`, solo respondería el nodo donde cayera el Pod del gateway).

### 7.5 Los dos a la vez: la paridad

El camino de migración real no tiene «apagón»: el sistema nuevo se enciende **al lado** del
viejo, se compara, y solo entonces se apaga el viejo.

```bash
kubectl apply -f gateway-convertido.yaml
kubectl -n migra wait --for=condition=Programmed gateway/nginx --timeout=120s
kubectl -n migra wait --for=condition=Ready pod -l gateway.networking.k8s.io/gateway-name=nginx --timeout=120s
kubectl -n migra get gateway,httproute
kubectl -n migra get httproute tienda-tienda-local -o jsonpath='{range .status.parents[0].conditions[*]}{.type}={.status} {end}{"\n"}'
echo "== viejo (Ingress, :8080)"; curl -s -H 'Host: tienda.local' http://localhost:8080/api
echo "== nuevo (Gateway, :8081)"; curl -s -H 'Host: tienda.local' http://localhost:8081/api
for i in $(seq 1 200); do r=$(curl -s --max-time 2 -H 'Host: tienda.local' http://localhost:8081/ | cut -d' ' -f1-2); echo "${r:-FALLO}"; done | sort | uniq -c
```

**Salida real de esta máquina:**

```
gateway.gateway.networking.k8s.io/nginx created
httproute.gateway.networking.k8s.io/tienda-tienda-local created
gateway.gateway.networking.k8s.io/nginx condition met
pod/nginx-nginx-6c88bb5958-qkmsm condition met
NAME                                      CLASS   ADDRESS        PROGRAMMED   AGE
gateway.gateway.networking.k8s.io/nginx   nginx   10.96.72.101   True         23s

NAME                                                      HOSTNAMES          AGE
httproute.gateway.networking.k8s.io/tienda-tienda-local   ["tienda.local"]   23s
Accepted=True ResolvedRefs=True
== viejo (Ingress, :8080)
pulso api desde api-7bd44fc74f-29pzt
== nuevo (Gateway, :8081)
pulso api desde api-7bd44fc74f-29pzt
    152 pulso v1
     48 pulso v2-canary
```

Mismas rutas, mismo reparto aproximado, los dos vivos. Y si algo falla, la `HTTPRoute` te lo
dice en su `status`: `Accepted` (el Gateway la aceptó) y `ResolvedRefs` (los Services
existen). Un Ingress no tenía nada parecido.

> **Si ves `FALLO` o respuestas vacías justo después del `apply`**: el Gateway puede estar
> `Programmed` antes de que su Pod de NGINX esté listo. Por eso está el segundo `wait`. Al
> preparar este laboratorio, sin él, 24 de 200 peticiones se perdieron.

### 7.6 Un canary con pesos de verdad, y el corte

🔮 **Predice:** para promover el canary ya no escalas réplicas. ¿Qué cambias?

```bash
for w in "50 50" "0 100"; do
  set -- $w
  kubectl -n migra patch httproute tienda-tienda-local --type=json -p "[
    {\"op\":\"replace\",\"path\":\"/spec/rules/0/backendRefs/0/weight\",\"value\":$1},
    {\"op\":\"replace\",\"path\":\"/spec/rules/0/backendRefs/1/weight\",\"value\":$2}]" >/dev/null
  sleep 3; echo "== pesos v1=$1 v2=$2"
  for i in $(seq 1 100); do curl -s --max-time 2 -H 'Host: tienda.local' http://localhost:8081/ | cut -d' ' -f1-2; done | sort | uniq -c
done
kubectl -n migra delete ingress tienda tienda-canary
sleep 3
curl -s -o /dev/null -w 'Ingress :8080 -> HTTP %{http_code}\n' -H 'Host: tienda.local' http://localhost:8080/
curl -s -H 'Host: tienda.local' http://localhost:8081/api
```

**Salida real de esta máquina:**

```
== pesos v1=50 v2=50
     46 pulso v1
     54 pulso v2-canary
== pesos v1=0 v2=100
    100 pulso v2-canary
ingress.networking.k8s.io "tienda" deleted from migra namespace
ingress.networking.k8s.io "tienda-canary" deleted from migra namespace
Ingress :8080 -> HTTP 404
pulso api desde api-7bd44fc74f-29pzt
```

Compara con el Paso 5.4: allí el porcentaje dependía de **cuántas réplicas** corrían; aquí
depende de **un número en la ruta**, sin tocar un solo Pod. El corte final fue borrar los
Ingress: el `404` del 8080 es el viejo sin reglas, y el 8081 sigue sirviendo.

### 7.7 Recuperar lo que la migración perdió

`limit-rps` no tiene equivalente en el estándar de Gateway API. Pero las implementaciones
extienden el estándar con **políticas** que se adjuntan a una ruta. NGINX Gateway Fabric trae
`RateLimitPolicy`:

```bash
kubectl explain ratelimitpolicies.spec.rateLimit.local.rules.rate | sed -n '/DESCRIPTION/,+3p'
cat > limite-velocidad.yaml <<'EOF'
apiVersion: gateway.nginx.org/v1alpha1
kind: RateLimitPolicy
metadata:
  name: tienda-limite
  namespace: migra
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: tienda-tienda-local
  rateLimit:
    rejectCode: 429
    local:
      rules:
      - key: $binary_remote_addr
        rate: 5r/s
        burst: 5
        noDelay: true
EOF

kubectl apply -f limite-velocidad.yaml; sleep 5
kubectl -n migra get ratelimitpolicy tienda-limite \
  -o jsonpath='{range .status.ancestors[0].conditions[*]}{.type}={.status} {.message}{"\n"}{end}'
for i in $(seq 1 40); do curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: tienda.local' http://localhost:8081/; done | sort | uniq -c
```

**Salida real de esta máquina:**

```
DESCRIPTION:
    Rate represents the rate of requests permitted. The rate is specified in
    requests per second (r/s)
    or requests per minute (r/m).
ratelimitpolicy.gateway.nginx.org/tienda-limite created
Accepted=True The Policy is accepted
Programmed=True Policy is programmed in the data plane
      6 200
     34 429
```

Cuarenta peticiones seguidas: pasan 6 (la ráfaga de 5 más la primera) y el resto recibe
`429 Too Many Requests`. **Esa es la lista de verificación de toda migración:** traducir lo
estándar, leer cada advertencia, y reconstruir lo perdido con la herramienta de la
implementación nueva. La diferencia con las anotaciones: `RateLimitPolicy` es un objeto
tipado, validado por el apiserver, con `status` que dice si se aplicó.

---

## Paso 8: Reto estilo examen (20 min)

**Este paso es un laboratorio estilo examen.** Hay un objetivo, un sistema roto y un script
que califica **el estado final**. La solución está al final del documento.

```bash
cd ~/lab-ckad-2
echo 'YXBpVmVyc2lvbjogdjEKa2luZDogTmFtZXNwYWNlCm1ldGFkYXRhOgogIG5hbWU6IHJldG8yCiAgbGFiZWxzOgogICAgcG9kLXNlY3VyaXR5Lmt1YmVybmV0ZXMuaW8vZW5mb3JjZTogcmVzdHJpY3RlZAogICAgcG9kLXNlY3VyaXR5Lmt1YmVybmV0ZXMuaW8vZW5mb3JjZS12ZXJzaW9uOiBsYXRlc3QKLS0tCmFwaVZlcnNpb246IHYxCmtpbmQ6IENvbmZpZ01hcAptZXRhZGF0YToKICBuYW1lOiBwYWdvcy1jb25maWcKICBuYW1lc3BhY2U6IHJldG8yCmRhdGE6CiAgVkVSU0lPTl9QQUdPUzogInBhZ29zLUNPUCIKLS0tCmFwaVZlcnNpb246IGFwcHMvdjEKa2luZDogRGVwbG95bWVudAptZXRhZGF0YToKICBuYW1lOiBwYWdvcwogIG5hbWVzcGFjZTogcmV0bzIKc3BlYzoKICByZXBsaWNhczogMgogIHNlbGVjdG9yOiB7IG1hdGNoTGFiZWxzOiB7IGFwcDogcGFnb3MgfSB9CiAgdGVtcGxhdGU6CiAgICBtZXRhZGF0YTogeyBsYWJlbHM6IHsgYXBwOiBwYWdvcyB9IH0KICAgIHNwZWM6CiAgICAgIGNvbnRhaW5lcnM6CiAgICAgIC0gbmFtZTogYXBwCiAgICAgICAgaW1hZ2U6IHB1bHNvOjEuMAogICAgICAgIHBvcnRzOiBbeyBjb250YWluZXJQb3J0OiA4MDgwIH1dCiAgICAgICAgZW52OgogICAgICAgIC0gbmFtZTogVkVSU0lPTgogICAgICAgICAgdmFsdWVGcm9tOiB7IGNvbmZpZ01hcEtleVJlZjogeyBuYW1lOiBwYWdvcy1jb25maWcsIGtleTogdmVyc2lvbiB9IH0KLS0tCmFwaVZlcnNpb246IHYxCmtpbmQ6IFNlcnZpY2UKbWV0YWRhdGE6CiAgbmFtZTogcGFnb3MKICBuYW1lc3BhY2U6IHJldG8yCnNwZWM6CiAgc2VsZWN0b3I6IHsgYXBwOiBwYWdvcyB9CiAgcG9ydHM6IFt7IHBvcnQ6IDgwLCB0YXJnZXRQb3J0OiA4MDgwIH1dCi0tLQphcGlWZXJzaW9uOiBuZXR3b3JraW5nLms4cy5pby92MQpraW5kOiBOZXR3b3JrUG9saWN5Cm1ldGFkYXRhOgogIG5hbWU6IGRlbmVnYXItdG9kbwogIG5hbWVzcGFjZTogcmV0bzIKc3BlYzoKICBwb2RTZWxlY3Rvcjoge30KICBwb2xpY3lUeXBlczogW0luZ3Jlc3NdCi0tLQphcGlWZXJzaW9uOiBuZXR3b3JraW5nLms4cy5pby92MQpraW5kOiBOZXR3b3JrUG9saWN5Cm1ldGFkYXRhOgogIG5hbWU6IHBlcm1pdGlyLWNoZWNrb3V0CiAgbmFtZXNwYWNlOiByZXRvMgpzcGVjOgogIHBvZFNlbGVjdG9yOiB7IG1hdGNoTGFiZWxzOiB7IGFwcDogcGFnb3MgfSB9CiAgcG9saWN5VHlwZXM6IFtJbmdyZXNzXQogIGluZ3Jlc3M6CiAgLSBmcm9tOgogICAgLSBwb2RTZWxlY3RvcjogeyBtYXRjaExhYmVsczogeyByb2w6IGNoZWNrb3V0IH0gfQogICAgcG9ydHM6IFt7IHByb3RvY29sOiBUQ1AsIHBvcnQ6IDgwIH1dCi0tLQphcGlWZXJzaW9uOiB2MQpraW5kOiBQb2QKbWV0YWRhdGE6CiAgbmFtZTogY2hlY2tvdXQKICBuYW1lc3BhY2U6IHJldG8yCiAgbGFiZWxzOiB7IHJvbDogY2hlY2tvdXQgfQpzcGVjOgogIHNlY3VyaXR5Q29udGV4dDogeyBydW5Bc05vblJvb3Q6IHRydWUsIHJ1bkFzVXNlcjogNjU1MzQsIHNlY2NvbXBQcm9maWxlOiB7IHR5cGU6IFJ1bnRpbWVEZWZhdWx0IH0gfQogIGNvbnRhaW5lcnM6CiAgLSBuYW1lOiBjbGllbnRlCiAgICBpbWFnZTogYnVzeWJveDoxLjM3CiAgICBjb21tYW5kOiBbInNsZWVwIiwgImluZmluaXR5Il0KICAgIHNlY3VyaXR5Q29udGV4dDogeyBhbGxvd1ByaXZpbGVnZUVzY2FsYXRpb246IGZhbHNlLCBjYXBhYmlsaXRpZXM6IHsgZHJvcDogWyJBTEwiXSB9IH0KLS0tCmFwaVZlcnNpb246IHYxCmtpbmQ6IFBvZAptZXRhZGF0YToKICBuYW1lOiBpbnRydXNvCiAgbmFtZXNwYWNlOiByZXRvMgogIGxhYmVsczogeyByb2w6IGludHJ1c28gfQpzcGVjOgogIHNlY3VyaXR5Q29udGV4dDogeyBydW5Bc05vblJvb3Q6IHRydWUsIHJ1bkFzVXNlcjogNjU1MzQsIHNlY2NvbXBQcm9maWxlOiB7IHR5cGU6IFJ1bnRpbWVEZWZhdWx0IH0gfQogIGNvbnRhaW5lcnM6CiAgLSBuYW1lOiBjbGllbnRlCiAgICBpbWFnZTogYnVzeWJveDoxLjM3CiAgICBjb21tYW5kOiBbInNsZWVwIiwgImluZmluaXR5Il0KICAgIHNlY3VyaXR5Q29udGV4dDogeyBhbGxvd1ByaXZpbGVnZUVzY2FsYXRpb246IGZhbHNlLCBjYXBhYmlsaXRpZXM6IHsgZHJvcDogWyJBTEwiXSB9IH0K' | base64 -d | kubectl apply -f - 2>/dev/null

cat > verificar-reto2.sh <<'EOF'
#!/usr/bin/env bash
# Verificador del Reto 2: califica el ESTADO FINAL, no los comandos que usaste.
NS=reto2; OK=0; TOTAL=0
chequeo() {  # $1 = descripcion, $2 = comando que sale con 0 si el mundo esta bien
  TOTAL=$((TOTAL+1))
  if bash -c "$2" >/dev/null 2>&1; then echo "  [OK]    $1"; OK=$((OK+1)); else echo "  [FALLA] $1"; fi
}
D='kubectl -n reto2 get deploy pagos -o jsonpath'
chequeo "El Deployment pagos tiene 2 replicas listas" \
  "[ \"\$($D='{.status.readyReplicas}')\" = 2 ]"
chequeo "El namespace sigue exigiendo Pod Security 'restricted' (no vale bajarlo)" \
  "[ \"\$(kubectl get ns $NS -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}')\" = restricted ]"
chequeo "VERSION sigue saliendo del ConfigMap pagos-config (no vale escribirla a mano)" \
  "[ \"\$($D='{.spec.template.spec.containers[0].env[?(@.name==\"VERSION\")].valueFrom.configMapKeyRef.name}')\" = pagos-config ]"
chequeo "La politica denegar-todo sigue en pie y cubre todo el namespace" \
  "[ \"\$(kubectl -n $NS get netpol denegar-todo -o jsonpath='{.spec.podSelector}')\" = '{}' ]"
chequeo "checkout llega a pagos y recibe la version del ConfigMap" \
  "kubectl -n $NS exec checkout -- wget -qO- -T 3 http://pagos | grep -q 'pulso pagos-COP'"
chequeo "intruso sigue SIN poder llegar a pagos (con pagos arriba)" \
  "[ \"\$($D='{.status.readyReplicas}')\" = 2 ] && ! kubectl -n $NS exec intruso -- wget -qO- -T 3 http://pagos"
echo "Resultado: $OK/$TOTAL"
[ "$OK" = "$TOTAL" ]
EOF
chmod +x verificar-reto2.sh
```

El `2>/dev/null` esconde las advertencias del `apply`: te darían pistas. El base64 es una venda
de cortesía, no un secreto; no lo decodifiques.

### El objetivo

En el namespace `reto2` vive `pagos`, un Deployment de 2 réplicas con su Service. Solo el
Pod `checkout` debe poder hablarle; `intruso` no. La versión que `pagos` anuncia debe salir
del ConfigMap `pagos-config`. Tu misión: que `checkout` reciba `pulso pagos-COP` desde
`http://pagos`.

**Trampas que el verificador castiga:** bajar el nivel de Pod Security del namespace, borrar
o debilitar la política `denegar-todo`, escribir la versión a mano en vez de leerla del
ConfigMap, o abrirle la puerta a `intruso`.

```bash
./verificar-reto2.sh
```

**Salida real de esta máquina**, justo después de instalar el reto:

```
  [FALLA] El Deployment pagos tiene 2 replicas listas
  [OK]    El namespace sigue exigiendo Pod Security 'restricted' (no vale bajarlo)
  [OK]    VERSION sigue saliendo del ConfigMap pagos-config (no vale escribirla a mano)
  [OK]    La politica denegar-todo sigue en pie y cubre todo el namespace
  [FALLA] checkout llega a pagos y recibe la version del ConfigMap
  [FALLA] intruso sigue SIN poder llegar a pagos (con pagos arriba)
Resultado: 3/6
```

El objetivo es `Resultado: 6/6`.

---

## Limpieza (3 min)

```bash
kind delete cluster --name ckad-red
docker ps -a --filter "label=io.x-k8s.kind.cluster=ckad-red" --format '{{.Names}}'
docker rmi controlador:1.0
```

`docker ps -a` no debe listar nada.

---

## Síntesis: qué hiciste y qué demostraste

| Lo que hiciste | Lo que demuestra |
|---|---|
| `anuncio` creado y ningún Pod | Un CRD define un tipo; sin controlador no pasa nada |
| Tres rechazos (`required`, `maximum`, CEL) | La validación vive en el esquema, sin código |
| `status` ignorado con `(no change)` | `spec` es del usuario, `status` es del controlador |
| `Forbidden` y `can-i` con `--subresource` | RBAC se construye leyendo los `Forbidden` |
| Deployment borrado al borrar el anuncio | `ownerReferences` + recolector de basura |
| `env` y `subPath` congelados, volumen actualizado | La forma de consumir decide si te enteras del cambio |
| `base64 -d` de un Secret | Codificación no es cifrado |
| `raiz` rechazado, `pulso-seguro` admitido | Pod Security por namespace; el mensaje es la receta |
| Debug `general` rechazado, `--custom` aceptado | Los perfiles negocian seguridad y depurabilidad |
| Deployment en `0/2` con el 403 en el ReplicaSet | Un nivel más abajo está la causa |
| 5 `FALLO` en `Recreate`, 2 en rolling, 1 con `preStop` | La disponibilidad se mide, no se supone |
| Cinco revisiones con `v1 inicial` | `change-cause` se copia; anótalo después de cada cambio |
| Cero respuestas perdidas en el corte azul/verde | Blue/green es un `patch` y un doble costo |
| Canary por réplicas, aproximado | Sin campo de peso, el reparto es aleatorio |
| Puerto 80 en la política: bloqueado | Las políticas ven el puerto del contenedor |
| Un `-` de más abre `monitoreo` | Y frente a O en `from` |
| `bad address` por nombre, respuesta por IP | Egress sin DNS rompe los nombres |
| Whisker con `EndOfTier` y `cuarentena` | Una política se prueba viendo sus veredictos |
| `limit-rps` perdido y `RateLimitPolicy` | Migrar es traducir, leer advertencias y reconstruir |
| Pesos 80/20, 50/50, 0/100 | Gateway API trae pesos de verdad |

---

## Recupera sin mirar (5 min)

Responde en `predicciones.md`, **sin volver a leer el laboratorio**:

1. ¿Qué tres piezas forman el patrón operador, y cuál de ellas limpia al borrar?
2. Escribe el `can-i` correcto para saber si una ServiceAccount puede parchear el `status`
   de un recurso.
3. ¿Qué puerto va en una NetworkPolicy: el del Service o el del contenedor?
4. Dibuja (en texto) la diferencia entre un `from` con un elemento de dos selectores y uno
   con dos elementos.
5. Nombra dos cosas que `ingress2gateway` tradujo sola y una que perdió.

---

## Cómo conecta con el resto del curso

- **Laboratorio 1 de este módulo:** `pulso`, distroless y `kubectl debug` vuelven aquí, ahora
  dentro de un namespace `restricted`.
- **Módulo 5 (CKA):** allí instalaste el controlador de Ingress y comparaste CNIs; aquí los
  usas como desarrollador y migras.
- **Módulo 7 (CKS):** Pod Security, RBAC mínimo, NetworkPolicies y la cuarentena de Calico
  son la base de la seguridad del clúster.
- **Módulo 8 (producción):** el controlador de juguete del Paso 1 es la versión artesanal de
  los operadores reales (Argo CD, Flux, cert-manager) que verás allí.

---

## Para profundizar

- Custom Resources y CRDs: <https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/>
- Validación con CEL en CRDs: <https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/#validation-rules>
- RBAC: <https://kubernetes.io/docs/reference/access-authn-authz/rbac/>
- Recolección de basura y `ownerReferences`: <https://kubernetes.io/docs/concepts/architecture/garbage-collection/>
- ConfigMaps: <https://kubernetes.io/docs/concepts/configuration/configmap/>
- Secrets: <https://kubernetes.io/docs/concepts/configuration/secret/>
- Pod Security Standards: <https://kubernetes.io/docs/concepts/security/pod-security-standards/>
- LimitRange: <https://kubernetes.io/docs/concepts/policy/limit-range/>
- ResourceQuota: <https://kubernetes.io/docs/concepts/policy/resource-quotas/>
- Deployments: <https://kubernetes.io/docs/concepts/workloads/controllers/deployment/>
- NetworkPolicies: <https://kubernetes.io/docs/concepts/services-networking/network-policies/>
- Calico en kind: <https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind>
- Retiro de ingress-nginx: <https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/>
- Gateway API: <https://gateway-api.sigs.k8s.io/>
- `ingress2gateway`: <https://github.com/kubernetes-sigs/ingress2gateway>
- NGINX Gateway Fabric: <https://docs.nginx.com/nginx-gateway-fabric/>
- Currículo CKAD v1.35: <https://github.com/cncf/curriculum>

**Pedagogía:** las mismas referencias del Laboratorio 1 (Sentance, Waite y Kallia, 2019;
White y Gunstone, 1992; Kapur, 2008; Kalyuga et al., 2003; Jonassen y Hung, 2006; Roediger y
Karpicke, 2006).

---

## Solución del reto (no la leas antes de intentarlo)

<details>
<summary>Mostrar la solución</summary>

Tres fallas, en capas: cada una esconde a la siguiente.

**1. `pagos` en `0/2` sin Pods.** Un nivel abajo: `kubectl -n reto2 describe rs -l app=pagos`
muestra `violates PodSecurity "restricted:latest"` con la lista de campos que faltan. El
namespace exige `restricted` y el Deployment no declara `securityContext`. **No** se arregla
bajando la etiqueta del namespace.

**2. Con los Pods creados, `CreateContainerConfigError`.** `describe pod` dice que la clave
`version` no existe en `pagos-config`. La clave real es `VERSION_PAGOS`.

**3. Con `pagos` arriba, `checkout` recibe un timeout.** La política `permitir-checkout`
abre el puerto **80**, el del Service; el contenedor escucha en el **8080** (Paso 6.3).

```bash
kubectl -n reto2 patch networkpolicy permitir-checkout --type=json \
  -p '[{"op":"replace","path":"/spec/ingress/0/ports/0/port","value":8080}]'
kubectl -n reto2 patch deployment pagos --type=strategic -p '{"spec":{"template":{"spec":{
  "securityContext":{"runAsNonRoot":true,"seccompProfile":{"type":"RuntimeDefault"}},
  "containers":[{"name":"app",
    "env":[{"name":"VERSION","valueFrom":{"configMapKeyRef":{"name":"pagos-config","key":"VERSION_PAGOS"}}}],
    "securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}}}]}}}}'
kubectl -n reto2 rollout status deployment/pagos --timeout=120s
./verificar-reto2.sh
```

**Salida real de esta máquina:**

```
  [OK]    El Deployment pagos tiene 2 replicas listas
  [OK]    El namespace sigue exigiendo Pod Security 'restricted' (no vale bajarlo)
  [OK]    VERSION sigue saliendo del ConfigMap pagos-config (no vale escribirla a mano)
  [OK]    La politica denegar-todo sigue en pie y cubre todo el namespace
  [OK]    checkout llega a pagos y recibe la version del ConfigMap
  [OK]    intruso sigue SIN poder llegar a pagos (con pagos arriba)
Resultado: 6/6
```

Y el atajo, castigado: bajar el namespace a `privileged`, borrar las dos políticas y escribir
`VERSION=pagos-COP` a mano hace que `checkout` reciba la respuesta correcta. Aun así:

```
  [OK]    El Deployment pagos tiene 2 replicas listas
  [FALLA] El namespace sigue exigiendo Pod Security 'restricted' (no vale bajarlo)
  [FALLA] VERSION sigue saliendo del ConfigMap pagos-config (no vale escribirla a mano)
  [FALLA] La politica denegar-todo sigue en pie y cubre todo el namespace
  [OK]    checkout llega a pagos y recibe la version del ConfigMap
  [FALLA] intruso sigue SIN poder llegar a pagos (con pagos arriba)
Resultado: 2/6
```

</details>

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
