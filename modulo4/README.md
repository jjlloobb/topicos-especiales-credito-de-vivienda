# Módulo 4 — Kubernetes Fundamentals (KCNA)

**Sesión 4 · sábado 22 de agosto de 2026 · 9:00–12:00**

El primer contacto serio con Kubernetes. La idea central del módulo cabe en una frase:
Kubernetes no ejecuta tu aplicación, **reconcilia** un estado deseado con el estado
real, una y otra vez, para siempre. Todo lo demás es consecuencia de eso.

Certificación de referencia: **KCNA** (Kubernetes and Cloud Native Associate).

---

## Objetivos de aprendizaje

- Comprender el loop **Watch-Diff-Update** de los controladores: el corazón del sistema.
- Entender EndpointSlices y cómo un Service llega realmente a sus pods.
- Entender los Admission Webhooks: dónde se intercepta y modifica lo que entra al clúster.
- Configurar Multi-Service CIDRs sin recrear el clúster.
- Habilitar Node Memory Swap (Kubernetes 1.29+) y entender cgroup v2.

---

## Agenda

| Tema | Contenido |
|---|---|
| Fundamentos de Kubernetes | Arquitectura, API declarativa, el loop de reconciliación |
| Orquestación de contenedores | Pods, Deployments, Services, scheduling |
| Entrega de aplicaciones cloud native | Helm, Kustomize, introducción a GitOps |
| Arquitectura cloud native | El ecosistema CNCF, CNI, runtimes |

---

## Laboratorio

[**Kubernetes: primeras cargas de trabajo y el loop de reconciliación**](./laboratorio-kubernetes.md),
en clase, 70–80 minutos, 4 pasos. Se hace sobre un clúster `kind` de un solo nodo que
tú creas y borras en la misma sesión:

| Paso | Contenido | Tiempo |
|---|---|---|
| 0 | Verificar herramientas y crear el clúster (`kind create cluster`, sin configuración) | ~7 min |
| 1 | La arquitectura de verdad: static pods, kubelet bajo systemd, `containerd` vía `crictl` | ~13 min |
| 2 | Desplegar cargas de trabajo: Pod, Deployment y Service sin memorizar YAML (`--dry-run=client -o yaml`), EndpointSlice y CoreDNS | ~30 min |
| 3 | Auto-reparación y escalado: borrar un pod, matar un contenedor por CRI, escalar 3→5→2 y ver a `kube-proxy` seguir | ~20 min |

Los cuatro pasos son el núcleo y cada uno depende del anterior: no se saltan. Dos ideas
atraviesan el paso 2 y se aplican al resto del curso: **el YAML de Kubernetes no se
memoriza, se genera** con `kubectl create/run/expose … --dry-run=client -o yaml`, y **la
documentación oficial de `kubernetes.io/docs` se consulta siempre**, en el trabajo real y
en los exámenes prácticos de la CNCF.

**Anexo opcional (para casa, no se hace en clase):** al final del mismo archivo, unos 50
minutos más con admission control (`LimitRanger` y tu propio `MutatingWebhookConfiguration`)
y cgroup v2 con Node Memory Swap. Requiere recrear el clúster con un archivo de
configuración de `kind` y tener `openssl` instalado.

**Requisitos:** Linux con Docker Engine activo, `kind` v0.32.0+ y `kubectl` v1.36.x
(soportado dentro de un *minor* del API server). El anexo opcional añade `openssl`, y swap
activo en el host si quieres ver números reales.

**Herramientas y conceptos:** `kubectl`, `kind`, `crictl`, Pods, Deployments, ReplicaSets,
Services, EndpointSlices, CoreDNS, `containerd` / CRI, CNI (aquí `kindnet`; en producción
Cilium, Calico, Flannel). En el anexo: Admission Webhooks, `LimitRange`, cgroup v2, Node
Memory Swap. Helm y Kustomize se mencionan en la sesión, pero este laboratorio no los usa.

---

## Dominios del examen KCNA

El examen cubre fundamentos de Kubernetes, orquestación de contenedores, entrega de
aplicaciones cloud native, arquitectura cloud native y observabilidad.

> **Consulta los pesos oficiales vigentes en la página del examen KCNA de la CNCF.**
> El currículo se revisa periódicamente y los pesos cambian entre versiones; no
> estudies con una tabla de pesos copiada de un blog.

---

## Cómo conecta con el resto del curso

- **Módulo 5 (CKA):** aquí ves el loop de reconciliación; allá lo depuras cuando falla.
- **Módulo 8:** el bucle GitOps es exactamente este loop de reconciliación, extendido
  hasta el repositorio Git.
