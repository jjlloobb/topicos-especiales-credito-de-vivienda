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

**Admission Webhooks y EndpointSlices** — 60 minutos, 5 pasos (requiere Kubernetes 1.28+):

1. Desplegar un Deployment y un Service, y observar los EndpointSlices que se crean
2. Observar el loop Watch-Diff-Update: borrar un pod y ver cómo se recrea
3. Crear un `MutatingWebhookConfiguration`
4. Verificar Node Memory Swap y cgroup v2
5. Escalar réplicas y ver los EndpointSlices actualizarse en vivo

**Herramientas:** `kubectl`, EndpointSlices, Admission Webhooks, Helm, Kustomize,
CNI (Cilium, Calico, Flannel), `containerd` / CRI-O.

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
