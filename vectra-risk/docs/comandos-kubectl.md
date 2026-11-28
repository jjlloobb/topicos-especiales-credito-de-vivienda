# Comandos `kubectl` para mostrar el clúster

Órdenes de **solo lectura** para enseñar qué corre en `kind-vectra`: nodos, pods, servicios, tareas, rutas, modelos, bases, seguridad y estado de GitOps. Ninguna cambia nada en el clúster. Todas se ejecutaron contra `kind-vectra` el 27 de noviembre de 2026 y respondieron sin error.

Diagramas relacionados: [clúster](diagrama-cluster.md) e [infraestructura](diagrama-infraestructura.md).

## Antes de empezar

Todas las órdenes llevan el contexto del clúster. Para no repetirlo, define un alias en la terminal:

```bash
alias k='kubectl --context kind-vectra'
```

El resto del documento usa `k`. Si prefieres no usar el alias, sustituye `k` por `kubectl --context kind-vectra`.

> **No muestres secretos.** No ejecutes `k get secret … -o yaml` ni `-o json` en pantalla: imprimen el contenido. Para enseñar que los secretos existen y están sincronizados, usa `k get externalsecrets -A` (más abajo).

## 1. El clúster de un vistazo

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Los nodos | `k get nodes -o wide` | 3 nodos `Ready`, Kubernetes v1.37.0 |
| Los namespaces | `k get namespaces` | 24, entre ellos los ocho `vectra-*` |
| Uso de CPU y memoria por nodo | `k top nodes` | Uso actual de cada nodo |
| Todos los tipos de recurso | `k api-resources --namespaced=true` | La lista de lo que el clúster sabe manejar |

## 2. Pods

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Todos los pods | `k get pods -A` | 93 `Running`, más los `Completed` de las tareas |
| Los de la aplicación | `k get pods -n vectra-app -o wide` | Dos réplicas de cada servicio, con su nodo y su IP |
| Solo los que no están bien | `k get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded` | Vacío, o tareas en `Error` tras un reinicio |
| Los de un servicio | `k get pods -n vectra-app -l app.kubernetes.io/name=case-service` | Los pods de `case-service` |
| Consumo por pod | `k top pods -n vectra-app --sort-by=memory` | Memoria y CPU de cada pod, de mayor a menor |
| El detalle de un despliegue | `k describe deploy case-service -n vectra-app` | Imagen por digest, réplicas, sondas y límites |
| Los últimos registros | `k logs -n vectra-app deploy/case-service -c case-service --tail=20` | Líneas JSON del servicio |

Cada pod de la aplicación dice `2/2`: un contenedor es el servicio y el otro, el proxy de la malla (Linkerd).

## 3. Servicios y despliegues

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Los `Service` de la aplicación | `k get svc -n vectra-app` | Nueve, de tipo `ClusterIP`, con los puertos 8080 y 8081 |
| El único expuesto hacia fuera | `k get svc -A --field-selector spec.type=LoadBalancer` | `api-gateway`, con la dirección externa del gateway |
| Despliegues y conjuntos con estado | `k get deploy,statefulset -n vectra-app` | Nueve `Deployment` en `2/2` |
| Todo lo de un namespace | `k get all -n vectra-edge` | Pods, servicios, despliegues y réplicas del borde |
| Si un despliegue terminó de actualizarse | `k rollout status deploy/case-service -n vectra-app` | `successfully rolled out` |
| Autoescaladores | `k get hpa -A` | Mínimo y máximo iguales: en kind no hay memoria para escalar |
| Presupuestos de interrupción | `k get pdb -A` | Cuántas réplicas pueden caer a la vez |

## 4. Tareas: `Job` y `CronJob`

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Tareas programadas | `k get cronjobs -A` | Seis, con su horario y su última corrida |
| Tareas de una vez y corridas recientes | `k get jobs -A` | Migraciones, `keycloak-config-cli` y las corridas de cada `CronJob` |
| Las corridas del monitoreo de sesgo | `k get jobs -n vectra-app -l app.kubernetes.io/name=bias-monitoring-job` | Una cada 15 minutos |

Tras reiniciar la máquina es normal ver alguna corrida en `Failed`: cayó con el clúster abajo y la siguiente pasa.

## 5. Entrada al clúster: gateway y rutas

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| El gateway y sus rutas | `k get gateway,httproute -n vectra-edge` | `api-gateway` programado y siete `HTTPRoute` |
| A dónde lleva una ruta | `k describe httproute intake -n vectra-edge` | La ruta de ingreso de solicitudes, hacia `case-service` |

## 6. Modelo y datos

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Las versiones del modelo | `k get inferenceservices -n vectra-serving` | Dos `InferenceService`, ambos listos |
| Sus pods | `k get pods -n vectra-serving` | Predictor y explicador de cada versión |
| Las bases PostgreSQL | `k get clusters.postgresql.cnpg.io -n vectra-data` | Cuatro, «Cluster in healthy state» |
| Los volúmenes | `k get pvc -A` | 17 volúmenes enlazados |

## 7. Seguridad

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Lo que puede hacer la cuenta de los agentes | `k auth can-i --list --as=system:serviceaccount:argocd:vectra-readonly-agent` | Solo `get`, `list` y `watch` |
| Que no puede crear pods | `k auth can-i create pods -n vectra-app --as=system:serviceaccount:argocd:vectra-readonly-agent` | `no` |
| Que no puede leer secretos | `k auth can-i get secrets -n vectra-app --as=system:serviceaccount:argocd:vectra-readonly-agent` | `no` |
| Namespaces con Pod Security restringido | `k get ns -l pod-security.kubernetes.io/enforce=restricted` | Los namespaces `vectra-*` |
| Políticas de admisión | `k get clusterpolicy` | Las políticas de Kyverno, todas `READY` |
| Políticas de red | `k get networkpolicy -n vectra-app` | Una por flujo permitido, más la de DNS |
| Autorización de la malla | `k get servers.policy.linkerd.io,authorizationpolicies.policy.linkerd.io -n vectra-app` | Un `Server` por puerto y una política por flujo |
| Secretos sincronizados desde la bóveda | `k get externalsecrets -A` | 71, todos `SecretSynced` |

Las dos órdenes que responden `no` terminan con código de salida 1: es lo esperado, no un error.

## 8. GitOps y observabilidad

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Las aplicaciones de Argo CD | `k get applications -n argocd` | 56; todas `Synced` y `Healthy`, salvo `kserve-crd` y `linkerd-control-plane`, que están `OutOfSync` y sanas |
| Que ninguna se sincroniza sola | `k get applications -n argocd -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.syncPolicy.automated}{"\n"}{end}'` | La segunda columna vacía en todas |
| Qué vigila Prometheus | `k get servicemonitors,prometheusrules -A` | Los monitores y las reglas de alerta |
| Los tableros de Grafana | `k get cm -n vectra-observability -l vectra.io/dashboard=1` | Seis `ConfigMap`, uno por tablero de plataforma |

## 9. Qué pasó hace poco

| Qué muestra | Orden | Qué esperar |
|---|---|---|
| Eventos recientes de la aplicación | `k get events -n vectra-app --sort-by=.lastTimestamp` | Lo último que ocurrió, al final de la lista |
| Solo las advertencias | `k get events -A --field-selector type=Warning --sort-by=.lastTimestamp` | Fallos de sondas, reinicios, tareas que cayeron |

## Una secuencia de dos minutos para la sustentación

```bash
k get nodes                                   # 1. tres nodos
k get pods -n vectra-app                      # 2. nueve servicios, dos réplicas cada uno
k get svc -A --field-selector spec.type=LoadBalancer   # 3. una sola puerta de entrada
k get cronjobs -A                             # 4. las tareas programadas
k get inferenceservices -n vectra-serving     # 5. el modelo activo y el de respaldo
k get applications -n argocd | head -15       # 6. todo llega por Argo CD
k auth can-i --list --as=system:serviceaccount:argocd:vectra-readonly-agent | head -14   # 7. el agente solo lee
k auth can-i get secrets -n vectra-app --as=system:serviceaccount:argocd:vectra-readonly-agent   # 8. «no»
```

## Qué no está aquí, a propósito

- **Órdenes que escriben** (`apply`, `delete`, `patch`, `scale`, `rollout restart`): en este proyecto los cambios llegan por un pull request y un sync de Argo CD, no por `kubectl`. Las de recuperación tras un reinicio están en `platform/runbooks/install.md`.
- **Lectura de secretos:** ver la advertencia del principio.
- **Los números de la columna «Qué esperar»** son los del 27 de noviembre de 2026 en kind; cambian si se despliega algo más.
