# Contexto: alcance del curso que va a usar este research

Curso: "Tópicos Especiales en Informática" — Maestría en Ingeniería de Sistemas,
Pontificia Universidad Javeriana, Bogotá. Clases sábados 9am-12pm, semestre 2026-3.

Módulos del curso (en orden):
1. Fundamentos de Linux (LFCS)
2. AI & Agentic Engineering (Product Vision Board → deep research → PRD → build dirigido por especificaciones)
3. Docker, Compose y Runtimes de Contenedores
4. Kubernetes Fundamentals (KCNA)
5. Certified Kubernetes Administrator (CKA)
6. Certified Kubernetes Application Developer (CKAD)
7. Certified Kubernetes Security Specialist (CKS)
8. A Producción: Paisaje CNCF, Agentes (kagent, K8sGPT, HolmesGPT) y GitOps (Argo CD / Flux)

Este research específicamente alimenta un laboratorio práctico de 75-90 minutos del
módulo 3, ya escrito y verificado con comandos reales, sobre runtimes de contenedores y
virtualización ligera: namespaces/cgroups compartidos (módulo 1 llevado a la práctica),
contenedor de sistema (LXC/LXD) vs contenedor de aplicación (Docker), máquina virtual
ligera vía `lxc launch --vm`, redes/almacenamiento automáticos de LXD vs declarados a
mano en Docker/Compose, y una comparación empírica con Trivy de vulnerabilidades según
tamaño de imagen base más una demostración de root vs no-root a nivel de capacidades
Linux.

El laboratorio termina con una sección "Para profundizar" que apunta a este research: es
material de enriquecimiento conceptual (gobernanza, historia de proyecto, estudios
publicados) para estudiantes que quieran ir más allá de lo que vieron correr en su
propia terminal — no es contenido bloqueante para completar el laboratorio.
