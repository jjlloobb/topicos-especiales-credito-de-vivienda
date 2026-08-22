# Módulo 3 — Docker, Compose y Runtimes de Contenedores

**Sesión 3 · sábado 15 de agosto de 2026 · 9:00–12:00**

Doble propósito. En lo técnico, este módulo baja el contenedor de la metáfora al
mecanismo: namespaces, cgroups y union filesystem. En lo de producto, aquí conviertes
el Product Vision Board del módulo 2 en un **PRD** (Product Requirements Document).

---

## Objetivos de aprendizaje

- Distinguir contenedor de máquina virtual: namespaces, cgroups, union filesystem.
- Escribir un `Dockerfile` multi-stage que minimice tamaño y superficie de ataque.
- Redactar un `compose.yaml` de nivel producción con las 6 prácticas no negociables.
- Operar el CLI de Docker con fluidez: ciclo de vida, imágenes, redes, volúmenes.
- Diagnosticar un stack de Compose que no arranca: logs, `inspect`, healthchecks.
- Distinguir el estado real del runtime en el nodo del que reporta `kubectl get nodes`.

---

## Agenda

| Tema | Contenido |
|---|---|
| Fundamentos | Qué es realmente un contenedor: namespaces, cgroups, union FS |
| Construir imágenes | `Dockerfile`, multi-stage, imágenes distroless, arquitectura interna |
| Compose en producción | Las 6 prácticas no negociables |
| Operación diaria | CLI de Docker, cgroups, diagnóstico |
| Puente al CKA | Visibilidad del runtime, permisos de Docker |

### Las 6 prácticas no negociables de Compose

1. Secretos por archivo, nunca en variables de entorno en claro
2. Arranque condicionado a healthcheck (`depends_on: condition: service_healthy`)
3. Redes con nombre explícito
4. Volúmenes con nombre explícito
5. `cap_drop: [ALL]` y capacidades añadidas una por una
6. `security_opt: no-new-privileges:true`

---

## Laboratorio en clase — runtimes y virtualización

Antes de este laboratorio de Compose, en clase se hace
[`laboratorio-virtualizacion-contenedores.md`](./laboratorio-virtualizacion-contenedores.md)
— 75-90 minutos, en vivo: namespaces/cgroups compartidos, contenedor de sistema (LXC/LXD)
vs contenedor de aplicación (Docker), máquina virtual ligera, y por qué el tamaño de una
imagen y el usuario del proceso son decisiones de seguridad medibles, no solo de buenas
prácticas. Es un laboratorio distinto de este; los dos son complementarios.

## Laboratorio

**Dockerfile multi-stage y Compose de producción** — 60 minutos, 7 pasos:

1. Build multi-stage de una app Go hacia una imagen `distroless`
2. `compose.yaml` sin clave `version:`, validado con `docker compose config`
3. Secretos por archivo (`POSTGRES_PASSWORD_FILE`)
4. `depends_on` con `condition: service_healthy`
5. Red y volumen con nombre explícito
6. Hardening: `cap_drop: [ALL]`, `no-new-privileges:true`
7. Comprobar que pertenecer al grupo `docker` equivale a ser root en el host

**Herramientas:** Docker Engine y CLI, Docker Compose v2, Podman, Trivy,
`containerd`, imágenes distroless.

---

## Entregable de producto: PVB + PRD

> **Ambos se entregan hoy, sábado 15 de agosto de 2026.** El trabajo se hace durante la
> semana posterior al módulo 2; esta carpeta contiene las herramientas y el caso de
> referencia que necesitas para hacerlo.

Tu `pvb.md` (módulo 2) y tu `prd.md` co-creado con IA, segmento por segmento.

### Cómo está organizada esta carpeta

```
modulo3/
├── laboratorio-virtualizacion-contenedores.md  ← lab en clase (OCI/LXC/LXD/Docker)
├── docs/      ← INPUTS: lo que alimenta la especificación
├── specs/     ← OUTPUTS: lo que produces (tu prd.md va aquí)
├── research/  ← los reportes de investigación crudos y sus auditorías
└── prompts-para-especificacion.md
```

**`docs/`** trae el caso de referencia completo (**Timonel**), para que veas la
profundidad esperada. Reemplázalos por los tuyos:

| Archivo | Qué es |
|---|---|
| `docs/pvb.md` | Product Vision Board del caso |
| `docs/overview.md` | Panorama del dominio, con fuentes |
| `docs/mercado.md` | Análisis de mercado y competencia |
| `docs/icp.md` | Perfil de cliente ideal y buyer personas |
| `docs/critica.md` | Investigación adversarial: por qué la idea podría fracasar |

Puedes añadir todos los archivos que tengas: transcripciones de entrevistas, benchmarks,
notas de campo. Todos se adjuntan al prompt.

Lee `docs/critica.md` con especial atención. Es lo que separa un PVB de tarea de un PVB
defendible. Y lee [`research/README.md`](./research/README.md): documenta cómo un reporte
de deep research llegó con cifras inventadas, autocitadas y con la dirección del dato
invertida. **Ese es el fallo que el proceso de este módulo existe para prevenir.**

### El proceso

1. Reemplaza los archivos de `docs/` por los de tu producto.
2. Abre [`prompts-para-especificacion.md`](./prompts-para-especificacion.md) y copia el
   **Prompt 1**.
3. Pégalo en una conversación nueva y adjunta **todos** los archivos de tu `docs/`.
4. La IA empieza por un **análisis de conflictos** entre tus documentos. Decide tú cada
   conflicto antes de avanzar.
5. Co-crea **segmento por segmento**. No apruebes en bloque.
6. Consolida el resultado en `specs/prd.md`.

### La patología conocida del PRD

Cada sesión con el agente abre direcciones nuevas y el alcance crece sin que nadie haya
decidido que creciera. La salida no es más disciplina personal — es volver al tablero y
hacer **una sola pregunta de corte**:

> ¿esto sigue siendo el producto que quiero construir?

La técnica concreta: dale al agente el PVB y el PRD **juntos** y pídele que señale
conflictos y desalineaciones, **no que decida por ti**. El PRD está terminado cuando no
le falta ni le sobra nada respecto de la visión.

> **Por qué segmento por segmento.** Es la misma regla del módulo 8 —*el agente propone,
> el humano aprueba*— aplicada a escribir especificaciones en vez de a operar un clúster.
> Si dejas que la IA produzca el PRD completo de una vez y lo apruebas en bloque, ya
> perdiste el control del alcance, y eso se nota en la sustentación.

---

## Cómo conecta con el resto del curso

- **Módulo 4 en adelante:** Kubernetes no construye imágenes; orquesta las que aquí
  aprendes a construir.
- **Módulo 5 (CKA):** el dominio de troubleshooting pesa 30%, y el runtime del nodo
  es el primer lugar donde se mira.
- **Módulo 7 (CKS):** la cadena de suministro de software pesa 20%, y empieza en el
  `Dockerfile`.
