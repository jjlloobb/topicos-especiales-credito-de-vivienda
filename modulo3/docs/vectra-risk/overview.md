# Panorama del dominio: IA explicable para scoring de riesgo crediticio

> Documento de contexto para el caso de estudio **Vectra Risk**.
> Toda cifra de este documento lleva fuente y fecha, obtenida por búsqueda web el 15
> de agosto de 2026. Lo que no se pudo verificar contra una fuente confiable está
> declarado en la sección 7, no maquillado en el resto del documento.

---

## 1. Por qué ahora

La categoría "IA explicable para decisiones de crédito" no es nueva — SHAP y LIME
llevan años en la literatura académica de scoring — pero **dos cosas la volvieron
urgente en 2025-2026 al mismo tiempo**:

- **Desde la infraestructura**, el serving de modelos en Kubernetes maduró hasta
  convertirse en estándar de facto: KServe pasó de Sandbox a **CNCF Incubating** en
  noviembre de 2025 ([CNCF, 11 nov 2025](https://www.cncf.io/blog/2025/11/11/kserve-becomes-a-cncf-incubating-project/)),
  lo que significa que ya hay al menos tres organizaciones independientes
  ejecutándolo en producción — es un requisito del propio proceso de graduación de
  la CNCF ([CNCF Project Lifecycle](https://contribute.cncf.io/projects/lifecycle/)).
- **Desde el negocio**, los vendors de crédito empezaron a integrar explicabilidad
  directamente en los cores bancarios que los bancos ya usan, no como producto
  aparte: Zest AI se integró de forma nativa en Temenos Loan Origination en abril
  de 2025 ([Zest AI / Temenos, 29 abr 2025](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)).

El movimiento va en dos direcciones a la vez:

- **Desde abajo**, librerías y proyectos open source que maduran (SHAP, LIME,
  AIF360, Fairlearn, KServe).
- **Desde arriba**, plataformas comerciales de crédito que absorben esa
  explicabilidad como feature nativa en vez de vendérsela aparte al banco.

---

## 2. Los proyectos y su estado real — con una advertencia sobre la etiqueta "CNCF"

En scoring de crédito **el ecosistema está repartido entre CNCF, Linux Foundation
AI & Data, y proyectos de vendors individuales sin gobernanza de fundación**.
Confundir estas categorías sería un error de gobernanza: popularidad y madurez
formal no son lo mismo, y hay que distinguirlas con cuidado antes de presentar algo
como "proyecto CNCF" sin serlo.

| Proyecto / librería | Gobernanza real | Estado | Qué hace |
|---|---|---|---|
| **KServe** | **CNCF** | Incubating desde nov 2025 (promovido de Sandbox) | Serving de modelos en Kubernetes vía la CRD `InferenceService` ([Spheron, 28 may 2026](https://www.spheron.network/blog/kserve-vs-seldon-core-vs-bentoml-kubernetes-ml-serving-guide/)) |
| **Kubeflow** | **Linux Foundation AI & Data**, no CNCF | Aplicó a CNCF Incubating en 2022; **no encontré confirmación de que la transferencia se haya completado** | Plataforma end-to-end de MLOps sobre Kubernetes ([Kubeflow blog, 2022](https://blog.kubeflow.org/kubeflow-applied-cncf-incubating/)) — **[VERIFICAR estado actual directamente en cncf.io/projects antes de citarlo como proyecto CNCF]** |
| **Seldon Core v2** | Propietario de Seldon (empresa), **no es un proyecto CNCF** | Producto open source de un vendor, no gobernanza de fundación | Orquestación de pipelines de inferencia multi-paso (ruteo, transformación, explicación, monitoreo) ([Spheron, 28 may 2026](https://www.spheron.network/blog/kserve-vs-seldon-core-vs-bentoml-kubernetes-ml-serving-guide/)) |
| **AI Fairness 360 (AIF360)** | IBM, no CNCF | Open source, mantenido por IBM | +70 métricas de sesgo, 9 algoritmos de mitigación ([AIF360](https://aif360.res.ibm.com/)) |
| **Fairlearn** | Microsoft, no CNCF | Open source, mantenido por Microsoft | Toolkit de fairness comparable a AIF360 ([arXiv 2205.06922](https://arxiv.org/pdf/2205.06922)) |
| **SHAP / LIME** | Proyectos académicos/comunitarios independientes | Librerías Python maduras, sin gobernanza de fundación | Explicabilidad post-hoc por decisión ([arXiv 2103.00949](https://arxiv.org/pdf/2103.00949)) |

**La distinción importa para el argumento de Vectra Risk:** solo KServe tiene el
tipo de gobernanza multi-organización, auditoría de seguridad y proceso de
graduación que ofrece garantías de continuidad a largo plazo. El resto son
proyectos sólidos, pero dependientes de un vendor (Seldon) o de una sola compañía
patrocinadora (IBM, Microsoft) — un riesgo de continuidad real, aunque distinto al
de un proyecto sin ningún respaldo corporativo.

---

## 3. El dinero: qué se está financiando

| Actor | Hecho verificado |
|---|---|
| **Zest AI** | Integración nativa anunciada con Temenos Loan Origination, 29 de abril de 2025 — el capital y la distribución van hacia **integrarse en el core existente**, no hacia venderse como capa aparte ([Zest AI / Temenos](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/)) |
| **LQN Hipotecas** (Colombia) | Ronda de **US$12M** (US$10,5M deuda + US$1,5M equity) cerrada en noviembre de 2025, liderada por Grupo Pegasus, para pasar de facilitador tecnológico a originador de crédito propio ([Forbes Colombia, 6 nov 2025](https://forbes.co/2025/11/06/emprendedores/lqn-recibe-us12-millones-para-lanzar-creditos-con-garantia-hipotecaria)) |
| **FICO Platform** | Sin ronda de capital reciente identificada (FICO es una empresa pública consolidada, no una startup en fundraising) — su tracción se mide en clientes: Nationwide Building Society (~23M usuarios) implementando estrategias de riesgo 50% más rápido con la plataforma ([EmpreFinanzas, ago 2026](https://emprefinanzas.com.mx/2026/08/13/la-inteligencia-artificial-en-la-transformacion-bancaria-la-brecha-real-no-es-la-tecnologia-sino-la-confianza-a-gran-escala/)) |

**La lectura relevante:** el capital que se está moviendo en esta categoría **no
está financiando "el motor de scoring
explicable" como producto independiente** — está financiando (a) integraciones
nativas dentro de cores bancarios ya establecidos (Zest AI + Temenos), o (b)
originadores que absorben todo el proceso de principio a fin, IA incluida (LQN). No
encontré una ronda de capital comparable financiando específicamente "capa de
explicabilidad y gobernanza para scoring de crédito, vendida por separado a
bancos" — que es, en esencia, lo que propone Vectra Risk. **Esto no significa que
no exista mercado; significa que no encontré evidencia pública de que el capital de
riesgo esté apostando por esa forma específica del producto.**

---

## 4. Lo que hacen los grandes jugadores establecidos

En scoring de crédito, el techo de la categoría lo ponen **plataformas de decisión
crediticia especializadas**, no la nube genérica:

- **FICO Platform, Experian Ascend, DataRobot, Provenir, Zest AI, Taktile** — un
  mercado catalogado con al menos diez jugadores activos a mayo de 2026, cada uno
  posicionado para un segmento distinto (enterprise, mid-market, low-code) pero
  todos con explicabilidad y auditoría como requisito de entrada, no como
  diferenciador ([DevOpsSchool, 27 may 2026](https://www.devopsschool.com/blog/top-10-ai-credit-scoring-platforms-features-pros-cons-comparison/)).
- Los hyperscalers genéricos (AWS SageMaker, Azure ML, Vertex AI) proveen la
  infraestructura de MLOps subyacente, pero **no compiten directamente en scoring
  de crédito como producto vertical** — ahí es donde entran los vendors
  especializados de la lista anterior, construidos encima de esa infraestructura.

Ninguno de estos jugadores especializados publicita explícitamente el crédito de
vivienda colombiano (VIS, subsidios, tasas certificadas por la Superintendencia
Financiera) como caso de uso de fábrica — es el hueco de conocimiento local que
`mercado.md` identifica como el espacio potencialmente defendible de Vectra Risk.

---

## 5. La tensión central de la categoría

Esta es la formulación más útil que produjo esta investigación. **Es una hipótesis,
no un hecho de mercado** — hay que presentarla así, sin darla por validada.

> El mercado de decisión crediticia con IA se parte en dos polos, y ninguno resuelve
> el problema completo de un banco mediano colombiano:
>
> 1. **Originadores tecnológicos verticales** (LQN y similares): resuelven
>    velocidad y experiencia de originación de punta a punta, pero el modelo de
>    decisión vive fuera del banco, en la infraestructura de un tercero no
>    regulado como entidad financiera.
> 2. **Plataformas enterprise globales de decisión crediticia** (FICO, Zest AI,
>    Experian Ascend): resuelven explicabilidad y gobernanza a nivel mundial, pero
>    no traen de fábrica el conocimiento normativo específico del crédito de
>    vivienda colombiano, y su modelo de despliegue no siempre es self-hosted
>    dentro de la infraestructura regulada del cliente.
>
> El hueco es el cruce entre ambos: **un motor de decisión que vive dentro de la
> infraestructura del propio banco, con el conocimiento normativo local, y con la
> velocidad que el mercado ya espera después de ver operar a LQN.** Eso es lo que
> propone Vectra Risk — y también es exactamente lo que `critica.md` pone en duda
> en su sección 4: que ese hueco sea lo bastante ancho y lo bastante defendible
> para sostener un negocio.

Que la formulación sea ordenada no la hace cierta. Validarla exige, como mínimo,
entrevistas directas con áreas de riesgo de bancos medianos colombianos — trabajo
de campo que este documento no reemplaza.

---

## 6. Contexto macro (cifras verificadas, y una que no lo está)

- La cartera hipotecaria de vivienda en Colombia cerró Q4 2025 en **$153,2 billones
  de pesos**, con un crecimiento anual del 11,2%, pero equivale a solo el **7,4%
  del PIB** — muy por debajo de Chile (26,3%) ([Valora Analitik, 21 may 2026](https://www.valoraanalitik.com/colombia-fintech-propone-reformas-a-mercado-vivienda-usada-para-generar-potencial-de-crecimiento/)).
- El BIS (Instituto de Estabilidad Financiera) publicó el 12 de diciembre de 2024
  que la IA **exacerba** riesgos ya existentes en finanzas (modelo, crédito,
  privacidad) pero no introduce riesgos fundamentalmente nuevos, y que la mayoría
  de reguladores no ha emitido normas de IA específicas para el sector financiero
  ([Global Regulation Tomorrow, 13 dic 2024](https://www.regulationtomorrow.com/2024/12/bis-paper-regulating-ai-in-the-financial-sector-recent-developments-and-main-challenges/)).

Y la que hay que leer con sospecha, no repetir sin más:

- Las cifras de "tamaño del mercado global de AI credit scoring" que circulan en
  reportes de firmas de market research **se contradicen entre sí por un factor de
  más de 5x** para períodos comparables (de USD 1.900M a USD 9.800M), sin
  metodología pública verificable. Desarrollado en detalle en `mercado.md`,
  sección 1. No las repito aquí como si fueran un hecho establecido.

---

## 7. Qué NO se pudo verificar

Registrado a propósito:

- **Si Kubeflow completó su transferencia de gobernanza a la CNCF** tras aplicar en
  2022, o si sigue bajo Linux Foundation AI & Data de forma independiente. La
  fuente que encontré es de la fecha de la solicitud, no de un resultado
  confirmado.
- **Cuántas rondas de capital de riesgo específicas ha recibido la categoría
  "explicabilidad y gobernanza de IA para crédito" como producto independiente**
  (fuera de Zest AI, que se integra a un core existente en vez de venderse como
  capa aparte), del tipo de las rondas grandes que sí se ven en categorías
  adyacentes de infraestructura y developer tooling.
- **Si algún vendor global de la sección 4 (FICO, Zest AI, Experian) ofrece
  despliegue self-hosted real dentro de la infraestructura de un banco
  latinoamericano.** Lo asumí como hueco de mercado en `mercado.md`, pero no lo
  confirmé directamente contra la documentación comercial de cada vendor —
  **queda como supuesto a validar antes de usarlo como argumento de venta en el
  PRD.**

---

*Material de referencia — Tópicos Especiales en Informática*
