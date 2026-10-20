# Laboratorio 1 (Módulo 6) – Construir, arrancar, observar y depurar una aplicación

**Módulo 6 · sesión 8 · en clase · 130–150 minutos.** En el módulo 5 el clúster era tuyo.
Hoy no: eres quien escribe la aplicación que va a vivir dentro de él. Vas a construir una
imagen **distroless** (sin shell), llevarla a un clúster `kind`, depurarla aunque no tenga
shell, enseñarle al kubelet cuándo está arrancando, cuándo está viva y cuándo puede recibir
tráfico, y ordenar su arranque con **init containers** y **sidecars nativos**.

| Bloque | Paso | Tiempo | ¿Se puede dejar para casa? |
|---|---|---|---|
| Clúster `kind` y hábitos de examen | 0 | ~8 min | No |
| Construir una imagen distroless | 1 | ~15 min | No |
| Llevar la imagen al clúster: tag, digest y `imagePullPolicy` | 2 | ~10 min | No |
| `kubectl debug`: contenedores efímeros, copias y nodos | 3 | ~25 min | No |
| Las tres probes, con una app que se deja romper | 4 | ~30 min | No |
| Init containers | 5 | ~10 min | No |
| Sidecars nativos: el Job que nunca termina | 6 | ~15 min | No |
| Recursos, QoS y `OOMKilled` | 7 | ~7 min | Sí |
| **Reto** estilo examen, calificado por script | 8 | ~20 min | No |

> La idea central de esta sesión cabe en una frase: **Kubernetes no sabe nada de tu
> aplicación salvo lo que tú le declaras.** Si no le dices cuándo arrancó, cuándo está viva
> y cuándo puede atender, adivina, y adivina mal. Cada paso de hoy es una declaración que
> cambia una decisión del kubelet, y cada decisión deja evidencia en la terminal.

---

## Cómo trabajar este laboratorio

Este laboratorio está construido con tres técnicas de enseñanza que tienen respaldo en la
investigación sobre cómo se aprende a programar y a diagnosticar. No son adorno: cambian
lo que haces en cada paso.

| Técnica | Lo que te pide | De dónde sale |
|---|---|---|
| **Predice, ejecuta, explica** | Antes de cada bloque marcado **🔮 Predice**, escribe en `predicciones.md` qué crees que va a pasar. Después compara. | PRIMM (Sentance y Waite, 2019) y Predict-Observe-Explain (White y Gunstone, 1992) |
| **Fallo productivo** | Varios pasos te hacen romper algo **a propósito** antes de ver la forma correcta. El error es el material. | Productive Failure (Kapur, 2008) |
| **Diagnóstico con fallas ocultas** | El reto final instala un sistema roto sin decirte qué tiene. Formulas hipótesis y las pruebas con `describe`, eventos y endpoints. | Jonassen y Hung (2006), aprender a diagnosticar |
| **Andamiaje que se retira** | Los pasos 0 a 7 te dan el comando. El Paso 8 solo te da el objetivo y un script que califica el resultado, igual que el examen. | Efecto del ejemplo resuelto y reversión por experticia (Sweller; Kalyuga et al., 2003) |

```bash
mkdir -p ~/lab-ckad-1 && cd ~/lab-ckad-1
echo "# Predicciones del laboratorio 1" > predicciones.md
```

Una predicción equivocada que escribiste vale más que una correcta que solo pensaste: es la
que te obliga a revisar tu modelo mental. Nadie la califica.

---

## Objetivo

Al terminar vas a poder responder, señalando evidencia en tu terminal:

1. ¿Por qué `kubectl exec -- sh` falla en una imagen bien construida, y cómo entras de todas
   formas a mirar sus procesos y su sistema de archivos?
2. ¿Por qué una imagen que **ya está en el nodo** puede terminar en `ImagePullBackOff`?
3. ¿Qué probe reinicia el contenedor, cuál solo lo saca del tráfico y cuál protege el
   arranque? ¿Qué columna de `kubectl get pods` cambia en cada caso?
4. ¿Por qué un Job con un sidecar «a la antigua» no termina nunca, y qué campo lo arregla?
5. ¿Por qué un sidecar nativo puede retrasar 30 segundos el final de un Job, y qué línea de
   shell lo evita?
6. ¿Qué te dice `Exit Code: 137` y qué te dice `Exit Code: 2`?

**Requisito:** módulo 5 completo (sabes crear un clúster `kind` y leer `kubectl describe`).

**Entorno verificado** (el 25 y 26 de septiembre de 2026, en la máquina donde se capturaron
todas las salidas): Linux con Docker Engine 29.8.1, `kind` v0.33.0, `kubectl` v1.37.0 y
nodos `kindest/node:v1.37.0`. `trivy` es opcional (Paso 1.4). Cuenta con **4 GiB de RAM
libres** y unos **600 MB de descargas** (imágenes base de Go, distroless y busybox).

Comprueba tus versiones antes de empezar; si difieren, las salidas pueden variar en detalle:

```bash
kind version
kubectl version --client | head -1
docker version --format '{{.Server.Version}}'
```

> Todas las salidas marcadas **«Salida real de esta máquina»** se capturaron ejecutando los
> comandos. Los nombres de Pods, IPs, hashes y tiempos serán **distintos en tu máquina**; la
> forma de la salida no.

---

## Paso 0: Un clúster y los hábitos del examen (8 min)

```bash
cd ~/lab-ckad-1
cat > kind-ckad.yaml <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ckad
nodes:
- role: control-plane
  image: kindest/node:v1.37.0
- role: worker
  image: kindest/node:v1.37.0
EOF

kind create cluster --config kind-ckad.yaml
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl get nodes
```

**Salida real de esta máquina:**

```
NAME                 STATUS   ROLES           AGE   VERSION
ckad-control-plane   Ready    control-plane   26s   v1.37.0
ckad-worker          Ready    <none>          12s   v1.37.0
```

Trabaja en tu propio namespace y déjalo fijo en el contexto, como harías en un clúster
compartido donde **no eres administrador**:

```bash
kubectl create namespace lab1
kubectl config set-context --current --namespace=lab1
```

Dos hábitos que ahorran minutos en el examen (el alias `k` ya viene configurado allí; aquí
lo creas tú):

```bash
alias k=kubectl
export do="--dry-run=client -o yaml"      # consejo de la comunidad, no de la LF
k run prueba --image=busybox:1.37 $do | head -12
```

**Salida real de esta máquina:**

```
apiVersion: v1
kind: Pod
metadata:
  labels:
    run: prueba
  name: prueba
spec:
  containers:
  - image: busybox:1.37
    name: prueba
    resources: {}
  dnsPolicy: ClusterFirst
```

`--dry-run=client` **no toca el API server**: genera el esqueleto y tú lo editas. Y cuando
no recuerdes un campo, `kubectl explain` lee el esquema del **propio clúster**, sin
navegador:

```bash
kubectl explain pod.spec.initContainers.restartPolicy | head -20
```

**Salida real de esta máquina:**

```
KIND:       Pod
VERSION:    v1

FIELD: restartPolicy <string>


DESCRIPTION:
    RestartPolicy defines the restart behavior of individual containers in a
    pod. This overrides the pod-level restart policy. When this field is not
    specified, the restart behavior is defined by the Pod's restart policy and
    the container type. Additionally, setting the RestartPolicy as "Always" for
    the init container will have the following effect: this init container will
    be continually restarted on exit until all regular containers have
    terminated. Once all regular containers have completed, all init containers
    with restartPolicy "Always" will be shut down. This lifecycle differs from
    normal init containers and is often referred to as a "sidecar" container.
    Although this init container still starts in the init container sequence, it
    does not wait for the container to complete before proceeding to the next
    init container. Instead, the next init container starts immediately after
    this init container is started, or after any startupProbe has successfully
```

Ya ves el Paso 6 escrito en el esquema: un `restartPolicy` dentro de un **init container**
es la marca de un sidecar.

---

## Paso 1: Construir una imagen distroless (15 min)

### 1.1 La aplicación: `pulso`

Durante todo el laboratorio vas a usar una sola aplicación, escrita para dejarse romper.
Es un servidor HTTP en Go, sin dependencias externas, cuyo comportamiento controlas **desde
fuera**, con peticiones HTTP:

| Ruta | Para qué |
|---|---|
| `/` | Responde `pulso <VERSION> desde <hostname>` |
| `/startupz` | `503` durante los primeros `STARTUP_SECONDS` segundos, después `200` |
| `/healthz` | `200`, salvo que la hayas «colgado»: entonces **no responde nunca** (un deadlock) |
| `/readyz` | `200`, o `503` si le dijiste que no está lista |
| `/admin/colgar` | Simula un deadlock |
| `/admin/no-listo` y `/admin/listo` | Simulan una dependencia que se cae y vuelve |
| `/admin/comer?mb=N` | Reserva N MiB de memoria, para provocar un `OOMKilled` |

¿Por qué controlarla por HTTP y no con un `kubectl exec`? Porque en el Paso 1.3 vas a
descubrir que **no tiene shell**, y esa es precisamente la idea.

```bash
mkdir -p ~/lab-ckad-1/pulso && cd ~/lab-ckad-1/pulso

cat > main.go <<'EOF'
// pulso: una app HTTP minima para practicar probes, depuracion y despliegues.
// Todo su estado se controla desde fuera con peticiones HTTP, sin shell.
package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync/atomic"
	"time"
)

var (
	inicio   = time.Now()
	arranque = segundosEnv("STARTUP_SECONDS", 0) // cuanto tarda en "arrancar"
	version  = envOr("VERSION", "v1")
	colgado  atomic.Bool // simula un deadlock: /healthz deja de responder
	noListo  atomic.Bool // simula una dependencia caida: /readyz responde 503
	memoria  [][]byte    // lo que se "come" /admin/comer
	host, _  = os.Hostname()
)

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func segundosEnv(k string, def int) time.Duration {
	n, err := strconv.Atoi(os.Getenv(k))
	if err != nil {
		n = def
	}
	return time.Duration(n) * time.Second
}

func arrancado() bool { return time.Since(inicio) >= arranque }

func main() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "pulso %s desde %s\n", version, host)
	})
	// startupProbe: 503 hasta que pasen STARTUP_SECONDS
	http.HandleFunc("/startupz", func(w http.ResponseWriter, r *http.Request) {
		if !arrancado() {
			http.Error(w, "todavia arrancando", http.StatusServiceUnavailable)
			return
		}
		fmt.Fprintln(w, "arrancado")
	})
	// livenessProbe: si esta "colgado", no responde nunca (como un deadlock real)
	http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		if !arrancado() {
			http.Error(w, "todavia arrancando", http.StatusServiceUnavailable)
			return
		}
		for colgado.Load() {
			time.Sleep(time.Second)
		}
		fmt.Fprintln(w, "vivo")
	})
	// readinessProbe: 503 mientras "no listo"
	http.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		if !arrancado() || noListo.Load() {
			http.Error(w, "no listo", http.StatusServiceUnavailable)
			return
		}
		fmt.Fprintln(w, "listo")
	})
	http.HandleFunc("/admin/colgar", func(w http.ResponseWriter, r *http.Request) {
		colgado.Store(true)
		log.Println("ADMIN: me cuelgo, /healthz ya no respondera")
		fmt.Fprintln(w, "colgado")
	})
	http.HandleFunc("/admin/no-listo", func(w http.ResponseWriter, r *http.Request) {
		noListo.Store(true)
		log.Println("ADMIN: dejo de estar listo")
		fmt.Fprintln(w, "no listo")
	})
	http.HandleFunc("/admin/listo", func(w http.ResponseWriter, r *http.Request) {
		noListo.Store(false)
		log.Println("ADMIN: vuelvo a estar listo")
		fmt.Fprintln(w, "listo")
	})
	// /admin/comer?mb=N reserva N MiB y las toca, para provocar un OOMKilled
	http.HandleFunc("/admin/comer", func(w http.ResponseWriter, r *http.Request) {
		mb, _ := strconv.Atoi(r.URL.Query().Get("mb"))
		b := make([]byte, mb<<20)
		for i := range b {
			b[i] = 1
		}
		memoria = append(memoria, b)
		log.Printf("ADMIN: reservadas %d MiB mas (%d bloques)\n", mb, len(memoria))
		fmt.Fprintf(w, "reservadas %d MiB\n", mb)
	})

	log.Printf("pulso %s escuchando en :8080 (arranque simulado: %s)\n", version, arranque)
	log.Fatal(http.ListenAndServe(":8080", nil))
}
EOF

cat > go.mod <<'EOF'
module pulso

go 1.25
EOF
```

### 1.2 Dos Dockerfiles, la misma aplicación

El primero es **multi-stage**: compila con la imagen completa de Go y copia **solo el
binario** a una base distroless.

```bash
cat > Dockerfile <<'EOF'
# Etapa 1: compilar con el toolchain completo de Go
FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /pulso .

# Etapa 2: solo el binario, sobre una base distroless sin shell ni gestor de paquetes
FROM gcr.io/distroless/static-debian13:nonroot
COPY --from=build /pulso /pulso
EXPOSE 8080
ENTRYPOINT ["/pulso"]
EOF
```

El segundo hace lo que hace mucha gente al empezar: compila y se queda ahí.

```bash
cat > Dockerfile.gordo <<'EOF'
# La misma app, sin multi-stage: el binario viaja junto al compilador entero
FROM golang:1.25-alpine
WORKDIR /src
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -o /pulso .
EXPOSE 8080
ENTRYPOINT ["/pulso"]
EOF
```

Tres decisiones del primero, y las tres se ven en este laboratorio:

- **`CGO_ENABLED=0`** produce un binario estático: no necesita la `libc` del sistema. Por eso
  sirve la base `static`, la más pequeña de la familia distroless.
- **`static-debian13:nonroot`** no trae shell, ni gestor de paquetes, ni `ls`, ni `ps`. Trae
  certificados CA, datos de zona horaria, `/etc/passwd` con el usuario `nonroot` y poco más.
- **`:nonroot`** hace que el proceso corra con UID **65532**, no como root. En el módulo 7
  verás por qué eso importa; hoy lo vas a medir.

🔮 **Predice** (escríbelo en `predicciones.md`): ¿cuánto pesará cada imagen? ¿Cuántas
veces más grande será la «gorda»?

```bash
docker build -q -t pulso:1.0 .
docker build -q -t pulso:gordo -f Dockerfile.gordo .
docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' pulso
```

**Salida real de esta máquina:**

```
sha256:ca2a57e04f95fa70e68d31379add6264fa0dd63b965f2ed1c352a1fd8cea2b5b
sha256:51b3f914726e049bf5489503b9c20893e43bf7206c495683306e65533796eb91
REPOSITORY   TAG       SIZE
pulso        gordo     448MB
pulso        1.0       14.6MB
```

La primera construcción descarga `golang:1.25-alpine` y la base distroless; tarda más.

### 1.3 Contar lo que viaja dentro

El tamaño es la mitad de la historia. La otra mitad es **cuántas cosas** van dentro, porque
cada archivo es algo que un atacante puede usar o que un escáner puede marcar:

```bash
for t in gordo 1.0; do
  c=$(docker create pulso:$t)
  echo "pulso:$t -> $(docker export $c | tar -t | wc -l) archivos"
  docker rm $c >/dev/null
done
docker inspect pulso:1.0 --format 'Usuario={{.Config.User}}  Entrypoint={{.Config.Entrypoint}}'
```

**Salida real de esta máquina:**

```
pulso:gordo -> 18553 archivos
pulso:1.0 -> 1403 archivos
Usuario=65532  Entrypoint=[/pulso]
```

Y la prueba que más enseña: arranca la imagen distroless e intenta entrar.

```bash
docker run -d --name pulso-local -p 18080:8080 -e STARTUP_SECONDS=3 pulso:1.0
sleep 1; curl -s -w ' [HTTP %{http_code}]\n' localhost:18080/startupz
sleep 3; curl -s -w ' [HTTP %{http_code}]\n' localhost:18080/startupz
docker exec pulso-local sh; echo "codigo de salida: $?"
docker rm -f pulso-local >/dev/null
```

**Salida real de esta máquina:**

```
9db797fa76a3dd8e9e08c97948a0dfb8a2ee44948d4d591c374983059b923163
todavia arrancando
 [HTTP 503]
arrancado
 [HTTP 200]
OCI runtime exec failed: exec failed: unable to start container process: exec: "sh": executable file not found in $PATH
codigo de salida: 127
```

`executable file not found in $PATH`: **no hay `sh`**. No es un error de la imagen, es su
diseño. Guarda esta línea: en el Paso 3 la vas a ver otra vez, ya dentro de Kubernetes.

### 1.4 (Opcional, si tienes `trivy`) Escanear las dos

```bash
trivy image --quiet --scanners vuln pulso:gordo 2>/dev/null | sed -n '1,8p'
trivy image --quiet --scanners vuln pulso:1.0   2>/dev/null | sed -n '1,9p'
```

**Salida real de esta máquina** (el 26 de septiembre de 2026; la base de vulnerabilidades
cambia cada día, así que tus números serán otros):

```
Report Summary

┌──────────────────────────────────────────────┬──────────┬─────────────────┐
│                    Target                    │   Type   │ Vulnerabilities │
├──────────────────────────────────────────────┼──────────┼─────────────────┤
│ pulso:gordo (alpine 3.24.1)                  │  alpine  │       20        │
├──────────────────────────────────────────────┼──────────┼─────────────────┤

Report Summary

┌─────────────────────────┬──────────┬─────────────────┐
│         Target          │   Type   │ Vulnerabilities │
├─────────────────────────┼──────────┼─────────────────┤
│ pulso:1.0 (debian 13.7) │  debian  │        0        │
├─────────────────────────┼──────────┼─────────────────┤
│ pulso                   │ gobinary │        0        │
```

**El mismo binario de Go, cero vulnerabilidades en los dos casos.** Las 20 de la imagen
gorda vienen del sistema operativo Alpine y del toolchain que **no necesitas en
producción**. La base distroless es Debian 13, y también se escanea, pero trae tan poco
que no hay nada que reportar hoy.

> **Lo que distroless NO es:** no es «sin sistema operativo» (trivy detecta `debian 13`),
> y no es inmune (mañana puede aparecer una CVE en sus certificados o en `tzdata`). Es
> **superficie mínima**. Reconstruir la imagen con frecuencia sigue siendo obligatorio.

---

## Paso 2: Llevar la imagen al clúster (10 min)

`kind` no ve las imágenes de tu Docker: cada nodo es un contenedor con su propio
`containerd`. Hay que cargarla. Para demostrar una trampa, cárgala también con la etiqueta
`latest`:

```bash
cd ~/lab-ckad-1
docker tag pulso:1.0 pulso:latest
kind load docker-image pulso:1.0 pulso:latest --name ckad
docker exec ckad-worker crictl images | grep -E 'IMAGE|pulso'
```

**Salida real de esta máquina** (recortada):

```
IMAGE                                           TAG                  IMAGE ID            SIZE
docker.io/library/pulso                         1.0                  7d1f506ed5d46       3.27MB
docker.io/library/pulso                         latest               7d1f506ed5d46       3.27MB
```

La imagen **está en el nodo**, con las dos etiquetas y el mismo ID.

🔮 **Predice:** vas a crear dos Pods idénticos, uno con `pulso:1.0` y otro con `pulso` (sin
etiqueta). Los dos encuentran la imagen en el nodo. ¿Arrancan los dos?

```bash
kubectl run con-tag --image=pulso:1.0
kubectl run sin-tag --image=pulso
sleep 15
kubectl get pods
kubectl get pod con-tag sin-tag \
  -o custom-columns='POD:.metadata.name,IMAGEN:.spec.containers[0].image,PULL:.spec.containers[0].imagePullPolicy'
kubectl describe pod sin-tag | grep -E 'Failed to pull' | head -1
```

**Salida real de esta máquina:**

```
pod/con-tag created
pod/sin-tag created
NAME      READY   STATUS         RESTARTS   AGE
con-tag   1/1     Running        0          15s
sin-tag   0/1     ErrImagePull   0          15s
POD       IMAGEN      PULL
con-tag   pulso:1.0   IfNotPresent
sin-tag   pulso       Always
  Warning  Failed     10s   kubelet            spec.containers{sin-tag}: Failed to pull image "pulso": failed to pull and unpack image "docker.io/library/pulso:latest": failed to resolve reference "docker.io/library/pulso:latest": pull access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
```

**`sin-tag` falla con la imagen en el nodo** (verás `ErrImagePull` o `ImagePullBackOff`:
alternan mientras el kubelet reintenta con esperas cada vez más largas). Sin etiqueta, Kubernetes asume `:latest`, y
con `:latest` el valor por defecto de `imagePullPolicy` es **`Always`**: el kubelet **ignora
la copia local** y va a Docker Hub a resolver `docker.io/library/pulso:latest`, que no
existe. Con una etiqueta explícita el defecto es `IfNotPresent`, y usa la copia local.

Dos lecciones, una de examen y otra de oficio:

- `imagePullPolicy` **se fija al crear el objeto** y se deriva de la etiqueta. Léelo con
  `-o custom-columns` en vez de suponerlo.
- En producción, ni siquiera una etiqueta basta: una etiqueta se puede volver a publicar
  apuntando a otros bytes. Lo inmutable es el **digest**, y el kubelet te dice cuál corrió:

```bash
kubectl get pod con-tag -o jsonpath='{.status.containerStatuses[0].imageID}{"\n"}'
kubectl delete pod sin-tag --now
```

**Salida real de esta máquina:**

```
docker.io/library/import-2026-09-26@sha256:f3bc0a51e4f9049c12208d2bb6e8ba2a13786b247994d368b52bcdc4dcfbaca9
pod "sin-tag" deleted from lab1 namespace
```

Fíjate en el nombre: `import-<fecha>`. `kind load` **importa** la imagen al `containerd` del
nodo sin pasar por ningún registro, y el runtime la registra con ese nombre interno. Con un
registro real verías `registro/imagen@sha256:...`, y **ese** es el valor que se pega en un
manifiesto de producción: `image: registro/pulso@sha256:...`.

---

## Paso 3: `kubectl debug` (25 min)

### 3.1 La puerta cerrada

```bash
kubectl exec con-tag -- sh
```

**Salida real de esta máquina:**

```
error: Internal error occurred: Internal error occurred: error executing command in container: failed to exec in container: failed to start exec "b51b7ba74c24c4a7df8081d632b8900c8eb299999c6ffbb839aebf850f8dfe94": OCI runtime exec failed: exec failed: unable to start container process: exec: "sh": executable file not found in $PATH
```

La misma línea del Paso 1.3, ahora dentro de Kubernetes. Una imagen bien construida no te
deja entrar con `exec`. Tienes tres herramientas, una para cada situación:

| Situación | Herramienta | Qué crea |
|---|---|---|
| El Pod está corriendo y quieres mirar **dentro** | contenedor efímero (`kubectl debug <pod> --target`) | un contenedor nuevo **dentro del mismo Pod** |
| El Pod se cae y no te da tiempo de mirar | copia (`kubectl debug <pod> --copy-to`) | un Pod **nuevo**, copia del original, con cambios |
| Sospechas del **nodo** | `kubectl debug node/<nodo>` | un Pod en el nodo con el sistema de archivos del host en `/host` |

### 3.2 Un contenedor efímero

🔮 **Predice:** vas a meter un busybox **dentro** del Pod `con-tag`. ¿Qué PID tendrá el
proceso `/pulso`? ¿Con qué usuario corre?

```bash
kubectl debug -it con-tag --image=busybox:1.37 --target=con-tag -c depurador -- sh
```

Ya estás dentro del depurador. Ejecuta allí:

```sh
ps -o pid,user,args
ls /proc/1/root/
wget -qO- localhost:8080/
exit
```

**Salida real de esta máquina:**

```
All commands and output from this session will be recorded in container logs, including credentials and sensitive information passed through the command prompt.
If you don't see a command prompt, try pressing enter.
PID   USER     COMMAND
    1 65532    /pulso
   24 root     sh
   37 root     ps -o pid,user,args
bin
boot
dev
etc
home
lib
lib64
proc
product_name
product_uuid
pulso
root
run
sbin
sys
tmp
usr
var
pulso v1 desde con-tag
```

Cuatro cosas que acabas de ver, y las cuatro caen en el examen:

- **`--target=con-tag`** comparte el **namespace de procesos** con ese contenedor. Por eso
  `ps` ve a `/pulso` como PID 1, con el UID **65532** que fijó `:nonroot`. Sin `--target`
  solo verías tus propios procesos.
- **`/proc/1/root/`** es el sistema de archivos **del contenedor de la app**, visto desde
  el depurador. Ahí está el binario `pulso`. Así se inspecciona un archivo de configuración
  en una imagen sin `cat`.
- **`localhost:8080`** funciona porque **todos los contenedores de un Pod comparten la
  red**. Eso no depende de `--target`.
- Tu depurador corre como **root** con `busybox`, aunque la app sea `nonroot`. Lo decide el
  **perfil** de depuración.

Los perfiles se eligen con `--profile`, y **el perfil por defecto cambió**: desde `kubectl`
v1.36 es `general` (antes era `legacy`, que se retirará en v1.39). Compruébalo en tu propio
`kubectl`, no en un blog:

```bash
kubectl debug --help | grep -A1 -- '--profile='
```

**Salida real de esta máquina:**

```
    --profile='general':
	Options are "general", "baseline", "restricted", "netadmin" or "sysadmin". Defaults to "general"
```

Y la propiedad que más sorprende: el contenedor efímero **no se puede borrar**. Terminó,
pero se queda en la especificación del Pod para siempre, hasta que el Pod muera:

```bash
kubectl get pod con-tag -o jsonpath='{range .status.ephemeralContainerStatuses[*]}{.name}{" -> "}{.state.terminated.reason}{"\n"}{end}'
kubectl logs con-tag -c depurador | head -3
```

**Salida real de esta máquina:**

```
depurador -> Completed
PID   USER     COMMAND
    1 65532    /pulso
   24 root     sh
```

Todo lo que tecleaste quedó en los logs del Pod. `kubectl debug` te lo advierte al entrar:
**no pegues contraseñas en un depurador**.

### 3.3 Un Pod que se cae: la copia

Este Pod espera un archivo de configuración y muere si no lo encuentra:

```bash
cat > roto.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: roto-config
data:
  aplicacion.conf: |
    modo=produccion
    puerto=8080
---
apiVersion: v1
kind: Pod
metadata:
  name: roto
spec:
  containers:
  - name: app
    image: busybox:1.37
    command: ["sh", "-c", "echo leyendo /config/app.conf; cat /config/app.conf || exit 1; sleep 3600"]
    volumeMounts:
    - name: config
      mountPath: /config
  volumes:
  - name: config
    configMap:
      name: roto-config
EOF

kubectl apply -f roto.yaml
sleep 25
kubectl get pod roto
kubectl logs roto
```

**Salida real de esta máquina:**

```
configmap/roto-config created
pod/roto created
NAME   READY   STATUS   RESTARTS      AGE
roto   0/1     Error    2 (24s ago)   25s
leyendo /config/app.conf
cat: can't open '/config/app.conf': No such file or directory
```

`kubectl logs` ya te da el síntoma: `/config/app.conf` no existe. Pero **¿qué hay en
`/config`?** Un contenedor efímero no sirve de mucho aquí: la app vive un instante y el
proceso ya no está. La herramienta es una **copia** del Pod, con el comando cambiado para
que no muera:

```bash
kubectl debug roto -it --copy-to=roto-copia --container=app -- sh
```

Dentro de la copia:

```sh
ls -l /config/
exit
```

**Salida real de esta máquina** (el comando `ls` dentro de la copia):

```
total 0
lrwxrwxrwx    1 root     root            22 Sep 26 04:33 aplicacion.conf -> ..data/aplicacion.conf
```

**Ahí está la causa:** el ConfigMap trae la clave `aplicacion.conf`, y la app busca
`app.conf`. La copia monta **los mismos volúmenes** que el original, así que ves
exactamente lo que vería la app.

> **Un detalle que vas a ver y que conviene entender.** Con `kind` v0.33 y Kubernetes
> v1.37, mientras el contenedor espera su siguiente reinicio la columna `STATUS` alterna
> entre `Error` y `CrashLoopBackOff`, y `kubectl logs roto --previous` puede responder
> `unable to retrieve container logs`. En esta máquina el directorio de logs del nodo
> (`/var/log/pods/lab1_roto_*/app/`) solo conservaba el archivo del **último** intento: el
> anterior ya se había borrado. Por eso, en un Pod que muere en bucle, empieza por
> `kubectl logs <pod>` (el último intento muerto). `--previous` brilla en otro caso, el del
> Paso 4.4: cuando el contenedor **actual** ya está vivo otra vez y quieres ver al que murió.

Limpia la copia (**no se borra sola**) y el Pod roto:

```bash
kubectl delete pod roto roto-copia --now
kubectl delete configmap roto-config
```

### 3.4 Depurar el nodo

¿Y si el problema no está en el Pod sino en el nodo? `kubectl debug node/...` crea un Pod
privilegiado **en ese nodo**, con el sistema de archivos del host montado en `/host`:

```bash
kubectl debug node/ckad-worker -it --image=busybox:1.37
```

Dentro:

```sh
chroot /host crictl ps --name con-tag
exit
```

**Salida real de esta máquina:**

```
All commands and output from this session will be recorded in container logs, including credentials and sensitive information passed through the command prompt.
If you don't see a command prompt, try pressing enter.
CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID              POD                 NAMESPACE
bab1f67ba6ea2       7d1f506ed5d46       57 seconds ago      Running             con-tag             0                   9515695bcceff       con-tag             lab1
```

`chroot /host` te pone en el sistema de archivos del nodo, donde sí existe `crictl`, la
herramienta del runtime de contenedores. Esto **ya no es trabajo de desarrollador**: es la
frontera con el CKA. Úsalo cuando `kubectl` no te alcance, y bórralo al salir, porque es
un Pod privilegiado y se queda en `Completed`:

```bash
kubectl get pods -o name | grep node-debugger | xargs kubectl delete --now
```

---

## Paso 4: Las tres probes (30 min)

| Probe | Pregunta | Si falla |
|---|---|---|
| `startupProbe` | ¿Ya terminaste de arrancar? | Reinicia el contenedor. **Mientras no pase, las otras dos no se ejecutan** |
| `livenessProbe` | ¿Sigues vivo? | Reinicia el contenedor. `RESTARTS` sube |
| `readinessProbe` | ¿Puedes atender tráfico ahora? | **No reinicia nada.** Te saca del tráfico del Service |

### 4.1 Fallo productivo: una app lenta con solo `livenessProbe`

`pulso` va a tardar **60 segundos** en arrancar. La `livenessProbe` pregunta cada 5
segundos y tolera 3 fallos.

🔮 **Predice:** ¿qué verás en `RESTARTS` a los 80 segundos? ¿Llegará a arrancar alguna vez?

```bash
cat > lento-sin-startup.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: lento-sin-startup
spec:
  containers:
  - name: app
    image: pulso:1.0
    env:
    - name: STARTUP_SECONDS
      value: "60"
    livenessProbe:
      httpGet: { path: /healthz, port: 8080 }
      periodSeconds: 5
      failureThreshold: 3
EOF

cat > lento-con-startup.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: lento-con-startup
spec:
  containers:
  - name: app
    image: pulso:1.0
    env:
    - name: STARTUP_SECONDS
      value: "60"
    startupProbe:
      httpGet: { path: /startupz, port: 8080 }
      periodSeconds: 5
      failureThreshold: 24      # 24 x 5 s = 120 s de margen para arrancar
    livenessProbe:
      httpGet: { path: /healthz, port: 8080 }
      periodSeconds: 5
      failureThreshold: 3
EOF

kubectl apply -f lento-sin-startup.yaml -f lento-con-startup.yaml
for t in 20 40 60 80; do sleep 20; echo "== t=${t}s"; kubectl get pods lento-sin-startup lento-con-startup; done
```

**Salida real de esta máquina:**

```
pod/lento-sin-startup created
pod/lento-con-startup created
== t=20s
NAME                READY   STATUS    RESTARTS     AGE
lento-sin-startup   1/1     Running   1 (5s ago)   20s
lento-con-startup   0/1     Running   0            20s
== t=40s
NAME                READY   STATUS    RESTARTS      AGE
lento-sin-startup   1/1     Running   2 (10s ago)   40s
lento-con-startup   0/1     Running   0             40s
== t=60s
NAME                READY   STATUS    RESTARTS      AGE
lento-sin-startup   1/1     Running   3 (15s ago)   60s
lento-con-startup   0/1     Running   0             60s
== t=80s
NAME                READY   STATUS             RESTARTS      AGE
lento-sin-startup   0/1     CrashLoopBackOff   3 (20s ago)   80s
lento-con-startup   1/1     Running            0             80s
```

Lee las dos filas como un diagnóstico:

- **`lento-sin-startup` no va a arrancar jamás.** Cada 15 segundos (3 fallos x 5 s) el
  kubelet lo mata, y cada reinicio **vuelve a poner el reloj de arranque en cero**. Los 60
  segundos nunca se cumplen. Es el bucle del reto del módulo, en vivo.
- **Y mira su columna `READY`: dice `1/1`** mientras la app responde `503` a todo. No tiene
  `readinessProbe`, así que para Kubernetes «el proceso existe» equivale a «está listo». Un
  Service le mandaría tráfico. Guárdalo para el 4.3.
- **`lento-con-startup` espera `0/1` sin reiniciarse** y pasa a `1/1` cuando la app termina
  de arrancar. La `startupProbe` concede `24 x 5 = 120` segundos y, mientras corre, la
  `livenessProbe` **no se ejecuta**.

Los eventos cuentan lo mismo, con la probe que falló en cada caso:

```bash
kubectl describe pod lento-sin-startup | grep -E 'Unhealthy|Killing' | head -2
kubectl describe pod lento-con-startup | grep -E 'Unhealthy' | head -1
kubectl delete pod lento-sin-startup lento-con-startup --now
```

**Salida real de esta máquina:**

```
  Warning  Unhealthy  20s (x12 over 75s)  kubelet            spec.containers{app}: Liveness probe failed: HTTP probe failed with statuscode: 503
  Normal   Killing    20s (x4 over 65s)   kubelet            spec.containers{app}: Container app failed liveness probe, will be restarted
  Warning  Unhealthy  20s (x12 over 75s)  kubelet            spec.containers{app}: Startup probe failed: HTTP probe failed with statuscode: 503
pod "lento-sin-startup" deleted from lab1 namespace
pod "lento-con-startup" deleted from lab1 namespace
```

> **La regla que sale de aquí:** el tiempo máximo de arranque es `failureThreshold x
> periodSeconds` de la `startupProbe`. Nunca subas `initialDelaySeconds` de la liveness
> para «dar tiempo»: si la app arranca rápido, esperas de más; si tarda más de lo previsto,
> vuelves al bucle.

### 4.2 Las tres juntas, en un Deployment con Service

Genera el esqueleto como en el examen, y mira lo que `create` **no** sabe poner:

```bash
kubectl create deployment pulso --image=pulso:1.0 --replicas=3 --port=8080 $do | grep -E 'Probe|replicas|image'
```

**Salida real de esta máquina:**

```
  replicas: 3
      - image: pulso:1.0
```

Ninguna probe: esas se escriben a mano. Este es el manifiesto completo:

```bash
cat > pulso-deploy.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pulso
spec:
  replicas: 3
  selector:
    matchLabels: { app: pulso }
  template:
    metadata:
      labels: { app: pulso }
    spec:
      containers:
      - name: app
        image: pulso:1.0
        ports: [{ containerPort: 8080 }]
        startupProbe:
          httpGet: { path: /startupz, port: 8080 }
          periodSeconds: 2
          failureThreshold: 30
        readinessProbe:
          httpGet: { path: /readyz, port: 8080 }
          periodSeconds: 3
          failureThreshold: 1
        livenessProbe:
          httpGet: { path: /healthz, port: 8080 }
          periodSeconds: 5
          timeoutSeconds: 1
          failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: pulso
spec:
  selector: { app: pulso }
  ports: [{ port: 80, targetPort: 8080 }]
EOF

kubectl apply -f pulso-deploy.yaml
kubectl rollout status deploy/pulso --timeout=120s
kubectl run cliente --image=busybox:1.37 --restart=Never -- sleep 3600
kubectl wait --for=condition=Ready pod/cliente --timeout=60s
kubectl get pods -l app=pulso
```

**Salida real de esta máquina:**

```
deployment.apps/pulso created
service/pulso created
Waiting for deployment "pulso" rollout to finish: 0 of 3 updated replicas are available...
Waiting for deployment "pulso" rollout to finish: 1 of 3 updated replicas are available...
Waiting for deployment "pulso" rollout to finish: 2 of 3 updated replicas are available...
deployment "pulso" successfully rolled out
pod/cliente created
pod/cliente condition met
NAME                     READY   STATUS    RESTARTS   AGE
pulso-675875fcdc-2dswt   1/1     Running   0          3s
pulso-675875fcdc-gpmqz   1/1     Running   0          4s
pulso-675875fcdc-rc2cn   1/1     Running   0          3s
```

`cliente` es un Pod desde el que vas a hablarle a `pulso`. Ni `pulso` ni `busybox` necesitan
nada más.

### 4.3 `readinessProbe`: fuera del tráfico, sin reiniciar

Elige una víctima y dile que su «base de datos» se cayó:

```bash
P=$(kubectl get pod -l app=pulso -o jsonpath='{.items[0].metadata.name}')
IP=$(kubectl get pod $P -o jsonpath='{.status.podIP}')
echo "victima: $P ($IP)"
kubectl exec cliente -- wget -qO- http://$IP:8080/admin/no-listo
sleep 5
kubectl get pods -l app=pulso
```

**Salida real de esta máquina:**

```
victima: pulso-675875fcdc-2dswt (10.244.1.10)
no listo
NAME                     READY   STATUS    RESTARTS   AGE
pulso-675875fcdc-2dswt   0/1     Running   0          8s
pulso-675875fcdc-gpmqz   1/1     Running   0          9s
pulso-675875fcdc-rc2cn   1/1     Running   0          8s
```

`0/1 Running`, **`RESTARTS 0`**. El contenedor sigue vivo. 🔮 **Predice:** si mandas 30
peticiones al Service, ¿cuántas llegan a la víctima?

```bash
kubectl exec cliente -- sh -c 'for i in $(seq 1 30); do wget -qO- http://pulso; done' | sort | uniq -c
```

**Salida real de esta máquina:**

```
     12 pulso v1 desde pulso-675875fcdc-gpmqz
     18 pulso v1 desde pulso-675875fcdc-rc2cn
```

**Ninguna.** Ahora mira dónde se decide eso. Aquí hay una sorpresa respecto a lo que dicen
muchas guías (y la versión corta de la diapositiva):

```bash
kubectl get endpointslices -l kubernetes.io/service-name=pulso
kubectl get endpointslices -l kubernetes.io/service-name=pulso \
  -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}{"  ready="}{.conditions.ready}{"  pod="}{.targetRef.name}{"\n"}{end}'
```

**Salida real de esta máquina:**

```
NAME          ADDRESSTYPE   PORTS   ENDPOINTS                           AGE
pulso-69mb6   IPv4          8080    10.244.1.8,10.244.1.10,10.244.1.9   8s
10.244.1.8  ready=true  pod=pulso-675875fcdc-gpmqz
10.244.1.10  ready=false  pod=pulso-675875fcdc-2dswt
10.244.1.9  ready=true  pod=pulso-675875fcdc-rc2cn
```

**La IP de la víctima sigue en el EndpointSlice**, y la columna `ENDPOINTS` la lista. Lo que
cambió es su condición: **`ready=false`**. `kube-proxy` solo manda tráfico a los endpoints
`ready=true`. Si diagnosticas un Service mirando solo la columna `ENDPOINTS`, vas a creer que
los tres Pods reciben tráfico. Mira las condiciones.

Devuélvela al tráfico:

```bash
kubectl exec cliente -- wget -qO- http://$IP:8080/admin/listo
```

### 4.4 `livenessProbe`: un deadlock de verdad

`/admin/colgar` hace que `/healthz` **no responda nunca**, como un proceso atascado en un
lock. La probe tiene `timeoutSeconds: 1` y `failureThreshold: 3`.

🔮 **Predice:** ¿en cuántos segundos, más o menos, verás `RESTARTS 1`?

```bash
P=$(kubectl get pod -l app=pulso -o jsonpath='{.items[1].metadata.name}')
IP=$(kubectl get pod $P -o jsonpath='{.status.podIP}')
date +%T; kubectl exec cliente -- wget -qO- http://$IP:8080/admin/colgar
sleep 25
date +%T; kubectl get pods -l app=pulso
kubectl describe pod $P | grep -E 'Unhealthy|Killing'
```

**Salida real de esta máquina:**

```
23:34:45
colgado
23:35:10
NAME                     READY   STATUS    RESTARTS      AGE
pulso-675875fcdc-2dswt   1/1     Running   0             33s
pulso-675875fcdc-gpmqz   1/1     Running   1 (12s ago)   34s
pulso-675875fcdc-rc2cn   1/1     Running   0             33s
  Warning  Unhealthy  12s (x3 over 22s)  kubelet            spec.containers{app}: Liveness probe failed: Get "http://10.244.1.8:8080/healthz": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
  Normal   Killing    12s                kubelet            spec.containers{app}: Container app failed liveness probe, will be restarted
```

`context deadline exceeded`: la petición **no falló, se quedó sin respuesta**, que es lo que
hace un deadlock. Tres veces, y el kubelet lo reinició. Ahora la pregunta de diagnóstico:
**¿qué pasó antes de morir?** El contenedor actual acaba de nacer y no lo sabe. El anterior sí:

```bash
kubectl logs $P --previous
kubectl get pod $P -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason} exit={.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
```

**Salida real de esta máquina:**

```
2026/09/26 04:34:37 pulso v1 escuchando en :8080 (arranque simulado: 0s)
2026/09/26 04:34:45 ADMIN: me cuelgo, /healthz ya no respondera
Error exit=2
```

La última línea del contenedor muerto es la orden que lo colgó. Y el código de salida es
**2**, no 137: el kubelet mandó `SIGTERM`, y el runtime de Go, que no tiene un manejador
instalado en esta app, **termina el programa** al recibirla. En esta máquina ese código fue
2. Compáralo con el `137` del Paso 7.

---

## Paso 5: Init containers (10 min)

Un init container corre **antes** que la app, **uno detrás de otro**, y cada uno debe
terminar bien antes de que empiece el siguiente. Este Pod espera a su base de datos y luego
aplica una «migración»:

```bash
cat > espera.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: espera
spec:
  initContainers:
  - name: espera-base-datos
    image: busybox:1.37
    env:
    - name: MI_NAMESPACE             # Downward API: el Pod se entera de su namespace
      valueFrom:
        fieldRef: { fieldPath: metadata.namespace }
    command: ["sh", "-c", "until nslookup basedatos.$MI_NAMESPACE.svc.cluster.local > /dev/null 2>&1; do echo 'basedatos aun no existe'; sleep 2; done; echo 'basedatos resuelve'"]
  - name: migracion
    image: busybox:1.37
    command: ["sh", "-c", "echo 'aplicando migraciones...'; sleep 5; echo 'esquema v2 listo' > /trabajo/esquema"]
    volumeMounts: [{ name: trabajo, mountPath: /trabajo }]
  containers:
  - name: app
    image: busybox:1.37
    command: ["sh", "-c", "echo \"arranco con $(cat /trabajo/esquema)\"; sleep 3600"]
    volumeMounts: [{ name: trabajo, mountPath: /trabajo }]
  volumes:
  - name: trabajo
    emptyDir: {}
EOF

kubectl apply -f espera.yaml
sleep 10; kubectl get pod espera
```

**Salida real de esta máquina:**

```
pod/espera created
NAME     READY   STATUS     RESTARTS   AGE
espera   0/1     Init:0/2   0          10s
```

`Init:0/2`: el primero de dos no ha terminado. 🔮 **Predice:** vas a crear el Service
`basedatos`. ¿Qué verás a los 5 y a los 12 segundos?

```bash
kubectl create service clusterip basedatos --tcp=5432:5432
sleep 5; kubectl get pod espera
sleep 7; kubectl get pod espera
kubectl logs espera -c espera-base-datos | tail -2
kubectl logs espera -c migracion
kubectl logs espera -c app
```

**Salida real de esta máquina:**

```
service/basedatos created
NAME     READY   STATUS     RESTARTS   AGE
espera   0/1     Init:1/2   0          15s
NAME     READY   STATUS    RESTARTS   AGE
espera   1/1     Running   0          22s
basedatos aun no existe
basedatos resuelve
aplicando migraciones...
arranco con esquema v2 listo
```

`Init:0/2`, luego `Init:1/2`, luego `Running`: **estrictamente en secuencia**. Y el archivo
que escribió `migracion` en el `emptyDir` lo leyó `app`: los init containers preparan el
terreno.

Dos detalles del manifiesto que valen oro:

- **`fieldRef: metadata.namespace`** es la **Downward API**: el Pod se entera de su propio
  namespace sin que lo escribas a mano. Sirve igual para el nombre del Pod, su IP o sus
  etiquetas.
- **¿Por qué el nombre completo** `basedatos.$MI_NAMESPACE.svc.cluster.local` y no solo
  `basedatos`? Porque así se escribió la primera versión, y **se quedó en `Init:0/2` para
  siempre aunque el Service existía**. El `nslookup` de busybox recorre los dominios de
  búsqueda de `/etc/resolv.conf` y devuelve error si el último responde `NXDOMAIN`. Un nombre
  completo no depende de esa lista. Es un error real, cometido al preparar este laboratorio.

```bash
kubectl delete pod espera --now
kubectl delete service basedatos
```

---

## Paso 6: Sidecars nativos (15 min)

### 6.1 El Job que nunca termina

Un Job escribe tres líneas de log y termina. Un segundo contenedor las «envía» (aquí, las
imprime con `tail -F`). Primero, el sidecar **a la antigua**: un contenedor más en
`containers:`.

```bash
cat > job-sidecar-clasico.yaml <<'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: reporte-clasico
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: reporte
        image: busybox:1.37
        command: ["sh", "-c", "for i in 1 2 3; do echo \"linea $i\" >> /logs/app.log; sleep 2; done; echo FIN"]
        volumeMounts: [{ name: logs, mountPath: /logs }]
      - name: enviador-logs          # sidecar "a la antigua": un contenedor mas
        image: busybox:1.37
        command: ["sh", "-c", "touch /logs/app.log; tail -F /logs/app.log"]
        volumeMounts: [{ name: logs, mountPath: /logs }]
      volumes:
      - name: logs
        emptyDir: {}
EOF
```

Ahora el sidecar **nativo**: el mismo contenedor, movido a `initContainers:` con
`restartPolicy: Always`.

```bash
cat > job-sidecar-nativo.yaml <<'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: reporte-nativo
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      initContainers:
      - name: enviador-logs          # sidecar nativo: initContainer + restartPolicy Always
        image: busybox:1.37
        restartPolicy: Always
        command: ["sh", "-c", "touch /logs/app.log; tail -F /logs/app.log"]
        volumeMounts: [{ name: logs, mountPath: /logs }]
      containers:
      - name: reporte
        image: busybox:1.37
        command: ["sh", "-c", "for i in 1 2 3; do echo \"linea $i\" >> /logs/app.log; sleep 2; done; echo FIN"]
        volumeMounts: [{ name: logs, mountPath: /logs }]
      volumes:
      - name: logs
        emptyDir: {}
EOF
```

🔮 **Predice:** el trabajo dura 6 segundos. ¿Cuál de los dos Jobs aparece `Complete`, y en
cuánto tiempo?

```bash
kubectl apply -f job-sidecar-clasico.yaml -f job-sidecar-nativo.yaml
sleep 50
kubectl get jobs
kubectl get pods -l 'batch.kubernetes.io/job-name in (reporte-clasico,reporte-nativo)'
kubectl logs job/reporte-nativo -c enviador-logs
```

**Salida real de esta máquina:**

```
job.batch/reporte-clasico created
job.batch/reporte-nativo created
NAME              STATUS     COMPLETIONS   DURATION   AGE
reporte-clasico   Running    0/1           51s        51s
reporte-nativo    Complete   1/1           40s        51s
NAME                    READY   STATUS      RESTARTS   AGE
reporte-clasico-qwdkw   1/2     NotReady    0          51s
reporte-nativo-xfqvw    0/2     Completed   0          51s
linea 1
linea 2
linea 3
```

- **`reporte-clasico` está `Running` para siempre**, con el Pod en `1/2 NotReady`: el
  contenedor `reporte` terminó, pero `tail -F` no termina nunca, y un Job solo completa
  cuando **todos** los contenedores de `containers:` terminaron. Es el sidecar zombi de la
  primera diapositiva del módulo.
- **`reporte-nativo` completó.** El kubelet sabe que un init container con
  `restartPolicy: Always` es un sidecar: no espera a que termine, y lo apaga cuando el
  contenedor principal sale. Estable desde Kubernetes v1.33.

### 6.2 El misterio de los 30 segundos

Mira otra vez la columna `DURATION` de `reporte-nativo`. El trabajo duraba 6 segundos.

```bash
kubectl get pod -l batch.kubernetes.io/job-name=reporte-nativo \
  -o jsonpath='{.items[0].spec.terminationGracePeriodSeconds}{"\n"}'
```

**Salida real de esta máquina:**

```
30
```

Esta es la explicación. Para apagar el sidecar, el kubelet le manda `SIGTERM`. Pero `sh`
corre como **PID 1** de su contenedor, y el kernel de Linux solo entrega a un PID 1 las
señales **para las que instaló un manejador** (`pid_namespaces(7)`). `sh` no instaló
ninguno, así que ignora el `SIGTERM`. El kubelet espera el periodo de gracia, **30
segundos**, y lo mata con `SIGKILL`.

La corrección es **una línea**: instalar el manejador.

```bash
sed -e 's/name: reporte-nativo/name: reporte-nativo-v2/' \
    -e "s|\"touch /logs/app.log; tail -F /logs/app.log\"|\"trap 'exit 0' TERM; touch /logs/app.log; tail -F /logs/app.log \& wait\"|" \
    job-sidecar-nativo.yaml > job-sidecar-nativo-v2.yaml
grep -n 'trap' job-sidecar-nativo-v2.yaml
kubectl apply -f job-sidecar-nativo-v2.yaml
kubectl wait --for=condition=complete job/reporte-nativo-v2 --timeout=90s
kubectl get jobs
```

**Salida real de esta máquina:**

```
14:        command: ["sh", "-c", "trap 'exit 0' TERM; touch /logs/app.log; tail -F /logs/app.log & wait"]
job.batch/reporte-nativo-v2 created
job.batch/reporte-nativo-v2 condition met
NAME                STATUS     COMPLETIONS   DURATION   AGE
reporte-clasico     Running    0/1           61s        61s
reporte-nativo      Complete   1/1           40s        61s
reporte-nativo-v2   Complete   1/1           10s        10s
```

**De 40 a 10 segundos.** `tail -F ... & wait` deja a `sh` esperando, con su manejador
listo: al llegar `SIGTERM`, sale con código 0. En tu propio código (Go, Python, Java) el
equivalente es **capturar `SIGTERM` y cerrar ordenadamente**. Un sidecar que ignora
`SIGTERM` retrasa **cada** apagado de **cada** Pod que lo lleva.

```bash
kubectl delete job reporte-clasico reporte-nativo reporte-nativo-v2
```

### 6.3 El sidecar arranca primero, y la app lo espera

El otro regalo del sidecar nativo es el **orden de arranque**. Aquí `pulso` hace de
«proxy» que tarda 15 segundos en estar listo, y la app lo necesita desde su primer segundo:

```bash
cat > orden.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: orden
spec:
  initContainers:
  - name: proxy                       # sidecar nativo que tarda 15 s en estar listo
    image: pulso:1.0
    restartPolicy: Always
    env:
    - { name: STARTUP_SECONDS, value: "15" }
    startupProbe:
      httpGet: { path: /startupz, port: 8080 }
      periodSeconds: 2
      failureThreshold: 15
  containers:
  - name: app                         # necesita al proxy desde su primer segundo
    image: busybox:1.37
    command: ["sh", "-c", "date +'%T app: arranco'; wget -qO- http://localhost:8080/ || echo 'app: el proxy no contesta'; sleep 3600"]
EOF

kubectl apply -f orden.yaml
for i in 1 2 3 4 5; do sleep 5; kubectl get pod orden --no-headers; done
kubectl logs orden -c app
kubectl get pod orden -o jsonpath='{range .status.initContainerStatuses[*]}{.name}{" arranco "}{.state.running.startedAt}{"\n"}{end}{range .status.containerStatuses[*]}{.name}{" arranco "}{.state.running.startedAt}{"\n"}{end}'
```

**Salida real de esta máquina:**

```
pod/orden created
orden   0/2   Init:0/1   0     5s
orden   0/2   Init:0/1   0     10s
orden   0/2   Init:0/1   0     15s
orden   2/2   Running   0     20s
orden   2/2   Running   0     25s
04:36:52 app: arranco
pulso v1 desde orden
proxy arranco 2026-09-26T04:36:36Z
app arranco 2026-09-26T04:36:52Z
```

**Unos 15 segundos entre uno y otro** (16 en esta ejecución: la `startupProbe` pregunta cada 2 segundos). El kubelet no arrancó `app` hasta que la
`startupProbe` del sidecar pasó. Si `proxy` hubiera estado en `containers:`, los dos habrían
arrancado a la vez (la posición en esa lista **no ordena nada**) y la primera petición de
`app` habría fallado.

> Un init container **normal** no admite probes. Un **sidecar** sí admite `startupProbe`,
> `readinessProbe` y `livenessProbe`. Compruébalo con `kubectl explain
> pod.spec.initContainers.startupProbe`.

```bash
kubectl delete pod orden --now
```

---

## Paso 7: Recursos, QoS y `OOMKilled` (7 min)

```bash
cat > glotona.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: glotona
spec:
  containers:
  - name: app
    image: pulso:1.0
    resources:
      requests: { memory: 32Mi, cpu: 50m }
      limits:   { memory: 64Mi, cpu: 200m }
EOF

kubectl apply -f glotona.yaml
kubectl wait --for=condition=Ready pod/glotona --timeout=60s
kubectl get pod glotona -o jsonpath='QoS: {.status.qosClass}{"\n"}'
```

**Salida real de esta máquina:**

```
pod/glotona created
pod/glotona condition met
QoS: Burstable
```

`Burstable`: tiene `requests` y `limits`, pero no son iguales. 🔮 **Predice:** el límite es
64 MiB. Le pides 20 MiB y luego 100 MiB más. ¿Qué pasa con la segunda petición?

```bash
IP=$(kubectl get pod glotona -o jsonpath='{.status.podIP}')
kubectl exec cliente -- wget -qO- -T 5 "http://$IP:8080/admin/comer?mb=20"
kubectl exec cliente -- wget -qO- -T 5 "http://$IP:8080/admin/comer?mb=100"
sleep 3
kubectl get pod glotona
kubectl describe pod glotona | grep -A3 'Last State'
```

**Salida real de esta máquina:**

```
reservadas 20 MiB
wget: error getting response
command terminated with exit code 1
NAME      READY   STATUS    RESTARTS     AGE
glotona   1/1     Running   1 (4s ago)   4s
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Fri, 25 Sep 2026 23:37:04 -0500
```

**`OOMKilled`, `Exit Code: 137`.** 137 es 128 + 9: la señal 9 es `SIGKILL`, y no la mandó
el kubelet con cortesía, la mandó **el kernel** al pasar el límite del cgroup. Compara con
el Paso 4.4: el código 2 era un apagado pedido; el 137 es una ejecución sumaria. La CPU, en
cambio, **nunca mata**: por encima del límite, se estrangula.

```bash
kubectl delete pod glotona --now
```

---

## Paso 8: Reto estilo examen (20 min)

**Este paso es un laboratorio estilo examen.** No hay comandos: hay un objetivo, un sistema
roto y un script que califica **el estado final**, no lo que tecleaste. Si te atascas, es
el punto, no un error del laboratorio. La solución está al final del documento.

El sistema se instala desde un bloque codificado en base64. **Es una venda de cortesía, no un
secreto**: sirve para que diagnostiques en lugar de leer las fallas en el YAML. Podrías
decodificarlo; no lo hagas.

```bash
cd ~/lab-ckad-1
echo 'YXBpVmVyc2lvbjogdjEKa2luZDogTmFtZXNwYWNlCm1ldGFkYXRhOgogIG5hbWU6IHJldG8xCi0tLQphcGlWZXJzaW9uOiBhcHBzL3YxCmtpbmQ6IERlcGxveW1lbnQKbWV0YWRhdGE6CiAgbmFtZTogdGllbmRhCiAgbmFtZXNwYWNlOiByZXRvMQpzcGVjOgogIHJlcGxpY2FzOiAyCiAgc2VsZWN0b3I6CiAgICBtYXRjaExhYmVsczogeyBhcHA6IHRpZW5kYSB9CiAgdGVtcGxhdGU6CiAgICBtZXRhZGF0YToKICAgICAgbGFiZWxzOiB7IGFwcDogdGllbmRhIH0KICAgIHNwZWM6CiAgICAgIGNvbnRhaW5lcnM6CiAgICAgIC0gbmFtZTogYXBwCiAgICAgICAgaW1hZ2U6IHB1bHNvOjEuMAogICAgICAgIGVudjoKICAgICAgICAtIHsgbmFtZTogU1RBUlRVUF9TRUNPTkRTLCB2YWx1ZTogIjQwIiB9CiAgICAgICAgLSB7IG5hbWU6IFZFUlNJT04sIHZhbHVlOiAidGllbmRhIiB9CiAgICAgICAgcG9ydHM6IFt7IGNvbnRhaW5lclBvcnQ6IDgwODAgfV0KICAgICAgICByZWFkaW5lc3NQcm9iZToKICAgICAgICAgIGh0dHBHZXQ6IHsgcGF0aDogL3JlYWR5eiwgcG9ydDogODA4MSB9CiAgICAgICAgICBwZXJpb2RTZWNvbmRzOiA1CiAgICAgICAgbGl2ZW5lc3NQcm9iZToKICAgICAgICAgIGh0dHBHZXQ6IHsgcGF0aDogL2hlYWx0aHosIHBvcnQ6IDgwODAgfQogICAgICAgICAgcGVyaW9kU2Vjb25kczogNQogICAgICAgICAgZmFpbHVyZVRocmVzaG9sZDogMwotLS0KYXBpVmVyc2lvbjogdjEKa2luZDogU2VydmljZQptZXRhZGF0YToKICBuYW1lOiB0aWVuZGEKICBuYW1lc3BhY2U6IHJldG8xCnNwZWM6CiAgc2VsZWN0b3I6IHsgYXBwOiB0aWVuZGFzIH0KICBwb3J0czogW3sgcG9ydDogODAsIHRhcmdldFBvcnQ6IDgwODAgfV0K' | base64 -d | kubectl apply -f -
```

Y el verificador:

```bash
cat > verificar-reto1.sh <<'EOF'
#!/usr/bin/env bash
# Verificador del Reto 1: califica el ESTADO FINAL, no los comandos que usaste.
NS=reto1; OK=0; TOTAL=0
chequeo() {  # $1 = descripcion, $2 = comando que sale con 0 si el mundo esta bien
  TOTAL=$((TOTAL+1))
  if bash -c "$2" >/dev/null 2>&1; then echo "  [OK]    $1"; OK=$((OK+1)); else echo "  [FALLA] $1"; fi
}
C='kubectl -n reto1 get deploy tienda -o jsonpath'
chequeo "El Deployment tienda tiene 2 replicas listas" \
  "[ \"\$($C='{.status.readyReplicas}')\" = 2 ] && [ \"\$($C='{.spec.replicas}')\" = 2 ]"
chequeo "Las 2 replicas listas no se han reiniciado ni una vez" \
  "r=\$(kubectl -n $NS get pods -l app=tienda -o jsonpath='{.items[*].status.containerStatuses[?(@.ready==true)].restartCount}'); [ \$(echo \$r | wc -w) -ge 2 ] && [ -z \"\$(echo \$r | tr -d ' 0')\" ]"
chequeo "La livenessProbe sigue ahi, en /healthz (no vale borrarla)" \
  "[ \"\$($C='{.spec.template.spec.containers[0].livenessProbe.httpGet.path}')\" = /healthz ]"
chequeo "La app sigue tardando 40 s en arrancar (no vale acortar STARTUP_SECONDS)" \
  "[ \"\$($C='{.spec.template.spec.containers[0].env[?(@.name==\"STARTUP_SECONDS\")].value}')\" = 40 ]"
chequeo "Hay una startupProbe que concede al menos 45 s" \
  "p=\$($C='{.spec.template.spec.containers[0].startupProbe.periodSeconds}'); f=\$($C='{.spec.template.spec.containers[0].startupProbe.failureThreshold}'); [ \$(( \${p:-10} * \${f:-3} )) -ge 45 ] && [ -n \"\$($C='{.spec.template.spec.containers[0].startupProbe}')\" ]"
chequeo "La readinessProbe pregunta a /readyz en el puerto correcto" \
  "[ \"\$($C='{.spec.template.spec.containers[0].readinessProbe.httpGet.path}')\" = /readyz ] && [ \"\$($C='{.spec.template.spec.containers[0].readinessProbe.httpGet.port}')\" = 8080 ]"
chequeo "El Service tienda tiene 2 endpoints listos" \
  "[ \"\$(kubectl -n $NS get endpointslices -l kubernetes.io/service-name=tienda -o jsonpath='{.items[*].endpoints[?(@.conditions.ready==true)].addresses[0]}' | wc -w)\" = 2 ]"
chequeo "El Service responde de verdad a traves del apiserver" \
  "kubectl get --raw /api/v1/namespaces/$NS/services/tienda:80/proxy/ | grep -q 'pulso tienda'"
echo "Resultado: $OK/$TOTAL"
[ "$OK" = "$TOTAL" ]
EOF
chmod +x verificar-reto1.sh
```

### El objetivo

En el namespace `reto1` vive `tienda`: un Deployment de 2 réplicas y su Service. La app
**tarda 40 segundos en arrancar**, y eso es un requisito del negocio, no un defecto. Tu
misión:

1. Que las 2 réplicas lleguen a `Ready` y **se queden así sin reiniciarse**.
2. Que el Service `tienda` entregue tráfico a las dos.
3. Que la app siga protegida: **la `livenessProbe` en `/healthz` debe seguir existiendo** y
   la `readinessProbe` debe preguntar a `/readyz`.

**Trampas que el verificador detecta y castiga:** borrar la `livenessProbe`, borrar la
`readinessProbe`, o bajar `STARTUP_SECONDS`. Las tres hacen desaparecer el síntoma y dejan
la app peor que antes. Eso no es arreglar.

Cuando creas que terminaste:

```bash
./verificar-reto1.sh
```

**Salida real de esta máquina**, justo después de instalar el reto (sin arreglar nada):

```
  [FALLA] El Deployment tienda tiene 2 replicas listas
  [FALLA] Las 2 replicas listas no se han reiniciado ni una vez
  [OK]    La livenessProbe sigue ahi, en /healthz (no vale borrarla)
  [OK]    La app sigue tardando 40 s en arrancar (no vale acortar STARTUP_SECONDS)
  [FALLA] Hay una startupProbe que concede al menos 45 s
  [FALLA] La readinessProbe pregunta a /readyz en el puerto correcto
  [FALLA] El Service tienda tiene 2 endpoints listos
  [FALLA] El Service responde de verdad a traves del apiserver
Resultado: 2/8
```

El objetivo es `Resultado: 8/8`. Espera a que el rollout termine antes de verificar.
Método sugerido, el mismo de las diapositivas: **el estado del Pod ya nombra la causa**.
`get`, luego `describe` y sus eventos, luego los EndpointSlices.

---

## Limpieza (3 min)

```bash
kind delete cluster --name ckad
docker ps -a --filter "label=io.x-k8s.kind.cluster=ckad" --format '{{.Names}}'
docker rmi pulso:gordo pulso:latest
```

`docker ps -a` no debe listar nada. Conserva `pulso:1.0` y la carpeta `~/lab-ckad-1`: el
Laboratorio 2 vuelve a usar `pulso`.

---

## Síntesis: qué hiciste y qué demostraste

| Lo que hiciste | Lo que demuestra |
|---|---|
| 448 MB y 18 553 archivos frente a 14,6 MB y 1 403 | Multi-stage + distroless: viaja el binario, no el taller |
| `exec: "sh": executable file not found` | No es un Pod roto, es una imagen bien construida |
| `sin-tag` en `ErrImagePull` con la imagen en el nodo | Sin etiqueta = `:latest` = `imagePullPolicy: Always` |
| `ps` dentro del efímero: `/pulso` como PID 1, UID 65532 | `--target` comparte el namespace de procesos |
| `ls /config/` en la copia: `aplicacion.conf` | `--copy-to` para Pods que mueren antes de que llegues |
| `chroot /host crictl ps` | `debug node/` llega donde `kubectl` no llega |
| `RESTARTS` subiendo cada 15 s en `lento-sin-startup` | Liveness sin startup mata a una app lenta para siempre |
| `READY 1/1` respondiendo 503 | Sin readiness, «existe» equivale a «listo» |
| `0/1`, `RESTARTS 0`, 0 de 30 peticiones | Readiness saca del tráfico sin reiniciar |
| `ready=false` con la IP todavía en el slice | El tráfico lo decide la condición, no la presencia |
| `context deadline exceeded` y `logs --previous` | Un deadlock es un silencio, y el muerto recuerda por qué |
| `Init:0/2` → `Init:1/2` → `Running` | Los init containers corren en secuencia |
| Job clásico eterno, Job nativo `Complete` | `restartPolicy: Always` en un init container es un sidecar |
| 40 s frente a 10 s | Un PID 1 sin manejador de `SIGTERM` cuesta el periodo de gracia |
| 15 s entre `proxy` y `app` | El sidecar con `startupProbe` ordena el arranque |
| `OOMKilled`, `137` frente a `2` | El kernel mata por memoria; el kubelet pide por probe |

---

## Recupera sin mirar (5 min, en clase o en casa)

Responde en `predicciones.md`, **sin volver a leer el laboratorio**. Recordar cuesta más que
releer, y por eso fija más (efecto de práctica de recuperación, Roediger y Karpicke, 2006).

1. Escribe de memoria el fragmento YAML de un sidecar nativo: los tres campos que lo hacen
   ser un sidecar.
2. ¿Qué dos columnas de `kubectl get pods` distinguen un fallo de liveness de uno de
   readiness?
3. Una app necesita hasta 3 minutos para arrancar. Escribe una `startupProbe` que lo
   permita con `periodSeconds: 10`.
4. ¿Qué comando usarías para ver los procesos de un Pod distroless, y qué bandera no puede
   faltar?
5. `Exit Code: 137`. ¿Quién mató el proceso y por qué?

---

## Cómo conecta con el resto del curso

- **Módulo 3:** allí construiste imágenes con Dockerfile. Aquí la imagen tiene una
  consecuencia operativa: sin shell, la depuración cambia de herramienta.
- **Módulo 5:** el `logs --previous` del Paso 7 de CKA vuelve aquí, y ahora sabes cuándo
  funciona y cuándo no.
- **Laboratorio 2 de este módulo:** la misma `pulso` se despliega con blue/green y canary,
  se configura con ConfigMaps y Secrets, se protege con NetworkPolicies y se expone con
  Ingress y Gateway API.
- **Módulo 7 (CKS):** `nonroot`, distroless y los perfiles de `kubectl debug` son la base de
  la seguridad de la carga de trabajo.

---

## Para profundizar

- Contenedores sidecar: <https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/>
- Init containers: <https://kubernetes.io/docs/concepts/workloads/pods/init-containers/>
- Configurar liveness, readiness y startup probes: <https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/>
- Depurar Pods en ejecución (contenedores efímeros): <https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/>
- Contenedores efímeros: <https://kubernetes.io/docs/concepts/workloads/pods/ephemeral-containers/>
- `kubectl` v1.36, cambio del perfil por defecto de `kubectl debug`: <https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-1.36.md>
- Imágenes y `imagePullPolicy`: <https://kubernetes.io/docs/concepts/containers/images/>
- Downward API: <https://kubernetes.io/docs/concepts/workloads/pods/downward-api/>
- Clases de QoS: <https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/>
- Distroless: <https://github.com/GoogleContainerTools/distroless>
- `pid_namespaces(7)`, señales al proceso init: <https://man7.org/linux/man-pages/man7/pid_namespaces.7.html>
- Currículo CKAD v1.35: <https://github.com/cncf/curriculum>

**Pedagogía usada en este laboratorio:**

- Sentance, S., Waite, J. y Kallia, M. (2019). *Teaching computer programming with PRIMM: a
  sociocultural perspective*. Computer Science Education, 29(2-3), 136–176.
- White, R. y Gunstone, R. (1992). *Probing Understanding*. Falmer Press (Predict-Observe-Explain).
- Kapur, M. (2008). *Productive Failure*. Cognition and Instruction, 26(3), 379–424.
- Kalyuga, S., Ayres, P., Chandler, P. y Sweller, J. (2003). *The Expertise Reversal Effect*.
  Educational Psychologist, 38(1), 23–31.
- Jonassen, D. H. y Hung, W. (2006). *Learning to Troubleshoot: A New Theory-Based Design
  Architecture*. Educational Psychology Review, 18(1), 77–114 (base del reto con fallas ocultas).
- Roediger, H. L. y Karpicke, J. D. (2006). *Test-Enhanced Learning*. Psychological Science,
  17(3), 249–255.

---

## Solución del reto (no la leas antes de intentarlo)

<details>
<summary>Mostrar la solución</summary>

El sistema tenía **tres** fallas, y aparecen en orden: cada una esconde a la siguiente.

**1. La app nunca termina de arrancar.** `RESTARTS` sube cada 15 segundos y los eventos
dicen `Liveness probe failed: ... statuscode: 503`. Es el Paso 4.1: 40 segundos de arranque
contra una liveness que mata a los 15. **No** se arregla borrando la liveness ni bajando
`STARTUP_SECONDS`: se añade una `startupProbe`.

**2. Aun arrancada, nunca está `Ready`.** Los eventos dicen `Readiness probe failed: ...
connect: connection refused`: la `readinessProbe` pregunta al puerto **8081**, y la app
escucha en el 8080.

**3. Con las dos réplicas `Ready`, el Service sigue sin endpoints.** El selector del Service
es `app: tiendas`, con una ese de más.

```bash
kubectl -n reto1 patch service tienda -p '{"spec":{"selector":{"app":"tienda"}}}'
kubectl -n reto1 patch deployment tienda --type=json -p '[
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/port","value":8080},
  {"op":"add","path":"/spec/template/spec/containers/0/startupProbe",
   "value":{"httpGet":{"path":"/startupz","port":8080},"periodSeconds":5,"failureThreshold":12}}
]'
kubectl -n reto1 rollout status deployment/tienda --timeout=180s
sleep 20
./verificar-reto1.sh
```

**Salida real de esta máquina:**

```
  [OK]    El Deployment tienda tiene 2 replicas listas
  [OK]    Las 2 replicas listas no se han reiniciado ni una vez
  [OK]    La livenessProbe sigue ahi, en /healthz (no vale borrarla)
  [OK]    La app sigue tardando 40 s en arrancar (no vale acortar STARTUP_SECONDS)
  [OK]    Hay una startupProbe que concede al menos 45 s
  [OK]    La readinessProbe pregunta a /readyz en el puerto correcto
  [OK]    El Service tienda tiene 2 endpoints listos
  [OK]    El Service responde de verdad a traves del apiserver
Resultado: 8/8
```

Y la prueba de que el verificador no se deja engañar. Con el Service arreglado, pero
«resolviendo» lo demás a la brava (borrar las dos probes y poner `STARTUP_SECONDS=0`), las
réplicas quedan `Ready` y el Service responde. Aun así:

```
  [OK]    El Deployment tienda tiene 2 replicas listas
  [OK]    Las 2 replicas listas no se han reiniciado ni una vez
  [FALLA] La livenessProbe sigue ahi, en /healthz (no vale borrarla)
  [FALLA] La app sigue tardando 40 s en arrancar (no vale acortar STARTUP_SECONDS)
  [FALLA] Hay una startupProbe que concede al menos 45 s
  [FALLA] La readinessProbe pregunta a /readyz en el puerto correcto
  [OK]    El Service tienda tiene 2 endpoints listos
  [OK]    El Service responde de verdad a traves del apiserver
Resultado: 4/8
```

El síntoma desapareció y la calificación no subió. **Arreglar es devolver el sistema a su
contrato, no callar la alarma.**

</details>

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
