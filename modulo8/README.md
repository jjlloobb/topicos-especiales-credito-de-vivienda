# Módulo 8 — A Producción: Paisaje CNCF, Agentes y GitOps

**Sesiones 13 y 14 · sábados 24 y 31 de octubre de 2026 · 9:00–12:00**

El módulo donde todo cierra. El producto que fijaste en el módulo 2, especificaste en
el 3 y aprendiste a construir en los módulos 4 a 7, aquí llega a producción — y se
queda ahí, operado con ayuda de agentes de IA.

Es también el módulo que da forma a la **sustentación final** de la sesión 16.

---

## Objetivos de aprendizaje

- Seleccionar herramientas del paisaje CNCF (Argo CD/Flux, Helm, Trivy, Cosign,
  Cilium, Crossplane, Prometheus/OpenTelemetry) y describir cómo un agente las conecta.
- Operar agentes dentro del clúster —**kagent**, **K8sGPT**, **HolmesGPT**— y explicar
  qué hace cada uno **y cuáles son sus puntos ciegos**.
- Acotar un agente con dos capas independientes: **allowlist de herramientas** y
  **RBAC del ServiceAccount**.
- Cerrar el bucle GitOps: detectar → diagnosticar → **proponer un PR con evidencia** →
  aprobar → reconciliar. Nunca auto-aprobar.

---

## Agenda

| Tema | Contenido |
|---|---|
| El ciclo de vida envuelto en IA | El paisaje CNCF y dónde encaja cada pieza |
| Los tres agentes del clúster | kagent, K8sGPT, HolmesGPT: qué hace cada uno |
| Allowlist y RBAC | Las dos capas del sandbox del agente |
| El bucle GitOps | Detectar, diagnosticar, proponer un pull request |
| Reto | Construir el agente auditor que termina en un pull request |

---

## La regla que gobierna todo el módulo

> **El agente propone, un humano aprueba.**

No es filosofía, es diseño. Cada capa que verás aquí —el allowlist de herramientas MCP,
el RBAC del ServiceAccount del agente, el gate de CI, la revisión del pull request—
existe para que el robot pueda hacer el trabajo **sin poder darse su propio visto bueno**.

El destino de la cadena del agente no es un `kubectl apply` autónomo: es **un pull
request con la evidencia adjunta**. Esa diferencia es la que hace que un SRE te deje
conectar un agente a su producción.

---

## Laboratorio

**GitOps con Flux v2: SOPS, ImagePolicy y rollback** — 60 minutos, 5 pasos
(requiere el CLI de `flux`, `age`, `sops` y un clúster K8s 1.26+):

1. `flux check --pre` y `flux install --dry-run`
2. Generar una clave Age y cifrar un Secret con SOPS (`--encrypted-regex`)
3. Crear los manifiestos `GitRepository` y `Kustomization`
4. `HelmRelease` con `test.enable: true` y rollback automático (`remediation.retries`)
5. Configurar `Provider` y `Alert` de notificaciones de Flux

**Herramientas:** kagent, K8sGPT, HolmesGPT, Flux v2 (source-controller,
kustomize-controller, helm-controller, notification-controller), Argo CD, SOPS + Age,
Helm, Crossplane, Trivy, Cosign, Cilium, Prometheus, OpenTelemetry, Grafana, Kyverno.

---

## Proyecto final

La sustentación de la **sesión 16 (sábado 14 de noviembre de 2026)** presenta el arco
completo:

1. El **PVB** del módulo 2 y qué cambió desde entonces (si nada cambió, no investigaste)
2. El **PRD** del módulo 3 y las decisiones de alcance que tomaste
3. La aplicación **corriendo en Kubernetes**
4. El **bucle GitOps** funcionando: un cambio en Git que se reconcilia en el clúster
5. Un **agente** operando dentro de sus límites, con la evidencia de que no puede
   salirse de ellos (`kubectl auth can-i` es tu mejor diapositiva)
6. Los **riesgos** que documentaste y cómo los mitigaste

Se evalúa el arco completo y la honestidad del análisis, no solo que la demo funcione.
