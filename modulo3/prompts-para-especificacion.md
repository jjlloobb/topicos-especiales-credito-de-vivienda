# Prompts para co-crear la especificación de tu producto

**Módulo 3 — Tópicos Especiales en Informática**

> [!NOTE]
> Cada prompt se ejecuta **secuencialmente**, en conversaciones separadas. El output de
> uno alimenta al siguiente. Esta semana solo ejecutas el **Prompt 1**.

> [!IMPORTANT]
> **Modo de trabajo: co-creación iterativa.** Estos prompts **no** le piden a la IA que
> genere todo de una vez. Cada uno la instruye a producir **un segmento a la vez**,
> detenerse, y esperar tu revisión antes de avanzar.
>
> Esto no es un capricho de formato: es la práctica que el curso evalúa. **El agente
> propone, tú apruebas.** Es la misma regla que gobierna el módulo 8, aplicada a la
> escritura de especificaciones en vez de a la operación del clúster.

---

## Convención de carpetas

```
modulo3/
├── docs/          ← INPUTS: todo lo que alimenta la especificación
│   ├── pvb.md            ← tu Product Vision Board del módulo 2
│   ├── overview.md       ← panorama del dominio
│   ├── mercado.md        ← análisis de mercado y competencia
│   ├── icp.md            ← perfil de cliente ideal
│   ├── critica.md        ← investigación adversarial
│   └── ...               ← transcripciones, benchmarks, notas de campo
│
├── specs/         ← OUTPUTS: lo que producen estos prompts
│   ├── prd.md            ← Prompt 1  (entregable de este módulo)
│   ├── arquitectura.md   ← Prompt 2  (más adelante)
│   └── backlog.md        ← Prompt 3  (más adelante)
│
├── research/      ← el reporte de investigación crudo y su auditoría
└── prompts-para-especificacion.md   ← este archivo
```

> [!TIP]
> **Markdown, no PDF.** Gastas menos tokens y el modelo lo lee mejor.
>
> Los archivos que hoy están en `docs/` son el **caso de referencia (Timonel)**.
> Reemplázalos por los tuyos manteniendo ese nivel de profundidad.

---

## Antes de empezar: la regla de evidencia

Tu PRD va a heredar todo lo que esté mal en tus `docs/`. Por eso, antes de ejecutar el
Prompt 1:

- Revisa que cada cifra de tus documentos tenga **fuente verificable**.
- Marca tus proyecciones internas como **[INTERNO]** y las afirmaciones sobre el mundo
  real sin verificar como **[VERIFICAR]**.
- Lee [`research/README.md`](./research/README.md) — documenta cómo un reporte de deep
  research generado con IA llegó con cifras inventadas, autocitadas y con la dirección
  del dato invertida. **Ese es el fallo que estos prompts intentan prevenir.**

---

## Prompt 1 — PRD: visión, propuesta de valor y especificación funcional

Cópialo completo en una conversación nueva y adjunta **todos** los archivos de tu `docs/`.

```text
Actúa como Head of Product + Platform/Cloud-Native Architect.

Voy a construir un producto que corre sobre Kubernetes y usa IA de forma central. Te
adjunto todos los documentos de mi carpeta docs/: Product Vision Board, panorama del
dominio, análisis de mercado, perfil de cliente ideal, investigación de crítica, y
cualquier transcripción, benchmark o nota de campo adicional.

═══════════════════════════════════════════════
REGLAS
═══════════════════════════════════════════════
1. NO inventes datos. Si falta algo, escribe TBD y propón 2-3 opciones razonables.
2. NO inventes cifras de mercado, precios, ni nombres de empresas o productos reales.
3. Cuando cites una cifra de mis docs, respeta su etiqueta: [INTERNO] es una proyección
   mía, [VERIFICAR] es una afirmación sin fuente confirmada. Nunca conviertas un
   [VERIFICAR] en un hecho.
4. Si una cifra de mis docs no tiene fuente, señálalo en vez de usarla como si la tuviera.
5. Extrae textualmente de mis docs cuando sea clave, sin excederte.
6. Señala las decisiones críticas y sus trade-offs en recuadros de alerta.
7. Usa diagramas Mermaid donde aporten.

═══════════════════════════════════════════════
MODO DE TRABAJO: CO-CREACIÓN ITERATIVA
═══════════════════════════════════════════════
NO produzcas todos los entregables de una vez.
Trabaja SEGMENTO POR SEGMENTO, en el orden listado abajo.

Para cada segmento:
1. Produce el contenido del segmento.
2. Explica las decisiones que tomaste y por qué.
3. Cita qué documento mío influyó en lo que escribiste.
4. Detente y pregunta: "¿Apruebas este segmento, tienes ajustes, o quieres explorar otra
   dirección?"
5. Avanza solo cuando yo lo indique.

Al terminar todos los segmentos, consolida el documento completo. Se guardará como
specs/prd.md.

═══════════════════════════════════════════════
PASO 0 — ANÁLISIS DE CONFLICTOS (OBLIGATORIO, ANTES DE TODO)
═══════════════════════════════════════════════
Antes de producir cualquier entregable, cruza TODOS mis documentos y busca:

1. Contradicciones de datos: cifras o afirmaciones que se contradigan entre documentos.
2. Conflictos de posicionamiento: diferencias en cómo se define al usuario, al problema
   o al producto.
3. Tensión entre la investigación de validación y la de crítica: dónde el documento
   crítico desmiente algo que el PVB da por bueno. Esta tensión es la más importante y
   NO debe resolverse a favor del optimismo por defecto.
4. Supuestos incompatibles: premisas que un documento asume y otro contradice.
5. Vacíos críticos: información necesaria para decidir que ningún documento provee.

Preséntalo así:

| # | Tipo de conflicto | Doc A dice... | Doc B dice... | Decisión requerida |
|---|-------------------|---------------|---------------|--------------------|

Propón una recomendación para cada uno, pero ESPERA MI DECISIÓN antes de continuar.
Estas decisiones moldean todo el PRD.

═══════════════════════════════════════════════
SEGMENTOS DEL PRD (uno a la vez)
═══════════════════════════════════════════════

### Segmento 1. One-liner + Job to be Done
- Una frase de producto (máx. 2 oraciones).
- JTBD: "Cuando [situación], quiero [motivación], para [resultado esperado]".
- Misión del producto (máx. 3 oraciones).

### Segmento 2. Contexto y problema
- Dolores del mercado, con los datos duros de mis docs y su fuente.
- ¿Por qué ahora? Tendencias o movimientos que crean urgencia.
- Alternativas actuales: qué usa hoy mi ICP y por qué no le alcanza.
- Incluye explícitamente qué parte del problema YA está resuelta gratis por proyectos
  open source o del ecosistema CNCF. Si mi producto compite con algo gratuito, dilo.

### Segmento 3. ICP detallado
- Perfil y firmographics (tamaño de equipo, sector, geografía, madurez en Kubernetes).
- Buyer personas y quién tiene el veto de confianza.
- Pains, con referencia directa a mis docs.
- Triggers de compra.
- Objeciones probables y cómo responderlas.

### Segmento 4. Propuesta de valor única y diferenciadores
- Qué problema resuelve, para quién, cómo.
- Diferenciación frente a los competidores de mis docs, incluidos los gratuitos.
- Qué brecha real llena.
- Matriz de posicionamiento 2x2 (Mermaid quadrantChart) con los ejes más relevantes del
  dominio, ubicando competidores y el producto propuesto.

### Segmento 5. Casos de uso (top 5)
Para cada uno: actor, trigger, 3-5 pasos del flujo, resultado esperado, KPI impactado.

### Segmento 6. Principios de diseño no negociables
Extrae de mis docs los principios que el producto no puede violar. Para cada uno:
(a) qué significa operativamente, (b) cómo se manifiesta en el producto, (c) qué queda
explícitamente PROHIBIDO.

Si mi producto incluye agentes que actúan sobre infraestructura, uno de los principios
DEBE ser el límite de autonomía: qué puede hacer el agente sin aprobación humana y qué
no. Expresa ese límite de forma verificable, no como promesa.

### Segmento 7. User journeys
En detalle narrativo, con pasos numerados:
1. Happy path del usuario final.
2. Happy path del operador/administrador.
3. Edge case: el flujo se interrumpe o el usuario abandona.
4. Edge case: el sistema (o el agente) no puede resolver la tarea y debe escalar a un
   humano. Describe cómo se entrega el contexto en ese traspaso.

### Segmento 8. Alcance del MVP (MoSCoW)
Must / Should / Could / Won't have, con el porqué de cada exclusión.
Restricción real: el MVP debe ser construible en lo que queda del semestre y desplegable
en Kubernetes en el módulo 8.

### Segmento 9. Especificación funcional: módulos y features
Módulos funcionales del sistema. Para cada uno: features principales, roles y permisos,
pantallas o flujos que lo exponen. Incluye un diagrama Mermaid de la arquitectura
funcional de alto nivel.

Indica qué componentes corren como cargas de trabajo en Kubernetes y cuáles son
servicios externos.

### Segmento 10. Métricas de éxito
- 1 métrica North Star.
- KPIs de activación, retención y calidad, cada uno con baseline (si mis docs lo dan) y
  meta.
- Métricas específicas de la IA: precisión, utilidad, seguridad.
- Al menos UNA métrica que detecte el fallo por ruido: el escenario en que el sistema
  produce mucho output de baja calidad y el usuario deja de prestarle atención.

### Segmento 11. Plan de evaluación de la IA
- Dataset inicial para evaluar antes de lanzar.
- Criterios de calidad: factualidad, adherencia a instrucciones, relevancia.
- Cómo se revisan los outputs.
- Red-teaming: escenarios adversariales. Si el sistema lee datos que un tercero puede
  influir (logs, tickets, contenido de usuarios), incluye inyección indirecta de prompts.

### Segmento 12. Riesgos y mitigaciones
Tabla con los 10 riesgos principales (técnicos, de seguridad, legales, de producto, de
mercado), cada uno con probabilidad, impacto y plan de mitigación específico.

Incluye obligatoriamente:
- Riesgo de comoditización por proyectos open source.
- Riesgo de que la IA produzca un output equivocado que alguien apruebe por confianza.

### Segmento 13. Plan de entrega alineado al curso
- Módulos 4-5 (Kubernetes y CKA): qué se construye y qué se valida.
- Módulo 6 (CKAD): qué se despliega.
- Módulo 7 (CKS): qué se asegura.
- Módulo 8 (producción): qué queda corriendo con GitOps y qué se mide.
- Sesión 16: qué se demuestra en la sustentación.

═══════════════════════════════════════════════
EMPIEZA POR EL PASO 0
═══════════════════════════════════════════════
Analiza mis documentos, presenta los conflictos, y espera mis decisiones antes del
Segmento 1.

═══════════════════════════════════════════════
MIS DOCUMENTOS
═══════════════════════════════════════════════

[ADJUNTA AQUÍ TODOS LOS ARCHIVOS DE TU CARPETA docs/]
```

---

## Prompt 2 — Arquitectura técnica

> [!WARNING]
> **No ejecutes este prompt esta semana.** Lo vas a usar cuando tengas los módulos de
> Kubernetes encima. Requiere un `specs/prd.md` aprobado.

```text
Actúa como Cloud-Native Architect.

Te adjunto mi PRD aprobado (specs/prd.md) y los documentos de docs/.

Mismas reglas que antes: no inventes datos, trabaja SEGMENTO POR SEGMENTO, detente
después de cada uno y espera mi aprobación.

Produce una arquitectura técnica que cubra:

1. Diagrama de componentes (Mermaid) y responsabilidad de cada uno.
2. Qué corre dentro del clúster y qué fuera, con la justificación.
3. Modelo de despliegue: namespaces, Deployments/StatefulSets, Services, Ingress.
4. Estrategia de configuración y secretos (nunca en la imagen; cómo se cifran en Git).
5. Modelo de permisos: ServiceAccounts y RBAC de cada componente, con el principio de
   mínimo privilegio explícito. Si hay un agente de IA, muestra el RBAC que lo limita y
   cómo se verifica con `kubectl auth can-i`.
6. Estrategia de datos: persistencia, respaldos, PVCs y StorageClass.
7. Observabilidad: qué métricas, logs y trazas se emiten y quién los consume.
8. Políticas de admisión que el sistema debe cumplir.
9. Flujo GitOps: qué repositorio, qué reconcilia Argo CD o Flux, cómo se hace rollback.
10. Decisiones de arquitectura en formato ADR: contexto, opciones evaluadas, decisión,
    consecuencias. Una ADR por decisión estructural.

El documento final se guardará como specs/arquitectura.md.
```

---

## Prompt 3 — Backlog de ingeniería

> [!WARNING]
> **No lo ejecutes todavía.** Requiere `specs/prd.md` y `specs/arquitectura.md`.

```text
Actúa como Tech Lead.

Te adjunto specs/prd.md y specs/arquitectura.md.

Mismas reglas: no inventes, segmento por segmento, espera mi aprobación.

Produce un backlog ejecutable:

1. Épicas derivadas de los módulos funcionales del PRD.
2. Para cada épica, historias de usuario con criterios de aceptación verificables
   (verificable = se puede comprobar con un comando o una prueba, no con una opinión).
3. Dependencias entre historias y el orden en que deben ejecutarse.
4. Para cada historia: qué evidencia demuestra que quedó terminada.
5. Agrupación por módulo del curso, de modo que el backlog avance junto con las clases.
6. Identificación de las historias del camino crítico hacia la sustentación final.

El documento final se guardará como specs/backlog.md.
```

---

## Cuándo usar cada prompt

| Prompt | Cuándo | Output |
|---|---|---|
| **1 — PRD** | Ahora. Se entrega el sábado 15 de agosto de 2026, junto con el PVB | `specs/prd.md` |
| **2 — Arquitectura** | Cuando tengas Kubernetes y CKA encima | `specs/arquitectura.md` |
| **3 — Backlog** | Antes de empezar a construir en serio | `specs/backlog.md` |

Concéntrate en un `prd.md` sólido. Un PRD flojo se arrastra hasta la sustentación.

---

## Si la IA no respeta el "segmento por segmento"

Es la frustración número uno del ejercicio. Tres salidas, en orden:

1. **Dilo explícitamente:** "Detente. No avancemos. Vamos segmento por segmento y espera
   mi aprobación."
2. **Sube de modelo.** Los modelos más capaces siguen mejor las instrucciones de proceso.
3. **Empieza una sesión nueva** con el prompt limpio. Una conversación que ya se desbordó
   tiende a seguir desbordándose.

Y si aun así se adelanta y produce cinco segmentos de una: **no los apruebes en bloque**.
Revísalos uno por uno o pídele que rehaga desde el primero que no revisaste. Aprobar en
bloque es exactamente el hábito que este ejercicio existe para desarmar.
