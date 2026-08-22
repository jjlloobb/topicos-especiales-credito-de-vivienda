# Panorama del dominio: agentes de IA operando Kubernetes

> Documento de contexto para el caso de estudio **Timonel**.
> Toda cifra de este documento pasó por [`research/deep-research-ai-k8s-cncf.AUDIT.md`](../research/deep-research-ai-k8s-cncf.AUDIT.md).
> Lo que no se pudo verificar contra fuente primaria **no está aquí**.

---

## 1. Por qué ahora

La categoría "agentes de IA que operan infraestructura cloud-native" dejó de ser una
demo de conferencia y entró al ecosistema formal de la CNCF en el lapso de unos 18 meses.
No es una predicción: son proyectos aceptados, con fecha.

El movimiento va en dos direcciones a la vez:

- **Desde abajo**, proyectos open source que se incorporan a la CNCF (kagent, K8sGPT,
  HolmesGPT).
- **Desde arriba**, plataformas comerciales que levantan capital para reposicionarse
  como "agénticas" (Port.io).

---

## 2. Los proyectos open source y su estado real en la CNCF

Presta atención al **nivel de madurez**: Sandbox, Incubating y Graduated no son
etiquetas de marketing, son etapas con requisitos distintos de gobernanza, adopción y
seguridad. Es contenido evaluable en KCNA.

| Proyecto | Nivel CNCF | Fecha | Qué hace |
|---|---|---|---|
| **kagent** | Sandbox | 22 may 2025 | Framework para ejecutar agentes como cargas de trabajo de Kubernetes, vía CRDs e integración con MCP |
| **K8sGPT** | Sandbox | aceptado 19 dic 2023 | Escanea el clúster, interpreta recursos en fallo y explica el error en lenguaje natural |
| **HolmesGPT** | Sandbox | 8 oct 2025 | Investigación de incidentes; consulta herramientas de observabilidad en bucles de razonamiento |
| **Backstage** | **Incubating** | Incubating desde 15 mar 2022 | Portal interno de desarrolladores y catálogo de servicios |
| **Crossplane** | Graduated | 28 oct 2025 | Plano de control: gestiona infraestructura externa como recursos de Kubernetes |
| **Flux** | Graduated | 30 nov 2022 | GitOps: reconcilia el clúster contra un repositorio Git |
| **Argo CD** | Graduated | 6 dic 2022 | GitOps: entrega continua declarativa |
| **Kyverno** | Graduated | 16 mar 2026 | Políticas de admisión como código |

> **Ojo con una confusión frecuente:** Backstage **no está graduado**. Es el portal de
> desarrolladores más conocido del ecosistema y aun así permanece en Incubating.
> Popularidad y madurez formal no son lo mismo — y esa distinción es justamente lo que
> la escala de la CNCF intenta capturar.

**Datos de los tres agentes:**

- **kagent** fue creado por gente de Solo.io vinculada a los orígenes de Istio (Idit
  Levine y Lin Sun). Ronda las 3.500 estrellas en GitHub y ~3.158 colaboradores
  registrados en LFX.
- **HolmesGPT** es co-mantenido por **Robusta y Microsoft**, licencia Apache 2.0, ~3.000
  estrellas. Diseñado con acceso de **solo lectura**, respetando el RBAC existente.
- **K8sGPT** es el más veterano de los tres y sigue en Sandbox tras más de dos años.

El dato de que HolmesGPT sea deliberadamente de solo lectura no es un detalle menor:
**es la misma decisión de diseño que sostiene el caso Timonel**, y la toma un proyecto
respaldado por Microsoft.

---

## 3. El dinero: qué se está financiando

| Empresa | Hecho verificado |
|---|---|
| **Port.io** | Serie C de **$100M el 11 de diciembre de 2025**, liderada por General Atlantic con Accel, Bessemer Venture Partners y Team8. Valoración de **$800M**, **$158M** acumulados. Se reposicionó como plataforma "agentic SDLC" |
| **Kubiya.ai** | **$12M** acumulados, incluida una extensión de $6M en agosto de 2024 liderada por Heavybit. Automatización agéntica de DevOps vía Slack/Teams |
| **StackGen** | Antes se llamaba **appCD**. Adquirió **OpsVerse en agosto de 2025** |
| **Facets.cloud** | Ingresos de **₹11,4 Cr** en el año fiscal cerrado en marzo de 2025. Reconocida en el *Market Guide for Infrastructure Automation & Orchestration* de Gartner y en el Hype Cycle de SRE |
| **Humanitec** | Orquestador de plataforma basado en la especificación abierta *Score*. Enfoque declarativo: evita ejecutar modelos estocásticos sobre infraestructura de producción |

La lectura relevante: **el capital grande no está entrando a "agente que arregla tu
clúster"**. Está entrando a *portales y catálogos* que después se reposicionan como
agénticos. Port.io levantó $100M siendo un portal de desarrolladores, no un agente de
remediación.

---

## 4. Lo que hacen los hyperscalers

Los tres grandes ya tienen respuesta, y todas comparten una característica: **atan el
valor a su propia nube**.

- **AWS** combina Amazon Bedrock con EKS, apoyándose en el propio K8sGPT open source.
- **Google Cloud** integra Gemini Cloud Assist directamente en la consola de GKE.
- **Microsoft** co-mantiene HolmesGPT y promueve su Azure SRE Agent sobre AKS.

Ninguno resuelve el escenario multinube ni on-premise, que es donde queda espacio.

---

## 5. La tensión central de la categoría

Esta es la formulación más útil que produjo la investigación. **Es un argumento, no un
dato** — el propio reporte la etiquetó como especulativa, y así hay que presentarla:

> El mercado se parte en dos extremos, y ninguno es satisfactorio:
>
> 1. **Agentes de solo lectura** (K8sGPT, HolmesGPT): diagnostican bien, pero devuelven
>    todo el trabajo de ejecución al humano. El *toil* no desaparece, se desplaza.
> 2. **Agentes con permiso de mutación**: ejecutan, pero **no pueden garantizar de forma
>    determinista** el efecto de una acción sobre una topología distribuida. Una
>    remediación en un microservicio puede desencadenar fallas en cascada aguas abajo.

El hueco es el puente entre ambos: ejecución con garantía. Ese puente es exactamente lo
que propone Timonel — y también es la tesis del **módulo 8**: el agente propone, el
humano aprueba, GitOps reconcilia.

Es importante que veas que **esto es una hipótesis, no un hecho de mercado**. Que la
formulación sea elegante no la hace cierta. Validarla o refutarla es trabajo tuyo.

---

## 6. Contexto macro (cifras de Gartner verificadas)

- **80%** de las grandes organizaciones de ingeniería de software tendrán equipos de
  platform engineering para **2026**, frente al 45% en 2022.
- **60%** de las organizaciones adoptarán equipos pequeños (2-5 personas) apoyados en
  plataformas y agentes de IA para **2029**, frente al 15% en 2026.
- El gasto mundial en servicios de nube pública alcanzaría **$723.000M en 2025**.
- El gasto mundial en IA totalizaría **~$2,59 billones en 2026**.

Y la que hay que leer junto a las anteriores, no después:

- **Más del 40% de los proyectos de IA agéntica empresariales serán cancelados para
  finales de 2027** (Gartner, junio de 2025), por falta de ROI demostrable, costos de
  inferencia crecientes y complejidad de gobernanza.

Esa última cifra no contradice a las otras: las acompaña. El mercado crece **y** la
mayoría de los proyectos agénticos concretos fracasa. Ambas cosas son ciertas a la vez,
y un análisis que solo cite las primeras cuatro está vendiendo, no analizando.

---

## 7. Qué NO se pudo verificar

Registrado a propósito, porque saber qué no sabes es parte del análisis:

- Que Kyverno supere los **3.000 millones de descargas**: no aparece en la fuente
  primaria de la CNCF.
- Cifras de adopción de plataformas **AIOps** (el supuesto salto de 30% en 2021 a 65%
  en 2025): no existe nota de prensa de Gartner que las respalde.
- Que la automatización con IA reduzca **30% los costos operativos de TI**: el propio
  Gartner apunta luego en dirección contraria para el costo por resolución con GenAI.

---

*Material de referencia — Tópicos Especiales en Informática*
