# Módulo 7 — Certified Kubernetes Security Specialist (CKS)

**Sesiones 11 y 12 · sábados 10 y 17 de octubre de 2026 · 9:00–12:00**

El módulo más exigente del curso. Requiere tener CKA vigente para presentar el examen,
y con razón: no se puede asegurar lo que no se sabe administrar.

Premisa del módulo: **un clúster de Kubernetes por defecto no es seguro**. Es
permisivo por diseño, para que funcione. Endurecerlo es trabajo explícito.

Certificación de referencia: **CKS**.

---

## Objetivos de aprendizaje

- Defensa activa en tiempo real con **Tetragon** (enforcement con eBPF).
- Cifrado pod-a-pod con **Cilium + WireGuard**, sin gestionar certificados a mano.
- Políticas como código con **Kyverno**: validación y mutación.
- Hardening de nodos con **CIS Kubernetes Benchmark** y `kube-bench`.
- Auditoría del API server y envío de logs a un SIEM para análisis forense.
- NetworkPolicies default-deny **sin romper el DNS del clúster**.
- Pod Security Standards vía Pod Security Admission y cifrado de Secrets en reposo.
- Detección de comportamiento anómalo en runtime con reglas de **Falco**.

---

## Dominios del examen CKS

| Dominio | Peso |
|---|---|
| Minimización de vulnerabilidades en microservicios | 20% |
| Seguridad de la cadena de suministro | 20% |
| Supervisión, registro y seguridad en runtime | 20% |
| Configuración del clúster | 15% |
| Fortalecimiento del clúster | 15% |
| Fortalecimiento del sistema | 10% |

> Verifica los pesos vigentes en la página oficial del examen CKS de la CNCF antes de
> presentarlo.

---

## Laboratorio

**Tetragon, Kyverno y CIS Benchmark** — 60 minutos, 5 pasos (requiere Tetragon y
Kyverno instalados vía Helm):

1. `TracingPolicy` de Tetragon que bloquea `security_kernel_module_request` con acción
   `Sigkill` — enforcement real con eBPF, no solo alerta
2. `ClusterPolicy` de Kyverno que rechaza pods privilegiados
   (`validationFailureAction: Enforce`)
3. Pod Security Standards por etiquetas de namespace: `enforce`, `warn`, `audit`
4. Audit Policy del API server: niveles `RequestResponse`, `Request`, `Metadata`, `None`
5. Ejecutar `kube-bench` como pod privilegiado montando `/var/lib/kubelet`

**Herramientas:** Falco, Tetragon, Kyverno, OPA/Gatekeeper, Cosign, Trivy,
`kube-bench`, CIS Kubernetes Benchmark, AppArmor, Cilium + WireGuard.

---

## Falco y Tetragon no son lo mismo

| | Falco | Tetragon |
|---|---|---|
| Qué hace | **Detecta** y alerta | Detecta y **bloquea** (`Sigkill`) |
| Momento | Después del hecho | En el momento de la llamada al kernel |
| Riesgo | Te enteras tarde | Una política mal escrita mata procesos legítimos |

Se usan juntos: Falco para cobertura amplia de detección, Tetragon para enforcement
quirúrgico en lo que de verdad no puede pasar.

---

## Cómo conecta con el resto del curso

- **Módulo 1:** el fortalecimiento del sistema operativo del nodo empieza en Linux.
- **Módulo 3:** la cadena de suministro empieza en el `Dockerfile` y la imagen base.
- **Módulo 8:** el RBAC restrictivo del agente de IA en el clúster es una aplicación
  directa de este módulo. Un agente con permisos de escritura es un hallazgo de CKS.
