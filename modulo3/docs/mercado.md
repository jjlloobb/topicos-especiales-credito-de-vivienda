# Análisis de mercado — plataformas y agentes de IA sobre Kubernetes

> Documento de contexto para el caso de estudio **Timonel**.
> Cada cifra de aquí está confirmada contra fuente primaria en
> [`research/deep-research-ai-k8s-cncf.AUDIT.md`](../research/deep-research-ai-k8s-cncf.AUDIT.md).

---

## 1. El mercado que se cita cuando se quiere convencer

Estas son las cifras que aparecen en toda presentación de la categoría. Son reales y
están verificadas contra notas de prensa de Gartner:

| Cifra | Valor | Horizonte |
|---|---|---|
| Grandes organizaciones con equipos de platform engineering | **80%** (vs 45% en 2022) | 2026 |
| Organizaciones con equipos pequeños (2-5 personas) apoyados en plataformas y agentes | **60%** (vs 15% en 2026) | 2029 |
| Gasto mundial en servicios de nube pública | **$723.000M** | 2025 |
| Gasto mundial en IA | **~$2,59 billones** | 2026 |

Todas apuntan en la misma dirección: hay dinero, hay equipos y hay mandato
organizacional. Es el tipo de tabla con la que se levanta una ronda.

---

## 2. La cifra que hay que poner en la misma diapositiva

> **Más del 40% de los proyectos de IA agéntica empresariales serán cancelados para
> finales de 2027.**
> Gartner, nota de prensa del 25 de junio de 2025. Razones citadas: ROI no demostrable,
> costos crecientes de inferencia y complejidad de gobernanza.

Esto **no** contradice la sección anterior. Las dos cosas son ciertas simultáneamente:

- El mercado de plataformas crece y se consolida.
- La mayoría de los proyectos agénticos concretos que se lanzan dentro de ese mercado
  fracasa.

**Implicación para Timonel:** el riesgo dominante no es que no haya mercado. Es
pertenecer al 40% que se cancela. Y las tres razones que da Gartner son precisamente las
que el diseño del producto debe atacar de frente:

| Razón de cancelación (Gartner) | Respuesta de diseño |
|---|---|
| ROI no demostrable | Una métrica única y medible desde el primer mes: % de PRs del agente aprobados sin modificación |
| Costos de inferencia crecientes | Filtrado previo del ruido con modelos baratos; el modelo caro solo entra al diagnóstico que llegó |
| Complejidad de gobernanza | El agente no tiene permisos de escritura; la gobernanza es el RBAC y el flujo de PR que el cliente **ya** tiene |

---

## 3. Estructura competitiva

### Capa gratuita (la que define el precio de todo lo demás)

Proyectos CNCF, sin costo de licencia, que ya cubren buena parte del valor:

- **K8sGPT** (Sandbox) — diagnóstico e interpretación de recursos en fallo.
- **HolmesGPT** (Sandbox, co-mantenido por Robusta y **Microsoft**) — investigación de
  incidentes contra herramientas de observabilidad, **de solo lectura por diseño**.
- **kagent** (Sandbox, creado por gente de Solo.io de la órbita de Istio) — framework
  para correr agentes como cargas de trabajo del clúster.
- **Argo CD** y **Flux** (Graduated) — la reconciliación GitOps.
- **Kyverno** (Graduated, marzo de 2026) — políticas de admisión.
- **Crossplane** (Graduated, octubre de 2025) — infraestructura como API de Kubernetes.

> **Este es el hecho competitivo más importante del análisis.** Cualquier producto
> comercial de la categoría tiene que justificar por qué alguien pagaría por algo cuyo
> 70% ya existe gratis, mantenido por la CNCF y respaldado por Microsoft.

### Capa de los hyperscalers

- **AWS:** Bedrock + EKS, apoyado en el propio K8sGPT open source.
- **Google Cloud:** Gemini Cloud Assist embebido en la consola de GKE.
- **Microsoft:** Azure SRE Agent sobre AKS, y co-mantenimiento de HolmesGPT.

Todos comparten la misma limitación estructural: **atan el valor a su nube**. Ninguno
sirve bien a un entorno multinube o con presencia on-premise.

### Capa comercial

| Empresa | Posición | Señal financiera verificada |
|---|---|---|
| **Port.io** | Portal de desarrolladores reposicionado como plataforma "agentic SDLC" | Serie C de **$100M** (11 dic 2025), valoración **$800M**, $158M acumulados |
| **Kubiya.ai** | Automatización agéntica de DevOps vía Slack/Teams | **$12M** acumulados |
| **StackGen** (antes appCD) | Infraestructura autónoma | Adquirió OpsVerse en agosto de 2025 |
| **Humanitec** | Orquestación declarativa con la especificación *Score* | Evita deliberadamente ejecutar modelos estocásticos sobre producción |
| **Facets.cloud** | Automatización de infraestructura | ₹11,4 Cr de ingresos (FY mar 2025); citada en Gartner |

**Lectura del capital:** los $100M de Port.io no fueron a un agente de remediación —
fueron a un **portal y catálogo** que luego se reposicionó como agéntico. El dinero
grande está comprando *contexto y catálogo*, no *autonomía*.

Y el caso de **Humanitec** merece atención especial: una empresa consolidada de la
categoría **decidió explícitamente no ejecutar modelos estocásticos sobre infraestructura
de producción**. Eso no es timidez tecnológica; es una lectura del riesgo que coincide
con la de HolmesGPT y con la de Timonel.

---

## 4. Dónde queda el espacio

Cruzando las tres capas, el hueco defendible es estrecho y concreto:

1. **Multinube y on-premise** — donde los hyperscalers no llegan por diseño de negocio.
2. **El puente entre diagnóstico y ejecución** — donde los proyectos gratuitos se
   detienen deliberadamente (HolmesGPT es de solo lectura *a propósito*).
3. **El registro auditable de decisiones** — que no es un algoritmo replicable sino un
   activo que se acumula operando.

**Lo que NO es espacio defendible:** el diagnóstico. Está resuelto, es gratis y lo
mantiene la CNCF con respaldo de Microsoft. Un producto que venda diagnóstico compite
contra cero.

---

## 5. El dolor operativo, con datos que resistieron la auditoría

De diez estadísticas de dolor operativo que traía la investigación, **cuatro
sobrevivieron**. Estas son:

**Kubernetes ya es donde vive la IA.**
El 66% de las organizaciones que alojan modelos de IA generativa usan Kubernetes para
gestionar parte o toda su carga de inferencia (CNCF Annual Survey, publicada el 20 de
enero de 2026). El título del anuncio de la CNCF lo dice sin rodeos: Kubernetes quedó
establecido como el "sistema operativo de facto" para IA.

**La brecha entre equipos es enorme y está medida.**
Según el informe DORA 2024, los equipos *elite* (19% de los encuestados) despliegan bajo
demanda, con lead time menor a un día, tasa de fallas en cambios del 5% y recuperación en
menos de una hora. Los *low performers* tienen 40% de tasa de fallas y tardan de una
semana a un mes en recuperarse.

**El tiempo se va en trabajo que no es producto.**
El 70% de los encuestados reporta que sus desarrolladores dedican 3-4 horas diarias a
tareas no centrales (*State of Internal Developer Portals 2024*, Port.io).
⚠️ **Léela con cuidado:** la muestra son 100 líderes de ingeniería, la metodología no está
publicada, y **Port.io vende productos de este mismo mercado**. Es una cifra de vendor.
Sirve como indicio, no como medida.

### Y el dato incómodo, que es el más importante

> **La adopción de IA se asocia con peor estabilidad de las entregas.**
>
> DORA 2024 estima una **reducción del 7,2% en estabilidad** (y del 1,5% en throughput)
> asociada a la adopción de IA. DORA 2025 reformula el hallazgo —la IA ya correlaciona
> positivamente con throughput— pero **la correlación negativa con la estabilidad
> persiste**.

Faros AI apunta en la misma dirección: comparando equipos de baja contra alta adopción de
IA, el tiempo mediano de revisión de pull requests sube **441,5%** y la probabilidad de
que un PR fusionado cause un incidente **se triplica**.
⚠️ Son comparaciones **entre cohortes**, no variaciones en el tiempo. Y correlación no es
causalidad: puede que los equipos que más adoptan IA sean también los que más presión de
entrega tienen.

**Por qué esto importa para Timonel más que cualquier cifra de mercado:**

La IA está generando más código, más rápido, con **más fallas de cambio**. Eso significa
que el mercado no necesita otra herramienta que produzca cambios más rápido — necesita
algo que sostenga la estabilidad mientras el volumen crece. Un producto cuya tesis es
*"el agente propone, el humano aprueba, GitOps reconcilia"* está posicionado exactamente
contra este dato.

También es una advertencia sobre el propio producto: si Timonel genera pull requests con
IA, **es parte del fenómeno que este dato describe**, no una excepción a él.

---

## 6. Riesgo geográfico y de segmento

El ICP de Timonel apunta a Colombia, México y Brasil, y ahí hay una debilidad que el
análisis debe declarar en vez de esconder:

**No encontramos datos públicos verificables sobre el tamaño del mercado de platform
engineering en Latinoamérica**, ni sobre cuántas organizaciones de la región operan
Kubernetes en producción con equipos de plataforma dedicados. Las cifras de Gartner son
globales.

Eso significa que **el supuesto geográfico del ICP no está validado con datos**. Es una
hipótesis basada en proximidad y acceso, no en tamaño de mercado medido. Es exactamente
el tipo de hueco que hay que declarar antes de que lo encuentre quien te evalúa.

---

## 7. Qué no se pudo verificar

Descartado del análisis por no resistir la auditoría:

- Cifras de adopción de plataformas **AIOps** (el supuesto salto de 30% en 2021 a 65% en
  2025): no existe nota de prensa de Gartner que las respalde.
- **Reducción del 30% en costos operativos de TI** por automatización con IA: el propio
  Gartner apunta después en dirección contraria para el costo por resolución con GenAI.
- **Backstage con 89% del mercado de portales internos**: la única fuente es el blog de
  una empresa que vende Backstage gestionado — conflicto de interés directo sobre esa
  cifra.
- **3.000 millones de descargas de Kyverno**: no aparece en la fuente primaria de la CNCF.

---

*Material de referencia — Tópicos Especiales en Informática*
