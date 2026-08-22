Actúa como un investigador técnico senior especializado en infraestructura de contenedores y virtualización Linux, haciendo un deep research de verificación (no de opinión ni de resumen de blogs) sobre la gobernanza, historia y estado actual de varias tecnologías. El resultado alimenta material didáctico de un curso universitario de posgrado en ingeniería de sistemas, y ya existe un laboratorio práctico completo basado en comandos reales verificados en una máquina — lo que necesito de ti es exactamente lo que un laboratorio práctico NO puede darme: gobernanza, historia de los proyectos, y datos de estudios/benchmarks publicados. Rigor y fuentes verificables, no fluidez.

## Contexto técnico ya verificado empíricamente (no lo investigues, ya lo confirmé corriendo los comandos)

- Un contenedor Docker y un contenedor de sistema LXC/LXD comparten el kernel del host (mismo `uname -r` adentro y afuera).
- Una máquina virtual lanzada con `lxc launch ... --vm` corre un kernel de invitado distinto (KVM real).
- Docker por defecto no remapea el namespace `user`: root dentro del contenedor y root del host comparten el mismo namespace de usuario.
- `python:3.13` (Debian completo, 1.62 GB) trae 438 vulnerabilidades HIGH/CRITICAL según un escaneo con Trivy (DB actualizada 2026-08-07); `python:3.13-slim` (178 MB) trae 23; `alpine:3.20` (12.2 MB) trae 0.
- Un proceso root en un contenedor Alpine tiene una máscara de capacidades Linux (`CapEff`) no nula (incluye `cap_net_bind_service`, `cap_sys_chroot`, `cap_setuid`, `cap_dac_override`, entre otras); con `--user 1000:1000` la máscara es cero.

No necesito que verifiques ninguno de esos datos — son observaciones directas mías. Lo que sí necesito es lo siguiente:

## 1. Open Container Initiative (OCI) — gobernanza exacta

- ¿Cuándo se fundó, bajo qué organización (Linux Foundation u otra), y quiénes fueron los miembros/patrocinadores fundadores?
- ¿Cuántas especificaciones mantiene actualmente (image-spec, runtime-spec, distribution-spec, u otras) y qué define cada una, en una frase técnica precisa?
- ¿Quién gobierna el proyecto hoy (estructura de mantenedores, empresas con asiento en el comité técnico)? Nombra la fuente oficial (oci.org, github.com/opencontainers, o documentación de la Linux Foundation), con fecha de consulta.

## 2. LXC — origen y gobernanza actual

- ¿En qué año se creó el proyecto LXC y quién lo inició?
- ¿Bajo qué organización/paraguas vive hoy (el proyecto "Linux Containers", linuxcontainers.org)? ¿Sigue activamente mantenido — cuál fue su lanzamiento estable más reciente y de qué fecha?

## 3. LXD — relación con Canonical, y **busca activamente si hubo algún cambio de gobernanza o fork**

- ¿Quién creó LXD y en qué año? ¿Cuál es su relación exacta con Canonical (Canonical es el mantenedor principal, un patrocinador, o algo distinto)?
- **Esto es importante, investígalo con cuidado y no lo omitas si lo encuentras incómodo para una narrativa simple:** ¿Hubo en algún momento un cambio en la forma en que Canonical licencia o gobierna LXD (por ejemplo, requerir un Contributor License Agreement, relicenciamiento, o cambios de gobernanza) que haya generado una bifurcación (fork) del proyecto por parte de la comunidad o de antiguos mantenedores? Si existe un proyecto derivado (por ejemplo, uno llamado "Incus" u otro), documenta qué es, quién lo mantiene, cuándo se creó y por qué se separó — con fuentes primarias (anuncios oficiales, no solo foros). Si no encuentras evidencia pública sólida de esto, dilo explícitamente en vez de omitir la sección.

## 4. Docker Hub — el programa de "imágenes oficiales"

- ¿Cómo funciona exactamente el programa de "Docker Official Images" (namespace `library/`)? ¿Quién las revisa, con qué criterios de seguridad/mantenimiento, y qué lo distingue del programa separado de "Verified Publisher"?
- Cifra o política oficial (no de un blog de terceros) sobre cada cuánto se reconstruyen/parchan las imágenes oficiales.

## 5. Investigación publicada sobre tamaño de imagen y superficie de vulnerabilidades

- Busca estudios, reportes de vendors de seguridad de contenedores (Sysdig, Snyk, Chainguard, Wiz, Aqua Security, o guías del NIST/CISA) que documenten la relación entre tamaño/número de paquetes de una imagen base y su cantidad de CVEs o superficie de ataque — con cifras y fecha. Esto complementaría (no reemplazaría) mi propia medición empírica con Trivy.
- Si son cifras de marketing de un vendor de un producto de seguridad, etiquétalas [VENDOR CLAIM] igual que cualquier otra afirmación comercial.

## 6. "Contenedor de sistema" vs "contenedor de aplicación" — origen del término

- ¿De dónde viene esta distinción terminológica ("system container" vs "application container")? ¿La documentación oficial de linuxcontainers.org la usa con esas palabras exactas? Cita la página específica.

## Reglas estrictas de evidencia (las mismas de siempre en este curso)

- **Cada afirmación factual lleva URL de fuente y fecha de consulta.** Sin excepción.
- **Nunca cites los archivos de contexto adjuntos como fuente.** Son insumos míos, no investigación verificada.
- Etiqueta cada afirmación como **[VERIFIED]** (fuente primaria oficial: sitio del proyecto, Linux Foundation, documentación oficial), **[VENDOR CLAIM]** (marketing de una empresa/producto), o **[SPECULATIVE]** (sin fuente sólida).
- **Busca activamente evidencia que complique la narrativa simple** — en particular en la pregunta 3 (LXD/Canonical/posible fork). No suavices ni omitas una historia de gobernanza incómoda.
- Si no encuentras evidencia pública sólida para algo, dilo explícitamente ("no encontré evidencia pública verificable de X") en vez de rellenar con algo plausible pero no verificado.
- Nombres exactos de proyectos y organizaciones — no inventes expansiones de siglas ni nombres.

## Formato de salida

Markdown, seis secciones numeradas como encabezados (una por cada punto de arriba), cada afirmación con su URL y etiqueta [VERIFIED]/[VENDOR CLAIM]/[SPECULATIVE]. Al final, una sección "Fuentes citadas" con la lista completa de URLs. Escribe en español.
