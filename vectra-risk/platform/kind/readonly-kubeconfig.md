# Un kubeconfig de solo lectura para los agentes del loop (U01-T17)

El `kubectl` de cualquier proceso usa `~/.kube/config`, y su contexto `kind-vectra` es de administrador. «Los agentes no tocan el clúster» era solo una instrucción en los despachos, y el 2026-11-16 falló dos veces: dos pruebas leyeron los `Secret` del clúster real (PR #195) y una prueba ejecutó con `bash` una guía que borró cuatro Deployments (`kubectl --context kind-vectra delete -f ...`). Esta identidad hace que un proceso lanzado por un agente **no pueda escribir en el clúster ni leer un `Secret`, aunque lo intente**, sin depender de recordar una variable en cada orden.

## Qué es

- `platform/rbac/readonly-agent/readonly-agent-kind.yaml`: la `ServiceAccount` `vectra-readonly-agent` en `argocd`, su `Secret` de token (`kubernetes.io/service-account-token`, sin valor en Git: lo llena el controlador de tokens), un `ClusterRole` y su `ClusterRoleBinding`.
- Llega al clúster con la Application `readonly-agent-rbac-kind`, solo de kind (`components.yaml`, `envs: [kind]`; `generate.py` no la emite para staging ni prod). Wave 1, la misma de `kyverno-policies`: puede sincronizar antes o después que las políticas. No importa: el `ClusterRole` no tiene comodines y `disallow-rbac-wildcards` lo admite sin excepción (caso `pass` de `kyverno-test.yaml`), y ninguna otra Application depende de esta. Namespace `argocd`: existe, no tiene cuota y `disallow-plain-secrets` solo vigila `vectra-*`.
- El `ClusterRole` lista solo `get`, `list` y `watch`, sin comodines (`disallow-rbac-wildcards`, `Enforce`, no se relaja). Cubre el núcleo, `apps`, `batch`, `autoscaling`, `policy`, `networking.k8s.io`, nodos, namespaces, `pods/log`, `metrics.k8s.io` y los recursos propios (Argo CD, ESO, CNPG, Kyverno, Gateway API, Envoy Gateway, KServe, Linkerd, Prometheus, cert-manager). **No** tiene `secrets`, `pods/exec`, `pods/portforward`, `pods/attach`, verbos de escritura, `impersonate`, `escalate` ni `bind`.
- No se reutilizó el `ClusterRole` integrado `view`: es un rol agregado cuyo contenido lo decide cualquier chart que lo etiquete, y no cubre los nodos, las `PersistentVolume`, las CRD, las métricas ni los recursos propios del proyecto, que es lo que hace falta para diagnosticar. Excluye `secrets`, pero no es una lista que el repositorio pueda fijar con una prueba.
- `configmaps` sí se leen (son del núcleo y hacen falta para diagnosticar): si algún día un ConfigMap lleva un valor sensible, es un defecto de ese ConfigMap.

## Cómo se usa

1. **El operador**, una vez y de nuevo tras recrear el clúster, con el kubeconfig de administrador (el de siempre) y la Application sincronizada:
   ```bash
   platform/kind/readonly-kubeconfig.sh write          # escribe ~/.kube/kind-vectra-readonly (0600, fuera del repositorio)
   platform/kind/readonly-kubeconfig.sh check          # lectura de vuelta: sale 0 solo si toda la tabla de `can-i` da lo esperado
   ```
   `write` usa el administrador solo para dos lecturas: `kubectl --context kind-vectra get secret vectra-readonly-agent-token -n argocd` (el token y la CA; no crea tokens) y `kubectl config view --minify` (la URL del API, de un archivo local). Nunca imprime el token. Se niega si el contexto no es `kind-*`, si la ruta cae dentro del repositorio, si es el kubeconfig de administrador (`~/.kube/config` o un archivo de `KUBECONFIG`) o si ya existe un archivo que el guion no escribió (los suyos llevan en la primera línea `# escrito por platform/kind/readonly-kubeconfig.sh ...`). Un temporal con el token no queda si algo falla.
2. **Los agentes** (codificador, revisor, y cualquier proceso que ellos lancen) corren con `KUBECONFIG=~/.kube/kind-vectra-readonly`. El archivo tiene un solo contexto, llamado `kind-vectra`: las órdenes con `--context kind-vectra` que ya llevan los guiones y las pruebas resuelven a la identidad de solo lectura, en vez de fallar o de escapar al administrador.
3. **La sesión del orquestador** usa el kubeconfig de administrador solo en las órdenes que el usuario aprueba, y lo nombra de forma explícita en cada una: `KUBECONFIG=~/.kube/config kubectl --context kind-vectra ...`.

`check` imprime la tabla (`esperado`, `obtenido`, ámbito, verbo, recurso) para `vectra-app`, `vectra-edge`, `vectra-data` y a nivel de clúster. Sí: `get pods`, `list deployments`, `get pods/log`, `list applications.argoproj.io`, `list externalsecrets.external-secrets.io` y `get nodes`. No: `get`/`list secrets`, `delete deployments|pods|*`, `create pods|deployments`, `patch`/`update deployments`, `create pods/exec|portforward|attach`, `get nodes/proxy|pods/proxy|services/proxy|nodes/log`, `create serviceaccounts/token`, `escalate` y `bind clusterroles` e `impersonate users`. Las pruebas del manifiesto prohíben además cualquier subrecurso salvo `pods/log` y comprueban que cada `(grupo, recurso)` exista (núcleo y CRD de `platform/.charts`).

## Tras reiniciar la máquina o recrear el clúster

- **Reiniciar la máquina**: el token es el de un `Secret` de larga vida; no expira ni depende de la sesión. Mientras el clúster conserve su estado (los contenedores de kind vuelven con sus volúmenes), el archivo sigue valiendo. La URL del API la fija kind al crear el clúster (`127.0.0.1:<puerto>`); si tras el reinicio el puerto cambiara, `check` falla con «sin respuesta» y `write` la reescribe. *No medido*: no se ha reiniciado una máquina con este archivo.
- **Recrear el clúster** (`kind delete cluster` y crear): el `Secret` nuevo tiene otro token y otra CA, y el archivo viejo deja de valer (`check` dará «sin respuesta» o 401). Hay que sincronizar de nuevo la Application y correr `write` otra vez.
- Para revocar la identidad sin recrear nada: borrar el `Secret` `vectra-readonly-agent-token` (con el administrador) invalida el token. Las Applications no se sincronizan solas (`disallow-argocd-auto-sync`): el `Secret` se vuelve a crear, con otro valor, solo cuando alguien sincroniza `readonly-agent-rbac-kind` a mano; mientras tanto no hay identidad de solo lectura y `write` sale 4 o 5.

## `argocd` y `docker`: lo que este kubeconfig no cubre

*Investigado sin ejecutar ninguno de los dos: no se cambió la configuración de nadie.*

- **`argocd`**: la CLI guarda la sesión (con el token de administrador tras `argocd login`) en su archivo de configuración, por omisión `~/.config/argocd/config`. Un proceso usa otra configuración, vacía, con `--config <ruta>` o con la variable `ARGOCD_CONFIG_DIR` (el directorio que la contiene); apuntada a un archivo que no existe, la CLI no tiene servidor ni token y falla en vez de actuar. Las demás variables (`ARGOCD_SERVER`, `ARGOCD_AUTH_TOKEN`, `ARGOCD_OPTS`) pueden reintroducir credenciales: un agente no debe heredarlas. El modo `--core` de la CLI no usa la sesión sino el kubeconfig del proceso, que con esta identidad solo lee. *No medido*: los nombres exactos de la variable y del indicador salen de la documentación de Argo CD y no se ejecutó la CLI para confirmarlos; confírmalos con `argocd --help` antes de fijarlos.
- **`docker`**: quien llega al demonio puede hacer `docker exec` en un nodo de kind y entonces es administrador del clúster (el nodo tiene el `admin.conf` de `kubeadm`). Un proceso no llega al demonio si `DOCKER_HOST` apunta a un socket que no existe o no escucha (`DOCKER_HOST=unix:///nonexistent`): el cliente falla con «Cannot connect to the Docker daemon».
- **Qué se rompe sin Docker**: las pruebas con Testcontainers (`pytest -m integration`) necesitan un demonio de verdad: `platform/tests/test_grafana_folder_permissions.py`, y las de `decision-registry`, `governance`, `case-management`, `identity-edge` (`tests/integration/realm_stack.py`), `bias-monitoring`, `product-metrics` y `system-verification` que levantan PostgreSQL, MinIO, Keycloak o Prometheus (`tests/integration/`, `tests/property/` y `tests/doubles/*_tc.py`), y las que hacen `docker build` o `docker run` de una imagen (`test_image.py`, `test_container_start.py`). No podrían correr con `DOCKER_HOST` anulado. Las pruebas unitarias no lo necesitan.
- **Recomendación** (decide el usuario): a los agentes, `KUBECONFIG` de solo lectura siempre; `--config`/`ARGOCD_CONFIG_DIR` a un archivo vacío en las órdenes que no necesitan `argocd`; `DOCKER_HOST` anulado salvo en las corridas de integración, que se lanzan con el demonio real y sin cluster en el entorno. Es una política de proceso: un agente que quiera Docker lo pide, no lo hereda.

## Qué NO resuelve

- Un proceso que fije él mismo `KUBECONFIG=~/.kube/config` o pase `--kubeconfig ~/.kube/config` vuelve a ser administrador.
- `docker exec` en un nodo de kind, si el proceso llega al demonio de Docker.
- La sesión de `argocd` guardada en la máquina.
- Lo que la identidad **sí lee**: la especificación de los pods y los `pods/log`, no solo los `configmaps`. Un valor puesto en una variable de entorno de un pod, o impreso en un log, es legible para los agentes. Ejemplo: el token raíz de desarrollo de Vault en kind (`root`, `platform/operators/vault-kind.yaml`) está en la spec de su pod; ya está en Git y Vault no se expone al host (sin `portforward` ni `proxy` no se llega a él), pero la regla es que ningún valor sensible va en la spec ni en un log.
- Cualquier proceso que lea `~/.kube/config` directamente (por ejemplo una biblioteca de Kubernetes que no respete `KUBECONFIG`).

La identidad de solo lectura reduce el daño de un error; no impide un acto deliberado.

## No medido (sin clúster)

Que el controlador de tokens llene el `Secret`, que Argo CD sincronice sin diferencias perpetuas por los campos que ese controlador agrega, y que `kubectl auth can-i` responda como se espera con los CRD reales: lo comprueba el orquestador con aprobación del usuario, con `write` y `check`, cuando esta tarea esté fusionada.
