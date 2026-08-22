# Módulo 1 — Fundamentos de Linux (LFCS)

**Sesión 1 · sábado 1 de agosto de 2026 · 9:00–12:00**

Todo lo que viene después corre sobre Linux. Un contenedor es un proceso de Linux con
namespaces y cgroups; un nodo de Kubernetes es una máquina Linux. Si este módulo queda
flojo, los módulos 3 a 8 se vuelven magia negra.

Certificación de referencia: **LFCS** (Linux Foundation Certified System Administrator).

---

## Objetivos de aprendizaje

- Manejar con fluidez los comandos esenciales: archivos, permisos, búsqueda y Git.
- Operar servicios con `systemd`, escribir scripts de Bash y gestionar paquetes.
- Administrar usuarios y grupos, `sudo`, límites de recursos y autenticación centralizada.
- Configurar redes: IPv4/IPv6, firewall con `nftables`, proxy inverso y sincronización horaria.
- Administrar almacenamiento: particiones, LVM, sistemas de archivos y NFS.

---

## Agenda

| Tema | Contenido |
|---|---|
| Historia | De dónde viene Linux y por qué importa esa herencia |
| Comandos esenciales | Archivos, permisos, búsqueda, control de versiones con Git |
| Operaciones y despliegue | `systemd`, scripts de Bash, gestión de paquetes y contenedores |
| Usuarios y grupos | `sudo`, límites de recursos (PAM / `limits.d`), LDAP y SSSD |
| Redes | IPv4/IPv6, `nftables`, proxy inverso, NTP |
| Almacenamiento | Particiones, LVM, sistemas de archivos, NFS, rendimiento |

---

## Dominios del examen LFCS

| Dominio | Peso |
|---|---|
| Operaciones y despliegue | 25% |
| Redes | 25% |
| Comandos esenciales | 20% |
| Almacenamiento | 20% |
| Usuarios y grupos | 10% |

> Verifica los pesos vigentes en la página oficial de la Linux Foundation antes de
> presentar el examen: cambian entre versiones del currículo.

---

## Laboratorio

**Hardening de host, almacenamiento y red** — 90 minutos, 9 pasos:

1. Flujo Git completo: `init`, `commit`, `branch`, `merge`
2. Verificación de integridad con `sha256sum`
3. Unidad `systemd` personalizada
4. ACLs con `setfacl` / `getfacl`
5. Usuario y grupo con límite de recursos vía `limits.d`
6. Autenticación SSH por clave pública
7. Regla `nftables`: permitir SSH, denegar el resto
8. Crear y extender un volumen LVM en caliente (`pvcreate`, `vgcreate`, `lvcreate`, `lvextend -r`)
9. Snapshot LVM y su reversión (copy-on-write)

**Herramientas:** `nftables`, LVM, `setfacl`/`getfacl`, `systemd`/`journalctl`,
SSSD/LDAP, Git, `gpg`, `sha256sum`, `losetup`, OpenSSH.

---

## Cómo conecta con el resto del curso

- **Módulo 3:** los namespaces y cgroups que aquí son teoría, allá son el contenedor.
- **Módulo 5 (CKA):** el 30% del examen es troubleshooting, y buena parte se
  diagnostica desde el nodo con `systemd`, `journalctl` y herramientas de red.
- **Módulo 7 (CKS):** el hardening del sistema operativo del nodo es un dominio propio.
