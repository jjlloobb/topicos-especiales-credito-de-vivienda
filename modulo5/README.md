# Módulo 5 — Certified Kubernetes Administrator (CKA)

**Sesiones 6 y 7 · sábados 5 y 12 de septiembre de 2026 · 9:00–12:00**

El pivote técnico del semestre. Aquí dejas de usar Kubernetes y empiezas a
administrarlo: el clúster es tuyo, y cuando se rompe, lo arreglas tú.

El CKA es un examen **práctico y cronometrado**: no hay preguntas de opción múltiple,
hay una terminal y problemas que resolver. Se estudia con las manos.

Certificación de referencia: **CKA**.

---

## Objetivos de aprendizaje

- Mantener ETCD: `defrag`, desarmar alarmas, snapshots y restauración.
- Optimizar `kube-proxy` con IPVS en lugar de iptables para alta escala.
- Diagnosticar fallos de red L3/L4 en Flannel y Calico.
- Auditar RBAC con `kubectl auth can-i` y detectar rutas de escalada de privilegios.
- Gestionar PVCs con StorageClass y expansión de volumen en caliente vía CSI.

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

## Laboratorio

**ETCD defrag, IPVS y auditoría de RBAC** — 60 minutos, 5 pasos:

1. Verificar el estado de ETCD y practicar sus comandos de mantenimiento
2. Auditar permisos de un ServiceAccount con `kubectl auth can-i --as=`
3. Detectar `ClusterRoleBindings` con `cluster-admin`: la ruta de escalada más común
4. Verificar y migrar el modo de `kube-proxy` a IPVS
5. Expandir un PVC en caliente vía CSI (`allowVolumeExpansion`)

**Herramientas:** `kubeadm`, `etcdctl`, IPVS/iptables, Ingress (NGINX, Traefik),
Gateway API, CNI (Calico, Flannel, Cilium), `kube-bench`, CIS Kubernetes Benchmark,
cert-manager, Helm, Kustomize, `containerd`/CRI-O.

---

## Cómo preparar el examen

- **Practica contra reloj.** El CKA se pierde por tiempo, no por desconocimiento.
- **Domina `kubectl explain` y la documentación oficial**, que sí puedes consultar
  durante el examen. Saber buscar rápido vale más que memorizar campos.
- **Aliases y `--dry-run=client -o yaml`.** Escribir YAML a mano cuesta minutos que
  no tienes.

---

## Cómo conecta con el resto del curso

- **Módulo 1:** el troubleshooting de nodo se hace con `systemd` y `journalctl`.
- **Módulo 7 (CKS):** la auditoría de RBAC que aquí es diagnóstico, allá es defensa.
- **Módulo 8:** un agente de IA que diagnostica el clúster necesita exactamente estos
  permisos de solo lectura — y entender por qué no más.
