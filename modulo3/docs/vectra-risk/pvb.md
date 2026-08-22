# Product Vision Board — Vectra Risk

> **Caso de estudio de referencia.** Versión extendida del PVB base, ampliada con la
> investigación documentada en [`overview.md`](./overview.md), [`mercado.md`](./mercado.md),
> [`icp.md`](./icp.md) y [`critica.md`](./critica.md).
>
> **Vectra Risk es un producto hipotético construido para este curso.** Los hechos
> externos (empresas, integraciones, cifras de mercado, regulación) son reales y
> llevan fuente y fecha. Las cifras internas (pricing, márgenes, targets) son
> **[INTERNO]**: proyecciones propias del caso, y así deben leerse.

---

## PRODUCTO

**Nombre del producto:** Vectra Risk

**Descripción en una línea:** Motor de scoring de riesgo crediticio para crédito de
vivienda, desplegado como microservicios en Kubernetes, que entrega una decisión
explicable y auditable en el punto de originación, dentro de la infraestructura
regulada del propio banco — sin reemplazar el juicio del comité de crédito.

**Tagline interno:** *"El modelo puntúa, el analista decide, el registro queda."*

---

## 1. PROBLEMA

Otorgar crédito de vivienda no es un problema de "tener un buen modelo predictivo".
Modelos de árboles de decisión, redes neuronales y SVM entrenados sobre datos de
mora de entidades colombianas ya alcanzan hasta 88,29% de AUC-ROC prediciendo
riesgo de no pago (fuente: [Redalyc](https://www.redalyc.org/journal/5537/553768213005/html/)).
El problema no es predecir mejor: es **integrar esa predicción en un proceso
regulado, explicable y defendible**, en un mercado donde la cartera hipotecaria
colombiana equivale a apenas el 7,4% del PIB —frente al 26,3% de Chile— pero crece
11,2% anual y solo el 3,3% de los colombianos tiene un crédito hipotecario activo
(fuente: [Valora Analitik, 21 may 2026](https://www.valoraanalitik.com/colombia-fintech-propone-reformas-a-mercado-vivienda-usada-para-generar-potencial-de-crecimiento/)).

De ahí salen tres dolores concretos, detallados en [`icp.md`](./icp.md):

- **El scoring vive en un notebook, no en producción.** El área de riesgo ya
  entrenó un modelo con buena métrica, pero no tiene cómo servirlo con la
  disponibilidad y trazabilidad que exige un proceso de originación regulado.
- **Explicar un rechazo hoy exige reconstruir a mano por qué el modelo decidió lo
  que decidió**, porque la explicabilidad no es parte del contrato del modelo.
- **Ya existen técnicas de explicabilidad e IA en crédito, y aun así el problema de
  gobernanza no baja.** SHAP, LIME, AIF360 y Fairlearn son gratuitos y maduros
  (ver [`overview.md`](./overview.md)), pero **no resuelven quién audita la
  decisión, cómo se versiona el modelo, ni cómo se defiende ante el comité**. El
  problema se desplaza, no desaparece.

El hueco real no es la técnica de explicabilidad. Es que **el comité de riesgo no
confía en aprobar decisiones de un modelo que no puede defender formalmente**. Un
modelo que decide crédito hipotecario sin que nadie pueda explicar un rechazo
específico es un hallazgo regulatorio esperando a ocurrir.

**Evidencia de que la tensión es real, no inventada:** el propio mercado ya se
movió hacia integrar explicabilidad de fábrica en vez de venderla aparte —Zest AI
se integró nativamente en Temenos Loan Origination en abril de 2025
([Zest AI / Temenos, 29 abr 2025](https://www.zest.ai/company/announcements/zest-ais-credit-decisioning-and-fraud-detection-now-seamlessly-integrated-with-temenos-loan-origination-solution/))—,
y a nivel local ya existe un competidor tecnológico con IA propia y capital: **LQN
Hipotecas**, con 80.000+ operaciones procesadas y US$12M de capital reciente
([Forbes Colombia, 6 nov 2025](https://forbes.co/2025/11/06/emprendedores/lqn-recibe-us12-millones-para-lanzar-creditos-con-garantia-hipotecaria)).
Cuando dos actores independientes —uno global, uno local— ya están moviéndose en
esta dirección, la tensión no es hipotética: es el estado del mercado.

### ¿Sobrevive al próximo salto de modelos?

**[X] Sí — es un problema de WORKFLOW/INTEGRACIÓN, no de OUTPUT.**

Un modelo más preciso mejora la predicción, pero no decide quién audita la
decisión, cómo se versiona el modelo, ni cómo se explica un rechazo ante la
Superintendencia. Eso es gobernanza y arquitectura, no inteligencia bruta.

**Durability Score: 4/5.** Un punto menos que en la primera versión de este PVB: la
investigación de crítica (`critica.md`, sección 1) muestra que la explicabilidad y
el monitoreo de sesgo —el núcleo de la propuesta— ya se están comoditizando más
rápido de lo asumido inicialmente, tanto en librerías gratuitas como en
integraciones comerciales nativas.

---

## 2. SEGMENTO TARGET

Detalle completo en [`icp.md`](./icp.md). Resumen:

Bancos medianos y cooperativas financieras colombianas que **ya originan crédito de
vivienda** (propio o vía brokers/proptechs como LQN) y **ya operan algo de
infraestructura en Kubernetes**, pero cuyo scoring de vivienda sigue en un motor de
reglas monolítico o en un modelo que nunca salió del notebook.

Las tres señales de calificación: reciben volumen creciente de solicitudes de
canales digitales o externos; ya operan Kubernetes para algo; y **el área de riesgo
ya construyó un modelo propio que nunca llegó a producción real** — la señal más
valiosa, porque indica que el problema es de gobernanza, no de capacidad técnica.

**Veto de confianza:** el **Vicepresidente de Riesgo / CRO**, y el **oficial de
cumplimiento / SARLAFT** en paralelo. El CRO pregunta *"¿puedo explicarle esta
decisión a la Superintendencia sin que suene a caja negra?"*; cumplimiento
pregunta *"¿puede el modelo estar discriminando por proxy sin que nadie lo note?"*.

**Contexto macro que respalda el segmento (verificado):** el riesgo crediticio
volvió a ser prioridad de primer nivel para los CRO en 2026, junto con "acelerar la
adopción responsable de la IA", según la encuesta anual de EY y el Institute of
International Finance a 101 bancos en 31 países (fuente:
[PQS, 5 jun 2026](https://pqs.pe/actualidad/economia/la-inteligencia-artificial-y-la-gestion-del-riesgo-crediticio-marcan-la-agenda-de-la-banca-en-2026/)).
El comprador existe y el tema ya está en su agenda.

**Ajuste geográfico respecto a la primera versión:** el beachhead se acota a
**Colombia únicamente**, no a Colombia/México/Brasil. El argumento regulatorio y
competitivo de Vectra Risk (Circular Externa 029 de la SFC, cartera hipotecaria
colombiana, LQN como competidor local) es específico de un país y extenderlo sin
validar sería repetir el hueco que `mercado.md` (sección 6) señala como no
resuelto en el propio ICP.

---

## 3. VENTAJA COMPETITIVA PRIMARIA

**[X] Trust**

1. **Cada decisión sale con su explicación, calculada en el mismo request**, no
   como reporte posterior — usando técnicas ya validadas en la literatura de
   scoring de crédito (SHAP, LIME; ver [`overview.md`](./overview.md)).
2. **Monitoreo de sesgo entre grupos protegidos como servicio de primera clase**,
   no como auditoría trimestral, atacando de frente el patrón de "redlining
   digital" documentado en sistemas de scoring
   ([Parada Visual, 6 nov 2025](https://www.paradavisual.com/auditoria-algoritmos-ia-eliminar-sesgos-discriminatorios-servicios/)).
3. **Historial de decisiones ligado a desenlace real de cartera**, que no se compra
   con una API: se acumula operando con datos reales del banco cliente.

**El moat no es la técnica de explicabilidad** (commodity, ver punto siguiente).
**Es el registro de explicaciones y el historial de sesgo monitoreado dentro de la
infraestructura propia del banco**, más el conocimiento normativo local que ningún
vendor global trae de fábrica.

> **Advertencia que la primera versión de este PVB no tenía:** `critica.md`
> (sección 3) muestra que explicabilidad + monitoreo de sesgo ya es **tabla
> estándar de un mercado maduro** —SHAP/LIME/AIF360/Fairlearn son gratis, y Zest AI
> ya lo ofrece integrado en Temenos—, no un diferenciador aislado. El moat real de
> Vectra Risk no puede ser "explicamos las decisiones": tiene que ser la
> combinación de soberanía del dato (self-hosted) y conocimiento normativo
> colombiano específico, como se reformula en `critica.md`, sección 8.

---

## 4. ARENA COMPETITIVA

**[X] Enhancer (AI-Enhanced)** — el scoring de crédito existe hace décadas; lo
fortalecemos con mejor arquitectura y explicabilidad verificable, no lo
reinventamos.

Análisis completo en [`mercado.md`](./mercado.md) y [`overview.md`](./overview.md).
Lo esencial:

- **Contra la capa gratuita** (SHAP, LIME, AIF360, Fairlearn, KServe): **no
  competimos, las orquestamos.** La técnica de explicabilidad está resuelta y es
  gratis; vender la técnica sola es competir contra cero. Vendemos la orquestación
  versionada, auditable y self-hosted dentro del banco.
- **Contra la capa comercial global** (FICO Platform, Zest AI ya integrado en
  Temenos, Experian Ascend, DataRobot, Provenir — al menos diez jugadores activos
  según [DevOpsSchool, 27 may 2026](https://www.devopsschool.com/blog/top-10-ai-credit-scoring-platforms-features-pros-cons-comparison/)):
  no compiten en conocimiento normativo colombiano ni, hasta donde pude verificar,
  en despliegue self-hosted dentro de la infraestructura del cliente
  latinoamericano — **[VERIFICAR directamente con cada vendor antes de usarlo como
  argumento de venta]**.
- **Contra el competidor local más concreto, LQN Hipotecas:** no le vendemos a
  LQN — LQN es, según `critica.md` (sección 4), un competidor potencial que ya
  tiene datos, capital y camino a originar crédito propio. Vectra Risk le vende a
  **los bancos que compiten con LQN** y necesitan su propio motor de decisión.

**Riesgo honesto de la arena, y es el riesgo número uno:** si un vendor global
(Zest AI, FICO) o el propio LQN deciden ofrecer despliegue self-hosted con
conocimiento normativo colombiano, la diferenciación de Vectra Risk se reduce a
velocidad de ejecución local. Desarrollado en la sección 9.

---

## 5. UX PARADIGM

**[X] Embedded Intelligence** — mejora el proceso de originación de forma
invisible para el solicitante y visible-pero-no-intrusiva para el analista.

**Por qué no Assistant ni Agent:** el analista de crédito necesita que, al abrir el
caso, el score y su explicación ya estén calculados y listos para sustentar la
decisión — no un asistente con el que conversar ni pasos de un agente que aprobar
uno por uno.

**Por qué no Autonomous:** la decisión final de otorgar o negar un crédito de
vivienda siempre la firma un humano o un comité. Ningún CRO colombiano va a
autorizar hoy un sistema que apruebe hipotecas sin firma humana.

**Sin preguntar:** calcular el score, calcular su explicación, monitorear
disparidad de sesgo, registrar la decisión.

**Nunca:** aprobar o negar un crédito por sí mismo, modificar su propia política de
negocio, ocultar una decisión de baja confianza como si fuera segura.

---

## 6. AI DECISION TRIANGLE

**[X] Capability**

- **Sacrifico velocidad frente a LQN**, que promociona desembolsos en 10 días y
  40% menos de tiempo de trámite ([Portafolio, 4 mar 2025](https://www.portafolio.co/mis-finanzas/creditos/lqn-hipotecas-desembolso-10-000-creditos-superando-los-1-5-billones-625098)).
  No competimos en velocidad de originación de punta a punta: competimos en la
  calidad y defendibilidad de la decisión que el banco toma con su propio capital.
- **Sacrifico costo de cómputo** calculando explicabilidad en cada request.
- **Sacrifico cobertura inicial**, priorizando el crédito de vivienda estándar
  antes que ingresos informales o mixtos.

**Razón de fondo:** el costo de una decisión mal explicada no es el token
desperdiciado — es un hallazgo del regulador o una demanda por discriminación
algorítmica.

---

## 7. MODELO ECONÓMICO

**Todas las cifras de esta sección son [INTERNO] — no encontré benchmarks públicos
de pricing de risk-tech B2B bancario en Colombia contra los cuales contrastarlas
(ver `pvb.md` original y `critica.md`, sección 8).**

**Modelo:** Hybrid Tiered — licencia por entidad financiera con límites crecientes
de solicitudes evaluadas al mes.

- **Starter:** $2.500 USD/mes, hasta 500 solicitudes/mes, 1 clúster.
- **Growth:** $8.000 USD/mes, hasta 3.000 solicitudes/mes, dashboard de sesgo
  incluido.
- **Enterprise:** a convenir, despliegue self-hosted (un requisito frecuente en
  banca regulada).

**¿Escala a 10x?** **[X] Sí, con un ajuste.** El costo marginal es cómputo de
inferencia + explicabilidad, que escala con solicitudes evaluadas, no con usuarios
internos del banco.

**Economía por cuenta (tier Growth) [INTERNO]:**

| Concepto | Mensual |
|---|---|
| Cómputo de inferencia + explicabilidad | $900 |
| Almacenamiento de historial y auditoría | $250 |
| Soporte e integración prorrateados | $1.200 |
| **Costo total** | **$2.350** |
| **Revenue** | **$8.000** |
| **Gross margin** | **~71%** |

El margen se sostiene si la mayoría de solicitudes se resuelve con el modelo
ligero (features tabulares) y solo una fracción exige variables alternativas no
estructuradas. Es una decisión económica, no solo técnica.

---

## 8. MÉTRICAS DE ÉXITO

**Métricas de usuario**

1. **Tiempo de originación desde solicitud hasta decisión con score explicado.**
   *Target: menos de 1 hora en el 80% de los casos estándar.* **[INTERNO]** — para
   dimensionar la ambición: LQN ya promete el ciclo completo en 10 días frente a
   más de 100 días de trámite tradicional, así que el scoring no puede ser el
   cuello de botella.
2. **Tasa de decisiones del modelo sostenidas sin modificación por el comité de
   crédito.** *Target: >70% al mes 6.* **[INTERNO]**

**Métricas de IA**

1. **AUC-ROC del modelo sobre cartera real del cliente.** *Target: >0.85*, en línea
   con la literatura académica colombiana (Redalyc, hasta 88,29%). **[INTERNO,
   contrastado contra benchmark académico, no contra cartera real todavía]**
2. **Disparidad de tasa de aprobación entre grupos protegidos.** *Target: <5 puntos
   porcentuales controlando por capacidad de pago. Por encima, el modelo se
   congela.* **[INTERNO]**
3. **Tasa de adopción real de la explicación por el comité de crédito** — no solo
   si el reporte se genera, sino si **cambia** una decisión o solo la **justifica
   después**. *Target: a definir con el primer cliente piloto.* **[INTERNO, métrica
   nueva respecto a la primera versión del PVB]**

**Salud secundaria:** porcentaje de decisiones que llegan con explicación completa,
sin degradación por timeout o fallo de microservicio.

> **Nota metodológica importante:** el target de AUC-ROC >0.85 no es un hallazgo
> validado contra la cartera de un cliente real — es una meta de producto anclada
> en un benchmark académico sobre otro conjunto de datos. Extrapolarlo directamente
> sería el mismo error de traslado de dominio que `critica.md` (sección 10) señala
> y evita al descartar la cifra de Gartner sobre cancelación de proyectos de IA
> agéntica para este caso: la cifra existe, mide algo real, pero no mide lo que
> Vectra Risk necesita medir hasta que se valide con datos propios.

---

## 9. RIESGOS CRÍTICOS

### 1. Comoditización — ya está ocurriendo, no es un riesgo futuro

**Riesgo alto — es el riesgo principal.** El scoring predictivo ya es una
commodity académica (88%+ de AUC con técnicas conocidas). La explicabilidad y el
monitoreo de sesgo, que sostienen el moat de la sección 3, también lo son: SHAP,
LIME, AIF360 y Fairlearn son gratuitos, y **Zest AI ya está integrado nativamente
en Temenos Loan Origination** desde abril de 2025. Y localmente, **LQN Hipotecas**
—80.000+ operaciones, US$12M de capital— podría pasar de originador a vendedor de
su propia capa de decisión en cualquier momento.

*Mitigación:* no apostar a la técnica de explicabilidad sino al **registro
acumulado de decisiones y desenlaces dentro de la infraestructura propia del
banco, con conocimiento normativo colombiano específico** — lo que ni Zest AI/FICO
(sin despliegue local verificado) ni LQN (no es una entidad regulada) ofrecen hoy.

### 2. El argumento regulatorio es más débil de lo que parece

A diferencia de lo que la primera versión de este PVB daba a entender, **no existe
una circular vinculante y específica de la Superintendencia Financiera de Colombia
sobre explicabilidad de IA en scoring de crédito**. Lo que hay son declaraciones
públicas del Superintendente y una circular general de gestión de riesgos de 2014
(Circular Externa 029). Esto es consistente con el hallazgo global: el BIS
concluyó en diciembre de 2024 que la mayoría de reguladores financieros no ha
emitido normas de IA específicas, porque consideran que los marcos existentes ya
cubren estos riesgos ([Global Regulation Tomorrow, 13 dic 2024](https://www.regulationtomorrow.com/2024/12/bis-paper-regulating-ai-in-the-financial-sector-recent-developments-and-main-challenges/)).

*Mitigación:* vender el argumento correcto — "su marco de gestión de riesgo ya
vigente exige esto, y su scoring actual probablemente no lo cumple del todo" — no
el argumento de una norma de IA que no existe.

### 3. ¿Replicable en 6 semanas?

**El modelo y los microservicios sí; la confianza regulatoria y el historial de
LQN no.** Un equipo competente sirve un modelo razonable con KServe en pocas
semanas. No se replica: el historial de decisiones ligado a desenlace real (que
LQN ya tiene parcialmente con 80.000+ operaciones y Vectra Risk tendría que
construir desde cero), y la certificación implícita de haber pasado una auditoría
de sesgo ante un CRO que ya confió en el sistema.

### 4. Cómo se rompe la confianza a escala

1. **El monitoreo de sesgo da una falsa sensación de control.** Las explicaciones
   post-hoc (SHAP/LIME) son aproximaciones, no una lectura directa del
   razonamiento del modelo (`critica.md`, sección 6). Publicar una métrica de
   disparidad <5 puntos no prueba ausencia de discriminación por proxy si las
   variables alternativas codifican el mismo sesgo de otra forma.
   *Mitigación:* medir disparidad **antes y después** de cada nueva fuente de
   datos alternativa, no solo el estado agregado.
2. **Irrelevancia silenciosa.** El comité archiva la explicación sin usarla para
   decidir nada, mientras las métricas de seguridad siguen viéndose perfectas
   (`critica.md`, sección 5). Es el modo de fallo más probable, y por eso se
   incorporó la métrica 3 de la sección 8.
3. **Desincronía entre `scoring-service` y `explainability-service`.** Si se
   desincronizan por una versión de modelo distinta o un despliegue parcial, el
   sistema puede entregar una explicación plausible que ya no corresponde a la
   decisión real, y nadie lo notaría porque ambos siguen respondiendo con éxito.
   *Mitigación:* diseño *fail-closed* — si la explicación no responde, el score
   tampoco se entrega como decisión usable.
4. **Fuga de datos sensibles del solicitante** a través de logs o del pipeline de
   monitoreo de sesgo.
   *Mitigación:* segmentación de red (NetworkPolicies), cifrado, despliegue
   self-hosted para el tier Enterprise.

**Verdad incómoda:** este producto ya no vive o muere solo por la confianza del
CRO — también vive o muere por si un competidor con más datos y más capital (LQN)
decide entrar al mismo carril antes de que Vectra Risk construya su propio
historial. Esa ventana puede cerrarse más rápido de lo que la primera versión de
este documento asumía.

---

*Material de referencia — Tópicos Especiales en Informática*
