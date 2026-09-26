# Módulo 5 — Certified Kubernetes Administrator (CKA)

**Sesiones 6 y 7 · sábados 5 y 12 de septiembre de 2026 · 9:00–12:00**

El pivote técnico del semestre. Aquí dejas de usar Kubernetes y empiezas a
administrarlo: el clúster es tuyo, y cuando se rompe, lo arreglas tú.

El CKA es un examen **práctico y cronometrado**: no hay preguntas de opción múltiple,
hay una terminal y problemas que resolver. Se estudia con las manos.

Certificación de referencia: **CKA**.

---

## Objetivos de aprendizaje

- Instalar un clúster desde cero con `kubeadm`: requisitos del host, `containerd`,
  `kubeadm init`, red de Pods y unión de nodos.
- Actualizar un clúster una versión menor completa, con `drain` y `uncordon`, sin perder
  las aplicaciones que corren en él.
- Respaldar y restaurar `etcd`, y entender qué se recupera y qué se pierde.
- Diagnosticar nodos, componentes del control plane y cargas de trabajo con `journalctl`,
  `crictl`, `kubectl describe` y `kubectl logs --previous`.
- Decidir dónde corre cada Pod con taints, tolerations y afinidad de nodo.
- Gestionar almacenamiento: StorageClass, PVC, PV y aprovisionamiento dinámico.
- Distinguir Deployment de StatefulSet, y saber cuándo hace falta cada uno.
- Auditar y construir RBAC: `Role`, `ClusterRole`, `RoleBinding`, `ClusterRoleBinding`,
  ServiceAccounts y usuarios con certificado.
- Exponer aplicaciones: `NodePort`, `port-forward`, Ingress y Gateway API.

---

## Dominios del examen CKA

| Dominio | Peso |
|---|---|
| Troubleshooting | 30% |
| Arquitectura, instalación y configuración del clúster | 25% |
| Servicios y redes | 20% |
| Cargas de trabajo y scheduling | 15% |
| Almacenamiento | 10% |

Casi un tercio del examen es diagnosticar cosas rotas. Estudia en ese orden.

> Verifica los pesos vigentes en la página oficial del examen CKA de la CNCF antes de
> presentarlo.

---

## Laboratorios

El módulo tiene **dos laboratorios**, uno por sesión. El segundo asume el primero.

### Sesión 6 — [Laboratorio 1: El clúster es tuyo](./laboratorio-cka-1.md)

**En clase, 95–110 minutos, 8 pasos.** Se hace sobre **dos máquinas virtuales de LXD** que
tú creas y borras en la misma sesión. Es la primera vez en el curso que Kubernetes no viene
hecho.

| Paso | Contenido | Tiempo |
|---|---|---|
| 0 | El sustrato: red y perfil de LXD, dos VMs Ubuntu 24.04 | ~12 min |
| 1 | Los requisitos que `kubeadm` comprueba (`product_uuid`, swap, `nproc`), y `containerd` con `SystemdCgroup` | ~12 min |
| 2 | Instalar `kubeadm`, `kubelet` y `kubectl` desde `pkgs.k8s.io`, y `apt-mark hold` | ~10 min |
| 3 | `kubeadm init`, nodo `NotReady`, red de Pods con Flannel **y el fallo real de `br_netfilter`** | ~18 min |
| 4 | `kubeadm join`, primer Deployment, Service y el taint del control plane | ~10 min |
| 5 | Static pods, el kubelet bajo `systemd`, `journalctl` y `crictl` | ~12 min |
| 6 | Actualizar el clúster de **v1.36.4 a v1.37.0**: `plan`, `apply`, `drain`, `upgrade node` | ~20 min |
| 7 | Respaldar y **restaurar** `etcd`, y el *mirror pod* que queda desincronizado | ~15 min |

El Paso 3 es el corazón pedagógico: la documentación oficial pide **un** `sysctl`, el CNI
falla igual, y el estudiante encuentra la causa **leyendo el log del contenedor**, no
buscando en un blog. El Paso 7 demuestra que restaurar `etcd` no es «recuperar lo borrado»:
es viajar al instante del snapshot, y todo lo posterior se pierde.

**Anexo opcional (para casa):** caducidad de tokens de unión y renovación manual de
certificados, ~20 min.

**Requisitos:** Linux con **LXD** funcionando y **6 GiB de RAM libres**.

### Sesión 7 — [Laboratorio 2: Operar el clúster](./laboratorio-cka-2.md)

**En clase, 120–140 minutos, 11 pasos.** Se hace sobre un clúster `kind` de **tres nodos**
(un control plane y dos workers) que tú creas y borras en la sesión.

| Paso | Contenido | Tiempo |
|---|---|---|
| 0 | Un clúster `kind` de 3 nodos con `extraPortMappings` | ~8 min |
| 1 | Taints, tolerations y afinidad: desplegar **dentro y fuera** del control plane | ~15 min |
| 2 | PV, PVC, StorageClass y `WaitForFirstConsumer` | ~15 min |
| 3 | **Deployment frente a StatefulSet**: `volumeClaimTemplates`, identidad y DNS por réplica | ~15 min |
| 4 | Actualizar y **revertir** un Deployment, incluido un despliegue roto a propósito | ~15 min |
| 5 | **NodePort frente a `kubectl port-forward`**: qué sobrevive y qué no | ~12 min |
| 6 | `metrics-server`, `kubectl top nodes/pods` y escalado automático con HPA | ~15 min |
| 7 | Diagnosticar un `CrashLoopBackOff` en cuatro capas | ~8 min |
| 8 | **RBAC**: ServiceAccount, usuario `ana` con certificado (CSR), `Role`/`RoleBinding`/`ClusterRole`/`ClusterRoleBinding` | ~20 min |
| 9 | **Ingress frente a Gateway API**: dos sitios web reales servidos por los dos | ~20 min |
| 10 | Observabilidad: `helm install kube-prometheus-stack` y el clúster entero en Grafana | ~12 min |

Tres momentos que valen la sesión entera: el mensaje `FailedScheduling` del Paso 1, que
distingue «taint no tolerado» de «no cumple la afinidad»; la trampa del Paso 8, donde
`--token` sobre el kubeconfig de administrador **no** cambia de identidad y `auth whoami` lo
demuestra; y el Paso 9, donde el controlador de Ingress aterriza en el nodo equivocado y el
estudiante lo arregla con lo que aprendió en el Paso 1.

**Anexo opcional (para casa):** cambiar de CNI, ~35 min. Se crean dos clústeres más y se
compara **kindnet, Calico y Cilium** midiendo, no citando: si aplican NetworkPolicy (los
tres sí, en contra de lo que dicen muchos blogs), cuántas CRDs añade cada uno, cómo se ven
las rutas en el kernel, y un clúster **sin `kube-proxy`** donde los Services funcionan con
**0 reglas de iptables** porque el balanceo vive en eBPF.

**Requisitos:** Linux con Docker Engine activo, `kind`, `kubectl` y `helm`. **6 GiB de RAM
libres** (8 GiB con el Paso 10, 10 GiB con el anexo).

---

## Trabajo de proyecto final — de tu PRD a las unidades con sus tareas

Además de los dos laboratorios de CKA, este módulo lleva el **tercer paso del proyecto
final**: convertir el `pvb.md` del módulo 2 y el `prd.md` del módulo 3 en la especificación
ejecutable del producto, usando el marco **AI-DLC de AWS**.

**Guía paso a paso:**
[`proyecto-final-de-prd-a-unidades-y-tareas.md`](./proyecto-final-de-prd-a-unidades-y-tareas.md)

| Qué produces | Con qué etapa de AI-DLC |
|---|---|
| Requisitos trazables desde el PRD | Requirements Analysis |
| Historias y personas con criterios verificables | User Stories |
| Qué etapas se ejecutan y con qué profundidad | Workflow Planning |
| Componentes, métodos, servicios y dependencias | Application Design |
| **Las unidades de trabajo y sus dependencias** | Units Generation |
| **Las tareas numeradas de cada unidad** | Code Generation, **Parte 1** |

**No hace falta cuenta de AWS ni instalar nada, y sirve con el agente de código que ya
uses.** Se usa la versión **v1.0.1** del marco, que son archivos Markdown que copias al
proyecto: su README oficial dice que funciona con cualquier agente que lea reglas de
proyecto. La línea nueva (v2.8.x) queda explicada en un apéndice de la guía, con sus
ventajas y sus ataduras.

**El overlay optimizado viene incluido.** El marco estándar carga 539 líneas de reglas en
cada turno y el modelo empieza a saltarse compuertas cuando el contexto se llena.
[`aidlc-optimizado/`](./aidlc-optimizado/) lo resuelve con despacho por fase: el archivo
siempre cargado baja a 134 líneas y cada fase carga su orquestación solo cuando le toca.
Es puramente aditivo, no modifica ninguna regla del ZIP oficial.

**Y hay un ejemplo de referencia completo.** [`ejemplo-timonel/`](./ejemplo-timonel/) continúa
el caso de estudio del módulo 3 un paso más allá: las 10 unidades de Timonel con lo que cada
una **no** hace, el grafo de dependencias verificado acíclico, el mapa de 36 historias con
criterios verificables, el plan de tareas de la unidad que impone el límite de autonomía, y el
archivo consolidado que es el formato del entregable. Es la vara de calidad, no una plantilla.

**Te detienes en la aprobación del plan de tareas, sin escribir una línea de código.** La
codificación se hace en los módulos siguientes con un loop de tres agentes (orquestador,
codificador y revisor), y ese loop necesita un plan de tareas aprobado para poder funcionar:
sin tareas verificables no hay nada que orquestar ni nada que revisar.

La regla del curso es la misma de siempre, aplicada a la especificación: **el agente
propone, tú apruebas**. El registro de auditoría de AI-DLC queda como evidencia de qué
leíste, qué cambios pediste y qué aprobaste.

---

## Herramientas y conceptos del módulo

`kubeadm`, `kubelet`, `kubectl`, `containerd`/CRI, `crictl`, LXD, `kind`, `etcdctl` y
`etcdutl`, Helm, `metrics-server`, Prometheus y Grafana, Flannel, Calico, Cilium, kindnet,
Ingress NGINX, Gateway API y NGINX Gateway Fabric, `openssl` y la API de CSR.

---

## Cómo preparar el examen

- **Practica contra reloj.** El CKA se pierde por tiempo, no por desconocimiento.
- **Domina `kubectl explain` y la documentación oficial**, que sí puedes consultar
  durante el examen. Saber buscar rápido vale más que memorizar campos.
- **Aliases y `--dry-run=client -o yaml`.** Escribir YAML a mano cuesta minutos que
  no tienes.
- **Lee los mensajes de error completos.** Los dos laboratorios están construidos alrededor
  de esa idea: `FailedScheduling`, `WaitForFirstConsumer`, `Failed to check br_netfilter`,
  `doesn't contain any IP SANs` y `Forbidden: … at the cluster scope` **contienen la
  respuesta**. En el examen, leerlos entero es más rápido que adivinar.

---

## Cómo conecta con el resto del curso

- **Módulo 1:** el troubleshooting de nodo se hace con `systemd` y `journalctl`.
- **Módulo 3:** `crictl` te muestra los contenedores OCI que hay debajo de cada Pod.
- **Módulo 4:** allí viste el loop de reconciliación; aquí lo operas y lo depuras.
- **Módulo 6 (CKAD):** el desarrollador escribe `Deployment`, `PVC` y `HTTPRoute`; tú
  escribes `StorageClass`, `Gateway` y RBAC. El Laboratorio 2 marca esa frontera.
- **Módulo 7 (CKS):** la auditoría de RBAC que aquí es diagnóstico, allá es defensa.
- **Módulo 8:** un agente de IA que diagnostica el clúster necesita exactamente estos
  permisos de solo lectura — y entender por qué no más. Y el `helm install` manual del
  Paso 10 es lo que GitOps convierte en un commit.

---

_Creado con ❤️ por Luis Felipe Ariza Vesga._
