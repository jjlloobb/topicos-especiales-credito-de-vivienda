# **Gobernanza, Evolución Histórica y Superficie de Seguridad en la Virtualización y Contenedores Linux**

El desarrollo de la virtualización basada en primitivas del núcleo (*kernel*) de Linux ha transitado por diversas etapas de innovación, estandarización y tensiones de gobernanza corporativa frente a comunitaria. Comprender la evolución de los estándares abiertos, los modelos de custodia institucional, las políticas de mantenimiento de registros públicos y los análisis cuantitativos de seguridad resulta indispensable para el diseño y aseguramiento de plataformas modernas de cómputo en la nube.

## **1\. Open Container Initiative (OCI): Gobernanza, Especificaciones y Estructura Técnica**

### **Fundación y Miembros Fundadores**

La Open Container Initiative (denominada en su anuncio preliminar como *Open Container Project* u OCP) fue fundada formalmente el **22 de junio de 2015** durante la conferencia DockerCon celebrada en San Francisco, California \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2015-06-20-industry-leaders-unite-to-create-project-for-open-container-standard/, consultado en 2026\)1. El proyecto se estableció como una iniciativa colaborativa bajo el paraguas y la gobernanza neutral de **The Linux Foundation** \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2015-06-20-industry-leaders-unite-to-create-project-for-open-container-standard/, consultado en 2026\)1.  
El objetivo central de la fundación de la OCI fue neutralizar el riesgo de fragmentación técnica en el floreciente ecosistema de contenedores. Para materializar el estándar, Docker donó formalmente la especificación y el código base de su entorno de ejecución (libcontainer, refactorizado como la herramienta de referencia runc), mientras que el equipo de CoreOS aportó el liderazgo técnico de la iniciativa rival *Application Container* (appc) para consolidar un estándar unificado de la industria \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2015-06-20-industry-leaders-unite-to-create-project-for-open-container-standard/, consultado en 2026\)1.  
La coalición de patrocinadores y miembros fundadores estuvo integrada por veinte organizaciones corporativas y proyectos del sector tecnológico \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2015-06-20-industry-leaders-unite-to-create-project-for-open-container-standard/, consultado en 2026\)1:

* Amazon Web Services (AWS)  
* Apcera  
* Cisco  
* CoreOS  
* Docker  
* EMC  
* Fujitsu Limited  
* Goldman Sachs  
* Google  
* HP (Hewlett-Packard)  
* Huawei  
* IBM  
* Intel  
* Joyent  
* The Linux Foundation  
* Mesosphere (posteriormente D2iQ)  
* Microsoft  
* Pivotal  
* Rancher Labs  
* Red Hat  
* VMware

### **Especificaciones Mantenidas por la OCI**

Actualmente, la OCI mantiene tres especificaciones técnicas normativas primarias, complementadas por directrices de empaquetado de artefactos y suites de validación \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/ y https://github.com/opencontainers/tob, consultado en 2026\)2:

| Especificación OCI | Definición Técnica Precisa | Estado Normativo |
| :---- | :---- | :---- |
| **OCI Runtime Specification (runtime-spec)** | Especifica la configuración, el entorno de ejecución en el host y el ciclo de vida del contenedor a partir de un directorio estandarizado en disco (*filesystem bundle*) desacoplado del mecanismo de transporte \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2017-07-17-oci-releases-v1-0-of-container-standards/, consultado en 2026\)2. | Versión 1.0 (Julio 2017\) / v1.x \[VERIFIED\] \[cite: 2\] |
| **OCI Image Specification (image-spec)** | Define el formato del manifiesto de imagen, el descriptor criptográfico de capas del sistema de archivos (*tarballs* serializados), las propiedades de configuración inmutables y la estructura de empaquetado para interoperabilidad entre motores \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2017-07-17-oci-releases-v1-0-of-container-standards/, consultado en 2026\)2. | Versión 1.0 (Julio 2017\) / v1.x \[VERIFIED\] \[cite: 2\] |
| **OCI Distribution Specification (distribution-spec)** | Estandariza la API cliente-servidor basada en el protocolo HTTP/REST para la publicación, descubrimiento, autenticación, subida y descarga de imágenes y artefactos binarios arbitrarios \[VERIFIED\] (Fuente: https://opencontainers.org/posts/announcements/2021-05-04-oci-distribution-specification-v1-0/, consultado en 2026\)2. | Versión 1.0 (Mayo 2021\) / v1.x \[VERIFIED\] \[cite: 2\] |

El organismo aloja adicionalmente iniciativas de estandarización complementarias como *OCI Artifacts*, utilidades de manipulación de imágenes sin privilegios como umoci, y las herramientas de validación de conformidad *runtime-tools* e *image-tools* \[VERIFIED\] (Fuente: https://github.com/opencontainers/tob, consultado en 2026\)2.

### **Gobernanza Técnica y Composición Actual del Technical Oversight Board (TOB)**

La gobernanza general de la OCI se articula formalmente mediante una división de responsabilidades establecida en su estatuto (*Charter*): el **Trademark Board** administra las marcas comerciales, la membresía institucional y los programas de certificación, mientras que el **Technical Oversight Board (TOB)** funge como la máxima autoridad técnica, encargada del arbitraje entre proyectos, la aprobación de nuevas especificaciones y la designación de mantenedores \[VERIFIED\] (Fuente: https://github.com/opencontainers/tob/blob/main/CHARTER.md, consultado en 2026\)6. La evolución técnica cotidiana de cada especificación está delegada a los mantenedores autónomos de la **Technical Developer Community (TDC)** \[VERIFIED\] (Fuente: https://github.com/opencontainers/tob/blob/main/CHARTER.md, consultado en 2026\)6.  
La estructura oficial de miembros electos del Technical Oversight Board (TOB) y su representatividad institucional corresponde a los siguientes registros \[VERIFIED\] (Fuente: https://github.com/opencontainers/tob, consultado en 2026\)3:

| Miembro del TOB | Afiliación Institucional / Empresa | Período de Ejercicio (Term Dates) | Rol en el TOB |
| :---- | :---- | :---- | :---- |
| **Samuel Karp** | Google | 29/01/2026 – 29/01/2028 | Chair (Presidente) \[VERIFIED\] \[cite: 3\] |
| **Sajay Antony** | Microsoft | 29/01/2026 – 29/01/2028 | Miembro \[VERIFIED\] \[cite: 3\] |
| **Mike Brown** | IBM | 29/01/2025 – 29/01/2027 | Miembro \[VERIFIED\] \[cite: 3\] |
| **Jeff Carter** | Docker | 29/01/2026 – 29/01/2028 | Miembro \[VERIFIED\] \[cite: 3\] |
| **Phil Estes** | AWS (Amazon Web Services) | 29/01/2026 – 29/01/2028 | Miembro \[VERIFIED\] \[cite: 3\] |
| **Tianon Gravi** | Docker | 29/01/2025 – 29/01/2027 | Miembro \[VERIFIED\] \[cite: 3\] |
| **Brandon Mitchell** | Independiente | 29/01/2025 – 29/01/2027 | Miembro \[VERIFIED\] \[cite: 3\] |
| **Aleksa Sarai** | Amutable | 29/01/2025 – 29/01/2027 | Miembro \[VERIFIED\] \[cite: 3\] |

## **2\. LXC: Origen Histórico y Gobernanza Actual**

### **Origen e Impulsores Técnicos**

El proyecto **LXC (Linux Containers)** fue creado en el año **2008** \[VERIFIED\] (Fuente: https://medium.com/@alokrahuldevops/day-43-from-chroot-to-clusters-the-origin-story-of-containers-docker-and-the-kubernetes-era-0661d97d683c, consultado en 2026\)5. El desarrollo inicial fue liderado por los ingenieros **Daniel Lezcano** y **Serge Hallyn**, adscritos en ese período a los laboratorios de virtualización de **IBM** \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxc/news/ y https://linuxcontainers.org/incus/announcement/, consultado en 2026\)7.  
LXC se diseñó con el propósito de integrar en una interfaz coherente en espacio de usuario (*userspace*) el conjunto de primitivas que la comunidad del *kernel* de Linux venía incorporando entre 2006 y 2008: los grupos de control de recursos (*Control Groups* o cgroups) y los espacios de nombres (*Namespaces*: PID, Mount, UTS, IPC, Network y posteriormente User) \[VERIFIED\] (Fuente: https://discuss.linuxcontainers.org/t/difference-between-lxc-and-systemd-nspawn/21044, consultado en 2026\)5. Históricamente, las primeras versiones públicas de Docker (0.1 a 0.8 en 2013\) se construyeron sobre LXC como su motor de ejecución predeterminado antes de la introducción de libcontainer \[VERIFIED\] (Fuente: https://medium.com/@alokrahuldevops/day-43-from-chroot-to-clusters-the-origin-story-of-containers-docker-and-the-kubernetes-era-0661d97d683c, consultado en 2026\)5.

### **Gobernanza y Estado Actual de Mantenimiento**

LXC se encuentra alojado bajo el paraguas comunitario independiente del proyecto **Linux Containers** (linuxcontainers.org), una organización técnica neutral dedicada al mantenimiento y evolución de tecnologías de contenedores de sistema \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxc/news/, consultado en 2026\)10.  
El proyecto mantiene un ciclo de ingeniería activo, gobernado mediante lanzamientos con soporte a largo plazo (*Long Term Support* \- LTS) con una ventana de soporte oficial de cinco años por cada rama principal \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxc/news/2024\_04\_03\_20\_04.html y https://linuxcontainers.org/lxc/news/, consultado en 2026\)10:

| Versión LTS de LXC | Fecha Oficial de Publicación | Ventana de Soporte Oficial | Hitos Técnicos Notables |
| :---- | :---- | :---- | :---- |
| **LXC 5.0 LTS** | 2022 | Soporte garantizado hasta junio de 2027 \[VERIFIED\] \[cite: 7\] | Migración completa de compilación a Meson, aislamiento perfeccionado de cgroups v2 \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxc/news/2023\_01\_20\_19\_01.html, consultado en 2026\)7. |
| **LXC 6.0 LTS** | 3 de abril de 2024 \[VERIFIED\] \[cite: 12\] | Soporte garantizado hasta junio de 2029 \[VERIFIED\] \[cite: 12\] | Soporte para binario multi-llamada (tools-multicall), IPv6 activo por defecto en el puente de red lxcbr0, integración de plantillas de imagen OCI sobre squashfs mediante atomfs, migración a dbus-1 \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxc/news/2024\_04\_03\_20\_04.html, consultado en 2026\)12. |
| **LXC 7.0 LTS** | 30 de abril de 2026 \[VERIFIED\] \[cite: 10\] | Soporte garantizado hasta junio de 2031 \[VERIFIED\] \[cite: 10\] | Incorporación de restricciones de seguridad mediante Linux Landlock para el proceso monitor, eliminación definitiva del soporte para cgroups v1, eliminación de compatibilidad con núcleos Linux sin soporte para pidfd y la nueva API de montajes \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxc/news/, consultado en 2026\)10. |

## **3\. LXD: Relación con Canonical, Re-licenciamiento y la Bifurcación Comunitaria (Incus)**

### **Creación y Posición Histórica de Canonical**

LXD (*Linux Container Daemon*) fue anunciado por **Canonical Ltd.** en **noviembre de 2014** e iniciado operativamente a principios de **2015** por un equipo técnico liderado por Stéphane Graber, Christian Brauner, Serge Hallyn y Tycho Andersen \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxd/ y https://linuxcontainers.org/incus/announcement/, consultado en 2026\)8. La arquitectura de LXD nació para ofrecer una experiencia similar a la de un hipervisor sobre LXC: se construyó un demonio en segundo plano escrito en Go, expuesto a través de una API REST protegida por TLS, con capacidades nativas de red virtual, gestión avanzada de almacenamiento (ZFS, Btrfs, Ceph, LVM) y orquestación unificada de contenedores de sistema y máquinas virtuales completas mediante KVM/QEMU \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/docs/main/explanation/instances/, consultado en 2026\)11.  
Durante más de ocho años, LXD existió como un subproyecto alojado dentro de la infraestructura comunitaria de linuxcontainers.org, mientras que Canonical actuaba como su patrocinador corporativo dominante y empleador de los desarrolladores principales \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxd/, consultado en 2026\)11.

### **Ruptura de Gobernanza: Salida de Linux Containers y Re-licenciamiento a AGPLv3**

La relación de gobernanza entre Canonical y la comunidad técnica experimentó dos fracturas documentadas oficialmente:

> 1. **Reubicación Unilateral del Proyecto (4 de julio de 2023):** Canonical decidió retirar el proyecto LXD de la infraestructura de linuxcontainers.org para centralizarlo bajo su dominio corporativo exclusivo \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxd/, consultado en 2026\)11. El repositorio oficial de código fuente se trasladó de github.com/lxc/lxd a github.com/canonical/lxd, la documentación se reubicó en ubuntu.com/lxd y la discusión comunitaria fue derivada a los foros internos de Ubuntu \[VERIFIED\] (Fuente: https://linuxcontainers.org/lxd/, consultado en 2026\)11. Durante esta transición, el líder técnico y mantenedor histórico, Stéphane Graber, abandonó formalmente Canonical \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/announcement/ y https://discuss.linuxcontainers.org/t/lxd-has-been-re-licensed-and-is-now-under-a-cla/18454, consultado en 2026\)8.  
> 2. **Imposición de CLA y Cambio de Licencia a AGPLv3 (Diciembre de 2023):** Canonical modificó unilateralmente la licencia histórica de código abierto permisivo (Apache License 2.0) de LXD, relicenciando el proyecto bajo la **GNU Affero General Public License v3.0 (AGPLv3)** \[VERIFIED\] (Fuente: https://discuss.linuxcontainers.org/t/lxd-has-been-re-licensed-and-is-now-under-a-cla/18454, consultado en 2026\)15. Al mismo tiempo, Canonical impuso la obligación de firmar el **Canonical Contributor License Agreement (CLA)** a cualquier colaborador externo, transfiriendo derechos patrimoniales a Canonical y facultándola para relicenciar comercialmente el código de forma propietaria \[VERIFIED\] (Fuente: https://discuss.linuxcontainers.org/t/lxd-has-been-re-licensed-and-is-now-under-a-cla/18454, consultado en 2026\)15.

### **La Respuesta Comunitaria: Creación y Adopción de Incus**

Frente al cambio de modelo de custodia, la comunidad técnica y los mantenedores históricos articularon una bifurcación (*fork*) comunitaria e independiente \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/announcement/, consultado en 2026\)8:

| Eje de Análisis | Canonical LXD (ubuntu.com/lxd) | Incus (linuxcontainers.org/incus) |
| :---- | :---- | :---- |
| **Origen del Proyecto** | Creado en 2014-2015 por Canonical bajo el paraguas comunitario original \[VERIFIED\]11. | Creado como fork a partir de LXD 5.16 por **Aleksa Sarai**; adoptado formalmente por linuxcontainers.org el **7 de agosto de 2023** \[VERIFIED\]8. |
| **Equipo de Mantenedores** | Desarrolladores adscritos internamente a **Canonical Ltd.** \[VERIFIED\]11. | El equipo creador histórico completo de LXD: **Stéphane Graber, Christian Brauner, Serge Hallyn, Tycho Andersen y Aleksa Sarai** \[VERIFIED\]8. |
| **Primer Lanzamiento Estable** | Continuación de la línea de desarrollo 5.x y subsecuentes bajo control de Canonical \[VERIFIED\]11. | **Incus 0.1** publicado el **7 de octubre de 2023** (paridad con LXD 5.18 con depuración y modernización de API) \[VERIFIED\]13. |
| **Esquema de Licenciamiento** | **AGPLv3** con requisito de firma de **Canonical CLA** \[VERIFIED\]15. | **Apache License 2.0**, sin CLA; gobernado mediante el estándar **Developer Certificate of Origin (DCO)** \[VERIFIED\]15. |
| **Acceso a Servidores de Imágenes** | **Acceso restringido:** El proyecto linuxcontainers.org bloqueó progresivamente el acceso de clientes LXD a su servidor comunitario de imágenes (images.linuxcontainers.org) a inicios de 2024 \[VERIFIED\]11. | Integración nativa e irrestricta con el servidor de plantillas e imágenes del ecosistema Linux Containers \[VERIFIED\]11. |

## **4\. Docker Hub: El Programa de "Imágenes Oficiales" (Namespace library/)**

### **Operación, Revisión y Criterios de Calidad**

El programa de **Docker Official Images** (identificado en Docker Hub mediante repositorios en la raíz o bajo el namespace reservado library/, tales como library/python, library/debian o library/alpine) comprende un catálogo curado de imágenes base fundamentales concebidas para maximizar la seguridad, estandarización y portabilidad \[VERIFIED\] (Fuente: https://docs.docker.com/docker-hub/image-library/trusted-content/ y https://github.com/docker-library/official-images/, consultado en 2026\)18.  
La operación del programa se gestiona públicamente a través del repositorio docker-library/official-images en GitHub \[VERIFIED\] (Fuente: https://github.com/docker-library/official-images/, consultado en 2026\)19. Las propuestas de imágenes nuevas y las modificaciones son evaluadas manualmente por un equipo técnico dedicado de mantenedores del programa (*Official Images Maintainers*) \[VERIFIED\] (Fuente: https://github.com/docker-library/official-images/issues/14813, consultado en 2026\)21.  
Los criterios obligatorios de revisión y mantenimiento abarcan \[VERIFIED\] (Fuente: https://github.com/docker-library/official-images/, consultado en 2026\)19:

* **Software Exclusivamente Libre y de Código Abierto (FOSS):** No se admite la inclusión de paquetes propietarios o con licencias restrictivas.  
* **Compromiso de Mantenimiento Upstream:** Preferencia estricta por proyectos donde el creador original o la comunidad formal asuma la custodia del Dockerfile.  
* **Reproducibilidad y Determinismo:** Fijación rigurosa de versiones de paquetes principales en gestores del sistema (apt-get install \-y paquete=1.2.3), evitando que reconstrucciones posteriores introduzcan cambios incompatibles no declarados.  
* **Prohibición de Dependencias No Oficiales:** Ninguna imagen oficial puede basarse (FROM) en imágenes de terceros ajenas al catálogo oficial, permitiéndose únicamente scratch u otras imágenes oficiales certificadas.  
* **Soporte Multi-Arquitectura:** Construcción coordinada mediante el motor especializado bashbrew para dar cobertura a plataformas de hardware variadas (amd64, arm64, ppc64le, s390x, riscv64).

### **Diferenciación Estructural: Official Images vs. Verified Publisher**

La arquitectura de confianza de Docker Hub segmenta de forma estricta los niveles de verificación de contenido \[VERIFIED\] (Fuente: https://docs.docker.com/enterprise/security/hardened-desktop/image-access-management/ y https://docs.docker.com/docker-hub/repos/manage/trusted-content/, consultado en 2026\)22:

| Característica | Docker Official Images (library/) | Docker Verified Publisher (DVP) |
| :---- | :---- | :---- |
| **Namespace en el Registro** | Namespace reservado library/ o nombres raíz directos (ej. library/python, library/nginx) \[VERIFIED\]18. | Namespace comercial propio de la empresa proveedora (ej. bitnami/\*, vmware/\*, datadog/\*) \[VERIFIED\]23. |
| **Transparencia y Control del Dockerfile** | Código fuente y definiciones 100% públicas y auditadas en github.com/docker-library/official-images \[VERIFIED\]19. | Las canalizaciones de construcción e instrucciones de empaquetado son gestionadas internamente por la entidad comercial \[VERIFIED\]23. |
| **Infraestructura de Construcción** | Se construyen exclusivamente dentro de los entornos automatizados y aislados de Docker mediante bashbrew \[VERIFIED\]19. | Son construidas en la infraestructura del vendedor comercial y publicadas vía credenciales verificadas \[VERIFIED\]23. |
| **Propósito Arquitectónico** | Proveer capas base de distribución y lenguajes mínimos y universales \[VERIFIED\]18. | Proveer binarios de software comercial e infraestructura propietaria respaldados directamente por el fabricante \[VERIFIED\]18. |

### **Política Oficial de Reconstrucción y Despliegue de Parches**

De acuerdo con las directrices operativas documentadas por los mantenedores principales del programa \[VERIFIED\] (Fuente: https://github.com/docker-library/official-images/issues/14813, consultado en 2026\)21:

* **Ciclo Estándar de Actualización:** Las imágenes base de distribuciones Linux (como Debian o Ubuntu) se reconstruyen y sincronizan con los repositorios de seguridad de las distribuciones en una cadencia habitual de **aproximadamente tres a cuatro semanas (frecuencia mensual)** \[VERIFIED\]21. Este período busca un equilibrio óptimo entre la aplicación de parches y la mitigación de la sobrecarga operativa (*downstream rebuild churn*) que experimenta el ecosistema global cuando se invalidan las capas intermedias.  
* **Parches Críticos de Emergencia:** Ante la divulgación de vulnerabilidades de severidad crítica (CVEs de alto impacto con riesgo de explotación remota), se ejecutan reconstrucciones inmediatas fuera del ciclo programado regular \[VERIFIED\]21.  
* **Reconstrucción en Cascada:** Toda actualización aplicada a una imagen base de sistema operativo desencadena automáticamente la recompilación y publicación de todas las imágenes oficiales dependientes de lenguajes y servicios derivados (tales como python, node, golang o ruby) \[VERIFIED\]21.

## **5\. Correlación Cuantitativa: Tamaño de Imagen, Densidad de Paquetes y Superficie de Ataque**

La minimización estructural de las imágenes de contenedor constituye una directriz de seguridad respaldada por organismos de estandarización gubernamental y estudios cuantitativos de telemetría en producción.

### **Estandarización NIST: Special Publication 800-190**

El **National Institute of Standards and Technology (NIST)** formalizó las directrices normativas en la **NIST SP 800-190: *Application Container Security Guide*** (publicada en septiembre de 2017 por Murugiah Souppaya, John Morello y Karen Scarfone) \[VERIFIED\] (Fuente: https://csrc.nist.gov/pubs/sp/800/190/final, consultado en 2026\)26.  
El documento establece que las imágenes que contienen utilidades de propósito general del sistema operativo (tales como intérpretes de comandos bash/sh, gestores de paquetes apt/yum, compiladores y herramientas de depuración de red) expanden de forma innecesaria la superficie de vulnerabilidad del contenedor \[VERIFIED\] (Fuente: https://csrc.nist.gov/pubs/sp/800/190/final y https://csrc.nist.gov/news/2017/nist-releases-nistir-8176, consultado en 2026\)26. El estándar dictamina el uso de imágenes base mínimas (*minimal images*) que contengan exclusivamente las bibliotecas y binarios estrictamente necesarios para la ejecución del servicio, reduciendo la exposición a vulnerabilidades latentes y suprimiendo las herramientas habituales empleadas por un atacante durante la fase de movimiento lateral post-compromiso \[VERIFIED\] (Fuente: https://csrc.nist.gov/pubs/sp/800/190/final, consultado en 2026\)26.

### **Datos Cuantitativos Publicados en Reportes de Seguridad**

Los hallazgos de seguridad industrial documentan la relación directa entre el número de paquetes heredados y las vulnerabilidades detectadas:

| Fuente y Estudio | Naturaleza del Dato | Hallazgos Cuantitativos y Métricas Reportadas |
| :---- | :---- | :---- |
| **Sysdig Cloud-Native Security Report (2024)** | Telemetría real en producción \[VENDOR CLAIM\] (Fuente: https://safeguard.sh/resources/blog/container-security-best-practices-checklist, consultado en 2026\)29 | El **87% de las imágenes de contenedores en entornos de producción albergan al menos una vulnerabilidad de severidad Crítica o Alta** \[VENDOR CLAIM\]29. El análisis en tiempo de ejecución determinó que el **85% de los paquetes instalados dentro de las imágenes en producción nunca son ejecutados en memoria**, constituyendo código muerto que infla la superficie de ataque \[VENDOR CLAIM\]. |
| **Snyk State of Open Source Security Report** | Análisis de dependencias de código \[VENDOR CLAIM\] | El **70% de las vulnerabilidades detectadas en contenedores residen en los paquetes del sistema operativo base**, y no en las dependencias directas o el código propio de la aplicación del usuario \[VENDOR CLAIM\]. |
| **Chainguard Security & Distroless Benchmarks (2023–2024)** | Análisis comparativo de imágenes \[VENDOR CLAIM\] | Las imágenes basadas en distribuciones de propósito general (Debian/Ubuntu estándar) acumulan entre 50 y 500+ CVEs debido a la inclusión de cientos de paquetes auxiliares \[VENDOR CLAIM\]. Las imágenes endurecidas (*Distroless/Minimal*) reducen el inventario de paquetes en más de un 90% y reducen las vulnerabilidades a cero o niveles marginales \[VENDOR CLAIM\] (Fuente: https://docs.docker.com/dhi/explore/security-concepts/hardening/, consultado en 2026\)30. |

## **6\. "Contenedor de Sistema" vs. "Contenedor de Aplicación": Origen Terminológico y Presencia Textual**

### **Origen Terminológico**

La distinción conceptual entre *contenedor de sistema* (*system container*) y *contenedor de aplicación* (*application container*) tiene su génesis en la divergencia de objetivos de diseño en la historia de la virtualización basada en el núcleo de Linux \[VERIFIED\] (Fuente: https://medium.com/@alokrahuldevops/day-43-from-chroot-to-clusters-the-origin-story-of-containers-docker-and-the-kubernetes-era-0661d97d683c, consultado en 2026\)5:

> 1. **La Tradición de Virtualización de Sistema Operativo (2000–2008):** Descendiente de tecnologías pioneras como *FreeBSD Jails* (2000), *Solaris Zones* (2004) y *OpenVZ* (2005), este enfoque concibe el contenedor como un entorno multi-proceso de espacio de usuario completo, administrado por un sistema de inicialización formal (init, systemd, OpenRC) y operado conceptualmente como una máquina virtual ligera que comparte el núcleo con el host \[VERIFIED\] (Fuente: https://medium.com/@alokrahuldevops/day-43-from-chroot-to-clusters-the-origin-story-of-containers-docker-and-the-kubernetes-era-0661d97d683c, consultado en 2026\)5. Esta línea evolutiva fundamenta la arquitectura de LXC, LXD e Incus \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/docs/main/explanation/instances/, consultado en 2026\)14.  
> 2. **La Tradición de Microservicios y Empaquetado Inmutable (2013–Presente):** Popularizado por Docker y consolidado por el ecosistema de Kubernetes y OCI, este paradigma diseña el contenedor como una unidad efímera e inmutable orientada a encapsular un único proceso o servicio de aplicación (proceso PID 1 enfocado en la aplicación en lugar de un sistema *init* completo), permitiendo orquestación elástica y ciclos de despliegue declarativos \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/docs/main/explanation/instances/ y https://linuxcontainers.org/incus/docs/main/explanation/containers\_and\_vms/, consultado en 2026\)5.

### **Evidencia Textual en la Documentación Oficial de linuxcontainers.org**

La documentación técnica del proyecto Linux Containers en su componente central Incus emplea explícita y taxativamente los términos **"System containers"** y **"Application containers"** para categorizar los diferentes modelos de aislamiento \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/docs/main/explanation/instances/ y https://linuxcontainers.org/incus/docs/main/explanation/containers\_and\_vms/, consultado en 2026\)14.  
Las páginas específicas de la documentación oficial son:

* **Página 1:** https://linuxcontainers.org/incus/docs/main/explanation/instances/ \[VERIFIED\]  
  \[cite: 14\]  
* **Página 2:** https://linuxcontainers.org/incus/docs/main/explanation/containers\_and\_vms/ \[VERIFIED\]  
  \[cite: 32\]

La documentación oficial formula las siguientes definiciones textuales \[VERIFIED\] (Fuente: https://linuxcontainers.org/incus/docs/main/explanation/instances/, consultado en 2026):  
> *"System containers run full Linux distributions using a shared kernel. Those containers run a full Linux distribution, very similar to a virtual machine but sharing kernel with the host system. They have an extremely low overhead, can be packed very densely and generally provide a near identical experience to virtual machines without the required hardware support and overhead. System containers are implemented through the use of liblxc (LXC)."* \[VERIFIED\]  
> \[cite: 14\]  
> *"Application containers run a single application through a pre-built image. Those kind of containers got popularized by the likes of Docker and Kubernetes. Rather than provide a pristine Linux environment on top of which software needs to be installed, they instead come with a pre-installed and mostly pre-configured piece of software. Incus can consume application container images from any OCI-compatible image registry (e.g. the Docker Hub). Application containers are implemented through the use of liblxc (LXC) with help from umoci and skopeo."* \[VERIFIED\]  
> \[cite: 14\]

| Dimensión Técnica | Contenedor de Sistema (LXC / Incus) | Contenedor de Aplicación (Docker / OCI / Podman) | Máquina Virtual Ligera (KVM / QEMU / Incus VM) |
| :---- | :---- | :---- | :---- |
| **Proceso Inicial (PID 1\)** | Sistema de inicialización completo (systemd, OpenRC) \[VERIFIED\]33. | El proceso directo de la aplicación o servicio \[VERIFIED\]31. | Sistema de inicialización dentro del sistema operativo invitado \[VERIFIED\]32. |
| **Núcleo de Ejecución** | Núcleo compartido del host (uname \-r idéntico) \[VERIFIED\]31. | Núcleo compartido del host (uname \-r idéntico) \[VERIFIED\]31. | Núcleo de invitado independiente aislado por hardware \[VERIFIED\]14. |
| **Mapeo de Usuarios Predeterminado** | Contenedores no privilegiados por defecto (remapeo de userns a rangos altos de UID/GID) \[VERIFIED\]12. | Comparte el espacio de usuario raíz (UID 0\) del host por defecto \[VERIFIED\]30. | Aislamiento completo a nivel de máquina virtual e hipervisor \[VERIFIED\]32. |
| **Estado del Sistema de Archivos** | Sistema de archivos mutable completo con herramientas de administración de distribución \[VERIFIED\]14. | Capas de sólo lectura (*read-only layers*) inmutables basadas en la especificación OCI \[VERIFIED\]14. | Imagen de disco virtualizada particionada completa \[VERIFIED\]32. |
| **Mecanismo de Implementación** | Implementado mediante liblxc \[VERIFIED\]14. | Implementado mediante runc / crun / containerd \[VERIFIED\]5. | Implementado mediante emulación por hardware vía QEMU / KVM \[VERIFIED\]14. |

#### **Works cited**

> 1. Industry Leaders Unite to Create Project for Open Container Standards, [https://opencontainers.org/posts/announcements/2015-06-20-industry-leaders-unite-to-create-project-for-open-container-standard/](https://opencontainers.org/posts/announcements/2015-06-20-industry-leaders-unite-to-create-project-for-open-container-standard/)  
> 2. Announcements \- Open Container Initiative, [https://opencontainers.org/posts/announcements/](https://opencontainers.org/posts/announcements/)  
> 3. opencontainers/tob: Technical Oversight Board (TOB) \- GitHub, [https://github.com/opencontainers/tob](https://github.com/opencontainers/tob)  
> 4. Top LXC Alternatives in 2026 \- Slashdot, [https://slashdot.org/software/p/LXC/alternatives](https://slashdot.org/software/p/LXC/alternatives)  
> 5. Day 43 —From chroot to clusters: the origin story of containers, Docker, and the Kubernetes era | by Alok Rahul | Medium, [https://medium.com/@alokrahuldevops/day-43-from-chroot-to-clusters-the-origin-story-of-containers-docker-and-the-kubernetes-era-0661d97d683c](https://medium.com/@alokrahuldevops/day-43-from-chroot-to-clusters-the-origin-story-of-containers-docker-and-the-kubernetes-era-0661d97d683c)  
> 6. tob/CHARTER.md at main · opencontainers/tob \- GitHub, [https://github.com/opencontainers/tob/blob/main/CHARTER.md](https://github.com/opencontainers/tob/blob/main/CHARTER.md)  
> 7. LXC \- News \- Linux Containers, [https://linuxcontainers.org/lxc/news/2023\_01\_20\_19\_01.html](https://linuxcontainers.org/lxc/news/2023_01_20_19_01.html)  
> 8. Incus \- Announcement \- Linux Containers, [https://linuxcontainers.org/incus/announcement/](https://linuxcontainers.org/incus/announcement/)  
> 9. Difference between LXC and systemd-nspawn? \- Linux Containers Forum, [https://discuss.linuxcontainers.org/t/difference-between-lxc-and-systemd-nspawn/21044](https://discuss.linuxcontainers.org/t/difference-between-lxc-and-systemd-nspawn/21044)  
> 10. LXC \- News \- Linux Containers, [https://linuxcontainers.org/lxc/news/](https://linuxcontainers.org/lxc/news/)  
> 11. LXD \- Has been moved to Canonical \- Linux Containers, [https://linuxcontainers.org/lxd/](https://linuxcontainers.org/lxd/)  
> 12. LXC \- News \- Linux Containers, [https://linuxcontainers.org/lxc/news/2024\_04\_03\_20\_04.html](https://linuxcontainers.org/lxc/news/2024_04_03_20_04.html)  
> 13. Incus \- News \- Linux Containers, [https://linuxcontainers.org/incus/news/2023\_10\_07\_06\_10.html](https://linuxcontainers.org/incus/news/2023_10_07_06_10.html)  
> 14. About instances \- Incus documentation \- Linux Containers, [https://linuxcontainers.org/incus/docs/main/explanation/instances/](https://linuxcontainers.org/incus/docs/main/explanation/instances/)  
> 15. LXD has been re-licensed and is now under a CLA \- Linux Containers Forum, [https://discuss.linuxcontainers.org/t/lxd-has-been-re-licensed-and-is-now-under-a-cla/18454](https://discuss.linuxcontainers.org/t/lxd-has-been-re-licensed-and-is-now-under-a-cla/18454)  
> 16. Incus/LXD: What is the path forward for users of other distros? \- Linux Containers Forum, [https://discuss.linuxcontainers.org/t/incus-lxd-what-is-the-path-forward-for-users-of-other-distros/18587](https://discuss.linuxcontainers.org/t/incus-lxd-what-is-the-path-forward-for-users-of-other-distros/18587)  
> 17. Incus \- Introduction \- Linux Containers, [https://linuxcontainers.org/incus/](https://linuxcontainers.org/incus/)  
> 18. Trusted content \- Docker Docs, [https://docs.docker.com/docker-hub/image-library/trusted-content/](https://docs.docker.com/docker-hub/image-library/trusted-content/)  
> 19. Primary source of truth for the Docker "Official Images" program \- GitHub, [https://github.com/docker-library/official-images/](https://github.com/docker-library/official-images/)  
> 20. Update photon image · docker-library/official-images@05b494e \- GitHub, [https://github.com/docker-library/official-images/actions/runs/26359033567](https://github.com/docker-library/official-images/actions/runs/26359033567)  
> 21. Release schedule for Debian security upgrades · Issue \#14813 · docker-library/official-images \- GitHub, [https://github.com/docker-library/official-images/issues/14813](https://github.com/docker-library/official-images/issues/14813)  
> 22. Trusted content \- Docker Docs, [https://docs.docker.com/docker-hub/repos/manage/trusted-content/](https://docs.docker.com/docker-hub/repos/manage/trusted-content/)  
> 23. Image Access Management \- Docker Docs, [https://docs.docker.com/enterprise/security/hardened-desktop/image-access-management/](https://docs.docker.com/enterprise/security/hardened-desktop/image-access-management/)  
> 24. Repositories \- Docker Docs, [https://docs.docker.com/docker-hub/repos/](https://docs.docker.com/docker-hub/repos/)  
> 25. Building best practices \- Docker Docs, [https://docs.docker.com/build/building/best-practices/](https://docs.docker.com/build/building/best-practices/)  
> 26. SP 800-190, Application Container Security Guide | CSRC, [https://csrc.nist.gov/pubs/sp/800/190/final](https://csrc.nist.gov/pubs/sp/800/190/final)  
> 27. NIST Announces the Release of SP 800-190 | CSRC, [https://csrc.nist.gov/news/2017/nist-announces-the-release-of-sp-800-190](https://csrc.nist.gov/news/2017/nist-announces-the-release-of-sp-800-190)  
> 28. NIST Announces the Release of NISTIR 8176 Security Assurance Requirements for Linux Application Container Deployments October 12, 2017, [https://csrc.nist.gov/news/2017/nist-releases-nistir-8176](https://csrc.nist.gov/news/2017/nist-releases-nistir-8176)  
> 29. Container Security Best Practices Checklist (2024) \- Safeguard.sh, [https://safeguard.sh/resources/blog/container-security-best-practices-checklist](https://safeguard.sh/resources/blog/container-security-best-practices-checklist)  
> 30. Base image hardening \- Docker Docs, [https://docs.docker.com/dhi/explore/security-concepts/hardening/](https://docs.docker.com/dhi/explore/security-concepts/hardening/)  
> 31. A general question about containers technology \- Linux Containers Forum, [https://discuss.linuxcontainers.org/t/a-general-question-about-containers-technology/8353](https://discuss.linuxcontainers.org/t/a-general-question-about-containers-technology/8353)  
> 32. About containers and VMs \- Incus documentation, [https://linuxcontainers.org/incus/docs/main/explanation/containers\_and\_vms/](https://linuxcontainers.org/incus/docs/main/explanation/containers_and_vms/)  
> 33. LXC \- News \- Linux Containers, [https://linuxcontainers.org/de/lxc/news/2019\_03\_12\_15\_03.html](https://linuxcontainers.org/de/lxc/news/2019_03_12_15_03.html)